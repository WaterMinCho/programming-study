"""선택한 기기에서 당일 채점 여부만 따로 전송함."""
import datetime
import hashlib
import json
import os
import re
import threading
import uuid

from learning_data.collection import CollectionError
from learning_data.privacy import DEFAULT_SERVER, save
from learning_data.sharing import request

KST = datetime.timezone(datetime.timedelta(hours=9))
VERSION = "2026-11-16-v1"
LOCKS = {}
NOTICE = ("켜면 오늘 채점을 마친 계정 수에 포함됩니다. 계정 확인값과 한국 날짜만 따로 보관하며 "
          "문항·답안·연구 참가자 번호와 연결하지 않습니다. 지난 날짜의 값은 다음 집계 때 지웁니다. "
          "끄면 이 기기의 전송을 멈추고 오늘 집계에서 해당 계정을 삭제 요청합니다.")


class DailyStudy:
    def __init__(self, identity):
        self.identity = identity
        self.path = identity.path.with_name("daily-study.json")
        self.lock = LOCKS.setdefault(os.path.normcase(os.path.realpath(self.path)), threading.RLock())

    def fingerprint(self):
        token = self.identity.settings().get("token")
        return hashlib.sha256(token.encode()).hexdigest() if token else None

    def settings(self):
        with self.lock:
            value = self._settings()
            fingerprint = self.fingerprint()
            day = datetime.datetime.now(KST).date().isoformat()
            if value and value.get("identity") != fingerprint and {"identity": fingerprint, "date": day} in self._deletions(value):
                # 돌아온 계정의 삭제 재시도를 알리며 다른 계정의 저장된 선택은 유지함.
                return dict(value, identity=fingerprint, enabled=False, delete_pending=True)
            return value

    def _settings(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("version") != VERSION or type(value.get("enabled")) is not bool:
                raise ValueError()
            pending = value.get("unresolved_deletions", [])
            if not isinstance(pending, list):
                raise ValueError()
            for row in pending:
                if (not isinstance(row, dict) or set(row) != {"identity", "date"}
                        or not isinstance(row["identity"], str) or not re.fullmatch(r"[a-f0-9]{64}", row["identity"])
                        or datetime.date.fromisoformat(row["date"]).isoformat() != row["date"]):
                    raise ValueError()
            return value
        except FileNotFoundError:
            return {}
        except (OSError, TypeError, ValueError):
            raise CollectionError("오늘 학습 계정 집계 설정을 읽지 못했습니다.") from None

    @staticmethod
    def _deletions(state):
        pending = list(state.get("unresolved_deletions", []))
        if state.get("delete_pending"):
            try:
                day = state.get("delete_date")
                if day is None:
                    at = datetime.datetime.fromisoformat(state["at"])
                    if at.tzinfo is None:
                        raise ValueError()
                    day = at.astimezone(KST).date().isoformat()
                row = {"identity": state["identity"], "date": day}
            except (KeyError, TypeError, ValueError):
                raise CollectionError("오늘 계정 집계의 삭제 대기 기록을 확인해 주세요.") from None
            if row not in pending:
                pending.append(row)
        return pending

    def enabled(self):
        state = self.settings()
        return state.get("enabled") is True and state.get("identity") == self.fingerprint()

    def choose(self, enabled):
        with self.lock:
            fingerprint = self.fingerprint()
            if not fingerprint:
                raise CollectionError("본인 확인을 마친 뒤 선택해 주세요.")
            now = datetime.datetime.now(KST)
            pending = self._deletions(self._settings())
            row = {"identity": fingerprint, "date": now.date().isoformat()}
            if enabled and row in pending:
                raise CollectionError("이전 집계의 삭제를 확인한 뒤 다시 켤 수 있습니다.")
            if not enabled and row not in pending:
                pending.append(row)
            value = {"version": VERSION, "enabled": bool(enabled), "identity": fingerprint,
                     "choice": str(uuid.uuid4()), "at": now.isoformat(), "delete_pending": not enabled,
                     "unresolved_deletions": pending}
            if not enabled:
                value["delete_date"] = row["date"]
            save(self.path, value)

    def synchronize(self, collections, *, allowed, canceled=lambda: False):
        if self.identity.base != DEFAULT_SERVER or canceled():
            return
        day = datetime.datetime.now(KST).date().isoformat()
        with self.lock:
            state = self._settings()
            fingerprint = self.fingerprint()
            pending = self._deletions(state)
            deletion = {"identity": fingerprint, "date": day}
            deleting = deletion in pending
            if state.get("identity") == fingerprint and state.get("delete_pending") and not deleting:
                # 지난 날짜는 서버의 다음 처리에서 정리하며 로컬 미확인 기록은 유지함.
                state.update(delete_pending=False, unresolved_deletions=pending)
                save(self.path, state)
        if not deleting and (not allowed or not state.get("enabled") or state.get("identity") != fingerprint):
            return
        if not deleting and state.get("sent_date") == day:
            return
        if not deleting and not any(store.daily_study() == {"date": day, "identity": fingerprint, "choice": state["choice"]}
                                    for store in collections.values()):
            return
        token = self.identity.settings().get("token")
        if not token or hashlib.sha256(token.encode()).hexdigest() != fingerprint:
            return
        data = {} if deleting else {"date": day, "accepted": True}
        try:
            nonce = json.loads(self.identity.path.with_name("identity-device.json").read_text(encoding="utf-8")).get("nonce")
            if isinstance(nonce, str) and re.fullmatch(r"[a-f0-9]{64}", nonce):
                data["nonce"] = nonce
        except (OSError, ValueError, AttributeError):
            pass
        with self.lock:
            if (canceled() or self.fingerprint() != fingerprint
                    or self._settings().get("choice") != state.get("choice")):
                return
        result = request(self.identity.base, "/v1/identity/study-activity", data, token=token,
                         method="DELETE" if deleting else "POST", error_detail=True)
        if result.get("eligible") is not True:
            if deleting:
                raise CollectionError("오늘 계정 집계 삭제를 확인하지 못했습니다. 본인 확인 후 다시 시도해 주세요.")
            return
        if (deleting and result.get("deleted") is not True) or (not deleting and result.get("date") != day):
            raise CollectionError("오늘 계정 집계 응답을 확인하지 못했습니다.")
        with self.lock:
            latest = self._settings()
            if latest.get("choice") != state.get("choice"):
                return
            if deleting:
                latest["unresolved_deletions"] = [row for row in self._deletions(latest) if row != deletion]
                if latest.get("identity") == fingerprint:
                    latest["delete_pending"] = False
            else:
                latest["sent_date"] = day
            save(self.path, latest)
        return "deleted" if deleting else None
