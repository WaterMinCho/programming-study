# -*- coding: utf-8 -*-
"""첫 실행 동의와 철회 화면, 학습을 막지 않는 비공개 전송을 제공함."""
import os
import threading

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QDialog, QWidget

from learning_data.collection import CollectionError
from learning_data.privacy import Consent, NOTICE_ROWS, AUTO_NOTICE
from learning_data import sync_schedule
from gui import dialogs, kit, theme
from gui.dialog_layout import DialogLayout
from gui.worker import Job


class AutoSubmissionDialog(QDialog):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("풀이 자동 제출")
        self.setModal(True)
        kit.page(self)
        self.shell = DialogLayout(self, "문제 묶음을 끝내면 자동 제출", "기존 학습 기록 동의와 전송은 유지합니다. 답안 파일을 자동으로 보낼지 선택해 주세요.")
        self.shell.content.addWidget(kit.para(AUTO_NOTICE))
        self.storage_hint = kit.para("비공개 서버에 보관합니다.", "body", "secondary")
        storage = QWidget()
        kit.box(storage, (32, 8, 32, 0)).addWidget(self.storage_hint)
        self.shell.insertWidget(2, storage)
        self.message = kit.para("", "caption", "secondary")
        self.shell.content.addWidget(self.message)
        keep = kit.button("기록만 자동 전송", scale="l")
        keep.clicked.connect(lambda: self.choose(False))
        self.enable = kit.button("답안 파일도 자동 제출", "primary", "l")
        self.enable.clicked.connect(lambda: self.choose(True))
        self.shell.actions.set_actions([keep], [self.enable])
        self.shell.fit(700, 460)

    def choose(self, enabled):
        try:
            self.controller.consent.set_auto_submission(enabled)
        except (CollectionError, OSError, ValueError) as error:
            self.message.setText(str(error))
            return False
        self.controller.changed.emit()
        self.accept()
        return True

    def reject(self):
        try:
            if self.controller.consent.needs_auto_choice() and self.choose(False):
                return
        except CollectionError:
            pass
        super().reject()


class ConsentDialog(QDialog):
    def __init__(self, parent, controller, first=False):
        super().__init__(parent)
        self.controller, self.first = controller, first
        self.setWindowTitle("학습 데이터 제공 안내" if first else "내 정보·데이터")
        self.setModal(True)
        kit.page(self)
        room = self.screen().availableGeometry()
        self.resize(min(760, parent.width(), room.width()-32), min(700, parent.height(), room.height()-72))
        self.shell = DialogLayout(self, "학습 데이터 제공 안내" if first else "내 정보·데이터")
        body = self.shell.content
        body.setSpacing(theme.GAP["group"])
        body.addWidget(kit.para("동의하면 새 풀이 기록을 자동으로 보내 문제 추천 연구에 사용합니다. 동의하지 않아도 문제를 풀고 채점할 수 있습니다. 두 항목을 모두 선택하면 동의 버튼이 켜집니다.",
                               "body", "secondary"))
        self.status_text = kit.para()
        body.addWidget(self.status_text)
        for title, text in NOTICE_ROWS:
            body.addWidget(kit.heading(kit.label(title, "headline"), kit.para(text)))
        body.addWidget(kit.heading(kit.label("답안 파일 자동 제출 (추가 선택)", "headline"), kit.para(AUTO_NOTICE)))
        self.submission_files = kit.button("보낼 풀이 파일 보기", "text", "l")
        self.submission_files.clicked.connect(lambda: parent.show_submission_files(self))
        self.submission_files.setVisible(not first and getattr(getattr(parent, "gitflow", None), "api", None) is not None)
        body.addWidget(self.submission_files)
        self.automatic = kit.button("답안 파일 자동 제출 설정", "text", "l")
        self.automatic.clicked.connect(lambda: AutoSubmissionDialog(self, controller).exec())
        body.addWidget(self.automatic)
        self.research = QCheckBox("학습 데이터 제공 동의 (선택)")
        self.overseas = QCheckBox("비공개 서버 보관 동의 (선택)")
        for box in (self.research, self.overseas):
            box.setProperty("role", "body")
            box.setFont(theme.font("body"))
            box.setMinimumHeight(theme.control_height("s"))
        self.message = kit.para("", "caption", "secondary")
        body.addWidget(self.message)
        self.scroll = self.shell.scroll
        self.storage_hint = kit.para("비공개 서버에 보관합니다.", "body", "secondary")
        self.choices = kit.spaced(self.research, kit.spaced(self.overseas, self.storage_hint, spacing=theme.GAP["detail"]),
                                  spacing=theme.GAP["detail"])
        self.choice_area = QWidget()
        kit.box(self.choice_area, (32, 16, 32, 16)).addWidget(self.choices)
        self.shell.insertWidget(2, self.choice_area)
        self.agree = kit.button("동의하고 시작" if first else "동의하고 수집 시작", "primary", "l")
        self.agree.clicked.connect(lambda: self.choose(True))
        self.decline = kit.button("동의하지 않고 시작" if first else "닫기", scale="l")
        self.decline.clicked.connect(lambda: self.choose(False) if first else self.accept())
        self.withdraw = kit.button("동의 철회·비공개 기록 삭제", "danger_text", "l")
        self.withdraw.clicked.connect(self.confirm_withdraw)
        self.shell.actions.set_actions([self.withdraw], [self.decline, self.agree])
        self.research.toggled.connect(self.refresh)
        self.overseas.toggled.connect(self.refresh)
        controller.changed.connect(self.refresh)
        self.refresh()
        self.shell.fit(760, 620)

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
            elif state.get("accepted"):
                text = "동의 내용이 바뀌었습니다. 내용을 확인하고 다시 선택해 주세요. 이전 기록은 동의 철회로 삭제할 수 있습니다."
            elif state:
                text = "수집에 동의하지 않았습니다. 학습과 로컬 채점은 사용할 수 있습니다."
            self.status_text.setText(text)
            self.message.setText(self.controller.message)
            self.automatic.setVisible(active and not pending)
            scope = state.get("receipt", {}).get("automatic_submission", {})
            self.automatic.setText("답안 파일 자동 제출: " + ("사용 중" if scope.get("accepted") else "사용 안 함") + " · 설정")
            self.agree.setVisible(not active)
            self.agree.setEnabled(self.research.isChecked() and self.overseas.isChecked() and not pending)
            self.choices.setVisible(not active and not pending)
            self.choice_area.setVisible(not active and not pending)
            self.withdraw.setVisible(not pending and (bool(state.get("accepted")) or self.controller.consent.has_private_records()))
        except CollectionError as error:
            self.status_text.setText(str(error))
            self.agree.setEnabled(False)

    def choose(self, accepted):
        try:
            self.controller.consent.choose(accepted)
        except (CollectionError, OSError) as error:
            self.message.setText(str(error))
            if self.first and not accepted:
                self.controller.cancel.set()
                self.controller.timer.stop()
                self.controller.consent._stop_all()
                if any(store.status()["enabled"] for store in self.controller.consent.collections.values()):
                    self.message.setText("수집 중단을 확인하지 못했습니다. 저장 공간과 파일 권한을 확인한 뒤 다시 선택해 주세요.")
                    return
                self.controller.message = "동의 설정을 저장하지 못해 수집 없이 시작합니다. 다음 실행 때 동의 여부를 다시 선택할 수 있습니다."
                self.controller.changed.emit()
                self.accept()
            return
        self.controller.changed.emit()
        self.controller.tick()
        self.accept()

    def confirm_withdraw(self):
        def chosen(key):
            if key != "withdraw":
                return
            try:
                self.controller.withdraw()
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

    def withdraw(self):
        self.consent.withdraw()
        self.cancel.set()
        self.message = "수집을 멈추고 비공개 기록 삭제를 요청했습니다. 완료 여부를 확인하고 있습니다. 기존 풀이·진도는 유지합니다."
        self.changed.emit()
        self.tick()

    def resume(self):
        if self.closing:
            self.closing = False
            self.cancel.clear()
            if self.job is None and os.environ.get("STUDY_AUTO_SYNC", "1") != "0":
                self.timer.start(sync_schedule.initial_ms())

    def tick(self):
        if self.closing or self.job is not None or os.environ.get("STUDY_AUTO_SYNC", "1") == "0":
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
        self.changed.emit()

    def finish(self, result):
        self.failures = min(4, self.failures + 1) if result.get("errors") else 0
        self.message = ("처리 대기 · " + result["errors"][0] if result.get("errors") else
                        "서버의 비공개 기록 삭제를 확인했습니다." if result.get("withdrawn") else
                        "서버에 새 기록 %d건을 전송했습니다." % result.get("sent", 0))
        self.changed.emit()

    def release_job(self):
        self.job.deleteLater()
        self.job = None
        self.changed.emit()
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
        self.closing = True
        self.timer.stop()
        if self.job is not None:
            self.cancel.set()
            return False
        return True
