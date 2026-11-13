# -*- coding: utf-8 -*-
"""가짜 전송으로 날짜별 상위 글과 불확실한 응답의 중복 방지를 확인함."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from tools import slack_threads as threads
from tools.slack_notify import endpoint

CHANNEL = "C123ABC456"
ANCHOR = "a" * 40
PARENT = "1794490000.000001"
REPLY = "1794490000.000002"


class Ledger:
    def __init__(self):
        self.rows, self.posts = [], []
        self.fail_ready = False

    def pages(self, path):
        if path != endpoint("commits/%s/statuses" % ANCHOR):
            raise AssertionError(path)
        return iter(self.rows)

    def post(self, path, payload):
        if path != endpoint("statuses/" + ANCHOR):
            raise AssertionError(path)
        if self.fail_ready and payload["description"].startswith("ready:"):
            raise OSError("저장 중 연결 끊김")
        self.posts.append(payload.copy())
        self.rows.insert(0, {**payload, "created_at": "2026-11-12T14:00:00Z"})


class DailyThreadTest(unittest.TestCase):
    def setUp(self):
        self.github = Ledger()
        self.sender = threads.DailyThreads(self.github, "xoxb-example", CHANNEL, ANCHOR)
        self.date = patch.object(threads, "korean_day", return_value="2026-11-12")
        self.date.start()
        self.addCleanup(self.date.stop)
        self.transport = patch.object(threads, "post_message", side_effect=[PARENT, REPLY, REPLY])
        self.post = self.transport.start()
        self.addCleanup(self.transport.stop)

    def test_same_day_reuses_one_parent_and_replies_without_channel_broadcast(self):
        card = {"text": "PR 결과", "blocks": []}
        self.sender.send(card)
        self.sender.send(card)
        calls = [call.args[0] for call in self.post.call_args_list]
        self.assertEqual("2026-11-12 오늘의 PR", calls[0]["text"])
        self.assertNotIn("thread_ts", calls[0])
        self.assertEqual([PARENT, PARENT], [payload["thread_ts"] for payload in calls[1:]])
        self.assertTrue(all(payload["reply_broadcast"] is False for payload in calls[1:]))
        self.assertNotIn("thread_ts", card)
        self.assertEqual(["creating", "ready:" + PARENT], [row["description"] for row in self.github.posts])

    def test_pr_and_server_use_separate_threads_on_the_same_day(self):
        server = threads.DailyThreads(self.github, "xoxb-example", CHANNEL, ANCHOR, topic="server")
        server_ts = "1794490001.000003"
        self.post.side_effect = [PARENT, server_ts, REPLY]
        self.sender.parent("2026-11-12")
        self.assertEqual(server_ts, server.parent("2026-11-12"))
        server.send({"text": "연결 테스트 복구"})
        parent, reply = [entry.args[0] for entry in self.post.call_args_list[1:]]
        self.assertIn("금일 서버 상태 모니터링", parent["text"])
        self.assertIn("2026-11-12", parent["text"])
        self.assertEqual(server_ts, reply["thread_ts"])
        self.assertFalse(reply["reply_broadcast"])
        self.assertEqual(2, len({row["context"] for row in self.github.posts}))

    def test_new_korean_day_creates_a_different_parent(self):
        self.sender.send({"text": "어제 결과"})
        self.post.side_effect = ["1794490001.000001", REPLY]
        with patch.object(threads, "korean_day", return_value="2026-11-13"):
            self.sender.send({"text": "오늘 결과"})
        self.assertEqual("2026-11-13 오늘의 PR", self.post.call_args_list[-2].args[0]["text"])
        self.assertEqual("1794490001.000001", self.post.call_args.args[0]["thread_ts"])
        self.assertEqual(2, len({row["context"] for row in self.github.posts}))

    def test_uncertain_parent_response_does_not_create_another_parent(self):
        self.post.side_effect = URLError("응답 확인 불가")
        with self.assertRaises(URLError):
            self.sender.send({"text": "PR 결과"})
        self.post.reset_mock()
        with self.assertRaises(URLError):
            self.sender.send({"text": "다른 PR 결과"})
        self.post.assert_not_called()
        self.assertEqual("creating", self.github.rows[0]["description"])

    def test_explicit_rejection_can_retry_and_keeps_the_parent_for_replies(self):
        self.post.side_effect = [ValueError("전송 거절"), PARENT, REPLY]
        with self.assertRaises(ValueError):
            self.sender.send({"text": "PR 결과"})
        self.assertEqual("failed", self.github.rows[0]["description"])
        self.sender.send({"text": "다시 보낸 결과"})
        self.assertEqual(PARENT, self.post.call_args.args[0]["thread_ts"])

    def test_failure_to_store_parent_confirmation_keeps_creation_pending(self):
        self.github.fail_ready = True
        with self.assertRaises(OSError):
            self.sender.send({"text": "PR 결과"})
        self.github.fail_ready = False
        self.post.reset_mock()
        with self.assertRaises(URLError):
            self.sender.send({"text": "다른 결과"})
        self.post.assert_not_called()

    def test_known_parent_is_not_recreated_when_a_reply_fails(self):
        self.post.side_effect = [PARENT, ValueError("답글 거절"), REPLY]
        with self.assertRaises(ValueError):
            self.sender.send({"text": "PR 결과"})
        self.sender.send({"text": "답글 다시 보내기"})
        self.assertEqual(PARENT, self.post.call_args.args[0]["thread_ts"])
        self.assertEqual(2, len(self.github.posts))


class TransportTest(unittest.TestCase):
    def response(self, **values):
        return json.dumps({"ok": True, "channel": CHANNEL, "ts": REPLY, **values}).encode()

    def test_recipient_is_fixed_and_token_is_only_in_the_authorization_header(self):
        with patch.object(threads, "read_url", return_value=self.response()) as read:
            self.assertEqual(REPLY, threads.post_message({"text": "결과", "channel": "COTHER123"}, "xoxb-example", CHANNEL))
        request = read.call_args.args[0]
        self.assertEqual("https://slack.com/api/chat.postMessage", request.full_url)
        self.assertEqual(CHANNEL, json.loads(request.data)["channel"])
        self.assertNotIn("xoxb-example", request.full_url + request.data.decode())
        self.assertEqual("Bearer xoxb-example", request.headers["Authorization"])

    def test_unknown_success_response_is_not_treated_as_a_retryable_rejection(self):
        for raw in (b"not-json", self.response(channel="COTHER123"), self.response(ts="invalid"), b"{}"):
            with self.subTest(raw=raw), patch.object(threads, "read_url", return_value=raw), self.assertRaises(URLError):
                threads.post_message({"text": "결과"}, "xoxb-example", CHANNEL)

    def test_declared_slack_error_is_reported_without_response_secrets(self):
        with patch.object(threads, "read_url", return_value=self.response(ok=False, error="missing_scope", detail="xoxb-private-value")):
            with self.assertRaises(ValueError) as error:
                threads.post_message({"text": "결과"}, "xoxb-example", CHANNEL)
        self.assertNotIn("xoxb-private-value", str(error.exception))

    def test_unknown_application_errors_remain_uncertain(self):
        for name in ("fatal_error", "internal_error", "service_unavailable", "request_timeout", "xoxb-private-value"):
            with self.subTest(error=name), patch.object(threads, "read_url", return_value=self.response(ok=False, error=name)):
                with self.assertRaises(URLError) as caught:
                    threads.post_message({"text": "결과"}, "xoxb-example", CHANNEL)
                self.assertIs(type(caught.exception), URLError)
                self.assertNotIn("xoxb-private-value", str(caught.exception))

    def test_response_read_failure_keeps_delivery_uncertain(self):
        with patch.object(threads, "read_url", side_effect=ValueError("응답 크기 초과")):
            with self.assertRaises(URLError) as caught:
                threads.post_message({"text": "결과"}, "xoxb-example", CHANNEL)
        self.assertIs(type(caught.exception), URLError)

    def test_server_error_is_uncertain_but_rate_limit_is_an_explicit_rejection(self):
        for code, expected in ((500, URLError), (408, URLError), (429, HTTPError)):
            error = HTTPError("https://slack.com/api/chat.postMessage", code, "failed", {}, None)
            with self.subTest(code=code), patch.object(threads, "read_url", side_effect=error):
                with self.assertRaises(expected) as caught:
                    threads.post_message({"text": "결과"}, "xoxb-example", CHANNEL)
                self.assertIs(type(caught.exception), expected)
            error.close()


class DayTest(unittest.TestCase):
    def test_the_automatic_workflow_serializes_dates_and_event_types_together(self):
        text = (Path(__file__).resolve().parents[1]/".github/workflows/slack-notify.yml").read_text(encoding="utf-8")
        block = re.search(r"(?m)^concurrency:\n((?:[ \t]+[^\n]+\n)+)", text)
        self.assertIsNotNone(block)
        group = re.search(r"(?m)^  group: (.+)$", block[1])
        self.assertIsNotNone(group)
        self.assertNotIn("${{", group[1])
        self.assertRegex(block[1], r"(?m)^  cancel-in-progress: false$")

    def test_midnight_is_korean_time(self):
        self.assertEqual("2026-11-12", threads.korean_day(datetime(2026, 11, 12, 14, 59, 59, tzinfo=timezone.utc)))
        self.assertEqual("2026-11-13", threads.korean_day(datetime(2026, 11, 12, 15, tzinfo=timezone.utc)))
        with self.assertRaises(ValueError):
            threads.korean_day(datetime(2026, 11, 12))

    def test_invalid_configuration_is_rejected_without_requests(self):
        for token, channel, anchor in (("", CHANNEL, ANCHOR), ("xoxb-example", "U123ABC456", ANCHOR),
                                        ("xoxb-example", CHANNEL, "not-a-commit")):
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                threads.DailyThreads(Ledger(), token, channel, anchor)
