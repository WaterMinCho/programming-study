# -*- coding: utf-8 -*-
"""채점·코드 실행·git 처럼 오래 걸리는 일을 화면 밖 스레드에서 한 번에 하나씩 돌림."""
import threading
import traceback

from PyQt6.QtCore import QThread, pyqtSignal

from session import SessionError


class Job(QThread):
    done = pyqtSignal(object)
    failed = pyqtSignal(str, str)  # (사용자에게 그대로 보여 줄 문구, 트레이스백). 둘 중 하나만 채움
    progress = pyqtSignal(object)  # 워커에서 내면 화면 스레드로 넘어감

    def __init__(self, fn, progress=False):
        """progress 면 fn(진행 알림, 취소 신호)로 부름. 취소 신호는 진행 알림을 받는 일만 봄."""
        super().__init__()
        self.fn, self.with_progress = fn, progress
        self.cancel = threading.Event()

    def run(self):
        try:
            result = self.fn(self.progress.emit, self.cancel) if self.with_progress else self.fn()
        except SessionError as error:
            self.failed.emit(str(error), "")
        except BaseException:  # 코어의 die() 가 내는 SystemExit 도 잡음. 스레드에서 새면 창이 죽음
            self.failed.emit("", traceback.format_exc())
        else:
            self.done.emit(result)
