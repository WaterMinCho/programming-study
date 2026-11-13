# -*- coding: utf-8 -*-
"""사용자가 요청할 때만 추가 데이터를 전송함. 인증 값은 로컬 파일에 보관함."""
import ipaddress
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import secrets

from learning_data.collection import CollectionError, FORMAT, NOTICE, SYNC_FILENAME, packed

MAX_BODY = 1024 * 1024


def endpoint(value):
    value = value.strip().rstrip("/")
    url = urllib.parse.urlsplit(value)
    if url.username or url.password or url.query or url.fragment or not url.hostname:
        raise CollectionError("수집 서버의 주소를 확인해 주세요.")
    local = url.hostname == "localhost"
    try:
        local = local or ipaddress.ip_address(url.hostname).is_loopback
    except ValueError:
        pass
    if url.scheme != "https" and not (url.scheme == "http" and local):
        raise CollectionError("HTTPS 주소를 입력해 주세요. 이 기기의 개발 서버만 HTTP를 사용할 수 있습니다.")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectionError("수집 서버의 주소가 바뀌었습니다. 새 주소를 직접 확인해 주세요.")


def request(base, path, data=None, token=None, method="POST", timeout=5, error_detail=False):
    payload = packed(data).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(endpoint(base) + path, payload, headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise CollectionError("수집 서버의 응답 크기를 확인해 주세요.")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError()
            return result
    except urllib.error.HTTPError as error:
        message = "수집 서버가 요청을 받지 않았습니다. 상태 코드 %d입니다." % error.code
        reason = None
        try:
            failure = json.loads(error.read(4096))
            detail = failure.get("error")
            reason = "revoked" if failure.get("code") == "revoked" else None
            if error_detail and isinstance(detail, str) and len(detail) <= 500:
                message += " " + detail
        except (OSError, ValueError, AttributeError):
            pass
        error.close()
        raise CollectionError(message, status=error.code, code=reason) from None
    except (urllib.error.URLError, OSError, ValueError):
        raise CollectionError("수집 서버에 연결하지 못했습니다. 데이터는 이 기기에 남아 있으니 다시 보내 주세요.", code="network") from None


class Sharing:
    def __init__(self, collection):
        self.collection = collection
        self.path = os.path.join(os.path.dirname(collection.path), SYNC_FILENAME)

    def settings(self):
        try:
            with open(self.path, encoding="utf-8") as source:
                data = json.load(source)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            raise CollectionError("서버 연결 설정을 읽을 수 없습니다.") from None

    def _save(self, data):
        self.collection._check_path()
        path = None
        try:
            fd, path = tempfile.mkstemp(prefix=".sharing-", dir=os.path.dirname(self.path))
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
                output.write(packed(data) + "\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(path, self.path)
        except OSError:
            raise CollectionError("서버 연결 설정을 저장하지 못했습니다. 다시 보내도 같은 기록은 중복 저장하지 않습니다.") from None
        finally:
            if path and os.path.exists(path):
                os.unlink(path)

    def connect_open(self, base, consent, after=0):
        """동의 뒤의 기록을 개인 초대 코드 없이 연결함."""
        from learning_data.privacy import validate_receipt, POLICY_VERSION
        try:
            receipt = validate_receipt(consent)
        except ValueError as error:
            raise CollectionError(str(error)) from error
        base = endpoint(base)
        status = self.collection.status()
        if not status["enabled"] or status["error"]:
            raise CollectionError("동의한 뒤 수집을 시작해 주세요.")
        config = self.settings()
        if config and (config.get("url") != base or config.get("participant") != status["participant"]):
            raise CollectionError("기존 서버 연결을 확인해 주세요.")
        if not config:
            config = {"url": base, "participant": status["participant"], "sequence": after,
                      "notice": NOTICE, "include_answers": False, "registration_secret": secrets.token_hex(32)}
            self._save(config)
        if not config.get("token"):
            config.update(enroll_sent=True, consent_receipt=receipt)
            self._save(config)
            enrolled = request(base, "/v1/enroll/open", {"participant": config["participant"], "notice": NOTICE,
                               "registration_secret": config["registration_secret"], "consent": receipt}, error_detail=True)
            if enrolled.get("participant") != config["participant"] or not isinstance(enrolled.get("token"), str):
                raise CollectionError("참가자 등록 응답을 확인해 주세요.")
            config["token"] = enrolled["token"]
            self._save(config)
        if config.get("consent_policy") != POLICY_VERSION or config.get("consent_receipt") != receipt or after > config.get("sequence", 0):
            request(base, "/v1/consent", {"consent": receipt}, token=config["token"], error_detail=True)
            config.update(consent_policy=POLICY_VERSION, consent_receipt=receipt, include_answers=False,
                          sequence=max(config.get("sequence", 0), after))
            self._save(config)

    def sync(self, base, invite="", include_answers=False, canceled=lambda: False):
        status = self.collection.status()
        if not status["enabled"] or status["error"]:
            raise CollectionError("추가 데이터 수집을 시작하고 저장 상태를 확인한 뒤 보내 주세요.")
        base = endpoint(base)
        config = self.settings()
        if config and (config.get("url") != base or config.get("participant") != status["participant"]):
            raise CollectionError("이미 연결한 서버와 참가자 정보를 확인해 주세요. 다른 서버로 바꾸기 전 기존 연결을 정리해 주세요.")
        if config and config.get("include_answers") != bool(include_answers):
            raise CollectionError("전송 중에는 답안 포함 설정을 바꿀 수 없습니다. 기존 서버 데이터를 삭제한 뒤 다시 연결해 주세요.")
        if config and not config.get("token"):
            raise CollectionError("서버 연결을 마친 뒤 다시 전송해 주세요. 자동 연결은 다음 전송 때 다시 시도합니다.")
        if not config:
            enrolled = request(base, "/v1/enroll", {"participant": status["participant"], "invite": invite, "notice": NOTICE})
            if enrolled.get("participant") != status["participant"] or not isinstance(enrolled.get("token"), str):
                raise CollectionError("서버의 참가자 등록 응답을 확인해 주세요.")
            config = {"url": base, "participant": status["participant"], "token": enrolled["token"], "sequence": 0,
                      "notice": NOTICE, "include_answers": bool(include_answers)}
            self._save(config)
        sent = 0
        while True:
            if canceled():
                return {"sent": sent, "last_sequence": config["sequence"]}
            if not self.collection.status()["enabled"]:
                raise CollectionError("수집을 중단해 전송도 멈췄습니다. 이미 확인받은 기록은 서버에 남습니다.")
            rows = self.collection.snapshot(after=config["sequence"], limit=100, include_answers=include_answers)[1:]
            if not rows:
                return {"sent": sent, "last_sequence": config["sequence"]}
            data = {"participant": status["participant"], "notice": NOTICE, "format": FORMAT,
                    "track": self.collection.track, "events": rows}
            while len(packed(data).encode("utf-8")) > MAX_BODY and len(rows) > 1:
                rows = rows[:len(rows) // 2]
                data["events"] = rows
            if len(packed(data).encode("utf-8")) > MAX_BODY:
                raise CollectionError("문항 한 건의 전송 크기가 너무 큽니다. 관리자에게 알려 주세요.")
            result = request(base, "/v1/events", data, token=config["token"])
            if result.get("received") != len(rows) or result.get("last_sequence") != rows[-1]["sequence"]:
                raise CollectionError("서버의 저장 확인이 맞지 않습니다. 이 기기의 기록은 유지됩니다.")
            config["sequence"] = rows[-1]["sequence"]
            self._save(config)
            sent += len(rows)

    def delete_remote(self):
        config = self.settings()
        if not config:
            raise CollectionError("연결한 수집 서버가 없습니다.")
        if not config.get("token"):
            if config.get("enroll_sent"):
                result = request(config["url"], "/v1/withdraw/open", {"participant": config["participant"],
                                 "registration_secret": config["registration_secret"]})
                if result.get("deleted") is not True:
                    raise CollectionError("서버의 철회 확인을 받지 못했습니다.")
                os.unlink(self.path)
                return result
            else:
                os.unlink(self.path)
                return {"deleted": True}
        result = request(config["url"], "/v1/me", token=config["token"], method="DELETE")
        if result.get("deleted") is not True:
            raise CollectionError("서버의 삭제 확인을 받지 못했습니다.")
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        except OSError:
            raise CollectionError("서버의 풀이를 삭제한 뒤 연결 설정 파일을 지우지 못했으니 다시 삭제를 요청해 주세요.") from None
        return result
