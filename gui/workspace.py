# -*- coding: utf-8 -*-
"""과목 이동, 과목별 현황 카드와 제출 작업 영역을 공통으로 배치함."""
from PyQt6.QtCore import QEvent, QSignalBlocker, QSize
from PyQt6.QtWidgets import QComboBox, QFrame, QGridLayout, QLayout, QSizePolicy, QWidget

from gui import kit, theme

SUBJECTS = (("hub", "학습 현황", "go_hub"), ("python", "파이썬", "go_home"),
            ("journey", "알고리즘", "go_journey"), ("web", "웹 면접", "go_web"), ("ai", "AI 비전", "go_ai"))


class SubjectTile(kit.Row):
    """과목 이름·학습 현황·다음 행동을 한 영역에 모음. 키보드와 클릭은 목록 줄의 동작을 유지함."""

    def __init__(self, title, token):
        super().__init__(title, "", mark=kit.Dot(token, 10), strong=True, wrap=True)
        self.setProperty("subject", True)
        self.setAccessibleName(title + " 학습 열기")
        kit.typed(self.title, "headline", True)
        kit.typed(self.second, "body")
        self.second.setProperty("tone", "secondary")
        text_box = self.title.parentWidget().layout()
        text_box.setSpacing(theme.GAP["title_description"])
        self.metric = kit.label("", "caption", "secondary")
        self.meter = kit.progress(thin=True)
        self.meter.setProperty("series", token)
        text_box.addSpacing(12)
        text_box.addWidget(self.metric)
        text_box.addSpacing(4)
        text_box.addWidget(self.meter)
        self.set_metric(None, None, "")

    def set_metric(self, count, total, name):
        known = count is not None and total is not None
        self.metric.setText("%s %d / %d" % (name, count, total) if known else "현황을 확인하지 못했습니다.")
        self.meter.setVisible(known and total > 0)
        if known:
            self.meter.setRange(0, max(1, total))
            self.meter.setValue(count)
        self.fit_height()

    def fit_height(self):
        text = self.title.parentWidget()
        row = self.layout()
        others = [row.itemAt(i) for i in range(row.count())
                  if row.itemAt(i).widget() is not None and row.itemAt(i).widget() is not text
                  and not row.itemAt(i).widget().isHidden()]
        left, _, right, _ = row.getContentsMargins()
        width = max(1, self.contentsRect().width() - left - right - sum(item.sizeHint().width() for item in others)
                    - row.spacing() * len(others))
        height = text.layout().heightForWidth(width)
        self.setFixedHeight(max(160 + theme.text_px() * 4, height + 2 * self.frameWidth()))

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest and hasattr(self, "metric"):
            self.fit_height()
        return result


class SubjectGrid(QWidget):
    """창의 폭에 따라 두 열과 한 열 사이에서 배치를 바꿈."""

    def __init__(self):
        super().__init__()
        self.rows, self.columns = [], 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)

    def add(self, tile):
        self.rows.append(tile)
        self.columns = 0
        self.arrange()
        return tile

    def arrange(self):
        columns = 2 if self.width() >= theme.TYPE["body"][0] * 32 else 1
        if columns == self.columns:
            return
        self.columns = columns
        for index, tile in enumerate(self.rows):
            self.grid.addWidget(tile, index // columns, index % columns)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, int(columns == 2))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def refont(self):
        self.arrange()


class SubmissionBar(QFrame):
    """화면을 스크롤해도 제출 버튼과 알림을 같은 위치에 둠."""

    def __init__(self, win):
        super().__init__()
        self.setObjectName("submissionbar")
        self.setProperty("ui", "2")
        self.row = kit.box(self, (24, 16, 24, 16), 16, horizontal=True)
        self.message = kit.para("제출할 내용을 확인하고 있습니다.", "caption", "secondary")
        self.row.addWidget(self.message, 1)
        self.submit = kit.button("풀이 제출", "secondary", "l")
        self.submit.setObjectName("submit_work")
        self.submit.setAccessibleDescription("아직 올리지 않은 풀이와 학습 기록을 제출합니다.")
        self.submit.clicked.connect(win.submit_pr)
        self.submit.hide()
        self.sync = kit.button("새 문제 받기", "secondary", "l")
        self.sync.clicked.connect(win.fetch_problems)
        self.row.addWidget(self.submit)
        self.row.addWidget(self.sync)
        self.state, self.busy, self.usable = {}, False, False

    def refresh(self, state, usable, busy=False):
        self.state, self.usable, self.busy = state, usable, busy
        pending = state.get("status") == "ok" and state.get("pending", False)
        self.submit.setVisible(usable and pending)
        self.submit.setEnabled(usable and not busy)
        self.sync.setEnabled(usable and not busy)
        if not usable:
            text = "제출과 문제 받기를 사용할 수 없습니다."
        elif busy:
            text = "작업이 끝나면 제출 현황을 갱신합니다."
        elif pending:
            text = "제출할 풀이가 있습니다."
        elif state.get("status") == "ok":
            text = "아직 제출하지 않은 변경이 없습니다."
        elif state.get("status") == "checking":
            text = "제출할 내용을 확인하고 있습니다."
        else:
            text = "제출할 내용을 확인하지 못했습니다. 새 문제를 받은 뒤 다시 확인합니다."
        self.message.setText(text)
        kit.set_tone(self.message, "accent" if pending else "secondary")
        self.arrange()

    def arrange(self):
        need = self.message.minimumSizeHint().width() + self.sync.sizeHint().width() + 80
        if not self.submit.isHidden():
            need += self.submit.sizeHint().width() + 16
        vertical = self.width() < max(680, need)
        self.row.setDirection(self.row.Direction.TopToBottom if vertical else self.row.Direction.LeftToRight)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def refont(self):
        self.arrange()


class Workspace(QWidget):
    """넓은 창은 왼쪽 과목 목록, 좁은 창은 위 선택란에서 같은 화면으로 이동함."""

    def __init__(self, win, pages):
        super().__init__()
        self.win, self.pages = win, pages
        self.overview_pages = (win.hub, win.home, win.journey_map, win.web_home, win.ai_home, win.ai_lesson)
        self.submission_pages = (*self.overview_pages, win.result_page)
        self.setObjectName("page")
        outer = kit.box(self, horizontal=True)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.rail = QFrame()
        self.rail.setObjectName("navigation")
        self.rail.setProperty("ui", "2")
        self.rail.setFixedWidth(188)
        nav = kit.box(self.rail, (16, 24, 16, 24), 8)
        nav.addWidget(kit.label("프로그래밍\n스터디", "headline", bold=True))
        nav.addSpacing(32)
        nav.addWidget(kit.label("내 공부", "caption", "tertiary"))
        self.buttons = {}
        for tid, title, action in SUBJECTS:
            button = kit.button(title, "text", "l")
            button.setProperty("navigation", True)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, action=action: self.navigate(action))
            self.buttons[tid] = button
            nav.addWidget(button)
        nav.addStretch(1)
        outer.addWidget(self.rail)
        body = QWidget()
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        box = kit.box(body)
        self.compact = QComboBox()
        self.compact.setObjectName("subject_picker")
        self.compact.setAccessibleName("학습 과목 이동")
        for tid, title, action in SUBJECTS:
            self.compact.addItem(title, action)
        self.compact.setMinimumHeight(48)
        self.compact.activated.connect(lambda index: self.navigate(self.compact.itemData(index)))
        box.addWidget(self.compact)
        box.addWidget(pages, 1)
        self.submissions = SubmissionBar(win)
        box.addWidget(self.submissions)
        outer.addWidget(body, 1)
        pages.currentChanged.connect(self.refresh)
        self.refresh()

    def minimumSizeHint(self):
        """넓은 창의 이동 목록 때문에 좁은 배치로 줄일 수 없게 되는 것을 막음."""
        return QSize(760, 480)

    def navigate(self, action):
        getattr(self.win, action)()
        self.refresh()

    def refresh(self, *_):
        started = self.win.session is not None and self.pages.currentWidget() is not self.win.start
        overview = self.pages.currentWidget() in self.overview_pages
        self.rail.setVisible(started and overview and self.width() >= 1120)
        self.compact.setVisible(started and overview and self.width() < 1120)
        self.submissions.setVisible(started and self.pages.currentWidget() in self.submission_pages)
        for index, (tid, _, _) in enumerate(SUBJECTS):
            self.buttons[tid].setChecked(self.win.area == tid)
            if self.win.area == tid:
                blocker = QSignalBlocker(self.compact)
                self.compact.setCurrentIndex(index)
                del blocker
        busy = self.win.job is not None or self.win.pending_close
        self.rail.setEnabled(not busy)
        self.compact.setEnabled(not busy)
        self.submissions.refresh(self.win.pending_submission, self.win.gitflow is not None, busy)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()
