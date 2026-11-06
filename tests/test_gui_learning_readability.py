"""학습 본문과 그림을 실제 배치에서 큰 글자로 확인함."""
import os
import unittest

from tests import guikit
from tests.test_gui_learning_state import LearningWindow

from PyQt6.QtGui import QFontInfo
from gui import ai_learn, kit, theme
from gui.docview import TextPiece


class LearningReadabilityTest(unittest.TestCase):
    def setUp(self):
        self.assertIn(guikit.APP.platformName(), ("offscreen", "windows") if os.name == "nt" else ("offscreen",))
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])

    def close(self, widget):
        widget.close()
        widget.deleteLater()
        guikit.pump()

    def test_markdown_questions_and_input_use_the_same_larger_reading_size(self):
        theme.set_text("large")
        win = LearningWindow()
        self.addCleanup(self.close, win)
        win.resize(1280, 900)
        win.show()
        win.page.load("test", "one", 2)
        guikit.wait_until(lambda: win.page.pending_position is None)
        guikit.pump(100)
        piece = win.page.view.findChildren(TextPiece)[0]
        block = piece.document().begin()
        fragment = block.begin().fragment()
        font = fragment.charFormat().font().resolve(piece.document().defaultFont())
        recall = win.page.view.findChildren(ai_learn.RecallBlock)[0]
        reading = recall.field.font().pixelSize()
        self.assertEqual(QFontInfo(font).pixelSize(), reading)
        self.assertGreater(reading, win.page.next_btn.font().pixelSize())
        self.assertGreater(win.page.view.width(), kit.READ_MIN)
        theme.set_text("larger")
        kit.refont(win)
        win.page.restyle()
        guikit.wait_until(lambda: win.page.pending_position is None)
        guikit.pump(80)
        self.assertGreater(recall.field.font().pixelSize(), reading)
        self.assertGreater(recall.findChildren(ai_learn.RichPara)[0].line, recall.field.font().pixelSize())
        recall.field.setText("정답")
        recall.check()
        self.assertEqual(recall.field.font().pixelSize(), theme.TYPE["learn_body"][0])

    def test_learning_picture_grows_with_text_and_zoom_preserves_the_larger_size(self):
        theme.set_text("normal")
        path = os.path.join(guikit.ROOT, "ai", "learn", "l01", "assets", "1a-1.png")
        figure = ai_learn.AiFigure(path, "입력과 예측의 관계입니다.")
        self.addCleanup(self.close, figure)
        figure.resize(1000, 800)
        figure.show()
        guikit.pump(60)
        before = figure.picture.pixmap().deviceIndependentSize().width()
        theme.set_text("larger")
        kit.refont(figure)
        figure.draw()
        guikit.pump(60)
        after = figure.picture.pixmap().deviceIndependentSize().width()
        self.assertGreater(after, before)
        figure.resize(400, 800)
        guikit.pump(50)
        self.assertTrue(figure.zoom_btn.isVisible())
        figure.open_dialog()
        self.addCleanup(self.close, figure.dialog)
        guikit.pump(60)
        zoomed = figure.dialog.picture.pixmap().deviceIndependentSize()
        self.assertGreater(zoomed.width(), figure.picture.pixmap().deviceIndependentSize().width())
        self.assertAlmostEqual(zoomed.width() / zoomed.height(), figure.source.width() / figure.source.height(), delta=0.01)
