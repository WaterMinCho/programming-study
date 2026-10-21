#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 면접 준비 글의 말투와 맥락 검사(설계 6.2, 6.3). 오류가 하나라도 있으면 1 로 끝남.

  python tools/web_lint.py                      출제된 미션·주제·페이지 전부
  python tools/web_lint.py w03 t03 l03          적은 것만
  python tools/web_lint.py w03 --checker PATH   바깥 말투 검사기(check_doc_tone.py)의 위치를 직접 줌

말투: 학습자에게 보이는 글(brief.md, steps.md, explain.md, followups.md, check.md, chains.md, page.md, meta 의 title·goal·절
제목, 검사 이름, figure 캡션, 표 칸, 그림 대체 글)을 저장소의 tools/check_style.py 로 보고, STUDY_TONE_CHECKER 환경 변수나
저장소 옆 ../_tools/check_doc_tone.py 가 있으면 그 검사기로도 봄. 두 검사기가 같은 곳을 잡으면 한 번만 적음.

맥락: web/terms.json 의 낱말이 알아도 되는 낱말(known, needs 페이지가 정의한 것, 그 글의 defines·defines_inline, 같은 미션의
앞 글이 정의한 것)이 아닌 채로 나오면 오류. 그 글이 정의하는 낱말은 처음 나오는 문장이 정의 꼴("…를 X라고 합니다", "X라는")이어야
하고 아니면 경고, 뒤에서야 정의하면 오류. 코드 블록, 인라인 코드, 제목, 면접관 말은 보지 않음.

그 밖의 규칙: 영어 낱말·인라인 코드 뒤에 띄어 쓴 조사("React 가"), 가리키는 것이 없는 "위 코드"·"아래 그림", 반말 질문 제목,
brief.md 에 새어 나간 단계 요구(단계 제목, 요구, 검사, 힌트와 %d글자 넘게 겹침), 가짜 정의("이것을 X라고 합니다"), 절 끝의 외딴
짧은 문단, "예상해 보세요" 바로 뒤에 붙은 답. 뒤의 셋은 사람이 보고 넘기는 경고임.
"""
import argparse
import difflib
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from tools import check_style  # noqa: E402
from webprep import bank  # noqa: E402

EXTERNAL_ENV = "STUDY_TONE_CHECKER"
EXTERNAL_DEFAULT = os.path.join(os.path.dirname(ROOT), "_tools", "check_doc_tone.py")
MISSION_TEXTS = ("brief.md", "steps.md", "explain.md", "followups.md", "check.md")  # 맥락 검사 순서
CODE_MARK = "ⓒ"  # 인라인 코드 자리. 영어 낱말처럼 뒤의 조사를 봄
PARTICLES = ("가|이|을|를|은|는|의|에|로|와|과|도|만|에서|으로|이라고|라고|라는|이라는|에게|처럼|부터|까지|보다|에는|에서는|로는|"
             "으로는|와는|과는|이란|란")
SPACED = re.compile(r"(?<=[A-Za-z%s)\]])\s+(%s)(?=[\s,.?!)]|$)" % (CODE_MARK, PARTICLES))
POINTING = re.compile(r"(위|아래)의?\s?(코드|그림|표|명령)")
POINT_KINDS = {"코드": ("code",), "명령": ("code",), "그림": ("figure", "alt"), "표": ("table",)}
PREDICT = re.compile(r"(예상해|적어|맞혀)\s?보세요")
ANSWERED = re.compile(r"(찍힙니다|나옵니다|됩니다|보입니다|남습니다|입니다)\.")
QUESTION_OK = re.compile(r"(요|니까)\s*\?\s*\Z")
INFORMAL = re.compile(r"(^|\s)(뭐|뭘|뭔|어떡|왜냐면)|(거야|거지|했어|할까|일까|그럴까|하지|하냐|할래)\s*[?.]?\s*\Z")
PSEUDO_SUBJECT = re.compile(r"^(이것|그것|이|그|이런 것|그런 것|이러한 것|이걸|그걸|이를|그걸)[을를은는이가]?$")
SENTENCE_END = re.compile(r"(?<=[.?!])\s+")
INLINE_CODE = re.compile(r"`[^`\n]*`")
LEAK_MIN = 12
SHORT_CLOSE = 30
LEVEL_NAMES = {"error": "오류", "warn": "경고"}


# 글 모양 읽기

class Unit:
    """글의 한 덩이. kind 는 heading, para, list, quote, caption, cell, alt, code, figure, table 가운데 하나."""

    def __init__(self, kind, text, line, level=0, interviewer=False):
        self.kind, self.text, self.line, self.level, self.interviewer = kind, text, line, level, interviewer

    @property
    def prose(self):
        """맥락과 그 밖의 규칙이 보는 글인지. 제목과 면접관 말, 코드는 아님."""
        return self.kind in ("para", "list", "quote", "caption", "cell", "alt") and not self.interviewer


def units_of(markdown):
    """마크다운을 Unit 목록으로. 문단은 이어진 줄을 합치고, 목록 항목과 인용 줄은 하나씩 둠."""
    out, para, fence, figure = [], None, False, False
    for no, raw in enumerate(markdown.replace("\r\n", "\n").split("\n"), 1):
        line = raw.rstrip()
        stripped = line.strip()
        if re.match(r"^(```|~~~)", stripped):
            if fence:
                fence = figure = False
            else:
                fence = True
                figure = stripped.lstrip("`~").strip() == "figure"
                out.append(Unit("figure" if figure else "code", "", no))
            para = None
            continue
        if fence:
            if figure and stripped.startswith("캡션:"):
                out.append(Unit("caption", stripped[len("캡션:"):].strip(), no))
            continue
        if not stripped or stripped.startswith("<!--"):
            para = None
            continue
        found = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", stripped)
        if found:
            out.append(Unit("heading", found.group(2), no, len(found.group(1))))
            para = None
            continue
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
                out.append(Unit("table", "", no))
                out.extend(Unit("cell", c, no) for c in cells if c)
            para = None
            continue
        found = re.match(r"^!\[([^\]]*)\]\(", stripped)
        if found:
            out.append(Unit("alt", found.group(1), no))
            para = None
            continue
        if stripped.startswith(">"):
            text = stripped.lstrip("> ").strip()
            out.append(Unit("quote", text, no, interviewer=text.startswith("면접관:")))
            para = None
            continue
        if re.match(r"^([-*+]|\d+\.)\s+", stripped):
            out.append(Unit("list", re.sub(r"^([-*+]|\d+\.)\s+", "", stripped), no))
            para = None
            continue
        if para is None:
            para = Unit("para", stripped, no)
            out.append(para)
        else:
            para.text += " " + stripped
    return out


def plain(text):
    """인라인 코드를 CODE_MARK 로 바꾼 글."""
    return INLINE_CODE.sub(CODE_MARK, text)


def sentences(text):
    return [s.strip() for s in SENTENCE_END.split(plain(text)) if s.strip()]


def shown(text, limit=60):
    """보고에 적을 글. 인라인 코드 자리를 `…` 로 보여 줌."""
    return text[:limit].replace(CODE_MARK, "`…`")


# 말투 검사기

def external_checker(path=None):
    """바깥 말투 검사기(check_doc_tone.py)의 check 함수. (함수 또는 None, 찾아본 경로)."""
    path = path or os.environ.get(EXTERNAL_ENV) or EXTERNAL_DEFAULT
    if not os.path.isfile(path):
        return None, path
    try:
        spec = importlib.util.spec_from_file_location("study_tone_checker", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as error:  # noqa: BLE001 - 바깥 파일이라 어떤 예외든 이유만 보여 줌
        return None, "%s (%s)" % (path, error)
    fn = getattr(module, "check", None)
    return (fn if callable(fn) else None), path


def checkers(external_path=None, use_external=True):
    """[(이름, check 함수)]. 저장소의 check_style 은 늘 들어가고 바깥 검사기는 있을 때만."""
    found = [("check_style", check_style.check)]
    note = ""
    if use_external:
        fn, path = external_checker(external_path)
        if fn:
            found.append(("check_doc_tone", fn))
        else:
            note = "바깥 말투 검사기를 찾지 못해 저장소의 tools/check_style.py 만 씁니다(찾은 곳: %s)." % path
    return found, note


def style_fails(text, name, tools):
    """글 하나를 모든 검사기에 넘겨 (규칙, 걸린 곳) 을 합침. 같은 것은 한 번만."""
    seen, out = set(), []
    for _, fn in tools:
        try:
            fails = fn(text, False, name)
        except Exception as error:  # noqa: BLE001
            fails = [("검사기 오류", str(error)[:60])]
        for rule, where in fails:
            key = (rule, where)
            if key not in seen:
                seen.add(key)
                out.append((rule, where))
    return out


# 보고

class Report:
    def __init__(self, label):
        self.label = label
        self.rows = []  # (level, where, rule, text)

    def error(self, where, rule, text):
        self.rows.append(("error", where, rule, text))

    def warn(self, where, rule, text):
        self.rows.append(("warn", where, rule, text))

    @property
    def errors(self):
        return [r for r in self.rows if r[0] == "error"]

    @property
    def warnings(self):
        return [r for r in self.rows if r[0] == "warn"]

    def lines(self):
        return ["  %s %s: %s: %s" % (LEVEL_NAMES[level], where, rule, text) for level, where, rule, text in self.rows]


# 낱말(용어) 맥락

class Terms:
    """terms.json 의 낱말. 긴 낱말부터 맞춰 보고, 별칭은 본 낱말로 셈."""

    def __init__(self, data, extra=()):
        self.pages = {}
        self.forms = {}  # 글에 나오는 꼴 → 본 낱말
        for item in data.get("terms", []):
            self.pages[item["term"]] = item.get("page", "")
            self.forms[item["term"]] = item["term"]
            for also in item.get("also", []):
                self.forms[also] = item["term"]
        for word in extra:
            self.forms.setdefault(word, word)
        self.known = set(data.get("known", []))

    def find(self, sentence):
        """문장에 나온 (본 낱말, 쓰인 꼴) 목록. 긴 꼴부터 맞춰 겹치지 않게 봄."""
        found, masked = [], sentence
        for form in sorted(self.forms, key=len, reverse=True):
            at = masked.find(form)
            while at >= 0:
                found.append((self.forms[form], form, at))
                masked = masked[:at] + "\0" * len(form) + masked[at + len(form):]
                at = masked.find(form)
        return sorted(found, key=lambda f: f[2])


def definition_form(sentence, form):
    esc = re.escape(form)
    if re.search(r"%s(\([^)]*\))?(이|가)?\s*(이?라고\s*(합니다|부릅니다|불립니다|하고|부르고|부르는|하는|하며)|이?라는(?=\s|$)|이?란(?=\s))"
                 % esc, sentence):
        return True
    return bool(re.search(r"%s(은|는|이란|란)\s.*부르는 말" % esc, sentence))


def pseudo_definition(sentence, form):
    """정의 문장인데 무엇을 그 낱말이라고 하는지가 문장 안에 없음("이것을 X라고 합니다", 문장이 낱말로 시작)."""
    head = sentence[:sentence.find(form)].strip().rstrip(",")
    head = re.sub(r"^(그래서|그러면|그리고|이때|이렇게 하면)\s+", "", head)
    return not head or bool(PSEUDO_SUBJECT.match(head))


def page_defines(pid, bank_dir, index, report, seen=None):
    """needs 페이지가 정의한 낱말(그 페이지의 needs 까지 따라감). 아직 출제되지 않은 페이지는 경고."""
    seen = seen if seen is not None else set()
    if pid in seen:
        return set()
    seen.add(pid)
    entry = next((e for e in index["pages"] if e["id"] == pid), None)
    if entry is None:
        report.error("meta.json", "needs", "페이지 %s 가 index.json 에 없습니다" % pid)
        return set()
    if not bank.is_ready("page", pid, bank_dir):
        report.warn("meta.json", "needs", "페이지 %s 가 아직 출제되지 않아 그 페이지가 정의하는 낱말을 알 수 없습니다" % pid)
        return set()
    page = bank.load_page(entry, bank_dir)
    words = set(page["defines"])
    for other in page["needs"]:
        words |= page_defines(other, bank_dir, index, report, seen)
    return words


def context_check(texts, terms, allowed, listed, report):
    """texts 는 [(파일 이름, 글)] 순서대로. allowed 는 알아도 되는 낱말, listed 는 이 글이 정의한다고 적은 낱말."""
    allowed = set(allowed)
    first, late = {}, {}
    for name, text in texts:
        for unit in units_of(text):
            if not unit.prose:
                continue
            where = "%s:%d" % (name, unit.line)
            here = (name, unit.line)
            for sentence in sentences(unit.text):
                for term, form, _ in terms.find(sentence):
                    is_def = definition_form(sentence, form)
                    if is_def and pseudo_definition(sentence, form):
                        report.warn(where, "가짜 정의", "무엇을 '%s'(이)라고 하는지가 문장 안에 없습니다: %s" % (form, shown(sentence)))
                    if term not in first:
                        first[term] = where
                        if term in listed:
                            if not is_def:
                                late[term] = (where, shown(sentence), here)
                        elif term in allowed or term in terms.known:
                            pass
                        elif is_def:
                            report.warn(where, "defines 누락", "meta 의 defines(_inline)에 없는 낱말을 여기서 정의합니다: '%s'" % form)
                        else:
                            report.error(where, "정의 전 사용", "소개되기 전에 나온 낱말: '%s'. 이 글에서 먼저 정의하거나 needs 에 %s 를 넣으세요: %s"
                                         % (form, terms.pages.get(term) or "그 페이지", shown(sentence)))
                        allowed.add(term)
                    elif is_def and term in late:
                        used_at, _, used_unit = late.pop(term)
                        if used_unit != here:  # 같은 문단 안에서 바로 다음 문장에 정의하면 넘어감
                            report.error(where, "정의가 사용 뒤에 옴", "낱말 '%s'의 정의가 첫 사용(%s)보다 뒤에 있습니다" % (form, used_at))
    for term, (where, sentence, _) in sorted(late.items()):
        report.warn(where, "정의 꼴", "첫 문장이 정의 꼴(…를 %s라고 합니다)이 아닌 낱말: '%s'. 문장: %s" % (term, term, sentence))
    for term in sorted(listed):
        if term not in first:
            report.warn("meta.json", "defines", "defines(_inline)에 적혔지만 글에 나오지 않는 낱말: '%s'" % term)


# 그 밖의 규칙

def extra_rules(name, text, report):
    units = units_of(text)
    for n, unit in enumerate(units):
        where = "%s:%d" % (name, unit.line)
        if unit.kind == "heading":
            title = unit.text.strip()
            if title.endswith("?") and not QUESTION_OK.search(title):
                report.error(where, "반말 질문 제목", "제목의 질문은 '~나요?', '~까요?' 처럼 씁니다: %s" % title)
            elif INFORMAL.search(title):
                report.error(where, "반말 제목", title)
            continue
        if not unit.prose:
            continue
        flat = plain(unit.text)
        for m in SPACED.finditer(flat):
            report.error(where, "띄어 쓴 조사", "영어 낱말이나 코드 뒤의 조사는 붙여 씁니다: %s" % shown(flat[max(0, m.start() - 12):m.end()].strip()))
        for m in POINTING.finditer(flat):
            wanted = POINT_KINDS[m.group(2)]
            if m.group(1) == "위":
                scope = reversed(units[:n])
                stop = lambda u: u.kind == "heading" and u.level <= 2  # noqa: E731
            else:
                scope = units[n + 1:]
                stop = lambda u: u.kind == "heading"  # noqa: E731
            found = False
            for other in scope:
                if stop(other):
                    break
                if other.kind in wanted:
                    found = True
                    break
            if not found:
                report.error(where, "가리키는 것이 없음", "'%s'라고 썼지만 이 절에 가리킬 %s 블록이 없습니다" % (m.group(0), m.group(2)))
        sents = sentences(unit.text)
        for i, s in enumerate(sents):
            if PREDICT.search(s) and "실행" not in s:
                answer = next((t for t in sents[i + 1:] if ANSWERED.search(t) and "실행" not in t), None)
                if answer:
                    report.warn(where, "예상 뒤 바로 답", "예상해 보라는 문장 뒤에 같은 문단에서 답이 이어집니다: %s" % shown(answer, 50))
    for start, end in sections(units):
        blocks = [u for u in units[start:end] if u.kind in ("para", "list", "quote", "code", "figure", "table", "alt")]
        if len(blocks) < 3 or blocks[-1].kind != "para":
            continue
        last = blocks[-1]
        if INLINE_CODE.search(last.text) or len(sentences(last.text)) != 1 or len(last.text) > SHORT_CLOSE:
            continue
        report.warn("%s:%d" % (name, last.line), "외딴 짧은 문단", "절 끝의 한 문장 문단입니다. 앞 문단에 붙이거나 지우세요: %s" % shown(last.text))


def sections(units):
    """제목으로 나눈 [(시작, 끝)] 인덱스 구간(제목 포함)."""
    starts = [n for n, u in enumerate(units) if u.kind == "heading"]
    bounds = [0] + starts + [len(units)]
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i + 1] > bounds[i]]


def squeeze(text):
    return re.sub(r"[\s`\"'.,!?:;()\[\]「」·]", "", plain(text))


def leak_check(brief, steps_text, report):
    """brief.md 가 단계 제목·요구·검사·힌트와 LEAK_MIN 글자 넘게 겹치면 오류."""
    flat = squeeze(" ".join(u.text for u in units_of(brief) if u.prose))
    for step in bank.parse_steps(steps_text):
        if step["no"] == 0:
            continue
        pieces = [("제목", step["title"])] + [("요구", step["request"])]
        pieces += [("검사", c) for c in step["checks"]] + [("힌트", h) for h in step["hints"]]
        for label, piece in pieces:
            packed = squeeze(piece)
            if not packed:
                continue
            if label == "제목" and len(packed) >= 4 and packed in flat:
                report.error("brief.md", "요구 유출", "%d단계 제목이 그대로 나옵니다: %s" % (step["no"], step["title"]))
                continue
            match = difflib.SequenceMatcher(None, flat, packed, autojunk=False).find_longest_match(0, len(flat), 0, len(packed))
            if match.size >= LEAK_MIN:
                report.error("brief.md", "요구 유출", "%d단계 %s와 겹칩니다: %s" % (step["no"], label, packed[match.b:match.b + match.size]))


# 항목 읽기

def load_items(bank_dir, wanted=None):
    """출제된 항목을 [(종류, entry)] 로. wanted 가 있으면 그 id 만(없는 id 는 ValueError)."""
    index = bank.read_index(bank_dir)
    rows = []
    for kind in ("mission", "topic", "page"):
        for entry in index[kind + "s"]:
            if bank.is_ready(kind, entry["id"], bank_dir):
                rows.append((kind, entry))
    if wanted:
        known = {entry["id"]: (kind, entry) for kind, entry in rows}
        missing = [w for w in wanted if w not in known]
        if missing:
            raise ValueError("출제된 미션·주제·페이지가 아닙니다: %s" % ", ".join(missing))
        rows = [known[w] for w in wanted]
    return index, rows


def mission_texts(mission, secrets):
    """맥락 검사 순서의 [(이름, 글)]. brief.md 는 공개 파일, 나머지는 봉인 안."""
    out = [("brief.md", mission["brief"])]
    out += [(name, secrets[name]) for name in MISSION_TEXTS[1:] if name in secrets]
    return out


def test_names(secrets):
    """검사 파일의 테스트 이름에서 id 를 뗀 학습자용 문장 [(파일, 문장)]."""
    out = []
    for rel, text in sorted(secrets.items()):
        if rel.startswith("checks/") and rel.endswith(".tsx"):
            for _, title in bank.TEST_NAME.findall(text):
                out.append((rel, title.split(" ", 1)[1] if " " in title else title))
    return out


def split_chains(markdown):
    """chains.md 를 {사슬 id: 그 사슬의 글} 로(## 사슬 id 줄 기준)."""
    out, current = {}, None
    for line in markdown.replace("\r\n", "\n").split("\n"):
        found = bank.CHAIN_HEAD.match(line.strip())
        if found and not line.startswith("###") and bank.CHAIN_ID.match(found.group(1)):
            current = found.group(1)
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return {cid: "\n".join(lines) for cid, lines in out.items()}


def extracted_strings(name, text):
    """검사기가 건너뛰는 표 칸, figure 캡션, 그림 대체 글을 [(어디, 글, 문장인지)] 로."""
    labels = {"caption": "캡션", "cell": "표 칸", "alt": "그림 대체 글"}
    return [("%s:%d(%s)" % (name, u.line, labels[u.kind]), u.text, True) for u in units_of(text) if u.kind in labels]


def style_check(report, tools, md_files, strings):
    """md_files 는 [(이름, 글)] 로 통째로, strings 는 [(어디, 한 줄, 문장인지)] 로 검사기에 넘김. 문장인 줄(검사 이름, 표 칸,
    캡션)이 마침표 없이 끝나면 마침표를 붙여서 ~함/~음 으로 끝나는 꼴도 잡히게 함. 제목은 그대로 둠."""
    for name, text in md_files:
        for rule, where in style_fails(text, name if name.endswith(".md") else name + ".md", tools):
            report.error(name, "말투 " + rule, where)
    for where, line, sentence in strings:
        probe = line.strip()
        if sentence and probe and not re.search(r"[.?!]\s*$", probe):
            probe += "."
        for rule, found in style_fails(probe, "strings.md", tools):
            report.error(where, "말투 " + rule, found)


def lint_item(kind, entry, bank_dir, index, tools, parts=("style", "context", "extra")):
    """항목 하나를 검사해 Report 로. parts 로 말투·맥락·그 밖의 규칙을 고름."""
    report = Report("%s %s" % (entry["id"], entry["title"]))
    terms_data = bank.read_terms(bank_dir)
    try:
        if kind == "mission":
            item = bank.load_mission(entry, bank_dir)
            secrets = bank.load_secrets(item["dir"])
            texts = mission_texts(item, secrets)
            strings = [("meta.json(title)", item["title"], False)]
            strings += [(rel, title, True) for rel, title in test_names(secrets)]
            for name, text in texts:
                strings += extracted_strings(name, text)
            if "style" in parts:
                style_check(report, tools, texts, strings)
            if "context" in parts:
                allowed = set(terms_data["known"])
                for pid in item["needs"]:
                    allowed |= page_defines(pid, bank_dir, index, report)
                listed = set(item["defines_inline"])
                context_check(texts, Terms(terms_data, listed), allowed | listed, listed, report)
            if "extra" in parts:
                for name, text in texts:
                    extra_rules(name, text, report)
                if "steps.md" in secrets:
                    leak_check(item["brief"], secrets["steps.md"], report)
        elif kind == "topic":
            item = bank.load_topic(entry, bank_dir)
            secrets = bank.load_secrets(item["dir"])
            text = secrets.get("chains.md", "")
            strings = [("meta.json(title)", item["title"], False)]
            for chain in item["chains"]:
                strings += [("meta.json(%s title)" % chain["id"], chain["title"], False),
                            ("meta.json(%s goal)" % chain["id"], chain["goal"], True)]
            strings += extracted_strings("chains.md", text)
            if "style" in parts:
                style_check(report, tools, [("chains.md", text)], strings)
            if "context" in parts:
                parts_of = split_chains(text)
                for chain in item["chains"]:
                    listed = set(chain["defines_inline"])
                    body = parts_of.get(chain["id"], "")
                    context_check([("chains.md(%s)" % chain["id"], body)], Terms(terms_data, listed),
                                  set(terms_data["known"]) | listed, listed, report)
            if "extra" in parts:
                extra_rules("chains.md", text, report)
        else:
            item = bank.load_page(entry, bank_dir)
            text = item["markdown"]
            strings = [("meta.json(title)", item["title"], False)]
            strings += [("meta.json(sections %s)" % key, title, False) for key, title in sorted(item["sections"].items())]
            strings += extracted_strings("page.md", text)
            if "style" in parts:
                style_check(report, tools, [("page.md", text)], strings)
            if "context" in parts:
                allowed = set(terms_data["known"])
                for pid in item["needs"]:
                    allowed |= page_defines(pid, bank_dir, index, report)
                listed = set(item["defines"])
                context_check([("page.md", text)], Terms(terms_data, listed), allowed | listed, listed, report)
            if "extra" in parts:
                extra_rules("page.md", text, report)
    except bank.BankError as error:
        report.error("meta.json", "읽기 실패", str(error))
    return report


def main(argv=None, out=None):
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog="web_lint.py", add_help=False)
    parser.add_argument("targets", nargs="*")
    parser.add_argument("--bank", default=bank.BANK_DIR)
    parser.add_argument("--checker")
    parser.add_argument("--no-external", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    opts = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if opts.help:
        print(__doc__.replace("%d", str(LEAK_MIN)).strip(), file=out)
        return 0
    bank_dir = os.path.abspath(opts.bank)
    tools, note = checkers(opts.checker, not opts.no_external)
    if note:
        print(note, file=out)
    try:
        index, rows = load_items(bank_dir, opts.targets)
    except (bank.BankError, ValueError) as error:
        print(str(error), file=out)
        return 2
    errors = warnings = 0
    for kind, entry in rows:
        report = lint_item(kind, entry, bank_dir, index, tools)
        print("[%s]" % report.label, file=out)
        for line in report.lines():
            print(line, file=out)
        if not report.rows:
            print("  통과", file=out)
        errors += len(report.errors)
        warnings += len(report.warnings)
    print("오류 %d, 경고 %d (항목 %d개)" % (errors, warnings, len(rows)), file=out)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
