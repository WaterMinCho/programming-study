# -*- coding: utf-8 -*-
"""알고리즘 여행의 문제 화면: 머리줄(던전 지도 · 문제 · 언어) · 왼쪽 문제·힌트·해설 탭 · 오른쪽 편집기와 결과 칸 · 아래 실행과 채점.

코드는 입력이 멈추고 SAVE_DELAY_MS 뒤에 서비스로 저장함. 실행·채점은 창의 run_job 으로 워커에서 돌림.
진행 알림(report)이 올 때마다 결과 칸에 줄을 하나씩 붙임. 마지막 결과 HTML 은 (문제, 언어)마다 메모리에 두어 다른 문제를 갔다 와도 다시 보임.
이 화면 안에서는 복사·붙여넣기가 됨(clipboard 속성을 gui/guard.py 가 봄). 파이썬 스터디의 회차 화면은 지금처럼 막힘.
언어 단추와 Node.js 가 없을 때의 대화상자는 지도(gui/journey_map.py)도 같이 씀."""
import datetime
import re

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QTextCursor
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy, QSplitter, QTabWidget,
                             QVBoxLayout, QWidget)

from gui import journey_html, kit, motion, theme
from gui.cases_dialog import CasesDialog
from gui.docview import DocView
from gui.editor import LANGS
from gui.journey_text import LANG_LABEL, clear_text, error_text
from gui.widgets import CodePanel, FindBar, Para
from journey.node import MIN_MAJOR
from journey.service import JourneyError
from session import SessionError

SAVE_DELAY_MS = 400  # 입력이 멈춘 뒤 자동 저장까지
SITE_LABEL = {"boj": "백준", "programmers": "프로그래머스"}
NODE_TITLE = "Node.js 찾기"
NODE_BUSY = "Node.js 찾는 중"  # node 를 찾거나 고른 파일을 확인하는 동안 화면 위 막대에 보이는 글
NODE_TEXT = ("JavaScript 로 풀려면 Node.js %d 이상이 필요합니다. 설치한 뒤 [다시 찾기]를 누르고, 설치했는데 찾지 못하면 "
             "[직접 고르기]로 node 실행 파일을 고르세요." % MIN_MAJOR)
NODE_LINK = "https://nodejs.org"  # Node 창 본문 아래에 누를 수 있는 주소로 보임
NODE_MISSING = "Node.js 를 찾지 못했습니다."  # [다시 찾기]로도 찾지 못했을 때 Node 창 본문 앞에 붙는 문장
GIVE_UP_TITLE = "해설 먼저 보기"
GIVE_UP_TEXT = "아직 통과하지 않은 문제입니다. 해설을 열면 기록에 남고, 나중에 통과해도 목록에 '해설 보고 통과'로 보입니다."
RESET_TITLE = "코드 되돌리기"
RESET_TEXT = "지금 코드를 지우고 시작 코드로 바꿉니다. 바로 뒤라면 편집기에서 Ctrl+Z(맥은 Cmd+Z)로 되살릴 수 있습니다."
CLEAR_TITLE = "던전 클리어"


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
    두 행동으로 node 를 찾으면 on_ready() 를 부름. 찾지 못하면 그 까닭(first)을 본문 앞에 붙여 같은 창을 다시 띄움. 찾기와 확인은 워커에서 함."""

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

    text = "%s %s" % (first, NODE_TEXT) if first else NODE_TEXT
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
            chip.setMinimumWidth(0)
            chip.ensurePolished()
            chip.setMinimumWidth(chip.sizeHint().width())

    def showEvent(self, event):
        super().showEvent(event)
        self.fit()


class JourneyCodePanel(CodePanel):
    HINT = "'코드 실행'을 누르면 입출력 예와 내가 추가한 테스트 케이스의 결과가 여기에 나옵니다. 코드 실행은 기록되지 않습니다."


def md_text(text):
    """마크다운 문단에 넣을 꾸밈없는 글. 인라인 꾸밈 글자를 글자 그대로 보이게 막음."""
    return re.sub(r"([\\`*_])", r"\\\1", text)


def problem_markdown(data):
    """[문제] 탭: 준비 문제 줄, 보스면 쓰는 문제 줄, 그다음 problem.md."""
    lines = []
    if data["prep"]:
        lines.append("준비 문제: " + ", ".join("%s %s%s" % (ref["no"], ref["title"], " (통과)" if ref["passed"] else "")
                                             for ref in data["prep"]))
    if data["role"] == "boss" and data["uses"]:
        lines.append("이 보스에 쓰는 문제: " + ", ".join(ref["no"] for ref in data["uses"]))
    return "\n\n".join([md_text(line) for line in lines] + [data["markdown"]])


def similar_text(item):
    """"백준 1000 · A+B", "프로그래머스 · K번째수"."""
    site = SITE_LABEL.get(item.get("site"), item.get("site") or "")
    number = " %s" % item["id"] if item.get("id") else ""
    return "%s%s · %s" % (site, number, item.get("title") or "")


class JourneyPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        self.setProperty("clipboard", True)  # gui/guard.py 가 이 화면 안의 복사·붙여넣기를 막지 않음
        self.win = win
        self.did = self.pid = None
        self.lang = "python"
        self.data = None  # service.problem() 의 결과
        self.explain = None  # service.open_explain() 의 결과. 해설 탭을 처음 그릴 때 읽음
        self.dirty = {}  # 아직 파일에 쓰지 않은 코드 {(던전, 문제, 언어): 글}
        self.results = {}  # 마지막 결과 HTML {(던전, 문제, 언어): HTML}
        self.live = None  # 실행·채점 중에 지금까지 온 결과
        self.cases_dialog = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 0)
        head = QHBoxLayout()
        self.map_btn = QPushButton("던전 지도")
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # 긴 제목이 창을 넓히지 않게 함
        self.tier = QLabel()
        self.tier.setObjectName("muted")
        self.lang_bar = LangChips()
        self.lang_btns = self.lang_bar.buttons
        head.addWidget(self.map_btn)
        head.addSpacing(8)
        head.addWidget(self.title, 1)
        head.addWidget(self.tier)
        head.addSpacing(16)
        head.addWidget(self.lang_bar)
        root.addLayout(head)
        self.band = Para(name="notice")
        self.band.hide()
        root.addWidget(self.band)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.tabs = QTabWidget()
        self.problem_view = DocView()
        hint_page, self.hint_view, hint_row = self._doc_page()
        self.hint_note = Para(name="muted")
        self.hint_btn = QPushButton()
        hint_row.addWidget(self.hint_note, 1)
        hint_row.addWidget(self.hint_btn)
        explain_page, self.explain_view, explain_row = self._doc_page()
        self.give_up_btn = QPushButton("포기하고 해설 보기")
        explain_row.addStretch(1)
        explain_row.addWidget(self.give_up_btn)
        self.tabs.addTab(self.problem_view, "문제")
        self.tabs.addTab(hint_page, "힌트")
        self.tabs.addTab(explain_page, "해설")
        right = QWidget()
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        self.code_panel = JourneyCodePanel(paste=True)
        self.code_panel.console.document().setDocumentMargin(10)
        right_box.addWidget(self.code_panel, 1)
        self.find_bar = FindBar(self.code_panel.editor, right)  # 실행·채점 중에 편집기를 잠가도 쓰이게 그 밖에 둠
        split.addWidget(self.tabs)
        split.addWidget(right)
        split.setStretchFactor(0, 45)
        split.setStretchFactor(1, 55)
        split.setSizes([540, 660])
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        bar = QFrame()
        bar.setObjectName("bar")
        bar_box = QHBoxLayout(bar)
        bar_box.setContentsMargins(4, 8, 4, 8)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setMinimumWidth(1)  # 긴 안내가 창을 넓히지 않고 잘림
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedWidth(140)
        self.busy_bar.hide()
        self.cases_btn = QPushButton("테스트 케이스 추가하기")
        self.stop_btn = QPushButton("중지")
        self.stop_btn.setEnabled(False)
        self.run_btn = QPushButton("코드 실행")
        self.grade_btn = QPushButton("제출 후 채점하기")
        self.grade_btn.setObjectName("primary")
        bar_box.addWidget(self.status, 1)
        bar_box.addWidget(self.busy_bar)
        bar_box.addWidget(self.cases_btn)
        bar_box.addSpacing(16)
        bar_box.addWidget(self.stop_btn)
        bar_box.addWidget(self.run_btn)
        bar_box.addWidget(self.grade_btn)
        root.addWidget(bar)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(SAVE_DELAY_MS)
        self.save_timer.timeout.connect(lambda: self.flush(offer=False, commit=False))  # 타이머 저장은 조합 중인 한글을 끊지 않음
        self.hint_scroll = QTimer(self)  # 새 힌트 조각이 자리를 잡은 뒤 맨 아래로 내림
        self.hint_scroll.setSingleShot(True)
        self.hint_scroll.setInterval(0)
        self.hint_scroll.timeout.connect(lambda: self.hint_view.verticalScrollBar().setValue(self.hint_view.verticalScrollBar().maximum()))
        self.code_panel.changed.connect(self.on_code_changed)
        self.code_panel.reset_btn.clicked.connect(self.ask_reset)
        self.code_panel.console.anchorClicked.connect(lambda url: self.on_link(url.toString()))
        self.explain_view.linked.connect(lambda url: self.win.open_url(url))
        self.lang_bar.picked.connect(self.pick_lang)
        self.hint_btn.clicked.connect(self.next_hint)
        self.give_up_btn.clicked.connect(self.ask_give_up)
        self.map_btn.clicked.connect(lambda: self.win.go_journey(self.did))
        self.cases_btn.clicked.connect(self.open_cases)
        self.stop_btn.clicked.connect(self.stop)
        self.run_btn.clicked.connect(self.run_code)
        self.grade_btn.clicked.connect(self.grade)

    @staticmethod
    def _doc_page():
        """DocView 아래에 단추 줄이 붙은 탭 하나. (탭, DocView, 단추 줄)."""
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 8)
        view = DocView()
        row = QHBoxLayout()
        row.setContentsMargins(20, 0, 20, 0)
        box.addWidget(view, 1)
        box.addLayout(row)
        return page, view, row

    # 불러오기

    def usable_lang(self):
        """설정의 언어. JavaScript 인데 node 가 없으면 Python 으로 풀고 "Node.js 필요" 를 보임.
        창이 이 화면을 열기 전에 워커에서 node 를 찾아 두므로 여기서는 기억한 결과만 읽음."""
        lang = saved_lang(self.win.settings)
        if lang == "javascript" and not node_ready(self.win):
            self.lang_bar.note.show()
            return "python"
        return lang

    def load(self, did, pid):
        """문제를 화면에 올림. 잠긴 보스처럼 열 수 없거나 앞 문제의 코드를 저장하지 못하면 화면을 바꾸지 않고 JourneyError 를 냄."""
        if not self.flush(offer=False):
            raise JourneyError(self.status.text())
        lang = self.usable_lang()
        data = self.win.journey.problem(did, pid, lang)
        self.did, self.pid, self.lang, self.data, self.explain = did, pid, lang, data, None
        self.find_bar.dismiss(select=False)
        self._show_code()
        self.status.setText("")
        self.tabs.setCurrentIndex(0)
        self.show_head()
        self.show_docs()
        self.show_result()

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
        """채점·해설로 기록이 바뀐 뒤 머리줄과 힌트·해설 탭을 다시 그림. 편집기의 글과 문제 탭의 읽던 자리는 그대로 둠."""
        if self.data is None:
            return
        try:
            data = self.win.journey.problem(self.did, self.pid, self.lang)
        except SessionError:
            return
        self.data = data
        self.show_head()
        self.show_docs(problem=False)

    def _show_code(self):
        self.code_panel.editor.set_lang(LANGS[self.lang])
        self.code_panel.set_code(self.data["code"])
        self.code_panel.hint.setText(self.data["file_name"])
        self.lang_bar.set_lang(self.lang)

    def show_head(self):
        data = self.data
        self.title.setText("%s · %s · %s" % (data["no"], data["role_label"], data["title"]))
        self.tier.setText(data["tier"])
        if data["role"] == "boss":
            uses = ", ".join(ref["no"] for ref in data["uses"])
            self.band.setText("보스 문제입니다. 이 던전의 %s에서 익힌 기술을 함께 씁니다." % uses if uses
                              else "보스 문제입니다. 이 던전에서 익힌 기술을 함께 씁니다.")
        self.band.setVisible(data["role"] == "boss")

    def show_docs(self, problem=True):
        if problem:
            self.problem_view.set_markdown(problem_markdown(self.data), self.data["base_dir"], self.lang)
        self.show_hints()
        self.show_explain()

    def show_hints(self):
        data = self.data
        hints, total = data["hints"], data["hint_total"]
        self.tabs.setTabText(1, "힌트 %d/%d" % (len(hints), total) if total else "힌트")
        if hints:
            text = "\n\n".join("### 힌트 %d\n\n%s" % (number, body) for number, body in enumerate(hints, 1))
        elif total:
            text = "힌트는 한 단계씩 열리고, 연 단계는 기록에 남습니다. 아래 [힌트 1 보기]를 누르면 첫 힌트가 나옵니다."
        else:
            text = "이 문제에는 힌트가 없습니다."
        self.hint_view.set_markdown(text, data["base_dir"], self.lang)
        left = total - len(hints)
        self.hint_btn.setText("힌트 %d 보기" % (len(hints) + 1))
        self.hint_btn.setVisible(left > 0)
        self.hint_note.setText("힌트를 모두 열었습니다." if total and not left else "")

    def show_explain(self):
        """해설이 열렸으면 explain.md, (보스면) 합성표, 기준 풀이, 더 풀어 볼 문제. 안 열렸으면 안내와 [포기하고 해설 보기]."""
        data, view = self.data, self.explain_view
        self.give_up_btn.setVisible(not data["explain_open"])
        if not data["explain_open"]:
            view.set_markdown("이 문제를 통과하면 해설이 열립니다.", data["base_dir"], self.lang)
            return
        if self.explain is None:
            try:
                self.explain = self.win.journey.open_explain(self.did, self.pid, self.lang)
            except SessionError as error:
                view.set_markdown(md_text(str(error)), data["base_dir"], self.lang)
                return
        explain = self.explain
        view.set_markdown(explain["markdown"], explain["base_dir"], self.lang)
        if explain["parts"]:
            view.add_para("합성표", "h2")
            view.add_table(["이 보스에서 하는 일", "익힌 문제"], [[part["text"], ", ".join(part["nos"])] for part in explain["parts"]])
        code = explain["solution"].get(self.lang)
        if code:
            view.add_code("기준 풀이 (%s)" % LANG_LABEL[self.lang], code, self.lang)
        if explain["similar"]:
            view.add_para("더 풀어 볼 문제", "h2")
            for item in explain["similar"]:
                view.add_para(similar_text(item), link=item.get("url"))

    def show_result(self):
        self.code_panel.show_console(self.results.get((self.did, self.pid, self.lang), ""))

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
            self.status.setText("")
            self.lang_bar.set_lang(self.lang)
            self.lang_bar.note.show()
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
            self.lang_bar.note.hide()
        self.lang, self.data = lang, data
        self.find_bar.dismiss(select=False)
        self._show_code()
        self.status.setText("")
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

    # 자동 저장

    def on_code_changed(self, text):
        if self.data is None:
            return
        self.dirty[(self.did, self.pid, self.lang)] = text
        self.save_timer.start()

    def flush(self, offer=True, commit=True):
        """대기 중인 코드를 파일에 쓰고, 다 썼으면 True 를 돌려줌. commit 이면 조합 중인 한글부터 확정함.
        저장하지 못하면 상태 줄에 이유를 쓰고, offer 면 대화상자로도 알림(부른 쪽이 직접 알릴 때는 offer=False)."""
        if commit:
            QGuiApplication.inputMethod().commit()
        self.save_timer.stop()
        if not self.dirty:
            return True
        for key, text in list(self.dirty.items()):
            try:
                self.win.journey.save_code(key[0], key[1], key[2], text)
            except (SessionError, OSError) as error:
                self.status.setText("저장하지 못했습니다: %s" % error)
                if offer:
                    self.fail("save", error)
                return False
            del self.dirty[key]
        self.status.setText("%s 에 자동 저장했습니다." % datetime.datetime.now().strftime("%H:%M:%S"))
        return True

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

    def set_busy(self, busy, text=""):
        """실행·채점하는 파일과 화면이 어긋나지 않게 편집기·탭·단추를 잠그고 [중지]만 켬."""
        for widget in (self.code_panel, self.tabs, self.lang_bar, self.map_btn, self.cases_btn, self.run_btn, self.grade_btn):
            widget.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")

    def run_code(self):
        if self.data is None or not self.flush():
            return
        did, pid, lang = self.did, self.pid, self.lang
        self.live = {"cases": []}
        self.code_panel.show_console('<body><p class="muted">실행 중입니다.</p></body>')
        self.win.run_job("코드를 실행하는 중입니다.", caught(lambda report, cancel: self.win.journey.run(did, pid, lang, report, cancel)),
                         lambda result: self._ran((did, pid, lang), result), on_fail=self._failed, on_progress=self.on_progress)

    def grade(self):
        if self.data is None or not self.flush():
            return
        did, pid, lang = self.did, self.pid, self.lang
        self.live = {"groups": []}
        self.code_panel.show_console('<body><p class="muted">채점을 준비하는 중입니다.</p></body>')
        self.win.run_job("채점하는 중입니다.", caught(lambda report, cancel: self.win.journey.grade(did, pid, lang, report, cancel)),
                         lambda result: self._graded((did, pid, lang), result), on_fail=self._failed, on_progress=self.on_progress)

    def on_progress(self, event):
        """워커가 보낸 진행 알림. 문구는 상태 줄에, 끝난 테스트 줄은 결과 칸에 붙임."""
        if event.get("kind") == "status":
            self.status.setText(event["text"])
            return
        if event.get("kind") != "case" or self.live is None:
            return
        if "groups" in self.live:
            groups = self.live["groups"]
            if not groups or groups[-1]["name"] != event.get("group"):
                groups.append({"name": event.get("group"), "cases": []})
            groups[-1]["cases"].append(event["case"])
            markup = journey_html.grade_html(self.live, done=False)
        else:
            self.live["cases"].append(event["case"])
            markup = journey_html.run_html(self.live, done=False)
        self.code_panel.show_console(markup)
        bar = self.code_panel.console.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _ran(self, key, result):
        if isinstance(result, Failed):
            self._failed()
            self.fail("run", result.message)
            return
        self.live = None
        self.results[key] = journey_html.run_html(result)
        self.show_result()
        self.status.setText(journey_html.STOPPED_RUN if result.get("cancelled") else "코드 실행을 마쳤습니다.")
        self.code_panel.focus_input()

    def _graded(self, key, result):
        if isinstance(result, Failed):
            self._failed()
            self.fail("grade", result.message)
            return
        self.live = None
        self.results[key] = journey_html.grade_html(result)
        self.show_result()
        if result.get("cancelled"):
            self.status.setText(journey_html.STOPPED_GRADE)
            return
        self.status.setText("채점을 마쳤습니다. 합계 %.1f점입니다." % (result.get("score") or 0.0))
        self.refresh()
        if result.get("cleared"):
            self.celebrate()

    def _failed(self):
        self.live = None
        self.show_result()

    def stop(self):
        """도는 실행·채점에 멈추라고 알림. 결과는 끝난 줄까지만 돌아오고 기록되지 않음."""
        job = getattr(self.win, "job", None)
        if job is not None:
            job[0].cancel.set()
            self.status.setText("중지하는 중입니다.")

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
        """서비스 오류를 하던 행동의 이름("코드 실행")을 제목으로 한 창에 보임. 내부 id 나 원문은 [자세히]로 넘김(journey_text.error_text)."""
        title, text, detail = error_text(action, error)
        self.win.ask(title, text, detail=detail)

    def on_link(self, url):
        """결과 칸의 [보스에 도전하기]."""
        if url != journey_html.BOSS_LINK:
            return
        boss = next((row["id"] for row in self.win.journey.dungeon(self.did)["problems"] if row["role"] == "boss"), None)
        if boss:
            self.win.open_problem(self.did, boss)

    def open_cases(self):
        if self.data is None:
            return
        did, pid = self.did, self.pid
        self.cases_dialog = CasesDialog(self, self.data, self.lang, lambda cases: self.win.journey.save_cases(did, pid, cases),
                                        self._cases_saved)
        self.cases_dialog.show()

    def _cases_saved(self, cases):
        self.data["cases"] = cases
        self.status.setText("테스트 케이스 %d개를 저장했습니다. [코드 실행]을 누르면 입출력 예와 함께 실행합니다." % len(cases))

    # 테마 · 글자 크기

    def restyle(self):
        """글자 크기나 테마가 바뀌면 부름. 지문·힌트·해설과 결과 칸에 CSS 를, 편집기에 글꼴을 다시 주고 읽던 자리는 지킴.
        지문·힌트·해설은 여행용 CSS(theme.journey_css)로, 기준 풀이는 문서 코드와 같은 code 크기로, 결과 칸은 본문 CSS 로 그림."""
        css, font = theme.doc_css(self.win.zoom), theme.code_font(self.win.zoom)
        for view in (self.problem_view, self.hint_view, self.explain_view):
            view.restyle(theme.journey_css(), theme.code_font(theme.text_px() - 1))
        self.code_panel.editor.setFont(font)
        console = self.code_panel.console
        bar = console.verticalScrollBar()
        place = bar.value()
        console.document().setDefaultStyleSheet(css)
        self.code_panel.show_console(self.code_panel.console_html)  # 스타일은 다음에 넣는 HTML 부터 적용됨
        bar.setValue(place)
