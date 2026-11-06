# -*- coding: utf-8 -*-
"""고정 은행의 자리 해설과 회전 빈칸 응답을 대조함. 기록은 임시 폴더에만 씀."""
import os
import tempfile
import unittest
from unittest import mock

import study
from aiprep import service
from session import SessionError
from tests import aifix


class RotateFeedbackBase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rotate_feedback_")
        self.addCleanup(temporary.cleanup)
        self.tmp = temporary.name
        patcher = mock.patch.object(study, "SUBMISSIONS_DIR", os.path.join(self.tmp, "submissions"))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(service, "now", return_value="2026-11-09T20:00:00")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = aifix.pc_bank(os.path.join(self.tmp, "bank"))
        self.sess = service.AiSession("tester", home=os.path.join(self.tmp, "home"), root=self.root)
        self.entries = {entry["id"]: entry for entry in self.sess.skeletons["S90"]["slots"]}

    def answer_slot(self, slot, value, readonly=False):
        return self.sess.check_rotate("pc", "18a", "t1", slot, value, readonly=readonly)

    def rotate_block(self):
        return next(block for step in self.sess.unit_steps("pc", "18a")["steps"]
                    for block in step["blocks"] if block["kind"] == "rotate")


class RotateFeedbackTest(RotateFeedbackBase):
    def test_returns_the_requested_slots_existing_explanation_for_both_results(self):
        for slot, value, ok in (("pc-k02", "opt.zero_grad()", True), ("pc-k05", "max", False)):
            with self.subTest(slot=slot, ok=ok):
                result = self.answer_slot(slot, value)
                self.assertEqual(ok, result["ok"])
                self.assertEqual(self.entries[slot]["answer"][0], result["answer"])
                self.assertEqual(self.entries[slot]["explain"], result["explain"])
        self.assertEqual([("pc-k02", True), ("pc-k05", False)],
                         [(row["slot"], row["ok"]) for row in self.sess.record.log])
        self.assertIsNone(self.sess._state().box("pc-k02"))

    def test_missing_and_empty_explanations_return_empty_text(self):
        entry = self.entries["pc-k01"]
        for value in (None, ""):
            with self.subTest(explain=value):
                if value is None:
                    entry.pop("explain", None)
                else:
                    entry["explain"] = value
                result = self.answer_slot("pc-k01", "train")
                self.assertTrue(result["ok"])
                self.assertEqual("", result["explain"])

    def test_readonly_returns_the_explanation_without_writing(self):
        before = list(self.sess.record.log)
        result = self.answer_slot("pc-k03", "backward", readonly=True)
        self.assertEqual(self.entries["pc-k03"]["explain"], result["explain"])
        self.assertEqual(before, self.sess.record.log)
        self.assertIsNone(self.sess._state().box("pc-k03"))

    def test_write_failure_raises_before_feedback_is_returned(self):
        before = list(self.sess.record.log)
        with mock.patch.object(self.sess, "_append", side_effect=SessionError("저장 오류")):
            with self.assertRaises(SessionError):
                self.answer_slot("pc-k03", "backward")
        self.assertEqual(before, self.sess.record.log)
        self.assertIsNone(self.sess._state().box("pc-k03"))

    def test_unit_data_does_not_add_the_explanation_to_unanswered_slots(self):
        block = self.rotate_block()
        for spot in block["slots"]:
            self.assertNotIn("explain", spot)


if __name__ == "__main__":
    unittest.main()
