# -*- coding: utf-8 -*-
"""수식 창의 실제 열기·닫기·작은 창과 원래 기록 보존을 확인함."""
from pathlib import Path

from tests import guikit
from tests.test_gui_ai import AiTest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from gui import ai_learn, motion, theme
from gui.ai_formula import FormulaBlock


class FormulaGuiTest(AiTest):
    real_bank = True

    def open_formula_step(self, size=(760, 480)):
        win = self.boot(size)
        win.go_ai()
        win.switch_ai_course("app")
        win.set_text("larger")
        self.assertTrue(win.open_ai_unit("a02", "a2d", 3))
        guikit.wait_until(lambda: win.ai_learn.pending_position is None)
        block, = win.ai_learn.view.findChildren(FormulaBlock)
        return win, block

    def stored(self):
        return {str(p.relative_to(self.tmp)): p.read_bytes() for p in Path(self.tmp).rglob("*")
                if p.is_file() and ("ai_home" in p.parts or "python_home" in p.parts or "submissions" in p.parts)}

    def test_close_escape_reopen_keep_stage_scroll_records_and_focus(self):
        win, block = self.open_formula_step((1280, 800))
        self.addCleanup(theme.set_mode, theme.state["mode"])
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            win.resize(760, 480)
            guikit.wait_until(lambda: win.ai_learn.pending_position is None)
            win.ai_learn.scroll.ensureWidgetVisible(block.button)
            guikit.pump()
            before = self.stored()
            at = win.ai_learn.scroll.verticalScrollBar().value()
            index = win.ai_learn.index
            for escape in (False, True):
                guikit.click(block.button)
                popup = block.dialog
                self.assertTrue(popup.isVisible())
                self.assertLessEqual(popup.width(), win.width())
                self.assertLessEqual(popup.height(), win.height())
                self.assertTrue(popup.screen().availableGeometry().contains(popup.frameGeometry()))
                self.assertTrue(block.close_button.visibleRegion().contains(block.close_button.rect()))
                self.assertFalse(block.check.answer.isVisible())
                block.panel.scroll.ensureWidgetVisible(block.check.button)
                guikit.click(block.check.button)
                self.assertTrue(block.check.answer.isVisible())
                guikit.click(block.check.button)
                if escape:
                    QTest.keyClick(popup, Qt.Key.Key_Escape)
                    guikit.pump()
                else:
                    guikit.click(block.close_button)
                self.assertFalse(popup.isVisible())
                self.assertIs(win.focusWidget(), block.button)
                self.assertEqual((index, at), (win.ai_learn.index, win.ai_learn.scroll.verticalScrollBar().value()))
                self.assertEqual(before, self.stored())

    def test_note_popup_keeps_existing_answer_and_selection(self):
        win = self.boot((760, 480))
        win.go_ai()
        win.switch_ai_course("app")
        win.ai.mark_read("a02", "a2d")
        win.open_ai_practice("unit", lesson="a02", unit="a2d")
        self.idle()
        quiz = win.ai_quiz
        while not quiz.fields:
            self.answer()
            guikit.click(quiz.next_btn)
        field = quiz.fields[0]
        field.setText("-12")
        field.setSelection(1, 2)
        guikit.wait_until(lambda: not win.input_timer.isActive() and win.focused_input is None)
        note = ai_learn.NoteDialog(win, "a02", "a2d/3")
        note.show()
        guikit.pump()
        block, = note.findChildren(FormulaBlock)
        before = self.stored()
        block.open_formula()
        guikit.pump()
        self.assertIs(block.dialog.parentWidget(), note)
        block.panel.scroll.ensureWidgetVisible(block.check.button)
        guikit.click(block.check.button)
        QTest.keyClick(block.dialog, Qt.Key.Key_Escape)
        guikit.pump()
        self.assertTrue(note.isVisible())
        self.assertEqual(("-12", "12"), (field.text(), field.selectedText()))
        self.assertEqual(before, self.stored())
        block.open_formula()
        guikit.pump()
        self.assertTrue(block.check.answer.isVisible())
        guikit.click(block.close_button)
        note.close()

    def test_new_figure_keeps_once_manual_and_reduced_motion_behavior(self):
        win, block = self.open_formula_step()
        self.addCleanup(setattr, motion, "enabled", motion.enabled)
        win.ai_learn.scroll.ensureWidgetVisible(block.button)
        guikit.click(block.button)
        picture = block.picture
        self.assertEqual(4, picture.count)
        self.assertFalse(picture.playing)
        picture.next()
        self.assertEqual(1, picture.frame())
        picture.prev()
        self.assertEqual(0, picture.frame())
        motion.enabled = True
        block.panel.scroll.verticalScrollBar().setValue(0)
        guikit.pump()
        picture._play_if_visible()
        self.assertTrue(picture.playing)
        guikit.wait_until(lambda: picture.frame() == 3 and not picture.playing, timeout=12)
        guikit.click(block.close_button)
        guikit.click(block.button)
        self.assertEqual(3, picture.frame())
        self.assertFalse(picture.playing)
        motion.enabled = False
        picture._play_if_visible()
        self.assertFalse(picture.playing)
        guikit.click(block.close_button)
