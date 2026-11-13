# -*- coding: utf-8 -*-
"""API 제출 연결의 공개 안내·오류·작은 창 배치를 임시 기록으로 확인함."""
from pathlib import Path
import threading
from unittest import mock

from tests import guikit
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QScrollArea
from aiprep.collection import CollectionError
from gui import theme
from submission_api import PrivateClient, Flow
from tests.test_gui_hub import HubTest


class ApiSetupTest(HubTest):
    def open_setup(self):
        win = self.boot()
        repo = Path(self.tmp) / "api-repo"
        folder = repo / "submissions/tester/r01"
        folder.mkdir(parents=True)
        (folder / "quiz.py").write_text("ANSWERS = {}\n", encoding="utf-8")
        self.git.api = PrivateClient(str(repo), "tester", {"python": win.session.collection, "ai": win.ai.collection})
        win.identity.save({"verified": True, "team": True, "token": "f" * 64})
        win.show_submission_setup()
        guikit.pump()
        self.capture_widget = win.submission_dialog
        return win, win.submission_dialog

    def test_setup_fits_small_window_max_text_and_both_themes(self):
        win, dialog = self.open_setup()
        win.resize(760, 480)
        win.set_text("larger")
        for selected in ("light", "dark"):
            theme.apply(guikit.APP, selected)
            area = win.screen().availableGeometry()
            dialog.resize(min(640, area.width() - 32), min(480, area.height() - 72))
            guikit.pump()
            self.assertLessEqual(dialog.width(), 760)
            self.assertLessEqual(dialog.height(), 480)
            self.assertIn("r01/quiz.py", dialog.files.toPlainText())
            self.assertGreaterEqual(dialog.connect_button.width(), dialog.connect_button.sizeHint().width())
            position = dialog.connect_button.mapTo(dialog, QPoint(0, 0))
            self.assertGreaterEqual(position.y(), 0)
            self.assertLessEqual(position.y() + dialog.connect_button.height(), dialog.height())
            self.assertFalse(hasattr(dialog, "invite"))

    def test_connection_error_keeps_answers_and_shows_message(self):
        win, dialog = self.open_setup()
        dialog.url.setText("https://example.test")
        dialog.confirm_private.setChecked(True)
        with mock.patch.object(self.git.api, "connect_open", side_effect=CollectionError("서버에 연결하지 못했습니다.")):
            guikit.click(dialog.connect_button)
            self.idle()
        self.assertTrue(win.dialog.isVisible())
        self.assertIn("서버에 연결하지", win.dialog.text.text())
        self.assertTrue((Path(self.tmp) / "api-repo/submissions/tester/r01/quiz.py").exists())

    def test_broken_connection_settings_remain_disabled_and_preserved(self):
        win, dialog = self.open_setup()
        dialog.close()
        self.git.api.path.parent.mkdir(parents=True, exist_ok=True)
        self.git.api.path.write_text("{broken", encoding="utf-8")
        win.show_submission_setup()
        current = win.submission_dialog
        self.assertFalse(current.confirm_private.isEnabled())
        self.assertFalse(current.connect_button.isEnabled())
        self.assertIn("읽을 수 없습니다", current.message.text())
        self.assertEqual("{broken", self.git.api.path.read_text(encoding="utf-8"))


class DirectSubmissionTest(HubTest):
    def setUp(self):
        super().setUp()
        guard = mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("시험에서 외부 서버를 호출할 수 없습니다."))
        guard.start()
        self.addCleanup(guard.stop)

    def prepare(self):
        win = self.boot()
        repo = Path(self.tmp) / "direct-submit"
        self.file = repo / "submissions/tester/r01/quiz.py"
        self.file.parent.mkdir(parents=True)
        self.file.write_text("ANSWERS = {'q1': 3}\n", encoding="utf-8")
        self.git.root, self.git.user = str(repo), "tester"
        win.gitflow = Flow(self.git)
        win.gitflow.set_collections({"python": win.session.collection, "ai": win.ai.collection})
        self.api = win.gitflow.api
        self.requests, self.stored = [], []
        self.api.transport = self.wire
        guikit.wait_until(lambda: win.pending_job is None)
        win.pending_submission = self.api.pending()
        win.workspace.refresh()
        return win

    def wire(self, base, path, data, **kwargs):
        self.requests.append(path)
        if path == "/v1/register/private":
            return {"participant": data["participant"], "token": "a" * 64}
        if path == "/v1/private/submissions":
            self.stored.append(dict(data["files"]))
            return {"state": "stored", "digest": data["digest"]}
        raise AssertionError("시험용 전송 경로가 아님")

    def test_current_consent_submits_without_reopening_setup_or_confirmation(self):
        win = self.prepare()
        consent = win.privacy.consent.settings()
        with mock.patch.object(win, "show_submission_setup") as setup, mock.patch.object(win, "show_privacy") as privacy, mock.patch.object(win, "ask") as ask:
            guikit.click(win.hub.submission_setup)
            self.idle()
            guikit.wait_until(lambda: win.pending_job is None)
            setup.assert_not_called()
            privacy.assert_not_called()
            ask.assert_not_called()
            self.assertEqual(["/v1/register/private", "/v1/private/submissions"], self.requests)
            self.assertEqual(1, len(self.stored))
            self.assertEqual("ok", win.workspace.submissions.result["status"])
            self.assertIn("저장", win.workspace.submissions.message.text())
            self.assertTrue(win.workspace.submissions.isVisible())
            self.assertFalse(win.hub.submission_setup.isVisible())
            self.assertFalse(win.hub.submission_setup.isEnabled())
            message = win.workspace.submissions.message.text()
            guikit.click(win.hub.submission_setup)
            self.idle()
            self.assertEqual(2, len(self.requests))
            self.assertEqual(message, win.workspace.submissions.message.text())
            ask.assert_not_called()
        self.assertEqual(consent, win.privacy.consent.settings())
        self.assertFalse(self.api.pending()["pending"])

    def test_missing_changed_or_withdrawing_consent_does_not_send_or_highlight(self):
        from learning_data.privacy import save
        win = self.prepare()
        original = win.privacy.consent.settings()
        for state in (dict(original, accepted=False), dict(original, policy_hash="changed"), dict(original, withdraw_pending=True)):
            save(win.privacy.consent.path, state)
            win.workspace.refresh()
            self.assertNotEqual("accent", win.hub.submission_setup.property("tone"))
            self.assertFalse(win.workspace.submissions.submit.isVisible())
            with mock.patch.object(win, "show_privacy") as privacy:
                win.submit_pr()
                privacy.assert_called_once()
            self.assertEqual([], self.requests)
            self.assertTrue(self.file.exists())
        save(win.privacy.consent.path, original)

    def test_accepting_consent_does_not_implicitly_submit_files(self):
        win = self.prepare()
        win.privacy.consent.choose(False)
        win.submit_pr()
        dialog = win.privacy.dialog
        dialog.research.setChecked(True)
        dialog.overseas.setChecked(True)
        guikit.click(dialog.agree)
        self.idle()
        self.assertEqual([], self.requests)
        self.assertTrue(win.has_submission_consent())
        guikit.click(win.hub.submission_setup)
        self.idle()
        self.assertEqual(1, len(self.stored))

    def test_offline_retry_keeps_answers_and_shows_the_error_in_place(self):
        win = self.prepare()
        before = self.file.read_bytes()
        with mock.patch.object(win, "ask") as ask:
            with mock.patch.object(self.api, "transport", side_effect=CollectionError("서버에 연결하지 못했습니다.")):
                guikit.click(win.hub.submission_setup)
                self.idle()
            self.assertEqual("error", win.workspace.submissions.result["status"])
            self.assertIn("연결하지 못했습니다", win.workspace.submissions.message.text())
            self.assertEqual(before, self.file.read_bytes())
            self.assertTrue(self.api.pending()["pending"])
            guikit.click(win.workspace.submissions.submit)
            self.idle()
            self.assertEqual("ok", win.workspace.submissions.result["status"])
            self.assertEqual(1, len(self.stored))
            ask.assert_not_called()

    def test_repeated_clicks_while_submitting_start_only_one_job(self):
        win = self.prepare()
        ready, release = threading.Event(), threading.Event()
        original = self.api.submit_ready
        def work():
            ready.set()
            if not release.wait(3):
                raise AssertionError("시험 전송 해제 신호를 받지 못함")
            return original()
        with mock.patch.object(self.api, "submit_ready", side_effect=work) as submit:
            try:
                win.submit_pr()
                guikit.wait_until(ready.is_set)
                self.assertFalse(win.hub.submission_setup.isEnabled())
                self.assertFalse(win.workspace.submissions.submit.isEnabled())
                self.assertIn("서버로 제출", win.workspace.submissions.message.text())
                win.submit_pr()
                submit.assert_called_once()
            finally:
                release.set()
            self.idle()
        self.assertEqual(1, len(self.stored))

    def test_file_preview_is_optional_and_server_connection_requires_verified_team(self):
        win = self.prepare()
        win.workspace.refresh()
        self.assertFalse(win.hub.server_connection.isVisible())
        win.show_submission_setup()
        self.assertFalse(hasattr(win, "submission_dialog"))
        win.show_privacy()
        dialog = win.privacy.dialog
        guikit.click(dialog.submission_files)
        preview = win.submission_files_dialog
        self.assertIn("r01/quiz.py", preview.files.toPlainText())
        self.assertEqual([], self.requests)
        preview.close()
        dialog.close()
        win.identity.save({"verified": True, "team": True, "token": "f" * 64})
        win.workspace.refresh()
        self.assertTrue(win.hub.server_connection.isVisible())
        for state in ({"verified": False, "team": True}, {"verified": True, "team": False}):
            with mock.patch.object(win.identity, "settings", return_value=state):
                win.workspace.refresh()
                self.assertFalse(win.hub.server_connection.isVisible())
                win.show_submission_setup()
                self.assertFalse(hasattr(win, "submission_dialog"))
        win.identity_invalid = True
        win.workspace.refresh()
        self.assertFalse(win.hub.server_connection.isVisible())
        win.identity_invalid = False
        win.identity_checked = False
        win.workspace.refresh()
        self.assertFalse(win.hub.server_connection.isVisible())
        win.identity_checked = True
        win.resize(760, 480)
        win.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            win.workspace.refresh()
            guikit.pump()
            button = win.hub.server_connection
            self.assertTrue(button.isVisible())
            self.assertTrue(button.visibleRegion().contains(button.rect()))
        guikit.click(win.hub.server_connection)
        self.assertTrue(win.submission_dialog.isVisible())
        win.submission_dialog.close()

    def test_pending_submission_and_result_fit_small_window_largest_text_both_themes(self):
        win = self.prepare()
        win.resize(760, 480)
        win.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            win.pending_submission = {"status": "ok", "pending": True, "count": 1}
            win.workspace.submissions.clear_result()
            win.workspace.refresh()
            guikit.pump()
            self.assertEqual("풀이 제출", win.hub.submission_setup.text())
            self.assertEqual("accent", win.hub.submission_setup.property("tone"))
            for button in (win.hub.submission_setup, win.workspace.submissions.submit):
                self.assertGreaterEqual(button.width(), button.sizeHint().width())
                self.assertTrue(button.visibleRegion().contains(button.rect()))
            scroll = max(win.hub.findChildren(QScrollArea), key=lambda area: area.width())
            scroll.verticalScrollBar().setValue(40)
            win.hub.submission_setup.setFocus(Qt.FocusReason.TabFocusReason)
            before = scroll.verticalScrollBar().value()
            before_width = win.hub.submission_setup.sizeHint().width()
            win.pending_submission = {"status": "ok", "pending": False, "count": 0}
            win.workspace.submissions.show_result({"status": "ok", "message": "비공개 서버에 풀이를 저장했습니다."})
            guikit.pump()
            self.assertIs(win.workspace, QApplication.focusWidget())
            self.assertTrue(win.hub.submission_setup.isHidden())
            self.assertFalse(win.hub.submission_setup.isEnabled())
            self.assertEqual(before, scroll.verticalScrollBar().value())
            self.assertNotEqual("accent", win.hub.submission_setup.property("tone"))
            self.assertEqual(before_width, win.hub.submission_setup.sizeHint().width())
            self.assertTrue(win.workspace.submissions.dismiss.visibleRegion().contains(win.workspace.submissions.dismiss.rect()))
            win.problem_updates = {"status": "ok", "available": True, "count": 1}
            win.pending_submission = {"status": "checking", "pending": False, "count": 0}
            error = "풀이 파일을 읽지 못했습니다. " + "긴파일경로/" * 100
            win.workspace.submissions.show_result({"status": "error", "message": error})
            win.pending_submission = {"status": "ok", "pending": True, "count": 1}
            win.workspace.refresh()
            guikit.pump()
            self.assertEqual("error", win.workspace.submissions.result["status"])
            self.assertLessEqual(len(win.workspace.submissions.message.text()), 49)
            with mock.patch.object(win, "ask") as ask:
                for button in (win.workspace.submissions.submit, win.workspace.submissions.sync,
                               win.workspace.submissions.details, win.workspace.submissions.dismiss):
                    self.assertTrue(button.visibleRegion().contains(button.rect()))
                ask.assert_not_called()
                guikit.click(win.workspace.submissions.details)
                self.assertEqual(error, ask.call_args.args[1])
            win.workspace.submissions.details.setFocus(Qt.FocusReason.TabFocusReason)
            win.workspace.submissions.dismiss_result()
            self.assertFalse(win.workspace.submissions.details.hasFocus())
            self.assertEqual(before, scroll.verticalScrollBar().value())
            win.workspace.submissions.show_result({"status": "error", "message": "연결 오류\n다시 시도해 주세요."})
            self.assertTrue(win.workspace.submissions.details.isVisible())
        win.pending_submission = {"status": "ok", "pending": True, "count": 1}
        win.problem_updates = {"status": "ok", "available": False}
        win.workspace.submissions.clear_result()
        win.workspace.refresh()
