# -*- coding: utf-8 -*-
"""AI 비전 개론 연습 화면(설계 2.6, 2.7). 위 막대(← AI 비전 개론 · 묶음 제목 · 7 / 20)와 얇은 진행 막대, 가운데 카드 하나, 아래 막대.

카드: 머리 꼬리표(차시, 꼴, 숫자 바뀜, 다시 나온 문항 …), 답한 뒤의 판정 줄, 지문, 빈칸이나 보기, 해설·근거·정정. 코드 울타리 안의 빈칸은
CodeSlots 가 코드 줄 사이에 입력 칸을 두어 그리고, 울타리 밖 빈칸은 지문 아래에 칸을 둠(빈칸이 둘 이상이면 지문과 칸에 ①② 번호).
차시 꼬리표는 묶음 제목이 같은 차시를 말하면(단원·차시 묶음의 그 차시 문항) 뺌. 묶음 첫 문항에는 [확실함]·[긴가민가]가 답을 내는 단추라는
안내를 한 번 둠. 답 단추는 [모르겠어요]·[긴가민가]·[확실함]이고 Ctrl+Enter 는 [확실함](답한 뒤에는 [다음]), Ctrl+Shift+Enter 는 [긴가민가].
답을 읽기 전에 조합 중인 한글을 확정함(commit_input). 단축키는 초점을 옮기지 않아 마지막 글자가 빠질 수 있어서임.
답한 뒤: 판정 줄 아래에 정답 목록, 칸 테두리 색, 빈칸이 둘 이상이면 칸마다 "맞음"·"틀림" 글(코드 칸은 코드 아래 한 줄)을 보이고, 보기는
꼬리표와 바른 문장을 보임. 문항이 묶음 뒤에 다시 들어가면 몇 문항 뒤에 나오는지 씀. [노트 보기]는 근거 단계를 창 모달 대화상자로 엶.
뼈대 카드: 빈칸은 판 전체 코드의 CodeSlots 이고, 함께 가린 칸이 틀리면 정답 줄 아래에 그 칸 번호를 한 줄 더 씀([내 답도 맞음]도 보임).
고르기는 보기가 코드라 CodeChoices(순서 고르기는 2×2)로 그리고 판정 아래 정답 줄 없이 보기 꼬리표만 씀.
묶음이 끝나면 같은 카드에 요약을 보임. 시험처럼 복사와 붙여넣기는 막힘: 키는 gui/guard.py, 가운데 단추와 끌어다 놓기는 칸마다 PasteBlock."""
import html
import time

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import QWidget

from aiprep import bank
from aiprep.grade import BLANK
from gui import ai_text, kit, theme
from gui.ai_learn import CARD_PAD, ChoiceList, CodeChoices, CodeSlots, NoteDialog, RichPara, Slot, doc, reading_column, reading_width, rich
from gui.guard import NOTE as PASTE_NOTE
from gui.widgets import AnswerLine, LinkLabel, PasteBlock
from learning_data.collection import AI_INPUT_SCHEMA
from session import SessionError


def commit_input():
    """조합 중인 한글을 확정함(gui/round_page.py 의 flush 와 같음). 테스트가 가짜로 바꿈."""
    QGuiApplication.inputMethod().commit()


def split_stem(stem):
    """지문을 [("text", 마크다운) | ("code", 코드 글)] 로 나눔. 빈칸이 든 코드 울타리만 따로 빼고 나머지는 글로 둠."""
    parts, text, code, fence = [], [], None, None
    for line in (stem or "").split("\n"):
        mark = bank.FENCE.match(line)
        if code is None:
            if mark and mark.group(2) is not None:
                code, fence = [], line
                continue
            text.append(line)
            continue
        if mark and not mark.group(2):
            if any(BLANK.search(row) for row in code):
                if "\n".join(text).strip():
                    parts.append(("text", "\n".join(text)))
                text = []
                parts.append(("code", "\n".join(code)))
            else:
                text += [fence] + code + [line]
            code = None
            continue
        code.append(line)
    if code is not None:
        text += [fence] + code
    if "\n".join(text).strip():
        parts.append(("text", "\n".join(text)))
    return parts


class Reveal(QObject):
    """칸에 초점이 오면 그 칸이 보이게 스크롤함(Tab 으로 옮길 때). scrolls 는 안쪽부터의 스크롤 칸."""

    def __init__(self, scrolls):
        super().__init__()
        self.scrolls = scrolls

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            for area in self.scrolls():
                area.ensureWidgetVisible(watched, 16, 16)
        return False


class PracticePage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.practice, self.item, self.feedback, self.dontknow = None, None, None, False
        self.input_context = None
        self.review_state = None
        self.args = None  # 묶음을 만든 (mode, lesson, unit, card). [한 번 더]가 다시 씀
        self.inputs, self.fields, self.results, self.docs, self.slots = [], [], [], [], []
        self.choices = None
        self.shown_at, self.clock = 0.0, time.monotonic
        self.busy = False
        self.reveal = Reveal(lambda: [slot.area for slot in self.slots] + [self.scroll])
        self.paste = PasteBlock(self)  # 가운데 단추 붙여넣기와 끌어다 놓기. 붙여넣기 키는 창의 Guard 가 먼저 막음
        self.paste.blocked.connect(self.note_blocked)
        self.note_dialog, self.queued = None, 0
        root = kit.box(self)
        self.top = kit.TopBar("← AI 비전 개론", "")
        self.back_btn, self.title = self.top.back, self.top.title
        self.count = self.top.add_right(kit.label("", "caption", "secondary"))
        root.addWidget(self.top)
        self.bar_line = kit.progress(thin=True)
        root.addWidget(self.bar_line)
        self.card, self.card_box = kit.card(CARD_PAD, 32)
        self.scroll, _ = reading_column(self.card)
        root.addWidget(self.scroll, 1)
        self.bar = kit.BottomBar()
        self.dont_btn = self.bar.add_tool(kit.button("모르겠어요", "text", "l"))
        self.note_btn = self.bar.add_tool(kit.button("노트 보기", "text", "l"))
        self.mine_btn = self.bar.add_tool(kit.button("내 답도 맞음", "text", "l"))
        self.home_btn = self.bar.add_action(kit.button("홈으로", "secondary", "l"))
        self.unsure_btn = self.bar.add_action(kit.button("긴가민가", "secondary", "l"))
        self.sure_btn = self.bar.add_action(kit.button("확실함", "primary", "l"))
        self.next_btn = self.bar.add_action(kit.button("다음", "primary", "l"))
        self.again_btn = self.bar.add_action(kit.button("한 번 더", "primary", "l"))
        self.dont_btn.setToolTip("정답과 해설을 표시하고 모르는 문항으로 기록해 복습에 반영합니다.")
        self.sure_btn.setToolTip("입력한 답을 채점하고 확신한 답으로 기록합니다.\n" + ai_text.SHORTCUTS)
        self.unsure_btn.setToolTip("입력한 답을 채점하고 확신하지 못한 답으로 기록합니다.\n" + ai_text.SHORTCUTS)
        self.note_btn.setToolTip("이 문항의 근거가 된 학습 단계를 엽니다.")
        self.mine_btn.setToolTip("내 답이 정답과 같은 뜻인데 틀림으로 나왔으면 누르세요. 맞은 답으로 바꾸고 출제자가 모아 봅니다.")
        root.addWidget(self.bar)
        self.shortcuts = []
        for keys, slot in (("Ctrl+Return", self.press_primary), ("Ctrl+Enter", self.press_primary),
                           ("Ctrl+Shift+Return", lambda: self.press_answer(False)), ("Ctrl+Shift+Enter", lambda: self.press_answer(False))):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(slot)
            self.shortcuts.append(shortcut)
        self.back_btn.clicked.connect(self.go_back)
        self.home_btn.clicked.connect(lambda: self.win.go_ai())
        self.dont_btn.clicked.connect(self.dont_know)
        self.sure_btn.clicked.connect(lambda: self.answer(True))
        self.unsure_btn.clicked.connect(lambda: self.answer(False))
        self.next_btn.clicked.connect(self.go_next)
        self.note_btn.clicked.connect(self.open_note)
        self.mine_btn.clicked.connect(self.override)
        self.again_btn.clicked.connect(self.again)
        self.set_buttons()  # 문항이 없으면 단추를 모두 숨김. 숨기지 않으면 막대의 최소 폭이 창의 최소 폭을 넓힘

    # 불러오기

    def load(self, mode, lesson=None, unit=None, card=None):
        """같은 미완료 묶음이 있으면 입력·판정을 복원함. 없으면 새 묶음이나 복습 완료 안내를 보임."""
        self.finish_input()
        practice = self.win.ai.resume_set(mode, lesson, unit, card)
        if practice is not None and practice is self.practice:
            self.win.ai.save_practice(practice, activate=True)
            return
        if practice is not None:
            self.practice, self.args = practice, (mode, lesson, unit, card)
            self.review_state = None
            self.title.setText(practice.title)
            self.title.show()
            self.back_btn.setText("← 오답 노트" if mode == "note" else "← " + bank.COURSES[self.win.ai.course])
            self.show_item(practice.current(measure_input=True))
            return
        status = self.win.ai.review_status() if mode in ("review", "sweep") else None
        practice = None if status is not None and not status["available"] else \
            self.win.ai.start_set(mode, lesson=lesson, unit=unit, card=card)
        self.practice, self.args = practice, (mode, lesson, unit, card)
        self.review_state = status
        self.title.setText(practice.title if practice else self.win.ai.title_of(mode))
        self.title.show()
        self.back_btn.setText("← 오답 노트" if mode == "note" else "← " + bank.COURSES[self.win.ai.course])
        if practice is None:
            self.show_review_complete()
        else:
            self.show_item(practice.current(measure_input=True))

    def clear(self):
        """문제 받기로 서비스가 바뀌면 부름. 옛 묶음과 옛 카드를 붙들지 않게 놓음."""
        self.finish_input()
        self.close_note()
        self.practice, self.item, self.feedback = None, None, None
        self.review_state = None
        self.empty_card()
        self.set_buttons()

    def empty_card(self):
        while self.card_box.count():
            item = self.card_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
            elif item.layout() is not None:
                self._drop(item.layout())
        self.inputs, self.fields, self.results, self.docs, self.slots, self.choices = [], [], [], [], [], None

    def _drop(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout() is not None:
                self._drop(item.layout())

    def chips(self, item):
        """머리 꼬리표. 첫 꼬리표는 늘 자리(차시 "5차시", 상황별 코드 "학습 루프")이고, 단원·차시 묶음에서 그 묶음의 문항이면 묶음
        제목이 자리를 말하므로 뺌. 차시 묶음에 섞인 상황별 코드 문항은 자리가 달라 남김."""
        chips = list(item["chips"])
        practice = self.practice
        if chips and practice is not None and practice.mode in ("unit", "lesson") and item.get("lesson") == practice.lesson:
            chips = chips[1:]
        return chips

    def show_item(self, item):
        """문항 하나를 그림(답하기 전 상태)."""
        self.close_note()
        self.empty_card()
        self.item, self.feedback, self.dontknow = item, None, False
        self.count.setText("%d / %d" % (item["at"], item["total"]))
        self.bar_line.setValue(round(100 * (item["at"] - 1) / max(1, item["total"])))
        chips = QWidget()
        chip_row = kit.FlowLayout(chips, 8)
        for text in self.chips(item):
            chip_row.addWidget(kit.badge(text, "accent" if text in ("다시 나온 문항", "지난번 확실했던 문항") else ""))
        self.card_box.addWidget(chips)
        self.verdict = QWidget()
        verdict_col = kit.box(self.verdict, spacing=theme.GAP["title_description"])
        self.verdict_text = kit.label("", "headline")
        self.answer_line = rich("")
        self.also_text = kit.para("", "body", "secondary")  # 뼈대 빈칸에서 함께 가린 칸이 틀렸을 때
        self.requeue = kit.para("", "body", "secondary")
        verdict_col.addWidget(self.verdict_text)
        verdict_col.addWidget(self.answer_line)
        verdict_col.addWidget(self.also_text)
        verdict_col.addWidget(self.requeue)
        self.also_text.hide()
        self.card_box.addWidget(self.verdict)
        self.verdict.hide()
        if item["kind"] == "blank":
            self.build_blanks(item)
        else:
            self.build_choice(item)
        self.status = kit.para("", "body", "secondary")
        self.card_box.addWidget(self.status)
        self.status.hide()
        self.guide = kit.para(ai_text.FIRST_HINT.get(item["kind"], ai_text.FIRST_HINT["blank"]) + ai_text.FIRST_HINT_TAIL, "body", "secondary")
        self.card_box.addWidget(self.guide)
        self.guide.setVisible(item["at"] == 1)  # 묶음 첫 문항에만
        self.after = QWidget()
        self.after_box = kit.box(self.after, spacing=16)
        self.card_box.addWidget(self.after)
        self.after.hide()
        for widget in self.inputs:
            widget.installEventFilter(self.reveal)
        chain = [self.back_btn] + self.inputs + [self.dont_btn, self.unsure_btn, self.sure_btn]
        for first, second in zip(chain, chain[1:]):
            QWidget.setTabOrder(first, second)
        self.set_buttons()
        self.scroll.verticalScrollBar().setValue(0)
        if item["kind"] == "blank" and self.inputs:
            self.inputs[0].setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.setFocus()  # 보기 줄에 초점을 두면 테두리가 고른 것처럼 보임
        self.shown_at = self.clock()
        draft = self.practice.draft
        values = draft.get("values") or []
        if item["kind"] == "blank":
            for widget, value in zip(self.inputs, values):
                widget.setText(str(value))
        else:
            for row, option in zip(self.choices.rows, item["options"]):
                row.box.setChecked(option["no"] in values)
        # 이번 문항이 답한 상태일 때만 저장한 판정을 복원함.
        if item.get("answered") and self.practice.answered is not None:
            self.dontknow = bool(draft.get("dontknow"))
            self.queued = int(draft.get("queued") or len(self.practice.queue))
            self.show_feedback(self.practice.answered)
        self.saved_values = self.values()
        self.input_context = None
        if item["kind"] == "blank":
            for widget in self.inputs:
                widget.textEdited.connect(self.edit_input)
                widget.editingFinished.connect(self.finish_input)
        else:
            self.choices.changed.connect(self.edit_input)
        self.win.ai.save_practice(self.practice, activate=True)

    def save_progress(self, *_):
        """제출 전 입력과 답한 뒤 상태를 로컬에 남김."""
        if self.practice is None or self.item is None:
            return
        self.practice.draft = {"values": self.values(), "dontknow": self.dontknow, "queued": self.queued}
        return self.win.ai.save_practice(self.practice)

    def edit_input(self, *_):
        if self.feedback is not None:
            return
        if not self.save_progress():
            return
        self.edited_values = self.practice.draft["values"]
        self.input_context = self.practice.sess.collection.observation_context()
        if self.input_context is None:
            self.saved_values = self.edited_values
        elif self.item["kind"] != "blank":
            self.finish_input()

    def finish_input(self):
        context, self.input_context = self.input_context, None
        if context is None or self.practice is None or self.item is None:
            return
        values = self.edited_values
        if values != self.saved_values:
            self.practice.sess.collect_event("ai_input", {"input_schema": AI_INPUT_SCHEMA, "set": self.practice.id,
                                                   "card": self.item["card"], "position": self.practice.pos},
                                      observation_context=context)
        self.saved_values = list(values)

    def hideEvent(self, event):
        self.save_progress()
        self.finish_input()
        super().hideEvent(event)

    def build_blanks(self, item):
        """지문과 빈칸. 칸 순서는 지문에서 ____ 가 나오는 순서이고 answer 에 이 순서로 넘김."""
        blanks = item["blanks"]
        numbered = len(blanks) >= 2
        stem = bank.number_blanks(item["stem"]) if numbered else item["stem"]
        order = []  # 지문 순서대로 ("code", 칸) 또는 ("field", 칸)
        count = 0
        for part in split_stem(stem):
            if part[0] == "text":
                self.docs.append(doc(part[1], "", self.card_box))
                count_here = len(BLANK.findall(part[1]))
                order += [("field", None)] * count_here
                count += count_here
                continue
            here = len(BLANK.findall(part[1]))
            marks = [ai_text.number_mark(count + n + 1) if numbered else "" for n in range(here)]
            hints = [b.get("hint") or ai_text.MODE_HINT.get(b["mode"], "") for b in blanks[count:count + here]]
            slots = CodeSlots(part[1], hints, marks)
            self.card_box.addWidget(slots)
            self.card_box.addWidget(slots.result)
            slots.result.hide()
            for slot in slots.fields:
                self.paste.watch(slot)
            self.slots.append(slots)
            order += [("code", slot) for slot in slots.fields]
            count += here
        fields = QWidget()
        fields_box = kit.box(fields, spacing=16)
        for n, (kind, widget) in enumerate(order):
            if kind == "code":
                self.inputs.append(widget)
                self.results.append(None)
                continue
            blank = blanks[n] if n < len(blanks) else {"mode": "word", "hint": ""}
            field = AnswerLine()
            kit.typed(field, "learn_body")
            field.setPlaceholderText(blank.get("hint") or ai_text.MODE_HINT.get(blank.get("mode"), ""))
            self.paste.watch(field)
            block = QWidget()
            row = kit.box(block, spacing=12, horizontal=True)
            if numbered:  # 번호는 칸 높이의 가운데. 칸 아래 결과 줄은 칸 왼쪽 선에 맞춤
                number = kit.label(ai_text.number_mark(n + 1), "label", bold=True, align=Qt.AlignmentFlag.AlignVCenter)
                number.setFixedHeight(theme.CONTROL["field"])
                row.addWidget(number, 0, Qt.AlignmentFlag.AlignTop)
            column = QWidget()
            column_box = kit.box(column, spacing=4)
            column_box.addWidget(field)
            result = rich("", "body")
            result.hide()
            column_box.addWidget(result)
            row.addWidget(column, 1)
            fields_box.addWidget(block)
            self.inputs.append(field)
            self.fields.append(field)
            self.results.append(result)
        if self.fields:
            self.card_box.addWidget(fields)
        else:
            fields.deleteLater()

    def build_choice(self, item):
        """지문과 보기. 보기가 코드(뼈대 카드)면 CodeChoices 이고 grid 가 2 면 2×2. 보기 아래 풀이 칸(whys)은 보기마다 하나."""
        self.docs.append(doc(item["stem"], "", self.card_box))
        texts = [o["text"] for o in item["options"]]
        if item.get("code_options"):
            self.choices = CodeChoices(texts, single=not item["multi"], grid=item.get("grid") or 1)
            self.whys = self.choices.whys
            self.card_box.addWidget(self.choices)
            self.inputs = list(self.choices.rows)
            return
        self.choices = ChoiceList(texts, single=not item["multi"])
        self.whys = []
        column = self.choices.layout()
        for n, row in enumerate(self.choices.rows):
            why = rich("", "body", "secondary")
            holder = QWidget()
            kit.box(holder, (kit.MARK + 12, 0, 0, 8)).addWidget(why)
            column.insertWidget(column.indexOf(row) + 1, holder)
            holder.hide()
            self.whys.append(holder)
        self.card_box.addWidget(self.choices)
        self.inputs = [row for row in self.choices.rows]

    # 답하기

    def values(self):
        if self.item["kind"] == "blank":
            return [widget.text() for widget in self.inputs]
        return [self.item["options"][n]["no"] for n in self.choices.picked()]

    def press_primary(self):
        if not self.isVisible():
            return
        if self.sure_btn.isVisible() and self.sure_btn.isEnabled():
            self.answer(True)
        elif self.next_btn.isVisible() and self.next_btn.isEnabled():
            self.go_next()
        elif self.again_btn.isVisible() and self.again_btn.isEnabled():
            self.again()

    def press_answer(self, sure):
        if self.isVisible() and self.unsure_btn.isVisible() and self.unsure_btn.isEnabled():
            self.answer(sure)

    def answer(self, sure):
        """[확실함]·[긴가민가]. 조합 중인 한글을 확정한 뒤 칸을 읽음. 아무것도 적거나 고르지 않았으면 안내만 함."""
        if self.practice is None or self.feedback is not None or self.busy:
            return
        commit_input()
        self.finish_input()
        value = self.values()
        if not any(str(v).strip() for v in value):
            self.status.setText(ai_text.EMPTY_ANSWER.get(self.item["kind"], ai_text.EMPTY_ANSWER["blank"]))
            self.status.show()
            return
        secs = self.clock() - self.shown_at
        self.queued = len(self.practice.queue)
        try:
            feedback = self.practice.answer(value, secs, sure)
        except SessionError as error:
            self.win.ask("알림", str(error))
            return
        self.show_feedback(feedback)
        if self.practice.pos == len(self.practice.queue) - 1:
            self.win.auto_submission.request()

    def dont_know(self):
        if self.practice is None or self.feedback is not None or self.busy:
            return
        self.finish_input()
        self.queued = len(self.practice.queue)
        try:
            feedback = self.practice.dont_know(self.clock() - self.shown_at)
        except SessionError as error:
            self.win.ask("알림", str(error))
            return
        self.dontknow = True
        self.show_feedback(feedback)
        if self.practice.pos == len(self.practice.queue) - 1:
            self.win.auto_submission.request()

    def show_feedback(self, feedback):
        """판정 줄, 칸과 보기의 결과, 해설·근거·정정을 그림. 판정 줄이 맨 위에 오게 스크롤함."""
        self.feedback = feedback
        self.status.hide()
        self.guide.hide()
        word, tone = ai_text.VERDICT.get(feedback["result"], ai_text.VERDICT["stuck"])
        if feedback.get("sure_wrong"):
            word = ai_text.SURE_WRONG
        if self.dontknow:
            word, tone = ai_text.DONT_KNOW, "secondary"
        self.verdict_text.setText(word)
        kit.set_tone(self.verdict_text, tone)
        if self.item["kind"] == "blank":
            self.mark_blanks(feedback["per_blank"], feedback["correct"])
        else:
            self.mark_choice(feedback)
        also = [row["blank"] + 1 for row in feedback.get("also") or []]
        self.also_text.setText(ai_text.also_line(also) if also else "")
        self.also_text.setVisible(bool(also))
        self.show_requeue(feedback["result"] == "pass")
        self.verdict.show()
        self.explain(feedback)
        self.set_buttons()
        self.next_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        self.scroll.verticalScrollBar().setValue(0)
        self.save_progress()

    def mark_blanks(self, per, correct):
        """칸마다 테두리 색, 판정 줄 아래 정답 목록. 빈칸이 둘 이상이면 칸마다 "맞음"·"틀림" 글을 더함(글 칸은 칸 아래, 코드 칸은 코드 아래
        한 줄). 정답은 판정 줄 아래 목록에만 씀. [모르겠어요]면 맞고 틀림을 쓰지 않고 테두리도 칠하지 않음. 답한 칸은 읽기 전용이라 자리표시를 지움."""
        numbered = len(self.inputs) >= 2
        marked = numbered and not self.dontknow
        answers, words = [], []
        for n, widget in enumerate(self.inputs):
            ok = n < len(per) and per[n]
            right = correct[n] if n < len(correct) else ""
            word = "맞음" if ok else "틀림"
            font = widget.font()
            widget.setReadOnly(True)
            widget.setPlaceholderText("")
            kit.set_tone(widget, "" if self.dontknow else ("success" if ok else "danger"))
            widget.setFont(font)
            mark = ai_text.number_mark(n + 1) + " " if numbered else ""
            answers.append("%s`%s`" % (mark, right) if self.is_code(widget) else "%s%s" % (mark, right))
            words.append("%s%s" % (mark, word))
            result = self.results[n] if n < len(self.results) else None
            if result is not None:
                result.setText(word)
                kit.set_tone(result, "success" if ok else "danger")
                result.setVisible(marked)
        for slots in self.slots:
            here = [n for n, widget in enumerate(self.inputs) if widget in slots.fields]
            slots.result.setText(" · ".join(words[n] for n in here))
            slots.result.setVisible(marked and bool(here))
        self.answer_line.setText("정답: " + " · ".join(answers))

    def is_code(self, widget):
        return isinstance(widget, Slot)

    def mark_choice(self, feedback):
        """보기마다 꼬리표와 바른 문장. 옳지 않은 것을 고르는 문항의 답은 거짓 문장이라 판정 아래 줄에 "정답" 이라 쓰지 않음."""
        right, picked = set(feedback["right"]), set(feedback["picked"])
        self.choices.set_enabled(False)
        shown = []
        for n, (row, holder) in enumerate(zip(self.choices.rows, self.whys)):
            no = self.item["options"][n]["no"]
            if no in right and no in picked:
                row.set_tag("정답 · 내 답", "success")
            elif no in right:
                row.set_tag("정답", "success")
            elif no in picked:
                row.set_tag("내 답", "danger")
            why = ai_text.teaching_text(feedback["why"].get(no) or feedback["why"].get(str(no)) or "")
            holder.findChild(RichPara).setText(why)
            holder.setVisible(bool(why))
            if no in right:
                shown.append(self.item["options"][n]["text"])
        word = "옳지 않은 문장" if self.item.get("pick") == "wrong" else "정답"
        if self.item.get("code_options"):  # 여러 줄 코드를 한 줄에 이으면 읽을 수 없어 보기 꼬리표만 씀
            shown = []
        self.answer_line.setText("%s: %s" % (word, " · ".join(shown)) if shown else "")
        self.answer_line.setVisible(bool(shown))

    def show_requeue(self, passed):
        """방금 답한 문항이 묶음 뒤에 다시 들어갔으면 몇 문항 뒤에 나오는지 쓰고 위 막대의 전체 문항 수를 늘림. 묶음 길이가 늘어난 까닭을 알림."""
        practice = self.practice
        gap = None
        if len(practice.queue) > self.queued:
            gap = next((j - practice.pos - 1 for j in range(practice.pos + 1, len(practice.queue))
                        if practice.queue[j]["card"] == self.item["card"]), None)
        self.requeue.setText(ai_text.requeue_line(passed, gap) if gap is not None else "")
        self.requeue.setVisible(gap is not None)
        self.count.setText("%d / %d" % (self.item["at"], len(practice.queue)))  # 늘어난 전체 문항 수를 바로 보임

    def explain(self, feedback):
        box = self.after_box
        while box.count():
            item = box.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if feedback.get("explain"):
            box.addWidget(kit.label("해설", "label", bold=True))
            self.docs.append(doc(ai_text.teaching_text(feedback["explain"]), "", box))
        target = self.note_reference()
        if target:
            link = kit.typed(LinkLabel('<a href="study-note">참고: %s</a>' % html.escape(target["label"]),
                                       line=theme.TYPE["caption"][1], font=theme.font("caption")), "caption")
            link.linkActivated.connect(self.open_reference)
            box.addWidget(link)
        self.after.setVisible(box.count() > 0)

    def override(self):
        """[내 답도 맞음]. 방금 틀린 빈칸 답을 맞음으로 바꿈. 뼈대 빈칸은 서비스가 함께 가린 칸까지 틀린 칸 모두를 한 번에 바꾸므로
        화면도 모든 칸을 맞음으로 칠하고 함께 가린 칸 줄을 지움."""
        try:
            feedback = self.practice.override()
        except SessionError as error:
            self.win.ask("알림", str(error))
            return
        self.feedback = feedback
        self.verdict_text.setText(ai_text.OVERRIDDEN)
        kit.set_tone(self.verdict_text, "success")
        self.mark_blanks([True] * len(self.inputs), self.answers_of())
        self.also_text.hide()
        self.show_requeue(True)
        self.set_buttons()

    def answers_of(self):
        """판정 줄 아래에 쓴 정답 목록을 다시 쓰려고 가져옴."""
        return [str(c) for c in (self.feedback or {}).get("correct", [])]

    def go_next(self):
        if self.practice is None or self.feedback is None:
            return
        self.close_note()
        try:
            item = self.practice.next(measure_input=True)
        except SessionError as error:
            self.win.ask("알림", str(error))
            return
        if item is None:
            self.show_summary()
        else:
            self.show_item(item)

    # 끝 요약

    def show_review_complete(self):
        self.close_note()
        self.empty_card()
        self.item, self.feedback = None, None
        self.count.setText("끝남")
        self.bar_line.setValue(100)
        self.card_box.addWidget(kit.heading(kit.para(ai_text.REVIEW_COMPLETE, "headline"),
                                           kit.para(ai_text.review_next(self.review_state["next"]))))
        self.set_buttons()
        self.home_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        self.scroll.verticalScrollBar().setValue(0)

    def show_summary(self):
        self.win.auto_submission.request()
        summary = self.practice.summary()
        if self.practice.mode in ("review", "sweep"):
            self.review_state = self.win.ai.review_status()
        complete = self.review_state is not None and not self.review_state["available"]
        if complete:
            summary = dict(summary, next=self.review_state["next"])
        self.close_note()
        self.empty_card()
        self.item, self.feedback = None, None
        self.count.setText("끝남")
        self.bar_line.setValue(100)
        title = kit.heading(kit.para(ai_text.SET_FIRST, "caption", "secondary"),
                            kit.para(ai_text.summary_head(summary), "headline"))
        lines = QWidget()
        lines_box = kit.box(lines, spacing=8)
        for text in ai_text.summary_lines(summary, self.unlisted()):
            lines_box.addWidget(kit.para(text))
        if complete:
            lines_box.addWidget(kit.para(ai_text.REVIEW_COMPLETE))
            if self.review_state["next"] is None:
                lines_box.addWidget(kit.para(ai_text.review_next(None)))
        self.card_box.addWidget(kit.heading(title, lines))
        self.card_box.addWidget(kit.para(ai_text.TRAINED, "body", "secondary"))
        self.set_buttons()
        if complete:
            self.home_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        self.scroll.verticalScrollBar().setValue(0)

    def unlisted(self):
        """단원을 오늘 읽어서 처음 답이 틀렸어도 오답 노트에 들어가지 않은 문항 수(확실함으로 틀린 답은 넣음). 그날 앞 묶음에서 맞힌
        문항이 이번에 틀린 것은 세지 않음."""
        try:
            listed = {item["key"] for group in self.win.ai.wrong_notes() for item in group["items"]}
            return sum(1 for cid, st in self.practice.stats.items()
                       if st["first"] not in (None, "pass") and cid not in listed and self.win.ai.read_today(cid))
        except SessionError:
            return 0

    def again(self):
        """[한 번 더]·[다음 단원]·[오답 노트로]. 단원 모드는 다음 안 읽은 단원을, 오답 다시 풀기는 오답 노트를, 나머지는 같은 모드의 새 묶음을 엶."""
        mode, lesson, unit, card = self.args
        if mode == "note":
            self.win.show_wrong("ai", self.win.wrong_page.back)
            return
        if mode == "unit":
            target = self.next_unit()
            if target:
                self.win.open_ai_unit(*target)
                return
            mode = "mixed"
        if mode == "mixed":  # 다시 보기 뒤 묶음도 다음 판은 보통 섞어 풀기
            lesson, unit = None, None
        self.win.open_ai_practice(mode, lesson=lesson, unit=unit)

    def next_unit(self):
        try:
            item = self.win.ai.continuation()
        except SessionError:
            return None
        return (item["lesson"], item["unit"]) if item["kind"] == "unit" else None

    # 단추

    def set_buttons(self):
        asking = self.item is not None and self.feedback is None
        answered = self.item is not None and self.feedback is not None
        ended = self.item is None and self.practice is not None
        complete = self.item is None and self.review_state is not None and not self.review_state["available"]
        for button, on in ((self.dont_btn, asking), (self.unsure_btn, asking), (self.sure_btn, asking), (self.next_btn, answered),
                           (self.note_btn, answered and self.note_reference() is not None),
                           (self.mine_btn, answered and self.item["kind"] == "blank" and not self.dontknow
                            and (self.feedback["result"] != "pass" or self.feedback.get("also")) and not self.feedback.get("overridden")),
                           (self.home_btn, ended or complete), (self.again_btn, ended and not complete)):
            button.setVisible(bool(on))
            button.setEnabled(not self.busy)
        if ended:
            mode = self.args[0]
            if mode == "note":
                text = "오답 노트로"
            elif mode == "unit":  # 안 읽은 단원이 없으면 again() 이 섞어 풀기를 엶
                text = "다음 단원" if self.next_unit() else "섞어 풀기"
            else:
                text = "한 번 더"
            self.again_btn.setText(text)
            self.again_btn.setToolTip("같은 연습 방식으로 새 문제 묶음을 만듭니다." if text == "한 번 더" else "")

    def note_reference(self):
        if not self.item or self.win.ai is None:
            return None
        try:
            return self.win.ai.note_target(self.item.get("card"))
        except SessionError:
            return None

    def open_reference(self, url):
        if url == "study-note":
            self.open_note()

    def open_note(self):
        target = self.note_reference()
        if target is None:
            return
        self.close_note()
        try:
            self.note_dialog = NoteDialog(self.win, target["lesson"], target["step"])
        except SessionError as error:
            self.win.ask("알림", str(error))
            return
        self.note_dialog.open()  # 창 모달. 열어 둔 채 [다음]으로 넘어가 다시 나온 문항을 노트를 보며 풀 수 없게 함

    def close_note(self):
        """열린 [노트 보기] 창을 닫음. 문항을 바꾸거나 묶음이 끝나거나 서비스가 바뀔 때 부름."""
        dialog, self.note_dialog = self.note_dialog, None
        if dialog is not None:
            try:
                dialog.close()
            except RuntimeError:  # 닫혀 지워진 창의 파이썬 껍데기
                pass

    def note_blocked(self):
        """붙여넣기를 막았다는 안내. 이 화면이 보일 때만."""
        if self.isVisible() and self.item is not None and self.feedback is None:
            self.status.setText(PASTE_NOTE)
            self.status.show()

    def go_back(self):
        if self.args and self.args[0] == "note":
            self.win.show_wrong("ai", self.win.wrong_page.back)
        else:
            self.win.go_ai()

    def fit_column(self):
        self.card.setMaximumWidth(reading_width(self.width()) + 2 * CARD_PAD)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_column()

    def set_busy(self, busy, text=""):
        self.busy = busy
        self.back_btn.setEnabled(not busy)
        if self.practice is not None:
            self.set_buttons()

    def restyle(self):
        self.fit_column()
        for piece in self.docs:
            piece.restyle(theme.learning_css())
        for widget in self.findChildren(RichPara):
            widget.restyle()
        for slots in self.slots:
            slots.restyle()
