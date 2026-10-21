# -*- coding: utf-8 -*-
"""화면 진입점. `python study.py` 가 bootstrap 을 거쳐 main() 을 부름."""
import os
import subprocess
import sys

from PyQt6.QtCore import QLibraryInfo, QLockFile, QSettings, QTimer, QTranslator
from PyQt6.QtWidgets import QApplication

import study
from gui import errors, icon, theme
from gui.dialogs import MessageDialog
from gui.window import MainWindow
from webprep import dev


def korean(app):
    """답 칸의 우클릭 메뉴처럼 Qt 가 만드는 글자를 한글로 바꿈. 번역 파일이 없으면 영어로 남음."""
    translator = QTranslator(app)
    if translator.load("qtbase_ko", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    return translator


def stop_servers_on_hangup(app):
    """터미널에서 띄운 창(start.command, python study.py)은 터미널 창을 닫으면 SIGHUP 으로 끝남. 그때도 [화면 띄우기]의 서버가
    남지 않게 dev.stop_on_hangup 의 처리기를 걺. 파이썬 신호 처리기는 파이썬 코드가 돌 때만 불려서, 타이머로 0.5초마다 빈 파이썬
    함수를 부름. Windows 는 걸 처리기가 없음."""
    if sys.platform == "win32":
        return None
    dev.stop_on_hangup()
    timer = QTimer(app)
    timer.timeout.connect(lambda: None)
    timer.start(500)
    return timer


def main(argv=None):
    app = QApplication(sys.argv[:1] + list(sys.argv[1:] if argv is None else argv))
    app.setApplicationName("프로그래밍 스터디")
    settings = QSettings("rokey-python-study", "study")  # 저장소 이름을 바꾸기 전의 이름이지만, 바꾸면 저장된 테마와 창 크기를 잃어서 그대로 둠
    theme.apply(app, settings.value("theme", "system", type=str))
    icon.install(app)
    korean(app)
    errors.install(os.path.join(study.ROOT, ".study_logs"))

    lock = QLockFile(os.path.join(study.ROOT, ".study.lock"))  # 창 두 개가 같은 풀이 기록을 덮어쓰지 않게 하나만 띄움
    lock.setStaleLockTime(0)  # 오래 켜 둬도 잠금이 풀리지 않게 함. 죽은 프로세스의 잠금은 Qt 가 치움
    if not lock.tryLock(0):
        text = "이미 실행 중입니다. 열려 있는 창을 사용해 주세요."
        if sys.stderr:  # pythonw 로 띄우면 stderr 가 없음
            print(text, file=sys.stderr)
        MessageDialog(None, "프로그래밍 스터디", text).exec()
        return 1

    stop_servers_on_hangup(app)
    window = MainWindow(settings)
    window.show()
    window.boot()
    code = app.exec()
    lock.unlock()
    if window.restart:  # 도구 파일이 새 버전으로 바뀌었으면 처음 실행한 명령으로 다시 띄움
        return subprocess.call([sys.executable] + sys.orig_argv[1:])  # 새 창이 끝날 때까지 기다림. 터미널에서 켰을 때 먼저 끝나면 터미널·start.bat 이 닫혀 새 창이 죽음
    return code


if __name__ == "__main__":
    sys.exit(main())
