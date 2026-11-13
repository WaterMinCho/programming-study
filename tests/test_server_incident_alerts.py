import json
import os
from datetime import timedelta
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from tools import server_incident_alerts as alerts
from tools.slack_notify import WEB, endpoint

ANCHOR = "a" * 40
NEXT = "b" * 40
NOW = alerts.timestamp("2026-11-14T12:00:00Z")
LINK = WEB + "/actions/runs/681"
BOT = {"login": "github-actions[bot]", "type": "Bot"}
OWNER = {"login": "WaterMinCho", "type": "User"}
OTHER = {"login": "reviewer", "type": "User"}
HEALTH = alerts.Incident("42", "health")
TEST = alerts.Incident("1051943140", "test")
REQUEST = "rokey-recovery/42"
RESULT = "rokey-recovery-result/42"
OUTCOME = "rokey-incident/42"


class Ledger:
    def __init__(self):
        self.rows = []
        self.now = NOW

    def get(self, path):
        route, query = path.split("?")
        page = int(parse_qs(query)["page"][0])
        rows = [row for anchor, row in reversed(self.rows)
                if route == endpoint(f"commits/{anchor}/statuses")]
        return rows[(page - 1) * 100:page * 100]

    def post(self, path, data):
        anchor = path.rsplit("/", 1)[-1]
        if path != endpoint("statuses/" + anchor):
            raise AssertionError(path)
        row = {"created_at": self.now.isoformat(), "creator": BOT, **data}
        self.rows.append((anchor, row))
        return row

    def add(self, context, description, *, creator=BOT, anchor=ANCHOR, **details):
        return self.post(endpoint("statuses/" + anchor), {
            "context": context, "description": description, "state": "success", "creator": creator, **details})

    def descriptions(self, context):
        return [row["description"] for _, row in self.rows if row["context"] == context]


class IncidentAlertsTest(unittest.TestCase):
    def setUp(self):
        self.github = Ledger()
        self.send = Mock()

    def poll(self, *incidents, minutes=0, anchor=ANCHOR, previous=(), cutover=NOW):
        self.github.now = NOW + timedelta(minutes=minutes)
        alerts.relay(self.github, anchor, incidents, self.send, run_id="681", now=self.github.now,
                     previous_anchors=previous, cutover=cutover)

    def result(self, reason, **details):
        self.github.add(RESULT, reason, **{"creator": OWNER, "target_url": LINK, **details})

    def message(self):
        return self.send.call_args.args[0]["text"]

    def test_one_request_one_result_and_no_initial_or_later_notification(self):
        self.poll(HEALTH)
        self.poll(HEALTH, minutes=5)
        self.send.assert_not_called()
        self.assertEqual(self.github.descriptions(REQUEST), ["requested"])
        row = self.github.rows[0][1]
        self.assertEqual((row["state"], row["target_url"]), ("pending", LINK))
        self.result("reload_verified")
        self.poll(HEALTH, minutes=6)
        self.poll(alerts.Incident("42", "health", NOW), minutes=15)
        self.send.assert_called_once()
        self.assertIn("수집 서버 장애 #42", self.message())
        self.assertIn(alerts.RESULTS["reload_verified"], self.message())
        self.assertEqual(self.github.descriptions(OUTCOME), ["sending", "sent"])

    def test_each_worker_outcome_and_deadline(self):
        for reason, text in alerts.RESULTS.items():
            with self.subTest(reason=reason):
                self.setUp()
                self.poll(HEALTH)
                self.result(reason)
                self.poll(HEALTH, minutes=9)
                if reason not in ("reload_verified", "already_up"):
                    self.send.assert_not_called()
                self.poll(HEALTH, minutes=10)
                self.send.assert_called_once()
                self.assertIn(text, self.message())

    def test_resolution_waits_for_pending_ack_and_describes_both_observations(self):
        self.poll(HEALTH)
        resolved = alerts.Incident("42", "health", NOW)
        self.poll(resolved, minutes=5)
        self.send.assert_not_called()
        self.result("reload_still_down")
        self.poll(resolved, minutes=6)
        self.assertIn(alerts.RESULTS["reload_still_down"], self.message())
        self.assertIn("Better Stack", self.message())
        self.assertNotIn("기록은 없습니다", self.message())

    def test_resolved_without_action_evidence(self):
        for requested in (True, False):
            with self.subTest(requested=requested):
                self.setUp()
                if requested:
                    self.poll(HEALTH)
                self.poll(alerts.Incident("42", "health", NOW), minutes=10)
                self.assertIn("확인된 자동 복구 작업 기록은 없습니다", self.message())
                self.assertIn("해결", self.message())
                self.assertEqual(len(self.github.descriptions(REQUEST)), int(requested))

    def test_untrusted_or_uncorrelated_status_cannot_report_or_suppress_recovery(self):
        self.github.add(REQUEST, "requested", creator=OWNER, state="pending", target_url=LINK)
        self.github.add(OUTCOME, "sent", creator=OTHER)
        self.poll(HEALTH, minutes=60)
        self.assertEqual(len(self.github.descriptions(REQUEST)), 2)
        for details in ({"creator": OTHER}, {"creator": BOT}, {"creator": {**OWNER, "type": "Bot"}},
                        {"target_url": LINK + "1"}, {"state": "pending"},
                        {"created_at": NOW.isoformat()}):
            self.result("reload_verified", **details)
            self.poll(HEALTH, minutes=65)
            self.send.assert_not_called()
        self.result("<!channel> private diagnostic")
        self.poll(HEALTH, minutes=69)
        self.send.assert_not_called()
        self.poll(HEALTH, minutes=70)
        self.assertIn("10분", self.message())
        self.assertNotIn("private", self.message())
        self.assertNotIn("다시 불러온 뒤", self.message())

    def test_first_seen_resolved_test_cutover_and_legacy_ack(self):
        old = alerts.Incident("10", "health", NOW - timedelta(seconds=1))
        resolved = alerts.Incident(TEST.identifier, "test", NOW)
        historical = alerts.Incident("11", "test", NOW)
        self.github.add(alerts.legacy_resolution("11"), "sent")
        self.poll(old, historical, resolved)
        self.poll(old, historical, resolved)
        self.send.assert_called_once()
        self.assertIn("연결 테스트 #1051943140", self.message())
        self.assertIn("해결", self.message())
        self.assertFalse(any("rokey-recovery/" in row["context"] for _, row in self.github.rows))

    def test_default_cutover_is_durable_after_missed_poll(self):
        old = alerts.Incident("10", "test", NOW - timedelta(days=1))
        self.poll(old, cutover=None)
        self.send.assert_not_called()
        fresh = alerts.Incident("11", "test", NOW + timedelta(minutes=1))
        self.poll(old, fresh, minutes=90, cutover=None)
        self.assertIn("연결 테스트 #11", self.message())
        self.assertEqual(self.github.descriptions(alerts.BASELINE), ["enabled"])

    def test_test_timeout_counts_from_first_observation_without_worker(self):
        self.poll(TEST, minutes=60)
        self.poll(TEST, minutes=69)
        self.send.assert_not_called()
        self.poll(TEST, minutes=70)
        self.poll(alerts.Incident(TEST.identifier, "test", NOW), minutes=71)
        self.send.assert_called_once()
        self.assertIn("연결 테스트 #1051943140", self.message())
        self.assertIn("10분", self.message())
        self.assertEqual(self.github.descriptions("rokey-recovery/" + TEST.identifier), [])

    def test_ambiguous_response_blocks_retry_without_starving_other_incidents(self):
        resolved = alerts.Incident("42", "health", NOW)
        self.send.side_effect = URLError("uncertain")
        with self.assertRaises(URLError):
            self.poll(resolved)
        self.send.side_effect = None
        self.send.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "42"):
            self.poll(resolved, alerts.Incident("43", "test", NOW), minutes=1)
        self.send.assert_called_once()
        self.assertIn("#43", self.message())
        self.assertEqual(self.github.descriptions(OUTCOME), ["sending"])

    def test_known_rejection_allows_retry(self):
        resolved = alerts.Incident("42", "health", NOW)
        for rejection in (ValueError("invalid_auth"), HTTPError("url", 429, "rejected", {}, None)):
            with self.subTest(rejection=type(rejection).__name__):
                self.setUp()
                self.send.side_effect = rejection
                with self.assertRaises(type(rejection)):
                    self.poll(resolved)
                self.assertEqual(self.github.descriptions(OUTCOME), ["sending", "retry"])
                self.send.side_effect = None
                self.poll(resolved)
                self.poll(resolved)
                self.assertEqual(self.send.call_count, 2)
                self.assertEqual(self.github.descriptions(OUTCOME)[-1], "sent")

    def test_owner_may_only_reconcile_sent_or_retry(self):
        for final in ("sent", "retry"):
            with self.subTest(final=final):
                self.setUp()
                self.github.add(OUTCOME, "sending")
                for author, description in ((OTHER, "retry"), (OWNER, "observed"), (OWNER, "requested"),
                                            (OWNER, "sending"), (OWNER, "simulation")):
                    self.github.add(OUTCOME, description, creator=author)
                resolved = alerts.Incident("42", "health", NOW)
                with self.assertRaises(RuntimeError):
                    self.poll(resolved)
                self.send.assert_not_called()
                self.github.add(OUTCOME, final, creator=OWNER)
                self.poll(resolved)
                self.poll(resolved)
                self.assertEqual(self.send.call_count, int(final == "retry"))

    def test_lost_sent_write_holds_delivery_across_anchor_rotation(self):
        resolved = alerts.Incident("42", "health", NOW)
        post = self.github.post

        def lose_ack(path, payload):
            if payload["description"] == "sent":
                raise TimeoutError
            return post(path, payload)

        with patch.object(self.github, "post", side_effect=lose_ack), self.assertRaises(TimeoutError):
            self.poll(resolved)
        # 이전 전송이 첫 페이지 뒤로 밀린 상태를 재현함.
        for _ in range(101):
            self.github.add("unrelated", "sent")
        with self.assertRaises(RuntimeError):
            self.poll(resolved, anchor=NEXT, previous=(ANCHOR,))
        self.send.assert_called_once()
        self.github.add(OUTCOME, "sent", creator=OWNER, anchor=NEXT)
        self.poll(resolved, anchor=NEXT, previous=(ANCHOR,))
        self.send.assert_called_once()


class SourceAndWorkflowTest(unittest.TestCase):
    def test_poll_is_monitor_scoped_and_discards_body(self):
        def response(identifier, monitor, **attrs):
            return {"id": identifier, "type": "incident",
                    "attributes": {"started_at": NOW.isoformat(), "resolved_at": None,
                                   "response_content": "private payload", **attrs},
                    "relationships": {"monitor": {"data": {"type": "monitor", "id": monitor}}}}

        pages = [
            [response("42", "1"), response("43", "2"), response("44", "1", started_at=None),
             response("4/5", "1")],
            [response("42", "1", resolved_at=NOW.isoformat())],
            [response(TEST.identifier, "2"), response("45", "1")]]
        data = [json.dumps({"data": rows, "pagination": {"next": i == 0}}).encode()
                for i, rows in enumerate(pages)]
        with patch.object(alerts, "read_url", side_effect=data) as read:
            events = list(alerts.events({"health": "monitor:1", "test": "monitor:2"}, "token"))
        self.assertEqual(events, [alerts.Incident("42", "health", NOW), TEST])
        self.assertNotIn("private payload", repr(events))
        requests = [call.args[0] for call in read.call_args_list]
        self.assertEqual([parse_qs(urlparse(r.full_url).query)["monitor_id"] for r in requests],
                         [["1"], ["1"], ["2"]])
        self.assertTrue(all(r.get_header("Authorization") == "Bearer token" for r in requests))

    def test_main_ensures_daily_parent_on_empty_and_before_attempting_reply(self):
        env = {"GH_TOKEN": "token", "SLACK_STUDY_BOT_TOKEN": "bot", "SLACK_STUDY_CHANNEL_ID": "channel",
               "SLACK_STUDY_THREAD_ANCHOR": ANCHOR, "BETTER_STACK_INCIDENTS_READ_TOKEN": "read",
               "ROKEY_INCIDENT_RESOURCES": "{}", "GITHUB_RUN_ID": "681", "ROKEY_INCIDENT_CUTOVER_AT": NOW.isoformat()}
        with patch.dict(os.environ, env, clear=True), patch.object(alerts, "DailyThreads") as threads, \
                patch.object(alerts, "Client", return_value=Ledger()) as client, patch.object(alerts, "relay") as relay:
            alerts.main()
            threads.assert_called_once_with(client.return_value, "bot", "channel", ANCHOR, topic="server")
            threads.return_value.parent.assert_called_once_with(alerts.korean_day())
            self.assertEqual(relay.call_args.args[3], threads.return_value.send)
            relay.reset_mock()
            threads.return_value.parent.side_effect = URLError("parent uncertain")
            with self.assertRaises(URLError):
                alerts.main()
            relay.assert_not_called()

    def test_main_posts_one_daily_parent_and_one_nonbroadcast_test_reply(self):
        from tools import slack_notify, slack_summary, slack_threads

        ledger = Ledger()
        slack_payloads = []
        route = endpoint("statuses/" + ANCHOR)

        def github_post(request):
            self.assertEqual(request.full_url, "https://api.github.com" + route)
            return json.dumps(ledger.post(route, json.loads(request.data))).encode()

        def github_get(request):
            path = request.full_url.removeprefix("https://api.github.com")
            return json.dumps(ledger.get(path)).encode()

        def slack_post(request):
            payload = json.loads(request.data)
            slack_payloads.append(payload)
            return json.dumps({"ok": True, "channel": payload["channel"],
                               "ts": f"1794490000.{len(slack_payloads):06}"}).encode()

        env = {"GH_TOKEN": "token", "SLACK_STUDY_BOT_TOKEN": "xoxb-test", "SLACK_STUDY_CHANNEL_ID": "C12345678",
               "SLACK_STUDY_THREAD_ANCHOR": ANCHOR, "BETTER_STACK_INCIDENTS_READ_TOKEN": "read",
               "ROKEY_INCIDENT_RESOURCES": '{"test":"monitor:2"}', "GITHUB_RUN_ID": "681"}
        day = alerts.korean_day(NOW)
        resolved = alerts.Incident(TEST.identifier, "test", NOW)
        with patch.dict(os.environ, env, clear=True), patch.object(alerts, "korean_day", return_value=day), \
                patch.object(slack_threads, "korean_day", return_value=day), \
                patch.object(alerts, "events", side_effect=[[], [resolved], [resolved]]), \
                patch.object(slack_summary, "read_url", side_effect=github_post), \
                patch.object(slack_notify, "read_url", side_effect=github_get), \
                patch.object(slack_threads, "read_url", side_effect=slack_post):
            for _ in range(3):
                alerts.main()
        parent, reply = slack_payloads
        self.assertNotIn("thread_ts", parent)
        self.assertIn(day, parent["text"])
        self.assertIn("연결 테스트 #1051943140", reply["text"])
        self.assertEqual(reply["thread_ts"], "1794490000.000001")
        self.assertIs(reply["reply_broadcast"], False)
        self.assertEqual(ledger.descriptions(alerts.BASELINE), ["enabled"])

    def test_workflow_only_sends_via_bot_and_serializes_scheduled_and_manual_runs(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/server-incidents.yml").read_text()
        for value in ("SLACK_STUDY_BOT_TOKEN", "SLACK_STUDY_CHANNEL_ID", "ROKEY_INCIDENT_CUTOVER_AT",
                      "ROKEY_INCIDENT_PREVIOUS_ANCHORS", "group: rokey-server-incidents",
                      "cancel-in-progress: false", "workflow_dispatch:", "refs/heads/main"):
            self.assertIn(value, workflow)
        self.assertNotIn("WEBHOOK", workflow)
