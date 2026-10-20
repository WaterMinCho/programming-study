# -*- coding: utf-8 -*-
"""Node 찾기·버전 확인·기억.

JourneySession 을 만들 때는 찾지 않고, 처음 JS 를 고르거나 runtime("javascript") 를 물을 때 찾아 프로세스 안에서 기억함.
후보 목록은 candidates() 라는 순수 함수가 만들고(파일이 있는지는 보지 않음), 실제 파일 확인과 --version 은 그 뒤에 함.
그래서 Windows 경로 순서도 macOS·Linux 의 테스트에서 가짜 환경 변수로 확인할 수 있음. 로그인 셸에 묻는 것은
[다시 찾기]를 눌렀을 때뿐이고 -lc 만 씀(-i 는 .zshrc 전체를 GUI 뒤에서 돌림).
"""
import glob
import json
import ntpath
import os
import posixpath
import re
import subprocess
import sys

import study

MIN_MAJOR = 20
VERSION_LIMIT_S = 5
PROBE_LIMIT_S = 5
VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
PREFIX_RE = re.compile(r"v?(\d+(?:\.\d+){0,2})\Z")
SHELLS = ("/bin/zsh", "/bin/bash")
MAC_FIXED = ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/opt/local/bin/node")

_found = None  # None 은 아직 찾지 않음, False 는 못 찾음, 아니면 {"path", "version", "major"}
_run = subprocess.run  # 테스트가 가짜로 바꿔 끼움


def _read_or_none(path):
    try:
        return study.read_text(path)
    except (OSError, UnicodeDecodeError):
        return None


def _volta_version(read, platform_json):
    text = read(platform_json)
    if not text:
        return None
    try:
        return json.loads(text)["node"]["runtime"]
    except (ValueError, KeyError, TypeError):
        return None


def _dedupe(paths):
    seen = {}
    for path in paths:
        if path and path not in seen:
            seen[path] = True
    return list(seen)


def candidates(env, home, platform, saved=None, read=None):
    """Node 실행 파일 후보를 3.8 의 순서로. `*` 가 든 항목은 expand() 가 가장 높은 버전부터 펼침.
    read 는 경로를 받아 파일 내용이나 None 을 돌려주는 함수(nvm 기본 별칭, Volta platform.json 을 읽음)."""
    read = read or (lambda path: None)
    join = ntpath.join if platform == "win32" else posixpath.join
    out = []
    if env.get("STUDY_NODE"):
        out.append(env["STUDY_NODE"])
    if saved:
        out.append(saved)
    if platform == "win32":
        volta_home = env.get("VOLTA_HOME") or (join(env["LOCALAPPDATA"], "Volta") if env.get("LOCALAPPDATA") else None)
        volta_bin = join(volta_home, "bin").lower() if volta_home else None
        for folder in (env.get("PATH") or "").split(";"):
            folder = folder.strip().strip('"')
            if folder and (not volta_bin or folder.rstrip("\\/").lower() != volta_bin):
                out.append(join(folder, "node.exe"))
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            if env.get(var):
                out.append(join(env[var], "nodejs", "node.exe"))
        if env.get("NVM_SYMLINK"):
            out.append(join(env["NVM_SYMLINK"], "node.exe"))
        out.append("C:\\nvm4w\\nodejs\\node.exe")
        for nvm_home in (env.get("NVM_HOME"), join(env["LOCALAPPDATA"], "nvm") if env.get("LOCALAPPDATA") else None,
                         join(env["APPDATA"], "nvm") if env.get("APPDATA") else None):
            if nvm_home:
                out.append(join(nvm_home, "v*", "node.exe"))
        if volta_home:
            version = _volta_version(read, join(volta_home, "tools", "user", "platform.json"))
            out.append(join(volta_home, "tools", "image", "node", version or "*", "node.exe"))
        out.append(join(home, "scoop", "apps", "nodejs", "current", "node.exe"))
        return _dedupe(out)

    volta_home = env.get("VOLTA_HOME") or join(home, ".volta")
    volta_bin = join(volta_home, "bin")
    for folder in (env.get("PATH") or "").split(":"):
        if folder and folder.rstrip("/") != volta_bin:
            out.append(join(folder, "node"))
    nvm_dir = env.get("NVM_DIR") or join(home, ".nvm")
    default = (read(join(nvm_dir, "alias", "default")) or "").strip()
    found = PREFIX_RE.match(default)
    if found:
        out.append(join(nvm_dir, "versions", "node", "v%s*" % found.group(1), "bin", "node"))
    out.append(join(nvm_dir, "versions", "node", "v*", "bin", "node"))
    out.extend(MAC_FIXED)
    version = _volta_version(read, join(volta_home, "tools", "user", "platform.json"))
    out.append(join(volta_home, "tools", "image", "node", version or "*", "bin", "node"))
    fnm_dirs = [env["FNM_DIR"]] if env.get("FNM_DIR") else []
    fnm_dirs += [join(home, ".local", "share", "fnm"), join(home, "Library", "Application Support", "fnm")]
    for folder in fnm_dirs:
        out.append(join(folder, "aliases", "default", "bin", "node"))
    return _dedupe(out)


def expand(pattern):
    """`*` 가 든 후보를 실제 경로로 펼쳐 버전이 높은 것부터 돌려줌. 없으면 그대로 한 개."""
    if "*" not in pattern:
        return [pattern]
    fixed = pattern.index("*")

    def version_key(path):
        return [int(part) for part in re.findall(r"\d+", path[fixed:])]

    return sorted(glob.glob(pattern), key=version_key, reverse=True)


def runnable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def inspect(path):
    """`node --version` 으로 판을 확인함. 돌릴 수 없으면 None, 아니면 {"path", "version", "major", "ok"}."""
    try:
        proc = _run([path, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    timeout=VERSION_LIMIT_S, creationflags=study.NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    output = proc.stdout.decode("utf-8", "replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
    found = VERSION_RE.match(output.strip())
    if not found:
        return None
    major = int(found.group(1))
    return {"path": path, "version": "%s.%s.%s" % found.groups(), "major": major, "ok": major >= MIN_MAJOR}


def check(path):
    """사용자가 직접 고른 경로를 확인함. 쓸 수 있으면 {"path", "version", "major"}, 아니면 ValueError(사용자 문구)."""
    if not path or not runnable(path):
        raise ValueError("실행할 수 있는 파일이 아닙니다: %s" % (path or "(비어 있음)"))
    info = inspect(path)
    if info is None:
        raise ValueError("Node.js 실행 파일이 아니거나 버전을 알 수 없습니다: %s" % path)
    if not info["ok"]:
        raise ValueError("Node.js %d 이상이 필요한데 이 파일은 %s 입니다." % (MIN_MAJOR, info["version"]))
    return {"path": info["path"], "version": info["version"], "major": info["major"]}


def shell_probe(env):
    """로그인 셸에 `command -v node` 를 물음. 출력의 마지막 줄이 실행할 수 있는 절대 경로일 때만 돌려줌."""
    shell = env.get("SHELL") if env.get("SHELL") in SHELLS else "/bin/zsh"
    try:
        proc = _run([shell, "-lc", "command -v node"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, timeout=PROBE_LIMIT_S, env=dict(env, TERM="dumb"))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    output = proc.stdout.decode("utf-8", "replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if lines and os.path.isabs(lines[-1]) and runnable(lines[-1]):
        return lines[-1]
    return None


def search(probe=False, saved=None, env=None, home=None, platform=None):
    """기억을 쓰지 않고 지금 찾음. 못 찾으면 None."""
    env = os.environ if env is None else env
    home = home or os.path.expanduser("~")
    platform = platform or sys.platform
    paths = []
    for pattern in candidates(env, home, platform, saved, _read_or_none):
        paths.extend(expand(pattern))
    if probe and platform != "win32" and env.get("STUDY_NODE_PROBE") != "0":
        probed = shell_probe(env)
        if probed:
            paths.append(probed)
    for path in _dedupe(paths):
        if not runnable(path):
            continue
        info = inspect(path)
        if info and info["ok"]:
            return {"path": info["path"], "version": info["version"], "major": info["major"]}
    return None


def find(probe=False, saved=None):
    """기억한 결과를 돌려주고, 아직 없거나 probe 면 다시 찾음."""
    global _found
    if _found is None or probe:
        _found = search(probe, saved) or False
    return _found or None


def remember(info):
    """사용자가 고른 경로를 확인한 결과를 기억함."""
    global _found
    _found = info or False


def forget():
    global _found
    _found = None
