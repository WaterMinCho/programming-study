# -*- coding: utf-8 -*-
"""알고리즘 여행의 문제 화면(작업 틀): 위 막대(← 알고리즘 여행 · 문제 이름 · 역할 꼬리표 · 번호 · 상태 / 풀이 언어 칩) ·
왼쪽 지문 카드(문제·힌트·해설 탭) · 오른쪽 편집기와 결과 카드 · 아래 막대(코드 되돌리기, 테스트 추가 / 코드 실행, 채점하기).

두 칸과 편집기·결과 카드 사이는 사람이 끌 수 있는 칸 나누기이고 끈 몫을 설정에 기억함. 결과가 아직 없으면 결과 카드를 머리만 남기고 접어
편집기를 키우고, 처음 [코드 실행]·[채점하기]를 누르는 순간 기억한 몫으로 펼침. 지문 카드는 읽는 글의 단 폭(kit.doc_width)보다 넓어지지 않음.
코드는 입력이 멈추고 SAVE_DELAY_MS 뒤에 서비스로 저장함(Ctrl+S 는 바로). 실행·채점은 창의 run_job 으로 워커에서 돌림.
진행 알림(report)이 올 때마다 결과 카드 본문에 줄을 하나씩 붙임. 마지막 결과는 (문제, 언어)마다 dict 로 두어 다른 문제를 갔다 오거나
테마·글자 크기가 바뀌어도 다시 그림. 같은 실행 안에서 다시 연 문제는 떠날 때의 탭과 읽던 자리로 돌아옴.
이 화면 안에서는 복사·붙여넣기가 됨(clipboard 속성을 gui/guard.py 가 봄). 파이썬 스터디의 회차 화면은 지금처럼 막힘.
언어 칩과 Node.js 가 없을 때의 대화상자는 지도(gui/journey_map.py)도 같이 씀."""
import datetime
import html
import math
import re
import time

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QGuiApplication, QKeySequence, QShortcut, QTextCursor
from PyQt6.QtWidgets import QButtonGroup, QSizePolicy, QStackedWidget, QWidget

from gui import kit, motion, theme
from gui.cases_dialog import CasesDialog
from gui.docview import PAD, DocView
from gui.editor import LANGS, CodeEditor, FindBar
from gui.journey_result import JourneyResult
from gui.journey_text import (EXPLAIN_LOCKED, HINT_INTRO, LANG_LABEL, NO_HINT, SAVE_FAILED, SAVED, SIDE_NOTE, clear_text, error_text,
                              fact_line, item_line, next_item, number_text, tier_tip, uses_text)
from gui.widgets import LinkLabel
from journey.node import MIN_MAJOR
from journey.service import NO_NODE, JourneyError
from session import SessionError

SAVE_DELAY_MS = 400  # 입력이 멈춘 뒤 자동 저장까지
SITE_LABEL = {"boj": "백준", "programmers": "프로그래머스"}
NODE_TITLE = "Node.js 찾기"
NODE_BUSY = "Node.js 찾는 중"  # node 를 찾거나 고른 파일을 확인하는 동안 화면 위 막대에 보이는 글
NODE_TEXT = ("JavaScript 로 풀려면 Node.js %d 이상이 필요합니다. 설치한 뒤 [다시 찾기]를 누르고, 설치했는데 찾지 못하면 "
             "[직접 고르기]로 node 실행 파일을 고르세요." % MIN_MAJOR)
NODE_LINK = "https://nodejs.org"  # Node 창 본문 아래에 누를 수 있는 주소로 보임
NODE_MISSING = "Node.js 를 찾지 못했습니다."  # [다시 찾기]로도 찾지 못했을 때 Node 창 본문 앞에 붙는 문장
NODE_RETRY = "새 Node.js 를 설치한 뒤 [다시 찾기]를 누르세요. 이미 설치했다면 [직접 고르기]로 그 node 실행 파일을 고르세요."  # 고른 파일을 쓸 수 없을 때 그 까닭 뒤
GIVE_UP_TITLE = "해설 먼저 보기"
GIVE_UP_TEXT = "아직 통과하지 않은 문제입니다. 해설을 열면 기록에 남고, 나중에 통과해도 목록에 '해설 보고 통과'로 보입니다."
RESET_TITLE = "코드 되돌리기"
RESET_TEXT = "지금 코드를 지우고 시작 코드로 바꿉니다. 바로 뒤라면 편집기에서 Ctrl+Z(맥은 Cmd+Z)로 되살릴 수 있습니다."
CLEAR_TITLE = "던전 클리어"
RUN_TIP = "입출력 예와 내 테스트로 돌려 봅니다. 기록에 남지 않습니다. (Ctrl+Enter, 맥은 Cmd+Enter)"
GRADE_TIP = "숨은 테스트까지 채점합니다. 결과는 기록에 남습니다. (Ctrl+Shift+Enter, 맥은 Cmd+Shift+Enter)"
RUN_BUSY, GRADE_BUSY = "코드 실행 중", "채점 중"  # 실행·채점을 맡길 때 창에 넘기는 일 이름. 진행은 결과 카드 머리가 보이므로 위 막대에 쓰지 않음
ESCAPE_NOTE = "Esc 를 누르면 편집기 밖으로 나갑니다."
EDITOR_LINES = 6  # 편집기 최소 높이의 줄 수. 보통 글자(16px)에서 120
PANE_GAP = 16  # 저장 실패 띠와 편집기 사이
RESULT_SPLIT = 340 / 608  # 펼친 결과 카드에서 편집기가 받는 처음 몫(1280×800 에서 편집기 331, 결과 카드 261)
TITLE_MIN, TITLE_CAP = 120, 260  # 위 막대 문제 이름의 가장 좁은 폭과 다 보이는 상한(보통 headline 22px 기준, 글자에 비례)
STATUS_LOW, STATUS_MAX = 120, 420  # 위 막대 상태 글의 하한(보통 caption 14px 기준, 글자에 비례)과 상한. 넘으면 두 줄
STATUS_GAP = 4  # 번호와 상태 글 사이를 막대 간격 12 에 더해 16 으로 둠
SAVE_ERROR = "코드를 저장하지 못했습니다"  # 저장 실패를 창으로 알릴 때의 첫 문장. 서비스 문구도 이것으로 시작함


def saved_lang(settings):
    """지도와 문제 화면이 같이 쓰는 언어 설정(QSettings journey/lang). 모르는 값이면 python."""
    lang = settings.value("journey/lang", "python", type=str)
    return lang if lang in LANG_LABEL else "python"


def node_ready(win):
    """JavaScript 로 풀 수 있는지. 서비스가 처음 찾은 결과를 프로세스 안에서 기억함.
    처음 찾기는 창이 지도·문제 화면을 열기 전이나 with_node 에서 워커로 해 두므로, 여기서는 기억한 결과만 읽음."""
    return bool(win.journey.runtime("javascript")["ok"])


def with_node(win, then):
    """then(JavaScript 로 풀 수 있는지)을 부름. 아직 node 를 찾아 보지 않았으면 찾기와 버전 확인을 워커에서 한 뒤에 부름.
    느린 node 후보(백신이 잡은 첫 실행, 멈춘 심)가 있어도 화면이 멈추지 않음."""
    if win.journey.node_checked():
        then(node_ready(win))
        return
    win.run_job(NODE_BUSY, lambda: win.journey.runtime("javascript"), lambda info: then(bool(info["ok"])))


class Failed:
    """워커에서 난 SessionError 의 문구. caught 로 감싼 일은 오류를 내는 대신 이것을 결과로 돌려줌."""

    def __init__(self, message):
        self.message = message


def caught(fn):
    """워커에서 도는 fn 이 SessionError 를 내면 Failed(문구)를 돌려주게 감쌈. 창의 run_job 은 그 오류를 "알림" 창으로 보임.
    여행 화면은 하던 행동의 이름을 제목으로 한 창(error_text)이나 Node 창으로 보이려고 결과로 받아 화면 스레드에서 다룸."""

    def run(*args):
        try:
            return fn(*args)
        except SessionError as error:
            return Failed(str(error))

    return run


def ask_node(win, on_ready, first=""):
    """Node.js 찾기 창. 오른쪽 끝 주 단추 [다시 찾기], 그 왼쪽 [닫기], 주 단추와 가장 먼 [직접 고르기] 순서이고 본문 아래에 내려받는 주소가 있음.
    두 행동으로 node 를 찾으면 on_ready() 를 부름. 찾지 못하면 그 까닭(first)을 본문 앞에 붙여 같은 창을 다시 띄움. 찾기와 확인은 워커에서 함.
    고른 파일을 쓸 수 없으면 검사기가 까닭에 필요한 버전을 이미 말하므로 뒤에는 짧은 안내(NODE_RETRY)만 붙임."""

    def found(info):
        if isinstance(info, Failed):  # 고른 파일이 node 가 아니거나 버전이 낮음
            ask_node(win, on_ready, info.message)
        elif info.get("ok"):
            on_ready()
        else:
            ask_node(win, on_ready, NODE_MISSING)

    def choose(key):
        if key == "find":
            win.run_job(NODE_BUSY, lambda: win.journey.find_node(probe=True), found)
            return
        path = win.pick_file("node 실행 파일 고르기")
        if not path:
            return

        def checked(info):
            if not isinstance(info, Failed):
                win.settings.setValue("journey/node", path)
            found(info)

        win.run_job(NODE_BUSY, caught(lambda: win.journey.set_node(path)), checked)

    if not first:
        text = NODE_TEXT
    else:
        text = "%s %s" % (first, NODE_TEXT if first == NODE_MISSING else NODE_RETRY)
    return win.ask(NODE_TITLE, text, (("다시 찾기", "find", "primary"), ("닫기", ""), ("직접 고르기", "pick", "close")), choose, link=NODE_LINK)


class LangChips(QWidget):
    """풀이 언어 칩 두 개와 "Node.js 필요" 글자. 누르면 picked(언어)를 내고, 고른 언어는 부른 쪽이 set_lang 으로 표시함.
    칩은 누르는 순간 체크가 옮겨 가므로 Node.js 가 없어 거절할 때는 부른 쪽이 set_lang(지금 언어)로 되돌림.
    onbg 면 회색 바탕 위의 칩(지도 위 막대)이고 앞에 "풀이 언어" 이름표를 둠. 칩의 최소 폭은 글자 폭(fit)이라 좁은 막대에서도 글자가 잘리지 않음."""
    picked = pyqtSignal(str)

    def __init__(self, onbg=False, parent=None):
        super().__init__(parent)
        row = kit.box(self, spacing=8, horizontal=True)
        if onbg:
            row.addWidget(kit.label("풀이 언어", "caption", "tertiary"))
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for lang, text in LANG_LABEL.items():
            chip = kit.chip(text, lang, onbg)
            chip.clicked.connect(lambda checked=False, lang=lang: self.picked.emit(lang))
            self.group.addButton(chip)
            row.addWidget(chip)
            self.buttons[lang] = chip
        self.note = kit.label("Node.js 필요", "caption", "tertiary")
        self.note.setToolTip("JavaScript 로 풀려면 Node.js %d 이상이 필요합니다." % MIN_MAJOR)
        self.note.hide()
        row.addWidget(self.note)
        self.lang = ""

    def set_lang(self, lang):
        """고른 언어의 칩을 고른 모양으로 둠."""
        self.lang = lang
        for name, chip in self.buttons.items():
            chip.setChecked(name == lang)

    def fit(self):
        """칩마다 최소 폭을 지금 글자의 폭으로 묶음. 글자 크기 단계가 바뀌면 화면의 restyle 이 다시 부름."""
        for chip in self.buttons.values():
            pin(chip)

    def showEvent(self, event):
        super().showEvent(event)
        self.fit()


def pin(widget):
    """최소 폭을 지금 글자의 sizeHint 폭으로 묶음. 막대가 좁을 때 Qt 가 단추를 스타일시트의 min-width 까지 줄여 글자가 잘리지 않게 함."""
    widget.setMinimumWidth(0)
    widget.ensurePolished()
    widget.setMinimumWidth(widget.sizeHint().width())


def md_text(text):
    """마크다운 문단에 넣을 꾸밈없는 글. 인라인 꾸밈 글자를 글자 그대로 보이게 막음."""
    return re.sub(r"([\\`*_])", r"\\\1", text)


def similar_text(item):
    """"백준 1000 · A+B", "프로그래머스 · K번째수"."""
    site = SITE_LABEL.get(item.get("site"), item.get("site") or "")
    number = " %s" % item["id"] if item.get("id") else ""
    return "%s%s · %s" % (site, number, item.get("title") or "")


def text_width(widget, text):
    return math.ceil(QFontMetricsF(widget.font()).horizontalAdvance(text)) if text else 0


class TabBarStack(QWidget):
    """지문 카드의 탭 막대(kit.TabBar)와 그 아래 쌓인 칸. QTabWidget 처럼 tabText·setTabText·setCurrentIndex·currentIndex·currentChanged 를 씀."""
    currentChanged = pyqtSignal(int)

    def __init__(self, names, pages):
        super().__init__()
        box = kit.box(self)
        self.bar = kit.TabBar(names)
        self.stack = QStackedWidget()
        for page in pages:
            self.stack.addWidget(page)
        box.addWidget(self.bar)
        box.addWidget(self.stack, 1)
        self.bar.picked.connect(self.setCurrentIndex)

    def tabText(self, number):
        return self.bar.buttons[number].text()

    def setTabText(self, number, text):
        self.bar.buttons[number].setText(text)

    def currentIndex(self):
        return self.stack.currentIndex()

    def setCurrentIndex(self, number):
        self.bar.set_current(number)
        if number != self.stack.currentIndex():
            self.stack.setCurrentIndex(number)
            self.currentChanged.emit(number)

    def focus_tab(self):
        """고른 탭으로 키보드 초점을 옮김(편집기에서 Esc)."""
        self.bar.buttons[self.currentIndex()].setFocus(Qt.FocusReason.ShortcutFocusReason)


class PrepLink(LinkLabel):
    """지문 머리의 준비 문제 링크. Para 는 마지막 줄 아래 줄 간격을 높이에서 빼는데, 링크 밑줄이 그 자리에 그려져 잘리므로 빼지 않음.
    실행·채점 중에 꺼지면 링크 대신 밑줄 없는 faint 색 글로 그려 누를 수 있어 보이지 않게 함."""

    def __init__(self, pid, text):
        super().__init__("", line=theme.TYPE["caption"][1], font=theme.font("caption"))
        self.pid, self.label = pid, text
        self.setText(self.shown())

    def shown(self):
        if self.isEnabled():
            return '<a href="%s">%s</a>' % (html.escape(self.pid), html.escape(self.label))
        return '<span style="color: %s;">%s</span>' % (theme.color("faint"), html.escape(self.label))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.EnabledChange, QEvent.Type.PaletteChange) and hasattr(self, "pid") and self.text() != self.shown():
            self.setText(self.shown())

    def tail(self):
        return 0


class FactLine(QWidget):
    """문제 탭 맨 위의 지문 머리(DocView.set_head). caption secondary 줄 하나나 둘, 줄 사이 4.
    첫 줄은 난이도와 지금 언어의 시간 제한, 둘째 줄은 역할마다 다름: 보스는 이 보스에 쓰는 앞 문제, 선택 문제는 보스와 상관없다는 말,
    중급은 준비 문제 링크와 통과 꼬리표. 링크를 누르면 opened(문제 id)를 냄. text() 는 보이는 글을 이은 것(시험용)."""
    opened = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        box = kit.box(self, spacing=4)
        self.first = kit.para("", "caption", "secondary")
        self.second = QWidget()
        self.second_box = kit.box(self.second, spacing=8, horizontal=True)
        box.addWidget(self.first)
        box.addWidget(self.second)
        self.links = []

    def set_problem(self, data, lang):
        self.first.setText(fact_line(data, lang))
        self.first.setToolTip(tier_tip(data["tier"]))
        while self.second_box.count():
            item = self.second_box.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self.links = []
        role = data["role"]
        if role == "boss":
            self.second_box.addWidget(kit.para(uses_text(data["uses"]), "caption", "secondary"), 1)
        elif role == "side":
            self.second_box.addWidget(kit.para(SIDE_NOTE, "caption", "secondary"), 1)
        elif data["prep"]:
            self.second_box.addWidget(kit.label("준비 문제", "caption", "secondary"))
            for ref in data["prep"]:
                link = kit.typed(PrepLink(ref["pid"], "%s %s" % (ref["no"], ref["title"])), "caption")
                link.linkActivated.connect(self.opened.emit)
                self.links.append(link)
                self.second_box.addWidget(link)
                if ref["passed"]:
                    self.second_box.addWidget(kit.badge("통과", "success"))
            self.second_box.addStretch(1)
        self.second.setVisible(self.second_box.count() > 0)

    def text(self):
        parts = [self.first.text()]
        for index in range(self.second_box.count()):
            widget = self.second_box.itemAt(index).widget()
            if widget is not None:
                parts.append(re.sub(r"<[^>]+>", "", widget.text()))
        return " ".join(part for part in parts if part)


class JourneyCodePanel(QWidget):
    """오른쪽 칸: 편집기(위에 저장 실패 띠)와 결과 카드를 세로 칸 나누기(손잡이 16)로 나눔. 옮긴 몫은 설정 journey/split_v 에 남음.
    collapse 는 결과 카드를 머리 높이로 묶고 손잡이를 잠그며, expand 는 묶음을 풀고 기억한 몫으로 나눔.
    글이 달라졌을 때만 changed(글)를 냄. 문법 색칠을 다시 하면 글이 같아도 textChanged 가 나옴."""
    changed = pyqtSignal(object)

    def __init__(self, settings=None):
        super().__init__()
        box = kit.box(self)
        self.split = kit.splitter(Qt.Orientation.Vertical, "journey/split_v", RESULT_SPLIT, 16, settings)
        self.editor_pane = QWidget()  # 찾기 막대도 여기에 떠서 실행·채점 중에 편집기를 잠가도 쓰임
        pane_box = kit.box(self.editor_pane, spacing=PANE_GAP)
        self.save_banner = kit.banner(SAVE_FAILED, "danger")
        self.save_banner.hide()
        self.editor = CodeEditor(paste=True)
        self.editor.setAccessibleDescription(ESCAPE_NOTE)
        pane_box.addWidget(self.save_banner)
        pane_box.addWidget(self.editor, 1)
        self.result = JourneyResult()
        self.split.addWidget(self.editor_pane)
        self.split.addWidget(self.result)
        box.addWidget(self.split)
        self.reset_btn = None  # 아래 막대의 [코드 되돌리기]. 문제 화면이 넣음
        self.code = ""  # 바로 앞에 알린 글
        self.editor.textChanged.connect(self._edited)
        self.collapse()  # 문제를 열기 전에도 접어 둠. 펼친 카드의 최소 높이가 창의 최소 높이에 들지 않음
        self.refit()

    def set_code(self, text):
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self.code = self.editor.toPlainText()

    def _edited(self):
        text = self.editor.toPlainText()
        if text != self.code:
            self.code = text
            self.changed.emit(text)

    def focus_input(self):
        self.editor.setFocus()

    def show_save_error(self, message):
        """편집기 위에 저장 실패 띠를 보이고 원문은 띠 도움말에 둠."""
        self.save_banner.setToolTip(message)
        if self.save_banner.isHidden():
            self.save_banner.show()
            self.fit_editor()

    def hide_save_error(self):
        if not self.save_banner.isHidden():
            self.save_banner.hide()
            self.fit_editor()

    def collapse(self):
        """결과 카드를 머리 글만 남은 높이로 묶고 손잡이를 잠금. 남는 높이는 편집기가 받음."""
        self.result.set_collapsed(True)
        self.split.set_locked(True)

    def expand(self):
        """묶음을 풀고 기억한 몫으로 나눔. 줄어든 편집기에서 커서 줄이 가려지지 않게 함."""
        if not self.result.collapsed:
            return
        self.result.set_collapsed(False)
        self.split.set_locked(False)
        self.split.place()
        QTimer.singleShot(0, self.editor.ensureCursorVisible)

    def refit(self):
        """글자 크기 단계에 따라 편집기와 결과 카드의 최소 높이, 접힌 카드의 높이를 다시 잡음. 결과 카드는 머리가 눌리지 않는 높이까지만
        줄어듦."""
        self.fit_editor()
        self.result.fit_height()

    def fit_editor(self):
        """편집기의 최소 높이. 평소에는 EDITOR_LINES 줄 남짓이고, 저장 실패 띠가 보이면 띠와 그 아래 간격만큼 빼되 한 줄은 남김.
        띠가 칸의 최소 높이를 키우면 창의 최소 높이가 480 을 넘어 작은 노트북 화면(1366×768, 125%)에서 아래 막대가 작업 표시줄에 가려짐."""
        line = 20 * theme.code_font(theme.text_px()).pixelSize() / theme.CODE_PX
        lowest = round(EDITOR_LINES * line)
        if not self.save_banner.isHidden():
            taken = self.save_banner.heightForWidth(max(1, self.editor_pane.width())) + PANE_GAP
            lowest = max(round(line), lowest - taken)
        self.editor.setMinimumHeight(lowest)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width() and not self.save_banner.isHidden():  # 폭이 바뀌면 띠 글의 줄 수가 바뀜
            self.fit_editor()


class JourneyPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)  # 맨 먼저 걸어야 뒤에 만드는 찾기 막대도 새 규칙으로 그려짐
        self.setObjectName("page")
        self.setProperty("clipboard", True)  # gui/guard.py 가 이 화면 안의 복사·붙여넣기를 막지 않음
        self.win = win
        self.did = self.pid = None
        self.lang = "python"
        self.data = None  # service.problem() 의 결과
        self.explain = None  # service.open_explain() 의 결과. 해설 탭을 처음 그릴 때 읽음
        self.dirty = {}  # 아직 파일에 쓰지 않은 코드 {(던전, 문제, 언어): 글}
        self.results = {}  # 마지막 결과 {(던전, 문제, 언어): (종류, 결과 dict)}
        self.places = {}  # 떠날 때의 탭과 세 칸의 스크롤 자리 {(던전, 문제): (탭, [자리])}
        self.pending = {}  # 다시 연 문제에서 돌아갈 스크롤 자리 {DocView: 자리}. 사람이 스크롤하거나 다른 문제를 열 때까지 지킴
        self.live = None  # 실행·채점 중에 지금까지 온 결과
        self.job_kind = None  # 도는 일이 실행("run")·채점("grade")이면 그 종류
        self.stage, self.started = "", 0.0  # 채점 단계 문장과 시작한 때
        self.busy, self.busy_text, self.opened_wide, self.node_missing = False, "", False, False
        self.save_error = ""  # 마지막 저장 실패의 문구. 창이 떠날 때 묻는 창에 씀
        self.cases_dialog = None
        root = kit.box(self)

        # 위 막대
        self.top = kit.TopBar("← 알고리즘 여행", "")
        self.map_btn, self.title = self.top.back, self.top.title
        self.title.show()
        self.top.row.setStretchFactor(self.title, 0)
        self.title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.heads = QWidget()  # 역할 꼬리표와 번호
        heads_box = kit.box(self.heads, spacing=8, horizontal=True)
        self.badge = kit.badge()
        self.number = kit.label("", "caption", "tertiary")
        heads_box.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        heads_box.addWidget(self.number, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status = kit.para("", "caption", "tertiary")  # 동작 결과 한 문장. 두 줄까지
        self.status.hide()
        self.top.row.insertWidget(2, self.heads, 0, Qt.AlignmentFlag.AlignVCenter)
        self.top.row.insertSpacing(3, STATUS_GAP)
        self.top.row.insertWidget(4, self.status, 1, Qt.AlignmentFlag.AlignVCenter)
        self.top.row.insertStretch(5, 0)  # 남는 폭은 상태 글이 상한까지 먼저 받고 나머지가 여기로 감
        self.lang_bar = LangChips()
        self.lang_btns = self.lang_bar.buttons
        self.lang_bar.note.setMinimumWidth(1)  # 화면의 최소 폭에 넣지 않음. 자리가 모자라면 fit_top 이 숨김
        self.top.add_right(self.lang_bar)
        root.addWidget(self.top)

        # 왼쪽 지문 카드
        self.problem_view, self.hint_view, self.explain_view = self.views = [DocView(flat=True) for _ in range(3)]
        for view in self.views:
            view.ruled = False
            bar = view.verticalScrollBar()
            bar.rangeChanged.connect(lambda low, high, view=view: self._settle(view))
            bar.actionTriggered.connect(lambda action, view=view: self.pending.pop(view, None))  # 사람이 스크롤하면 옮겨 둘 자리를 버림
        self.facts = FactLine()
        self.problem_view.set_head(self.facts)
        self.hint_tail = QWidget()
        hint_box = kit.box(self.hint_tail, spacing=8)
        self.hint_btn = kit.button("", "secondary", "m")
        self.hint_note = kit.label("", "caption", "tertiary")
        hint_box.addWidget(self.hint_btn, 0, Qt.AlignmentFlag.AlignLeft)
        hint_box.addWidget(self.hint_note)
        self.hint_view.set_tail(self.hint_tail)
        self.explain_tail = QWidget()  # 해설 꼬리. [해설 먼저 보기]의 글자가 위 문단과 같은 세로선에 오게 FLUSH 만큼 내어 둠
        explain_box = kit.box(self.explain_tail)
        self.give_up_btn = kit.button("해설 먼저 보기", "danger_text", "m")
        self.next_box = QWidget()  # 해설 끝의 다음 문제 줄. 위 24(조각 사이 16 에 8 을 더함). 꼬리를 내어 둔 만큼 왼쪽을 되돌림
        next_box = kit.box(self.next_box, (kit.FLUSH, 8, 0, 0), 8)
        self.next_rows = kit.RowList(flush=True)
        next_box.addWidget(kit.label("다음 문제", "caption", "tertiary"))
        next_box.addWidget(self.next_rows)
        explain_box.addWidget(self.give_up_btn, 0, Qt.AlignmentFlag.AlignLeft)
        explain_box.addWidget(self.next_box)
        self.explain_view.set_tail(self.explain_tail, flush=True)
        self.tabs = TabBarStack(["문제", "힌트", "해설"], self.views)
        self.problem_card, card_box = kit.card(0, 0)
        card_box.addWidget(self.tabs)

        # 오른쪽 편집기와 결과 카드
        self.code_panel = JourneyCodePanel(win.settings)
        self.result = self.code_panel.result
        self.find_bar = FindBar(self.code_panel.editor, self.code_panel.editor_pane)
        kit.typed(self.find_bar.input, "code")
        kit.typed(self.find_bar.count, "caption")
        self.find_bar.installEventFilter(self)  # 막대가 뜨고 닫힐 때 편집기의 Esc 를 끄고 켬
        self.split = kit.splitter(Qt.Orientation.Horizontal, "journey/split", 0.5, 24, win.settings)
        self.split.addWidget(self.problem_card)
        self.split.addWidget(self.code_panel)
        body = QWidget()
        kit.box(body, (kit.MARGIN, 24, kit.MARGIN, 24)).addWidget(self.split)
        root.addWidget(body, 1)

        # 아래 막대
        self.bar = kit.BottomBar()
        self.reset_btn = self.bar.add_tool(kit.button("코드 되돌리기", "danger_text", "m"))
        self.reset_btn.setToolTip("시작 코드로 되돌립니다.")
        policy = self.reset_btn.sizePolicy()
        policy.setRetainSizeWhenHidden(True)  # 실행·채점 중에 숨겨도 [테스트 추가]가 왼쪽으로 옮겨 가지 않음
        self.reset_btn.setSizePolicy(policy)
        self.code_panel.reset_btn = self.reset_btn
        self.cases_btn = self.bar.add_tool(kit.button("테스트 추가", "text", "m"))
        self.stop_btn = self.bar.add_action(kit.button("중지", "secondary", "l"))
        self.stop_btn.hide()
        self.run_btn = self.bar.add_action(kit.button("코드 실행", "secondary", "l"))
        self.run_btn.setToolTip(RUN_TIP)
        self.grade_btn = self.bar.add_action(kit.button("채점하기", "primary", "l"))
        self.grade_btn.setToolTip(GRADE_TIP)
        root.addWidget(self.bar)

        # 단축키
        editor = self.code_panel.editor
        for keys, slot in ((("Ctrl+Return", "Ctrl+Enter"), self.run_code), (("Ctrl+Shift+Return", "Ctrl+Shift+Enter"), self.grade)):
            for key in keys:  # 키패드 Enter 도 받음. 편집기 안에서도 창의 단축키가 먼저 받아 줄바꿈이 들어가지 않음
                QShortcut(QKeySequence(key), self, slot)
        QShortcut(QKeySequence.StandardKey.Save, self, self.save_now)
        self.escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), editor, self.tabs.focus_tab, context=Qt.ShortcutContext.WidgetShortcut)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(SAVE_DELAY_MS)
        self.save_timer.timeout.connect(lambda: self.flush(offer=False, commit=False))  # 타이머 저장은 조합 중인 한글을 끊지 않음
        self.hint_scroll = QTimer(self)  # 새 힌트 조각이 자리를 잡은 뒤 맨 아래로 내림
        self.hint_scroll.setSingleShot(True)
        self.hint_scroll.setInterval(0)
        self.hint_scroll.timeout.connect(lambda: self.hint_view.verticalScrollBar().setValue(self.hint_view.verticalScrollBar().maximum()))
        self.ticker = QTimer(self)  # 채점 중 지난 초
        self.ticker.setInterval(1000)
        self.ticker.timeout.connect(self._tick)
        self.code_panel.changed.connect(self.on_code_changed)
        self.reset_btn.clicked.connect(self.ask_reset)
        self.explain_view.linked.connect(lambda url: self.win.open_url(url))
        self.facts.opened.connect(self.open_other)
        self.result.acted.connect(self.on_banner)
        self.lang_bar.picked.connect(self.pick_lang)
        self.hint_btn.clicked.connect(self.next_hint)
        self.give_up_btn.clicked.connect(self.ask_give_up)
        self.map_btn.clicked.connect(lambda: self.win.go_journey(self.did))
        self.cases_btn.clicked.connect(self.open_cases)
        self.stop_btn.clicked.connect(self.stop)
        self.run_btn.clicked.connect(self.run_code)
        self.grade_btn.clicked.connect(self.grade)
        self.fit_columns()

    # 폭

    def fit_columns(self):
        """지문 카드는 읽는 글의 단 폭(창 폭을 따라 넓어짐)에 안쪽 여백과 스크롤 막대 자리를 더한 폭까지이고 넘는 폭은 편집기 칸이 받음.
        두 칸의 몫은 창 크기가 바뀌어도 기억한 몫대로 다시 나눔."""
        doc = kit.doc_width(self.width())
        self.problem_card.setMaximumWidth(doc + 2 * PAD + self.problem_view.verticalScrollBar().sizeHint().width())
        for view in self.views:
            view.sheet.setMaximumWidth(doc + 2 * PAD)
        self.split.place()

    def fit_top(self):
        """위 막대의 문제 이름과 상태 글 폭. 돌아가기·꼬리표·번호·칩을 뺀 폭을 둘이 나눔. 이름은 다 보이되 상한(TITLE_CAP)까지,
        상태 글은 하한과 STATUS_MAX 사이이고 넘으면 줄을 바꿈. 자리가 모자라면 이름이 TITLE_MIN 까지 줄임표로 줄고,
        그래도 모자라면 "Node.js 필요" 를 숨김(같은 말이 JavaScript 칩 도움말에 있음). 최소 폭은 늘 TITLE_MIN 과 상태 하한이라
        창이 좁아져도 이 막대가 1024 창을 넓히지 않음. 상하한은 글자 크기에 비례함."""
        status, note, row = self.status, self.lang_bar.note, self.top.row
        status.setVisible(bool(status.text()))
        scale = theme.TYPE["headline"][0] / theme.BASE_TYPE["headline"][0]
        title_full = text_width(self.title, self.title.text()) + 2
        cap = round(TITLE_CAP * scale)
        status_full = text_width(status, status.text()) + 2 if status.text() else 0  # 글 폭을 소수점까지 재어 올림하고도 한 줄에 들게 2 를 더함
        low = min(status_full, round(STATUS_LOW * theme.TYPE["caption"][0] / theme.BASE_TYPE["caption"][0]))
        left, _, right, _ = row.getContentsMargins()
        gaps = row.spacing() * (4 if status.text() else 3) + STATUS_GAP

        def room():
            parts = (self.map_btn, self.heads, self.lang_bar)
            return self.top.width() - left - right - gaps - sum(widget.sizeHint().width() for widget in parts)

        note.setVisible(self.node_missing)
        if self.node_missing and room() < min(TITLE_MIN, title_full) + low:
            note.hide()
        space = room()
        title = max(min(TITLE_MIN, title_full), min(title_full, cap, space - low))
        self.title.setMinimumWidth(min(TITLE_MIN, title_full))
        self.title.setMaximumWidth(title)
        status.setMinimumWidth(low)
        status.setMaximumWidth(max(low, min(STATUS_MAX, status_full, space - title)))

    def pin_widths(self):
        """돌아가기 단추와 칩의 최소 폭을 지금 글자 폭으로 묶음."""
        pin(self.map_btn)
        self.lang_bar.fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_columns()
        self.fit_top()

    def showEvent(self, event):
        """화면을 보일 때 초점은 편집기에 둠. 문제를 열면 바로 코드를 쓸 수 있음. 내려 둔 창을 다시 띄울 때(운영체제가 보내는 보이기)는
        초점을 옮기지 않음."""
        super().showEvent(event)
        self.pin_widths()
        self.fit_top()
        if not event.spontaneous():
            self.code_panel.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, target, event):
        if target is self.find_bar and event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            self.escape.setEnabled(self.find_bar.isHidden())  # 같은 키의 단축키 둘이 같이 켜지면 둘 다 눌리지 않음
        return False

    # 불러오기

    def usable_lang(self):
        """설정의 언어. JavaScript 인데 node 가 없으면 Python 으로 풀고 "Node.js 필요" 를 보임.
        창이 이 화면을 열기 전에 워커에서 node 를 찾아 두므로 여기서는 기억한 결과만 읽음."""
        lang = saved_lang(self.win.settings)
        self.show_node_note(lang == "javascript" and not node_ready(self.win))
        return "python" if self.node_missing else lang

    def show_node_note(self, missing):
        """"Node.js 필요" 를 보이거나 숨김. 자리가 모자라 fit_top 이 그 글을 숨겨도 같은 말이 JavaScript 칩 도움말에 있음."""
        self.node_missing = missing
        self.lang_btns["javascript"].setToolTip(self.lang_bar.note.toolTip() if missing else "")
        self.fit_top()

    def load(self, did, pid):
        """문제를 화면에 올림. 잠긴 보스처럼 열 수 없거나 앞 문제의 코드를 저장하지 못하면 화면을 바꾸지 않고 JourneyError 를 냄.
        같은 실행 안에서 열었던 문제면 떠날 때의 탭과 읽던 자리로 돌아감."""
        if not self.flush(offer=False):
            raise JourneyError(self.save_error)
        lang = self.usable_lang()
        data = self.win.journey.problem(did, pid, lang)
        self.keep_place()
        self.did, self.pid, self.lang, self.data, self.explain = did, pid, lang, data, None
        self.find_bar.dismiss(select=False)
        self._show_code()
        self.set_status("")
        self.show_head()
        self.show_docs()
        self.opened_wide = False
        self.show_result()
        self.restore_place()
        if self.isVisible():
            self.code_panel.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def reload(self):
        """[문제 받기]로 은행이 바뀐 뒤에 부름. 같은 문제를 새로 읽어 True, 그 문제를 더는 열 수 없으면 False."""
        if self.data is None:
            return False
        try:
            self.load(self.did, self.pid)
        except SessionError:
            return False
        return True

    def refresh(self):
        """채점·해설로 기록이 바뀐 뒤 머리와 힌트·해설 탭을 다시 그림. 편집기의 글과 세 탭의 읽던 자리는 그대로 둠.
        힌트·해설 칸은 다시 그리면 맨 위로 가므로 읽던 자리를 돌아갈 자리(pending)에 넣음."""
        if self.data is None:
            return
        try:
            data = self.win.journey.problem(self.did, self.pid, self.lang)
        except SessionError:
            return
        self.data = data
        kept = {view: view.verticalScrollBar().value() for view in (self.hint_view, self.explain_view)}
        self.show_head()
        self.show_docs(problem=False)
        for view, place in kept.items():
            if place:
                self.pending[view] = place
                self._settle(view)

    def keep_place(self):
        if self.data is not None:
            self.places[(self.did, self.pid)] = (self.tabs.currentIndex(), [view.verticalScrollBar().value() for view in self.views])

    def restore_place(self):
        tab, places = self.places.get((self.did, self.pid), (0, [0, 0, 0]))
        self.tabs.setCurrentIndex(tab)
        self.pending = {view: place for view, place in zip(self.views, places) if place}
        for view in self.views:
            self._settle(view)

    def _settle(self, view):
        """돌아갈 자리가 있으면 스크롤 범위가 바뀔 때마다 그 자리로 옮김. 조각의 높이는 보인 뒤 레이아웃이 여러 번에 걸쳐 정하고,
        그 사이 범위가 줄었다 늘면 스크롤 값이 줄어든 범위에 묶이므로 한 번 옮긴 것으로 끝내지 않음."""
        place = self.pending.get(view)
        bar = view.verticalScrollBar()
        if place is not None and bar.maximum() >= place:
            bar.setValue(place)

    def _show_code(self):
        self.code_panel.editor.set_lang(LANGS[self.lang])
        self.code_panel.set_code(self.data["code"])
        self.lang_bar.set_lang(self.lang)

    def show_head(self):
        """위 막대의 이름·꼬리표·번호와 지문 머리."""
        data = self.data
        self.title.setText(data["title"])
        self.badge.setText(data["role_label"])
        self.number.setText(number_text(data))
        self.facts.set_problem(data, self.lang)
        self.facts.setEnabled(not self.busy)
        self.fit_top()

    def show_docs(self, problem=True):
        if problem:
            self.problem_view.set_markdown(self.data["markdown"], self.data["base_dir"], self.lang)
        self.show_hints()
        self.show_explain()

    def show_hints(self):
        """연 힌트와 그 아래 [힌트 n 보기]. 아직 연 힌트가 없으면 안내 한 문단, 힌트가 없는 문제는 그 한 문장."""
        data, view = self.data, self.hint_view
        hints, total = data["hints"], data["hint_total"]
        self.tabs.setTabText(1, "힌트 %d/%d" % (len(hints), total) if total else "힌트")
        if hints:
            view.set_markdown("\n\n".join("### 힌트 %d\n\n%s" % (number, body) for number, body in enumerate(hints, 1)), data["base_dir"], self.lang)
        else:
            view.set_markdown("", data["base_dir"], self.lang)
            view.add_para(HINT_INTRO if total else NO_HINT, "muted")
        left = total - len(hints)
        self.hint_btn.setText("힌트 %d 보기" % (len(hints) + 1))
        self.hint_btn.setVisible(left > 0)
        self.hint_note.setText("힌트를 모두 열었습니다." if total and not left else "")
        self.hint_note.setVisible(bool(self.hint_note.text()))
        self.hint_tail.setVisible(bool(total))

    def show_explain(self):
        """해설이 열렸으면 explain.md, (보스면) 보스에 쓰인 기술 표, 기준 풀이, 더 풀어 볼 문제, 다음 문제 줄.
        안 열렸으면 안내 한 문장과 [해설 먼저 보기]."""
        data, view = self.data, self.explain_view
        opened = data["explain_open"]
        self.give_up_btn.setVisible(not opened)
        self.next_box.hide()
        self.explain_tail.setVisible(not opened)  # 다음 문제 줄이 생기면 show_next 가 다시 보임
        if not opened:
            view.set_markdown("", data["base_dir"], self.lang)
            view.add_para(EXPLAIN_LOCKED, "muted")
            return
        if self.explain is None:
            try:
                self.explain = self.win.journey.open_explain(self.did, self.pid, self.lang)
            except SessionError as error:
                view.set_markdown(md_text(error_text("explain", error)[1]), data["base_dir"], self.lang)
                return
        explain = self.explain
        view.set_markdown(explain["markdown"], explain["base_dir"], self.lang)
        if explain["parts"]:
            view.add_para("보스에 쓰인 기술", "h2")
            view.add_table(["이 보스에서 하는 일", "익힌 문제"], [[part["text"], ", ".join(part["nos"])] for part in explain["parts"]])
        code = explain["solution"].get(self.lang)
        if code:
            view.add_code("기준 풀이 (%s)" % LANG_LABEL[self.lang], code, self.lang)
        if explain["similar"]:
            view.add_para("더 풀어 볼 문제", "h2")
            for item in explain["similar"]:
                view.add_para(similar_text(item), link=item.get("url"))
        self.show_next()

    def show_next(self):
        """해설 끝의 다음 문제 줄. 지도·첫 화면과 같은 이어서 할 일(next_item)이고, 지금 문제와 같으면 두지 않음."""
        self.next_rows.clear()
        try:
            item = next_item(self.win.journey, "%s/%s" % (self.did, self.pid))
        except SessionError:
            item = None
        if item is None or (item["did"], item["pid"]) == (self.did, self.pid):
            return
        row = self.next_rows.add(kit.Row(item["title"], item_line(item), data=(item["did"], item["pid"])))
        row.clicked.connect(lambda: self.busy or self.win.open_problem(*row.data))
        row.setEnabled(not self.busy)
        self.next_box.show()
        self.explain_tail.show()

    def show_result(self):
        """(문제, 언어)의 기억한 결과를 그림. 없으면 결과가 없을 때의 머리를 두고, 이 문제를 연 뒤 한 번도 펼치지 않았으면 접음."""
        remembered = self.results.get((self.did, self.pid, self.lang))
        if remembered:
            self.expand_result()
            self.result.show_result(*remembered)
            return
        self.result.show_empty(self.data["best"].get(self.lang), len(self.data["cases"]))
        if not self.opened_wide:
            self.code_panel.collapse()

    def expand_result(self):
        self.opened_wide = True
        self.code_panel.expand()

    # 위 막대 상태

    def set_status(self, text, tip=""):
        self.status.setText(text)
        self.status.setToolTip(tip)
        self.fit_top()

    def _saved(self):
        self.set_status(SAVED, "%s 에 저장했습니다." % datetime.datetime.now().strftime("%H:%M:%S"))

    # 언어

    def pick_lang(self, lang, node_ok=None):
        """언어를 바꿈. 쓰던 코드를 저장하고 그 언어의 파일(없으면 시작 코드)을 엶. JavaScript 인데 node 가 없으면 Python 에 머묾.
        node_ok 는 with_node 가 알아낸 결과이고, 없으면 with_node 를 거쳐 다시 부름."""
        if self.data is None or lang == self.lang:
            self.lang_bar.set_lang(self.lang)
            return
        if lang == "javascript" and node_ok is None:
            with_node(self.win, lambda ok: self.pick_lang(lang, ok))
            return
        if lang == "javascript" and not node_ok:
            self.set_status("")
            self.lang_bar.set_lang(self.lang)
            self.show_node_note(True)
            ask_node(self.win, lambda: self.pick_lang("javascript"))
            return
        if not self.flush():
            self.lang_bar.set_lang(self.lang)
            return
        try:
            data = self.win.journey.problem(self.did, self.pid, lang)
        except SessionError as error:
            self.lang_bar.set_lang(self.lang)
            self.fail("lang", error)
            return
        self.win.settings.setValue("journey/lang", lang)
        if lang == "javascript":
            self.show_node_note(False)
        self.lang, self.data, self.explain = lang, data, None
        self.find_bar.dismiss(select=False)
        self._show_code()
        self.set_status("")
        self.show_head()
        self.show_docs()
        self.show_result()

    # 힌트 · 해설

    def next_hint(self):
        try:
            opened = self.win.journey.reveal_hint(self.did, self.pid)
        except SessionError as error:
            self.fail("hint", error)
            return
        self.data["hints"].append(opened["text"])
        self.pending.pop(self.hint_view, None)
        self.show_hints()
        self.hint_scroll.start()

    def ask_give_up(self):
        """기록을 지울 수 없는 행동이라 [해설 열기]는 빨간 옅은 바탕이고 Enter 로 눌리지 않음."""
        self.win.ask(GIVE_UP_TITLE, GIVE_UP_TEXT, (("해설 열기", "open", "danger"), ("닫기", "")), lambda key: self.give_up())

    def give_up(self):
        try:
            self.explain = self.win.journey.open_explain(self.did, self.pid, self.lang, give_up=True)
        except SessionError as error:
            self.fail("explain", error)
            return
        self.data["explain_open"] = True
        self.show_explain()
        self.tabs.setCurrentIndex(2)

    def open_other(self, pid):
        """지문 머리의 준비 문제 링크."""
        if not self.busy:
            self.win.open_problem(self.did, pid)

    def on_banner(self, key):
        """결과 카드 완료 띠의 [해설 보기]는 해설 탭을, [보스 풀기]는 이 던전의 보스 문제를 엶."""
        if key == "explain":
            self.tabs.setCurrentIndex(2)
            return
        boss = next((row["id"] for row in self.win.journey.dungeon(self.did)["problems"] if row["role"] == "boss"), None)
        if boss and not self.busy:
            self.win.open_problem(self.did, boss)

    # 저장

    def on_code_changed(self, text):
        if self.data is None:
            return
        self.dirty[(self.did, self.pid, self.lang)] = text
        self.save_timer.start()

    def flush(self, offer=True, commit=True):
        """대기 중인 코드를 파일에 쓰고, 다 썼으면 True 를 돌려줌. commit 이면 조합 중인 한글부터 확정함.
        저장하지 못하면 편집기 위에 오류 띠를 보이고(원문은 띠 도움말) 위 막대의 "저장했습니다" 를 지움.
        offer 면 대화상자로도 알림(부른 쪽이 직접 알릴 때는 offer=False). 다음 저장이 되면 띠를 숨김."""
        if commit:
            QGuiApplication.inputMethod().commit()
        self.save_timer.stop()
        panel = self.code_panel
        if not self.dirty:  # [저장하지 않고 나가기]로 쓰던 코드를 버린 뒤에도 여기로 오므로 앞의 실패 띠를 거둠
            self.save_error = ""
            panel.hide_save_error()
            return True
        for key, text in list(self.dirty.items()):
            try:
                self.win.journey.save_code(key[0], key[1], key[2], text)
            except (SessionError, OSError) as error:
                message = str(error)
                self.save_error = message if message.startswith(SAVE_ERROR) else "%s: %s" % (SAVE_ERROR, message)
                panel.show_save_error(message)
                if self.status.text() == SAVED:
                    self.set_status("")
                if offer:
                    self.fail("save", error)
                return False
            del self.dirty[key]
        self.save_error = ""
        panel.hide_save_error()
        self._saved()
        return True

    def save_now(self):
        """Ctrl+S. 기다리지 않고 저장함."""
        if self.data is not None and not self.busy and self.flush():
            self._saved()

    def ask_reset(self):
        self.win.ask(RESET_TITLE, RESET_TEXT, (("되돌리기", "reset", "danger"), ("닫기", "")), lambda key: self.reset())

    def reset(self):
        try:
            starter = self.win.journey.reset_code(self.did, self.pid, self.lang)
        except SessionError as error:
            self.fail("reset", error)
            return
        cur = self.code_panel.editor.textCursor()
        cur.select(QTextCursor.SelectionType.Document)
        cur.insertText(starter)  # 편집으로 넣어야 되돌리기(Ctrl+Z)가 남음
        self.flush()

    # 실행 · 채점

    def locked(self):
        """실행·채점하는 파일과 화면이 어긋나지 않게 도는 동안 끄는 것. 탭과 문서는 읽을 수 있게 둠."""
        return ([self.code_panel.editor, self.lang_bar, self.map_btn, self.hint_btn, self.give_up_btn, self.cases_btn, self.reset_btn,
                 self.run_btn, self.grade_btn, self.facts] + self.next_rows.rows)

    def set_busy(self, busy, text=""):
        """도는 동안 편집기·칩·돌아가기·힌트·해설 단추·아래 막대를 잠그고 [코드 되돌리기]는 숨김. 실행·채점이면 누른 단추가
        진행형(실행 중·채점 중)이 되고 그 왼쪽에 [중지]가 나옴. 진행은 결과 카드 머리가 보이므로 실행·채점이 아닌 일의 이름만 위 막대 상태 자리에 씀."""
        first = busy and not self.busy
        self.busy = busy
        kind = self.job_kind if busy else None
        for widget in self.locked():
            widget.setEnabled(not busy)
        self.run_btn.setText("실행 중" if kind == "run" else "코드 실행")
        self.grade_btn.setText("채점 중" if kind == "grade" else "채점하기")
        self.stop_btn.setVisible(kind is not None)
        if first:
            self.stop_btn.setText("중지")
            self.stop_btn.setEnabled(True)
        self.reset_btn.setVisible(not busy)  # 파괴 글자 단추는 꺼진 모양이 없어 끄는 대신 숨김
        if busy and text and text not in (RUN_BUSY, GRADE_BUSY):
            self.busy_text = text
            self.set_status(text)
        if not busy:
            if self.busy_text and self.status.text() == self.busy_text:
                self.set_status("")
            self.busy_text, self.job_kind = "", None

    def run_code(self):
        """[코드 실행]. 입출력 예와 내 테스트를 돌리고 기록하지 않음. 결과 카드는 누른 순간 펼침."""
        if self.data is None or self.busy or not self.flush():
            return
        did, pid, lang = self.did, self.pid, self.lang
        self.live = {"cases": [], "total": len(self.data["examples"]) + len(self.data["cases"])}
        self._start("run")
        started = self.win.run_job(RUN_BUSY, caught(lambda report, cancel: self.win.journey.run(did, pid, lang, report, cancel)),
                                   lambda result: self._ran((did, pid, lang), result), on_fail=self._failed, on_progress=self.on_progress)
        self._refused(started)

    def grade(self):
        """[채점하기]. 숨은 테스트까지 채점하고 기록함."""
        if self.data is None or self.busy or not self.flush():
            return
        did, pid, lang = self.did, self.pid, self.lang
        self.live = {"groups": []}
        self._start("grade")
        self.ticker.start()
        started = self.win.run_job(GRADE_BUSY, caught(lambda report, cancel: self.win.journey.grade(did, pid, lang, report, cancel)),
                                   lambda result: self._graded((did, pid, lang), result), on_fail=self._failed, on_progress=self.on_progress)
        self._refused(started)

    def _refused(self, started):
        """다른 일이 도는 중이라 창이 일을 받지 않았으면(run_job 이 False) _start 가 펼친 진행 머리와 시계를 거둠."""
        if started is False:
            self.job_kind = None
            self._failed()

    def _start(self, kind):
        self.job_kind, self.stage, self.started = kind, "", time.monotonic()
        self.expand_result()
        self._show_live()

    def seconds(self):
        return int(time.monotonic() - self.started) if self.job_kind == "grade" else 0

    def _show_live(self):
        """진행 중인 결과를 머리와 본문에 그림."""
        if self.live is not None:
            self.result.show_result(self.job_kind, self.live, False, self.stage, self.seconds())

    def _tick(self):
        """채점 중 1초마다 머리 caption 의 지난 초만 고침."""
        if self.live is None:
            self.ticker.stop()
            return
        self.result.show_head(self.job_kind, self.live, False, self.stage, self.seconds())

    def on_progress(self, event):
        """워커가 보낸 진행 알림. 단계 문장은 결과 카드 머리에, 끝난 테스트 줄은 본문에 붙임."""
        if self.live is None:
            return
        if event.get("kind") == "status":
            self.stage = event["text"]
        elif event.get("kind") == "case":
            if "groups" in self.live:
                groups = self.live["groups"]
                if not groups or groups[-1]["name"] != event.get("group"):
                    groups.append({"name": event.get("group"), "cases": []})
                groups[-1]["cases"].append(event["case"])
            else:
                self.live["cases"].append(event["case"])
        else:
            return
        self._show_live()

    def _ran(self, key, result):
        if isinstance(result, Failed):
            self._failed()
            self.fail("run", result.message)
            return
        self.live = None
        self.results[key] = ("run", result)
        self.show_result()
        self.code_panel.focus_input()

    def _graded(self, key, result):
        if isinstance(result, Failed):
            self._failed()
            self.fail("grade", result.message)
            return
        self.live = None
        self.ticker.stop()
        self.results[key] = ("grade", result)
        self.show_result()
        self.code_panel.focus_input()  # 도는 동안 편집기를 꺼서 초점이 사라졌음
        if result.get("cancelled"):
            return
        self.refresh()
        if result.get("cleared"):
            self.celebrate()

    def _failed(self):
        self.live = None
        self.ticker.stop()
        self.show_result()
        self.code_panel.focus_input()

    def stop(self):
        """도는 실행·채점에 멈추라고 알림. 결과는 끝난 줄까지만 돌아오고 기록되지 않음."""
        job = getattr(self.win, "job", None)
        if job is not None:
            job[0].cancel.set()
            self.stop_btn.setText("멈추는 중")
            self.stop_btn.setEnabled(False)

    def celebrate(self):
        """보스를 처음 통과함. 색종이와 다음 추천 던전을 알리는 대화상자. 다음 던전이 있으면 [다음 던전 보기]가 지도에서 그 던전을 고름."""
        motion.confetti(self)
        overview = self.win.journey.overview()
        target = overview["next"]
        there = next((row for row in overview["dungeons"] if target and row["id"] == target["did"] != self.did), None)
        text = clear_text(self.data["dungeon_title"], there["title"] if there else None)
        if there:
            self.win.ask(CLEAR_TITLE, text, (("다음 던전 보기", "next", "primary"), ("닫기", "")), lambda key: self.win.go_journey(there["id"]))
        else:
            self.win.ask(CLEAR_TITLE, text)

    def fail(self, action, error):
        """서비스 오류를 하던 행동의 이름("코드 실행")을 제목으로 한 창에 보임. 내부 id 나 원문은 [자세히]로 넘김(journey_text.error_text).
        실행·채점 중에 node 가 사라졌으면(앱을 켠 뒤 지움) [다시 찾기]·[직접 고르기]가 있는 Node 창을 띄움."""
        if str(error) == NO_NODE:
            ask_node(self.win, lambda: None, NODE_MISSING)
            return
        title, text, detail = error_text(action, error)
        self.win.ask(title, text, detail=detail)

    def open_cases(self):
        if self.data is None or self.busy:
            return
        did, pid = self.did, self.pid
        if self.cases_dialog is not None:  # 열 때마다 새로 만들므로 닫힌 앞 창이 화면의 자식으로 쌓이지 않게 지움
            self.cases_dialog.deleteLater()
        self.cases_dialog = CasesDialog(self, self.data, self.lang, lambda cases: self.win.journey.save_cases(did, pid, cases),
                                        self._cases_saved)
        self.cases_dialog.show()

    def _cases_saved(self, cases):
        self.data["cases"] = cases
        self.set_status("내 테스트 %d개를 저장했습니다." % len(cases) if cases else "내 테스트를 모두 지웠습니다.")
        if self.result.shown[0] is None:  # 결과가 없을 때의 caption 이 내 테스트 수를 말함
            self.show_result()

    # 테마 · 글자 크기

    def restyle(self):
        """글자 크기나 테마가 바뀌면 부름. 지문·힌트·해설에 CSS 를, 편집기와 기준 풀이에 코드 글꼴을 다시 주고 결과 카드를 같은 결과로
        다시 그림. 읽던 자리는 지킴. 글 폭이 바뀌므로 칸 폭, 위 막대, 접힌 카드 높이도 다시 잡음."""
        for view in self.views:
            view.restyle(theme.journey_css(), theme.code_font(theme.text_px() - 1))
        self.code_panel.editor.setFont(theme.code_font(theme.text_px()))
        self.result.redraw()
        self.code_panel.refit()
        self.pin_widths()
        self.fit_columns()
        self.fit_top()
