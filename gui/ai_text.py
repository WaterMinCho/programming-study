# -*- coding: utf-8 -*-
"""AI 비전 개론 화면의 글. 서비스(aiprep.service)가 준 값을 화면 글로 바꾸고, 공유 오답 노트 화면에 붙는 공급자 AiNotes 를 둠.

하루 목표, 목표 단원 수, 새 문항 상한은 화면에 쓰지 않음(2026-11-03 사용자 결정: 문제집을 원하는 만큼 푸는 꼴). 복습 날짜가 된 문항 수와
외운 문항 수는 알림으로만 씀. 내부 id(i05, 5c, 상자 3)는 화면에 쓰지 않음."""
import datetime
import html
import re

import mdlite
from aiprep import bank
from gui.result_page import band, md_html
from session import SessionError

TRACK = "AI 비전 개론"
ABOUT = "차시마다 학습 단원을 읽고 빈칸·고르기 문제를 풉니다. 맞힌 문항도 며칠 간격을 두고 다시 나옵니다."
TERMS = ("복습 문항은 다시 풀 날이 된 문항입니다. 서로 다른 세 날에 그날 처음 낸 답을 연달아 맞히면 외운 문항이 됩니다. "
         "단원을 읽은 날은 세지 않습니다.")
START_LINE = "1차시 첫 단원부터 시작합니다."
MIXED_ABOUT = "읽은 단원의 문항을 차시를 섞어 20문항씩 냅니다. 복습 문항이 먼저 나옵니다."
MIXED_EMPTY = "단원을 하나 읽으면 섞어 풀 수 있습니다."
LESSON_PRACTICE = "단원을 읽지 않아도 이 차시의 모든 문항을 20문항씩 냅니다."
PREPARING = "준비 중"
BOOK = "%d차시 문제집"
NOTES_ROW = "오답 노트"
BROKEN = "읽지 못한 차시가 있습니다: %s. [새 문제 받기]로 최신 판을 받은 뒤 다시 열어 보세요."
FIX_HINT = "파일을 고친 뒤 프로그램을 다시 실행해 주세요."
GUESS_LATER = "%d단계에서 답을 확인합니다."
RECALL_HEAD = "떠올리기"
WHY_HEAD = "왜일까요?"
REVEAL_HEAD = "짐작 확인"
MEMO_HINT = "답을 떠올린 뒤 질문을 눌러 맞춰 보세요."
RECALL_EMPTY = "답을 적은 뒤 [확인]을 누르세요."
BLOCK_BROKEN = "이 부분을 읽지 못했습니다. [새 문제 받기]로 최신 판을 받아 보세요."
TRAINED = "다시 읽기보다 문제를 풀 때 1주 뒤에 더 많이 기억합니다."
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
MOCK_LATER = "모의고사 화면은 아직 없습니다. [새 문제 받기]로 새 판을 받으면 열립니다."
NUMBERS = bank.NUMBERS


def plain(text):
    """인라인 마크다운(`코드`, **굵게**)을 꾸밈 없는 글자로."""
    return mdlite.inline_plain(text or "")


def number_mark(n):
    """빈칸 번호 글자. 1 → ①."""
    return NUMBERS[n - 1] if 1 <= n <= len(NUMBERS) else "(%d)" % n


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
    """정정 한 줄. 강의 자료의 어느 곳을 바로잡았는지만 쓰고 바른 내용은 해설이 말함."""
    places = [ref_one(e["where"]) for e in errata if e.get("where")]
    where = " · ".join(dict.fromkeys(places))
    if where:
        return "강의 자료(%s)에 틀린 곳이 있어 바로잡은 내용으로 냈습니다. 해설을 보고 외우세요." % where
    return "강의 자료에 틀린 곳이 있어 바로잡은 내용으로 냈습니다. 해설을 보고 외우세요."


# 날짜

def md(day):
    return "%d월 %d일" % (day.month, day.day)


def exam_line(overview, today):
    """홈 제목 아래 알림 줄. 시험까지 남은 날, 오늘 푼 문항, 외운 문항."""
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
    """외운 문항 조각("외운 문항 3/52"). 허브·홈·문제집·단원 줄이 모두 이 꼴로 씀."""
    return "외운 문항 %d/%d" % (row["memorised"], row["families"])


def due_part(count):
    return "복습 %d문항" % count


# 허브와 홈의 줄

def read_counts(overview):
    """(공개된 단원 수, 읽은 단원 수)."""
    ready = [row for row in overview["lessons"] if row["ready"]]
    return sum(row["units_total"] for row in ready), sum(row["read"] for row in ready)


def track_line(overview):
    """허브의 AI 비전 개론 줄 둘째 줄. 읽은 단원이 없으면 첫 단원 안내."""
    total, read = read_counts(overview)
    if not read:
        return START_LINE
    parts = ["단원 %d개 중 %d개 읽음" % (total, read)]
    if overview["memorised"]:
        parts.append(memorised_part(overview))
    if overview["due"]:
        parts.append(due_part(overview["due"]))
    return " · ".join(parts)


def lesson_line(row):
    """학습 단원 구역의 차시 줄 둘째 줄. 읽은 단원 수만 쓰고 외운 문항과 복습은 문제집 줄이 씀."""
    return "단원 %d개 중 %d개 읽음" % (row["units_total"], row["read"])


def lesson_dot(row):
    """차시 줄 점. 안 읽음은 빈 원, 읽는 중은 채운 원, 다 읽음은 체크. 둘째 줄 글로도 나뉨."""
    if row["units_total"] and row["read"] >= row["units_total"]:
        return "done"
    return "progress" if row["read"] else "todo"


def book_line(row):
    """문제집 구역의 차시 문제집 줄 둘째 줄. "외운 문항 3/52 · 복습 6문항"."""
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
    """단원 줄 둘째 줄. "읽음 · 외운 문항 3/9 · 복습 2문항 · 약 5분" 또는 "안 읽음 · 약 5분"."""
    parts = ["읽음" if unit["read"] else "안 읽음"]
    if unit["read"]:
        parts.append(memorised_part(unit))
        if unit["due"]:
            parts.append(due_part(unit["due"]))
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
    item = overview["next"]
    kind = item["kind"]
    out = {"kind": kind, "lesson": item.get("lesson"), "unit": item.get("unit"), "title": "", "line": "", "action": ""}
    if kind == "again":
        out.update(title="오늘 틀린 문항 %d개가 남았습니다" % item["count"],
                   line="복습 묶음 맨 앞에 나옵니다. 두 번 이어 맞히면 오늘은 더 나오지 않습니다.", action="복습 시작")
    elif kind == "review":
        out.update(title=due_part(item["count"]), line="며칠 전에 푼 문항을 다시 풀 날이 되었습니다.", action="복습 시작")
    elif kind == "unit":
        out.update(title=item["title"], line=unit_why(item, overview, today), action="학습 시작")
    elif kind == "revisit":
        lesson = next((row for row in overview["lessons"] if row["id"] == item["lesson"]), None)
        unit = next((u for u in (lesson or {}).get("units", []) if u["key"] == item["unit"]), None)
        name = "%d차시 · %s" % (lesson["no"], unit["title"]) if lesson and unit else item["title"]
        out.update(title=name, line="읽은 단원 가운데 덜 외운 단원입니다. 외울 것을 떠올려 본 뒤 섞어 풉니다.", action="다시 보기")
    elif kind == "mock":  # 모의고사 화면이 생기기 전에 엔진이 회차를 권하면 할 일 단추 없이 안내만 둠
        out.update(title=item["title"], line=MOCK_LATER)
    else:
        out.update(kind="none", title="아직 공개된 단원이 없습니다", line="새 차시가 올라오면 여기에 나옵니다.")
    return out


def unit_why(item, overview, today):
    """안 읽은 단원을 권하는 줄. 어제나 오늘 수업한 차시면 그 말을 앞에 붙임. 수업 날과 읽는 시간은 overview 의 차시 줄에서 읽음."""
    lesson = next((row for row in overview["lessons"] if row["id"] == item["lesson"]), {})
    unit = next((u for u in lesson.get("units", []) if u["key"] == item["unit"]), {})
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
    if entry["kind"] == "set":
        return "%s 연습 %d/%d" % (TRACK, entry.get("first_pass") or 0, entry.get("n") or 0)
    return "%s 모의고사 %s/%s" % (TRACK, entry.get("score"), entry.get("of"))


# 연습 묶음 끝 요약(설계 2.7)

def summary_head(summary):
    return "%d문항 가운데 %d문항을 처음 답에 맞혔습니다." % (summary["n"], summary["first_pass"])


def summary_lines(summary, unlisted=0):
    """끝 요약의 글 줄들(위에서 아래로). unlisted 는 처음 답이 틀렸지만 단원을 읽은 날이라 오답 노트에 넣지 않은 문항 수."""
    lines = []
    if summary["first_today"]:
        lines.append("오늘 처음 푼 문항 가운데 맞힌 문항 %d개" % summary["first_today"])
    if summary["again_day"]:
        lines.append("다른 날 풀었던 문항 가운데 다시 맞힌 문항 %d개" % summary["again_day"])
    if summary["up"] or summary["down"]:
        lines.append("복습 간격이 늘어난 문항 %d개 · 줄어든 문항 %d개" % (summary["up"], summary["down"]))
    if summary["memorised"]:
        lines.append("새로 외운 문항 %d개" % summary["memorised"])
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
        return [dict(group, items=[dict(item, label=self.label(item)) for item in group["items"]]) for group in groups]

    def label(self, item):
        kind = item["label"].split(" · ")[0]
        try:
            card = self.win.ai.card_info(item["key"])
        except SessionError:
            return item["label"]
        return "%s · %s" % (kind, card_head(card, self.win.ai))

    def detail(self, note, info):
        """(제목, 본문 HTML). 제목은 그 문항이 나온 단원. 읽지 못하면 AiError(SessionError)."""
        sess = self.win.ai
        item = sess.wrong_item(note["key"])
        title = item["title"]
        lesson = sess.lessons.get(item.get("lesson"))
        unit = sess.notes.get(item.get("lesson"), {}).get("units", {}).get(sess.card_info(note["key"]).get("unit"))
        if lesson and unit:
            title = "%d차시 · %s" % (lesson["no"], unit["title"])
        return title, note_html(item, info, answer_word(sess.card_info(note["key"])))

    def explain(self, note):
        return self.win.ai.explain(note["key"])

    def retry(self, note):
        self.win.open_ai_practice("note", card=note["key"])


def answer_word(card):
    """정답 줄 머리. 옳지 않은 것을 고르는 문항의 답은 거짓 문장이라 "정답" 이라 쓰지 않음."""
    return "옳지 않은 문장" if card.get("kind") == "choice" and (card.get("item") or {}).get("pick") == "wrong" else "정답"


def card_head(card, sess):
    """문항 줄에 쓰는 문제 첫머리. 문장 카드는 문장, 생성기는 단원 제목, 나머지는 지문의 첫 글 줄."""
    if card["kind"] == "stmt":
        return plain(card["stmt"].get("text", ""))
    if card["kind"] == "gen":
        unit = sess.notes.get(card["lesson"], {}).get("units", {}).get(card["unit"])
        return unit["title"] if unit else ""
    stem = (card.get("item") or {}).get("stem", "")
    return next((plain(line).strip() for line in stem.split("\n") if line.strip() and not bank.FENCE.match(line)), "")


BAND = (32, 4)  # gui/wrong_page.py 의 BAND 와 같은 띠 여백


ONE_DAY_LINE = re.compile(r"^1일에 걸쳐 ")  # 엔진의 "N일에 걸쳐 M번 틀림" 이 하루면 어색해서 뗌. 엔진 문구를 고치면 지움


def note_html(item, info, word="정답"):
    """오답 노트 문항 칸. 결과 줄, 근거, 문제, 내 답, 펴면 정답과 해설. 근거는 정답을 알려 주지 않아 파이썬 탭처럼 문제 앞에 둠.
    word 는 정답 줄 머리(answer_word)."""
    lines = [ONE_DAY_LINE.sub("", line) for line in item["lines"]] or ["틀림"]
    parts = ['<p><b>%s</b></p>' % html.escape(" · ".join(lines))]
    if item["ref"]:
        parts += [band("근거", space=BAND), "<p>%s</p>" % html.escape(ref_text(item["ref"]))]
    parts += [band("문제", space=BAND), md_html(bank.number_blanks(item["stem"]))]
    if item["options"]:
        parts.append("<p>%s</p>" % "<br/>".join("%d. %s" % (n + 1, mdlite.inline_html(text)) for n, text in enumerate(item["options"])))
    parts.append(band("내 답", space=BAND))
    if item["mine"] is None:
        parts.append("<p>이 컴퓨터에 남은 답이 없습니다.</p>")
    else:
        parts.append("<p>%s</p>" % "<br/>".join(mdlite.inline_html(text) or "(비움)" for text in item["mine"]))
    if info is not None:
        parts.append(band("정답과 해설", "answer", BAND))
        parts.append("<p><b>%s: %s</b></p>" % (word, ", ".join(mdlite.inline_html(a) for a in info["answer"])))
        if info.get("explain"):
            parts.append("<p>%s</p>" % mdlite.inline_html(info["explain"]))
        whys = [(text, why) for text, why in (info.get("why") or {}).items() if why]
        if whys:
            parts.append("<p>%s</p>" % "<br/>".join("%s: %s" % (mdlite.inline_html(text), mdlite.inline_html(why)) for text, why in whys))
    return "<body>%s</body>" % "".join(parts)
