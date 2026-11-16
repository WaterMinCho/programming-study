# -*- coding: utf-8 -*-
"""코드 참조의 작은 창 배치와 답안·읽던 위치·저장 기록 보존을 확인함."""
import json
import os
from pathlib import Path
import time
from unittest import mock

from tests import guikit, test_gui_ai
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QPoint, Qt
from PyQt6.QtTest import QTest
from gui import ai_learn, theme
from gui.ai_code_help import CodeHelpBlock, CodeReferenceDialog
from aiprep import bank, service


class SelectionTrace(QObject):
    """검사 입력의 선택·초점 이벤트만 기록함. 글자나 실제 학습 기록은 출력하지 않음."""

    def __init__(self, win, block, field, label):
        super().__init__()
        self.win, self.block, self.field, self.label = win, block, field, label
        self.rows, self.connections, self.running = [], [], True
        self.started = time.monotonic()
        guikit.APP.installEventFilter(self)
        for signal, phase in ((block.button.pressed, "button.pressed"),
                              (block.button.released, "button.released.before_open"),
                              (block.button.clicked, "button.clicked.after_open"),
                              (block.restore_timer.timeout, "restore_timer.after"),
                              (guikit.APP.focusChanged, "application.focusChanged")):
            self.connect(signal, phase)
        if field is not None:
            self.connect(field.selectionChanged, "input.selectionChanged")
            self.connect(field.cursorPositionChanged, "input.cursorPositionChanged")

    def connect(self, signal, phase):
        callback = lambda *args: self.record(phase)
        signal.connect(callback)
        self.connections.append((signal, callback))

    def name(self, widget):
        if widget is None:
            return None
        for target, name in ((self.win, "main"), (self.block.button, "button"), (self.field, "input"),
                             (self.block.restore_timer, "restore_timer")):
            if widget is target:
                return name
        return "popup" if isinstance(widget, CodeReferenceDialog) else type(widget).__name__

    def record(self, phase, **extra):
        if not self.running or sip.isdeleted(self.block) or sip.isdeleted(self.win):
            return
        field = self.field if self.field is not None and not sip.isdeleted(self.field) else None
        saved = self.block.return_state
        cached = [{"cursor": cursor, "start": start, "length": length,
                   "same_text": field is not None and text == field.text()}
                  for text, cursor, start, length in saved[3].values()] if saved else None
        self.rows.append({"ms": round((time.monotonic() - self.started) * 1000, 2), "phase": phase,
                          "input": [field.selectionStart(), field.selectionLength(), field.cursorPosition()] if field else None,
                          "focus": self.name(guikit.APP.focusWidget()), "active": self.name(guikit.APP.activeWindow()),
                          "main_active": self.win.isActiveWindow(), "timer": self.block.restore_timer.isActive(),
                          "saved": cached, "position_pending": saved is not None and saved[2] is not None, **extra})

    def eventFilter(self, watched, event):
        if not self.running or sip.isdeleted(self.block):
            return False
        selected = (self.win, self.block.button, self.field, self.block.restore_timer)
        events = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.FocusIn,
                  QEvent.Type.FocusOut, QEvent.Type.WindowActivate, QEvent.Type.WindowDeactivate)
        if (any(watched is item for item in selected) or isinstance(watched, CodeReferenceDialog)) and (
                event.type() in events or watched is self.block.restore_timer and event.type() == QEvent.Type.Timer):
            reason = event.reason().name if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut) else None
            self.record("event.before." + event.type().name, target=self.name(watched), reason=reason,
                        spontaneous=event.spontaneous())
        return False

    def message(self):
        return json.dumps({"case": self.label, "platform": guikit.APP.platformName(),
                           "dpr": self.win.devicePixelRatioF(), "events": self.rows}, ensure_ascii=False)

    def save(self):
        folder = os.environ.get("STUDY_UI_ARTIFACT_DIR")
        if folder:
            out = Path(folder)
            out.mkdir(parents=True, exist_ok=True)
            (out / ("code-help-focus-" + self.label + ".json")).write_text(self.message() + "\n", encoding="utf-8")

    def stop(self):
        self.running = False
        guikit.APP.removeEventFilter(self)
        for signal, callback in self.connections:
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self.connections = []


class CodeHelpGuiTest(test_gui_ai.AiTest):
    real_bank = True

    def stored(self):
        return {str(p.relative_to(self.tmp)): p.read_bytes() for p in Path(self.tmp).rglob("*")
                if p.is_file() and ("ai_home" in p.parts or "python_home" in p.parts or "submissions" in p.parts)}

    def settled(self):
        guikit.pump()
        guikit.wait_until(lambda: self.win.ai_learn.pending_position is None
                         and not self.win.input_timer.isActive() and self.win.focused_input is None)

    def capture(self, widget, name):
        folder = os.environ.get("STUDY_UI_ARTIFACT_DIR")
        if not folder:
            return
        out = Path(folder)
        out.mkdir(parents=True, exist_ok=True)
        self.assertTrue(widget.grab().save(str(out / (name + ".png"))))
        data = {"platform": guikit.APP.platformName(), "dpr": widget.devicePixelRatioF(),
                "window": list(widget.geometry().getRect()), "frame": list(widget.frameGeometry().getRect()),
                "available": list(widget.screen().availableGeometry().getRect())}
        (out / (name + ".json")).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_real_references_keep_draft_course_and_records_in_small_max_text_both_themes(self):
        win = self.boot((1280, 800))
        win.go_ai()
        self.addCleanup(theme.set_mode, theme.state["mode"])
        win.set_text("larger")
        for course, lid, key, number in (("intro", "i15", "15b", 4), ("app", "a01", "a1b", 4),
                                         ("app", "a02", "a2c", 2)):
            if win.ai.course != course:
                win.switch_ai_course(course)
            self.assertTrue(win.open_ai_unit(lid, key, number))
            reader = win.ai_learn
            self.settled()
            block, = reader.view.findChildren(CodeHelpBlock)
            fields = reader.view.findChildren(ai_learn.RecallBlock)
            field = fields[0].field if fields else None
            if field is not None:
                field.setText("미완성 17")
                field.setSelection(0, 3)
            for mode in ("light", "dark"):
                theme.set_mode(mode)
                win.restyle()
                win.resize(760, 480)
                self.settled()
                reader.scroll.ensureWidgetVisible(block.button)
                block.button.setFocus()
                self.settled()
                self.assertTrue(block.button.visibleRegion().contains(block.button.rect()))
                self.assertEqual(0, reader.scroll.horizontalScrollBar().maximum())
                self.assertEqual(block.docs[-1].mapTo(reader.view, QPoint()).x(), block.button.mapTo(reader.view, QPoint()).x())
                before = self.stored()
                source = win.ai
                at = (reader.lid, reader.key, reader.index, reader.scroll.verticalScrollBar().value())
                draft = (field.text(), field.selectedText()) if field is not None else None
                selected_course = win.settings.value("ai/course/" + win.user)
                trace = SelectionTrace(win, block, field, lid + "-" + mode)
                self.addCleanup(trace.stop)
                trace.record("baseline.before_capture")
                self.capture(win, "code-help-%s-%s-reader" % (lid, mode))
                with mock.patch.object(service.AiSession, "__init__", side_effect=AssertionError("참조에서 세션 생성")), \
                        mock.patch.object(source.collection, "emit", side_effect=AssertionError("참조에서 수집")):
                    trace.record("before_click")
                    guikit.click(block.button)
                    trace.record("after_click")
                    popup = block.dialog
                    self.assertIsNotNone(popup)
                    self.addCleanup(lambda p=popup: p.close() if not sip.isdeleted(p) else None)
                    self.assertTrue(popup.isVisible() and popup.isModal())
                    self.assertEqual(block.block["reference"]["title"], popup.panel.title.text())
                    self.assertLessEqual(popup.width(), win.width())
                    self.assertLessEqual(popup.height(), win.height())
                    self.assertTrue(popup.screen().availableGeometry().contains(popup.frameGeometry()))
                    self.assertTrue(popup.close_btn.visibleRegion().contains(popup.close_btn.rect()))
                    self.assertTrue(popup.panel.title.visibleRegion().contains(popup.panel.title.rect()))
                    self.assertEqual(0, popup.panel.scroll.horizontalScrollBar().maximum())
                    for inner in popup.view.findChildren(CodeHelpBlock):
                        self.assertFalse(inner.button.isVisibleTo(popup))
                        inner.open_reference()
                        self.assertIsNone(inner.dialog)
                    for recall in popup.view.findChildren(ai_learn.RecallBlock):
                        self.assertFalse(recall.entry.isVisibleTo(popup))
                    for kind in (ai_learn.GuessBlock, ai_learn.RevealBlock, ai_learn.RecallBlock,
                                 ai_learn.WhyBlock, ai_learn.RotateBlock, ai_learn.MemoBlock):
                        self.assertFalse(popup.view.findChildren(kind))
                    self.capture(popup, "code-help-%s-%s-popup" % (lid, mode))
                    fixed = (popup.panel.title.mapTo(popup, QPoint()), popup.close_btn.mapTo(popup, QPoint()))
                    popup.panel.scroll.verticalScrollBar().setValue(popup.panel.scroll.verticalScrollBar().maximum())
                    guikit.pump()
                    self.assertEqual(fixed, (popup.panel.title.mapTo(popup, QPoint()), popup.close_btn.mapTo(popup, QPoint())))
                    trace.record("before_escape")
                    QTest.keyClick(popup, Qt.Key.Key_Escape)
                    trace.record("escape_return")
                    self.settled()
                    trace.record("settled")
                    trace.save()
                diagnostic = trace.message()
                trace.stop()
                self.assertIsNone(block.dialog)
                self.assertIs(win.focusWidget(), block.button)
                self.assertIs(source, win.ai)
                self.assertEqual(selected_course, win.settings.value("ai/course/" + win.user))
                self.assertEqual(at, (reader.lid, reader.key, reader.index, reader.scroll.verticalScrollBar().value()))
                if field is not None:
                    self.assertEqual(draft, (field.text(), field.selectedText()), diagnostic)
                self.assertEqual(before, self.stored())
        # 마지막 참조 창을 운영체제 캡처에서도 확인할 수 있게 열어 둠.
        guikit.click(block.button)
        self.capture_widget = block.dialog

    def test_reopen_refits_and_revalidates_without_changing_the_active_step(self):
        win = self.boot((1280, 800))
        win.go_ai()
        win.open_ai_unit("i15", "15b", 4)
        self.settled()
        reader = win.ai_learn
        block, = reader.view.findChildren(CodeHelpBlock)
        reader.scroll.ensureWidgetVisible(block.button)
        guikit.click(block.button)
        popup = block.dialog
        wide = popup.width()
        self.assertTrue(popup.screen().availableGeometry().contains(popup.frameGeometry()))
        self.capture(popup, "code-help-wide-popup")
        guikit.click(popup.close_btn)
        win.resize(760, 480)
        win.set_text("larger")
        self.settled()
        reader.scroll.ensureWidgetVisible(block.button)
        guikit.click(block.button)
        popup = block.dialog
        self.assertLess(popup.width(), wide)
        self.assertTrue(popup.screen().availableGeometry().contains(popup.frameGeometry()))
        pictures = popup.view.findChildren(ai_learn.AiFigure)
        self.assertTrue(pictures)
        picture = pictures[0]
        popup.panel.scroll.ensureWidgetVisible(picture)
        before = self.stored()
        if picture.count > 1:
            picture.next()
            self.assertEqual(1, picture.frame())
            picture.prev()
        picture.open_dialog()
        guikit.pump()
        self.assertTrue(picture.dialog.isVisible())
        self.assertIs(picture.dialog.parentWidget(), popup)
        picture.dialog.close()
        guikit.pump()
        self.assertEqual(before, self.stored())
        guikit.click(popup.close_btn)
        target = block.block["reference"]
        block.block["reference"] = dict(target, title=target["title"] + " 변경")
        before = self.stored()
        with mock.patch.object(bank, "resolve_code_reference", wraps=bank.resolve_code_reference) as resolve:
            block.open_reference()
            resolve.assert_called_once()
        self.assertIsNone(block.dialog)
        self.assertTrue(block.error.isVisible())
        self.assertEqual(before, self.stored())
        self.assertEqual(("i15", "15b"), (reader.lid, reader.key))
        self.capture_widget = win

    def test_modal_focus_reset_keeps_input_selection_in_both_directions(self):
        win = self.boot((760, 480))
        win.go_ai()
        win.open_ai_unit("i15", "15b", 4)
        self.settled()
        reader = win.ai_learn
        block, = reader.view.findChildren(CodeHelpBlock)
        field = reader.view.findChildren(ai_learn.RecallBlock)[0].field
        reader.scroll.ensureWidgetVisible(block.button)
        block.button.setFocus()
        self.settled()
        for start, length in ((0, 3), (3, -3)):
            field.setText("미완성 ")
            field.setFocus()
            QTest.keyClicks(field, "17")
            block.button.setFocus()
            reader.scroll.ensureWidgetVisible(block.button)
            self.settled()
            field.setSelection(start, length)
            self.assertTrue(field.isUndoAvailable())
            selected = (field.text(), field.selectedText(), field.cursorPosition())
            at = reader.scroll.verticalScrollBar().value()
            before = self.stored()
            guikit.click(block.button)
            popup = block.dialog
            # 모달의 기본 초점 복귀가 선택을 지우는 경로를 재현함.
            popup.finished.connect(lambda _: field.deselect())
            with mock.patch.object(win.ai.collection, "emit", side_effect=AssertionError("참조에서 수집")):
                QTest.keyClick(popup, Qt.Key.Key_Escape)
                self.settled()
            self.assertEqual(selected, (field.text(), field.selectedText(), field.cursorPosition()))
            self.assertIs(win.focusWidget(), block.button)
            self.assertEqual(at, reader.scroll.verticalScrollBar().value())
            self.assertEqual(before, self.stored())
            self.assertTrue(field.isUndoAvailable())
            field.undo()
            self.assertEqual("미완성 ", field.text())
        guikit.click(block.button)
        popup = block.dialog
        field.setText("열어 둔 동안 바뀐 입력")
        with mock.patch.object(field, "setSelection", wraps=field.setSelection) as select, \
                mock.patch.object(field, "setCursorPosition", wraps=field.setCursorPosition) as cursor:
            QTest.keyClick(popup, Qt.Key.Key_Escape)
            self.settled()
            select.assert_not_called()
            cursor.assert_not_called()
        self.assertEqual("열어 둔 동안 바뀐 입력", field.text())
        self.capture_widget = win

    def test_page_hide_and_dialog_destruction_close_only_the_owned_reference(self):
        win = self.boot((760, 480))
        win.go_ai()
        win.open_ai_unit("i15", "15b", 4)
        self.settled()
        block, = win.ai_learn.view.findChildren(CodeHelpBlock)
        block.open_reference()
        old = block.dialog
        old.close()
        block.open_reference()
        current = block.dialog
        guikit.pump()
        self.assertIs(block.dialog, current)
        self.assertTrue(current.isVisible())
        current.deleteLater()
        guikit.pump()
        self.assertIsNone(block.dialog)
        block.open_reference()
        popup = block.dialog
        win.go_ai()
        guikit.pump()
        self.assertIsNone(block.dialog)
        self.assertTrue(sip.isdeleted(popup) or not popup.isVisible())
        self.assertIsNot(win.focusWidget(), block.button)
        self.capture_widget = win
