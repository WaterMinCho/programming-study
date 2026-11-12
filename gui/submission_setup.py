# -*- coding: utf-8 -*-
"""개인 초대로 API 제출을 연결하고 공개할 풀이 파일을 안내함."""
from PyQt6.QtWidgets import QDialog, QLineEdit, QPlainTextEdit, QWidget

from gui import kit, theme
from aiprep.collection import CollectionError
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
            "개인 초대로 연결하면 GitHub 쓰기 권한 없이 제출합니다.")))
        body.addWidget(kit.para("풀이 파일은 GitHub 공개 PR에 올립니다. 추가 학습 데이터는 비공개로 보내며 입력 답안은 기본으로 제외합니다.", "caption", "secondary"))
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://제출-서버-주소")
        self.url.setAccessibleName("풀이 제출 서버 주소")
        self.invite = QLineEdit()
        self.invite.setPlaceholderText("개인 초대 코드")
        self.invite.setAccessibleName("개인 초대 코드")
        self.invite.setEchoMode(QLineEdit.EchoMode.Password)
        try:
            self.url.setText(self.client.settings().get("url", ""))
            files = snapshot(self.client.root, self.client.user)
            listing = "\n".join(sorted(files)) or "아직 제출할 풀이 파일이 없습니다."
        except (CollectionError, OSError, ValueError) as error:
            listing = str(error)
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
        self.connect_button = kit.button("연결하고 제출", "primary", "l")
        self.connect_button.clicked.connect(self.connect_and_submit)
        direct = kit.button("GitHub로 직접 제출", "text", "l")
        direct.clicked.connect(self.direct)
        body.addWidget(direct)
        body.addWidget(kit.para("직접 제출은 저장소 쓰기 권한이 있는 스터디원만 사용합니다. 수집 중단·답안 포함 설정은 각 과목의 [학습 데이터]에서 관리합니다.", "caption", "secondary"))
        outer.addWidget(kit.scroll(content), 1)
        footer = QWidget()
        row = kit.FlowLayout(footer, spacing=theme.GAP["detail"])
        row.addWidget(self.connect_button)
        close = kit.button("닫기", scale="l")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        outer.addWidget(footer)

    def connect_and_submit(self):
        base, code = self.url.text(), self.invite.text()
        self.invite.clear()
        self.accept()
        def work():
            try:
                self.client.connect(base, code)
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
