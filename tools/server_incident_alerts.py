"""모니터 사건별 복구 결과를 한국 날짜의 서버 스레드에 한 번만 보냄."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from tools.slack_notify import WEB, endpoint, read_url
from tools.slack_summary import Client
from tools.slack_threads import DailyThreads, korean_day

API = "https://incidents.betterstack.com/api/v3/incidents"
NUMBER = re.compile(r"[1-9][0-9]{0,19}")
RUN_URL = re.compile(re.escape(WEB + "/actions/runs/") + NUMBER.pattern)
WAIT = timedelta(minutes=10)
BOT = "github-actions[bot]"
OWNER = "WaterMinCho"
BASELINE = "rokey-incident-cutover"
RESULTS = {
    "reload_verified": "앱을 다시 불러온 뒤 서버의 정상 응답을 확인했습니다.",
    "already_up": "복구 작업 전에 서버가 이미 정상 응답했습니다.",
    "reload_still_down": "앱을 다시 불러온 뒤에도 서버가 오류를 반환했습니다.",
    "reload_unconfirmed": "앱 다시 불러오기를 시도했지만 정상 응답을 확인하지 못했습니다.",
    "provider_unavailable": "서버 상태나 호스팅 진단 정보를 조회하지 못해 복구 작업을 보류했습니다.",
    "unsafe_cause": "안전하게 앱을 다시 불러올 조건을 확인하지 못해 작업을 보류했습니다.",
    "cooldown": "최근에 복구 작업을 시도해 앱을 다시 불러오지 않았습니다.",
}


def timestamp(value):
    at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if at.utcoffset() is None:
        raise ValueError("시각의 시간대를 확인해 주세요.")
    return at


@dataclass(frozen=True)
class Incident:
    identifier: str
    monitor: str
    resolved_at: datetime = None


def events(resources, token):
    incidents = {}
    if len(set(resources.values())) != len(resources):
        raise ValueError("운영·테스트 모니터 번호를 구분해 주세요.")
    for key, resource in resources.items():
        kind, identifier = resource.split(":")
        if key not in ("health", "test") or kind != "monitor" or not NUMBER.fullmatch(identifier):
            raise ValueError("모니터 목록을 확인해 주세요.")
        page = 1
        while True:
            query = urlencode({"monitor_id": identifier, "per_page": 50, "page": page})
            request = Request(API + "?" + query, headers={"Authorization": "Bearer " + token})
            data = json.loads(read_url(request))
            for row in data["data"]:
                relationships = row.get("relationships") or {}
                if relationships:
                    monitor = (relationships.get("monitor") or {}).get("data") or {}
                    if monitor.get("type") != "monitor" or monitor.get("id") != identifier:
                        continue
                if row["type"] != "incident" or not NUMBER.fullmatch(row["id"]):
                    continue
                attributes = row["attributes"]
                if not attributes.get("started_at"):
                    continue
                resolved = attributes.get("resolved_at")
                incident = Incident(row["id"], key, timestamp(resolved) if resolved else None)
                previous = incidents.get(incident.identifier)
                if previous and previous.monitor != key:
                    raise ValueError("같은 사건이 서로 다른 모니터에서 조회됐습니다.")
                if not previous or incident.resolved_at:
                    incidents[incident.identifier] = incident
            if not data["pagination"]["next"]:
                break
            page += 1
    return incidents.values()


def trusted_statuses(github, anchors):
    """현재 앵커부터 이전 앵커 순서로 작성자를 확인한 최신 상태를 읽음."""
    latest = {}
    for anchor in anchors:
        if not re.fullmatch(r"[0-9a-f]{40}", anchor):
            raise ValueError("상태 기록을 저장할 커밋을 확인해 주세요.")
        page = 1
        while True:
            rows = github.get(endpoint(f"commits/{anchor}/statuses?per_page=100&page={page}"))
            for row in rows:
                context = row["context"]
                result = context.startswith("rokey-recovery-result/")
                if not (result or context == BASELINE or context.startswith((
                        "rokey-recovery/", "rokey-incident/", "server-alert/"))):
                    continue
                creator = row.get("creator") or {}
                author = (creator.get("login"), creator.get("type"))
                reconcile = context.startswith("rokey-incident/") and row.get("description") in ("sent", "retry")
                if ((author == (OWNER, "User") and (result or reconcile))
                        or (author == (BOT, "Bot") and not result)):
                    latest.setdefault(context, {**row, "anchor": anchor})
            if len(rows) < 100:
                break
            page += 1
    return latest


def worker_result(request, result):
    if not result or result.get("state") != "success" or result.get("description") not in RESULTS:
        return None
    if (result["anchor"] == request["anchor"] and result.get("target_url") == request["target_url"]
            and timestamp(result["created_at"]) >= timestamp(request["created_at"])):
        return result["description"]
    return None


def legacy_resolution(identifier):
    digest = hashlib.sha256(f"{identifier}/resolved_at".encode()).hexdigest()[:32]
    return "server-alert/" + digest


def relay(github, anchor, incidents, send, *, run_id, cutover=None, previous_anchors=(), now=None):
    if not NUMBER.fullmatch(run_id):
        raise ValueError("Actions 실행 번호를 확인해 주세요.")
    now = now or datetime.now(timezone.utc)
    latest = trusted_statuses(github, (anchor, *previous_anchors))
    location = endpoint("statuses/" + anchor)
    if cutover is None:
        baseline = latest.get(BASELINE)
        if baseline is None:
            baseline = github.post(location, {"context": BASELINE, "state": "success", "description": "enabled"})
        cutover = timestamp(baseline["created_at"]) - WAIT
    uncertain = []
    for incident in incidents:
        identifier = incident.identifier
        context = "rokey-incident/" + identifier
        delivery = latest.get(context, {}).get("description")
        legacy = latest.get(legacy_resolution(identifier), {}).get("description")
        if delivery == "sent" or legacy == "sent":
            continue
        if delivery not in (None, "observed", "retry") or (legacy == "sending" and delivery != "retry"):
            uncertain.append(identifier)
            continue
        request_context = "rokey-recovery/" + identifier
        request = latest.get(request_context)
        status = {"context": context, "state": "success"}
        resolved = incident.resolved_at
        if resolved and resolved < cutover and not (delivery or request):
            continue

        reason = None
        if incident.monitor == "health":
            if request:
                if (request.get("description") != "requested" or request.get("state") != "pending"
                        or not RUN_URL.fullmatch(request.get("target_url") or "")):
                    raise ValueError("복구 요청 기록을 확인해 주세요.")
                reason = worker_result(request, latest.get("rokey-recovery-result/" + identifier))
            elif not resolved:
                github.post(location, {"context": request_context, "state": "pending",
                                       "description": "requested", "target_url": f"{WEB}/actions/runs/{run_id}"})
                continue
            if request and now < timestamp(request["created_at"]) + WAIT:
                if not reason or (not resolved and reason not in ("reload_verified", "already_up")):
                    continue
            message = RESULTS.get(reason, "")
            if resolved:
                message = message or "확인된 자동 복구 작업 기록은 없습니다."
                message += " Better Stack에서 장애가 해결된 것을 확인했습니다."
            elif not message:
                message = "복구 요청 후 10분 동안 작업 결과와 모니터의 복구 기록을 확인하지 못했습니다."
            title = "수집 서버 장애"
        else:
            title = "연결 테스트"
            if resolved:
                message = "Better Stack에서 테스트 모니터의 장애가 해결된 것을 확인했습니다."
            elif not delivery:
                github.post(location, {**status, "description": "observed"})
                continue
            elif delivery == "observed" and now < timestamp(latest[context]["created_at"]) + WAIT:
                continue
            else:
                message = "첫 확인 후 10분 동안 테스트 모니터에 복구 기록이 없었습니다."

        github.post(location, {**status, "description": "sending"})
        try:
            send({"text": f"{title} #{identifier} · {message}"})
        except (HTTPError, ValueError):
            # Slack이 명시적으로 거절한 전송만 다시 시도함.
            github.post(location, {**status, "description": "retry"})
            raise
        github.post(location, {**status, "description": "sent"})
        latest[context] = {**status, "description": "sent"}
    if uncertain:
        raise RuntimeError("Slack 수신 확인이 필요한 사건: " + ", ".join(uncertain))


def main():
    env = os.environ
    github = Client(env["GH_TOKEN"])
    anchor = env["SLACK_STUDY_THREAD_ANCHOR"]
    threader = DailyThreads(github, env["SLACK_STUDY_BOT_TOKEN"], env["SLACK_STUDY_CHANNEL_ID"], anchor, topic="server")
    threader.parent(korean_day())
    cutover = env.get("ROKEY_INCIDENT_CUTOVER_AT")
    previous = (env.get("ROKEY_INCIDENT_PREVIOUS_ANCHORS") or "").split()
    incidents = events(json.loads(env["ROKEY_INCIDENT_RESOURCES"]), env["BETTER_STACK_INCIDENTS_READ_TOKEN"])
    relay(github, anchor, incidents, threader.send, run_id=env["GITHUB_RUN_ID"],
          cutover=timestamp(cutover) if cutover else None, previous_anchors=previous)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    except (HTTPError, URLError, OSError, ValueError, KeyError) as error:
        # 주소·인증값·서버 응답 본문을 로그에서 제외함.
        raise SystemExit(f"서버 알림 전달 실패 ({type(error).__name__})") from None
