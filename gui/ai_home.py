# -*- coding: utf-8 -*-
"""AI 개론·응용 홈과 차시별 학습 목록을 구성함.

읽던 단계, 단원 연습, 날짜를 띄운 복습 기록을 구분해 표시함.
분류 선택을 고정하고 현재 과정의 목록과 공개 준비 상태를 표시함.
모의고사 탭은 개론 세션으로 화면을 그리며 개론·응용 회차를 한 목록에 보임."""
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QBoxLayout, QWidget

from aiprep import bank, mixed_mock
from gui import ai_text, kit, theme
from gui.disclosure import DisclosureButton
from gui.wrong_page import count_line
from gui.section_browser import SectionBrowser
from session import SessionError


class CourseTabs(kit.NavigationTabs):
    """AI 개론·응용 과정 탭과 모의고사 탭. 공통 탭 동작은 그대로 두고 surface_alt 바탕(모서리 8, 안쪽 4) 위에 세 탭을 둠.
    고른 탭만 흰 면과 주 색 글자로 띄우고 안 고른 탭은 바탕 없이 muted 글자로 둠.
    어두운 테마에서는 surface 가 surface_alt 보다 어두워 고른 탭이 꺼져 보이므로 틀을 surface, 고른 탭을 hover,
    안 고른 탭에 마우스를 올린 바탕을 surface_alt 로 두어 틀 < 올림 < 고름 순으로 밝게 함."""
    def __init__(self, names, deferred=False):
        super().__init__(names, deferred=deferred)
        self.setObjectName("course_tabs")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = self.layout().itemAt(0).layout()
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(4)

    def refont(self):
        # 테두리 굵기가 고름(1)·초점(2)에 따라 달라도 탭 높이·글 자리가 같게, 테두리와 안쪽 여백의 합을 2 로 맞춤
        height = max(48, theme.TYPE["headline"][1] + 16) - 4
        color = lambda key: theme.qcolor(key).name()
        dark = theme.state["scheme"] == "dark"
        frame, over, picked = ("surface", "surface_alt", "hover") if dark else ("surface_alt", "hover", "surface")
        self.setStyleSheet(f"""
            QWidget#course_tabs {{ background: {color(frame)}; border-radius: {theme.RADIUS['dense_card']}px; }}
            QPushButton#tab {{ background: transparent; color: {color('muted')};
                font-size: {theme.TYPE['headline'][0]}px; font-weight: 700;
                min-height: {height}px; max-height: {height}px; padding: 1px 17px;
                border: 1px solid transparent; border-radius: {theme.RADIUS['dense_control']}px; }}
            QPushButton#tab:hover {{ background: {color(over)}; }}
            QPushButton#tab:checked {{ background: {color(picked)}; color: {color('primary')};
                border-color: {color('line')}; }}
            QPushButton#tab:focus {{ border: 2px dashed {color('focus')}; padding: 0 16px; }}
            QPushButton#tab:disabled {{ color: {color('faint')}; }}
            QPushButton#tab:checked:disabled {{ background: {color(picked)}; }}
        """)


TABS = ("intro", "app", "mock")  # AI 홈 탭 번호 순서. 셋째는 과정이 아니라 모의고사
TAIL_BAR = 120  # 차시 줄·단원 카드 머리의 읽은 단원 막대 폭


class TailRow(kit.Row):
    """꺾쇠 왼쪽에 tail 위젯(막대와 숫자, 꼬리표 묶음)을 더 둔 목록 줄. 줄바꿈 높이를 잴 때 앞 위젯과 tail 폭도 뺌.
    줄이 처음 보이기 전에는 새로 넣은 위젯이 아직 숨김 상태라 isHidden 을 보지 않고 늘 폭을 뺌."""
    tail = None

    def __init__(self, *args, tail=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tail = tail
        if tail is not None:
            self.layout().insertWidget(self.layout().indexOf(self.end) + 1, tail, 0, Qt.AlignmentFlag.AlignVCenter)

    def fit_height(self):
        super().fit_height()
        if not self.wrap or self.tail is None:
            return
        gap = self.text_box.spacing()
        pad = self.pad if self.least is not None else self.text_box.getContentsMargins()[1]
        size = lambda widget: widget.sizeHint().expandedTo(widget.minimumSize()).width() + 12
        width = max(1, self.width() - 2 * self.frameWidth() - 48 - 12 - kit.MARK - (kit.MARK + 12 if self.mark is not None else 0)
                    - (size(self.lead) if self.lead is not None else 0)
                    - (size(self.end) if self.end.text() else 0) - size(self.tail))
        text_height = self.title.heightForWidth(width)
        if self.second.text():
            text_height += gap + self.second.heightForWidth(width)
        self.setFixedHeight(max(self.height(), text_height + 2 * pad))

    def event(self, event):
        # 글자 크기를 바꾸면 refont 가 줄을 자식보다 먼저 다시 재므로, 자식 크기가 바뀐 뒤 오는 배치 요청 때 한 번 더 잼
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self.fit_height()
        return result


def read_bar(read, total):
    """읽은 단원 막대와 '읽은 수 / 단원 수' 숫자. 다 읽으면 막대를 success 로 칠함. (묶음, 막대, 숫자) 를 돌려줌."""
    out = QWidget()
    row = kit.box(out, spacing=12, horizontal=True)
    bar = kit.progress(thin=True)
    bar.setFixedWidth(TAIL_BAR)
    bar.setValue(round(100 * read / total) if total else 0)
    if total and read >= total:
        kit.set_tone(bar, "success")
    number = kit.label("%d / %d" % (read, total), "caption", "secondary")
    row.addWidget(bar, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(number, 0, Qt.AlignmentFlag.AlignVCenter)
    return out, bar, number


class GuideLine(QWidget):
    """안내 단추 묶음과 시험 날짜 글을 한 줄에 둠. 둘이 한 줄에 들어가지 않으면 날짜 글을 아래 줄로 내림."""
    def __init__(self, buttons, info):
        super().__init__()
        self.buttons, self.info = buttons, info
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(theme.GAP["detail"])
        self.row.addWidget(buttons, 1)
        self.row.addWidget(info, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def arrange(self):
        flow = self.buttons.layout()
        shown = [flow.itemAt(n).widget() for n in range(flow.count()) if not flow.itemAt(n).widget().isHidden()]
        need = (sum(widget.sizeHint().width() for widget in shown) + flow.spacing() * max(0, len(shown) - 1)
                + self.row.spacing() + self.info.sizeHint().width())
        stacked = not self.info.isHidden() and self.width() < need
        direction = QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight
        if self.row.direction() != direction:
            self.row.setDirection(direction)
            place = Qt.AlignmentFlag.AlignLeft if stacked else Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            self.row.setAlignment(self.info, place)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()


class AiHomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.overview, self.target, self.busy, self.mixed_ready = None, None, False, False
        self.mixed_row, self.notes_row = None, None
        outer = kit.box(self)
        self.top = kit.TopBar("← 처음 화면", "AI", plain=True, dense=True)
        self.hub_btn = self.top.back
        outer.addWidget(self.top)
        header = QWidget()
        row = kit.box(header, (0, theme.GAP["detail"], 0, 0),
                      spacing=theme.GAP["detail"])
        self.tab = "intro"  # 고른 탭. intro·app 은 과정, mock 은 모의고사
        self.old_open = False
        self.course_tabs = CourseTabs(["AI 개론", "AI 응용", "모의고사"], deferred=True)
        self.course_tabs.setAccessibleName("AI 학습 과정과 모의고사")
        for tab, description in zip(self.course_tabs.buttons, (
                "데이터와 모델, 딥러닝 학습 원리를 익힙니다.",
                "OpenCV로 이미지와 동영상을 다루는 방법을 익힙니다.",
                "개론과 응용 회차를 제한 시간 안에 풀고 결과를 확인합니다.")):
            tab.setToolTip(description)
            tab.setAccessibleDescription(description)
        self.course_tabs.picked.connect(lambda n: self.win.select_ai_tab(TABS[n]))
        row.addWidget(self.course_tabs)
        self.browser = SectionBrowser(header=header)
        self.scroll = self.browser.scroll
        outer.addWidget(self.browser, 1)
        from gui import ai_guide
        self.guide_btn = kit.button("학습·사용 안내", "text", "s", onbg=True)
        self.guide_btn.clicked.connect(lambda: ai_guide.open_guide(self))
        self.data_btn = kit.button("학습 기록 설정", "text", "s", onbg=True)
        self.data_btn.setToolTip("AI 기록 제공 상태를 확인하고 수집을 중단하거나 기록 파일을 저장합니다.")
        self.data_btn.clicked.connect(self.open_data)
        guide_flow = QWidget()
        flow = kit.FlowLayout(guide_flow, spacing=theme.GAP["detail"])
        flow.addWidget(self.guide_btn)
        self.guide_divider = kit.frame("rowline")  # 두 단추 사이 세로 구분
        self.guide_divider.setFixedSize(1, 12)
        flow.addWidget(self.guide_divider)
        flow.addWidget(self.data_btn)
        self.notice = kit.banner("", "danger")
        self.browser.body.addWidget(self.notice)
        self.notice.hide()

        lessons = QWidget()
        root = kit.box(lessons, spacing=16)
        self.info = kit.label("", "caption", "secondary")
        self.guide_line = GuideLine(guide_flow, self.info)
        root.addWidget(self.guide_line)
        self.guide_rule = kit.frame("rowline")
        self.guide_rule.setFixedHeight(1)
        root.addWidget(self.guide_rule)
        self.revision_note = kit.para("", "caption", "secondary")
        self.revision_note.hide()
        root.addWidget(self.revision_note)
        self.next_card = kit.NextCard(compact=True)
        self.next_btn = self.next_card.button
        root.addWidget(self.next_card)
        head, _, self.lesson_count = kit.section("학습 단원")
        self.course_intro = kit.para("", "body", "secondary")
        root.addWidget(kit.heading(head, self.course_intro))
        self.lessons_rule = kit.frame("rowline")  # 머리와 차시 목록 사이 1px 가로선
        self.lessons_rule.setFixedHeight(1)
        root.addWidget(self.lessons_rule)
        self.lesson_list = kit.RowList(separate=True, least=72, pad=11, gap=4)
        root.addWidget(self.lesson_list)
        self.lesson_empty = kit.para("", "body", "secondary")
        root.addWidget(self.lesson_empty)
        self.browser.add_section("lessons", "학습 단원", "그림과 예제를 읽고 단원별로 연습합니다.", lessons)

        books = QWidget()
        root = kit.box(books, spacing=16)
        head, _, _ = kit.section("문제집")
        root.addWidget(kit.heading(head, kit.para(ai_text.TERMS, "caption", "secondary")))
        self.books = kit.RowList(separate=True, least=72, pad=11, gap=4)
        root.addWidget(self.books)
        self.browser.add_section("books", "문제집", "차시 문제집, 섞어 풀기와 오답 노트를 엽니다.", books)

        patterns = QWidget()
        root = kit.box(patterns, spacing=16)
        head, _, self.pattern_count = kit.section(ai_text.CODING_TITLE)
        self.pattern_about = kit.para(ai_text.CODING_ABOUT["intro"], "caption", "secondary")
        root.addWidget(kit.heading(head, self.pattern_about))
        self.pattern_section = QWidget()
        pattern_box = kit.box(self.pattern_section)
        self.pattern_list = kit.RowList(separate=True, least=72, pad=11, gap=4)
        pattern_box.addWidget(self.pattern_list)
        root.addWidget(self.pattern_section)
        self.pattern_empty = kit.para("", "body", "secondary")
        root.addWidget(self.pattern_empty)
        self.browser.add_section("coding", ai_text.CODING_TITLE, "상황에 맞는 코드와 실행 순서를 연습합니다.", patterns)

        mocks = QWidget()
        root = kit.box(mocks, spacing=16)
        head, _, self.mock_count = kit.section("모의고사")
        root.addWidget(kit.heading(head, kit.para("제한 시간 동안 풀고 제출한 뒤 정답과 해설을 확인합니다. 중간에 나가도 시간은 계속 흐릅니다.", "caption", "secondary")))
        self.mock_notice = kit.banner("")
        self.mock_notice.hide()
        root.addWidget(self.mock_notice)
        self.mock_section = QWidget()
        mock_box = kit.box(self.mock_section, spacing=theme.GAP["description_content"])
        self.mock_list = kit.RowList(separate=True, least=72, pad=11, gap=4)
        mock_box.addWidget(self.mock_list)
        self.mock_pending = kit.para("", "body", "secondary")
        mock_box.addWidget(self.mock_pending)
        root.addWidget(self.mock_section)
        self.mock_empty = kit.para("", "body", "secondary")
        root.addWidget(self.mock_empty)
        self.old_toggle = DisclosureButton("이전에 푼 회차")
        self.old_toggle.toggled.connect(self.toggle_old)
        self.old_toggle.hide()
        root.addWidget(self.old_toggle)
        self.old_list = kit.RowList(separate=True, least=72, pad=11, gap=4)
        self.old_list.hide()
        root.addWidget(self.old_list)
        self.browser.add_section("mocks", "모의고사", "회차를 골라 제한 시간 안에 풉니다.", mocks, listed=False)
        self.browser.body.addStretch(1)
        focus_order = [self.hub_btn, *self.course_tabs.buttons, *self.browser.buttons.values(), self.guide_btn, self.data_btn, self.next_btn]
        for first, second in zip(focus_order, focus_order[1:]):
            QWidget.setTabOrder(first, second)

        self.hub_btn.clicked.connect(lambda: self.win.go_hub())
        self.next_btn.clicked.connect(self.open_next)

    def showEvent(self, event):
        kit.outline_settings(self)
        super().showEvent(event)

    def refresh(self):
        """서비스에서 현황을 다시 읽어 칸을 채움. 기록을 읽지 못하면 띠에 이유를 보이고 수치 줄과 목록을 비움."""
        course = getattr(self.win.ai, "course", "intro")
        if self.tab == "mock":
            self.browser.begin_refresh((self.win.user, "mock"), section="mocks")
        else:
            self.browser.begin_refresh((self.win.user, course))
        course_index = TABS.index(self.tab)
        self.course_tabs.set_current(course_index)
        anchor = getattr(self, "settings_btn", self.hub_btn)
        if anchor is not self.hub_btn:
            QWidget.setTabOrder(self.hub_btn, anchor)
        QWidget.setTabOrder(anchor, self.course_tabs.buttons[course_index])
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
            self.old_list.clear()
            self.old_list.hide()
            self.old_toggle.hide()
            self.mock_notice.hide()
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
        self.guide_line.arrange()
        self.show_next(overview)
        self.show_books(overview)
        self.show_lessons(overview)
        self.show_patterns(overview)
        self.show_mocks(overview)
        self.set_busy(self.busy)
        self.browser.finish_refresh()
        if self.tab == "mock":
            chain = [self.course_tabs.buttons[course_index], *self.mock_list.rows]
            if not self.old_toggle.isHidden():
                chain += [self.old_toggle, *(self.old_list.rows if self.old_open else [])]
            for first, second in zip(chain, chain[1:]):
                QWidget.setTabOrder(first, second)

    def show_mocks(self, overview):
        """모의고사 탭. 새 회차는 위 목록에, 예전 회차(legacy)와 제출한 숨긴 회차(hidden)는 접는 줄 아래에 둠.
        예전 회차를 풀다 만 사람에게는 그 회차를 목록에서 빼고 안내 띠를 보임."""
        self.mock_list.clear()
        self.old_list.clear()
        ready = [row for row in overview['mocks'] if row['ready']]
        rows = [row for row in ready if not (row.get('legacy') or row.get('hidden'))]
        old = [row for row in ready if row.get('legacy') or row.get('hidden')]
        pending = overview.get('mock_pending', '')
        self.mock_pending.setText(pending)
        self.mock_pending.setVisible(bool(pending))
        self.mock_section.setVisible(bool(rows) or bool(pending))
        self.mock_count.setText('공개된 시험 %d개' % len(rows) if rows else '')
        self.mock_empty.setText('아직 공개된 모의고사가 없습니다.')
        self.mock_empty.setVisible(not rows and not pending)
        for spec in rows:
            self.mock_list.add(self.mock_row(spec))
        for spec in old:
            self.old_list.add(self.mock_row(spec))
        self.old_toggle.setText('이전에 푼 회차 %d개' % len(old))
        self.old_toggle.setVisible(bool(old))
        self.old_toggle.blockSignals(True)
        self.old_toggle.setChecked(self.old_open)
        self.old_toggle.blockSignals(False)
        self.old_list.setVisible(bool(old) and self.old_open)
        drafts = overview.get('legacy_drafts') or []
        self.mock_notice.text.setText('풀던 이전 회차는 문항이 바뀌어 이어 풀 수 없습니다. 아래 목록의 새 회차를 처음부터 풀어 주세요.')
        self.mock_notice.setVisible(bool(drafts))

    def mock_row(self, spec):
        """회차 줄. 오른쪽 꼬리표는 풀기 전·푸는 중·첫 점수·자료 확인 필요 가운데 하나임."""
        state = self.win.ai.mock_state(spec['id'])
        end, tone, hint = '풀기 전', '', ''
        if state['error']:
            end, tone = '자료 확인 필요', 'danger'
        elif state['active']:
            end, tone = '푸는 중', 'accent'
            hint = '남은 시간 %d분' % ((state['remaining'] + 59) // 60)
        elif state['first_score'] is not None:
            end = '%d / %d' % (state['first_score'], spec['count'])
        detail = mixed_mock.description(spec) if mixed_mock.candidate(spec) else '%d문항 · %d분 · %d~%d차시' % (
            spec['count'], spec['minutes'], spec['range'][0], spec['range'][1])
        if state['error']:
            detail += '\n' + state['error']
        row = TailRow(spec['title'], detail, wrap=True, tail=kit.badge(end, tone))
        if state['error'] or hint:
            row.setToolTip(state['error'] or hint)
        if hint:
            row.setAccessibleDescription(hint)
        row.clicked.connect(lambda checked=False, mid=spec['id']: self.win.open_ai_mock(mid))
        return row

    def toggle_old(self, opened):
        self.old_open = bool(opened)
        self.old_list.setVisible(self.old_open and not self.old_toggle.isHidden())
        if self.tab == "mock":
            chain = [self.old_toggle, *(self.old_list.rows if self.old_open else [])]
            for first, second in zip(chain, chain[1:]):
                QWidget.setTabOrder(first, second)

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
        side, line = "", target["line"]
        if line.startswith("「") and "\n" in line:  # 「단원 이름」 줄은 제목 옆에 두고 나머지 줄을 설명으로 둠
            side, line = line.split("\n", 1)
        self.next_card.set_item(target["title"], line, target["action"])
        self.next_card.set_side(side)
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
            tail, line_bar, line_number = read_bar(row["read"], row["units_total"])
            line = TailRow(ai_text.lesson_title(row["no"], row["title"], row.get("course", "intro")), ai_text.lesson_line(row), "예습" if row["preview"] else "",
                           kit.Dot(ai_text.lesson_dot(row)), row["id"], strong=True, wrap=True,
                           lead=kit.number_chip("%02d" % row["no"], "accent", tile=True), tail=tail)
            line.bar, line.number = line_bar, line_number
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
        그릴 줄이 없으면 구역을 숨김. 구역 설명은 고른 과정을 따름."""
        self.pattern_about.setText(ai_text.CODING_ABOUT.get(overview.get("course"), ai_text.CODING_ABOUT["intro"]))
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
        for widget in (self.hub_btn, self.next_btn, self.data_btn, self.course_tabs, self.old_toggle):
            widget.setEnabled(not busy)
        for row in self.books.rows + self.lesson_list.rows + self.pattern_list.rows + self.mock_list.rows + self.old_list.rows:
            kit.set_inert(row, busy or self.overview is None or (row is self.mixed_row and not self.mixed_ready))

    def restyle(self):
        self.course_tabs.refont()
        self.browser.refont()
        self.old_toggle.refont()
        for widget in self.findChildren(kit.Dot) + self.findChildren(kit.Chevron) + [self.old_toggle.arrow]:
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
        self.top = kit.TopBar("← AI 비전 개론", "", dense=True)
        self.back_btn, self.title = self.top.back, self.top.title
        self.top.row.addStretch(1)
        self.note_btn = self.top.add_right(kit.button("전체 노트", "text", "s"))
        self.memo_btn = self.top.add_right(kit.button("복습 질문", "text", "s"))
        for button in (self.note_btn, self.memo_btn):
            button.setProperty("outlined", True)
        self.note_btn.setToolTip("이 차시의 모든 단원을 정답을 편 채로 다시 읽습니다. 다시 읽기는 복습 확인 기록으로 세지 않습니다.")
        self.memo_btn.setToolTip("이 차시의 복습 질문을 모아 엽니다. 질문을 누르면 답이 펼쳐집니다.")
        self.memo_btn.setAccessibleDescription(self.memo_btn.toolTip())
        outer.addWidget(self.top)
        inner = kit.dense(QWidget())
        root = kit.box(inner, (0, 16, 0, 24))
        self.unit_card, card_box = kit.card(16, 0)
        self.unit_bar = kit.progress(thin=True)
        self.unit_bar.setFixedWidth(TAIL_BAR)
        self.unit_count = kit.label("", "caption", bold=True)
        head, _ = kit.card_head(kit.heading(kit.label("단원", "headline"), kit.para(
            "읽기·단원 연습·날짜를 띄운 복습 확인 기록을 따로 표시합니다.", "caption", "secondary")), self.unit_bar, self.unit_count)
        card_box.addLayout(head)
        root.addWidget(self.unit_card)
        root.addSpacing(theme.GAP["description_content"])
        self.unit_list = kit.RowList(separate=True, least=64, pad=7, gap=4)  # 두 줄 글 높이 50 + 2 × 7 = 64
        root.addWidget(self.unit_list)
        root.addSpacing(16)
        root.addWidget(kit.para(ai_text.LESSON_PRACTICE, "caption", "secondary"))
        root.addStretch(1)
        outer.addWidget(kit.scroll(kit.dense_column(inner)), 1)
        self.bar = kit.BottomBar(dense=True)
        self.practice_btn = self.bar.add_action(kit.button("이 차시 풀기", "primary", "m"))
        self.practice_btn.setToolTip(ai_text.LESSON_PRACTICE)
        outer.addWidget(self.bar)
        self.back_btn.clicked.connect(lambda: self.win.go_ai())
        self.note_btn.clicked.connect(lambda: self.win.open_ai_note(self.lid))
        self.memo_btn.clicked.connect(lambda: self.win.open_ai_note(self.lid, only_memo=True))
        self.practice_btn.clicked.connect(lambda: self.win.open_ai_practice("lesson", lesson=self.lid))

    def showEvent(self, event):
        kit.outline_settings(self)
        super().showEvent(event)

    def load(self, lid):
        """차시를 올림. 준비 중이거나 읽지 못한 차시면 AiError."""
        data = self.win.ai.lesson(lid)
        self.lid = lid
        self.title.setText(ai_text.lesson_title(data["no"], data["title"], self.win.ai.course))
        self.back_btn.setText("← " + bank.COURSES[self.win.ai.course])
        self.title.show()
        self.unit_list.clear()
        for order, unit in enumerate(data["units"], 1):
            dot = "done" if unit.get("practiced") else "progress" if unit["read"] else "todo"
            badges = ai_text.unit_badges(unit)
            tail = None
            if badges:
                tail = QWidget()
                tail_box = kit.box(tail, spacing=8, horizontal=True)
                for text in badges:
                    tail_box.addWidget(kit.badge(text, "accent"), 0, Qt.AlignmentFlag.AlignVCenter)
            row = TailRow(unit["title"], ai_text.unit_line(unit), "", kit.Dot(dot), unit["key"], wrap=True,
                          lead=kit.number_chip("%02d" % order, "neutral"), tail=tail)
            row.badges = [tail_box.itemAt(n).widget() for n in range(tail_box.count())] if badges else []
            row.setToolTip(ai_text.TERMS)
            row.clicked.connect(lambda key=unit["key"]: self.open_unit(key))
            self.unit_list.add(row)
        read = sum(1 for unit in data["units"] if unit["read"])
        total = len(data["units"])
        self.unit_count.setText("%d개 중 %d개 읽음" % (total, read))
        self.unit_bar.setValue(round(100 * read / total) if total else 0)
        kit.set_tone(self.unit_bar, "success" if total and read >= total else "")

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
