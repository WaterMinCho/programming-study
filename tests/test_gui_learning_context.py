# -*- coding: utf-8 -*-
"""첫 글줄 정렬과 학습 흐름 그림의 좁은 창 배치를 확인함."""
import json
from pathlib import Path
import unittest

from tests import guikit
from gui import kit, theme
from gui.ai_learn import OptionRow, RevealBlock
from gui.learning_context import ContextHead, LearningContext
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtWidgets import QWidget


class LearningLayoutTest(unittest.TestCase):
    def test_inline_marks_follow_the_first_line_after_wrapping_and_refont(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        root = kit.page(QWidget())
        box = kit.box(root, (24, 24, 24, 24), 24)
        for text in ("파라미터를 갱신합니다.", "파라미터를 갱신합니다. " * 8):
            box.addWidget(RevealBlock.line("정답", "success", text))
            box.addWidget(OptionRow(text))
        box.addStretch()
        root.resize(600, 1200)
        root.show()
        self.addCleanup(root.close)
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(root)
            guikit.pump()
            for pair in root.findChildren(kit.FirstLine):
                if pair.mark.isHidden():
                    continue
                mark = pair.mark.mapTo(pair, QPoint()).y() + max(pair.mark.minimumHeight(), pair.mark.sizeHint().height()) / 2
                text = pair.text.mapTo(pair, QPoint()).y() + pair.text_center()
                self.assertLessEqual(abs(mark - text), 1, (step, type(pair.mark).__name__))

    def test_context_can_expand_without_hiding_any_diagram_label(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        theme.set_text("larger")
        data = json.loads((Path(guikit.ROOT) / "ai" / "learning-map.json").read_text(encoding="utf-8"))
        root = kit.page(QWidget())
        box = kit.box(root)
        context = LearningContext(data, ["gradient", "update"], reflect=True, expanded=False)
        box.addWidget(context)
        box.addStretch()
        root.resize(600, 1100)
        root.show()
        self.addCleanup(root.close)
        guikit.pump()
        self.assertTrue(context.diagram.isHidden())
        guikit.click(context.flow_btn)
        self.assertTrue(context.diagram.isVisible())
        self.assertEqual(context.map.columns(), 3)
        width = (context.map.width() - 32) / 3 - 12
        for stage in ("data", "predict", "loss", "gradient", "update"):
            self.assertLessEqual(QFontMetricsF(theme.font("learn_caption")).horizontalAdvance(data["stages"][stage]["title"]), width - 16)
        guikit.click(context.toggle)
        self.assertTrue(context.answer.isVisible())
        guikit.click(context.flow_btn)
        self.assertTrue(context.diagram.isHidden())


    def context_in(self, width, step, focus=("data", "predict", "loss", "gradient", "update")):
        self.addCleanup(theme.set_text, theme.state["text"])
        theme.set_text(step)
        data = json.loads((Path(guikit.ROOT) / "ai" / "learning-map.json").read_text(encoding="utf-8"))
        root = kit.page(QWidget())
        box = kit.box(root)
        context = LearningContext(data, list(focus), expanded=False)
        box.addWidget(context)
        box.addStretch()
        root.resize(width, 900)
        root.show()
        self.addCleanup(root.close)
        guikit.pump()
        return context

    def test_context_title_and_connection_share_a_line_with_the_flow_button_at_the_right(self):
        context = self.context_in(1200, "normal")
        head, title, link = context.head, context.head.title, context.head.link
        self.assertEqual(head.mode, "wide")
        middle = lambda widget: widget.mapTo(context, QPoint()).y() + widget.height() / 2
        self.assertLessEqual(abs(middle(title) - middle(link)), 1)
        self.assertLessEqual(abs(middle(head) - middle(context.flow_btn)), 1)
        self.assertGreater(link.mapTo(context, QPoint()).x(), title.mapTo(context, QPoint(title.width(), 0)).x())
        self.assertEqual(context.flow_btn.mapTo(context, QPoint(context.flow_btn.width(), 0)).x(), context.contentsRect().right() + 1 - 20)
        self.assertGreater(context.flow_btn.mapTo(context, QPoint()).x(), link.mapTo(context, QPoint()).x() + ContextHead.natural(link))
        self.assertEqual(title.heightForWidth(title.width()), title.heightForWidth(10000))

    def test_narrow_context_moves_the_connection_below_the_title_and_wraps_it(self):
        context = self.context_in(560, "larger")
        head, title, link, button = context.head, context.head.title, context.head.link, context.flow_btn
        self.assertEqual(head.mode, "split")
        self.assertGreaterEqual(link.mapTo(context, QPoint()).y(), title.mapTo(context, QPoint(0, title.height())).y())
        self.assertGreaterEqual(link.height(), link.heightForWidth(link.width()))
        self.assertGreater(link.heightForWidth(link.width()), link.heightForWidth(10000))
        self.assertEqual(title.heightForWidth(title.width()), title.heightForWidth(10000))
        # 단추는 제목 줄 오른쪽 끝에 남고 연결할 과정은 아래 줄에서 단추 밑까지 줄 전체 폭을 씀
        middle = lambda widget: widget.mapTo(context, QPoint()).y() + widget.height() / 2
        self.assertLessEqual(abs(middle(title) - middle(button)), 1)
        self.assertEqual(button.mapTo(context, QPoint(button.width(), 0)).x(), context.contentsRect().right() + 1 - 20)
        self.assertEqual(link.mapTo(context, QPoint()).x(), title.mapTo(context, QPoint()).x())
        self.assertEqual(link.mapTo(context, QPoint(link.width(), 0)).x(), button.mapTo(context, QPoint(button.width(), 0)).x())
        self.assertLessEqual(head.mapTo(context, QPoint(0, head.height())).y(), context.height() - 16)

    def test_very_narrow_context_puts_the_flow_button_on_its_own_line(self):
        context = self.context_in(300, "larger")
        head, title, link, button = context.head, context.head.title, context.head.link, context.flow_btn
        self.assertEqual(head.mode, "stacked")
        self.assertGreaterEqual(button.mapTo(context, QPoint()).y(), link.mapTo(context, QPoint(0, link.height())).y())
        self.assertEqual(button.mapTo(context, QPoint()).x(), title.mapTo(context, QPoint()).x())
        self.assertLessEqual(context.minimumSizeHint().width(), 300)


if __name__ == "__main__":
    unittest.main()
