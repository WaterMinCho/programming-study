# -*- coding: utf-8 -*-
"""계정 정보를 보관하지 않고 한 번 확인한 기기를 기억함."""
import json
import datetime
import os
from pathlib import Path
import re
import secrets
import tempfile
import urllib.parse
import urllib.request

from learning_data.collection import CollectionError, inside, packed
from learning_data.privacy import DEFAULT_SERVER
from learning_data.sharing import NoRedirect, request


def github(path, data):
    req = urllib.request.Request("https://github.com" + path, urllib.parse.urlencode(data).encode(),
                                 {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
                                  "User-Agent": "programming-study-identity"}, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=10) as response:
            raw = response.read(16385)
            if len(raw) > 16384:
                raise ValueError()
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
    except (OSError, ValueError):
        raise CollectionError("GitHub에 연결하지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요.") from None


class Identity:
    def __init__(self, repository, user, home=None, base=DEFAULT_SERVER):
        import session
        if not session.valid_user(user):
            raise CollectionError("기기 사용자를 확인해 주세요.")
        home = home or os.environ.get("STUDY_IDENTITY_HOME") or os.environ.get("STUDY_AI_HOME") or str(Path.home() / ".rokey-study" / "identity")
        self.path = Path(home) / "identity.json"
        if inside(self.path, repository):
            raise CollectionError("기기 인증은 저장소 밖에 보관해 주세요.")
        self.base, self.pending_token = base, None
        self.device, self.client_id, self.nonce = None, None, secrets.token_hex(32)

    def settings(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(value, dict) or value.get("verified") is not True or type(value.get("team")) is not bool
                    or (value["team"] and not re.fullmatch(r"[a-f0-9]{64}", str(value.get("token", ""))))):
                raise ValueError()
            return value
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            raise CollectionError("이 기기의 본인 확인 정보를 읽지 못했습니다. 원본 파일은 그대로 보관합니다.") from None

    def save(self, result):
        value = {"verified": result.get("verified") is True, "team": result.get("team") is True}
        if not value["verified"]:
            raise CollectionError("본인 확인 응답을 확인해 주세요.")
        if value["team"]:
            if not re.fullmatch(r"[a-f0-9]{64}", str(result.get("token", ""))):
                raise CollectionError("기기 확인 응답을 확인해 주세요.")
            value["token"] = result["token"]
        self.settings()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".identity-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(packed(value) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.pending_token = None
        self.device = None
        return value

    def begin(self):
        config = request(self.base, "/v1/identity/config", method="GET", error_detail=True)
        if not config.get("enabled") or not re.fullmatch(r"[A-Za-z0-9_.-]{6,128}", str(config.get("client_id", ""))):
            raise CollectionError("본인 확인 연결을 준비 중입니다. 잠시 뒤 다시 시도해 주세요.")
        self.client_id = config["client_id"]
        value = github("/login/device/code", {"client_id": self.client_id})
        if (value.get("verification_uri") != "https://github.com/login/device" or not isinstance(value.get("device_code"), str)
                or not isinstance(value.get("user_code"), str) or type(value.get("expires_in")) is not int
                or not 1 <= value["expires_in"] <= 1800):
            raise CollectionError("GitHub 본인 확인 안내를 읽지 못했습니다.")
        self.nonce, self.pending_token = self.installation_nonce(), None
        self.device = value
        return {key: value[key] for key in ("verification_uri", "user_code", "expires_in")}

    def installation_nonce(self):
        path = self.path.with_name("identity-device.json")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not path.exists():
            fd, temporary = tempfile.mkstemp(prefix=".device-", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(packed({"nonce": secrets.token_hex(32)}) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary, path)
                except FileExistsError:
                    pass
            finally:
                os.unlink(temporary)
        try:
            nonce = json.loads(path.read_text(encoding="utf-8"))["nonce"]
            if not isinstance(nonce, str) or not re.fullmatch(r"[a-f0-9]{64}", nonce):
                raise ValueError()
            return nonce
        except (OSError, ValueError, KeyError, TypeError):
            raise CollectionError("기기 확인 코드를 읽지 못했습니다. 원본은 그대로 보관합니다.") from None

    def poll(self):
        nonce = self.nonce
        if not nonce or (self.pending_token is None and self.device is None):
            raise CollectionError("본인 확인을 다시 시작해 주세요.")
        if self.pending_token is None:
            value = github("/login/oauth/access_token", {"client_id": self.client_id, "device_code": self.device["device_code"],
                                                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
            error = value.get("error")
            if error in ("authorization_pending", "slow_down"):
                interval = int(self.device.get("interval", 5)) + (5 if error == "slow_down" else 0)
                self.device["interval"] = interval
                return {"pending": True, "interval": max(5, interval)}
            token = value.pop("access_token", None)
            value.clear()
            if not isinstance(token, str):
                self.cancel()
                raise CollectionError("GitHub 확인을 마치지 못했습니다. 다시 시작해 주세요.")
            self.pending_token = token
        result = request(self.base, "/v1/identity/verify", {"access_token": self.pending_token, "nonce": nonce},
                         timeout=30, error_detail=True)
        if nonce != self.nonce:
            raise CollectionError("본인 확인을 중단했습니다.")
        return self.save(result)

    def summary(self, days):
        settings = self.settings()
        if not settings.get("team"):
            raise CollectionError("스터디원에게만 제공하는 통계입니다.")
        result = request(self.base, "/v1/team/summary?days=" + str(days), token=settings["token"], method="GET", error_detail=True)
        try:
            for key in ("total", "period_total", "undated", "installations", "period_installations"):
                if type(result[key]) is not int or result[key] < 0:
                    raise ValueError()
            if result["days"] != days or len(result["series"]) != (24 if days == 1 else days):
                raise ValueError()
            for row in result["series"]:
                if not isinstance(row["at"], str) or any(type(row[key]) is not int or row[key] < 0 for key in ("python", "ai")):
                    raise ValueError()
                if datetime.datetime.fromisoformat(row["at"]).tzinfo is None:
                    raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise CollectionError("통계 응답을 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 확인해 주세요.") from None
        return result

    def cancel(self):
        self.pending_token = self.device = None
        self.nonce = None
