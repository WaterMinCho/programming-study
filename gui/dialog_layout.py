# -*- coding: utf-8 -*-
"""제목·스크롤 본문·고정 동작 영역을 같은 기준으로 배치함."""
from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QVBoxLayout, QWidget

from gui import kit, theme


class ActionLayout(QLayout):
    """보조 동작은 왼쪽, 확인 동작은 오른쪽에 두고 실제 글자 폭에 따라 줄을 나눔."""

    def __init__(self, parent):
        super().__init__(parent)
        self.items, self.left_count = [], 0
        self.setContentsMargins(32, 16, 32, 24)
        self.setSpacing(8)

    def set_actions(self, left, right):
        while self.count():
            self.takeAt(0)
        self.left_count = len(left)
        for button in left + right:
            self.addWidget(button)
        self.invalidate()

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self):
        return True

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            if not item.isEmpty():
                size = size.expandedTo(item.sizeHint())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def sizeHint(self):
        return self.minimumSize()

    def heightForWidth(self, width):
        return self.place(QRect(0, 0, width, 0), False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.place(rect, True)

    def place(self, rect, move):
        left, top, right, bottom = self.getContentsMargins()
        area = rect.adjusted(left, top, -right, -bottom)
        groups = [[item for item in group if not item.isEmpty()]
                  for group in (self.items[:self.left_count], self.items[self.left_count:])]
        gap, y = self.spacing(), area.y()

        def width(items):
            return sum(item.sizeHint().width() for item in items) + max(0, len(items) - 1) * gap

        def row(items, x, at_y, full=False):
            height = max((item.sizeHint().height() for item in items), default=0)
            for item in items:
                size = item.sizeHint()
                if move:
                    item.setGeometry(QRect(QPoint(x, at_y + (height - size.height()) // 2),
                                           QSize(area.width() if full else size.width(), size.height())))
                x += size.width() + gap
            return height

        first, last = groups
        if width(first) + width(last) + (gap if first and last else 0) <= area.width():
            return top + max(row(first, area.x(), y), row(last, area.right() + 1 - width(last), y)) + bottom
        if first:
            pending = []
            for item in first:
                if pending and width(pending + [item]) > area.width():
                    y += row(pending, area.x(), y) + gap
                    pending = []
                pending.append(item)
            y += row(pending, area.x(), y)
            if last:
                y += gap
        if last and width(last) <= area.width():
            y += row(last, area.right() + 1 - width(last), y)
        else:
            for number, item in enumerate(last):
                y += row([item], area.x(), y, True) + (gap if number < len(last) - 1 else 0)
        return y - rect.y() + bottom


class DialogLayout(QVBoxLayout):
    """본문이 길어져도 제목과 하단 단추에 계속 접근할 수 있게 함."""

    def __init__(self, dialog, title):
        super().__init__(dialog)
        kit.page(dialog)
        self.dialog = dialog
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(0)
        self.header = kit.frame("dialog_header")
        self.title = kit.para(title, "headline", bold=True)
        kit.box(self.header, (32, 32, 32, 16)).addWidget(self.title)
        self.addWidget(self.header)
        self.body = QWidget()
        self.content = kit.box(self.body, (32, 8, 32, 24), theme.GAP["paragraph"])
        self.content.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll = kit.scroll(self.body)
        self.scroll.setObjectName("dialog_scroll")
        self.body.setObjectName("dialog_body")
        self.addWidget(self.scroll, 1)
        self.footer = kit.frame("dialog_actions")
        self.actions = ActionLayout(self.footer)
        self.addWidget(self.footer)

    def fit(self, preferred_width=640, preferred_height=0):
        dialog = self.dialog
        room = dialog.screen().availableGeometry()
        parent = dialog.parentWidget()
        max_width = min(room.width() - 32, parent.width() - 32 if parent is not None else room.width() - 32)
        max_height = min(room.height() - 64, parent.height() - 32 if parent is not None else room.height() - 64)
        width = max(self.minimumSize().width(), min(preferred_width, max_width))
        self.activate()
        body_width = width - self.scroll.verticalScrollBar().sizeHint().width()
        body_height = max(self.content.minimumSize().height(), self.content.totalHeightForWidth(body_width))
        fixed = 0
        for index in range(self.count()):
            widget = self.itemAt(index).widget()
            if widget is not self.scroll and not widget.isHidden():
                fixed += max(widget.minimumSizeHint().height(), widget.heightForWidth(width))
        height = fixed + body_height + 2 * self.scroll.frameWidth()
        dialog.resize(width, min(max_height, max(preferred_height, height)))
