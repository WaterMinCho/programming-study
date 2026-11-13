# -*- coding: utf-8 -*-
"""대기 조회 중 화면 유지와 팝업의 하단 동작·긴 본문을 확인함."""
import threading
import time
import unittest
from unittest import mock

from tests import guikit
from PyQt6.QtCore import QEvent, QObject, QPoint
from PyQt6.QtWidgets import QWidget

from gui import dialogs, theme
from gui.identity import IdentityDialog
from learning_data.collection import CollectionError


class Host(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(760, 480)
        self.open_url = mock.Mock()


class IdentityFixture:
    def __init__(self):
        self.pending_token = None
        self.device = {"verification_uri": "https://github.com/login/device", "interval": 5}
        self.poll = mock.Mock(return_value={"pending": True, "interval": 5})
        self.begin = mock.Mock()

    def cancel(self):
        self.pending_token = self.device = None


class EnabledChanges(QObject):
    def __init__(self):
        super().__init__()
        self.values = []

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.EnabledChange:
            self.values.append(widget.isEnabled())
        return False


class DialogTest(unittest.TestCase):
    def setUp(self):
        self.host = Host()
        self.host.show()
        self.dialogs = []
        self.gates = []
        self.previous_step, self.previous_mode = theme.state["text"], theme.state["mode"]

    def tearDown(self):
        for gate in self.gates:
            gate.set()
        for dialog in self.dialogs:
            if getattr(dialog, "job", None) is not None:
                guikit.wait_until(lambda: dialog.job is None)
            dialog.close()
        self.host.close()
        theme.set_text(self.previous_step)
        theme.set_mode(self.previous_mode)
        guikit.pump()

    def identity(self, waiting=True):
        identity = IdentityFixture()
        dialog = IdentityDialog(self.host, identity)
        self.dialogs.append(dialog)
        dialog.show()
        if waiting:
            dialog.started({"user_code": "ABCD-EFGH", "expires_in": 900,
                            "verification_uri": "https://github.com/login/device"})
            dialog.timer.stop()
        guikit.pump()
        self.capture_widget = dialog
        return dialog

    def finish_poll(self, dialog):
        guikit.wait_until(lambda: dialog.job is None)
        dialog.timer.stop()
        guikit.pump()

    def assert_footer(self, dialog):
        for button in (dialog.copy, dialog.cancel_button, dialog.begin_button):
            if not button.isVisible():
                continue
            rect = button.geometry().translated(button.parentWidget().mapTo(dialog, QPoint()))
            self.assertTrue(dialog.rect().contains(rect), (button.text(), rect, dialog.size()))
            self.assertGreaterEqual(button.width(), button.sizeHint().width())
            self.assertGreaterEqual(rect.top(), dialog.shell.scroll.geometry().bottom())

    def test_pending_preserves_pixels_focus_selection_scroll_and_actions(self):
        theme.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            dialog = self.identity()
            dialog.details_button.setChecked(True)
            guikit.pump()
            dialog.shell.scroll.verticalScrollBar().setValue(dialog.shell.scroll.verticalScrollBar().maximum())
            dialog.code.setSelection(0, 4)
            dialog.begin_button.setFocus()
            guikit.pump()
            changes = EnabledChanges()
            dialog.begin_button.installEventFilter(changes)
            position = dialog.shell.scroll.verticalScrollBar().value()
            before = dialog.begin_button.grab().toImage()
            selection = dialog.code.selectedText()
            geometry = dialog.begin_button.geometry()
            for interval in (5, 10, 10):
                gate = threading.Event()
                self.gates.append(gate)
                dialog.identity.poll.side_effect = lambda: (gate.wait(10), {"pending": True, "interval": interval})[1]
                dialog.poll()
                guikit.pump()
                self.assertTrue(dialog.begin_button.isEnabled())
                self.assertIs(guikit.APP.focusWidget(), dialog.begin_button)
                self.assertEqual(before, dialog.begin_button.grab().toImage())
                gate.set()
                self.finish_poll(dialog)
                self.assertEqual(position, dialog.shell.scroll.verticalScrollBar().value())
                self.assertEqual(selection, dialog.code.selectedText())
                self.assertEqual(geometry, dialog.begin_button.geometry())
                self.assertIs(guikit.APP.focusWidget(), dialog.begin_button)
                self.assert_footer(dialog)
            self.assertEqual([], changes.values)
            dialog.close()
        self.capture_widget = self.identity()

    def test_code_copy_is_a_footer_action_and_expiry_removes_stale_code(self):
        dialog = self.identity(False)
        self.assertTrue(dialog.copy.isHidden())
        dialog.started({"user_code": "ABCD-EFGH", "expires_in": 900,
                        "verification_uri": "https://github.com/login/device"})
        dialog.timer.stop()
        guikit.pump()
        self.assertTrue(dialog.copy.isVisible())
        self.assert_footer(dialog)
        clipboard = mock.Mock()
        with mock.patch("gui.identity.QApplication.clipboard", return_value=clipboard):
            guikit.click(dialog.copy)
            clipboard.setText.assert_called_once_with("ABCD-EFGH")
            self.assertTrue(dialog.isVisible())
            dialog.copy.setFocus()
            dialog.expires = time.monotonic() - 1
            dialog.poll()
            self.assertTrue(dialog.copy.isHidden())
            self.assertTrue(dialog.code_panel.isHidden())
            self.assertIs(guikit.APP.focusWidget(), dialog.begin_button)
            dialog.copy_code()
            clipboard.setText.assert_called_once()

    def test_recoverable_error_keeps_code_but_cancelled_flow_hides_it(self):
        dialog = self.identity()
        dialog.identity.poll.side_effect = CollectionError("연결을 확인해 주세요.")
        dialog.poll()
        self.finish_poll(dialog)
        self.assertTrue(dialog.copy.isVisible())
        dialog.identity.cancel()
        dialog.poll()
        self.finish_poll(dialog)
        self.assertTrue(dialog.copy.isHidden())
        self.assertTrue(dialog.code_panel.isHidden())

    def test_pending_token_can_finish_after_device_code_expiry(self):
        dialog = self.identity()
        dialog.identity.pending_token = "synthetic-pending-token"
        dialog.expires = time.monotonic() - 1
        dialog.identity.poll.return_value = {"verified": True}
        dialog.begin()
        self.finish_poll(dialog)
        self.assertEqual(dialog.DialogCode.Accepted, dialog.result())
        dialog.identity.begin.assert_not_called()

    def test_close_during_pending_work_ignores_a_late_success(self):
        dialog = self.identity()
        gate = threading.Event()
        self.gates.append(gate)
        dialog.identity.poll.side_effect = lambda: (gate.wait(10), {"verified": True})[1]
        finished = []
        dialog.finished.connect(finished.append)
        dialog.poll()
        dialog.reject()
        self.assertTrue(dialog.pending_close)
        gate.set()
        self.finish_poll(dialog)
        self.assertEqual([dialog.DialogCode.Rejected], finished)
        self.assertFalse(dialog.timer.isActive())

    def test_identity_footer_and_code_fit_max_text_both_themes(self):
        theme.set_text("larger")
        for size in ((760, 480), (1024, 700), (1280, 800)):
            self.host.resize(*size)
            for mode in ("light", "dark"):
                theme.set_mode(mode)
                dialog = self.identity()
                self.assertLessEqual(dialog.width(), self.host.width())
                self.assertLessEqual(dialog.height(), self.host.height())
                self.assert_footer(dialog)
                viewport = dialog.shell.scroll.viewport()
                self.assertTrue(viewport.rect().contains(dialog.code.geometry().translated(dialog.code.parentWidget().mapTo(viewport, QPoint()))))
                self.assertEqual(0, dialog.shell.scroll.horizontalScrollBar().maximum())
                dialog.close()
        self.host.resize(760, 480)
        self.capture_widget = self.identity()

    def test_long_message_keeps_all_actions_outside_body_scroll(self):
        theme.set_text("larger")
        dialog = dialogs.MessageDialog(self.host, "학습 기록을 삭제할까요?", "기록과 답안은 서로 구분합니다. " * 45,
            buttons=(("이어서 학습", "continue"), ("닫기", "close"), ("기록 삭제", "delete", "danger_text")), detail="진단 내용")
        self.dialogs.append(dialog)
        dialog.show()
        guikit.pump()
        self.assertLessEqual(dialog.height(), self.host.height())
        self.assertGreater(dialog.shell.scroll.verticalScrollBar().maximum(), 0)
        for button in dialog.buttons.values():
            rect = button.geometry().translated(button.parentWidget().mapTo(dialog, QPoint()))
            self.assertTrue(dialog.rect().contains(rect))
            self.assertFalse(button.isDefault())
        self.assertEqual("danger_text", dialog.buttons["delete"].objectName())
        self.capture_widget = dialog
