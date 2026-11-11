"""기본 브랜치에서 공개 PR의 상태만 읽어 Slack 카드로 보냄."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile


REPO = "WaterMinCho/programming-study"
WEB = f"https://github.com/{REPO}"
RELAY = ".github/workflows/slack-events.yml"
WORKFLOWS = {
    ".github/workflows/ci.yml": "CI",
    ".github/workflows/style.yml": "문장 검사",
    ".github/workflows/learning-server.yml": "수집 서버 운영 검사",
    ".github/workflows/journey.yml": "알고리즘 여행 검증",
}
RESULTS = {
    "success": "통과", "failure": "실패", "timed_out": "시간 초과",
    "action_required": "실행 승인 필요", "cancelled": "취소", "skipped": "생략",
    "neutral": "판정 없음", "startup_failure": "실행 환경 오류",
}
LIMIT = 1024 * 1024


def plain(value, limit=160):
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(value))[:limit]


def escaped(value):
    return plain(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def positive(value):
    if type(value) is not int or value <= 0:
        raise ValueError("이벤트 번호의 형식이 올바르지 않음")
    return value


def card(title, description, pr=None, fields=(), buttons=(), footer=""):
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": title}}]
    if pr:
        blocks.append({"type": "section", "text": {
            "type": "plain_text", "text": f"#{pr['number']}  {plain(pr['title'])}"}})
    blocks.append({"type": "section", "text": {"type": "plain_text", "text": description}})
    if fields:
        blocks.append({"type": "section", "fields": [
            {"type": "plain_text", "text": f"{label}\n{plain(value, 300)}"}
            for label, value in fields]})
    if buttons:
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": label},
             "url": url, **({"style": "primary"} if i == 0 else {})}
            for i, (label, url) in enumerate(buttons)]})
    if footer:
        blocks.append({"type": "context", "elements": [
            {"type": "plain_text", "text": footer}]})
    fallback = title + (f" · #{pr['number']} {escaped(pr['title'])}" if pr else "")
    fallback += "\n" + escaped(description)
    fallback += "".join(f"\n{escaped(label)}: {escaped(value)}" for label, value in fields)
    fallback += "".join(f"\n{label}: {url}" for label, url in buttons)
    return {"text": fallback, "blocks": blocks,
            "unfurl_links": False, "unfurl_media": False}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_url(request, limit=LIMIT):
    with build_opener(NoRedirect).open(request, timeout=20) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("알림 조회 크기 초과")
    return data


class GitHub:
    def __init__(self, token):
        self.token = token

    def get(self, path, binary=False):
        if not path.startswith(f"/repos/{REPO}/") or ".." in path:
            raise ValueError("GitHub 조회 경로가 올바르지 않음")
        request = Request("https://api.github.com" + path, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json", "User-Agent": "study-notifications"})
        try:
            data = read_url(request)
        except HTTPError as error:
            if not binary or error.code != 302:
                raise
            location = error.headers.get("Location", "")
            parsed = urlparse(location)
            if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
                    or not parsed.hostname or not parsed.hostname.endswith(
                        (".blob.core.windows.net", ".actions.githubusercontent.com"))):
                raise ValueError("이벤트 파일의 다운로드 경로가 올바르지 않음") from None
            # 파일 호스트에는 GitHub 인증 헤더를 전달하지 않음
            data = read_url(Request(location, headers={"User-Agent": "study-notifications"}))
        return data if binary else json.loads(data)

    def pages(self, path):
        separator = "&" if "?" in path else "?"
        for page in range(1, 32):
            data = self.get(f"{path}{separator}per_page=100&page={page}")
            yield from data
            if len(data) < 100:
                return
        raise ValueError("알림 조회 페이지 초과")


def endpoint(path):
    return f"/repos/{REPO}/{path}"


def development(pr, github):
    if pr.get("base", {}).get("repo", {}).get("full_name") != REPO:
        return False
    if pr["head"]["ref"].startswith("study/"):
        return False
    files = list(github.pages(endpoint(f"pulls/{positive(pr['number'])}/files")))
    return bool(files) and any(not item["filename"].startswith("submissions/") for item in files)


def association(run, github):
    sha = run["head_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("실행 판이 올바르지 않음")
    # 포크 실행에서는 workflow_run.pull_requests가 비어 있어 커밋 연결을 조회함
    return github.get(endpoint(f"commits/{sha}/pulls?per_page=100"))


def metadata(run, github):
    artifacts = github.get(endpoint(f"actions/runs/{positive(run['id'])}/artifacts"))["artifacts"]
    name = f"study-notification-{positive(run['run_attempt'])}"
    matches = [a for a in artifacts if a["name"] == name and not a["expired"]]
    if len(matches) != 1 or matches[0]["size_in_bytes"] > 16384:
        raise ValueError("이벤트 번호 파일이 없거나 크기가 올바르지 않음")
    raw = github.get(endpoint(f"actions/artifacts/{positive(matches[0]['id'])}/zip"), binary=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or entries[0].filename != "notification.json" or entries[0].file_size > 1024:
            raise ValueError("이벤트 번호 파일의 구성이 올바르지 않음")
        data = json.loads(archive.read(entries[0]))
    positive(data["pr"])
    if data.get("review") is not None:
        positive(data["review"])
    if data.get("review_comment") is not None:
        positive(data["review_comment"])
    return data


def near(value, run):
    if not value:
        return False
    at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    return abs((at - created).total_seconds()) <= 600


def relay_card(run, github):
    data = metadata(run, github)
    pr = github.get(endpoint(f"pulls/{data['pr']}"))
    associated = data["pr"] in {p["number"] for p in association(run, github)}
    # 닫힌 미머지 PR은 커밋 연결 목록에서 빠져 실행의 head를 직접 대조함
    matching_head = (run["head_sha"] == pr["head"]["sha"]
                     and run["head_branch"] == pr["head"]["ref"]
                     and run.get("head_repository", {}).get("full_name")
                     == (pr["head"].get("repo") or {}).get("full_name")
                     and bool(pr["head"].get("repo")))
    if not associated and not matching_head:
        return None
    if not development(pr, github):
        return None
    actor = run["actor"]["login"]
    url = f"{WEB}/pull/{pr['number']}"
    fields = [("작성자", pr["user"]["login"]), ("브랜치", pr["head"]["ref"])]
    action = data["action"]
    if run["event"] == "pull_request_review" and action == "submitted":
        review = github.get(endpoint(f"pulls/{pr['number']}/reviews/{positive(data['review'])}"))
        if (review["user"].get("type") == "Bot" or review["user"]["login"] != actor
                or not near(review["submitted_at"], run)):
            return None
        status = {"approved": "승인 의견", "changes_requested": "수정 요청",
                  "commented": "검토 의견"}.get(review["state"].lower())
        if not status:
            return None
        return card("💬 코드 리뷰가 도착했습니다", f"{plain(actor)}님이 {status}을 남겼습니다.", pr,
                    [("리뷰 상태", status), ("검토자", actor)],
                    [("리뷰 보기", f"{url}#pullrequestreview-{review['id']}"), ("PR 보기", url)],
                    "리뷰 의견과 PR 머지는 별도로 확인합니다.")
    if run["event"] == "pull_request_review_comment" and action == "created":
        comment = github.get(endpoint(f"pulls/comments/{positive(data['review_comment'])}"))
        if (not comment.get("in_reply_to_id") or comment["user"].get("type") == "Bot"
                or comment["user"]["login"] != actor or not near(comment["created_at"], run)
                or comment["pull_request_url"] != "https://api.github.com" + endpoint(f"pulls/{pr['number']}")):
            return None
        return card("💬 코드 리뷰에 답글이 달렸습니다", "리뷰 대화에서 답글을 확인해 주세요.", pr,
                    [("작성자", actor)],
                    [("답글 보기", f"{url}#discussion_r{positive(comment['id'])}"), ("PR 보기", url)])
    if run["event"] != "pull_request" or action not in {"opened", "closed", "reopened", "ready_for_review"}:
        return None
    if action == "opened":
        if actor != pr["user"]["login"] or not near(pr["created_at"], run):
            return None
        title = "📝 새 PR이 올라왔습니다"
        description = "초안 PR입니다. 준비를 마치면 검토를 요청해 주세요." if pr["draft"] else "변경 내용과 작성자의 설명을 확인해 주세요."
    else:
        event_name = {"closed": "closed", "reopened": "reopened", "ready_for_review": "ready_for_review"}[action]
        timeline = github.pages(endpoint(f"issues/{pr['number']}/timeline"))
        if not any(item.get("event") == event_name and near(item.get("created_at"), run)
                   and (item.get("actor") or {}).get("login") == actor for item in timeline):
            return None
        if action == "closed":
            title = "🎉 PR이 머지됐습니다" if pr["merged"] else "📁 PR이 닫혔습니다"
            description = "변경 내용이 공통 저장소에 반영됐습니다." if pr["merged"] else "머지 없이 닫힌 PR입니다."
        else:
            title = "🔎 PR 검토를 준비했습니다" if action == "ready_for_review" else "📝 PR이 다시 열렸습니다"
            description = "변경 내용과 남아 있는 피드백을 확인해 주세요."
    return card(title, description, pr, fields, [("PR 보기", url)])


def ci_card(run, github):
    if run["event"] != "pull_request" or run["conclusion"] in {"cancelled", "skipped", "neutral"}:
        return None
    if run["conclusion"] not in RESULTS:
        return None
    candidates = association(run, github)
    matching = [p for p in candidates if p["head"]["sha"] == run["head_sha"]]
    if len(matching) != 1:
        return None
    pr = github.get(endpoint(f"pulls/{matching[0]['number']}"))
    if pr["head"]["sha"] != run["head_sha"] or not development(pr, github):
        return None
    jobs = github.get(endpoint(f"actions/runs/{positive(run['id'])}/attempts/{positive(run['run_attempt'])}/jobs?per_page=100"))["jobs"]
    visible = [j for j in jobs if j["conclusion"] not in {"skipped", "cancelled"}]
    fields = [(j["name"], RESULTS.get(j["conclusion"], "확인 필요")) for j in visible[:8]]
    workflow = WORKFLOWS[run["path"].split("@")[0]]
    title = "✅ 검사가 끝났습니다" if run["conclusion"] == "success" else "⚠️ 검사 결과를 확인해 주세요"
    description = f"{workflow} · {RESULTS[run['conclusion']]}"
    return card(title, description, pr, fields,
                [("검사 결과", f"{WEB}/actions/runs/{run['id']}/attempts/{run['run_attempt']}"),
                 ("PR 보기", f"{WEB}/pull/{pr['number']}")],
                f"이번 실행 결과만 표시합니다. 전체 머지 조건은 PR에서 확인해 주세요. · 실행 {run['run_attempt']}회차")


def notification(event_name, event, github):
    if event.get("repository", {}).get("full_name") != REPO:
        return None
    if event_name == "workflow_dispatch":
        return card("🔔 스터디 알림 연결을 확인합니다",
                    "PR 등록·머지, CI 결과, 리뷰 소식을 이 채널에서 확인할 수 있습니다.",
                    fields=[("대상", "모델·프로그램 개발 PR"), ("알림 언어", "한국어")],
                    buttons=[("PR 목록 보기", f"{WEB}/pulls")],
                    footer="연결 확인용 메시지입니다. 실제 PR이나 검사 결과가 아닙니다.")
    if event_name == "issue_comment":
        if event.get("action") != "created" or not event["issue"].get("pull_request"):
            return None
        comment = event["comment"]
        if comment["user"]["type"] == "Bot":
            return None
        pr = github.get(endpoint(f"pulls/{positive(event['issue']['number'])}"))
        if not development(pr, github):
            return None
        return card("💬 PR에 새 댓글이 있습니다", "댓글을 열어 의견과 답변을 확인해 주세요.", pr,
                    [("작성자", comment["user"]["login"])],
                    [("댓글 보기", f"{WEB}/pull/{pr['number']}#issuecomment-{positive(comment['id'])}"),
                     ("PR 보기", f"{WEB}/pull/{pr['number']}")])
    if event_name != "workflow_run" or event.get("action") != "completed":
        return None
    # 전달받은 본문 대신 GitHub에 저장된 실행을 다시 조회함
    number = positive(event["workflow_run"]["id"])
    attempt = positive(event["workflow_run"]["run_attempt"])
    run = github.get(endpoint(f"actions/runs/{number}/attempts/{attempt}"))
    if run.get("run_attempt") != attempt:
        return None
    if run.get("repository", {}).get("full_name") != REPO or run["status"] != "completed":
        return None
    path = run["path"].split("@")[0]
    if path == RELAY and run["conclusion"] == "success":
        return relay_card(run, github)
    if path in WORKFLOWS:
        return ci_card(run, github)
    return None


def send(payload, webhook):
    if not re.fullmatch(r"https://hooks\.slack\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+", webhook):
        raise ValueError("Slack 웹훅 주소의 형식이 올바르지 않음")
    request = Request(webhook, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    if read_url(request, limit=128).strip() != b"ok":
        raise ValueError("Slack이 알림을 확인하지 못함")


def main():
    webhook = os.environ.get("SLACK_STUDY_WEBHOOK_URL", "")
    if not webhook:
        print("알림 보류: SLACK_STUDY_WEBHOOK_URL을 먼저 등록해 주세요.")
        return 0
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        payload = notification(os.environ["GITHUB_EVENT_NAME"], event, GitHub(os.environ["GH_TOKEN"]))
        if payload:
            send(payload, webhook)
            print("Slack 알림을 보냈습니다.")
        else:
            print("이번 이벤트는 알림 대상이 아닙니다.")
        return 0
    except (OSError, HTTPError, URLError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        # 예외 문자열에는 웹훅·인증값이 포함될 수 있어 남기지 않음
        print("Slack 알림을 보내지 못했습니다. 연결 설정과 실행 기록을 확인해 주세요.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
