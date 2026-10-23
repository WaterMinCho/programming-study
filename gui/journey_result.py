# -*- coding: utf-8 -*-
"""알고리즘 여행 문제 화면의 결과 카드. 맨 위에 머리(headline, 진행 막대, caption)를 고정하고 그 아래 스크롤 칸에 완료 띠와 결과 본문을 둠.

머리 글은 journey_text.result_head 가 정하고 본문은 journey_html.run_body·grade_body 의 프로그래머스 꼴 HTML 임.
실행·채점 중에는 줄이 올 때마다 본문에 붙이고 스크롤 칸만 맨 아래로 내려서 머리는 늘 보임. 끝나면 스크롤 칸을 맨 위로 올림.
결과가 없을 때 접으면(set_collapsed) 머리 글 두 줄만 남음. 스크롤 칸은 카드 아래 끝에 닿으므로 flat 속성을 달아 바탕을 칠하지 않고
카드가 면과 둥근 모서리를 그림(theme.STYLE_V2 의 카드 안 flat 스크롤 칸 규칙)."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QScrollArea, QWidget

from gui import journey_html, journey_text, kit, theme
from gui.docview import TextPiece

PAD = 24  # 카드 안쪽 여백


class JourneyResult(QFrame):
    """결과 카드. show_empty 는 결과가 아직 없을 때, show_result 는 실행·채점 결과(진행 중이면 done=False)를 그림.
    text() 는 머리, caption, 띠 글, 본문 글을 이은 것. 완료 띠의 단추를 누르면 acted(행동 키)를 냄."""
    acted = pyqtSignal(str)  # "explain"(해설 탭) 또는 "boss"(보스 문제)

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.collapsed = False
        self.following = False  # 진행 중이라 본문이 늘 때마다 스크롤 칸을 맨 아래로 내림
        self.shown = (None, {}, True, "", 0)  # 지금 그린 (종류, 결과, 끝났는지, 채점 단계, 지난 초). redraw 가 같은 dict 로 다시 그림
        self.box = kit.box(self, spacing=16)
        self.head = QWidget()
        head_box = kit.box(self.head, (PAD, PAD, PAD, 0))
        self.title = kit.para("", "headline")
        self.gap = QWidget()  # 막대가 없을 때 headline 과 caption 사이 4
        self.gap.setFixedHeight(4)
        self.bar_box = QWidget()  # 막대와 그 위 12, 아래 8
        self.bar = kit.progress()
        kit.box(self.bar_box, (0, 12, 0, 8)).addWidget(self.bar)
        self.caption = kit.para("", "caption", "secondary")
        for widget in (self.title, self.gap, self.bar_box, self.caption):
            head_box.addWidget(widget)
        self.box.addWidget(self.head)

        self.scroll = QScrollArea()
        self.scroll.setProperty("flat", True)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner_box = kit.box(inner, (PAD, 0, PAD, PAD))
        self.banners = QWidget()  # 완료 띠들. 띠 사이 8, 마지막 띠 아래 16
        self.banners_box = kit.box(self.banners, (0, 0, 0, 16), 8)
        self.banners.hide()
        self.body = TextPiece("<body></body>", theme.result_css())
        inner_box.addWidget(self.banners)
        inner_box.addWidget(self.body)
        inner_box.addStretch(1)
        self.scroll.setWidget(inner)
        self.box.addWidget(self.scroll, 1)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._follow)

    # 그리기

    def show_empty(self, best=None, mine=0):
        """결과가 없을 때의 머리. best 는 지금 언어의 최고 점수(기록이 없으면 None), mine 은 내 테스트 수. 스크롤 칸은 비움."""
        self.shown = (None, {"best": best, "mine": mine}, True, "", 0)
        self.following = False
        self._head(journey_text.result_head(best=best, mine=mine))
        self._body("<body></body>", [])

    def show_result(self, kind, result, done=True, stage="", seconds=0):
        """kind 는 "run"·"grade". done=False 는 진행 중이고 result 는 그때까지 온 줄임. stage·seconds 는 채점 단계 문장과 지난 초.
        진행 중에는 스크롤 칸을 맨 아래로, 끝나면 맨 위로 둠."""
        head = self.show_head(kind, result, done, stage, seconds)
        body = (journey_html.run_body if kind == "run" else journey_html.grade_body)(result, done)
        self._body(body, head["banners"] if done else [])
        self.following = not done
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum() if self.following else 0)

    def show_head(self, kind, result, done=True, stage="", seconds=0):
        """머리만 다시 그림(채점 중 1초마다 지난 초). 그린 머리 dict 를 돌려줌."""
        self.shown = (kind, result, done, stage, seconds)
        head = journey_text.result_head(kind, result, done, stage=stage, seconds=seconds)
        self._head(head)
        return head

    def _head(self, head):
        self.title.setText(head["title"])
        self.caption.setText(head["caption"])
        self.caption.setVisible(bool(head["caption"]))
        bar = head["bar"]
        if bar == "busy":
            self.bar.setRange(0, 0)
        elif bar is not None:
            value, most = bar
            self.bar.setRange(0, max(1, round(most * 10)))
            self.bar.setValue(round(value * 10))
        kit.set_tone(self.bar, head["tone"])
        shown = bar is not None and not self.collapsed
        self.bar_box.setVisible(shown)
        self.gap.setVisible(not shown and bool(head["caption"]))
        self.fit_height()

    def _body(self, markup, banners):
        while self.banners_box.count():
            widget = self.banners_box.takeAt(0).widget()
            widget.hide()
            widget.deleteLater()
        for text, action, key in banners:
            banner = kit.banner(text, "success", action=action)
            banner.action.clicked.connect(lambda checked=False, key=key: self.acted.emit(key))
            self.banners_box.addWidget(banner)
        self.banners.setVisible(bool(banners))
        self.body.markup = markup
        self.body.restyle(theme.result_css())

    def _follow(self, low, high):
        """진행 중에 본문이 늘어 스크롤 범위가 바뀌면 맨 아래로 따라감. 높이는 레이아웃이 나중에 정하므로 범위가 바뀐 뒤에 내림."""
        if self.following:
            self.scroll.verticalScrollBar().setValue(high)

    # 접기

    def set_collapsed(self, collapsed):
        """접으면 막대와 스크롤 칸을 숨기고 머리 글 두 줄과 아래 여백 24 만 남김. 카드 높이를 그 높이로 묶어서 칸 나누기가
        남는 높이를 편집기에 줌. 펴면 묶음을 풂."""
        self.collapsed = bool(collapsed)
        self.scroll.setVisible(not self.collapsed)
        self.box.setContentsMargins(0, 0, 0, PAD if self.collapsed else 0)
        if self.collapsed:
            self.bar_box.hide()
            self.gap.setVisible(bool(self.caption.text()))
            self.fit_height()
        else:
            self.redraw()

    def fit_height(self):
        """접힌 카드는 높이를 지금 머리 글의 높이로 묶어서 칸 나누기가 남는 높이를 편집기에 줌. 펼친 카드는 머리가 눌리지 않을 만큼만
        줄어듦(headline 과 caption 의 줄 높이로 셈). 글이나 폭, 글자 크기가 바뀌면 다시 부름."""
        if self.collapsed:
            height = self.folded_height()
            self.setMinimumHeight(height)
            self.setMaximumHeight(height)
        else:
            self.setMinimumHeight(2 * PAD + 4 + theme.TYPE["headline"][1] + theme.TYPE["caption"][1])
            self.setMaximumHeight(16777215)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():  # 폭이 바뀌면 머리 글의 줄바꿈이 바뀔 수 있음
            self.fit_height()

    def folded_height(self):
        """접힌 카드의 높이: 위 24, headline, 4, caption, 아래 24. 글의 줄바꿈은 지금 카드 폭으로 잼."""
        width = max(1, (self.width() if self.width() > 2 * PAD else self.sizeHint().width()) - 2 * PAD)
        lines = sum(label.heightForWidth(width) for label in (self.title, self.caption) if label.text())
        return 2 * PAD + 4 + lines

    # 글자 크기 · 테마

    def redraw(self):
        """지금 그린 결과를 같은 dict 로 다시 그림(테마·글자 크기가 바뀌거나 펼칠 때). 스크롤 자리는 지킴."""
        bar = self.scroll.verticalScrollBar()
        place = bar.value()
        kind, result, done, stage, seconds = self.shown
        following = self.following
        if kind is None:
            self.show_empty(**result)
        else:
            self.show_result(kind, result, done, stage, seconds)
        self.following = following
        if not following:
            bar.setValue(place)

    def text(self):
        parts = [self.title.text(), self.caption.text()]
        parts += [banner.text.text() for banner in self.banners.findChildren(QFrame, "banner") if not banner.isHidden()]
        parts.append(self.body.toPlainText())
        return "\n".join(part for part in parts if part)
