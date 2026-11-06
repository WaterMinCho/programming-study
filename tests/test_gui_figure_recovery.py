import os
import tempfile
import unittest
from pathlib import Path

from tests import guikit
from tests.test_gui_docview import GIF, PNG
from tests.test_gui_learning_state import LearningWindow, PROSE, recall

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtWidgets import QScrollArea

from gui import ai_learn, kit, theme
from gui.docview import FigureView, TextPiece


class FigureRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.assertIn(guikit.APP.platformName(), ("offscreen", "windows") if os.name == "nt" else ("offscreen",))
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.path = os.path.join(self.folder.name, "figure.gif")

    def write(self, data):
        with open(self.path, "wb") as stream:
            stream.write(data)

    def close(self, widget):
        widget.close()
        widget.deleteLater()
        guikit.pump()

    def shown(self, figure, width=600):
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(figure)
        area.resize(width, 440)
        area.show()
        self.addCleanup(self.close, area)
        guikit.pump(80)
        return area

    def block(self, path=None):
        return {"kind": "figure", "file": "assets/figure.gif", "path": path or self.path,
                "caption": "그림의 캡션입니다.", "content": "그림의 대체 설명입니다.",
                "frames": [{"text": "%d장 설명입니다." % n, "ms": 1000} for n in (1, 2, 3)]}

    def test_missing_image_keeps_alt_and_failed_retry_does_not_add_widgets(self):
        figure = FigureView(self.path, "전달할 그림 설명입니다.")
        self.shown(figure)
        self.assertFalse(figure.available)
        self.assertTrue(figure.error_box.isVisible())
        self.assertIn("전달할 그림 설명입니다.", figure.error_description.text())
        count = len(figure.findChildren(type(figure.retry_btn)))
        for _ in range(3):
            guikit.click(figure.retry_btn)
            self.assertFalse(figure.available)
            self.assertEqual(len(figure.findChildren(type(figure.retry_btn))), count)
            self.assertTrue(figure.error_box.isVisible())
            self.assertFalse(figure.picture.isVisible() or figure.zoom_btn.isVisible() or figure.timer.isActive())

    def test_retry_reads_restored_png_in_the_same_widget(self):
        figure = FigureView(Path(self.path), "그림의 설명입니다.")
        self.shown(figure)
        self.write(PNG)
        guikit.click(figure.retry_btn)
        self.assertTrue(figure.available)
        self.assertFalse(figure.source.isNull())
        self.assertEqual(figure.data, PNG)
        self.assertIsNone(figure.controls)
        self.assertFalse(figure.error_box.isVisible())
        self.assertEqual(figure.caption.text(), "그림의 설명입니다.")
        self.assertTrue(figure.caption.isVisible())
        self.assertTrue(figure.hasFocus())

    def test_corrupt_png_and_gif_show_fallback_instead_of_an_empty_picture(self):
        for data in (b"not an image", b"GIF89a\x00broken"):
            with self.subTest(data=data):
                self.write(data)
                figure = ai_learn.figure(self.block())
                self.shown(figure)
                self.assertFalse(figure.available)
                self.assertTrue(figure.error_box.isVisible())
                self.assertIn("그림의 캡션입니다.", figure.error_description.text())
                self.assertIn("그림의 대체 설명입니다.", figure.error_description.text())
                for n in (1, 2, 3):
                    self.assertIn("%d장 설명입니다." % n, figure.error_description.text())
                self.assertFalse(figure.frame_text.isVisible() or figure.timer.isActive())
                self.assertEqual(figure.error_box.toolTip(), "assets/figure.gif")

    def test_restored_gif_keeps_frame_descriptions_and_does_not_autoplay(self):
        figure = ai_learn.figure(self.block())
        self.shown(figure)
        self.write(GIF)
        guikit.click(figure.retry_btn)
        self.assertTrue(figure.available)
        self.assertEqual((figure.frame(), figure.count, figure.frame_text.text()), (0, 3, "1장 설명입니다."))
        self.assertTrue(figure.frame_text.isVisible())
        self.assertFalse(figure.error_box.isVisible() or figure.playing or figure.timer.isActive())
        figure.next()
        self.assertEqual((figure.frame(), figure.frame_text.text()), (1, "2장 설명입니다."))
        self.assertEqual((figure.prev_btn.text(), figure.next_btn.text()), ("이전 장", "다음 장"))

    def test_revisit_retry_opens_the_last_frame(self):
        figure = ai_learn.figure(self.block(), last=True)
        self.shown(figure)
        self.write(GIF)
        guikit.click(figure.retry_btn)
        self.assertEqual((figure.frame(), figure.frame_text.text()), (2, "3장 설명입니다."))
        self.assertFalse(figure.playing)

    def test_small_column_large_text_keeps_description_and_retry_readable(self):
        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                theme.set_mode(mode)
                theme.set_text("larger")
                figure = ai_learn.figure(dict(self.block(), content="설명이 길어도 문장을 자르지 않습니다. " * 20))
                area = self.shown(figure)
                figure.setFixedWidth(160)
                kit.refont(area)
                guikit.pump(80)
                area.ensureWidgetVisible(figure.retry_btn, 8, 8)
                guikit.pump(30)
                button = figure.retry_btn
                self.assertGreaterEqual(button.width(), button.sizeHint().width())
                self.assertGreaterEqual(figure.error_description.height(),
                                        figure.error_description.heightForWidth(figure.error_description.width()))
                self.assertTrue(area.viewport().rect().contains(QRect(button.mapTo(area.viewport(), QPoint()), button.size())))

    def learning(self):
        second = os.path.join(self.folder.name, "second.gif")
        with open(second, "wb") as stream:
            stream.write(GIF)
        win = LearningWindow()
        self.addCleanup(self.close, win)
        win.ai.units["one"][1]["blocks"] = [self.block(), self.block(second), recall(),
                                                  {"kind": "text", "markdown": PROSE}]
        win.resize(760, 480)
        win.show()
        win.activateWindow()
        win.page.load("test", "one", 2)
        self.settle(win.page)
        return win

    def settle(self, page):
        guikit.wait_until(lambda: page.pending_position is None and not page.position_timer.isActive())
        guikit.pump(80)

    def test_recovery_keeps_draft_focus_and_separate_frame_positions_on_return(self):
        win = self.learning()
        page = win.page
        field = page.view.findChildren(ai_learn.RecallBlock)[0].field
        field.setText("한글 초안입니다.")
        field.setFocus()
        field.setSelection(6, -3)
        page.scroll.ensureWidgetVisible(field, 16, 16)
        self.settle(page)
        expected = field.text(), field.cursorPosition(), field.selectionStart(), field.selectedText()
        figures = page.view.findChildren(ai_learn.AiFigure)
        self.write(GIF)
        self.assertTrue(figures[0].reload())
        self.settle(page)
        self.assertTrue(field.hasFocus())
        self.assertEqual((field.text(), field.cursorPosition(), field.selectionStart(), field.selectedText()), expected)
        viewport = page.scroll.viewport()
        self.assertTrue(viewport.rect().contains(QRect(field.mapTo(viewport, QPoint()), field.size())))
        figures[0].go(2)
        figures[1].go(1)
        page.move(1)
        self.settle(page)
        page.move(-1)
        self.settle(page)
        self.assertEqual([figure.frame() for figure in page.view.findChildren(ai_learn.AiFigure)], [2, 1])
        field = page.view.findChildren(ai_learn.RecallBlock)[0].field
        self.assertEqual((field.text(), field.cursorPosition(), field.selectionStart(), field.selectedText()), expected)
        self.assertFalse([call for call in win.ai.calls if call[0] != "step"])

    def test_recovery_preserves_the_reading_text_below_the_figure(self):
        win = self.learning()
        page = win.page
        piece = page.view.findChildren(TextPiece)[-1]
        bar = page.scroll.verticalScrollBar()
        top = piece.mapTo(page.scroll.widget(), QPoint()).y()
        bar.setValue(top + round(piece.height() * 0.4))
        win.page.setFocus(Qt.FocusReason.OtherFocusReason)
        self.settle(page)
        before = piece.mapTo(page.scroll.viewport(), QPoint()).y()
        self.write(GIF)
        self.assertTrue(page.view.findChildren(ai_learn.AiFigure)[0].reload())
        self.settle(page)
        self.assertAlmostEqual(piece.mapTo(page.scroll.viewport(), QPoint()).y(), before, delta=2)

    def test_retry_button_does_not_pass_focus_through_the_recall_input(self):
        win = self.learning()
        page = win.page
        field = page.view.findChildren(ai_learn.RecallBlock)[0].field
        figure = page.view.findChildren(ai_learn.AiFigure)[0]
        field.setText("입력한 문장 일부를 선택했습니다.")
        field.setSelection(13, -7)
        page.scroll.ensureWidgetVisible(figure.retry_btn, 12, 16)
        figure.retry_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        self.settle(page)
        expected = field.text(), field.cursorPosition(), field.selectionStart(), field.selectedText()
        guikit.click(figure.retry_btn)
        self.settle(page)
        self.assertTrue(figure.retry_btn.hasFocus())
        self.write(GIF)
        guikit.click(figure.retry_btn)
        self.settle(page)
        self.assertTrue(figure.available and figure.hasFocus())
        self.assertEqual((field.text(), field.cursorPosition(), field.selectionStart(), field.selectedText()), expected)

    def test_lazily_built_figure_keeps_reading_position_before_and_after_a_step_return(self):
        for data in (PNG, GIF):
            for returned in (False, True):
                with self.subTest(data=data[:4], returned=returned):
                    if os.path.exists(self.path):
                        os.remove(self.path)
                    win = LearningWindow()
                    self.addCleanup(self.close, win)
                    level = dict(recall(), level=7, text=PROSE, figure=self.block())
                    win.ai.units["one"][1]["blocks"] = [
                        {"kind": "levels", "concept": "그림 복구", "levels": [level]},
                        {"kind": "text", "markdown": PROSE}]
                    win.resize(760, 480)
                    win.show()
                    win.activateWindow()
                    page = win.page
                    page.load("test", "one", 2)
                    self.settle(page)
                    page.view.findChildren(ai_learn.LevelsBlock)[0].row.set_opened(True)
                    self.settle(page)
                    if returned:
                        page.move(1)
                        self.settle(page)
                        page.move(-1)
                        self.settle(page)
                    block = page.view.findChildren(ai_learn.LevelsBlock)[0]
                    piece = block.findChildren(TextPiece)[0]
                    top = piece.mapTo(page.scroll.widget(), QPoint()).y()
                    page.scroll.verticalScrollBar().setValue(top + round(piece.height() * 0.4))
                    page.setFocus(Qt.FocusReason.OtherFocusReason)
                    self.settle(page)
                    before = piece.mapTo(page.scroll.viewport(), QPoint()).y()
                    calls = list(win.ai.calls)
                    self.write(data)
                    self.assertTrue(block.findChildren(ai_learn.AiFigure)[0].reload())
                    self.settle(page)
                    self.assertAlmostEqual(piece.mapTo(page.scroll.viewport(), QPoint()).y(), before, delta=2)
                    self.assertEqual(win.ai.calls, calls)
