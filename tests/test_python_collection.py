# -*- coding: utf-8 -*-
"""파이썬 입력의 동의 경계·채점 중 변경·중복과 기존 기록 보존을 확인함."""
import os
from pathlib import Path
import unittest
from unittest import mock

import adaptive
from aiprep.collection import Collection, CollectionError
from python_collection import PythonCollection
from tests import test_session as fixtures

right_answer = fixtures.right_answer
wrong_answer = fixtures.wrong_answer


class PythonCollectionTest(unittest.TestCase):
    make_round = fixtures.SessionTest.make_round

    def setUp(self):
        fixtures.SessionTest.setUp(self)
        self.store = self.sess.collection = PythonCollection(str(Path(self.tmp) / "private"), adaptive.study.ROOT)

    tearDown = fixtures.SessionTest.tearDown

    def item(self, kind="quiz"):
        key = next(key for key, item in self.sess.cat.items() if item["kind"] == kind)
        self.make_round("r90", [key])
        return self.sess.open_round("r90")["items"][0]

    def rows(self, kind="answer"):
        return [row for row in self.store.snapshot(include_answers=True)[1:] if row["kind"] == kind]

    def test_default_off_preserves_existing_answer_and_profile(self):
        item = self.item()
        self.sess.set_answer("r90", item["id"], right_answer(self.sess, item))
        self.sess.grade("r90")
        self.assertFalse(Path(self.store.path).exists())
        self.assertEqual("ok", self.sess._round("r90")["results"][item["key"]])

    def test_unchanged_preconsent_answer_is_not_imported(self):
        item = self.item()
        value = right_answer(self.sess, item)
        self.sess.set_answer("r90", item["id"], value)
        self.store.set_enabled(True)
        self.sess.set_answer("r90", item["id"], value)
        self.sess.grade("r90")
        self.assertEqual([], self.rows())
        self.assertEqual([], self.rows("python_input"))

    def test_goal_at_input_and_first_attempt_survive_save_and_regrade(self):
        item = self.item()
        self.store.set_enabled(True)
        self.store.set_goal("vision")
        self.store.returned(self.sess, "r90", item["id"])
        self.sess.set_answer("r90", item["id"], right_answer(self.sess, item))
        self.store.set_goal("arm")
        self.sess.grade("r90")
        first = self.rows()[0]
        self.assertEqual("python", first["track"])
        self.assertEqual("vision", first["data"]["goal"]["goal_id"])
        self.assertIsNotNone(first["data"]["prediction_at"])
        self.assertTrue(first["data"]["first_in_set"])
        before = len(self.store.snapshot())
        self.sess.grade("r90")
        self.assertEqual(before, len(self.store.snapshot()))
        self.sess.set_answer("r90", item["id"], wrong_answer(item))
        self.sess.grade("r90")
        self.assertEqual(2, len(self.rows()))
        self.assertFalse(self.rows()[-1]["data"]["first_in_set"])
        exported = self.store.snapshot()
        self.assertTrue(all("response" not in row["data"] for row in exported[1:]))

    def test_reconsent_and_external_edits_do_not_acquire_old_input(self):
        item = self.item()
        self.store.set_enabled(True)
        self.sess.set_answer("r90", item["id"], right_answer(self.sess, item))
        self.store.set_enabled(False)
        self.store.set_enabled(True)
        self.sess.grade("r90")
        self.assertEqual([], self.rows())
        self.sess.set_answer("r90", item["id"], wrong_answer(item))
        self.sess._write_quiz(self.sess._round("r90"), {item["id"]: right_answer(self.sess, item)})
        self.sess.grade("r90")
        self.assertEqual([], self.rows())

    def test_edit_during_grading_does_not_label_new_answer_with_old_result(self):
        item = self.item()
        self.store.set_enabled(True)
        self.sess.set_answer("r90", item["id"], right_answer(self.sess, item))
        original = adaptive.grade_round
        def change(*args):
            result = original(*args)
            self.sess.set_answer("r90", item["id"], wrong_answer(item))
            return result
        with mock.patch.object(adaptive, "grade_round", side_effect=change):
            self.sess.grade("r90")
        self.assertEqual([], self.rows())

    def test_code_starter_and_collection_failure_do_not_block_grading(self):
        item = self.item("code")
        self.store.set_enabled(True)
        self.sess.reset_item("r90", item["id"])
        self.assertEqual([], self.rows("python_input"))
        self.sess.set_answer("r90", item["id"], right_answer(self.sess, item))
        with mock.patch.object(self.store, "_connect", side_effect=CollectionError("실패")):
            self.sess.grade("r90")
        self.assertEqual("ok", self.sess._round("r90")["results"][item["key"]])
        self.assertEqual([], self.rows())

    def test_external_write_and_restore_during_grading_is_not_a_stable_snapshot(self):
        item = self.item()
        self.store.set_enabled(True)
        self.sess.set_answer("r90", item["id"], right_answer(self.sess, item))
        original = adaptive.grade_round
        def change(*args):
            result = original(*args)
            path = Path(self.sess.folder("r90")) / "quiz.py"
            stat = path.stat()
            raw = path.read_bytes()
            path.write_bytes(raw + b"\n")
            path.write_bytes(raw)
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10000000))
            return result
        with mock.patch.object(adaptive, "grade_round", side_effect=change):
            self.sess.grade("r90")
        self.assertEqual([], self.rows())

    def test_python_database_cannot_be_opened_as_ai(self):
        self.store.set_enabled(True)
        other = Collection(str(Path(self.store.path).parent), adaptive.study.ROOT)
        self.assertTrue(other.status()["error"])
        self.assertEqual("python", self.store.snapshot()[0]["track"])
