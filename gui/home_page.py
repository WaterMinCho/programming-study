# -*- coding: utf-8 -*-
"""파이썬의 다음 회차·숙달 단원·지난 회차를 모음. 제출은 창 아래 공통 영역에서 다룸."""
import html

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPainter
from PyQt6.QtWidgets import QFrame, QGridLayout, QListWidget, QListWidgetItem, QWidget

from gui import feedback, kit, theme
from gui.widgets import LinkLabel, UnitStrip, unit_legend

GAP = 16  # 카드 사이와 카드 안 묶음 사이 간격
UNIT_COLUMNS = 10  # 단원 칸을 한 줄에 10개씩 둠(20단원이면 10×2)
UNIT_CELL = 52  # 단원 칸 높이
UNIT_GAP = 8  # 단원 칸 사이 가로·세로 간격


def card(title, description=None):
    frame, box = kit.card(spacing=GAP)
    title = kit.label(title, "headline")
    box.addWidget(kit.heading(title, description) if description is not None else title)
    return frame, box


def muted(text=""):
    return kit.para(text, "body", "secondary")


class Stat(QFrame):
    """카드 머리 오른쪽의 숫자 상자. 바탕을 직접 칠해 테마가 바뀌면 다음 그리기에서 색이 따라옴.
    카드 안 카드 규칙(surface_alt)에 덮이지 않게 스타일시트 대신 칠함."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor("emphasis_bg"))
        radius = theme.RADIUS["dense_control"]
        painter.drawRoundedRect(self.rect(), radius, radius)


class UnitGrid(UnitStrip):
    """UnitStrip 의 칸 만들기와 툴팁은 그대로 쓰고, 범례를 회색 칸 한 줄로 위에 두고 칸을 UNIT_COLUMNS 열 격자로 놓음."""

    class Cells(QGridLayout):
        """UnitStrip.set_units 가 부르는 addWidget(칸, 늘림)을 다음 격자 자리에 놓는 것으로 받음."""

        def addWidget(self, widget, *_):
            index = self.count()
            super().addWidget(widget, index // UNIT_COLUMNS, index % UNIT_COLUMNS)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.cell_height = UNIT_CELL
        box = kit.box(self, spacing=12)
        legend, legend_box = kit.well(12, 8)
        legend_box.addLayout(unit_legend())
        box.addWidget(legend)
        self.cells = self.Cells()
        self.cells.setSpacing(UNIT_GAP)
        for column in range(UNIT_COLUMNS):
            self.cells.setColumnStretch(column, 1)
        box.addLayout(self.cells)


def outlined(button):
    """위 막대의 글자 단추에 테두리를 줌."""
    button.setProperty("outlined", True)
    return button


class HomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.win = win
        outer = kit.box(self)
        self.top = top = kit.TopBar("학습 현황", "파이썬 스터디", dense=True)
        self.hub_btn = top.back
        self.wrong_btn = top.add_right(outlined(kit.button("오답 노트", "text", "s")))
        self.theme_btn = top.add_right(outlined(kit.button("", "text", "s")))
        self.theme_btn.setToolTip("화면 테마를 시스템·밝게·어둡게 순서로 바꿉니다.")
        outer.addWidget(top)
        inner = QWidget()
        kit.dense(inner)
        root = kit.box(inner, (0, 16, 0, 32), GAP)
        self.user = kit.label("", "caption", "tertiary")
        record_tools = QWidget()
        record_row = kit.FlowLayout(record_tools, spacing=theme.GAP["group"])
        record_row.addWidget(self.user)
        self.data_btn = kit.button("학습 기록 설정", "text", onbg=True)
        self.data_btn.setToolTip("파이썬 기록 제공 상태를 확인하고 수집을 중단하거나 기록 파일을 저장합니다.")
        self.data_btn.clicked.connect(self.show_data)
        record_row.addWidget(self.data_btn)
        root.addWidget(record_tools)
        self.notice = LinkLabel()
        kit.typed(self.notice, "body")
        self.notice.setObjectName("notice")
        self.notice.linkActivated.connect(lambda _: win.show_notice_detail())
        self.notice.hide()
        root.addWidget(self.notice)
        self.next_card = kit.NextCard(compact=True)
        self.next_card.caption.setText("다음 회차")
        self.action_desc, self.action_btn = self.next_card.line, self.next_card.button
        root.addWidget(self.next_card)
        units_card, box = kit.card(spacing=GAP)
        self.ready = kit.label("", "headline", bold=True)
        self.mastered = kit.label("", "caption", "secondary")
        stat = Stat()
        stat_row = kit.box(stat, (12, 8, 12, 8), theme.GAP["detail"], horizontal=True)
        stat_row.addWidget(self.ready, 0, Qt.AlignmentFlag.AlignVCenter)
        stat_row.addWidget(self.mastered, 0, Qt.AlignmentFlag.AlignVCenter)
        head_row, _ = kit.card_head("단원별 학습", stat)
        box.addLayout(head_row)
        self.ready_bar = kit.progress(thin=True)
        box.addWidget(self.ready_bar)
        self.strip = UnitGrid()
        box.addWidget(self.strip)
        self.weak_box = kit.frame("banner")
        self.weak = kit.para("", "body", "secondary")
        kit.box(self.weak_box, (16, 12, 16, 12)).addWidget(self.weak)
        box.addWidget(self.weak_box)
        root.addWidget(units_card)
        self.rounds_hint = kit.para("", "caption", "secondary")
        rounds_card, box = card("지난 회차", self.rounds_hint)
        self.rounds = QListWidget()
        kit.typed(self.rounds, "label")
        self.rounds.setObjectName("plain")
        self.rounds.setStyleSheet("QListWidget::item { padding: 19px 16px; }")  # 보통 글자에서 줄 높이 56(글 17, 구분선 1)
        self.rounds.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rounds.setMinimumHeight(160)
        box.addWidget(self.rounds)
        root.addWidget(rounds_card)
        self.git_hint = kit.para("", "caption", "secondary")
        root.addWidget(self.git_hint)
        self.status = kit.para("", "caption", "secondary")
        self.busy_bar = kit.progress()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.hide()
        root.addWidget(self.status)
        root.addWidget(self.busy_bar)
        self.foot = LinkLabel('<a href="%s">불편한 점 알리기</a>' % feedback.ISSUE_URL)
        kit.typed(self.foot, "caption")
        self.foot.setOpenExternalLinks(False)
        self.foot.linkActivated.connect(lambda _: QDesktopServices.openUrl(QUrl(feedback.issue_url(win))))
        root.addWidget(self.foot)
        outer.addWidget(kit.scroll(kit.dense_column(inner)), 1)
        self.hub_btn.clicked.connect(win.go_hub)
        self.wrong_btn.clicked.connect(lambda: win.show_wrong("python", "python"))
        self.theme_btn.clicked.connect(win.cycle_theme)
        self.action_btn.clicked.connect(win.start_next)
        self.rounds.itemClicked.connect(lambda item: win.show_result(item.data(Qt.ItemDataRole.UserRole)))

    def showEvent(self, event):
        """설정 단추는 창이 add_settings 로 붙이므로 처음 보일 때 다른 위 막대 단추와 같은 테두리를 줌.
        add_settings 는 글자 단추로 보고 오른쪽 여백을 FLUSH 만큼 줄이지만, 테두리가 보이는 단추라 학습 현황처럼 여백을 24 로 되돌림."""
        settings = getattr(self, "settings_btn", None)
        if settings is not None and not settings.property("outlined"):
            kit.repolish(outlined(settings))
            left, top, _, bottom = self.top.row.getContentsMargins()
            self.top.row.setContentsMargins(left, top, self.top.margin, bottom)
        super().showEvent(event)

    def show_data(self):
        from gui.ai_data import LearningDataDialog
        self.data_dialog = LearningDataDialog(self, self.win.session.collection, host=self.win)
        self.data_dialog.show()

    def refresh(self):
        win = self.win
        overview = win.session.overview()
        self.data_btn.setText("학습 기록 설정 · 확인 필요" if win.session.collection.error else "학습 기록 설정")
        self.user.setText("ID: %s" % overview["user"])
        self.ready.setText("%d / %d" % (overview["mastered"], overview["total_units"]))
        self.mastered.setText("숙달한 단원 / 전체 단원")
        self.ready_bar.setRange(0, max(1, overview["total_units"]))
        self.ready_bar.setValue(overview["mastered"])
        self.strip.set_units(overview["units"])
        tags = overview["weak_tags"]
        self.weak_box.setProperty("tone", "warning" if tags else "")
        kit.repolish(self.weak_box)
        self.weak.setText("다시 볼 개념: " + ", ".join(tags) if tags else ("아직 틀린 문항이 없습니다." if win.session.prof["attempts"] else "문제를 풀면 다시 볼 개념을 모아 보여 줍니다."))
        label, desc = win.next_action(overview)
        self.next_card.set_item(label.removesuffix(" 시작").removesuffix(" 이어 풀기"), desc, label)
        self.rounds.clear()
        done = [r for r in overview["rounds"] if r["completed"]]
        for r in reversed(done):
            earned, total = (int(n) for n in (r["first_score"] or r["score"]).split("/"))
            item = QListWidgetItem("%s    %d / %d점 (%d%%)" % (r["title"], earned, total, round(100 * earned / total) if total else 0))
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.rounds.addItem(item)
        self.rounds_hint.setText("회차를 누르면 결과와 해설을 다시 볼 수 있습니다. 목록에는 첫 제출 때 받은 점수가 나옵니다." if done else "아직 제출한 회차가 없습니다.")
        usable = win.gitflow is not None
        self.git_hint.setVisible(not usable)
        self.git_hint.setText("" if usable else "지금은 제출과 문제 받기를 쓸 수 없습니다.\n" + win.git_reason)
        note = win.notice
        self.notice.setVisible(bool(note))
        if note:
            more = ' <a href="detail">자세히</a>' if note.get("detail") else ""
            self.notice.setText(html.escape(note.get("message") or "") + more)

    def restyle(self):
        self.theme_btn.setText("테마: %s" % theme.MODES[theme.state["mode"]])

    def set_busy(self, busy, text=""):
        for widget in (self.action_btn, self.rounds, self.wrong_btn, self.hub_btn, self.data_btn):
            widget.setEnabled(not busy)
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")
