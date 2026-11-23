# -*- coding: utf-8 -*-
"""동의·거부·재전송·철회와 공개 제출의 분리를 확인함."""
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid

from aiprep.collection import Collection, CollectionError, NOTICE, stamp
from aiprep.privacy import Consent, receipt
from aiprep import sharing
from learning_server.app import Database, application
from learning_data.collection import packed
from submission_api import Client


class PrivacyTest(unittest.TestCase):
    def test_purpose_update_asks_old_consenters_again_and_stops_collection_until_then(self):
        from learning_data import privacy
        for old_version in ("2026-11-13-v3", "2026-11-12-v2"):
            with self.subTest(old_version):
                self.setUp()
                old_hash = privacy.SUPPORTED_POLICIES[old_version]
                with mock.patch.multiple(privacy, POLICY_VERSION=old_version, POLICY_HASH=old_hash):
                    self.consent.choose(True)
                    self.consent.set_auto_submission(True)
                    for store in self.collections.values():
                        self.assertTrue(store.emit("answer", {"result": "pass", "card": "q0"}))
                old = self.consent.settings()["receipt"]
                self.assertEqual(old, privacy.validate_receipt(old, automatic=True))
                self.assertTrue(self.consent.needs_choice())
                self.assertFalse(self.consent.needs_auto_choice())
                for store in self.collections.values():
                    store.initialize_distribution()
                    self.assertFalse(store.status()["enabled"])
                    self.assertFalse(store.emit("answer", {"result": "pass", "card": "q1"}))
                self.assertEqual({"sent": 0, "errors": []}, self.consent.synchronize())
                with self.db.connect() as db:
                    self.assertEqual(0, db.execute("SELECT count(*) FROM participants").fetchone()[0])
                epochs = {name: store.status()["epoch"] for name, store in self.collections.items()}
                again = self.consent.choose(True)
                self.assertEqual(privacy.POLICY_VERSION, again["policy"])
                self.assertEqual(privacy.POLICY_VERSION, again["receipt"]["policy"])
                self.assertFalse(self.consent.needs_choice())
                self.assertTrue(self.consent.needs_auto_choice())
                for name, store in self.collections.items():
                    self.assertTrue(store.status()["enabled"])
                    self.assertNotEqual(epochs[name], store.status()["epoch"])
                    self.assertTrue(store.emit("answer", {"result": "pass", "card": "q2"}))
                result = self.consent.synchronize()
                self.assertFalse(result["errors"])
                with self.db.connect() as db:
                    cards = {json.loads(row[0])["data"].get("card") for row in db.execute("SELECT payload FROM events")}
                self.assertIn("q2", cards)
                self.assertFalse({"q0", "q1"} & cards)

    def test_old_decline_or_withdrawal_is_not_asked_again(self):
        from learning_data import privacy
        old_version = "2026-11-13-v3"
        with mock.patch.multiple(privacy, POLICY_VERSION=old_version, POLICY_HASH=privacy.SUPPORTED_POLICIES[old_version]):
            self.consent.choose(False)
        self.assertFalse(self.consent.needs_choice())
        self.assertFalse(self.consent.settings()["accepted"])
        with mock.patch.multiple(privacy, POLICY_VERSION=old_version, POLICY_HASH=privacy.SUPPORTED_POLICIES[old_version]):
            self.consent.choose(True)
            self.consent.withdraw()
            self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(self.consent.needs_choice())
        self.assertEqual(old_version, self.consent.settings()["policy"])
        for store in self.collections.values():
            self.assertFalse(store.emit("answer", {"result": "pass"}))

    def test_unknown_or_tampered_policy_is_asked_again(self):
        from learning_data import privacy
        self.consent.choose(True)
        state = self.consent.settings()
        for broken in (dict(state, policy_hash=privacy.SUPPORTED_POLICIES["2026-11-13-v3"]), dict(state, policy="2026-11-01-v1")):
            privacy.save(self.consent.path, broken)
            self.assertTrue(self.consent.needs_choice())
            with self.assertRaises(ValueError):
                privacy.validate_receipt(dict(state["receipt"], policy=broken["policy"], policy_hash=broken["policy_hash"]))

    def test_unmocked_http_is_rejected_by_the_fixture(self):
        import urllib.request
        with self.assertRaisesRegex(AssertionError, "외부 서버"):
            urllib.request.build_opener().open("https://example.invalid")

    def test_invalid_saved_consent_time_stays_a_recoverable_sync_error(self):
        self.consent.choose(True)
        from learning_data.privacy import save
        state = self.consent.settings()
        state["receipt"]["at"] = "2026-11-13T13:00:00"
        save(self.consent.path, state)
        result = self.consent.synchronize()
        self.assertEqual(0, result["sent"])
        self.assertTrue(result["errors"])
        self.assertTrue(all("시간대" in text for text in result["errors"]))

    def test_incomplete_open_connection_is_a_recoverable_error_for_manual_sync(self):
        self.consent.choose(True)
        store = self.collections["ai"]
        share = sharing.Sharing(store)
        with mock.patch.object(sharing, "request", side_effect=CollectionError("offline")):
            with self.assertRaises(CollectionError):
                share.connect_open("https://example.test", self.consent.settings()["receipt"])
        self.assertNotIn("token", share.settings())
        with self.assertRaisesRegex(CollectionError, "서버 연결을 마친 뒤"):
            share.sync("https://example.test")
        self.assertTrue(share.settings()["enroll_sent"])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.collections = {name: Collection(str(self.root / name), str(self.repo), track=name) for name in ("python", "ai")}
        self.consent = Consent(self.collections, "https://example.test")
        self.db = Database(self.root / "server/learning.sqlite3")
        self.app = application(self.db, legacy_contract=True)
        for patcher in (mock.patch.dict(os.environ, {"STUDY_OPEN_REGISTRATION": "1"}),
                        mock.patch.object(sharing, "request", self.transport),
                        mock.patch("learning_data.submission.request", self.transport),
                        mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("시험에서 외부 서버를 호출할 수 없습니다."))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def call(self, path, data=None, token=None, method="POST"):
        raw = packed(data).encode("utf-8")
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_TYPE": "application/json",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
        if token:
            env["HTTP_AUTHORIZATION"] = "Bearer " + token
        status = []
        value = json.loads(b"".join(self.app(env, lambda code, headers: status.append(code))))
        return int(status[0].split()[0]), value

    def transport(self, base, path, data=None, token=None, method="POST", **kwargs):
        status, value = self.call(path, data, token, method)
        if status != 200:
            raise CollectionError(value["error"], status=status, code=value.get("code"))
        return value

    def computer(self, name):
        """같은 서버로 보내는 다른 컴퓨터의 수집 폴더와 동의 설정을 만듦."""
        collections = {track: Collection(str(self.root / name / track), str(self.repo), track=track) for track in ("python", "ai")}
        return Consent(collections, "https://example.test")

    def verified(self, account):
        """account 계정으로 본인 확인을 마친 기기 키를 서버에 넣고 그 키를 저장한 기기 인증을 돌려줌."""
        from learning_server.app import hashed
        from learning_server.team import Access
        token = secrets.token_hex(32)
        with self.db.connect() as db:
            db.execute("INSERT INTO identity_grants (token_hash,policy,created,member,account_hash) VALUES (?,?,0,0,?)",
                       (hashed(token), Access(self.db).policy(), hashlib.sha256(account.encode()).hexdigest()))
        return SimpleNamespace(base="https://example.test", settings=lambda: {"verified": True, "team": False, "token": token})

    def links(self):
        with self.db.connect() as db:
            return db.execute("SELECT link, source FROM research_links ORDER BY participant").fetchall()

    def test_same_account_computers_share_one_link_and_one_withdrawal_removes_both(self):
        first, second = self.verified("account-1"), self.verified("account-1")
        other = self.computer("other")
        for consent in (self.consent, other):
            consent.choose(True)
            for store in consent.collections.values():
                self.assertTrue(store.emit("answer", {"result": "pass", "card": "q1"}))
        self.assertFalse(self.consent.synchronize(identity=first)["errors"])
        self.assertFalse(other.synchronize(identity=second)["errors"])
        links = self.links()
        self.assertEqual(4, len(links))
        self.assertEqual(1, len(set(links)))
        self.assertEqual("account", links[0][1])
        target = self.root / "export.jsonl"
        self.db.export(str(target))
        text = target.read_text(encoding="utf-8")
        self.assertEqual({links[0][0]}, {json.loads(line)["research_link"] for line in text.splitlines()})
        with self.db.connect() as db:
            secret = [row[0] for row in db.execute("SELECT account_hash FROM identity_grants UNION SELECT account_key FROM research_accounts")]
        self.assertEqual(2, len(secret))
        self.assertFalse([value for value in secret if value in text])
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants WHERE revoked=0").fetchone()[0])
            self.assertEqual([(None,)], db.execute("SELECT link FROM research_accounts").fetchall())
        self.assertEqual([], self.links())
        self.assertFalse(self.consent.path.with_name("research-link.json").exists())
        self.assertTrue(other.synchronize(identity=second)["errors"])
        self.assertTrue(other.settings()["withdraw_pending"])
        for store in other.collections.values():
            self.assertFalse(store.status()["enabled"])
            self.assertFalse(Path(store.path).exists())
        self.assertTrue(other.synchronize(identity=second)["withdrawn"])
        self.assertFalse(other.path.with_name("research-link.json").exists())

    def test_unverified_computer_links_its_own_courses_and_moves_to_the_account_after_verification(self):
        self.consent.choose(True)
        for store in self.collections.values():
            store.emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize()["errors"])
        links = self.links()
        self.assertEqual([links[0], links[0]], links)
        self.assertEqual("device", links[0][1])
        identity = self.verified("account-1")
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        moved = self.links()
        self.assertEqual([moved[0], moved[0]], moved)
        self.assertEqual("account", moved[0][1])
        self.assertNotEqual(links[0][0], moved[0][0])
        with self.db.connect() as db:
            db.execute("DELETE FROM identity_grants")
        self.assertFalse(self.consent.synchronize(identity=identity)["errors"])
        self.assertEqual(moved, self.links())
        other = self.computer("other")
        other.choose(True)
        self.assertFalse(other.synchronize(identity=self.verified("account-2"))["errors"])
        self.assertEqual(2, len({link for link, source in self.links()}))

    def test_withdrawal_from_a_computer_that_never_sent_records_still_reaches_the_account(self):
        first = self.verified("account-1")
        other, late = self.computer("other"), self.computer("late")
        for consent in (self.consent, other, late):
            consent.choose(True)
        other.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(other.synchronize(identity=self.verified("account-1"))["errors"])
        old = self.links()[0][0]
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize(identity=first)["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants WHERE revoked=0").fetchone()[0])
        self.assertTrue(late.synchronize(identity=self.verified("account-1"))["errors"])
        self.assertTrue(late.settings()["withdraw_pending"])
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize(identity=first)["errors"])
        renewed = {link for link, source in self.links()}
        self.assertEqual(1, len(renewed))
        self.assertNotIn(old, renewed)

    def test_server_rejects_copied_links_wrong_proofs_and_links_on_old_receipts(self):
        from learning_data import privacy
        token = self.verified("account-1").settings()["token"]
        code, value = self.call("/v1/identity/research-link", {"consented_at": receipt()["at"]}, token)
        self.assertEqual(200, code)
        again = self.verified("account-1").settings()["token"]
        self.assertEqual(value, self.call("/v1/identity/research-link", {"consented_at": receipt()["at"]}, again)[1])
        other = self.verified("account-2").settings()["token"]
        self.assertNotEqual(value["link"], self.call("/v1/identity/research-link", {"consented_at": receipt()["at"]}, other)[1]["link"])
        self.assertEqual(400, self.call("/v1/identity/research-link", {"consented_at": "2026-11-23T12:00:00"}, token)[0])
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE, "registration_secret": secrets.token_hex(32), "consent": receipt()}
        self.assertEqual(403, self.call("/v1/enroll/open", dict(packet, research_link=value["link"]))[0])
        self.assertEqual(403, self.call("/v1/enroll/open", dict(packet, research_link=value["link"], research_proof="0" * 64))[0])
        self.assertEqual(403, self.call("/v1/research-link/withdraw", {"research_link": value["link"], "research_proof": "0" * 64})[0])
        old = dict(receipt(), policy="2026-11-13-v3", policy_hash=privacy.SUPPORTED_POLICIES["2026-11-13-v3"])
        self.assertEqual(400, self.call("/v1/enroll/open", dict(packet, consent=old, research_link=str(uuid.uuid4())))[0])
        self.assertEqual(200, self.call("/v1/enroll/open", dict(packet, research_link=value["link"], research_proof=value["proof"]))[0])
        self.assertEqual([(value["link"], "account")], self.links())

    def test_decline_does_not_collect_register_or_upload(self):
        self.consent.choose(False)
        self.assertFalse(self.consent.needs_choice())
        for store in self.collections.values():
            self.assertFalse(store.emit("answer", {"result": "pass"}))
            self.assertFalse(Path(store.path).exists())
        self.assertEqual(0, self.consent.synchronize()["sent"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants").fetchone()[0])

    def test_current_consent_uploads_only_new_records_without_answer_body(self):
        for store in self.collections.values():
            store.set_enabled(True)
            store.emit("answer", {"response": "OLD PRIVATE ANSWER", "result": "fail"})
        self.consent.choose(True)
        for store in self.collections.values():
            store.emit("answer", {"response": "NEW PRIVATE ANSWER", "result": "pass"})
        result = self.consent.synchronize()
        self.assertFalse(result["errors"])
        self.assertEqual(0, self.consent.synchronize()["sent"])
        with self.db.connect() as db:
            rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM events")]
            self.assertEqual(2, sum(row["kind"] == "answer" for row in rows))
            self.assertNotIn("PRIVATE ANSWER", json.dumps(rows))
            self.assertEqual(0, db.execute("SELECT count(*) FROM submission_accounts").fetchone()[0])

    def test_pausing_python_does_not_stop_ai_automatic_upload(self):
        self.consent.choose(True)
        self.collections["python"].set_enabled(False)
        self.collections["ai"].emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize()["errors"])
        with self.db.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM events WHERE track='ai' AND json_extract(payload, '$.kind')='answer'").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM events WHERE track='python'").fetchone()[0])

    def test_offline_withdraw_stops_immediately_and_retries_remote_delete(self):
        self.consent.choose(True)
        self.consent.synchronize()
        old = [sharing.Sharing(store).settings()["token"] for store in self.collections.values()]
        self.consent.withdraw()
        with mock.patch.object(sharing, "request", side_effect=CollectionError("offline")):
            self.assertTrue(self.consent.synchronize()["errors"])
        self.assertTrue(self.consent.settings()["withdraw_pending"])
        for store in self.collections.values():
            self.assertFalse(store.status()["enabled"])
            self.assertFalse(Path(store.path).exists())
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(self.consent.settings()["withdraw_pending"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
        for token in old:
            self.assertEqual(401, self.call("/v1/events", {}, token)[0])
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize()["errors"])

    def test_registration_retries_require_private_seed_and_explicit_current_receipt(self):
        packet = {"participant": str(uuid.uuid4()), "notice": NOTICE,
                  "registration_secret": secrets.token_hex(32), "consent": receipt()}
        code, first = self.call("/v1/enroll/open", packet)
        self.assertEqual(200, code)
        self.assertEqual(first, self.call("/v1/enroll/open", packet)[1])
        self.assertEqual(409, self.call("/v1/enroll/open", dict(packet, registration_secret=secrets.token_hex(32)))[0])
        self.assertEqual(400, self.call("/v1/enroll/open", dict(packet, consent={}))[0])
        with mock.patch.dict(os.environ, {"STUDY_OPEN_REGISTRATION": "0"}):
            self.assertEqual(503, self.call("/v1/enroll/open", packet)[0])

    def test_local_delete_failure_stops_every_track_and_keeps_retry_pending(self):
        self.consent.choose(True)
        self.consent.synchronize()
        with mock.patch.object(self.collections["python"], "delete", side_effect=CollectionError("locked")):
            self.consent.withdraw()
            self.assertTrue(all(not store.status()["enabled"] for store in self.collections.values()))
            self.assertTrue(self.consent.synchronize()["errors"])
            self.assertTrue(self.consent.settings()["withdraw_pending"])
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(self.consent.settings()["withdraw_pending"])

    def test_lost_registration_ack_can_be_withdrawn_without_creating_another_account(self):
        self.consent.choose(True)
        normal = self.transport
        failed = []
        def lost(base, path, *args, **kwargs):
            value = normal(base, path, *args, **kwargs)
            if path == "/v1/enroll/open" and not failed:
                failed.append(True)
                raise CollectionError("lost acknowledgement")
            return value
        with mock.patch.object(sharing, "request", lost):
            self.assertTrue(self.consent.synchronize()["errors"])
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants WHERE revoked=0").fetchone()[0])
        self.consent.choose(True)
        self.assertFalse(self.consent.synchronize()["errors"])

    def test_failed_enable_or_consent_save_does_not_leave_collection_running(self):
        with mock.patch.object(self.collections["ai"], "set_enabled", side_effect=CollectionError("locked")):
            with self.assertRaises(CollectionError):
                self.consent.choose(True)
        self.assertTrue(all(not store.status()["enabled"] for store in self.collections.values()))
        with mock.patch("aiprep.privacy.save", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.consent.choose(True)
        self.assertTrue(all(not store.status()["enabled"] for store in self.collections.values()))

    def test_declining_a_new_notice_pauses_without_unconfirmed_deletion(self):
        self.consent.choose(True)
        store = self.collections["ai"]
        store.emit("answer", {"result": "pass"})
        self.consent.synchronize()
        config = sharing.Sharing(store).settings()
        rows = store.status()["events"]
        self.consent.choose(False)
        self.assertFalse(self.consent.settings().get("withdraw_pending", False))
        self.assertTrue(all(not item.status()["enabled"] for item in self.collections.values()))
        self.assertEqual(rows, store.status()["events"])
        self.assertEqual(config, sharing.Sharing(store).settings())
        self.assertEqual(0, self.consent.synchronize()["sent"])
        with self.db.connect() as db:
            self.assertGreater(db.execute("SELECT count(*) FROM events").fetchone()[0], 0)
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])

    def test_reconsent_keeps_connection_and_skips_previously_held_records(self):
        self.consent.choose(True)
        self.consent.synchronize()
        store = self.collections["ai"]
        config = sharing.Sharing(store).settings()
        store.emit("answer", {"result": "fail"})
        held = store.latest_sequence()
        self.consent.choose(False)
        self.consent.choose(True)
        store.emit("answer", {"result": "pass"})
        self.assertFalse(self.consent.synchronize()["errors"])
        new = sharing.Sharing(store).settings()
        self.assertEqual(config["token"], new["token"])
        self.assertEqual(self.consent.settings()["receipt"], new["consent_receipt"])
        with self.db.connect() as db:
            rows = [json.loads(row[0]) for row in db.execute("SELECT payload FROM events WHERE track='ai'")]
        answers = [row for row in rows if row["kind"] == "answer"]
        self.assertEqual(["pass"], [row["data"]["result"] for row in answers])
        self.assertTrue(all(row["sequence"] > held for row in answers))

    def test_confirmed_server_revocation_stops_all_local_collection(self):
        self.consent.choose(True)
        self.consent.synchronize()
        store = self.collections["python"]
        config = sharing.Sharing(store).settings()
        self.db.remove(config["participant"])
        store.emit("answer", {"result": "pass"})
        self.assertTrue(self.consent.synchronize()["errors"])
        self.assertTrue(self.consent.settings()["withdraw_pending"])
        self.assertTrue(all(not item.status()["enabled"] for item in self.collections.values()))
        self.assertTrue(self.consent.synchronize()["withdrawn"])

    def test_empty_first_run_profile_does_not_remind_public_submission(self):
        self.consent.choose(False)
        folder = self.repo / "submissions/tester"
        folder.mkdir(parents=True)
        (folder / "profile.json").write_text('{"rounds": [], "attempts": []}')
        client = Client(str(self.repo), "tester", self.collections)
        self.assertFalse(client.pending()["pending"])

    def test_public_submission_can_connect_without_research_consent(self):
        self.consent.choose(False)
        client = Client(str(self.repo), "tester", self.collections)
        client.transport = self.transport
        client.connect_open("https://example.test")
        config = client.settings()
        self.assertNotIn(uuid.UUID(config["participant"]).hex[:10], config["display_id"])
        client.connect_open("https://example.test")
        with self.db.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM submission_accounts").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM submission_collections").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
        row = {"participant": config["participant"], "track": "python", "format": 1,
               "event_id": str(uuid.uuid4()), "sequence": 1, "at": stamp(), "kind": "answer", "data": {"result": "pass"}}
        packet = {"participant": config["participant"], "notice": NOTICE, "format": 1, "track": "python", "events": [row]}
        self.assertEqual(403, self.call("/v1/events", packet, config["token"])[0])
