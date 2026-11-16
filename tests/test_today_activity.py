# -*- coding: utf-8 -*-
"""채점 시점의 계정·동의 표식이 과거 기록과 내보내기에 섞이지 않는지 확인함."""
import contextlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from learning_data.collection import Collection


class DailyStudyTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.activity = {"identity": "a" * 64, "choice": "11111111-1111-4111-8111-111111111111"}
        self.callback = mock.Mock(side_effect=lambda: dict(self.activity))
        self.store = Collection(self.root / "private", self.repo, activity_identity=self.callback)
        clock = mock.patch("learning_data.collection.stamp", return_value="2026-11-16T14:59:00+00:00")
        self.clock = clock.start()
        self.addCleanup(clock.stop)

    def answer(self, **changes):
        return dict({"card": "fixture-card", "answered": True, "result": "pass"}, **changes)

    def marker(self, date="2026-11-16"):
        return dict(self.activity, date=date)

    def test_missing_or_stopped_collection_never_calls_identity_or_creates_a_file(self):
        self.assertEqual({}, self.store.daily_study())
        self.assertFalse(self.store.emit("answer", self.answer()))
        self.assertFalse(Path(self.store.path).exists())
        self.store.set_enabled(True)
        self.assertTrue(self.store.emit("answer", self.answer()))
        self.assertEqual(self.marker(), self.store.daily_study())
        self.store.set_enabled(False)
        self.callback.reset_mock()
        self.assertEqual({}, self.store.daily_study())
        self.assertFalse(self.store.emit("answer", self.answer()))
        self.callback.assert_not_called()
        self.store.set_enabled(True)
        self.assertEqual({}, self.store.daily_study())

    def test_new_event_uses_emission_identity_and_choice_without_relabelling_old_events(self):
        self.store.set_enabled(True)
        with self.store._connect() as conn:
            conn.executescript("""
                CREATE TABLE marker_writes(value TEXT);
                CREATE TRIGGER count_marker AFTER INSERT ON meta WHEN NEW.key='daily_study'
                BEGIN INSERT INTO marker_writes VALUES (NEW.value); END;
            """)
        self.store.emit("answer", self.answer(), key="first")
        original = self.marker()
        self.store.emit("answer", self.answer(), key="second")
        with self.store._connect() as conn:
            self.assertEqual(1, conn.execute("SELECT count(*) FROM marker_writes").fetchone()[0])
        self.activity["identity"] = "b" * 64
        self.assertEqual(original, self.store.daily_study())
        self.callback.reset_mock()
        self.assertTrue(self.store.emit("answer", self.answer(), key="first"))
        self.callback.assert_not_called()
        self.assertEqual(original, self.store.daily_study())
        self.store.emit("answer", self.answer(), key="third")
        self.assertEqual(self.marker(), self.store.daily_study())
        previous_choice = self.marker()
        self.activity["choice"] = "22222222-2222-4222-8222-222222222222"
        self.assertEqual(previous_choice, self.store.daily_study())
        self.store.emit("answer", self.answer(), key="fourth")
        self.assertEqual(self.marker(), self.store.daily_study())
        self.clock.return_value = "2026-11-16T15:00:00+00:00"
        self.store.emit("answer", self.answer(), key="next-day")
        self.assertEqual(self.marker("2026-11-17"), self.store.daily_study())
        with self.store._connect() as conn:
            self.assertEqual(4, conn.execute("SELECT count(*) FROM marker_writes").fetchone()[0])

    def test_only_current_answered_grades_mark_activity(self):
        for track, kind, result in (("ai", "answer", "pass"), ("ai", "answer", "partial"),
                                    ("ai", "answer", "stuck"), ("ai", "mock_answer", "pass"),
                                    ("ai", "mock_answer", "stuck"), ("python", "answer", "ok"),
                                    ("python", "answer", "wrong")):
            with self.subTest(track=track, kind=kind, result=result):
                store = Collection(self.root / (track + kind + result), self.repo, track, activity_identity=self.callback)
                store.set_enabled(True)
                self.assertTrue(store.emit(kind, self.answer(result=result), at="2026-11-16T23:58:59+09:00"))
                self.assertEqual(self.marker(), store.daily_study())
        self.store.set_enabled(True)
        excluded = [("legacy_answer", self.answer()), ("question_returned", self.answer()),
                    ("mock_submit", self.answer()), ("mock_answer", self.answer(result="partial"))]
        excluded += [("answer", self.answer(**changes)) for changes in (
            {"card": " "}, {"card": None}, {"card": 1}, {"answered": False}, {"answered": 1},
            {"answered": "true"}, {"dontknow": True}, {"result": "blank"}, {"result": "not_collected"},
            {"result": "ok"}, {"result": {}}, {"synthetic": True}, {"synthetic": "false"},
            {"provenance": {"kind": "legacy_profile"}}, {"response": [" "]},
            {"source_at": "2026-11-15T23:59:59+09:00"}, {"source_at": "2026-11-16T23:59:01+09:00"},
            {"source_at": "2026-11-16T23:58:00"}, {"source_at": "unknown"}, {"source_at": None})]
        missing = self.answer()
        missing.pop("answered")
        excluded.append(("answer", missing))
        self.callback.reset_mock()
        for kind, payload in excluded:
            with self.subTest(kind=kind, payload=payload):
                self.assertTrue(self.store.emit(kind, payload))
                self.assertEqual({}, self.store.daily_study())
        self.callback.assert_not_called()

    def test_old_consent_context_and_failed_insert_do_not_mark_activity(self):
        self.store.set_enabled(True)
        context = self.store.observation_context()
        self.store.set_enabled(False)
        self.store.set_enabled(True)
        self.assertTrue(self.store.emit("mock_answer", self.answer(response=["fixture"]), observation_context=context))
        self.assertEqual({}, self.store.daily_study())
        self.assertFalse(self.store.emit("answer", self.answer(bad=float("nan"))))
        self.assertEqual({}, self.store.daily_study())
        self.callback.assert_not_called()

    def test_bad_or_failing_identity_callback_does_not_lose_the_grade(self):
        self.store.set_enabled(True)
        invalid = [None, "a" * 64, {}, {"identity": "not-a-fingerprint", "choice": self.activity["choice"]},
                   {"identity": "a" * 64}, dict(self.activity, choice="not-a-uuid"), dict(self.activity, extra="no")]
        self.callback.side_effect = None
        for index, value in enumerate(invalid):
            with self.subTest(index=index):
                self.callback.return_value = value
                self.assertTrue(self.store.emit("answer", self.answer()))
                self.assertEqual({}, self.store.daily_study())
        self.callback.side_effect = RuntimeError("fixture callback failure")
        self.assertTrue(self.store.emit("answer", self.answer()))
        self.assertEqual(len(invalid) + 1, self.store.status()["events"])
        self.assertEqual(0, self.store.missed)
        self.assertEqual({}, self.store.daily_study())

    def test_marker_is_local_metadata_and_reading_never_scans_or_writes_events(self):
        self.store.set_enabled(True)
        self.store.emit("answer", self.answer())
        statements = []
        connect = self.store._connect
        @contextlib.contextmanager
        def traced(*args, **kwargs):
            with connect(*args, **kwargs) as conn:
                conn.set_trace_callback(statements.append)
                changes = conn.total_changes
                yield conn
                self.assertEqual(changes, conn.total_changes)
        with mock.patch.object(self.store, "_connect", traced), mock.patch.object(self.store, "snapshot", side_effect=AssertionError):
            self.assertEqual(self.marker(), self.store.daily_study())
        self.assertFalse(any("events" in sql.lower() or "items" in sql.lower() for sql in statements))
        destination = self.root / "export.jsonl"
        self.store.export(destination)
        for output in (destination.read_text(encoding="utf-8"), json.dumps(self.store.snapshot(include_answers=True))):
            for private in ("daily_study", self.activity["identity"], self.activity["choice"]):
                self.assertNotIn(private, output)
        for value in ("bad-json", "[]", json.dumps(dict(self.marker(), choice="invalid")),
                      json.dumps(dict(self.marker(), date="invalid")), json.dumps(dict(self.marker(), extra=True))):
            with sqlite3.connect(self.store.path) as conn:
                conn.execute("UPDATE meta SET value=? WHERE key='daily_study'", (value,))
            self.assertEqual({}, self.store.daily_study())


if __name__ == "__main__":
    unittest.main()
