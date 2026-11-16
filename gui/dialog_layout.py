# -*- coding: utf-8 -*-
"""제목·스크롤 본문·고정 동작 영역을 같은 기준으로 배치함."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from gui import kit, theme
from gui.action_layout import ActionLayout


class DialogLayout(QVBoxLayout):
    """본문이 길어져도 제목과 하단 단추에 계속 접근할 수 있게 함."""

    def __init__(self, dialog, title, description=""):
        super().__init__(dialog)
        kit.page(dialog)
        self.dialog = dialog
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(0)
        self.header = kit.frame("dialog_header")
        self.title = kit.para(title, "headline", bold=True)
        heading = self.title
        if description:
            heading = kit.heading(self.title, kit.para(description, "body", "secondary"))
        kit.box(self.header, (32, 24, 32, 16 if description else 12)).addWidget(heading)
        self.addWidget(self.header)
        self.body = QWidget()
        self.content = kit.box(self.body, (32, 16, 32, 24), theme.GAP["paragraph"])
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
        body_height = max(self.scroll.minimumSizeHint().height(), self.content.minimumSize().height(),
                          self.content.totalHeightForWidth(body_width))
        fixed = 0
        for index in range(self.count()):
            widget = self.itemAt(index).widget()
            if widget is not self.scroll and not widget.isHidden():
                fixed += max(widget.minimumSizeHint().height(), widget.heightForWidth(width))
        height = fixed + body_height + 2 * self.scroll.frameWidth()
        dialog.resize(width, min(max_height, max(preferred_height, height)))
