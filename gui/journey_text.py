# -*- coding: utf-8 -*-
"""알고리즘 여행 화면과 첫 화면이 같이 쓰는 글자 도우미. 서비스(journey/service.py)가 돌려준 dict 를 화면 낱말로 바꿈.
PyQt 를 가져오지 않으므로 화면 없이 시험함(tests/test_journey_text.py).

낱말은 정해 둔 것만 씀: 던전은 클리어, 문제는 통과, 수강생이 만든 테스트는 내 테스트, 점수 매기기는 채점.
내부 id(d01, p1, meta.json)는 화면 글에 쓰지 않고 도움말과 자세히에만 남김. "던전 4를", "「별빛 항로」을" 처럼 숫자나 이름 뒤 조사가
읽는 법에 따라 바뀌는 자리는 조사 없이 문장을 짬."""
import math
import re

from gui.web_text import minutes_text
from journey.service import ROLE_LABEL

LANG_LABEL = {"python": "Python", "javascript": "JavaScript"}
ACTION = "문제 풀기"  # 이어서 할 일 카드의 단추 글자
TIERS = {"B": "브론즈", "S": "실버", "G": "골드", "P": "플래티넘", "D": "다이아몬드", "R": "루비"}  # 백준 등급 글자
BOJ_TIER = re.compile(r"([BSGPDR])([1-5])(?:~([BSGPDR])([1-5]))?\Z")  # "G3", "G1~P5", "P5~P4"
LEVEL = re.compile(r"Lv([0-5])(?:~([0-5]))?(\s*상)?\Z")  # "Lv2", "Lv3~4", "Lv3 상"

# 결과 카드 머리
NOT_RUN = "아직 실행하지 않았습니다."
RUN_HINT = "[코드 실행]을 누르면 결과가 여기에 나옵니다."
FIRST_PASS = "처음으로 통과했습니다. 해설이 열렸습니다."
BOSS_OPENED = "보스 문제가 열렸습니다."
NO_CODE = "코드를 불러오지 못했습니다"  # 머리 headline 이라 마침표가 없음(결과 수치 줄과 같은 꼴)

# 서비스 오류 창. 제목은 하던 행동의 이름
ACTIONS = {"open": "문제 열기", "hint": "힌트 열기", "explain": "해설 열기", "lang": "언어 바꾸기", "reset": "코드 되돌리기",
           "save": "코드 저장", "run": "코드 실행", "grade": "채점하기"}
REFETCH = "이 문제를 열 수 없습니다. 첫 화면의 [새 문제 받기]로 다시 받은 뒤 여세요."
NO_LANG = "이 언어로는 풀 수 없습니다. Python 이나 JavaScript 를 고르세요."
NO_RECORD = "알고리즘 여행 기록을 저장하지 못했습니다. 기록은 바뀌지 않았습니다. 잠시 뒤 다시 하세요."
# 내부 id 나 은행 파일 이름이 든 서비스·은행 문구. 화면에는 문제를 다시 받으라는 글(REFETCH)을 보임
BANK_PROBLEMS = (re.compile(r"(문제|던전) \S+ 를 찾을 수 없습니다\."), re.compile(r"던전 \S+ 를 읽을 수 없습니다\."),
                 re.compile(r"던전 \S+ 의 봉인 파일을 풀 수 없습니다\."), re.compile(r"^이 문제의 채점 파일"),
                 re.compile(r"\S+\.(json|md|py|js) 을 (읽을|풀) 수 없습니다"))
# 첫 문장은 쉬운 글이고 뒤에 원문(파일 경로, 예외 글)이 붙는 서비스 문구
KEEP_FIRST = ("코드 파일을 읽을 수 없습니다", "코드를 실행하지 못했습니다", "채점하지 못했습니다", "테스트 입력을 만들지 못했습니다",
              "코드를 저장하지 못했습니다", "테스트 케이스를 저장하지 못했습니다")


def score_text(score):
    """결과 카드의 점수. 정수면 소수점을 떼고 아니면 한 자리까지: 100.0 → "100", 41.5 → "41.5"."""
    return ("%.1f" % float(score or 0.0)).rstrip("0").rstrip(".")


def whole_score(score):
    """목록 줄과 첫 화면의 점수. 소수점 아래를 버림: 41.5 → "41"."""
    return "%d" % math.floor(float(score or 0.0))


def place(row):
    """던전 이름 "던전 1 「향신료 시장」". row 는 overview()["dungeons"] 의 줄이나 dungeon() 의 결과."""
    return "던전 %d 「%s」" % (row["no"], row["title"])


def _item(row, pid, title, role):
    return {"did": row["id"], "pid": pid, "title": title, "place": place(row), "role": role, "action": ACTION}


def next_item(service, last="", overview=None):
    """이어서 할 일 {"did", "pid", "title", "place", "role", "action"} 또는 None. role 은 "중급" 같은 역할 이름임.
    last 는 설정 journey/last 의 "던전/문제". 은행에 있는 문제이고 그 던전을 읽을 수 있으면 먼저 봄. 아직 통과 전이고 잠긴 보스가
    아니면 그 문제를 고름. 아니면 서비스 추천(index 순서로 클리어하지 않은 첫 던전의 안 푼 첫 문제)을 고름.
    overview 를 이미 읽었으면 넘겨서 다시 읽지 않음."""
    overview = service.overview() if overview is None else overview
    rows = {row["id"]: row for row in overview["dungeons"]}
    did, _, pid = str(last or "").partition("/")
    if did in rows and rows[did]["ready"]:
        found = next((row for row in service.dungeon(did)["problems"] if row["id"] == pid), None)
        if found and not found["passed"] and not found["locked"]:
            return _item(rows[did], pid, found["title"], found["role_label"])
    target = overview["next"]
    if not target or target["did"] not in rows:
        return None
    return _item(rows[target["did"]], target["pid"], target["title"], ROLE_LABEL.get(target["role"], ""))


def track_line(overview, item):
    """첫 화면 알고리즘 여행 줄의 둘째 줄. item 은 next_item 의 결과: "15문제 중 2개 통과 · 다음은 대상단 하루 일정"."""
    if item:
        tail = "다음은 %s" % item["title"]
    elif overview["total"]:
        tail = "모두 클리어했습니다."
    else:
        tail = "아직 준비된 던전이 없습니다."
    return "%d문제 중 %d개 통과 · %s" % (overview["total"], overview["passed"], tail)


def map_count(overview):
    """지도 구역 이름 옆 caption. "15문제 중 8개 통과 · 클리어 1개"."""
    return "%d문제 중 %d개 통과 · 클리어 %d개" % (overview["total"], overview["passed"], overview["cleared"])


def dungeon_count(info):
    """던전 구역 이름 옆 caption. "6문제 중 2개 통과". 준비 중이거나 읽지 못한 던전은 빈 글."""
    return "%d문제 중 %d개 통과" % (info["total"], info["passed"]) if info["ready"] else ""


def dungeon_lines(info, numbers):
    """던전 카드 맨 위 보조 줄 한두 개. 첫 줄은 주제와 보스 난이도임. 권장 선행 던전이 있으면 둘째 줄에 씀.
    numbers 는 {던전 id: 번호} 이고 번호를 모르는 id 는 건너뜀."""
    first = "%s · 보스 난이도 %s" % (info["topic"], info["boss_target"])
    lines = ["최종 던전 · " + first if info.get("final") else first]
    before = [str(numbers[did]) for did in info.get("prereq") or [] if did in numbers]
    if before:
        lines.append("던전 %s 다음에 풀면 좋습니다." % ", ".join(before))
    return lines


def node_tip(row):
    """지도 원의 도움말. row 는 overview()["dungeons"] 의 줄. 열린 던전은 "던전 1 「향신료 시장」 · 해시·투 포인터 · 6문제 중 2개 통과",
    준비 중인 던전은 "… · 준비 중", 읽지 못한 던전은 "… · 열 수 없음" 이고 마지막 던전은 앞에 "최종 던전 · " 을 붙임."""
    if row.get("error"):
        tail = "열 수 없음"
    elif not row["ready"]:
        tail = "준비 중"
    else:
        tail = "%s · %d문제 중 %d개 통과" % (row["topic"], row["total"], row["passed"])
    return "%s%s · %s" % ("최종 던전 · " if row.get("final") else "", place(row), tail)


def row_line(row, info):
    """문제 목록 줄의 둘째 줄. 번호 · 난이도 · 상태 · 준비 문제 순서이고 보스는 번호를 뺌. 잠긴 보스는 여는 조건을 씀.
    row 는 dungeon()["problems"] 의 줄, info 는 그 dungeon() 결과."""
    if row["locked"]:
        text = "중급 %d개를 모두 통과하면 열립니다." % info["mid_total"]
        return text + (" 지금 %d개 통과했습니다." % info["mid_passed"] if info["mid_passed"] else "")
    parts = [] if row["role"] == "boss" else [row["no"]]
    parts.append(row["tier"])
    if row["passed"]:
        parts.append("해설 보고 통과" if row["explained_first"] else "통과")
        if row["passed_langs"]:
            parts.append(", ".join(LANG_LABEL.get(lang, lang) for lang in row["passed_langs"]))
    elif row["tried"]:
        parts.append("최고 %s점" % whole_score(max(list(row["best"].values()) or [0.0])))
    if row["prep"]:
        parts.append("준비 문제 " + ", ".join(ref["no"] for ref in row["prep"]))
    return " · ".join(parts)


def tier_tip(tier, boss=False):
    """난이도 꼬리표("S3 / Lv2")의 도움말. 백준 등급과 프로그래머스 레벨을 풀어 씀. boss 면 앞에 "보스 문제는" 을 붙임.
    "G1~P5" 는 골드 1~플래티넘 5, "P5~P4" 는 플래티넘 5~4, "Lv3 상" 은 레벨 3 상위로 읽음. 꼴을 모르면 빈 글."""
    boj, _, level = str(tier or "").partition("/")
    found_boj, found_level = BOJ_TIER.match(boj.strip()), LEVEL.match(level.strip())
    if not found_boj or not found_level:
        return ""
    first, number, last, last_number = found_boj.groups()
    boj_text = "%s %s" % (TIERS[first], number)
    if last:
        boj_text += "~" + (last_number if last == first else "%s %s" % (TIERS[last], last_number))
    low, high, upper = found_level.groups()
    level_text = "레벨 %s%s%s" % (low, "~" + high if high else "", " 상위" if upper else "")
    return "%s백준 %s, 프로그래머스 %s 수준입니다." % ("보스 문제는 " if boss else "", boj_text, level_text)


def _line_hint(fatal):
    return "%d번째 줄을 확인하세요." % fatal["line"] if fatal.get("line") else ""


def result_head(kind=None, result=None, done=True, best=None, mine=0, stage="", seconds=0):
    """결과 카드 머리 {"title", "caption", "bar", "tone", "banners"}.
    kind 는 "run"·"grade" 이고 None 이면 아직 결과가 없는 접힌 카드임. best 는 지금 언어의 최고 점수(기록이 없으면 None),
    mine 은 내 테스트 수. done=False 는 진행 중이고 result 는 그때까지 온 줄임(실행이면 전체 수 total 도 넣음).
    stage 는 채점 단계 문장(grading 의 GEN_TEXT, ACC_TEXT, EFF_TEXT), seconds 는 채점을 시작한 뒤 지난 초.
    bar 는 None(숨김), "busy"(끝을 모르는 반복 막대), (값, 최댓값) 가운데 하나이고 tone 이 "success" 면 초록 막대.
    banners 는 완료 띠 [(글, 단추 글자, 행동 키)]이고 행동 키는 "explain"(해설 탭)과 "boss"(보스 문제)."""
    head = {"title": "", "caption": "", "bar": None, "tone": "", "banners": []}
    result = result or {}
    if kind is None:
        if best is not None:
            caption = "지금까지 최고 점수는 100점 중 %s점입니다." % score_text(best)
        elif mine:
            caption = "[코드 실행]은 입출력 예와 내 테스트 %d개를 돌립니다." % mine
        else:
            caption = RUN_HINT
        return dict(head, title=NOT_RUN, caption=caption)
    if kind == "run":
        total, cases = result.get("total") or 0, result.get("cases") or []
        if not done:
            return dict(head, title="실행 중", bar=(len(cases), total), caption="테스트 %d개 중 %d개 끝남" % (total, len(cases)))
        if result.get("cancelled"):
            return dict(head, title="실행을 멈췄습니다", caption="끝난 테스트까지만 보입니다.")
        if result.get("fatal"):
            return dict(head, title=NO_CODE, caption=_line_hint(result["fatal"]))
        passed = result.get("passed") or 0
        title = "테스트 %d개 중 %d개 통과" % (total, passed)
        if passed == total:
            return dict(head, title=title, bar=(passed, total), tone="success", caption="[채점하기]로 숨은 테스트까지 채점하세요.")
        return dict(head, title=title, bar=(passed, total), caption="고친 뒤 다시 실행하세요.")
    if not done:
        caption = stage + (" %s 지났습니다." % minutes_text(seconds) if seconds else "") if stage else "채점을 준비하는 중입니다."
        return dict(head, title="채점 중", bar="busy", caption=caption)
    if result.get("cancelled"):
        return dict(head, title="채점을 멈췄습니다", caption="이번 채점은 기록에 남지 않습니다.")
    if result.get("fatal"):
        return dict(head, title=NO_CODE, caption=" ".join(part for part in ("0점으로 기록했습니다.", _line_hint(result["fatal"])) if part))
    score = float(result.get("score") or 0.0)
    caption = " · ".join("%s %s / %s" % (group["name"], score_text(group["earned"]), score_text(group["points"]))
                         for group in result.get("groups") or [])
    banners = []
    if result.get("first_pass"):
        banners.append((FIRST_PASS, "해설 보기", "explain"))
    if result.get("boss_opened"):
        banners.append((BOSS_OPENED, "보스 풀기", "boss"))
    return dict(head, title="100점 중 %s점" % score_text(score), bar=(score, 100.0), tone="success" if score >= 100 else "",
                caption=caption, banners=banners)


def clear_text(title, following=None):
    """던전 클리어 창의 글. following 은 다음 던전의 이름이고 None 이면 준비된 던전을 모두 클리어한 것임.
    조사를 이름 뒤가 아니라 "던전" 뒤에 붙여 이름마다 을·를이 바뀌지 않게 함."""
    text = "「%s」 던전을 클리어했습니다." % title
    if following:
        return text + " 다음은 「%s」 던전입니다." % following
    return text + " 준비된 던전을 모두 클리어했습니다."


def bank_text(overview):
    """읽지 못한 던전을 알리는 주의 띠의 (글, 도움말). 도움말은 서비스가 남긴 원문이고, 읽지 못한 던전이 없으면 ("", "")."""
    broken = [str(row["no"]) for row in overview["dungeons"] if row.get("error")]
    if not broken:
        return "", ""
    text = "읽지 못한 던전이 있습니다: 던전 %s. 첫 화면의 [새 문제 받기]로 다시 받은 뒤 여세요." % ", ".join(broken)
    return text, "\n".join(overview.get("bank_errors") or [])


def error_text(action, message):
    """서비스 오류 창의 (제목, 글, 자세히). 제목은 하던 행동의 이름("문제 열기")이고 action 은 ACTIONS 의 키.
    내부 id 나 은행 파일 이름이 든 문구는 쉬운 글로 바꾸고 원문은 자세히로 넘김. 첫 문장 뒤에 원문이 붙은 문구는 첫 문장만 남김.
    잠긴 보스, 힌트를 다 연 경우처럼 쉬운 글로 된 나머지 문구는 그대로 둠."""
    title, message = ACTIONS.get(action, "알림"), str(message or "")
    if message.startswith("알고리즘 여행 기록을 저장하지 못했습니다."):
        return title, NO_RECORD, message.partition("\n")[2].strip()
    if message.startswith("언어는 python 이나 javascript"):
        return title, NO_LANG, message
    for first in KEEP_FIRST:
        if message.startswith(first):
            return title, first + ".", message[len(first):].lstrip(".:").strip()
    if any(pattern.search(message) for pattern in BANK_PROBLEMS):
        return title, REFETCH, message
    return title, message, ""
