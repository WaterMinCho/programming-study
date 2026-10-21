# -*- coding: utf-8 -*-
"""학습자 기록 submissions/<ID>/web/record.json 읽기·쓰기와 파생 상태.

기록은 덧붙이기만 함. 쓰기는 잠금 안에서 파일을 다시 읽고 한 줄 덧붙임(알고리즘 여행 progress.json 과 같은 방식).
미션의 받기 전·읽는 중·실전 중·끝남, 지금 단계, 단계가 열린 시각은 모두 기록의 시각에서 계산함. 그래서 프로그램을
껐다 켜도 시계가 이어 흐름. 시각 형식은 adaptive.now() 와 같은 ISO 초 단위임.
"""
import datetime
import json
import os
import threading

import adaptive
import study

NOTE_LIMIT = 500
MISSION_KINDS = ("receive", "live", "step", "check", "hint", "skip", "finish", "self", "after")


class RecordError(Exception):
    """기록 파일을 읽거나 쓰지 못함. 문구는 사용자에게 그대로 보여 줌."""


def parse_at(text):
    """기록 시각을 datetime 으로. 못 읽으면 None."""
    try:
        return datetime.datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None


def clip_note(text):
    text = (text or "").strip()
    return text[:NOTE_LIMIT]


class Record:
    def __init__(self, path, user, label="웹 면접 준비 기록(web/record.json)"):
        self.path = path
        self.user = user
        self.label = label
        self._lock = threading.RLock()
        self.log = []
        self.reload()

    def load(self):
        """파일 전체. 없으면 None, 깨졌으면 RecordError."""
        if not os.path.isfile(self.path):
            return None
        try:
            data = study.read_json(self.path)
            log = data["log"]
            if not isinstance(log, list) or not all(isinstance(e, dict) and "kind" in e for e in log):
                raise ValueError("log 항목의 형식이 맞지 않습니다")
        except json.JSONDecodeError as error:
            raise RecordError("%s 을 읽을 수 없습니다: %d번째 줄 %d번째 글자 근처의 JSON 형식이 맞지 않습니다."
                              % (self.label, error.lineno, error.colno))
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise RecordError("%s 을 읽을 수 없습니다: %s" % (self.label, error))
        return data

    def reload(self):
        with self._lock:
            self.log = (self.load() or {"log": []})["log"]
            return self.log

    def append(self, entry, at=None):
        """잠금 안에서 다시 읽고 한 줄 덧붙여 씀. 처음이면 파일을 만듦. 덧붙인 항목을 돌려줌."""
        with self._lock:
            data = self.load() or {"format": 1, "user": self.user, "created": at or adaptive.now(), "log": []}
            row = {"at": at or adaptive.now()}
            row.update(entry)
            if "note" in row:
                row["note"] = clip_note(row["note"])
            data["log"].append(row)
            try:
                study.write_text(self.path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
            except OSError as error:
                raise RecordError("%s 을 저장하지 못했습니다. 기록은 바뀌지 않았으니 잠시 뒤 다시 해 주세요.\n%s" % (self.label, error))
            self.log = data["log"]
            return row


# 파생 상태

def blank_mission():
    return {"try": 0, "phase": "none", "received_at": None, "live_at": None, "finished_at": None, "no_ai": None,
            "steps": {}, "current": None, "step_open_at": None, "hints": {}, "hint_count": 0, "skips": [],
            "last_check": None, "hidden": None, "self": None, "after": {}, "checks": 0}


def mission_states(log):
    """{미션 id: 상태}. 상태는 마지막 try 의 것임. phase 는 none(받기 전)·reading(읽는 중)·live(실전 중)·done(끝남).
    current 는 지금 열린 단계 번호(실전 전이나 끝난 뒤는 None), step_open_at 은 그 단계가 열린 시각."""
    found = {}
    for entry in log:
        kind, item = entry.get("kind"), entry.get("item")
        if kind not in MISSION_KINDS or not item:
            continue
        state = found.setdefault(item, blank_mission())
        try_no = int(entry.get("try") or 1)
        if kind == "receive":
            if try_no >= state["try"]:  # 새 try 는 앞 기록을 모두 버리고 읽는 중부터 시작함
                fresh = blank_mission()
                fresh.update({"try": try_no, "phase": "reading", "received_at": entry.get("at")})
                found[item] = fresh
            continue
        if try_no != state["try"] or state["phase"] == "none":
            continue
        at = entry.get("at")
        if kind == "live":
            state.update({"phase": "live", "live_at": at, "no_ai": entry.get("no_ai"), "current": 0, "step_open_at": at})
        elif kind in ("step", "skip"):
            step = int(entry.get("step") or 0)
            result = "skip" if kind == "skip" else str(entry.get("result") or "pass")
            state["steps"][step] = {"result": result, "at": at, "said": entry.get("said")}
            if kind == "skip":
                state["skips"].append(step)
            if state["phase"] == "live" and result in ("pass", "done", "skip") and step >= (state["current"] or 0):
                state["current"] = step + 1
                state["step_open_at"] = at
        elif kind == "hint":
            step = int(entry.get("step") or 0)
            state["hints"][step] = max(state["hints"].get(step, 0), int(entry.get("n") or 1))
            state["hint_count"] += 1
        elif kind == "check":
            state["last_check"] = entry
            state["checks"] += 1
        elif kind == "finish":
            state.update({"phase": "done", "finished_at": at, "hidden": entry.get("hidden"), "current": None})
        elif kind == "self":
            state["self"] = entry.get("ticks")
        elif kind == "after":
            state["after"][int(entry.get("step") or 0)] = entry
    return found


def chain_results(log):
    """{사슬 id: [{"at", "result"}]} (기록 순서)."""
    found = {}
    for entry in log:
        if entry.get("kind") == "chain" and entry.get("chain"):
            found.setdefault(str(entry["chain"]), []).append({"at": entry.get("at"), "result": str(entry.get("result") or "")})
    return found


def drill_answers(log, cid):
    """사슬 cid 의 drill 항목을 (마지막 chain 기록 앞의 것, 뒤의 것)으로 나눔. 뒤의 것이 지금 진행 중인 답임."""
    before, after = [], []
    for entry in log:
        if entry.get("chain") != cid:
            continue
        if entry.get("kind") == "chain":
            before.extend(after)
            after = []
        elif entry.get("kind") == "drill":
            after.append(entry)
    return before, after


def last_answers(log, cid):
    """사슬 cid 의 질문별 지난 답 {q: drill 항목} (가장 최근 완료 회차의 것). 아직 완료한 회차가 없으면 빈 dict."""
    before, _ = drill_answers(log, cid)
    out = {}
    for entry in before:
        out[int(entry.get("q") or 0)] = entry
    return out


def learned(log):
    """{페이지 id: 마지막으로 연 시각}."""
    found = {}
    for entry in log:
        if entry.get("kind") == "learn" and entry.get("page"):
            found[str(entry["page"])] = entry.get("at")
    return found


def talked_ratio(log):
    """막힌 질문에서 아는 데까지 말했다고 표시한 비율 (말함, 막힌 질문 수)."""
    stuck = [e for e in log if e.get("kind") == "drill" and e.get("talked") is not None]
    return sum(1 for e in stuck if e.get("talked")), len(stuck)


def activity_days(log):
    """check·drill 기록이 있는 날짜(YYYY-MM-DD) 집합. 공통 대시보드의 막대와 연속 학습일에 더함."""
    return {str(e.get("at") or "")[:10] for e in log if e.get("kind") in ("check", "drill") and e.get("at")}
