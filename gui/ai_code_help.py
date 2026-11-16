# -*- coding: utf-8 -*-
"""코드의 짧은 사용 설명과 앞 학습 단계의 읽기 전용 참조를 표시함."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QWidget

from aiprep import bank
from gui import kit, theme
from gui.dialog_layout import DialogLayout


class CodeReferenceDialog(QDialog):
    """참고 단계의 설명만 표시함. 제목과 닫기는 본문 스크롤 밖에 둠."""

    def __init__(self, win, reference):
        from aiprep.service import read_note_reference
        from gui.ai_learn import Ctx, StepView
        data = read_note_reference(reference, win.ai.root)
        super().__init__(win)
        self.setProperty("clipboard", True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setModal(True)
        self.setWindowTitle(data["name"])
        self.panel = DialogLayout(self, data["step"]["title"])
        self.panel.content.setSpacing(theme.LEARN_GAP["paragraph"])
        self.panel.content.addWidget(kit.para(data["name"], "learn_caption", "secondary"))
        ctx = Ctx(win, data["lesson"], data["unit"], readonly=True, base_dir=data["base_dir"], reference_links=False)
        self.view = StepView(data["step"], ctx, show_title=False)
        self.panel.content.addWidget(self.view)
        self.close_btn = kit.button("닫기", "secondary", "l")
        self.close_btn.clicked.connect(self.close)
        self.panel.actions.set_actions([], [self.close_btn])
        self.restyle()

    def restyle(self):
        from gui.ai_learn import READ_WIDTH, learning_texts
        self.view.restyle()
        learning_texts(self.panel.body)
        self.panel.fit(READ_WIDTH + 96, 640)
        self.place()

    def place(self):
        owner = self.parentWidget()
        room = owner.screen().availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(owner.frameGeometry().center())
        self.move(max(room.left(), min(frame.left(), room.right() - frame.width() + 1)),
                  max(room.top(), min(frame.top(), room.bottom() - frame.height() + 1)))

    def showEvent(self, event):
        super().showEvent(event)
        self.place()  # 창 테두리를 만든 뒤 실제 바깥 크기로 위치를 맞춤.


class CodeHelpBlock(QWidget):
    """본문 설명과 보조 단추를 쌓고 참조 창을 닫으면 누른 단추로 초점을 돌림."""

    def __init__(self, block, ctx):
        super().__init__()
        from gui.ai_learn import doc
        self.block, self.ctx = block, ctx
        self.reference_links = ctx.reference_links and not ctx.readonly
        self.dialog, self.docs = None, []
        column = kit.box(self, spacing=theme.LEARN_GAP["detail"])
        if block.get("code"):
            self.docs.append(doc("```python\n%s\n```" % block["code"], ctx.base_dir, column))
        self.docs.append(doc(block["explanation"], ctx.base_dir, column))
        self.button = kit.button(block["title"] + " 설명 다시 보기", "secondary", "l")
        self.button.clicked.connect(self.open_reference)
        column.addWidget(self.button, 0, Qt.AlignmentFlag.AlignLeft)
        self.button.setVisible(self.reference_links)
        self.error = kit.para("참고 학습을 열 수 없습니다. 현재 단계의 설명을 읽어 주세요.", "learn_caption", "secondary")
        column.addWidget(self.error)
        self.error.hide()

    def open_reference(self):
        if not self.reference_links:
            return
        if self.dialog is not None:
            self.dialog.raise_()
            return
        try:
            dialog = CodeReferenceDialog(self.ctx.win, self.block["reference"])
        except bank.AiBankError:
            self.error.show()
            return
        self.error.hide()
        self.dialog = dialog
        self.destroyed.connect(dialog.deleteLater)
        dialog.finished.connect(self.closed)
        dialog.destroyed.connect(lambda: self.clear_dialog(dialog))
        dialog.open()

    def clear_dialog(self, dialog):
        if self.dialog is dialog:
            self.dialog = None

    def closed(self, _result):
        self.dialog = None
        if self.isVisible():
            self.button.setFocus(Qt.FocusReason.OtherFocusReason)

    def hideEvent(self, event):
        if self.dialog is not None:
            self.dialog.close()
        super().hideEvent(event)

    def restyle(self):
        for piece in self.docs:
            piece.restyle(theme.learning_css())
        if self.dialog is not None:
            self.dialog.restyle()
