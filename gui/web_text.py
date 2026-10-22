# -*- coding: utf-8 -*-
"""웹 면접 준비 화면과 첫 화면이 같이 쓰는 글자 도우미. 서비스의 overview() 값을 화면 낱말로 바꿈.

낱말은 정해 둔 것만 씀: 시작 전, 진행 중, 끝남, 준비 중. 내부 ID(w03, 3-A, l03, 상자 1)는 화면에 쓰지 않음."""
import datetime
import math

from webprep import service

WEEKDAYS = "월화수목금토일"
ACTIONS = {"mission": "미션 시작", "chain": "복습 시작", "page": "노트 읽기", "topic": "사슬 풀기"}  # 이어서 할 일 카드의 단추 글자


def clock_text(seconds):
    """초를 m:ss 로. 음수는 0:00."""
    seconds = max(0, int(seconds or 0))
    return "%d:%02d" % divmod(seconds, 60)


def minutes_left(seconds):
    """남은 초를 '34분 남음' 으로. 1분 미만은 '1분 남음', 0 이하는 '시간 지남'."""
    seconds = int(seconds or 0)
    if seconds <= 0:
        return "시간 지남"
    return "%d분 남음" % max(1, math.ceil(seconds / 60))


def minutes_text(seconds):
    """걸린 시간을 문장 안에 쓰는 꼴로. 90 → '1분 30초', 120 → '2분', 40 → '40초'."""
    minutes, rest = divmod(max(0, int(seconds or 0)), 60)
    return " ".join(part for part in ("%d분" % minutes if minutes else "", "%d초" % rest if rest or not minutes else "") if part)


def day_text(iso):
    """2026-10-24 를 10/24 로. 못 읽으면 그대로."""
    try:
        _, month, day = (int(n) for n in str(iso)[:10].split("-"))
    except ValueError:
        return str(iso or "")
    return "%d/%d" % (month, day)


def date_text(iso):
    """2026-10-24 를 '10월 24일(토)' 로. 못 읽으면 그대로."""
    try:
        day = datetime.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso or "")
    return "%d월 %d일(%s)" % (day.month, day.day, WEEKDAYS[day.weekday()])


def ordinal(n):
    """1 → 첫 번째, 2 → 두 번째."""
    words = {1: "첫", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열"}
    return "%s 번째" % words.get(n, "%d" % n)


def mission_state(row):
    """overview()["missions"] 의 한 줄을 상태 글자로. 읽는 중은 남은 읽기 시간, 실전 중은 단계와 남은 시간, 끝남은 통과한 단계 수."""
    if not row["ready"]:
        return "읽을 수 없음" if row["error"] else "준비 중"
    timers = row.get("timers") or {}
    phase = row["phase"]
    if phase == "reading":
        left = timers.get("reading_left")
        return "진행 중 · 읽기 %s" % minutes_left(left) if (left or 0) > 0 else "진행 중 · 읽기 시간 끝"
    if phase == "live":
        left = row["live_min"] * 60 - (timers.get("live_elapsed") or 0)
        return "진행 중 · %d단계 · %s" % (row["current"] or 0, minutes_left(left) if left > 0 else "%d분 넘김" % max(1, math.ceil(-left / 60)))
    if phase == "done":
        return "끝남 · %d단계 중 %d단계 통과" % (max(0, row["total_steps"] - 1), row["done_steps"])
    return "시작 전"


def mission_line(row, prep_min=None):
    """목록 줄의 둘째 줄. 시작 전이면 읽기·실전 시간을 붙임."""
    text = mission_state(row)
    if row["ready"] and row["phase"] == "none" and prep_min is not None:
        text += " · 읽기 %d분, 실전 %d분" % (prep_min, row["live_min"])
    return text


def chain_line(chain, today_ids=()):
    """사슬 줄의 둘째 줄. 복습 상자 번호는 쓰지 않고 날짜로 말함."""
    if chain.get("box") is None:
        return "시작 전"
    if chain["id"] in today_ids:
        return "오늘 복습"
    return "끝남 · 다음 복습 %s" % day_text(chain.get("due"))


def next_item(overview, missions=None):
    """이어서 할 일 카드에 보일 것. {"title", "line", "action", "kind", "id"} 또는 None.
    missions 는 서비스의 미션 사전(읽기 시간을 적을 때)."""
    target = overview.get("next")
    if not target:
        return None
    kind, iid = target["kind"], target["id"]
    item = {"kind": kind, "id": iid, "title": target["title"], "action": ACTIONS.get(kind, "열기"), "line": ""}
    if kind == "mission":
        row = next((m for m in overview.get("missions", []) if m["id"] == iid), None)
        if row is not None and row["phase"] in ("reading", "live"):
            item["action"] = "이어 하기"
            item["line"] = "라이브 코딩 미션 · " + mission_state(row).replace("진행 중 · ", "")
        elif row is not None:
            prep = (missions or {}).get(iid, {}).get("prep_min")
            item["line"] = "라이브 코딩 미션 · %s" % mission_line(row, prep).replace("시작 전 · ", "")
    elif kind == "chain":
        times = next((c["times"] for t in overview.get("topics", []) for c in t["chains"] if c["id"] == iid), None)  # 웹 홈 줄과 같은 차수
        item["line"] = "꼬리 질문 복습" + (" · %s 복습" % ordinal(times + 1) if times is not None else "")
    elif kind == "page":
        item["line"] = "학습 노트"
    elif kind == "topic":
        item["title"] = target.get("chain_title") or target["title"]
        item["line"] = "꼬리 질문 · %s" % target["title"]
        item["id"] = target.get("chain") or iid
    return item


def stack_status(stack):
    """위 막대의 검사 도구 상태: (점 상태, 글). 설치됐으면 ready, 아니면 todo."""
    if not stack.get("node"):
        return "todo", "Node.js 없음"
    if stack.get("installed"):
        return ("todo", "검사 도구 다시 설치 필요") if stack.get("stale") else ("ready", "검사 도구 준비됨")
    return "todo", "검사 도구 설치 전"


def result_tone(result):
    """질문·검사 판정의 꼬리표 색."""
    return {"pass": "success", "done": "success", "partial": "warning", "skip": "warning", "stuck": "danger"}.get(result, "")


def result_label(result):
    return service.RESULT_LABEL.get(result, result)
