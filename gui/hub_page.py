# -*- coding: utf-8 -*-
"""첫 화면(허브): 파이썬 스터디와 알고리즘 여행 카드 · 두 쪽을 합친 최근 7일 학습 · 제출.

카드의 수치는 두 서비스가 계산한 값을 그대로 보여 줌(파이썬은 session.overview, 여행은 journey.service 의 overview).
막대의 파이썬 채점 수는 시도 기록에서 서로 다른 (회차, 시각) 쌍의 수임. 회차를 한 번 채점하면 문항마다 같은 시각의 시도가
하나씩 남아서, 시도 수를 그대로 세면 여행 채점 한 번(1)과 견줄 수 없음."""
import datetime
import html

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget

from gui import errors, motion, theme
from gui.home_page import card, muted
from gui.journey_page import LANG_LABEL
from gui.mascot import Mascot
from gui.widgets import LinkLabel, Para

DAYS = 7  # 막대로 보이는 날 수(오늘 포함)
RECENT = 5  # 최근 채점 줄 수
WEEKDAYS = "월화수목금토일"
SERIES = (("ok", "파이썬 스터디"), ("primary", "알고리즘 여행"))  # 막대 색과 범례. 날마다 이 순서로 나란히 그림


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


class EntryCard(QFrame):
    """파이썬 스터디·알고리즘 여행으로 들어가는 큰 카드. 카드 어디를 눌러도 button 을 누른 것과 같고, 단추가 꺼져 있으면 아무 일도 없음."""

    def __init__(self, title, button):
        super().__init__()
        self.setObjectName("card")
        self.button, self.down = button, False
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(18, 12, 18, 14)
        self.box.setSpacing(6)
        head = QLabel(title)
        head.setObjectName("h2")
        self.box.addWidget(head)

    def finish(self):
        """내용을 다 넣은 뒤 아래쪽 오른편에 단추를 둠."""
        self.box.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.button)
        self.box.addLayout(row)

    def sync(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.button.isEnabled() else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        self.down = event.button() == Qt.MouseButton.LeftButton
        event.accept()

    def mouseReleaseEvent(self, event):
        down, self.down = self.down, False
        if down and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()) \
                and self.button.isEnabled():
            self.button.click()


class WeekChart(QWidget):
    """최근 7일의 날짜별 채점 수. 날마다 파이썬(ok)과 알고리즘(primary) 막대를 나란히 그리고, 바탕은 track 색."""

    def __init__(self):
        super().__init__()
        self.days = []  # [(날짜, 파이썬 채점 수, 알고리즘 채점 수)], 오늘이 마지막
        self.setMinimumHeight(170)

    def set_days(self, days):
        self.days = list(days)
        self.setToolTip("\n".join("%d/%d(%s) 파이썬 %d · 알고리즘 %d" % (day.month, day.day, WEEKDAYS[day.weekday()], python, journey)
                                  for day, python, journey in self.days))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        line = self.fontMetrics().height()
        legend_top = self.height() - line
        label_top = legend_top - line - 10
        top, bottom = 4.0, label_top - 4.0
        span = max(1.0, bottom - top)
        peak = max([1] + [max(python, journey) for _, python, journey in self.days])
        column = self.width() / max(1, len(self.days))
        bar = max(4.0, min(14.0, column / 4))
        for number, (day, python, journey) in enumerate(self.days):
            middle = column * (number + 0.5)
            painter.setPen(Qt.PenStyle.NoPen)
            for left, value, token in ((middle - bar - 1.5, python, SERIES[0][0]), (middle + 1.5, journey, SERIES[1][0])):
                painter.setBrush(theme.qcolor("track"))
                painter.drawRoundedRect(QRectF(left, top, bar, span), 3, 3)
                if value:
                    filled = max(4.0, span * value / peak)
                    painter.setBrush(theme.qcolor(token))
                    painter.drawRoundedRect(QRectF(left, bottom - filled, bar, filled), 3, 3)
            painter.setPen(theme.qcolor("heading" if number == len(self.days) - 1 else "muted"))
            painter.drawText(QRectF(column * number, label_top, column, line + 6), Qt.AlignmentFlag.AlignCenter, WEEKDAYS[day.weekday()])
        left = 0.0
        for token, label in SERIES:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor(token))
            painter.drawRoundedRect(QRectF(left, legend_top + (line - 10) / 2, 10, 10), 2, 2)
            width = self.fontMetrics().horizontalAdvance(label) + 2
            painter.setPen(theme.qcolor("muted"))
            painter.drawText(QRectF(left + 15, legend_top, width, line), Qt.AlignmentFlag.AlignVCenter, label)
            left += 15 + width + 18


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
        root.setContentsMargins(24, 16, 24, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("프로그래밍 스터디")
        title.setObjectName("h1")
        self.user = QLabel()
        self.user.setObjectName("muted")
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("quiet")
        self.theme_btn.setToolTip("누를 때마다 시스템 → 밝게 → 어둡게 순서로 바뀝니다. 시스템은 운영체제 설정을 따릅니다.")
        head.addWidget(Mascot(34))
        head.addSpacing(4)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.user)
        head.addSpacing(8)
        head.addWidget(self.theme_btn)
        root.addLayout(head)
        self.notice = LinkLabel()
        self.notice.setObjectName("notice")  # refresh 가 html.escape 한 글을 넣음
        self.notice.linkActivated.connect(lambda _: win.show_notice_detail())
        self.notice.hide()
        root.addWidget(self.notice)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.python_btn = QPushButton("파이썬 스터디 들어가기")
        self.python_card = EntryCard("파이썬 스터디", self.python_btn)
        line = QHBoxLayout()
        self.ready = QLabel()
        self.ready.setObjectName("ready")
        self.ready_bar = QProgressBar()
        self.ready_bar.setRange(0, 100)
        self.ready_bar.setTextVisible(False)
        self.mastered = QLabel()
        line.addWidget(self.ready)
        line.addSpacing(12)
        line.addWidget(self.ready_bar, 1)
        line.addSpacing(12)
        line.addWidget(self.mastered)
        self.python_card.box.addLayout(line)
        self.python_next = muted()
        self.python_last = muted()
        self.python_card.box.addWidget(self.python_next)
        self.python_card.box.addWidget(self.python_last)
        self.python_card.finish()

        self.journey_btn = QPushButton("여행 떠나기")
        self.journey_card = EntryCard("알고리즘 여행", self.journey_btn)
        self.journey_passed = QLabel()
        self.journey_langs = muted()
        self.journey_next = muted()
        self.journey_error = Para(name="error")
        for widget in (self.journey_passed, self.journey_langs, self.journey_next, self.journey_error):
            self.journey_card.box.addWidget(widget)
        self.journey_card.finish()
        for button in (self.python_btn, self.journey_btn):
            button.setObjectName("primary")
            button.setProperty("big", True)
            button.setMinimumHeight(46)
        self.python_card.sync()
        self.journey_card.sync()
        cards.addWidget(self.python_card, 1)
        cards.addWidget(self.journey_card, 1)
        root.addLayout(cards)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        week_card, box = card("최근 7일 학습")
        self.chart = WeekChart()
        self.streak = QLabel()
        self.recent = muted()
        box.addWidget(self.chart)
        box.addWidget(self.streak)
        box.addWidget(self.recent)
        box.addStretch(1)
        git_card, box = card("제출")
        row = QHBoxLayout()
        self.git_btn = QPushButton("제출(PR 올리기)")
        self.sync_btn = QPushButton("문제 받기")
        row.addWidget(self.git_btn, 1)
        row.addWidget(self.sync_btn, 1)
        self.git_hint = muted()
        self.status = muted()
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.hide()
        box.addLayout(row)
        box.addWidget(self.git_hint)
        box.addWidget(self.status)
        box.addWidget(self.busy_bar)
        box.addStretch(1)
        bottom.addWidget(week_card, 3)
        bottom.addWidget(git_card, 2)
        root.addLayout(bottom)
        root.addStretch(1)  # 창이 크면 카드를 늘리지 않고 아래를 비움

        self.foot = LinkLabel('글자 크기: Ctrl(맥은 Cmd) 과 +, -, 0 · <a href="%s">불편한 점 신고하기</a>' % errors.ISSUE_URL)
        self.foot.setObjectName("muted")
        self.foot.setOpenExternalLinks(True)
        root.addWidget(self.foot)

        self.theme_btn.clicked.connect(win.cycle_theme)
        self.python_btn.clicked.connect(win.go_home)
        self.journey_btn.clicked.connect(lambda: win.go_journey())
        self.git_btn.clicked.connect(win.submit_pr)
        self.sync_btn.clicked.connect(win.fetch_problems)

    def refresh(self):
        win = self.win
        overview = win.session.overview()
        self.user.setText("ID: %s" % overview["user"])
        motion.count_text(self.ready, "%d%%", overview["readiness"])
        motion.count(self.ready_bar, overview["readiness"], self.ready_bar.setValue)
        self.mastered.setText("숙달한 단원 %d / %d" % (overview["mastered"], overview["total_units"]))
        self.python_next.setText("지금 할 일: %s" % win.next_action(overview)[0])
        done = [r for r in overview["rounds"] if r["completed"]]
        if done:
            last = done[-1]
            earned, total = (int(n) for n in (last["first_score"] or last["score"]).split("/"))
            self.python_last.setText("지난 회차: %s 첫 채점 %d / %d점" % (last["title"], earned, total))
        else:
            self.python_last.setText("아직 제출한 회차가 없습니다.")
        journey = self.show_journey()
        self.show_week(overview, journey)
        usable = win.gitflow is not None
        self.git_btn.setEnabled(usable)
        self.sync_btn.setEnabled(usable)
        self.git_hint.setText("제출: 내 풀이 폴더를 올리고 브라우저에서 PR 페이지를 엽니다.\n문제 받기: 새로 올라온 문제를 내려받습니다. 내 풀이는 바꾸지 않습니다."
                              if usable else "지금은 제출과 문제 받기를 쓸 수 없습니다. 풀이와 채점은 계속할 수 있습니다.\n" + win.git_reason)
        note = win.notice
        self.notice.setVisible(bool(note))
        if note:
            more = ' <a href="detail">자세히</a>' if note.get("detail") else ""
            self.notice.setText(html.escape(note.get("message") or "") + more)

    def show_journey(self):
        """알고리즘 여행 카드. 여행 기록을 읽지 못했으면 이유를 보이고 단추를 끄고 None 을, 아니면 여행 서비스의 overview 를 돌려줌."""
        win = self.win
        ready = win.journey is not None
        for widget in (self.journey_passed, self.journey_langs, self.journey_next):
            widget.setVisible(ready)
        self.journey_error.setVisible(not ready)
        self.journey_btn.setEnabled(ready)
        self.journey_card.sync()
        if not ready:
            self.journey_error.setText("%s\n파일을 고친 뒤 프로그램을 다시 실행해 주세요." % win.journey_error)
            return None
        overview = win.journey.overview()
        self.journey_passed.setText("통과 %d / %d · 보스 %d / %d" % (overview["passed"], overview["total"], overview["cleared"],
                                                                   overview["ready"]))
        self.journey_langs.setText(" · ".join("%s %d" % (label, overview["by_lang"].get(lang, 0)) for lang, label in LANG_LABEL.items()))
        target = overview["next"]
        if target:
            self.journey_next.setText("다음 추천: %s %s" % (target["no"], target["title"]))
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
        lines = ["%s · %s" % (label, stamp(at)) for at, label in rows[:RECENT]]
        self.recent.setText("최근 채점\n" + "\n".join(lines) if lines else "아직 채점한 기록이 없습니다.")

    def restyle(self):
        self.theme_btn.setText("테마: %s" % theme.MODES[theme.state["mode"]])
        self.chart.update()

    def set_busy(self, busy, text=""):
        self.python_btn.setEnabled(not busy)
        self.journey_btn.setEnabled(not busy and self.win.journey is not None)
        for widget in (self.git_btn, self.sync_btn):
            widget.setEnabled(not busy and self.win.gitflow is not None)
        for entry in (self.python_card, self.journey_card):
            entry.sync()
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")
