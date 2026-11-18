# -*- coding: utf-8 -*-
"""파이썬의 다음 회차·숙달 단원·지난 회차를 모음. 제출은 창 아래 공통 영역에서 다룸."""
import html
import math

from PyQt6.QtCore import QRectF, QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFontMetricsF, QPainter, QPalette, QPen
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate, QWidget

from gui import feedback, kit, theme
from gui.widgets import LinkLabel, UnitStrip, unit_legend

GAP = 16  # 카드 사이와 카드 안 묶음 사이 간격
UNIT_COLUMNS = 10  # 단원 칸을 한 줄에 10개씩 둠(20단원이면 10×2)
UNIT_PAD = 3  # 단원 칸 위아래 여백. 보통 글자에서 번호 줄 24 + 이름 줄 22 + 6 = 52
UNIT_GAP = 8  # 단원 칸 사이 가로·세로 간격
ROUND_GAP = 8  # 지난 회차 줄 사이
ROUND_PAD = 16  # 지난 회차 줄 안 좌우 여백과 글 위아래 여백
ROLE_TITLE, ROLE_SCORE = Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 2  # 지난 회차 줄을 나눠 그릴 제목과 점수
CHEVRON = "›"  # 줄 전체가 결과 화면을 여는 자리임을 알리는 꺾쇠. 새 문구는 넣지 않음


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


class UnitCell(QLabel):
    """단원 칸. 두 자리 번호와 그 아래 caption 크기 단원 이름 한 줄(줄임표)을 그림. 바탕·글자색은 objectName(unit_상태)의 스타일시트를 따름.
    칸 폭이 이름 세 글자를 담지 못하면 이름을 그리지 않고 번호만 가운데에 둠. 높이는 글자 단계의 두 줄 높이를 따름."""

    def __init__(self, number, name):
        super().__init__(number)
        self.name = name
        self.refont()

    def refont(self):
        self.setMinimumHeight(theme.TYPE["label"][1] + theme.TYPE["caption"][1] + 2 * UNIT_PAD)
        self.update()

    def name_shown(self):
        return QFontMetricsF(theme.font("caption")).horizontalAdvance("가나다") + 8 <= self.width()

    def paintEvent(self, event):
        QFrame.paintEvent(self, event)  # 바탕과 테두리만 칠하고 글은 아래에서 그림
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        rect = QRectF(self.contentsRect()).adjusted(4, 0, -4, 0)
        number_font = theme.font("label", True)  # 글자 단계를 따름
        if not self.name_shown():
            painter.setFont(number_font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())
            return
        number_h, name_h = theme.TYPE["label"][1], theme.TYPE["caption"][1]
        top = rect.center().y() - (number_h + name_h) / 2
        painter.setFont(number_font)
        painter.drawText(QRectF(rect.left(), top, rect.width(), number_h), Qt.AlignmentFlag.AlignCenter, self.text())
        caption = theme.font("caption")
        painter.setFont(caption)
        name = QFontMetricsF(caption).elidedText(self.name, Qt.TextElideMode.ElideRight, rect.width())
        painter.drawText(QRectF(rect.left(), top + number_h, rect.width(), name_h), Qt.AlignmentFlag.AlignCenter, name)


class UnitGrid(UnitStrip):
    """UnitStrip 의 칸 만들기와 툴팁은 그대로 쓰고, 범례를 회색 칸 한 줄로 위에 두고 칸을 UNIT_COLUMNS 열 격자로 놓음.
    set_units 뒤에 칸을 UnitCell(두 자리 번호와 단원 이름)로 바꿔 끼움. 상태 이름과 툴팁은 UnitStrip 이 만든 그대로 옮김."""

    class Cells(QGridLayout):
        """UnitStrip.set_units 가 부르는 addWidget(칸, 늘림)을 다음 격자 자리에 놓는 것으로 받음."""

        def addWidget(self, widget, *_):
            index = self.count()
            super().addWidget(widget, index // UNIT_COLUMNS, index % UNIT_COLUMNS)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.cell_height = 0  # 칸 높이는 UnitCell 이 글자 단계로 정함
        box = kit.box(self, spacing=12)
        legend, legend_box = kit.well(12, 8)
        legend_box.addLayout(unit_legend())
        box.addWidget(legend)
        self.cells = self.Cells()
        self.cells.setSpacing(UNIT_GAP)
        for column in range(UNIT_COLUMNS):
            self.cells.setColumnStretch(column, 1)
        box.addLayout(self.cells)

    def set_units(self, units):
        super().set_units(units)
        for index, unit in enumerate(units):
            old = self.cells.itemAt(index).widget()
            number = unit["unit"][1:]
            cell = UnitCell("%02d" % int(number) if number.isdigit() else unit["unit"], unit["title"])
            cell.setObjectName(old.objectName())
            cell.setToolTip(old.toolTip())
            self.cells.replaceWidget(old, cell)
            old.deleteLater()


class RoundDelegate(QStyledItemDelegate):
    """지난 회차 줄. 항목 글은 그대로 두고 회차 번호 칩, 제목, 오른쪽 굵은 점수, 주 색 꺾쇠로 나눠 그림.
    줄마다 surface_alt 바탕에 모서리 6 이고 줄 사이를 ROUND_GAP 띄움. 진단 테스트처럼 회차 번호가 없으면 칩 자리만 비움."""

    @staticmethod
    def row_height():
        return theme.TYPE["label"][1] + 2 * ROUND_PAD  # 보통 글자 56

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.row_height() + (ROUND_GAP if index.row() else 0))

    def paint(self, painter, option, index):
        rect = QRectF(option.rect).adjusted(0, ROUND_GAP if index.row() else 0, 0, 0)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        back = "selection" if selected else "hover" if option.state & QStyle.StateFlag.State_MouseOver else "surface_alt"
        ink = theme.qcolor("selection_ink" if selected else "ink")
        radius = theme.RADIUS["dense_control"]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor(back))
        painter.drawRoundedRect(rect, radius, radius)
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setPen(QPen(theme.qcolor("focus"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
        inner = rect.adjusted(ROUND_PAD, 0, -ROUND_PAD, 0)
        chip_font = theme.font("caption", True)
        chip_h = theme.TYPE["caption"][1] + 2
        chip_w = max(chip_h, math.ceil(QFontMetricsF(chip_font).horizontalAdvance("00")) + 16)
        number = index.data(Qt.ItemDataRole.UserRole) or ""
        if number.startswith("r") and number[1:].isdigit():
            chip = QRectF(inner.left(), inner.center().y() - chip_h / 2, chip_w, chip_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("selection" if not selected else "surface"))
            painter.drawRoundedRect(chip, theme.RADIUS["dense_chip"], theme.RADIUS["dense_chip"])
            painter.setFont(chip_font)
            painter.setPen(theme.qcolor("selection_ink"))
            painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, "%02d" % int(number[1:]))
        left = inner.left() + chip_w + 12
        link_font = theme.font("label", True)
        link_w = QFontMetricsF(link_font).horizontalAdvance(CHEVRON)
        painter.setFont(link_font)
        painter.setPen(ink if selected else theme.qcolor("link"))
        link = QRectF(inner.right() - link_w, inner.top(), link_w, inner.height())
        painter.drawText(link, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, CHEVRON)
        score_font = theme.font("label", True)
        score = index.data(ROLE_SCORE) or ""
        score_w = QFontMetricsF(score_font).horizontalAdvance(score)
        painter.setFont(score_font)
        painter.setPen(ink)
        score_rect = QRectF(link.left() - 16 - score_w, inner.top(), score_w, inner.height())
        painter.drawText(score_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, score)
        title_font = theme.font("label")
        painter.setFont(title_font)
        title_rect = QRectF(left, inner.top(), max(0.0, score_rect.left() - 16 - left), inner.height())
        title = QFontMetricsF(title_font).elidedText(index.data(ROLE_TITLE) or "", Qt.TextElideMode.ElideRight, title_rect.width())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        painter.restore()


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
        self.track_dot = kit.Dot("series_python", 10)
        top.row.insertWidget(top.row.indexOf(top.title), self.track_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.wrong_btn = top.add_right(outlined(kit.button("오답 노트", "text", "s")))
        self.wrong_count = kit.badge("", "danger")  # 파이썬 트랙의 틀린 문항 수. 0 이면 숨김
        wrong_box = kit.box(self.wrong_btn, (0, 0, 8, 0), horizontal=True)
        wrong_box.addStretch(1)
        wrong_box.addWidget(self.wrong_count, 0, Qt.AlignmentFlag.AlignVCenter)
        self.wrong_count.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.wrong_count.hide()
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
        self.ready = kit.label("", "headline", "accent", bold=True)  # 숙달 수만 주 색으로 둠
        self.ready_total = kit.label("", "headline", "secondary")
        self.mastered = kit.label("", "caption", "secondary")
        stat = Stat()
        stat_row = kit.box(stat, (12, 8, 12, 8), theme.GAP["detail"], horizontal=True)
        count = QWidget()
        count_row = kit.box(count, spacing=theme.SPACE[0], horizontal=True)
        count_row.addWidget(self.ready)
        count_row.addWidget(self.ready_total)
        stat_row.addWidget(count, 0, Qt.AlignmentFlag.AlignVCenter)
        stat_row.addWidget(self.mastered, 0, Qt.AlignmentFlag.AlignVCenter)
        head_row, _ = kit.card_head("단원별 학습", stat)
        box.addLayout(head_row)
        self.ready_bar = kit.progress(thin=True)
        box.addWidget(self.ready_bar)
        self.strip = UnitGrid()
        box.addWidget(self.strip)
        self.weak_box = kit.frame("banner")
        self.weak_head = kit.label("다시 볼 개념", "body", "warning", bold=True)
        self.weak = kit.para("", "body", "secondary")
        weak_column = kit.box(self.weak_box, (16, 12, 16, 12), theme.GAP["detail"] // 2)
        weak_column.addWidget(self.weak_head)
        weak_column.addWidget(self.weak)
        box.addWidget(self.weak_box)
        root.addWidget(units_card)
        self.rounds_hint = kit.para("", "caption", "secondary")
        self.rounds_count = kit.badge("")  # 지난 회차 수. 0 이면 숨김
        rounds_card, box = kit.card(spacing=GAP)
        rounds_head, _ = kit.card_head("지난 회차", self.rounds_count)
        box.addWidget(kit.heading(rounds_head, self.rounds_hint))
        self.rounds = QListWidget()
        kit.typed(self.rounds, "label")
        self.rounds.setObjectName("plain")
        self.rounds.setItemDelegate(RoundDelegate(self.rounds))
        self.rounds.setMouseTracking(True)  # 올린 줄의 바탕을 바꿈
        self.rounds.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rounds.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 높이를 줄 수에 맞추므로 스크롤하지 않음
        self.rounds.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rounds.hide()
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
        self.ready.setText(str(overview["mastered"]))
        self.ready_total.setText("/ %d" % overview["total_units"])
        self.mastered.setText("숙달한 단원 / 전체 단원")
        self.ready_bar.setRange(0, max(1, overview["total_units"]))
        self.ready_bar.setValue(overview["mastered"])
        self.strip.set_units(overview["units"])
        tags = overview["weak_tags"]
        self.weak_box.setProperty("tone", "warning" if tags else "")
        kit.repolish(self.weak_box)
        self.weak_head.setVisible(bool(tags))
        self.weak.setText(", ".join(tags) if tags else ("아직 틀린 문항이 없습니다." if win.session.prof["attempts"] else "문제를 풀면 다시 볼 개념을 모아 보여 줍니다."))
        self.set_wrong_count()
        label, desc = win.next_action(overview)
        self.next_card.set_item(label.removesuffix(" 시작").removesuffix(" 이어 풀기"), desc, label)
        self.rounds.clear()
        done = [r for r in overview["rounds"] if r["completed"]]
        for r in reversed(done):
            earned, total = (int(n) for n in (r["first_score"] or r["score"]).split("/"))
            score = "%d / %d점 (%d%%)" % (earned, total, round(100 * earned / total) if total else 0)
            item = QListWidgetItem("%s    %s" % (r["title"], score))
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            item.setData(ROLE_TITLE, r["title"])
            item.setData(ROLE_SCORE, score)
            self.rounds.addItem(item)
        self.rounds_count.setText(str(len(done)))
        self.rounds_count.setVisible(bool(done))
        self.fit_rounds()
        self.rounds_hint.setText("회차를 누르면 결과와 해설을 다시 볼 수 있습니다. 목록에는 첫 제출 때 받은 점수가 나옵니다." if done else "아직 제출한 회차가 없습니다.")
        usable = win.gitflow is not None
        self.git_hint.setVisible(not usable)
        self.git_hint.setText("" if usable else "지금은 제출과 문제 받기를 쓸 수 없습니다.\n" + win.git_reason)
        note = win.notice
        self.notice.setVisible(bool(note))
        if note:
            more = ' <a href="detail">자세히</a>' if note.get("detail") else ""
            self.notice.setText(html.escape(note.get("message") or "") + more)

    def fit_rounds(self):
        """지난 회차 목록의 높이를 줄 수에 맞추고 줄이 없으면 숨김."""
        count = self.rounds.count()
        self.rounds.setVisible(bool(count))
        if count:
            self.rounds.setFixedHeight(count * RoundDelegate.row_height() + (count - 1) * ROUND_GAP + 2 * self.rounds.frameWidth())
            self.rounds.doItemsLayout()

    def set_wrong_count(self):
        """[오답 노트] 단추 안 꼬리표에 파이썬 트랙의 틀린 문항 수를 넣음. 학습 현황 오답 줄의 '틀린 문항 N개' 와 같은 수임.
        꼬리표 폭만큼 단추 오른쪽 안 여백을 늘려 단추 글이 가운데에 남게 함."""
        python = next((track for track in self.win.wrong_tracks if track.tid == "python"), None)
        count = sum(1 for group in python.groups() for item in group["items"] if item["state"] == "wrong") if python else 0
        self.wrong_count.setText(str(count))
        self.wrong_count.setVisible(bool(count))
        self.wrong_btn.setAccessibleDescription("틀린 문항 %d개" % count if count else "")
        self.fit_wrong_button()

    def fit_wrong_button(self):
        if self.wrong_count.isHidden():
            self.wrong_btn.setStyleSheet("")
        else:
            self.wrong_count.ensurePolished()
            self.wrong_btn.setStyleSheet("QPushButton { padding-right: %dpx; }" % (8 + self.wrong_count.sizeHint().width() + 8))
        self.wrong_btn.updateGeometry()

    def restyle(self):
        self.theme_btn.setText("테마: %s" % theme.MODES[theme.state["mode"]])
        self.fit_wrong_button()
        self.fit_rounds()

    def set_busy(self, busy, text=""):
        for widget in (self.action_btn, self.rounds, self.wrong_btn, self.hub_btn, self.data_btn):
            widget.setEnabled(not busy)
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")
