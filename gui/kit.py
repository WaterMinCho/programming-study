# -*- coding: utf-8 -*-
"""새 디자인 시스템의 부품. 첫 화면과 웹 면접 준비 화면이 씀.

맨 위 위젯에 page() 로 ui="2" 속성을 주면 theme.STYLE_V2 의 색 규칙이 그 아래에만 걸림. 글자 크기와 굵기는 스타일시트가 아니라
theme.TYPE 으로 글꼴을 직접 주고(label, para), 간격은 theme.SPACE 의 값만 씀. 단추는 종류(kind)를 objectName 으로, 크기(scale)를
속성으로 받음. 목록 줄(Row)은 줄 전체가 눌림. 단계 표시(Stepper), 상태 점(Dot), 꺾쇠(Chevron)는 직접 그리는 위젯이고
칠할 때마다 지금 테마의 색을 읽음."""
import math

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QLayout, QProgressBar, QPushButton, QScrollArea,
                             QSizePolicy, QVBoxLayout, QWidget)

from gui import theme
from gui.widgets import LinkLabel, Para

FLUSH = 14  # 글자 단추의 안쪽 여백 12 과 테두리 2. 막대 가장자리의 글자 단추는 이만큼 바깥으로 내어 글자가 내용 선에 맞게 함
MARGIN = 32  # 창 좌우 여백
MARK = 20  # 목록 줄 앞 상태 점의 칸 폭
ROW_TEXT = 24 + MARK + 12  # 목록 줄의 글이 시작하는 자리(안쪽 여백, 점 칸, 점과 글 사이)
HOME_WIDTH = 960  # 홈 화면 내용 단의 최대 폭
DOT_STATES = {"progress": "primary", "review": "retry", "done": "ok", "todo": "faint", "ready": "ok"}  # 상태 점의 색 토큰


def page(widget):
    """화면이나 대화상자의 맨 위 위젯에 새 규칙을 걸음."""
    widget.setProperty("ui", "2")
    return widget


def repolish(widget):
    """속성을 바꾼 뒤 스타일시트를 다시 적용함."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_tone(widget, tone):
    """tone 속성을 바꾸고 다시 칠함. 띠의 앞 낱말처럼 부모의 tone 으로 색이 정해지는 자식도 같이 다시 칠함."""
    widget.setProperty("tone", tone or None)
    repolish(widget)
    for child in widget.findChildren(QWidget):
        repolish(child)


def label(text="", role="body", tone="", bold=None, align=None):
    """한 줄 글. role 은 theme.TYPE 의 이름, tone 은 secondary·tertiary·accent·success·warning·danger."""
    out = QLabel(text)
    out.setFont(theme.font(role, bold))
    if tone:
        out.setProperty("tone", tone)
    if align is not None:
        out.setAlignment(align)
    return out


def para(text="", role="body", tone="", bold=None):
    """여러 줄로 넘어가는 글. 줄 높이는 TYPE 의 px 값."""
    out = Para(text, line=theme.TYPE[role][1], font=theme.font(role, bold))
    if tone:
        out.setProperty("tone", tone)
    return out


def badge(text="", tone=""):
    """누를 수 없는 꼬리표. 높이 24, 글자 caption 700. tone 은 accent·success·warning·danger, 없으면 회색."""
    out = QLabel(text)
    out.setObjectName("badge")
    out.setFont(theme.font("caption", True))
    out.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if tone:
        out.setProperty("tone", tone)
    out.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return out


def button(text="", kind="secondary", scale="m", onbg=False):
    """단추. kind 는 primary·secondary·text·danger·danger_text·chip·tab 가운데 하나, scale 은 l(48)·m(40)·s(32). onbg 는 회색 바탕 위의 글자 단추(올리면 line 색)."""
    out = QPushButton(text)
    if kind != "secondary":
        out.setObjectName(kind)
    out.setProperty("scale", scale)
    if onbg:
        out.setProperty("onbg", True)
    out.setAutoDefault(False)
    out.setCursor(Qt.CursorShape.PointingHandCursor)
    out.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # 마우스로 누를 때는 초점 테두리를 그리지 않음
    return out


def chip(text, tid=None):
    out = button(text, "chip", "m")
    out.setCheckable(True)
    out.tid = tid
    return out


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
    """흰 카드(surface, 모서리 16, 테두리 없음)와 그 안의 세로 상자."""
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
    row.addWidget(head)
    row.addStretch(1)
    row.addWidget(note, 0, Qt.AlignmentFlag.AlignBottom)
    return row, head, note


def spaced(*items, spacing=4):
    """위젯들을 간격 spacing 으로 세로로 쌓은 묶음 위젯."""
    out = QWidget()
    inner = box(out, spacing=spacing)
    for item in items:
        inner.addWidget(item)
    return out


def banner(text="", tone="", lead=""):
    """안내·주의·오류·완료 띠. (띠, 글 Para). lead 가 없으면 tone 에 맞는 앞 낱말을 씀."""
    out = frame("banner")
    words = {"": "안내", "warning": "주의", "danger": "오류", "success": "완료"}
    if tone:
        out.setProperty("tone", tone)
    row = box(out, (16, 12, 16, 12), 8, horizontal=True)
    word = label(lead or words.get(tone, "안내"), "body", bold=True)
    word.setObjectName("lead")
    text_label = para(text)
    row.addWidget(word, 0, Qt.AlignmentFlag.AlignTop)
    row.addWidget(text_label, 1)
    out.text = text_label
    out.word = word
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
    num.setMinimumWidth(math.ceil(QFontMetricsF(num.font()).horizontalAdvance("88:88")))  # 자릿수가 바뀌어도 폭이 흔들리지 않음
    row.addWidget(cap, 0, Qt.AlignmentFlag.AlignBottom)
    row.addWidget(num, 0, Qt.AlignmentFlag.AlignBottom)
    return out, cap, num


class ElideLabel(QLabel):
    """폭이 모자라면 줄임표로 줄이는 한 줄 글. 전체 글은 도움말에 둠."""

    def __init__(self, text="", role="headline", tone="", bold=None):
        super().__init__()
        self.full = ""
        self.setFont(theme.font(role, bold))
        if tone:
            self.setProperty("tone", tone)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

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
    """상태 점. state 는 progress(채운 파랑)·review(채운 주황)·done(초록 원 안 체크)·todo(테두리 원)·ready(채운 초록), 또는 색 토큰 이름.
    size 는 지름(트랙 이름 앞은 8, 목록 줄은 10, 끝남 체크는 16)."""

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


class Chevron(QWidget):
    """목록 줄 오른쪽 끝의 꺾쇠."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(MARK, MARK)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(theme.qcolor("faint"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(QPointF(7, 5))
        path.lineTo(12, 10)
        path.lineTo(7, 15)
        painter.drawPath(path)


class Row(QFrame):
    """목록 줄. 왼쪽 상태 점(없을 수 있음), 제목과 둘째 줄, 오른쪽 caption 과 꺾쇠. 줄 전체를 한 번 누르면 clicked 가 남.
    한 줄이면 높이 56, 둘째 줄이 있으면 72. 올리면 hover 색, 누르면 surface_alt, 키보드 초점은 안쪽 2px 테두리."""
    clicked = pyqtSignal()

    def __init__(self, title, second="", end="", mark=None, data=None, strong=False, inert=False):
        super().__init__()
        self.setObjectName("row")
        self.data, self.inert, self.down = data, inert, False
        self.setMinimumHeight(theme.CONTROL["row2"] if second else theme.CONTROL["row"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 남는 자리를 줄이 나눠 갖지 않음
        row = box(self, (24, 0, 24, 0), 12, horizontal=True)
        self.mark = mark
        if mark is not None:
            row.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)
        text = QWidget()
        column_box = box(text, (0, 12, 0, 12), 0)
        self.title = ElideLabel(title, "label", bold=strong)  # 긴 제목은 줄임표로 줄이고 전체는 도움말에 둠
        self.second = ElideLabel(second, "caption", "secondary")
        self.title.setFixedHeight(theme.TYPE["label"][1])  # 글꼴의 줄 높이가 글자 크기와 같아 두 줄이 닿지 않게 줄 높이를 줌
        self.second.setFixedHeight(theme.TYPE["caption"][1])
        self.second.setVisible(bool(second))
        column_box.addWidget(self.title)
        column_box.addWidget(self.second)
        row.addWidget(text, 1, Qt.AlignmentFlag.AlignVCenter)
        self.end = label(end, "caption", "tertiary")
        self.end.setVisible(bool(end))
        row.addWidget(self.end, 0, Qt.AlignmentFlag.AlignVCenter)
        self.chevron = Chevron()
        self.chevron.setVisible(not inert)
        row.addWidget(self.chevron, 0, Qt.AlignmentFlag.AlignVCenter)
        if not inert:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_second(self, text):
        self.second.setText(text)
        self.second.setVisible(bool(text))
        self.setMinimumHeight(theme.CONTROL["row2"] if text else theme.CONTROL["row"])

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
    link = LinkLabel("", line=theme.TYPE["body"][1], font=theme.font("body"))
    out.layout().replaceWidget(out.text, link)
    out.text.hide()
    out.text.deleteLater()
    out.text = link
    return out, link


class RowList(QFrame):
    """줄을 세로로 쌓은 흰 목록. 줄 사이에만 line 색 1px 선(좌우 24 들여서). 준비 중 항목은 끝의 글자 단추 하나로 접음.
    flush 면 카드 안 이름표 아래에 두는 목록이라 줄과 선을 들이지 않고 이름표와 같은 세로선에 맞춤."""

    def __init__(self, inside_card=False, flush=False):
        super().__init__()
        self.setObjectName("rows" if inside_card or flush else "card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.flush = flush
        self.box = box(self)
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
        if self.rows:
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
    """가로로 늘어놓다가 폭이 모자라면 다음 줄로 넘기는 배치(주제 칩). 줄 사이와 칸 사이 간격은 spacing 하나로 씀."""

    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self.items = []
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

    def _place(self, rect, move):
        left, top, right, bottom = self.getContentsMargins()
        area = rect.adjusted(left, top, -right, -bottom)
        x, y, line = area.x(), area.y(), 0
        gap = self.spacing()
        for item in self.items:
            if item.widget() is not None and not item.widget().isVisibleTo(item.widget().parentWidget()):
                continue
            hint = item.sizeHint()
            if x > area.x() and x + hint.width() > area.right() + 1:
                x, y, line = area.x(), y + line + gap, 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + gap
            line = max(line, hint.height())
        return y + line - rect.y() + bottom


class Stepper(QWidget):
    """미션 단계 표시. steps 는 (번호, 이름, 상태) 목록이고 상태는 done·now·skip·lock. 원 28, 원 사이 2px 선, 끝난 구간은 link 색.
    이름표는 caption 14 이고 지금 단계만 굵게, 잠긴 단계는 번호만 보임(이름 없음). 높이 56 의 줄 안에서 그림."""

    CIRCLE, GAP, LABEL_MAX, CONN_MIN, CONN_MAX = 28, 8, 120, 16, 160

    def __init__(self):
        super().__init__()
        self.steps = []
        self.setFixedHeight(theme.CONTROL["stepper"] - 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_steps(self, steps):
        self.steps = list(steps)
        self.setToolTip("\n".join("%s %s" % (no, title or "잠김") for no, title, _ in self.steps))
        self.update()

    def _label_width(self, metrics, title, state):
        if state == "lock" or not title:
            return 0
        return min(self.LABEL_MAX, math.ceil(metrics.horizontalAdvance(title)))

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
        conn = max(self.CONN_MIN, min(self.CONN_MAX, room / conns)) if conns else 0
        x, middle = 0.0, self.height() / 2
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

    def __init__(self, names):
        super().__init__()
        outer = box(self)
        row = QHBoxLayout()
        row.setContentsMargins(24, 8, 24, 0)
        row.setSpacing(24)
        self.group = QButtonGroup(self)
        self.buttons = []
        for number, name in enumerate(names):
            tab = button(name, "tab")
            tab.setCheckable(True)
            tab.setFont(theme.font("label", True))
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


class TopBar(QFrame):
    """화면 위 막대(높이 64). plain 이면 홈처럼 바탕색이고 선이 없음, steps 이면 아래에 단계 표시가 이어져 선을 그쪽이 그림.
    왼쪽에 back 글자 단추(← 도착 화면 이름)와 제목, 오른쪽에 부른 쪽이 넣는 것. 가장자리의 글자 단추는 FLUSH 만큼 내어 글자를 내용 선에 맞춤."""

    def __init__(self, back_text="", title="", plain=False, steps=False):
        super().__init__()
        self.setObjectName("topbar")
        self.setFixedHeight(theme.CONTROL["topbar"])
        if plain:
            self.setProperty("plain", True)
        if steps:
            self.setProperty("steps", True)
        self.row = box(self, (MARGIN - FLUSH if back_text else MARGIN, 0, MARGIN, 0), 12, horizontal=True)
        self.back = None
        if back_text:
            self.back = button(back_text, "text", "m", onbg=plain)
            self.row.addWidget(self.back)
        self.title = ElideLabel(title, "headline")
        self.title.setVisible(bool(title))
        self.row.addWidget(self.title, 1)

    def add_right(self, widget, flush=False):
        """오른쪽 끝에 위젯을 더함. flush 면 글자 단추라 오른쪽 여백을 FLUSH 만큼 줄임."""
        if flush:
            left, top, _, bottom = self.row.getContentsMargins()
            self.row.setContentsMargins(left, top, MARGIN - FLUSH, bottom)
        self.row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return widget


class BottomBar(QFrame):
    """작업 화면 아래 막대(높이 80). 왼쪽 끝 파괴 글자 단추, 24 띄워 도구 글자 단추들, 오른쪽 끝 주 단추와 그 왼쪽 8 에 보조 단추."""

    def __init__(self):
        super().__init__()
        self.setObjectName("bottombar")
        self.setFixedHeight(theme.CONTROL["bottombar"])
        self.row = box(self, (MARGIN - FLUSH, 0, MARGIN, 0), 8, horizontal=True)
        self.tools = QHBoxLayout()
        self.tools.setContentsMargins(0, 0, 0, 0)
        self.tools.setSpacing(24)
        self.row.addLayout(self.tools)
        self.row.addStretch(1)

    def add_tool(self, widget):
        self.tools.addWidget(widget)
        return widget

    def add_action(self, widget):
        """오른쪽 묶음에 더함. 주 단추를 마지막에 더해 오른쪽 끝이 되게 함."""
        self.row.addWidget(widget)
        return widget


class NextCard(QFrame):
    """홈 화면 맨 위의 이어서 할 일 카드. caption, headline 제목, body 설명 한 줄, 오른쪽 아래 주 단추 l(화면에 하나뿐인 주 단추)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        row = box(self, (32, 32, 32, 32), 24, horizontal=True)
        text = QWidget()
        column_box = box(text, spacing=4)
        self.caption = label("이어서 할 일", "caption", "tertiary")
        self.title = para("", "headline")
        self.line = para("", "body", "secondary")
        column_box.addWidget(self.caption)
        column_box.addWidget(self.title)
        column_box.addWidget(self.line)
        row.addWidget(text, 1)
        self.button = button("", "primary", "l")
        row.addWidget(self.button, 0, Qt.AlignmentFlag.AlignBottom)

    def set_item(self, title, line, action):
        """제목, 설명 한 줄, 단추 글자. action 이 비면 단추를 숨김."""
        self.title.setText(title)
        self.line.setText(line)
        self.line.setVisible(bool(line))
        self.button.setText(action)
        self.button.setVisible(bool(action))


class CheckMark(QWidget):
    """체크 상자 20(테두리 2px field_edge, 모서리 6). 켜면 accent 바탕과 흰 체크 표시. 상자는 칸의 왼쪽 끝에 붙여 그려서 위 본문과 같은
    세로선에 옴. 키보드 초점 테두리는 줄(Check)이 그림. QCheckBox 처럼 setChecked·isChecked·toggled·setEnabled 를 가짐."""
    toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.checked = False
        self.setFixedSize(20, 28)  # 상자 20 을 본문 첫 줄(28)의 가운데에 둠

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
        rect = QRectF(0, 4, 20, 20)
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
            path = QPainterPath(QPointF(5, 14))
            path.lineTo(8.5, 17.5)
            path.lineTo(15, 10.5)
            painter.drawPath(path)


class Check(QFrame):
    """체크 목록 한 줄: 상자(box) 20, 꼬리표(필수·보충, 없을 수 있음), 줄바꿈되는 글, 오른쪽 caption 메모. 줄 전체를 누르거나 Space 를
    치면 상자가 바뀜. 상자의 왼쪽 끝은 위 본문의 왼쪽 끝과 같은 선에 둠(바깥 여백 0). 상자를 끄면(box.setEnabled) 글은 그대로 읽힘."""

    def __init__(self, text, tag="", tag_tone="", note=""):
        super().__init__()
        self.setObjectName("row")
        self.down = False  # 최소 높이 48 은 상자 28 과 위아래 여백 12 가 만듦. 최소 높이를 따로 주면 줄바꿈한 글의 높이가 상자에 전해지지 않음
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        row = box(self, (0, 12, 0, 12), 12, horizontal=True)
        self.box = CheckMark()
        row.addWidget(self.box, 0, Qt.AlignmentFlag.AlignTop)
        text_row = QHBoxLayout()
        text_row.setContentsMargins(0, 0, 0, 0)
        text_row.setSpacing(8)
        self.tag = badge(tag, tag_tone)
        self.tag.setVisible(bool(tag))
        self.label = para(text)
        text_row.addWidget(self.tag, 0, Qt.AlignmentFlag.AlignTop)
        text_row.addWidget(self.label, 1)
        row.addLayout(text_row, 1)
        self.note = label(note, "caption", "tertiary")
        self.note.setVisible(bool(note))
        row.addWidget(self.note, 0, Qt.AlignmentFlag.AlignTop)

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

