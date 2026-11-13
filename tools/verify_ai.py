#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 비전 개론 문항 묶음·학습 노트 블록·그림·서명 검증(설계 4.6, 8.7). 실패가 하나라도 있으면 1 로 끝남.

  python tools/verify_ai.py [i05 common pc ...]        출제된 문항 묶음 전부(또는 적은 것)를 봄. pc 는 상황별 코드(뼈대 카드)
  python tools/verify_ai.py i05 --seeds 50             생성기를 50 시드만 돌림(기본 300)
  python tools/verify_ai.py i05 --answers FILE         재풀이 답안(ai_seal.py brief 가 만든 answers.json)을 채점함
  python tools/verify_ai.py --levels-answers FILE      세 수준 물음 재풀이 답안(ai_seal.py levels 가 만든 levels_answers.json)을 채점함
  python tools/verify_ai.py i05 --sign --writer "출제 1" --resolver "재풀이 2" --checker "대조 3" --reviewer "검토 4"
                            [--first-pass FILE | --keep-first-pass] [--finding 글 ...]
                                                       검증을 통과하면 work/review.json 을 씀(그 뒤 ai_seal.py seal)
  python tools/verify_ai.py --require-review           문항 묶음·공용 생성기·모의고사 서명이 없거나 서명 뒤 바뀐 파일이 있으면 실패
  python tools/verify_ai.py --overrides | --leeches    submissions 기록에서 [내 답도 맞음] 답과 자주 틀리는 문항을 모아 보임
  python tools/verify_ai.py --sources DIR              강의 폴더의 sha256 을 facts.json sources 와 견줌(출제자 컴퓨터에서만)

그 밖의 옵션: --bank DIR(기본 ai/), --manifest FILE(기본 tools/ai_art/manifest.json). 학습 노트의 글 꼴·말투·맥락과 서명은
verify_web.py --bank ai 와 web_lint.py --bank ai 가 보고, 여기서는 ai-* 블록·프레임 줄·단계 사실 줄·그림 한도와 manifest 를 봄.
세 수준 블록(ai-levels)은 web_lint 가 울타리 안을 건너뛰므로 꼴·수준 규칙·말투는 check_levels, 맥락은 check_levels_context, 그림은
check_level_figure 가 여기서 봄.
검사 번호와 이름은 STEP_NAMES 에 있음. 표준 라이브러리만 씀.

상황별 코드(pc)는 차시와 같은 흐름을 탐. 학습 노트 l18, items/pc 의 facts.json, ai/patterns/S*.json 에서 만든 뼈대 카드를 Lesson
하나로 묶어 check_lesson 을 돌리고, 19 뼈대 검사로 코드 예제·자리·순서·고르기·고칠 줄을 봄. pc 서명은 ai/patterns/*.json 을 모두 덮음.
"""
import argparse
import ast
import collections
import json
import math
import os
import re
import subprocess
import sys
import textwrap
import time
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import bank as aibank  # noqa: E402
from aiprep import gen as genlib  # noqa: E402
from aiprep import grade, review, skel  # noqa: E402
from tools import ai_art, ai_mock_rules, ai_seal, check_style, lecture_locations, verify_web, web_lint  # noqa: E402
from webprep import bank as webbank  # noqa: E402

STEP_NAMES = {1: "목록", 2: "문항 꼴", 3: "빈칸 규칙", 4: "고르기", 5: "문장", 6: "생성기", 7: "사실 확인", 8: "노트 블록", 9: "근거",
              10: "말투", 11: "맥락", 12: "모의고사", 13: "그림", 14: "한도", 15: "비밀 값", 16: "검토 서명", 17: "재풀이 대조",
              18: "강의 파일", 19: "뼈대"}
VERDICTS = ("맞음", "단순화", "부분적으로 맞음", "버전 차이", "틀림", "확인 못 함")
BAD_VERDICTS = ("틀림", "확인 못 함")
ASK_AS = ("단순화", "부분적으로 맞음")
VALUE_MODES = ("number", "exact", "values")
LONG_API = ("register_full_backward_hook", "ReduceLROnPlateau", "CosineAnnealingLR", "DataCollatorWithPadding")
PARTICLE_TRAP = re.compile(r"_{4,}\s?(을|를|은|는|이|가|과|와)(?=[\s.,?!)]|$)")
POINTING = re.compile(r"^(모두|위의)|[①-④]|위 보기|보기\s*\d")
REF_FORMS = (
    ("lecture", re.compile(r"(?:응용 )?(\d{1,2})차시 슬 p\d+(?:~p?\d+)?\Z")),
    ("lecture", re.compile(r"(?:응용 )?(\d{1,2})차시 노트북 \d{2} \[\d+\]\Z")),
    ("lecture", re.compile(r"(?:응용 )?(\d{1,2})차시 과제 \d+번\Z")),
    ("lecture", re.compile(r"(?:응용 )?(\d{1,2})차시 강의노트 \[\d+\]\Z")),
    ("summary", re.compile(r"요약 (\d)주차 p\d+(?:~p?\d+)?\Z")),
    ("graduate", re.compile(r"대학원 \d{2} p\d+(?:~p?\d+)?\Z")),
    ("official", re.compile(r"공식 (\d{1,2})차시\Z")),
    ("doc", re.compile(r"(?:\S+ )?문서 \S.*\Z")),
)
DEEP_MAX = {"i13": 5, "i14": 5, "i16": 5}
DEEP_DEFAULT = 3
ALLOWED_LICENSES = ("CC0", "PD", "Public Domain", "퍼블릭 도메인", "CC BY 4.0", "CC BY-SA 4.0", "MIT", "BSD-3-Clause")
QUOTED_CLIP_LICENSE = "3Blue1Brown FAQ clip permission (under 60 seconds)"
QUOTED_CLIP_AUTHOR = "3Blue1Brown · Grant Sanderson"
QUOTED_CLIP_PERMISSION = "https://www.3blue1brown.com/about/"
QUOTED_CLIP_URLS = (
    "https://storage.googleapis.com/3blue1brown-website-bucket/lessons/2017/neural-networks/network-propagation.mp4",
    "https://storage.googleapis.com/3blue1brown-website-bucket/lessons/2017/neural-networks/number-line-squish.mp4",
)
SECRET = re.compile(r"sk-[A-Za-z0-9]{8,}|hf_[A-Za-z0-9]{8,}|api_key\s*=|KAGGLE_KEY|(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])")
IMPORT_BAD = re.compile(r"^\s*(?:import|from)\s+(numpy|torch)\b", re.M)
TEXT_EXT = (".py", ".json", ".md", ".txt")
GEN_MS = 50.0
MIN_STEMS = 20
FULL_SEEDS = 100  # 서로 다른 지문 수는 시드를 이만큼 이상 돌릴 때만 봄
STYLE_SAMPLES = 20
IMAGE_REF = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
SKEL_COMMENT = re.compile(r"(^|\s)#")
LEVEL_DIGIT = {7: 1, 15: 2, 20: 3}  # 블록 그림 이름 <단원>-<단계 번호><수준 번호> 의 수준 번호
LEVEL_CHARS = {7: 300, 15: 450, 20: 450}  # 수준 글(코드 뺌) 길이 경고선
LEVEL_PNG = {"bytes": 30 * 1024, "size": (1040, 560)}  # 블록 그림 경고선
SEVEN_SIGNS = re.compile(r"[=×÷+/^√∂Σ²³*<>]|\d\s*[−-]\s*\d")  # 숫자 앞에 붙은 − 는 됨(−4)
LIBRARY = re.compile(r"torch|numpy|(?<![A-Za-z])(?:nn|np)(?![A-Za-z])", re.I)
POLITE = re.compile(r"(?<!세)요\.(?=\s|$)|볼까요|해 봐요")
NUMBER_TEXT = re.compile(r"\d+(?:\.\d+)?")
NUMBER_WORD = re.compile(r"-?\d+(?:\.\d+)?\Z")
FIGURE_NO = re.compile(r"^그림\s*\d")
LEVELS_KEY = re.compile(r"(a?l\d{2}) (a?\d{1,2}[a-i])/(\d+) (\S+) (7|15|20)\Z")


class Verifier(object):
    """실패·경고를 모으고 보여 줌. verify_web.check_review 가 쓰는 fail(label, step, message) 꼴을 맞춤."""

    def __init__(self, opts, out=None):
        self.opts = opts
        self.out = out or sys.stdout
        self.failures, self.warnings = [], []
        self._headed = set()
        self.tools = [("check_style", check_style.check)]

    def say(self, text):
        print(text, file=self.out)

    def head(self, label, title=""):
        if label not in self._headed:
            self._headed.add(label)
            self.say("[%s]%s" % (label, " " + title if title else ""))

    def fail(self, label, step, message):
        self.failures.append((label, step, message))
        self.head(label)
        self.say("  실패 %d %s: %s" % (step, STEP_NAMES.get(step, ""), message))

    def warn(self, label, step, message):
        self.warnings.append((label, step, message))
        self.head(label)
        self.say("  경고 %d %s: %s" % (step, STEP_NAMES.get(step, ""), message))

    def note(self, label, message):
        self.head(label)
        self.say("  " + message)

    def failed(self, label):
        return any(where == label for where, _, _ in self.failures)

    def style(self, label, where, text, markdown=False):
        """학습자에게 보이는 글 하나를 말투 검사기에 넘김. markdown 이면 울타리 코드 블록을 건너뜀."""
        if not text or not str(text).strip():
            return
        report = web_lint.Report(label)
        if markdown:
            web_lint.style_check(report, self.tools, [(where, str(text))], [])
        else:
            web_lint.style_check(report, self.tools, [], [(where, str(text), True)])
        for _, place, rule, found in report.errors:
            self.fail(label, 10, "%s: %s: %s" % (place, rule, found))


def clip(text, limit=60):
    return verify_web.clip(text, limit)


def lesson_no(lid):
    found = aibank.LESSON_ID.match(lid or "")
    return int(found.group(1)) if found else None


# 1. 목록

def check_index(v, bank_dir):
    try:
        index = aibank.read_index(bank_dir)
    except aibank.AiBankError as error:
        v.fail("index", 1, str(error))
        return None
    exam = review.exam_dates(index["exam"])
    if None in exam.values():
        v.fail("index", 1, "exam 날짜(date, last_new, sweep_from, last_review)는 YYYY-MM-DD 여야 합니다.")
    elif not exam["last_new"] < exam["sweep_from"] <= exam["last_review"] < exam["date"]:
        v.fail("index", 1, "exam 날짜 순서는 last_new < sweep_from <= last_review < date 여야 합니다.")
    pages = {p["id"] for p in index["pages"]}
    seen_ids, seen_no = set(), set()
    for lesson in index["lessons"]:
        lid = lesson["id"]
        if lid in seen_ids or (lesson.get("course", "intro"), lesson["no"]) in seen_no:
            v.fail("index", 1, "lessons 에 같은 id 나 no 가 두 번 있습니다: %s" % lid)
        seen_ids.add(lid)
        seen_no.add((lesson.get("course", "intro"), lesson["no"]))
        if lesson["no"] != lesson_no(lid):
            v.fail("index", 1, "%s 의 no 가 id 와 다릅니다: %d" % (lid, lesson["no"]))
        if lesson["page"] not in pages:
            v.fail("index", 1, "%s 의 page %s 가 pages 에 없습니다." % (lid, lesson["page"]))
        else:
            expected_page = ("al%02d" if lesson.get("course") == "app" else "l%02d") % lesson["no"]
            if lesson["page"] != expected_page:
                v.fail("index", 1, "%s 의 page 는 %s 여야 합니다: %s" % (lid, expected_page, lesson["page"]))
        if not lesson["weight"] > 0:
            v.fail("index", 1, "%s 의 weight 는 0 보다 커야 합니다." % lid)
        if lesson["date"] and review.parse_day(lesson["date"]) is None:
            v.fail("index", 1, "%s 의 date 는 YYYY-MM-DD 여야 합니다: %s" % (lid, lesson["date"]))
        if lesson["hw_due"] is not None and review.parse_day(lesson["hw_due"]) is None:
            v.fail("index", 1, "%s 의 hw_due 는 null 이나 YYYY-MM-DD 여야 합니다." % lid)
    for pattern in index["patterns"]:
        if pattern["page"] not in pages:
            v.fail("index", 1, "patterns %s 의 page %s 가 pages 에 없습니다." % (pattern["id"], pattern["page"]))
        for key, unit in pattern["units"].items():
            if not re.match(r"18[a-h]\Z", key):
                v.fail("index", 1, "patterns 의 단원 키는 18a~18h 여야 합니다: %s" % key)
            if unit["after"] and unit["after"] not in seen_ids:
                v.fail("index", 1, "patterns %s 의 after %s 가 lessons 에 없습니다." % (key, unit["after"]))
    nos = sorted(no for course, no in seen_no if course == "intro")
    for mock in index["mocks"]:
        if len(mock["range"]) != 2 or mock["range"][0] > mock["range"][1] or (nos and not (nos[0] <= mock["range"][0]
                                                                                            and mock["range"][1] <= nos[-1])):
            v.fail("index", 1, "%s 의 range 가 차시 범위가 아닙니다: %s" % (mock["id"], mock["range"]))
        days = [review.parse_day(d) for d in mock["window"]]
        if mock["id"] == "m4" and mock.get("scope") == "mixed" and not days:
            continue
        if len(days) != 2 or None in days or days[0] > days[1]:
            v.fail("index", 1, "%s 의 window 는 [시작, 끝] 날짜여야 합니다." % mock["id"])
        elif exam["date"] and days[1] >= exam["date"]:
            v.fail("index", 1, "%s 의 window 가 시험 날짜 전에 끝나야 합니다." % mock["id"])
    return index


# 2~9. 문항 묶음

class Lesson(object):
    """검사하는 차시 하나. entry, note(load_note 결과 또는 None), data(load_items 결과), cards, steps({단원: 단계 목록})."""

    def __init__(self, entry, note, data, cards):
        self.entry, self.note, self.data, self.cards = entry, note, data, cards
        self.id = entry["id"]
        self.units = note["units"] if note else {}
        self.group = None  # 상황별 코드면 index.json patterns 항목
        self.skeletons = {}  # 노트의 ai-diff·ai-rotate·skel 울타리와 뼈대 카드가 쓰는 뼈대


def ref_kind(ref):
    for kind, pattern in REF_FORMS:
        found = pattern.match(ref)
        if found:
            return kind, found.group(1) if pattern.groups else None
    return None, None


def first_ref_ok(ref, no, course="intro"):
    kind, value = ref_kind(ref)
    if kind == "lecture":
        return int(value) == no and ("app" if ref.startswith("응용 ") else "intro") == course
    if kind == "summary":
        week = int(value)
        return course == "intro" and (week - 1) * 5 < no <= week * 5
    return False


def card_texts(card):
    """카드에서 학습자에게 보이는 글 [(어디, 글, 마크다운인지)]. 뼈대 카드는 skel.card_texts."""
    if card["kind"] == "skel":
        return skel.card_texts(card)
    out = []
    cid = card["id"]
    if card["kind"] in ("blank", "choice"):
        item = card["item"]
        out.append(("%s:stem" % cid, item.get("stem", ""), True))
        out.append(("%s:explain" % cid, item.get("explain", ""), True))
        alt = item.get("alt") if isinstance(item.get("alt"), dict) else {}
        for key in ("stem", "explain"):
            if alt.get(key):
                out.append(("%s:alt %s" % (cid, key), alt[key], True))
        for n, option in enumerate(item.get("options") or [], 1):
            out.append(("%s:보기%d" % (cid, n), option.get("text", ""), False))
            out.append(("%s:보기%d why" % (cid, n), option.get("why", ""), False))
        for blank in item.get("blanks") or []:
            out.append(("%s:hint" % cid, blank.get("hint", ""), False))
    elif card["kind"] == "stmt":
        statement = card["stmt"]
        out.append(("%s:text" % cid, statement.get("text", ""), False))
        out.append(("%s:why" % cid, statement.get("why", ""), False))
        if statement.get("cloze"):
            out.append(("%s:cloze" % cid, statement["cloze"].get("text", ""), False))
    return out


def check_alt(v, les, card):
    """바꿔 쓴 문항(alt)은 stem·explain 만 바꾸고 빈칸 수가 같아야 함."""
    alt = (card.get("item") or {}).get("alt")
    if alt is None:
        return
    cid = card["id"]
    if not isinstance(alt, dict) or not set(alt) <= {"stem", "explain"}:
        v.fail(les.id, 2, "%s 의 alt 는 stem·explain 만 바꾸는 객체여야 합니다." % cid)
        return
    if "stem" in alt and len(aibank.BLANK.findall(alt["stem"])) != len(aibank.BLANK.findall(card["item"].get("stem", ""))):
        v.fail(les.id, 2, "%s 의 alt stem 의 빈칸 수가 원래 지문과 다릅니다." % cid)


def check_card_common(v, les, card, ids, retired):
    cid, label = card["id"], les.id
    if card["kind"] == "skel":
        kind_letter = skel.PART_LETTER[card["part"]]
    else:
        kind_letter = {"blank": "b", "choice": "c", "stmt": "s", "gen": "g"}[card["kind"]]
    if not re.match(r"%s-%s\d{2,3}\Z" % (les.id, kind_letter), cid):
        v.fail(label, 2, "%s 의 id 꼴이 %s-%s07 이 아닙니다." % (cid, les.id, kind_letter))
    if cid in ids:
        v.fail(label, 2, "id 가 두 번 쓰였습니다: %s (%s)" % (cid, ids[cid]))
    ids[cid] = les.id
    if cid in retired:
        v.fail(label, 2, "retired.json 에 있는 지운 id 를 다시 썼습니다: %s" % cid)
    unit = les.units.get(card["unit"])
    if unit is None:
        v.fail(label, 2, "%s 의 unit %s 가 학습 노트 sections 에 없습니다." % (cid, card["unit"]))
    if les.group is not None and card["unit"] not in les.group["units"]:
        v.fail(label, 2, "%s 의 unit %s 가 index.json patterns 단원에 없습니다." % (cid, card["unit"]))
    step = card.get("step")
    found = re.match(r"(\w+)/(\d+)\Z", str(step or ""))
    if not found or found.group(1) != card["unit"]:
        v.fail(label, 2, "%s 의 step 은 \"%s/3\" 꼴이어야 합니다: %r" % (cid, card["unit"], step))
    elif unit is not None:
        steps = [s for s in unit["steps"] if s["no"]]
        no = int(found.group(2))
        if not 1 <= no <= len(steps):
            v.fail(label, 2, "%s 의 step %s 단계가 없습니다(단계 %d개)." % (cid, step, len(steps)))
        elif not set(steps[no - 1]["facts"]) & set(card["facts"]):
            v.fail(label, 2, "%s 의 facts 가 step %s 단계의 <!-- facts --> 줄과 겹치지 않습니다." % (cid, step))
    if card["level"] not in (1, 2, 3):
        v.fail(label, 2, "%s 의 level 은 1~3 이어야 합니다." % cid)
    if card["prio"] not in (1, 2, 3):
        v.fail(label, 2, "%s 의 prio 는 1~3 이어야 합니다." % cid)
    if not 1 <= len(card["tags"]) <= 3:
        v.fail(label, 2, "%s 의 tags 는 1~3개여야 합니다." % cid)


def check_refs(v, les, card):
    label, cid = les.id, card["id"]
    refs = card["ref"]
    if card["kind"] == "stmt":
        refs = list(card["stmt"].get("ref") or [])
    if not refs:
        v.fail(label, 9, "%s 에 ref 가 없습니다." % cid)
        return
    for ref in refs:
        if ref_kind(ref)[0] is None:
            v.fail(label, 9, "%s 의 ref 꼴이 3.8 표에 없습니다: %s" % (cid, ref))
    if les.group is not None:  # 상황별 코드는 차시 번호를 견주지 않고 강의 꼴이나 요약본이면 됨
        if ref_kind(refs[0])[0] not in ("lecture", "summary"):
            v.fail(label, 9, "%s 의 첫 ref 는 그 줄을 가르친 강의 슬·노트북·과제·강의노트나 요약본이어야 합니다: %s" % (cid, refs[0]))
    elif not first_ref_ok(refs[0], lesson_no(les.id), aibank.course_of(les.id)):
        v.fail(label, 9, "%s 의 첫 ref 는 %d차시의 슬·노트북·과제·강의노트·요약본이어야 합니다: %s" % (cid, lesson_no(les.id), refs[0]))
    kinds = {ref_kind(r)[0] for r in refs}
    if kinds and kinds <= {"graduate", "official"} and not card["deep"]:
        v.fail(label, 9, "%s 는 대학원·공식만 근거라 deep 이어야 합니다." % cid)


def check_facts(v, les, card, used):
    label, cid = les.id, card["id"]
    facts, errata = les.data["facts"], les.data["errata"]
    if not card["facts"]:
        v.fail(label, 7, "%s 에 facts 가 없습니다." % cid)
    for fid in card["facts"]:
        fact = facts.get(fid)
        if fact is None:
            v.fail(label, 7, "%s 의 사실 %s 가 facts.json 에 없습니다." % (cid, fid))
            continue
        used.add(fid)
        verdict = fact.get("verdict")
        if verdict in BAD_VERDICTS:
            v.fail(label, 7, "%s 가 판정이 '%s'인 사실 %s 를 씁니다." % (cid, verdict, fid))
        if verdict in ASK_AS and not fact.get("ask_as"):
            v.fail(label, 7, "%s 의 사실 %s 는 '%s'인데 ask_as 가 없습니다." % (cid, fid, verdict))
        if fact.get("concept_only") and card["kind"] == "blank" and any(
                b.get("mode") in VALUE_MODES for b in card["item"].get("blanks") or []):
            v.fail(label, 7, "%s 가 개념 문항으로만 쓰는 사실 %s 를 값 빈칸으로 묻습니다." % (cid, fid))
    if card["errata"]:
        explain = (card.get("item") or {}).get("explain", "") if card["kind"] != "stmt" else card["stmt"].get("why", "")
        if card["kind"] == "skel":
            explain = " ".join(text for where, text, _ in skel.card_texts(card) if where.endswith(":explain"))
        if card["kind"] == "gen":
            explain = "정정" if "정정" in card["gen"].doc else ""
        if "정정" not in explain:
            v.fail(label, 7, "%s 는 errata 가 있는데 해설에 정정 문구가 없습니다." % cid)
        for xid in card["errata"]:
            if xid not in errata:
                v.fail(label, 7, "%s 의 errata %s 가 facts.json 에 없습니다." % (cid, xid))


def check_blank(v, les, card):
    label, cid, item = les.id, card["id"], card["item"]
    blanks = item.get("blanks") or []
    count = len(aibank.BLANK.findall(item.get("stem", "")))
    if count != len(blanks) or not blanks:
        v.fail(label, 2, "%s 의 ____ 가 %d개인데 blanks 가 %d개입니다." % (cid, count, len(blanks)))
    sets = []
    for n, blank in enumerate(blanks, 1):
        mode = blank.get("mode") or "word"
        answers = blank.get("answer")
        if mode not in grade.MODES:
            v.fail(label, 2, "%s 의 %d번 칸 mode 를 모릅니다: %s" % (cid, n, mode))
            continue
        if not isinstance(answers, list) or not answers or not all(isinstance(a, str) and a.strip() for a in answers):
            v.fail(label, 2, "%s 의 %d번 칸 answer 는 글 목록이어야 합니다." % (cid, n))
            continue
        normed = set()
        for answer in answers:
            value = grade.norm(mode, answer, blank)
            if value is None:
                v.fail(label, 3, "%s 의 %d번 칸 정답 %r 를 %s 모드로 읽지 못합니다." % (cid, n, answer, mode))
            else:
                normed.add(json.dumps(value, default=str))
            if any(api in answer for api in LONG_API):
                v.fail(label, 3, "%s 의 정답 %s 는 철자 시험이 되는 긴 API 이름이라 고르기로만 냅니다." % (cid, answer))
            elif mode == "code" and len(answer) > 20:
                v.warn(label, 3, "%s 의 코드 정답이 깁니다(%d자). 철자 시험이 되지 않는지 보세요: %s" % (cid, len(answer), answer))
        sets.append(normed)
        if mode in ("number", "values"):
            v.note(label, "대조 확인: %s %d번 칸 정답 %s 가 지문 숫자로 계산되는지" % (cid, n, answers[0]))
    for a in range(len(sets)):
        for b in range(a + 1, len(sets)):
            if sets[a] & sets[b]:
                v.fail(label, 3, "%s 의 %d번 칸과 %d번 칸 정답이 겹칩니다. 지문에 칸마다 무엇인지 정하는 말을 두고 답을 나누세요."
                       % (cid, a + 1, b + 1))
    for found in PARTICLE_TRAP.finditer(item.get("stem", "")):
        v.warn(label, 3, "%s 의 빈칸 바로 뒤에 받침에 따라 갈리는 조사가 있습니다: %s" % (cid, found.group(0)))


def same_text(text):
    """겹침을 볼 때의 글. 공백 차이와 대소문자만 무시함(코드 보기의 '--' 와 '-' 는 다르게 봄)."""
    return " ".join(unicodedata.normalize("NFKC", str(text)).split()).casefold().rstrip(".")


def option_problems(options, pick, multi, stem, cid):
    """고르기 보기 꼴의 실패 문구 목록(정적 문항과 생성기가 같이 씀)."""
    out = []
    if len(options) != 4:
        out.append("%s 의 보기는 4개여야 합니다(지금 %d개)." % (cid, len(options)))
    if pick not in ("right", "wrong"):
        out.append("%s 의 pick 은 right 나 wrong 이어야 합니다." % cid)
    answers = grade.right_options({"options": options, "pick": pick})
    if multi:
        if not 2 <= len(answers) <= 3:
            out.append("%s 는 모두 고르기인데 답이 %d개입니다(2~3개)." % (cid, len(answers)))
        if "모두" not in (stem or ""):
            out.append("%s 는 모두 고르기인데 지문에 '모두' 가 없습니다." % cid)
    elif len(answers) != 1:
        out.append("%s 의 답 보기가 %d개입니다(하나여야 함)." % (cid, len(answers)))
    seen = {}
    for n, option in enumerate(options, 1):
        text = str(option.get("text", ""))
        if not text.strip():
            out.append("%s 의 %d번 보기 글이 비었습니다." % (cid, n))
        if POINTING.search(text.strip()):
            out.append("%s 의 %d번 보기가 다른 보기를 가리킵니다: %s" % (cid, n, clip(text, 30)))
        key = same_text(text)
        if key in seen:
            out.append("%s 의 %d번과 %d번 보기가 같습니다." % (cid, seen[key], n))
        seen[key] = n
    return out


def check_choice(v, les, card, longest):
    label, cid, item = les.id, card["id"], card["item"]
    options = item.get("options") or []
    for problem in option_problems(options, item.get("pick"), item.get("multi"), item.get("stem", ""), cid):
        v.fail(label, 4, problem)
    answers = grade.right_options(item)
    for n, option in enumerate(options):
        if n in answers:
            continue
        if not str(option.get("why", "")).strip():
            v.fail(label, 4, "%s 의 %d번 보기에 why(바른 문장)가 없습니다." % (cid, n + 1))
        if item.get("pick") == "right" and not option.get("ok") and not str(option.get("aim", "")).strip():
            v.fail(label, 4, "%s 의 %d번 오답 보기에 노리는 착각(aim)이 없습니다." % (cid, n + 1))
    if len(answers) == 1 and options:
        lengths = [len(str(o.get("text", ""))) for o in options]
        longest.append(lengths[answers[0]] == max(lengths) and lengths.count(max(lengths)) == 1)


def check_topic(v, les, topic, all_topics):
    label = les.id
    tid = str(topic.get("id", ""))
    if not re.match(r"%s-t\d{2,3}\Z" % les.id, tid):
        v.fail(label, 5, "주제 id 꼴이 %s-t01 이 아닙니다: %s" % (les.id, tid))
    statements = topic.get("statements") or []
    pool = list(statements)
    tags = set(topic.get("tags") or [])
    for other in all_topics:
        if other is not topic and tags & set(other.get("tags") or []):
            pool += other.get("statements") or []
    true = sum(1 for s in pool if s.get("ok") is True)
    false = sum(1 for s in pool if s.get("ok") is False)
    if true < 4 or false < 4:
        v.fail(label, 5, "주제 %s 의 문장이 참 %d·거짓 %d 입니다(같은 tag 주제를 합쳐 4·4 이상)." % (tid, true, false))
    seen = {}
    for statement in statements:
        sid = statement.get("id")
        if not isinstance(statement.get("ok"), bool):
            v.fail(label, 5, "%s 의 ok 는 true 나 false 여야 합니다." % sid)
        for key in ("text", "why"):
            if not str(statement.get(key, "")).strip():
                v.fail(label, 5, "%s 에 %s 가 없습니다." % (sid, key))
        if not statement.get("ref") and not topic.get("ref"):
            v.fail(label, 5, "%s 에 ref 가 없습니다." % sid)
        key = same_text(statement.get("text", ""))
        if key in seen:
            v.fail(label, 5, "%s 와 %s 의 문장이 같습니다." % (seen[key], sid))
        seen[key] = sid
        cloze = statement.get("cloze")
        if cloze:
            if statement.get("ok") is not True:
                v.fail(label, 5, "%s 는 거짓 문장이라 cloze 를 두지 않습니다." % sid)
            if len(aibank.BLANK.findall(cloze.get("text", ""))) != 1:
                v.fail(label, 5, "%s 의 cloze 에는 ____ 가 하나 있어야 합니다." % sid)
            answers = cloze.get("answer")
            if not isinstance(answers, list) or not answers:
                v.fail(label, 5, "%s 의 cloze answer 는 글 목록이어야 합니다." % sid)
            elif (cloze.get("mode") or "word") not in grade.MODES:
                v.fail(label, 5, "%s 의 cloze mode 를 모릅니다." % sid)


def check_gen(v, les, card, oracles, seeds):
    label, cid, spec = les.id, card["id"], card["gen"]
    meta = spec.meta
    if meta.get("basis") not in genlib.BASIS:
        v.fail(label, 6, "%s 의 basis 는 %s 가운데 하나여야 합니다." % (cid, ", ".join(genlib.BASIS)))
    fn = oracles.get(genlib.oracle_name(cid))
    if fn is None:
        v.fail(label, 6, "%s 의 oracle 함수 %s 가 oracle.py 에 없습니다." % (cid, genlib.oracle_name(cid)))
    stems, styled, problems, spent = set(), 0, [], 0.0
    for seed in range(1, seeds + 1):
        started = time.perf_counter()
        try:
            made = genlib.run(spec, seed)
        except Exception as error:  # noqa: BLE001 - 출제 코드의 어떤 오류든 이유만 보여 줌
            problems.append("시드 %d: %s: %s" % (seed, type(error).__name__, error))
            break
        spent += time.perf_counter() - started
        stems.add(made.get("stem", ""))
        if made["kind"] == "blank":
            count = len(aibank.BLANK.findall(made.get("stem", "")))
            if count != len(made.get("blanks") or []):
                problems.append("시드 %d: ____ %d개와 blanks %d개가 다릅니다" % (seed, count, len(made.get("blanks") or [])))
                break
            if fn is not None:
                try:
                    want = fn(made.get("params") or {})
                except Exception as error:  # noqa: BLE001
                    problems.append("시드 %d: oracle 오류 %s" % (seed, error))
                    break
                want = want if isinstance(want, list) else [want]
                got = [b["answer"][0] for b in made["blanks"]]
                same = len(want) == len(got) and all(
                    grade.norm(b.get("mode") or "word", str(w), b) == grade.norm(b.get("mode") or "word", g, b)
                    for b, w, g in zip(made["blanks"], want, got))
                if not same:
                    problems.append("시드 %d: oracle %s 와 생성기 %s 가 다릅니다" % (seed, want, got))
                    break
        else:
            found = option_problems(made.get("options") or [], made.get("pick"), made.get("multi"), made.get("stem"), cid)
            if found:
                problems.append("시드 %d: %s" % (seed, found[0]))
                break
            if fn is not None:
                try:
                    want = fn(made.get("params") or {})
                except Exception as error:  # noqa: BLE001
                    problems.append("시드 %d: oracle 오류 %s" % (seed, error))
                    break
                want = sorted(want if isinstance(want, list) else [want])
                got = sorted(made["options"][n]["text"] for n in grade.right_options(made))
                if [str(w) for w in want] != got:
                    problems.append("시드 %d: oracle %s 와 생성기 %s 가 다릅니다" % (seed, want, got))
                    break
        if len(stems) > styled and styled < STYLE_SAMPLES:
            styled = len(stems)
            sample = {"id": "%s 시드 %d" % (cid, seed), "kind": made["kind"], "item": made}
            for where, text, markdown in card_texts(sample):
                v.style(label, where, text, markdown)
    for problem in problems:
        v.fail(label, 6, "%s %s" % (cid, problem))
    if not problems:
        if seeds >= FULL_SEEDS and len(stems) < MIN_STEMS:
            v.fail(label, 6, "%s 가 %d 시드에서 서로 다른 지문을 %d개만 만듭니다(%d개 이상, 아니면 정적 문항으로)."
                   % (cid, seeds, len(stems), MIN_STEMS))
        if seeds and spent * 1000.0 / seeds > GEN_MS:
            v.fail(label, 6, "%s 가 한 번에 평균 %.0fms 걸립니다(%dms 이하)." % (cid, spent * 1000.0 / seeds, GEN_MS))


def check_imports(v, label, folder):
    for name in ("gens.py", "oracle.py"):
        path = os.path.join(folder, name)
        if os.path.isfile(path) and IMPORT_BAD.search(study.read_text(path)):
            v.fail(label, 6, "%s 가 numpy·torch 를 import 합니다(표준 라이브러리만)." % name)


def check_counts(v, les):
    """meta.json 의 단원별 수와 봉인 안 수, 단원마다 핵심 3~4개."""
    label = les.id
    meta_units = les.data["meta"].get("units") or {}
    actual = {}
    zero = {"blank": 0, "choice": 0, "stmt": 0, "gen": [], "core": 0, "slot": 0, "order": 0, "pick": 0, "change": 0}
    for card in les.cards:
        row = actual.setdefault(card["unit"], json.loads(json.dumps(zero)))
        if card["kind"] == "gen":
            row["gen"].append(card["id"])
        elif card["kind"] == "skel":
            row[card["part"]] += 1
        else:
            row[card["kind"]] += 1
        row["core"] += int(card["core"])
    names = ("blank", "choice", "stmt", "core") + (tuple(skel.PART_LETTER) if les.group is not None else ())
    for key in sorted(set(meta_units) | set(actual)):
        want = meta_units.get(key)
        got = actual.get(key, zero)
        if want is None:
            v.fail(label, 2, "items meta.json units 에 %s 단원이 없습니다." % key)
        else:
            for name in names:
                if int(want.get(name, 0)) != got[name]:
                    v.fail(label, 2, "meta.json 의 %s %s 수 %s 가 봉인 안 수 %d 와 다릅니다." % (key, name, want.get(name, 0), got[name]))
            if sorted(want.get("gen") or []) != sorted(got["gen"]):
                v.fail(label, 2, "meta.json 의 %s gen 목록이 gens.py 와 다릅니다." % key)
        if key in actual and not 3 <= got["core"] <= 4:
            v.fail(label, 2, "%s 단원의 핵심 문항이 %d개입니다(3~4개)." % (key, got["core"]))


def check_note_blocks(v, les, terms=None):
    """학습 노트의 ai-* 블록, 단계 수, 단계 사실 줄, 프레임 줄. 세 수준 블록은 자리와 수를 여기서, 안은 check_levels 로 봄."""
    label = les.id
    note = les.note
    if note is None:
        return
    for no, found in lecture_locations.find(note["markdown"], markdown=True):
        v.fail(label, 10, "page.md:%d: %s: %s" % (no, lecture_locations.RULE, found))
    terms = terms or {"known": [], "terms": []}
    level_blocks = 0
    unit_cards = {}
    for card in les.cards:
        unit_cards.setdefault(card["unit"], {})[card["id"]] = card
    facts = les.data["facts"] if les.data else {}
    for key in note["order"]:
        unit = note["units"][key]
        where = "%s %s" % (note["id"], key)
        if unit["lead"].strip():
            v.fail(label, 8, "%s: H2 바로 밑에 글이 있습니다. 첫 ### 단계 안으로 옮기세요." % where)
        steps = [s for s in unit["steps"] if s["scope"] != "trend"]
        if not 4 <= len(steps) <= 7:
            v.fail(label, 8, "%s: 단계가 %d개입니다(먼저 풀어 보기와 외울 것을 넣어 4~7개)." % (where, len(steps)))
        if not steps or steps[-1]["scope"] != "memo":
            v.fail(label, 8, "%s: 마지막 단계가 「외울 것」이 아닙니다." % where)
        mine = unit_cards.get(key, {})
        ids, covered = set(), set()
        guesses, reveals = {}, {}
        for step in unit["steps"]:
            spot = "%s/%s" % (key, step["no"] or "흐름")
            if step["scope"] != "trend" and not step["facts"]:
                v.fail(label, 8, "%s 단계에 <!-- facts: … --> 줄이 없습니다." % spot)
            for fid in step["facts"]:
                if facts and fid not in facts:
                    v.fail(label, 8, "%s 단계의 사실 %s 가 facts.json 에 없습니다." % (spot, fid))
            for block in step["blocks"]:
                kind = block["kind"]
                if block.get("error"):
                    v.fail(label, 8, "%s 의 %s 블록: %s" % (spot, kind, block["error"]))
                    continue
                bid = block.get("id")
                if kind in ("guess", "recall", "rotate", "levels", "formula"):
                    if not bid:
                        v.fail(label, 8, "%s 의 %s 블록에 id 가 없습니다." % (spot, kind))
                    elif bid in ids:
                        v.fail(label, 8, "%s 의 블록 id %s 가 단원 안에서 겹칩니다." % (spot, bid))
                    ids.add(bid)
                if kind == "guess":
                    options = block.get("options") or []
                    if not 2 <= len(options) <= 4 or not str(block.get("q", "")).strip():
                        v.fail(label, 8, "%s 의 먼저 풀어 보기는 q 와 보기 2~4개가 있어야 합니다." % spot)
                    if not isinstance(block.get("answer"), int) or not 0 <= block["answer"] < len(options):
                        v.fail(label, 8, "%s 의 먼저 풀어 보기 answer 가 보기 번호(0부터)가 아닙니다." % spot)
                    reveal = block.get("reveal_step")
                    if not isinstance(reveal, int) or not (step["no"] or 0) < reveal <= len(steps):
                        v.fail(label, 8, "%s 의 reveal_step 이 뒤 단계 번호가 아닙니다: %r" % (spot, reveal))
                    bad = [c for c in block.get("cards") or [] if c not in mine]
                    if bad or not block.get("cards"):
                        v.fail(label, 8, "%s 의 먼저 풀어 보기 cards 가 이 단원 카드가 아닙니다: %s" % (spot, bad or "없음"))
                    guesses[bid] = block
                    v.style(label, "%s guess" % spot, block.get("q", ""))
                    for text in options:
                        v.style(label, "%s guess 보기" % spot, text)
                elif kind == "reveal":
                    bid = block.get("guess") or bid
                    if bid not in guesses:
                        v.fail(label, 8, "%s 의 짐작 확인이 앞의 먼저 풀어 보기 id 를 가리키지 않습니다: %r" % (spot, bid))
                    reveals[bid] = step["no"]
                elif kind == "recall":
                    if len(aibank.BLANK.findall(block.get("q", ""))) != 1:
                        v.fail(label, 8, "%s 의 떠올리기 q 에는 ____ 가 하나 있어야 합니다." % spot)
                    if not isinstance(block.get("answer"), list) or not block.get("answer"):
                        v.fail(label, 8, "%s 의 떠올리기 answer 는 글 목록이어야 합니다." % spot)
                    if (block.get("mode") or "word") not in grade.MODES:
                        v.fail(label, 8, "%s 의 떠올리기 mode 를 모릅니다." % spot)
                    v.style(label, "%s recall" % spot, block.get("q", ""))
                    v.style(label, "%s recall why" % spot, block.get("why", ""))
                elif kind == "why":
                    if not str(block.get("q", "")).strip() or not str(block.get("a", "")).strip():
                        v.fail(label, 8, "%s 의 왜일까요는 q 와 a 가 있어야 합니다." % spot)
                    v.style(label, "%s why q" % spot, block.get("q", ""))
                    v.style(label, "%s why a" % spot, block.get("a", ""))
                elif kind == "memo":
                    for n, item in enumerate(block.get("items") or [], 1):
                        if not isinstance(item, dict) or not item.get("q") or not item.get("a"):
                            v.fail(label, 8, "%s 의 외울 것 %d번에 q·a 가 없습니다." % (spot, n))
                            continue
                        bad = [c for c in item.get("cards") or [] if c not in mine]
                        if bad or not item.get("cards"):
                            v.fail(label, 8, "%s 의 외울 것 %d번 cards 가 이 단원 카드가 아닙니다: %s" % (spot, n, bad or "없음"))
                        covered |= set(item.get("cards") or [])
                        v.style(label, "%s 외울 것 q" % spot, item["q"])
                        v.style(label, "%s 외울 것 a" % spot, item["a"])
                elif kind == "trend":
                    v.style(label, "%s 2026 흐름 제목" % spot, block.get("title", ""))
                    v.style(label, "%s 2026 흐름" % spot, block.get("text", ""), markdown=True)
                elif kind == "figure":
                    for n, frame in enumerate(block["frames"], 1):
                        v.style(label, "%s 그림 %s 프레임 %d" % (spot, block["file"], n), frame["text"])
                elif kind in ("diff", "rotate"):
                    skel_block(v, les, spot, block)
                elif kind == "levels":
                    check_levels(v, les, unit, step, block, spot, terms)
                elif kind == "formula":
                    for field in aibank.FORMULA_TEXT_KEYS[1:]:
                        v.style(label, "%s 수식 %s" % (spot, field), block[field])
                    fig = block["figure"]
                    for text in [fig["caption"], fig["content"]] + [f["text"] for f in fig["frames"]]:
                        v.style(label, "%s 수식 그림" % spot, text)
            spots = [n for n, b in enumerate(step["blocks"]) if b["kind"] == "levels"]
            level_blocks += len(spots)
            if len(spots) > 1:
                v.fail(label, 8, "%s 단계에 세 수준 블록이 %d개입니다(한 단계에 하나)." % (spot, len(spots)))
            if spots and spots[-1] != len(step["blocks"]) - 1:
                v.fail(label, 8, "%s 의 세 수준 블록이 단계의 마지막 블록이 아닙니다." % spot)
            if spots and (step["scope"] in ("memo", "trend") or step["no"] == 1 or any(b["kind"] == "guess" for b in step["blocks"])):
                v.fail(label, 8, "%s 단계에는 세 수준 블록을 두지 않습니다(먼저 풀어 보기·외울 것·2026 흐름 단계)." % spot)
        for bid, block in guesses.items():
            if reveals.get(bid) != block.get("reveal_step"):
                v.fail(label, 8, "%s 의 짐작 %s 확인을 안내한 %s단계에서 보여 주세요." % (where, bid, block.get("reveal_step")))
        missing = sorted(cid for cid, card in mine.items() if card["core"] and cid not in covered)
        if missing:
            v.fail(label, 8, "%s 의 외울 것이 핵심 카드를 덮지 않습니다: %s" % (where, verify_web.listing(missing)))
        meta = note["unit_meta"].get(key, {})
        if meta.get("key_figure") and not os.path.isfile(os.path.join(note["dir"], *str(meta["key_figure"]).split("/"))):
            v.warn(label, 13, "%s 의 key_figure 파일이 아직 없습니다: %s" % (where, meta["key_figure"]))
    if les.group is None and not 3 <= level_blocks <= 5:
        v.warn(label, 8, "%s 의 세 수준 블록이 %d개입니다(차시마다 3~5개)." % (note["id"], level_blocks))
    skel_fences(v, les)


def _has_word(text, word):
    """word 가 text 에 낱말로 나오는지. 숫자는 앞뒤가 다른 숫자에 붙지 않을 때, 영문은 앞뒤가 영문·숫자가 아닐 때, 한글은 들어 있으면."""
    text, word = text.replace("−", "-"), word.strip().replace("−", "-")
    if not word:
        return False
    if NUMBER_WORD.match(word):
        return bool(re.search(r"(?<![\d.])%s(?!\d|\.\d)" % re.escape(word), text))
    if re.match(r"[A-Za-z0-9_]", word):
        return bool(re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(word), text))
    return word in text


def step_numbers(step):
    """단계 글·그림 캡션·내용·프레임 줄에 나온 숫자 집합. 캡션 앞의 "그림 N." 은 뺌."""
    pieces = []
    for block in step["blocks"]:
        if block["kind"] == "text":
            pieces.append(block["markdown"])
        elif block["kind"] == "figure":
            pieces += [re.sub(r"^그림\s*\d+\.?\s*", "", block["caption"]), block["content"]] + [f["text"] for f in block["frames"]]
    return set(NUMBER_TEXT.findall("\n".join(pieces)))


def check_levels(v, les, unit, step, block, spot, terms):
    """세 수준 블록 하나(plan 2.3 표). concept, 수준마다 글·그림·물음 꼴과 수준 규칙(7살 낱말·식 기호, 15살 라이브러리·행렬 표기,
    20살 코드·착각·위치), 말투. 그림 파일은 check_level_figure, 맥락은 check_levels_context 가 봄."""
    label = les.id
    tag = "%s %s" % (spot, block.get("id") or "?")
    concept = block.get("concept") or ""
    v.style(label, "%s concept" % tag, concept)  # 접힌 줄 제목으로 늘 보임
    if not concept.strip():
        v.fail(label, 8, "%s 세 수준 블록에 concept 가 없습니다." % tag)
    elif len(concept) > 20:
        v.fail(label, 8, "%s 의 concept 가 %d자입니다(20자 이하): %s" % (tag, len(concept), concept))
    else:
        for term in terms["terms"]:
            if concept in [term["term"]] + list(term.get("also") or []) and les.note["id"] not in (term.get("page"), term.get("intro")):
                v.warn(label, 8, "%s 의 concept '%s' 는 terms.json 낱말인데 이 노트가 그 낱말의 intro·page 가 아닙니다." % (tag, concept))
        shown = step["title"] + "\n" + "\n".join(b["markdown"] for b in step["blocks"] if b["kind"] == "text")
        if concept not in shown:
            v.warn(label, 8, "%s 의 concept '%s' 가 단계 글에 없습니다." % (tag, concept))
    recall_q = {str(b.get("q", "")).strip() for s in unit["steps"] for b in s["blocks"] if b["kind"] == "recall"}
    recall_a = {str(a).strip() for b in step["blocks"] if b["kind"] == "recall" for a in b.get("answer") or []}
    numbers = step_numbers(step)
    finder = web_lint.Terms(terms)
    known = set(terms.get("known") or [])
    levels = block["levels"]
    for n, level in enumerate(levels):
        no = level["level"]
        where = "%s %d살" % (tag, no)
        parts = aibank.level_parts(level)
        texts = dict(parts)
        if not level["text"].strip():
            v.fail(label, 8, "%s 에 text 가 없습니다." % where)
        if not level.get("figure"):
            v.fail(label, 8, "%s 에 figure 가 없습니다." % where)
        if len(aibank.BLANK.findall(level["q"])) != 1:
            v.fail(label, 8, "%s 의 q 에는 ____ 가 하나 있어야 합니다." % where)
        if not any(a.strip() for a in level["answer"]):
            v.fail(label, 8, "%s 의 answer 가 비었습니다." % where)
        blank = {"answer": level["answer"], "mode": level["mode"], "places": level["places"], "unit": level["unit"]}
        for answer in level["answer"]:
            if answer.strip() and not grade.grade_blank(blank, answer):
                v.fail(label, 8, "%s 의 answer '%s' 를 mode %s 로 채점하면 맞음이 되지 않습니다." % (where, answer, level["mode"]))
        if not level["why"].strip():
            v.fail(label, 8, "%s 에 why 가 없습니다." % where)
        if any(line.lstrip().startswith(("#", ">")) for line in level["text"].split("\n")):
            v.fail(label, 8, "%s 의 text 에 제목이나 인용 줄이 있습니다." % where)
        if level["q"].strip() in recall_q:
            v.fail(label, 8, "%s 의 q 가 같은 단원 떠올리기 q 와 같습니다." % where)
        for key, text in parts:
            found = POLITE.search(text) if key != "code" else None
            if found:
                v.fail(label, 10, "%s 의 %s 에 '%s' 가 있습니다. ~니다 체로 씁니다." % (where, key, found.group(0)))
        if numbers and not numbers & set(NUMBER_TEXT.findall("\n".join(t for _, t in parts))):
            v.warn(label, 8, "%s 가 단계 글·캡션의 숫자를 하나도 쓰지 않습니다." % where)
        if len(level["text"]) > LEVEL_CHARS[no]:
            v.warn(label, 8, "%s 의 text 가 %d자입니다(%d자 이하로)." % (where, len(level["text"]), LEVEL_CHARS[no]))
        same = sorted({a.strip() for a in level["answer"]} & recall_a)
        if same:
            v.warn(label, 8, "%s 의 answer 가 같은 단계 떠올리기 answer 와 같습니다: %s" % (where, ", ".join(same)))
        if level["mode"] == "word" and len(level["answer"]) < 2:
            v.warn(label, 8, "%s 의 mode 가 word 이면 받는 답을 둘 이상 둡니다." % where)
        for lower in levels[:n]:  # 세 수준이 한 화면에 같이 펴지므로 물음 전에 보이는 글·캡션·코드를 봄
            for answer in lower["answer"]:
                for key in ("text", "caption", "code"):
                    if _has_word(texts.get(key, ""), answer):
                        v.warn(label, 8, "%s 의 %s 에 %d살 물음의 답 '%s' 가 나옵니다." % (where, key, lower["level"], answer))
        for key in ("text", "caption", "q", "why", "mistake"):  # web_lint 가 울타리 안을 건너뛰어서 여기서 봄
            flat = web_lint.plain(texts.get(key, ""))
            for found in web_lint.SPACED.finditer(flat):
                v.fail(label, 10, "%s %s: 띄어 쓴 조사: 영어 낱말이나 코드 뒤의 조사는 붙여 씁니다: %s"
                       % (where, key, web_lint.shown(flat[max(0, found.start() - 12):found.end()].strip())))
        shown = [(key, texts[key]) for key in ("text", "q", "why", "caption", "content") if key in texts]
        if no == 7:
            shown += [("answer", answer) for answer in level["answer"]]
            for key, text in shown:
                if "`" in text:
                    v.fail(label, 8, "%s 의 %s 에 인라인 코드가 있습니다(7살은 코드 없이)." % (where, key))
                found = SEVEN_SIGNS.search(text)
                if found:
                    v.fail(label, 8, "%s 의 %s 에 식 기호 '%s' 가 있습니다(7살은 식 없이)." % (where, key, found.group(0)))
                words = sorted({term for term, _, _ in finder.find(text) if term not in known})
                if words:
                    v.fail(label, 8, "%s 의 %s 에 낱말 %s 가 나옵니다(7살은 terms.json 낱말 없이)." % (where, key, ", ".join(words)))
                if re.search(r"[A-Za-z]", text):
                    v.warn(label, 8, "%s 의 %s 에 영문자가 있습니다." % (where, key))
        elif no == 15:
            for key, text in shown:
                if "`" in text:
                    v.fail(label, 8, "%s 의 %s 에 인라인 코드가 있습니다(15살은 코드 없이)." % (where, key))
                for found in (LIBRARY.search(text), re.search(r"[∂Σ@]|\[\[", text)):
                    if found:
                        v.fail(label, 8, "%s 의 %s 에 '%s' 가 있습니다(15살은 라이브러리 이름·편미분 기호·행렬 표기 없이)."
                               % (where, key, found.group(0)))
            if not any("=" in text for _, text in shown):
                v.warn(label, 8, "%s 에 = 가 든 계산이 없습니다." % where)
        else:
            lines = [line for line in level["code"].split("\n") if line.strip()]
            if not 2 <= len(lines) <= 8:
                v.fail(label, 8, "%s 의 code 가 %d줄입니다(2~8줄)." % (where, len(lines)))
            if not level["mistake"].strip():
                v.fail(label, 8, "%s 에 mistake 가 없습니다." % where)
        v.style(label, "%s text" % where, level["text"], markdown=True)
        for key in ("caption", "content", "q", "why", "mistake"):
            v.style(label, "%s %s" % (where, key), texts.get(key, ""))


def check_levels_context(v, les, bank_dir, terms):
    """세 수준 블록 글의 terms 낱말이 블록 자리까지 정의됐는지(11). page.md 를 split_levels 로 본문 조각과 수준 조각으로 나눠 순서대로
    web_lint.context_check 에 넘기고 블록 꼬리표가 든 줄만 남김. allowed 는 web_lint.lint_item 의 page 갈래와 같음. 본문 줄은
    web_lint.py --bank ai 가 보므로 버림."""
    note = les.note
    if note is None:
        return
    parts = aibank.split_levels(note.get("markdown", ""), note.get("sections"))
    tags, texts = [], []
    for kind, value, line in parts:
        if kind == "main":
            texts.append(("page.md", "\n" * (line - 1) + value))  # 본문 줄 번호를 page.md 줄 번호와 맞춤
            continue
        if value.get("error"):
            continue
        for level in value["levels"]:
            name = "page.md %s/%s %s %d살" % (value.get("unit"), value.get("step"), value.get("id") or "?", level["level"])
            tags.append(name)
            texts.append((name, "\n\n".join(text for key, text in aibank.level_parts(level) if key != "code")))
    if not tags:
        return
    report = web_lint.Report(les.id)
    allowed = set(terms.get("known") or [])
    try:
        index = webbank.read_index(bank_dir)
        for pid in note.get("needs") or []:
            allowed |= web_lint.page_defines(pid, bank_dir, index, report)
    except webbank.BankError as error:
        v.fail(les.id, 11, "needs 페이지를 읽지 못했습니다: %s" % error)
        return
    listed = set(note.get("defines") or [])
    web_lint.context_check(texts, web_lint.Terms(terms, listed), allowed | listed, listed, report)
    for level, where, rule, text in report.rows:
        if any(tag in where or tag in text for tag in tags):
            (v.fail if level == "error" else v.warn)(les.id, 11, "%s: %s: %s" % (where, rule, text))


def skel_block(v, les, spot, block):
    """ai-diff 는 뼈대와 두 코드 예제가, ai-rotate 는 뼈대·코드 예제와 slots 의 자리가 있어야 함."""
    label = les.id
    skeleton = les.skeletons.get(str(block.get("skel")))
    if skeleton is None:
        v.fail(label, 8, "%s 의 ai-%s 뼈대 %s 가 ai/patterns 에 없습니다." % (spot, block["kind"], block.get("skel")))
        return
    variants = skeleton.get("variants") or {}
    sides = ("left", "right") if block["kind"] == "diff" else ("variant",)
    for side in sides:
        if block.get(side) not in variants:
            v.fail(label, 8, "%s 의 ai-%s %s 코드 예제 %r 이 뼈대 %s 에 없습니다." % (spot, block["kind"], side, block.get(side), skeleton["id"]))
            return
    if block["kind"] == "rotate":
        try:
            skel.rotate_block(skeleton, block["variant"], block.get("slots") if isinstance(block.get("slots"), list) else None)
        except aibank.AiBankError as error:
            v.fail(label, 8, "%s 의 ai-rotate: %s" % (spot, error))


def skel_fences(v, les):
    """<!-- skel: S1 표준형 --> 표시 바로 아래 코드 울타리가 그 코드 예제 lines 와 같은지. 줄 끝 # 주석과 끝 공백, 빈 줄은 뗌."""
    for fence in aibank.skel_fences(les.note.get("markdown", "")):
        where = "%s %d번 줄" % (les.note["id"], fence["line"])
        skeleton = les.skeletons.get(fence["skel"])
        if skeleton is None or fence["variant"] not in (skeleton.get("variants") or {}):
            v.fail(les.id, 8, "%s 의 skel 표시가 없는 뼈대·코드 예제를 가리킵니다: %s %s" % (where, fence["skel"], fence["variant"]))
            continue
        if fence["code"] is None:
            v.fail(les.id, 8, "%s 의 skel 표시 바로 아래에 닫힌 코드 울타리가 없습니다." % where)
            continue
        got = []
        for line in fence["code"]:
            line = re.sub(r"\s+#.*$", "", line).rstrip()
            if line.strip() and not line.lstrip().startswith("#"):
                got.append(line)
        want = [line.rstrip() for line in skel.lines_of(skeleton, fence["variant"])]
        if got != want:
            at = next((n for n, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
            v.fail(les.id, 8, "%s 의 울타리가 뼈대 %s %s 코드 예제와 다릅니다(%d번째 줄부터)." % (where, fence["skel"], fence["variant"], at + 1))


def check_context(v, les, terms, pages_no):
    """문항 글의 terms 낱말이 이 차시까지 소개됐는지(page·intro 차시가 이 차시보다 뒤면 실패). 상황별 코드 카드는 권하는
    차시(after)까지로 봄."""
    label = les.id
    introduced = {}
    for term in terms["terms"]:
        first = [(p.startswith("a"), pages_no[p]) for p in (term.get("intro"), term.get("page")) if p in pages_no]
        if first:
            introduced[term["term"]] = min(first)
    finder = web_lint.Terms(terms)
    for card in les.cards:
        no = lesson_no(card.get("after")) if les.group is not None else lesson_no(les.id)
        if no is None:
            continue
        for where, text, _ in card_texts(card):
            plain = re.sub(r"```.*?```", "", str(text), flags=re.S)
            for term, form, _ in finder.find(plain):
                at = introduced.get(term)
                if at is not None and at > (aibank.course_of(les.id) == "app", no):
                    v.fail(label, 11, "%s 에 %d차시에서 소개하는 낱말 '%s'가 나옵니다." % (where, at[1], term))
                    break


def intro_definitions(v, bank_dir, terms, index):
    """terms 의 intro 페이지에 그 낱말의 한 문장 정의가 있는지(설계 6.5)."""
    pages = {p["id"]: p for p in index["pages"]}
    for term in terms["terms"]:
        pid = term.get("intro")
        if not pid or pid == term.get("page"):
            continue
        if pid not in pages or not os.path.isfile(os.path.join(aibank.page_dir(pid, bank_dir), "page.md")):
            continue
        text = study.read_text(os.path.join(aibank.page_dir(pid, bank_dir), "page.md"))
        found = False
        for unit in web_lint.units_of(text):
            if unit.prose and any(web_lint.definition_form(s, f) for s in web_lint.sentences(unit.text)
                                  for f in [term["term"]] + term["also"]):
                found = True
                break
        if not found:
            v.fail("terms", 11, "'%s'의 intro 페이지 %s 에 한 문장 정의가 없습니다." % (term["term"], pid))


def git_root(bank_dir):
    """은행이 든 git 저장소 맨 위 폴더. git 저장소 밖(임시 사본)이거나 git 이 없으면 None."""
    here = os.path.abspath(bank_dir)
    while not os.path.exists(os.path.join(here, ".git")):  # git 저장소 밖이면 git 을 부르지 않음
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=bank_dir, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    except OSError:
        return None
    return top.stdout.strip() if top.returncode == 0 else None


def git_pattern_ids(bank_dir, root):
    """직전 커밋(HEAD)의 ai/patterns/S*.json 카드 id. 그 커밋에 폴더가 없으면 None."""
    rel = os.path.relpath(os.path.realpath(os.path.join(bank_dir, "patterns")), os.path.realpath(root)).replace(os.sep, "/")
    listed = subprocess.run(["git", "ls-tree", "--name-only", "HEAD", rel + "/"], cwd=root, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    names = [n for n in listed.stdout.decode("utf-8", "replace").split("\n") if re.search(r"/S\d+\.json\Z", n)]
    if listed.returncode != 0 or not names:
        return None
    ids = set()
    for name in names:
        shown = subprocess.run(["git", "show", "HEAD:%s" % name], cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
        try:
            data = json.loads(shown.stdout.decode("utf-8"))
            ids |= {str(e["id"]) for key in skel.PART_KEY.values() for e in data.get(key) or []}
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return ids


def git_ids(bank_dir, lid):
    """직전 커밋(HEAD)의 그 차시 카드·문장 id. 상황별 코드(pc)는 ai/patterns 뼈대 카드 id 도 더함. git 이 없거나 그 커밋에
    없으면 None."""
    folder = aibank.items_dir(lid, bank_dir)
    root = git_root(bank_dir)
    if root is None:
        return None
    rel = os.path.relpath(os.path.realpath(folder), os.path.realpath(root)).replace(os.sep, "/")
    ids = set()
    patterns = git_pattern_ids(bank_dir, root) if lid == "pc" else None
    shown = subprocess.run(["git", "show", "HEAD:%s/sealed.json" % rel], cwd=root, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if shown.returncode != 0:
        return patterns
    try:
        files = study.unseal_blob(json.loads(shown.stdout.decode("utf-8"))["blob"])
        for item in json.loads(files.get("items.json", '{"items": []}')).get("items") or []:
            ids.add(str(item["id"]))
        for topic in json.loads(files.get("statements.json", '{"topics": []}')).get("topics") or []:
            ids |= {str(s["id"]) for s in topic.get("statements") or []}
    except (ValueError, KeyError, TypeError):
        return None
    gens = subprocess.run(["git", "show", "HEAD:%s/gens.py" % rel], cwd=root, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if gens.returncode == 0:
        ids |= set(re.findall(r"""(?:@gen|register)\(\s*['"]([\w-]+)['"]""", gens.stdout.decode("utf-8", "replace")))
    return ids | (patterns or set())


def load_lesson(v, bank_dir, entry):
    label = entry["id"]
    note = None
    if os.path.isfile(os.path.join(aibank.page_dir(entry["page"], bank_dir), "meta.json")):
        try:
            note = aibank.load_note({"id": entry["page"], "title": entry["title"]}, bank_dir)
        except aibank.AiBankError as error:
            v.fail(label, 8, str(error))
    else:
        v.fail(label, 2, "학습 노트 %s/meta.json 이 없습니다." % entry["page"])
    try:
        data = aibank.load_items(entry, bank_dir)
    except aibank.AiBankError as error:
        v.fail(label, 2, str(error))
        return None
    if not data["facts"]:
        v.fail(label, 7, "봉인 안 facts.json 이 없거나 사실이 비었습니다.")
    return Lesson(entry, note, data, aibank.cards_of(entry, data))


def load_pattern_group(v, bank_dir, group, skeletons):
    """상황별 코드 무리 하나를 Lesson 꼴로. entry {"id", "no": None, "page", "title"}, note(l18), data(items/<무리>, facts·review
    와 생성기), cards(공개 단원의 뼈대·수치 문항). 정적 카드(items.json·statements.json)가 있으면 실패(엔진이 읽지 않음)."""
    label = group["id"]
    entry = {"id": label, "no": None, "page": group["page"], "title": group["title"]}
    note = None
    if os.path.isfile(os.path.join(aibank.page_dir(group["page"], bank_dir), "meta.json")):
        try:
            note = aibank.load_note({"id": group["page"], "title": group["title"]}, bank_dir)
        except aibank.AiBankError as error:
            v.fail(label, 8, str(error))
    else:
        v.fail(label, 2, "학습 노트 %s/meta.json 이 없습니다." % group["page"])
    try:
        data = aibank.load_items({"id": label}, bank_dir)
    except aibank.AiBankError as error:
        v.fail(label, 2, str(error))
        return None
    if not data["facts"]:
        v.fail(label, 7, "봉인 안 facts.json 이 없거나 사실이 비었습니다.")
    try:
        extra = sorted(set(webbank.load_secrets(data["dir"])) - {"facts.json", "review.json"})
    except webbank.BankError:
        extra = []
    if extra:
        v.fail(label, 2, "items/%s 의 봉인에는 facts.json 과 review.json 만 둡니다. 코드 카드는 ai/patterns 뼈대에서 만듭니다: %s"
               % (label, ", ".join(extra)))
    units = {}
    for key, info in group["units"].items():
        if note is None or key not in note["visible"]:
            continue
        if not info["name"]:
            v.fail(label, 1, "index.json patterns 의 %s 단원에 name 이 없습니다." % key)
        units[key] = {"after": info["after"], "name": info["name"], "title": note["units"][key]["title"]}
    try:
        cards = skel.cards(group, skeletons, units)
        cards.extend(aibank.pattern_gen_cards(group, data, units))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        v.fail(label, 19, "뼈대 카드를 만들 수 없습니다: %s" % error)
        cards = []
    les = Lesson(entry, note, data, cards)
    les.group, les.skeletons = group, skeletons
    return les


def check_lesson(v, bank_dir, les, ids, retired, terms, pages_no, seeds):
    label = les.id
    no = les.entry.get("no")
    v.head(label, "%d차시 %s" % (no, les.entry["title"]) if no is not None else les.entry["title"])
    oracles = {}
    try:
        oracles = genlib.load_oracle(os.path.join(les.data["dir"], "oracle.py"))
    except genlib.GenError as error:
        v.fail(label, 6, str(error))
    check_imports(v, label, les.data["dir"])
    used, longest = set(), []
    for fact in les.data["facts"].values():
        if fact.get("verdict") not in VERDICTS:
            v.fail(label, 7, "사실 %s 의 verdict 를 모릅니다: %r" % (fact.get("id"), fact.get("verdict")))
    styled = set()
    for card in les.cards:
        check_card_common(v, les, card, ids, retired)
        check_alt(v, les, card)
        check_refs(v, les, card)
        check_facts(v, les, card, used)
        if card["kind"] == "blank":
            check_blank(v, les, card)
        elif card["kind"] == "choice":
            check_choice(v, les, card, longest)
        elif card["kind"] == "gen":
            check_gen(v, les, card, oracles, seeds)
        for where, text, markdown in card_texts(card):
            if card["kind"] == "skel":  # 코드 예제 상황 글은 카드마다 같아 한 번만 봄
                if (text, markdown) in styled:
                    continue
                styled.add((text, markdown))
            v.style(label, where, text, markdown)
    for topic in les.data["topics"]:
        check_topic(v, les, topic, les.data["topics"])
    if longest and sum(longest) > 0.4 * len(longest):
        v.warn(label, 4, "답 보기가 가장 긴 고르기가 %d/%d 입니다(40%% 이하로)." % (sum(longest), len(longest)))
    deep = sum(1 for c in les.cards if c["deep"])
    if deep > DEEP_MAX.get(les.id, DEEP_DEFAULT):
        v.fail(label, 9, "deep 카드가 %d개입니다(%d개 이하)." % (deep, DEEP_MAX.get(les.id, DEEP_DEFAULT)))
    unused = sorted(fid for fid, fact in les.data["facts"].items() if fact.get("core") and fid not in used)
    if unused:
        v.warn(label, 7, "어느 카드도 쓰지 않는 핵심 사실: %s" % verify_web.listing(unused))
    check_counts(v, les)
    check_note_blocks(v, les, terms)
    check_levels_context(v, les, bank_dir, terms)
    check_context(v, les, terms, pages_no)
    before = git_ids(bank_dir, les.id)
    if before is not None:
        now_ids = {c["id"] for c in les.cards}
        if les.group is not None:  # 공개 전 단원의 뼈대 카드는 카드로 만들지 않아도 파일에 남아 있음
            now_ids |= {str(e.get("id")) for sk in les.skeletons.values() for key in skel.PART_KEY.values() for e in sk.get(key) or []}
        gone = sorted(before - now_ids - retired)
        if gone:
            v.fail(label, 2, "직전 커밋에 있던 id 가 retired.json 없이 사라졌습니다: %s" % verify_web.listing(gone))
    for card in les.cards:
        for where, text, _ in card_texts(card):
            for ref in IMAGE_REF.findall(str(text)):
                if not ref.startswith(("assets/", "../")):
                    v.fail(label, 13, "%s 의 그림 %s 은 직접 그린 그림이어야 합니다." % (where, ref))


# 19. 뼈대

def _entry_where(skeleton, part, entry):
    return "%s %s" % (skeleton.get("id"), entry.get("id"))


def check_skeletons(v, les, seeds):
    """ai/patterns 뼈대 파일(설계 3.7, 계획 8.1). 코드 예제의 situation·lines, slot 의 토큰과 답, order 의 valid 와 시드마다 오답 보기,
    pick 보기, change 의 다른 줄, 카드마다 level·ref·facts·step, 카드 id 꼴과 겹침."""
    label = les.id
    seen = {}
    for sid in sorted(les.skeletons, key=lambda k: int(k[1:])):
        skeleton = les.skeletons[sid]
        if skeleton.get("format") != 1:
            v.fail(label, 19, "%s 의 format 은 1 이어야 합니다." % sid)
        if not str(skeleton.get("title") or "").strip():
            v.fail(label, 19, "%s 에 title 을 적어야 합니다." % sid)
        variants = skeleton.get("variants") or {}
        for name, variant in variants.items():
            if not str(variant.get("situation") or "").strip():
                v.fail(label, 19, "%s 의 %s 코드 예제에 situation 이 없습니다." % (sid, name))
            elif aibank.BLANK.search(variant["situation"]):
                v.fail(label, 19, "%s 의 %s 코드 예제 situation 에 ____ 가 있습니다." % (sid, name))
            for n, line in enumerate(variant.get("lines") or []):
                if "\t" in line or aibank.BLANK.search(line) or SKEL_COMMENT.search(line):
                    v.fail(label, 19, "%s 의 %s 코드 예제 %d번 줄에 탭·____·# 주석이 있습니다: %s" % (sid, name, n, clip(line, 40)))
        for part, key in skel.PART_KEY.items():
            for entry in skeleton.get(key) or []:
                cid = str(entry.get("id"))
                where = _entry_where(skeleton, part, entry)
                if not re.match(r"pc-%s\d{2,3}\Z" % skel.PART_LETTER[part], cid):
                    v.fail(label, 19, "%s 의 id 꼴이 pc-%s01 이 아닙니다." % (where, skel.PART_LETTER[part]))
                if cid in seen:
                    v.fail(label, 19, "카드 id 가 두 뼈대에 있습니다: %s (%s, %s)" % (cid, seen[cid], sid))
                seen[cid] = sid
                if entry.get("level") not in (1, 2, 3):
                    v.fail(label, 19, "%s 의 level 은 1~3 이어야 합니다(카드마다 적음)." % where)
                if not entry.get("ref"):
                    v.fail(label, 19, "%s 에 ref 가 없습니다(카드마다 적음)." % where)
                if not entry.get("facts") or not entry.get("step"):
                    v.fail(label, 19, "%s 에 facts 와 step 을 적어야 합니다." % where)
                check_skel_entry(v, label, skeleton, part, entry, seeds)


def check_skel_entry(v, label, skeleton, part, entry, seeds):
    where = _entry_where(skeleton, part, entry)
    variants = skeleton.get("variants") or {}
    names = [entry.get("from"), entry.get("to")] if part == "change" else [entry.get("variant")]
    missing = [n for n in names if n not in variants]
    if missing:
        v.fail(label, 19, "%s 의 코드 예제 %s 가 뼈대에 없습니다." % (where, ", ".join(map(repr, missing))))
        return
    card = {"id": str(entry.get("id")), "part": part, "entry": entry}
    try:
        if part == "slot":
            check_skel_slot(v, label, skeleton, entry, card)
        elif part == "order":
            check_skel_order(v, label, skeleton, entry, card, seeds)
        elif part == "pick":
            check_skel_pick(v, label, skeleton, entry, card)
        else:
            check_skel_change(v, label, skeleton, entry, card, seeds)
    except (aibank.AiBankError, KeyError, IndexError, TypeError, ValueError) as error:
        v.fail(label, 19, "%s 로 문항을 만들 수 없습니다: %s" % (where, error))


def check_skel_slot(v, label, skeleton, entry, card):
    where = _entry_where(skeleton, "slot", entry)
    lines = skel.lines_of(skeleton, entry["variant"])
    no, token = entry.get("line"), str(entry.get("token") or "")
    if not isinstance(no, int) or not 0 <= no < len(lines):
        v.fail(label, 19, "%s 의 줄 번호가 코드 예제 밖입니다: %r" % (where, no))
        return
    if not token or not skel.token_re(token).search(lines[no]):
        v.fail(label, 19, "%s 의 토큰 %r 가 %d번 줄에 없습니다." % (where, token, no))
        return
    count = sum(len(skel.token_re(token).findall(line)) for line in lines)
    if count != 1:
        v.fail(label, 19, "%s 의 토큰 %r 가 코드 예제 전체에 %d번 나옵니다(한 번이어야 함, 코드 예제 전체가 보여 답이 됨)." % (where, token, count))
    answers = entry.get("answer")
    if not isinstance(answers, list) or not answers or not all(isinstance(a, str) and a.strip() for a in answers):
        v.fail(label, 19, "%s 의 answer 는 글 목록이어야 합니다." % where)
        return
    if answers[0] != token:
        v.fail(label, 19, "%s 의 answer 첫째는 token 과 같아야 합니다: %r" % (where, answers[0]))
    mode = entry.get("mode") or "code"
    if mode not in grade.MODES:
        v.fail(label, 19, "%s 의 mode 를 모릅니다: %s" % (where, mode))
        return
    for answer in answers:
        if any(api in answer for api in LONG_API):
            v.fail(label, 19, "%s 의 정답 %s 는 철자 시험이 되는 긴 API 이름이라 고르기로만 냅니다." % (where, answer))
    line_answer = entry.get("line_answer")
    if line_answer is not None:
        if not isinstance(line_answer, list) or not line_answer or line_answer[0] != lines[no].strip():
            v.fail(label, 19, "%s 의 line_answer 첫째는 들여쓰기를 뺀 %d번 줄이어야 합니다." % (where, no))
            line_answer = None
    for other in skeleton.get("slots") or []:
        if other is entry or other.get("variant") != entry["variant"]:
            continue
        if other.get("line") == no and other.get("line_answer") is not None and line_answer is not None \
                and other.get("line_answer") != line_answer:
            v.fail(label, 19, "%s 와 %s 는 같은 줄이라 line_answer 가 같거나 없어야 합니다." % (where, other.get("id")))
        if str(other.get("id")) > card["id"]:
            mine = {json.dumps(grade.norm(mode, a), default=str) for a in answers}
            theirs = {json.dumps(grade.norm(other.get("mode") or "code", a), default=str) for a in other.get("answer") or []}
            if mine & theirs:
                v.fail(label, 19, "%s 와 %s 의 answer 가 겹칩니다(함께 가리면 칸을 구별할 수 없음)." % (where, other.get("id")))
    view = skel.slot_view(card, skeleton, {})
    for answer in answers:
        if grade.grade_skel(view, [answer])["result"] != "pass":
            v.fail(label, 19, "%s 의 정답 %r 를 채점기가 받지 않습니다." % (where, answer))
    if line_answer:
        whole = skel.slot_view(card, skeleton, {}, masked=[], whole=True)
        for answer in line_answer:
            if grade.grade_skel(whole, [answer])["result"] != "pass":
                v.fail(label, 19, "%s 의 줄 정답 %r 를 채점기가 받지 않습니다." % (where, answer))


def check_skel_order(v, label, skeleton, entry, card, seeds):
    where = _entry_where(skeleton, "order", entry)
    lines = skel.lines_of(skeleton, entry["variant"])
    picked = entry.get("lines") or []
    if len(picked) < 3 or len(set(picked)) != len(picked) or not all(isinstance(k, int) and 0 <= k < len(lines) for k in picked):
        v.fail(label, 19, "%s 의 lines 는 코드 예제 안의 서로 다른 줄 번호 셋 이상이어야 합니다." % where)
        return
    valid = entry.get("valid") or []
    every = list(range(len(picked)))
    if not all(sorted(p) == every for p in valid if isinstance(p, list)) or not all(isinstance(p, list) for p in valid):
        v.fail(label, 19, "%s 의 valid 는 lines 안 위치의 순열 목록이어야 합니다." % where)
        return
    if every not in valid:
        v.fail(label, 19, "%s 의 valid 에 코드 예제 순서 %s 가 없습니다." % (where, every))
    for seed in range(1, seeds + 1):
        view = skel.order_view(card, skeleton, seed)
        texts = [o["text"] for o in view["options"]]
        if len(set(texts)) != 4 or sum(1 for o in view["options"] if o["ok"]) != 1:
            v.fail(label, 19, "%s 시드 %d 의 보기가 서로 다른 넷이 아니거나 정답이 하나가 아닙니다." % (where, seed))
            break
    v.style(label, "%s stem" % where, entry.get("stem", ""), markdown=True)


def check_skel_pick(v, label, skeleton, entry, card):
    where = _entry_where(skeleton, "pick", entry)
    if not str(entry.get("stem") or "").strip():
        v.fail(label, 19, "%s 에 stem 을 적어야 합니다." % where)
    wrong = entry.get("wrong") or []
    if len(wrong) != 3 or not all(isinstance(w, dict) for w in wrong):
        v.fail(label, 19, "%s 의 wrong 은 {text, aim, why} 셋이어야 합니다." % where)
        return
    for n, item in enumerate(wrong, 1):
        for key in ("text", "aim", "why"):
            if not str(item.get(key) or "").strip():
                v.fail(label, 19, "%s 의 %d번 오답의 %s 칸이 비었습니다." % (where, n, key))
    view = skel.pick_view(card, skeleton)
    seen = {}
    for n, option in enumerate(view["options"], 1):
        key = grade.norm("code", option["text"])
        if key in seen:
            v.fail(label, 19, "%s 의 %d번과 %d번 보기가 코드로 같습니다." % (where, seen[key], n))
        seen[key] = n


def check_skel_change(v, label, skeleton, entry, card, seeds):
    where = _entry_where(skeleton, "change", entry)
    if entry.get("from") == entry.get("to"):
        v.fail(label, 19, "%s 의 from 과 to 가 같은 판입니다." % where)
        return
    if not str(entry.get("stem") or "").strip():
        v.fail(label, 19, "%s 에 stem 을 적어야 합니다." % where)
    back = entry.get("back")
    if back is not None and not (isinstance(back, str) and back.strip()):
        v.fail(label, 19, "%s 의 back 은 null 이나 지문 글이어야 합니다." % where)
        back = None
    for reverse in ([False, True] if back else [False]):
        src, dst = (entry["to"], entry["from"]) if reverse else (entry["from"], entry["to"])
        left, right = skel.lines_of(skeleton, src), skel.lines_of(skeleton, dst)
        differ = {skel._change_line(left, i) for i, _, same in skel._pairs(left, right) if not same and i is not None}
        if len(differ) < 2:
            v.fail(label, 19, "%s 의 %s → %s 다른 줄이 %d개입니다(2개 이상)." % (where, src, dst, len(differ)))
            continue
        for seed in range(1, seeds + 1):
            view = skel.change_view(card, skeleton, seed, reverse)
            texts = [o["text"] for o in view["options"]]
            oks = {o["text"] for o in view["options"] if o["ok"]}
            if not 4 <= len(texts) <= 5 or not 2 <= len(oks) <= 3 or oks != {t for t in texts if t in differ} \
                    or len(set(texts)) != len(texts):
                v.fail(label, 19, "%s 시드 %d(%s → %s)의 보기가 4~5개·정답 2~3개·정답 = 다른 줄이 아닙니다." % (where, seed, src, dst))
                break


# 12. 모의고사

def _mock_payload(bank_dir, mid):
    folder = aibank.mock_dir(mid, bank_dir)
    meta = study.read_json(os.path.join(folder, "meta.json"))
    secrets = webbank.load_secrets(folder)
    data = json.loads(secrets.get("items.json", '{"items": []}'))
    if not isinstance(meta, dict) or not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("meta는 객체이며 items.items는 목록이어야 합니다.")
    return meta, data["items"]


class _MockSources:
    """모의고사 검사에서 차시 근거·연습 견본·다른 회차를 읽어 재사용함."""

    def __init__(self, bank_dir, index, seeds, skeletons):
        self.bank_dir, self.index = bank_dir, index
        self.seeds, self.skeletons = max(1, seeds), skeletons
        self.entries = {entry["id"]: entry for entry in index["lessons"] if 1 <= entry["no"] <= 17}
        self.entries.update({group["id"]: group for group in index["patterns"]})
        self.data, self.notes = {}, {}
        self.practice, self.exams = None, None
        self.errata_facts = set()

    def source(self, lid):
        if lid not in self.entries:
            raise ValueError("출제 범위의 차시나 상황별 코드 묶음이 없습니다: %s" % lid)
        if lid not in self.data:
            self.data[lid] = aibank.load_items(self.entries[lid], self.bank_dir, with_gens=False)
        return self.data[lid]

    def note(self, lid):
        if lid not in self.notes:
            entry = self.entries[lid]
            self.notes[lid] = aibank.load_note({"id": entry["page"], "title": entry["title"]}, self.bank_dir)
        return self.notes[lid]

    def practice_stems(self):
        if self.practice is not None:
            return self.practice
        practice = []

        def add(cid, item):
            if not isinstance(item, dict):
                raise ValueError("연습 문항은 객체여야 합니다: %s" % cid)
            alt = item.get("alt") if isinstance(item.get("alt"), dict) else {}
            cloze = item.get("cloze") if isinstance(item.get("cloze"), dict) else {}
            for stem in (item.get("stem"), item.get("text"), alt.get("stem"), cloze.get("text")):
                if isinstance(stem, str) and stem.strip():
                    practice.append((cid, ai_mock_rules.tokens(stem)))
            if item.get("errata"):
                self.errata_facts.update(fid for fid in (item.get("facts") or []) if isinstance(fid, str))

        for lid in self.entries:
            folder = aibank.items_dir(lid, self.bank_dir)
            if not os.path.isfile(os.path.join(folder, "meta.json")) or not aibank.has_secrets(folder):
                continue
            data = self.source(lid)
            for fid, fact in data["facts"].items():
                if fact.get("errata"):
                    self.errata_facts.add(fid)
            for erratum in data["errata"].values():
                self.errata_facts.update(fid for fid in (erratum.get("facts") or []) if isinstance(fid, str))
            for item in data["items"]:
                add(str(item.get("id")) if isinstance(item, dict) else lid, item)
            for topic in data["topics"]:
                for statement in topic.get("statements", []):
                    add(str(statement.get("id")), dict(topic, **statement))
            path = os.path.join(folder, "gens.py")
            if os.path.isfile(path) and lid not in {g["id"] for g in self.index["patterns"]}:
                if IMPORT_BAD.search(study.read_text(path)):
                    raise ValueError("%s의 생성기에 numpy·torch import가 있어 견본을 만들지 않았습니다." % lid)
                for spec in genlib.load_module(path):
                    if spec.meta.get("errata"):
                        self.errata_facts.update(spec.meta.get("facts") or [])
                    for seed in range(self.seeds):
                        add("%s@%d" % (spec.id, seed), genlib.run(spec, seed))
        for group in self.index["patterns"]:
            folder = aibank.items_dir(group["id"], self.bank_dir)
            if not os.path.isfile(os.path.join(folder, "meta.json")):
                continue
            path = os.path.join(folder, "gens.py")
            if os.path.isfile(path):
                if IMPORT_BAD.search(study.read_text(path)):
                    raise ValueError("%s의 생성기에 numpy·torch import가 있어 견본을 만들지 않았습니다." % group["id"])
                data = aibank.load_items({"id": group["id"]}, self.bank_dir)
                note = aibank.load_note({"id": group["page"], "title": group["title"]}, self.bank_dir)
                units = {key: info for key, info in group["units"].items() if key in note["visible"]}
                for card in aibank.pattern_gen_cards(group, data, units):
                    if card["errata"]:
                        self.errata_facts.update(card["facts"])
                    for seed in range(self.seeds):
                        add("%s@%d" % (card["id"], seed), genlib.run(card["gen"], seed))
            skeletons, cards = ai_seal.pattern_cards(self.bank_dir, group)
            for card in cards:
                skeleton = skeletons[card["pattern"]]
                if card["part"] == "slot":
                    for name, view in ai_seal.skel_samples(card, skeleton, cards):
                        add("%s %s" % (card["id"], name), view)
                else:
                    for seed in range(3):
                        add("%s@%d" % (card["id"], seed), ai_seal.skel_choice(card, skeleton, seed))
                if card["errata"]:
                    self.errata_facts.update(card["facts"])
        self.practice = practice
        return practice

    def other_exams(self):
        if self.exams is None:
            exams = {}
            for entry in self.index["mocks"]:
                mid = entry["id"]
                if mid not in ai_mock_rules.LESSON_COUNTS or not os.path.isfile(os.path.join(
                        aibank.mock_dir(mid, self.bank_dir), "meta.json")):
                    continue
                _, items = _mock_payload(self.bank_dir, mid)
                if not all(isinstance(item, dict) for item in items):
                    raise ValueError("%s의 비교 문항에 객체가 아닌 값이 있습니다." % mid)
                exams[mid] = items
            self.exams = exams
        return self.exams


def _mock_code(v, label, item):
    """코드 울타리와 등록 답으로 채운 빈칸 코드의 구문을 확인함. 실행하지 않음."""
    cid = item["id"]
    for where, text, _ in card_texts({"id": cid, "kind": item["kind"], "item": item}):
        if ai_mock_rules.code_blocks(text)[1]:
            v.fail(label, 12, "%s의 %s에 닫히지 않은 코드 울타리가 있습니다." % (cid, where))
    if item["kind"] != "blank":
        return
    answers = iter((blank.get("answer") or ["____"])[0] if isinstance(blank.get("answer"), list)
                   else "____" for blank in item.get("blanks", []))
    filled = aibank.BLANK.sub(lambda found: str(next(answers, found.group())), item.get("stem", ""))
    for language, source in ai_mock_rules.code_blocks(filled)[0]:
        if language in ("", "py", "python"):
            try:
                ast.parse(textwrap.dedent(source))
            except (SyntaxError, ValueError) as error:
                v.fail(label, 12, "%s의 등록 답을 채운 코드 구문을 읽지 못합니다: %s" % (cid, error))


def _mock_evidence(v, label, item, sources):
    cid, lid = item["id"], item.get("lesson")
    if not isinstance(lid, str) or lid not in sources.entries or not aibank.LESSON_ID.fullmatch(lid):
        v.fail(label, 12, "%s의 lesson이 출제 범위의 차시가 아닙니다: %r" % (cid, lid))
        return
    try:
        data, note = sources.source(lid), sources.note(lid)
        facts, errata = dict(data["facts"]), dict(data["errata"])
        if isinstance(item.get("pattern"), str) and item["pattern"] in sources.skeletons:
            for group in sources.index["patterns"]:
                extra = sources.source(group["id"])
                facts.update(extra["facts"])
                errata.update(extra["errata"])
                if item.get("unit") in group["units"]:
                    note = sources.note(group["id"])
        fids, refs = item.get("facts"), item.get("ref")
        if not isinstance(fids, list) or not fids or not all(isinstance(fid, str) and fid for fid in fids):
            v.fail(label, 12, "%s의 facts는 비어 있지 않은 사실 ID 목록이어야 합니다." % cid)
            fids = []
        unit, step = item.get("unit"), item.get("step")
        current = note["units"].get(unit) if isinstance(unit, str) else None
        match = re.fullmatch(r"(\w+)/(\d+)", str(step or ""))
        if current is None or not match or match.group(1) != unit:
            v.fail(label, 12, "%s의 unit·step이 실제 학습 단계가 아닙니다: %r / %r" % (cid, unit, step))
        else:
            steps = [part for part in current["steps"] if part["no"]]
            number = int(match.group(2))
            if not 1 <= number <= len(steps):
                v.fail(label, 12, "%s의 step %s가 없습니다." % (cid, step))
            elif not set(steps[number - 1]["facts"]) & set(fids):
                v.fail(label, 12, "%s의 facts가 step %s의 사실 줄과 겹치지 않습니다." % (cid, step))
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            v.fail(label, 12, "%s의 ref는 비어 있지 않은 근거 목록이어야 합니다." % cid)
        else:
            recorded = {ref for fid in fids for ref in facts.get(fid, {}).get("where", [])}
            for ref in refs:
                if ref_kind(ref)[0] is None and not (label == "m4" and ref.startswith("https://") and ref in recorded):
                    v.fail(label, 9, "%s의 ref 형식을 읽지 못합니다: %s" % (cid, ref))
            documented = label == "m4" and refs[0] in recorded and (ref_kind(refs[0])[0] == "doc" or refs[0].startswith("https://"))
            if not first_ref_ok(refs[0], lesson_no(lid), aibank.course_of(lid)) and not documented:
                v.fail(label, 9, "%s의 첫 ref는 %s의 강의·과제·요약 근거여야 합니다." % (cid, lid))
        les = Lesson({"id": label}, None, {"facts": facts, "errata": errata}, [])
        card = {"id": cid, "kind": item["kind"], "item": item, "facts": fids, "errata": item.get("errata") or []}
        check_facts(v, les, card, set())
        for fid in fids:
            fact = facts.get(fid) or {}
            if fact and fact.get("verdict") not in VERDICTS:
                v.fail(label, 7, "%s의 사실 %s의 verdict를 모릅니다: %r" % (cid, fid, fact.get("verdict")))
            if fid in sources.errata_facts or fact.get("errata"):
                v.fail(label, 12, "%s가 정정 근거 사실 %s를 사용합니다." % (cid, fid))
            if fact.get("concept_only") and (
                    (item["kind"] == "blank" and any(ai_mock_rules.numeric_blank(b) for b in item["blanks"])) or
                    (item["kind"] == "choice" and ai_mock_rules.numeric_choices(item))):
                v.fail(label, 12, "%s가 concept_only 사실 %s를 숫자·모양으로 묻습니다." % (cid, fid))
    except (aibank.AiBankError, ValueError, TypeError, KeyError) as error:
        v.fail(label, 12, "%s의 차시 근거를 읽지 못합니다: %s" % (cid, error))


MIXED_BLUEPRINT = dict({"i%02d" % n: 1 for n in range(1, 18) if n != 10}, a01=5, a02=6, a03=5)


def _mixed_mock_problems(entry, meta, items, sources):
    """m4의 실제 문항 배분과 명시한 분류를 대조함. 초안도 검사함."""
    out = []
    expected = {"scope": "mixed", "courses": ["intro", "app"], "count": 32, "minutes": 120,
                "course_counts": {"intro": 16, "app": 16}, "blueprint": MIXED_BLUEPRINT, "range": [1, 17]}
    for name, data in (("index", entry), ("meta.json", meta)):
        for key, value in expected.items():
            if data.get(key) != value or (key in ("count", "minutes") and type(data.get(key)) is not int):
                out.append("m4 %s의 %s가 혼합 배분과 일치하지 않습니다." % (name, key))
        declared = data.get("blueprint")
        if isinstance(declared, dict) and any(type(n) is not int for n in declared.values()):
            out.append("m4 %s의 blueprint 값은 정수여야 합니다." % name)
    revision = entry.get("blueprint_revision")
    if not isinstance(revision, str) or not revision.strip() or meta.get("blueprint_revision") != revision:
        out.append("m4의 blueprint_revision이 없거나 서로 일치하지 않습니다.")
    if type(meta.get("format")) is not int or meta.get("format") != 1 or meta.get("id") != "m4":
        out.append("m4 meta.json의 format=1과 id=m4를 확인하세요.")
    if type(meta.get("draft")) is not bool:
        out.append("m4 meta.json의 draft는 bool이어야 합니다.")
    if not isinstance(meta.get("time_basis"), str) or not meta["time_basis"].strip():
        out.append("m4의 time_basis에 연습 기본 시간의 근거를 적으세요.")
    for field, expected_counts in (("course", {"intro": 16, "app": 16}), ("lesson", MIXED_BLUEPRINT),
                                   ("kind", {"blank": 16, "choice": 16}), ("level", {1: 8, 2: 16, 3: 8})):
        counts = collections.Counter(item.get(field) for item in items if isinstance(item.get(field), (str, int)))
        if counts != expected_counts:
            out.append("m4의 실제 %s 배분이 일치하지 않습니다: %s" % (field, dict(counts)))
    if sorted(item["id"] for item in items) != ["m4-%02d" % n for n in range(1, 33)]:
        out.append("m4의 문항 ID는 m4-01부터 m4-32까지 한 번씩 사용하세요.")
    for item in items:
        cid, lid = item["id"], item.get("lesson")
        lesson = sources.entries.get(lid) if isinstance(lid, str) else None
        if (not lesson or lid not in MIXED_BLUEPRINT or lesson.get("course") != item.get("course")
                or aibank.course_of(lid) != item.get("course")):
            out.append("%s의 course·lesson이 개론 1~17차시·응용 1~3차시와 일치하지 않습니다." % cid)
        for key in ("concept", "family", "format", "transferaxis", "level_reason"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                out.append("%s의 %s는 비어 있지 않은 글이어야 합니다." % (cid, key))
        conditions = item.get("conditions")
        if not isinstance(conditions, list) or not conditions or not all(isinstance(c, str) and c.strip() for c in conditions):
            out.append("%s의 conditions는 비어 있지 않은 조건 목록이어야 합니다." % cid)
        if item.get("blueprint_revision") != revision:
            out.append("%s의 blueprint_revision이 회차와 일치하지 않습니다." % cid)
        if type(item.get("deep", False)) is not bool or type(item.get("multi", False)) is not bool:
            out.append("%s의 deep·multi는 bool이어야 합니다." % cid)
        if item["kind"] == "blank" and item.get("allowed_answers") != [b.get("answer") for b in item["blanks"]]:
            out.append("%s의 allowed_answers가 빈칸의 허용 답과 일치하지 않습니다." % cid)
    return out


def _mixed_duplicates(items, exams):
    """기존 회차와 지문·보기 중복만 비교함. 세 회의 사실 사용 제한은 유지함."""
    seen, out = {}, []
    for group in list(exams.values()) + [items]:
        for item in group:
            key = ai_mock_rules.question_key(item)
            if key in seen and (item in items or seen[key].startswith("m4-")):
                out.append("회차 간 같은 문항입니다: %s / %s" % (seen[key], item["id"]))
            seen[key] = item["id"]
    return out


def _mixed_mock_evidence(v, label, item, sources):
    """보조 차시까지 사실 목록을 대조하며 정정·미확인 사실을 제외함."""
    cid = item["id"]
    try:
        related = item.get("related_sources")
        if not isinstance(related, list):
            raise ValueError("related_sources는 차시·사실 목록이어야 합니다.")
        groups = [{"lesson": item.get("lesson"), "facts": item.get("facts")}] + related
        expected = []
        for group in groups:
            lid, fids = group["lesson"], group["facts"]
            if (lid not in sources.entries or not re.fullmatch(r"i(?:0[1-9]|1[0-7])|a0[1-3]", lid)
                    or not isinstance(fids, list) or not fids or not all(isinstance(f, str) for f in fids)):
                raise ValueError("sourcefacts의 차시·사실이 공개 범위와 일치하지 않습니다.")
            data, note = sources.source(lid), sources.note(lid)
            covered = {fid for unit in note["units"].values() for step in unit["steps"] for fid in step["facts"]}
            for fid in fids:
                expected.append({"lesson": lid, "id": fid})
                fact = data["facts"].get(fid)
                if not fact or fid not in covered:
                    raise ValueError("%s/%s를 사실 목록과 공개 학습 단계에서 찾지 못했습니다." % (lid, fid))
                if fid in sources.errata_facts or fact.get("errata"):
                    raise ValueError("정정 근거 사실 %s/%s를 사용합니다." % (lid, fid))
            les = Lesson({"id": label}, None, data, [])
            check_facts(v, les, {"id": cid, "kind": item["kind"], "item": item, "facts": fids, "errata": []}, set())
            for fid in fids:
                fact = data["facts"][fid]
                if fact.get("verdict") not in VERDICTS:
                    raise ValueError("%s/%s의 verdict를 모릅니다." % (lid, fid))
                if fact.get("concept_only") and ((item["kind"] == "blank" and any(
                        ai_mock_rules.numeric_blank(b) for b in item["blanks"])) or
                        (item["kind"] == "choice" and ai_mock_rules.numeric_choices(item))):
                    raise ValueError("concept_only 사실 %s/%s를 숫자·모양으로 묻습니다." % (lid, fid))
        if item.get("sourcefacts") != expected:
            raise ValueError("sourcefacts가 주 차시·보조 차시의 사실 목록과 일치하지 않습니다.")
    except (aibank.AiBankError, ValueError, TypeError, KeyError) as error:
        v.fail(label, 12, "%s의 혼합 근거를 읽지 못합니다: %s" % (cid, error))


def check_mock(v, bank_dir, mock, ids, sources=None):
    """회차별 배분·근거·연습 및 회차 간 겹침을 확인함."""
    label = mock["id"]
    mixed = label == "m4"
    strict = mixed or label in ai_mock_rules.LESSON_COUNTS
    v.head(label, mock["title"])
    try:
        meta, raw_items = _mock_payload(bank_dir, label)
    except (OSError, webbank.BankError, ValueError, AttributeError) as error:
        v.fail(label, 12, "items.json을 읽을 수 없습니다: %s" % error)
        return None
    if len(raw_items) != mock["count"]:
        v.fail(label, 12, "문항이 %d개입니다(%d개)." % (len(raw_items), mock["count"]))
    items = []
    for item in raw_items:
        if not isinstance(item, dict):
            v.fail(label, 12, "문항은 객체여야 합니다.")
            continue
        cid, kind = item.get("id"), item.get("kind")
        if not isinstance(cid, str) or not re.fullmatch(re.escape(label) + r"-\d{2,3}", cid):
            v.fail(label, 12, "문항 id는 %s-01 형식이어야 합니다: %r" % (label, cid))
            continue
        if cid in ids:
            v.fail(label, 12, "id 가 두 번 쓰였습니다: %s" % cid)
        ids[cid] = label
        if kind not in ("blank", "choice"):
            v.fail(label, 12, "%s는 빈칸이나 고르기여야 합니다." % cid)
            continue
        if item.get("errata"):
            v.fail(label, 12, "%s 는 정정 주제(errata)라 모의고사에 넣지 않습니다." % cid)
        if not isinstance(item.get("stem"), str) or not item["stem"].strip():
            v.fail(label, 12, "%s의 stem은 비어 있지 않은 글이어야 합니다." % cid)
            continue
        if strict and (not isinstance(item.get("explain"), str) or not item["explain"].strip()):
            v.fail(label, 12, "%s의 explain은 비어 있지 않은 글이어야 합니다." % cid)
        les = Lesson({"id": label}, None, {}, [])
        card = {"id": cid, "kind": kind, "item": item}
        if kind == "blank":
            blanks = item.get("blanks")
            if not isinstance(blanks, list) or not all(isinstance(b, dict) for b in blanks):
                v.fail(label, 12, "%s의 blanks는 빈칸 객체 목록이어야 합니다." % cid)
                continue
            if not 1 <= len(blanks) <= 2:
                v.fail(label, 12, "%s의 빈칸 수는 1~2개여야 합니다." % cid)
            check_blank(v, les, card)
        else:
            options = item.get("options")
            if not isinstance(options, list) or not all(isinstance(option, dict) for option in options):
                v.fail(label, 12, "%s의 options는 보기 객체 목록이어야 합니다." % cid)
                continue
            if any(type(option.get("ok")) is not bool for option in options):
                v.fail(label, 12, "%s의 보기 ok는 bool이어야 합니다." % cid)
            if any(not isinstance(option.get("text"), str) or not option["text"].strip() for option in options):
                v.fail(label, 12, "%s의 보기 text는 비어 있지 않은 글이어야 합니다." % cid)
            check_choice(v, les, card, [])
            if item.get("multi") and len(grade.right_options(item)) != 2:
                v.fail(label, 12, "%s 는 모두 고르기인데 답이 2개가 아닙니다." % cid)
        if strict:
            if type(item.get("level")) is not int or item["level"] not in (1, 2, 3):
                v.fail(label, 12, "%s의 level은 1~3 정수여야 합니다." % cid)
            _mock_code(v, label, item)
            for where, text, markdown in card_texts(card):
                v.style(label, where, text, markdown)
        items.append(item)
    if sum(bool(item.get("deep")) for item in items) > 2:
        v.fail(label, 12, "deep 문항은 2개 이하여야 합니다.")
    if strict:
        if sources is None:
            try:
                sources = _MockSources(bank_dir, aibank.read_index(bank_dir), v.opts.seeds, skel.load_patterns(bank_dir))
                aibank.load_common(bank_dir)
            except (aibank.AiBankError, ValueError) as error:
                v.fail(label, 12, "모의고사 비교 자료를 읽지 못합니다: %s" % error)
                return None
        problems = (_mixed_mock_problems(mock, meta, items, sources) if mixed else
                    ai_mock_rules.exam_problems(label, mock, meta, items, sources.skeletons))
        for message in problems:
            v.fail(label, 12, message)
        try:
            practice = sources.practice_stems()
            for message in ai_mock_rules.practice_problems(items, practice):
                v.fail(label, 12, message)
            exams = sources.other_exams()
            cross = (_mixed_duplicates(items, exams) if mixed else ai_mock_rules.cross_problems(label, exams))
            for message in cross:
                v.fail(label, 12, message)
        except (aibank.AiBankError, genlib.GenError, OSError, ValueError, TypeError, KeyError) as error:
            v.fail(label, 12, "모의고사 비교 자료를 읽지 못합니다: %s" % error)
        for item in items:
            _mock_evidence(v, label, item, sources)
            if mixed:
                _mixed_mock_evidence(v, label, item, sources)
    data = {"dir": aibank.mock_dir(label, bank_dir), "items": items, "topics": [], "facts": {}, "errata": {}, "sources": {}, "gens": []}
    try:
        return Lesson({"id": label}, None, data, aibank.cards_of({"id": label}, data))
    except (TypeError, ValueError, KeyError) as error:
        v.fail(label, 12, "모의고사 채점 카드를 읽지 못합니다: %s" % error)
        return None



# 13~15. 그림, 한도, 비밀 값

def quoted_clip_problems(credit):
    """확인한 원작자와 공식 자산 두 개의 짧은 인용 조건만 검사함."""
    problems = []
    for key, wanted in (("author", QUOTED_CLIP_AUTHOR), ("permission_url", QUOTED_CLIP_PERMISSION)):
        if credit.get(key) != wanted:
            problems.append("%s는 %s여야 합니다." % (key, wanted))
    if credit.get("url") not in QUOTED_CLIP_URLS:
        problems.append("url은 확인한 공식 MP4 두 개 가운데 하나여야 합니다.")
    seconds = credit.get("source_seconds")
    if type(seconds) not in (int, float) or not 0 < seconds < 60 or not math.isfinite(seconds):
        problems.append("source_seconds는 0보다 크고 60보다 작은 유한한 수여야 합니다.")
    return problems


def check_figures(v, bank_dir, index, manifest):
    data = ai_art.read_manifest(manifest)
    total = 0
    quoted_seconds = []
    for page in index["pages"]:
        pdir = aibank.page_dir(page["id"], bank_dir)
        label = page["id"]
        try:
            meta = study.read_json(os.path.join(pdir, "meta.json"))
        except (OSError, ValueError):
            continue
        credit_rows = [c for c in meta.get("credits") or [] if isinstance(c, dict)]
        credits = {str(c.get("file")): c for c in credit_rows}
        for credit in credit_rows:
            if credit.get("url") in QUOTED_CLIP_URLS and credit.get("license") != QUOTED_CLIP_LICENSE:
                v.fail(label, 13, "%s의 공식 MP4 인용은 확인한 짧은 인용 허락 이름으로 적습니다." % credit.get("file", "?"))
            if credit.get("license") == QUOTED_CLIP_LICENSE:
                problems = quoted_clip_problems(credit)
                for problem in problems:
                    v.fail(label, 13, "%s의 짧은 인용 허락: %s" % (credit.get("file", "?"), problem))
                if not problems:
                    quoted_seconds.append(credit["source_seconds"])
        if not os.path.isfile(os.path.join(pdir, "page.md")):
            continue
        parsed = aibank.parse_page(study.read_text(os.path.join(pdir, "page.md")), meta.get("sections") or {}, pdir)
        blocks = [b for key in parsed["order"] for s in parsed["units"][key]["steps"] for b in s["blocks"] if b["kind"] == "figure"]
        blocks += [b["figure"] for key in parsed["order"] for s in parsed["units"][key]["steps"] for b in s["blocks"]
                   if b["kind"] == "formula" and not b.get("error")]
        for block in blocks:
            path = block["path"]
            if not block["file"] or not os.path.isfile(path):
                continue
            rel = "learn/%s/%s" % (page["id"], block["file"])
            for problem in ai_art.image_problems(path):
                v.fail(label, 13, "%s: %s" % (block["file"], problem))
            if block["file"].lower().endswith(".gif"):
                try:
                    frames = ai_art.image_info(path)["frames"]
                except ValueError:
                    frames = None
                if frames is not None and frames != len(block["frames"]):
                    v.fail(label, 13, "%s 의 장이 %d개인데 프레임 줄이 %d개입니다." % (block["file"], frames, len(block["frames"])))
            entry = data["files"].get(rel)
            credit = credits.get(block["file"])
            if entry is not None:
                if credit and credit.get("license") == QUOTED_CLIP_LICENSE:
                    v.fail(label, 13, "%s는 인용 자산이므로 직접 그린 그림의 manifest에 등록하지 않습니다." % block["file"])
                if entry.get("sha256") != ai_art.file_sha(path):
                    v.fail(label, 13, "%s 가 manifest 의 해시와 다릅니다. 다시 그렸으면 `python -m tools.ai_art %s --record` 로 적으세요."
                           % (block["file"], page["id"]))
                continue
            if credit is None:
                v.fail(label, 13, "manifest 에 없는 그림입니다: %s. 직접 그린 그림은 manifest 에 적고, 가져온 그림은 meta.json credits 에 "
                                  "출처를 적습니다." % block["file"])
            elif credit.get("license") != QUOTED_CLIP_LICENSE and (credit.get("license") not in ALLOWED_LICENSES or not credit.get("author") or not credit.get("url")):
                v.fail(label, 13, "%s 의 credits 는 author·url 과 허용 라이선스(%s)가 있어야 합니다." % (block["file"], ", ".join(ALLOWED_LICENSES)))
            elif "출처" not in block["caption"] and not any(h == "그림 출처" for h, _ in parsed["extra"]):
                v.fail(label, 13, "%s 는 가져온 그림인데 캡션이나 「그림 출처」 절에 출처가 없습니다." % block["file"])
        for key in parsed["order"]:
            for step in parsed["units"][key]["steps"]:
                for block in step["blocks"]:
                    if block["kind"] == "levels" and not block.get("error"):
                        for level in block["levels"]:
                            check_level_figure(v, label, data, page["id"], key, step, block, level)
        assets = os.path.join(pdir, "assets")
        size = sum(os.path.getsize(os.path.join(assets, f)) for f in os.listdir(assets)) if os.path.isdir(assets) else 0
        if size > ai_art.LIMITS["note_bytes"]:
            v.fail(label, 14, "그림 합계가 %.1fMB 입니다(학습 노트 하나 %.1fMB 이하)." % (size / 1048576.0, ai_art.LIMITS["note_bytes"] / 1048576.0))
        total += size
    if math.fsum(quoted_seconds) >= 60:
        v.fail("index", 13, "이 원작자의 짧은 인용 credits 전체 source_seconds 합계는 60초 미만이어야 합니다.")
    if total > ai_art.LIMITS["total_bytes"]:
        v.fail("index", 14, "그림 합계가 %.1fMB 입니다(%dMB 이하)." % (total / 1048576.0, ai_art.LIMITS["total_bytes"] // 1048576))
    elif total > ai_art.LIMITS["warn_bytes"]:
        v.warn("index", 14, "그림 합계가 %.1fMB 입니다. 비중이 낮은 차시의 GIF 를 PNG 로 바꾸세요." % (total / 1048576.0))


def check_level_figure(v, label, manifest, pid, key, step, block, level):
    """세 수준 블록 그림 하나(13). 이름이 <단원>-<단계 번호><수준 번호>(7살 1, 15살 2, 20살 3)이고 PNG, 캡션("그림 N." 으로
    시작하지 않음)·내용이 있고, 파일이 있고 한도 안이고 manifest 해시와 같아야 함. 그림이 없는 것은 8 노트 블록에서 봄."""
    fig = level.get("figure")
    if not fig:
        return
    where = "%s/%s %s %d살" % (key, step["no"], block.get("id") or "?", level["level"])
    name = "%s-%s%d" % (key, step["no"], LEVEL_DIGIT[level["level"]])
    if fig["file"] != "assets/%s.png" % name:
        v.fail(label, 13, "%s 그림 이름은 블록 자리와 수준을 따라 assets/%s.png 여야 합니다: %s" % (where, name, fig["file"]))
    if not fig["caption"].strip():
        v.fail(label, 13, "%s 그림에 caption 이 없습니다." % where)
    elif FIGURE_NO.match(fig["caption"]):
        v.fail(label, 13, "%s 그림 caption 은 \"그림 N.\" 으로 시작하지 않습니다: %s" % (where, clip(fig["caption"], 40)))
    if not fig["content"].strip():
        v.fail(label, 13, "%s 그림에 content 가 없습니다." % where)
    path = fig["path"]
    if not os.path.isfile(path):
        v.fail(label, 13, "%s 그림 파일이 없습니다: %s" % (where, fig["file"]))
        return
    with open(path, "rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            v.fail(label, 13, "%s 그림 %s 가 PNG 가 아닙니다." % (where, fig["file"]))
            return
    for problem in ai_art.image_problems(path):
        v.fail(label, 13, "%s: %s" % (fig["file"], problem))
    entry = manifest["files"].get("learn/%s/%s" % (pid, fig["file"]))
    if entry is None:
        v.fail(label, 13, "manifest 에 없는 그림입니다: %s. 그린 뒤 `python -m tools.ai_art %s --record` 로 적습니다." % (fig["file"], pid))
    elif entry.get("sha256") != ai_art.file_sha(path):
        v.fail(label, 13, "%s 가 manifest 의 해시와 다릅니다. 다시 그렸으면 `python -m tools.ai_art %s --record` 로 적으세요." % (fig["file"], pid))
    try:
        info = ai_art.image_info(path)
    except ValueError:
        return
    if info["bytes"] > LEVEL_PNG["bytes"]:
        v.warn(label, 13, "%s 가 %.1fKB 입니다(%dKB 이하로)." % (fig["file"], info["bytes"] / 1024.0, LEVEL_PNG["bytes"] // 1024))
    if (info["width"], info["height"]) != LEVEL_PNG["size"]:
        v.warn(label, 13, "%s 가 %d×%d 입니다(%d×%d 로)." % ((fig["file"], info["width"], info["height"]) + LEVEL_PNG["size"]))


def check_secrets(v, bank_dir):
    """공개 파일과 봉인 안 글에 키·토큰 꼴이 없는지. 해시를 적는 review.json·facts.json·manifest 는 보지 않음."""
    for rel, path in verify_web.walk_files(bank_dir, skip=("assets", "__pycache__", "lecture")):
        name = os.path.basename(rel)
        if not name.endswith(TEXT_EXT) or name in ("review.json", "sealed.json", "art_manifest.json") or "/work/" in "/" + rel:
            continue
        found = SECRET.search(study.read_text(path))
        if found:
            v.fail("secrets", 15, "%s 에 키나 토큰처럼 보이는 글이 있습니다: %s…" % (rel, found.group(0)[:6]))
    for parent in ("items", "mocks"):
        folder = os.path.join(bank_dir, parent)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            try:
                files = webbank.load_secrets(os.path.join(folder, name))
            except webbank.BankError:
                continue
            for rel, text in files.items():
                if rel in ("facts.json", "review.json"):
                    continue
                found = SECRET.search(text)
                if found:
                    v.fail("secrets", 15, "%s/%s 봉인 안 %s 에 키나 토큰처럼 보이는 글이 있습니다: %s…" % (parent, name, rel, found.group(0)[:6]))


# 16. 서명

def review_files(folder, secrets, bank_dir=None, patterns=False):
    """서명이 덮는 파일의 sha256. 폴더의 공개 파일 전부(sealed.json 뺌)와 work/ 의 봉인 글(review.json 뺌). 글 파일은 LF 기준
    글로(.py 포함, Windows CRLF 에서도 맞음), 그림은 바이트로. patterns 면 ai/patterns/*.json 을 patterns/… 키로 더함."""
    files = {}
    for rel, path in verify_web.walk_files(folder, skip=("work", "__pycache__")):
        if rel == webbank.SEALED_NAME:
            continue
        files[rel] = verify_web.text_sha(study.read_text(path)) if rel.endswith(TEXT_EXT) else verify_web.file_sha(path)
    for rel, text in (secrets or {}).items():
        if rel != "review.json":
            files["work/" + rel] = verify_web.text_sha(text)
    if patterns and bank_dir:
        pdir = os.path.join(bank_dir, "patterns")
        for name in sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []:
            if name.endswith(".json"):
                files["patterns/" + name] = verify_web.text_sha(study.read_text(os.path.join(pdir, name)))
    return files


def grade_skel_answer(key, value, lessons, terms):
    """상황별 코드 공개본 답안 칸 하나. (맞았는지, 틀린 꼬리표) 를 돌려주고 뼈대 키가 아니면 None. 키는 "S1 표준형 전체"(코드 예제의
    모든 자리, 칸마다 글), "pc-o01 시드 1"·"pc-x01 시드 1"(고르기, {"picked": [문제지 번호]}), "pc-p01"(맞는 줄 고르기),
    "pc-k02 f2"(뼈대 빈칸 견본, 칸마다 글). 빈칸은 모든 칸이 맞아야 맞음이고 틀린 칸은 자리 id 로 보임."""
    groups = [les for les in lessons if les.group is not None]
    cards = {c["id"]: c for les in groups for c in les.cards if c["kind"] == "skel"}
    skeletons = next((les.skeletons for les in groups), {})

    def blanks(view):
        values = value if isinstance(value, list) else [value]
        per = grade.grade_item(view, values, terms)["per_blank"]
        bad = [b["slot"] for b, ok in zip(view["blanks"], per) if not ok]
        return not bad, "%s(%s)" % (key, ", ".join(bad)) if bad else key

    def choice(card, view):
        order = ai_seal.skel_option_order(card, len(view["options"]))
        got = value.get("picked") if isinstance(value, dict) else value
        picked = [order[p - 1] for p in got or [] if isinstance(p, int) and 1 <= p <= len(order)]
        return grade.grade_choice(view, picked)["result"] == "pass", key

    found = ai_seal.WHOLE_KEY.match(key)
    if found and found.group(1) in skeletons:
        view = ai_seal.whole_view(skeletons[found.group(1)], found.group(2), list(cards.values()))
        return blanks(view) if view else None
    found = ai_seal.SAMPLE_KEY.match(key)
    if found and found.group(1) in cards:
        card = cards[found.group(1)]
        samples = dict(ai_seal.skel_samples(card, skeletons[card["pattern"]], list(cards.values())))
        return blanks(samples[found.group(2)]) if found.group(2) in samples else None
    found = ai_seal.SEED_KEY.match(key)
    if found and found.group(1) in cards:
        card = cards[found.group(1)]
        return choice(card, ai_seal.skel_choice(card, skeletons[card["pattern"]], int(found.group(2))))
    card = cards.get(key)
    if card is not None and card["part"] == "pick":
        return choice(card, ai_seal.skel_choice(card, skeletons[card["pattern"]]))
    return None


def grade_answers(v, label, path, lessons, bank_dir, first=False):
    """재풀이 답안을 채점함. {"cards", "correct", "wrong", "gens": {"checked", "seeds"}} 를 돌려주고 틀린 카드를 보여 줌.
    상황별 코드 키는 grade_skel_answer 가 채점하고, first 면(서명의 first_pass) 2단계 견본(skel.md 의 "pc-k02 f2")은 세지 않음.
    문장 칸은 공개본 꼬리표(<주제 id>-<번호>)를 ai_seal.statement_rows 로 문장 id 로 되돌림. 빈칸판이 있는 문장은 ok 와 cloze 가
    둘 다 맞아야 맞음이고, 빈칸판이 없는 문장의 cloze 는 보지 않음. 고르기 칸에 order 가 없으면 ai_seal.option_order 로 공개본의
    보기 순서를 다시 만듦. 생성기 고르기 표본이 {"picked"} 꼴이면 ai_seal.gen_option_order 로 섞은 순서를 되돌림. 예전 꼴(문장
    id 를 키로 쓴 답안, order 를 적은 고르기, 원래 번호를 적은 생성기 표본)도 그대로 채점함."""
    try:
        answers = study.read_json(path)
    except (OSError, ValueError) as error:
        v.fail(label, 17, "답안을 읽을 수 없습니다: %s" % error)
        return None
    cards = {c["id"]: c for les in lessons for c in les.cards}
    tags = {tag: str(s["id"]) for les in lessons for topic in les.data["topics"] for tag, s in ai_seal.statement_rows(topic)}
    terms = grade.term_map(aibank.read_terms(bank_dir))
    correct, wrong, gens, seeds = 0, [], 0, set()
    for key, value in sorted(answers.items()):
        if first and ai_seal.SAMPLE_KEY.match(key):
            continue
        graded = grade_skel_answer(key, value, lessons, terms)
        if graded is not None:
            if graded[0]:
                correct += 1
            else:
                wrong.append(graded[1])
            continue
        cid = tags.get(key, key)
        card = cards.get(cid)
        if card is None:
            v.warn(label, 17, "답안의 %s 가 문항에 없습니다." % key)
            continue
        ok = False
        if card["kind"] == "blank":
            ok = grade.grade_item(card["item"], value, terms)["result"] == "pass"
        elif card["kind"] == "choice":
            order = value.get("order") or ai_seal.option_order(card["item"])
            picked = [order[p - 1] for p in value.get("picked") or [] if 1 <= p <= len(order)]
            ok = grade.grade_choice(card["item"], picked)["result"] == "pass"
        elif card["kind"] == "stmt":
            got = value if isinstance(value, dict) else {}
            ok = got.get("ok") is card["stmt"].get("ok")
            cloze = card["stmt"].get("cloze")
            if ok and cloze:
                blank = {"answer": cloze["answer"], "mode": cloze.get("mode") or "word"}
                typed = got.get("cloze")
                typed = [typed] if isinstance(typed, str) else typed
                ok = grade.grade_item({"stem": cloze["text"], "blanks": [blank]}, typed, terms)["result"] == "pass"
        elif card["kind"] == "gen":
            gens += 1
            ok = True
            for seed, got in sorted((value or {}).items()):
                seeds.add(seed)
                made = genlib.run(card["gen"], int(seed))
                if made["kind"] == "blank":
                    good = grade.grade_item(made, got, terms)["result"] == "pass"
                elif isinstance(got, dict):
                    order = ai_seal.gen_option_order(card["gen"].id, seed, len(made["options"]))
                    picked = [order[p - 1] for p in got.get("picked") or [] if isinstance(p, int) and 1 <= p <= len(order)]
                    good = grade.grade_choice(made, picked)["result"] == "pass"
                else:
                    picked = [p - 1 for p in got if isinstance(p, int)] if isinstance(got, list) else \
                        [n for n, o in enumerate(made["options"]) if o["text"] == str(got)]
                    good = grade.grade_choice(made, picked)["result"] == "pass"
                ok = ok and good
        if ok:
            correct += 1
        else:
            wrong.append(cid)
    v.note(label, "재풀이 대조: 맞음 %d / %d%s" % (correct, correct + len(wrong), (", 틀림 " + verify_web.listing(wrong, 12)) if wrong else ""))
    for cid in wrong:
        v.warn(label, 17, "%s 를 재풀이자가 틀렸습니다. 원인을 하나로 정해 findings 에 적으세요(정답 틀림, 두 가지로 읽힘, 받는 답 빠짐, "
                          "공정한 함정, oracle 불일치)." % cid)
    return {"cards": correct + len(wrong), "correct": correct, "wrong": wrong, "gens": {"checked": gens, "seeds": len(seeds)}}


def note_levels(pid, note):
    """학습 노트의 세 수준 물음을 {"l04 4b/3 v1 7": 수준} 으로(ai_seal.py levels 의 답안 키와 같은 꼴)."""
    out = {}
    for key in (note or {}).get("order", []):
        for step in note["units"][key]["steps"]:
            for block in step["blocks"]:
                if block["kind"] == "levels" and not block.get("error"):
                    for level in block["levels"]:
                        out["%s %s/%s %s %d" % (pid, key, step["no"], block["id"], level["level"])] = level
    return out


def grade_levels(v, path, bank_dir, index):
    """세 수준 물음 재풀이 답안(ai_seal.py levels 의 levels_answers.json)을 채점함. 답안 키에 나온 노트의 모든 수준 물음을 그 수준의
    answer·mode·places·unit 으로 grade_blank 하고 "세 수준 물음 재풀이: 맞음 a / b" 줄을 찍음. 빈 칸, 글이 아닌 값, 답안에 없는 키는
    틀림. 문항 재풀이(--answers)와 섞지 않음. {"levels", "correct", "wrong"} 를 돌려줌."""
    label = "levels"
    v.head(label, "세 수준 물음 재풀이")
    try:
        answers = study.read_json(path)
    except (OSError, ValueError) as error:
        v.fail(label, 17, "답안을 읽을 수 없습니다: %s" % error)
        return None
    if not isinstance(answers, dict):
        v.fail(label, 17, "답안은 {\"l04 4b/3 v1 7\": \"답\"} 꼴의 JSON 객체여야 합니다.")
        return None
    terms = grade.term_map(aibank.read_terms(bank_dir))
    pages = {p["id"]: p for p in index["pages"]}
    asked = {}
    for pid in sorted({found.group(1) for found in map(LEVELS_KEY.match, answers) if found and found.group(1) in pages}):
        try:
            asked.update(note_levels(pid, aibank.load_note(pages[pid], bank_dir)))
        except aibank.AiBankError as error:
            v.fail(label, 17, str(error))
    for key in sorted(set(answers) - set(asked)):
        v.warn(label, 17, "답안의 %s 가 세 수준 물음에 없습니다." % key)
    correct, wrong = 0, []
    for key, level in sorted(asked.items()):
        value = answers.get(key)
        if key not in answers:
            v.warn(label, 17, "답안에 %s 가 없습니다. ai_seal.py levels 로 답안 파일을 다시 만들고 그 물음을 풉니다." % key)
        elif not isinstance(value, str):
            v.warn(label, 17, "답안의 %s 값이 글이 아닙니다. 숫자도 \"2.4\" 처럼 따옴표로 적습니다." % key)
        elif grade.grade_blank({"answer": level["answer"], "mode": level["mode"], "places": level["places"], "unit": level["unit"]},
                               value, terms):
            correct += 1
            continue
        wrong.append(key)
    v.note(label, "세 수준 물음 재풀이: 맞음 %d / %d%s" % (correct, correct + len(wrong),
                                                       (", 틀림 " + verify_web.listing(wrong, 12)) if wrong else ""))
    for key in wrong:
        v.warn(label, 17, "%s 를 재풀이자가 틀렸습니다. 원인을 하나로 정해 서명 --finding 에 적으세요(그 수준 글만으로 못 풂, 받는 답 빠짐, "
                          "정답 틀림)." % key)
    return {"levels": correct + len(wrong), "correct": correct, "wrong": wrong}


def review_target(folder):
    return os.path.join(folder, webbank.WORK_DIR, "review.json")


def valid_first_pass(value):
    """기존 첫 재풀이의 알려진 필드가 읽을 수 있는 형식인지 봄. 빈 기록과 추가 메타데이터는 그대로 허용함."""
    if not isinstance(value, dict):
        return False
    for key in ('cards', 'correct'):
        if key in value and (type(value[key]) is not int or value[key] < 0):
            return False
    if 'cards' in value and 'correct' in value and value['correct'] > value['cards']:
        return False
    if 'wrong' in value and (not isinstance(value['wrong'], list) or not all(isinstance(cid, str) for cid in value['wrong'])):
        return False
    if 'minutes' in value and (type(value['minutes']) not in (int, float) or not math.isfinite(value['minutes']) or value['minutes'] < 0):
        return False
    if 'gens' in value:
        if not isinstance(value['gens'], dict):
            return False
        if any(key in value['gens'] and (type(value['gens'][key]) is not int or value['gens'][key] < 0) for key in ('checked', 'seeds')):
            return False
    return True


def sign(v, label, folder, secrets, first_pass, files):
    o = v.opts
    names = {"writer": o.writer, "resolver": o.resolver, "checker": o.checker, "reviewer": o.reviewer}
    missing = [key for key, value in names.items() if not (value or "").strip()]
    if missing:
        v.fail(label, 16, "--%s 가 필요합니다." % ", --".join(missing))
        return
    names = {k: x.strip() for k, x in names.items()}
    if names["writer"] in (names["resolver"], names["checker"], names["reviewer"]):
        v.fail(label, 16, "출제자는 재풀이·대조·검토를 겸하지 않습니다(%s)." % names["writer"])
        return
    if names["resolver"] == names["checker"]:
        v.fail(label, 16, "재풀이자와 대조자는 달라야 합니다(%s)." % names["resolver"])
        return
    findings = []
    old = secrets.get("review.json")
    if old:
        try:
            findings = json.loads(old).get("findings", [])
            if not isinstance(findings, list) or not all(isinstance(text, str) for text in findings):
                raise ValueError("findings")
            findings = list(findings)
        except (ValueError, AttributeError, TypeError):
            v.fail(label, 16, "이전 검토 메모를 읽을 수 없어 서명하지 않았습니다.")
            return
    findings += [text for text in (o.finding or []) if text.strip()]
    data = {"format": 1, "id": label}
    data.update(names)
    data.update({"first_pass": first_pass or {}, "files": dict(sorted(files.items())), "findings": findings})
    target = review_target(folder)
    study.write_text(target, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    v.note(label, "서명했습니다: %s (파일 %d개). ai_seal.py seal 로 다시 묶어 커밋하세요." % (study.shown_path(target), len(files)))


class _ReviewSteps(object):
    """verify_web.check_review 의 단계 번호 11(그 도구의 검토 서명)을 이 도구의 16 으로 바꿔 넘김. 11 은 여기서 맥락임."""

    def __init__(self, v):
        self.v = v

    def fail(self, label, step, message):
        self.v.fail(label, 16 if step == 11 else step, message)


def check_signature(v, label, folder, secrets, files):
    text = secrets.get("review.json")
    verify_web.check_review(_ReviewSteps(v), label, text, files)
    if text:
        try:
            data = json.loads(text)
        except ValueError:
            return
        if not str(data.get("checker", "")).strip():
            v.fail(label, 16, "review.json 에 checker(대조자)가 없습니다.")
        elif data.get("checker") in (data.get("writer"), data.get("resolver")):
            v.fail(label, 16, "대조자(%s)가 출제자나 재풀이자와 같습니다." % data.get("checker"))


def signature_step(v, bank_dir, label, folder, lessons=None, patterns=False):
    """--sign·--require-review. 서명 대상 폴더 하나(문항 묶음, common, pc, 모의고사)."""
    o = v.opts
    if not (o.sign or o.require_review):
        return
    if label == "m4":
        try:
            if study.read_json(os.path.join(folder, "meta.json")).get("draft") is not False:
                v.fail(label, 16, "m4는 초안 상태입니다. 최종 검토 뒤 draft를 해제하고 서명하세요.")
                return
        except (OSError, ValueError, AttributeError) as error:
            v.fail(label, 16, "m4 초안 상태를 읽지 못합니다: %s" % error)
            return
    try:
        secrets = webbank.load_secrets(folder)
    except webbank.BankError as error:
        v.fail(label, 16, str(error))
        return
    files = review_files(folder, secrets, bank_dir, patterns)
    if o.sign:
        if v.failed(label):
            v.fail(label, 16, "실패가 있어 서명하지 않았습니다.")
        else:
            if o.keep_first_pass:
                try:
                    first = json.loads(secrets.get("review.json", "{}"))["first_pass"]
                    if not valid_first_pass(first):
                        raise ValueError("first_pass")
                except (ValueError, KeyError, TypeError):
                    v.fail(label, 16, "이전 첫 재풀이 기록을 읽을 수 없어 서명하지 않았습니다.")
                    return
            else:
                first = grade_answers(v, label, o.first_pass, lessons or [], bank_dir, first=True) if o.first_pass else None
            if v.failed(label):
                v.fail(label, 16, "첫 재풀이를 읽지 못해 서명하지 않았습니다.")
                return
            if first is not None and o.minutes:
                first["minutes"] = o.minutes
            sign(v, label, folder, secrets, first, files)
            secrets = webbank.load_secrets(folder)
    if o.require_review:
        check_signature(v, label, folder, secrets, files)


# 출제자용 모아 보기

def records(subs_dir):
    """submissions/*/ai/record.json 의 [(ID, log)]."""
    out = []
    for user in sorted(os.listdir(subs_dir)) if os.path.isdir(subs_dir) else []:
        path = os.path.join(subs_dir, user, "ai", "record.json")
        if os.path.isfile(path):
            try:
                out.append((user, study.read_json(path).get("log") or []))
            except (OSError, ValueError, AttributeError):
                continue
    return out


def show_overrides(v):
    """[내 답도 맞음] 답을 문항별로. 뼈대 빈칸에서 함께 가린 칸을 바꾼 답(also_value)은 그 자리 카드 id 로 모음."""
    found = {}
    for user, log in records(study.SUBMISSIONS_DIR):
        for entry in log:
            if entry.get("kind") == "override" and entry.get("card"):
                if entry.get("value"):
                    found.setdefault(entry["card"], []).append((user, " / ".join(str(x) for x in entry["value"])))
                for slot, text in sorted((entry.get("also_value") or {}).items()):
                    found.setdefault(str(slot), []).append((user, str(text)))
    v.say("[내 답도 맞음] 답 %d개 문항" % len(found))
    for cid, rows in sorted(found.items()):
        v.say("  %s: %s" % (cid, "; ".join("%s(%s)" % (value, user) for user, value in rows)))


def card_units(bank_dir, index):
    """{카드 id: (차시 id, 단원)}. 봉인을 풀지 않고 읽을 수 있는 출제된 차시만."""
    out = {}
    for entry in index["lessons"]:
        if not aibank.is_ready(entry, bank_dir):
            continue
        try:
            data = aibank.load_items(entry, bank_dir)
        except aibank.AiBankError:
            continue
        for card in aibank.cards_of(entry, data):
            out[card["id"]] = (card["lesson"], card["unit"])
    for group in index["patterns"]:
        if not aibank.pattern_ready(group, bank_dir):
            continue
        try:
            cards = ai_seal.pattern_cards(bank_dir, group)[1]
            data = aibank.load_items({"id": group["id"]}, bank_dir)
            note = aibank.load_note({"id": group["page"], "title": group["title"]}, bank_dir)
            units = {key: info for key, info in group["units"].items() if key in note["visible"]}
            cards.extend(aibank.pattern_gen_cards(group, data, units))
            for card in cards:
                out[card["id"]] = (card["lesson"], card["unit"])
        except (aibank.AiBankError, KeyError, TypeError, ValueError):
            continue
    return out


def show_leeches(v, exam, units):
    """자주 틀리는 문항. units 는 card_units 결과이고 읽은 날은 그 카드의 단원 것을 씀(앱의 오답 규칙과 같음)."""
    found = {}
    for user, log in records(study.SUBMISSIONS_DIR):
        events = review.card_events(log)
        reads = review.read_days(log)
        for cid, rows in events.items():
            read_day = reads.get(units[cid]) if cid in units else None
            schedule = review.card_schedule(rows, read_day, exam, rows[-1]["day"], cid)
            if review.leech(schedule):
                found.setdefault(cid, []).append(user)
    v.say("자주 틀리는 문항 %d개" % len(found))
    for cid, users in sorted(found.items(), key=lambda pair: -len(pair[1])):
        v.say("  %s: %d명 (%s)" % (cid, len(users), ", ".join(users)))


def check_sources(v, lessons, lecture_dir):
    for les in lessons:
        for rel, digest in sorted((les.data.get("sources") or {}).items()):
            path = os.path.join(lecture_dir, *rel.split("/"))
            if not os.path.isfile(path):
                v.fail(les.id, 18, "강의 파일이 없습니다: %s" % rel)
            elif verify_web.file_sha(path) != digest:
                v.fail(les.id, 18, "강의 파일이 사실 확인 때와 다릅니다: %s. 이 파일을 근거로 쓴 사실을 다시 확인하세요." % rel)


# 명령줄

def parse_args(argv):
    parser = argparse.ArgumentParser(prog="verify_ai.py", description="AI 비전 개론 문항 묶음 검증")
    parser.add_argument("targets", nargs="*", help="차시 id(i05), common, 모의고사 id(m1). 없으면 출제된 것 전부")
    parser.add_argument("--bank", default=aibank.AI_DIR)
    parser.add_argument("--manifest", default=ai_art.MANIFEST)
    parser.add_argument("--seeds", type=int, default=300)
    parser.add_argument("--answers")
    parser.add_argument("--levels-answers", dest="levels_answers")
    parser.add_argument("--sign", action="store_true")
    parser.add_argument("--writer")
    parser.add_argument("--resolver")
    parser.add_argument("--checker")
    parser.add_argument("--reviewer")
    first_pass = parser.add_mutually_exclusive_group()
    first_pass.add_argument("--first-pass", dest="first_pass")
    first_pass.add_argument("--keep-first-pass", action="store_true", help="이전 서명의 첫 재풀이 기록을 보존합니다")
    parser.add_argument("--minutes", type=int)
    parser.add_argument("--finding", action="append")
    parser.add_argument("--require-review", action="store_true")
    parser.add_argument("--overrides", action="store_true")
    parser.add_argument("--leeches", action="store_true")
    parser.add_argument("--sources")
    opts = parser.parse_args(argv)
    if opts.keep_first_pass and not opts.sign:
        parser.error("--keep-first-pass 는 --sign 과 함께 씁니다.")
    if opts.keep_first_pass and opts.minutes is not None:
        parser.error("--keep-first-pass 는 기록한 시간을 보존하므로 --minutes 와 함께 쓰지 않습니다.")
    return opts


def main(argv=None, out=None):
    opts = parse_args(sys.argv[1:] if argv is None else argv)
    v = Verifier(opts, out)
    bank_dir = os.path.abspath(opts.bank)
    index = check_index(v, bank_dir)
    if index is None:
        return 1
    if opts.overrides or opts.leeches:
        if opts.overrides:
            show_overrides(v)
        if opts.leeches:
            show_leeches(v, review.exam_dates(index["exam"]), card_units(bank_dir, index))
        return 0
    if opts.levels_answers:  # 학습 노트 블록만 보는 채점이라 문항 묶음 검사를 돌리지 않음
        grade_levels(v, os.path.abspath(opts.levels_answers), bank_dir, index)
        v.say("실패 %d개, 경고 %d개" % (len(v.failures), len(v.warnings)))
        return 1 if v.failures else 0
    try:
        terms = aibank.read_terms(bank_dir)
        retired = aibank.read_retired(bank_dir)
    except aibank.AiBankError as error:
        v.fail("index", 1, str(error))
        return 1
    try:
        aibank.load_common(bank_dir)
    except aibank.AiBankError as error:
        v.fail("common", 6, str(error))
    skeletons, skeleton_error = {}, None
    try:
        skeletons = skel.load_patterns(bank_dir)
    except aibank.AiBankError as error:
        skeleton_error = str(error)
    pages_no = {p["id"]: int(aibank.PAGE_ID.fullmatch(p["id"]).group(1)) for p in index["pages"] if aibank.PAGE_ID.fullmatch(p["id"])}
    entries = [e for e in index["lessons"] if os.path.isfile(os.path.join(aibank.items_dir(e["id"], bank_dir), "meta.json"))]
    mocks = [m for m in index["mocks"] if os.path.isfile(os.path.join(aibank.mock_dir(m["id"], bank_dir), "meta.json"))]
    common = os.path.join(bank_dir, "items", "common")
    has_common = os.path.isfile(os.path.join(common, "gens.py"))
    patterns = os.path.join(bank_dir, "items", "pc")
    has_pc = os.path.isfile(os.path.join(patterns, "meta.json"))
    known = {e["id"] for e in entries} | {m["id"] for m in mocks} | ({"common"} if has_common else set()) | ({"pc"} if has_pc else set())
    if opts.targets:
        missing = [t for t in opts.targets if t not in known]
        if missing:
            v.say("출제된 문항 묶음·모의고사가 아닙니다: %s" % ", ".join(missing))
            return 2
        entries = [e for e in entries if e["id"] in opts.targets]
        mocks = [m for m in mocks if m["id"] in opts.targets]
        has_common = has_common and "common" in opts.targets
        has_pc = has_pc and "pc" in opts.targets
    else:
        intro_definitions(v, bank_dir, terms, index)
        check_figures(v, bank_dir, index, opts.manifest)
        check_secrets(v, bank_dir)
    ids = {}
    lessons = []
    for entry in entries:
        les = load_lesson(v, bank_dir, entry)
        if les is None:
            continue
        les.skeletons = skeletons
        lessons.append(les)
        check_lesson(v, bank_dir, les, ids, retired, terms, pages_no, opts.seeds)
        signature_step(v, bank_dir, les.id, les.data["dir"], [les])
    if has_common:
        v.head("common", "공용 생성기")
        check_imports(v, "common", common)
        signature_step(v, bank_dir, "common", common)
    if has_pc:  # 상황별 코드 뼈대 카드. 서명이 ai/patterns/*.json 을 같이 덮음
        v.head("pc", "상황별 코드")
        group = next((g for g in index["patterns"] if g["id"] == "pc"), None)
        les = None
        if skeleton_error:
            v.fail("pc", 19, skeleton_error)
        elif group is None:
            v.fail("pc", 1, "index.json patterns 에 pc 가 없습니다.")
        else:
            les = load_pattern_group(v, bank_dir, group, skeletons)
        if les is not None:
            lessons.append(les)
            check_lesson(v, bank_dir, les, ids, retired, terms, pages_no, opts.seeds)
            check_skeletons(v, les, opts.seeds)
        signature_step(v, bank_dir, "pc", patterns, [les] if les else [], patterns=True)
    mock_sources = _MockSources(bank_dir, index, opts.seeds, skeletons) if mocks else None
    mock_lessons = []
    for mock in mocks:
        les = check_mock(v, bank_dir, mock, ids, mock_sources)
        if les is not None:
            mock_lessons.append(les)
        signature_step(v, bank_dir, mock["id"], aibank.mock_dir(mock["id"], bank_dir), [les] if les else [])
    if opts.answers and not opts.sign:
        grade_answers(v, "answers", opts.answers, lessons + mock_lessons, bank_dir)
    if opts.sources:
        check_sources(v, lessons, os.path.abspath(os.path.expanduser(opts.sources)))
    count = sum(1 for les in lessons if les.group is None) + len(mocks) + int(has_common) + int(has_pc)
    if v.failures:
        v.say("실패 %d개, 경고 %d개 (묶음 %d개)" % (len(v.failures), len(v.warnings), count))
        return 1
    v.say("OK: 묶음 %d개 통과, 경고 %d개" % (count, len(v.warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
