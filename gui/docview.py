# -*- coding: utf-8 -*-
"""여정 문제 화면의 지문·힌트·해설 칸(DocView)과 해설 그림(FigureView), 그림을 그린 크기로 보는 창(FigureDialog).

DocView 는 마크다운을 글 조각(QTextBrowser)과 그림 조각으로 나눠 위에서 아래로 쌓고, 기준 풀이 같은 코드 조각과 표·문단을 뒤에 더함.
조각은 스크롤 막대 없이 내용 높이만큼 늘어나고 바깥 스크롤 하나로 읽음. 글은 theme.journey_css 로 그리고, 칸 맨 위가 아닌
구역 제목(2·3단계) 앞에는 가로줄을 넣음. 칸이 좁으면(TIGHT_WIDTH) 표 칸과 코드 상자의 가로 여백을 줄임."""
import html
import math
import os

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMovie, QPainter, QPainterPath, QPen, QPixmap, QTextCursor, QTextLength, QTextTable
from PyQt6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QTextBrowser, QVBoxLayout,
                             QWidget)

import mdlite
from gui import motion, theme
from gui.editor import LANGS, CodeEditor
from gui.widgets import Para

CODE_MARKS = {"python": ("python", "py"), "javascript": ("javascript", "js")}  # 펜스 코드 블록에 붙는 언어 표시
SCALE = 2  # 그림 파일은 화면에 보일 크기의 2배로 그려 둠
NARROW_CSS = "pre { white-space: pre-wrap; }"  # 글 조각은 가로 스크롤이 없으므로 긴 코드 줄을 조각 폭에서 줄바꿈함
RULED = (2, 3)  # 앞에 가로줄을 넣는 제목 단계. 지문·해설의 구역 제목은 2단계, 힌트 제목은 3단계임
CODE_RADIUS = 8  # 코드 상자와 해설 그림의 모서리 반지름
CODE_MARGIN = (12, -4)  # 코드 상자 위·아래의 바깥 여백. mdlite 가 표에 style 로 적은 여백은 CSS 로 덮지 못해 문서를 읽은 뒤 바꿈.
# 아래 여백이 음수인 까닭: Qt 가 표 뒤에 두는 빈 줄이 상자 아래로 4px 남짓 삐져나와서, 그만큼 당겨야 상자 뒤의 가로줄 간격이 문단 뒤와 같아짐
MIN_SHARE = 0.1  # 표의 열 하나가 가지는 폭의 하한. 전체 폭의 비율
TIGHT_WIDTH = 500  # 칸이 이보다 좁으면(1024 폭 창의 왼쪽 칸) 표 칸과 코드 상자의 가로 여백을 줄임
TIGHT_CSS = "table.grid th { padding: 9px 10px; } table.grid td { padding: 0px 10px 10px 10px; } td.codebox { padding: 12px 12px; }"


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


def spread(table):
    """표를 조각 폭에 꽉 채우고, 열 폭을 그 열에서 가장 긴 칸 글의 길이에 비례해 나눔(열마다 적어도 MIN_SHARE).
    Qt 가 정하는 폭은 긴 목록이 든 열을 좁혀 원소마다 줄을 바꾸고 짧은 열은 비워 두어서 직접 나눔."""
    longest = [max(len(cell_text(table.cellAt(row, column))) for row in range(table.rows())) for column in range(table.columns())]
    shares = [max(length, sum(longest) * MIN_SHARE) for length in longest]
    total = sum(shares) or 1
    box = table.format()
    box.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
    box.setColumnWidthConstraints([QTextLength(QTextLength.Type.PercentageLength, 100 * share / total) for share in shares])
    table.setFormat(box)


class Sheet(QWidget):
    """조각을 얹는 바탕. 칠할 때마다 지금 테마의 surface 색을 읽어서 테마를 바꿔도 따로 다시 칠할 일이 없음."""

    def paintEvent(self, event):
        QPainter(self).fillRect(event.rect(), theme.qcolor("surface"))


class TextPiece(QTextBrowser):
    """글 조각. 폭이 바뀌면 높이를 내용에 맞춤. 휠은 바깥 스크롤로 넘겨서 Ctrl+휠로 이 조각만 글자가 커지는 일도 없음."""

    def __init__(self, markup, css):
        super().__init__()
        self.markup = markup
        self.setOpenLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QTextBrowser { background: transparent; border: 0; }")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(0)
        self.restyle(css)

    def restyle(self, css):
        """CSS 는 다음에 넣는 HTML 부터 적용되므로 HTML 을 다시 넣음."""
        self.document().setDefaultStyleSheet(css + NARROW_CSS)
        self.setHtml(self.markup)
        for frame in self.code_frames():
            box = frame.format()
            box.setTopMargin(CODE_MARGIN[0])
            box.setBottomMargin(CODE_MARGIN[1])
            frame.setFormat(box)
        for table in self.grid_tables():
            spread(table)
        self.fit()

    def fit(self):
        """문서 높이 전체를 씀. content_height 처럼 마지막 줄 아래 간격을 빼면 그만큼 안에서 스크롤돼서, 글을 끌어 고르거나
        키로 움직일 때 첫 줄이 위로 밀림. 보이기 전에는 QTextBrowser 가 문서 폭을 정하지 않아 줄이 앉지 않으므로 폭을 먼저 줌.
        이미 자리 잡은 칸에 새로 들어온 조각은 보일 때의 resizeEvent 안에서 높이를 바꾸는데, 이 높이 변경은 resizeEvent 로 다시
        오지 않아 스크롤 범위가 만들 때의 낮은 높이 기준으로 남음. 조각은 안에서 스크롤하지 않으므로 범위를 0 으로 둠."""
        self.document().setTextWidth(self.viewport().width())
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
        """코드 상자마다 화면 위의 사각형. 칸 안 첫 줄과 끝 줄의 자리에 칸 여백을 더해 셈.
        끝 줄 아래에 붙는 넓힌 줄 간격은 블록 사각형에 들지 않아 위아래 여백이 같아짐."""
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
        """Qt 의 표는 모서리를 둥글게 그리지 못해서 코드 상자의 바탕과 테두리를 글보다 먼저 그림. 상자 칸의 바탕은 CSS 에서 투명하게 둠."""
        boxes = self.code_boxes()
        if boxes:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(theme.qcolor("border"), 1))
            painter.setBrush(theme.qcolor("codebox_bg"))
            for rect in boxes:
                painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), CODE_RADIUS, CODE_RADIUS)
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
    lang 은 "python" 이나 "javascript" 이고, 그 언어가 아닌 코드 블록은 보이지 않음."""
    linked = pyqtSignal(str)  # 글 조각의 링크를 눌렀을 때. 주소

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sheet = Sheet()
        self.box = QVBoxLayout(self.sheet)
        self.box.setContentsMargins(20, 18, 20, 20)
        self.box.setSpacing(10)
        self.box.addStretch(1)
        self.setWidget(self.sheet)
        self.pieces = []  # 쌓은 순서대로의 조각: TextPiece, FigureView, CodeView, 없는 그림 안내(Para)
        self.css, self.code_font = theme.journey_css(), theme.code_font()
        self.tight = False  # 칸이 TIGHT_WIDTH 보다 좁은지. resizeEvent 가 바꿈

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

    def set_markdown(self, text, base_dir, lang):
        """내용을 text 로 바꾸고 맨 위로 감. 이미지 줄의 경로는 base_dir 기준임."""
        self.clear()
        run = []
        for block in keep_lang(mdlite.parse(text), lang):
            if block["t"] != "image":
                run.append(block)
                continue
            self._add_blocks(run)
            run = []
            try:
                piece = FigureView(os.path.join(base_dir, block["src"]), block["alt"])
            except OSError:  # 없는 파일, 읽을 권한이 없는 파일, [문제 받기]가 바꾸는 중인 파일
                piece = Para("그림을 찾을 수 없습니다: %s" % block["src"], "muted")
            self._add(piece)
        self._add_blocks(run)
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
        rule = "<hr/>" if kind in ("h%d" % level for level in RULED) and self.pieces else ""
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
            if block["t"] == "heading" and block["level"] in RULED and (out or self.pieces):
                out.append({"t": "rule"})
            out.append(block)
        return out

    def _add_piece(self, markup):
        piece = TextPiece(markup, self.sheet_css())
        piece.anchorClicked.connect(lambda url: self.linked.emit(url.toString()))
        self._add(piece)

    def _add(self, widget):
        self.box.insertWidget(self.box.count() - 1, widget)
        self.pieces.append(widget)


class FigureView(QWidget):
    """해설 그림 하나와 캡션. 파일은 처음에 한 번 바이트로 읽고 열어 두지 않아서, 보이는 동안에도 [문제 받기]가 파일을 바꾸거나 지울 수 있음.
    그림 파일은 2배 크기라 화면에는 그 절반 폭까지만 보이고, 칸이 좁으면 칸 폭에 맞춰 줄임. 줄어 보일 때 그림을 누르면
    그린 크기(절반 폭)로 FigureDialog 를 띄움.
    GIF 는 아래 막대(처음·이전·재생·다음, "2 / 3")로 한 장씩 넘겨 봄. 움직임이 켜져 있으면 처음 보일 때 한 번 재생하고 마지막 장에서 멈춤."""

    def __init__(self, path, alt="", parent=None):
        super().__init__(parent)
        with open(path, "rb") as handle:
            data = handle.read()
        self.movie, self.count, self.playing, self.shown, self.drawn_width = None, 1, False, False, -1
        self.shrunk, self.down, self.dialog = False, False, None
        self.source = QPixmap()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 10, 0, 0)  # 글 조각의 줄은 글자 위에 여백이 있고 아래에는 없어서, 그림 위만 띄워 위아래 간격을 맞춤
        box.setSpacing(6)
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)  # 폭은 칸을 따르고 높이는 그림을 따름
        box.addWidget(self.picture)
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
            bar = QHBoxLayout()
            bar.addStretch(1)
            self.first_btn = self._button(bar, "처음", self.first)
            self.prev_btn = self._button(bar, "이전", self.prev)
            self.play_btn = self._button(bar, "재생", self.toggle)
            self.next_btn = self._button(bar, "다음", self.next)
            self.counter = QLabel()
            self.counter.setObjectName("muted")
            bar.addSpacing(6)
            bar.addWidget(self.counter)
            bar.addStretch(1)
            self.controls = QWidget()
            self.controls.setLayout(bar)
            # 칸을 단추 줄보다 좁히면 단추가 잘림. 단추 줄의 폭을 따르면 칸 전체가 넓어져 글이 오른쪽 밖으로 밀림
            self.controls.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            bar.setContentsMargins(0, 0, 0, 0)
            self.controls.setVisible(self.count > 1)
            box.addWidget(self.controls)
            self.movie.jumpToFrame(0)
        else:
            self.source.loadFromData(data)
            self.draw()
        self.caption = Para(alt, "muted")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.caption.setVisible(bool(alt))
        box.addWidget(self.caption)

    def _button(self, bar, text, slot):
        button = QPushButton(text)
        button.setObjectName("quiet")
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
        """지금 장을 칸 폭에 맞춰 화면 배율로 부드럽게 줄이고, 모서리를 코드 상자처럼 둥글게 깎고 테두리를 둘러 보여 줌."""
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
        self.picture.setCursor(Qt.CursorShape.PointingHandCursor if self.shrunk else Qt.CursorShape.ArrowCursor)
        self.picture.setToolTip("누르면 그림을 원래 크기로 봅니다." if self.shrunk else "")

    def _on_picture(self, event):
        return event.button() == Qt.MouseButton.LeftButton and self.picture.geometry().contains(event.position().toPoint())

    def mousePressEvent(self, event):
        """줄어 보이는 그림 위의 누름을 받음. 그림을 담은 QLabel 은 누름을 받지 않고 여기로 넘김."""
        self.down = self.shrunk and self._on_picture(event)
        if self.down:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        down, self.down = self.down, False
        if down and self._on_picture(event):
            self.dialog = FigureDialog(self.window(), self.source, self.caption.text())
            self.dialog.show()
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
    """해설 그림 한 장을 그린 크기(파일 폭의 1/SCALE)로 보여 주는 창. 화면보다 크면 스크롤함. 움직이는 그림은 누른 때의 장을 보여 줌."""

    def __init__(self, parent, source, title=""):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # 누를 때마다 새 창을 만들므로 닫은 창은 지움
        self.setWindowTitle(title or "그림")
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 12, 12, 12)
        ratio = self.devicePixelRatioF()
        pixmap = source.scaledToWidth(max(1, round(source.width() / SCALE * ratio)), Qt.TransformationMode.SmoothTransformation)
        pixmap.setDevicePixelRatio(ratio)
        self.picture = QLabel()
        self.picture.setPixmap(pixmap)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(self.picture)
        box.addWidget(scroll, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("닫기")
        close.clicked.connect(self.close)
        row.addWidget(close)
        box.addLayout(row)
        size = pixmap.deviceIndependentSize()
        room = self.screen().availableGeometry()
        self.resize(min(round(size.width()) + 40, room.width() - 40), min(round(size.height()) + 90, room.height() - 60))
