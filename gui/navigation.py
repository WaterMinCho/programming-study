# -*- coding: utf-8 -*-
"""과목 이동 단추의 아이콘과 글자를 같은 좌표에 배치함."""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QIcon, QPainterPath, QPen
from PyQt6.QtWidgets import QPushButton, QStyle, QStyleOptionButton, QStylePainter

from gui import kit, theme


class NavigationButton(QPushButton):
    def __init__(self, key, title):
        super().__init__(title)
        self.key = key
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
        return QSize(max(200, self.fontMetrics().horizontalAdvance(self.text()) + 80), self.minimumHeight())

    def text_rect(self):
        return QRectF(48, 0, max(0, self.width() - 64), self.height())

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
        painter.translate(16, (self.height() - 20) / 2)
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
