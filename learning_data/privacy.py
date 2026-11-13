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

POLICY_VERSION = "2026-11-13-v3"
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
    ("비공개 서버 보관", "PythonAnywhere LLP의 비공개 서버에 기록을 보관하며 스터디 운영자가 모델 실습 자료를 준비합니다. 전송 항목·목적·보관 기간은 위 내용과 같습니다. 호스팅 문의: support@pythonanywhere.com."),
    ("선택·철회", "동의를 거부하거나 [내 정보·데이터]에서 철회할 수 있습니다. 문제 학습·로컬 채점은 계속 사용할 수 있습니다. 연결이 끊긴 상태의 서버 삭제는 다시 연결되면 처리합니다."),
    ("풀이 파일 제출", "[풀이 제출]에서 확인하고 보낸 답안 파일·채점·진도는 같은 목적과 기간으로 비공개 서버에 저장합니다. 자동 전송에서는 답안 본문을 제외하며 파일 제출은 직접 선택합니다. 새 풀이와 학습현황을 GitHub에 공개하지 않습니다. 이미 공개한 Git 이력은 유지합니다."),
    ("전달 사본", "이미 연구용으로 전달한 사본·백업의 삭제는 운영자가 철회 기록과 대조해 처리합니다. 관련 문의는 위 이메일로 보내 주세요."),
    ("철회 처리 기록", "삭제한 학습 기록이 다시 전송되지 않도록 인증 폐기 상태와 처리 시각만 남깁니다. 이 정보는 모델 학습 자료로 사용하지 않습니다."),
)
POLICY_HASH = hashlib.sha256(json.dumps(NOTICE_ROWS, ensure_ascii=False).encode()).hexdigest()
SUPPORTED_POLICIES = {POLICY_VERSION: POLICY_HASH, "2026-11-12-v2": '6016ed9fd12583db1dc36efd1984e8781697da85b38680fb845718b912d4557e'}
AUTO_VERSION = "2026-11-13-auto-v1"
AUTO_NOTICE = "동의하면 문제 묶음을 채점한 뒤 답안 파일·채점 결과·진도를 비공개 서버에 자동 제출합니다. 프로그램을 시작할 때도 미제출 풀이를 보냅니다. 업데이트 전이나 이 선택 전에 작성한 풀이 파일도 포함됩니다. 사용 목적·보관 기간·철회 방법은 기존 학습 데이터 동의와 같습니다. 끄면 새 자동 제출을 멈추고 기록 자동 전송과 수동 제출은 계속 사용할 수 있습니다."
AUTO_HASH = hashlib.sha256(AUTO_NOTICE.encode("utf-8")).hexdigest()
CONSENT_LOCKS = {}


def known_policy(value):
    return (isinstance(value, dict) and isinstance(value.get("policy"), str) and value["policy"] in SUPPORTED_POLICIES
            and value.get("policy_hash") == SUPPORTED_POLICIES[value["policy"]])


def receipt():
    return {"policy": POLICY_VERSION, "policy_hash": POLICY_HASH, "accepted": True,
            "overseas": True, "at": datetime.datetime.now().astimezone().isoformat()}


def validate_receipt(value, *, automatic=False):
    if not known_policy(value):
        raise ValueError("현재 동의서의 내용을 확인하고 선택해 주세요.")
    if value.get("accepted") is not True or value.get("overseas") is not True:
        raise ValueError("수집·이용과 비공개 서버 보관에 동의한 기록이 필요합니다.")
    if not isinstance(value.get("at"), str) or len(value["at"]) > 80:
        raise ValueError("동의 시각을 확인해 주세요.")
    instant = datetime.datetime.fromisoformat(value["at"])
    if instant.tzinfo is None:
        raise ValueError("동의 시각의 시간대를 확인해 주세요.")
    result = {key: value[key] for key in ("policy", "policy_hash", "accepted", "overseas", "at")}
    scope = value.get("automatic_submission")
    if scope is not None:
        if (not isinstance(scope, dict) or scope.get("version") != AUTO_VERSION or scope.get("hash") != AUTO_HASH
                or type(scope.get("accepted")) is not bool or not isinstance(scope.get("at"), str)
                or len(scope["at"]) > 80 or not isinstance(scope.get("choice"), str)):
            raise ValueError("자동 제출 안내의 선택 기록을 확인해 주세요.")
        if datetime.datetime.fromisoformat(scope["at"]).tzinfo is None:
            raise ValueError("자동 제출 선택 시각의 시간대를 확인해 주세요.")
        uuid.UUID(scope["choice"])
        result["automatic_submission"] = {key: scope[key] for key in ("version", "hash", "accepted", "at", "choice")}
    if automatic and (scope is None or scope["accepted"] is not True):
        raise ValueError("답안 파일 자동 제출을 선택한 기록이 필요합니다.")
    return result


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
        self.lock = CONSENT_LOCKS.setdefault(os.path.normcase(os.path.realpath(self.path)), threading.RLock())

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
        from learning_data.collection import CollectionError, inside
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
        return not known_policy(value)

    def has_private_records(self):
        from learning_data.sharing import Sharing
        return (any(Path(store.path).exists() or Path(Sharing(store).path).exists() for store in self.collections.values()) or
                any(self.path.with_name(name).exists() for name in ("private-submission.json", "submission-api.json")))

    def choose(self, accepted):
        from learning_data.collection import CollectionError
        with self.lock:
            old = self.settings()
            if old.get("withdraw_pending"):
                raise CollectionError("서버의 철회 처리를 마친 뒤 다시 동의할 수 있습니다.")
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

    def needs_auto_choice(self):
        value = self.settings()
        if self.needs_choice() or not value.get("accepted") or value.get("withdraw_pending"):
            return False
        try:
            result = validate_receipt(value.get("receipt"))
            return "automatic_submission" not in result
        except ValueError:
            return True

    def set_auto_submission(self, enabled):
        from learning_data.collection import CollectionError
        with self.lock:
            value = self.settings()
            if self.needs_choice() or not value.get("accepted") or value.get("withdraw_pending"):
                raise CollectionError("학습 데이터 제공에 동의한 뒤 자동 제출을 선택해 주세요.")
            try:
                current = validate_receipt(value.get("receipt"))
            except ValueError as error:
                raise CollectionError(str(error)) from error
            scope = current.get("automatic_submission")
            if scope is not None and scope["accepted"] is bool(enabled):
                return value
            current["automatic_submission"] = {"version": AUTO_VERSION, "hash": AUTO_HASH, "accepted": bool(enabled),
                                                "at": datetime.datetime.now().astimezone().isoformat(), "choice": str(uuid.uuid4())}
            value.update(receipt=current, choice=str(uuid.uuid4()))
            save(self.path, value)
            return value

    def withdraw(self):
        with self.lock:
            value = self.settings()
            if not known_policy(value):
                value.update(policy=POLICY_VERSION, policy_hash=POLICY_HASH)
            value.update(accepted=False, choice=str(uuid.uuid4()),
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
        for name in ("private-submission-pending.json", "submission-pending.json"):
            try:
                self.path.with_name(name).unlink(missing_ok=True)
            except OSError:
                errors.append("이 기기의 전송 대기 답안을 삭제하지 못했습니다. 다시 시도합니다.")
        return errors

    def synchronize(self, canceled=lambda: False):
        from learning_data.collection import CollectionError
        from learning_data.sharing import Sharing
        value = self.settings()
        errors, sent = [], 0
        if value.get("withdraw_pending"):
            errors.extend(self._delete_local())
            errors.extend(self._delete_submissions())
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

    def _delete_submissions(self):
        from learning_data.collection import CollectionError
        from learning_data.sharing import request
        errors = []
        for name in ("private-submission.json", "submission-api.json"):
            path = self.path.with_name(name)
            try:
                if not path.exists():
                    continue
                config = json.loads(path.read_text(encoding="utf-8"))
                if config.get("token"):
                    confirmed = request(config["url"], "/v1/me", token=config["token"], method="DELETE")
                elif name == "private-submission.json" and config.get("enroll_sent"):
                    confirmed = request(config["url"], "/v1/withdraw/private", {"participant": config["participant"], "registration_secret": config["registration_secret"]})
                else:
                    confirmed = {"deleted": True}
                if confirmed.get("deleted") is not True:
                    raise CollectionError("서버 삭제를 확인하지 못했습니다.")
                path.unlink()
            except (CollectionError, OSError, ValueError, KeyError, TypeError):
                errors.append("제출한 기록의 삭제를 확인하지 못했습니다. 문의: " + CONTACT)
        return errors
