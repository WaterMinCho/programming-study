#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`python study.py` 로 화면을 띄우기 전에 PyQt6 를 준비함.

지금 파이썬에 PyQt6 가 있으면(수업에서 이미 설치한 경우) 바로 화면을 띄움. 없으면 전용 가상 환경(~/.rokey-study/venv,
환경 변수 STUDY_VENV 로 바꿀 수 있음)의 파이썬으로 study.py 를 다시 실행함. 전용 환경이 없거나 깨졌으면 터미널에서 동의를 받아
새로 만들고 PyQt6 를 설치한 뒤 다시 실행함. 파이썬이 3.10~3.14 64비트가 아니면 PyQt6 를 설치할 수 없어서 안내만 함.

막히면 원인과 선택지를 알리고 0 이 아닌 코드로 끝냄. 터미널 모드(go)는 실행하자마자 채점해서
화면에서 풀다 만 답이 첫 시도로 기록되므로 go 로 넘기지 않음.

start.pyw 나 ROKEY.app 으로 켜면 터미널이 없는 창 모드로 돎. 흐름은 같고 안내, 동의, 진행 표시를 준비 창에 띄움.

표준 라이브러리만 씀. PyQt6 는 Host.pyqt_error 와 Host.gui_main 안에서만, tkinter 는 SetupWindow 안에서만 import 함.
"""
import importlib.util
import os
import queue
import re
import shutil
import subprocess
import sys
import sysconfig
import threading

import study

ROOT = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.join(ROOT, "study.py")
START = os.path.join(ROOT, "start.pyw")  # 창 모드의 실행 파일. 예외로 끝나면 기록하고 알림 창을 띄움
MIN_VERSION, MAX_VERSION = (3, 10), (3, 14)  # PyQt6 휠이 나와 있는 파이썬 범위. 3.15 용은 아직 없음(2026-10)
PROBE_TIMEOUT = 60  # 초 단위. 설치 직후 첫 import 는 백신 검사로 느릴 수 있어 넉넉히 잡음
# 소스 빌드로 빠지면 한참 뒤에 알아보기 어려운 오류로 끝나서 휠만 받음
PIP_INSTALL = ["-m", "pip", "install", "--disable-pip-version-check", "--only-binary=:all:", "PyQt6"]
PYTHON_URL = "https://www.python.org/downloads/latest/python3.14/"  # python.org 첫 화면의 단추는 최신판(곧 3.15)을 줌
RETRY = "python study.py"
UPDATE_RETRY = "python study.py update 로 새 버전을 받은 뒤 python study.py"
OPENING = "화면을 엽니다. 쓰는 동안 이 터미널 창은 닫지 말아 주세요(닫으면 화면도 함께 닫힙니다)."
YES = ("y", "yes", "ㅛ", "예", "네")  # ㅛ: 한글 입력 상태에서 y 를 누른 경우
LOG = os.path.join(os.path.expanduser("~"), ".rokey-study", "launch.log")  # 창 모드에서 터미널 대신 출력을 받는 파일
WINDOW_TITLE = "프로그래밍 스터디 준비"
POLL = 50  # 준비 창이 작업 스레드의 출력을 확인하는 간격(밀리초)


class Host:
    """입력·출력·프로세스 실행·설치처럼 실행기가 바깥에 하는 일을 모아 둠. 테스트는 이 클래스를 가짜로 바꿈."""

    flags = 0  # 자식 프로세스에 주는 creationflags. 창 모드는 콘솔 창을 숨기는 값으로 바꿈

    def python_info(self):
        return {"version": sys.version_info[:2], "bits64": sys.maxsize > 2 ** 32,
                "platform": sysconfig.get_platform(), "prefix": sys.prefix}

    def pyqt_error(self):
        """지금 파이썬에서 PyQt6 를 못 쓰는 이유. 쓸 수 있으면 None."""
        try:
            import PyQt6.QtWidgets  # noqa: F401
        except Exception as error:  # sip 버전이 안 맞으면 ImportError 가 아닌 예외가 남
            return "%s: %s" % (type(error).__name__, error)
        return None

    def gui_main(self):
        import gui.app
        return gui.app.main

    def can_venv(self):
        """Ubuntu·Debian 은 venv·ensurepip 가 별도 패키지(python3-venv)라 없을 수 있음."""
        return all(importlib.util.find_spec(name) for name in ("venv", "ensurepip"))

    def isatty(self):
        return bool(sys.stdin) and sys.stdin.isatty()

    def say(self, text):
        print(text, flush=True)

    def ask(self, prompt):
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):  # 입력이 닫혔거나 Ctrl+C 를 누르면 거절로 봄
            print()
            return ""

    def probe(self, python):
        """그 파이썬으로 PyQt6 를 불러올 수 있는지 별도 프로세스에서 확인함."""
        try:
            return subprocess.run([python, "-c", "import PyQt6.QtWidgets"], timeout=PROBE_TIMEOUT,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, creationflags=self.flags).returncode == 0
        except (OSError, subprocess.TimeoutExpired):  # 기반 파이썬이 지워졌거나 응답이 없음
            return False

    def create_venv(self, path):
        import venv
        venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(path)  # `python -m venv` 의 기본값과 같게

    def pip_install(self, python):
        """PyQt6 를 설치하고 (종료 코드, 오류 글)을 돌려줌. 진행 표시는 화면에 바로 나가고, 표준 오류는 보여 주면서 모아 둠."""
        lines = []
        with subprocess.Popen([python] + PIP_INSTALL, stderr=subprocess.PIPE, text=True, errors="replace") as proc:
            for line in proc.stderr:
                print(line, end="", file=sys.stderr, flush=True)
                lines.append(line)
        return proc.returncode, "".join(lines)

    def remove(self, path):
        shutil.rmtree(path)

    def call(self, command):
        """os.execv 는 Windows 에서 부모가 먼저 끝나 콘솔과 종료 코드를 잃어서 쓰지 않음."""
        return subprocess.call(command)


class SetupWindow:
    """설치 동의, 진행 표시, 실패 안내를 띄우는 준비 창. 이 창이 필요할 때는 PyQt6 가 없어서 tkinter 로 그림."""

    def __init__(self):
        import tkinter  # Homebrew 파이썬처럼 tkinter 가 빠진 파이썬이 있어서 창을 만들 때 불러옴
        from tkinter import ttk
        self.inbox = queue.Queue()  # 작업 스레드가 낸 글. tkinter 는 창을 만든 스레드에서만 건드릴 수 있음
        self.answer = False
        self.root = tkinter.Tk()
        self.root.title(WINDOW_TITLE)
        self.text = tkinter.Text(self.root, width=88, height=20, wrap="char", state="disabled", font="TkFixedFont")
        self.text.pack(fill="both", expand=True, padx=12, pady=(12, 8))
        self.bar = ttk.Progressbar(self.root, mode="indeterminate")
        self.bar.pack(fill="x", padx=12)
        buttons = ttk.Frame(self.root)
        buttons.pack(anchor="e", padx=12, pady=12)
        self.install = ttk.Button(buttons, text="설치", command=lambda: self.press(True))
        self.cancel = ttk.Button(buttons, text="닫기", command=lambda: self.press(False))
        self.install.pack(side="left")
        self.cancel.pack(side="left", padx=(8, 0))
        self.root.protocol("WM_DELETE_WINDOW", self.cancel.invoke)  # 꺼진 단추의 invoke 는 아무 일도 하지 않아서 설치 중에는 닫히지 않음
        self.enable()

    def enable(self, *buttons):
        """넘긴 단추만 켜고 나머지는 끔."""
        for button in (self.install, self.cancel):
            button.state(["!disabled" if button in buttons else "disabled"])

    def write(self, text):
        self.text.configure(state="normal")
        self.text.insert("end", text)
        self.text.configure(state="disabled")
        self.text.see("end")

    def update(self):
        """적은 글이 바로 보이게 창을 한 번 그림."""
        self.root.update()

    def wait(self):
        """release 가 불릴 때까지 창을 돌림."""
        self.root.mainloop()

    def release(self):
        self.root.quit()

    def press(self, answer):
        self.answer = answer
        self.release()

    def ask(self):
        """[설치]나 [닫기]를 누를 때까지 기다림. [설치]를 눌렀으면 True."""
        self.enable(self.install, self.cancel)
        self.wait()
        self.enable()
        return self.answer

    def wait_close(self):
        """[닫기]를 누를 때까지 창을 그대로 둠."""
        self.enable(self.cancel)
        self.wait()

    def run(self, work):
        """work(emit) 를 스레드에서 돌리고 끝날 때까지 진행 표시를 움직인 뒤 work 의 결과를 돌려줌. emit 에 넘긴 글은 글 칸에 붙음.
        오래 걸리는 일을 창을 만든 스레드에서 하면 창이 멈춘 것처럼 보임."""
        outcome = {}

        def target():
            try:
                outcome["value"] = work(self.inbox.put)
            except Exception as error:  # 스레드에서 난 예외는 부른 쪽에서 다시 던짐
                outcome["error"] = error

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        self.bar.start()
        self.root.after(POLL, self.pump, thread)
        self.wait()
        self.bar.stop()
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    def pump(self, thread):
        """작업 스레드가 낸 글을 글 칸으로 옮기고, 스레드가 끝났으면 기다림을 풂."""
        alive = thread.is_alive()  # 글을 옮기기 전에 확인해야 끝나기 직전에 낸 글을 놓치지 않음
        try:
            while True:
                self.write(self.inbox.get_nowait())
        except queue.Empty:
            pass
        if alive:
            self.root.after(POLL, self.pump, thread)
        else:
            self.release()

    def close(self):
        self.root.destroy()


class WindowHost(Host):
    """창 모드의 Host. 터미널에 내보내던 안내, 동의, 진행 표시를 준비 창으로 옮기고 자식 프로세스의 콘솔 창을 숨김."""

    flags = study.NO_WINDOW

    def __init__(self, log=None):
        self.log = log  # 출력을 받는 기록 파일. 연결하지 않았으면 None
        self.lines = []  # 사용자가 아직 확인하지 않은 안내. 본 화면을 띄우면 비움
        self.window = None  # 준비 창. 설치 동의나 실패 안내가 필요할 때 만듦
        self.dismissed = False  # 설치 동의에서 [닫기]를 눌렀는가

    def open_window(self):
        """준비 창을 띄우고 그동안의 안내를 옮겨 적음. 띄우지 못하면 False."""
        if self.window is None:
            try:
                self.window = SetupWindow()
            except Exception:  # tkinter 가 없으면 ImportError, 화면을 못 열면 TclError
                return False
            self.window.write("".join(line + "\n" for line in self.lines))
        return True

    def close_window(self):
        if self.window is not None:
            self.window.close()
            self.window = None

    def isatty(self):
        """설치 동의를 받을 수 있는가. 창 모드는 준비 창의 단추로 받음."""
        return self.open_window()

    def say(self, text):
        text = text.replace(OPENING, "").rstrip()  # 터미널이 없어서 터미널 창을 닫지 말라는 안내는 뺌
        if not text:
            return
        print(text, flush=True)  # 기록 파일에 남김
        if self.dismissed:
            return
        self.lines.append(text)
        if self.window is not None:
            self.window.write(text + "\n")
            self.window.update()

    def ask(self, prompt):
        if self.window.ask():
            return "y"
        self.close_window()  # [닫기]를 눌렀으므로 뒤따르는 안내는 띄우지 않음
        self.lines, self.dismissed = [], True
        return ""

    def stream(self, command):
        """명령을 콘솔 창 없이 돌리면서 출력을 준비 창에 흘리고 (종료 코드, 출력)을 돌려줌."""
        def work(emit):
            lines = []
            with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors="replace", creationflags=self.flags) as proc:
                for line in proc.stdout:
                    print(line, end="", flush=True)
                    emit(line)
                    lines.append(line)
            return proc.returncode, "".join(lines)
        return self.window.run(work)

    def create_venv(self, path):
        """venv.EnvBuilder 는 안에서 ensurepip 를 콘솔 프로그램으로 띄워 검은 창이 번쩍이므로 `-m venv` 를 콘솔 창 없이 돌림."""
        command = [study.console_python(), "-m", "venv", path]
        code, _ = self.stream(command)
        if code != 0:
            raise subprocess.CalledProcessError(code, command)

    def pip_install(self, python):
        return self.stream([python] + PIP_INSTALL)

    def remove(self, path):
        self.window.run(lambda emit: shutil.rmtree(path))  # 파일이 많아서 창을 만든 스레드에서 지우면 그동안 창이 멈춤

    def call(self, command):
        """준비 창을 닫고 본 화면을 띄움. Windows 는 콘솔 창이 뜨지 않게 전용 환경의 pythonw.exe 로 띄움.
        study.py 대신 start.pyw 를 실행해서 본 화면 쪽이 예외로 끝나도 기록과 알림이 남음."""
        self.close_window()
        self.lines = []
        pythonw = os.path.join(os.path.dirname(command[0]), "pythonw.exe")
        python = pythonw if os.path.isfile(pythonw) else command[0]
        return subprocess.call([python, START] + command[2:], env=dict(os.environ, STUDY_WINDOW="1"), creationflags=self.flags)

    def finish(self, code):
        """실패 안내가 남아 있으면 [닫기]를 누를 때까지 준비 창에 둠. 준비 창을 띄울 수 없으면 예전 실행 파일로 넘기고 0 을 돌려줌."""
        if not self.lines:
            return code
        if not self.open_window():
            hand_off()
            return 0
        if self.log:
            self.window.write("  기록          : %s\n" % self.log)
        self.window.wait_close()
        self.close_window()
        return code


def windowed():
    """창 모드인가. start.pyw 와 ROKEY.app 이 STUDY_WINDOW=1 을 세우고, pythonw 로 켜면 표준 출력이 없음."""
    return os.environ.get("STUDY_WINDOW") == "1" or sys.stdout is None


def connect_log():
    """표준 출력이나 표준 오류가 없으면(pythonw) 기록 파일에 연결하고 그 경로를 돌려줌. 연결하지 않았으면 None.
    print 는 출력이 없어도 조용히 넘어가지만 sys.stderr.write 처럼 직접 쓰는 코드는 죽음. 파일은 실행할 때마다 새로 씀."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        stream, path = open(LOG, "w", encoding="utf-8", errors="replace", buffering=1), LOG
    except OSError:
        stream, path = open(os.devnull, "w", encoding="utf-8", errors="replace"), None
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    return path


def hand_off():
    """준비 창을 띄울 수 없을 때 예전 실행 파일을 열어 터미널에서 이어 가게 함."""
    os.environ.pop("STUDY_WINDOW", None)  # 넘겨받은 쪽까지 창 모드로 돌면 다시 여기로 와서 끝없이 되풀이됨
    if os.name == "nt":
        os.environ["STUDY_CONSOLE"] = "1"  # 이 값이 없으면 start.bat 이 start.pyw 로 다시 넘겨서 여기로 돌아옴
        os.startfile(os.path.join(ROOT, "start.bat"))
    else:
        subprocess.call(["open", os.path.join(ROOT, "start.command")])


def venv_dir():
    """전용 환경 위치. 저장소 밖에 둬서 OneDrive 동기화·경로 길이·폴더 이동의 영향을 받지 않음."""
    path = os.environ.get("STUDY_VENV") or os.path.join("~", ".rokey-study", "venv")
    return os.path.abspath(os.path.expanduser(path))


def venv_python(venv):
    return os.path.join(venv, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv, "bin", "python")


def venv_state(path):
    """none 은 없거나 빈 폴더, venv 는 가상 환경, other 는 다른 것이 든 폴더라 지우면 안 됨."""
    if os.path.isfile(os.path.join(path, "pyvenv.cfg")):
        return "venv"
    if not os.path.exists(path) or (os.path.isdir(path) and not os.listdir(path)):
        return "none"
    return "other"


def same_path(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def python_problem(info):
    """이 파이썬에 PyQt6 를 설치할 수 없는 이유. 설치할 수 있으면 None."""
    version = info["version"]
    name = "%d.%d" % version
    if not info["bits64"]:
        return "지금 파이썬은 32비트인데, PyQt6 는 64비트 파이썬에만 설치됩니다."
    if version > MAX_VERSION:
        return "지금 파이썬은 %s 인데, PyQt6 가 아직 %s 용으로 나오지 않았습니다." % (name, name)
    oldest = (3, 11) if info["platform"] == "win-arm64" else MIN_VERSION
    if version < oldest:
        return "지금 파이썬은 %s 인데, PyQt6 는 파이썬 %d.%d 이상에만 설치됩니다." % (name, oldest[0], oldest[1])
    return None


def pip_failure(log):
    """pip 가 남긴 오류 글에서 사용자에게 알릴 원인을 고름."""
    if re.search(r"connection|timed out|could not fetch", log, re.IGNORECASE):
        return "인터넷 연결 문제로 PyQt6 를 내려받지 못했습니다. 연결을 확인해 주세요."
    if "No matching distribution" in log:
        return "이 컴퓨터(운영체제·파이썬)에 맞는 PyQt6 설치 파일이 없습니다."
    return "PyQt6 설치 중 오류가 났습니다. 위의 pip 메시지를 확인해 주세요."


def fail(host, reason, retry=RETRY):
    """원인과 선택지를 알리고 종료 코드 1 을 돌려줌."""
    host.say(reason)
    host.say("  다시 시도     : %s" % retry)
    host.say("  터미널로 쓰기 : python study.py go  (채점하기 전에 묻습니다. 채점하면 화면에서 쓰다 만 답도 첫 시도로 기록됩니다)")
    return 1


def consent(host, venv, broken):
    """무엇을 어디에 설치하는지 알리고 동의를 받음."""
    if broken:
        host.say("전용 환경이 온전하지 않습니다(설치가 중간에 끊겼거나, 설치에 쓴 파이썬이 지워졌을 수 있습니다).")
        host.say("지우고 다시 설치합니다.")
    else:
        host.say("화면(창)을 띄우는 데 필요한 PyQt6 가 지금 파이썬에 없습니다.")
        host.say("이 프로그램만 쓰는 전용 환경을 만들어 그 안에 설치합니다.")
    host.say("  설치하는 것      : PyQt6 (창을 그리는 라이브러리)")
    host.say("  용량             : 내려받기 약 85MB, 설치 후 약 250MB")
    host.say("  설치 위치        : %s" % venv)
    host.say("  건드리지 않는 것 : 시스템 파이썬, 이 저장소 폴더")
    host.say("  지우는 방법      : 설치 위치의 폴더를 삭제하면 됩니다")
    return host.ask("설치할까요? [y/N] ").strip().lower() in YES


def launch(argv=None, host=None):
    """화면을 띄우고 종료 코드를 돌려줌. 띄우지 못하면 0 이 아닌 값."""
    argv = list(argv or [])
    if host is None and windowed():
        host = WindowHost(connect_log())
        return host.finish(launch(argv, host))
    host = host or Host()
    info = host.python_info()
    venv = venv_dir()
    rerun = same_path(info["prefix"], venv)  # 전용 환경의 파이썬으로 다시 실행된 쪽인가
    error = host.pyqt_error()
    if error is None:
        try:
            main = host.gui_main()
        except Exception as import_error:  # 문법 오류처럼 ImportError 가 아닌 예외도 같은 안내로 끝냄
            return fail(host, "화면 모듈(gui/app.py)을 불러오지 못했습니다: %s: %s" % (type(import_error).__name__, import_error),
                        retry=UPDATE_RETRY)
        if not rerun:  # 다시 실행된 쪽이면 부모가 이미 알렸음
            host.say(OPENING)
        return int(main() or 0)
    if rerun:  # 여기서 또 다시 실행하면 끝없이 되풀이됨
        return fail(host, "전용 환경(%s)에서 PyQt6 를 불러오지 못했습니다. %s" % (venv, error))

    python = venv_python(venv)
    state = venv_state(venv)
    if state == "venv" and host.probe(python):
        host.say(OPENING)
        return host.call([python, STUDY] + argv)

    # 여기부터는 새로 설치해야 하는 경우
    problem = python_problem(info)
    if problem:
        command = "py -3.14 study.py" if os.name == "nt" else "python3.14 study.py"
        return fail(host, "%s 파이썬 3.14(64비트)를 설치해 주세요: %s" % (problem, PYTHON_URL),
                    retry="파이썬 3.14 설치 후 %s" % command)
    if state == "other":
        return fail(host, "%s 는 가상 환경 폴더가 아니어서 건드리지 않았습니다. 환경 변수 STUDY_VENV 를 확인해 주세요." % venv)
    if not host.can_venv():
        return fail(host, "이 파이썬에는 가상 환경 모듈(venv·ensurepip)이 없습니다. "
                          "Ubuntu·Debian 은 `sudo apt install python3-venv` 로 설치한 뒤 다시 실행해 주세요.")
    if not host.isatty():
        return fail(host, "화면에 필요한 PyQt6 를 설치해야 합니다. 설치 전에 동의를 받아야 하니 터미널에서 직접 실행해 주세요.")
    if not consent(host, venv, broken=state == "venv"):
        return fail(host, "PyQt6 를 설치하지 않아 화면을 열 수 없습니다.")

    try:
        if state == "venv":
            host.remove(venv)
        host.say("전용 환경을 만드는 중입니다.")
        host.create_venv(venv)
    except (OSError, subprocess.CalledProcessError) as os_error:
        return fail(host, "전용 환경을 준비하지 못했습니다(%s). %s" % (venv, os_error))
    host.say("PyQt6 를 내려받아 설치합니다.")
    code, log = host.pip_install(python)
    if code != 0:
        return fail(host, pip_failure(log))
    host.say("설치가 끝났습니다. " + OPENING)
    return host.call([python, STUDY] + argv)
