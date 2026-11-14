# -*- coding: utf-8 -*-
"""공개 문항과 합성 첫 시도로 오답 재출제의 간격·상한·진행을 확인함."""
import copy
import unittest
from unittest import mock

import adaptive


class PythonRetestTest(unittest.TestCase):
    def setUp(self):
        source = adaptive.catalog()
        self.other = {k: v for k, v in source.items()
                      if v["unit"] == "s04" and v["kind"] == "quiz" and v["level"] == 1}
        self.cat = {k: v for k, v in source.items()
                    if v["unit"] == "s03" and v["kind"] == "quiz" and v["level"] == 1}
        self.keys = sorted(self.cat)
        patcher = mock.patch.object(adaptive, "units", return_value=[{"id": "s03", "meta": {}}])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.prof = {"seed": 1, "rounds": [], "attempts": []}

    def round(self, results):
        rid = "r%02d" % (len(self.prof["rounds"]) + 1)
        self.prof["rounds"].append({"id": rid, "kind": "round", "items": list(results)})
        self.prof["attempts"].extend({"round": rid, "item": k, "try": 1, "ok": ok}
                                     for k, ok in results.items())
        return rid

    def test_recent_wrong_does_not_fill_normal_slots_when_new_questions_remain(self):
        wrong = self.keys[:3]
        cat = {k: self.cat[k] for k in wrong}
        cat.update(self.other)
        self.round(dict.fromkeys(wrong, False))
        before = copy.deepcopy(self.prof)
        self.assertEqual([], adaptive.retest_pool(self.prof, cat))
        with mock.patch.object(adaptive, "units", return_value=[{"id": u, "meta": {}} for u in ("s03", "s04")]):
            nxt = adaptive.build_round(self.prof, cat)
        self.assertTrue(nxt["items"])
        self.assertFalse(set(wrong) & set(nxt["items"]))
        self.assertEqual([], nxt["retest"])
        self.assertFalse(nxt["retest_progress_fallback"])
        self.assertEqual(before, self.prof)

    def test_due_wrong_cannot_bypass_two_question_cap_through_normal_slots(self):
        wrong = self.keys[:6]
        cat = {k: self.cat[k] for k in wrong}
        self.round(dict.fromkeys(wrong, False))
        self.round({})
        nxt = adaptive.build_round(self.prof, cat)
        repeated = set(wrong) & set(nxt["items"])
        self.assertEqual(2, len(repeated))
        self.assertEqual(repeated, set(nxt["retest"]))
        self.assertFalse(nxt["retest_progress_fallback"])

    def test_answer_corrected_in_same_round_still_needs_a_later_first_attempt(self):
        key = self.keys[0]
        rid = self.round({key: False})
        self.prof["attempts"].append({"round": rid, "item": key, "try": 2, "ok": True})
        self.round({})
        self.assertEqual([key], adaptive.retest_pool(self.prof, self.cat))
        self.round({key: True})
        self.round({})
        self.assertEqual([], adaptive.retest_pool(self.prof, self.cat))
        nxt = adaptive.build_round(self.prof, self.cat)
        self.assertNotIn(key, nxt["items"])

    def test_new_wrong_after_a_correct_round_reopens_review_from_the_latest_round(self):
        key = self.keys[0]
        self.round({key: False})
        self.round({key: True})
        self.round({key: False})
        self.assertEqual([], adaptive.retest_pool(self.prof, self.cat))
        self.round({})
        self.assertEqual([key], adaptive.retest_pool(self.prof, self.cat))

    def test_exhausted_small_bank_keeps_progress_without_changing_history(self):
        keys = self.keys[:3]
        cat = {k: self.cat[k] for k in keys}
        self.round(dict.fromkeys(keys, False))
        before = copy.deepcopy(self.prof)
        nxt = adaptive.build_round(self.prof, cat)
        self.assertEqual(keys[:2], nxt["items"])
        self.assertEqual(nxt["items"], nxt["retest"])
        self.assertTrue(nxt["retest_progress_fallback"])
        self.assertEqual(before, self.prof)
        self.round(dict.fromkeys(nxt["items"], False))
        self.assertEqual([keys[2]], adaptive.build_round(self.prof, cat)["items"])

    def test_one_new_question_is_enough_to_keep_the_normal_gap(self):
        keys = self.keys[:2]
        cat = {k: self.cat[k] for k in keys}
        self.round({keys[0]: False})
        nxt = adaptive.build_round(self.prof, cat)
        self.assertEqual([keys[1]], nxt["items"])
        self.assertFalse(nxt["retest_progress_fallback"])

    def test_corrected_questions_can_finish_an_exhausted_unpassed_level(self):
        keys = self.keys[:2]
        cat = {k: self.cat[k] for k in keys}
        self.round(dict.fromkeys(keys, False))
        self.round(dict.fromkeys(keys, True))
        self.assertFalse(adaptive.all_states(self.prof, cat)[0]["done"])
        self.assertEqual([], adaptive.retest_pool(self.prof, cat, gap=0))
        nxt = adaptive.build_round(self.prof, cat)
        self.assertEqual(keys, nxt["items"])
        self.assertTrue(nxt["retest_progress_fallback"])
        self.round(dict.fromkeys(keys, True))
        self.assertTrue(adaptive.all_states(self.prof, cat)[0]["done"])
        self.assertIsNone(adaptive.build_round(self.prof, cat))

    def test_other_units_new_questions_precede_corrected_questions_without_stalling(self):
        keys = self.keys[:2]
        cat = {k: self.cat[k] for k in keys}
        cat.update(self.other)
        self.round(dict.fromkeys(keys, False))
        self.round(dict.fromkeys(keys, True))
        with mock.patch.object(adaptive, "units", return_value=[{"id": u, "meta": {}} for u in ("s03", "s04")]):
            nxt = adaptive.build_round(self.prof, cat)
            self.assertFalse(set(keys) & set(nxt["items"]))
            self.assertFalse(nxt["retest_progress_fallback"])
            self.round(dict.fromkeys(self.other, True))
            nxt = adaptive.build_round(self.prof, cat)
            self.assertEqual(keys, nxt["items"])
            self.assertTrue(nxt["retest_progress_fallback"])

    def test_removed_question_and_non_first_attempt_do_not_create_review_candidates(self):
        key = self.keys[0]
        rid = self.round({"removed/Q1": False})
        self.prof["attempts"].append({"round": rid, "item": key, "try": 2, "ok": False})
        self.round({})
        self.assertEqual([], adaptive.retest_pool(self.prof, self.cat))


if __name__ == "__main__":
    unittest.main()
