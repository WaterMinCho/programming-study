# -*- coding: utf-8 -*-
"""창 모드 테스트. 진짜 pythonw.exe 로 작은 스크립트를 돌려 결과를 파일로 확인함. Windows 에서만 돌고 그 밖에서는 건너뜀.

pythonw 에는 표준 출력이 없어서 스크립트가 결과를 result.json 으로 남김. 준비 창은 잠깐 떴다가 스스로 닫히고, PyQt6 는 설치하지 않음.
실행: python -m unittest tests.test_windowed
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
TIMEOUT = 120  # 초 단위. 준비 창이 닫히지 않고 멈추면 테스트를 실패로 끝냄

# 스크립트 틀. 인수는 저장소 폴더와 임시 폴더. 본문에서 난 예외도 result.json 에 남김
SCRIPT = '''# -*- coding: utf-8 -*-
import json, os, sys, traceback
root, tmp = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
result = {"stdout_missing": sys.stdout is None and sys.stderr is None}
try:
    import bootstrap, study
    bootstrap.LOG = os.path.join(tmp, "launch.log")
%s
except BaseException:
    result["error"] = traceback.format_exc()
with open(os.path.join(tmp, "result.json"), "w", encoding="utf-8") as f:
    json.dump(result, f)
'''

CONNECT_LOG = '''
result["windowed"] = bootstrap.windowed()
result["log"] = bootstrap.connect_log()
print("print 로 쓴 줄")
sys.stderr.write("stderr.write 로 쓴 줄\\n")
'''

GRADE = '''
bank = study.load_set("s01")
spec = bank["problems"][0]
source = os.path.join(tmp, spec["id"] + ".py")
study.write_text(source, bank["secrets"][spec["id"] + "/solution.py"])
result["executable"] = sys.executable
result["console_python"] = study.console_python()
result["cases"] = len(spec["cases"])
result["graded"] = study.run_problem(spec, source)
'''

# 설치가 필요한 상태로 꾸미고 [설치]를 누른 것처럼 진행시킴. 가상 환경 만들기와 pip 는 한 줄만 출력하는 가짜 명령
SETUP_WINDOW = '''
os.environ["STUDY_VENV"] = os.path.join(tmp, "venv")
bootstrap.PIP_INSTALL = ["-c", "print('FAKE PIP OUTPUT')"]
bootstrap.venv_python = lambda venv: study.console_python()
bootstrap.hand_off = lambda: result.update(handed_off=True)  # tkinter 가 없는 파이썬이면 터미널을 여는 대신 표시만 남김


def fake_call(command, **options):
    """본 화면은 띄우지 않고 띄우려던 명령만 남김."""
    result["command"], result["flags"] = command, options["creationflags"]
    return 0


bootstrap.subprocess.call = fake_call


class Host(bootstrap.WindowHost):
    def python_info(self):
        return {"version": (3, 14), "bits64": True, "platform": "win-amd64", "prefix": sys.prefix}

    def pyqt_error(self):
        return "ModuleNotFoundError: No module named 'PyQt6'"

    def can_venv(self):
        return True

    def open_window(self):
        first = self.window is None
        opened = bootstrap.WindowHost.open_window(self)
        if first and opened:
            self.press_install()
        return opened

    def press_install(self):
        self.window.install.invoke()  # 꺼진 단추는 눌러도 반응하지 않아서 켜질 때까지 되풀이함
        self.window.root.after(100, self.press_install)

    def create_venv(self, path):
        self.stream([study.console_python(), "-c", "print('FAKE VENV OUTPUT')"])

    def call(self, command):
        result["text"] = self.window.text.get("1.0", "end")
        return bootstrap.WindowHost.call(self, command)


host = Host(bootstrap.connect_log())
result["code"] = host.finish(bootstrap.launch([], host))
result["window_closed"] = host.window is None
'''


def script(body):
    return SCRIPT % textwrap.indent(body, "    ")


@unittest.skipUnless(os.name == "nt" and os.path.isfile(PYTHONW), "Windows 의 pythonw.exe 로만 확인함")
class WindowedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="window_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_pythonw(self, body):
        """본문을 pythonw.exe 로 돌리고 result.json 을 읽어 돌려줌. 표준 입출력을 넘기지 않아야 pythonw 에서 None 이 됨."""
        path = os.path.join(self.tmp, "script.pyw")
        with open(path, "w", encoding="utf-8") as f:
            f.write(script(body))
        subprocess.run([PYTHONW, path, ROOT, self.tmp], cwd=self.tmp, timeout=TIMEOUT)
        result_path = os.path.join(self.tmp, "result.json")
        self.assertTrue(os.path.isfile(result_path), "pythonw 스크립트가 결과를 남기지 못함")
        with open(result_path, encoding="utf-8") as f:
            result = json.load(f)
        self.assertNotIn("error", result, result.get("error"))
        self.assertTrue(result["stdout_missing"], "pythonw 인데 표준 출력이 있음")
        return result

    def log(self):
        with open(os.path.join(self.tmp, "launch.log"), encoding="utf-8") as f:
            return f.read()

    def test_missing_streams_are_connected_to_log(self):
        result = self.run_pythonw(CONNECT_LOG)
        self.assertTrue(result["windowed"])
        self.assertEqual(result["log"], os.path.join(self.tmp, "launch.log"))
        self.assertEqual(self.log(), "print 로 쓴 줄\nstderr.write 로 쓴 줄\n")

    def test_runner_grades_under_pythonw(self):
        """창 모드의 본 화면처럼 pythonw 부모에서 문제 은행의 문제 하나를 모범 답안으로 채점함."""
        result = self.run_pythonw(GRADE)
        self.assertEqual(os.path.basename(result["executable"]).lower(), "pythonw.exe")
        self.assertEqual(os.path.basename(result["console_python"]).lower(), "python.exe")
        self.assertTrue(os.path.isfile(result["console_python"]))
        self.assertEqual(result["graded"], [True, result["cases"], ""])

    def test_setup_window_installs_and_closes(self):
        result = self.run_pythonw(SETUP_WINDOW)
        if result.get("handed_off"):
            self.skipTest("이 파이썬에는 tkinter 가 없음")
        self.assertEqual((result["code"], result["window_closed"]), (0, True))
        for part in ("85MB", "FAKE VENV OUTPUT", "FAKE PIP OUTPUT", "설치가 끝났습니다."):
            self.assertIn(part, result["text"])
            self.assertIn(part, self.log())
        self.assertNotIn("터미널 창", result["text"])
        python, start = result["command"]
        self.assertEqual(os.path.basename(python).lower(), "pythonw.exe")  # 본 화면도 콘솔 창 없이 띄움
        self.assertEqual(start, os.path.join(ROOT, "start.pyw"))
        self.assertEqual(result["flags"], subprocess.CREATE_NO_WINDOW)


OLD_START_BAT = "\r\n".join([
    '@echo off',
    'rem Windows: double-click to open the study window. study.py prints every other message.',
    'chcp 65001 >nul',
    'cd /d "%~dp0"',
    'where py >nul 2>nul',
    'if %errorlevel%==0 (',
    '    py -3 study.py',
    ') else (',
    '    python study.py',
    ')',
    'if %errorlevel%==9009 echo Python 을 찾지 못했습니다. https://www.python.org/downloads/latest/python3.14/ 에서 Python 3.14 를 설치한 뒤 다시 실행해 주세요.',
    'if not %errorlevel%==0 pause',
]) + "\r\n"  # 터미널을 같이 열던 예전 start.bat

# study.py·start.pyw 대신 넣는 가짜. 어떤 파일이 어떤 파이썬으로 실행됐는지 ran.txt 에 한 줄씩 남김
FAKE = """import os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "ran.txt"), "a", encoding="utf-8") as f:
    f.write("%s %s %s\\n" % (os.path.basename(__file__), os.path.basename(sys.executable).lower(), os.environ.get("STUDY_CONSOLE", "")))
"""
# 실행 중에 start.bat 을 새 파일로 바꾸는 가짜 study.py. 문제 받기가 프로그램을 갱신하는 경우와 같음
UPDATE = FAKE + """import shutil
shutil.copyfile(os.path.join(here, "new_start.bat"), os.path.join(here, "start.bat"))
"""


@unittest.skipUnless(os.name == "nt", "start.bat 은 Windows 에서만 확인함")
class StartBatTest(unittest.TestCase):
    """start.bat 을 임시 폴더에 복사하고 study.py·start.pyw 를 가짜로 바꿔 cmd 로 실행함."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="start_bat_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        shutil.copyfile(os.path.join(ROOT, "start.bat"), os.path.join(self.tmp, "start.bat"))
        for name in ("study.py", "start.pyw"):
            self.write(name, FAKE)

    def write(self, name, text):
        with open(os.path.join(self.tmp, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def run_bat(self, **env):
        """더블클릭과 같이 cmd /c 로 실행함. 끝난 뒤 cmd 의 오류 출력을 돌려줌."""
        base = {k: v for k, v in os.environ.items() if k != "STUDY_CONSOLE"}
        proc = subprocess.run(["cmd", "/c", os.path.join(self.tmp, "start.bat")], stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=TIMEOUT, env=dict(base, **env))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stderr

    def ran(self, count):
        """가짜 스크립트가 count 줄을 남길 때까지 기다린 뒤 잠깐 더 보고 남은 줄을 모두 돌려줌. start 로 띄운 것은 cmd 가 끝난 뒤에 돌 수 있음."""
        path = os.path.join(self.tmp, "ran.txt")

        def lines():
            if not os.path.isfile(path):
                return []
            with open(path, encoding="utf-8") as f:
                return f.read().splitlines()

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and len(lines()) < count:
            time.sleep(0.2)
        time.sleep(2)
        return lines()

    def test_double_click_hands_off_to_start_pyw_without_console(self):
        self.run_bat()
        self.assertEqual(self.ran(1), ["start.pyw pythonw.exe "])

    def test_console_mode_runs_study_py_in_this_console(self):
        self.run_bat(STUDY_CONSOLE="1")
        self.assertEqual(self.ran(1), ["study.py python.exe 1"])

    def test_old_start_bat_updated_while_running_ends_without_starting_again(self):
        shutil.copyfile(os.path.join(ROOT, "start.bat"), os.path.join(self.tmp, "new_start.bat"))
        with open(os.path.join(self.tmp, "start.bat"), "wb") as f:
            f.write(OLD_START_BAT.encode("utf-8"))
        self.write("study.py", UPDATE)
        self.assertEqual(self.run_bat().strip(), b"")  # 엉뚱한 자리부터 읽으면 '내부 또는 외부 명령이 아닙니다' 같은 오류가 남
        self.assertEqual(self.ran(1), ["study.py python.exe "])

    def test_hand_off_opens_start_bat_in_console_mode(self):
        body = "import sys\nsys.path.insert(0, sys.argv[1])\nimport bootstrap\nbootstrap.ROOT = sys.argv[2]\nbootstrap.hand_off()\n"
        subprocess.run([sys.executable, "-c", body, ROOT, self.tmp], timeout=TIMEOUT, check=True,
                       env=dict(os.environ, STUDY_WINDOW="1"))
        self.assertEqual(self.ran(1), ["study.py python.exe 1"])


if __name__ == "__main__":
    unittest.main()
