# -*- coding: utf-8 -*-
"""실행기 테스트. 실제로 설치하거나 창을 띄우지 않고 결정 로직만 확인함.

프로세스 실행, 가상 환경 생성, 입력 같은 바깥 동작은 FakeHost 가 대신하면서 부른 순서를 기록함.
창 모드의 준비 창은 FakeWindow 가 대신함. 진짜 tkinter 창은 tkinter 와 화면이 있을 때만 띄우고 mainloop 는 돌지 않음.
실행: python -m unittest discover -s tests
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bootstrap  # noqa: E402
import study  # noqa: E402

GOOD = {"version": (3, 14), "bits64": True, "platform": "win-amd64", "prefix": "/usr"}
PIP_NO_WHEEL = ("ERROR: Could not find a version that satisfies the requirement PyQt6 (from versions: none)\n"
                "ERROR: No matching distribution found for PyQt6\n")
PIP_OFFLINE = ("WARNING: Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after "
               "connection broken by 'NameResolutionError(\"HTTPSConnection(host='pypi.org', port=443): "
               "Failed to resolve 'pypi.org'\")': /simple/pyqt6/\n") + PIP_NO_WHEEL


class FakeHost:
    """bootstrap.Host 대역. calls 에 바깥 동작을 부른 순서대로 남김."""

    def __init__(self, pyqt=False, info=None, healthy=False, venv_module=True, tty=True, answer="y",
                 create_error=None, pip=(0, ""), exit_code=0, gui=None):
        self.pyqt, self.info, self.healthy, self.venv_module, self.tty = pyqt, dict(info or GOOD), healthy, venv_module, tty
        self.answer, self.create_error, self.pip, self.exit_code, self.gui = answer, create_error, pip, exit_code, gui
        self.calls, self.said = [], []

    def python_info(self):
        return self.info

    def pyqt_error(self):
        return None if self.pyqt else "ModuleNotFoundError: No module named 'PyQt6'"

    def gui_main(self):
        self.calls.append(("gui",))
        if isinstance(self.gui, Exception):
            raise self.gui
        return lambda: self.gui

    def can_venv(self):
        return self.venv_module

    def isatty(self):
        return self.tty

    def say(self, text):
        self.said.append(text)

    def ask(self, prompt):
        self.calls.append(("ask",))
        self.said.append(prompt)
        return self.answer

    def probe(self, python):
        self.calls.append(("probe", python))
        return self.healthy

    def create_venv(self, path):
        self.calls.append(("create", path))
        if self.create_error:
            raise self.create_error

    def pip_install(self, python):
        self.calls.append(("pip", python))
        return self.pip

    def remove(self, path):
        self.calls.append(("remove", path))

    def call(self, command):
        self.calls.append(("call", list(command)))
        return self.exit_code

    def names(self):
        return [c[0] for c in self.calls]

    def text(self):
        return "\n".join(self.said)


class LaunchCase(unittest.TestCase):
    """실제 홈 폴더의 전용 환경을 건드리지 않게 STUDY_VENV 를 임시 폴더 아래로 돌림.
    진짜 준비 창과 터미널 열기는 부르면 실패하게 막아 둠. 가짜로 바꾸지 못한 경로가 생겨도 사용자 화면에 아무것도 뜨지 않음."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="boot_test_")
        self.venv = os.path.join(os.path.realpath(self.tmp), "venv")
        self.python = bootstrap.venv_python(self.venv)
        patcher = mock.patch.dict(os.environ, {"STUDY_VENV": self.venv})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("STUDY_WINDOW", None)  # 창 모드로 켠 환경에서 테스트를 돌려도 터미널 모드의 흐름을 확인함
        for name in ("SetupWindow", "hand_off"):
            patcher = mock.patch.object(bootstrap, name, side_effect=AssertionError("%s 를 가짜로 바꾸지 않고 부름" % name))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def make_venv(self):
        os.makedirs(self.venv)
        open(os.path.join(self.venv, "pyvenv.cfg"), "w").close()

    def assert_guidance(self, host, code):
        """실패 안내 확인. 0 이 아닌 코드로 끝나고, 다시 시도 방법과 go 를 알리고, 재실행하지 않음."""
        self.assertNotEqual(code, 0)
        self.assertIn("다시 시도", host.text())
        self.assertIn("python study.py go", host.text())
        self.assertNotIn("call", host.names())
        self.assertNotIn("!", host.text())


class PythonCheckTest(unittest.TestCase):
    def problem(self, version, bits64=True, platform="win-amd64"):
        return bootstrap.python_problem({"version": version, "bits64": bits64, "platform": platform, "prefix": ""})

    def test_supported_range(self):
        for version in ((3, 10), (3, 11), (3, 12), (3, 13), (3, 14)):
            self.assertIsNone(self.problem(version), version)
        self.assertIsNone(self.problem((3, 12), platform="macosx-11.0-arm64"))

    def test_too_old_and_too_new(self):
        self.assertIn("3.10 이상", self.problem((3, 9)))
        message = self.problem((3, 15))
        self.assertIn("3.15", message)
        self.assertIn("아직", message)  # 3.15 용 휠이 아직 없다고 알려야 함

    def test_32bit(self):
        self.assertIn("32비트", self.problem((3, 12), bits64=False, platform="win32"))

    def test_windows_arm64_needs_311(self):
        self.assertIn("3.11 이상", self.problem((3, 10), platform="win-arm64"))
        self.assertIsNone(self.problem((3, 11), platform="win-arm64"))


class PathTest(unittest.TestCase):
    def test_default_venv_is_outside_repo(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("STUDY_VENV", None)
            path = bootstrap.venv_dir()
        self.assertEqual(path, os.path.join(os.path.expanduser("~"), ".rokey-study", "venv"))
        self.assertFalse(path.startswith(os.path.join(ROOT, "")))

    def test_env_overrides_venv(self):
        with mock.patch.dict(os.environ, {"STUDY_VENV": os.path.join("~", "elsewhere")}):
            self.assertEqual(bootstrap.venv_dir(), os.path.join(os.path.expanduser("~"), "elsewhere"))

    def test_venv_python_is_inside_venv(self):
        python = bootstrap.venv_python("/x/venv")
        self.assertTrue(python.startswith(os.path.join("/x/venv", "")))
        self.assertIn("python", os.path.basename(python))
        with mock.patch.object(os, "name", "nt"):
            self.assertEqual(bootstrap.venv_python("venv"), os.path.join("venv", "Scripts", "python.exe"))


class LaunchTest(LaunchCase):
    # 바로 실행, 재실행

    def test_pyqt_present_runs_gui_directly(self):
        host = FakeHost(pyqt=True, gui=0)
        self.assertEqual(bootstrap.launch([], host), 0)
        self.assertEqual(host.names(), ["gui"])  # 점검·설치·재실행 없음
        self.assertEqual(host.said, [bootstrap.OPENING])

    def test_gui_exit_code_is_returned(self):
        self.assertEqual(bootstrap.launch([], FakeHost(pyqt=True, gui=3)), 3)
        self.assertEqual(bootstrap.launch([], FakeHost(pyqt=True, gui=None)), 0)

    def test_pyqt_present_wins_over_unsupported_python(self):
        host = FakeHost(pyqt=True, gui=0, info=dict(GOOD, version=(3, 15)))
        self.assertEqual(bootstrap.launch([], host), 0)

    def test_missing_gui_module_is_reported(self):
        host = FakeHost(pyqt=True, gui=ModuleNotFoundError("No module named 'gui'"))
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertIn("gui/app.py", host.text())

    def test_healthy_venv_reruns_study_with_its_python(self):
        self.make_venv()
        host = FakeHost(healthy=True, exit_code=7)
        self.assertEqual(bootstrap.launch([], host), 7)  # 자식의 종료 코드를 그대로 돌려줌
        self.assertEqual(host.calls, [("probe", self.python), ("call", [self.python, bootstrap.STUDY])])
        self.assertEqual(host.said, [bootstrap.OPENING])  # 묻지 않음

    def test_rerun_keeps_arguments(self):
        self.make_venv()
        host = FakeHost(healthy=True)
        bootstrap.launch(["gui"], host)
        self.assertEqual(host.calls[-1], ("call", [self.python, bootstrap.STUDY, "gui"]))

    def test_healthy_venv_wins_over_unsupported_python(self):
        """3.14 로 만든 전용 환경이 있으면 나중에 3.15 로 실행해도 화면이 열림."""
        self.make_venv()
        host = FakeHost(healthy=True, info=dict(GOOD, version=(3, 15)))
        self.assertEqual(bootstrap.launch([], host), 0)
        self.assertEqual(host.names(), ["probe", "call"])

    def test_rerun_side_opens_quietly(self):
        """전용 환경의 파이썬으로 다시 실행된 쪽은 안내를 되풀이하지 않고 화면만 띄움."""
        host = FakeHost(pyqt=True, gui=0, info=dict(GOOD, prefix=self.venv))
        self.assertEqual(bootstrap.launch([], host), 0)
        self.assertEqual((host.names(), host.said), (["gui"], []))

    def test_no_rerun_loop_inside_venv(self):
        """전용 환경의 파이썬으로 돌고 있는데도 PyQt6 가 없으면 다시 실행하지 않음."""
        self.make_venv()
        host = FakeHost(healthy=True, info=dict(GOOD, prefix=self.venv))
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.calls, [])

    # 새로 설치

    def test_consent_creates_installs_then_reruns(self):
        host = FakeHost(answer="y", exit_code=0)
        self.assertEqual(bootstrap.launch([], host), 0)
        self.assertEqual(host.calls, [("ask",), ("create", self.venv), ("pip", self.python),
                                      ("call", [self.python, bootstrap.STUDY])])

    def test_consent_text_says_what_where_and_how_big(self):
        host = FakeHost(answer="n")
        bootstrap.launch([], host)
        text = host.text()
        for part in ("PyQt6", "85MB", "250MB", self.venv, "시스템 파이썬", "저장소"):
            self.assertIn(part, text)

    def test_only_explicit_yes_installs(self):
        def created(answer):
            host = FakeHost(answer=answer)
            bootstrap.launch([], host)
            return "create" in host.names()
        for answer in ("y", "Y", " yes ", "ㅛ", "네"):
            self.assertTrue(created(answer), answer)
        for answer in ("", "n", "no", "아니오", "q"):
            self.assertFalse(created(answer), answer)

    def test_decline_installs_nothing(self):
        host = FakeHost(answer="n")
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.names(), ["ask"])

    def test_pip_command_installs_wheels_only(self):
        self.assertEqual(bootstrap.PIP_INSTALL[:3], ["-m", "pip", "install"])
        self.assertIn("--only-binary=:all:", bootstrap.PIP_INSTALL)
        self.assertEqual(bootstrap.PIP_INSTALL[-1], "PyQt6")

    def test_not_a_terminal_never_installs(self):
        host = FakeHost(tty=False)
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.calls, [])  # 묻지도 만들지도 않음
        self.assertIn("터미널", host.text())

    def test_unsupported_python_never_installs(self):
        for info in (dict(GOOD, version=(3, 15)), dict(GOOD, version=(3, 9)),
                     dict(GOOD, bits64=False, platform="win32"), dict(GOOD, version=(3, 10), platform="win-arm64")):
            host = FakeHost(info=info)
            code = bootstrap.launch([], host)
            self.assert_guidance(host, code)
            self.assertEqual(host.calls, [], info)
            self.assertIn("파이썬 3.14(64비트)를 설치", host.text())
            self.assertIn("python.org", host.text())

    def test_unsupported_python_retry_command_per_os(self):
        for name, command in (("nt", "py -3.14 study.py"), ("posix", "python3.14 study.py")):
            host = FakeHost(info=dict(GOOD, version=(3, 15)))
            with mock.patch.object(os, "name", name):
                bootstrap.launch([], host)
            self.assertIn(command, host.text())

    def test_no_venv_module(self):
        host = FakeHost(venv_module=False)
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.calls, [])
        self.assertIn("python3-venv", host.text())

    def test_venv_creation_failure(self):
        error = subprocess.CalledProcessError(1, ["python", "-m", "ensurepip"])
        host = FakeHost(create_error=error)
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.names(), ["ask", "create"])
        self.assertIn("전용 환경을 준비하지 못했습니다", host.text())

    def test_pip_failure_offline(self):
        host = FakeHost(pip=(1, PIP_OFFLINE))
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.names(), ["ask", "create", "pip"])
        self.assertIn("인터넷", host.text())

    def test_pip_failure_no_wheel(self):
        host = FakeHost(pip=(1, PIP_NO_WHEEL))
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertIn("맞는 PyQt6 설치 파일이 없습니다", host.text())
        self.assertNotIn("인터넷", host.text())

    def test_pip_failure_other(self):
        host = FakeHost(pip=(1, "ERROR: Could not install packages due to an OSError: [Errno 28] No space left on device\n"))
        self.assert_guidance(host, bootstrap.launch([], host))
        self.assertIn("pip 메시지", host.text())

    # 깨진 전용 환경

    def test_broken_venv_is_replaced_after_consent(self):
        self.make_venv()
        host = FakeHost(healthy=False, answer="y")
        self.assertEqual(bootstrap.launch([], host), 0)
        self.assertEqual(host.names(), ["probe", "ask", "remove", "create", "pip", "call"])
        self.assertEqual(host.calls[2], ("remove", self.venv))
        self.assertIn("온전하지 않습니다", host.text())

    def test_broken_venv_is_kept_when_declined(self):
        self.make_venv()
        host = FakeHost(healthy=False, answer="n")
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.names(), ["probe", "ask"])

    def test_broken_venv_without_terminal(self):
        self.make_venv()
        host = FakeHost(healthy=False, tty=False)
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.names(), ["probe"])

    def test_folder_that_is_not_a_venv_is_never_removed(self):
        os.makedirs(self.venv)
        open(os.path.join(self.venv, "내 파일.txt"), "w").close()
        host = FakeHost(answer="y")
        code = bootstrap.launch([], host)
        self.assert_guidance(host, code)
        self.assertEqual(host.calls, [])
        self.assertIn("STUDY_VENV", host.text())

    def test_empty_folder_counts_as_missing(self):
        os.makedirs(self.venv)
        host = FakeHost(answer="y")
        self.assertEqual(bootstrap.launch([], host), 0)
        self.assertEqual(host.names(), ["ask", "create", "pip", "call"])


class HostTest(unittest.TestCase):
    """진짜 Host 중 설치 없이 확인할 수 있는 부분."""

    def test_python_info(self):
        info = bootstrap.Host().python_info()
        self.assertEqual(info["version"], sys.version_info[:2])
        self.assertEqual(set(info), {"version", "bits64", "platform", "prefix"})

    def test_probe_of_missing_python_is_false(self):
        self.assertFalse(bootstrap.Host().probe(os.path.join(tempfile.gettempdir(), "no", "such", "python")))

    def test_probe_matches_this_python(self):
        host = bootstrap.Host()
        code = subprocess.run([sys.executable, "-c", "import PyQt6.QtWidgets"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode
        self.assertEqual(host.probe(sys.executable), code == 0)

    def test_gui_main_returns_entry_point(self):
        app = mock.Mock()
        with mock.patch.dict(sys.modules, {"gui": mock.Mock(app=app), "gui.app": app}):
            self.assertIs(bootstrap.Host().gui_main(), app.main)

    def test_missing_gui_package_is_import_error(self):
        with mock.patch.dict(sys.modules, {"gui": None}):
            with self.assertRaises(ImportError):
                bootstrap.Host().gui_main()

    def test_pip_install_returns_exit_code_and_error_text(self):
        """pip 대신 표준 오류에 한 줄 남기고 실패하는 명령을 돌림."""
        fake_pip = ["-c", "import sys; sys.stderr.write('ERROR: boom\\n'); sys.exit(3)"]
        shown = io.StringIO()
        with mock.patch.object(bootstrap, "PIP_INSTALL", fake_pip), contextlib.redirect_stderr(shown):
            code, log = bootstrap.Host().pip_install(sys.executable)
        self.assertEqual((code, log), (3, "ERROR: boom\n"))
        self.assertEqual(shown.getvalue(), log)  # 오류는 화면에도 똑같이 나옴

    def test_ask_treats_closed_input_and_ctrl_c_as_no_answer(self):
        for error in (EOFError, KeyboardInterrupt):
            with mock.patch("builtins.input", side_effect=error), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bootstrap.Host().ask("? "), "")


class EntryTest(LaunchCase):
    """study.main 은 인수가 없거나 gui 면 화면을, go 면 터미널 모드를 실행함."""

    def run_main(self, argv, host=None, launch_code=0):
        go = mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(study, "cmd_go", go))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if host is None:
                launch = stack.enter_context(mock.patch.object(bootstrap, "launch", return_value=launch_code))
            else:
                launch = None
                stack.enter_context(mock.patch.object(bootstrap, "Host", lambda: host))
            try:
                study.main(argv)
                code = None
            except SystemExit as error:
                code = error.code
        return go, launch, code

    def test_no_argument_and_gui_launch_the_window(self):
        for argv in ([], ["gui"]):
            go, launch, code = self.run_main(argv, launch_code=5)
            launch.assert_called_once_with(argv)
            go.assert_not_called()
            self.assertEqual(code, 5)

    def test_go_is_terminal_mode(self):
        go, launch, code = self.run_main(["go"])
        go.assert_called_once()
        launch.assert_not_called()
        self.assertIsNone(code)

    def test_no_argument_never_grades(self):
        """화면을 띄우든 못 띄우든 인수 없는 실행은 cmd_go(채점)를 부르지 않음."""
        self.make_venv()
        hosts = [
            FakeHost(pyqt=True, gui=0),
            FakeHost(pyqt=True, gui=ModuleNotFoundError("No module named 'gui'")),
            FakeHost(healthy=True, exit_code=0),
            FakeHost(healthy=True, exit_code=134),  # 화면이 죽은 경우
            FakeHost(healthy=False, answer="n"),
            FakeHost(healthy=False, answer="y", pip=(1, PIP_OFFLINE)),
            FakeHost(healthy=False, answer="y", create_error=OSError("디스크가 가득 찼습니다")),
            FakeHost(healthy=False, tty=False),
            FakeHost(healthy=False, venv_module=False),
            FakeHost(healthy=False, info=dict(GOOD, version=(3, 15))),
            FakeHost(healthy=True, info=dict(GOOD, prefix=self.venv)),
        ]
        for index, host in enumerate(hosts):
            go, _, code = self.run_main([], host=host)
            go.assert_not_called()
            self.assertIsNotNone(code, index)

    def test_help_explains_both_modes(self):
        parser = study.build_parser()
        self.assertIn("화면", parser.description)
        self.assertIn("go", parser.description)
        text = parser.format_help()
        self.assertRegex(text, r"gui +\(기본\) 화면")
        self.assertRegex(text, r"go +터미널 모드")


LOADED_SCRIPT = r"""
import json, os, sys
root, tmp, runs = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
sys.path.insert(0, root)
import study
study.SUBMISSIONS_DIR = os.path.join(tmp, "submissions")
study.USER_FILE = os.path.join(tmp, ".study_user")
codes = []
for argv in runs:
    try:
        study.main(argv)
        codes.append(0)
    except SystemExit as error:
        codes.append(error.code or 0)
loaded = sorted(name for name in sys.modules if name.split(".")[0] in ("PyQt6", "gui", "bootstrap"))
sys.stderr.write("RESULT=" + json.dumps({"codes": codes, "loaded": loaded}))
"""


class NoGuiImportTest(unittest.TestCase):
    """CI 에는 PyQt6 가 없어서 터미널 명령과 채점 자식 프로세스는 PyQt6 를 import 하면 안 됨."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="boot_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_study(self, *runs):
        env = dict(os.environ, STUDY_USER="tester", PYTHONIOENCODING="utf-8")
        proc = subprocess.run([sys.executable, "-c", LOADED_SCRIPT, ROOT, self.tmp, json.dumps(list(runs))],
                              capture_output=True, env=env, cwd=self.tmp, stdin=subprocess.DEVNULL)
        err = proc.stderr.decode("utf-8", "replace")
        self.assertIn("RESULT=", err, err)
        result = json.loads(err.rsplit("RESULT=", 1)[1])
        self.assertEqual(result["loaded"], [])
        return result["codes"], proc.stdout.decode("utf-8", "replace")

    def test_go_and_grade(self):
        codes, out = self.run_study(["go"], ["grade", "d1"], ["me"])
        self.assertEqual(codes, [0, 0, 0])
        self.assertIn("진단", out)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "submissions", "tester", "d1", "quiz.py")))

    def test_child_runner(self):
        source = os.path.join(self.tmp, "p01.py")
        job = {"source": source, "mode": "print", "cases": [], "workdir": self.tmp,
               "result": os.path.join(self.tmp, "result.json"), "pid": os.path.join(self.tmp, "pid.txt")}
        job_path = os.path.join(self.tmp, "job.json")
        with open(source, "w", encoding="utf-8") as f:
            f.write("print(1)\n")
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(job, f)
        codes, _ = self.run_study(["_run", job_path])
        self.assertEqual(codes, [0])
        self.assertTrue(os.path.isfile(job["result"]))
        self.assertTrue(study.read_text(job["pid"]).isdigit())

    def test_help(self):
        codes, out = self.run_study(["--help"])
        self.assertEqual(codes, [0])
        self.assertIn("터미널 모드", out)


class FakeWindow:
    """bootstrap.SetupWindow 대역. 누를 단추를 미리 정해 두고, 창에 적힌 글과 부른 순서를 남김."""

    def __init__(self, install=True):
        self.install, self.text, self.calls = install, "", []

    def write(self, text):
        self.text += text

    def update(self):
        pass

    def ask(self):
        self.calls.append("ask")
        return self.install

    def run(self, work):
        self.calls.append("run")
        return work(self.write)

    def wait_close(self):
        self.calls.append("wait_close")

    def close(self):
        self.calls.append("close")


class WindowTestHost(bootstrap.WindowHost):
    """진짜 WindowHost 에서 파이썬 확인과 설치 명령 실행만 FakeHost 로 돌림."""

    def __init__(self, fake, log=None):
        super().__init__(log)
        self.fake = fake

    def python_info(self):
        return self.fake.python_info()

    def pyqt_error(self):
        return self.fake.pyqt_error()

    def gui_main(self):
        return self.fake.gui_main()

    def can_venv(self):
        return self.fake.can_venv()

    def probe(self, python):
        return self.fake.probe(python)

    def remove(self, path):
        self.fake.remove(path)

    def stream(self, command):
        self.fake.calls.append(("stream", list(command)))
        return self.fake.pip if "pip" in command else (0, "")


class WindowLaunchTest(LaunchCase):
    """창 모드 실행. 준비 창, 본 화면 실행(subprocess.call), 예전 실행 파일 열기를 가짜로 바꿈.
    host 를 넘기지 않고 launch 를 불러서 창 모드 분기와 finish 를 구현 그대로 거침."""

    def launch(self, fake, tkinter=True, install=True, log=None):
        """창 모드로 실행해 종료 코드를 돌려줌. tkinter 가 False 면 준비 창을 만들 수 없는 파이썬으로 봄."""
        self.windows = []

        def make_window():
            if not tkinter:
                raise ImportError("No module named '_tkinter'")
            self.windows.append(FakeWindow(install))
            return self.windows[-1]

        host = WindowTestHost(fake, log)
        with mock.patch.dict(os.environ, {"STUDY_WINDOW": "1"}), \
                mock.patch.object(bootstrap, "connect_log", return_value=log), \
                mock.patch.object(bootstrap, "WindowHost", return_value=host) as self.make_host, \
                mock.patch.object(bootstrap, "SetupWindow", make_window), \
                mock.patch.object(bootstrap, "hand_off") as self.hand_off, \
                mock.patch.object(subprocess, "call", return_value=fake.exit_code) as self.call, \
                contextlib.redirect_stdout(io.StringIO()) as self.printed:
            return bootstrap.launch([])

    def test_window_mode_is_env_or_missing_stdout(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("STUDY_WINDOW", None)
            self.assertFalse(bootstrap.windowed())
            with mock.patch.object(sys, "stdout", None):  # pythonw 로 켠 경우
                self.assertTrue(bootstrap.windowed())
            os.environ["STUDY_WINDOW"] = "1"
            self.assertTrue(bootstrap.windowed())

    def test_window_mode_makes_window_host_with_connected_log(self):
        self.assertEqual(self.launch(FakeHost(pyqt=True, gui=4), log="launch.log"), 4)
        self.make_host.assert_called_once_with("launch.log")

    # 바로 실행, 재실행

    def test_pyqt_present_opens_gui_without_setup_window(self):
        fake = FakeHost(pyqt=True, gui=3)
        self.assertEqual(self.launch(fake), 3)
        self.assertEqual((fake.names(), self.windows), (["gui"], []))
        self.assertEqual(self.printed.getvalue(), "")  # 터미널이 없으니 터미널 창을 닫지 말라는 안내도 없음
        self.call.assert_not_called()

    def test_pyqt_present_needs_no_tkinter(self):
        fake = FakeHost(pyqt=True, gui=0)
        self.assertEqual(self.launch(fake, tkinter=False), 0)
        self.assertEqual(fake.names(), ["gui"])
        self.hand_off.assert_not_called()

    def test_healthy_venv_reruns_with_pythonw_in_window_mode(self):
        self.make_venv()
        pythonw = os.path.join(os.path.dirname(self.python), "pythonw.exe")
        os.makedirs(os.path.dirname(pythonw))
        open(pythonw, "w").close()
        fake = FakeHost(healthy=True, exit_code=7)
        self.assertEqual(self.launch(fake), 7)  # 자식의 종료 코드를 그대로 돌려줌
        self.assertEqual((fake.calls, self.windows), ([("probe", self.python)], []))
        (command,), options = self.call.call_args
        self.assertEqual(command, [pythonw, bootstrap.START])  # start.pyw 로 띄워야 자식의 예외도 기록하고 알림
        self.assertEqual(options["env"]["STUDY_WINDOW"], "1")
        self.assertEqual(self.printed.getvalue(), "")

    def test_rerun_keeps_python_when_venv_has_no_pythonw(self):
        self.make_venv()
        self.assertEqual(self.launch(FakeHost(healthy=True)), 0)
        self.assertEqual(self.call.call_args[0][0], [self.python, bootstrap.START])

    # 새로 설치

    def test_install_button_creates_installs_then_reruns(self):
        fake = FakeHost()
        self.assertEqual(self.launch(fake), 0)
        self.assertEqual(fake.calls, [("stream", [study.console_python(), "-m", "venv", self.venv]),
                                      ("stream", [self.python] + bootstrap.PIP_INSTALL)])
        window, = self.windows
        self.assertEqual(window.calls, ["ask", "close"])  # 본 화면을 띄우기 전에 준비 창을 닫음
        for part in ("PyQt6", "85MB", "250MB", self.venv, "시스템 파이썬", "설치가 끝났습니다."):
            self.assertIn(part, window.text)
        self.assertNotIn("터미널 창", window.text)
        self.assertEqual(self.printed.getvalue(), window.text)  # 창에 적은 글은 기록에도 남음
        self.call.assert_called_once()

    def test_close_button_installs_nothing(self):
        fake = FakeHost()
        self.assertEqual(self.launch(fake, install=False), 1)
        self.assertEqual(fake.calls, [])
        window, = self.windows  # 닫은 창을 실패 안내로 다시 띄우지 않음
        self.assertEqual(window.calls, ["ask", "close"])
        self.call.assert_not_called()

    def test_broken_venv_is_replaced_after_install_button(self):
        self.make_venv()
        fake = FakeHost(healthy=False)
        self.assertEqual(self.launch(fake), 0)
        self.assertEqual(fake.names(), ["probe", "remove", "stream", "stream"])
        self.assertIn("온전하지 않습니다", self.windows[0].text)

    # 실패 안내

    def test_failure_stays_in_window_until_closed(self):
        log = os.path.join(self.tmp, "launch.log")
        self.assertEqual(self.launch(FakeHost(pip=(1, PIP_OFFLINE)), log=log), 1)
        window, = self.windows
        self.assertEqual(window.calls, ["ask", "wait_close", "close"])
        for part in ("인터넷", "다시 시도", "python study.py go", log):
            self.assertIn(part, window.text)
        self.call.assert_not_called()

    def test_venv_is_created_with_console_python_and_failure_is_reported(self):
        host = bootstrap.WindowHost()
        folder = os.path.join(self.tmp, "Python314")
        with mock.patch.object(sys, "executable", os.path.join(folder, "pythonw.exe")), \
                mock.patch.object(host, "stream", return_value=(1, "")) as stream:
            with self.assertRaises(subprocess.CalledProcessError):  # launch 가 받아서 안내로 바꿈
                host.create_venv(self.venv)
        stream.assert_called_once_with([os.path.join(folder, "python.exe"), "-m", "venv", self.venv])

    def test_failure_before_consent_opens_window(self):
        self.assertEqual(self.launch(FakeHost(info=dict(GOOD, version=(3, 15)))), 1)
        window, = self.windows
        self.assertEqual(window.calls, ["wait_close", "close"])
        self.assertIn("파이썬 3.14(64비트)를 설치", window.text)
        self.assertNotIn("  기록 ", window.text)  # 기록 파일에 연결하지 않았으면 위치를 알리는 줄이 없음

    def test_child_exit_code_alone_opens_no_window(self):
        """본 화면이 0 이 아닌 코드로 끝나도 안내할 것이 없으면 준비 창을 띄우지 않음."""
        self.assertEqual(self.launch(FakeHost(pyqt=True, gui=1)), 1)
        self.assertEqual(self.windows, [])

    # tkinter 가 없는 파이썬

    def test_without_tkinter_hands_off_to_old_launcher(self):
        fake = FakeHost()
        self.assertEqual(self.launch(fake, tkinter=False), 0)
        self.assertEqual(fake.calls, [])  # 설치는 넘겨받은 터미널 쪽이 물어봄
        self.hand_off.assert_called_once_with()
        self.call.assert_not_called()


class WindowHostTest(unittest.TestCase):
    """창 모드 도우미 가운데 준비 창 없이 확인할 수 있는 부분."""

    FLAGS = 0x1234  # 표식 값. 콘솔 창을 숨기는 진짜 값은 Windows 밖에서 0 이라 넘겼는지 가릴 수 없음

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="boot_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.log = os.path.join(self.tmp, "home", "launch.log")

    def test_missing_streams_are_connected_to_log_file(self):
        os.makedirs(os.path.dirname(self.log))
        study.write_text(self.log, "지난 실행\n")
        with mock.patch.object(bootstrap, "LOG", self.log), mock.patch.object(sys, "stdout", None), \
                mock.patch.object(sys, "stderr", None):
            self.assertEqual(bootstrap.connect_log(), self.log)
            self.addCleanup(sys.stdout.close)
            print("화면에 쓴 줄")
            sys.stderr.write("오류로 쓴 줄\n")  # pythonw 에서 연결하지 않으면 여기서 죽음
        self.assertEqual(study.read_text(self.log), "화면에 쓴 줄\n오류로 쓴 줄\n")  # 실행할 때마다 새로 씀

    def test_only_the_missing_stream_is_connected(self):
        with mock.patch.object(bootstrap, "LOG", self.log), mock.patch.object(sys, "stderr", None):
            stdout = sys.stdout
            self.assertEqual(bootstrap.connect_log(), self.log)
            self.addCleanup(sys.stderr.close)
            self.assertIs(sys.stdout, stdout)
            self.assertEqual(sys.stderr.name, self.log)

    def test_log_falls_back_to_devnull(self):
        blocker = os.path.join(self.tmp, "file")
        open(blocker, "w").close()
        with mock.patch.object(bootstrap, "LOG", os.path.join(blocker, "launch.log")), \
                mock.patch.object(sys, "stdout", None):
            self.assertIsNone(bootstrap.connect_log())
            self.addCleanup(sys.stdout.close)
            self.assertEqual(sys.stdout.name, os.devnull)
            print("버리는 줄")

    def test_existing_streams_are_left_alone(self):
        with mock.patch.object(bootstrap, "LOG", self.log):
            self.assertIsNone(bootstrap.connect_log())
        self.assertFalse(os.path.exists(self.log))

    def test_stream_shows_output_in_window_and_returns_it(self):
        """pip 대신 출력 두 줄을 남기고 실패하는 명령을 돌림."""
        fake_pip = ["-c", "import sys; print('Downloading'); sys.stderr.write('ERROR: boom\\n'); sys.exit(3)"]
        host = bootstrap.WindowHost()
        host.window = FakeWindow()
        with mock.patch.object(bootstrap, "PIP_INSTALL", fake_pip), contextlib.redirect_stdout(io.StringIO()) as logged:
            code, log = host.pip_install(sys.executable)
        self.assertEqual(code, 3)
        self.assertEqual(sorted(log.splitlines()), ["Downloading", "ERROR: boom"])  # 표준 출력과 표준 오류를 함께 모음
        self.assertEqual((host.window.text, logged.getvalue()), (log, log))

    def test_children_are_started_without_console_window(self):
        """창 모드가 띄우는 자식(PyQt6 확인, 설치 명령, 본 화면)에 콘솔 창을 숨기는 값을 넘김."""
        host = bootstrap.WindowHost()
        host.window = FakeWindow()
        with mock.patch.object(bootstrap.WindowHost, "flags", self.FLAGS), mock.patch.object(subprocess, "run") as run, \
                mock.patch.object(subprocess, "Popen") as popen, mock.patch.object(subprocess, "call") as call, \
                contextlib.redirect_stdout(io.StringIO()):
            popen.return_value.__enter__.return_value.stdout = []
            python = os.path.join(self.tmp, "python")
            host.probe(python)
            host.stream([python, "-m", "venv", "venv"])
            host.call([python, bootstrap.STUDY, "gui"])
        for child in (run, popen, call):
            self.assertEqual(child.call_args[1]["creationflags"], self.FLAGS, child)
        self.assertEqual(call.call_args[0][0], [python, bootstrap.START, "gui"])

    def test_console_is_hidden_only_in_window_mode(self):
        self.assertEqual(bootstrap.Host.flags, 0)
        self.assertEqual(bootstrap.WindowHost.flags, 0x08000000 if os.name == "nt" else 0)  # CREATE_NO_WINDOW

    def test_remove_deletes_folder_through_window(self):
        folder = os.path.join(self.tmp, "venv")
        os.makedirs(os.path.join(folder, "Lib"))
        host = bootstrap.WindowHost()
        host.window = FakeWindow()
        host.remove(folder)
        self.assertFalse(os.path.exists(folder))
        self.assertEqual(host.window.calls, ["run"])  # 창이 멈추지 않게 준비 창의 작업 스레드로 지움
        with self.assertRaises(OSError):  # launch 가 받아서 안내로 바꿈
            host.remove(folder)

    def test_hand_off_opens_old_launcher_in_terminal_mode(self):
        for name in ("nt", "posix"):
            with mock.patch.dict(os.environ, {"STUDY_WINDOW": "1"}), mock.patch.object(os, "name", name), \
                    mock.patch.object(os, "startfile", create=True) as startfile, \
                    mock.patch.object(subprocess, "call") as call:
                bootstrap.hand_off()
                self.assertNotIn("STUDY_WINDOW", os.environ)  # 넘겨받은 쪽까지 창 모드면 끝없이 되풀이됨
            opened = startfile.call_args_list + call.call_args_list
            expected = mock.call(os.path.join(ROOT, "start.bat")) if name == "nt" else \
                mock.call(["open", os.path.join(ROOT, "start.command")])
            self.assertEqual(opened, [expected])

    def test_real_window_host_cannot_open_window_without_tkinter(self):
        with mock.patch.dict(sys.modules, {"tkinter": None}):
            host = bootstrap.WindowHost()
            self.assertFalse(host.isatty())
            self.assertIsNone(host.window)


class ConsolePythonTest(unittest.TestCase):
    def test_pythonw_is_swapped_for_python_next_to_it(self):
        for name in ("pythonw.exe", "PythonW.EXE"):
            with mock.patch.object(sys, "executable", os.path.join("venv", "Scripts", name)):
                self.assertEqual(study.console_python(), os.path.join("venv", "Scripts", "python.exe"))

    def test_console_python_is_kept(self):
        self.assertEqual(study.console_python(), sys.executable)
        with mock.patch.object(sys, "executable", os.path.join("venv", "Scripts", "python.exe")):
            self.assertEqual(study.console_python(), sys.executable)

    def test_runner_uses_console_python(self):
        """창 모드(pythonw)에서도 채점 러너는 python.exe 로 띄움."""
        with tempfile.TemporaryDirectory(prefix="boot_test_") as tmp, \
                mock.patch.object(study, "console_python", return_value=sys.executable) as console_python:
            source = os.path.join(tmp, "p01.py")
            study.write_text(source, "print(1)\n")
            study.run_cases({"mode": "print", "cases": []}, source)
        console_python.assert_called_once_with()


def load_start():
    """start.pyw 는 확장자가 .py 가 아니라서 경로로 불러옴."""
    loader = importlib.machinery.SourceFileLoader("start_pyw", os.path.join(ROOT, "start.pyw"))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


class StartFileTest(unittest.TestCase):
    """start.pyw 는 study.main 을 창 모드로 부르고, 예외로 끝나면 기록한 뒤 알림. 알림 창은 가짜로 바꿈."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="boot_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(os.chdir, os.getcwd())
        self.addCleanup(sys.path.__setitem__, slice(None), list(sys.path))
        self.start = load_start()
        self.log = os.path.join(self.tmp, "home", "launch.log")

    def run_start(self, main):
        """study.main 을 main 으로 바꿔 start.pyw 를 돌리고 (종료 코드, 가짜 알림)을 돌려줌.
        더블클릭하면 어느 폴더에서 실행될지 모르므로 다른 폴더에서, 저장소가 sys.path 에 없는 상태로 시작함."""
        with mock.patch.object(study, "main", main), mock.patch.object(self.start, "LOG", self.log), \
                mock.patch.object(self.start, "alert") as alert, mock.patch.dict(os.environ):
            os.environ.pop("STUDY_WINDOW", None)
            os.chdir(self.tmp)
            sys.path[:] = [path for path in sys.path if path != ROOT]
            try:
                self.start.main()
                code = None
            except SystemExit as error:
                code = error.code
            self.window_mode = os.environ.get("STUDY_WINDOW")
        return code, alert

    def test_runs_study_in_window_mode_from_its_folder(self):
        main = mock.Mock(side_effect=SystemExit(5))  # study.main 은 sys.exit 로 끝남
        code, alert = self.run_start(main)
        self.assertEqual(code, 5)
        main.assert_called_once_with([])
        self.assertEqual(self.window_mode, "1")
        self.assertTrue(bootstrap.same_path(os.getcwd(), ROOT))
        self.assertEqual(sys.path[0], ROOT)
        alert.assert_not_called()
        self.assertFalse(os.path.exists(self.log))

    def test_exception_is_recorded_and_alerted(self):
        code, alert = self.run_start(mock.Mock(side_effect=RuntimeError("받아 온 코드의 오류")))
        self.assertEqual(code, 1)
        recorded = study.read_text(self.log)
        self.assertIn("Traceback", recorded)
        self.assertIn("RuntimeError: 받아 온 코드의 오류", recorded)
        (text,), _ = alert.call_args
        for part in ("start.bat", "start.command", "python study.py update", self.log):
            self.assertIn(part, text)

    def test_import_failure_is_recorded_and_alerted(self):
        with mock.patch.dict(sys.modules, {"study": None}):
            code, alert = self.run_start(mock.Mock())
        self.assertEqual(code, 1)
        self.assertIn("import study", study.read_text(self.log))
        alert.assert_called_once()

    def test_alert_is_shown_even_if_log_cannot_be_written(self):
        blocker = os.path.join(self.tmp, "file")
        open(blocker, "w").close()
        self.log = os.path.join(blocker, "launch.log")
        code, alert = self.run_start(mock.Mock(side_effect=RuntimeError("받아 온 코드의 오류")))
        self.assertEqual(code, 1)
        alert.assert_called_once()

    def test_record_appends_to_existing_log(self):
        with mock.patch.object(self.start, "LOG", self.log):
            self.start.record("첫 오류")
            self.start.record("둘째 오류")
        recorded = study.read_text(self.log)
        self.assertLess(recorded.index("첫 오류"), recorded.index("둘째 오류"))

    def test_alert_uses_the_dialog_of_each_os(self):
        """두 운영체제의 알림을 함께 가짜로 바꿔 둠. 분기가 어긋나도 진짜 알림 창이 뜨지 않고 실패로 끝남."""
        import ctypes
        script = ["-e", "on run argv", "-e", "display alert (item 1 of argv) message (item 2 of argv)", "-e", "end run"]
        for name, platform in (("nt", "win32"), ("posix", "darwin")):
            with mock.patch.object(os, "name", name), mock.patch.object(sys, "platform", platform), \
                    mock.patch.object(ctypes, "windll", create=True) as windll, \
                    mock.patch.object(subprocess, "call") as call:
                self.start.alert("안내")
            box = windll.user32.MessageBoxW
            if name == "nt":
                box.assert_called_once_with(None, "안내", self.start.TITLE, 0x10)
                call.assert_not_called()
            else:
                call.assert_called_once_with(["osascript"] + script + [self.start.TITLE, "안내"])
                box.assert_not_called()

    def test_first_line_names_registered_python(self):
        """py 실행기는 `/usr/bin/env python3` 이면 PATH 의 python3.exe(콘솔용)를 먼저 찾아서 검은 창이 뜸."""
        with open(os.path.join(ROOT, "start.pyw"), "rb") as f:
            self.assertEqual(f.readline().rstrip(), b"#!/usr/bin/python3")


class MacAppTest(unittest.TestCase):
    """ROKEY.app 은 열지 않음. 꾸러미에 든 파일을 확인하고, 실행 스크립트는 임시 폴더에 옮겨 가짜 python3 와 osascript 로 돌려 봄."""

    CONTENTS = os.path.join(ROOT, "ROKEY.app", "Contents")

    def test_launcher_script_is_executable_and_has_unix_line_endings(self):
        path = os.path.join(self.CONTENTS, "MacOS", "ROKEY")
        with open(path, "rb") as f:
            script = f.read()
        self.assertTrue(script.startswith(b"#!/bin/zsh -l\n"))
        self.assertNotIn(b"\r", script)  # 줄 끝이 CRLF 면 zsh 가 첫 줄부터 실행하지 못함
        self.assertIn(b"exec python3 start.pyw", script)
        if os.name != "nt":  # Windows 의 파일에는 실행 권한이 없음
            self.assertTrue(os.access(path, os.X_OK))

    def run_script(self, start=None, python=sys.executable):
        """스크립트를 임시 저장소 폴더로 옮겨 zsh 로 돌리고 (종료 코드, 알림 인수)를 돌려줌.
        start 는 그 폴더에 둘 start.pyw 의 내용, python 은 python3 라는 이름으로 실행될 프로그램.
        PATH 에는 가짜 python3, osascript, dirname 만 둬서 어느 분기로 가도 진짜 알림 창이 뜨지 않음.
        zsh 는 -f 로 띄워 사용자 설정 파일이 PATH 를 바꾸지 못하게 함."""
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="boot_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo, fake_bin = os.path.join(self.tmp, "repo"), os.path.join(self.tmp, "bin")
        script = os.path.join(self.repo, "ROKEY.app", "Contents", "MacOS", "ROKEY")
        os.makedirs(os.path.dirname(script))
        shutil.copy(os.path.join(self.CONTENTS, "MacOS", "ROKEY"), script)
        alert = os.path.join(self.tmp, "alert.txt")
        for name, line in (("python3", 'exec "%s" "$@"' % python), ("dirname", 'exec /usr/bin/dirname "$@"'),
                           ("osascript", 'printf "%%s\\n" "$@" > "%s"' % alert)):
            study.write_text(os.path.join(fake_bin, name), "#!/bin/sh\n%s\n" % line)
            os.chmod(os.path.join(fake_bin, name), 0o755)
        if start is not None:
            study.write_text(os.path.join(self.repo, "start.pyw"), start)
        code = subprocess.run(["/bin/zsh", "-f", script], env={"PATH": fake_bin}, cwd=self.tmp, stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60).returncode
        return code, study.read_text(alert) if os.path.exists(alert) else None

    @unittest.skipUnless(sys.platform == "darwin", "macOS 의 zsh 로만 돌려 봄")
    def test_launcher_script_runs_start_pyw_in_repo_folder(self):
        start = ("import json, os, sys\n"
                 "with open('result.json', 'w') as f:\n"
                 "    json.dump([os.getcwd(), os.environ.get('STUDY_WINDOW'), sys.argv], f)\n"
                 "sys.exit(7)\n")
        self.assertEqual(self.run_script(start), (7, None))  # 알림 없이 start.pyw 의 종료 코드로 끝남
        folder, window_mode, argv = json.loads(study.read_text(os.path.join(self.repo, "result.json")))
        self.assertEqual((folder, window_mode, argv), (self.repo, "1", ["start.pyw"]))

    @unittest.skipUnless(sys.platform == "darwin", "macOS 의 zsh 로만 돌려 봄")
    def test_launcher_script_alerts_when_it_cannot_start(self):
        """격리돼 다른 경로에서 실행된 앱처럼 옆에 start.pyw 가 없거나, python3 가 실행되지 않는 경우."""
        for options in ({}, {"start": "", "python": "/usr/bin/false"}):
            code, alert = self.run_script(**options)
            self.assertEqual(code, 1, options)
            self.assertIn("start.command", alert)

    def test_info_plist_points_at_script_and_icon(self):
        with open(os.path.join(self.CONTENTS, "Info.plist"), "rb") as f:
            info = plistlib.load(f)
        self.assertEqual((info["CFBundleName"], info["CFBundlePackageType"]), ("ROKEY 파이썬 스터디", "APPL"))
        self.assertTrue(os.path.isfile(os.path.join(self.CONTENTS, "MacOS", info["CFBundleExecutable"])))
        self.assertTrue(os.path.isfile(os.path.join(self.CONTENTS, "Resources", info["CFBundleIconFile"] + ".icns")))


def has_screen():
    """tkinter 창을 띄울 수 있는 환경인가. Homebrew 파이썬에는 _tkinter 가 없고 리눅스 CI 에는 화면이 없음."""
    if importlib.util.find_spec("_tkinter") is None:
        return False
    return sys.platform in ("win32", "darwin") or bool(os.environ.get("DISPLAY"))


@unittest.skipUnless(has_screen(), "tkinter 와 화면이 있을 때만 준비 창을 띄워 봄")
class SetupWindowTest(unittest.TestCase):
    """진짜 준비 창. mainloop 를 돌지 않고 update 로 한 걸음씩 넘기면서 단추를 직접 누름."""

    def setUp(self):
        self.window = bootstrap.SetupWindow()
        self.addCleanup(self.window.close)
        self.released = []
        release = self.window.release
        self.window.release = lambda: (self.released.append(True), release())

    def step_until_released(self):
        """mainloop 대신 씀. 작업 스레드가 끝나 release 가 불릴 때까지 창을 한 걸음씩 돌림."""
        deadline = time.monotonic() + 10
        while not self.released:
            self.assertLess(time.monotonic(), deadline)
            self.window.update()
            time.sleep(0.01)

    def shown(self):
        return self.window.text.get("1.0", "end-1c")

    def test_title_and_read_only_text(self):
        self.assertEqual(str(self.window.text.cget("state")), "disabled")
        self.window.write("안내 한 줄\n")
        self.window.update()
        self.assertEqual(self.window.root.title(), "ROKEY 파이썬 스터디 준비")
        self.assertEqual(self.shown(), "안내 한 줄\n")
        self.assertEqual(str(self.window.text.cget("state")), "disabled")

    def test_buttons_are_off_until_asked(self):
        self.window.install.invoke()
        self.window.cancel.invoke()
        self.assertEqual(self.released, [])

    def test_ask_returns_the_pressed_button(self):
        for button, answer in ((self.window.install, True), (self.window.cancel, False)):
            self.window.wait = button.invoke  # mainloop 대신 단추를 누름
            self.assertIs(self.window.ask(), answer)
            self.assertTrue(self.window.install.instate(["disabled"]))  # 답을 받으면 단추를 끔
            self.assertTrue(self.window.cancel.instate(["disabled"]))

    def test_run_shows_worker_output_and_returns_result(self):
        self.window.wait = self.step_until_released
        threads, bar = [], []
        for name in ("start", "stop"):
            real = getattr(self.window.bar, name)
            setattr(self.window.bar, name, lambda name=name, real=real: (bar.append(name), real()))

        def work(emit):
            threads.append(threading.get_ident())
            emit("첫 줄\n")
            emit("둘째 줄\n")
            return 7

        self.assertEqual(self.window.run(work), 7)
        self.assertEqual(self.shown(), "첫 줄\n둘째 줄\n")
        self.assertNotEqual(threads, [threading.get_ident()])  # 창을 만든 스레드에서 돌리면 그동안 창이 멈춤
        self.assertEqual(bar, ["start", "stop"])

    def test_run_raises_worker_error_again(self):
        self.window.wait = self.step_until_released

        def work(emit):
            raise OSError("파이썬이 없음")

        with self.assertRaises(OSError):
            self.window.run(work)

    def test_x_of_window_closes_only_while_close_button_is_on(self):
        press_x = self.window.root.protocol("WM_DELETE_WINDOW")  # 창의 X 에 걸린 Tcl 명령
        self.window.root.tk.call(press_x)
        self.assertEqual(self.released, [])  # 설치 중에는 [닫기]가 꺼져 있어서 X 를 눌러도 닫히지 않음
        self.window.wait = lambda: None
        self.window.wait_close()
        self.window.root.tk.call(press_x)
        self.assertEqual(self.released, [True])

    def test_wait_close_leaves_only_close_button(self):
        self.window.wait = lambda: None
        self.window.wait_close()
        self.assertTrue(self.window.install.instate(["disabled"]))
        self.assertTrue(self.window.cancel.instate(["!disabled"]))
        self.window.cancel.invoke()
        self.assertEqual(self.released, [True])


if __name__ == "__main__":
    unittest.main()
