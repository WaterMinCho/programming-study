# -*- coding: utf-8 -*-
"""검사 도구 설치 관리 대화상자: 상태 한 문장과 꼬리표, 설치 진행과 설치 로그 꼬리, 결과 띠(완료·오류), [자세히] [닫기] [설치하기].
동의 글(무엇을, 어디에, 언제 인터넷이 필요한지, 지우는 법, 로그 위치, Node 판)과 설치된 상태의 [다시 설치하기] [지우기]는 [자세히] 안에 둠.

설치와 지우기는 창의 run_job 으로 워커에서 돌리고(node_modules 는 파일 수천 개라 지우는 데도 몇 초 걸림), 진행 알림은 상태 줄에,
로그 파일의 끝 몇 줄은 반초마다 읽어 보여 줌. WebSession.install 이 내는 WebError 는 워커 안에서 받아 결과로 돌려주므로 실패 문구가
이 창 안에 남음. 로그 칸은 설치를 시작할 때 한 번 나타나 설치가 끝나도 남으므로 설치 중과 실패 뒤의 창 높이가 거의 같음.
설치가 끝난 상태에서는 주 단추가 없고 [닫기]만 있음."""
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QTextBrowser, QWidget

import mdlite
import study
from gui import kit, theme
from gui.web_text import gui_text
from webprep import stack
from webprep.service import WebError

TAIL_LINES = 8  # 보여 주는 설치 로그의 끝 줄 수
TAIL_MS = 500  # 로그를 다시 읽는 간격
CONSENT_HEIGHT = (200, 280)  # 동의 글 상자의 높이 범위. 글이 짧으면 그만큼만, 경로가 길어 넘치면 안에서 스크롤함
WIDTH = 560  # 대화상자 폭(설계 5.14 의 최대). 경로가 긴 동의 글이 들어가야 함
CONFIRM_REMOVE = "검사 도구(node_modules)를 지웁니다. 미션의 [검사하기]를 다시 쓰려면 다시 설치해야 합니다."
BUSY_ELSEWHERE = "다른 작업이 끝난 뒤 다시 눌러 주세요."
FAILED = "검사 도구를 설치하지 못했습니다. 인터넷 연결을 확인한 뒤 다시 설치하세요."


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


def state_sentence(state):
    """창 맨 위의 상태 한 문장. Node 나 lockfile 이 없으면 그 안내. Node 판과 경로는 [자세히] 안의 동의 글에만 적음."""
    if not state["node"] or not state["lock"]:
        return gui_text(state["problem"])
    if state["installed"]:
        return "패키지 목록이 바뀌어 검사 도구를 다시 설치해야 합니다." if state.get("stale") else "검사 도구가 설치되어 있어 미션의 [검사하기]를 쓸 수 있습니다."
    return "검사 도구 약 %dMB 를 이 컴퓨터에 설치합니다. 처음 설치할 때 한 번 인터넷이 필요합니다." % stack.SIZE_MB


def stack_badge(state):
    """상태 꼬리표의 (글, 색)."""
    if not state["node"]:
        return "Node.js 없음", "danger"
    if state["installed"]:
        return ("다시 설치 필요", "warning") if state.get("stale") else ("설치됨", "success")
    return "설치 전", ""


class SetupDialog(QDialog):
    def __init__(self, win, on_change=None):
        super().__init__(win)
        kit.page(self)
        self.win, self.on_change = win, on_change
        self.setWindowTitle("검사 도구 설치 관리")
        self.setModal(True)
        self.setFixedWidth(WIDTH)
        self.busy = False  # 설치나 지우기가 도는 중. 그동안 단추를 끄고 창을 닫지 않음
        box = kit.box(self, (32, 32, 32, 24))
        head_row = QHBoxLayout()
        head_row.setSpacing(12)
        head_row.addWidget(kit.label("검사 도구 설치 관리", "headline"))
        self.badge = kit.badge("")
        head_row.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        head_row.addStretch(1)
        box.addLayout(head_row)
        box.addSpacing(12)
        self.state = kit.para("")
        self.state.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.state)
        self.details = QWidget()  # [자세히]: 동의 글과 설치된 상태의 [다시 설치하기] [지우기]
        details_box = kit.box(self.details, (0, 16, 0, 0), 8)
        self.consent = QTextBrowser()
        self.consent.setObjectName("plain")
        self.consent.setOpenLinks(False)
        self.consent.document().setDocumentMargin(0)
        details_box.addWidget(self.consent)
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.again_btn = kit.button("다시 설치하기", "text", "l")  # 설치돼 있을 때 주 단추 대신 글자 단추로 둠
        self.remove_btn = kit.button("지우기", "danger_text", "l")
        tools.addWidget(self.again_btn)
        tools.addWidget(self.remove_btn)
        tools.addStretch(1)
        details_box.addLayout(tools)
        self.details.hide()
        box.addWidget(self.details)
        self.work = QWidget()  # 진행 줄, 진행 막대, 로그 꼬리, 결과 띠. 모두 숨으면 이 묶음도 숨겨 본문과 단추 사이를 32 로 둠
        work_box = kit.box(self.work, (0, 16, 0, 0), 8)
        self.status = kit.label("", "caption", "secondary")
        self.status.hide()
        self.busy_bar = kit.progress(thin=True)
        self.busy_bar.setRange(0, 0)
        self.busy_bar.hide()
        self.log = QPlainTextEdit()
        self.log.setObjectName("plain")
        self.log.setReadOnly(True)
        self.log.setFont(theme.code_font(-1))
        self.log.setFixedHeight(QFontMetrics(self.log.font()).lineSpacing() * TAIL_LINES + 8)  # 꼬리 줄 수만큼
        self.log.hide()
        self.result = kit.banner("", "success")
        self.result.hide()
        for widget in (self.status, self.busy_bar, self.log, self.result):
            work_box.addWidget(widget)
        self.work.hide()
        box.addWidget(self.work)
        box.addSpacing(32)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.more_btn = kit.button("자세히", "text", "l")
        self.close_btn = kit.button("닫기", "secondary", "l")
        self.install_btn = kit.button("설치하기", "primary", "l")
        row.addWidget(self.more_btn)
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
        self.again_btn.clicked.connect(self.install)
        self.more_btn.clicked.connect(lambda: (self.details.setVisible(self.details.isHidden()), self.fit()))
        self.failed = False  # 마지막 설치가 실패했는지. 실패하면 [다시 설치하기]가 주 단추로 나옴
        self.refresh()
        self.fit()

    def refresh(self):
        """설치 상태와 동의 글을 다시 읽음."""
        web = self.win.web
        state = web.stack_state()
        self.state.setText(state_sentence(state))
        text, tone = stack_badge(state)
        self.badge.setText(text)
        kit.set_tone(self.badge, tone)
        document = self.consent.document()
        document.setDefaultStyleSheet(theme.web_css(self.win.zoom))
        self.consent.setHtml(consent_html(gui_text(web.consent())))
        document.setTextWidth(WIDTH - 64 - 16)
        low, high = CONSENT_HEIGHT
        self.consent.setFixedHeight(max(low, min(high, int(document.size().height()) + 4)))
        installed = state["installed"] and not state.get("stale")
        self.install_btn.setText("다시 설치하기" if state["installed"] or self.failed else "설치하기")
        self.install_btn.setVisible(not installed or self.failed)  # 설치된 상태에서는 주 단추 없이 [닫기]만
        self.again_btn.setVisible(installed and not self.failed)
        for button in (self.install_btn, self.again_btn):
            button.setEnabled(state["node"] is not None and not self.busy)
            button.setToolTip("" if state["node"] else gui_text(state["problem"]))
        self.remove_btn.setVisible(bool(state["installed"]))
        self.remove_btn.setEnabled(state["installed"] and not self.busy)

    def fit(self):
        """보이는 것이 바뀐 뒤 창 높이를 레이아웃이 줄바꿈까지 셈한 높이에 맞춤. 진행 묶음은 안에 보이는 것이 있을 때만 보임."""
        self.work.setVisible(any(not widget.isHidden() for widget in (self.status, self.busy_bar, self.log, self.result)))
        layout = self.layout()
        layout.invalidate()
        layout.activate()
        need = layout.totalHeightForWidth(WIDTH) if layout.hasHeightForWidth() else layout.totalSizeHint().height()
        self.resize(WIDTH, need)

    def lock(self, text):
        """설치나 지우기를 시작함. 결과 띠를 치우고 단추를 끄고 상태 줄에 text 를 보임."""
        self.busy = True
        self.result.hide()
        self.busy_bar.show()
        self.status.setText(text)
        self.status.show()
        for button in (self.install_btn, self.again_btn, self.remove_btn, self.close_btn):
            button.setEnabled(False)

    def _done(self):
        """설치나 지우기가 끝남. 단추를 되돌리고 상태를 다시 읽음."""
        self.busy = False
        self.tail_timer.stop()
        self.busy_bar.hide()
        self.status.setText("")
        self.status.hide()
        self.close_btn.setEnabled(True)
        self.refresh()
        if self.on_change:
            self.on_change()

    def _refused(self):
        """run_job 이 다른 일 때문에 시작하지 못함."""
        self._done()
        self.status.setText(BUSY_ELSEWHERE)
        self.status.show()
        self.fit()

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

        self.fit()  # 로그 칸이 여기서 한 번 나타나고 설치가 끝나도 남음
        if self.win.run_job("검사 도구를 설치하는 중입니다.", work, self._installed, on_fail=self._failed, on_progress=self._progress):
            self.tail_timer.start()
        else:
            self._refused()

    def _progress(self, event):
        if event.get("kind") == "status":
            self.status.setText(event["text"])

    def show_tail(self):
        tail = log_tail(stack.log_path())
        if tail != self.log.toPlainText():
            self.log.setPlainText(tail)
            bar = self.log.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _installed(self, result):
        self.failed = not result.get("ok")
        self._done()
        self.show_tail()
        if result.get("ok"):
            self.say(result.get("message") or "검사 도구를 설치했습니다.", "")
            return
        log = result.get("log") or stack.log_path()
        text = result.get("message") or FAILED
        if log and log not in text:
            text += "\n설치 로그: %s" % log
        self.say(text, "error")

    def _failed(self):
        self.failed = True
        self._done()
        self.show_tail()
        self.say("설치 도중 프로그램 오류가 났습니다. 설치 로그: %s" % stack.log_path(), "error")

    def say(self, text, name):
        """결과 띠에 글을 보임. name 이 error 면 오류 띠, 아니면 완료 띠."""
        tone = "danger" if name == "error" else "success"
        kit.set_tone(self.result, tone)
        self.result.word.setText("오류" if name == "error" else "완료")
        self.result.text.setText(text)
        self.result.show()
        self.fit()

    # 지우기

    def ask_remove(self):
        self.win.ask("검사 도구 지우기", CONFIRM_REMOVE, (("지우기", "remove", "danger"), ("닫기", "")), lambda key: self.remove())

    def remove(self):
        if self.busy:
            return
        self.log.hide()
        self.lock("검사 도구를 지우는 중입니다.")
        self.fit()
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
