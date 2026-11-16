# -*- coding: utf-8 -*-
"""과목별 기록 제공 상태와 파일 저장·희망 직무 설정을 다룸."""
import os

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QLabel, QWidget)

from learning_data.collection import CollectionError
from learning_data import goals
from gui import kit, motion, theme
from gui.dialog_layout import DialogLayout


class DataSection(QWidget):
    """필요한 설정만 펼치고 입력값은 접은 뒤에도 유지함."""
    def __init__(self, title, parent):
        super().__init__(parent)
        self.opened = False
        layout = kit.box(self)
        self.header = kit.Row(title, end="펼치기", strong=True, wrap=True)
        self.header.chevron.hide()
        self.header.setAccessibleName(title + " 펼치기")
        layout.addWidget(self.header)
        self.body = QWidget()
        self.content = kit.box(self.body, (24, 8, 24, 24), theme.GAP["paragraph"])
        layout.addWidget(self.body)
        self.body.hide()
        self.header.clicked.connect(lambda: self.set_opened(not self.opened))

    def set_opened(self, opened):
        self.opened = bool(opened)
        action = "접기" if self.opened else "펼치기"
        self.header.end.setText(action)
        self.header.setAccessibleName(self.header.title.text() + " " + action)
        if not self.opened and self.body.isAncestorOf(QApplication.focusWidget()):
            self.header.setFocus(Qt.FocusReason.OtherFocusReason)
        self.body.setEnabled(self.opened)
        if self.opened:
            self.body.show()
            motion.fade_opacity(self.body, True)
        else:
            motion.fade_opacity(self.body, False, self.body.hide)


class LearningDataDialog(QDialog):
    def __init__(self, parent, collection, host=None):
        super().__init__(parent)
        kit.page(self)
        self.collection = collection
        self.host = host or parent.window()
        self.controller = getattr(self.host, "privacy", None)
        subject = "파이썬" if collection.track == "python" else "AI"
        title = subject + " 학습 기록"
        self.setWindowTitle(title)
        self.setModal(True)
        self.shell = DialogLayout(self, title)
        body = self.shell.content
        body.setSpacing(theme.GAP["group"])
        status_card, summary = kit.card(spacing=theme.GAP["paragraph"])
        self.status_text = kit.para("", "headline", bold=True)
        self.status_hint = kit.para("", "body", "secondary")
        summary.addWidget(kit.heading(self.status_text, self.status_hint))
        self.toggle = kit.button("", scale="m")
        self.toggle.clicked.connect(self.change_consent)
        summary.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(status_card)

        self.transfer_section = DataSection("전송 상태와 수집 항목", self)
        transfer = self.transfer_section.content
        transfer.addWidget(kit.para("파이썬·AI에서 동의한 과목의 연구용 기록을 함께 보냅니다. 여기서는 답안 파일을 보내지 않습니다.", "body", "secondary"))
        self.sync_status = kit.para()
        transfer.addWidget(self.sync_status)
        self.send_button = kit.button("모든 과목 기록 보내기")
        self.send_button.setToolTip("동의한 모든 과목의 아직 보내지 않은 연구용 기록을 비공개 서버로 전송합니다. 답안 파일은 보내지 않습니다.")
        self.send_button.clicked.connect(self.send)
        transfer.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.record_count = kit.para("", "caption", "secondary")
        transfer.addWidget(self.record_count)
        notice = ("이 과목에서는 프로그램에 저장한 입력 변경·채점 결과·문항과 개념을 수집합니다. "
                  "외부 편집기의 입력 시각과 읽은 시간은 측정하지 않습니다.") if collection.track == "python" else (
                  "개론·응용의 연습·모의고사·학습 중 답안과 채점 결과, 문항을 연 순서·응답 시간·확신 여부를 수집합니다.")
        transfer.addWidget(kit.para(notice, "caption", "secondary"))
        transfer.addWidget(kit.para("입력 답안 본문은 자동 전송에서 제외합니다. 수집을 다시 켜면 중단 전에 모아 둔 미전송 기록도 보낼 수 있습니다.", "caption", "secondary"))
        body.addWidget(self.transfer_section)

        self.export_section = DataSection("내 컴퓨터에 기록 저장", self)
        export = self.export_section.content
        export.addWidget(kit.para(subject + " 문항·채점 결과·시각 등을 JSONL 파일로 저장합니다. 파일에는 학습자 구분값과 선택한 희망 직무도 포함됩니다.", "body", "secondary"))
        self.with_answers = QCheckBox("작성한 답안도 파일에 포함")
        kit.typed(self.with_answers, "body")
        self.with_answers.setMinimumHeight(theme.control_height("s"))
        export.addWidget(self.with_answers)
        export.addWidget(kit.para("이 선택은 저장할 파일에만 적용됩니다. 파일을 서버에 보내지는 않습니다.", "caption", "secondary"))
        self.export_button = kit.button("기록 파일 저장하기")
        self.export_button.clicked.connect(self.choose_file)
        export.addWidget(self.export_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.export_message = kit.para("", "caption", "secondary")
        export.addWidget(self.export_message)
        self.export_message.hide()
        body.addWidget(self.export_section)

        self.goal_section = DataSection("희망 직무 · 선택 사항", self)
        goal_box = self.goal_section.content
        goal_box.addWidget(kit.para("희망 직무를 고르면 이후 기록에 함께 저장해 직무별 풀이 경향 연구에 사용합니다.", "body", "secondary"))
        self.goal_combo = QComboBox()
        self.goal_combo.setAccessibleName("희망 직무")
        kit.typed(self.goal_combo, "body")
        self.goal_combo.setMinimumHeight(theme.control_height("m"))
        self.goal_combo.addItem("선택 안 함", None)
        self.goal_error = ""
        try:
            for goal_id, goal_title in goals.catalog(collection.repository)["options"]:
                self.goal_combo.addItem(goal_title, goal_id)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.goal_error = "희망 직무 목록을 읽지 못했습니다. %s" % error
        goal_box.addWidget(self.goal_combo)
        self.goal_save = kit.button("희망 직무 저장")
        self.goal_save.clicked.connect(self.save_goal)
        goal_box.addWidget(self.goal_save, 0, Qt.AlignmentFlag.AlignLeft)
        self.goal_status = kit.para("", "caption", "secondary")
        goal_box.addWidget(self.goal_status)
        body.addWidget(self.goal_section)

        self.message = kit.para("", "caption", "secondary")
        body.addWidget(self.message)
        self.message.hide()
        body.addStretch(1)
        self.scroll = self.shell.scroll
        self._reading = None
        self._layout_sample = None
        self.position_timer = QTimer(self)
        self.position_timer.setSingleShot(True)
        self.position_timer.setInterval(16)
        self.position_timer.timeout.connect(self.restore_reading_position)
        self.scroll.verticalScrollBar().actionTriggered.connect(self.cancel_reading_restore)
        self.scroll.verticalScrollBar().sliderPressed.connect(self.cancel_reading_restore)
        self.finished.connect(self.cancel_reading_restore)
        self.privacy_button = kit.button("동의·삭제 관리", "text", "l")
        self.privacy_button.setToolTip("내 정보·데이터에서 동의 내용을 확인하거나 모든 과목의 연구용 기록을 삭제합니다.")
        self.privacy_button.clicked.connect(self.open_privacy)
        self.close_button = kit.button("닫기", scale="l")
        self.close_button.clicked.connect(self.accept)
        self.shell.actions.set_actions([self.privacy_button], [self.close_button])
        if self.controller is not None:
            self.controller.changed.connect(self.refresh_transfer)
        self.refresh()
        self.shell.fit(720, 600)

    def refresh(self):
        status = self.collection.status()
        goal = status.get("goal") or goals.unselected()
        self.goal_combo.setCurrentIndex(max(0, self.goal_combo.findData(goal["goal_id"])))
        self.goal_status.setText(self.goal_error or ("저장한 직무: %s" % self.goal_combo.currentText()))
        self.refresh_transfer()

    def save_goal(self):
        try:
            self.collection.set_goal(self.goal_combo.currentData())
            self.refresh()
            self.goal_status.setText("저장했습니다. 이후 수집 기록부터 적용합니다.")
        except CollectionError as error:
            self.goal_status.setText(str(error))

    @property
    def working(self):
        return self.controller is not None and self.controller.job is not None

    def refresh_transfer(self):
        if self._reading is None:
            self._reading = self.reading_position()
            self._layout_sample = None
        status = self.collection.status()
        self.export_button.setEnabled(os.path.exists(self.collection.path) and not status["error"])
        self.goal_combo.setEnabled(status["enabled"] and not status["error"] and not self.goal_error)
        self.goal_save.setEnabled(self.goal_combo.isEnabled())
        self.goal_save.setToolTip("" if self.goal_combo.isEnabled() else "기록 수집을 시작하면 희망 직무를 저장할 수 있습니다.")
        self.record_count.setText("이 기기에 보관한 연구 기록 %d건 · 문항 버전 %d개" % (status["events"], status["items"]))
        self.record_count.setToolTip("입력 변경·문항 열기·채점마다 기록을 남깁니다. 같은 문항에서 여러 기록이 남을 수 있습니다.")
        try:
            state = self.controller.consent.settings() if self.controller is not None else {}
            active = bool(state.get("accepted")) and not self.controller.consent.needs_choice() if self.controller is not None else False
            pending = state.get("withdraw_pending", False)
            automatic = os.environ.get("STUDY_AUTO_SYNC", "1") != "0"
            title = "기록 수집 중" if status["enabled"] and active else "기록 제공 안 함"
            hint = "새 연구 기록은 약 1분마다 비공개 서버로 자동 전송합니다."
            toggle = "이 과목 수집 중단" if status["enabled"] else "수집 다시 시작"
            if pending:
                title = "비공개 기록 삭제 대기"
                hint = ("수집을 중단했습니다. 서버 연결 후 삭제를 확인합니다." if automatic else
                        "서버 연결이 중지되어 삭제 요청을 보내지 못했습니다.")
            elif not active:
                hint = "기록을 제공하지 않아도 문제를 풀고 채점할 수 있습니다."
                toggle = "동의 내용 확인" if state.get("accepted") else "기록 제공 동의하기"
            elif not status["enabled"]:
                title, hint = "이 과목 수집 중단", "이 과목의 새 기록을 수집하거나 전송하지 않습니다."
            elif not automatic:
                hint = "현재 실행 환경에서는 자동 전송을 껐습니다. 기록은 이 기기에 보관합니다."
            if status["error"]:
                title, hint = "기록 확인 필요", status["error"]
            self.status_text.setText(title)
            self.status_hint.setText(hint)
            self.toggle.setText(toggle)
            self.toggle.setEnabled(not pending and not status["error"])
            self.toggle.setVisible(not pending and not status["error"])
            self.toggle.setToolTip("수집을 중단해도 이미 모은 기록은 남습니다. 전체 삭제는 [동의·삭제 관리]에서 진행합니다.")
            if pending:
                sync = hint
            elif not automatic:
                sync = "현재 실행 환경에서는 자동 전송을 껐습니다."
                if self.controller is not None and self.controller.message:
                    sync += "\n" + self.controller.message
            elif self.working:
                sync = "기록을 보내고 있습니다."
            elif active:
                sync = self.controller.message or "새 기록의 자동 전송을 기다리고 있습니다."
            else:
                sync = "기록 제공에 동의한 뒤 자동으로 전송합니다."
            self.sync_status.setText(sync)
            if active and automatic and not pending and not status["error"]:
                if self.working:
                    self.status_text.setText("기록 전송 중" if status["enabled"] else "이 과목 수집 중단")
                    self.status_hint.setText(sync)
                elif self.controller.failures:
                    self.status_text.setText("전송 확인 필요")
                    self.status_hint.setText(sync + "\n[전송 상태와 수집 항목]에서 다시 보낼 수 있습니다.")
            self.send_button.setEnabled(active and automatic and not pending and not self.working and not self.controller.closing)
        except CollectionError as error:
            self.status_text.setText("동의 상태 확인 필요")
            self.status_hint.setText(str(error))
            self.sync_status.setText(str(error))
            self.send_button.setEnabled(False)
            self.toggle.setEnabled(False)
            self.toggle.hide()
        if self._reading is not None:
            self.position_timer.start()

    def reading_position(self):
        if not self.isVisible() or not self.scroll.verticalScrollBar().value():
            return None
        viewport = self.scroll.viewport()
        focus = QApplication.focusWidget()
        preferred = self.goal_combo if self.goal_combo.view().isVisible() else focus
        candidates = [preferred] + self.shell.body.findChildren(QWidget)
        visible = []
        for widget in candidates:
            if widget is None or not self.shell.body.isAncestorOf(widget) or not widget.isVisible():
                continue
            if widget is not preferred and not isinstance(widget, (QLabel, QAbstractButton, QComboBox)):
                continue
            top = widget.mapTo(viewport, QPoint()).y()
            if top < viewport.height() and top + widget.height() > 0:
                if widget is preferred:
                    return widget, top, viewport.width(), focus
                visible.append((widget, top))
        if not visible:
            return None
        widget, top = min(visible, key=lambda item: (item[1] < 0, abs(item[1])))
        return widget, top, viewport.width(), focus

    def restore_reading_position(self):
        if self._reading is None:
            return
        widget, top, width, focus = self._reading
        viewport = self.scroll.viewport()
        if not self.isVisible() or not widget.isVisible() or width != viewport.width():
            self._reading = None
            return
        current_focus = QApplication.focusWidget()
        if current_focus is not focus:
            self._reading = None
            if (current_focus is not None and current_focus.window() is self
                    and self.shell.body.isAncestorOf(current_focus)):
                self.scroll.ensureWidgetVisible(current_focus)
            return
        current = widget.mapTo(viewport, QPoint()).y()
        sample = current, self.shell.body.height(), viewport.height()
        if sample != self._layout_sample:
            self._layout_sample = sample
            self.position_timer.start()
            return
        self._reading = None
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.value() + current - top)

    def cancel_reading_restore(self, *args):
        self.position_timer.stop()
        self._reading = None

    def send(self):
        if self.controller is not None:
            self.controller.tick()
            self.refresh_transfer()

    def open_privacy(self):
        if callable(getattr(self.host, "show_privacy", None)):
            self.accept()
            self.host.show_privacy()

    def change_consent(self):
        privacy = getattr(self.host, "privacy", None)
        current_consent = (privacy is not None and not privacy.consent.needs_choice()
                           and privacy.consent.settings().get("accepted"))
        if not current_consent and callable(getattr(self.host, "show_privacy", None)):
            self.open_privacy()
            return
        try:
            self.collection.set_enabled(not self.collection.status()["enabled"],
                                        privacy_state=privacy.consent.path if privacy is not None else None)
            self.message.clear()
            self.message.hide()
        except CollectionError as error:
            self.message.setText(str(error))
            self.message.show()
        self.refresh()

    def choose_file(self):
        self.picker = QFileDialog(self, "학습 기록 파일 저장")
        self.picker.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.picker.setOption(QFileDialog.Option.DontUseNativeDialog)
        self.picker.setNameFilter("학습 기록 (*.jsonl)")
        self.picker.setDefaultSuffix("jsonl")
        self.picker.fileSelected.connect(self.export_to)
        self.picker.show()

    def export_to(self, path):
        try:
            result = self.collection.export(path, include_answers=self.with_answers.isChecked())
            self.export_message.setText("기록 %d건을 저장했습니다.\n%s" % (result["events"], result["path"]))
        except CollectionError as error:
            self.export_message.setText(str(error))
        self.export_message.show()
        self.refresh_transfer()
