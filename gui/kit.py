# -*- coding: utf-8 -*-
"""새 디자인 시스템의 부품. 첫 화면과 웹 면접 준비 화면이 씀.

맨 위 위젯에 page() 로 ui="2" 속성을 주면 theme.STYLE_V2 의 색 규칙이 그 아래에만 걸림. 글자 크기와 굵기는 스타일시트가 아니라
theme.TYPE 으로 글꼴을 직접 주고(label, para), 그 역할을 role 속성에 적어 두어 글자 크기 단계가 바뀌면 refont 가 글꼴을 다시 줌.
간격은 theme.SPACE 의 값만 씀. 단추는 종류(kind)를 objectName 으로, 크기(scale)를
속성으로 받음. 목록 줄(Row)은 줄 전체가 눌림. 단계 표시(Stepper), 상태 점(Dot), 꺾쇠(Chevron), 칸 나누기 손잡이(SplitHandle)는
직접 그리는 위젯이고 칠할 때마다 지금 테마의 색을 읽음."""
import math

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QLayout, QProgressBar, QPushButton, QScrollArea,
                             QSizePolicy, QSplitter, QSplitterHandle, QVBoxLayout, QWidget)

from gui import theme
from gui.widgets import LinkLabel, Para

FLUSH = 14  # 글자 단추의 안쪽 여백 12 과 테두리 2. 막대 가장자리의 글자 단추는 이만큼 바깥으로 내어 글자가 내용 선에 맞게 함
MARGIN = 32  # 창 좌우 여백
MARK = 20  # 목록 줄 앞 상태 점의 칸 폭
ROW_TEXT = 24 + MARK + 12  # 목록 줄의 글이 시작하는 자리(안쪽 여백, 점 칸, 점과 글 사이)
HOME_WIDTH = 960  # 홈 화면 내용 단의 최대 폭
DOC_MIN = 640  # 1280 창까지의 읽는 글 단 폭. 17px 본문으로 약 54자(설계 문서의 실측)
DOC_CHARS = 54  # DOC_MIN 에 들어가는 17px 본문 글자 수
DOC_PX = theme.BASE_TYPE["body"][0]  # 그 글자 수를 잰 본문 크기(설계값 17)
LINE_CHARS = 64  # 한 줄에 두는 글자 수의 상한. 설계값 DOC_CHARS 의 1.2배이고 '가'로만 채우면 48자
GROW_FROM = 1280  # 이 창 폭부터 읽는 글의 단이 넓어짐
DOT_STATES = {"progress": "primary", "review": "retry", "done": "ok", "todo": "faint", "ready": "ok", "lock": "faint"}  # 상태 점의 색 토큰
PANE_MIN = 320  # 끄는 칸 나누기에서 가로로 놓인 칸 하나의 최소 폭
GRIP = (4, 32)  # 칸 나누기 손잡이 가운데 무늬의 짧은 변과 긴 변


def doc_max():
    """읽는 글 단 폭의 상한. 지금 본문 크기로 LINE_CHARS 자가 들어가는 폭: DOC_MIN / DOC_CHARS 가 17px 글자 하나의 폭이고
    본문이 커진 만큼 비례함. 17px 이면 759, 19px 이면 848, 21px 이면 937."""
    return round(DOC_MIN / DOC_CHARS * LINE_CHARS * theme.TYPE["body"][0] / DOC_PX)


def doc_width(window_width):
    """창 폭에 맞춘 읽는 글의 단 폭. 1280 창까지는 DOC_MIN 이고, 창이 그보다 넓어진 폭의 반만큼 넓어지되 doc_max 를 넘지 않음.
    2000 창이면 640 + 360 = 1000 에서 상한으로 자름(17px 본문 759, 19px 848)."""
    return max(DOC_MIN, min(doc_max(), DOC_MIN + (window_width - GROW_FROM) // 2))


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
    if widget.property("tone") == (tone or None):  # 시계처럼 1초마다 같은 값으로 부르는 곳이 있어 바뀔 때만 다시 칠함
        return
    widget.setProperty("tone", tone or None)
    repolish(widget)
    for child in widget.findChildren(QWidget):
        repolish(child)


def typed(widget, role, bold=None):
    """위젯에 theme.TYPE 의 role 글꼴을 주고 역할을 적어 둠(refont 가 다시 줄 때 읽음)."""
    widget.setFont(theme.font(role, bold))
    widget.setProperty("role", role)
    if bold is not None:
        widget.setProperty("bold", bool(bold))
    return widget


def refont(root):
    """글자 크기 단계가 바뀐 뒤 root 아래 모든 부품의 글꼴을 지금 TYPE 으로 다시 줌. 역할을 적어 둔 위젯은 글꼴(Para 는 줄 높이도)을,
    refont 메서드가 있는 부품(줄임표 글, 목록 줄, 체크 상자)은 제 크기를 다시 잡음. 시계 숫자처럼 measure 속성이 있는 글은 그 글자의 폭을 다시 잼."""
    for widget in [root] + root.findChildren(QWidget):
        role = widget.property("role")
        if role:
            widget.setFont(theme.font(role, widget.property("bold")))
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


def badge(text="", tone=""):
    """누를 수 없는 꼬리표. 높이 24, 글자 caption 700. tone 은 accent·success·warning·danger, 없으면 회색."""
    out = typed(QLabel(text), "caption", True)
    out.setObjectName("badge")
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


def chip(text, tid=None, onbg=False):
    """누르면 골라지는 칩(높이 40). onbg 는 회색 바탕 위에 두는 칩임. 평소에는 바탕 없이 글만 보이고 고르면 흰 알약이 됨."""
    out = button(text, "chip", "m", onbg)
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
    line.addWidget(word, 0, Qt.AlignmentFlag.AlignTop)
    line.addWidget(text_label, 1)
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
    """목록 줄. 왼쪽 상태 점(없을 수 있음), 제목과 둘째 줄, 오른쪽 caption 과 꺾쇠. 줄 전체를 한 번 누르면 clicked 가 남.
    한 줄이면 높이 56, 둘째 줄이 있으면 72. 올리면 hover 색, 누르면 surface_alt, 키보드 초점은 안쪽 2px 테두리.
    꺼지면 글이 faint 색이 되고 꺾쇠를 그리지 않음(theme.STYLE_V2, Chevron)."""
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
        self.setMinimumHeight(theme.CONTROL["row2"] if text else theme.CONTROL["row"])

    def refont(self):
        """글자 크기 단계가 바뀐 뒤 두 줄의 높이를 지금 줄 높이로."""
        self.title.setFixedHeight(theme.TYPE["label"][1])
        self.second.setFixedHeight(theme.TYPE["caption"][1])

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
        conn = max(self.CONN_MIN, min(self.CONN_MAX, room / conns)) if conns else 0
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
    """사람이 끄는 두 칸 나누기. orientation 은 Qt.Orientation, 손잡이 폭 handle 은 가로 나누기 24, 세로 나누기 16.
    ratio 는 첫 칸의 처음 몫(0~1)이고 끈 몫은 settings(QSettings)의 key 에 0~1 값으로 남음."""
    return Splitter(orientation, key, ratio, handle, settings)


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
        self.row.addWidget(self.title, 1)
        self.title.setVisible(bool(title))  # 부모에 붙인 뒤에 보임. Row 와 같은 까닭

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
        self.label = para(text)
        text_row.addWidget(self.tag, 0, Qt.AlignmentFlag.AlignTop)
        text_row.addWidget(self.label, 1)
        row.addLayout(text_row, 1)
        self.note = label(note, "caption", "tertiary")
        row.addWidget(self.note, 0, Qt.AlignmentFlag.AlignTop)
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

