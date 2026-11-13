# -*- coding: utf-8 -*-
"""기기 확인·권한 분리와 집계의 원본 보존을 확인함."""
import contextlib
import datetime
import io
import json
import sqlite3
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
        self.assertTrue(result["verified"])
        self.assertFalse(result["team"])
        self.assertTrue(self.access.authenticate("Bearer " + result["token"], require_team=False)["verified"])
        with self.assertRaises(ApiError) as raised:
            self.access.authenticate("Bearer " + result["token"])
        self.assertEqual(403, raised.exception.status)
        with self.database.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM identity_installations").fetchone()[0])

    def test_http_routes_separate_public_configuration_device_check_and_team_statistics(self):
        from learning_server.app import application
        with mock.patch("learning_server.team.Access", return_value=self.access):
            app = application(self.database)
        def call(path, method="GET", payload=None, token=""):
            raw = json.dumps(payload).encode()
            environ = {"PATH_INFO": path, "REQUEST_METHOD": method, "CONTENT_LENGTH": str(len(raw)),
                       "CONTENT_TYPE": "application/json", "wsgi.input": io.BytesIO(raw), "HTTP_AUTHORIZATION": "Bearer " + token}
            status = []
            body = b"".join(app(environ, lambda code, headers: status.append(int(code.split()[0]))))
            return status[0], json.loads(body)
        self.assertEqual((200, {"enabled": True, "client_id": "client123"}), call("/v1/identity/config"))
        self.assertEqual(401, call("/v1/identity/status")[0])
        self.account = 999
        code, result = call("/v1/identity/verify", "POST", self.data)
        self.assertEqual(200, code)
        self.assertEqual((200, {"verified": True, "team": False}), call("/v1/identity/status", token=result["token"]))
        self.assertEqual(403, call("/v1/team/summary", token=result["token"])[0])

    def test_same_account_on_two_devices_is_one_account_and_two_installations(self):
        self.access.verify(self.data)
        self.access.verify({"access_token": "gho_" + "y" * 36, "nonce": "b" * 64})
        with self.database.connect() as db:
            self.assertEqual(1, db.execute("SELECT count(*) FROM identity_accounts").fetchone()[0])
            self.assertEqual(2, db.execute("SELECT count(*) FROM identity_installations").fetchone()[0])

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

    def test_membership_change_preserves_regular_learner_device_key(self):
        self.account = 999
        token = self.access.verify(self.data)["token"]
        with mock.patch.dict("os.environ", {"STUDY_TEAM_MEMBER_HASHES": ",".join(self.access.digest("member:" + str(n)) for n in (201, 202, 203, 204))}):
            result = self.access.authenticate("Bearer " + token, require_team=False)
            self.assertEqual({"verified": True, "team": False}, result)
            with self.assertRaises(ApiError) as raised:
                self.access.authenticate("Bearer " + token)
            self.assertEqual(403, raised.exception.status)

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

    def test_graded_series_place_midnight_and_unknown_dates_in_separate_counts(self):
        rows = [
            ("ai", "answer", "pass", "2026-11-12T15:00:00+00:00"),
            ("python", "answer", "wrong", "2026-11-12T14:59:59+00:00"),
            ("ai", "legacy_answer", "partial", "2026-11-13T12:00:00+09:00"),
            ("ai", "mock_answer", "stuck", "2026-11-13T09:00:00+09:00"),
        ]
        with self.database.connect() as db:
            for n, (track, kind, result, at) in enumerate(rows, 1):
                payload = json.dumps({"kind": kind, "data": {"card": "q", "result": result}, "at": at})
                db.execute("INSERT INTO events VALUES (?,?,?,?,?)", ("participant", track, str(n), n, payload))
        viewer = "Bearer " + self.access.verify(self.data)["token"]
        now = datetime.datetime(2026, 11, 13, 12, tzinfo=KST)
        for days in (1, 7, 15, 30):
            graded = self.access.summary(viewer, days, now)["graded"]
            self.assertEqual((3, 1, 1), (graded["total"], graded["undated"], graded["unknown"]))
            self.assertEqual(1 if days == 1 else 2, graded["period_total"])
            self.assertEqual(1, graded["series"][0 if days == 1 else -1]["ai"])
            if days != 1:
                self.assertEqual(1, graded["series"][-2]["python"])

    def test_period_activity_preserves_raw_and_counts_cards_across_days_and_people(self):
        now = datetime.datetime(2026, 11, 13, 12, tzinfo=KST)
        viewer = "Bearer " + self.access.verify(self.data)["token"]
        revision = "a" * 64
        def add(seq, kind, day=13, track="ai", participant="a", card="q", item=None, **fields):
            at = now.replace(day=day, hour=9).isoformat()
            data = dict(card=card, set="s", **fields)
            event = dict(at=at, kind=kind, data=data, item=item, item_revision=revision if item else None)
            db.execute("INSERT INTO events VALUES (?,?,?,?,?)", (participant, track, str(seq), seq, json.dumps(event)))
        with self.database.connect() as db:
            add(1, "question_returned", day=11)
            add(2, "question_returned", day=13, participant="b")
            add(3, "mock_question_returned", input_schema=1)
            add(4, "ai_input", input_schema=1)
            add(5, "set", card="not-shown")
            add(6, "answer", result="pass", item={"stem": "문제", "tags": ["개념"]})
            add(7, "question_returned", track="python")
            add(8, "python_input", track="python", item={"level": 2})
            add(9, "answer", track="python", item={"level": 2}, input_event="8", result="wrong")
            add(10, "mock_answer", card="never-opened", result="stuck", answered=False)
            add(11, "answer", card="used", item={"difficulty": True}, result="pass")
            add(12, "ai_input", day=10, input_schema=True)
            add(13, "question_returned", day=8, input_schema=1)
            add(14, "answer", track="python", participant="b", item={"level": 2}, result="ok", input_event="8")
            before = db.execute("SELECT * FROM events ORDER BY rowid").fetchall()
        result = self.access.summary(viewer, 7, now)
        activity = result["activity"]
        self.assertEqual((14, 14, 4, 2), (result["total"], result["period_total"], result["graded"]["period_total"],
                                          activity["distinct_cards"]))
        self.assertEqual(5, sum(row["ai"] + row["python"] for row in activity["opens"]))
        self.assertEqual([None, 0, None, None, None, None, 1], [row["ai"] for row in activity["inputs"]])
        self.assertTrue(activity["inputs"][-1]["ai_unmeasured"])
        self.assertEqual(1, activity["inputs"][-1]["python"])
        self.assertEqual(now.replace(day=8, hour=9).isoformat(), activity["period_first_ai_measurement_at"])
        self.assertEqual(dict(stem=1, concepts=1, revision=4, difficulty=2, ordered_timed=4, linked_input=1),
                         activity["graded_metadata"])
        self.assertNotIn("never-opened", json.dumps(activity))
        with self.database.connect() as db:
            self.assertEqual(before, db.execute("SELECT * FROM events ORDER BY rowid").fetchall())

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

    def test_existing_database_backfill_is_atomic_and_preserves_original_rows(self):
        self.insert("1", "2026-11-13T01:00:00+00:00")
        with self.database.connect() as db:
            payload = json.dumps({"at": "2026-11-13T01:00:00+00:00", "kind": "answer",
                                  "data": {"card": "q1", "result": "wrong"}})
            db.execute("UPDATE events SET payload=?", (payload,))
            self.assertEqual([(1,)], db.execute("SELECT confirmed FROM team_attempts").fetchall())
            for action in ("insert", "update", "delete"):
                db.execute("DROP TRIGGER team_attempts_" + action)
            db.execute("DROP VIEW team_attempt_source")
            db.execute("DROP TABLE team_attempts")
        def original_rows():
            uri = Path(self.database.path).resolve().as_uri() + "?mode=ro"
            with contextlib.closing(sqlite3.connect(uri, uri=True)) as db:
                return {table: db.execute("SELECT * FROM " + table).fetchall()
                        for table in ("events", "team_events", "storage_totals", "identity_grants")}
        before = original_rows()
        connect = sqlite3.connect
        def interrupt(*args, **kwargs):
            db = connect(*args, **kwargs)
            db.set_authorizer(lambda action, name, *_: sqlite3.SQLITE_DENY
                              if action == sqlite3.SQLITE_CREATE_TRIGGER and name == "team_attempts_update" else sqlite3.SQLITE_OK)
            return db
        with mock.patch("sqlite3.connect", side_effect=interrupt), self.assertRaises(sqlite3.DatabaseError):
            Database(self.database.path)
        with self.database.connect() as db:
            self.assertEqual([], db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'team_attempt%'").fetchall())
        self.assertEqual(before, original_rows())
        for _ in range(2):
            Database(self.database.path)
            self.assertEqual(before, original_rows())
            with self.database.connect() as db:
                self.assertEqual([(1,)], db.execute("SELECT confirmed FROM team_attempts").fetchall())
        with self.database.connect() as db:
            db.execute("UPDATE events SET payload='{}'")
            self.assertEqual([], db.execute("SELECT * FROM team_attempts").fetchall())
            self.assertEqual(1, db.execute("SELECT count(*) FROM team_events").fetchone()[0])
