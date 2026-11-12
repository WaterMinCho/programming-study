# -*- coding: utf-8 -*-
"""제한한 저장소의 풀이 브랜치와 PR만 게시함. 제출 파일은 실행하지 않음."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from aiprep.collection import inside


class PublishError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise PublishError("GitHub 주소가 바뀌어 게시를 멈췄습니다.")


class Publisher:
    def __init__(self, repository, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise PublishError("GitHub 저장소 설정을 확인해 주세요.")
        self.repository, self.token = repository, token

    @classmethod
    def configured(cls):
        path = os.environ.get("STUDY_GITHUB_CONFIG", "")
        root = str(Path(__file__).resolve().parents[1])
        if not path or inside(path, root):
            raise PublishError("GitHub 게시 연결을 준비 중입니다. 서버에 저장한 풀이는 유지됩니다.")
        try:
            if os.name != "nt" and Path(path).stat().st_mode & 0o077:
                raise ValueError()
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data.get("token"), str) or not data["token"].strip():
                raise ValueError()
            return cls(data["repository"], data["token"])
        except (OSError, ValueError, KeyError, TypeError):
            raise PublishError("서버의 GitHub 게시 설정을 확인해 주세요.") from None

    def request(self, method, path, data=None, missing=False):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
        url = "https://api.github.com/repos/" + self.repository + path
        req = urllib.request.Request(url, raw, {"Authorization": "Bearer " + self.token,
                                     "Accept": "application/vnd.github+json", "Content-Type": "application/json",
                                     "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "programming-study"}, method=method)
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=5) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            error.close()
            if missing and error.code == 404:
                return None
            raise PublishError("GitHub 게시 요청이 완료되지 않았습니다. 상태 코드 %d입니다." % error.code) from None
        except (OSError, ValueError):
            raise PublishError("GitHub 응답을 받지 못했습니다. 저장한 풀이로 다시 게시할 수 있습니다.") from None

    def publish(self, public_id, display_id, digest, files, before_write=lambda: None):
        if not re.fullmatch(r"api_[a-f0-9]{32}", public_id) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise PublishError("서버의 풀이 식별자를 확인해 주세요.")
        branch = "study/" + public_id
        marker = "submission:" + digest
        def write(method, path, data):
            before_write()
            return self.request(method, path, data)
        previous = self.request("GET", "/git/ref/heads/" + branch, missing=True)
        tip = previous["object"]["sha"] if previous else None
        old = self.request("GET", "/git/commits/" + tip) if tip else None
        if not old or old["message"].splitlines()[-1] != marker:
            main = self.request("GET", "/git/ref/heads/main")["object"]["sha"]
            base = self.request("GET", "/git/commits/" + main)["tree"]["sha"]
            own = write("POST", "/git/trees", {"tree": [
                {"path": path, "mode": "100644", "type": "blob", "content": text}
                for path, text in sorted(files.items())]})["sha"]
            tree = write("POST", "/git/trees", {"base_tree": base, "tree": [
                {"path": "submissions/" + public_id, "mode": "040000", "type": "tree", "sha": own}]})["sha"]
            parents = [tip, main] if tip and tip != main else [main]
            commit = write("POST", "/git/commits", {"message": "%s 풀이 제출\n\n%s" % (display_id, marker),
                                                           "tree": tree, "parents": parents})["sha"]
            if previous:
                write("PATCH", "/git/refs/heads/" + branch, {"sha": commit, "force": False})
            else:
                write("POST", "/git/refs", {"ref": "refs/heads/" + branch, "sha": commit})
        owner = self.repository.split("/")[0]
        query = urllib.parse.urlencode({"head": owner + ":" + branch, "base": "main", "state": "open"})
        pulls = self.request("GET", "/pulls?" + query)
        pr = pulls[0] if pulls else write("POST", "/pulls", {
            "title": display_id + " 풀이", "head": branch, "base": "main",
            "body": "프로그램에서 제출한 풀이를 서버에 저장한 뒤 게시함. 채점·분석 결과는 검사와 댓글에서 확인함."})
        url = pr["html_url"]
        if not re.fullmatch(r"https://github\.com/" + re.escape(self.repository) + r"/pull/[1-9][0-9]*", url):
            raise PublishError("GitHub PR 주소를 확인하지 못했습니다.")
        return url
