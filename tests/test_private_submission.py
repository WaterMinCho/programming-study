# -*- coding: utf-8 -*-
"""비공개 파일 제출·공개 경로 폐쇄·응답 유실·철회를 확인함."""
import json
from pathlib import Path
from unittest import mock
import unittest

from aiprep.collection import CollectionError
from aiprep import sharing
from learning_server.app import application
from submission_api import PrivateClient, Flow
from tests import test_learning_privacy as privacy_fixture


class PrivateSubmissionTest(unittest.TestCase):
    setUp = privacy_fixture.PrivacyTest.setUp
    call = privacy_fixture.PrivacyTest.call
    transport = privacy_fixture.PrivacyTest.transport

    def test_closed_git_resolution_never_calls_legacy_submission_or_remote_copy(self):
            from gitflow import GitFlow
            flow = GitFlow(str(self.repo), "tester")
            with mock.patch.object(flow, "_run", side_effect=AssertionError("legacy path called")):
                for choice in ("local", "remote"):
                    result = flow.resolve(choice)
                    self.assertEqual("error", result["status"])
                    self.assertIn("공개 Git 제출을 종료", result["message"])

    def client(self):
        self.app = application(self.db)
        self.consent.choose(True)
        folder = self.repo / "submissions/tester/r01"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "quiz.py").write_text("ANSWERS = {'q1': 3}\n")
        client = PrivateClient(str(self.repo), "tester", self.collections)
        client.transport = self.transport
        return client

    def test_automatic_scope_preserves_old_consent_period_and_needs_its_own_choice(self):
        from learning_data.privacy import validate_receipt
        client = self.client()
        old = self.consent.settings()
        self.assertTrue(self.consent.needs_auto_choice())
        self.assertFalse(self.consent.needs_choice())
        with self.assertRaises(ValueError):
            validate_receipt(old["receipt"], automatic=True)
        active = self.consent.set_auto_submission(True)
        self.assertEqual(old["at"], active["at"])
        self.assertEqual(old["start"], active["start"])
        self.assertFalse(self.consent.needs_auto_choice())
        self.assertTrue(validate_receipt(active["receipt"], automatic=True)["automatic_submission"]["accepted"])
        self.assertEqual("ok", client.submit_ready(automatic=True)["status"])
        self.assertEqual("nothing", client.submit_ready(automatic=True)["status"])
        disabled = self.consent.set_auto_submission(False)
        self.assertTrue(disabled["accepted"])
        self.assertEqual(old["start"], disabled["start"])
        self.assertEqual("paused", client.submit_ready(automatic=True)["status"])
        with self.db.connect() as db:
            saved = db.execute("SELECT receipt FROM open_enrollments WHERE purpose='private_submission'").fetchone()[0]
            self.assertFalse(json.loads(saved)["automatic_submission"]["accepted"])

    def test_reenabling_automatic_submission_without_new_files_only_syncs_consent(self):
        client = self.client()
        self.consent.set_auto_submission(True)
        self.assertEqual("ok", client.submit_ready(automatic=True)["status"])
        self.consent.set_auto_submission(False)
        self.assertEqual("paused", client.submit_ready(automatic=True)["status"])
        self.consent.set_auto_submission(True)
        with mock.patch.object(client, "transport", wraps=client.transport) as transport:
            self.assertEqual("nothing", client.submit_ready(automatic=True)["status"])
            self.assertEqual("nothing", client.submit_ready(automatic=True)["status"])
            self.assertEqual(["/v1/consent"], [call.args[1] for call in transport.call_args_list])
        with self.db.connect() as db:
            receipt, = db.execute("SELECT receipt FROM open_enrollments WHERE purpose='private_submission'").fetchone()
            self.assertTrue(json.loads(receipt)["automatic_submission"]["accepted"])

    def test_server_rejects_automatic_files_without_scope_and_keeps_manual_submission(self):
        import uuid
        from learning_data.collection import digest
        from learning_data.submission import snapshot
        client = self.client()
        client.connect_open("https://example.test")
        with self.assertRaises(CollectionError):
            files = snapshot(client.root, client.user)
            request_id = str(uuid.uuid4())
            client.transport("https://example.test", "/v1/private/submissions",
                             {"files": files, "request_id": request_id, "digest": digest({"files": files, "request": request_id}), "automatic": True},
                             token=client.settings()["token"])
        self.assertEqual("ok", client.submit()["status"])
        self.consent.set_auto_submission(True)
        client.sync_consent(self.consent, self.consent.settings())
        self.assertEqual("nothing", client.submit_ready(automatic=True)["status"])
        self.consent.set_auto_submission(False)
        client.sync_consent(self.consent, self.consent.settings())
        with self.assertRaises(ValueError):
            from learning_data.privacy import validate_receipt
            validate_receipt(self.consent.settings()["receipt"], automatic=True)

    def test_automatic_transfer_respects_paused_tracks_and_changed_choice(self):
        client = self.client()
        self.consent.set_auto_submission(True)
        self.collections["ai"].set_enabled(False)
        with mock.patch.object(client, "transport") as transport:
            self.assertEqual("paused", client.submit_ready(automatic=True)["status"])
            transport.assert_not_called()
        self.assertTrue((self.repo/"submissions/tester/r01/quiz.py").exists())

    def test_permission_disabled_after_sync_prevents_the_next_file_request(self):
        client = self.client()
        self.consent.set_auto_submission(True)
        sync = client.sync_consent
        def disable_after_sync(*args, **kwargs):
            sync(*args, **kwargs)
            self.consent.set_auto_submission(False)
        with mock.patch.object(client, "sync_consent", side_effect=disable_after_sync):
            with self.assertRaises(ValueError):
                client.submit_ready(automatic=True)
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM api_submissions").fetchone()[0])
        self.assertFalse(client.pending_path.exists())

    def test_server_does_not_restore_a_delayed_on_receipt_after_off(self):
        client = self.client()
        self.consent.set_auto_submission(True)
        client.submit_ready(automatic=True)
        old_receipt = self.consent.settings()["receipt"]
        config = client.settings()
        self.consent.set_auto_submission(False)
        client.sync_consent(self.consent, self.consent.settings())
        status, _ = self.call("/v1/consent", {"consent": old_receipt}, token=config["token"])
        self.assertEqual(409, status)
        status, _ = self.call("/v1/private/submissions", {"automatic": True}, token=config["token"])
        self.assertEqual(403, status)
        status, _ = self.call("/v1/private/submissions", {"automatic": "true"}, token=config["token"])
        self.assertEqual(400, status)
        plain = {k:v for k,v in old_receipt.items() if k != "automatic_submission"}
        self.assertEqual(200, self.call("/v1/consent", {"consent": plain}, token=config["token"])[0])
        with self.db.connect() as db:
            scope = json.loads(db.execute("SELECT receipt FROM open_enrollments WHERE participant=?", (config["participant"],)).fetchone()[0])["automatic_submission"]
            self.assertFalse(scope["accepted"])

    def test_cancellation_after_registration_stops_before_any_file_request(self):
        import threading
        from learning_data.submission import submit_private
        client = self.client()
        self.consent.set_auto_submission(True)
        cancel = threading.Event()
        wire = client.transport
        routes = []
        def register_then_stop(base, path, *args, **kwargs):
            routes.append(path)
            result = wire(base, path, *args, **kwargs)
            if path == "/v1/register/private":
                cancel.set()
            return result
        client.transport = register_then_stop
        result = submit_private(client, automatic=True, canceled=cancel.is_set)
        self.assertEqual("paused", result["status"])
        self.assertNotIn("/v1/private/submissions", routes)
        self.assertTrue((self.repo/"submissions/tester/r01/quiz.py").exists())

    def test_production_public_routes_are_closed_before_any_publisher(self):
        self.app = application(self.db)
        with mock.patch("tests.legacy_submissions.Publisher.configured") as publisher:
            for path in ("/v1/register", "/v1/register/open", "/v1/submissions", "/v1/submissions/publish"):
                self.assertEqual(410, self.call(path, {})[0])
            publisher.assert_not_called()

    def test_private_submission_stores_and_retries_without_git(self):
        client = self.client()
        with mock.patch("tests.legacy_submissions.Publisher.configured") as publisher:
            client.connect_open("https://example.test")
            first = client.submit()
            second = client.submit()
            publisher.assert_not_called()
        self.assertIsNone(first["pr_url"])
        self.assertEqual(first["receipt"], second["receipt"])
        self.assertFalse(client.pending()["pending"])
        with self.db.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM api_submissions").fetchone()[0])
            self.assertIsNone(db.execute("SELECT pr_url FROM api_submissions").fetchone()[0])

    def test_exact_file_byte_limit_is_accepted(self):
        from learning_data.submission import MAX_BYTES
        client = self.client()
        client.connect_open("https://example.test")
        path = self.repo / "submissions/tester/r01/quiz.py"
        path.write_bytes(("가" * (MAX_BYTES // 3)).encode("utf-8") + b"x" * (MAX_BYTES % 3))
        self.assertEqual("ok", client.submit()["status"])
        self.assertEqual(MAX_BYTES, path.stat().st_size)

    def test_raw_file_over_limit_stays_local(self):
        from learning_data.submission import MAX_BYTES
        client = self.client()
        client.connect_open("https://example.test")
        path = self.repo / "submissions/tester/r01/quiz.py"
        path.write_bytes(b"x" * (MAX_BYTES + 1))
        with mock.patch.object(client, "transport") as transport:
            with self.assertRaises(CollectionError):
                client.submit()
            transport.assert_not_called()
        self.assertFalse(client.pending_path.exists())
        self.assertEqual(MAX_BYTES + 1, path.stat().st_size)

    def test_escaped_request_over_limit_is_not_sent_or_left_pending(self):
        from learning_data.submission import MAX_BYTES
        client = self.client()
        client.connect_open("https://example.test")
        path = self.repo / "submissions/tester/r01/quiz.py"
        path.write_bytes(b"\n" * MAX_BYTES)
        with mock.patch.object(client, "transport") as transport:
            with self.assertRaisesRegex(CollectionError, "6MiB"):
                client.submit()
            transport.assert_not_called()
        self.assertFalse(client.pending_path.exists())
        self.assertEqual(MAX_BYTES, path.stat().st_size)
        path.write_text("ANSWERS = {'q1': 4}\n")
        self.assertEqual("ok", client.submit()["status"])

    def test_old_oversized_pending_request_does_not_block_corrected_answer(self):
        import uuid
        from learning_data.collection import digest
        from learning_data.submission import MAX_BYTES
        client = self.client()
        client.connect_open("https://example.test")
        files = {"r01/quiz.py": "\n" * MAX_BYTES}
        identifier = str(uuid.uuid4())
        client.save({"participant": client.settings()["participant"], "request_id": identifier,
                     "files": files, "digest": digest({"files": files, "request": identifier})}, client.pending_path)
        transport = client.transport
        with mock.patch.object(client, "transport", wraps=transport) as send:
            with self.assertRaises(CollectionError) as caught:
                client.submit()
            self.assertEqual(413, caught.exception.status)
            self.assertIn("다시 눌러", str(caught.exception))
            self.assertEqual(identifier, send.call_args.args[2]["request_id"])
            send.assert_called_once()
        self.assertFalse(client.pending_path.exists())
        self.assertEqual("ok", client.submit()["status"])
        self.assertIn("3", (self.repo / "submissions/tester/r01/quiz.py").read_text())

    def test_invalid_saved_consent_time_does_not_escape_as_a_value_error(self):
        client = self.client()
        from learning_data.privacy import save
        state = self.consent.settings()
        state["receipt"]["at"] = "2026-11-13T13:00:00"
        save(self.consent.path, state)
        with self.assertRaisesRegex(CollectionError, "시간대"):
            client.connect_open("https://example.test")

    def test_decline_cannot_send_files_and_local_answers_remain(self):
        client = self.client()
        self.consent.choose(False)
        with self.assertRaises(CollectionError):
            client.connect_open("https://example.test")
        self.assertTrue((self.repo / "submissions/tester/r01/quiz.py").exists())

    def test_lost_ack_reuses_receipt_and_later_answer_is_preserved(self):
        client = self.client()
        client.connect_open("https://example.test")
        transport = client.transport
        failed = []
        def lose(base, path, *args, **kwargs):
            result = transport(base, path, *args, **kwargs)
            if path == "/v1/private/submissions" and not failed:
                failed.append(True)
                raise CollectionError("응답 유실")
            return result
        client.transport = lose
        with self.assertRaises(CollectionError):
            client.submit()
        self.assertTrue(client.pending_path.exists())
        path = self.repo / "submissions/tester/r01/quiz.py"
        path.write_text("ANSWERS = {'q1': 4}\n")
        with mock.patch("learning_server.submissions.MIN_INTERVAL", 0):
            self.assertEqual("ok", client.submit()["status"])
        self.assertFalse(client.pending_path.exists())
        self.assertIn("4", path.read_text())
        with self.db.connect() as db:
            self.assertEqual(2, db.execute("SELECT count(*) FROM api_submissions").fetchone()[0])

    def test_withdraw_removes_private_files_and_does_not_delete_local_answers(self):
        client = self.client()
        client.connect_open("https://example.test")
        client.submit()
        self.consent.withdraw()
        with mock.patch.object(sharing, "request", side_effect=CollectionError("offline")):
            self.assertTrue(self.consent.synchronize()["errors"])
        self.assertTrue(self.consent.settings()["withdraw_pending"])
        self.assertTrue(client.path.exists())
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(client.path.exists())
        self.assertTrue((self.repo / "submissions/tester/r01/quiz.py").exists())
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM api_submissions").fetchone()[0])

    def test_lost_enrollment_ack_can_be_withdrawn_with_saved_seed(self):
        client = self.client()
        transport = client.transport
        def lose(*args, **kwargs):
            transport(*args, **kwargs)
            raise CollectionError("연결 응답 유실")
        client.transport = lose
        with self.assertRaises(CollectionError):
            client.connect_open("https://example.test")
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants WHERE revoked=0").fetchone()[0])

    def test_legacy_git_setting_cannot_publish_through_default_flow(self):
        client = self.client()
        git = mock.Mock(root=str(self.repo), user="tester")
        flow = Flow(git)
        flow.set_collections(self.collections)
        flow.api.save({"mode": "git"})
        self.assertEqual("ok", flow.submit()["status"])
        self.assertIsNone(flow.api.submit()["pr_url"])
        git.submit.assert_not_called()
        with self.db.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM api_submissions").fetchone()[0])

    def test_ready_submission_connects_once_and_reuses_current_consent(self):
        client = self.client()
        before = self.consent.settings()
        transport = mock.Mock(wraps=self.transport)
        client.transport = transport
        self.assertEqual("ok", client.submit_ready()["status"])
        self.assertEqual("nothing", client.submit_ready()["status"])
        self.assertEqual(["/v1/register/private", "/v1/private/submissions"], [call.args[1] for call in transport.call_args_list])
        self.assertEqual(before, self.consent.settings())
        self.assertFalse(client.pending()["pending"])

    def test_ready_submission_does_not_register_without_files_or_current_consent(self):
        client = self.client()
        file = self.repo / "submissions/tester/r01/quiz.py"
        file.unlink()
        with mock.patch.object(client, "transport") as transport:
            self.assertEqual("nothing", client.submit_ready()["status"])
            transport.assert_not_called()
            file.write_text("ANSWERS = {'q1': 3}\n")
            self.consent.choose(False)
            self.assertEqual("error", client.submit_ready()["status"])
            transport.assert_not_called()
        self.assertFalse(client.path.exists())
        self.assertTrue(file.exists())

    def test_ready_submission_keeps_the_connected_custom_server(self):
        client = self.client()
        client.connect_open("https://example.test")
        client.transport = mock.Mock(wraps=self.transport)
        with mock.patch.object(client, "connect_open", side_effect=AssertionError("기존 연결을 다시 만들면 안 됨")):
            self.assertEqual("ok", client.submit_ready()["status"])
        self.assertEqual("https://example.test", client.transport.call_args.args[0])
        self.assertEqual("/v1/private/submissions", client.transport.call_args.args[1])

    def test_ready_submission_does_not_enroll_an_unconfirmed_custom_server(self):
        client = self.client()
        client.save({"url": "https://example.test"})
        with mock.patch.object(client, "transport") as transport:
            self.assertEqual("error", client.submit_ready()["status"])
            transport.assert_not_called()

    def test_invalid_connection_and_pending_files_are_preserved_without_uploading(self):
        client = self.client()
        client.save({"token": "a" * 64})
        original = client.path.read_bytes()
        with mock.patch.object(client, "transport") as transport:
            with self.assertRaisesRegex(CollectionError, "운영자"):
                client.submit_ready()
            transport.assert_not_called()
        self.assertEqual(original, client.path.read_bytes())
        client.path.unlink()
        client.connect_open("https://example.test")
        client.pending_path.write_text("{broken", encoding="utf-8")
        with mock.patch.object(client, "transport") as transport:
            with self.assertRaisesRegex(CollectionError, "대기 정보"):
                client.pending()
            with self.assertRaisesRegex(CollectionError, "대기 정보"):
                client.submit_ready()
            transport.assert_not_called()
        self.assertEqual("{broken", client.pending_path.read_text(encoding="utf-8"))
        self.assertTrue((self.repo / "submissions/tester/r01/quiz.py").exists())

    def test_unauthorized_submission_gives_operator_help_without_erasing_connection(self):
        client = self.client()
        client.connect_open("https://example.test")
        original = client.path.read_bytes()
        flow = Flow(mock.Mock())
        flow.api = client
        with mock.patch.object(client, "transport", side_effect=CollectionError("인증을 확인해 주세요.", status=401)):
            result = flow.submit()
        self.assertEqual("error", result["status"])
        self.assertIn("운영자", result["message"])
        self.assertEqual(original, client.path.read_bytes())
        self.assertTrue(client.pending_path.exists())

    def test_ready_submission_recovers_a_lost_registration_ack_with_the_same_seed(self):
        client = self.client()
        registrations = []
        def wire(base, path, data, **kwargs):
            result = self.transport(base, path, data, **kwargs)
            if path == "/v1/register/private":
                registrations.append(dict(data))
                if len(registrations) == 1:
                    raise CollectionError("연결 응답 유실")
            return result
        client.transport = wire
        with self.assertRaises(CollectionError):
            client.submit_ready()
        self.assertEqual("ok", client.submit_ready()["status"])
        self.assertEqual(registrations[0], registrations[1])
        with self.db.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM participants").fetchone()[0])
            self.assertEqual(1, db.execute("SELECT count(*) FROM api_submissions").fetchone()[0])

    def test_pending_ack_is_retried_even_after_answers_revert_to_the_published_file(self):
        client = self.client()
        self.assertEqual("ok", client.submit_ready()["status"])
        file = self.repo / "submissions/tester/r01/quiz.py"
        original = file.read_text()
        file.write_text("ANSWERS = {'q1': 4}\n")
        failed = []
        def wire(base, path, data, **kwargs):
            result = self.transport(base, path, data, **kwargs)
            if path == "/v1/private/submissions" and not failed:
                failed.append(True)
                raise CollectionError("저장 응답 유실")
            return result
        client.transport = wire
        with mock.patch("learning_server.submissions.MIN_INTERVAL", 0):
            with self.assertRaises(CollectionError):
                client.submit_ready()
            file.write_text(original)
            self.assertTrue(client.pending()["pending"])
            self.assertEqual("ok", client.submit_ready()["status"])
        self.assertFalse(client.pending()["pending"])
        self.assertEqual(original, file.read_text())
        with self.db.connect() as db:
            self.assertEqual(3, db.execute("SELECT count(*) FROM api_submissions").fetchone()[0])

    def test_withdrawal_during_registration_does_not_restore_connection(self):
        client = self.client()
        transport = client.transport
        def withdrawing(*args, **kwargs):
            result = transport(*args, **kwargs)
            self.consent.withdraw()
            return result
        client.transport = withdrawing
        with self.assertRaises(CollectionError):
            client.connect_open("https://example.test")
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(client.path.exists())

    def test_missing_delete_confirmation_remains_pending(self):
        client = self.client()
        client.connect_open("https://example.test")
        self.consent.withdraw()
        with mock.patch.object(sharing, "request", return_value={"deleted": False}):
            self.assertTrue(self.consent.synchronize()["errors"])
        self.assertTrue(client.path.exists())

    def test_old_git_submit_is_closed_without_touching_git(self):
        import gitflow
        flow = gitflow.GitFlow(str(self.repo), "tester")
        with mock.patch.object(flow, "_run") as run:
            self.assertEqual("error", flow.submit()["status"])
            run.assert_not_called()

    def test_rejected_packet_does_not_block_a_fixed_file(self):
        client = self.client()
        client.connect_open("https://example.test")
        with mock.patch.object(client, "transport", side_effect=CollectionError("파일 거부", status=400)):
            with self.assertRaises(CollectionError):
                client.submit()
        self.assertFalse(client.pending_path.exists())
        self.assertEqual("ok", client.submit()["status"])

    def test_late_store_ack_cannot_restore_withdrawn_files(self):
        client = self.client()
        client.connect_open("https://example.test")
        transport = client.transport
        def withdraw_after_store(*args, **kwargs):
            value = transport(*args, **kwargs)
            self.consent.withdraw()
            self.assertTrue(self.consent.synchronize()["withdrawn"])
            return value
        client.transport = withdraw_after_store
        with self.assertRaises(CollectionError):
            client.submit()
        self.assertFalse(client.path.exists())
        self.assertFalse(client.pending_path.exists())

    def test_quota_refuses_new_data_but_allows_delete(self):
        client = self.client()
        client.connect_open("https://example.test")
        with mock.patch("learning_server.app.MAX_STORED_BYTES", 1):
            with self.assertRaises(CollectionError):
                client.submit()
        self.assertTrue(client.pending_path.exists())
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(client.pending_path.exists())

    def test_withdrawal_keeps_only_revocation_status(self):
        client = self.client()
        client.connect_open("https://example.test")
        config = client.settings()
        client.submit()
        self.consent.withdraw()
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        with self.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM submission_accounts WHERE participant=?", (config["participant"],)).fetchone()[0])
            self.assertEqual((1,), db.execute("SELECT revoked FROM participants WHERE participant=?", (config["participant"],)).fetchone())

    def test_locked_pending_file_is_retried_after_connection_was_deleted(self):
        client = self.client()
        client.connect_open("https://example.test")
        client.pending_path.write_text("temporary answer")
        legacy = self.consent.path.with_name("submission-pending.json")
        legacy.write_text("previous answer")
        original = Path.unlink
        def locked(path, *args, **kwargs):
            if path == client.pending_path:
                raise OSError("locked")
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "unlink", locked):
            self.consent.withdraw()
            self.assertTrue(self.consent.synchronize()["errors"])
            self.assertTrue(self.consent.settings()["withdraw_pending"])
        self.assertFalse(client.path.exists())
        self.assertTrue(client.pending_path.exists())
        self.assertFalse(legacy.exists())
        self.assertTrue(self.consent.synchronize()["withdrawn"])
        self.assertFalse(client.pending_path.exists())
