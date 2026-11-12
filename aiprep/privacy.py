# -*- coding: utf-8 -*-
"""동의 내용과 선택을 보관하고 동의한 과목만 비공개로 전송함."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import uuid

POLICY_VERSION = "2026-11-12-v1"
DEFAULT_SERVER = "https://whalstn9.pythonanywhere.com"
CONTACT = "whalstn9@gmail.com"
RETENTION = "수집일부터 동의 철회 전까지"
NOTICE_ROWS = (
    ("운영자·문의", "조민수 · " + CONTACT),
    ("사용 목적", "파이썬·AI 개론·응용의 문제 추천 모델 개발과 선택한 희망 직무별 풀이 경향 연구에 사용합니다."),
    ("전송 항목", "기기별 임의 번호, 푼 문제·개념·문제 버전, 정오답, 풀이 순서·시각·응답 시간, 확신 여부, 선택한 희망 직무와 당시 로드맵 버전, 동의서 버전·선택 시각입니다."),
    ("이 기기의 추가 보관", "동의 뒤 프로그램에서 입력·변경한 답안과 채점 과정을 추가 기록으로 보관합니다. 자동 전송에서는 답안 본문을 제외합니다. 기존 학습의 풀이·진도 파일과는 별도입니다."),
    ("제외 항목", "직접 입력한 답안 본문, 이름·이메일·GitHub 로그인 정보는 자동 전송하지 않습니다. 희망 직무는 고르지 않아도 됩니다."),
    ("보관 기간", RETENTION + " 보관합니다. 철회하면 자동 수집·전송을 멈추고 이 기기의 추가 기록과 서버의 비공개 기록을 삭제합니다."),
    ("전송 방법", "동의 후 새로 수집한 기록을 HTTPS로 자동 전송합니다. 오프라인에서는 이 기기에 보관했다가 다시 연결되면 보냅니다. 과거 풀이를 자동으로 가져오지 않습니다."),
    ("국외 보관", "PythonAnywhere LLP의 미국 서버에 기록을 보관하며 스터디 운영자가 모델 실습 자료를 준비합니다. 전송 항목·목적·보관 기간은 위 내용과 같습니다. 호스팅 문의: support@pythonanywhere.com."),
    ("선택·철회", "동의를 거부하거나 [내 정보·데이터]에서 철회할 수 있습니다. 문제 학습·로컬 채점은 계속 사용할 수 있습니다. 연결이 끊긴 상태의 서버 삭제는 다시 연결되면 처리합니다."),
    ("공개 풀이 제출", "GitHub 공개 풀이 제출은 자동 전송과 별도입니다. 공개할 파일을 확인하고 [풀이 제출]을 눌렀을 때만 게시합니다. 이미 공개한 Git 이력은 비공개 수집 동의 철회로 삭제되지 않습니다."),
    ("전달 사본", "이미 연구용으로 전달한 사본·백업의 삭제는 운영자가 철회 기록과 대조해 처리합니다. 관련 문의는 위 이메일로 보내 주세요."),
    ("철회 처리 기록", "삭제한 학습 기록이 다시 전송되지 않도록 인증 폐기 상태와 처리 시각만 남깁니다. 이 정보는 모델 학습 자료로 사용하지 않습니다."),
)
POLICY_HASH = hashlib.sha256(json.dumps(NOTICE_ROWS, ensure_ascii=False).encode()).hexdigest()


def receipt():
    return {"policy": POLICY_VERSION, "policy_hash": POLICY_HASH, "accepted": True,
            "overseas": True, "at": datetime.datetime.now().astimezone().isoformat()}


def validate_receipt(value):
    if not isinstance(value, dict) or value.get("policy") != POLICY_VERSION or value.get("policy_hash") != POLICY_HASH:
        raise ValueError("현재 동의서의 내용을 확인하고 선택해 주세요.")
    if value.get("accepted") is not True or value.get("overseas") is not True:
        raise ValueError("수집·이용과 미국 서버 보관에 동의한 기록이 필요합니다.")
    if not isinstance(value.get("at"), str) or len(value["at"]) > 80:
        raise ValueError("동의 시각을 확인해 주세요.")
    instant = datetime.datetime.fromisoformat(value["at"])
    if instant.tzinfo is None:
        raise ValueError("동의 시각의 시간대를 확인해 주세요.")
    return {key: value[key] for key in ("policy", "policy_hash", "accepted", "overseas", "at")}


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".privacy-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            json.dump(data, output, ensure_ascii=False, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Consent:
    def __init__(self, collections, server=DEFAULT_SERVER):
        self.collections, self.server = collections, server
        self.lock = threading.RLock()

    @property
    def path(self):
        return Path(self.collections["python"].path).with_name("learning-privacy.json")

    def _stop_all(self):
        errors = []
        for store in self.collections.values():
            try:
                store._remember_stop(True)
            except Exception as error:
                errors.append(str(error))
        return errors

    def settings(self):
        from aiprep.collection import CollectionError, inside
        if any(inside(self.path, store.repository) for store in self.collections.values()):
            raise CollectionError("동의 설정은 공개 저장소 밖에 보관해 주세요.")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            raise CollectionError("동의 설정을 읽지 못했습니다.") from None

    def needs_choice(self):
        value = self.settings()
        if value.get("withdraw_pending"):
            return False
        return value.get("policy") != POLICY_VERSION or value.get("policy_hash") != POLICY_HASH

    def choose(self, accepted):
        from aiprep.collection import CollectionError
        from aiprep.sharing import Sharing
        with self.lock:
            old = self.settings()
            if old.get("withdraw_pending"):
                raise CollectionError("서버의 철회 처리를 마친 뒤 다시 동의할 수 있습니다.")
            if not accepted and any(Sharing(store).settings() for store in self.collections.values()):
                return self.withdraw()
            value = {"policy": POLICY_VERSION, "policy_hash": POLICY_HASH, "accepted": bool(accepted), "choice": str(uuid.uuid4()),
                     "at": datetime.datetime.now().astimezone().isoformat(), "start": {}}
            self._stop_all()
            for track, store in self.collections.items():
                if accepted:
                    value["start"][track] = store.latest_sequence()
            if accepted:
                value["receipt"] = receipt()
            save(self.path, value)
            try:
                for store in self.collections.values():
                    store.set_enabled(bool(accepted), renew=bool(accepted), privacy_state=self.path if accepted else None)
            except Exception:
                value["accepted"] = False
                self._stop_all()
                save(self.path, value)
                raise
            return value

    def withdraw(self):
        with self.lock:
            value = self.settings()
            value.update(policy=POLICY_VERSION, accepted=False, choice=str(uuid.uuid4()),
                         withdrawn_at=datetime.datetime.now().astimezone().isoformat(), withdraw_pending=True)
            save(self.path, value)
            self._stop_all()
            self._delete_local()
            return value

    def _delete_local(self):
        errors = []
        self._stop_all()
        for store in self.collections.values():
            try:
                store.delete()
            except Exception as error:
                errors.append(str(error))
        return errors

    def synchronize(self, canceled=lambda: False):
        from aiprep.collection import CollectionError
        from aiprep.sharing import Sharing
        value = self.settings()
        errors, sent = [], 0
        if value.get("withdraw_pending"):
            errors.extend(self._delete_local())
            for store in self.collections.values():
                try:
                    share = Sharing(store)
                    if share.settings():
                        share.delete_remote()
                except CollectionError as error:
                    errors.append("서버 삭제를 확인하지 못했습니다. " + CONTACT + "로 문의해 주세요." if error.status == 401 else str(error))
            if not errors:
                with self.lock:
                    latest = self.settings()
                    if latest.get("choice") == value.get("choice"):
                        latest.update(withdraw_pending=False, remote_deleted_at=datetime.datetime.now().astimezone().isoformat())
                        save(self.path, latest)
            return {"sent": 0, "errors": errors, "withdrawn": not errors}
        if self.needs_choice() or not value.get("accepted"):
            return {"sent": 0, "errors": []}
        for track, store in self.collections.items():
            try:
                if canceled() or self.settings().get("choice") != value.get("choice"):
                    break
                if not store.status()["enabled"]:
                    continue
                share = Sharing(store)
                share.connect_open(self.server, value["receipt"], after=value["start"].get(track, 0))
                sent += share.sync(self.server, include_answers=False, canceled=canceled)["sent"]
            except CollectionError as error:
                if error.code == "revoked":
                    self.withdraw()
                    errors.append("서버에서 철회를 확인해 수집을 멈추고 삭제를 확인합니다.")
                    break
                errors.append(str(error))
        return {"sent": sent, "errors": errors}
