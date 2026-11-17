# -*- coding: utf-8 -*-
"""일별 계정 신호의 인증·날짜·중복과 연구 기록 분리를 확인함."""
import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from learning_server.app import ApiError, Database, application, hashed
from learning_server.team import Access, KST, initialize


class StudyActivityTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Database(str(Path(temporary.name) / "test.sqlite3"))
        self.account = 101
        self.access = Access(self.database, self.github)
        patch = mock.patch.dict("os.environ", {
            "STUDY_IDENTITY_CLIENT_ID": "test-client", "STUDY_IDENTITY_CLIENT_SECRET": "test-secret",
            "STUDY_TEAM_MEMBER_HASHES": ",".join(self.access.digest("member:" + str(n)) for n in range(101, 105)),
        })
        patch.start()
        self.addCleanup(patch.stop)
        self.now = datetime.datetime(2026, 11, 16, 12, tzinfo=KST)
        self.team = self.verify(101, "a")

    def github(self, method, client_id, secret, token):
        return {} if method == "DELETE" else {"user": {"id": self.account}, "app": {"client_id": client_id}}

    def verify(self, account, nonce):
        self.account = account
        data = {"access_token": "gho_" + str(account).zfill(36), "nonce": nonce * 64}
        return self.access.verify(data)["token"]

    def signal(self, token, *, now=None, **extra):
        now = now or self.now
        return self.access.study_activity("Bearer " + token,
                                          {"date": now.date().isoformat(), "accepted": True, **extra}, now=now)

    def summary(self, days=7, now=None):
        return self.access.summary("Bearer " + self.team, days, now or self.now)["today"]

    def make_legacy(self, token):
        with self.database.connect() as db:
            db.execute("UPDATE identity_grants SET account_hash=NULL WHERE token_hash=?", (hashed(token),))

    def test_two_devices_and_repeated_subject_signals_count_one_account(self):
        second_device = self.verify(101, "b")
        learner = self.verify(999, "c")
        for token in (self.team, second_device, learner, self.team, second_device):
            self.assertEqual({"eligible": True, "date": "2026-11-16"}, self.signal(token))
        expected = {"date": "2026-11-16", "accounts": 2, "coverage": "all",
                    "eligible_accounts": 2, "authenticated_accounts": 2}
        for days in (1, 7, 15, 30):
            self.assertEqual(expected, self.summary(days))
        with self.database.connect() as db:
            self.assertEqual(["account_hash", "date"], [row[1] for row in db.execute("PRAGMA table_info(identity_study_days)")])
            for table in ("participants", "events", "open_enrollments"):
                self.assertEqual(0, db.execute("SELECT count(*) FROM " + table).fetchone()[0])

    def test_old_grant_without_nonce_remains_authenticated_and_partial(self):
        learner = self.verify(999, "b")
        self.make_legacy(learner)
        self.assertEqual({"eligible": False, "date": "2026-11-16"}, self.signal(learner))
        self.assertTrue(self.access.authenticate("Bearer " + learner, require_team=False)["verified"])
        self.assertEqual({"eligible": False, "deleted": False}, self.access.study_activity(
            "Bearer " + learner, {}, delete=True, now=self.now))
        self.assertEqual({"date": "2026-11-16", "accounts": 0, "coverage": "partial",
                          "eligible_accounts": 1, "authenticated_accounts": 2}, self.summary())

    def test_existing_nonce_restores_only_matching_grant_and_is_not_stored(self):
        learner = self.verify(999, "b")
        other = self.verify(998, "c")
        self.make_legacy(learner)
        self.make_legacy(other)
        with mock.patch.object(self.access, "call", side_effect=AssertionError("network")):
            self.assertTrue(self.signal(learner, nonce="b" * 64)["eligible"])
            with mock.patch.object(self.access, "digest", side_effect=AssertionError("repeat scan")):
                self.assertTrue(self.signal(learner)["eligible"])
        with self.database.connect() as db:
            self.assertEqual((self.access.digest("account:999"),), db.execute(
                "SELECT account_hash FROM identity_grants WHERE token_hash=?", (hashed(learner),)).fetchone())
            self.assertEqual((None,), db.execute(
                "SELECT account_hash FROM identity_grants WHERE token_hash=?", (hashed(other),)).fetchone())
            self.assertNotIn("b" * 64, "\n".join(db.iterdump()))
        self.assertEqual(1, self.summary()["accounts"])

    def test_wrong_nonce_does_not_link_and_repeated_scan_is_limited(self):
        learner = self.verify(999, "b")
        self.make_legacy(learner)
        self.assertFalse(self.signal(learner, nonce="c" * 64)["eligible"])
        with self.assertRaises(ApiError) as failure:
            self.signal(learner, nonce="b" * 64)
        self.assertEqual(429, failure.exception.status)
        self.assertEqual(0, self.summary()["accounts"])
        self.assertTrue(self.signal(learner, now=self.now + datetime.timedelta(seconds=30), nonce="b" * 64)["eligible"])

    def test_reconfirmation_and_account_switch_do_not_reassign_activity(self):
        first = self.verify(999, "b")
        self.make_legacy(first)
        with self.database.connect() as db:
            db.execute("DELETE FROM identity_receipts")
        self.assertEqual(first, self.verify(999, "b"))
        self.assertTrue(self.signal(first)["eligible"])
        second = self.verify(998, "b")
        self.assertNotEqual(first, second)
        self.assertEqual(1, self.summary()["accounts"])
        self.assertTrue(self.signal(second)["eligible"])
        self.access.study_activity("Bearer " + second, {}, delete=True, now=self.now)
        with self.database.connect() as db:
            self.assertEqual([(self.access.digest("account:999"), "2026-11-16")],
                             db.execute("SELECT * FROM identity_study_days").fetchall())

    def test_recovery_uses_original_policy_for_nonmember(self):
        learner = self.verify(999, "b")
        self.make_legacy(learner)
        values = ",".join(self.access.digest("member:" + str(n)) for n in range(201, 205))
        with mock.patch.dict("os.environ", {"STUDY_TEAM_MEMBER_HASHES": values}):
            self.assertTrue(self.signal(learner, nonce="b" * 64)["eligible"])
            with self.assertRaises(ApiError) as failure:
                self.signal(self.team)
            self.assertEqual(401, failure.exception.status)

    def test_policy_change_preserves_today_count_above_eligible_accounts(self):
        second = self.verify(102, "b")
        self.signal(self.team)
        self.signal(second)
        values = ",".join(self.access.digest("member:" + str(n)) for n in range(201, 205))
        with mock.patch.dict("os.environ", {"STUDY_TEAM_MEMBER_HASHES": values}):
            self.team = self.verify(201, "c")
            today = self.summary()
        self.assertEqual(2, today["accounts"])
        self.assertEqual(1, today["eligible_accounts"])
        self.assertEqual(3, today["authenticated_accounts"])
        self.assertEqual("partial", today["coverage"])

    def test_midnight_is_korean_and_old_rows_are_purged_by_write_and_read(self):
        utc = datetime.timezone.utc
        before = datetime.datetime(2026, 11, 15, 14, 59, 59, tzinfo=utc)
        midnight = before + datetime.timedelta(seconds=1)
        self.access.study_activity("Bearer " + self.team, {"date": "2026-11-15", "accepted": True}, now=before)
        self.access.study_activity("Bearer " + self.team, {"date": "2026-11-16", "accepted": True}, now=midnight)
        with self.database.connect() as db:
            self.assertEqual([("2026-11-16",)], db.execute("SELECT date FROM identity_study_days").fetchall())
        next_day = datetime.datetime(2026, 11, 17, tzinfo=KST)
        self.assertEqual(0, self.summary(30, next_day)["accounts"])
        with self.database.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM identity_study_days").fetchone()[0])

    def test_delete_is_idempotent_and_same_account_devices_share_removal(self):
        other_device = self.verify(101, "b")
        learner = self.verify(999, "c")
        self.signal(self.team)
        self.signal(learner)
        self.make_legacy(other_device)
        for _ in range(2):
            self.assertEqual({"eligible": True, "deleted": True}, self.access.study_activity(
                "Bearer " + other_device, {"nonce": "b" * 64}, delete=True, now=self.now))
        self.assertEqual(1, self.summary()["accounts"])
        self.assertTrue(self.access.authenticate("Bearer " + self.team)["verified"])

    def test_nullable_migration_preserves_existing_grants_and_does_not_backfill(self):
        with self.database.connect() as db:
            original = db.execute("SELECT token_hash,policy,created,member FROM identity_grants").fetchall()
            db.execute("ALTER TABLE identity_grants DROP COLUMN account_hash")
            db.execute("ALTER TABLE identity_grants DROP COLUMN account_recovery_at")
            initialize(db)
            initialize(db)
            self.assertEqual(original, db.execute("SELECT token_hash,policy,created,member FROM identity_grants").fetchall())
            self.assertEqual([(None, None)], db.execute("SELECT account_hash,account_recovery_at FROM identity_grants").fetchall())
        self.assertFalse(self.signal(self.team)["eligible"])

    def test_http_contract_authentication_consent_and_date_validation(self):
        endpoint = "/v1/identity/study-activity"
        app = application(self.database)
        today = datetime.datetime.now(KST).date()
        body = {"date": today.isoformat(), "accepted": True}
        learner = self.verify(999, "b")

        def call(method="POST", data=body, token=learner, path=endpoint, raw=None, **headers):
            payload = json.dumps(data).encode() if raw is None else raw
            environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(payload)),
                       "CONTENT_TYPE": "application/json", "wsgi.input": io.BytesIO(payload),
                       "HTTP_AUTHORIZATION": "Bearer " + token, **headers}
            status = []
            response = b"".join(app(environ, lambda code, _: status.append(int(code.split()[0]))))
            return status[0], json.loads(response)

        self.assertEqual(401, call(token="0" * 64)[0])
        for accepted in (None, False, 1, "true"):
            self.assertEqual(403, call(data={"date": today.isoformat(), "accepted": accepted})[0])
        self.assertEqual(403, call(data={"date": today.isoformat()})[0])
        for date in ((today - datetime.timedelta(days=1)).isoformat(), (today + datetime.timedelta(days=1)).isoformat(),
                     "2026-11-16T00:00:00+09:00", None):
            self.assertEqual(400, call(data={**body, "date": date})[0])
        for extra in ({"nonce": "bad"}, {"participant": "forbidden"}, {"synthetic": True}, {"answer": "forbidden"}):
            self.assertEqual(400, call(data={**body, **extra})[0])
        self.assertEqual(400, call(data=[])[0])
        self.assertEqual(413, call(raw=b"x" * 2049)[0])
        self.assertEqual(415, call(CONTENT_TYPE="text/plain")[0])
        self.assertEqual(400, call(CONTENT_LENGTH="2000")[0])
        self.assertEqual((200, {"eligible": True, "date": today.isoformat()}), call())
        self.assertEqual(403, call(method="GET", path="/v1/team/summary")[0])
        code, result = call(method="GET", token=self.team, path="/v1/team/summary")
        self.assertEqual(200, code)
        self.assertEqual(1, result["today"]["accounts"])
        self.assertEqual((200, {"eligible": True, "deleted": True}), call(method="DELETE", raw=b""))
        self.assertEqual(401, call(method="DELETE", token="0" * 64, raw=b"")[0])


if __name__ == "__main__":
    unittest.main()
