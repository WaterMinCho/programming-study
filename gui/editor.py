# -*- coding: utf-8 -*-
"""코드 편집기: 문법 색칠, 들여쓰기와 괄호·따옴표 닫기, 줄 주석, 줄 번호 칸, 찾기 막대.
언어마다 다른 부분은 Lang 프로필(PYTHON, JAVASCRIPT)에 모아 두고 편집기와 색칠이 그것을 읽음."""
import builtins
import keyword
import re

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QKeySequence, QPainter, QShortcut, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTextEdit, QWidget

from gui import theme

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

JS_TOKEN = re.compile(r"""(?P<comment>//)
    |(?P<block>/\*)
    |(?P<quote>`|'|")
    |(?P<number>(?<![\w.$])(?:0x[\da-f_]+|0b[01_]+|0o[0-7_]+|(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:e[+-]?\d+)?n?))
    |(?P<name>(?:[^\W\d]|\$)[\w$]*)""", re.IGNORECASE | re.VERBOSE)
JS_KEYWORDS = frozenset("""break case catch class const continue default delete do else export extends false finally for function if
    import in instanceof let new null of return static super switch this throw true try typeof undefined var void while yield
    async await""".split())
JS_BUILTINS = frozenset("""console Math Array Object Number String Boolean Map Set WeakMap JSON parseInt parseFloat BigInt Symbol
    Infinity NaN Date RegExp Error Promise require""".split())
JS_STRING_END = {quote: re.compile(r"(?:\\.|[^\\])*?" + quote) for quote in ("`", "'", '"')}
JS_STRING_END["/*"] = re.compile(r".*?\*/")


class Lang:
    """편집기와 문법 색칠이 언어마다 다르게 다루는 것. 속성만 있음.

    multiline 은 줄을 넘어 이어지는 문자열·주석의 여는 글자이고, 색칠이 줄마다 적어 두는 상태 n 은 multiline[n-1] 로 연 것 안이라는 뜻.
    block 은 여는 글자가 닫는 글자와 다른 블록 주석의 (여는 글자, 닫는 글자). 따옴표는 여는 글자와 닫는 글자가 같은 pairs 의 글자.
    """

    def __init__(self, name, label, ext, comment, token, multiline, multiline_kind, string_end, pairs, prefix, keywords, builtins,
                 self_word, def_words, decorator, opens_block, electric, block=None):
        self.name, self.label, self.ext, self.comment = name, label, ext, comment
        self.token, self.multiline, self.multiline_kind, self.string_end = token, multiline, multiline_kind, string_end
        self.pairs, self.prefix, self.keywords, self.builtins = pairs, prefix, keywords, builtins
        self.self_word, self.def_words, self.decorator, self.electric, self.block = self_word, def_words, decorator, electric, block
        self.opens_block = opens_block
        self.openers = {close: ch for ch, close in pairs.items() if ch != close}
        self.quotes = tuple(ch for ch, close in pairs.items() if ch == close)  # 빈 글이 들어 있다고 보지 않게 글이 아니라 튜플


def opens_block_py(before):
    return before.rstrip().endswith(":")


def opens_block_js(before):
    return scan(before, lang=JAVASCRIPT)[0].rstrip().endswith(("{", "[", "("))


PYTHON = Lang(name="python", label="Python", ext=".py", comment="#", token=TOKEN, multiline=TRIPLE, multiline_kind=("string", "string"),
              string_end=STRING_END, pairs=PAIRS, prefix=STRING_PREFIX, keywords=KEYWORDS, builtins=BUILTINS, self_word="self",
              def_words=("def", "class"), decorator=DECORATOR, opens_block=opens_block_py, electric="")
JAVASCRIPT = Lang(name="javascript", label="JavaScript", ext=".js", comment="//", token=JS_TOKEN, multiline=("`", "/*"),
                  multiline_kind=("string", "comment"), string_end=JS_STRING_END, pairs=dict(PAIRS, **{"`": "`"}), prefix=None,
                  keywords=JS_KEYWORDS, builtins=JS_BUILTINS, self_word="this", def_words=("function", "class"), decorator=None,
                  opens_block=opens_block_js, electric="}])", block=("/*", "*/"))
LANGS = {"python": PYTHON, "javascript": JAVASCRIPT}


def scan(text, state="", lang=PYTHON):
    """한 줄에서 문자열과 주석을 뺀 코드 글자와 끝난 자리의 상태를 돌려줌. state 는 앞줄에서 이어진 여러 줄 문자열·주석의 여는 글자.

    상태는 코드면 빈 글, 줄 끝까지 주석이면 lang.comment, 문자열 안이면 그 따옴표(삼중 따옴표면 세 글자), 블록 주석 안이면 그 여는 글자,
    문자열 안의 역슬래시 바로 뒤면 역슬래시.
    """
    block = lang.block or ("", "")
    code, escaped, at = [], False, 0
    while at < len(text) and state != lang.comment:
        ch = text[at]
        if escaped:
            escaped = False
        elif state:
            in_block = state == block[0]
            close = block[1] if in_block else state
            escaped = ch == "\\" and not in_block
            if text.startswith(close, at):
                state, at = "", at + len(close) - 1
        elif ch in lang.quotes:
            state = ch * 3 if ch * 3 in lang.multiline and text.startswith(ch * 3, at) else ch
            at += len(state) - 1
        elif text.startswith(lang.comment, at):
            state = lang.comment
            at += len(state) - 1
        elif block[0] and text.startswith(block[0], at):
            state = block[0]
            at += len(state) - 1
        else:
            code.append(ch)
        at += 1
    return "".join(code), "\\" if escaped else state


def line_at(cur):
    """커서가 있는 줄의 글과 그 줄에서 커서 앞에 있는 글자 수. Qt 는 이모지 같은 글자를 두 칸으로 세어서 파이썬의 글자 수로 바꿈."""
    text, at = cur.block().text(), cur.positionInBlock()
    return text, at if text.isascii() else len(text.encode("utf-16-le", "surrogatepass")[:2 * at].decode("utf-16-le", "surrogatepass"))


def carried(cur, lang=PYTHON):
    """앞줄에서 이어진 여러 줄 문자열·주석의 여는 글자. 문법 색칠이 줄마다 적어 둔 상태에서 읽음."""
    state = cur.block().previous().userState()
    return lang.multiline[state - 1] if state > 0 else ""


class PlainEdit(QPlainTextEdit):
    """붙여넣기를 받지 않는 여러 줄 입력칸. 어느 길로 붙여넣든 insertFromMimeData 를 거치므로 여기서 버림."""

    def canInsertFromMimeData(self, source):
        return False

    def insertFromMimeData(self, source):
        pass


class Highlighter(QSyntaxHighlighter):
    """lang 의 문법에 따라 글자색을 입힘. 색은 줄의 배치에만 얹혀서 글과 실행 취소 기록이 바뀌지 않음.
    줄의 상태는 여러 줄 문자열·주석이 다음 줄로 이어지는지를 나타냄: 0 은 코드, n 은 lang.multiline[n-1] 로 연 것 안."""

    def __init__(self, document, lang=PYTHON):
        super().__init__(document)
        self.lang = lang
        self.formats = {}
        for kind in ("keyword", "def", "builtin", "string", "comment", "number", "decorator", "self", "blank"):
            self.formats[kind] = QTextCharFormat()
            self.formats[kind].setForeground(theme.editor(kind))
        self.formats["blank"].setBackground(theme.editor("blank_bg"))

    def highlightBlock(self, text):
        lang = self.lang
        wide = [at for at, ch in enumerate(text) if ch > "\uffff"] if not text.isascii() else []

        def paint(start, end, kind):
            if wide:  # Qt 는 이모지 같은 글자를 두 칸으로 셈
                start, end = (at + sum(1 for spot in wide if spot < at) for at in (start, end))
            self.setFormat(start, end - start, self.formats[kind])

        at, state, named = 0, max(self.previousBlockState(), 0), 0  # named 는 방금 지나온 def·class 의 끝
        if state:  # 앞줄에서 연 문자열이나 주석이 이어짐
            opener = lang.multiline[state - 1]
            end = lang.string_end[opener].match(text)
            paint(0, end.end() if end else len(text), lang.multiline_kind[state - 1])
            at, state = (end.end(), 0) if end else (len(text), state)
        elif lang.decorator:
            mark = lang.decorator.match(text)
            if mark:
                at = mark.end()
                paint(mark.start(1), at, "decorator")
        while not state:
            found = lang.token.search(text, at)
            if not found:
                break
            kind, start, at = found.lastgroup, found.start(), found.end()
            if kind == "comment":
                paint(start, len(text), kind)
                break
            if kind in ("quote", "block"):
                opener = found.group(kind)
                end = lang.string_end[opener].match(text, at)
                at = end.end() if end else len(text)  # 닫지 않은 문자열·주석은 줄 끝까지
                if not end and opener in lang.multiline:
                    state = lang.multiline.index(opener) + 1
                paint(start, at, "comment" if kind == "block" else "string")
            elif kind == "name":
                word, kind = found.group(), ""
                attribute = text[start - 1:start] == "."  # 점 뒤의 이름은 속성이라 칠하지 않음
                if named and text[named:start].isspace():
                    kind = "def"
                elif word == lang.self_word and not attribute:  # JS 의 this 는 예약어이기도 해서 예약어보다 먼저 봄
                    kind = "self"
                elif word in lang.keywords:
                    kind = "keyword"
                elif not attribute:
                    kind = "builtin" if word in lang.builtins else ""
                named = at if word in lang.def_words else 0
                if kind:
                    paint(start, at, kind)
            else:
                paint(start, at, kind)
        for blank in BLANK.finditer(text):
            paint(blank.start(), blank.end(), "blank")
        self.setCurrentBlockState(state)


class CodeEditor(PlainEdit):
    """시험 화면처럼 남색 바탕에 lang 의 문법대로 글자색을 입힌 편집기. 고정폭이고 자동완성이 없음.
    들여쓰기와 괄호·따옴표 닫기, Ctrl+/ 줄 주석을 돕고 탭 문자는 넣지 않음. paste 가 참일 때만 붙여넣기를 글자로 받음(allow_paste)."""

    def __init__(self, parent=None, lang=PYTHON, paste=False):
        super().__init__(parent)
        self.lang, self.allow_paste = lang, paste
        self.setObjectName("code")  # 색은 theme.EDITOR_STYLE 이 줌
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setCursorWidth(2)
        self.document().setDocumentMargin(8)  # 줄 번호 칸과 글 사이를 띄움
        self.highlighter = Highlighter(self.document(), lang)
        self.head = 0  # 본문 위에 비워 둔 높이. 찾기 막대가 뜨면 그 자리가 됨
        self.numbers = LineNumbers(self)
        self.blockCountChanged.connect(self.fit_numbers)
        self.updateRequest.connect(lambda rect, dy: self.numbers.update())
        self.cursorPositionChanged.connect(self.numbers.update)
        self.fit_numbers()

    def set_lang(self, lang):
        """언어 프로필을 바꾸고 글 전체를 다시 칠함."""
        self.lang = self.highlighter.lang = lang
        self.highlighter.rehighlight()

    def canInsertFromMimeData(self, source):
        return self.allow_paste and source.hasText()

    def insertFromMimeData(self, source):
        """paste 편집기만 받음. 서식이 있는 글도 글자만 넣음."""
        if self.allow_paste and source.hasText():
            cur = self.textCursor()
            cur.insertText(source.text())
            self.setTextCursor(cur)
            self.ensureCursorVisible()

    def keyPressEvent(self, event):
        key, cur, ch = event.key(), self.textCursor(), event.text()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        back = key == Qt.Key.Key_Backtab or (key == Qt.Key.Key_Tab and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
        if self.isReadOnly():
            super().keyPressEvent(event)
        elif back or (key == Qt.Key.Key_Tab and cur.hasSelection()):
            self._shift_lines(-1 if back else 1)
        elif key == Qt.Key.Key_Tab:
            cur.insertText(" " * (INDENT - cur.positionInBlock() % INDENT))
        elif key == Qt.Key.Key_Slash and ctrl:  # Ctrl+/ (맥은 Cmd+/)
            self._toggle_comment()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cur.beginEditBlock()
            cur.removeSelectedText()
            text, at = line_at(cur)
            before = text[:at]
            pad = before[:len(before) - len(before.lstrip(" "))]
            tail = "\n" + pad if self._empty_pair(cur) in ("()", "[]", "{}") else ""  # 빈 괄호 사이면 닫는 괄호를 원래 들여쓰기의 새 줄로 내림
            if tail or self.lang.opens_block(before):
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
        elif ch and ch in self.lang.electric and not ctrl and not cur.hasSelection() and self._in_indent(cur):
            cur.beginEditBlock()  # 빈칸만 있는 줄에서 닫는 괄호를 치면 한 단계 내어쓰고 넣음. 되돌리기 한 번에 둘 다 돌아감
            for _ in range((cur.positionInBlock() - 1) % INDENT + 1):
                cur.deletePreviousChar()
            if not self._pair(event, cur):
                cur.insertText(ch)
            cur.endEditBlock()
            self.setTextCursor(cur)
        elif not self._pair(event, cur):
            super().keyPressEvent(event)

    @staticmethod
    def _in_indent(cur):
        before = cur.block().text()[:cur.positionInBlock()]
        return bool(before) and not before.strip(" ")

    def _empty_pair(self, cur):
        """커서가 빈 쌍 사이면 그 두 글자, 아니면 빈 글. 문자열과 주석 안의 글자는 쌍으로 보지 않음."""
        text, at = line_at(cur)
        pair = text[max(at - 1, 0):at + 1]
        if len(pair) < 2 or self.lang.pairs.get(pair[0]) != pair[1] or scan(text[:at - 1], carried(cur, self.lang), self.lang)[1]:
            return ""
        return pair

    def _pair(self, event, cur):
        """괄호·따옴표 키면 닫는 글자를 같이 넣거나 이미 있는 닫는 글자를 넘어가고 True 를 돌려줌. 글자만 넣으면 될 때는 False.

        자판 배열과 입력기에 따라 키 코드가 달라서 들어갈 글자로 판단함.
        """
        lang, ch, ctrl = self.lang, event.text(), Qt.KeyboardModifier.ControlModifier
        close, opener = lang.pairs.get(ch), lang.openers.get(ch)
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
        inside = carried(cur, lang)
        prev, after, state = text[:at][-1:], text[at:at + 1], scan(text[:at], inside, lang)[1]
        quote = ch == close
        if state == "\\" or (state and not quote):  # 역슬래시 뒤의 글자와 문자열·주석 안의 괄호는 그대로 들어감
            return False
        if after == ch and (state == ch if quote else opener):  # 따옴표는 그 문자열을 닫는 것일 때만 넘어감
            code, end = scan(text, inside, lang)
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
        if quote and (state or prev in lang.quotes or (word and not (lang.prefix and lang.prefix.search(text[:at])))):
            return False
        if after and not after.isspace() and after not in ")]},:":  # 뒤에 글자가 이어지면 닫지 않음
            return False
        if not quote:  # 아랫줄에서 닫히는 괄호가 열려 있는 줄에서는 닫지 않음. 닫으면 친 닫는 괄호가 넘어가지 못해 하나 남음
            code = scan(text, inside, lang)[0]
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

    def _toggle_comment(self):
        """고른 줄(없으면 커서가 있는 줄)을 주석으로 만들거나 풂. 빈 줄을 뺀 모든 줄이 이미 주석이면 풀고, 아니면 모두 주석으로 만듦.
        주석 글자는 고른 줄 가운데 가장 얕은 들여쓰기 자리에 넣어서 들여쓰기 모양이 그대로 남음. 한 번에 되돌아가게 한 덩어리로 고침."""
        cur, doc, comment = self.textCursor(), self.document(), self.lang.comment
        first = doc.findBlock(cur.selectionStart()).blockNumber()
        last = doc.findBlock(max(cur.selectionStart(), cur.selectionEnd() - 1)).blockNumber()
        lines = [doc.findBlockByNumber(number) for number in range(first, last + 1)]
        lines = [block for block in lines if block.text().strip()]
        if not lines:
            return
        indents = [len(block.text()) - len(block.text().lstrip(" ")) for block in lines]
        undo = all(block.text().lstrip(" ").startswith(comment) for block in lines)
        cur.beginEditBlock()
        for block, indent in zip(lines, indents):
            edit = QTextCursor(block)
            if undo:
                width = len(comment) + 1 if block.text()[indent + len(comment):indent + len(comment) + 1] == " " else len(comment)
                edit.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, indent)
                edit.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, width)
                edit.removeSelectedText()
            else:
                edit.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, min(indents))
                edit.insertText(comment + " ")
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
        corner = LineNumbers.corner(self)  # 편집기의 둥근 테두리 안쪽을 따라 왼쪽 모서리만 둥글게 칠함. 오른쪽 모서리는 칸 밖에 놓임
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
    PAD, CORNER = 8, 5  # 번호 양옆의 여백, 왼쪽 모서리의 반지름(편집기 테두리 모서리 6 에서 테두리 1 을 뺌)

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    @staticmethod
    def corner(editor):
        """왼쪽 모서리의 반지름. 편집기 테두리 모서리에서 테두리 1px 를 뺀 값임. 새 화면 규칙(ui="2") 안에서는 theme.STYLE_V2 가
        테두리 모서리를 12 로 주어 11 이고 밖에서는 CORNER 임. 더 작은 반지름으로 칠하면 칸 모서리가 테두리 밖으로 나와 둥근 테두리 선을 덮음."""
        widget = editor
        while widget is not None:
            if widget.property("ui") == "2":
                return theme.RADIUS["control"] - 1
            widget = widget.parentWidget()
        return LineNumbers.CORNER

    def paintEvent(self, event):
        self.editor.paint_numbers(event)

    def wheelEvent(self, event):
        QApplication.sendEvent(self.editor.viewport(), event)


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
