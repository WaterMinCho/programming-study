# -*- coding: utf-8 -*-
"""꼬리 질문 사슬 화면. 위 막대(← 웹 면접 준비 · 사슬 제목 · 복습 차수와 질문 번호), 가운데 720 단의 카드 하나, 아래 막대의 주 단추.

질문 상태: 면접관 질문(title 크기), 답 시간 막대, 면접관이 보여 주는 코드(사슬 소개는 [배경 보기]로 접음), 말한 내용 칸.
확인 상태: 내 답 칸, 지난 답, 짚을 내용 표시 목록([필수]·[보충]), [필수]를 빠뜨리면 「막히면」 띠와 "아는 데까지 말했습니다" 표시.
사슬 끝: 통과한 질문 수, 다음 복습 날짜, 질문별 판정, 약한 답, 이어서 답한 예, 학습 노트로 가는 줄.
답 시간은 질문을 보인 때부터 [답 확인]이나 [모르겠습니다]를 누른 때까지이고 clock(기본 time.monotonic)으로 잼. 시간이 끝나도 막지 않고
넘긴 초만 빨갛게 보임. 기록은 질문마다 서비스의 answer 로, 사슬 끝에 finish_chain 으로 남김."""
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QPlainTextEdit, QStackedWidget, QWidget

import mdlite
from gui import kit, theme
from gui.docview import TextPiece
from gui.web_text import clock_text, date_text, ordinal, result_label, result_tone
from webprep.record import NOTE_LIMIT
from webprep.service import WebError

TALKED_TEXT = "막힌 곳에서 아는 데까지 말했습니다"
ITEMS_HINT = "말한 항목에 표시하세요."
GAVE_UP_HINT = "모르겠다고 답했습니다. 짚을 내용을 읽고 [다음 질문]을 누르세요."
STUCK_DEFAULT = "막힌 곳에서 아는 데까지 말했는지 표시하세요."
NOTE_HELP = "다음 복습 때 지난 답으로 보입니다. 풀이를 제출하면 저장소에도 올라갑니다."
WARN_SHARE = 0.2  # 남은 시간이 이 비율 이하면 주황
SHORTCUT_TIP = "Ctrl+Enter (맥은 Cmd+Enter)"


def plain(text):
    """표시 항목과 질문처럼 QLabel 에 넣는 글. 인라인 마크다운(`코드`, **굵게**)을 꾸밈 없는 글자로 바꿈."""
    return mdlite.inline_plain(text)


def background_text(chain):
    """[배경 보기]로 펼치는 사슬 소개: 목표와 소개 문단."""
    parts = [plain(part) for part in (chain["goal"], chain["intro"]) if part]
    return "\n\n".join(parts)


def code_html(markdown):
    """면접관이 보여 주는 코드(펜스 블록이 든 마크다운)를 코드 상자 HTML 로. 코드 블록이 없으면 빈 글."""
    blocks = [block for block in mdlite.parse(markdown or "") if block["t"] == "code"]
    return mdlite.blocks_html(blocks) if blocks else ""


def review_text(chain, index, total):
    """위 막대 오른쪽 글: 복습 차수(한 번 푼 사슬만)와 질문 번호."""
    where = "질문 %d/%d" % (index + 1, total)
    if chain["box"]:
        return "%s 복습 · %s" % (ordinal(chain["times"] + 1), where)
    return where


def mine_text(secs, limit):
    """내 답 칸의 머리글. 걸린 시간과 넘긴 시간."""
    head = "내 답 · %s" % ("%d초" % secs if secs < 60 else clock_text(secs))
    if secs > limit:
        head += " · %s 넘김" % clock_text(secs - limit)
    return head


def last_note(last):
    """지난 답 한 줄. 적은 내용이 없으면 그 사실과 날짜."""
    if not last:
        return ""
    when = date_text(last.get("at") or "") if last.get("at") else ""
    secs = last.get("secs")
    head = "지난 답" + (" · " + when if when else "") + (" · %d초" % secs if secs is not None else "")
    return "%s: %s" % (head, last.get("note") or "적은 내용 없음")


class WebDrillPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.setProperty("clipboard", True)  # 적는 칸은 자기 말을 적는 곳이라 붙여넣기를 막지 않음
        self.win = win
        self.cid, self.chain, self.back = None, None, None
        self.index, self.started, self.checked, self.gave_up = 0, 0.0, False, False
        self.verdicts, self.secs, self.done = [], 0, None  # 이번 회차의 질문별 판정, 지금 질문의 답 시간, 사슬 끝 결과
        self.talked_any = False  # 이번 회차에 "아는 데까지 말했습니다"를 표시한 적이 있는지
        self.clock = time.monotonic
        self.busy = False
        self.code_views = []

        root = kit.box(self)
        self.top = kit.TopBar("← 웹 면접 준비", "")
        self.back_btn, self.title = self.top.back, self.top.title
        self.timer_label = self.top.add_right(kit.label("", "caption", "secondary"))
        self.end_badge = self.top.add_right(kit.badge("끝남", "success"))
        self.end_badge.hide()
        root.addWidget(self.top)

        self.stack = QStackedWidget()
        self.ask_page, self.ask_card, ask_box = self._page(24)
        # 질문
        self.ask_head = kit.spaced(kit.label("면접관 질문", "caption", "tertiary"))
        self.ask = kit.para("", "title")
        self.ask_head.layout().addWidget(self.ask)
        ask_box.addWidget(self.ask_head)
        # 답 시간
        self.time_box = QWidget()
        time_col = kit.box(self.time_box, spacing=8)
        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(12)
        self.limit_label = kit.label("", "caption", "secondary")
        self.left_label = kit.label("", "caption", "secondary")
        time_row.addWidget(self.limit_label)
        time_row.addStretch(1)
        time_row.addWidget(self.left_label)
        self.time_bar = kit.progress(thin=True)
        time_col.addLayout(time_row)
        time_col.addWidget(self.time_bar)
        ask_box.addWidget(self.time_box)
        # 면접관이 보여 주는 코드와 배경
        self.code_box = QWidget()
        code_col = kit.box(self.code_box, spacing=8)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(12)
        self.code_label = kit.label("면접관이 보여 주는 코드", "caption", "tertiary")
        self.bg_btn = kit.button("배경 보기", "text", "s")
        head.addWidget(self.code_label)
        head.addStretch(1)
        head.addWidget(self.bg_btn)
        code_col.addLayout(head)
        self.intro = kit.para("", "body", "secondary")
        self.intro.hide()
        code_col.addWidget(self.intro)
        self.code_holder = QWidget()
        self.code_col = kit.box(self.code_holder, spacing=8)
        code_col.addWidget(self.code_holder)
        ask_box.addWidget(self.code_box)
        # 말한 내용
        self.field_box = QWidget()
        field_col = kit.box(self.field_box, spacing=8)
        field_col.addWidget(kit.label("말한 내용 (선택)", "label", bold=True))
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("예: 응답 순서")
        self.note.setMinimumHeight(144)
        self.note.setMaximumHeight(144)
        field_col.addWidget(self.note)
        field_col.addWidget(kit.label(NOTE_HELP, "caption", "secondary"))
        ask_box.addWidget(self.field_box)
        # 답 확인 뒤
        self.answer_box = QWidget()
        answer_col = kit.box(self.answer_box, spacing=24)
        mine_block = QWidget()
        mine_col = kit.box(mine_block, spacing=12)
        self.mine, mine_box = kit.well()
        self.mine_head = kit.label("", "caption", "secondary", bold=True)
        self.mine_note = kit.para("")
        mine_box.addWidget(self.mine_head)
        mine_box.addWidget(self.mine_note)
        self.last = kit.para("", "caption", "secondary")
        mine_col.addWidget(self.mine)
        mine_col.addWidget(self.last)
        answer_col.addWidget(mine_block)
        items_block = QWidget()
        items_col = kit.box(items_block, spacing=8)
        self.items_title = kit.para(ITEMS_HINT)
        items_col.addWidget(kit.spaced(kit.label("짚을 내용", "caption", "tertiary"), self.items_title))
        self.items = kit.CheckList()
        items_col.addWidget(self.items)
        answer_col.addWidget(items_block)
        self.stuck_box = QWidget()
        stuck_col = kit.box(self.stuck_box, spacing=8)
        self.stuck = kit.banner("", lead="막히면")
        self.talked = kit.CheckList()
        stuck_col.addWidget(self.stuck)
        stuck_col.addWidget(self.talked)
        answer_col.addWidget(self.stuck_box)
        self.answer_box.hide()
        ask_box.addWidget(self.answer_box)

        self.end_page, self.end_card, end_box = self._page(32)
        score_block = QWidget()
        score_col = kit.box(score_block, spacing=8)
        score_row = QHBoxLayout()
        score_row.setContentsMargins(0, 0, 0, 0)
        score_row.setSpacing(12)
        self.score = kit.label("", "display")
        score_row.addWidget(self.score)
        score_row.addWidget(kit.label("통과한 질문", "caption", "secondary"), 0, Qt.AlignmentFlag.AlignBottom)
        score_row.addStretch(1)
        score_col.addLayout(score_row)
        self.due_text = kit.para("")
        self.talked_text = kit.para("", "caption", "secondary")
        score_col.addWidget(self.due_text)
        score_col.addWidget(self.talked_text)
        end_box.addWidget(score_block)
        self.results = QWidget()
        self.results_col = kit.box(self.results)
        self.result_rows = []
        end_box.addWidget(self.results)
        self.weak_block = QWidget()
        weak_col = kit.box(self.weak_block, spacing=12)
        weak_col.addWidget(kit.label("약한 답", "headline"))
        self.weak_well, weak_box = kit.well()
        self.weak_quote = kit.para("")
        weak_box.addWidget(self.weak_quote)
        self.weak_why = kit.para("", "body", "secondary")
        weak_col.addWidget(self.weak_well)
        weak_col.addWidget(self.weak_why)
        end_box.addWidget(self.weak_block)
        self.follow_block = QWidget()
        follow_col = kit.box(self.follow_block, spacing=12)
        follow_col.addWidget(kit.label("이어서 답한 예", "headline"))
        self.follow_well, follow_box = kit.well()
        self.follow = kit.para("")
        follow_box.addWidget(self.follow)
        follow_col.addWidget(self.follow_well)
        end_box.addWidget(self.follow_block)
        self.learn_list = kit.RowList(inside_card=True)
        self.learn_row = None
        end_box.addWidget(self.learn_list)
        self.stack.addWidget(self.ask_page)
        self.stack.addWidget(self.end_page)
        root.addWidget(self.stack, 1)

        self.bar = kit.BottomBar()
        self.give_up_btn = self.bar.add_action(kit.button("모르겠습니다", "secondary", "l"))
        self.again_btn = self.bar.add_action(kit.button("한 번 더 풀기", "secondary", "l"))
        self.confirm_btn = self.bar.add_action(kit.button("답 확인", "primary", "l"))
        self.next_btn = self.bar.add_action(kit.button("다음 질문", "primary", "l"))
        self.done_btn = self.bar.add_action(kit.button("다음 할 일 보기", "primary", "l"))
        for button in (self.confirm_btn, self.next_btn, self.done_btn):
            button.setToolTip(SHORTCUT_TIP)
        root.addWidget(self.bar)
        self.shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.shortcut.activated.connect(self.press_primary)

        self.ticker = QTimer(self)
        self.ticker.setInterval(1000)
        self.ticker.timeout.connect(self.tick)
        self.back_btn.clicked.connect(self.go_back)
        self.done_btn.clicked.connect(self.go_back)
        self.confirm_btn.clicked.connect(lambda: self.reveal(False))
        self.give_up_btn.clicked.connect(lambda: self.reveal(True))
        self.next_btn.clicked.connect(self.answer)
        self.again_btn.clicked.connect(lambda: self.load(self.cid, self.back))
        self.bg_btn.clicked.connect(self.toggle_background)
        self.note.textChanged.connect(self._clip_note)

    @staticmethod
    def _page(spacing):
        """720 단의 카드 하나가 든 스크롤 칸. (칸, 카드, 카드 안 세로 상자)."""
        card, box = kit.card(24, spacing)
        inner = QWidget()
        outer = kit.box(inner, (kit.MARGIN, 24, kit.MARGIN, 32))
        outer.addWidget(kit.column(card, 720))
        outer.addStretch(1)
        return kit.scroll(inner), card, box

    # 불러오기

    def load(self, cid, back=None):
        """사슬을 화면에 올리고 첫 질문부터 시작함. back 은 돌아갈 곳(("mission", 미션 id) 또는 None 이면 웹 홈). 잠긴 사슬이면 WebError."""
        chain = self.win.web.chain(cid)
        self.cid, self.chain, self.back = cid, chain, back
        self.index, self.verdicts, self.done, self.talked_any = 0, [], None, False
        self.title.setText(chain["title"])
        self.title.show()
        self.back_btn.setText("← 미션" if back and back[0] == "mission" else "← 웹 면접 준비")
        self.intro.setText(background_text(chain))
        self.intro.hide()
        self.bg_btn.setText("배경 보기")
        self.bg_btn.setVisible(bool(self.intro.text()))
        for view in self.code_views:
            self.code_col.removeWidget(view)
            view.hide()
            view.deleteLater()
        self.code_views = []
        markup = code_html(chain["code"])
        if markup:
            view = TextPiece(markup, theme.web_css(self.win.zoom))
            self.code_col.addWidget(view)
            self.code_views.append(view)
        self.code_label.setText("면접관이 보여 주는 코드" if self.code_views else "배경")
        self.code_box.setVisible(bool(self.code_views) or bool(self.intro.text()))
        self.end_badge.hide()
        self.stack.setCurrentWidget(self.ask_page)
        self.show_question()

    def question(self):
        return self.chain["questions"][self.index]

    def show_question(self):
        question = self.question()
        total = len(self.chain["questions"])
        self.timer_label.setText(review_text(self.chain, self.index, total))
        self.ask.setText(plain(question["ask"]))
        self.note.setPlainText("")
        self.started, self.checked, self.gave_up = self.clock(), False, False
        self.limit_label.setText("답 시간 %s" % ("%d분" % (self.chain["secs"] // 60) if self.chain["secs"] % 60 == 0 else clock_text(self.chain["secs"])))
        self.time_box.show()
        self.field_box.show()
        self.answer_box.hide()
        self.note.setEnabled(True)
        self.confirm_btn.setVisible(True)
        self.give_up_btn.setVisible(True)
        self.next_btn.setVisible(False)
        self.again_btn.setVisible(False)
        self.done_btn.setVisible(False)
        self.confirm_btn.setEnabled(not self.busy)
        self.give_up_btn.setEnabled(not self.busy)
        self.tick()
        self.ask_page.verticalScrollBar().setValue(0)

    def toggle_background(self):
        opened = not self.intro.isVisible()
        self.intro.setVisible(opened)
        self.bg_btn.setText("배경 접기" if opened else "배경 보기")

    # 시계

    def tick(self):
        if self.chain is None or self.checked:
            return
        limit = self.chain["secs"]
        gone = int(self.clock() - self.started)
        left = limit - gone
        if left >= 0:
            self.left_label.setText("%s 남음" % clock_text(left))
            self.time_bar.setValue(min(100, round(100 * gone / max(1, limit))))
            tone = "warning" if left <= limit * WARN_SHARE else ""
        else:
            self.left_label.setText("+%s 시간 지남" % clock_text(-left))
            self.time_bar.setValue(100)
            tone = "danger"
        if self.left_label.property("tone") != (tone or None):
            kit.set_tone(self.left_label, tone)
            kit.set_tone(self.time_bar, tone)

    def showEvent(self, event):
        super().showEvent(event)
        self.ticker.start()
        self.tick()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.ticker.stop()

    # 답 확인

    def press_primary(self):
        """Ctrl+Enter. 지금 보이는 주 단추를 누름."""
        for button in (self.confirm_btn, self.next_btn, self.done_btn):
            if button.isVisible() and button.isEnabled():
                button.click()
                return

    def reveal(self, gave_up):
        """[답 확인]이나 [모르겠습니다]. 답 시간을 멈추고 짚을 내용을 엶."""
        question = self.question()
        self.secs = int(self.clock() - self.started)
        self.checked, self.gave_up = True, gave_up
        self.time_box.hide()
        self.field_box.hide()
        self.confirm_btn.hide()
        self.give_up_btn.hide()
        self.mine_head.setText(mine_text(self.secs, self.chain["secs"]))
        self.mine_note.setText(self.note.toPlainText().strip() or "적은 내용 없음")
        last = question["last"]
        self.last.setText(last_note(last))
        self.last.setVisible(bool(last))
        need_marks = list(last["need"]) if last else []
        extra_marks = list(last["extra"]) if last else []
        rows, need_no, extra_no = [], 0, 0
        for item in question["items"]:
            if item["need"]:
                mark, need_no = (need_marks[need_no] if need_no < len(need_marks) else None), need_no + 1
            else:
                mark, extra_no = (extra_marks[extra_no] if extra_no < len(extra_marks) else None), extra_no + 1
            note = "" if mark is None else ("지난번 표시함" if mark else "지난번 빠뜨림")
            rows.append((plain(item["text"]), "필수" if item["need"] else "보충", "accent" if item["need"] else "", note, False))
        self.items.set_items(rows)
        self.items.set_enabled(not gave_up and not self.busy)
        for row in self.items.rows:
            row.box.toggled.connect(lambda checked=False: self.sync_stuck())
        self.items_title.setText(GAVE_UP_HINT if gave_up else ITEMS_HINT)
        self.talked.set_items([(TALKED_TEXT, "", "", "", False)])
        self.talked.rows[0].box.toggled.connect(lambda checked: self._talked(checked))
        self.answer_box.show()
        self.next_btn.setText("사슬 끝내기" if self.index == len(self.chain["questions"]) - 1 else "다음 질문")
        self.next_btn.setVisible(True)
        self.next_btn.setEnabled(not self.busy)
        self.sync_stuck()

    def _talked(self, checked):
        if checked:
            self.talked_any = True

    def need_marks(self):
        question = self.question()
        marks = self.items.marks()
        need = [m for m, item in zip(marks, question["items"]) if item["need"]]
        extra = [m for m, item in zip(marks, question["items"]) if not item["need"]]
        return need, extra

    def sync_stuck(self):
        """[필수]를 빠뜨렸으면 「막히면」 띠와 "아는 데까지 말했습니다" 표시를 보임."""
        need, _ = self.need_marks()
        missing = not all(need)
        question = self.question()
        self.stuck.text.setText(plain(question["stuck"]) if question["stuck"] else STUCK_DEFAULT)
        self.stuck_box.setVisible(missing)

    def answer(self):
        """[다음 질문]. 표시를 기록하고 다음 질문이나 사슬 끝으로 감."""
        need, extra = self.need_marks()
        talked = (1 if self.talked.marks()[0] else 0) if not all(need) else None
        try:
            result = self.win.web.answer(self.cid, self.question()["no"], self.secs, need, extra, talked, self.note.toPlainText())
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.verdicts.append(result["result"])
        if self.index + 1 < len(self.chain["questions"]):
            self.index += 1
            self.show_question()
            return
        self.finish()

    def finish(self):
        try:
            done = self.win.web.finish_chain(self.cid)
        except WebError as error:
            self.win.ask("알림", str(error))
            return
        self.done = done
        total = len(self.chain["questions"])
        self.timer_label.setText("")
        self.end_badge.show()
        passed = sum(1 for r in done["per_question"] if r == "pass")
        self.score.setText("%d/%d" % (passed, total))
        self.due_text.setText("다음 복습은 %s입니다." % date_text(done["due"]))
        stuck = sum(1 for r in done["per_question"] if r != "pass")
        self.talked_text.setText("막힌 질문 %d개에서 아는 데까지 말했습니다." % stuck if self.talked_any and stuck else "")
        self.talked_text.setVisible(bool(self.talked_text.text()))
        for row in self.result_rows:
            self.results_col.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.result_rows = []
        for question, result in zip(self.chain["questions"], done["per_question"]):
            row = QWidget()
            line = kit.box(row, (0, 12, 0, 12), 12, horizontal=True)
            line.addWidget(kit.badge(result_label(result), result_tone(result)), 0, Qt.AlignmentFlag.AlignTop)
            line.addWidget(kit.para(plain(question["ask"])), 1)
            self.results_col.addWidget(row)
            self.result_rows.append(row)
        weak = done["weak"]
        self.weak_block.setVisible(bool(weak))
        if weak:
            self.weak_quote.setText(plain(weak["quote"]))
            self.weak_why.setText(plain(weak["why"]))
            self.weak_why.setVisible(bool(weak["why"]))
        self.follow_block.setVisible(bool(done["follow"]))
        self.follow.setText(plain(done["follow"]))
        self.learn_list.clear()
        self.learn_row = None
        if done["page"]:
            pages = getattr(self.win.web, "pages", {})
            title = pages.get(done["page"], {}).get("title") or "학습 노트"
            self.learn_row = self.learn_list.add(kit.Row(title, "이 사슬의 원리가 나오는 학습 노트", data=done["page"]))
            self.learn_row.clicked.connect(self.open_learn)
        self.learn_list.setVisible(self.learn_row is not None)
        self.done_btn.setText("미션으로" if self.back and self.back[0] == "mission" else "다음 할 일 보기")
        for button in (self.confirm_btn, self.give_up_btn, self.next_btn):
            button.hide()
        self.again_btn.show()
        self.done_btn.show()
        self.again_btn.setEnabled(not self.busy)
        self.done_btn.setEnabled(not self.busy)
        self.stack.setCurrentWidget(self.end_page)
        self.end_page.verticalScrollBar().setValue(0)

    def open_learn(self):
        done = self.done
        self.win.open_learn(done["page"], done["section"], back=("drill", self.cid, self.back))

    def go_back(self):
        if self.back and self.back[0] == "mission":
            self.win.open_mission(self.back[1])
        else:
            self.win.go_web()

    def _clip_note(self):
        text = self.note.toPlainText()
        if len(text) > NOTE_LIMIT:
            cursor = self.note.textCursor()
            self.note.setPlainText(text[:NOTE_LIMIT])
            cursor.setPosition(NOTE_LIMIT)
            self.note.setTextCursor(cursor)

    # 상태

    def set_busy(self, busy, text=""):
        self.busy = busy
        for widget in (self.back_btn, self.done_btn, self.again_btn, self.next_btn):
            widget.setEnabled(not busy)
        self.confirm_btn.setEnabled(not busy and not self.checked)
        self.give_up_btn.setEnabled(not busy and not self.checked)
        self.items.set_enabled(not busy and not self.gave_up)
        self.talked.set_enabled(not busy)

    def restyle(self):
        for view in self.code_views:
            view.restyle(theme.web_css(self.win.zoom))
        if self.chain is not None:
            self.tick()
