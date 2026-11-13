# -*- coding: utf-8 -*-
"""처음 사용하는 기기에서 계정 정보를 남기지 않고 본인 확인을 받음."""
import time

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QDialog

from gui import kit
from gui.worker import Job
from learning_data.collection import CollectionError


class IdentityDialog(QDialog):
    def __init__(self, win, identity):
        super().__init__(win)
        self.win, self.identity, self.job = win, identity, None
        self.pending_close, self.expires, self.retrying = False, 0, False
        self.setWindowTitle("이 기기에서 본인 확인")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setProperty("ui", "2")
        room = win.screen().availableGeometry()
        self.resize(min(620, room.width() - 32), min(460, room.height() - 64))
        box = kit.box(self, (24, 24, 24, 24), 16)
        inner = kit.frame("page")
        content = kit.box(inner, spacing=16)
        content.addWidget(kit.label("GitHub에서 한 번 확인합니다", "headline", bold=True))
        content.addWidget(kit.para("기존 사용자도 이 기기에서 처음 한 번 확인합니다. 실명·이메일·사진과 GitHub 계정 번호 원문은 저장하지 않습니다.", "body"))
        content.addWidget(kit.para("계정 중복을 확인할 수 있는 HMAC 값과 임의 기기 코드를 보관합니다. GitHub 토큰은 확인 후 해제합니다.", "caption", "secondary"))
        content.addWidget(kit.para("임의 기기 코드로 첫 실행 기기 수를 집계합니다. 학습 기록 제공 여부는 다음 화면에서 별도로 선택합니다.", "caption", "secondary"))
        self.code = kit.label("", "title", bold=True)
        self.code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.code.hide()
        content.addWidget(self.code)
        self.status = kit.para("아래 버튼을 눌러 GitHub 본인 확인을 시작해 주세요.", "body", "secondary")
        content.addWidget(self.status)
        self.copy = kit.button("확인 코드 복사")
        self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.code.text()))
        self.copy.hide()
        content.addWidget(self.copy)
        box.addWidget(kit.scroll(inner), 1)
        self.begin_button = kit.button("GitHub에서 확인하기", "primary", "l")
        self.begin_button.clicked.connect(self.begin)
        box.addWidget(self.begin_button)
        self.cancel_button = kit.button("프로그램 닫기", "text")
        self.cancel_button.clicked.connect(self.reject)
        box.addWidget(self.cancel_button)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.poll)

    def work(self, fn, done):
        if self.job is not None:
            return
        self.begin_button.setEnabled(False)
        def call():
            try:
                return fn()
            except CollectionError as error:
                return {"error": str(error)}
            except Exception:
                return {"error": "본인 확인을 처리하지 못했습니다. 다시 시도해 주세요."}
        job = self.job = Job(call)
        def finished(result):
            job.wait()
            self.job = None
            self.begin_button.setEnabled(True)
            if self.pending_close:
                super(IdentityDialog, self).reject()
            elif result.get("error"):
                self.retrying = True
                self.status.setText(result["error"])
                self.begin_button.setText("다시 확인하기")
            else:
                done(result)
        job.done.connect(finished)
        job.start()

    def begin(self):
        self.timer.stop()
        if self.identity.pending_token is not None and time.monotonic() < self.expires:
            self.work(self.identity.poll, self.polled)
            return
        if self.identity.device is not None and time.monotonic() < self.expires:
            if self.retrying:
                self.retrying = False
                self.work(self.identity.poll, self.polled)
                return
            self.win.open_url(self.identity.device["verification_uri"])
            self.timer.start(max(5, int(self.identity.device.get("interval", 5))) * 1000)
            return
        self.status.setText("본인 확인 코드를 준비하고 있습니다.")
        self.work(self.identity.begin, self.started)

    def started(self, result):
        self.retrying = False
        self.code.setText(result["user_code"])
        self.code.show()
        self.copy.show()
        self.status.setText("열린 GitHub 화면에 이 코드를 입력하고 확인해 주세요. 완료되면 프로그램으로 돌아옵니다.")
        self.expires = time.monotonic() + result["expires_in"]
        self.win.open_url(result["verification_uri"])
        self.begin_button.setText("확인 창 다시 열기")
        self.timer.start(max(5, int(self.identity.device.get("interval", 5))) * 1000)

    def poll(self):
        if time.monotonic() >= self.expires:
            self.status.setText("확인 코드가 만료됐습니다. 다시 확인해 주세요.")
            self.identity.cancel()
            return
        self.work(self.identity.poll, self.polled)

    def polled(self, result):
        if result.get("pending"):
            self.timer.start(result["interval"] * 1000)
        else:
            self.complete(result)

    def complete(self, result):
        if result.get("verified"):
            self.timer.stop()
            self.accept()

    def reject(self):
        self.timer.stop()
        self.identity.cancel()
        if self.job is not None:
            self.pending_close = True
            self.status.setText("진행 중인 확인을 마친 뒤 프로그램을 닫습니다.")
            return
        super().reject()
