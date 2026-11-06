# -*- coding: utf-8 -*-
"""첫 글줄 정렬과 학습 흐름 그림의 좁은 창 배치를 확인함."""
import json
from pathlib import Path
import unittest

from tests import guikit
from gui import kit, theme
from gui.ai_learn import OptionRow, RevealBlock
from gui.learning_context import LearningContext
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


if __name__ == "__main__":
    unittest.main()
