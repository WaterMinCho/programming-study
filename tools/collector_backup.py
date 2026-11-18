# -*- coding: utf-8 -*-
"""전용 콘솔에서 만든 백업 사본을 운영자 맥으로 내려받고 해시와 무결성을 확인함.

콘솔이 꺼져 있어 API 가 412 를 돌려줄 때만 파일 API 로 운영 DB 를 직접 받아 맥에서 백업 사본을 만듦.
실패·오래됨·용량 경고는 state.json 과 출력 줄에 남기고 맥 알림센터에 띄움.
"""
import argparse
import base64
import contextlib
import datetime
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

from learning_server import operations

STALE = 12 * 3600
REPEAT = 24 * 3600
KST = datetime.timezone(datetime.timedelta(hours=9))
DB_LIMIT = 256 * 1024 * 1024
TITLE = "수집 서버 백업"
MESSAGES = {
    "stale": "마지막 백업 사본이 만들어진 지 12시간이 넘었습니다.",
    "console_unavailable": ("전용 콘솔이 꺼져 있어 파일을 직접 받아 백업했습니다. "
                            "서버 용량을 재고 이전 자동 사본을 정리하려면 콘솔을 다시 열어 주세요."),
    "capacity": "서버 용량 경고가 있습니다.",
}
START_FAILED = "수집 서버 백업을 시작하지 못했습니다. 정기 실행 로그의 마지막 줄을 확인해 주세요."


class ApiError(ValueError):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


class BackupError(ValueError):
    """문구와 함께 실패한 단계 이름과 HTTP 코드를 담음. 출력 줄에는 문구 없이 단계 이름과 HTTP 코드만 찍음."""
    def __init__(self, message, stage, http=None):
        super().__init__(message)
        self.stage = stage
        self.http = http


# 받은 파일이 SQLite 로 읽히지 않을 때의 sqlite3.Error 도 실패로 기록함.
FAILURES = (OSError, ValueError, KeyError, TypeError, sqlite3.Error)


@contextlib.contextmanager
def step(name):
    try:
        yield
    except BackupError:
        raise
    except ApiError as error:
        raise BackupError(str(error), name, error.status) from None
    except FAILURES as error:
        raise BackupError(str(error), name) from None


def save(path, value):
    raw = json.dumps(value).encode()
    descriptor, temporary = tempfile.mkstemp(prefix=".backup-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        if path.read_bytes() != raw:
            raise ValueError("백업 작업 상태를 다시 읽어 확인하지 못했습니다.")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration(path):
    path = operations.private_path(path)
    config = json.loads(path.read_bytes())
    token_path = operations.private_path(config["token_file"])
    for private in (path, token_path):
        if os.name != "nt" and private.stat().st_mode & 0o077:
            raise ValueError("운영 설정과 인증 파일은 본인만 읽을 수 있게 보관해 주세요.")
    if config["host"] not in ("www.pythonanywhere.com", "eu.pythonanywhere.com"):
        raise ValueError("공식 호스팅 API 주소를 확인해 주세요.")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", config["username"]) or type(config["console"]) is not int or config["console"] < 1:
        raise ValueError("계정과 전용 콘솔 번호를 확인해 주세요.")
    home = PurePosixPath("/home") / config["username"]
    for name in ("repo", "db", "remote_root"):
        value = PurePosixPath(config[name])
        if not value.is_relative_to(home) or ".." in value.parts or value == home:
            raise ValueError("운영 경로는 해당 계정의 홈 아래로 지정해 주세요.")
    if PurePosixPath(config["remote_root"]).is_relative_to(PurePosixPath(config["db"]).parent):
        raise ValueError("자동 백업은 별도 운영 폴더에 보관해 주세요.")
    for name in ("db", "remote_root"):
        if PurePosixPath(config[name]).is_relative_to(PurePosixPath(config["repo"])):
            raise ValueError("운영 자료는 공개 저장소 밖에 보관해 주세요.")
    token = token_path.read_text().strip()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{16,256}", token):
        raise ValueError("호스팅 API 인증 파일을 확인해 주세요.")
    config["destination"] = str(operations.private_path(config["destination"]))
    return config, token


class Api:
    def __init__(self, config, token):
        self.base = "https://%s/api/v0/user/%s" % (config["host"], config["username"])
        self.token = token
        self.opener = build_opener(NoRedirect())

    def call(self, path, data=None, maximum=1024*1024):
        payload = urlencode(data).encode() if data is not None else None
        req = Request(self.base + path, data=payload, headers={"Authorization": "Token " + self.token})
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(maximum + 1)
        except HTTPError as error:
            if error.code == 404 and path.startswith("/files/path"):
                return None
            raise ApiError("호스팅 API 요청에 실패했습니다. 인증·연결·요청 제한을 확인해 주세요.", error.code) from None
        except http.client.HTTPException:
            raise ApiError("호스팅 API 응답을 끝까지 받지 못했습니다.", None) from None
        if len(raw) > maximum:
            raise ValueError("백업 응답이 허용한 크기를 넘었습니다.")
        return raw

    def file(self, path, maximum=1024*1024):
        return self.call("/files/path" + quote(path, safe="/"), maximum=maximum)


def command(config, identity, previous=None):
    """자기 작업 UUID와 확인된 이전 백업만 처리하는 고정 명령을 만듦."""
    if str(uuid.UUID(identity)) != identity or (previous and str(uuid.UUID(previous)) != previous):
        raise ValueError("백업 작업 번호를 확인해 주세요.")
    values = json.dumps({key: config[key] for key in ("repo", "db", "remote_root", "username")})
    code = '''import json,os,sys,uuid,shutil,tempfile
from pathlib import Path
c=json.loads(%r);identity=%r;previous=%r
os.umask(0o077);sys.path.insert(0,c['repo'])
from learning_server import operations
from learning_server.capacity import report
root=Path(c['remote_root']);root.mkdir(parents=True,exist_ok=True)
target=root/identity
if not target.exists():
 staging=root/(identity+'.pending')
 if staging.exists():
  if staging.is_symlink():raise ValueError('Unexpected backup path')
  shutil.rmtree(staging)
 operations.backup(c['db'],staging)
 operations.verify_backup(staging)
 staging.rename(target)
operations.verify_backup(target)
if previous and previous!=identity:
 old=root/previous
 marker=old/'checkpoint.json'
 if marker.is_file():
  saved=json.loads(marker.read_bytes())
  if saved.get('purpose')=='offsite_checkpoint' and saved.get('identity')==previous and not old.is_symlink():
   for p in old.glob('.checkpoint-*'):
    if p.is_file() and not p.is_symlink():p.unlink()
   if {p.name for p in old.iterdir()}=={'learning.sqlite3','learning.sqlite3.key','manifest.json','checkpoint.json'}:
    for p in old.iterdir():p.unlink()
    old.rmdir()
result={'purpose':'offsite_checkpoint','identity':identity,'capacity':report(c['db'],Path('/home')/c['username'],512)}
fd,temp=tempfile.mkstemp(prefix='.checkpoint-',dir=target)
try:
 with os.fdopen(fd,'wb') as output:
  output.write((json.dumps(result)+'\\n').encode());output.flush();os.fsync(output.fileno())
 os.replace(temp,target/'checkpoint.json')
finally:
 if os.path.exists(temp):os.unlink(temp)
''' % (values, identity, previous)
    encoded = base64.b64encode(code.encode()).decode()
    return "python3.12 -c " + shlex.quote("import base64;exec(base64.b64decode(%r))" % encoded) + "\n"


def trusted(root, identity):
    """맥에 검증된 사본이 있는 작업 번호만 돌려줌. 없으면 None 을 돌려줘 서버 정리를 하지 않게 함."""
    if not identity:
        return None
    try:
        if str(uuid.UUID(identity)) != identity:
            raise ValueError("백업 작업 번호가 다릅니다.")
        operations.verify_backup(root / identity)
    except FAILURES:
        return None
    return identity


def remove_folder(path):
    if path.is_symlink():
        raise ValueError("백업 임시 경로를 확인해 주세요.")
    if path.exists():
        shutil.rmtree(path)


def direct_copy(config, api, root, identity, *, tries=3, pause=time.sleep):
    """콘솔 없이 운영 DB 파일을 받아 맥에서 SQLite 백업 API 로 다시 복사함.

    저널이 없을 때 DB 를 두 번 받아 해시가 같고 키가 앞뒤로 같을 때만 씀. 서버 용량은 재지 않음.
    """
    db = config["db"]
    last = "direct_unstable"
    for index in range(tries):
        if index:
            pause(5)
        with step("download"):
            wal = api.file(db + "-wal", maximum=DB_LIMIT)
        if wal is not None:
            raise BackupError("운영 DB 가 WAL 모드라 직접 받지 않습니다.", "direct_wal")
        with step("download"):
            if api.file(db + "-journal", maximum=DB_LIMIT) is not None:
                last = "direct_busy"
                continue
            key = api.file(db + ".key", maximum=4096)
            first = api.file(db, maximum=DB_LIMIT)
            second = api.file(db, maximum=DB_LIMIT)
            if key is None or first is None or second is None:
                raise BackupError("운영 DB 나 인증 키를 받지 못했습니다.", "download")
            if hashlib.sha256(first).digest() != hashlib.sha256(second).digest():
                last = "direct_unstable"
                continue
            if api.file(db + "-journal", maximum=DB_LIMIT) is not None:
                last = "direct_busy"
                continue
            if api.file(db + ".key", maximum=4096) != key:
                raise BackupError("받는 동안 인증 키가 바뀌었습니다.", "direct_key")
        break
    else:
        raise BackupError("운영 DB 를 세 번 받아 보는 동안 계속 쓰는 중이었거나 내용이 바뀌었습니다.", last)
    checkpoint = {"purpose": "offsite_checkpoint", "identity": identity, "path": "files",
                  "capacity": {"status": "unknown", "warnings": ["capacity_unchecked"]}}
    source = root / (identity + ".direct")
    staging = root / (identity + ".pending")
    target = root / identity
    try:
        with step("verify"):
            if not target.exists():
                remove_folder(source)
                remove_folder(staging)
                source.mkdir(mode=0o700)
                operations.write_private(source / "learning.sqlite3", first)
                operations.write_private(source / "learning.sqlite3.key", key)
                operations.backup(source / "learning.sqlite3", staging)
                try:
                    operations.write_private(staging / "checkpoint.json", json.dumps(checkpoint).encode())
                    operations.verify_backup(staging)
                    staging.rename(target)
                except BaseException:
                    shutil.rmtree(staging, ignore_errors=True)
                    raise
    finally:
        if source.exists() and not source.is_symlink():
            shutil.rmtree(source, ignore_errors=True)
    return checkpoint


def console_copy(config, api, root, identity, previous, *, polls, pause):
    remote = str(PurePosixPath(config["remote_root"]) / identity)
    ready = None
    with step("poll"):
        for index in range(polls):
            if index:
                pause(5)
            ready = api.file(remote + "/checkpoint.json")
            if ready is not None:
                break
        if ready is None:
            raise ValueError("백업 완료를 확인하지 못했습니다. 전용 콘솔을 확인해 주세요. 같은 작업 번호로 다시 확인합니다.")
        checkpoint = json.loads(ready)
        if checkpoint.get("identity") != identity or checkpoint.get("purpose") != "offsite_checkpoint":
            raise ValueError("백업 완료 표식의 작업 번호가 다릅니다.")
    target = root / identity
    if not target.exists():
        staging = root / (identity + ".pending")
        remove_folder(staging)
        with operations.new_directory(staging) as folder:
            with step("download"):
                for name, maximum in (("manifest.json", 1024*1024), ("learning.sqlite3", DB_LIMIT), ("learning.sqlite3.key", 4096)):
                    raw = api.file(remote + "/" + name, maximum=maximum)
                    if raw is None:
                        raise ValueError("백업 구성 파일이 없습니다.")
                    operations.write_private(folder / name, raw)
            with step("verify"):
                operations.write_private(folder / "checkpoint.json", ready)
                operations.verify_backup(folder)
            folder.rename(target)
    return checkpoint


def copy(config, api, root, state, state_path, *, polls, pause):
    """콘솔 백업을 먼저 쓰고 send_input 이 412 일 때만 직접 받기로 넘어감.

    앞 실행에서 남은 pending 은 콘솔에 이미 보냈을 수 있어 직접 받기에 쓰지 않음.
    직접 받기는 새 번호로 만들고 pending 은 남겨 다음 콘솔 백업이 서버의 같은 번호를 이어받게 함.
    """
    reused = state.get("pending")
    identity = reused or str(uuid.uuid4())
    state["pending"] = identity
    state.setdefault("remote_latest", state.get("latest"))
    save(state_path, state)
    previous = trusted(root, state.get("remote_latest"))
    try:
        api.call("/consoles/%d/send_input/" % config["console"], {"input": command(config, identity, previous)})
    except ApiError as error:
        if error.status != 412:
            raise BackupError(str(error), "send_input", error.status) from None
        if reused:
            identity = str(uuid.uuid4())
        return "files", identity, direct_copy(config, api, root, identity, pause=pause)
    except OSError as error:
        raise BackupError(str(error), "send_input") from None
    return "console", identity, console_copy(config, api, root, identity, previous, polls=polls, pause=pause)


def problems(state, now, path=None):
    kinds = []
    created = state.get("backup_created_at")
    if created and (now - datetime.datetime.fromisoformat(created)).total_seconds() > STALE:
        kinds.append("stale")
    if state.get("consecutive_failures", 0) >= 2:
        kinds.append("failed")
    if path == "files":
        kinds.append("console_unavailable")
    if (state.get("capacity") or {}).get("status") == "warning":
        kinds.append("capacity")
    return kinds


def notify(title, text):
    """문구는 osascript 의 argv 로만 넘겨 스크립트 문자열에 섞이지 않게 함."""
    result = subprocess.run(["osascript", "-e", "on run argv",
                             "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                             "-e", "end run", title, text],
                            timeout=10, check=False, capture_output=True)
    return result.returncode == 0


def message(state, kinds):
    if not kinds:
        return "수집 서버 백업이 다시 정상입니다."
    lines = []
    for kind in kinds:
        if kind == "failed":
            text = "수집 서버 백업이 %d번 연속 실패했습니다." % state["consecutive_failures"]
            if state.get("checked_at"):
                last = datetime.datetime.fromisoformat(state["checked_at"]).astimezone(KST)
                text += " 마지막 성공은 %d월 %d일 %s입니다." % (last.month, last.day, last.strftime("%H:%M"))
            lines.append(text)
        else:
            lines.append(MESSAGES[kind])
    return " ".join(lines)


def alert_step(state, kinds, now, send, succeeded=True):
    """문제 목록이 바뀌면 알리고, 같으면 24시간 뒤 다시 알림. 알림이 실패하면 기록을 바꾸지 않음.

    정상 복귀 알림은 성공한 실행에서만 보냄. 보낸 시각을 읽지 못하면 다시 알림.
    """
    alert = state.get("alert") or {}
    if not kinds and not succeeded:
        return
    if kinds == alert.get("kinds", []):
        if not kinds:
            return
        try:
            if (now - datetime.datetime.fromisoformat(alert["sent_at"])).total_seconds() < REPEAT:
                return
        except (KeyError, TypeError, ValueError):
            pass
    try:
        sent = send(TITLE, message(state, kinds))
    except (OSError, subprocess.SubprocessError):
        sent = False
    if sent:
        state["alert"] = {"kinds": kinds, "sent_at": now.isoformat()} if kinds else None


def run(config, api, *, polls=12, pause=time.sleep, notifier=None, now=None):
    root = Path(config["destination"])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path = root / "state.json"
    state = json.loads(state_path.read_bytes()) if state_path.exists() else {}
    for leftover in root.glob("*.direct"):
        remove_folder(leftover)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    state["last_attempt_at"] = now.isoformat()
    try:
        path, identity, checkpoint = copy(config, api, root, state, state_path, polls=polls, pause=pause)
        with step("verify"):
            manifest = operations.verify_backup(root / identity)
        checked = operations.stamp()
        if state.get("pending") == identity:
            state["pending"] = None
        state.update(latest=identity, checked_at=checked, backup_created_at=manifest["created_at"],
                     last_error=None, consecutive_failures=0)
        if path == "console":
            state.update(remote_latest=identity, capacity=checkpoint["capacity"], capacity_checked_at=checked)
        kinds = problems(state, now, path)
        state.update(status="warning" if kinds else "ok", problems=kinds)
        alert_step(state, kinds, now, notifier or notify)
        save(state_path, state)
    except FAILURES as error:
        state.update(last_error={"stage": getattr(error, "stage", "unknown"), "http": getattr(error, "http", None),
                                 "at": now.isoformat()},
                     consecutive_failures=state.get("consecutive_failures", 0) + 1)
        kinds = problems(state, now)
        state["problems"] = kinds
        alert_step(state, kinds, now, notifier or notify, succeeded=False)
        with contextlib.suppress(OSError, ValueError):
            save(state_path, state)
        error.problems = kinds
        raise
    return {"status": state["status"], "verified": True, "path": path, "checked_at": checked,
            "backup_created_at": state["backup_created_at"], "stale": "stale" in kinds,
            "capacity": state.get("capacity"), "problems": kinds}


def main():
    parser = argparse.ArgumentParser(description="운영자 전용 외부 백업입니다.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    phase = "config"
    try:
        import fcntl
        config, token = configuration(args.config)
        root = Path(config["destination"])
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        phase = "lock"
        with (root / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            phase = "unknown"
            result = run(config, Api(config, token))
        print(json.dumps(result))
        return 0 if result["status"] == "ok" else 2
    except FAILURES as error:
        if not hasattr(error, "problems") and phase != "lock":
            # run 이 실패를 기록하기 전에 멈추면 state 가 없어 중복 막기 없이 알림. 다른 실행이 잠금을 쥔 경우는 알리지 않음.
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                notify(TITLE, START_FAILED)
        print(json.dumps({"status": "error", "code": "offsite_backup_failed", "stage": getattr(error, "stage", phase),
                          "http": getattr(error, "http", None),
                          "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                          "problems": getattr(error, "problems", [])}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
