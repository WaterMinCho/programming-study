"""커리어 화면의 실제 버튼에 첫 방문 안내를 표시함."""
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QPoint, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QPolygon
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QWidget

from gui import kit, motion, theme


TOUR_KEYS = {name: f"onboarding/career/{name}/v1" for name in ("catalog", "detail", "magazine")}


def steps_for(page, context):
    if context == "catalog":
        card = next((card for card in page.gallery.cards.values() if card.isVisibleTo(page)), None)
        choices = ((page.filter_toggle, "관심 분야로 좁히기", "산업과 제품을 고르면 관련 직무만 남습니다."),
                   (card, "하는 일부터 살펴보기", "직무를 누르면 업무와 준비할 기술을 그림으로 볼 수 있습니다."))
    elif context == "detail":
        choices = ((page.detail_tabs, "업무에서 학습으로", "하는 일을 살펴본 뒤, 학습 로드맵에서 준비할 순서를 확인하세요."),
                   (page.goal_button, "관심 직무 저장", "이 컴퓨터에 관심 직무를 저장합니다. 다른 직무로 바꿀 수도 있습니다."))
    else:
        papers = page.paper_content.isVisibleTo(page)
        target = next((item for item in page.paper_previews.values() if item.isVisibleTo(page)), None) if papers else next(
            (card.cover for card in page.cards.values() if card.isVisibleTo(page)), None)
        choices = ((page.tabs, "영상과 논문 해설", "영상으로 배우거나, 논문의 핵심 과정을 그림으로 따라가세요."),
                   (target, "그림을 눌러 해설 열기" if papers else "썸네일을 눌러 재생",
                    "그림을 누르면 단계별 설명이 열립니다." if papers else "영상 정보에서 주제와 길이를 먼저 확인할 수도 있습니다."))
    return [(target, title, text) for target, title, text in choices
            if target is not None and target.isEnabled() and target.isVisibleTo(page)]


class CareerTour(QWidget):
    def __init__(self, page, settings, context):
        super().__init__(page)
        self.page, self.settings, self.context = page, settings, context
        self.active = self.closing = False
        self.step = 0
        self.anchor = QRect()
        self.target = self.previous_focus = None
        self.steps = []
        self.hide()
        self.setAccessibleName("커리어 사용법")
        self.card, box = kit.card(pad=theme.GAP["paragraph"], spacing=theme.GAP["title_description"])
        self.card.setParent(self)
        kit.page(self.card)
        heading = QHBoxLayout()
        self.title = kit.label("", "headline")
        self.title.setWordWrap(True)
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
        actions.addWidget(self.skip)
        actions.addStretch(1)
        actions.addWidget(self.back)
        actions.addWidget(self.next)
        box.addLayout(actions)
        self.skip.clicked.connect(self.finish)
        self.back.clicked.connect(lambda: self.move_step(-1))
        self.next.clicked.connect(lambda: self.move_step(1))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.arrange)
        page.installEventFilter(self)
        theme.signals.changed.connect(self.schedule)

    def begin(self, previous_focus=None):
        self.steps = steps_for(self.page, self.context)
        if not self.steps or not self.page.isVisible():
            return False
        self.previous_focus = previous_focus or QApplication.focusWidget()
        self.previous_scroll = self.page.scroll.verticalScrollBar().value()
        self.previous_anchor = self.page._anchor
        self.page._timer.stop()
        self.page._anchor = None
        self.page._settling = True
        self.active = True
        self.setGeometry(self.page.rect())
        QApplication.instance().installEventFilter(self)
        self.show()
        self.raise_()
        kit.refont(self.card)
        self.move_step(0)
        if not self.active:
            return False
        self.next.setFocus(Qt.FocusReason.TabFocusReason)
        motion.fade_opacity(self, True)
        return True

    def move_step(self, direction):
        if self.closing:
            return
        number = self.step + direction
        if number >= len(self.steps):
            self.finish()
            return
        self.step = max(0, number)
        self.target, title, text = self.steps[self.step]
        self.title.setText(title)
        self.description.setText(text)
        self.count.setText(f"{self.step + 1} / {len(self.steps)}")
        self.back.setEnabled(self.step > 0)
        self.next.setText("마침" if self.step == len(self.steps) - 1 else "다음")
        self.next.setAccessibleDescription(f"{self.count.text()} · {title}. {text}")
        if self.page.scroll.isAncestorOf(self.target):
            viewport = self.page.scroll.viewport()
            top = self.target.mapTo(viewport, QPoint()).y()
            # 단계 진입 때만 대상을 위로 옮겨 안내 공간을 확보함.
            bar = self.page.scroll.verticalScrollBar()
            bar.setValue(bar.value() + top)
        self.arrange()

    def schedule(self):
        if self.active and not self.closing:
            self.timer.start(0)

    def arrange(self):
        if not self.active or self.closing:
            return
        if sip.isdeleted(self.target) or not self.target.isVisibleTo(self.page):
            self.dismiss()
            return
        self.setGeometry(self.page.rect())
        anchor = QRect(self.mapFromGlobal(self.target.mapToGlobal(QPoint())), self.target.size())
        if self.page.scroll.isAncestorOf(self.target):
            viewport = self.page.scroll.viewport()
            anchor = anchor.intersected(QRect(self.mapFromGlobal(viewport.mapToGlobal(QPoint())), viewport.size()))
        self.anchor = anchor.intersected(self.rect())
        if self.anchor.isEmpty():
            self.dismiss()
            return
        margin, gap = theme.GAP["paragraph"], theme.GAP["title_description"]
        width = min(self.width() - 2 * margin, max(360, 22 * theme.TYPE["body"][0]))
        height = self.card.layout().totalHeightForWidth(width)
        x = max(margin, min(self.anchor.center().x() - width // 2, self.width() - width - margin))
        below = self.anchor.bottom() + gap
        above = self.anchor.top() - gap - height
        if below + height > self.height() - margin and above < margin:
            # 큰 그림의 위아래에 공간이 없을 때만 누를 수 있는 상단 부분을 강조함.
            self.anchor.setHeight(min(self.anchor.height(), theme.control_height("l")))
            below = self.anchor.bottom() + gap
        y = below if below + height <= self.height() - margin else above
        if y < margin:
            self.dismiss()
            return
        self.card.setGeometry(x, y, width, height)
        self.update()

    def finish(self):
        if not self.active or self.closing:
            return
        self.settings.setValue(TOUR_KEYS[self.context], True)
        self.closing = True
        motion.fade_opacity(self, False, self.dismiss)

    def dismiss(self):
        if not self.active:
            return
        self.active = False
        self.timer.stop()
        QApplication.instance().removeEventFilter(self)
        self.hide()
        self.page.scroll.verticalScrollBar().setValue(self.previous_scroll)
        self.page._anchor = self.previous_anchor
        self.page._settling = False
        self.page._schedule_restore()
        focus = self.previous_focus
        if self.page.isVisible() and focus is not None and not sip.isdeleted(focus) and focus.isVisible() and focus.isEnabled():
            focus.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event):
        if not self.active:
            return False
        kind = event.type()
        if watched is self.page and kind == QEvent.Type.Hide:
            self.dismiss()
        elif kind in (QEvent.Type.Resize, QEvent.Type.LayoutRequest) and watched in (self.page, self.card):
            self.schedule()
        elif isinstance(watched, QWidget) and (watched is self.page or self.page.isAncestorOf(watched)):
            if kind in (QEvent.Type.Shortcut, QEvent.Type.ShortcutOverride):
                event.accept()
                return True
            if kind == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Escape:
                    self.finish()
                elif key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                    self.focusNextPrevChild(key == Qt.Key.Key_Tab and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                    if watched in (self.skip, self.back, self.next):
                        watched.click()
                return True
        return False

    def focusNextPrevChild(self, forward):
        buttons = [button for button in (self.skip, self.back, self.next) if button.isEnabled()]
        focus = QApplication.focusWidget()
        index = buttons.index(focus) if focus in buttons else -1
        buttons[(index + (1 if forward else -1)) % len(buttons)].setFocus(Qt.FocusReason.TabFocusReason)
        return True

    def paintEvent(self, event):
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
