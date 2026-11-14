# -*- coding: utf-8 -*-
"""대화상자. 화면이 멈추지 않고 시험하기 쉽게, 모두 exec() 없이 show() 로 띄우고 고른 결과를 콜백으로 넘김."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QDialog, QLineEdit, QPlainTextEdit

import session
from gui import kit, theme
from gui.dialog_layout import DialogLayout
from gui.widgets import LinkLabel


class MessageDialog(QDialog):
    """안내·확인. buttons 는 (글자, 키) 또는 (글자, 키, 역할) 목록이고 첫 번째가 오른쪽 끝에 옴. 역할은 primary(파란 주 단추, 단추가 하나면
    Enter 로 눌림), danger(되돌릴 수 없는 행동. 빨간 옅은 바탕, Enter 없음), danger_text(주 단추가 따로 있는 창의 되돌릴 수 없는 행동.
    빨간 글자 단추이고 주 단추와 가장 멀게 왼쪽 끝에 옴), close(닫기 같은 보조 단추). 역할을 주지 않으면 첫 번째가 primary,
    나머지는 close. 창을 그냥 닫으면 고른 키는 "" 임."""

    def __init__(self, parent, title, text, buttons=(("확인", "ok"),), on_choice=None, detail="", link=""):
        super().__init__(parent)
        kit.page(self)
        self.setWindowTitle(title)
        self.setModal(True)
        self.on_choice, self.choice = on_choice, ""
        self.shell = DialogLayout(self, title)
        box = self.shell.content
        self.text = kit.para(text)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.text)
        if link:
            self.link = kit.typed(LinkLabel('<a href="%s">%s</a>' % (link, link), line=theme.TYPE["body"][1], font=theme.font("body")), "body")
            self.link.linkActivated.connect(lambda url: parent.open_url(url))
            box.addWidget(self.link)
        self.detail = QPlainTextEdit(detail)
        self.detail.setReadOnly(True)
        self.detail.setFont(theme.code_font(theme.text_px() - 1))
        self.detail.setMinimumHeight(140)
        self.detail.hide()
        box.addWidget(self.detail)
        tools = []
        if detail:
            more = kit.button("자세히", "text", "l")
            more.clicked.connect(lambda: (self.detail.setVisible(not self.detail.isVisible()), self.fit()))
            copy = kit.button("내용 복사", "text", "l")
            copy.clicked.connect(lambda: QGuiApplication.clipboard().setText("%s\n\n%s" % (text, detail)))
            tools = [more, copy]
        self.buttons = {}
        roles = {}
        for number, item in enumerate(buttons):
            label, key = item[0], item[1]
            roles[key] = item[2] if len(item) > 2 else ("primary" if number == 0 else "close")
        for item in reversed(buttons):  # 첫 번째 버튼이 오른쪽 끝에 오게
            label, key = item[0], item[1]
            kind = {"primary": "primary", "danger": "danger", "danger_text": "danger_text"}.get(roles[key], "secondary")
            button = kit.button(label, kind, "l")
            button.clicked.connect(lambda checked=False, k=key: self.choose(k))
            button.setParent(self)  # 창의 단추 규칙(ui=2)이 붙은 뒤에 크기를 잼
            button.ensurePolished()
            button.setMinimumWidth(button.sizeHint().width())  # 창이 좁아도 단추 글자가 잘리지 않게
            self.buttons[key] = button
        first = self.buttons[buttons[0][1]]
        first.setDefault(len(buttons) == 1 and roles[buttons[0][1]] == "primary")  # 고를 것이 있거나 되돌릴 수 없는 창은 Enter 로 넘어가지 않음
        far = [self.buttons[key] for key in roles if roles[key] == "danger_text"]  # 왼쪽 끝. 주 단추와 가장 멀게
        made = [button for button in self.buttons.values() if button not in far]
        self.shell.actions.set_actions(tools + far, made)
        self.fit()

    def fit(self):
        self.shell.fit(560)

    def choose(self, key):
        self.choice = key
        self.accept()
        if self.on_choice:
            self.on_choice(key)


class IdDialog(QDialog):
    """첫 실행 때 풀이를 구분할 ID를 받아 저장함."""

    def __init__(self, parent, on_saved):
        super().__init__(parent)
        self.setWindowTitle("처음 실행")
        self.setModal(True)
        self.on_saved = on_saved
        self.asked = ""  # 풀이 기록이 이미 있다고 알린 ID
        self.shell = DialogLayout(self, "풀이 ID를 입력해 주세요")
        box = self.shell.content
        why = kit.para("영문·숫자·밑줄·붙임표로 풀이 ID를 정합니다. 메일 주소나 실명은 넣지 않습니다. "
                   "기존 기록을 이어서 풀려면 사용하던 ID를 입력합니다. "
                   "풀이 파일은 내용을 확인한 뒤 비공개 서버로 보냅니다.", "body", "secondary")
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("예: gildong-hong")
        self.error = kit.para(" ", "caption", "danger")
        self.ok = kit.button("시작", "primary", "l")
        self.ok.setDefault(True)
        self.ok.setEnabled(False)
        box.addWidget(why)
        for widget in (self.edit, self.error):
            box.addWidget(widget)
        self.shell.actions.set_actions([], [self.ok])
        self.shell.fit(640)
        self.edit.textChanged.connect(self.check)
        self.ok.clicked.connect(self.save)

    def check(self, text):
        text = text.strip()
        good = session.valid_user(text)
        self.ok.setEnabled(good)
        self.ok.setText("시작")
        self.asked = ""
        self.say(" " if good or not text else "영문·숫자·-·_ 만 쓸 수 있고, 첫 글자는 영문이나 숫자여야 합니다.")

    def say(self, text):
        """입력칸 아래에 안내를 보여 줌. 안내가 여러 줄로 늘어나면 위의 설명이 눌려 잘리므로 창을 그만큼 키움."""
        self.error.setText(text)
        self.shell.fit(self.width(), self.height())

    def save(self):
        QGuiApplication.inputMethod().commit()
        name = self.edit.text().strip()
        if name != self.asked and session.valid_user(name) and session.has_record(name):  # 남의 ID 를 넣어 그 사람 기록을 이어 쓰지 않게 한 번 물음
            self.asked = name
            self.ok.setText("이 기록으로 시작")
            self.say("이 컴퓨터에 %s 의 풀이 기록이 있습니다. 내 ID 가 맞으면 [이 기록으로 시작]을 눌러 이어서 풉니다. "
                     "다른 사람의 ID 라면 내 ID 로 고쳐 주세요." % session.user_folder(name))
            return
        try:
            user = session.save_user(self.edit.text())
        except (session.SessionError, OSError) as error:
            self.say(str(error))
            return
        self.accept()
        self.on_saved(user)


class ErrorDialog(QDialog):
    """예상하지 못한 오류를 보여 줌. 풀이는 자동 저장돼 있어 창은 계속 쓸 수 있음."""

    def __init__(self, text, log_path, issue_url):
        super().__init__()
        self.setWindowTitle("프로그램 오류")
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)  # 이 창이 남아 있어도 본 창을 닫으면 프로그램이 끝나게
        self.resize(640, 420)
        self.shell = DialogLayout(self, "프로그램에서 오류가 났습니다")
        box = self.shell.content
        from html import escape
        from gui import feedback
        note = kit.typed(LinkLabel("같은 오류가 반복되면 "
                         '<a href="%s">불편 신고 양식</a>에서 환경정보를 확인하고 증상을 적어 주세요. '
                         '<a href="%s">다른 문의 양식</a>도 선택할 수 있습니다.' % (escape(issue_url, quote=True), feedback.CHOOSE_URL),
                         line=theme.TYPE["body"][1], font=theme.font("body")), "body")
        note.setOpenExternalLinks(True)
        self.view = QPlainTextEdit(text)
        self.view.setReadOnly(True)
        where = kit.para("기록 파일: %s" % log_path if log_path else "기록 파일을 쓰지 못했습니다.", "caption", "secondary")
        where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.copy = kit.button("오류 내용 복사", scale="l")
        self.copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.view.toPlainText()))
        close = kit.button("닫기", "primary", "l")
        close.clicked.connect(self.accept)
        box.addWidget(note)
        for widget in (self.view, where):
            box.addWidget(widget)
        self.shell.actions.set_actions([self.copy], [close])
        self.shell.fit(680, 420)

    def append(self, text):
        self.view.appendPlainText("\n" + text)
