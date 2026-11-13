# -*- coding: utf-8 -*-
"""과목 이동의 글자·아이콘 정렬과 실제 화면 전환을 확인함."""
import copy
from tests import guikit

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtTest import QTest

from gui import theme
from tests.test_gui_hub import HubTest


class NavigationTest(HubTest):
    def test_sidebar_labels_and_keyboard_navigation_fit_both_themes_at_max_text(self):
        win = self.boot()
        win.resize(1180, 600)
        win.move(win.screen().availableGeometry().topLeft() + QPoint(12, 12))
        win.set_text("larger")
        before = copy.deepcopy(win.session.prof)
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            guikit.pump()
            self.assertTrue(win.workspace.rail.isVisible())
            buttons = win.workspace.buttons
            parents = [button for button in buttons.values() if button.depth == 0]
            children = [button for button in buttons.values() if button.depth == 1]
            self.assertEqual(1, len({button.text_rect().left() for button in parents}))
            self.assertEqual(1, len({button.text_rect().left() for button in children}))
            self.assertGreater(children[0].text_rect().left(), parents[0].text_rect().left())
            self.assertEqual(1, len({button.height() for button in buttons.values()}))
            for tid in ("python", "ai", "journey", "hub"):
                button = buttons[tid]
                button.setFocus()
                QTest.keyClick(button, Qt.Key.Key_Space)
                self.idle()
                self.assertEqual(tid, win.area)
                self.assertTrue(button.isChecked())
                self.assertEqual(1, sum(item.isChecked() for item in buttons.values()))
                metrics = QFontMetricsF(theme.font("label", True))
                self.assertLessEqual(metrics.horizontalAdvance(button.text()), button.text_rect().width())
                self.assertLessEqual(metrics.height(), button.text_rect().height())
                self.assertEqual(button.accessibleName(), button.text())
                self.assertLessEqual(button.minimumHeight(), button.maximumHeight())
        self.assertEqual(before, win.session.prof)
        win.set_text("normal")
        win.resize(760, 480)
        guikit.pump()
        self.assertFalse(win.workspace.rail.isVisible())
        self.assertTrue(win.workspace.compact.isVisible())
        win.resize(1180, 600)
        guikit.pump()
        self.assertTrue(win.workspace.rail.isVisible())
        self.assertFalse(win.workspace.compact.isVisible())
        win.set_text("larger")
        guikit.pump()
