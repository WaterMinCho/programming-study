"""학습 본문과 그림을 실제 배치에서 큰 글자로 확인함."""
import os
import unittest

from tests import guikit
from tests.test_gui_learning_state import LearningWindow

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QFontInfo
from gui import ai_learn, kit, theme
from gui.docview import TextPiece
import mdlite


class LearningReadabilityTest(unittest.TestCase):
    def setUp(self):
        self.assertIn(guikit.APP.platformName(), ("offscreen", "windows") if os.name == "nt" else ("offscreen",))
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])

    def close(self, widget):
        widget.close()
        widget.deleteLater()
        guikit.pump()

    def test_narrow_comparison_keeps_each_value_with_its_column_and_row(self):
        theme.set_text("larger")
        blocks = mdlite.parse("| | 지도학습 | 비지도학습 | 자기지도학습 | 강화학습 |\n"
            "|---|---|---|---|---|\n| 주는 것 | 입력과 정답 | 정답 없는 데이터 | 데이터에서 만든 정답 | 행동 뒤 점수 |\n"
            "| 예 | 체중 예측 | 군집 나누기 | 가린 부분 맞히기 | 게임 |")
        piece = TextPiece(mdlite.blocks_html(blocks), theme.learning_css(), blocks)
        self.addCleanup(self.close, piece)
        piece.resize(600, 600)
        piece.show()
        guikit.pump(60)
        self.assertTrue(piece.compact)
        plain = piece.toPlainText()
        for title, value in (("지도학습", "입력과 정답"), ("비지도학습", "정답 없는 데이터"),
                             ("자기지도학습", "데이터에서 만든 정답"), ("강화학습", "행동 뒤 점수")):
            section = plain.split(title + "\n", 1)[1]
            self.assertTrue(section.startswith("주는 것: " + value))
        self.assertIn("예: 게임", plain)
        self.assertLessEqual(piece.document().size().width(), piece.viewport().width()+1)
        piece.resize(1500, piece.height())
        guikit.pump(60)
        self.assertFalse(piece.compact)
        self.assertEqual([(t.rows(), t.columns()) for t in piece.grid_tables()], [(3, 5)])
        theme.set_text("normal")
        piece.restyle(theme.learning_css())
        piece.resize(500, piece.height())
        guikit.pump(60)
        self.assertTrue(piece.compact)
        self.assertIn("주는 것: 행동 뒤 점수", piece.toPlainText())

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
        self.assertGreater(win.page.view.width(), 1000)
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

    def test_comparison_reflow_keeps_the_active_answer_on_return(self):
        theme.set_text("larger")
        win = LearningWindow()
        self.addCleanup(self.close, win)
        table = "| | 지도학습 | 비지도학습 | 자기지도학습 | 강화학습 |\n|---|---|---|---|---|\n| 자료 | 입력과 정답 | 정답 없는 데이터 | 만든 정답 | 점수 |"
        win.ai.units["one"][1]["blocks"].insert(0, {"kind": "text", "markdown": table})
        win.resize(2000, 900)
        win.show()
        win.activateWindow()
        win.page.load("test", "one", 2)
        guikit.wait_until(lambda: win.page.pending_position is None)
        field = win.page.view.findChildren(ai_learn.RecallBlock)[0].field
        field.setText("입력 중인 답안")
        field.setFocus()
        field.setSelection(3, 2)
        win.page.scroll.ensureWidgetVisible(field)
        win.resize(760, 480)
        guikit.pump(150)
        win.page.show_step(0)
        win.page.show_step(1)
        guikit.wait_until(lambda: win.page.pending_position is None)
        guikit.pump(80)
        field = win.page.view.findChildren(ai_learn.RecallBlock)[0].field
        self.assertEqual((field.text(), field.selectedText()), ("입력 중인 답안", "중인"))
        self.assertTrue(field.hasFocus())
        self.assertTrue(any(piece.compact for piece in win.page.view.findChildren(TextPiece)))
        viewport = win.page.scroll.viewport()
        rect = QRect(field.mapTo(viewport, QPoint()), field.size())
        self.assertTrue(viewport.rect().contains(rect), (rect, viewport.rect(), win.page.scroll.verticalScrollBar().value()))

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
