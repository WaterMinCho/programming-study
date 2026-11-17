# -*- coding: utf-8 -*-
"""채점한 곳마다 오늘 계정 집계를 알리고, 학습 기록 수집과는 섞이지 않는지 확인함."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import adaptive
import study
from aiprep import service
from learning_data.collection import Collection
from python_collection import PythonCollection
from tests import test_journey_service, test_session
from tests.test_ai_service import Base as AiBase, FIXTURE


class CollectionMarkTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.callback = mock.Mock()
        self.store = Collection(self.root / "private", self.repo, activity_mark=self.callback)

    def answer(self, **changes):
        return dict({"card": "fixture-card", "result": "pass", "response": ["값"]}, **changes)

    def test_mark_reaches_the_counter_with_or_without_research_collection(self):
        # 예전에는 수집 중인 기기에서만 표식을 남겼음. 지금은 수집 파일이 없거나 꺼져 있어도 알림.
        self.store.mark_graded()
        self.assertFalse(Path(self.store.path).exists())
        self.store.set_enabled(True)
        self.store.mark_graded()
        self.store.set_enabled(False)
        self.store.mark_graded()
        self.assertEqual(3, self.callback.call_count)
        Collection(self.root / "other", self.repo).mark_graded()

    def test_emit_no_longer_writes_a_marker_into_research_records(self):
        # 예전에는 채점 기록과 같은 파일에 계정 지문·선택 구분값을 남겼음. 지금은 수집 기록에 아무것도 남기지 않음.
        self.store.set_enabled(True)
        with self.store._connect() as conn:
            conn.executescript("""
                CREATE TABLE marker_writes(value TEXT);
                CREATE TRIGGER count_marker AFTER INSERT ON meta WHEN NEW.key='daily_study'
                BEGIN INSERT INTO marker_writes VALUES (NEW.value); END;
            """)
        self.assertTrue(self.store.emit("answer", self.answer(), key="first"))
        self.assertTrue(self.store.emit("mock_answer", self.answer(), key="second"))
        with self.store._connect() as conn:
            self.assertEqual(0, conn.execute("SELECT count(*) FROM marker_writes").fetchone()[0])
            conn.execute("INSERT INTO meta VALUES ('daily_study', ?)", (json.dumps({"identity": "a" * 64}),))
        self.callback.assert_not_called()
        self.store.set_enabled(False)
        self.store.set_enabled(True)
        destination = self.root / "export.jsonl"
        self.store.export(destination)
        for output in (destination.read_text(encoding="utf-8"), json.dumps(self.store.snapshot(include_answers=True))):
            self.assertNotIn("daily_study", output)
            self.assertNotIn("a" * 64, output)
        with self.store._connect() as conn:
            self.assertIsNone(conn.execute("SELECT value FROM meta WHERE key='daily_study'").fetchone())

    def test_failing_callback_does_not_lose_the_grade(self):
        self.store.set_enabled(True)
        self.callback.side_effect = RuntimeError("fixture callback failure")
        self.store.mark_graded()
        self.assertTrue(self.store.emit("answer", self.answer()))
        self.assertEqual(1, self.store.status()["events"])
        self.assertEqual(0, self.store.missed)


class AiMarkTest(AiBase):
    def session(self):
        sess = super().session()
        self.marks = mock.Mock()
        sess.collection.activity_mark = self.marks
        return sess

    def test_practice_answer_marks_without_research_consent_but_dont_know_does_not(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        self.assertFalse(os.path.exists(sess.collection.path))
        ps = service.PracticeSet(sess, "today1", "unit", ["i90-b01"], 3)
        ps.dont_know(2)
        self.marks.assert_not_called()
        other = service.PracticeSet(sess, "today2", "unit", ["i90-b01"], 3)
        other.answer([""], 1, False)
        self.marks.assert_not_called()
        again = service.PracticeSet(sess, "today3", "unit", ["i90-b01"], 3)
        again.answer(["다른 답"], 1, False)
        self.marks.assert_called_once()
        self.assertFalse(os.path.exists(sess.collection.path))

    def test_broken_research_record_still_marks(self):
        # 예전에는 수집 저장이 실패하면 표식을 남기지 않았음. 지금은 수집과 따로 알림.
        sess = self.session()
        sess.collection.set_enabled(True)
        Path(sess.collection.path).write_bytes(b"broken")
        sess.mark_read("i90", "90a")
        service.PracticeSet(sess, "today4", "unit", ["i90-b01"], 3).answer(["반대"], 1, True)
        self.marks.assert_called_once()
        self.assertTrue(sess.collection.status()["error"])


class MockMarkTest(AiBase):
    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, self.root)
        index_path = os.path.join(self.root, "index.json")
        index = study.read_json(index_path)
        index["mocks"][0]["count"] = 1
        study.write_text(index_path, json.dumps(index, ensure_ascii=False))
        folder = Path(self.root) / "mocks/m90"
        (folder / "work").mkdir(parents=True)
        (folder / "meta.json").write_text("{}", encoding="utf-8")
        items = [{"id": "m90-01", "kind": "blank", "lesson": "i90", "unit": "90a", "step": "90a/1",
                  "stem": "숫자를 쓰세요: ____", "blanks": [{"answer": ["3"], "mode": "number"}],
                  "explain": "정답은 3입니다.", "ref": ["검증 기록"]}]
        (folder / "work/items.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")

    def test_submit_marks_only_when_an_answer_was_graded(self):
        sess = self.session()
        sess.collection.activity_mark = marks = mock.Mock()
        sess.start_mock("m90", seed=1).submit()
        marks.assert_not_called()
        retry = sess.start_mock("m90", repeat=True, seed=2)
        retry.save_answer(["4"], "m90-01")
        retry.submit()
        retry.submit()
        marks.assert_called_once()


class PythonMarkTest(unittest.TestCase):
    make_round = test_session.SessionTest.make_round

    def setUp(self):
        test_session.SessionTest.setUp(self)
        self.sess.collection = PythonCollection(str(Path(self.tmp) / "private"), adaptive.study.ROOT)
        self.marks = self.sess.collection.activity_mark = mock.Mock()

    tearDown = test_session.SessionTest.tearDown

    def test_grade_marks_new_answers_but_not_untouched_or_unchanged_rounds(self):
        key = next(key for key, item in self.sess.cat.items() if item["kind"] == "quiz")
        self.make_round("r90", [key])
        item = self.sess.open_round("r90")["items"][0]
        self.sess.grade("r90")
        self.marks.assert_not_called()
        self.sess.set_answer("r90", item["id"], test_session.wrong_answer(item))
        self.sess.grade("r90")
        self.assertEqual(1, self.marks.call_count)
        self.sess.grade("r90")
        self.assertEqual(1, self.marks.call_count)
        self.sess.set_answer("r90", item["id"], test_session.right_answer(self.sess, item))
        self.sess.grade("r90")
        self.assertEqual(2, self.marks.call_count)
        self.assertFalse(Path(self.sess.collection.path).exists())


class JourneyMarkTest(test_journey_service.Base):
    def result(self):
        return {"cancelled": False, "score": 40.0, "acc": 40.0, "eff": 0.0, "passed": False,
                "tests": [1, 1, 0, 0], "fatal": None}

    def test_grade_marks_only_edited_code(self):
        journey = self.session()
        journey.activity_mark = marks = mock.Mock()
        with mock.patch("journey.service.grading.grade", side_effect=lambda *args, **kwargs: self.result()):
            journey.grade("t01", "p1", "python")
            marks.assert_not_called()
            journey.save_code("t01", "p1", "python", "def solution(nums):\n    return 0\n")
            journey.grade("t01", "p1", "python")
            marks.assert_called_once()
            with mock.patch("journey.service.grading.grade", return_value=dict(self.result(), cancelled=True)):
                journey.grade("t01", "p1", "python")
            marks.assert_called_once()
        self.assertEqual(2, len(self.read_log()))

    def test_failing_callback_keeps_the_grade_record(self):
        journey = self.session()
        journey.activity_mark = mock.Mock(side_effect=RuntimeError("fixture callback failure"))
        journey.save_code("t01", "p1", "python", "def solution(nums):\n    return 0\n")
        with mock.patch("journey.service.grading.grade", return_value=self.result()):
            journey.grade("t01", "p1", "python")
        self.assertEqual(1, len(self.read_log()))


if __name__ == "__main__":
    unittest.main()
