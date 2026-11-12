# -*- coding: utf-8 -*-
"""초대 인증을 재사용해 공개 풀이를 접수하고 GitHub 게시 상태를 보관함."""
import datetime
import hashlib
import hmac
import json
from pathlib import PurePosixPath
import re
import secrets
import sqlite3
import uuid
import zlib
import unicodedata

from aiprep.collection import NOTICE, digest, packed, stamp
from learning_server.app import ApiError, hashed, identifier
from learning_server.github import Publisher, PublishError

MAX_BYTES = 4 * 1024 * 1024
MAX_FILES = 1000
MIN_INTERVAL = 5
MAX_DAILY = 100
SCHEMA = """
CREATE TABLE IF NOT EXISTS submission_accounts (
    participant TEXT PRIMARY KEY, display_id TEXT COLLATE NOCASE NOT NULL UNIQUE, public_id TEXT UNIQUE NOT NULL, latest TEXT
);
CREATE TABLE IF NOT EXISTS submission_collections (
    participant TEXT PRIMARY KEY, account TEXT NOT NULL, track TEXT NOT NULL,
    UNIQUE(account, track)
);
CREATE TABLE IF NOT EXISTS api_submissions (
    participant TEXT NOT NULL, digest TEXT NOT NULL, payload BLOB, received TEXT NOT NULL,
    pr_url TEXT, lease TEXT, lease_until TEXT,
    PRIMARY KEY(participant, digest)
);
"""


def clean_files(files):
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise ApiError(400, "제출할 풀이 파일 수를 확인해 주세요.")
    total = 0
    names = set()
    for path, text in files.items():
        if not isinstance(path, str) or len(path) > 240 or "\\" in path or ":" in path or "\x00" in path:
            raise ApiError(400, "풀이 파일의 경로를 확인해 주세요.")
        parts = path.split("/")
        normal = unicodedata.normalize("NFC", path).casefold()
        reserved = {"CON", "PRN", "AUX", "NUL"} | {prefix + str(i) for prefix in ("COM", "LPT") for i in range(1, 10)}
        if any(p.split(".")[0].upper() in reserved for p in parts):
            raise ApiError(400, "Windows에서 열 수 없는 파일 이름입니다.")
        if normal in names or any(p.endswith((" ", ".")) or re.search(r'[<>"|?*\x00-\x1f]', p) for p in parts):
            raise ApiError(400, "다른 운영체제에서 겹치거나 열 수 없는 파일 이름입니다.")
        names.add(normal)
        if any(not p or p.startswith(".") or p in ("node_modules", "__pycache__") for p in parts):
            raise ApiError(400, "숨김 파일과 풀이 폴더 밖의 파일은 제출할 수 없습니다.")
        if str(PurePosixPath(path)) != path or PurePosixPath(path).is_absolute():
            raise ApiError(400, "상대 경로로 된 풀이 파일만 제출할 수 있습니다.")
        if not (path == "profile.json" or re.match(r"(?:[rsmc][0-9]+|journey|ai|web)/", path)):
            raise ApiError(400, "프로그램의 풀이 파일만 제출할 수 있습니다.")
        if PurePosixPath(path).suffix.lower() not in (".py", ".js", ".json", ".md", ".txt", ".html", ".css", ".ts", ".tsx", ".jsx"):
            raise ApiError(400, "지원하지 않는 풀이 파일입니다.")
        if parts[-1] in ("learning-data-sharing.json", "submission-api.json") or not isinstance(text, str):
            raise ApiError(400, "서버 연결 설정은 공개 풀이에 포함할 수 없습니다.")
        total += len(text.encode("utf-8"))
        if total > MAX_BYTES:
            raise ApiError(413, "풀이 파일이 4MiB를 넘습니다. 스터디장에게 알려 주세요.")
    return files


class Submissions:
    def __init__(self, database, publisher=None):
        self.database, self.publisher = database, publisher

    def register(self, data, open_registration=False, private=False):
        name, tracks = data.get("display_id"), data.get("tracks", {})
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
            raise ApiError(400, "풀이 ID는 영문·숫자·밑줄·붙임표로 64자 안에 입력해 주세요.")
        if not isinstance(tracks, dict) or set(tracks) - {"ai", "python"}:
            raise ApiError(400, "연결할 학습 과목을 확인해 주세요.")
        if open_registration and tracks:
            raise ApiError(400, "비공개 학습 기록은 동의 후 과목별 연결을 사용합니다.")
        parent = identifier(data.get("participant"))
        children = [identifier(value) for value in tracks.values()]
        if len(set([parent] + children)) != len(children) + 1:
            raise ApiError(400, "과목별 가명 구분값이 겹칩니다.")
        connected = {}
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            enrolled = (self.database.enroll_open(data, "private_submission" if private else "submission", connection=db) if open_registration
                        else self.database.enroll(data, connection=db))
            if not db.execute("SELECT 1 FROM participants WHERE participant=? AND revoked=0", (parent,)).fetchone():
                raise ApiError(401, "철회한 참가자입니다.")
            old = db.execute("SELECT display_id, public_id FROM submission_accounts WHERE participant=?", (parent,)).fetchone()
            if old and old[0] != name:
                raise ApiError(409, "이미 연결한 풀이 ID가 다릅니다.")
            public_id = old[1] if old else "api_" + uuid.uuid4().hex
            if not old:
                try:
                    db.execute("INSERT INTO submission_accounts VALUES (?, ?, ?, NULL)", (parent, name, public_id))
                except sqlite3.IntegrityError:
                    raise ApiError(409, "이미 연결한 풀이 ID입니다. 다른 ID를 정해 주세요.") from None
            saved = dict(db.execute("SELECT track, participant FROM submission_collections WHERE account=?", (parent,)))
            if old and saved != tracks:
                raise ApiError(409, "이미 연결한 과목의 가명 정보가 달라 등록을 멈췄습니다.")
            for track, child in tracks.items():
                token = hmac.new(self.database.secret, (parent + ":collection:" + child).encode(), hashlib.sha256).hexdigest()
                existing = db.execute("SELECT token_hash, revoked FROM participants WHERE participant=?", (child,)).fetchone()
                if existing and existing != (hashed(token), 0):
                    raise ApiError(409, "이미 다른 연결에 등록된 학습 자료입니다. 기존 연결을 유지해 주세요.")
                db.execute("INSERT OR IGNORE INTO participants VALUES (?, ?, ?, ?, 0)", (child, hashed(token), NOTICE, stamp()))
                db.execute("INSERT OR IGNORE INTO submission_collections VALUES (?, ?, ?)", (child, parent, track))
                connected[track] = {"participant": child, "token": token}
        return dict(enrolled, public_id=public_id, tracks=connected)

    def store(self, participant, data):
        files = clean_files(data.get("files"))
        envelope = {"files": files, "request": identifier(data.get("request_id"))}
        current = digest(envelope)
        if data.get("digest") != current:
            raise ApiError(400, "제출 파일과 해시가 맞지 않습니다.")
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM participants WHERE participant=? AND revoked=0", (participant,)).fetchone():
                raise ApiError(401, "철회한 참가자입니다.")
            account = db.execute("SELECT latest FROM submission_accounts WHERE participant=?", (participant,)).fetchone()
            if not account:
                raise ApiError(403, "API 풀이 제출 연결이 필요합니다.")
            previous = db.execute("SELECT pr_url FROM api_submissions WHERE participant=? AND digest=?", (participant, current)).fetchone()
            if previous:
                return self.receipt(current, previous[0])
            if account[0] != data.get("previous"):
                raise ApiError(409, "서버에 다른 풀이가 먼저 저장됐습니다. 이전 접수 결과를 확인한 뒤 다시 제출해 주세요.")
            instant = datetime.datetime.now(datetime.timezone.utc)
            now = instant.isoformat()
            recent = db.execute("SELECT max(received) FROM api_submissions WHERE participant=?", (participant,)).fetchone()[0]
            if recent and (instant - datetime.datetime.fromisoformat(recent)).total_seconds() < MIN_INTERVAL:
                raise ApiError(429, "풀이 제출이 연속으로 들어왔습니다. 5초 뒤 다시 제출해 주세요.")
            count = db.execute("SELECT count(*) FROM api_submissions WHERE participant=? AND received>=?",
                               (participant, (instant - datetime.timedelta(days=1)).isoformat())).fetchone()[0]
            if count >= MAX_DAILY:
                raise ApiError(429, "최근 24시간의 파일 제출 100회에 도달했습니다. 학습과 과정 기록 전송은 계속 사용할 수 있습니다.")
            busy = db.execute("SELECT 1 FROM api_submissions WHERE participant=? AND lease_until>?", (participant, now)).fetchone()
            if busy:
                raise ApiError(409, "이전 풀이를 GitHub에 게시 중입니다. 잠시 뒤 다시 제출해 주세요.")
            payload = zlib.compress(packed(envelope).encode("utf-8"))
            previous_bytes = db.execute("SELECT coalesce(sum(length(payload)),0) FROM api_submissions WHERE participant=?", (participant,)).fetchone()[0]
            self.database.storage_limit(db, participant, len(payload)-previous_bytes)
            db.execute("UPDATE api_submissions SET payload=NULL WHERE participant=?", (participant,))
            db.execute("INSERT INTO api_submissions VALUES (?, ?, ?, ?, NULL, NULL, NULL)",
                       (participant, current, payload, now))
            db.execute("UPDATE submission_accounts SET latest=? WHERE participant=?", (current, participant))
        return self.receipt(current, None)

    @staticmethod
    def receipt(current, url):
        return {"digest": current, "state": "published" if url else "stored", "pr_url": url}

    def publish(self, participant, data):
        current = data.get("digest")
        if not isinstance(current, str) or not re.fullmatch(r"[a-f0-9]{64}", current):
            raise ApiError(400, "풀이 접수 번호를 확인해 주세요.")
        lease = secrets.token_hex(16)
        now = datetime.datetime.now(datetime.timezone.utc)
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM participants WHERE participant=? AND revoked=0", (participant,)).fetchone():
                raise ApiError(401, "철회한 참가자입니다.")
            row = db.execute("SELECT s.payload, s.pr_url, s.lease_until, a.display_id, a.latest, a.public_id FROM api_submissions s "
                             "JOIN submission_accounts a ON a.participant=s.participant WHERE s.participant=? AND s.digest=?",
                             (participant, current)).fetchone()
            if not row:
                raise ApiError(404, "서버에 저장된 풀이 접수를 찾지 못했습니다.")
            payload, url, until, display, latest, public_id = row
            if url:
                return self.receipt(current, url)
            if latest != current or payload is None:
                raise ApiError(409, "더 최근 풀이가 저장돼 이전 접수의 게시를 멈췄습니다.")
            if until and datetime.datetime.fromisoformat(until) > now:
                raise ApiError(409, "GitHub에 게시 중입니다. 잠시 뒤 다시 확인해 주세요.")
            db.execute("UPDATE api_submissions SET lease=?, lease_until=? WHERE participant=? AND digest=?",
                       (lease, (now + datetime.timedelta(seconds=90)).isoformat(), participant, current))
        try:
            envelope = json.loads(zlib.decompress(payload))
            if digest(envelope) != current:
                raise ApiError(503, "저장한 풀이의 무결성을 확인하지 못했습니다.")
            files = envelope["files"]
            clean_files(files)
            publisher = self.publisher or Publisher.configured()
            def before_write():
                with self.database.connect() as db:
                    owned = db.execute("SELECT 1 FROM api_submissions s JOIN participants p ON p.participant=s.participant "
                                       "WHERE s.participant=? AND s.digest=? AND s.lease=? AND s.lease_until>? AND p.revoked=0",
                                       (participant, current, lease, datetime.datetime.now(datetime.timezone.utc).isoformat())).fetchone()
                if not owned:
                    raise PublishError("게시 확인 시간이 지나 멈췄습니다. 다시 제출해 주세요.")

            url = publisher.publish(public_id, display, current, files, before_write=before_write)
            with self.database.connect() as db:
                updated = db.execute("UPDATE api_submissions SET pr_url=? WHERE participant=? AND digest=? AND lease=?",
                                     (url, participant, current, lease)).rowcount
                if not updated:
                    raise PublishError("GitHub 게시 후 서버의 접수 상태를 다시 확인해 주세요.")
            return self.receipt(current, url)
        except PublishError as error:
            raise ApiError(503, str(error)) from None
        except (zlib.error, ValueError, KeyError):
            raise ApiError(503, "저장한 풀이 내용을 확인하지 못했습니다. 관리자에게 알려 주세요.") from None
        finally:
            with self.database.connect() as db:
                db.execute("UPDATE api_submissions SET lease=NULL, lease_until=NULL WHERE participant=? AND digest=? AND lease=?",
                           (participant, current, lease))
