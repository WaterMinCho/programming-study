"""기존 직무의 업무 그림·이름·산출물을 고르는 목록을 표시함."""
import math

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap, QTextLayout, QTextOption
from PyQt6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

from gui import theme
from gui.career_scene import SCENES


class RoleCard(QAbstractButton):
    def __init__(self, role, parent=None):
        super().__init__(parent)
        self.role = role
        self.saved = False
        self.compact = False
        self._row_title_height = 0
        self._layouts = {}
        self.image = QPixmap(str(SCENES / f"{role['id']}.webp"))
        self.setProperty("reading_anchor", True)
        self.setCheckable(True)
        self.setAutoRepeat(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.set_role(role)
        self.refont()
        theme.signals.changed.connect(self.update)

    def set_role(self, role):
        self.role = role
        self.setText(role["title"])
        self.setAccessibleName(role["title"])
        self._layouts.clear()
        self._describe()
        self.update()

    def _describe(self):
        text = self.role["outputs"][0]
        if self.saved:
            text += " · 관심 직무"
        self.setAccessibleDescription(text)
        self.setToolTip(self.role["title"] + "\n" + text)

    def set_saved(self, saved):
        self.saved = bool(saved)
        self._describe()
        self.update()

    def nextCheckState(self):
        # 선택은 목록에서 바꾸며 관심 직무 저장과 구분함.
        pass

    def refont(self):
        self.setFont(theme.font("body", True))
        self._layouts.clear()
        self.updateGeometry()
        self.update()

    def _text_layout(self, name, width):
        title = name == "title"
        role = "body" if title else "caption"
        text = self.role["title"] if title else self.role["outputs"][0]
        font = self.font() if title else theme.font(role)
        key = (name, width, text, font.toString(), theme.TYPE[role][1])
        if key not in self._layouts:
            layout = QTextLayout(text, font)
            option = QTextOption()
            option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            layout.setTextOption(option)
            layout.beginLayout()
            height = 0
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(max(1, width))
                step = max(theme.TYPE[role][1], math.ceil(line.height()))
                line.setPosition(QPointF(0, height + (step - line.height()) / 2))
                height += step
            layout.endLayout()
            if len(self._layouts) >= 8:
                self._layouts.clear()
            self._layouts[key] = (layout, height)
        return self._layouts[key]

    def _areas(self, width, compact):
        pad = theme.GAP["paragraph"]
        inner = max(1, width - 2 * pad)
        if compact:
            picture_width = min(160, inner / 3)
            picture = QRectF(pad, pad, picture_width, picture_width * 9 / 16)
            left = picture.right() + pad
            text = QRectF(left, pad, max(1, width - pad - left), 0)
        else:
            picture = QRectF(pad, pad, inner, min(160, inner / 2))
            text = QRectF(pad, picture.bottom() + theme.GAP["title_description"], inner, 0)
        return picture, text

    def _title_width(self, width):
        return max(1, width - (theme.TYPE["caption"][0] + theme.GAP["detail"] if self.saved else 0))

    def measure(self, width, compact):
        picture, text = self._areas(width, compact)
        title = self._text_layout("title", self._title_width(text.width()))[1]
        output = self._text_layout("output", text.width())[1]
        return picture, text, title, output

    def content_height(self, width, compact, title_height=0):
        picture, text, title, output = self.measure(width, compact)
        bottom = text.top() + max(title, title_height) + theme.GAP["title_description"] + output
        return math.ceil(max(picture.bottom(), bottom) + theme.GAP["paragraph"])

    @property
    def image_rect(self):
        return self._areas(self.width(), self.compact)[0]

    @property
    def text_rects(self):
        _, text, title, output = self.measure(self.width(), self.compact)
        title = max(title, self._row_title_height)
        return {
            "title": QRectF(text.left(), text.top(), self._title_width(text.width()), title),
            "output": QRectF(text.left(), text.top() + title + theme.GAP["title_description"], text.width(), output),
        }

    def sizeHint(self):
        width = math.ceil(QFontMetricsF(self.font()).horizontalAdvance("가" * 16)) + 2 * theme.GAP["paragraph"]
        return QSize(width, self.content_height(width, self.compact))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not event.isAutoRepeat():
                self.setDown(True)
            event.accept()
        elif event.key() == Qt.Key.Key_Space and event.isAutoRepeat():
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not event.isAutoRepeat() and self.isDown():
                self.setDown(False)
                self.click()
            event.accept()
        elif event.key() == Qt.Key.Key_Space and event.isAutoRepeat():
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        tone = "selection" if self.isChecked() or self.isDown() else "surface"
        if self.underMouse() and self.isEnabled() and tone == "surface":
            tone = "hover"
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor(tone))
        painter.drawRoundedRect(area, theme.RADIUS["card"], theme.RADIUS["card"])

        picture = self.image_rect
        clip = QPainterPath()
        clip.addRoundedRect(picture, theme.RADIUS["control"], theme.RADIUS["control"])
        painter.save()
        painter.setClipPath(clip)
        if self.image.isNull():
            painter.fillRect(picture, theme.qcolor("surface_alt"))
            center = picture.center()
            mark = QRectF(center.x() - 20, center.y() - 14, 40, 28)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(theme.qcolor("border_strong"), 2))
            painter.drawRoundedRect(mark, 4, 4)
            painter.drawEllipse(center + QPointF(9, -5), 3, 3)
            path = QPainterPath(center + QPointF(-16, 9))
            path.lineTo(center + QPointF(-5, -3))
            path.lineTo(center + QPointF(8, 10))
            painter.drawPath(path)
        else:
            source = QRectF(self.image.rect())
            scale = max(picture.width() / source.width(), picture.height() / source.height())
            width, height = picture.width() / scale, picture.height() / scale
            crop = QRectF((source.width() - width) / 2, (source.height() - height) / 2, width, height)
            painter.drawPixmap(picture, self.image, crop)
        painter.restore()

        for name, rect in self.text_rects.items():
            painter.setPen(theme.qcolor("ink" if name == "title" else "muted"))
            layout, _ = self._text_layout(name, rect.width())
            layout.draw(painter, rect.topLeft())
        if self.saved:
            title = self.text_rects["title"]
            size = theme.TYPE["caption"][0]
            x = title.right() + theme.GAP["detail"]
            y = title.top() + (theme.TYPE["body"][1] - size) / 2
            bookmark = QPainterPath(QPointF(x, y))
            for point in ((x + size, y), (x + size, y + size), (x + size / 2, y + size * .7), (x, y + size)):
                bookmark.lineTo(*point)
            bookmark.closeSubpath()
            painter.fillPath(bookmark, theme.qcolor("link"))
        if self.hasFocus() or self.isChecked():
            pen = QPen(theme.qcolor("focus" if self.hasFocus() else "link"), 3 if self.hasFocus() else 2)
            if self.hasFocus():
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(area, theme.RADIUS["card"], theme.RADIUS["card"])


class RoleGallery(QWidget):
    picked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {}
        self.selected_role_id = ""
        self.saved_role_id = ""
        self.columns = 1
        self._placing = False
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def set_roles(self, roles):
        previous = self.cards
        self.cards = {}
        for role in roles:
            key = role["id"]
            card = previous.pop(key, None)
            if card is None:
                card = RoleCard(role, self)
                card.clicked.connect(lambda checked=False, role_id=key: self._pick(role_id))
            else:
                card.set_role(role)
            card.setChecked(key == self.selected_role_id)
            card.set_saved(key == self.saved_role_id)
            self.cards[key] = card
        for card in previous.values():
            card.hide()
            card.deleteLater()
        ordered = list(self.cards.values())
        for first, second in zip(ordered, ordered[1:]):
            QWidget.setTabOrder(first, second)
        self._place()
        for card in ordered:
            card.show()

    def _pick(self, role_id):
        self.set_selected(role_id)
        self.picked.emit(role_id)

    def set_selected(self, role_id):
        self.selected_role_id = role_id or ""
        for key, card in self.cards.items():
            card.setChecked(key == self.selected_role_id)

    def set_saved(self, role_id):
        self.saved_role_id = role_id or ""
        for key, card in self.cards.items():
            card.set_saved(key == self.saved_role_id)
        self._place()

    def _rows(self, width):
        gap = theme.GAP["group"]
        minimum = math.ceil(QFontMetricsF(theme.font("body", True)).horizontalAdvance("가" * 16)) + 2 * theme.GAP["paragraph"]
        columns = max(1, min(3, (width + gap) // (minimum + gap)))
        card_width = max(1, (width - (columns - 1) * gap) // columns)
        cards = list(self.cards.values())
        y = 0
        placements = []
        for start in range(0, len(cards), columns):
            row = cards[start:start + columns]
            title_height = max(card.measure(card_width, columns == 1)[2] for card in row)
            height = max(card.content_height(card_width, columns == 1, title_height) for card in row)
            for index, card in enumerate(row):
                placements.append((card, index * (card_width + gap), y, card_width, height, title_height))
            y += height + gap
        return columns, max(0, y - gap), placements

    def heightForWidth(self, width):
        return self._rows(width)[1]

    def sizeHint(self):
        return QSize(960, self.heightForWidth(960))

    def minimumSizeHint(self):
        return QSize(0, 0)

    def _place(self):
        if self._placing:
            return
        self._placing = True
        try:
            self.columns, height, placements = self._rows(self.width())
            for card, x, y, width, card_height, title_height in placements:
                card.compact = self.columns == 1
                card._row_title_height = title_height
                card.setGeometry(x, y, width, card_height)
                card.update()
            self.setMinimumHeight(height)
            self.updateGeometry()
        finally:
            self._placing = False

    def refont(self):
        for card in self.cards.values():
            card.refont()
        self._place()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()
