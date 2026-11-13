# -*- coding: utf-8 -*-
"""AI 개론·응용 홈과 차시별 학습 목록을 구성함.

읽던 단계, 단원 연습, 날짜를 띄운 복습 기록을 구분해 표시함.
상황별 코드와 모의고사는 현재 과정에 공개된 항목만 표시함.
혼합 모의고사는 두 탭에서 같은 응시 기록을 사용함."""
from PyQt6.QtWidgets import QWidget

from aiprep import bank, mixed_mock
from gui import ai_text, kit, theme
from gui.wrong_page import count_line
from session import SessionError


class AiHomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.overview, self.target, self.busy, self.mixed_ready = None, None, False, False
        self.mixed_row, self.notes_row = None, None
        outer = kit.box(self)
        top = kit.TopBar("← 처음 화면", plain=True)
        self.hub_btn = top.back
        top.row.addStretch(1)  # 제목이 없는 막대라 돌아가기를 왼쪽 끝에 붙임
        outer.addWidget(top)

        inner = QWidget()
        root = kit.box(inner, (0, 24, 0, 48))
        from gui import ai_guide
        guide_line = QWidget()
        guide_row = kit.box(guide_line, horizontal=True)
        self.guide_btn = kit.button("학습·사용 안내")
        self.guide_btn.clicked.connect(lambda: ai_guide.open_guide(self))
        self.data_btn = kit.button("학습 데이터")
        self.data_btn.clicked.connect(self.open_data)
        guide_flow = QWidget()
        flow = kit.FlowLayout(guide_flow, spacing=12)
        flow.addWidget(self.guide_btn)
        flow.addWidget(self.data_btn)
        guide_row.addWidget(guide_flow, 1)
        root.addWidget(kit.heading(kit.label(ai_text.TRACK, "title"),
                                   guide_line))
        root.addSpacing(theme.GAP["description_content"])
        self.course_tabs = kit.TabBar(["개론", "응용"], deferred=True)
        self.course_tabs.setAccessibleName("AI 학습 과정")
        self.course_tabs.picked.connect(lambda n: self.win.switch_ai_course(("intro", "app")[n]))
        root.addWidget(self.course_tabs)
        root.addSpacing(theme.GAP["group"])
        self.course_intro = kit.para("", "body", "secondary")
        root.addWidget(self.course_intro)
        root.addSpacing(theme.GAP["group"])
        lead = QWidget()
        lead_box = kit.box(lead, spacing=theme.GAP["group"])
        self.info = kit.label("", "caption", "secondary")
        lead_box.addWidget(self.info)
        self.revision_note = kit.para("", "caption", "secondary")
        self.revision_note.hide()
        lead_box.addWidget(self.revision_note)
        self.notice = kit.banner("", "danger")  # 기록을 읽지 못한 까닭이나 읽지 못한 차시
        self.notice.hide()
        lead_box.addWidget(self.notice)
        self.next_card = kit.NextCard()
        self.next_btn = self.next_card.button
        lead_box.addWidget(self.next_card)
        root.addWidget(lead)

        root.addSpacing(theme.GAP["section"])
        head, _, self.lesson_count = kit.section("학습 단원")
        root.addLayout(head)
        root.addSpacing(theme.GAP["description_content"])
        self.lesson_list = kit.RowList()
        root.addWidget(self.lesson_list)

        root.addSpacing(theme.GAP["section"])
        head, _, _ = kit.section("문제집")
        root.addWidget(kit.heading(head, kit.para(ai_text.TERMS, "caption", "secondary")))
        root.addSpacing(theme.GAP["description_content"])
        self.books = kit.RowList()
        root.addWidget(self.books)

        self.pattern_section = QWidget()  # index.json 에 상황별 코드 무리가 없으면 숨김
        pattern_box = kit.box(self.pattern_section, (0, theme.GAP["section"], 0, 0))
        head, _, _ = kit.section("상황별 코드")
        pattern_box.addLayout(head)
        pattern_box.addSpacing(theme.GAP["description_content"])
        self.pattern_list = kit.RowList()
        pattern_box.addWidget(self.pattern_list)
        root.addWidget(self.pattern_section)
        self.mock_section = QWidget()
        mock_box = kit.box(self.mock_section, (0, theme.GAP["section"], 0, 0))
        head, _, _ = kit.section('모의고사')
        mock_box.addWidget(kit.heading(head, kit.para('제한 시간 동안 풀고 제출한 뒤 정답과 해설을 확인합니다. 중간에 나가도 시간은 계속 흐릅니다.', 'caption', 'secondary')))
        mock_box.addSpacing(theme.GAP["description_content"])
        self.mock_list = kit.RowList()
        mock_box.addWidget(self.mock_list)
        self.mock_pending = kit.para('', 'body', 'secondary')
        mock_box.addWidget(self.mock_pending)
        root.addWidget(self.mock_section)
        root.addStretch(1)
        column = kit.column(inner)
        column.setContentsMargins(kit.MARGIN, 0, kit.MARGIN, 0)
        self.scroll = kit.scroll(column)
        outer.addWidget(self.scroll, 1)

        self.hub_btn.clicked.connect(lambda: self.win.go_hub())
        self.next_btn.clicked.connect(self.open_next)

    def refresh(self):
        """서비스에서 현황을 다시 읽어 칸을 채움. 기록을 읽지 못하면 띠에 이유를 보이고 수치 줄과 목록을 비움."""
        course = getattr(self.win.ai, "course", "intro")
        self.course_tabs.set_current(1 if course == "app" else 0)
        self.course_intro.setText("AI 응용 · 이미지를 준비하고 분류·검출에 연결합니다. 초판 자료는 확인한 단원부터 공개합니다." if course == "app" else
                                  "AI 개론 · 데이터와 모델, 손실과 기울기를 연결해 학습 원리를 익힙니다.")
        try:
            overview = self.overview = self.win.ai.overview()
        except SessionError as error:
            self.overview = None
            self.revision_note.hide()
            self.notice.text.setText("%s\n%s" % (error, ai_text.FIX_HINT))
            self.notice.show()
            self.info.setText("")
            self.info.hide()
            self.lesson_count.setText("")
            self.lesson_list.clear()
            self.pattern_list.clear()
            self.pattern_section.hide()
            self.mock_section.hide()
            self.next_card.hide()
            self.show_books(None)
            return
        broken = [row["title"] for row in overview["lessons"] if row.get("error")]
        lines = [ai_text.BROKEN % ", ".join(broken)] if broken else []
        lines += [ai_text.PATTERN_BROKEN % group["title"] for group in overview["patterns"] if group.get("error")]
        version_error = overview.get("errors", {}).get("card_versions")
        if version_error:
            lines.append(version_error)
        collection_error = self.win.ai.collection.status()["error"]
        if collection_error:
            lines.append(collection_error)
        self.notice.text.setText("\n".join(lines))
        self.notice.setToolTip("\n".join("%s: %s" % (row["title"], row["error"]) for row in overview["lessons"] + overview["patterns"]
                                         if row.get("error")))
        self.notice.setVisible(bool(lines))
        revision_notes = []
        if overview.get("revised_cards"):
            revision_notes.append("내용이 바뀐 %d문항은 새 내용으로 복습을 확인합니다." % overview["revised_cards"])
        if overview.get("legacy_cards"):
            revision_notes.append("문항 버전이 없는 %d문항은 이전 풀이로 복습 현황을 계산합니다." % overview["legacy_cards"])
        self.revision_note.setText("\n".join(revision_notes))
        self.revision_note.setVisible(bool(revision_notes))
        self.info.setText(ai_text.exam_line(overview, self.win.ai.today()))
        self.info.setVisible(bool(self.info.text()))
        self.show_next(overview)
        self.show_books(overview)
        self.show_lessons(overview)
        self.show_patterns(overview)
        self.show_mocks(overview)

    def show_mocks(self, overview):
        self.mock_list.clear()
        rows = [row for row in overview['mocks'] if row['ready']]
        pending = overview.get('mock_pending', '')
        self.mock_pending.setText(pending)
        self.mock_pending.setVisible(bool(pending))
        self.mock_section.setVisible(bool(rows) or bool(pending))
        for spec in rows:
            state = self.win.ai.mock_state(spec['id'])
            end = '풀기 전'
            if state['error']:
                end = '자료 확인 필요'
            elif state['active']:
                end = '남은 시간 %d분' % ((state['remaining'] + 59) // 60)
            elif state['first_score'] is not None:
                end = '%d / %d' % (state['first_score'], spec['count'])
            detail = mixed_mock.description(spec) if mixed_mock.candidate(spec) else '%d문항 · %d분 · %d~%d차시' % (
                spec['count'], spec['minutes'], spec['range'][0], spec['range'][1])
            row = self.mock_list.add(kit.Row(spec['title'], detail, end=end))
            if state['error']:
                row.setToolTip(state['error'])
            row.clicked.connect(lambda checked=False, mid=spec['id']: self.win.open_ai_mock(mid))

    def show_books(self, overview):
        """문제집 구역. 섞어 풀기, 공개된 차시마다 차시 문제집, 오답 노트 순. overview 가 None 이면(기록을 읽지 못함) 줄 이름만 두고 끔."""
        self.books.clear()
        read = ai_text.read_counts(overview)[1] if overview else 0
        self.mixed_ready = bool(read)
        self.mixed_row = self.books.add(kit.Row("섞어 풀기", ai_text.mixed_line(overview) if overview else "", mark=kit.Dot(
            "review" if overview and overview["due"] else ("progress" if read else "todo"))))
        self.mixed_row.clicked.connect(self.open_mixed)
        for row in (overview["lessons"] if overview else []):
            if not row["ready"]:
                continue
            book = self.books.add(kit.Row(ai_text.lesson_title(row["no"], "문제집", row.get("course", "intro")), ai_text.book_line(row), "예습" if row["preview"] else "",
                                          kit.Dot(ai_text.book_dot(row)), row["id"]))
            book.clicked.connect(lambda lid=row["id"]: self.open_book(lid))
        groups = ai_text.AiNotes(self.win).groups() if overview else []  # 기록이 깨졌으면 빈 목록
        self.notes_row = self.books.add(kit.Row(ai_text.NOTES_ROW, count_line(groups) if overview else "", mark=kit.Dot(
            "review" if any(i["state"] != "fixed" for g in groups for i in g["items"]) else "todo")))
        self.notes_row.clicked.connect(self.open_notes)
        self.set_busy(self.busy)
        if overview is None:
            for row in self.books.rows:
                kit.set_inert(row, True)

    def show_next(self, overview):
        target = self.target = ai_text.next_item(overview, self.win.ai.today())
        self.next_card.set_item(target["title"], target["line"], target["action"])
        self.next_card.show()

    def show_lessons(self, overview):
        self.lesson_list.clear()
        waiting = []
        ready = 0
        for row in overview["lessons"]:
            if not row["ready"]:
                if not row.get("error"):
                    waiting.append(ai_text.lesson_title(row["no"], row["title"], row.get("course", "intro")))
                continue
            ready += 1
            line = kit.Row(ai_text.lesson_title(row["no"], row["title"], row.get("course", "intro")), ai_text.lesson_line(row), "예습" if row["preview"] else "",
                           kit.Dot(ai_text.lesson_dot(row)), row["id"])
            line.clicked.connect(lambda lid=row["id"]: self.open_lesson(lid))
            self.lesson_list.add(line)
        self.lesson_list.add_more(waiting, ai_text.PREPARING)
        self.lesson_count.setText("공개된 차시 %d개" % ready if ready else "")

    def show_patterns(self, overview):
        """상황별 코드 구역. 공개된 단원은 한 줄(제목은 단원 이름 "학습 루프 · 미니배치 학습 한 에폭", 점은 읽음 체크·안 읽음 빈 원),
        준비 중 단원은 끝의 글자 단추로 접음. 무리를 읽지 못했으면 그 무리 줄은 그리지 않고 띠가 까닭을 알림(차시와 같음).
        그릴 줄이 없으면 구역을 숨김."""
        self.pattern_list.clear()
        waiting = []
        for group in overview["patterns"]:
            if group.get("error"):
                continue
            for unit in group["units"]:
                if not unit["ready"]:
                    waiting.append(unit["label"])
                    continue
                dot = "done" if unit.get("practiced") else "progress" if unit["read"] else "todo"
                row = kit.Row(unit["label"], ai_text.pattern_line(unit), mark=kit.Dot(dot),
                              data=(group["id"], unit["key"]), wrap=True)
                row.setToolTip(ai_text.TERMS)
                row.clicked.connect(lambda lid=group["id"], key=unit["key"]: self.open_unit(lid, key))
                self.pattern_list.add(row)
        self.pattern_list.add_more(waiting, ai_text.PREPARING)
        self.pattern_section.setVisible(bool(self.pattern_list.rows or waiting))

    def open_unit(self, lid, key):
        if not self.busy:
            self.win.open_ai_unit(lid, key)

    def open_data(self):
        if self.busy:
            return
        from gui.ai_data import LearningDataDialog
        self.data_dialog = LearningDataDialog(self, self.win.ai.collection, host=self.win)
        self.data_dialog.show()

    def open_lesson(self, lid):
        if not self.busy:
            self.win.open_ai_lesson(lid)

    def open_book(self, lid):
        if not self.busy:
            self.win.open_ai_practice("lesson", lesson=lid)

    def open_mixed(self):
        if not self.busy and self.mixed_ready:
            self.win.open_ai_practice("mixed")

    def open_notes(self):
        if not self.busy:
            self.win.show_wrong("ai", "ai")

    def open_next(self):
        """마지막 학습 단계나 미완료 연습 묶음을 엶."""
        target = self.target
        if target is None or self.busy:
            return
        kind = target["kind"]
        if kind == "unit":
            self.win.open_ai_unit(target["lesson"], target["unit"], target.get("step"))
        elif kind == "practice":
            self.win.open_ai_practice(target["mode"], lesson=target.get("lesson"), unit=target.get("unit"), card=target.get("card"))
        elif kind in ("review", "again"):
            self.win.open_ai_practice("review")
        elif kind == "revisit":
            self.win.open_ai_revisit()
        elif kind == 'mock':
            self.win.open_ai_mock(target['mock'])

    def set_busy(self, busy, text=""):
        """문제 받기·제출이 기록을 쓰는 동안 줄과 단추를 끔. 섞어 풀기는 끝나도 읽은 단원이 있을 때만 다시 켬."""
        self.busy = busy
        for widget in (self.hub_btn, self.next_btn, self.data_btn, self.course_tabs):
            widget.setEnabled(not busy)
        for row in self.books.rows + self.lesson_list.rows + self.pattern_list.rows + self.mock_list.rows:
            kit.set_inert(row, busy or (row is self.mixed_row and not self.mixed_ready))

    def restyle(self):
        for widget in self.findChildren(kit.Dot) + self.findChildren(kit.Chevron):
            widget.update()


class AiLessonPage(QWidget):
    """차시 화면(설계 2.3). 단원 줄을 누르면 학습 단원을 엶."""

    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.lid, self.busy = None, False
        outer = kit.box(self)
        self.top = kit.TopBar("← AI 비전 개론", "")
        self.back_btn, self.title = self.top.back, self.top.title
        self.note_btn = self.top.add_right(kit.button("전체 노트", "text", "s"))
        self.memo_btn = self.top.add_right(kit.button("복습 질문", "text", "s"), flush=True)
        self.note_btn.setToolTip("이 차시의 모든 단원을 정답을 편 채로 다시 읽습니다. 다시 읽기는 복습 확인 기록으로 세지 않습니다.")
        self.memo_btn.setToolTip("이 차시의 복습 질문을 모아 엽니다. 질문을 누르면 답이 펼쳐집니다.")
        self.memo_btn.setAccessibleDescription(self.memo_btn.toolTip())
        outer.addWidget(self.top)
        inner = QWidget()
        root = kit.box(inner, (0, 24, 0, 48))
        head, _, self.unit_count = kit.section("단원")
        root.addWidget(kit.heading(head, kit.para("읽기·단원 연습·날짜를 띄운 복습 확인 기록을 따로 표시합니다.", "caption", "secondary")))
        root.addSpacing(theme.GAP["description_content"])
        self.unit_list = kit.RowList()
        root.addWidget(self.unit_list)
        root.addSpacing(16)
        root.addWidget(kit.para(ai_text.LESSON_PRACTICE, "caption", "secondary"))
        root.addStretch(1)
        column = kit.column(inner)
        column.setContentsMargins(kit.MARGIN, 0, kit.MARGIN, 0)
        outer.addWidget(kit.scroll(column), 1)
        self.bar = kit.BottomBar()
        self.practice_btn = self.bar.add_action(kit.button("이 차시 풀기", "primary", "l"))
        self.practice_btn.setToolTip(ai_text.LESSON_PRACTICE)
        outer.addWidget(self.bar)
        self.back_btn.clicked.connect(lambda: self.win.go_ai())
        self.note_btn.clicked.connect(lambda: self.win.open_ai_note(self.lid))
        self.memo_btn.clicked.connect(lambda: self.win.open_ai_note(self.lid, only_memo=True))
        self.practice_btn.clicked.connect(lambda: self.win.open_ai_practice("lesson", lesson=self.lid))

    def load(self, lid):
        """차시를 올림. 준비 중이거나 읽지 못한 차시면 AiError."""
        data = self.win.ai.lesson(lid)
        self.lid = lid
        self.title.setText(ai_text.lesson_title(data["no"], data["title"], self.win.ai.course))
        self.back_btn.setText("← " + bank.COURSES[self.win.ai.course])
        self.title.show()
        self.unit_list.clear()
        for unit in data["units"]:
            dot = "done" if unit.get("practiced") else "progress" if unit["read"] else "todo"
            row = kit.Row(unit["title"], ai_text.unit_line(unit), " · ".join(ai_text.unit_badges(unit)),
                          kit.Dot(dot), unit["key"], wrap=True)
            row.setToolTip(ai_text.TERMS)
            row.clicked.connect(lambda key=unit["key"]: self.open_unit(key))
            self.unit_list.add(row)
        read = sum(1 for unit in data["units"] if unit["read"])
        self.unit_count.setText("%d개 중 %d개 읽음" % (len(data["units"]), read))

    def open_unit(self, key):
        if not self.busy:
            self.win.open_ai_unit(self.lid, key)

    def set_busy(self, busy, text=""):
        self.busy = busy
        for widget in (self.back_btn, self.note_btn, self.memo_btn, self.practice_btn):
            widget.setEnabled(not busy)

    def restyle(self):
        for widget in self.findChildren(kit.Dot) + self.findChildren(kit.Chevron):
            widget.update()
