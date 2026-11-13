"""허용한 모니터의 장애·복구를 스터디 채널에 한 번씩 알림."""
import hashlib
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from tools.slack_notify import endpoint, read_url, send
from tools.slack_summary import Client

API = "https://incidents.betterstack.com/api/v3/incidents"
LABELS = {"health": "수집 서버", "internal": "운영 점검", "test": "연결 테스트"}


def events(resources, token):
    notices = []
    for key, resource in resources.items():
        kind, identifier = resource.split(":")
        if key not in LABELS or kind not in ("monitor", "heartbeat") or not identifier.isdecimal():
            raise ValueError("모니터 목록을 확인해 주세요.")
        page = 1
        while True:
            query = urlencode({kind + "_id": identifier, "per_page": 50, "page": page})
            request = Request(API + "?" + query, headers={"Authorization": "Bearer " + token})
            data = json.loads(read_url(request))
            for row in data["data"]:
                for field in ("started_at", "resolved_at"):
                    when = row["attributes"].get(field)
                    if when:
                        notices.append((when, row["id"], field, key))
            if not data["pagination"]["next"]:
                break
            page += 1
    return sorted(notices)


def relay(github, anchor, notices, webhook):
    if not notices:
        return
    if not re.fullmatch(r"[0-9a-f]{40}", anchor):
        raise ValueError("알림 수신 기록을 저장할 커밋을 확인해 주세요.")
    latest = {}
    for row in github.pages(endpoint(f"commits/{anchor}/statuses")):
        latest.setdefault(row["context"], row["description"])
    for _, identifier, field, key in notices:
        digest = hashlib.sha256(f"{identifier}/{field}".encode()).hexdigest()[:32]
        context = "server-alert/" + digest
        if latest.get(context) == "sent":
            continue
        if latest.get(context) == "sending":
            raise RuntimeError("수신 여부가 불분명합니다. 채널과 전송 기록을 대조해 주세요.")
        status = {"context": context, "state": "success", "description": "sending"}
        location = endpoint("statuses/" + anchor)
        github.post(location, status)
        text = "🔴 장애 감지" if field == "started_at" else "🟢 복구"
        try:
            send({"text": f"{text} · ROKEY {LABELS[key]}"}, webhook)
        except HTTPError as error:
            if error.code in (400, 403, 404, 410, 429):
                github.post(location, {**status, "description": "retry"})
            raise
        github.post(location, {**status, "description": "sent"})
        latest[context] = "sent"


def main():
    resources = json.loads(os.environ["ROKEY_INCIDENT_RESOURCES"])
    relay(Client(os.environ["GH_TOKEN"]), os.environ["SLACK_STUDY_THREAD_ANCHOR"],
          events(resources, os.environ["BETTER_STACK_INCIDENTS_READ_TOKEN"]),
          os.environ["SLACK_STUDY_WEBHOOK_URL"])


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, ValueError, KeyError, RuntimeError) as error:
        # 웹훅 주소와 서버 응답 본문은 로그에서 제외함.
        raise SystemExit(f"서버 알림 전달 실패 ({type(error).__name__})") from None
