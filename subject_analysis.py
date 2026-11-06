# -*- coding: utf-8 -*-
"""제출된 네 과목의 기록을 읽어 공개할 수 있는 집계만 돌려줌.

collect_user(user, python_catalog=None)와 collect_team(python_catalog=None)이 진입점임.
value는 기록에서 센 정수이고 total은 definition에 적은 분모임. 횟수처럼 분모가 없는 값의 total은 None임.
source=submitted는 제출 파일만 읽고 from_overviews의 source=service는 호출자가 읽은 서비스 값을 받음.
no_record는 제출본에 집계할 기록이 없다는 상태임. 실제 학습 시작 여부를 추정하지 않음.
unavailable은 기록이나 목록을 확인하지 못한 상태임. 두 상태에는 숫자를 넣지 않음.
원시 답·풀이·메모·로컬 경력 기록을 반환하지 않음.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime
import os
import stat
from typing import Literal

import adaptive
import study
from aiprep import review as ai_review
from aiprep.service import AiSession
from journey.service import JourneySession
from webprep import bank as web_bank, record as web_record, review as web_review

SUBJECTS = (("python", "파이썬 스터디"), ("journey", "알고리즘 여행"),
            ("web", "웹 면접 준비"), ("ai", "AI 비전 개론"))
STATUS_LABELS = {"available": "제출 기록 있음", "no_record": "제출 기록 없음", "unavailable": "확인 불가"}
SOURCE_LABELS = {"submitted": "제출된 파일", "service": "이 기기 서비스"}


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    value: int
    total: int | None
    unit: str
    definition: str
    group: Literal["coverage", "activity"] = "activity"
    total_label: str = "공개 항목"


@dataclass(frozen=True)
class NextAction:
    kind: str
    target: str
    text: str


@dataclass(frozen=True)
class SubjectSummary:
    key: str
    title: str
    status: Literal["available", "no_record", "unavailable"]
    metrics: tuple[Metric, ...]
    next_action: NextAction
    issue: str | None = None
    source: Literal["submitted", "service"] = "submitted"


@dataclass(frozen=True)
class UserSummary:
    user: str
    subjects: tuple[SubjectSummary, ...]

    def to_dict(self):
        """GUI나 JSON 출력에 넘길 값. 원시 기록을 포함하지 않음."""
        data = asdict(self)
        data["subjects"] = list(data["subjects"])
        for subject in data["subjects"]:
            subject["metrics"] = list(subject["metrics"])
        return data


@dataclass(frozen=True)
class TeamSummary:
    users: tuple[UserSummary, ...]
    status: Literal["ok", "unavailable"] = "ok"


class _Unavailable(Exception):
    def __init__(self, issue):
        self.issue = issue


def _record_exists(path):
    root, actual = os.path.realpath(study.SUBMISSIONS_DIR), os.path.realpath(path)
    try:
        if os.path.commonpath((root, actual)) != root:
            raise _Unavailable("source")
    except ValueError:
        raise _Unavailable("source") from None
    try:
        info = os.stat(path)
    except FileNotFoundError:
        return False
    except OSError:
        raise _Unavailable("record") from None
    if not stat.S_ISREG(info.st_mode):
        raise _Unavailable("record")
    return True


def _record_log(user, subject):
    path = os.path.join(study.SUBMISSIONS_DIR, user, subject, "record.json")
    try:
        return web_record.Record(path, user).log
    except Exception:
        raise _Unavailable("record") from None


def _validate_rows(log, required):
    """집계에 쓰는 기록의 필수 필드와 시각을 확인함. 메모 같은 비집계 필드는 읽지 않음."""
    for row in log:
        if not isinstance(row.get("kind"), str):
            raise _Unavailable("record")
        fields = required.get(row.get("kind"))
        if fields is None:
            continue
        if web_record.parse_at(row.get("at")) is None or any(not isinstance(row.get(key), str) or not row[key] for key in fields):
            raise _Unavailable("record")


def _calendar_day():
    return datetime.date.today()


def _python(user, cat):
    path = adaptive.profile_path(user)
    exists = _record_exists(path)
    if not exists:
        legacy = study.started_sets(user)
        metrics = [Metric("legacy_sets", "기존 세트 폴더", len(legacy), None, "개",
                          "제출본에 남은 세트 풀이 폴더를 셉니다. 응답 수나 학습량은 폴더만으로 추정하지 않습니다.")] if legacy else []
        return bool(legacy), metrics, NextAction("sets", "", "학습 중인 기기의 파이썬 기록을 확인하세요.")
    try:
        prof = adaptive.load_profile(user)
        rounds, attempts = prof["rounds"], prof["attempts"]
        if not isinstance(rounds, list) or not isinstance(attempts, list):
            raise ValueError
        for row in rounds:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not adaptive.ROUND_RE.fullmatch(row["id"]):
                raise ValueError
        for row in attempts:
            if (not isinstance(row, dict) or not isinstance(row.get("item"), str) or not isinstance(row.get("ok"), bool)
                    or type(row.get("try")) is not int or row["try"] < 1):
                raise ValueError
    except Exception:
        raise _Unavailable("record") from None
    try:
        cat = adaptive.catalog() if cat is None else cat
        legacy = study.started_sets(user)
    except Exception:
        raise _Unavailable("catalog") from None
    answered = [row for row in attempts if row["item"] in cat and not row.get("skipped")]
    items = {row["item"] for row in answered}
    metrics = [
        Metric("answered_items", "답한 문항", len(items), len(cat), "개",
               "현재 공개된 문항 중 응답을 채점한 문항을 한 번씩 셉니다. 미응답으로 확정한 기록은 제외합니다.", "coverage"),
        Metric("answers", "응답 기록", len(answered), None, "회",
               "프로필에 남은 문항별 응답 기록을 셉니다. 같은 결과로 다시 채점하면 기록을 늘리지 않습니다."),
        Metric("repeats", "반복 풀이", len(answered) - len(items), None, "회",
               "같은 문항에 두 번째 이후로 답한 기록을 셉니다. 다른 회차에서 다시 답한 기록도 포함합니다."),
        Metric("finished_rounds", "끝낸 회차", sum(bool(row.get("completed_at")) for row in rounds), len(rounds), "회",
               "만든 회차 중 종료 기록이 있는 회차를 셉니다. 진단 회차도 포함합니다.", "coverage", "만든 회차"),
    ]
    if legacy:
        metrics.append(Metric("legacy_sets", "기존 세트 폴더", len(legacy), None, "개",
                              "회차형 프로필과 별도로 남은 세트 풀이 폴더를 셉니다. 폴더가 있다는 이유로 응답 수를 늘리지 않습니다."))
    unfinished = next((row for row in reversed(rounds) if not row.get("completed_at")), None)
    if unfinished:
        action = NextAction("round", unfinished["id"], "%s 회차의 풀이를 이어서 하세요." % unfinished["id"])
    elif rounds or answered:
        action = NextAction("practice", "", "파이썬에서 다음 맞춤 회차를 풀어 보세요.")
    elif legacy:
        action = NextAction("sets", "", "파이썬에서 기존 세트의 풀이를 이어서 하세요.")
    else:
        action = NextAction("diagnose", "", "파이썬 진단 테스트를 시작하세요.")
    return bool(rounds or attempts or legacy), metrics, action


def _journey(user):
    if not _record_exists(os.path.join(study.SUBMISSIONS_DIR, user, "journey", "progress.json")):
        return False, [], None
    try:
        sess = JourneySession(user)
    except Exception:
        raise _Unavailable("source") from None
    _validate_rows(sess.log, {"grade": ("item", "lang"), "hint": ("item",), "explain": ("item",)})
    for row in sess.log:
        if row.get("kind") == "grade" and (not isinstance(row.get("passed"), bool) or row["lang"] not in ("python", "javascript")):
            raise _Unavailable("record")
    if sess.bank_errors:
        raise _Unavailable("catalog")
    view = sess.overview()
    keys = {"%s/%s" % (did, problem["id"]) for did, dungeon in sess.dungeons.items() for problem in dungeon["problems"]}
    grades = [row for row in sess.log if row.get("kind") == "grade" and row.get("item") in keys]
    tried = {row["item"] for row in grades}
    metrics = [
        Metric("tried_items", "채점한 문제", len(tried), view["total"], "개",
               "현재 공개된 문제 중 채점 기록이 있는 문제를 한 번씩 셉니다.", "coverage"),
        Metric("passed_items", "통과한 문제", view["passed"], view["total"], "개",
               "Python이나 JavaScript 중 한 언어라도 통과한 문제를 한 번씩 셉니다. 해설을 본 뒤 통과한 문제도 포함합니다.", "coverage"),
        Metric("grades", "채점 기록", len(grades), None, "회", "공개된 문제의 채점 완료 기록을 셉니다. 취소한 채점은 기록에 남지 않습니다."),
        Metric("repeats", "반복 채점", len(grades) - len(tried), None, "회",
               "같은 문제의 두 번째 이후 채점 기록을 셉니다. 다른 언어로 다시 채점한 기록도 포함합니다."),
    ]
    pick = view["next"]
    action = NextAction("problem", "%s/%s" % (pick["did"], pick["pid"]),
                        "%s/%s 문제를 풀어 보세요." % (pick["did"], pick["pid"])) if pick else NextAction("journey", "", "여행에서 선택 문제나 통과한 문제를 다시 풀어 보세요.")
    return bool(sess.log), metrics, action


def _web(user):
    if not _record_exists(os.path.join(study.SUBMISSIONS_DIR, user, "web", "record.json")):
        return False, [], None
    log = _record_log(user, "web")
    fields = {kind: ("item",) for kind in web_record.MISSION_KINDS}
    fields.update(learn=("page",), chain=("chain", "result"), drill=("chain",))
    _validate_rows(log, fields)
    if any(row.get("kind") == "chain" and row.get("result") not in web_review.RESULTS for row in log):
        raise _Unavailable("record")
    try:
        index = web_bank.read_index()
        missions = {e["id"]: web_bank.load_mission(e) for e in index["missions"] if web_bank.is_ready("mission", e["id"])}
        topics = [web_bank.load_topic(e) for e in index["topics"] if web_bank.is_ready("topic", e["id"])]
        pages = {e["id"] for e in index["pages"] if web_bank.is_ready("page", e["id"]) and web_bank.load_page(e)}
    except Exception:
        raise _Unavailable("catalog") from None
    chains = {c["id"]: None for topic in topics if not topic["local"] for c in topic["chains"]}
    chains.update({mid + "-F": mid for mid in missions})
    public = [row for row in log if (row.get("kind") == "learn" and row.get("page") in pages)
              or (row.get("kind") in web_record.MISSION_KINDS and row.get("item") in missions)
              or (row.get("kind") in ("chain", "drill") and row.get("chain") in chains)]
    try:
        states = web_record.mission_states(public)
        schedules = {cid: web_review.schedule(rows) for cid, rows in web_record.chain_results(public).items()}
        learned = set(web_record.learned(public))
        unlocked = {cid for cid, mid in chains.items() if mid is None or states.get(mid, {}).get("phase") == "done"}
        due = [row for row in web_review.due_list(schedules, [], _calendar_day(), 0) if row["chain"] in unlocked]
    except Exception:
        raise _Unavailable("record") from None
    metrics = [
        Metric("opened_notes", "열어 본 노트", len(learned), len(pages), "개", "연 기록이 있는 공개 학습 페이지를 한 번씩 셉니다.", "coverage"),
        Metric("finished_missions", "완료 상태 미션", sum(s["phase"] == "done" for s in states.values()), len(missions), "개",
               "미션별 마지막 시도의 상태가 끝남인 미션을 셉니다. 다시 받으면 새 시도의 상태를 따릅니다.", "coverage"),
        Metric("tried_chains", "풀이한 사슬", len(schedules), len(chains), "개",
               "끝까지 답하고 판정을 남긴 공개 말하기 사슬을 한 번씩 셉니다. 통과 여부와 구분합니다.", "coverage"),
        Metric("checks", "미션 검사", sum(row["kind"] == "check" for row in public), None, "회", "제출 기록에 남은 미션 검사 횟수를 셉니다."),
        Metric("answers", "말하기 응답", sum(row["kind"] == "drill" for row in public), None, "회", "제출 기록에 남은 사슬 질문별 응답을 셉니다. 로컬 경력 답변은 읽지 않습니다."),
        Metric("due", "복습할 사슬", len(due), None, "개", "이미 푼 사슬 중 복습 날짜가 오늘이거나 지났고 지금 열려 있는 사슬을 셉니다."),
    ]
    ongoing = next((mid for mid in index["order"] if states.get(mid, {}).get("phase") in ("reading", "live")), None)
    if ongoing:
        action = NextAction("mission", ongoing, "%s 미션을 이어서 하세요." % ongoing)
    elif due:
        cid = due[0]["chain"]
        action = NextAction("chain", cid, "%s 사슬을 복습하세요." % cid)
    else:
        action = NextAction("web", "", "웹 면접 준비에서 다음 노트나 미션을 선택하세요.")
        for iid in index["order"]:
            if iid in pages and iid not in learned:
                action = NextAction("page", iid, "%s 노트를 열어 보세요." % iid)
                break
            if iid in missions and states.get(iid, {}).get("phase") != "done":
                action = NextAction("mission", iid, "%s 미션을 시작하세요." % iid)
                break
    return bool(public), metrics, action


def _ai(user):
    path = os.path.join(study.SUBMISSIONS_DIR, user, "ai", "record.json")
    if not _record_exists(path):
        return False, [], None
    try:
        sess = AiSession(user)
    except Exception:
        raise _Unavailable("source") from None
    _validate_rows(sess.record.log, {"learn": ("lesson", "unit"), "revisit": ("lesson", "unit"),
                                    "answer": ("card", "result"), "recall": ("lesson", "unit")})
    if any(row.get("kind") == "answer" and row.get("result") not in web_review.RESULTS for row in sess.record.log):
        raise _Unavailable("record")
    if sess.errors:
        raise _Unavailable("catalog")
    view = sess.overview()
    available = {(lid, key) for lid, note in sess.notes.items() for key in note["visible"]}
    events = ai_review.card_events(sess.record.log)
    answers = [row for row in sess.record.log if row.get("kind") == "answer" and row.get("card") in sess.cards]
    reads = {(row["lesson"], row["unit"]) for row in sess.record.log if row.get("kind") == "learn" and (row["lesson"], row["unit"]) in available}
    recalls = [row for row in sess.record.log if row.get("kind") == "recall" and (row["lesson"], row["unit"]) in available]
    revisits = [row for row in sess.record.log if row.get("kind") == "revisit" and (row["lesson"], row["unit"]) in available]
    metrics = [
        Metric("read_units", "끝까지 연 단원", len(reads), len(available), "개", "마지막 단계까지 연 기록이 있는 공개 단원을 한 번씩 셉니다.", "coverage"),
        Metric("answered_items", "답한 문항", len(set(events) & sess.cards.keys()), len(sess.cards), "개",
               "답을 판정한 공개 연습 문항을 한 번씩 셉니다. 보기나 함께 가린 칸에서 판정한 문장도 포함합니다.", "coverage"),
        Metric("answers", "직접 응답", len(answers), None, "회", "연습 문항에 직접 답한 기록을 셉니다. 보기의 동반 판정이나 정답 인정 요청은 별도 응답으로 더하지 않습니다."),
        Metric("repeats", "반복 응답", len(answers) - len({row["card"] for row in answers}), None, "회", "같은 연습 문항에 두 번째 이후로 직접 답한 기록을 셉니다."),
        Metric("recalls", "노트 확인 물음", len(recalls), None, "회", "노트의 떠올리기·세 수준 확인 물음·돌려 가며 빈칸에 답한 기록을 셉니다."),
        Metric("revisits", "노트 다시 보기", len(revisits), None, "회", "공개 단원을 다시 보기로 연 기록을 셉니다. 같은 단원을 여러 번 열면 각각 셉니다."),
        Metric("due", "복습할 문항", view["due"], None, "개", "학습일과 기존 복습 규칙으로 정한 오늘 복습 목록의 공개 문항을 셉니다. 학습일은 새벽 4시에 바뀝니다."),
    ]
    mocks = sum(row.get("kind") == "mock_submit" for row in sess.record.log)
    if mocks:
        metrics.append(Metric("mock_submissions", "모의고사 제출", mocks, None, "회", "모의고사 제출 기록을 셉니다. 연습 응답 수나 과목 점수에 더하지 않습니다."))
    pick = view["next"]
    if pick["kind"] in ("unit", "revisit"):
        target = "%s/%s" % (pick["lesson"], pick["unit"])
        action = NextAction(pick["kind"], target, "%s 단원을 %s." % (target, "다시 보세요" if pick["kind"] == "revisit" else "읽어 보세요"))
    elif pick["kind"] in ("again", "review"):
        action = NextAction(pick["kind"], "", "%s 문항 %d개를 풀어 보세요." % ("오늘 틀린" if pick["kind"] == "again" else "복습할", pick["count"]))
    elif pick["kind"] == "mock":
        action = NextAction("mock", pick["mock"], "%s 모의고사를 풀어 보세요." % pick["mock"])
    else:
        action = NextAction("ai", "", "AI 비전 개론에서 공개된 단원을 확인하세요.")
    return bool(sess.record.log), metrics, action


def collect_user(user, python_catalog=None):
    """제출 파일만 읽음. 외부 로컬 경로를 검색하지 않음. 한 과목의 오류를 다른 과목에 전파하지 않음."""
    if not isinstance(user, str) or not study.USER_RE.fullmatch(user):
        raise ValueError("학습자 ID의 형식을 확인하세요.")
    readers = (lambda: _python(user, python_catalog), lambda: _journey(user), lambda: _web(user), lambda: _ai(user))
    subjects = []
    for (key, title), read in zip(SUBJECTS, readers):
        try:
            has_record, metrics, action = read()
            if not has_record:
                action = NextAction("check_submission", "", "학습 중인 기기의 기록을 확인하세요.")
            subjects.append(SubjectSummary(key, title, "available" if has_record else "no_record", tuple(metrics) if has_record else (), action))
        except Exception as error:
            issue = error.issue if isinstance(error, _Unavailable) else "analysis"
            text = {"catalog": "학습 목록을 확인한 뒤 다시 집계하세요.",
                    "source": "학습 기록과 목록을 확인한 뒤 다시 집계하세요."}.get(issue, "학습 기록을 확인한 뒤 다시 집계하세요.")
            subjects.append(SubjectSummary(key, title, "unavailable", (), NextAction("check_" + issue, "", text), issue))
    return UserSummary(user, tuple(subjects))


def from_overviews(user, overviews):
    """GUI가 이미 읽은 네 서비스 overview를 집계함. 파일을 찾거나 기록을 전송하지 않음.

과목 키가 없거나 None이면 그 과목을 확인 불가로 둠. 0인 서비스 값도 관측된 값으로 보존함.
제출 파일에서만 셀 수 있는 응답·반복 수를 overview 값으로 추정하지 않음.
"""
    if not isinstance(user, str) or not study.USER_RE.fullmatch(user):
        raise ValueError("학습자 ID의 형식을 확인하세요.")
    subjects = []
    for key, title in SUBJECTS:
        try:
            view = overviews[key]
            if not isinstance(view, dict) or view.get("errors") or view.get("bank_errors"):
                raise ValueError
            metrics, action = _overview_metrics(key, view)
            if any(type(m.value) is not int or m.value < 0 or (m.total is not None and (type(m.total) is not int or m.total < m.value)) for m in metrics):
                raise ValueError
            subjects.append(SubjectSummary(key, title, "available", tuple(metrics), action, source="service"))
        except Exception:
            subjects.append(SubjectSummary(key, title, "unavailable", (), NextAction("check_service", "", "이 기기의 서비스를 다시 확인하세요."), "service", "service"))
    return UserSummary(user, tuple(subjects))


def _overview_metrics(key, view):
    action = NextAction("subject", "", "이 과목에서 다음 학습 항목을 확인하세요.")
    if key == "python":
        units, rounds = view["units"], view["rounds"]
        metrics = [Metric("tested_units", "채점한 단원", sum(bool(row["tested"]) for row in units), len(units), "개",
                          "이 기기의 서비스에서 채점 기록이 있다고 표시한 단원을 셉니다.", "coverage"),
                   Metric("first_grades", "첫 채점 기록", view["attempts"], None, "회",
                          "서비스의 회차별 문항 첫 채점 수입니다. 미응답으로 확정한 기록도 포함합니다."),
                   Metric("finished_rounds", "끝낸 회차", sum(bool(row["completed"]) for row in rounds), len(rounds), "회",
                          "이 기기에서 만든 회차 중 끝낸 회차를 셉니다.", "coverage", "만든 회차")]
        if view["current"]:
            rid = view["current"]["id"]
            action = NextAction("round", rid, "%s 회차를 이어서 하세요." % rid)
        else:
            action = NextAction("practice", "", "파이썬에서 다음 회차를 확인하세요.")
    elif key == "journey":
        metrics = [Metric("passed_items", "통과한 문제", view["passed"], view["total"], "개",
                          "이 기기의 서비스에서 한 언어라도 통과한 문제를 한 번씩 셉니다.", "coverage"),
                   Metric("grades", "채점 기록", view["attempts"], None, "회", "이 기기 서비스의 채점 완료 횟수입니다.")]
        if view["next"]:
            pick = view["next"]
            target = "%s/%s" % (pick["did"], pick["pid"])
            action = NextAction("problem", target, "%s 문제를 풀어 보세요." % target)
    elif key == "web":
        pages = [row for row in view["pages"] if row["ready"]]
        chains = [chain for row in view["topics"] if row["ready"] for chain in row["chains"]]
        due = sum(not row["new"] for row in view["today"]["chains"])
        metrics = [Metric("opened_notes", "열어 본 노트", sum(bool(row["learned_at"]) for row in pages), len(pages), "개",
                          "이 기기 서비스에서 연 기록을 확인한 공개 노트를 셉니다.", "coverage"),
                   Metric("finished_missions", "완료 상태 미션", view["done_missions"], view["ready_missions"], "개",
                          "이 기기 서비스에서 마지막 시도가 끝남인 미션을 셉니다.", "coverage"),
                   Metric("topic_chains", "풀이한 주제 사슬", sum(row["times"] > 0 for row in chains), len(chains), "개",
                          "서비스가 제공한 주제 사슬 중 판정 기록이 있는 사슬을 셉니다. 미션 꼬리 질문은 이 분모에 넣지 않습니다.", "coverage"),
                   Metric("due", "복습할 사슬", due, None, "개", "이 기기 서비스의 오늘 복습 목록에서 새 사슬을 제외하고 셉니다."),
                   Metric("activity_days", "기록한 학습일", len(view["activity"]), None, "일",
                          "이 기기 서비스에서 검사나 말하기 응답을 기록한 날짜 수입니다. 로컬 사슬의 활동도 포함합니다.")]
        pick = view["next"]
        if pick:
            target = pick.get("chain") or pick["id"]
            action = NextAction(pick["kind"], target, "%s 항목을 이어서 하세요." % target)
    else:
        lessons = [row for row in view["lessons"] if row["ready"]]
        pattern_units = [unit for row in view["patterns"] for unit in row["units"] if unit["ready"]]
        read = sum(row["read"] for row in lessons) + sum(unit["read"] for unit in pattern_units)
        total = sum(row["units_total"] for row in lessons) + len(pattern_units)
        metrics = [Metric("read_units", "끝까지 연 단원", read, total, "개",
                          "이 기기 서비스에서 마지막 단계까지 연 공개 단원 수입니다. 상황별 코드 단원도 포함합니다.", "coverage"),
                   Metric("due", "복습할 문항", view["due"], None, "개", "이 기기 서비스의 학습일과 복습 일정으로 센 문항 수입니다."),
                   Metric("again", "오늘 다시 풀 문항", view["again"], None, "개", "서비스에서 오늘 틀린 뒤 다시 풀도록 남겨 둔 문항 수입니다.")]
        pick = view["next"]
        if pick["kind"] in ("unit", "revisit"):
            target = "%s/%s" % (pick["lesson"], pick["unit"])
            action = NextAction(pick["kind"], target, "%s 단원을 확인하세요." % target)
        elif pick["kind"] in ("again", "review"):
            action = NextAction(pick["kind"], "", "복습 목록의 문항을 풀어 보세요.")
        elif pick["kind"] == "mock":
            action = NextAction("mock", pick["mock"], "%s 모의고사를 확인하세요." % pick["mock"])
    return metrics, action


def collect_team(python_catalog=None):
    """제출 폴더가 있는 학습자를 ID 순서로 집계함. 프로필이 없는 다른 과목 학습자도 포함함."""
    try:
        info = os.stat(study.SUBMISSIONS_DIR)
        if not stat.S_ISDIR(info.st_mode):
            return TeamSummary((), "unavailable")
        users = study.all_users()
    except FileNotFoundError:
        return TeamSummary(())
    except OSError:
        return TeamSummary((), "unavailable")
    return TeamSummary(tuple(collect_user(user, python_catalog) for user in users))


def metric_text(metric):
    if metric.total == 0:
        return "%s %d%s · %s 0%s" % (metric.label, metric.value, metric.unit, metric.total_label, metric.unit)
    count = "%d/%d" % (metric.value, metric.total) if metric.total is not None else str(metric.value)
    return "%s %s%s" % (metric.label, count, metric.unit)


def status_text(subject):
    if subject.source == "service" and subject.status == "available":
        return "서비스 확인"
    return STATUS_LABELS[subject.status]


def _md(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\n", " ")


def markdown(rows, title="과목별 학습 기록을 확인하세요", unavailable=False):
    """과목 사이의 합계나 순위 없이 기록과 정의를 표로 보임."""
    sources = {s.source for row in rows for s in row.subjects}
    if sources == {"service"}:
        explanation = "이 기기 서비스에서 확인한 값을 과목별로 보여 줍니다."
    elif sources == {"submitted", "service"}:
        explanation = "행마다 적힌 데이터 출처에서 확인한 값과 다음 행동을 보여 줍니다. 제출 파일이 없다는 이유로 학습 시작 여부를 판단하지 않습니다."
    else:
        explanation = "제출된 파일만 집계합니다. 다음 행동도 제출 기록을 기준으로 안내합니다. 미제출 학습은 학습 중인 기기에서 확인하세요."
    lines = ["### " + title, "", explanation, "",
             "| 학습자 | 대과목 | 데이터 출처 | 기록 상태 | 학습·풀이 | 시도·복습 | 다음 행동 |", "|---|---|---|---|---|---|---|"]
    definitions = {}
    for row in rows:
        for subject in row.subjects:
            cells = []
            for group in ("coverage", "activity"):
                metrics = [metric for metric in subject.metrics if metric.group == group]
                cells.append("<br>".join(_md(metric_text(metric)) for metric in metrics) or status_text(subject))
                for metric in metrics:
                    definitions[(subject.title, metric.key)] = (metric.label, metric.definition)
            lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (_md(row.user), subject.title, SOURCE_LABELS[subject.source], status_text(subject), *cells, _md(subject.next_action.text)))
    if not rows:
        for _, title_ in SUBJECTS:
            if unavailable:
                lines.append("| 학습자 목록 | %s | 제출된 파일 | 확인 불가 | 확인 불가 | 확인 불가 | 제출 기록 목록을 확인한 뒤 다시 집계하세요. |" % title_)
            else:
                lines.append("| 학습자 목록 | %s | 제출된 파일 | 제출 기록 없음 | 제출 기록 없음 | 제출 기록 없음 | 학습 중인 기기의 기록을 확인하세요. |" % title_)
    if definitions:
        lines += ["", "<details>", "<summary>집계 방법을 확인하세요</summary>", ""]
        for (subject, _), (label, definition) in definitions.items():
            lines.append("- %s의 %s: %s" % (subject, label, definition))
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"
