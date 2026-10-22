# -*- coding: utf-8 -*-
"""첫 화면(허브): 위 막대(이름, ID, 테마 단추), 제목 "오늘 할 공부", 이어서 할 일 카드 하나(화면에 하나뿐인 주 단추), 공부 트랙 줄 셋,
최근 7일 학습 카드, 제출 줄 둘, 바닥글. 960 폭의 가운데 단에 두고 창이 작으면 스크롤함.

카드의 수치는 세 서비스가 계산한 값을 그대로 보여 줌(파이썬은 session.overview, 여행은 journey.service, 웹은 webprep.service 의 overview).
막대의 파이썬 채점 수는 시도 기록에서 서로 다른 (회차, 시각) 쌍의 수임. 회차를 한 번 채점하면 문항마다 같은 시각의 시도가
하나씩 남아서, 시도 수를 그대로 세면 여행 채점 한 번(1)과 견줄 수 없음.
이어서 할 일은 웹의 진행 중 미션이나 오늘 복습이 있으면 그것, 아니면 가장 최근에 기록을 남긴 트랙의 다음 할 일, 기록이 없으면 파이썬 스터디의
다음 회차임. 막대와 최근 채점 줄은 칠할 때마다 지금 테마의 색을 읽음."""
import datetime
import html
import math

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QFontMetricsF, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from gui import errors, kit, theme, web_text
from gui.journey_page import LANG_LABEL
from gui.mascot import Mascot
from gui.widgets import LinkLabel
from webprep.record import RecordError
from webprep.service import WebError

DAYS = 7  # 막대로 보이는 날 수(오늘 포함)
RECENT = 5  # 최근 채점 줄 수
WEEKDAYS = "월화수목금토일"
TRACKS = (("python", "파이썬"), ("journey", "알고리즘"), ("web", "웹 면접"))  # 막대 순서와 범례 이름. 트랙 색(theme.SERIES)도 이 순서
BAR_GAP = 2  # 한 날의 막대 사이
EMPTY = "아직 채점한 기록이 없습니다."
THEME_TEXT = {"system": "밝게 보기", "light": "어둡게 보기", "dark": "시스템 따르기"}  # 단추를 누르면 바뀌는 쪽(시스템 → 밝게 → 어둡게 → 시스템)
PYTHON_ABOUT = "파이썬 교과목 평가에 나오는 문제를 회차로 나눠 풀고 채점합니다."
FIX_HINT = "파일을 고친 뒤 프로그램을 다시 실행해 주세요."


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
        self.setFont(theme.font("label"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_rows(self, rows):
        self.rows = list(rows)
        self.setFixedHeight(self.line_height() * len(self.rows))
        self.setToolTip("\n".join("%s · %s" % row for row in self.rows))
        self.update()

    @staticmethod
    def line_height():
        return theme.TYPE["body"][1]

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
    """최근 7일의 날짜별 학습 수. 날마다 파이썬, 알고리즘, 웹 막대를 트랙 색(theme.SERIES)으로 TRACKS 순서로 나란히 그리고, 바탕은 track 색.
    기록이 없는 날의 바탕은 옅게 그리고, 7일 모두 없으면 막대 자리 가운데에 EMPTY 를 씀.
    막대 아래에 요일과 날짜를 micro 13 으로 쓰고 오늘은 굵게 씀. 하루 칸이 좁아 날짜(10/15)끼리 붙으면 날만(15) 씀. 범례는 카드 머리줄에 있음."""

    def __init__(self):
        super().__init__()
        self.days = []  # [(날짜, 파이썬 채점 수, 알고리즘 채점 수, 웹 검사·드릴 수)], 오늘이 마지막
        self.setMinimumHeight(136)

    def set_days(self, days):
        self.days = list(days)
        self.setToolTip("\n".join("%d/%d(%s) 파이썬 %d · 알고리즘 %d · 웹 %d" % (day.month, day.day, WEEKDAYS[day.weekday()], python, journey, web)
                                  for day, python, journey, web in self.days))
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
            text = QFontMetricsF(theme.font("caption")).boundingRect(area, Qt.AlignmentFlag.AlignCenter, EMPTY)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("surface"))
            painter.drawRoundedRect(text.adjusted(-16, -8, 16, 8), 8, 8)  # 바탕 막대 위에 글이 겹치지 않게 바탕색 알약을 깔음
            painter.setPen(theme.qcolor("muted"))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, EMPTY)


class HubPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.target = None  # 이어서 할 일 카드의 단추가 여는 것: 부르면 화면을 여는 함수
        outer = kit.box(self)

        top = kit.TopBar(plain=True)
        self.theme_btn = kit.button("", "text", "s", onbg=True)
        self.theme_btn.setToolTip("누를 때마다 시스템 → 밝게 → 어둡게 순서로 바뀝니다. 시스템은 운영체제 설정을 따릅니다.")
        self.user = kit.label("", "caption", "tertiary")
        top.row.addWidget(Mascot(32))
        top.row.addWidget(kit.label("프로그래밍 스터디", "headline"))
        top.row.addStretch(1)
        top.row.addWidget(self.user)
        top.add_right(self.theme_btn, flush=True)
        outer.addWidget(top)

        inner = QWidget()
        root = kit.box(inner, (0, 24, 0, 48))
        root.addWidget(kit.label("오늘 할 공부", "title"))
        root.addSpacing(4)
        self.summary = kit.para("", "body", "secondary")
        root.addWidget(self.summary)
        root.addSpacing(32)
        self.notice_banner, self.notice = kit.link_banner("warning")  # refresh 가 html.escape 한 글을 넣음
        self.notice.linkActivated.connect(lambda _: win.show_notice_detail())
        self.notice_banner.hide()
        self.next_card = kit.NextCard()
        self.next_btn = self.next_card.button
        lead = QWidget()  # 알림 띠가 보이면 카드와 16 띄움. 숨은 띠 옆에는 간격이 생기지 않음
        lead_box = kit.box(lead, spacing=16)
        lead_box.addWidget(self.notice_banner)
        lead_box.addWidget(self.next_card)
        root.addWidget(lead)
        root.addSpacing(48)

        cols = QHBoxLayout()
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(24)
        left = QWidget()
        left_box = kit.box(left)
        head, _, _ = kit.section("공부 트랙")
        left_box.addLayout(head)
        left_box.addSpacing(12)
        self.tracks = kit.RowList()
        self.python_row = self.tracks.add(kit.Row("파이썬 스터디", PYTHON_ABOUT, mark=kit.Dot("series_python", 8), strong=True))
        self.journey_row = self.tracks.add(kit.Row("알고리즘 여행", "", mark=kit.Dot("series_algorithm", 8), strong=True))
        self.web_row = self.tracks.add(kit.Row("웹 면접 준비", "", mark=kit.Dot("series_web", 8), strong=True))
        self.journey_error = kit.banner("", "danger")  # 여행 기록을 읽지 못한 이유. 그동안 여행 줄은 눌리지 않음
        self.web_error = kit.banner("", "danger")
        stack = QWidget()  # 목록과 띠 사이 12. 숨은 띠 옆에는 간격이 생기지 않아 띠가 없으면 구역 사이가 48 로 남음
        stack_box = kit.box(stack, spacing=12)
        stack_box.addWidget(self.tracks)
        for banner in (self.journey_error, self.web_error):
            banner.hide()
            stack_box.addWidget(banner)
        left_box.addWidget(stack)
        left_box.addStretch(1)
        right = QWidget()
        right_box = kit.box(right)
        head, _, self.streak = kit.section("최근 7일 학습")
        right_box.addLayout(head)
        right_box.addSpacing(12)
        week_card, box = kit.card(spacing=0)
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
        box.addLayout(legend)
        box.addSpacing(8)
        self.chart = WeekChart()
        box.addWidget(self.chart)
        self.recent_box = QWidget()  # 최근 채점 칸. 채점 기록이 없으면 숨겨서 카드가 막대만 보임
        recent = kit.box(self.recent_box, (0, 16, 0, 0), 4)
        self.recent = RecentList()
        recent.addWidget(kit.label("최근 채점", "caption", "tertiary"))
        recent.addWidget(self.recent)
        box.addWidget(self.recent_box)
        right_box.addWidget(week_card)
        right_box.addStretch(1)
        cols.addWidget(left, 7)
        cols.addWidget(right, 5)
        root.addLayout(cols)
        root.addSpacing(48)

        head, _, _ = kit.section("제출")
        root.addLayout(head)
        root.addSpacing(12)
        self.git = kit.RowList()
        self.git_btn = self.git.add(kit.Row("풀이 제출", "풀이 폴더를 올리고 브라우저에서 PR 페이지를 엽니다."))
        self.sync_btn = self.git.add(kit.Row("새 문제 받기", "새로 올라온 문제를 받습니다. 내 풀이는 바뀌지 않습니다."))
        root.addWidget(self.git)
        self.git_hint = kit.banner("", "warning")  # 제출을 쓸 수 없는 이유. 그동안 두 줄은 눌리지 않음
        self.git_hint.hide()
        root.addSpacing(12)
        root.addWidget(self.git_hint)
        self.status = kit.label("", "caption", "secondary")
        self.status.hide()
        self.busy_bar = kit.progress()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.hide()
        root.addWidget(self.status)
        root.addSpacing(8)
        root.addWidget(self.busy_bar)
        root.addSpacing(24)
        self.foot = LinkLabel('글자 크기는 Ctrl(맥은 Cmd)과 +, -, 0 으로 바꿉니다. <a href="%s">불편한 점 알리기</a>' % errors.ISSUE_URL,
                              line=theme.TYPE["caption"][1], font=theme.font("caption"))
        self.foot.setProperty("tone", "tertiary")
        self.foot.setOpenExternalLinks(True)
        root.addWidget(self.foot)
        column = kit.column(inner)
        column.layout().setContentsMargins(32, 0, 32, 0)
        outer.addWidget(kit.scroll(column), 1)

        self.theme_btn.clicked.connect(win.cycle_theme)
        self.next_btn.clicked.connect(self.open_next)
        self.python_row.clicked.connect(win.go_home)
        self.journey_row.clicked.connect(lambda: win.go_journey())
        self.web_row.clicked.connect(lambda: win.go_web())
        self.git_btn.clicked.connect(win.submit_pr)
        self.sync_btn.clicked.connect(win.fetch_problems)

    def refresh(self):
        win = self.win
        overview = win.session.overview()
        self.user.setText("ID: %s" % overview["user"])
        name, _ = split_action(win.next_action(overview)[0])
        self.python_row.set_second("단원 %d개 중 %d개 숙달 · 다음은 %s" % (overview["total_units"], overview["mastered"], name))
        journey = self.show_journey()
        web = self.show_web()
        self.show_week(overview, journey, web)
        self.show_next(overview, journey, web)
        usable = win.gitflow is not None
        for row in (self.git_btn, self.sync_btn):
            kit.set_inert(row, not usable)
        self.git_hint.setVisible(not usable)
        self.git_hint.text.setText("" if usable else "지금은 제출과 문제 받기를 쓸 수 없습니다. 풀이와 채점은 계속할 수 있습니다.\n" + win.git_reason)
        note = win.notice
        self.notice_banner.setVisible(bool(note))
        if note:
            more = ' <a href="detail">자세히</a>' if note.get("detail") else ""
            self.notice.setText(html.escape(note.get("message") or "") + more)
        self.restyle()

    def show_journey(self):
        """알고리즘 여행 줄. 여행 기록을 읽지 못했으면 이유를 띠로 보이고 줄을 끄고 None 을, 아니면 여행 서비스의 overview 를 돌려줌."""
        win = self.win
        ready = win.journey is not None
        self.journey_error.setVisible(not ready)
        kit.set_inert(self.journey_row, not ready)
        if not ready:
            self.journey_error.text.setText("%s\n%s" % (win.journey_error, FIX_HINT))
            self.journey_row.set_second("기록을 읽지 못했습니다.")
            return None
        overview = win.journey.overview()
        target = overview["next"]
        if target:
            tail = "다음은 %s" % target["title"]
        elif overview["total"]:
            tail = "출제된 던전을 모두 클리어했습니다."
        else:
            tail = "아직 출제된 던전이 없습니다."
        self.journey_row.set_second("%d문제 중 %d개 통과 · %s" % (overview["total"], overview["passed"], tail))
        return overview

    def show_web(self):
        """웹 면접 준비 줄. 웹 기록을 읽지 못했으면 이유를 띠로 보이고 줄을 끄고 None 을, 아니면 웹 서비스의 overview 를 돌려줌."""
        win = self.win
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
            return None
        due = [c for c in overview["today"]["chains"] if not c["new"]]
        fresh = len(overview["today"]["chains"]) - len(due)
        parts = ["미션 %d개 중 %d개 끝남" % (overview["ready_missions"], overview["done_missions"]),
                 "오늘 복습 %d개" % len(due) if due or not fresh else "새 사슬 %d개" % fresh]
        state, text = web_text.stack_status(overview["stack"])
        if state != "ready":
            parts.append(text)
        self.web_row.set_second(" · ".join(parts))
        return overview

    def show_next(self, overview, journey, web):
        """이어서 할 일 카드와 요약 문장. 웹의 진행 중 미션이나 오늘 복습이 먼저, 그다음 가장 최근 기록을 남긴 트랙, 기록이 없으면 파이썬."""
        running = [m for m in (web["missions"] if web else []) if m["phase"] in ("reading", "live")]
        due = [c for c in (web["today"]["chains"] if web else []) if not c["new"]]
        parts = []
        if running:
            parts.append("진행 중인 미션 %d개" % len(running))
        if due:
            parts.append("오늘 복습 %d개" % len(due))
        self.summary.setText("%s가 있습니다." % "와 ".join(parts) if parts else "이어서 할 일을 골라 시작하세요.")
        web_item = web_text.next_item(web, self.win.web.missions) if web else None
        latest = []
        gradings = python_gradings(self.win.session.prof["attempts"])
        if gradings:
            latest.append((gradings[-1][0], "python"))
        if journey and journey["recent"]:
            latest.append((str(journey["recent"][0]["at"] or ""), "journey"))
        if web and web["activity"]:
            latest.append((str(web["activity"][-1]), "web"))
        order = ["web"] if (running or due) and web_item else []
        order += [track for _, track in sorted(latest, reverse=True)] + ["python"]
        for track in order:
            if track == "python":
                label, desc = self.win.next_action(overview)
                name, action = split_action(label)
                self.set_next(name, "파이썬 스터디 · %s" % first_sentence(desc), action, self.start_python)
                return
            if track == "journey" and journey and journey["next"]:
                target = journey["next"]
                there = next((row for row in journey["dungeons"] if row["id"] == target["did"]), None)
                place = " · 던전 %d 「%s」" % (there["no"], there["title"]) if there else ""
                self.set_next(target["title"], "알고리즘 여행%s" % place, "문제 풀기",
                              lambda did=target["did"], pid=target["pid"]: self.win.open_problem(did, pid))
                return
            if track == "web" and web_item:
                opener = {"mission": self.win.open_mission, "page": self.win.open_learn}.get(web_item["kind"], self.win.open_drill)
                self.set_next(web_item["title"], "웹 면접 준비 · %s" % web_item["line"], web_item["action"],
                              lambda f=opener, iid=web_item["id"]: f(iid))
                return

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

    def show_week(self, overview, journey, web=None):
        """막대, 연속 학습일, 최근 채점. overview 는 파이썬 쪽, journey 와 web 은 여행·웹 쪽 overview(읽지 못했으면 None).
        웹은 검사와 드릴 기록이 있는 날을 하루 1 로 셈(overview 의 activity 는 날짜 목록임)."""
        gradings = python_gradings(self.win.session.prof["attempts"])
        python = {}
        for at, _ in gradings:
            python[at[:10]] = python.get(at[:10], 0) + 1
        activity = journey["activity"] if journey else {}
        web_days = {day: 1 for day in (web["activity"] if web else [])}
        today = datetime.date.today()
        days = [today - datetime.timedelta(days=back) for back in range(DAYS - 1, -1, -1)]
        self.chart.set_days((day, python.get(day.isoformat(), 0), activity.get(day.isoformat(), 0), web_days.get(day.isoformat(), 0))
                            for day in days)
        self.total.setText("합계 %d회" % sum(sum(values) for _, *values in self.chart.days))
        streak, day = 0, today
        while python.get(day.isoformat()) or activity.get(day.isoformat()) or web_days.get(day.isoformat()):
            streak += 1
            day -= datetime.timedelta(days=1)
        self.streak.setText("연속 학습 %d일" % streak)
        titles = {r["id"]: r["title"] for r in overview["rounds"]}
        rows = [(at, "파이썬 스터디 %s" % titles.get(rid, rid)) for at, rid in gradings[-RECENT:]]
        for entry in (journey["recent"] if journey else []):
            rows.append((str(entry["at"] or ""), "%s %s %d점" % (entry["no"], LANG_LABEL.get(entry["lang"], entry["lang"]),
                                                               math.floor(entry["score"] or 0.0))))
        rows.sort(key=lambda row: row[0], reverse=True)
        self.recent.set_rows((label, stamp(at)) for at, label in rows[:RECENT])
        self.recent_box.setVisible(bool(rows))

    def restyle(self):
        self.theme_btn.setText(THEME_TEXT[theme.state["mode"]])
        for widget in (self.chart, self.recent):
            widget.update()

    def set_busy(self, busy, text=""):
        self.next_btn.setEnabled(not busy)
        kit.set_inert(self.python_row, busy)
        kit.set_inert(self.journey_row, busy or self.win.journey is None)
        kit.set_inert(self.web_row, busy or self.web_error.isVisibleTo(self))
        for row in (self.git_btn, self.sync_btn):
            kit.set_inert(row, busy or self.win.gitflow is None)
        self.busy_bar.setVisible(busy)
        self.status.setVisible(busy and bool(text))
        self.status.setText(text if busy else "")
