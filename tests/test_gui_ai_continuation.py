# -*- coding: utf-8 -*-
"""학습 재개 안내와 풀이 초안 복원을 화면 환경에서 확인함."""
from unittest import mock

from tests import guikit
from tests.test_ai_service import Base
from tests.test_gui_ai import AiTest
from gui import ai_text


class ContinuationGuiTest(AiTest):
    def test_last_step_requires_starting_practice_and_reopens_at_last(self):
        win = self.boot()
        win.open_ai_unit("i90", "90a", 4)
        self.assertFalse(win.ai.lesson("i90")["units"][0]["read"])
        win.go_ai()
        win.ai_home.open_next()
        self.assertEqual(3, win.ai_learn.index)
        guikit.click(win.ai_learn.next_btn)
        self.assertTrue(win.ai.lesson("i90")["units"][0]["read"])
        self.assertNotIn(("i90", "90a"), win.ai.completed_units())
        self.assertEqual("practice", win.ai.continuation()["kind"])

    def test_home_and_hub_reopen_the_same_practice_with_draft(self):
        win = self.boot()
        win.ai.mark_read("i90", "90a")
        win.open_ai_practice("unit", lesson="i90", unit="90a")
        page = win.ai_quiz
        self.assertEqual("blank", page.item["kind"])
        page.inputs[0].setText("중간 입력")
        saved_set = page.practice.id
        win.go_ai()
        win.ai_home.open_next()
        self.assertEqual(saved_set, page.practice.id)
        self.assertEqual("중간 입력", page.inputs[0].text())
        win.go_hub()
        win.hub.open_ai(ai_text.next_item(win.ai.overview(), win.ai.today()))
        self.assertEqual(saved_set, page.practice.id)
        self.assertEqual("중간 입력", page.inputs[0].text())

    def test_editing_a_blank_counts_one_change_and_restoring_counts_none(self):
        from gui.ai_quiz import PracticePage
        from PyQt6.QtTest import QTest
        win = self.boot()
        win.ai.mark_read("i90", "90a")
        win.open_ai_practice("unit", lesson="i90", unit="90a")
        page = win.ai_quiz
        def inputs():
            return [r["data"] for r in win.ai.collection.snapshot() if r["kind"] == "ai_input"]
        field = page.inputs[0]
        QTest.keyClicks(field, "example")
        self.assertEqual([], inputs())
        field.clearFocus()
        page.finish_input()
        page.save_progress()
        self.assertEqual(1, len(inputs()))
        self.assertEqual({"input_schema", "set", "card", "position", "course", "goal", "observed_at"}, set(inputs()[0]))
        self.assertEqual(1, inputs()[0]["input_schema"])
        shown = [r for r in win.ai.collection.snapshot() if r["kind"] == "question_returned"]
        self.assertEqual(1, shown[-1]["data"]["input_schema"])
        win.ai._active_set = None
        restored = PracticePage(win)
        self.addCleanup(restored.deleteLater)
        restored.load("unit", "i90", "90a")
        self.assertEqual("example", restored.values()[0])
        restored.finish_input()
        with mock.patch.object(win.ai, "_save_local", return_value=False):
            QTest.keyClicks(restored.inputs[0], "z")
            restored.finish_input()
        self.assertEqual(1, len(inputs()))

    def test_new_page_restores_local_draft_without_grading_it(self):
        from gui.ai_quiz import PracticePage
        win = self.boot()
        win.ai.mark_read("i90", "90a")
        win.open_ai_practice("unit", lesson="i90", unit="90a")
        page = win.ai_quiz
        page.inputs[0].setText("다시 열 입력")
        page.save_progress()
        before = list(win.ai.record.log)
        win.ai._active_set = None
        restored = PracticePage(win)
        self.addCleanup(restored.deleteLater)
        restored.load("unit", "i90", "90a")
        self.assertEqual("다시 열 입력", restored.inputs[0].text())
        self.assertEqual(before, win.ai.record.log)


class ContinuationTextTest(Base):
    def test_due_review_does_not_replace_the_next_completed_unit_text(self):
        sess = self.session()
        sess.save_step("i90", "90a", 4)
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        self.play(ps, lambda _: "pass")
        overview = sess.overview()
        overview["next"] = {"kind": "review", "count": 100}
        self.assertEqual("90b", ai_text.next_item(overview, sess.today())["unit"])
