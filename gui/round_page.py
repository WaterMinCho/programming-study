# -*- coding: utf-8 -*-
"""회차 화면: 왼쪽 문항 목록 · 가운데 문제 · 오른쪽 답안 · 아래 실행과 제출."""
import datetime
import html
import textwrap

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPen, QPixmap, QTextCursor
from PyQt6.QtWidgets import (QLabel, QListWidget, QListWidgetItem, QSplitter, QStackedWidget, QStyle, QStyledItemDelegate,
                             QStyleOptionViewItem, QTextBrowser, QVBoxLayout, QWidget)

import mdlite
import study
from gui import kit, theme
from gui.guard import NOTE
from gui.widgets import ChoicePanel, CodePanel, FindBar, PasteBlock, TextPanel
from session import SessionError

SAVE_DELAY_MS = 400  # 입력이 멈춘 뒤 자동 저장까지
DOT_PX = 12
ROW_GAP = 5  # 문항 목록 한 줄 안에서 윗줄과 아랫줄 사이
_dots = {}


def dot(color, filled):
    """문항 목록의 상태 동그라미. filled 면 색을 채우고 아니면 테두리만 그림."""
    if (color, filled) not in _dots:
        pixmap = QPixmap(DOT_PX * 2, DOT_PX * 2)  # 고해상도 화면에서도 매끈하게 두 배로 그림
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(color), 1.5))
        painter.setBrush(QColor(color) if filled else Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(1.5, 1.5, DOT_PX - 3, DOT_PX - 3))
        painter.end()
        icon = QIcon()
        for mode in (QIcon.Mode.Normal, QIcon.Mode.Selected):  # 선택된 줄에서도 색이 바뀌지 않게 함
            icon.addPixmap(pixmap, mode)
        _dots[color, filled] = icon
    return _dots[color, filled]
PASTE_NOTE_MS = 4000  # 복사·붙여넣기를 막았다는 안내를 보여 주는 시간


def split_input(text):
    """study 가 만든 입력 표시('입력:\\n    3', '테스트 코드:\\n    f()', 'f(1)')를 (이름, 내용)으로 나눔."""
    for head in ("입력", "테스트 코드"):
        if text.startswith(head + ":"):
            return head, textwrap.dedent(text[len(head) + 1:].strip("\n")).strip()
    return "호출", text


def run_html(run):
    """'코드 실행' 결과(session.try_run)를 예시별 표로 만듦. 색은 본문 CSS 의 클래스로 주어 테마가 바뀌어도 그대로 다시 넣을 수 있음."""
    note = '<span class="muted">예시만 실행하며 기록되지 않습니다.</span>'
    cases = run["cases"]
    if cases:
        parts = ["<p><b>예시 %d개 중 %d개 통과</b> · %s</p>" % (len(cases), sum(1 for case in cases if case["ok"]), note)]
    else:
        parts = ["<p>%s</p>" % note]
    if run["message"]:
        parts.append('<p class="wrong" style="white-space:pre-wrap;"><b>%s</b></p>' % html.escape(run["message"], quote=False))
    elif not cases:
        parts.append("<p>실행 결과가 없습니다.</p>")
    for number, case in enumerate(cases, 1):
        head, body = split_input(case["input"])
        value = "반환값" if head == "호출" else "출력"
        label, mark = ("통과", "ok") if case["ok"] else ("실패", "wrong")
        rows = [(head, body), ("기대한 " + value, case["want"]), ("실제 " + value, case["got"])]
        if case["printed"]:
            rows.append(("함수 안 출력", case["printed"]))
        parts.append('<p><b>예시 %d · <span class="%s">%s</span></b></p>' % (number, mark, label))
        parts.append('<table class="grid" border="1" cellspacing="0" cellpadding="4">%s</table>' % "".join(
            '<tr><th align="left">%s</th><td><pre>%s</pre></td></tr>' % (name, html.escape(text, quote=False)) for name, text in rows))
    return "<body>%s</body>" % "".join(parts)


class RowDelegate(QStyledItemDelegate):
    """문항 목록의 줄. 같이 배포하는 글꼴은 줄 높이가 글자 크기와 같아 두 줄이 붙어 보이므로 줄 사이를 띄워 그림."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), size.height() + ROW_GAP * (index.data() or "").count("\n"))

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style()
        margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, opt, opt.widget) + 1  # 기본 그리기가 글 양옆에 두는 여백
        rect = QRectF(style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget)).adjusted(margin, 0, -margin, 0)
        lines, opt.text = (index.data() or "").split("\n"), ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)  # 바탕과 동그라미
        height = opt.fontMetrics.height()
        top = rect.center().y() - (len(lines) * (height + ROW_GAP) - ROW_GAP) / 2
        painter.save()
        painter.setFont(opt.font)
        painter.setPen(theme.qcolor("selection_ink" if opt.state & QStyle.StateFlag.State_Selected else "ink"))
        for n, line in enumerate(lines):
            painter.drawText(QRectF(rect.left(), top + n * (height + ROW_GAP), rect.width(), height),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             opt.fontMetrics.elidedText(line, Qt.TextElideMode.ElideRight, int(rect.width())))
        painter.restore()


class RoundPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.win = win
        self.view, self.current, self.review = None, None, False
        self.dirty = {}  # 아직 파일에 쓰지 않은 답 {문항 ID: 값}

        root = kit.box(self)
        top = kit.TopBar("파이썬 스터디")
        self.home_btn, self.title = top.back, top.title
        self.progress = top.add_right(kit.label("", "caption", "secondary"))
        self.back_btn = top.add_right(kit.button("결과로 돌아가기", "text"))
        root.addWidget(top)
        self.banner = QLabel("다시 풀기는 연습이라 숙달 판정에는 첫 제출만 반영됩니다. 고친 뒤 '다시 채점'을 누르면 점수만 다시 계산합니다.")
        self.banner.setObjectName("notice")
        root.addWidget(self.banner)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setContentsMargins(24, 16, 24, 16)
        self.listw = QListWidget()
        self.listw.setMinimumWidth(200)
        self.listw.setIconSize(QSize(DOT_PX, DOT_PX))
        self.listw.setItemDelegate(RowDelegate(self.listw))
        self.listw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        mid = QWidget()
        mid_box = QVBoxLayout(mid)
        mid_box.setContentsMargins(0, 0, 0, 0)
        mid_box.setSpacing(theme.GAP["title_description"])
        self.item_title = kit.para("", "headline")
        self.body = QTextBrowser()
        self.body.setOpenLinks(False)
        self.body.document().setDocumentMargin(14)
        mid_box.addWidget(self.item_title)
        mid_box.addWidget(self.body, 1)
        right = QWidget()
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(theme.GAP["description_content"])
        self.pane_title = kit.label("답안", "headline")
        self.stack = QStackedWidget()
        self.choice_panel, self.text_panel, self.code_panel = ChoicePanel(), TextPanel(), CodePanel()
        for panel in (self.choice_panel, self.text_panel, self.code_panel):
            self.stack.addWidget(panel)
            panel.changed.connect(self.on_answer_changed)
        self.paste_block = PasteBlock(self)
        for edit in (self.code_panel.editor, self.text_panel.multi, self.text_panel.single, self.choice_panel.entry):
            self.paste_block.watch(edit)
        right_box.addWidget(self.pane_title)
        right_box.addWidget(self.stack, 1)
        self.find_bar = FindBar(self.code_panel.editor, right)  # 실행·채점 중에 답안 칸을 잠가도 쓰이게 그 밖에 둠
        for widget in (self.listw, mid, right):
            split.addWidget(widget)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 5)
        split.setStretchFactor(2, 4)
        split.setSizes([245, 515, 495])
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        self.bar = kit.BottomBar()
        self.prev_btn = kit.button("이전", "secondary", "l")
        self.next_btn = kit.button("다음", "secondary", "l")
        self.status = kit.ElideLabel("", "caption", "secondary")
        self.status.setFixedWidth(10 * theme.TYPE["caption"][0])  # 자동 저장 안내가 생겨도 답안 칸 높이가 바뀌지 않게 자리를 남김
        self.paste_note = kit.label(NOTE, "caption", "warning")
        self.paste_note.setMinimumWidth(1)
        self.paste_note.hide()
        self.busy_bar = kit.progress()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setFixedWidth(140)
        self.busy_bar.hide()
        self.run_btn = kit.button("코드 실행", "text", "l")
        self.submit_btn = kit.button("회차 제출", "primary", "l")
        for widget in (self.status, self.paste_note, self.busy_bar, self.run_btn):
            self.bar.add_tool(widget)
        self.bar.add_action(self.prev_btn)
        self.bar.add_action(self.next_btn)
        self.bar.action_row.addSpacing(16)
        self.bar.add_action(self.submit_btn)
        root.addWidget(self.bar)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(SAVE_DELAY_MS)
        self.save_timer.timeout.connect(lambda: self.flush(commit=False))  # 타이머 저장은 조합 중인 한글을 끊지 않음
        self.note_timer = QTimer(self)
        self.note_timer.setSingleShot(True)
        self.note_timer.setInterval(PASTE_NOTE_MS)
        self.note_timer.timeout.connect(self.paste_note.hide)
        self.paste_block.blocked.connect(self.note_blocked)
        self.listw.currentRowChanged.connect(self.show_item)
        self.prev_btn.clicked.connect(lambda: self.listw.setCurrentRow(self.listw.currentRow() - 1))
        self.next_btn.clicked.connect(lambda: self.listw.setCurrentRow(self.listw.currentRow() + 1))
        self.run_btn.clicked.connect(self.run_code)
        self.submit_btn.clicked.connect(self.submit)
        self.code_panel.reset_btn.clicked.connect(self.ask_reset)
        self.home_btn.clicked.connect(win.go_home)
        self.back_btn.clicked.connect(self.back)

    # 불러오기

    def load(self, rid, review=False, select=None):
        """회차를 화면에 올림. 답안지를 읽을 수 없으면 화면을 바꾸지 않고 SessionError 를 냄."""
        if self.view and not self.flush():  # 앞에 보던 회차에 남은 입력부터 저장. 못 하면 그 입력을 지우지 않고 멈춤
            raise SessionError(self.status.text())
        view = self.win.session.open_round(rid)
        self.dirty.clear()
        self.view, self.review, self.current = view, review, None
        self.title.setText(view["title"] + (" · 다시 풀기" if review else ""))
        self.banner.setVisible(review)
        self.back_btn.setVisible(review)
        self.submit_btn.setText("다시 채점" if review else "회차 제출")
        self.status.setText("")
        row = next((n for n, item in enumerate(view["items"]) if item["id"] == select), 0)
        self.listw.blockSignals(True)
        self.listw.clear()
        for item in view["items"]:
            self.listw.addItem(QListWidgetItem())
            self._fill_row(item)
        self.listw.setCurrentRow(row)
        self.listw.blockSignals(False)
        self._update_progress()
        self.show_item(row)

    def _fill_row(self, item):
        """목록의 한 줄. 답을 적은 문항은 초록 동그라미, 아직이면 빈 동그라미. 다시 풀기에서는 채점 결과의 색과 이름을 씀."""
        row = self.listw.item(item["no"] - 1)
        if self.review:
            state, token = theme.result_label(item["result"])
            row.setText("%d. %s · %s\n%s" % (item["no"], item["type_label"], state, item["unit_title"]))
            row.setIcon(dot(theme.color(token), token != "blank"))
        else:
            row.setText("%d. %s\n%s" % (item["no"], item["type_label"], item["unit_title"]))
            row.setIcon(dot(theme.color("ok" if item["answered"] else "blank"), item["answered"]))
        row.setData(Qt.ItemDataRole.UserRole, bool(item["answered"]))

    def _update_progress(self):
        items = self.view["items"]
        self.progress.setText("작성 %d / %d문항" % (sum(1 for item in items if item["answered"]), len(items)))

    def show_item(self, row):
        self.flush()  # 앞 문항에 남은 입력부터 저장
        if not 0 <= row < len(self.view["items"]):
            return
        item = self.view["items"][row]
        self.find_bar.dismiss(select=False)
        label = "%s · %s · %d점" % (item["type_label"], item["unit_title"], item["points"])
        if item["kind"] == "code":
            label = "%s · %s" % (item["title"], label)
        self.item_title.setText("%d. %s%s" % (item["no"], label, " · 지난번에 틀린 문항" if item["retest"] else ""))
        self.body.setHtml(self.body_html(item))
        if item["kind"] == "code":
            panel, name = self.code_panel, "코드"
        elif item["type"] == "choice":
            panel, name = self.choice_panel, "답안 · 객관식"
        else:
            panel, name = self.text_panel, "답안 · " + item["type_label"]
        panel.set_item(item)
        self.stack.setCurrentWidget(panel)
        self.current = item  # 패널을 바꾼 뒤에 옮김. 위에서 오류가 나도 보이는 입력칸과 저장할 문항이 어긋나지 않음
        self.pane_title.setText(name)
        self.run_btn.setVisible(item["kind"] == "code")
        self.prev_btn.setEnabled(row > 0)
        self.next_btn.setEnabled(row < len(self.view["items"]) - 1)

    @staticmethod
    def body_html(item):
        """본문 칸에 넣을 HTML. 보기를 카드로 보여 주는 객관식은 지문만 넣음."""
        return mdlite.blocks_html(item["stem"]) if item.get("options") else mdlite.to_html(item["body_md"])

    def note_blocked(self):
        """복사나 붙여넣기를 막았다는 안내를 잠깐 보여 줌."""
        self.paste_note.show()
        self.note_timer.start()

    def restyle(self):
        """글자 크기나 테마가 바뀌면 부름. 본문 CSS 와 입력칸 글꼴을 다시 주고, 읽던 자리는 지킴."""
        css, font = theme.doc_css(self.win.zoom), theme.code_font(self.win.zoom)
        for browser in (self.body, self.code_panel.console):
            browser.document().setDefaultStyleSheet(css)
        self.choice_panel.restyle(css)
        for widget in (self.code_panel.editor, self.text_panel.multi, self.text_panel.single, self.choice_panel.entry):
            widget.setFont(font)
        if self.current:  # 스타일은 다음에 넣는 HTML 부터 적용되므로 본문을 다시 넣음
            bars = [browser.verticalScrollBar() for browser in (self.body, self.code_panel.console)]
            places = [bar.value() for bar in bars]
            self.body.setHtml(self.body_html(self.current))
            self.code_panel.show_console(self.code_panel.console_html)
            for bar, place in zip(bars, places):
                bar.setValue(place)
        for item in self.view["items"] if self.view else []:  # 목록의 동그라미 색도 테마를 따라감
            self._fill_row(item)

    # 자동 저장

    def on_answer_changed(self, value):
        item = self.current
        if item is None:
            return
        item["answer"] = value
        if item["kind"] == "code":
            item["answered"] = study.norm_out(value) != study.norm_out(item["starter"])
        else:
            item["answered"] = bool(value if item["type"] == "choice" else value.strip())
        self.dirty[item["id"]] = value
        self.save_timer.start()
        self._fill_row(item)
        self._update_progress()

    def flush(self, commit=True, offer=True):
        """대기 중인 답을 파일에 쓰고, 다 썼으면 True 를 돌려줌. commit=True 면 조합 중인 한글부터 확정함.
        offer=False 면 답안지 복구를 제안하지 않음(부른 쪽이 직접 알릴 때)."""
        if commit:
            QGuiApplication.inputMethod().commit()
        self.save_timer.stop()
        if not self.dirty:
            return True
        for item_id, value in list(self.dirty.items()):
            try:
                self.win.session.set_answer(self.view["id"], item_id, value)
            except (SessionError, OSError) as error:
                self.status.setText("저장하지 못했습니다: %s" % error)
                if offer:
                    self.win.offer_repair(self.view["id"], self.reload)
                return False
            del self.dirty[item_id]
        self.status.setText("%s 에 자동 저장했습니다." % datetime.datetime.now().strftime("%H:%M:%S"))
        return True

    def reload(self):
        """답안지를 복구한 뒤에 부름. 못 쓴 답을 마저 쓰고 파일에 남은 답으로 화면을 다시 맞춤."""
        if self.flush():
            self.load(self.view["id"], self.review, self.current["id"] if self.current else None)

    def back(self):
        if self.win.leave_round(self.back, "저장하지 않고 나가기"):
            self.win.show_result(self.view["id"])

    # 실행 · 제출

    def set_busy(self, busy, text=""):
        """채점하는 파일과 화면이 어긋나지 않게 실행·채점 중에는 입력을 잠금."""
        for widget in (self.listw, self.stack, self.prev_btn, self.next_btn, self.run_btn, self.submit_btn, self.home_btn, self.back_btn):
            widget.setEnabled(not busy)
        self.busy_bar.setVisible(busy)
        if busy:
            self.paste_note.hide()  # 진행 글과 막대가 들어갈 자리를 비움
            self.status.setText(text)
        else:
            row = self.listw.currentRow()
            self.prev_btn.setEnabled(row > 0)
            self.next_btn.setEnabled(row < self.listw.count() - 1)

    def run_code(self):
        item = self.current
        if item is None or item["kind"] != "code" or not self.flush():
            return
        self.code_panel.show_console("<body><p>실행 중입니다.</p></body>")
        rid = self.view["id"]
        self.win.run_job("예시를 실행하는 중입니다.", lambda: self.win.session.try_run(rid, item["id"]), self._ran,
                         on_fail=lambda: self.code_panel.show_console(""))

    def _ran(self, run):
        self.code_panel.show_console(run_html(run))
        self.status.setText("예시 실행을 마쳤습니다.")
        self.code_panel.focus_input()

    def ask_reset(self):
        self.win.ask("시작 코드로 되돌리기", "지금 작성한 코드를 지우고 처음 받은 코드로 되돌립니다.",
                     (("되돌리기", "reset"), ("취소", "")), lambda key: self._reset())

    def _reset(self):
        cur = self.code_panel.editor.textCursor()
        cur.select(QTextCursor.SelectionType.Document)
        cur.insertText(self.current["starter"])  # 편집으로 넣어야 자동 저장이 돌고 되돌리기(Ctrl+Z)가 남음
        self.flush()

    def submit(self):
        if not self.flush():
            return
        rid = self.view["id"]
        if self.review:
            self.win.run_job("다시 채점하는 중입니다.", lambda: self.win.session.grade(rid), lambda result: self.win.show_result(rid, result))
            return
        try:
            pending = self.win.session.pending(rid)
        except SessionError as error:
            self.status.setText(str(error))
            self.win.offer_repair(rid, self.reload)
            return
        blank, total = pending["blank"], pending["total"]
        if len(blank) == total:
            lines = ["아직 작성한 문항이 없습니다. 지금 제출하면 전체 %d문항이 미응답으로 남습니다." % total, "미응답은 오답으로 처리됩니다."]
        elif blank:
            lines = ["전체 %d문항 중 %d문항을 작성했습니다." % (total, total - len(blank)),
                     "미응답 문항: %s번" % ", ".join(str(n) for n in blank), "미응답은 오답으로 처리됩니다."]
        else:
            lines = ["전체 %d문항을 모두 작성했습니다." % total]
        lines += ["", "제출하면 지금 답이 첫 시도로 기록됩니다. 제출한 뒤에 고쳐서 다시 채점해도 숙달 판정은 바뀌지 않습니다."]
        self.win.ask("회차 제출", "\n".join(lines), (("제출", "submit"), ("계속 풀기", "")), lambda key: self._grade(rid))

    def _grade(self, rid):
        self.win.run_job("채점하는 중입니다. 코드 문제는 모든 테스트를 실행합니다.",
                         lambda: self.win.session.grade(rid, finalize=True), lambda result: self.win.show_result(rid, result))
