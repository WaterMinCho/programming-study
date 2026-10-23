# -*- coding: utf-8 -*-
"""알고리즘 여행의 던전 지도. 첫 화면·웹 홈과 같은 홈 틀임: 위 막대(← 처음 화면, 풀이 언어 칩, 캐시 비우기), 제목과 한 줄 설명,
주의 띠(Node.js 없음, 읽지 못한 던전), 이어서 할 일 카드(화면에 하나뿐인 주 단추), 그 아래 5:7 두 구역(왼쪽 던전 지도 카드,
오른쪽 고른 던전의 목록 카드). 960 폭의 가운데 단에 두고 창이 작으면 스크롤함.

던전은 모두 열려 있고 지도는 권장 순서만 보여 줌. 보스 줄은 그 던전의 중급 문제를 모두 통과하기 전에는 눌리지 않음.
"보스에서 익힌 기술" 은 보스를 통과했거나 보스 해설을 연 뒤에만 서비스가 내용을 줌. 화면 낱말은 gui/journey_text.py 가 만듦."""
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QToolTip, QWidget

from gui import kit, theme
from gui.docview import Doc
from gui.journey_page import LangChips, ask_node, node_ready, saved_lang, with_node
from gui.journey_text import (bank_text, dungeon_count, dungeon_lines, item_line, map_count, next_item, node_tip, place, row_line, tier_tip)
from journey.node import MIN_MAJOR

COLUMNS = 4  # 한 줄의 던전 수. 줄마다 방향을 바꾸는 뱀 모양 길
CIRCLE = 40  # 던전 원의 지름
HIT = 48  # 원을 누르는 범위의 지름
RING = 6  # 원 끝에서 고름 고리까지
EDGE = 52  # 바깥 열 원 가운데와 지도 끝 사이
TOP = 28  # 지도 위 끝에서 첫 줄 원 가운데까지
NAME_GAP = 8  # 원 아래 끝과 이름 알약 사이
BELOW = 26  # 이름 알약 아래 끝과 다음 줄 원 위 끝 사이
BOTTOM = 4  # 마지막 줄 이름 알약 아래의 여백
NAME_MAX = 86  # 보통 글자에서 이름 글 폭의 상한. 글자가 커지면 caption 크기에 비례함
INSET = 24  # 바깥 열 이름 글이 지도 끝에서 떨어지는 거리(카드 안쪽 여백과 같음)
PILL_PAD = 4  # 이름 글 양옆의 알약 여백
PILL_GAP = 4  # 이웃 이름 알약 사이의 최소 간격. 알약은 카드와 같은 색이라 글 사이로는 12 가 보임
MARK = 16  # 범례 표시의 지름
WIDTH_HINT = 390  # 1280 창의 지도 카드 폭. 실제 폭은 카드 폭을 따름
LEGEND_ITEMS = (("cleared", "클리어"), ("progress", "진행 중"), ("todo", "시작 전"), ("waiting", "준비 중"))
ARROWS = {Qt.Key.Key_Left: (0, -1), Qt.Key.Key_Right: (0, 1), Qt.Key.Key_Up: (-1, 0), Qt.Key.Key_Down: (1, 0)}  # 화면의 이웃: (줄, 칸)

ABOUT = "코딩 테스트 유형을 던전 %d개로 나눠 차례로 풀고, 던전마다 보스 문제로 마무리합니다."
NODE_TEXT = "JavaScript 로 풀려면 Node.js %d 이상이 필요합니다. 지금은 Python 으로 풉니다." % MIN_MAJOR
ALL_CLEAR = "준비된 던전을 모두 클리어했습니다. 새 던전이 나오면 첫 화면의 [새 문제 받기]로 받으세요."
NO_DUNGEON = "아직 준비된 던전이 없습니다. 첫 화면의 [새 문제 받기]로 받으세요."
WAITING = "준비 중인 던전입니다. 새 던전이 나오면 첫 화면의 [새 문제 받기]로 받으세요."
BROKEN = "이 던전을 열 수 없습니다. 위 주의 띠를 확인하세요."
CACHE_TIP = "채점에 쓰는 큰 테스트 입력을 이 컴퓨터에 보관해 둡니다."
CLEAR_TEXT = "채점할 때 만든 테스트 입력 %s를 지웁니다. 다음 채점 때 다시 만들어서 그 채점만 조금 느려집니다."
CACHE_SHOWN = 1024 * 1024  # 캐시가 이만큼 쌓여야 [캐시 비우기]가 보임


def size_text(size):
    """캐시 크기를 MB 단위 정수로. 단추는 1MB 부터 보이므로 그보다 작은 값은 쓰지 않음."""
    return "%dMB" % round(size / CACHE_SHOWN)


def pill_height():
    """이름 알약의 높이. 지금 글자 단계의 caption 줄 높이(보통 22, 크게 24, 더 크게 28)."""
    return theme.TYPE["caption"][1]


def line_gap():
    """지도 줄 사이(원 가운데끼리). 원 아래 반지름, 이름 알약과 그 위아래 간격, 다음 원 위 반지름을 더해 보통 96."""
    return CIRCLE // 2 + NAME_GAP + pill_height() + BELOW + CIRCLE // 2


def map_height(lines):
    """줄 lines 개인 지도의 높이. 보통 글자에서 4줄이면 28 + 96 × 3 + 20 + 8 + 22 + 4 = 370."""
    return TOP + (lines - 1) * line_gap() + CIRCLE // 2 + NAME_GAP + pill_height() + BOTTOM


def name_room(step):
    """이름 글 폭의 상한. 칸 간격 step 에서 8 을 뺀 값과 NAME_MAX(caption 크기에 비례) 가운데 작은 쪽."""
    return min(NAME_MAX * theme.TYPE["caption"][0] / theme.BASE_TYPE["caption"][0], step - 8)


def paint_node(painter, rect, state, number=None, font=None):
    """던전 원 하나를 rect 에 그림. state 는 cleared(ok 채움)·progress(primary 채움)·todo(surface 와 2px faint 테두리)·
    waiting(surface 와 2px faint 점선). number 가 있으면 가운데에 font 로 씀. 지도와 범례가 같이 부름."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if state in ("cleared", "progress"):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor("ok" if state == "cleared" else "primary"))
        painter.drawEllipse(rect)
    else:
        pen = QPen(theme.qcolor("faint"), 2)
        if state == "waiting":
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setDashPattern([1.0, 1.0])  # 선 굵기 단위라 2px 선, 2px 틈
        painter.setPen(pen)
        painter.setBrush(theme.qcolor("surface"))
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))  # 2px 선의 바깥 끝이 rect 에 오게
    if number is not None:
        ink = {"cleared": "surface", "progress": "primary_ink", "waiting": "faint"}.get(state, "ink")
        painter.setPen(theme.qcolor(ink))
        painter.setFont(font or theme.font("caption", True))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(number))
    painter.restore()


class MapView(QWidget):
    """던전 16개를 4개씩 4줄 뱀 모양 길로 그린 지도. 원 가운데 x = 52 + 칸 × (폭 − 104) / 3, y = 28 + 줄 × 줄 사이.
    원 아래에는 surface 알약 위에 이름을 써서 꺾이는 세로 길이 지나가도 읽힘. 고른 던전은 원 밖 6 에 2px 고리이고 글자색임.
    키보드로 초점이 왔을 때만 focus 색이라 마우스로 누른 뒤에는 진행 중(파랑 채움) 던전에서 고리가 원에 묻히지 않음.
    누르거나 화살표로 고르면 picked(던전 id), Enter·Space 는 entered(던전 id) 를 냄. 화살표는 화면의 이웃(같은 줄의 왼쪽·오른쪽,
    위·아래 줄의 같은 칸)으로 움직임. 높이는 글자 단계의 caption 줄 높이로 정하고(refont) 늘어나지 않음. 색과 글꼴은 칠할 때마다 읽음."""
    picked = pyqtSignal(str)
    entered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows, self.selected, self.over = [], None, None
        self.keyed = False  # 초점이 키보드(Tab, 화살표)로 왔는지. 마우스로 누른 초점이면 거짓
        self.placed = (None, [])  # 이름 자리를 정한 조건(폭, caption 단계, 이름들)과 그 결과(labels)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("던전 지도")
        self.setMouseTracking(True)  # 원과 이름 위에서만 손 모양 커서
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.refont()

    def lines(self):
        return math.ceil(len(self.rows) / COLUMNS) or COLUMNS

    def refont(self):
        """글자 크기 단계가 바뀐 뒤 높이를 지금 caption 줄 높이로 다시 잡음."""
        self.setFixedHeight(map_height(self.lines()))
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(WIDTH_HINT, map_height(self.lines()))

    def set_rows(self, rows, selected):
        self.rows = list(rows)
        self.set_selected(selected)
        self.refont()

    def set_selected(self, did):
        """고른 던전을 바꾸고 화면 읽기 프로그램이 읽을 설명을 그 던전의 도움말로 둠."""
        self.selected = did
        row = next((row for row in self.rows if row["id"] == did), None)
        self.setAccessibleDescription(node_tip(row) if row else "")
        self.update()

    @staticmethod
    def state(row):
        """overview 줄의 지도 상태. 준비 중이거나 읽지 못한 던전은 waiting, 보스를 통과하면 cleared, 한 문제라도 통과하면 progress."""
        if not row["ready"]:
            return "waiting"
        if row["cleared"]:
            return "cleared"
        return "progress" if row["passed"] else "todo"

    def step(self):
        return (self.width() - 2 * EDGE) / (COLUMNS - 1)

    @staticmethod
    def spot(index):
        """던전 순서 index 의 화면 자리 (줄, 칸). 홀수 줄은 오른쪽에서 왼쪽으로 감."""
        line, column = divmod(index, COLUMNS)
        return line, COLUMNS - 1 - column if line % 2 else column

    def centers(self):
        """던전 순서대로 원의 가운데."""
        step, gap = self.step(), line_gap()
        return [QPointF(EDGE + column * step, TOP + line * gap) for line, column in (self.spot(n) for n in range(len(self.rows)))]

    def nodes(self):
        """[(던전 id, 원의 사각형)]."""
        half = CIRCLE / 2
        return [(row["id"], QRectF(center.x() - half, center.y() - half, CIRCLE, CIRCLE)) for row, center in zip(self.rows, self.centers())]

    def labels(self):
        """[(던전 id, 알약 사각형, 글 사각형, 줄인 이름)]. 이름은 원 아래 8 에 두고 줄마다 fit_line 으로 자리를 정함.
        폭·글자 단계·이름이 그대로면 앞에서 정한 자리를 다시 씀(칠할 때마다 부름)."""
        key = (self.width(), theme.TYPE["caption"], tuple(row["title"] for row in self.rows))
        if self.placed[0] != key:
            self.placed = (key, self.place_labels())
        return self.placed[1]

    def place_labels(self):
        metrics = QFontMetricsF(theme.font("caption"))
        room, height, centers = name_room(self.step()), pill_height(), self.centers()
        widths = [min(room, math.ceil(metrics.horizontalAdvance(row["title"]))) for row in self.rows]
        lefts = [0.0] * len(self.rows)
        for line in range(self.lines()):
            members = sorted((n for n in range(len(self.rows)) if self.spot(n)[0] == line), key=lambda n: self.spot(n)[1])
            if members:
                self.fit_line(members, [centers[n].x() for n in members], widths, lefts)
        out = []
        for number, (row, center) in enumerate(zip(self.rows, centers)):
            name = metrics.elidedText(row["title"], Qt.TextElideMode.ElideRight, widths[number])
            if name != row["title"] and name.endswith("…"):  # 낱말 사이에서 자르면 줄임표 앞에 띄어쓰기가 남음
                name = name[:-1].rstrip() + "…"
            width = math.ceil(metrics.horizontalAdvance(name))
            text = QRectF(lefts[number] + (widths[number] - width) / 2, center.y() + CIRCLE / 2 + NAME_GAP, width, height)
            out.append((row["id"], text.adjusted(-PILL_PAD, 0, PILL_PAD, 0), text, name))
        return out

    def fit_line(self, members, middles, widths, lefts):
        """한 줄(왼쪽부터 members)의 이름 글 자리를 lefts 에 적음. 이름은 원 가운데 아래에 두되 글 끝이 [24, 폭 − 24] 안에 오게
        바깥 열 이름을 안쪽으로 밂. 이웃 알약 사이를 PILL_GAP 이상 띄우려고 겹치는 이름을 옆으로 밀고, 한 줄에 다 들어가지 않으면
        가장 긴 이름부터 줄임표로 줄임. widths 는 이름 글 폭이고 줄인 만큼 바뀜."""
        low, high = INSET, self.width() - INSET
        space = 2 * PILL_PAD + PILL_GAP
        while sum(widths[n] for n in members) + space * (len(members) - 1) > high - low:
            widest = max(members, key=lambda n: widths[n])
            if widths[widest] <= 0:  # 자리를 잡기 전처럼 지도 폭이 거의 없을 때
                break
            widths[widest] -= 1
        for number, middle in zip(members, middles):
            lefts[number] = min(max(middle - widths[number] / 2, low), high - widths[number])
        for one, other in zip(members, members[1:]):  # 왼쪽 이름에 닿으면 오른쪽으로 밂
            lefts[other] = max(lefts[other], lefts[one] + widths[one] + space)
        last = members[-1]
        lefts[last] = min(lefts[last], high - widths[last])
        for one, other in reversed(list(zip(members, members[1:]))):  # 오른쪽 끝을 넘었으면 왼쪽으로 되밂
            lefts[one] = min(lefts[one], lefts[other] - space - widths[one])

    def at(self, point):
        """point 가 든 던전 id. 원(지름 48)과 그 던전의 이름 알약을 받음. 없으면 None."""
        for row, center in zip(self.rows, self.centers()):
            if math.hypot(point.x() - center.x(), point.y() - center.y()) <= HIT / 2:
                return row["id"]
        return next((did for did, pill, _, _ in self.labels() if pill.contains(point)), None)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        points = self.centers()
        for row, start, end in zip(self.rows, points, points[1:]):  # 클리어한 던전에서 다음 던전으로 가는 구간은 link 색
            painter.setPen(QPen(theme.qcolor("link" if row["cleared"] else "line"), 2))
            painter.drawLine(start, end)
        number_font = theme.font("caption", True)
        for (did, circle), row in zip(self.nodes(), self.rows):
            if did == self.selected:
                painter.setPen(QPen(theme.qcolor("focus" if self.hasFocus() and self.keyed else "ink"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(circle.adjusted(-RING + 1, -RING + 1, RING - 1, RING - 1))  # 2px 선의 가운데가 반지름 25 에 와서 바깥 끝이 26
            paint_node(painter, circle, self.state(row), row["no"], number_font)
        painter.setFont(theme.font("caption"))
        radius = pill_height() / 2
        for _, pill, text, name in self.labels():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("surface"))
            painter.drawRoundedRect(pill, radius, radius)
            painter.setPen(theme.qcolor("muted"))
            painter.drawText(text, Qt.AlignmentFlag.AlignCenter, name)
        painter.end()

    def mousePressEvent(self, event):
        if self.keyed:
            self.keyed = False
            self.update()
        did = self.at(event.position())
        if did and did != self.selected and event.button() == Qt.MouseButton.LeftButton:  # 고른 던전을 다시 누르면 목록을 다시 그리지 않음
            self.picked.emit(did)

    def mouseMoveEvent(self, event):
        over = self.at(event.position())
        if over != self.over:
            self.over = over
            self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.over = None
        self.unsetCursor()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        ids = [row["id"] for row in self.rows]
        if not ids:
            super().keyPressEvent(event)
            return
        if (key in ARROWS or key in (Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)) and not self.keyed:
            self.keyed = True
            self.update()
        index = ids.index(self.selected) if self.selected in ids else 0
        target = None
        if key in ARROWS:
            line, column = self.spot(index)
            down, right = ARROWS[key]
            spots = {self.spot(n): n for n in range(len(ids))}
            target = spots.get((line + down, column + right))
        elif key == Qt.Key.Key_Home:
            target = 0
        elif key == Qt.Key.Key_End:
            target = len(ids) - 1
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not event.isAutoRepeat() and self.selected in ids:
                self.entered.emit(self.selected)
            return
        else:
            super().keyPressEvent(event)
            return
        if target is not None and ids[target] != self.selected:
            self.picked.emit(ids[target])

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.keyed = event.reason() != Qt.FocusReason.MouseFocusReason
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            did = self.at(QPointF(event.pos()))
            row = next((row for row in self.rows if row["id"] == did), None)
            if row:
                QToolTip.showText(event.globalPos(), node_tip(row), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)


class Mark(QWidget):
    """범례의 표시 하나. 지도의 원을 번호 없이 16 크기로 그림."""

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setFixedSize(MARK, MARK)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_node(painter, QRectF(0, 0, MARK, MARK), self.state)
        painter.end()


class Legend(QWidget):
    """지도 아래 범례. 표시 16 과 8 띄운 caption 이름 넷을 사이 16 으로 늘어놓고, 폭이 모자라면 다음 줄로 넘김."""

    def __init__(self):
        super().__init__()
        flow = kit.FlowLayout(self, 16)
        flow.setContentsMargins(24, 0, 24, 0)
        self.items = []
        for state, name in LEGEND_ITEMS:
            item = QWidget()
            row = kit.box(item, spacing=8, horizontal=True)
            row.addWidget(Mark(state), 0, Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(kit.label(name, "caption", "secondary"), 0, Qt.AlignmentFlag.AlignVCenter)
            flow.addWidget(item)
            self.items.append(item)


class JourneyMapPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.did, self.info, self.overview, self.target, self.busy = None, None, None, None, False
        self.cache_size = 0  # show_cache 가 읽어 둔 캐시 크기(바이트). 확인 창 본문에 씀
        outer = kit.box(self)

        self.top = kit.TopBar("← 처음 화면", plain=True)
        self.home_btn = self.top.back
        self.top.row.addStretch(1)  # 제목이 없는 막대라 돌아가기는 왼쪽 끝, 나머지는 오른쪽 끝에 붙임
        self.busy_label = kit.ElideLabel("", "caption", "secondary")  # Node.js 찾는 중처럼 도는 일의 이름. 막대가 좁으면 줄임표로 줄임
        self.busy_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.busy_label.setMinimumWidth(1)
        self.busy_bar = kit.progress(thin=True)
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setFixedWidth(120)
        for widget in (self.busy_label, self.busy_bar):
            widget.hide()
            self.top.add_right(widget)
        self.lang_bar = LangChips(onbg=True)
        self.lang_btns = self.lang_bar.buttons
        self.top.add_right(self.lang_bar)
        self.clear_cache_btn = kit.button("캐시 비우기", "text", "s", onbg=True)
        self.clear_cache_btn.setToolTip(CACHE_TIP)
        self.top.add_right(self.clear_cache_btn, flush=True)
        outer.addWidget(self.top)

        inner = QWidget()
        root = kit.box(inner, (0, 24, 0, 48))
        root.addWidget(kit.label("알고리즘 여행", "title"))
        root.addSpacing(4)
        self.about = kit.para(ABOUT % 16, "body", "secondary")
        root.addWidget(self.about)
        root.addSpacing(16)
        self.node_banner = kit.banner(NODE_TEXT, "warning", action="Node 찾기")
        self.bank_banner = kit.banner("", "warning")  # 읽지 못한 던전. 서비스가 남긴 원문은 도움말에만
        banners = QWidget()  # 띠 둘이 같이 보이면 8 띄움. 숨은 띠 옆에는 간격이 생기지 않음
        banner_box = kit.box(banners, spacing=8)
        for banner in (self.node_banner, self.bank_banner):
            banner.hide()
            banner_box.addWidget(banner)
        root.addWidget(banners)
        root.addSpacing(16)
        self.next_card = kit.NextCard()
        self.next_btn = self.next_card.button
        self.next_note = kit.para("", "body", "secondary")  # 이어서 할 일이 없을 때 카드 대신 보이는 한 줄
        self.next_note.hide()
        root.addWidget(self.next_card)
        root.addWidget(self.next_note)
        root.addSpacing(48)

        cols = QHBoxLayout()
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(24)
        left = QWidget()
        left_box = kit.box(left)
        head, _, self.passed = kit.section("던전 지도")
        left_box.addLayout(head)
        left_box.addSpacing(12)
        self.map_card, map_box = kit.card(pad=0)
        map_box.setContentsMargins(0, 24, 0, 24)
        self.view = MapView()
        self.legend = Legend()
        map_box.addWidget(self.view)
        map_box.addWidget(self.legend)
        left_box.addWidget(self.map_card)
        left_box.addStretch(1)

        right = QWidget()
        right_box = kit.box(right)
        head, self.title, self.count = kit.section("")
        right_box.addLayout(head)
        right_box.addSpacing(12)
        self.card, card_box = kit.card(0, 0)
        lines = QWidget()
        lines_box = kit.box(lines, (24, 24, 24, 8), 4)
        self.meta = kit.para("", "caption", "secondary")  # 주제와 보스 난이도. 도움말은 난이도를 풀어 씀
        self.meta_more = kit.para("", "caption", "secondary")  # 권장 선행 던전(있을 때만)
        lines_box.addWidget(self.meta)
        lines_box.addWidget(self.meta_more)
        self.note = kit.para("", "body", "secondary")  # 준비 중이거나 읽지 못한 던전의 안내
        self.note_box = QWidget()
        kit.box(self.note_box, (24, 8, 24, 24)).addWidget(self.note)
        self.rows = kit.RowList(inside_card=True)
        self.rule = kit.frame("rowline")
        self.rule.setFixedHeight(1)
        self.intro = Doc()
        self.skills = kit.para()
        self.boss_new = kit.para()
        self.intro_box = kit.spaced(kit.label("던전 소개", "caption", "tertiary"), self.intro, spacing=8)
        self.skills_box = kit.spaced(kit.label("익히는 기술", "caption", "tertiary"), self.skills)
        self.boss_box = kit.spaced(kit.label("보스에서 익힌 기술", "caption", "tertiary"), self.boss_new)
        self.about_box = QWidget()
        about_box = kit.box(self.about_box, (24, 24, 24, 24), 24)  # 묶음 사이 24 는 소개 글의 문단 사이(16)보다 넓게 둠
        for widget in (self.intro_box, self.skills_box, self.boss_box):
            about_box.addWidget(widget)
        for widget in (lines, self.note_box, self.rows, self.rule, self.about_box):
            card_box.addWidget(widget)
        right_box.addWidget(self.card)
        right_box.addStretch(1)
        cols.addWidget(left, 5)
        cols.addWidget(right, 7)
        root.addLayout(cols)
        root.addStretch(1)
        column = kit.column(inner)
        column.setContentsMargins(kit.MARGIN, 0, kit.MARGIN, 0)
        self.scroll = kit.scroll(column)
        outer.addWidget(self.scroll, 1)

        self.home_btn.clicked.connect(lambda: self.win.go_hub())
        self.view.picked.connect(self.show_dungeon)
        self.view.entered.connect(self.focus_rows)
        self.lang_bar.picked.connect(self.pick_lang)
        self.node_banner.action.clicked.connect(lambda: ask_node(self.win, lambda: self.pick_lang("javascript")))
        self.clear_cache_btn.clicked.connect(self.ask_clear_cache)
        self.next_btn.clicked.connect(self.open_next)

    # 불러오기

    def refresh(self, select=None):
        """서비스에서 수치를 다시 읽어 모든 칸을 다시 채움. 고르는 던전은 select(문제 화면에서 돌아올 때 그 문제의 던전),
        이어서 할 일의 던전, 첫 준비된 던전 순이라 첫 화면이 말한 던전이 열림. 이어서 할 일은 첫 화면과 같은 journey_text.next_item 이
        고름. 이어서 할 일이 없으면(모두 클리어) 마지막으로 고른 던전에 머묾."""
        overview = self.overview = self.win.journey.overview()
        rows = overview["dungeons"]
        ids = [row["id"] for row in rows]
        self.target = next_item(self.win.journey, self.win.settings.value("journey/last", "", type=str), overview)
        here = self.did if self.target is None else None
        did = next((d for d in (select, (self.target or {}).get("did"), here) if d in ids), None)
        if did is None:
            did = next((row["id"] for row in rows if row["ready"]), ids[0] if ids else None)
        self.about.setText(ABOUT % len(rows))
        self.passed.setText(map_count(overview))
        text, tip = bank_text(overview)
        self.bank_banner.text.setText(text)
        self.bank_banner.setToolTip(tip)
        self.bank_banner.setVisible(bool(text))
        self.lang_bar.set_lang(self.usable_lang())
        self.show_next(overview)
        self.show_cache(self.win.journey.cache_info())
        self.view.set_rows(rows, did)
        if did is not None:
            self.show_dungeon(did)

    def usable_lang(self):
        """설정의 언어. JavaScript 인데 node 가 없으면 Python 으로 풀고 Node.js 띠를 보임. 그 밖에는 띠를 숨김.
        node 는 JavaScript 를 고른 적이 있을 때만 창이 이 화면을 열기 전에 워커에서 찾아 두므로, 여기서는 기억한 결과만 읽음."""
        lang = saved_lang(self.win.settings)
        missing = lang == "javascript" and not node_ready(self.win)
        self.node_banner.setVisible(missing)
        return "python" if missing else lang

    def show_next(self, overview):
        """이어서 할 일 카드. 할 일이 없으면 카드 대신 한 줄(모두 클리어했거나 준비된 던전이 없음)."""
        target = self.target
        self.next_card.setVisible(target is not None)
        self.next_note.setVisible(target is None)
        if target is None:
            self.next_note.setText(ALL_CLEAR if overview["ready"] else NO_DUNGEON)
            return
        self.next_card.set_item(target["title"], item_line(target), target["action"])

    def show_cache(self, info):
        """[캐시 비우기]는 캐시가 1MB 이상일 때만 보임. 숨으면 칩이 막대 끝이라 오른쪽 여백을 글자 단추 몫만큼 되돌림."""
        shown = info["bytes"] >= CACHE_SHOWN
        self.cache_size = info["bytes"]
        self.clear_cache_btn.setVisible(shown)
        left, top, _, bottom = self.top.row.getContentsMargins()
        self.top.row.setContentsMargins(left, top, kit.MARGIN - kit.FLUSH if shown else kit.MARGIN, bottom)

    def show_dungeon(self, did):
        """오른쪽 구역에 던전 did 의 보조 줄, 문제 목록, 소개를 보여 줌."""
        self.did = did
        self.view.set_selected(did)
        info = self.info = self.win.journey.dungeon(did)
        numbers = {row["id"]: row["no"] for row in (self.overview or {"dungeons": []})["dungeons"]}
        self.title.setText(place(info))
        self.count.setText(dungeon_count(info))
        lines = dungeon_lines(info, numbers)
        self.meta.setText(lines[0])
        self.meta.setToolTip(tier_tip(info["boss_target"], boss=True))
        self.meta_more.setText(lines[1] if len(lines) > 1 else "")
        self.meta_more.setVisible(len(lines) > 1)
        ready = info["ready"]
        self.note.setText("" if ready else (BROKEN if info["error"] else WAITING))
        self.note_box.setVisible(not ready)
        for widget in (self.rows, self.rule, self.about_box):
            widget.setVisible(ready)
        self.rows.clear()
        if not ready:
            self.intro.clear()
            return
        self.fill_list()
        self.intro.set_markdown(info["intro"], info["base_dir"], self.lang_bar.lang)
        self.intro_box.setVisible(bool(self.intro.pieces))
        self.skills.setText(", ".join(info["skills"]))
        self.skills_box.setVisible(bool(info["skills"]))
        self.boss_new.setText(info["boss_new"] or "")
        self.boss_box.setVisible(bool(info["boss_new"]))

    def fill_list(self):
        """문제 목록 줄. 앞 점은 통과 done, 시도함 progress, 안 함 todo, 잠긴 보스 lock 이고 끝 caption 은 역할. 미리 고른 줄은 없음."""
        info = self.info
        for row in info["problems"]:
            if row["locked"]:
                state = "lock"
            elif row["passed"]:
                state = "done"
            else:
                state = "progress" if row["tried"] else "todo"
            dot = kit.Dot(state)
            if row["locked"]:
                dot.setToolTip("잠김")
            line = kit.Row(row["title"], row_line(row, info), row["role_label"], dot, row["id"], strong=row["role"] == "boss",
                           inert=row["locked"])
            if row["locked"]:  # 숨긴 꺾쇠 자리를 남겨 끝 caption "보스" 가 다른 줄의 역할과 같은 열에 옴
                policy = line.chevron.sizePolicy()
                policy.setRetainSizeWhenHidden(True)
                line.chevron.setSizePolicy(policy)
            line.clicked.connect(lambda pid=row["id"]: self.open_problem(pid))
            line.setEnabled(not self.busy)
            self.rows.add(line)

    def focus_rows(self, did):
        """지도에서 Enter·Space 를 누르면 그 던전의 첫 열 수 있는 줄로 초점을 옮김."""
        first = next((row for row in self.rows.rows if not row.inert), None) if did == self.did and self.rows.isVisible() else None
        if first is not None:
            first.setFocus(Qt.FocusReason.TabFocusReason)
            self.scroll.ensureWidgetVisible(first)

    def open_problem(self, pid):
        if not self.busy and self.did is not None:
            self.win.open_problem(self.did, pid)

    def open_next(self):
        if self.target is not None and not self.busy:
            self.win.open_problem(self.target["did"], self.target["pid"])

    def showEvent(self, event):
        """화면을 보일 때 초점은 화면 자체에 둠. 첫 TabFocus 단추(← 처음 화면)가 초점 테두리를 단 채 열리지 않게 함.
        내려 둔 창을 다시 띄울 때(운영체제가 보내는 보이기)는 고르던 자리를 지킴."""
        super().showEvent(event)
        if not event.spontaneous():
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    # 언어 · 캐시

    def pick_lang(self, lang, node_ok=None):
        """문제 화면과 같은 설정을 바꿈. JavaScript 인데 node 가 없으면 칩을 Python 으로 되돌리고 Node.js 띠와 대화상자를 띄움.
        node_ok 는 with_node 가 알아낸 결과이고, 없으면 with_node 를 거쳐 다시 부름."""
        if lang == "javascript" and node_ok is None:
            with_node(self.win, lambda ok: self.pick_lang(lang, ok))
            return
        if lang == "javascript" and not node_ok:
            self.lang_bar.set_lang(self.lang_bar.lang)  # 누르는 순간 옮겨 간 체크를 지금 언어로 되돌림
            self.node_banner.show()
            ask_node(self.win, lambda: self.pick_lang("javascript"))
            return
        self.win.settings.setValue("journey/lang", lang)
        self.node_banner.hide()
        self.lang_bar.set_lang(lang)
        if self.info and self.info["ready"]:
            self.intro.set_markdown(self.info["intro"], self.info["base_dir"], lang)
            self.intro_box.setVisible(bool(self.intro.pieces))

    def ask_clear_cache(self):
        """지운 입력은 다음 채점 때 다시 만들 수 있어 [지우기]가 주 단추임. 단추가 둘이라 Enter 로 눌리지 않음."""
        self.win.ask("캐시 비우기", CLEAR_TEXT % size_text(self.cache_size), (("지우기", "clear", "primary"), ("닫기", "")),
                     lambda key: self.clear_cache())

    def clear_cache(self):
        self.show_cache(self.win.journey.clear_cache())

    # 화면 상태

    def set_busy(self, busy, text=""):
        """도는 일이 있는 동안 돌아가기·칩·캐시 단추·띠 단추·이어서 할 일·지도·목록 줄을 끄고 위 막대에 일의 이름과 반복 막대를 보임."""
        self.busy = busy
        for widget in (self.home_btn, self.lang_bar, self.clear_cache_btn, self.node_banner.action, self.next_btn, self.view):
            widget.setEnabled(not busy)
        for row in self.rows.rows:
            row.setEnabled(not busy)
        self.busy_label.setText(text if busy else "")
        self.busy_label.setVisible(busy and bool(text))
        self.busy_bar.setVisible(busy)

    def restyle(self):
        """글자 크기나 테마가 바뀌면 부름. 소개 글에 CSS 를 다시 넣고 칩 폭과 지도 높이를 다시 잡음. 지도·점·범례는 칠할 때 색을 읽음."""
        self.intro.restyle(theme.journey_css(), theme.code_font(theme.text_px() - 1))
        self.lang_bar.fit()
        self.view.refont()
        for widget in self.findChildren(kit.Dot) + self.findChildren(Mark) + self.findChildren(kit.Chevron):
            widget.update()
