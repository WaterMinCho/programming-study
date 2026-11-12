# -*- coding: utf-8 -*-
"""개인 초대로 API 제출을 연결하고 공개할 풀이 파일을 안내함."""
from PyQt6.QtWidgets import QCheckBox, QDialog, QLineEdit, QPlainTextEdit, QWidget

from gui import kit, theme
from aiprep.collection import CollectionError
from aiprep.privacy import DEFAULT_SERVER
from submission_api import snapshot


class SubmissionSetup(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.client = win, win.gitflow.api
        self.setWindowTitle("풀이 제출 연결")
        self.setModal(True)
        kit.page(self)
        area = win.screen().availableGeometry()
        self.resize(min(640, win.width(), area.width() - 32), min(640, win.height(), area.height() - 72))
        self.move(area.x() + (area.width() - self.width()) // 2, area.y() + 24)
        outer = kit.box(self, (24, 24, 24, 24), spacing=theme.GAP["group"])
        content = QWidget()
        body = kit.box(content, spacing=theme.GAP["paragraph"])
        body.addWidget(kit.heading(kit.label("풀이 제출 연결", "headline"), kit.para(
            "공개할 파일을 확인한 뒤 제출합니다. GitHub 로그인이나 쓰기 권한은 필요하지 않습니다.")))
        body.addWidget(kit.para("풀이 파일은 서버에 저장한 뒤 GitHub 공개 PR에 올립니다. 동의한 비공개 학습 기록의 자동 전송과는 별도입니다.", "caption", "secondary"))
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://제출-서버-주소")
        self.url.setAccessibleName("풀이 제출 서버 주소")
        self.invite = QLineEdit()
        self.invite.setPlaceholderText("개인 초대 코드")
        self.invite.setAccessibleName("개인 초대 코드")
        self.invite.setEchoMode(QLineEdit.EchoMode.Password)
        try:
            self.url.setText(self.client.settings().get("url", DEFAULT_SERVER))
            files = snapshot(self.client.root, self.client.user)
            listing = "\n".join(sorted(files)) or "아직 제출할 풀이 파일이 없습니다."
        except (CollectionError, OSError, ValueError) as error:
            listing = str(error)
        advanced = kit.button("다른 서버·개인 초대 연결 (운영자용)", "text", "l")
        advanced.setCheckable(True)
        self.url.hide()
        self.invite.hide()
        advanced.toggled.connect(self.url.setVisible)
        advanced.toggled.connect(self.invite.setVisible)
        body.addWidget(advanced)
        body.addWidget(self.url)
        body.addWidget(self.invite)
        preview = kit.button("공개할 풀이 파일 보기", "text", "l")
        preview.setCheckable(True)
        body.addWidget(preview)
        self.files = QPlainTextEdit(listing)
        self.files.setReadOnly(True)
        self.files.setMinimumHeight(96)
        self.files.hide()
        preview.toggled.connect(self.files.setVisible)
        body.addWidget(self.files)
        self.confirm_public = QCheckBox("확인한 풀이 파일을 GitHub에 공개합니다.")
        self.confirm_public.setFont(theme.font("body"))
        self.confirm_public.setMinimumHeight(theme.control_height("s"))
        body.addWidget(self.confirm_public)
        self.connect_button = kit.button("확인하고 제출", "primary", "l")
        self.connect_button.setEnabled(False)
        self.confirm_public.toggled.connect(self.connect_button.setEnabled)
        self.connect_button.clicked.connect(self.connect_and_submit)
        direct = kit.button("GitHub로 직접 제출", "text", "l")
        direct.setEnabled(False)
        self.confirm_public.toggled.connect(direct.setEnabled)
        direct.clicked.connect(self.direct)
        body.addWidget(direct)
        body.addWidget(kit.para("직접 제출은 저장소 쓰기 권한이 있는 스터디원만 사용합니다. 비공개 수집 동의·철회는 [내 정보·데이터]에서 관리합니다.", "caption", "secondary"))
        outer.addWidget(kit.scroll(content), 1)
        footer = QWidget()
        row = kit.FlowLayout(footer, spacing=theme.GAP["detail"])
        row.addWidget(self.connect_button)
        close = kit.button("닫기", scale="l")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        outer.addWidget(footer)

    def connect_and_submit(self):
        if not self.confirm_public.isChecked():
            return
        base, code = self.url.text(), self.invite.text()
        self.invite.clear()
        self.accept()
        def work():
            try:
                if code:
                    self.client.connect(base, code)
                else:
                    self.client.connect_open(base)
            except (CollectionError, OSError, ValueError) as error:
                return {"status": "error", "message": str(error)}
            return self.win.gitflow.submit()
        self.win.run_job("풀이 제출을 연결하는 중입니다.", work, lambda result: self.win._git_done("풀이 제출", result))

    def direct(self):
        try:
            config = self.client.settings()
            config["mode"] = "git"
            self.client.save(config)
        except (CollectionError, OSError, ValueError) as error:
            self.win.ask("제출 연결", str(error))
            return
        self.accept()
        self.win.submit_pr()
