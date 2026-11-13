# -*- coding: utf-8 -*-
"""AI 비전 개론 화면의 글. 서비스(aiprep.service)가 준 값을 화면 글로 바꾸고, 공유 오답 노트 화면에 붙는 공급자 AiNotes 를 둠.

하루 목표, 목표 단원 수, 새 문항 상한은 화면에 쓰지 않음(2026-11-03 사용자 결정: 문제집을 원하는 만큼 푸는 꼴). 복습 날짜가 된 문항 수와
복습 확인 수는 알림으로만 씀. 내부 id(i05, 5c, 상자 3)는 화면에 쓰지 않음."""
import datetime
import html
import re

import mdlite
from aiprep import bank
from gui.result_page import band, code_box, md_html
from session import SessionError


def teaching_text(text):
    """옛 해설의 출처 대조 머리말만 뺌. 정확한 조건과 설명은 그대로 남김."""
    return re.sub(r"(^|(?<=[.!?])\s+|\n)정정:\s*", r"\1", text)

TRACK = "AI"
COURSES = {"intro": "개론", "app": "응용"}
STEPS = ("1. [학습 시작]을 눌러 단원을 읽습니다.",
         "2. 단원 끝의 [연습 시작]을 눌러 그 단원 문항을 풉니다.",
         "3. 다음 날부터는 전에 푼 문항이 다시 나옵니다. [복습 시작]이 보이면 복습부터 풉니다.")
TERMS = ("읽기·단원 연습·복습 확인은 따로 기록합니다. 복습 확인은 예정된 복습에서 각 날의 첫 답을 세 번 연속 맞힌 문항 묶음입니다. "
         "읽은 날은 제외합니다. 같은 내용을 묻는 여러 형태는 한 묶음으로 세며, 이미 풀어본 형태가 모두 기준을 충족해야 확인한 것으로 셉니다.")
START_LINE = "1차시 첫째 단원부터 읽습니다."
ORDINALS = ("첫째", "둘째", "셋째", "넷째", "다섯째", "여섯째", "일곱째", "여덟째", "아홉째", "열째")
MIXED_ABOUT = "읽은 단원의 문항을 차시를 섞어 20문항씩 냅니다. 복습 문항이 먼저 나옵니다."
MIXED_EMPTY = "단원을 하나 읽으면 섞어 풀 수 있습니다."
LESSON_PRACTICE = "단원을 읽지 않아도 이 차시의 모든 문항을 20문항씩 냅니다."
PREPARING = "준비 중"
BOOK = "%d차시 문제집"
NOTES_ROW = "오답 노트"
BROKEN = "읽지 못한 차시가 있습니다: %s. 프로그램을 다시 실행해 최신 버전을 받은 뒤 다시 열어 보세요."
PATTERN_BROKEN = "%s를 읽지 못했습니다. 프로그램을 다시 실행해 최신 버전을 받은 뒤 다시 열어 보세요."
FIX_HINT = "파일을 고친 뒤 프로그램을 다시 실행해 주세요."
GUESS_LATER = "%d단계에서 답을 확인합니다."
RECALL_HEAD = "떠올리기"
WHY_HEAD = "왜일까요?"
REVEAL_HEAD = "짐작 확인"
MEMO_HINT = "질문을 읽고 답을 충분히 생각한 뒤 펼쳐보세요."
RECALL_EMPTY = "답을 적은 뒤 [확인]을 누르세요."
BLOCK_BROKEN = "이 부분을 읽지 못했습니다. 프로그램을 다시 실행해 최신 버전을 받아 보세요."
TRAINED = "다음 복습에서는 해설을 보기 전에 답을 먼저 떠올려 보세요."
SET_FIRST = "이번 묶음의 첫 답"
REVIEW_COMPLETE = "지금 복습할 문항이 없습니다."
EARLY = "복습 날짜 전에 맞힌 %d문항은 날짜가 되면 다시 확인합니다."
EMPTY_ANSWER = {"blank": "답을 적은 뒤 [확실함]이나 [긴가민가]를 누르세요. 모르면 [모르겠어요]를 누르세요.",
                "choice": "보기를 고른 뒤 [확실함]이나 [긴가민가]를 누르세요. 모르면 [모르겠어요]를 누르세요."}
FIRST_HINT = {"blank": "답을 적은 뒤 자신 있으면 [확실함], 아니면 [긴가민가]를 누르세요.",
              "choice": "보기를 고른 뒤 자신 있으면 [확실함], 아니면 [긴가민가]를 누르세요."}
FIRST_HINT_TAIL = " 틀린 문항은 내일 다시 나오고, [확실함]으로 틀린 문항은 7일 뒤에 한 번 더 나옵니다."
SHORTCUTS = "Ctrl+Enter 는 [확실함], Ctrl+Shift+Enter 는 [긴가민가] (맥은 Cmd)"
LEECH_HEAD = "자주 틀리는 문항"
LEECH_ABOUT = "맞힌 뒤 다시 틀린 일이 서로 다른 날 세 번 이상 있었던 문항입니다."
MODE_HINT = {"word": "낱말", "code": "코드", "number": "숫자", "shape": "모양", "values": "값", "exact": "출력 그대로"}
SCOPE_BADGE = {"support": "보충 설명", "deep": "심화", "extra": "더 알아보기 · 시험 범위 밖", "trend": "2026 흐름 · 시험 범위 밖"}
SCOPE_HEADS = ("심화", "보충 설명", "더 알아보기", "2026 흐름")  # 단계 제목 앞머리. 꼬리표가 같은 말을 하므로 제목에서는 뺌
BOXES = {"정정": ("정정", "warning"), "보충 설명": ("보충 설명", "accent")}  # > **[정정]** 인용 상자의 꼬리표와 색
VERDICT = {"pass": ("맞았습니다", "success"), "partial": ("일부 맞았습니다", "warning"), "stuck": ("틀렸습니다", "danger")}
SURE_WRONG = "확실하다고 했지만 틀렸습니다"
DONT_KNOW = "모르는 문항으로 넘겼습니다"
OVERRIDDEN = "맞은 답으로 바꿨습니다"
MOCK_LATER = "모의고사 화면을 아직 열 수 없습니다. [설정]의 [업데이트 확인]에서 새 자료가 있는지 확인하세요."
ROTATE_HEAD = "돌려 가며 빈칸"
ROTATE_DONE = "모든 자리를 맞혔습니다."
ROTATE_SLOTS = "가리는 자리: %s"
NEXT_SLOT = "다음 자리"
LEVELS_HEAD = "세 단계로 다시 보기"
LEVEL_NAMES = {7: "초급", 15: "중급", 20: "심화"}
LEVEL_DESCRIPTIONS = {7: "숫자와 그림으로 뜻을 잡습니다.", 15: "계산과 식으로 원리를 확인합니다.", 20: "정의와 코드를 연결해 적용합니다."}
LEVEL_CHECK = "확인 물음"
LEVEL_MISTAKE = "자주 하는 착각"
NUMBERS = bank.NUMBERS


def lesson_title(no, title, course="intro"):
    """자료에 같은 차시 번호가 있으면 화면에서 한 번만 씀."""
    prefix = ("응용 %s차시" if course == "app" else "%s차시") % no
    title = title.strip()
    return title if title == prefix or title.startswith(prefix + " ") else (prefix + " " + title).strip()


def plain(text):
    """인라인 마크다운(`코드`, **굵게**)을 꾸밈 없는 글자로."""
    return mdlite.inline_plain(text or "")


def number_mark(n):
    """빈칸 번호 글자. 1 → ①."""
    return NUMBERS[n - 1] if 1 <= n <= len(NUMBERS) else "(%d)" % n


def also_line(numbers):
    """뼈대 빈칸에서 함께 가린 칸이 틀렸을 때 정답 줄 아래 한 줄. numbers 는 1부터의 칸 번호. 그 칸 자리를 묻는 문항은 틀린
    것으로 기록돼 다음 학습일 복습에 나옴."""
    return "%s 칸은 틀렸습니다. 그 칸을 묻는 문항이 내일 복습에 나옵니다." % "·".join(number_mark(n) for n in numbers)


def diff_caption(different, same):
    """나란히 보기 위 caption. "다른 줄 2개 · 같은 줄 13개"."""
    return "다른 줄 %d개 · 같은 줄 %d개" % (different, same)


# 근거 표기(설계 3.8)

REFS = (
    (re.compile(r"(\d{1,2})차시 슬 p(\d+)(?:~p?(\d+))?(.*)\Z"),
     lambda m: "%s차시 슬라이드 %s%s쪽%s" % (m.group(1), m.group(2), "~" + m.group(3) if m.group(3) else "", m.group(4))),
    (re.compile(r"(\d{1,2})차시 노트북 (\d+) \[(\d+)\](.*)\Z"), lambda m: "%s차시 노트북 %s 셀 %s%s" % m.groups()),
    (re.compile(r"(\d{1,2})차시 강의노트(?: \[\d+\])?(.*)\Z"), lambda m: "%s차시 강의 노트%s" % m.groups()),
    (re.compile(r"요약 (\d)주차 p(\d+)(.*)\Z"), lambda m: "강사 요약본 %s주차 %s쪽%s" % m.groups()),
    (re.compile(r"대학원 (\d+) p(\d+)(.*)\Z"), lambda m: "대학원 강의안 %s %s쪽%s" % m.groups()),
    (re.compile(r"공식 (\d{1,2})차시(.*)\Z"), lambda m: "공식 커리큘럼 %s차시%s" % m.groups()),
    (re.compile(r"문서 (.+)\Z"), lambda m: "공식 문서 %s" % m.group(1)),
)


def ref_one(ref):
    """근거 하나를 사람 말로. 꼴을 모르면 그대로."""
    ref = str(ref).strip()
    for pattern, render in REFS:
        found = pattern.match(ref)
        if found:
            return render(found)
    return ref


def ref_text(refs):
    """근거 목록 한 줄. "4차시 슬라이드 20쪽 · 강사 요약본 1주차 19쪽"."""
    return " · ".join(ref_one(r) for r in refs or [])


def errata_text(errata):
    """자료 오류를 고친 문항임을 알림. 위치는 검증 기록에 남기고 바른 내용은 해설에서 다룸."""
    return "학습 자료의 오류를 바로잡은 문항입니다. 해설에서 이유를 확인하세요."


# 날짜

def md(day):
    return "%d월 %d일" % (day.month, day.day)


def exam_line(overview, today):
    """홈 제목 아래 알림 줄. 시험까지 남은 날, 오늘 푼 문항, 복습 확인 수."""
    parts = []
    days = overview["plan"].get("days_left")
    if days is not None and days >= 0:
        exam = today + datetime.timedelta(days=days)
        parts.append("%s 시험까지 %d일" % (md(exam), days) if days else "오늘 시험")
    answered = overview["today_answers"] + overview["today_extra"]
    if answered:
        parts.append("오늘 푼 문항 %d개" % answered)
    if overview["memorised"]:
        parts.append(memorised_part(overview))
    return " · ".join(parts)


def memorised_part(row):
    """같은 원리의 문항을 묶어 복습 기준을 충족한 수를 표시함."""
    if not row["memorised"]:
        return "복습 확인 전 · 전체 %d묶음" % row["families"]
    return "복습 확인 %d/%d묶음" % (row["memorised"], row["families"])


def due_part(count):
    return "복습 %d문항" % count


# 허브와 홈의 줄

def read_counts(overview):
    """(공개된 단원 수, 읽은 단원 수)."""
    ready = [row for row in overview["lessons"] if row["ready"]]
    return sum(row["units_total"] for row in ready), sum(row["read"] for row in ready)


def track_line(overview):
    """허브의 진도와 복습 수에 선택한 과정을 표시함."""
    total, read = read_counts(overview)
    if not read:
        item = overview.get("continuation", overview["next"])
        place = unit_place(item, overview) if item["kind"] == "unit" else ""
        detail = "%s부터 읽습니다." % place if place else START_LINE
    else:
        parts = ["단원 %d개 중 %d개 읽음" % (total, read)]
        if overview["memorised"]:
            parts.append(memorised_part(overview))
        if overview["due"]:
            parts.append(due_part(overview["due"]))
        detail = " · ".join(parts)
    course = COURSES.get(overview.get("course"))
    if course and detail.startswith(course + " "):
        detail = detail[len(course) + 1:]
    return "%s · %s" % (course, detail) if course else detail


def lesson_line(row):
    """학습 단원 구역의 차시 줄 둘째 줄. 읽은 단원 수를 표시함."""
    return "단원 %d개 중 %d개 읽음" % (row["units_total"], row["read"])


def lesson_dot(row):
    """차시 줄 점. 안 읽음은 빈 원, 읽는 중은 채운 원, 다 읽음은 체크. 둘째 줄 글로도 나뉨."""
    if row["units_total"] and row["read"] >= row["units_total"]:
        return "done"
    return "progress" if row["read"] else "todo"


def book_line(row):
    """문제집 구역의 차시 줄 둘째 줄. 복습 확인과 예정 문항을 표시함."""
    parts = [memorised_part(row)]
    if row["due"]:
        parts.append(due_part(row["due"]))
    return " · ".join(parts)


def book_dot(row):
    """차시 문제집 줄 점. 복습 문항이 있으면 주황, 핵심 문항을 거의 다 외웠으면 체크, 외운 문항이 있으면 파랑, 아니면 빈 원.
    색이 같은 점은 둘째 줄 글이 나눔."""
    if row["due"]:
        return "review"
    if row["state"] == "mastered":
        return "done"
    return "progress" if row["memorised"] else "todo"


def unit_line(unit):
    """읽기·단원 연습·복습 확인을 나누어 표시함."""
    parts = ["읽기 마침" if unit["read"] else "읽기 전"]
    if "practiced" in unit:
        parts.append("단원 연습 마침" if unit["practiced"] else "단원 연습 미완료")
    if unit["read"] or unit.get("practiced"):
        parts.append(memorised_part(unit))
        if unit["due"]:
            parts.append(due_part(unit["due"]))
    parts.append("약 %d분" % unit["minutes"])
    return " · ".join(parts)


def pattern_line(unit):
    """상황별 코드의 권장 순서와 읽기·연습·복습 기록을 표시함."""
    parts = ["%d차시 뒤에 권함" % unit["after_no"]] if unit.get("after_no") else []
    if unit["read"]:
        parts.append("읽기 마침")
        if "practiced" in unit:
            parts.append("단원 연습 마침" if unit["practiced"] else "단원 연습 미완료")
        parts.append(memorised_part(unit))
        if unit["due"]:
            parts.append(due_part(unit["due"]))
    else:
        parts.append("약 %d분" % unit["minutes"])
    return " · ".join(parts)


def unit_badges(unit):
    out = []
    if unit.get("kind") == "code":
        out.append("코드 읽기")
    if unit.get("deep"):
        out.append("심화 있음")
    return out


def mixed_line(overview):
    """섞어 풀기 줄 둘째 줄."""
    if not read_counts(overview)[1]:
        return MIXED_EMPTY
    if overview["due"]:
        return "%s이 먼저 나오고 나머지는 읽은 단원에서 섞어 냅니다." % due_part(overview["due"])
    return MIXED_ABOUT


def next_item(overview, today):
    """이어서 할 일 카드 {"kind", "title", "line", "action", "lesson", "unit"}. 할 일이 없으면 action 이 빈 글. today 는 학습일."""
    item = overview.get("continuation", overview["next"])
    kind = item["kind"]
    out = {"kind": kind, "lesson": item.get("lesson"), "unit": item.get("unit"), "title": "", "line": "", "action": ""}
    if "continuation" in overview:
        if kind == "practice":
            out.update(title=item["title"], line="풀던 묶음과 입력을 이어서 엽니다.", action="이어서 풀기",
                       mode=item["mode"], card=item.get("card"))
        elif kind == "unit":
            title, name = unit_task(item, overview)
            line = "읽다가 멈춘 %d단계부터 이어서 읽습니다." % item["step"] if item.get("resuming") else \
                "읽은 뒤 이 단원 문항부터 풉니다. 약 %d분." % (item.get("minutes") or 5)
            out.update(title=title, line="「%s」\n%s" % (name, line) if name else line,
                       action="이어서 학습" if item.get("resuming") else "학습 시작", step=item["step"])
        else:
            out.update(title="이어서 열 단원이 없습니다", line="문제집이나 복습에서 더 연습할 수 있습니다.")
        return out
    if kind == "again":
        out.update(title="오늘 틀린 문항 %d개가 남았습니다" % item["count"],
                   line="복습 묶음 맨 앞에 나옵니다. 두 번 이어 맞히면 오늘은 더 나오지 않습니다.", action="복습 시작")
    elif kind == "review":
        out.update(title=due_part(item["count"]), line="며칠 전에 푼 문항을 다시 풀 날이 되었습니다.", action="복습 시작")
    elif kind == "unit":
        title, name = unit_task(item, overview)
        why = unit_why(item, overview, today)
        out.update(title=title, line="「%s」\n%s" % (name, why) if name else why, action="학습 시작")
    elif kind == "revisit":  # 단원 이름(name)은 서비스가 차시·상황별 코드 모두 한 규칙으로 줌
        out.update(title=item.get("name") or item["title"], line="읽은 단원 가운데 덜 외운 단원입니다. 외울 것을 떠올려 본 뒤 섞어 풉니다.",
                   action="다시 보기")
    elif kind == "mock":
        out.update(title=item["title"], line='제출한 뒤 정답과 해설을 확인합니다. 중간에 나가도 시간은 계속 흐릅니다.',
                   action='모의고사 열기', mock=item['mock'])
    else:
        out.update(kind="none", title="아직 공개된 단원이 없습니다", line="새 차시가 올라오면 여기에 나옵니다.")
    return out


def find_unit(item, overview):
    """item 이 가리키는 (차시나 상황별 코드 무리 줄, 단원 줄). overview 의 lessons 와 patterns 에서 찾고 없으면 빈 dict."""
    rows = list(overview["lessons"]) + list(overview.get("patterns") or [])
    lesson = next((row for row in rows if row["id"] == item["lesson"]), {})
    unit = next((u for u in lesson.get("units", []) if u["key"] == item["unit"]), {})
    return lesson, unit


def unit_place(item, overview):
    """안 읽은 단원의 자리. 차시 단원은 "1차시 첫째 단원", 상황별 코드 단원은 단원 이름 규칙의 앞머리(index 단원 name)로
    "학습 루프 단원". 카드 제목과 허브 줄이 같이 써서 둘이 같은 단원을 말함. 단원을 찾지 못하면 빈 글."""
    lesson, unit = find_unit(item, overview)
    if unit.get("name"):
        return "%s 단원" % unit["name"]
    if lesson.get("no") and unit:
        n = [u["key"] for u in lesson["units"]].index(item["unit"])
        return "%s %s 단원" % (lesson_title(lesson["no"], "", lesson.get("course", "intro")), ORDINALS[n] if n < len(ORDINALS) else "%d번째" % (n + 1))
    return ""


def unit_task(item, overview):
    """안 읽은 단원 카드의 (제목, 단원 제목). 제목은 할 일을 씀("1차시 첫째 단원 읽기"). 단원 제목은 카드 둘째 줄 맨 앞에 둠.
    단원을 찾지 못하면 서비스가 준 단원 이름."""
    place = unit_place(item, overview)
    if place:
        return "%s 읽기" % place, find_unit(item, overview)[1].get("title", "")
    return item.get("name") or item["title"], ""


def unit_why(item, overview, today):
    """안 읽은 단원을 권하는 줄. 어제나 오늘 수업한 차시면 그 말을 앞에 붙임. 수업 날과 읽는 시간은 overview 의 차시 줄에서,
    상황별 코드 단원은 patterns 줄에서 읽음(수업 날이 없음)."""
    lesson, unit = find_unit(item, overview)
    head = ""
    try:
        held = datetime.date.fromisoformat(str(lesson.get("date") or ""))
    except ValueError:
        held = None
    if held == today:
        head = "오늘 수업한 차시입니다. "
    elif held is not None and held == today - datetime.timedelta(days=1):
        head = "어제 수업한 차시입니다. "
    return "%s읽은 뒤 이 단원 문항부터 풉니다. 약 %d분." % (head, int(unit.get("minutes") or 5))


# 허브 최근 채점 줄

def recent_label(entry):
    """허브 최근 채점 줄. 연습은 처음 답에 맞힌 수 / 문항 수로 모의고사 줄과 같은 꼴."""
    label = "%s %s" % (TRACK, COURSES[entry["course"]]) if entry.get("course") in COURSES else TRACK
    if entry["kind"] == "set":
        return "%s 연습 %d/%d" % (label, entry.get("first_pass") or 0, entry.get("n") or 0)
    return "%s 모의고사 %s/%s" % (label, entry.get("score"), entry.get("of"))


# 연습 묶음 끝 요약(설계 2.7)

def review_next(upcoming):
    """빈 자동 복습의 다음 날짜나 직접 더 연습할 길을 안내함."""
    if upcoming:
        return "다음 복습: %s %d문항" % (upcoming["text"], upcoming["count"])
    return "차시 문제집이나 섞어 풀기에서 더 연습할 수 있습니다."


def summary_head(summary):
    return "%d문항 가운데 %d문항을 처음 답에 맞혔습니다." % (summary["n"], summary["first_pass"])


def summary_lines(summary, unlisted=0):
    """끝 요약의 글 줄들(위에서 아래로). unlisted 는 처음 답이 틀렸지만 단원을 읽은 날이라 오답 노트에 넣지 않은 문항 수."""
    lines = []
    if summary["first_today"]:
        lines.append("오늘 새로 접한 문항 중 이번 묶음에서 마친 문항 %d개" % summary["first_today"])
    if summary["again_day"]:
        lines.append("이전 학습일에 풀었던 문항 중 이번 첫 답에 맞힌 문항 %d개" % summary["again_day"])
    if summary["up"] or summary["down"]:
        lines.append("복습 간격이 늘어난 문항 %d개 · 줄어든 문항 %d개" % (summary["up"], summary["down"]))
    if summary["memorised"]:
        lines.append("복습 기준을 충족한 묶음 %d개" % summary["memorised"])
    if summary["sure_wrong"]:
        lines.append("확실하다고 했지만 틀린 문항 %d개" % summary["sure_wrong"])
    if summary["left"]:
        lines.append("네 번 틀려 오늘 다시 볼 문항 %d개" % len(summary["left"]))
    if summary["next"]:
        lines.append("다음 복습: %s %d문항" % (summary["next"]["text"], summary["next"]["count"]))
    if summary["early"]:
        lines.append(EARLY % summary["early"])
    if unlisted:
        lines.append("단원을 읽은 날 틀린 %d문항은 오답 노트에 넣지 않고 다음 복습에서 다시 냅니다." % unlisted)
    return lines


def requeue_line(passed, gap):
    """방금 답한 문항이 묶음 뒤에 다시 들어갔을 때의 줄. gap 은 사이에 놓인 문항 수."""
    when = "바로 다음에" if gap == 0 else "%d문항 뒤에" % gap
    if passed:
        return "한 번 더 맞히면 이 묶음에서 빠집니다. 이 문항은 %s 다시 나옵니다." % when
    return "이 문항은 %s 다시 나옵니다." % when


# 오답 노트 공급자(설계 2.11)

class AiNotes:
    """AI 비전 개론의 오답 공급자. 연습 차시로 묶어 줌(AiSession.wrong_notes). 창이 세션보다 먼저 만들고 win.ai 는 문제 받기 뒤 바뀜."""
    tid, name = "ai", TRACK
    EMPTY = "아직 틀린 문항이 없습니다. 단원을 읽은 날 틀린 문항은 여기에 넣지 않고 다음 복습에서 다시 냅니다."

    def __init__(self, win):
        self.win = win

    @property
    def empty(self):
        if self.win.ai is None and self.win.ai_error:
            return self.win.ai_error
        return self.EMPTY

    def groups(self):
        """묶음 이름이 이미 차시를 말하므로 문항 줄에는 꼴과 문제 첫머리를 씀."""
        if self.win.ai is None:
            return []
        try:
            groups = self.win.ai.wrong_notes()
        except SessionError:  # 깨진 기록은 허브와 홈의 띠가 알림
            return []
        return [dict(group, items=numbered([dict(item, label=self.label(item)) for item in group["items"]])) for group in groups]

    def label(self, item):
        kind = item["label"].split(" · ")[0]
        try:
            card = self.win.ai.card_info(item["key"])
            if card["kind"] == "stmt":  # 문장 카드는 틀린 문장에 따라 꼴과 첫머리가 바뀜
                note = self.win.ai.wrong_item(item["key"])
                return "%s · %s" % ("빈칸" if note["kind"] == "blank" else kind, stmt_head(card, note))
        except SessionError:
            return item["label"]
        return "%s · %s" % (kind, card_head(card, self.win.ai))

    def detail(self, note, info):
        """(제목, 본문 HTML). 제목은 그 문항이 나온 단원의 이름("5차시 · 단원", "학습 루프 · 단원"). 읽지 못하면 AiError(SessionError)."""
        item = self.win.ai.wrong_item(note["key"])
        item["note_target"] = self.win.ai.note_target(note["key"])
        return item.get("name") or item["title"], note_html(item, info, answer_word(item))

    def open_reference(self, note):
        from gui.ai_learn import NoteDialog
        target = self.win.ai.note_target(note["key"])
        if target is None:
            return
        self.reference_dialog = NoteDialog(self.win, target["lesson"], target["step"])
        self.reference_dialog.open()

    def explain(self, note):
        return self.win.ai.explain(note["key"])

    def retry(self, note):
        self.win.open_ai_practice("note", card=note["key"])


def numbered(items):
    """줄 글이 같은 문항이 둘 이상이면 카드 id 순서로 (1)·(2) 를 붙임. 같은 주제의 문장 카드와 같은 단원의 생성기가 겹침."""
    keys = {}
    for item in items:
        keys.setdefault(item["label"], []).append(item["key"])
    for item in items:
        same = sorted(keys[item["label"]])
        if len(same) > 1:
            item["label"] = "%s (%d)" % (item["label"], same.index(item["key"]) + 1)
    return items


def answer_word(item):
    """정답 줄 머리. item 은 wrong_item 결과. 옳지 않은 것을 고르는 문항의 답은 거짓 문장이라 "정답" 이라 쓰지 않음."""
    return "옳지 않은 문장" if item.get("kind") == "choice" and item.get("pick") == "wrong" else "정답"


def card_head(card, sess):
    """문항 줄에 쓰는 문제 첫머리. 생성기는 단원 제목, 뼈대 카드는 서비스가 만든 head(빈칸은 주 자리 줄을 가린 꼴
    `opt.____()`, 고르기는 지문 첫 줄), 나머지는 지문의 첫 글 줄. 문장 카드는 stmt_head."""
    if card["kind"] == "skel":
        return card.get("head", "")
    if card["kind"] == "gen":
        unit = sess.notes.get(card["lesson"], {}).get("units", {}).get(card["unit"])
        return unit["title"] if unit else ""
    return first_line((card.get("item") or {}).get("stem", ""))


def stmt_head(card, note):
    """문장 카드 줄의 첫머리. 문장이 곧 답인 판(빈칸판·고르기판)은 지문 첫 줄을 쓰고, 맞는지 묻는 판만 문장을 씀."""
    if note["kind"] == "blank" or note["options"]:
        return first_line(note["stem"])
    return plain(card["stmt"].get("text", ""))


def first_line(stem):
    return next((plain(line).strip() for line in stem.split("\n") if line.strip() and not bank.FENCE.match(line)), "")


BAND = (32, 4)  # gui/wrong_page.py 의 BAND 와 같은 띠 여백


def note_html(item, info, word="정답"):
    """오답 노트 문항 칸. 결과 줄, 근거, 문제, 내 답, 펴면 정답과 해설. 근거는 정답을 알려 주지 않아 파이썬 탭처럼 문제 앞에 둠.
    word 는 정답 줄 머리(answer_word). 지문은 코드 울타리 안 빈칸에도 ①② 를 붙임(이 칸에는 CodeSlots 가 없어 어느 칸이 어느
    답인지 번호로만 알 수 있음). 보기가 코드(code_options, 뼈대 고르기 카드)면 보기·내 답·정답을 줄을 지킨 코드 상자로 그리고 보기
    풀이는 보기 번호로 이음."""
    lines = item["lines"] or ["틀림"]
    code = bool(item.get("code_options"))
    options = item["options"]
    parts = ['<p><b>%s</b></p>' % html.escape(" · ".join(lines))]
    if item.get("note_target"):
        parts += [band("참고", space=BAND), '<p><a href="study-note">%s</a></p>' % html.escape(item["note_target"]["label"])]
    parts += [band("문제", space=BAND), md_html(bank.number_blanks(item["stem"], code=True))]
    if options and code:
        parts += ["<p>%d번</p>%s" % (n + 1, code_box(text)) for n, text in enumerate(options)]
    elif options:
        parts.append("<p>%s</p>" % "<br/>".join("%d. %s" % (n + 1, mdlite.inline_html(text)) for n, text in enumerate(options)))
    parts.append(band("내 답", space=BAND))
    if item["mine"] is None:
        parts.append("<p>이 컴퓨터에 남은 답이 없습니다.</p>")
    elif code:  # 고른 보기는 코드 상자, [모르겠어요] 같은 글은 문단
        parts += [code_box(text) if text in options else "<p>%s</p>" % html.escape(text) for text in item["mine"]] or ["<p>(비움)</p>"]
    else:
        parts.append("<p>%s</p>" % "<br/>".join(mdlite.inline_html(text) or "(비움)" for text in item["mine"]))
    if info is not None:
        parts.append(band("정답과 해설", "answer", BAND))
        if code:
            parts += ["<p><b>%s</b></p>" % word] + [code_box(a) for a in info["answer"]]
        else:
            parts.append("<p><b>%s: %s</b></p>" % (word, ", ".join(mdlite.inline_html(a) for a in info["answer"])))
        if info.get("explain"):
            parts.append("<p>%s</p>" % mdlite.inline_html(teaching_text(info["explain"])))
        whys = [(text, teaching_text(why)) for text, why in (info.get("why") or {}).items() if why]
        if whys and code:
            parts.append("<p>%s</p>" % "<br/>".join("%d번: %s" % (options.index(text) + 1, mdlite.inline_html(why))
                                                     for text, why in whys if text in options))
        elif whys:
            parts.append("<p>%s</p>" % "<br/>".join("%s: %s" % (mdlite.inline_html(text), mdlite.inline_html(why)) for text, why in whys))
    return "<body>%s</body>" % "".join(parts)
