# -*- coding: utf-8 -*-
"""AI 홈의 모의고사 탭. 탭 왕복, 탭 설정, 돌아가기, 예전 회차 접는 줄, 초안 안내 띠를 확인함."""
import datetime
import json
import os
from pathlib import Path
import sqlite3
import unittest
from unittest import mock

import study
from aiprep import bank, mixed_mock
from aiprep import service as ai_service
from tests import guikit, test_gui_ai
from tests.test_ai_mixed_mock import make_bank
from tests.test_gui_ai import AiTest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget
from gui import theme


def settle(home):
    guikit.pump()
    guikit.wait_until(lambda: home.browser.pending is None)
    guikit.pump()


class MockTabTest(AiTest):
    real_bank = True

    def setUp(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        theme.set_text("normal")
        super().setUp()

    def test_course_positions_survive_a_visit_to_the_mock_tab(self):
        win = self.boot((760, 480))
        win.go_ai()
        home, browser = win.ai_home, win.ai_home.browser
        tabs = home.course_tabs.buttons
        bar = home.scroll.verticalScrollBar()
        guikit.click(tabs[2])
        settle(home)
        self.assertEqual("intro", win.ai.course)
        self.assertFalse(browser.navigation.isVisible())
        self.assertTrue(home.course_tabs.isVisible())
        self.assertTrue(home.mock_list.isVisible())
        guikit.click(tabs[1])
        settle(home)
        self.assertEqual("app", win.ai.course)
        self.assertTrue(browser.navigation.isVisible())
        self.assertTrue(home.lesson_list.isVisible())
        self.assertFalse(home.mock_list.isVisible())
        guikit.click(browser.buttons["coding"])
        settle(home)
        bar.setValue(min(200, bar.maximum()))
        coding_position = bar.value()
        guikit.click(tabs[0])
        settle(home)
        guikit.click(browser.buttons["books"])
        settle(home)
        bar.setValue(min(380, bar.maximum()))
        book_position = bar.value()
        self.assertGreater(book_position, 0)
        guikit.click(tabs[2])
        settle(home)
        self.assertFalse(home.books.isVisible())
        guikit.click(tabs[0])
        settle(home)
        self.assertTrue(browser.buttons["books"].isChecked())
        self.assertTrue(home.books.isVisible())
        self.assertEqual(book_position, bar.value())
        guikit.click(tabs[2])
        guikit.click(tabs[1])
        settle(home)
        self.assertTrue(browser.buttons["coding"].isChecked())
        self.assertEqual(coding_position, bar.value())

    def test_tab_choice_is_kept_per_user_without_touching_the_course_key(self):
        win = self.boot((760, 480))
        win.go_ai()
        home = win.ai_home
        guikit.click(home.course_tabs.buttons[1])
        guikit.click(home.course_tabs.buttons[2])
        self.assertEqual("mock", win.settings.value("ai/tab/" + win.user))
        self.assertEqual("app", win.settings.value("ai/course/" + win.user))
        self.assertEqual(["ai/course/" + win.user, "ai/tab/" + win.user],
                         sorted(key for key in win.settings.allKeys() if key.startswith("ai/")))
        home.tab = "intro"
        self.assertTrue(win.open_session(win.go_ai))
        self.assertEqual("mock", home.tab)
        self.assertEqual("intro", win.ai.course)
        self.assertTrue(home.course_tabs.buttons[2].isChecked())
        self.assertTrue(home.mock_list.isVisible())
        guikit.click(home.course_tabs.buttons[1])
        self.assertEqual("course", win.settings.value("ai/tab/" + win.user))
        win.settings.setValue("ai/course/" + win.user, "mock")
        self.assertTrue(win.open_session(win.go_ai))
        self.assertEqual(("intro", "intro"), (home.tab, win.ai.course))
        self.assertTrue(home.course_tabs.buttons[0].isChecked())

    def test_mock_page_returns_to_the_tab_it_was_opened_from(self):
        win = self.boot((760, 480))
        win.go_ai()
        home = win.ai_home
        guikit.click(home.course_tabs.buttons[2])
        mid = home.mock_list.rows[0]
        guikit.click(mid)
        self.assertIs(win.ai_mock, win.pages.currentWidget())
        self.assertEqual("← 모의고사", win.ai_mock.top.back.text())
        guikit.click(win.ai_mock.top.back)
        guikit.pump()
        self.assertIs(home, win.pages.currentWidget())
        self.assertEqual("mock", home.tab)
        self.assertTrue(home.course_tabs.buttons[2].isChecked())
        self.assertTrue(home.mock_list.isVisible())
        guikit.click(home.course_tabs.buttons[0])
        self.assertTrue(win.open_ai_mock("m1"))
        self.assertEqual("← AI 개론", win.ai_mock.top.back.text())
        guikit.click(win.ai_mock.top.back)
        guikit.pump()
        self.assertEqual("intro", home.tab)
        self.assertTrue(home.course_tabs.buttons[0].isChecked())

    def test_failed_switch_keeps_the_previous_tab(self):
        win = self.boot((760, 480))
        win.go_ai()
        home = win.ai_home
        guikit.click(home.course_tabs.buttons[1])
        path = Path(win.ai.record.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf-8")
        with mock.patch.object(win, "ask") as alert:
            guikit.click(home.course_tabs.buttons[2])
        alert.assert_called_once()
        self.assertEqual("app", win.ai.course)
        self.assertEqual("app", home.tab)
        self.assertEqual([False, True, False], [button.isChecked() for button in home.course_tabs.buttons])
        self.assertNotEqual("mock", win.settings.value("ai/tab/" + win.user))

    def test_failed_switch_from_the_mock_tab_keeps_the_mock_tab(self):
        win = self.boot((760, 480))
        win.go_ai()
        home = win.ai_home
        guikit.click(home.course_tabs.buttons[2])
        path = Path(win.ai.record.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf-8")
        with mock.patch.object(win, "ask") as alert:
            guikit.click(home.course_tabs.buttons[1])
        alert.assert_called_once()
        self.assertEqual(("mock", "intro"), (home.tab, win.ai.course))
        self.assertEqual([False, False, True], [button.isChecked() for button in home.course_tabs.buttons])

    def test_keyboard_moves_from_the_mock_tab_to_the_rows_and_back(self):
        win = self.boot((760, 480))
        win.go_ai()
        home = win.ai_home
        tab = home.course_tabs.buttons[2]
        tab.setFocus()
        QTest.keyClick(tab, Qt.Key.Key_Space)
        settle(home)
        self.assertEqual("mock", home.tab)
        tab.setFocus()
        QTest.keyClick(tab, Qt.Key.Key_Tab)
        self.assertTrue(home.mock_list.rows[0].hasFocus())
        QTest.keyClick(home.mock_list.rows[0], Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(tab.hasFocus())
        guikit.click(home.course_tabs.buttons[0])
        settle(home)
        home.course_tabs.buttons[0].setFocus()
        QTest.keyClick(home.course_tabs.buttons[0], Qt.Key.Key_Tab)
        self.assertTrue(home.browser.buttons["lessons"].hasFocus())

    def test_mock_rows_fit_small_windows_with_large_text_in_both_themes(self):
        win = self.boot((760, 480))
        win.go_ai()
        home = win.ai_home
        guikit.click(home.course_tabs.buttons[2])
        for size in ((1024, 700), (760, 480)):
            win.resize(*size)
            for step in ("normal", "larger"):
                win.set_text(step)
                for mode in ("light", "dark"):
                    theme.set_mode(mode)
                    win.restyle()
                    settle(home)
                    where = (size, step, mode)
                    self.assertEqual(0, home.scroll.horizontalScrollBar().maximum(), where)
                    self.assertGreaterEqual(home.scroll.viewport().height(), 200, where)
                    tabs = home.course_tabs.buttons
                    self.assertEqual(1, len({button.mapTo(home, QPoint()).y() for button in tabs}), where)
                    self.assertEqual(1, len({button.height() for button in tabs}), where)
                    for row in home.mock_list.rows:
                        home.scroll.ensureWidgetVisible(row)
                        guikit.pump()
                        title = row.title.mapTo(row, QPoint())
                        badge = row.tail.mapTo(row, QPoint())
                        self.assertLessEqual(title.x() + row.title.width(), badge.x(), where)
                        self.assertTrue(row.rect().contains(row.title.geometry().translated(title - row.title.pos())), where)
                        self.assertGreaterEqual(row.title.height(), row.title.heightForWidth(row.title.width()), where)
                        self.assertEqual("풀기 전", row.tail.text())
        self.capture_widget = win

    # 학습 현황은 모의고사 탭을 골라도 마지막 과정(ai/course)을 따름

    def hub_state(self, win):
        win.go_hub()
        self.idle()
        hub = win.hub
        return (hub.ai_row.second.text(), hub.ai_row.metric.text(), hub.next_card.title.text(),
                hub.next_card.line.text(), hub.next_subject.text())

    def read_application_unit(self, win):
        """[AI 응용] 탭에서 공개된 첫 단원 하나를 읽음."""
        win.go_ai()
        guikit.click(win.ai_home.course_tabs.buttons[1])
        settle(win.ai_home)
        self.assertEqual("app", win.ai.course)
        lid = next(lid for lid, note in win.ai.notes.items() if note["visible"])
        win.ai.mark_read(lid, sorted(win.ai.notes[lid]["visible"])[0])

    def choose_mock_tab(self, win):
        win.go_ai()
        guikit.click(win.ai_home.course_tabs.buttons[2])
        settle(win.ai_home)
        self.assertEqual(("mock", "intro"), (win.ai_home.tab, win.ai.course))

    def test_hub_keeps_the_application_course_while_the_mock_tab_is_chosen(self):
        win = self.boot((1280, 800))
        self.read_application_unit(win)
        before = self.hub_state(win)
        self.assertTrue(before[0].startswith("응용 · "), before)
        self.choose_mock_tab(win)
        self.assertEqual(before, self.hub_state(win))
        self.assertNotIn("개론", win.hub.ai_row.second.text())
        self.assertEqual(("mock", "intro"), (win.ai_home.tab, win.ai.course))
        self.assertTrue(win.open_session(win.go_hub))
        self.idle()
        self.assertEqual(before, self.hub_state(win))
        self.assertEqual(("mock", "intro"), (win.ai_home.tab, win.ai.course))
        self.assertEqual(("app", "mock"), (win.settings.value("ai/course/" + win.user), win.settings.value("ai/tab/" + win.user)))
        self.assertIs(win.course_ai(), win.course_ai())
        self.assertIs(win.ai_courses["app"][1], win.course_ai())

    def test_hub_is_unchanged_for_intro_learners_on_the_mock_tab(self):
        win = self.boot((1280, 800))
        win.go_ai()
        win.ai.mark_read("i01", sorted(win.ai.notes["i01"]["visible"])[0])
        before = self.hub_state(win)
        self.assertTrue(before[0].startswith("개론 · "), before)
        self.choose_mock_tab(win)
        self.assertEqual(before, self.hub_state(win))
        self.assertIs(win.ai, win.course_ai())
        self.assertEqual(1, len(win.ai_courses))

    def test_hub_next_card_returns_to_the_application_course_from_the_mock_tab(self):
        win = self.boot((1280, 800))
        self.read_application_unit(win)
        self.choose_mock_tab(win)
        self.hub_state(win)
        guikit.click(win.hub.next_btn)
        self.idle()
        self.assertEqual("app", win.ai.course)
        self.assertIs(win.ai_learn, self.page())
        self.assertEqual(("app", "course"), (win.settings.value("ai/course/" + win.user), win.settings.value("ai/tab/" + win.user)))

    def test_hub_next_card_keeps_the_mock_tab_for_intro_learners(self):
        win = self.boot((1280, 800))
        win.go_ai()
        win.ai.mark_read("i01", sorted(win.ai.notes["i01"]["visible"])[0])
        self.choose_mock_tab(win)
        self.hub_state(win)
        guikit.click(win.hub.next_btn)
        self.idle()
        self.assertEqual("intro", win.ai.course)
        self.assertIs(win.ai_learn, self.page())
        self.assertEqual("mock", win.settings.value("ai/tab/" + win.user))

    def test_hub_counts_follow_the_application_course_after_a_mixed_mock_submit(self):
        win = self.boot((1280, 800))
        self.read_application_unit(win)
        self.choose_mock_tab(win)
        self.assertTrue(win.open_ai_mock("m4"))
        page = win.ai_mock
        guikit.click(page.start_btn)
        if page.item["kind"] == "blank":
            page.inputs[0].setFocus()
            QTest.keyClicks(page.inputs[0], "x")
        else:
            guikit.click(page.choices.rows[0].box)
        self.assertTrue(page.persist())
        page.exam.submit()
        guikit.pump()
        shown = self.hub_state(win)
        win.go_ai()
        guikit.click(win.ai_home.course_tabs.buttons[1])
        settle(win.ai_home)
        overview = win.ai.hub_overview()
        self.assertEqual("복습 확인 %d / %d" % (overview["memorised"], overview["families"]), shown[1])
        self.assertTrue(shown[0].startswith("응용 · "), shown)

    def events(self, kind=None):
        path = Path(os.environ["STUDY_AI_HOME"]) / test_gui_ai.USER / "learning-data.sqlite3"
        if not path.exists():
            return []
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            rows = [(k, json.loads(p)) for k, p in conn.execute("SELECT kind, payload FROM events ORDER BY seq")]
        finally:
            conn.close()
        return [data for k, data in rows if kind is None or k == kind]

    def test_expired_intro_round_is_submitted_once_when_the_mock_tab_opens(self):
        self.clock = "2026-11-04T10:00:00"
        exam = ai_service.AiSession(test_gui_ai.USER, course="intro").start_mock("m1")
        cid = exam.draft["order"][0]
        item = exam.items[cid]
        exam.save_answer(["x"] if item["kind"] == "blank" else [item["options"][0]["no"]], cid)
        del exam
        self.clock = "2026-11-04T20:00:00"
        self.settings.setValue("ai/course/" + test_gui_ai.USER, "app")
        self.settings.setValue("ai/tab/" + test_gui_ai.USER, "course")
        win = self.boot((1280, 800))
        daily = win.identity.path.with_name("daily-study.json")
        self.hub_state(win)
        self.assertEqual([], [row for row in self.log("mock_submit") if row.get("mock") == "m1"])
        self.choose_mock_tab(win)
        submitted = [row for row in self.log("mock_submit") if row.get("mock") == "m1"]
        self.assertEqual(1, len(submitted))
        self.assertTrue(submitted[0].get("auto"))
        events = [data for data in self.events("mock_submit") if data.get("mock") == "m1"]
        self.assertEqual([(True, "intro")], [(data.get("auto"), data.get("course")) for data in events])
        guikit.click(win.ai_home.course_tabs.buttons[1])
        settle(win.ai_home)
        self.choose_mock_tab(win)
        self.hub_state(win)
        self.assertTrue(win.open_session(win.go_hub))
        self.idle()
        self.assertEqual(1, len([row for row in self.log("mock_submit") if row.get("mock") == "m1"]))
        self.assertEqual(1, len([data for data in self.events("mock_submit") if data.get("mock") == "m1"]))
        self.assertFalse(daily.exists())

    def test_switching_tabs_and_visiting_the_hub_adds_no_events_or_marks(self):
        win = self.boot((1280, 800))
        self.read_application_unit(win)
        daily = win.identity.path.with_name("daily-study.json")
        before = (len(self.events()), len(self.log()), daily.exists())
        tabs = win.ai_home.course_tabs.buttons
        for index in (0, 1, 2):
            guikit.click(tabs[index])
            settle(win.ai_home)
        self.hub_state(win)
        win.go_ai()
        for index in (1, 2):
            guikit.click(tabs[index])
            settle(win.ai_home)
        self.assertTrue(win.open_session(win.go_hub))
        self.idle()
        self.hub_state(win)
        self.assertEqual(before, (len(self.events()), len(self.log()), daily.exists()))

    def test_mock_list_end_gap_follows_the_shared_list_rule(self):
        """목록 끝 빈 자리는 제출 알림 자리(Workspace.position_reminder)와 본문 아래 여백으로 생기고 개론 탭의 [문제집] 목록과 같음."""
        win = self.boot((1280, 800))
        win.go_ai()
        home = win.ai_home

        def end_gap():
            settle(home)
            bar = home.scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
            guikit.pump()
            self.assertGreater(bar.maximum(), 0)
            viewport = home.scroll.viewport()
            content = home.browser.content
            bottom = max(child.mapTo(viewport, QPoint(0, child.height())).y()
                         for child in content.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly) if child.isVisible())
            return viewport.height() - bottom

        guikit.click(home.browser.buttons["books"])
        books = end_gap()
        guikit.click(home.course_tabs.buttons[2])
        mocks = end_gap()
        expected = home.scroll.widget().layout().contentsMargins().bottom() + home.browser.body.contentsMargins().bottom()
        self.assertEqual(expected, mocks)
        self.assertEqual(books, mocks)


class OldMockTest(unittest.TestCase):
    """합성 은행의 m4 를 legacy·hidden 으로 바꿔 모의고사 탭의 접는 줄과 안내 띠를 확인함."""
    real_bank = False
    pc = False
    tearDown = test_gui_ai.AiTest.tearDown
    boot = test_gui_ai.AiTest.boot
    idle = test_gui_ai.AiTest.idle

    def setUp(self):
        before = (dict(theme.state), QFont(guikit.APP.font()), guikit.APP.palette(), guikit.APP.styleSheet())
        test_gui_ai.AiTest.setUp(self)
        self.addCleanup(self.restore_theme, before)
        self.addCleanup(theme.set_text, theme.state["text"])
        theme.set_text("normal")
        self.root = make_bank(self.tmp + "/old_bank")
        patch = mock.patch.object(bank, "AI_DIR", str(self.root))
        patch.start()
        self.addCleanup(patch.stop)
        mixed_mock._EXAMS.clear()
        self.addCleanup(mixed_mock._EXAMS.clear)

    def restore_theme(self, before):
        state, font, palette, stylesheet = before
        theme.set_text(state["text"])
        theme.set_mode(state["mode"], force=True)
        guikit.APP.setFont(font)
        guikit.APP.setPalette(palette)
        guikit.APP.setStyleSheet(stylesheet)

    def mark(self, **flags):
        index = study.read_json(self.root / "index.json")
        next(m for m in index["mocks"] if m["id"] == "m4").update(flags)
        study.write_text(self.root / "index.json", json.dumps(index))

    def tick(self, minutes):
        self.clock = (datetime.datetime.fromisoformat(self.clock) + datetime.timedelta(minutes=minutes)).isoformat(timespec="seconds")

    def reopen(self, win):
        """은행 목록을 바꾼 뒤 같은 사용자의 개론 세션을 새로 만들고 모의고사 탭을 다시 그림."""
        win.ai_mock.clear()
        mixed_mock._EXAMS.clear()
        win.ai = ai_service.AiSession(win.user)
        win.ai_courses.clear()
        win.ai_courses["intro"] = (bank.source_stamp(win.ai.root), win.ai)
        win.go_ai()
        if win.ai_home.tab != "mock":
            guikit.click(win.ai_home.course_tabs.buttons[2])
        guikit.pump()

    def titles(self, home):
        return [row.title.text() for row in home.mock_list.rows + home.old_list.rows]

    def test_hidden_round_is_left_out_until_the_learner_submits_it(self):
        self.mark(hidden=True)
        win = self.boot((760, 480))
        self.reopen(win)
        home = win.ai_home
        self.assertNotIn("혼합 모의고사", self.titles(home))
        self.assertNotIn("혼합", home.mock_pending.text())
        self.assertFalse(home.old_toggle.isVisible())
        self.mark(hidden=False)
        self.reopen(win)
        win.ai.start_mock("m4").submit()
        self.mark(hidden=True)
        self.reopen(win)
        self.assertEqual([], [row.title.text() for row in home.mock_list.rows])
        self.assertEqual(["혼합 모의고사"], [row.title.text() for row in home.old_list.rows])
        self.assertTrue(home.old_toggle.isVisible())

    def test_legacy_round_folds_under_the_old_rounds_line_for_submitters_only(self):
        self.mark(legacy=True)
        win = self.boot((760, 480))
        self.reopen(win)
        home = win.ai_home
        self.assertFalse(home.old_toggle.isVisible())
        self.assertFalse(home.old_list.isVisible())
        self.assertFalse(home.mock_notice.isVisible())
        self.mark(legacy=False)
        self.reopen(win)
        win.ai.start_mock("m4").submit()
        self.mark(legacy=True)
        self.reopen(win)
        self.assertTrue(home.old_toggle.isVisible())
        self.assertEqual("이전에 푼 회차 1개", home.old_toggle.text())
        self.assertFalse(home.old_toggle.isChecked())
        self.assertFalse(home.old_list.isVisible())
        self.assertEqual("", home.mock_count.text())
        self.assertFalse(home.mock_notice.isVisible())
        home.old_toggle.setFocus()
        QTest.keyClick(home.old_toggle, Qt.Key.Key_Space)
        guikit.pump()
        self.assertTrue(home.old_list.isVisible())
        self.assertEqual(1, len(home.old_list.rows))
        row = home.old_list.rows[0]
        self.assertEqual("0 / 32", row.tail.text())
        home.refresh()
        guikit.pump()
        self.assertTrue(home.old_toggle.isChecked())
        self.assertTrue(home.old_list.isVisible())
        guikit.click(home.course_tabs.buttons[0])
        guikit.click(home.course_tabs.buttons[2])
        self.assertTrue(home.old_list.isVisible())
        home.set_busy(True)
        self.assertFalse(home.old_toggle.isEnabled())
        self.assertTrue(all(row.inert for row in home.old_list.rows))
        home.set_busy(False)
        guikit.click(home.old_list.rows[0])
        self.assertIs(win.ai_mock, win.pages.currentWidget())
        self.assertEqual("m4", win.ai_mock.mid)

    def test_unfinished_legacy_draft_shows_the_notice_and_keeps_the_draft(self):
        win = self.boot((760, 480))
        self.reopen(win)
        exam = win.ai.start_mock("m4", seed=5)
        exam.save_answer(["3"], "m4-01")
        draft = Path(exam.path)
        before = draft.read_bytes()
        del exam
        self.mark(legacy=True)
        self.tick(60)
        self.reopen(win)
        home = win.ai_home
        self.assertTrue(home.mock_notice.isVisible())
        self.assertIn("새 회차", home.mock_notice.text.text())
        self.assertNotIn("혼합 모의고사", self.titles(home))
        self.assertEqual(before, draft.read_bytes())
        self.tick(120)
        self.reopen(win)
        self.assertFalse(home.mock_notice.isVisible())
        self.assertEqual(["혼합 모의고사"], [row.title.text() for row in home.old_list.rows])
        self.assertEqual("1 / 32", home.old_list.rows[0].tail.text())
