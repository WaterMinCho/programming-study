# -*- coding: utf-8 -*-
"""과정 전환·심화 창·새 그림의 작은 창 배치를 확인함."""
from pathlib import Path

from tests import guikit
from tests.test_gui_ai import AiTest
from gui import ai_learn, theme
from gui.docview import FigureView


class CourseGuiTest(AiTest):
    real_bank = True

    def test_course_switch_keeps_participant_old_cursor_and_scoped_lists(self):
        win = self.boot((760, 480))
        win.go_ai()
        self.assertEqual('AI', win.workspace.compact.currentText())
        win.ai.save_step('i01', '1a', 2)
        participant = win.ai.collection.status()['participant']
        guikit.click(win.ai_home.course_tabs.buttons[1])
        self.assertEqual('app', win.ai.course)
        self.assertEqual(['a01'], list(win.ai.lessons))
        self.assertEqual(participant, win.ai.collection.status()['participant'])
        self.assertFalse(win.ai_home.pattern_section.isVisible())
        self.assertFalse(win.ai_home.mock_section.isVisible())
        self.assertIn('응용', win.ai_home.lesson_list.rows[0].title.text())
        win.ai.save_step('a01', 'a1b', 3)
        guikit.click(win.ai_home.course_tabs.buttons[0])
        self.assertEqual('intro', win.ai.course)
        self.assertEqual(2, win.ai.unit_steps('i01', '1a')['at_step'])
        self.assertNotIn('a01', win.ai.lessons)
        self.assertEqual('intro', win.settings.value('ai/course/' + win.user))

    def test_deep_dialog_closes_without_changing_main_position_or_records(self):
        win = self.boot((760, 480))
        win.go_ai()
        win.set_text('larger')
        win.open_ai_unit('i04', '4c', 2)
        guikit.pump()
        level = win.ai_learn.view.findChildren(ai_learn.LevelsBlock)[0]
        level.block = dict(level.block, concept="배치·확률적·미니배치 경사하강법")
        win.ai_learn.scroll.ensureWidgetVisible(level.deep_btn)
        guikit.pump()
        old_scroll = win.ai_learn.scroll.verticalScrollBar().value()
        old_step = win.ai_learn.index
        path = Path(win.ai.record.path)
        before = path.read_bytes() if path.exists() else None
        for mode in ('light', 'dark'):
            theme.set_mode(mode)
            win.restyle()
            guikit.click(level.deep_btn)
            guikit.pump()
            popup = level.deep_dialog
            self.assertTrue(popup.isVisible())
            self.assertLessEqual(popup.width(), win.width())
            self.assertLessEqual(popup.height(), win.height())
            self.assertTrue(level.deep_close.isVisible())
            self.assertTrue(popup.findChildren(FigureView))
            guikit.click(level.deep_close)
            guikit.pump()
            self.assertEqual(old_step, win.ai_learn.index)
            self.assertEqual(old_scroll, win.ai_learn.scroll.verticalScrollBar().value())
            self.assertEqual(before, path.read_bytes() if path.exists() else None)

    def test_application_steps_keep_image_ratio_at_max_text_and_both_themes(self):
        win = self.boot((760, 480))
        win.go_ai()
        win.switch_ai_course('app')
        win.set_text('larger')
        for mode in ('light', 'dark'):
            theme.set_mode(mode)
            win.restyle()
            for unit in ('a1a','a1b','a1c','a1d'):
                for number in range(1, 6):
                    win.open_ai_unit('a01', unit, number)
                    guikit.pump(20)
                    self.assertLessEqual(win.width(), 760)
                    for image in win.ai_learn.view.findChildren(ai_learn.AiFigure):
                        self.assertTrue(image.available)
                        shown = image.picture.pixmap().deviceIndependentSize()
                        self.assertAlmostEqual(shown.width()/shown.height(), image.source.width()/image.source.height(), delta=.01)
                        self.assertEqual(0, win.ai_learn.scroll.horizontalScrollBar().maximum())

    def test_failed_course_open_restores_the_selected_tab(self):
        win = self.boot((760,480))
        win.go_ai()
        path = Path(win.ai.record.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf-8")
        guikit.click(win.ai_home.course_tabs.buttons[1])
        self.assertEqual("intro", win.ai.course)
        self.assertTrue(win.ai_home.course_tabs.buttons[0].isChecked())
        self.assertFalse(win.ai_home.course_tabs.buttons[1].isChecked())
