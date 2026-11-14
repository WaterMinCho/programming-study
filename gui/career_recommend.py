"""학력·경험·관심을 창 안에서 대조하고 직무 그림과 학습 순서로 연결함."""
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QSizePolicy, QWidget

from career.recommend import (ACTIVITIES, DEGREES, EXPERIENCES, INTERESTS, MAJORS, RULES,
                              Education, Profile, first_group, recommend)
from gui import kit, theme
from gui.career_roadmap import CareerRoadmapPage, clear_layout, flow_buttons
from gui.career_role_gallery import RoleGallery
from gui.dialog_layout import DialogLayout


def picker(options, prompt):
    combo = kit.typed(QComboBox(), "body")
    combo.addItem(prompt, "")
    for key, label in options.items():
        combo.addItem(label, key)
    combo.setAccessibleName(prompt)
    combo.setProperty("field_prompt", prompt)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(1)
    combo.setMinimumWidth(0)
    combo.setMinimumHeight(theme.control_height("l"))
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return combo


class EntryRows(QWidget):
    changed = pyqtSignal()

    def __init__(self, education=False):
        super().__init__()
        self.education, self.rows = education, []
        box = kit.box(self, spacing=theme.GAP["paragraph"])
        self.entries = QWidget()
        self.entries_box = kit.box(self.entries, spacing=theme.GAP["paragraph"])
        box.addWidget(self.entries)
        self.add_button = kit.button("+ 학위·전공 추가" if education else "+ 경력 분야 추가")
        self.add_button.clicked.connect(self.add_row)
        box.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignLeft)

    def add_row(self):
        widget, box = kit.well(spacing=theme.GAP["title_description"])
        widget.heading = kit.para("", "label", bold=True)
        box.addWidget(widget.heading)
        fields = []
        if self.education:
            fields.append(picker(DEGREES, "학위 선택"))
            fields.append(picker(MAJORS, "전공 분야 선택"))
        else:
            fields.append(picker(EXPERIENCES, "경력 분야 선택"))
        for field in fields:
            box.addWidget(field)
            field.currentIndexChanged.connect(self.changed.emit)
        remove = kit.button("이 항목 삭제", "text")
        remove.setAccessibleName("학위·전공 항목 삭제" if self.education else "경력 항목 삭제")
        box.addWidget(remove, 0, Qt.AlignmentFlag.AlignRight)
        row = (widget, fields)
        self.rows.append(row)
        self.entries_box.addWidget(widget)
        self._renumber()
        remove.clicked.connect(lambda: self.remove_row(row))
        kit.refont(widget)
        widget.show()
        fields[0].setFocus(Qt.FocusReason.TabFocusReason)
        self.changed.emit()

    def remove_row(self, row):
        self.rows.remove(row)
        self.entries_box.removeWidget(row[0])
        row[0].hide()
        row[0].deleteLater()
        self._renumber()
        self.add_button.setFocus(Qt.FocusReason.TabFocusReason)
        self.changed.emit()

    def _renumber(self):
        for number, (widget, fields) in enumerate(self.rows, 1):
            widget.heading.setText(("학력 " if self.education else "경력 ") + str(number))
            for field in fields:
                field.setAccessibleName(f"{number}번째 {field.property('field_prompt')}")

    def complete(self):
        for _, fields in self.rows:
            for field in fields:
                if not field.currentData():
                    field.setFocus(Qt.FocusReason.TabFocusReason)
                    return False
        return True

    def values(self):
        return tuple(tuple(field.currentData() for field in fields) for _, fields in self.rows)

    def clear(self):
        for row in list(self.rows):
            self.remove_row(row)


class InterestGallery(RoleGallery):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.choices = set()
        # 기존 그림을 재사용하되 카드의 뜻은 직무 선택이 아닌 관심 결과로 표시함.
        self.scene_keys = {scene: key for key, (_, scene) in INTERESTS.items()}
        self.set_roles([{"id": scene, "title": title, "outputs": ["관심 있는 결과로 선택"]}
                        for title, scene in INTERESTS.values()])
        self._describe_choices()

    def _pick(self, scene):
        key = self.scene_keys[scene]
        if key in self.choices:
            self.choices.remove(key)
        elif len(self.choices) < 3:
            self.choices.add(key)
        self._describe_choices()
        self.changed.emit()

    def _describe_choices(self):
        for scene, card in self.cards.items():
            selected = self.scene_keys[scene] in self.choices
            caption = "선택됨 · 다시 누르면 해제" if selected else "최대 3개를 골랐습니다" if len(self.choices) == 3 else "누르면 관심 결과로 선택"
            card.set_role(dict(card.role, outputs=[caption]))
            card.setChecked(selected)
            card.setEnabled(selected or len(self.choices) < 3)
            description = ("선택됨. 다시 누르면 해제합니다." if selected else
                           "선택한 항목을 해제하면 고를 수 있습니다." if len(self.choices) == 3 else
                           "누르면 선택합니다. 최대 3개를 고를 수 있습니다.")
            card.setAccessibleDescription(description)
            card.setToolTip(description)
        self._place()

    def clear(self):
        self.choices.clear()
        self._describe_choices()
        self.changed.emit()


class ResultGallery(RoleGallery):
    """한 직무의 그림·이름을 결과 구역의 전체 폭으로 배치함."""
    def _rows(self, width):
        if not self.cards:
            return 1, 0, []
        card = next(iter(self.cards.values()))
        title_height = card.measure(width, True)[2]
        height = card.content_height(width, True, title_height)
        return 1, height, [(card, 0, 0, width, height, title_height)]


class CareerRecommendDialog(QDialog):
    def __init__(self, catalog, parent=None, on_select_goal=None, on_source=None, saved_role_id=None):
        super().__init__(parent)
        self.catalog, self.on_select_goal = catalog, on_select_goal
        self.saved_role_id = saved_role_id
        self.stage, self.results = 0, ()
        self.result_position, self.restore_result = 0, False
        self.result_focus = None
        self.setWindowTitle("내 경험과 연결되는 직무")
        self.setModal(True)
        self.shell = DialogLayout(self, "배운 분야를 알려주세요")
        self.shell.scroll.verticalScrollBar().rangeChanged.connect(self._restore_result_position)
        self.steps = kit.Stepper()
        self.steps.setAccessibleName("학력, 경험, 관심의 세 단계")
        self.shell.header.layout().addWidget(self.steps)
        self.panels = []
        for _ in range(4):
            panel = QWidget()
            kit.box(panel, spacing=theme.GAP["description_content"])
            self.shell.content.addWidget(panel)
            self.panels.append(panel)
        self.education = EntryRows(education=True)
        self.panels[0].layout().addWidget(kit.para(
            "취득한 학위와 전공 분야를 추가하세요. 학사·석사·박사의 전공이 다르면 각각 넣습니다. 입력 없이 다음으로 넘어가도 됩니다.", "body"))
        self.panels[0].layout().addWidget(kit.para(
            "학교·회사 이름은 묻지 않습니다. 입력은 서버로 보내지 않으며, 이 창을 닫으면 지워집니다.", "caption", "secondary"))
        self.panels[0].layout().addWidget(self.education)
        self.experiences = EntryRows()
        self.panels[1].layout().addWidget(kit.para(
            "개발 외의 경력도 추가할 수 있습니다. 아래 활동은 직장·수업·개인 작업에서 직접 해본 것을 골라주세요.", "body"))
        self.panels[1].layout().addWidget(self.experiences)
        self.panels[1].layout().addWidget(kit.para("직접 해본 활동", "headline", bold=True))
        self.activities = {}
        for key, label in ACTIVITIES.items():
            button = kit.chip(label)
            button.setAccessibleDescription("직접 해본 활동을 선택하거나 해제합니다.")
            self.activities[key] = button
        self.panels[1].layout().addWidget(flow_buttons(*self.activities.values()))
        self.panels[2].layout().addWidget(kit.para(
            "만들어보고 싶은 결과를 최대 3개 골라주세요. 아직 정하지 못했다면 선택하지 않아도 됩니다.", "body"))
        self.interests = InterestGallery()
        self.interest_count = kit.para("0 / 3개 선택", "caption", "secondary")
        self.panels[2].layout().addWidget(self.interest_count)
        self.panels[2].layout().addWidget(self.interests)
        self.interests.changed.connect(lambda: self.interest_count.setText(f"{len(self.interests.choices)} / 3개 선택"))
        self.detail = CareerRoadmapPage(catalog=catalog, on_select_goal=self._save_goal, on_source=on_source)
        self.shell.insertWidget(self.shell.indexOf(self.shell.footer), self.detail, 1)
        self.detail.hide()
        self.error = kit.para("", "body", "danger")
        self.error.setContentsMargins(32, 8, 32, 8)
        self.shell.insertWidget(self.shell.indexOf(self.shell.footer), self.error)
        self.education.changed.connect(self.error.hide)
        self.experiences.changed.connect(self.error.hide)
        self.back_button = kit.button("이전")
        self.next_button = kit.button("다음", "primary")
        self.close_button = kit.button("닫기", "text")
        self.close_button.setToolTip("이 창을 닫고 입력한 학력·경력·활동·관심을 지웁니다.")
        self.clear_button = kit.button("입력 지우기", "text")
        self.back_button.clicked.connect(self.back)
        self.next_button.clicked.connect(self.next)
        self.close_button.clicked.connect(self.reject)
        self.clear_button.clicked.connect(self.clear_profile)
        self.shell.actions.set_actions([self.clear_button, self.close_button], [self.back_button, self.next_button])
        theme.signals.changed.connect(self._appearance_changed)
        self.show_stage(0)
        self.shell.fit(960, 720)

    def _appearance_changed(self):
        kit.refont(self)
        self.education.add_button.updateGeometry()
        self.update()

    def profile(self):
        return Profile(tuple(Education(*row) for row in self.education.values()),
                       tuple(row[0] for row in self.experiences.values()),
                       tuple(key for key, button in self.activities.items() if button.isChecked()),
                       tuple(key for key in INTERESTS if key in self.interests.choices))

    def show_stage(self, stage):
        self.restore_result = False
        self.stage = stage
        titles = ("배운 분야를 알려주세요", "해본 일을 골라주세요", "어떤 결과를 만들고 싶나요?", "경험과 관심으로 연결한 직무", "업무와 학습 로드맵")
        self.shell.title.setText(titles[stage])
        self.steps.setVisible(stage < 3)
        self.steps.set_steps([(i + 1, name, "done" if i < stage else "now" if i == stage else "ready")
                              for i, name in enumerate(("학력", "경험", "관심"))])
        for i, panel in enumerate(self.panels):
            panel.setVisible(i == stage)
        self.shell.scroll.setVisible(stage != 4)
        self.detail.setVisible(stage == 4)
        self.error.hide()
        self.back_button.setVisible(stage > 0)
        self.back_button.setText("추천으로 돌아가기" if stage == 4 else "답변 수정" if stage == 3 else "이전")
        self.next_button.setVisible(stage < 3)
        self.next_button.setText("추천 보기" if stage == 2 else "다음")
        self.clear_button.setVisible(stage != 4)
        kit.refont(self)
        self.shell.scroll.verticalScrollBar().setValue(0)
        (self.next_button if stage < 3 else self.back_button).setFocus(Qt.FocusReason.TabFocusReason)

    def next(self):
        entries = self.education if self.stage == 0 else self.experiences if self.stage == 1 else None
        if entries and not entries.complete():
            self.error.setText("추가한 항목을 선택하거나 [이 항목 삭제]를 눌러주세요.")
            self.error.show()
            self.shell.scroll.ensureWidgetVisible(self.focusWidget())
            return
        if self.stage == 2:
            self.results = recommend(self.profile(), self.catalog)
            self._render_results()
        self.show_stage(min(3, self.stage + 1))

    def back(self):
        from_detail = self.stage == 4
        self.show_stage(3 if from_detail else 0 if self.stage == 3 else max(0, self.stage - 1))
        if from_detail:
            self.restore_result = True
            QTimer.singleShot(0, self._finish_result_restore)

    def _finish_result_restore(self):
        if self.stage != 3:
            return
        self.shell.content.activate()
        bar = self.shell.scroll.verticalScrollBar()
        bar.setValue(min(self.result_position, bar.maximum()))
        self.restore_result = False
        if self.result_focus is not None and self.result_focus.isVisibleTo(self):
            self.result_focus.setFocus(Qt.FocusReason.TabFocusReason)

    def _restore_result_position(self, *_):
        if not self.restore_result or self.stage != 3:
            return
        bar = self.shell.scroll.verticalScrollBar()
        if bar.maximum() >= self.result_position:
            bar.setValue(self.result_position)
            self.restore_result = False

    def _render_results(self):
        box = self.panels[3].layout()
        self.result_focus = None
        clear_layout(box)
        if not self.catalog.roles:
            box.addWidget(kit.para("직무 자료를 읽지 못했습니다.", "headline", bold=True))
            box.addWidget(kit.para("창을 닫고 [설정]의 [업데이트 확인]을 눌러주세요.", "body"))
            return
        count = sum(role["id"] in RULES for role in self.catalog.roles)
        box.addWidget(kit.para(
            f"현재 로드맵의 {count}개 직무 안에서 관심·활동·경력·전공을 정해진 기준으로 비교했습니다. 취업 가능성이나 실력을 판정한 결과는 아닙니다.",
            "caption", "secondary"))
        if not self.results:
            entered = self.profile().activities or self.profile().interests
            title = "현재 직무 목록에서 연결 근거를 찾지 못했습니다." if entered else "해본 활동이나 관심 결과를 하나만 골라보세요."
            box.addWidget(kit.para(title, "headline", bold=True))
            box.addWidget(kit.para("학력·경력만으로 직무를 정하지 않습니다. 창을 닫고 직무 그림부터 둘러봐도 됩니다.", "body"))
            return
        shown = first_group(self.results)
        box.addWidget(kit.para("관심 → 직접 해본 활동 → 경력 → 전공 순으로 비교합니다. 항목별 근거 수가 같으면 함께 표시합니다.", "caption", "secondary"))
        for result in shown:
            self._result_card(box, result)
        rest = self.results[len(shown):]
        if rest:
            more = kit.button(f"다른 연결 직무 {len(rest)}개 펼치기", "text")
            extra = QWidget()
            extra_box = kit.box(extra, spacing=theme.GAP["description_content"])
            extra.hide()
            more.setCheckable(True)
            def expand(checked):
                if checked and not extra_box.count():
                    for result in rest:
                        self._result_card(extra_box, result)
                    kit.refont(extra)
                extra.setVisible(checked)
                more.setText(f"다른 연결 직무 {len(rest)}개 " + ("접기" if checked else "펼치기"))
            more.toggled.connect(expand)
            box.addWidget(more, 0, Qt.AlignmentFlag.AlignLeft)
            box.addWidget(extra)

    def _result_card(self, box, result):
        role = self.catalog.role(result.role_id)
        card, content = kit.well(pad_x=24, pad_y=24, spacing=theme.GAP["paragraph"])
        gallery = ResultGallery()
        gallery.set_roles([role])
        gallery.picked.connect(self.open_detail)
        gallery.cards[role["id"]].setAccessibleDescription("업무와 학습 로드맵을 엽니다. 돌아오면 추천 결과와 입력이 유지됩니다.")
        content.addWidget(gallery)
        if result.interests:
            content.addWidget(kit.heading(kit.para("관심을 둔 결과", "label", bold=True),
                kit.para(" · ".join(INTERESTS[key][0] for key in result.interests), "body")))
        if result.activities:
            content.addWidget(kit.heading(kit.para("직접 해본 활동", "label", bold=True),
                kit.para(" · ".join(ACTIVITIES[key] for key in result.activities), "body")))
        background = [EXPERIENCES[key] for key in result.experiences]
        background += [f"{DEGREES[row.degree]} · {MAJORS[row.major]}" for row in result.education]
        if background:
            content.addWidget(kit.heading(kit.para("함께 참고한 배경", "label", bold=True),
                kit.para(" / ".join(background), "body", "secondary")))
        preparation = " → ".join(node["label"] for node in role["roadmap_nodes"][:3])
        content.addWidget(kit.heading(kit.para("이 직무에서 준비할 기술", "label", bold=True),
            kit.para(preparation or "준비할 기술 자료를 아직 확인하지 못했습니다.", "body")))
        content.addWidget(kit.heading(kit.para("첫 실습", "label", bold=True), kit.para(result.first_step, "body")))
        open_button = kit.button("업무·로드맵 보기", "primary")
        open_button.clicked.connect(lambda: self.open_detail(result.role_id))
        content.addWidget(open_button, 0, Qt.AlignmentFlag.AlignLeft)
        box.addWidget(card)

    def open_detail(self, role_id):
        if not self.detail.select_role(role_id):
            self.error.setText("직무 자료를 열지 못했습니다. 창을 닫고 업데이트를 확인해 주세요.")
            self.error.show()
            return
        focus = QApplication.focusWidget()
        self.result_focus = focus if focus is not None and self.panels[3].isAncestorOf(focus) else None
        self.result_position = self.shell.scroll.verticalScrollBar().value()
        self.detail.set_saved_role(self.saved_role_id)
        self.detail.controls.hide()
        self.detail.controls_gap.hide()
        self.show_stage(4)

    def _save_goal(self, role_id, coarse_goal_id):
        if self.on_select_goal is not None:
            self.on_select_goal(role_id, coarse_goal_id)
            self.saved_role_id = role_id
            self.detail.set_saved_role(role_id)

    def clear_profile(self):
        self.education.clear()
        self.experiences.clear()
        for button in self.activities.values():
            button.setChecked(False)
        self.interests.clear()
        self.results = ()
        self.result_position, self.restore_result = 0, False
        self.result_focus = None
        clear_layout(self.panels[3].layout())
        self.show_stage(0)

    def done(self, result):
        self.clear_profile()
        super().done(result)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.stage == 4:
            self.back()
            event.accept()
        else:
            super().keyPressEvent(event)
