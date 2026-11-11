# -*- coding: utf-8 -*-
"""추가 수집의 동의·보존·중복·내보내기와 실제 채점 연결을 확인함."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

import study
from aiprep import collection, service
from tests.test_ai_service import Base
from tests import test_ai_mock as mock_tests


class CollectionTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="learning_data_")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.store = collection.Collection(str(self.root / "private"), str(self.repo))

    def rows(self, raw=False):
        path = self.root / ("raw.jsonl" if raw else "data.jsonl")
        self.store.export(str(path), include_answers=raw)
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_explicit_consent_stop_and_other_session(self):
        self.assertFalse(self.store.emit("answer", {"response": "값"}))
        self.assertFalse(os.path.exists(self.store.path))
        self.store.set_enabled(True)
        other = collection.Collection(str(self.root / "private"), str(self.repo))
        self.assertTrue(other.status()["enabled"])
        other.set_enabled(False)
        self.assertFalse(self.store.emit("answer", {}))
        self.assertEqual(0, self.store.status()["events"])
        self.store.set_enabled(True)
        self.assertEqual(other.status()["participant"], self.store.status()["participant"])

    def test_unique_events_preserve_retries_and_redact_only_inputs(self):
        self.store.set_enabled(True)
        item = collection.question({"stem": "____", "blanks": [{"answer": ["答"], "mode": "word"}], "explain": "설명"}, card="x")
        self.store.emit("answer", {"response": ["개인 입력"], "result": "pass"}, item, key="one")
        self.store.emit("answer", {"response": ["개인 입력"], "result": "pass"}, item, key="one")
        self.store.emit("answer", {"response": ["다시 입력"], "result": "stuck"}, item, key="two")
        self.assertEqual((2, 1), (self.store.status()["events"], self.store.status()["items"]))
        rows = self.rows()
        self.assertNotIn("개인 입력", json.dumps(rows, ensure_ascii=False))
        self.assertNotIn("答", json.dumps(rows, ensure_ascii=False))
        self.assertEqual(["pass", "stuck"], [r["data"]["result"] for r in rows if r["kind"] == "answer"])
        raw = self.rows(raw=True)
        self.assertEqual([["개인 입력"], ["다시 입력"]], [r["data"]["response"] for r in raw if r["kind"] == "answer"])
        self.assertEqual([r["event_id"] for r in rows[1:]], [r["event_id"] for r in raw[1:]])

    def test_question_revision_changes_with_grading_and_display_order(self):
        item = {"stem": "고르세요", "options": [{"text": "가", "ok": True}, {"text": "나", "ok": False}]}
        first = collection.question(item, option_order=[1, 0])
        self.assertEqual([1, 0], [o["no"] for o in first["content"]["options"]])
        self.assertNotIn("ok", json.dumps(first["content"]))
        self.assertNotEqual(first["revision"], collection.question(item, option_order=[0, 1])["revision"])
        item["options"][0]["ok"] = False
        self.assertNotEqual(first["revision"], collection.question(item, option_order=[1, 0])["revision"])

    def test_export_never_overwrites_or_saves_in_repository(self):
        self.store.set_enabled(True)
        target = self.root / "existing.jsonl"
        target.write_text("보존", encoding="utf-8")
        for path in (target, self.repo / "public.jsonl", Path(self.store.path).parent / "private.jsonl"):
            with self.assertRaises(collection.CollectionError):
                self.store.export(str(path))
        self.assertEqual("보존", target.read_text(encoding="utf-8"))
        self.assertEqual([], list(self.root.glob(".learning-data-*")))

    def test_failure_rolls_back_event_and_item_and_export_temp(self):
        self.store.set_enabled(True)
        self.assertFalse(self.store.emit("answer", {"bad": float("nan")}, {"revision": "x", "content": {}}))
        self.assertEqual((0, 0, 1), (self.store.status()["events"], self.store.status()["items"], self.store.missed))
        with mock.patch.object(collection.os, "link", side_effect=OSError("저장 실패")):
            with self.assertRaises(collection.CollectionError):
                self.store.export(str(self.root / "failed.jsonl"))
        self.assertFalse((self.root / "failed.jsonl").exists())
        self.assertEqual([], list(self.root.glob(".learning-data-*")))

    def test_delete_rotates_identity_and_leaves_other_records(self):
        original = self.root / "private/state.json"
        self.store.set_enabled(True)
        original.write_text("기존 기록", encoding="utf-8")
        participant = self.store.status()["participant"]
        self.store.delete()
        self.assertFalse(os.path.exists(self.store.path))
        self.assertEqual("기존 기록", original.read_text(encoding="utf-8"))
        self.store.set_enabled(True)
        self.assertNotEqual(participant, self.store.status()["participant"])

    def test_corrupt_file_is_reported_without_replacing_it(self):
        Path(self.store.path).parent.mkdir()
        Path(self.store.path).write_bytes(b"broken")
        self.assertTrue(self.store.status()["error"])
        self.assertFalse(self.store.emit("answer", {}))
        with self.assertRaises(collection.CollectionError):
            self.store.set_enabled(True)
        self.assertEqual(b"broken", Path(self.store.path).read_bytes())

    def test_repository_local_home_cannot_collect(self):
        store = collection.Collection(str(self.repo / "private"), str(self.repo))
        with self.assertRaises(collection.CollectionError):
            store.set_enabled(True)
        self.assertFalse(os.path.exists(store.path))


class CollectionIntegrationTest(Base):
    def events(self, sess, kind):
        with sqlite3.connect(sess.collection.path) as conn:
            return [json.loads(r[0]) for r in conn.execute("SELECT payload FROM events WHERE kind=? ORDER BY seq", (kind,))]

    def test_correct_input_is_private_and_repeated_queries_are_deduplicated(self):
        sess = self.session()
        sess.collection.set_enabled(False)
        sess.mark_read("i90", "90a")
        sess.collection.set_enabled(True)
        ps = service.PracticeSet(sess, "private1", "unit", ["i90-b01"], 3)
        ps.current()
        ps.current()
        ps.answer(["반대"], 2.5, True)
        self.assertEqual(["반대"], self.events(sess, "answer")[0]["response"])
        self.assertNotIn("value", self.log(sess, "answer")[0])
        self.assertEqual(1, len(self.events(sess, "question_returned")))
        self.assertEqual([], self.events(sess, "learn"))
        with self.assertRaises(service.AiError):
            ps.answer(["반대"], 1, True)
        self.assertEqual(1, len(self.events(sess, "answer")))

    def test_retry_override_and_dontknow_remain_separate(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        sess.collection.set_enabled(True)
        ps = service.PracticeSet(sess, "private2", "unit", ["i90-b01"], 3)
        ps.answer(["다른 답"], 1, False)
        ps.next()
        ps.dont_know(2)
        answers = self.events(sess, "answer")
        self.assertEqual(["stuck", "stuck"], [e["result"] for e in answers])
        self.assertEqual([True, False], [e["first_in_set"] for e in answers])
        self.assertTrue(answers[1]["dontknow"])
        other = service.PracticeSet(sess, "private2b", "unit", ["i90-b01"], 3)
        other.answer(["다른 답"], 1, False)
        other.override()
        self.assertEqual(1, len(self.events(sess, "override")))
        self.assertEqual("stuck", self.events(sess, "answer")[-1]["result"])

    def test_recall_input_and_corrupt_collection_do_not_break_learning(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        sess.save_recall("i90", "90a", "r1", True, value="반대", block={"q": "____", "answer": ["반대"]})
        self.assertEqual("반대", self.events(sess, "recall")[0]["response"])
        Path(sess.collection.path).write_bytes(b"broken")
        sess.mark_read("i90", "90a")
        self.assertEqual(1, len(self.log(sess, "learn")))
        self.assertTrue(sess.collection.status()["error"])

    def test_collection_never_changes_published_record_shape(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=4)
        current = ps.current()
        ps.answer(self.right(ps, current), 3, False)
        self.assertNotIn("response", study.read_text(sess.record.path))
        self.assertNotIn("participant", study.read_text(sess.record.path))
        self.assertEqual(list(ps.stats), self.events(sess, "set")[0]["selection"]["selected"])

    def test_mock_submission_records_missing_and_answered_items_once(self):
        helper = mock_tests.MockServiceTest("test_unsubmitted_questions_do_not_enter_practice")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        sess = helper.session()
        sess.collection.set_enabled(True)
        exam = sess.start_mock("m90", seed=1)
        exam.question()
        exam.question()
        exam.save_answer(["3"], "m90-01")
        self.assertEqual([], self.events(sess, "mock_answer"))
        exam.submit()
        exam.submit()
        rows = self.events(sess, "mock_answer")
        self.assertEqual(4, len(rows))
        self.assertEqual(3, sum(row["result"] == "blank" for row in rows))
        self.assertTrue(all(row["secs"] is None for row in rows))
        self.assertEqual(1, len(self.events(sess, "mock_question_returned")))

    def test_mock_input_before_consent_is_not_copied_on_later_submit(self):
        helper = mock_tests.MockServiceTest("test_unsubmitted_questions_do_not_enter_practice")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        sess = helper.session()
        sess.collection.set_enabled(False)
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(["BEFORE_CONSENT"], "m90-01")
        sess.collection.set_enabled(True)
        exam.save_answer(["BEFORE_CONSENT"], "m90-01")
        exam.save_answer(["3"], "m90-02")
        result = exam.submit()
        rows = self.events(sess, "mock_answer")
        self.assertEqual("not_collected", next(row["result"] for row in rows if row["card"] == "m90-01"))
        self.assertNotIn("BEFORE_CONSENT", json.dumps(rows))
        self.assertEqual("stuck", result["results"]["m90-01"])
        self.assertEqual(["BEFORE_CONSENT"], exam.draft["answers"]["m90-01"])

    def test_term_dictionary_revision_is_part_of_question_identity(self):
        sess = self.session()
        ps = service.PracticeSet(sess, "terms", "unit", ["i90-b01"], 3)
        first = ps._collection_item(ps.queue[0])["revision"]
        sess.collection_terms_revision = collection.digest([{"term": "changed"}])
        self.assertNotEqual(first, ps._collection_item(ps.queue[0])["revision"])


class CollectionCliTest(unittest.TestCase):
    def test_cli_requires_agreement_and_keeps_export_opt_in(self):
        parser = study.build_parser()
        args = parser.parse_args(["ai-data", "enable", "--user", "learner"])
        with tempfile.TemporaryDirectory() as root, mock.patch.dict(os.environ, {"STUDY_AI_HOME": root}):
            with mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                args.func(args)
            self.assertFalse((Path(root) / "learner" / collection.FILENAME).exists())
        self.assertFalse(parser.parse_args(["ai-data", "export"]).include_answers)


class DistributionPolicyTest(unittest.TestCase):
    setUp = CollectionTest.setUp
    def test_first_start_records_distribution_basis_once_without_claiming_consent_time(self):
        self.store.initialize_distribution()
        before = self.store.status()
        self.assertTrue(before["enabled"])
        self.store.initialize_distribution()
        self.assertEqual(before["epoch"], self.store.status()["epoch"])
        row = self.store.snapshot()[1]
        self.assertEqual("distribution-2026-11-11", row["data"]["basis"])
        self.assertIsNone(row["data"]["consent_at"])
        self.assertEqual(2, len(self.store.snapshot()))

    def test_stop_and_delete_survive_reopening_without_losing_user_choice(self):
        self.store.initialize_distribution()
        participant = self.store.status()["participant"]
        self.store.set_enabled(False)
        self.store.initialize_distribution()
        self.assertFalse(self.store.status()["enabled"])
        self.store.delete()
        reopened = collection.Collection(str(self.root / "private"), str(self.repo))
        reopened.initialize_distribution()
        self.assertFalse(os.path.exists(reopened.path))
        self.assertFalse(reopened.status()["enabled"])
        self.assertFalse(reopened.emit("answer", {"result":"pass"}))
        reopened.set_enabled(True)
        self.assertTrue(reopened.status()["enabled"])
        self.assertNotEqual(participant, reopened.status()["participant"])

    def test_failed_stop_commit_still_blocks_goal_updates(self):
        self.store.repository = study.ROOT
        self.store.initialize_distribution()
        reader = sqlite3.connect(self.store.path)
        try:
            reader.execute("BEGIN")
            reader.execute("SELECT * FROM meta").fetchall()
            with self.assertRaises(collection.CollectionError):
                self.store.set_enabled(False)
        finally:
            reader.rollback()
            reader.close()
        count = len(self.store.snapshot())
        self.assertFalse(self.store.status()["enabled"])
        with self.assertRaises(collection.CollectionError):
            self.store.set_goal("vision")
        self.assertEqual(count, len(self.store.snapshot()))
