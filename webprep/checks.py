# -*- coding: utf-8 -*-
"""단계 검사 준비·실행·결과 해석.

봉인을 풀어 <ROOT>/.web-check/<미션>/ 에 checks/step<k>.test.tsx, kit/, setup.ts, vitest.config.mts 를 쓰고
`node <ROOT>/node_modules/vitest/vitest.mjs run --config … --reporter=json --outputFile=…` 을 돌림. cwd 는 저장소 맨 위,
CI=1, FORCE_COLOR=0, NODE_OPTIONS 는 비움. 60초를 넘기면 프로세스 트리를 끊음. 끝나면 성공·실패와 상관없이 폴더를 지움.
JSON 의 testResults[].assertionResults[] 에서 title, status, duration, failureMessages 를 읽고, 검사 이름의 첫 낱말이
검사 id("1a") 임. 파일이 아예 돌지 못한 경우(문법 오류 등)는 그 파일의 검사 id 를 모두 실패로 적음.
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
    """.web-check/<mid>/ 를 만들고 {"dir", "config", "expected": {검사 id: 단계}} 를 돌려줌. steps 는 돌릴 단계 번호 목록."""
    folder = os.path.join(root, CHECK_DIR, mid)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
    files = bank.check_files(secrets)
    includes, expected = [], {}
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
    return {"dir": folder, "config": config, "expected": expected}


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
    text = output.decode("utf-8", "replace") if isinstance(output, bytes) else (output or "")
    return {"returncode": proc.returncode, "timeout": timeout, "output": ANSI.sub("", text),
            "ms": int((time.monotonic() - started) * 1000)}


def clean_message(messages, root):
    """실패 문구를 (보이는 글, 접은 DOM 덤프)로. ANSI 와 .web-check 경로를 지우고 앞 12줄만 보임."""
    text = ANSI.sub("", "\n".join(m for m in messages if m))
    text = text.replace(os.path.join(root, CHECK_DIR) + os.sep, "").replace(CHECK_DIR + "/", "")
    shown, detail = [], []
    for line in text.splitlines():
        if detail or DUMP_HEAD.match(line):
            detail.append(line)
        else:
            shown.append(line)
    while shown and not shown[-1].strip():
        shown.pop()
    clipped = shown[:MESSAGE_LINES]
    if len(shown) > MESSAGE_LINES:
        clipped.append("… (이하 생략)")
    return "\n".join(clipped).strip(), "\n".join(detail).strip()


def _step_of(cid, expected):
    if cid in expected:
        return expected[cid]
    found = re.match(r"(\d+)[a-z]*\Z", cid)
    return int(found.group(1)) if found else "hidden"


def parse(text, expected, root):
    """vitest JSON 보고서를 {"tests": [{"id", "step", "title", "status", "ms", "message", "detail"}], "files": [...]} 로.
    expected 에 있는데 결과에 없는 검사 id 는 파일 수준 실패 문구와 함께 실패로 넣음."""
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
            message, detail = clean_message(item.get("failureMessages") or [], root) if not passed else ("", "")
            if not message and not passed:
                message = "검사가 %s 상태로 끝났습니다." % (status or "알 수 없는")
            tests.append({"id": cid, "step": _step_of(cid, expected), "title": rest or title, "status": "pass" if passed else "fail",
                          "ms": int(item.get("duration") or 0), "message": message, "detail": detail})
            seen.add(cid)
        if not file_result.get("assertionResults") and str(file_result.get("status")) != "passed":
            name = os.path.basename(str(file_result.get("name") or ""))
            file_errors.append((name, clean_message([str(file_result.get("message") or "")], root)))
    for cid, step in expected.items():
        if cid in seen:
            continue
        name = "hidden.test.tsx" if step == "hidden" else "step%s.test.tsx" % step
        message, detail = next(((m, d) for n, (m, d) in file_errors if n == name), ("", ""))
        tests.append({"id": cid, "step": step, "title": "", "status": "fail", "ms": 0,
                      "message": message or "검사 파일이 끝까지 돌지 못했습니다.", "detail": detail})
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
    prepared = prepare(root, mid, secrets, kit, steps, app_src, hidden)
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
            parsed = parse(text, prepared["expected"], root)
    finally:
        cleanup(root, mid)
    by_step = {}
    for step in list(steps) + (["hidden"] if hidden and "hidden" in bank.check_files(secrets) else []):
        mine = [t for t in parsed["tests"] if t["step"] == step]
        by_step[step] = {"pass": [t["id"] for t in mine if t["status"] == "pass"],
                         "fail": [t["id"] for t in mine if t["status"] == "fail"],
                         "ok": bool(mine) and all(t["status"] == "pass" for t in mine)}
    return {"tests": parsed["tests"], "pass": [t["id"] for t in parsed["tests"] if t["status"] == "pass"],
            "fail": [t["id"] for t in parsed["tests"] if t["status"] == "fail"], "ms": ran["ms"], "timeout": False,
            "warnings": warnings, "by_step": by_step, "file_errors": parsed["file_errors"]}
