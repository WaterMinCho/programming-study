# -*- coding: utf-8 -*-
"""시범 초대와 읽기 전용 점검, 인증 키를 포함한 백업·복구를 제공함."""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from learning_data.collection import FORMAT, inside, packed, stamp
from learning_data.sharing import endpoint, request
from learning_server.app import REPOSITORY

BACKUP_FILES = ("learning.sqlite3", "learning.sqlite3.key")


def private_path(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    if inside(str(path), REPOSITORY):
        raise ValueError("운영 파일은 공개 저장소 밖에 보관해 주세요.")
    return path


@contextlib.contextmanager
def read_database(path):
    path = private_path(path)
    if not path.is_file():
        raise ValueError("기존 수집 데이터베이스 파일을 지정해 주세요.")
    with contextlib.closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        yield db


def read_key(path):
    value = Path(str(path) + ".key").read_bytes()
    if len(value) != 32:
        raise ValueError("데이터베이스와 함께 보관한 인증 키를 확인해 주세요.")
    return value


def status(path):
    path = private_path(path)
    read_key(path)
    with read_database(path) as db:
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("데이터베이스 무결성 검사에 실패했습니다.")
        active, revoked = db.execute(
            "SELECT coalesce(sum(revoked=0),0), coalesce(sum(revoked<>0),0) FROM participants"
        ).fetchone()
        tracks = dict(db.execute("SELECT track, count(*) FROM events GROUP BY track"))
        available = db.execute(
            "SELECT count(*) FROM invites WHERE participant IS NULL AND julianday(expires)>julianday(?)",
            (datetime.datetime.now(datetime.timezone.utc).isoformat(),)
        ).fetchone()[0]
    return {"status": "ok", "active_accounts": active, "revoked_accounts": revoked,
            "events": {track: tracks.get(track, 0) for track in ("ai", "python")},
            "available_invites": available, "database_bytes": path.stat().st_size}


@contextlib.contextmanager
def new_directory(destination, source=None):
    destination = private_path(destination)
    if source and inside(str(destination), str(private_path(source))):
        raise ValueError("원본 폴더 밖의 새 폴더를 지정해 주세요.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(mode=0o700)
    try:
        yield destination
    except BaseException:
        shutil.rmtree(destination)
        raise


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    if path.read_bytes() != data:
        raise ValueError("저장한 운영 파일을 다시 읽어 확인하지 못했습니다.")


def pilot(database, destination, url, days=7):
    """네 명에게 과목별 초대를 발급함. 등록과 전송 동의는 참가자가 직접 함."""
    url = endpoint(url)
    with new_directory(destination, Path(database.path).parent) as directory, database.prepare_invites(8, days) as codes:
        for index in range(4):
            message = (
                "운영자용 이전 시범 초대입니다\n\n"
                "서버 주소: %s\n"
                "AI 개론·응용 초대 코드: %s\n"
                "파이썬 초대 코드: %s\n"
                "초대 유효 기간: 발급 후 %d일\n\n"
                "일반 수강생에게는 개인 초대 파일이 필요하지 않습니다. 첫 실행에서 동의 여부를 선택합니다.\n"
                "동의 후 자동 전송하는 연구 기록에는 답안 본문이 없습니다. 답안 파일 자동 제출은 따로 선택합니다. 연구 자료를 내보낼 때 입력 답안 포함은 기본으로 꺼져 있습니다.\n"
                "동의 상태와 철회는 [내 정보·데이터]에서 관리하며, 동의하지 않아도 학습·로컬 채점은 사용할 수 있습니다.\n"
                "위 코드는 운영자가 별도 시범 연결을 안내한 경우에만 사용합니다.\n"
                "내보낸 사본과 백업 삭제는 프로그램 담당에게 별도로 요청합니다.\n"
                "두 코드는 본인만 사용하며 공개 채널이나 저장소에 올리지 않습니다.\n"
            ) % (url, codes[index * 2], codes[index * 2 + 1], days)
            write_private(directory / ("member-%02d.txt" % (index + 1)), message.encode("utf-8"))
        result = {"members": 4, "invites": 8, "tracks": ["ai", "python"], "url": url,
                  "created_at": stamp(), "expires_in_days": days}
        write_private(directory / "manifest.json", (packed(result) + "\n").encode("utf-8"))
    return result


def check(url):
    result = request(endpoint(url), "/health", method="GET")
    if result.get("status") != "ok" or result.get("format") != FORMAT:
        raise ValueError("서버의 상태와 수집 형식 응답을 확인해 주세요.")
    return result


def class_invites(database, destination, url, count=100, days=7):
    """참가자당 하나의 API 개인 초대를 새 비공개 폴더에 저장함."""
    url = endpoint(url)
    with new_directory(destination, Path(database.path).parent) as directory, database.prepare_invites(count, days) as codes:
        for index, code in enumerate(codes, 1):
            text = ("운영자용 이전 시범 초대\n\n서버 주소: %s\n개인 초대 코드: %s\n"
                    "발급 후 %d일 안에 연결합니다.\n\n"
                    "일반 수강생은 이 초대 파일을 사용하지 않습니다. 첫 실행에서 수집 동의 여부를 선택합니다.\n"
                    "동의 후 새 학습 기록을 비공개 서버로 자동 전송하며 입력 답안 본문은 제외합니다.\n"
                    "답안 파일은 [풀이 제출]을 눌러 비공개로 보냅니다. [답안 파일도 자동 제출]을 켜면 프로그램을 열거나 문제 묶음을 채점할 때 미제출 파일을 보냅니다.\n"
                    "동의 상태와 철회는 [내 정보·데이터]에서 관리합니다.\n"
                    "이 초대는 한 사람만 사용하며 공개 채널이나 저장소에 올리지 않습니다.\n") % (url, code, days)
            write_private(directory / ("member-%03d.txt" % index), text.encode("utf-8"))
        result = {"members": count, "invites": count, "created_at": stamp(), "expires_in_days": days}
        write_private(directory / "manifest.json", (packed(result) + "\n").encode("utf-8"))
    return result


def export(path, destination, include_answers=False):
    path = private_path(path)
    read_key(path)
    if inside(destination, REPOSITORY) or inside(destination, str(path.parent)):
        raise ValueError("공개 저장소와 서버 데이터 폴더 밖의 새 파일을 골라 주세요.")
    if os.path.lexists(destination):
        raise ValueError("이미 있는 파일입니다. 다른 이름을 골라 주세요.")
    fd, temp = tempfile.mkstemp(prefix=".dataset-", dir=os.path.dirname(os.path.abspath(destination)))
    try:
        expected, count = hashlib.sha256(), 0
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output, read_database(path) as db:
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


def snapshot_state(path):
    result = status(path)
    result.pop("available_invites")
    return result


def backup(path, destination):
    path = private_path(path)
    key = read_key(path)
    with new_directory(destination, path.parent) as directory:
        target = directory / BACKUP_FILES[0]
        write_private(target, b"")
        with read_database(path) as source, contextlib.closing(sqlite3.connect(target)) as saved:
            source.backup(saved)
            saved.execute("PRAGMA journal_mode=DELETE")
        if read_key(path) != key:
            raise ValueError("백업 중 인증 키가 바뀌었습니다. 다시 백업해 주세요.")
        write_private(directory / BACKUP_FILES[1], key)
        result = {"format": 1, "created_at": stamp(), "state": snapshot_state(target),
                  "files": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                            for name in BACKUP_FILES}}
        write_private(directory / "manifest.json", (packed(result) + "\n").encode("utf-8"))
        verify_backup(directory)
    return result


def verify_backup(directory):
    directory = private_path(directory)
    result = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("format") != 1 or not isinstance(result.get("files"), dict):
        raise ValueError("백업 목록의 형식을 확인해 주세요.")
    if set(result["files"]) != set(BACKUP_FILES):
        raise ValueError("데이터베이스와 인증 키를 함께 지정해 주세요.")
    for name in BACKUP_FILES:
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != result["files"][name]:
            raise ValueError("백업 파일의 SHA-256이 목록과 다릅니다.")
    if snapshot_state(directory / BACKUP_FILES[0]) != result.get("state"):
        raise ValueError("백업의 등록·기록 건수가 목록과 다릅니다.")
    return result


def restore(source, destination):
    source = private_path(source)
    result = verify_backup(source)
    with new_directory(destination, source) as directory:
        for name in BACKUP_FILES:
            value = (source / name).read_bytes()
            if hashlib.sha256(value).hexdigest() != result["files"][name]:
                raise ValueError("복구 중 백업 파일이 바뀌었습니다. 다시 확인해 주세요.")
            write_private(directory / name, value)
        if snapshot_state(directory / BACKUP_FILES[0]) != result["state"]:
            raise ValueError("복구한 데이터베이스의 상태를 확인하지 못했습니다.")
    return result["state"]
