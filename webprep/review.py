# -*- coding: utf-8 -*-
"""복습 상자와 다음 복습 날짜(설계 2.5). 상자 1~5 의 간격 반복(라이트너 방식)임.

상자는 record.json 의 chain 기록에서 계산하고 따로 저장하지 않음. 처음 푼 사슬은 통과면 상자 2, 부분이나 막힘이면
상자 1. 그 뒤로는 통과면 한 상자 올림(5에서 멈춤), 부분이면 머묾, 막힘이면 상자 1. 다음 복습 날짜는 푼 날짜에 간격을
더한 날(로컬 자정 기준). 넘어간 단계가 있거나 실전 시간을 10분 넘게 넘긴 미션은 7일 뒤 "다시 해 볼 미션"으로 한 번 나옴.
"""
import datetime

from webprep import record

INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
TOP_BOX = 5
NEW_PER_DAY = 2
RETRY_DAYS = 7
OVER_MIN = 10
RESULTS = ("pass", "partial", "stuck")


def question_result(need_marks, gave_up=False):
    """질문 판정. need_marks 는 [필수] 항목마다 0/1. 모두 표시하면 pass, 일부면 partial, 없거나 모르겠으면 stuck."""
    if gave_up or not any(need_marks):
        return "stuck"
    return "pass" if all(need_marks) else "partial"


def chain_result(question_results):
    """사슬 판정. 모두 통과면 pass, 막힘이 하나라도 있으면 stuck, 그 밖은 partial."""
    if not question_results:
        return "stuck"
    if all(r == "pass" for r in question_results):
        return "pass"
    if any(r == "stuck" for r in question_results):
        return "stuck"
    return "partial"


def next_box(box, result):
    """지금 상자(처음이면 None)와 이번 결과로 다음 상자를."""
    if box is None:
        return 2 if result == "pass" else 1
    if result == "pass":
        return min(TOP_BOX, box + 1)
    if result == "stuck":
        return 1
    return box


def _day(at):
    when = record.parse_at(at)
    return when.date() if when else None


def schedule(results):
    """사슬의 chain 기록 목록 [{"at", "result"}] 에서 {"box", "last", "due", "times"} 를. 기록이 없으면 None."""
    box, last = None, None
    for item in results:
        box = next_box(box, item.get("result"))
        last = _day(item.get("at")) or last
    if box is None or last is None:
        return None
    return {"box": box, "last": last, "due": last + datetime.timedelta(days=INTERVAL_DAYS[box]), "times": len(results)}


def due_list(schedules, new_order, today, new_per_day=NEW_PER_DAY):
    """오늘 복습 목록. schedules 는 {사슬 id: schedule()}, new_order 는 아직 안 푼 사슬의 권장 순서.
    복습 날짜가 오늘이거나 지난 사슬(오래된 순) 뒤에 새 사슬을 new_per_day 개까지 더함."""
    due = [(plan["due"], cid) for cid, plan in schedules.items() if plan and plan["due"] <= today]
    rows = [{"chain": cid, "box": schedules[cid]["box"], "due": when, "new": False} for when, cid in sorted(due)]
    fresh = [cid for cid in new_order if cid not in schedules][:max(0, new_per_day)]
    rows += [{"chain": cid, "box": None, "due": None, "new": True} for cid in fresh]
    return rows


def retry_missions(states, metas, today):
    """다시 해 볼 미션. 넘어간 단계가 있거나 실전 시간을 OVER_MIN 분 넘게 넘긴 채 끝난 미션이 끝난 날로부터 7일 되는
    날 한 번 나옴. 그 뒤 새 try 를 받으면 사라짐."""
    rows = []
    for mid, state in states.items():
        meta = metas.get(mid)
        if not meta or state["phase"] != "done" or not state["finished_at"]:
            continue
        over = 0.0
        live, done = record.parse_at(state["live_at"]), record.parse_at(state["finished_at"])
        if live and done:
            over = (done - live).total_seconds() / 60.0 - meta["live_min"]
        if not state["skips"] and over <= OVER_MIN:
            continue
        when = _day(state["finished_at"]) + datetime.timedelta(days=RETRY_DAYS)
        if when == today:
            rows.append({"mission": mid, "title": meta["title"], "why": "넘어간 단계가 있습니다" if state["skips"]
                         else "실전 시간을 %d분 넘겼습니다" % round(over)})
    return rows
