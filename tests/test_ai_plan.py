# -*- coding: utf-8 -*-
"""aiprep.plan 과 서비스의 새 카드 열림 테스트(설계 1.4, 2.2, 2.9). 오늘 목표 단원, 비핵심 상한과 열림 조건,
차시 풀기로 연 문제집, 밀린 복습 때 목표 절반, 모의고사 카드는 상한 밖, NextCard 여섯 경우의 순서와 12-01 의 줄임,
최근 수업 차시 먼저를 봄.

실행: python -m unittest tests.test_ai_plan
"""
import datetime
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import plan, review, service  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "ai_bank")
EXAM = review.exam_dates({"date": "2026-12-02", "last_new": "2026-11-24", "sweep_from": "2026-11-25", "last_review": "2026-12-01"})
D = datetime.date


class TargetTest(unittest.TestCase):
    def test_units_target(self):
        self.assertEqual(7, plan.units_target(122, 0, 122, D(2026, 11, 6), EXAM))
        self.assertEqual(2, plan.units_target(122, 0, 2, D(2026, 11, 6), EXAM))
        self.assertEqual(10, plan.units_target(30, 20, 40, D(2026, 11, 24), EXAM))
        self.assertEqual(0, plan.units_target(30, 0, 30, D(2026, 11, 25), EXAM))
        self.assertEqual(4, plan.units_target(122, 0, 122, D(2026, 11, 6), EXAM, backlog=151))
        self.assertEqual(7, plan.units_target(122, 0, 122, D(2026, 11, 6), EXAM, backlog=150))

    def test_days_left(self):
        self.assertEqual(26, plan.days_left(EXAM, D(2026, 11, 6)))


class AgainTest(unittest.TestCase):
    def test_wrong_until_two_passes(self):
        today = D(2026, 11, 9)

        def ev(card, result, minute):
            return {"src": "answer", "day": today, "result": result, "at": "2026-11-09T20:%02d:00" % minute}
        events = {"a": [ev("a", "stuck", 1), ev("a", "pass", 5), ev("a", "pass", 9)],
                  "b": [ev("b", "stuck", 2), ev("b", "pass", 6)],
                  "c": [ev("c", "pass", 3)],
                  "d": [ev("d", "partial", 4)],
                  "e": [dict(ev("e", "stuck", 0), day=D(2026, 11, 8))]}
        self.assertEqual(["b", "d"], plan.again_cards(events, today))


class PickTest(unittest.TestCase):
    def test_recent_lesson_first(self):
        today = D(2026, 11, 5)
        units = [{"lesson": "i03", "no": 3, "date": D(2026, 10, 21), "unit": "3a", "order": 0},
                 {"lesson": "i14", "no": 14, "date": D(2026, 11, 5), "unit": "14b", "order": 1},
                 {"lesson": "i14", "no": 14, "date": D(2026, 11, 5), "unit": "14a", "order": 0},
                 {"lesson": "i15", "no": 15, "date": D(2026, 11, 6), "unit": "15a", "order": 0}]
        self.assertEqual("14a", plan.pick_unit(units, today)["unit"])
        self.assertEqual("3a", plan.pick_unit(units, D(2026, 11, 8))["unit"])
        self.assertIsNone(plan.pick_unit([], today))

    def test_revisit_lowest_box_then_oldest(self):
        units = [{"lesson": "i01", "unit": "1a", "core_box": 2.0, "read": D(2026, 11, 6)},
                 {"lesson": "i02", "unit": "2a", "core_box": 1.0, "read": D(2026, 11, 7)},
                 {"lesson": "i02", "unit": "2b", "core_box": 1.0, "read": D(2026, 11, 6)}]
        self.assertEqual("2b", plan.pick_revisit(units)["unit"])
        self.assertEqual("2a", plan.pick_revisit(units, [("i02", "2b")])["unit"])

    def test_pending_mock(self):
        mocks = [{"id": "m1", "title": "모의고사 1회", "count": 30, "minutes": 60, "window": ["2026-11-14", "2026-11-16"]}]
        self.assertEqual(D(2026, 11, 16), plan.pending_mock(mocks, {"m1"}, set(), D(2026, 11, 15), EXAM)["until"])
        self.assertIsNone(plan.pending_mock(mocks, {"m1"}, {"m1"}, D(2026, 11, 15), EXAM))
        self.assertIsNone(plan.pending_mock(mocks, set(), set(), D(2026, 11, 15), EXAM))
        self.assertIsNone(plan.pending_mock(mocks, {"m1"}, set(), D(2026, 11, 17), EXAM))


class NextCardTest(unittest.TestCase):
    TODAY = D(2026, 11, 15)
    UNIT = {"lesson": "i11", "no": 11, "unit": "11c", "title": "패딩과 스트라이드", "minutes": 5, "date": D(2026, 11, 14)}
    REVISIT = {"lesson": "i05", "unit": "5c", "no": 5, "title": "기울기 소실과 폭발"}
    MOCK = {"id": "m1", "title": "모의고사 1회", "count": 30, "minutes": 60, "until": D(2026, 11, 16)}

    def ctx(self, **extra):
        out = {"today": self.TODAY, "exam": EXAM, "again": [], "mock": None, "due": 0, "target": 7, "read_today": 2,
               "unit": self.UNIT, "revisit": self.REVISIT}
        out.update(extra)
        return out

    def test_order_of_six(self):
        got = plan.next_card(self.ctx(again=["a", "b"], mock=self.MOCK, due=50))
        self.assertEqual(("again", 2, "오늘 틀린 문항 2개가 남았습니다"), (got["kind"], got["count"], got["title"]))
        got = plan.next_card(self.ctx(mock=self.MOCK, due=50))
        self.assertEqual(("mock", "m1"), (got["kind"], got["mock"]))
        self.assertIn("11월 16일까지", got["why"])
        got = plan.next_card(self.ctx(due=40))
        self.assertEqual(("review", 40, "복습을 먼저 하면 새 단원이 밀리지 않습니다."), (got["kind"], got["count"], got["why"]))
        got = plan.next_card(self.ctx(due=12))
        self.assertEqual(("unit", "11c", "11차시 · 패딩과 스트라이드"), (got["kind"], got["unit"], got["title"]))
        self.assertTrue(got["why"].startswith("어제 수업한 차시입니다."))
        got = plan.next_card(self.ctx(due=12, read_today=7))
        self.assertEqual(("review", "오늘 날짜가 된 문항입니다."), (got["kind"], got["why"]))
        got = plan.next_card(self.ctx(due=0, read_today=7))
        self.assertEqual(("revisit", "다시 보기 · 5차시 기울기 소실과 폭발"), (got["kind"], got["title"]))

    def test_no_goal_keeps_suggesting_units(self):
        got = plan.next_card(self.ctx(due=12, read_today=30, target=None))
        self.assertEqual("unit", got["kind"])

    def test_last_review_day_skips_mock_and_units(self):
        last = EXAM["last_review"]
        got = plan.next_card(self.ctx(today=last, mock=self.MOCK, due=3))
        self.assertEqual(("review", 3), (got["kind"], got["count"]))
        got = plan.next_card(self.ctx(today=last, due=0, revisit=None))
        self.assertEqual("none", got["kind"])

    def test_lesson_state(self):
        self.assertEqual("none", plan.lesson_state(0, 6, [False]))
        self.assertEqual("level1", plan.lesson_state(2, 6, [False]))
        self.assertEqual("level2", plan.lesson_state(6, 6, [True, False]))
        self.assertEqual("mastered", plan.lesson_state(6, 6, [True] * 9 + [False]))


class OpenTest(unittest.TestCase):
    """서비스의 새 카드 열림. 고정 은행 i90(핵심 7장, 비핵심 10장)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ai_plan_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for target, value in ((study, ("SUBMISSIONS_DIR", os.path.join(self.tmp, "subs"))),):
            patcher = mock.patch.object(target, value[0], value[1])
            patcher.start()
            self.addCleanup(patcher.stop)
        self.at = "2026-11-09T20:00:00"
        patcher = mock.patch.object(service, "now", lambda: self.at)
        patcher.start()
        self.addCleanup(patcher.stop)

    def session(self):
        return service.AiSession("alice", home=os.path.join(self.tmp, "home"), root=FIXTURE)

    def state(self, sess):
        return sess._state()

    def fresh(self, sess, where=None):
        st = self.state(sess)
        return sorted(c["id"] for c in sess.cards.values() if st.eligible_new(c) and (not where or where(c)))

    def test_core_opens_on_read_and_non_core_after_box_two(self):
        sess = self.session()
        self.assertEqual([], self.fresh(sess))
        sess.mark_read("i90", "90a")
        self.assertEqual(["i90-b01", "i90-b02", "i90-b03"], self.fresh(sess))
        for cid in ("i90-b01", "i90-b02", "i90-b03"):
            sess._append({"kind": "answer", "set": "s1", "card": cid, "result": "pass", "again": 0})
        self.assertEqual([], self.fresh(sess))  # 읽은 날이라 상자 1
        self.at = "2026-11-10T20:00:00"
        for cid in ("i90-b01", "i90-b02", "i90-b03"):
            sess._append({"kind": "answer", "set": "s2", "card": cid, "result": "pass", "again": 0})
        self.assertEqual(["i90-c01", "i90-g01"], self.fresh(sess))

    def test_non_core_cap_when_enabled(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        for day in ("2026-11-09", "2026-11-10"):
            self.at = day + "T20:00:00"
            for cid in ("i90-b01", "i90-b02", "i90-b03"):
                sess._append({"kind": "answer", "set": "s" + day, "card": cid, "result": "pass", "again": 0})
        with mock.patch.object(service, "NEW_PER_DAY", 1):
            st = self.state(sess)
            self.assertEqual(1, st.new_cap_left())
            picked = service.build_set(sess, st, "mixed", __import__("random").Random(3))
            self.assertEqual(1, len([c for c in picked if not sess.cards[c]["core"] and c not in st.events]))
            sess._append({"kind": "answer", "set": "s3", "card": "i90-c01", "result": "pass", "again": 0})
            st = self.state(sess)
            self.assertEqual((1, 0), (st.new_today, st.new_cap_left()))
        self.assertGreater(self.state(sess).new_cap_left(), 100)  # 기본(사용자 답 11-03)은 상한 없음

    def test_lesson_problem_book_opens_all_cards(self):
        sess = self.session()
        ps = sess.start_set("lesson", lesson="i90", seed=4)
        self.assertEqual(1, sum(1 for e in sess.record.log if e.get("kind") == "open"))
        st = self.state(sess)
        self.assertEqual(sorted(sess.cards), self.fresh(sess) + sorted(st.events))
        self.assertTrue(any(not sess.cards[c]["core"] for c in [e["card"] for e in ps.queue]))
        sess.start_set("lesson", lesson="i90", seed=5)
        self.assertEqual(1, sum(1 for e in sess.record.log if e.get("kind") == "open"))

    def test_no_new_non_core_after_last_new(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        for day in ("2026-11-23", "2026-11-24"):
            self.at = day + "T20:00:00"
            for cid in ("i90-b01", "i90-b02", "i90-b03"):
                sess._append({"kind": "answer", "set": "s" + day, "card": cid, "result": "pass", "again": 0})
        self.assertEqual(["i90-c01", "i90-g01"], self.fresh(sess, lambda c: c["unit"] == "90a"))
        self.at = "2026-11-25T20:00:00"
        self.assertEqual([], self.fresh(sess, lambda c: c["unit"] == "90a"))

    def test_mock_cards_do_not_count_as_new(self):
        sess = self.session()
        sess._append({"kind": "mock_submit", "mock": "m90", "try": 1, "results": {"m90-01": "stuck", "m90-02": "blank"}})
        self.assertEqual(0, self.state(sess).new_today)

    def test_backlog_halves_goal_with_goal_on(self):
        sess = self.session()
        with mock.patch.object(service, "DAILY_GOAL", True):
            row = self.state(sess).plan()
            self.assertEqual((1, False, True), (row["units_today"], row["backlog"], row["goal"]))
        with mock.patch.object(service._State, "_due_at_start", lambda self: 151):
            row = self.state(sess).plan()
            self.assertTrue(row["backlog"])

    def test_last_review_day_only_box_one_sure_and_leech(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        self.at = "2026-11-28T20:00:00"
        sess._append({"kind": "answer", "set": "s1", "card": "i90-b01", "result": "pass", "again": 0})
        sess._append({"kind": "answer", "set": "s1", "card": "i90-b02", "result": "stuck", "again": 0})
        self.at = "2026-11-29T20:00:00"
        sess._append({"kind": "answer", "set": "s2", "card": "i90-b01", "result": "pass", "again": 0})
        self.at = "2026-12-01T20:00:00"
        st = self.state(sess)
        due = st.due_cards()
        self.assertIn("i90-b02", due)
        self.assertNotIn("i90-b01", due)


if __name__ == "__main__":
    unittest.main()
