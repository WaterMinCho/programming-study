# -*- coding: utf-8 -*-
"""동의·거부·재전송·철회와 공개 제출의 분리를 확인함."""
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest import mock
import uuid

from aiprep.collection import Collection, CollectionError, NOTICE, stamp
from aiprep.privacy import Consent, receipt
from aiprep import sharing
from learning_server.app import Database, application
from submission_api import Client


class PrivacyTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.collections = {name: Collection(str(self.root / name), str(self.repo), track=name) for name in ("python", "ai")}
        self.consent = Consent(self.collections, "https://example.test")
        self.db = Database(self.root / "server/learning.sqlite3")
        self.app = application(self.db)
        for patcher in (mock.patch.dict(os.environ, {"STUDY_OPEN_REGISTRATION": "1"}),
                        mock.patch.object(sharing, "request", self.transport)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def call(self, path, data=None, token=None, method="POST"):
        raw = json.dumps(data).encode()
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

    def test_declining_a_new_notice_with_an_existing_connection_requests_withdrawal(self):
        self.consent.choose(True)
        self.consent.synchronize()
        self.consent.choose(False)
        self.assertTrue(self.consent.settings()["withdraw_pending"])
        self.assertTrue(self.consent.synchronize()["withdrawn"])

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
