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
REPOSITORY = str(Path(__file__).resolve().parent.parent)


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def hashed(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path):
        if inside(path, REPOSITORY):
            raise ValueError("수집 서버의 데이터 파일은 공개 저장소 밖에 지정해 주세요.")
        self.path = os.path.abspath(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
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
            """)
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

    def enroll(self, data):
        participant = identifier(data.get("participant"))
        code = data.get("invite")
        if not isinstance(code, str) or not 16 <= len(code) <= 128 or data.get("notice") != NOTICE:
            raise ApiError(400, "초대 코드와 전송 동의 항목을 확인해 주세요.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
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
            row = db.execute("SELECT participant FROM participants WHERE token_hash=?" + ("" if allow_revoked else " AND revoked=0"), (hashed(token),)).fetchone()
        if not row:
            raise ApiError(401, "참가자 인증을 확인해 주세요.")
        return row[0]

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
            for values in cleaned:
                old = db.execute("SELECT payload FROM events WHERE participant=? AND track=? AND event_id=?", values[:3]).fetchone()
                if old and old[0] != values[4]:
                    raise ApiError(409, "이미 받은 기록의 내용이 달라 저장하지 않았습니다.")
                try:
                    if not old:
                        db.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)", values)
                except sqlite3.IntegrityError:
                    raise ApiError(409, "기록의 고유번호와 순서가 겹칩니다.")
        return {"received": len(cleaned), "last_sequence": previous}

    def remove(self, participant):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM events WHERE participant=?", (participant,))
            db.execute("UPDATE participants SET revoked=1 WHERE participant=?", (participant,))

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


def application(database):
    def app(environ, start_response):
        try:
            method, path = environ.get("REQUEST_METHOD"), environ.get("PATH_INFO")
            if method == "GET" and path == "/health":
                result = {"status": "ok", "format": FORMAT}
            elif method == "POST" and path in ("/v1/enroll", "/v1/events"):
                length = int(environ.get("CONTENT_LENGTH") or 0)
                if length <= 0 or length > MAX_BODY:
                    raise ApiError(413, "전송 크기를 확인해 주세요.")
                if environ.get("CONTENT_TYPE", "").split(";")[0].strip() != "application/json":
                    raise ApiError(415, "JSON 형식으로 보내 주세요.")
                participant = database.authenticate(environ.get("HTTP_AUTHORIZATION", "")) if path == "/v1/events" else None
                raw = environ["wsgi.input"].read(length)
                if len(raw) != length:
                    raise ApiError(400, "전송 내용을 끝까지 받지 못했습니다.")
                data = json.loads(raw.decode("utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                if not isinstance(data, dict):
                    raise ApiError(400, "JSON 객체로 보내 주세요.")
                result = database.enroll(data) if path == "/v1/enroll" else database.ingest(participant, data)
            elif method == "DELETE" and path == "/v1/me":
                database.remove(database.authenticate(environ.get("HTTP_AUTHORIZATION", ""), allow_revoked=True))
                result = {"deleted": True}
            else:
                raise ApiError(404, "요청한 경로가 없습니다.")
            code = 200
        except ApiError as error:
            code, result = error.status, {"error": error.message}
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
