# -*- coding: utf-8 -*-
"""과목 이동, 과목별 현황 카드와 제출 작업 영역을 공통으로 배치함."""
from PyQt6.QtCore import QEvent, QPoint, QSignalBlocker, QSize, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtWidgets import QApplication, QFrame, QGridLayout, QLayout, QScrollArea, QSizePolicy, QWidget

import study
from gui import kit, theme
from gui.mascot import Mascot
from gui.navigation import NavigationButton, NavigationPicker

SUBJECTS = (("hub", "학습 현황", "go_hub"), ("python", "파이썬", "go_home"),
            ("journey", "알고리즘", "go_journey"), ("web", "웹 면접", "go_web"), ("ai", "AI", "go_ai"),
            ("career_roadmap", "개발자 로드맵", "go_career"), ("career_magazine", "매거진", "go_magazine"))


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
        self.win, self.result = win, None
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
        self.sync = kit.button("프로그램 업데이트", "secondary", "l")
        self.sync.setToolTip("프로그램과 학습 자료를 함께 업데이트합니다.")
        self.sync.clicked.connect(win.fetch_problems)
        buttons.addWidget(self.submit)
        buttons.addWidget(self.sync)
        self.details = kit.button("자세히", "text", "l")
        self.details.clicked.connect(self.show_details)
        buttons.addWidget(self.details)
        self.details.hide()
        self.dismiss = kit.button("닫기", "text", "l")
        self.dismiss.clicked.connect(self.dismiss_result)
        buttons.addWidget(self.dismiss)
        self.dismiss.hide()
        self.row.addWidget(self.actions)
        self.state, self.busy, self.usable = {}, False, False

    def refresh(self, state, updates, usable, busy=False, allowed=None):
        busy = busy or self.win.submission_running
        was_pending = self.state.get("status") == "ok" and self.state.get("pending", False)
        self.state, self.usable, self.busy = state, usable, busy
        if allowed is None:
            allowed = self.win.has_submission_consent()
        pending = state.get("status") == "ok" and state.get("pending", False) and allowed
        if self.result and self.result.get("status") in ("ok", "nothing") and (not allowed or pending and not was_pending):
            self.clear_result()
        available = updates.get("status") == "ok" and updates.get("available", False)
        self.submit.setVisible(usable and pending)
        self.sync.setVisible(usable and available)
        self.submit.setEnabled(usable and pending and not busy)
        self.sync.setEnabled(usable and available and not busy)
        self.dismiss.setVisible(self.result is not None and not busy)
        self.dismiss.setEnabled(not busy)
        detail = False
        if busy:
            text = "풀이 결과를 서버로 제출합니다." if self.win.submission_running else "작업이 끝나면 제출 현황을 갱신합니다."
        elif self.result is not None:
            text, detail = self.result_summary()
        elif pending and available:
            text = "제출할 풀이와 새 업데이트가 있습니다."
        elif pending:
            text = "제출할 풀이가 있습니다."
        else:
            text = "새 업데이트가 있습니다."
        self.message.setText(text)
        self.details.setVisible(detail and not busy)
        self.details.setEnabled(not busy)
        tone = "accent" if pending else "secondary"
        if self.result is not None:
            tone = {"ok": "success", "error": "danger"}.get(self.result.get("status"), "secondary")
        kit.set_tone(self.message, tone)
        self.arrange()
        self.setVisible(usable and (pending or available or self.result is not None))

    def show_result(self, result):
        self.result = dict(result)
        self.win.workspace.refresh()

    def clear_result(self):
        self.result = None

    def dismiss_result(self):
        self.clear_result()
        self.win.workspace.refresh()

    def show_details(self):
        if self.result:
            self.win.ask("제출 안내", self.result.get("message") or "제출 결과를 확인해 주세요.", detail=self.result.get("detail") or "")

    def result_summary(self):
        if not self.result:
            return "", False
        original = self.result.get("message") or "제출 결과를 확인해 주세요."
        summary = " ".join(original.split())
        text = summary[:48] + "…" if len(summary) > 48 else summary
        return text, text != original.strip() or bool(self.result.get("detail"))

    def arrange(self):
        need = QFontMetricsF(self.message.font()).horizontalAdvance(self.message.text()) + self.actions.layout().sizeHint().width() + 64
        vertical = self.width() < need
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
        self.subjects = tuple(row for row in SUBJECTS if row[0] == "hub" or row[0].startswith("career_") or row[0] in study.ENTRY_TRACKS)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.overview_pages = (win.hub, win.home, win.journey_map, win.web_home, win.ai_home, win.ai_lesson)
        self.submission_pages = (*self.overview_pages, win.result_page)
        self.setObjectName("page")
        outer = kit.box(self, horizontal=True)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.rail = QFrame()
        self.rail.setObjectName("navigation")
        self.rail.setProperty("ui", "2")
        self.rail.setFixedWidth(232)
        nav = kit.box(self.rail, (16, 24, 16, 24), 8)
        brand = QWidget()
        brand_row = kit.box(brand, spacing=12, horizontal=True)
        mark = QWidget()
        mark.setFixedWidth(36)
        mark_row = kit.box(mark)
        mark_row.addWidget(Mascot(32), 0, Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(mark)
        brand_row.addWidget(kit.para("프로그래밍\n스터디", "label", bold=True), 1)
        nav.addWidget(brand)
        nav.addSpacing(24)
        self.buttons = {}
        self.career_toggle = NavigationButton("career", "커리어")
        self.career_toggle.clicked.connect(self.toggle_career)
        self.career_expanded = False
        for tid, title, action in self.subjects:
            if tid == "career_roadmap":
                nav.addSpacing(16)
                nav.addWidget(self.career_toggle)
            button = NavigationButton(tid, title, depth=int(tid.startswith("career_")))
            if button.depth:
                # 접은 상태에서도 펼친 목록이 들어가는지를 같은 높이로 판단함.
                policy = button.sizePolicy()
                policy.setRetainSizeWhenHidden(True)
                button.setSizePolicy(policy)
            button.clicked.connect(lambda checked=False, action=action: self.navigate(action))
            self.buttons[tid] = button
            nav.addWidget(button)
        nav.addStretch(1)
        outer.addWidget(self.rail)
        self.body = QWidget()
        self.body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        box = kit.box(self.body)
        self.compact = NavigationPicker()
        self.compact.setAccessibleName("메뉴 이동")
        for tid, title, action in self.subjects:
            self.compact.addItem("커리어 · " + title if tid.startswith("career_") else title, action)
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

    def toggle_career(self):
        self.career_expanded = not self.career_expanded
        self.refresh_navigation()

    def refont(self):
        # 하위 단추와 상단 제목에도 새 글꼴을 적용한 뒤 목록 크기를 다시 잼.
        QTimer.singleShot(0, self.refresh_navigation)

    def refresh_navigation(self):
        active = self.win.area
        focused = QApplication.focusWidget()
        self.career_toggle.setProperty("expanded", self.career_expanded)
        action = "커리어 메뉴 접기" if self.career_expanded else "커리어 메뉴 펼치기"
        self.career_toggle.setToolTip(action)
        self.career_toggle.setAccessibleDescription(action)
        self.career_toggle.setChecked(not self.career_expanded and active.startswith("career_"))
        for index, (tid, _, _) in enumerate(self.subjects):
            button = self.buttons[tid]
            if button.depth:
                if focused is button and not self.career_expanded:
                    self.career_toggle.setFocus(Qt.FocusReason.OtherFocusReason)
                button.setVisible(self.career_expanded)
            button.setChecked(tid == active and not button.isHidden())
            if tid == active:
                with QSignalBlocker(self.compact):
                    self.compact.setCurrentIndex(index)
        self.career_toggle.update()

        rail_width = max(button.sizeHint().width() for button in (self.career_toggle, *self.buttons.values())) + 32
        self.rail.setFixedWidth(rail_width)
        breakpoint = max(1120, rail_width + 760)
        rail_fits = self.width() >= breakpoint and self.height() >= self.rail.minimumSizeHint().height()
        show_navigation = self.win.session is not None and self.pages.currentWidget() in self.overview_pages
        self.rail.setVisible(show_navigation and rail_fits)
        self.compact.setVisible(show_navigation and not rail_fits)
        if show_navigation and rail_fits and focused is self.compact:
            target = self.buttons.get(active)
            if target is not None:
                (self.career_toggle if target.isHidden() else target).setFocus(Qt.FocusReason.OtherFocusReason)
        elif show_navigation and not rail_fits and focused and self.rail.isAncestorOf(focused):
            self.compact.setFocus(Qt.FocusReason.OtherFocusReason)

    def refresh(self, *_):
        self.refresh_navigation()
        started = self.win.session is not None and self.pages.currentWidget() is not self.win.start
        busy = self.win.job is not None or self.win.pending_close or self.win.close_pending
        self.rail.setEnabled(not busy)
        self.compact.setEnabled(not busy)
        usable = started and self.pages.currentWidget() in self.submission_pages and self.win.gitflow is not None
        allowed = self.win.has_submission_consent()
        pending = self.win.pending_submission.get("status") == "ok" and self.win.pending_submission.get("pending", False) and allowed
        available = self.win.problem_updates.get("status") == "ok" and self.win.problem_updates.get("available", False)
        focused = QApplication.focusWidget()
        if ((focused is self.submissions.submit and not (usable and pending)) or
                (focused is self.submissions.sync and not (usable and available)) or
                (focused is self.submissions.details and not (usable and not busy and self.submissions.result_summary()[1])) or
                (focused is self.submissions.dismiss and self.submissions.result is None)):
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.submissions.refresh(self.win.pending_submission, self.win.problem_updates, usable, busy, allowed)
        self.position_reminder()
        self.win.hub.refresh_submission(allowed)

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
