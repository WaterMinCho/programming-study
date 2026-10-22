# -*- coding: utf-8 -*-
"""학습 노트 화면: 위 막대(돌아가기 · 노트 제목)와 가운데 카드 안의 DocView 하나. 카드 폭은 읽는 글의 단 폭(kit.doc_width, 1280 창에서 640 이고
창이 넓어지면 따라 넓어짐)에 안쪽 여백 24 둘을 더한 값.

figure 블록은 web_mission.figures_to_images 가 그림 줄로 바꾸고, 그림은 알고리즘 여행의 FigureView(gui/docview.py)가 그대로 그림.
드릴 화면의 학습 노트 줄은 절 id(3a)를 주고, 그 절의 제목 줄이 칸 맨 위에 오게 스크롤함. 열 때마다 서비스가 learn 을 기록함.
카드 안 맨 아래의 [다음 절]은 지금 보는 자리 다음에 오는 절 제목으로 스크롤함. 읽기 화면이라 아래 막대와 주 단추가 없음."""
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from gui import kit, theme
from gui.docview import DocView, FigureView, TextPiece
from gui.web_mission import LANG, figures_to_images

BACK_TEXT = {"mission": "← 미션", "drill": "← 꼬리 질문"}


def heading_top(view, text):
    """DocView 에서 글이 text 인 줄의 세로 자리. 없으면 None."""
    for piece in view.pieces:
        if not isinstance(piece, TextPiece):
            continue
        block = piece.document().begin()
        while block.isValid():
            if block.text().strip() == text:
                return piece.y() + piece.document().documentLayout().blockBoundingRect(block).top()
            block = block.next()
    return None


def scroll_to_heading(view, text, above=8):
    """DocView 에서 글이 text 인 줄이 칸 맨 위에 오게 스크롤함. 찾으면 True."""
    top = heading_top(view, text)
    if top is None:
        return False
    view.verticalScrollBar().setValue(max(0, int(top) - above))
    return True


class WebLearnPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.setProperty("clipboard", True)
        self.win = win
        self.pid, self.page, self.back, self.section = None, None, None, ""
        self.headings = []  # 이 노트의 절 제목들(문서 순서)
        self.reached = None  # [다음 절]로 마지막에 간 절. 문서가 짧아 스크롤이 안 움직여도 다음 절이 앞으로 가게 함
        root = kit.box(self)
        self.top = kit.TopBar("← 웹 면접 준비", "")
        self.back_btn, self.title = self.top.back, self.top.title
        root.addWidget(self.top)
        body = QWidget()
        body_box = kit.box(body, (kit.MARGIN, 24, kit.MARGIN, 24))
        self.card, card_box = kit.card(24, 0)
        self.view = DocView()
        self.view.box.setContentsMargins(0, 0, 0, 0)
        self.view.css = theme.web_css(self.win.zoom)
        self.view.ruled = False
        card_box.addWidget(self.view, 1)
        self.next_row = QWidget()
        next_box = QHBoxLayout(self.next_row)
        next_box.setContentsMargins(0, 24, 0, 0)
        next_box.setSpacing(12)
        self.next_btn = kit.button("다음 절", "secondary", "m")
        self.next_title = kit.label("", "caption", "tertiary")
        next_box.addWidget(self.next_btn)
        next_box.addWidget(self.next_title, 1)
        self.next_row.hide()
        card_box.addWidget(self.next_row)
        body_box.addWidget(kit.column(self.card, kit.DOC_MIN + 48), 1)
        root.addWidget(body, 1)
        self.back_btn.clicked.connect(self.go_back)
        self.next_btn.clicked.connect(self.go_next)
        self.view.linked.connect(lambda url: self.win.open_url(url))
        self.view.verticalScrollBar().valueChanged.connect(lambda _: self.sync_next())

    def load(self, pid, section="", back=None):
        """페이지를 올림. section 은 meta 의 sections 키(3a)이고 그 절로 스크롤함. 없는 페이지면 WebError."""
        page = self.win.web.show(pid)
        self.pid, self.page, self.back, self.section = pid, page, back, section
        self.reached = None
        self.title.setText(page["title"])
        self.title.show()
        self.back_btn.setText(BACK_TEXT.get(back[0], "← 웹 면접 준비") if back else "← 웹 면접 준비")
        self.view.set_markdown(figures_to_images(page["markdown"], page["dir"]), page["dir"], LANG)
        for piece in self.view.pieces:
            if isinstance(piece, FigureView):
                for button in piece.findChildren(QPushButton):
                    button.setObjectName("")  # 여행 화면의 quiet 모양 대신 이 화면의 작은 단추로 그림
                    kit.repolish(button)
        self.headings = [text for text in page["sections"].values() if heading_top(self.view, text) is not None]
        heading = page["sections"].get(section, "") if section else ""
        if heading:
            QTimer.singleShot(0, lambda: scroll_to_heading(self.view, heading))  # 조각이 자리를 잡은 뒤에 스크롤함
        else:
            self.view.verticalScrollBar().setValue(0)
        QTimer.singleShot(0, self.sync_next)

    def next_heading(self):
        """지금 스크롤 자리보다 아래에 있고 마지막에 간 절보다 뒤인 첫 절 제목. 없으면 None."""
        here = self.view.verticalScrollBar().value() + 8
        after = self.headings.index(self.reached) + 1 if self.reached in self.headings else 0
        tops = [(heading_top(self.view, text), text) for text in self.headings[after:]]
        return next((text for top, text in tops if top is not None and top > here), None)

    def sync_next(self):
        """[다음 절] 줄을 다음 절 제목에 맞춤. 다음 절이 없으면 줄을 숨김."""
        if self.page is None:
            return
        text = self.next_heading()
        self.next_row.setVisible(text is not None)
        self.next_title.setText(text or "")

    def go_next(self):
        text = self.next_heading()
        if text:
            self.reached = text
            scroll_to_heading(self.view, text)
            self.sync_next()

    def go_back(self):
        back = self.back
        if back and back[0] == "mission":
            self.win.open_mission(back[1])
        elif back and back[0] == "drill":
            self.win.open_drill(back[1], back[2] if len(back) > 2 else None, resume=True)
        else:
            self.win.go_web()

    def fit_column(self):
        """카드 폭을 창 폭에 맞춘 읽는 글의 단 폭에 맞춤."""
        self.card.setMaximumWidth(kit.doc_width(self.width()) + 48)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_column()

    def set_busy(self, busy, text=""):
        self.back_btn.setEnabled(not busy)

    def restyle(self):
        self.fit_column()
        self.view.restyle(theme.web_css(self.win.zoom), theme.code_font(self.win.zoom))
