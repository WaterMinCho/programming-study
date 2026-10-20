# -*- coding: utf-8 -*-
"""첫 화면(허브): 파이썬 스터디와 알고리즘 여행 줄 카드를 위아래로 쌓고, 그 아래에 두 쪽을 합친 최근 7일 학습과 제출을 나란히 둠.

카드의 수치는 두 서비스가 계산한 값을 그대로 보여 줌(파이썬은 session.overview, 여행은 journey.service 의 overview).
막대의 파이썬 채점 수는 시도 기록에서 서로 다른 (회차, 시각) 쌍의 수임. 회차를 한 번 채점하면 문항마다 같은 시각의 시도가
하나씩 남아서, 시도 수를 그대로 세면 여행 채점 한 번(1)과 견줄 수 없음.
카드의 바탕·테두리와 막대·던전 띠·최근 채점 줄은 칠할 때마다 지금 테마의 색을 읽음."""
import datetime
import html
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QToolTip,
                             QVBoxLayout, QWidget)

from gui import errors, motion, theme
from gui.journey_map import LEGEND, MapView
from gui.journey_page import LANG_LABEL
from gui.mascot import Mascot
from gui.widgets import LinkLabel, Para

DAYS = 7  # 막대로 보이는 날 수(오늘 포함)
RECENT = 5  # 최근 채점 줄 수
WEEKDAYS = "월화수목금토일"
SERIES = (("ok", "파이썬 스터디"), ("primary", "알고리즘 여행"))  # 막대 색과 범례. 날마다 이 순서로 나란히 그림. 줄 카드의 색 띠도 이 색임
ACCENT = 5  # 줄 카드 왼쪽 색 띠의 폭
RADIUS = 8  # 카드 모서리의 반지름. 파이썬 스터디 화면의 카드(QFrame#card)와 같음
PAD = 24  # 카드 안쪽 여백
GAP = 16  # 카드 사이
EMPTY = "아직 채점한 기록이 없습니다."
TIPS = (("제출", "내 풀이 폴더를 올리고 브라우저에서 PR 페이지를 엽니다."),
        ("문제 받기", "새로 올라온 문제를 내려받습니다. 내 풀이는 바꾸지 않습니다."))


def python_gradings(attempts):
    """파이썬 스터디의 채점 한 번마다 (시각, 회차 id). 시도 기록에서 서로 다른 (회차, 시각) 쌍을 모음."""
    return sorted({(a["at"], a["round"]) for a in attempts})


def stamp(at):
    """기록 시각(2026-10-20T21:03:05)을 화면 글자(10/20 21:03)로."""
    day, _, clock = str(at).partition("T")
    try:
        _, month, date = (int(n) for n in day.split("-"))
    except ValueError:
        return str(at)
    return "%d/%d %s" % (month, date, clock[:5])


def legend_html(entries):
    """(토큰, 기호, 이름) 목록을 색칠한 기호와 이름으로 이은 글. 색은 글을 넣을 때의 테마로 굳으므로 restyle 에서 다시 만듦."""
    return "&nbsp;&nbsp;&nbsp;".join('<span style="color: %s;">%s</span>&nbsp;%s' % (theme.color(token), mark, label)
                                     for token, mark, label in entries)


def caption(text=""):
    label = QLabel(text)
    label.setObjectName("caption")
    return label


def stat_row(box, *stats):
    """수치들을 세로줄로 나눠 box 에 한 줄로 놓고, 수치마다 그 앞의 세로줄(첫 수치는 None)을 돌려줌. 수치를 숨길 때 같이 숨김."""
    row = QHBoxLayout()
    row.setSpacing(28)
    lines = []
    for number, item in enumerate(stats):
        line = Divider(6) if number else None
        if line:
            row.addWidget(line)
        row.addWidget(item)
        lines.append(line)
    row.addStretch(1)
    box.addLayout(row)
    return lines


def next_line(box, tag):
    """"지금 할 일" 같은 꼬리표와 그 뒤의 글을 box 에 한 줄로 놓고 글 Para 를 돌려줌."""
    row = QHBoxLayout()
    row.setSpacing(10)
    label = QLabel(tag)
    label.setObjectName("tag")
    text = Para()
    row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(text, 1, Qt.AlignmentFlag.AlignVCenter)
    box.addLayout(row)
    return text


class Panel(QFrame):
    """둥근 바탕과 테두리를 직접 칠하는 카드. accent 토큰을 주면 왼쪽에 그 색의 띠를 칠함. lit 이면 테두리가 짙어짐."""

    def __init__(self, accent=None):
        super().__init__()
        self.accent, self.lit = accent, False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        painter.fillPath(path, theme.qcolor("surface"))
        if self.accent:
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(QRectF(0, 0, ACCENT, self.height()), theme.qcolor(self.accent))
            painter.restore()
        painter.setPen(QPen(theme.qcolor("border_strong" if self.lit else "border"), 1))
        painter.drawPath(path)


class Divider(QWidget):
    """수치와 수치, 막대와 최근 채점 사이의 세로줄. inset 만큼 위아래를 비움."""

    def __init__(self, inset=0):
        super().__init__()
        self.inset = inset
        self.setFixedWidth(1)

    def paintEvent(self, event):
        QPainter(self).fillRect(self.rect().adjusted(0, self.inset, 0, -self.inset), theme.qcolor("track"))


class Stat(QWidget):
    """큰 숫자(value) 하나와 그 아래 작은 이름(name)."""

    def __init__(self, name=""):
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)
        self.value = QLabel()
        self.value.setObjectName("stat")
        self.name = caption(name)
        box.addWidget(self.value)
        box.addWidget(self.name)


class EntryCard(Panel):
    """파이썬 스터디·알고리즘 여행으로 들어가는 줄 카드. 왼쪽 색 띠, 제목과 한 줄 설명, 그 아래 box 에 부른 쪽이 넣는 내용,
    오른쪽 세로 가운데의 단추. 카드 어디를 눌러도 button 을 누른 것과 같고, 단추가 꺼져 있으면 아무 일도 없음."""

    def __init__(self, title, about, accent, button):
        super().__init__(accent)
        self.button, self.down = button, False
        row = QHBoxLayout(self)
        row.setContentsMargins(ACCENT + PAD, 20, PAD + 4, 20)
        row.setSpacing(32)
        self.box = QVBoxLayout()
        self.box.setSpacing(0)
        head = QLabel(title)
        head.setObjectName("track")
        self.box.addWidget(head)
        self.box.addSpacing(2)
        self.box.addWidget(Para(about, "muted"))
        self.box.addSpacing(16)
        row.addLayout(self.box, 1)
        row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)

    def sync(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.button.isEnabled() else Qt.CursorShape.ArrowCursor)
        self.lit = self.lit and self.button.isEnabled()
        self.update()

    def enterEvent(self, event):
        self.lit = self.button.isEnabled()
        self.update()

    def leaveEvent(self, event):
        self.lit = False
        self.update()

    def mousePressEvent(self, event):
        self.down = event.button() == Qt.MouseButton.LeftButton
        event.accept()

    def mouseReleaseEvent(self, event):
        down, self.down = self.down, False
        if down and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()) \
                and self.button.isEnabled():
            self.button.click()


class DungeonStrip(QWidget):
    """던전마다 동그라미 하나를 길 위에 늘어놓은 띠와 오른쪽 범례. 색과 모양은 던전 지도(MapView.state, LEGEND)와 같음.
    폭이 모자라면 범례를 빼고 동그라미를 띠 폭에 맞춰 줄임. 마우스를 올리면 던전 이름이 나옴."""

    MARK = 22  # 동그라미의 가장 큰 지름
    STEP = 34  # 동그라미 가운데 사이의 가장 넓은 간격
    ROOM = 28  # 범례를 같이 그리려면 동그라미 하나에 남아야 하는 폭

    def __init__(self):
        super().__init__()
        self.rows = []
        self.setFixedHeight(self.MARK + 4)
        self.setMinimumWidth(16 * 15)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_rows(self, rows):
        self.rows = list(rows)
        self.update()

    def legend_font(self):
        font = QFont(self.font())
        font.setPixelSize(13)
        return font

    def legend_items(self):
        """[(토큰, 기호, 이름, 기호 폭, 이름 폭)]."""
        metrics = QFontMetricsF(self.legend_font())
        return [(token, mark, label, metrics.horizontalAdvance(mark + " "), metrics.horizontalAdvance(label))
                for token, mark, label in LEGEND]

    def legend_width(self):
        return sum(mark + label for _, _, _, mark, label in self.legend_items()) + 14 * (len(LEGEND) - 1)

    def marks_width(self):
        """동그라미에 쓰는 폭. 범례를 같이 그릴 수 없으면 띠 폭 전체."""
        room = self.width() - self.legend_width() - 24
        return room if room >= self.ROOM * len(self.rows) else self.width()

    def step(self):
        return min(self.STEP, (self.marks_width() - 2) / max(1, len(self.rows)))

    def radius(self):
        return min(self.MARK, self.step() - 3) / 2

    def centers(self):
        step, radius = self.step(), self.radius()
        return [QPointF(radius + 1 + number * step, self.height() / 2) for number in range(len(self.rows))]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        points = self.centers()
        if len(points) > 1:
            painter.setPen(QPen(theme.qcolor("track"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(points[0], points[-1])
        radius = self.radius() - 1
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(11 if radius >= 9 else 9)
        painter.setFont(font)
        for row, center in zip(self.rows, points):
            state = MapView.state(row)
            circle = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
            painter.setPen(QPen(theme.qcolor(state), 2, Qt.PenStyle.DotLine if state == "faint" else Qt.PenStyle.SolidLine))
            painter.setBrush(theme.qcolor("ok" if state == "ok" else "surface"))
            painter.drawEllipse(circle)
            painter.setPen(theme.qcolor({"ok": "surface", "faint": "muted"}.get(state, "ink")))
            painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(row["no"]))
        if self.marks_width() < self.width():
            painter.setFont(self.legend_font())
            left = self.width() - self.legend_width()
            for token, mark, label, mark_width, label_width in self.legend_items():
                for text, width, color in ((mark, mark_width, token), (label, label_width, "muted")):
                    painter.setPen(theme.qcolor(color))
                    painter.drawText(QRectF(left, 0, width + 1, self.height()), Qt.AlignmentFlag.AlignVCenter, text)
                    left += width
                left += 14

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            row = next((row for row, center in zip(self.rows, self.centers())
                        if math.hypot(event.pos().x() - center.x(), event.pos().y() - center.y()) <= self.radius() + 3), None)
            if row:
                QToolTip.showText(event.globalPos(), "던전 %d · %s 「%s」" % (row["no"], row["topic"], row["title"]), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)


class RecentList(QWidget):
    """최근 채점 줄들. 줄마다 왼쪽에 무엇을 채점했는지, 오른쪽에 시각을 작게 쓰고, 폭이 모자라면 왼쪽 글을 줄임표로 줄여 한 줄에 담음.
    줄인 글은 도움말에서 다 보임."""

    LINE = 1.6  # 줄 간격. 글자 크기의 몇 배
    STAMP_PX = 13  # 시각의 글자 크기
    GUTTER = 12  # 글과 시각 사이

    def __init__(self):
        super().__init__()
        self.rows = []  # [(글, 시각)]
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_rows(self, rows):
        self.rows = list(rows)
        self.setFixedHeight(math.ceil(self.line_height() * len(self.rows)))
        self.setToolTip("\n".join("%s · %s" % row for row in self.rows))
        self.update()

    def line_height(self):
        return QFontMetricsF(self.font()).height() * self.LINE

    def paintEvent(self, event):
        painter = QPainter(self)
        stamp_font = QFont(self.font())
        stamp_font.setPixelSize(self.STAMP_PX)
        line, metrics, stamp_metrics = self.line_height(), QFontMetricsF(self.font()), QFontMetricsF(stamp_font)
        for number, (label, stamp) in enumerate(self.rows):
            top, stamp_width = number * line, stamp_metrics.horizontalAdvance(stamp)
            painter.setFont(stamp_font)
            painter.setPen(theme.qcolor("muted"))
            painter.drawText(QRectF(self.width() - stamp_width, top, stamp_width, line),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, stamp)
            room = self.width() - stamp_width - self.GUTTER
            painter.setFont(self.font())
            painter.setPen(theme.qcolor("ink"))
            painter.drawText(QRectF(0, top, room, line), Qt.AlignmentFlag.AlignVCenter,
                             metrics.elidedText(label, Qt.TextElideMode.ElideRight, room))


class WeekChart(QWidget):
    """최근 7일의 날짜별 채점 수. 날마다 파이썬(ok)과 알고리즘(primary) 막대를 나란히 그리고, 바탕은 track 색.
    채점이 없는 날의 바탕은 옅게 그리고, 7일 모두 없으면 막대 자리 가운데에 EMPTY 를 씀.
    막대 아래에 요일과 날짜를 쓰고 오늘은 굵게 씀. 범례는 카드 머리줄에 있음."""

    def __init__(self):
        super().__init__()
        self.days = []  # [(날짜, 파이썬 채점 수, 알고리즘 채점 수)], 오늘이 마지막
        self.setMinimumHeight(130)

    def set_days(self, days):
        self.days = list(days)
        self.setToolTip("\n".join("%d/%d(%s) 파이썬 %d · 알고리즘 %d" % (day.month, day.day, WEEKDAYS[day.weekday()], python, journey)
                                  for day, python, journey in self.days))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        small = QFont(self.font())
        small.setPixelSize(12)
        day_line, date_line = QFontMetricsF(self.font()).height(), QFontMetricsF(small).height()
        label_top = self.height() - day_line - date_line - 2
        top, bottom = 2.0, label_top - 8.0
        span = max(1.0, bottom - top)
        peak = max([1] + [max(python, journey) for _, python, journey in self.days])
        column = self.width() / max(1, len(self.days))
        bar = max(10.0, min(18.0, column / 3.2))
        for number, (day, python, journey) in enumerate(self.days):
            middle = column * (number + 0.5)
            painter.setPen(Qt.PenStyle.NoPen)
            track = theme.qcolor("track")
            if not (python or journey):
                track.setAlphaF(0.6)
            for left, value, token in ((middle - bar - 2, python, SERIES[0][0]), (middle + 2, journey, SERIES[1][0])):
                painter.setBrush(track)
                painter.drawRoundedRect(QRectF(left, top, bar, span), 4, 4)
                if value:
                    filled = max(8.0, span * value / peak)
                    painter.setBrush(theme.qcolor(token))
                    painter.drawRoundedRect(QRectF(left, bottom - filled, bar, filled), 4, 4)
            today = number == len(self.days) - 1
            font = QFont(self.font())
            font.setBold(today)
            painter.setFont(font)
            painter.setPen(theme.qcolor("heading" if today else "ink"))
            painter.drawText(QRectF(column * number, label_top, column, day_line), Qt.AlignmentFlag.AlignCenter, WEEKDAYS[day.weekday()])
            painter.setFont(small)
            painter.setPen(theme.qcolor("muted"))
            painter.drawText(QRectF(column * number, label_top + day_line + 2, column, date_line), Qt.AlignmentFlag.AlignCenter,
                             "%d/%d" % (day.month, day.day))
        if self.days and not any(python or journey for _, python, journey in self.days):
            note = QFont(self.font())
            note.setPixelSize(13)
            painter.setFont(note)
            area = QRectF(0, top, self.width(), span)
            text = QFontMetricsF(note).boundingRect(area, Qt.AlignmentFlag.AlignCenter, EMPTY)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("surface"))
            painter.drawRoundedRect(text.adjusted(-14, -7, 14, 7), 8, 8)  # 바탕 막대 위에 글이 겹치지 않게 바탕색 알약을 깔음
            painter.setPen(theme.qcolor("muted"))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, EMPTY)


class HubPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        self.win = win
        inner = QWidget()
        inner.setObjectName("page")
        scroll = QScrollArea()  # 창이 작으면 내용을 찌그러뜨리지 않고 스크롤함
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        root = QVBoxLayout(inner)
        root.setContentsMargins(28, 18, 28, 12)
        root.setSpacing(GAP)

        head = QHBoxLayout()
        title = QLabel("프로그래밍 스터디")
        title.setObjectName("hub_title")
        self.user = QLabel()
        self.user.setObjectName("muted")
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("quiet")
        self.theme_btn.setToolTip("누를 때마다 시스템 → 밝게 → 어둡게 순서로 바뀝니다. 시스템은 운영체제 설정을 따릅니다.")
        head.addWidget(Mascot(34))
        head.addSpacing(6)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.user)
        head.addSpacing(12)
        head.addWidget(self.theme_btn)
        root.addLayout(head)
        self.notice = LinkLabel()
        self.notice.setObjectName("notice")  # refresh 가 html.escape 한 글을 넣음
        self.notice.linkActivated.connect(lambda _: win.show_notice_detail())
        self.notice.hide()
        root.addWidget(self.notice)

        self.python_btn = QPushButton("파이썬 스터디 들어가기")
        self.python_card = EntryCard("파이썬 스터디", "파이썬 교과목 평가에 나오는 문제를 회차로 나눠 풀고 채점합니다.", SERIES[0][0],
                                     self.python_btn)
        ready, mastered, self.python_last_stat = Stat("시험 준비도"), Stat("숙달한 단원"), Stat()
        self.ready, self.ready_label, self.mastered = ready.value, ready.name, mastered.value
        self.python_last, self.python_last_label = self.python_last_stat.value, self.python_last_stat.name
        box = self.python_card.box
        self.python_last_line = stat_row(box, ready, mastered, self.python_last_stat)[2]
        box.addSpacing(14)
        self.ready_bar = QProgressBar()
        self.ready_bar.setRange(0, 100)
        self.ready_bar.setTextVisible(False)
        box.addWidget(self.ready_bar)
        box.addSpacing(16)
        self.python_next = next_line(box, "지금 할 일")

        self.journey_btn = QPushButton("여행 떠나기")
        self.journey_card = EntryCard("알고리즘 여행", "코딩 테스트에 자주 나오는 알고리즘을 던전별로 나눠 Python 이나 JavaScript 로 풉니다.",
                                      SERIES[1][0], self.journey_btn)
        self.journey_error = Para(name="error")
        self.journey_body = QWidget()  # 여행 기록을 읽지 못하면 수치·띠·추천을 통째로 숨김
        self.journey_card.box.addWidget(self.journey_error)
        self.journey_card.box.addWidget(self.journey_body)
        box = QVBoxLayout(self.journey_body)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        passed, boss = Stat("통과한 문제"), Stat("보스 클리어")
        self.journey_langs = {lang: Stat("%s 통과" % label) for lang, label in LANG_LABEL.items()}
        self.journey_passed, self.journey_boss = passed.value, boss.value
        stat_row(box, passed, boss, *self.journey_langs.values())
        box.addSpacing(14)
        self.strip = DungeonStrip()
        box.addWidget(self.strip)
        box.addSpacing(16)
        self.journey_next = next_line(box, "다음 추천")
        for button in (self.python_btn, self.journey_btn):
            button.setObjectName("primary")
            button.setProperty("big", True)
            button.setProperty("track", True)
            button.setMinimumSize(250, 54)
        self.python_card.sync()
        self.journey_card.sync()
        root.addWidget(self.python_card)
        root.addWidget(self.journey_card)

        bottom = QHBoxLayout()
        bottom.setSpacing(GAP)
        week_card, box, week_head = self.panel("최근 7일 학습")
        self.series = caption()
        self.streak = QLabel()
        self.streak.setObjectName("tag")
        week_head.addWidget(self.series)
        week_head.addSpacing(16)
        week_head.addWidget(self.streak)
        row = QHBoxLayout()
        row.setSpacing(24)
        self.chart = WeekChart()
        self.recent_box = QWidget()  # 최근 채점 칸. 채점 기록이 없으면 세로줄과 함께 숨겨서 막대가 카드 폭을 다 씀
        column = QVBoxLayout(self.recent_box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        self.recent = RecentList()
        column.addWidget(caption("최근 채점"))
        column.addWidget(self.recent)
        column.addStretch(1)
        self.recent_line = Divider()
        row.addWidget(self.chart, 1)
        row.addWidget(self.recent_line)
        row.addWidget(self.recent_box, 1)
        box.addLayout(row, 1)
        git_card, box, _ = self.panel("제출")
        row = QHBoxLayout()
        row.setSpacing(10)
        self.git_btn = QPushButton("제출(PR 올리기)")
        self.sync_btn = QPushButton("문제 받기")
        for button in (self.git_btn, self.sync_btn):
            button.setMinimumHeight(40)
            row.addWidget(button, 1)
        self.git_tips = QWidget()  # 두 단추의 설명. 제출을 쓸 수 없으면 숨기고 git_hint 에 이유를 보임
        grid = QGridLayout(self.git_tips)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        for line, (name, about) in enumerate(TIPS):
            tag = caption(name)
            tag.setContentsMargins(0, 1, 0, 0)  # 설명 첫 줄의 글자 가운데에 맞춤
            grid.addWidget(tag, line, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(Para(about), line, 1)
        grid.setColumnStretch(1, 1)
        self.git_hint = Para(name="muted")
        self.status = Para(name="muted")
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.hide()
        box.addLayout(row)
        box.addSpacing(6)
        box.addWidget(self.git_tips)
        box.addWidget(self.git_hint)
        box.addWidget(self.status)
        box.addWidget(self.busy_bar)
        box.addStretch(1)
        bottom.addWidget(week_card, 2)
        bottom.addWidget(git_card, 1)
        root.addLayout(bottom, 1)  # 창이 크면 아래 카드가 늘어나 막대가 길어짐

        self.foot = LinkLabel('글자 크기: Ctrl(맥은 Cmd) 과 +, -, 0 · <a href="%s">불편한 점 신고하기</a>' % errors.ISSUE_URL)
        self.foot.setObjectName("muted")
        self.foot.setOpenExternalLinks(True)
        root.addWidget(self.foot)

        self.theme_btn.clicked.connect(win.cycle_theme)
        self.python_btn.clicked.connect(win.go_home)
        self.journey_btn.clicked.connect(lambda: win.go_journey())
        self.git_btn.clicked.connect(win.submit_pr)
        self.sync_btn.clicked.connect(win.fetch_problems)

    @staticmethod
    def panel(title):
        """아래쪽 카드. (카드, 내용을 넣을 세로 상자, 제목 오른쪽에 위젯을 더할 머리줄)."""
        frame = Panel()
        box = QVBoxLayout(frame)
        box.setContentsMargins(PAD + ACCENT, 18, PAD, 18)  # 줄 카드의 글과 같은 자리에서 시작함
        box.setSpacing(10)
        head = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("h2")
        head.addWidget(label)
        head.addStretch(1)
        box.addLayout(head)
        box.addSpacing(4)
        return frame, box, head

    def refresh(self):
        win = self.win
        overview = win.session.overview()
        self.user.setText("ID: %s" % overview["user"])
        motion.count_text(self.ready, "%d%%", overview["readiness"])
        motion.count(self.ready_bar, overview["readiness"], self.ready_bar.setValue)
        self.mastered.setText("%d / %d" % (overview["mastered"], overview["total_units"]))
        self.python_next.setText(win.next_action(overview)[0])
        done = [r for r in overview["rounds"] if r["completed"]]
        if done:
            last = done[-1]
            earned, total = (int(n) for n in (last["first_score"] or last["score"]).split("/"))
            self.python_last.setText("%d / %d" % (earned, total))
            self.python_last_label.setText("%s 첫 채점" % last["title"])
        self.python_last_stat.setVisible(bool(done))  # 제출한 회차가 없으면 지난 회차 수치를 빼고 준비도와 단원만 보임
        self.python_last_line.setVisible(bool(done))
        journey = self.show_journey()
        self.show_week(overview, journey)
        usable = win.gitflow is not None
        self.git_btn.setEnabled(usable)
        self.sync_btn.setEnabled(usable)
        self.git_tips.setVisible(usable)
        self.git_hint.setVisible(not usable)
        self.git_hint.setText("" if usable else "지금은 제출과 문제 받기를 쓸 수 없습니다. 풀이와 채점은 계속할 수 있습니다.\n" + win.git_reason)
        note = win.notice
        self.notice.setVisible(bool(note))
        if note:
            more = ' <a href="detail">자세히</a>' if note.get("detail") else ""
            self.notice.setText(html.escape(note.get("message") or "") + more)
        self.restyle()

    def show_journey(self):
        """알고리즘 여행 카드. 여행 기록을 읽지 못했으면 이유를 보이고 단추를 끄고 None 을, 아니면 여행 서비스의 overview 를 돌려줌."""
        win = self.win
        ready = win.journey is not None
        self.journey_body.setVisible(ready)
        self.journey_error.setVisible(not ready)
        self.journey_btn.setEnabled(ready)
        self.journey_card.sync()
        if not ready:
            self.journey_error.setText("%s\n파일을 고친 뒤 프로그램을 다시 실행해 주세요." % win.journey_error)
            return None
        overview = win.journey.overview()
        self.journey_passed.setText("%d / %d" % (overview["passed"], overview["total"]))
        self.journey_boss.setText("%d / %d" % (overview["cleared"], overview["ready"]))
        for lang, item in self.journey_langs.items():
            item.value.setText(str(overview["by_lang"].get(lang, 0)))
        self.strip.set_rows(overview["dungeons"])
        target = overview["next"]
        if target:
            there = next((row for row in overview["dungeons"] if row["id"] == target["did"]), None)
            place = " · 던전 %d 「%s」" % (there["no"], there["title"]) if there else ""
            self.journey_next.setText("%s %s%s" % (target["no"], target["title"], place))
        elif overview["total"]:
            self.journey_next.setText("출제된 던전을 모두 클리어했습니다.")
        else:
            self.journey_next.setText("아직 출제된 던전이 없습니다.")
        return overview

    def show_week(self, overview, journey):
        """막대, 연속 학습일, 최근 채점. overview 는 파이썬 쪽, journey 는 여행 쪽 overview(읽지 못했으면 None)."""
        gradings = python_gradings(self.win.session.prof["attempts"])
        python = {}
        for at, _ in gradings:
            python[at[:10]] = python.get(at[:10], 0) + 1
        activity = journey["activity"] if journey else {}
        today = datetime.date.today()
        days = [today - datetime.timedelta(days=back) for back in range(DAYS - 1, -1, -1)]
        self.chart.set_days((day, python.get(day.isoformat(), 0), activity.get(day.isoformat(), 0)) for day in days)
        streak, day = 0, today
        while python.get(day.isoformat()) or activity.get(day.isoformat()):
            streak += 1
            day -= datetime.timedelta(days=1)
        self.streak.setText("연속 학습 %d일" % streak)
        titles = {r["id"]: r["title"] for r in overview["rounds"]}
        rows = [(at, "파이썬 스터디 %s" % titles.get(rid, rid)) for at, rid in gradings[-RECENT:]]
        for entry in (journey["recent"] if journey else []):
            rows.append((str(entry["at"] or ""), "%s %s %.1f점" % (entry["no"], LANG_LABEL.get(entry["lang"], entry["lang"]),
                                                                  entry["score"] or 0.0)))
        rows.sort(key=lambda row: row[0], reverse=True)
        self.recent.set_rows((label, stamp(at)) for at, label in rows[:RECENT])
        self.recent_box.setVisible(bool(rows))
        self.recent_line.setVisible(bool(rows))

    def restyle(self):
        self.theme_btn.setText("테마: %s" % theme.MODES[theme.state["mode"]])
        self.series.setText(legend_html([(token, "■", label) for token, label in SERIES]))
        for widget in (self.chart, self.strip, self.recent, self.python_card, self.journey_card):
            widget.update()

    def set_busy(self, busy, text=""):
        self.python_btn.setEnabled(not busy)
        self.journey_btn.setEnabled(not busy and self.win.journey is not None)
        for widget in (self.git_btn, self.sync_btn):
            widget.setEnabled(not busy and self.win.gitflow is not None)
        for entry in (self.python_card, self.journey_card):
            entry.sync()
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")
