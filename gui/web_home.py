# -*- coding: utf-8 -*-
"""웹 면접 준비 홈: 머리줄(Node 와 검사 도구 상태 · 설치 관리) · 오늘 복습과 라이브 코딩 미션 카드 · 꼬리 질문 주제 · 학습 노트 ·
막힌 질문에서 아는 데까지 말한 비율.

수치는 모두 webprep.service.WebSession.overview() 가 계산한 값이고, 이 화면은 그것을 목록과 카드로 보여 주기만 함.
목록은 줄 수만큼의 높이를 가지고(다섯 줄까지, 그 위는 스크롤) 나머지 자리는 카드 아래 단추 줄 앞의 빈칸이 받음.
미션·드릴·학습 노트 화면과 첫 화면의 웹 줄 카드가 같이 쓰는 글자 도우미(시계, 미션 상태)도 여기에 둠. 설치 상태 한 줄(stack_line)은
설치 대화상자 모듈에 있고 여기서 다시 내보냄."""
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
                             QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from gui import theme
from gui.round_page import DOT_PX, RowDelegate, dot
from gui.web_setup import SetupDialog, stack_line  # noqa: F401  stack_line 은 허브 카드와 미션 화면이 여기서 가져감
from gui.widgets import Para
from webprep.record import RecordError
from webprep.service import WebError

KIND_LABEL = {"page": "학습 노트", "mission": "미션", "topic": "주제"}  # 다음 추천 앞에 붙는 종류
CHIP_COLUMNS = 3  # 꼬리 질문 주제 칸의 한 줄에 놓는 주제 수. 1024 폭에서도 가장 긴 제목이 줄임표 없이 들어감
LIST_ROWS = 5  # 목록이 스크롤 없이 보이는 줄 수
ROW_FALLBACK = 52  # 빈 목록의 줄 높이
NO_TODAY = "오늘 복습할 사슬이 없습니다. 아래 주제에서 골라 풀 수 있습니다."
NO_STUCK = "막힌 질문에서 아는 데까지 말한 비율은 꼬리 질문에서 [필수] 항목을 빠뜨린 뒤부터 보입니다."


def clock_text(seconds):
    """초를 m:ss 로. 음수는 0:00."""
    seconds = max(0, int(seconds or 0))
    return "%d:%02d" % divmod(seconds, 60)


def day_text(iso):
    """2026-10-24 를 10/24 로. 못 읽으면 그대로."""
    try:
        _, month, day = (int(n) for n in str(iso)[:10].split("-"))
    except ValueError:
        return str(iso or "")
    return "%d/%d" % (month, day)


def mission_state(row):
    """overview()["missions"] 의 한 줄을 상태 글자로. 읽는 중은 남은 읽기 시간, 실전 중은 지난 시간과 단계, 끝남은 통과한 단계 수."""
    if not row["ready"]:
        return "읽을 수 없음" if row["error"] else "준비 중"
    timers = row.get("timers") or {}
    if row["phase"] == "reading":
        left = timers.get("reading_left")
        return "읽는 중 %s" % clock_text(left) if (left or 0) > 0 else "읽는 중 · 읽기 시간 끝"
    if row["phase"] == "live":
        return "실전 중 %s / %d:00 · %d단계" % (clock_text(timers.get("live_elapsed")), row["live_min"], row["current"] or 0)
    if row["phase"] == "done":
        return "끝남 %d/%d" % (row["done_steps"], max(0, row["total_steps"] - 1))
    return row["phase_label"]


def next_text(overview):
    """다음 추천 한 줄."""
    target = overview.get("next")
    if target:
        return "%s %s %s" % (KIND_LABEL.get(target["kind"], ""), target["id"], target["title"])
    if overview.get("ready_missions") or any(t["ready"] for t in overview.get("topics", [])):
        return "출제된 미션과 사슬을 모두 끝냈습니다."
    return "아직 출제된 미션이 없습니다."


def chain_plan(chain):
    """사슬 한 줄의 복습 계획. 상자가 없으면 새 사슬."""
    if chain.get("box") is None:
        return "새 사슬"
    return "상자 %d · 다음 복습 %s" % (chain["box"], day_text(chain.get("due")))


def card(title):
    """제목이 있는 카드. (카드, 내용 상자, 제목 오른쪽 머리줄)."""
    frame = QFrame()
    frame.setObjectName("card")
    box = QVBoxLayout(frame)
    box.setContentsMargins(20, 16, 20, 16)
    box.setSpacing(10)
    head = QHBoxLayout()
    label = QLabel(title)
    label.setObjectName("h2")
    head.addWidget(label)
    head.addStretch(1)
    box.addLayout(head)
    return frame, box, head


def make_list():
    """두 줄짜리 줄이 든 목록. 높이는 채운 뒤 fit_list 가 줄 수에 맞춤."""
    listw = QListWidget()
    listw.setIconSize(QSize(DOT_PX, DOT_PX))
    listw.setItemDelegate(RowDelegate(listw))
    listw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    listw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    fit_list(listw)
    return listw


def fit_list(listw):
    """목록 높이를 줄 수에 맞춤(LIST_ROWS 줄까지, 그 위는 스크롤). 빈 목록은 한 줄 높이."""
    shown = min(listw.count(), LIST_ROWS)
    rows = sum(listw.sizeHintForRow(n) for n in range(shown)) if shown else ROW_FALLBACK
    listw.setFixedHeight(rows + 2 * listw.frameWidth())


def add_row(listw, text, data, color="muted", filled=False, enabled=True):
    item = QListWidgetItem(text)
    item.setData(Qt.ItemDataRole.UserRole, data)
    item.setIcon(dot(theme.color(color), filled))
    if not enabled:
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
    listw.addItem(item)
    return item


def current_data(listw):
    item = listw.currentItem()
    return item.data(Qt.ItemDataRole.UserRole) if item is not None and item.flags() & Qt.ItemFlag.ItemIsEnabled else None


class TopicChip(QFrame):
    """꼬리 질문 주제 하나. 한 줄에 번호와 제목, 오른쪽에 푼 사슬 수(또는 준비 중). 제목이 칸보다 길면 줄임표로 줄이고 전체는
    도움말에 둠. 누르면 picked(주제 id)를 내고 고른 주제는 테두리가 짙어짐."""
    picked = pyqtSignal(str)

    def __init__(self, row):
        super().__init__()
        self.setObjectName("card")
        self.tid, self.ready = row["id"], row["ready"]
        self.full = "%d %s" % (row["no"], row["title"])
        box = QHBoxLayout(self)
        box.setContentsMargins(14, 8, 14, 8)
        box.setSpacing(8)
        self.title = QLabel(self.full)
        self.title.setObjectName("" if row["ready"] else "muted")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # 칸 폭에 맞춰 줄임
        self.count = QLabel()
        self.count.setObjectName("caption")
        if not row["ready"]:
            self.count.setText("읽을 수 없음" if row["error"] else "준비 중")
        else:
            self.count.setText("%d/%d" % (row["done"], row["total"]))
        box.addWidget(self.title, 1)
        box.addWidget(self.count)
        tip = self.full if not row["ready"] else "%s · 사슬 %d개 가운데 %d개 풂" % (self.full, row["total"], row["done"])
        self.setToolTip(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor if row["ready"] else Qt.CursorShape.ArrowCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_selected(self, selected):
        self.setProperty("me", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        metrics = self.title.fontMetrics()
        self.title.setText(metrics.elidedText(self.full, Qt.TextElideMode.ElideRight, max(1, self.title.width())))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.ready:
            self.picked.emit(self.tid)
        event.accept()


class WebHomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        self.win = win
        self.overview = None
        self.topic, self.chips = None, {}
        self.setup_dialog = None
        inner = QWidget()
        inner.setObjectName("page")
        scroll = QScrollArea()  # 창이 작으면 내용을 찌그러뜨리지 않고 스크롤함
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        root = QVBoxLayout(inner)
        root.setContentsMargins(28, 18, 28, 12)
        root.setSpacing(16)

        head = QHBoxLayout()
        self.hub_btn = QPushButton("처음으로")
        title = QLabel("웹 면접 준비")
        title.setObjectName("h1")
        self.stack_label = QLabel()
        self.stack_label.setObjectName("muted")
        self.setup_btn = QPushButton("설치 관리")
        self.setup_btn.setToolTip("라이브 코딩 미션의 검사 도구를 설치하거나 지웁니다. 꼬리 질문과 학습 노트에는 필요 없습니다.")
        head.addWidget(self.hub_btn)
        head.addSpacing(8)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.stack_label)
        head.addSpacing(10)
        head.addWidget(self.setup_btn)
        root.addLayout(head)
        self.notice = Para(name="notice")
        self.notice.hide()
        root.addWidget(self.notice)
        self.problem = Para(name="warn")  # 검사 도구나 Node 가 없을 때의 안내 한 줄
        self.problem.hide()
        root.addWidget(self.problem)

        top = QHBoxLayout()
        top.setSpacing(16)
        today_card, box, head = card("오늘 복습")
        self.today_minutes = QLabel()
        self.today_minutes.setObjectName("caption")
        head.addWidget(self.today_minutes)
        self.today_list = make_list()
        self.today_empty = Para(NO_TODAY, "muted")
        row = QHBoxLayout()
        row.addStretch(1)
        self.review_btn = QPushButton("복습 시작")
        self.review_btn.setObjectName("primary")
        row.addWidget(self.review_btn)
        box.addWidget(self.today_list)
        box.addWidget(self.today_empty)
        box.addStretch(1)  # 옆 카드보다 짧으면 단추 줄을 카드 바닥에 붙임
        box.addLayout(row)
        mission_card, box, head = card("라이브 코딩 미션")
        self.mission_count = QLabel()
        self.mission_count.setObjectName("caption")
        head.addWidget(self.mission_count)
        self.mission_list = make_list()
        row = QHBoxLayout()
        self.mission_note = QLabel()
        self.mission_note.setObjectName("muted")
        self.mission_note.setMinimumWidth(1)
        self.mission_btn = QPushButton("받기")
        self.mission_btn.setObjectName("primary")
        row.addWidget(self.mission_note, 1)
        row.addWidget(self.mission_btn)
        box.addWidget(self.mission_list)
        box.addStretch(1)
        box.addLayout(row)
        top.addWidget(today_card, 1)
        top.addWidget(mission_card, 1)
        root.addLayout(top)

        topic_card, box, head = card("꼬리 질문 주제")
        self.topic_count = QLabel()
        self.topic_count.setObjectName("caption")
        head.addWidget(self.topic_count)
        self.chip_grid = QGridLayout()
        self.chip_grid.setHorizontalSpacing(10)
        self.chip_grid.setVerticalSpacing(10)
        box.addLayout(self.chip_grid)
        self.chain_title = Para(name="muted")
        self.chain_list = make_list()
        row = QHBoxLayout()
        row.addStretch(1)
        self.drill_btn = QPushButton("골라 풀기")
        self.drill_btn.setObjectName("primary")
        row.addWidget(self.drill_btn)
        box.addWidget(self.chain_title)
        box.addWidget(self.chain_list)
        box.addLayout(row)
        root.addWidget(topic_card)

        page_card, box, head = card("학습 노트")
        self.page_list = make_list()
        row = QHBoxLayout()
        row.addStretch(1)
        self.read_btn = QPushButton("읽기")
        row.addWidget(self.read_btn)
        box.addWidget(self.page_list)
        box.addLayout(row)
        root.addWidget(page_card)

        self.talked = Para(name="muted")
        root.addWidget(self.talked)
        bar = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setMinimumWidth(1)
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedWidth(140)
        self.busy_bar.hide()
        bar.addWidget(self.status, 1)
        bar.addWidget(self.busy_bar)
        root.addLayout(bar)

        self.hub_btn.clicked.connect(lambda: self.win.go_hub())
        self.setup_btn.clicked.connect(self.open_setup)
        self.today_list.itemDoubleClicked.connect(lambda item: self.start_review())
        self.review_btn.clicked.connect(self.start_review)
        self.mission_list.currentItemChanged.connect(lambda *_: self._sync_mission())
        self.mission_list.itemDoubleClicked.connect(lambda item: self.open_mission())
        self.mission_btn.clicked.connect(self.open_mission)
        self.chain_list.itemDoubleClicked.connect(lambda item: self.open_chain())
        self.drill_btn.clicked.connect(self.open_chain)
        self.page_list.itemDoubleClicked.connect(lambda item: self.open_page())
        self.read_btn.clicked.connect(self.open_page)

    # 불러오기

    def refresh(self):
        """서비스에서 현황을 다시 읽어 모든 칸을 다시 채움. 기록을 읽지 못하면 알림 줄에 이유를 보이고 목록을 비움."""
        try:
            overview = self.overview = self.win.web.overview()
        except (WebError, RecordError) as error:
            self.overview = None
            self.notice.setText(str(error))
            self.notice.show()
            self.clear()
            return
        stack = overview["stack"]
        self.stack_label.setText(stack_line(stack))
        self.problem.setText(stack["problem"])
        self.problem.setVisible(bool(stack["problem"]))
        errors = overview["bank_errors"]
        self.notice.setText("은행에서 읽지 못한 항목이 있습니다. %s" % " / ".join(errors) if errors else "")
        self.notice.setVisible(bool(errors))
        self.show_today(overview["today"])
        self.show_missions(overview["missions"])
        self.show_topics(overview["topics"])
        self.show_pages(overview["pages"])
        if overview["stuck"]:
            self.talked.setText("막힌 질문에서 아는 데까지 말한 비율 %d / %d" % (overview["talked"], overview["stuck"]))
        else:
            self.talked.setText(NO_STUCK)
        self.status.setText("")

    def clear(self):
        """현황을 읽지 못했을 때. 지난 현황이 알림과 섞여 보이지 않게 모든 칸을 비우고 단추를 끔."""
        self.problem.hide()
        for label in (self.stack_label, self.today_minutes, self.mission_count, self.mission_note, self.topic_count, self.chain_title,
                      self.talked):
            label.setText("")
        for listw in (self.today_list, self.mission_list, self.chain_list, self.page_list):
            listw.clear()
            fit_list(listw)
            listw.show()
        self.today_empty.hide()
        self.clear_chips()
        self.topic = None
        for button in (self.review_btn, self.mission_btn, self.drill_btn, self.read_btn):
            button.setEnabled(False)

    def show_today(self, today):
        self.today_minutes.setText("약 %d분" % today["minutes"] if today["chains"] else "")
        self.today_list.clear()
        for row in today["chains"]:
            plan = "새 사슬" if row["new"] else "상자 %d" % row["box"]
            add_row(self.today_list, "사슬 %s %s\n%s" % (row["chain"], row["title"], plan), ("chain", row["chain"]),
                    "primary" if row["new"] else "retry", filled=not row["new"])
        for row in today["missions"]:
            add_row(self.today_list, "다시 해 볼 미션 %s %s\n%s" % (row["mission"], row["title"], row["why"]), ("mission", row["mission"]),
                    "retry", filled=True)
        fit_list(self.today_list)
        empty = self.today_list.count() == 0
        self.today_list.setVisible(not empty)
        self.today_empty.setVisible(empty)
        self.review_btn.setEnabled(not empty)
        if not empty:
            self.today_list.setCurrentRow(0)

    def show_missions(self, missions):
        self.mission_list.clear()
        for row in missions:
            color, filled = {"done": ("ok", True), "live": ("primary", True), "reading": ("primary", False)}.get(row["phase"], ("muted", False))
            if not row["ready"]:
                color = "faint"
            text = "%s %s · %s\n%s" % (row["id"], row["title"], row["level"], mission_state(row))
            add_row(self.mission_list, text, row["id"], color, filled, enabled=row["ready"])
        fit_list(self.mission_list)
        ready = [m for m in missions if m["ready"]]
        self.mission_count.setText("출제 %d개 가운데 끝남 %d개" % (len(ready), sum(1 for m in ready if m["phase"] == "done")))
        pick = next((n for n, m in enumerate(missions) if m["ready"] and m["phase"] in ("reading", "live")), None)
        if pick is None:
            pick = next((n for n, m in enumerate(missions) if m["ready"] and m["phase"] != "done"), None)
        if pick is None:
            pick = next((n for n, m in enumerate(missions) if m["ready"]), None)
        if pick is not None:
            self.mission_list.setCurrentRow(pick)
        self._sync_mission()

    def _sync_mission(self):
        mid = current_data(self.mission_list)
        row = next((m for m in (self.overview or {}).get("missions", []) if m["id"] == mid), None)
        self.mission_btn.setEnabled(row is not None)
        if row is None:
            self.mission_btn.setText("받기")
            self.mission_note.setText("")
            return
        self.mission_btn.setText({"none": "받기", "done": "해설 보기"}.get(row["phase"], "이어 하기"))
        self.mission_note.setText("읽기 %d분 · 실전 %d분 · %d단계" % (self.win.web.missions[mid]["prep_min"], row["live_min"],
                                                             max(0, row["total_steps"] - 1)))

    def clear_chips(self):
        for chip in self.chips.values():
            self.chip_grid.removeWidget(chip)
            chip.hide()
            chip.deleteLater()
        self.chips = {}

    def show_topics(self, topics):
        self.clear_chips()
        for number, row in enumerate(topics):
            chip = TopicChip(row)
            chip.picked.connect(self.pick_topic)
            self.chip_grid.addWidget(chip, number // CHIP_COLUMNS, number % CHIP_COLUMNS)
            self.chips[row["id"]] = chip
        for column in range(CHIP_COLUMNS):
            self.chip_grid.setColumnStretch(column, 1)
        ready = [t for t in topics if t["ready"]]
        self.topic_count.setText("출제 %d개 · 사슬 %d개 가운데 %d개 풂" % (len(ready), sum(t["total"] for t in ready), sum(t["done"] for t in ready)))
        if self.topic not in self.chips or not self.chips[self.topic].ready:
            self.topic = next((t["id"] for t in ready), None)
        self.pick_topic(self.topic)

    def pick_topic(self, tid):
        """주제 tid 의 사슬 목록을 보임."""
        self.topic = tid
        for key, chip in self.chips.items():
            chip.set_selected(key == tid)
        self.chain_list.clear()
        row = next((t for t in (self.overview or {}).get("topics", []) if t["id"] == tid), None)
        if row is None:
            self.chain_title.setText("아직 출제된 주제가 없습니다.")
        else:
            self.chain_title.setText("주제 %d 「%s」의 사슬" % (row["no"], row["title"]))
            for chain in row["chains"]:
                new = chain["box"] is None
                add_row(self.chain_list, "%s %s\n%s" % (chain["id"], chain["title"], chain_plan(chain)), chain["id"],
                        "primary" if new else "retry", filled=not new)
            if self.chain_list.count():
                self.chain_list.setCurrentRow(0)
        fit_list(self.chain_list)
        self.chain_list.setVisible(self.chain_list.count() > 0)
        self.drill_btn.setEnabled(self.chain_list.count() > 0)

    def show_pages(self, pages):
        self.page_list.clear()
        for row in pages:
            if row["learned_at"]:
                mark = "읽음 %s" % day_text(row["learned_at"])
            else:
                mark = "아직 읽지 않음" if row["ready"] else ("읽을 수 없음" if row["error"] else "준비 중")
            add_row(self.page_list, "%s %s\n%s" % (row["id"], row["title"], mark), row["id"], "ok" if row["learned_at"] else "muted",
                    filled=bool(row["learned_at"]), enabled=row["ready"])
        fit_list(self.page_list)
        pick = next((n for n, p in enumerate(pages) if p["ready"] and not p["learned_at"]), None)
        if pick is None:
            pick = next((n for n, p in enumerate(pages) if p["ready"]), None)
        if pick is not None:
            self.page_list.setCurrentRow(pick)
        self.read_btn.setEnabled(pick is not None)

    # 이동

    def start_review(self):
        data = current_data(self.today_list)
        if data is None:
            return
        kind, iid = data
        if kind == "mission":
            self.win.open_mission(iid)
        else:
            self.win.open_drill(iid)

    def open_mission(self):
        mid = current_data(self.mission_list)
        if mid:
            self.win.open_mission(mid)

    def open_chain(self):
        cid = current_data(self.chain_list)
        if cid:
            self.win.open_drill(cid)

    def open_page(self):
        pid = current_data(self.page_list)
        if pid:
            self.win.open_learn(pid)

    def open_setup(self):
        self.setup_dialog = SetupDialog(self.win, on_change=self.refresh)
        self.setup_dialog.show()

    # 상태

    def set_busy(self, busy, text=""):
        for widget in (self.hub_btn, self.setup_btn, self.review_btn, self.mission_btn, self.drill_btn, self.read_btn):
            widget.setEnabled(not busy)
        if not busy and self.overview is not None:
            self.review_btn.setEnabled(self.today_list.count() > 0)
            self._sync_mission()
            self.drill_btn.setEnabled(self.chain_list.count() > 0)
            self.read_btn.setEnabled(current_data(self.page_list) is not None)
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")

    def restyle(self):
        """테마가 바뀌면 목록의 동그라미 색을 다시 칠함."""
        if self.overview is not None:
            self.refresh()
