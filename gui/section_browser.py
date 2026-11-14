"""분류 선택을 고정하고 선택한 목록의 읽던 위치를 보관함."""
import math

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF, QIcon, QPen
from PyQt6.QtWidgets import (QButtonGroup, QGridLayout, QPushButton, QSizePolicy,
                             QStyle, QStyleOptionButton, QStylePainter, QWidget)

from gui import kit, theme


class SectionButton(QPushButton):
    """긴 분류 이름을 줄이지 않고 같은 글자 시작점에 그림."""
    def __init__(self, key, title, description):
        super().__init__(title)
        self.key = key
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
        return QSize(math.ceil(metrics.horizontalAdvance(self.text())) + 40,
                     max(48, theme.TYPE["label"][1] + 24))

    def minimumSizeHint(self):
        return QSize(80, self.sizeHint().height())

    def heightForWidth(self, width):
        metrics = QFontMetricsF(theme.font("label", True))
        bounds = metrics.boundingRect(QRectF(0, 0, max(1, width - 40), 1000),
                                      Qt.TextFlag.TextWordWrap, self.text())
        return max(self.sizeHint().height(), math.ceil(bounds.height()) + 24)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text, option.icon = "", QIcon()
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        painter.setFont(theme.font("label", True))
        painter.setPen(theme.qcolor("selection_ink" if self.isChecked() else "ink"))
        painter.drawText(QRectF(self.rect()).adjusted(20, 8, -20, -8),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                         self.text())
        if self.isChecked():
            painter.setPen(QPen(theme.qcolor("link"), 3))
            painter.drawLine(2, 12, 2, self.height() - 12)


class SectionBrowser(QWidget):
    """같은 분류 선택과 스크롤을 여러 과정에서 재사용함. 상태는 메모리에만 둠."""
    def __init__(self, parent=None):
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
        self.navigation_column = kit.column(self.navigation)
        self.navigation_column.setContentsMargins(kit.MARGIN, 0, kit.MARGIN, 0)
        outer.addWidget(self.navigation_column)
        self.content = QWidget()
        self.body = kit.box(self.content, (0, 16, 0, 48), 16)
        column = kit.column(self.content)
        column.setContentsMargins(kit.MARGIN, 0, kit.MARGIN, 0)
        self.scroll = kit.scroll(column)
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
                border: 1px solid {color('line')}; border-radius: 8px; padding: 0;
                min-height: 0; max-height: 16777200px; min-width: 0; }}
            QPushButton#section_choice:hover {{ background: {color('hover')}; }}
            QPushButton#section_choice:checked {{ background: {color('selection')}; border-color: {color('link')}; }}
            QPushButton#section_choice:focus {{ border: 2px solid {color('focus')}; }}
        """)
        self._place()

    def _place(self):
        if not self.buttons:
            return
        buttons = list(self.buttons.values())
        width = max(1, self.navigation.width())
        needed = max(button.sizeHint().width() for button in buttons)
        columns = len(buttons) if width >= needed * len(buttons) + 8 * (len(buttons) - 1) else min(2, len(buttons))
        if columns != self.columns:
            self.columns = columns
            for button in buttons:
                self.grid.removeWidget(button)
            for number, button in enumerate(buttons):
                self.grid.addWidget(button, number // columns, number % columns)
            for column in range(len(buttons)):
                self.grid.setColumnStretch(column, 1 if column < columns else 0)
        cell_width = max(1, (width - 8 * (columns - 1)) // columns)
        height = max(button.heightForWidth(cell_width) for button in buttons)
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
            self.navigation_column.setContentsMargins(kit.MARGIN, 0, kit.MARGIN + gutter, 0)
            self._place()
        if target in self.buttons.values() and event.type() == QEvent.Type.KeyPress:
            buttons = list(self.buttons.values())
            at, key = buttons.index(target), event.key()
            moves = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1,
                     Qt.Key.Key_Up: -self.columns, Qt.Key.Key_Down: self.columns}
            if key in moves or key in (Qt.Key.Key_Home, Qt.Key.Key_End):
                index = 0 if key == Qt.Key.Key_Home else len(buttons) - 1 if key == Qt.Key.Key_End else (at + moves[key]) % len(buttons)
                buttons[index].setFocus(Qt.FocusReason.TabFocusReason)
                self.select(buttons[index].key)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not event.isAutoRepeat():
                    target.click()
                return True
        return super().eventFilter(target, event)
