#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""터미널 없이 스터디 화면(창)을 띄움. Windows 는 더블클릭하면 pythonw 로 실행되고, macOS 는 ROKEY.app 이 이 파일을 실행함.

study.py 를 창 모드(STUDY_WINDOW=1)로 부름. 받아 온 코드에 오류가 있어 창을 못 띄우면 기록을 남기고 예전 실행 파일을 알려 줌.
첫 줄을 `/usr/bin/env python3` 로 쓰면 Windows 의 py 실행기가 PATH 에서 python3.exe 를 먼저 찾아 콘솔용 파이썬으로 띄워서 검은 창이 뜸.
env 없이 쓰면 등록된 파이썬 3 의 pythonw.exe 로 띄움.
"""
import datetime
import os
import subprocess
import sys
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.expanduser("~"), ".rokey-study", "launch.log")  # bootstrap.LOG 와 같은 파일
TITLE = "ROKEY 파이썬 스터디"
FAILED = "창을 열지 못했습니다. start.bat(맥은 start.command)으로 실행하거나 python study.py update 를 실행해 주세요.\n기록: %s"


def record(text):
    """오류 내용을 기록 파일 끝에 붙임. 쓰지 못해도 알림은 띄워야 해서 넘어감."""
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[%s]\n%s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), text))
    except OSError:
        pass


def alert(text):
    """터미널이 없으므로 운영체제의 알림 창으로 알림."""
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x10)  # 0x10: 오류 아이콘
    elif sys.platform == "darwin":
        script = ["-e", "on run argv", "-e", "display alert (item 1 of argv) message (item 2 of argv)", "-e", "end run"]
        subprocess.call(["osascript"] + script + [TITLE, text])
    elif sys.stderr:
        print(text, file=sys.stderr)


def main():
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    os.environ["STUDY_WINDOW"] = "1"
    try:
        import study
        study.main([])
    except Exception:  # 끝낼 때 쓰는 SystemExit 는 여기서 잡히지 않음
        record(traceback.format_exc())
        alert(FAILED % LOG)
        sys.exit(1)


if __name__ == "__main__":
    main()
