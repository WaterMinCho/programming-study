# -*- coding: utf-8 -*-
"""AI 개론·응용 홈과 차시별 학습 목록을 구성함.

읽던 단계, 단원 연습, 날짜를 띄운 복습 기록을 구분해 표시함.
분류 선택을 고정하고 현재 과정의 목록과 공개 준비 상태를 표시함.
혼합 모의고사는 두 탭에서 같은 응시 기록을 사용함."""
from PyQt6.QtWidgets import QWidget

from aiprep import bank, mixed_mock
from gui import ai_text, kit, theme
from gui.wrong_page import count_line
from gui.section_browser import SectionBrowser
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
        self.top = kit.TopBar("← 처음 화면", plain=True)
        self.hub_btn = self.top.back
        self.top.row.addStretch(1)
        outer.addWidget(self.top)
        header = QWidget()
        row = kit.box(header, (0, theme.GAP["detail"], 0, 0),
                      spacing=theme.GAP["detail"])
        self.course_tabs = kit.NavigationTabs(["AI 개론", "AI 응용"], deferred=True)
        self.course_tabs.setAccessibleName("AI 학습 과정")
        for tab, description in zip(self.course_tabs.buttons, (
                "데이터와 모델, 딥러닝 학습 원리를 익힙니다.",
                "OpenCV로 이미지와 동영상을 다루는 방법을 익힙니다.")):
            tab.setToolTip(description)
            tab.setAccessibleDescription(description)
        self.course_tabs.picked.connect(lambda n: self.win.switch_ai_course(("intro", "app")[n]))
        row.addWidget(self.course_tabs)
        self.browser = SectionBrowser(header=header)
        self.scroll = self.browser.scroll
        outer.addWidget(self.browser, 1)
        from gui import ai_guide
        self.guide_btn = kit.button("학습·사용 안내", "text", onbg=True)
        self.guide_btn.clicked.connect(lambda: ai_guide.open_guide(self))
        self.data_btn = kit.button("학습 기록 설정", "text", onbg=True)
        self.data_btn.setToolTip("AI 기록 제공 상태를 확인하고 수집을 중단하거나 기록 파일을 저장합니다.")
        self.data_btn.clicked.connect(self.open_data)
        guide_flow = QWidget()
        flow = kit.FlowLayout(guide_flow, spacing=12)
        flow.addWidget(self.guide_btn)
        flow.addWidget(self.data_btn)
        self.notice = kit.banner("", "danger")
        self.browser.body.addWidget(self.notice)
        self.notice.hide()

        lessons = QWidget()
        root = kit.box(lessons, spacing=theme.GAP["description_content"])
        root.addWidget(guide_flow)
        self.info = kit.label("", "caption", "secondary")
        root.addWidget(self.info)
        self.revision_note = kit.para("", "caption", "secondary")
        self.revision_note.hide()
        root.addWidget(self.revision_note)
        self.next_card = kit.NextCard()
        self.next_btn = self.next_card.button
        root.addWidget(self.next_card)
        root.addSpacing(theme.GAP["group"])
        head, _, self.lesson_count = kit.section("학습 단원")
        self.course_intro = kit.para("", "body", "secondary")
        root.addWidget(kit.heading(head, self.course_intro))
        self.lesson_list = kit.RowList()
        root.addWidget(self.lesson_list)
        self.lesson_empty = kit.para("", "body", "secondary")
        root.addWidget(self.lesson_empty)
        self.browser.add_section("lessons", "학습 단원", "그림과 예제를 읽고 단원별로 연습합니다.", lessons)

        books = QWidget()
        root = kit.box(books, spacing=theme.GAP["description_content"])
        head, _, _ = kit.section("문제집")
        root.addWidget(kit.heading(head, kit.para(ai_text.TERMS, "caption", "secondary")))
        self.books = kit.RowList()
        root.addWidget(self.books)
        self.browser.add_section("books", "문제집", "차시 문제집, 섞어 풀기와 오답 노트를 엽니다.", books)

        patterns = QWidget()
        root = kit.box(patterns, spacing=theme.GAP["description_content"])
        head, _, self.pattern_count = kit.section(ai_text.CODING_TITLE)
        root.addWidget(kit.heading(head, kit.para("학습·평가·분류에 쓰는 코드를 읽고 빈칸과 실행 순서를 연습합니다.", "caption", "secondary")))
        self.pattern_section = QWidget()
        pattern_box = kit.box(self.pattern_section)
        self.pattern_list = kit.RowList()
        pattern_box.addWidget(self.pattern_list)
        root.addWidget(self.pattern_section)
        self.pattern_empty = kit.para("", "body", "secondary")
        root.addWidget(self.pattern_empty)
        self.browser.add_section("coding", ai_text.CODING_TITLE, "상황에 맞는 코드와 실행 순서를 연습합니다.", patterns)

        mocks = QWidget()
        root = kit.box(mocks, spacing=theme.GAP["description_content"])
        head, _, self.mock_count = kit.section("모의고사")
        root.addWidget(kit.heading(head, kit.para("제한 시간 동안 풀고 제출한 뒤 정답과 해설을 확인합니다. 중간에 나가도 시간은 계속 흐릅니다.", "caption", "secondary")))
        self.mock_section = QWidget()
        mock_box = kit.box(self.mock_section, spacing=theme.GAP["description_content"])
        self.mock_list = kit.RowList()
        mock_box.addWidget(self.mock_list)
        self.mock_pending = kit.para("", "body", "secondary")
        mock_box.addWidget(self.mock_pending)
        root.addWidget(self.mock_section)
        self.mock_empty = kit.para("", "body", "secondary")
        root.addWidget(self.mock_empty)
        self.browser.add_section("mocks", "모의고사", "회차를 골라 제한 시간 안에 풉니다.", mocks)
        self.browser.body.addStretch(1)
        focus_order = [self.hub_btn, *self.course_tabs.buttons, *self.browser.buttons.values(), self.guide_btn, self.data_btn, self.next_btn]
        for first, second in zip(focus_order, focus_order[1:]):
            QWidget.setTabOrder(first, second)

        self.hub_btn.clicked.connect(lambda: self.win.go_hub())
        self.next_btn.clicked.connect(self.open_next)

    def refresh(self):
        """서비스에서 현황을 다시 읽어 칸을 채움. 기록을 읽지 못하면 띠에 이유를 보이고 수치 줄과 목록을 비움."""
        course = getattr(self.win.ai, "course", "intro")
        self.browser.begin_refresh((self.win.user, course))
        course_index = 1 if course == "app" else 0
        self.course_tabs.set_current(course_index)
        QWidget.setTabOrder(self.hub_btn, self.course_tabs.buttons[course_index])
        self.course_intro.setText("AI 응용 · 이미지를 준비하고 분류·검출에 연결합니다. 자료는 확인을 마친 단원부터 공개합니다." if course == "app" else
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
            self.mock_list.clear()
            self.mock_section.hide()
            self.pattern_count.setText("")
            self.mock_count.setText("")
            for empty in (self.lesson_empty, self.pattern_empty, self.mock_empty):
                empty.setText("기록을 읽지 못해 목록을 표시할 수 없습니다.")
                empty.show()
            self.next_card.hide()
            self.show_books(None)
            self.browser.finish_refresh()
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
            revision_notes.append("수정된 %d문항 · 새 내용으로 복습 확인" % overview["revised_cards"])
        if overview.get("legacy_cards"):
            revision_notes.append("버전이 없는 %d문항 · 이전 풀이로 집계" % overview["legacy_cards"])
        self.revision_note.setText("\n".join(revision_notes))
        self.revision_note.setVisible(bool(revision_notes))
        self.info.setText(ai_text.exam_line(overview, self.win.ai.today()))
        self.info.setVisible(bool(self.info.text()))
        self.show_next(overview)
        self.show_books(overview)
        self.show_lessons(overview)
        self.show_patterns(overview)
        self.show_mocks(overview)
        self.set_busy(self.busy)
        self.browser.finish_refresh()

    def show_mocks(self, overview):
        self.mock_list.clear()
        rows = [row for row in overview['mocks'] if row['ready']]
        pending = overview.get('mock_pending', '')
        self.mock_pending.setText(pending)
        self.mock_pending.setVisible(bool(pending))
        self.mock_section.setVisible(bool(rows) or bool(pending))
        self.mock_count.setText('공개된 시험 %d개' % len(rows) if rows else '')
        self.mock_empty.setText('이 과정의 모의고사는 아직 공개하지 않았습니다.')
        self.mock_empty.setVisible(not rows and not pending)
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
            if state['error']:
                detail += '\n' + state['error']
            row = self.mock_list.add(kit.Row(spec['title'], detail, end=end, wrap=True))
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
        broken = any(row.get("error") for row in overview["lessons"])
        error_text = "일부 차시를 읽지 못했습니다. " if ready else "학습 자료를 읽지 못했습니다. "
        self.lesson_empty.setText(error_text + ai_text.FIX_HINT if broken else
                                  "아직 공개된 학습 단원이 없습니다." if not waiting else "학습 단원을 준비하고 있습니다.")
        self.lesson_empty.setVisible(not ready or broken)

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
        self.pattern_count.setText("공개된 단원 %d개" % len(self.pattern_list.rows) if self.pattern_list.rows else "")
        broken = any(group.get("error") for group in overview["patterns"])
        shown = bool(self.pattern_list.rows or waiting)
        error_text = "일부 코딩 실습을 읽지 못했습니다. " if shown else "코딩 실습 자료를 읽지 못했습니다. "
        self.pattern_empty.setText(error_text + ai_text.FIX_HINT if broken else
                                   "이 과정의 코딩 실습은 아직 공개하지 않았습니다.")
        self.pattern_empty.setVisible(broken or not shown)

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
            kit.set_inert(row, busy or self.overview is None or (row is self.mixed_row and not self.mixed_ready))

    def restyle(self):
        self.course_tabs.refont()
        self.browser.refont()
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
