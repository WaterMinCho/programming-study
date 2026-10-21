# -*- coding: utf-8 -*-
"""검사 도구 설치 관리 대화상자: 설치 상태 한 줄, 동의 글(무엇을, 어디에, 언제 인터넷이 필요한지, 지우는 법), 설치 진행과 설치 로그 꼬리,
실패했을 때의 이유와 로그 위치, [지우기].

설치와 지우기는 창의 run_job 으로 워커에서 돌리고(node_modules 는 파일 수천 개라 지우는 데도 몇 초 걸림), 진행 알림은 상태 줄에,
로그 파일의 끝 몇 줄은 반초마다 읽어 보여 줌. WebSession.install 이 내는 WebError 는 워커 안에서 받아 결과로 돌려주므로 실패 문구가
이 창 안에 남음. 로그와 결과 글이 나타나면 창 높이를 줄바꿈한 글까지 담게 늘림(fit)."""
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QTextBrowser, QVBoxLayout

import mdlite
import study
from gui import theme
from gui.widgets import Para
from webprep import stack
from webprep.service import WebError

TAIL_LINES = 8  # 보여 주는 설치 로그의 끝 줄 수
TAIL_MS = 500  # 로그를 다시 읽는 간격
CONSENT_HEIGHT = (220, 300)  # 동의 글 상자의 높이 범위. 글이 짧으면 그만큼만, 경로가 길어 넘치면 안에서 스크롤함
CONSENT_WIDTH = 660  # 동의 글의 줄바꿈 높이를 셈할 때 쓰는 글 폭(창 720 에서 여백과 스크롤 막대를 뺀 값)
CONFIRM_REMOVE = "검사 도구(node_modules)를 지웁니다. 미션의 [검사]를 다시 쓰려면 다시 설치해야 합니다. 지울까요?"
BUSY_ELSEWHERE = "다른 작업이 끝난 뒤 다시 눌러 주세요."


def log_tail(path, lines=TAIL_LINES):
    """설치 로그의 끝 몇 줄. 파일이 없으면 빈 글."""
    try:
        text = study.read_text(path)
    except (OSError, UnicodeDecodeError):
        return ""
    return "\n".join(text.rstrip().splitlines()[-lines:])


def consent_html(text):
    """동의 글의 줄마다 문단으로. 명령은 `코드`로 적혀 있어 코드 글꼴로 보임."""
    return mdlite.to_html("\n\n".join(line for line in text.splitlines() if line.strip()))


def stack_line(stack):
    """"Node.js 22.23.2 · 검사 도구 설치됨 (약 80MB)" 같은 한 줄. 설치 상태는 stack.state() 의 값. 웹 홈 머리줄과 허브의 웹 카드,
    미션 정보도 이 줄을 씀."""
    node = stack.get("node")
    parts = ["Node.js %s" % node["version"] if node else "Node.js 없음"]
    if stack.get("installed"):
        parts.append("검사 도구 설치됨 (약 %dMB)" % stack.get("size_mb", 0))
        if stack.get("stale"):
            parts.append("다시 설치 필요")
    else:
        parts.append("검사 도구 설치 전")
    return " · ".join(parts)


def stack_text(state):
    """상태 줄. Node 판과 설치 여부를 한 줄로, 문제가 있으면 그 안내를 다음 줄에. 경로는 동의 글의 '어디에'와 '쓰는 Node.js'에만 적음."""
    text = stack_line(state)
    if state["problem"]:
        text += "\n" + state["problem"]
    return text


class SetupDialog(QDialog):
    def __init__(self, win, on_change=None):
        super().__init__(win)
        self.win, self.on_change = win, on_change
        self.setWindowTitle("검사 도구 설치 관리")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.busy = False  # 설치나 지우기가 도는 중. 그동안 단추를 끄고 창을 닫지 않음
        box = QVBoxLayout(self)
        box.setContentsMargins(22, 20, 22, 16)
        box.setSpacing(12)
        head = QLabel("검사 도구 설치 관리")
        head.setObjectName("h2")
        self.state = Para()
        self.state.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.consent = QTextBrowser()
        self.consent.setOpenLinks(False)
        self.consent.document().setDocumentMargin(12)
        self.status = Para(name="muted")
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.hide()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(theme.code_font(-2))
        self.log.setFixedHeight(QFontMetrics(self.log.font()).lineSpacing() * TAIL_LINES + 14)  # 꼬리 줄 수만큼. 동의 글과 높이를 다투지 않음
        self.log.hide()
        self.result = Para()
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.result.hide()
        for widget in (head, self.state, self.consent):
            box.addWidget(widget)
        box.addSpacing(4)  # 동의 글 상자의 테두리와 상태 줄 사이
        for widget in (self.status, self.busy_bar, self.log, self.result):
            box.addWidget(widget)
        row = QHBoxLayout()
        self.remove_btn = QPushButton("지우기")
        self.close_btn = QPushButton("닫기")
        self.install_btn = QPushButton("설치")
        self.install_btn.setObjectName("primary")
        row.addWidget(self.remove_btn)
        row.addStretch(1)
        row.addWidget(self.close_btn)
        row.addWidget(self.install_btn)
        box.addLayout(row)
        self.tail_timer = QTimer(self)
        self.tail_timer.setInterval(TAIL_MS)
        self.tail_timer.timeout.connect(self.show_tail)
        self.remove_btn.clicked.connect(self.ask_remove)
        self.close_btn.clicked.connect(self.close)
        self.install_btn.clicked.connect(self.install)
        self.refresh()
        self.resize(720, self.sizeHint().height())

    def refresh(self):
        """설치 상태와 동의 글을 다시 읽음."""
        web = self.win.web
        state = web.stack_state()
        self.state.setText(stack_text(state))
        document = self.consent.document()
        document.setDefaultStyleSheet(theme.doc_css(self.win.zoom))
        self.consent.setHtml(consent_html(web.consent()))
        document.setTextWidth(CONSENT_WIDTH)
        low, high = CONSENT_HEIGHT
        self.consent.setMinimumHeight(max(low, min(high, int(document.size().height()) + 4)))
        self.install_btn.setText("다시 설치" if state["installed"] else "설치")
        self.install_btn.setEnabled(state["node"] is not None and not self.busy)
        self.install_btn.setToolTip("" if state["node"] else state["problem"])
        self.remove_btn.setEnabled(state["installed"] and not self.busy)

    def fit(self):
        """로그·진행 막대·결과 글이 나타난 뒤 창 높이를 레이아웃이 줄바꿈까지 셈한 높이에 맞춤. 줄어들지는 않음."""
        layout = self.layout()
        layout.activate()
        need = layout.totalHeightForWidth(self.width()) if layout.hasHeightForWidth() else layout.totalSizeHint().height()
        if need > self.height():
            self.resize(self.width(), need)

    def lock(self, text):
        """설치나 지우기를 시작함. 결과 글을 치우고 단추를 끄고 상태 줄에 text 를 보임."""
        self.busy = True
        self.result.hide()
        self.busy_bar.show()
        self.status.setText(text)
        for button in (self.install_btn, self.remove_btn, self.close_btn):
            button.setEnabled(False)

    def _done(self):
        """설치나 지우기가 끝남. 단추를 되돌리고 상태를 다시 읽음."""
        self.busy = False
        self.tail_timer.stop()
        self.busy_bar.hide()
        self.status.setText("")
        self.close_btn.setEnabled(True)
        self.refresh()
        if self.on_change:
            self.on_change()

    def _refused(self):
        """run_job 이 다른 일 때문에 시작하지 못함."""
        self._done()
        self.status.setText(BUSY_ELSEWHERE)

    # 설치

    def install(self):
        if self.busy:
            return
        web = self.win.web
        self.log.setPlainText("")
        self.log.show()
        self.lock("검사 도구를 설치하는 중입니다.")

        def work(report, cancel):
            try:
                return web.install(report=lambda text: report({"kind": "status", "text": text}))
            except WebError as error:
                return {"ok": False, "message": str(error), "log": stack.log_path()}

        if self.win.run_job("검사 도구를 설치하는 중입니다.", work, self._installed, on_fail=self._failed, on_progress=self._progress):
            self.tail_timer.start()
        else:
            self._refused()
        self.fit()

    def _progress(self, event):
        if event.get("kind") == "status":
            self.status.setText(event["text"])
            self.fit()

    def show_tail(self):
        tail = log_tail(stack.log_path())
        if tail != self.log.toPlainText():
            self.log.setPlainText(tail)
            bar = self.log.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _installed(self, result):
        self._done()
        self.show_tail()
        if result.get("ok"):
            self.log.hide()
            self.say(result.get("message") or "검사 도구를 설치했습니다.", "")
            return
        log = result.get("log") or stack.log_path()
        text = result.get("message") or "설치가 실패했습니다."
        if log and log not in text:
            text += "\n설치 로그: %s" % log
        self.say(text, "error")

    def _failed(self):
        self._done()
        self.show_tail()
        self.say("설치 도중 프로그램 오류가 났습니다. 설치 로그: %s" % stack.log_path(), "error")

    def say(self, text, name):
        self.result.setObjectName(name)
        self.result.style().unpolish(self.result)
        self.result.style().polish(self.result)
        self.result.setText(text)
        self.result.show()
        self.fit()

    # 지우기

    def ask_remove(self):
        self.win.ask("검사 도구 지우기", CONFIRM_REMOVE, (("지우기", "remove"), ("취소", "")), lambda key: self.remove())

    def remove(self):
        if self.busy:
            return
        self.log.hide()
        self.lock("검사 도구를 지우는 중입니다.")
        if not self.win.run_job("검사 도구를 지우는 중입니다.", self.win.web.uninstall, self._removed):
            self._refused()

    def _removed(self, result):
        self._done()
        removed = result["removed"]
        self.say("지웠습니다: %s" % ", ".join(os.path.basename(p) for p in removed) if removed else "지울 것이 없습니다.", "")

    def closeEvent(self, event):
        if self.busy:  # 설치나 지우기가 끝나기 전에는 닫지 않음. 창을 닫아도 일은 계속 돌기 때문임
            event.ignore()
            return
        self.tail_timer.stop()
        event.accept()
