# -*- coding: utf-8 -*-
"""추가 학습 데이터의 동의·중단·내보내기·삭제를 다룸."""
import os

from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QWidget

from learning_data.collection import CollectionError
from learning_data import goals
from gui import dialogs, kit, theme
from gui.dialog_layout import DialogLayout


class LearningDataDialog(QDialog):
    def __init__(self, parent, collection, host=None):
        super().__init__(parent)
        kit.page(self)
        self.collection = collection
        self.host = host or parent.window()
        self.controller = getattr(self.host, "privacy", None)
        title = "파이썬 학습 데이터" if collection.track == "python" else "학습 데이터"
        self.setWindowTitle(title)
        self.setModal(True)
        room = parent.screen().availableGeometry()
        self.resize(min(640, parent.width(), room.width()-32), min(420, parent.height(), room.height()-72))
        self.shell = DialogLayout(self, title)
        body = self.shell.content
        body.setSpacing(theme.GAP["group"])
        body.addWidget(kit.para("문제 추천 연구에 쓸 풀이 과정을 이 기기에 추가로 보관합니다.", "body", "secondary"))
        notice = ("수집을 시작한 뒤 프로그램에서 변경해 저장한 퀴즈·코드 입력과 채점 결과, 문항과 개념을 보관합니다. "
                  "외부 편집기의 입력 시각이나 문항을 읽은 시간은 추정하지 않습니다. 과거 풀이를 자동으로 가져오지 않습니다.") if collection.track == "python" else (
                                "AI 개론·응용에서 수집을 시작한 뒤의 연습·모의고사 답안과 채점 결과, 문항을 연 순서, 응답 시간, 확신 여부를 보관합니다. "
                                "학습 중의 짐작·떠올리기·코드 빈칸 결과도 포함합니다. 과거 풀이를 가져오지 않습니다.")
        body.addWidget(kit.para(notice))
        body.addWidget(kit.para("[내 정보·데이터]에서 동의하면 새 기록을 비공개로 자동 전송합니다. 풀이 파일은 [풀이 제출]을 누르거나 파일 자동 제출을 켜면 보냅니다. "
                                "동의하지 않거나 철회해도 모든 학습 기능을 사용할 수 있습니다."))
        self.status_text = kit.para()
        body.addWidget(self.status_text)
        self.toggle = kit.button("", "primary", "l")
        self.toggle.clicked.connect(self.change_consent)
        body.addWidget(self.toggle)
        body.addWidget(kit.heading(kit.label("희망 직무 선택", "headline"),
                                   kit.para("직접 고른 진로 목표로 풀이 경향을 살펴봅니다. 능력 등급이나 적합도를 판단하지 않습니다. "
                                            "미선택으로 두어도 됩니다. 수집을 다시 시작하면 새로 골라 주세요.", "body", "secondary")))
        self.goal_combo = QComboBox()
        self.goal_combo.setAccessibleName("희망 직무")
        self.goal_combo.setProperty("role", "body")
        self.goal_combo.setFont(theme.font("body"))
        self.goal_combo.setMinimumHeight(theme.control_height("l"))
        self.goal_combo.addItem("미선택", None)
        self.goal_error = ""
        try:
            for goal_id, title in goals.catalog(collection.repository)["options"]:
                self.goal_combo.addItem(title, goal_id)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.goal_error = "희망 직무 목록을 읽지 못했습니다. %s" % error
        body.addWidget(self.goal_combo)
        goal_actions = QWidget()
        goal_flow = kit.FlowLayout(goal_actions, spacing=theme.GAP["detail"])
        self.goal_save = kit.button("희망 직무 저장", scale="l")
        self.goal_save.clicked.connect(self.save_goal)
        goal_flow.addWidget(self.goal_save)
        body.addWidget(goal_actions)
        self.goal_status = kit.para("", "caption", "secondary")
        body.addWidget(self.goal_status)
        self.with_answers = QCheckBox("내보낼 때 입력 답안 포함")
        kit.typed(self.with_answers, "body")
        self.with_answers.setMinimumHeight(theme.control_height("s"))
        body.addWidget(self.with_answers)
        body.addWidget(kit.para("기본 내보내기는 입력 답안을 제외합니다. 문항·채점 결과·시간·가명 구분값은 포함합니다. "
                                "희망 직무와 선택 당시 로드맵 버전도 포함합니다. 가명 구분값을 써도 완전한 익명 자료는 아닙니다.", "caption", "secondary"))
        self.export_button = kit.button("파일로 내보내기", scale="l")
        self.export_button.clicked.connect(self.choose_file)
        body.addWidget(self.export_button)
        self.delete_button = kit.button("동의 철회·비공개 기록 삭제", "danger_text", "l")
        self.delete_button.clicked.connect(self.confirm_delete)
        body.addWidget(self.delete_button)
        body.addWidget(kit.heading(kit.label("비공개 자동 전송", "headline"),
                                   kit.para("동의 후 수집 중인 모든 과목의 새 기록을 자동으로 보냅니다. 입력 답안 본문은 자동 전송에서 제외합니다. "
                                            "개인 초대 코드는 필요하지 않습니다.", "body", "secondary")))
        self.sync_status = kit.para("", "caption", "secondary")
        body.addWidget(self.sync_status)
        actions = QWidget()
        transfer = kit.FlowLayout(actions, spacing=theme.GAP["detail"])
        self.send_button = kit.button("지금 전송", scale="l")
        self.send_button.clicked.connect(self.send)
        transfer.addWidget(self.send_button)
        self.privacy_button = kit.button("내 정보·데이터", scale="l")
        self.privacy_button.clicked.connect(self.open_privacy)
        transfer.addWidget(self.privacy_button)
        body.addWidget(actions)
        self.message = kit.para("", "caption", "secondary")
        body.addWidget(self.message)
        body.addStretch(1)
        self.scroll = self.shell.scroll
        self.close_button = kit.button("닫기", scale="l")
        self.close_button.clicked.connect(self.accept)
        self.shell.actions.set_actions([], [self.close_button])
        self.shell.fit(680, 420)
        if self.controller is not None:
            self.controller.changed.connect(self.refresh_transfer)
        self.refresh()

    def refresh(self):
        status = self.collection.status()
        state = "수집 중" if status["enabled"] else "수집 안 함"
        text = "%s · 학습 동작 %d건 · 문항 버전 %d개" % (state, status["events"], status["items"])
        if status["error"]:
            text += "\n" + status["error"]
        self.status_text.setText(text)
        self.toggle.setText("수집 중단" if status["enabled"] else "수집 다시 시작")
        self.export_button.setEnabled(os.path.exists(self.collection.path) and not status["error"])
        goal = status.get("goal") or goals.unselected()
        self.goal_combo.setCurrentIndex(max(0, self.goal_combo.findData(goal["goal_id"])))
        self.goal_combo.setEnabled(status["enabled"] and not status["error"] and not self.goal_error)
        self.goal_save.setEnabled(self.goal_combo.isEnabled())
        self.goal_status.setText(self.goal_error or ("저장한 희망 직무: %s" % self.goal_combo.currentText()))
        self.refresh_transfer()

    def save_goal(self):
        try:
            self.collection.set_goal(self.goal_combo.currentData())
            self.message.setText("희망 직무와 현재 로드맵 버전을 저장했습니다. 이후 기록부터 적용합니다.")
        except CollectionError as error:
            self.message.setText(str(error))
        self.refresh()

    @property
    def working(self):
        return self.controller is not None and self.controller.job is not None

    def refresh_transfer(self):
        try:
            state = self.controller.consent.settings() if self.controller is not None else {}
            active = bool(state.get("accepted")) and not self.controller.consent.needs_choice() if self.controller is not None else False
            self.sync_status.setText(self.controller.message or "새 기록은 비공개로 자동 전송합니다." if active else
                                     "동의 상태와 서버 삭제 처리는 [내 정보·데이터]에서 확인합니다.")
            self.send_button.setEnabled(active and not self.working)
            self.delete_button.setEnabled(self.controller is not None and not state.get("withdraw_pending") and
                                          (bool(state.get("accepted")) or self.controller.consent.has_private_records()))
        except CollectionError as error:
            self.sync_status.setText(str(error))
            self.send_button.setEnabled(False)

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
        if not self.collection.status()["enabled"] and not current_consent and callable(getattr(self.host, "show_privacy", None)):
            self.open_privacy()
            return
        try:
            self.collection.set_enabled(not self.collection.status()["enabled"],
                                        privacy_state=privacy.consent.path if privacy is not None else None)
            self.message.setText("설정을 저장했습니다. 수집을 중단해도 이미 모은 데이터는 직접 삭제하기 전까지 남습니다.")
        except CollectionError as error:
            self.message.setText(str(error))
        self.refresh()

    def choose_file(self):
        self.picker = QFileDialog(self, "학습 데이터 내보내기")
        self.picker.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.picker.setOption(QFileDialog.Option.DontUseNativeDialog)
        self.picker.setNameFilter("학습 데이터 (*.jsonl)")
        self.picker.setDefaultSuffix("jsonl")
        self.picker.fileSelected.connect(self.export_to)
        self.picker.show()

    def export_to(self, path):
        try:
            result = self.collection.export(path, include_answers=self.with_answers.isChecked())
            self.message.setText("저장한 파일을 다시 읽어 %d건을 확인했습니다. %s" % (result["events"], result["path"]))
        except CollectionError as error:
            self.message.setText(str(error))
        self.refresh()

    def confirm_delete(self):
        def chosen(key):
            if key != "delete" or self.controller is None:
                return
            try:
                self.controller.withdraw()
            except (CollectionError, OSError) as error:
                self.message.setText(str(error))
            self.refresh()
        self.confirmation = dialogs.MessageDialog(self, "동의를 철회할까요?",
            "모든 과목의 추가 수집·전송을 멈추고 이 기기와 서버의 비공개 기록을 삭제합니다. "
            "기존 풀이·진도는 유지하며 서버 삭제는 연결 후 확인합니다.",
            buttons=(("취소", "cancel"), ("철회하고 삭제", "delete", "danger")), on_choice=chosen)
        self.confirmation.show()
