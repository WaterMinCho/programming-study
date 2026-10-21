# -*- coding: utf-8 -*-
"""검사 도구(저장소 맨 위 node_modules) 설치 확인·설치·지우기와 Node 찾기.

설치는 셸과 npx 를 거치지 않고 `node <npm-cli.js> ci --no-audit --no-fund --prefer-offline --ignore-scripts` 로 돌림.
npm-cli.js 는 macOS·Linux 에서 <node 폴더>/../lib/node_modules/npm/bin/npm-cli.js, Windows 에서
<node 폴더>\\node_modules\\npm\\bin\\npm-cli.js 임. 출력은 ~/.rokey-study/web/install.log 에 쓰고 10분 안에 끝나야 함.
끝나면 node_modules/.web-stack 에 package-lock.json 의 sha256 을 적어 두고, 켤 때 값이 다르면 다시 설치하라고 안내함.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time

import study
from journey import node as node_finder

MIN_NODE = (22, 12)
INSTALL_LIMIT_S = 600
MARKER = ".web-stack"
LOCK_NAME = "package-lock.json"
VITEST_MJS = os.path.join("node_modules", "vitest", "vitest.mjs")
SIZE_MB = 80
LOG_NAME = "install.log"
NPM_ARGS = ("ci", "--no-audit", "--no-fund", "--prefer-offline", "--ignore-scripts")
_run = subprocess.run  # 테스트가 가짜로 바꿔 끼움


def home_dir():
    """저장소에 올리지 않는 로컬 값(설치 로그, 하루 새 사슬 수, 경력 사슬)을 두는 폴더. STUDY_WEB_HOME 으로 바꿀 수 있음."""
    return os.environ.get("STUDY_WEB_HOME") or os.path.join(os.path.expanduser("~"), ".rokey-study", "web")


def log_path():
    return os.path.join(home_dir(), LOG_NAME)


def node_label():
    return node_finder.minimum_label(MIN_NODE)


def find_node(saved=None, probe=False):
    """MIN_NODE 이상의 Node 를 찾음. 없으면 None. 결과는 journey.node 가 minimum 별로 기억함."""
    return node_finder.find(probe=probe, saved=saved, minimum=MIN_NODE)


def npm_cli(node_path):
    """node 실행 파일 옆의 npm-cli.js. 없으면 None."""
    folder = os.path.dirname(os.path.abspath(node_path))
    beside = os.path.join(folder, "node_modules", "npm", "bin", "npm-cli.js")  # Windows 설치본과 nvm-windows 의 자리
    under_lib = os.path.join(folder, "..", "lib", "node_modules", "npm", "bin", "npm-cli.js")  # macOS·Linux 설치본과 nvm 의 자리
    candidates = [beside, under_lib] if sys.platform == "win32" else [under_lib, beside]  # 어느 OS 에서든 두 자리를 다 봄
    for path in candidates:
        if os.path.isfile(path):
            return os.path.normpath(path)
    return None


def lock_hash(root):
    """package-lock.json 의 sha256. 파일이 없으면 None."""
    path = os.path.join(root, LOCK_NAME)
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def marker_path(root):
    return os.path.join(root, "node_modules", MARKER)


def read_marker(root):
    try:
        return study.read_text(marker_path(root)).strip()
    except OSError:
        return None


def installed(root):
    return os.path.isfile(os.path.join(root, VITEST_MJS))


def state(root, node=None):
    """{"installed", "stale", "no_marker", "node", "problem", "lock"}. stale 은 설치 때 적어 둔 lockfile 해시와 지금 해시가
    다르거나 표시 파일이 없음(손으로 npm install 한 경우). no_marker 는 그 가운데 표시 파일이 없는 경우.
    problem 은 미션 쪽에 보여 줄 안내 한 줄(없으면 빈 글)."""
    has = installed(root)
    current = lock_hash(root)
    marker = read_marker(root) if has else None
    no_marker = bool(has and marker is None)
    stale = no_marker or bool(has and current and marker != current)
    problem = ""
    if node is None:
        problem = ("Node.js 를 찾지 못했습니다. Node.js %s 이상을 설치하고 다시 시도해 주세요. nvm 이나 nvm-windows 를 쓰면 "
                   "기본 판을 %s 이상으로 두거나 STUDY_NODE 에 node 경로를 적어 주세요." % (node_label(), node_label()))
    elif not current:
        problem = "저장소 맨 위에서 %s 을 찾지 못했습니다. 저장소를 최신으로 받아 주세요." % LOCK_NAME
    elif not has:
        problem = "검사 도구가 아직 설치되지 않았습니다. `python study.py web install` 로 설치해 주세요."
    elif no_marker:
        problem = "설치 표시가 없습니다. `python study.py web install` 로 한 번 더 설치하면 표시가 생깁니다."
    elif stale:
        problem = "패키지 목록이 바뀌었습니다. `python study.py web install` 로 다시 설치해 주세요."
    return {"installed": has, "stale": stale, "no_marker": no_marker, "node": node, "problem": problem, "lock": current,
            "size_mb": SIZE_MB, "dir": os.path.join(root, "node_modules")}


def consent_text(root, node=None):
    """설치 동의 글. 무엇을, 얼마나, 언제 인터넷이 필요한지, 어디에, 지우는 법을 적음."""
    lines = ["검사 도구 약 %dMB 를 이 컴퓨터에 설치합니다(저장소에 올라가지 않습니다)." % SIZE_MB, "",
             "무엇을: 저장소 맨 위 package.json 에 적힌 vitest, jsdom, React, Testing Library 입니다. 라이브 코딩 미션의 "
             "단계 검사를 돌리고 미션 폴더에서 `npm run dev` 와 `npm test` 를 쓰는 데 필요합니다.",
             "어디에: %s" % os.path.join(root, "node_modules"),
             "언제 인터넷이 필요한가요: 처음 설치할 때 한 번입니다. 그 뒤 검사는 인터넷 없이 돕니다.",
             "지우는 법: `python study.py web uninstall` 을 실행하거나 위 폴더를 지웁니다.",
             "설치 로그: %s" % log_path()]
    if node:
        lines.append("쓰는 Node.js: %s (%s)" % (node["version"], node["path"]))
    if "onedrive" in root.lower():
        lines += ["", "저장소가 OneDrive 아래에 있습니다. 수천 개 파일이 동기화되며 설치가 느려질 수 있으니, "
                  "저장소를 OneDrive 밖으로 옮기는 편이 낫습니다."]
    return "\n".join(lines)


def _env():
    env = dict(os.environ)
    env.pop("NODE_OPTIONS", None)
    env["CI"] = "1"
    env["FORCE_COLOR"] = "0"
    return env


def install(root, node, report=None):
    """node_modules 를 설치함. {"ok", "message", "seconds", "log"}. report(글) 가 있으면 진행 안내를 넘김."""
    log = log_path()
    cli = npm_cli(node["path"])
    if cli is None:
        return {"ok": False, "seconds": 0.0, "log": log,
                "message": "node 옆에서 npm-cli.js 를 찾지 못했습니다: %s" % os.path.dirname(node["path"])}
    if not os.path.isfile(os.path.join(root, LOCK_NAME)):
        return {"ok": False, "seconds": 0.0, "log": log, "message": "저장소 맨 위에서 %s 을 찾지 못했습니다." % LOCK_NAME}
    os.makedirs(os.path.dirname(log), exist_ok=True)
    if report:
        report("검사 도구를 설치하는 중입니다. 몇 분 걸릴 수 있습니다.")
    started = time.monotonic()
    try:
        with open(log, "w", encoding="utf-8", errors="replace") as handle:
            handle.write("$ %s %s %s\n" % (node["path"], cli, " ".join(NPM_ARGS)))
            handle.flush()
            done = _run([node["path"], cli] + list(NPM_ARGS), cwd=root, stdin=subprocess.DEVNULL, stdout=handle,
                        stderr=subprocess.STDOUT, timeout=INSTALL_LIMIT_S, env=_env(), creationflags=study.NO_WINDOW)
    except subprocess.TimeoutExpired:
        return {"ok": False, "seconds": time.monotonic() - started, "log": log,
                "message": "설치가 %d분 안에 끝나지 않아 멈췄습니다. 네트워크를 확인하고 다시 시도해 주세요. 로그: %s"
                           % (INSTALL_LIMIT_S // 60, log)}
    except OSError as error:
        return {"ok": False, "seconds": time.monotonic() - started, "log": log,
                "message": "설치 명령을 실행하지 못했습니다: %s" % error}
    seconds = time.monotonic() - started
    if done.returncode != 0:
        return {"ok": False, "seconds": seconds, "log": log,
                "message": "설치가 실패했습니다(종료 코드 %d). 로그를 확인해 주세요: %s" % (done.returncode, log)}
    if not installed(root):
        return {"ok": False, "seconds": seconds, "log": log,
                "message": "설치는 끝났지만 %s 가 없습니다. 로그를 확인해 주세요: %s" % (VITEST_MJS, log)}
    current = lock_hash(root)
    try:
        study.write_text(marker_path(root), (current or "") + "\n")
    except OSError as error:
        return {"ok": False, "seconds": seconds, "log": log, "message": "설치 표시를 쓰지 못했습니다: %s" % error}
    return {"ok": True, "seconds": seconds, "log": log, "message": "검사 도구를 설치했습니다(%d초)." % round(seconds)}


def uninstall(root):
    """node_modules 와 .web-check 를 지움. {"removed": [경로]}."""
    removed = []
    for name in ("node_modules", ".web-check"):
        path = os.path.join(root, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path)
    return {"removed": removed}
