# -*- coding: utf-8 -*-
"""보낼 풀이 파일을 확인하고 비공개 서버 제출을 연결함."""
from PyQt6.QtWidgets import QCheckBox, QDialog, QLineEdit, QPlainTextEdit, QWidget

from gui import kit, theme
from aiprep.collection import CollectionError
from aiprep.privacy import DEFAULT_SERVER
from submission_api import snapshot


class SubmissionSetup(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.client = win, win.gitflow.api
        self.setWindowTitle("비공개 풀이 제출")
        self.setModal(True)
        kit.page(self)
        area = win.screen().availableGeometry()
        self.resize(min(640, win.width(), area.width()-32), min(640, win.height(), area.height()-72))
        self.move(area.x()+(area.width()-self.width())//2, area.y()+24)
        outer = kit.box(self, (24, 24, 24, 24), spacing=theme.GAP["group"])
        content = QWidget()
        body = kit.box(content, spacing=theme.GAP["paragraph"])
        body.addWidget(kit.heading(kit.label("비공개 풀이 제출", "headline"), kit.para(
            "확인한 풀이 파일을 서버에 보관합니다. GitHub에는 올리지 않습니다.")))
        body.addWidget(kit.para("답안 파일·채점·진도를 문제 추천 연구에 사용합니다. 수집 동의와 보관 기간은 [내 정보·데이터]에서 확인하고 철회할 수 있습니다.", "caption", "secondary"))
        self.url = QLineEdit(DEFAULT_SERVER)
        self.url.setAccessibleName("풀이 제출 서버 주소")
        self.url.hide()
        advanced = kit.button("다른 서버 연결 (운영자용)", "text", "l")
        advanced.setCheckable(True)
        advanced.toggled.connect(self.url.setVisible)
        body.addWidget(advanced)
        body.addWidget(self.url)
        try:
            files = snapshot(self.client.root, self.client.user)
            listing = "\n".join(sorted(files)) or "아직 제출할 풀이 파일이 없습니다."
        except (CollectionError, OSError, ValueError) as error:
            listing = str(error)
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
        self.confirm_private.setFont(theme.font("body"))
        self.confirm_private.setMinimumHeight(theme.control_height("s"))
        body.addWidget(self.confirm_private)
        self.connect_button = kit.button("확인하고 제출", "primary", "l")
        self.connect_button.setEnabled(False)
        self.confirm_private.toggled.connect(self.connect_button.setEnabled)
        self.connect_button.clicked.connect(self.connect_and_submit)
        outer.addWidget(kit.scroll(content), 1)
        footer = QWidget()
        row = kit.FlowLayout(footer, spacing=theme.GAP["detail"])
        row.addWidget(self.connect_button)
        close = kit.button("닫기", scale="l")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        outer.addWidget(footer)

    def connect_and_submit(self):
        if not self.confirm_private.isChecked():
            return
        base = self.url.text()
        self.accept()
        def work():
            try:
                self.client.connect_open(base)
                return self.client.submit()
            except (CollectionError, OSError, ValueError) as error:
                return {"status": "error", "message": str(error)}
        self.win.run_job("비공개로 제출하는 중입니다.", work, lambda result: self.win._git_done("풀이 제출", result))
