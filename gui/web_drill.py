# -*- coding: utf-8 -*-
"""꼬리 질문 사슬 화면: 머리줄(돌아가기 · 사슬 제목 · 질문 번호 · 답 시계) · 위쪽 사슬 소개와 면접관이 보여 주는 코드 · 아래쪽 질문 하나,
적는 칸(선택), [답 확인] [모르겠어요], 그 뒤 [필수]·[보충] 짚을 내용과 지난 답, 「막히면」 줄과 "아는 데까지 말했습니다" 표시,
질문별 판정 · 사슬 끝의 약한 답, 이어 말하기, 학습 노트 절로 가는 단추, 결과와 다음 복습 날짜.

답 시간은 질문을 보인 때부터 [답 확인]이나 [모르겠어요]를 누른 때까지이고 clock(기본 time.monotonic)으로 잼. 시계가 끝나도 막지 않고
넘긴 초만 빨갛게 보임. 두 단추는 한 질문에서 한 번만 쓰므로 누른 뒤에는 숨겨 그 줄을 짚을 내용에 돌려줌.
기록은 질문마다 서비스의 answer 로, 사슬 끝에 finish_chain 으로 남김.
질문 칸은 내용 높이만큼만 차지하고(FitScroll) 나머지는 사슬 소개와 코드가 씀."""
import time

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
                             QVBoxLayout, QWidget)

import mdlite
from gui import theme
from gui.docview import DocView
from gui.journey_page import md_text
from gui.web_home import clock_text, day_text
from gui.web_mission import LANG, CheckList, quote_lines
from gui.widgets import Para
from webprep import service
from webprep.record import NOTE_LIMIT
from webprep.service import WebError

TALKED_TEXT = "막힌 곳에서 아는 데까지 말했습니다"
INTRO_LEAST = 120  # 질문 칸이 커져도 사슬 소개에 남겨 두는 높이
NOTE_HINT = "말한 내용 (선택, %d자까지). 다음 복습 때 짚을 내용 옆에 보입니다. [제출]하면 저장소에 올라갑니다." % NOTE_LIMIT


def plain(text):
    """표시 항목과 질문처럼 QLabel 에 넣는 글. 인라인 마크다운(`코드`, **굵게**)을 꾸밈 없는 글자로 바꿈."""
    return mdlite.inline_plain(text)


def intro_markdown(chain):
    parts = ["## 사슬 %s. %s" % (chain["id"], md_text(chain["title"]))]
    if chain["goal"]:
        parts.append(md_text(chain["goal"]))
    if chain["box"]:
        parts.append("상자 %d, %d번째 복습" % (chain["box"], chain["times"] + 1))
    if chain["intro"]:
        parts.append(chain["intro"])
    if chain["code"]:
        parts.append(chain["code"])
    return "\n\n".join(parts)


def end_markdown(done, chain):
    """사슬 끝 칸: 결과와 상자, 약한 답, 이어 말하기."""
    per = ", ".join(service.RESULT_LABEL[r] for r in done["per_question"])
    parts = ["## 사슬 결과: %s" % done["label"], "질문별 %s" % per, "상자 %d, 다음 복습 %s" % (done["box"], day_text(done["due"]))]
    if done["weak"]:
        parts.append("## 약한 답\n\n%s" % quote_lines(done["weak"]["quote"]))
        if done["weak"]["why"]:
            parts.append(done["weak"]["why"])
    if done["follow"]:
        parts.append("## 이어 말하기\n\n%s" % quote_lines(done["follow"]))
    if chain["page"]:
        parts.append("이어서 학습 노트 %s%s 을 읽으면 이 사슬의 원리가 나옵니다." % (chain["page"], " (%s 절)" % chain["section"] if chain["section"] else ""))
    return "\n\n".join(parts)


def last_note(last):
    """지난 답 한 줄. 적은 내용이 없으면 그 사실과 날짜."""
    if not last:
        return ""
    when = day_text(last.get("at") or "")
    note = last.get("note") or "적은 내용 없음"
    secs = last.get("secs")
    return "지난 답 (%s%s): %s" % (when, ", %d초" % secs if secs is not None else "", note)


class FitScroll(QScrollArea):
    """질문 칸을 담는 스크롤 칸. 세로 상자에 카드의 줄바꿈 높이를 heightForWidth 로 알려 주어 칸이 내용 높이만큼만 차지하고,
    창이 작아 위의 사슬 소개에 keep 만큼을 남기지 못할 때는 그만큼 줄여 안에서 스크롤함."""

    def __init__(self, keep):
        super().__init__()
        self.keep = keep
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def hasHeightForWidth(self):
        return self.widget() is not None

    def heightForWidth(self, width):
        card = self.widget()
        layout = card.layout()
        want = layout.heightForWidth(width) if layout.hasHeightForWidth() else card.sizeHint().height()
        parent = self.parentWidget()
        room = parent.height() - self.keep if parent is not None and parent.height() > 0 else want
        return max(0, min(want, room))

    def sizeHint(self):
        return QSize(super().sizeHint().width(), self.heightForWidth(max(1, self.width())))


class WebDrillPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        self.setProperty("clipboard", True)  # 적는 칸은 자기 말을 적는 곳이라 붙여넣기를 막지 않음
        self.win = win
        self.cid, self.chain, self.back = None, None, None
        self.index, self.started, self.checked, self.gave_up = 0, 0.0, False, False
        self.verdicts, self.secs, self.done = [], 0, None  # 이번 회차의 질문별 판정, 지금 질문의 답 시간, 사슬 끝 결과
        self.clock = time.monotonic
        self.busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 0)
        root.setSpacing(8)
        head = QHBoxLayout()
        self.back_btn = QPushButton("돌아가기")
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.counter = QLabel()
        self.counter.setObjectName("muted")
        self.timer_label = QLabel()
        self.timer_label.setObjectName("h2")
        self.timer_label.setTextFormat(Qt.TextFormat.RichText)
        head.addWidget(self.back_btn)
        head.addSpacing(8)
        head.addWidget(self.title, 1)
        head.addWidget(self.counter)
        head.addSpacing(16)
        head.addWidget(self.timer_label)
        root.addLayout(head)

        self.stack = QStackedWidget()
        ask_page = QWidget()
        ask_box = QVBoxLayout(ask_page)
        ask_box.setContentsMargins(0, 0, 0, 0)
        ask_box.setSpacing(8)
        self.intro_view = DocView()
        self.intro_view.setMinimumHeight(INTRO_LEAST)
        card = QFrame()
        card.setObjectName("card")
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 14, 20, 14)
        box.setSpacing(10)
        self.ask = Para(name="h2")
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText(NOTE_HINT)
        self.note.setMaximumHeight(72)
        self.answer_row = QWidget()  # [답 확인] [모르겠어요]. 누른 뒤에는 통째로 숨김
        row = QHBoxLayout(self.answer_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.confirm_btn = QPushButton("답 확인")
        self.confirm_btn.setObjectName("primary")
        self.give_up_btn = QPushButton("모르겠어요")
        row.addWidget(self.confirm_btn)
        row.addStretch(1)
        row.addWidget(self.give_up_btn)
        self.items_title = Para("짚을 내용입니다. 말한 항목에 표시하세요.", "muted")
        self.last = Para(name="muted")
        self.items = CheckList()
        self.stuck = Para(name="warn")
        self.talked = CheckList()
        self.progress = Para(name="muted")
        after_row = QHBoxLayout()
        self.next_btn = QPushButton("다음 질문")
        self.next_btn.setObjectName("primary")
        after_row.addStretch(1)
        after_row.addWidget(self.next_btn)
        for widget in (self.ask, self.note, self.answer_row, self.items_title, self.last, self.items, self.stuck, self.talked, self.progress):
            box.addWidget(widget)
        box.addLayout(after_row)
        self.card = card
        self.card_scroll = FitScroll(INTRO_LEAST + ask_box.spacing())
        self.card_scroll.setWidget(card)
        ask_box.addWidget(self.intro_view, 1)
        ask_box.addWidget(self.card_scroll)
        end_page = QWidget()
        end_box = QVBoxLayout(end_page)
        end_box.setContentsMargins(0, 0, 0, 8)
        self.end_view = DocView()
        end_row = QHBoxLayout()
        end_row.setContentsMargins(20, 0, 20, 0)
        self.learn_btn = QPushButton("학습 노트 읽기")
        self.again_btn = QPushButton("한 번 더")
        self.done_btn = QPushButton("돌아가기")
        self.done_btn.setObjectName("primary")
        end_row.addWidget(self.learn_btn)
        end_row.addStretch(1)
        end_row.addWidget(self.again_btn)
        end_row.addWidget(self.done_btn)
        end_box.addWidget(self.end_view, 1)
        end_box.addLayout(end_row)
        self.stack.addWidget(ask_page)
        self.stack.addWidget(end_page)
        self.ask_page, self.end_page = ask_page, end_page
        root.addWidget(self.stack, 1)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 8)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setMinimumWidth(1)
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedWidth(140)
        self.busy_bar.hide()
        bar.addWidget(self.status, 1)
        bar.addWidget(self.busy_bar)
        root.addLayout(bar)

        self.ticker = QTimer(self)
        self.ticker.setInterval(1000)
        self.ticker.timeout.connect(self.tick)
        self.back_btn.clicked.connect(self.go_back)
        self.done_btn.clicked.connect(self.go_back)
        self.confirm_btn.clicked.connect(lambda: self.reveal(False))
        self.give_up_btn.clicked.connect(lambda: self.reveal(True))
        self.next_btn.clicked.connect(self.answer)
        self.learn_btn.clicked.connect(self.open_learn)
        self.again_btn.clicked.connect(lambda: self.load(self.cid, self.back))
        self.note.textChanged.connect(self._clip_note)

    # 불러오기

    def load(self, cid, back=None):
        """사슬을 화면에 올리고 첫 질문부터 시작함. back 은 돌아갈 곳(("mission", 미션 id) 또는 None 이면 웹 홈). 잠긴 사슬이면 WebError."""
        chain = self.win.web.chain(cid)
        self.cid, self.chain, self.back = cid, chain, back
        self.index, self.verdicts = 0, []
        self.title.setText("사슬 %s %s" % (chain["id"], chain["title"]))
        self.intro_view.set_markdown(intro_markdown(chain), "", LANG)
        self.stack.setCurrentWidget(self.ask_page)
        self.status.setText("")
        self.show_question()

    def question(self):
        return self.chain["questions"][self.index]

    def show_question(self):
        question = self.question()
        self.counter.setText("질문 %d / %d" % (self.index + 1, len(self.chain["questions"])))
        self.ask.setText("면접관: %s" % plain(question["ask"]))
        self.note.setPlainText("")
        self.started, self.checked, self.gave_up = self.clock(), False, False
        for widget in (self.items_title, self.last, self.items, self.stuck, self.talked, self.next_btn):
            widget.hide()
        self.note.setEnabled(True)
        self.answer_row.show()
        self.confirm_btn.setEnabled(not self.busy)
        self.give_up_btn.setEnabled(not self.busy)
        self.progress.setText(self.progress_text())
        self.progress.setVisible(bool(self.verdicts))
        self.tick()
        self.card_scroll.updateGeometry()  # 질문 칸의 높이를 새 내용에 맞춤

    def progress_text(self):
        return " · ".join("Q%d %s" % (q["no"], service.RESULT_LABEL[r]) for q, r in zip(self.chain["questions"], self.verdicts))

    # 시계

    def tick(self):
        if self.chain is None or self.checked:
            return
        limit = self.chain["secs"]
        gone = int(self.clock() - self.started)
        if gone <= limit:
            self.timer_label.setText("답 시간 %s" % clock_text(limit - gone))
        else:
            self.timer_label.setText('답 시간 0:00 · <span style="color: %s;">%s 넘김</span>' % (theme.color("wrong"), clock_text(gone - limit)))

    def showEvent(self, event):
        super().showEvent(event)
        self.ticker.start()
        self.tick()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.ticker.stop()

    # 답 확인

    def reveal(self, gave_up):
        """[답 확인]이나 [모르겠어요]. 답 시간을 멈추고 짚을 내용을 엶."""
        question = self.question()
        self.secs = int(self.clock() - self.started)
        self.checked, self.gave_up = True, gave_up
        limit = self.chain["secs"]
        if self.secs <= limit:
            self.timer_label.setText("답 시간 %s (%s 안)" % (clock_text(self.secs), clock_text(limit)))
        else:
            self.timer_label.setText('답 시간 %s · <span style="color: %s;">%s 넘김</span>'
                                     % (clock_text(self.secs), theme.color("wrong"), clock_text(self.secs - limit)))
        self.answer_row.hide()
        last = question["last"]
        need_marks = list(last["need"]) if last else []
        extra_marks = list(last["extra"]) if last else []
        rows, need_no, extra_no = [], 0, 0
        for item in question["items"]:
            if item["need"]:
                mark, need_no = (need_marks[need_no] if need_no < len(need_marks) else None), need_no + 1
            else:
                mark, extra_no = (extra_marks[extra_no] if extra_no < len(extra_marks) else None), extra_no + 1
            note = "" if mark is None else ("지난번 표시함" if mark else "지난번 빠뜨림")
            rows.append((plain(item["text"]), "필수" if item["need"] else "보충", note, False))
        self.items.set_items(rows)
        self.items.set_enabled(not gave_up)
        for row in self.items.rows:
            row.box.toggled.connect(lambda checked=False: self.sync_stuck())
        self.last.setText(last_note(last))
        self.last.setVisible(bool(last))
        self.items_title.setText("모르겠다고 답했습니다. 짚을 내용을 읽고 [다음 질문]을 누르세요." if gave_up else "짚을 내용입니다. 말한 항목에 표시하세요.")
        self.items_title.show()
        self.items.show()
        self.talked.set_items([(TALKED_TEXT, "", "", False)])
        self.next_btn.setText("사슬 끝내기" if self.index == len(self.chain["questions"]) - 1 else "다음 질문")
        self.next_btn.show()
        self.next_btn.setEnabled(not self.busy)
        self.sync_stuck()
        self.card_scroll.updateGeometry()

    def need_marks(self):
        question = self.question()
        marks = self.items.marks()
        need = [m for m, item in zip(marks, question["items"]) if item["need"]]
        extra = [m for m, item in zip(marks, question["items"]) if not item["need"]]
        return need, extra

    def sync_stuck(self):
        """[필수]를 빠뜨렸으면 「막히면」 줄과 "아는 데까지 말했습니다" 표시를 보임."""
        need, _ = self.need_marks()
        missing = not all(need)
        question = self.question()
        self.stuck.setText("막히면: %s" % plain(question["stuck"]) if question["stuck"] else "막힌 곳에서 아는 데까지 말했는지 표시하세요.")
        self.stuck.setVisible(missing)
        self.talked.setVisible(missing)

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
        self.status.setText("Q%d 판정: %s" % (self.question()["no"], result["label"]))
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
        self.counter.setText("질문 %d / %d" % (len(self.chain["questions"]), len(self.chain["questions"])))
        self.timer_label.setText("")
        self.end_view.set_markdown(end_markdown(done, self.chain), "", LANG)
        self.learn_btn.setVisible(bool(done["page"]))
        self.learn_btn.setText("학습 노트 %s 읽기%s" % (done["page"], " (%s 절)" % done["section"] if done["section"] else ""))
        self.done_btn.setText("미션으로" if self.back and self.back[0] == "mission" else "웹 홈")
        self.stack.setCurrentWidget(self.end_page)
        self.status.setText("사슬 결과 %s. 상자 %d, 다음 복습 %s." % (done["label"], done["box"], day_text(done["due"])))

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
        for widget in (self.back_btn, self.done_btn, self.learn_btn, self.again_btn, self.next_btn):
            widget.setEnabled(not busy)
        self.confirm_btn.setEnabled(not busy and not self.checked)
        self.give_up_btn.setEnabled(not busy and not self.checked)
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")

    def restyle(self):
        css, font = theme.journey_css(self.win.zoom), theme.code_font(self.win.zoom)
        for view in (self.intro_view, self.end_view):
            view.restyle(css, font)
        if self.chain is not None:
            self.tick()
