# -*- coding: utf-8 -*-
"""AI 비전 개론 은행(ai/) 읽기(설계 8절).

index.json 은 웹 꼴(missions·topics·pages·order)에 exam, lessons, patterns, mocks 를 더한 것이라 웹 키는 webprep.bank 가
그대로 읽고 나머지를 여기서 읽음. 학습 노트 ai/learn/lNN/ 은 웹 학습 노트 꼴(meta.json, page.md, assets/)이고 page.md 의
## 는 단원, ### 는 단계, 울타리 figure·ai-* 는 블록임(8.3). ai-levels 는 단계 끝의 「세 수준으로 다시 보기」이고 수준 7·15·20
마다 글, 그림, 확인 물음을 가짐(_levels_block). 문항 묶음 ai/items/iNN/ 은 공개 meta.json·gens.py·oracle.py 와
봉인된 work/items.json·statements.json·facts.json·review.json 임. 차시가 "출제됨"이라는 것은 학습 노트 meta.json, 문항
meta.json, 봉인(또는 평문 작업본 work/)이 모두 있다는 것임. 경로 상수는 쓸 때 bank.AI_DIR 로 읽음(테스트가 바꿔 끼움).
"""
import copy
import hashlib
import json
import os
import re

import study
from aiprep import gen as genlib
from aiprep.grade import BLANK, MODES
from learning_data import generation
from learning_data.collection import digest
from webprep import bank as webbank

AI_DIR = os.path.join(study.ROOT, "ai")
INDEX_NAME, TERMS_NAME, RETIRED_NAME = "index.json", "terms.json", "retired.json"
LESSON_ID = re.compile(r"[ia](\d{2})\Z")
PAGE_ID = re.compile(r"a?l(\d{2})\Z")
MOCK_ID = re.compile(r"m(\d{1,2})\Z")
UNIT_KEY = re.compile(r"(a?\d{1,2})([a-i])\Z")
CARD_ID = re.compile(r"(?:[ia]\d{2}|pc|m\d{1,2})-[a-z]\d{2,3}\Z")
COURSES = {"intro": "AI 개론", "app": "AI 응용"}


def course_of(lid):
    """고유 차시 id에서 과정 구분을 구함. 기존 id는 개론으로 유지함."""
    return "app" if str(lid or "").startswith("a") else "intro"


FACTS_MARK = re.compile(r"^\s*<!--\s*facts:\s*(.*?)\s*-->\s*$")
ANCHOR_MARK = re.compile(r'^\s*<a (?:id|name)="[\w-]+"></a>\s*$')
SKEL_MARK = re.compile(r"^\s*<!--\s*skel:\s*(S\d+)\s+(.*?)\s*-->\s*$")  # 바로 아래 코드 울타리가 그 뼈대 판과 같아야 함
FENCE = re.compile(r"^\s*(```|~~~)\s*([\w-]*)\s*$")
BLOCK_KINDS = {"ai-guess": "guess", "ai-reveal": "reveal", "ai-recall": "recall", "ai-why": "why", "ai-diff": "diff",
               "ai-rotate": "rotate", "ai-memo": "memo", "ai-trend": "trend", "ai-levels": "levels", "ai-formula": "formula"}
FORMULA_TEXT_KEYS = ("id", "title", "input", "terms", "operation", "output", "q", "a")
LEVELS = (7, 15, 20)
LEVEL_KEYS = ("level", "text", "figure", "q", "answer", "mode", "places", "unit", "why")
LEVEL_KEYS_20 = LEVEL_KEYS + ("code", "mistake")  # 20살만 쓰는 키
LEVEL_TEXTS = ("text", "q", "why", "code", "mistake")
LEVEL_PARTS = ("text", "caption", "content", "code", "mistake", "q", "why")  # level_parts 가 돌려주는 순서
LEVEL_FIGURE = re.compile(r"assets/[^/]+\.png\Z")
SCOPES = (("심화", "deep"), ("보충 설명", "support"), ("더 알아보기", "extra"), ("2026 흐름", "trend"), ("외울 것", "memo"))
NUMBERS = "①②③④⑤⑥⑦⑧⑨⑩"


class AiBankError(webbank.BankError):
    """은행 파일을 읽지 못함. 문구는 화면 띠나 터미널에 그대로 보여 줌."""


def source_stamp(root=None):
    """과정 재진입에 쓸 자료 변경 표식. 그림은 표시할 때 별도로 읽음."""
    def failed(error):
        raise error
    rows = []
    try:
        for folder, dirs, names in os.walk(root or AI_DIR, onerror=failed):
            dirs[:] = sorted(name for name in dirs if name not in ("assets", "__pycache__"))
            for name in sorted(names):
                path = os.path.join(folder, name)
                stat = os.stat(path)
                rows.append((path, stat.st_mtime_ns, stat.st_size, stat.st_ino, stat.st_ctime_ns))
    except OSError:
        return None
    return tuple(rows)


def _read_json(path, shown):
    try:
        return study.read_json(path)
    except (OSError, ValueError) as error:
        raise AiBankError("%s 을 읽을 수 없습니다: %s" % (shown, error))


def _list(value):
    return [str(v) for v in (value or [])]


# index.json, terms.json, retired.json

def read_index(root=None):
    """index.json 을 {"pages", "order", "exam", "lessons", "patterns", "mocks"} 로. 날짜는 글 그대로 둠(review.exam_dates 로 바꿈)."""
    root = root or AI_DIR
    try:
        web = webbank.read_index(root)
    except webbank.BankError as error:
        raise AiBankError(str(error))
    data = _read_json(os.path.join(root, INDEX_NAME), INDEX_NAME)
    try:
        exam = {key: str(data["exam"][key]) for key in ("date", "last_new", "sweep_from", "last_review")}
        lessons = []
        for item in data["lessons"]:
            lid = str(item["id"])
            if not LESSON_ID.match(lid):
                raise ValueError("lessons 의 id %r" % lid)
            course = str(item.get("course") or course_of(lid))
            if course not in COURSES or course != course_of(lid):
                raise ValueError("lessons 의 course %r" % course)
            lessons.append({"course": course, "id": lid, "no": int(item["no"]), "title": str(item["title"]), "page": str(item["page"]),
                            "date": str(item.get("date") or ""), "weight": float(item.get("weight", 1.0)),
                            "units": int(item.get("units", 0)), "hw_due": item.get("hw_due")})
        patterns = []
        for item in data.get("patterns") or []:
            units = {str(k): {"after": str((v or {}).get("after", "")), "name": str((v or {}).get("name", ""))}
                     for k, v in (item.get("units") or {}).items()}
            patterns.append({"id": str(item["id"]), "page": str(item["page"]), "title": str(item.get("title", "상황별 코드")),
                             "units": units})
        mocks = []
        for item in data.get("mocks") or []:
            mid = str(item["id"])
            if not MOCK_ID.match(mid):
                raise ValueError("mocks 의 id %r" % mid)
            mocks.append({"id": mid, "title": str(item["title"]), "minutes": int(item.get("minutes", 60)),
                          "count": int(item.get("count", 30)), "range": [int(x) for x in item.get("range", [1, 17])],
                          "window": [str(x) for x in item.get("window", [])]})
            for key in ("scope", "courses", "course_counts", "blueprint", "blueprint_revision"):
                if key in item:
                    mocks[-1][key] = item[key]
    except (KeyError, TypeError, ValueError) as error:
        raise AiBankError("%s 의 형식이 맞지 않습니다: %s" % (INDEX_NAME, webbank._why(error)))
    return {"pages": web["pages"], "order": web["order"], "exam": exam, "lessons": lessons, "patterns": patterns,
            "mocks": mocks, "courses": dict(COURSES)}


def read_terms(root=None):
    """terms.json 을 {"known", "terms": [{"term", "also", "accept", "page", "intro"}]} 로. 없으면 빈 목록."""
    path = os.path.join(root or AI_DIR, TERMS_NAME)
    if not os.path.isfile(path):
        return {"known": [], "terms": []}
    data = _read_json(path, TERMS_NAME)
    try:
        terms = [{"term": str(t["term"]), "also": _list(t.get("also")), "accept": _list(t.get("accept")),
                  "page": str(t.get("page", "")), "intro": str(t.get("intro", ""))} for t in data.get("terms", [])]
        return {"known": _list(data.get("known")), "terms": terms}
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise AiBankError("%s 의 형식이 맞지 않습니다: %s" % (TERMS_NAME, webbank._why(error)))


def read_retired(root=None):
    """retired.json 의 지운 id 집합. 없으면 빈 집합."""
    path = os.path.join(root or AI_DIR, RETIRED_NAME)
    if not os.path.isfile(path):
        return set()
    data = _read_json(path, RETIRED_NAME)
    return {str(x) for x in data.get("ids", [])}


# 폴더와 출제 여부

def page_dir(pid, root=None):
    return os.path.join(root or AI_DIR, "learn", pid)


def items_dir(iid, root=None):
    return os.path.join(root or AI_DIR, "items", iid)


def mock_dir(mid, root=None):
    return os.path.join(root or AI_DIR, "mocks", mid)


def has_secrets(folder):
    return os.path.isfile(os.path.join(folder, webbank.SEALED_NAME)) or os.path.isdir(os.path.join(folder, webbank.WORK_DIR))


def is_ready(lesson, root=None):
    """학습 노트 meta.json, 문항 meta.json, 봉인(또는 평문 작업본)이 모두 있으면 출제된 차시."""
    return (os.path.isfile(os.path.join(page_dir(lesson["page"], root), "meta.json"))
            and os.path.isfile(os.path.join(items_dir(lesson["id"], root), "meta.json"))
            and has_secrets(items_dir(lesson["id"], root)))


def pattern_ready(group, root=None):
    """상황별 코드 무리가 출제됐는지. 학습 노트 meta.json, items/<무리 id>/meta.json, 봉인(또는 평문 작업본), patterns 폴더의
    S*.json 하나 이상이 모두 있어야 함."""
    try:
        skeletons = [n for n in os.listdir(os.path.join(root or AI_DIR, "patterns")) if re.match(r"S\d+\.json\Z", n)]
    except OSError:
        skeletons = []
    return (bool(skeletons) and os.path.isfile(os.path.join(page_dir(group["page"], root), "meta.json"))
            and os.path.isfile(os.path.join(items_dir(group["id"], root), "meta.json"))
            and has_secrets(items_dir(group["id"], root)))


def lesson_of_unit(key):
    """단원 키 5c → i05, 18a → None(상황별 코드)."""
    found = UNIT_KEY.match(key or "")
    if not found or found.group(1) == "18":
        return None
    number = found.group(1)
    return ("a%02d" % int(number[1:])) if number.startswith("a") else ("i%02d" % int(number))


# 학습 노트

def strip_marks(text):
    """단계 머리의 facts·skel 표시와 제목의 이전 주소를 보존하는 빈 앵커를 지운 글. 화면(Doc·DocView)에 넘기기 전에 씀(mdlite 는
    주석을 글로 그림)."""
    return "\n".join(line for line in (text or "").replace("\r\n", "\n").split("\n")
                     if not FACTS_MARK.match(line) and not SKEL_MARK.match(line) and not ANCHOR_MARK.match(line))


def skel_fences(markdown):
    """page.md 의 <!-- skel: S1 표준형 --> 표시와 바로 아래 코드 울타리 [{"skel", "variant", "line"(표시 줄 번호), "code"}].
    code 는 울타리 안 줄 목록이고, 표시 아래 첫 글 줄이 울타리가 아니거나 울타리가 닫히지 않으면 None."""
    lines = (markdown or "").replace("\r\n", "\n").split("\n")
    out = []
    for no, line in enumerate(lines):
        found = SKEL_MARK.match(line)
        if not found:
            continue
        row = {"skel": found.group(1), "variant": found.group(2), "line": no + 1, "code": None}
        at = next((k for k in range(no + 1, len(lines)) if lines[k].strip()), None)
        opened = FENCE.match(lines[at]) if at is not None else None
        if opened and opened.group(2) and not opened.group(2).startswith("ai-") and opened.group(2) != "figure":
            end = next((k for k in range(at + 1, len(lines)) if FENCE.match(lines[k]) and not FENCE.match(lines[k]).group(2)), None)
            if end is not None:
                row["code"] = lines[at + 1:end]
        out.append(row)
    return out


def facts_of(lines):
    for line in lines:
        found = FACTS_MARK.match(line)
        if found:
            return [x for x in re.split(r"[\s,]+", found.group(1)) if x]
    return []


def scope_of(title):
    for head, scope in SCOPES:
        if title.startswith(head):
            return scope
    return "lecture"


def figure_block(lines, folder=None):
    """figure 울타리 안 줄을 {"kind": "figure", "file", "path", "caption", "frames": [{"text", "ms"}], "content"} 로."""
    out = {"kind": "figure", "file": "", "path": "", "caption": "", "frames": [], "content": ""}
    in_frames = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("파일:"):
            out["file"] = stripped[len("파일:"):].strip()
            in_frames = False
        elif stripped.startswith("캡션:"):
            out["caption"] = stripped[len("캡션:"):].strip()
            in_frames = False
        elif stripped.startswith("내용:"):
            out["content"] = stripped[len("내용:"):].strip()
            in_frames = False
        elif stripped.startswith("프레임:"):
            in_frames = True
        elif re.match(r"^\d+\.\s", stripped):
            found = re.match(r"^\d+\.\s*(.*?)\s*(?:\((\d+)\s*ms\))?\s*\Z", stripped)
            out["frames"].append({"text": found.group(1), "ms": int(found.group(2)) if found.group(2) else None})
    if folder and out["file"]:
        out["path"] = os.path.join(folder, *out["file"].split("/"))
    return out


def _formula_block(text, folder=None):
    """입력·항·계산·출력과 접힌 확인 물음을 읽음. 알 수 없는 키와 그림 경로는 거부함."""
    def broken(message):
        return {"kind": "formula", "error": message}
    try:
        data = json.loads(text)
    except ValueError:
        return broken("수식 설명의 JSON을 읽을 수 없습니다.")
    if not isinstance(data, dict) or set(data) != set(FORMULA_TEXT_KEYS) | {"figure"}:
        return broken("수식 설명의 필드가 맞지 않습니다.")
    if any(not isinstance(data[k], str) or not data[k].strip() or "```" in data[k] or "~~~" in data[k]
           for k in FORMULA_TEXT_KEYS):
        return broken("수식 설명은 비어 있지 않은 글로 쓰고 코드 울타리를 넣지 않습니다.")
    fig = data["figure"]
    if not isinstance(fig, dict) or set(fig) != {"file", "caption", "content", "frames"}:
        return broken("수식 그림의 필드가 맞지 않습니다.")
    if any(not isinstance(fig[k], str) or not fig[k].strip() for k in ("file", "caption", "content")):
        return broken("수식 그림의 파일·캡션·대체 설명을 적어 주세요.")
    if not re.fullmatch(r"assets/[\w-]+\.(?:png|gif)", fig["file"]):
        return broken("수식 그림은 assets 아래 PNG 또는 GIF 파일이어야 합니다.")
    frames = fig["frames"]
    if not isinstance(frames, list) or any(not isinstance(f, dict) or set(f) != {"text", "ms"}
            or not isinstance(f["text"], str) or not f["text"].strip()
            or type(f["ms"]) is not int or not 1600 <= f["ms"] <= 2500 for f in frames):
        return broken("수식 그림의 장별 설명과 시간을 확인해 주세요.")
    if (fig["file"].endswith(".gif") and not 2 <= len(frames) <= 10) or (fig["file"].endswith(".png") and frames):
        return broken("GIF는 2~10장으로 쓰고 PNG에는 장 목록을 넣지 않습니다.")
    return dict(data, kind="formula", figure=dict(fig, kind="figure",
                path=os.path.join(folder, *fig["file"].split("/")) if folder else ""))


def _json_block(kind, text):
    try:
        data = json.loads(text)
    except ValueError as error:
        return {"kind": kind, "error": "JSON 을 읽을 수 없습니다: %s" % error}
    if kind == "memo":
        if not isinstance(data, list):
            return {"kind": kind, "error": "ai-memo 는 [{\"q\", \"a\", \"cards\"}] 목록이어야 합니다."}
        return {"kind": kind, "items": data}
    if not isinstance(data, dict):
        return {"kind": kind, "error": "%s 는 JSON 객체여야 합니다." % kind}
    out = dict(data)
    out["kind"] = kind
    return out


def _levels_block(text, folder=None):
    """ai-levels 울타리 안 JSON 을 {"kind": "levels", "id", "concept", "levels": [수준 셋]} 으로. 수준은 {"level", "id"(블록 id),
    "text", "q", "answer", "mode", "places"(없으면 None), "unit"(없으면 ""), "why", "code", "mistake", "figure"} 이고 figure 는
    None 이나 figure 블록 꼴(path 는 folder 기준). 꼴이 맞지 않으면 {"kind": "levels", "error"} 하나(키 이름을 잘못 쓴 블록이 조용히
    버려지지 않게 함)."""
    def broken(message):
        return {"kind": "levels", "error": message}

    try:
        data = json.loads(text)
    except ValueError as error:
        return broken("JSON 을 읽을 수 없습니다: %s" % error)
    if not isinstance(data, dict):
        return broken("ai-levels 는 JSON 객체여야 합니다.")
    unknown = sorted(set(data) - {"id", "concept", "levels"})
    if unknown:
        return broken("ai-levels 에 모르는 키가 있습니다: %s" % ", ".join(unknown))
    concept = data.get("concept", "")
    if not isinstance(concept, str):
        return broken("ai-levels 의 concept 는 글이어야 합니다.")
    levels = data.get("levels")
    if not isinstance(levels, list) or len(levels) != len(LEVELS) or not all(isinstance(x, dict) for x in levels) \
            or [x.get("level") for x in levels] != list(LEVELS) or not all(type(x.get("level")) is int for x in levels):
        return broken("levels 는 level 7·15·20 순서의 객체 셋이어야 합니다.")
    bid = "" if data.get("id") is None else str(data["id"])
    rows, texts = [], [concept]
    for level in levels:
        no = level["level"]
        unknown = sorted(set(level) - set(LEVEL_KEYS_20 if no == 20 else LEVEL_KEYS))
        if unknown:
            return broken("%d살 수준에 쓸 수 없는 키가 있습니다: %s" % (no, ", ".join(unknown)))
        row = {"level": no, "id": bid}
        for key in LEVEL_TEXTS:
            row[key] = level.get(key, "")
            if not isinstance(row[key], str):
                return broken("%d살 수준의 %s 는 글이어야 합니다." % (no, key))
        row["mode"] = level.get("mode", "word")
        if not isinstance(row["mode"], str):
            return broken("%d살 수준의 mode 는 글이어야 합니다." % no)
        if row["mode"] not in MODES:
            return broken("%d살 수준의 mode 를 모릅니다: %s" % (no, row["mode"]))
        row["places"], row["unit"] = level.get("places"), level.get("unit", "")
        if row["places"] is not None and (type(row["places"]) is not int or row["places"] < 0):
            return broken("%d살 수준의 places 는 0 이상의 정수여야 합니다." % no)
        if not isinstance(row["unit"], str):
            return broken("%d살 수준의 unit 는 글이어야 합니다." % no)
        answer = level.get("answer")
        if not isinstance(answer, list) or not answer or not all(isinstance(a, str) for a in answer):
            return broken("%d살 수준의 answer 는 비지 않은 글 목록이어야 합니다." % no)
        row["answer"] = list(answer)
        row["figure"] = None
        if "figure" in level:
            fig = level["figure"]
            if not isinstance(fig, dict) or set(fig) != {"file", "caption", "content"} \
                    or not all(isinstance(fig[k], str) for k in ("file", "caption", "content")):
                return broken("%d살 수준의 figure 는 {\"file\", \"caption\", \"content\"} 글 객체여야 합니다." % no)
            if not LEVEL_FIGURE.match(fig["file"]):
                return broken("%d살 수준의 그림은 assets/ 아래 .png 여야 합니다: %s" % (no, fig["file"]))
            row["figure"] = {"kind": "figure", "file": fig["file"], "path": os.path.join(folder, *fig["file"].split("/")) if folder else "",
                             "caption": fig["caption"], "content": fig["content"], "frames": []}
            texts += [fig["caption"], fig["content"]]
        texts += [row[key] for key in LEVEL_TEXTS] + row["answer"]
        rows.append(row)
    if any("```" in value or "~~~" in value for value in texts):  # 화면의 mdlite 는 ~~~ 도 코드 울타리로 읽음
        return broken("ai-levels 글 안에는 ``` 나 ~~~ 를 쓰지 않습니다. 코드는 20살 수준의 code 에 둡니다.")
    return {"kind": "levels", "id": bid, "concept": concept, "levels": rows}


def level_parts(level):
    """수준 하나의 글을 [(이름, 글)] 로. 이름은 text, caption, content, code, mistake, q, why 순이고 빈 글은 뺌.
    검사, 재풀이 공개본, 말투 덤프가 같이 씀."""
    figure = level.get("figure") or {}
    values = dict(level, caption=figure.get("caption", ""), content=figure.get("content", ""))
    return [(name, values.get(name) or "") for name in LEVEL_PARTS if (values.get(name) or "").strip()]


def split_levels(markdown, sections=None):
    """page.md 를 위에서부터 ("main", 글, 시작 줄) 과 ("levels", 블록, 울타리 줄) 로 나눔. 블록은 _levels_block 결과이고
    sections(meta.json 의 {키: 단원 제목})를 주면 블록에 "unit"(단원 키)과 "step"(parse_page 와 같은 단계 번호)을 더함.
    본문 글에는 다른 울타리가 그대로 남음."""
    by_title = {title: key for key, title in (sections or {}).items()}
    out, text, start = [], [], 1
    fence, body, at = None, [], 0
    unit, step = None, 0
    for no, line in enumerate((markdown or "").replace("\r\n", "\n").split("\n"), 1):
        found = FENCE.match(line)
        if fence == "ai-levels":
            if found and not found.group(2):
                block = _levels_block("\n".join(body))
                if sections is not None:
                    block.update(unit=unit, step=step)
                out.append(("levels", block, at))
                fence, start = None, no + 1
            else:
                body.append(line)
            continue
        if fence is None and found and found.group(2) == "ai-levels":
            if text:
                out.append(("main", "\n".join(text), start))
            text, fence, body, at = [], "ai-levels", [], no
            continue
        text.append(line)
        if found:
            fence = found.group(2) or "code" if fence is None else (None if not found.group(2) else fence)
        elif fence is None and line.startswith("## "):
            unit, step = by_title.get(line[3:].strip()), 0
        elif fence is None and line.startswith("### ") and scope_of(line[4:].strip()) != "trend":
            step += 1
    if fence == "ai-levels":
        block = {"kind": "levels", "error": "울타리가 닫히지 않았습니다."}
        if sections is not None:
            block.update(unit=unit, step=step)
        out.append(("levels", block, at))
    elif text:
        out.append(("main", "\n".join(text), start))
    return out


def parse_blocks(lines, folder=None):
    """단계 줄을 위에서 아래로 블록 목록으로. 글(text)은 <!-- facts --> 줄을 지운 마크다운, figure 는 figure_block,
    ai-* 는 JSON 을 읽은 dict(kind 는 guess·reveal·recall·why·diff·rotate·memo·trend·levels, levels 는 _levels_block 꼴).
    JSON 이 깨졌거나 이름을 모르는 블록은 error 키를 가짐."""
    blocks, text, fence, body = [], [], None, []

    def flush():
        joined = strip_marks("\n".join(text)).strip("\n")
        if joined.strip():
            blocks.append({"kind": "text", "markdown": joined})
        del text[:]

    for line in lines:
        found = FENCE.match(line)
        if fence is None:
            if found and found.group(2) and (found.group(2) == "figure" or found.group(2).startswith("ai-")):
                flush()
                fence, body = found.group(2), []
                continue
            if found and found.group(2):
                fence, body = "code", [line]
                continue
            text.append(line)
            continue
        if found and not found.group(2):
            if fence == "code":
                text.extend(body + [line])
            elif fence == "figure":
                blocks.append(figure_block(body, folder))
            elif fence not in BLOCK_KINDS:  # 이름을 잘못 쓴 블록이 정답째 코드로 보이지 않게 함
                blocks.append({"kind": fence, "error": "모르는 블록 이름입니다: %s" % fence})
            elif fence == "ai-levels":
                blocks.append(_levels_block("\n".join(body), folder))
            elif fence == "ai-formula":
                blocks.append(_formula_block("\n".join(body), folder))
            else:
                blocks.append(_json_block(BLOCK_KINDS[fence], "\n".join(body)))
            fence, body = None, []
            continue
        body.append(line)
    if fence == "code":
        text.extend(body)
    elif fence is not None:
        blocks.append({"kind": BLOCK_KINDS.get(fence, fence), "error": "울타리가 닫히지 않았습니다."})
    flush()
    return blocks


def parse_page(markdown, sections, folder=None):
    """page.md 를 {"title", "intro", "units": {키: 단원}, "order": [키], "extra": [(제목, 글)]} 로. 단원은 {"key", "title",
    "lead"(H2 바로 밑 글), "steps": [단계]}, 단계는 {"no", "title", "scope", "facts", "markdown", "blocks", "line"}.
    sections 는 meta.json 의 {키: 단원 제목}. sections 에 없는 H2(그림 출처 등)는 extra 로 감."""
    by_title = {title: key for key, title in sections.items()}
    title, intro, units, order, extra = "", [], {}, [], []
    unit, step, fence = None, None, False
    for no, line in enumerate((markdown or "").replace("\r\n", "\n").split("\n"), 1):
        mark = FENCE.match(line)
        if mark:
            if not fence:
                fence = True
            elif not mark.group(2):
                fence = False
        elif not fence:
            if line.startswith("# ") and not title:
                title = line[2:].strip()
                continue
            if line.startswith("## "):
                head = line[3:].strip()
                key = by_title.get(head)
                if key is None:
                    unit, step = None, None
                    extra.append([head, []])
                else:
                    unit = {"key": key, "title": head, "lead": [], "steps": [], "line": no}
                    units[key], step = unit, None
                    order.append(key)
                continue
            if line.startswith("### ") and unit is not None:
                head = line[4:].strip()
                step = {"title": head, "scope": scope_of(head), "lines": [], "line": no}
                unit["steps"].append(step)
                continue
        if step is not None:
            step["lines"].append(line)
        elif unit is not None:
            unit["lead"].append(line)
        elif extra:
            extra[-1][1].append(line)
        else:
            intro.append(line)
    for unit in units.values():
        no = 0
        for step in unit["steps"]:
            if step["scope"] != "trend":
                no += 1
            step["no"] = no if step["scope"] != "trend" else None
            step["facts"] = facts_of(step["lines"])
            step["markdown"] = strip_marks("\n".join(step["lines"])).strip("\n")
            step["blocks"] = parse_blocks(step.pop("lines"), folder)
        unit["lead"] = "\n".join(unit["lead"]).strip()
    return {"title": title, "intro": strip_marks("\n".join(intro)).strip(), "units": units, "order": order,
            "extra": [(head, "\n".join(lines).strip()) for head, lines in extra]}


def load_note(page, root=None):
    """출제된 학습 노트. 웹 키(title, defines, needs, sections, sources) + lesson, credits, unit_meta, 그리고 parse_page 결과.
    meta.json 의 units 가 있으면 그 단원만 공개(visible)."""
    entry = {"id": page["id"], "title": page.get("title", "")}
    try:
        loaded = webbank.load_page(entry, root or AI_DIR)
    except webbank.BankError as error:
        raise AiBankError(str(error))
    pdir = loaded["dir"]
    meta = _read_json(os.path.join(pdir, "meta.json"), "%s/meta.json" % page["id"])
    try:
        unit_meta = {str(k): dict(v or {}) for k, v in (meta.get("units") or {}).items()}
    except (TypeError, ValueError, AttributeError) as error:
        raise AiBankError("%s/meta.json 의 units 형식이 맞지 않습니다: %s" % (page["id"], error))
    parsed = parse_page(loaded["markdown"], loaded["sections"], pdir)
    visible = [key for key in parsed["order"] if not unit_meta or key in unit_meta]
    note = dict(loaded, lesson=str(meta.get("lesson", "")), credits=list(meta.get("credits") or []), unit_meta=unit_meta,
                visible=visible, **parsed)
    return note


def number_blanks(stem, code=False):
    """빈칸이 둘 이상이면 코드 블록 밖의 ____ 앞에 ①② 번호를 붙인 지문. 코드 블록 안 빈칸은 화면의 CodeSlots 가 그림.
    code 가 참이면 코드 블록 안 빈칸에도 번호를 붙임(오답 노트 HTML 처럼 CodeSlots 없이 지문을 그릴 때)."""
    count = len(BLANK.findall(stem or ""))
    if count < 2:
        return stem
    out, fence, n = [], False, 0

    def mark(found):
        nonlocal n
        n += 1
        return (NUMBERS[n - 1] if n <= len(NUMBERS) else "(%d)" % n) + found.group(0)

    for line in (stem or "").split("\n"):
        if FENCE.match(line):
            fence = not fence
            out.append(line)
            continue
        if fence and not code:
            n += len(BLANK.findall(line))
            out.append(line)
            continue
        out.append(BLANK.sub(mark, line))
    return "\n".join(out)


def blanks_in_code(stem):
    """지문의 빈칸 가운데 코드 울타리 안에 있는 것이 있는지."""
    fence = False
    for line in (stem or "").split("\n"):
        if FENCE.match(line):
            fence = not fence
        elif fence and BLANK.search(line):
            return True
    return False


# 문항 묶음

def _source_hash(path):
    """저장소 서명처럼 UTF-8 텍스트의 줄바꿈을 LF로 맞춰 해시를 구함."""
    try:
        with open(path, encoding="utf-8") as source:
            return hashlib.sha256(source.read().encode("utf-8")).hexdigest()
    except FileNotFoundError:
        return None


def generation_source(spec):
    """로드한 소스와 실행할 공용 함수의 스냅샷을 사용함. 디스크의 새 파일을 다시 읽지 않음."""
    source = copy.deepcopy(getattr(spec, "collection_source", None))
    if source is not None:
        base = genlib.bases().get(spec.meta.get("base"))
        source["source_hashes"]["common"] = getattr(base, "collection_source_hash", None)
        source["version_hash"] = digest({"id": spec.id, "metadata_hash": spec.collection_metadata_hash,
                                         "sources": source["source_hashes"]})
    return source


def load_items(lesson, root=None, with_gens=True):
    """문항 묶음 ai/items/<id>/ 을 읽음. {"dir", "meta", "items", "topics", "facts": {id: 사실}, "errata": {id: 오류},
    "review"(글 또는 None), "gens": [GenSpec], "sources"}. 봉인과 평문 작업본은 webprep.bank.load_secrets 규칙(평문이 이김)."""
    idir = items_dir(lesson["id"], root)
    meta = _read_json(os.path.join(idir, "meta.json"), "%s/meta.json" % lesson["id"])
    try:
        secrets = webbank.load_secrets(idir)
    except webbank.BankError as error:
        raise AiBankError("%s: %s" % (lesson["id"], error))
    out = {"dir": idir, "meta": meta, "items": [], "topics": [], "facts": {}, "errata": {}, "review": secrets.get("review.json"),
           "gens": [], "sources": {}}
    try:
        if "items.json" in secrets:
            out["items"] = list(json.loads(secrets["items.json"]).get("items") or [])
        if "statements.json" in secrets:
            out["topics"] = list(json.loads(secrets["statements.json"]).get("topics") or [])
        if "facts.json" in secrets:
            facts = json.loads(secrets["facts.json"])
            out["facts"] = {str(f["id"]): f for f in facts.get("facts") or []}
            out["errata"] = {str(e["id"]): e for e in facts.get("errata") or []}
            out["sources"] = dict(facts.get("sources") or {})
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise AiBankError("%s 의 봉인 안 JSON 을 읽을 수 없습니다: %s" % (lesson["id"], error))
    if with_gens:
        try:
            path = os.path.join(idir, "gens.py")
            source_hash = _source_hash(path)
            out["gens"] = genlib.load_module(path, "ai_gens_%s" % lesson["id"])
            if source_hash != _source_hash(path):
                raise genlib.GenError("생성기를 읽는 동안 파일이 바뀌었습니다.")
            for spec in out["gens"]:
                try:
                    generation.validate_declaration(spec.meta)
                    base = genlib.bases().get(spec.meta.get("base"))
                    hashes = {"generator": source_hash, "common": getattr(base, "collection_source_hash", None),
                              "runtime": genlib.RUNTIME_SOURCE_HASH}
                    spec.collection_metadata_hash = digest(spec.meta)
                    spec.collection_source = {
                        "generator_id": spec.id, "template_id": spec.meta.get("template_id") or spec.meta.get("base") or spec.id,
                        "template_revision": spec.meta.get("template_revision"), "source_hashes": hashes,
                        "display_params": copy.deepcopy(spec.meta.get("display_params"))}
                    if spec.meta.get("display_params") is not None:
                        # 선언한 키·값은 시드 0으로 미리 확인하며 실제 생성 시에도 다시 검증함.
                        try:
                            generation.capture(generation_source(spec), genlib.run(spec, 0), {})
                        except Exception as error:  # noqa: BLE001 - 생성기의 사전 실행 오류를 차시 안내로 바꿈
                            raise AiBankError("%s/%s: %s" % (lesson["id"], spec.id, error)) from error
                except (ValueError, TypeError, genlib.GenError) as error:
                    raise AiBankError("%s/%s: %s" % (lesson["id"], spec.id, error)) from error
        except (genlib.GenError, OSError, UnicodeError) as error:
            raise AiBankError("%s: %s" % (lesson["id"], error))
    return out


def load_common(root=None):
    """공용 생성기 ai/items/common/gens.py 를 읽어 @base 를 등록함. 없으면 아무것도 안 함."""
    path = os.path.join(root or AI_DIR, "items", "common", "gens.py")
    try:
        source_hash = _source_hash(path)
        previous = genlib.bases()
        specs = genlib.load_module(path, "ai_gens_common")
        if source_hash != _source_hash(path):
            raise genlib.GenError("공용 생성기를 읽는 동안 파일이 바뀌었습니다.")
        for name, fn in genlib.bases().items():
            if fn is not previous.get(name):
                fn.collection_source_hash = source_hash
        return specs
    except (genlib.GenError, OSError, UnicodeError) as error:
        raise AiBankError("common: %s" % error)


def cards_of(lesson, data):
    """문항 묶음을 카드 목록으로. 카드는 {"id", "kind": blank|choice|stmt|gen, "lesson", "unit", "step", "facts", "core",
    "prio", "family", "confuse", "level", "tags", "deep", "errata", "ref", "order", 원본("item"·"stmt"·"topic"·"gen")}."""
    cards = []

    def add(cid, kind, source, **extra):
        card = {"id": cid, "kind": kind, "lesson": lesson["id"], "unit": str(source.get("unit", "")),
                "step": source.get("step"), "facts": _list(source.get("facts")), "core": bool(source.get("core")),
                "prio": int(source.get("prio") or 2), "family": str(source.get("family") or cid),
                "confuse": _list(source.get("confuse")), "level": int(source.get("level") or 2), "tags": _list(source.get("tags")),
                "deep": bool(source.get("deep")), "errata": _list(source.get("errata")), "ref": _list(source.get("ref")),
                "order": len(cards)}
        card.update(extra)
        cards.append(card)

    for item in data["items"]:
        kind = item.get("kind")
        if kind in ("blank", "choice"):
            add(str(item["id"]), kind, item, item=item)
    for topic in data["topics"]:
        for statement in topic.get("statements") or []:
            source = dict(topic, **{k: v for k, v in statement.items() if k in ("unit", "facts", "core", "family", "confuse", "step",
                                                                                   "errata", "ref", "deep", "prio", "level")})
            source.setdefault("step", topic.get("step"))
            add(str(statement["id"]), "stmt", source, stmt=statement, topic=topic)
    for spec in data["gens"]:
        add(spec.id, "gen", spec.meta, gen=spec, family=str(spec.meta.get("family") or spec.id))
    return cards


def pattern_gen_cards(group, data, units):
    """공개된 상황별 코드 단원의 생성 문항에 권장 차시와 이름을 붙임."""
    source = {"items": [], "topics": [], "gens": data["gens"]}
    cards = cards_of({"id": group["id"]}, source)
    return [dict(card, after=units[card["unit"]]["after"], name=units[card["unit"]]["name"])
            for card in cards if card["unit"] in units]
