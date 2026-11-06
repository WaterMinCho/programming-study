# -*- coding: utf-8 -*-
"""과목 이동, 과목별 현황 카드와 제출 작업 영역을 공통으로 배치함."""
from PyQt6.QtCore import QEvent, QPoint, QSignalBlocker, QSize, Qt
from PyQt6.QtWidgets import QApplication, QComboBox, QFrame, QGridLayout, QLayout, QScrollArea, QSizePolicy, QWidget

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
    """제출할 변경이나 받을 자료가 있을 때만 하단에 알림을 띄움."""

    def __init__(self, win):
        super().__init__()
        self.setObjectName("submissionbar")
        self.setProperty("ui", "2")
        self.row = kit.box(self, (24, 16, 24, 16), 16, horizontal=True)
        self.message = kit.para("", "caption", "secondary")
        self.row.addWidget(self.message, 1)
        self.actions = QWidget()
        buttons = kit.box(self.actions, spacing=12, horizontal=True)
        self.submit = kit.button("풀이 제출", "secondary", "l")
        self.submit.setObjectName("submit_work")
        self.submit.setAccessibleDescription("아직 올리지 않은 풀이와 학습 기록을 제출합니다.")
        self.submit.clicked.connect(win.submit_pr)
        self.submit.hide()
        self.sync = kit.button("새 문제 받기", "secondary", "l")
        self.sync.clicked.connect(win.fetch_problems)
        buttons.addWidget(self.submit)
        buttons.addWidget(self.sync)
        self.row.addWidget(self.actions)
        self.state, self.busy, self.usable = {}, False, False

    def refresh(self, state, updates, usable, busy=False):
        self.state, self.usable, self.busy = state, usable, busy
        pending = state.get("status") == "ok" and state.get("pending", False)
        available = updates.get("status") == "ok" and updates.get("available", False)
        self.submit.setVisible(usable and pending)
        self.sync.setVisible(usable and available)
        self.submit.setEnabled(usable and not busy)
        self.sync.setEnabled(usable and not busy)
        if busy:
            text = "작업이 끝나면 제출 현황을 갱신합니다."
        elif pending and available:
            text = "제출할 풀이와 새 학습 자료가 있습니다."
        elif pending:
            text = "제출할 풀이가 있습니다."
        else:
            text = "새 학습 자료가 있습니다."
        self.message.setText(text)
        kit.set_tone(self.message, "accent" if pending else "secondary")
        self.arrange()
        self.setVisible(usable and (pending or available))

    def arrange(self):
        need = self.message.sizeHint().width() + self.actions.sizeHint().width() + 64
        vertical = self.width() < max(800, need)
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
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
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
        self.body = QWidget()
        self.body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        box = kit.box(self.body)
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
        self.submissions.setParent(self.body)
        self.reminder_padding = []
        self.reminder_viewports = []
        for page in self.submission_pages:
            scrolls = page.findChildren(QScrollArea)
            if scrolls:
                for scroll in scrolls:
                    self.reminder_viewports.append(scroll.viewport())
                    scroll.viewport().installEventFilter(self)
                    layout = scroll.widget().layout() if scroll.widget() else None
                    if layout:
                        self.reminder_padding.append((layout, layout.getContentsMargins()))
            else:
                self.reminder_padding.append((page.layout(), page.layout().getContentsMargins()))
        self.body.installEventFilter(self)
        QApplication.instance().focusChanged.connect(self.reveal_focus)
        outer.addWidget(self.body, 1)
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
        for index, (tid, _, _) in enumerate(SUBJECTS):
            self.buttons[tid].setChecked(self.win.area == tid)
            if self.win.area == tid:
                blocker = QSignalBlocker(self.compact)
                self.compact.setCurrentIndex(index)
                del blocker
        busy = self.win.job is not None or self.win.pending_close
        self.rail.setEnabled(not busy)
        self.compact.setEnabled(not busy)
        usable = started and self.pages.currentWidget() in self.submission_pages and self.win.gitflow is not None
        pending = self.win.pending_submission.get("status") == "ok" and self.win.pending_submission.get("pending", False)
        available = self.win.problem_updates.get("status") == "ok" and self.win.problem_updates.get("available", False)
        focused = QApplication.focusWidget()
        if ((focused is self.submissions.submit and not (usable and pending)) or
                (focused is self.submissions.sync and not (usable and available))):
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.submissions.refresh(self.win.pending_submission, self.win.problem_updates, usable, busy)
        self.position_reminder()

    def position_reminder(self):
        """알림이 나타나도 본문은 그대로 두고, 마지막 조작부까지 스크롤할 여백을 남김."""
        bar = self.submissions
        width = max(1, min(960, self.body.width() - 32))
        bar.setFixedWidth(width)
        bar.arrange()
        bar.layout().activate()
        height = max(bar.sizeHint().height(), bar.layout().heightForWidth(width))
        bottom = self.body.height()
        scrolls = [area for area in self.pages.currentWidget().findChildren(QScrollArea) if area.isVisible()]
        if scrolls:
            area = max(scrolls, key=lambda area: area.width() * area.height())
            bottom = area.viewport().mapTo(self.body, QPoint(0, area.viewport().height())).y()
        bar.setGeometry((self.body.width() - width) // 2, bottom - height - 16, width, height)
        bar.raise_()
        # 상태 변경으로 스크롤 범위가 달라지지 않도록 두 동작의 높이를 항상 남김.
        reserve = 48 + 2 * theme.TYPE["caption"][1] + bar.submit.sizeHint().height()
        for layout, (left, top, right, bottom) in self.reminder_padding:
            layout.setContentsMargins(left, top, right, bottom + reserve)

    def eventFilter(self, watched, event):
        if (watched is self.body or watched in self.reminder_viewports) and event.type() == QEvent.Type.Resize:
            self.position_reminder()
        return super().eventFilter(watched, event)

    def reveal_focus(self, old, current):
        """키보드로 옮긴 초점은 떠 있는 알림 위까지 스크롤함. 알림 표시 자체로 읽던 위치를 옮기지 않음."""
        if current is None or not self.submissions.isVisible() or not self.pages.isAncestorOf(current):
            return
        parent = current.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                parent.ensureWidgetVisible(current, 8, self.submissions.height() + 24)
                return
            parent = parent.parentWidget()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()
