# -*- coding: utf-8 -*-
"""AI 비전 개론 학습 단원 화면(AiLearnPage), 다시 보기 화면(RevisitPage), 차시의 전체 노트·외울 것 화면(AiNotePage), 연습 화면의
[노트 보기] 대화상자(NoteDialog)와 그 안의 부품.

한 화면에 단계 하나를 보임. 단계(StepView)는 서비스가 나눠 준 블록을 위에서 아래로 쌓음: 글은 docview.Doc(그 안의 > **[정정]**,
> **[보충 설명]** 인용은 꼬리표를 단 상자로 뺌), 그림은 AiFigure, ai-guess·ai-reveal·ai-recall·ai-why·ai-memo·ai-trend 는 아래의 블록 위젯.
1~4차시 노트에 ai-diff·ai-rotate 가 없어서 그 둘과 모르는 블록은 읽지 못한 블록처럼 안내 글만 둠(뼈대 카드와 같이 다음 PR).

AiFigure 는 GIF 를 1장에서 멈춘 채 열고, 지금 장의 `프레임:` 설명을 그림 바로 아래에 두어 장을 넘길 때 같이 바꿈. 설명 칸은 가장 긴 장
설명의 높이를 지켜서 장을 넘겨도 넘김 단추가 움직이지 않음. 그림에 초점이 있으면 ←·→ 가 장을 넘김. 단계 이동은 아래 막대와 ←·→ 이고,
입력 칸·그림·외울 것 줄에 초점이 있으면 그쪽이 ←·→ 를 쓰므로 Alt+←·→ 로만 넘김.
마지막 단계를 보인 순간 단원을 읽은 것으로 기록하고, 단계를 옮길 때마다 중간 자리를 로컬에 남김. 읽기 화면이라 복사를 막지 않음."""
import html
import re

from PyQt6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPainter, QPen, QShortcut
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy, QWidget

import mdlite
from aiprep import bank
from gui import ai_text, kit, theme
from gui.docview import Doc, FigureView, missing_figure
from gui.widgets import Para
from gui.wrong_page import Arrow
from session import SessionError

BOX_LINE = re.compile(r"^\s*>\s?\*\*\[(정정|보충 설명)\]\*\*\s*")
WIDE = 16777215  # Qt 위젯 크기의 상한. Doc 의 최대 폭(640)을 풀어 카드 폭을 따르게 함
STEP_KEYS = (("Left", -1), ("Right", 1), ("Alt+Left", -1), ("Alt+Right", 1))


def code_span(text):
    """인라인 코드 조각을 코드 글꼴과 code_bg 바탕의 span 으로. QLabel 리치 텍스트는 문서 CSS 를 받지 않아 style 을 직접 씀."""
    families = ", ".join("'%s'" % name for name in theme.code_families())
    return '<span style="font-family: %s; background-color: %s;">%s</span>' % (families, theme.color("code_bg"), html.escape(text, quote=False))


def inline_markup(text):
    """인라인 마크다운을 QLabel 리치 텍스트로."""
    def render(tokens):
        out = []
        for kind, value in tokens:
            if kind == "code":
                out.append(code_span(value))
            elif kind == "bold":
                out.append("<b>%s</b>" % render(value))
            elif kind == "br":
                out.append("<br/>")
            else:
                out.append(html.escape(value, quote=False))
        return "".join(out)
    return render(mdlite.inline_tokens(text or ""))


class RichPara(Para):
    """인라인 마크다운(`코드`, **굵게**)을 그리는 여러 줄 글. 코드 바탕색은 넣을 때의 테마로 굳어 restyle 이 글을 다시 넣음.
    줄 높이는 비율이 아니라 px 로 줌. 화면 글꼴에 없는 글자(−)를 다른 글꼴로 그리면 비율 줄 높이는 그 글꼴 높이로 벌어짐."""

    def markup(self, text):
        return '<span style="white-space: pre-wrap;">%s</span>' % inline_markup(text)

    def setText(self, text):
        self.plain, self.pct = text, self.percent()
        QLabel.setText(self, text and '<p style="margin: 0; line-height: %dpx;">%s</p>' % (self.line, self.markup(text)))
        if self.line and self.width() > 1:
            self.hold()

    def tail(self):
        return 0

    def restyle(self):
        self.setText(self.plain)


def rich(text="", role="body", tone="", bold=None):
    out = kit.typed(RichPara(text, line=theme.TYPE[role][1], font=theme.font(role, bold)), role, bold)
    if tone:
        out.setProperty("tone", tone)
    return out


def split_boxes(markdown):
    """글을 [("text", 마크다운) | ("box", 꼬리표, 마크다운)] 로 나눔. > **[정정]**·> **[보충 설명]** 으로 시작하는 인용이 상자임.
    코드 울타리 안의 > 줄은 건드리지 않음."""
    parts, text, box, fence = [], [], None, False
    for line in (markdown or "").split("\n"):
        if box is not None:
            if line.lstrip().startswith(">"):
                box[1].append(re.sub(r"^\s*>\s?", "", line))
                continue
            parts.append(("box", box[0], "\n".join(box[1]).strip()))
            box = None
        if bank.FENCE.match(line):
            fence = not fence
        found = None if fence else BOX_LINE.match(line)
        if found:
            if "\n".join(text).strip():
                parts.append(("text", "\n".join(text).strip("\n")))
            text = []
            box = (found.group(1), [line[found.end():]])
            continue
        text.append(line)
    if box is not None:
        parts.append(("box", box[0], "\n".join(box[1]).strip()))
    if "\n".join(text).strip():
        parts.append(("text", "\n".join(text).strip("\n")))
    return parts


def doc(markdown, base_dir, layout):
    """layout 에 붙인 뒤 글을 넣은 Doc. Doc.set_markdown 이 보이기를 정하는데 부모가 없으면 잠깐 따로 창으로 떠서 창이 초점을 잃음."""
    out = Doc()
    out.setMaximumWidth(WIDE)
    layout.addWidget(out)
    out.set_markdown(markdown, base_dir, "python")
    return out


def head(text):
    """블록 머리의 작은 이름(떠올리기, 왜일까요?)."""
    return kit.label(text, "caption", "tertiary", bold=True)


class TextBlock(QWidget):
    """단계 글 한 덩이. 정정·보충 설명 인용은 꼬리표를 단 회색 상자로 그림."""

    def __init__(self, markdown, base_dir):
        super().__init__()
        self.docs = []
        column = kit.box(self, spacing=16)
        for part in split_boxes(markdown):
            if part[0] == "text":
                self.docs.append(doc(part[1], base_dir, column))
                continue
            word, tone = ai_text.BOXES[part[1]]
            box, inner = kit.well(16, 16, 8)
            tag_row = QHBoxLayout()
            tag_row.setContentsMargins(0, 0, 0, 0)
            tag_row.addWidget(kit.badge(word, tone))
            tag_row.addStretch(1)
            inner.addLayout(tag_row)
            column.addWidget(box)
            self.docs.append(doc(part[2], base_dir, inner))


class AiFigure(FigureView):
    """학습 단원 그림. 자동 재생하지 않고 1장에서 멈춘 채 열림. frames 는 figure 블록의 `프레임:` 줄([{"text", "ms"}])이고 지금 장의
    설명을 그림 바로 아래(넘김 줄 위)에 가운데 맞춰 둠. 설명 칸의 최소 높이는 지금 폭에서 가장 긴 장 설명의 높이라 장마다 설명 줄 수가
    달라도 넘김 줄과 캡션이 제자리에 있음. 넘김 단추는 단계 넘김 [이전]·[다음]과 헷갈리지 않게 [이전 장]·[다음 장]으로 씀.
    초점이 있으면 ←·→ 가 장을 넘기고(Alt 가 붙으면 단계 넘김으로 보냄) 그림 둘레에 초점 테두리를 그림. last 면 마지막 장에서 엶."""

    def __init__(self, path, caption="", frames=(), last=False):
        super().__init__(path, caption, autoplay=False, frame_changed=self.show_frame)
        self.frames = list(frames or [])
        self.held = None  # 설명 칸 높이를 잰 (폭, 본문 글자 크기)
        self.frame_text = rich("", "body", "secondary")
        self.frame_text.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.layout().insertWidget(1, self.frame_text)
        self.frame_text.setVisible(any(f.get("text") for f in self.frames))  # 설명이 없는 장도 자리를 지켜 단추가 움직이지 않게 함
        if self.movie:
            self.prev_btn.setText("이전 장")
            self.next_btn.setText("다음 장")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if self.movie and self.count > 1 else Qt.FocusPolicy.NoFocus)
        if last and self.movie:
            self.go(self.count - 1)
        self.show_frame(self.frame())

    def show_frame(self, number):
        self.frame_text.setText(self.frames[number]["text"] if number < len(self.frames) else "")

    def hold_frames(self):
        """설명 칸의 최소 높이를 지금 폭에서 가장 긴 장 설명의 높이로 둠. 폭이나 글자 크기가 바뀔 때만 다시 잼(장을 넘길 때마다 draw 가 불림)."""
        width = self.width()
        key = (width, theme.TYPE["body"][0])
        if not self.frame_text.isVisibleTo(self) or width <= 1 or key == self.held:
            return
        shown, tallest = self.frame_text.plain, 0
        self.frame_text.setMinimumHeight(0)  # 최소 높이가 남아 있으면 heightForWidth 가 그 아래로 내려가지 않음
        for frame in self.frames:
            self.frame_text.setText(frame.get("text", ""))
            tallest = max(tallest, self.frame_text.heightForWidth(width))
        self.frame_text.setText(shown)
        self.frame_text.setMinimumHeight(tallest)
        self.held = key

    def draw(self):
        super().draw()
        if hasattr(self, "frame_text"):
            self.hold_frames()

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) and self.movie \
                and not event.modifiers() & Qt.KeyboardModifier.AltModifier:
            event.accept()  # 단계 넘김 단축키보다 장 넘김이 먼저. Alt+←·→ 는 단계 넘김에 둠
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        alt = event.modifiers() & Qt.KeyboardModifier.AltModifier
        if self.movie and not alt and event.key() == Qt.Key.Key_Left:
            self.prev()
        elif self.movie and not alt and event.key() == Qt.Key.Key_Right:
            self.next()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        """초점 테두리는 그림 둘레에만 그림. 그림 칸은 폭을 다 쓰고 그림은 가운데라 칸이 아니라 그림 크기로 잼."""
        super().paintEvent(event)
        pixmap = self.picture.pixmap()
        if self.hasFocus() and pixmap is not None and not pixmap.isNull():
            size = pixmap.deviceIndependentSize()
            place = self.picture.geometry()
            rect = QRectF(QPointF(place.x() + (place.width() - size.width()) / 2, place.y() + (place.height() - size.height()) / 2), size)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(theme.qcolor("focus"), 2))
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), theme.RADIUS["control"], theme.RADIUS["control"])


def figure(block):
    """figure 블록의 그림. 파일을 읽지 못하면 안내 글."""
    try:
        return AiFigure(block["path"], block.get("caption", ""), block.get("frames"))
    except OSError:
        return missing_figure(block.get("file", ""))


class RadioMark(kit.CheckMark):
    """하나만 고르는 보기의 둥근 표시. 네모 체크 상자(여럿 고르기)와 모양으로 나뉨. 켜면 accent 테두리 안에 채운 점을 그림.
    누르면 켜기만 함(이미 고른 보기를 다시 눌러도 꺼지지 않음)."""

    def toggle(self):
        if self.isEnabled():
            self.setChecked(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, (self.height() - 20) // 2, 20, 20)
        if not self.isEnabled():
            edge, dot = ("primary_off", "primary_off") if self.checked else ("border", None)
        else:
            edge, dot = ("primary", "primary") if self.checked else ("field_edge", None)
        painter.setPen(QPen(theme.qcolor(edge), 2))
        painter.setBrush(theme.qcolor("surface_alt" if not self.isEnabled() and not self.checked else "surface"))
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))
        if dot:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor(dot))
            painter.drawEllipse(rect.adjusted(5, 5, -5, -5))


class OptionRow(kit.Check):
    """고르기 보기 한 줄. kit.Check 의 글을 인라인 마크다운으로 그림(보기에 `코드`가 많음). 글은 px 줄 높이라 넓힌 간격이 글자 위에
    생기므로, 표시를 첫 줄 높이 칸의 아래에 붙여 글자와 같은 높이에 둠. single 이면 표시가 둥근 RadioMark 임."""

    def __init__(self, text, single=True):
        super().__init__("")
        row = self.layout()
        text_row = row.itemAt(1).layout()
        old = self.label
        self.label = rich(text)
        text_row.replaceWidget(old, self.label)
        old.hide()
        old.deleteLater()
        square = self.box
        self.mark = QWidget()
        row.replaceWidget(square, self.mark)
        if single:
            self.box = RadioMark()
            square.hide()
            square.deleteLater()
        self.box.refont = lambda: self.box.setFixedSize(20, 20)
        kit.box(self.mark).addWidget(self.box, 0, Qt.AlignmentFlag.AlignBottom)
        self.refont()

    def refont(self):
        self.box.refont()
        self.mark.setFixedSize(20, theme.TYPE["body"][1])

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) \
                and not event.modifiers() & Qt.KeyboardModifier.AltModifier:
            event.accept()  # 보기 목록에 초점이 있으면 ←·→ 로 단계를 넘기지 않음
            return True
        return super().event(event)

    def set_tag(self, text, tone=""):
        self.tag.setText(text)
        kit.set_tone(self.tag, tone)
        self.tag.setVisible(bool(text))


class ChoiceList(QWidget):
    """보기 목록. single 이면 하나만 골라짐. changed 는 표시가 바뀔 때마다 남."""
    changed = pyqtSignal()

    def __init__(self, texts, single=True):
        super().__init__()
        self.single = single
        column = kit.box(self)
        self.rows = []
        for text in texts:
            row = OptionRow(text, single)
            row.box.toggled.connect(lambda on, row=row: self._toggled(row, on))
            column.addWidget(row)
            self.rows.append(row)

    def _toggled(self, row, on):
        if on and self.single:
            for other in self.rows:
                if other is not row:
                    other.box.setChecked(False)
        self.changed.emit()

    def picked(self):
        return [n for n, row in enumerate(self.rows) if row.box.isChecked()]

    def set_enabled(self, enabled):
        for row in self.rows:
            row.box.setEnabled(enabled)
            row.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
            row.setFocusPolicy(Qt.FocusPolicy.StrongFocus if enabled else Qt.FocusPolicy.NoFocus)


class GuessBlock(QWidget):
    """「먼저 풀어 보기」 블록. 보기를 고르는 순간 기록하고 몇 단계에서 답을 확인하는지 알림(채점하지 않음). 이 단계를 떠나기 전까지는
    다른 보기로 바꿀 수 있고 바꿀 때마다 기록함(서비스는 마지막 기록을 씀). 전에 고른 단원을 다시 열면 고른 보기를 보이고 잠금.
    읽기 전용(전체 노트, [노트 보기])이면 고를 수 없게 두고 정답 보기에 "정답" 꼬리표를 닮(정답은 ctx.answers 가 짐작 확인 블록에서 찾음)."""

    def __init__(self, block, ctx):
        super().__init__()
        self.block, self.ctx = block, ctx
        column = kit.box(self, spacing=12)
        column.addWidget(rich(block.get("q", ""), "body", bold=True))
        self.choices = ChoiceList(block.get("options") or [])
        column.addWidget(self.choices)
        self.note = kit.para("", "body", "secondary")
        column.addWidget(self.note)
        if ctx.readonly:
            self.choices.set_enabled(False)
            answer = ctx.answers.get(str(block.get("id")))
            if isinstance(answer, int) and 0 <= answer < len(self.choices.rows):
                self.choices.rows[answer].set_tag("정답", "success")
            self.note.hide()
            return
        picked = block.get("picked")
        self.saved = picked if isinstance(picked, int) and 0 <= picked < len(self.choices.rows) else None
        if self.saved is not None:
            self.choices.rows[self.saved].box.setChecked(True)
        self.choices.set_enabled(self.saved is None)
        self.choices.changed.connect(self.pick)
        self.note.setText(self.later() if self.saved is not None else "")
        self.note.setVisible(self.saved is not None)

    def later(self):
        step = self.block.get("reveal_step")
        return ai_text.GUESS_LATER % step if isinstance(step, int) else ""

    def pick(self):
        picked = self.choices.picked()
        if not picked or picked[0] == self.saved:
            return
        if self.ctx.save_guess(self.block, picked[0]):
            self.saved = picked[0]
        self.note.setText(self.later())
        self.note.setVisible(bool(self.note.text()))


class RevealBlock(QWidget):
    """짐작 확인. 처음 고른 답과 정답을 꼬리표와 함께 한 줄씩 보임. 짐작하지 않았으면 정답만."""

    def __init__(self, block):
        super().__init__()
        options, answer, picked = block.get("options") or [], block.get("answer"), block.get("picked")
        box, column = kit.well(16, 16, 8)
        kit.box(self).addWidget(box)
        column.addWidget(head(ai_text.REVEAL_HEAD))
        if block.get("q"):
            column.addWidget(rich(block["q"], "body", "secondary"))
        if not isinstance(answer, int) or not 0 <= answer < len(options):
            column.addWidget(kit.para(ai_text.BLOCK_BROKEN, "body", "secondary"))
            return
        if isinstance(picked, int) and 0 <= picked < len(options) and picked != answer:
            column.addWidget(self.line("처음 고른 답", "danger", options[picked]))
        column.addWidget(self.line("정답", "success", options[answer]))
        if picked == answer:
            column.addWidget(kit.para("처음에 고른 답이 맞았습니다.", "body", "secondary"))

    @staticmethod
    def line(word, tone, text):
        out = QWidget()
        row = kit.box(out, spacing=12, horizontal=True)
        row.addWidget(kit.badge(word, tone), 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(rich(text), 1)
        return out


class AltPass(QObject):
    """입력 칸이 Alt+←·→ 를 단어 이동으로 가져가지 않게 함(맥의 기본 단축키). 그 키는 단계 넘김 단축키로 감."""

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ShortcutOverride and event.modifiers() & Qt.KeyboardModifier.AltModifier \
                and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            return True
        return False


ALT_PASS = AltPass()


class RecallBlock(QWidget):
    """떠올리기. 빈칸 한 칸과 [확인]. 바로 채점해 맞음·틀림, 정답, 한 줄 까닭을 보임. 틀려도 막지 않고 상자는 움직이지 않음.
    readonly 면 입력 칸 없이 정답을 편 채로 그림."""

    def __init__(self, block, ctx):
        super().__init__()
        self.block, self.ctx = block, ctx
        column = kit.box(self, spacing=12)
        column.addWidget(head(ai_text.RECALL_HEAD))
        column.addWidget(rich(block.get("q", "")))
        self.field = QLineEdit()
        kit.typed(self.field, "body")
        self.field.setPlaceholderText(ai_text.MODE_HINT.get(block.get("mode") or "word", ""))
        self.field.installEventFilter(ALT_PASS)
        self.check_btn = kit.button("확인", "secondary", "l")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.field, 1)
        row.addWidget(self.check_btn)
        self.entry = QWidget()
        self.entry.setLayout(row)
        column.addWidget(self.entry)
        self.empty_note = kit.para(ai_text.RECALL_EMPTY, "body", "secondary")
        column.addWidget(self.empty_note)
        self.empty_note.hide()
        self.result = QWidget()
        result_col = kit.box(self.result, spacing=4)
        self.verdict = kit.badge("")
        verdict_row = QHBoxLayout()
        verdict_row.setContentsMargins(0, 0, 0, 0)
        verdict_row.addWidget(self.verdict)
        verdict_row.addStretch(1)
        result_col.addLayout(verdict_row)
        answers = block.get("answer") or [""]
        result_col.addWidget(rich("정답: `%s`" % answers[0] if block.get("mode") == "code" else "정답: **%s**" % answers[0]))
        if block.get("why"):
            result_col.addWidget(rich(block["why"], "body", "secondary"))
        column.addWidget(self.result)
        self.check_btn.clicked.connect(self.check)
        self.field.returnPressed.connect(self.check)
        self.entry.setVisible(not ctx.readonly)
        self.result.setVisible(ctx.readonly)
        self.verdict.setVisible(not ctx.readonly)

    def check(self):
        """칸이 비면 채점하지 않고 안내만 함(잘못 누른 [확인]이 틀린 기록으로 남지 않게)."""
        if not self.check_btn.isEnabled():
            return
        if not self.field.text().strip():
            self.empty_note.show()
            return
        self.empty_note.hide()
        ok = self.ctx.check_recall(self.block, self.field.text())
        if ok is None:
            return
        self.field.setReadOnly(True)
        self.check_btn.setEnabled(False)
        kit.set_tone(self.field, "success" if ok else "danger")
        self.verdict.setText("맞았습니다" if ok else "틀렸습니다")
        kit.set_tone(self.verdict, "success" if ok else "danger")
        self.result.show()


class WhyBlock(QWidget):
    """왜일까요? 질문 한 줄과 접힌 답. readonly 면 펴 둠."""

    def __init__(self, block, ctx):
        super().__init__()
        column = kit.box(self, spacing=8)
        column.addWidget(head(ai_text.WHY_HEAD))
        column.addWidget(rich(block.get("q", "")))
        self.answer = rich(block.get("a", ""), "body", "secondary")
        self.button = kit.button("답 보기", "secondary", "s")
        self.button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        column.addWidget(self.button)
        column.addWidget(self.answer)
        self.button.clicked.connect(self.toggle)
        self.answer.setVisible(ctx.readonly)
        self.button.setVisible(not ctx.readonly)

    def toggle(self):
        opened = not self.answer.isVisible()
        self.answer.setVisible(opened)
        self.button.setText("답 접기" if opened else "답 보기")


class FoldRow(QFrame):
    """누르면 아래 내용을 펴고 접는 줄. 꺾쇠와 줄바꿈하는 글. 줄 전체를 누르거나 Enter·Space 로 바꾸고, → 는 펴고 ← 는 접음.
    초점이 있으면 ←·→ 를 단계 넘김보다 먼저 받음."""
    toggled = pyqtSignal(bool)

    def __init__(self, text, role="body", bold=False):
        super().__init__()
        self.setObjectName("row")
        self.opened, self.down = False, False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        row = kit.box(self, (0, 12, 0, 12), 12, horizontal=True)
        self.role = role
        self.arrow = Arrow()
        self.arrow.set_opened(False)
        self.mark = QWidget()  # 꺾쇠를 글 첫 줄 글자의 가운데 높이에 두는 칸. px 줄 높이는 넓힌 간격을 글자 위에 두어 아래에 붙임
        kit.box(self.mark).addWidget(self.arrow, 0, Qt.AlignmentFlag.AlignBottom)
        self.label = rich(text, role, bold=bold)
        row.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.label, 1)
        self.refont()

    def refont(self):
        self.mark.setFixedHeight(theme.TYPE[self.role][1])

    def set_opened(self, opened):
        self.opened = opened
        self.arrow.set_opened(opened)
        self.toggled.emit(opened)

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) \
                and not event.modifiers() & Qt.KeyboardModifier.AltModifier:
            event.accept()
            return True
        return super().event(event)

    def mousePressEvent(self, event):
        self.down = event.button() == Qt.MouseButton.LeftButton
        event.accept()

    def mouseReleaseEvent(self, event):
        down, self.down = self.down, False
        if down and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.set_opened(not self.opened)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not event.isAutoRepeat():
                self.set_opened(not self.opened)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.set_opened(key == Qt.Key.Key_Right)
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(theme.qcolor("focus"), 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), theme.RADIUS["small"], theme.RADIUS["small"])


def fold(row, body):
    """row 를 누르면 body 가 펴지고 접히게 이음."""
    row.toggled.connect(body.setVisible)
    body.setVisible(row.opened)
    return row


class MemoBlock(QWidget):
    """외울 것. 질문 줄 목록이고 줄을 누르면 답이 펴짐. opened 면 처음부터 모두 펴 둠([노트 보기])."""

    def __init__(self, items, opened=False):
        super().__init__()
        column = kit.box(self)
        self.rows = []
        for item in items:
            row = FoldRow(item.get("q", ""))
            answer = QWidget()
            kit.box(answer, (kit.MARK + 12, 0, 0, 12)).addWidget(rich(item.get("a", ""), "body", "secondary"))
            column.addWidget(row)
            column.addWidget(answer)
            fold(row, answer)
            if opened:
                row.set_opened(True)
            self.rows.append(row)


class TrendBlock(QWidget):
    """「2026 흐름 · 시험 범위 밖」. 접힌 채로 둠."""

    def __init__(self, block, base_dir):
        super().__init__()
        column = kit.box(self, spacing=8)
        self.row = FoldRow(block.get("title") or ai_text.SCOPE_BADGE["trend"], "label", bold=True)
        body = QWidget()
        body_box = kit.box(body, (kit.MARK + 12, 0, 0, 0))
        self.doc = doc(block.get("text", ""), base_dir, body_box)
        column.addWidget(self.row)
        column.addWidget(body)
        fold(self.row, body)


def guess_answers(steps):
    """{짐작 id: 정답 번호}. 서비스는 먼저 풀어 보기 블록에서 정답을 빼고 주므로 같은 단원의 짐작 확인 블록에서 모음(읽기 전용 화면용)."""
    return {str(b.get("guess")): b["answer"] for step in steps for b in step["blocks"]
            if b.get("kind") == "reveal" and isinstance(b.get("answer"), int)}


class Ctx:
    """블록이 서비스에 남기는 일. readonly 면 기록하지 않고 정답을 편 채로 그림. answers 는 읽기 전용 먼저 풀어 보기의 정답(guess_answers)."""

    def __init__(self, win, lid, key, readonly=False, answers=None):
        self.win, self.lid, self.key, self.readonly = win, lid, key, readonly
        self.answers = answers or {}
        self.base_dir = win.ai.notes[lid]["dir"] if win.ai is not None and lid in win.ai.notes else ""

    def save_guess(self, block, picked):
        if self.readonly:
            return False
        try:
            self.win.ai.save_guess(self.lid, self.key, block.get("id"), picked)
        except SessionError as error:
            self.win.ask("알림", str(error))
            return False
        return True

    def check_recall(self, block, value):
        """채점 결과(bool). 기록하지 못하면 알리고 None."""
        ok = bool(self.win.ai.check_recall(block, value))
        if not self.readonly:
            try:
                self.win.ai.save_recall(self.lid, self.key, block.get("id"), ok)
            except SessionError as error:
                self.win.ask("알림", str(error))
                return None
        return ok


def step_title(step):
    """(꼬리표, 제목). 심화·보충 설명 같은 단계는 꼬리표가 같은 말을 하므로 제목 앞머리를 뺌."""
    badge = ai_text.SCOPE_BADGE.get(step["scope"], "")
    title = step["title"]
    for word in ai_text.SCOPE_HEADS:
        if badge and title.startswith(word):
            title = title[len(word):].lstrip(" :·") or step["title"]
    return badge, title


class StepView(QWidget):
    """단계 하나: 머리(꼬리표와 제목)와 블록들. 글자 크기나 테마가 바뀌면 restyle. title_role 은 제목 글자 역할이고 전체 노트는
    단원 이름(headline)보다 작게 label 굵게를 줌."""

    def __init__(self, step, ctx, extra=(), title_role="headline"):
        super().__init__()
        self.docs, self.figures = [], []
        column = kit.box(self, spacing=24)
        badge, title = step_title(step)
        top = QWidget()
        top_box = kit.box(top, spacing=8)
        if badge:
            tag_row = QHBoxLayout()
            tag_row.setContentsMargins(0, 0, 0, 0)
            tag_row.addWidget(kit.badge(badge, "accent"))
            tag_row.addStretch(1)
            top_box.addLayout(tag_row)
        self.title = kit.para(title, title_role, bold=True if title_role != "headline" else None)
        top_box.addWidget(self.title)
        column.addWidget(top)
        for block in list(step["blocks"]) + list(extra):
            widget = self.block(block, ctx)
            if widget is not None:
                column.addWidget(widget)

    def block(self, block, ctx):
        kind = block.get("kind")
        if block.get("error"):
            return kit.para(ai_text.BLOCK_BROKEN, "body", "secondary")
        if kind == "text":
            out = TextBlock(block["markdown"], ctx.base_dir)
            self.docs += out.docs
            return out
        if kind == "figure":
            out = figure(block)
            if isinstance(out, AiFigure):
                self.figures.append(out)
            return out
        if kind == "guess":
            return GuessBlock(block, ctx)
        if kind == "reveal":
            return RevealBlock(block)
        if kind == "recall":
            return RecallBlock(block, ctx)
        if kind == "why":
            return WhyBlock(block, ctx)
        if kind == "memo":
            return MemoBlock(block.get("items") or [], opened=ctx.readonly)
        if kind == "trend":
            out = TrendBlock(block, ctx.base_dir)
            self.docs.append(out.doc)
            return out
        return kit.para(ai_text.BLOCK_BROKEN, "body", "secondary")  # ai-diff·ai-rotate(다음 PR)와 이 판이 모르는 블록

    def restyle(self):
        for piece in self.docs:
            piece.restyle(theme.web_css())
        for widget in self.figures:
            widget.draw()
        for widget in self.findChildren(RichPara):
            widget.restyle()


def step_dots(steps, index):
    """Stepper 의 (번호, 이름, 상태). 첫 단계가 먼저 풀어 보기면 "먼저", 마지막은 "외울 것", 나머지는 번호만."""
    out = []
    for n, step in enumerate(steps):
        name = ""
        if n == 0 and step["blocks"] and any(b.get("kind") == "guess" for b in step["blocks"]):
            name = "먼저"
        elif n == len(steps) - 1 and step["scope"] == "memo":
            name = "외울 것"
        out.append((n + 1, name, "done" if n < index else ("now" if n == index else "todo")))
    return out


def reading_column(card):
    """카드를 읽는 글의 단(kit.read_width + 48)에 둔 스크롤 칸. (칸, 바깥 상자)."""
    inner = QWidget()
    outer = kit.box(inner, (kit.MARGIN, 24, kit.MARGIN, 32))
    outer.addWidget(kit.column(card, kit.READ_MIN + 48))
    outer.addStretch(1)
    return kit.scroll(inner), outer


class AiLearnPage(QWidget):
    """학습 단원 화면. 위 막대(← N차시 · 단원 제목 · [외울 것으로]), 단계 표시, 가운데 카드 하나에 지금 단계, 아래 막대 [이전]·[다음]."""

    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.setProperty("clipboard", True)
        self.win = win
        self.lid, self.key, self.steps, self.extra, self.index = None, None, [], [], 0
        self.view, self.marked = None, False
        root = kit.box(self)
        self.top = kit.TopBar("← AI 비전 개론", "", steps=True)
        self.back_btn, self.title = self.top.back, self.top.title
        self.memo_btn = self.top.add_right(kit.button("외울 것으로", "text", "s"), flush=True)
        self.memo_btn.setToolTip("수업에서 들은 단원은 마지막 단계의 외울 것부터 떠올려 볼 수 있습니다.")
        root.addWidget(self.top)
        stepper_frame = kit.frame("stepper")
        stepper_frame.setFixedHeight(theme.CONTROL["stepper"])
        self.stepper = kit.Stepper()
        kit.box(stepper_frame, (kit.MARGIN, 0, kit.MARGIN, 0), horizontal=True).addWidget(self.stepper)
        root.addWidget(stepper_frame)
        self.card, self.card_box = kit.card(24, 0)
        self.scroll, _ = reading_column(self.card)
        root.addWidget(self.scroll, 1)
        self.bar = kit.BottomBar()
        self.prev_btn = self.bar.add_action(kit.button("이전", "secondary", "l"))
        self.next_btn = self.bar.add_action(kit.button("다음", "primary", "l"))
        self.prev_btn.setToolTip("← 키로도 넘깁니다. 입력 칸이나 그림을 고른 동안에는 Alt+←")
        self.next_btn.setToolTip("→ 키로도 넘깁니다. 입력 칸이나 그림을 고른 동안에는 Alt+→")
        root.addWidget(self.bar)
        self.shortcuts = []
        for keys, step in STEP_KEYS:  # 창 단축키라 이 화면이 보일 때만 받음. 입력 칸·그림·목록은 ShortcutOverride 로 ←·→ 를 먼저 가져감
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(lambda step=step: self.move(step))
            self.shortcuts.append(shortcut)
        self.back_btn.clicked.connect(lambda: self.win.open_ai_lesson(self.lid))
        self.memo_btn.clicked.connect(lambda: self.show_step(len(self.steps) - 1))
        self.prev_btn.clicked.connect(lambda: self.move(-1))
        self.next_btn.clicked.connect(self.forward)

    def load(self, lid, key, step=None):
        """단원을 올림. step 은 1부터의 단계 번호. 없으면 지난번 자리(마지막 단계였으면 처음)부터. 없는 단원이면 AiError."""
        data = self.win.ai.unit_steps(lid, key)
        read = any(unit["key"] == key and unit["read"] for unit in self.win.ai.lesson(lid)["units"])
        self.lid, self.key, self.marked = lid, key, read  # 이미 읽은 단원은 다시 끝까지 보아도 읽기 기록을 또 남기지 않음
        self.back_btn.setText("← %d차시" % self.win.ai.lessons[lid]["no"])
        self.title.setText(data["title"])
        self.title.show()
        self.read(data)
        last = len(self.steps)
        at = step or data.get("at_step") or 1
        if step is None and at >= last:
            at = 1
        self.show_step(max(1, min(last, at)) - 1)

    def read(self, data):
        """서비스의 단계에서 2026 흐름 단계를 빼서 마지막 단계 끝에 접힌 블록으로 붙임(단계 번호에 넣지 않음)."""
        self.steps = [s for s in data["steps"] if s["scope"] != "trend"]
        self.extra = [{"kind": "trend", "title": s["title"], "text": "\n\n".join(b.get("markdown", "") for b in s["blocks"]
                                                                                  if b.get("kind") == "text")}
                      for s in data["steps"] if s["scope"] == "trend"]

    def show_step(self, index):
        """index 번 단계를 그림. 짐작 확인이 방금 고른 답을 보이게 단계를 새로 읽음."""
        try:
            self.read(self.win.ai.unit_steps(self.lid, self.key))
        except SessionError as error:
            self.win.ask("알림", str(error))
            return
        self.index = index = max(0, min(index, len(self.steps) - 1))
        if self.view is not None:
            self.card_box.removeWidget(self.view)
            self.view.hide()
            self.view.deleteLater()
        last = index == len(self.steps) - 1
        self.view = StepView(self.steps[index], Ctx(self.win, self.lid, self.key), self.extra if last else ())
        self.card_box.addWidget(self.view)
        self.stepper.set_steps(step_dots(self.steps, index))
        self.stepper.setToolTip("\n".join("%d %s" % (n + 1, s["title"]) for n, s in enumerate(self.steps)))
        self.prev_btn.setEnabled(index > 0)
        self.next_btn.setText("연습 시작" if last else "다음")
        self.memo_btn.setVisible(not last)
        self.win.ai.save_step(self.lid, self.key, index + 1)
        if last and not self.marked:
            self.mark_read()
        self.scroll.verticalScrollBar().setValue(0)
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(0))  # 새 단계의 조각이 자리를 잡은 뒤에도 맨 위
        self.setFocus()  # 지운 단계의 부품이 갖던 초점이 새 단계의 첫 줄로 넘어가 초점 테두리가 그려지지 않게 화면이 받음

    def mark_read(self):
        try:
            self.win.ai.mark_read(self.lid, self.key)
        except SessionError as error:
            self.win.ask("알림", str(error))
            return
        self.marked = True

    def move(self, step):
        if not self.steps or not self.isVisible():
            return
        target = self.index + step
        if 0 <= target < len(self.steps):
            self.show_step(target)

    def forward(self):
        if self.index == len(self.steps) - 1:
            self.win.open_ai_practice("unit", lesson=self.lid, unit=self.key)
        else:
            self.move(1)

    def fit_column(self):
        self.card.setMaximumWidth(kit.read_width(self.width()) + 48)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_column()

    def set_busy(self, busy, text=""):
        for widget in (self.back_btn, self.memo_btn, self.prev_btn, self.next_btn):
            widget.setEnabled(not busy)
        if not busy:
            self.prev_btn.setEnabled(self.index > 0)

    def restyle(self):
        self.fit_column()
        if self.view is not None:
            self.view.restyle()
        self.stepper.update()


class RevisitPage(QWidget):
    """다시 보기(설계 2.5). 덜 외운 단원 하나의 중심 그림과 외울 것 질문(가린 꼴). [연습 시작]은 그 단원 문항을 앞에 둔 섞어 풀기."""

    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.setProperty("clipboard", True)
        self.win = win
        self.data, self.memo = None, None
        root = kit.box(self)
        self.top = kit.TopBar("← AI 비전 개론", "")
        self.back_btn, self.title = self.top.back, self.top.title
        root.addWidget(self.top)
        self.card, self.card_box = kit.card(24, 24)
        self.scroll, _ = reading_column(self.card)
        root.addWidget(self.scroll, 1)
        self.bar = kit.BottomBar()
        self.skip_btn = self.bar.add_action(kit.button("건너뛰기", "secondary", "l"))
        self.start_btn = self.bar.add_action(kit.button("연습 시작", "primary", "l"))
        self.skip_btn.setToolTip("이 단원은 오늘 다시 권하지 않고 홈으로 갑니다.")
        root.addWidget(self.bar)
        self.figure = None
        self.back_btn.clicked.connect(lambda: self.win.go_ai())
        self.skip_btn.clicked.connect(lambda: self.leave(False))
        self.start_btn.clicked.connect(lambda: self.leave(True))

    def load(self):
        data = self.win.ai.revisit()
        if data is None:
            raise SessionError("다시 볼 단원이 없습니다. 단원을 하나 읽은 뒤 열어 보세요.")
        self.data = data
        no = self.win.ai.lessons[data["lesson"]]["no"]
        self.title.setText("%d차시 · %s" % (no, data["title"]))
        self.title.show()
        while self.card_box.count():
            widget = self.card_box.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.figure = None
        if data["figure"]:
            try:
                self.figure = AiFigure(data["figure"], last=True)
            except OSError:
                self.card_box.addWidget(missing_figure(data["figure"]))
            else:
                self.card_box.addWidget(self.figure)
        intro = QWidget()
        kit.box(intro, spacing=4).addWidget(kit.label("외울 것", "headline"))
        intro.layout().addWidget(kit.para(ai_text.MEMO_HINT, "body", "secondary"))
        self.card_box.addWidget(intro)
        self.memo = MemoBlock(data["memo"])
        self.card_box.addWidget(self.memo)
        self.scroll.verticalScrollBar().setValue(0)
        self.setFocus()

    def leave(self, start):
        data = self.data
        try:
            self.win.ai.save_revisit(data["lesson"], data["unit"])
        except SessionError as error:
            self.win.ask("알림", str(error))
            return
        if start:
            self.win.open_ai_practice("mixed", lesson=data["lesson"], unit=data["unit"])
        else:
            self.win.go_ai()

    def fit_column(self):
        self.card.setMaximumWidth(kit.read_width(self.width()) + 48)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_column()

    def set_busy(self, busy, text=""):
        for widget in (self.back_btn, self.skip_btn, self.start_btn):
            widget.setEnabled(not busy)

    def restyle(self):
        self.fit_column()
        if self.figure is not None:
            self.figure.draw()
        for widget in self.findChildren(RichPara):
            widget.restyle()


class AiNotePage(QWidget):
    """차시의 [전체 노트]와 [외울 것]. 단원마다 접고 펴는 묶음이고, 전체 노트는 단원을 펼 때 단계를 그림(정답을 편 읽기 전용).
    외울 것은 단원을 모두 펴 두고 답은 가린 채로 두며, 맨 위에 자주 틀리는 문항을 둠."""

    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.setProperty("clipboard", True)
        self.win = win
        self.lid, self.only_memo, self.views = None, False, []
        root = kit.box(self)
        self.top = kit.TopBar("← AI 비전 개론", "")
        self.back_btn, self.title = self.top.back, self.top.title
        root.addWidget(self.top)
        self.card, self.card_box = kit.card(24, 8)
        self.scroll, _ = reading_column(self.card)
        root.addWidget(self.scroll, 1)
        self.back_btn.clicked.connect(lambda: self.win.open_ai_lesson(self.lid))

    def load(self, lid, only_memo=False):
        data = self.win.ai.note(lid, only_memo)
        self.lid, self.only_memo, self.views = lid, only_memo, []
        no = self.win.ai.lessons[lid]["no"]
        self.back_btn.setText("← %d차시" % no)
        self.title.setText("%d차시 %s" % (no, "외울 것" if only_memo else "전체 노트"))
        self.title.show()
        while self.card_box.count():
            item = self.card_box.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        if only_memo:
            self.card_box.addWidget(kit.para(ai_text.MEMO_HINT, "body", "secondary"))
            if data["leeches"]:
                self.card_box.addWidget(self.leeches(data["leeches"]))
        for unit in data["units"]:
            if not unit["steps"]:
                continue
            row = FoldRow(unit["title"], "headline", bold=True)  # 펼친 단계 제목(label 굵게)보다 크게 둬 단원 경계가 보이게 함
            body = QWidget()
            body_box = kit.box(body, (kit.MARK + 12, 0, 0, 24), 24)
            if only_memo:
                for step in unit["steps"]:
                    for block in step["blocks"]:
                        body_box.addWidget(MemoBlock(block.get("items") or []))
            else:
                row.toggled.connect(lambda on, unit=unit, body_box=body_box: on and self.fill(unit, body_box))
            self.card_box.addWidget(row)
            self.card_box.addWidget(body)
            fold(row, body)
            row.set_opened(only_memo)
        self.scroll.verticalScrollBar().setValue(0)
        self.setFocus()

    def leeches(self, cards):
        box, column = kit.well(16, 16, 8)
        column.addWidget(kit.label(ai_text.LEECH_HEAD, "label", bold=True))
        column.addWidget(kit.para(ai_text.LEECH_ABOUT, "body", "secondary"))
        for cid in cards:
            try:
                card = self.win.ai.card_info(cid)
            except SessionError:
                continue
            text = card["stmt"]["text"] if card["kind"] == "stmt" else (card.get("item") or {}).get("stem", "")
            first = next((line for line in text.split("\n") if line.strip() and not bank.FENCE.match(line)), "")
            column.addWidget(rich("· " + first))
        return box

    def fill(self, unit, body_box):
        """전체 노트의 단원을 처음 펼 때 단계를 그림."""
        if body_box.count():
            return
        ctx = Ctx(self.win, self.lid, unit["key"], readonly=True, answers=guess_answers(unit["steps"]))
        for step in unit["steps"]:
            if step["scope"] == "trend":
                continue
            view = StepView(step, ctx, title_role="label")
            body_box.addWidget(view)
            self.views.append(view)

    def fit_column(self):
        self.card.setMaximumWidth(kit.read_width(self.width()) + 48)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_column()

    def set_busy(self, busy, text=""):
        self.back_btn.setEnabled(not busy)

    def restyle(self):
        self.fit_column()
        for view in self.views:
            view.restyle()
        for widget in self.findChildren(RichPara):
            widget.restyle()


class NoteDialog(QDialog):
    """연습 화면 [노트 보기]: 문항의 근거 단계 하나를 정답을 편 읽기 전용으로 보여 줌. 블록은 기록을 남기지 않음."""

    def __init__(self, win, lid, where):
        super().__init__(win)
        kit.page(self)
        self.setProperty("clipboard", True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        key, _, no = str(where or "").partition("/")
        data = win.ai.unit_steps(lid, key)
        steps = [s for s in data["steps"] if s["scope"] != "trend"]
        step = next((s for s in steps if str(s["no"]) == no), steps[0] if steps else None)
        self.setWindowTitle("%d차시 · %s" % (win.ai.lessons[lid]["no"], data["title"]))
        box = kit.box(self, (24, 24, 24, 24), 16)
        box.addWidget(kit.para(self.windowTitle(), "caption", "secondary"))
        self.view = StepView(step, Ctx(win, lid, key, readonly=True, answers=guess_answers(data["steps"]))) if step \
            else kit.para(ai_text.BLOCK_BROKEN)
        holder = QWidget()
        holder_box = kit.box(holder, (0, 0, 16, 0))
        holder_box.addWidget(self.view)
        holder_box.addStretch(1)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(holder)
        scroll.viewport().setAutoFillBackground(False)
        holder.setAutoFillBackground(False)
        box.addWidget(scroll, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.close_btn = kit.button("닫기", "secondary", "l")
        self.close_btn.clicked.connect(self.close)
        row.addWidget(self.close_btn)
        box.addLayout(row)
        room = win.geometry()
        self.resize(min(kit.READ_MIN + 96, room.width() - 40), max(320, room.height() - 80))
