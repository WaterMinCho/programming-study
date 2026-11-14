# -*- coding: utf-8 -*-
"""설정 팝업의 화면 경계·키보드·보조 동작·종료를 외부 연결 없이 확인함."""
import copy
import os
import subprocess
import sys
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from tests import guikit, test_gui_hub
from PyQt6 import sip
from PyQt6.QtCore import QEasingCurve, QPoint, QSettings, Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtTest import QTest

from gui import feedback, motion, theme
from gui.settings_menu import QDesktopServices


class SettingsMenuTest(test_gui_hub.HubTest):
    def open_menu(self):
        win = self.boot()
        guikit.click(win.hub.settings_btn)
        return win, win.hub.settings_panel

    def test_popup_fits_and_reanchors_at_max_text_in_both_themes(self):
        win, menu = self.open_menu()
        hub = win.hub
        before = copy.deepcopy(win.session.prof)
        self.assertEqual(hub.settings_btn.text(), "설정")
        self.assertEqual(menu.windowType(), Qt.WindowType.Popup)
        self.assertFalse(menu.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose))
        self.assertEqual(hub.layout().indexOf(menu), -1)
        self.assertEqual(len(menu.actions), 4)
        self.assertEqual([button.text() for button in menu.theme_buttons.values()], ["시스템 따르기", "밝게", "어둡게"])
        available = menu.screen().availableGeometry()
        sizes = ((1280, 800), (1024, 700), (760, 480))
        if guikit.APP.platformName() != "offscreen":
            sizes = tuple((min(width, available.width() - 48), min(height, available.height() - 64)) for width, height in sizes)
        for mode in ("light", "dark"):
            win.set_theme(mode)
            win.set_text("larger")
            for size in sizes:
                with self.subTest(mode=mode, size=size):
                    win.resize(*size)
                    guikit.wait_until(lambda: not menu.anchor_timer.isActive() and menu.size() == menu.sizeHint())
                    guikit.pump()
                    self.assertEqual((win.width(), win.height()), size)
                    self.assertTrue(menu.screen().availableGeometry().contains(menu.geometry()))
                    for button in menu.controls():
                        rect = button.rect().translated(button.mapTo(menu, QPoint()))
                        self.assertTrue(menu.rect().contains(rect), button.text())
                        self.assertGreaterEqual(button.width(), button.fontMetrics().horizontalAdvance(button.text()) + 28, button.text())
                        self.assertEqual(button.height(), theme.control_height("s"))
                    for buttons in (hub.text_buttons, hub.theme_buttons):
                        self.assertEqual(len({button.width() for button in buttons.values()}), 1)
                        self.assertEqual({button.font().pixelSize() for button in buttons.values()}, {theme.TYPE["caption"][0]})
                    self.assertEqual([key for key, button in hub.theme_buttons.items() if button.isChecked()], [mode])
        available = menu.screen().availableGeometry()
        win.move(available.left(), available.bottom() - 100)
        guikit.pump()
        guikit.wait_until(lambda: not menu.anchor_timer.isActive())
        self.assertLess(menu.geometry().bottom(), hub.settings_btn.mapToGlobal(QPoint()).y())
        self.assertTrue(available.contains(menu.geometry()))
        win.move(available.topLeft())
        guikit.pump()
        self.assertEqual(win.session.prof, before)
        self.capture_widget = menu

    def test_keyboard_dismissal_restores_focus(self):
        win, menu = self.open_menu()
        selected = menu.text_buttons[theme.state["text"]]
        self.assertTrue(selected.hasFocus())
        controls = menu.controls()
        selected.setFocus()
        for _ in range(len(controls)):
            current = guikit.APP.focusWidget()
            QTest.keyClick(current, Qt.Key.Key_Tab)
            self.assertIs(guikit.APP.focusWidget(), controls[(controls.index(current) + 1) % len(controls)])
        QTest.keyClick(guikit.APP.focusWidget(), Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        self.assertIn(guikit.APP.focusWidget(), controls)
        for key, direction in ((Qt.Key.Key_Right, 1), (Qt.Key.Key_Down, 1), (Qt.Key.Key_Left, -1), (Qt.Key.Key_Up, -1)):
            current = guikit.APP.focusWidget()
            QTest.keyClick(current, key)
            self.assertIs(guikit.APP.focusWidget(), controls[(controls.index(current) + direction) % len(controls)])
        menu.theme_buttons["dark"].setFocus()
        QTest.keyClick(menu.theme_buttons["dark"], Qt.Key.Key_Return)
        guikit.pump()
        self.assertTrue(menu.isVisible())
        self.assertEqual(win.settings.value("theme"), "dark")
        QTest.keyClick(guikit.APP.focusWidget(), Qt.Key.Key_Escape)
        guikit.pump()
        self.assertFalse(menu.isVisible())
        self.assertFalse(win.hub.settings_btn.isChecked())
        self.assertTrue(win.hub.settings_btn.hasFocus())
        guikit.click(win.hub.settings_btn)
        self.assertTrue(menu.isVisible())

    def test_update_check_and_identity_wait_for_other_work(self):
        win, menu = self.open_menu()
        win.hub.set_busy(True)
        for button in (menu.update_btn, menu.identity_btn, menu.replay_tour):
            self.assertFalse(button.isEnabled())
        self.assertTrue(menu.report_btn.isEnabled())
        win.hub.set_busy(False)
        self.assertTrue(menu.update_btn.isEnabled())
        with mock.patch.object(win, "gitflow", None):
            menu.refresh_actions()
            self.assertFalse(menu.update_btn.isEnabled())
        menu.refresh_actions()
        self.assertTrue(menu.isVisible())

    def test_outside_click_and_trigger_close_without_moving_the_page(self):
        win, menu = self.open_menu()
        hub = win.hub
        viewport = hub.scroll.viewport().geometry()
        self.assertFalse(hasattr(hub, "foot"))
        QTest.mouseClick(win, guikit.LEFT, pos=QPoint(20, win.height() - 20))
        guikit.pump()
        self.assertFalse(menu.isVisible())
        guikit.click(hub.settings_btn)
        self.assertTrue(menu.isVisible())
        guikit.click(hub.settings_btn)
        self.assertFalse(menu.isVisible())
        self.assertTrue(hub.settings_btn.hasFocus())
        self.assertEqual(hub.scroll.viewport().geometry(), viewport)

    def test_actions_hide_before_callbacks_and_use_the_existing_update_check(self):
        win, menu = self.open_menu()
        seen = []
        with mock.patch.object(win, "check_updates", side_effect=lambda: seen.append(("update", menu.isVisible()))), \
                mock.patch.object(win, "ensure_identity", side_effect=lambda **kw: seen.append(("identity", menu.isVisible(), kw))), \
                mock.patch.object(win, "show_hub_tour", side_effect=lambda **kw: seen.append(("tour", menu.isVisible(), kw))), \
                mock.patch.object(QDesktopServices, "openUrl", side_effect=lambda url: seen.append(("report", menu.isVisible(), url.toString()))), \
                mock.patch.object(feedback, "commit", return_value="e" * 40):
            for button in (menu.update_btn, menu.identity_btn, menu.replay_tour, menu.report_btn):
                menu.open_menu()
                guikit.click(button)
                self.assertFalse(menu.isVisible())
        self.assertEqual(seen[:3], [("update", False), ("identity", False, {"force": True}), ("tour", False, {"replay": True})])
        self.assertEqual(seen[3][:2], ("report", False))
        query = parse_qs(urlsplit(seen[3][2]).query)
        self.assertEqual(query["template"], ["trouble.yml"])
        self.assertIn("screen: hub", query["env"][0])
        self.assertIn("window: %dx%d" % (win.width(), win.height()), query["env"][0])
        self.assertNotIn("exception:", query["env"][0])

    def test_text_and_theme_choices_are_remembered_after_reopening(self):
        win, menu = self.open_menu()
        for step in ("normal", "larger", "large", "normal"):
            guikit.click(menu.text_buttons[step])
            self.assertTrue(menu.isVisible())
            self.assertEqual(win.settings.value("text"), step)
            self.assertEqual([key for key, button in menu.text_buttons.items() if button.isChecked()], [step])
        for mode in ("dark", "light", "system"):
            guikit.click(menu.theme_buttons[mode])
            self.assertEqual(win.settings.value("theme"), mode)
        menu.dismiss()
        guikit.click(win.hub.settings_btn)
        win.settings.sync()
        saved = QSettings(win.settings.fileName(), QSettings.Format.IniFormat)
        self.assertEqual((saved.value("text"), saved.value("theme")), ("normal", "system"))
        self.assertTrue(menu.text_buttons["normal"].isChecked())
        self.assertTrue(menu.theme_buttons["system"].isChecked())

    def test_fades_use_opposite_curves_and_reduced_motion_finishes_immediately(self):
        win = self.boot()
        menu = win.hub.settings_panel
        with mock.patch.object(motion, "enabled", True):
            menu.open_menu()
            self.assertEqual(menu._motion.easingCurve().type(), QEasingCurve.Type.InCubic)
            guikit.wait_until(lambda: menu._motion is None)
            self.assertEqual(menu._opacity_effect.opacity(), 1.0)
            menu.dismiss()
            self.assertEqual(menu._motion.easingCurve().type(), QEasingCurve.Type.OutCubic)
            self.assertTrue(menu.isVisible())
            current = menu._opacity_effect.opacity()
            menu.open_menu()
            self.assertEqual(menu._opacity_effect.opacity(), current)
            guikit.wait_until(lambda: menu._motion is None)
            self.assertTrue(menu.isVisible())
            menu.dismiss()
            guikit.wait_until(lambda: not menu.isVisible())
            menu.open_menu()
            self.assertEqual(menu._opacity_effect.opacity(), 0.0)
            guikit.wait_until(lambda: menu._motion is None)
            menu.dismiss()
            guikit.wait_until(lambda: not menu.isVisible())
        menu.open_menu()
        self.assertIsNone(menu._motion)
        self.assertEqual(menu._opacity_effect.opacity(), 1.0)
        menu.dismiss()
        self.assertFalse(menu.isVisible())
        self.assertIsNone(menu._motion)

    def test_choices_keep_existing_answers_and_selections(self):
        win, menu = self.open_menu()
        field, editor = win.round_page.text_panel.single, win.round_page.code_panel.editor
        field.setText("saved answer")
        field.setSelection(2, 5)
        editor.setPlainText("answer = 12\nprint(answer)")
        cursor = editor.textCursor()
        cursor.setPosition(1)
        cursor.setPosition(9, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

        def state():
            cursor = editor.textCursor()
            return (field.text(), field.selectionStart(), field.selectedText(), editor.toPlainText(), cursor.anchor(), cursor.position())

        before, profile = state(), copy.deepcopy(win.session.prof)
        for step in ("normal", "larger", "large"):
            for mode in ("light", "dark", "system"):
                guikit.click(menu.text_buttons[step])
                guikit.click(menu.theme_buttons[mode])
                self.assertEqual(state(), before)
                self.assertTrue(menu.isVisible())
        self.assertEqual(win.session.prof, profile)

    def test_closing_or_deleting_the_owner_cancels_deferred_actions(self):
        win, menu = self.open_menu()
        with mock.patch.object(win, "check_updates") as check:
            menu.update_btn.click()
            self.assertTrue(menu.action_timer.isActive())
            win.close()
            guikit.pump()
            check.assert_not_called()
        win.show()
        menu.open_menu()
        with mock.patch.object(win, "check_updates") as check:
            menu.update_btn.click()
            sip.delete(win)
            self.win = None
            guikit.pump()
            check.assert_not_called()

    def test_window_close_hides_the_popup_during_a_fade(self):
        win = self.boot()
        with mock.patch.object(motion, "enabled", True):
            menu = win.hub.settings_panel
            menu.open_menu()
            win.close()
            guikit.pump()
            self.assertFalse(menu.isVisible())
            self.assertFalse(win.isVisible())
            self.assertIsNone(guikit.APP.activePopupWidget())

    def test_popup_close_does_not_quit_but_the_owner_close_still_quits(self):
        code = '''
from tests import guikit
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from gui.settings_menu import SettingsMenu
app = guikit.APP
app.setQuitOnLastWindowClosed(True)
owner = QWidget()
from types import SimpleNamespace
owner.win = SimpleNamespace(job=None, submission_running=False, pending_close=False, close_pending=False, gitflow=None, git_reason="업데이트 연결 없음")
layout = QVBoxLayout(owner)
from gui import kit
trigger = kit.button("설정")
layout.addWidget(trigger)
menu = SettingsMenu(owner, trigger)
owner.resize(760, 480)
owner.show()
closed = []
observed = []
app.lastWindowClosed.connect(lambda: closed.append(True))
def finish():
    menu.open_menu()
    owner.close()
QTimer.singleShot(0, menu.open_menu)
QTimer.singleShot(10, menu.dismiss)
QTimer.singleShot(30, lambda: observed.append((bool(closed), owner.isVisible(), menu.isVisible())))
QTimer.singleShot(50, finish)
QTimer.singleShot(2000, app.quit)
app.exec()
assert closed and not owner.isVisible() and not menu.isVisible()
assert observed == [(False, True, False)], observed
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=guikit.ROOT, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
