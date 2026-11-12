# -*- coding: utf-8 -*-
"""기존 기록 이관·롤백·직접 삭제와 누적 용량의 정합을 확인함."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from learning_server import app, capacity, storage


class StorageCapacityTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / "data/db.sqlite3"
        self.database = app.Database(str(self.path))

    def event(self, db, participant="one", key="e", sequence=1, payload="한글"):
        db.execute("INSERT INTO events VALUES (?, 'ai', ?, ?, ?)", (participant, key, sequence, payload))

    def test_old_database_migration_preserves_unicode_events_and_latest_compressed_files(self):
        with self.database.connect() as db:
            self.event(db)
            db.execute("INSERT INTO api_submissions VALUES ('one','f',?, 'now',NULL,NULL,NULL)", (b"compressed",))
            db.execute("INSERT INTO api_submissions VALUES ('two','old',NULL, 'now',NULL,NULL,NULL)")
            before = db.execute("SELECT * FROM events").fetchall()
            for name in storage.TRIGGERS:
                db.execute("DROP TRIGGER " + name)
            db.execute("DROP TABLE storage_totals")
        migrated = app.Database(str(self.path))
        with migrated.connect() as db:
            self.assertEqual(before, db.execute("SELECT * FROM events").fetchall())
            self.assertEqual((1, 16), storage.usage(db))
            self.assertTrue(capacity.verify_totals(db))
        app.Database(str(self.path))
        with migrated.connect() as db:
            self.assertEqual((1, 16), storage.usage(db))

    def test_updates_replacements_deletes_and_rollback_keep_exact_counts(self):
        with self.database.connect() as db:
            self.event(db)
            db.execute("INSERT INTO api_submissions VALUES ('one','f',?, 'now',NULL,NULL,NULL)", (b"12345",))
            db.execute("UPDATE api_submissions SET payload=NULL")
            db.execute("UPDATE events SET participant='two',payload='짧은 글'")
            self.assertEqual((0, 0), storage.usage(db, "one"))
            self.assertEqual((1, len("짧은 글".encode())), storage.usage(db, "two"))
            self.assertTrue(capacity.verify_totals(db))
        with self.assertRaises(sqlite3.IntegrityError), self.database.connect() as db:
            self.event(db, "one", "new", 2)
            self.event(db, "one", "new", 3)
        with self.database.connect() as db:
            self.assertTrue(capacity.verify_totals(db))
            db.execute("DELETE FROM events")
            db.execute("DELETE FROM api_submissions")
            self.assertEqual((0, 0), storage.usage(db))
            self.assertTrue(capacity.verify_totals(db))

    def test_normal_quota_reads_use_primary_keys_without_scanning_payloads(self):
        with self.database.connect() as db:
            self.event(db)
            queries = []
            db.set_trace_callback(queries.append)
            self.database.storage_limit(db, "one", 1)
            self.assertEqual(2, len(queries))
            self.assertFalse(any("sum(" in query.lower() for query in queries))
            plan = db.execute("EXPLAIN QUERY PLAN SELECT events,bytes FROM storage_totals WHERE participant=?", ("",)).fetchall()
            self.assertTrue(all("SEARCH" in row[3] for row in plan))

    def test_concurrent_writes_cannot_exceed_global_quota_and_rollback_counters(self):
        def write(index):
            try:
                with self.database.connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    self.database.storage_limit(db, str(index), 10, 1)
                    self.event(db, str(index), str(index), 1, "1234567890")
                return True
            except app.ApiError as error:
                self.assertEqual(507, error.status)
                return False
        with mock.patch.object(app, "MAX_STORED_BYTES", 30), ThreadPoolExecutor(max_workers=6) as pool:
            accepted = list(pool.map(write, range(10)))
        self.assertEqual(3, sum(accepted))
        with self.database.connect() as db:
            self.assertEqual((3, 30), storage.usage(db))
            self.assertTrue(capacity.verify_totals(db))

    def test_capacity_includes_backups_and_flags_counter_drift_without_changing_records(self):
        backup = self.root / "backup.bin"
        backup.write_bytes(b"x" * (2 * 1024 * 1024))
        result = capacity.report(self.path, self.root, 1, verify=True)
        self.assertIn("disk_capacity", result["warnings"])
        self.assertTrue(result["counter_verified"])
        with self.database.connect() as db:
            db.execute("UPDATE storage_totals SET bytes=1 WHERE participant=''")
        result = capacity.report(self.path, self.root, 10, verify=True)
        self.assertIn("counter_mismatch", result["warnings"])
        self.assertEqual(b"x" * (2 * 1024 * 1024), backup.read_bytes())
        with self.assertRaises(ValueError):
            capacity.report(self.path, self.root / "other", 10)

    def test_missing_counter_trigger_is_not_silently_trusted(self):
        with self.database.connect() as db:
            db.execute("DROP TRIGGER storage_events_insert")
        with self.assertRaises(ValueError):
            app.Database(str(self.path))

    def test_disappearing_temporary_files_do_not_drop_the_capacity_report(self):
        temporary = self.root / "temporary-journal"
        temporary.write_bytes(b"temporary")
        original = Path.lstat
        def disappear(path, *args, **kwargs):
            if path == temporary:
                raise FileNotFoundError()
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "lstat", autospec=True, side_effect=disappear):
            result = capacity.report(self.path, self.root, 512)
        self.assertEqual(1, result["vanished_during_scan"])
        self.assertEqual("ok", result["status"])
        self.assertTrue(temporary.exists())
