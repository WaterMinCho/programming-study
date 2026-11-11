# -*- coding: utf-8 -*-
"""목표 선택·동의 경계와 실제 서비스가 저장한 기록의 집계를 확인함."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from aiprep import collection, goals, service
from learning_server import cohorts
from tests.test_ai_service import Base
from tests import test_ai_mock as mock_tests

ROOT = Path(__file__).resolve().parent.parent


class GoalTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.roadmap = self.repo / "tools/roadmap/roadmap.json"
        self.roadmap.parent.mkdir(parents=True)
        self.roadmap.write_bytes((ROOT / "tools/roadmap/roadmap.json").read_bytes())
        data = json.loads(self.roadmap.read_text())
        data.update(updated="2026-11-07", version="fixture-v1")
        self.roadmap.write_text(json.dumps(data), encoding="utf-8")
        self.store = collection.Collection(str(self.root / "source/private"), str(self.repo))

    def test_default_off_creates_only_a_stop_marker_when_stopped(self):
        self.assertFalse(self.store.status()["enabled"])
        self.store.set_enabled(False)
        self.assertFalse(self.store.emit("answer", {}))
        with self.assertRaises(collection.CollectionError):
            self.store.set_goal("arm")
        self.assertFalse(Path(self.store.path).exists())
        self.assertTrue(Path(self.store.stop_path).exists())

    def test_selection_revision_and_past_snapshots(self):
        self.store.set_enabled(True)
        self.store.emit("answer", {})
        old = self.store.set_goal("arm")
        self.store.emit("answer", {})
        data = json.loads(self.roadmap.read_text())
        data["updated"] = "2026-11-08"
        self.roadmap.write_text(json.dumps(data), encoding="utf-8")
        new = self.store.set_goal("arm")
        self.store.emit("answer", {})
        self.store.set_goal("vision")
        self.store.emit("answer", {})
        self.store.set_goal(None)
        self.store.emit("answer", {})
        answers = [r["data"]["goal"] for r in self.store.snapshot()[1:] if r["kind"] == "answer"]
        self.assertEqual([None, "arm", "arm", "vision", None], [r["goal_id"] for r in answers])
        self.assertEqual(old, answers[1])
        self.assertEqual(new, answers[2])
        self.assertNotEqual(old["roadmap_revision"], new["roadmap_revision"])
        self.assertNotEqual(old["selection_id"], new["selection_id"])
        self.assertEqual("2026-11-08", new["roadmap_updated"])
        self.assertEqual("self_selected_goal", new["basis"])

    def test_reconsent_and_unknown_goal(self):
        self.store.set_enabled(True)
        self.store.set_goal("nav")
        self.store.set_enabled(False)
        self.assertIsNone(self.store.status()["goal"]["goal_id"])
        with self.assertRaises(collection.CollectionError):
            self.store.set_goal("arm")
        self.store.set_enabled(True)
        other = collection.Collection(str(Path(self.store.path).parent), str(self.repo))
        self.assertIsNone(other.status()["goal"]["goal_id"])
        before = other.snapshot()
        with self.assertRaises(collection.CollectionError):
            other.set_goal("invented")
        self.assertEqual(before[1:], other.snapshot()[1:])

    def test_export_readonly_db_and_private_output_boundaries(self):
        self.store.set_enabled(True)
        self.store.set_goal("platform")
        self.store.emit("answer", {"again": 0, "result": "pass"})
        original = Path(self.store.path).read_bytes()
        destination = self.root / "output"
        result = cohorts.export(self.store.path, str(destination), database=True)
        self.assertEqual(original, Path(self.store.path).read_bytes())
        self.assertEqual(1, result["groups"])
        if os.name != "nt":
            self.assertEqual(0o700, destination.stat().st_mode & 0o777)
            self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in destination.iterdir()))
        for forbidden in (destination, ROOT / "forbidden-cohorts", Path(self.store.path).parent / "output"):
            with self.assertRaises((ValueError, FileExistsError)):
                cohorts.export(self.store.path, str(forbidden), database=True)
        with self.assertRaises(FileNotFoundError):
            cohorts.read_events(self.root / "absent.sqlite3", database=True)
        self.assertFalse((self.root / "absent.sqlite3").exists())

    def test_missing_goal_source_and_synthetic_recall_remain_separate(self):
        self.store.set_enabled(True)
        self.store.emit("recall", {"lesson": "l", "unit": "u", "id": "r", "ok": True})
        row = self.store.snapshot()[1:][-1]
        old = copy.deepcopy(row)
        old["data"].pop("goal")
        old.update(event_id="old", at=None, synthetic=False)
        generated = copy.deepcopy(row)
        generated.update(event_id="generated", synthetic=True)
        observed = copy.deepcopy(row)
        observed.update(event_id="observed", synthetic=False)
        empty_goal = copy.deepcopy(row)
        empty_goal.update(event_id="empty-goal", synthetic=False)
        empty_goal["data"]["goal"] = {}
        result = cohorts.summarize([old, generated, observed, empty_goal])
        self.assertEqual({"unrecorded", "unselected"}, {r["goal_state"] for r in result})
        synthetic = next(r for r in result if r["source"] == "synthetic")
        self.assertEqual((1, 0), (synthetic["first_answers"], synthetic["retries"]))
        self.assertEqual(1, sum(r["missing_timestamps"] for r in result))


class ActualLogTest(Base):
    def test_actual_practice_recall_and_corrections_count_exactly(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        sess.collection.set_goal("arm")
        ps = service.PracticeSet(sess, "goal-practice", "unit", ["i90-b01"], 3)
        ps.answer(["다른 답"], 1, False)
        ps.next()
        ps.answer(["반대"], 2, True)
        other = service.PracticeSet(sess, "goal-correction", "unit", ["i90-b01"], 3)
        other.answer(["다른 답"], 1, False)
        sess.collection.set_goal("vision")
        other.override()
        sess.save_recall("i90", "90a", "r1", False)
        sess.save_recall("i90", "90a", "r1", True)
        rows = sess.collection.snapshot()[1:]
        groups = cohorts.summarize(rows, "synthetic")
        practice = [r for r in groups if r["kind"] == "practice"]
        arm = [r for r in practice if r["goal_id"] == "arm"]
        self.assertTrue(arm)
        for row in arm:
            self.assertEqual((1, 3, 2, 1, 1, 0), tuple(row[k] for k in
                             ("participants", "answers", "first_answers", "retries", "correct", "corrections")))
        for row in [r for r in practice if r["goal_id"] == "vision"]:
            self.assertEqual((0, 1), (row["answers"], row["corrections"]))
        recall = next(r for r in groups if r["kind"] == "recall")
        self.assertEqual((2, 1, 1, 1, 2), tuple(recall[k] for k in
                         ("answers", "first_answers", "retries", "correct", "missing_response_times")))
        late = copy.deepcopy(rows[-1])
        late.update(kind="goal_changed", sequence=999, event_id="late")
        late["data"] = {"goal": {"goal_id": "nav"}}
        self.assertEqual(groups, cohorts.summarize(rows + [late], "synthetic"))
        changed = copy.deepcopy(next(r for r in rows if r["kind"] == "answer"))
        changed.update(at=None, synthetic=True)
        changed["data"]["goal"]["goal_id"] = "unknown-goal"
        summary = cohorts.summarize([changed], "recorded")[0]
        self.assertEqual(("unknown", "synthetic", 1), (summary["goal_state"], summary["source"], summary["missing_timestamps"]))

    def test_actual_mock_is_separate_and_has_no_invented_time(self):
        helper = mock_tests.MockServiceTest("test_unsubmitted_questions_do_not_enter_practice")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        sess = helper.session()
        sess.collection.set_enabled(True)
        exam = sess.start_mock("m90", seed=1)
        exam.question()
        exam.save_answer(["3"], "m90-01")
        exam.submit()
        rows = cohorts.summarize(sess.collection.snapshot()[1:], "synthetic")
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(("mock", "unselected", 1, 1, 0, 1),
                             (row["kind"], row["goal_state"], row["answers"], row["first_answers"], row["retries"], row["missing_response_times"]))
