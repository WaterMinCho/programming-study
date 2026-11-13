"""직무 로드맵의 보이는 부분을 원본 좌표로 찾아 그리는 확대창."""

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import QAbstractScrollArea, QDialog, QFrame

from gui import kit, motion, theme
from gui.dialog_layout import ActionLayout


class RoadmapCanvas(QAbstractScrollArea):
    scale_changed = pyqtSignal(float)
    STEP = 1.25

    def __init__(self, pixmap, title):
        super().__init__()
        self.original = pixmap
        self.scale = 1.0
        self.fitted = True
        self.drag_position = None
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)

    def _origin(self):
        x = max(0, (self.viewport().width() - self.original.width() * self.scale) / 2)
        return QPointF(x - self.horizontalScrollBar().value(), -self.verticalScrollBar().value())

    def source_point(self, position):
        return (QPointF(position) - self._origin()) / self.scale

    def _ranges(self):
        viewport = self.viewport()
        for bar, length, page in ((self.horizontalScrollBar(), self.original.width(), viewport.width()),
                                  (self.verticalScrollBar(), self.original.height(), viewport.height())):
            bar.setPageStep(page)
            bar.setSingleStep(32)
            bar.setRange(0, max(0, round(length * self.scale) - page))

    def _set_scale(self, scale, anchor):
        source = self.source_point(anchor)
        self.scale = scale
        self._ranges()
        delta = self._origin() + source * scale - anchor
        for bar, distance in ((self.horizontalScrollBar(), delta.x()), (self.verticalScrollBar(), delta.y())):
            bar.setValue(bar.value() + round(distance))
        self.viewport().update()
        self.scale_changed.emit(scale)

    def zoom(self, scale, anchor=None):
        self.fitted = False
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        if anchor is None:
            anchor = QRectF(self.viewport().rect()).center()
        self._set_scale(max(0.1, min(4.0, scale)), anchor)

    def fit_width(self):
        self.fitted = True
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._set_scale(max(1, self.viewport().width()) / self.original.width(), QPointF())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fitted:
            self.fit_width()
        else:
            self._ranges()

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), theme.qcolor("surface_alt"))
        origin = self._origin()
        image = QRectF(origin, self.original.size().toSizeF() * self.scale)
        visible = image.intersected(QRectF(event.rect()))
        if not visible.isEmpty():
            source = QRectF(self.source_point(visible.topLeft()), visible.size() / self.scale)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(visible, self.original, source)

    def scrollContentsBy(self, dx, dy):
        self.viewport().update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self.drag_position = event.position()
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_position is None:
            return super().mouseMoveEvent(event)
        delta = event.position() - self.drag_position
        self.drag_position = event.position()
        self._pan(delta)
        event.accept()

    def _pan(self, delta):
        horizontal, vertical = self.horizontalScrollBar(), self.verticalScrollBar()
        horizontal.setValue(horizontal.value() - round(delta.x()))
        vertical.setValue(vertical.value() - round(delta.y()))

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)
        self.drag_position = None
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()

    def wheelEvent(self, event):
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            delta = event.pixelDelta().y() or event.angleDelta().y()
            if delta:
                self.zoom(self.scale * self.STEP ** max(-8, min(8, delta / 120)), event.position())
        elif not event.pixelDelta().isNull():
            self._pan(event.pixelDelta())
        else:
            return super().wheelEvent(event)
        event.accept()

    def viewportEvent(self, event):
        if (event.type() == QEvent.Type.NativeGesture
                and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture):
            self.zoom(self.scale * (1 + event.value()), event.position())
            event.accept()
            return True
        return super().viewportEvent(event)


class RoadmapImageDialog(QDialog):
    """부모 창이 있는 모니터에서 최대화하고 운영체제의 창 복원을 사용함."""
    def __init__(self, pixmap, title, parent):
        flags = (Qt.WindowType.Window | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowSystemMenuHint
                 | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        super().__init__(parent, flags)
        kit.page(self)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowTitle(title + " 로드맵")
        self._closing = False
        layout = kit.box(self)
        header = kit.frame("dialog_header")
        header_box = kit.box(header, (24, 8, 24, 8), spacing=16, horizontal=True)
        header_box.addWidget(kit.para(self.windowTitle(), "headline"), 1)
        self.window_size = kit.button("창 최대화", "text", "s")
        self.window_size.clicked.connect(self.toggle_maximized)
        header_box.addWidget(self.window_size)
        layout.addWidget(header)
        self.area = RoadmapCanvas(pixmap, self.windowTitle())
        hint = "드래그로 이동 · Ctrl/⌘ + 휠로 확대·축소"
        self.area.setAccessibleDescription(hint)
        self.area.viewport().setToolTip(hint)
        layout.addWidget(self.area, 1)
        footer = kit.frame("dialog_actions")
        layout.addWidget(footer)
        self.less = kit.button("−")
        self.more = kit.button("+")
        self.percent = kit.label("", "body", align=Qt.AlignmentFlag.AlignCenter)
        self.percent.setMinimumWidth(self.percent.fontMetrics().horizontalAdvance("100%") + 8)
        self.fit = kit.button("폭에 맞추기")
        self.close_button = kit.button("닫기")
        actions = ActionLayout(footer)
        actions.setContentsMargins(24, 8, 24, 8)
        actions.set_actions([self.less, self.percent, self.more, self.fit], [self.close_button])
        for button, label, keys, callback in (
            (self.less, "축소", ("-",), lambda: self.area.zoom(self.area.scale / self.area.STEP)),
            (self.more, "확대", ("+", "="), lambda: self.area.zoom(self.area.scale * self.area.STEP)),
            (self.fit, "폭에 맞추기", ("F", "0"), self.area.fit_width),
        ):
            button.setAccessibleName(label)
            button.setToolTip(f"{label} ({keys[0]})")
            button.clicked.connect(callback)
            for key in keys:
                QShortcut(QKeySequence(key), self).activated.connect(callback)
        self.close_button.setToolTip("닫기 (Esc)")
        self.close_button.clicked.connect(self.accept)
        self.area.scale_changed.connect(self._scale_changed)
        self.setFocusProxy(self.area)
        screen = parent.window().screen()
        self.setScreen(screen)
        room = screen.availableGeometry()
        self.resize(round(room.width() * 0.84), round(room.height() * 0.84))
        self.move(room.center() - self.rect().center())

    def _scale_changed(self, scale):
        self.percent.setText(f"{round(scale * 100)}%")
        self.less.setEnabled(scale > 0.1)
        self.more.setEnabled(scale < 4)

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.window_size.setText("창 크기 복원" if self.isMaximized() else "창 최대화")

    def showEvent(self, event):
        super().showEvent(event)
        self.area.setFocus()
        if motion.enabled:
            motion.fade_opacity(self, True, self._finish_opening)

    def _finish_opening(self):
        self.setGraphicsEffect(None)
        self._opacity_effect = None

    def done(self, result):
        if self._closing:
            return
        self._closing = True
        if motion.enabled and self.isVisible():
            self.setEnabled(False)
            motion.fade_opacity(self, False, lambda: super(RoadmapImageDialog, self).done(result))
        else:
            super().done(result)
