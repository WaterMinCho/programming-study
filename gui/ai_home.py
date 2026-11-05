# -*- coding: utf-8 -*-
"""AI 비전 개론 홈(AiHomePage)과 차시 화면(AiLessonPage).

홈: 위 막대(← 처음 화면), 제목과 세 단계 안내(단원 읽기, 그 단원 문항 풀기, 다음 날부터 복습), 알림 줄(시험까지 남은 날, 오늘 푼 문항,
외운 문항), 이어서 할 일 카드(화면에 하나뿐인 주 단추), 학습 단원 구역(차시마다 한 줄, 준비 중인 차시는 끝의 글자 단추 하나로 접음),
문제집 구역(복습 문항과 외운 문항의 낱말 풀이, 섞어 풀기, 공개된 차시마다 차시 문제집, 오답 노트), 상황별 코드 구역(공개된 단원마다 한 줄,
준비 중 단원은 같은 꼴로 접음). 읽기가 풀기보다 먼저라 학습 단원을 문제집 위에 둠. 상황별 코드 단원은 권하는 차시를 읽은 뒤에
읽고(학습 루프는 6차시 뒤) 이어서 할 일 카드도 그때 권하므로 맨 아래에 둠. 하루 목표는 두지 않고(2026-11-03 사용자 결정) 문제집을
원하는 만큼 풀게 함. 문제집 줄은 외운 문항과 복습 문항을, 학습 단원 줄은 읽은 단원 수를, 상황별 코드 줄은 권하는 차시와 외운 문항·복습
(안 읽었으면 읽는 시간)을 씀. 상황별 코드 단원은 권하는 차시를 읽기 전에도 열 수 있음.
모의고사 구역은 문항이 공개된 회차만 보임.
차시 화면: 단원 줄, [전체 노트]·[외울 것], 아래 막대의 [이 차시 풀기]. 수치는 모두 AiSession 이 계산한 값이고 화면 글은 gui/ai_text.py 가 만듦."""
from PyQt6.QtWidgets import QWidget

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
        root.addWidget(kit.heading(kit.label(ai_text.TRACK, "title"),
                                   kit.para("\n".join(ai_text.STEPS), "body", "secondary")))
        root.addSpacing(theme.GAP["description_content"])
        lead = QWidget()
        lead_box = kit.box(lead, spacing=theme.GAP["group"])
        self.info = kit.label("", "caption", "secondary")
        lead_box.addWidget(self.info)
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
        try:
            overview = self.overview = self.win.ai.overview()
        except SessionError as error:
            self.overview = None
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
        self.notice.text.setText("\n".join(lines))
        self.notice.setToolTip("\n".join("%s: %s" % (row["title"], row["error"]) for row in overview["lessons"] + overview["patterns"]
                                         if row.get("error")))
        self.notice.setVisible(bool(lines))
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
        self.mock_section.setVisible(bool(rows))
        for spec in rows:
            state = self.win.ai.mock_state(spec['id'])
            end = '풀기 전'
            if state['error']:
                end = '자료 확인 필요'
            elif state['active']:
                end = '남은 시간 %d분' % ((state['remaining'] + 59) // 60)
            elif state['first_score'] is not None:
                end = '%d / %d' % (state['first_score'], spec['count'])
            row = self.mock_list.add(kit.Row(spec['title'], '%d문항 · %d분 · %d~%d차시' %
                                            (spec['count'], spec['minutes'], spec['range'][0], spec['range'][1]), end=end))
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
            book = self.books.add(kit.Row(ai_text.BOOK % row["no"], ai_text.book_line(row), "예습" if row["preview"] else "",
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
                    waiting.append(ai_text.lesson_title(row["no"], row["title"]))
                continue
            ready += 1
            line = kit.Row(ai_text.lesson_title(row["no"], row["title"]), ai_text.lesson_line(row), "예습" if row["preview"] else "",
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
                row = kit.Row(unit["label"], ai_text.pattern_line(unit), mark=kit.Dot("done" if unit["read"] else "todo"),
                              data=(group["id"], unit["key"]))
                row.clicked.connect(lambda lid=group["id"], key=unit["key"]: self.open_unit(lid, key))
                self.pattern_list.add(row)
        self.pattern_list.add_more(waiting, ai_text.PREPARING)
        self.pattern_section.setVisible(bool(self.pattern_list.rows or waiting))

    def open_unit(self, lid, key):
        if not self.busy:
            self.win.open_ai_unit(lid, key)

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
        """이어서 할 일. 안 읽은 단원, 복습(오늘 틀린 문항이 맨 앞에 나옴), 다시 보기."""
        target = self.target
        if target is None or self.busy:
            return
        kind = target["kind"]
        if kind == "unit":
            self.win.open_ai_unit(target["lesson"], target["unit"])
        elif kind in ("review", "again"):
            self.win.open_ai_practice("review")
        elif kind == "revisit":
            self.win.open_ai_revisit()
        elif kind == 'mock':
            self.win.open_ai_mock(target['mock'])

    def set_busy(self, busy, text=""):
        """문제 받기·제출이 기록을 쓰는 동안 줄과 단추를 끔. 섞어 풀기는 끝나도 읽은 단원이 있을 때만 다시 켬."""
        self.busy = busy
        for widget in (self.hub_btn, self.next_btn):
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
        self.memo_btn = self.top.add_right(kit.button("외울 것", "text", "s"), flush=True)
        self.note_btn.setToolTip("이 차시의 모든 단원을 정답을 편 채로 다시 읽습니다. 다시 읽기는 외운 문항에 넣지 않습니다.")
        self.memo_btn.setToolTip("이 차시 모든 단원의 외울 것을 답을 가린 질문으로 모아 봅니다.")
        outer.addWidget(self.top)
        inner = QWidget()
        root = kit.box(inner, (0, 24, 0, 48))
        head, _, self.unit_count = kit.section("단원")
        root.addLayout(head)
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
        self.title.setText(ai_text.lesson_title(data["no"], data["title"]))
        self.title.show()
        self.unit_list.clear()
        for unit in data["units"]:
            row = kit.Row(unit["title"], ai_text.unit_line(unit), " · ".join(ai_text.unit_badges(unit)),
                          kit.Dot("done" if unit["read"] else "todo"), unit["key"])
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
