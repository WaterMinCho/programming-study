# -*- coding: utf-8 -*-
"""aiprep.notes 테스트(설계 2.11). 갈래 계산(읽은 날 오답 빠짐, 확신 오답은 들어옴, 다른 날 한 번 맞히면 fixed, 두 번이면
내려감, 다시 틀리면 wrong), 모의고사 비운 문항 = skipped, 묶음 순서(모의고사 최근 회차 → 차시 → 상황별 코드), 갈래 안 순서
(확신 오답 → 자주 틀리는 문항 → 최근)를 봄.

실행: python -m unittest tests.test_ai_notes
"""
import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aiprep import notes, review  # noqa: E402

D = datetime.date


def ans(day, result, sure=None, minute=0, dontknow=False):
    return {"kind": "answer", "card": "x", "at": "2026-11-%02dT20:%02d:00" % (day, minute), "result": result, "again": 0,
            "set": "s%d" % day, "sure": sure, "dontknow": dontknow}


def events(rows, card="i05-b01"):
    log = [dict(r, card=card) for r in rows]
    return review.card_events(log)[card]


class CardNoteTest(unittest.TestCase):
    def test_read_day_wrong_is_left_out_unless_sure(self):
        self.assertIsNone(notes.card_note(events([ans(9, "stuck")]), D(2026, 11, 9))["state"])
        got = notes.card_note(events([ans(9, "stuck", True)]), D(2026, 11, 9))
        self.assertEqual(("wrong", True), (got["state"], got["sure"]))
        self.assertIsNone(notes.card_note(events([ans(9, "stuck", dontknow=True)]), D(2026, 11, 9))["state"])

    def test_wrong_fixed_then_removed(self):
        rows = [ans(10, "stuck")]
        self.assertEqual("wrong", notes.card_note(events(rows))["state"])
        rows.append(ans(10, "pass", minute=5))
        self.assertEqual("wrong", notes.card_note(events(rows))["state"])  # 같은 날 뒤 답은 보지 않음
        rows.append(ans(11, "pass"))
        self.assertEqual("fixed", notes.card_note(events(rows))["state"])
        rows.append(ans(13, "pass"))
        self.assertIsNone(notes.card_note(events(rows))["state"])

    def test_fixed_back_to_wrong_and_partial(self):
        rows = [ans(10, "partial"), ans(11, "pass")]
        self.assertEqual("fixed", notes.card_note(events(rows))["state"])
        rows.append(ans(12, "stuck"))
        got = notes.card_note(events(rows))
        self.assertEqual(("wrong", 2, ["2026-11-10", "2026-11-12"]), (got["state"], got["fails"], [d.isoformat() for d in got["days"]]))

    def test_dontknow_is_skipped(self):
        self.assertEqual("skipped", notes.card_note(events([ans(10, "stuck", dontknow=True)]))["state"])

    def test_mock_blank_and_wrong(self):
        log = [{"kind": "mock_submit", "at": "2026-11-15T20:00:00", "mock": "m1", "try": 1,
                "results": {"m1-01": "pass", "m1-02": "stuck", "m1-03": "blank"}}]
        found = review.card_events(log)
        self.assertEqual("wrong", notes.card_note(found["m1-02"])["state"])
        self.assertEqual("skipped", notes.card_note(found["m1-03"])["state"])
        self.assertIsNone(notes.card_note(found["m1-01"])["state"])
        later = log + [{"kind": "answer", "card": "m1-02", "at": "2026-11-16T20:00:00", "result": "pass", "again": 0, "set": "s"}]
        self.assertEqual("fixed", notes.card_note(review.card_events(later)["m1-02"])["state"])


class GroupTest(unittest.TestCase):
    def test_groups_and_order(self):
        log = [
            {"kind": "mock_submit", "at": "2026-11-15T20:00:00", "mock": "m1", "try": 1, "results": {"m1-02": "stuck"}},
            {"kind": "mock_submit", "at": "2026-11-22T20:00:00", "mock": "m2", "try": 1, "results": {"m2-05": "blank"}},
            dict(ans(10, "stuck"), card="i05-b01"),
            dict(ans(11, "stuck", True), card="i05-b02"),
            dict(ans(12, "stuck"), card="i05-c01"),
            dict(ans(12, "stuck"), card="i03-b01"),
            dict(ans(12, "stuck"), card="pc-k01"),
        ]
        cards = {"i05-b01": {"id": "i05-b01", "kind": "blank", "lesson": "i05"},
                 "i05-b02": {"id": "i05-b02", "kind": "blank", "lesson": "i05"},
                 "i05-c01": {"id": "i05-c01", "kind": "choice", "lesson": "i05", "deep": True},
                 "i03-b01": {"id": "i03-b01", "kind": "blank", "lesson": "i03"},
                 "pc-k01": {"id": "pc-k01", "kind": "skel", "lesson": "i09"},
                 "m1-02": {"id": "m1-02", "kind": "mock"}, "m2-05": {"id": "m2-05", "kind": "mock"}}
        lessons = {"i03": {"no": 3, "title": "PyTorch 텐서"}, "i05": {"no": 5, "title": "경사하강법 구현"}}
        mocks = {"m1": {"title": "모의고사 1회"}, "m2": {"title": "모의고사 2회"}}
        groups, counts = notes.wrong_notes(review.card_events(log), cards, {}, lessons, mocks, leeches={"i05-b01"},
                                           mock_order=["m2", "m1"])
        self.assertEqual(["모의고사 2회", "모의고사 1회", "3차시 PyTorch 텐서", "5차시 경사하강법 구현", "상황별 코드"],
                         [g["title"] for g in groups])
        self.assertEqual({"wrong": 6, "skipped": 1, "fixed": 0}, counts)
        five = groups[3]["items"]
        self.assertEqual(["i05-b02", "i05-b01", "i05-c01"], [i["key"] for i in five])
        self.assertEqual(("빈칸 · 5차시", True, False), (five[0]["label"], five[0]["sure"], five[0]["leech"]))
        self.assertTrue(five[1]["leech"])
        self.assertTrue(five[2]["deep"])
        self.assertEqual(("고르기 · 5차시", "모의고사 · 모의고사 2회"), (five[2]["label"], groups[0]["items"][0]["label"]))
        keys = [i["key"] for g in groups for i in g["items"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_pattern_cards_share_one_group_with_part_labels(self):
        log = [dict(ans(12, "stuck"), card=cid) for cid in ("pc-k01", "pc-o01", "pc-x01")]
        cards = {"pc-k01": {"id": "pc-k01", "kind": "skel", "part": "slot", "lesson": "pc"},
                 "pc-o01": {"id": "pc-o01", "kind": "skel", "part": "order", "lesson": "pc"},
                 "pc-x01": {"id": "pc-x01", "kind": "skel", "part": "change", "lesson": "pc"}}
        groups, _ = notes.wrong_notes(review.card_events(log), cards, {}, {}, {})
        self.assertEqual(["상황별 코드"], [g["title"] for g in groups])
        labels = {i["key"]: i["label"] for i in groups[0]["items"]}
        self.assertEqual({"pc-k01": "코드 빈칸 · 상황별 코드", "pc-o01": "순서 고르기 · 상황별 코드", "pc-x01": "고르기 · 상황별 코드"}, labels)


if __name__ == "__main__":
    unittest.main()
