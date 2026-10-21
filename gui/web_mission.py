# -*- coding: utf-8 -*-
"""라이브 코딩 미션 화면: 머리줄(웹 홈 · 제목 · 읽기/실전 시계 · 상태) · 단계 띠 · 왼쪽 지금 요구(또는 읽기 안내, 해설) · 오른쪽 검사 결과
(끝나면 모범 답안 비교와 스스로 점검 탭) · 아래 [폴더 열기] [화면 띄우기] [테스트 돌리기] [검사] [끝내기].

상태(받기 전·읽는 중·실전 중·끝남)와 시계는 서비스가 record.json 의 시각에서 계산한 값에, 그 값을 받은 뒤 흐른 초를 더해 보여 줌.
그래서 프로그램을 껐다 켜도 시계가 이어 흐르고, 테스트는 서비스의 시각과 이 화면의 clock 을 바꿔 끼워 시계를 돌림.
검사와 끝내기(숨긴 검사)는 창의 run_job 으로 워커에서 돌림. [폴더 열기]는 open_folder 가 맡고, 테스트는 창의 open_folder 를
가짜로 바꿔 실제로 편집기를 띄우지 않음.
[화면 띄우기]는 서비스가 미션 폴더에서 vite 를 띄우면 창의 open_url 로 주소를 엶. 다시 누르거나, 이 화면을 떠나거나(창을 내려 둔 것은 빼고),
프로그램을 닫으면 서버를 끔. [테스트 돌리기]는 미션 폴더의 내 테스트를 npm test 처럼 돌림. 둘 다 npm 과 PowerShell 을 거치지 않음.
왼쪽과 오른쪽 칸의 비율은 상태마다 다름(SPLIT): 받기 전·읽는 중은 읽기 안내가 넓고, 1단계부터는 검사 결과가 넓음."""
import html
import os
import shutil
import subprocess
import sys
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
                             QSizePolicy, QSplitter, QStackedWidget, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

import mdlite
import study
from gui import theme
from gui.docview import DocView
from gui.journey_page import md_text
from gui.web_home import clock_text, stack_line
from gui.web_setup import SetupDialog
from gui.widgets import LinkLabel, Para, centered
from webprep import dev, service
from webprep.service import WebError

MAC_EDITORS = (("Cursor", "/Applications/Cursor.app"), ("Visual Studio Code", "/Applications/Visual Studio Code.app"))
STEP_COLOR = {"done": "ok", "pass": "ok", "skip": "retry", "open": "primary", "locked": "faint"}
LANG = "javascript"  # 지문·해설의 코드 블록은 언어 표시가 tsx 라 어느 언어를 줘도 모두 보임
RESULT_CSS = "pre { white-space: pre-wrap; }"  # 검사 결과 칸은 가로 스크롤 없이 긴 실패 문구를 줄바꿈함
FINISH_TEXT = "지금 끝내면 남은 단계는 통과하지 않은 채 끝나고 해설이 열립니다. 끝낼까요?"
AGAIN_TEXT = ("내 미션 폴더를 템플릿으로 덮어쓰고 새 시도로 기록합니다. 지난 코드를 남기려면 먼저 첫 화면의 [제출(PR 올리기)]로 올려 두세요. "
              "다시 할까요?")
SKIP_TEXT = "이 요구를 넘어가면 기록에 '넘어감'으로 남고 다음 요구가 열립니다. 넘어갈까요?"
NO_STACK_TEXT = ("%s\n받은 코드를 읽고 고칠 수는 있지만 [검사]는 검사 도구를 설치한 뒤에 됩니다.")
AI_TEXT = "에디터의 AI 자동완성을 껐습니다"
SERVE_ON, SERVE_OFF = "화면 띄우기", "화면 끄기"
SERVE_STOPPED = "화면 서버가 멈췄습니다. 다시 띄우려면 [화면 띄우기]를 누르세요."
SERVE_TIP = "미션 폴더에서 npm run dev 와 같은 화면 서버를 띄우고 브라우저로 엽니다. 다시 누르면 끕니다."
AFTER_LEAVE_TEXT = "통과 뒤 질문에 아직 답하지 않았습니다. 지금 나가면 이 질문은 기록되지 않고 다음에 열 때 다음 단계부터 보입니다. 나갈까요?"
NO_CHECK_STEP0 = "0단계에는 자동 검사가 없습니다. 1단계부터 [검사] 결과가 여기에 나옵니다."
NO_CHECK_YET = "[검사]를 누르면 1단계부터 지금 단계까지의 검사가 돌고 결과가 여기에 나옵니다."
SPLIT = {"none": (840, 400), "reading": (840, 400), "step0": (700, 540), "live": (560, 680), "done": (660, 540)}  # 상태별 왼쪽·오른쪽 폭
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


def request_markdown(step, hints):
    """지금 요구 칸의 마크다운. 단계 제목과 목표, 면접관 요구, 설명, 검사가 확인하는 내용, 들은 힌트."""
    parts = ["## %d단계. %s" % (step["no"], step["title"]), "목표 %d분" % step["target_min"], quote_lines(step["request"])]
    if step["note"]:
        parts.append(step["note"])
    if step["checks"]:
        parts.append("검사는 아래 내용을 확인합니다.\n" + "\n".join("- " + line for line in step["checks"]))
    for number, text in enumerate(hints, 1):
        parts.append("### 면접관 힌트 %d\n\n%s" % (number, text))
    return "\n\n".join(parts)


def after_markdown(after):
    return "\n\n".join(["## 통과 뒤 질문", quote_lines(after["ask"]),
                        "%d초 안에 소리 내어 답한 뒤, 아래에서 말한 항목에 표시하고 [답을 마쳤습니다]를 누르세요." % after["secs"]])


def info_markdown(view, stack):
    """받기 전·읽는 중에 오른쪽에 보이는 미션 정보."""
    steps = ", ".join("%d단계 %d분" % (k, minutes) for k, minutes in enumerate(view["targets"]))
    lines = ["## 미션 정보", "- 난이도: %s" % md_text(view["level"]), "- 읽기 %d분, 실전 %d분" % (view["prep_min"], view["live_min"]),
             "- 목표 시간: %s (0단계는 코드 설명)" % steps]
    if view["pages"]:
        lines.append("- 묶인 학습 노트: %s" % ", ".join(view["pages"]))
    shown = study.shown_path(view["dir"])
    if shown.startswith(".."):  # 풀이 폴더가 저장소 밖이면 ../ 가 이어진 상대 경로보다 절대 경로가 읽기 쉬움
        shown = os.path.abspath(view["dir"])
    lines.append("- 내 폴더: `%s`" % shown)
    lines.append("- %s" % md_text(stack_line(stack)))
    if stack["problem"]:
        lines.append("\n%s" % md_text(stack["problem"]))
    if view["phase"] == "none":
        lines.append("\n[과제 받기]를 누르면 템플릿 코드가 내 폴더로 복사되고 읽기 시간이 시작됩니다. 읽기 안내대로 코드를 읽고, 준비되면 "
                     "[실전 시작]을 누릅니다.")
    else:
        lines.append("\n읽기 시간이 남아 있어도 [실전 시작]을 누를 수 있습니다. 실전이 시작되면 0단계(코드 설명)가 열립니다.")
    return "\n".join(lines)


def done_markdown(done, base_dir):
    """끝난 미션의 왼쪽 칸: 단계별 결과, 시간, 숨긴 검사, 해설."""
    rows = []
    for row in done["steps"]:
        name = "%d단계 %s" % (row["no"], row["title"]) if row["title"] else "%d단계" % row["no"]
        rows.append("- %s: **%s**%s" % (md_text(name), row["label"], " (힌트 %d)" % row["hints"] if row["hints"] else ""))
    timers = done["timers"]
    note = "실전 %s" % clock_text(timers["live_elapsed"])
    if timers["live_over"]:
        note += " (%s 넘김)" % clock_text(timers["live_over"])
    note += " · %d번째 시도" % done["try"]
    hidden = done["hidden"]
    if hidden:
        if "error" in hidden:
            note += " · 숨긴 검사를 돌리지 못했습니다: %s" % md_text(hidden["error"])
        else:
            note += " · 숨긴 검사: 통과 %d, 실패 %d" % (len(hidden["pass"]), len(hidden["fail"]))
    parts = ["## 단계별 결과", "\n".join(rows), note]
    if done["explain"]:
        parts.append(figures_to_images(done["explain"], base_dir))
    return "\n\n".join(parts)


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


def esc(text):
    return html.escape(str(text), quote=False)


def para(text, kind=""):
    return "<p%s>%s</p>" % (' class="%s"' % kind if kind else "", text)


def code_box(text):
    return ('<table width="100%%" cellspacing="0" cellpadding="8" border="0" style="margin-top:2px; margin-bottom:6px;">'
            '<tr><td class="codebox"><pre>%s</pre></td></tr></table>' % esc(text))


def took_text(result):
    """검사 전체에 걸린 시간 " (3.2초)". 가짜 실행기처럼 0.1초가 안 되면 빈 글. 검사별 시간과는 다른 값이라 머리줄이 아니라 상태 줄에 적음."""
    return " (%.1f초)" % (result["ms"] / 1000.0) if result["ms"] >= 100 else ""


def results_html(result, expanded=()):
    """검사 결과 칸의 HTML. 검사마다 통과·실패와 걸린 시간, 실패 문구(앞 12줄), DOM 덤프는 [자세히]로 접음."""
    total, passed = len(result["tests"]), len(result["pass"])
    parts = [para("검사 %d개 가운데 %d개 통과" % (total, passed), "h3")]
    for line in result["warnings"]:
        parts.append(para('<span class="retry">주의</span> %s' % esc(line)))
    for test in result["tests"]:
        ok = test["status"] == "pass"
        mark = '<span class="ok">통과</span>' if ok else '<span class="wrong">실패</span>'
        parts.append(para("<b>%s</b> %s <span class=\"muted\">%.1f초</span> · %s" % (esc(test["id"]), mark, test["ms"] / 1000.0,
                                                                                   esc(test["title"]))))
        if ok:
            continue
        if test["message"]:
            parts.append(code_box(test["message"]))
        if test["detail"]:
            if test["id"] in expanded:
                parts.append(code_box(test["detail"]))
                parts.append(para('<a href="fold:%s">접기</a>' % esc(test["id"])))
            else:
                parts.append(para('<a href="more:%s">자세히</a>' % esc(test["id"])))
    if result["broken"]:
        parts.append(para('<span class="wrong">앞 단계 검사가 깨졌습니다: %s단계. 진행은 막지 않지만 고쳐 두세요.</span>'
                          % ", ".join(str(k) for k in result["broken"])))
    if result["passed"]:
        parts.append(para('<span class="ok">%d단계를 통과했습니다.</span>' % result["open"]))
    else:
        parts.append(para("%d단계 검사가 아직 통과하지 않았습니다. 고친 뒤 다시 [검사]를 누르세요." % result["open"], "muted"))
    return "<body>%s</body>" % "".join(parts)


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


class CheckRow(QWidget):
    """표시 항목 한 줄: 체크 상자, 꼬리표([필수]·[보충]), 줄바꿈되는 글, 오른쪽의 작은 메모(지난번 표시). 글을 눌러도 상자가 바뀜."""

    def __init__(self, text, tag="", note=""):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.box = QCheckBox()
        self.tag = QLabel(tag)
        self.tag.setObjectName("tag")
        self.tag.setVisible(bool(tag))
        self.label = Para(text)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # 긴 항목은 칸 폭에서 줄바꿈함
        self.note = QLabel(note)
        self.note.setObjectName("caption")
        self.note.setVisible(bool(note))
        row.addWidget(self.box, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.tag, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.label, 1)
        row.addWidget(self.note, 0, Qt.AlignmentFlag.AlignTop)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.box.isEnabled():
            self.box.setChecked(not self.box.isChecked())
        event.accept()

    def resizeEvent(self, event):
        """줄바꿈한 글의 높이를 글 칸의 최소 높이로 둠. 칸이 여럿 겹친 세로 상자는 줄바꿈 높이를 끝까지 전하지 못해 한 줄만 보임."""
        super().resizeEvent(event)
        height = self.label.heightForWidth(max(1, self.label.width()))
        if height != self.label.minimumHeight():
            self.label.setMinimumHeight(height)
            self.updateGeometry()


class CheckList(QWidget):
    """CheckRow 를 세로로 쌓는 칸. set_items 로 통째로 바꿈."""

    def __init__(self):
        super().__init__()
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(6)
        self.rows = []

    def set_items(self, items):
        """items 는 (글, 꼬리표, 메모, 처음 표시) 목록."""
        for row in self.rows:
            self.box.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        for text, tag, note, checked in items:
            row = CheckRow(text, tag, note)
            row.box.setChecked(bool(checked))
            self.box.addWidget(row)
            self.rows.append(row)
        self.setVisible(bool(self.rows))

    def marks(self):
        return [1 if row.box.isChecked() else 0 for row in self.rows]

    def set_enabled(self, enabled):
        for row in self.rows:
            row.box.setEnabled(enabled)


class WebMissionPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        self.setProperty("clipboard", True)  # 검사 문구와 모범 답안 비교를 복사할 수 있음
        self.win = win
        self.mid, self.view, self.done = None, None, None
        self.fetched, self.clock = 0.0, time.monotonic
        self.results = {}  # 마지막 검사 결과 {미션: 결과}
        self.done_cache = {}  # 끝난 미션의 해설·비교 {(미션, 시도): finish 결과}. 파일을 모두 읽어 비교하므로 시도마다 한 번만 계산함
        self.split_key = None  # 지금 적용한 SPLIT 의 키. 같은 상태에서 다시 그릴 때는 사용자가 끈 비율을 지킴
        self.expanded = set()  # [자세히]를 연 검사 id
        self.after, self.after_started = None, 0.0  # 통과 뒤 질문과 그것을 보인 때
        self.showing_brief, self.revealed, self.busy = False, False, False
        self.request_step = None  # 표시 항목을 만든 단계. 같은 단계를 다시 그릴 때 표시를 지킴
        self.setup_dialog = None
        self.stack_ok = False  # 화면 띄우기와 테스트 돌리기에 쓰는 Node 와 검사 도구가 있는지

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 0)
        root.setSpacing(8)
        head = QHBoxLayout()
        self.home_btn = QPushButton("웹 홈")
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.level = QLabel()
        self.level.setObjectName("muted")
        self.timer_label = QLabel()
        self.timer_label.setObjectName("h2")
        self.timer_label.setTextFormat(Qt.TextFormat.RichText)
        self.phase_tag = QLabel()
        self.phase_tag.setObjectName("tag")
        head.addWidget(self.home_btn)
        head.addSpacing(8)
        head.addWidget(self.title, 1)
        head.addWidget(self.level)
        head.addSpacing(16)
        head.addWidget(self.timer_label)
        head.addSpacing(12)
        head.addWidget(self.phase_tag)
        root.addLayout(head)
        self.strip = LinkLabel()
        self.strip.setObjectName("muted")
        root.addWidget(self.strip)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.left = QStackedWidget()
        self.brief_view = DocView()
        self.request_page, self.request_view, request_box, request_row = self._doc_page()
        self.request_items = CheckList()  # 0단계 점검 항목과 통과 뒤 질문의 표시 항목
        self.request_items.hide()
        request_box.insertWidget(1, self.request_items)
        self.hint_btn = QPushButton("힌트 듣기")
        self.skip_btn = QPushButton("다음 요구로 넘어가기")
        self.explain_btn = QPushButton("설명 끝")
        self.explain_btn.setObjectName("primary")
        self.after_btn = QPushButton("답을 마쳤습니다")
        self.after_btn.setObjectName("primary")
        self.request_note = QLabel()
        self.request_note.setObjectName("muted")
        self.request_note.setMinimumWidth(1)
        request_row.addWidget(self.request_note, 1)
        for button in (self.hint_btn, self.skip_btn, self.explain_btn, self.after_btn):
            request_row.addWidget(button)
        self.done_page, self.done_view, _, done_row = self._doc_page()
        self.followup_btn = QPushButton("꼬리 질문 풀기")
        self.followup_btn.setObjectName("primary")
        self.page_btns = []
        self.done_row = done_row
        done_row.addStretch(1)
        done_row.addWidget(self.followup_btn)
        for page in (self.brief_view, self.request_page, self.done_page):
            self.left.addWidget(page)
        self.right = QStackedWidget()
        self.info_view = DocView()
        self.result_view = QTextBrowser()
        self.result_view.setOpenLinks(False)
        self.result_view.document().setDocumentMargin(14)
        self.diff_tabs = QTabWidget()
        self.mine_diff, self.template_diff = QPlainTextEdit(), QPlainTextEdit()
        self.highlighters = []
        for edit, name in ((self.mine_diff, "내 코드와 모범 답안"), (self.template_diff, "템플릿과 모범 답안")):
            edit.setReadOnly(True)
            edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            edit.setFont(theme.code_font(-2))
            self.highlighters.append(DiffHighlighter(edit.document()))
            self.diff_tabs.addTab(edit, name)
        self.check_tab = QWidget()  # 스스로 점검. 해설 칸을 가리지 않게 오른쪽 탭에 둠
        check_box = QVBoxLayout(self.check_tab)
        check_box.setContentsMargins(14, 12, 14, 12)
        check_box.setSpacing(10)
        self.done_items_title = Para("해당하는 항목에 표시하고 [점검 저장]을 누르세요. 표시는 기록에 남습니다.", "muted")
        self.done_items = CheckList()
        check_inner = QWidget()  # 항목 아래에 남는 자리를 비워 두어 줄이 늘어나지 않게 함
        inner_box = QVBoxLayout(check_inner)
        inner_box.setContentsMargins(0, 0, 0, 0)
        inner_box.addWidget(self.done_items)
        inner_box.addStretch(1)
        check_scroll = QScrollArea()
        check_scroll.setWidgetResizable(True)
        check_scroll.setFrameShape(QFrame.Shape.NoFrame)
        check_scroll.setWidget(check_inner)
        self.save_btn = QPushButton("점검 저장")
        self.save_btn.setObjectName("primary")
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(self.save_btn)
        check_box.addWidget(self.done_items_title)
        check_box.addWidget(check_scroll, 1)
        check_box.addLayout(save_row)
        self.diff_tabs.addTab(self.check_tab, "스스로 점검")
        for page in (self.info_view, self.result_view, self.diff_tabs):
            self.right.addWidget(page)
        split.addWidget(self.left)
        split.addWidget(self.right)
        split.setStretchFactor(0, 55)
        split.setStretchFactor(1, 45)
        split.setChildrenCollapsible(False)
        self.split = split
        root.addWidget(split, 1)

        bar = QFrame()
        bar.setObjectName("bar")
        bar_box = QHBoxLayout(bar)
        bar_box.setContentsMargins(4, 8, 4, 8)
        self.status = Para(name="muted")  # 작은 창에서는 두 줄로 넘어가 [검사] 안내가 잘리지 않음
        self.status.setMinimumWidth(1)
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedWidth(140)
        self.busy_bar.hide()
        self.brief_btn = QPushButton("읽기 안내 다시 보기")
        self.brief_btn.setObjectName("quiet")
        self.folder_btn = QPushButton("폴더 열기")
        self.folder_btn.setToolTip("내 미션 폴더를 편집기(Cursor, VS Code)로 엽니다. 없으면 탐색기로 엽니다.")
        self.serve_btn = QPushButton(SERVE_ON)
        self.serve_btn.setToolTip(SERVE_TIP)
        self.test_btn = QPushButton("테스트 돌리기")
        self.test_btn.setToolTip("미션 폴더에서 npm test 와 같은 테스트를 돌립니다.")
        self.ai_box = QCheckBox(AI_TEXT)
        self.get_btn = QPushButton("과제 받기")
        self.start_btn = QPushButton("실전 시작")
        self.check_btn = QPushButton("검사")
        self.finish_btn = QPushButton("끝내기")
        self.again_btn = QPushButton("다시 하기")
        for button in (self.get_btn, self.start_btn, self.check_btn):
            button.setObjectName("primary")
        bar_box.addLayout(centered(self.status), 1)
        bar_box.addWidget(self.busy_bar)
        bar_box.addWidget(self.brief_btn)
        bar_box.addSpacing(12)
        bar_box.addWidget(self.folder_btn)
        bar_box.addWidget(self.serve_btn)
        bar_box.addWidget(self.test_btn)
        bar_box.addWidget(self.ai_box)
        for button in (self.again_btn, self.finish_btn, self.get_btn, self.start_btn, self.check_btn):
            bar_box.addWidget(button)
        root.addWidget(bar)
        for widget in (self.ai_box, self.start_btn, self.check_btn, self.finish_btn, self.again_btn, self.brief_btn,
                       self.skip_btn, self.explain_btn, self.after_btn):  # 상태마다 보이는 단추만 남겨 창의 최소 폭을 넓히지 않음
            widget.hide()

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
        self.save_btn.clicked.connect(self.save_self)
        self.followup_btn.clicked.connect(self.open_followups)
        self.result_view.anchorClicked.connect(lambda url: self.on_result_link(url.toString()))
        self.done_view.linked.connect(lambda url: self.win.open_url(url))

    @staticmethod
    def _doc_page():
        """DocView 와 그 아래 단추 줄이 든 왼쪽 칸 하나. (칸, DocView, 세로 상자, 단추 줄)."""
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 8)
        box.setSpacing(8)
        view = DocView()
        row = QHBoxLayout()
        row.setContentsMargins(20, 0, 20, 0)
        box.addWidget(view, 1)
        box.addLayout(row)
        return page, view, box, row

    # 불러오기

    def load(self, mid):
        """미션을 화면에 올림. 읽을 수 없으면 WebError."""
        view = self.win.web.mission(mid)
        self.mid, self.view, self.done = mid, view, None
        self.fetched = self.clock()
        self.after, self.showing_brief, self.revealed = None, False, False
        self.expanded = set()
        self.ai_box.setChecked(False)
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

    def timer_html(self, timers):
        view = self.view
        over = '<span style="color: %s;">%s</span>' % (theme.color("wrong"), "%s")
        if self.after is not None:
            secs = int(self.clock() - self.after_started)
            text = "답 시간 %s / %s" % (clock_text(secs), clock_text(self.after["secs"]))
            if secs > self.after["secs"]:
                text += " · " + over % ("%s 넘김" % clock_text(secs - self.after["secs"]))
            return text
        if view["phase"] == "none":
            return "읽기 %d분 · 실전 %d분" % (view["prep_min"], view["live_min"])
        if view["phase"] == "reading":
            left = timers["reading_left"] or 0
            if left >= 0:
                return "읽기 남은 시간 %s" % clock_text(left)
            return "읽기 시간 끝 · " + over % ("%s 지남" % clock_text(-left))
        text = "실전 %s / %d:00" % (clock_text(timers["live_elapsed"]), view["live_min"])
        if view["phase"] == "done":
            text = "실전 %s 끝남" % clock_text(timers["live_elapsed"])
        if timers["live_over"]:
            text += " · " + over % ("%s 넘김" % clock_text(timers["live_over"]))
        return text

    def strip_html(self, timers):
        parts = []
        for row in self.view["steps"]:
            color, label = theme.color(STEP_COLOR.get(row["result"], "muted")), row["label"]
            if row["result"] == "open" and timers.get("step_target") is not None:
                gone = timers["step_elapsed"] or 0
                label += " (목표 %d분, %s %s)" % (row["target_min"], clock_text(abs(timers["step_target"] - gone)),
                                                "지남" if gone >= timers["step_target"] else "남음")
                parts.append('<b style="color: %s;">%d %s</b>' % (color, row["no"], esc(label)))
            else:
                parts.append('<span style="color: %s;">%d %s</span>' % (color, row["no"], esc(label)))
        return "단계 &nbsp;" + " &nbsp;·&nbsp; ".join(parts)

    def tick(self):
        if self.view is None or self.mid is None:
            return
        timers = self.timers()
        self.timer_label.setText(self.timer_html(timers))
        self.strip.setText(self.strip_html(timers))
        if self.view["phase"] == "live" and self.after is None:
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
        self.title.setText("%s %s" % (view["id"], view["title"]))
        self.level.setText(view["level"])
        self.phase_tag.setText(view["phase_label"])
        self.ai_box.setVisible(phase == "reading")
        self.get_btn.setVisible(phase == "none")
        self.start_btn.setVisible(phase == "reading")
        self.check_btn.setVisible(phase == "live")
        self.finish_btn.setVisible(phase == "live")
        self.again_btn.setVisible(phase == "done")
        self.brief_btn.setVisible(phase in ("live", "done"))
        self.folder_btn.setEnabled(os.path.isdir(view["dir"]) and not self.busy)
        stack = self.win.web.stack_state()
        self.stack_ok = bool(stack["node"] and stack["installed"] and stack["lock"])
        if phase in ("none", "reading"):
            self.brief_view.set_markdown(view["brief"], self.base_dir(), LANG)
            self.left.setCurrentWidget(self.brief_view)
            self.info_view.set_markdown(info_markdown(view, stack), "", LANG)
            self.right.setCurrentWidget(self.info_view)
        elif self.after is not None:  # 마지막 단계를 통과해 끝났어도 통과 뒤 질문에 먼저 답함
            self.right.setCurrentWidget(self.result_view)
            self.show_results()
            self.show_after()
        elif phase == "live":
            self.right.setCurrentWidget(self.result_view)
            self.show_results()
            self.show_request()
        else:
            self.right.setCurrentWidget(self.diff_tabs)
            self.show_done()
        if self.showing_brief and phase in ("live", "done"):
            self.brief_view.set_markdown(view["brief"], self.base_dir(), LANG)
            self.left.setCurrentWidget(self.brief_view)
        self.brief_btn.setText(("해설로 돌아가기" if phase == "done" else "요구로 돌아가기") if self.showing_brief else "읽기 안내 다시 보기")
        self.fit_split()
        self.tick()
        self.sync_buttons()

    def fit_split(self):
        """상태에 맞는 왼쪽·오른쪽 폭. 상태가 바뀔 때만 바꿈."""
        view = self.view
        key = view["phase"]
        if key == "live" and self.after is None and view["current"] is not None and view["current"]["no"] == 0:
            key = "step0"
        if key != self.split_key:
            self.split_key = key
            self.split.setSizes(list(SPLIT[key]))

    def show_request(self):
        """지금 단계의 요구. 0단계는 목표 시간이 지나면 점검 항목이 열림."""
        view, step = self.view, self.view["current"]
        if not self.showing_brief:
            self.left.setCurrentWidget(self.request_page)
        if step is None:
            self.request_view.set_markdown("열린 단계가 없습니다.", "", LANG)
            self.request_items.set_items([])
            return
        markdown = request_markdown(step, step["hints"])
        timers = self.timers()
        self.revealed = step["no"] == 0 and timers["step_elapsed"] >= (timers["step_target"] or 0)
        if step["no"] == 0 and not self.revealed:
            markdown += "\n\n설명을 마치면 점검 항목이 나옵니다. 목표 시간 %d분이 지나면 열립니다." % step["target_min"]
        self.request_view.set_markdown(markdown, self.base_dir(), LANG)
        kept = self.request_items.marks() if self.request_step == step["no"] else []
        self.request_step = step["no"]
        items = [(mdlite.inline_plain(text), "", "", n < len(kept) and kept[n]) for n, text in enumerate(step["self"])]
        self.request_items.set_items(items if self.revealed else [])
        self.request_items.set_enabled(not self.busy)
        self.explain_btn.setVisible(step["no"] == 0)
        self.explain_btn.setEnabled(self.revealed and not self.busy)
        self.hint_btn.setVisible(True)
        self.hint_btn.setEnabled(len(step["hints"]) < step["hint_total"] and not self.busy)
        self.hint_btn.setText("힌트 듣기 (%d/%d)" % (len(step["hints"]), step["hint_total"]) if step["hint_total"] else "힌트 없음")
        self.skip_btn.setVisible(step["no"] > 0)
        self.skip_btn.setEnabled(bool(timers["can_skip"]) and not self.busy)
        self.after_btn.setVisible(False)
        self.request_note.setText("말한 항목에 표시한 뒤 [설명 끝]을 누르세요." if step["no"] == 0 and self.revealed else "")
        self.check_btn.setEnabled(step["no"] > 0 and not self.busy)

    def show_after(self):
        after = self.after
        self.left.setCurrentWidget(self.request_page)
        self.request_view.set_markdown(after_markdown(after), "", LANG)
        kept = self.request_items.marks() if self.request_step == "after" else []
        self.request_step = "after"
        self.request_items.set_items([(mdlite.inline_plain(item["text"]), "필수" if item["need"] else "보충", "", n < len(kept) and kept[n])
                                      for n, item in enumerate(after["items"])])
        self.request_items.set_enabled(not self.busy)
        for button in (self.hint_btn, self.skip_btn, self.explain_btn):
            button.setVisible(False)
        self.after_btn.setVisible(True)
        self.after_btn.setEnabled(not self.busy)
        self.request_note.setText("")
        self.check_btn.setEnabled(False)

    def show_results(self):
        result = self.results.get(self.mid)
        if result is None:
            current = self.view["current"]
            text = NO_CHECK_STEP0 if current is not None and current["no"] == 0 and self.after is None else NO_CHECK_YET
            markup = '<body><p class="muted">%s</p></body>' % text
        else:
            markup = results_html(result, self.expanded)
        self.result_view.document().setDefaultStyleSheet(theme.doc_css(self.win.zoom) + RESULT_CSS)
        self.result_view.setHtml(markup)

    def show_done(self):
        done, view = self.done, self.view
        self.left.setCurrentWidget(self.done_page)
        self.done_view.set_markdown(done_markdown(done, self.base_dir()), self.base_dir(), LANG)
        ticks = done["self_ticks"] or {}
        self.done_items.set_items([(mdlite.inline_plain(item["text"]), "", "", ticks.get(item["key"])) for item in done["self_items"]])
        self.diff_tabs.setTabVisible(2, bool(done["self_items"]))
        self.followup_btn.setVisible(bool(done["followups"]))
        for button in self.page_btns:
            self.done_row.removeWidget(button)
            button.hide()
            button.deleteLater()
        self.page_btns = []
        for pid in done["pages"]:
            button = QPushButton("학습 노트 %s" % pid)
            button.clicked.connect(lambda checked=False, pid=pid: self.win.open_learn(pid, back=("mission", self.mid)))
            self.done_row.insertWidget(len(self.page_btns), button)
            self.page_btns.append(button)
        self.mine_diff.setPlainText(diff_text(done["mine_diff"]))
        self.template_diff.setPlainText(diff_text(done["template_diff"]))

    def sync_buttons(self):
        busy = self.busy
        for button in (self.home_btn, self.brief_btn, self.get_btn, self.start_btn, self.finish_btn, self.again_btn, self.save_btn,
                       self.followup_btn, self.after_btn):
            button.setEnabled(not busy)
        for button in self.page_btns:
            button.setEnabled(not busy)
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
        self.request_items.set_enabled(not busy)
        self.done_items.set_enabled(not busy)

    def set_busy(self, busy, text=""):
        self.busy = busy
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")
        self.sync_buttons()

    # 동작

    def toggle_brief(self):
        self.showing_brief = not self.showing_brief
        self.show()

    def go_home(self):
        """[웹 홈]. 통과 뒤 질문에 답하는 중이면 그 질문이 기록되지 않는다고 알리고 물음."""
        if self.after is not None:
            self.win.ask("통과 뒤 질문", AFTER_LEAVE_TEXT, (("나가기", "leave"), ("계속 답하기", "")), lambda key: self.win.go_web())
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
                self.win.ask("화면 서버", "%s\n\n서버가 마지막으로 남긴 출력입니다.\n%s" % (SERVE_STOPPED, tail))
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
        """[과제 받기]. 검사 도구가 없으면 설치를 먼저 권함."""
        stack = self.win.web.stack_state()
        if stack["problem"]:
            self.win.ask("검사 도구", NO_STACK_TEXT % stack["problem"], (("설치하기", "install"), ("그냥 받기", "get"), ("닫기", "")),
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
        self.status.setText("과제를 받았습니다. 읽기 시간 %d분이 시작되었습니다." % self.view["prep_min"])

    def start(self):
        try:
            self.win.web.start(self.mid, self.ai_box.isChecked())
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.load(self.mid)
        self.status.setText("실전 시간 %d분이 시작되었습니다. 받은 코드를 설명하세요." % self.view["live_min"])

    def explain_done(self):
        try:
            self.win.web.explain_done(self.mid, self.request_items.marks())
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.refresh()
        self.status.setText("0단계를 끝냈습니다. 1단계 요구가 열렸습니다.")

    def hint(self):
        try:
            hint = self.win.web.hint(self.mid)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.refresh()
        self.status.setText("면접관 힌트 %d을 들었습니다. 기록에 남습니다." % hint["n"])

    def ask_skip(self):
        self.win.ask("다음 요구로 넘어가기", SKIP_TEXT, (("넘어가기", "skip"), ("계속 풀기", "")), lambda key: self.skip())

    def skip(self):
        try:
            result = self.win.web.skip(self.mid)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.refresh()
        self.status.setText("%d단계를 넘어갔습니다. 기록에 남습니다." % result["skipped"])

    def check(self):
        mid = self.mid
        self.result_view.setHtml('<body><p class="muted">검사를 돌리는 중입니다.</p></body>')
        self.win.run_job("검사하는 중입니다. 몇 초 걸립니다.", lambda: self.win.web.check(mid), lambda result: self._checked(mid, result),
                         on_fail=self.show_results)

    def _checked(self, mid, result):
        self.results[mid] = result
        self.expanded = set()
        if mid != self.mid:
            return
        if result["passed"] and result["after"]:
            self.after, self.after_started = result["after"], self.clock()
        self.refresh()
        bar = self.result_view.verticalScrollBar()
        bar.setValue(0)
        if result["finished"] and not result["after"]:
            self.status.setText("모든 단계를 끝냈습니다. 해설이 열렸습니다.")
        elif result["passed"]:
            self.status.setText("%d단계를 통과했습니다.%s" % (result["open"], took_text(result)))
        else:
            self.status.setText("검사 %d개 가운데 %d개 통과%s. 고친 뒤 다시 [검사]를 누르세요."
                                % (len(result["tests"]), len(result["pass"]), took_text(result)))

    def on_result_link(self, url):
        kind, _, cid = url.partition(":")
        if kind == "more":
            self.expanded.add(cid)
        elif kind == "fold":
            self.expanded.discard(cid)
        else:
            return
        self.show_results()

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
        self.status.setText("통과 뒤 질문 판정: %s (답 시간 %d초)" % (service.RESULT_LABEL[result["result"]], secs))

    def ask_finish(self):
        self.win.ask("끝내기", FINISH_TEXT, (("끝내기", "finish"), ("계속 풀기", "")), lambda key: self.finish())

    def finish(self):
        mid = self.mid
        self.win.run_job("끝내는 중입니다.", lambda: self.win.web.finish(mid), lambda done: self._finished(mid, done))

    def _finished(self, mid, done):
        self.done_cache[(mid, done["try"])] = done
        if mid != self.mid:
            return
        self.done, self.after = done, None
        self.refresh()
        self.status.setText("미션을 끝냈습니다. 해설과 모범 답안 비교가 열렸습니다.")

    def save_self(self):
        done = self.done
        ticks = {item["key"]: mark for item, mark in zip(done["self_items"], self.done_items.marks())}
        try:
            self.win.web.self_check(self.mid, ticks)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        done["self_ticks"] = ticks
        self.status.setText("스스로 점검을 저장했습니다.")

    def open_followups(self):
        self.win.open_drill(self.done["followups"], back=("mission", self.mid))

    def ask_again(self):
        self.win.ask("다시 하기", AGAIN_TEXT, (("다시 하기", "again"), ("취소", "")), lambda key: self._get(True))

    # 테마 · 글자 크기

    def restyle(self):
        css, font = theme.journey_css(self.win.zoom), theme.code_font(self.win.zoom)
        for view in (self.brief_view, self.request_view, self.done_view, self.info_view):
            view.restyle(css, font)
        for edit in (self.mine_diff, self.template_diff):
            edit.setFont(theme.code_font(self.win.zoom - 2))
        for highlighter in self.highlighters:
            highlighter.rehighlight()
        if self.view is not None:
            self.show_results()
            self.tick()
