# -*- coding: utf-8 -*-
"""미션 폴더에서 화면 띄우기(vite 개발 서버)와 내 테스트 돌리기(vitest run).

Windows 의 PowerShell 은 `npm` 을 npm.ps1 로 찾아서 스크립트 실행 정책이 기본값이면 `npm run dev` 가 막힘. 그래서 셸과 npm 을
거치지 않고 node 로 저장소 맨 위 node_modules 의 vite 와 vitest 를 미션 폴더에서 바로 돌림. 실행 정책은 건드리지 않음.
자식은 새 세션(Windows 는 콘솔 없이)에서 돌아 터미널의 신호를 받지 않음. 끄는 길은 DevServer.stop, stop_all, stop_on_hangup,
_hold 에 있음.
테스트 결과는 JSON 보고서와 기본 출력을 같이 읽어 npm test 와 같은 통과·실패를 냄(parse_tests, run_tests).
"""
import atexit
import collections
import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

import study
from webprep import checks, stack

VITE_JS = os.path.join("node_modules", "vite", "bin", "vite.js")
START_LIMIT_S = 30
TEST_LIMIT_S = checks.LIMIT_S  # 도는 동안 미션 화면이 잠기므로, [검사]가 같은 vitest·jsdom 실행에 두는 한도를 씀
WAIT_STEP_S = 0.5  # 테스트를 기다리며 취소 신호를 보는 간격
TAIL_LINES = 40
LOCAL_URL = re.compile(r"Local:\s+(https?://\S+)")
STACK_LINE = re.compile(r"^\s+at ")
FAIL_HEAD = re.compile(r"^\s*FAIL\s+(.*\S)")
UNHANDLED = "Unhandled Error"
RULE = "\u23af"  # vitest 기본 출력의 구분선 글자
TIMED_OUT = "Error: STACK_TRACE_ERROR"  # 시간 제한을 넘긴 테스트의 JSON 실패 문구 첫 줄
TIMED_OUT_TEXT = "테스트가 vitest 의 시간 제한(testTimeout) 안에 끝나지 않았습니다."
KILL_ON_JOB_CLOSE, EXTENDED_LIMITS = 0x2000, 9  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, JobObjectExtendedLimitInformation
_popen = subprocess.Popen  # 테스트가 가짜로 바꿔 끼움
_kill_tree = checks._kill_tree  # 테스트가 가짜로 바꿔 끼움
_running = set()  # atexit 에서 끌 서버
_stopping = []  # stop(wait=False) 가 맡긴 끊기 스레드
_tests = {}  # 돌고 있는 vitest 와 그 결과 폴더. 신호를 받아 끝날 때 stop_all 이 끊고 지움
_job = []  # Windows 의 kernel32 와 작업 개체 핸들. 핸들은 파이썬이 끝날 때 닫힘


class DevError(Exception):
    """화면을 띄우거나 테스트를 돌리지 못함. 문구는 사용자에게 그대로 보여 줌."""


def _env():
    """npm run dev, npm test 처럼 CI 를 두지 않음. 색을 끄고 NODE_OPTIONS 를 비우는 것은 [검사]와 같음."""
    env = dict(os.environ)
    env.pop("NODE_OPTIONS", None)
    env["FORCE_COLOR"] = "0"
    return env


def _options(folder):
    options = {"cwd": folder, "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
               "env": _env(), "creationflags": study.NO_WINDOW}
    if sys.platform != "win32":
        options["start_new_session"] = True
    return options


def _tool(repo, rel):
    path = os.path.join(repo, rel)
    if not os.path.isfile(path):
        raise DevError("%s 를 찾지 못했습니다. `python study.py web install` 로 검사 도구를 설치해 주세요." % study.shown_path(path))
    return path


class _JobLimits(ctypes.Structure):
    """JOBOBJECT_EXTENDED_LIMIT_INFORMATION. flags(LimitFlags) 만 씀."""
    _fields_ = [("time_limits", ctypes.c_int64 * 2), ("flags", ctypes.c_uint32), ("working_set", ctypes.c_size_t * 2),
                ("process_limit", ctypes.c_uint32), ("affinity", ctypes.c_size_t), ("priority", ctypes.c_uint32),
                ("scheduling", ctypes.c_uint32), ("io_counters", ctypes.c_uint64 * 6), ("memory", ctypes.c_size_t * 4)]


def _hold(proc):
    """Windows 에서 자식을 KILL_ON_JOB_CLOSE 작업 개체에 넣음. 콘솔 창을 닫거나 작업 관리자로 끝내 이 파이썬이 atexit 없이 끝나도
    작업 개체의 핸들이 닫히면서 OS 가 자식과 그 아래(esbuild, vitest 워커)를 끊음. 넣으면 True. 넣지 못하면 stop 과 atexit 에 맡김."""
    if sys.platform != "win32":
        return False
    if not _job:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        handle = kernel32.CreateJobObjectW(None, None)
        limits = _JobLimits(flags=KILL_ON_JOB_CLOSE)
        if not handle or not kernel32.SetInformationJobObject(ctypes.c_void_p(handle), EXTENDED_LIMITS, ctypes.byref(limits),
                                                             ctypes.sizeof(limits)):
            if handle:
                kernel32.CloseHandle(ctypes.c_void_p(handle))
            return False
        _job[:] = [kernel32, handle]
    kernel32, handle = _job
    return bool(kernel32.AssignProcessToJobObject(ctypes.c_void_p(handle), ctypes.c_void_p(int(proc._handle))))


class DevServer:
    """미션 폴더 하나의 vite 개발 서버. start 로 띄우고 stop 으로 끔. 한 번 띄운 뒤에는 다시 쓰지 않고 새로 만듦."""

    def __init__(self, node_path, repo, folder):
        self.node_path, self.repo, self.folder = node_path, repo, folder
        self.proc, self.reader, self.url = None, None, ""
        self.lines = collections.deque(maxlen=TAIL_LINES)
        self.seen = threading.Event()

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def tail(self, count=12, wait=True):
        """끝 count 줄. wait 가 참이고 서버가 끝났으면 남은 출력을 다 읽을 때까지 잠깐 기다림."""
        if wait and self.reader is not None and self.proc.poll() is not None:
            self.reader.join(1)
        return "\n".join(list(self.lines)[-count:])

    def start(self, limit=START_LIMIT_S):
        """서버를 띄우고 출력에 나온 Local 주소(끝의 / 는 뺌)를 돌려줌. limit 초 안에 주소가 나오지 않거나 그 전에 끝나면 끄고 DevError."""
        vite = _tool(self.repo, VITE_JS)
        try:
            self.proc = _popen([self.node_path, vite], **_options(self.folder))
        except OSError as error:
            raise DevError("화면 서버를 실행하지 못했습니다: %s" % error)
        _hold(self.proc)
        _running.add(self)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        deadline = time.monotonic() + limit
        while not self.seen.wait(0.1) and self.proc.poll() is None and time.monotonic() < deadline:
            pass
        if self.url:
            return self.url
        code = self.proc.poll()
        self.stop()
        if code is None:
            raise DevError("화면 서버가 %d초 안에 주소를 알려 주지 않아 껐습니다.\n%s" % (limit, self.tail()))
        raise DevError("화면 서버가 바로 끝났습니다(종료 코드 %s).\n%s" % (code, self.tail()))

    def _read(self):
        """출력을 끝까지 읽어 끝 줄을 남김. 주소를 보면 start 의 기다림을 풂."""
        for raw in iter(self.proc.stdout.readline, b""):
            line = checks.ANSI.sub("", raw.decode("utf-8", "replace")).rstrip()
            self.lines.append(line)
            found = LOCAL_URL.search(line)
            if found and not self.url:
                self.url = found.group(1).rstrip("/")
                self.seen.set()
        self.proc.stdout.close()

    def stop(self, wait=True):
        """서버와 그 아래 프로세스를 끊음. 이미 끝났으면 끊지 않음(같은 번호를 다른 프로세스가 받았을 수 있음).
        wait 가 거짓이면 끊고 기다리는 일을 스레드에 맡기고 바로 돌아옴. 그 스레드는 settle 이 기다림."""
        _running.discard(self)
        if self.proc is None:
            return
        if wait:
            self._end()
            return
        thread = threading.Thread(target=self._end, daemon=True)
        _stopping[:] = [t for t in _stopping if t.is_alive()] + [thread]
        thread.start()

    def _end(self):
        proc = self.proc
        if proc.poll() is None:
            _kill_tree(proc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def settle(limit=10):
    """stop(wait=False) 로 맡긴 끊기가 끝날 때까지 기다림."""
    for thread in list(_stopping):
        thread.join(limit)
    _stopping[:] = [t for t in _stopping if t.is_alive()]


@atexit.register
def stop_all():
    """켜 둔 서버와 돌던 테스트를 모두 끊고 테스트의 결과 폴더를 지운 뒤, 맡겨 둔 끊기를 기다림."""
    for server in list(_running):
        server.stop()
    for proc, tmp in list(_tests.items()):
        _kill_tree(proc)
        shutil.rmtree(tmp, True)
    settle()


def _die(signum, frame):
    """stop_on_hangup 의 처리기. 자식을 끊은 뒤 처리기를 기본으로 되돌리고 같은 신호를 다시 받아 끝남."""
    stop_all()
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


def stop_on_hangup():
    """터미널 창을 닫아 오는 SIGHUP 과 끝내라는 SIGTERM 을 받으면 켜 둔 서버와 돌던 테스트를 끊고 끝나게 함. 처리기가 없으면 파이썬은
    이 신호로 바로 끝나고 새 세션의 자식은 남음. nohup 으로 띄워 무시하도록 물려받은 신호는 그대로 무시함. 메인 스레드에서 부름.
    Windows 는 _hold 의 작업 개체가 같은 일을 해서 걸지 않음."""
    if sys.platform == "win32":
        return
    for signum in (signal.SIGHUP, signal.SIGTERM):
        if signal.getsignal(signum) != signal.SIG_IGN:
            signal.signal(signum, _die)


def _rel(path, folder):
    try:
        return os.path.relpath(path, folder).replace(os.sep, "/")
    except ValueError:  # Windows 에서 드라이브가 다른 경우
        return os.path.basename(path)


def _trim(message, folder):
    """실패 문구에서 미션 폴더 밖(node_modules 등)을 가리키는 호출 줄을 빼고, 미션 폴더 경로를 줄여 src/… 로 보임."""
    prefixes = {os.path.join(folder, ""), os.path.join(folder, "").replace("\\", "/")}
    lines = []
    for line in message.splitlines():
        if STACK_LINE.match(line) and not any(p in line for p in prefixes):
            continue
        for prefix in prefixes:
            line = line.replace("file://" + prefix, "").replace("file:///" + prefix, "").replace(prefix, "")
        lines.append(line)
    return "\n".join(lines)


def _message(messages, folder):
    return checks.clean_message([_trim(str(m), folder) for m in messages if m], folder)[0]


def fail_blocks(output):
    """vitest 기본 출력(ANSI 를 지운 글)의 'FAIL <파일> > <이름>' 묶음을 {머리: 글} 로. 같은 오류로 실패한 것은 FAIL 줄이 이어서
    나오고 아래 글을 같이 씀. 묶음은 구분선 글자가 든 줄에서 끝남. 파일 전체의 오류는 머리가 '<파일> [ <파일> ]' 임."""
    blocks, heads, lines = {}, [], None
    for line in output.splitlines() + [RULE]:
        head = FAIL_HEAD.match(line)
        if head and not lines:
            heads.append(head.group(1))
            lines = []
            continue
        if head or RULE in line:
            for name in heads:
                blocks.setdefault(name, "\n".join(lines).strip())
            heads, lines = ([head.group(1)], []) if head else ([], None)
        elif lines is not None:
            lines.append(line)
    return blocks


def parse_tests(text, folder, output=""):
    """vitest JSON 보고서를 {"files", "total", "passed", "failed", "skipped", "fails": [{"file", "name", "message"}]} 로.
    실패한 테스트 없이 실패로 끝난 파일(문법 오류, beforeAll·afterAll 의 오류)은 name 이 빈 글인 실패로 넣음. 그 문구와 시간 제한을
    넘긴 테스트의 문구는 JSON 에 없거나 쓸모없어서 output(기본 출력)의 FAIL 묶음에서 가져옴."""
    try:
        results = json.loads(text)["testResults"]
    except (ValueError, KeyError, TypeError) as error:
        raise DevError("테스트 결과를 읽을 수 없습니다: %s" % (str(error) or type(error).__name__))
    blocks = fail_blocks(output)
    total, passed, skipped, fails = 0, 0, 0, []
    for file_result in results:
        name = _rel(str(file_result.get("name") or ""), folder)
        failed_here = False
        for item in file_result.get("assertionResults") or []:
            status = str(item.get("status") or "")
            if status not in ("passed", "failed"):
                skipped += 1  # skip, todo
                continue
            total += 1
            if status == "passed":
                passed += 1
                continue
            failed_here = True
            title = " > ".join([str(t) for t in item.get("ancestorTitles") or []] + [str(item.get("title") or "")])
            messages = item.get("failureMessages") or []
            if messages and str(messages[0]).startswith(TIMED_OUT):
                messages = [blocks.get("%s > %s" % (name, title)) or TIMED_OUT_TEXT]
            fails.append({"file": name, "name": title, "message": _message(messages, folder) or "테스트가 실패했습니다."})
        if str(file_result.get("status")) != "passed" and not failed_here:
            block = next((body for head, body in blocks.items() if head == name or head.startswith(name + " ")), "")
            message = _message([block or file_result.get("message")], folder)
            fails.append({"file": name, "name": "", "message": message or "테스트 파일이 끝까지 돌지 못했습니다."})
    return {"files": len(results), "total": total, "passed": passed, "failed": total - passed, "skipped": skipped, "fails": fails}


def error_text(output, folder):
    """vitest 기본 출력(ANSI 를 지운 글)에서 오류 줄을 뽑음. Unhandled Errors 묶음이 있으면 그 안의 줄(구분선 글자와 node_modules 호출 줄은 뺌),
    없으면 끝 줄."""
    lines = [line.rstrip() for line in output.splitlines()]
    start = next((n for n, line in enumerate(lines) if UNHANDLED in line), None)
    if start is None:
        picked = [line for line in lines if line.strip() and not line.startswith("JSON report")][-checks.MESSAGE_LINES:]
    else:
        picked = []
        for line in lines[start + 1:]:
            if line.strip().startswith("Test Files"):
                break
            if RULE in line:
                line = line.replace(RULE, "").strip()
            if line.strip() and "node_modules" not in line:
                picked.append(line)
    return _message(["\n".join(picked)], folder)


def _wait(proc, deadline, cancel):
    """vitest 가 끝날 때까지 기다려 출력(bytes)을 돌려줌. deadline 을 넘기거나 cancel 이 서면 None."""
    while time.monotonic() < deadline and not (cancel is not None and cancel.is_set()):
        try:
            return proc.communicate(timeout=WAIT_STEP_S)[0] or b""
        except subprocess.TimeoutExpired:
            pass
    return None


def run_tests(node_path, repo, folder, limit=TEST_LIMIT_S, cancel=None):
    """미션 폴더에서 `vitest run` 을 돌림(npm test 와 같음). parse_tests 의 값에 "ms", "ok" 를 더해 돌려줌.
    ok 는 테스트 파일이 있고 실패와 돌지 못한 파일이 없을 때 참이고, npm test 처럼 테스트가 모두 건너뛰도록 표시되어 있어도 참.
    실패가 없는데 vitest 가 0 이 아닌 코드로 끝나면 그 종료 코드를 code 로 가진 실패를 더함(file, name 은 빈 글).
    limit 초를 넘기면 vitest 를 끊고 DevError. cancel(threading.Event)이 서면 끊고 None."""
    vitest = _tool(repo, stack.VITEST_MJS)
    with tempfile.TemporaryDirectory(prefix="web_test_", **study.TMP_OPTIONS) as tmp:
        out_path = os.path.join(tmp, "result.json")
        started = time.monotonic()
        try:
            proc = _popen([node_path, vitest, "run", "--reporter=json", "--reporter=default", "--outputFile=%s" % out_path],
                          **_options(folder))
        except OSError as error:
            raise DevError("테스트 명령을 실행하지 못했습니다: %s" % error)
        _hold(proc)
        _tests[proc] = tmp
        try:
            output = _wait(proc, started + limit, cancel)
            if output is None:
                _kill_tree(proc)
                try:
                    proc.communicate(timeout=5)
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    pass
        except BaseException:  # Ctrl+C. vitest 는 새 세션(Windows 는 콘솔 없음)이라 신호를 받지 못하므로 끊음
            _kill_tree(proc)
            raise
        finally:
            _tests.pop(proc, None)
        if output is None and cancel is not None and cancel.is_set():
            return None
        if output is None:
            raise DevError("테스트가 %d초 안에 끝나지 않아 멈췄습니다. 무한 반복이나 끝나지 않는 await 가 있는지 확인해 주세요." % limit)
        output = checks.ANSI.sub("", output.decode("utf-8", "replace"))
        ms = int((time.monotonic() - started) * 1000)
        try:
            text = study.read_text(out_path)
        except OSError:  # 설정 파일 오류처럼 vitest 가 시작하지 못함. 원인은 앞쪽 줄에 있고 뒤쪽은 node_modules 안 호출 줄임
            shown = [line.replace(RULE, "").rstrip() for line in output.splitlines()]
            raise DevError("테스트 결과 파일이 만들어지지 않았습니다(종료 코드 %s).\n%s"
                           % (proc.returncode, _message(["\n".join(line for line in shown if line.strip())], folder)))
    result = parse_tests(text, folder, output)
    if proc.returncode and result["files"] and not result["fails"]:
        result["fails"].append({"file": "", "name": "", "code": proc.returncode, "message": error_text(output, folder)})
    result["ms"] = ms
    result["ok"] = bool(result["files"]) and not result["fails"]
    return result


def summary(result):
    """상태 줄과 `web test` 의 끝 줄에 쓰는 한 줄."""
    if not result["files"]:
        return "돌릴 테스트를 찾지 못했습니다. 미션 폴더에 .test.ts(x) 파일이 있는지 확인해 주세요."
    broken = sum(1 for fail in result["fails"] if not fail["name"] and "code" not in fail)
    if result["total"]:
        text = "내 테스트 %d개 가운데 %d개 통과" % (result["total"], result["passed"])
        if broken:
            text += ", 돌지 못한 파일 %d개" % broken
    elif broken:
        text = "내 테스트 파일 %d개가 끝까지 돌지 못했습니다" % broken
    else:
        text = "내 테스트 %d개가 모두 skip 이나 todo 로 표시되어 돌린 테스트가 없습니다" % result["skipped"]
    if any("code" in fail for fail in result["fails"]):
        text += ". vitest 는 오류로 끝났습니다" if text.endswith("니다") else ", vitest 오류로 실패"
    return text + " (%.1f초)" % (result["ms"] / 1000.0)


def failure_text(fail):
    """실패 하나의 글. 첫 줄은 파일과 테스트 이름, 그 아래는 실패 문구 앞 줄."""
    if "code" in fail:
        head = "vitest 가 오류로 끝났습니다(종료 코드 %s). 테스트가 모두 통과해도 npm test 는 실패로 끝납니다." % fail["code"]
    elif fail["name"]:
        head = "%s > %s" % (fail["file"], fail["name"])
    else:
        head = "%s 파일이 끝까지 돌지 못했습니다" % fail["file"]
    return "%s\n%s" % (head, fail["message"])
