# -*- coding: utf-8 -*-
"""답안 입력 위젯과 단원 띠."""
import builtins
import html
import keyword
import math
import re

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (QFont, QKeySequence, QPainter, QPainterPath, QPen, QShortcut, QSyntaxHighlighter, QTextBlockFormat, QTextCharFormat,
                         QTextCursor, QTextDocument, QTextDocumentFragment, QTextFrame)
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSplitter,
                             QTextBrowser, QTextEdit, QVBoxLayout, QWidget)

import mdlite
from gui import motion, theme

INDENT = 4
PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
OPENERS = {close: ch for ch, close in PAIRS.items() if ch != close}
STRING_PREFIX = re.compile(r"(?<!\w)(?:[bfru]|[bf]r|r[bf])$", re.IGNORECASE)  # f"", r"", rb"" 처럼 따옴표 앞에 붙는 글자
KEYWORDS = frozenset(keyword.kwlist)
BUILTINS = frozenset(name for name in dir(builtins) if not name.startswith("_")) - KEYWORDS
TRIPLE = ("'''", '"""')
STRING_END = {quote: re.compile(r"(?:\\.|[^\\])*?" + quote) for quote in TRIPLE + ("'", '"')}  # 역슬래시 뒤의 따옴표는 문자열을 닫지 않음
TOKEN = re.compile(r"""(?P<comment>\#)
    |(?:\b(?:[bfru]|[bf]r|r[bf]))?(?P<quote>'''|\"\"\"|'|\")
    |(?P<number>(?<![\w.])(?:0x[\da-f_]+|0b[01_]+|0o[0-7_]+|(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:e[+-]?\d+)?j?))
    |(?P<name>[^\W\d]\w*)""", re.IGNORECASE | re.VERBOSE)
DECORATOR = re.compile(r"\s*(@[^\W\d][\w.]*)")
BLANK = re.compile("_{4,}")  # 빈칸 채우기 문항의 빈칸


def scan(text, state=""):
    """한 줄에서 문자열과 주석을 뺀 코드 글자와 끝난 자리의 상태를 돌려줌. state 는 앞줄에서 이어진 삼중 따옴표.

    상태는 코드면 빈 글, 주석이면 #, 문자열 안이면 그 따옴표(삼중 따옴표면 세 글자), 문자열 안의 역슬래시 바로 뒤면 역슬래시.
    """
    code, escaped, at = [], False, 0
    while at < len(text) and state != "#":
        ch = text[at]
        if escaped:
            escaped = False
        elif state:
            escaped = ch == "\\"
            if text.startswith(state, at):
                state, at = "", at + len(state) - 1
        elif ch in "\"'":
            state = ch * 3 if text.startswith(ch * 3, at) else ch
            at += len(state) - 1
        elif ch == "#":
            state = ch
        else:
            code.append(ch)
        at += 1
    return "".join(code), "\\" if escaped else state


def line_at(cur):
    """커서가 있는 줄의 글과 그 줄에서 커서 앞에 있는 글자 수. Qt 는 이모지 같은 글자를 두 칸으로 세어서 파이썬의 글자 수로 바꿈."""
    text, at = cur.block().text(), cur.positionInBlock()
    return text, at if text.isascii() else len(text.encode("utf-16-le", "surrogatepass")[:2 * at].decode("utf-16-le", "surrogatepass"))


def carried(cur):
    """앞줄에서 이어진 삼중 따옴표. 문법 색칠이 줄마다 적어 둔 상태에서 읽음."""
    state = cur.block().previous().userState()
    return TRIPLE[state - 1] if state > 0 else ""


def is_paste(event):
    """붙여넣기 키(Ctrl/Cmd+V 와 플랫폼별 단축키, Shift+Insert)인지."""
    plain = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
    return event.matches(QKeySequence.StandardKey.Paste) or (event.key() == Qt.Key.Key_Insert and plain == Qt.KeyboardModifier.ShiftModifier)


class PasteBlock(QObject):
    """답 칸의 붙여넣기를 막음: 붙여넣기 키, 가운데 버튼, 끌어다 놓기. 복사·잘라내기 키와 우클릭 메뉴는 gui/guard.py 가 창 전체에서 막음."""
    blocked = pyqtSignal()  # 붙여넣으려는 것을 막았을 때

    def __init__(self, parent=None):
        super().__init__(parent)

    def watch(self, edit):
        targets = [edit] + ([edit.viewport()] if isinstance(edit, QPlainTextEdit) else [])  # 여러 줄 칸의 마우스 이벤트는 viewport 가 받음
        for target in targets:
            target.installEventFilter(self)

    def eventFilter(self, target, event):
        kind, types = event.type(), QEvent.Type
        if kind == types.KeyPress and is_paste(event):
            self.blocked.emit()
            return True
        if kind in (types.MouseButtonPress, types.MouseButtonRelease) and event.button() == Qt.MouseButton.MiddleButton:
            if kind == types.MouseButtonRelease:
                self.blocked.emit()
            return True
        if kind in (types.DragEnter, types.DragMove, types.Drop):
            event.ignore()
            if kind != types.DragMove:
                self.blocked.emit()
            return True
        return False


class PlainEdit(QPlainTextEdit):
    """붙여넣기를 받지 않는 여러 줄 입력칸. 어느 길로 붙여넣든 insertFromMimeData 를 거치므로 여기서 버림."""

    def canInsertFromMimeData(self, source):
        return False

    def insertFromMimeData(self, source):
        pass


class Highlighter(QSyntaxHighlighter):
    """파이썬 문법에 따라 글자색을 입힘. 색은 줄의 배치에만 얹혀서 글과 실행 취소 기록이 바뀌지 않음.
    줄의 상태는 삼중 따옴표 문자열이 다음 줄로 이어지는지를 나타냄: 0 은 코드, 1 과 2 는 TRIPLE 의 그 따옴표로 연 문자열 안."""

    def __init__(self, document):
        super().__init__(document)
        self.formats = {}
        for kind in ("keyword", "def", "builtin", "string", "comment", "number", "decorator", "self", "blank"):
            self.formats[kind] = QTextCharFormat()
            self.formats[kind].setForeground(theme.editor(kind))
        self.formats["blank"].setBackground(theme.editor("blank_bg"))

    def highlightBlock(self, text):
        wide = [at for at, ch in enumerate(text) if ch > "\uffff"] if not text.isascii() else []

        def paint(start, end, kind):
            if wide:  # Qt 는 이모지 같은 글자를 두 칸으로 셈
                start, end = (at + sum(1 for spot in wide if spot < at) for at in (start, end))
            self.setFormat(start, end - start, self.formats[kind])

        at, state, named = 0, max(self.previousBlockState(), 0), 0  # named 는 방금 지나온 def·class 의 끝
        if state:  # 앞줄에서 연 문자열이 이어짐
            end = STRING_END[TRIPLE[state - 1]].match(text)
            at, state = (end.end(), 0) if end else (len(text), state)
            paint(0, at, "string")
        else:
            mark = DECORATOR.match(text)
            if mark:
                at = mark.end()
                paint(mark.start(1), at, "decorator")
        while not state:
            found = TOKEN.search(text, at)
            if not found:
                break
            kind, start, at = found.lastgroup, found.start(), found.end()
            if kind == "comment":
                paint(start, len(text), kind)
                break
            if kind == "quote":
                quote = found.group(kind)
                end = STRING_END[quote].match(text, at)
                at = end.end() if end else len(text)  # 닫지 않은 문자열은 줄 끝까지
                if not end and quote in TRIPLE:
                    state = TRIPLE.index(quote) + 1
                paint(start, at, "string")
            elif kind == "name":
                word, kind = found.group(), ""
                if named and text[named:start].isspace():
                    kind = "def"
                elif word in KEYWORDS:
                    kind = "keyword"
                elif text[start - 1:start] != ".":  # 점 뒤의 이름은 속성이라 칠하지 않음
                    kind = "self" if word == "self" else "builtin" if word in BUILTINS else ""
                named = at if word in ("def", "class") else 0
                if kind:
                    paint(start, at, kind)
            else:
                paint(start, at, kind)
        for blank in BLANK.finditer(text):
            paint(blank.start(), blank.end(), "blank")
        self.setCurrentBlockState(state)


class CodeEditor(PlainEdit):
    """시험 화면처럼 남색 바탕에 파이썬 문법대로 글자색을 입힌 편집기. 고정폭이고 자동완성이 없음. 들여쓰기와 괄호·따옴표 닫기를 돕고 탭 문자는 넣지 않음."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("code")  # 색은 theme.EDITOR_STYLE 이 줌
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setCursorWidth(2)
        self.document().setDocumentMargin(8)  # 줄 번호 칸과 글 사이를 띄움
        self.highlighter = Highlighter(self.document())
        self.head = 0  # 본문 위에 비워 둔 높이. 찾기 막대가 뜨면 그 자리가 됨
        self.numbers = LineNumbers(self)
        self.blockCountChanged.connect(self.fit_numbers)
        self.updateRequest.connect(lambda rect, dy: self.numbers.update())
        self.cursorPositionChanged.connect(self.numbers.update)
        self.fit_numbers()

    def keyPressEvent(self, event):
        key, cur = event.key(), self.textCursor()
        back = key == Qt.Key.Key_Backtab or (key == Qt.Key.Key_Tab and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
        if self.isReadOnly():
            super().keyPressEvent(event)
        elif back or (key == Qt.Key.Key_Tab and cur.hasSelection()):
            self._shift_lines(-1 if back else 1)
        elif key == Qt.Key.Key_Tab:
            cur.insertText(" " * (INDENT - cur.positionInBlock() % INDENT))
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cur.beginEditBlock()
            cur.removeSelectedText()
            text, at = line_at(cur)
            before = text[:at]
            pad = before[:len(before) - len(before.lstrip(" "))]
            tail = "\n" + pad if self._empty_pair(cur) in ("()", "[]", "{}") else ""  # 빈 괄호 사이면 닫는 괄호를 원래 들여쓰기의 새 줄로 내림
            if tail or before.rstrip().endswith(":"):
                pad += " " * INDENT
            cur.insertText(tail)  # 내려가는 닫는 괄호를 먼저 넣어서, 다시 실행한 뒤에도 커서가 가운데 줄에 놓이게 함
            cur.setPosition(cur.position() - len(tail))
            cur.insertText("\n" + pad)
            cur.endEditBlock()
            self.setTextCursor(cur)
            self.ensureCursorVisible()
        elif key == Qt.Key.Key_Backspace and not cur.hasSelection() and self._in_indent(cur):
            cur.beginEditBlock()
            for _ in range((cur.positionInBlock() - 1) % INDENT + 1):  # 들여쓰기 한 단계(최대 4칸)
                cur.deletePreviousChar()
            cur.endEditBlock()
        elif key == Qt.Key.Key_Backspace and not cur.hasSelection() and self._empty_pair(cur):
            cur.beginEditBlock()
            cur.deletePreviousChar()
            cur.deleteChar()
            cur.endEditBlock()
        elif not self._pair(event, cur):
            super().keyPressEvent(event)

    @staticmethod
    def _in_indent(cur):
        before = cur.block().text()[:cur.positionInBlock()]
        return bool(before) and not before.strip(" ")

    @staticmethod
    def _empty_pair(cur):
        """커서가 빈 쌍 사이면 그 두 글자, 아니면 빈 글. 문자열과 주석 안의 글자는 쌍으로 보지 않음."""
        text, at = line_at(cur)
        pair = text[max(at - 1, 0):at + 1]
        if len(pair) < 2 or PAIRS.get(pair[0]) != pair[1] or scan(text[:at - 1], carried(cur))[1]:
            return ""
        return pair

    def _pair(self, event, cur):
        """괄호·따옴표 키면 닫는 글자를 같이 넣거나 이미 있는 닫는 글자를 넘어가고 True 를 돌려줌. 글자만 넣으면 될 때는 False.

        자판 배열과 입력기에 따라 키 코드가 달라서 들어갈 글자로 판단함.
        """
        ch, ctrl = event.text(), Qt.KeyboardModifier.ControlModifier
        close, opener = PAIRS.get(ch), OPENERS.get(ch)
        if not (close or opener) or event.modifiers() in (ctrl, ctrl | Qt.KeyboardModifier.ShiftModifier):  # Ctrl 조합의 글자는 Qt 도 넣지 않음
            return False
        picked = cur.selectedText()
        if picked and not BLANK.fullmatch(picked):
            if not close:
                return False
            start, end = cur.selectionStart(), cur.selectionEnd()
            cur.beginEditBlock()
            cur.setPosition(end)
            cur.insertText(close)
            cur.setPosition(start)
            cur.insertText(ch)
            cur.setPosition(end + 1, QTextCursor.MoveMode.KeepAnchor)  # 감싼 글은 선택된 채로 둠
            cur.endEditBlock()
            self.setTextCursor(cur)
            return True
        text, at = line_at(cur)
        if picked:  # 빈칸을 선택하고 치면 감싸지 않고, 빈칸을 지운 자리에 친 것으로 봄
            at -= cur.position() - cur.selectionStart()
            text = text[:at] + text[at + len(picked):]
        inside = carried(cur)
        prev, after, state = text[:at][-1:], text[at:at + 1], scan(text[:at], inside)[1]
        quote = ch == close
        if state == "\\" or (state and not quote):  # 역슬래시 뒤의 글자와 문자열·주석 안의 괄호는 그대로 들어감
            return False
        if after == ch and (state == ch if quote else opener):  # 따옴표는 그 문자열을 닫는 것일 때만 넘어감
            code, end = scan(text, inside)
            if opener and code.count(opener) > code.count(ch):  # 닫는 괄호가 모자라면 넘어가지 않고 새로 넣음
                return False
            if quote and end == ch:  # 줄이 문자열 안에서 끝나면 뒤의 따옴표는 다른 문자열을 여는 것이라 새로 넣음
                return False
            cur.removeSelectedText()
            cur.movePosition(QTextCursor.MoveOperation.Right)
            self.setTextCursor(cur)
            return True
        if not close:
            return False
        word = prev.isalnum() or prev == "_"
        if quote and (state or prev in ('"', "'") or (word and not STRING_PREFIX.search(text[:at]))):
            return False
        if after and not after.isspace() and after not in ")]},:":  # 뒤에 글자가 이어지면 닫지 않음
            return False
        if not quote:  # 아랫줄에서 닫히는 괄호가 열려 있는 줄에서는 닫지 않음. 닫으면 친 닫는 괄호가 넘어가지 못해 하나 남음
            code = scan(text, inside)[0]
            if code.count(ch) > code.count(close):
                return False
        cur.beginEditBlock()  # 앞서 친 글과 합쳐지지 않고 이 한 번만 되돌아가게 함
        cur.insertText(ch + close)
        cur.endEditBlock()
        cur.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cur)
        return True

    def _shift_lines(self, direction):
        cur, doc = self.textCursor(), self.document()
        first = doc.findBlock(cur.selectionStart()).blockNumber()
        last = doc.findBlock(max(cur.selectionStart(), cur.selectionEnd() - 1)).blockNumber()
        cur.beginEditBlock()
        for number in range(first, last + 1):
            block = doc.findBlockByNumber(number)
            edit = QTextCursor(block)
            if direction > 0:
                edit.insertText(" " * INDENT)
            else:
                text = block.text()
                drop = min(INDENT, len(text) - len(text.lstrip(" ")))
                edit.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, drop)
                edit.removeSelectedText()
        cur.endEditBlock()

    def number_width(self):
        """줄 번호 칸의 폭. 줄 수의 자릿수를 따르고 두 자리보다 좁아지지 않음."""
        return 2 * LineNumbers.PAD + self.fontMetrics().horizontalAdvance("9") * max(2, len(str(self.blockCount())))

    def fit_numbers(self, *_):
        """본문을 줄 번호 칸의 폭만큼 오른쪽으로, head 만큼 아래로 밀고 칸을 다시 놓음. 줄 수나 글자 크기가 바뀌면 부름."""
        self.setViewportMargins(self.number_width(), self.head, 0, 0)
        self.place_numbers()

    def place_numbers(self):
        """줄 번호 칸을 본문 왼쪽에 놓음. 가로 스크롤 막대를 덮지 않게 본문의 아래 끝에서 멈춤."""
        area = self.contentsRect()
        self.numbers.setGeometry(area.left(), area.top(), self.number_width(), self.viewport().geometry().bottom() + 1 - area.top())

    def set_head(self, height):
        """본문 위에 height 만큼을 비움."""
        self.head = height
        self.fit_numbers()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.place_numbers()

    def setFont(self, font):
        """글꼴을 바꾸고 줄 번호 칸을 그 글꼴에 맞춤. 글꼴이 바뀌는 이벤트마다 맞추면 안 됨: 앱 테마를 바꾸는 동안 글꼴이 잠깐 앱 글꼴로
        돌아가는데, 그 글꼴로 본문을 다시 배치하면 끝까지 내려 둔 스크롤이 몇 줄 위로 밀림."""
        super().setFont(font)
        self.fit_numbers()

    def paint_numbers(self, event):
        """보이는 줄마다 번호(1부터)를 오른쪽 정렬로 그림. 커서가 있는 줄은 본문 글자색, 나머지는 흐린 색."""
        strip, metrics = self.numbers, self.fontMetrics()
        painter = QPainter(strip)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.editor("gutter" if self.isEnabled() else "locked_gutter"))  # 실행·채점 중에 잠기면 본문처럼 어두워짐
        corner = LineNumbers.CORNER  # 편집기의 둥근 테두리 안쪽을 따라 왼쪽 모서리만 둥글게 칠함. 오른쪽 모서리는 칸 밖에 놓임
        painter.drawRoundedRect(QRectF(0, 0, strip.width() + corner, self.contentsRect().height()), corner, corner)
        painter.fillRect(QRectF(strip.width() - 1, 0, 1, strip.height()), theme.editor("edge"))
        painter.setFont(self.font())
        block, current, right = self.firstVisibleBlock(), self.textCursor().blockNumber(), strip.width() - LineNumbers.PAD
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top() + self.viewport().y() - strip.y()
        while block.isValid() and top <= event.rect().bottom():
            height = self.blockBoundingRect(block).height()  # 아직 배치하지 않은 줄은 여기서 배치됨
            line, text = block.layout().lineAt(0), str(block.blockNumber() + 1)
            painter.setPen(theme.editor("ink" if block.blockNumber() == current else "line_no"))
            painter.drawText(QPointF(right - metrics.horizontalAdvance(text), top + line.y() + line.ascent()), text)  # 본문 글자와 밑선을 맞춤
            top += height
            block = block.next()


class LineNumbers(QWidget):
    """편집기 왼쪽의 줄 번호 칸. 그리기는 편집기(CodeEditor.paint_numbers)가 함. 눌러도 편집기의 글과 커서가 바뀌지 않고, 휠은 편집기로 넘김."""
    PAD, CORNER = 8, 5  # 번호 양옆의 여백, 왼쪽 모서리의 반지름

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, event):
        self.editor.paint_numbers(event)

    def wheelEvent(self, event):
        QApplication.sendEvent(self.editor.viewport(), event)


LINE_PCT = 135  # 안내 글의 줄 높이. 글자 크기에 대한 백분율


class Para(QLabel):
    """여러 줄로 넘어가는 안내 글. 같이 배포하는 글꼴은 줄 높이가 글자 크기와 같아 줄이 붙어 보이므로 줄 간격을 넓혀 그림.
    setText 와 text 는 QLabel 처럼 꾸밈없는 글을 주고받음. 넓힌 줄 간격은 마지막 줄 아래에도 붙는데, 그만큼은 높이에서 빼서
    한 줄짜리 글이 QLabel 과 같은 자리를 차지하게 함."""

    plain = ""

    def __init__(self, text="", name=""):
        super().__init__()
        self.setObjectName(name)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setText(text)

    def markup(self, text):
        return '<span style="white-space: pre-wrap;">%s</span>' % html.escape(text)

    def setText(self, text):
        self.plain = text
        super().setText(text and '<p style="margin: 0; line-height: %d%%;">%s</p>' % (LINE_PCT, self.markup(text)))

    def text(self):
        return self.plain

    def tail(self):
        """마지막 줄 아래에 붙는 줄 간격."""
        self.ensurePolished()
        return self.fontMetrics().height() * (LINE_PCT - 100) // 100 if self.plain else 0

    def heightForWidth(self, width):
        return super().heightForWidth(width) - self.tail()

    def sizeHint(self):
        """꾸밈없는 QLabel 이 줄바꿈하는 글의 폭을 어림하는 방식을 따름. 꾸민 글의 어림은 좁고 길어서 대화상자가 헐겁게 열림."""
        if not self.plain:
            return super().sizeHint()
        self.ensurePolished()
        metrics, shown = self.fontMetrics(), QTextDocumentFragment.fromHtml(super().text()).toPlainText()
        wide = metrics.averageCharWidth() * 80
        flags = Qt.TextFlag.TextWordWrap if self.wordWrap() else 0
        box = metrics.boundingRect(0, 0, wide, 2000, flags, shown)
        for part, lines in ((2, 4), (4, 2)):
            if self.wordWrap() and box.height() < lines * metrics.lineSpacing() and box.width() > wide // part:
                box = metrics.boundingRect(0, 0, wide // part, 2000, flags, shown)
        width = box.width()
        if box.height() < 2 * metrics.lineSpacing():  # 한 줄이면 꾸민 글이 실제로 차지하는 폭을 줌. 1px 만 모자라도 두 줄로 넘어감
            doc = QTextDocument()
            doc.setDefaultFont(self.font())
            doc.setDocumentMargin(0)
            doc.setHtml(super().text())
            width = max(width, math.ceil(doc.idealWidth()))
        width += self.contentsMargins().left() + self.contentsMargins().right()
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        return QSize(size.width(), max(0, size.height() - self.tail()))


def centered(label):
    """단추나 다른 글과 한 줄에 놓이는 Para 를 세로 가운데에 둠. 줄 전체 높이로 늘리면 마지막 줄 아래 간격 때문에 글이 위로 치우침."""
    column = QVBoxLayout()
    column.addStretch(1)
    column.addWidget(label)
    column.addStretch(1)
    return column


def hint_label():
    return Para(name="muted")


class LinkLabel(Para):
    """링크가 든 글(HTML). 링크 색은 글을 넣는 순간의 팔레트로 굳으므로 테마가 바뀌면 글을 다시 넣음."""

    def markup(self, text):
        return text

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and self.text():
            text = self.text()
            self.clear()  # 같은 글은 setText 가 건너뜀
            self.setText(text)


def content_height(doc):
    """문서의 내용이 끝나는 높이. 표나 코드 상자로 끝나면 그 아래 여백을, 글로 끝나면 마지막 줄 아래에 붙는 줄 간격을 뺌."""
    last, child = None, doc.rootFrame().begin()
    while not child.atEnd():
        frame = child.currentFrame()
        if frame is not None or child.currentBlock().text():
            last = frame or child.currentBlock()
        child += 1
    if last is None:
        return doc.size().height()
    if isinstance(last, QTextFrame):
        return doc.size().height() - last.frameFormat().bottomMargin()
    form, line = last.blockFormat(), last.layout().lineAt(last.layout().lineCount() - 1)
    if form.lineHeightType() != QTextBlockFormat.LineHeightTypes.ProportionalHeight.value:
        return doc.size().height()
    return doc.size().height() - line.height() * (form.lineHeight() / 100 - 1)


class ChoiceCard(QWidget):
    """객관식 보기 하나: 번호 배지와 보기 내용. 어디를 눌러도 골라지고, 고르면 오른쪽에 체크 표시가 그려짐.
    내용이 없으면(보기를 나누지 못한 문항) 번호만 보여 줌."""
    picked = pyqtSignal(int)  # 누르거나 Space 로 골랐을 때. 보기 번호
    stepped = pyqtSignal(int, int)  # 위·아래 키. 보기 번호와 방향(-1, 1)
    PAD, BADGE, MARK = 12, 26, 18  # 안쪽 여백, 번호 배지의 한 변, 체크 표시의 한 변

    def __init__(self, number, html, css, multi, parent=None):
        super().__init__(parent)
        self.number, self.multi = number, multi
        self.html = html or "<body><p><b>%d번</b></p></body>" % number
        self.checked, self.tick, self.over, self.ring, self.top = False, 0.0, False, False, self.PAD
        self.down = False  # 이 카드에서 왼쪽 버튼을 누른 채인지
        self.doc = QTextDocument(self)
        self.doc.setDocumentMargin(0)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restyle(css)

    def restyle(self, css):
        """본문과 같은 CSS 로 내용을 다시 넣음. 긴 코드 줄은 카드 폭에서 줄바꿈함."""
        self.doc.setDefaultFont(self.font())
        self.doc.setDefaultStyleSheet(css + "pre { white-space: pre-wrap; }")
        self.doc.setHtml(self.html)
        self.arrange()
        self.update()

    def arrange(self):
        """폭에 맞춰 내용을 줄바꿈하고 카드 높이를 정함. 첫 줄의 가운데를 번호 배지의 가운데에 맞춤."""
        self.doc.setTextWidth(max(80, self.width() - 4 * self.PAD - self.BADGE - self.MARK))
        height, first = content_height(self.doc), self.doc.firstBlock()
        line = first.layout().lineAt(0).height() if first.text() else self.BADGE  # 코드 상자로 시작하면 위쪽을 배지에 맞춤
        self.top = self.PAD + max(0.0, (self.BADGE - line) / 2)
        self.setFixedHeight(math.ceil(max(self.PAD + self.BADGE, self.top + height) + self.PAD))

    def isChecked(self):
        return self.checked

    def setChecked(self, checked, animate=False):
        self.checked, self.tick = checked, 0.0
        motion.play(self, motion.CHECK_MS if checked and animate else 0, self._draw_tick)  # 0 이면 돌던 것을 멈추고 곧바로 끝 상태

    def _draw_tick(self, t):
        self.tick = t
        self.update()

    def resizeEvent(self, event):
        self.arrange()

    def enterEvent(self, event):
        self.over = True
        self.update()

    def leaveEvent(self, event):
        self.over = False
        self.update()

    def focusInEvent(self, event):
        self.ring = event.reason() != Qt.FocusReason.MouseFocusReason  # 키보드로 옮겨 왔을 때만 테두리를 보임
        self.update()

    def focusOutEvent(self, event):
        self.ring = False
        self.update()

    def mousePressEvent(self, event):
        self.down = event.button() == Qt.MouseButton.LeftButton
        event.accept()

    def mouseDoubleClickEvent(self, event):
        """더블클릭의 두 번째 누름은 고르기로 치지 않음. 앞 화면의 버튼을 두 번 누른 것이 같은 자리의 카드로 들어와 답이 바뀌거나,
        방금 고른 카드가 바로 풀리지 않게 함."""
        self.down = False
        event.accept()

    def mouseReleaseEvent(self, event):
        down, self.down = self.down, False
        if down and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.picked.emit(self.number)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space:
            if not event.isAutoRepeat():  # 누르고 있어도 한 번만 고름
                self.picked.emit(self.number)
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.stepped.emit(self.number, -1 if key == Qt.Key.Key_Up else 1)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        on, pad, badge = self.checked, self.PAD, self.BADGE
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.55)
        edge = "primary" if on else ("border_strong" if self.over else "border")
        painter.setPen(QPen(theme.qcolor(edge), 2 if on else 1))
        painter.setBrush(theme.qcolor("selection" if on else ("hover" if self.over else "surface")))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
        if self.ring:
            painter.setPen(QPen(theme.qcolor("primary"), 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(4.5, 4.5, -4.5, -4.5), 5, 5)
        corner = 7 if self.multi else badge / 2  # 여러 개를 고르는 문항은 네모, 하나만 고르는 문항은 동그라미
        painter.setPen(QPen(theme.qcolor("primary" if on else "border_strong"), 1.5))
        painter.setBrush(theme.qcolor("primary" if on else "surface_alt"))
        painter.drawRoundedRect(QRectF(pad, pad, badge, badge), corner, corner)
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(theme.qcolor("primary_ink" if on else "muted"))
        painter.drawText(QRectF(pad, pad, badge, badge), Qt.AlignmentFlag.AlignCenter, str(self.number))
        painter.save()
        painter.translate(2 * pad + badge, self.top)
        self.doc.drawContents(painter)
        painter.restore()
        if on and self.tick > 0:
            self._paint_tick(painter)

    def _paint_tick(self, painter):
        """체크 표시를 tick(0~1)만큼만 그림. 짧은 획을 먼저 긋고 긴 획을 이어 긋음."""
        size = self.MARK
        left, top = self.width() - self.PAD - size, self.PAD + (self.BADGE - size) / 2
        points = [QPointF(left + size * x, top + size * y) for x, y in ((0.12, 0.55), (0.4, 0.8), (0.9, 0.22))]
        short = math.hypot(points[1].x() - points[0].x(), points[1].y() - points[0].y())
        long = math.hypot(points[2].x() - points[1].x(), points[2].y() - points[1].y())
        drawn = self.tick * (short + long)
        path = QPainterPath(points[0])
        path.lineTo(points[0] + (points[1] - points[0]) * min(1.0, drawn / short))
        if drawn > short:
            path.lineTo(points[1] + (points[2] - points[1]) * ((drawn - short) / long))
        painter.setPen(QPen(theme.qcolor("primary"), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class ChoicePanel(QWidget):
    """객관식: 보기마다 카드 하나. 보기 수를 세지 못한 문항은 번호 입력칸.
    보기는 카드를 누르거나 숫자 키로 고르고, 카드에 포커스가 있으면 위·아래 키로 옮기고 Space 로 고름."""
    changed = pyqtSignal(object)  # 고른 번호 목록

    def __init__(self, parent=None):
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        self.hint = hint_label()
        self.stray = hint_label()  # 답안지에 손으로 적은 값이 카드와 맞지 않을 때의 안내
        self.stray.setObjectName("warn")
        self.stray.hide()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("예: 2   (여러 개면 1, 3)")
        self.entry.textChanged.connect(lambda text: self.changed.emit(sorted({int(n) for n in re.findall(r"\d+", text)})))
        inner = QWidget()
        inner.setObjectName("page")
        self.cards = QVBoxLayout(inner)
        self.cards.setContentsMargins(0, 0, 0, 0)
        self.cards.setSpacing(8)
        self.cards.addStretch(1)
        self.scroll = QScrollArea()  # 보기가 길어 칸을 넘으면 스크롤함
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll.setWidget(inner)
        box.addWidget(self.hint)
        box.addWidget(self.stray)
        box.addWidget(self.entry)
        box.addWidget(self.scroll, 1)
        self.buttons, self.multi, self.css = [], False, ""
        # 숫자 키는 포커스가 문항 목록이나 다른 버튼에 있어도 듣고, 이 칸이 가려지거나 잠기면 듣지 않음. 입력칸에서는 글자로 들어감
        self.keys = [QShortcut(QKeySequence(str(number)), self, lambda n=number: self.toggle(n)) for number in range(1, 10)]
        for key in self.keys:
            key.setAutoRepeat(False)  # 누르고 있어도 한 번만 고름

    def set_item(self, item):
        for card in self.buttons:
            self.cards.removeWidget(card)
            card.deleteLater()
        self.buttons, self.multi = [], item["multi"]
        answer = item["answer"]
        picked = [] if answer is None else (list(answer) if isinstance(answer, (list, tuple, set)) else [answer])
        options = item.get("options") or [None] * item["choices"]  # 보기를 나누지 못한 문항은 번호만 든 카드
        # 따옴표로 감싼 번호나 없는 번호는 카드로 보여 줄 수 없고 그대로 두면 오답으로 채점되므로 알림
        stray = [value for value in picked if type(value) is not int or not 1 <= value <= len(options)] if options else []
        self.stray.setText("답안지에 적힌 값(%s)이 보기 번호와 맞지 않습니다. 보기를 다시 골라 주세요." % ", ".join(repr(value) for value in stray))
        self.stray.setVisible(bool(stray))
        many = "정답을 모두 고르세요. 보기를 누르거나 숫자 키(1~%d)로 고릅니다."
        one = "보기를 누르거나 숫자 키(1~%d)로 고르세요. 다시 누르면 선택이 풀립니다."
        self.hint.setText((many if item["multi"] else one) % len(options) if options else "보기 번호를 숫자로 적으세요.")
        self.entry.setVisible(not options)
        self.entry.blockSignals(True)
        self.entry.setText(", ".join(str(n) for n in picked))
        self.entry.blockSignals(False)
        for number, blocks in enumerate(options, 1):
            card = ChoiceCard(number, mdlite.blocks_html(blocks) if blocks else "", self.css, item["multi"])
            card.setChecked(number in picked and number not in stray)
            card.picked.connect(self.toggle)
            card.stepped.connect(self.step)
            self.cards.insertWidget(self.cards.count() - 1, card)
            self.buttons.append(card)
        for key in self.keys:
            key.setEnabled(bool(options))
        self.scroll.verticalScrollBar().setValue(0)

    def restyle(self, css):
        self.css = css
        for card in self.buttons:
            card.restyle(css)

    def toggle(self, number):
        """number 번 보기를 고르거나 풂. 단일 정답이면 방금 고른 것만 남김."""
        if not 1 <= number <= len(self.buttons):
            return
        card = self.buttons[number - 1]
        if not card.checked and not self.multi:
            for other in self.buttons:
                other.setChecked(False)
        card.setChecked(not card.checked, animate=True)
        self.stray.hide()  # 이제 저장되는 값은 카드에 보이는 그대로임
        self.scroll.ensureWidgetVisible(card, 0, 8)
        self.changed.emit([n for n, each in enumerate(self.buttons, 1) if each.checked])

    def step(self, number, direction):
        """number 번 카드에서 위나 아래 카드로 포커스를 옮김."""
        if 1 <= number + direction <= len(self.buttons):
            card = self.buttons[number + direction - 1]
            card.setFocus(Qt.FocusReason.TabFocusReason)
            self.scroll.ensureWidgetVisible(card, 0, 8)

    def focus_input(self):
        pass


class TextPanel(QWidget):
    """출력 예측(여러 줄) · 단답(한 줄). 고정폭이라 화면에 보이는 공백과 줄바꿈이 똑같이 저장됨."""
    changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        self.hint = hint_label()
        self.multi = PlainEdit()
        self.multi.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.multi.setTabChangesFocus(True)
        self.single = QLineEdit()
        self.single.setMinimumHeight(38)
        box.addWidget(self.hint)
        box.addWidget(self.multi, 1)
        box.addWidget(self.single)
        self.pad = QWidget()
        box.addWidget(self.pad, 1)
        self.multi.textChanged.connect(lambda: self.changed.emit(self.multi.toPlainText()))
        self.single.textChanged.connect(self.changed.emit)

    def set_item(self, item):
        is_output = item["type"] == "output"
        for widget in (self.multi, self.single):
            widget.blockSignals(True)
        self.multi.setVisible(is_output)
        self.single.setVisible(not is_output)
        self.pad.setVisible(not is_output)
        self.hint.setText("실행하면 화면에 찍히는 글자를 그대로 적으세요. 답을 따옴표로 감싸지는 않지만, 출력에 찍히는 따옴표는 적습니다. "
                          "여러 줄이면 줄을 바꿔 적습니다." if is_output else "따옴표 없이 한 줄로 적으세요.")
        text = item["answer"] or ""
        self.multi.setPlainText(text if is_output else "")
        self.single.setText("" if is_output else text)
        for widget in (self.multi, self.single):
            widget.blockSignals(False)

    def focus_input(self):
        (self.multi if self.multi.isVisible() else self.single).setFocus()


class CodePanel(QWidget):
    changed = pyqtSignal(object)
    HINT = "'코드 실행'을 누르면 예시 실행 결과가 여기에 나옵니다. 예시만 실행하며 기록되지 않습니다."

    def __init__(self, parent=None):
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.hint = hint_label()
        self.reset_btn = QPushButton("시작 코드로 되돌리기")
        top.addLayout(centered(self.hint), 1)
        top.addWidget(self.reset_btn)
        box.addLayout(top)
        split = QSplitter(Qt.Orientation.Vertical)
        self.editor = CodeEditor()
        self.console = QTextBrowser()
        self.console.setOpenLinks(False)
        split.addWidget(self.editor)
        split.addWidget(self.console)
        split.setSizes([340, 280])
        split.setChildrenCollapsible(False)
        box.addWidget(split, 1)
        self.editor.textChanged.connect(self._edited)
        self.code = ""  # 바로 앞에 알린 글
        self.console_html = ""

    def set_item(self, item):
        self.hint.setText("빈칸(____)만 채우세요. 다른 부분은 고치지 않습니다." if item["type"] == "fill" else "아래에 코드를 작성하세요.")
        self.set_code(item["answer"])
        self.show_console("")

    def set_code(self, text):
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self.code = self.editor.toPlainText()

    def _edited(self):
        """글이 달라졌을 때만 알림. 문법 색칠을 다시 하면 글이 같아도 textChanged 가 나옴."""
        text = self.editor.toPlainText()
        if text != self.code:
            self.code = text
            self.changed.emit(text)

    def show_console(self, html):
        """실행 결과를 보여 줌. 결과가 없으면 안내를 본문으로 넣음. 입력칸의 안내 글(placeholder)은 한 줄만 그려져 좁은 칸에서 잘림."""
        self.console_html = html
        self.console.setHtml(html or '<body><p class="muted">%s</p></body>' % self.HINT)

    def focus_input(self):
        self.editor.setFocus()


class FindBar(QFrame):
    """편집기 안의 글을 찾는 막대: 입력칸, 개수 표시, 이전·다음·닫기 단추. 편집기 오른쪽 위에 뜨고, 글을 가리지 않게 본문을 그 높이만큼 내림.
    맞는 곳은 편집기의 extraSelections 로 칠해서 글과 답이 바뀌지 않음. 대소문자는 가리지 않음.
    화면을 잠가 편집기가 꺼져 있어도 쓰이게 편집기가 아니라 host(편집기의 조상)의 자식으로 둠."""
    GAP, WIDTH, INPUT = 6, 320, 80  # 편집기 테두리와의 간격, 가장 넓을 때의 폭, 좁은 편집기에서 입력칸에 남겨 두는 폭

    def __init__(self, editor, host):
        super().__init__(host)
        self.setObjectName("find")
        self.editor = editor
        self.matches, self.index = [], -1  # 맞는 곳(선택을 든 커서)과 지금 가리키는 곳의 순번
        self.origin = QTextCursor(editor.document())  # 여기서부터 처음 맞는 곳을 가리킴. 글을 고치면 같이 밀림
        row = QHBoxLayout(self)
        row.setContentsMargins(5, 4, 4, 4)
        row.setSpacing(2)
        self.input = QLineEdit()
        self.input.setPlaceholderText("찾기")
        self.input.setAcceptDrops(False)  # 끌어다 놓기를 받으면 끌어온 글이 편집기에서 빠짐
        self.count = QLabel()
        self.count.setObjectName("muted")
        self.count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count.setMinimumWidth(44)
        row.addWidget(self.input, 1)
        row.addWidget(self.count)
        self.prev_btn = self._button("↑", "이전 (Shift+Enter)", lambda: self.step(-1))
        self.next_btn = self._button("↓", "다음 (Enter)", lambda: self.step(1))
        self.close_btn = self._button("×", "닫기 (Esc)", lambda: self.dismiss())
        self.input.textChanged.connect(lambda: self.search())
        editor.document().contentsChanged.connect(lambda: self.isHidden() or self.search(move=False))
        standard, scope = QKeySequence.StandardKey, Qt.ShortcutContext.WidgetWithChildrenShortcut
        bindings = ((standard.Find, "", self.reveal), (standard.FindNext, "F3", lambda: self.step(1)),
                    (standard.FindPrevious, "Shift+F3", lambda: self.step(-1)))
        for owner in (editor, self):  # 포커스가 편집기나 이 막대에 있을 때만 들음
            for key, fixed, slot in bindings:
                keys = QKeySequence.keyBindings(key)
                extra = [QKeySequence(fixed)] if fixed and QKeySequence(fixed) not in keys else []  # 맥의 표준 키에는 F3 이 없음
                QShortcut(key, owner, slot, context=scope).setKeys(keys + extra)
        self.escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), editor, self.dismiss, context=scope)  # 막대가 떠 있으면 편집기에서도 Esc 로 닫음
        self.escape.setEnabled(False)
        widget = editor.viewport()
        while widget is not host:  # 편집기나 그 위의 칸이 움직이면 따라감
            widget.installEventFilter(self)
            widget = widget.parentWidget()
        self.hide()

    def _button(self, text, tip, slot):
        button = QPushButton(text)
        button.setObjectName("tool")
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 눌러도 포커스가 입력칸에 남음
        button.clicked.connect(slot)
        self.layout().addWidget(button)
        return button

    def reveal(self):
        """막대를 띄우고 입력칸으로 감. 편집기에서 한 줄 안의 글을 선택해 두었으면 그 글을 찾음."""
        cursor = self.editor.textCursor()
        picked = cursor.selectedText()
        self.origin.setPosition(cursor.selectionStart())
        if picked and "\u2029" not in picked:  # 여러 줄을 선택하면 줄 사이에 이 글자가 들어 있음
            self.input.setText(picked)
        self.show()  # 띄워야 스타일이 입혀져 높이가 정해짐
        self.raise_()
        self.escape.setEnabled(True)
        self.editor.set_head(self.sizeHint().height() + 2 * self.GAP)
        self.place()
        self.input.setFocus()
        self.input.selectAll()
        self.search()

    def dismiss(self, select=True):
        """막대를 닫고 칠을 지움. select 면 가리키던 곳을 선택하고 포커스를 편집기로 돌려줌.
        그 사이에 편집기에서 커서를 옮겼거나 글을 선택했으면 그대로 둠."""
        if self.isHidden():
            return
        self.hide()
        self.escape.setEnabled(False)
        self.editor.setExtraSelections([])
        self.editor.set_head(0)
        if select:
            cursor = self.editor.textCursor()
            if self.matches and not cursor.hasSelection() and cursor.position() == self.matches[self.index].selectionStart():
                self.editor.setTextCursor(self.matches[self.index])
            self.editor.setFocus()
        self.matches, self.index = [], -1

    def search(self, move=True):
        """맞는 곳을 처음부터 다시 찾고, origin 이후의 첫 곳(없으면 맨 처음 곳)을 가리킴."""
        text, document = self.input.text(), self.editor.document()
        self.matches = []
        found = document.find(text, 0) if text else QTextCursor()
        while not found.isNull():
            self.matches.append(found)
            found = document.find(text, found)
        start = self.origin.position()
        self.index = next((n for n, each in enumerate(self.matches) if each.selectionStart() >= start), 0) if self.matches else -1
        self.paint(move)

    def step(self, direction):
        """다음(1)이나 이전(-1) 곳을 가리킴. 끝에서는 반대쪽 끝으로 돌아감. 막대가 닫혀 있으면 띄움."""
        if self.isHidden():
            self.reveal()
        elif self.matches:
            self.index = (self.index + direction) % len(self.matches)
            self.origin.setPosition(self.matches[self.index].selectionStart())
            self.paint(move=True)

    def paint(self, move=False):
        """맞는 곳을 전부 옅게, 가리키는 곳은 진하게 칠하고 개수를 고침. move 면 가리키는 곳으로 편집기의 커서를 옮겨 그 줄이 보이게 함."""
        marks = []
        for number, each in enumerate(self.matches):
            mark = QTextEdit.ExtraSelection()
            mark.cursor = each
            name = "find_current" if number == self.index else "find"
            mark.format.setBackground(theme.editor(name))
            mark.format.setForeground(theme.editor(name + "_ink"))  # 문법 색이 칠 위에서 흐려지지 않게 글자색도 정함
            marks.append(mark)
        self.editor.setExtraSelections(marks)
        missing = bool(self.input.text()) and not self.matches
        self.count.setText("없음" if missing else "%d/%d" % (self.index + 1, len(self.matches)) if self.matches else "")
        for button in (self.prev_btn, self.next_btn):
            button.setEnabled(bool(self.matches))
        if missing != bool(self.input.property("missing")):
            self.input.setProperty("missing", missing)
            self.input.style().unpolish(self.input)  # 속성으로 고른 스타일은 다시 입혀야 바뀜
            self.input.style().polish(self.input)
        if move and self.matches:
            spot = QTextCursor(self.matches[self.index])
            spot.setPosition(spot.selectionStart())
            seen = self.editor.viewport().rect().contains(self.editor.cursorRect(spot))
            self.editor.setTextCursor(spot)
            if not seen:  # 화면 밖에 있던 곳은 가운데로 가져옴
                self.editor.centerCursor()

    def place(self):
        """편집기가 본문 위에 비워 둔 자리의 오른쪽 끝에 놓음. 편집기가 좁으면 그 폭에 맞춰 줄어듦.
        본문 폭만 쓰면 개수가 잘리고 입력칸이 INPUT 보다 좁아질 때는 줄 번호 칸 위의 빈 자리까지 씀."""
        view = self.editor.viewport()
        want = self.minimumSizeHint().width() - self.input.minimumSizeHint().width() + self.INPUT  # 개수가 두 자리일 때 입력칸이 INPUT 이 되는 폭
        width = min(max(min(self.WIDTH, view.width() - 2 * self.GAP), want), view.x() + view.width() - 2 * self.GAP)
        size = QSize(width, self.sizeHint().height())
        corner = QPoint(view.width() - self.GAP - size.width(), -self.GAP - size.height())
        self.setGeometry(QRect(view.mapTo(self.parentWidget(), corner), size))

    def eventFilter(self, target, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move) and not self.isHidden():
            self.place()
        return False

    def keyPressEvent(self, event):
        """입력칸이 받지 않고 넘긴 키. Enter 는 다음, Shift+Enter 는 이전, Esc 는 닫기."""
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.step(-1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
        elif key == Qt.Key.Key_Escape:
            self.dismiss()
        else:
            super().keyPressEvent(event)


def unit_legend():
    """단원 띠의 색이 뜻하는 상태를 한 줄로 보여 줌."""
    legend = QHBoxLayout()
    legend.setSpacing(6)
    for state, name in theme.UNIT.items():
        swatch = QLabel()
        swatch.setObjectName("unit_" + state)
        swatch.setFixedSize(12, 12)
        text = QLabel(name)
        text.setObjectName("muted")
        legend.addWidget(swatch)
        legend.addWidget(text)
        legend.addSpacing(10)
    legend.addStretch(1)
    return legend


class UnitStrip(QWidget):
    """차시마다 칸 하나. 색으로 상태를 보이고, 마우스를 올리면 단원 이름과 상태가 나옴.
    compact 면 칸을 낮추고 범례를 빼서 팀 현황의 카드에 넣음."""

    def __init__(self, compact=False, parent=None):
        super().__init__(parent)
        self.cell_height = 24 if compact else 38
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        self.cells = QHBoxLayout()
        self.cells.setSpacing(3 if compact else 4)
        box.addLayout(self.cells)
        if not compact:
            box.addLayout(unit_legend())

    @staticmethod
    def state_of(unit):
        if not unit["tested"]:
            return "none"
        if unit["mastered"]:
            return "mastered"
        if unit["retry"]:
            return "retry"
        return "level1" if unit["level"] == 1 else "level2"

    def set_units(self, units):
        while self.cells.count():
            self.cells.takeAt(0).widget().deleteLater()
        for unit in units:
            number = unit["unit"][1:]
            cell = QLabel(str(int(number)) if number.isdigit() else unit["unit"])
            cell.setObjectName("unit_" + self.state_of(unit))  # 색을 위젯에 직접 주면 툴팁까지 물들어서 theme.STYLE 에서 줌
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setMinimumHeight(self.cell_height)
            accuracy = "" if unit["accuracy"] is None else " · 정답률 %d%% (%d문항)" % (round(unit["accuracy"] * 100), unit["attempted"])
            cell.setToolTip("%s %s\n%s%s" % (unit["unit"], unit["title"], unit["label"], accuracy))
            self.cells.addWidget(cell, 1)
