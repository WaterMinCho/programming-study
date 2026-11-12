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

    def client(self):
        self.app = application(self.db)
        self.consent.choose(True)
        folder = self.repo / "submissions/tester/r01"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "quiz.py").write_text("ANSWERS = {'q1': 3}\n")
        client = PrivateClient(str(self.repo), "tester", self.collections)
        client.transport = self.transport
        return client

    def test_production_public_routes_are_closed_before_any_publisher(self):
        self.app = application(self.db)
        with mock.patch("learning_server.submissions.Publisher.configured") as publisher:
            for path in ("/v1/register", "/v1/register/open", "/v1/submissions", "/v1/submissions/publish"):
                self.assertEqual(410, self.call(path, {})[0])
            publisher.assert_not_called()

    def test_private_submission_stores_and_retries_without_git(self):
        client = self.client()
        with mock.patch("learning_server.submissions.Publisher.configured") as publisher:
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
        self.assertEqual("setup_required", flow.submit()["status"])
        git.submit.assert_not_called()

    def test_withdrawal_during_registration_does_not_restore_connection(self):
        client = self.client()
        transport = client.transport
        def withdrawing(*args, **kwargs):
            result = transport(*args, **kwargs)
            self.consent.choose(False)
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
