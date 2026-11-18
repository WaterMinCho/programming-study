# -*- coding: utf-8 -*-
"""새 디자인 시스템의 부품. 첫 화면, 웹 면접 준비 화면, 알고리즘 여행 화면이 씀.

맨 위 위젯에 page() 로 ui="2" 속성을 주면 theme.STYLE_V2 의 색 규칙이 그 아래에만 걸림. 글자 크기와 굵기는 스타일시트가 아니라
theme.TYPE 으로 글꼴을 직접 주고(label, para), 그 역할을 role 속성에 적어 두어 글자 크기 단계가 바뀌면 refont 가 글꼴을 다시 줌.
간격은 theme.SPACE 의 값만 씀. 단추는 종류(kind)를 objectName 으로, 크기(scale)를
속성으로 받음. 목록 줄(Row)은 줄 전체가 눌림. 단계 표시(Stepper), 상태 점(Dot), 꺾쇠(Chevron), 칸 나누기 손잡이(SplitHandle)는
직접 그리는 위젯이고 칠할 때마다 지금 테마의 색을 읽음."""
import math

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen, QTextDocument
from PyQt6.QtWidgets import (QBoxLayout, QButtonGroup, QFrame, QHBoxLayout, QLabel, QLayout, QProgressBar, QPushButton, QScrollArea,
                             QSizePolicy, QSplitter, QSplitterHandle, QVBoxLayout, QWidget, QWidgetItem)

from gui import theme
from gui.widgets import LinkLabel, Para

FLUSH = 14  # 글자 단추의 안쪽 여백 12 과 테두리 2. 막대 가장자리의 글자 단추는 이만큼 바깥으로 내어 글자가 내용 선에 맞게 함
MARGIN = 32  # 창 좌우 여백
DENSE_MARGIN = 24  # 촘촘한 화면(dense)의 위아래 막대 좌우 여백
DENSE_BAR_PAD = (theme.CONTROL["bottombar_dense"] - theme.CONTROL["m"]) // 2  # 촘촘한 아래 막대의 위아래 여백. m 단추가 64 막대에 꼭 맞음
MARK = 20  # 목록 줄 앞 상태 점의 칸 폭
ROW_TEXT = 24 + MARK + 12  # 목록 줄의 글이 시작하는 자리(안쪽 여백, 점 칸, 점과 글 사이)
HOME_WIDTH = 1600  # 홈 화면 내용 단의 최대 폭
DOC_MIN = 880  # 편집기 옆 글 단의 시작 폭. 실제 칸이 좁으면 가용 폭을 따름
DOC_PX = theme.BASE_TYPE["body"][0]  # 읽기 폭을 비례해 넓힐 때 쓰는 본문 크기
READ_MIN = 1120  # 카드 하나로 읽는 화면의 시작 폭. 작은 창에서는 가용 폭을 따름
DOT_STATES = {"progress": "primary", "review": "retry", "done": "ok", "todo": "faint", "ready": "ok", "lock": "faint"}  # 상태 점의 색 토큰
PANE_MIN = 320  # 끌어 옮기는 칸 나누기에서 가로로 놓인 칸 하나의 최소 폭
GRIP = (4, 32)  # 칸 나누기 손잡이 가운데 무늬의 짧은 변과 긴 변
SEG_EDGE = 1  # 붙은 칩 묶음(segmented)의 바깥 테두리 두께. 간격이 아니라 선이라 SPACE 값이 아님


def doc_max():
    """편집기 옆 글 단의 상한. 본문 글자가 커진 만큼 폭도 넓힘."""
    return round(1200 * theme.TYPE["body"][0] / DOC_PX)


def read_max():
    """카드 하나만 있는 읽기 화면의 글 단 상한."""
    return round(1600 * theme.TYPE["body"][0] / DOC_PX)


def read_width(window_width):
    """읽기 카드의 바깥 여백을 남기고 창 폭을 사용함. 실제 칸이 좁으면 레이아웃이 가용 폭에 맞춤."""
    return max(READ_MIN, min(read_max(), window_width - 2 * MARGIN - 48))


def doc_width(window_width):
    """편집기와 나란히 놓이는 글 단도 창의 남는 폭을 사용하되 상한을 둠."""
    return max(DOC_MIN, min(doc_max(), window_width - 2 * MARGIN - 48))


def page(widget):
    """화면이나 대화상자의 맨 위 위젯에 새 규칙을 걸음."""
    widget.setProperty("ui", "2")
    return widget


def dense(widget):
    """widget 아래 카드·단추·입력칸·꼬리표에 촘촘한 모서리(theme.RADIUS 의 dense_*)와 m 주 단추 좌우 24 를 걸고 widget 을 돌려줌.
    widget 자신이 아니라 그 아래 부품에 걸림. 이미 칠한 뒤에 부르면 아래 부품을 다시 칠함."""
    widget.setProperty("density", "dense")
    if widget.testAttribute(Qt.WidgetAttribute.WA_WState_Polished):
        for child in [widget] + widget.findChildren(QWidget):
            repolish(child)
    return widget


def repolish(widget):
    """속성을 바꾼 뒤 스타일시트를 다시 적용함."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_tone(widget, tone):
    """tone 속성을 바꾸고 다시 칠함. 띠의 앞 낱말처럼 부모의 tone 으로 색이 정해지는 자식도 같이 다시 칠함."""
    if widget.property("tone") == (tone or None):  # 시계처럼 1초마다 같은 값으로 부르는 곳이 있어 바뀔 때만 다시 칠함
        return
    widget.setProperty("tone", tone or None)
    repolish(widget)
    for child in widget.findChildren(QWidget):
        repolish(child)


def set_font(widget, font):
    """위젯 글꼴을 바꿈. Qt 는 스타일시트를 처음 입힐 때의 글꼴을 이 속성에 저장해 두고 스타일을 다시 입힐 때마다 그 글꼴로 되돌리므로,
    저장된 글꼴도 같이 바꿔야 테마를 바꾼 뒤에 새 글꼴이 남음."""
    widget.setFont(font)
    if widget.property("_q_styleSheetWidgetFont") is not None:
        widget.setProperty("_q_styleSheetWidgetFont", font)


def typed(widget, role, bold=None):
    """위젯에 theme.TYPE 의 role 글꼴을 주고 역할을 적어 둠(refont 가 다시 줄 때 읽음)."""
    set_font(widget, theme.font(role, bold))
    widget.setProperty("role", role)
    if bold is not None:
        widget.setProperty("bold", bool(bold))
    return widget


def refont(root):
    """글자 크기 단계가 바뀐 뒤 root 아래 모든 부품의 글꼴을 지금 TYPE 으로 다시 줌. 역할을 적어 둔 위젯은 글꼴(Para 는 줄 높이도)을,
    refont 메서드가 있는 부품(줄임표 글, 목록 줄, 체크 상자)은 제 크기를 다시 잡음. 시계 숫자처럼 measure 속성이 있는 글은 그 글자의 폭을 다시 잼."""
    for widget in [root] + root.findChildren(QWidget):
        widget.ensurePolished()
        role = widget.property("role")
        if role:
            set_font(widget, theme.font(role, widget.property("bold")))
            if isinstance(widget, Para):  # 줄 높이를 바꾸고 글을 다시 넣어 새 글꼴로 줄 높이를 다시 셈
                widget.line = theme.TYPE[role][1]
                widget.setText(widget.text())
            if widget.property("measure"):
                widget.setMinimumWidth(math.ceil(QFontMetricsF(widget.font()).horizontalAdvance(widget.property("measure"))))
        if hasattr(widget, "refont"):
            widget.refont()


def label(text="", role="body", tone="", bold=None, align=None):
    """한 줄 글. role 은 theme.TYPE 의 이름, tone 은 secondary·tertiary·accent·success·warning·danger."""
    out = typed(QLabel(text), role, bold)
    if tone:
        out.setProperty("tone", tone)
    if align is not None:
        out.setAlignment(align)
    return out


def para(text="", role="body", tone="", bold=None):
    """여러 줄로 넘어가는 글. 줄 높이는 TYPE 의 px 값."""
    out = typed(Para(text, line=theme.TYPE[role][1], font=theme.font(role, bold)), role, bold)
    if tone:
        out.setProperty("tone", tone)
    return out


class _Baseline(QObject):
    """크기가 다른 한 줄 라벨의 기준선을 맞춤. 글꼴의 아래 여유가 상자 아랫변 정렬에 섞이지 않게 함."""

    def __init__(self, labels):
        super().__init__(labels[0])
        self.labels = labels
        self.margins = [label.contentsMargins() for label in labels]
        self.updating = False
        for label in labels:
            label.installEventFilter(self)
        self.refresh()

    def refresh(self):
        if self.updating:
            return
        self.updating = True
        try:
            for label in self.labels:
                label.ensurePolished()
            descents = [QFontMetricsF(label.font()).descent() for label in self.labels]
            lowest = max(descents)
            for label, margins, descent in zip(self.labels, self.margins, descents):
                label.setContentsMargins(margins.left(), margins.top(), margins.right(),
                                         margins.bottom() + round(lowest - descent))
        finally:
            self.updating = False

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.Polish):
            self.refresh()
        return super().eventFilter(watched, event)


def baseline(*labels):
    """AlignBottom으로 놓은 한 줄 라벨들을 같은 글자 기준선에 맞춤."""
    _Baseline(labels)


def badge(text="", tone=""):
    """누를 수 없는 꼬리표. 높이 24, 글자 caption 700. tone 은 accent·success·warning·danger, 없으면 회색."""
    out = typed(QLabel(text), "caption", True)
    out.setObjectName("badge")
    out.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if tone:
        out.setProperty("tone", tone)
    out.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return out


class NumberChip(QLabel):
    """번호 칩. 꼬리표와 같은 높이(caption 줄 높이 + 2)이고 모서리 4. 폭은 두 자리 숫자 폭 + 16 이상이라 한 자리 번호도
    같은 폭으로 줄이 맞음. 글자 크기 단계가 바뀌면 refont 가 폭을 다시 잼."""

    def refont(self):
        metrics = QFontMetricsF(self.font())
        if self.property("tile"):  # 정사각 칩. 높이는 스타일시트가 theme.number_tile 로 정함
            self.setMinimumWidth(theme.number_tile())
        else:
            self.setMinimumWidth(max(theme.TYPE["caption"][1] + 2, math.ceil(metrics.horizontalAdvance("00")) + 16))
        self.updateGeometry()


def number_chip(text, tone="", tile=False):
    """줄 앞 번호 칩. text 는 이미 있는 순번 글('01', '3')이고 tone 은 accent·success·solid(주 색 바탕에 흰 글), neutral 이나 빈 값이면 회색.
    tile 이면 테두리 1px 를 두른 정사각(theme.number_tile)으로 그림."""
    out = typed(NumberChip(str(text)), "caption", True)
    out.setObjectName("badge")
    out.setProperty("number", True)
    out.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if tone and tone != "neutral":
        out.setProperty("tone", tone)
    if tile:
        out.setProperty("tile", True)
    out.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    out.refont()
    return out


def segmented(widget, kind="soft"):
    """칩 묶음 widget 을 붙은 칩 모양으로 바꾸고 돌려줌. kind 는 soft(고르면 강조 바탕에 파란 글)·solid(고르면 파란 바탕에 흰 글).
    칩 사이 간격을 0, 상자 여백을 테두리 두께 1 로 두고 양 끝 칩에 seg 속성(first·last·only)을 줘 바깥쪽 모서리만 둥글게 함.
    묶음 높이는 칩 높이 + 2 가 됨. 고름·눌림 동작은 그대로임."""
    widget.setProperty("segmented", kind)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setSizePolicy(widget.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Fixed)  # 남는 높이를 받아 테두리가 늘어나지 않게 함
    layout = widget.layout()
    if layout is not None:
        layout.setSpacing(0)
        layout.setContentsMargins(SEG_EDGE, SEG_EDGE, SEG_EDGE, SEG_EDGE)  # 칩이 묶음 테두리를 덮지 않게 함
    chips = []
    for index in range(layout.count() if layout is not None else 0):
        item = layout.itemAt(index).widget()
        if isinstance(item, QPushButton) and item.objectName() == "chip":
            chips.append(item)
    for index, item in enumerate(chips):
        item.setProperty("seg", "only" if len(chips) == 1 else "first" if index == 0 else "last" if index == len(chips) - 1 else "middle")
    for item in [widget] + chips:
        if item.testAttribute(Qt.WidgetAttribute.WA_WState_Polished):
            repolish(item)
    return widget


class FirstLine(QWidget):
    """꼬리표와 본문 첫 줄의 중심을 맞춤. 줄바꿈 높이나 큰 행간에 따라 꼬리표가 뜨지 않게 함."""

    aligned = pyqtSignal()

    def __init__(self, mark, text, spacing=12, anchor=None, trailing=False):
        super().__init__()
        self.mark, self.text, self.anchor = mark, text, anchor or text
        self.center = 0
        row = box(self, spacing=spacing, horizontal=True)
        self.mark_holder, self.text_holder = QWidget(), QWidget()
        self.mark_box, self.text_box = box(self.mark_holder), box(self.text_holder)
        self.mark_box.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        self.text_box.addWidget(text, 0, Qt.AlignmentFlag.AlignTop)
        if trailing:
            row.addWidget(self.text_holder, 1, Qt.AlignmentFlag.AlignTop)
            row.addWidget(self.mark_holder, 0, Qt.AlignmentFlag.AlignTop)
        else:
            row.addWidget(self.mark_holder, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(self.text_holder, 1, Qt.AlignmentFlag.AlignTop)
        self.setProperty("first_line_pair", True)
        mark.installEventFilter(self)
        if isinstance(text, FirstLine):
            text.aligned.connect(self.refont)

    def text_center(self):
        anchor = self.anchor
        if callable(anchor):
            return anchor()
        if isinstance(anchor, FirstLine):
            return anchor.center
        if isinstance(anchor, QLabel):
            key = (anchor.font().toString(), QLabel.text(anchor), anchor.width())
            top = anchor.mapTo(self.text, QPoint(0, 0)).y() if anchor is not self.text else 0
            if getattr(self, "center_key", None) == key:
                return top + self.glyph_center
            document = QTextDocument()
            document.setDefaultFont(anchor.font())
            document.setDocumentMargin(0)
            document.setHtml(QLabel.text(anchor))
            document.setTextWidth(max(1, anchor.width()))
            document.documentLayout().documentSize()
            block = document.begin()
            line = block.layout().lineAt(0)
            if line.isValid():
                self.center_key = key
                self.glyph_center = line.y() + (line.ascent() + line.descent()) / 2
                return top + self.glyph_center
        return anchor.sizeHint().height() / 2

    def refont(self):
        self.mark.ensurePolished()
        visible = not self.mark.isHidden()
        self.mark_holder.setVisible(visible)
        text = self.text_center()
        mark = max(self.mark.minimumHeight(), self.mark.sizeHint().height(), 0) / 2 if visible else 0
        previous, self.center = self.center, max(mark, text)
        self.mark_box.setContentsMargins(0, math.floor(self.center - mark), 0, 0)
        self.text_box.setContentsMargins(0, math.floor(self.center - text), 0, 0)
        if previous != self.center:
            self.aligned.emit()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest and hasattr(self, "mark"):
            self.refont()
        return result

    def eventFilter(self, watched, event):
        if watched is self.mark and event.type() in (QEvent.Type.ShowToParent, QEvent.Type.HideToParent):
            self.refont()
        return super().eventFilter(watched, event)


class _TabButton(QPushButton):
    auto_check = True

    def nextCheckState(self):
        if self.auto_check or self.isChecked():
            super().nextCheckState()


def button(text="", kind="secondary", scale="m", onbg=False):
    """단추. kind 는 primary·secondary·text·danger·danger_text·chip·tab 가운데 하나, scale 은 l(48)·m(44)·s(32). onbg 는 회색 바탕 위의 글자 단추(올리면 line 색)."""
    out = _TabButton(text) if kind == "tab" else QPushButton(text)
    if kind != "secondary":
        out.setObjectName(kind)
    out.setProperty("scale", scale)
    if onbg:
        out.setProperty("onbg", True)
    out.setAutoDefault(False)
    out.setCursor(Qt.CursorShape.PointingHandCursor)
    out.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # 마우스로 누를 때는 초점 테두리를 그리지 않음
    return out


def chip(text, tid=None, onbg=False):
    """누르면 골라지는 칩(높이 40). onbg 는 회색 바탕 위에 두는 칩임. 평소에는 바탕 없이 글만 보이고 고르면 흰 알약이 됨."""
    out = button(text, "chip", "m", onbg)
    out.setCheckable(True)
    out.tid = tid
    return out


class FlushItem(QWidgetItem):
    """상자 안 위젯 하나를 FLUSH 만큼 왼쪽 여백 쪽으로 내어 두는 상자 칸. widen 이면 오른쪽 끝은 두고 그만큼 넓힘.
    Qt 는 음수 상자 여백을 기본 여백으로 읽어서 여백으로는 내어 둘 수 없음."""

    def __init__(self, widget, widen=False):
        super().__init__(widget)
        self.widen = widen

    def setGeometry(self, rect):
        super().setGeometry(rect.adjusted(-FLUSH, 0, 0, 0) if self.widen else rect.translated(-FLUSH, 0))


def flush_left(layout, widget, widen=False):
    """layout 에 이미 넣은 widget 을 FLUSH 만큼 내어 둠. 맨 앞이 글자 단추라 단추 글자를 위 글과 같은 세로선에 둘 때 씀
    (막대 가장자리 단추는 TopBar·BottomBar 가 막대 여백으로 같은 일을 함)."""
    index = layout.indexOf(widget)
    layout.takeAt(index)
    layout.insertItem(index, FlushItem(widget, widen))
    return widget


def frame(name):
    out = QFrame()
    out.setObjectName(name)
    return out


def box(widget, margins=(0, 0, 0, 0), spacing=0, horizontal=False):
    """위젯에 세로(또는 가로) 상자를 붙이고 돌려줌."""
    layout = QHBoxLayout(widget) if horizontal else QVBoxLayout(widget)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def card(pad=24, spacing=16):
    """흰 카드(surface, 모서리 16, 얇은 테두리)와 그 안의 세로 상자."""
    out = frame("card")
    return out, box(out, (pad, pad, pad, pad), spacing)


def well(pad_x=16, pad_y=12, spacing=4):
    """카드 안의 회색 칸(면접관 말, 코드 상자, 내 답)."""
    out = frame("well")
    return out, box(out, (pad_x, pad_y, pad_x, pad_y), spacing)


def column(widget, width=HOME_WIDTH):
    """widget 을 width 까지의 가운데 단에 둠. 창이 넓으면 양옆이 바탕으로 남음."""
    widget.setMaximumWidth(width)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    outer = QWidget()
    row = box(outer, horizontal=True)
    row.addStretch(1)
    row.addWidget(widget, 100)  # 단이 최대 폭에 닿으면 남는 폭을 양옆이 똑같이 나눔
    row.addStretch(1)
    return outer


class DenseColumn(QWidget):
    """widget 을 좌우 여백 DENSE_MARGIN 에 두고, 창이 넓으면 width 를 넘는 만큼 좌우 여백을 똑같이 늘려 가운데에 둠.
    column 과 달리 최대 폭보다 좁을 때 양옆에 늘림 몫이 생기지 않아 본문 좌우가 촘촘한 위 막대의 내용 선과 맞음."""

    def __init__(self, widget, width=HOME_WIDTH):
        super().__init__()
        self.cap = width
        box(self, (DENSE_MARGIN, 0, DENSE_MARGIN, 0)).addWidget(widget)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        side = DENSE_MARGIN + max(0, self.width() - self.cap - 2 * DENSE_MARGIN) // 2
        if self.layout().contentsMargins().left() != side:
            self.layout().setContentsMargins(side, 0, side, 0)


def dense_column(widget, width=HOME_WIDTH):
    """DenseColumn 을 감싼 위젯. 바깥 상자의 여백은 Workspace 가 제출 알림 자리를 더할 때 쓰므로 DenseColumn 의 여백과 나눔."""
    outer = QWidget()
    box(outer).addWidget(DenseColumn(widget, width))
    return outer


def scroll(inner):
    """창이 작으면 내용을 찌그러뜨리지 않고 스크롤하는 칸. inner 는 바탕색을 가진 page 위젯."""
    inner.setObjectName("page")
    area = QScrollArea()
    area.setObjectName("page")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(inner)
    return area


def section(title, caption=""):
    """홈 화면의 구역 이름 줄. (줄, 제목 라벨, 오른쪽 caption 라벨)."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    head = label(title, "headline")
    note = label(caption, "caption", "secondary")
    row.addWidget(head, 0, Qt.AlignmentFlag.AlignBottom)
    row.addStretch(1)
    row.addWidget(note, 0, Qt.AlignmentFlag.AlignBottom)
    baseline(head, note)
    return row, head, note


def card_head(title, *right):
    """카드 머리 줄. (줄, 제목). title 은 글이면 headline 라벨을 만들고 위젯이면 그대로 씀. 제목이 남는 폭을 받고
    right 의 위젯들은 오른쪽 끝에 세로 가운데로 둠."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    head = label(title, "headline") if isinstance(title, str) else title
    row.addWidget(head, 1, Qt.AlignmentFlag.AlignVCenter)
    for widget in right:
        row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
    return row, head


def spaced(*items, spacing=4):
    """위젯들을 간격 spacing 으로 세로로 쌓은 묶음 위젯."""
    out = QWidget()
    inner = box(out, spacing=spacing)
    for item in items:
        inner.addWidget(item)
    return out


def heading(title, description):
    """제목과 설명을 묶음. 설명이 숨으면 두 글 사이 간격도 남기지 않음."""
    if isinstance(title, QLayout):
        row = QWidget()
        row.setLayout(title)
        title = row
    out = spaced(title, description, spacing=theme.GAP["title_description"])
    out.title, out.description = title, description
    out.setProperty("spacing_role", "title_description")
    return out


def banner(text="", tone="", lead="", action=""):
    """안내·주의·오류·완료 띠. 글 Para 는 out.text, 앞 낱말은 out.word. lead 가 없으면 tone 에 맞는 앞 낱말을 씀.
    action 이 있으면 글 오른쪽에 그 이름의 보조 단추 m 을 두고 out.action 으로 돌려줌(없으면 None). 띠 안 단추의 바탕은
    theme.STYLE_V2 가 surface 로 칠함. 단추가 있는 띠는 앞 낱말과 글을 한 묶음으로 단추 높이의 가운데에 둠."""
    out = frame("banner")
    words = {"": "안내", "warning": "주의", "danger": "오류", "success": "완료"}
    if tone:
        out.setProperty("tone", tone)
    row = box(out, (16, 12, 16, 12), 8, horizontal=True)
    word = label(lead or words.get(tone, "안내"), "body", bold=True)
    word.setObjectName("lead")
    text_label = para(text)
    line = row
    if action:  # 글이 한 줄이면 묶음이 단추의 가운데 높이에 옴. 두 줄 이상이면 띠가 글 높이를 따름
        holder = QWidget()
        line = box(holder, spacing=8, horizontal=True)
        row.addWidget(holder, 1, Qt.AlignmentFlag.AlignVCenter)
    out.pair = FirstLine(word, text_label, spacing=8)
    line.addWidget(out.pair, 1)
    out.text = text_label
    out.word = word
    out.action = None
    if action:
        out.action = button(action, "secondary", "m")
        row.addWidget(out.action, 0, Qt.AlignmentFlag.AlignVCenter)
    return out


def progress(thin=False):
    """진행 막대(8px)나 시간 막대(4px). set_tone 으로 success·warning·danger 로 바꿈."""
    out = QProgressBar()
    out.setTextVisible(False)
    out.setRange(0, 100)
    if thin:
        out.setProperty("thin", True)
    out.setFixedHeight(4 if thin else 8)
    return out


def clock(caption_text="남은 시간"):
    """작업 화면 위 막대 오른쪽의 시계: caption 과 display 숫자. (묶음 위젯, caption 라벨, 숫자 라벨)."""
    out = QWidget()
    row = box(out, spacing=12, horizontal=True)
    cap = label(caption_text, "caption", "tertiary")
    num = label("", "display")
    num.setProperty("measure", "88:88")  # 자릿수가 바뀌어도 폭이 흔들리지 않게 이 글자의 폭을 최소 폭으로 둠. refont 도 같은 글자로 다시 잼
    num.setMinimumWidth(math.ceil(QFontMetricsF(num.font()).horizontalAdvance("88:88")))
    row.addWidget(cap, 0, Qt.AlignmentFlag.AlignBottom)
    row.addWidget(num, 0, Qt.AlignmentFlag.AlignBottom)
    baseline(cap, num)
    return out, cap, num


class ElideLabel(QLabel):
    """폭이 모자라면 줄임표로 줄이는 한 줄 글. 전체 글은 도움말에 둠."""

    def __init__(self, text="", role="headline", tone="", bold=None):
        super().__init__()
        self.full = ""
        typed(self, role, bold)
        if tone:
            self.setProperty("tone", tone)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def refont(self):
        self._fit()
        self.updateGeometry()

    def setText(self, text):
        self.full = text
        self.setToolTip(text)
        self._fit()

    def text(self):
        return self.full

    def _fit(self):
        metrics = QFontMetricsF(self.font())
        super().setText(metrics.elidedText(self.full, Qt.TextElideMode.ElideRight, max(1, self.width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def sizeHint(self):
        return QSize(math.ceil(QFontMetricsF(self.font()).horizontalAdvance(self.full)) + 2, super().sizeHint().height())


class Dot(QWidget):
    """상태 점. state 는 progress(채운 파랑)·review(채운 주황)·done(초록 원 안 체크)·todo(테두리 원)·ready(채운 초록)·lock(자물쇠),
    또는 색 토큰 이름. size 는 지름(트랙 이름 앞은 8, 목록 줄은 10, 끝남 체크는 16). 자물쇠는 size 와 무관하게 높이 16 으로 그림.
    2px 선으로 고리(폭 6, 높이 8)를 긋고 그 아래에 몸통(10×8, 모서리 2)을 채움."""

    def __init__(self, state="todo", size=10):
        super().__init__()
        self.state, self.size = state, size
        self.setFixedSize(MARK, MARK)

    def set_state(self, state):
        self.state = state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        token = DOT_STATES.get(self.state, self.state)
        color = theme.qcolor(token)
        if self.state == "lock":
            self.paint_lock(painter, color)
            return
        size = 16 if self.state == "done" else self.size
        rect = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size)
        if self.state == "todo":
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(1, 1, -1, -1))
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(rect)
        if self.state == "done":
            painter.setPen(QPen(theme.qcolor("surface"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            path = QPainterPath(QPointF(rect.left() + 4, rect.top() + 8.5))
            path.lineTo(rect.left() + 7, rect.top() + 11.5)
            path.lineTo(rect.left() + 12, rect.top() + 5.5)
            painter.drawPath(path)

    def paint_lock(self, painter, color):
        """칸 가운데에 자물쇠를 그림. 위 끝 2 에서 아래 끝 18 까지 높이 16 을 차지함. 고리 선의 가운데는 x 7~13 이고
        반원 꼭대기 y 3 에서 몸통 위 10 까지 내려옴."""
        middle = self.width() / 2
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(QPointF(middle - 3, 10.5))
        path.lineTo(middle - 3, 6)
        path.arcTo(QRectF(middle - 3, 3, 6, 6), 180, -180)
        path.lineTo(middle + 3, 10.5)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(middle - 5, 10, 10, 8), 2, 2)


class Chevron(QWidget):
    """목록 줄 오른쪽 끝의 꺾쇠. 꺼지면(바쁜 동안 꺼진 줄) 그리지 않고 자리만 남김."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(MARK, MARK)

    def paintEvent(self, event):
        if not self.isEnabled():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(theme.qcolor("faint"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(QPointF(7, 5))
        path.lineTo(12, 10)
        path.lineTo(7, 15)
        painter.drawPath(path)


class Row(QFrame):
    """목록 줄. 왼쪽 상태 점(없을 수 있음), 앞 위젯 lead(번호 칩 등, 없을 수 있음), 제목과 둘째 줄, 오른쪽 caption 과 꺾쇠. 줄 전체를 한 번 누르면 clicked 가 남.
    한 줄이면 최소 높이 56, 둘째 줄이 있으면 80을 확보함. wrap이면 긴 글을 줄바꿈하고 그 높이를 더함. 나머지는 줄임표로 줄임.
    올리면 hover 색, 누르면 surface_alt, 키보드 초점은 안쪽 2px 테두리.
    꺼지면 글이 faint 색이 되고 꺾쇠를 그리지 않음(theme.STYLE_V2, Chevron)."""
    clicked = pyqtSignal()

    def __init__(self, title, second="", end="", mark=None, data=None, strong=False, inert=False, wrap=False, lead=None):
        super().__init__()
        self.setObjectName("row")
        self.data, self.inert, self.down = data, inert, False
        self.wrap = wrap
        self.setMinimumHeight(theme.CONTROL["row2"] if second else theme.CONTROL["row"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 남는 자리를 줄이 나눠 갖지 않음
        row = box(self, (24, 0, 24, 0), 12, horizontal=True)
        self.mark = mark
        if mark is not None:
            row.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lead = lead
        if lead is not None:
            row.addWidget(lead, 0, Qt.AlignmentFlag.AlignVCenter)
        self.least, self.pad = None, 12
        text = QWidget()
        column_box = self.text_box = box(text, (0, 12, 0, 12), theme.GAP["detail"])
        if wrap:
            self.title = para(title, "label", bold=strong)
            self.second = para(second, "caption", "secondary")
        else:
            self.title = ElideLabel(title, "label", bold=strong)
            self.second = ElideLabel(second, "caption", "secondary")
            self.title.setFixedHeight(theme.TYPE["label"][1])
            self.second.setFixedHeight(theme.TYPE["caption"][1])
        column_box.addWidget(self.title)
        column_box.addWidget(self.second)
        row.addWidget(text, 1, Qt.AlignmentFlag.AlignVCenter)
        self.end = label(end, "caption", "tertiary")
        row.addWidget(self.end, 0, Qt.AlignmentFlag.AlignVCenter)
        self.chevron = Chevron()
        row.addWidget(self.chevron, 0, Qt.AlignmentFlag.AlignVCenter)
        # 부모가 생긴 뒤에 보이고 숨김. 부모 없는 위젯을 보이면 잠깐 따로 창으로 떠서 화면의 창이 초점을 잃음
        self.second.setVisible(bool(second))
        self.end.setVisible(bool(end))
        self.chevron.setVisible(not inert)
        if not inert:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_second(self, text):
        self.second.setText(text)
        self.second.setVisible(bool(text))
        self.fit_height()

    def refont(self):
        """글자 크기 단계가 바뀐 뒤 두 줄의 높이를 지금 줄 높이로."""
        if not self.wrap:
            self.title.setFixedHeight(theme.TYPE["label"][1])
            self.second.setFixedHeight(theme.TYPE["caption"][1])
        self.fit_height()

    def set_least(self, least, pad=12, gap=8):
        """최소 높이를 least 로 바꾸고 글 묶음 위아래 여백을 pad, 두 줄 사이를 gap 으로 둠.
        높이는 max(least, 글 높이 + 2 * pad) 라 큰 글자에서는 글만큼 늘어남."""
        self.least, self.pad = least, pad
        self.text_box.setSpacing(gap)
        self.fit_height()

    def fit_height(self):
        """줄바꿈한 글과 안쪽 여백이 들어갈 높이를 확보함. 짧은 글로 바꾸면 높이도 줄임.
        set_least 를 불렀으면 CONTROL 의 row·row2 대신 그 최소 높이와 여백을 씀. 이때 pad 는 줄 테두리 바깥에서 글까지라
        테두리가 있는 줄(separate)은 글 묶음 여백에서 테두리 두께를 뺌."""
        gap = self.text_box.spacing()
        if self.least is None:
            _, pad, _, _ = self.text_box.getContentsMargins()
            height = theme.CONTROL["row2"] if self.second.text() else theme.CONTROL["row"]
        else:
            pad, inset = self.pad, max(0, self.pad - self.frameWidth())
            self.text_box.setContentsMargins(0, inset, 0, inset)
            text_height = theme.TYPE["label"][1]
            if self.second.text():
                text_height += gap + theme.TYPE["caption"][1]
            height = max(self.least, text_height + 2 * pad)
        if self.wrap:
            width = max(1, self.width() - 48 - 12 - MARK - (MARK + 12 if self.mark is not None else 0)
                        - (self.lead.sizeHint().width() + 12 if self.lead is not None and not self.lead.isHidden() else 0)
                        - (self.end.sizeHint().width() + 12 if self.end.text() else 0))
            text_height = self.title.heightForWidth(width)
            if self.second.text():
                text_height += gap + self.second.heightForWidth(width)
            height = max(height, text_height + 2 * pad)
        if self.wrap:
            self.setFixedHeight(height)
        else:
            self.setMinimumHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_height()

    def _flag(self, name, on):
        if self.property(name) != on:
            self.setProperty(name, on)
            repolish(self)

    def enterEvent(self, event):
        if not self.inert:
            self._flag("over", True)

    def leaveEvent(self, event):
        self._flag("over", False)

    def mousePressEvent(self, event):
        self.down = event.button() == Qt.MouseButton.LeftButton and not self.inert
        self._flag("down", self.down)
        event.accept()

    def mouseReleaseEvent(self, event):
        down, self.down = self.down, False
        self._flag("down", False)
        if down and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and not self.inert:
            if not event.isAutoRepeat():  # 누르고 있어도 한 번만 엶
                self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus() and not self.inert:
            painter = QPainter(self)
            painter.setPen(QPen(theme.qcolor("focus"), 2))
            painter.drawRect(QRectF(self.rect()).adjusted(1, 1, -1, -1))


def set_inert(row, inert):
    """목록 줄을 누를 수 없게(또는 다시 누를 수 있게) 바꿈. 꺾쇠와 손 모양 커서, 키보드 초점을 같이 바꿈."""
    row.inert = inert
    row.chevron.setVisible(not inert)
    row.setCursor(Qt.CursorShape.ArrowCursor if inert else Qt.CursorShape.PointingHandCursor)
    row.setFocusPolicy(Qt.FocusPolicy.NoFocus if inert else Qt.FocusPolicy.StrongFocus)
    if inert:
        row.setProperty("over", False)
        repolish(row)


def link_banner(tone=""):
    """링크가 든 글을 담는 띠. banner 의 글 자리에 LinkLabel 을 둠. (띠, LinkLabel)."""
    out = banner("", tone)
    link = typed(LinkLabel("", line=theme.TYPE["body"][1], font=theme.font("body")), "body")
    out.pair.text_box.replaceWidget(out.text, link)
    out.pair.text = out.pair.anchor = link
    out.text.hide()
    out.text.deleteLater()
    out.text = link
    return out, link


class RowList(QFrame):
    """줄을 세로로 쌓은 흰 목록. 줄 사이에만 line 색 1px 선(좌우 24 들여서). 준비 중 항목은 끝의 글자 단추 하나로 접음.
    flush 면 카드 안 이름표 아래에 두는 목록이라 줄과 선을 들이지 않고 이름표와 같은 세로선에 맞춤.
    separate 면 선 없이 줄마다 따로 테두리 상자가 되고 줄 사이를 8 띄움. 상자 모양은 kit.dense 아래에서만 걸림(theme.STYLE_V2).
    least 를 주면 더하는 줄마다 Row.set_least(least, pad, gap) 를 부름.
    striped 면 줄 사이 선을 긋지 않고 짝수 번째 줄에 stripe 속성을 줘 surface_alt 바탕을 칠함."""

    def __init__(self, inside_card=False, flush=False, separate=False, least=None, pad=12, gap=8, striped=False):
        super().__init__()
        self.setObjectName("rows" if inside_card or flush or separate else "card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.flush, self.separate, self.striped = flush, separate, striped
        self.least, self.pad, self.gap = least, pad, gap
        self.box = box(self, spacing=8 if separate else 0)
        self.rows, self.lines, self.more_btn, self.more_list = [], [], None, None

    def clear(self):
        for widget in self.rows + self.lines + [w for w in (self.more_btn, self.more_list) if w is not None]:
            self.box.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self.rows, self.lines, self.more_btn, self.more_list = [], [], None, None
        while self.box.count():
            self.box.takeAt(0)

    def add(self, row):
        if self.separate:
            row.setProperty("separate", True)
            repolish(row)
        if self.least is not None:
            row.set_least(self.least, self.pad, self.gap)
        if self.striped and len(self.rows) % 2:
            row.setProperty("stripe", True)
            repolish(row)
        if self.rows and not self.separate and not self.striped:
            line = frame("rowline")
            line.setFixedHeight(1)
            line.setContentsMargins(0, 0, 0, 0)
            holder = QWidget()
            holder_box = box(holder, (0, 0, 0, 0) if self.flush else (24, 0, 24, 0))
            holder_box.addWidget(line)
            self.box.addWidget(holder)
            self.lines.append(holder)
        if self.flush:
            row.layout().setContentsMargins(0, 0, 0, 0)
        self.box.addWidget(row)
        self.rows.append(row)
        return row

    def add_more(self, names, what="준비 중"):
        """준비 중인 이름들을 '준비 중 N개 보기' 단추로 접음. 단추 글자는 줄 제목과 같은 세로선(24 + 20 + 12)에 맞춤."""
        if not names:
            return None
        holder = QWidget()
        holder_box = box(holder, (ROW_TEXT - FLUSH, 8, 24, 12))
        self.more_btn = button("%s %d개 보기" % (what, len(names)), "text", "s")
        self.more_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        holder_box.addWidget(self.more_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.box.addWidget(holder)
        self.more_list = QWidget()
        list_box = box(self.more_list, (ROW_TEXT, 0, 24, 16), 4)
        for name in names:
            list_box.addWidget(label(name, "caption", "tertiary"))
        self.more_list.hide()
        self.box.addWidget(self.more_list)
        closed = self.more_btn.text()

        def toggle():
            opened = not self.more_list.isVisible()
            self.more_list.setVisible(opened)
            self.more_btn.setText("접기" if opened else closed)

        self.more_btn.clicked.connect(toggle)
        self.lines.append(holder)  # clear 가 같이 치움
        return self.more_btn


class FlowLayout(QLayout):
    """가로로 늘어놓다가 폭이 모자라면 다음 줄로 넘기는 배치(주제 칩). 줄 사이와 칸 사이 간격은 spacing 하나로 씀.
    centered 면 줄마다 남는 폭을 좌우로 똑같이 나눠 그 줄을 가운데에 둠."""

    def __init__(self, parent=None, spacing=8, centered=False):
        super().__init__(parent)
        self.items = []
        self.centered = centered
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._place(rect, move=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def line_width(self):
        """보이는 칸을 모두 한 줄에 놓는 폭(좌우 여백 포함). sizeHint 는 가장 넓은 칸 하나의 폭만 돌려주므로 한 줄 폭이 필요하면 이 함수를 씀."""
        left, _, right, _ = self.getContentsMargins()
        widths = [item.sizeHint().expandedTo(item.minimumSize()).width() for item in self.items
                  if item.widget() is None or item.widget().isVisibleTo(item.widget().parentWidget())]
        return sum(widths) + self.spacing() * max(0, len(widths) - 1) + left + right

    def _place(self, rect, move):
        left, top, right, bottom = self.getContentsMargins()
        area = rect.adjusted(left, top, -right, -bottom)
        x, y, line = area.x(), area.y(), 0
        gap = self.spacing()
        pending = []

        def place_line():
            if move:
                shift = max(0, area.right() + 1 - (x - gap)) // 2 if self.centered else 0
                for child, start, size in pending:
                    child.setGeometry(QRect(QPoint(start + shift, y + (line - size.height()) // 2), size))

        for item in self.items:
            if item.widget() is not None and not item.widget().isVisibleTo(item.widget().parentWidget()):
                continue
            hint = item.sizeHint().expandedTo(item.minimumSize())
            if x > area.x() and x + hint.width() > area.right() + 1:
                place_line()
                x, y, line = area.x(), y + line + gap, 0
                pending = []
            pending.append((item, x, hint))
            x += hint.width() + gap
            line = max(line, hint.height())
        place_line()
        return y + line - rect.y() + bottom


class Stepper(QWidget):
    """미션 단계 표시. steps 는 (번호, 이름, 상태) 목록이고 상태는 done·now·skip·lock. 원 28, 원 사이 2px 선, 끝난 구간은 link 색.
    이름표는 caption 14 이고 지금 단계만 굵게, 잠긴 단계는 번호만 보임(이름 없음). 높이 56 의 줄 안에서 그림.
    dense 면 높이 48(CONTROL["stepper_dense"]) 의 줄 안에서 그리고, 원 사이 선을 CONN_MAX 대신 DENSE_CONN_MAX 까지 늘려 줄 폭을 채움."""

    CIRCLE, GAP, LABEL_MAX, CONN_MIN, CONN_MAX, DENSE_CONN_MAX = 28, 8, 120, 16, 160, 400

    def __init__(self, dense=False):
        super().__init__()
        self.steps = []
        self.dense = dense
        self.setFixedHeight(theme.CONTROL["stepper_dense" if dense else "stepper"] - 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_steps(self, steps):
        self.steps = list(steps)
        self.setToolTip("\n".join("%s %s" % (no, title or "잠김") for no, title, _ in self.steps))
        self.update()

    def _label_width(self, metrics, title, state):
        """단계 이름이 차지하는 폭. 넘어간 단계는 이름 대신 '넘어감'을 쓰므로 그 폭으로 잼."""
        if state == "lock" or not title:
            return 0
        return min(self.LABEL_MAX, math.ceil(metrics.horizontalAdvance("넘어감" if state == "skip" else title)))

    def paintEvent(self, event):
        if not self.steps:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = theme.font("caption")
        bold = theme.font("caption", True)
        metrics = QFontMetricsF(bold)
        widths = [self.CIRCLE + (self.GAP + self._label_width(metrics, title, state) if self._label_width(metrics, title, state) else 0)
                  for _, title, state in self.steps]
        conns = max(0, len(self.steps) - 1)
        room = self.width() - sum(widths) - conns * 24
        conn = max(self.CONN_MIN, min(self.DENSE_CONN_MAX if self.dense else self.CONN_MAX, room / conns)) if conns else 0
        x, middle = 0.0, float(self.height() // 2)  # 정수 줄에 맞춰 2px 선과 원이 반 화소로 번지지 않게
        for number, ((no, title, state), width) in enumerate(zip(self.steps, widths)):
            circle = QRectF(x, middle - self.CIRCLE / 2, self.CIRCLE, self.CIRCLE)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor({"done": "selection", "now": "primary"}.get(state, "surface_alt")))
            painter.drawEllipse(circle)
            if state == "done":
                painter.setPen(QPen(theme.qcolor("selection_ink"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                path = QPainterPath(QPointF(circle.left() + 8, middle + 0.5))
                path.lineTo(circle.left() + 12, middle + 4.5)
                path.lineTo(circle.left() + 20, middle - 4.5)
                painter.drawPath(path)
            elif state == "skip":
                painter.setPen(QPen(theme.qcolor("retry"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(QPointF(circle.left() + 8, middle), QPointF(circle.right() - 8, middle))
            else:
                painter.setFont(bold)
                painter.setPen(theme.qcolor("primary_ink" if state == "now" else "faint"))
                painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(no))
            x += self.CIRCLE
            text_width = self._label_width(metrics, title, state)
            if text_width:
                x += self.GAP
                painter.setFont(bold if state == "now" else font)
                painter.setPen(theme.qcolor({"now": "ink", "done": "muted", "skip": "retry"}.get(state, "faint")))
                shown = "넘어감" if state == "skip" else title
                painter.drawText(QRectF(x, 0, text_width + 1, self.height()), Qt.AlignmentFlag.AlignVCenter,
                                 metrics.elidedText(shown, Qt.TextElideMode.ElideRight, text_width + 1))
                x += text_width
            if number < conns:
                painter.setPen(QPen(theme.qcolor("link" if state in ("done", "skip") else "line"), 2))
                painter.drawLine(QPointF(x + 12, middle), QPointF(x + 12 + conn, middle))
                x += 24 + conn


class TabBar(QWidget):
    """같은 자리의 내용을 바꾸는 탭. 체크형 단추를 QButtonGroup 으로 묶고 아래에 line 1px. picked(번호)가 남."""
    picked = pyqtSignal(int)

    def __init__(self, names, deferred=False):
        super().__init__()
        outer = box(self)
        row = QHBoxLayout()
        row.setContentsMargins(24, 8, 24, 0)
        row.setSpacing(24)
        self.group = QButtonGroup(self)
        self.buttons = []
        for number, name in enumerate(names):
            tab = button(name, "tab")
            tab.auto_check = not deferred
            tab.setCheckable(True)
            typed(tab, "label", True)
            self.group.addButton(tab, number)
            row.addWidget(tab)
            self.buttons.append(tab)
        row.addStretch(1)
        outer.addLayout(row)
        line = frame("rowline")
        line.setFixedHeight(1)
        outer.addWidget(line)
        self.group.idClicked.connect(self.picked.emit)
        if self.buttons:
            self.buttons[0].setChecked(True)

    def set_current(self, number):
        self.buttons[number].setChecked(True)

    def set_visible(self, number, visible):
        self.buttons[number].setVisible(visible)


class NavigationTabs(TabBar):
    """상위 탐색 항목을 같은 폭과 큰 글자로 표시함."""
    def __init__(self, names, deferred=False):
        super().__init__(names, deferred=deferred)
        self.layout().itemAt(1).widget().hide()
        row = self.layout().itemAt(0).layout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.GAP["detail"])
        row.takeAt(row.count() - 1)
        for number, tab in enumerate(self.buttons):
            typed(tab, "headline", True)
            row.setStretch(number, 1)
        self.refont()

    def refont(self):
        height = theme.TYPE["headline"][1] + theme.GAP["group"]
        color = lambda key: theme.qcolor(key).name()
        self.setStyleSheet(f"""
            QPushButton#tab {{ background: {color('surface')}; color: {color('ink')};
                font-size: {theme.TYPE['headline'][0]}px; font-weight: 700;
                min-height: {height}px; max-height: {height}px; padding: 0 16px;
                border: 2px solid {color('line')}; border-radius: {theme.RADIUS['control']}px; }}
            QPushButton#tab:hover {{ background: {color('hover')}; }}
            QPushButton#tab:checked {{ background: {color('selection')}; color: {color('selection_ink')};
                border-color: {color('link')}; }}
            QPushButton#tab:focus {{ border-color: {color('focus')}; border-style: dashed; }}
            QPushButton#tab:disabled {{ color: {color('faint')}; background: {color('bg')}; }}
            QPushButton#tab:checked:disabled {{ background: {color('selection')}; }}
        """)


class SplitHandle(QSplitterHandle):
    """칸 나누기의 손잡이. 바탕은 스타일시트(bg)가 칠하고 가운데에 GRIP 무늬(가로로 누운 손잡이는 32×4, 모서리 2)를 그림.
    무늬 색은 평소 border 이고 마우스를 올리면 scroll_hover 로 바뀜. 두 번 누르면 처음 몫으로 돌아감. 칸 나누기가 잠기면 무늬를 그리지 않음."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.over = False

    def enterEvent(self, event):
        super().enterEvent(event)
        self.over = True
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.over = False
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.splitter().locked:
            self.splitter().reset()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.splitter().locked:
            return
        short, long = GRIP
        width, height = (short, long) if self.orientation() == Qt.Orientation.Horizontal else (long, short)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor("scroll_hover" if self.over else "border"))
        painter.drawRoundedRect(QRectF((self.width() - width) // 2, (self.height() - height) // 2, width, height), 2, 2)  # 정수 자리에 둬 번지지 않게


class Splitter(QSplitter):
    """사람이 끌어서 두 칸의 몫을 바꾸는 칸 나누기(splitter 가 만듦). 칸은 접히지 않음. 가로로 놓인 칸은 PANE_MIN 보다 좁아지지 않음.
    첫 칸의 몫(0~1)을 ratio 로 들고 창 크기가 바뀌어도 그 몫을 지킴(QSplitter 는 마지막으로 받은 크기의 비율로 나눔).
    사람이 끌면 그 몫을 settings 의 key 에 적음. 다음에 같은 key 로 만들면 그 몫으로 시작함. set_locked 는 손잡이를 끄고 무늬를 숨김."""

    def __init__(self, orientation, key="", ratio=0.5, handle=24, settings=None):
        super().__init__(orientation)
        self.key, self.start, self.settings = key, ratio, settings
        self.locked = False
        self.ratio = self.saved()
        self.setHandleWidth(handle)
        self.setChildrenCollapsible(False)
        self.splitterMoved.connect(self.moved)

    def createHandle(self):
        return SplitHandle(self.orientation(), self)

    def addWidget(self, widget):
        if self.orientation() == Qt.Orientation.Horizontal:
            widget.setMinimumWidth(max(widget.minimumWidth(), PANE_MIN))
        super().addWidget(widget)
        if self.count() == 2:
            self.place()

    def saved(self):
        """설정에 적힌 몫. 설정이 없거나 값이 0~1 사이의 수가 아니면 처음 몫."""
        if self.settings is None or not self.key:
            return self.start
        try:
            value = float(self.settings.value(self.key, self.start))
        except (TypeError, ValueError):
            return self.start
        return value if 0 < value < 1 else self.start

    def place(self):
        """지금 몫으로 두 칸의 크기를 줌. 크기는 비율로만 쓰이므로 큰 수로 나눠 주면 Qt 가 칸 폭에 맞춰 나눔."""
        first = round(self.ratio * 10000)
        self.setSizes([first, 10000 - first])

    def remember(self):
        if self.settings is not None and self.key:
            self.settings.setValue(self.key, round(self.ratio, 4))

    def moved(self, *_):
        sizes = self.sizes()
        if len(sizes) == 2 and sum(sizes) > 0:
            self.ratio = sizes[0] / sum(sizes)
            self.remember()

    def reset(self):
        """처음 몫으로 되돌리고 기억함(손잡이를 두 번 누를 때)."""
        self.ratio = self.start
        self.place()
        self.remember()

    def set_locked(self, locked):
        """손잡이를 끄거나(끌리지 않고 무늬를 그리지 않음) 다시 켬. 잠근 동안의 칸 크기는 부른 쪽이 칸의 최대 크기로 정함."""
        self.locked = bool(locked)
        split = Qt.CursorShape.SplitHCursor if self.orientation() == Qt.Orientation.Horizontal else Qt.CursorShape.SplitVCursor
        for index in range(1, self.count()):
            grip = self.handle(index)
            grip.setEnabled(not self.locked)
            grip.setCursor(Qt.CursorShape.ArrowCursor if self.locked else split)
            grip.update()


def splitter(orientation, key="", ratio=0.5, handle=24, settings=None):
    """사람이 끌어 옮기는 두 칸 나누기. orientation 은 Qt.Orientation, 손잡이 폭 handle 은 가로 나누기 24, 세로 나누기 16.
    ratio 는 첫 칸의 처음 몫(0~1)이고 옮긴 몫은 settings(QSettings)의 key 에 0~1 값으로 남음."""
    return Splitter(orientation, key, ratio, handle, settings)


class TopBar(QFrame):
    """화면 위 막대(높이 64). plain 이면 홈처럼 바탕색이고 선이 없음, steps 이면 아래에 단계 표시가 이어져 선을 그쪽이 그림.
    왼쪽에 back 글자 단추(← 도착 화면 이름)와 제목, 오른쪽에 부른 쪽이 넣는 것. 가장자리의 글자 단추는 FLUSH 만큼 내어 글자를 내용 선에 맞춤.
    dense 면 높이 CONTROL["topbar_dense"](56), 좌우 여백 DENSE_MARGIN(24)이고 막대 안 부품에 촘촘한 모서리를 씀."""

    def __init__(self, back_text="", title="", plain=False, steps=False, dense=False):
        super().__init__()
        self.setObjectName("topbar")
        self.margin = DENSE_MARGIN if dense else MARGIN
        self.setFixedHeight(theme.CONTROL["topbar_dense" if dense else "topbar"])
        if plain:
            self.setProperty("plain", True)
        if steps:
            self.setProperty("steps", True)
        if dense:
            self.setProperty("density", "dense")  # 아직 칠하기 전이라 kit.dense 와 같음
        margin = self.margin
        self.row = box(self, (margin - FLUSH if back_text else margin, 0, margin, 0), 12, horizontal=True)
        self.back = None
        if back_text:
            self.back = button(back_text, "text", "m", onbg=plain)
            self.row.addWidget(self.back)
        self.title = ElideLabel(title, "headline")
        self.row.addWidget(self.title, 1)
        self.title.setVisible(bool(title))  # 부모에 붙인 뒤에 보임. Row 와 같은 까닭

    def add_right(self, widget, flush=False):
        """오른쪽 끝에 위젯을 더함. flush 면 글자 단추라 오른쪽 여백을 FLUSH 만큼 줄임."""
        if flush:
            left, top, _, bottom = self.row.getContentsMargins()
            self.row.setContentsMargins(left, top, self.margin - FLUSH, bottom)
        self.row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return widget


def outline_settings(screen):
    """창이 add_settings 로 위 막대에 붙인 설정 단추에 테두리를 주고, 줄였던 오른쪽 여백을 막대 여백으로 되돌림.
    설정 단추는 화면이 처음 보일 때 붙어 있으므로 showEvent 에서 부름. 이미 테두리가 있으면 아무것도 하지 않음."""
    settings = getattr(screen, "settings_btn", None)
    if settings is None or settings.property("outlined"):
        return
    settings.setProperty("outlined", True)
    repolish(settings)
    left, top, _, bottom = screen.top.row.getContentsMargins()
    screen.top.row.setContentsMargins(left, top, screen.top.margin, bottom)


class BottomBar(QFrame):
    """작업 화면 아래 막대. 최소 높이 80이고 좁은 창에서는 도구를 위로 옮김. 주 단추는 오른쪽 끝에 둠.
    dense 면 최소 높이 CONTROL["bottombar_dense"](64), 좌우 여백 DENSE_MARGIN(24)이고 막대 안 단추에 촘촘한 모서리를 씀."""

    class _Actions(QWidget):
        def sizeHint(self):
            layout = self.layout()
            width = layout.natural_width()
            size = layout.minimumSize()
            size.setWidth(width)
            size.setHeight(layout.heightForWidth(width))
            return size

    def __init__(self, dense=False):
        from gui.action_layout import ActionLayout

        super().__init__()
        self.setObjectName("bottombar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.least = theme.CONTROL["bottombar_dense" if dense else "bottombar"]
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        if dense:
            self.setProperty("density", "dense")  # 아직 칠하기 전이라 kit.dense 와 같음
            self.row.setContentsMargins(DENSE_MARGIN - FLUSH, DENSE_BAR_PAD, DENSE_MARGIN, DENSE_BAR_PAD)
        else:
            self.row.setContentsMargins(MARGIN - FLUSH, 16, MARGIN, 16)
        self.row.setSpacing(8)
        self.tool_box = QWidget()
        self.tools = FlowLayout(self.tool_box, spacing=24)
        self.actions = self._Actions()
        self.action_row = ActionLayout(self.actions, margins=(0, 0, 0, 0),
                                       spacing=theme.GAP["detail"], reverse_stacked=False)
        self.row.addWidget(self.tool_box, 1, Qt.AlignmentFlag.AlignVCenter)
        self.row.addWidget(self.actions, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tool_box.installEventFilter(self)
        self.actions.installEventFilter(self)
        self.setMinimumHeight(self.least)

    def add_tool(self, widget):
        self.tools.addWidget(widget)
        self.arrange()
        return widget

    def add_action(self, widget):
        """오른쪽 묶음에 더함. 주 단추를 마지막에 더해 오른쪽 끝이 되게 함."""
        self.action_row.addWidget(widget)
        self.arrange()
        return widget

    def arrange(self):
        """도구와 행동 단추가 한 줄에 안 들어가면 도구를 윗줄로 옮김. 주 단추는 오른쪽 끝에 둠."""
        if not self.isVisible():
            self.setFixedHeight(self.least)
            return
        left, top, right, bottom = self.row.getContentsMargins()
        width = max(1, self.width() - left - right)
        tools = [item for item in self.tools.items if not item.isEmpty()]
        self.tool_box.setVisible(bool(tools))
        tool_width = sum(item.sizeHint().expandedTo(item.minimumSize()).width() for item in tools) + max(0, len(tools) - 1) * self.tools.spacing()
        action_width = self.action_row.natural_width()
        stacked = bool(tools) and tool_width + theme.GAP["group"] + action_width > width
        direction = QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight
        if self.row.direction() != direction:
            self.row.setDirection(direction)
        action_height = self.action_row.heightForWidth(min(width, action_width))
        self.actions.setFixedHeight(action_height)
        gap = self.row.spacing()
        tool_height = self.tools.heightForWidth(width if stacked else max(1, width - action_width - gap)) if tools else 0
        self.tool_box.setFixedHeight(tool_height)
        height = tool_height + gap + action_height if stacked else max(tool_height, action_height)
        self.setFixedHeight(max(self.least, top + height + bottom))

    def refont(self):
        self.arrange()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def showEvent(self, event):
        super().showEvent(event)
        self.arrange()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.arrange()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self.arrange()
        return result

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.LayoutRequest:
            self.arrange()
        return super().eventFilter(watched, event)


class NextCard(QFrame):
    """홈 화면 맨 위의 이어서 할 일 카드. caption, title 제목, body 설명 줄(여러 줄일 수 있음), 오른쪽 아래 주 단추 l(화면에 하나뿐인 주 단추).
    compact 면 caption 이 accent 꼬리표, 제목이 headline, 단추가 m 이고 오른쪽 가운데에 옴. 여백 24·16, 글 사이 4, 최소 높이 108,
    바탕은 emphasis_bg 한 색과 hero_edge 테두리(plain_next 속성을 주면 surface 바탕과 line 테두리).
    set_side 로 제목 오른쪽에 body secondary 옆 글을 둘 수 있음. 한 줄에 안 들어가면 옆 글이 제목 아래로 내려가고 빈 글이면 숨김."""

    def __init__(self, compact=False):
        super().__init__()
        self.setObjectName("card")
        self.setProperty("next_action", True)
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        if compact:
            self.setProperty("compact", True)
            self.setMinimumHeight(108)
            self.row.setContentsMargins(24, 16, 24, 16)
        else:
            self.row.setContentsMargins(24, 24, 24, 24)
        self.row.setSpacing(theme.GAP["group"])
        self.text_box = QWidget()
        column_box = box(self.text_box, spacing=theme.GAP["detail"])
        if compact:
            self.caption = badge("이어서 할 일", "accent")
        else:
            self.caption = label("이어서 할 일", "caption", "teal", bold=True)
        self.title = para("", "headline" if compact else "title")
        self.side = para("", "body", "secondary")
        self.line = para("", "body", "secondary")
        self.title_box = QWidget()
        self.title_row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.title_box)
        self.title_row.setContentsMargins(0, 0, 0, 0)
        self.title_row.setSpacing(theme.GAP["title_description"])
        self.title_row.addWidget(self.title, 0, Qt.AlignmentFlag.AlignVCenter)
        self.title_row.addWidget(self.side, 1, Qt.AlignmentFlag.AlignVCenter)
        column_box.addWidget(self.caption)
        self.head = heading(self.title_box, self.line)
        column_box.addWidget(self.head)
        if compact:  # 보통 글자에서 꼬리표 24·제목·설명 한 줄이 최소 높이 108 안에 들게 꼬리표-제목, 제목-설명 사이를 4 로 좁힘. 굵은 글자 줄 높이가 큰 글꼴 환경에서는 내용만큼 커짐
            column_box.setSpacing(theme.SPACE[0])
            self.head.layout().setSpacing(theme.SPACE[0])
        self.side.hide()
        self.row.addWidget(self.text_box, 1)
        self.button = button("", "primary", "m" if compact else "l")
        place = Qt.AlignmentFlag.AlignVCenter if compact else Qt.AlignmentFlag.AlignBottom
        self.row.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight | place)

    def set_item(self, title, line, action):
        """제목, 설명 줄(여러 줄일 수 있음), 단추 글자. action 이 비면 단추를 숨김."""
        self.title.setText(title)
        self.line.setText(line)
        self.line.setVisible(bool(line))
        self.button.setText(action)
        self.button.setVisible(bool(action))
        self.arrange()

    def set_side(self, text):
        """제목 오른쪽 옆 글. 빈 글이면 숨김."""
        self.side.setText(text)
        self.side.setVisible(bool(text))
        self.arrange()

    def arrange(self):
        """좁은 카드에서는 단추를 글 아래에 둬 제목과 설명의 폭을 확보함. 옆 글이 제목과 한 줄에 안 들어가면 제목 아래로 내림."""
        margins = self.row.contentsMargins()
        width = self.width() - margins.left() - margins.right()
        room = width - self.button.sizeHint().width() - self.row.spacing()
        minimum = 24 * theme.TYPE["body"][0] if self.line.isVisibleTo(self) else 12 * theme.TYPE["headline"][0]
        stacked = not self.button.isHidden() and room < minimum
        self.row.setDirection(QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight)
        text_room = width if stacked or self.button.isHidden() else room
        widths = [math.ceil(max(QFontMetricsF(part.font()).horizontalAdvance(line) for line in part.text().split("\n"))) + 2
                  for part in (self.title, self.side)]
        below = not self.side.isHidden() and sum(widths) + self.title_row.spacing() > text_room
        self.title_row.setDirection(QBoxLayout.Direction.TopToBottom if below else QBoxLayout.Direction.LeftToRight)
        self.title_row.setAlignment(self.side, Qt.AlignmentFlag.AlignLeft if below else Qt.AlignmentFlag.AlignVCenter)

    def refont(self):
        self.arrange()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()


class CheckMark(QWidget):
    """체크 상자 20(테두리 2px field_edge, 모서리 6). 켜면 accent 바탕과 흰 체크 표시. 상자는 칸의 왼쪽 끝에 붙여 그려서 위 본문과 같은
    세로선에 옴. 키보드 초점 테두리는 줄(Check)이 그림. QCheckBox 처럼 setChecked·isChecked·toggled·setEnabled 를 가짐."""
    toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.checked = False
        self.refont()

    def refont(self):
        self.setFixedSize(20, theme.TYPE["body"][1])  # 상자 20 을 본문 첫 줄의 가운데에 둠

    def isChecked(self):
        return self.checked

    def setChecked(self, checked):
        if self.checked != bool(checked):
            self.checked = bool(checked)
            self.update()
            self.toggled.emit(self.checked)

    def toggle(self):
        if self.isEnabled():
            self.setChecked(not self.checked)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = (self.height() - 20) // 2
        rect = QRectF(0, top, 20, 20)
        if not self.isEnabled():
            edge, fill = ("primary_off", "primary_off") if self.checked else ("border", "surface_alt")
        elif self.checked:
            edge, fill = "primary", "primary"
        else:
            edge, fill = "field_edge", "surface"
        painter.setPen(QPen(theme.qcolor(edge), 2))
        painter.setBrush(theme.qcolor(fill))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), theme.RADIUS["check"], theme.RADIUS["check"])
        if self.checked:
            painter.setPen(QPen(theme.qcolor("primary_ink" if self.isEnabled() else "primary_off_ink"), 2, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            path = QPainterPath(QPointF(5, top + 10))
            path.lineTo(8.5, top + 13.5)
            path.lineTo(15, top + 6.5)
            painter.drawPath(path)


class Check(QFrame):
    """체크 목록 한 줄: 상자(box) 20, 꼬리표(필수·보충, 없을 수 있음), 줄바꿈되는 글, 오른쪽 caption 메모. 줄 전체를 누르거나 Space 를
    치면 상자가 바뀜. 상자의 왼쪽 끝은 위 본문의 왼쪽 끝과 같은 선에 둠(바깥 여백 0). 상자를 끄면(box.setEnabled) 글은 그대로 읽힘."""

    def __init__(self, text, tag="", tag_tone="", note="", text_widget=None, mark_widget=None):
        super().__init__()
        self.setObjectName("row")
        self.down = False  # 최소 높이 48 은 상자 28 과 위아래 여백 12 가 만듦. 최소 높이를 따로 주면 줄바꿈한 글의 높이가 상자에 전해지지 않음
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        row = box(self, (0, 12, 0, 12), 12, horizontal=True)
        self.box = mark_widget or CheckMark()
        self.tag = badge(tag, tag_tone)
        self.label = text_widget or para(text)
        self.text_line = FirstLine(self.tag, self.label, spacing=8)
        self.content_line = FirstLine(self.box, self.text_line)
        self.note = label(note, "caption", "tertiary")
        self.line = FirstLine(self.note, self.content_line, trailing=True)
        row.addWidget(self.line, 1, Qt.AlignmentFlag.AlignTop)
        self.tag.setVisible(bool(tag))  # 부모에 붙인 뒤에 보임. Row 와 같은 까닭
        self.note.setVisible(bool(note))

    def mousePressEvent(self, event):
        self.down = event.button() == Qt.MouseButton.LeftButton
        event.accept()

    def mouseReleaseEvent(self, event):
        down, self.down = self.down, False
        if down and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.box.toggle()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            if not event.isAutoRepeat():
                self.box.toggle()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus():  # 키보드 초점은 목록 줄처럼 줄 안쪽 2px 테두리로 보임
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(theme.qcolor("focus"), 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), theme.RADIUS["small"], theme.RADIUS["small"])


class CheckList(QWidget):
    """Check 를 세로로 쌓는 칸. set_items 로 통째로 바꾸고 changed 는 표시가 바뀔 때마다 남."""
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.box = box(self)
        self.rows = []

    def set_items(self, items):
        """items 는 (글, 꼬리표, 꼬리표 색, 메모, 처음 표시) 목록."""
        for row in self.rows:
            self.box.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        for text, tag, tone, note, checked in items:
            row = Check(text, tag, tone, note)
            row.box.setChecked(bool(checked))
            row.box.toggled.connect(lambda _: self.changed.emit())
            self.box.addWidget(row)
            self.rows.append(row)
        self.setVisible(bool(self.rows))

    def marks(self):
        return [1 if row.box.isChecked() else 0 for row in self.rows]

    def set_enabled(self, enabled):
        for row in self.rows:
            row.box.setEnabled(enabled)
            row.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)


def visible_primary_buttons(widget):
    """widget 아래에서 보이는 주 단추들. 한 화면 상태에 하나 이하여야 함(tests 의 검사 C5)."""
    return [b for b in widget.findChildren(QPushButton) if b.objectName() == "primary" and b.isVisibleTo(widget) and b.isVisible()]

