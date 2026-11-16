# -*- coding: utf-8 -*-
"""작은 회차 화면의 제목·편집기·실행 결과와 입력 보존을 확인함."""
from tests import guikit, test_gui

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QTextCursor
from PyQt6.QtTest import QSignalSpy

from gui import theme


class RoundLayoutTest(test_gui.GuiTest):
    def test_small_max_text_keeps_title_editor_and_result_separate(self):
        self.boot()
        self.make_round("r90", [self.first(kind="code", type="fill")])
        self.win.open_round("r90")
        self.idle()
        page = self.win.round_page
        editor, console = page.code_panel.editor, page.code_panel.console
        answer = "\n".join("value = %d" % number for number in range(30))
        editor.setPlainText(answer)
        page.flush()
        cursor = editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        changed = QSignalSpy(page.code_panel.changed)
        self.addCleanup(theme.set_mode, theme.state["mode"])

        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                theme.set_mode(mode)
                self.win.set_text("larger")
                self.win.resize(1440, 900)
                guikit.pump()
                wide = page.split.sizes()
                self.win.resize(760, 480)
                guikit.wait_until(lambda: page.bar.height() == theme.CONTROL["bottombar"] and page.listw.width() == 160)
                guikit.pump()
                self.assertEqual((self.win.width(), self.win.height()), (760, 480))
                self.assertGreaterEqual(page.item_title.height(), page.item_title.heightForWidth(page.item_title.width()))
                self.assertGreaterEqual(page.body.height(), 150)
                self.assertGreaterEqual(editor.height(), 70)
                self.assertGreaterEqual(console.height(), 50)
                self.assertFalse(editor.geometry().intersects(console.geometry()))
                self.assertLess(editor.geometry().bottom(), console.geometry().top())
                for widget in (editor, console):
                    self.assertTrue(widget.parentWidget().rect().contains(widget.geometry()))
                for button in (page.run_btn, page.prev_btn, page.next_btn, page.submit_btn):
                    self.assertTrue(page.rect().contains(button.rect().translated(button.mapTo(page, QPoint(0, 0)))))
                self.win.resize(1440, 900)
                guikit.wait_until(lambda: page.listw.width() == wide[0])
                guikit.pump()
                for actual, expected in zip(page.split.sizes(), wide):
                    self.assertLessEqual(abs(actual - expected), 1)
                self.assertEqual(editor.toPlainText(), answer)
                self.assertEqual(editor.textCursor().selectedText(), "value")
                self.assertEqual(page.current["answer"], answer)
                self.assertEqual(len(changed), 0)
                self.assertFalse(page.save_timer.isActive())

        self.win.resize(760, 480)
        guikit.wait_until(lambda: page.listw.width() == 160)
        guikit.pump()
        self.capture_widget = self.win
