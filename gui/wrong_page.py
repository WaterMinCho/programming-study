# -*- coding: utf-8 -*-
"""오답 노트 화면: 위 막대(← 돌아갈 화면 · 오답 노트 · 트랙이 둘 이상이면 트랙 칩), 왼쪽 목록 카드와 오른쪽 문항 카드(칸 나누기), 아래 막대([해설 보기] · [다시 풀기]).

트랙마다 공급자 하나가 오답을 줌. 창(gui/window.py)의 WRONG_TRACKS 에 적은 순서로 칩과 첫 화면의 줄이 놓이고, 공급자는 PythonNotes 와 같은 모양임:
tid·name·empty(오답이 없을 때의 안내), groups() 는 [{"title": 묶음 이름, "items": [문항]}] 이고 문항 dict에 key·label·state를 둠.
detail(문항, 해설) 은 (제목, 본문 HTML)이고 해설 구역 앞에 answer 닻을 둠, explain(문항) 은 detail 에 다시 넘길 해설 값, retry(문항) 은
다시 푸는 화면을 엶. 읽지 못한 것은 SessionError 로 알리고 groups() 는 예외를 내지 않음. state 는 wrong·skipped·fixed 가운데 하나.

왼쪽 목록은 state 로 갈래(틀린 문항 · 미응답 문항 · 다시 맞힌 문항)를 나누고, 갈래 안에서는 묶음 이름(파이썬 스터디는 차시)을 작은 제목으로 둠.
상태는 갈래로만 알리고 줄에는 색이나 꼬리 글을 붙이지 않음. 처음에는 앞의 두 갈래를 펴고 다시 맞힌 문항은 접어 둠. 편 상태는 창이 열려 있는 동안
트랙마다 기억함. 위·아래 화살표, Home·End, PageUp·PageDown 은 갈래 머리 줄과 묶음 이름을 건너뛰고 보이는 문항 줄 사이에서만 고름."""
import html

from PyQt6.QtCore import QEvent, QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QButtonGroup, QFrame, QLabel, QScrollArea, QStackedWidget, QTextBrowser, QWidget

from gui import kit, theme
from gui.mascot import Mascot
from gui.result_page import band, explain_html, md_html, my_answer_html, ref_html
from session import SessionError

CATEGORIES = (("wrong", "틀린 문항"), ("skipped", "미응답 문항"), ("fixed", "다시 맞힌 문항"))  # 목록의 갈래 순서와 이름
OPENED = {"wrong": True, "skipped": True, "fixed": False}  # 갈래를 처음에 펴 두는지
SPLIT = 0.45  # 왼쪽 목록 카드의 처음 몫. 1024 창에서 목록 카드 421, 문항 줄의 글 자리 341(크게 19px 로 "빈칸 채우기 · 12회차 미니 모의고사" 가 다 들어감)
BACK_TEXT = {"python": "← 파이썬 스터디", "hub": "← 처음 화면", "ai": "← AI"}
PICK = "왼쪽 목록에서 문항을 고르세요."
ALL_FIXED = "틀린 문항을 모두 다시 맞혔습니다. 왼쪽의 '다시 맞힌 문항'을 펴면 다시 볼 수 있습니다."
NONE_YET = "아직 틀린 문항이 없습니다."
BAND = (32, 4)  # 문항 칸 띠의 (위, 아래) 여백. 새 문서 규칙은 문단 아래가 16 이고 줄 높이가 넓어서 기본값(14, 8)이면 띠가 위 글에 붙어 보임. 위를 넓히고 아래를 좁혀 띠가 제 아래 글과 묶이게 함
NAV_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown)


def category(note):
    """파이썬 스터디 오답의 갈래. 그 뒤에 맞혔으면 fixed, 아니고 비워 뒀으면 skipped, 나머지는 wrong."""
    return "fixed" if note["fixed"] else "skipped" if note["skipped"] else "wrong"


def count_line(groups):
    """첫 화면 줄에 쓰는 갈래별 문항 수. 없는 갈래는 빼고, 문항이 하나도 없으면 NONE_YET."""
    counts = {state: 0 for state, _ in CATEGORIES}
    for group in groups:
        for item in group["items"]:
            counts[item["state"]] += 1
    parts = ["%s %d개" % (name, counts[state]) for state, name in CATEGORIES if counts[state]]
    return " · ".join(parts) if parts else NONE_YET


def item_html(note, item, info):
    """첫 시도의 결과와 틀린 회차, 참고 자료, 문제, 내 답. info(해설)가 있으면 결과 화면과 같은 정답과 해설을 덧붙임.
    참고 자료는 정답을 알려 주지 않아서 해설을 펴기 전에도 보여 줌. 은행 문항에 ref 가 없으면 참고 자료와 문제 띠를 넣지 않음.
    상태는 왼쪽 분류가 알려 주므로 첫 줄은 색 없이 첫 시도 결과와 회차만 적고, 다시 맞힘은 따로 적지 않음."""
    name, _ = theme.result_label("skipped" if note["skipped"] else "wrong")
    facts = [note["round_title"]]
    if note["wrong_count"] > 1:
        facts.append("%d개 회차에서 틀림" % note["wrong_count"])
    parts = ['<p><b>%s</b> <span class="muted">· %s</span></p>' % (name, " · ".join(facts))]
    if item["ref"]:  # 문제 본문이 참고 자료 목록에 이어 붙어 보이지 않게 문제에도 띠를 붙임
        parts += [ref_html(item["ref"], BAND), band("문제", space=BAND)]
    parts += [md_html(item["body_md"]), band("내 답", space=BAND), my_answer_html(item)]
    if info is not None:
        parts.append(explain_html(item, info, BAND))
    return "<body>%s</body>" % "".join(parts)


def detail_css():
    """문항 칸의 CSS. 새 화면 문서 규칙(theme.web_css)에 코드 상자 바탕을 더함. web_css 는 상자 바탕을 DocView 가 칠한다고 보고 투명하게 둠."""
    return theme.web_css() + "td.codebox { background-color: %s; }" % theme.color("codebox_bg")


class PythonNotes:
    """파이썬 스터디의 오답 공급자. 첫 제출에서 틀렸거나 비워 둔 문항을 차시별로 묶어 줌(session.wrong_notes). 문항은 그 dict 에
    label(유형 · 회차)과 state 를 더한 것임."""
    tid, name = "python", "파이썬 스터디"
    empty = "아직 틀린 문항이 없습니다. 회차를 제출하면 틀린 문항이 여기에 모입니다."

    def __init__(self, win):
        self.win = win

    def groups(self):
        return [{"title": "%d차시 · %s" % (int(unit["unit"][1:]), unit["title"]),
                 "items": [dict(note, label="%s · %s" % (note["type_label"], note["round_title"]), state=category(note)) for note in unit["items"]]}
                for unit in self.win.session.wrong_notes()]

    def detail(self, note, info):
        """그 회차의 답안지가 깨졌으면 SessionError. [다시 풀기]를 누르면 창이 복구를 제안함."""
        item = self.win.session.wrong_item(note["round"], note["id"])
        label = "%s · %s · %d점" % (item["type_label"], item["unit_title"], item["points"])
        return ("%s · %s" % (item["title"], label) if item["kind"] == "code" else label), item_html(note, item, info)

    def explain(self, note):
        """터미널에서 일부만 채점해 아직 끝나지 않은 회차면 SessionError."""
        return self.win.session.explain(note["round"], note["id"])

    def retry(self, note):
        """끝낸 회차는 다시 풀기 화면으로 엶. 터미널에서 일부만 채점해 끝나지 않은 회차는 홈의 이어 풀기와 같은 풀이 화면으로 엶."""
        self.win.open_round(note["round"], review=note["completed"], select=note["id"])


class Arrow(QWidget):
    """갈래 머리 줄 앞의 꺾쇠. 펴면 아래, 접으면 오른쪽을 가리킴. 칠할 때마다 지금 테마의 색을 읽음."""

    def __init__(self):
        super().__init__()
        self.opened = True
        self.setFixedSize(kit.MARK, kit.MARK)

    def set_opened(self, opened):
        self.opened = opened
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(theme.qcolor("muted"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        points = ((5, 7.5), (10, 12.5), (15, 7.5)) if self.opened else ((7.5, 5), (12.5, 10), (7.5, 15))
        path = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QPointF(*point))
        painter.drawPath(path)


class KeyRing:
    """키보드로 받은 초점에만 테두리를 표시함(Fold, NoteRow 앞에 섞음).
    마우스로 누른 줄도 초점을 받아 화살표로 이동할 수 있음."""
    keyed = False

    def focusInEvent(self, event):
        if event.reason() != Qt.FocusReason.ActiveWindowFocusReason:  # 창을 다시 앞으로 가져올 때는 처음 받은 방법을 따름
            self.keyed = event.reason() != Qt.FocusReason.MouseFocusReason
        super().focusInEvent(event)

    def paintEvent(self, event):
        if self.keyed:
            super().paintEvent(event)
        else:  # kit.Row.paintEvent 는 초점이 있으면 늘 테두리를 그려서 그 앞의 QFrame 만 칠함
            QFrame.paintEvent(self, event)


class Fold(KeyRing, kit.Row):
    """갈래 머리 줄: 꺾쇠, 갈래 이름(headline), 문항 수 꼬리표. 누르거나 Enter·Space 를 치면 펴고 접고, ← 는 접고 → 는 폄.
    body 는 그 갈래의 묶음 이름과 문항 줄을 담은 위젯이고 접으면 숨김."""
    toggled = pyqtSignal(bool)

    def __init__(self, state, title, count):
        super().__init__(title, mark=Arrow())
        self.state, self.body, self.opened = state, None, True
        kit.typed(self.title, "headline", True)
        self.count = kit.badge(str(count))
        self.layout().insertWidget(self.layout().indexOf(self.end), self.count, 0, Qt.AlignmentFlag.AlignVCenter)
        self.chevron.hide()
        self.refont()
        self.title.refont()
        self.clicked.connect(lambda: self.set_opened(not self.opened))

    def refont(self):
        super().refont()
        self.title.setFixedHeight(theme.TYPE["headline"][1])

    def set_opened(self, opened):
        self.opened = opened
        self.mark.set_opened(opened)
        if self.body is not None:
            self.body.setVisible(opened)
        self.toggled.emit(opened)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.set_opened(event.key() == Qt.Key.Key_Right)
        else:
            super().keyPressEvent(event)


class NoteRow(KeyRing, kit.Row):
    """문항 줄. 꺾쇠 없는 한 줄(label)이고 글은 갈래 이름과 같은 세로선(kit.ROW_TEXT)에서 시작함. 문항은 data 에 둠.
    고르면 picked 모양(selection 바탕)이 됨. Tab 은 고른 줄 하나에만 닿고 나머지 줄은 누르거나 화살표로 옮김."""

    def __init__(self, item):
        super().__init__(item["label"], data=item)
        self.chevron.hide()
        self.layout().setContentsMargins(kit.ROW_TEXT, 0, 24, 0)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def set_picked(self, picked):
        if self.property("picked") != picked:
            self.setProperty("picked", picked)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if picked else Qt.FocusPolicy.ClickFocus)
            for widget in [self] + self.findChildren(QLabel):  # 글자색은 줄의 picked 로 정해져서 글도 다시 칠함
                kit.repolish(widget)


class NoteList(QScrollArea):
    """왼쪽 목록. 갈래마다 머리 줄(Fold)과 그 아래 묶음 이름, 문항 줄(NoteRow). 줄을 누르거나 화살표로 옮기면 picked(문항)를 냄."""
    picked = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # 키보드 초점은 줄마다 받음
        self.setProperty("flat", True)  # 카드 안 스크롤 칸의 투명 규칙(theme.STYLE_V2)을 받아 카드의 둥근 모서리가 보임
        self.sheet = QWidget()
        self.box = kit.box(self.sheet, (0, 8, 0, 8))
        self.box.addStretch(1)
        self.setWidget(self.sheet)
        self.folds, self.rows, self.order, self.current = [], [], [], None  # order 는 머리 줄과 문항 줄의 화면 순서

    def clear(self):
        while self.box.count() > 1:  # 맨 끝의 남는 칸은 둠
            widget = self.box.takeAt(0).widget()
            widget.hide()
            widget.deleteLater()
        self.folds, self.rows, self.order, self.current = [], [], [], None

    def fill(self, groups, opened):
        """groups 는 공급자의 묶음 목록. 문항이 없는 갈래는 빼고, opened(갈래 → 폄)대로 펴 두며 사람이 펴고 접으면 opened 에 적음.
        고른 줄은 없애고 맨 위로 감."""
        self.clear()
        self.verticalScrollBar().setValue(0)
        for state, name in CATEGORIES:
            parts = [(group["title"], [item for item in group["items"] if item["state"] == state]) for group in groups]
            parts = [(title, items) for title, items in parts if items]
            if not parts:
                continue
            if self.folds:  # 갈래 사이에 line 색 1px 선(좌우 24 들여서)
                rule = kit.frame("rowline")
                rule.setFixedHeight(1)
                line = QWidget()
                kit.box(line, (24, 8, 24, 8)).addWidget(rule)
                self.box.insertWidget(self.box.count() - 1, line)
            fold = Fold(state, name, sum(len(items) for _, items in parts))
            fold.installEventFilter(self)
            self.box.insertWidget(self.box.count() - 1, fold)
            self.order.append(fold)
            fold.body = QWidget()
            body_box = kit.box(fold.body, (0, 0, 0, 8))
            for title, items in parts:  # 묶음 이름 위를 넓게 띄워 아래 줄과 묶음. 목록 칸이 좁으면 줄임표로 줄임
                head = QWidget()
                kit.box(head, (kit.ROW_TEXT, 20, 24, 0)).addWidget(kit.ElideLabel(title, "caption", "secondary", bold=True))
                body_box.addWidget(head)
                for item in items:
                    row = NoteRow(item)
                    row.clicked.connect(lambda row=row: self.pick(row))
                    row.installEventFilter(self)
                    body_box.addWidget(row)
                    self.rows.append(row)
                    self.order.append(row)
            self.box.insertWidget(self.box.count() - 1, fold.body)  # 상자에 넣어 부모가 생긴 뒤에 펴고 접음
            fold.toggled.connect(lambda on, state=state: opened.__setitem__(state, on))
            fold.set_opened(opened[state])
            self.folds.append(fold)

    def fold_of(self, state):
        return next((fold for fold in self.folds if fold.state == state), None)

    def row_of(self, key):
        return next((row for row in self.rows if row.data["key"] == key), None)

    def shown(self):
        """보이는(갈래가 펴진) 문항 줄. 화면 순서."""
        return [row for row in self.rows if row.isVisibleTo(self.sheet)]

    def selected(self):
        """고른 문항. 없으면 None."""
        return self.current.data if self.current is not None else None

    def pick(self, row, focus=False):
        """row 를 고르고 그 줄이 보이게 스크롤한 뒤 picked 를 냄. None 이면 고른 것을 없앰. focus 면 키보드 초점도 그 줄로 옮김."""
        if self.current is not None and self.current is not row:
            self.current.set_picked(False)
        self.current = row
        if row is not None:
            row.set_picked(True)
            if focus:
                row.setFocus(Qt.FocusReason.OtherFocusReason)
            QTimer.singleShot(0, lambda: self.reveal(row))  # 새로 채운 목록은 줄이 자리를 잡은 뒤에야 위치를 앎
        self.picked.emit(self.selected())

    def reveal(self, row):
        if row is self.current and row.isVisibleTo(self.sheet):
            for _ in range(3):  # 갈래를 막 폈거나 목록을 새로 채웠으면 미뤄 둔 배치가 안쪽 상자부터 한 겹씩 남아 있어 먼저 끝냄
                QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
            self.ensureWidgetVisible(row, 0, 8)

    def step(self, origin, key):
        """origin(머리 줄이나 문항 줄)에서 key 쪽의 보이는 문항 줄을 고름. 머리 줄에서 아래로 가면 그 아래 첫 줄, 위로 가면 그 위 마지막 줄."""
        shown = self.shown()
        if not shown:
            return
        if key in (Qt.Key.Key_Home, Qt.Key.Key_End):
            target = shown[0] if key == Qt.Key.Key_Home else shown[-1]
        elif origin in shown:
            page = max(1, self.viewport().height() // theme.CONTROL["row"])
            jump = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1, Qt.Key.Key_PageUp: -page, Qt.Key.Key_PageDown: page}[key]
            target = shown[max(0, min(len(shown) - 1, shown.index(origin) + jump))]
        else:
            at = self.order.index(origin) if origin in self.order else 0
            down = key in (Qt.Key.Key_Down, Qt.Key.Key_PageDown)
            near = [row for row in (self.order[at + 1:] if down else reversed(self.order[:at])) if row in shown]
            if not near:
                return
            target = near[0]
        self.pick(target, focus=True)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in NAV_KEYS:
            self.step(watched, event.key())
            return True
        return super().eventFilter(watched, event)


class WrongPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName("page")
        self.win = win
        self.tracks = list(win.wrong_tracks)
        self.track = self.tracks[0]
        self.back = "python"
        self.groups = []
        self.revealed = {}  # [해설 보기]를 누른 문항의 해설 {(트랙, 문항 키): 공급자 explain 의 값}
        self.explainable = False
        self.keys = {}  # 트랙마다 마지막으로 고른 문항 키. 목록을 새로 채워도 그 문항을 다시 고름
        self.busy = False
        self.opened = {track.tid: dict(OPENED) for track in self.tracks}
        root = kit.box(self)

        self.top = kit.TopBar(BACK_TEXT["python"], "오답 노트")
        self.back_btn = self.top.back
        self.chips = {}
        self.chip_row = chips = QWidget()  # 트랙이 둘 이상일 때만 보임. 하나뿐이면 돌아가기 단추와 같은 이름이 한 번 더 보여서 숨김
        chip_box = kit.box(chips, spacing=8, horizontal=True)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        for track in self.tracks:
            chip = kit.chip(track.name, track.tid)
            chip.clicked.connect(lambda checked=False, tid=track.tid: self.show_track(tid))
            self.chip_group.addButton(chip)
            chip_box.addWidget(chip)
            self.chips[track.tid] = chip
        self.top.add_right(chips)
        chips.setVisible(len(self.tracks) > 1)
        root.addWidget(self.top)

        self.list = NoteList()
        list_card, list_box = kit.card(0, 0)
        list_box.addWidget(self.list)
        detail_card, detail_box = kit.card(24, theme.GAP["title_description"])
        self.item_title = kit.para("", "headline")  # 긴 코드 문제 제목은 줄을 바꿈
        self.detail = QTextBrowser()
        self.detail.setObjectName("plain")
        self.detail.setOpenLinks(False)
        self.detail.anchorClicked.connect(self.open_reference)
        self.detail.document().setDocumentMargin(0)
        detail_box.addWidget(self.item_title)
        detail_box.addWidget(self.detail, 1)
        self.split = kit.splitter(Qt.Orientation.Horizontal, "wrong/split", SPLIT, 24, win.settings)
        self.split.addWidget(list_card)
        self.split.addWidget(detail_card)
        body = QWidget()
        kit.box(body, (kit.MARGIN, 24, kit.MARGIN, 24)).addWidget(self.split)
        self.bar = kit.BottomBar()
        self.explain_btn = self.bar.add_action(kit.button("해설 보기", "secondary", "l"))
        self.retry_btn = self.bar.add_action(kit.button("다시 풀기", "primary", "l"))
        self.retry_btn.setToolTip("선택한 문항을 다시 푸는 화면을 엽니다.")
        self.filled = QWidget()  # 오답이 있는 트랙: 두 카드와 아래 막대
        filled_box = kit.box(self.filled)
        filled_box.addWidget(body, 1)
        filled_box.addWidget(self.bar)

        self.empty = QWidget()
        empty_box = kit.box(self.empty, (kit.MARGIN, 24, kit.MARGIN, 24), 16)
        self.empty_text = kit.para("", "body", "secondary")
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        empty_box.addStretch(1)
        empty_box.addWidget(Mascot(88), 0, Qt.AlignmentFlag.AlignHCenter)
        empty_box.addWidget(self.empty_text)
        empty_box.addStretch(2)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.filled)
        self.stack.addWidget(self.empty)
        root.addWidget(self.stack, 1)

        self.list.picked.connect(self.show_item)
        self.explain_btn.clicked.connect(self.reveal)
        self.retry_btn.clicked.connect(self.retry)
        self.back_btn.clicked.connect(self.go_back)

    def open(self, tid=None, back="python"):
        """화면을 열 때 부름. tid 트랙(없으면 지난번 트랙)을 보이고, 위 막대의 돌아가기를 back(python 은 파이썬 스터디 홈, hub 는 첫 화면)으로 둠."""
        self.back = back if back in BACK_TEXT else "python"
        self.back_btn.setText(BACK_TEXT[self.back])
        self.show_track(tid or self.track.tid)

    def show_track(self, tid):
        self.track = next((track for track in self.tracks if track.tid == tid), self.tracks[0])
        for key, chip in self.chips.items():
            chip.setChecked(key == self.track.tid)
        self.refresh()

    def refresh(self):
        """공급자에게서 오답을 다시 읽어 목록을 새로 채움. 이 트랙에서 고르던 문항이 남아 있으면 다시 고르고, 접힌 갈래에 있으면 그 갈래를 폄.
        없으면 펴 둔 갈래의 첫 문항을 고름. 펼친 해설은 접음."""
        tid = self.track.tid
        self.groups, self.revealed = self.track.groups(), {}
        self.list.fill(self.groups, self.opened[tid])
        self.empty_text.setText(self.track.empty)
        self.stack.setCurrentWidget(self.filled if any(group["items"] for group in self.groups) else self.empty)
        row = self.list.row_of(self.keys.get(tid))
        if row is not None and not self.opened[tid][row.data["state"]]:
            self.list.fold_of(row.data["state"]).set_opened(True)
        self.list.pick(row if row is not None else next(iter(self.list.shown()), None))
        self.chain()

    def chain(self):
        """Tab 순서를 화면 순서(돌아가기, 칩, 목록, 문항 칸, 아래 단추)로 다시 맺음. 목록 줄은 새로 채울 때마다 새로 만들어져
        그대로 두면 창의 Tab 순서 맨 끝, 아래 단추 뒤에 붙음. 숨은 것과 Tab 을 받지 않는 문항 줄은 Qt 가 건너뜀."""
        widgets = [self.back_btn] + list(self.chips.values()) + self.list.order + [self.detail, self.explain_btn, self.retry_btn]
        for first, second in zip(widgets, widgets[1:]):
            QWidget.setTabOrder(first, second)

    def selected(self):
        """고른 문항(공급자가 준 dict). 없으면 None."""
        return self.list.selected()

    def show_item(self, item):
        """고른 문항의 제목과 본문. 고른 것이 없으면 안내 한 줄."""
        self.item_title.setText("")
        self.explainable = False  # [해설 보기]를 누를 수 있는지. 본문을 읽었고 해설을 아직 펴지 않은 문항만 누름
        if item is None:
            items = [i for group in self.groups for i in group["items"]]
            text = ALL_FIXED if items and all(i["state"] == "fixed" for i in items) else PICK
            self.detail.setHtml('<body><p class="muted">%s</p></body>' % html.escape(text))
        else:
            self.keys[self.track.tid] = item["key"]
            try:
                title, body = self.track.detail(item, self.revealed.get((self.track.tid, item["key"])))
            except SessionError as error:  # 그 회차의 답안지가 깨짐. [다시 풀기]를 누르면 복구를 제안함
                self.detail.setHtml("<body><p>%s</p></body>" % html.escape(str(error)))
            else:
                self.item_title.setText(title)
                self.detail.setHtml(body)
                self.explainable = (self.track.tid, item["key"]) not in self.revealed
        self.item_title.setVisible(bool(self.item_title.text()))
        self.explain_btn.setEnabled(self.explainable and not self.busy)
        self.retry_btn.setEnabled(item is not None and not self.busy)

    def reveal(self):
        item = self.selected()
        try:
            self.revealed[(self.track.tid, item["key"])] = self.track.explain(item)
        except SessionError as error:  # 터미널에서 일부만 채점해 아직 끝나지 않은 회차
            self.win.ask("알림", str(error))
            return
        self.show_item(item)
        self.detail.scrollToAnchor("answer")  # 문제 본문이 길어도 해설이 바로 보이게

    def retry(self):
        self.track.retry(self.selected())

    def open_reference(self, url):
        """현재 문항의 학습 단계만 엶. 문서 속 외부 주소는 따라가지 않음."""
        item = self.selected()
        if url.toString() != "study-note" or item is None or not hasattr(self.track, "open_reference"):
            return
        try:
            self.track.open_reference(item)
        except SessionError as error:
            self.win.ask("알림", str(error))

    def go_back(self):
        focus = QApplication.focusWidget()
        if focus is not None and self.list.isAncestorOf(focus):  # 숨는 줄의 초점이 다음 화면의 첫 단추로 넘어가 테두리가 그려지지 않게 놓음
            focus.clearFocus()
        if self.back == "hub":
            self.win.go_hub()
        elif self.back == "ai":
            self.win.go_ai()
        else:
            self.win.go_home()

    def set_busy(self, busy, text=""):
        """돌아가기로 첫 화면을 열 때 창이 Node.js 를 찾는 동안 부름. 그동안 목록과 칩도 꺼서 다른 문항이나 트랙으로 옮겨 단추가 다시 켜지지 않게 함."""
        self.busy = busy
        for widget in (self.back_btn, self.chip_row, self.list):
            widget.setEnabled(not busy)
        self.explain_btn.setEnabled(not busy and self.explainable)
        self.retry_btn.setEnabled(not busy and self.selected() is not None)

    def restyle(self):
        """글자 크기나 테마가 바뀌면 부름. 본문 CSS 를 다시 주고 꺾쇠를 다시 칠하며, 읽던 자리는 지킴."""
        self.detail.document().setDefaultStyleSheet(detail_css())
        for arrow in self.findChildren(Arrow):
            arrow.update()
        bar = self.detail.verticalScrollBar()
        place = bar.value()
        self.show_item(self.selected())
        bar.setValue(place)
