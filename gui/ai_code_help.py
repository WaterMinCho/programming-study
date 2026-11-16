# -*- coding: utf-8 -*-
"""코드의 짧은 사용 설명과 앞 학습 단계의 읽기 전용 참조를 표시함."""
from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from aiprep import bank
from gui import kit, theme
from gui.dialog_layout import DialogLayout

_RESTORE_SELECTION = QEvent.Type(QEvent.registerEventType())


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
        self.return_state = None
        self.restore_timer = QTimer(self)
        self.restore_timer.setSingleShot(True)
        self.restore_timer.timeout.connect(self.restore_source)
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
        reader = self.ctx.win.ai_learn
        for source in reader.view.findChildren(CodeHelpBlock):
            if source.dialog is None and source.return_state is not None:
                _, view, _, fields = source.return_state
                if reader.view is view:
                    source.restore_selections(view, fields)
                source.cancel_restore()
        self.cancel_restore()
        from gui.ai_guide import ViewState
        reader.remember_view()
        _, saved = reader.view_states[reader.view_key[0]]
        position = ViewState(reader)
        position.focus, position.selection = self.button, None
        self.return_state = (reader, reader.view, position, saved["fields"])
        try:
            dialog = CodeReferenceDialog(self.ctx.win, self.block["reference"])
        except bank.AiBankError:
            self.return_state = None
            self.error.show()
            return
        self.error.hide()
        self.dialog = dialog
        self.ctx.win.installEventFilter(self)
        self.destroyed.connect(dialog.deleteLater)
        dialog.finished.connect(self.closed)
        dialog.destroyed.connect(lambda: self.clear_dialog(dialog))
        dialog.open()

    def clear_dialog(self, dialog):
        if self.dialog is dialog:
            self.closed(0)

    def closed(self, _result):
        self.dialog = None
        if self.isVisible():
            self.restore_timer.start(0)

    def restore_source(self):
        saved = self.return_state
        if saved is None or not self.isVisible() or self.dialog is not None:
            self.cancel_restore()
            return
        reader, view, position, fields = saved
        if reader.view is not view:
            self.cancel_restore()
            return
        elif position is not None:
            self.return_state = (reader, view, None, fields)
            position.restore()
            self.button.setFocus(Qt.FocusReason.OtherFocusReason)
        if QApplication.activeWindow() is self.ctx.win:
            self.queue_selection_restore()

    def queue_selection_restore(self):
        # QLineEdit가 창 활성화 뒤 예약한 선택 해제를 먼저 처리함.
        QCoreApplication.removePostedEvents(self, _RESTORE_SELECTION)
        QCoreApplication.postEvent(self, QEvent(_RESTORE_SELECTION), Qt.EventPriority.LowEventPriority.value)

    def eventFilter(self, watched, event):
        if (watched is self.ctx.win and event.type() == QEvent.Type.WindowActivate
                and self.return_state is not None and self.dialog is None):
            self.queue_selection_restore()
        return False

    def event(self, event):
        if event.type() == _RESTORE_SELECTION:
            saved = self.return_state
            if (saved is not None and saved[2] is None and QApplication.activeWindow() is self.ctx.win
                    and self.isVisible() and self.dialog is None):
                reader, view, _, fields = saved
                self.cancel_restore()
                if reader.view is view:
                    self.restore_selections(view, fields)
            return True
        return super().event(event)

    def cancel_restore(self):
        self.restore_timer.stop()
        QCoreApplication.removePostedEvents(self, _RESTORE_SELECTION)
        self.ctx.win.removeEventFilter(self)
        self.return_state = None

    @staticmethod
    def restore_selections(view, fields):
        """글자와 undo 이력을 유지하며 바뀌지 않은 입력의 선택·커서만 복원함."""
        from gui.ai_learn import RecallBlock, _view_widget
        for path, (text, cursor, start, length) in fields.items():
            block = _view_widget(view, path)
            if not isinstance(block, RecallBlock) or block.field.text() != text:
                continue
            if (block.field.cursorPosition(), block.field.selectionStart(), block.field.selectionLength()) == (cursor, start, length):
                continue
            if start >= 0:
                block.field.setSelection(start + length if cursor == start else start, -length if cursor == start else length)
            else:
                block.field.setCursorPosition(cursor)

    def hideEvent(self, event):
        self.cancel_restore()
        if self.dialog is not None:
            self.dialog.close()
        super().hideEvent(event)

    def restyle(self):
        for piece in self.docs:
            piece.restyle(theme.learning_css())
        if self.dialog is not None:
            self.dialog.restyle()
