# -*- coding: utf-8 -*-
"""단계 검사 준비·실행·결과 해석.

봉인을 풀어 <ROOT>/.web-check/<미션>-<8자리 16진수>/ 에 checks/step<k>.test.tsx, kit/, setup.ts, vitest.config.mts 를 쓰고
`node <ROOT>/node_modules/vitest/vitest.mjs run --config … --reporter=json --outputFile=…` 을 돌림. cwd 는 저장소 맨 위,
CI=1, FORCE_COLOR=0, NODE_OPTIONS 는 비움. 60초를 넘기거나 Ctrl+C 로 멈추면 프로세스 트리를 끊음. 끝나면 성공·실패와 상관없이 폴더를 지움.
폴더 이름에 실행마다 다른 꼬리를 붙여, 화면과 터미널이 같은 미션을 동시에 검사해도 서로의 폴더를 지우거나 덮어쓰지 않음.
JSON 의 testResults[].assertionResults[] 에서 title, status, duration, failureMessages 를 읽고, 검사 이름의 첫 낱말이
검사 id("1a") 임. 파일이 아예 돌지 못한 경우(문법 오류 등)는 그 파일의 검사 id 를 모두 실패로 적되, 제목은 검사 파일에서 읽고
문구 첫 줄은 한국어 안내로 둠. 화면은 실패 문구의 첫 줄만 보이고 나머지는 [원문 보기]에 두므로 첫 줄을 읽을 수 있는 한국어로 만듦.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import study
from webprep import bank

CHECK_DIR = ".web-check"
CONFIG_NAME = "vitest.config.mts"
SETUP_NAME = "setup.ts"
LIMIT_S = 60
TEST_TIMEOUT_MS = 5000
MESSAGE_LINES = 12
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
DUMP_HEAD = re.compile(r"^\s*(Ignored nodes:|<body|<div|Here are the accessible roles|Unable to find)")
STACK_LINE = re.compile(r"^\s+at ")
FOREIGN_FRAME = re.compile(r"node_modules[/\\]|\(node:|\(<anonymous>\)|" + re.escape(CHECK_DIR) + r"[/\\]")
SLOT_NAME = re.compile(r"\b([\w.]+)-[0-9a-f]{8}(?=[/\\]checks[/\\])")
ASSERT_HEAD = re.compile(r"^(?:AssertionError|Error): (.+)$")
HANGUL = re.compile("[가-힣]")
FILE_FAILED = ("검사 파일을 불러오다 멈춰서 이 검사를 돌리지 못했습니다. 원문에 나온 파일과 줄에서 문법 오류나 "
               "없는 파일을 가져오는 import가 있는지 확인해 주세요.")
# Testing Library 가 요소를 못 찾았을 때의 영어 첫 줄 → 화면에 보일 한국어 한 줄. 원래 줄은 접은 원문 맨 앞에 남김
LIBRARY_LINES = (
    (r'Unable to find an accessible element with the role "([^"]+)" and name "([^"]*)"', '이름이 "{1}"이고 역할(role)이 {0}인 요소를 화면에서 찾지 못했습니다.'),
    (r'Unable to find role="([^"]+)" and name "([^"]*)"', '이름이 "{1}"이고 역할(role)이 {0}인 요소를 화면에서 찾지 못했습니다.'),
    (r'Unable to find an accessible element with the role "([^"]+)"', '역할(role)이 {0}인 요소를 화면에서 찾지 못했습니다.'),
    (r'Unable to find role="([^"]+)"', '역할(role)이 {0}인 요소를 화면에서 찾지 못했습니다.'),
    (r'Unable to find an element with the text: (.+?)(?:\. This could be because.*)?', '"{0}" 글자를 화면에서 찾지 못했습니다.'),
    (r'Unable to find a label with the text of: (.+)', '"{0}" label이 붙은 요소를 화면에서 찾지 못했습니다.'),
    (r'Found a label with the text of: (.+?), however no form control was found.*', '"{0}" label은 있지만 그 label에 이어진 입력칸이 없습니다.'),
    (r'Unable to find an element with the placeholder text of: (.+)', '안내 글자(placeholder)가 "{0}"인 요소를 화면에서 찾지 못했습니다.'),
    (r'Found multiple elements with the role "([^"]+)" and name "([^"]*)"', '이름이 "{1}"이고 역할(role)이 {0}인 요소가 화면에 둘 이상 있습니다.'),
    (r'Found multiple elements with the role "([^"]+)"', '역할(role)이 {0}인 요소가 화면에 둘 이상 있습니다.'),
    (r'Found multiple elements with the text(?: of)?: (.+)', '"{0}" 글자가 화면에 둘 이상 있습니다.'),
)
LIBRARY_HEAD = re.compile(r"^(?:TestingLibraryElementError|Error): (.+)$")
STALE_S = 600  # 이보다 오래된 검사 폴더는 끊긴 실행이 남긴 것으로 보고 지움. 한 번 검사는 LIMIT_S 를 넘지 않음
_popen = subprocess.Popen  # 테스트가 가짜로 바꿔 끼움


class CheckError(Exception):
    """검사를 준비하거나 돌리지 못함. 문구는 사용자에게 그대로 보여 줌."""


def _js_string(path):
    return json.dumps(path.replace("\\", "/"))


def config_text(root, includes, app_src, kit_dir, setup_path):
    """vitest.config.mts 의 글. root 는 저장소 맨 위, include 는 열린 단계 파일만, 별칭 @app 과 @kit.
    dedupe 로 react 를 저장소 맨 위 node_modules 에서만 읽어, 학습자 폴더가 다른 곳에 있거나 그 안에 node_modules 가 있어도
    React 가 한 벌만 로드됨."""
    lines = ["import { defineConfig } from 'vitest/config';", "", "export default defineConfig({",
             "  root: %s," % _js_string(root),
             "  esbuild: { jsx: 'automatic', jsxImportSource: 'react' },",
             "  resolve: { alias: { '@app': %s, '@kit': %s }, dedupe: ['react', 'react-dom'] }," % (_js_string(app_src), _js_string(kit_dir)),
             "  test: {",
             "    include: [%s]," % ", ".join(_js_string(os.path.relpath(p, root)) for p in includes),
             "    environment: 'jsdom',",
             "    setupFiles: [%s]," % _js_string(setup_path),
             "    testTimeout: %d," % TEST_TIMEOUT_MS,
             "    css: false,",
             "    watch: false,",
             "  },", "});", ""]
    return "\n".join(lines)


def prepare(root, mid, secrets, kit, steps, app_src, hidden=False):
    """.web-check/<mid>/ 를 만들고 {"dir", "config", "expected": {검사 id: 단계}, "titles": {검사 id: 이름}} 를 돌려줌.
    steps 는 돌릴 단계 번호 목록. mid 자리에 run_steps 는 실행마다 다른 폴더 이름을 넘김."""
    folder = os.path.join(root, CHECK_DIR, mid)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
    files = bank.check_files(secrets)
    includes, expected, titles = [], {}, {}
    wanted = [(step, files.get(step)) for step in steps]
    if hidden and "hidden" in files:
        wanted.append(("hidden", files["hidden"]))
    for step, text in wanted:
        if text is None:
            raise CheckError("%d단계 검사 파일(checks/step%d.test.tsx)이 봉인 안에 없습니다." % (step, step))
        name = "hidden.test.tsx" if step == "hidden" else "step%d.test.tsx" % step
        path = os.path.join(folder, "checks", name)
        study.write_text(path, text)
        includes.append(path)
        for cid in bank.check_ids(text):
            expected[cid] = step
        for _, name in bank.TEST_NAME.findall(text):
            cid, _, rest = name.partition(" ")
            titles.setdefault(cid, rest)
    kit_dir = os.path.join(folder, "kit")
    setup_path = os.path.join(folder, SETUP_NAME)
    setup_written = False
    for rel, text in kit.items():
        if rel == SETUP_NAME:
            study.write_text(setup_path, text)
            setup_written = True
        else:
            study.write_text(os.path.join(kit_dir, *rel.split("/")), text)
    if not setup_written:
        study.write_text(setup_path, "import '@testing-library/jest-dom/vitest';\n")
    os.makedirs(kit_dir, exist_ok=True)
    config = os.path.join(folder, CONFIG_NAME)
    study.write_text(config, config_text(root, includes, app_src, kit_dir, setup_path))
    return {"dir": folder, "config": config, "expected": expected, "titles": titles}


def new_slot(mid):
    """이번 검사 실행의 폴더 이름. 같은 미션을 두 곳에서 동시에 검사해도 겹치지 않음."""
    return "%s-%s" % (mid, uuid.uuid4().hex[:8])


def sweep(root, mid, now=None):
    """끊긴 실행(전원 꺼짐, 강제 종료)이 남긴 이 미션의 검사 폴더 가운데 STALE_S 보다 오래된 것을 지움. 도는 중인 폴더는 건드리지 않음."""
    parent = os.path.join(root, CHECK_DIR)
    now = time.time() if now is None else now
    try:
        names = os.listdir(parent)
    except OSError:
        return
    for name in names:
        if not re.match(r"%s-[0-9a-f]{8}\Z" % re.escape(mid), name):
            continue
        path = os.path.join(parent, name)
        try:
            old = now - os.path.getmtime(path) > STALE_S
        except OSError:
            continue
        if old:
            shutil.rmtree(path, ignore_errors=True)


def cleanup(root, mid):
    shutil.rmtree(os.path.join(root, CHECK_DIR, mid), ignore_errors=True)
    parent = os.path.join(root, CHECK_DIR)
    try:
        if os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
    except OSError:
        pass


def _env():
    env = dict(os.environ)
    env.pop("NODE_OPTIONS", None)
    env["CI"] = "1"
    env["FORCE_COLOR"] = "0"
    return env


def _kill_tree(proc):
    """자식과 그 아래 프로세스를 끊음. POSIX 는 새 세션의 프로세스 그룹, Windows 는 taskkill /T."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=study.NO_WINDOW)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ValueError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def run(node_path, root, config, out_path, limit=LIMIT_S):
    """vitest 를 돌림. {"returncode", "timeout", "output", "ms"}. 결과 JSON 은 out_path 에 쓰임."""
    vitest = os.path.join(root, "node_modules", "vitest", "vitest.mjs")
    if not os.path.isfile(vitest):
        raise CheckError("검사 도구가 설치되어 있지 않습니다. `python study.py web install` 로 설치해 주세요.")
    cmd = [node_path, vitest, "run", "--config", config, "--reporter=json", "--outputFile=%s" % out_path]
    options = {"cwd": root, "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
               "env": _env(), "creationflags": study.NO_WINDOW}
    if sys.platform != "win32":
        options["start_new_session"] = True
    started = time.monotonic()
    try:
        proc = _popen(cmd, **options)
    except OSError as error:
        raise CheckError("검사 명령을 실행하지 못했습니다: %s" % error)
    try:
        output = proc.communicate(timeout=limit)[0]
        timeout = False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            output = proc.communicate(timeout=5)[0]
        except (subprocess.TimeoutExpired, OSError, ValueError):
            output = b""
        timeout = True
    except BaseException:  # Ctrl+C. vitest 는 새 세션(Windows 는 콘솔 없음)이라 신호를 받지 못하므로 끊음
        _kill_tree(proc)
        raise
    text = output.decode("utf-8", "replace") if isinstance(output, bytes) else (output or "")
    return {"returncode": proc.returncode, "timeout": timeout, "output": ANSI.sub("", text),
            "ms": int((time.monotonic() - started) * 1000)}


def _prefixes(folder):
    """경로를 줄일 때 찾을 폴더 앞부분. 운영체제 구분자와 / 둘 다, 실제 경로가 다르면(심볼릭 링크) 그것도."""
    found = []
    for path in (folder, os.path.realpath(folder)):
        for text in (os.path.join(path, ""), os.path.join(path, "").replace("\\", "/")):
            if text not in found:
                found.append(text)
    return found


def _relative(folder, root):
    """vite 가 오류에 저장소 기준 상대 경로로 적는 미션 폴더(submissions/<ID>/web/missions/<미션>/)."""
    try:
        rel = os.path.relpath(folder, root)
    except ValueError:  # Windows 에서 드라이브가 다른 경우
        return []
    return [os.path.join(rel, "").replace("\\", "/")]


def _shorten(line, root, app):
    """줄 안의 긴 경로를 줄임. 검사 폴더는 `<미션>/checks/…`, 미션 폴더는 `src/…`, 저장소의 나머지는 `node_modules/…` 처럼
    저장소 기준으로 보이고 file:// 앞머리도 뗌. 미션 폴더도 저장소 안에 있으므로 저장소보다 먼저 줄임."""
    for prefix in _prefixes(os.path.join(root, CHECK_DIR)) + (_prefixes(app) + _relative(app, root) if app else []) + _prefixes(root):
        line = line.replace("file:///" + prefix, "").replace("file://" + prefix, "").replace(prefix, "")
    return SLOT_NAME.sub(r"\1", line.replace(CHECK_DIR + "/", ""))


def _foreign(line, app):
    """호출 줄이 학습자 코드 밖(검사 도구, Node 안쪽, 봉인한 검사 파일)을 가리키는지. app 을 주면 그 폴더 밖이면 모두 밖으로 봄."""
    if FOREIGN_FRAME.search(line):
        return True
    if app:
        flat = line.replace("\\", "/")
        return not any(prefix.replace("\\", "/") in flat for prefix in _prefixes(app))
    return False


def clean_message(messages, root, app=None):
    """실패 문구를 (보이는 글, 접은 원문)으로. ANSI 를 지우고 긴 경로를 줄이며 보이는 글은 앞 12줄만 둠.
    DOM 덤프와, 검사 도구·Node 안쪽·봉인한 검사 파일을 가리키는 호출 줄은 접은 원문으로 보냄. 학습자 코드를 가리키는 호출 줄은
    보이는 글에 남김. app 은 미션 폴더이고, 주면 그 폴더 밖을 가리키는 호출 줄도 접은 원문으로 보냄."""
    text = ANSI.sub("", "\n".join(m for m in messages if m))
    shown, detail, frames = [], [], []
    for line in text.splitlines():
        if detail or DUMP_HEAD.match(line):
            detail.append(_shorten(line, root, app))
        elif STACK_LINE.match(line) and _foreign(line, app):
            frames.append(_shorten(line, root, app))
        else:
            shown.append(_shorten(line, root, app))
    while shown and not shown[-1].strip():
        shown.pop()
    clipped = shown[:MESSAGE_LINES]
    if len(shown) > MESSAGE_LINES:
        clipped.append("… (이하 생략)")
    return "\n".join(clipped).strip(), "\n".join(detail + frames).strip()


def korean_first(message, detail):
    """보이는 글의 첫 줄을 한국어로 만듦. 화면은 이 첫 줄만 보이고 나머지는 [원문 보기]에 둠.
    검사가 expect(값, '한국어 문구')로 남긴 문구는 vitest 가 "AssertionError: <문구>: expected …" 한 줄로 내므로 <문구>만 보임.
    jest-dom 처럼 "Error: <문구>" 만 내는 경우는 문구가 한국어로 시작할 때만 올림. Testing Library 가 요소를 못 찾은 줄은
    LIBRARY_LINES 로 옮김. 어느 경우든 원래 첫 줄(기대값과 실제값, 영어 원문)은 접은 원문 맨 앞에 둠. 그 밖은 그대로 둠."""
    lines = message.splitlines()
    head = _korean_head(lines[0]) if lines else None
    if head is None:
        return message, detail
    return "\n".join([head] + lines[1:]), "\n".join(part for part in (lines[0], detail) if part)


def _korean_head(line):
    found = ASSERT_HEAD.match(line)
    if found:
        said = found.group(1)
        cut = said.find(": expected ")
        head = (said[:cut] if cut > 0 else said).strip()
        if HANGUL.search(head) if cut > 0 else HANGUL.match(head.lstrip("\"'“‘「[(").strip()):
            return head
    found = LIBRARY_HEAD.match(line)
    if found:
        for pattern, korean in LIBRARY_LINES:
            matched = re.fullmatch(pattern, found.group(1).strip())
            if matched:
                return korean.format(*matched.groups())
    return None


def _step_of(cid, expected):
    if cid in expected:
        return expected[cid]
    found = re.match(r"(\d+)[a-z]*\Z", cid)
    return int(found.group(1)) if found else "hidden"


def parse(text, expected, root, titles=None, app=None):
    """vitest JSON 보고서를 {"tests": [{"id", "step", "title", "status", "ms", "message", "detail"}], "files": [...]} 로.
    expected 에 있는데 결과에 없는 검사 id 는 파일 수준 실패로 넣음. 제목은 titles(검사 파일에서 읽은 이름)에서 가져오고 문구 첫 줄은
    FILE_FAILED, 그 아래에 그 파일의 오류 원문을 둠. app 은 미션 폴더(clean_message)."""
    try:
        data = json.loads(text)
        results = data["testResults"]
    except (ValueError, KeyError, TypeError) as error:
        raise CheckError("검사 결과를 읽을 수 없습니다: %s" % (str(error) or type(error).__name__))
    tests, seen, file_errors = [], set(), []
    for file_result in results:
        for item in file_result.get("assertionResults") or []:
            title = str(item.get("title") or item.get("fullName") or "")
            cid, _, rest = title.partition(" ")
            status = str(item.get("status") or "")
            passed = status == "passed"
            message, detail = ("", "")
            if not passed:
                message, detail = korean_first(*clean_message(item.get("failureMessages") or [], root, app))
            if not message and not passed:
                message = "검사가 %s 상태로 끝났습니다." % (status or "알 수 없는")
            tests.append({"id": cid, "step": _step_of(cid, expected), "title": rest or title, "status": "pass" if passed else "fail",
                          "ms": int(item.get("duration") or 0), "message": message, "detail": detail})
            seen.add(cid)
        if not file_result.get("assertionResults") and str(file_result.get("status")) != "passed":
            name = os.path.basename(str(file_result.get("name") or ""))
            file_errors.append((name, clean_message([str(file_result.get("message") or "")], root, app)))
    for cid, step in expected.items():
        if cid in seen:
            continue
        name = "hidden.test.tsx" if step == "hidden" else "step%s.test.tsx" % step
        message, detail = next(((m, d) for n, (m, d) in file_errors if n == name), ("", ""))
        tests.append({"id": cid, "step": step, "title": (titles or {}).get(cid, ""), "status": "fail", "ms": 0,
                      "message": "\n".join(part for part in (FILE_FAILED, message) if part), "detail": detail})
    order = {cid: n for n, cid in enumerate(expected)}
    tests.sort(key=lambda t: (order.get(t["id"], len(order)), t["id"]))
    return {"tests": tests, "file_errors": [n for n, _ in file_errors]}


def has_packages(node_modules):
    """node_modules 폴더에 실제 패키지가 있는지. vite 가 `npm test` 때 만드는 .vite 같은 점 항목만 있으면 False."""
    try:
        return any(not name.startswith(".") for name in os.listdir(node_modules))
    except OSError:
        return False


def run_steps(node_path, root, mid, secrets, kit, steps, app_src, hidden=False, limit=LIMIT_S):
    """단계 검사를 준비하고 돌리고 폴더를 지움. {"tests", "pass", "fail", "ms", "timeout", "warnings", "by_step"}.
    by_step 은 {단계: {"pass": [...], "fail": [...], "ok": bool}} 이고 검사가 하나도 없는 단계는 ok 가 False."""
    warnings = []
    if has_packages(os.path.join(os.path.dirname(app_src), "node_modules")):
        warnings.append("미션 폴더 안에 node_modules 가 있습니다. React 가 두 벌 읽혀 훅 에러가 날 수 있으니 지워 주세요.")
    sweep(root, mid)
    slot = new_slot(mid)
    prepared = prepare(root, slot, secrets, kit, steps, app_src, hidden)
    try:
        with tempfile.TemporaryDirectory(prefix="web_check_", **study.TMP_OPTIONS) as tmp:
            out_path = os.path.join(tmp, "result.json")
            ran = run(node_path, root, prepared["config"], out_path, limit)
            if ran["timeout"]:
                raise CheckError("검사가 %d초 안에 끝나지 않았습니다. 무한 반복이나 끝나지 않는 await 가 있는지 확인해 주세요." % limit)
            try:
                text = study.read_text(out_path)
            except OSError:
                tail = "\n".join(ran["output"].strip().splitlines()[-MESSAGE_LINES:])
                raise CheckError("검사 결과 파일이 만들어지지 않았습니다(종료 코드 %s).\n%s" % (ran["returncode"], tail))
            parsed = parse(text, prepared["expected"], root, prepared["titles"], os.path.dirname(app_src))
    finally:
        cleanup(root, slot)
    by_step = {}
    for step in list(steps) + (["hidden"] if hidden and "hidden" in bank.check_files(secrets) else []):
        mine = [t for t in parsed["tests"] if t["step"] == step]
        by_step[step] = {"pass": [t["id"] for t in mine if t["status"] == "pass"],
                         "fail": [t["id"] for t in mine if t["status"] == "fail"],
                         "ok": bool(mine) and all(t["status"] == "pass" for t in mine)}
    return {"tests": parsed["tests"], "pass": [t["id"] for t in parsed["tests"] if t["status"] == "pass"],
            "fail": [t["id"] for t in parsed["tests"] if t["status"] == "fail"], "ms": ran["ms"], "timeout": False,
            "warnings": warnings, "by_step": by_step, "file_errors": parsed["file_errors"]}
