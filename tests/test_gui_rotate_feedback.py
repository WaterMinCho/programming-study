# -*- coding: utf-8 -*-
"""회전 빈칸의 해설 노출·초기화·저장 실패와 화면 배치를 offscreen에서 확인함."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from tests import guikit  # noqa: E402
from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402
from gui import ai_learn, kit, theme  # noqa: E402
from session import SessionError  # noqa: E402
from tests.test_ai_rotate_feedback import RotateFeedbackBase  # noqa: E402


class RotateFeedbackGuiTest(RotateFeedbackBase):
    def setUp(self):
        super().setUp()
        old_text, old_mode = theme.state["text"], theme.state["mode"]
        self.addCleanup(theme.set_text, old_text)
        self.addCleanup(theme.set_mode, old_mode)
        theme.set_text("normal")
        self.win = SimpleNamespace(ai=self.sess, ask=mock.Mock())
        self.ctx = ai_learn.Ctx(self.win, "pc", "18a")
        self.host = None

    def open_block(self, readonly=False, size=(640, 500)):
        self.ctx.readonly = readonly
        self.host = QWidget()
        self.host.setProperty("ui", "2")
        self.addCleanup(self.close_host)
        inner = QWidget()
        column = kit.box(inner, (24, 24, 24, 24), 16)
        before = QWidget()
        before.setFixedHeight(180)
        column.addWidget(before)
        self.block = ai_learn.RotateBlock(self.rotate_block(), self.ctx)
        column.addWidget(self.block)
        after = QWidget()
        after.setFixedHeight(800)
        column.addWidget(after)
        self.scroll = kit.scroll(inner)
        kit.box(self.host).addWidget(self.scroll)
        self.host.resize(*size)
        self.host.show()
        self.host.activateWindow()
        guikit.pump()
        if not readonly:
            self.scroll.ensureWidgetVisible(self.block.field(), 0, 0)
            self.block.field().setFocus()
            guikit.pump()
        return self.block

    def close_host(self):
        if self.host is not None:
            self.host.close()
            self.host.deleteLater()
            self.host = None
            guikit.pump()

    def submit(self, value):
        field = self.block.field()
        field.setText(value)
        QTest.keyClick(field, Qt.Key.Key_Return)
        guikit.pump()

    def test_explanation_is_hidden_before_answer_and_shown_below_both_results(self):
        block = self.open_block()
        self.assertTrue(block.explanation.isHidden())
        self.assertEqual("", block.explanation.text())
        self.submit("train")
        self.assertTrue(block.explanation.isVisible())
        self.assertEqual(self.entries["pc-k01"]["explain"], block.explanation.text())
        self.assertGreaterEqual(block.explanation.mapTo(block, QPoint()).y(),
                                block.answer.mapTo(block, QPoint(0, block.answer.height())).y())
        QTest.keyClick(block.field(), Qt.Key.Key_Return)
        guikit.pump()
        self.assertEqual("", block.explanation.text())
        self.assertTrue(block.explanation.isHidden())
        self.assertIs(QApplication.focusWidget(), block.field())
        self.submit("step")
        self.assertFalse(block.result_ok)
        self.assertEqual(self.entries["pc-k02"]["explain"], block.explanation.text())
        self.assertTrue(block.explanation.isVisible())

    def test_empty_explanation_and_completion_clear_previous_text(self):
        self.entries["pc-k02"].pop("explain")
        self.entries["pc-k03"]["explain"] = ""
        block = self.open_block()
        for slot in list(block.queue):
            self.submit(self.entries[slot]["answer"][0])
            if slot in ("pc-k02", "pc-k03"):
                self.assertTrue(block.explanation.isHidden())
                self.assertEqual("", block.explanation.text())
            block.advance()
            guikit.pump()
            self.assertTrue(block.explanation.isHidden())
            self.assertEqual("", block.explanation.text())
        self.assertTrue(block.done.isVisible())

    def test_empty_input_and_write_failure_keep_feedback_hidden_and_allow_retry(self):
        block = self.open_block()
        self.submit("")
        self.assertTrue(block.empty_note.isVisible())
        self.assertTrue(block.explanation.isHidden())
        self.assertEqual([], self.sess.record.log)
        with mock.patch.object(self.sess, "_append", side_effect=SessionError("저장 오류")):
            self.submit("train")
        self.win.ask.assert_called_once()
        self.assertIsNone(block.result_ok)
        self.assertFalse(block.field().isReadOnly())
        self.assertTrue(block.check_btn.isVisible())
        self.assertTrue(block.answer.isHidden())
        self.assertTrue(block.explanation.isHidden())
        self.assertEqual("", block.explanation.text())
        self.assertEqual([], self.sess.record.log)
        self.submit("train")
        self.assertTrue(block.explanation.isVisible())
        self.assertEqual(1, len(self.sess.record.log))

    def test_readonly_does_not_expose_feedback_or_write(self):
        block = self.open_block(readonly=True)
        shown = [label.text() for label in block.findChildren(ai_learn.RichPara) if label.isVisible()]
        self.assertNotIn(self.entries["pc-k01"]["explain"], shown)
        self.assertEqual([], self.sess.record.log)
        self.assertEqual([], block.slots.fields)

    def test_feedback_preserves_keyboard_focus_scroll_and_input_position(self):
        block = self.open_block()
        field = block.field()
        self.scroll.verticalScrollBar().setValue(140)
        guikit.pump()
        before = (self.scroll.verticalScrollBar().value(), field.mapTo(self.scroll.viewport(), QPoint()))
        self.submit("train")
        after = (self.scroll.verticalScrollBar().value(), field.mapTo(self.scroll.viewport(), QPoint()))
        self.assertIs(QApplication.focusWidget(), field)
        self.assertEqual(before, after)

    def test_small_window_large_text_and_both_schemes_keep_explanation_readable(self):
        path = Path(guikit.ROOT) / "ai" / "patterns" / "S1.json"
        existing = json.loads(path.read_text(encoding="utf-8"))["slots"][0]["explain"]
        self.entries["pc-k01"]["explain"] = existing
        for scheme in ("light", "dark"):
            for text in ("normal", "larger"):
                with self.subTest(scheme=scheme, text=text):
                    theme.set_mode(scheme)
                    theme.set_text(text)
                    block = self.open_block(size=(600, 440))
                    self.submit("train")
                    explanation = block.explanation
                    self.assertEqual(existing, explanation.text())
                    self.assertTrue(explanation.wordWrap())
                    self.assertEqual(theme.TYPE["learn_body"][0], explanation.font().pixelSize())
                    self.assertGreaterEqual(explanation.height(), explanation.heightForWidth(explanation.width()))
                    viewport = self.scroll.viewport()
                    self.assertLessEqual(explanation.width(), viewport.width())
                    self.scroll.ensureWidgetVisible(explanation, 0, 0)
                    guikit.pump()
                    self.assertLessEqual(explanation.mapTo(viewport, QPoint(0, explanation.height())).y(), viewport.height())
                    self.close_host()


if __name__ == "__main__":
    unittest.main()
