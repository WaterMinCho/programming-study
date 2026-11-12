# -*- coding: utf-8 -*-
"""합성 프로필로 이관·재실행·되돌리기·철회의 저장 범위를 확인함."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from aiprep.collection import NOTICE, packed
from learning_server import app, dataset, legacy, operations
from learning_server.__main__ import main


class LegacyTransferTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="legacy_transfer_")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.path = self.root / "server/learning.sqlite3"
        self.database = app.Database(str(self.path))
        self.catalog = {"q": {"unit": "s01", "tags": ["loops"], "kind": "quiz", "type": "output"}}
        self.plan = {"format": 1, "timezone": "+09:00", "profiles": []}
        for index in range(4):
            source = self.root / ("source-%d" % index) / "profile.json"
            source.parent.mkdir()
            source.write_text(packed({"user": "private-person-%d" % index, "rounds": [], "attempts": [
                {"round": "r", "item": "q", "try": 1, "ok": True,
                 "at": "2026-01-01T10:00:00", "response": "private-answer-%d" % index},
                {"round": "r", "item": "q", "try": 2, "ok": False, "at": "2026-01-02T10:00:00"},
                {"round": "r", "item": "q", "try": 3, "ok": False, "at": None},
                {"round": "r", "item": "absent", "try": 1, "ok": False, "at": "2026-01-03T10:00:00"},
                {"round": "r", "item": "q", "try": 4, "ok": False, "at": None, "skipped": True}
            ]}), encoding="utf-8")
            self.plan["profiles"].append({"participant": str(uuid.uuid4()), "profile": str(source.relative_to(self.root)),
                                          "consent": {"confirmed_on": "2026-01-01", "evidence_ref": "private-evidence-%d" % index,
                                                      "private_server_transfer": True, "recommendation_research": True}})
        self.manifest = self.root / "plan.json"
        self.save_plan()

    def save_plan(self):
        self.manifest.write_text(packed(self.plan), encoding="utf-8")

    def transfer(self, **kwargs):
        return legacy.transfer(self.path, self.manifest, self.catalog, **kwargs)

    def rows(self):
        with self.database.connect() as db:
            return db.execute("SELECT payload FROM events ORDER BY participant, sequence").fetchall()

    def participant(self, index=0):
        return self.plan["profiles"][index]["participant"]

    def edit_profile(self, index, edit):
        source = self.root / self.plan["profiles"][index]["profile"]
        profile = json.loads(source.read_bytes())
        edit(profile)
        source.write_text(packed(profile), encoding="utf-8")

    def test_four_profiles_are_atomic_idempotent_and_keep_sources_unchanged(self):
        paths = [self.manifest] + [self.root / entry["profile"] for entry in self.plan["profiles"]]
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        first = self.transfer()
        saved = self.rows()
        second = self.transfer()
        self.assertEqual((4, 0, 16, 8), tuple(first[k] for k in ("inserted_profiles", "existing_profiles", "events", "answers")))
        self.assertEqual({"missing_time": 4, "unknown_question": 4, "skipped": 4}, first["omitted"])
        self.assertEqual((0, 4), (second["inserted_profiles"], second["existing_profiles"]))
        self.assertEqual(saved, self.rows())
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})
        self.assertEqual(4, operations.status(self.path)["active_accounts"])
        result_text = packed(first)
        for entry in self.plan["profiles"]:
            self.assertNotIn(entry["participant"], result_text)
            self.assertNotIn(entry["profile"], result_text)

    def test_provenance_preserves_unknowns_and_keeps_consent_out_of_events(self):
        self.transfer()
        events = [json.loads(row[0]) for row in self.rows()]
        answers = [row for row in events if row["kind"] == "answer"]
        prepared = dataset.prepare(events)
        self.assertEqual(4, len(prepared))
        for row in answers:
            self.assertIsNone(row["item_revision"])
            self.assertIsNone(row["data"]["observed_at"])
            self.assertIsNone(row["data"]["prediction_at"])
            self.assertEqual("current_catalog", row["data"]["provenance"]["concepts"])
            self.assertEqual("unknown", row["data"]["provenance"]["question_revision"])
            self.assertEqual("+09:00", row["data"]["provenance"]["timezone_assumption"])
            self.assertIsNone(row["data"]["goal"])
        text = packed(events)
        for private in ("private-person", "private-answer", "private-evidence", "source-", "token"):
            self.assertNotIn(private, text)
        with self.database.connect() as db:
            checksum, provenance, consent = db.execute(
                "SELECT source_sha256, provenance, consent FROM legacy_transfers WHERE participant=?", (self.participant(),)).fetchone()
        source = self.root / self.plan["profiles"][0]["profile"]
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), checksum)
        self.assertNotIn("consent", json.loads(provenance))
        self.assertEqual(self.plan["profiles"][0]["consent"], json.loads(consent))

    def test_dry_run_reads_existing_database_without_creating_ledger_or_key(self):
        before = (self.path.read_bytes(), Path(str(self.path) + ".key").read_bytes())
        result = self.transfer(dry_run=True)
        self.assertEqual("dry_run", result["status"])
        self.assertEqual(4, result["inserted_profiles"])
        self.assertEqual(before, (self.path.read_bytes(), Path(str(self.path) + ".key").read_bytes()))
        with self.database.connect() as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='legacy_transfers'").fetchone())
        absent = self.root / "missing/server.sqlite3"
        with self.assertRaises((OSError, ValueError)):
            legacy.transfer(absent, self.manifest, self.catalog)
        self.assertFalse(absent.parent.exists())
        Path(str(self.path) + ".key").unlink()
        with self.assertRaises(OSError):
            self.transfer()
        self.assertFalse(Path(str(self.path) + ".key").exists())

    def test_missing_either_consent_scope_rejects_whole_plan(self):
        for field in ("private_server_transfer", "recommendation_research", "evidence_ref", "confirmed_on"):
            with self.subTest(field=field):
                original = self.plan["profiles"][-1]["consent"].pop(field)
                self.save_plan()
                with self.assertRaises((KeyError, ValueError)):
                    self.transfer()
                self.plan["profiles"][-1]["consent"][field] = original
                self.assertEqual([], self.rows())

    def test_duplicate_source_or_participant_is_rejected_before_writing(self):
        original = copy.deepcopy(self.plan)
        for field in ("participant", "profile"):
            self.plan = copy.deepcopy(original)
            self.plan["profiles"][-1][field] = self.plan["profiles"][0][field]
            self.save_plan()
            with self.assertRaises(ValueError):
                self.transfer()
            self.assertEqual([], self.rows())

    def test_changed_source_catalog_timezone_or_consent_never_appends(self):
        self.transfer()
        saved = self.rows()
        catalog = copy.deepcopy(self.catalog)
        self.catalog["q"]["tags"] = ["other"]
        with self.assertRaises(ValueError):
            self.transfer()
        self.catalog = catalog
        for change in (lambda: self.plan.update(timezone="+08:00"),
                       lambda: self.plan["profiles"][0]["consent"].update(evidence_ref="changed")):
            plan = copy.deepcopy(self.plan)
            change()
            self.save_plan()
            with self.assertRaises(ValueError):
                self.transfer()
            self.plan = plan
        self.save_plan()
        self.edit_profile(0, lambda profile: profile["attempts"][0].update(ok=False))
        with self.assertRaises(ValueError):
            self.transfer()
        self.assertEqual(saved, self.rows())

    def test_later_conflict_rolls_back_earlier_new_profiles(self):
        with self.database.connect() as db:
            db.execute("INSERT INTO participants VALUES (?, ?, 'ordinary', '2026-01-01', 0)",
                       (self.participant(3), "ordinary-account"))
        with self.assertRaises(ValueError):
            self.transfer()
        self.assertEqual([], self.rows())
        self.assertEqual(1, operations.status(self.path)["active_accounts"])
        with self.database.connect() as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='legacy_transfers'").fetchone())

    def test_storage_failure_rolls_back_all_new_accounts_and_events(self):
        limit = self.database.storage_limit
        calls = 0
        def fail_later(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise app.ApiError(507, "storage limit")
            return limit(*args)
        with mock.patch.object(app.Database, "storage_limit", side_effect=fail_later):
            with self.assertRaises(app.ApiError):
                self.transfer()
        self.assertEqual([], self.rows())
        self.assertEqual(0, operations.status(self.path)["active_accounts"])

    def test_payload_tampering_and_external_revocation_are_not_successful_retries(self):
        self.transfer()
        saved = self.rows()
        with self.database.connect() as db:
            db.execute("UPDATE events SET payload='{}' WHERE participant=? AND sequence=1", (self.participant(),))
        with self.assertRaises(ValueError):
            self.transfer()
        self.assertEqual(len(saved), len(self.rows()))
        self.database.remove(self.participant(1))
        with self.assertRaises(ValueError):
            self.transfer(dry_run=True)

    def test_removal_is_scoped_repeatable_and_prevents_reimport(self):
        self.transfer()
        other = [row for row in self.rows() if json.loads(row[0])["participant"] != self.participant()]
        first = legacy.remove_transfer(self.path, self.participant(), reason="rollback")
        second = legacy.remove_transfer(self.path, self.participant(), reason="withdrawal")
        third = legacy.remove_transfer(self.path, self.participant(), reason="rollback")
        self.assertEqual(4, first["deleted_events"])
        self.assertEqual(0, second["deleted_events"])
        self.assertEqual("withdrawn", third["state"])
        self.assertEqual(other, self.rows())
        with self.database.connect() as db:
            self.assertEqual((1,), db.execute("SELECT revoked FROM participants WHERE participant=?", (self.participant(),)).fetchone())
            self.assertEqual((None, "withdrawn"), db.execute("SELECT consent, state FROM legacy_transfers WHERE participant=?", (self.participant(),)).fetchone())
        with self.assertRaises(ValueError):
            self.transfer()
        with self.assertRaises(ValueError):
            legacy.remove_transfer(self.path, str(uuid.uuid4()), reason="rollback")

    def test_server_only_cli_uses_explicit_catalog_without_importing_the_learning_app(self):
        catalog = self.root / "catalog.json"
        catalog.write_text(json.dumps(self.catalog), encoding="utf-8")
        argv = ["collector", "--db", str(self.path), "legacy-import", "--manifest", str(self.manifest), "--catalog", str(catalog)]
        output = io.StringIO()
        with mock.patch("sys.argv", argv), mock.patch.dict("sys.modules", {"adaptive": None}), contextlib.redirect_stdout(output):
            main()
        self.assertEqual(4, json.loads(output.getvalue())["inserted_profiles"])
        catalog.write_text('{"q": {"unit": "private-secret"}}', encoding="utf-8")
        error = io.StringIO()
        with mock.patch("sys.argv", argv), contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            main()
        self.assertNotIn("private-secret", error.getvalue())
        self.assertEqual(4, self.transfer()["existing_profiles"])

    def test_cli_reports_only_json_counts_and_sanitizes_failures(self):
        argv = ["collector", "--db", str(self.path), "legacy-import", "--manifest", str(self.manifest)]
        output = io.StringIO()
        with mock.patch("sys.argv", argv), mock.patch("adaptive.catalog", return_value=self.catalog), contextlib.redirect_stdout(output):
            main()
        self.assertEqual(4, json.loads(output.getvalue())["inserted_profiles"])
        error_output = io.StringIO()
        with mock.patch("sys.argv", argv), mock.patch("adaptive.catalog", side_effect=ValueError("private-secret-auth-key")), contextlib.redirect_stderr(error_output):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(1, error.exception.code)
        self.assertEqual({"status": "error", "code": "legacy_transfer_failed"}, json.loads(error_output.getvalue()))
        self.assertNotIn("private-secret-auth-key", error_output.getvalue())
        output = io.StringIO()
        argv = ["collector", "--db", str(self.path), "legacy-remove", "--participant", self.participant(), "--reason", "withdrawal"]
        with mock.patch("sys.argv", argv), contextlib.redirect_stdout(output):
            main()
        self.assertEqual({"status": "ok", "state": "withdrawn", "deleted_events": 4}, json.loads(output.getvalue()))
        self.assertEqual(12, len(self.rows()))

    def test_backup_carries_tombstones_and_rejects_reimport_after_restore(self):
        self.transfer()
        legacy.remove_transfer(self.path, self.participant(), reason="withdrawal")
        operations.backup(self.path, self.root / "backup")
        operations.restore(self.root / "backup", self.root / "restored")
        restored = self.root / "restored/learning.sqlite3"
        with self.assertRaises(ValueError):
            legacy.transfer(restored, self.manifest, self.catalog)
        if os.name != "nt":
            self.assertEqual(0o600, restored.stat().st_mode & 0o777)

    def test_concurrent_retries_do_not_duplicate_accounts_or_events(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.transfer(), range(2)))
        self.assertEqual(4, sum(result["inserted_profiles"] for result in results))
        self.assertEqual(4, sum(result["existing_profiles"] for result in results))
        self.assertEqual(16, len(self.rows()))

    def test_same_source_with_new_aliases_cannot_be_imported_twice(self):
        self.transfer()
        saved = self.rows()
        for entry in self.plan["profiles"]:
            entry["participant"] = str(uuid.uuid4())
        self.save_plan()
        with self.assertRaises(ValueError):
            self.transfer()
        self.assertEqual(saved, self.rows())

    def test_no_usable_timestamp_rejects_profile_without_inventing_events(self):
        self.edit_profile(3, lambda profile: [row.update(at=None) for row in profile["attempts"]])
        with self.assertRaises(ValueError):
            self.transfer()
        self.assertEqual([], self.rows())

    def test_existing_participant_limit_is_enforced(self):
        with mock.patch.object(app, "MAX_PARTICIPANT_EVENTS", 3):
            with self.assertRaises(app.ApiError):
                self.transfer()
        self.assertEqual([], self.rows())
        self.assertEqual(0, operations.status(self.path)["active_accounts"])

    def test_invalid_or_backwards_timezone_moments_cancel_the_whole_transfer(self):
        source = self.root / self.plan["profiles"][3]["profile"]
        original = source.read_bytes()
        for moment in ("invalid-time", "2025-12-31T10:00:00", "2026-01-01T10:30:00+14:00"):
            source.write_bytes(original)
            self.edit_profile(3, lambda profile: profile["attempts"][1].update(at=moment))
            with self.assertRaises(ValueError):
                self.transfer()
            self.assertEqual([], self.rows())

    def test_legacy_removal_and_app_authentication_stay_separate(self):
        ordinary = str(uuid.uuid4())
        token = self.database.enroll({"participant": ordinary, "invite": self.database.invites()[0], "notice": NOTICE})["token"]
        self.transfer()
        legacy.remove_transfer(self.path, self.participant(), reason="withdrawal")
        self.assertEqual(ordinary, self.database.authenticate("Bearer " + token))
        self.database.remove(ordinary)
        self.assertEqual(12, len(self.rows()))
        self.assertEqual(3, operations.status(self.path)["active_accounts"])


if __name__ == "__main__":
    unittest.main()
