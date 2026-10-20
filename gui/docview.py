# -*- coding: utf-8 -*-
"""여정 문제 화면의 지문·힌트·해설 칸(DocView)과 해설 그림(FigureView).

DocView 는 마크다운을 글 조각(QTextBrowser)과 그림 조각으로 나눠 위에서 아래로 쌓고, 기준 풀이 같은 코드 조각과 표·문단을 뒤에 더함.
조각은 스크롤 막대 없이 내용 높이만큼 늘어나고 바깥 스크롤 하나로 읽음."""
import html
import math
import os

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMovie, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget

import mdlite
from gui import motion, theme
from gui.editor import LANGS, CodeEditor
from gui.widgets import Para

CODE_MARKS = {"python": ("python", "py"), "javascript": ("javascript", "js")}  # 펜스 코드 블록에 붙는 언어 표시
SCALE = 2  # 그림 파일은 화면에 보일 크기의 2배로 그려 둠
NARROW_CSS = "pre { white-space: pre-wrap; }"  # 글 조각은 가로 스크롤이 없으므로 긴 코드 줄을 조각 폭에서 줄바꿈함


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
        self.box.setContentsMargins(14, 12, 14, 14)
        self.box.setSpacing(8)
        self.box.addStretch(1)
        self.setWidget(self.sheet)
        self.pieces = []  # 쌓은 순서대로의 조각: TextPiece, FigureView, CodeView, 없는 그림 안내(Para)
        self.css, self.code_font = theme.doc_css(), theme.code_font()

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
        self._add_piece('<body><p%s>%s</p></body>' % (' class="%s"' % kind if kind else "", body))

    def restyle(self, css, code_font):
        """글자 크기나 테마가 바뀌면 부름. 글 조각에 CSS 를, 코드 조각에 글꼴을 다시 주고 읽던 자리는 지킴."""
        bar = self.verticalScrollBar()
        place = bar.value()
        self.css, self.code_font = css, code_font
        for piece in self.pieces:
            if isinstance(piece, TextPiece):
                piece.restyle(css)
            elif isinstance(piece, CodeView):
                piece.setFont(code_font)
        bar.setValue(place)

    def _add_blocks(self, blocks):
        if blocks:
            self._add_piece(mdlite.blocks_html(blocks))

    def _add_piece(self, markup):
        piece = TextPiece(markup, self.css)
        piece.anchorClicked.connect(lambda url: self.linked.emit(url.toString()))
        self._add(piece)

    def _add(self, widget):
        self.box.insertWidget(self.box.count() - 1, widget)
        self.pieces.append(widget)


class FigureView(QWidget):
    """해설 그림 하나와 캡션. 파일은 처음에 한 번 바이트로 읽고 열어 두지 않아서, 보이는 동안에도 [문제 받기]가 파일을 바꾸거나 지울 수 있음.
    그림 파일은 2배 크기라 화면에는 그 절반 폭까지만 보이고, 칸이 좁으면 칸 폭에 맞춰 줄임.
    GIF 는 아래 막대(처음·이전·재생·다음, "2 / 3")로 한 장씩 넘겨 봄. 움직임이 켜져 있으면 처음 보일 때 한 번 재생하고 마지막 장에서 멈춤."""

    def __init__(self, path, alt="", parent=None):
        super().__init__(parent)
        with open(path, "rb") as handle:
            data = handle.read()
        self.movie, self.count, self.playing, self.shown, self.drawn_width = None, 1, False, False, -1
        self.source = QPixmap()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
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
        """지금 장을 칸 폭에 맞춰 화면 배율로 부드럽게 줄여 보여 줌."""
        self.drawn_width = self.width()
        if self.source.isNull():
            return
        ratio = self.devicePixelRatioF()
        width = min(self.source.width() / SCALE, max(1, self.width()))
        pixmap = self.source.scaledToWidth(max(1, round(width * ratio)), Qt.TransformationMode.SmoothTransformation)
        pixmap.setDevicePixelRatio(ratio)
        self.picture.setPixmap(pixmap)

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
