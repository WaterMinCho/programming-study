#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 면접 준비 은행(web/) 검증. 실패가 하나라도 있으면 1 로 끝남.

  python tools/verify_web.py [w03 t03 l03 ...]        형식부터 그림까지 모두 봄(대상이 없으면 출제된 항목 전부)
  python tools/verify_web.py --pages                  학습 페이지만(형식, 글, 출력 순서 문제, 그림)
  python tools/verify_web.py w03 --runs 3             반복 안정성 검사를 3번만 돌림(기본 5번)
  python tools/verify_web.py w03 --sign --writer W --resolver R --reviewer V [--finding 글 ...]
                                                      검증을 통과하면 review.json 을 씀(미션·주제는 work/ 안, 페이지는 폴더에)
  python tools/verify_web.py --require-review         검토 서명이 없거나 서명 뒤에 바뀐 파일이 있으면 실패

그 밖의 옵션: --bank DIR(기본 web/), --root DIR(node_modules 와 .web-check 를 두는 저장소 맨 위, 기본은 이 저장소).
단계 검사는 학습자 화면과 같은 webprep.checks 로 돌림. 템플릿과 단계별 모범 답안은 <root>/.web-check/_verify_<미션>/ 에
잠깐 만들었다가 지움. 단계 번호와 내용은 아래 STEP_NAMES 와 각 check_ 함수에 있음. 말투는 저장소의 tools/check_style.py 로만
보고, 바깥 말투 검사기와 맥락(낱말) 검사는 tools/web_lint.py 가 맡음.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from journey import node as node_finder  # noqa: E402
from tools import check_style, verify_journey, web_lint  # noqa: E402
from tools.journey_art import KB  # noqa: E402
from tools.web_art import LIMITS, owner_of  # noqa: E402
from webprep import bank, checks, stack  # noqa: E402

STEP_NAMES = {1: "형식", 2: "비밀 파일", 3: "글", 4: "템플릿", 5: "단계 답안", 6: "최종 답안", 7: "반복", 8: "시간",
              9: "페이지 출력", 10: "그림", 11: "검토 서명"}
RUN_STEPS = (4, 5, 6, 7, 8)  # Node 와 설치된 검사 도구가 있어야 도는 단계
LEVELS = ("워밍업", "기본", "응용", "실전")
EXPLAIN_HEADS = ("면접관은 무엇을 보았나요", "모범 답안", "단계마다 무엇을 바꿨나요")
EXPLAIN_OPTIONAL = ("고치기 전 코드",)
APP_SCRIPTS = {"dev": "vite", "test": "vitest run"}  # 꼭 있어야 하는 scripts
APP_OPTIONAL_SCRIPTS = {"typecheck": "tsc --noEmit"}  # 두어도 되는 scripts(typescript 는 1차 스택에 없음)
APP_KEYS = ("name", "private", "type", "scripts")
APP_FILES = ("package.json", "vite.config.ts", "tsconfig.json", "index.html")
APP_LIMIT = 200 * KB
SKIP_DIRS = ("node_modules", "dist", ".git")
TEST_FILE = re.compile(r"\.test\.(ts|tsx|js|jsx)\Z")
EXTERNAL_URL = re.compile(r"https?://(?!localhost|127\.0\.0\.1)[^\s'\")]+")
COMPANY = re.compile(r"토스|카카오|네이버|쿠팡|당근|배민|우아한|\b(toss|kakao|naver|coupang|daangn|baemin|woowa)\b", re.I)
RELATIVE_IMPORT = re.compile(r"""(?:from|import)\s*\(?\s*['"](\.{1,2}/[^'"]*)['"]""")
KIT_IMPORT = re.compile(r"""['"]@kit/([^'"]+)['"]""")
CHECK_ID = re.compile(r"(\d+)([a-z])\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
QUESTIONS = (3, 5)
NEED_ITEMS = (1, 3)
EXTRA_ITEMS = 3
TEMPLATE_TESTS = (1, 3)
TARGET_SHARE = 0.9
DEFAULT_RUNS = 5
ALL_LIMIT_MS = 15000
FILE_LIMIT_MS = 5000
RUN_LIMIT_S = 60
NODE_LIMIT_S = 20
OUTPUT_LANGS = ("js", "javascript")
SHOWN = 120
_run = subprocess.run  # 테스트가 가짜로 바꿔 끼움


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def clip(text, limit=SHOWN):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def listing(items, most=6):
    items = [str(i) for i in items]
    text = ", ".join(items[:most])
    if len(items) > most:
        text += " 외 %d개" % (len(items) - most)
    return text


def walk_files(folder, skip=SKIP_DIRS):
    """folder 아래 파일의 (상대 경로, 절대 경로). 숨김 파일과 skip 폴더는 뺌."""
    out = []
    for here, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in skip and not d.startswith("."))
        for name in sorted(names):
            if name.startswith("."):
                continue
            path = os.path.join(here, name)
            out.append((os.path.relpath(path, folder).replace(os.sep, "/"), path))
    return out


def code_blocks(markdown):
    """figure 가 아닌 울타리 코드 블록을 [(언어, 글)] 로(1번부터 셈)."""
    blocks, fence, lang, lines = [], False, "", []
    for line in markdown.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if re.match(r"^(```|~~~)", stripped):
            if fence:
                if lang != "figure":
                    blocks.append((lang, "\n".join(lines)))
                fence, lines = False, []
            else:
                fence, lang = True, stripped.lstrip("`~").strip().lower()
            continue
        if fence:
            lines.append(line)
    return blocks


def figure_blocks(markdown):
    """figure 블록을 [{"line", "file", "caption", "frames": [ms...], "content", "frame_lines"}] 로."""
    out, fence, current = [], False, None
    for no, line in enumerate(markdown.replace("\r\n", "\n").split("\n"), 1):
        stripped = line.strip()
        if re.match(r"^(```|~~~)", stripped):
            if fence:
                fence = False
                if current is not None:
                    out.append(current)
                    current = None
            else:
                fence = True
                if stripped.lstrip("`~").strip().lower() == "figure":
                    current = {"line": no, "file": "", "caption": "", "frames": [], "content": "", "frame_lines": 0, "bad_ms": []}
            continue
        if not fence or current is None:
            continue
        if stripped.startswith("파일:"):
            current["file"] = stripped[len("파일:"):].strip()
        elif stripped.startswith("캡션:"):
            current["caption"] = stripped[len("캡션:"):].strip()
        elif stripped.startswith("내용:"):
            current["content"] = stripped[len("내용:"):].strip()
        elif re.match(r"^\d+\.\s", stripped):
            current["frame_lines"] += 1
            found = re.search(r"\((\d+)\s*ms\)\s*\Z", stripped)
            if found:
                current["frames"].append(int(found.group(1)))
            else:
                current["bad_ms"].append(stripped[:30])
    return out


def headings(markdown):
    out = []
    for line in web_lint.units_of(markdown):
        if line.kind == "heading":
            out.append((line.level, line.text.strip()))
    return out


class Verifier(object):
    def __init__(self, opts, steps=None, out=None):
        self.opts = opts
        self.out = out or sys.stdout
        self.steps = steps
        self.bank = os.path.abspath(opts.bank)
        self.root = os.path.abspath(opts.root or study.ROOT)
        self.runs = max(1, int(opts.runs or DEFAULT_RUNS))
        self.failures = []
        self.warnings = []
        self._headed = set()
        self._node = None
        self._node_looked = False
        self.index = None
        self.pages_by_id = {}
        self.chain_ids = {}
        self.tools = [("check_style", check_style.check)]

    def wants(self, step):
        return self.steps is None or step in self.steps

    # 출력

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

    # Node 와 검사 도구

    def node_path(self, step):
        """웹 트랙의 최소 판(22.12) 이상인 Node. 없으면 한 번만 실패를 적음."""
        if not self._node_looked:
            self._node_looked = True
            found = stack.find_node()
            self._node = found["path"] if found else None
            if not self._node:
                self.fail("node", step, "Node.js %s 이상을 찾지 못해 검사를 돌리지 못했습니다. STUDY_NODE 에 node 경로를 적어 주세요."
                          % stack.node_label())
        return self._node

    def stack_ready(self, label, step):
        if not stack.installed(self.root):
            self.fail(label, step, "검사 도구가 %s 에 설치되어 있지 않습니다. `python study.py web install` 로 설치해 주세요."
                      % os.path.join(study.shown_path(self.root), "node_modules"))
            return False
        return True

    def vitest_env(self):
        env = dict(os.environ)
        env.pop("NODE_OPTIONS", None)
        env["CI"] = "1"
        env["FORCE_COLOR"] = "0"
        return env


# 형식: index.json 과 terms.json

def load_index(v):
    try:
        v.index = bank.read_index(v.bank)
    except bank.BankError as error:
        v.fail("index", 1, str(error))
        return False
    for kind in ("missions", "topics", "pages"):
        entries = v.index[kind]
        ids = [e["id"] for e in entries]
        if len(set(ids)) != len(ids):
            v.fail("index", 1, "%s 에 같은 id 가 두 번 있습니다." % kind)
        if kind != "pages":
            nos = [e["no"] for e in entries]
            if len(set(nos)) != len(nos):
                v.fail("index", 1, "%s 의 no 가 겹칩니다." % kind)
    for entry in v.index["missions"]:
        if entry["level"] not in LEVELS:
            v.fail("index", 1, "미션 %s 의 level 은 %s 가운데 하나여야 합니다: %r" % (entry["id"], ", ".join(LEVELS), entry["level"]))
    known = {e["id"] for kind in ("missions", "topics", "pages") for e in v.index[kind]}
    order = v.index["order"]
    unknown = [iid for iid in order if iid not in known]
    if unknown:
        v.fail("index", 1, "order 에 목록에 없는 id 가 있습니다: %s" % listing(unknown))
    if len(set(order)) != len(order):
        v.fail("index", 1, "order 에 같은 id 가 두 번 있습니다.")
    for kind, folder in bank.FOLDERS.items():
        parent = os.path.join(v.bank, folder)
        if not os.path.isdir(parent):
            continue
        for name in sorted(os.listdir(parent)):
            if os.path.isdir(os.path.join(parent, name)) and not name.startswith(".") and name not in known:
                v.fail("index", 1, "%s/%s 폴더가 index.json 에 없습니다." % (folder, name))
    v.pages_by_id = {e["id"]: e for e in v.index["pages"]}
    for entry in v.index["topics"]:
        if bank.is_ready("topic", entry["id"], v.bank):
            try:
                for chain in bank.load_topic(entry, v.bank)["chains"]:
                    v.chain_ids[chain["id"]] = entry["id"]
            except bank.BankError:
                pass  # 그 주제를 볼 때 실패로 적음
    return True


def check_terms(v):
    try:
        terms = bank.read_terms(v.bank)
    except bank.BankError as error:
        v.fail("terms", 1, str(error))
        return
    seen = set()
    for item in terms["terms"]:
        word = item["term"]
        if word in seen:
            v.fail("terms", 1, "같은 낱말이 두 번 있습니다: %s" % word)
        seen.add(word)
        if word in terms["known"]:
            v.fail("terms", 1, "known 과 terms 양쪽에 있는 낱말: %s" % word)
        pid = item["page"]
        if pid not in v.pages_by_id:
            v.fail("terms", 1, "'%s'의 page %s 가 index.json 의 페이지가 아닙니다." % (word, pid))
            continue
        if bank.is_ready("page", pid, v.bank):
            try:
                defines = bank.load_page(v.pages_by_id[pid], v.bank)["defines"]
            except bank.BankError:
                continue
            if word not in defines:
                v.fail("terms", 1, "'%s'를 소개한다는 페이지 %s 의 defines 에 그 낱말이 없습니다." % (word, pid))


def check_sources(v, label, sources, required=False):
    if not isinstance(sources, list):
        v.fail(label, 1, "sources 는 목록이어야 합니다.")
        return
    if not sources:
        (v.fail if required else v.warn)(label, 1, "sources 가 비어 있습니다. 숫자·기본값·버전에 따라 바뀌는 사실에는 출처를 적습니다.")
        return
    for n, item in enumerate(sources, 1):
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item.get(k) for k in ("what", "url", "checked")):
            v.fail(label, 1, "sources[%d] 는 {what, url, checked} 여야 합니다." % n)
        elif not DATE.match(item["checked"]):
            v.fail(label, 1, "sources[%d].checked 는 YYYY-MM-DD 꼴이어야 합니다: %s" % (n, item["checked"]))


def check_page_ids(v, label, key, ids):
    for pid in ids:
        if pid not in v.pages_by_id:
            v.fail(label, 1, "%s 의 %s 가 index.json 의 페이지가 아닙니다." % (key, pid))
        elif not bank.is_ready("page", pid, v.bank):
            v.warn(label, 1, "%s 의 페이지 %s 가 아직 준비 중입니다." % (key, pid))


# 미션

def check_mission(v, entry):
    mid = entry["id"]
    mdir = bank.item_dir("mission", mid, v.bank)
    v.head(mid, entry["title"])
    try:
        mission = bank.load_mission(entry, v.bank)
        secrets = bank.load_secrets(mdir)
    except bank.BankError as error:
        v.fail(mid, 1, str(error))
        return
    try:
        raw = study.read_json(os.path.join(mdir, "meta.json"))
    except (OSError, ValueError) as error:
        v.fail(mid, 1, "meta.json: %s" % error)
        return
    live = len(mission["steps"]) - 1
    if v.wants(1):
        mission_format(v, mid, mission, raw)
        template_folder(v, mid, mission)
    steps = bank.parse_steps(secrets.get("steps.md", ""))
    if v.wants(2):
        mission_secrets(v, mid, mission, secrets, steps)
    if v.wants(3):
        text_check(v, "mission", entry, mid)
    if v.wants(10):
        figures(v, mid, secrets.get("explain.md", ""), mdir, "mission", mid, ())
    if any(v.wants(step) for step in RUN_STEPS) and not v.failed(mid):
        mission_runs(v, mid, mission, secrets, live)
    review(v, "mission", mid, mission, secrets)


def mission_format(v, mid, mission, raw):
    if raw.get("format") != 1:
        v.fail(mid, 1, "meta.json 의 format 은 1 이어야 합니다.")
    if raw.get("id") != mid:
        v.fail(mid, 1, "meta.json 의 id 가 폴더 이름과 다릅니다: %r" % raw.get("id"))
    if not mission["title"].strip():
        v.fail(mid, 1, "title 이 비어 있습니다.")
    if mission["level"] not in LEVELS:
        v.fail(mid, 1, "level 은 %s 가운데 하나여야 합니다: %r" % (", ".join(LEVELS), mission["level"]))
    if mission["prep_min"] <= 0 or mission["live_min"] <= 0:
        v.fail(mid, 1, "prep_min 과 live_min 은 1 이상이어야 합니다.")
    if len(mission["steps"]) < 2:
        v.fail(mid, 1, "steps 에는 0단계(코드 설명)와 요구 단계 하나 이상이 있어야 합니다.")
    if any(m <= 0 for m in mission["steps"]):
        v.fail(mid, 1, "steps 의 목표 분은 1 이상이어야 합니다.")
    if sum(mission["steps"]) > mission["live_min"] * TARGET_SHARE:
        v.warn(mid, 1, "단계 목표 합계 %d분이 실전 시간 %d분의 %d%% 를 넘습니다(설계 6.5). 실측 뒤 목표를 고치세요."
               % (sum(mission["steps"]), mission["live_min"], TARGET_SHARE * 100))
    if not isinstance(raw.get("hidden", False), bool):
        v.fail(mid, 1, "hidden 은 true 나 false 여야 합니다.")
    check_page_ids(v, mid, "pages", mission["pages"])
    check_page_ids(v, mid, "needs", mission["needs"])
    for cid in mission["chains"]:
        if cid == mid + "-F":
            continue
        if not bank.CHAIN_ID.match(cid):
            v.fail(mid, 1, "chains 의 사슬 id 꼴이 아닙니다: %s" % cid)
        elif cid not in v.chain_ids:
            tid = "t%02d" % int(cid.split("-")[0]) if cid.split("-")[0].isdigit() else ""
            if tid and tid in {e["id"] for e in v.index["topics"]} and not bank.is_ready("topic", tid, v.bank):
                v.warn(mid, 1, "chains 의 %s 는 아직 준비 중인 주제 %s 의 사슬입니다." % (cid, tid))
            else:
                v.fail(mid, 1, "chains 의 %s 가 어느 주제의 meta.json 에도 없습니다." % cid)
    for key in ("defines_inline",):
        if not isinstance(raw.get(key, []), list):
            v.fail(mid, 1, "%s 는 목록이어야 합니다." % key)
    check_sources(v, mid, raw.get("sources", []))
    if not mission["brief"].strip():
        v.fail(mid, 1, "brief.md 가 비어 있습니다.")


def template_folder(v, mid, mission):
    app = mission["app_dir"]
    for name in APP_FILES:
        if not os.path.isfile(os.path.join(app, name)):
            v.fail(mid, 1, "app/%s 가 없습니다." % name)
    if not os.path.isdir(os.path.join(app, "src")):
        v.fail(mid, 1, "app/src/ 가 없습니다.")
    for name in ("node_modules", "dist"):
        folder = os.path.join(app, name)
        if os.path.isdir(folder) and (name == "dist" or checks.has_packages(folder)):
            v.fail(mid, 1, "app/%s 폴더를 지우세요. 의존성은 저장소 맨 위 node_modules 를 씁니다." % name)
    package_path = os.path.join(app, "package.json")
    if os.path.isfile(package_path):
        try:
            package = study.read_json(package_path)
        except ValueError as error:
            package = None
            v.fail(mid, 1, "app/package.json 을 읽을 수 없습니다: %s" % error)
        if isinstance(package, dict):
            extra = sorted(set(package) - set(APP_KEYS))
            if extra:
                v.fail(mid, 1, "app/package.json 에는 %s 만 둡니다. 더 있는 키: %s" % (", ".join(APP_KEYS), ", ".join(extra)))
            if package.get("private") is not True or package.get("type") != "module" or not str(package.get("name", "")).strip():
                v.fail(mid, 1, "app/package.json 은 name, \"private\": true, \"type\": \"module\" 이어야 합니다.")
            scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
            wanted = dict(APP_SCRIPTS, **{k: v_ for k, v_ in APP_OPTIONAL_SCRIPTS.items() if k in scripts})
            if scripts != wanted:
                v.fail(mid, 1, "app/package.json 의 scripts 는 %s 여야 합니다(typecheck 는 %s 로 둘 수 있음)."
                       % (json.dumps(APP_SCRIPTS, ensure_ascii=False), json.dumps(APP_OPTIONAL_SCRIPTS, ensure_ascii=False)))
    files = walk_files(app)
    total = sum(os.path.getsize(path) for _, path in files)
    if total > APP_LIMIT:
        v.fail(mid, 1, "app/ 크기가 %.1fKB 입니다(한도 %dKB)." % (total / KB, APP_LIMIT // KB))
    tests = [rel for rel, _ in files if TEST_FILE.search(rel)]
    if len(tests) < TEMPLATE_TESTS[0]:
        v.fail(mid, 1, "app/ 에 기존 테스트(*.test.tsx)가 없습니다. 실제 저장소처럼 1~3개를 두고 템플릿에서 통과하게 합니다.")
    elif len(tests) > TEMPLATE_TESTS[1]:
        v.warn(mid, 1, "app/ 의 기존 테스트가 %d개입니다(권장 1~3개)." % len(tests))
    for rel, path in files:
        if not rel.endswith(bank.TEXT_EXTS):
            continue
        try:
            text = study.read_text(path)
        except (OSError, UnicodeDecodeError):
            v.fail(mid, 1, "app/%s 를 UTF-8 글로 읽을 수 없습니다." % rel)
            continue
        found = EXTERNAL_URL.search(text)
        if found:
            v.fail(mid, 1, "app/%s 에 바깥 주소가 있습니다: %s" % (rel, found.group(0)))
        found = COMPANY.search(text)
        if found:
            v.fail(mid, 1, "app/%s 에 회사 이름이 있습니다: %s" % (rel, found.group(0)))


def mission_secrets(v, mid, mission, secrets, steps):
    live = len(mission["steps"]) - 1
    if "steps.md" not in secrets:
        v.fail(mid, 2, "work/steps.md 가 없습니다.")
        return
    if [s["no"] for s in steps] != list(range(live + 1)):
        v.fail(mid, 2, "steps.md 의 단계 번호 %s 가 meta.json 의 steps(0~%d단계)와 맞지 않습니다."
               % ([s["no"] for s in steps], live))
    for step in steps:
        label = "%d단계" % step["no"]
        if not step["title"].strip():
            v.fail(mid, 2, "%s 제목이 비어 있습니다." % label)
        if not step["request"].strip():
            v.fail(mid, 2, "%s 에 `### 요구` 의 면접관 말(> 면접관: …)이 없습니다." % label)
        if step["no"] == 0:
            if not step["self"]:
                v.fail(mid, 2, "0단계에는 `### 점검` 항목이 있어야 합니다.")
            if step["checks"] or step["hints"]:
                v.fail(mid, 2, "0단계에는 검사와 힌트를 두지 않습니다.")
            continue
        if not step["checks"]:
            v.fail(mid, 2, "%s 에 `### 검사` 목록이 없습니다." % label)
        if not step["hints"]:
            v.fail(mid, 2, "%s 에 `### 힌트` 가 없습니다." % label)
        if step["after"] is not None:
            if not step["after"]["ask"].strip():
                v.fail(mid, 2, "%s 의 통과 뒤 질문에 면접관 말이 없습니다." % label)
            if not any(item["need"] for item in step["after"]["items"]):
                v.fail(mid, 2, "%s 의 통과 뒤 질문에 [필수] 항목이 없습니다." % label)
    files = bank.check_files(secrets)
    kit = bank.kit_files(v.bank)
    kit_names = {os.path.splitext(rel)[0] for rel in kit} | set(kit)
    for k in range(1, live + 1):
        text = files.get(k)
        if text is None:
            v.fail(mid, 2, "checks/step%d.test.tsx 가 없습니다." % k)
            continue
        check_file(v, mid, "step%d.test.tsx" % k, text, k, kit_names)
        if not any(rel.startswith("solution/step%d/" % k) for rel in secrets):
            v.fail(mid, 2, "solution/step%d/ 에 그 단계에서 바뀐 파일이 없습니다." % k)
    for rel in secrets:
        found = re.match(r"solution/step(\d+)/", rel)
        if found and not 1 <= int(found.group(1)) <= live:
            v.fail(mid, 2, "%s 는 1~%d단계가 아닙니다." % (rel, live))
        if found and not rel.endswith(bank.TEXT_EXTS):
            v.fail(mid, 2, "모범 답안은 글 파일만 둡니다: %s" % rel)
    if mission["hidden"] and "hidden" not in files:
        v.fail(mid, 2, "meta.json 의 hidden 이 true 인데 checks/hidden.test.tsx 가 없습니다.")
    if not mission["hidden"] and "hidden" in files:
        v.fail(mid, 2, "checks/hidden.test.tsx 가 있으면 meta.json 의 hidden 을 true 로 둡니다.")
    if "hidden" in files:
        check_file(v, mid, "hidden.test.tsx", files["hidden"], "hidden", kit_names)
    explain = secrets.get("explain.md", "")
    if not explain.strip():
        v.fail(mid, 2, "work/explain.md 가 없습니다.")
    else:
        heads = [title for level, title in headings(explain) if level == 2]
        for title in EXPLAIN_HEADS:
            if title not in heads:
                v.fail(mid, 2, "explain.md 에 「%s」 절이 없습니다." % title)
        for title in heads:
            if title not in EXPLAIN_HEADS + EXPLAIN_OPTIONAL:
                v.warn(mid, 2, "explain.md 의 「%s」 절은 정해진 절(%s)이 아닙니다." % (title, ", ".join(EXPLAIN_HEADS + EXPLAIN_OPTIONAL)))
    cid = mid + "-F"
    if "followups.md" not in secrets:
        v.fail(mid, 2, "work/followups.md 가 없습니다.")
    else:
        chains = bank.parse_chains(secrets["followups.md"])
        if cid not in chains:
            v.fail(mid, 2, "followups.md 의 사슬 id 는 %s 여야 합니다(있는 것: %s)." % (cid, listing(chains) or "없음"))
        else:
            chain_body(v, mid, chains[cid], "followups.md")
        if cid not in mission["chains"]:
            v.warn(mid, 2, "meta.json 의 chains 에 %s 를 넣으면 꼬리 질문이 복습 목록에 들어갑니다." % cid)
    if not bank.parse_bullets(secrets.get("check.md", "")):
        v.warn(mid, 2, "work/check.md 에 이 미션만의 점검 항목이 없습니다.")


def check_file(v, mid, name, text, step, kit_names):
    ids = bank.check_ids(text)
    if not ids:
        v.fail(mid, 2, "%s 에 test('…') 가 없습니다." % name)
    for cid in ids:
        if step == "hidden":
            if cid[:1].isdigit():
                v.fail(mid, 2, "%s 의 검사 id 는 숫자로 시작하지 않습니다(단계 검사와 섞이지 않게): %s" % (name, cid))
        else:
            found = CHECK_ID.match(cid)
            if not found or int(found.group(1)) != step:
                v.fail(mid, 2, "%s 의 검사 이름은 \"%d<a-z> 학습자용 문장\" 으로 시작해야 합니다: %s" % (name, step, cid))
    titles = [title for _, title in bank.TEST_NAME.findall(text)]
    firsts = [t.split(" ", 1)[0] for t in titles]
    if len(set(firsts)) != len(firsts):
        v.fail(mid, 2, "%s 에 같은 검사 id 가 두 번 있습니다." % name)
    for title in titles:
        if " " not in title.strip():
            v.fail(mid, 2, "%s 의 검사 이름에 학습자용 문장이 없습니다: %s" % (name, title))
    for found in RELATIVE_IMPORT.findall(text):
        v.fail(mid, 2, "%s 가 상대 경로로 import 합니다(%s). 학습자 코드는 @app/, 도우미는 @kit/ 로만 가져옵니다." % (name, found))
    for found in KIT_IMPORT.findall(text):
        if found not in kit_names:
            v.fail(mid, 2, "%s 가 @kit/%s 를 import 하지만 kit/ 에 그 파일이 없습니다." % (name, found))


def chain_body(v, label, chain, name):
    """사슬 하나의 꼴. 소개, 질문 3~5개(경고), 질문마다 [필수] 1~3개와 「막히면」, 약한 답."""
    cid = chain["id"]
    if not chain["intro"].strip():
        v.fail(label, 2, "%s(%s) 에 소개 문단이 없습니다." % (name, cid))
    count = len(chain["questions"])
    if count == 0:
        v.fail(label, 2, "%s(%s) 에 질문(### Q1. …)이 없습니다." % (name, cid))
    elif not QUESTIONS[0] <= count <= QUESTIONS[1]:
        v.warn(label, 2, "%s(%s) 의 질문이 %d개입니다(권장 %d~%d개)." % (name, cid, count, QUESTIONS[0], QUESTIONS[1]))
    if [q["no"] for q in chain["questions"]] != list(range(1, count + 1)):
        v.fail(label, 2, "%s(%s) 의 질문 번호가 Q1 부터 이어지지 않습니다." % (name, cid))
    for question in chain["questions"]:
        qlabel = "%s(%s) Q%d" % (name, cid, question["no"])
        need = [i for i in question["items"] if i["need"]]
        extra = [i for i in question["items"] if not i["need"]]
        if not NEED_ITEMS[0] <= len(need) <= NEED_ITEMS[1]:
            (v.fail if not need else v.warn)(label, 2, "%s 의 [필수] 항목이 %d개입니다(1~%d개)." % (qlabel, len(need), NEED_ITEMS[1]))
        if len(extra) > EXTRA_ITEMS:
            v.warn(label, 2, "%s 의 [보충] 항목이 %d개입니다(0~%d개)." % (qlabel, len(extra), EXTRA_ITEMS))
        if not question["stuck"].strip():
            v.fail(label, 2, "%s 에 「> 막히면: …」 줄이 없습니다." % qlabel)
        if not question["ask"].strip():
            v.fail(label, 2, "%s 의 질문 문장이 비어 있습니다." % qlabel)
    if chain["weak"] is None or not chain["weak"]["quote"].strip():
        v.fail(label, 2, "%s(%s) 에 「### 약한 답」(인용 한 줄과 왜 약한지)이 없습니다." % (name, cid))
    elif not chain["weak"]["why"].strip():
        v.fail(label, 2, "%s(%s) 의 약한 답에 왜 약한지 설명하는 문단이 없습니다." % (name, cid))


def text_check(v, kind, entry, label):
    """학습자에게 보이는 글이 tools/check_style.py 를 통과하는지(표 칸, 캡션, meta 글, 검사 이름까지)."""
    report = web_lint.lint_item(kind, entry, v.bank, v.index, v.tools, parts=("style",))
    for _, where, rule, text in report.errors:
        v.fail(label, 3, "%s: %s: %s" % (where, rule, text))


# 미션 실행

def by_step(parsed, steps, hidden):
    out = {}
    for step in list(steps) + (["hidden"] if hidden else []):
        mine = [t for t in parsed["tests"] if t["step"] == step]
        out[step] = {"pass": [t["id"] for t in mine if t["status"] == "pass"], "fail": [t for t in mine if t["status"] == "fail"],
                     "ok": bool(mine) and all(t["status"] == "pass" for t in mine)}
    return out


def build_variant(v, mid, mission, secrets, upto, label):
    """템플릿에 solution/step1~upto 를 덮은 앱을 <root>/.web-check/_verify_<mid>/<label>/ 에 만듦."""
    folder = os.path.join(v.root, checks.CHECK_DIR, "_verify_" + mid, label)
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(mission["app_dir"], folder, ignore=shutil.ignore_patterns(*SKIP_DIRS))
    for rel, text in bank.solution_files(secrets, upto).items():
        study.write_text(os.path.join(folder, *rel.split("/")), text)
    return folder


def run_checks(v, mid, node, secrets, kit, steps, app_dir, hidden=False):
    """단계 검사를 한 번 돌려 {"by_step", "pass", "fail", "ms", "files": {파일: ms}} 로. 돌리지 못하면 None(실패를 적음)."""
    try:
        prepared = checks.prepare(v.root, mid, secrets, kit, steps, os.path.join(app_dir, "src"), hidden)
    except checks.CheckError as error:
        v.fail(mid, 4, str(error))
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="verify_web_", **study.TMP_OPTIONS) as tmp:
            out_path = os.path.join(tmp, "result.json")
            try:
                ran = checks.run(node, v.root, prepared["config"], out_path, RUN_LIMIT_S)
            except checks.CheckError as error:
                v.fail(mid, 4, str(error))
                return None
            if ran["timeout"]:
                v.fail(mid, 8, "검사가 %d초 안에 끝나지 않았습니다." % RUN_LIMIT_S)
                return None
            try:
                text = study.read_text(out_path)
            except OSError:
                tail = "\n".join(ran["output"].strip().splitlines()[-checks.MESSAGE_LINES:])
                v.fail(mid, 4, "검사 결과 파일이 만들어지지 않았습니다(종료 코드 %s).\n%s" % (ran["returncode"], tail))
                return None
            try:
                parsed = checks.parse(text, prepared["expected"], v.root)
                raw = json.loads(text)
            except (checks.CheckError, ValueError) as error:
                v.fail(mid, 4, str(error))
                return None
    finally:
        checks.cleanup(v.root, mid)
    files = {}
    for result in raw.get("testResults") or []:
        name = os.path.basename(str(result.get("name") or ""))
        try:
            files[name] = int(result["endTime"]) - int(result["startTime"])
        except (KeyError, TypeError, ValueError):
            continue
    return {"by_step": by_step(parsed, steps, hidden and "hidden" in bank.check_files(secrets)), "tests": parsed["tests"],
            "pass": [t["id"] for t in parsed["tests"] if t["status"] == "pass"],
            "fail": [t["id"] for t in parsed["tests"] if t["status"] == "fail"], "ms": ran["ms"], "files": files}


def run_node(v, node, args, cwd, limit=NODE_LIMIT_S):
    """node 자식 하나를 돌려 (returncode, 출력) 으로. 시간을 넘기면 (None, 안내)."""
    options = {"cwd": cwd, "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
               "env": v.vitest_env(), "creationflags": study.NO_WINDOW}
    try:
        done = _run([node] + list(args), timeout=limit, **options)
    except subprocess.TimeoutExpired:
        return None, "%d초 안에 끝나지 않았습니다." % limit
    except OSError as error:
        return None, "실행하지 못했습니다: %s" % error
    output = done.stdout.decode("utf-8", "replace") if isinstance(done.stdout, bytes) else (done.stdout or "")
    return done.returncode, checks.ANSI.sub("", output)


def run_own_tests(v, mid, node, app_dir):
    """템플릿 안의 기존 테스트(npm test 와 같음)를 vitest 로 돌림. 모두 통과하면 True."""
    vitest = os.path.join(v.root, "node_modules", "vitest", "vitest.mjs")
    with tempfile.TemporaryDirectory(prefix="verify_web_own_", **study.TMP_OPTIONS) as tmp:
        out_path = os.path.join(tmp, "own.json")
        args = [vitest, "run", "--root", app_dir, "--config", os.path.join(app_dir, "vite.config.ts"), "--reporter=json",
                "--outputFile=%s" % out_path]
        code, output = run_node(v, node, args, v.root, RUN_LIMIT_S)
        if code is None:
            v.fail(mid, 4, "템플릿의 기존 테스트가 %s" % output)
            return False
        try:
            data = json.loads(study.read_text(out_path))
            results = data["testResults"]
        except (OSError, ValueError, KeyError, TypeError):
            v.fail(mid, 4, "템플릿의 기존 테스트 결과를 읽지 못했습니다(종료 코드 %s).\n%s" % (code, clip(output, 400)))
            return False
    total, bad = 0, []
    for result in results:
        rows = result.get("assertionResults") or []
        if not rows and str(result.get("status")) != "passed":
            bad.append("%s: %s" % (os.path.basename(str(result.get("name") or "")), clip(result.get("message") or "", 160)))
        for row in rows:
            total += 1
            if str(row.get("status")) != "passed":
                bad.append(str(row.get("title") or row.get("fullName") or ""))
    if total == 0:
        v.fail(mid, 4, "템플릿에서 돌아간 기존 테스트가 없습니다.")
        return False
    if bad:
        v.fail(mid, 4, "템플릿의 기존 테스트가 실패합니다: %s" % listing(bad))
        return False
    v.note(mid, "템플릿의 기존 테스트 %d개 통과" % total)
    return True


def typecheck(v, mid, node, app_dir):
    tsc = os.path.join(v.root, "node_modules", "typescript", "bin", "tsc")
    if not os.path.isfile(tsc):
        v.note(mid, "typescript 가 설치되어 있지 않아 타입 검사(tsc --noEmit)는 건너뜁니다(설계 8절: 1차 스택에서 뺌).")
        return
    code, output = run_node(v, node, [tsc, "--noEmit", "-p", app_dir], app_dir, RUN_LIMIT_S)
    if code != 0:
        v.fail(mid, 6, "마지막 단계 모범 답안이 tsc --noEmit 을 통과하지 못합니다.\n%s" % clip(output, 400))


def describe_fails(tests):
    return listing("%s(%s)" % (t["id"], clip(t["message"].splitlines()[0] if t["message"] else "", 90)) for t in tests)


def mission_runs(v, mid, mission, secrets, live):
    node = v.node_path(4)
    if not node or not v.stack_ready(mid, 4):
        return
    kit = bank.kit_files(v.bank)
    all_steps = list(range(1, live + 1))
    verify_dir = os.path.join(v.root, checks.CHECK_DIR, "_verify_" + mid)
    try:
        template = build_variant(v, mid, mission, secrets, 0, "template")
        if v.wants(4):
            run_own_tests(v, mid, node, template)
            result = run_checks(v, mid, node, secrets, kit, all_steps, template)
            if result is None:
                return
            for k in all_steps:
                if result["by_step"][k]["ok"]:
                    v.fail(mid, 4, "%d단계 검사가 템플릿에서 모두 통과합니다. 검사가 요구를 확인하지 못하고 있습니다." % k)
        final = None
        for k in all_steps:
            variant = build_variant(v, mid, mission, secrets, k, "step%d" % k)
            last = k == live
            if not (v.wants(5) or (last and any(v.wants(s) for s in (6, 7, 8)))):
                continue
            result = run_checks(v, mid, node, secrets, kit, all_steps, variant, hidden=last and mission["hidden"])
            if result is None:
                return
            if v.wants(5):
                for j in range(1, k + 1):
                    row = result["by_step"][j]
                    if not row["ok"]:
                        v.fail(mid, 5, "%d단계까지 고친 코드에서 %d단계 검사가 실패합니다: %s" % (k, j, describe_fails(row["fail"]) or "검사 없음"))
                if not last and result["by_step"][k + 1]["ok"]:
                    v.fail(mid, 5, "%d단계까지 고친 코드에서 %d단계 검사가 미리 통과합니다. 단계가 미리 풀립니다." % (k, k + 1))
            if last:
                final = (variant, result)
        if final is None:
            return
        variant, result = final
        if v.wants(6):
            if mission["hidden"]:
                row = result["by_step"].get("hidden")
                if not row or not row["ok"]:
                    v.fail(mid, 6, "마지막 단계 모범 답안에서 숨긴 검사가 실패합니다: %s" % (describe_fails(row["fail"]) if row else "검사 없음"))
            typecheck(v, mid, node, variant)
        times = [result["ms"]]
        file_times = dict(result["files"])
        if v.wants(7):
            first = (sorted(result["pass"]), sorted(result["fail"]))
            for n in range(2, v.runs + 1):
                again = run_checks(v, mid, node, secrets, kit, all_steps, variant, hidden=mission["hidden"])
                if again is None:
                    return
                times.append(again["ms"])
                for name, ms in again["files"].items():
                    file_times[name] = max(file_times.get(name, 0), ms)
                if (sorted(again["pass"]), sorted(again["fail"])) != first:
                    v.fail(mid, 7, "%d번째 실행의 결과가 첫 실행과 다릅니다(불안정한 검사): 통과 %s / 실패 %s"
                           % (n, listing(again["pass"]), listing(again["fail"])))
            v.note(mid, "모범 답안 검사 %d번 반복, 결과 같음" % v.runs)
        if v.wants(8):
            typical = int(statistics.median(times))
            if typical > ALL_LIMIT_MS:
                v.fail(mid, 8, "열린 단계 전체 검사가 %.1f초 걸립니다(한도 %d초)." % (typical / 1000.0, ALL_LIMIT_MS // 1000))
            slow = sorted((name, ms) for name, ms in file_times.items() if ms > FILE_LIMIT_MS)
            if slow:
                v.fail(mid, 8, "검사 파일 하나가 %d초를 넘습니다: %s" % (FILE_LIMIT_MS // 1000, listing("%s %.1f초" % (n, ms / 1000.0) for n, ms in slow)))
            v.note(mid, "전체 검사 %.1f초(%d번 가운데 중간값), 가장 긴 파일 %.1f초"
                   % (typical / 1000.0, len(times), (max(file_times.values()) if file_times else 0) / 1000.0))
    finally:
        shutil.rmtree(verify_dir, ignore_errors=True)
        parent = os.path.join(v.root, checks.CHECK_DIR)
        try:
            if os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
        except OSError:
            pass


# 주제

def check_topic(v, entry):
    tid = entry["id"]
    tdir = bank.item_dir("topic", tid, v.bank)
    v.head(tid, entry["title"])
    try:
        topic = bank.load_topic(entry, v.bank)
        secrets = bank.load_secrets(tdir)
        raw = study.read_json(os.path.join(tdir, "meta.json"))
    except (bank.BankError, OSError, ValueError) as error:
        v.fail(tid, 1, str(error))
        return
    if v.wants(1):
        if raw.get("format") != 1:
            v.fail(tid, 1, "meta.json 의 format 은 1 이어야 합니다.")
        if raw.get("id") != tid:
            v.fail(tid, 1, "meta.json 의 id 가 폴더 이름과 다릅니다: %r" % raw.get("id"))
        if raw.get("no") != entry["no"]:
            v.fail(tid, 1, "meta.json 의 no(%r)가 index.json 의 no(%d)와 다릅니다." % (raw.get("no"), entry["no"]))
        if not topic["title"].strip():
            v.fail(tid, 1, "title 이 비어 있습니다.")
        if not topic["chains"]:
            v.fail(tid, 1, "chains 가 비어 있습니다.")
        page = None
        if topic["page"]:
            check_page_ids(v, tid, "page", [topic["page"]])
            if topic["page"] in v.pages_by_id and bank.is_ready("page", topic["page"], v.bank):
                try:
                    page = bank.load_page(v.pages_by_id[topic["page"]], v.bank)
                except bank.BankError:
                    page = None
        mission_ids = {e["id"] for e in v.index["missions"]}
        for chain in topic["chains"]:
            cid = chain["id"]
            if cid.split("-")[0] != str(entry["no"]):
                v.fail(tid, 1, "사슬 %s 의 번호는 주제 번호 %d 로 시작해야 합니다." % (cid, entry["no"]))
            if not chain["title"].strip() or not chain["goal"].strip():
                v.fail(tid, 1, "사슬 %s 의 title 과 goal 이 있어야 합니다." % cid)
            if chain["secs"] <= 0:
                v.fail(tid, 1, "사슬 %s 의 secs 는 1 이상이어야 합니다." % cid)
            for mid in chain["missions"]:
                if mid not in mission_ids:
                    v.fail(tid, 1, "사슬 %s 의 missions 에 index.json 에 없는 미션이 있습니다: %s" % (cid, mid))
                elif not bank.is_ready("mission", mid, v.bank):
                    v.warn(tid, 1, "사슬 %s 의 미션 %s 는 아직 준비 중입니다." % (cid, mid))
            if chain["section"]:
                if page is not None and chain["section"] not in page["sections"]:
                    v.fail(tid, 1, "사슬 %s 의 section %s 가 페이지 %s 의 sections 에 없습니다." % (cid, chain["section"], topic["page"]))
                elif page is None:
                    v.warn(tid, 1, "사슬 %s 의 section %s 는 페이지가 준비되면 다시 확인합니다." % (cid, chain["section"]))
        check_sources(v, tid, raw.get("sources", []))
    if v.wants(2):
        text = secrets.get("chains.md")
        if text is None:
            v.fail(tid, 2, "work/chains.md 가 없습니다.")
        else:
            chains = bank.parse_chains(text)
            meta_ids = [c["id"] for c in topic["chains"]]
            for cid in meta_ids:
                if cid not in chains:
                    v.fail(tid, 2, "chains.md 에 사슬 %s 가 없습니다." % cid)
                else:
                    chain_body(v, tid, chains[cid], "chains.md")
            for cid in chains:
                if cid not in meta_ids:
                    v.fail(tid, 2, "chains.md 의 사슬 %s 가 meta.json 의 chains 에 없습니다." % cid)
    if v.wants(3):
        text_check(v, "topic", entry, tid)
    review(v, "topic", tid, topic, secrets)


# 학습 페이지

def check_page(v, entry):
    pid = entry["id"]
    pdir = bank.item_dir("page", pid, v.bank)
    v.head(pid, entry["title"])
    try:
        page = bank.load_page(entry, v.bank)
        raw = study.read_json(os.path.join(pdir, "meta.json"))
    except (bank.BankError, OSError, ValueError) as error:
        v.fail(pid, 1, str(error))
        return
    blocks = code_blocks(page["markdown"])
    if v.wants(1):
        if raw.get("format") != 1:
            v.fail(pid, 1, "meta.json 의 format 은 1 이어야 합니다.")
        if raw.get("id") != pid:
            v.fail(pid, 1, "meta.json 의 id 가 폴더 이름과 다릅니다: %r" % raw.get("id"))
        if not page["title"].strip():
            v.fail(pid, 1, "title 이 비어 있습니다.")
        if not isinstance(raw.get("defines", []), list):
            v.fail(pid, 1, "defines 는 목록이어야 합니다.")
        if pid in page["needs"]:
            v.fail(pid, 1, "needs 에 자기 자신이 있습니다.")
        check_page_ids(v, pid, "needs", page["needs"])
        cycle = needs_cycle(v, pid)
        if cycle:
            v.fail(pid, 1, "needs 가 돌고 돕니다: %s" % " → ".join(cycle))
        heads = headings(page["markdown"])
        if len([h for h in heads if h[0] == 1]) != 1:
            v.fail(pid, 1, "page.md 에는 H1 제목이 하나 있어야 합니다.")
        if not any(level == 2 for level, _ in heads):
            v.fail(pid, 1, "page.md 에 H2 절이 없습니다.")
        titles = {title for _, title in heads}
        for key, title in sorted(page["sections"].items()):
            if title not in titles:
                v.fail(pid, 1, "sections 의 %s(「%s」)가 page.md 의 제목에 없습니다." % (key, title))
        for n, item in enumerate(page["outputs"], 1):
            if not isinstance(item, dict) or not isinstance(item.get("block"), int) or not isinstance(item.get("expect"), str):
                v.fail(pid, 1, "outputs[%d] 는 {block: 번호, expect: 글} 이어야 합니다." % n)
                continue
            if not 1 <= item["block"] <= len(blocks):
                v.fail(pid, 1, "outputs[%d].block %d 번 코드 블록이 없습니다(figure 를 뺀 블록 %d개)." % (n, item["block"], len(blocks)))
            elif blocks[item["block"] - 1][0] not in OUTPUT_LANGS:
                v.fail(pid, 1, "outputs[%d] 의 %d번 블록은 node 로 돌리는 js 블록이어야 합니다(지금 %r)."
                       % (n, item["block"], blocks[item["block"] - 1][0]))
        check_sources(v, pid, raw.get("sources", []))
    if v.wants(3):
        text_check(v, "page", entry, pid)
    if v.wants(9) and page["outputs"]:
        page_outputs(v, pid, page, blocks)
    if v.wants(10):
        figures(v, pid, page["markdown"], pdir, "page", pid, tuple(page["sections"]))
    review(v, "page", pid, page, None)


def needs_cycle(v, pid):
    """needs 를 따라가다 pid 로 돌아오면 그 길, 아니면 None."""
    seen = set()
    stack_ = [(pid, [pid])]
    while stack_:
        current, trail = stack_.pop()
        if current in seen:
            continue
        seen.add(current)
        entry = v.pages_by_id.get(current)
        if entry is None or not bank.is_ready("page", current, v.bank):
            continue
        try:
            needs = bank.load_page(entry, v.bank)["needs"]
        except bank.BankError:
            continue
        for other in needs:
            if other == pid:
                return trail + [pid]
            stack_.append((other, trail + [other]))
    return None


def page_outputs(v, pid, page, blocks):
    node = v.node_path(9)
    if not node:
        return
    with tempfile.TemporaryDirectory(prefix="verify_web_pages_", **study.TMP_OPTIONS) as tmp:
        for n, item in enumerate(page["outputs"], 1):
            if not isinstance(item, dict) or not isinstance(item.get("block"), int) or not 1 <= item["block"] <= len(blocks):
                continue
            lang, code = blocks[item["block"] - 1]
            if lang not in OUTPUT_LANGS:
                continue
            path = os.path.join(tmp, "block%d.js" % item["block"])
            study.write_text(path, code + "\n")
            returncode, output = run_node(v, node, [path], tmp)
            if returncode is None:
                v.fail(pid, 9, "%d번 블록이 %s" % (item["block"], output))
                continue
            if returncode != 0:
                v.fail(pid, 9, "%d번 블록이 node 에서 에러로 끝났습니다.\n%s" % (item["block"], clip(output, 300)))
                continue
            got, want = output.strip().replace("\r\n", "\n"), str(item["expect"]).strip().replace("\r\n", "\n")
            if got != want:
                v.fail(pid, 9, "%d번 블록의 출력이 outputs[%d].expect 와 다릅니다.\n  기대: %s\n  실제: %s"
                       % (item["block"], n, clip(want), clip(got)))
            else:
                v.note(pid, "%d번 블록 출력 일치" % item["block"])


# 그림

def figures(v, label, markdown, folder, kind, owner, sections):
    """figure 블록과 ![…](assets/…) 가 가리키는 그림의 이름 규칙, 꼴, 한도. 파일이 아직 없으면 경고(그림 준비 중)."""
    assets = os.path.join(folder, "assets")
    referenced = set()
    for block in figure_blocks(markdown):
        where = "%d줄 figure" % block["line"]
        rel = block["file"]
        if not rel.startswith("assets/") or rel.count("/") != 1:
            v.fail(label, 10, "%s 의 파일은 assets/<이름>.gif 나 .png 여야 합니다: %r" % (where, rel))
            continue
        name, ext = os.path.splitext(rel.split("/", 1)[1])
        ext = ext.lower()[1:]
        referenced.add(rel.split("/", 1)[1])
        if ext not in ("gif", "png"):
            v.fail(label, 10, "%s 의 파일은 gif 나 png 여야 합니다: %s" % (where, rel))
            continue
        found = owner_of(name)
        if found is None:
            v.fail(label, 10, "%s 의 그림 이름 %s 가 l01-1, 3a-1, w03-1 꼴이 아닙니다." % (where, name))
        elif kind == "mission" and found != ("mission", owner):
            v.fail(label, 10, "%s 의 그림 이름 %s 는 이 미션의 꼴(%s-1)이 아닙니다." % (where, name, owner))
        elif kind == "page" and not (found == ("page", owner) or (found[0] == "section" and found[1] in sections)):
            v.fail(label, 10, "%s 의 그림 이름 %s 는 이 페이지(%s-1)나 그 절(%s)의 꼴이 아닙니다."
                   % (where, name, owner, ", ".join("%s-1" % s for s in sections) or "없음"))
        if not block["caption"]:
            v.fail(label, 10, "%s 에 캡션: 줄이 없습니다." % where)
        elif not block["caption"].startswith("그림 "):
            v.warn(label, 10, "%s 의 캡션은 \"그림 1.\" 처럼 번호로 시작합니다: %s" % (where, clip(block["caption"], 50)))
        if ext == "gif":
            if block["frame_lines"] < 2:
                v.fail(label, 10, "%s 는 GIF 인데 프레임: 설명이 두 줄 이상 없습니다." % where)
            if block["bad_ms"]:
                v.fail(label, 10, "%s 의 프레임 줄은 \"(1400ms)\" 로 끝나야 합니다: %s" % (where, listing(block["bad_ms"], 3)))
            if block["frame_lines"] > LIMITS["frames"]:
                v.fail(label, 10, "%s 의 프레임이 %d개입니다(한도 %d개)." % (where, block["frame_lines"], LIMITS["frames"]))
            bad = [ms for ms in block["frames"] if not LIMITS["ms_min"] <= ms <= LIMITS["ms_max"]]
            if bad:
                v.fail(label, 10, "%s 의 프레임 시간 %s 가 %d~%dms 를 벗어납니다." % (where, listing("%dms" % b for b in bad), LIMITS["ms_min"], LIMITS["ms_max"]))
        elif not block["content"]:
            v.fail(label, 10, "%s 는 PNG 인데 내용: 설명이 없습니다." % where)
        path = os.path.join(assets, rel.split("/", 1)[1])
        if not os.path.isfile(path):
            v.warn(label, 10, "%s 의 그림 파일이 아직 없습니다(화면에는 캡션과 \"그림 준비 중\"만 보임): %s" % (where, rel))
            continue
        for problem in verify_journey.image_problems(path):
            v.fail(label, 10, "%s: %s" % (rel, problem))
        if ext == "gif":
            try:
                with open(path, "rb") as f:
                    frames = verify_journey.gif_info(f.read())["frames"]
            except (OSError, ValueError):
                frames = None
            if frames is not None and frames != block["frame_lines"]:
                v.warn(label, 10, "%s 의 프레임 수 %d 가 프레임 설명 %d줄과 다릅니다." % (rel, frames, block["frame_lines"]))
    for rel in verify_journey.image_refs(markdown):
        referenced.add(rel.split("/")[-1])
        if not os.path.isfile(os.path.join(folder, *rel.split("/"))):
            v.fail(label, 10, "![…](%s) 가 가리키는 그림이 없습니다." % rel)
    if os.path.isdir(assets):
        for name in sorted(os.listdir(assets)):
            if os.path.isfile(os.path.join(assets, name)) and name not in referenced and not name.startswith("."):
                v.warn(label, 10, "assets/%s 는 어느 글도 가리키지 않습니다." % name)


def check_total_images(v):
    total = 0
    for kind, folder in bank.FOLDERS.items():
        parent = os.path.join(v.bank, folder)
        if not os.path.isdir(parent):
            continue
        for name in os.listdir(parent):
            assets = os.path.join(parent, name, "assets")
            if os.path.isdir(assets):
                total += sum(os.path.getsize(os.path.join(assets, f)) for f in os.listdir(assets) if os.path.isfile(os.path.join(assets, f)))
    if total > LIMITS["total_bytes"]:
        v.fail("index", 10, "web/ 의 그림 합계가 %.1fMB 입니다(한도 %dMB)." % (total / KB / 1024.0, LIMITS["total_bytes"] // KB // 1024))


# 검토 서명

def review_files(kind, item, secrets):
    """review.json 이 덮는 파일의 sha256. 공개 파일과 그림은 바이트로, 봉인 안 글은 글로 셈. review.json 자신은 뺌."""
    files = {}
    folder = item["dir"]
    names = ("meta.json", "brief.md") if kind == "mission" else ("meta.json", "page.md") if kind == "page" else ("meta.json",)
    for name in names:
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            files[name] = file_sha(path)
    if kind == "mission":
        for rel, path in walk_files(item["app_dir"]):
            files["app/" + rel] = file_sha(path)
    assets = os.path.join(folder, "assets")
    if os.path.isdir(assets):
        for name in sorted(os.listdir(assets)):
            if os.path.isfile(os.path.join(assets, name)):
                files["assets/" + name] = file_sha(os.path.join(assets, name))
    for rel, text in (secrets or {}).items():
        if rel != "review.json":
            files["work/" + rel] = text_sha(text)
    return files


def review_text(kind, item, secrets):
    if kind == "page":
        path = os.path.join(item["dir"], "review.json")
        return study.read_text(path) if os.path.isfile(path) else None
    return (secrets or {}).get("review.json")


def review_target(kind, item):
    if kind == "page":
        return os.path.join(item["dir"], "review.json")
    return os.path.join(item["dir"], bank.WORK_DIR, "review.json")


def review(v, kind, label, item, secrets):
    o = v.opts
    if o.sign:
        if v.failed(label):
            v.fail(label, 11, "실패가 있어 서명하지 않았습니다.")
        else:
            sign(v, kind, label, item, secrets)
    if o.require_review:
        check_review(v, label, review_text(kind, item, secrets), review_files(kind, item, secrets))


def sign(v, kind, label, item, secrets):
    o = v.opts
    names = {"writer": o.writer, "resolver": o.resolver, "reviewer": o.reviewer}
    missing = [key for key, value in names.items() if not (value or "").strip()]
    if missing:
        v.fail(label, 11, "--%s 가 필요합니다." % ", --".join(missing))
        return
    if o.writer.strip() in (o.resolver.strip(), o.reviewer.strip()):
        v.fail(label, 11, "출제자는 재풀이자나 검토자를 겸하지 않습니다(%s)." % o.writer)
        return
    findings = []
    old = review_text(kind, item, secrets)
    if old:
        try:
            findings = list(json.loads(old).get("findings") or [])
        except (ValueError, AttributeError):
            findings = []
    findings += [text for text in (o.finding or []) if text.strip()]
    files = review_files(kind, item, secrets)
    data = {"format": 1, "writer": o.writer.strip(), "resolver": o.resolver.strip(), "reviewer": o.reviewer.strip(),
            "files": dict(sorted(files.items())), "findings": findings}
    target = review_target(kind, item)
    study.write_text(target, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    v.note(label, "서명했습니다: %s (파일 %d개)%s" % (study.shown_path(target), len(files),
                                           "" if kind == "page" else ". web_seal.py seal 로 다시 묶어 커밋하세요."))


def check_review(v, label, text, files):
    if text is None:
        v.fail(label, 11, "검토 서명(review.json)이 없습니다. 검토를 받고 --sign 으로 서명하세요.")
        return
    try:
        data = json.loads(text)
    except ValueError as error:
        v.fail(label, 11, "review.json 을 읽을 수 없습니다: %s" % error)
        return
    names = [data.get(key) for key in ("writer", "resolver", "reviewer")] if isinstance(data, dict) else []
    if len(names) != 3 or not all(isinstance(x, str) and x.strip() for x in names):
        v.fail(label, 11, "review.json 에 writer, resolver, reviewer 가 모두 있어야 합니다.")
        return
    if names[0] in names[1:]:
        v.fail(label, 11, "출제자(%s)가 재풀이자나 검토자와 같습니다." % names[0])
    signed = data.get("files") if isinstance(data.get("files"), dict) else {}
    changed = sorted(name for name in set(signed) | set(files) if signed.get(name) != files.get(name))
    if changed:
        v.fail(label, 11, "검토 뒤에 바뀐 파일: %s" % listing(changed, 8))


# 명령줄

def parse_args(argv):
    parser = argparse.ArgumentParser(prog="verify_web.py", description="웹 면접 준비 은행 검증")
    parser.add_argument("targets", nargs="*", help="미션·주제·페이지 id (없으면 출제된 것 전부)")
    parser.add_argument("--bank", default=bank.BANK_DIR)
    parser.add_argument("--root", help="node_modules 와 .web-check 를 두는 저장소 맨 위")
    parser.add_argument("--pages", action="store_true", help="학습 페이지만 봄")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="반복 안정성 검사 횟수(기본 %d)" % DEFAULT_RUNS)
    parser.add_argument("--sign", action="store_true", help="검증을 통과하면 review.json 을 씀")
    parser.add_argument("--writer", help="출제자 이름표")
    parser.add_argument("--resolver", help="재풀이자 이름표")
    parser.add_argument("--reviewer", help="검토자 이름표")
    parser.add_argument("--finding", action="append", help="review.json 의 findings 에 남길 한 줄(여러 번 줄 수 있음)")
    parser.add_argument("--require-review", action="store_true", help="검토 서명이 없거나 서명 뒤에 바뀐 파일이 있으면 실패")
    return parser.parse_args(argv)


def main(argv=None, steps=None, out=None):
    opts = parse_args(sys.argv[1:] if argv is None else argv)
    v = Verifier(opts, steps, out)
    if not load_index(v):
        return 1
    if v.wants(1):
        check_terms(v)
    if v.wants(10):
        check_total_images(v)
    rows = []
    kinds = ("page",) if opts.pages else ("mission", "topic", "page")
    for kind in kinds:
        for entry in v.index[kind + "s"]:
            if bank.is_ready(kind, entry["id"], v.bank):
                rows.append((kind, entry))
    if opts.targets:
        known = {entry["id"]: (kind, entry) for kind, entry in rows}
        missing = [t for t in opts.targets if t not in known]
        if missing:
            v.say("출제된 미션·주제·페이지가 아닙니다: %s" % ", ".join(missing))
            return 2
        rows = [known[t] for t in opts.targets]
    for kind, entry in rows:
        {"mission": check_mission, "topic": check_topic, "page": check_page}[kind](v, entry)
    if v.failures:
        v.say("실패 %d개, 경고 %d개 (항목 %d개)" % (len(v.failures), len(v.warnings), len(rows)))
        return 1
    v.say("OK: 항목 %d개 통과, 경고 %d개" % (len(rows), len(v.warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
