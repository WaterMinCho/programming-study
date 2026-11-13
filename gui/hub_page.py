# -*- coding: utf-8 -*-
"""첫 화면(허브): 위 막대의 이름·ID·설정 팝업, 이어서 할 일 카드 하나, 과목별 학습과 오답 노트, 최근 7일 학습 카드를 표시함.
구역은 위아래로 쌓고 창이 작으면 스크롤함.

카드의 수치는 네 서비스가 계산한 값을 그대로 보여 줌(파이썬은 session.overview, 여행은 journey.service, 웹은 webprep.service,
AI 비전 개론은 aiprep.service 의 overview).
막대의 파이썬 채점 수는 시도 기록에서 서로 다른 (회차, 시각) 쌍의 수임. 회차를 한 번 채점하면 문항마다 같은 시각의 시도가
하나씩 남아서, 시도 수를 그대로 세면 여행 채점 한 번(1)과 견줄 수 없음.
이어서 할 일은 웹의 진행 중 미션이나 오늘 복습, AI 비전 개론의 복습이 aiprep.service.REVIEW_FIRST 이상이면 그것(둘 다면 마지막 기록 순),
아니면 가장 최근에 기록을 남긴 트랙의 다음 할 일, 기록이 없으면 파이썬 스터디의
다음 회차임. 여행의 다음 할 일은 journey_text.next_item 이 마지막으로 연 문제부터 보고 고름. 막대와 최근 채점 줄은 칠할 때마다 지금 테마의 색을 읽음."""
import datetime
import html
import math

import study

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF, QPainter
from PyQt6.QtWidgets import QApplication, QBoxLayout, QHBoxLayout, QSizePolicy, QWidget

from aiprep import service as ai_service
from gui import ai_text, journey_text, kit, theme, web_text
from gui.mascot import Mascot
from gui.settings_menu import SettingsMenu
from gui.workspace import SubjectGrid, SubjectTile
from gui.wrong_page import count_line
from session import SessionError
from webprep.record import RecordError
from webprep.service import WebError

DAYS = 7  # 막대로 보이는 날 수(오늘 포함)
RECENT = 5  # 최근 채점 줄 수
WEEKDAYS = "월화수목금토일"
TRACKS = (("python", "파이썬"), ("journey", "알고리즘"), ("web", "웹 면접"), ("ai", "AI"))  # 막대 순서와 범례 이름. 트랙 색(theme.SERIES)도 이 순서
BAR_GAP = 2  # 한 날의 막대 사이
EMPTY = "최근 7일 학습 기록이 없습니다.\n공부 트랙에서 시작할 수 있습니다."
PYTHON_ABOUT = "파이썬 교과목 평가에 나오는 문제를 회차로 나눠 풀고 채점합니다."
FIX_HINT = "파일을 고친 뒤 프로그램을 다시 실행해 주세요."
SIDE_MIN = 40  # 최근 7일 카드에서 막대와 최근 채점을 나란히 두는 가장 좁은 폭(본문 글자 수). 보통 글자 680, 더 큰 글자 840
SIDE_GAP = 32  # 나란히 둘 때 막대와 최근 채점 사이
RECENT_SHARE = 0.45  # 나란히 둘 때 최근 채점 칸이 받는 폭의 상한(막대가 더 넓게)
QWIDGETSIZE_MAX = 16777215  # Qt 위젯 크기의 상한. 최근 채점 칸의 고정 폭을 풀 때 씀
ACCOUNT_WIDTH = 240  # ID 는 이 폭까지 보이고 긴 이름은 도움말에 남김


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


def first_sentence(text):
    """안내 글의 첫 문장. 카드의 설명은 한 줄이라 '지금 할 일' 안내의 둘째 문장과 둘째 줄을 뺌."""
    line = text.splitlines()[0] if text else ""
    head, dot, _ = line.partition(". ")
    return head + "." if dot else line


def split_action(label):
    """파이썬 스터디의 '지금 할 일' 글자("2회차 이어 풀기", "진단 테스트 시작", "다음 회차 시작")를 (이름, 단추 글자)로 나눔."""
    for tail in ("이어 풀기", "시작"):
        if label.endswith(" " + tail):
            return label[:-len(tail) - 1], tail
    return label, "시작"


class RecentList(QWidget):
    """최근 채점 줄들. 줄마다 왼쪽에 무엇을 채점했는지(label 17), 오른쪽에 시각(caption 14)을 쓰고, 폭이 모자라면 왼쪽 글을 줄임표로
    줄여 한 줄에 담음. 줄인 글은 도움말에서 다 보임."""

    GUTTER = 12  # 글과 시각 사이

    def __init__(self):
        super().__init__()
        self.rows = []  # [(글, 시각)]
        kit.typed(self, "label")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def refont(self):
        self.set_rows(self.rows)

    def set_rows(self, rows):
        self.rows = list(rows)
        self.setFixedHeight(self.line_height() * len(self.rows))
        self.setToolTip("\n".join("%s · %s" % row for row in self.rows))
        self.update()

    @staticmethod
    def line_height():
        return theme.TYPE["body"][1]

    def natural_width(self):
        """가장 긴 줄이 줄임표 없이 다 보이는 폭."""
        metrics, stamp_metrics = QFontMetricsF(self.font()), QFontMetricsF(theme.font("caption"))
        return math.ceil(max([metrics.horizontalAdvance(label) + self.GUTTER + stamp_metrics.horizontalAdvance(when)
                              for label, when in self.rows] or [0])) + 1

    def paintEvent(self, event):
        painter = QPainter(self)
        stamp_font = theme.font("caption")
        line, metrics, stamp_metrics = self.line_height(), QFontMetricsF(self.font()), QFontMetricsF(stamp_font)
        for number, (label, when) in enumerate(self.rows):
            top, stamp_width = number * line, stamp_metrics.horizontalAdvance(when)
            painter.setFont(stamp_font)
            painter.setPen(theme.qcolor("faint"))
            painter.drawText(QRectF(self.width() - stamp_width, top, stamp_width, line),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, when)
            room = self.width() - stamp_width - self.GUTTER
            painter.setFont(self.font())
            painter.setPen(theme.qcolor("ink"))
            painter.drawText(QRectF(0, top, room, line), Qt.AlignmentFlag.AlignVCenter,
                             metrics.elidedText(label, Qt.TextElideMode.ElideRight, room))


class WeekChart(QWidget):
    """최근 7일의 날짜별 학습 수. 날마다 파이썬, 알고리즘, 웹, AI 비전 막대를 트랙 색(theme.SERIES)으로 TRACKS 순서로 나란히 그리고, 바탕은 track 색.
    기록이 없는 날의 바탕은 옅게 그리고, 7일 모두 없으면 막대 자리 가운데에 EMPTY 를 씀.
    막대 아래에 요일과 날짜를 micro 13 으로 쓰고 오늘은 굵게 씀. 하루 칸이 좁아 날짜(10/15)끼리 붙으면 날만(15) 씀. 범례는 막대 칸의 위 줄에 있음."""

    def __init__(self):
        super().__init__()
        self.days = []  # [(날짜, 파이썬 채점 수, 알고리즘 채점 수, 웹 검사·드릴 수, AI 하루 수)], 오늘이 마지막
        self.setMinimumHeight(136)

    def set_days(self, days):
        self.days = list(days)
        self.setToolTip("\n".join("%d/%d(%s) 파이썬 %d · 알고리즘 %d · 웹 %d · AI %d" % (day.month, day.day, WEEKDAYS[day.weekday()], python, journey,
                                                                                    web, ai)
                                  for day, python, journey, web, ai in self.days))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        small, bold = theme.font("micro"), theme.font("micro", True)
        line = theme.TYPE["micro"][1]
        label_top = self.height() - 2 * line - 4
        top, bottom = 2.0, label_top - 8.0
        span = max(1.0, bottom - top)
        peak = max([1] + [max(values) for _, *values in self.days])
        column = self.width() / max(1, len(self.days))
        bar = max(8.0, min(16.0, (column - 12) / len(TRACKS) - BAR_GAP))
        day_only = column < QFontMetricsF(small).horizontalAdvance("10/15") + 12
        for number, (day, *values) in enumerate(self.days):
            middle = column * (number + 0.5)
            painter.setPen(Qt.PenStyle.NoPen)
            track = theme.qcolor("track")
            if not any(values):
                track.setAlphaF(0.6)
            first = middle - (len(TRACKS) * bar + (len(TRACKS) - 1) * BAR_GAP) / 2
            for slot, (value, token) in enumerate(zip(values, theme.SERIES)):
                left = first + slot * (bar + BAR_GAP)
                painter.setBrush(track)
                painter.drawRoundedRect(QRectF(left, top, bar, span), 4, 4)
                if value:
                    filled = max(8.0, span * value / peak)
                    painter.setBrush(theme.qcolor(token))
                    painter.drawRoundedRect(QRectF(left, bottom - filled, bar, filled), 4, 4)
            today = number == len(self.days) - 1
            painter.setFont(bold if today else small)
            painter.setPen(theme.qcolor("ink" if today else "faint"))
            painter.drawText(QRectF(column * number, label_top, column, line), Qt.AlignmentFlag.AlignCenter, WEEKDAYS[day.weekday()])
            painter.drawText(QRectF(column * number, label_top + line + 4, column, line), Qt.AlignmentFlag.AlignCenter,
                             "%d" % day.day if day_only else "%d/%d" % (day.month, day.day))
        if self.days and not any(any(values) for _, *values in self.days):
            painter.setFont(theme.font("caption"))
            area = QRectF(0, top, self.width(), span)
            flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
            text = QFontMetricsF(theme.font("caption")).boundingRect(area, flags, EMPTY)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("surface"))
            painter.drawRoundedRect(text.adjusted(-16, -8, 16, 8), 8, 8)  # 바탕 막대 위에 글이 겹치지 않게 바탕색 알약을 깔음
            painter.setPen(theme.qcolor("muted"))
            painter.drawText(area, flags, EMPTY)


class WeekBody(QWidget):
    """최근 7일 카드의 막대 칸(범례 줄과 막대)과 최근 채점 칸. 폭이 SIDE_MIN 이상이면 막대 칸 오른쪽에 최근 채점을 두고, 좁으면 막대 아래에 둠.
    나란히 둘 때 최근 채점 칸은 가장 긴 줄이 다 보이는 폭이되 RECENT_SHARE 를 넘지 않고, 남는 폭은 막대 칸이 받음.
    최근 채점 칸이 숨으면 막대 칸이 폭을 다 받음."""

    def __init__(self, plot, recent_box, recent):
        super().__init__()
        self.plot, self.recent_box, self.recent = plot, recent_box, recent
        self.row = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.addWidget(plot, 1)
        self.row.addWidget(recent_box, 0, Qt.AlignmentFlag.AlignTop)
        self.side = None
        self.arrange()

    def arrange(self):
        """지금 폭과 글자 크기에 맞춰 두 칸을 나란히 두거나 위아래로 쌓음. 글자 크기나 최근 채점 줄이 바뀐 뒤에도 부름."""
        side = self.width() >= SIDE_MIN * theme.TYPE["body"][0]
        if side != self.side:
            self.side = side
            self.row.setDirection(QBoxLayout.Direction.LeftToRight if side else QBoxLayout.Direction.TopToBottom)
            self.row.setSpacing(SIDE_GAP if side else 16)
        if side:
            self.recent_box.setFixedWidth(min(self.recent.natural_width(), int((self.width() - SIDE_GAP) * RECENT_SHARE)))
        else:
            self.recent_box.setMinimumWidth(0)
            self.recent_box.setMaximumWidth(QWIDGETSIZE_MAX)

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        return QSize(0, size.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()


class HubBar(kit.TopBar):
    """앱 이름과 ID, 글자 크기와 테마 도구를 담음. 폭이 모자라면 도구를 아래 줄에 둠."""

    def __init__(self):
        super().__init__(plain=True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.row.removeWidget(self.title)
        self.identity = QWidget()
        self.identity_row = kit.box(self.identity, spacing=12, horizontal=True)
        self.controls = QWidget()
        self.control_row = kit.box(self.controls, spacing=8, horizontal=True)
        self.row.setContentsMargins(32, 16, kit.MARGIN - kit.FLUSH, 16)
        self.row.setSpacing(8)
        self.row.addWidget(self.identity, 1)
        self.row.addWidget(self.controls, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def add_right(self, widget, flush=False):
        self.control_row.addWidget(widget)
        return widget

    def arrange(self):
        left, top, right, bottom = self.row.getContentsMargins()
        identity, controls = self.identity_row.sizeHint(), self.control_row.sizeHint()
        # 조건부 단추가 나타나도 본문 시작 높이를 바꾸지 않도록 전체 도구 폭으로 줄을 정함.
        tools = [self.control_row.itemAt(i).widget() for i in range(self.control_row.count())]
        tools = [widget for widget in tools if widget is not None]
        reserved = sum(widget.sizeHint().width() for widget in tools) + self.control_row.spacing() * max(0, len(tools) - 1)
        stacked = identity.width() + 24 + max(controls.width(), reserved) > self.width() - left - right
        self.row.setDirection(QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight)
        height = identity.height() + 8 + controls.height() if stacked else max(identity.height(), controls.height())
        self.setFixedHeight(max(theme.CONTROL["topbar"], top + height + bottom))

    def refont(self):
        self.arrange()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self.arrange()
        return result


class HubPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.target = None  # 이어서 할 일 카드의 단추가 여는 것: 부르면 화면을 여는 함수
        self.journey_next = None  # 여행의 이어서 할 일(journey_text.next_item). 여행 줄과 카드가 같은 문제를 말함
        outer = kit.box(self)

        self.top = top = HubBar()
        self.user = kit.ElideLabel("", "caption", "tertiary")
        self.user.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.user.setMaximumWidth(ACCOUNT_WIDTH)
        top.identity_row.addWidget(Mascot(32))
        top.identity_row.addWidget(kit.label("프로그래밍 스터디", "headline"))
        top.identity_row.addStretch(1)
        top.identity_row.addWidget(self.user)
        self.settings_btn = kit.button("설정", "text", "s", onbg=True)
        self.privacy_btn = kit.button("내 정보·데이터", "text", "s", onbg=True)
        self.privacy_btn.clicked.connect(win.show_privacy)
        top.add_right(self.privacy_btn)
        self.submission_setup = kit.button("풀이 제출", "text", "s", onbg=True)
        self.submission_setup.setProperty("submission_action", True)
        self.submission_setup.clicked.connect(win.submit_pr)
        top.add_right(self.submission_setup)
        self.server_connection = kit.button("다른 서버 연결", "text", "s", onbg=True)
        self.server_connection.clicked.connect(win.show_submission_setup)
        self.server_connection.setVisible(win.can_configure_submission())
        top.add_right(self.server_connection)
        self.manual_sync = kit.button("프로그램 업데이트", "text", "s", onbg=True)
        self.manual_sync.clicked.connect(win.fetch_problems)
        top.add_right(self.manual_sync)
        self.settings_panel = SettingsMenu(self, self.settings_btn)
        self.text_buttons = self.settings_panel.text_buttons
        self.theme_buttons = self.settings_panel.theme_buttons
        self.identity_btn = self.settings_panel.identity_btn
        self.replay_tour = self.settings_panel.replay_tour
        top.add_right(self.settings_btn, flush=True)
        outer.addWidget(top)

        inner = QWidget()
        root = kit.box(inner, (0, 16, 0, 48))
        self.summary = kit.para("", "body", "secondary")
        root.addWidget(kit.heading(kit.label("내 학습 현황", "title"), self.summary))
        root.addSpacing(theme.GAP["description_content"])
        self.notice_banner, self.notice = kit.link_banner("warning")  # refresh 가 html.escape 한 글을 넣음
        self.notice.linkActivated.connect(lambda _: win.show_notice_detail())
        self.notice_banner.hide()
        self.next_card = kit.NextCard()
        self.next_card.row.setContentsMargins(24, 16, 24, 16)
        self.next_btn = self.next_card.button
        lead = QWidget()  # 숨은 알림 자리를 비우고 다음 행동까지 묶음.
        lead_box = kit.box(lead, spacing=theme.GAP["group"])
        lead_box.addWidget(self.notice_banner)
        lead_box.addWidget(self.next_card)
        root.addWidget(lead)
        root.addSpacing(theme.GAP["section"])

        head, _, _ = kit.section("과목별 학습")
        root.addLayout(head)
        root.addSpacing(theme.GAP["description_content"])
        self.tracks = SubjectGrid()
        self.python_row = self.tracks.add(SubjectTile("파이썬 스터디", "series_python"))
        self.journey_row = self.tracks.add(SubjectTile("알고리즘 여행", "series_algorithm"))
        self.web_row = SubjectTile("웹 면접 준비", "series_web")
        if "web" in study.ENTRY_TRACKS:
            self.tracks.add(self.web_row)
        else:
            self.web_row.setParent(self.tracks)
            self.web_row.hide()
        self.ai_row = self.tracks.add(SubjectTile(ai_text.TRACK, "series_ai"))
        self.journey_error = kit.banner("", "danger")  # 여행 기록을 읽지 못한 이유. 그동안 여행 줄은 눌리지 않음
        self.web_error = kit.banner("", "danger")
        self.ai_error = kit.banner("", "danger")
        stack = QWidget()  # 목록과 띠 사이 12. 숨은 띠 옆에는 간격이 생기지 않아 띠가 없으면 구역 사이가 48 로 남음
        stack_box = kit.box(stack, spacing=12)
        stack_box.addWidget(self.tracks)
        for banner in (self.journey_error, self.web_error, self.ai_error):
            banner.hide()
            stack_box.addWidget(banner)
        root.addWidget(stack)
        root.addSpacing(theme.GAP["section"])

        head, _, _ = kit.section("오답 노트")
        root.addLayout(head)
        root.addSpacing(theme.GAP["description_content"])
        self.notes = kit.RowList()  # 오답 노트 트랙마다 한 줄. 누르면 오답 노트를 그 트랙으로 엶
        self.note_rows = []  # [(공급자, 줄)]
        series = dict(zip((tid for tid, _ in TRACKS), theme.SERIES))  # 공부 트랙 줄과 같은 점. 점 색이 없는 트랙은 점 없이 둠
        for track in win.wrong_tracks:
            mark = kit.Dot(series[track.tid], 8) if track.tid in series else None
            row = self.notes.add(kit.Row(track.name, "", mark=mark, strong=True, wrap=True))
            row.clicked.connect(lambda tid=track.tid: win.show_wrong(tid, "hub"))
            self.note_rows.append((track, row))
        root.addWidget(self.notes)
        root.addSpacing(theme.GAP["section"])

        head, _, self.streak = kit.section("최근 7일 학습")
        root.addLayout(head)
        root.addSpacing(theme.GAP["description_content"])
        self.week_card, box = kit.card(spacing=0)
        plot = QWidget()  # 막대 칸: 범례 줄과 막대. 채점 수가 막대의 오른쪽 끝에 맞아서 나란히 둔 최근 채점 칸의 수로 읽히지 않음
        plot_box = kit.box(plot, spacing=8)
        legend = QHBoxLayout()
        legend.setContentsMargins(0, 0, 0, 0)
        legend.setSpacing(16)
        for token, (_, name) in zip(theme.SERIES, TRACKS):
            item = QHBoxLayout()
            item.setSpacing(8)
            item.addWidget(kit.Dot(token, 8))
            item.addWidget(kit.label(name, "caption", "secondary"))
            legend.addLayout(item)
        legend.addStretch(1)
        self.total = kit.label("", "caption", "tertiary")
        legend.addWidget(self.total)
        plot_box.addLayout(legend)
        self.chart = WeekChart()
        plot_box.addWidget(self.chart, 1)
        self.recent_box = QWidget()  # 최근 채점 칸. 채점 기록이 없으면 숨겨서 카드가 막대만 보임
        recent = kit.box(self.recent_box, spacing=4)
        self.recent = RecentList()
        recent.addWidget(kit.label("최근 채점", "caption", "tertiary"))
        recent.addWidget(self.recent)
        self.week = WeekBody(plot, self.recent_box, self.recent)
        box.addWidget(self.week)
        root.addWidget(self.week_card)
        root.addSpacing(theme.GAP["section"])

        self.git_hint = kit.banner("", "warning")  # 제출을 쓸 수 없는 이유. 그동안 두 줄은 눌리지 않음
        self.git_hint.hide()
        root.addSpacing(12)
        root.addWidget(self.git_hint)
        self.status = kit.para("", "caption", "secondary")
        self.status.hide()
        self.busy_bar = kit.progress()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.hide()
        root.addWidget(self.status)
        root.addSpacing(8)
        root.addWidget(self.busy_bar)
        from gui.team_dashboard import TeamCard
        self.team_card = TeamCard(win)
        root.addSpacing(24)
        root.addWidget(self.team_card)
        root.addSpacing(24)
        column = kit.column(inner)
        column.layout().setContentsMargins(32, 0, 32, 0)
        self.scroll = kit.scroll(column)
        outer.addWidget(self.scroll, 1)

        self.next_btn.clicked.connect(self.open_next)
        self.python_row.clicked.connect(win.go_home)
        self.journey_row.clicked.connect(lambda: win.go_journey())
        if "web" in study.ENTRY_TRACKS:
            self.web_row.clicked.connect(lambda: win.go_web())
        self.ai_row.clicked.connect(lambda: win.go_ai())

    def refresh(self):
        win = self.win
        self.team_card.refresh_identity()
        overview = win.session.overview()
        self.user.setText("ID: %s" % overview["user"])
        name, _ = split_action(win.next_action(overview)[0])
        self.python_row.set_second("다음은 %s" % name)
        self.python_row.set_metric(overview["mastered"], overview["total_units"], "숙달 단원")
        journey = self.show_journey()
        web = self.show_web()
        ai = self.show_ai()
        for track, row in self.note_rows:
            detail = count_line(track.groups())
            if track.tid == "ai" and ai:
                detail = "%s · %s" % (ai_text.COURSES[ai["course"]], detail)
            row.set_second(detail)
        self.show_week(overview, journey, web, ai)
        self.show_next(overview, journey, web, ai)
        self.next_card.setToolTip(self.next_card.line.text())
        self.next_card.line.hide()
        self.next_card.arrange()
        usable = win.gitflow is not None
        self.git_hint.setVisible(not usable)
        self.git_hint.text.setText("" if usable else "지금은 풀이 제출과 업데이트를 쓸 수 없습니다. 풀이와 채점은 계속할 수 있습니다.\n" + win.git_reason)
        note = win.notice
        self.notice_banner.setVisible(bool(note))
        if note:
            more = ' <a href="detail">자세히</a>' if note.get("detail") else ""
            self.notice.setText(html.escape(note.get("message") or "") + more)
        self.restyle()

    def refresh_submission(self, allowed=None, busy=False):
        win = self.win
        usable = win.session is not None and win.gitflow is not None
        busy = busy or win.job is not None or win.pending_close or win.close_pending or win.submission_running
        if allowed is None:
            allowed = win.has_submission_consent()
        ready = (usable and allowed and win.pending_submission.get("status") == "ok"
                 and win.pending_submission.get("pending", False))
        available = usable and win.problem_updates.get("status") == "ok" and win.problem_updates.get("available", False)
        focused = QApplication.focusWidget()
        if ((focused is self.submission_setup and not ready) or (focused is self.manual_sync and not available)):
            target = getattr(win, "workspace", self)
            target.setFocus(Qt.FocusReason.OtherFocusReason)
        kit.set_tone(self.submission_setup, "accent" if ready else None)
        self.submission_setup.setVisible(ready)
        self.submission_setup.setEnabled(ready and not busy)
        self.submission_setup.setAccessibleDescription("제출할 풀이가 있습니다." if ready else "답안 파일·채점·진도를 비공개 서버에 제출합니다.")
        self.submission_setup.setToolTip("답안 파일·채점·진도를 비공개 서버에 제출합니다. 보낼 파일은 [내 정보·데이터]에서 확인할 수 있습니다.")
        self.server_connection.setVisible(win.can_configure_submission())
        self.server_connection.setEnabled(usable and not busy)
        self.manual_sync.setVisible(available)
        self.manual_sync.setEnabled(available and not busy)
        kit.set_tone(self.manual_sync, "accent" if available else None)

    def show_journey(self):
        """알고리즘 여행 줄. 여행 기록을 읽지 못했으면 이유를 띠로 보이고 줄을 끄고 None 을, 아니면 여행 서비스의 overview 를 돌려줌.
        이어서 할 일은 설정 journey/last 의 마지막으로 연 문제를 먼저 보고 journey_next 에 둠."""
        win = self.win
        ready = win.journey is not None
        self.journey_error.setVisible(not ready)
        kit.set_inert(self.journey_row, not ready)
        self.journey_next = None
        if not ready:
            self.journey_error.text.setText("%s\n%s" % (win.journey_error, FIX_HINT))
            self.journey_row.set_second("기록을 읽지 못했습니다.")
            self.journey_row.set_metric(None, None, "")
            return None
        overview = win.journey.overview()
        last = win.settings.value("journey/last", "", type=str)
        self.journey_next = journey_text.next_item(win.journey, last, overview)
        detail = journey_text.track_line(overview, self.journey_next)
        self.journey_row.set_second(detail.partition(" · ")[2] or detail)
        self.journey_row.set_metric(overview["passed"], overview["total"], "통과한 문제")
        return overview

    def show_web(self):
        """웹 면접 준비 줄. 웹 기록을 읽지 못했으면 이유를 띠로 보이고 줄을 끄고 None 을, 아니면 웹 서비스의 overview 를 돌려줌."""
        win = self.win
        if "web" not in study.ENTRY_TRACKS:
            self.web_error.hide()
            return None
        overview, error = None, win.web_error
        if win.web is not None:
            try:
                overview = win.web.overview()
            except (WebError, RecordError) as caught:
                error = str(caught)
        ready = overview is not None
        self.web_error.setVisible(not ready)
        kit.set_inert(self.web_row, not ready)
        if not ready:
            self.web_error.text.setText("%s\n%s" % (error, FIX_HINT))
            self.web_row.set_second("기록을 읽지 못했습니다.")
            self.web_row.set_metric(None, None, "")
            return None
        due = [c for c in overview["today"]["chains"] if not c["new"]]
        fresh = len(overview["today"]["chains"]) - len(due)
        parts = ["복습 %d개" % len(due) if due or not fresh else "새 학습 %d개" % fresh]
        state, text = web_text.stack_status(overview["stack"])
        if state != "ready":
            parts.append("설정 필요")
        self.web_row.set_second(" · ".join(parts))
        self.web_row.set_metric(overview["done_missions"], overview["ready_missions"], "완료한 미션")
        return overview

    def show_ai(self):
        """AI 비전 개론 줄. 기록이나 은행 목록을 읽지 못했으면 이유를 띠로 보이고 줄을 끄고 None 을, 아니면 서비스의 overview 를 돌려줌."""
        win = self.win
        overview, error = None, win.ai_error
        if win.ai is not None:
            try:
                overview = win.ai.hub_overview()
            except (SessionError, RecordError) as caught:
                error = str(caught)
        ready = overview is not None
        self.ai_error.setVisible(not ready)
        kit.set_inert(self.ai_row, not ready)
        if not ready:
            self.ai_error.text.setText("%s\n%s" % (error, FIX_HINT))
            self.ai_row.set_second("기록을 읽지 못했습니다.")
            self.ai_row.set_metric(None, None, "")
            return None
        self.ai_row.set_second(ai_text.track_line(overview))
        self.ai_row.set_metric(overview["memorised"], overview["families"], "복습 확인")
        return overview

    def show_next(self, overview, journey, web, ai=None):
        """이어서 할 일 카드와 요약을 채움. 마지막 활동이 AI이면 저장한 학습·연습을 먼저 엶.
        다른 경우에는 웹의 진행 중 미션·복습과 최근 트랙 순서를 따름."""
        if "web" not in study.ENTRY_TRACKS:
            web = None
        running = [m for m in (web["missions"] if web else []) if m["phase"] in ("reading", "live")]
        due = [c for c in (web["today"]["chains"] if web else []) if not c["new"]]
        parts = []
        if running:
            parts.append("진행 중인 미션 %d개" % len(running))
        if due:
            parts.append("오늘 복습 %d개" % len(due))
        if ai and ai["due"]:
            parts.append("AI 복습 %d개" % ai["due"])
        self.summary.setText("%s가 있습니다." % "와 ".join(parts) if parts else "공부할 과목을 고르거나 이어서 진행하세요.")
        web_item = web_text.next_item(web, self.win.web.missions) if web else None
        latest = []
        gradings = python_gradings(self.win.session.prof["attempts"])
        if gradings:
            latest.append((gradings[-1][0], "python"))
        if journey and journey["recent"]:
            latest.append((str(journey["recent"][0]["at"] or ""), "journey"))
        if web and web["activity"]:
            latest.append((str(web["activity"][-1]), "web"))
        if ai and ai["last_at"]:
            latest.append((str(ai["last_at"]), "ai"))
        ai_item = ai_text.next_item(ai, self.win.ai.today()) if ai else None
        first = [track for _, track in sorted(latest, reverse=True)
                 if (track == "web" and (running or due) and web_item)
                 or (track == "ai" and "continuation" not in ai and ai["due"] >= ai_service.REVIEW_FIRST)]
        if (running or due) and web_item and "web" not in first:
            first.insert(0, "web")
        order = first + [track for _, track in sorted(latest, reverse=True)] + ["python"]
        if latest and max(latest)[1] == "ai" and ai_item and ai_item["action"]:
            order.insert(0, "ai")
        for track in order:
            if track == "python":
                label, desc = self.win.next_action(overview)
                name, action = split_action(label)
                self.set_next(name, "파이썬 스터디 · %s" % first_sentence(desc), action, self.start_python)
                return
            if track == "journey" and journey and self.journey_next:
                target = self.journey_next
                self.set_next(target["title"], "알고리즘 여행 · %s" % target["place"], target["action"],
                              lambda did=target["did"], pid=target["pid"]: self.win.open_problem(did, pid))
                return
            if track == "web" and web_item:
                opener = {"mission": self.win.open_mission, "page": self.win.open_learn}.get(web_item["kind"], self.win.open_drill)
                self.set_next(web_item["title"], "웹 면접 준비 · %s" % web_item["line"], web_item["action"],
                              lambda f=opener, iid=web_item["id"]: f(iid))
                return
            if track == "ai" and ai_item and ai_item["action"]:
                self.set_next(ai_item["title"], "%s · %s" % (ai_text.TRACK, ai_item["line"]), ai_item["action"],
                              lambda item=ai_item: self.open_ai(item))
                return

    def open_ai(self, item):
        """저장한 AI 학습 단계나 연습 묶음을 엶. 예전 추천 값도 기존 화면으로 연결함."""
        if item["kind"] == "unit":
            self.win.open_ai_unit(item["lesson"], item["unit"], item.get("step"))
        elif item["kind"] == "practice":
            self.win.open_ai_practice(item["mode"], lesson=item.get("lesson"), unit=item.get("unit"), card=item.get("card"))
        elif item["kind"] in ("review", "again"):
            self.win.open_ai_practice("review")
        elif item["kind"] == "revisit":
            self.win.open_ai_revisit()
        else:
            self.win.go_ai()

    def start_python(self):
        """파이썬 스터디 홈을 거쳐 회차를 엶. 홈을 거쳐야 area 가 python 이 되어 문제 받기 뒤에도 그쪽에 머묾."""
        self.win.go_home()
        if self.win.pages.currentWidget() is self.win.home:
            self.win.start_next()

    def set_next(self, title, line, action, target):
        self.next_card.set_item(title, line, action)
        self.target = target

    def open_next(self):
        if self.target is not None:
            self.target()

    def show_week(self, overview, journey, web=None, ai=None):
        """막대, 연속 학습일, 최근 채점. overview 는 파이썬 쪽, journey·web·ai 는 여행·웹·AI 쪽 overview(읽지 못했으면 None).
        웹 막대는 검사 한 번과 끝낸 사슬 하나를 1 로 세고(activity_counts), 연속 학습일은 검사나 드릴 기록이 있는 날(activity)로 셈.
        AI 막대는 끝낸 연습 묶음, 끝까지 읽은 단원, 제출한 모의고사를 1 로 셈(달력 날짜)."""
        gradings = python_gradings(self.win.session.prof["attempts"])
        python = {}
        for at, _ in gradings:
            python[at[:10]] = python.get(at[:10], 0) + 1
        activity = journey["activity"] if journey else {}
        web_days = set(web["activity"] if web else [])
        web_counts = web["activity_counts"] if web else {}
        ai_counts = ai["activity_counts"] if ai else {}
        today = datetime.date.today()
        days = [today - datetime.timedelta(days=back) for back in range(DAYS - 1, -1, -1)]
        self.chart.set_days((day, python.get(day.isoformat(), 0), activity.get(day.isoformat(), 0), web_counts.get(day.isoformat(), 0),
                             ai_counts.get(day.isoformat(), 0)) for day in days)
        self.total.setText("기록된 활동 %d회" % sum(sum(values) for _, *values in self.chart.days))
        self.total.setToolTip("채점 기록과 AI 단원 읽기·연습·모의고사 완료를 셉니다.")
        streak, day = 0, today
        while python.get(day.isoformat()) or activity.get(day.isoformat()) or day.isoformat() in web_days or ai_counts.get(day.isoformat()):
            streak += 1
            day -= datetime.timedelta(days=1)
        self.streak.setText("연속 학습 %d일" % streak)
        titles = {r["id"]: r["title"] for r in overview["rounds"]}
        rows = [(at, "파이썬 스터디 %s" % titles.get(rid, rid)) for at, rid in gradings[-RECENT:]]
        for entry in (journey["recent"] if journey else []):
            rows.append((str(entry["at"] or ""), "%s %s %s점" % (entry["no"], journey_text.LANG_LABEL.get(entry["lang"], entry["lang"]),
                                                               journey_text.whole_score(entry["score"]))))
        for entry in (ai["recent"] if ai else []):
            rows.append((str(entry["at"] or ""), ai_text.recent_label(entry)))
        rows.sort(key=lambda row: row[0], reverse=True)
        self.recent.set_rows((label, stamp(at)) for at, label in rows[:RECENT])
        self.recent_box.setVisible(bool(rows))
        self.week.arrange()

    def restyle(self):
        self.user.setFixedWidth(min(ACCOUNT_WIDTH, self.user.sizeHint().width()))
        self.settings_panel.restyle()
        for widget in (self.chart, self.recent):
            widget.update()
        self.week.arrange()  # 글자 크기가 바뀌면 최근 채점 줄의 폭과 나란히 둘 폭이 바뀜

    def set_busy(self, busy, text=""):
        self.next_btn.setEnabled(not busy)
        kit.set_inert(self.python_row, busy)
        kit.set_inert(self.journey_row, busy or self.win.journey is None)
        kit.set_inert(self.web_row, busy or self.web_error.isVisibleTo(self))
        kit.set_inert(self.ai_row, busy or self.ai_error.isVisibleTo(self))
        for _, row in self.note_rows:
            kit.set_inert(row, busy)
        for button in (self.git_btn, self.sync_btn):
            button.setEnabled(not busy and self.win.gitflow is not None)
        self.refresh_submission(busy=busy)
        self.settings_panel.refresh_actions(busy)
        self.busy_bar.setVisible(busy)
        self.status.setVisible(busy and bool(text))
        self.status.setText(text if busy else "")
        if not busy:
            QTimer.singleShot(0, self.win.show_hub_tour)
