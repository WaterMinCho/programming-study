# -*- coding: utf-8 -*-
"""추가 선택·비동기 제출·재시도·중복·종료를 가상 기록과 전송으로 확인함."""
import os
import threading
from unittest import mock

from tests import guikit
from tests.test_gui_hub import HubTest
from tests import test_gui_submission as submission_fixture
from gui import theme
from gui.privacy import AutoSubmissionDialog
from learning_data.collection import CollectionError


class AutomaticSubmissionTest(HubTest):
    prepare = submission_fixture.DirectSubmissionTest.prepare

    def wire(self, base, path, data, **kwargs):
        if path == "/v1/consent":
            self.requests.append(path)
            return {"consent_saved": True}
        return submission_fixture.DirectSubmissionTest.wire(self, base, path, data, **kwargs)

    def enable(self, win):
        win.privacy.consent.set_auto_submission(True)
        os.environ["STUDY_AUTO_SYNC"] = "1"
        win.auto_submission.request()
        self.start(win)

    def start(self, win):
        win.auto_submission.timer.stop()
        win.auto_submission.tick()

    def finished(self, win):
        guikit.wait_until(lambda: win.auto_submission.job is None)
        guikit.wait_until(lambda: win.pending_job is None)

    def test_startup_backlog_and_repeated_checkpoint_submit_only_changed_files(self):
        win = self.prepare()
        before = self.file.read_bytes()
        self.enable(win)
        self.finished(win)
        self.assertEqual(1, len(self.stored))
        self.assertEqual(before, self.file.read_bytes())
        self.assertIn("자동 제출", win.workspace.submissions.message.text())
        win.auto_submission.request()
        self.start(win)
        self.finished(win)
        self.assertEqual(1, len(self.stored))
        self.file.write_text("ANSWERS = {'q1': 4}\n")
        win.auto_submission.request()
        self.start(win)
        self.finished(win)
        self.assertEqual(2, len(self.stored))

    def test_default_consent_and_refusal_never_automatically_send_files(self):
        win = self.prepare()
        os.environ["STUDY_AUTO_SYNC"] = "1"
        win.auto_submission.request()
        self.start(win)
        self.assertIsNone(win.auto_submission.job)
        self.assertEqual([], self.requests)
        win.privacy.consent.set_auto_submission(False)
        win.auto_submission.request()
        self.start(win)
        self.finished(win)
        self.assertEqual([], self.requests)
        self.assertTrue(win.privacy.consent.settings()["accepted"])

    def test_new_checkpoint_during_upload_is_kept_and_manual_click_does_not_overlap(self):
        win = self.prepare()
        entered, release = threading.Event(), threading.Event()
        original = self.api.submit_ready
        def work(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise AssertionError("시험 전송 해제 신호를 받지 못함")
            return original(*args, **kwargs)
        with mock.patch.object(self.api, "submit_ready", side_effect=work) as submit:
            try:
                self.enable(win)
                guikit.wait_until(entered.is_set)
                self.assertIsNone(win.job)
                self.assertTrue(win.workspace.rail.isEnabled())
                self.assertFalse(win.hub.submission_setup.isEnabled())
                win.submit_pr()
                self.assertEqual(1, submit.call_count)
                win.auto_submission.request()
            finally:
                release.set()
            self.finished(win)
            self.start(win)
            self.finished(win)
        self.assertEqual(1, len(self.stored))

    def test_offline_retry_preserves_data_and_permission_off_is_synced_without_files(self):
        win = self.prepare()
        before = self.file.read_bytes()
        with mock.patch.object(self.api, "transport", side_effect=CollectionError("연결하지 못했습니다.", code="network")):
            self.enable(win)
            self.finished(win)
        self.assertTrue(win.auto_submission.wanted)
        self.assertTrue(win.auto_submission.timer.isActive())
        self.assertEqual(before, self.file.read_bytes())
        self.start(win)
        self.finished(win)
        self.assertEqual(1, len(self.stored))
        win.privacy.consent.set_auto_submission(False)
        win.privacy.changed.emit()
        self.start(win)
        self.finished(win)
        self.assertIn("/v1/consent", self.requests)
        self.assertEqual(1, len(self.stored))

    def test_permanent_failure_is_not_repeated_after_restart_without_file_change(self):
        from gui.auto_submission import AutoSubmission
        win = self.prepare()
        with mock.patch.object(self.api, "transport", side_effect=CollectionError("인증을 확인해 주세요.", status=401)) as transport:
            self.enable(win)
            self.finished(win)
            count = transport.call_count
            win.auto_submission.stop()
            win.auto_submission = AutoSubmission(win)
            win.auto_submission.request()
            self.start(win)
            self.finished(win)
            self.assertEqual(count, transport.call_count)
            self.file.write_text("ANSWERS = {'q1': 8}\n")
            win.auto_submission.request()
            self.start(win)
            self.finished(win)
            self.assertGreater(transport.call_count, count)

    def test_close_waits_for_inflight_work_without_erasing_the_local_answer(self):
        win = self.prepare()
        entered, release = threading.Event(), threading.Event()
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise AssertionError("시험 전송 해제 신호를 받지 못함")
            return {"status": "paused", "message": "자동 제출을 멈췄습니다."}
        with mock.patch.object(self.api, "submit_ready", side_effect=blocked):
            try:
                self.enable(win)
                guikit.wait_until(entered.is_set)
                win.close()
                self.assertTrue(win.isVisible())
                self.assertTrue(win.auto_submission.closing)
            finally:
                release.set()
            guikit.wait_until(lambda: not win.isVisible())
            self.assertIsNone(win.auto_submission.job)
        self.assertTrue(self.file.exists())

    def test_disabled_scope_cancels_a_queued_job_without_declining_research(self):
        win = self.prepare()
        win.privacy.consent.set_auto_submission(True)
        os.environ["STUDY_AUTO_SYNC"] = "1"
        win.auto_submission.request()
        win.privacy.consent.set_auto_submission(False)
        win.privacy.changed.emit()
        self.start(win)
        self.finished(win)
        self.assertTrue(win.privacy.consent.settings()["accepted"])
        self.assertEqual([], self.stored)

    def test_bad_json_is_not_retried_until_the_file_changes(self):
        win = self.prepare()
        broken = self.file.with_suffix(".json")
        broken.write_text("{broken", encoding="utf-8")
        self.enable(win)
        self.finished(win)
        self.assertFalse(win.auto_submission.wanted)
        self.assertFalse(win.auto_submission.timer.isActive())
        self.assertEqual([], self.requests)
        broken.write_text("{}", encoding="utf-8")
        win.auto_submission.request()
        self.start(win)
        self.finished(win)
        self.assertEqual(1, len(self.stored))

    def test_canceling_close_restores_automatic_submission(self):
        win = self.prepare()
        win.auto_submission.stop()
        with mock.patch.object(win, "leave_pages", return_value=False):
            win.close()
        self.assertTrue(win.isVisible())
        self.assertFalse(win.auto_submission.closing)

    def test_identity_confirmation_during_close_restores_background_work(self):
        win = self.prepare()
        win.auto_submission.stop()
        with mock.patch.object(win, "identity_dialog", mock.Mock(job=object())) as dialog:
            win.close()
            dialog.reject.assert_called_once()
        self.assertTrue(win.isVisible())
        self.assertFalse(win.auto_submission.closing)

    def test_local_permission_failure_stops_automatic_retry(self):
        win = self.prepare()
        with mock.patch.object(self.api, "submit_ready", side_effect=PermissionError("permission denied")):
            self.enable(win)
            self.finished(win)
        self.assertFalse(win.auto_submission.wanted)
        self.assertFalse(win.auto_submission.timer.isActive())
        self.assertTrue(self.file.exists())

    def test_notice_keeps_existing_consent_and_fits_small_window_max_text_both_themes(self):
        win = self.prepare()
        before = win.privacy.consent.settings()
        win.resize(760, 480)
        win.set_text("larger")
        dialog = AutoSubmissionDialog(win, win.privacy)
        self.capture_widget = dialog
        dialog.show()
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            dialog.shell.fit(700, 460)
            guikit.pump()
            self.assertLessEqual(dialog.height(), 480)
            self.assertTrue(dialog.enable.visibleRegion().contains(dialog.enable.rect()))
            self.assertTrue(dialog.storage_hint.visibleRegion().contains(dialog.storage_hint.rect()))
        dialog.reject()
        after = win.privacy.consent.settings()
        self.assertTrue(after["accepted"])
        self.assertEqual(before["at"], after["at"])
        self.assertEqual(before["start"], after["start"])
        self.assertFalse(after["receipt"]["automatic_submission"]["accepted"])
        self.assertFalse(win.privacy.consent.needs_auto_choice())
        dialog = AutoSubmissionDialog(win, win.privacy)
        self.capture_widget = dialog
        dialog.show()
        guikit.click(dialog.enable)
        self.assertTrue(win.privacy.consent.settings()["receipt"]["automatic_submission"]["accepted"])
        dialog = AutoSubmissionDialog(win, win.privacy)
        dialog.show()
        dialog.reject()
        self.assertTrue(win.privacy.consent.settings()["receipt"]["automatic_submission"]["accepted"])
        self.capture_widget = AutoSubmissionDialog(win, win.privacy)
        self.capture_widget.show()
