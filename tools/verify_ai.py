#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 비전 개론 문항 묶음·학습 노트 블록·그림·서명 검증(설계 4.6, 8.7). 실패가 하나라도 있으면 1 로 끝남.

  python tools/verify_ai.py [i05 common ...]           출제된 문항 묶음 전부(또는 적은 것)를 봄
  python tools/verify_ai.py i05 --seeds 50             생성기를 50 시드만 돌림(기본 300)
  python tools/verify_ai.py i05 --answers FILE         재풀이 답안(ai_seal.py brief 가 만든 answers.json)을 채점함
  python tools/verify_ai.py i05 --sign --writer "출제 1" --resolver "재풀이 2" --checker "대조 3" --reviewer "검토 4"
                            [--first-pass FILE] [--finding 글 ...]
                                                       검증을 통과하면 work/review.json 을 씀(그 뒤 ai_seal.py seal)
  python tools/verify_ai.py --require-review           문항 묶음·공용 생성기·모의고사 서명이 없거나 서명 뒤 바뀐 파일이 있으면 실패
  python tools/verify_ai.py --overrides | --leeches    submissions 기록에서 [내 답도 맞음] 답과 자주 틀리는 문항을 모아 보임
  python tools/verify_ai.py --sources DIR              강의 폴더의 sha256 을 facts.json sources 와 견줌(출제자 컴퓨터에서만)

그 밖의 옵션: --bank DIR(기본 ai/), --manifest FILE(기본 tools/ai_art/manifest.json). 학습 노트의 글 꼴·말투·맥락과 서명은
verify_web.py --bank ai 와 web_lint.py --bank ai 가 보고, 여기서는 ai-* 블록·프레임 줄·단계 사실 줄·그림 한도와 manifest 를 봄.
검사 번호와 이름은 STEP_NAMES 에 있음. 표준 라이브러리만 씀.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import bank as aibank  # noqa: E402
from aiprep import gen as genlib  # noqa: E402
from aiprep import grade, review  # noqa: E402
from tools import ai_art, ai_seal, check_style, verify_web, web_lint  # noqa: E402
from webprep import bank as webbank  # noqa: E402

STEP_NAMES = {1: "목록", 2: "문항 꼴", 3: "빈칸 규칙", 4: "고르기", 5: "문장", 6: "생성기", 7: "사실 확인", 8: "노트 블록", 9: "근거",
              10: "말투", 11: "맥락", 12: "모의고사", 13: "그림", 14: "한도", 15: "비밀 값", 16: "검토 서명", 17: "재풀이 대조",
              18: "강의 파일"}
VERDICTS = ("맞음", "단순화", "부분적으로 맞음", "버전 차이", "틀림", "확인 못 함")
BAD_VERDICTS = ("틀림", "확인 못 함")
ASK_AS = ("단순화", "부분적으로 맞음")
VALUE_MODES = ("number", "exact", "values")
LONG_API = ("register_full_backward_hook", "ReduceLROnPlateau", "CosineAnnealingLR", "DataCollatorWithPadding")
PARTICLE_TRAP = re.compile(r"_{4,}\s?(을|를|은|는|이|가|과|와)(?=[\s.,?!)]|$)")
POINTING = re.compile(r"^(모두|위의)|[①-④]|위 보기|보기\s*\d")
REF_FORMS = (
    ("lecture", re.compile(r"(\d{1,2})차시 슬 p\d+(?:~p?\d+)?\Z")),
    ("lecture", re.compile(r"(\d{1,2})차시 노트북 \d{2} \[\d+\]\Z")),
    ("lecture", re.compile(r"(\d{1,2})차시 과제 \d+번\Z")),
    ("lecture", re.compile(r"(\d{1,2})차시 강의노트 \[\d+\]\Z")),
    ("summary", re.compile(r"요약 (\d)주차 p\d+(?:~p?\d+)?\Z")),
    ("graduate", re.compile(r"대학원 \d{2} p\d+(?:~p?\d+)?\Z")),
    ("official", re.compile(r"공식 (\d{1,2})차시\Z")),
    ("doc", re.compile(r"(?:\S+ )?문서 \S.*\Z")),
)
DEEP_MAX = {"i13": 5, "i14": 5, "i16": 5}
DEEP_DEFAULT = 3
ALLOWED_LICENSES = ("CC0", "PD", "Public Domain", "퍼블릭 도메인", "CC BY 4.0", "CC BY-SA 4.0", "MIT", "BSD-3-Clause")
SECRET = re.compile(r"sk-[A-Za-z0-9]{8,}|hf_[A-Za-z0-9]{8,}|api_key\s*=|KAGGLE_KEY|(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])")
IMPORT_BAD = re.compile(r"^\s*(?:import|from)\s+(numpy|torch)\b", re.M)
TEXT_EXT = (".py", ".json", ".md", ".txt")
GEN_MS = 50.0
MIN_STEMS = 20
FULL_SEEDS = 100  # 서로 다른 지문 수는 시드를 이만큼 이상 돌릴 때만 봄
STYLE_SAMPLES = 20
IMAGE_REF = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")


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
        if lid in seen_ids or lesson["no"] in seen_no:
            v.fail("index", 1, "lessons 에 같은 id 나 no 가 두 번 있습니다: %s" % lid)
        seen_ids.add(lid)
        seen_no.add(lesson["no"])
        if lesson["no"] != lesson_no(lid):
            v.fail("index", 1, "%s 의 no 가 id 와 다릅니다: %d" % (lid, lesson["no"]))
        if lesson["page"] not in pages:
            v.fail("index", 1, "%s 의 page %s 가 pages 에 없습니다." % (lid, lesson["page"]))
        elif lesson["page"] != "l%02d" % lesson["no"]:
            v.fail("index", 1, "%s 의 page 는 l%02d 여야 합니다: %s" % (lid, lesson["no"], lesson["page"]))
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
    nos = sorted(seen_no)
    for mock in index["mocks"]:
        if len(mock["range"]) != 2 or mock["range"][0] > mock["range"][1] or (nos and not (nos[0] <= mock["range"][0]
                                                                                            and mock["range"][1] <= nos[-1])):
            v.fail("index", 1, "%s 의 range 가 차시 범위가 아닙니다: %s" % (mock["id"], mock["range"]))
        days = [review.parse_day(d) for d in mock["window"]]
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


def ref_kind(ref):
    for kind, pattern in REF_FORMS:
        found = pattern.match(ref)
        if found:
            return kind, found.group(1) if pattern.groups else None
    return None, None


def first_ref_ok(ref, no):
    kind, value = ref_kind(ref)
    if kind == "lecture":
        return int(value) == no
    if kind == "summary":
        week = int(value)
        return (week - 1) * 5 < no <= week * 5
    return False


def card_texts(card):
    """카드에서 학습자에게 보이는 글 [(어디, 글, 마크다운인지)]."""
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
    """바꿔 쓴 판(alt)은 stem·explain 만 바꾸고 빈칸 수가 같아야 함."""
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
    if not first_ref_ok(refs[0], lesson_no(les.id)):
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
                want = fn(made.get("params") or {})
                want = sorted(want if isinstance(want, list) else [want])
                got = sorted(made["options"][n]["text"] for n in grade.right_options(made))
                if [str(w) for w in want] != got:
                    problems.append("시드 %d: oracle %s 와 생성기 %s 가 다릅니다" % (seed, want, got))
                    break
        if len(stems) > styled and styled < STYLE_SAMPLES:
            styled = len(stems)
            v.style(label, "%s 시드 %d stem" % (cid, seed), made.get("stem", ""), markdown=True)
            v.style(label, "%s 시드 %d explain" % (cid, seed), made.get("explain", ""), markdown=True)
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
    for card in les.cards:
        row = actual.setdefault(card["unit"], {"blank": 0, "choice": 0, "stmt": 0, "gen": [], "core": 0})
        if card["kind"] == "gen":
            row["gen"].append(card["id"])
        else:
            row[card["kind"]] += 1
        row["core"] += int(card["core"])
    for key in sorted(set(meta_units) | set(actual)):
        want = meta_units.get(key)
        got = actual.get(key, {"blank": 0, "choice": 0, "stmt": 0, "gen": [], "core": 0})
        if want is None:
            v.fail(label, 2, "items meta.json units 에 %s 단원이 없습니다." % key)
        else:
            for name in ("blank", "choice", "stmt", "core"):
                if int(want.get(name, 0)) != got[name]:
                    v.fail(label, 2, "meta.json 의 %s %s 수 %s 가 봉인 안 수 %d 와 다릅니다." % (key, name, want.get(name, 0), got[name]))
            if sorted(want.get("gen") or []) != sorted(got["gen"]):
                v.fail(label, 2, "meta.json 의 %s gen 목록이 gens.py 와 다릅니다." % key)
        if key in actual and not 3 <= got["core"] <= 4:
            v.fail(label, 2, "%s 단원의 핵심 문항이 %d개입니다(3~4개)." % (key, got["core"]))


def check_note_blocks(v, les):
    """학습 노트의 ai-* 블록, 단계 수, 단계 사실 줄, 프레임 줄."""
    label = les.id
    note = les.note
    if note is None:
        return
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
        guesses = {}
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
                if kind in ("guess", "recall"):
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
        missing = sorted(cid for cid, card in mine.items() if card["core"] and cid not in covered)
        if missing:
            v.fail(label, 8, "%s 의 외울 것이 핵심 카드를 덮지 않습니다: %s" % (where, verify_web.listing(missing)))
        meta = note["unit_meta"].get(key, {})
        if meta.get("key_figure") and not os.path.isfile(os.path.join(note["dir"], *str(meta["key_figure"]).split("/"))):
            v.warn(label, 13, "%s 의 key_figure 파일이 아직 없습니다: %s" % (where, meta["key_figure"]))


def check_context(v, les, terms, pages_no):
    """문항 글의 terms 낱말이 이 차시까지 소개됐는지(page·intro 차시가 이 차시보다 뒤면 실패)."""
    label, no = les.id, lesson_no(les.id)
    forms = []
    for term in terms["terms"]:
        first = [pages_no.get(p) for p in (term.get("intro"), term.get("page")) if pages_no.get(p) is not None]
        if first:
            for form in [term["term"]] + term["also"]:
                forms.append((form, term["term"], min(first)))
    forms.sort(key=lambda f: -len(f[0]))
    for card in les.cards:
        for where, text, _ in card_texts(card):
            plain = re.sub(r"```.*?```", "", str(text), flags=re.S)
            for form, term, at in forms:
                if form in plain and at > no:
                    v.fail(label, 11, "%s 에 %d차시에서 소개하는 낱말 '%s'가 나옵니다." % (where, at, term))
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


def git_ids(bank_dir, lid):
    """직전 커밋(HEAD)의 그 차시 카드·문장 id. git 이 없거나 그 커밋에 없으면 None."""
    folder = aibank.items_dir(lid, bank_dir)
    here = os.path.abspath(bank_dir)
    while not os.path.exists(os.path.join(here, ".git")):  # git 저장소 밖(임시 사본)이면 git 을 부르지 않음
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=bank_dir, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    except OSError:
        return None
    if top.returncode != 0:
        return None
    root = top.stdout.strip()
    rel = os.path.relpath(os.path.realpath(folder), os.path.realpath(root)).replace(os.sep, "/")
    ids = set()
    shown = subprocess.run(["git", "show", "HEAD:%s/sealed.json" % rel], cwd=root, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if shown.returncode != 0:
        return None
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
    return ids


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


def check_lesson(v, bank_dir, les, ids, retired, terms, pages_no, seeds):
    label = les.id
    v.head(label, "%d차시 %s" % (les.entry["no"], les.entry["title"]))
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
    check_note_blocks(v, les)
    check_context(v, les, terms, pages_no)
    before = git_ids(bank_dir, les.id)
    if before is not None:
        now_ids = {c["id"] for c in les.cards}
        gone = sorted(before - now_ids - retired)
        if gone:
            v.fail(label, 2, "직전 커밋에 있던 id 가 retired.json 없이 사라졌습니다: %s" % verify_web.listing(gone))
    for card in les.cards:
        for where, text, _ in card_texts(card):
            for ref in IMAGE_REF.findall(str(text)):
                if not ref.startswith(("assets/", "../")):
                    v.fail(label, 13, "%s 의 그림 %s 은 직접 그린 그림이어야 합니다." % (where, ref))


# 12. 모의고사

def check_mock(v, bank_dir, mock, ids):
    """모의고사 묶음의 꼴(문항 수, 꼴, 칸 수, errata 없음, deep 2 이하). 회차 청사진·자카드는 PR5 에서 더함."""
    label = mock["id"]
    folder = aibank.mock_dir(mock["id"], bank_dir)
    v.head(label, mock["title"])
    try:
        secrets = webbank.load_secrets(folder)
        items = json.loads(secrets.get("items.json", '{"items": []}')).get("items") or []
    except (webbank.BankError, ValueError) as error:
        v.fail(label, 12, "items.json 을 읽을 수 없습니다: %s" % error)
        return
    if len(items) != mock["count"]:
        v.fail(label, 12, "문항이 %d개입니다(%d개)." % (len(items), mock["count"]))
    deep = 0
    for item in items:
        mid = str(item.get("id"))
        if mid in ids:
            v.fail(label, 12, "id 가 두 번 쓰였습니다: %s" % mid)
        ids[mid] = label
        if item.get("kind") not in ("blank", "choice"):
            v.fail(label, 12, "%s 는 빈칸이나 고르기여야 합니다." % mid)
        if item.get("errata"):
            v.fail(label, 12, "%s 는 정정 주제(errata)라 모의고사에 넣지 않습니다." % mid)
        if len(item.get("blanks") or []) > 2:
            v.fail(label, 12, "%s 에 빈칸이 셋 넘게 있습니다(문항마다 1~2칸)." % mid)
        if item.get("kind") == "choice" and item.get("multi") and len(grade.right_options(item)) != 2:
            v.fail(label, 12, "%s 는 모두 고르기인데 답이 2개가 아닙니다." % mid)
        deep += bool(item.get("deep"))
    if deep > 2:
        v.fail(label, 12, "deep 문항이 %d개입니다(2개 이하)." % deep)


# 13~15. 그림, 한도, 비밀 값

def check_figures(v, bank_dir, index, manifest):
    data = ai_art.read_manifest(manifest)
    total = 0
    for page in index["pages"]:
        pdir = aibank.page_dir(page["id"], bank_dir)
        if not os.path.isfile(os.path.join(pdir, "page.md")):
            continue
        label = page["id"]
        try:
            meta = study.read_json(os.path.join(pdir, "meta.json"))
        except (OSError, ValueError):
            continue
        credits = {str(c.get("file")): c for c in meta.get("credits") or [] if isinstance(c, dict)}
        parsed = aibank.parse_page(study.read_text(os.path.join(pdir, "page.md")), meta.get("sections") or {}, pdir)
        blocks = [b for key in parsed["order"] for s in parsed["units"][key]["steps"] for b in s["blocks"] if b["kind"] == "figure"]
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
            if entry is not None:
                if entry.get("sha256") != ai_art.file_sha(path):
                    v.fail(label, 13, "%s 가 manifest 의 해시와 다릅니다. 다시 그렸으면 `python -m tools.ai_art %s --record` 로 적으세요."
                           % (block["file"], page["id"]))
                continue
            credit = credits.get(block["file"])
            if credit is None:
                v.fail(label, 13, "manifest 에 없는 그림입니다: %s. 직접 그린 그림은 manifest 에 적고, 가져온 그림은 meta.json credits 에 "
                                  "출처를 적습니다." % block["file"])
            elif credit.get("license") not in ALLOWED_LICENSES or not credit.get("author") or not credit.get("url"):
                v.fail(label, 13, "%s 의 credits 는 author·url 과 허용 라이선스(%s)가 있어야 합니다." % (block["file"], ", ".join(ALLOWED_LICENSES)))
            elif "출처" not in block["caption"] and not any(h == "그림 출처" for h, _ in parsed["extra"]):
                v.fail(label, 13, "%s 는 가져온 그림인데 캡션이나 「그림 출처」 절에 출처가 없습니다." % block["file"])
        assets = os.path.join(pdir, "assets")
        size = sum(os.path.getsize(os.path.join(assets, f)) for f in os.listdir(assets)) if os.path.isdir(assets) else 0
        if size > ai_art.LIMITS["note_bytes"]:
            v.fail(label, 14, "그림 합계가 %.1fMB 입니다(학습 노트 하나 %.1fMB 이하)." % (size / 1048576.0, ai_art.LIMITS["note_bytes"] / 1048576.0))
        total += size
    if total > ai_art.LIMITS["total_bytes"]:
        v.fail("index", 14, "그림 합계가 %.1fMB 입니다(%dMB 이하)." % (total / 1048576.0, ai_art.LIMITS["total_bytes"] // 1048576))
    elif total > ai_art.LIMITS["warn_bytes"]:
        v.warn("index", 14, "그림 합계가 %.1fMB 입니다. 비중이 낮은 차시의 GIF 를 PNG 로 바꾸세요." % (total / 1048576.0))


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


def grade_answers(v, label, path, lessons, bank_dir):
    """재풀이 답안을 채점함. {"cards", "correct", "wrong", "gens": {"checked", "seeds"}} 를 돌려주고 틀린 카드를 보여 줌.
    문장 칸은 공개본 꼬리표(<주제 id>-<번호>)를 ai_seal.statement_rows 로 문장 id 로 되돌림. 빈칸판이 있는 문장은 ok 와 cloze 가
    둘 다 맞아야 맞음이고, 빈칸판이 없는 문장의 cloze 는 보지 않음. 고르기 칸에 order 가 없으면 ai_seal.option_order 로 공개본의
    보기 순서를 다시 만듦. 예전 꼴(문장 id 를 키로 쓴 답안, order 를 적은 고르기)도 그대로 채점함."""
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


def review_target(folder):
    return os.path.join(folder, webbank.WORK_DIR, "review.json")


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
            findings = list(json.loads(old).get("findings") or [])
        except (ValueError, AttributeError):
            findings = []
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
            first = grade_answers(v, label, o.first_pass, lessons or [], bank_dir) if o.first_pass else None
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
    found = {}
    for user, log in records(study.SUBMISSIONS_DIR):
        for entry in log:
            if entry.get("kind") == "override" and entry.get("card"):
                found.setdefault(entry["card"], []).append((user, " / ".join(str(x) for x in entry.get("value") or [])))
    v.say("[내 답도 맞음] 답 %d개 문항" % len(found))
    for cid, rows in sorted(found.items()):
        v.say("  %s: %s" % (cid, "; ".join("%s(%s)" % (value, user) for user, value in rows)))


def show_leeches(v, exam):
    found = {}
    for user, log in records(study.SUBMISSIONS_DIR):
        events = review.card_events(log)
        reads = review.read_days(log)
        for cid, rows in events.items():
            lesson = "i%s" % cid[1:3] if cid.startswith("i") else None
            read_day = next((day for (lid, _), day in reads.items() if lid == lesson), None)
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
    parser.add_argument("--sign", action="store_true")
    parser.add_argument("--writer")
    parser.add_argument("--resolver")
    parser.add_argument("--checker")
    parser.add_argument("--reviewer")
    parser.add_argument("--first-pass", dest="first_pass")
    parser.add_argument("--minutes", type=int)
    parser.add_argument("--finding", action="append")
    parser.add_argument("--require-review", action="store_true")
    parser.add_argument("--overrides", action="store_true")
    parser.add_argument("--leeches", action="store_true")
    parser.add_argument("--sources")
    return parser.parse_args(argv)


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
            show_leeches(v, review.exam_dates(index["exam"]))
        return 0
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
    pages_no = {p["id"]: int(p["id"][1:]) for p in index["pages"] if aibank.PAGE_ID.match(p["id"])}
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
        lessons.append(les)
        check_lesson(v, bank_dir, les, ids, retired, terms, pages_no, opts.seeds)
        signature_step(v, bank_dir, les.id, les.data["dir"], [les])
    if has_common:
        v.head("common", "공용 생성기")
        check_imports(v, "common", common)
        signature_step(v, bank_dir, "common", common)
    if has_pc:  # 상황별 코드 카드(뼈대 카드는 PR2). 서명이 ai/patterns/*.json 을 같이 덮음
        v.head("pc", "상황별 코드")
        signature_step(v, bank_dir, "pc", patterns, patterns=True)
    for mock in mocks:
        check_mock(v, bank_dir, mock, ids)
        signature_step(v, bank_dir, mock["id"], aibank.mock_dir(mock["id"], bank_dir))
    if opts.answers and not opts.sign:
        grade_answers(v, "answers", opts.answers, lessons, bank_dir)
    if opts.sources:
        check_sources(v, lessons, os.path.abspath(os.path.expanduser(opts.sources)))
    count = len(lessons) + len(mocks) + int(has_common) + int(has_pc)
    if v.failures:
        v.say("실패 %d개, 경고 %d개 (묶음 %d개)" % (len(v.failures), len(v.warnings), count))
        return 1
    v.say("OK: 묶음 %d개 통과, 경고 %d개" % (count, len(v.warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
