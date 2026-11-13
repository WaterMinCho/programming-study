"""종횡비 물음의 새 입력과 기존 초급 답의 화면 복원을 확인함."""
import copy
import os
import unittest
from pathlib import Path
from unittest import mock

from tests import guikit

from PyQt6.QtGui import QFont, QImage

from gui import ai_learn, theme
from tests.test_ai_lesson_content_fixes import ROOT, note, old_aspect_note
from tests import test_gui_ai


class LessonContentGuiTest(unittest.TestCase):
    pc = False
    real_bank = False
    tearDown = test_gui_ai.AiTest.tearDown
    boot = test_gui_ai.AiTest.boot
    idle = test_gui_ai.AiTest.idle
    log = test_gui_ai.AiTest.log

    def setUp(self):
        before = (dict(theme.state), QFont(guikit.APP.font()), guikit.APP.palette(), guikit.APP.styleSheet())
        test_gui_ai.AiTest.setUp(self)
        self.addCleanup(self.restore_theme, before)

    def restore_theme(self, before):
        state, font, palette, stylesheet = before
        theme.set_text(state["text"])
        theme.set_mode(state["mode"], force=True)
        guikit.APP.setFont(font)
        guikit.APP.setPalette(palette)
        guikit.APP.setStyleSheet(stylesheet)

    def test_versioned_level_drops_old_twenty_draft_and_preserves_record(self):
        win = self.boot(size=(760, 480))
        win.ai.notes["i90"] = old_aspect_note()
        win.open_ai_unit("i90", "15b", 3)
        page = win.ai_learn
        levels = page.view.findChildren(ai_learn.LevelsBlock)[0]
        levels.row.set_opened(True)
        levels.build()
        old = levels.body.findChildren(ai_learn.RecallBlock)[0]
        win.ai.save_recall("i90", "15b", "15b-levels", True, level=7, value="20", block=old.block)
        first = copy.deepcopy(self.log("recall"))
        old.field.setText("20")
        page.move(1)
        win.ai.notes["i90"] = note("l15")
        page.move(-1)
        levels = page.view.findChildren(ai_learn.LevelsBlock)[0]
        levels.row.set_opened(True)
        levels.build()
        new = levels.body.findChildren(ai_learn.RecallBlock)[0]
        self.assertEqual(("15b-levels-v2", ""), (new.block["id"], new.field.text()))
        self.assertEqual(first, self.log("recall"))
        new.field.setText("6")
        new.check()
        self.assertEqual(first, self.log("recall")[:len(first)])
        self.assertEqual(("15b-levels-v2", 7, True),
                         (self.log("recall")[-1]["id"], self.log("recall")[-1].get("level"), self.log("recall")[-1]["ok"]))

    def test_block_id_change_alone_prevents_old_draft_restoration(self):
        win = self.boot()
        win.ai.notes["i90"] = old_aspect_note()
        win.open_ai_unit("i90", "15b", 3)
        page = win.ai_learn
        levels = page.view.findChildren(ai_learn.LevelsBlock)[0]
        levels.row.set_opened(True)
        levels.build()
        levels.body.findChildren(ai_learn.RecallBlock)[0].field.setText("20")
        page.move(1)
        read = win.ai.unit_steps

        def changed(lid, key):
            data = copy.deepcopy(read(lid, key))
            for block in data["steps"][2]["blocks"]:
                if block.get("id") == "15b-levels":
                    block["id"] = "15b-levels-v2"
                    for level in block["levels"]:
                        level["id"] = block["id"]
            return data

        with mock.patch.object(win.ai, "unit_steps", side_effect=changed) as changed_read:
            page.move(-1)
        changed_read.assert_called_with("i90", "15b")
        levels = page.view.findChildren(ai_learn.LevelsBlock)[0]
        levels.row.set_opened(True)
        levels.build()
        new = levels.body.findChildren(ai_learn.RecallBlock)[0]
        self.assertEqual("가로와 세로의 수를 더하면 ____ 입니다.", new.block["q"])
        self.assertEqual("", new.field.text())
        self.assertEqual([], self.log("recall"))

    def test_figure_scale_and_narrow_page_in_both_themes(self):
        image = QImage(str(ROOT / "ai/learn/l15/assets/15b-6.png"))
        self.assertEqual((1120, 600), (image.width(), image.height()))
        blue = [(x, y) for y in range(200, 440) for x in range(70, 400)
                if image.pixelColor(x, y).name() == "#2563eb"]
        orange = [(x, y) for y in range(200, 440) for x in range(630, 950)
                  if image.pixelColor(x, y).name() == "#ea580c"]
        spans = [(max(x for x, _ in points) - min(x for x, _ in points),
                  max(y for _, y in points) - min(y for _, y in points)) for points in (blue, orange)]
        self.assertAlmostEqual(2, spans[0][0] / spans[1][0], delta=0.03)
        self.assertAlmostEqual(2, spans[0][1] / spans[1][1], delta=0.04)
        for width, height in spans:
            self.assertAlmostEqual(1.5, width / height, delta=0.03)
        win = self.boot(size=(760, 480))
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.addCleanup(theme.set_text, theme.state["text"])
        theme.set_text("larger")
        win.ai.notes["i90"] = note("l15")
        win.open_ai_unit("i90", "15b", 3)
        levels = win.ai_learn.view.findChildren(ai_learn.LevelsBlock)[0]
        levels.row.set_opened(True)
        levels.build()
        evidence = os.environ.get("LESSON_FIX_SCREENSHOTS")
        for dark in (False, True):
            theme.set_mode("dark" if dark else "light")
            win.restyle()
            guikit.pump()
            page = win.ai_learn
            guikit.wait_until(lambda: page.pending_position is None)
            self.assertLessEqual(page.scroll.horizontalScrollBar().maximum(), 0)
            new = next(r for r in page.view.findChildren(ai_learn.RecallBlock)
                       if r.block["id"] == "15b-levels-v2" and r.block["level"] == 7)
            new.field.setFocus()
            guikit.pump()
            guikit.wait_until(lambda: not win.input_timer.isActive() and page.pending_position is None)
            self.assertGreater(new.field.width(), 100)
            self.assertTrue(page.scroll.viewport().rect().contains(new.field.mapTo(page.scroll.viewport(), new.field.rect().bottomRight())),
                            (page.scroll.viewport().rect(), new.field.mapTo(page.scroll.viewport(), new.field.rect().bottomRight())))
            if evidence:
                Path(evidence).mkdir(parents=True, exist_ok=True)
                win.grab().save(str(Path(evidence) / ("aspect-dark.png" if dark else "aspect-light.png")))
