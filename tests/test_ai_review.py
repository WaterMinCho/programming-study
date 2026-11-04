# -*- coding: utf-8 -*-
"""aiprep.review 테스트(설계 2.8). 일정 표를 그대로 따라가고, 학습일 경계, 같은 날 뒤 오답, 날짜 전 partial,
차시 풀기로 먼저 답한 카드의 읽은 날, 훑기 흩뿌림, 시험 뒤 상한 해제, override 짝, 자주 틀리는 문항, 외움 판정을 봄.

실행: python -m unittest tests.test_ai_review
"""
import datetime
import hashlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aiprep import review  # noqa: E402
from aiprep.service import families_memorised  # noqa: E402

EXAM = review.exam_dates({"date": "2026-12-02", "last_new": "2026-11-24", "sweep_from": "2026-11-25", "last_review": "2026-12-01"})
CARD = "i05-b09"
D = datetime.date


def answer(at, result, sure=None, card=CARD, again=0, set_id=None, **extra):
    row = {"kind": "answer", "card": card, "at": at, "result": result, "again": again, "set": set_id or "s" + at[:10]}
    if sure is not None:
        row["sure"] = sure
    row.update(extra)
    return row


def learn(at, lesson="i05", unit="5c"):
    return {"kind": "learn", "lesson": lesson, "unit": unit, "at": at}


def schedule(log, today, card=CARD):
    events = review.card_events(log)[card]
    read = review.read_days(log).get(("i05", "5c"))
    return review.card_schedule(events, read, EXAM, today, card)


TABLE = [  # (시각, 결과, 확실함, 기대 상자, 기대 다음 날짜)
    ("2026-11-09T20:05:00", "pass", True, 1, D(2026, 11, 10)),
    ("2026-11-09T21:05:00", "stuck", False, 1, D(2026, 11, 10)),
    ("2026-11-10T20:00:00", "pass", True, 2, D(2026, 11, 12)),
    ("2026-11-11T20:00:00", "pass", None, 2, D(2026, 11, 12)),
    ("2026-11-12T20:00:00", "pass", None, 3, D(2026, 11, 16)),
    ("2026-11-16T20:00:00", "stuck", True, 1, D(2026, 11, 17)),
    ("2026-11-17T20:00:00", "pass", None, 2, D(2026, 11, 19)),
    ("2026-11-19T20:00:00", "pass", None, 3, D(2026, 11, 23)),
    ("2026-11-23T20:00:00", "pass", None, 4, D(2026, 11, 30)),
    ("2026-11-30T20:00:00", "pass", None, 5, D(2026, 12, 3)),
]


class TableTest(unittest.TestCase):
    """설계 2.8 일정 예를 한 줄씩."""

    def test_spec_table(self):
        self.assertEqual(5, int(hashlib.sha1(CARD.encode()).hexdigest(), 16) % 7)
        log = [learn("2026-11-09T20:00:00")]
        for at, result, sure, box, due in TABLE:
            log.append(answer(at, result, sure))
            today = review.study_day(at)
            got = schedule(log, today)
            self.assertEqual((box, due), (got["box"], got["due"]), at)
        got = schedule(log, D(2026, 11, 30))
        self.assertEqual(D(2026, 11, 23), got["recheck"])
        self.assertTrue(got["done"])
        after = schedule(log, D(2026, 12, 5))
        self.assertEqual((5, D(2026, 12, 14)), (after["box"], after["due"]))
        self.assertFalse(after["done"])

    def test_recheck_caps_due(self):
        log = [learn("2026-11-01T20:00:00"), answer("2026-11-01T20:01:00", "pass"), answer("2026-11-02T20:00:00", "pass"),
               answer("2026-11-04T20:00:00", "pass"), answer("2026-11-08T20:00:00", "pass"),
               answer("2026-11-15T20:00:00", "stuck", True), answer("2026-11-16T20:00:00", "pass"),
               answer("2026-11-18T20:00:00", "pass")]
        got = schedule(log, D(2026, 11, 18))
        self.assertEqual((3, D(2026, 11, 22)), (got["box"], got["due"]))
        self.assertEqual(D(2026, 11, 22), got["recheck"])
        self.assertTrue(got["sure_wrong"])


class RuleTest(unittest.TestCase):
    def test_study_day_turns_at_four(self):
        self.assertEqual(D(2026, 11, 9), review.study_day("2026-11-09T23:55:00"))
        self.assertEqual(D(2026, 11, 9), review.study_day("2026-11-10T00:05:00"))
        self.assertEqual(D(2026, 11, 9), review.study_day("2026-11-10T03:59:59"))
        self.assertEqual(D(2026, 11, 10), review.study_day("2026-11-10T04:00:00"))
        self.assertIsNone(review.study_day("어제"))

    def test_late_night_answers_are_one_day(self):
        log = [answer("2026-11-09T23:55:00", "pass"), answer("2026-11-10T00:05:00", "pass", set_id="s2")]
        got = schedule(log, D(2026, 11, 9))
        self.assertEqual((2, D(2026, 11, 11)), (got["box"], got["due"]))
        self.assertEqual(1, len(got["days"]))

    def test_read_day_first_answer_is_box_one(self):
        log = [learn("2026-11-09T20:00:00"), answer("2026-11-09T20:05:00", "pass")]
        self.assertEqual(1, schedule(log, D(2026, 11, 9))["box"])
        log = [answer("2026-11-09T20:05:00", "pass")]
        self.assertEqual(2, schedule(log, D(2026, 11, 9))["box"])

    def test_read_day_rule_only_for_first_answer(self):
        """차시 풀기로 상자 3 이 된 카드를 나중에 단원을 읽은 날 맞히면 3 → 4."""
        log = [answer("2026-11-01T20:00:00", "pass"), answer("2026-11-03T20:00:00", "pass"),
               learn("2026-11-07T20:00:00"), answer("2026-11-07T20:10:00", "pass")]
        got = schedule(log, D(2026, 11, 7))
        self.assertEqual(4, got["box"])

    def test_same_day_later_stuck_drops_to_one(self):
        log = [answer("2026-11-01T20:00:00", "pass"), answer("2026-11-03T20:00:00", "pass"),
               answer("2026-11-03T21:00:00", "stuck", set_id="s9")]
        got = schedule(log, D(2026, 11, 3))
        self.assertEqual((1, D(2026, 11, 4)), (got["box"], got["due"]))
        self.assertEqual(1, got["drops"])

    def test_same_day_later_pass_is_ignored(self):
        log = [answer("2026-11-01T20:00:00", "stuck"), answer("2026-11-01T21:00:00", "pass", set_id="s9")]
        got = schedule(log, D(2026, 11, 1))
        self.assertEqual((1, D(2026, 11, 2)), (got["box"], got["due"]))

    def test_early_pass_ignored_and_early_partial_keeps_due(self):
        log = [answer("2026-11-01T20:00:00", "pass"), answer("2026-11-03T20:00:00", "pass")]
        self.assertEqual((3, D(2026, 11, 7)), (schedule(log, D(2026, 11, 3))["box"], schedule(log, D(2026, 11, 3))["due"]))
        early = log + [answer("2026-11-05T20:00:00", "pass")]
        self.assertEqual((3, D(2026, 11, 7)), (schedule(early, D(2026, 11, 5))["box"], schedule(early, D(2026, 11, 5))["due"]))
        partial = log + [answer("2026-11-05T20:00:00", "partial")]
        got = schedule(partial, D(2026, 11, 5))
        self.assertEqual((3, D(2026, 11, 6), D(2026, 11, 3)), (got["box"], got["due"], got["last"]))
        stuck = log + [answer("2026-11-05T20:00:00", "stuck")]
        self.assertEqual((1, D(2026, 11, 6)), (schedule(stuck, D(2026, 11, 5))["box"], schedule(stuck, D(2026, 11, 5))["due"]))

    def test_partial_on_due_day_stays(self):
        log = [answer("2026-11-01T20:00:00", "pass"), answer("2026-11-03T20:00:00", "partial")]
        got = schedule(log, D(2026, 11, 3))
        self.assertEqual((2, D(2026, 11, 5)), (got["box"], got["due"]))

    def test_cap_on_last_review_before_exam(self):
        log = [answer("2026-11-20T20:00:00", "pass"), answer("2026-11-22T20:00:00", "pass"),
               answer("2026-11-26T20:00:00", "partial")]
        got = schedule(log, D(2026, 11, 26))
        self.assertEqual((3, D(2026, 11, 30)), (got["box"], got["due"]))
        log = [answer("2026-11-10T20:00:00", "pass"), answer("2026-11-12T20:00:00", "pass"), answer("2026-11-16T20:00:00", "pass"),
               answer("2026-11-23T20:00:00", "pass")]
        got = schedule(log, D(2026, 11, 23))
        self.assertEqual((5, D(2026, 12, 1)), (got["box"], got["due"]))

    def test_pass_on_last_review_or_exam_day_moves_to_the_next_day(self):
        log = [answer("2026-11-28T20:00:00", "stuck", True), answer("2026-12-01T20:00:00", "pass", True)]
        self.assertEqual(D(2026, 12, 2), schedule(log, D(2026, 12, 1))["due"])
        log.append(answer("2026-12-02T20:00:00", "pass"))
        self.assertEqual(D(2026, 12, 3), schedule(log, D(2026, 12, 2))["due"])

    def test_sweep_pass_to_box_four_is_done_before_exam(self):
        log = [answer("2026-11-20T20:00:00", "pass"), answer("2026-11-22T20:00:00", "pass"), answer("2026-11-26T20:00:00", "pass")]
        got = schedule(log, D(2026, 11, 26))
        self.assertEqual((4, D(2026, 12, 3), True), (got["box"], got["due"], got["done"]))
        self.assertEqual(D(2026, 12, 3), review.due_on(got, CARD, EXAM, D(2026, 11, 26)))

    def test_sweep_spreads_open_cards_same_way(self):
        log = [answer("2026-11-10T20:00:00", "pass"), answer("2026-11-12T20:00:00", "pass"), answer("2026-11-16T20:00:00", "pass"),
               answer("2026-11-23T20:00:00", "pass")]
        days = {}
        for n in range(40):
            card = "i05-b%02d" % n
            rows = [dict(r, card=card) for r in log]
            got = review.card_schedule(review.card_events(rows)[card], None, EXAM, D(2026, 11, 26), card)
            day = review.due_on(got, card, EXAM, D(2026, 11, 26))
            self.assertEqual(day, review.due_on(got, card, EXAM, D(2026, 11, 26)))
            self.assertEqual(review.sweep_day(card, EXAM), day)
            days[day] = days.get(day, 0) + 1
        self.assertGreaterEqual(len(days), 5)
        self.assertTrue(all(D(2026, 11, 25) <= d <= D(2026, 12, 1) for d in days))
        self.assertNotIn(D(2026, 12, 1), [d for d, c in days.items() if c > 15])

    def test_after_exam_no_cap(self):
        log = [answer("2026-11-10T20:00:00", "pass"), answer("2026-11-12T20:00:00", "pass"), answer("2026-11-16T20:00:00", "pass"),
               answer("2026-11-23T20:00:00", "pass")]
        before = schedule(log, D(2026, 11, 23))
        after = schedule(log, D(2026, 12, 3))
        self.assertEqual(D(2026, 12, 1), before["due"])
        self.assertEqual(D(2026, 12, 7), after["due"])

    def test_override_marks_only_the_named_answer(self):
        log = [answer("2026-11-01T20:00:00", "stuck", set_id="s1", value=["역 전파"]),
               answer("2026-11-01T20:05:00", "stuck", set_id="s1", again=1, value=["역 전파"]),
               {"kind": "override", "at": "2026-11-01T20:06:00", "set": "s1", "again": 1, "card": CARD, "value": ["역 전파"]}]
        events = review.card_events(log)[CARD]
        self.assertEqual(["stuck", "pass"], [e["result"] for e in events])
        log[2]["again"] = 0
        events = review.card_events(log)[CARD]
        self.assertEqual(["pass", "stuck"], [e["result"] for e in events])
        got = review.card_schedule(events, None, EXAM, D(2026, 11, 1), CARD)
        self.assertEqual(1, got["box"])
        log[2].update(set="other")
        self.assertEqual(["stuck", "stuck"], [e["result"] for e in review.card_events(log)[CARD]])

    def test_also_and_mock_events(self):
        log = [answer("2026-11-01T20:00:00", "stuck", card="i05-s01", also={"i05-s02": "stuck"}),
               {"kind": "mock_submit", "at": "2026-11-15T20:00:00", "mock": "m1", "try": 1,
                "results": {"m1-01": "pass", "m1-02": "stuck", "m1-03": "blank"}},
               {"kind": "mock_submit", "at": "2026-11-15T21:00:00", "mock": "m1", "try": 2, "results": {"m1-02": "pass"}}]
        events = review.card_events(log)
        self.assertEqual("also", events["i05-s02"][0]["src"])
        self.assertEqual(["stuck"], [e["result"] for e in events["m1-02"]])
        self.assertTrue(events["m1-03"][0]["dontknow"])

    def test_leech_counts_drops_on_different_days(self):
        log = [answer("2026-11-01T20:00:00", "pass"), answer("2026-11-03T20:00:00", "stuck"),
               answer("2026-11-04T20:00:00", "pass"), answer("2026-11-06T20:00:00", "stuck"),
               answer("2026-11-07T20:00:00", "pass"), answer("2026-11-09T20:00:00", "stuck")]
        got = schedule(log, D(2026, 11, 9))
        self.assertEqual(3, got["drops"])
        self.assertTrue(review.leech(got))
        self.assertFalse(review.leech(schedule(log[:4], D(2026, 11, 6))))


class MemorisedTest(unittest.TestCase):
    def test_box_four_and_family_counted_once(self):
        def sched(box):
            return {"box": box, "drops": 0}
        cards = [{"id": "a", "family": "f1"}, {"id": "b", "family": "f1"}, {"id": "c", "family": "f2"}, {"id": "d", "family": "f3"}]
        self.assertEqual(2, families_memorised(cards, {"a": sched(4), "b": sched(5), "c": sched(4), "d": sched(3)}))
        self.assertEqual(1, families_memorised(cards, {"a": sched(4), "b": sched(2), "c": sched(4)}))
        self.assertEqual(2, families_memorised(cards, {"a": sched(4), "c": sched(4)}))
        self.assertTrue(review.memorised(sched(4)))
        self.assertFalse(review.memorised(sched(3)))
        self.assertFalse(review.memorised(None))


if __name__ == "__main__":
    unittest.main()
