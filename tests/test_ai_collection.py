# -*- coding: utf-8 -*-
"""추가 수집의 동의·보존·중복·내보내기와 실제 채점 연결을 확인함."""
import contextlib
import json
import os
import random
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
        with contextlib.closing(sqlite3.connect(sess.collection.path)) as conn:
            return [json.loads(r[0]) for r in conn.execute("SELECT payload FROM events WHERE kind=? ORDER BY seq", (kind,))]

    def test_correct_input_is_private_and_repeated_queries_are_deduplicated(self):
        sess = self.session()
        sess.collection.set_enabled(False)
        sess.mark_read("i90", "90a")
        sess.collection.set_enabled(True)
        sess.cards["i90-b01"]["level"] = 3
        ps = service.PracticeSet(sess, "private1", "unit", ["i90-b01"], 3)
        ps.current()
        ps.current()
        ps.answer(["반대"], 2.5, True)
        self.assertEqual(["반대"], self.events(sess, "answer")[0]["response"])
        self.assertNotIn("value", self.log(sess, "answer")[0])
        self.assertEqual(1, len(self.events(sess, "question_returned")))
        self.assertEqual([], self.events(sess, "learn"))
        snapshots = [row["item"] for row in sess.collection.snapshot() if row["kind"] in ("question_returned", "answer")]
        self.assertTrue(all(item["difficulty"] == 3 for item in snapshots))
        self.assertEqual(2, len(snapshots))
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

    def test_selection_trace_keeps_seeded_choices_and_actual_candidate_pools(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        state = sess._state()
        for mode in ("unit", "mixed", "lesson", "review", "sweep", "note"):
            kwargs = {"lesson": "i90", "unit": "90a"}
            if mode == "note":
                kwargs["card"] = "i90-b01"
            expected = service.build_set(sess, state, mode, random.Random(4), **kwargs)
            trace = {}
            actual = service.build_set(sess, state, mode, random.Random(4), trace=trace, **kwargs)
            self.assertEqual(expected, actual)
            self.assertEqual(actual, trace["selected"])
            self.assertTrue(set(actual) <= set(trace["candidate_ids"]))
            self.assertEqual(list(dict.fromkeys(cid for pool in trace["candidate_pools"] for cid in pool["ids"])),
                             trace["candidate_ids"])
            self.assertIsNone(trace["selection_probability"])
            self.assertEqual(collection.runtime_revision(), trace["runtime_revision"])
            self.assertEqual(set(actual), set(trace["selected_pools"]))
            self.assertEqual({cid: "learner_choice" if mode == "note" and cid == "i90-b01" else "rules"
                              for cid in actual}, trace["selected_sources"])
            self.assertEqual("learner_choice" if mode == "note" else "rules", trace["trigger"])

    def test_failed_stop_still_starts_new_collection_period_on_resume(self):
        from learning_server.dataset import prepare
        sess = self.session()
        sess.collection.set_enabled(True)
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=4)
        current = ps.current()
        epoch = sess.collection.status()["epoch"]
        with mock.patch.object(sess.collection, "_connect", side_effect=collection.CollectionError("locked")):
            with self.assertRaises(collection.CollectionError):
                sess.collection.set_enabled(False)
        sess.collection.set_enabled(True)
        self.assertNotEqual(epoch, sess.collection.status()["epoch"])
        ps.answer(self.right(ps, current), 3, False)
        self.assertIsNone(prepare(sess.collection.snapshot())[0]["prediction_at"])

    def test_note_trace_separates_requested_card_from_rule_selected_companion(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        state, trace = sess._state(), {}
        notes = ([{"items": [{"key": "i90-b01", "state": "wrong"},
                              {"key": "i90-b02", "state": "wrong"}]}], [])
        with mock.patch.object(state, "notes", return_value=notes):
            selected = service.build_set(sess, state, "note", random.Random(4), card="i90-b01", trace=trace)
        self.assertEqual({"i90-b01", "i90-b02"}, set(selected))
        self.assertEqual({"i90-b01": "learner_choice", "i90-b02": "rules"}, trace["selected_sources"])

    def test_real_practice_events_link_first_return_time_after_restore(self):
        from learning_server.dataset import prepare
        sess = self.session()
        sess.collection.set_enabled(True)
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=4)
        current = ps.current()
        first = next(row for row in sess.collection.snapshot() if row["kind"] == "question_returned")
        ps = service.PracticeSet.restore(sess, ps.snapshot())
        ps.current()
        ps.answer(self.right(ps, current), 3, False)
        row = prepare(sess.collection.snapshot())[0]
        self.assertEqual(first["at"], row["prediction_at"])
        self.assertEqual(first["event_id"], row["prediction_event"])

    def test_runtime_change_keeps_raw_answer_without_guessing_return_time(self):
        from learning_server.dataset import prepare
        sess = self.session()
        sess.collection.set_enabled(True)
        sess.mark_read('i90', '90a')
        with mock.patch.object(collection, 'runtime_revision', return_value='before-update'):
            practice = sess.start_set('unit', lesson='i90', unit='90a', seed=4)
            current = practice.current()
            saved = practice.snapshot()
        before = sess.collection.snapshot()
        first = next(row for row in before if row['kind'] == 'question_returned')
        with mock.patch.object(collection, 'runtime_revision', return_value='after-update'):
            restored = service.PracticeSet.restore(sess, saved)
            restored.current()
            restored.answer(self.right(restored, current), 3, False)
        after = sess.collection.snapshot()
        self.assertEqual(first, next(row for row in after if row['kind'] == 'question_returned'))
        answer = next(row for row in after if row['kind'] == 'answer')
        self.assertNotEqual(first['item_revision'], answer['item_revision'])
        prepared = prepare(after)[0]
        self.assertIsNone(prepared['prediction_at'])
        self.assertIsNone(prepared['prediction_event'])

    def test_mock_submission_records_missing_and_answered_items_once(self):
        helper = mock_tests.MockServiceTest("test_unsubmitted_questions_do_not_enter_practice")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        sess = helper.session()
        sess.collection.set_enabled(True)
        exam = sess.start_mock("m90", seed=1)
        for item in exam.items.values():
            item["level"] = 2
        exam.question()
        exam.question()
        exam.save_answer(["3"], "m90-01")
        self.assertEqual([], self.events(sess, "mock_answer"))
        exam.submit()
        exam.submit()
        rows = self.events(sess, "mock_answer")
        self.assertEqual(4, len(rows))
        self.assertEqual(3, sum(row["result"] == "blank" for row in rows))
        exported = [row["data"] for row in sess.collection.snapshot() if row["kind"] == "mock_answer"]
        self.assertEqual([row["card"] == "m90-01" for row in exported], [row["answered"] for row in exported])
        self.assertTrue(all("response" not in row for row in exported))
        self.assertTrue(all(row["secs"] is None for row in rows))
        self.assertEqual(1, len(self.events(sess, "mock_question_returned")))
        snapshots = [row["item"] for row in sess.collection.snapshot() if row["kind"] in ("mock_question_returned", "mock_answer")]
        self.assertEqual(5, len(snapshots))
        self.assertTrue(all(item["difficulty"] == 2 for item in snapshots))

    def test_mock_input_counts_only_persisted_changes_in_the_same_consent_period(self):
        helper = mock_tests.MockServiceTest("test_unsubmitted_questions_do_not_enter_practice")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        sess = helper.session()
        sess.collection.set_enabled(True)
        exam = sess.start_mock("m90", seed=1)
        cid = "m90-01"
        exam.save_answer([""], cid)
        exam.save_answer(["a"], cid, flush=False)
        exam.save_answer([""], cid)
        self.assertEqual([], self.events(sess, "ai_input"))
        exam.save_answer(["a"], cid, flush=False)
        exam.save_answer(["ab"], cid, flush=False)
        with mock.patch.object(study, "write_text", side_effect=OSError("full")), self.assertRaises(mock_tests.MockError):
            exam.save_answer(["abc"], cid)
        self.assertEqual([], self.events(sess, "ai_input"))
        exam.save_answer(["answer-marker"], cid)
        exam.save_answer(["answer-marker"], cid)
        sess.start_mock("m90").save_answer(["answer-marker"], cid)
        exam.save_answer(["b"], cid, flush=False)
        sess.collection.set_enabled(False)
        sess.collection.set_enabled(True)
        exam.move(0)
        rows = self.events(sess, "ai_input")
        self.assertEqual(1, len(rows))
        self.assertEqual({"input_schema", "card", "mock", "try", "course", "goal", "observed_at"}, set(rows[0]))
        self.assertEqual(1, rows[0]["input_schema"])
        exported = [r for r in sess.collection.snapshot() if r["kind"] == "ai_input"]
        self.assertNotIn("answer-marker", json.dumps(exported))
        self.assertIsNone(exported[0]["item_revision"])

    def test_real_mock_events_link_return_time_without_same_exam_labels(self):
        from learning_server.dataset import prepare
        helper = mock_tests.MockServiceTest("test_unsubmitted_questions_do_not_enter_practice")
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        sess = helper.session()
        sess.collection.set_enabled(True)
        exam = sess.start_mock("m90", seed=1)
        first = exam.question(0)
        exam.save_answer(["3"], first["card"])
        exam.submit()
        raw = sess.collection.snapshot()
        shown = next(row for row in raw if row["kind"] == "mock_question_returned")
        row = next(row for row in prepare(raw) if row["question_id"] == first["card"])
        self.assertEqual(shown["at"], row["prediction_at"])
        self.assertEqual(shown["event_id"], row["prediction_event"])
        self.assertEqual([], row["features"]["sequence_history"])

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
        self.assertNotIn("answered", next(row for row in rows if row["card"] == "m90-01"))
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
    def test_first_start_waits_for_explicit_choice_and_does_not_create_consent(self):
        self.store.initialize_distribution()
        before = self.store.status()
        self.assertFalse(before["enabled"])
        self.assertFalse(os.path.exists(self.store.path))
        self.store.set_enabled(True)
        before = self.store.status()
        self.store.initialize_distribution()
        self.assertEqual(before["epoch"], self.store.status()["epoch"])
        row = self.store.snapshot()[1]
        self.assertEqual("consent", row["kind"])
        self.assertEqual(2, len(self.store.snapshot()))

    def test_stop_and_delete_survive_reopening_without_losing_user_choice(self):
        self.store.initialize_distribution()
        self.store.set_enabled(True)
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
        self.store.set_enabled(True)
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
