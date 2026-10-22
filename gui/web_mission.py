# -*- coding: utf-8 -*-
"""라이브 코딩 미션 화면: 위 막대(← 웹 면접 준비 · 제목 · 시계 하나) · 단계 표시 · 왼쪽 카드(읽기 안내, 지금 요구, 끝나면 해설·비교·점검 탭) ·
오른쪽 카드(미션 정보, 검사 결과, 끝나면 요약과 이어서 할 일) · 아래 막대(왼쪽 끝 파괴 글자 단추와 도구 단추, 오른쪽 끝 주 단추 하나).
동작 결과 한 문장(status)은 위 막대의 제목 오른쪽에 보임.

상태(받기 전·읽는 중·실전 중·끝남)와 시계는 서비스가 record.json 의 시각에서 계산한 값에, 그 값을 받은 뒤 흐른 초를 더해 보여 줌.
그래서 프로그램을 껐다 켜도 시계가 이어 흐르고, 테스트는 서비스의 시각과 이 화면의 clock 을 바꿔 끼워 시계를 돌림.
검사와 끝내기(숨긴 검사)는 창의 run_job 으로 워커에서 돌림. [폴더 열기]는 open_folder 가 맡고, 테스트는 창의 open_folder 를
가짜로 바꿔 실제로 편집기를 띄우지 않음.
[화면 띄우기]는 서비스가 미션 폴더에서 vite 를 띄우면 창의 open_url 로 주소를 엶. 다시 누르거나, 이 화면을 떠나거나(창을 내려 둔 것은 빼고),
프로그램을 닫으면 서버를 끔. [테스트 돌리기]는 미션 폴더의 내 테스트를 npm test 처럼 돌림. 둘 다 npm 과 PowerShell 을 거치지 않음.
두 카드의 폭은 어느 상태에서나 7:5 이고, 위 막대·단계 표시·아래 막대는 고정이며 카드 안만 스크롤함."""
import os
import re
import shutil
import subprocess
import sys
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QPlainTextEdit, QScrollArea, QSizePolicy, QStackedWidget, QWidget

import mdlite
import study
from gui import kit, theme
from gui.docview import DocView, FigureView, TextPiece, keep_lang
from gui.journey_page import md_text
from gui.web_setup import SetupDialog
from gui.web_text import clock_text
from webprep import dev, service
from webprep.service import WebError

MAC_EDITORS = (("Cursor", "/Applications/Cursor.app"), ("Visual Studio Code", "/Applications/Visual Studio Code.app"))
LANG = "javascript"  # 지문·해설의 코드 블록은 언어 표시가 tsx 라 어느 언어를 줘도 모두 보임
DOC_WIDTH = 640  # 읽는 글의 단 폭
STEP_STATE = {"done": "done", "pass": "done", "skip": "skip", "open": "now", "locked": "lock"}  # 서비스의 단계 결과 → 단계 표시의 상태
FINISH_TEXT = "지금 상태로 기록을 남기고 해설을 엽니다. 남은 단계는 통과하지 않은 채 끝나고, 다시 풀려면 처음부터 다시 해야 합니다."
AGAIN_TEXT = "미션 폴더의 코드를 처음 상태로 되돌립니다. 지금 코드는 지워집니다. 남기려면 먼저 첫 화면에서 제출하세요."
SKIP_TEXT = "이 단계를 건너뛰면 기록에 넘어감으로 남고 다음 단계가 열립니다."
NO_STACK_TEXT = "%s\n받은 코드를 읽고 고칠 수는 있지만 검사는 검사 도구를 설치한 뒤에 됩니다."
AI_TEXT = "에디터의 AI 자동완성을 껐습니다"
AI_NOTE = "표시하지 않아도, 읽기 시간이 남아 있어도 실전을 시작할 수 있습니다."
GET_NOTE = "미션을 받으면 템플릿 코드가 내 폴더로 복사되고 읽기 시간이 시작됩니다."
SERVE_ON, SERVE_OFF = "화면 띄우기", "화면 끄기"
SERVE_STOPPED = "화면 서버가 멈췄습니다."
SERVE_TIP = "미션 폴더에서 npm run dev 와 같은 화면 서버를 띄우고 브라우저로 엽니다. 다시 누르면 끕니다."
AFTER_LEAVE_TEXT = "통과 뒤 질문에 아직 답하지 않았습니다. 지금 나가면 이 질문은 기록되지 않고 다음에 열 때 다음 단계부터 보입니다."
NO_CHECK_STEP0 = "이 단계는 말로 설명하는 단계라 자동 검사가 없습니다."
NO_CHECK_YET = "아직 검사하지 않았습니다."
CHECK_HINT = "검사하기를 누르면 1단계부터 지금 단계까지의 검사가 돌고 결과가 여기에 나옵니다."
FIX_NOTE = "고친 뒤 다시 검사하세요."
SHORTCUT = "Ctrl+Enter (맥은 Cmd+Enter)"
RAW_MAX = 240  # 검사 원문 상자의 가장 큰 높이
STATUS_WIDTH = 420  # 위 막대의 상태 글 폭. 넘으면 줄을 바꿈(두 줄까지)
_popen = subprocess.Popen  # 테스트가 가짜로 바꿔 끼움
_startfile = getattr(os, "startfile", None)


def open_folder(path, settings=None, platform=None, exists=os.path.exists, which=shutil.which):
    """미션 폴더를 편집기로 엶. macOS 는 Cursor, VS Code 순으로 찾아 `open -a` 로 열고 없으면 Finder 로, Windows 는 PATH 의 code 로
    열고 없으면 탐색기로, 그 밖에는 xdg-open 으로 엶. 고른 편집기는 QSettings web/editor 에 기억해 다음에는 그것부터 씀.
    돌려주는 글은 상태 줄에 보임."""
    platform = platform or sys.platform
    remembered = settings.value("web/editor", "", type=str) if settings is not None else ""
    try:
        if platform == "darwin":
            names = [name for name, _ in MAC_EDITORS]
            order = ([remembered] if remembered in names else []) + [name for name in names if name != remembered]
            for name in order:
                app = dict(MAC_EDITORS)[name]
                if exists(app):
                    _popen(["open", "-a", app, path])
                    if settings is not None:
                        settings.setValue("web/editor", name)
                    return "%s 에서 폴더를 열었습니다." % name
            _popen(["open", path])
            return "Finder 에서 폴더를 열었습니다."
        if platform == "win32":
            code = which("code") or which("code.cmd")
            if code:
                _popen([code, path], creationflags=study.NO_WINDOW)
                if settings is not None:
                    settings.setValue("web/editor", "Visual Studio Code")
                return "VS Code 에서 폴더를 열었습니다."
            if _startfile is not None:
                _startfile(path)
                return "탐색기에서 폴더를 열었습니다."
        _popen(["xdg-open", path])
        return "폴더를 열었습니다."
    except OSError as error:
        return "폴더를 열지 못했습니다: %s" % error


def quote_lines(text):
    return "\n".join("> " + line for line in (text or "").splitlines())


def said(text):
    """면접관 말. 은행 글이 '면접관:' 으로 시작하면 그 앞말을 뗌(회색 칸의 이름표가 대신함)."""
    text = (text or "").strip()
    for head in ("면접관:", "면접관 :"):
        if text.startswith(head):
            return text[len(head):].strip()
    return text


def request_markdown(step, hints, revealed=True):
    """지금 요구 칸의 마크다운(면접관 말은 회색 칸이 따로 보임): 설명, 검사가 확인하는 내용, 들은 힌트.
    0단계는 점검 항목이 아직 열리지 않았으면 언제 열리는지를 적음."""
    parts = []
    if step["note"]:
        parts.append(step["note"])
    if step["checks"]:
        parts.append("검사는 아래 내용을 확인합니다.\n" + "\n".join("- " + line for line in step["checks"]))
    if step["no"] == 0 and not revealed:  # 자동 검사가 없다는 말은 오른쪽 결과 칸에 한 번만 둠
        parts.append("설명을 마치면 점검 항목이 나옵니다. 목표 시간 %d분이 지나면 열립니다." % step["target_min"])
    for number, text in enumerate(hints, 1):
        parts.append("### 면접관 힌트 %d\n\n%s" % (number, text))
    return "\n\n".join(parts)


def brief_text(markdown):
    """읽기 안내의 첫 제목('# w03. 거래내역 불러오기')에서 미션 id 를 뗌. 내부 id 는 화면에 쓰지 않음."""
    return re.sub(r"\A(#+ )[a-z]+\d+\. ", r"\1", markdown or "")


def after_markdown(after):
    return "%d초 안에 소리 내어 답한 뒤, 아래에서 말한 항목에 표시하고 [답을 마쳤습니다]를 누르세요." % after["secs"]


WORDS = {"끝": "끝남", "잠김": "시작 전"}  # 서비스의 단계 낱말을 화면 낱말 사전으로 바꿈. 잠김은 단계 표시에서만 씀


def done_markdown(done, base_dir):
    """끝난 미션의 해설 탭: 단계별 결과, 그 아래 해설."""
    rows = []
    for row in done["steps"]:
        name = "%d단계 %s" % (row["no"], row["title"]) if row["title"] else "%d단계" % row["no"]
        label = WORDS.get(row["label"], row["label"])
        rows.append("- %s: **%s**%s" % (md_text(name), label, " (힌트 %d)" % row["hints"] if row["hints"] else ""))
    parts = ["## 단계별 결과", "\n".join(rows)]
    if done["explain"]:
        parts.append(figures_to_images(done["explain"], base_dir))
    return "\n\n".join(parts)


def summary_text(done, live_min):
    """끝난 미션의 요약 문장: 넘어간 단계, 걸린 시간과 넘긴 시간, 힌트 수, 숨긴 검사, 시도 번호."""
    parts = []
    skipped = [str(row["no"]) for row in done["steps"] if row["result"] == "skip"]
    if skipped:
        parts.append("%s단계는 넘어갔습니다." % ", ".join(skipped))
    timers = done["timers"]
    took = "실전에 %s 걸렸습니다." % clock_text(timers["live_elapsed"])
    if timers["live_over"]:
        took = "실전에 %s 걸려 목표 %d분을 %s 넘겼습니다." % (clock_text(timers["live_elapsed"]), live_min, clock_text(timers["live_over"]))
    parts.append(took)
    hints = sum(row["hints"] for row in done["steps"])
    if hints:
        parts.append("힌트를 %d번 들었습니다." % hints)
    hidden = done["hidden"]
    if hidden:
        if "error" in hidden:
            parts.append("숨긴 검사를 돌리지 못했습니다: %s" % hidden["error"])
        else:
            parts.append("숨긴 검사는 통과 %d개, 실패 %d개입니다." % (len(hidden["pass"]), len(hidden["fail"])))
    if done["try"] > 1:
        parts.append("%d번째 시도입니다." % done["try"])
    return " ".join(parts)


def figures_to_images(markdown, base_dir):
    """학습 페이지와 해설의 figure 블록을 그림 줄(![캡션](파일))로 바꿈. 그림 파일이 아직 없으면 캡션과 '그림 준비 중'만 남김.
    프레임·내용 설명은 그림 제작용 메모라 보이지 않음."""
    out, inside, file, caption = [], False, "", ""
    for line in markdown.splitlines():
        stripped = line.strip()
        if not inside and stripped == "```figure":
            inside, file, caption = True, "", ""
            continue
        if inside:
            if stripped == "```":
                inside = False
                if file and os.path.isfile(os.path.join(base_dir, file)):
                    out.append("![%s](%s)" % (caption.replace("]", ")"), file))
                else:
                    out.append("그림 준비 중. %s" % md_text(caption) if caption else "그림 준비 중.")
            elif stripped.startswith("파일:"):
                file = stripped[len("파일:"):].strip()
            elif stripped.startswith("캡션:"):
                caption = stripped[len("캡션:"):].strip()
            continue
        out.append(line)
    return "\n".join(out)


def took_text(result):
    """검사 전체에 걸린 시간 " (3.2초)". 가짜 실행기처럼 0.1초가 안 되면 빈 글."""
    return " (%.1f초)" % (result["ms"] / 1000.0) if result["ms"] >= 100 else ""


def first_line(text):
    """실패 문구의 첫 줄. 빈 줄은 건너뜀."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def diff_text(rows):
    """비교 탭의 글. 첫 줄에 다른 파일 수와 이름, 그 아래 파일마다 unified diff."""
    if not rows:
        return "모범 답안과 같습니다."
    head = "모범 답안과 다른 파일 %d개: %s" % (len(rows), ", ".join(row["file"] for row in rows))
    return head + "\n\n" + "\n\n".join("파일: %s\n%s" % (row["file"], row["diff"]) for row in rows)


class DiffHighlighter(QSyntaxHighlighter):
    """unified diff 의 줄 색. 더한 줄은 ok, 뺀 줄은 wrong, 위치 줄(@@)은 muted, 파일 줄은 굵게."""

    def highlightBlock(self, text):
        style = QTextCharFormat()
        if text.startswith("파일: ") or text.startswith("+++ ") or text.startswith("--- "):
            style.setFontWeight(700)
            style.setForeground(theme.qcolor("heading"))
        elif text.startswith("+"):
            style.setForeground(theme.qcolor("ok"))
        elif text.startswith("-"):
            style.setForeground(theme.qcolor("wrong"))
        elif text.startswith("@@"):
            style.setForeground(theme.qcolor("muted"))
        else:
            return
        self.setFormat(0, len(text), style)


CheckList = kit.CheckList  # 드릴 화면이 여기서 가져감


class Doc(QWidget):
    """스크롤하지 않는 마크다운 글. 카드 안에서 다른 위젯과 같이 스크롤되게 DocView 의 조각(TextPiece, FigureView)만 세로로 쌓음.
    pieces 는 쌓은 순서대로의 조각이고, 글 폭은 DOC_WIDTH 까지."""

    def __init__(self):
        super().__init__()
        self.box = kit.box(self, spacing=8)
        self.pieces = []
        self.css, self.code_font = theme.web_css(), theme.code_font()
        self.setMaximumWidth(DOC_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def clear(self):
        for piece in self.pieces:
            self.box.removeWidget(piece)
            piece.hide()
            piece.deleteLater()
        self.pieces = []

    def set_markdown(self, text, base_dir, lang):
        self.clear()
        run = []
        for block in keep_lang(mdlite.parse(text), lang):
            if block["t"] != "image":
                run.append(block)
                continue
            self._add_blocks(run)
            run = []
            try:
                piece = FigureView(os.path.join(base_dir, block["src"]), block["alt"])
            except OSError:
                piece = kit.para("그림을 찾을 수 없습니다: %s" % block["src"], "caption", "secondary")
            self._add(piece)
        self._add_blocks(run)
        self.setVisible(bool(self.pieces))

    def _add_blocks(self, blocks):
        if blocks:
            piece = TextPiece(mdlite.blocks_html(blocks), self.css)
            self._add(piece)

    def _add(self, widget):
        self.box.addWidget(widget)
        self.pieces.append(widget)

    def restyle(self, css, code_font):
        self.css, self.code_font = css, code_font
        for piece in self.pieces:
            if isinstance(piece, TextPiece):
                piece.restyle(css)
            elif isinstance(piece, FigureView):
                piece.draw()


class Column(QScrollArea):
    """카드 안의 스크롤 칸. 안쪽 여백 24 의 세로 상자(box)에 부른 쪽이 위젯을 넣음. 바탕은 카드의 surface 색."""

    def __init__(self, spacing=0):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.box = kit.box(self.inner, (24, 24, 24, 24), spacing)
        self.setWidget(self.inner)


class RawBox(QFrame):
    """검사 원문 상자: 회색 칸 안의 읽기 전용 코드 글. 높이는 RAW_MAX 까지이고 넘치면 안에서 스크롤함."""

    def __init__(self, text):
        super().__init__()
        self.setObjectName("well")
        box = kit.box(self, (4, 4, 4, 4))
        self.edit = QPlainTextEdit(text)
        self.edit.setObjectName("plain")
        self.edit.setReadOnly(True)
        self.edit.setFont(theme.code_font(-1))
        self.edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.edit.setMaximumHeight(RAW_MAX)
        box.addWidget(self.edit)

    def text(self):
        return self.edit.toPlainText()


class ResultPanel(Column):
    """검사 결과 칸. 맨 위에 통과 수와 진행 막대, 검사마다 꼬리표 줄, 실패 줄 아래 접힌 원문. text() 는 보이는 글을 모두 이은 것."""

    def __init__(self, on_toggle):
        super().__init__()
        self.on_toggle = on_toggle  # (검사 id, 펼쳤는지)
        self.head = kit.para("", "headline")
        self.bar = kit.progress()
        self.note = kit.para("", "caption", "secondary")
        self.hint = kit.para("", "body", "secondary")
        self.rows = QWidget()
        self.rows_box = kit.box(self.rows)
        self.box.addWidget(self.head)
        self.box.addSpacing(12)
        self.box.addWidget(self.bar)
        self.box.addSpacing(8)
        self.box.addWidget(self.note)
        self.box.addWidget(self.hint)
        self.box.addSpacing(16)
        self.box.addWidget(self.rows)
        self.box.addStretch(1)
        self.labels = []  # text() 가 이을 글들

    def _clear_rows(self):
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.labels = []

    def show_empty(self, text):
        """검사 결과가 아직 없을 때의 안내 한두 문장."""
        self._clear_rows()
        self.head.setText(NO_CHECK_YET)
        self.bar.hide()
        self.note.hide()
        self.hint.setText(text)
        self.hint.show()
        self.labels = [self.head, self.hint]

    def show_result(self, result, expanded):
        """검사 결과를 그림. expanded 는 원문을 펼친 검사 id 들."""
        self._clear_rows()
        total, passed = len(result["tests"]), len(result["pass"])
        self.head.setText("검사 %d개 중 %d개 통과" % (total, passed))
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(passed)
        kit.set_tone(self.bar, "success" if total and passed == total else "")
        self.bar.show()
        self.note.setText(FIX_NOTE if passed < total else ("%d단계를 통과했습니다." % result["open"] if result["passed"] else ""))
        self.note.setVisible(bool(self.note.text()))
        self.hint.hide()
        self.labels = [self.head, self.note]
        for line in result["warnings"]:
            self._add(kit.banner(line, "warning"), 8)
        for test in result["tests"]:
            ok = test["status"] == "pass"
            row = QWidget()
            row_box = QHBoxLayout(row)
            row_box.setContentsMargins(0, 16, 0, 16)
            row_box.setSpacing(12)
            tag = kit.badge("통과" if ok else "실패", "success" if ok else "danger")
            text = QWidget()
            text_box = kit.box(text, spacing=4)
            title = kit.para(test["title"])
            text_box.addWidget(title)
            self.labels += [tag, title]
            if not ok:
                why = kit.para(first_line(test["message"]), "caption", "secondary")
                why.setVisible(bool(why.text()))
                text_box.addWidget(why)
                self.labels.append(why)
                opened = test["id"] in expanded
                raw_btn = kit.button("원문 접기" if opened else "원문 보기", "text", "s")
                raw_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                raw_btn.clicked.connect(lambda checked=False, cid=test["id"], was=opened: self.on_toggle(cid, not was))
                holder = QWidget()
                holder_box = kit.box(holder, horizontal=True)
                holder_box.addWidget(raw_btn)
                holder_box.addStretch(1)
                text_box.addWidget(holder)
                if opened:
                    raw = RawBox("\n\n".join(part for part in (test["message"], test["detail"]) if part))
                    text_box.addWidget(raw)
                    self.labels.append(raw)
            took = kit.label("%.1f초" % (test["ms"] / 1000.0), "caption", "tertiary")
            row_box.addWidget(tag, 0, Qt.AlignmentFlag.AlignTop)
            row_box.addWidget(text, 1)
            row_box.addWidget(took, 0, Qt.AlignmentFlag.AlignTop)
            self._add(row)
            line = kit.frame("rowline")
            line.setFixedHeight(1)
            self.rows_box.addWidget(line)
        if result["broken"]:
            self._add(kit.banner("앞 단계 검사가 깨졌습니다: %s단계. 진행은 막지 않지만 고쳐 두세요." % ", ".join(str(k) for k in result["broken"]),
                                 "danger"), 8)

    def _add(self, widget, below=0):
        self.rows_box.addWidget(widget)
        if below:
            self.rows_box.addSpacing(below)
        if isinstance(widget, QFrame) and widget.objectName() == "banner":
            self.labels.append(widget.text)

    def text(self):
        """보이는 글을 모두 이은 것. 방금 만든 조각은 이벤트 루프가 돌기 전에는 아직 보이지 않으므로 숨김 표시만 봄."""
        return "\n".join(item.text() for item in self.labels if not item.isHidden())


class WebMissionPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.setProperty("clipboard", True)  # 검사 문구와 모범 답안 비교를 복사할 수 있음
        self.win = win
        self.mid, self.view, self.done = None, None, None
        self.fetched, self.clock = 0.0, time.monotonic
        self.results = {}  # 마지막 검사 결과 {미션: 결과}
        self.done_cache = {}  # 끝난 미션의 해설·비교 {(미션, 시도): finish 결과}. 파일을 모두 읽어 비교하므로 시도마다 한 번만 계산함
        self.expanded = set()  # [원문 보기]를 연 검사 id
        self.after, self.after_started = None, 0.0  # 통과 뒤 질문과 그것을 보인 때
        self.showing_brief, self.revealed, self.busy = False, False, False
        self.request_step = None  # 표시 항목을 만든 단계. 같은 단계를 다시 그릴 때 표시를 지킴
        self.setup_dialog = None
        self.stack_ok = False  # 화면 띄우기와 테스트 돌리기에 쓰는 Node 와 검사 도구가 있는지
        self.checking = False  # [검사하기]를 누른 뒤 결과가 오기 전

        root = kit.box(self)
        self.top = kit.TopBar("← 웹 면접 준비", "", steps=True)
        self.home_btn, self.title = self.top.back, self.top.title
        self.title.show()
        self.phase_note = kit.label("", "caption", "secondary")  # 받기 전: 읽기·실전 시간
        self.clock_box, self.clock_caption, self.timer_label = kit.clock("남은 시간")
        self.done_badge = kit.badge("끝남", "success")
        self.status = kit.para("", "caption", "secondary")  # 동작 결과 한 문장. 제목 오른쪽에 두 줄까지. 아래 막대는 단추로 차서 자리가 없음
        self.status.setMinimumWidth(1)
        self.status.setMaximumWidth(STATUS_WIDTH)
        self.top.row.insertWidget(2, self.status, 0, Qt.AlignmentFlag.AlignVCenter)
        for widget in (self.phase_note, self.clock_box, self.done_badge):
            self.top.add_right(widget)
        root.addWidget(self.top)
        stepper_frame = kit.frame("stepper")
        stepper_frame.setFixedHeight(theme.CONTROL["stepper"])
        stepper_box = kit.box(stepper_frame, (kit.MARGIN, 0, kit.MARGIN, 0), horizontal=True)
        self.stepper = kit.Stepper()
        stepper_box.addWidget(self.stepper)
        root.addWidget(stepper_frame)

        body = QWidget()
        body_box = kit.box(body, (kit.MARGIN, 24, kit.MARGIN, 24), 24, horizontal=True)
        left_card, left_box = kit.card(pad=0, spacing=0)
        self.left = QStackedWidget()
        left_box.addWidget(self.left)
        right_card, right_box = kit.card(pad=0, spacing=0)
        self.right = QStackedWidget()
        right_box.addWidget(self.right)
        body_box.addWidget(left_card, 7)
        body_box.addWidget(right_card, 5)
        root.addWidget(body, 1)

        # 왼쪽: 읽기 안내
        self.brief_view = DocView()
        self.brief_view.box.setContentsMargins(24, 24, 24, 24)
        self.brief_view.ruled = False
        self.brief_view.sheet.setMaximumWidth(DOC_WIDTH + 48)
        # 왼쪽: 지금 요구(실전 중)와 통과 뒤 질문
        self.request_page = Column()
        box = self.request_page.box
        self.step_caption = kit.label("", "caption", "tertiary")
        self.step_title = kit.para("", "headline")
        self.time_note = kit.label("", "caption", "secondary")
        self.time_left = kit.label("", "caption", "secondary")
        self.time_bar = kit.progress(thin=True)
        self.time_row = QWidget()
        time_box = kit.box(self.time_row, spacing=8)
        time_line = QHBoxLayout()
        time_line.setContentsMargins(0, 0, 0, 0)
        time_line.setSpacing(12)
        time_line.addWidget(self.time_note, 1)
        time_line.addWidget(self.time_left)
        time_box.addLayout(time_line)
        time_box.addWidget(self.time_bar)
        self.quote_well, quote_box = kit.well()
        self.quote_who = kit.label("면접관", "caption", "secondary", bold=True)
        self.quote_text = kit.para("")
        quote_box.addWidget(self.quote_who)
        quote_box.addWidget(self.quote_text)
        self.request_view = Doc()
        self.request_items = kit.CheckList()  # 0단계 점검 항목과 통과 뒤 질문의 표시 항목
        self.request_items.hide()
        self.hint_btn = kit.button("힌트 듣기", "secondary", "m")
        self.skip_btn = kit.button("이 단계 건너뛰기", "secondary", "m")
        self.skip_note = kit.label("", "caption", "tertiary")
        self.request_buttons = QWidget()
        buttons_box = kit.box(self.request_buttons, spacing=8, horizontal=True)
        buttons_box.addWidget(self.hint_btn)
        buttons_box.addWidget(self.skip_btn)
        buttons_box.addWidget(self.skip_note)
        buttons_box.addStretch(1)
        box.addWidget(self.step_caption)
        box.addSpacing(4)
        box.addWidget(self.step_title)
        box.addSpacing(16)
        box.addWidget(self.time_row)
        box.addSpacing(24)
        box.addWidget(self.quote_well)
        box.addSpacing(16)
        box.addWidget(self.request_view)
        box.addSpacing(8)
        box.addWidget(self.request_items)
        box.addSpacing(16)
        box.addWidget(self.request_buttons)
        box.addStretch(1)
        # 왼쪽: 끝남(해설 · 내 코드와 비교 · 스스로 점검)
        self.done_page = QWidget()
        done_box = kit.box(self.done_page)
        self.tabs = kit.TabBar(["해설", "내 코드와 비교", "스스로 점검"])
        self.tab_pages = QStackedWidget()
        self.done_view = DocView()
        self.done_view.box.setContentsMargins(24, 24, 24, 24)
        self.done_view.ruled = False
        self.done_view.sheet.setMaximumWidth(DOC_WIDTH + 48)
        diff_page = QWidget()
        diff_box = kit.box(diff_page, (24, 24, 24, 24), 8)
        self.mine_diff, self.template_diff = QPlainTextEdit(), QPlainTextEdit()
        self.highlighters = []
        for edit, name in ((self.mine_diff, "내 코드와 모범 답안"), (self.template_diff, "템플릿과 모범 답안")):
            edit.setObjectName("plain")
            edit.setReadOnly(True)
            edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            edit.setFont(theme.code_font(-2))
            self.highlighters.append(DiffHighlighter(edit.document()))
            diff_box.addWidget(kit.label(name, "caption", "tertiary"))
            diff_box.addWidget(edit, 1)
            diff_box.addSpacing(8)
        self.check_page = Column()
        self.done_items_title = kit.para("해당하는 항목에 표시하세요. 표시하면 바로 저장합니다.", "body", "secondary")
        self.done_items = kit.CheckList()
        self.saved_note = kit.label("", "caption", "tertiary")
        self.check_page.box.addWidget(self.done_items_title)
        self.check_page.box.addSpacing(8)
        self.check_page.box.addWidget(self.done_items)
        self.check_page.box.addSpacing(8)
        self.check_page.box.addWidget(self.saved_note)
        self.check_page.box.addStretch(1)
        for page in (self.done_view, diff_page, self.check_page):
            self.tab_pages.addWidget(page)
        done_box.addWidget(self.tabs)
        done_box.addWidget(self.tab_pages, 1)
        for page in (self.brief_view, self.request_page, self.done_page):
            self.left.addWidget(page)

        # 오른쪽: 미션 정보(받기 전 · 읽는 중)
        self.info_page = Column()
        box = self.info_page.box
        self.stack_banner = kit.banner("", "warning")
        self.stack_banner.hide()
        self.info_grid = QWidget()
        grid = QGridLayout(self.info_grid)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)
        self.info_values = {}
        for number, name in enumerate(("난이도", "시간", "단계")):
            grid.addWidget(kit.label(name, "caption", "tertiary"), number, 0, Qt.AlignmentFlag.AlignTop)
            value = kit.para("")
            self.info_values[name] = value
            grid.addWidget(value, number, 1)
        grid.setColumnStretch(1, 1)
        self.get_note = kit.para(GET_NOTE, "body", "secondary")
        self.notes_caption = kit.label("같이 읽을 노트", "caption", "tertiary")
        self.note_rows = kit.RowList(flush=True)
        self.ready_caption = kit.label("실전 전 확인", "caption", "tertiary")
        self.ai_box = kit.Check(AI_TEXT)
        self.ai_note = kit.label(AI_NOTE, "caption", "secondary")
        self.ai_note.setWordWrap(True)
        box.addWidget(self.stack_banner)
        box.addSpacing(16)
        box.addWidget(kit.label("미션 정보", "headline"))
        box.addSpacing(16)
        box.addWidget(self.info_grid)
        box.addSpacing(16)
        box.addWidget(self.get_note)
        box.addSpacing(32)
        box.addWidget(self.notes_caption)
        box.addWidget(self.note_rows)
        box.addSpacing(32)
        box.addWidget(self.ready_caption)
        box.addWidget(self.ai_box)
        box.addWidget(self.ai_note)
        box.addStretch(1)
        # 오른쪽: 검사 결과(실전 중)
        self.result_view = ResultPanel(self.toggle_raw)
        # 오른쪽: 끝남 요약과 이어서 할 일
        self.summary_page = Column()
        box = self.summary_page.box
        count_row = QHBoxLayout()
        count_row.setContentsMargins(0, 0, 0, 0)
        count_row.setSpacing(12)
        self.passed_count = kit.label("", "display")
        count_row.addWidget(self.passed_count, 0, Qt.AlignmentFlag.AlignBottom)
        count_row.addWidget(kit.label("통과한 단계", "caption", "secondary"), 0, Qt.AlignmentFlag.AlignBottom)
        count_row.addStretch(1)
        self.summary = kit.para("", "body", "secondary")
        self.next_rows = kit.RowList(flush=True)
        box.addLayout(count_row)
        box.addSpacing(8)
        box.addWidget(self.summary)
        box.addSpacing(24)
        box.addWidget(kit.label("이어서 할 일", "caption", "tertiary"))
        box.addWidget(self.next_rows)
        box.addStretch(1)
        for page in (self.info_page, self.result_view, self.summary_page):
            self.right.addWidget(page)

        # 아래 막대
        self.bar = kit.BottomBar()
        self.finish_btn = self.bar.add_tool(kit.button("실전 끝내기", "danger_text", "m"))
        self.again_btn = self.bar.add_tool(kit.button("다시 하기", "danger_text", "m"))
        self.folder_btn = self.bar.add_tool(kit.button("폴더 열기", "text", "m"))
        self.folder_btn.setToolTip("내 미션 폴더를 편집기(Cursor, VS Code)로 엽니다. 없으면 탐색기로 엽니다.")
        self.serve_btn = self.bar.add_tool(kit.button(SERVE_ON, "text", "m"))
        self.serve_btn.setToolTip(SERVE_TIP)
        self.test_btn = self.bar.add_tool(kit.button("테스트 돌리기", "text", "m"))
        self.test_btn.setToolTip("미션 폴더에서 npm test 와 같은 테스트를 돌립니다.")
        self.brief_btn = self.bar.add_tool(kit.button("안내 다시 보기", "text", "m"))
        self.busy_bar = kit.progress(thin=True)
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setFixedWidth(120)
        self.busy_bar.hide()
        self.bar.add_action(self.busy_bar)
        self.get_btn = self.bar.add_action(kit.button("미션 받기", "primary", "l"))
        self.start_btn = self.bar.add_action(kit.button("실전 시작", "primary", "l"))
        self.explain_btn = self.bar.add_action(kit.button("설명 끝내기", "primary", "l"))
        self.check_btn = self.bar.add_action(kit.button("검사하기", "primary", "l"))
        self.after_btn = self.bar.add_action(kit.button("답을 마쳤습니다", "primary", "l"))
        self.next_btn = self.bar.add_action(kit.button("다음 할 일 보기", "primary", "l"))
        self.primaries = (self.get_btn, self.start_btn, self.explain_btn, self.check_btn, self.after_btn, self.next_btn)
        for button in self.primaries:
            button.setToolTip(SHORTCUT)
        root.addWidget(self.bar)
        for widget in (self.phase_note, self.clock_box, self.done_badge, self.finish_btn, self.again_btn, self.serve_btn, self.test_btn,
                       self.brief_btn, self.skip_btn, self.skip_note, self.request_items) + self.primaries:
            widget.hide()
        self.shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.shortcut.activated.connect(self.press_primary)

        self.ticker = QTimer(self)
        self.ticker.setInterval(1000)
        self.ticker.timeout.connect(self.tick)
        self.home_btn.clicked.connect(self.go_home)
        self.brief_btn.clicked.connect(self.toggle_brief)
        self.folder_btn.clicked.connect(self.open_folder)
        self.serve_btn.clicked.connect(self.toggle_serve)
        self.test_btn.clicked.connect(self.run_tests)
        self.get_btn.clicked.connect(self.get)
        self.start_btn.clicked.connect(self.start)
        self.check_btn.clicked.connect(self.check)
        self.finish_btn.clicked.connect(self.ask_finish)
        self.again_btn.clicked.connect(self.ask_again)
        self.hint_btn.clicked.connect(self.hint)
        self.skip_btn.clicked.connect(self.ask_skip)
        self.explain_btn.clicked.connect(self.explain_done)
        self.after_btn.clicked.connect(self.answer_after)
        self.next_btn.clicked.connect(lambda: self.win.go_web())
        self.tabs.picked.connect(self.tab_pages.setCurrentIndex)
        self.done_items.changed.connect(self.save_self)
        self.done_view.linked.connect(lambda url: self.win.open_url(url))
        self.brief_view.linked.connect(lambda url: self.win.open_url(url))

    # 불러오기

    def load(self, mid):
        """미션을 화면에 올림. 읽을 수 없으면 WebError."""
        view = self.win.web.mission(mid)
        if mid != self.mid or view["phase"] != "reading":  # 읽는 중에 같이 읽을 노트를 보고 돌아오면 표시를 지키고, 그 밖에는 지움
            self.ai_box.box.setChecked(False)
        self.mid, self.view, self.done = mid, view, None
        self.fetched = self.clock()
        self.after, self.showing_brief, self.revealed = None, False, False
        self.expanded = set()
        self.status.setText("")
        if view["phase"] == "done":
            self.done = self.finished_view()
        self.show()

    def reload(self):
        """기록이 바뀐 뒤 같은 미션을 다시 읽음. 더는 열 수 없으면 False."""
        if self.mid is None:
            return False
        try:
            self.load(self.mid)
        except WebError as error:
            self.status.setText(str(error))
            return False
        return True

    def refresh(self):
        """동작 뒤 상태만 다시 읽음. 읽기 안내 보기와 통과 뒤 질문은 그대로 둠."""
        try:
            self.view = self.win.web.mission(self.mid)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.fetched = self.clock()
        if self.view["phase"] == "done" and self.done is None:
            self.done = self.finished_view()
        self.show()

    def finished_view(self):
        """끝난 미션의 해설·모범 답안 비교·점검 항목. 같은 시도는 한 번만 계산함."""
        key = (self.mid, self.view["try"])
        if key not in self.done_cache:
            self.done_cache[key] = self.win.web.finish(self.mid)
        return self.done_cache[key]

    def base_dir(self):
        return self.win.web.missions[self.mid]["dir"]

    def page_title(self, pid):
        """학습 노트의 제목. 은행에 없으면 id 그대로."""
        page = self.win.web.pages.get(pid) if self.win.web is not None else None
        return page["title"] if page else pid

    # 시계

    def elapsed(self):
        return max(0.0, self.clock() - self.fetched)

    def timers(self):
        """서비스가 준 시계에 그 뒤 흐른 초를 더한 값."""
        view = self.view
        out = dict(view["timers"])
        gone = int(self.elapsed())
        if out.get("reading_left") is not None:
            out["reading_left"] -= gone
        if view["phase"] == "live":
            out["live_elapsed"] = (out["live_elapsed"] or 0) + gone
            out["live_over"] = max(0, out["live_elapsed"] - view["live_min"] * 60)
            if out.get("step_target") is not None:
                out["step_elapsed"] = (out["step_elapsed"] or 0) + gone
                out["step_over"] = max(0, out["step_elapsed"] - out["step_target"])
                out["can_skip"] = out["step_elapsed"] >= out["step_target"]
        return out

    def _clock(self, caption, seconds, warn_under=0):
        """위 막대 시계에 남은 초를 보임. 0 아래면 넘긴 초를 + 로 빨갛게, warn_under 초 아래면 주황으로."""
        if seconds < 0:
            self.clock_caption.setText("시간 지남" if caption == "남은 시간" else caption.replace("남은 시간", "시간 끝"))
            self.timer_label.setText("+" + clock_text(-seconds))
            kit.set_tone(self.timer_label, "danger")
        else:
            self.clock_caption.setText(caption)
            self.timer_label.setText(clock_text(seconds))
            kit.set_tone(self.timer_label, "warning" if warn_under and seconds <= warn_under else "")

    def show_clock(self, timers):
        """위 막대 오른쪽: 받기 전은 읽기·실전 시간 한 줄, 읽는 중·실전 중·통과 뒤 질문은 시계 하나, 끝남은 끝남 꼬리표."""
        view, phase = self.view, self.view["phase"]
        self.phase_note.setVisible(phase == "none")
        self.clock_box.setVisible(phase in ("reading", "live") or self.after is not None)  # 마지막 단계의 통과 뒤 질문도 답 시계를 보임
        self.done_badge.setVisible(phase == "done" and self.after is None)
        if phase == "none":
            self.phase_note.setText("읽기 %d분 · 실전 %d분" % (view["prep_min"], view["live_min"]))
        elif self.after is not None:
            self._clock("답 시간", self.after["secs"] - int(self.clock() - self.after_started))
        elif phase == "reading":
            self._clock("읽기 남은 시간", timers["reading_left"] or 0)
        elif phase == "live":
            self._clock("남은 시간", view["live_min"] * 60 - (timers["live_elapsed"] or 0), warn_under=300)

    def show_step_time(self, timers):
        """지금 단계의 목표 시간 막대와 그 위 글. 20% 아래면 주황, 넘기면 빨강."""
        target, gone = timers.get("step_target"), timers.get("step_elapsed") or 0
        self.time_row.setVisible(target is not None and self.after is None)
        if target is None or self.after is not None:
            return
        left = target - gone
        self.time_note.setText("목표 %d분 중 %d분 지났습니다" % (target // 60, min(target, gone) // 60))
        self.time_bar.setRange(0, max(1, target))
        self.time_bar.setValue(min(target, gone))
        if left < 0:
            self.time_left.setText("+%s 지남" % clock_text(-left))
            tone = "danger"
        else:
            self.time_left.setText("%s 남음" % clock_text(left))
            tone = "warning" if left <= target * 0.2 else ""
        kit.set_tone(self.time_left, tone or "secondary")
        kit.set_tone(self.time_bar, tone)
        self.skip_note.setText("" if timers["can_skip"] else "%d분 뒤 열립니다" % max(1, (left + 59) // 60))

    def tick(self):
        if self.view is None or self.mid is None:
            return
        timers = self.timers()
        self.show_clock(timers)
        if self.view["phase"] == "live" and self.after is None:
            self.show_step_time(timers)
            self.skip_btn.setEnabled(bool(timers["can_skip"]) and not self.busy)
            current = self.view["current"]
            if current and current["no"] == 0 and not self.revealed and not self.showing_brief \
                    and timers["step_elapsed"] >= (timers["step_target"] or 0):
                self.show_request()  # 읽기 안내를 보는 중이면 돌아올 때 show() 가 엶
        self.sync_serve()

    def showEvent(self, event):
        super().showEvent(event)
        self.ticker.start()
        self.tick()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.ticker.stop()
        if not event.spontaneous():  # 창을 내려 둘 때는 화면 서버를 끄지 않음
            self.stop_serving(wait=False)

    # 그리기

    def show(self):
        view = self.view
        phase = view["phase"]
        self.title.setText(view["title"])
        self.stepper.set_steps((row["no"], row["title"], STEP_STATE.get(row["result"], "lock")) for row in view["steps"])
        for button in self.primaries:
            button.hide()
        self.get_btn.setVisible(phase == "none")
        self.start_btn.setVisible(phase == "reading")
        self.next_btn.setVisible(phase == "done" and self.after is None)
        self.finish_btn.setVisible(phase == "live")
        self.again_btn.setVisible(phase == "done" and self.after is None)
        self.brief_btn.setVisible(phase in ("live", "done"))
        for button in (self.serve_btn, self.test_btn):
            button.setVisible(phase != "none")
        stack = self.win.web.stack_state()
        self.stack_ok = bool(stack["node"] and stack["installed"] and stack["lock"])
        if phase in ("none", "reading"):
            self.brief_view.set_markdown(brief_text(view["brief"]), self.base_dir(), LANG)
            self.left.setCurrentWidget(self.brief_view)
            self.show_info(stack)
            self.right.setCurrentWidget(self.info_page)
        elif self.after is not None:  # 마지막 단계를 통과해 끝났어도 통과 뒤 질문에 먼저 답함
            self.right.setCurrentWidget(self.result_view)
            self.show_results()
            self.show_after()
        elif phase == "live":
            self.right.setCurrentWidget(self.result_view)
            self.show_results()
            self.show_request()
        else:
            self.right.setCurrentWidget(self.summary_page)
            self.show_done()
        if self.showing_brief and phase in ("live", "done"):
            self.brief_view.set_markdown(brief_text(view["brief"]), self.base_dir(), LANG)
            self.left.setCurrentWidget(self.brief_view)
        self.brief_btn.setText(("해설로 돌아가기" if phase == "done" else "요구로 돌아가기") if self.showing_brief else "안내 다시 보기")
        self.tick()
        self.sync_buttons()

    def show_info(self, stack):
        """받기 전·읽는 중의 오른쪽 카드: 미션 정보, 같이 읽을 노트, 실전 전 확인."""
        view = self.view
        self.stack_banner.text.setText(stack["problem"])
        self.stack_banner.setVisible(bool(stack["problem"]))
        self.info_values["난이도"].setText(view["level"])
        self.info_values["시간"].setText("읽기 %d분, 실전 %d분" % (view["prep_min"], view["live_min"]))
        last = len(view["targets"]) - 1
        self.info_values["단계"].setText("0~%d단계. 0단계는 말로 설명합니다." % last if last else "0단계만 있습니다. 말로 설명합니다.")
        self.get_note.setVisible(view["phase"] == "none")
        self.note_rows.clear()
        for pid in view["pages"]:
            row = self.note_rows.add(kit.Row(self.page_title(pid), data=pid))
            row.clicked.connect(lambda pid=pid: self.win.open_learn(pid, back=("mission", self.mid)))
        self.notes_caption.setVisible(bool(view["pages"]))
        self.note_rows.setVisible(bool(view["pages"]))
        for widget in (self.ready_caption, self.ai_box, self.ai_note):
            widget.setVisible(view["phase"] == "reading")

    def show_request(self):
        """지금 단계의 요구. 0단계는 목표 시간이 지나면 점검 항목이 열림."""
        view, step = self.view, self.view["current"]
        if not self.showing_brief:
            self.left.setCurrentWidget(self.request_page)
        if step is None:
            self.step_caption.hide()
            self.step_title.setText("열린 단계가 없습니다.")
            self.quote_well.hide()
            self.request_view.set_markdown("", "", LANG)
            self.request_items.set_items([])
            self.request_buttons.hide()
            return
        timers = self.timers()
        self.revealed = step["no"] == 0 and timers["step_elapsed"] >= (timers["step_target"] or 0)
        self.step_caption.setText("%d단계" % step["no"])
        self.step_caption.show()
        self.step_title.setText(step["title"])
        self.quote_who.setText("면접관")
        self.quote_text.setText(said(step["request"]))
        self.quote_well.setVisible(bool(step["request"]))
        self.request_view.set_markdown(request_markdown(step, step["hints"], self.revealed), self.base_dir(), LANG)
        kept = self.request_items.marks() if self.request_step == step["no"] else []
        self.request_step = step["no"]
        items = [(mdlite.inline_plain(text), "", "", "", n < len(kept) and kept[n]) for n, text in enumerate(step["self"])]
        self.request_items.set_items(items if self.revealed else [])
        self.request_items.set_enabled(not self.busy)
        self.explain_btn.setVisible(step["no"] == 0)
        self.explain_btn.setEnabled(self.revealed and not self.busy)
        self.check_btn.setVisible(step["no"] > 0)
        self.check_btn.setEnabled(step["no"] > 0 and not self.busy)
        self.after_btn.hide()
        self.hint_btn.setVisible(len(step["hints"]) < step["hint_total"])  # 힌트를 다 들으면 쓸 일이 없어 숨김
        self.hint_btn.setEnabled(not self.busy)
        self.hint_btn.setToolTip("들은 힌트 %d/%d. 누른 시각이 기록에 남습니다." % (len(step["hints"]), step["hint_total"]))
        self.skip_btn.setVisible(step["no"] > 0)
        self.skip_btn.setEnabled(bool(timers["can_skip"]) and not self.busy)
        self.skip_note.setVisible(step["no"] > 0)
        self.request_buttons.setVisible(len(step["hints"]) < step["hint_total"] or step["no"] > 0)
        self.show_step_time(timers)

    def show_after(self):
        after = self.after
        self.left.setCurrentWidget(self.request_page)
        self.step_caption.hide()
        self.step_title.setText("통과 뒤 질문")
        self.time_row.hide()
        self.quote_who.setText("면접관")
        self.quote_text.setText(said(after["ask"]))
        self.quote_well.show()
        self.request_view.set_markdown(after_markdown(after), "", LANG)
        kept = self.request_items.marks() if self.request_step == "after" else []
        self.request_step = "after"
        self.request_items.set_items([(mdlite.inline_plain(item["text"]), "필수" if item["need"] else "보충", "accent" if item["need"] else "",
                                       "", n < len(kept) and kept[n]) for n, item in enumerate(after["items"])])
        self.request_items.set_enabled(not self.busy)
        self.request_buttons.hide()
        for button in (self.explain_btn, self.check_btn):
            button.hide()
        self.after_btn.show()
        self.after_btn.setEnabled(not self.busy)

    def show_results(self):
        result = self.results.get(self.mid)
        if result is None:
            current = self.view["current"]
            self.result_view.show_empty(NO_CHECK_STEP0 if current is not None and current["no"] == 0 and self.after is None else CHECK_HINT)
        else:
            self.result_view.show_result(result, self.expanded)

    def show_done(self):
        done, view = self.done, self.view
        self.left.setCurrentWidget(self.done_page)
        self.done_view.set_markdown(done_markdown(done, self.base_dir()), self.base_dir(), LANG)
        ticks = done["self_ticks"] or {}
        self.done_items.set_items([(mdlite.inline_plain(item["text"]), "", "", "", ticks.get(item["key"])) for item in done["self_items"]])
        self.saved_note.setText("")
        self.tabs.set_visible(2, bool(done["self_items"]))
        if not done["self_items"] and self.tab_pages.currentWidget() is self.check_page:
            self.tabs.set_current(0)
            self.tab_pages.setCurrentIndex(0)
        self.mine_diff.setPlainText(diff_text(done["mine_diff"]))
        self.template_diff.setPlainText(diff_text(done["template_diff"]))
        steps = [row for row in done["steps"] if row["no"] > 0]
        self.passed_count.setText("%d/%d" % (sum(1 for row in steps if row["result"] == "pass"), len(steps)))
        self.summary.setText(summary_text(done, view["live_min"]))
        self.next_rows.clear()
        if done["followups"]:
            row = self.next_rows.add(kit.Row("이 미션의 꼬리 질문", "꼬리 질문", data=done["followups"]))
            row.clicked.connect(self.open_followups)
        for pid in done["pages"]:
            row = self.next_rows.add(kit.Row(self.page_title(pid), "학습 노트", data=pid))
            row.clicked.connect(lambda pid=pid: self.win.open_learn(pid, back=("mission", self.mid)))
        self.next_rows.setVisible(bool(self.next_rows.rows))

    def sync_buttons(self):
        busy = self.busy
        for button in (self.home_btn, self.brief_btn, self.get_btn, self.start_btn, self.finish_btn, self.again_btn, self.after_btn, self.next_btn):
            button.setEnabled(not busy)
        for row in self.note_rows.rows + self.next_rows.rows:
            row.setEnabled(not busy)
        received = self.view is not None and os.path.isdir(self.view["dir"])
        self.folder_btn.setEnabled(not busy and received)
        for button in (self.serve_btn, self.test_btn):
            button.setEnabled(not busy and received and self.stack_ok)
        if self.view is not None and self.view["phase"] == "live" and not busy:
            step = self.view["current"]
            self.check_btn.setEnabled(step is not None and step["no"] > 0 and self.after is None)
            self.hint_btn.setEnabled(step is not None and len(step["hints"]) < step["hint_total"])
            self.explain_btn.setEnabled(self.revealed)
            self.skip_btn.setEnabled(bool(self.timers()["can_skip"]))
        else:
            for button in (self.check_btn, self.hint_btn, self.explain_btn, self.skip_btn):
                button.setEnabled(False)
        if not busy and not self.checking:
            self.check_btn.setText("검사하기")
        self.request_items.set_enabled(not busy)
        self.done_items.set_enabled(not busy)

    def set_busy(self, busy, text=""):
        self.busy = busy
        if not busy:
            self.checking = False
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")
        self.sync_buttons()

    def press_primary(self):
        """Ctrl+Enter. 보이고 켜진 주 단추를 누름."""
        for button in self.primaries:
            if button.isVisible() and button.isEnabled():
                button.click()
                return

    # 동작

    def toggle_brief(self):
        self.showing_brief = not self.showing_brief
        self.show()

    def go_home(self):
        """[← 웹 면접 준비]. 통과 뒤 질문에 답하는 중이면 그 질문이 기록되지 않는다고 알리고 물음."""
        if self.after is not None:
            self.win.ask("통과 뒤 질문", AFTER_LEAVE_TEXT, (("나가기", "leave", "danger"), ("닫기", "")), lambda key: self.win.go_web())
            return
        self.win.go_web()

    def open_folder(self):
        if self.view is not None:
            self.status.setText(self.win.open_folder(self.view["dir"]))

    def serving(self):
        """이 미션의 화면 서버가 돌고 있으면 서비스의 serving() 값, 아니면 None."""
        info = self.win.web.serving() if self.win.web is not None else None
        return info if info and info["running"] and info["mid"] == self.mid else None

    def sync_serve(self):
        """[화면 띄우기] 단추를 서버 상태에 맞춤. 띄운 서버가 스스로 멈췄으면 치우고 대화상자로 서버의 마지막 출력을 보임."""
        info = self.serving()
        if self.serve_btn.text() == SERVE_OFF and info is None:
            server = self.win.web.server if self.win.web is not None else None
            tail = server.tail(6, wait=False) if server is not None else ""
            self.stop_serving()
            self.status.setText(SERVE_STOPPED)
            if tail.strip():
                self.win.ask("화면 서버", "%s 다시 띄우려면 [화면 띄우기]를 누르세요.\n\n서버가 마지막으로 남긴 출력입니다.\n%s" % (SERVE_STOPPED, tail))
        self.show_serving(info)

    def show_serving(self, info):
        """[화면 띄우기] 단추의 글자와 툴팁을 바꿈. 서버가 돌면 툴팁에 주소를 둠."""
        self.serve_btn.setText(SERVE_OFF if info else SERVE_ON)
        self.serve_btn.setToolTip("%s 에서 화면 서버가 돌고 있습니다. 누르면 끕니다." % info["url"] if info else SERVE_TIP)

    def toggle_serve(self):
        """[화면 띄우기]면 워커에서 서버를 띄우고, [화면 끄기]면 끔."""
        if self.serving() is not None:
            self.stop_serving(wait=False)
            self.status.setText("화면을 껐습니다.")
            return
        mid = self.mid
        self.win.run_job("화면을 띄우는 중입니다.", lambda: self.win.web.serve(mid), self._served)

    def _served(self, info):
        if self.win.close_pending:  # 띄우는 사이에 창을 닫았으면 브라우저를 열지 않음. 서버는 창을 닫으며 끔
            return
        self.show_serving(info)
        self.win.open_url(info["url"])
        self.status.setText("화면을 띄웠습니다: %s" % info["url"])

    def stop_serving(self, wait=True):
        """화면 서버를 끄고 단추를 되돌림. wait 가 거짓이면 프로세스가 끝나기를 기다리지 않음(화면이 멈추지 않게)."""
        if self.win.web is not None:
            self.win.web.stop_serving(wait)
        self.show_serving(None)

    def run_tests(self):
        """워커에서 내 테스트를 돌림. 진행 알림은 없고, 창을 닫으면 run_job 의 취소 신호로 vitest 를 끊음."""
        mid = self.mid
        self.win.run_job("내 테스트를 돌리는 중입니다.", lambda report, cancel: self.win.web.own_tests(mid, cancel), self._tested,
                         on_progress=lambda event: None)

    def _tested(self, result):
        """상태 줄에 요약을 쓰고, 실패가 있으면 첫 실패의 앞 줄을 대화상자로 보임. 실패가 여럿이면 [자세히]에 모두 둠.
        창을 닫아 멈춘 테스트(None)는 알리지 않음."""
        if result is None:
            return
        line = dev.summary(result)
        self.status.setText(line)
        fails = result["fails"]
        if fails:
            detail = "\n\n".join(dev.failure_text(fail) for fail in fails) if len(fails) > 1 else ""
            self.win.ask("내 테스트", "%s\n\n%s" % (line, dev.failure_text(fails[0])), detail=detail)

    def get(self):
        """[미션 받기]. 검사 도구가 없으면 설치를 먼저 권함."""
        stack = self.win.web.stack_state()
        if stack["problem"]:
            self.win.ask("검사 도구", NO_STACK_TEXT % stack["problem"], (("설치하기", "install"), ("그냥 받기", "get", "close"), ("닫기", "")),
                         self._get_choice)
            return
        self._get(False)

    def _get_choice(self, key):
        if key == "get":
            self._get(False)
        elif key == "install":
            self.setup_dialog = SetupDialog(self.win)
            self.setup_dialog.finished.connect(self._after_setup)
            self.setup_dialog.show()

    def _after_setup(self, _):
        """설치 창을 닫은 뒤. 설치됐으면 과제를 받고, 아니면 받기 전 그대로 둠."""
        if not self.win.web.stack_state()["problem"]:
            self._get(False)

    def _get(self, again):
        self.stop_serving()  # 다시 하기는 서버가 지켜보는 폴더를 지우고 새로 씀
        try:
            self.win.web.get(self.mid, again)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.results.pop(self.mid, None)
        self.load(self.mid)
        self.status.setText("읽기 %d분이 시작되었습니다." % self.view["prep_min"])

    def start(self):
        try:
            self.win.web.start(self.mid, self.ai_box.box.isChecked())
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.load(self.mid)
        self.status.setText("실전 %d분이 시작되었습니다." % self.view["live_min"])

    def explain_done(self):
        try:
            self.win.web.explain_done(self.mid, self.request_items.marks())
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.refresh()
        self.status.setText("1단계가 열렸습니다.")

    def hint(self):
        try:
            hint = self.win.web.hint(self.mid)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.refresh()
        self.status.setText("힌트 %d을 들었습니다." % hint["n"])

    def ask_skip(self):
        self.win.ask("이 단계 건너뛰기", SKIP_TEXT, (("건너뛰기", "skip", "danger"), ("닫기", "")), lambda key: self.skip())

    def skip(self):
        try:
            result = self.win.web.skip(self.mid)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.refresh()
        self.status.setText("%d단계를 넘어갔습니다." % result["skipped"])

    def check(self):
        mid = self.mid
        self.checking = True
        self.check_btn.setText("검사 중")
        self.check_btn.setEnabled(False)
        if not self.win.run_job("검사하는 중입니다. 몇 초 걸립니다.", lambda: self.win.web.check(mid), lambda result: self._checked(mid, result),
                                on_fail=self.show_results):
            self.checking = False
            self.sync_buttons()

    def _checked(self, mid, result):
        self.results[mid] = result
        self.expanded = set()
        if mid != self.mid:
            return
        if result["passed"] and result["after"]:
            self.after, self.after_started = result["after"], self.clock()
        self.refresh()
        self.result_view.verticalScrollBar().setValue(0)
        # 통과 수는 결과 칸 머리가 보이므로 위 막대에는 걸린 시간만 적음(같은 말을 두 번 하지 않음)
        if result["finished"] and not result["after"]:
            self.status.setText("모든 단계를 끝냈습니다.")
        else:
            took = took_text(result).strip(" ()")
            self.status.setText("검사에 %s 걸렸습니다." % took if took else "")

    def toggle_raw(self, cid, opened):
        """[원문 보기]·[원문 접기]."""
        if opened:
            self.expanded.add(cid)
        else:
            self.expanded.discard(cid)
        self.show_results()

    def on_result_link(self, url):
        """옛 결과 칸의 링크 꼴(more:검사 id, fold:검사 id)로 원문을 펼치고 접음."""
        kind, _, cid = url.partition(":")
        if kind in ("more", "fold"):
            self.toggle_raw(cid, kind == "more")

    def answer_after(self):
        after = self.after
        marks = self.request_items.marks()
        need = [m for m, item in zip(marks, after["items"]) if item["need"]]
        extra = [m for m, item in zip(marks, after["items"]) if not item["need"]]
        secs = int(self.clock() - self.after_started)
        try:
            result = self.win.web.after_answer(self.mid, after["step"], need, extra, secs)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.after = None
        self.refresh()
        self.status.setText("판정: %s (%d초)" % (service.RESULT_LABEL[result["result"]], secs))

    def ask_finish(self):
        self.win.ask("실전 끝내기", FINISH_TEXT, (("끝내기", "finish", "danger"), ("닫기", "")), lambda key: self.finish())

    def finish(self):
        mid = self.mid
        self.win.run_job("끝내는 중입니다.", lambda: self.win.web.finish(mid), lambda done: self._finished(mid, done))

    def _finished(self, mid, done):
        self.done_cache[(mid, done["try"])] = done
        if mid != self.mid:
            return
        self.done, self.after = done, None
        self.refresh()
        self.status.setText("미션을 끝냈습니다.")

    def save_self(self):
        """스스로 점검에 표시하면 바로 기록함."""
        done = self.done
        if done is None or self.busy:
            return
        ticks = {item["key"]: mark for item, mark in zip(done["self_items"], self.done_items.marks())}
        try:
            self.win.web.self_check(self.mid, ticks)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        done["self_ticks"] = ticks
        self.saved_note.setText("저장했습니다")

    def open_followups(self):
        self.win.open_drill(self.done["followups"], back=("mission", self.mid))

    def ask_again(self):
        self.win.ask("미션 다시 하기", AGAIN_TEXT, (("다시 하기", "again", "danger"), ("닫기", "")), lambda key: self._get(True))

    # 테마 · 글자 크기

    def restyle(self):
        css, font = theme.web_css(self.win.zoom), theme.code_font(self.win.zoom)
        for view in (self.brief_view, self.request_view, self.done_view):
            view.restyle(css, font)
        for edit in (self.mine_diff, self.template_diff):
            edit.setFont(theme.code_font(self.win.zoom - 2))
        for highlighter in self.highlighters:
            highlighter.rehighlight()
        if self.view is not None:
            self.show_results()
            self.tick()
