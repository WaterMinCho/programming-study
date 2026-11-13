# -*- coding: utf-8 -*-
"""AI 비전 개론 학습 단원 화면(AiLearnPage), 다시 보기 화면(RevisitPage), 차시의 전체 노트·외울 것 화면(AiNotePage), 연습 화면의
[노트 보기] 대화상자(NoteDialog)와 그 안의 부품. 연습 화면과 같이 쓰는 코드 부품(빈칸 코드 CodeSlots, 코드 보기 CodeChoices)도 둠.

한 화면에 단계 하나를 보임. 단계(StepView)는 서비스가 나눠 준 블록을 위에서 아래로 쌓음: 글은 docview.Doc(그 안의 > **[정정]**,
> **[보충 설명]** 인용은 꼬리표를 단 상자로 뺌), 그림은 AiFigure, ai-guess·ai-reveal·ai-recall·ai-why·ai-diff·ai-rotate·ai-memo·ai-trend·
ai-levels 는 아래의 블록 위젯. 서비스가 error 를 단 블록과 모르는 블록은 안내 글만 둠. 상황별 코드 단원(차시가 아닌 무리)은 위 막대가
홈으로 돌아감.

AiFigure 는 GIF 를 처음 열면 한 번 재생하고 마지막 장에서 멈추며, 지금 장의 `프레임:` 설명을 그림 바로 아래에 두어 장을 넘길 때 같이 바꿈. 설명 칸은 가장 긴 장
설명의 높이를 지켜서 장을 넘겨도 넘김 단추가 움직이지 않음. 그림에 초점이 있으면 ←·→ 가 장을 넘김. 단계 이동은 아래 막대와 ←·→ 이고,
입력 칸·그림·외울 것 줄에 초점이 있으면 그쪽이 ←·→ 를 쓰므로 Alt+←·→ 로만 넘김.
마지막 단계를 보인 순간 단원을 읽은 것으로 기록하고, 단계를 옮길 때마다 중간 자리를 로컬에 남김. 읽기 화면이라 복사를 막지 않음."""
import html
import re

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QKeySequence, QPainter, QPen, QShortcut
from PyQt6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

import mdlite
from aiprep import bank, skel
from aiprep.grade import BLANK
from gui import motion, ai_text, kit, theme
from gui.docview import Doc, FigureView, TextPiece
from gui.widgets import AnswerLine, Para
from gui.wrong_page import Arrow
from session import SessionError

BOX_LINE = re.compile(r"^\s*>\s?\*\*\[(정정|보충 설명)\]\*\*\s*")
WIDE = 16777215  # Qt 위젯 크기의 상한. Doc 의 최대 폭(640)을 풀어 카드 폭을 따르게 함
STEP_KEYS = (("Left", -1), ("Right", 1), ("Alt+Left", -1), ("Alt+Right", 1))
SLOT_CHARS = 8  # 코드 칸의 처음 폭(코드 글자 수). 적는 만큼 넓어짐
READ_WIDTH = 1200  # 기본 학습 본문의 폭. 작은 창에서는 바깥 스크롤 칸의 가용 폭을 따름
CARD_PAD = 32
READ_ROLES = {"body": "learn_body", "label": "learn_body", "caption": "learn_caption", "headline": "learn_heading"}


def reading_width(window_width):
    """학습 본문을 1200~1600px까지 넓히고 창의 바깥 여백을 남김."""
    return max(READ_WIDTH, min(1600, window_width - 2 * kit.MARGIN - 2 * CARD_PAD))


def learning_texts(root):
    """학습 내용의 글·입력에 읽기용 크기를 줌. 위아래 작업 막대의 단추 크기는 별도로 둠."""
    for widget in [root] + root.findChildren(QWidget):
        current = widget.property("role")
        role = READ_ROLES.get(current, current if current in READ_ROLES.values() else None)
        if role and isinstance(widget, (QLabel, QLineEdit)):
            widget.ensurePolished()
            kit.typed(widget, role, widget.property("bold"))
            if isinstance(widget, Para):
                widget.line = theme.TYPE[role][1]
                widget.setText(widget.text())
            elif isinstance(widget, QLineEdit):
                widget.setMinimumHeight(theme.TYPE[role][1] + 24)


def reading_heading(title, description):
    """학습 제목과 설명 사이에 읽기용 간격을 적용함."""
    group = kit.heading(title, description)
    group.layout().setSpacing(theme.LEARN_GAP["title_description"])
    return group


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
            elif kind == "mark":
                out.append('<span style="background-color: %s; color: %s; font-weight: 700;">%s</span>' %
                           (theme.color("highlight_bg"), theme.color("highlight_ink"), render(value)))
            elif kind == "underline":
                out.append("<u>%s</u>" % render(value))
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
    role = READ_ROLES.get(role, role)
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
    out.css = theme.learning_css()
    out.box.setSpacing(theme.LEARN_GAP["paragraph"])
    out.setMaximumWidth(WIDE)
    layout.addWidget(out)
    out.set_markdown(markdown, base_dir, "python")
    return out


def head(text):
    """블록 머리의 작은 이름(떠올리기, 왜일까요?)."""
    return kit.para(text, "learn_activity", bold=True)


class TextBlock(QWidget):
    """단계 글 한 덩이. 정정·보충 설명 인용은 꼬리표를 단 회색 상자로 그림."""

    def __init__(self, markdown, base_dir):
        super().__init__()
        self.docs = []
        column = kit.box(self, spacing=theme.LEARN_GAP["paragraph"])
        for part in split_boxes(markdown):
            if part[0] == "text":
                self.docs.append(doc(part[1], base_dir, column))
                continue
            if part[1] == "정정":
                self.docs.append(doc(part[2], base_dir, column))
                continue
            word, tone = ai_text.BOXES[part[1]]
            box, inner = kit.well(24, 24, theme.LEARN_GAP["detail"])
            tag_row = QHBoxLayout()
            tag_row.setContentsMargins(0, 0, 0, 0)
            tag_row.addWidget(kit.badge(word, tone))
            tag_row.addStretch(1)
            inner.addLayout(tag_row)
            column.addWidget(box)
            self.docs.append(doc(part[2], base_dir, inner))


class AiFigure(FigureView):
    """학습 단원 그림. 처음 열면 한 번 재생하고 마지막 장에서 멈춤. frames 는 figure 블록의 `프레임:` 줄([{"text", "ms"}])이고 지금 장의
    설명을 그림 바로 아래(넘김 줄 위)에 가운데 맞춰 둠. 설명 칸의 최소 높이는 지금 폭에서 가장 긴 장 설명의 높이라 장마다 설명 줄 수가
    달라도 넘김 줄과 캡션이 제자리에 있음. 넘김 단추는 단계 넘김 [이전]·[다음]과 헷갈리지 않게 [이전 장]·[다음 장]으로 씀.
    초점이 있으면 ←·→ 가 장을 넘기고(Alt 가 붙으면 단계 넘김으로 보냄) 그림 둘레에 초점 테두리를 그림. last 면 마지막 장에서 엶."""

    def __init__(self, path, caption="", frames=(), last=False, description=""):
        details = [description] if description else []
        details.extend("%d. %s" % (n + 1, frame["text"]) for n, frame in enumerate(frames or []) if frame.get("text"))
        super().__init__(path, caption, autoplay=False, frame_changed=self.show_frame, description="\n\n".join(details))
        self.frames = list(frames or [])
        self.start_last = last
        self.autoplay_pending = not last
        self.held = None  # 설명 칸 높이를 잰 폭·실제 글꼴·줄 높이
        self.frame_text = rich("", "body", "secondary")
        self.frame_text.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.layout().insertWidget(self.layout().indexOf(self.picture) + 1, self.frame_text)
        if self.movie:
            self.prev_btn.setText("이전 장")
            self.next_btn.setText("다음 장")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if self.movie and self.count > 1 else Qt.FocusPolicy.NoFocus)
        if last and self.movie:
            self.go(self.count - 1)
        self.show_frame(self.frame())
        learning_texts(self)
        self.draw()

    def show_frame(self, number):
        self.frame_text.setText(self.frames[number]["text"] if number < len(self.frames) else "")
        self.frame_text.setVisible(self.available and any(frame.get("text") for frame in self.frames))

    def display_scale(self):
        largest = theme.scaled_type(theme.TEXT_STEPS[-1])["learn_body"][0]
        return largest / theme.TYPE["learn_body"][0] / 1.5

    def display_width(self):
        """글자가 커지면 그림도 키우며 최대 글자에서 가용 폭과 원본 1.5배 상한까지 씀."""
        largest = theme.scaled_type(theme.TEXT_STEPS[-1])["learn_body"][0]
        text_scale = theme.TYPE["learn_body"][0] / largest
        return min(max(1, self.width()), self.source.width() * 1.5) * text_scale

    def zoom_scale(self):
        return min(1, self.display_scale())

    def reload(self):
        loaded = super().reload()
        if loaded and self.movie:
            learning_texts(self)
            self.refont()
            self.prev_btn.setText("이전 장")
            self.next_btn.setText("다음 장")
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if self.count > 1 else Qt.FocusPolicy.NoFocus)
            if self.start_last:
                self.go(self.count - 1)
            self.draw()
        return loaded

    def hold_frames(self):
        """설명 칸의 최소 높이를 지금 폭에서 가장 긴 장 설명의 높이로 둠. 폭이나 글자 크기가 바뀔 때만 다시 잼(장을 넘길 때마다 draw 가 불림)."""
        width = self.width()
        self.frame_text.ensurePolished()
        key = (width, self.frame_text.font().toString(), self.frame_text.line)
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

    def _play_if_visible(self):
        if not motion.enabled:
            return
        if not self.isVisible() or not self.visibleRegion().intersects(self.picture.geometry()):
            self.autoplay_pending = True
            return
        self.play()

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
        if self.autoplay_pending and self.movie and self.count > 1 and self.visibleRegion().intersects(self.picture.geometry()):
            self.autoplay_pending = False
            if motion.enabled:
                QTimer.singleShot(0, self._play_if_visible)
        pixmap = self.picture.pixmap()
        if self.hasFocus() and pixmap is not None and not pixmap.isNull():
            size = pixmap.deviceIndependentSize()
            place = self.picture.geometry()
            rect = QRectF(QPointF(place.x() + (place.width() - size.width()) / 2, place.y() + (place.height() - size.height()) / 2), size)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(theme.qcolor("focus"), 2))
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), theme.RADIUS["control"], theme.RADIUS["control"])


def figure(block, last=False):
    """figure 블록의 그림. 읽지 못하면 캡션·대체 내용·장별 설명과 재시도를 보임."""
    out = AiFigure(block["path"], block.get("caption", ""), block.get("frames"), last=last,
                   description=block.get("content", ""))
    out.error_box.setToolTip(block.get("file") or block["path"])
    return out


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
        super().__init__("", text_widget=rich(text), mark_widget=RadioMark() if single else kit.CheckMark())
        self.mark = self.content_line.mark_holder
        self.box.refont = lambda: self.box.setFixedSize(20, 20)
        self.refont()

    def refont(self):
        self.box.refont()
        self.text_line.refont()
        self.content_line.refont()

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


# 코드 부품(연습 화면과 학습 단원이 같이 씀)

def code_font():
    """코드 상자의 글꼴. 연습 문항의 빈칸 코드와 같은 크기(글자 단계를 따라감)."""
    return theme.code_font(theme.TYPE["learn_code"][0] - theme.CODE_PX)


class Slot(AnswerLine):
    """코드 줄 안의 빈칸. 높이는 theme.slot_height(), 폭은 SLOT_CHARS 자에서 시작해 적은 글만큼 넓어짐. 폭은 자리표시 글(hint)도 담음.
    답한 뒤 자리표시를 지워도 폭이 그대로라 뒤 코드가 움직이지 않음."""

    def __init__(self, font, hint=""):
        super().__init__()
        self.setProperty("slot", True)
        self.setProperty("learning", True)
        self.hint = hint
        self.setFont(font)
        self.setPlaceholderText(hint)
        self.setToolTip(hint)
        self.textChanged.connect(self.fit)
        self.fit()

    def fit(self):
        metrics = QFontMetricsF(self.font())
        least = metrics.horizontalAdvance("M" * SLOT_CHARS)
        want = max(least, metrics.horizontalAdvance(self.text() + "MM"), metrics.horizontalAdvance(self.hint + "M"))
        self.setFixedWidth(int(want) + 16)


class CodeSlots(QFrame):
    """빈칸이 든 코드 블록. 줄마다 코드 글꼴 QLabel 과 Slot 을 가로로 놓고 줄은 바꾸지 않으며, 넘치면 가로로 스크롤함.
    marks 는 칸마다 앞에 붙일 번호 글자(빈칸이 하나면 빈 글). result 는 답한 뒤 코드 아래에 칸마다 맞고 틀림을 쓰는 줄이고
    부른 쪽이 카드에 놓음. 빈칸이 없는 코드도 같은 모양으로 그림(돌려 가며 빈칸의 읽기 전용 판)."""

    def __init__(self, code, hints, marks):
        super().__init__()
        self.setObjectName("well")
        self.code, self.hints, self.marks = code, list(hints), list(marks)
        self.fields, self.lines = [], []
        self.result = rich("", "body")
        outer = kit.box(self, (16, 12, 16, 12))
        self.area = QScrollArea()
        self.area.setProperty("flat", True)
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.area.setWidgetResizable(True)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.inner.setAutoFillBackground(False)
        self.area.setWidget(self.inner)
        self.area.viewport().setAutoFillBackground(False)
        outer.addWidget(self.area)
        self.build()

    def build(self):
        font = code_font()
        column = kit.box(self.inner)
        count = 0
        for line in self.code.split("\n"):
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(0)
            pieces = BLANK.split(line)
            for n, piece in enumerate(pieces):
                if piece:
                    label = QLabel(piece)
                    label.setTextFormat(Qt.TextFormat.PlainText)
                    label.setFont(font)
                    row.addWidget(label)
                if n < len(pieces) - 1:
                    mark = self.marks[count] if count < len(self.marks) else ""
                    if mark:
                        row.addWidget(kit.label(mark, "label", bold=True))  # 코드 밖 칸 번호와 같은 크기
                    hint = self.hints[count] if count < len(self.hints) else ""
                    slot = Slot(font, hint)
                    row.addWidget(slot)
                    self.fields.append(slot)
                    count += 1
            row.addStretch(1)
            holder.setFixedHeight(theme.learning_slot_height() if len(pieces) > 1 else theme.TYPE["learn_code"][1])
            column.addWidget(holder)
            self.lines.append(holder)
        self.fit()

    def fit(self):
        """줄 높이의 합에 가로 스크롤 막대가 필요하면 그 높이를 더함."""
        height = sum(line.maximumHeight() for line in self.lines)
        wide = self.inner.sizeHint().width() > max(1, self.area.viewport().width())
        self.area.setFixedHeight(height + (self.area.horizontalScrollBar().sizeHint().height() if wide else 0))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def restyle(self):
        """글자 크기 단계가 바뀐 뒤 코드 글꼴, 칸 폭, 줄 높이를 다시 잡음."""
        font = code_font()
        for label in self.inner.findChildren(QLabel):
            if label.property("role") is None:
                label.setFont(font)
        for field in self.fields:
            field.setFont(font)
            field.fit()
        self.result.restyle()
        for line in self.lines:
            line.setFixedHeight(theme.learning_slot_height() if line.findChild(Slot) else theme.TYPE["learn_code"][1])
        self.fit()


class CodeLines(QFrame):
    """여러 줄 코드 상자(코드 보기 하나). 줄마다 코드 글꼴 QLabel 이고 줄은 바꾸지 않음. 줄 높이는 지금 단계의 코드 줄 높이."""
    PAD = 12  # 위아래 안쪽 여백. 보기 표시를 첫 줄 가운데에 둘 때 씀

    def __init__(self, text):
        super().__init__()
        self.setObjectName("well")
        self.labels = []
        column = kit.box(self, (16, self.PAD, 16, self.PAD))
        for line in str(text).split("\n"):
            label = QLabel(line)
            label.setTextFormat(Qt.TextFormat.PlainText)
            column.addWidget(label)
            self.labels.append(label)
        self.refont()

    def refont(self):
        font = code_font()
        for label in self.labels:
            label.setFont(font)
            label.setFixedHeight(theme.TYPE["learn_code"][1])


class CodeOptionRow(OptionRow):
    """코드 보기 한 줄. OptionRow 의 글 자리에 CodeLines 를 두고 꼬리표(정답·내 답)는 코드 아래에 둠. 꼬리표를 옆에 두면 2×2 보기에서
    코드 폭이 줄어서임. 표시(둥근 점·체크 상자)는 코드 첫 줄의 가운데 높이."""

    def __init__(self, text, single=True):
        super().__init__("", single)
        self.content_line.text_box.removeWidget(self.text_line)
        self.label.hide()
        self.label = self.code = CodeLines(text)
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        column.addWidget(self.code)
        column.addWidget(self.tag, 0, Qt.AlignmentFlag.AlignLeft)
        self.text_line.hide()
        self.text_line.deleteLater()
        self.content_line.text = content
        self.content_line.anchor = lambda: CodeLines.PAD + theme.TYPE["learn_code"][1] / 2
        self.content_line.text_box.addWidget(content, 0, Qt.AlignmentFlag.AlignTop)
        self.refont()

    def refont(self):
        self.box.refont()
        if hasattr(self, "code"):
            self.content_line.refont()


class CodeChoices(ChoiceList):
    """코드 보기 목록(뼈대 카드의 순서 고르기·맞는 줄·고칠 줄). 보기마다 CodeOptionRow 이고 grid 가 2 면 2×2 로 둠. 연습 화면이 보기
    아래에 풀이를 쓰는 칸(whys, 처음에는 숨김)을 보기마다 하나씩 둠. ChoiceList 와 같은 rows·picked()·set_enabled()·changed."""

    def __init__(self, texts, single=True, grid=1):
        super().__init__([], single)
        self.whys = []
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(8)
        self.layout().addLayout(layout)
        columns = 2 if grid == 2 else 1
        for n, text in enumerate(texts):
            row = CodeOptionRow(text, single)
            row.box.toggled.connect(lambda on, row=row: self._toggled(row, on))
            why = QWidget()
            kit.box(why, (kit.MARK + 12, 0, 0, 8)).addWidget(rich("", "body", "secondary"))
            cell = QWidget()
            cell_box = kit.box(cell)
            cell_box.addWidget(row)
            cell_box.addWidget(why)
            cell_box.addStretch(1)
            why.hide()
            layout.addWidget(cell, n // columns, n % columns)
            self.rows.append(row)
            self.whys.append(why)
        for n in range(columns):
            layout.setColumnStretch(n, 1)


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
        return kit.FirstLine(kit.badge(word, tone), rich(text))


class AltPass(QObject):
    """입력 칸이 Alt+←·→ 를 단어 이동으로 가져가지 않게 함(맥의 기본 단축키). 그 키는 단계 넘김 단축키로 감."""

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ShortcutOverride and event.modifiers() & Qt.KeyboardModifier.AltModifier \
                and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            return True
        return False


ALT_PASS = AltPass()


class RecallBlock(QFrame):
    """떠올리기. 빈칸 한 칸과 [확인]. 바로 채점해 맞음·틀림, 정답, 한 줄 까닭을 보임. 틀려도 막지 않고 상자는 움직이지 않음.
    readonly 면 입력 칸 없이 정답을 편 채로 그림. title 은 머리 글이고 세 수준 블록의 확인 물음이 바꿔 씀."""

    def __init__(self, block, ctx, title=ai_text.RECALL_HEAD):
        super().__init__()
        self.setObjectName("learning_activity")
        self.block, self.ctx = block, ctx
        column = kit.box(self, (32, 32, 32, 32), spacing=24)
        column.addWidget(head(title))
        column.addWidget(rich(block.get("q", "")))
        self.field = AnswerLine()
        kit.typed(self.field, "learn_body")
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
            result_col.addWidget(rich(ai_text.teaching_text(block["why"]), "body", "secondary"))
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
        font = self.field.font()
        self.field.setReadOnly(True)
        self.check_btn.setEnabled(False)
        kit.set_tone(self.field, "success" if ok else "danger")
        self.field.setFont(font)
        self.verdict.setText("맞았습니다" if ok else "틀렸습니다")
        kit.set_tone(self.verdict, "success" if ok else "danger")
        self.result.show()


class DiffLine(QWidget):
    """나란히 보기의 한 행. texts 는 칸마다 코드 줄(없는 쪽은 None). 다른 줄(changed)이면 notice_bg 바탕을 칠하고 같은 줄은 글자를
    secondary 색으로 흐리게 둠. 칸 글은 줄을 바꾸지 않고, 칸의 최소 폭을 잡지 않아 블록이 좁아지면 DiffBlock 이 판을 쌓음."""

    def __init__(self, texts, changed, pad, gap):
        super().__init__()
        self.changed = changed
        row = kit.box(self, (pad, 0, pad, 0), gap, horizontal=True)
        self.cells = []
        for text in texts:
            cell = QLabel(text or "")
            cell.setTextFormat(Qt.TextFormat.PlainText)
            cell.setFont(code_font())
            cell.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            if not changed:
                cell.setProperty("tone", "secondary")
            row.addWidget(cell, 1)
            self.cells.append(cell)
        self.setFixedHeight(theme.TYPE["learn_code"][1])  # 같은 줄의 코드가 겹치지 않게 학습 코드 줄 높이를 사용함

    def paintEvent(self, event):
        if self.changed:
            painter = QPainter(self)
            painter.fillRect(self.rect(), theme.qcolor("notice_bg"))
            painter.end()


class DiffBlock(QWidget):
    """나란히 보기(ai-diff, 설계 3.7.2). 위 caption "다른 줄 2개 · 같은 줄 13개", 아래 코드 상자. 두 판 각각의 가장 긴 줄이 지금 코드
    글꼴로 반 폭 열에 들어가면 두 열(열 머리는 판 이름), 아니면 왼쪽 판 다음 오른쪽 판을 위아래로 쌓음. 다른 줄은 notice_bg 바탕,
    같은 줄은 흐린 글자이고 줄은 바꾸지 않음. 코드 글자는 줄이지 않음(작은 글자를 사용자가 지적함). 폭이나 글자 단계가 바뀌면 다시
    정함. 블록은 Doc 밖에 있어 카드 폭을 다 씀. 기록하지 않아 읽기 전용 화면에서도 같은 모양."""
    PAD = 12  # 상자 안 좌우 여백
    GAP = 24  # 두 열 사이

    def __init__(self, block):
        super().__init__()
        self.block, self.rows = block, list(block.get("rows") or [])
        self.two, self.lines = None, []
        column = kit.box(self, spacing=8)
        column.addWidget(kit.label(ai_text.diff_caption(block.get("different", 0), block.get("same", 0)), "caption", "secondary"))
        self.table, self.table_box = kit.well(0, 8, 0)
        column.addWidget(self.table)
        self.build(False)  # 폭을 알기 전에는 쌓은 표. 처음 폭이 정해지면 resizeEvent 가 다시 정함

    def need(self):
        """두 열에서 한 열이 담아야 하는 코드 폭(px). 두 판 가운데 가장 긴 줄."""
        metrics = QFontMetricsF(code_font())
        texts = [row[side] for row in self.rows for side in ("left", "right") if row.get(side)]
        return max([metrics.horizontalAdvance(text) for text in texts] or [0])

    def fits(self, width):
        """width 폭의 상자에서 두 열이 되는지."""
        return (width - 2 * self.PAD - self.GAP) / 2.0 >= self.need()

    def build(self, two):
        """두 열(two)이나 위아래로 쌓은 표를 새로 그림."""
        self.two = two
        while self.table_box.count():
            widget = self.table_box.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.lines = []
        left, right = self.block.get("left", ""), self.block.get("right", "")
        if two:
            self.table_box.addWidget(self.heads([left, right]))
            for row in self.rows:
                self.add(DiffLine([row.get("left"), row.get("right")], not row.get("same"), self.PAD, self.GAP))
            return
        for n, (side, name) in enumerate((("left", left), ("right", right))):
            self.table_box.addWidget(self.heads([name], top=8 if n else 0))
            for row in self.rows:
                if row.get(side) is not None:
                    self.add(DiffLine([row[side]], not row.get("same"), self.PAD, self.GAP))

    def heads(self, names, top=0):
        out = QWidget()
        row = kit.box(out, (self.PAD, top, self.PAD, 4), self.GAP, horizontal=True)
        for name in names:
            head_label = kit.label(name, "caption", "secondary", bold=True)
            head_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            row.addWidget(head_label, 1)
        return out

    def add(self, line):
        self.table_box.addWidget(line)
        self.lines.append(line)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        two = self.fits(self.width())
        if two != self.two:
            self.build(two)

    def restyle(self):
        """글자 단계가 바뀌면 코드 폭과 줄 높이가 바뀌므로 지금 폭으로 다시 그림."""
        self.build(self.fits(self.width()) if self.width() > 1 else False)


class RotateBlock(QWidget):
    """돌려 가며 빈칸(ai-rotate, 설계 3.7.1). 판 코드에서 한 번에 한 자리를 가린 CodeSlots 와 [확인]. 답하면 맞음·틀림과 정답을
    보이고 정답 아래에 같은 자리의 해설을 붙임. [다음 자리]로 넘어가면 해설을 비움. 순서는 skel.rotate_next(틀린 자리는 세 자리 뒤에
    다시)이고 채점과 기록은 ctx.check_rotate(상자는 움직이지 않음). 모든 자리를 맞히면 판 코드 전체와 끝 문구를 보임.
    칸에서 Enter 는 [확인], 답한 뒤에는 [다음 자리].
    readonly(전체 노트, [노트 보기])면 판 코드와 가리는 자리 목록만 그리고 채점하지 않음."""

    def __init__(self, block, ctx):
        super().__init__()
        self.block, self.ctx = block, ctx
        spots = block.get("slots") or []
        self.spots = {spot["id"]: spot for spot in spots}
        self.queue, self.pos, self.result_ok = [spot["id"] for spot in spots], 0, None
        self.slots = None
        column = kit.box(self, spacing=12)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(head(ai_text.ROTATE_HEAD))
        top.addStretch(1)
        self.count = kit.label("", "caption", "secondary")
        top.addWidget(self.count)
        column.addLayout(top)
        self.holder = QWidget()
        self.holder_box = kit.box(self.holder)
        column.addWidget(self.holder)
        if ctx.readonly:
            self.count.hide()
            self.put(CodeSlots(block.get("code", ""), [], []))
            column.addWidget(kit.para(ai_text.ROTATE_SLOTS % " · ".join(spot["token"] for spot in spots), "body", "secondary"))
            return
        self.check_btn = kit.button("확인", "secondary", "l")
        self.next_btn = kit.button(ai_text.NEXT_SLOT, "text", "l")
        self.verdict = kit.badge("")
        self.answer = rich("")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        row.addWidget(self.check_btn)
        self.answer_line = kit.FirstLine(self.verdict, self.answer)
        row.addWidget(self.answer_line, 1, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.next_btn)
        self.buttons = QWidget()
        self.buttons.setLayout(row)
        column.addWidget(self.buttons)
        self.explanation = rich("", "body", "secondary")
        column.addWidget(self.explanation)
        self.explanation.hide()
        self.empty_note = kit.para(ai_text.RECALL_EMPTY, "body", "secondary")
        column.addWidget(self.empty_note)
        self.done = kit.para(ai_text.ROTATE_DONE, "body", "success")
        column.addWidget(self.done)
        self.empty_note.hide()
        self.done.hide()
        self.check_btn.clicked.connect(self.check)
        self.next_btn.clicked.connect(self.advance)
        if self.queue:
            self.show_slot()
        else:
            self.finish()

    def put(self, slots):
        """코드 상자를 바꿈."""
        if self.slots is not None:
            self.holder_box.removeWidget(self.slots)
            self.slots.hide()
            self.slots.deleteLater()
        self.slots = slots
        self.holder_box.addWidget(slots)

    def field(self):
        return self.slots.fields[0] if self.slots is not None and self.slots.fields else None

    def show_slot(self, focus=False):
        """지금 자리만 가린 코드를 그림. focus 면 칸에 초점을 둠([다음 자리]로 넘어올 때)."""
        spot = self.spots[self.queue[self.pos]]
        self.put(CodeSlots(spot["code"], [spot.get("hint") or ai_text.MODE_HINT.get(spot.get("mode") or "code", "")], [""]))
        field = self.field()
        field.installEventFilter(ALT_PASS)
        field.returnPressed.connect(self.enter)
        self.result_ok = None
        self.count.setText("%d / %d" % (self.pos + 1, len(self.queue)))
        self.check_btn.show()
        self.next_btn.hide()
        self.verdict.hide()
        self.answer.hide()
        self.explanation.setText("")
        self.explanation.hide()
        self.empty_note.hide()
        if focus:
            field.setFocus(Qt.FocusReason.OtherFocusReason)

    def enter(self):
        if self.result_ok is None:
            self.check()
        else:
            self.advance()

    def check(self):
        """칸이 비면 채점하지 않고 안내만 함. 채점하지 못하면(ctx 가 알림) 그대로 둠."""
        field = self.field()
        if field is None or self.result_ok is not None:
            return
        if not field.text().strip():
            self.empty_note.show()
            return
        self.empty_note.hide()
        got = self.ctx.check_rotate(self.block, self.queue[self.pos], field.text())
        if got is None:
            return
        ok = self.result_ok = bool(got["ok"])
        font = field.font()
        field.setReadOnly(True)
        kit.set_tone(field, "success" if ok else "danger")
        field.setFont(font)
        self.verdict.setText("맞았습니다" if ok else "틀렸습니다")
        kit.set_tone(self.verdict, "success" if ok else "danger")
        self.answer.setText("정답: `%s`" % got["answer"])
        self.check_btn.hide()
        for widget in (self.verdict, self.answer, self.next_btn):
            widget.show()
        self.explanation.setText(got.get("explain") or "")
        self.explanation.setVisible(bool(self.explanation.text()))

    def advance(self):
        """[다음 자리]. 틀린 자리는 세 자리 뒤에 다시 넣고 남은 자리가 없으면 끝."""
        if self.result_ok is None:
            return
        self.queue, self.pos = skel.rotate_next(self.queue, self.pos, self.result_ok)
        if self.pos >= len(self.queue):
            self.finish()
        else:
            self.show_slot(focus=True)

    def finish(self):
        self.put(CodeSlots(self.block.get("code", ""), [], []))
        self.count.setText("")
        self.buttons.hide()
        self.explanation.setText("")
        self.explanation.hide()
        self.empty_note.hide()
        self.done.show()

    def restyle(self):
        if self.slots is not None:
            self.slots.restyle()


class WhyBlock(QFrame):
    """왜일까요? 질문 한 줄과 접힌 답. readonly 면 펴 둠."""

    def __init__(self, block, ctx):
        super().__init__()
        self.setObjectName("learning_activity")
        column = kit.box(self, (32, 32, 32, 32), spacing=24)
        column.addWidget(head(ai_text.WHY_HEAD))
        column.addWidget(rich(block.get("q", "")))
        self.answer = rich(block.get("a", ""), "body", "secondary")
        self.button = kit.button("답 보기", "secondary", "l")
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
        self.role = READ_ROLES.get(role, role)
        self.arrow = Arrow()
        self.arrow.set_opened(False)
        self.label = rich(text, role, bold=bold)
        self.pair = kit.FirstLine(self.arrow, self.label)
        self.mark = self.pair.mark_holder
        row.addWidget(self.pair, 1)
        self.refont()

    def refont(self):
        self.pair.refont()

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


class Sheet(QWidget):
    """회색 칸(well) 안에 두는 흰 칸. 단추와 입력 칸이 단계 본문과 같은 바탕에 놓여 회색 바탕의 보조 단추가 바탕에 묻히지 않음.
    색은 그릴 때마다 테마에서 읽어 테마를 바꿔도 따라감."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor("surface"))
        painter.drawRoundedRect(QRectF(self.rect()), theme.RADIUS["control"], theme.RADIUS["control"])


class LevelsBlock(QWidget):
    """「세 수준으로 다시 보기」. 회색 칸 안의 접힌 줄 하나이고 처음 펼 때 한 번만 수준 셋을 그림(접힌 동안 안이 비어 있음). 수준마다
    흰 칸(Sheet) 하나에 머리 줄, 그림, 글(20살은 끝에 코드), 20살의 자주 하는 착각과 다루는 곳, 확인 물음. 확인 물음은
    떠올리기(RecallBlock)를 그대로 쓰고 Ctx 가 수준을 같이 기록함. readonly 면 확인 물음이 정답과 까닭을 편 채로 그려짐.
    docs·figures 는 restyle 때 다시 그릴 부품."""

    reloading = pyqtSignal()

    def __init__(self, block, ctx):
        super().__init__()
        self.block, self.ctx = block, ctx
        self.docs, self.figures = [], []
        box, inner = kit.well(24, 24, theme.LEARN_GAP["detail"])
        kit.box(self).addWidget(box)
        concept = block.get("concept") or ""
        self.row = FoldRow("%s · %s" % (ai_text.LEVELS_HEAD, concept) if concept else ai_text.LEVELS_HEAD, "label", bold=True)
        self.body = QWidget()
        self.body_box = kit.box(self.body, (0, 24, 0, 0), theme.LEARN_GAP["group"])
        inner.addWidget(self.row)
        self.deep_dialog = None
        self.deep_btn = kit.button("심화 설명", "secondary", "l")
        self.deep_btn.setToolTip("그림과 코드로 이 개념의 심화 설명을 별도 창에서 봅니다.")
        self.deep_btn.clicked.connect(self.open_deep)
        inner.addWidget(self.body)
        inner.addWidget(self.deep_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.deep_btn.setVisible(any(level.get("level") == 20 for level in block.get("levels") or []))
        self.row.toggled.connect(lambda on: on and self.build())
        fold(self.row, self.body)

    def build(self):
        if self.body_box.count():
            return
        for level in self.block.get("levels") or []:
            part = Sheet()
            self.body_box.addWidget(part)  # 붙인 뒤에 채움. 부모 없는 글 조각이 잠깐 따로 창으로 뜨지 않게 함
            self.fill(part, level)
        for image in self.body.findChildren(FigureView):
            image.reloading.connect(self.reloading)
        last = self.row  # 펼 때 만든 부품은 창 초점 순서 끝에 붙으므로 접힌 줄 바로 뒤로 옮김
        for widget in self.body.findChildren(QWidget):
            if widget.focusPolicy().value & Qt.FocusPolicy.TabFocus.value:
                QWidget.setTabOrder(last, widget)
                last = widget

    def open_deep(self):
        if self.deep_dialog is None:
            level = next((v for v in self.block.get("levels") or [] if v.get("level") == 20), None)
            if level is None:
                return
            dialog = self.deep_dialog = QDialog(self)
            kit.page(dialog)
            dialog.setModal(True)
            title = (self.block.get("concept") or "개념") + " 심화 설명"
            dialog.setWindowTitle(title)
            outer = kit.box(dialog, (24, 24, 24, 24), theme.GAP["group"])
            outer.addWidget(kit.para(title, "headline"))
            holder = QWidget()
            content = kit.box(holder)
            part = Sheet()
            content.addWidget(part)
            content.addStretch(1)
            self.fill(part, level, check=False)
            self.deep_scroll = kit.scroll(holder)
            outer.addWidget(self.deep_scroll, 1)
            self.deep_close = kit.button("닫기", "secondary", "l")
            self.deep_close.clicked.connect(dialog.close)
            outer.addWidget(self.deep_close, 0, Qt.AlignmentFlag.AlignRight)
            dialog.finished.connect(lambda _: self.deep_btn.setFocus(Qt.FocusReason.OtherFocusReason))
        self.restyle()
        owner, dialog = self.ctx.win, self.deep_dialog
        screen = owner.screen().availableGeometry()
        dialog.resize(max(320, min(1000, owner.width()-40, screen.width()-48)),
                      max(320, min(owner.height()-80, screen.height()-80)))
        def place():
            frame = dialog.frameGeometry()
            frame.moveCenter(owner.frameGeometry().center())
            dialog.move(max(screen.left(), min(frame.left(), screen.right()-frame.width()+1)),
                        max(screen.top(), min(frame.top(), screen.bottom()-frame.height()+1)))
        place()
        dialog.show()
        place()

    def fill(self, part, level, check=True):
        column = kit.box(part, (32, 32, 32, 32), theme.LEARN_GAP["group"])
        if check:
            column.addWidget(kit.heading(kit.para(ai_text.LEVEL_NAMES.get(level.get("level"), ""), "learn_activity", bold=True),
                                        kit.para(ai_text.LEVEL_DESCRIPTIONS.get(level.get("level"), ""), "learn_caption", "secondary")))
        if level.get("figure"):
            picture = figure(level["figure"])
            column.addWidget(picture)
            if isinstance(picture, AiFigure):
                self.figures.append(picture)
        text = level.get("text") or ""
        if level.get("code"):
            text += "\n\n```python\n%s\n```" % level["code"]
        if text.strip():
            self.docs.append(doc(text, self.ctx.base_dir, column))
        if level.get("mistake"):
            note = QWidget()
            note_box = kit.box(note, spacing=4)
            note_box.addWidget(head(ai_text.LEVEL_MISTAKE))
            note_box.addWidget(rich(level['mistake']))
            column.addWidget(note)
        if check:
            column.addWidget(RecallBlock(level, self.ctx, ai_text.LEVEL_CHECK))
        learning_texts(part)

    def restyle(self):
        for piece in self.docs:
            piece.restyle(theme.learning_css())
        for widget in self.figures:
            widget.draw()


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
        """채점 결과(bool). 기록하지 못하면 알리고 None. 세 수준 블록의 확인 물음이면 block 의 level 을 같이 기록함."""
        ok = bool(self.win.ai.check_recall(block, value))
        if not self.readonly:
            try:
                self.win.ai.save_recall(self.lid, self.key, block.get("id"), ok, level=block.get("level"), value=value, block=block)
            except SessionError as error:
                self.win.ask("알림", str(error))
                return None
        return ok

    def check_rotate(self, block, slot, value):
        """돌려 가며 빈칸 한 자리의 채점 {"ok", "answer"}. 서비스가 채점과 기록을 같이 하고 readonly 면 기록하지 않음. 실패하면 알리고
        None."""
        try:
            return self.win.ai.check_rotate(self.lid, self.key, block.get("id"), slot, value, readonly=self.readonly)
        except SessionError as error:
            self.win.ask("알림", str(error))
            return None


def step_title(step):
    """(꼬리표, 제목). 심화·보충 설명 같은 단계는 꼬리표가 같은 말을 하므로 제목 앞머리를 뺌."""
    badge = ai_text.SCOPE_BADGE.get(step["scope"], "")
    title = step["title"]
    if step["scope"] == "memo" and title.startswith("외울 것"):
        title = "복습 질문" + title[len("외울 것"):]
    for word in ai_text.SCOPE_HEADS:
        if badge and title.startswith(word):
            title = title[len(word):].lstrip(" :·") or step["title"]
    return badge, title


class StepView(QWidget):
    """단계 하나: 머리(꼬리표와 제목)와 블록들. 글자 크기나 테마가 바뀌면 restyle. title_role 은 제목 글자 역할이고 전체 노트는
    단원 이름(headline)보다 작게 label 굵게를 줌."""

    reloading = pyqtSignal()

    def __init__(self, step, ctx, extra=(), title_role="headline"):
        super().__init__()
        self.docs, self.figures, self.codes = [], [], []  # codes 는 글자 단계를 따라 다시 그릴 코드 블록(나란히 보기, 돌려 가며 빈칸)
        self.formulas = []  # 수식 창의 글자와 색을 갱신할 부품
        self.levels = []  # 세 수준 블록. 펼 때 만든 글 조각과 그림을 restyle 때 다시 그림
        column = kit.box(self, spacing=theme.LEARN_GAP["group"])
        if not ctx.readonly:
            from gui.learning_context import LearningContext, unit_context
            root = getattr(ctx.win.ai, "root", None)
            context = unit_context(root, ctx.key) if root else None
            if context is not None:
                self.context = LearningContext(*context, reflect=step["scope"] == "memo",
                                               expanded=step["no"] == 1 or step["scope"] == "memo")
                self.context.reloading.connect(self.reloading)
                column.addWidget(self.context)
        badge, title = step_title(step)
        top = QWidget()
        top_box = kit.box(top, spacing=theme.LEARN_GAP["detail"])
        if badge:
            tag_row = QHBoxLayout()
            tag_row.setContentsMargins(0, 0, 0, 0)
            tag_row.addWidget(kit.badge(badge, "accent"))
            tag_row.addStretch(1)
            top_box.addLayout(tag_row)
        self.title = kit.para(title, READ_ROLES.get(title_role, title_role), bold=True if title_role != "headline" else None)
        top_box.addWidget(self.title)
        content = []
        for index, block in enumerate(list(step["blocks"]) + list(extra)):
            widget = self.block(block, ctx)
            if widget is not None:
                if index == 0 and block.get("kind") == "text":
                    top = reading_heading(top, widget)
                else:
                    content.append(widget)
        column.addWidget(top)
        for widget in content:
            column.addWidget(widget)
        learning_texts(self)
        for image in self.findChildren(FigureView):
            image.reloading.connect(self.reloading)
        for level in self.levels:
            level.reloading.connect(self.reloading)

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
        if kind in ("diff", "rotate"):
            out = DiffBlock(block) if kind == "diff" else RotateBlock(block, ctx)
            self.codes.append(out)
            return out
        if kind == "memo":
            return MemoBlock(block.get("items") or [], opened=ctx.readonly)
        if kind == "trend":
            out = TrendBlock(block, ctx.base_dir)
            self.docs.append(out.doc)
            return out
        if kind == "levels":
            out = LevelsBlock(block, ctx)
            self.levels.append(out)
            return out
        if kind == "formula":
            from gui.ai_formula import FormulaBlock
            out = FormulaBlock(block, ctx)
            self.formulas.append(out)
            return out
        return kit.para(ai_text.BLOCK_BROKEN, "body", "secondary")  # 이 판이 모르는 블록

    def restyle(self):
        for piece in self.docs:
            piece.restyle(theme.learning_css())
        for widget in self.figures:
            widget.draw()
        for widget in self.codes + self.levels + self.formulas:
            widget.restyle()
        for widget in self.findChildren(RichPara):
            widget.restyle()


def step_dots(steps, index):
    """Stepper 의 (번호, 이름, 상태). 첫 물음은 먼저, 마지막은 복습 질문으로 표시함."""
    out = []
    for n, step in enumerate(steps):
        name = ""
        if n == 0 and step["blocks"] and any(b.get("kind") == "guess" for b in step["blocks"]):
            name = "먼저"
        elif n == len(steps) - 1 and step["scope"] == "memo":
            name = "복습 질문"
        out.append((n + 1, name, "done" if n < index else ("now" if n == index else "todo")))
    return out


def reading_column(card):
    """카드를 읽기용 폭과 안쪽 여백에 둔 스크롤 칸. (칸, 바깥 상자)."""
    inner = QWidget()
    outer = kit.box(inner, (kit.MARGIN, 32, kit.MARGIN, 48))
    outer.addWidget(kit.column(card, READ_WIDTH + 2 * CARD_PAD))
    outer.addStretch(1)
    return kit.scroll(inner), outer


def _step_content(value):
    """짐작의 고른 번호만 뺀 내용 판. 공개 답은 새 서비스 값으로 그리고 입력 초안은 같은 내용에서만 복원함."""
    if isinstance(value, dict):
        return tuple((key, _step_content(part)) for key, part in sorted(value.items())
                     if key != "picked" or value.get("kind") not in ("guess", "reveal"))
    if isinstance(value, list):
        return tuple(_step_content(part) for part in value)
    return value


def _view_path(widget, root):
    """중첩된 같은 id의 입력도 구별하는 부모별 같은 종류의 자식 순서. 지운 위젯을 보관하지 않음."""
    path = []
    while widget is not root:
        if widget is None or widget.parentWidget() is None:
            return None
        parent = widget.parentWidget()
        kind = type(widget).__name__
        children = [child for child in parent.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
                    if type(child).__name__ == kind]
        path.append((kind, children.index(widget)))
        widget = parent
    return tuple(reversed(path))


def _view_widget(root, path):
    if path is None:
        return None
    for kind, index in path:
        children = [child for child in root.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
                    if type(child).__name__ == kind]
        if index >= len(children):
            return None
        root = children[index]
    return root


class AiLearnPage(QWidget):
    """학습 단원 화면. 위 막대(← N차시 · 단원 제목 · [복습 질문]), 단계 표시, 가운데 카드 하나에 지금 단계, 아래 막대 [이전]·[다음].
    상황별 코드 단원은 차시 화면이 없어 위 막대가 "← AI 비전 개론" 이고 홈으로 돌아감(서비스 place 의 back)."""
    position_restored = pyqtSignal()

    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.setProperty("clipboard", True)
        self.win = win
        self.lid, self.key, self.steps, self.extra, self.index = None, None, [], [], 0
        self.view, self.marked, self.back = None, False, "lesson"
        self.view_states, self.view_key, self.state_unit = {}, None, None
        self.pending_position = None
        self.position_geometry = None
        self.position_timer = QTimer(self)
        self.position_timer.setSingleShot(True)
        self.position_timer.timeout.connect(self.restore_position)
        root = kit.box(self)
        self.top = kit.TopBar("← AI 비전 개론", "", steps=True)
        self.back_btn, self.title = self.top.back, self.top.title
        self.memo_btn = self.top.add_right(kit.button("복습 질문", "text", "s"), flush=True)
        self.memo_btn.setToolTip("이 단원의 복습 질문으로 이동합니다. 답을 생각한 뒤 펼쳐 확인하세요.")
        self.memo_btn.setAccessibleDescription(self.memo_btn.toolTip())
        root.addWidget(self.top)
        stepper_frame = kit.frame("stepper")
        stepper_frame.setFixedHeight(theme.CONTROL["stepper"])
        self.stepper = kit.Stepper()
        kit.box(stepper_frame, (kit.MARGIN, 0, kit.MARGIN, 0), horizontal=True).addWidget(self.stepper)
        root.addWidget(stepper_frame)
        self.card, self.card_box = kit.card(CARD_PAD, 0)
        self.scroll, _ = reading_column(self.card)
        self.scroll.viewport().installEventFilter(self)
        self.scroll.widget().installEventFilter(self)
        self.scroll.verticalScrollBar().rangeChanged.connect(self.position_changed)
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
        self.back_btn.clicked.connect(self.go_back)
        self.memo_btn.clicked.connect(lambda: self.show_step(len(self.steps) - 1))
        self.prev_btn.clicked.connect(lambda: self.move(-1))
        self.next_btn.clicked.connect(self.forward)

    def load(self, lid, key, step=None):
        """단원을 올림. step이 없으면 마지막 단계도 저장한 자리부터 엶."""
        data = self.win.ai.unit_steps(lid, key)
        read = any(unit["key"] == key and unit["read"] for unit in self.win.ai.lesson(lid)["units"])
        place = self.win.ai.place(lid)
        unit = (self.win.ai, lid, key)
        if self.state_unit != unit:
            self.clear_view_state(unit)
        self.lid, self.key, self.marked = lid, key, read  # 이미 읽은 단원은 다시 끝까지 보아도 읽기 기록을 또 남기지 않음
        self.back = place["back"]
        # 차시 단원은 "← 5차시" 가 자리를 말하고, 상황별 코드 단원은 홈으로 돌아가므로 제목이 단원 이름("학습 루프 · …") 전체를 씀
        self.back_btn.setText("← %s" % (place["label"] if self.back == "lesson" else ai_text.TRACK))
        self.title.setText(data["title"] if self.back == "lesson" else data["name"])
        self.title.show()
        self.read(data)
        last = len(self.steps)
        at = step or data.get("at_step") or 1
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
        unit = (self.win.ai, self.lid, self.key)
        if self.state_unit != unit:
            self.clear_view_state(unit)
        self.remember_view()
        self.position_timer.stop()
        self.pending_position = None
        self.index = index = max(0, min(index, len(self.steps) - 1))
        last = index == len(self.steps) - 1
        extra = self.extra if last else ()
        number = self.steps[index]["no"]
        content = _step_content([self.steps[index], list(extra)])
        saved = self.view_states.get(number)
        state = saved[1] if saved is not None and saved[0] == content else None
        self.view_states.pop(number, None)
        self.setFocus()  # 지운 입력 칸의 초점이 새 단계 첫 부품으로 넘어가지 않게 함
        if self.view is not None:
            self.view.removeEventFilter(self)
            self.card_box.removeWidget(self.view)
            self.view.hide()
            self.view.deleteLater()
        self.view = StepView(self.steps[index], Ctx(self.win, self.lid, self.key), extra)
        self.view.installEventFilter(self)
        self.view.reloading.connect(self.hold_reading)
        self.view_key = number, content
        self.card_box.addWidget(self.view)
        learning_texts(self.view)  # 부모의 스타일이 적용된 뒤에도 읽기용 실제 글꼴을 유지함
        if state is not None:
            self.restore_fields(state)
        self.stepper.set_steps(step_dots(self.steps, index))
        self.stepper.setToolTip("\n".join("%d %s" % (n + 1, s["title"]) for n, s in enumerate(self.steps)))
        self.prev_btn.setEnabled(index > 0)
        self.next_btn.setText("연습 시작" if last else "다음")
        self.memo_btn.setVisible(not last)
        self.win.ai.save_step(self.lid, self.key, index + 1)
        if state is not None:
            self.queue_position(state["anchor"], state["focus"])
        else:
            self.queue_position(None)

    def clear_view_state(self, unit):
        """단원이나 서비스가 바뀌면 화면 상태와 대기 중 복원을 버림."""
        self.position_timer.stop()
        self.pending_position = None
        self.view_states, self.view_key, self.state_unit = {}, None, unit

    def remember_view(self):
        if self.view is None or self.view_key is None:
            return
        focus = _view_path(self.window().focusWidget(), self.view)
        anchor = self.reading_position()
        if self.pending_position is not None and self.pending_position[0] is self.view:
            _, anchor, pending_focus = self.pending_position
            if self.window().focusWidget() is self:
                focus = pending_focus
        state = {"anchor": anchor, "focus": focus, "fields": {}, "figures": {}, "levels": {}, "contexts": {}}
        from gui.learning_context import LearningContext
        for block in self.view.findChildren(LearningContext):
            state["contexts"][_view_path(block, self.view)] = (
                block.flow_btn.isChecked(), block.toggle.isChecked() if hasattr(block, "toggle") else False)
        for block in self.view.findChildren(LevelsBlock):
            if block.body_box.count():
                state["levels"][_view_path(block, self.view)] = block.row.opened
        for block in self.view.findChildren(RecallBlock):
            field = block.field
            if not field.isReadOnly():
                state["fields"][_view_path(block, self.view)] = (field.text(), field.cursorPosition(),
                                                               field.selectionStart(), field.selectionLength())
        for figure in self.view.findChildren(AiFigure):
            state["figures"][_view_path(figure, self.view)] = figure.frame()
        number, content = self.view_key
        self.view_states[number] = content, state

    def restore_fields(self, state):
        """접힌 중첩 카드의 칸도 만든 뒤 초안만 복원함. 채점·읽음 기록을 남기지 않음."""
        from gui.learning_context import LearningContext
        for path, (diagram, answer) in state.get("contexts", {}).items():
            block = _view_widget(self.view, path)
            if isinstance(block, LearningContext):
                block.flow_btn.setChecked(diagram)
                if hasattr(block, "toggle"):
                    block.toggle.setChecked(answer)
        for path, opened in sorted(state["levels"].items()):
            block = _view_widget(self.view, path)
            if isinstance(block, LevelsBlock):
                block.build()
                block.row.set_opened(opened)
        for path, entry in state["fields"].items():
            block = _view_widget(self.view, path)
            if isinstance(block, RecallBlock):
                text, cursor, start, length = entry
                block.field.setText(text)
                if start >= 0:
                    block.field.setSelection(start + length if cursor == start else start, -length if cursor == start else length)
                else:
                    block.field.setCursorPosition(cursor)
        for path, frame in state["figures"].items():
            figure = _view_widget(self.view, path)
            if isinstance(figure, AiFigure) and figure.movie:
                figure.go(frame)

    def reading_position(self, viewport_height=None):
        """읽던 글 조각과 그 안의 상대 위치. 줄바꿈으로 높이가 달라져도 옛 절대 스크롤 값을 쓰지 않음."""
        value = self.scroll.verticalScrollBar().value()
        pieces = self.view.findChildren(TextPiece) + self.view.findChildren(RichPara) + self.view.findChildren(AiFigure)
        visible = [(piece, piece.mapTo(self.scroll.widget(), QPoint()).y()) for piece in pieces
                   if piece.window() is self.window() and piece.isVisibleTo(self.view)]
        inside = [(piece, top) for piece, top in visible if top <= value < top + piece.height()]
        if inside:
            piece, top = min(inside, key=lambda item: item[0].height())
        elif visible:
            piece, top = min(visible, key=lambda item: abs(item[1] - value))
        else:
            piece, top = self.view, self.view.mapTo(self.scroll.widget(), QPoint()).y()
        focus = self.window().focusWidget()
        visible_focus = None
        if isinstance(focus, QLineEdit) and self.view.isAncestorOf(focus):
            y = focus.mapTo(self.scroll.viewport(), QPoint()).y()
            height = self.scroll.viewport().height() if viewport_height is None else viewport_height
            if y < height and y + focus.height() > 0:
                visible_focus = _view_path(focus, self.view)
        return _view_path(piece, self.view), (value - top) / max(1, piece.height()), visible_focus

    def queue_position(self, anchor, focus=None):
        """창에 딸린 타이머 하나만 씀. 빠르게 단계를 바꿔도 예전 단계의 복원이 남지 않음."""
        self.position_timer.stop()
        self.pending_position = self.view, anchor, focus
        self.position_geometry = None
        self.position_timer.start(0)

    def hold_reading(self, viewport_height=None):
        if self.view is not None and self.view_key is not None and self.pending_position is None:
            self.queue_position(self.reading_position(viewport_height))

    def restore_position(self):
        pending = self.pending_position
        if pending is None or pending[0] is not self.view:
            return
        _, anchor, focus = pending
        inner = self.scroll.widget()
        widgets = [self.view] + [widget for widget in self.view.findChildren(QWidget) if widget.window() is self.window()]
        for widget in reversed(widgets):
            if widget.layout() is not None:
                widget.layout().activate()
        inner.layout().activate()
        self.card_box.activate()
        if anchor is not None and inner.height() < inner.minimumSizeHint().height():
            return  # 글 조각의 높이가 전해진 뒤 Resize·rangeChanged에서 다시 부름
        target = _view_widget(self.view, focus)
        field = _view_widget(self.view, anchor[2]) if anchor is not None else None
        piece = _view_widget(self.view, anchor[0]) if anchor is not None else None
        geometry = (inner.size(), inner.minimumSizeHint(), self.view.size(), self.scroll.viewport().size(),
                    piece.mapTo(inner, QPoint()).y() if piece is not None else None,
                    piece.height() if piece is not None else None,
                    target.mapTo(inner, QPoint()).y() if target is not None else None,
                    field.mapTo(inner, QPoint()).y() if field is not None else None,
                    self.scroll.verticalScrollBar().maximum())
        if geometry != self.position_geometry:
            self.position_geometry = geometry
            self.position_timer.start(0)  # 중첩 글의 줄바꿈이 다음 배치 요청에 전해질 때까지 복원 기준을 보관함
            return
        self.pending_position = None
        self.position_geometry = None
        if target is not None and self.isVisible() and self.window().focusWidget() is self:
            target.setFocus(Qt.FocusReason.OtherFocusReason)
        value = piece.mapTo(inner, QPoint()).y() + round(anchor[1] * piece.height()) if piece is not None else 0
        self.scroll.verticalScrollBar().setValue(value)
        if isinstance(field, QLineEdit) and field.hasFocus():
            viewport = self.scroll.viewport()
            top = field.mapTo(viewport, QPoint()).y()
            bar = self.scroll.verticalScrollBar()
            bottom = top + field.height() + 16 - viewport.height()
            if bottom > 0:
                bar.setValue(bar.value() + bottom)
            elif top < 16:
                bar.setValue(bar.value() + top - 16)  # 입력 칸 전체가 보이게 실제 좌표로 맞춤
        self.position_restored.emit()

    def position_changed(self, *_):
        if self.pending_position is not None:
            self.position_geometry = None
            self.position_timer.start(0)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            if watched is self.scroll.viewport():
                self.hold_reading(event.oldSize().height())
            self.position_changed()
        elif event.type() == QEvent.Type.LayoutRequest:
            if watched is self.view:
                self.hold_reading()  # 자식 글 높이가 부모 배치에 반영되기 전에 읽던 위치를 보관함
            self.position_changed()
        return super().eventFilter(watched, event)

    def hideEvent(self, event):
        self.remember_view()
        self.position_timer.stop()
        self.pending_position = None
        super().hideEvent(event)

    def go_back(self):
        if self.back == "lesson":
            self.win.open_ai_lesson(self.lid)
        else:
            self.win.go_ai()

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
            if not self.marked:
                self.mark_read()
                if not self.marked:
                    return
            self.win.open_ai_practice("unit", lesson=self.lid, unit=self.key)
        else:
            self.move(1)

    def fit_column(self):
        self.card.setMaximumWidth(reading_width(self.width()) + 2 * CARD_PAD)

    def resizeEvent(self, event):
        self.hold_reading()
        super().resizeEvent(event)
        self.fit_column()

    def set_busy(self, busy, text=""):
        for widget in (self.back_btn, self.memo_btn, self.prev_btn, self.next_btn):
            widget.setEnabled(not busy)
        if not busy:
            self.prev_btn.setEnabled(self.index > 0)

    def restyle(self):
        self.hold_reading()
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
        self.card, self.card_box = kit.card(CARD_PAD, 32)
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
        self.title.setText(data["name"])
        self.title.show()
        while self.card_box.count():
            widget = self.card_box.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.figure = None
        if data["figure"]:
            self.figure = figure(data.get("figure_info") or {"path": data["figure"]}, last=True)
            self.card_box.addWidget(self.figure)
        intro = reading_heading(kit.label("복습 질문", "learn_heading"), rich(ai_text.MEMO_HINT, "body", "secondary"))
        self.card_box.addWidget(intro)
        self.memo = MemoBlock(data["memo"])
        self.card_box.addWidget(self.memo)
        learning_texts(self.card)
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
        self.card.setMaximumWidth(reading_width(self.width()) + 2 * CARD_PAD)

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
    """차시의 [전체 노트]와 [복습 질문]. 단원마다 접고 펴는 묶음이고, 전체 노트는 단원을 펼 때 단계를 그림(정답을 편 읽기 전용).
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
        self.card, self.card_box = kit.card(CARD_PAD, 16)
        self.scroll, _ = reading_column(self.card)
        root.addWidget(self.scroll, 1)
        self.back_btn.clicked.connect(lambda: self.win.open_ai_lesson(self.lid))

    def load(self, lid, only_memo=False):
        data = self.win.ai.note(lid, only_memo)
        self.lid, self.only_memo, self.views = lid, only_memo, []
        no = self.win.ai.lessons[lid]["no"]
        self.back_btn.setText("← " + self.win.ai.place(lid)["label"])
        self.title.setText("%s %s" % (self.win.ai.place(lid)["label"], "복습 질문" if only_memo else "전체 노트"))
        self.title.show()
        while self.card_box.count():
            item = self.card_box.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        if only_memo:
            self.card_box.addWidget(rich(ai_text.MEMO_HINT, "body", "secondary"))
            if data["leeches"]:
                self.card_box.addWidget(self.leeches(data["leeches"]))
        for unit in data["units"]:
            if not unit["steps"]:
                continue
            row = FoldRow(unit["title"], "headline", bold=True)  # 펼친 단계 제목(label 굵게)보다 크게 둬 단원 경계가 보이게 함
            body = QWidget()
            body_box = kit.box(body, (kit.MARK + 12, 16, 0, 32), theme.LEARN_GAP["group"])
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
            learning_texts(view)
            self.views.append(view)

    def fit_column(self):
        self.card.setMaximumWidth(reading_width(self.width()) + 2 * CARD_PAD)

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
        self.setWindowTitle(data["name"])
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
        learning_texts(self.view)
        row = QHBoxLayout()
        row.addStretch(1)
        self.close_btn = kit.button("닫기", "secondary", "l")
        self.close_btn.clicked.connect(self.close)
        row.addWidget(self.close_btn)
        box.addLayout(row)
        room = win.geometry()
        self.resize(min(READ_WIDTH + 96, room.width() - 40), max(320, room.height() - 80))
