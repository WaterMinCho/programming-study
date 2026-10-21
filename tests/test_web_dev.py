# -*- coding: utf-8 -*-
"""미션 폴더의 화면 서버와 내 테스트(webprep/dev.py), 그것을 부르는 서비스(serve, stop_serving, own_tests), 터미널 명령
`web dev`·`web test` 테스트. 프로세스는 가짜를 씀. FakeServer 는 vite 처럼 주소를 출력하고 끊길 때까지 돌고, FakeTestRun 은
vitest JSON 보고서를 쓰고 끝남. 프로세스 트리 끊기와 Windows 작업 개체에 넣기도 가짜로 바꿔 실제 프로세스를 건드리지 않음.
HangupTest 는 진짜 파이썬 자식이 가짜 도구(파이썬 스크립트)를 띄우게 하고 그 자식에 신호를 보내, 남는 프로세스가 없는지 봄.
RealJobTest 는 Windows 에서 진짜 작업 개체에 넣은 손자가, 자식 파이썬을 강제로 끝낼 때 같이 끝나는지 봄.
실제 vite·vitest 를 띄우는 통합 테스트는 저장소 맨 위에 node_modules 가 있고 Node 22.12 이상이 있을 때만 돎.

실행: python -m unittest tests.test_web_dev
"""
import ctypes
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.request
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from webprep import checks, cli, dev, stack  # noqa: E402
from webprep.service import WebError  # noqa: E402
from tests.test_web_cli import CliBase  # noqa: E402
from tests.test_web_service import Base  # noqa: E402

REAL_NODE = None if os.environ.get("STUDY_LEAN_CI") else stack.find_node()
HAS_VITE = os.path.isfile(os.path.join(ROOT, dev.VITE_JS)) and os.path.isfile(os.path.join(ROOT, stack.VITEST_MJS))
FIXTURE_APP = os.path.join(ROOT, "tests", "web_bank", "missions", "x01", "app")
VITE_LINES = (b"\n", b"  VITE v7.3.1  ready in 300 ms\n", b"\n", "  ➜  Local:   http://localhost:5173/\n".encode("utf-8"),
              "  ➜  Network: use --host to expose\n".encode("utf-8"))
RULE = "\u23af"
UNHANDLED_OUTPUT = "\n".join([  # 테스트는 모두 통과했는데 처리되지 않은 거부가 남았을 때 vitest 4 기본 출력의 뒷부분
    " \x1b[32m✓\x1b[39m src/App.test.tsx (1 test) 112ms",
    "\x1b[31m%s\x1b[39m\x1b[1m\x1b[41m Unhandled Errors \x1b[49m\x1b[22m\x1b[31m%s\x1b[39m" % (RULE * 6, RULE * 6),
    "", "Vitest caught 1 unhandled error during the test run.", "",
    "%s Unhandled Rejection %s" % (RULE * 4, RULE * 5),
    "Error: boom",
    " ❯ src/boom.test.ts:3:18",
    "      3|   Promise.reject(new Error('boom'));",
    "       |                  ^",
    " ❯ ../../node_modules/@vitest/runner/dist/index.js:145:11",
    "",
    RULE * 30, "", "",
    " Test Files  1 passed (1)",
    "      Tests  1 passed (1)",
    "     Errors  1 error",
    "JSON report written to /tmp/result.json", ""]).encode("utf-8")
HOOK_OUTPUT = "\n".join([  # beforeAll·afterAll 이 던졌을 때 vitest 4 기본 출력의 뒷부분. JSON 에는 이 문구가 없거나 짧음
    " ❯ src/format.test.ts (1 test | 1 skipped) 2ms",
    " ✓ src/App.test.tsx (1 test) 92ms", "",
    "%s Failed Suites 2 %s" % (RULE * 6, RULE * 7), "",
    " FAIL  src/format.test.ts > 준비 실패",
    "Error: 준비 단계에서 터짐",
    " ❯ src/format.test.ts:5:27",
    "      5|   beforeAll(() => { throw new Error('준비 단계에서 터짐'); });",
    "       |                           ^", "",
    "%s[1/2]%s" % (RULE * 24, RULE), "",
    " FAIL  src/close.test.ts [ src/close.test.ts ]",
    "TypeError: Cannot read properties of undefined (reading 'close')",
    " ❯ src/close.test.ts:5:26", "",
    "%s[2/2]%s" % (RULE * 24, RULE), "", "",
    " Test Files  2 failed | 1 passed (3)",
    "      Tests  2 passed | 1 skipped (3)",
    "JSON report written to /tmp/result.json", ""]).encode("utf-8")
TIMEOUT_OUTPUT = "\n".join([  # 시간 제한을 넘긴 테스트. 같은 오류로 실패한 테스트는 FAIL 줄이 이어서 나옴
    "%s Failed Tests 2 %s" % (RULE * 7, RULE * 7), "",
    " FAIL  src/format.test.ts > 기다림 > 끝나지 않는 기다림",
    " FAIL  src/format.test.ts > 기다림 > 또 끝나지 않는 기다림",
    "Error: Test timed out in 5000ms.",
    "If this is a long-running test, pass a timeout value as the last argument or configure it globally with \"testTimeout\".",
    " ❯ src/format.test.ts:8:3", "",
    "%s[1/1]%s" % (RULE * 24, RULE), "", " Test Files  1 failed (1)", ""]).encode("utf-8")
STARTUP_OUTPUT = "\n".join(  # vite.config.ts 가 깨져 vitest 가 시작하지 못함. 원인은 앞에 있고 끝 12줄에는 원인이 없음
    ["\u2718 [ERROR] Expected identifier but found \"{\"", "", "    vite.config.ts:11:16:", "      11 \u2502 export default {{", "",
     "failed to load config from /work/mission/vite.config.ts", "", "%s Startup Error %s" % (RULE * 7, RULE * 8),
     "Error: Build failed with 1 error:", "vite.config.ts:11:16: ERROR: Expected identifier but found \"{\""]
    + ["    at step%d (/repo/node_modules/esbuild/lib/main.js:%d:15)" % (n, 1000 + n) for n in range(9)]
    + ["    at addChunk (node:internal/streams/readable:561:12) {", "  errors: [Getter/Setter],", "  warnings: [Getter/Setter]", "}"]
).encode("utf-8")
FAKE_TOOL = """import os, time
path = os.path.join(os.getcwd(), "pid")
with open(path + ".new", "w") as f:
    f.write(str(os.getpid()))
os.replace(path + ".new", path)
print("  Local:   http://localhost:5173/", flush=True)
time.sleep(60)
"""
CHILD = """import os, sys, time
sys.path.insert(0, sys.argv[1])
from webprep import cli, dev
mode, repo, folder = sys.argv[2:5]


class Web(object):
    server = None

    def serve(self, mid):
        self.server = dev.DevServer(sys.executable, repo, folder)
        return {"mid": mid, "url": self.server.start(limit=20)}

    def serving(self):
        return {"running": self.server.running}

    def stop_serving(self, wait=True):
        self.server.stop(wait)

    def own_tests(self, mid):
        return dev.run_tests(sys.executable, repo, folder)


if mode == "exit":
    Web().serve("x01")
elif mode == "gui":
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from gui import app
    qapp = QApplication(sys.argv[:1])
    app.stop_servers_on_hangup(qapp)
    Web().serve("x01")
    QTimer.singleShot(0, lambda: open(os.path.join(folder, "looping"), "w").close())  # 이벤트 루프에 들어갔다는 표시
    qapp.exec()
else:
    getattr(cli.Cli(print, input, time.monotonic), mode)(Web(), "x01")
"""
JOB_CHILD = """import subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import study
from webprep import dev
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=study.NO_WINDOW)
print(grandchild.pid, dev._hold(grandchild), flush=True)
time.sleep(120)
"""


class FakeServer(object):
    """dev._popen 자리(vite). lines 를 출력하고, code 가 None 이면 kill 될 때까지 돌고 숫자면 출력 뒤 바로 그 코드로 끝남.
    pid 가 None 이라 진짜 프로세스 트리 끊기에 넘어가면 TypeError 로 멈춤."""

    procs = []
    lines = VITE_LINES
    code = None

    def __init__(self, cmd, **options):
        FakeServer.procs.append(self)
        self.cmd, self.options, self.pid, self.returncode, self.killed = cmd, options, None, None, False
        read, self.pipe = os.pipe()
        self.stdout = os.fdopen(read, "rb")
        for line in self.lines:
            os.write(self.pipe, line)
        if self.code is not None:
            self.end(self.code)

    def end(self, code):
        if self.returncode is None:
            self.returncode = code
            os.close(self.pipe)

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.end(-9)

    def wait(self, timeout=None):
        return self.returncode


class FakeTestRun(object):
    """dev._popen 자리(vitest run). report 를 --outputFile 에 쓰고 바로 끝남. report 가 None 이면 쓰지 않고 output 만 냄."""

    calls = []
    report = None
    output = b""
    code = 0

    def __init__(self, cmd, **options):
        FakeTestRun.calls.append((cmd, options))
        self.returncode = self.code
        if self.report is not None:
            out = [a for a in cmd if a.startswith("--outputFile=")][0].split("=", 1)[1]
            study.write_text(out, json.dumps(self.report))

    def communicate(self, timeout=None):
        return self.output, None


def fake_popen(cmd, **options):
    """vite.js 면 FakeServer, 아니면 FakeTestRun."""
    return (FakeServer if cmd[1].endswith("vite.js") else FakeTestRun)(cmd, **options)


class HangingRun(object):
    """dev._popen 자리(끝나지 않는 vitest run). 끊길 때까지 communicate 가 TimeoutExpired 를 냄."""

    procs = []

    def __init__(self, cmd, **options):
        HangingRun.procs.append(self)
        self.killed = threading.Event()
        self.waits = []

    def communicate(self, timeout=None):
        self.waits.append(timeout)
        if self.killed.wait(min(timeout, 0.05)):
            return b"", None
        raise subprocess.TimeoutExpired("vitest", timeout)

    def kill(self):
        self.killed.set()


def start_child(test, mode, env=None, preexec_fn=None):
    """CHILD 를 mode 로 띄우고 가짜 도구가 pid 를 남길 때까지 기다린 뒤 (자식, 가짜 도구의 pid, 자식의 임시 폴더)를 돌려줌.
    preexec_fn 은 자식이 파이썬을 실행하기 전에 자식 안에서 부름."""
    tmp = tempfile.mkdtemp(prefix="web_hup_")
    test.addCleanup(shutil.rmtree, tmp, True)
    repo, folder = os.path.join(tmp, "repo"), os.path.join(tmp, "mission")
    for rel in (dev.VITE_JS, stack.VITEST_MJS):
        study.write_text(os.path.join(repo, rel), FAKE_TOOL)
    os.makedirs(folder)
    script, log = os.path.join(tmp, "child.py"), os.path.join(tmp, "child.log")
    study.write_text(script, CHILD)
    with open(log, "wb") as err:
        child = subprocess.Popen([sys.executable, script, ROOT, mode, repo, folder], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=err, env=dict(os.environ, TMPDIR=tmp, **(env or {})), preexec_fn=preexec_fn)
    test.addCleanup(child.wait)
    test.addCleanup(child.kill)
    pid = int(study.read_text(wait_file(test, child, tmp, os.path.join("mission", "pid"))))
    test.addCleanup(kill_group, pid)
    return child, pid, tmp


def wait_file(test, child, tmp, rel):
    """start_child 의 자식이 tmp 아래에 rel 을 쓸 때까지 기다리고 그 경로를 돌려줌. 그 전에 자식이 끝나면 자식의 오류 출력으로 실패함."""
    path, deadline = os.path.join(tmp, rel), time.monotonic() + 30
    while not os.path.isfile(path):
        test.assertIsNone(child.poll(), study.read_text(os.path.join(tmp, "child.log")))
        test.assertLess(time.monotonic(), deadline, "%s 가 생기지 않았습니다" % rel)
        time.sleep(0.05)
    return path


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def group_gone(pid, limit=5):
    """pid 가 이끄는 프로세스 그룹이 limit 초 안에 모두 끝나면 참."""
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def reset_fakes():
    FakeServer.procs, FakeServer.lines, FakeServer.code = [], VITE_LINES, None
    FakeTestRun.calls, FakeTestRun.report, FakeTestRun.output, FakeTestRun.code = [], None, b"", 0


def vitest_report(folder, fail=False, broken=False):
    """미션 폴더의 테스트 보고서. 통과 1개와 건너뜀 1개에, fail 이면 실패 1개, broken 이면 끝까지 돌지 못한 파일 1개를 더함.
    실패 문구에는 vitest 처럼 미션 폴더의 절대 경로와 node_modules 안 호출 줄이 들어 있음."""
    runner = "file:///repo/node_modules/@vitest/runner/dist/index.js:915:20"
    rows = [{"ancestorTitles": ["App"], "title": "제목이 보입니다", "status": "passed", "failureMessages": []},
            {"ancestorTitles": [], "title": "나중에 쓸 테스트", "status": "skipped", "failureMessages": []}]
    if fail:
        rows.append({"ancestorTitles": ["App"], "title": "더하기를 누르면 1", "status": "failed",
                     "failureMessages": ["\x1b[31mAssertionError: expected '0' to be '1'\x1b[39m\n    at %s:12:5\n    at %s\n"
                                         "    at new Promise (<anonymous>)\n\nIgnored nodes: comments\n<body />"
                                         % (os.path.join(folder, "src", "App.test.tsx"), runner)]})
    results = [{"name": os.path.join(folder, "src", "App.test.tsx"), "status": "failed" if fail else "passed", "message": "",
                "assertionResults": rows}]
    if broken:
        results.append({"name": os.path.join(folder, "src", "format.test.ts"), "status": "failed", "assertionResults": [],
                        "message": "Transform failed with 1 error:\n%s:3:1: ERROR: Unexpected \"}\"" % os.path.join(folder, "src", "format.ts")})
    return {"testResults": results}


class FakeBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="web_dev_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        self.folder = os.path.join(self.tmp, "mission")
        for rel in (dev.VITE_JS, stack.VITEST_MJS):
            study.write_text(os.path.join(self.repo, rel), "")
        os.makedirs(self.folder)
        reset_fakes()
        self.held = []
        for name, value in (("_popen", fake_popen), ("_kill_tree", lambda proc: proc.kill()), ("_hold", self.held.append)):
            patcher = mock.patch.object(dev, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(dev.stop_all)

    def server(self):
        return dev.DevServer("/fake/node", self.repo, self.folder)


class DevServerTest(FakeBase):
    def test_start_returns_the_local_url_and_stop_cuts_the_tree(self):
        server = self.server()
        with mock.patch.dict(os.environ, {"NODE_OPTIONS": "--inspect"}):
            os.environ.pop("CI", None)
            self.assertEqual(server.start(limit=5), "http://localhost:5173")
        proc = FakeServer.procs[-1]
        self.assertEqual(proc.cmd, ["/fake/node", os.path.join(self.repo, "node_modules", "vite", "bin", "vite.js")])
        options = proc.options
        self.assertEqual((options["cwd"], options["stdin"], options["creationflags"]), (self.folder, subprocess.DEVNULL, study.NO_WINDOW))
        self.assertNotIn("shell", options)
        self.assertNotIn("CI", options["env"])  # npm run dev 처럼 CI 를 두지 않음
        self.assertEqual(options["env"]["FORCE_COLOR"], "0")
        self.assertNotIn("NODE_OPTIONS", options["env"])
        self.assertEqual(self.held, [proc])  # Windows 는 작업 개체에 넣음
        if sys.platform != "win32":
            self.assertTrue(options["start_new_session"])
        self.assertTrue(server.running)
        self.assertIn(server, dev._running)
        self.assertIn("VITE v7.3.1", server.tail())
        server.stop()
        self.assertTrue(proc.killed)
        self.assertFalse(server.running)
        self.assertNotIn(server, dev._running)

    def test_vite_takes_the_next_port_when_5173_is_busy(self):
        FakeServer.lines = (b"Port 5173 is in use, trying another one...\n", "  ➜  Local:   http://localhost:5174/\n".encode("utf-8"))
        self.assertEqual(self.server().start(limit=5), "http://localhost:5174")

    def test_a_server_that_ends_first_reports_the_code_and_the_last_lines(self):
        FakeServer.lines = (b"failed to load config from vite.config.ts\n", b"error when starting dev server:\n",
                            b"Error: Cannot find module '@vitejs/plugin-react'\n")
        FakeServer.code = 1
        server = self.server()
        with self.assertRaises(dev.DevError) as caught:
            server.start(limit=5)
        self.assertIn("종료 코드 1", str(caught.exception))
        self.assertIn("Cannot find module '@vitejs/plugin-react'", str(caught.exception))
        self.assertFalse(FakeServer.procs[-1].killed)  # 이미 끝난 프로세스는 끊지 않음
        self.assertNotIn(server, dev._running)

    def test_no_url_within_the_limit_stops_the_server(self):
        FakeServer.lines = (b"  VITE v7.3.1\n",)
        with self.assertRaises(dev.DevError) as caught:
            self.server().start(limit=0.3)
        self.assertIn("주소를 알려 주지 않아 껐습니다", str(caught.exception))
        self.assertTrue(FakeServer.procs[-1].killed)

    def test_missing_vite_asks_to_install(self):
        os.remove(os.path.join(self.repo, dev.VITE_JS))
        with self.assertRaises(dev.DevError) as caught:
            self.server().start(limit=5)
        self.assertIn("web install", str(caught.exception))
        self.assertEqual(FakeServer.procs, [])

    def test_stop_all_at_exit_stops_every_server_left_running(self):
        first, second = self.server(), self.server()
        first.start(limit=5)
        second.start(limit=5)
        dev.stop_all()
        self.assertEqual([p.killed for p in FakeServer.procs], [True, True])
        self.assertEqual(dev._running, set())

    def test_stop_without_waiting_hands_the_kill_to_a_thread_that_exit_waits_for(self):
        server = self.server()
        server.start(limit=5)
        gate = threading.Event()

        def slow_kill(proc):  # Windows 의 taskkill 처럼 오래 걸리는 끊기
            gate.wait(5)
            proc.kill()

        with mock.patch.object(dev, "_kill_tree", slow_kill):
            server.stop(wait=False)  # 끊기를 기다리지 않고 돌아옴
            self.assertNotIn(server, dev._running)
            self.assertFalse(FakeServer.procs[-1].killed)
            gate.set()
            dev.stop_all()  # 프로그램이 끝날 때 맡긴 끊기를 기다림
        self.assertTrue(FakeServer.procs[-1].killed)
        self.assertEqual(dev._stopping, [])


class TestRunTest(FakeBase):
    def run_tests(self):
        return dev.run_tests("/fake/node", self.repo, self.folder)

    def test_runs_vitest_in_the_mission_folder_like_npm_test(self):
        FakeTestRun.report = vitest_report(self.folder)
        result = self.run_tests()
        cmd, options = FakeTestRun.calls[-1]
        self.assertEqual(cmd[:5], ["/fake/node", os.path.join(self.repo, "node_modules", "vitest", "vitest.mjs"), "run", "--reporter=json",
                                   "--reporter=default"])
        self.assertTrue(cmd[5].startswith("--outputFile="))
        self.assertEqual((options["cwd"], options["creationflags"]), (self.folder, study.NO_WINDOW))
        self.assertEqual(len(self.held), 1)
        self.assertEqual(dev._tests, {})
        self.assertEqual((result["total"], result["passed"], result["failed"], result["fails"], result["ok"]), (1, 1, 0, [], True))
        self.assertRegex(dev.summary(result), r"\A내 테스트 1개 가운데 1개 통과 \(\d+\.\d초\)\Z")

    def test_failures_keep_the_first_lines_and_files_that_did_not_run(self):
        FakeTestRun.report = vitest_report(self.folder, fail=True, broken=True)
        result = self.run_tests()
        self.assertEqual((result["total"], result["passed"], result["failed"], result["ok"]), (2, 1, 1, False))
        first, broken = result["fails"]
        self.assertEqual((first["file"], first["name"]), ("src/App.test.tsx", "App > 더하기를 누르면 1"))
        self.assertEqual(first["message"].replace(os.sep, "/"), "AssertionError: expected '0' to be '1'\n    at src/App.test.tsx:12:5")  # 색, 폴더 밖 호출 줄, DOM 덤프는 뺌
        self.assertEqual((broken["file"], broken["name"]), ("src/format.test.ts", ""))
        self.assertIn("돌지 못한 파일 1개", dev.summary(result))
        self.assertTrue(dev.failure_text(first).startswith("src/App.test.tsx > App > 더하기를 누르면 1\nAssertionError"))
        self.assertEqual(dev.failure_text(broken).replace(os.sep, "/"),
                         "src/format.test.ts 파일이 끝까지 돌지 못했습니다\nTransform failed with 1 error:\nsrc/format.ts:3:1: ERROR: Unexpected \"}\"")

    def test_no_test_files_or_none_that_ran(self):
        FakeTestRun.report = {"testResults": []}
        result = self.run_tests()
        self.assertFalse(result["ok"])
        self.assertIn("돌릴 테스트를 찾지 못했습니다", dev.summary(result))
        FakeTestRun.report = vitest_report(self.folder, broken=True)
        FakeTestRun.report["testResults"].pop(0)
        self.assertTrue(dev.summary(self.run_tests()).startswith("내 테스트 파일 1개가 끝까지 돌지 못했습니다 ("))

    def test_an_error_outside_the_tests_fails_the_run_like_npm_test(self):
        FakeTestRun.report, FakeTestRun.code, FakeTestRun.output = vitest_report(self.folder), 1, UNHANDLED_OUTPUT
        result = self.run_tests()
        self.assertEqual((result["total"], result["passed"], result["ok"]), (1, 1, False))
        self.assertRegex(dev.summary(result), r"\A내 테스트 1개 가운데 1개 통과, vitest 오류로 실패 \(")
        text = dev.failure_text(result["fails"][0])
        self.assertTrue(text.startswith("vitest 가 오류로 끝났습니다(종료 코드 1). 테스트가 모두 통과해도 npm test 는 실패로 끝납니다.\n"), text)
        self.assertIn("Unhandled Rejection\nError: boom\n ❯ src/boom.test.ts:3:18\n", text)
        self.assertNotIn("node_modules", text)
        self.assertNotIn(RULE, text)
        self.assertNotIn("Test Files", text)
        FakeTestRun.output = b"Error: Failed to load url ./missing (resolved id: ./missing)\n Test Files  1 passed (1)\nJSON report written to /x\n"
        text = dev.failure_text(self.run_tests()["fails"][0])  # 오류 묶음이 없으면 끝 줄을 보임
        self.assertTrue(text.endswith("Error: Failed to load url ./missing (resolved id: ./missing)\n Test Files  1 passed (1)"), text)
        FakeTestRun.report = {"testResults": []}  # 테스트 파일이 없을 때도 vitest 는 1로 끝남
        result = self.run_tests()
        self.assertEqual(result["fails"], [])
        self.assertIn("돌릴 테스트를 찾지 못했습니다", dev.summary(result))

    def test_ctrl_c_cuts_vitest_in_both_runners(self):
        killed = []

        class Interrupted(object):
            def __init__(self, cmd, **options):
                self.pid = None

            def communicate(self, timeout=None):
                raise KeyboardInterrupt

        for module, call in ((dev, lambda: dev.run_tests("/fake/node", self.repo, self.folder)),
                             (checks, lambda: checks.run("/fake/node", self.repo, "vitest.config.mts", os.path.join(self.tmp, "out.json")))):
            with mock.patch.object(module, "_popen", Interrupted), mock.patch.object(module, "_kill_tree", killed.append):
                with self.assertRaises(KeyboardInterrupt):
                    call()
        self.assertEqual(len(killed), 2)
        self.assertTrue(all(isinstance(proc, Interrupted) for proc in killed))

    def test_missing_report_shows_the_cause_without_outside_frames(self):
        FakeTestRun.output = b"\x1b[31mError: Cannot find package 'jsdom'\x1b[39m\n"
        with self.assertRaises(dev.DevError) as caught:
            self.run_tests()
        self.assertIn("결과 파일이 만들어지지 않았습니다", str(caught.exception))
        self.assertIn("Error: Cannot find package 'jsdom'", str(caught.exception))
        FakeTestRun.output = STARTUP_OUTPUT
        with self.assertRaises(dev.DevError) as caught:
            self.run_tests()
        text = str(caught.exception)
        self.assertIn("\u2718 [ERROR] Expected identifier but found \"{\"\n    vite.config.ts:11:16:", text)
        self.assertIn("Error: Build failed with 1 error:", text)
        self.assertNotIn("node_modules", text)
        self.assertNotIn(RULE, text)

    def test_a_run_over_the_limit_or_a_cancel_cuts_vitest(self):
        HangingRun.procs = []
        with mock.patch.object(dev, "_popen", HangingRun):
            with self.assertRaises(dev.DevError) as caught:
                dev.run_tests("/fake/node", self.repo, self.folder, limit=1)
            self.assertIn("1초 안에 끝나지 않아 멈췄습니다", str(caught.exception))
            self.assertTrue(HangingRun.procs[-1].killed.is_set())
            cancel = threading.Event()
            threading.Timer(0.2, cancel.set).start()  # 화면이 창을 닫으며 취소 신호를 보냄
            started = time.monotonic()
            result = dev.run_tests("/fake/node", self.repo, self.folder, cancel=cancel)
        self.assertIsNone(result)  # 창을 닫는 중이라 보일 결과가 없음
        self.assertLess(time.monotonic() - started, 5)  # 한도(60초)까지 기다리지 않음
        self.assertTrue(HangingRun.procs[-1].killed.is_set())
        self.assertEqual(max(HangingRun.procs[-1].waits[:-1]), dev.WAIT_STEP_S)
        self.assertEqual(dev.TEST_LIMIT_S, checks.LIMIT_S)
        self.assertEqual(dev._tests, {})

    def test_hook_errors_show_the_error_from_the_default_output(self):
        report = vitest_report(self.folder)
        report["testResults"] += [
            {"name": os.path.join(self.folder, "src", "format.test.ts"), "status": "failed", "message": "",
             "assertionResults": [{"ancestorTitles": ["준비 실패"], "title": "가격", "status": "skipped", "failureMessages": []}]},
            {"name": os.path.join(self.folder, "src", "close.test.ts"), "status": "failed",
             "message": "Cannot read properties of undefined (reading 'close')",
             "assertionResults": [{"ancestorTitles": [], "title": "닫기", "status": "passed", "failureMessages": []}]}]
        FakeTestRun.report, FakeTestRun.code, FakeTestRun.output = report, 1, HOOK_OUTPUT
        result = self.run_tests()
        self.assertEqual((result["total"], result["passed"], result["ok"]), (2, 2, False))
        before, after = result["fails"]
        self.assertEqual((before["file"], before["name"]), ("src/format.test.ts", ""))  # beforeAll 이 던지면 테스트는 건너뜀으로 나옴
        self.assertEqual(before["message"], "Error: 준비 단계에서 터짐\n ❯ src/format.test.ts:5:27\n"
                                            "      5|   beforeAll(() => { throw new Error('준비 단계에서 터짐'); });\n"
                                            "       |                           ^")
        self.assertEqual((after["file"], after["name"]), ("src/close.test.ts", ""))  # afterAll 이 던지면 테스트는 통과로 나옴
        self.assertEqual(after["message"], "TypeError: Cannot read properties of undefined (reading 'close')\n ❯ src/close.test.ts:5:26")
        self.assertRegex(dev.summary(result), r"\A내 테스트 2개 가운데 2개 통과, 돌지 못한 파일 2개 \(")
        report["testResults"] = report["testResults"][1:2]  # 준비가 깨진 파일 하나뿐임
        result = self.run_tests()
        self.assertEqual((result["files"], result["total"], len(result["fails"])), (1, 0, 1))
        self.assertIn("준비 단계에서 터짐", result["fails"][0]["message"])
        self.assertRegex(dev.summary(result), r"\A내 테스트 파일 1개가 끝까지 돌지 못했습니다 \(")

    def test_a_test_over_the_vitest_time_limit_says_so(self):
        runner = "\n    at task (file:///repo/node_modules/@vitest/runner/dist/index.js:796:27)"
        report = vitest_report(self.folder)
        report["testResults"].append({"name": os.path.join(self.folder, "src", "format.test.ts"), "status": "failed", "message": "",
                                      "assertionResults": [{"ancestorTitles": ["기다림"], "title": title, "status": "failed",
                                                            "failureMessages": ["Error: STACK_TRACE_ERROR" + runner]}
                                                           for title in ("끝나지 않는 기다림", "또 끝나지 않는 기다림")]})
        FakeTestRun.report, FakeTestRun.code, FakeTestRun.output = report, 1, TIMEOUT_OUTPUT
        result = self.run_tests()
        self.assertEqual((result["total"], result["passed"]), (3, 1))
        for fail in result["fails"]:
            self.assertTrue(fail["message"].startswith("Error: Test timed out in 5000ms.\nIf this is a long-running test"), fail)
            self.assertTrue(fail["message"].endswith(" ❯ src/format.test.ts:8:3"), fail)
        FakeTestRun.output = b""  # 기본 출력에서 찾지 못해도 STACK_TRACE_ERROR 는 보이지 않음
        self.assertEqual(self.run_tests()["fails"][0]["message"], dev.TIMED_OUT_TEXT)

    def test_all_tests_skipped_is_not_a_missing_file(self):
        report = vitest_report(self.folder)
        report["testResults"][0]["assertionResults"].pop(0)  # 남은 테스트는 건너뜀 하나
        FakeTestRun.report = report
        result = self.run_tests()
        self.assertEqual((result["files"], result["total"], result["skipped"], result["ok"]), (1, 0, 1, True))  # npm test 처럼 성공
        self.assertRegex(dev.summary(result), r"\A내 테스트 1개가 모두 skip 이나 todo 로 표시되어 돌린 테스트가 없습니다 \(")
        result["fails"].append({"file": "", "name": "", "code": 1, "message": ""})  # 처리되지 않은 오류로 vitest 는 1로 끝남
        self.assertRegex(dev.summary(result), r"돌린 테스트가 없습니다\. vitest 는 오류로 끝났습니다 \(")


class JobTest(unittest.TestCase):
    def test_windows_puts_each_child_in_one_job_that_ends_with_python(self):
        """작업 개체 하나를 KILL_ON_JOB_CLOSE 로 만들고 자식마다 넣음. kernel32 는 가짜를 씀."""
        calls = []

        def create(attributes, name):
            calls.append(("create", attributes, name))
            return 77

        def set_info(job, kind, limits, size):
            calls.append(("set", job.value, kind, limits._obj.flags, size))
            return 1

        def assign(job, process):
            calls.append(("assign", job.value, process.value))
            return 1

        kernel32 = types.SimpleNamespace(CreateJobObjectW=create, SetInformationJobObject=set_info, AssignProcessToJobObject=assign)
        with mock.patch.object(dev, "_job", []), mock.patch.object(dev, "sys", types.SimpleNamespace(platform="win32")), \
                mock.patch.object(ctypes, "WinDLL", lambda name, use_last_error=False: kernel32, create=True):
            self.assertTrue(dev._hold(types.SimpleNamespace(_handle=501)))
            self.assertTrue(dev._hold(types.SimpleNamespace(_handle=502)))
        size = 144 if ctypes.sizeof(ctypes.c_void_p) == 8 else 112  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION 의 크기
        self.assertEqual(calls, [("create", None, None), ("set", 77, 9, 0x2000, size), ("assign", 77, 501), ("assign", 77, 502)])
        self.assertEqual(create.restype, ctypes.c_void_p)  # 64비트 핸들을 자르지 않음

    def test_a_job_that_cannot_be_set_is_closed_and_tried_again_later(self):
        calls = []
        kernel32 = types.SimpleNamespace(CreateJobObjectW=lambda attributes, name: calls.append("create") or 77,
                                         SetInformationJobObject=lambda *args: calls.append("set") or 0,
                                         CloseHandle=lambda job: calls.append(("close", job.value)))
        with mock.patch.object(dev, "_job", []), mock.patch.object(dev, "sys", types.SimpleNamespace(platform="win32")), \
                mock.patch.object(ctypes, "WinDLL", lambda name, use_last_error=False: kernel32, create=True):
            self.assertFalse(dev._hold(types.SimpleNamespace(_handle=501)))
            self.assertFalse(dev._hold(types.SimpleNamespace(_handle=502)))
        self.assertEqual(calls, ["create", "set", ("close", 77), "create", "set", ("close", 77)])


@unittest.skipUnless(os.name == "nt", "작업 개체는 Windows 에만 있음")
class RealJobTest(unittest.TestCase):
    def test_a_killed_python_takes_the_held_child_with_it(self):
        """작업 관리자로 끝낸 것처럼 atexit 없이 끝난 파이썬(JOB_CHILD)의 자식을 OS 가 끊음. 그 자식(이 테스트에서는 손자)은 진짜 작업 개체에 넣음."""
        tmp = tempfile.mkdtemp(prefix="web_job_")
        self.addCleanup(shutil.rmtree, tmp, True)
        script, log = os.path.join(tmp, "child.py"), os.path.join(tmp, "child.log")
        study.write_text(script, JOB_CHILD)
        with open(log, "wb") as err:
            child = subprocess.Popen([sys.executable, script, ROOT], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err,
                                     creationflags=study.NO_WINDOW)
        self.addCleanup(child.stdout.close)
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        words = child.stdout.readline().split()  # 손자의 pid 와 _hold 의 값
        if len(words) != 2:
            child.wait(10)
            self.fail(study.read_text(log))
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x00100001, False, int(words[0]))  # SYNCHRONIZE | PROCESS_TERMINATE
        self.assertTrue(handle, ctypes.get_last_error())
        handle = ctypes.c_void_p(handle)  # 손자가 끝나도 핸들을 쥐고 있어 그 pid 를 다른 프로세스가 받지 않음
        self.addCleanup(kernel32.CloseHandle, handle)
        self.addCleanup(kernel32.TerminateProcess, handle, 1)  # 남았으면 끊음
        self.assertEqual(words[1], b"True")  # 작업 개체에 넣음
        child.kill()  # TerminateProcess 라 atexit 의 stop_all 이 돌지 않음
        child.wait(10)
        self.assertEqual(kernel32.WaitForSingleObject(handle, 10000), 0)  # WAIT_OBJECT_0. 10초 안에 손자가 끝남


@unittest.skipIf(sys.platform == "win32", "SIGHUP 과 프로세스 그룹은 POSIX 에만 있음. Windows 는 RealJobTest 의 작업 개체가 맡음")
class HangupTest(unittest.TestCase):
    """터미널 창을 닫거나(SIGHUP) 끝내라는 신호(SIGTERM)를 받거나 그냥 끝난 파이썬이, 새 세션에 띄운 서버와 테스트를 남기지 않음."""

    def test_closing_the_terminal_during_web_dev_stops_the_server(self):
        child, pid, _ = start_child(self, "dev")
        child.send_signal(signal.SIGHUP)
        self.assertEqual(child.wait(10), -signal.SIGHUP)  # 자식을 끊은 뒤 같은 신호로 끝남
        self.assertTrue(group_gone(pid))

    def test_sigterm_during_web_test_stops_vitest_and_removes_its_folder(self):
        child, pid, tmp = start_child(self, "test")
        child.send_signal(signal.SIGTERM)
        self.assertEqual(child.wait(10), -signal.SIGTERM)
        self.assertTrue(group_gone(pid))
        self.assertEqual([name for name in os.listdir(tmp) if name.startswith("web_test_")], [])

    def test_a_normal_exit_stops_the_server_at_exit(self):
        child, pid, _ = start_child(self, "exit")
        self.assertEqual(child.wait(10), 0)
        self.assertTrue(group_gone(pid))

    def test_nohup_keeps_ignoring_the_hangup(self):
        """nohup 처럼 SIGHUP 을 무시하게 해서 띄우면 터미널 창을 닫아도 서버와 함께 남음."""
        child, pid, _ = start_child(self, "dev", preexec_fn=lambda: signal.signal(signal.SIGHUP, signal.SIG_IGN))
        child.send_signal(signal.SIGHUP)
        with self.assertRaises(subprocess.TimeoutExpired):
            child.wait(1)
        os.killpg(pid, 0)  # 서버도 돎
        child.send_signal(signal.SIGTERM)  # SIGTERM 에는 서버를 끊고 끝남
        self.assertEqual(child.wait(10), -signal.SIGTERM)
        self.assertTrue(group_gone(pid))


class ServiceTest(Base):
    def setUp(self):
        super().setUp()
        study.write_text(os.path.join(self.repo, dev.VITE_JS), "")
        reset_fakes()
        for name, value in (("_popen", fake_popen), ("_kill_tree", lambda proc: proc.kill()), ("_hold", lambda proc: None)):
            patcher = mock.patch.object(dev, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(dev.stop_all)

    def test_serve_runs_in_the_received_mission_and_one_server_at_a_time(self):
        web = self.session()
        with self.assertRaises(WebError) as caught:
            web.serve("x01")
        self.assertIn("과제를 먼저 받아 주세요", str(caught.exception))
        self.assertIsNone(web.serving())
        web.get("x01")
        self.assertEqual(web.serve("x01"), {"mid": "x01", "url": "http://localhost:5173"})
        first = FakeServer.procs[-1]
        self.assertEqual((first.cmd[0], first.options["cwd"]), ("/fake/node", web.learner_dir("x01")))
        info = web.serving()
        self.assertEqual((info["mid"], info["url"], info["running"]), ("x01", "http://localhost:5173", True))
        web.serve("x01")
        self.assertTrue(first.killed)
        second = FakeServer.procs[-1]
        second.end(1)  # 서버가 스스로 멈춤
        self.assertFalse(web.serving()["running"])
        self.assertIn("VITE v7.3.1", web.server.tail())
        web.stop_serving()
        self.assertIsNone(web.serving())
        self.assertFalse(second.killed)
        self.assertEqual(self.kinds(), ["receive"])  # 화면 띄우기는 기록하지 않음

    def test_serve_and_tests_need_node_and_the_stack(self):
        web = self.session()
        web.get("x01")
        self.node = None
        with self.assertRaises(WebError) as caught:
            web.serve("x01")
        self.assertIn("Node.js 를 찾지 못했습니다", str(caught.exception))
        self.node = {"path": "/fake/node", "version": "22.23.2", "major": 22}
        os.remove(os.path.join(self.repo, stack.VITEST_MJS))
        with self.assertRaises(WebError) as caught:
            web.own_tests("x01")
        self.assertIn("web install", str(caught.exception))
        self.assertEqual((FakeServer.procs, FakeTestRun.calls), ([], []))

    def test_own_tests_run_in_the_mission_folder_without_a_record(self):
        web = self.session()
        web.get("x01")
        FakeTestRun.report = vitest_report(web.learner_dir("x01"), fail=True)
        result = web.own_tests("x01")
        self.assertEqual((result["total"], result["passed"], result["ok"]), (2, 1, False))
        self.assertEqual(FakeTestRun.calls[-1][1]["cwd"], web.learner_dir("x01"))
        self.assertEqual(self.kinds(), ["receive"])


class DevCliTest(CliBase):
    def setUp(self):
        super().setUp()
        study.write_text(os.path.join(self.repo, dev.VITE_JS), "")
        reset_fakes()
        for name, value in (("_popen", fake_popen), ("_kill_tree", lambda proc: proc.kill()), ("_hold", lambda proc: None)):
            patcher = mock.patch.object(dev, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(dev.stop_all)
        for name in ("SIGHUP", "SIGTERM"):  # dev, test 가 거는 처리기를 테스트가 끝나면 되돌림
            if hasattr(signal, name):
                self.addCleanup(signal.signal, getattr(signal, name), signal.getsignal(getattr(signal, name)))

    def test_dev_prints_the_url_and_ctrl_c_stops_the_server(self):
        code, text = self.cmd("dev", "x01")
        self.assertEqual(code, 1)
        self.assertIn("오류: 미션 폴더가 없습니다", text)
        self.cmd("get", "x01")
        with mock.patch.object(cli.time, "sleep", side_effect=KeyboardInterrupt):
            code, text = self.cmd("dev", "x01")
        self.assertEqual(code, 0)
        self.assertIn("화면을 띄웠습니다: http://localhost:5173", text)
        self.assertIn("Ctrl+C", text)
        self.assertTrue(text.endswith("화면을 껐습니다."))
        self.assertTrue(FakeServer.procs[-1].killed)

    def test_dev_reports_a_server_that_stopped_by_itself(self):
        self.cmd("get", "x01")
        FakeServer.lines = VITE_LINES + (b"[vite] server connection lost\n",)
        with mock.patch.object(cli.time, "sleep", lambda secs: FakeServer.procs[-1].end(1)):
            code, text = self.cmd("dev", "x01")
        self.assertEqual(code, 1)
        self.assertIn("화면 서버가 멈췄습니다.", text)
        self.assertIn("server connection lost", text)
        self.assertIn("test", cli.USAGE)

    def test_test_fails_on_an_error_outside_the_tests(self):
        self.cmd("get", "x01")
        folder = os.path.join(self.subs, "alice", "web", "missions", "x01")
        FakeTestRun.report, FakeTestRun.code, FakeTestRun.output = vitest_report(folder), 1, UNHANDLED_OUTPUT
        code, text = self.cmd("test", "x01")
        self.assertEqual(code, 1)
        self.assertIn("vitest 가 오류로 끝났습니다(종료 코드 1)", text)
        self.assertIn("Error: boom", text)

    def test_test_prints_each_failure_and_the_summary(self):
        self.cmd("get", "x01")
        folder = os.path.join(self.subs, "alice", "web", "missions", "x01")
        FakeTestRun.report = vitest_report(folder, fail=True)
        code, text = self.cmd("test", "x01")
        self.assertEqual(code, 1)
        self.assertIn("src/App.test.tsx > App > 더하기를 누르면 1\nAssertionError: expected '0' to be '1'", text)
        self.assertIn("내 테스트 2개 가운데 1개 통과", text.splitlines()[-1])
        FakeTestRun.report = vitest_report(folder)
        code, text = self.cmd("test", "x01")
        self.assertEqual(code, 0)
        self.assertTrue(text.startswith("내 테스트 1개 가운데 1개 통과"))


@unittest.skipUnless(REAL_NODE and HAS_VITE, "저장소 맨 위 node_modules 와 Node 22.12 이상이 있어야 함")
class RealDevTest(unittest.TestCase):
    """고정 은행 x01 의 템플릿을 저장소 안 임시 폴더에 두고 실제 vite 를 띄워 주소를 읽고, 끈 뒤 남은 프로세스가 없는지 봄.
    미션 폴더처럼 저장소 맨 위 node_modules 에서 vite 와 플러그인을 찾도록 저장소 안에 두되, 도중에 멈춰도 git 에 잡히지 않게
    .gitignore 에 있는 .web-check 아래에 둠."""

    def test_vite_serves_the_page_then_stops_and_vitest_runs_the_own_test(self):
        parent = os.path.join(ROOT, checks.CHECK_DIR)
        os.makedirs(parent, exist_ok=True)
        folder = tempfile.mkdtemp(prefix="dev_", dir=parent)
        self.addCleanup(checks.cleanup, ROOT, os.path.basename(folder))
        app = os.path.join(folder, "app")
        shutil.copytree(FIXTURE_APP, app)
        server = dev.DevServer(REAL_NODE["path"], ROOT, app)
        self.addCleanup(server.stop)
        url = server.start()
        self.assertRegex(url, r"\Ahttp://localhost:\d+\Z")
        with urllib.request.urlopen(url, timeout=20) as response:
            self.assertIn('<div id="root">', response.read().decode("utf-8"))
        with urllib.request.urlopen(url + "/src/main.tsx", timeout=60) as response:
            self.assertEqual(response.status, 200)
        pid = server.proc.pid
        server.stop()
        self.assertFalse(server.running)
        if sys.platform != "win32":
            with self.assertRaises(ProcessLookupError):  # vite 와 그 아래 esbuild 까지 프로세스 그룹이 모두 끝남
                os.killpg(pid, 0)
        result = dev.run_tests(REAL_NODE["path"], ROOT, app)
        self.assertEqual((result["total"], result["passed"], result["ok"]), (1, 1, True), result["fails"])
        extra = os.path.join(app, "src", "extra.test.ts")
        study.write_text(extra, "import { test, expect } from 'vitest';\n\n"
                                "test.only('only', () => {\n  expect({ n: 1 }).toMatchSnapshot();\n});\n")
        with mock.patch.dict(os.environ):
            for name in ("CI", "GITHUB_ACTIONS"):  # vitest 는 둘 중 하나만 있어도 CI 로 보고 .only 를 막음
                os.environ.pop(name, None)
            result = dev.run_tests(REAL_NODE["path"], ROOT, app)  # 수강생의 npm test 처럼 .only 를 받고 새 스냅샷을 씀
        self.assertEqual((result["total"], result["passed"], result["ok"]), (2, 2, True), result["fails"])
        self.assertTrue(os.path.isfile(os.path.join(app, "src", "__snapshots__", "extra.test.ts.snap")))
        shutil.rmtree(os.path.join(app, "src", "__snapshots__"))
        study.write_text(extra, "import { beforeAll, describe, test } from 'vitest';\n\ndescribe('준비', () => {\n"
                                "  beforeAll(() => { throw new Error('준비에서 터짐'); });\n  test('a', () => {});\n});\n")
        study.write_text(os.path.join(app, "src", "slow.test.ts"),
                         "import { test } from 'vitest';\n\ntest('끝나지 않음', async () => {\n  await new Promise(() => {});\n}, 300);\n")
        result = dev.run_tests(REAL_NODE["path"], ROOT, app)  # 준비 단계의 오류와 시간 초과는 기본 출력의 문구로 보임
        fails = {fail["file"]: fail for fail in result["fails"]}
        self.assertEqual(fails["src/extra.test.ts"]["name"], "", result["fails"])
        self.assertTrue(fails["src/extra.test.ts"]["message"].startswith("Error: 준비에서 터짐\n ❯ src/extra.test.ts:4:"), result["fails"])
        self.assertEqual(fails["src/slow.test.ts"]["name"], "끝나지 않음")
        self.assertTrue(fails["src/slow.test.ts"]["message"].startswith("Error: Test timed out in 300ms."), result["fails"])
        os.remove(extra)
        os.remove(os.path.join(app, "src", "slow.test.ts"))
        study.write_text(os.path.join(app, "src", "boom.test.ts"),
                         "import { test, expect } from 'vitest';\n\ntest('ok', () => {\n  Promise.reject(new Error('boom'));\n"
                         "  expect(1).toBe(1);\n});\n")
        result = dev.run_tests(REAL_NODE["path"], ROOT, app)  # 처리되지 않은 거부는 npm test 처럼 실패
        self.assertEqual((result["total"], result["passed"], result["ok"]), (2, 2, False))
        self.assertIn("Error: boom", result["fails"][0]["message"])
        self.assertIn("src/boom.test.ts:4:18", result["fails"][0]["message"])


if __name__ == "__main__":
    unittest.main()
