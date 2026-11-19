# -*- coding: utf-8 -*-
"""AI 홈의 모의고사 탭. 탭 왕복, 탭 설정, 돌아가기, 예전 회차 접는 줄, 초안 안내 띠를 확인함."""
import datetime
import json
from pathlib import Path
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
        for size in ((760, 480), (1024, 700)):
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
