# -*- coding: utf-8 -*-
"""운영자 맥에서 전용 콘솔의 일관된 백업을 내려받고 해시·복구 상태를 확인함."""
import argparse
import base64
import datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

from learning_server import operations


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
            raise ValueError("호스팅 API 요청에 실패했습니다. 인증·연결·요청 제한을 확인해 주세요.") from None
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


def run(config, api, *, polls=12, pause=time.sleep):
    root = Path(config["destination"])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path = root / "state.json"
    state = json.loads(state_path.read_bytes()) if state_path.exists() else {}
    identity = state.get("pending") or str(uuid.uuid4())
    state["pending"] = identity
    save(state_path, state)
    remote = str(PurePosixPath(config["remote_root"]) / identity)
    previous = state.get("latest")
    if previous:
        try:
            if str(uuid.UUID(previous)) != previous:
                raise ValueError("백업 작업 번호가 다릅니다.")
            operations.verify_backup(root / previous)
        except (OSError, ValueError, KeyError, TypeError):
            previous = None
    api.call("/consoles/%d/send_input/" % config["console"], {"input": command(config, identity, previous)})
    ready = None
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
        if staging.exists():
            if staging.is_symlink():
                raise ValueError("백업 임시 경로를 확인해 주세요.")
            shutil.rmtree(staging)
        with operations.new_directory(staging) as folder:
            for name, maximum in (("manifest.json", 1024*1024), ("learning.sqlite3", 256*1024*1024), ("learning.sqlite3.key", 4096)):
                raw = api.file(remote + "/" + name, maximum=maximum)
                if raw is None:
                    raise ValueError("백업 구성 파일이 없습니다.")
                operations.write_private(folder / name, raw)
            operations.write_private(folder / "checkpoint.json", ready)
            operations.verify_backup(folder)
            folder.rename(target)
    manifest = operations.verify_backup(target)
    age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(manifest["created_at"])).total_seconds()
    state.update(pending=None, latest=identity, checked_at=operations.stamp(),
                 backup_created_at=manifest["created_at"],
                 status="warning" if age > 8*3600 else checkpoint["capacity"]["status"], capacity=checkpoint["capacity"])
    save(state_path, state)
    return {"status": state["status"], "verified": True, "checked_at": state["checked_at"],
            "backup_created_at": state["backup_created_at"], "stale": age > 8*3600, "capacity": state["capacity"]}


def main():
    parser = argparse.ArgumentParser(description="운영자 전용 외부 백업입니다.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    try:
        import fcntl
        config, token = configuration(args.config)
        root = Path(config["destination"])
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (root / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = run(config, Api(config, token))
        print(json.dumps(result))
        return 0 if result["status"] == "ok" else 2
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"status": "error", "code": "offsite_backup_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
