# -*- coding: utf-8 -*-
"""여정 문제 화면의 지문·힌트·해설 칸(DocView), 스크롤하지 않는 글(Doc), 해설 그림(FigureView), 그림을 그린 크기로 보는 창(FigureDialog).
웹 면접 준비의 미션 안내·학습 노트도 같은 부품을 씀.

DocView 는 마크다운을 글 조각(QTextBrowser)과 그림 조각으로 나눠 위에서 아래로 쌓고, 기준 풀이 같은 코드 조각과 표·문단을 뒤에 더함.
조각은 스크롤 막대 없이 내용 높이만큼 늘어나고 바깥 스크롤 하나로 읽음. 글은 새 화면 문서 규칙(theme.journey_css 는 web_css 와 같음)으로
그리고, ruled 면 칸 맨 위가 아닌 구역 제목(2·3단계) 앞에 가로줄을 넣음. 칸이 좁으면(TIGHT_WIDTH) 표 칸과 코드 상자의 가로 여백을 줄임.
카드 안에 두는 칸은 flat 으로 만들어 바탕을 칠하지 않음. 조각 목록 밖 맨 위·맨 아래에는 set_head·set_tail 로 위젯을 둠."""
import html
import math
import os

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFontMetricsF, QMovie, QPainter, QPainterPath, QPen, QPixmap, QTextCursor, QTextFrame, QTextLength, QTextTable
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget

import mdlite
from gui import kit, motion, theme
from gui.editor import LANGS, CodeEditor

CODE_MARKS = {"python": ("python", "py"), "javascript": ("javascript", "js")}  # 펜스 코드 블록에 붙는 언어 표시
SCALE = 2  # 그림 파일은 화면에 보일 크기의 2배로 그려 둠
NARROW_CSS = "pre { white-space: pre-wrap; }"  # 글 조각은 가로 스크롤이 없으므로 긴 코드 줄을 조각 폭에서 줄바꿈함
RULED = (2, 3)  # 앞에 가로줄을 넣는 제목 단계. 지문·해설의 구역 제목은 2단계, 힌트 제목은 3단계임
CODE_RADIUS = theme.RADIUS["control"]  # 코드 상자와 해설 그림의 모서리 반지름(12)
CODE_MARGIN = (16, 10)  # 코드 상자의 초기 바깥 여백. 문단 사이 간격은 실제 글꼴과 줄 위치로 보정함.
# 문단의 아래 여백은 다음 블록의 위 여백과 겹치지만 표의 여백은 더해지므로, 상자 뒤 블록에 위 여백(제목의 24)이 있으면 그만큼 아래 여백을 뺌
CODE_SPILL = 4  # 그 빈 줄이 상자 아래로 삐져나오는 높이. 조각 끝 상자는 아래 여백을 이만큼 당겨 조각이 상자 끝에서 끝나게 함
PAD = 24  # DocView 의 안쪽 여백
GAP = theme.GAP["paragraph"]  # DocView 조각 사이를 문단 간격으로 띄움.
TIGHT_WIDTH = 500  # 칸이 이보다 좁으면(1024 폭 창의 왼쪽 칸) 표 칸과 코드 상자의 가로 여백을 줄임
TIGHT_CSS = "table.grid th { padding: 8px 8px; } table.grid td { padding: 4px 8px 8px 8px; } td.codebox { padding: 12px 12px; }"
MISSING_TEXT = "그림을 불러오지 못했습니다."  # 없는 그림 자리의 안내. 경로는 도움말에 둠


def keep_lang(blocks, lang):
    """다른 언어의 코드 블록을 뺀 블록 목록. 언어 표시가 없거나 두 언어가 아닌 블록은 남김. 목록 항목과 인용 안도 거름."""
    other = {mark for name, marks in CODE_MARKS.items() if name != lang for mark in marks}
    out = []
    for block in blocks:
        if block["t"] == "code" and block["lang"].lower() in other:
            continue
        if "items" in block:
            block = dict(block, items=[keep_lang(item, lang) for item in block["items"]])
        elif "blocks" in block:
            block = dict(block, blocks=keep_lang(block["blocks"], lang))
        out.append(block)
    return out


def cell_text(cell):
    """표 칸의 글."""
    cursor = cell.firstCursorPosition()
    cursor.setPosition(cell.lastCursorPosition().position(), QTextCursor.MoveMode.KeepAnchor)
    return cursor.selectedText()


def word_width(cell):
    """칸 글에서 띄어쓰기 없이 이어진 가장 긴 덩어리의 폭. 글 조각마다 그 조각의 글꼴(머리 칸의 굵은 글, 코드 글꼴)로 잼."""
    widest, block = 0.0, cell.firstCursorPosition().block()
    last, base = cell.lastCursorPosition().block().blockNumber(), block.document().defaultFont()
    while block.isValid() and block.blockNumber() <= last:
        part = block.begin()
        while not part.atEnd():
            fragment = part.fragment()
            metrics = QFontMetricsF(fragment.charFormat().font().resolve(base))
            widest = max([widest] + [metrics.horizontalAdvance(word) for word in fragment.text().split()])
            part += 1
        block = block.next()
    return widest


def shares(weights, least, room):
    """열 폭의 비율. weights 에 비례해 room 을 나누되 least 보다 좁아지는 열은 least 로 묶고 나머지를 다시 나눔.
    least 의 합이 room 보다 크면 least 에 비례함."""
    widths = [None] * len(weights)
    while True:
        free = [n for n, width in enumerate(widths) if width is None]
        left = room - sum(width for width in widths if width is not None)
        total = sum(weights[n] for n in free) or 1
        narrow = [n for n in free if left * weights[n] / total < least[n]]
        if not narrow:
            break
        for n in narrow:
            widths[n] = least[n]
    widths = [left * weights[n] / total if width is None else width for n, width in enumerate(widths)]
    total = sum(widths) or 1
    return [width / total for width in widths]


def spread(table, width):
    """표를 조각 폭 width 에 꽉 채우고, 열 폭을 그 열에서 가장 긴 칸 글의 길이에 비례해 나눔. 열마다 띄어쓰기 없는 가장 긴 덩어리와
    칸 좌우 여백이 들어가는 폭은 남겨서 짧은 열의 머리가 한 글자씩 줄을 바꾸지 않음.
    Qt 가 정하는 폭은 긴 목록이 든 열을 좁혀 원소마다 줄을 바꾸고 짧은 열은 비워 두어서 직접 나눔."""
    box = table.format()
    edge = 2 * box.border() + box.cellSpacing() + 1  # 칸 테두리와 칸 사이, 반올림 몫
    weights, least = [], []
    for column in range(table.columns()):
        cells = [table.cellAt(row, column) for row in range(table.rows())]
        weights.append(max(len(cell_text(cell)) for cell in cells) or 1)
        pads = [cell.format().toTableCellFormat() for cell in cells]
        least.append(max(word_width(cell) + pad.leftPadding() + pad.rightPadding() for cell, pad in zip(cells, pads)) + edge)
    room = max(1.0, width - box.leftMargin() - box.rightMargin() - 2 * box.border())
    box.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
    box.setColumnWidthConstraints([QTextLength(QTextLength.Type.PercentageLength, 100 * share)
                                   for share in shares(weights, least, room)])
    table.setFormat(box)


def parts_of(text, base_dir, lang):
    """마크다운을 쌓을 차례대로 나눠 내놓음. 그림 줄 사이의 블록들은 한 목록으로, 그림 줄은 그림 조각(FigureView)으로 내놓고
    그림 파일을 읽지 못하면 설명과 재시도를 보임. 이미지 줄의 경로는 base_dir 에서 찾음. DocView 와 Doc 이 같이 씀."""
    run = []
    for block in keep_lang(mdlite.parse(text), lang):
        if block["t"] != "image":
            run.append(block)
            continue
        if run:
            yield run
        run = []
        figure = FigureView(os.path.join(base_dir, block["src"]), block["alt"])
        figure.error_box.setToolTip(block["src"])
        yield figure
    if run:
        yield run


def stacked_tables(blocks):
    """좁은 표를 열별 설명으로 바꿈. 첫 열의 항목 이름과 각 열의 값을 같은 문단에 둠."""
    out = []
    for block in blocks:
        if block["t"] == "table" and len(block["head"]) > 2:
            first, *heads = block["head"]
            for column, title in enumerate(heads, 1):
                out.append({"t": "heading", "level": 2, "text": "%s · %s" % (first, title) if first else title})
                for row in block["rows"]:
                    label = row[0] if row else ""
                    value = row[column] if column < len(row) else ""
                    out.append({"t": "para", "text": "%s: %s" % (label, value) if label else value})
        elif "blocks" in block:
            out.append(dict(block, blocks=stacked_tables(block["blocks"])))
        elif "items" in block:
            out.append(dict(block, items=[stacked_tables(item) for item in block["items"]]))
        else:
            out.append(block)
    return out


class Sheet(QWidget):
    """조각을 얹는 바탕. 칠할 때마다 지금 테마의 surface 색을 읽어서 테마를 바꿔도 따로 다시 칠할 일이 없음.
    flat 이면 칠하지 않음. 카드 안에 둔 칸은 카드가 면과 둥근 모서리를 그림."""

    def __init__(self, flat=False):
        super().__init__()
        self.flat = flat

    def paintEvent(self, event):
        if not self.flat:
            QPainter(self).fillRect(event.rect(), theme.qcolor("surface"))


class TextPiece(QTextBrowser):
    """글 조각. 폭이 바뀌면 높이를 내용에 맞춤. 휠은 바깥 스크롤로 넘겨서 Ctrl+휠로 이 조각만 글자가 커지는 일도 없음."""

    def __init__(self, markup, css, blocks=None):
        super().__init__()
        self.markup = markup
        self.blocks = blocks
        self.compact = False
        self.table_width = 0
        self.fitting = False
        self.spread_width = None  # 표의 열 폭을 나눈 조각 폭. 폭이 바뀌면 다시 나눔
        self.setOpenLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QTextBrowser { background: transparent; border: 0; padding: 0; }")  # 앱 전체의 입력칸 여백이 붙지 않게
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(0)
        self.restyle(css)

    def restyle(self, css):
        """CSS 는 다음에 넣는 HTML 부터 적용되므로 HTML 을 다시 넣음."""
        self.document().setDefaultStyleSheet(css + NARROW_CSS)
        self.compact = False
        self.table_width = 0
        self.render_markup(self.markup)
        self.table_width = max((sum(max(word_width(table.cellAt(row, col))
            + table.cellAt(row, col).format().toTableCellFormat().leftPadding()
            + table.cellAt(row, col).format().toTableCellFormat().rightPadding()
            for row in range(table.rows())) + 4 for col in range(table.columns()))
            for table in self.grid_tables() if table.columns() > 2), default=0) if self.blocks else 0
        self.fit()

    def render_markup(self, markup):
        """문서를 다시 넣고 코드 상자의 여백을 적용함."""
        self.setHtml(markup)
        self.document().setTextWidth(max(1, self.viewport().width()))  # 폭이 없으면 줄을 앉히지 않아 center_code 가 줄 자리를 못 읽음
        following = self.following_margins()
        for frame in self.code_frames():
            box = frame.format()
            box.setTopMargin(CODE_MARGIN[0])
            box.setBottomMargin(max(0, CODE_MARGIN[1] - following.get(frame, 0)))
            frame.setFormat(box)
        self.trim_ends()
        self.spread_width = None

    def following_margins(self):
        """문서 맨 바깥의 표마다 그 뒤 첫 글 블록의 위 여백 {표: 여백}. Qt 가 표 바로 뒤에 두는 빈 블록은 건너뜀."""
        items, part = [], self.document().rootFrame().begin()
        while not part.atEnd():
            items.append(part.currentFrame() or part.currentBlock())
            part += 1
        out = {}
        for index, item in enumerate(items):
            if not isinstance(item, QTextFrame):
                continue
            after = items[index + 1:index + 3]
            if after and not isinstance(after[0], QTextFrame) and not after[0].text():
                after = after[1:]
            if after and not isinstance(after[0], QTextFrame):
                out[item] = after[0].blockFormat().topMargin()
        return out

    def center_code(self, frame):
        """글자의 위아래 경계로 코드 여백을 맞춤. 줄 높이만 쓰면 글꼴에 따라 글자가 아래로 치우칠 수 있음."""
        cell = frame.cellAt(0, 0)
        first = self.ink_bounds(cell.firstCursorPosition().block())
        last = self.ink_bounds(cell.lastCursorPosition().block(), last=True)
        if first is None or last is None:
            return
        rect = self.code_box(frame)
        shift = ((rect.bottom() - last.bottom()) - (first.top() - rect.top())) / 2
        pad = cell.format().toTableCellFormat()
        pad.setTopPadding(pad.topPadding() + shift)
        pad.setBottomPadding(pad.bottomPadding() - shift)
        cell.setFormat(pad)

    def ink_bounds(self, block, last=False):
        """첫 줄이나 끝 줄의 글자 경계를 문서 좌표로 구함. Qt의 문자 위치는 UTF-16 기준임."""
        origin = self.document().documentLayout().blockBoundingRect(block).topLeft()
        layout = block.layout()
        if not block.text().strip() or not layout.lineCount():
            return None
        line = layout.lineAt(layout.lineCount() - 1 if last else 0)
        encoded = block.text().encode("utf-16-le")
        text = encoded[2 * line.textStart():2 * (line.textStart() + line.textLength())].decode("utf-16-le")
        font = block.charFormat().font().resolve(self.document().defaultFont())
        rect = QFontMetricsF(font).tightBoundingRect(text)
        return rect.translated(origin + QPointF(line.x(), line.y() + line.ascent()))

    def balance_code_gaps(self):
        """일반 문단 사이 코드 상자의 앞뒤 간격을 맞춤. 제목에 지정한 위 여백은 따로 유지함."""
        items, part = [], self.document().rootFrame().begin()
        while not part.atEnd():
            item = part.currentFrame() or part.currentBlock()
            if isinstance(item, QTextFrame) or item.text():
                items.append(item)
            part += 1
        codes = self.code_frames()
        for index, frame in enumerate(items[1:-1], 1):
            if not isinstance(frame, QTextFrame) or frame not in codes:
                continue
            before, after = items[index - 1], items[index + 1]
            if isinstance(before, QTextFrame) or isinstance(after, QTextFrame):
                continue
            if before.blockFormat().bottomMargin() != GAP or after.blockFormat().topMargin():
                continue
            first, last = self.ink_bounds(after), self.ink_bounds(before, last=True)
            if first is None or last is None:
                continue
            rect = self.code_box(frame)
            above = math.ceil(rect.top() - last.bottom()) - 1
            below = math.floor(first.top() - rect.bottom()) - 1
            box = frame.format()
            box.setBottomMargin(box.bottomMargin() + above - below)
            frame.setFormat(box)

    def trim_ends(self):
        """조각 맨 위와 맨 아래의 바깥 여백을 없앰. 조각 앞뒤 간격은 DocView 의 안쪽 여백과 조각 사이가 줌. 맨 위가 절 제목이면 CSS 의
        위 여백 24 가, 코드 상자면 CODE_MARGIN 이 그 간격에 더해지던 것. 코드 상자로 시작하거나 끝나는 글은 상자 앞뒤에 빈 블록이 있음."""
        items, part = [], self.document().rootFrame().begin()
        while not part.atEnd():
            items.append(part.currentFrame() or part.currentBlock())
            part += 1
        first = items[0]
        if not isinstance(first, QTextFrame):
            format_ = first.blockFormat()
            format_.setTopMargin(0)
            QTextCursor(first).setBlockFormat(format_)
        filled = [item for item in items if isinstance(item, QTextFrame) or item.text()]
        codes = self.code_frames()
        for item, side in ((filled[0], "top"), (filled[-1], "bottom")) if filled else ():
            if isinstance(item, QTextFrame) and item in codes:
                box = item.format()
                if side == "top":
                    box.setTopMargin(0)
                else:
                    box.setBottomMargin(-CODE_SPILL)
                item.setFormat(box)

    def fit(self):
        """문서 높이 전체를 씀. content_height 처럼 마지막 줄 아래 간격을 빼면 그만큼 안에서 스크롤돼서, 글을 끌어 고르거나
        키로 움직일 때 첫 줄이 위로 밀림. 보이기 전에는 QTextBrowser 가 문서 폭을 정하지 않아 줄이 앉지 않으므로 폭을 먼저 줌.
        이미 자리 잡은 칸에 새로 들어온 조각은 보일 때의 resizeEvent 안에서 높이를 바꾸는데, 이 높이 변경은 resizeEvent 로 다시
        오지 않아 스크롤 범위가 만들 때의 낮은 높이 기준으로 남음. 조각은 안에서 스크롤하지 않으므로 범위를 0 으로 둠."""
        if self.fitting:
            return
        self.fitting = True
        try:
            width = self.viewport().width()
            compact = bool(self.blocks and width + 1 < self.table_width)
            if compact != self.compact:
                self.compact = compact
                self.render_markup(mdlite.blocks_html(stacked_tables(self.blocks)) if compact else self.markup)
            self.document().setTextWidth(width)
            if width != self.spread_width:
                self.spread_width = width
                for table in self.grid_tables():
                    spread(table, width)
                for frame in self.code_frames():
                    self.center_code(frame)
                self.balance_code_gaps()
            self.setFixedHeight(math.ceil(self.document().size().height()))
            self.verticalScrollBar().setRange(0, 0)
        finally:
            self.fitting = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def wheelEvent(self, event):
        event.ignore()

    def tables(self):
        """문서의 표들. 인용 상자 안의 코드 상자처럼 표 안에 든 표도 봄."""
        found, frames = [], self.document().rootFrame().childFrames()
        while frames:
            frame = frames.pop()
            frames.extend(frame.childFrames())
            if isinstance(frame, QTextTable):
                found.append(frame)
        return found

    def code_frames(self):
        """코드 블록 하나가 든 1x1 표(mdlite 의 코드 상자)들. 테두리가 없고 첫 글자가 코드 글꼴인 1x1 표로 알아봄."""
        mono = theme.code_families()[:1]
        return [frame for frame in self.tables() if frame.rows() == frame.columns() == 1 and not frame.format().border()
                and (frame.cellAt(0, 0).firstCursorPosition().block().charFormat().fontFamilies() or [])[:1] == mono]

    def grid_tables(self):
        """마크다운 표(mdlite 의 class="grid")들. 코드·인용 상자와 달리 테두리가 있고 열이 둘 이상임."""
        return [frame for frame in self.tables() if frame.format().border() and frame.columns() > 1]

    def code_boxes(self):
        """코드 상자마다 화면 위의 사각형. 칸 안 첫 블록과 끝 블록의 사각형에 칸 여백을 더해 셈. 블록 사각형은 줄 위의 넓힌 간격을
        넣고 끝 줄 아래 끝까지는 넣지 않으므로, center_code 가 고친 여백을 더하면 글 줄 위아래가 같은 12 가 됨."""
        return [self.code_box(frame) for frame in self.code_frames()]

    def code_box(self, frame):
        layout = self.document().documentLayout()
        cell = frame.cellAt(0, 0)
        pad = cell.format().toTableCellFormat()
        top = layout.blockBoundingRect(cell.firstCursorPosition().block())
        bottom = layout.blockBoundingRect(cell.lastCursorPosition().block())
        return QRectF(top.left() - pad.leftPadding(), top.top() - pad.topPadding(),
                      top.width() + pad.leftPadding() + pad.rightPadding(),
                      bottom.bottom() - top.top() + pad.topPadding() + pad.bottomPadding())

    def paintEvent(self, event):
        """Qt 의 표는 모서리를 둥글게 그리지 못해서 코드 상자의 바탕을 글보다 먼저 그림. 상자는 테두리 없이 surface_alt 로 채움.
        상자 칸의 바탕은 CSS 에서 투명하게 둠."""
        boxes = self.code_boxes()
        if boxes:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("surface_alt"))
            for rect in boxes:
                painter.drawRoundedRect(rect, CODE_RADIUS, CODE_RADIUS)
            painter.end()
        super().paintEvent(event)


class CodeView(CodeEditor):
    """읽기 전용 코드 조각. 문법 색은 편집기와 같고, 세로 스크롤 없이 줄 수만큼 늘어남. 긴 줄은 가로로 스크롤함."""

    def __init__(self, code, lang, font):
        super().__init__(lang=LANGS[lang])
        self.setReadOnly(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setPlainText(code.rstrip("\n"))  # 파일 끝 줄바꿈으로 빈 줄 번호가 하나 더 보이지 않게 함
        self.setFont(font)

    def setFont(self, font):
        super().setFont(font)
        self.fit()

    def fit(self):
        """줄 높이의 합에 문서 여백과 테두리를 더한 높이. 가로 스크롤 막대가 뜨면 그 높이도 더함."""
        lines, block = 0.0, self.document().firstBlock()
        while block.isValid():
            lines += self.blockBoundingRect(block).height()
            block = block.next()
        bar = self.horizontalScrollBar()
        extra = bar.sizeHint().height() if bar.maximum() > 0 else 0
        self.setFixedHeight(math.ceil(lines + 2 * self.document().documentMargin() + 2 * self.frameWidth()) + extra)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def wheelEvent(self, event):
        if event.angleDelta().x() and not event.angleDelta().y():
            super().wheelEvent(event)
        else:
            event.ignore()


class DocView(QScrollArea):
    """지문·힌트·해설 한 칸. set_markdown 으로 내용을 바꾸고 add_* 로 뒤에 조각을 더함.
    lang 은 "python" 이나 "javascript" 이고, 그 언어가 아닌 코드 블록은 보이지 않음.
    flat 이면 바탕을 칠하지 않고 flat 속성을 달아 카드 안 스크롤 칸의 투명 규칙(theme.STYLE_V2)을 받음."""
    linked = pyqtSignal(str)  # 글 조각의 링크를 눌렀을 때. 주소

    def __init__(self, parent=None, flat=False):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.flat = flat
        if flat:
            self.setProperty("flat", True)
        self.sheet = Sheet(flat)
        self.box = QVBoxLayout(self.sheet)
        self.box.setContentsMargins(PAD, PAD, PAD, PAD)
        self.box.setSpacing(GAP)
        self.box.addStretch(1)
        self.setWidget(self.sheet)
        if flat:
            self.sheet.setAutoFillBackground(False)  # setWidget 이 켜 둔 창 바탕(bg) 칠하기도 끔
        self.pieces = []  # 쌓은 순서대로의 조각: TextPiece, FigureView, CodeView, 없는 그림 안내(Para)
        self.head = self.tail = None  # 조각 목록 밖 맨 위·맨 아래 위젯. set_markdown 과 clear 가 지우지 않음
        self.css, self.code_font = theme.journey_css(), theme.code_font(theme.text_px() - 1)  # 기준 풀이는 문서 코드와 같은 code 크기
        self.tight = False  # 칸이 TIGHT_WIDTH 보다 좁은지. resizeEvent 가 바꿈
        self.ruled = True  # 구역 제목 앞에 가로줄을 넣는지. 웹 면접 준비 화면은 줄 없이 제목 위 여백만 둠

    def sheet_css(self):
        """글 조각에 주는 CSS. 칸이 좁으면 여백을 줄이는 규칙을 더함."""
        return self.css + (TIGHT_CSS if self.tight else "")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        tight = self.width() < TIGHT_WIDTH
        if tight != self.tight:
            self.tight = tight
            self.restyle(self.css, self.code_font)

    def clear(self):
        for piece in self.pieces:
            self.box.removeWidget(piece)
            piece.hide()
            piece.deleteLater()
        self.pieces = []

    def set_head(self, widget):
        """조각 목록 위에 widget 을 둠(지문 머리). 앞에 둔 위젯은 빼서 숨김. None 이면 빼기만 함."""
        self._place("head", widget)

    def set_tail(self, widget, flush=False):
        """조각 목록 아래, 남는 칸 앞에 widget 을 둠(힌트 꼬리). 앞에 둔 위젯은 빼서 숨김. None 이면 빼기만 함.
        flush 면 kit.FLUSH 만큼 왼쪽으로 내어 넓혀 둠. 맨 앞이 글자 단추인 꼬리에서 단추 글자가 위 글과 같은 세로선에 옴."""
        self._place("tail", widget, flush)

    def _place(self, name, widget, flush=False):
        old = getattr(self, name)
        if old is widget:
            return
        if old is not None:
            self.box.removeWidget(old)
            old.hide()
        setattr(self, name, widget)
        if widget is not None:
            self.box.insertWidget(0 if name == "head" else self.box.count() - 1, widget)
            if flush:
                kit.flush_left(self.box, widget, widen=True)

    def set_markdown(self, text, base_dir, lang):
        """내용을 text 로 바꾸고 맨 위로 감. 이미지 줄의 경로는 base_dir 에서 찾음."""
        self.clear()
        for part in parts_of(text, base_dir, lang):
            if isinstance(part, list):
                self._add_blocks(part)
            else:
                self._add(part)
        self.verticalScrollBar().setValue(0)

    def add_code(self, title, code, lang):
        """제목(없으면 생략)과 읽기 전용 코드 조각을 더하고 코드 조각을 돌려줌."""
        if title:
            self._add_blocks([{"t": "heading", "level": 2, "text": title}])
        view = CodeView(code, lang, self.code_font)
        self._add(view)
        return view

    def add_table(self, head, rows):
        """마크다운 표처럼 그린 표를 더함. 칸의 글은 인라인 마크다운(`코드`, **굵게**)으로 읽음."""
        self._add_blocks([{"t": "table", "head": list(head), "rows": [list(row) for row in rows]}])

    def add_para(self, text, kind="", link=None):
        """꾸밈없는 글 한 문단을 더함. kind 는 CSS 클래스(h2, muted 등), link 가 있으면 문단 전체가 링크이고 누르면 linked 를 냄."""
        body = html.escape(text, quote=False)
        if link:
            body = '<a href="%s">%s</a>' % (html.escape(link), body)
        rule = "<hr/>" if self.ruled and kind in ("h%d" % level for level in RULED) and self.pieces else ""
        self._add_piece('<body>%s<p%s>%s</p></body>' % (rule, ' class="%s"' % kind if kind else "", body))

    def restyle(self, css, code_font):
        """글자 크기나 테마가 바뀌거나 칸이 좁아지면 부름. 글 조각에 CSS 를, 코드 조각에 글꼴을 다시 주고, 그림의 테두리를 다시 그리고,
        읽던 자리는 지킴."""
        bar = self.verticalScrollBar()
        place = bar.value()
        self.css, self.code_font = css, code_font
        for piece in self.pieces:
            if isinstance(piece, TextPiece):
                piece.restyle(self.sheet_css())
            elif isinstance(piece, CodeView):
                piece.setFont(code_font)
            elif isinstance(piece, FigureView):
                piece.draw()
        bar.setValue(place)

    def _add_blocks(self, blocks):
        if blocks:
            blocks = self._ruled(blocks)
            self._add_piece(mdlite.blocks_html(blocks), blocks)

    def _ruled(self, blocks):
        """맨 바깥의 구역 제목 앞에 가로줄 블록을 넣은 목록. 칸 맨 위에 오는 제목에는 넣지 않음."""
        out = []
        for block in blocks:
            if self.ruled and block["t"] == "heading" and block["level"] in RULED and (out or self.pieces):
                out.append({"t": "rule"})
            out.append(block)
        return out

    def _add_piece(self, markup, blocks=None):
        piece = TextPiece(markup, self.sheet_css(), blocks)
        piece.anchorClicked.connect(lambda url: self.linked.emit(url.toString()))
        self._add(piece)

    def _add(self, widget):
        self.box.insertWidget(self.box.count() - 1 - (self.tail is not None), widget)
        self.pieces.append(widget)


class Doc(QWidget):
    """스크롤하지 않는 마크다운 글. 카드 안에서 다른 위젯과 같이 스크롤되게 DocView 의 조각(TextPiece, FigureView)만 세로로 쌓음.
    pieces 는 쌓은 순서대로의 조각이고, 글 폭은 kit.DOC_MIN 이나 화면이 주는 단 폭까지."""

    def __init__(self):
        super().__init__()
        self.box = kit.box(self, spacing=8)
        self.pieces = []
        self.css = theme.web_css()
        self.setMaximumWidth(kit.DOC_MIN)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def clear(self):
        for piece in self.pieces:
            self.box.removeWidget(piece)
            piece.hide()
            piece.deleteLater()
        self.pieces = []

    def set_markdown(self, text, base_dir, lang):
        self.clear()
        for part in parts_of(text, base_dir, lang):
            if isinstance(part, list):
                self._add_blocks(part)
            else:
                self._add(part)
        self.setVisible(bool(self.pieces))

    def _add_blocks(self, blocks):
        if blocks:
            piece = TextPiece(mdlite.blocks_html(blocks), self.css, blocks)
            self._add(piece)

    def _add(self, widget):
        self.box.addWidget(widget)
        self.pieces.append(widget)

    def restyle(self, css, code_font=None):
        """code_font 는 DocView.restyle 과 같은 꼴로 부르게 받기만 함. 이 글에는 코드 조각이 없음."""
        self.css = css
        for piece in self.pieces:
            if isinstance(piece, TextPiece):
                piece.restyle(css)
            elif isinstance(piece, FigureView):
                piece.draw()


class FigureView(QWidget):
    """해설 그림 하나와 캡션. 파일은 처음에 한 번 바이트로 읽고 열어 두지 않아서, 보이는 동안에도 [문제 받기]가 파일을 바꾸거나 지울 수 있음.
    그림 파일은 2배 크기라 화면에는 그 절반 폭까지만 보이고, 칸이 좁으면 칸 폭에 맞춰 줄임. 줄어 보일 때는 [크게 보기]가 보이고,
    그 단추나 그림을 누르면 그린 크기(절반 폭)로 FigureDialog 를 띄움. 움직이는 그림의 단추는 넘김 줄 오른쪽 끝, 정지 그림이나 넘김 줄에
    자리가 없는 그림은 캡션 아래 오른쪽이라 캡션이 그림 바로 아래에 붙음.
    GIF 는 아래 막대(처음·이전·재생·다음, "2 / 3")로 한 장씩 넘겨 봄. 움직임이 켜져 있고 autoplay 면 처음 보일 때 한 번 재생하고 마지막 장에서 멈춤.
    data 를 주면 파일을 읽지 않고 그 바이트를 씀. zoomable 이 거짓이면(그림 창 안) 줄어도 크게 보기를 두지 않음.
    frame_changed 는 장을 옮긴 뒤 한 번 부르는 함수(장 번호를 받음). 뒤로 갈 때 0번 장부터 다시 넘기며 지나는 장에서는 부르지 않음.
    파일이 없거나 해독되지 않으면 캡션·description과 재시도를 보임. 다시 읽을 때 위젯을 교체하지 않음."""

    reloading = pyqtSignal()

    def __init__(self, path, alt="", parent=None, data=None, zoomable=True, autoplay=True, frame_changed=None, description="", scale=None):
        super().__init__(parent)
        self.path, self.data, self.zoomable = path, b"", zoomable
        self.description, self.available = description, False
        self.scale = scale
        self.autoplay, self.frame_changed = autoplay, frame_changed
        self.movie, self.count, self.playing, self.shown, self.drawn_width = None, 1, False, False, -1
        self.shrunk, self.down, self.dialog = False, False, None
        self.source = QPixmap()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 8, 0, 0)  # 글 조각의 줄은 글자 위에 여백이 있고 아래에는 없어서, 그림 위만 띄워 위아래 간격을 맞춤
        box.setSpacing(8)
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)  # 폭은 칸을 따르고 높이는 그림을 따름
        box.addWidget(self.picture)
        self.zoom_btn = kit.button("크게 보기", "text", "s")
        self.zoom_btn.clicked.connect(self.open_dialog)
        self.controls = None  # 움직이는 그림의 넘김 줄
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._tick)
        self.error_box, error_layout = kit.well(16, 16, theme.GAP["description_content"])
        self.error_note = kit.para(MISSING_TEXT, "caption", "secondary")
        self.error_description = kit.para("", "body", "secondary")
        error_layout.addWidget(kit.heading(self.error_note, self.error_description))
        self.retry_btn = kit.button("다시 시도", "secondary", "s")
        self.retry_btn.setAccessibleName("그림 다시 불러오기")
        self.retry_btn.clicked.connect(lambda: self.reload())
        error_layout.addWidget(self.retry_btn, 0, Qt.AlignmentFlag.AlignLeft)
        box.addWidget(self.error_box)
        self.error_box.setToolTip(os.fsdecode(path))
        self.error_box.hide()
        self.caption = kit.para(alt, "caption", "secondary")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(self.caption)
        self.caption.setVisible(bool(alt))  # 부모에 붙인 뒤에 보임. 먼저 보이면 잠깐 따로 창으로 떠서 화면의 창이 초점을 잃음
        self.zoom_row = QWidget()  # [크게 보기]를 캡션 아래 오른쪽에 두는 줄. 움직이는 그림은 넘김 줄에 자리가 있으면 그 오른쪽 끝에 둠
        row = kit.box(self.zoom_row, horizontal=True)
        row.addStretch(1)
        row.addWidget(self.zoom_btn)
        self.zoom_row.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)  # 넘김 줄과 같은 까닭
        box.addWidget(self.zoom_row)
        self.zoom_row.hide()
        self._read(data)

    def _clear_movie(self):
        self.timer.stop()
        self.playing = False
        if self.movie is not None:
            self.movie.stop()
            self.movie.deleteLater()
            self.buffer.deleteLater()
            self.movie = None

    def _unavailable(self):
        """그림을 읽지 못해도 캡션과 대체 설명을 남기고 같은 자리에서 다시 읽도록 함."""
        self._clear_movie()
        self.available, self.count, self.shrunk = False, 1, False
        self.source = QPixmap()
        self.picture.clear()
        self.picture.hide()
        self.caption.hide()
        if self.controls is not None:
            self.controls.hide()
        self.place_zoom(False)
        parts = [text.strip() for text in (self.caption.text(), self.description) if text and text.strip()]
        self.error_description.setText("\n\n".join(dict.fromkeys(parts)))
        self.error_description.setVisible(bool(parts))
        self.error_box.show()
        return False

    def _read(self, data=None):
        """바이트를 한 번 읽고 첫 그림까지 해독함. 실패하면 이전 그림이나 재생 단추를 남기지 않음."""
        self._clear_movie()
        self.data, self.source, self.count = b"", QPixmap(), 1
        try:
            if data is None:
                with open(self.path, "rb") as handle:
                    data = handle.read()
        except OSError:
            return self._unavailable()
        self.data = data
        if data[:4] == b"GIF8":
            self.open_movie()
            if not self.movie.isValid():
                return self._unavailable()
            self.count = max(1, self.movie.frameCount())
            if self.controls is None:
                self.controls = QWidget()
                bar = kit.FlowLayout(self.controls, spacing=theme.GAP["detail"])
                self.first_btn = self._button(bar, "처음", self.first)
                self.prev_btn = self._button(bar, "이전", self.prev)
                self.play_btn = self._button(bar, "재생", self.toggle)
                self.next_btn = self._button(bar, "다음", self.next)
                self.counter = kit.label("", "caption", "secondary")
                bar.addWidget(self.counter)
                self.controls.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                self.layout().insertWidget(self.layout().indexOf(self.caption), self.controls)
            self.refont()
            if not self.movie.jumpToFrame(0) or self.source.isNull():
                return self._unavailable()
        elif not self.source.loadFromData(data):
            return self._unavailable()
        self.available = True
        self.error_box.hide()
        self.picture.show()
        self.caption.setVisible(bool(self.caption.text()))
        if self.controls is not None:
            self.controls.setVisible(self.movie is not None and self.count > 1)
        self.draw()
        return True

    def reload(self):
        """같은 그림 위젯에서 파일만 다시 읽음. 단원·문항이나 학습 기록을 다시 열지 않음."""
        focused = self.retry_btn.hasFocus()
        self.reloading.emit()
        if focused:
            # 숨길 단추의 초점이 다른 입력 칸으로 잠깐 옮겨가 선택 범위를 지우지 않게 함
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        loaded = self._read()
        if self.frame_changed is not None:
            self.frame_changed(self.frame())
        self.draw()
        if not loaded and focused:
            self.retry_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        return loaded

    def open_movie(self):
        """그림 바이트로 QMovie 를 새로 엶. 프레임을 모아 두지 않아서 뒤로는 0번 장으로만 바로 감. 이미 열린 것이 있으면 닫고 바꿈."""
        old = (self.movie, self.buffer) if self.movie is not None else None
        self.buffer = QBuffer(self)
        self.buffer.setData(QByteArray(self.data))
        self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.movie = QMovie(self.buffer, QByteArray(b"gif"), self)
        self.movie.setCacheMode(QMovie.CacheMode.CacheNone)
        self.movie.frameChanged.connect(self._took_frame)
        if old is not None:
            old[0].frameChanged.disconnect(self._took_frame)
            old[0].deleteLater()
            old[1].deleteLater()

    def _button(self, bar, text, slot):
        button = kit.button(text, "text", "s")
        button.clicked.connect(slot)
        bar.addWidget(button)
        return button

    def frame(self):
        """지금 보이는 장의 번호(0부터)."""
        return max(0, self.movie.currentFrameNumber()) if self.movie else 0

    def go(self, target):
        """target 번 장으로 감. 앞으로는 한 장씩 넘기고, 뒤로는 0번 장으로 돌아가 다시 넘김."""
        target = max(0, min(target, self.count - 1))
        if target < self.frame() and not self.movie.jumpToFrame(0):
            self.open_movie()  # 가운데 장에서는 QMovie 가 0번 장으로 돌아가지 못해(마지막 장에서만 됨) 처음부터 다시 읽음
            self.movie.jumpToFrame(0)
        for _ in range(target - self.frame()):
            self.movie.jumpToNextFrame()
        if self.frame_changed is not None:
            self.frame_changed(self.frame())

    def first(self):
        self.stop()
        self.go(0)

    def prev(self):
        self.stop()
        self.go(self.frame() - 1)

    def next(self):
        self.stop()
        self.go(self.frame() + 1)

    def toggle(self):
        if self.playing:
            self.stop()
        else:
            self.play()

    def play(self):
        """지금 장부터 마지막 장까지 GIF 에 적힌 시간대로 넘기고 멈춤. 마지막 장에서 누르면 처음부터 다시 함."""
        if self.frame() >= self.count - 1:
            self.go(0)
        self.playing = True
        self.timer.start(self.movie.nextFrameDelay())
        self._sync()

    def stop(self):
        if self.movie:
            self.playing = False
            self.timer.stop()
            self._sync()

    def _tick(self):
        self.go(self.frame() + 1)
        if self.frame() >= self.count - 1:
            self.stop()
        else:
            self.timer.start(self.movie.nextFrameDelay())

    def _took_frame(self, number):
        self.source = self.movie.currentPixmap()
        self.draw()
        self._sync()

    def _sync(self):
        frame = self.frame()
        self.counter.setText("%d / %d" % (frame + 1, self.count))
        self.first_btn.setEnabled(frame > 0)
        self.prev_btn.setEnabled(frame > 0)
        self.next_btn.setEnabled(frame < self.count - 1)
        self.play_btn.setText("멈춤" if self.playing else "재생")

    def refont(self):
        """장 번호와 재생 문구가 바뀌어도 넘김 줄의 폭을 유지함."""
        if not self.controls:
            return
        self.counter.setFont(theme.font(self.counter.property("role") or "caption"))
        metrics = QFontMetricsF(self.counter.font())
        numbers = ["%d / %d" % (number, self.count) for number in range(1, self.count + 1)]
        widest = max(numbers, key=metrics.horizontalAdvance)
        self.counter.setMinimumWidth(math.ceil(metrics.horizontalAdvance(widest)))
        self.counter.setProperty("measure", widest)
        self.play_btn.ensurePolished()
        current = self.play_btn.text()
        self.play_btn.setMinimumWidth(0)
        widths = []
        for text in ("재생", "멈춤"):
            self.play_btn.setText(text)
            widths.append(self.play_btn.sizeHint().width())
        self.play_btn.setText(current)
        self.play_btn.setMinimumWidth(max(widths))
        self.controls.layout().invalidate()
        self.controls.updateGeometry()

    def display_scale(self):
        """그림 원본과 표시 크기의 비율. 학습 그림은 본문 크기에 맞춰 바꿀 수 있음."""
        return SCALE if self.scale is None else self.scale

    def draw(self):
        """지금 장을 칸 폭에 맞춰 화면 배율로 부드럽게 줄이고, 모서리를 코드 상자처럼 둥글게 깎고 테두리를 둘러 보여 줌.
        테두리는 어두운 테마에서 남색 그림과 카드의 경계를 그림."""
        self.drawn_width = self.width()
        if self.source.isNull():
            return
        ratio = self.devicePixelRatioF()
        width = min(self.source.width() / self.display_scale(), max(1, self.width()))
        pixmap = self.source.scaledToWidth(max(1, round(width * ratio)), Qt.TransformationMode.SmoothTransformation)
        pixmap.setDevicePixelRatio(ratio)
        framed = QPixmap(pixmap.size())
        framed.setDevicePixelRatio(ratio)
        framed.fill(Qt.GlobalColor.transparent)
        painter = QPainter(framed)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(QPointF(0, 0), pixmap.deviceIndependentSize()).adjusted(0.5, 0.5, -0.5, -0.5), CODE_RADIUS, CODE_RADIUS)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.setClipping(False)
        painter.setPen(QPen(theme.qcolor("border"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        self.picture.setPixmap(framed)
        self.shrunk = width < self.source.width() / self.display_scale()
        zoom = self.shrunk and self.zoomable
        self.picture.setCursor(Qt.CursorShape.PointingHandCursor if zoom else Qt.CursorShape.ArrowCursor)
        self.place_zoom(zoom)

    def place_zoom(self, zoom):
        """[크게 보기]를 보이거나 숨김. 움직이는 그림은 넘김 줄에 단추가 다 들어가면 그 오른쪽 끝에, 아니면 캡션 아래 줄에 둠.
        글자 크기 단계가 커지면 1024 창의 지문 칸에서 넘김 단추 넷, 장 번호와 이 단추가 한 줄에 들어가지 않아 글자가 잘렸음."""
        inline = zoom and self.count > 1 and self.bar_room() >= self.zoom_btn.sizeHint().width()
        if inline != (self.zoom_btn.parentWidget() is self.controls):
            (self.zoom_row if inline else self.controls).layout().removeWidget(self.zoom_btn)
            (self.controls if inline else self.zoom_row).layout().addWidget(self.zoom_btn)
        self.zoom_btn.setVisible(zoom)
        if self.zoom_row.isHidden() == (zoom and not inline):
            self.zoom_row.setVisible(zoom and not inline)

    def bar_room(self):
        """넘김 줄에서 단추·장 번호와 그 사이 간격을 뺀 남는 폭."""
        parts = (self.first_btn, self.prev_btn, self.play_btn, self.next_btn, self.counter)
        return self.width() - sum(part.sizeHint().width() for part in parts) - self.controls.layout().spacing() * len(parts)

    def open_dialog(self):
        """지금 장을 그린 크기로 보는 창을 띄움."""
        self.dialog = FigureDialog(self.window(), self, self.caption.text())
        self.dialog.show()

    def _on_picture(self, event):
        return event.button() == Qt.MouseButton.LeftButton and self.picture.geometry().contains(event.position().toPoint())

    def mousePressEvent(self, event):
        """줄어 보이는 그림 위의 누름을 받음. 그림을 담은 QLabel 은 누름을 받지 않고 여기로 넘김."""
        self.down = self.shrunk and self.zoomable and self._on_picture(event)
        if self.down:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        down, self.down = self.down, False
        if down and self._on_picture(event):
            self.open_dialog()
        else:
            super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() != self.drawn_width:
            self.draw()

    def showEvent(self, event):
        super().showEvent(event)
        self.refont()
        if not self.shown:
            self.shown = True
            if self.movie and self.count > 1 and motion.enabled and self.autoplay:
                self.play()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.stop()


class FigureDialog(QDialog):
    """해설 그림 한 장을 그린 크기(파일 폭의 1/SCALE)로 보여 주는 창. 제목은 그림 캡션이고 화면보다 크면 스크롤함.
    움직이는 그림은 같은 넘김 단추를 달고 누른 때의 장부터 보여 주며, 저절로 재생하지 않음."""

    def __init__(self, parent, figure, title=""):
        super().__init__(parent)
        kit.page(self)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # 누를 때마다 새 창을 만들므로 닫은 창은 지움
        self.setWindowTitle(title or "그림")
        box = kit.box(self, (24, 24, 24, 24), 16)
        if title:
            box.addWidget(kit.para(title, "headline"))
        self.view = FigureView("", parent=None, data=figure.data, zoomable=False, scale=figure.display_scale())
        self.view.shown = True
        if self.view.movie:
            self.view.go(figure.frame())
        self.picture = self.view.picture
        drawn = math.ceil(figure.source.width() / figure.display_scale())
        self.view.setMinimumWidth(drawn)  # 창이 좁으면 그림을 줄이지 않고 스크롤함
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(self.view)
        scroll.viewport().setAutoFillBackground(False)  # 창 바탕(surface_raised)이 그림 둘레에 보이게 함
        box.addWidget(scroll, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        close = kit.button("닫기", "secondary", "l")
        close.clicked.connect(self.close)
        row.addWidget(close)
        box.addLayout(row)
        # 폭은 그림, 넘김 줄, 한 줄로 쓴 제목(읽는 글 단까지) 가운데 넓은 것. 작은 그림에서 제목이 몇 글자씩 꺾이거나 넘김 단추가 눌리지 않게 함
        title_width = QFontMetricsF(theme.font("headline")).horizontalAdvance(title) if title else 0
        bar_width = self.view.controls.sizeHint().width() if self.view.movie else 0
        width = math.ceil(max(drawn, bar_width, min(title_width, kit.DOC_MIN))) + 48
        room = self.screen().availableGeometry()
        width = min(width, room.width() - 40)
        height = box.totalHeightForWidth(width) if box.hasHeightForWidth() else box.sizeHint().height()
        height += self.view.sizeHint().height() - scroll.sizeHint().height()
        self.resize(width, min(height, room.height() - 60))
