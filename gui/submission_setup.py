# -*- coding: utf-8 -*-
"""보낼 풀이 파일을 확인하고 비공개 서버 제출을 연결함."""
from PyQt6.QtWidgets import QCheckBox, QDialog, QLineEdit, QPlainTextEdit

from gui import kit, theme
from gui.dialog_layout import DialogLayout
from learning_data.collection import CollectionError
from learning_data.privacy import DEFAULT_SERVER
from learning_data.submission import snapshot


def file_listing(client):
    try:
        files = snapshot(client.root, client.user)
        return bool(files), "\n".join(sorted(files)) or "아직 제출할 풀이 파일이 없습니다."
    except (CollectionError, OSError, ValueError) as error:
        return False, str(error)


class SubmissionFiles(QDialog):
    """선택해서 여는 읽기 전용 파일 목록. 연결·등록·제출은 호출하지 않음."""

    def __init__(self, parent, client):
        super().__init__(parent)
        self.setWindowTitle("보낼 풀이 파일")
        self.setModal(True)
        self.finished.connect(self.deleteLater)
        kit.page(self)
        self.shell = DialogLayout(self, "보낼 풀이 파일", "[풀이 제출]을 누르면 답안 파일·채점·진도를 비공개 서버에 보냅니다.")
        self.files = QPlainTextEdit(file_listing(client)[1])
        self.files.setReadOnly(True)
        self.files.setMinimumHeight(96)
        self.shell.content.addWidget(self.files)
        close = kit.button("닫기", scale="l")
        close.clicked.connect(self.accept)
        self.shell.actions.set_actions([], [close])
        self.shell.fit(640, 400)


class SubmissionSetup(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.client = win, win.gitflow.api
        self.setWindowTitle("제출 서버 연결")
        self.setModal(True)
        kit.page(self)
        area = win.screen().availableGeometry()
        self.resize(min(640, win.width(), area.width()-32), min(640, win.height(), area.height()-72))
        self.move(area.x()+(area.width()-self.width())//2, area.y()+24)
        self.shell = DialogLayout(self, "제출 서버 연결", "스터디원이 별도 서버를 연결할 때 사용합니다. 일반 제출은 첫 화면의 [풀이 제출]을 누릅니다.")
        body = self.shell.content
        body.addWidget(kit.para("답안 파일·채점·진도를 문제 추천 연구에 사용합니다. 수집 동의와 보관 기간은 [내 정보·데이터]에서 확인하고 철회할 수 있습니다.", "caption", "secondary"))
        connection_error = ""
        try:
            base = self.client.settings().get("url") or DEFAULT_SERVER
        except CollectionError as error:
            base, connection_error = DEFAULT_SERVER, str(error)
        self.url = QLineEdit(base)
        self.url.setAccessibleName("풀이 제출 서버 주소")
        body.addWidget(self.url)
        available, listing = file_listing(self.client)
        if connection_error:
            available, listing = False, connection_error
        preview = kit.button("보낼 풀이 파일 보기", "text", "l")
        preview.setCheckable(True)
        body.addWidget(preview)
        self.files = QPlainTextEdit(listing)
        self.files.setReadOnly(True)
        self.files.setMinimumHeight(96)
        self.files.hide()
        preview.toggled.connect(self.files.setVisible)
        body.addWidget(self.files)
        self.confirm_private = QCheckBox("위 파일을 비공개 서버에 제출합니다.")
        kit.typed(self.confirm_private, "body")
        self.confirm_private.setMinimumHeight(theme.control_height("s"))
        self.confirm_private.setEnabled(available)
        body.addWidget(self.confirm_private)
        self.message = kit.para("" if available else listing, "caption", "secondary")
        body.addWidget(self.message)
        self.connect_button = kit.button("확인하고 제출", "primary", "l")
        self.connect_button.setEnabled(False)
        self.confirm_private.toggled.connect(lambda checked: self.connect_button.setEnabled(checked and self.confirm_private.isEnabled()))
        self.connect_button.clicked.connect(self.connect_and_submit)
        body.addStretch(1)
        close = kit.button("닫기", scale="l")
        close.clicked.connect(self.reject)
        self.shell.actions.set_actions([], [close, self.connect_button])
        self.shell.fit(680, 520)

    def connect_and_submit(self):
        if not self.confirm_private.isChecked() or not self.confirm_private.isEnabled():
            return
        base = self.url.text()
        def work():
            try:
                self.client.connect_open(base)
                return self.client.submit()
            except (CollectionError, OSError, ValueError) as error:
                return {"status": "error", "message": str(error)}
        if self.win.run_job("비공개로 제출하는 중입니다.", work, lambda result: self.win._git_done("풀이 제출", result)):
            self.accept()
        else:
            self.message.setText("다른 작업을 마친 뒤 다시 제출해 주세요. 확인한 파일 목록은 유지했습니다.")
