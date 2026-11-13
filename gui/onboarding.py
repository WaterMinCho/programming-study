# -*- coding: utf-8 -*-
"""첫 화면의 실제 조작 위치에 사용 안내를 표시함."""
from PyQt6.QtCore import QEvent, QPoint, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QPolygon
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QWidget

from gui import kit, theme


TOUR_KEY = "onboarding/hub/v1"


class HubTour(QWidget):
    def __init__(self, win):
        super().__init__(win.workspace)
        self.settings = win.settings
        self.hub = win.hub
        self.space = win.workspace
        self.scroll = self.hub.scroll
        self.target = self.previous_focus = None
        self.step = 0
        self.anchor = QRect()
        self.hide()
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.card, box = kit.card(pad=theme.GAP["paragraph"], spacing=theme.GAP["title_description"])
        self.card.setParent(self)
        kit.page(self.card)
        heading = QHBoxLayout()
        self.title = kit.label("", "headline")
        self.count = kit.label("", "caption", "secondary")
        heading.addWidget(self.title, 1)
        heading.addWidget(self.count)
        box.addLayout(heading)
        self.description = kit.label("", "body", "secondary")
        self.description.setWordWrap(True)
        box.addWidget(self.description)
        actions = QHBoxLayout()
        actions.setSpacing(theme.GAP["detail"])
        self.skip = kit.button("건너뛰기", "text")
        self.back = kit.button("이전")
        self.next = kit.button("다음", "primary")
        self.skip.clicked.connect(self.finish)
        self.back.clicked.connect(lambda: self.move_step(-1))
        self.next.clicked.connect(lambda: self.move_step(1))
        actions.addWidget(self.skip)
        actions.addStretch(1)
        actions.addWidget(self.back)
        actions.addWidget(self.next)
        box.addLayout(actions)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.arrange)
        for widget in (self.skip, self.back, self.next, self.space, self.hub, self.scroll.viewport(), self.scroll.widget(),
                       self.space.submissions, self.space.compact, *self.space.buttons.values(),
                       self.hub.next_btn, self.hub.settings_btn, self.hub.privacy_btn, self.hub.foot):
            widget.installEventFilter(self)
        self.scroll.verticalScrollBar().valueChanged.connect(self.schedule)
        theme.signals.changed.connect(self.schedule)

    def steps(self):
        subjects = self.space.compact if self.space.compact.isVisible() else self.space.buttons.get("python")
        choices = (
            (subjects, "과목 선택", "여기서 공부할 과목을 고릅니다."),
            (self.hub.next_btn if self.hub.target else None, "이어서 할 일", "이 버튼을 누르면 카드에 적힌 학습을 시작합니다."),
            (self.hub.settings_btn, "화면 설정", "글자 크기와 테마를 바꿉니다. 첫 화면 안내도 여기서 다시 볼 수 있습니다."),
            (self.hub.privacy_btn, "내 정보·데이터", "학습 데이터 제공 여부를 확인하거나 변경합니다."),
            (self.hub.foot, "불편한 점 알리기", "문제 오류나 사용 중 불편한 점을 알릴 수 있습니다."),
        )
        return [(i, widget, title, text) for i, (widget, title, text) in enumerate(choices)
                if widget is not None and widget.isVisible() and widget.isEnabled()]

    def begin(self, previous_focus):
        if self.isVisible():
            return
        steps = self.steps()
        if not steps:
            return
        self.previous_focus = previous_focus
        self.previous_scroll = self.scroll.verticalScrollBar().value()
        self.step = steps[0][0]
        self.setGeometry(self.space.rect())
        self.show()
        self.raise_()
        kit.refont(self.card)
        self.arrange()
        self.next.setFocus(Qt.FocusReason.TabFocusReason)

    def move_step(self, direction):
        ids = [i for i, *_ in self.steps()]
        candidates = [i for i in ids if (i - self.step) * direction > 0]
        if candidates:
            self.step = candidates[0] if direction > 0 else candidates[-1]
            self.arrange()
        elif direction > 0:
            self.finish()

    def finish(self):
        self.settings.setValue(TOUR_KEY, True)
        self.dismiss()

    def dismiss(self):
        self.hide()
        self.timer.stop()
        if self.hub.isVisible():
            widget = self.previous_focus
            if widget is None or not widget.isVisible() or not widget.isEnabled():
                widget = self.hub.settings_btn
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
        self.scroll.verticalScrollBar().setValue(self.previous_scroll)
        self.previous_focus = self.target = None

    def eventFilter(self, watched, event):
        if self.isVisible():
            if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                forward = event.key() == Qt.Key.Key_Tab and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                return self.focusNextPrevChild(forward)
            if watched is self.hub and event.type() == QEvent.Type.Hide:
                self.dismiss()
            elif event.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.LayoutRequest,
                                  QEvent.Type.EnabledChange, QEvent.Type.Show, QEvent.Type.Hide):
                self.schedule()
        return False

    def schedule(self):
        if self.isVisible():
            self.timer.start(0)

    def target_rect(self, widget):
        origin = widget.mapTo(self.space, QPoint())
        rect = QRect(origin, widget.size())
        if self.scroll.isAncestorOf(widget):
            viewport = self.scroll.viewport()
            visible = QRect(viewport.mapTo(self.space, QPoint()), viewport.size())
            bar = self.space.submissions
            if bar.isVisible():
                visible.setBottom(min(visible.bottom(), bar.mapTo(self.space, QPoint()).y() - 1))
            if not visible.contains(rect):
                scrollbar = self.scroll.verticalScrollBar()
                scrollbar.setValue(scrollbar.value() + rect.center().y() - visible.center().y())
                rect.moveTopLeft(widget.mapTo(self.space, QPoint()))
            rect = rect.intersected(visible)
        return rect.intersected(self.rect())

    def arrange(self):
        if not self.isVisible():
            return
        self.setGeometry(self.space.rect())
        steps = self.steps()
        if not steps:
            self.dismiss()
            return
        # 대상이 숨겨지면 그다음 유효한 단계를 찾고, 마지막에서는 앞 단계로 돌아감.
        start = next((n for n, item in enumerate(steps) if item[0] >= self.step), len(steps))
        for index in (*range(start, len(steps)), *reversed(range(start))):
            step, target, title, text = steps[index]
            anchor = self.target_rect(target)
            if not anchor.isEmpty():
                break
        else:
            self.dismiss()
            return
        self.step, self.target, self.anchor = step, target, anchor
        self.title.setText(title)
        self.count.setText(f"{index + 1} / {len(steps)}")
        self.description.setText(text)
        if index == 0 and self.back.hasFocus():
            self.next.setFocus(Qt.FocusReason.TabFocusReason)
        self.back.setEnabled(index > 0)
        self.next.setText("마침" if index == len(steps) - 1 else "다음")
        self.next.setAccessibleDescription(f"{self.count.text()} · {title}. {text}")
        margin = theme.GAP["paragraph"]
        gap = theme.GAP["title_description"]
        width = min(self.width() - 2 * margin, max(360, 22 * theme.TYPE["body"][0]))
        height = self.card.layout().totalHeightForWidth(width)
        x = max(margin, min(anchor.center().x() - width // 2, self.width() - width - margin))
        below = self.height() - margin - anchor.bottom() >= height + gap
        y = anchor.bottom() + gap if below else anchor.top() - gap - height
        self.card.setGeometry(x, max(margin, min(y, self.height() - height - margin)), width, height)
        self.update()

    def paintEvent(self, event):
        if self.anchor.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        ring = QRectF(self.anchor).adjusted(1, 1, -1, -1)
        radius = theme.RADIUS["small"]
        path.addRoundedRect(ring, radius, radius)
        shade = theme.qcolor("ink" if theme.state["scheme"] == "light" else "bg")
        shade.setAlpha(115)
        painter.fillPath(path, shade)
        painter.setPen(QPen(theme.qcolor("focus"), 2))
        painter.drawRoundedRect(ring, radius, radius)
        card = self.card.geometry()
        x = max(card.left() + 16, min(self.anchor.center().x(), card.right() - 16))
        below = card.top() > self.anchor.center().y()
        y = card.top() if below else card.bottom()
        tip = self.anchor.bottom() + 1 if below else self.anchor.top() - 1
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor("surface"))
        painter.drawPolygon(QPolygon([QPoint(x - 8, y), QPoint(x + 8, y), QPoint(x, tip)]))

    def focusNextPrevChild(self, forward):
        buttons = [button for button in (self.skip, self.back, self.next) if button.isEnabled()]
        current = QApplication.focusWidget()
        index = buttons.index(current) if current in buttons else -1
        buttons[(index + (1 if forward else -1)) % len(buttons)].setFocus(Qt.FocusReason.TabFocusReason)
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finish()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            button = QApplication.focusWidget()
            if button in (self.next, self.back, self.skip):
                button.click()
        else:
            super().keyPressEvent(event)
