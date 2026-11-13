# -*- coding: utf-8 -*-
"""처음 사용하는 기기에서 계정 정보를 남기지 않고 본인 확인을 받음."""
import time

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QDialog

from gui import kit
from gui.dialog_layout import DialogLayout
from gui.worker import Job
from learning_data.collection import CollectionError


class IdentityDialog(QDialog):
    def __init__(self, win, identity, closing_app=True):
        super().__init__(win)
        self.win, self.identity, self.job = win, identity, None
        self.closing_app = closing_app
        self.pending_close, self.expires, self.retrying = False, 0, False
        self.setWindowTitle("이 기기에서 본인 확인")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.shell = DialogLayout(self, "GitHub 본인 확인")
        content = self.shell.content
        content.addWidget(kit.para("이 기기에서는 처음 한 번만 확인합니다.", "body", "secondary"))
        self.code_panel = kit.frame("verification_code")
        code_box = kit.box(self.code_panel, (24, 16, 24, 16), 8)
        self.copy_notice = kit.para("GitHub 화면에 아래 코드를 입력해 주세요.", "caption", "secondary")
        code_box.addWidget(self.copy_notice)
        self.code = kit.label("", "title", bold=True, align=Qt.AlignmentFlag.AlignCenter)
        self.code.setObjectName("verification_code_text")
        self.code.setTextFormat(Qt.TextFormat.PlainText)
        self.code.setAccessibleName("GitHub 확인 코드")
        self.code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        code_box.addWidget(self.code)
        self.code_panel.hide()
        content.addWidget(self.code_panel)
        self.status = kit.para("아래 버튼을 누르면 브라우저에서 GitHub 확인 화면이 열립니다.", "body", "secondary")
        content.addWidget(self.status)
        self.details_button = kit.button("보관하는 정보", "text", "s")
        self.details_button.setCheckable(True)
        content.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.details = kit.para("실명·이메일·사진과 GitHub 계정 번호 원문은 저장하지 않습니다. 계정 중복 집계용 HMAC 값과 임의 기기 코드만 보관합니다. "
                               "GitHub 토큰은 확인 후 해제합니다. 다음 실행부터는 이 기기를 자동으로 확인합니다. 임의 기기 코드로 첫 실행 기기 수를 집계합니다. "
                               "학습 기록 제공은 다음 화면에서 따로 선택합니다.",
                               "caption", "secondary")
        self.details.hide()
        self.details_button.toggled.connect(self.details.setVisible)
        content.addWidget(self.details)
        self.copy = kit.button("확인 코드 복사", scale="l")
        self.copy.clicked.connect(self.copy_code)
        self.copy.hide()
        self.begin_button = kit.button("GitHub에서 확인하기", "primary", "l")
        self.begin_button.clicked.connect(self.begin)
        self.cancel_button = kit.button("프로그램 닫기" if closing_app else "취소", scale="l")
        self.cancel_button.clicked.connect(self.reject)
        self.shell.actions.set_actions([self.copy], [self.cancel_button, self.begin_button])
        self.shell.fit(680, 420)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.poll)
        self.copy_timer = QTimer(self)
        self.copy_timer.setSingleShot(True)
        self.copy_timer.timeout.connect(lambda: self.copy_notice.setText("GitHub 화면에 아래 코드를 입력해 주세요."))
        self.begin_button.setFocus()

    def valid_code(self):
        return bool(self.code.text() and self.identity.device is not None and self.identity.pending_token is None
                    and time.monotonic() < self.expires and not self.pending_close)

    def hide_code(self):
        focused = self.copy.hasFocus() or self.code.hasFocus()
        self.copy.hide()
        self.code_panel.hide()
        self.code.clear()
        self.code.setAccessibleName("GitHub 확인 코드")
        if focused and not self.pending_close:
            self.begin_button.setFocus()

    def copy_code(self):
        if self.valid_code():
            QApplication.clipboard().setText(self.code.text())
            self.copy_notice.setText("확인 코드를 복사했습니다.")
            self.copy_timer.start(3000)
        elif self.identity.pending_token is None and time.monotonic() >= self.expires:
            self.expired()

    def work(self, fn, done, background=False):
        if self.job is not None:
            return
        if not background:
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
            if self.pending_close:
                super(IdentityDialog, self).reject()
            elif result.get("error"):
                self.begin_button.setEnabled(True)
                self.retrying = True
                self.status.setText(result["error"])
                self.begin_button.setText("다시 확인하기")
                if not self.valid_code():
                    self.hide_code()
            else:
                if not background:
                    self.begin_button.setEnabled(True)
                done(result)
        job.done.connect(finished)
        job.start()

    def begin(self):
        self.timer.stop()
        device = self.identity.device
        if self.identity.pending_token is not None:
            self.work(self.identity.poll, self.polled)
            return
        if device is not None and time.monotonic() < self.expires:
            if self.retrying:
                self.retrying = False
                self.work(self.identity.poll, self.polled)
                return
            self.win.open_url(device["verification_uri"])
            self.timer.start(max(5, int(device.get("interval", 5))) * 1000)
            return
        self.status.setText("본인 확인 코드를 준비하고 있습니다.")
        self.hide_code()
        self.work(self.identity.begin, self.started)

    def started(self, result):
        self.retrying = False
        self.code.setText(result["user_code"])
        self.code.setAccessibleName("GitHub 확인 코드 " + result["user_code"])
        self.code_panel.show()
        self.copy.show()
        self.copy_notice.setText("GitHub 화면에 아래 코드를 입력해 주세요.")
        self.status.setText("GitHub에서 확인을 마치면 자동으로 이어집니다.")
        self.expires = time.monotonic() + result["expires_in"]
        self.win.open_url(result["verification_uri"])
        self.begin_button.setText("확인 창 다시 열기")
        self.timer.start(max(5, int(self.identity.device.get("interval", 5))) * 1000)

    def poll(self):
        if self.identity.pending_token is None and time.monotonic() >= self.expires:
            self.expired()
            return
        self.work(self.identity.poll, self.polled, background=True)

    def expired(self):
        self.timer.stop()
        self.status.setText("확인 코드가 만료됐습니다. 다시 확인해 주세요.")
        self.hide_code()
        self.begin_button.setText("새 코드 받기")
        self.identity.cancel()

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
        self.copy_timer.stop()
        self.pending_close = self.job is not None
        self.hide_code()
        self.identity.cancel()
        if self.job is not None:
            self.begin_button.setEnabled(False)
            self.copy.setEnabled(False)
            self.status.setText("진행 중인 확인을 마친 뒤 프로그램을 닫습니다." if self.closing_app else "진행 중인 확인을 마친 뒤 이 창을 닫습니다.")
            return
        super().reject()
