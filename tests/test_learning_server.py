# -*- coding: utf-8 -*-
"""가명 참가자 인증·원자 수집·재전송·철회와 앱 연결을 확인함."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest import mock

from aiprep import collection, sharing
from learning_server import app


class ServerTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="learning_server_")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = app.Database(str(self.root / "server/data.sqlite3"))
        self.application = app.application(self.db)
        self.participant = str(uuid.uuid4())
        self.invite = self.db.invites()[0]
        self.token = self.db.enroll({"participant": self.participant, "invite": self.invite, "notice": collection.NOTICE})["token"]

    def call(self, path, data=None, token=None, method="POST", raw=None):
        body = raw if raw is not None else json.dumps(data).encode("utf-8")
        environ = {"PATH_INFO": path, "REQUEST_METHOD": method, "CONTENT_LENGTH": str(len(body)),
                   "CONTENT_TYPE": "application/json", "wsgi.input": io.BytesIO(body)}
        if token:
            environ["HTTP_AUTHORIZATION"] = "Bearer " + token
        result = []
        body = b"".join(self.application(environ, lambda status, headers: result.append(status)))
        return int(result[0].split()[0]), json.loads(body)

    def row(self, sequence=1, track="ai"):
        return {"format": 1, "track": track, "participant": self.participant, "sequence": sequence,
                "event_id": str(uuid.uuid4()), "at": collection.stamp(), "kind": "answer",
                "data": {"result": "pass"}, "item_revision": None, "item": None}

    def packet(self, rows, track="ai"):
        return {"format": 1, "track": track, "participant": self.participant, "notice": collection.NOTICE, "events": rows}

    def count(self):
        with self.db.connect() as db:
            return db.execute("SELECT count(*) FROM events").fetchone()[0]

    def test_authentication_invite_binding_and_both_tracks(self):
        self.assertEqual(401, self.call("/v1/events", self.packet([self.row()]))[0])
        with self.assertRaises(app.ApiError):
            self.db.enroll({"participant": str(uuid.uuid4()), "invite": self.invite, "notice": collection.NOTICE})
        self.assertEqual(self.token, self.db.enroll({"participant": self.participant, "invite": self.invite, "notice": collection.NOTICE})["token"])
        for track in ("ai", "python"):
            self.assertEqual(200, self.call("/v1/events", self.packet([self.row(track=track)], track), self.token)[0])
        self.assertEqual(2, self.count())

    def test_duplicate_is_idempotent_and_conflict_rolls_back_whole_batch(self):
        row = self.row()
        for _ in range(2):
            self.assertEqual(200, self.call("/v1/events", self.packet([row]), self.token)[0])
        self.assertEqual(1, self.count())
        first, conflict = self.row(2), self.row(3)
        conflict["event_id"] = row["event_id"]
        self.assertEqual(409, self.call("/v1/events", self.packet([first, conflict]), self.token)[0])
        self.assertEqual(1, self.count())
        collision = self.row(1)
        self.assertEqual(409, self.call("/v1/events", self.packet([collision]), self.token)[0])
        self.assertEqual(1, self.count())

    def test_participant_mismatch_and_input_boundaries(self):
        row = self.row()
        row["participant"] = str(uuid.uuid4())
        self.assertEqual(400, self.call("/v1/events", self.packet([row]), self.token)[0])
        self.assertEqual(400, self.call("/v1/events", token=self.token, raw=b"[")[0])
        for key, value in (("at", "not-a-date"), ("at", "2026-01-01T10:00:00"), ("sequence", 10 ** 40)):
            invalid = self.row()
            invalid[key] = value
            self.assertEqual(400, self.call("/v1/events", self.packet([invalid]), self.token)[0])
        self.assertEqual(413, self.call("/v1/events", token=self.token, raw=b"x" * (app.MAX_BODY + 1))[0])
        self.assertEqual(0, self.count())

    def test_delete_is_repeatable_and_revokes_upload(self):
        self.call("/v1/events", self.packet([self.row()]), self.token)
        for _ in range(2):
            self.assertEqual(200, self.call("/v1/me", token=self.token, method="DELETE")[0])
        self.assertEqual(0, self.count())
        self.assertEqual(401, self.call("/v1/events", self.packet([self.row()]), self.token)[0])

    def test_client_preserves_data_after_lost_ack_and_retries_without_duplicates(self):
        store = collection.Collection(str(self.root / "client"), str(self.root / "repo"))
        store.set_enabled(True)
        store.emit("answer", {"response": ["입력 원문"], "result": "pass"})
        client = sharing.Sharing(store)
        invite = self.db.invites()[0]
        lost = [True]

        def transport(base, path, data=None, token=None, method="POST"):
            status, result = self.call(path, data, token, method)
            if status != 200:
                raise collection.CollectionError(str(status))
            if path == "/v1/events" and lost[0]:
                lost[0] = False
                raise collection.CollectionError("저장 확인 응답을 놓쳤습니다.")
            return result

        with mock.patch.object(sharing, "request", side_effect=transport):
            with self.assertRaises(collection.CollectionError):
                client.sync("https://collector.example", invite)
            self.assertEqual(0, client.settings()["sequence"])
            self.assertEqual(2, self.count())
            self.assertEqual(2, client.sync("https://collector.example")["sent"])
            self.assertEqual(2, self.count())
            self.assertEqual(0, client.sync("https://collector.example")["sent"])
            with self.db.connect() as db:
                self.assertNotIn("입력 원문", "".join(row[0] for row in db.execute("SELECT payload FROM events")))
            local = Path(store.path).read_bytes()
            self.assertTrue(client.delete_remote()["deleted"])
            self.assertEqual(local, Path(store.path).read_bytes())
            self.assertEqual(0, self.count())

    def test_no_network_without_local_consent_and_no_http_remote(self):
        store = collection.Collection(str(self.root / "client"), str(self.root / "repo"))
        with mock.patch.object(sharing, "request") as network:
            with self.assertRaises(collection.CollectionError):
                sharing.Sharing(store).sync("https://collector.example")
            network.assert_not_called()
        for value in ("http://collector.example", "https://user:pass@example.com", "https://example.com?token=secret"):
            with self.assertRaises(collection.CollectionError):
                sharing.endpoint(value)
        self.assertEqual("http://127.0.0.1:8765", sharing.endpoint("http://127.0.0.1:8765/"))

    def test_export_is_read_back_and_excludes_raw_input_by_default(self):
        row = self.row()
        row["data"]["response"] = ["답안 원문"]
        self.call("/v1/events", self.packet([row]), self.token)
        path = self.root / "dataset.jsonl"
        self.assertEqual(1, self.db.export(str(path))["events"])
        self.assertNotIn("response", path.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            self.db.export(str(path))

    def test_settings_permission_failure_is_reported_as_collection_error(self):
        store = collection.Collection(str(self.root / "client"), str(self.root / "repo"))
        store.set_enabled(True)
        with mock.patch.object(sharing.tempfile, "mkstemp", side_effect=PermissionError("denied")):
            with self.assertRaises(collection.CollectionError):
                sharing.Sharing(store)._save({})

    def test_loopback_http_uses_real_client_protocol(self):
        import threading
        from wsgiref.simple_server import make_server, WSGIRequestHandler
        class Quiet(WSGIRequestHandler):
            def log_message(self, format, *args):
                pass
        server = make_server("127.0.0.1", 0, self.application, handler_class=Quiet)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = "http://127.0.0.1:%d" % server.server_port
            invite = self.db.invites()[0]
            participant = str(uuid.uuid4())
            enrolled = sharing.request(url, "/v1/enroll", {"invite": invite, "participant": participant, "notice": collection.NOTICE})
            self.assertTrue(sharing.request(url, "/v1/me", token=enrolled["token"], method="DELETE")["deleted"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
