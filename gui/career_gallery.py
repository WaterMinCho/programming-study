"""매거진의 로컬 표지와 영상 목록을 창 폭과 글자 크기에 맞춰 배치함."""
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QImageReader, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QAbstractButton, QBoxLayout, QGridLayout, QSizePolicy, QWidget

from gui import kit, theme

COVERS = Path(__file__).resolve().parents[1] / "career" / "covers"


class VideoCover(QAbstractButton):
    def __init__(self, video):
        super().__init__()
        self.video = video
        self.image = None
        self.setAccessibleName(f"{video.title} 재생")
        self.setAccessibleDescription(f"{video.author} · {video.duration_label}")
        self.setToolTip(f"{video.title} 재생")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCheckable(True)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def nextCheckState(self):
        # 현재 영상은 페이지에서 선택한 뒤에만 바뀜.
        pass

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 첫 번째 클릭에서 이미 재생을 요청했음.
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def heightForWidth(self, width):
        return round(width * 9 / 16)

    def sizeHint(self):
        return QSize(256, 144)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not event.isAutoRepeat():
                self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _load_cover(self):
        reader = QImageReader(str(COVERS / f"{self.video.video_id}.webp"))
        size = reader.size()
        if size.width() > 1280:
            reader.setScaledSize(size.scaled(1280, 720, Qt.AspectRatioMode.KeepAspectRatio))
        return QPixmap.fromImage(reader.read()) if size.isValid() else QPixmap()

    def paintEvent(self, event):
        if self.image is None:
            self.image = self._load_cover()
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect())
        radius = theme.RADIUS["control"]
        outline = QPainterPath()
        outline.addRoundedRect(area, radius, radius)
        painter.setClipPath(outline)
        if self.image.isNull():
            gradient = QLinearGradient(area.topLeft(), area.bottomRight())
            gradient.setColorAt(0, theme.qcolor("selection"))
            gradient.setColorAt(1, theme.qcolor("surface_alt"))
            painter.fillPath(outline, gradient)
            painter.setPen(theme.qcolor("selection_ink"))
            painter.setFont(theme.font("headline", True))
            painter.drawText(area.adjusted(16, 8, -16, -8), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             self.video.topic)
        else:
            painter.drawPixmap(area, self.image, QRectF(self.image.rect()))

        painter.setFont(theme.font("caption", True))
        metrics = painter.fontMetrics()
        height = max(24, metrics.height() + 6)
        inset = theme.GAP["detail"]
        base = QColor(13, 21, 32, 218)
        badge = QRectF(inset, area.height() - height - inset, height, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(base)
        painter.drawEllipse(badge)
        cx, cy = badge.center().x(), badge.center().y()
        side = height * .20
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawPolygon(QPolygonF([QPointF(cx - side * .6, cy - side), QPointF(cx - side * .6, cy + side),
                                       QPointF(cx + side, cy)]))
        duration = self.video.duration_label
        width = metrics.horizontalAdvance(duration) + 14
        time_box = QRectF(area.width() - width - inset, badge.top(), width, height)
        painter.setBrush(base)
        painter.drawRoundedRect(time_box, 6, 6)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(time_box, Qt.AlignmentFlag.AlignCenter, duration)
        if self.hasFocus() or self.isChecked() or (self.underMouse() and self.isEnabled()):
            # 밝거나 어두운 사진 위에서도 초점 테두리가 보이도록 두 색으로 그림.
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(theme.qcolor("focus"), 3))
            painter.drawRoundedRect(area.adjusted(1.5, 1.5, -1.5, -1.5), radius, radius)
            if self.hasFocus():
                painter.setPen(QPen(theme.qcolor("surface"), 2))
                painter.drawRoundedRect(area.adjusted(4, 4, -4, -4), radius - 2, radius - 2)


class VideoCard(QWidget):
    def __init__(self, video):
        super().__init__()
        self.setProperty("reading_anchor", True)
        box = kit.box(self)
        self.cover = VideoCover(video)
        box.addWidget(self.cover)
        box.addSpacing(theme.GAP["title_description"])
        self.related_note = kit.para("로드맵에서 연 영상", "caption", "secondary")
        box.addWidget(self.related_note)
        self.related_note.hide()
        self.title = kit.para(video.title, "label", bold=True)
        box.addWidget(self.title)
        box.addStretch(1)
        box.addSpacing(theme.GAP["detail"])
        byline = QWidget()
        line = kit.box(byline, spacing=theme.GAP["detail"], horizontal=True)
        self.author = kit.ElideLabel(video.author, "caption", "secondary")
        line.addWidget(self.author, 1)
        self.info = kit.button("영상 정보", "text", "s")
        self.info.setAccessibleName(f"{video.title} 영상 정보")
        line.addWidget(self.info)
        box.addWidget(byline)
        self.error = kit.para("", "caption", "danger")
        self.error.hide()
        box.addWidget(self.error)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.cover.setFixedHeight(self.cover.heightForWidth(event.size().width()))


class VideoGallery(QWidget):
    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(theme.GAP["group"])
        self.grid.setVerticalSpacing(32)
        self.columns = 0
        self.cards = []

    def set_cards(self, cards):
        for card in self.cards:
            self.grid.removeWidget(card)
            card.hide()
        self.cards = list(cards)
        self.columns = 0
        self.refont()

    def refont(self):
        gap = self.grid.horizontalSpacing()
        card_width = max(276, theme.TYPE["label"][0] * 15)
        columns = max(1, min(3, (self.width() + gap) // (card_width + gap)))
        if self.columns == columns:
            return
        self.columns = columns
        for i in range(3):
            self.grid.setColumnStretch(i, int(i < columns))
        for i, card in enumerate(self.cards):
            self.grid.addWidget(card, i // columns, i % columns)
            card.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refont()


class VideoFilters(QWidget):
    def __init__(self, search, origin):
        super().__init__()
        self.search, self.origin = search, origin
        self.line = kit.box(self, spacing=theme.GAP["title_description"], horizontal=True)
        self.line.addWidget(search, 1)
        self.line.addWidget(origin)
        self.refont()

    def refont(self):
        self.origin.setMinimumHeight(self.search.sizeHint().height())
        search_width = self.search.fontMetrics().horizontalAdvance(self.search.placeholderText()) + 48
        wide = self.width() >= search_width + self.line.spacing() + self.origin.sizeHint().width()
        self.line.setDirection(QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refont()
