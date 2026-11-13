# -*- coding: utf-8 -*-
"""과거 AI 판정 보관과 학습 입력 제외·재실행·철회를 확인함."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest import mock

from aiprep.collection import packed
from learning_server import app, capacity, dataset, legacy, legacy_ai
from learning_server.__main__ import main


class LegacyAiTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="legacy_ai_")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.path = self.root / "server/learning.sqlite3"
        self.database = app.Database(str(self.path))
        self.source = self.root / "original/record.json"
        self.source.parent.mkdir()
        self.source.write_text(packed({"log": [
            {"kind": "answer", "card": "q1", "set": "s", "again": 0, "result": "pass", "at": "2026-01-01T12:00:00", "value": "private-answer"},
            {"kind": "answer", "card": "q2", "set": "s", "again": 1, "result": "partial", "at": None, "secs": 0, "picked": "private-pick"},
            {"kind": "read", "card": "q3"}
        ]}), encoding="utf-8")
        self.plan = {"format": 1, "archived_at": "2026-11-12T16:00:00+09:00", "profiles": [
            {"participant": str(uuid.uuid4()), "record": "original/record.json",
             "consent": {"confirmed_on": "2026-11-12", "evidence_ref": "private-evidence",
                         "private_server_transfer": True, "recommendation_research": True}}]}
        self.manifest = self.root / "plan.json"
        self.save()

    def save(self):
        self.manifest.write_text(packed(self.plan), encoding="utf-8")

    def transfer(self, **kwargs):
        return legacy_ai.transfer(self.path, self.manifest, **kwargs)

    def events(self):
        with self.database.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM events ORDER BY sequence")]

    def test_replay_preserves_sources_partial_and_unknowns_without_training_leak(self):
        original = self.source.read_bytes()
        first = self.transfer()
        second = self.transfer()
        self.assertEqual((1, 2, 2), tuple(first[key] for key in ("inserted_profiles", "events", "answers")))
        self.assertEqual((0, 1), (second["inserted_profiles"], second["existing_profiles"]))
        events = self.events()
        self.assertEqual(["pass", "partial"], [row["data"]["result"] for row in events])
        self.assertEqual([], dataset.prepare(events))
        relabelled = copy.deepcopy(events)
        for row in relabelled:
            row["kind"] = "answer"
        self.assertEqual([], dataset.prepare(relabelled))
        self.assertEqual(self.plan["archived_at"], events[0]["at"])
        self.assertIsNone(events[1]["data"]["original_at"])
        self.assertEqual(0, events[1]["data"]["original_secs"])
        for row in events:
            self.assertIsNone(row["item_revision"])
            self.assertIsNone(row["data"]["prediction_at"])
            self.assertIsNone(row["data"]["course"])
            self.assertFalse(row["data"]["training_eligible"])
            self.assertEqual("archived_at", row["data"]["provenance"]["at_meaning"])
        for private in ("private-answer", "private-pick", "private-evidence", "original/", "token"):
            self.assertNotIn(private, packed(events))
        self.assertEqual(original, self.source.read_bytes())
        self.assertTrue(capacity.report(self.path, self.root, 512, verify=True)["counter_verified"])

    def test_dry_run_and_cli_leave_database_and_key_unchanged(self):
        key = Path(str(self.path) + ".key")
        before = (self.path.read_bytes(), key.read_bytes())
        with mock.patch("sys.argv", ["server", "--db", str(self.path), "legacy-ai-import", "--manifest", str(self.manifest), "--dry-run"]):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                main()
        self.assertEqual("dry_run", json.loads(output.getvalue())["status"])
        self.assertEqual(before, (self.path.read_bytes(), key.read_bytes()))

    def test_missing_consent_duplicate_and_unknown_result_reject_before_write(self):
        original = copy.deepcopy(self.plan)
        for field in ("private_server_transfer", "recommendation_research", "evidence_ref", "confirmed_on"):
            self.plan = copy.deepcopy(original)
            del self.plan["profiles"][0]["consent"][field]
            self.save()
            with self.assertRaises((KeyError, ValueError)):
                self.transfer()
        self.plan = copy.deepcopy(original)
        self.plan["profiles"].append(copy.deepcopy(self.plan["profiles"][0]))
        self.save()
        with self.assertRaises(ValueError):
            self.transfer()
        self.plan = original
        self.save()
        record = json.loads(self.source.read_bytes())
        record["log"][0]["result"] = "unknown"
        self.source.write_text(packed(record), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.transfer()
        self.assertEqual([], self.events())

    def test_changed_archive_time_conflicts_and_withdrawal_prevents_reimport(self):
        self.transfer()
        self.plan["archived_at"] = "2026-11-12T17:00:00+09:00"
        self.save()
        with self.assertRaises(ValueError):
            self.transfer()
        self.plan["archived_at"] = "2026-11-12T16:00:00+09:00"
        self.save()
        legacy.remove_transfer(self.path, self.plan["profiles"][0]["participant"], reason="withdrawal")
        self.assertEqual([], self.events())
        with self.assertRaises(ValueError):
            self.transfer()
        self.assertTrue(capacity.report(self.path, self.root, 512, verify=True)["counter_verified"])

    def test_quota_failure_preserves_existing_database(self):
        with mock.patch.object(app.Database, "storage_limit", side_effect=app.ApiError(507, "storage limit")):
            with self.assertRaises(app.ApiError):
                self.transfer()
        self.assertEqual([], self.events())
        with self.database.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants").fetchone()[0])
        self.assertTrue(capacity.report(self.path, self.root, 512, verify=True)["counter_verified"])

    def test_corrections_and_duplicate_attempts_require_separate_review(self):
        original = json.loads(self.source.read_bytes())
        for extra in ({"kind": "override", "card": "q1"}, original["log"][0]):
            record = copy.deepcopy(original)
            record["log"].append(extra)
            self.source.write_text(packed(record), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.transfer()
            self.assertEqual([], self.events())
