# -*- coding: utf-8 -*-
"""오답 노트 화면: 첫 제출에서 틀렸거나 비워 둔 문항을 차시별로 묶은 목록과, 고른 문항의 문제 · 내 답 · 정답과 해설."""
import html

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter,
                             QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from gui import theme
from gui.mascot import Mascot
from gui.result_page import band, explain_html, md_html, my_answer_html, ref_html
from gui.widgets import Para
from session import SessionError

EMPTY = "아직 틀린 문항이 없습니다. 회차를 제출하면 틀린 문항이 여기에 모입니다."
ALL_FIXED = "틀린 문항을 모두 다시 맞혔습니다. [다시 맞힌 문항 숨기기]를 끄면 다시 보입니다."


class NoteList(QListWidget):
    """단원 머리 줄을 꺼 둔 목록. Qt 는 Home·End·PageUp·PageDown 이 꺼진 줄을 가리키면 움직이지 않아서, 그때는 옆 문항 줄로 옮김."""

    def moveCursor(self, action, modifiers):
        index = super().moveCursor(action, modifiers)
        if not index.isValid() or index.flags() & Qt.ItemFlag.ItemIsEnabled:
            return index
        move = QAbstractItemView.CursorAction
        step = -1 if action in (move.MoveUp, move.MovePageUp, move.MovePrevious, move.MoveLeft) else 1  # 누른 방향의 문항 줄을 먼저 봄
        for row in (index.row() + step, index.row() - step):
            near = self.model().index(row, 0)
            if near.flags() & Qt.ItemFlag.ItemIsEnabled:
                return near
        return index


class WrongPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        self.win = win
        self.units, self.rows = [], []  # rows 는 목록의 줄마다 문항. 단원 머리 줄은 None
        self.revealed = {}  # [해설 보기]를 누른 문항의 해설 {문항 키: session.explain 의 값}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        head = QHBoxLayout()
        self.home_btn = QPushButton("홈으로")
        title = QLabel("오답 노트")
        title.setObjectName("h1")
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.hide_fixed = QCheckBox("다시 맞힌 문항 숨기기")
        head.addWidget(self.home_btn)
        head.addSpacing(8)
        head.addWidget(title)
        head.addSpacing(16)
        head.addWidget(self.summary)
        head.addStretch(1)
        head.addWidget(self.hide_fixed)
        root.addLayout(head)

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.listw = NoteList()
        self.listw.setObjectName("notes")  # 단원 머리 줄의 바탕과 글자색은 theme.STYLE 에서 줌
        self.listw.setMinimumWidth(260)
        self.listw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right = QWidget()
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.item_title = Para(name="h2")  # 긴 코드 문제 제목은 줄을 바꿔 창이 좁아도 단추를 밀어내지 않음
        self.explain_btn = QPushButton("해설 보기")
        self.retry_btn = QPushButton("다시 풀기")
        top.addWidget(self.item_title, 1)
        top.addWidget(self.explain_btn)
        top.addWidget(self.retry_btn)
        self.detail = QTextBrowser()
        self.detail.setOpenLinks(False)
        self.detail.document().setDocumentMargin(14)
        right_box.addLayout(top)
        right_box.addWidget(self.detail, 1)
        self.split.addWidget(self.listw)
        self.split.addWidget(right)
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        self.split.setSizes([400, 850])
        self.split.setChildrenCollapsible(False)

        self.empty = QWidget()
        box = QVBoxLayout(self.empty)
        self.empty_text = Para(name="muted")
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        box.addStretch(1)
        box.addWidget(Mascot(88), 0, Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(self.empty_text)
        box.addStretch(2)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.split)
        self.stack.addWidget(self.empty)
        root.addWidget(self.stack, 1)

        self.listw.currentRowChanged.connect(self.show_row)
        self.hide_fixed.toggled.connect(self.fill)
        self.explain_btn.clicked.connect(self.reveal)
        self.retry_btn.clicked.connect(self.retry)
        self.home_btn.clicked.connect(win.go_home)

    def refresh(self):
        """풀이 기록을 다시 읽어 목록을 새로 채움. 화면을 열 때마다 부름."""
        self.units, self.revealed = self.win.session.wrong_notes(), {}
        notes = [note for unit in self.units for note in unit["items"]]
        self.summary.setText("틀린 문항 %d개 · 그 뒤에 맞힌 문항 %d개" % (len(notes), sum(1 for note in notes if note["fixed"])))
        self.empty_text.setText(ALL_FIXED if notes else EMPTY)
        self.fill()

    def fill(self):
        """목록을 다시 놓음. 고르던 문항이 목록에 남아 있으면 그 문항을 그대로 고름."""
        keep = self.selected()
        self.rows = []
        self.listw.blockSignals(True)
        self.listw.clear()
        for unit in self.units:
            notes = [note for note in unit["items"] if not (note["fixed"] and self.hide_fixed.isChecked())]
            if not notes:
                continue
            head = QListWidgetItem("%d차시 · %s · %d문항" % (int(unit["unit"][1:]), unit["title"], len(notes)))
            head.setFlags(Qt.ItemFlag.NoItemFlags)  # 누르거나 화살표 키로 고를 수 없음
            font = self.listw.font()
            font.setBold(True)
            head.setFont(font)
            self.listw.addItem(head)
            self.rows.append(None)
            for note in notes:
                parts = [note["type_label"], note["round_title"]]
                if note["skipped"]:
                    parts.append("미응답")
                if note["fixed"]:
                    parts.append("다시 맞힘")
                self.listw.addItem(" · ".join(parts))
                self.rows.append(note)
        picks = [n for n, note in enumerate(self.rows) if note]
        row = next((n for n in picks if keep and self.rows[n]["key"] == keep["key"]), picks[0] if picks else -1)
        self.listw.setCurrentRow(row)
        self.listw.blockSignals(False)
        self.stack.setCurrentWidget(self.split if picks else self.empty)
        self.color_rows()
        self.show_row(row)

    def selected(self):
        """고른 문항(session.wrong_notes 의 항목). 없으면 None."""
        row = self.listw.currentRow()
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def show_row(self, row):
        note, item = self.selected(), None
        self.item_title.setText("")
        self.detail.clear()
        if note is not None:
            try:
                item = self.win.session.wrong_item(note["round"], note["id"])
            except SessionError as error:  # 그 회차의 답안지가 깨짐. [다시 풀기]를 누르면 복구를 제안함
                self.detail.setHtml("<body><p>%s</p></body>" % html.escape(str(error)))
            else:
                label = "%s · %s · %d점" % (item["type_label"], item["unit_title"], item["points"])
                self.item_title.setText("%s · %s" % (item["title"], label) if item["kind"] == "code" else label)
                self.detail.setHtml(self.item_html(note, item))
        self.explain_btn.setEnabled(item is not None and note["key"] not in self.revealed)
        self.retry_btn.setEnabled(note is not None)

    def item_html(self, note, item):
        """첫 시도의 결과와 틀린 회차, 참고 자료, 문제, 내 답. [해설 보기]를 눌렀으면 결과 화면과 같은 정답과 해설을 덧붙임.
        참고 자료는 정답을 알려 주지 않아서 해설을 펴기 전에도 보여 줌. 은행 문항에 ref 가 없으면 참고 자료와 문제 띠를 넣지 않음."""
        name, mark = theme.result_label("skipped" if note["skipped"] else "wrong")
        facts = [note["round_title"]]
        if note["wrong_count"] > 1:
            facts.append("%d개 회차에서 틀림" % note["wrong_count"])
        if note["fixed"]:
            facts.append('<span class="ok">그 뒤에 다시 맞힘</span>')
        parts = ['<p><b><span class="%s">%s</span></b> <span class="muted">· %s</span></p>' % (mark, name, " · ".join(facts))]
        if item["ref"]:  # 문제 본문이 참고 자료 목록에 이어 붙어 보이지 않게 문제에도 띠를 붙임
            parts += [ref_html(item["ref"]), band("문제")]
        parts += [md_html(item["body_md"]), band("내 답"), my_answer_html(item)]
        if note["key"] in self.revealed:
            parts.append(explain_html(item, self.revealed[note["key"]]))
        return "<body>%s</body>" % "".join(parts)

    def reveal(self):
        note = self.selected()
        try:
            self.revealed[note["key"]] = self.win.session.explain(note["round"], note["id"])
        except SessionError as error:  # 터미널에서 일부만 채점해 아직 끝나지 않은 회차
            self.win.ask("알림", str(error))
            return
        self.show_row(self.listw.currentRow())
        self.detail.scrollToAnchor("answer")  # 문제 본문이 길어도 해설이 바로 보이게

    def retry(self):
        """끝낸 회차는 다시 풀기 화면으로 엶. 터미널에서 일부만 채점해 끝나지 않은 회차는 홈의 이어 풀기와 같은 풀이 화면으로 엶."""
        note = self.selected()
        self.win.open_round(note["round"], review=note["completed"], select=note["id"])

    def color_rows(self):
        """문항 줄의 글자색. 다시 맞힌 문항은 정답 색, 미응답은 회색, 나머지는 오답 색."""
        for row, note in enumerate(self.rows):
            if note:
                self.listw.item(row).setForeground(theme.qcolor("ok" if note["fixed"] else "blank" if note["skipped"] else "wrong"))

    def restyle(self):
        """글자 크기나 테마가 바뀌면 부름. 결과 화면처럼 본문 CSS 와 목록 색을 다시 주고, 읽던 자리는 지킴."""
        self.detail.document().setDefaultStyleSheet(theme.doc_css(self.win.zoom))
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Base, theme.qcolor("track"))  # 어두운 테마에서 확인란의 네모가 바탕에 묻히지 않게
        self.hide_fixed.setPalette(palette)
        if self.rows:
            self.color_rows()
            bar = self.detail.verticalScrollBar()
            place = bar.value()
            self.show_row(self.listw.currentRow())
            bar.setValue(place)
