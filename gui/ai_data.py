# -*- coding: utf-8 -*-
"""추가 학습 데이터의 동의·중단·내보내기·삭제를 다룸."""
import os

from PyQt6.QtWidgets import QCheckBox, QComboBox, QDialog, QFileDialog, QLineEdit, QWidget

from aiprep.collection import CollectionError
from aiprep import goals
from aiprep.sharing import Sharing
from gui import dialogs, kit, theme


class LearningDataDialog(QDialog):
    def __init__(self, parent, collection, host=None):
        super().__init__(parent)
        kit.page(self)
        self.collection = collection
        self.host = host or parent.window()
        self.sharing = Sharing(collection)
        self.working = False
        title = "파이썬 학습 데이터" if collection.track == "python" else "학습 데이터"
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(640, 420)
        outer = kit.box(self, (24, 24, 24, 24), spacing=theme.GAP["group"])
        outer.addWidget(kit.heading(kit.label(title, "headline"),
                                   kit.para("문제 추천 연구에 쓸 풀이 과정을 이 기기에 추가로 보관합니다.", "body", "secondary")))
        content = QWidget()
        body = kit.box(content, spacing=theme.GAP["group"])
        notice = ("수집을 시작한 뒤 프로그램에서 변경해 저장한 퀴즈·코드 입력과 채점 결과, 문항과 개념을 보관합니다. "
                  "외부 편집기의 입력 시각이나 문항을 읽은 시간은 추정하지 않습니다. 과거 풀이를 자동으로 가져오지 않습니다.") if collection.track == "python" else (
                                "AI 개론·응용에서 수집을 시작한 뒤의 연습·모의고사 답안과 채점 결과, 문항을 연 순서, 응답 시간, 확신 여부를 보관합니다. "
                                "학습 중의 짐작·떠올리기·코드 빈칸 결과도 포함합니다. 과거 풀이를 가져오지 않습니다.")
        body.addWidget(kit.para(notice))
        body.addWidget(kit.para("기본은 이 컴퓨터에만 저장하며 GitHub 풀이 제출에는 포함하지 않습니다. "
                                "파일을 내보내거나 아래 버튼으로 서버에 보낼 수 있습니다. 수집을 중단해도 모든 학습 기능을 사용할 수 있습니다."))
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
        body.addWidget(self.with_answers)
        body.addWidget(kit.para("기본 내보내기는 입력 답안을 제외합니다. 문항·채점 결과·시간·가명 구분값은 포함합니다. "
                                "희망 직무와 선택 당시 로드맵 판도 포함합니다. 가명 구분값을 써도 완전한 익명 자료는 아닙니다.", "caption", "secondary"))
        self.export_button = kit.button("파일로 내보내기", scale="l")
        self.export_button.clicked.connect(self.choose_file)
        body.addWidget(self.export_button)
        self.delete_button = kit.button("추가 데이터 삭제", "danger_text", "l")
        self.delete_button.clicked.connect(self.confirm_delete)
        body.addWidget(self.delete_button)
        body.addWidget(kit.heading(kit.label("팀에 데이터 보내기", "headline"),
                                   kit.para("수집 서버 주소와 개인 초대 코드를 받은 뒤 사용할 수 있습니다. "
                                            "아래 단추를 누를 때만 전송하며 자동 전송하지 않습니다.", "body", "secondary")))
        self.server_url = QLineEdit()
        self.server_url.setPlaceholderText("https://수집-서버-주소")
        self.server_url.setAccessibleName("수집 서버 주소")
        self.invite = QLineEdit()
        self.invite.setEchoMode(QLineEdit.EchoMode.Password)
        self.invite.setPlaceholderText("개인 초대 코드")
        self.invite.setAccessibleName("개인 초대 코드")
        body.addWidget(self.server_url)
        body.addWidget(self.invite)
        self.share_answers = QCheckBox("서버에 입력 답안도 보내기")
        body.addWidget(self.share_answers)
        body.addWidget(kit.para("전송 자료에는 가명 구분값, 문항, 채점 결과, 시간과 수집 설정이 포함됩니다. "
                                "희망 직무와 선택 당시 로드맵 판도 전송합니다. 입력 답안은 위 항목을 선택했을 때만 포함합니다. "
                                "팀에서 파이썬·AI 개론·응용 문제 추천 모델과 희망 직무별 풀이 경향을 연구하는 데 사용합니다. "
                                "서버에서 내 풀이 데이터를 삭제할 수 있습니다.", "caption", "secondary"))
        self.send_button = kit.button("서버에 보내기", scale="l")
        self.send_button.clicked.connect(self.send)
        body.addWidget(self.send_button)
        self.remote_delete = kit.button("서버의 내 풀이 삭제", "danger_text", "l")
        self.remote_delete.clicked.connect(self.confirm_remote_delete)
        body.addWidget(self.remote_delete)
        self.message = kit.para("", "caption", "secondary")
        body.addWidget(self.message)
        body.addStretch(1)
        self.scroll = kit.scroll(content)
        outer.addWidget(self.scroll, 1)
        self.close_button = kit.button("닫기", scale="l")
        self.close_button.clicked.connect(self.accept)
        outer.addWidget(self.close_button)
        try:
            settings = self.sharing.settings()
            self.server_url.setText(settings.get("url", ""))
            self.share_answers.setChecked(settings.get("include_answers", False))
        except CollectionError as error:
            self.message.setText(str(error))
        self.refresh()

    def refresh(self):
        status = self.collection.status()
        state = "수집 중" if status["enabled"] else "수집 안 함"
        text = "%s · 학습 동작 %d건 · 문항 판 %d개" % (state, status["events"], status["items"])
        if status["error"]:
            text += "\n" + status["error"]
        self.status_text.setText(text)
        self.toggle.setText("수집 중단" if status["enabled"] else "수집 다시 시작")
        self.export_button.setEnabled(os.path.exists(self.collection.path) and not status["error"])
        self.delete_button.setEnabled(os.path.exists(self.collection.path))
        goal = status.get("goal") or goals.unselected()
        self.goal_combo.setCurrentIndex(max(0, self.goal_combo.findData(goal["goal_id"])))
        self.goal_combo.setEnabled(status["enabled"] and not status["error"] and not self.goal_error)
        self.goal_save.setEnabled(self.goal_combo.isEnabled())
        self.goal_status.setText(self.goal_error or ("저장한 희망 직무: %s" % self.goal_combo.currentText()))

    def save_goal(self):
        try:
            self.collection.set_goal(self.goal_combo.currentData())
            self.message.setText("희망 직무와 현재 로드맵 판을 저장했습니다. 이후 기록부터 적용합니다.")
        except CollectionError as error:
            self.message.setText(str(error))
        self.refresh()

    def run_remote(self, fn):
        def guarded():
            try:
                return fn()
            except CollectionError as error:
                return {"error": str(error)}

        def finish(result):
            self.working = False
            for widget in controls:
                widget.setEnabled(True)
            self.invite.clear()
            self.message.setText(result.get("error") or ("서버의 풀이 데이터를 삭제하고 인증을 폐기했습니다." if result.get("deleted")
                                                         else "서버에 %d건을 보내 저장 확인을 받았습니다." % result["sent"]))
            self.refresh()
        controls = (self.toggle, self.export_button, self.delete_button, self.send_button, self.remote_delete,
                    self.server_url, self.invite, self.share_answers, self.close_button, self.goal_combo, self.goal_save)
        self.working = True
        for widget in controls:
            widget.setEnabled(False)
        started = self.host.run_job("학습 데이터 처리 중", guarded, finish,
                                    on_fail=lambda: finish({"error": "서버 요청을 마치지 못했습니다. 다시 시도해 주세요."}))
        if not started:
            finish({"error": "다른 작업을 마친 뒤 다시 보내 주세요."})

    def send(self):
        url, invite, answers = self.server_url.text(), self.invite.text(), self.share_answers.isChecked()
        self.run_remote(lambda: self.sharing.sync(url, invite, include_answers=answers))

    def confirm_remote_delete(self):
        self.confirmation = dialogs.MessageDialog(self, "서버의 내 풀이 삭제", "서버에 보낸 내 풀이 데이터를 삭제하고 연결 인증을 폐기합니다. "
                                                 "다시 참여하려면 추가 데이터를 삭제한 뒤 새 초대 코드로 등록해야 합니다.",
                                                 buttons=(("취소", "cancel"), ("삭제", "delete", "danger")),
                                                 on_choice=lambda key: self.run_remote(self.sharing.delete_remote) if key == "delete" else None)
        self.confirmation.show()

    def reject(self):
        if not self.working:
            super().reject()

    def closeEvent(self, event):
        if self.working:
            event.ignore()
        else:
            super().closeEvent(event)

    def change_consent(self):
        try:
            self.collection.set_enabled(not self.collection.status()["enabled"])
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
            if key != "delete":
                return
            try:
                self.collection.delete()
                self.message.setText("이 기기의 추가 데이터를 삭제하고 수집을 중단했습니다. 기존 학습 기록과 내보낸 파일은 남습니다.")
            except CollectionError as error:
                self.message.setText(str(error))
            self.refresh()
        self.confirmation = dialogs.MessageDialog(self, "추가 데이터 삭제", "수집을 중단하고 이 기기의 추가 데이터를 삭제합니다. "
                                                 "서버의 기록을 지울 수 있도록 연결 인증은 남깁니다. 서버에 보낸 기록과 내보낸 파일은 별도로 삭제해 주세요.",
                                                 buttons=(("취소", "cancel"), ("삭제", "delete", "danger")), on_choice=chosen)
        self.confirmation.show()
