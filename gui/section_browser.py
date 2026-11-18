"""분류 선택을 고정하고 선택한 목록의 읽던 위치를 보관함."""
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF, QIcon, QPainterPath, QPen
from PyQt6.QtWidgets import (QButtonGroup, QGridLayout, QPushButton, QSizePolicy,
                             QStyle, QStyleOptionButton, QStylePainter, QWidget)

from gui import kit, theme


class SectionButton(QPushButton):
    """분류의 선택과 초점을 나눠 표시하고 긴 이름은 같은 폭 안에서 줄바꿈함."""
    def __init__(self, key, title, description):
        super().__init__(title)
        self.key = key
        self.description = description
        self.expanded = True
        self.setObjectName("section_choice")
        self.setCheckable(True)
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(title)
        self.setToolTip(description)
        self.setAccessibleDescription(description)
        kit.typed(self, "label", True)

    def sizeHint(self):
        metrics = QFontMetricsF(theme.font("label", True))
        inset = 64 if self.expanded else 24
        return QSize(math.ceil(metrics.horizontalAdvance(self.text())) + inset,
                     max(56 if self.expanded else 44, theme.TYPE["label"][1] + (32 if self.expanded else 20)))

    def minimumSizeHint(self):
        metrics = QFontMetricsF(theme.font("label", True))
        word_width = max((metrics.horizontalAdvance(word) for word in self.text().split()), default=0)
        return QSize(max(80, math.ceil(word_width) + (64 if self.expanded else 24)), self.sizeHint().height())

    def heightForWidth(self, width):
        metrics = QFontMetricsF(theme.font("label", True))
        bounds = metrics.boundingRect(QRectF(0, 0, max(1, width - (64 if self.expanded else 24)), 1000),
                                      Qt.TextFlag.TextWordWrap, self.text())
        height = max(self.sizeHint().height(), math.ceil(bounds.height()) + (32 if self.expanded else 20))
        if self.expanded:
            detail = QFontMetricsF(theme.font("caption")).boundingRect(
                QRectF(0, 0, max(1, width - 32), 1000), Qt.TextFlag.TextWordWrap, self.description)
            height += math.ceil(detail.height()) + 8
        return height

    def paint_icon(self, painter, color):
        painter.save()
        painter.translate(16, 18)
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.key == "mocks":
            painter.drawEllipse(QRectF(2, 3, 18, 18))
            painter.drawLine(QPointF(11, 7), QPointF(11, 12))
            painter.drawLine(QPointF(11, 12), QPointF(15, 14))
            painter.drawLine(QPointF(8, 0), QPointF(14, 0))
        elif self.key == "coding":
            path = QPainterPath(QPointF(7, 5))
            for point in ((2, 11), (7, 17)):
                path.lineTo(*point)
            path.moveTo(16, 5)
            for point in ((21, 11), (16, 17)):
                path.lineTo(*point)
            path.moveTo(13, 3)
            path.lineTo(10, 19)
            painter.drawPath(path)
        else:
            painter.drawRoundedRect(QRectF(2, 1, 18, 20), 2, 2)
            if self.key == "lessons":
                painter.drawLine(QPointF(7, 1), QPointF(7, 21))
            for y in (7, 12, 17):
                painter.drawLine(QPointF(10, y), QPointF(16, y))
        painter.restore()

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text, option.icon = "", QIcon()
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setFont(theme.font("label", True))
        tone = "faint" if not self.isEnabled() else "primary_ink" if self.isChecked() else "muted"
        painter.setPen(theme.qcolor(tone))
        if not self.expanded:
            painter.drawText(QRectF(self.rect()).adjusted(12, 8, -12, -8),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.text())
            return
        self.paint_icon(painter, theme.qcolor(tone))
        title = QFontMetricsF(painter.font()).boundingRect(QRectF(0, 0, max(1, self.width() - 64), 1000),
                                                         Qt.TextFlag.TextWordWrap, self.text())
        painter.drawText(QRectF(48, 16, self.width() - 64, title.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                         self.text())
        if self.expanded:
            painter.setFont(theme.font("caption"))
            painter.setPen(theme.qcolor(tone))
            top = max(56, math.ceil(title.height()) + 32)
            painter.drawText(QRectF(16, top, self.width() - 32, self.height() - top - 8),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                             self.description)


class SectionBrowser(QWidget):
    """같은 분류 선택과 스크롤을 여러 과정에서 재사용함. 상태는 메모리에만 둠."""
    def __init__(self, parent=None, *, header=None):
        super().__init__(parent)
        self.current, self.context = None, None
        self.panels, self.buttons, self.states = {}, {}, {}
        self.columns, self.pending = 0, None
        self._signature = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._restore)
        outer = kit.box(self)
        self.navigation = QWidget()
        self.navigation.setAccessibleName("학습 분류")
        self.grid = QGridLayout(self.navigation)
        self.grid.setContentsMargins(0, 8, 0, 12)
        self.grid.setSpacing(8)
        self.group = QButtonGroup(self)
        navigation = self.navigation
        if header is not None:
            navigation = QWidget()
            stack = kit.box(navigation)
            stack.addWidget(header)
            stack.addWidget(self.navigation)
        self.navigation_column = kit.dense_column(navigation)
        outer.addWidget(self.navigation_column)
        self.content = kit.dense(QWidget())
        self.body = kit.box(self.content, (0, 16, 0, 48), 16)
        self.scroll = kit.scroll(kit.dense_column(self.content))
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.navigation.installEventFilter(self)
        self.scroll.viewport().installEventFilter(self)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._range_changed)
        self.scroll.verticalScrollBar().actionTriggered.connect(self._cancel_restore)
        self.scroll.verticalScrollBar().sliderPressed.connect(self._cancel_restore)
        outer.addWidget(self.scroll, 1)

    def add_section(self, key, title, description, panel):
        button = SectionButton(key, title, description)
        self.buttons[key], self.panels[key] = button, panel
        self.group.addButton(button)
        button.installEventFilter(self)
        button.clicked.connect(lambda checked=False, key=key: self.select(key))
        self.body.addWidget(panel)
        panel.hide()
        self.columns = 0
        self.refont()
        if self.current is None:
            self.current = key
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setChecked(True)
            panel.show()

    def remember(self):
        if self.context is None or self.current is None:
            return
        state = self.states.setdefault(self.context, {"section": self.current, "positions": {}})
        state["section"] = self.current
        state["positions"][self.current] = self.pending if self.pending is not None else self.scroll.verticalScrollBar().value()

    def begin_refresh(self, context):
        self.remember()
        self._timer.stop()
        self.pending = None
        self.context = context
        self.states.setdefault(context, {"section": self.current, "positions": {}})

    def finish_refresh(self):
        state = self.states[self.context]
        self.select(state["section"], remember=False)

    def select(self, key, *, remember=True):
        if key not in self.panels:
            return
        if remember:
            self.remember()
        self.current = key
        for name, panel in self.panels.items():
            panel.setVisible(name == key)
            self.buttons[name].setChecked(name == key)
            self.buttons[name].setFocusPolicy(Qt.FocusPolicy.StrongFocus if name == key else Qt.FocusPolicy.ClickFocus)
        focused = self.window().focusWidget()
        if focused in self.buttons.values() and focused is not self.buttons[key]:
            self.buttons[key].setFocus(Qt.FocusReason.OtherFocusReason)
        state = self.states.setdefault(self.context, {"section": key, "positions": {}})
        state["section"] = key
        self.pending = state["positions"].get(key, 0)
        self._signature = None
        self._timer.start(0)

    def _range_changed(self, *_):
        if self.pending is not None:
            self._timer.start(0)

    def _cancel_restore(self, *_):
        self.pending = None
        self._timer.stop()

    def _restore(self):
        if self.pending is None:
            return
        self.content.layout().activate()
        self.scroll.widget().layout().activate()
        bar = self.scroll.verticalScrollBar()
        signature = (self.content.size(), bar.maximum(), self.scroll.viewport().size())
        bar.setValue(min(self.pending, bar.maximum()))
        if signature == self._signature:
            self.pending = None
        else:
            self._signature = signature
            self._timer.start(0)

    def refont(self):
        color = theme.color
        self.setStyleSheet(f"""
            QPushButton#section_choice {{ background: {color('surface')}; color: {color('ink')};
                border: 1px solid {color('border')}; border-radius: {theme.RADIUS['dense_control']}px; padding: 0;
                min-height: 0; max-height: 16777200px; min-width: 0; }}
            QPushButton#section_choice:hover {{ background: {color('hover')}; }}
            QPushButton#section_choice:checked {{ background: {color('primary')}; border-color: {color('primary')}; }}
            QPushButton#section_choice:focus {{ border: 2px dashed {color('focus')}; }}
            QPushButton#section_choice:checked:focus {{ border: 2px dashed {color('primary_ink')}; }}
            QPushButton#section_choice:disabled {{ background: {color('surface_alt')}; border-color: transparent; }}
            QPushButton#section_choice:checked:disabled {{ background: {color('selection')}; }}
        """)
        self._place()

    def _place(self):
        if not self.buttons:
            return
        buttons = list(self.buttons.values())
        width = max(1, self.navigation.width())
        for button in buttons:
            button.expanded = self.window().height() >= 700 and width >= 1100
        needed = [max(button.sizeHint().width(), button.minimumSizeHint().width()) for button in buttons]
        equal_minimum = max(button.minimumSizeHint().width() for button in buttons) * len(buttons)
        single_line = width >= max(sum(needed), equal_minimum) + self.grid.spacing() * (len(buttons) - 1)
        columns = len(buttons) if single_line else min(2, len(buttons))
        if columns != self.columns:
            self.columns = columns
            for button in buttons:
                self.grid.removeWidget(button)
            for number, button in enumerate(buttons):
                self.grid.addWidget(button, number // columns, number % columns)
        available = max(1, width - self.grid.spacing() * (columns - 1))
        widths = [max(1, available // columns)] * len(buttons)
        for column in range(len(buttons)):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        height = max(button.heightForWidth(cell_width) for button, cell_width in zip(buttons, widths))
        for button in buttons:
            button.setFixedHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def eventFilter(self, target, event):
        if target is self.scroll.viewport() and event.type() == QEvent.Type.Wheel:
            self._cancel_restore()
        if target is self.navigation and event.type() == QEvent.Type.Resize:
            self._place()
        if target is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            gutter = self.scroll.width() - self.scroll.viewport().width()
            self.navigation_column.layout().setContentsMargins(0, 0, gutter, 0)
            self._place()
        if target in self.buttons.values() and event.type() == QEvent.Type.KeyPress:
            buttons = list(self.buttons.values())
            at, key = buttons.index(target), event.key()
            moves = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1,
                     Qt.Key.Key_Up: -self.columns, Qt.Key.Key_Down: self.columns}
            if key in moves or key in (Qt.Key.Key_Home, Qt.Key.Key_End):
                index = 0 if key == Qt.Key.Key_Home else len(buttons) - 1 if key == Qt.Key.Key_End else (at + moves[key]) % len(buttons)
                if index != at:
                    buttons[index].setFocus(Qt.FocusReason.TabFocusReason)
                    self.select(buttons[index].key)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not event.isAutoRepeat():
                    target.click()
                return True
        return super().eventFilter(target, event)
