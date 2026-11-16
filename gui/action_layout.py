# -*- coding: utf-8 -*-
"""팝업과 하단 동작의 폭·높이·줄바꿈을 같은 계산으로 배치함."""
from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QSizePolicy, QSpacerItem


class ActionLayout(QLayout):
    """보조 동작은 왼쪽, 확인 동작은 오른쪽에 두고 실제 글자 폭에 따라 줄을 나눔."""

    def __init__(self, parent, margins=(32, 16, 32, 24), spacing=8, reverse_stacked=True):
        super().__init__(parent)
        self.items, self.left_count = [], 0
        self.reverse_stacked = reverse_stacked
        self.setContentsMargins(*margins)
        self.setSpacing(spacing)

    def set_actions(self, left, right):
        while self.count():
            self.takeAt(0)
        self.left_count = len(left)
        for button in left + right:
            self.addWidget(button)
        self.invalidate()

    def addItem(self, item):
        self.items.append(item)
        self.invalidate()

    def addSpacing(self, width):
        self.addItem(QSpacerItem(width, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        if not 0 <= index < len(self.items):
            return None
        item = self.items.pop(index)
        if index < self.left_count:
            self.left_count -= 1
        self.invalidate()
        return item

    def expandingDirections(self):
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self):
        return True

    def _groups(self):
        groups = []
        for source in (self.items[:self.left_count], self.items[self.left_count:]):
            items = [item for item in source if item.spacerItem() is not None or
                     (item.widget() is not None and item.widget().isVisibleTo(item.widget().parentWidget())) or
                     (item.widget() is None and not item.isEmpty())]
            while items and items[0].spacerItem() is not None:
                items.pop(0)
            while items and items[-1].spacerItem() is not None:
                items.pop()
            groups.append(items)
        return groups

    @staticmethod
    def _size(item):
        return item.sizeHint().expandedTo(item.minimumSize())

    def _width(self, items):
        controls = sum(item.spacerItem() is None for item in items)
        return sum(self._size(item).width() for item in items) + max(0, controls - 1) * self.spacing()

    def natural_width(self):
        """보이는 동작을 한 줄에 놓는 데 필요한 폭과 바깥 여백을 합함."""
        first, last = self._groups()
        left, _, right, _ = self.getContentsMargins()
        return left + self._width(first) + self._width(last) + (self.spacing() if first and last else 0) + right

    def minimumSize(self):
        size = QSize()
        for group in self._groups():
            for item in group:
                size = size.expandedTo(self._size(item))
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
        groups = self._groups()
        gap, y = self.spacing(), area.y()

        width = self._width

        def row(items, x, at_y, full=False):
            height = max((self._size(item).height() for item in items), default=0)
            for item in items:
                size = self._size(item)
                if move:
                    item.setGeometry(QRect(QPoint(x, at_y + (height - size.height()) // 2),
                                           QSize(area.width() if full else size.width(), size.height())))
                x += size.width() + (gap if item.spacerItem() is None else 0)
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
            buttons = [item for item in last if item.spacerItem() is None]
            if self.reverse_stacked:
                buttons.reverse()
            for number, item in enumerate(buttons):
                y += row([item], area.x(), y, True) + (gap if number < len(buttons) - 1 else 0)
        return y - rect.y() + bottom

