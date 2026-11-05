# -*- coding: utf-8 -*-
"""합성 답 기록으로 당일 복습 완료·재개·다음 날 출제와 수동 연습을 확인함."""
import copy
import datetime
import random

from aiprep import service
from tests.test_ai_service import Base, PatternBase


class ReviewCompletionTest(Base):
    def history(self, only=None):
        sess = self.session()
        if only is not None:
            sess.cards = {cid: sess.cards[cid] for cid in only}
        self.at = "2026-11-08T20:00:00"
        for unit in ("90a", "90b"):
            sess.mark_read("i90", unit)
        self.at = "2026-11-09T20:00:00"
        return sess

    def complete(self, sess, cid):
        for again, result in enumerate(("stuck", "pass", "pass")):
            sess._append({"kind": "answer", "set": "past-set", "card": cid,
                          "result": result, "again": again, "seed": 3})

    def picked(self, sess, mode, **kwargs):
        return service.build_set(sess, sess._state(), mode, random.Random(7), **kwargs)

    def test_completed_wrong_card_stays_out_after_reopening_today(self):
        sess = self.history(["i90-b01"])
        self.complete(sess, "i90-b01")
        saved = copy.deepcopy(sess.record.log)
        for mode in ("review", "sweep"):
            with self.subTest(mode=mode):
                self.assertEqual([], self.picked(sess, mode))
        reopened = self.session()
        self.assertNotIn("i90-b01", self.picked(reopened, "review"))
        self.assertEqual(saved, reopened.record.log)
        self.assertEqual(["stuck", "pass", "pass"],
                         [e["result"] for e in saved if e["kind"] == "answer"])

    def test_next_day_due_card_returns(self):
        sess = self.history(["i90-b01"])
        self.complete(sess, "i90-b01")
        self.assertEqual(datetime.date(2026, 11, 10), sess._state().due_day("i90-b01"))
        self.at = "2026-11-10T20:00:00"
        self.assertIn("i90-b01", sess._state().due_cards())
        self.assertEqual(["i90-b01"], self.picked(sess, "review"))

    def pending_generator(self, again=False):
        static = ("i90-b01", "i90-b02", "i90-c01", "i90-b04", "i90-c02", "i90-s01")
        sess = self.history(["i90-g01", *static])
        self.at = "2026-11-08T21:00:00"
        sess._append({"kind": "answer", "set": "yesterday", "card": "i90-g01", "result": "stuck", "again": 0, "seed": 3})
        self.at = "2026-11-09T20:00:00"
        for cid in static:
            sess._append({"kind": "answer", "set": "completed", "card": cid, "result": "pass", "again": 0})
        if again:
            sess._append({"kind": "answer", "set": "unfinished", "card": "i90-g01", "result": "stuck", "again": 0, "seed": 3})
        return sess

    def test_due_generator_survives_after_static_fillers_are_completed(self):
        sess = self.pending_generator()
        self.assertEqual(["i90-g01"], sess._state().due_cards())
        for mode in ("review", "sweep"):
            self.assertEqual(["i90-g01"], self.picked(sess, mode), mode)
        self.assertTrue(sess.review_status()["available"])

    def test_unfinished_generator_survives_after_static_fillers_are_completed(self):
        sess = self.pending_generator(again=True)
        self.assertIn("i90-g01", sess._state().again)
        for mode in ("review", "sweep"):
            self.assertEqual(["i90-g01"], self.picked(sess, mode), mode)
        self.assertTrue(sess.review_status()["available"])

    def test_due_card_and_unfinished_wrong_card_remain(self):
        sess = self.history(["i90-b01", "i90-b02"])
        self.at = "2026-11-08T21:00:00"
        sess._append({"kind": "answer", "set": "yesterday", "card": "i90-b02", "result": "stuck", "again": 0})
        self.at = "2026-11-09T20:00:00"
        self.complete(sess, "i90-b01")
        self.assertEqual(["i90-b02"], self.picked(sess, "review"))
        practice = sess.start_set("note", card="i90-b01", seed=1)
        practice.answer(["틀린 답"], 2, False)
        self.assertIn("i90-b01", sess._state().again)
        self.assertEqual({"i90-b01", "i90-b02"}, set(self.picked(sess, "review")))

    def test_generator_is_excluded_with_enough_other_cards(self):
        sess = self.history()
        for cid in sess.cards:
            sess._append({"kind": "answer", "set": "opened", "card": cid, "result": "pass", "again": 0, "seed": 3})
        self.at = "2026-11-10T20:00:00"
        before = self.picked(sess, "review")
        self.assertGreaterEqual(len(before), 7)
        target = next(cid for cid in before if sess.cards[cid]["kind"] == "gen")
        self.complete(sess, target)
        for mode in ("review", "sweep"):
            with self.subTest(mode=mode):
                picked = self.picked(sess, mode)
                self.assertNotIn(target, picked)
                self.assertGreaterEqual(len(picked), 7)

    def test_manual_practice_can_include_a_completed_card(self):
        sess = self.history(["i90-b01"])
        self.complete(sess, "i90-b01")
        for mode, kwargs in (("mixed", {}), ("lesson", {"lesson": "i90"}),
                             ("unit", {"lesson": "i90", "unit": "90b"}), ("note", {"card": "i90-b01"})):
            with self.subTest(mode=mode):
                self.assertIn("i90-b01", self.picked(sess, mode, **kwargs))

    def test_same_day_sets_keep_their_own_first_answer_and_completion_counts(self):
        sess = self.history(["i90-b01"])
        first = sess.start_set("lesson", lesson="i90", seed=2)
        self.play(first, lambda cur: "fail" if cur["again"] == 0 else "pass")
        self.assertEqual((0, 1, 0), tuple(first.summary()[key] for key in ("first_pass", "first_today", "again_day")))
        second = sess.start_set("lesson", lesson="i90", seed=3)
        self.play(second, lambda cur: "pass")
        self.assertEqual((1, 1, 0), tuple(second.summary()[key] for key in ("first_pass", "first_today", "again_day")))
        self.assertEqual([0, 1], [row["first_pass"] for row in self.log(sess, "set_end")])
        self.at = "2026-11-10T20:00:00"
        review = sess.start_set("review", seed=4)
        self.play(review, lambda cur: "pass")
        self.assertEqual((1, 0, 1), tuple(review.summary()[key] for key in ("first_pass", "first_today", "again_day")))

    def test_review_status_reports_completion_without_writing(self):
        sess = self.history(["i90-b01"])
        self.complete(sess, "i90-b01")
        saved = copy.deepcopy(sess.record.log)
        status = sess.review_status()
        self.assertFalse(status["available"])
        self.assertEqual({"date": "2026-11-10", "text": "11월 10일", "count": 1}, status["next"])
        self.assertEqual(saved, sess.record.log)
        self.at = "2026-11-10T20:00:00"
        self.assertTrue(sess.review_status()["available"])

    def test_empty_review_does_not_request_reading_or_write_a_set(self):
        sess = self.session()
        self.assertEqual({"available": False, "next": None}, sess.review_status())
        for mode in ("review", "sweep"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(service.AiError, "복습할 문항이 없습니다"):
                    sess.start_set(mode)
        self.assertEqual([], self.log(sess))


class PatternReviewCompletionTest(PatternBase):
    def test_pattern_cards_wait_after_mixed_completion_then_return_when_due(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        sess.mark_read("pc", "18a")
        for cid in ("pc-k01", "pc-o01", "pc-p01", "i90-b01"):
            self.answer(sess, cid, result="stuck")
        self.at = "2026-11-10T20:00:00"
        practice = sess.start_set("mixed", seed=7)
        self.assertTrue(any(e["card"].startswith("pc-") for e in practice.queue))
        self.play(practice, lambda cur: "pass")
        self.assertFalse(sess.review_status()["available"])
        self.at = "2026-11-12T20:00:00"
        practice = sess.start_set("review", seed=7)
        self.assertTrue(any(e["card"].startswith("pc-") for e in practice.queue))
