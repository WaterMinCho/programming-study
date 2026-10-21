# -*- coding: utf-8 -*-
"""학습 노트 화면: 머리줄(돌아가기 · 제목)과 page.md 를 그림과 함께 보여 주는 DocView 하나.

figure 블록은 web_mission.figures_to_images 가 그림 줄로 바꾸고, 그림은 알고리즘 여행의 FigureView(gui/docview.py)가 그대로 그림.
드릴 화면의 "학습 노트 읽기"는 절 id(3a)를 주고, 그 절의 제목 줄이 칸 맨 위에 오게 스크롤함. 열 때마다 서비스가 learn 을 기록함."""
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from gui import theme
from gui.docview import DocView, TextPiece
from gui.web_mission import LANG, figures_to_images


def scroll_to_heading(view, text, above=8):
    """DocView 에서 글이 text 인 줄이 칸 맨 위에 오게 스크롤함. 찾으면 True."""
    for piece in view.pieces:
        if not isinstance(piece, TextPiece):
            continue
        block = piece.document().begin()
        while block.isValid():
            if block.text().strip() == text:
                top = piece.y() + piece.document().documentLayout().blockBoundingRect(block).top()
                view.verticalScrollBar().setValue(max(0, int(top) - above))
                return True
            block = block.next()
    return False


class WebLearnPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        self.setProperty("clipboard", True)
        self.win = win
        self.pid, self.page, self.back, self.section = None, None, None, ""
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)
        head = QHBoxLayout()
        self.back_btn = QPushButton("돌아가기")
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.where = QLabel()
        self.where.setObjectName("muted")
        head.addWidget(self.back_btn)
        head.addSpacing(8)
        head.addWidget(self.title, 1)
        head.addWidget(self.where)
        root.addLayout(head)
        self.view = DocView()
        root.addWidget(self.view, 1)
        self.back_btn.clicked.connect(self.go_back)
        self.view.linked.connect(lambda url: self.win.open_url(url))

    def load(self, pid, section="", back=None):
        """페이지를 올림. section 은 meta 의 sections 키(3a)이고 그 절로 스크롤함. 없는 페이지면 WebError."""
        page = self.win.web.show(pid)
        self.pid, self.page, self.back, self.section = pid, page, back, section
        self.title.setText("%s %s" % (pid, page["title"]))
        heading = page["sections"].get(section, "") if section else ""
        self.where.setText("%s 절" % section if heading else "")
        self.view.set_markdown(figures_to_images(page["markdown"], page["dir"]), page["dir"], LANG)
        if heading:
            QTimer.singleShot(0, lambda: scroll_to_heading(self.view, heading))  # 조각이 자리를 잡은 뒤에 스크롤함

    def go_back(self):
        back = self.back
        if back and back[0] == "mission":
            self.win.open_mission(back[1])
        elif back and back[0] == "drill":
            self.win.open_drill(back[1], back[2] if len(back) > 2 else None, resume=True)
        else:
            self.win.go_web()

    def set_busy(self, busy, text=""):
        self.back_btn.setEnabled(not busy)

    def restyle(self):
        self.view.restyle(theme.journey_css(self.win.zoom), theme.code_font(self.win.zoom))
