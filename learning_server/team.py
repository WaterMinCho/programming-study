# -*- coding: utf-8 -*-
"""계정 번호 원문을 남기지 않고 기기 확인과 팀원용 집계를 제공함."""
import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request

PERIODS = (1, 7, 15, 30)
KST = datetime.timezone(datetime.timedelta(hours=9))


def initialize(db):
    db.execute("CREATE TABLE IF NOT EXISTS identity_grants (token_hash TEXT PRIMARY KEY, policy TEXT NOT NULL, created INTEGER NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS identity_receipts (request_hash TEXT PRIMARY KEY, member INTEGER NOT NULL, expires INTEGER NOT NULL)")
    if "member" not in {row[1] for row in db.execute("PRAGMA table_info(identity_grants)")}:
        db.execute("ALTER TABLE identity_grants ADD COLUMN member INTEGER NOT NULL DEFAULT 1")
    if "account_hash" not in {row[1] for row in db.execute("PRAGMA table_info(identity_receipts)")}:
        db.execute("ALTER TABLE identity_receipts ADD COLUMN account_hash TEXT NOT NULL DEFAULT ''")
    db.execute("CREATE TABLE IF NOT EXISTS identity_accounts (account_hash TEXT PRIMARY KEY, first_seen INTEGER NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS identity_policy (slot INTEGER PRIMARY KEY CHECK(slot=1), value TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS identity_installations (device_hash TEXT PRIMARY KEY, first_seen INTEGER NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS identity_installations_time ON identity_installations(first_seen)")
    initialize_events(db)
    initialize_attempts(db)


def initialize_events(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='team_events'").fetchone():
        return
    db.execute("CREATE TABLE team_events (participant TEXT, track TEXT, event_id TEXT, at INTEGER, synthetic INTEGER NOT NULL, PRIMARY KEY(participant,track,event_id))")
    def values(prefix):
        payload = prefix + "payload"
        return ("CASE WHEN json_valid(%s) THEN CASE WHEN json_extract(%s,'$.kind')='legacy_answer' THEN NULL ELSE CAST(strftime('%%s',json_extract(%s,'$.at')) AS INTEGER) END ELSE NULL END, "
                "CASE WHEN json_valid(%s) THEN CASE WHEN json_extract(%s,'$.synthetic')=1 THEN 1 ELSE 0 END ELSE 0 END" % (payload, payload, payload, payload, payload))
    db.execute("INSERT INTO team_events SELECT participant,track,event_id," + values("") + " FROM events")
    db.execute("CREATE INDEX team_events_time ON team_events(synthetic,at,track)")
    insert = "INSERT OR REPLACE INTO team_events VALUES (new.participant,new.track,new.event_id," + values("new.") + ");"
    remove = "DELETE FROM team_events WHERE participant=old.participant AND track=old.track AND event_id=old.event_id;"
    for action, body in (("INSERT", insert), ("DELETE", remove), ("UPDATE", remove + insert)):
        db.execute("CREATE TRIGGER team_events_%s AFTER %s ON events BEGIN %s END" % (action.lower(), action, body))


def initialize_attempts(db):
    """원본을 그대로 두고 문항별 채점 판정만 색인함. 첫 이관과 이후 저장에 같은 질의를 사용함."""
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='team_attempts'").fetchone():
        return
    db.execute("""CREATE VIEW team_attempt_source AS
        SELECT participant, track, event_id, CASE
            WHEN json_type(payload,'$.data.card') IS NOT 'text' OR trim(card)='' THEN NULL
            WHEN dontknow=1 OR answered='false' THEN NULL
            WHEN answered IS NOT NULL AND answered!='true' THEN NULL
            WHEN kind='answer' AND track='python' AND result IN ('ok','wrong') THEN 1
            WHEN track!='ai' OR kind IS NULL OR kind NOT IN ('answer','legacy_answer','mock_answer') THEN NULL
            WHEN result='pass' OR (kind!='mock_answer' AND result='partial') THEN 1
            WHEN result='stuck' THEN CASE
                WHEN answered='true' THEN 1
                WHEN json_type(payload,'$.data.response')='array' THEN
                    CASE WHEN EXISTS (SELECT 1 FROM json_each(payload,'$.data.response')
                        WHERE type='integer' OR (type='text' AND trim(value, char(9,10,11,12,13,32,160,12288))!=''))
                        THEN 1 END
                WHEN kind='answer' THEN 1
                WHEN kind='legacy_answer' AND json_type(payload,'$.data.sure') IN ('true','false') THEN 1
                ELSE 0 END
            END AS confirmed
        FROM (SELECT participant, track, event_id, payload, json_extract(payload,'$.kind') AS kind,
                     json_extract(payload,'$.data.card') AS card, json_extract(payload,'$.data.result') AS result,
                     json_extract(payload,'$.data.dontknow') AS dontknow, json_type(payload,'$.data.answered') AS answered
              FROM events WHERE json_valid(payload))""")
    db.execute("""CREATE TABLE team_attempts (
        participant TEXT, track TEXT, event_id TEXT, confirmed INTEGER NOT NULL,
        PRIMARY KEY(participant,track,event_id)) WITHOUT ROWID""")
    select = "SELECT participant,track,event_id,confirmed FROM team_attempt_source WHERE confirmed IS NOT NULL"
    db.execute("INSERT INTO team_attempts " + select)
    add = ("INSERT INTO team_attempts " + select +
           " AND participant=new.participant AND track=new.track AND event_id=new.event_id;")
    remove = "DELETE FROM team_attempts WHERE participant=old.participant AND track=old.track AND event_id=old.event_id;"
    for action, body in (("insert", add), ("delete", remove), ("update", remove + add)):
        db.execute("CREATE TRIGGER team_attempts_%s AFTER %s ON events BEGIN %s END" % (action, action, body))


def activity_summary(db, start, step, size, end):
    """선택 기간에 실제로 나타난 문항과 행동을 셈. 기존 원본과 색인은 읽기만 함."""
    begin = int(start.timestamp())
    slots = [{"at": (start + datetime.timedelta(seconds=n * step)).isoformat(), "python": 0, "ai": 0}
             for n in range(size)]
    opened = [dict(row) for row in slots]
    inputs = [dict(row, ai=None, ai_unmeasured=False) for row in slots]
    cards = set()
    metadata = dict(stem=0, concepts=0, revision=0, difficulty=0, ordered_timed=0, linked_input=0)
    first_measured = None
    rows = db.execute("""
        SELECT t.at,t.track,json_extract(e.payload,'$.kind'),json_extract(e.payload,'$.data.card'),
            json_type(e.payload,'$.data.card')='text',a.confirmed,
            json_type(e.payload,'$.data.input_schema')='integer' AND json_extract(e.payload,'$.data.input_schema')=1,
            json_type(e.payload,'$.item.stem')='text' AND trim(json_extract(e.payload,'$.item.stem'))!='',
            json_type(e.payload,'$.item.tags')='array' AND EXISTS
                (SELECT 1 FROM json_each(e.payload,'$.item.tags') WHERE type='text' AND trim(value)!=''),
            length(json_extract(e.payload,'$.item_revision'))=64,
            CASE WHEN t.track='python' AND json_type(e.payload,'$.item.difficulty') IS NULL
                THEN json_type(e.payload,'$.item.level')='integer' AND json_extract(e.payload,'$.item.level') BETWEEN 1 AND 3
                ELSE json_type(e.payload,'$.item.difficulty')='integer' AND json_extract(e.payload,'$.item.difficulty') BETWEEN 1 AND 3 END,
            e.sequence>0,
            CASE WHEN a.confirmed=1 AND t.track='python' THEN EXISTS (
                SELECT 1 FROM events i JOIN team_events it USING(participant,track,event_id)
                WHERE i.participant=e.participant AND i.track=e.track
                    AND i.event_id=json_extract(e.payload,'$.data.input_event') AND i.sequence<e.sequence
                    AND it.synthetic=0 AND it.at<=t.at AND json_valid(i.payload)
                    AND json_extract(i.payload,'$.kind')='python_input'
                    AND json_extract(i.payload,'$.data.card')=json_extract(e.payload,'$.data.card')
                    AND json_extract(i.payload,'$.data.set')=json_extract(e.payload,'$.data.set')
                    AND json_extract(i.payload,'$.item_revision')=json_extract(e.payload,'$.item_revision')) END
        FROM team_events t JOIN events e USING(participant,track,event_id)
        LEFT JOIN team_attempts a USING(participant,track,event_id)
        WHERE t.synthetic=0 AND t.at>=? AND t.at<? AND json_valid(e.payload)
            AND json_extract(e.payload,'$.kind') IN
                ('question_returned','mock_question_returned','python_input','ai_input','answer','mock_answer')
        ORDER BY t.at""", (begin, end))
    for at, track, kind, card, has_card, graded, measured, stem, tags, revision, difficulty, ordered, linked in rows:
        if track not in ("python", "ai"):
            continue
        slot = (at - begin) // step
        is_open = kind in ("question_returned", "mock_question_returned")
        is_input = ((track == "python" and kind == "python_input") or
                    (track == "ai" and kind == "ai_input" and measured))
        if is_open:
            if has_card and card.strip():
                cards.add((track, card))
            opened[slot][track] += 1
            if track == "ai" and not measured:
                inputs[slot]["ai_unmeasured"] = True
        if track == "ai" and measured and (is_open or is_input):
            if first_measured is None:
                first_measured = datetime.datetime.fromtimestamp(at, KST).isoformat()
            if inputs[slot]["ai"] is None:
                inputs[slot]["ai"] = 0
        if is_input:
            inputs[slot][track] += 1
        if graded == 1:
            metadata["stem"] += bool(stem)
            metadata["concepts"] += bool(tags)
            metadata["revision"] += bool(revision)
            metadata["difficulty"] += bool(difficulty)
            metadata["ordered_timed"] += bool(ordered)
            metadata["linked_input"] += bool(linked)
    return {"distinct_cards": len(cards), "opens": opened, "inputs": inputs, "graded_metadata": metadata,
            "ai_input_schema": 1, "period_first_ai_measurement_at": first_measured}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OSError("redirect")


def github(method, client_id, secret, token):
    auth = base64.b64encode((client_id + ":" + secret).encode()).decode()
    url = "https://api.github.com/applications/" + client_id + ("/token" if method == "POST" else "/grant")
    request = urllib.request.Request(url, json.dumps({"access_token": token}).encode(),
                                    {"Authorization": "Basic " + auth, "Accept": "application/vnd.github+json",
                                     "Content-Type": "application/json", "User-Agent": "programming-study-identity",
                                     "X-GitHub-Api-Version": "2026-03-10"}, method=method)
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
        if method == "DELETE":
            if response.status != 204:
                raise OSError("revocation")
            return {}
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("size")
        return json.loads(raw)


class Access:
    def __init__(self, database, call=github):
        self.database, self.call = database, call

    def config(self):
        cid = os.environ.get("STUDY_IDENTITY_CLIENT_ID", "")
        secret = os.environ.get("STUDY_IDENTITY_CLIENT_SECRET", "")
        return cid, secret

    def public_config(self):
        cid, secret = self.config()
        ready = bool(cid and secret and self.members())
        return {"enabled": ready, "client_id": cid if ready else ""}

    def digest(self, text):
        return hmac.new(self.database.secret, text.encode(), hashlib.sha256).hexdigest()

    def members(self):
        values = frozenset(value.strip() for value in os.environ.get("STUDY_TEAM_MEMBER_HASHES", "").split(",") if value.strip())
        return values if len(values) == 4 and all(re.fullmatch(r"[a-f0-9]{64}", value) for value in values) else frozenset()

    def policy(self):
        value = hashlib.sha256(",".join(sorted(self.members())).encode()).hexdigest()
        with self.database.connect() as db:
            old = db.execute("SELECT value FROM identity_policy WHERE slot=1").fetchone()
            if old != (value,):
                db.execute("BEGIN IMMEDIATE")
                old = db.execute("SELECT value FROM identity_policy WHERE slot=1").fetchone()
                if old != (value,):
                    db.execute("DELETE FROM identity_grants WHERE member=1")
                    db.execute("DELETE FROM identity_receipts")
                    db.execute("INSERT OR REPLACE INTO identity_policy VALUES (1,?)", (value,))
        return value

    def verify(self, data):
        from learning_server.app import ApiError, hashed
        cid, secret = self.config()
        if not cid or not secret or not self.members():
            raise ApiError(503, "본인 확인 연결을 준비 중입니다. 잠시 뒤 다시 시도해 주세요.")
        token, nonce = data.get("access_token"), data.get("nonce")
        if (not isinstance(token, str) or not re.fullmatch(r"gh[ou]_[A-Za-z0-9_]{20,480}", token)
                or not isinstance(nonce, str) or not re.fullmatch(r"[a-f0-9]{64}", nonce)):
            raise ApiError(400, "본인 확인 응답을 확인해 주세요.")
        policy = self.policy()
        request_hash = self.digest("verify:" + policy + ":" + token + ":" + nonce)
        now = int(time.time())
        with self.database.connect() as db:
            prior = db.execute("SELECT member,account_hash FROM identity_receipts WHERE request_hash=? AND expires>?", (request_hash, now)).fetchone()
        if prior is not None and prior[1]:
            viewer = self.digest("viewer:" + policy + ":" + prior[1] + ":" + nonce)
            return {"verified": True, "team": bool(prior[0]), "token": viewer}
        try:
            info = self.call("POST", cid, secret, token)
            try:
                user_id = info.get("user", {}).get("id")
                member = type(user_id) is int and self.digest("member:" + str(user_id)) in self.members()
                valid = type(user_id) is int and user_id > 0 and info.get("app", {}).get("client_id") == cid
                account_hash = self.digest("account:" + str(user_id)) if valid else None
            finally:
                info.clear()
                self.call("DELETE", cid, secret, token)
        except urllib.error.HTTPError as failure:
            if failure.code in (400, 401, 404, 422):
                raise ApiError(403, "GitHub 확인 코드가 만료됐습니다. 다시 확인해 주세요.") from None
            raise ApiError(503, "GitHub 본인 확인을 마치지 못했습니다. 다시 시도해 주세요.") from None
        except (OSError, ValueError, TypeError, AttributeError):
            raise ApiError(503, "GitHub 본인 확인을 마치지 못했습니다. 다시 시도해 주세요.") from None
        if not valid:
            raise ApiError(403, "이 프로그램의 본인 확인 응답이 아닙니다.")
        viewer = self.digest("viewer:" + policy + ":" + account_hash + ":" + nonce)
        with self.database.connect() as db:
            if db.execute("SELECT value FROM identity_policy WHERE slot=1").fetchone() != (policy,):
                raise ApiError(409, "기기 확인 설정이 바뀌었습니다. 다시 확인해 주세요.")
            db.execute("DELETE FROM identity_receipts WHERE expires<=?", (now,))
            db.execute("INSERT OR IGNORE INTO identity_receipts (request_hash,member,expires,account_hash) VALUES (?,?,?,?)", (request_hash, int(member), now + 300, account_hash))
            db.execute("INSERT OR IGNORE INTO identity_installations VALUES (?,?)", (self.digest("installation:" + nonce), now))
            db.execute("INSERT OR IGNORE INTO identity_accounts VALUES (?,?)", (account_hash, now))
            db.execute("INSERT OR IGNORE INTO identity_grants (token_hash,policy,created,member) VALUES (?,?,?,?)", (hashed(viewer), policy, now, int(member)))
        return {"verified": True, "team": member, "token": viewer}

    def authenticate(self, authorization, require_team=True):
        from learning_server.app import ApiError, hashed
        if not authorization.startswith("Bearer ") or not re.fullmatch(r"[a-f0-9]{64}", authorization[7:]):
            raise ApiError(401, "기기 본인 확인이 필요합니다.")
        with self.database.connect() as db:
            allowed = db.execute("SELECT member FROM identity_grants WHERE token_hash=? AND (policy=? OR member=0)", (hashed(authorization[7:]), self.policy())).fetchone()
        if not allowed:
            raise ApiError(401, "기기 본인 확인을 다시 받아 주세요.")
        if require_team and not allowed[0]:
            raise ApiError(403, "스터디원에게만 제공하는 통계입니다.")
        return {"verified": True, "team": bool(allowed[0])}

    def summary(self, authorization, days, now=None):
        from learning_server.app import ApiError
        self.authenticate(authorization)
        if type(days) is not int or days not in PERIODS:
            raise ApiError(400, "조회 기간을 확인해 주세요.")
        now = now or datetime.datetime.now(KST)
        now = now.astimezone(KST)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=days - 1)
        step, size = (3600, 24) if days == 1 else (86400, days)
        begin, end = int(start.timestamp()), int(now.timestamp()) + 1
        with self.database.connect() as db:
            db.execute("BEGIN")
            joined = " FROM team_events LEFT JOIN team_attempts USING (participant, track, event_id) WHERE synthetic=0"
            total, undated, graded, graded_undated, unknown = db.execute("""
                SELECT count(*), count(CASE WHEN at IS NULL OR at>? THEN 1 END),
                       count(CASE WHEN confirmed=1 THEN 1 END),
                       count(CASE WHEN confirmed=1 AND (at IS NULL OR at>=?) THEN 1 END),
                       count(CASE WHEN confirmed=0 THEN 1 END)""" + joined, (end, end)).fetchone()
            values = db.execute("""SELECT (at-?)/? AS slot,track,count(*),count(CASE WHEN confirmed=1 THEN 1 END)"""
                                + joined + " AND at>=? AND at<? GROUP BY slot,track", (begin, step, begin, end)).fetchall()
            activity = activity_summary(db, start, step, size, end)
            installations = db.execute("SELECT count(*),coalesce(sum(first_seen>=? AND first_seen<?),0) FROM identity_installations", (begin, end)).fetchone()
            accounts = db.execute("SELECT count(*),coalesce(sum(first_seen>=? AND first_seen<?),0) FROM identity_accounts", (begin, end)).fetchone()
        series = [{"at": (start + datetime.timedelta(seconds=n * step)).isoformat(), "python": 0, "ai": 0} for n in range(size)]
        graded_series = [row.copy() for row in series]
        for slot, track, count, attempts in values:
            if 0 <= slot < size and track in ("python", "ai"):
                series[slot][track] = count
                graded_series[slot][track] = attempts
        return {"activity": activity, "total": total, "period_total": sum(row["python"] + row["ai"] for row in series),
                "graded": {"total": graded, "undated": graded_undated, "unknown": unknown, "series": graded_series,
                           "period_total": sum(row["python"] + row["ai"] for row in graded_series)},
                "undated": undated, "days": days, "series": series, "as_of": now.isoformat(), "time_basis": "recorded_at",
                "installations": installations[0], "period_installations": installations[1],
                "accounts": accounts[0], "period_accounts": accounts[1]}
