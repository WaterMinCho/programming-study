# -*- coding: utf-8 -*-
"""고정 은행과 임시 기록으로 빈 복습·완료 화면·계속 복습 단추를 offscreen에서 확인함."""
from unittest import mock

from PyQt6.QtWidgets import QLabel, QWidget

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
        self.assertIn("이번 묶음에서 첫 답에 맞힌 문항", visible_text(page.card))
        self.assertIn("1 / 1", visible_text(page.card))
        self.assertIn("복습할 문항이 없습니다", visible_text(page.card))
        self.assertIn("11월 6일", visible_text(page.card))
        self.assertEqual(1, self.log("set_end")[-1]["first_pass"])
        self.assertFalse(page.again_btn.isVisible())
        self.assertTrue(page.home_btn.isVisible())

    def test_summary_aligns_review_and_counts_and_stacks_at_max_text(self):
        win, _ = self.prepare()
        win.open_ai_practice("review")
        page = win.ai_quiz
        self.finish(page)
        data = dict(page.practice.summary(), first_today=1, up=3, memorised=2)
        upcoming = {"date": "2026-12-31", "text": "12월 31일", "count": 120}
        with mock.patch.object(page.practice, "summary", return_value=data), \
                mock.patch.object(win.ai, "review_status", return_value={"available": False, "next": upcoming}):
            page.show_summary()
        guikit.pump()
        self.assertIn("복습 간격이 늘어난 문항", visible_text(page.card))
        self.assertIn("복습 간격이 줄어든 문항", visible_text(page.card))
        sections = page.card.findChild(QWidget, "practice_summary_sections")
        review, counts = (sections.layout().itemAt(i).widget() for i in range(2))
        for mode in ("light", "dark"):
            win.set_theme(mode)
            win.resize(1200, 780)
            win.set_text("regular")
            guikit.pump()
            self.assertLess(review.x(), counts.x())
            self.assertEqual(review.y(), counts.y())
            win.resize(760, 480)
            win.set_text("larger")
            guikit.pump()
            self.assertEqual(review.x(), counts.x())
            self.assertGreaterEqual(counts.y(), review.geometry().bottom() + 24)
            self.assertEqual(0, page.scroll.horizontalScrollBar().maximum())
            date = next(label for label in review.findChildren(QLabel) if label.text() == "12월 31일 · 120문항")
            self.assertGreaterEqual(date.width(), date.sizeHint().width())
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

    def test_due_generator_is_opened_after_static_cards_are_completed(self):
        win = self.boot()
        sess = win.ai
        static = ("i90-b01", "i90-b02", "i90-c01", "i90-b04", "i90-c02", "i90-s01")
        sess.cards = {cid: sess.cards[cid] for cid in ("i90-g01", *static)}
        self.at(3)
        for unit in ("90a", "90b"):
            sess.mark_read("i90", unit)
        sess._append({"kind": "answer", "set": "yesterday", "card": "i90-g01", "result": "stuck", "again": 0, "seed": 3})
        self.at(4)
        for cid in static:
            sess._append({"kind": "answer", "set": "completed", "card": cid, "result": "pass", "again": 0})
        win.open_ai_practice("review")
        page = win.ai_quiz
        self.assertIs(self.page(), page)
        self.assertIsNotNone(page.practice)
        self.assertEqual("i90-g01", page.item["card"])
        self.assertNotIn("지금 복습할 문항이 없습니다", visible_text(page.card))
