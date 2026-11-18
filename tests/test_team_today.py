# -*- coding: utf-8 -*-
"""팀원이 아닌 기기도 받는 오늘 계정 수 경로의 인증·응답·캐시를 확인함."""
import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from learning_server.app import Database, application
from learning_server.team import Access, KST


class TeamTodayTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Database(str(Path(temporary.name) / "test.sqlite3"))
        self.account = 101
        self.access = Access(self.database, self.github)
        self.tick = 1000.0
        self.access.clock = lambda: self.tick
        patch = mock.patch.dict("os.environ", {
            "STUDY_IDENTITY_CLIENT_ID": "test-client", "STUDY_IDENTITY_CLIENT_SECRET": "test-secret",
            "STUDY_TEAM_MEMBER_HASHES": ",".join(self.access.digest("member:" + str(n)) for n in range(101, 105)),
        })
        patch.start()
        self.addCleanup(patch.stop)
        self.team = self.verify(101, "a")
        self.learner = self.verify(999, "b")
        with mock.patch("learning_server.team.Access", return_value=self.access):
            self.app = application(self.database)
        self.date = datetime.datetime.now(KST).date().isoformat()

    def github(self, method, client_id, secret, token):
        return {} if method == "DELETE" else {"user": {"id": self.account}, "app": {"client_id": client_id}}

    def verify(self, account, nonce):
        self.account = account
        return self.access.verify({"access_token": "gho_" + str(account).zfill(36), "nonce": nonce * 64})["token"]

    def add(self, date, *accounts):
        with self.database.connect() as db:
            db.executemany("INSERT INTO identity_study_days VALUES (?,?)", [("account-%s" % n, date) for n in accounts])

    def rows(self):
        with self.database.connect() as db:
            return db.execute("SELECT count(*) FROM identity_study_days").fetchone()[0]

    def call(self, token=None, path="/v1/identity/today", query="", **headers):
        environ = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "QUERY_STRING": query,
                   "wsgi.input": io.BytesIO(b""), **headers}
        if token is not None:
            environ["HTTP_AUTHORIZATION"] = "Bearer " + token
        status = []
        response = b"".join(self.app(environ, lambda code, _: status.append(int(code.split()[0]))))
        return status[0], json.loads(response)

    def test_missing_malformed_and_unknown_keys_are_rejected(self):
        self.assertEqual(401, self.call()[0])
        self.assertEqual(401, self.call(HTTP_AUTHORIZATION=self.learner)[0])
        for token in ("", "a" * 63, "A" * 64, "g" * 64, self.learner + "0", "0" * 64):
            self.assertEqual(401, self.call(token)[0], token)
        with mock.patch.dict("os.environ", {"STUDY_TEAM_MEMBER_HASHES": self.access.digest("member:102")}):
            self.assertEqual(401, self.call(self.team)[0])
            self.assertEqual(200, self.call(self.learner)[0])

    def test_member_and_nonmember_get_the_same_two_keys(self):
        self.add(self.date, 1, 2, 3)
        member = self.call(self.team)
        other = self.call(self.learner)
        self.assertEqual((200, {"date": self.date, "accounts": 3}), member)
        self.assertEqual(member, other)
        self.assertEqual({"date", "accounts"}, set(other[1]))
        self.assertEqual(403, self.call(self.learner, path="/v1/team/summary")[0])

    def test_query_string_is_rejected(self):
        for query in ("days=7", "x", "date=" + self.date):
            self.assertEqual((400, {"error": "요청 내용을 읽을 수 없습니다."}), self.call(self.learner, query=query))

    def test_yesterday_rows_are_neither_counted_nor_deleted(self):
        yesterday = (datetime.datetime.now(KST).date() - datetime.timedelta(days=1)).isoformat()
        self.add(yesterday, 1, 2, 3, 4)
        self.add(self.date, 5)
        before = self.rows()
        self.assertEqual((200, {"date": self.date, "accounts": 1}), self.call(self.learner))
        self.assertEqual(5, before)
        self.assertEqual(before, self.rows())

    def test_korean_midnight_changes_date_and_count(self):
        self.add("2026-11-15", 1)
        self.add("2026-11-16", 2, 3)
        before = datetime.datetime(2026, 11, 15, 23, 59, 59, tzinfo=KST)
        midnight = datetime.datetime(2026, 11, 16, tzinfo=KST)
        self.assertEqual({"date": "2026-11-15", "accounts": 1}, self.access.today("Bearer " + self.learner, before))
        self.assertEqual({"date": "2026-11-16", "accounts": 2}, self.access.today("Bearer " + self.learner, midnight))
        utc = datetime.datetime(2026, 11, 15, 15, tzinfo=datetime.timezone.utc)
        self.assertEqual({"date": "2026-11-16", "accounts": 2}, self.access.today("Bearer " + self.learner, utc))

    def test_cache_keeps_value_for_300_seconds_and_drops_it_on_new_date(self):
        now = datetime.datetime(2026, 11, 16, 12, tzinfo=KST)
        today = lambda moment=now: self.access.today("Bearer " + self.learner, moment)["accounts"]
        self.add("2026-11-16", 1)
        self.assertEqual(1, today())
        self.add("2026-11-16", 2)
        self.tick += 299
        self.assertEqual(1, today())
        self.tick += 1
        self.assertEqual(2, today())
        self.add("2026-11-16", 3)
        self.add("2026-11-17", 4)
        self.tick += 10
        self.assertEqual(2, today())
        self.assertEqual(1, today(datetime.datetime(2026, 11, 17, tzinfo=KST)))

    def test_cache_over_http_and_authentication_is_not_cached(self):
        self.add(self.date, 1)
        self.assertEqual(1, self.call(self.learner)[1]["accounts"])
        self.add(self.date, 2)
        self.assertEqual((200, {"date": self.date, "accounts": 1}), self.call(self.team))
        for token in ("0" * 64, "a" * 63):
            self.assertEqual(401, self.call(token)[0])
        self.assertEqual(401, self.call()[0])
        self.tick += 300
        self.assertEqual(2, self.call(self.learner)[1]["accounts"])

    def test_database_error_is_503(self):
        with self.database.connect() as db:
            db.execute("DROP TABLE identity_study_days")
        code, result = self.call(self.learner)
        self.assertEqual(503, code)
        self.assertEqual({"error"}, set(result))


if __name__ == "__main__":
    unittest.main()
