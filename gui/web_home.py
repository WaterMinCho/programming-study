# -*- coding: utf-8 -*-
"""웹 면접 준비 홈: 위 막대(← 처음 화면 · 검사 도구 상태 · 설치 관리) · 제목 · 이어서 할 일 카드 · 오늘 복습 · 라이브 코딩 미션 · 꼬리 질문 ·
학습 노트 구역. 구역은 아래로 이어지고 준비 중인 항목은 구역 끝의 글자 단추 하나로 접음.

수치는 모두 webprep.service.WebSession.overview() 가 계산한 값이고, 이 화면은 그것을 줄(gui.kit.Row)로 보여 주기만 함. 줄을 한 번 누르면
바로 열리고 미리 고른 줄은 없음. 화면 낱말은 gui/web_text.py 가 만듦."""
from PyQt6.QtWidgets import QButtonGroup, QWidget

from gui import kit
from gui.web_setup import SetupDialog
from gui.web_text import chain_line, date_text, gui_text, mission_line, next_item, ordinal, stack_status
from webprep.record import RecordError
from webprep.service import WebError

ABOUT = "프런트엔드 채용의 라이브 코딩 미션과 직무 면접 꼬리 질문을 연습합니다."
REVIEW_ABOUT = "한 번 푼 꼬리 질문을 정해진 날에 다시 풀고, 아직 풀지 않은 사슬을 하루 몇 개씩 더합니다."
NO_TODAY = "오늘 복습할 사슬이 없습니다."
NO_STUCK = "'막혀도 끝까지 말함'은 꼬리 질문에서 필수 항목을 빠뜨린 뒤부터 셉니다."
ALL_DONE = "지금 있는 미션과 사슬을 모두 끝냈습니다."
NOTHING_YET = "아직 준비된 미션이 없습니다."
BROKEN = "읽지 못한 항목이 있습니다: %s. [새 문제 받기]로 최신 판을 받은 뒤 다시 열어 보세요."


def next_due_text(topics):
    """가장 가까운 다음 복습 날짜 문장. 복습 예정인 사슬이 없으면 빈 글."""
    dues = sorted(c["due"] for t in topics for c in t["chains"] if c.get("due"))
    return "다음 복습은 %s입니다." % date_text(dues[0]) if dues else ""


class WebHomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.overview = None
        self.topic, self.chips, self.busy = None, {}, False
        self.setup_dialog = None
        self.target = None  # 이어서 할 일 카드가 여는 것(web_text.next_item)
        outer = kit.box(self)

        self.top = kit.TopBar("← 처음 화면", plain=True)
        self.hub_btn = self.top.back
        self.stack_dot = kit.Dot("todo", 8)
        self.stack_label = kit.label("", "caption", "secondary")
        self.top.row.addStretch(1)  # 제목이 없는 막대라 돌아가기는 왼쪽 끝, 상태와 설치 관리는 오른쪽 끝에 붙임
        self.top.add_right(self.stack_dot)
        self.top.add_right(self.stack_label)
        self.setup_btn = kit.button("설치 관리", "text", "s", onbg=True)
        self.setup_btn.setToolTip("라이브 코딩 미션의 검사 도구를 설치하거나 지웁니다. 꼬리 질문과 학습 노트에는 필요 없습니다.")
        self.top.add_right(self.setup_btn, flush=True)
        outer.addWidget(self.top)

        inner = QWidget()
        root = kit.box(inner, (0, 24, 0, 48))
        root.addWidget(kit.label("웹 면접 준비", "title"))
        root.addSpacing(4)
        root.addWidget(kit.para(ABOUT, "body", "secondary"))
        root.addSpacing(16)
        self.notice = kit.banner("", "danger")  # 기록을 읽지 못한 까닭(오류), 읽지 못한 미션·주제·노트(주의)
        self.notice.hide()
        self.problem = kit.banner("", "warning")  # 검사 도구나 Node 가 없을 때의 안내
        self.problem.hide()
        banners = QWidget()  # 띠 둘이 같이 보이면 8 띄움. 숨은 띠 옆에는 간격이 생기지 않음
        banner_box = kit.box(banners, spacing=8)
        banner_box.addWidget(self.notice)
        banner_box.addWidget(self.problem)
        root.addWidget(banners)
        root.addSpacing(16)
        self.next_card = kit.NextCard()
        self.next_btn = self.next_card.button
        self.next_note = kit.para("", "body", "secondary")  # 할 일이 없을 때 카드 대신 보이는 한 줄
        self.next_note.hide()
        root.addWidget(self.next_card)
        root.addWidget(self.next_note)

        root.addSpacing(48)
        row, _, self.today_minutes = kit.section("오늘 복습")
        root.addLayout(row)
        root.addSpacing(4)
        root.addWidget(kit.label(REVIEW_ABOUT, "caption", "secondary"))
        root.addSpacing(12)
        self.today_list = kit.RowList()
        self.today_empty = kit.para(NO_TODAY, "body", "secondary")
        root.addWidget(self.today_list)
        root.addWidget(self.today_empty)

        root.addSpacing(48)
        row, _, self.mission_count = kit.section("라이브 코딩 미션")
        root.addLayout(row)
        root.addSpacing(12)
        self.mission_list = kit.RowList()
        root.addWidget(self.mission_list)

        root.addSpacing(48)
        row, _, self.topic_count = kit.section("꼬리 질문")
        root.addLayout(row)
        root.addSpacing(12)
        self.topic_card, card_box = kit.card(pad=0, spacing=0)
        card_box.setContentsMargins(0, 24, 0, 0)
        chips_holder = QWidget()
        self.chip_row = kit.FlowLayout(chips_holder, 8)  # 칩이 넘치면 다음 줄로 넘김
        self.chip_row.setContentsMargins(24, 0, 24, 16)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self.more_topics_btn = kit.button("", "text", "s")
        self.more_topics_btn.hide()
        self.more_topics = QWidget()
        self.more_topics_box = kit.box(self.more_topics, (24, 0, 24, 16), 4)
        self.more_topics.hide()
        self.chain_line = kit.frame("rowline")
        self.chain_line.setFixedHeight(1)
        self.chain_list = kit.RowList(inside_card=True)
        self.chain_empty = kit.para("", "body", "secondary")
        chain_empty_holder = QWidget()
        kit.box(chain_empty_holder, (24, 16, 24, 24)).addWidget(self.chain_empty)
        self.chain_empty_holder = chain_empty_holder
        card_box.addWidget(chips_holder)
        card_box.addWidget(self.more_topics)
        card_box.addWidget(self.chain_line)
        card_box.addWidget(self.chain_list)
        card_box.addWidget(chain_empty_holder)
        root.addWidget(self.topic_card)
        root.addSpacing(12)
        self.talked = kit.label("", "caption", "secondary")
        root.addWidget(self.talked)

        root.addSpacing(48)
        row, _, self.page_count = kit.section("학습 노트")
        root.addLayout(row)
        root.addSpacing(12)
        self.page_list = kit.RowList()
        root.addWidget(self.page_list)

        root.addSpacing(24)
        self.status = kit.label("", "caption", "secondary")
        self.status.setMinimumWidth(1)
        self.busy_bar = kit.progress()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.hide()
        root.addWidget(self.status)
        root.addSpacing(8)
        root.addWidget(self.busy_bar)
        root.addStretch(1)
        column = kit.column(inner)
        column.setContentsMargins(kit.MARGIN, 0, kit.MARGIN, 0)
        self.scroll = kit.scroll(column)
        outer.addWidget(self.scroll, 1)

        self.hub_btn.clicked.connect(lambda: self.win.go_hub())
        self.setup_btn.clicked.connect(self.open_setup)
        self.next_btn.clicked.connect(self.open_next)
        self.more_topics_btn.clicked.connect(self.toggle_topics)
        self.chip_group.idClicked.connect(self._chip_picked)

    # 불러오기

    def refresh(self):
        """서비스에서 현황을 다시 읽어 모든 칸을 다시 채움. 기록을 읽지 못하면 알림 띠에 이유를 보이고 목록을 비움."""
        try:
            overview = self.overview = self.win.web.overview()
        except (WebError, RecordError) as error:
            self.overview = None
            self.say(str(error), "danger")
            self.notice.setToolTip("")
            self.notice.show()
            self.clear()
            return
        stack = overview["stack"]
        state, text = stack_status(stack)
        self.stack_dot.set_state(state)
        self.stack_label.setText(text)
        self.problem.text.setText(gui_text(stack["problem"]))
        self.problem.setVisible(bool(stack["problem"]))
        broken = [row["title"] for kind in ("missions", "topics", "pages") for row in overview[kind] if row.get("error")]
        self.say(BROKEN % ", ".join(broken) if broken else "", "warning")
        self.notice.setToolTip("\n".join(overview["bank_errors"]))  # 파일 이름과 까닭은 도움말에만
        self.notice.setVisible(bool(broken))
        self.show_next(overview)
        self.show_today(overview["today"])
        self.show_missions(overview["missions"])
        self.show_topics(overview["topics"])
        self.show_pages(overview["pages"])
        self.talked.setText("막혀도 끝까지 말함 %d/%d" % (overview["talked"], overview["stuck"]) if overview["stuck"] else NO_STUCK)
        self.status.setText("")

    def clear(self):
        """현황을 읽지 못했을 때. 지난 현황이 알림과 섞여 보이지 않게 모든 칸을 비움."""
        self.problem.hide()
        self.stack_label.setText("")
        self.stack_dot.set_state("todo")
        for label in (self.today_minutes, self.mission_count, self.topic_count, self.page_count, self.talked, self.chain_empty):
            label.setText("")
        for listw in (self.today_list, self.mission_list, self.chain_list, self.page_list):
            listw.clear()
        self.today_empty.hide()
        self.chain_empty_holder.hide()
        self.clear_chips()
        self.topic, self.target = None, None
        self.next_card.hide()
        self.next_note.setText("")
        self.next_note.hide()

    def show_next(self, overview):
        """이어서 할 일 카드. 할 일이 없으면 카드 대신 한 줄."""
        self.target = next_item(overview, self.win.web.missions)
        if self.target:
            self.next_card.set_item(self.target["title"], self.target["line"], self.target["action"])
            self.next_card.show()
            self.next_note.hide()
            return
        self.next_card.hide()
        ready = overview.get("ready_missions") or any(t["ready"] for t in overview.get("topics", []))
        self.next_note.setText(ALL_DONE if ready else NOTHING_YET)
        self.next_note.show()

    def show_today(self, today):
        self.today_minutes.setText("약 %d분" % today["minutes"] if today["chains"] or today["missions"] else "")
        self.today_list.clear()
        chains = {c["id"]: (t["title"], c["times"]) for t in (self.overview or {}).get("topics", []) for c in t["chains"]}
        for row in today["chains"]:
            topic, times = chains.get(row["chain"], ("", 0))
            if row["new"]:
                second = "시작 전" + (" · %s" % topic if topic else "")
            else:
                second = " · ".join(part for part in (topic, "%s 복습" % ordinal(times + 1)) if part)
            self.today_list.add(self._row(row["title"], second, kit.Dot("todo" if row["new"] else "review"), ("chain", row["chain"])))
        for row in today["missions"]:
            self.today_list.add(self._row(row["title"], "다시 해 볼 미션 · %s" % row["why"], kit.Dot("review"), ("mission", row["mission"])))
        empty = not self.today_list.rows
        self.today_list.setVisible(not empty)
        self.today_empty.setText(" ".join(part for part in (NO_TODAY, next_due_text((self.overview or {}).get("topics", []))) if part))
        self.today_empty.setVisible(empty)

    def say(self, text, tone):
        """알림 띠의 글과 색. tone 은 danger(기록을 읽지 못함)나 warning(읽지 못한 항목이 있음)."""
        kit.set_tone(self.notice, tone)
        self.notice.word.setText("오류" if tone == "danger" else "주의")
        self.notice.text.setText(text)

    def show_missions(self, missions):
        self.mission_list.clear()
        waiting = []
        for row in missions:
            if not row["ready"]:
                if not row.get("error"):  # 읽지 못한 미션은 준비 중으로 세지 않고 위 알림 띠에만 이름이 나옴
                    waiting.append(row["title"])
                continue
            state = {"done": "done", "live": "progress", "reading": "progress"}.get(row["phase"], "todo")
            prep = self.win.web.missions[row["id"]]["prep_min"]
            self.mission_list.add(self._row(row["title"], mission_line(row, prep), kit.Dot(state), ("mission", row["id"]), end=row["level"]))
        self.mission_list.add_more(waiting)
        ready = [m for m in missions if m["ready"]]
        self.mission_count.setText("%d개 중 %d개 끝남" % (len(ready), sum(1 for m in ready if m["phase"] == "done")) if ready else "")
        self.mission_list.setVisible(bool(ready or waiting))

    def clear_chips(self):
        for chip in self.chips.values():
            self.chip_group.removeButton(chip)
            self.chip_row.removeWidget(chip)
            chip.hide()
            chip.deleteLater()
        self.chips = {}
        while self.chip_row.count():
            self.chip_row.takeAt(0)
        while self.more_topics_box.count():
            item = self.more_topics_box.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.more_topics_btn.hide()
        self.more_topics.hide()

    def show_topics(self, topics):
        self.clear_chips()
        ready = [t for t in topics if t["ready"]]
        waiting = [t["title"] for t in topics if not t["ready"]]
        for number, row in enumerate(ready):
            chip = kit.chip(row["title"], row["id"])
            chip.setToolTip("사슬 %d개 중 %d개 끝남" % (row["total"], row["done"]))
            self.chip_group.addButton(chip, number)
            self.chip_row.addWidget(chip)
            self.chips[row["id"]] = chip
        if waiting:
            self.more_topics_btn.setText("준비 중 %d개 보기" % len(waiting))
            self.chip_row.addWidget(self.more_topics_btn)
            self.more_topics_btn.show()  # 줄에 붙여 부모가 생긴 뒤에 보임. 먼저 보이면 잠깐 따로 창으로 뜸
            for name in waiting:
                self.more_topics_box.addWidget(kit.label(name, "caption", "tertiary"))
        self.topic_count.setText("사슬 %d개 중 %d개 끝남" % (sum(t["total"] for t in ready), sum(t["done"] for t in ready)) if ready else "")
        if self.topic not in self.chips:
            self.topic = next((t["id"] for t in ready), None)
        self.pick_topic(self.topic)

    def toggle_topics(self):
        opened = not self.more_topics.isVisible()
        self.more_topics.setVisible(opened)
        self.more_topics_btn.setText("접기" if opened else "준비 중 %d개 보기" % self.more_topics_box.count())

    def _chip_picked(self, number):
        chip = self.chip_group.button(number)
        if chip is not None:
            self.pick_topic(chip.tid)

    def pick_topic(self, tid):
        """주제 tid 의 사슬 목록을 보임."""
        self.topic = tid
        for key, chip in self.chips.items():
            chip.setChecked(key == tid)
        self.chain_list.clear()
        row = next((t for t in (self.overview or {}).get("topics", []) if t["id"] == tid), None)
        today_ids = {r["chain"] for r in (self.overview or {}).get("today", {}).get("chains", []) if not r["new"]}
        if row is not None:
            for chain in row["chains"]:
                state = "review" if chain["id"] in today_ids else ("done" if chain["box"] is not None else "todo")
                self.chain_list.add(self._row(chain["title"], chain_line(chain, today_ids), kit.Dot(state), ("chain", chain["id"])))
        has = bool(self.chain_list.rows)
        self.chain_line.setVisible(has or self.overview is not None)
        self.chain_list.setVisible(has)
        self.chain_empty.setText("" if has else ("이 주제에는 아직 사슬이 없습니다." if row is not None else "아직 준비된 주제가 없습니다."))
        self.chain_empty_holder.setVisible(not has and self.overview is not None)

    def show_pages(self, pages):
        self.page_list.clear()
        waiting = []
        for row in pages:
            if not row["ready"]:
                waiting.append(row["title"])
                continue
            self.page_list.add(self._row(row["title"], "", kit.Dot("done" if row["learned_at"] else "todo"), ("page", row["id"])))
        self.page_list.add_more(waiting)
        ready = [p for p in pages if p["ready"]]
        self.page_count.setText("%d개 중 %d개 끝남" % (len(ready), sum(1 for p in ready if p["learned_at"])) if ready else "")
        self.page_list.setVisible(bool(ready or waiting))

    def _row(self, title, second, mark, data, end=""):
        row = kit.Row(title, second, end, mark, data)
        row.clicked.connect(lambda: self.open(data))
        return row

    # 이동

    def open(self, data):
        """줄을 눌렀을 때. data 는 (종류, id)."""
        if self.busy:
            return
        kind, iid = data
        if kind == "mission":
            self.win.open_mission(iid)
        elif kind == "chain":
            self.win.open_drill(iid)
        elif kind == "page":
            self.win.open_learn(iid)

    def open_next(self):
        target = self.target
        if target is None or self.busy:
            return
        kind = "chain" if target["kind"] in ("chain", "topic") else target["kind"]
        self.open((kind, target["id"]))

    def open_setup(self):
        self.setup_dialog = SetupDialog(self.win, on_change=self.refresh)
        self.setup_dialog.show()

    # 상태

    def set_busy(self, busy, text=""):
        self.busy = busy
        for widget in (self.hub_btn, self.setup_btn, self.next_btn):
            widget.setEnabled(not busy)
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")

    def restyle(self):
        """테마가 바뀌면 점과 꺾쇠를 다시 칠함."""
        for widget in self.findChildren(kit.Dot) + self.findChildren(kit.Chevron):
            widget.update()
