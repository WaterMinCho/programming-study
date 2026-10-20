#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""알고리즘 여행 문제 은행(dungeons/) 검증. 실패가 하나라도 있으면 1 로 끝남.

  python tools/verify_journey.py [d01 | d01/p3 ...]           형식부터 그림까지 모두 봄(대상이 없으면 출제된 던전 전부)
  python tools/verify_journey.py d01 --lang javascript        JS 기준 풀이·알려진 풀이·스트레스와 다시 푼 풀이의 JS 답만
  python tools/verify_journey.py d01/p3 --fill                비어 있는 기대값을 solution.py 의 결과로 채움(평문 tests.json)
  python tools/verify_journey.py d01 --timing --pythons P1,P2 --nodes N1,N2 [--report]
                                                              기준 컴퓨터에서 시간 여유와 회색 지대를 잼
  python tools/verify_journey.py --styles [--changed REF]     wrong.json 의 재귀 방식(style) 항목만 이 Python 판에서 봄
  python tools/verify_journey.py d01/p3 --alt DIR             아직 넣지 않은 다시 푼 풀이(DIR 의 alt.py, alt.js)로 스트레스와 전체 테스트 대조
  python tools/verify_journey.py d01/p3 --sign --writer W --resolver R --reviewer V [--finding 글 ...]
                                                              검증을 통과하면 review.json 을 씀(d01 처럼 던전을 주면 던전 폴더의 것)
  python tools/verify_journey.py --require-review [--changed REF]
                                                              검토 서명이 없거나 서명 뒤에 바뀐 파일이 있으면 실패
  python tools/verify_journey.py --plan REF                   journey.yml 이 쓸 engine=…, styles=… 두 줄만 찍음

그 밖의 옵션: --bank DIR(기본 dungeons/), --changed REF(REF 와 갈라진 뒤 바뀐 던전만), --jobs N(동시에 돌릴 자식 수).
실행과 판정은 화면과 같은 journey.runner·journey.grading 을 씀. 생성 입력은 기본 캐시를 쓰고, 결정성 단계는 캐시 없이
두 프로세스에서 다시 만들고 스트레스 입력도 돌릴 때마다 새로 만듦. 단계 번호와 내용은 아래 STEP_NAMES 와 각 step_ 함수에 있음.
"""
import argparse
import ast
import copy
import fnmatch
import hashlib
import json
import keyword
import math
import os
import re
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import mdlite  # noqa: E402
import study  # noqa: E402
from journey import bank, grading, runner, values  # noqa: E402
from journey import node as node_finder  # noqa: E402
from tools.journey_art import KB, LIMITS, SCALE  # noqa: E402

LANGS = values.LANGS
EXT = runner.EXT
LANG_LABEL = {"python": "Python", "javascript": "JavaScript"}
STEP_NAMES = {1: "형식", 2: "비밀 파일", 3: "지문", 4: "테스트 구성", 5: "제한사항 검사", 6: "생성 결정성", 7: "기준 풀이",
              8: "완전 탐색", 9: "스트레스 대조", 10: "다시 푼 풀이", 11: "시작 코드", 12: "알려진 풀이", 13: "재귀 방식",
              14: "그림", 15: "시간", 16: "기대값 채우기", 18: "검토 서명"}
LANG_STEPS = (7, 9, 10, 12, 13)  # --lang javascript 일 때 도는 단계. 나머지는 언어와 상관없거나 Python 만 씀

HEADINGS = ("문제 설명", "함수", "제한사항", "입출력 예", "입출력 예 설명")
REQUIRED = ("solution.py", "solution.js", "brute.py", "validate.py", "tests.json", "extra.json", "hints.md", "explain.md")
# 다시 푼 풀이는 출제자가 검증을 통과시킨 뒤에 들어오므로 서명(--sign)과 서명 확인(--require-review)에서만 꼭 있어야 함
REVIEW_REQUIRED = ("alt.py", "alt.js")
EXPECTS = ("wrong", "timeout", "runtime", "fail", "pass")
STYLES = {"python": ("plain", "raised", "raised_small", "cache", "cache_default", "builtin", "iterative"),
          "javascript": ("recursive", "heavy")}
# 재귀 방식별 기대 판정. 열은 테스트의 depth 가 없음(300 이하), limit(1,000~1,500), chain(2×10^5 이상)
STYLE_TABLE = {
    "iterative": ("pass", "pass", "pass"),
    "plain": ("pass", "runtime", "runtime"), "cache_default": ("pass", "runtime", "runtime"),
    "builtin": ("pass", "runtime", "runtime"),
    "raised": ("pass", "pass", "runtime"), "raised_small": ("pass", "pass", "runtime"), "cache": ("pass", "pass", "runtime"),
    "recursive": ("pass", "pass", "runtime"), "heavy": ("pass", "pass", "runtime"),
}
DEPTHS = (None, "limit", "chain")
VERDICT_TEXT = {"pass": "통과", "runtime": "런타임 에러"}

TEST_ID = re.compile(r"[a-z0-9_]+\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
JS_NAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\Z")
JS_RESERVED = frozenset((
    "break case catch class const continue debugger default delete do else enum export extends false finally for function "
    "if import in instanceof new null return super switch this throw true try typeof var void while with yield let static "
    "implements interface package private protected public await arguments eval undefined NaN Infinity").split())
JS_FUNCTION = re.compile(r"function\s+solution\s*\(([^)]*)\)")
IMAGE_REF = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
GEN_CALLS = ("set", "frozenset", "hash", "__import__", "eval", "exec", "compile", "open")

EXAMPLES = (2, 3)
ACCURACY = (15, 25)
NAMED_MIN = 9
BUNDLE_SIZE, BUNDLE_LINES = 50, 6
EFFICIENCY = (3, 8)
LITERAL_MAX = 4096  # 정규 JSON 이 이보다 길면 expected_sha 로 둠
SEALED_LIMIT = 300 * KB
PEAK_LIMIT_MB = 256  # 기준 풀이의 피크 메모리 상한
STRESS_SEEDS = 20
WIDE_MS = 60000  # 완전 탐색·다시 푼 풀이·기대값 채우기는 답만 보므로 호출 하나에 60초까지 줌
SHOWN = 160  # 실패 문구에 넣는 값의 길이

TIMING_RUNS = 3
FAST_SHARE = 15  # 통과시킬 풀이는 제한의 1/15 안
SLOW_TIMES = 10  # 죽일 풀이는 제한의 10배 넘게
LIMIT_RULE = 16.5
LIMIT_STEP = 500
BASE_LIMIT = {"python": 2000, "javascript": 1000}

ENGINE_CHANGED = ("journey/", "tools/verify_journey.py", "study.py")  # 이것이 바뀌면 --changed 가 모든 던전을 봄
PLAN_ENGINE = ENGINE_CHANGED + ("tests/journey_bank/", "tools/journey_seal.py", ".github/workflows/journey.yml",
                                "tests/test_journey_*.py")


# 작은 도우미

def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def shown(value, limit=SHOWN):
    return values.show(value, "python", limit)


def shown_canonical(text, limit=SHOWN):
    try:
        return shown(json.loads(text), limit)
    except (TypeError, ValueError):
        return str(text)


def listing(items, most=6):
    items = list(items)
    text = ", ".join(items[:most])
    if len(items) > most:
        text += " 외 %d개" % (len(items) - most)
    return text


def status_of(raw):
    """판정에 쓰는 상태. fatal 을 grading 처럼 나누는 일은 Verifier.run_tests 가 이미 했음."""
    return None if raw is None else raw["status"]


STATUS_TEXT = {"pass": "통과", "wrong": "틀린 답", "bad_return": "허용하지 않는 반환값", "runtime": "런타임 에러",
               "timeout": "시간 초과", "memory": "메모리 초과", "cancelled": "취소됨", "fatal": "실행 전 오류"}


def describe(raw):
    """결과 하나를 한 줄로. 실패 문구에 씀."""
    if raw is None:
        return "실행하지 못함"
    parts = [STATUS_TEXT.get(raw["status"], raw["status"])]
    fatal = raw.get("fatal") or {}
    detail = raw.get("error") or fatal.get("message") or ""
    if detail:
        parts.append(detail.strip().splitlines()[-1][:200])
    if raw.get("note"):
        parts.append(raw["note"][:200])
    return ", ".join(parts)


def gen_violations(source):
    """gen.py 에서 결정성을 깨는 것(journey.gen 이 아닌 import, 금지된 호출, 집합 표현)을 찾아 설명 목록으로 돌려줌."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return ["문법 오류: %s" % error]
    found = []
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            names = [alias.name for alias in item.names if alias.name != "journey.gen"]
            if names:
                found.append("%d번째 줄 import %s" % (item.lineno, ", ".join(names)))
        elif isinstance(item, ast.ImportFrom) and item.module != "journey.gen":
            found.append("%d번째 줄 from %s import" % (item.lineno, item.module or "."))
        elif isinstance(item, (ast.Set, ast.SetComp)):
            found.append("%d번째 줄 집합 표현" % item.lineno)
        elif isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id in GEN_CALLS:
            found.append("%d번째 줄 %s() 호출" % (item.lineno, item.func.id))
    return found


def composite_validate(kinds, source):
    """genrun 의 --validate 로 넘길 검사기 원문. 인자 타입(정수는 2^53-1 이하)을 먼저 보고 validate.py 의 validate 를 부름.
    genrun 이 저장소 루트를 sys.path[0] 에 두므로 journey.values 를 import 할 수 있음."""
    return ("from journey import values as _values\n"
            "_KINDS = %r\n"
            "_SPACE = {'__name__': 'validate'}\n"
            "exec(compile(%r, 'validate.py', 'exec'), _SPACE)\n\n\n"
            "def validate(*args):\n"
            "    if _KINDS is not None:\n"
            "        if len(args) != len(_KINDS):\n"
            "            return '타입 검사: 인자가 %%d개입니다(매개변수 %%d개)' %% (len(args), len(_KINDS))\n"
            "        for index, (value, kind) in enumerate(zip(args, _KINDS)):\n"
            "            problem = _values.check(value, kind)\n"
            "            if problem:\n"
            "                return '타입 검사: %%d번째 인자: %%s' %% (index + 1, problem)\n"
            "    check = _SPACE.get('validate')\n"
            "    return check(*args) if callable(check) else None\n") % (kinds, source or "")


def markdown_sections(text):
    """## 제목마다 (제목, 블록 목록). 맨 앞의 제목 없는 블록은 버림."""
    sections, current = [], None
    for block in mdlite.parse(text or ""):
        if block["t"] == "heading" and block["level"] == 2:
            current = (block["text"].strip(), [])
            sections.append(current)
        elif current is not None:
            current[1].append(block)
    return sections


def section(sections, title):
    for name, blocks in sections:
        if name == title:
            return blocks
    return []


def constraint_count(markdown):
    """「제한사항」의 맨 바깥 불릿 수. validate 문구의 "N번 줄:" 의 N 이 이 번호를 가리킴."""
    return sum(len(block["items"]) for block in section(markdown_sections(markdown), "제한사항")
               if block["t"] in ("ul", "ol"))


def image_refs(text):
    return IMAGE_REF.findall(text or "")


def gif_info(data):
    """GIF 를 Pillow 없이 읽어 폭, 높이, 프레임 수, 프레임 시간(ms) 목록을 돌려줌. 깨졌으면 ValueError."""
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("GIF 머리가 아닙니다")
    try:
        width, height = struct.unpack("<HH", data[6:10])
        packed, pos = data[10], 13
        if packed & 0x80:
            pos += 3 * (2 ** ((packed & 7) + 1))
        durations, delay = [], None
        while True:
            block = data[pos]
            pos += 1
            if block == 0x3B:
                break
            if block == 0x21:
                label = data[pos]
                pos += 1
                if label == 0xF9 and data[pos] >= 4:
                    delay = struct.unpack("<H", data[pos + 2:pos + 4])[0] * 10
                pos = _skip_blocks(data, pos)
            elif block == 0x2C:
                local = data[pos + 8]
                pos += 9
                if local & 0x80:
                    pos += 3 * (2 ** ((local & 7) + 1))
                pos = _skip_blocks(data, pos + 1)
                durations.append(delay or 0)
                delay = None
            else:
                raise ValueError("알 수 없는 블록 0x%02X" % block)
    except (IndexError, struct.error):
        raise ValueError("GIF 가 중간에 끊겼습니다")
    return {"width": width, "height": height, "frames": len(durations), "durations": durations}


def _skip_blocks(data, pos):
    while True:
        size = data[pos]
        pos += 1
        if size == 0:
            return pos
        pos += size


def png_info(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        raise ValueError("PNG 머리가 아닙니다")
    width, height = struct.unpack(">II", data[16:24])
    return {"width": width, "height": height, "frames": 1, "durations": []}


def image_problems(path):
    """그림 파일 하나가 7절 한도(크기, 프레임 수, 프레임 시간, 폭)를 넘은 곳의 문구 목록."""
    kind = os.path.splitext(path)[1].lower()[1:]
    with open(path, "rb") as f:
        data = f.read()
    try:
        info = gif_info(data) if kind == "gif" else png_info(data)
    except ValueError as error:
        return ["읽을 수 없습니다(%s)" % error]
    found = []
    limit = LIMITS["%s_bytes" % kind]
    if len(data) > limit:
        found.append("크기가 %.1fKB 입니다(한도 %dKB)" % (len(data) / KB, limit // KB))
    if info["frames"] > LIMITS["frames"]:
        found.append("프레임이 %d개입니다(한도 %d개)" % (info["frames"], LIMITS["frames"]))
    bad = [ms for ms in info["durations"] if not LIMITS["ms_min"] <= ms <= LIMITS["ms_max"]]
    if bad:
        found.append("프레임 시간 %s 가 %d~%dms 를 벗어납니다" % (", ".join("%dms" % ms for ms in bad), LIMITS["ms_min"],
                                                             LIMITS["ms_max"]))
    if info["width"] > LIMITS["width"] * SCALE:
        found.append("파일 폭이 %dpx 입니다(한도 %dpx)" % (info["width"], LIMITS["width"] * SCALE))
    return found


def write_tests_json(path, data):
    """tests.json 을 테스트 하나에 한 줄인 꼴로 씀. 키 순서는 그대로 둠."""
    keys = list(data)
    lines = ["{"]
    for k, key in enumerate(keys):
        tail = "," if k < len(keys) - 1 else ""
        name = json.dumps(key, ensure_ascii=False)
        value = data[key]
        if isinstance(value, list) and value:
            lines.append("  %s: [" % name)
            for i, item in enumerate(value):
                lines.append("    " + json.dumps(item, ensure_ascii=False) + ("," if i < len(value) - 1 else ""))
            lines.append("  ]" + tail)
        else:
            lines.append("  %s: %s%s" % (name, json.dumps(value, ensure_ascii=False), tail))
    lines.append("}")
    study.write_text(path, "\n".join(lines) + "\n")


# git

def git(args, cwd):
    done = subprocess.run(["git", "-c", "core.quotepath=false"] + args, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                          creationflags=study.NO_WINDOW)
    if done.returncode != 0:
        raise SystemExit("git %s 이 실패했습니다: %s" % (" ".join(args), done.stderr.strip()))
    return done.stdout


def changed_files(bank_dir, ref):
    """(저장소 맨 위, 은행 폴더의 상대 경로, REF 와 갈라진 뒤 바뀐 파일 목록)."""
    top = git(["rev-parse", "--show-toplevel"], bank_dir).strip()
    rel_bank = os.path.relpath(os.path.realpath(bank_dir), os.path.realpath(top)).replace(os.sep, "/")
    files = [line for line in git(["diff", "--name-only", "%s...HEAD" % ref], top).splitlines() if line.strip()]
    return top, rel_bank, files


def touches(path, patterns):
    for pattern in patterns:
        if pattern.endswith("/"):
            if path.startswith(pattern):
                return True
        elif fnmatch.fnmatchcase(path, pattern):
            return True
    return False


def changed_dungeons(rel_bank, files):
    prefix = rel_bank.rstrip("/") + "/"
    found = []
    for path in files:
        if path.startswith(prefix):
            parts = path[len(prefix):].split("/")
            if len(parts) > 1 and parts[0] not in found:
                found.append(parts[0])
    return found


def changed_scope(bank_dir, ref):
    """--changed REF: (모든 던전을 볼지, 바뀐 던전 목록, index.json 이 바뀌었는지)."""
    _, rel_bank, files = changed_files(bank_dir, ref)
    everything = any(touches(path, ENGINE_CHANGED) for path in files)
    index = rel_bank.rstrip("/") + "/" + bank.INDEX_NAME in files
    return everything, changed_dungeons(rel_bank, files), index


def has_style(ddir):
    """던전의 wrong.json 가운데 style 항목이 있는지. 읽지 못하면 참(재귀 행렬을 돌리는 쪽이 안전함)."""
    try:
        secrets = bank.load_secrets(ddir)
        for rel, text in secrets.items():
            if rel.endswith("/wrong.json"):
                data = json.loads(text)
                if any(isinstance(entry, dict) and entry.get("style") for entry in data.values()):
                    return True
    except (bank.BankError, ValueError, AttributeError):
        return True
    return False


def plan(bank_dir, ref):
    """journey.yml 의 plan 작업이 쓸 값. REF 가 빈 글이면 둘 다 참."""
    if not ref:
        return {"engine": True, "styles": True}
    _, rel_bank, files = changed_files(bank_dir, ref)
    engine = any(touches(path, PLAN_ENGINE) for path in files)
    styles = engine or any(has_style(os.path.join(bank_dir, did)) for did in changed_dungeons(rel_bank, files)
                           if os.path.isdir(os.path.join(bank_dir, did)))
    return {"engine": engine, "styles": styles}


# 은행 읽기

class Dungeon(object):
    def __init__(self, v, did):
        self.v = v
        self.did = did
        self.dir = os.path.join(v.bank, did)
        self.label = did
        self.meta = None
        self.secrets = {}
        self.errors = []
        try:
            self.meta = study.read_json(os.path.join(self.dir, "meta.json"))
        except (OSError, ValueError) as error:
            self.errors.append((1, "meta.json 을 읽을 수 없습니다: %s" % error))
        try:
            self.secrets = bank.load_secrets(self.dir)
        except bank.BankError as error:
            self.errors.append((2, str(error)))
        items = self.meta.get("problems") if isinstance(self.meta, dict) else None
        self.items = [item for item in (items if isinstance(items, list) else [])
                      if isinstance(item, dict) and isinstance(item.get("id"), str)]

    def ids(self):
        return [item["id"] for item in self.items]

    def boss(self):
        for item in self.items:
            if item.get("role") == "boss":
                return item["id"]
        return None


class Problem(object):
    def __init__(self, v, dungeon, item):
        self.v = v
        self.dungeon = dungeon
        self.pid = item["id"]
        self.role = item.get("role")
        self.dir = os.path.join(dungeon.dir, self.pid)
        self.label = "%s/%s" % (dungeon.did, self.pid)
        self.errors = []
        self.raw = self._json_file("problem.json", 1)
        self.markdown = self._text_file("problem.md", 3)
        self.tests = self._secret_json("tests.json", 2)
        self.wrong = self._secret_json("wrong.json", 2) or {}
        self.extra = self._secret_json("extra.json", 2)
        if not isinstance(self.wrong, dict):
            self.errors.append((2, "wrong.json 은 이름을 키로 둔 객체여야 합니다."))
            self.wrong = {}
        self.references = {}
        self.gen_failed = set()
        self._paths = {}
        self._modules = {}
        self._inputs = {}

    def _json_file(self, name, step):
        try:
            return study.read_json(os.path.join(self.dir, name))
        except (OSError, ValueError) as error:
            self.errors.append((step, "%s 을 읽을 수 없습니다: %s" % (name, error)))
            return None

    def _text_file(self, name, step):
        try:
            return study.read_text(os.path.join(self.dir, name))
        except (OSError, ValueError) as error:
            self.errors.append((step, "%s 을 읽을 수 없습니다: %s" % (name, error)))
            return None

    def _secret_json(self, name, step):
        text = self.secret(name)
        if text is None:
            return None
        try:
            return json.loads(text)
        except ValueError as error:
            self.errors.append((step, "%s 을 읽을 수 없습니다: %s" % (name, error)))
            return None

    def secret(self, name):
        return self.dungeon.secrets.get("%s/%s" % (self.pid, name))

    def secret_names(self):
        prefix = self.pid + "/"
        return sorted(rel[len(prefix):] for rel in self.dungeon.secrets if rel.startswith(prefix))

    def source(self, name):
        """비밀 파일 하나를 검증용 임시 폴더에 써서 경로를 돌려줌(봉인만 된 파일도 실행할 수 있게). 없으면 None."""
        if name in self._paths:
            return self._paths[name]
        text = self.secret(name)
        path = None
        if text is not None:
            path = os.path.join(self.v.tmp, self.dungeon.did, self.pid, *name.split("/"))
            study.write_text(path, text)
        self._paths[name] = path
        return path

    def module(self, name, step):
        """봉인 파일(brute.py, certify.py, validate.py)을 이 프로세스에서 실행한 이름공간. 없거나 실패하면 None."""
        if name in self._modules:
            return self._modules[name]
        text = self.secret(name)
        space = None
        if text is not None:
            space = {"__name__": name.rsplit(".", 1)[0]}
            try:
                exec(compile(text, name, "exec"), space)
            except Exception as error:
                self.v.fail(self, step, "%s 을 불러오지 못했습니다: %s: %s" % (name, type(error).__name__, error))
                space = None
        self._modules[name] = space
        return space

    # problem.json

    def params(self):
        try:
            return [param["name"] for param in self.raw["signature"]["params"]]
        except (TypeError, KeyError):
            return []

    def kinds(self):
        try:
            kinds = [param["type"] for param in self.raw["signature"]["params"]]
            for kind in kinds:
                values.parse_type(kind)
            return kinds
        except (TypeError, KeyError, ValueError, AttributeError):
            return None

    def returns(self):
        try:
            return self.raw["signature"]["returns"]
        except (TypeError, KeyError):
            return None

    def limit(self, lang):
        return int(self.raw["time_limit_ms"][lang])

    def examples(self):
        examples = self.raw.get("examples") if isinstance(self.raw, dict) else None
        return [ex for ex in (examples if isinstance(examples, list) else [])
                if isinstance(ex, dict) and isinstance(ex.get("args"), list) and "expected" in ex]

    # tests.json

    def accuracy(self):
        tests = self.tests.get("accuracy") if isinstance(self.tests, dict) else None
        return [t for t in (tests if isinstance(tests, list) else []) if isinstance(t, dict) and isinstance(t.get("id"), str)]

    def efficiency(self):
        tests = self.tests.get("efficiency") if isinstance(self.tests, dict) else None
        return [t for t in (tests if isinstance(tests, list) else []) if isinstance(t, dict) and isinstance(t.get("id"), str)]

    def acc_tests(self):
        return grading.example_tests({"examples": self.examples()}) + self.accuracy()

    def eff_tests(self, lang):
        return [t for t in self.efficiency() if lang in (t.get("langs") or LANGS)]

    def tests_for(self, lang):
        return self.acc_tests() + self.eff_tests(lang)

    def by_id(self):
        found = {}
        for test in self.acc_tests() + self.efficiency():
            found.setdefault(test["id"], test)
        return found

    def is_eff(self, test):
        return any(test is t for t in self.efficiency())

    def gen_source(self):
        return self.secret("gen.py")

    def args_path(self, test):
        """생성 테스트의 입력 파일(캐시). 자식은 케이스 폴더 기준 상대 경로로 읽으므로 실제 경로로 바꿈."""
        return os.path.realpath(runner.generated_args(self.gen_source() or "", grading.gen_spec(test)))

    def inputs(self, test):
        """테스트의 인자 목록들(묶음이 아니면 길이 1). 생성 테스트는 만든 파일을 읽음."""
        if test["id"] not in self._inputs:
            if "gen" in test:
                self._inputs[test["id"]] = study.read_json(self.args_path(test))
            else:
                self._inputs[test["id"]] = [test.get("args")]
        return self._inputs[test["id"]]

    def wrong_source(self, name, lang):
        if name == "alt":
            return self.source("alt" + EXT[lang])
        return self.source("wrong/%s%s" % (name, EXT[lang]))


# 검증기

class Verifier(object):
    def __init__(self, opts, steps=None, out=None):
        self.opts = opts
        self.out = out or sys.stdout
        self.steps = steps
        self.bank = os.path.abspath(opts.bank)
        self.langs = [opts.lang] if opts.lang else list(LANGS)
        self.jobs = max(1, opts.jobs or runner.workers())
        self.tmp = tempfile.mkdtemp(prefix="verify_journey_")
        self.failures = []
        self.warnings = []
        self.lock = threading.Lock()
        self._node = None
        self._node_looked = False
        self._headed = set()
        self.index_changed = True  # --changed 가 없으면 index.json 도 늘 봄

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def wants(self, step):
        if self.steps is not None and step not in self.steps:
            return False
        if self.opts.lang == "javascript" and step not in LANG_STEPS:
            return False
        return True

    # 출력

    def say(self, text):
        with self.lock:
            print(text, file=self.out)

    def head(self, where):
        if where.label not in self._headed:
            self._headed.add(where.label)
            title = ""
            if isinstance(where, Problem) and isinstance(where.raw, dict):
                title = " " + str(where.raw.get("title", ""))
            self.say("[%s]%s" % (where.label, title))

    def fail(self, where, step, message):
        with self.lock:
            self.failures.append((where.label, step, message))
        self.head(where)
        self.say("  실패 %d %s: %s" % (step, STEP_NAMES.get(step, ""), message))

    def warn(self, where, step, message):
        with self.lock:
            self.warnings.append((where.label, step, message))
        self.head(where)
        self.say("  경고 %d %s: %s" % (step, STEP_NAMES.get(step, ""), message))

    def note(self, where, message):
        self.head(where)
        self.say("  " + message)

    # 실행

    def node_path(self):
        if not self._node_looked:
            self._node_looked = True
            found = node_finder.find()
            self._node = found["path"] if found else None
            if not self._node:
                self.failures.append(("node", 7, "Node.js 를 찾지 못했습니다."))
                self.say("실패: Node.js %d 이상을 찾지 못해 JavaScript 단계를 돌리지 못했습니다. --lang python 으로 Python 단계만 "
                         "돌릴 수 있습니다." % node_finder.MIN_MAJOR)
        return self._node

    def run(self, lang, source, cases, workers=1, python=None, node=None):
        """케이스 목록을 한 작업 폴더에서 돌림. 실행하지 못하면 결과 자리에 None."""
        if not cases:
            return []
        if lang == "javascript" and not node:
            node = self.node_path()
            if not node:
                return [None] * len(cases)
        try:
            with runner.workspace() as folder:
                workdir = os.path.realpath(folder)
                runner.prepare(lang, source, workdir)
                return runner.run_cases(lang, source, cases, workers, None, None, node, python, workdir)
        except (OSError, RuntimeError) as error:
            self.say("실패: %s 를 실행하지 못했습니다: %s" % (os.path.basename(source), error))
            with self.lock:
                self.failures.append(("run", 7, str(error)))
            return [None] * len(cases)

    def case(self, p, test, limit_ms, kill_ms=None, expect=True):
        """채점과 같은 grading.make_case 로 만듦. 기대값이 없는 테스트(4단계가 따로 알림)와 expect=False(--fill)는
        기대값 없이 돌려 답만 받음. 생성 입력은 자식이 케이스 폴더 기준으로 읽으므로 실제 경로로 바꿈."""
        unchecked = not expect or ("expected" not in test and not test.get("expected_sha"))
        case = grading.make_case(dict(test, expected=None) if unchecked else test, p.gen_source(), limit_ms,
                                 kill_ms or runner.grade_kill_ms(limit_ms))
        if unchecked:
            del case["expected"]
        if "args_path" in case:
            case["args_path"] = os.path.realpath(case["args_path"])
        return case

    def run_tests(self, p, lang, source, tests, limit_ms, kill_ms=None, expect=True, python=None, node=None):
        """테스트 목록을 돌려 {id: 결과}. 정확성 테스트는 jobs 개씩 동시에, 효율성 테스트는 하나씩 돌림.
        fatal 은 grading 과 같게 봄. 처음 돈 케이스가 fatal 이면 실행 전체가 실행 전 오류라 남은 테스트는 돌리지 않고
        같은 fatal 로 채우고, 그 뒤에 난 fatal 은 그 줄의 런타임 에러로 바꿈."""
        groups = ([], [])
        for test in tests:
            try:
                case = self.case(p, test, limit_ms, kill_ms, expect)
            except (runner.GenError, OSError, ValueError) as error:
                if test["id"] not in p.gen_failed:
                    p.gen_failed.add(test["id"])
                    self.fail(p, 6, "%s 의 입력을 만들지 못했습니다: %s" % (test["id"], str(error).strip()[-400:]))
                continue
            groups[1 if p.is_eff(test) else 0].append((test["id"], case))
        found, whole_fatal = {}, None
        for group, workers in ((groups[0], self.jobs), (groups[1], 1)):
            if not group:
                continue
            ids = [test_id for test_id, _ in group]
            if whole_fatal is not None:
                found.update((test_id, dict(whole_fatal)) for test_id in ids)
                continue
            raws = self.run(lang, source, [case for _, case in group], workers, python, node)
            if not found and raws[0] is not None and raws[0]["status"] == "fatal":
                whole_fatal = raws[0]
            else:
                raws = [grading._as_runtime(raw) if raw is not None else None for raw in raws]
            found.update(zip(ids, raws))
        return found

    def reference(self, p, tests):
        """solution.py 의 답(호출마다 정규 JSON). 기대값과 맞은 것만 돌려줌. 7단계가 이미 잰 것은 다시 돌리지 않음."""
        missing = [t for t in tests if t["id"] not in p.references]
        source = p.source("solution.py")
        if missing and source:
            for test_id, raw in self.run_tests(p, "python", source, missing, WIDE_MS, WIDE_MS).items():
                if raw and raw["status"] == "pass" and raw["values"] is not None:
                    p.references[test_id] = raw["values"]
        return p.references

    def generate(self, gen_source, specs, validate_source=None):
        """명세마다 genrun 자식으로 입력을 새로 만듦(캐시 안 씀). [(경로, 보고 | None, 오류 | None)]."""
        folder = tempfile.mkdtemp(prefix="gen_", dir=self.tmp)

        def one(index):
            path = os.path.realpath(os.path.join(folder, "%d.json" % index))
            try:
                return path, runner.generate_to(gen_source, specs[index], path, validate_source), None
            except (runner.GenError, OSError) as error:
                return path, None, str(error).strip()[-600:]

        with ThreadPoolExecutor(max_workers=self.jobs) as pool:
            return list(pool.map(one, range(len(specs))))

    # 전체 흐름

    def targets(self, tokens):
        """[(던전, 문제 목록 | None)]. None 은 던전 전체."""
        try:
            ordered = [entry["id"] for entry in bank.read_index(self.bank)]
        except bank.BankError:
            ordered = []
        try:
            folders = sorted(name for name in os.listdir(self.bank) if os.path.isdir(os.path.join(self.bank, name)))
        except OSError:
            folders = []
        ready = [did for did in ordered + [f for f in folders if f not in ordered]
                 if bank.is_ready(did, self.bank)]
        picked = []
        if tokens:
            for token in tokens:
                parts = [part for part in token.replace("\\", "/").split("/") if part]
                if not parts or len(parts) > 2 or parts[0] not in ready:
                    raise SystemExit("출제된 던전이나 문제가 아닙니다: %s (은행 %s)" % (token, self.bank))
                found = next((item for item in picked if item[0] == parts[0]), None)
                if found is None:
                    found = [parts[0], [] if len(parts) == 2 else None]
                    picked.append(found)
                if len(parts) == 2 and found[1] is not None and parts[1] not in found[1]:
                    found[1].append(parts[1])
                elif len(parts) == 1:
                    found[1] = None
        else:
            picked = [[did, None] for did in ready]
        if self.opts.changed:
            everything, dids, self.index_changed = changed_scope(self.bank, self.opts.changed)
            if not everything:
                picked = [item for item in picked if item[0] in dids]
        return [(did, pids) for did, pids in picked]

    def mode(self):
        o = self.opts
        if o.fill:
            return "fill"
        if o.timing:
            return "timing"
        if o.styles:
            return "styles"
        if o.alt:
            return "alt"
        return "check"

    def main(self, tokens):
        mode = self.mode()
        targets = self.targets(tokens)
        if mode == "alt" and (len(targets) != 1 or not targets[0][1] or len(targets[0][1]) != 1):
            raise SystemExit("--alt 는 문제 하나(d01/p3 처럼)에만 씁니다.")
        index_only = mode == "check" and self.index_changed and self.wants(1)
        if not targets and not index_only:
            self.say("검증할 던전이 없습니다(바뀐 던전이 없거나 출제된 던전이 없습니다).")
            return 0
        if mode == "check":
            check_index(self)
        problems = 0
        for did, pids in targets:
            d = Dungeon(self, did)
            for step, message in d.errors:
                self.fail(d, step, message)
            whole = pids is None
            before = len(self.failures)
            if mode == "check":
                check_dungeon(self, d)
            chosen = []
            for pid in (d.ids() if whole else pids):
                item = next((item for item in d.items if item["id"] == pid), None)
                if item is None:
                    self.fail(d, 1, "meta.json 에 문제 %s 가 없습니다." % pid)
                    continue
                if not os.path.isdir(os.path.join(d.dir, pid)):
                    continue
                chosen.append(Problem(self, d, item))
            for p in chosen:
                problems += 1
                started = len(self.failures)
                if mode == "fill":
                    guarded(self, p, 16, fill_problem)
                elif mode == "timing":
                    guarded(self, p, 15, time_problem)
                elif mode == "styles":
                    if self.wants(13):
                        guarded(self, p, 13, step_styles)
                elif mode == "alt":
                    alt_dir = os.path.abspath(self.opts.alt)
                    if self.wants(9):
                        guarded(self, p, 9, step_stress, alt_dir)
                    if self.wants(10):
                        guarded(self, p, 10, step_alt, alt_dir)
                else:
                    check_problem(self, p)
                if self.opts.require_review:
                    guarded(self, p, 18, check_problem_review)
                if self.opts.sign and not whole:
                    if len(self.failures) == started:
                        sign(self, p, problem_files(p))
                    else:
                        self.say("  검증을 통과하지 못해 %s 에 서명하지 않았습니다." % p.label)
            if whole and self.opts.require_review:
                check_dungeon_review(self, d)
            if whole and self.opts.sign:
                if len(self.failures) == before:
                    sign(self, d, dungeon_files(d))
                else:
                    self.say("  검증을 통과하지 못해 %s 에 서명하지 않았습니다." % d.label)
        if self.failures:
            self.say("실패 %d건, 경고 %d건." % (len(self.failures), len(self.warnings)))
            return 1
        tail = ", 경고 %d건" % len(self.warnings) if self.warnings else ""
        if not targets:
            self.say("OK: index.json 을 검증했습니다(바뀐 던전은 없습니다%s)." % tail)
            return 0
        self.say("OK: 문제 %d개를 검증했습니다%s." % (problems, tail))
        return 0


class Place(object):
    """index.json 처럼 문제나 던전이 아닌 곳의 실패를 찍을 때 쓰는 이름표."""

    def __init__(self, label):
        self.label = label


# 던전 단위

def check_index(v):
    if not v.wants(1):
        return
    where = Place("index.json")
    try:
        data = study.read_json(os.path.join(v.bank, bank.INDEX_NAME))
    except (OSError, ValueError) as error:
        v.fail(where, 1, "index.json 을 읽을 수 없습니다: %s" % error)
        return
    if not isinstance(data, dict) or data.get("format") != 1 or not isinstance(data.get("dungeons"), list):
        v.fail(where, 1, "index.json 은 format 1 과 dungeons 목록이 있어야 합니다.")
        return
    entries = data["dungeons"]
    if len(entries) != 16:
        v.fail(where, 1, "던전이 %d개입니다(16개여야 합니다)." % len(entries))
    ids, nos = [], []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            v.fail(where, 1, "%d번째 항목이 객체가 아닙니다." % (index + 1))
            continue
        did, no = entry.get("id"), entry.get("no")
        if not isinstance(did, str) or not did:
            v.fail(where, 1, "%d번째 항목의 id 가 없습니다." % (index + 1))
        if not isinstance(no, int) or isinstance(no, bool):
            v.fail(where, 1, "%s 의 no 가 정수가 아닙니다." % did)
        for key in ("title", "topic", "boss_target"):
            if not isinstance(entry.get(key), str) or not entry.get(key):
                v.fail(where, 1, "%s 의 %s 가 비었습니다." % (did, key))
        if not isinstance(entry.get("prereq", []), list):
            v.fail(where, 1, "%s 의 prereq 가 목록이 아닙니다." % did)
        if "final" in entry and not isinstance(entry["final"], bool):
            v.fail(where, 1, "%s 의 final 은 true/false 여야 합니다." % did)
        ids.append(did)
        nos.append(no)
    for name, items in (("id", ids), ("no", nos)):
        twice = sorted(set(str(x) for x in items if items.count(x) > 1))
        if twice:
            v.fail(where, 1, "같은 %s 가 두 번 이상 있습니다: %s" % (name, ", ".join(twice)))
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("prereq"), list):
            unknown = [str(x) for x in entry["prereq"] if x not in ids]
            if unknown:
                v.fail(where, 1, "%s 의 prereq 에 없는 던전이 있습니다: %s" % (entry.get("id"), ", ".join(unknown)))
    try:
        folders = sorted(name for name in os.listdir(v.bank) if bank.is_ready(name, v.bank))
    except OSError:
        folders = []
    stray = [name for name in folders if name not in ids]
    if stray:
        v.fail(where, 1, "index.json 에 없는 던전 폴더에 meta.json 이 있습니다: %s" % ", ".join(stray))


def check_dungeon(v, d):
    if v.wants(1):
        check_meta(v, d)
    if v.wants(2):
        sealed = os.path.join(d.dir, bank.SEALED_NAME)
        if os.path.isfile(sealed) and os.path.getsize(sealed) > SEALED_LIMIT:
            v.fail(d, 2, "sealed.json 이 %.1fKB 입니다(한도 %dKB)." % (os.path.getsize(sealed) / KB, SEALED_LIMIT // KB))
    if v.wants(14):
        check_assets(v, d)


def check_meta(v, d):
    meta = d.meta
    if not isinstance(meta, dict):
        return
    if meta.get("format") != 1:
        v.fail(d, 1, "meta.json 의 format 은 1 이어야 합니다.")
    skills = meta.get("skills", [])
    if not isinstance(skills, list) or not all(isinstance(s, str) and s.strip() for s in skills):
        v.fail(d, 1, "meta.json 의 skills 는 글의 목록이어야 합니다.")
    items = meta.get("problems")
    if not isinstance(items, list) or not items:
        v.fail(d, 1, "meta.json 에 problems 목록이 없습니다.")
        return
    ids = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            v.fail(d, 1, "problems 의 %d번째 항목이 객체가 아닙니다." % (index + 1))
            continue
        pid = item.get("id")
        if not isinstance(pid, str) or not bank.PROBLEM_ID.match(pid):
            v.fail(d, 1, "문제 id %r 는 p1~p9 나 boss 여야 합니다." % (pid,))
        if not isinstance(item.get("no"), str) or not item.get("no"):
            v.fail(d, 1, "%s 의 no(화면 번호)가 없습니다." % pid)
        if item.get("role") not in bank.ROLES:
            v.fail(d, 1, "%s 의 role %r 는 %s 가운데 하나여야 합니다." % (pid, item.get("role"), " | ".join(bank.ROLES)))
        if isinstance(pid, str) and not os.path.isdir(os.path.join(d.dir, pid)):
            v.fail(d, 1, "문제 폴더 %s 가 없습니다." % pid)
        ids.append(pid)
    twice = sorted(set(str(x) for x in ids if ids.count(x) > 1))
    if twice:
        v.fail(d, 1, "같은 문제 id 가 두 번 있습니다: %s" % ", ".join(twice))
    roles = [item.get("role") for item in items if isinstance(item, dict)]
    if roles.count("boss") != 1 or roles[-1] != "boss":
        v.fail(d, 1, "보스 문제는 정확히 하나이고 마지막에 있어야 합니다.")


def dungeon_refs(d):
    """던전의 지문·힌트·해설·intro.md 가 가리키는 그림 경로 → 가리킨 파일 이름 목록."""
    refs = {}
    try:
        intro = study.read_text(os.path.join(d.dir, "intro.md"))
    except (OSError, ValueError):
        intro = ""
    for ref in image_refs(intro):
        refs.setdefault(ref, []).append("intro.md")
    for pid in bank.problem_ids(d.dir):
        try:
            statement = study.read_text(os.path.join(d.dir, pid, "problem.md"))
        except (OSError, ValueError):
            statement = ""
        texts = [("problem.md", statement)] + [(name, d.secrets.get("%s/%s" % (pid, name), "")) for name in ("hints.md", "explain.md")]
        for name, text in texts:
            for ref in image_refs(text):
                refs.setdefault(ref, []).append("%s/%s" % (pid, name))
    return refs


def check_assets(v, d):
    folder = os.path.join(d.dir, "assets")
    if not os.path.isdir(folder):
        return
    refs = dungeon_refs(d)
    total = 0
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        total += os.path.getsize(path)
        rel = "assets/" + name
        if not name.lower().endswith((".gif", ".png")):
            v.warn(d, 14, "그림이 아닌 파일이 있습니다: %s" % rel)
            continue
        for problem in image_problems(path):
            v.fail(d, 14, "%s: %s" % (rel, problem))
        if rel not in refs:
            v.warn(d, 14, "아무 글도 가리키지 않는 그림입니다: %s" % rel)
    if total > LIMITS["total_bytes"]:
        v.fail(d, 14, "assets 합계가 %.1fKB 입니다(한도 %dKB)." % (total / KB, LIMITS["total_bytes"] // KB))


# 문제 단위

def check_problem(v, p):
    v.head(p)
    for step, message in p.errors:
        if v.steps is None or step in v.steps:
            v.fail(p, step, message)
    if not isinstance(p.raw, dict):
        return
    steps = [(1, step_format), (2, step_secrets), (3, step_statement), (4, step_composition), (5, step_validate),
             (6, step_determinism), (7, step_reference), (8, step_brute), (9, step_stress), (10, step_alt),
             (11, step_starter), (12, step_known), (13, step_styles), (14, step_images)]
    for number, function in steps:
        if v.wants(number):
            guarded(v, p, number, function)


def guarded(v, p, number, function, *args):
    """단계 하나를 돌림. 앞 단계가 잡은 형식 오류 때문에 예외가 나도 다른 문제와 단계는 계속 봄."""
    try:
        function(v, p, *args)
    except Exception as error:
        v.fail(p, number, "이 단계를 끝까지 돌리지 못했습니다(앞의 실패를 먼저 고치세요): %s: %s" % (type(error).__name__, error))


def js_name_problem(name):
    if not JS_NAME.match(name):
        return "JavaScript 식별자가 아닙니다"
    if name in JS_RESERVED:
        return "JavaScript 예약어입니다"
    return None


def step_format(v, p):
    raw = p.raw
    if raw.get("format") != 1:
        v.fail(p, 1, "problem.json 의 format 은 1 이어야 합니다.")
    if not isinstance(raw.get("title"), str) or not raw.get("title", "").strip():
        v.fail(p, 1, "problem.json 의 title 에 문제 제목을 적어 주세요.")
    if not isinstance(raw.get("tier", ""), str):
        v.fail(p, 1, "tier 는 글이어야 합니다.")
    signature = raw.get("signature")
    params = signature.get("params") if isinstance(signature, dict) else None
    if not isinstance(params, list) or not params:
        v.fail(p, 1, "signature.params 가 비었습니다.")
        params = []
    names = []
    for param in params:
        if not isinstance(param, dict) or not isinstance(param.get("name"), str):
            v.fail(p, 1, "signature.params 의 항목은 {name, type} 이어야 합니다.")
            continue
        name = param["name"]
        names.append(name)
        if not name.isidentifier() or keyword.iskeyword(name):
            v.fail(p, 1, "매개변수 이름 %s 는 Python 식별자가 아니거나 예약어입니다." % name)
        why = js_name_problem(name)
        if why:
            v.fail(p, 1, "매개변수 이름 %s: %s." % (name, why))
        try:
            values.parse_type(str(param.get("type")))
        except ValueError as error:
            v.fail(p, 1, "매개변수 %s 의 %s" % (name, error))
    if len(set(names)) != len(names):
        v.fail(p, 1, "매개변수 이름이 겹칩니다: %s" % ", ".join(names))
    try:
        values.parse_type(str(signature.get("returns") if isinstance(signature, dict) else None))
    except ValueError as error:
        v.fail(p, 1, "반환형의 %s" % error)
    limits = raw.get("time_limit_ms")
    for lang in LANGS:
        limit = limits.get(lang) if isinstance(limits, dict) else None
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            v.fail(p, 1, "time_limit_ms.%s 가 양의 정수가 아닙니다." % lang)
    score = raw.get("score")
    if score is not None:
        try:
            if abs(float(score["accuracy"]) + float(score["efficiency"]) - 100) > 1e-9:
                v.fail(p, 1, "score 의 accuracy 와 efficiency 를 더하면 100 이어야 합니다.")
        except (TypeError, KeyError, ValueError):
            v.fail(p, 1, "score 는 {accuracy, efficiency} 여야 합니다.")
    if not isinstance(raw.get("examples"), list):
        v.fail(p, 1, "examples 가 목록이 아닙니다.")
    else:
        for index, ex in enumerate(raw["examples"]):
            if not isinstance(ex, dict) or not isinstance(ex.get("args"), list) or "expected" not in ex:
                v.fail(p, 1, "입출력 예 %d 는 {args, expected} 여야 합니다." % (index + 1))
    ids = p.dungeon.ids()
    for key in ("prep", "uses"):
        listed = raw.get(key, [])
        if not isinstance(listed, list):
            v.fail(p, 1, "%s 는 문제 id 의 목록이어야 합니다." % key)
            continue
        unknown = [str(x) for x in listed if x not in ids or x == p.pid]
        if unknown:
            v.fail(p, 1, "%s 에 이 던전에 없는 문제가 있습니다: %s" % (key, ", ".join(unknown)))
    if raw.get("uses") and p.role != "boss":
        v.fail(p, 1, "uses 는 보스 문제에만 둡니다.")


def step_secrets(v, p):
    for name in REQUIRED:
        if p.secret(name) is None:
            v.fail(p, 2, "%s 가 없습니다." % name)
    if v.opts.sign or v.opts.require_review:
        for name in REVIEW_REQUIRED:
            if p.secret(name) is None:
                v.fail(p, 2, "%s 가 없습니다. 서명하려면 다시 푼 풀이를 문제 폴더에 넣어야 합니다." % name)
    hints = p.secret("hints.md")
    if hints is not None and not 2 <= len(bank.parse_hints(hints)) <= 4:
        v.fail(p, 2, "hints.md 에 ## 1, ## 2 … 절이 %d개입니다(2~4개)." % len(bank.parse_hints(hints)))
    gen_source = p.gen_source()
    gen_tests = [t for t in p.accuracy() + p.efficiency() if "gen" in t]
    if gen_tests:
        if gen_source is None:
            v.fail(p, 2, "생성 테스트가 있는데 gen.py 가 없습니다.")
        else:
            try:
                defined = {item.name for item in ast.parse(gen_source).body if isinstance(item, ast.FunctionDef)}
            except SyntaxError as error:
                v.fail(p, 2, "gen.py 를 읽을 수 없습니다: %s" % error)
                defined = None
            if defined is not None:
                missing = sorted({str(t["gen"]) for t in gen_tests} - defined)
                if missing:
                    v.fail(p, 2, "gen.py 에 함수가 없습니다: %s" % ", ".join(missing))
    used = set()
    for name, entry in sorted(p.wrong.items()):
        langs = entry.get("langs") if isinstance(entry, dict) else None
        if not isinstance(langs, list) or not langs or not set(langs) <= set(LANGS):
            v.fail(p, 2, "wrong.json 의 %s: langs 는 python, javascript 가운데 하나 이상이어야 합니다." % name)
            continue
        for lang in langs:
            rel = ("alt" + EXT[lang]) if name == "alt" else "wrong/%s%s" % (name, EXT[lang])
            used.add(rel)
            if p.secret(rel) is None:
                v.fail(p, 2, "wrong.json 의 %s 에 맞는 파일 %s 가 없습니다." % (name, rel))
    stray = [rel for rel in p.secret_names() if rel.startswith("wrong/") and rel not in used]
    if stray:
        v.warn(p, 2, "wrong.json 에 적지 않은 파일이 있습니다: %s" % ", ".join(stray))
    extra = p.extra
    if extra is not None and not isinstance(extra, dict):
        v.fail(p, 2, "extra.json 은 객체여야 합니다.")
        extra = None
    extra = extra or {}
    if p.role == "boss":
        if not isinstance(extra.get("parts"), list) or not extra.get("parts"):
            v.fail(p, 2, "보스의 extra.json 에 parts(합성표)가 없습니다.")
        if not isinstance(extra.get("boss_new"), str) or not extra.get("boss_new", "").strip():
            v.fail(p, 2, "보스의 extra.json 에 boss_new 가 없습니다.")
    ids = p.dungeon.ids()
    for index, part in enumerate(extra.get("parts") or []):
        if not isinstance(part, dict) or not isinstance(part.get("text"), str) or not isinstance(part.get("from"), list):
            v.fail(p, 2, "extra.json 의 parts %d번째는 {text, from: [문제 id]} 여야 합니다." % (index + 1))
            continue
        unknown = [str(x) for x in part["from"] if x not in ids]
        if unknown:
            v.fail(p, 1, "extra.json 의 parts 에 이 던전에 없는 문제가 있습니다: %s" % ", ".join(unknown))
    for index, item in enumerate(extra.get("similar") or []):
        if not isinstance(item, dict) or item.get("site") not in ("boj", "programmers") or not item.get("title"):
            v.fail(p, 2, "extra.json 의 similar %d번째는 site(boj | programmers)와 title 이 있어야 합니다." % (index + 1))
        elif item["site"] == "boj" and not isinstance(item.get("id"), int):
            v.fail(p, 2, "extra.json 의 similar %d번째(BOJ)에 문제 번호 id 가 없습니다." % (index + 1))


def step_statement(v, p):
    if p.markdown is None:
        return
    sections = markdown_sections(p.markdown)
    titles = [title for title, _ in sections]
    positions = []
    for heading in HEADINGS:
        if heading not in titles:
            v.fail(p, 3, "problem.md 에 ## %s 가 없습니다." % heading)
        else:
            positions.append(titles.index(heading))
    if positions != sorted(positions):
        v.fail(p, 3, "problem.md 의 제목 순서가 %s 가 아닙니다." % " → ".join(HEADINGS))
    params = p.params()
    blocks = section(sections, "함수")
    py = [b["text"] for b in blocks if b["t"] == "code" and b["lang"] in ("python", "py")]
    js = [b["text"] for b in blocks if b["t"] == "code" and b["lang"] in ("javascript", "js")]
    if not py:
        v.fail(p, 3, "## 함수 에 ```python 블록이 없습니다.")
    else:
        names = python_params(py[0])
        if names is None:
            v.fail(p, 3, "## 함수 의 Python 블록에서 def solution(...) 을 읽지 못했습니다.")
        elif names != params:
            v.fail(p, 3, "## 함수 의 Python 매개변수 %s 가 signature 의 %s 와 다릅니다." % (", ".join(names), ", ".join(params)))
    if not js:
        v.fail(p, 3, "## 함수 에 ```javascript 블록이 없습니다.")
    else:
        found = JS_FUNCTION.search(js[0])
        if not found:
            v.fail(p, 3, "## 함수 의 JavaScript 블록에서 function solution(...) 을 읽지 못했습니다.")
        else:
            names = [part.split("=")[0].strip() for part in found.group(1).split(",") if part.strip()]
            if names != params:
                v.fail(p, 3, "## 함수 의 JavaScript 매개변수 %s 가 signature 의 %s 와 다릅니다." % (", ".join(names), ", ".join(params)))
    tables = [b for b in section(sections, "입출력 예") if b["t"] == "table"]
    if not tables:
        v.fail(p, 3, "## 입출력 예 에 표가 없습니다.")
        return
    table = tables[0]
    head = [mdlite.inline_plain(cell).strip() for cell in table["head"]]
    if head != params + ["result"]:
        v.fail(p, 3, "입출력 예 표의 머리 %s 가 매개변수 이름 + result(%s)와 다릅니다." % (" | ".join(head), " | ".join(params + ["result"])))
        return
    examples = p.examples()
    if len(table["rows"]) != len(examples):
        v.fail(p, 3, "입출력 예 표의 행이 %d개이고 examples 는 %d개입니다." % (len(table["rows"]), len(examples)))
    for index, (row, ex) in enumerate(zip(table["rows"], examples)):
        cells = []
        for cell in row:
            try:
                cells.append(values.parse_literal(mdlite.inline_plain(cell)))
            except ValueError:
                v.fail(p, 3, "입출력 예 표 %d행의 칸 %r 를 값으로 읽지 못했습니다." % (index + 1, cell))
                cells = None
                break
        if cells is None:
            continue
        want = list(ex["args"]) + [ex["expected"]]
        if values.canonical(cells) != values.canonical(want):
            v.fail(p, 3, "입출력 예 표 %d행 %s 이 examples 의 %s 와 다릅니다." % (index + 1, shown(cells), shown(want)))


def python_params(text):
    for source in (text, text.rstrip() + "\n    pass\n"):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for item in tree.body:
            if isinstance(item, ast.FunctionDef) and item.name == "solution":
                return [arg.arg for arg in item.args.posonlyargs + item.args.args]
        return None
    return None


def step_composition(v, p):
    examples, accuracy = p.examples(), p.accuracy()
    named = [t for t in accuracy if "count" not in t]
    bundles = [t for t in accuracy if t.get("count") == BUNDLE_SIZE]
    counts = ["Python %d줄" % len(p.eff_tests("python")), "JavaScript %d줄" % len(p.eff_tests("javascript"))]
    v.note(p, "입출력 예 %d개, 정확성 %d줄(이름 붙인 테스트 %d개, %d건 묶음 %d줄), 효율성 %s" % (
        len(examples), len(accuracy), len(named), BUNDLE_SIZE, len(bundles), ", ".join(counts)))
    if not EXAMPLES[0] <= len(examples) <= EXAMPLES[1]:
        v.fail(p, 4, "입출력 예가 %d개입니다(%d~%d개)." % (len(examples), EXAMPLES[0], EXAMPLES[1]))
    if not ACCURACY[0] <= len(accuracy) <= ACCURACY[1]:
        v.fail(p, 4, "정확성 테스트가 %d줄입니다(%d~%d줄)." % (len(accuracy), ACCURACY[0], ACCURACY[1]))
    if len(named) < NAMED_MIN:
        v.fail(p, 4, "이름 붙인 정확성 테스트(count 없음)가 %d개입니다(%d개 이상)." % (len(named), NAMED_MIN))
    if len(bundles) != BUNDLE_LINES:
        v.fail(p, 4, "%d건 묶음(count: %d)이 %d줄입니다(%d줄)." % (BUNDLE_SIZE, BUNDLE_SIZE, len(bundles), BUNDLE_LINES))
    for lang in LANGS:
        count = len(p.eff_tests(lang))
        if not EFFICIENCY[0] <= count <= EFFICIENCY[1]:
            v.fail(p, 4, "%s 효율성 테스트가 %d줄입니다(%d~%d줄)." % (LANG_LABEL[lang], count, EFFICIENCY[0], EFFICIENCY[1]))
    raw_tests = p.tests if isinstance(p.tests, dict) else {}
    for group in ("accuracy", "efficiency"):
        if any(not isinstance(t, dict) or not isinstance(t.get("id"), str) for t in raw_tests.get(group) or []):
            v.fail(p, 4, "tests.json 의 %s 에 id 가 없는 항목이 있습니다." % group)
    ids = [t["id"] for t in p.acc_tests() + p.efficiency()]
    twice = sorted(set(x for x in ids if ids.count(x) > 1))
    if twice:
        v.fail(p, 4, "테스트 id 가 겹칩니다(입출력 예는 ex1, ex2 … 를 씀): %s" % ", ".join(twice))
    bad_ids = [x for x in ids if not TEST_ID.match(x)]
    if bad_ids:
        v.fail(p, 4, "테스트 id 는 영문 소문자·숫자·밑줄만 씁니다: %s" % ", ".join(bad_ids))
    kinds, returns = p.kinds(), p.returns()
    for index, ex in enumerate(examples):
        check_literal(v, p, "입출력 예 %d" % (index + 1), ex["args"], kinds)
        check_expected_value(v, p, "입출력 예 %d" % (index + 1), ex["expected"], returns, None)
    for test in accuracy + p.efficiency():
        check_test(v, p, test, kinds, returns)
    if any(t.get("depth") == "limit" for t in accuracy + p.efficiency()):
        heavy = [name for name, entry in p.wrong.items() if isinstance(entry, dict) and entry.get("style") == "heavy"
                 and "javascript" in (entry.get("langs") or [])]
        if not heavy:
            v.fail(p, 4, "depth: limit 테스트가 있는데 wrong.json 에 JavaScript heavy 항목이 없습니다.")


def check_literal(v, p, where, args, kinds):
    if kinds is None:
        return
    if not isinstance(args, list) or len(args) != len(kinds):
        v.fail(p, 4, "%s 의 인자가 매개변수 %d개와 맞지 않습니다." % (where, len(kinds)))
        return
    for index, (value, kind) in enumerate(zip(args, kinds)):
        problem = values.check(value, kind)
        if problem:
            v.fail(p, 4, "%s 의 %d번째 인자: %s" % (where, index + 1, problem))


def check_expected_value(v, p, where, value, returns, count):
    if returns is None:
        return
    try:
        values.parse_type(returns)
    except ValueError:
        return
    if count:
        if not isinstance(value, list) or len(value) != count:
            v.fail(p, 4, "%s 의 expected 는 결과 %d개의 목록이어야 합니다." % (where, count))
            return
        items = value
    else:
        items = [value]
    for item in items:
        problem = values.check(item, returns)
        if problem:
            v.fail(p, 4, "%s 의 expected: %s" % (where, problem))
            return


def check_test(v, p, test, kinds, returns):
    where = test["id"]
    if not isinstance(test.get("name"), str) or not test.get("name", "").strip():
        v.fail(p, 4, "%s 에 name(경계 사례 설명)이 없습니다." % where)
    has_args, has_gen = "args" in test, "gen" in test
    if has_args == has_gen:
        v.fail(p, 4, "%s 는 args 와 gen 가운데 하나만 둡니다." % where)
    if has_args:
        check_literal(v, p, where, test["args"], kinds)
    if has_gen:
        if not isinstance(test.get("gen"), str) or not isinstance(test.get("seed"), int) or isinstance(test.get("seed"), bool):
            v.fail(p, 4, "%s 의 gen 은 함수 이름, seed 는 정수여야 합니다." % where)
        if not isinstance(test.get("params", {}), dict):
            v.fail(p, 4, "%s 의 params 는 객체여야 합니다." % where)
    count = test.get("count")
    if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 2):
        v.fail(p, 4, "%s 의 count 는 2 이상의 정수여야 합니다." % where)
        count = None
    if count and not has_gen:
        v.fail(p, 4, "%s 는 묶음(count)인데 gen 이 없습니다." % where)
    if "expected" in test:
        check_expected_value(v, p, where, test["expected"], returns, count)
        if len(values.canonical(test["expected"])) > LITERAL_MAX:
            v.fail(p, 4, "%s 의 expected 가 %d자를 넘습니다. expected_sha 로 바꾸세요." % (where, LITERAL_MAX))
    elif test.get("expected_sha"):
        if not isinstance(test["expected_sha"], str) or not SHA.match(test["expected_sha"]):
            v.fail(p, 4, "%s 의 expected_sha 는 sha256 16진수 64자여야 합니다." % where)
    else:
        v.fail(p, 4, "%s 에 expected 도 expected_sha 도 없습니다. --fill 로 채우세요." % where)
    if test.get("depth") not in DEPTHS:
        v.fail(p, 4, "%s 의 depth 는 limit 나 chain 만 씁니다." % where)
    if p.is_eff(test):
        if not isinstance(test.get("stress"), dict) or not test.get("stress"):
            v.fail(p, 4, "효율성 테스트 %s 에 stress(줄인 생성기 매개변수)가 없습니다." % where)
        langs = test.get("langs")
        if langs is not None and (not isinstance(langs, list) or not langs or not set(langs) <= set(LANGS)):
            v.fail(p, 4, "%s 의 langs 는 python, javascript 만 씁니다." % where)


def step_validate(v, p):
    space = p.module("validate.py", 5)
    if space is None:
        return
    validate = space.get("validate")
    if not callable(validate):
        v.fail(p, 5, "validate.py 에 validate 함수가 없습니다.")
        return

    def run(args):
        try:
            return validate(*copy.deepcopy(args))
        except Exception as error:
            return "validate 가 예외를 냈습니다: %s: %s" % (type(error).__name__, error)

    for index, ex in enumerate(p.examples()):
        message = run(ex["args"])
        if message:
            v.fail(p, 5, "입출력 예 %d 가 제한사항을 어깁니다: %s" % (index + 1, message))
    for test in p.accuracy():
        if "args" in test and isinstance(test["args"], list):
            message = run(test["args"])
            if message:
                v.fail(p, 5, "%s 가 제한사항을 어깁니다: %s" % (test["id"], message))
    lines = constraint_count(p.markdown or "")
    descriptive = space.get("DESCRIPTIVE") or {}
    invalid = (p.tests or {}).get("invalid") if isinstance(p.tests, dict) else None
    if not isinstance(invalid, list) or not invalid:
        v.fail(p, 5, "tests.json 에 invalid(제한사항을 일부러 어긴 입력)가 없습니다.")
        invalid = []
    covered = set(int(n) for n in descriptive if isinstance(n, int))
    for index, entry in enumerate(invalid):
        line = entry.get("line") if isinstance(entry, dict) else None
        if not isinstance(line, int) or isinstance(line, bool) or not isinstance(entry.get("args"), list):
            v.fail(p, 5, "invalid %d번째에 line(제한사항 번호)과 args 가 있어야 합니다." % (index + 1))
            continue
        if not 1 <= line <= lines:
            v.fail(p, 5, "invalid %d번째의 line %d 이 제한사항 줄 수 %d 를 벗어납니다." % (index + 1, line, lines))
        covered.add(line)
        message = run(entry["args"])
        if not isinstance(message, str) or not message.startswith("%d번 줄:" % line):
            v.fail(p, 5, "invalid %d번째(%d번 줄)에 validate 가 \"%d번 줄:\" 로 시작하는 문구를 돌려주지 않았습니다: %r"
                   % (index + 1, line, line, message))
    missing = [str(n) for n in range(1, lines + 1) if n not in covered]
    if missing:
        v.fail(p, 5, "제한사항 %s번 줄에 invalid 도 DESCRIPTIVE 도 없습니다." % ", ".join(missing))


def step_determinism(v, p):
    source = p.gen_source()
    if source is None:
        return
    found = gen_violations(source)
    for problem in found:
        v.fail(p, 6, "gen.py: %s (journey.gen 만 import 하고 set·frozenset·hash 는 쓰지 않습니다)" % problem)
    if found:
        return
    tests = [t for t in p.accuracy() + p.efficiency() if "gen" in t and t["id"] not in p.gen_failed]
    if not tests:
        return
    specs = [grading.gen_spec(t) for t in tests]
    checker = composite_validate(p.kinds(), p.secret("validate.py"))
    first = v.generate(source, specs, checker)
    second = v.generate(source, specs)
    os.makedirs(runner.cache_dir(), exist_ok=True)
    for test, spec, (path_a, report, error_a), (path_b, _, error_b) in zip(tests, specs, first, second):
        error = error_a or error_b
        if error:
            p.gen_failed.add(test["id"])
            v.fail(p, 6, "%s 의 입력을 만들지 못했습니다: %s" % (test["id"], error))
            continue
        invalid = (report or {}).get("invalid")
        if invalid:
            step = 4 if str(invalid.get("message", "")).startswith("타입 검사") else 5
            where = test["id"] if not test.get("count") else "%s 의 %d번째 입력" % (test["id"], invalid.get("index", 0) + 1)
            v.fail(p, step, "%s 이 제한사항을 어깁니다: %s" % (where, invalid.get("message")))
        sha_a, sha_b = file_sha(path_a), file_sha(path_b)
        if sha_a != sha_b:
            v.fail(p, 6, "생성기가 프로세스마다 다른 입력을 냅니다: %s (gen %s, seed %s)" % (test["id"], spec["gen"], spec["seed"]))
            continue
        cached = os.path.join(runner.cache_dir(), runner.cache_key(source, spec) + ".json")
        if os.path.isfile(cached):
            if file_sha(cached) != sha_a:
                v.fail(p, 6, "%s 의 입력이 캐시에 있는 같은 명세의 입력과 다릅니다." % test["id"])
        else:
            partial = "%s.tmp%d" % (cached, os.getpid())
            shutil.copyfile(path_a, partial)
            os.replace(partial, cached)
    runner.trim_cache()


def step_reference(v, p):
    for lang in v.langs:
        name = "solution" + EXT[lang]
        source = p.source(name)
        if source is None:
            continue
        tests = p.tests_for(lang)
        found = v.run_tests(p, lang, source, tests, p.limit(lang))
        bad = []
        for test in tests:
            raw = found.get(test["id"])
            if raw is None:
                continue
            if raw["status"] != "pass":
                bad.append("%s(%s)" % (test["id"], describe(raw)))
                continue
            if raw["peak_mb"] is not None and raw["peak_mb"] >= PEAK_LIMIT_MB:
                v.fail(p, 7, "%s 가 %s 에서 메모리를 %.1fMB 썼습니다(%dMB 미만이어야 합니다)."
                       % (name, test["id"], raw["peak_mb"], PEAK_LIMIT_MB))
            if lang == "python":
                p.references[test["id"]] = raw["values"]
        if bad:
            v.fail(p, 7, "%s 가 통과하지 못한 테스트: %s" % (name, listing(bad, 4)))


def step_brute(v, p):
    space = p.module("brute.py", 8)
    if space is None:
        return
    if not callable(space.get("solution")):
        v.fail(p, 8, "brute.py 에 solution 함수가 없습니다.")
        return
    brute_ok = space.get("brute_ok") or (lambda *args: True)
    certify = None
    if p.secret("certify.py") is not None:
        certify_space = p.module("certify.py", 8)
        certify = certify_space.get("certify") if certify_space else None
        if certify_space is not None and not callable(certify):
            v.fail(p, 8, "certify.py 에 certify 함수가 없습니다.")
    tests = [t for t in p.acc_tests() if t["id"] not in p.gen_failed]
    references = v.reference(p, tests)
    plans, uncovered = [], []
    for test in tests:
        try:
            inputs = p.inputs(test)
        except (runner.GenError, OSError, ValueError) as error:
            v.fail(p, 8, "%s 의 입력을 읽지 못했습니다: %s" % (test["id"], error))
            continue
        reference = references.get(test["id"])
        if reference is None or len(reference) != len(inputs):
            v.warn(p, 8, "%s 는 기준 풀이의 답이 기대값과 맞지 않아 대조하지 않았습니다." % test["id"])
            continue
        picked = []
        for index, args in enumerate(inputs):
            where = test["id"] if len(inputs) == 1 else "%s 의 %d번째 입력" % (test["id"], index + 1)
            try:
                ok = brute_ok(*copy.deepcopy(args))
            except Exception as error:
                v.fail(p, 8, "%s 에서 brute_ok 가 예외를 냈습니다: %s: %s" % (where, type(error).__name__, error))
                continue
            if ok:
                picked.append(index)
            elif certify is None:
                uncovered.append(where)
            else:
                try:
                    message = certify(copy.deepcopy(args), json.loads(reference[index]))
                except Exception as error:
                    message = "certify 가 예외를 냈습니다: %s: %s" % (type(error).__name__, error)
                if message:
                    v.fail(p, 8, "%s 의 정의 대조 실패: %s" % (where, message))
        if picked:
            path = os.path.join(v.tmp, "brute_%s_%s.json" % (p.label.replace("/", "_"), test["id"]))
            study.write_text(path, json.dumps([inputs[i] for i in picked], ensure_ascii=False, separators=(",", ":")))
            case = {"args_path": os.path.realpath(path), "calls": len(picked), "bundle": True, "limit_ms": WIDE_MS,
                    "kill_ms": WIDE_MS}
            plans.append((test, inputs, reference, picked, case))
    if uncovered and p.secret("certify.py") is None:
        v.fail(p, 8, "brute_ok 가 거짓인 입력이 %d개 있는데 certify.py 가 없습니다: %s" % (len(uncovered), listing(uncovered, 3)))
    if not plans:
        return
    raws = v.run("python", p.source("brute.py"), [plan[4] for plan in plans], v.jobs)
    for (test, inputs, reference, picked, _), raw in zip(plans, raws):
        got = raw.get("values") if raw else None
        if raw is None or got is None or len(got) != len(picked):
            v.fail(p, 8, "brute.py 가 %s 에서 끝까지 돌지 못했습니다: %s" % (test["id"], describe(raw)))
            continue
        for answer, index in zip(got, picked):
            if answer != reference[index]:
                where = test["id"] if len(inputs) == 1 else "%s 의 %d번째 입력" % (test["id"], index + 1)
                v.fail(p, 8, "%s 에서 brute.py 의 답 %s 이 기대값 %s 과 다릅니다. 입력 %s" % (
                    where, shown_canonical(answer), shown_canonical(reference[index]), shown(inputs[index])))
                break


def step_stress(v, p, alt_dir=None):
    tests = [t for t in p.efficiency() if isinstance(t.get("stress"), dict) and isinstance(t.get("seed"), int)
             and t["id"] not in p.gen_failed]
    source = p.gen_source()
    if not tests or source is None:
        return
    python_side = "python" in v.langs
    brute = p.module("brute.py", 9) if python_side else None
    brute_ok = (brute.get("brute_ok") or (lambda *args: True)) if brute else None
    programs = [("solution.py", "python", p.source("solution.py"))]
    if python_side and brute and callable(brute.get("solution")):
        programs.insert(0, ("brute.py", "python", p.source("brute.py")))
    for lang in v.langs:
        if lang == "javascript":
            programs.append(("solution.js", "javascript", p.source("solution.js")))
        name = "alt" + EXT[lang]
        programs.append((name, lang, os.path.join(alt_dir, name) if alt_dir else p.source(name)))
    programs = [(label, lang, path) for label, lang, path in programs if path and os.path.isfile(path)]
    checker = composite_validate(p.kinds(), p.secret("validate.py")) if python_side else None
    for test in tests:
        params = dict(test.get("params") or {})
        params.update(test["stress"])
        specs = [{"gen": test.get("gen"), "seed": test["seed"] + k, "params": params, "count": None}
                 for k in range(STRESS_SEEDS)]
        made = v.generate(source, specs, checker)
        errors = [error for _, _, error in made if error]
        if errors:
            v.fail(p, 9, "%s 의 stress 입력을 만들지 못했습니다: %s" % (test["id"], errors[0]))
            continue
        paths = [path for path, _, _ in made]
        for k, (_, report, _) in enumerate(made):
            invalid = (report or {}).get("invalid")
            if invalid:
                step = 4 if str(invalid.get("message", "")).startswith("타입 검사") else 5
                v.fail(p, step, "%s 의 stress 입력(seed %d)이 제한사항을 어깁니다: %s" % (test["id"], specs[k]["seed"], invalid.get("message")))
        inputs = [study.read_json(path)[0] for path in paths]
        allowed = list(range(len(inputs)))
        if brute_ok is not None:
            refused = []
            for k, args in enumerate(inputs):
                try:
                    ok = brute_ok(*copy.deepcopy(args))
                except Exception:
                    ok = False
                if not ok:
                    refused.append(k)
            if refused:
                v.fail(p, 9, "%s 의 stress 입력 %d개에서 brute_ok 가 거짓입니다. stress 의 값을 줄이세요." % (test["id"], len(refused)))
            allowed = [k for k in allowed if k not in refused]
        answers = {}
        for label, lang, path in programs:
            chosen = allowed if label == "brute.py" else list(range(len(inputs)))
            cases = [{"args_path": paths[k], "calls": 1, "limit_ms": WIDE_MS, "kill_ms": WIDE_MS} for k in chosen]
            for k, raw in zip(chosen, v.run(lang, path, cases, v.jobs)):
                if raw is not None and raw["status"] == "pass" and raw["values"]:
                    answers.setdefault(k, []).append((label, raw["values"][0], True))
                else:
                    answers.setdefault(k, []).append((label, "(%s)" % describe(raw), False))
        wrong = [k for k in range(len(inputs))
                 if not all(ok for _, _, ok in answers.get(k, [])) or len(set(a for _, a, _ in answers.get(k, []))) > 1]
        if wrong:
            k = min(wrong, key=lambda k: os.path.getsize(paths[k]))
            shown_answers = ", ".join("%s %s" % (label, shown_canonical(answer, 80) if ok else answer)
                                      for label, answer, ok in answers[k])
            v.fail(p, 9, "%s 의 stress 입력 %d개에서 답이 갈립니다. 가장 짧은 입력(seed %d): %s / 답: %s" % (
                test["id"], len(wrong), specs[k]["seed"], shown(inputs[k]), shown_answers))


def step_alt(v, p, alt_dir=None):
    for lang in v.langs:
        name = "alt" + EXT[lang]
        source = os.path.join(alt_dir, name) if alt_dir else p.source(name)
        if not source or not os.path.isfile(source):
            if alt_dir:
                v.fail(p, 10, "%s 에 %s 가 없습니다." % (alt_dir, name))
            continue
        tests = p.tests_for(lang)
        found = v.run_tests(p, lang, source, tests, WIDE_MS, WIDE_MS)
        bad = ["%s(%s)" % (t["id"], describe(found.get(t["id"]))) for t in tests
               if t["id"] in found and (found[t["id"]] is None or found[t["id"]]["status"] != "pass")]
        if bad:
            v.fail(p, 10, "%s 의 답이 기대값과 다른 테스트: %s" % (name, listing(bad, 4)))


def step_starter(v, p):
    returns = p.returns()
    examples = p.examples()
    try:
        kind = values.parse_type(returns)
    except (ValueError, AttributeError):
        return
    initial = ast.literal_eval(values.INITIAL["python"]["list" if isinstance(kind, tuple) else kind])
    if examples and all(values.canonical(ex["expected"]) == values.canonical(initial) for ex in examples):
        v.fail(p, 11, "시작 코드(answer = %r)가 입출력 예를 모두 통과합니다. 예를 하나 이상 바꾸세요." % (initial,))


def expect_matches(expect, status):
    if expect == "pass":
        return status == "pass"
    if expect == "fail":
        return status != "pass"
    if expect == "wrong":
        return status in ("wrong", "bad_return")
    return status == expect


def step_known(v, p):
    tests_by_id = p.by_id()
    for name, entry in sorted(p.wrong.items()):
        if not isinstance(entry, dict):
            v.fail(p, 12, "wrong.json 의 %s 는 객체여야 합니다." % name)
            continue
        expect = entry.get("expect")
        if expect is None and not entry.get("style"):
            v.fail(p, 12, "wrong.json 의 %s 에 expect 도 style 도 없습니다." % name)
            continue
        if expect is None:
            continue
        if expect not in EXPECTS:
            v.fail(p, 12, "wrong.json 의 %s: expect 는 %s 가운데 하나로 적습니다." % (name, " | ".join(EXPECTS)))
            continue
        on = entry.get("on") or []
        if expect == "pass" and on:
            v.fail(p, 12, "wrong.json 의 %s: pass 항목에는 on 을 적지 않습니다." % name)
        if expect != "pass" and (not isinstance(on, list) or not on):
            v.fail(p, 12, "wrong.json 의 %s: on(이 판정이 나야 할 테스트)이 없습니다." % name)
            continue
        gray = entry.get("gray") or {}
        if gray and expect != "timeout":
            v.fail(p, 12, "wrong.json 의 %s: gray 는 timeout 항목에만 둡니다." % name)
        langs = [lang for lang in (entry.get("langs") or []) if lang in LANGS]
        for lang, ids in (gray.items() if isinstance(gray, dict) else []):
            eff_ids = [t["id"] for t in p.eff_tests(lang)] if lang in LANGS else []
            for test_id in ids if isinstance(ids, list) else []:
                if test_id not in eff_ids:
                    v.fail(p, 12, "wrong.json 의 %s: gray 의 %s 는 %s 효율성 테스트가 아닙니다." % (name, test_id, lang))
                if test_id in on:
                    v.fail(p, 12, "wrong.json 의 %s: %s 가 on 과 gray 에 같이 있습니다." % (name, test_id))
        for lang in langs:
            if lang not in v.langs:
                continue
            source = p.wrong_source(name, lang)
            if source is None:
                continue
            lang_ids = {t["id"] for t in p.tests_for(lang)}
            if expect == "pass":
                tests = p.tests_for(lang)
            else:
                unknown = [test_id for test_id in on if test_id not in lang_ids]
                if unknown:
                    v.fail(p, 12, "wrong.json 의 %s: on 의 %s 는 %s 에서 도는 테스트가 아닙니다." % (name, ", ".join(unknown), lang))
                tests = [tests_by_id[test_id] for test_id in on if test_id in lang_ids]
            found = v.run_tests(p, lang, source, tests, p.limit(lang))
            bad = []
            for test in tests:
                if test["id"] not in found:
                    continue
                status = status_of(found[test["id"]])
                if not expect_matches(expect, status):
                    bad.append("%s(%s)" % (test["id"], describe(found[test["id"]])))
            if bad:
                v.fail(p, 12, "%s %s 은 %s 이어야 하는데 다른 판정이 나온 테스트: %s" % (
                    LANG_LABEL[lang], name, expect, listing(bad, 4)))


def step_styles(v, p):
    for name, entry in sorted(p.wrong.items()):
        style = entry.get("style") if isinstance(entry, dict) else None
        if not style:
            continue
        for lang in [lang for lang in (entry.get("langs") or []) if lang in LANGS]:
            if lang not in v.langs:
                continue
            if style not in STYLES[lang]:
                v.fail(p, 13, "wrong.json 의 %s: %s 의 style 은 %s 가운데 하나로 적습니다." % (name, lang, ", ".join(STYLES[lang])))
                continue
            source = p.wrong_source(name, lang)
            if source is None:
                continue
            tests = p.tests_for(lang)
            found = v.run_tests(p, lang, source, tests, p.limit(lang))
            bad = []
            for test in tests:
                if test["id"] not in found:
                    continue
                row = DEPTHS.index(test.get("depth")) if test.get("depth") in DEPTHS else 0
                want = STYLE_TABLE[style][row]
                status = status_of(found[test["id"]])
                if status != want:
                    bad.append("%s(기대 %s, 실제 %s)" % (test["id"], VERDICT_TEXT[want], describe(found[test["id"]])))
            if bad:
                v.fail(p, 13, "%s %s(style %s)의 판정이 재귀 표와 다른 테스트: %s" % (LANG_LABEL[lang], name, style, listing(bad, 4)))


def step_images(v, p):
    texts = [("problem.md", p.markdown or "")] + [(name, p.secret(name) or "") for name in ("hints.md", "explain.md")]
    for name, text in texts:
        for ref in image_refs(text):
            target = os.path.normpath(os.path.join(p.dungeon.dir, *ref.split("/")))
            if not ref.startswith("assets/") or not os.path.isfile(target):
                v.fail(p, 14, "%s 이 가리키는 그림이 없습니다: %s (던전 폴더의 assets/ 기준)" % (name, ref))


# 기대값 채우기

def fill_problem(v, p):
    path = os.path.join(p.dir, "tests.json")
    source = p.source("solution.py")
    if not os.path.isfile(path):
        v.fail(p, 16, "평문 tests.json 이 없습니다. journey_seal.py unseal 로 꺼낸 뒤 채우세요.")
        return
    if source is None:
        v.fail(p, 16, "solution.py 가 없어 기대값을 채울 수 없습니다.")
        return
    try:
        data = study.read_json(path)
    except (OSError, ValueError) as error:
        v.fail(p, 16, "tests.json 을 읽을 수 없습니다: %s" % error)
        return
    p.tests = data
    returns = p.returns()
    tests = p.accuracy() + p.efficiency()
    found = v.run_tests(p, "python", source, tests, WIDE_MS, WIDE_MS, expect=False)
    filled = []
    for test in tests:
        raw = found.get(test["id"])
        if raw is None:
            continue
        if raw["status"] != "pass" or raw["values"] is None:
            v.fail(p, 16, "solution.py 가 %s 에서 답을 내지 못했습니다: %s" % (test["id"], describe(raw)))
            continue
        answers = [json.loads(text) for text in raw["values"]]
        problem = next((values.check(answer, returns) for answer in answers if returns and values.check(answer, returns)), None)
        if problem:
            v.fail(p, 16, "solution.py 의 %s 답이 반환형과 맞지 않습니다: %s" % (test["id"], problem))
            continue
        value = answers if test.get("count") else answers[0]
        text = values.canonical(value)
        if "expected" in test:
            if values.canonical(test["expected"]) != text:
                v.fail(p, 16, "%s 의 expected %s 가 기준 풀이의 답 %s 와 다릅니다." % (test["id"], shown(test["expected"]), shown(value)))
        elif test.get("expected_sha"):
            if values.digest(text) != test["expected_sha"]:
                v.fail(p, 16, "%s 의 expected_sha 가 기준 풀이의 답과 다릅니다." % test["id"])
        elif len(text) <= LITERAL_MAX:
            test["expected"] = value
            filled.append("%s(expected)" % test["id"])
        else:
            test["expected_sha"] = values.digest(text)
            filled.append("%s(expected_sha)" % test["id"])
    if filled:
        write_tests_json(path, data)
        v.note(p, "기대값을 채웠습니다: %s" % ", ".join(filled))
    else:
        v.note(p, "채울 기대값이 없습니다.")


# 시간 재기

def version_label(lang, exe):
    try:
        done = subprocess.run([exe, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=15, text=True, encoding="utf-8", errors="replace", creationflags=study.NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    text = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    if done.returncode != 0 or not text:
        return None
    if lang == "javascript":
        return "Node.js " + text.lstrip("v")
    return text


def interpreters(v, p, lang):
    """잴 판 [(이름, 실행 파일)]. 마지막 것이 빠른 쪽 판."""
    if lang == "python":
        given = v.opts.pythons
        exes = [x for x in (given or "").split(",") if x.strip()] or [study.console_python()]
    else:
        given = v.opts.nodes
        exes = [x for x in (given or "").split(",") if x.strip()]
        if not exes and v.node_path():
            exes = [v.node_path()]
    found = []
    for exe in exes:
        exe = exe.strip()
        label = version_label(lang, exe)
        if label is None:
            v.fail(p, 15, "%s 를 실행하지 못했습니다." % exe)
        else:
            found.append((label, exe))
    return found


def measure(v, p, lang, source, test, limit_ms, exe):
    """효율성 테스트 하나를 제한의 10배에서 끊으며 돌려 (가운데 ms | None, 끊겼는지, 마지막 결과). 끊기면 다시 돌리지 않음."""
    case = v.case(p, test, limit_ms * SLOW_TIMES, limit_ms * SLOW_TIMES)
    python, node = (exe, None) if lang == "python" else (None, exe)
    times, raw = [], None
    for _ in range(TIMING_RUNS):
        raw = v.run(lang, source, [case], 1, python, node)[0]
        if raw is None:
            return None, False, None
        if raw["status"] == "timeout":
            return None, True, raw
        times.append(raw["elapsed_ms"] or 0.0)
    return statistics.median(times), False, raw


def classify(ratio, killed, gray):
    if killed:
        return "어디서나 실패"
    if ratio <= 1.0 / FAST_SHARE:
        return "어디서나 통과"
    return "회색(gray)" if gray else "회색(적지 않음)"


def time_problem(v, p):
    report = v.opts.report
    v.head(p)
    for step, message in p.errors:
        if step in (1, 2):
            v.fail(p, step, message)
    if not isinstance(p.raw, dict):
        return
    for lang in v.langs:
        tests = [t for t in p.eff_tests(lang) if t["id"] not in p.gen_failed]
        if not tests:
            continue
        versions = interpreters(v, p, lang)
        if not versions:
            continue
        limit = p.limit(lang)
        ext = EXT[lang]
        alt_entry = p.wrong.get("alt") if isinstance(p.wrong.get("alt"), dict) else None
        keep = [("기준 풀이", p.source("solution" + ext))]
        if not (alt_entry and alt_entry.get("expect") == "timeout"):
            keep.append(("alt", p.source("alt" + ext)))
        slow = []
        for name, entry in sorted(p.wrong.items()):
            if not isinstance(entry, dict) or lang not in (entry.get("langs") or []):
                continue
            if entry.get("expect") == "pass" and name != "alt":
                keep.append((name, p.wrong_source(name, lang)))
            elif entry.get("expect") == "timeout":
                slow.append((name, p.wrong_source(name, lang), entry))
        keep = [(name, path) for name, path in keep if path]
        v.say("  %s 제한 %dms. 판 %s" % (LANG_LABEL[lang], limit, ", ".join(label for label, _ in versions)))
        v.say("  %-8s %-10s %-16s %-14s %-16s %10s %6s %8s  %s" % ("문제", "언어", "판", "풀이", "테스트", "ms", "제한", "배수",
                                                                 "" if report else "판정"))
        slowest = 0.0

        def row(version, name, test, ms, killed, raw, verdict):
            shown_ms = ("> %d" % (limit * SLOW_TIMES)) if killed else ("%.2f" % ms if ms is not None else "-")
            ratio = ("> %d" % SLOW_TIMES) if killed else ("%.4f" % (ms / limit) if ms is not None else "-")
            extra = ""
            if raw is not None and raw["status"] not in ("pass", "timeout"):
                extra = " (%s)" % describe(raw)
            v.say("  %-8s %-10s %-16s %-14s %-16s %10s %6d %8s  %s%s" % (p.label, LANG_LABEL[lang], version, name, test["id"],
                                                                      shown_ms, limit, ratio, "" if report else verdict, extra))

        for version, exe in versions:
            for name, source in keep:
                for test in tests:
                    ms, killed, raw = measure(v, p, lang, source, test, limit, exe)
                    if ms is None and not killed:
                        v.fail(p, 15, "%s 를 %s 에서 돌리지 못했습니다." % (name, test["id"]))
                        continue
                    if not killed:
                        slowest = max(slowest, ms)
                    verdict = classify(ms / limit if ms is not None else 0, killed, False)
                    row(version, name, test, ms, killed, raw, verdict)
                    if report:
                        continue
                    if verdict != "어디서나 통과":
                        v.fail(p, 15, "통과시킬 풀이 %s 가 %s %s 에서 제한의 1/%d 를 넘었습니다(%s)." % (
                            name, version, test["id"], FAST_SHARE, verdict))
                    elif raw is not None and raw["status"] != "pass":
                        v.fail(p, 15, "통과시킬 풀이 %s 가 %s %s 에서 통과하지 못했습니다: %s" % (name, version, test["id"], describe(raw)))
        if not report:
            version, exe = versions[-1]
            for name, source, entry in slow:
                on = set(entry.get("on") or [])
                gray_map = entry.get("gray") if isinstance(entry.get("gray"), dict) else {}
                gray = set(gray_map.get(lang) or [])
                for test in tests:
                    ms, killed, raw = measure(v, p, lang, source, test, limit, exe)
                    if ms is None and not killed:
                        v.fail(p, 15, "%s 를 %s 에서 돌리지 못했습니다." % (name, test["id"]))
                        continue
                    ratio = ms / limit if ms is not None else 0
                    verdict = classify(ratio, killed, test["id"] in gray)
                    row(version, name, test, ms, killed, raw, verdict)
                    if test["id"] in on:
                        if not killed:
                            v.fail(p, 15, "죽일 풀이 %s 가 on 의 테스트 %s 를 %s 에서 제한의 %.2f배에 끝냈습니다(10배를 넘어야 합니다)." % (
                                name, test["id"], version, ratio))
                    elif verdict == "회색(적지 않음)":
                        v.fail(p, 15, "죽일 풀이 %s 가 %s 에서 제한의 %.2f배에 끝났습니다. 회색 지대이니 gray 에 적거나 테스트 크기·제한을 바꾸세요." % (
                            name, test["id"], ratio))
                    elif test["id"] in gray and verdict != "회색(gray)":
                        v.warn(p, 15, "%s 의 gray 에 적은 %s 가 회색 지대가 아닙니다(%s)." % (name, test["id"], verdict))
        rule = max(BASE_LIMIT[lang], int(math.ceil(LIMIT_RULE * slowest / LIMIT_STEP)) * LIMIT_STEP)
        v.say("  %s 제한: problem.json %dms, 16.5배 규칙 %dms(가장 느린 통과 풀이 %.2fms)" % (LANG_LABEL[lang], limit, rule, slowest))
        if limit < rule and not report:
            v.warn(p, 15, "%s 제한 %dms 가 16.5배 규칙의 값 %dms 보다 작습니다. 다시 잴 때의 흔들림(10%% 안팎)을 받을 여유가 없습니다." % (
                LANG_LABEL[lang], limit, rule))


# 검토 서명

def problem_files(p):
    """review.json 이 덮는 문제 파일의 sha256. 공개 파일과 비밀 파일 전부(review.json 제외)."""
    files = {}
    for name in ("problem.json", "problem.md"):
        path = os.path.join(p.dir, name)
        if os.path.isfile(path):
            files[name] = text_sha(study.read_text(path))
    for name in p.secret_names():
        if name != "review.json":
            files[name] = text_sha(p.secret(name))
    return files


def dungeon_files(d):
    """던전 폴더의 review.json 이 덮는 intro.md, meta.json, assets/ 그림의 sha256."""
    files = {}
    for name in ("intro.md", "meta.json"):
        path = os.path.join(d.dir, name)
        if os.path.isfile(path):
            files[name] = text_sha(study.read_text(path))
    folder = os.path.join(d.dir, "assets")
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if os.path.isfile(os.path.join(folder, name)):
                files["assets/" + name] = file_sha(os.path.join(folder, name))
    return files


def review_text(where):
    if isinstance(where, Problem):
        return where.secret("review.json")
    return where.secrets.get("review.json")


def sign(v, where, files):
    o = v.opts
    names = {"writer": o.writer, "resolver": o.resolver, "reviewer": o.reviewer}
    missing = [key for key, value in names.items() if not (value or "").strip()]
    if missing:
        v.fail(where, 18, "--%s 가 필요합니다." % ", --".join(missing))
        return
    if o.writer.strip() in (o.resolver.strip(), o.reviewer.strip()):
        v.fail(where, 18, "출제자는 재풀이자나 검토자를 겸하지 않습니다(%s)." % o.writer)
        return
    findings = []
    old = review_text(where)
    if old:
        try:
            findings = list(json.loads(old).get("findings") or [])
        except (ValueError, AttributeError):
            findings = []
    findings += [text for text in (o.finding or []) if text.strip()]
    data = {"format": 1, "writer": o.writer.strip(), "resolver": o.resolver.strip(), "reviewer": o.reviewer.strip(),
            "files": dict(sorted(files.items())), "findings": findings}
    folder = where.dir
    study.write_text(os.path.join(folder, "review.json"), json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    v.note(where, "서명했습니다: %s/review.json (파일 %d개)" % (where.label, len(files)))


def check_review(v, where, text, files, prefix):
    if text is None:
        v.fail(where, 18, "review.json 이 없습니다. 검토를 받고 --sign 으로 서명하세요.")
        return
    try:
        data = json.loads(text)
    except ValueError as error:
        v.fail(where, 18, "review.json 을 읽을 수 없습니다: %s" % error)
        return
    names = [data.get(key) for key in ("writer", "resolver", "reviewer")] if isinstance(data, dict) else []
    if len(names) != 3 or not all(isinstance(x, str) and x.strip() for x in names):
        v.fail(where, 18, "review.json 에 writer, resolver, reviewer 가 모두 있어야 합니다.")
        return
    if names[0] in names[1:]:
        v.fail(where, 18, "출제자(%s)가 재풀이자나 검토자와 같습니다." % names[0])
    signed = data.get("files") if isinstance(data.get("files"), dict) else {}
    changed = sorted(name for name in set(signed) | set(files) if signed.get(name) != files.get(name))
    if changed:
        v.fail(where, 18, "검토 뒤에 바뀐 파일: %s" % ", ".join(prefix + name for name in changed))


def check_problem_review(v, p):
    check_review(v, p, p.secret("review.json"), problem_files(p), p.pid + "/")


def check_dungeon_review(v, d):
    check_review(v, d, d.secrets.get("review.json"), dungeon_files(d), "")


# 명령줄

def parse_args(argv):
    parser = argparse.ArgumentParser(prog="verify_journey.py", description="알고리즘 여행 문제 은행을 검증합니다.")
    parser.add_argument("targets", nargs="*", help="d01 이나 d01/p3. 없으면 출제된 던전 전부")
    parser.add_argument("--bank", default=bank.BANK_DIR, help="은행 폴더(기본 dungeons/)")
    parser.add_argument("--changed", metavar="REF", help="REF 와 갈라진 뒤 바뀐 던전만")
    parser.add_argument("--lang", choices=LANGS, help="그 언어의 단계만")
    parser.add_argument("--fill", action="store_true", help="비어 있는 기대값을 solution.py 로 채움")
    parser.add_argument("--timing", action="store_true", help="기준 컴퓨터에서 시간 여유와 회색 지대를 잼")
    parser.add_argument("--report", action="store_true", help="--timing 에서 판정하지 않고 표만 찍음")
    parser.add_argument("--pythons", help="--timing 이 잴 Python 실행 파일들(쉼표로 구분, 빠른 판을 마지막에)")
    parser.add_argument("--nodes", help="--timing 이 잴 node 실행 파일들(쉼표로 구분, 빠른 판을 마지막에)")
    parser.add_argument("--styles", action="store_true", help="wrong.json 의 재귀 방식 항목만 봄")
    parser.add_argument("--plan", metavar="REF", help="journey.yml 의 engine, styles 두 줄만 찍음")
    parser.add_argument("--alt", metavar="DIR", help="DIR 의 alt.py, alt.js 로 스트레스와 전체 테스트를 대조함")
    parser.add_argument("--sign", action="store_true", help="검증을 통과하면 review.json 을 씀")
    parser.add_argument("--writer", help="출제자 이름표")
    parser.add_argument("--resolver", help="재풀이자 이름표")
    parser.add_argument("--reviewer", help="검토자 이름표")
    parser.add_argument("--finding", action="append", help="review.json 의 findings 에 남길 한 줄(여러 번 줄 수 있음)")
    parser.add_argument("--require-review", action="store_true", help="검토 서명이 없거나 서명 뒤에 바뀐 파일이 있으면 실패")
    parser.add_argument("--jobs", type=int, help="동시에 돌릴 자식 프로세스 수")
    return parser.parse_args(argv)


def main(argv=None, steps=None, out=None):
    """명령을 실행하고 종료 코드를 돌려줌. steps 는 테스트가 단계 번호 집합으로 일부만 돌릴 때 씀."""
    opts = parse_args(sys.argv[1:] if argv is None else argv)
    if opts.plan is not None:
        result = plan(os.path.abspath(opts.bank), opts.plan)
        print("engine=%s\nstyles=%s" % (str(result["engine"]).lower(), str(result["styles"]).lower()), file=out or sys.stdout)
        return 0
    v = Verifier(opts, steps, out)
    try:
        return v.main(opts.targets)
    finally:
        v.close()


if __name__ == "__main__":
    sys.exit(main())
