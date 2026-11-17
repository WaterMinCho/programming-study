"""본인 확인을 마친 계정이 오늘 채점했는지만 따로 전송함. 학습 기록 제공 동의와는 별개임."""
import datetime
import hashlib
import json
import os
import re
import threading

from learning_data.collection import CollectionError
from learning_data.privacy import DEFAULT_SERVER, save
from learning_data.sharing import request

KST = datetime.timezone(datetime.timedelta(hours=9))
VERSION = "2026-11-17-v2"
LOCKS = {}
NOTICE = ("본인 확인을 마친 계정으로 오늘 문제를 채점하면 '오늘 열심히 공부한 계정' 수에 한 번 들어갑니다. "
          "서버에는 어느 계정인지 구별하는 값과 날짜만 보내며, 지난 날짜의 값은 다음 집계 때 지웁니다. "
          "어떤 문제를 풀었는지와 답은 보내지 않습니다.")


def today():
    return datetime.datetime.now(KST).date().isoformat()


class DailyStudy:
    def __init__(self, identity):
        self.identity = identity
        self.path = identity.path.with_name("daily-study.json")
        self.lock = LOCKS.setdefault(os.path.normcase(os.path.realpath(self.path)), threading.RLock())

    def fingerprint(self):
        token = self.identity.settings().get("token")
        return hashlib.sha256(token.encode()).hexdigest() if token else None

    def _load(self):
        """이 버전의 기록만 읽음. 파일이 없거나 깨졌거나 이전 버전이면 None."""
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (isinstance(value, dict) and value.get("version") == VERSION and isinstance(value.get("date"), str)
                    and all(isinstance(value.get(key), list)
                            and all(isinstance(row, str) and re.fullmatch(r"[a-f0-9]{64}", row) for row in value[key])
                            for key in ("graded", "sent"))):
                return value
        except (OSError, ValueError):
            pass
        return None

    def _state(self, day):
        value = self._load()
        if value is None or value["date"] != day:
            return {"version": VERSION, "date": day, "graded": [], "sent": []}
        return value

    def mark(self):
        """채점한 계정의 지문을 오늘 날짜로 남김. 그날 처음 남겼을 때만 True."""
        fingerprint = self.fingerprint()
        if not fingerprint:
            return False
        with self.lock:
            state = self._state(today())
            if fingerprint in state["graded"]:
                return False
            state["graded"].append(fingerprint)
            save(self.path, state)
        return True

    def due(self):
        if self.identity.base != DEFAULT_SERVER:
            return False
        fingerprint = self.fingerprint()
        with self.lock:
            state = self._state(today())
        return bool(fingerprint) and fingerprint in state["graded"] and fingerprint not in state["sent"]

    def synchronize(self, canceled=lambda: False):
        if self.identity.base != DEFAULT_SERVER or canceled():
            return
        day = today()
        token = self.identity.settings().get("token")
        if not token:
            return
        fingerprint = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            if os.path.exists(self.path) and self._load() is None:
                # 이전 버전의 선택·삭제 대기 기록은 보내지 않고 지움.
                save(self.path, self._state(day))
            state = self._state(day)
        if fingerprint not in state["graded"] or fingerprint in state["sent"]:
            return
        data = {"date": day, "accepted": True}
        try:
            nonce = json.loads(self.identity.path.with_name("identity-device.json").read_text(encoding="utf-8")).get("nonce")
            if isinstance(nonce, str) and re.fullmatch(r"[a-f0-9]{64}", nonce):
                data["nonce"] = nonce
        except (OSError, ValueError, AttributeError):
            pass
        if canceled():
            return
        result = request(self.identity.base, "/v1/identity/study-activity", data, token=token,
                         method="POST", error_detail=True)
        # 서버가 셀 수 없는 계정이라고 답한 날도 보낸 것으로 적어 그날 다시 보내지 않음.
        if result.get("eligible") is True and result.get("date") != day:
            raise CollectionError("오늘 계정 집계 응답을 확인하지 못했습니다.")
        with self.lock:
            latest = self._load()
            if latest is None or latest["date"] != day or fingerprint in latest["sent"]:
                return
            latest["sent"].append(fingerprint)
            save(self.path, latest)
