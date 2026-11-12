# -*- coding: utf-8 -*-
"""첫 동의 화면의 선택·거부·작은 창 배치를 확인함."""
from tests import guikit
from unittest import mock
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest

from gui import theme
from aiprep import service as ai_service
from session import SessionError
from tests.test_gui_hub import HubTest


class PrivacyGuiTest(HubTest):
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
            for widget in (dialog.agree, dialog.decline, dialog.research, dialog.overseas):
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
        for box in (dialog.research, dialog.overseas):
            QTest.mouseClick(box, Qt.MouseButton.LeftButton, pos=QPoint(8, box.height()//2))
        guikit.click(dialog.agree)
        self.assertTrue(win.privacy.consent.settings()["accepted"])
        self.assertTrue(win.session.collection.status()["enabled"])
        self.assertEqual(profile, win.session.prof)
