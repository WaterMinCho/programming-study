# -*- coding: utf-8 -*-
"""웹 면접 준비 은행(web/) 읽기와 봉인 풀기.

미션·주제·페이지가 "출제됨"이라는 것은 그 폴더에 meta.json 이 있다는 것뿐임(알고리즘 여행과 같은 규칙). 공개 파일
(index.json, meta.json, brief.md, app/, page.md, kit/)은 여기서 읽어 서비스가 쓸 모양으로 정리하고, 비밀 파일
(work/ 아래 단계 요구·검사·모범 답안·해설·꼬리 질문·사슬 본문)은 sealed.json 에서 풀되 평문 작업본이 있으면 평문이
이김. 봉인은 study.seal_blob 과 같은 base64+zlib 이라 우연히 답을 보지 않게 가리는 장치임. 경로 상수는 import 할 때
복사하지 말고 bank.BANK_DIR 처럼 쓸 때 읽음(테스트가 바꿔 끼움).
"""
import json
import os
import re
import zlib

import study

BANK_DIR = os.path.join(study.ROOT, "web")
INDEX_NAME = "index.json"
TERMS_NAME = "terms.json"
SEALED_NAME = "sealed.json"
WORK_DIR = "work"
KIT_DIR = "kit"
APP_DIR = "app"
SELF_CHECK = "self_check.md"
FOLDERS = {"mission": "missions", "topic": "drills", "page": "learn"}
SAFE_ID = re.compile(r"[a-z][a-z0-9]{1,15}\Z")
CHAIN_ID = re.compile(r"[A-Za-z0-9]+-[A-Z]\Z")
STEP_HEAD = re.compile(r"##\s+(\d+)\.\s*(.*?)\s*\Z")
SUB_HEAD = re.compile(r"###\s+(.*?)\s*\Z")
CHAIN_HEAD = re.compile(r"##\s+(\S+)\s*\Z")
QUESTION_HEAD = re.compile(r"###\s+Q(\d+)\.\s*(.*?)\s*\Z")
ITEM = re.compile(r"[-*]\s+\[(필수|보충)\]\s*(.*?)\s*\Z")
BULLET = re.compile(r"[-*]\s+(.*?)\s*\Z")
STUCK = re.compile(r">\s*막히면:\s*(.*?)\s*\Z")
TEST_NAME = re.compile(r"""(?:^|\n)\s*(?:test|it)\(\s*(['"`])((?:(?!\1).)*)\1""")
TEXT_EXTS = (".md", ".ts", ".tsx", ".js", ".jsx", ".json", ".css", ".html", ".mts", ".txt")


class BankError(Exception):
    """은행 파일을 읽지 못함. 문구는 화면 위 알림이나 터미널에 그대로 보여 줌."""


def _why(error):
    if isinstance(error, KeyError):
        return "%s 키가 없음" % error
    return str(error) or type(error).__name__


def _read_json(path, shown):
    try:
        return study.read_json(path)
    except (OSError, ValueError) as error:
        raise BankError("%s 을 읽을 수 없습니다: %s" % (shown, error))


def _read_text(path, shown):
    try:
        return study.read_text(path)
    except (OSError, ValueError) as error:
        raise BankError("%s 을 읽을 수 없습니다: %s" % (shown, error))


def _entry(item, keys):
    out = {"id": str(item["id"]), "title": str(item["title"])}
    if not SAFE_ID.match(out["id"]):
        raise ValueError("id %r" % out["id"])
    for key in keys:
        out[key] = int(item[key]) if key == "no" else str(item.get(key, ""))
    return out


def read_index(root=None):
    """index.json 을 {"missions", "topics", "pages", "order"} 로. 빠진 키는 기본값으로 채움."""
    root = root or BANK_DIR
    data = _read_json(os.path.join(root, INDEX_NAME), INDEX_NAME)
    try:
        out = {"missions": [_entry(item, ("no", "level")) for item in data["missions"]],
               "topics": [_entry(item, ("no",)) for item in data["topics"]],
               "pages": [_entry(item, ()) for item in data["pages"]],
               "order": [str(iid) for iid in data.get("order", [])]}
    except (KeyError, TypeError, ValueError) as error:
        raise BankError("%s 의 형식이 맞지 않습니다: %s" % (INDEX_NAME, _why(error)))
    return out


def read_terms(root=None):
    """terms.json 을 {"known": [...], "terms": [{"term", "also", "page"}]} 로. 없으면 빈 목록."""
    path = os.path.join(root or BANK_DIR, TERMS_NAME)
    if not os.path.isfile(path):
        return {"known": [], "terms": []}
    data = _read_json(path, TERMS_NAME)
    try:
        terms = [{"term": str(t["term"]), "also": [str(a) for a in t.get("also", [])], "page": str(t.get("page", ""))}
                 for t in data.get("terms", [])]
        return {"known": [str(k) for k in data.get("known", [])], "terms": terms}
    except (KeyError, TypeError, ValueError) as error:
        raise BankError("%s 의 형식이 맞지 않습니다: %s" % (TERMS_NAME, _why(error)))


def item_dir(kind, iid, root=None):
    return os.path.join(root or BANK_DIR, FOLDERS[kind], iid)


def is_ready(kind, iid, root=None):
    return os.path.isfile(os.path.join(item_dir(kind, iid, root), "meta.json"))


def _str_list(value):
    return [str(v) for v in (value or [])]


def load_mission(entry, root=None):
    """출제된 미션의 공개 파일을 읽어 entry 에 더함. 더하는 키: dir, app_dir, brief, prep_min, live_min, steps(단계별
    목표 분, 0단계부터), hidden, pages, chains, needs, defines_inline, sources."""
    mdir = item_dir("mission", entry["id"], root)
    meta = _read_json(os.path.join(mdir, "meta.json"), "%s/meta.json" % entry["id"])
    brief = _read_text(os.path.join(mdir, "brief.md"), "%s/brief.md" % entry["id"])
    try:
        steps = [int(minutes) for minutes in meta["steps"]]
        if not steps or any(m < 0 for m in steps):
            raise ValueError("steps 는 0단계부터의 목표 분 목록이어야 함")
        mission = dict(entry, dir=mdir, app_dir=os.path.join(mdir, APP_DIR), brief=brief,
                       title=str(meta.get("title", entry["title"])), level=str(meta.get("level", entry.get("level", ""))),
                       prep_min=int(meta["prep_min"]), live_min=int(meta["live_min"]), steps=steps,
                       hidden=bool(meta.get("hidden", False)), pages=_str_list(meta.get("pages")),
                       chains=_str_list(meta.get("chains")), needs=_str_list(meta.get("needs")),
                       defines_inline=_str_list(meta.get("defines_inline")), sources=list(meta.get("sources") or []))
    except (KeyError, TypeError, ValueError) as error:
        raise BankError("%s/meta.json 의 형식이 맞지 않습니다: %s" % (entry["id"], _why(error)))
    if not os.path.isdir(mission["app_dir"]):
        raise BankError("%s 에 템플릿 폴더 app/ 이 없습니다." % entry["id"])
    return mission


def load_topic(entry, root=None):
    """출제된 주제의 meta.json 을 읽어 entry 에 더함. 더하는 키: dir, page, local, chains(id, title, goal, secs,
    missions, section, defines_inline). local 이 참이면 그 주제의 사슬 기록은 저장소에 올리지 않고 ~/.rokey-study/web 에 둠."""
    tdir = item_dir("topic", entry["id"], root)
    meta = _read_json(os.path.join(tdir, "meta.json"), "%s/meta.json" % entry["id"])
    try:
        chains = []
        for item in meta["chains"]:
            cid = str(item["id"])
            if not CHAIN_ID.match(cid):
                raise ValueError("사슬 id %r" % cid)
            chains.append({"id": cid, "title": str(item["title"]), "goal": str(item.get("goal", "")),
                           "secs": int(item.get("secs", 60)), "missions": _str_list(item.get("missions")),
                           "section": str(item.get("section", "")), "defines_inline": _str_list(item.get("defines_inline")),
                           "topic": entry["id"]})
        topic = dict(entry, dir=tdir, title=str(meta.get("title", entry["title"])), page=str(meta.get("page", "")),
                     local=bool(meta.get("local", False)), chains=chains)
    except (KeyError, TypeError, ValueError) as error:
        raise BankError("%s/meta.json 의 형식이 맞지 않습니다: %s" % (entry["id"], _why(error)))
    ids = [c["id"] for c in chains]
    if len(set(ids)) != len(ids):
        raise BankError("%s/meta.json 에 같은 사슬 id 가 두 번 있습니다." % entry["id"])
    return topic


def load_page(entry, root=None):
    """출제된 학습 페이지. 더하는 키: dir, markdown, defines, needs, sections, outputs, sources."""
    pdir = item_dir("page", entry["id"], root)
    meta = _read_json(os.path.join(pdir, "meta.json"), "%s/meta.json" % entry["id"])
    markdown = _read_text(os.path.join(pdir, "page.md"), "%s/page.md" % entry["id"])
    try:
        sections = {str(k): str(v) for k, v in (meta.get("sections") or {}).items()}
        page = dict(entry, dir=pdir, markdown=markdown, title=str(meta.get("title", entry["title"])),
                    defines=_str_list(meta.get("defines")), needs=_str_list(meta.get("needs")), sections=sections,
                    outputs=list(meta.get("outputs") or []), sources=list(meta.get("sources") or []))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise BankError("%s/meta.json 의 형식이 맞지 않습니다: %s" % (entry["id"], _why(error)))
    return page


# 공통 도우미(kit)

def kit_files(root=None):
    """web/kit/ 의 검사 도우미 파일을 {상대 경로: 글} 로. self_check.md 는 뺌. 폴더가 없으면 빈 dict."""
    kdir = os.path.join(root or BANK_DIR, KIT_DIR)
    files = {}
    for folder, _, names in os.walk(kdir):
        for name in sorted(names):
            if name == SELF_CHECK or not name.endswith(TEXT_EXTS):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, kdir).replace(os.sep, "/")
            files[rel] = _read_text(path, "kit/" + rel)
    return files


def self_check(root=None):
    """모든 미션 공통 점검 항목(kit/self_check.md 의 불릿). 없으면 빈 목록."""
    path = os.path.join(root or BANK_DIR, KIT_DIR, SELF_CHECK)
    return parse_bullets(_read_text(path, "kit/" + SELF_CHECK)) if os.path.isfile(path) else []


# 비밀 파일과 봉인

def plain_secret_paths(idir):
    """work/ 아래 평문 파일의 상대 경로(work/ 기준, 슬래시 구분) 목록."""
    wdir = os.path.join(idir, WORK_DIR)
    rels = []
    for folder, dirs, names in os.walk(wdir):
        dirs[:] = sorted(d for d in dirs if d != "node_modules")
        for name in sorted(names):
            if name.startswith("."):
                continue
            rels.append(os.path.relpath(os.path.join(folder, name), wdir).replace(os.sep, "/"))
    return sorted(rels)


def load_secrets(idir):
    """비밀 파일을 {work/ 기준 상대 경로: 내용} 으로. sealed.json 의 blob 을 풀고, 평문 작업본이 있으면 평문이 이김."""
    files = {}
    sealed = os.path.join(idir, SEALED_NAME)
    if os.path.isfile(sealed):
        try:
            blob = study.unseal_blob(study.read_json(sealed)["blob"])
        except (OSError, ValueError, KeyError, TypeError, zlib.error) as error:
            raise BankError("%s 을 풀 수 없습니다: %s" % (SEALED_NAME, error))
        if not isinstance(blob, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in blob.items()):
            raise BankError("%s 의 묶음이 {경로: 글} 꼴이 아닙니다." % SEALED_NAME)
        files.update(blob)
    for rel in plain_secret_paths(idir):
        files[rel] = _read_text(os.path.join(idir, WORK_DIR, *rel.split("/")), "%s/%s" % (WORK_DIR, rel))
    return files


def seal_text(files, note):
    """비밀 파일 묶음을 sealed.json 에 쓸 글로."""
    return json.dumps({"note": note, "blob": study.seal_blob(files)}, ensure_ascii=False, indent=1) + "\n"


def check_files(secrets):
    """단계 검사 파일을 {단계 번호: 글} 로. hidden.test.tsx 는 키 "hidden"."""
    out = {}
    for rel, text in secrets.items():
        found = re.match(r"checks/step(\d+)\.test\.tsx\Z", rel)
        if found:
            out[int(found.group(1))] = text
        elif rel == "checks/hidden.test.tsx":
            out["hidden"] = text
    return out


def check_ids(text):
    """검사 파일의 테스트 이름에서 검사 id("1a", "3b")만 뽑음. 이름의 첫 낱말이 id 임."""
    ids = []
    for _, title in TEST_NAME.findall(text):
        first = title.split(" ", 1)[0]
        if first and first not in ids:
            ids.append(first)
    return ids


def solution_files(secrets, upto):
    """solution/step1 … step<upto> 를 차례로 덮은 {app 기준 상대 경로: 글}. 뒤 단계가 이김."""
    out = {}
    for step in range(1, upto + 1):
        prefix = "solution/step%d/" % step
        for rel, text in secrets.items():
            if rel.startswith(prefix):
                out[rel[len(prefix):]] = text
    return out


# 글 파서

def parse_bullets(text):
    items = []
    for line in (text or "").splitlines():
        found = BULLET.match(line.strip())
        if found:
            items.append(found.group(1))
    return items


def _strip_quote(lines):
    return "\n".join(line.strip()[1:].strip() for line in lines).strip()


def _sections(lines):
    """`### 제목` 으로 나눈 [(제목, 줄들)]. 첫 제목 앞의 줄은 제목 None."""
    out, current = [(None, [])], None
    for line in lines:
        found = SUB_HEAD.match(line.strip())
        if found and not line.startswith("####"):
            current = (found.group(1), [])
            out.append(current)
        else:
            out[-1][1].append(line)
    return out


def _request(lines):
    """인용 줄(> …)을 요구로, 그 뒤 문단을 설명으로."""
    quote, note, seen = [], [], False
    for line in lines:
        if line.strip().startswith(">"):
            quote.append(line)
            seen = True
        elif seen:
            note.append(line)
    return _strip_quote(quote), "\n".join(note).strip()


def parse_items(lines):
    """`- [필수] …`, `- [보충] …` 목록과 「막히면」 줄. [{"need", "text"}], stuck."""
    items, stuck = [], ""
    for line in lines:
        found = ITEM.match(line.strip())
        if found:
            items.append({"need": found.group(1) == "필수", "text": found.group(2)})
            continue
        found = STUCK.match(line.strip())
        if found:
            stuck = found.group(1)
    return items, stuck


def parse_steps(text):
    """work/steps.md 를 단계 목록으로. 단계마다 no, title, request, note, self(0단계 점검 항목), checks, hints,
    after({"ask", "items"} 또는 None). 번호 순으로 정렬함."""
    steps, current = [], None
    for line in (text or "").splitlines():
        found = STEP_HEAD.match(line.strip())
        if found and not line.startswith("###"):
            current = {"no": int(found.group(1)), "title": found.group(2), "lines": []}
            steps.append(current)
        elif current is not None:
            current["lines"].append(line)
    out = []
    for step in steps:
        row = {"no": step["no"], "title": step["title"], "request": "", "note": "", "self": [], "checks": [],
               "hints": [], "after": None}
        for head, lines in _sections(step["lines"]):
            if head == "요구":
                row["request"], row["note"] = _request(lines)
            elif head == "점검":
                row["self"] = parse_bullets("\n".join(lines))
            elif head == "검사":
                row["checks"] = parse_bullets("\n".join(lines))
            elif head == "힌트":
                row["hints"] = parse_bullets("\n".join(lines))
            elif head == "통과 뒤 질문":
                ask, _ = _request(lines)
                items, _ = parse_items(lines)
                row["after"] = {"ask": ask, "items": items}
        out.append(row)
    out.sort(key=lambda r: r["no"])
    return out


def _intro(lines):
    """사슬 소개 문단과 면접관이 보여 주는 코드 블록."""
    intro, code, fence = [], [], False
    for line in lines:
        if line.strip().startswith("```"):
            fence = not fence
            code.append(line)
        elif fence:
            code.append(line)
        else:
            intro.append(line)
    return "\n".join(intro).strip(), "\n".join(code).strip()


def parse_chains(text):
    """work/chains.md(또는 followups.md)를 {사슬 id: 사슬} 로. 사슬은 id, intro, code, questions(no, ask, items, stuck),
    weak({"quote", "why"} 또는 None), follow(이어 말하기 글)."""
    chains, current = {}, None
    for line in (text or "").splitlines():
        found = CHAIN_HEAD.match(line.strip())
        if found and not line.startswith("###") and CHAIN_ID.match(found.group(1)):
            current = {"id": found.group(1), "lines": []}
            chains[found.group(1)] = current
        elif current is not None:
            current["lines"].append(line)
    out = {}
    for cid, chain in chains.items():
        row = {"id": cid, "intro": "", "code": "", "questions": [], "weak": None, "follow": ""}
        for head, lines in _sections(chain["lines"]):
            if head is None:
                row["intro"], row["code"] = _intro(lines)
                continue
            question = QUESTION_HEAD.match("### " + head)
            if question:
                items, stuck = parse_items(lines)
                row["questions"].append({"no": int(question.group(1)), "ask": question.group(2), "items": items,
                                         "stuck": stuck})
            elif head == "약한 답":
                quote, why = _request(lines)
                row["weak"] = {"quote": quote, "why": why}
            elif head == "이어 말하기":
                row["follow"] = _request(lines)[0]
        row["questions"].sort(key=lambda q: q["no"])
        out[cid] = row
    return out


def strip_figures(markdown):
    """학습 페이지의 figure 블록을 캡션 한 줄로 바꿈(터미널 출력용). 그림 파일 자리와 프레임 설명은 뺌."""
    out, inside = [], False
    for line in markdown.splitlines():
        if line.strip() == "```figure":
            inside = True
            continue
        if inside:
            if line.strip() == "```":
                inside = False
            elif line.startswith("캡션:"):
                out.append("[그림] " + line[len("캡션:"):].strip())
            continue
        out.append(line)
    return "\n".join(out)
