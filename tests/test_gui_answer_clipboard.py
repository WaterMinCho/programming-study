# -*- coding: utf-8 -*-
"""읽기 화면 아래 답안 칸의 클립보드 제한과 직접 입력을 확인함."""
import unittest

from tests import guikit
from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QDragEnterEvent, QDropEvent, QInputMethodEvent, QKeySequence
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QToolTip, QVBoxLayout, QWidget

from gui import ai_learn
from gui.guard import Guard
from gui.widgets import AnswerLine
from tests.test_gui_ai import AiTest


class AnswerClipboardTest(unittest.TestCase):
    def setUp(self):
        self.window = QWidget()
        self.window.setProperty("clipboard", True)
        self.column = QVBoxLayout(self.window)
        self.guard = Guard(self.window)
        guikit.APP.installEventFilter(self.guard)
        self.old_clipboard = QApplication.clipboard().text()

    def tearDown(self):
        QToolTip.hideText()
        guikit.APP.removeEventFilter(self.guard)
        self.window.close()
        self.window.deleteLater()
        QApplication.clipboard().setText(self.old_clipboard)
        guikit.pump()

    def test_reading_permission_does_not_allow_answer_shortcuts_menus_or_drops(self):
        for factory in (AnswerLine, lambda: ai_learn.Slot(ai_learn.code_font())):
            field = factory()
            self.column.addWidget(field)
            self.window.show()
            field.setFocus()
            field.setText("my-answer")
            field.setSelection(1, 3)
            before = (field.text(), field.cursorPosition(), field.selectedText())
            QApplication.clipboard().setText("outside-answer")
            blocked = QSignalSpy(field.blocked)
            for action in (QKeySequence.StandardKey.Copy, QKeySequence.StandardKey.Cut, QKeySequence.StandardKey.Paste,
                           QKeySequence.StandardKey.DeleteEndOfLine, QKeySequence.StandardKey.DeleteCompleteLine):
                for sequence in QKeySequence.keyBindings(action):
                    QTest.keySequence(field, sequence)
            QTest.keyClick(field, Qt.Key.Key_Insert, Qt.KeyboardModifier.ShiftModifier)
            for action in (field.copy, field.cut, field.paste):
                action()
            menu = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(2, 2))
            guikit.APP.sendEvent(field, menu)
            self.assertTrue(menu.isAccepted())
            QTest.mouseClick(field, Qt.MouseButton.MiddleButton)
            mime = QMimeData()
            mime.setText("outside-answer")
            for event in (QDragEnterEvent(QPoint(2, 2), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier),
                          QDropEvent(QPointF(2, 2), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)):
                guikit.APP.sendEvent(field, event)
                self.assertFalse(event.isAccepted())
            self.assertGreater(len(blocked), 5)
            self.assertEqual(before, (field.text(), field.cursorPosition(), field.selectedText()))
            self.assertEqual("outside-answer", QApplication.clipboard().text())

    def test_typing_composition_undo_and_saved_answer_restoration_still_work(self):
        field = AnswerLine()
        self.column.addWidget(field)
        self.window.show()
        field.setFocus()
        QTest.keyClicks(field, "answer")
        self.assertEqual("answer", field.text())
        QTest.keySequence(field, QKeySequence(QKeySequence.StandardKey.Undo))
        self.assertEqual("", field.text())
        QTest.keySequence(field, QKeySequence(QKeySequence.StandardKey.Redo))
        self.assertEqual("answer", field.text())
        event = QInputMethodEvent()
        event.setCommitString("학습")
        guikit.APP.sendEvent(field, event)
        self.assertEqual("answer학습", field.text())
        field.setText("saved-answer")
        QApplication.clipboard().setText("outside-answer")
        QTest.keySequence(field, QKeySequence(QKeySequence.StandardKey.Paste))
        self.assertEqual("saved-answer", field.text())
        field.setReadOnly(True)
        field.paste()
        self.assertEqual("saved-answer", field.text())

    def test_reading_text_copy_and_regular_identity_input_paste_are_unaffected(self):
        reader, identity = QLineEdit(), QLineEdit()
        reader.setText("example code")
        reader.setReadOnly(True)
        self.column.addWidget(reader)
        self.column.addWidget(identity)
        self.window.show()
        reader.selectAll()
        QTest.keySequence(reader, QKeySequence(QKeySequence.StandardKey.Copy))
        self.assertEqual("example code", QApplication.clipboard().text())
        QTest.keySequence(identity, QKeySequence(QKeySequence.StandardKey.Paste))
        self.assertEqual("example code", identity.text())


class LearningClipboardTest(AiTest):
    pc = True

    def test_late_created_level_questions_and_next_code_slot_keep_the_answer_policy(self):
        win = self.boot()
        old_clipboard = QApplication.clipboard().text()
        self.addCleanup(QApplication.clipboard().setText, old_clipboard)
        self.addCleanup(QToolTip.hideText)
        win.open_ai_unit("i90", "90a", 2)
        guikit.wait_until(lambda: win.ai_learn.pending_position is None)
        levels = win.ai_learn.view.findChildren(ai_learn.LevelsBlock)[0]
        self.assertEqual([], levels.body.findChildren(ai_learn.RecallBlock))
        win.ai_learn.scroll.ensureWidgetVisible(levels.row)
        guikit.pump()
        guikit.click(levels.row)
        recalls = levels.body.findChildren(ai_learn.RecallBlock)
        self.assertEqual(3, len(recalls))
        for recall in recalls:
            recall.field.setText("draft")
            QApplication.clipboard().setText("outside-answer")
            QTest.keySequence(recall.field, QKeySequence(QKeySequence.StandardKey.Paste))
            self.assertEqual("draft", recall.field.text())
        self.assertEqual([], self.log("recall"))
        win.open_ai_unit("pc", "18a", 3)
        rotate = win.ai_learn.view.findChildren(ai_learn.RotateBlock)[0]
        previous = None
        for count in range(2):
            field = rotate.field()
            self.assertIsNot(previous, field)
            self.assertFalse(field.isReadOnly())
            field.setText("draft")
            QTest.keySequence(field, QKeySequence(QKeySequence.StandardKey.Paste))
            self.assertEqual("draft", field.text())
            self.assertEqual(count, len(self.log("recall")))
            guikit.click(rotate.check_btn)
            guikit.click(rotate.next_btn)
            previous = field
