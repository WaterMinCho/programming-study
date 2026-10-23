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
CODE_MARGIN = (16, 10)  # 코드 상자 위·아래의 바깥 여백. mdlite 가 표에 style 로 적은 여백은 CSS 로 덮지 못해 문서를 읽은 뒤 바꿈.
# 위 16 은 문단 사이와 같음. Qt 는 표 뒤에 빈 줄을 두어 상자 아래가 CODE_SPILL 만큼 더 벌어지고, 고정 줄 높이의 넓힌 간격은 다음 문단 글자
# 위에 생김. 아래를 10 으로 줄여야 상자 위와 아래에 보이는 간격이 같아짐(세 글자 단계에서 화소로 재어 1px 안).
# 문단의 아래 여백은 다음 블록의 위 여백과 겹치지만 표의 여백은 더해지므로, 상자 뒤 블록에 위 여백(제목의 24)이 있으면 그만큼 아래 여백을 뺌
CODE_SPILL = 4  # 그 빈 줄이 상자 아래로 삐져나오는 높이. 조각 끝 상자는 아래 여백을 이만큼 당겨 조각이 상자 끝에서 끝나게 함
PAD = 24  # DocView 의 안쪽 여백
GAP = 16  # DocView 의 조각 사이. 문단 사이와 같은 값
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


def missing_figure(src):
    """없는 그림 자리에 두는 안내 글. 그림 경로는 도움말."""
    note = kit.para(MISSING_TEXT, "caption", "secondary")
    note.setToolTip(src)
    return note


def parts_of(text, base_dir, lang):
    """마크다운을 쌓을 차례대로 나눠 내놓음. 그림 줄 사이의 블록들은 한 목록으로, 그림 줄은 그림 조각(FigureView)으로 내놓고
    그림 파일을 읽지 못하면 그 자리에 안내 글을 내놓음. 이미지 줄의 경로는 base_dir 에서 찾음. DocView 와 Doc 이 같이 씀."""
    run = []
    for block in keep_lang(mdlite.parse(text), lang):
        if block["t"] != "image":
            run.append(block)
            continue
        if run:
            yield run
        run = []
        try:
            yield FigureView(os.path.join(base_dir, block["src"]), block["alt"])
        except OSError:  # 없는 파일, 읽을 권한이 없는 파일, [문제 받기]가 바꾸는 중인 파일
            yield missing_figure(block["src"])
    if run:
        yield run


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

    def __init__(self, markup, css):
        super().__init__()
        self.markup = markup
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
        self.setHtml(self.markup)
        self.document().setTextWidth(max(1, self.viewport().width()))  # 폭이 없으면 줄을 앉히지 않아 center_code 가 줄 자리를 못 읽음
        following = self.following_margins()
        for frame in self.code_frames():
            box = frame.format()
            box.setTopMargin(CODE_MARGIN[0])
            box.setBottomMargin(max(0, CODE_MARGIN[1] - following.get(frame, 0)))
            frame.setFormat(box)
            self.center_code(frame)
        self.trim_ends()
        self.spread_width = None
        self.fit()

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
        """코드 상자 칸의 위아래 안쪽 여백을 글 줄에 맞춰 고침. 고정 줄 높이(pre 의 line-height)는 넓힌 간격을 줄 위에 두어 칸 안의 글이
        그만큼 아래로 내려앉음. 그 간격만큼 위 여백을 줄이고 아래 여백을 늘려 상자 크기와 자리는 그대로 두고 글 줄을 가운데에 둠."""
        cell = frame.cellAt(0, 0)
        block = cell.firstCursorPosition().block()
        self.document().documentLayout().blockBoundingRect(block)  # 줄을 앉혀야 줄 자리를 읽음
        if block.layout().lineCount() == 0:
            return
        spill = block.layout().lineAt(0).y()
        pad = cell.format().toTableCellFormat()
        pad.setTopPadding(pad.topPadding() - spill)
        pad.setBottomPadding(pad.bottomPadding() + spill)
        cell.setFormat(pad)

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
        width = self.viewport().width()
        self.document().setTextWidth(width)
        if width != self.spread_width:
            self.spread_width = width
            for table in self.grid_tables():
                spread(table, width)
        self.setFixedHeight(math.ceil(self.document().size().height()))
        self.verticalScrollBar().setRange(0, 0)

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
        layout, rects = self.document().documentLayout(), []
        for frame in self.code_frames():
            cell = frame.cellAt(0, 0)
            pad = cell.format().toTableCellFormat()
            top = layout.blockBoundingRect(cell.firstCursorPosition().block())
            bottom = layout.blockBoundingRect(cell.lastCursorPosition().block())
            rects.append(QRectF(top.left() - pad.leftPadding(), top.top() - pad.topPadding(),
                                top.width() + pad.leftPadding() + pad.rightPadding(),
                                bottom.bottom() - top.top() + pad.topPadding() + pad.bottomPadding()))
        return rects

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

    def set_tail(self, widget):
        """조각 목록 아래, 남는 칸 앞에 widget 을 둠(힌트 꼬리). 앞에 둔 위젯은 빼서 숨김. None 이면 빼기만 함."""
        self._place("tail", widget)

    def _place(self, name, widget):
        old = getattr(self, name)
        if old is widget:
            return
        if old is not None:
            self.box.removeWidget(old)
            old.hide()
        setattr(self, name, widget)
        if widget is not None:
            self.box.insertWidget(0 if name == "head" else self.box.count() - 1, widget)

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
            self._add_piece(mdlite.blocks_html(self._ruled(blocks)))

    def _ruled(self, blocks):
        """맨 바깥의 구역 제목 앞에 가로줄 블록을 넣은 목록. 칸 맨 위에 오는 제목에는 넣지 않음."""
        out = []
        for block in blocks:
            if self.ruled and block["t"] == "heading" and block["level"] in RULED and (out or self.pieces):
                out.append({"t": "rule"})
            out.append(block)
        return out

    def _add_piece(self, markup):
        piece = TextPiece(markup, self.sheet_css())
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
            piece = TextPiece(mdlite.blocks_html(blocks), self.css)
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
    그 단추나 그림을 누르면 그린 크기(절반 폭)로 FigureDialog 를 띄움. 움직이는 그림의 단추는 넘김 줄 오른쪽 끝, 정지 그림은 그림 아래 오른쪽.
    GIF 는 아래 막대(처음·이전·재생·다음, "2 / 3")로 한 장씩 넘겨 봄. 움직임이 켜져 있으면 처음 보일 때 한 번 재생하고 마지막 장에서 멈춤.
    data 를 주면 파일을 읽지 않고 그 바이트를 씀. zoomable 이 거짓이면(그림 창 안) 줄어도 크게 보기를 두지 않음."""

    def __init__(self, path, alt="", parent=None, data=None, zoomable=True):
        super().__init__(parent)
        if data is None:
            with open(path, "rb") as handle:
                data = handle.read()
        self.data, self.zoomable = data, zoomable
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
        if data[:4] == b"GIF8":
            self.buffer = QBuffer(self)
            self.buffer.setData(QByteArray(data))
            self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.movie = QMovie(self.buffer, QByteArray(b"gif"), self)
            self.movie.setCacheMode(QMovie.CacheMode.CacheNone)  # 프레임을 모아 두지 않음. 대신 뒤로는 0번 장으로만 바로 감
            self.movie.frameChanged.connect(self._took_frame)
            self.count = max(1, self.movie.frameCount())
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self._tick)
            self.controls = QWidget()
            bar = kit.box(self.controls, spacing=8, horizontal=True)
            bar.addStretch(1)
            self.first_btn = self._button(bar, "처음", self.first)
            self.prev_btn = self._button(bar, "이전", self.prev)
            self.play_btn = self._button(bar, "재생", self.toggle)
            self.next_btn = self._button(bar, "다음", self.next)
            self.counter = kit.label("", "caption", "secondary")
            bar.addWidget(self.counter)
            bar.addStretch(1)
            # 칸을 단추 줄보다 좁히면 단추가 잘림. 단추 줄의 폭을 따르면 칸 전체가 넓어져 글이 오른쪽 밖으로 밀림
            self.controls.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            box.addWidget(self.controls)  # 부모에 붙인 뒤에 숨김을 정함. 먼저 보이게 하면 잠깐 따로 창으로 뜨고 그 폭이 최소 폭으로 남음
            self.controls.setVisible(self.count > 1)
        self.zoom_row = QWidget()  # [크게 보기]를 그림 아래 오른쪽에 두는 줄. 움직이는 그림은 넘김 줄에 자리가 있으면 그 오른쪽 끝에 둠
        row = kit.box(self.zoom_row, horizontal=True)
        row.addStretch(1)
        row.addWidget(self.zoom_btn)
        self.zoom_row.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)  # 넘김 줄과 같은 까닭
        box.addWidget(self.zoom_row)
        self.zoom_row.hide()
        if self.movie:
            self.movie.jumpToFrame(0)
        else:
            self.source.loadFromData(data)
            self.draw()
        self.caption = kit.para(alt, "caption", "secondary")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(self.caption)
        self.caption.setVisible(bool(alt))  # 부모에 붙인 뒤에 보임. 먼저 보이면 잠깐 따로 창으로 떠서 화면의 창이 초점을 잃음

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
        if target < self.frame():
            self.movie.jumpToFrame(0)
        for _ in range(target - self.frame()):
            self.movie.jumpToNextFrame()

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

    def draw(self):
        """지금 장을 칸 폭에 맞춰 화면 배율로 부드럽게 줄이고, 모서리를 코드 상자처럼 둥글게 깎고 테두리를 둘러 보여 줌.
        테두리는 어두운 테마에서 남색 그림과 카드의 경계를 그림."""
        self.drawn_width = self.width()
        if self.source.isNull():
            return
        ratio = self.devicePixelRatioF()
        width = min(self.source.width() / SCALE, max(1, self.width()))
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
        self.shrunk = width < self.source.width() / SCALE
        zoom = self.shrunk and self.zoomable
        self.picture.setCursor(Qt.CursorShape.PointingHandCursor if zoom else Qt.CursorShape.ArrowCursor)
        self.place_zoom(zoom)

    def place_zoom(self, zoom):
        """[크게 보기]를 보이거나 숨김. 움직이는 그림은 넘김 줄에 단추가 다 들어가면 그 오른쪽 끝에, 아니면 그림 아래 줄에 둠.
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
        if not self.shown:
            self.shown = True
            if self.movie and self.count > 1 and motion.enabled:
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
        self.view = FigureView("", parent=None, data=figure.data, zoomable=False)
        self.view.shown = True
        if self.view.movie:
            self.view.go(figure.frame())
        self.picture = self.view.picture
        drawn = math.ceil(figure.source.width() / SCALE)
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
