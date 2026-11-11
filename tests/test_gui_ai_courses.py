# -*- coding: utf-8 -*-
"""과정 전환·심화 창·새 그림의 작은 창 배치를 확인함."""
from pathlib import Path
import datetime

from tests import guikit
from tests.test_gui_ai import AiTest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
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
        self.assertEqual(['a01', 'a02', 'a03'], list(win.ai.lessons))
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
        guikit.wait_until(lambda: win.ai_learn.pending_position is None)
        level = win.ai_learn.view.findChildren(ai_learn.LevelsBlock)[0]
        level.block = dict(level.block, concept="배치·확률적·미니배치 경사하강법")
        win.ai_learn.scroll.ensureWidgetVisible(level.deep_btn)
        guikit.pump()
        old_step = win.ai_learn.index
        path = Path(win.ai.record.path)
        before = path.read_bytes() if path.exists() else None
        for mode in ('light', 'dark'):
            theme.set_mode(mode)
            win.restyle()
            guikit.wait_until(lambda: win.ai_learn.pending_position is None)
            win.ai_learn.scroll.ensureWidgetVisible(level.deep_btn)
            guikit.pump()
            old_scroll = win.ai_learn.scroll.verticalScrollBar().value()
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
            for lesson, units in [('a01', ('a1a','a1b','a1c','a1d')),
                                  ('a02', ('a2a','a2b','a2c','a2d','a2e')),
                                  ('a03', ('a3a','a3b','a3c','a3d','a3e'))]:
                for unit in units:
                    for number in range(1, 7 if unit == 'a3a' else 6):
                        win.open_ai_unit(lesson, unit, number)
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

    def test_cached_popup_fits_smaller_parent_and_escape_returns_focus(self):
        win = self.boot((1280, 800))
        win.go_ai()
        win.set_text('larger')
        win.open_ai_unit('i04', '4c', 2)
        guikit.wait_until(lambda: win.ai_learn.pending_position is None)
        level = win.ai_learn.view.findChildren(ai_learn.LevelsBlock)[0]
        level.open_deep()
        guikit.pump()
        popup = level.deep_dialog
        guikit.click(level.deep_close)
        win.resize(760, 480)
        guikit.wait_until(lambda: win.ai_learn.pending_position is None)
        for mode in ('light', 'dark'):
            theme.set_mode(mode)
            win.restyle()
            guikit.wait_until(lambda: win.ai_learn.pending_position is None)
            win.ai_learn.scroll.ensureWidgetVisible(level.deep_btn)
            guikit.pump()
            at = win.ai_learn.scroll.verticalScrollBar().value()
            guikit.click(level.deep_btn)
            guikit.pump()
            self.assertIs(popup, level.deep_dialog)
            self.assertLessEqual(popup.width(), win.width())
            self.assertLessEqual(popup.height(), win.height())
            self.assertTrue(win.screen().availableGeometry().contains(popup.frameGeometry()))
            QTest.keyClick(popup, Qt.Key.Key_Escape)
            guikit.pump()
            self.assertFalse(popup.isVisible())
            self.assertIs(win.focusWidget(), level.deep_btn)
            self.assertEqual(at, win.ai_learn.scroll.verticalScrollBar().value())

    def test_hub_keeps_intro_activity_when_application_is_selected(self):
        win = self.boot((760, 480))
        win.go_ai()
        self.clock = datetime.datetime.now().isoformat(timespec='seconds')
        win.ai.mark_read('i01', '1a')
        win.switch_ai_course('app')
        self.assertFalse(win.ai.overview()['activity_counts'])
        win.go_hub()
        self.assertTrue(win.hub.ai_row.second.text().startswith('응용 · '))
        for _ in range(2):
            days = {row[0]: row[-1] for row in win.hub.chart.days}
            self.assertEqual(1, days[datetime.date.today()])
            self.assertEqual(1, sum(days.values()))
            win.hub.refresh()
        ai_notes = dict((track.tid, row) for track, row in win.hub.note_rows)['ai']
        self.assertTrue(ai_notes.second.text().startswith('응용 · '))

    def test_main_reading_anchor_does_not_follow_popup_content(self):
        win = self.boot((760, 480))
        win.go_ai()
        win.set_text('larger')
        win.open_ai_unit('i04', '4c', 2)
        guikit.pump()
        page = win.ai_learn
        level = page.view.findChildren(ai_learn.LevelsBlock)[0]
        level.open_deep()
        guikit.pump()
        popup = level.deep_dialog
        parts = popup.findChildren(ai_learn.RichPara) + popup.findChildren(FigureView)
        self.assertTrue(parts)
        for part in parts:
            top = part.mapTo(page.scroll.widget(), QPoint()).y()
            page.scroll.verticalScrollBar().setValue(top+2)
            path = page.reading_position()[0]
            anchor = ai_learn._view_widget(page.view, path)
            self.assertIs(anchor.window(), win)
        guikit.click(level.deep_close)
