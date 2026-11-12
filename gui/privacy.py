# -*- coding: utf-8 -*-
"""첫 실행 동의와 철회 화면, 학습을 막지 않는 비공개 전송을 제공함."""
import os
import threading

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QDialog, QWidget

from aiprep.collection import CollectionError
from aiprep.privacy import Consent, NOTICE_ROWS
from aiprep import sync_schedule
from gui import dialogs, kit, theme
from gui.worker import Job


class ConsentDialog(QDialog):
    def __init__(self, parent, controller, first=False):
        super().__init__(parent)
        self.controller, self.first = controller, first
        self.setWindowTitle("학습 기록 수집 동의" if first else "내 정보·데이터")
        self.setModal(True)
        kit.page(self)
        room = self.screen().availableGeometry()
        self.resize(min(760, room.width()-32), min(700, room.height()-72))
        outer = kit.box(self, (24, 24, 24, 24), spacing=theme.GAP["group"])
        content = QWidget()
        body = kit.box(content, spacing=theme.GAP["group"])
        body.addWidget(kit.heading(kit.label("학습 기록 수집 동의" if first else "내 정보·데이터", "title"),
                                   kit.para("동의하지 않아도 문제를 풀고 채점할 수 있습니다.", "body", "secondary")))
        self.status_text = kit.para()
        body.addWidget(self.status_text)
        for title, text in NOTICE_ROWS:
            body.addWidget(kit.heading(kit.label(title, "headline"), kit.para(text)))
        self.research = QCheckBox("수집·이용과 자동 전송 동의 (선택)")
        self.overseas = QCheckBox("미국 서버 보관 동의 (선택)")
        for box in (self.research, self.overseas):
            box.setProperty("role", "body")
            box.setFont(theme.font("body"))
            box.setMinimumHeight(theme.control_height("s"))
        self.message = kit.para("", "caption", "secondary")
        body.addWidget(self.message)
        self.scroll = kit.scroll(content)
        outer.addWidget(self.scroll, 1)
        outer.addWidget(self.research)
        outer.addWidget(self.overseas)
        actions = QWidget()
        flow = kit.FlowLayout(actions, spacing=theme.GAP["detail"])
        self.agree = kit.button("동의하고 시작" if first else "동의하고 수집 시작", "primary", "l")
        self.agree.clicked.connect(lambda: self.choose(True))
        self.decline = kit.button("동의하지 않고 시작" if first else "닫기", scale="l")
        self.decline.clicked.connect(lambda: self.choose(False) if first else self.accept())
        self.withdraw = kit.button("동의 철회·비공개 기록 삭제", "danger_text", "l")
        self.withdraw.clicked.connect(self.confirm_withdraw)
        for button in (self.agree, self.decline, self.withdraw):
            flow.addWidget(button)
        outer.addWidget(actions)
        self.research.toggled.connect(self.refresh)
        self.overseas.toggled.connect(self.refresh)
        controller.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        try:
            state = self.controller.consent.settings()
            pending = state.get("withdraw_pending", False)
            active = state.get("accepted", False) and not self.controller.consent.needs_choice()
            text = "동의 여부를 선택해 주세요."
            if pending:
                text = "이 기기의 수집을 멈췄습니다. 서버 삭제는 연결되는 대로 다시 시도합니다."
                if os.environ.get("STUDY_AUTO_SYNC", "1") == "0":
                    text = "이 기기의 수집을 멈췄습니다. 서버 연결이 중지되어 삭제 요청을 보내지 못했습니다."
            elif active:
                text = "수집에 동의했습니다 · 선택 시각: " + state.get("at", "")[:19].replace("T", " ")
            elif state:
                text = "수집에 동의하지 않았습니다. 학습과 로컬 채점은 사용할 수 있습니다."
            self.status_text.setText(text)
            self.message.setText(self.controller.message)
            self.agree.setVisible(not active)
            self.agree.setEnabled(self.research.isChecked() and self.overseas.isChecked() and not pending)
            self.research.setVisible(not active and not pending)
            self.overseas.setVisible(not active and not pending)
            self.withdraw.setVisible(active)
        except CollectionError as error:
            self.status_text.setText(str(error))
            self.agree.setEnabled(False)

    def choose(self, accepted):
        try:
            self.controller.consent.choose(accepted)
        except (CollectionError, OSError) as error:
            self.message.setText(str(error))
            return
        self.controller.changed.emit()
        self.controller.tick()
        self.accept()

    def confirm_withdraw(self):
        def chosen(key):
            if key != "withdraw":
                return
            try:
                self.controller.consent.withdraw()
                self.controller.message = "수집을 멈추고 비공개 기록 삭제를 요청했습니다. 완료 여부를 확인하고 있습니다. 기존 풀이·진도는 유지합니다."
                self.controller.changed.emit()
                self.controller.tick()
            except (CollectionError, OSError) as error:
                self.message.setText(str(error))
        self.confirmation = dialogs.MessageDialog(self, "동의를 철회할까요?",
            "수집·자동 전송을 멈추고 비공개 학습 기록을 삭제합니다. 서버 삭제는 온라인에서 확인합니다. "
            "프로그램의 풀이·진도와 이미 공개한 GitHub 이력은 유지합니다.",
            buttons=(("취소", "cancel"), ("철회하고 삭제", "withdraw", "danger")), on_choice=chosen)
        self.confirmation.show()

    def reject(self):
        if self.first:
            self.choose(False)
        else:
            super().reject()


class SyncController(QObject):
    changed = pyqtSignal()

    def __init__(self, parent, collections):
        super().__init__(parent)
        self.consent = Consent(collections)
        self.message, self.job = "", None
        self.cancel, self.closing = threading.Event(), False
        self.failures = 0
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.tick)
        if os.environ.get("STUDY_AUTO_SYNC", "1") != "0":
            self.timer.start(sync_schedule.initial_ms())

    def show(self, first=False):
        self.dialog = ConsentDialog(self.parent(), self, first)
        self.dialog.show()

    def tick(self):
        if self.job is not None or os.environ.get("STUDY_AUTO_SYNC", "1") == "0":
            return
        self.timer.stop()
        try:
            state = self.consent.settings()
        except CollectionError as error:
            self.message = str(error)
            self.changed.emit()
            self.failures = min(4, self.failures + 1)
            self.timer.start(sync_schedule.delay_ms(self.failures))
            return
        if not state.get("accepted") and not state.get("withdraw_pending"):
            return
        self.cancel.clear()
        self.job_choice = state.get("choice")
        self.job = Job(lambda: self.consent.synchronize(self.cancel.is_set))
        self.job.done.connect(self.finish)
        self.job.failed.connect(lambda *_: self.finish({"errors": ["서버에 연결하지 못했습니다. 기록은 이 기기에 보관하고 다시 시도합니다."]}))
        self.job.finished.connect(self.release_job)
        self.job.start()

    def finish(self, result):
        self.failures = min(4, self.failures + 1) if result.get("errors") else 0
        self.message = ("처리 대기 · " + result["errors"][0] if result.get("errors") else
                        "서버의 비공개 기록 삭제를 확인했습니다." if result.get("withdrawn") else
                        "서버에 새 기록 %d건을 전송했습니다." % result.get("sent", 0))
        self.changed.emit()

    def release_job(self):
        self.job.deleteLater()
        self.job = None
        if self.closing:
            self.parent().close()
            return
        try:
            state = self.consent.settings()
        except CollectionError as error:
            self.message = str(error)
            self.changed.emit()
            self.failures = min(4, self.failures + 1)
            if os.environ.get("STUDY_AUTO_SYNC", "1") != "0":
                self.timer.start(sync_schedule.delay_ms(self.failures))
            return
        if state.get("choice") != self.job_choice:
            self.failures = 0
            QTimer.singleShot(0, self.tick)
        elif os.environ.get("STUDY_AUTO_SYNC", "1") != "0":
            if state.get("accepted") or state.get("withdraw_pending"):
                self.timer.start(sync_schedule.delay_ms(self.failures, bool(state.get("withdraw_pending"))))

    def stop(self):
        self.timer.stop()
        if self.job is not None:
            self.closing = True
            self.cancel.set()
            return False
        return True
