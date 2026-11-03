# -*- coding: utf-8 -*-
"""오늘 목표와 다음 할 일(설계 1.4, 2.2, 2.5). 날짜는 모두 학습일(review.study_day)이고 함수는 기록을 직접 읽지 않음.
서비스가 기록에서 센 값을 넘기면 목표 단원 수, 오늘 틀리고 남은 카드, NextCard 한 줄, 다시 볼 단원을 돌려줌."""
import datetime
import math

REVIEW_FIRST = 40
BACKLOG_HALF = 150
NEW_PER_DAY = 35
ONE_DAY = datetime.timedelta(days=1)


def days_left(exam, today):
    """시험까지 남은 날. 시험 날짜가 없으면 None."""
    if not exam.get("date"):
        return None
    return (exam["date"] - today).days


def units_target(planned_total, read_before, published_unread, today, exam, backlog=0):
    """오늘 목표 단원 수. min(공개된 안 읽은 단원, ceil(계획한 안 읽은 단원 ÷ (last_new 까지 남은 날 + 1))).
    read_before·published_unread 는 오늘이 시작될 때의 값이라 하루 안에서는 목표가 바뀌지 않음. last_new 뒤에는 0,
    그날 첫 화면의 밀린 복습(backlog)이 BACKLOG_HALF 를 넘으면 절반(올림)."""
    last_new = exam.get("last_new")
    if last_new is None or today > last_new:
        return 0
    days = (last_new - today).days + 1
    left = max(0, planned_total - read_before)
    target = min(max(0, published_unread), int(math.ceil(left / float(days))))
    if backlog > BACKLOG_HALF:
        target = int(math.ceil(target / 2.0))
    return target


def again_cards(events, today):
    """오늘 틀리고 아직 두 번 이어 맞히지 못한 카드(처음 틀린 시각 순). events 는 review.card_events 결과.
    틀림·일부 맞음·[모르겠어요]가 모두 틀림이고, 마지막으로 틀린 뒤 pass 가 둘 이어지면 빠짐."""
    rows = []
    for cid, items in events.items():
        mine = [e for e in items if e["src"] == "answer" and e["day"] == today]
        first_fail, streak, pending = None, 0, False
        for event in mine:
            if event["result"] == "pass":
                streak += 1
                if streak >= 2:
                    pending = False
            else:
                first_fail = first_fail or event["at"]
                pending, streak = True, 0
        if pending:
            rows.append((first_fail, cid))
    return [cid for _, cid in sorted(rows)]


def pick_unit(units, today):
    """다음에 읽을 단원. units 는 안 읽은 공개 단원 [{"lesson", "no", "date"(date 또는 None), "unit", "order"}].
    어제나 오늘 수업한 차시의 단원 먼저, 그다음 차시 순, 단원 순."""
    if not units:
        return None

    def key(row):
        recent = row.get("date") is not None and today - ONE_DAY <= row["date"] <= today
        return (0 if recent else 1, row["no"], row["order"])
    return sorted(units, key=key)[0]


def pick_revisit(units, seen_today=()):
    """다시 볼 단원. units 는 읽은 단원 [{"lesson", "unit", "core_box"(핵심 카드 평균 상자), "read"(읽은 날)}].
    평균 상자가 가장 낮고 같으면 오래전에 읽은 단원. 오늘 이미 다시 본 단원은 뺌."""
    rows = [u for u in units if (u["lesson"], u["unit"]) not in set(seen_today)]
    if not rows:
        return None
    return sorted(rows, key=lambda u: (u["core_box"], u["read"] or datetime.date.min, u["lesson"], u["unit"]))[0]


def _md(day):
    return "%d월 %d일" % (day.month, day.day)


def next_card(ctx):
    """홈 NextCard 한 줄(설계 2.2 표). ctx 는 서비스가 센 값:
    today, exam, again(카드 목록), mock({"id", "title", "count", "minutes", "until"} 또는 None), due(날짜가 된 복습 수,
    12-01 에는 줄인 수), target·read_today(오늘 목표와 읽은 단원, target 이 None 이면 목표 없이 안 읽은 단원을 권함),
    unit(pick_unit 결과에 title·minutes),
    revisit(pick_revisit 결과에 title·no). 돌려주는 값 {"kind", "lesson", "unit", "mock", "title", "count", "why"}."""
    today, exam = ctx["today"], ctx["exam"]
    last_day = exam.get("last_review") is not None and today == exam["last_review"]
    out = {"kind": "none", "lesson": None, "unit": None, "mock": None, "title": "", "count": 0, "why": ""}
    again = ctx.get("again") or []
    if again:
        out.update(kind="again", count=len(again), title="오늘 틀린 문항 %d개가 남았습니다" % len(again),
                   why="두 번 이어 맞히면 오늘 복습에서 빠집니다.")
        return out
    mock = ctx.get("mock")
    if mock and not last_day:
        until = mock.get("until")
        out.update(kind="mock", mock=mock["id"], count=mock.get("count", 30),
                   title="%s · %d문항 · %d분" % (mock["title"], mock.get("count", 30), mock.get("minutes", 60)),
                   why=("%s까지 한 번 풀어 보세요. 시작하면 시계가 멈추지 않습니다." % _md(until)) if until
                   else "시작하면 시계가 멈추지 않습니다.")
        return out
    due = ctx.get("due") or 0
    if due >= REVIEW_FIRST:
        out.update(kind="review", count=due, title="복습 %d문항" % due, why="복습을 먼저 하면 새 단원이 밀리지 않습니다.")
        return out
    unit = ctx.get("unit")
    target = ctx.get("target")
    if unit and not last_day and (target is None or (ctx.get("read_today") or 0) < target):
        when = unit.get("date")
        head = ""
        if when == today:
            head = "오늘 수업한 차시입니다. "
        elif when == today - ONE_DAY:
            head = "어제 수업한 차시입니다. "
        out.update(kind="unit", lesson=unit["lesson"], unit=unit["unit"],
                   title="%d차시 · %s" % (unit["no"], unit.get("title", "")),
                   why="%s읽은 뒤 이 단원 문항과 복습을 함께 풉니다. 약 %d분." % (head, unit.get("minutes") or 5))
        return out
    if due > 0:
        out.update(kind="review", count=due, title="복습 %d문항" % due, why="오늘 날짜가 된 문항입니다.")
        return out
    revisit = ctx.get("revisit")
    if revisit:
        out.update(kind="revisit", lesson=revisit["lesson"], unit=revisit["unit"],
                   title="다시 보기 · %d차시 %s" % (revisit.get("no", 0), revisit.get("title", "")),
                   why="외운 것을 떠올린 뒤 섞어 풉니다.")
        return out
    if unit and not last_day:
        out.update(kind="unit", lesson=unit["lesson"], unit=unit["unit"],
                   title="%d차시 · %s" % (unit["no"], unit.get("title", "")),
                   why="읽은 뒤 이 단원 문항과 복습을 함께 풉니다. 약 %d분." % (unit.get("minutes") or 5))
        return out
    out.update(title="아직 공개된 단원이 없습니다", why="새 차시가 올라오면 여기에 나옵니다.")
    return out


def pending_mock(mocks, ready, taken, today, exam):
    """권장 기간 안이고 아직 풀지 않은 모의고사. mocks 는 index.json 의 목록, ready·taken 은 출제된·푼 회차 id 집합."""
    if exam.get("last_review") is not None and today >= exam["last_review"]:
        return None
    for mock in mocks:
        window = [w for w in mock.get("window") or []]
        if len(window) != 2 or mock["id"] not in ready or mock["id"] in taken:
            continue
        start, end = (datetime.date.fromisoformat(w) for w in window)
        if start <= today <= end:
            return dict(mock, until=end)
    return None


def lesson_state(read, total, core_marks):
    """차시 줄 점 상태. 핵심 카드 90% 이상이 상자 4 이상이면 mastered, 단원을 다 읽었으면 level2, 하나라도 읽었으면
    level1, 아니면 none. core_marks 는 핵심 카드마다 외웠는지(bool) 목록."""
    if core_marks and sum(1 for m in core_marks if m) >= 0.9 * len(core_marks):
        return "mastered"
    if total and read >= total:
        return "level2"
    if read:
        return "level1"
    return "none"
