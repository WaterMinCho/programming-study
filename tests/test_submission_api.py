# -*- coding: utf-8 -*-
"""초대·본인 경로·실패 후 재접수와 공개·비공개 전송을 확인함."""
import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest import mock

from aiprep.collection import Collection, CollectionError, NOTICE, digest
from aiprep import sharing
from learning_server import app
from tests.legacy_github import Publisher, PublishError
from tests.legacy_submissions import Submissions, clean_files
from submission_api import Client, Flow, snapshot


class SubmissionTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.folder = self.repo / "submissions/tester/r01"
        self.folder.mkdir(parents=True)
        (self.folder / "quiz.py").write_text("ANSWERS = {'q1': 4}\n", encoding="utf-8")
        self.db = app.Database(self.root / "server/data.sqlite3")
        self.wsgi = app.application(self.db, legacy_contract=True)
        self.stores = {name: Collection(str(self.root / name), str(self.repo), track=name) for name in ("ai", "python")}
        for store in self.stores.values():
            store.initialize_distribution()
            store.set_enabled(True)
            store.emit("answer", {"response": "secret input", "result": "pass"})
        self.client = Client(str(self.repo), "tester", self.stores)
        self.client.transport = self.transport
        self.publisher = mock.Mock()
        self.publisher.publish.return_value = "https://github.com/WaterMinCho/programming-study/pull/9999"
        rate = mock.patch("learning_server.submissions.MIN_INTERVAL", 0)
        rate.start()
        self.addCleanup(rate.stop)
        self.original_request = sharing.request
        local = mock.patch.object(sharing, "request", side_effect=self.transport)
        local.start()
        self.addCleanup(local.stop)
        patch = mock.patch("tests.legacy_submissions.Publisher.configured", return_value=self.publisher)
        patch.start()
        self.addCleanup(patch.stop)

    def transport(self, base, path, data=None, token=None, method="POST", **kwargs):
        code, result = self.call(path, data, token, method)
        if code != 200:
            raise CollectionError(result["error"])
        return result

    def call(self, path, data=None, token=None, method="POST"):
        raw = json.dumps(data).encode("utf-8")
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_TYPE": "application/json",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
        if token:
            env["HTTP_AUTHORIZATION"] = "Bearer " + token
        response = []
        result = b"".join(self.wsgi(env, lambda status, headers: response.append(status)))
        return int(response[0].split()[0]), json.loads(result)

    def connect(self):
        invite = self.db.invites()[0]
        self.client.connect("http://127.0.0.1:8765", invite)
        return self.client.settings()

    def packet(self, files, **extra):
        nonce = str(uuid.uuid4())
        return dict(files=files, request_id=nonce, digest=digest({"files": files, "request": nonce}), **extra)

    def test_one_invite_registers_private_tracks_with_independent_public_identifier(self):
        config = self.connect()
        self.assertNotEqual(config["public_id"], "api_" + uuid.UUID(config["participant"]).hex)
        for name, store in self.stores.items():
            setup = sharing.Sharing(store).settings()
            self.assertEqual(setup["participant"], store.status()["participant"])
            self.assertFalse(setup["include_answers"])
            self.assertEqual(store.status()["participant"], self.db.authenticate("Bearer " + setup["token"]))
        self.assertNotIn(config["token"], json.dumps(snapshot(self.repo, "tester")))

    def test_duplicate_display_id_rolls_back_invite_and_can_retry(self):
        self.connect()
        code = self.db.invites()[0]
        parent = str(uuid.uuid4())
        body = {"participant": parent, "invite": code, "notice": NOTICE, "display_id": "TESTER", "tracks": {}}
        self.assertEqual(self.call("/v1/register", body)[0], 409)
        with self.db.connect() as db:
            self.assertIsNone(db.execute("SELECT participant FROM invites WHERE code_hash=?", (app.hashed(code),)).fetchone()[0])
            self.assertIsNone(db.execute("SELECT 1 FROM participants WHERE participant=?", (parent,)).fetchone())
        body.update(participant=str(uuid.uuid4()), display_id="another-student")
        self.assertEqual(self.call("/v1/register", body)[0], 200)

    def test_public_submission_limit_does_not_block_private_records(self):
        config = self.connect()
        self.client.submit()
        self.stores["ai"].emit("answer", {"response": "new", "result": "pass"})
        (self.folder / "quiz.py").write_text("ANSWERS = {'q1': 8}\n")
        with mock.patch("learning_server.submissions.MAX_DAILY", 1):
            with self.assertRaisesRegex(CollectionError, "24시간"):
                self.client.submit()
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM api_submissions").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE track='ai' AND payload LIKE '%pass%'").fetchone()[0], 2)

    def test_short_interval_rejects_new_receipt_but_allows_same_receipt_retry(self):
        config = self.connect()
        first = self.packet(snapshot(self.repo, "tester"))
        self.assertEqual(self.call("/v1/submissions", first, config["token"])[0], 200)
        with self.db.connect() as db:
            moment = datetime.datetime.fromisoformat(db.execute("SELECT received FROM api_submissions").fetchone()[0])
        class Clock(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return moment + datetime.timedelta(seconds=1)
        with mock.patch("learning_server.submissions.MIN_INTERVAL", 5), mock.patch("learning_server.submissions.datetime.datetime", Clock):
            self.assertEqual(self.call("/v1/submissions", first, config["token"])[0], 200)
            second = self.packet({"r01/quiz.py": "ANSWERS = {}\n"}, previous=first["digest"])
            self.assertEqual(self.call("/v1/submissions", second, config["token"])[0], 429)

    def test_revocation_between_remote_writes_stops_publisher(self):
        config = self.connect()
        def revoke(*args, **kwargs):
            with self.db.connect() as db:
                db.execute("UPDATE participants SET revoked=1 WHERE participant=?", (config["participant"],))
            kwargs["before_write"]()
            self.fail("철회 뒤 게시가 계속됨")
        self.publisher.publish.side_effect = revoke
        with self.assertRaisesRegex(CollectionError, "게시"):
            self.client.submit()

    def test_submit_preserves_originals_and_retries_reuse_receipt_and_pr(self):
        self.connect()
        original = (self.folder / "quiz.py").read_bytes()
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            first = self.client.submit()
            self.assertFalse(self.client.pending()["pending"])
            again = self.client.submit()
        self.assertEqual(first["pr_url"], again["pr_url"])
        self.assertEqual(self.publisher.publish.call_count, 1)
        self.assertEqual((self.folder / "quiz.py").read_bytes(), original)
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM api_submissions").fetchone()[0], 1)
            values = [r[0] for r in db.execute("SELECT payload FROM events")]
            self.assertTrue(values)
            self.assertNotIn("secret input", " ".join(values))

    def test_lost_store_ack_keeps_pending_snapshot_and_new_answer_is_not_lost(self):
        self.connect()
        normal = self.client.transport
        failed = []
        def lose(base, path, *args, **kwargs):
            result = normal(base, path, *args, **kwargs)
            if path == "/v1/submissions" and not failed:
                failed.append(True)
                raise CollectionError("lost acknowledgement")
            return result
        self.client.transport = lose
        with self.assertRaises(CollectionError):
            self.client.submit()
        self.assertTrue(self.client.pending_path.exists())
        (self.folder / "quiz.py").write_text("ANSWERS = {'q1': 5}\n")
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            self.assertEqual(self.client.submit()["status"], "ok")
        self.assertFalse(self.client.pending_path.exists())
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM api_submissions").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT count(*) FROM api_submissions WHERE payload IS NOT NULL").fetchone()[0], 1)

    def test_github_failure_is_distinct_from_stored_and_retry_does_not_duplicate(self):
        self.connect()
        self.publisher.publish.side_effect = PublishError("temporarily unavailable")
        with self.assertRaisesRegex(CollectionError, "서버에 풀이를 저장"):
            self.client.submit()
        self.assertTrue(self.client.pending()["pending"])
        self.publisher.publish.side_effect = None
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            self.assertEqual(self.client.submit()["status"], "ok")
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM api_submissions").fetchone()[0], 1)

    def test_reverting_to_earlier_answers_is_a_new_submission(self):
        self.connect()
        first = (self.folder / "quiz.py").read_text()
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            for content in (first, "ANSWERS = {'q1': 5}\n", first):
                (self.folder / "quiz.py").write_text(content)
                self.assertEqual(self.client.submit()["status"], "ok")
        self.assertEqual(self.publisher.publish.call_count, 3)
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM api_submissions").fetchone()[0], 3)

    def test_backup_restores_submission_receipts_and_authentication(self):
        from learning_server import operations
        config = self.connect()
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            self.client.submit()
        operations.backup(self.db.path, self.root / "backup")
        operations.restore(self.root / "backup", self.root / "restored")
        restored = app.Database(self.root / "restored/learning.sqlite3")
        self.assertEqual(restored.authenticate("Bearer " + config["token"]), config["participant"])
        self.assertEqual(Submissions(restored).publish(config["participant"], {"digest": self.client.settings()["last_hash"]})["state"], "published")

    def test_bulk_invites_are_private_files_without_registration(self):
        from learning_server.operations import class_invites
        destination = self.root / "class-invites"
        result = class_invites(self.db, destination, "https://example.test", count=100)
        self.assertEqual(result["members"], 100)
        self.assertEqual(len(list(destination.glob("member-*.txt"))), 100)
        text = (destination / "member-001.txt").read_text(encoding="utf-8")
        self.assertIn("일반 수강생은 이 초대 파일을 사용하지 않습니다", text)
        self.assertIn("비공개로 보냅니다", text)
        self.assertNotIn("GitHub 공개 PR로 올립니다", text)
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM submission_accounts").fetchone()[0], 0)

    def test_stopped_collection_is_not_restarted_by_connect_or_submit(self):
        self.stores["ai"].set_enabled(False)
        self.connect()
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            self.client.submit()
        self.assertFalse(self.stores["ai"].status()["enabled"])
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE track='ai'").fetchone()[0], 0)

    def test_deleting_additional_data_does_not_block_public_submission(self):
        self.connect()
        self.stores["ai"].delete()
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            self.assertEqual(self.client.submit()["status"], "ok")
        self.assertFalse(self.stores["ai"].status()["enabled"])

    def test_other_participant_and_stale_snapshot_do_not_overwrite(self):
        config = self.connect()
        files = snapshot(self.repo, "tester")
        packet = self.packet(files)
        self.assertEqual(self.call("/v1/submissions", packet)[0], 401)
        self.assertEqual(self.call("/v1/submissions", packet, config["token"])[0], 200)
        newer = {"r01/quiz.py": "ANSWERS = {}\n"}
        self.assertEqual(self.call("/v1/submissions", self.packet(newer), config["token"])[0], 409)
        other = self.db.enroll({"participant": str(uuid.uuid4()), "invite": self.db.invites()[0], "notice": NOTICE})
        self.assertEqual(self.call("/v1/submissions/publish", {"digest": packet["digest"]}, other["token"])[0], 404)

    def test_paths_case_collisions_secrets_and_byte_limits_are_rejected(self):
        for path in ("../main.py", "/profile.json", "r01/../profile.json", "r01/.env", "r01/.git/config", "r01/a\\b.py", "r01/a.py.", "r01/a:bad.py", "r01/submission-api.json", "r01/CON.py", "main.py"):
            with self.subTest(path=path), self.assertRaises(app.ApiError):
                clean_files({path: "x"})
        with self.assertRaises(app.ApiError):
            clean_files({"r01/a.py": "x", "r01/A.py": "y"})
        with self.assertRaises(app.ApiError):
            clean_files({"r01/a.py": "x" * (4 * 1024 * 1024 + 1)})
        (self.folder / ".env").write_text("PRIVATE_KEY=hidden")
        self.assertNotIn("r01/.env", snapshot(self.repo, "tester"))

    def test_legacy_folders_and_utf8_bom_remain_in_snapshot(self):
        folder = self.repo / "submissions/tester/s01"
        folder.mkdir()
        (folder / "meta.json").write_bytes(b"\xef\xbb\xbf{}")
        files = snapshot(self.repo, "tester")
        self.assertEqual(files["s01/meta.json"].encode("utf-8"), b"\xef\xbb\xbf{}")
        clean_files(files)

    def test_default_flow_connects_private_and_does_not_use_direct_git(self):
        from aiprep.privacy import Consent
        Consent(self.stores).choose(True)
        git = mock.Mock(root=str(self.repo), user="tester")
        flow = Flow(git)
        flow.set_collections(self.stores)
        flow.api.transport = self.transport
        flow.api.save({"mode": "git"})
        with mock.patch.dict("os.environ", {"STUDY_OPEN_REGISTRATION": "1"}):
            result = flow.submit()
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["pr_url"])
        self.assertEqual(flow.submit()["status"], "nothing")
        git.submit.assert_not_called()
        self.publisher.publish.assert_not_called()
        with self.db.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM api_submissions").fetchone()[0])

    def test_real_http_client_registers_stores_and_publishes(self):
        import threading
        from wsgiref.simple_server import make_server, WSGIRequestHandler
        class Quiet(WSGIRequestHandler):
            def log_message(self, *args):
                pass
        server = make_server("127.0.0.1", 0, self.wsgi, handler_class=Quiet)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = Client(str(self.repo), "tester", self.stores)
        try:
            base = "http://127.0.0.1:%d" % server.server_port
            with self.assertRaisesRegex(CollectionError, "초대 코드"):
                client.connect(base, "x" * 24)
            client.connect(base, self.db.invites()[0])
            with mock.patch.object(sharing, "request", self.original_request):
                result = client.submit()
            self.assertEqual(result["status"], "ok")
            self.assertFalse(client.pending()["pending"])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_active_publish_does_not_hold_write_lock_and_blocks_new_snapshot_and_delete(self):
        config = self.connect()
        def publish(*args, **kwargs):
            kwargs["before_write"]()
            self.assertEqual(len(self.db.invites()), 1)
            files = {"r01/quiz.py": "ANSWERS = {}\n"}
            current = self.client.settings()["last_hash"]
            self.assertEqual(self.call("/v1/submissions", self.packet(files, previous=current), config["token"])[0], 409)
            self.assertEqual(self.call("/v1/me", token=config["token"], method="DELETE")[0], 409)
            return "https://github.com/WaterMinCho/programming-study/pull/9999"
        self.publisher.publish.side_effect = publish
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            self.assertEqual(self.client.submit()["status"], "ok")

    def test_revocation_deletes_api_payload_and_linked_private_data(self):
        config = self.connect()
        with mock.patch.object(sharing, "request", side_effect=self.transport):
            self.client.submit()
        self.assertEqual(self.call("/v1/me", token=config["token"], method="DELETE")[0], 200)
        self.assertEqual(self.call("/v1/me", token=config["token"], method="DELETE")[0], 200)
        with self.db.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM api_submissions").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], 0)
        self.assertTrue((self.folder / "quiz.py").exists())

    def test_symlink_file_is_rejected_without_reading_target(self):
        target = self.root / "private.py"
        target.write_text("private credential")
        try:
            (self.folder / "p01.py").symlink_to(target)
        except OSError:
            self.skipTest("심볼릭 링크 권한이 없는 환경")
        with self.assertRaises(CollectionError):
            snapshot(self.repo, "tester")


class PublisherTest(unittest.TestCase):
    def test_current_main_and_only_server_owned_subtree_are_used(self):
        publisher = Publisher("WaterMinCho/programming-study", "server-only-token")
        calls = []
        def transport(method, path, data=None, missing=False):
            calls.append((method, path, data))
            if path.startswith("/git/ref/heads/study/"):
                return None
            if path == "/git/ref/heads/main":
                return {"object": {"sha": "main-sha"}}
            if path == "/git/commits/main-sha":
                return {"tree": {"sha": "main-tree"}}
            if path == "/git/trees":
                return {"sha": "combined-tree" if "base_tree" in data else "own-tree"}
            if path == "/git/commits":
                return {"sha": "new-commit"}
            if path == "/git/refs":
                return {}
            if path.startswith("/pulls?"):
                return []
            if path == "/pulls":
                return {"html_url": "https://github.com/WaterMinCho/programming-study/pull/9999"}
            self.fail(path)
        publisher.request = transport
        public = "api_" + "1" * 32
        guard = mock.Mock()
        publisher.publish(public, "tester", "2" * 64, {"r01/quiz.py": "raise SystemExit(7)"}, before_write=guard)
        trees = [c[2] for c in calls if c[1] == "/git/trees"]
        self.assertEqual(trees[1], {"base_tree": "main-tree", "tree": [
            {"path": "submissions/" + public, "mode": "040000", "type": "tree", "sha": "own-tree"}]})
        commit = next(c[2] for c in calls if c[1] == "/git/commits")
        self.assertEqual(commit["parents"], ["main-sha"])
        self.assertNotIn("server-only-token", json.dumps(calls))
        self.assertEqual(guard.call_count, 5)

    def test_same_submission_marker_reuses_branch_commit_and_existing_pr(self):
        publisher = Publisher("WaterMinCho/programming-study", "token")
        calls = []
        def request(method, path, data=None, missing=False):
            calls.append((method, path))
            if path.startswith("/git/ref/"):
                return {"object": {"sha": "existing"}}
            if path == "/git/commits/existing":
                return {"message": "풀이 제출\n\nsubmission:" + "2" * 64}
            return [{"html_url": "https://github.com/WaterMinCho/programming-study/pull/9999"}]
        publisher.request = request
        publisher.publish("api_" + "1" * 32, "tester", "2" * 64, {"r01/quiz.py": "x"})
        self.assertTrue(all(method == "GET" for method, _ in calls))
