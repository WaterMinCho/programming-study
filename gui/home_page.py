# -*- coding: utf-8 -*-
"""파이썬의 다음 회차·숙달 단원·지난 회차를 모음. 제출은 창 아래 공통 영역에서 다룸."""
import html

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QWidget

from gui import feedback, kit, theme
from gui.widgets import LinkLabel, UnitStrip


def card(title, description=None):
    frame, box = kit.card(spacing=theme.GAP["group"])
    title = kit.label(title, "headline")
    box.addWidget(kit.heading(title, description) if description is not None else title)
    return frame, box


def muted(text=""):
    return kit.para(text, "body", "secondary")


class HomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.win = win
        outer = kit.box(self)
        top = kit.TopBar("학습 현황", "파이썬 스터디")
        self.hub_btn = top.back
        self.wrong_btn = top.add_right(kit.button("오답 노트", "text"))
        self.theme_btn = top.add_right(kit.button("", "text"))
        self.theme_btn.setToolTip("화면 테마를 시스템·밝게·어둡게 순서로 바꿉니다.")
        outer.addWidget(top)
        inner = QWidget()
        root = kit.box(inner, (0, 24, 0, 32), 24)
        self.user = kit.label("", "caption", "tertiary")
        root.addWidget(self.user)
        self.data_btn = kit.button("학습 데이터")
        self.data_btn.setToolTip("파이썬 학습 기록의 수집 설정·전송 상태·파일 내보내기 창을 엽니다.")
        self.data_btn.clicked.connect(self.show_data)
        root.addWidget(self.data_btn)
        self.notice = LinkLabel()
        kit.typed(self.notice, "body")
        self.notice.setObjectName("notice")
        self.notice.linkActivated.connect(lambda _: win.show_notice_detail())
        self.notice.hide()
        root.addWidget(self.notice)
        self.next_card = kit.NextCard()
        self.next_card.caption.setText("다음 회차")
        self.action_desc, self.action_btn = self.next_card.line, self.next_card.button
        root.addWidget(self.next_card)
        units_card, box = card("단원별 학습")
        self.ready = kit.label("", "display")
        self.mastered = kit.label("", "caption", "secondary")
        self.ready_bar = kit.progress()
        box.addWidget(kit.spaced(self.ready, self.mastered, spacing=theme.GAP["detail"]))
        box.addWidget(self.ready_bar)
        self.strip = UnitStrip()
        self.weak = kit.para("", "body", "secondary")
        box.addWidget(self.strip)
        box.addWidget(self.weak)
        root.addWidget(units_card)
        self.rounds_hint = kit.para("", "caption", "secondary")
        rounds_card, box = card("지난 회차", self.rounds_hint)
        self.rounds = QListWidget()
        kit.typed(self.rounds, "caption")
        self.rounds.setObjectName("plain")
        self.rounds.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rounds.setMinimumHeight(160)
        box.addWidget(self.rounds)
        root.addWidget(rounds_card)
        self.git_hint = kit.para("", "caption", "secondary")
        root.addWidget(self.git_hint)
        self.status = kit.para("", "caption", "secondary")
        self.busy_bar = kit.progress()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.hide()
        root.addWidget(self.status)
        root.addWidget(self.busy_bar)
        self.foot = LinkLabel('<a href="%s">불편한 점 알리기</a>' % feedback.ISSUE_URL)
        kit.typed(self.foot, "caption")
        self.foot.setOpenExternalLinks(False)
        self.foot.linkActivated.connect(lambda _: QDesktopServices.openUrl(QUrl(feedback.issue_url(win))))
        root.addWidget(self.foot)
        column = kit.column(inner)
        column.layout().setContentsMargins(32, 0, 32, 0)
        outer.addWidget(kit.scroll(column), 1)
        self.hub_btn.clicked.connect(win.go_hub)
        self.wrong_btn.clicked.connect(lambda: win.show_wrong("python", "python"))
        self.theme_btn.clicked.connect(win.cycle_theme)
        self.action_btn.clicked.connect(win.start_next)
        self.rounds.itemClicked.connect(lambda item: win.show_result(item.data(Qt.ItemDataRole.UserRole)))

    def show_data(self):
        from gui.ai_data import LearningDataDialog
        self.data_dialog = LearningDataDialog(self, self.win.session.collection, host=self.win)
        self.data_dialog.show()

    def refresh(self):
        win = self.win
        overview = win.session.overview()
        self.data_btn.setText("학습 데이터 · 저장 확인 필요" if win.session.collection.error else "학습 데이터")
        self.user.setText("ID: %s" % overview["user"])
        self.ready.setText("%d / %d" % (overview["mastered"], overview["total_units"]))
        self.mastered.setText("숙달한 단원 / 전체 단원")
        self.ready_bar.setRange(0, max(1, overview["total_units"]))
        self.ready_bar.setValue(overview["mastered"])
        self.strip.set_units(overview["units"])
        tags = overview["weak_tags"]
        self.weak.setText("다시 볼 개념: " + ", ".join(tags) if tags else ("아직 틀린 문항이 없습니다." if win.session.prof["attempts"] else "문제를 풀면 다시 볼 개념을 모아 보여 줍니다."))
        label, desc = win.next_action(overview)
        self.next_card.set_item(label.removesuffix(" 시작").removesuffix(" 이어 풀기"), desc, label)
        self.rounds.clear()
        done = [r for r in overview["rounds"] if r["completed"]]
        for r in reversed(done):
            earned, total = (int(n) for n in (r["first_score"] or r["score"]).split("/"))
            item = QListWidgetItem("%s    %d / %d점 (%d%%)" % (r["title"], earned, total, round(100 * earned / total) if total else 0))
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.rounds.addItem(item)
        self.rounds_hint.setText("회차를 누르면 결과와 해설을 다시 볼 수 있습니다. 목록에는 첫 제출 때 받은 점수가 나옵니다." if done else "아직 제출한 회차가 없습니다.")
        usable = win.gitflow is not None
        self.git_hint.setVisible(not usable)
        self.git_hint.setText("" if usable else "지금은 제출과 문제 받기를 쓸 수 없습니다.\n" + win.git_reason)
        note = win.notice
        self.notice.setVisible(bool(note))
        if note:
            more = ' <a href="detail">자세히</a>' if note.get("detail") else ""
            self.notice.setText(html.escape(note.get("message") or "") + more)

    def restyle(self):
        self.theme_btn.setText("테마: %s" % theme.MODES[theme.state["mode"]])

    def set_busy(self, busy, text=""):
        for widget in (self.action_btn, self.rounds, self.wrong_btn, self.hub_btn, self.data_btn):
            widget.setEnabled(not busy)
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")
