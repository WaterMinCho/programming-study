# -*- coding: utf-8 -*-
"""수식의 입력·항·계산·출력을 기록 변경 없이 펼침."""
from types import SimpleNamespace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QWidget

from gui import kit, theme
from gui.dialog_layout import DialogLayout


class FormulaBlock(QWidget):
    """그림과 읽기 전용 설명을 별도 창에 둠. 답은 누른 뒤에만 표시함."""

    def __init__(self, block, ctx):
        super().__init__()
        self.block, self.ctx = block, ctx
        self.dialog, self.docs, self.picture = None, [], None
        self.button = kit.button("수식 자세히 보기", "secondary", "l")
        self.button.setToolTip(block["title"])
        self.button.clicked.connect(self.open_formula)
        kit.box(self).addWidget(self.button, 0, Qt.AlignmentFlag.AlignLeft)

    def open_formula(self):
        from gui.ai_learn import WhyBlock, doc, figure, learning_texts
        owner = self.window()
        if self.dialog is None:
            self.dialog = QDialog(owner)
            self.dialog.setModal(True)
            self.dialog.setWindowTitle(self.block["title"])
            self.destroyed.connect(self.dialog.deleteLater)
            self.panel = DialogLayout(self.dialog, self.block["title"])
            content = self.panel.content
            self.picture = figure(self.block["figure"])
            content.addWidget(self.picture)
            self.docs.append(doc("\n\n".join("### %s\n\n%s" % (title, self.block[key]) for key, title in (
                ("input", "점과 행렬의 모양"), ("terms", "행렬의 각 항"),
                ("operation", "행별 곱셈과 덧셈"), ("output", "출력 좌표와 역조회"))), self.ctx.base_dir, content))
            self.check = WhyBlock(self.block, SimpleNamespace(readonly=False))
            content.addWidget(self.check)
            self.close_button = kit.button("닫기", "secondary", "l")
            self.close_button.clicked.connect(self.dialog.close)
            self.panel.actions.set_actions([], [self.close_button])
            self.dialog.finished.connect(lambda _: self.button.setFocus(Qt.FocusReason.OtherFocusReason))
            learning_texts(self.panel.body)
        self.restyle()
        self.panel.fit(1000, 640)
        room = owner.screen().availableGeometry()
        frame = self.dialog.frameGeometry()
        frame.moveCenter(owner.frameGeometry().center())
        self.dialog.move(max(room.left(), min(frame.left(), room.right() - frame.width() + 1)),
                         max(room.top(), min(frame.top(), room.bottom() - frame.height() + 1)))
        self.dialog.show()

    def restyle(self):
        if self.dialog is None:
            return
        from gui.ai_learn import RichPara, learning_texts
        for piece in self.docs:
            piece.restyle(theme.learning_css())
        for para in self.dialog.findChildren(RichPara):
            para.restyle()
        learning_texts(self.panel.body)
        self.picture.draw()
