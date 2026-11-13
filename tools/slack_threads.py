# -*- coding: utf-8 -*-
"""한국 날짜별 상위 글을 기억하고 결과 카드를 그 스레드에 보냄."""
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request

from tools.slack_notify import endpoint, read_url

KST = timezone(timedelta(hours=9))
TS = re.compile(r"[0-9]{10,16}\.[0-9]{6}")
DECLINED = frozenset(("invalid_auth", "missing_scope", "not_in_channel", "channel_not_found", "is_archived", "rate_limited", "ratelimited"))


def korean_day(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("알림 시각의 시간대를 확인해 주세요.")
    return now.astimezone(KST).date().isoformat()


def post_message(payload, token, channel):
    request = Request("https://slack.com/api/chat.postMessage",
                      data=json.dumps({**payload, "channel": channel}, ensure_ascii=False).encode("utf-8"),
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=utf-8"},
                      method="POST")
    try:
        raw = read_url(request)
    except HTTPError as error:
        if error.code not in (400, 401, 403, 404, 405, 413, 414, 415, 422, 429):
            raise URLError("Slack 수신 여부를 확인하지 못했습니다.") from None
        raise
    except ValueError:
        raise URLError("Slack 응답을 확인하지 못했습니다.") from None
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise URLError("Slack 응답을 읽지 못했습니다.") from None
    if isinstance(result, dict) and result.get("ok") is False:
        if result.get("error") in DECLINED:
            raise ValueError("Slack이 메시지를 받지 못했습니다. 앱의 전송 권한과 채널 참여를 확인해 주세요.")
        raise URLError("Slack 메시지 처리 여부를 확인하지 못했습니다.")
    if (not isinstance(result, dict) or result.get("ok") is not True or result.get("channel") != channel
            or not isinstance(result.get("ts"), str) or not TS.fullmatch(result["ts"])):
        raise URLError("Slack 수신 확인 번호를 확인하지 못했습니다.")
    return result["ts"]


class DailyThreads:
    def __init__(self, github, token, channel, anchor, *, topic="pr"):
        if (not re.fullmatch(r"xoxb-[A-Za-z0-9-]+", token or "")
                or not re.fullmatch(r"[CG][A-Z0-9]{8,}", channel or "")
                or not re.fullmatch(r"[0-9a-f]{40}", anchor or "")):
            raise ValueError("일별 Slack 알림의 봇·채널·저장 위치를 확인해 주세요.")
        if topic not in ("pr", "server"):
            raise ValueError("Slack 스레드 종류를 확인해 주세요.")
        self.topic = topic
        self.github, self.token, self.channel, self.anchor = github, token, channel, anchor

    def parent(self, day):
        channel_key = hashlib.sha256(self.channel.encode()).hexdigest()[:12]
        if self.topic == "server":
            context = f"서버 모니터링 스레드/{day}/{channel_key}"
            title = f"*금일 서버 상태 모니터링* · {day}  |  <https://rokey-study.betteruptime.com|서버 상태>"
        else:
            context = f"스터디 PR 스레드/{day}/{channel_key}"
            title = day + " 오늘의 PR"
        location = endpoint("statuses/" + self.anchor)
        midnight = datetime.combine(datetime.fromisoformat(day).date(), time.min, KST)
        for row in self.github.pages(endpoint("commits/%s/statuses" % self.anchor)):
            if row.get("context") == context:
                description = row.get("description", "")
                if description.startswith("ready:") and TS.fullmatch(description[6:]):
                    return description[6:]
                if description == "creating":
                    raise URLError("오늘의 상위 글이 Slack에 도착했는지 확인해 주세요.")
                if description == "failed":
                    break
                raise ValueError("일별 Slack 글의 저장 기록을 확인해 주세요.")
            created = row.get("created_at")
            if created and datetime.fromisoformat(created.replace("Z", "+00:00")) < midnight:
                break
        self.github.post(location, {"state": "success", "context": context, "description": "creating"})
        try:
            ts = post_message({"text": title, "unfurl_links": False, "unfurl_media": False},
                              self.token, self.channel)
        except (HTTPError, ValueError):
            self.github.post(location, {"state": "success", "context": context, "description": "failed"})
            raise
        self.github.post(location, {"state": "success", "context": context, "description": "ready:" + ts})
        return ts

    def send(self, payload):
        ts = self.parent(korean_day())
        post_message({**payload, "thread_ts": ts, "reply_broadcast": False}, self.token, self.channel)
