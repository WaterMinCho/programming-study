# -*- coding: utf-8 -*-
"""과정 전환·심화 창·새 그림의 작은 창 배치를 확인함."""
from pathlib import Path
import datetime
import json
import shutil
from unittest import mock

from tests import guikit
from tests.test_gui_ai import AiTest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from gui import ai_learn, ai_text, theme
from aiprep import service as ai_service
from gui.docview import FigureView



class CodingWithoutAppGroupTest(AiTest):
    """응용 무리가 없는 고정 은행(pc 만 있음). 실제 은행으로 응용 코딩 구역이 숨는 것을 보던 확인을 무리 수와 상관없이 남김."""
    pc = True

    def test_app_course_without_group_hides_rows_and_says_not_yet(self):
        win = self.boot((760, 480))
        win.go_ai()
        home = win.ai_home
        guikit.click(home.browser.buttons["coding"])
        self.idle()
        self.assertTrue(home.pattern_section.isVisible())
        win.switch_ai_course("app")
        self.idle()
        guikit.click(home.browser.buttons["coding"])
        self.idle()
        self.assertEqual({}, win.ai.patterns)
        self.assertFalse(home.pattern_section.isVisible())
        self.assertTrue(home.pattern_empty.isVisible())
        self.assertIn("아직", home.pattern_empty.text())
        self.assertEqual("", home.pattern_count.text())
        self.assertEqual(ai_text.CODING_ABOUT["app"], home.pattern_about.text())


class CodingWithAppGroupTest(AiTest):
    """개론 무리 pc 와 응용 무리 apc 가 함께 든 고정 은행. 과정마다 자기 무리만 보이고 권하는 차시 글이 과정을 따름."""
    apc = True

    def rows(self, home):
        return [(r.title.text(), r.second.text()) for r in home.pattern_list.rows]

    def test_each_course_lists_its_own_coding_units(self):
        win = self.boot((1024, 700))
        win.go_ai()
        home = win.ai_home
        guikit.click(home.browser.buttons["coding"])
        self.idle()
        self.assertEqual([("학습 루프 · 시험 뼈대 단원", "90차시 뒤에 권함 · 약 6분")], self.rows(home))
        self.assertEqual(ai_text.CODING_ABOUT["intro"], home.pattern_about.text())
        win.switch_ai_course("app")
        self.idle()
        guikit.click(home.browser.buttons["coding"])
        self.idle()
        self.assertEqual(["apc"], list(win.ai.patterns))
        self.assertTrue(home.pattern_section.isVisible())
        self.assertFalse(home.pattern_empty.isVisible())
        self.assertEqual([("응용 루프 · 시험 응용 단원", "응용 90차시 뒤에 권함 · 약 6분")], self.rows(home))
        self.assertEqual(ai_text.CODING_ABOUT["app"], home.pattern_about.text())
        self.assertEqual("공개된 단원 1개", home.pattern_count.text())
        self.assertTrue(win.open_ai_unit("apc", "a18a"))
        guikit.pump()
        self.assertEqual("apc", win.ai_learn.lid)

    def test_app_rotate_block_hides_only_note_only_slots(self):
        """S190 의 돌려 가며 빈칸 t1 은 note_only 자리 apc-n102·apc-n101 만 가리고 카드 상자는 움직이지 않음."""
        win = self.boot((1024, 700))
        win.go_ai()
        win.switch_ai_course("app")
        self.idle()
        self.assertTrue(win.open_ai_unit("apc", "a18a", 3))
        guikit.pump()
        block = win.ai_learn.view.findChildren(ai_learn.RotateBlock)[0]
        self.assertEqual("1 / 2", block.count.text())
        self.assertEqual(["apc-n102", "apc-n101"], block.queue)
        field = block.field()
        self.assertEqual("변수 이름", field.placeholderText())
        field.setText("loader")
        guikit.click(block.check_btn)
        self.assertEqual(("틀렸습니다", "정답: `data`"), (block.verdict.text(), block.answer.text()))
        self.assertEqual([("a18a", "t1", "apc-n102", False)], [(r["unit"], r["id"], r["slot"], r["ok"]) for r in self.log("recall")])
        tokens = {spot["id"]: spot["token"] for spot in block.block["slots"]}
        guikit.click(block.next_btn)
        for _ in range(5):
            if block.done.isVisible():
                break
            block.field().setText(tokens[block.queue[block.pos]])
            guikit.click(block.check_btn)
            self.assertEqual("맞았습니다", block.verdict.text())
            guikit.click(block.next_btn)
        self.assertTrue(block.done.isVisible())
        self.assertEqual(["apc-n102", "apc-n101", "apc-n102"], block.queue)
        state = win.ai._state()
        self.assertFalse([cid for cid in ("apc-n101", "apc-n102", "apc-k05") if state.box(cid) is not None])
        self.assertNotIn("apc-n101", win.ai.cards)


class CourseGuiTest(AiTest):
    real_bank = True

    def open_mocks(self, extra=()):
        """실제 은행에서 이 사용자가 볼 회차. 새 사용자는 hidden·legacy 가 아닌 회차만, 예전 회차는 제출한 사람만 봄."""
        from aiprep import bank
        return {m['id'] for m in bank.read_index(bank.AI_DIR)['mocks'] if not m.get('hidden') and not m.get('legacy')} | set(extra)

    def test_course_switch_keeps_participant_old_cursor_and_scoped_lists(self):
        self.assertEqual({'m11', 'm12', 'm13', 'm14', 'm15'}, self.open_mocks())
        self.check_course_switch(self.open_mocks())

    def test_each_round_keeps_its_scope_on_the_list_and_start_screen(self):
        win = self.boot((760, 480))
        win.go_ai()
        guikit.click(win.ai_home.course_tabs.buttons[2])
        details = {row.title.text(): row.second.text() for row in win.ai_home.mock_list.rows}
        for no in range(1, 6):
            with self.subTest(round=no):
                count, app_end = (54, 10) if no == 5 else (52, 9)
                expected = f'{count}문항 · 120분 · 개론 1~17차시 · 응용 1~{app_end}차시'
                self.assertEqual(expected, details[f'모의고사 {no}회'])
                self.assertTrue(win.open_ai_mock(f'm{10 + no}'))
                self.assertEqual(expected, win.ai_mock.heading.text())

    def test_learner_who_submitted_an_old_round_sees_it_in_both_courses(self):
        import os
        from aiprep import bank
        from tests.test_ai_mixed_mock import submitted_before
        from tests.test_gui_ai import USER
        submitted_before(USER, os.environ['STUDY_AI_HOME'], bank.AI_DIR, 'm4')
        self.check_course_switch(self.open_mocks({'m4'}))

    def check_course_switch(self, mocks):
        win = self.boot((760, 480))
        win.go_ai()
        self.assertEqual('AI', win.workspace.compact.currentText())
        win.ai.save_step('i01', '1a', 2)
        participant = win.ai.collection.status()['participant']
        guikit.click(win.ai_home.course_tabs.buttons[1])
        self.assertEqual('app', win.ai.course)
        from gui import ai_text
        self.assertNotIn('응용 · 응용', ai_text.track_line(win.ai.overview()))
        ready = [row['id'] for row in win.ai.overview()['lessons'] if row['ready']]
        self.assertEqual([f'a{no:02d}' for no in range(1, 11)], ready)
        self.assertEqual(participant, win.ai.collection.status()['participant'])
        self.assertFalse(win.ai_home.pattern_section.isVisible())
        self.assertEqual(mocks, set(win.ai.mocks))
        self.assertIn('응용', win.ai_home.lesson_list.rows[0].title.text())
        win.ai.save_step('a01', 'a1b', 3)
        guikit.click(win.ai_home.course_tabs.buttons[2])
        self.assertEqual('intro', win.ai.course)
        self.assertTrue(win.ai_home.mock_section.isVisible())
        listed = [m for m in win.ai.overview()['mocks'] if m['ready']]
        self.assertEqual([m['title'] for m in listed if not m.get('legacy')], [row.title.text() for row in win.ai_home.mock_list.rows])
        self.assertEqual([m['title'] for m in listed if m.get('legacy')], [row.title.text() for row in win.ai_home.old_list.rows])
        self.assertEqual(mocks, set(win.ai.mocks))
        self.assertEqual('app', win.settings.value('ai/course/' + win.user))
        guikit.click(win.ai_home.course_tabs.buttons[0])
        self.assertEqual('intro', win.ai.course)
        self.assertEqual(2, win.ai.unit_steps('i01', '1a')['at_step'])
        self.assertNotIn('a01', win.ai.lessons)
        self.assertEqual('intro', win.settings.value('ai/course/' + win.user))
        self.assertEqual(mocks, set(win.ai.mocks))
        self.capture_widget=win

    def test_missing_mixed_fixture_keeps_application_mock_section_hidden(self):
        from aiprep import bank
        from tests.test_ai_mixed_mock import make_bank
        root=make_bank(self.tmp+'/without-mixed')
        index=json.loads((root/'index.json').read_text(encoding='utf-8'))
        index['mocks']=[m for m in index['mocks'] if m['id']!='m4']
        (root/'index.json').write_text(json.dumps(index),encoding='utf-8')
        shutil.rmtree(root/'mocks/m4')
        with mock.patch.object(bank,'AI_DIR',str(root)):
            win=self.boot((760,480))
            win.go_ai();win.switch_ai_course('app');self.idle()
            self.assertEqual({},win.ai.mocks)
            self.assertNotIn('mocks',win.ai_home.browser.buttons)
            self.assertFalse(win.ai_home.mock_list.isVisible())
            guikit.click(win.ai_home.course_tabs.buttons[2])
            self.assertFalse(win.ai_home.mock_section.isVisible())
            self.assertTrue(win.ai_home.mock_empty.isVisible())
            self.assertEqual('아직 공개된 모의고사가 없습니다.',win.ai_home.mock_empty.text())
            self.capture_widget=win

    def test_switch_reuses_the_course_and_keeps_the_old_tab_until_content_is_ready(self):
        win = self.boot((760, 480))
        win.go_ai()
        intro = win.ai
        make_session = ai_service.AiSession
        observed = []

        def prepare(*args, **kwargs):
            observed.append((win.ai_home.course_tabs.buttons[0].isChecked(), "개론" in win.ai_home.course_intro.text()))
            guikit.pump()
            return make_session(*args, **kwargs)

        with mock.patch("gui.window.ai_service.AiSession", side_effect=prepare) as factory:
            win.ai_home.course_tabs.buttons[1].setFocus()
            QTest.keyClick(win.ai_home.course_tabs.buttons[1], Qt.Key.Key_Space)
            guikit.pump()
            applied = win.ai
            self.assertEqual([(True, True)], observed)
            self.assertEqual([False, True, False], [button.isChecked() for button in win.ai_home.course_tabs.buttons])
            with mock.patch.object(win.ai_home, "show_books", wraps=win.ai_home.show_books) as books:
                guikit.click(win.ai_home.course_tabs.buttons[0])
                self.assertIs(intro, win.ai)
                self.assertEqual([True, False, False], [button.isChecked() for button in win.ai_home.course_tabs.buttons])
                books.assert_called_once()
            guikit.click(win.ai_home.course_tabs.buttons[1])
            self.assertIs(applied, win.ai)
            guikit.click(win.ai_home.course_tabs.buttons[1])
            self.assertEqual([False, True, False], [button.isChecked() for button in win.ai_home.course_tabs.buttons])
            guikit.click(win.ai_home.course_tabs.buttons[2])
            self.assertIs(intro, win.ai)
            guikit.click(win.ai_home.course_tabs.buttons[0])
            self.assertIs(intro, win.ai)
            guikit.click(win.ai_home.course_tabs.buttons[2])
            self.assertIs(intro, win.ai)
            self.assertEqual([False, False, True], [button.isChecked() for button in win.ai_home.course_tabs.buttons])
            factory.assert_called_once()
        self.assertTrue(win.ai_home.updatesEnabled())

    def test_cached_course_reloads_changed_materials_and_rejects_a_broken_record(self):
        win = self.boot((760, 480))
        root = Path(self.tmp) / "course-bank"
        shutil.copytree(win.ai.root, root, ignore=shutil.ignore_patterns("assets", "__pycache__"))
        win.ai = ai_service.AiSession(win.user, root=str(root))
        win.ai_courses.clear()
        win.go_ai()
        guikit.click(win.ai_home.course_tabs.buttons[1])
        before = win.ai
        guikit.click(win.ai_home.course_tabs.buttons[0])
        path = root / "index.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in data["lessons"] if row["id"] == "a01")["title"] = "응용 자료 수정 확인"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        guikit.click(win.ai_home.course_tabs.buttons[1])
        self.assertIsNot(before, win.ai)
        self.assertIn("응용 자료 수정 확인", win.ai_home.lesson_list.rows[0].title.text())
        guikit.click(win.ai_home.course_tabs.buttons[0])
        intro = win.ai
        record = Path(win.ai.record.path)
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("{broken", encoding="utf-8")
        with mock.patch.object(win, "ask") as alert:
            guikit.click(win.ai_home.course_tabs.buttons[1])
        alert.assert_called_once()
        self.assertIs(intro, win.ai)
        self.assertTrue(win.ai_home.course_tabs.buttons[0].isChecked())
        self.assertEqual(b"{broken", record.read_bytes())
        self.assertTrue(win.ai_home.updatesEnabled())

    def test_course_tab_and_content_commit_together_at_max_text_in_both_themes(self):
        win = self.boot((760, 480))
        win.go_ai()
        win.set_text("larger")
        original = win.ai_home.show_lessons
        phases = []

        def update(overview):
            phases.append(win.ai_home.updatesEnabled())
            guikit.pump()
            return original(overview)

        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            for number, course in ((1, "app"), (2, "intro"), (0, "intro")):
                with mock.patch.object(win.ai_home, "show_lessons", side_effect=update):
                    guikit.click(win.ai_home.course_tabs.buttons[number])
                self.assertEqual(course, win.ai.course)
                self.assertTrue(win.ai_home.course_tabs.buttons[number].isChecked())
                self.assertEqual([n == number for n in range(3)], [button.isChecked() for button in win.ai_home.course_tabs.buttons])
                self.assertTrue(win.ai_home.updatesEnabled())
                self.assertEqual(0, win.ai_home.scroll.horizontalScrollBar().maximum())
        self.assertEqual([False] * 6, phases)

    def test_version_notice_fits_small_window_max_text_and_both_themes(self):
        from unittest import mock
        win = self.boot((760, 480))
        win.go_ai()
        win.set_text("larger")
        overview = dict(win.ai.overview(), legacy_cards=999, revised_cards=999)
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            with mock.patch.object(win.ai, "overview", return_value=overview):
                win.ai_home.refresh()
            guikit.pump()
            note = win.ai_home.revision_note
            self.assertTrue(note.isVisible())
            self.assertIn("999", note.text())
            guikit.wait_until(lambda: win.ai_home.browser.pending is None and note.width() > 0
                              and note.height() >= note.heightForWidth(note.width()))
            scroll = win.ai_home.scroll
            reminder = win.workspace.submissions
            scroll.verticalScrollBar().setValue(note.mapTo(scroll.widget(), QPoint()).y() - 24)
            guikit.pump()
            point = note.mapTo(scroll.viewport(), QPoint())
            limit = (scroll.viewport().mapFromGlobal(reminder.mapToGlobal(QPoint())).y()
                     if reminder.isVisible() else scroll.viewport().height())
            self.assertGreaterEqual(point.y(), 0)
            self.assertLessEqual(point.y() + note.height(), limit)
            self.assertGreater(note.heightForWidth(note.width()), 0)
            self.assertLessEqual(note.width(), win.width())
            self.assertGreater(win.ai_home.next_btn.height(), 0)

    def test_learning_answers_block_clipboard_without_moving_at_max_text_in_both_courses(self):
        from PyQt6.QtGui import QKeySequence
        from PyQt6.QtWidgets import QApplication, QToolTip
        win = self.boot((760, 480))
        win.set_text("larger")
        old_clipboard = QApplication.clipboard().text()
        self.addCleanup(QApplication.clipboard().setText, old_clipboard)
        self.addCleanup(QToolTip.hideText)
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            for course, lesson, unit, step in (("intro", "i01", "1a", 2), ("app", "a01", "a1e", 3)):
                win.go_ai()
                win.switch_ai_course(course)
                self.assertTrue(win.open_ai_unit(lesson, unit, step))
                learn = win.ai_learn
                guikit.wait_until(lambda: learn.pending_position is None)
                recall = learn.view.findChildren(ai_learn.RecallBlock)[0]
                field = recall.field
                field.setText("draft")
                field.setSelection(1, 3)
                field.setFocus(Qt.FocusReason.TabFocusReason)
                guikit.wait_until(lambda: not win.input_timer.isActive() and win.focused_input is None and learn.pending_position is None)
                before = (learn.index, learn.scroll.verticalScrollBar().value(), field.geometry(), list(win.ai.record.log))
                QApplication.clipboard().setText("outside-answer")
                for action in (QKeySequence.StandardKey.Copy, QKeySequence.StandardKey.Cut, QKeySequence.StandardKey.Paste):
                    QTest.keySequence(field, QKeySequence(action))
                guikit.pump()
                self.assertEqual("draft", field.text())
                self.assertEqual("raf", field.selectedText())
                self.assertEqual("outside-answer", QApplication.clipboard().text())
                self.assertIs(field, QApplication.focusWidget())
                self.assertEqual(before, (learn.index, learn.scroll.verticalScrollBar().value(), field.geometry(), list(win.ai.record.log)))
                for widget in (field, recall.check_btn):
                    self.assertTrue(widget.visibleRegion().contains(widget.rect()))
                QToolTip.hideText()

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
        ready = [row['id'] for row in win.ai.overview()['lessons'] if row['ready']]
        for mode in ('light', 'dark'):
            theme.set_mode(mode)
            win.restyle()
            for lesson in ready:
                for row in win.ai.unit_list(lesson):
                    unit = row['key']
                    for step in win.ai.unit_steps(lesson, unit)['steps']:
                        number = step['no']
                        win.open_ai_unit(lesson, unit, number)
                        guikit.pump(20)
                        guikit.wait_until(lambda: win.ai_learn.pending_position is None)
                        self.assertLessEqual(win.width(), 760)
                        for image in win.ai_learn.view.findChildren(ai_learn.AiFigure):
                            self.assertTrue(image.available)
                            shown = image.picture.pixmap().deviceIndependentSize()
                            self.assertAlmostEqual(shown.width()/shown.height(), image.source.width()/image.source.height(), delta=.01)
                            self.assertEqual(0, win.ai_learn.scroll.horizontalScrollBar().maximum())
                            if image.controls is not None:
                                win.ai_learn.scroll.ensureWidgetVisible(image.controls, 0, 0)
                                guikit.pump()
                                guikit.wait_until(lambda: win.ai_learn.pending_position is None)
                                viewport = win.ai_learn.scroll.viewport()
                                top = image.controls.mapTo(viewport, QPoint())
                                bottom = top + QPoint(image.controls.width()-1, image.controls.height()-1)
                                where = f'{mode} {lesson} {unit}/{number}: {top}, {bottom}, {viewport.rect()}'
                                self.assertTrue(viewport.rect().contains(top), where)
                                self.assertTrue(viewport.rect().contains(bottom), where)
        win.open_ai_unit('a02', 'a2f', 3)
        guikit.wait_until(lambda: win.ai_learn.pending_position is None)
        image = win.ai_learn.view.findChildren(ai_learn.AiFigure)[0]
        win.ai_learn.scroll.ensureWidgetVisible(image.controls, 0, 0)
        guikit.pump()

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
