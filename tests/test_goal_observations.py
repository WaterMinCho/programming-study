# -*- coding: utf-8 -*-
"""모의고사 입력 관찰의 목표·동의 차수·복원·실패 되돌리기를 확인함."""
import copy
from pathlib import Path
import unittest
from unittest import mock

from aiprep import collection
from aiprep.mock import MockError
from learning_server import cohorts
from tests import test_ai_mock as mock_tests


class ObservationTest(unittest.TestCase):
    def setUp(self):
        helper = mock_tests.MockServiceTest("test_unsubmitted_questions_do_not_enter_practice")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.sess = helper.session()
        self.store = self.sess.collection
        self.store.set_enabled(True)

    def answers(self):
        return {row["data"]["card"]: row for row in self.store.snapshot(include_answers=True)[1:]
                if row["kind"] == "mock_answer"}

    def test_input_goal_and_time_survive_same_value_save_and_resume(self):
        arm = self.store.set_goal("arm")
        exam = self.sess.start_mock("m90", seed=1)
        first_at = "2026-11-08T01:00:00+00:00"
        later_at = "2026-11-08T01:10:00+00:00"
        with mock.patch.object(collection, "stamp", return_value=first_at):
            exam.save_answer(["3"], "m90-01")
            exam.save_answer(["4"], "m90-03")
        first = copy.deepcopy(exam.draft["collection_observations"]["m90-01"])
        vision = self.store.set_goal("vision")
        with mock.patch.object(collection, "stamp", return_value=later_at):
            exam.save_answer(["3"], "m90-01")
            exam.save_answer(["3"], "m90-02")
            exam.save_answer(["3"], "m90-03")
        self.assertEqual(first, exam.draft["collection_observations"]["m90-01"])
        resumed = self.sess.start_mock("m90")
        self.assertEqual(exam.draft, resumed.draft)
        result = resumed.submit()
        rows = self.answers()
        self.assertEqual(arm, rows["m90-01"]["data"]["goal"])
        for cid in ("m90-02", "m90-03"):
            self.assertEqual(vision, rows[cid]["data"]["goal"])
            self.assertEqual(later_at, rows[cid]["data"]["observed_at"])
        self.assertEqual(first_at, rows["m90-01"]["data"]["observed_at"])
        self.assertEqual(result["at"], rows["m90-01"]["data"]["source_at"])
        self.assertNotEqual(first_at, rows["m90-01"]["at"])
        self.assertFalse(any("response" in row["data"] for row in self.store.snapshot()[1:]))
        counts = {row["goal_id"]: row["answers"] for row in cohorts.summarize(list(rows.values()))}
        self.assertEqual({"arm": 1, "vision": 2}, counts)

    def test_legacy_missing_observation_stays_unrecorded(self):
        self.store.set_goal("arm")
        exam = self.sess.start_mock("m90", seed=1)
        exam.save_answer(["3"], "m90-01")
        exam.draft.pop("collection_observations")
        exam._write_draft()
        self.store.set_goal("vision")
        exam.save_answer(["3"], "m90-01")
        self.assertNotIn("collection_observations", exam.draft)
        exam.submit()
        row = self.answers()["m90-01"]
        self.assertEqual("pass", row["data"]["result"])
        self.assertIsNone(row["data"]["goal"])
        self.assertIsNone(row["data"]["observed_at"])
        self.assertEqual("unrecorded", cohorts.summarize([row])[0]["goal_state"])

    def test_failed_draft_write_restores_all_observation_fields(self):
        self.store.set_goal("arm")
        exam = self.sess.start_mock("m90", seed=1)
        for initialized in (False, True):
            if initialized:
                exam.save_answer(["3"], "m90-01")
                self.store.set_goal("vision")
            before = copy.deepcopy(exam.draft)
            saved = Path(exam.path).read_bytes()
            with mock.patch.object(exam, "_write_draft", side_effect=MockError("저장 실패")):
                with self.assertRaises(MockError):
                    exam.save_answer(["4"], "m90-01")
            self.assertEqual(before, exam.draft)
            self.assertEqual(saved, Path(exam.path).read_bytes())

    def test_consent_epoch_and_goal_are_one_snapshot_and_stale_input_is_excluded(self):
        self.store.set_goal("arm")
        context = self.store.observation_context()
        self.store.set_enabled(False)
        self.store.set_enabled(True)
        self.store.set_goal("vision")
        self.store.emit("mock_answer", {"card": "old", "result": "pass", "response": ["OLD"]},
                        observation_context=context)
        row = self.answers()["old"]
        self.assertEqual("not_collected", row["data"]["result"])
        self.assertIsNone(row["data"]["response"])
        self.assertIsNone(row["data"]["goal"])
        self.assertFalse(self.store.emit("mock_submit", {"results": {"old": "pass"}}, observation_context=context))
        self.store.emit("answer", {"goal": context["goal"], "result": "pass"})
        latest = self.store.snapshot()[1:][-1]
        self.assertEqual("vision", latest["data"]["goal"]["goal_id"])
        current = self.store.observation_context()
        self.assertEqual(self.store.status()["epoch"], current["epoch"])
        self.assertEqual(self.store.status()["goal"], current["goal"])
