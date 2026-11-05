# -*- coding: utf-8 -*-
"""고정 은행과 임시 기록으로 빈 복습·완료 화면·계속 복습 단추를 offscreen에서 확인함."""
from unittest import mock

from tests import guikit
from tests.test_gui_ai import AiTest, visible_text


class ReviewCompletionPageTest(AiTest):
    def prepare(self, cards=("i90-b01",)):
        win = self.boot()
        sess = win.ai
        sess.cards = {cid: sess.cards[cid] for cid in cards}
        self.at(3)
        sess.mark_read("i90", "90a")
        for cid in cards:
            sess._append({"kind": "answer", "set": "yesterday", "card": cid, "result": "stuck", "again": 0})
        self.at(4)
        return win, sess

    def finish(self, page):
        while page.item is not None:
            self.answer()
            guikit.click(page.next_btn)

    def test_empty_review_shows_next_date_and_home_without_a_set(self):
        win, sess = self.prepare()
        for again, result in enumerate(("stuck", "pass", "pass")):
            sess._append({"kind": "answer", "set": "past-set", "card": "i90-b01", "result": result, "again": again})
        before = list(self.log())
        with mock.patch.object(win, "ask") as ask:
            win.open_ai_practice("review")
        page = win.ai_quiz
        self.assertIs(self.page(), page)
        self.assertIsNone(page.item)
        self.assertIn("복습할 문항이 없습니다", visible_text(page.card))
        self.assertIn("11월 5일", visible_text(page.card))
        self.assertTrue(page.home_btn.isVisible())
        self.assertFalse(page.again_btn.isVisible())
        ask.assert_not_called()
        self.assertEqual(before, self.log())
        guikit.click(page.home_btn)
        self.assertIs(self.page(), win.ai_home)

    def test_finished_review_hides_restart_but_keeps_first_pass_score(self):
        win, sess = self.prepare()
        win.open_ai_practice("review")
        page = win.ai_quiz
        self.finish(page)
        self.assertIn("이번 묶음의 첫 답", visible_text(page.card))
        self.assertIn("복습할 문항이 없습니다", visible_text(page.card))
        self.assertIn("11월 6일", visible_text(page.card))
        self.assertEqual(1, self.log("set_end")[-1]["first_pass"])
        self.assertFalse(page.again_btn.isVisible())
        self.assertTrue(page.home_btn.isVisible())

    def test_finished_review_can_continue_when_another_card_remains(self):
        win, sess = self.prepare(("i90-b01", "i90-b02"))
        with mock.patch("aiprep.service.SET_SIZE", 1):
            win.open_ai_practice("review")
            page = win.ai_quiz
            self.finish(page)
            self.assertTrue(page.again_btn.isVisible())
            guikit.click(page.again_btn)
        self.assertIs(self.page(), page)
        self.assertEqual("i90-b02", page.item["card"])
