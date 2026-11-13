# -*- coding: utf-8 -*-
"""카드마다의 복습 상자, 학습일, 시험 전 훑기(설계 1.3, 2.8). 상자는 기록에서 매번 계산하고 저장하지 않음.

학습일은 04:00 에 바뀜(DAY_START_HOUR). 23:55 와 다음 날 00:05 의 두 답이 서로 다른 날 두 번이 되지 않게 하려는 것임.
card_schedule 은 한 카드의 답 기록(card_events 가 만든 것)을 학습일마다 묶어 그날 첫 답으로 상자를 정함. 규칙 번호는
설계 2.8 의 1~7 과 같음. 날짜는 모두 datetime.date 이고 exam 은 {"date", "last_new", "sweep_from", "last_review"}.
"""
import datetime
import hashlib

from webprep import record
from webprep.review import next_box

INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
DAY_START_HOUR = 4
MEMORISED_BOX = 4
RECHECK_DAYS = 7
LEECH_DROPS = 3
ONE_DAY = datetime.timedelta(days=1)


def study_day(at):
    """기록 시각의 학습일. 04:00 전이면 앞 날. 읽지 못하면 None."""
    when = at if isinstance(at, datetime.datetime) else record.parse_at(at)
    if when is None:
        return None
    return (when - datetime.timedelta(hours=DAY_START_HOUR)).date()


def parse_day(text):
    if isinstance(text, datetime.date):
        return text
    try:
        return datetime.date.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None


def exam_dates(raw):
    """index.json 의 exam 을 date 로."""
    return {key: parse_day(raw.get(key)) for key in ("date", "last_new", "sweep_from", "last_review")}


# 기록에서 카드별 답 모으기

class EventIndex(object):
    """card_events 를 덧붙는 기록에 이어서 계산함. events 는 {카드 id: [답]}, ver 는 카드마다 바뀐 횟수(일정 캐시의 키)."""

    def __init__(self, first_try_only=True, versions=None, revised=()):
        self.first_try_only = first_try_only
        self.versions, self.revised = versions or {}, set(revised)
        self.unversioned = set()
        self.events, self.ver = {}, {}
        self._answers = {}
        self._mocks = set()
        self._also = {}  # (set, 주 카드, again, 함께 고른·가린 카드) → also 행. override 의 also_value 가 지울 행을 찾음

    def _add(self, cid, row, revision=None):
        expected = self.versions.get(cid)
        wrong_version = revision is not None and revision != expected
        unconfirmed_change = revision is None and cid in self.revised
        if expected is not None and (wrong_version or unconfirmed_change):
            return
        if revision is None:
            self.unversioned.add(cid)
        self.events.setdefault(cid, []).append(row)
        self.ver[cid] = self.ver.get(cid, 0) + 1

    def feed(self, entries):
        for entry in entries:
            kind = entry.get("kind")
            at = entry.get("at")
            day = study_day(at)
            if day is None:
                continue
            if kind == "answer" and entry.get("card"):
                cid = str(entry["card"])
                row = {"at": at, "day": day, "result": str(entry.get("result") or "stuck"), "sure": entry.get("sure"),
                       "again": int(entry.get("again") or 0), "set": entry.get("set"), "dontknow": bool(entry.get("dontknow")),
                       "src": "answer", "override": False}
                self._add(cid, row, entry.get("content_revision"))
                self._answers[(entry.get("set"), cid, row["again"])] = row
                for other, result in (entry.get("also") or {}).items():
                    also = {"at": at, "day": day, "result": str(result), "sure": None, "again": 0,
                            "set": entry.get("set"), "dontknow": False, "src": "also", "override": False}
                    self._add(str(other), also, (entry.get("content_revisions") or {}).get(str(other)))
                    self._also[(entry.get("set"), cid, row["again"], str(other))] = also
            elif kind == "override" and entry.get("card"):
                cid = str(entry["card"])
                again = int(entry.get("again") or 0)
                row = self._answers.get((entry.get("set"), cid, again))
                if row is not None and row["result"] != "pass":
                    row["result"], row["override"] = "pass", True
                    self.ver[cid] = self.ver.get(cid, 0) + 1
                for other in entry.get("also_value") or {}:
                    # 함께 가린 칸을 [내 답도 맞음]으로 바꾸면 그 자리의 also 행을 지움. pass 로 두면 card_schedule 이 보통 답으로
                    # 보아 상자를 올릴 수 있어서 지움
                    also = self._also.pop((entry.get("set"), cid, again, str(other)), None)
                    rows = self.events.get(str(other), [])
                    if also is not None and any(r is also for r in rows):
                        rows[:] = [r for r in rows if r is not also]
                        if not rows:
                            del self.events[str(other)]  # 답이 하나도 남지 않으면 답한 적 없는 카드로 되돌림
                        self.ver[str(other)] = self.ver.get(str(other), 0) + 1
            elif kind == "mock_submit":
                mid = entry.get("mock")
                if self.first_try_only and mid in self._mocks:
                    continue
                self._mocks.add(mid)
                for cid, result in (entry.get("results") or {}).items():
                    self._add(str(cid), {"at": at, "day": day, "result": "pass" if result == "pass" else "stuck", "sure": None,
                                         "again": 0, "set": entry.get("mock"), "dontknow": result == "blank", "src": "mock",
                                         "override": False, "mock": entry.get("mock")})


def card_events(log, first_try_only=True):
    """기록을 {카드 id: [답]} 으로. 답은 {"at", "day", "result", "sure", "again", "set", "dontknow", "src"} 이고 시간 순.
    src 는 answer(연습 답), also(문장 카드에서 함께 고른 보기, 뼈대 빈칸에서 함께 가린 자리), mock(모의고사 첫 풀이 제출).
    override 는 set·again·card 로 가리킨 답 하나를 pass 로 바꾸고, also_value 에 적힌 자리의 그 답 also 행은 지움. 모의고사는
    각 모의고사에서 처음 제출한 판정만 넣음. 자료 갱신으로 시작만 한 시도가 앞에 있어도 제출 번호로 제외하지 않음."""
    index = EventIndex(first_try_only)
    index.feed(log)
    return index.events


def read_days(log):
    """{(차시, 단원): 처음 끝까지 읽은 학습일}."""
    out = {}
    for entry in log:
        if entry.get("kind") == "learn" and entry.get("lesson") and entry.get("unit"):
            key = (str(entry["lesson"]), str(entry["unit"]))
            day = study_day(entry.get("at"))
            if day is not None and key not in out:
                out[key] = day
    return out


# 일정

def _by_day(events):
    days = []
    for event in events:
        if days and days[-1][0] == event["day"]:
            days[-1][1].append(event)
        else:
            days.append((event["day"], [event]))
    return days


def sweep_day(card, exam):
    """시험 전 훑기에서 그 카드가 나올 날. sweep_from + (카드 id 의 sha1 정수 mod 7)일."""
    start = exam.get("sweep_from")
    if start is None:
        return None
    offset = int(hashlib.sha1(str(card).encode("utf-8")).hexdigest(), 16) % 7
    return start + datetime.timedelta(days=offset)


def in_sweep(exam, today):
    return bool(exam.get("sweep_from") and exam.get("last_review")) and exam["sweep_from"] <= today <= exam["last_review"]


def card_schedule(events, read_day, exam, today, card=None):
    """한 카드의 상자와 다음 날짜. events 는 card_events 의 그 카드 목록(시간 순), read_day 는 그 카드 단원을 처음 읽은 학습일
    (없으면 None), today 는 지금 학습일. 답이 없으면 None.

    돌려주는 dict: box, last(상자를 정한 날), due, recheck(확신 오답 다시 볼 날), done(시험 전 확인 끝), drops(서로 다른 날
    상자 2 이상에서 1 로 떨어진 횟수), first(첫 답 학습일), days([(학습일, 그날 뒤 상자, 상자를 움직였는지)]), times(답 수),
    sure_wrong(마지막으로 틀린 답이 확실함이었는지)."""
    if not events:
        return None
    exam = exam or {}
    after_exam = bool(exam.get("date")) and today > exam["date"]
    box = last = due = recheck = None
    done, drops, days, sure_wrong = False, 0, [], False

    def capped(day, new_box, result):
        """규칙 4·5·7. day 에 상자를 new_box 로 정했을 때의 다음 날짜와 시험 전 확인 끝 여부."""
        when = day + datetime.timedelta(days=INTERVAL_DAYS[new_box])
        finished = False
        if not after_exam and exam.get("date"):
            if exam.get("sweep_from") and day >= exam["sweep_from"] and result == "pass" and new_box >= MEMORISED_BOX:
                when, finished = exam["date"] + ONE_DAY, True
            elif exam.get("last_review"):
                when = max(day + ONE_DAY, min(when, exam["last_review"]))  # 마지막 복습일과 시험날에 맞힌 카드는 다음 날로
        if recheck is not None and recheck > day:
            when = min(when, recheck)
        return when, finished

    for day, rows in _by_day(events):
        first, rest = rows[0], rows[1:]
        before = box
        result = first["result"]
        moved = False
        early = box is not None and due is not None and day < due
        if early or (box is not None and first["again"] > 0):
            # 규칙 3: 날짜 전(또는 묶음 안에서 다시 나온 답). pass 는 무시, stuck 은 적용, partial 은 머물고 날짜를 늦추지 않음
            if result == "stuck":
                box, last, due, done = 1, day, day + ONE_DAY, False
                moved = True
            elif result == "partial":
                due = min(due, day + ONE_DAY)
        else:
            if box is None and read_day is not None and day == read_day:
                new_box = 1  # 규칙 2: 읽은 날의 첫 답은 pass 여도 상자 1
            else:
                new_box = next_box(box, result)
            box, last = new_box, day
            due, done = capped(day, new_box, result)
            moved = True
        if any(r["result"] == "stuck" for r in rest):  # 규칙 1: 같은 날 뒤의 오답도 반영
            box, last, due, done = 1, day, day + ONE_DAY, False
            moved = True
        wrong_sure = [r for r in rows if r["result"] == "stuck" and r.get("sure") and not r.get("dontknow")]
        if wrong_sure:  # 규칙 5: 확신 오답
            recheck = day + datetime.timedelta(days=RECHECK_DAYS)
            due = min(due, day + ONE_DAY) if due else day + ONE_DAY
            done = False
        fails = [r for r in rows if r["result"] != "pass"]
        if fails:
            sure_wrong = bool(wrong_sure)
        if before is not None and before >= 2 and box == 1:
            drops += 1
        days.append((day, box, moved))
    return {"box": box, "last": last, "due": due, "recheck": recheck, "done": done, "drops": drops, "first": events[0]["day"],
            "days": days, "times": len(events), "sure_wrong": sure_wrong}


def due_on(schedule, card, exam, today, open_card=True):
    """오늘 기준 다음 날짜. 훑기 기간에는 마지막 답이 훑기 시작 전인 열린 카드를 sweep_day 로 당김."""
    if schedule is None:
        return None
    due = schedule["due"]
    if open_card and in_sweep(exam, today) and schedule["last"] is not None and schedule["last"] < exam["sweep_from"] \
            and not schedule["done"]:
        due = min(due, sweep_day(card, exam))
    return due


def memorised(schedule):
    return bool(schedule) and (schedule["box"] or 0) >= MEMORISED_BOX


def leech(schedule):
    """자주 틀리는 문항: 서로 다른 날에 상자 2 이상에서 1 로 떨어진 횟수가 LEECH_DROPS 이상."""
    return bool(schedule) and schedule["drops"] >= LEECH_DROPS


def relative_delay(schedule, today):
    """밀린 정도 (오늘 − due) ÷ 간격. 복습 묶음을 이 값이 큰 순으로 채움."""
    if not schedule or schedule["due"] is None:
        return 0.0
    return (today - schedule["due"]).days / float(INTERVAL_DAYS.get(schedule["box"] or 1, 1))
