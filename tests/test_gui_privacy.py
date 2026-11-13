# -*- coding: utf-8 -*-
"""첫 동의 화면의 선택·거부·작은 창 배치를 확인함."""
from tests import guikit
from unittest import mock, TestCase
import os
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest

from gui import theme
from aiprep import service as ai_service
from session import SessionError
from tests.test_gui_hub import HubTest
from gui.privacy import SyncController
from aiprep.collection import CollectionError


class PrivacyGuiTest(HubTest):
    def test_first_decline_can_close_when_consent_settings_cannot_be_saved(self):
        win, dialog = self.open_first()
        for store in win.privacy.consent.collections.values():
            with store._connect() as db:
                db.execute("DELETE FROM meta WHERE key='privacy_state_path'")
            store.set_enabled(True)
            self.assertTrue(store.status()["enabled"])
        with mock.patch.object(win.privacy.consent, "choose", side_effect=OSError("설정 폴더 쓰기 실패")):
            guikit.click(dialog.decline)
        self.assertFalse(dialog.isVisible())
        self.assertIn("수집 없이", win.privacy.message)
        self.assertTrue(win.privacy.cancel.is_set())
        for store in win.privacy.consent.collections.values():
            self.assertFalse(store.status()["enabled"])
            self.assertFalse(store.emit("answer", {"result": "pass"}))

    def test_reopening_a_learner_reuses_the_same_privacy_controller(self):
        win = self.boot()
        original = win.privacy
        win.open_session()
        self.idle()
        self.assertIs(original, win.privacy)
        self.assertEqual(1, len(win.privacy_controllers))

    def test_broken_ai_learning_record_does_not_skip_its_withdrawal(self):
        win = self.boot()
        original = win.ai.collection
        with mock.patch.object(ai_service, "AiSession", side_effect=SessionError("임시 학습 기록 오류")):
            win.open_session()
            self.idle()
        self.assertIsNone(win.ai)
        self.assertEqual(original.path, win.privacy.consent.collections["ai"].path)
        win.privacy.consent.withdraw()
        self.assertFalse(original.status()["enabled"])

    def open_first(self):
        win = self.boot()
        win.resize(760, 480)
        win.privacy.consent.choose(False)
        win.privacy.consent.path.unlink()
        win.privacy.show(first=True)
        guikit.pump()
        self.capture_widget = win.privacy.dialog
        return win, self.capture_widget

    def test_consent_fits_small_window_max_text_and_both_themes(self):
        win, dialog = self.open_first()
        win.set_text("larger")
        for selected in ("light", "dark"):
            theme.apply(guikit.APP, selected)
            area = win.screen().availableGeometry()
            dialog.resize(min(640, area.width()-32), min(480, area.height()-72))
            guikit.pump()
            self.assertLessEqual(dialog.width(), min(640, area.width()-32))
            self.assertFalse(dialog.agree.isEnabled())
            self.assertEqual("학습 데이터 제공 동의 (선택)", dialog.research.text())
            self.assertEqual("비공개 서버 보관 동의 (선택)", dialog.overseas.text())
            self.assertEqual("비공개 서버에 보관합니다.", dialog.storage_hint.text())
            self.assertEqual("body", dialog.storage_hint.property("role"))
            for widget in (dialog.agree, dialog.decline, dialog.research, dialog.overseas, dialog.storage_hint):
                point = widget.mapTo(dialog, QPoint(0, 0))
                self.assertGreaterEqual(point.y(), 0)
                self.assertLessEqual(point.y()+widget.height(), dialog.height())
                self.assertGreaterEqual(widget.width(), widget.sizeHint().width())
            self.assertEqual(0, dialog.scroll.horizontalScrollBar().maximum())

    def test_decline_and_later_consent_preserve_learning_profile(self):
        win, dialog = self.open_first()
        profile = win.session.prof.copy()
        guikit.click(dialog.decline)
        self.assertFalse(win.privacy.consent.settings()["accepted"])
        self.assertFalse(win.session.collection.status()["enabled"])
        win.show_privacy()
        dialog = win.privacy.dialog
        self.assertFalse(dialog.agree.isEnabled())
        QTest.mouseClick(dialog.research, Qt.MouseButton.LeftButton, pos=QPoint(8, dialog.research.height()//2))
        self.assertFalse(dialog.agree.isEnabled())
        QTest.mouseClick(dialog.overseas, Qt.MouseButton.LeftButton, pos=QPoint(8, dialog.overseas.height()//2))
        guikit.click(dialog.agree)
        self.assertTrue(win.privacy.consent.settings()["accepted"])
        self.assertTrue(win.session.collection.status()["enabled"])
        self.assertEqual(profile, win.session.prof)
        win.show_privacy()
        self.assertFalse(win.privacy.dialog.choices.isVisible())
        self.assertTrue(win.privacy.dialog.withdraw.isVisible())


class SyncSchedulingGuiTest(TestCase):
    def setUp(self):
        from PyQt6.QtWidgets import QWidget
        self.parent = QWidget()
        self.addCleanup(self.parent.deleteLater)
        self.state = {"choice": "one", "accepted": True}
        with mock.patch("gui.privacy.Consent") as consent, mock.patch.dict(os.environ, STUDY_AUTO_SYNC="0"):
            consent.return_value.settings.side_effect = lambda: dict(self.state)
            self.controller = SyncController(self.parent, {})
        self.addCleanup(self.controller.timer.stop)

    def release(self):
        self.controller.job = mock.Mock()
        self.controller.job_choice = self.state["choice"]
        with mock.patch.dict(os.environ, STUDY_AUTO_SYNC="1"), \
                mock.patch("aiprep.sync_schedule.secrets.randbelow", return_value=0):
            self.controller.release_job()

    def test_failed_upload_backs_off_success_resets_and_withdrawal_stays_short(self):
        self.assertTrue(self.controller.timer.isSingleShot())
        self.controller.finish({"errors": ["연결 실패"]})
        self.release()
        self.assertEqual(96000, self.controller.timer.interval())
        self.controller.failures = 4
        self.state["withdraw_pending"] = True
        self.release()
        self.assertEqual(48000, self.controller.timer.interval())
        self.controller.finish({"sent": 1})
        self.assertEqual(0, self.controller.failures)

    def test_broken_settings_retry_and_stopping_does_not_schedule_another_job(self):
        self.controller.consent.settings.side_effect = CollectionError("설정 파일 오류")
        with mock.patch.dict(os.environ, STUDY_AUTO_SYNC="1"), \
                mock.patch("aiprep.sync_schedule.secrets.randbelow", return_value=0):
            self.controller.tick()
        self.assertTrue(self.controller.timer.isActive())
        self.assertEqual(96000, self.controller.timer.interval())
        self.controller.closing = True
        self.controller.job = mock.Mock()
        self.controller.timer.stop()
        with mock.patch.object(self.parent, "close") as close:
            self.controller.release_job()
        close.assert_called_once_with()
        self.assertFalse(self.controller.timer.isActive())
