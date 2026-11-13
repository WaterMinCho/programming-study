# -*- coding: utf-8 -*-
"""풀이 파일을 비공개 서버로 보내고 전송 결과를 확인함."""
import json
import functools
import os
from pathlib import Path
import re
import tempfile
import uuid
import secrets

from learning_data.collection import CollectionError, NOTICE, digest, inside, packed
from learning_data.sharing import Sharing, endpoint, request

MAX_BYTES = 4 * 1024 * 1024
MAX_REQUEST_BYTES = 6 * 1024 * 1024
SUFFIXES = (".py", ".js", ".json", ".md", ".txt", ".html", ".css", ".ts", ".tsx", ".jsx")


def check_canceled(canceled):
    if canceled():
        raise CollectionError("자동 제출을 멈췄습니다.", code="canceled")


def snapshot(root, user):
    folder = Path(root) / "submissions" / user
    files, size = {}, 0
    if folder.is_symlink():
        raise CollectionError("풀이 폴더의 바로가기 연결을 해제한 뒤 제출해 주세요.", status=422)
    for base, dirs, names in os.walk(folder, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "dist")]
        if any((Path(base) / d).is_symlink() for d in dirs):
            raise CollectionError("풀이 폴더 안의 심볼릭 링크는 제출할 수 없습니다.", status=422)
        for name in sorted(names):
            path = Path(base) / name
            rel = path.relative_to(folder).as_posix()
            if not (rel == "profile.json" or re.match(r"(?:[rsmc][0-9]+|journey|ai|web)/", rel)):
                continue
            if name.startswith(".") or path.suffix.lower() not in SUFFIXES or name in ("learning-data-sharing.json", "submission-api.json"):
                continue
            if path.is_symlink() or not inside(path, folder):
                raise CollectionError("풀이 폴더 밖을 가리키는 파일은 제출할 수 없습니다.", status=422)
            with path.open("rb") as source:
                raw = source.read(MAX_BYTES + 1)
            size += len(raw)
            if size > MAX_BYTES or len(files) >= 1000:
                raise CollectionError("풀이 파일이 제출 크기를 넘습니다. 스터디장에게 알려 주세요.", status=413)
            try:
                text = raw.decode("utf-8")
                if path.suffix == ".json":
                    decoded = json.loads(text.lstrip("\ufeff"))
                    if rel == "profile.json" and isinstance(decoded, dict) and not decoded.get("rounds") and not decoded.get("attempts"):
                        continue
            except (UnicodeError, ValueError):
                raise CollectionError("읽을 수 없는 풀이 파일이 있습니다: %s" % rel, status=422) from None
            files[rel] = text
    return files


class Client:
    def __init__(self, root, user, collections):
        self.root, self.user, self.collections = root, user, collections
        self.path = Path(collections["python"].path).parent / "submission-api.json"
        self.pending_path = self.path.with_name("submission-pending.json")
        self.transport = functools.partial(request, error_detail=True)

    def settings(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            raise CollectionError("API 제출 연결 설정을 읽을 수 없습니다.") from None

    def save(self, data, path=None):
        path = path or self.path
        if inside(path, self.root):
            raise CollectionError("API 인증 설정은 공개 저장소 밖에 보관해 주세요.")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp = tempfile.mkstemp(prefix=".submission-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
                output.write(packed(data))
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def connect(self, base, invite):
        base = endpoint(base)
        config = self.settings()
        if config.get("url") and config["url"] != base:
            raise CollectionError("이미 연결한 서버와 다른 주소입니다. 기존 연결을 유지해 주세요.")
        tracks = config.get("registration_tracks")
        if tracks is None:
            tracks = {}
            for name, store in self.collections.items():
                state = store.status()
                if state.get("participant") and not Sharing(store).settings():
                    tracks[name] = state["participant"]
        config.update(mode="api", url=base, participant=config.get("participant") or str(uuid.uuid4()), registration_tracks=tracks)
        self.save(config)
        if not config.get("token"):
            result = self.transport(base, "/v1/register", {"participant": config["participant"], "display_id": self.user,
                                    "invite": invite, "notice": NOTICE, "tracks": tracks})
            if result.get("participant") != config["participant"] or not re.fullmatch(r"[a-f0-9]{64}", str(result.get("token", ""))):
                raise CollectionError("서버의 API 등록 응답을 확인해 주세요.")
            if not re.fullmatch(r"api_[a-f0-9]{32}", str(result.get("public_id", ""))):
                raise CollectionError("서버의 공개 풀이 식별자를 확인해 주세요.")
            connections = result.get("tracks")
            if not isinstance(connections, dict) or set(connections) != set(tracks):
                raise CollectionError("서버의 과목별 연결 응답을 확인해 주세요.")
            for name, child in connections.items():
                if not isinstance(child, dict) or child.get("participant") != tracks[name] or not re.fullmatch(r"[a-f0-9]{64}", str(child.get("token", ""))):
                    raise CollectionError("서버의 과목별 인증 응답을 확인해 주세요.")
            config.update(token=result["token"], public_id=result["public_id"], connections=result.get("tracks", {}))
            self.save(config)
        self.install_connections(config)

    def install_connections(self, config):
        for track, details in config.get("connections", {}).items():
            store = self.collections.get(track)
            if store is None or store.status().get("participant") != details.get("participant"):
                continue  # 추가 데이터를 삭제·새로 시작한 과목은 이전 인증으로 다시 연결하지 않음.
            share = Sharing(store)
            old = share.settings()
            if old:
                if old.get("url") != config["url"] or old.get("participant") != details["participant"] or old.get("token") != details["token"]:
                    raise CollectionError("기존 학습 데이터 전송 연결을 덮어쓰지 않았습니다.")
            else:
                share._save({"url": config["url"], "participant": details["participant"], "token": details["token"],
                             "sequence": 0, "notice": NOTICE, "include_answers": False})

    def connect_open(self, base=None):
        """공개 파일을 확인한 참가자의 제출 전용 연결을 준비함. 연구 수집은 별도로 동의함."""
        from learning_data.privacy import DEFAULT_SERVER
        base = endpoint(base or DEFAULT_SERVER)
        config = self.settings()
        if config.get("url") and config["url"] != base:
            raise CollectionError("기존 제출 서버 연결을 확인해 주세요.")
        if config.get("token"):
            return
        config.update(mode="api", url=base, participant=config.get("participant") or str(uuid.uuid4()),
                      registration_secret=config.get("registration_secret") or secrets.token_hex(32),
                      display_id=config.get("display_id") or self.user[:51] + "_" + secrets.token_hex(5), separate_research=True)
        self.save(config)
        result = self.transport(base, "/v1/register/open", {"participant": config["participant"], "display_id": config["display_id"],
                                "notice": NOTICE, "registration_secret": config["registration_secret"],
                                "public_submission": True, "tracks": {}})
        if result.get("participant") != config["participant"] or not re.fullmatch(r"[a-f0-9]{64}", str(result.get("token", ""))):
            raise CollectionError("서버의 제출 연결 응답을 확인해 주세요.")
        if not re.fullmatch(r"api_[a-f0-9]{32}", str(result.get("public_id", ""))):
            raise CollectionError("서버의 공개 풀이 식별자를 확인해 주세요.")
        config.update(token=result["token"], public_id=result["public_id"])
        self.save(config)

    def pending(self):
        files = snapshot(self.root, self.user)
        config = self.settings()
        if config.get("separate_research") or "connections" not in config:
            return {"status": "ok", "pending": bool(files) and digest(files) != config.get("published_hash"),
                    "count": len(files) if digest(files) != config.get("published_hash") else 0}
        pending = bool(files) and digest(files) != config.get("published_hash") or bool(config.get("research_pending"))
        for store in self.collections.values():
            share = Sharing(store).settings()
            if share and store.status()["enabled"] and not store.status()["error"]:
                pending = pending or len(store.snapshot(after=share.get("sequence", 0), limit=1)[1:]) > 0
        return {"status": "ok", "pending": pending, "count": len(files) if pending else 0}

    def submit(self):
        config = self.settings()
        if not config.get("token"):
            return {"status": "setup_required", "message": "API 제출 서버를 먼저 연결해 주세요."}
        self.install_connections(config)
        files = snapshot(self.root, self.user)
        if not files:
            return {"status": "nothing", "message": "아직 제출할 풀이가 없습니다."}
        batches = []
        if self.pending_path.exists():
            saved = json.loads(self.pending_path.read_text(encoding="utf-8"))
            expected = digest({"files": saved.get("files"), "request": saved.get("request_id")})
            if saved.get("participant") != config["participant"] or saved.get("digest") != expected:
                raise CollectionError("이전 제출의 보관 파일을 확인해 주세요.")
            batches.append(saved)
        if ((not batches and config.get("published_hash") != digest(files)) or
                (batches and digest(batches[-1]["files"]) != digest(files))):
            nonce = str(uuid.uuid4())
            batches.append({"participant": config["participant"], "request_id": nonce, "files": files,
                            "digest": digest({"files": files, "request": nonce})})
        sent, errors = 0, []
        for store in (() if config.get("separate_research") else self.collections.values()):
            if not store.status()["enabled"]:
                continue
            try:
                share = Sharing(store)
                setup = share.settings()
                if setup:
                    sent += share.sync(setup["url"], include_answers=setup["include_answers"])["sent"]
            except CollectionError as error:
                errors.append(str(error))
        config["research_pending"] = bool(errors)
        self.save(config)
        url = config.get("pr_url")
        for part in batches:
            current = part["digest"]
            self.save(part, self.pending_path)
            saved = self.transport(config["url"], "/v1/submissions", {"files": part["files"], "request_id": part["request_id"], "digest": current,
                                   "previous": config.get("last_hash")}, token=config["token"], timeout=20)
            if saved.get("digest") != current or saved.get("state") not in ("stored", "published"):
                raise CollectionError("서버의 풀이 저장 확인을 받지 못했습니다. 로컬 풀이는 유지됩니다.")
            config["last_hash"] = current
            self.save(config)
            try:
                published = saved if saved["state"] == "published" else self.transport(config["url"], "/v1/submissions/publish",
                                        {"digest": current}, token=config["token"], timeout=55)
                url = published.get("pr_url", "")
                if published.get("digest") != current or published.get("state") != "published" or not isinstance(url, str) or not re.fullmatch(
                        r"https://github\.com/WaterMinCho/programming-study/pull/[1-9][0-9]*", url):
                    raise CollectionError("GitHub PR 생성 확인을 받지 못했습니다.")
            except CollectionError as error:
                raise CollectionError("서버에 풀이를 저장했습니다. GitHub 게시를 마치지 못했으니 다시 [풀이 제출]을 눌러 주세요. %s" % error) from None
            config.update(published_hash=digest(part["files"]), pr_url=url)
            self.save(config)
            self.pending_path.unlink(missing_ok=True)
        message = "서버에 풀이를 저장하고 GitHub PR에 올렸습니다. 추가 학습 기록 %d건도 전송했습니다." % sent
        if config.get("separate_research"):
            message = "서버에 풀이를 저장하고 GitHub PR에 올렸습니다."
        if errors:
            message = "서버 저장과 GitHub 제출을 마쳤습니다. 추가 학습 기록 일부는 보내지 못했으니 다시 [풀이 제출]을 눌러 주세요."
        config["research_pending"] = bool(errors)
        self.save(config)
        return {"status": "ok", "message": message, "pr_url": url, "detail": "\n".join(errors)}


class PrivateClient(Client):
    """풀이 파일을 비공개 서버에만 저장하고 공개 Git 게시를 호출하지 않음."""

    def __init__(self, root, user, collections):
        super().__init__(root, user, collections)
        self.path = self.path.with_name("private-submission.json")
        self.pending_path = self.path.with_name("private-submission-pending.json")

    def settings(self):
        config = super().settings()
        if config.get("token"):
            if (not isinstance(config["token"], str) or not re.fullmatch(r"[a-f0-9]{64}", config["token"]) or not isinstance(config.get("participant"), str)
                    or not config["participant"] or not isinstance(config.get("url"), str)):
                raise CollectionError("제출 연결 정보를 확인할 수 없습니다. 연결 파일을 지우지 말고 운영자에게 문의해 주세요.")
            endpoint(config["url"])
        return config

    def pending(self):
        files = snapshot(self.root, self.user)
        config = self.settings()
        saved = self._pending_request(config)
        pending = bool(files) and (digest(files) != config.get("published_hash") or saved is not None)
        return {"status": "ok", "pending": pending, "count": len(files) if pending else 0}

    def _pending_request(self, config):
        if not self.pending_path.exists():
            return None
        try:
            saved = json.loads(self.pending_path.read_text(encoding="utf-8"))
            if (not isinstance(saved, dict) or not isinstance(saved.get("files"), dict) or not saved["files"]
                    or not isinstance(saved.get("request_id"), str) or saved.get("participant") != config.get("participant")
                    or saved.get("digest") != digest({"files": saved.get("files"), "request": saved.get("request_id")})):
                raise ValueError()
        except (OSError, ValueError):
            raise CollectionError("이전 제출의 대기 정보를 읽을 수 없습니다. 파일을 지우지 말고 운영자에게 문의해 주세요. 로컬 풀이는 유지됩니다.") from None
        return saved

    def submit_ready(self, automatic=False, canceled=lambda: False):
        check_canceled(canceled)
        from learning_data.privacy import Consent, DEFAULT_SERVER
        consent = Consent(self.collections)
        state = consent.settings()
        if consent.needs_choice() or not state.get("accepted") or state.get("withdraw_pending"):
            return {"status": "error", "message": "[내 정보·데이터]에서 동의 내용을 확인한 뒤 제출해 주세요. 로컬 풀이는 유지됩니다."}
        if automatic:
            from learning_data.privacy import validate_receipt
            receipt = validate_receipt(state.get("receipt"))
            if not receipt.get("automatic_submission", {}).get("accepted"):
                self.sync_consent(consent, state, canceled=canceled)
                return {"status": "paused", "message": "답안 파일 자동 제출을 사용하지 않습니다."}
            validate_receipt(receipt, automatic=True)
            if not all(store.status()["enabled"] for store in self.collections.values()):
                return {"status": "paused", "message": "수집을 중단한 과목이 있어 파일 자동 제출을 멈췄습니다."}
        if not self.pending()["pending"]:
            if automatic:
                self.sync_consent(consent, state, canceled=canceled)
            return {"status": "nothing", "message": "새로 제출할 풀이가 없습니다."}
        config = self.settings()
        if not config.get("token"):
            if config.get("url") and config["url"] != DEFAULT_SERVER and not config.get("enroll_sent"):
                return {"status": "error", "message": "다른 서버 연결은 운영자 설정에서 먼저 확인해 주세요. 로컬 풀이는 유지됩니다.", "retryable": False}
            self.connect_open(config.get("url"), canceled=canceled)
        if automatic:
            self.sync_consent(consent, state, canceled=canceled)
        return self.submit(automatic=automatic, canceled=canceled)

    def sync_consent(self, consent, state, canceled=lambda: False):
        config = self.settings()
        if not config.get("token"):
            return
        receipt = state["receipt"]
        stamp = digest(receipt)
        if config.get("consent_stamp") != stamp:
            check_canceled(canceled)
            confirmed = self.transport(config["url"], "/v1/consent", {"consent": receipt}, token=config["token"])
            if confirmed.get("consent_saved") is not True:
                raise CollectionError("자동 제출 동의의 저장 확인을 받지 못했습니다.")
            config["consent_stamp"] = stamp
            self.save_active(consent, state.get("choice"), config)

    def save_active(self, consent, choice, data, path=None):
        with consent.lock:
            current = consent.settings()
            if current.get("choice") != choice or not current.get("accepted") or current.get("withdraw_pending") or consent.needs_choice():
                raise CollectionError("동의가 바뀌어 제출을 멈췄습니다. 로컬 풀이는 유지됩니다.")
            self.save(data, path)

    def connect_open(self, base=None, canceled=lambda: False):
        from learning_data.privacy import Consent, DEFAULT_SERVER, validate_receipt
        consent = Consent(self.collections)
        state = consent.settings()
        if consent.needs_choice() or not state.get("accepted") or state.get("withdraw_pending"):
            raise CollectionError("[내 정보·데이터]에서 수집 내용을 확인하고 동의한 뒤 제출해 주세요.")
        try:
            receipt = validate_receipt(state.get("receipt"))
        except ValueError as error:
            raise CollectionError(str(error)) from error
        base = endpoint(base or DEFAULT_SERVER)
        config = self.settings()
        if config.get("url") and config["url"] != base:
            raise CollectionError("기존 제출 서버 연결을 확인해 주세요.")
        config.update(mode="private", url=base, participant=config.get("participant") or str(uuid.uuid4()),
                      registration_secret=config.get("registration_secret") or secrets.token_hex(32),
                      display_id=config.get("display_id") or "private_" + secrets.token_hex(12), separate_research=True)
        if config.get("token"):
            return
        config["enroll_sent"] = True
        self.save_active(consent, state.get("choice"), config)
        check_canceled(canceled)
        result = self.transport(base, "/v1/register/private", {"participant": config["participant"], "display_id": config["display_id"],
                                "notice": NOTICE, "registration_secret": config["registration_secret"], "consent": receipt,
                                "private_submission": True, "tracks": {}})
        if result.get("participant") != config["participant"] or not re.fullmatch(r"[a-f0-9]{64}", str(result.get("token", ""))):
            raise CollectionError("서버의 비공개 제출 연결 응답을 확인해 주세요.")
        current = consent.settings()
        if current.get("choice") != state.get("choice") or not current.get("accepted") or current.get("withdraw_pending"):
            raise CollectionError("연결 중 동의가 바뀌어 제출을 멈췄습니다.")
        config.update(token=result["token"], consent_stamp=digest(receipt))
        self.save_active(consent, state.get("choice"), config)

    def submit(self, automatic=False, canceled=lambda: False):
        from learning_data.privacy import Consent, validate_receipt
        consent = Consent(self.collections)
        state = consent.settings()
        if consent.needs_choice() or not state.get("accepted") or state.get("withdraw_pending"):
            return {"status": "error", "message": "수집 동의를 확인한 뒤 제출해 주세요. 로컬 풀이는 유지됩니다."}
        if automatic:
            validate_receipt(state.get("receipt"), automatic=True)
        config = self.settings()
        choice = state.get("choice")
        if not config.get("token"):
            return {"status": "setup_required", "message": "비공개 풀이 제출을 연결해 주세요."}
        files = snapshot(self.root, self.user)
        if not files:
            return {"status": "nothing", "message": "아직 제출할 풀이가 없습니다."}
        parts = []
        saved = self._pending_request(config)
        if saved is not None:
            parts.append(saved)
        if (not parts and config.get("published_hash") != digest(files)) or (parts and digest(parts[-1]["files"]) != digest(files)):
            request_id = str(uuid.uuid4())
            parts.append({"participant": config["participant"], "request_id": request_id, "files": files,
                          "digest": digest({"files": files, "request": request_id})})
        if not parts:
            return {"status": "nothing", "message": "이미 제출한 풀이입니다.", "pr_url": None, "receipt": config.get("last_hash")}
        for part in parts:
            payload = {"files": part["files"], "request_id": part["request_id"],
                       "digest": part["digest"], "previous": config.get("last_hash")}
            if automatic:
                payload["automatic"] = True
            if part is not saved and len(packed(payload).encode("utf-8")) > MAX_REQUEST_BYTES:
                raise CollectionError("줄바꿈·기호를 포함한 전송 크기가 6MiB를 넘습니다. 풀이 파일을 줄인 뒤 다시 제출해 주세요. 로컬 풀이는 유지됩니다.", status=413)
            if automatic:
                if not all(store.status()["enabled"] for store in self.collections.values()):
                    return {"status": "paused", "message": "수집을 중단해 파일 자동 제출을 멈췄습니다."}
            self.save_active(consent, choice, part, self.pending_path)
            try:
                check_canceled(canceled)
                result = self.transport(config["url"], "/v1/private/submissions", payload, token=config["token"], timeout=20)
            except CollectionError as error:
                with consent.lock:
                    if consent.settings().get("choice") == choice:
                        if error.status in (400, 403, 413, 415, 422):
                            self.pending_path.unlink(missing_ok=True)
                        if error.status == 413 and part is saved:
                            raise CollectionError("이전 제출의 대기 정보를 정리했습니다. [풀이 제출]을 다시 눌러 현재 답안을 보내 주세요.", status=413, code="pending_oversized_removed") from error
                        if error.code == "revoked":
                            consent.withdraw()
                raise
            if result.get("digest") != part["digest"] or result.get("state") != "stored":
                raise CollectionError("서버의 저장 확인을 받지 못했습니다. 로컬 풀이는 유지됩니다.")
            config.update(last_hash=part["digest"], published_hash=digest(part["files"]))
            with consent.lock:
                self.save_active(consent, choice, config)
                self.pending_path.unlink(missing_ok=True)
        return {"status": "ok", "message": "비공개 서버에 풀이를 저장했습니다.", "pr_url": None, "receipt": config.get("last_hash")}


def submit_private(client, automatic=False, canceled=lambda: False):
    if client is None:
        return {"status": "error", "message": "비공개 제출 연결을 확인해 주세요.", "retryable": False}
    try:
        return client.submit_ready(automatic=True, canceled=canceled) if automatic else client.submit_ready()
    except (CollectionError, OSError, ValueError) as error:
        message = str(error)
        status = error.status if isinstance(error, CollectionError) else None
        if getattr(error, "code", None) == "canceled":
            return {"status": "paused", "message": message}
        if status == 401:
            message += " 연결 파일을 지우지 말고 운영자에게 문의해 주세요. 로컬 풀이는 유지됩니다."
        retryable = (getattr(error, "code", None) in ("network", "pending_oversized_removed") or
                     (status is not None and (status in (408, 429) or status >= 500)) or isinstance(error, FileNotFoundError))
        return {"status": "error", "message": message, "detail": "", "retryable": retryable}


class Flow:
    def __init__(self, git):
        self.git, self.api = git, None

    def __getattr__(self, name):
        return getattr(self.git, name)

    def set_collections(self, collections):
        self.api = PrivateClient(self.git.root, self.git.user, collections)

    def pending(self):
        try:
            if self.api:
                return self.api.pending()
            return self.git.pending()
        except (CollectionError, OSError, ValueError):
            return {"status": "error", "pending": False, "count": 0}

    def submit(self):
        return submit_private(self.api)

    def sync(self):
        result = self.git.sync()
        if result.get("status") in ("no_git", "not_repo"):
            result["message"] = "새 자료를 받으려면 Git으로 복제한 프로그램 폴더가 필요합니다. 풀이는 비공개 서버에 제출합니다."
        return result
