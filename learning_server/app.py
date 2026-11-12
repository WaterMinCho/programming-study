# -*- coding: utf-8 -*-
"""초대·참가자 인증·멱등 수집·본인 데이터 삭제를 제공하는 WSGI 앱임."""
import contextlib
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import tempfile
import uuid

from aiprep.collection import FORMAT, NOTICE, inside, packed

MAX_BODY = 1024 * 1024
MAX_EVENTS = 100
MAX_STORED_BYTES = 64 * 1024 * 1024
MAX_PARTICIPANT_BYTES = 8 * 1024 * 1024
MAX_PARTICIPANT_EVENTS = 20000
REPOSITORY = str(Path(__file__).resolve().parent.parent)


class ApiError(Exception):
    def __init__(self, status, message, code=None):
        self.code = code
        self.status, self.message = status, message


def hashed(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path):
        if inside(path, REPOSITORY):
            raise ValueError("수집 서버의 데이터 파일은 공개 저장소 밖에 지정해 주세요.")
        self.path = os.path.abspath(path)
        Path(self.path).parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        keyfile = self.path + ".key"
        try:
            fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as output:
                output.write(secrets.token_bytes(32))
        self.secret = Path(keyfile).read_bytes()
        if len(self.secret) != 32:
            raise ValueError("수집 서버의 인증 키 파일을 확인해 주세요.")
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS invites (
                    code_hash TEXT PRIMARY KEY, expires TEXT NOT NULL, participant TEXT
                );
                CREATE TABLE IF NOT EXISTS participants (
                    participant TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, notice TEXT NOT NULL,
                    enrolled TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events (
                    participant TEXT NOT NULL, track TEXT NOT NULL, event_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(participant, track, event_id), UNIQUE(participant, track, sequence)
                );
                CREATE TABLE IF NOT EXISTS open_enrollments (
                    participant TEXT PRIMARY KEY, purpose TEXT NOT NULL, receipt TEXT,
                    created TEXT NOT NULL, withdrawn TEXT
                );
            """)
            from learning_server.submissions import SCHEMA
            db.executescript(SCHEMA)
        if os.name != "nt":
            os.chmod(self.path, 0o600)

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def invites(self, count=1, days=7):
        if not 1 <= count <= 200 or not 1 <= days <= 30:
            raise ValueError("초대 수는 1~200, 유효 기간은 1~30일로 지정해 주세요.")
        expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).isoformat()
        codes = [secrets.token_urlsafe(24) for _ in range(count)]
        with self.connect() as db:
            db.executemany("INSERT INTO invites VALUES (?, ?, NULL)", [(hashed(code), expires) for code in codes])
        return codes

    def health(self):
        with contextlib.closing(sqlite3.connect(Path(self.path).as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("SELECT 1 FROM participants LIMIT 1").fetchone()

    def storage_limit(self, db, participant, extra_bytes, extra_events=0):
        """새로 저장할 분량을 논리 보관량과 대조함."""
        def used(where="", args=()):
            events = db.execute("SELECT count(*), coalesce(sum(length(CAST(payload AS BLOB))),0) FROM events" + where, args).fetchone()
            files = db.execute("SELECT coalesce(sum(length(payload)),0) FROM api_submissions" + where, args).fetchone()[0]
            return events[0], events[1]+files
        count, own = used(" WHERE participant=?", (participant,))
        total = used()[1]
        if total+extra_bytes > MAX_STORED_BYTES or own+extra_bytes > MAX_PARTICIPANT_BYTES or count+extra_events > MAX_PARTICIPANT_EVENTS:
            raise ApiError(507, "서버의 기록 보관량에 도달했습니다. 로컬 풀이는 유지되며 운영자 확인 후 다시 전송합니다.")

    def enroll(self, data, connection=None):
        if connection is not None:
            return self._enroll(connection, data)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._enroll(db, data)

    def _enroll(self, db, data):
        participant = identifier(data.get("participant"))
        code = data.get("invite")
        if not isinstance(code, str) or not 16 <= len(code) <= 128 or data.get("notice") != NOTICE:
            raise ApiError(400, "초대 코드와 전송 동의 항목을 확인해 주세요.")
        invite = db.execute("SELECT expires, participant FROM invites WHERE code_hash=?", (hashed(code),)).fetchone()
        if not invite or datetime.datetime.fromisoformat(invite[0]) <= datetime.datetime.now(datetime.timezone.utc):
            raise ApiError(403, "초대 코드가 없거나 만료됐습니다.")
        if invite[1] not in (None, participant):
            raise ApiError(403, "이미 사용한 초대 코드입니다.")
        token = hmac.new(self.secret, (code + ":" + participant).encode("utf-8"), hashlib.sha256).hexdigest()
        old = db.execute("SELECT token_hash, revoked FROM participants WHERE participant=?", (participant,)).fetchone()
        if old and (old[0] != hashed(token) or old[1]):
            raise ApiError(409, "이미 등록되거나 철회한 참가자입니다. 관리자에게 새 등록을 요청해 주세요.")
        db.execute("INSERT OR IGNORE INTO participants VALUES (?, ?, ?, ?, 0)",
                   (participant, hashed(token), NOTICE, datetime.datetime.now(datetime.timezone.utc).isoformat()))
        db.execute("UPDATE invites SET participant=? WHERE code_hash=?", (participant, hashed(code)))
        return {"participant": participant, "token": token}

    def authenticate(self, authorization, allow_revoked=False):
        if not authorization.startswith("Bearer "):
            raise ApiError(401, "참가자 인증이 필요합니다.")
        token = authorization[7:]
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise ApiError(401, "참가자 인증을 확인해 주세요.")
        with self.connect() as db:
            row = db.execute("SELECT participant, revoked FROM participants WHERE token_hash=?", (hashed(token),)).fetchone()
        if not row:
            raise ApiError(401, "참가자 인증을 확인해 주세요.")
        if row[1] and not allow_revoked:
            raise ApiError(401, "철회한 참가자의 인증입니다.", code="revoked")
        return row[0]

    def enroll_open(self, data, purpose="research", connection=None):
        if os.environ.get("STUDY_OPEN_REGISTRATION") != "1":
            raise ApiError(503, "첫 실행 연결을 준비 중입니다. 학습은 계속할 수 있습니다.")
        if connection is None:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                return self.enroll_open(data, purpose, connection=db)
        from aiprep.privacy import validate_receipt
        participant = identifier(data.get("participant"))
        seed = data.get("registration_secret")
        if data.get("notice") != NOTICE or not isinstance(seed, str) or not re.fullmatch(r"[a-f0-9]{64}", seed):
            raise ApiError(400, "기기의 연결 정보를 확인해 주세요.")
        if purpose in ("research", "private_submission"):
            consent = validate_receipt(data.get("consent"))
            if purpose == "private_submission" and data.get("private_submission") is not True:
                raise ApiError(400, "비공개로 보낼 풀이 파일을 확인해 주세요.")
        elif data.get("public_submission") is True:
            consent = {"public_submission": True}
        else:
            raise ApiError(400, "공개할 풀이 파일을 확인한 뒤 제출해 주세요.")
        token = hmac.new(self.secret, (purpose + ":" + participant + ":" + seed).encode(), hashlib.sha256).hexdigest()
        db = connection
        old = db.execute("SELECT token_hash, revoked FROM participants WHERE participant=?", (participant,)).fetchone()
        if old:
            if old != (hashed(token), 0):
                raise ApiError(409, "기존 연결 또는 철회 상태를 확인해 주세요.")
        else:
            now = datetime.datetime.now(datetime.timezone.utc)
            count = db.execute("SELECT count(*) FROM open_enrollments WHERE purpose<>'withdrawal' AND created>=?",
                               ((now-datetime.timedelta(days=1)).isoformat(),)).fetchone()[0]
            if count >= 1000:
                raise ApiError(429, "오늘의 새 연결이 많아 잠시 대기합니다. 학습은 계속할 수 있습니다.")
            db.execute("INSERT INTO participants VALUES (?, ?, ?, ?, 0)", (participant, hashed(token), NOTICE, now.isoformat()))
            db.execute("INSERT INTO open_enrollments VALUES (?, ?, ?, ?, NULL)",
                       (participant, purpose, packed(consent), now.isoformat()))
        return {"participant": participant, "token": token}

    def record_consent(self, participant, data):
        from aiprep.privacy import validate_receipt
        consent = validate_receipt(data.get("consent"))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM participants WHERE participant=? AND revoked=0", (participant,)).fetchone():
                raise ApiError(401, "철회한 참가자입니다.")
            db.execute("INSERT INTO open_enrollments VALUES (?, 'research', ?, ?, NULL) "
                       "ON CONFLICT(participant) DO UPDATE SET receipt=excluded.receipt",
                       (participant, packed(consent), datetime.datetime.now(datetime.timezone.utc).isoformat()))
        return {"consent_saved": True}

    def withdraw_open(self, data, purpose="research"):
        participant = identifier(data.get("participant"))
        seed = data.get("registration_secret")
        if not isinstance(seed, str) or not re.fullmatch(r"[a-f0-9]{64}", seed):
            raise ApiError(400, "기기의 연결 정보를 확인해 주세요.")
        token = hmac.new(self.secret, (purpose + ":" + participant + ":" + seed).encode(), hashlib.sha256).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT token_hash FROM participants WHERE participant=?", (participant,)).fetchone()
            if old and old != (hashed(token),):
                raise ApiError(403, "철회할 기기의 연결 정보를 확인해 주세요.")
            if not old:
                now = datetime.datetime.now(datetime.timezone.utc)
                count = db.execute("SELECT count(*) FROM open_enrollments WHERE purpose='withdrawal' AND created>=?",
                                   ((now-datetime.timedelta(days=1)).isoformat(),)).fetchone()[0]
                if count >= 10000:
                    raise ApiError(429, "새 연결 처리가 많아 잠시 뒤 철회를 다시 확인합니다.")
                db.execute("INSERT INTO open_enrollments VALUES (?, 'withdrawal', NULL, ?, ?)",
                           (participant, now.isoformat(), now.isoformat()))
            db.execute("INSERT OR IGNORE INTO participants VALUES (?, ?, ?, ?, 1)",
                       (participant, hashed(token), NOTICE, datetime.datetime.now(datetime.timezone.utc).isoformat()))
        self.remove(participant)
        return {"deleted": True}

    def ingest(self, participant, data):
        if data.get("participant") != participant or data.get("notice") != NOTICE or data.get("format") != FORMAT:
            raise ApiError(400, "참가자·전송 동의·파일 형식을 확인해 주세요.")
        track, events = data.get("track"), data.get("events")
        if track not in ("ai", "python") or not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
            raise ApiError(400, "과목과 전송 건수를 확인해 주세요.")
        cleaned = []
        previous = 0
        for row in events:
            if not isinstance(row, dict) or row.get("participant") != participant or row.get("track") != track or row.get("format") != FORMAT:
                raise ApiError(400, "기록의 참가자와 과목이 맞지 않습니다.")
            identifier(row.get("event_id"))
            seq = row.get("sequence")
            if type(seq) is not int or not previous < seq <= 2 ** 63 - 1:
                raise ApiError(400, "기록 순서가 맞지 않습니다.")
            previous = seq
            if not isinstance(row.get("data"), dict) or not isinstance(row.get("at"), str) or len(row["at"]) > 80:
                raise ApiError(400, "기록 내용과 시각을 확인해 주세요.")
            try:
                if datetime.datetime.fromisoformat(row["at"]).tzinfo is None:
                    raise ValueError()
            except ValueError:
                raise ApiError(400, "기록 시각에 날짜·시각·시간대를 함께 보내 주세요.")
            if not re.fullmatch(r"[a-z_]{1,48}", str(row.get("kind", ""))):
                raise ApiError(400, "기록 종류를 확인해 주세요.")
            revision = row.get("item_revision")
            if revision is not None and (not re.fullmatch(r"[a-f0-9]{64}", str(revision)) or not isinstance(row.get("item"), dict)):
                raise ApiError(400, "문항 판과 지문을 확인해 주세요.")
            cleaned.append((participant, track, row["event_id"], seq, packed(row)))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM participants WHERE participant=? AND revoked=0", (participant,)).fetchone():
                raise ApiError(401, "철회한 참가자입니다.")
            if os.environ.get("STUDY_OPEN_REGISTRATION") == "1" and not db.execute(
                    "SELECT 1 FROM open_enrollments WHERE participant=? AND purpose='research' AND receipt IS NOT NULL AND withdrawn IS NULL",
                    (participant,)).fetchone():
                raise ApiError(403, "현재 수집 동의를 확인한 뒤 전송해 주세요.")
            fresh = []
            for values in cleaned:
                old = db.execute("SELECT payload FROM events WHERE participant=? AND track=? AND event_id=?", values[:3]).fetchone()
                if old and old[0] != values[4]:
                    raise ApiError(409, "이미 받은 기록의 내용이 달라 저장하지 않았습니다.")
                if not old:
                    fresh.append(values)
            if fresh:
                self.storage_limit(db, participant, sum(len(row[4].encode("utf-8")) for row in fresh), len(fresh))
                try:
                    db.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?)", fresh)
                except sqlite3.IntegrityError:
                    raise ApiError(409, "기록의 고유번호와 순서가 겹칩니다.")
        return {"received": len(cleaned), "last_sequence": previous}

    def remove(self, participant):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if db.execute("SELECT 1 FROM api_submissions WHERE participant=? AND lease_until>?", (participant, now)).fetchone():
                raise ApiError(409, "GitHub 게시가 끝난 뒤 다시 삭제해 주세요.")
            children = [row[0] for row in db.execute("SELECT participant FROM submission_collections WHERE account=?", (participant,))]
            for target in [participant] + children:
                db.execute("DELETE FROM events WHERE participant=?", (target,))
                db.execute("UPDATE participants SET revoked=1 WHERE participant=?", (target,))
                db.execute("UPDATE open_enrollments SET receipt=NULL, withdrawn=? WHERE participant=?", (now, target))
            db.execute("DELETE FROM api_submissions WHERE participant=?", (participant,))
            db.execute("DELETE FROM submission_collections WHERE account=? OR participant=?", (participant, participant))
            db.execute("DELETE FROM submission_accounts WHERE participant=?", (participant,))

    def export(self, destination, include_answers=False):
        if inside(destination, REPOSITORY) or inside(destination, os.path.dirname(self.path)):
            raise ValueError("공개 저장소와 서버 데이터 폴더 밖의 새 파일을 골라 주세요.")
        if os.path.lexists(destination):
            raise ValueError("이미 있는 파일입니다. 다른 이름을 골라 주세요.")
        fd, temp = tempfile.mkstemp(prefix=".dataset-", dir=os.path.dirname(os.path.abspath(destination)))
        try:
            expected, count = hashlib.sha256(), 0
            with self.connect() as db, os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
                db.execute("BEGIN")
                for row in db.execute("SELECT payload FROM events ORDER BY participant, track, sequence"):
                    value = json.loads(row[0])
                    value.setdefault("synthetic", False)
                    if not include_answers:
                        value["data"].pop("response", None)
                    line = packed(value) + "\n"
                    output.write(line)
                    expected.update(line.encode("utf-8"))
                    count += 1
                output.flush()
                os.fsync(output.fileno())
            actual = hashlib.sha256()
            with open(temp, "rb") as saved:
                for line in saved:
                    json.loads(line)
                    actual.update(line)
            if actual.digest() != expected.digest():
                raise ValueError("내보낸 파일의 내용을 확인하지 못했습니다.")
            os.link(temp, destination)
            return {"events": count, "sha256": actual.hexdigest()}
        finally:
            if os.path.exists(temp):
                os.unlink(temp)


def identifier(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ApiError(400, "가명 구분값과 기록 고유번호를 확인해 주세요.")
    return value


def application(database, *, legacy_contract=False):
    from learning_server.submissions import Submissions
    submissions = Submissions(database)
    def app(environ, start_response):
        try:
            method, path = environ.get("REQUEST_METHOD"), environ.get("PATH_INFO")
            if not legacy_contract and path in ("/v1/register", "/v1/register/open", "/v1/submissions", "/v1/submissions/publish"):
                raise ApiError(410, "공개 풀이 제출을 종료했습니다. 프로그램을 업데이트해 비공개로 제출해 주세요.")
            if method == "GET" and path == "/health":
                database.health()
                result = {"status": "ok", "format": FORMAT}
            elif method == "POST" and path in ("/v1/enroll", "/v1/enroll/open", "/v1/withdraw/open", "/v1/withdraw/private", "/v1/events", "/v1/consent", "/v1/register", "/v1/register/open", "/v1/register/private", "/v1/submissions", "/v1/private/submissions", "/v1/submissions/publish"):
                length = int(environ.get("CONTENT_LENGTH") or 0)
                limit = 6 * MAX_BODY if path in ("/v1/submissions", "/v1/private/submissions") else MAX_BODY
                if length <= 0 or length > limit:
                    raise ApiError(413, "전송 크기를 확인해 주세요.")
                if environ.get("CONTENT_TYPE", "").split(";")[0].strip() != "application/json":
                    raise ApiError(415, "JSON 형식으로 보내 주세요.")
                participant = database.authenticate(environ.get("HTTP_AUTHORIZATION", "")) if path not in ("/v1/enroll", "/v1/enroll/open", "/v1/withdraw/open", "/v1/withdraw/private", "/v1/register", "/v1/register/open", "/v1/register/private") else None
                raw = environ["wsgi.input"].read(length)
                if len(raw) != length:
                    raise ApiError(400, "전송 내용을 끝까지 받지 못했습니다.")
                data = json.loads(raw.decode("utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                if not isinstance(data, dict):
                    raise ApiError(400, "JSON 객체로 보내 주세요.")
                if path == "/v1/enroll":
                    result = database.enroll(data)
                elif path == "/v1/enroll/open":
                    result = database.enroll_open(data)
                elif path == "/v1/withdraw/open":
                    result = database.withdraw_open(data)
                elif path == "/v1/withdraw/private":
                    result = database.withdraw_open(data, "private_submission")
                elif path == "/v1/consent":
                    result = database.record_consent(participant, data)
                elif path == "/v1/events":
                    result = database.ingest(participant, data)
                elif path == "/v1/register/private":
                    result = submissions.register(data, open_registration=True, private=True)
                elif path in ("/v1/register", "/v1/register/open"):
                    result = submissions.register(data, open_registration=path.endswith("/open"))
                elif path == "/v1/private/submissions":
                    with database.connect() as db:
                        allowed = db.execute("SELECT 1 FROM open_enrollments WHERE participant=? AND purpose='private_submission' AND withdrawn IS NULL", (participant,)).fetchone()
                    if not allowed:
                        raise ApiError(403, "비공개 풀이 제출 연결이 필요합니다.")
                    result = submissions.store(participant, data)
                elif path == "/v1/submissions":
                    result = submissions.store(participant, data)
                else:
                    result = submissions.publish(participant, data)
            elif method == "DELETE" and path == "/v1/me":
                database.remove(database.authenticate(environ.get("HTTP_AUTHORIZATION", ""), allow_revoked=True))
                result = {"deleted": True}
            else:
                raise ApiError(404, "요청한 경로가 없습니다.")
            code = 200
        except ApiError as error:
            code, result = error.status, {"error": error.message}
            if error.code:
                result["code"] = error.code
        except (ValueError, UnicodeError, RecursionError):
            code, result = 400, {"error": "요청 내용을 읽을 수 없습니다."}
        except (sqlite3.Error, OSError):
            code, result = 503, {"error": "수집 서버를 사용할 수 없습니다. 잠시 뒤 다시 보내 주세요."}
        body = packed(result).encode("utf-8")
        from http import HTTPStatus
        start_response("%d %s" % (code, HTTPStatus(code).phrase),
                       [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")])
        return [body]
    return app
