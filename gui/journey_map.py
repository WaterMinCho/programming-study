# -*- coding: utf-8 -*-
"""알고리즘 여행의 던전 지도: 왼쪽 지도(던전 16개를 4개씩 4줄 뱀 모양 길로) · 오른쪽 고른 던전의 소개와 문제 목록.

던전은 모두 열려 있고 지도는 권장 순서만 보여 줌. 보스 줄은 그 던전의 중급 문제를 모두 통과하기 전에는 꺼 둠.
"보스에서 익힌 기술" 줄은 보스를 통과했거나 보스 해설을 연 뒤에만 서비스가 내용을 줌."""
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QPen
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter, QToolTip, QVBoxLayout,
                             QWidget)

from gui import theme
from gui.docview import DocView
from gui.journey_page import LANG_LABEL, LangButtons, ask_node, md_text, node_ready, saved_lang
from gui.round_page import DOT_PX, RowDelegate, dot
from gui.widgets import Para

COLUMNS = 4  # 한 줄의 던전 수
RADIUS = 19  # 던전 원의 반지름
LEGEND = (("ok", "●", "클리어"), ("primary", "◐", "진행 중"), ("border_strong", "○", "시작 전"), ("faint", "◌", "준비 중"))
CLEAR_TEXT = "만들어 둔 효율성 테스트 입력을 지웁니다. 다음 채점 때 다시 만듭니다. 지울까요?"


def size_text(size):
    """캐시 크기. 1MB 보다 작으면 "1MB 미만"."""
    if not size:
        return "0MB"
    if size < 1024 * 1024:
        return "1MB 미만"
    return "%dMB" % round(size / (1024 * 1024))


def legend_html():
    """지도 아래 범례. 기호를 지도의 원과 같은 색으로 칠함."""
    return "&nbsp;&nbsp;&nbsp;".join('<span style="color: %s;">%s</span> %s' % (theme.color(token), mark, label)
                                     for token, mark, label in LEGEND)


def row_text(row, info):
    """문제 목록의 두 줄. 첫 줄은 번호·역할·제목, 둘째 줄은 난이도와 상태."""
    first = "%s %s · %s" % (row["no"], row["role_label"], row["title"])
    if row["locked"]:
        return first + "\n잠김 · 중급 %d개 중 %d개 통과" % (info["mid_total"], info["mid_passed"])
    parts = [row["tier"]]
    if row["passed"]:
        langs = "·".join(LANG_LABEL[lang] for lang in row["passed_langs"])
        parts.append("%s (%s)" % ("해설 보고 통과" if row["explained_first"] else "통과", langs))
    elif row["tried"]:
        parts.append("최고 %.1f점" % max(list(row["best"].values()) or [0.0]))
    if row["prep"]:
        parts.append("준비 문제 " + ", ".join(ref["no"] for ref in row["prep"]))
    return first + "\n" + " · ".join(parts)


class MapView(QWidget):
    """QPainter 로 그린 지도. 원 안에 던전 번호, 색은 클리어 ok · 진행 중 primary · 시작 전 border_strong · 준비 중 faint 점선.
    고른 던전은 primary 두 겹 테두리. 누르면 picked(던전 id) 를 냄."""
    picked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows, self.selected = [], None
        self.setMinimumSize(300, 320)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_rows(self, rows, selected):
        self.rows, self.selected = rows, selected
        self.update()

    def set_selected(self, did):
        self.selected = did
        self.update()

    def centers(self):
        """던전 순서대로 원의 가운데. 4개씩 한 줄이고 줄마다 방향을 바꿈."""
        lines = max(1, math.ceil(len(self.rows) / COLUMNS))
        left, top, bottom = RADIUS + 22, RADIUS + 16, RADIUS + 34  # 아래는 "최종" 글자 자리
        step_x = (self.width() - 2 * left) / (COLUMNS - 1)
        step_y = (self.height() - top - bottom) / max(1, lines - 1)
        points = []
        for index in range(len(self.rows)):
            line, column = divmod(index, COLUMNS)
            if line % 2:
                column = COLUMNS - 1 - column
            points.append(QPointF(left + column * step_x, top + line * step_y))
        return points

    def nodes(self):
        """[(던전 id, 원의 사각형)]. 누를 수 있는 자리임."""
        return [(row["id"], QRectF(center.x() - RADIUS, center.y() - RADIUS, 2 * RADIUS, 2 * RADIUS))
                for row, center in zip(self.rows, self.centers())]

    def at(self, point):
        """point 가 든 원의 던전 id. 원 둘레 조금 밖까지 받음."""
        for row, center in zip(self.rows, self.centers()):
            if math.hypot(point.x() - center.x(), point.y() - center.y()) <= RADIUS + 4:
                return row["id"]
        return None

    @staticmethod
    def state(row):
        if not row["ready"]:
            return "faint"
        if row["cleared"]:
            return "ok"
        return "primary" if row["passed"] else "border_strong"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        points = self.centers()
        painter.setPen(QPen(theme.qcolor("track"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for start, end in zip(points, points[1:]):
            painter.drawLine(start, end)
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(14)
        painter.setFont(font)
        for row, center in zip(self.rows, points):
            state = self.state(row)
            circle = QRectF(center.x() - RADIUS, center.y() - RADIUS, 2 * RADIUS, 2 * RADIUS)
            if row["id"] == self.selected:
                painter.setPen(QPen(theme.qcolor("primary"), 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for gap in (4, 7):
                    painter.drawEllipse(circle.adjusted(-gap, -gap, gap, gap))
            style = Qt.PenStyle.DotLine if state == "faint" else Qt.PenStyle.SolidLine
            painter.setPen(QPen(theme.qcolor(state), 2.5 if state == "primary" else 2, style))
            painter.setBrush(theme.qcolor("ok" if state == "ok" else "surface"))
            painter.drawEllipse(circle)
            painter.setPen(theme.qcolor({"ok": "surface", "faint": "muted"}.get(state, "ink")))
            painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(row["no"]))
            if row.get("final"):
                painter.setPen(theme.qcolor("muted"))
                painter.drawText(QRectF(center.x() - 40, center.y() + RADIUS + 6, 80, 20), Qt.AlignmentFlag.AlignCenter, "최종")
        painter.end()

    def mousePressEvent(self, event):
        did = self.at(event.position())
        if did and event.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(did)

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            did = self.at(QPointF(event.pos()))
            row = next((row for row in self.rows if row["id"] == did), None)
            if row:
                QToolTip.showText(event.globalPos(), "던전 %d · %s 「%s」" % (row["no"], row["topic"], row["title"]), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)


class MapRowDelegate(RowDelegate):
    """문제 목록의 줄. 꺼 둔 줄(잠긴 보스)은 옅게 그림."""

    def paint(self, painter, option, index):
        painter.save()
        if not index.flags() & Qt.ItemFlag.ItemIsEnabled:
            painter.setOpacity(0.55)
        super().paint(painter, option, index)
        painter.restore()


class JourneyMapPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        self.win = win
        self.did, self.info, self.overview = None, None, None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)
        head = QHBoxLayout()
        self.home_btn = QPushButton("처음으로")
        title = QLabel("알고리즘 여행")
        title.setObjectName("h1")
        self.lang_bar = LangButtons()
        self.lang_btns = self.lang_bar.buttons
        self.passed = QLabel()
        self.passed.setObjectName("muted")
        head.addWidget(self.home_btn)
        head.addSpacing(8)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.lang_bar)
        head.addSpacing(16)
        head.addWidget(self.passed)
        root.addLayout(head)
        self.notice = Para(name="notice")
        self.notice.hide()
        root.addWidget(self.notice)

        split = QSplitter(Qt.Orientation.Horizontal)
        left = QFrame()
        left.setObjectName("card")
        left_box = QVBoxLayout(left)
        left_box.setContentsMargins(12, 10, 12, 10)
        self.view = MapView()
        self.legend = QLabel(legend_html())
        self.legend.setObjectName("muted")
        cache_row = QHBoxLayout()
        self.cache = QLabel()
        self.cache.setObjectName("muted")
        self.clear_cache_btn = QPushButton("캐시 비우기")
        self.clear_cache_btn.setObjectName("quiet")
        self.clear_cache_btn.setToolTip("효율성 테스트의 큰 입력은 처음 채점할 때 만들어 이 컴퓨터에 보관해 둡니다.")
        cache_row.addWidget(self.cache)
        cache_row.addWidget(self.clear_cache_btn)
        cache_row.addStretch(1)
        left_box.addWidget(self.view, 1)
        left_box.addWidget(self.legend)
        left_box.addLayout(cache_row)

        right = QFrame()
        right.setObjectName("card")
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(16, 12, 16, 12)
        right_box.setSpacing(6)
        self.title = Para(name="h2")
        self.meta = Para(name="muted")
        self.intro = DocView()
        self.skills = Para()
        self.boss_new = Para()
        self.listw = QListWidget()
        self.listw.setIconSize(QSize(DOT_PX, DOT_PX))
        self.listw.setItemDelegate(MapRowDelegate(self.listw))
        self.listw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bottom = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setMinimumWidth(1)
        self.solve_btn = QPushButton("문제 풀기")
        self.solve_btn.setObjectName("primary")
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.solve_btn)
        for widget in (self.title, self.meta):
            right_box.addWidget(widget)
        right_box.addWidget(self.intro, 2)
        for widget in (self.skills, self.boss_new):
            right_box.addWidget(widget)
        right_box.addWidget(self.listw, 3)
        right_box.addLayout(bottom)

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 5)
        split.setSizes([500, 640])
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        self.home_btn.clicked.connect(lambda: self.win.go_hub())
        self.view.picked.connect(self.show_dungeon)
        self.lang_bar.picked.connect(self.pick_lang)
        self.clear_cache_btn.clicked.connect(self.ask_clear_cache)
        self.listw.currentItemChanged.connect(lambda *_: self._sync_solve())
        self.listw.itemDoubleClicked.connect(lambda item: self.open_problem())
        self.solve_btn.clicked.connect(self.open_problem)

    # 불러오기

    def refresh(self, select=None):
        """서비스에서 수치를 다시 읽어 그림. select 가 있으면 그 던전을 고름. 없으면 보던 던전, 마지막으로 연 문제의 던전, 다음 추천 순."""
        overview = self.overview = self.win.journey.overview()
        rows = overview["dungeons"]
        ids = [row["id"] for row in rows]
        last = self.win.settings.value("journey/last", "", type=str).partition("/")[0]
        recommended = (overview["next"] or {}).get("did")
        did = next((d for d in (select, self.did, last, recommended) if d in ids), None)
        if did is None:
            did = next((row["id"] for row in rows if row["ready"]), ids[0] if ids else None)
        self.passed.setText("통과 %d/%d" % (overview["passed"], overview["total"]))
        errors = overview["bank_errors"]
        self.notice.setText("문제 은행에서 읽지 못한 던전이 있습니다. %s" % " / ".join(errors) if errors else "")
        self.notice.setVisible(bool(errors))
        self.lang_bar.set_lang(self.usable_lang())
        self.show_cache(self.win.journey.cache_info())
        self.view.set_rows(rows, did)
        if did is not None:
            self.show_dungeon(did)

    def usable_lang(self):
        """설정의 언어. JavaScript 를 고른 적이 있을 때만 node 를 찾아 보고, 없으면 Python 과 "Node.js 필요" 를 보임."""
        lang = saved_lang(self.win.settings)
        if lang == "javascript" and not node_ready(self.win):
            self.lang_bar.note.show()
            return "python"
        return lang

    def show_cache(self, info):
        self.cache.setText("생성 입력 캐시 %s" % size_text(info["bytes"]))

    def show_dungeon(self, did):
        """오른쪽에 던전 did 의 소개와 문제 목록을 보여 줌."""
        self.did = did
        self.view.set_selected(did)
        info = self.info = self.win.journey.dungeon(did)
        numbers = {row["id"]: row["no"] for row in (self.overview or {"dungeons": []})["dungeons"]}
        self.title.setText("던전 %d · %s 「%s」" % (info["no"], info["topic"], info["title"]))
        prereq = ", ".join(str(numbers.get(d, d)) for d in info["prereq"])
        self.meta.setText("보스 목표 %s · %s" % (info["boss_target"], "권장 선행 던전 %s" % prereq if prereq else "권장 선행 없음"))
        ready = info["ready"]
        for widget in (self.skills, self.listw, self.solve_btn):
            widget.setVisible(ready)
        self.boss_new.setVisible(ready and bool(info["boss_new"]))
        self.listw.clear()
        if not ready:
            text = "이 던전을 읽을 수 없습니다. %s" % info["error"] if info["error"] else "아직 출제되지 않은 던전입니다."
            self.intro.set_markdown(md_text(text), "", self.lang_bar.lang)
            return
        self.intro.set_markdown(info["intro"], info["base_dir"], self.lang_bar.lang)
        self.skills.setText("익히는 기술: %s" % ", ".join(info["skills"]))
        self.boss_new.setText("보스에서 익힌 기술: %s" % info["boss_new"] if info["boss_new"] else "")
        self.fill_list()

    def fill_list(self):
        """문제 목록을 채우고, 마지막으로 연 문제나 이 던전의 다음 추천 문제를 고름."""
        info = self.info
        bold = QFont(self.listw.font())
        bold.setBold(True)
        for row in info["problems"]:
            item = QListWidgetItem(row_text(row, info))
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setIcon(self.icon(row))
            if row["role"] == "boss":
                item.setFont(bold)
            if row["locked"]:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("중급 문제를 모두 통과하면 열립니다(%d개 중 %d개 통과)." % (info["mid_total"], info["mid_passed"]))
            self.listw.addItem(item)
        last_did, _, last_pid = self.win.settings.value("journey/last", "", type=str).partition("/")
        recommended = (self.overview or {}).get("next") or {}
        wanted = [last_pid if last_did == self.did else None, recommended.get("pid") if recommended.get("did") == self.did else None]
        rows = [self.listw.item(n) for n in range(self.listw.count())]
        enabled = [item for item in rows if item.flags() & Qt.ItemFlag.ItemIsEnabled]
        pick = next((item for pid in wanted for item in enabled if pid and item.data(Qt.ItemDataRole.UserRole) == pid), None)
        self.listw.setCurrentItem(pick or (enabled[0] if enabled else None))
        self._sync_solve()

    @staticmethod
    def icon(row):
        if row["locked"]:
            return dot(theme.color("faint"), False)
        if row["passed"]:
            return dot(theme.color("ok"), True)
        return dot(theme.color("primary" if row["tried"] else "border_strong"), False)

    def _sync_solve(self):
        item = self.listw.currentItem()
        self.solve_btn.setEnabled(bool(item and item.flags() & Qt.ItemFlag.ItemIsEnabled))

    def open_problem(self):
        item = self.listw.currentItem()
        if item is not None and item.flags() & Qt.ItemFlag.ItemIsEnabled:
            self.win.open_problem(self.did, item.data(Qt.ItemDataRole.UserRole))

    # 언어 · 캐시

    def pick_lang(self, lang):
        """문제 화면과 같은 설정을 바꿈. JavaScript 인데 node 가 없으면 Python 에 머물고 대화상자를 띄움."""
        if lang == "javascript" and not node_ready(self.win):
            self.lang_bar.note.show()
            ask_node(self.win, lambda: self.pick_lang("javascript"))
            return
        self.win.settings.setValue("journey/lang", lang)
        if lang == "javascript":
            self.lang_bar.note.hide()
        self.lang_bar.set_lang(lang)
        if self.info and self.info["ready"]:
            self.intro.set_markdown(self.info["intro"], self.info["base_dir"], lang)

    def ask_clear_cache(self):
        self.win.ask("캐시 비우기", CLEAR_TEXT, (("지우기", "clear"), ("취소", "")), lambda key: self.clear_cache())

    def clear_cache(self):
        self.show_cache(self.win.journey.clear_cache())
        self.status.setText("생성 입력 캐시를 비웠습니다.")

    # 화면 상태

    def set_busy(self, busy, text=""):
        for widget in (self.home_btn, self.lang_bar, self.view, self.listw, self.solve_btn, self.clear_cache_btn):
            widget.setEnabled(not busy)
        self.status.setText(text if busy else "")
        if not busy:
            self._sync_solve()

    def restyle(self):
        """글자 크기나 테마가 바뀌면 부름. 소개 글의 CSS 와 목록의 동그라미 색을 다시 넣음. 지도는 칠할 때마다 테마 색을 읽음."""
        self.intro.restyle(theme.doc_css(self.win.zoom), theme.code_font(self.win.zoom))
        self.legend.setText(legend_html())
        if self.info and self.info["ready"]:
            for number, row in enumerate(self.info["problems"]):
                self.listw.item(number).setIcon(self.icon(row))
        self.view.update()
