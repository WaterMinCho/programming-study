"""접힌 내용 바로 위의 이름·화살표·클릭 영역을 함께 배치함."""
from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QPushButton, QSizePolicy, QWidget

from gui import kit, theme

KEY_MODIFIERS = (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
                 | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)


class DisclosureMark(QWidget):
    def __init__(self):
        super().__init__()
        self.opened = False
        self.setFixedSize(20, 20)

    def set_opened(self, opened):
        self.opened = bool(opened)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(theme.qcolor("muted" if self.isEnabled() else "faint"), 2,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        points = ((5, 7.5), (10, 12.5), (15, 7.5)) if self.opened else ((7.5, 5), (12.5, 10), (7.5, 15))
        path = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QPointF(*point))
        painter.drawPath(path)


class DisclosureButton(QPushButton):
    """본문과 글자 시작점을 맞추고 긴 이름도 줄바꿈하는 펼치기 단추임."""
    def __init__(self, text, *, role="body", bold=True, text_widget=None, arrow_keys=False):
        super().__init__(text)
        self.setObjectName("disclosure")
        self.setCheckable(True)
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow_keys = arrow_keys
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if arrow_keys else Qt.FocusPolicy.TabFocus)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        kit.typed(self, role, bold)
        self.label = text_widget if text_widget is not None else kit.para(text, role, "secondary", bold=bold)
        self.reserve = None
        if text_widget is None:
            self.reserve = kit.para(text, role, bold=bold)
            self.reserve.setParent(self)
            self.reserve.hide()
        self.arrow = DisclosureMark()
        self.pair = kit.FirstLine(self.arrow, self.label, trailing=True)
        self.mark = self.pair.mark_holder
        self.pair.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        kit.box(self, (0, 12, 0, 12)).addWidget(self.pair)
        self.toggled.connect(self._state_changed)
        self.setAccessibleName(text)
        self._state_changed(False)
        self.refont()

    def setText(self, text):
        super().setText(text)
        if hasattr(self, "label"):
            self.label.setText(text)
            self.setAccessibleName(text)
            self.refont()

    def _state_changed(self, opened):
        self.arrow.set_opened(opened)
        self.setAccessibleDescription("내용 펼쳐짐" if opened else "내용 접힘")
        self.update()

    def setChecked(self, opened):
        super().setChecked(opened)
        if hasattr(self, "arrow"):
            self._state_changed(self.isChecked())

    def refont(self):
        role = self.property("role")
        style = ("QPushButton#disclosure { padding: 0; margin: 0; border: none; min-width: 0; "
                 "min-height: 48px; max-height: 16777215px; font-size: %dpx; }" % theme.TYPE[role][0])
        if self.styleSheet() != style:
            self.setStyleSheet(style)
        kit.refont(self.label)
        if self.reserve is not None:
            kit.refont(self.reserve)
        self.pair.refont()
        self.updateGeometry()
        self.update()

    def heightForWidth(self, width):
        reserved = self.reserve.heightForWidth(max(1, width - 32)) + 24 if self.reserve is not None else 0
        return max(48, self.pair.layout().totalHeightForWidth(max(1, width)) + 24, reserved)

    def sizeHint(self):
        width = max(160, self.label.sizeHint().width() + 32)
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self):
        return QSize(80, 48)

    def event(self, event):
        if getattr(self, "arrow_keys", False) and event.type() == QEvent.Type.ShortcutOverride and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) \
                and not event.modifiers() & KEY_MODIFIERS:
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        key = event.key()
        keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter) + ((Qt.Key.Key_Left, Qt.Key.Key_Right) if self.arrow_keys else ())
        if not event.modifiers() & KEY_MODIFIERS and key in keys:
            if not event.isAutoRepeat():
                if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                    self.setChecked(key == Qt.Key.Key_Right)
                else:
                    self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.underMouse() and self.isEnabled() or self.isDown():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("hover"))
            painter.drawRoundedRect(rect, theme.RADIUS["small"], theme.RADIUS["small"])
        painter.setPen(QPen(theme.qcolor("line"), 1))
        painter.drawLine(QPointF(0, self.height() - 1), QPointF(self.width(), self.height() - 1))
        if self.hasFocus():
            painter.setPen(QPen(theme.qcolor("focus"), 2))
            painter.drawLine(QPointF(1, self.height() - 2), QPointF(self.width() - 1, self.height() - 2))
