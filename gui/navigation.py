# -*- coding: utf-8 -*-
"""과목 이동 단추의 아이콘과 글자를 같은 좌표에 배치함."""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QIcon, QPainterPath, QPen
from PyQt6.QtWidgets import QPushButton, QStyle, QStyleOptionButton, QStylePainter

from gui import kit, theme


class NavigationButton(QPushButton):
    def __init__(self, key, title, depth=0):
        super().__init__(title)
        self.key = key
        self.depth = depth
        self.setObjectName("text")
        self.setProperty("navigation", True)
        self.setProperty("scale", "l")
        self.setCheckable(True)
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(title)
        self.setToolTip(title)
        kit.typed(self, "label")
        self.refont()

    def refont(self):
        self.setMinimumHeight(max(56, theme.TYPE["label"][1] + 24))
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(max(200, self.fontMetrics().horizontalAdvance(self.text()) + 80 + 12 * self.depth), self.minimumHeight())

    def text_rect(self):
        left = 48 + 12 * self.depth
        right = 36 if self.key == "career" else 16
        return QRectF(left, 0, max(0, self.width() - left - right), self.height())

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text, option.icon = "", QIcon()
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        color = theme.qcolor("faint" if not self.isEnabled() else "selection_ink" if self.isChecked() else "muted")
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.save()
        painter.translate(16 + 12 * self.depth, (self.height() - 20) / 2)
        if self.key == "hub":
            for x, y in ((1, 1), (12, 1), (1, 12), (12, 12)):
                painter.drawRoundedRect(QRectF(x, y, 7, 7), 1.5, 1.5)
        elif self.key == "python":
            path = QPainterPath(QPointF(6, 4))
            path.lineTo(1, 10)
            path.lineTo(6, 16)
            path.moveTo(14, 4)
            path.lineTo(19, 10)
            path.lineTo(14, 16)
            path.moveTo(11, 2)
            path.lineTo(9, 18)
            painter.drawPath(path)
        elif self.key == "journey":
            painter.drawRoundedRect(QRectF(7, 1, 6, 5), 1, 1)
            painter.drawRoundedRect(QRectF(0.5, 14, 6, 5), 1, 1)
            painter.drawRoundedRect(QRectF(13.5, 14, 6, 5), 1, 1)
            painter.drawLine(QPointF(10, 6), QPointF(10, 10))
            painter.drawLine(QPointF(3.5, 10), QPointF(16.5, 10))
            painter.drawLine(QPointF(3.5, 10), QPointF(3.5, 14))
            painter.drawLine(QPointF(16.5, 10), QPointF(16.5, 14))
        elif self.key == "career":
            painter.drawRoundedRect(QRectF(1, 6, 18, 13), 2, 2)
            painter.drawRoundedRect(QRectF(6, 1, 8, 5), 1, 1)
            painter.drawLine(QPointF(1, 11), QPointF(19, 11))
        elif self.key == "career_roadmap":
            path = QPainterPath(QPointF(1, 3))
            for x, y in ((7, 1), (13, 4), (19, 2), (19, 17), (13, 19), (7, 16), (1, 18)):
                path.lineTo(x, y)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(QPointF(7, 1), QPointF(7, 16))
            painter.drawLine(QPointF(13, 4), QPointF(13, 19))
        elif self.key == "career_magazine":
            painter.drawRoundedRect(QRectF(1, 1, 18, 18), 2, 2)
            path = QPainterPath(QPointF(8, 6))
            path.lineTo(14, 10)
            path.lineTo(8, 14)
            path.closeSubpath()
            painter.drawPath(path)
        else:
            painter.drawRoundedRect(QRectF(1, 2, 18, 13), 2, 2)
            painter.drawLine(QPointF(6, 19), QPointF(14, 19))
            painter.drawLine(QPointF(10, 15), QPointF(10, 19))
            if self.key == "ai":
                painter.drawEllipse(QPointF(7, 8), 1.5, 1.5)
                painter.drawEllipse(QPointF(14, 7), 1.5, 1.5)
                painter.drawLine(QPointF(8.5, 8), QPointF(12.5, 7))
        painter.restore()
        painter.setFont(theme.font("label", self.isChecked()))
        painter.setPen(color)
        painter.drawText(self.text_rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        if self.key == "career":
            x, y = self.width() - 22, self.height() / 2
            if self.property("expanded"):
                painter.drawLine(QPointF(x - 4, y - 2), QPointF(x, y + 2))
                painter.drawLine(QPointF(x, y + 2), QPointF(x + 4, y - 2))
            else:
                painter.drawLine(QPointF(x - 2, y - 4), QPointF(x + 2, y))
                painter.drawLine(QPointF(x + 2, y), QPointF(x - 2, y + 4))
