# -*- coding: utf-8 -*-
"""기기 확인·권한 분리와 집계의 원본 보존을 확인함."""
import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from learning_server.app import ApiError, Database
from learning_server.team import Access, KST, initialize


class AccessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = Database(str(Path(self.tmp.name) / "data.sqlite3"))
        self.calls = []
        self.account = 101
        self.revoke_error = False
        self.access = Access(self.database, self.github)
        self.env = mock.patch.dict("os.environ", {"STUDY_IDENTITY_CLIENT_ID": "client123", "STUDY_IDENTITY_CLIENT_SECRET": "test-secret",
                                                "STUDY_TEAM_MEMBER_HASHES": ",".join(self.access.digest("member:" + str(n)) for n in (101, 102, 103, 104))})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.data = {"access_token": "gho_" + "x" * 36, "nonce": "a" * 64}

    def github(self, method, cid, secret, token):
        self.calls.append(method)
        if method == "DELETE":
            if self.revoke_error:
                raise OSError("unavailable")
            return {}
        return {"app": {"client_id": cid}, "user": {"id": self.account, "login": "private-login", "email": "private@example.test", "name": "private-name"}}

    def test_member_grant_and_retry_do_not_store_github_identity_or_token(self):
        result = self.access.verify(self.data)
        self.assertTrue(result["verified"])
        self.assertTrue(result["team"])
        self.access.authenticate("Bearer " + result["token"])
        self.assertEqual(result, self.access.verify(self.data))
        self.assertEqual(["POST", "DELETE"], self.calls)
        with self.database.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM identity_installations").fetchone()[0])
            text = "\n".join(db.iterdump())
        for forbidden in (self.data["access_token"], "private-login", "private@example.test", "private-name", result["token"]):
            self.assertNotIn(forbidden, text)

    def test_nonmember_is_verified_but_cannot_read_statistics(self):
        self.account = 999
        result = self.access.verify(self.data)
        self.assertEqual({"verified": True, "team": False, "token": ""}, result)
        with self.assertRaises(ApiError) as raised:
            self.access.authenticate("Bearer " + "0" * 64)
        self.assertEqual(403, raised.exception.status)
        with self.database.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM identity_installations").fetchone()[0])

    def test_revocation_failure_does_not_grant_access(self):
        self.revoke_error = True
        with self.assertRaises(ApiError):
            self.access.verify(self.data)
        with self.database.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM identity_grants").fetchone()[0])

    def test_membership_change_invalidates_existing_device_keys(self):
        token = self.access.verify(self.data)["token"]
        with mock.patch.dict("os.environ", {"STUDY_TEAM_MEMBER_HASHES": ""}):
            with self.assertRaises(ApiError):
                self.access.authenticate("Bearer " + token)

    def test_unknown_and_invalid_auth_are_not_empty_statistics(self):
        for header in ("", "Bearer invalid", "Bearer " + "0" * 64):
            with self.assertRaises(ApiError):
                self.access.summary(header, 7)

    def insert(self, eid, at, track="python", kind="grade", synthetic=False):
        payload = json.dumps({"at": at, "kind": kind, "synthetic": synthetic})
        with self.database.connect() as db:
            db.execute("INSERT INTO events VALUES (?,?,?,?,?)", ("participant", track, eid, int(eid), payload))

    def test_periods_use_korean_midnight_and_exclude_synthetic_and_undated(self):
        self.insert("1", "2026-11-12T15:00:00+00:00")
        self.insert("2", "2026-11-12T14:59:59+00:00", "ai")
        self.insert("3", "2026-11-10T09:00:00+09:00", kind="legacy_answer")
        self.insert("4", "2026-11-13T09:00:00+09:00", synthetic=True)
        token = "Bearer " + self.access.verify(self.data)["token"]
        now = datetime.datetime(2026, 11, 13, 12, tzinfo=KST)
        for days in (1, 7, 15, 30):
            result = self.access.summary(token, days, now)
            self.assertEqual(3, result["total"])
            self.assertEqual(1, result["undated"])
            self.assertEqual(1 if days == 1 else 2, result["period_total"])
            self.assertEqual(24 if days == 1 else days, len(result["series"]))
        for days in (0, 2, 31, True):
            with self.assertRaises(ApiError):
                self.access.summary(token, days, now)

    def test_migration_and_deletion_preserve_source_records_and_reconcile_counts(self):
        self.insert("1", "2026-11-13T09:00:00+09:00")
        with self.database.connect() as db:
            before = db.execute("SELECT * FROM events").fetchall()
            for action in ("insert", "update", "delete"):
                db.execute("DROP TRIGGER team_events_" + action)
            db.execute("DROP TABLE team_events")
            initialize(db)
            self.assertEqual(before, db.execute("SELECT * FROM events").fetchall())
            self.assertEqual(1, db.execute("SELECT count(*) FROM team_events").fetchone()[0])
            db.execute("DELETE FROM events")
            self.assertEqual(0, db.execute("SELECT count(*) FROM team_events").fetchone()[0])
