# -*- coding: utf-8 -*-
"""여행 화면: 던전 지도(gui/journey_map.py), 문제 화면(gui/journey_page.py), 테스트 케이스 대화상자(gui/cases_dialog.py),
문제 화면의 복사·붙여넣기 예외(gui/guard.py). 가짜 창(run_job 이 fn 을 바로 부르고 report 를 on_progress 로 넘김)과
고정 은행 tests/journey_bank 로 봄. PyQt6 가 없으면 전부 건너뜀.

코드 실행·채점은 실제 Python 하네스를 띄우므로 STUDY_LEAN_CI 가 있으면 그 테스트만 건너뜀. JavaScript 를 고르는 테스트는
runtime 을 가짜로 바꿔 끼워 node 없이 돎. 시간 값(ms)은 단언하지 않음."""
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QSettings, Qt, QUrl  # noqa: E402
from PyQt6.QtGui import QGuiApplication, qGray  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget  # noqa: E402

import adaptive  # noqa: E402
import study  # noqa: E402
from gui import journey_html, kit, theme  # noqa: E402
from gui.dialogs import MessageDialog  # noqa: E402
from gui.docview import CodeView, TextPiece  # noqa: E402
from gui.editor import JAVASCRIPT, PYTHON  # noqa: E402
from gui.guard import Guard  # noqa: E402
from gui.journey_map import ALL_CLEAR, BROKEN, CACHE_TIP, CLEAR_TEXT, WAITING, JourneyMapPage, MapView  # noqa: E402
from gui.journey_page import GIVE_UP_TEXT, NODE_BUSY, NODE_TITLE, JourneyPage  # noqa: E402
from gui.round_page import RoundPage  # noqa: E402
from journey import bank, node, runner, values  # noqa: E402
from journey.service import JourneySession  # noqa: E402
from session import SessionError  # noqa: E402

FIXTURE = os.path.join(guikit.ROOT, "tests", "journey_bank")
LEAN = bool(os.environ.get("STUDY_LEAN_CI"))
SKIP_LEAN = unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 ci.yml 의 화면 테스트 작업에서 돎")
NODE = None if LEAN else node.find()
NO_NODE = {"ok": False, "label": "", "problem": "Node.js 를 찾지 못했습니다."}
HAS_NODE = {"ok": True, "label": "Node.js 22.0.0", "problem": ""}
MAX_SOLUTION = "def solution(nums):\n    print('찍음')\n    return max(nums)\n"
FIRST_SOLUTION = "def solution(nums):\n    return nums[0]\n"
BOSS_SOLUTION = "def solution(nums, k):\n    return sum(sorted(nums, reverse=True)[:k])\n"


def bright_share(widget):
    """tests/test_gui.py 의 bright_share 와 같은 셈. 찍은 그림을 8분의 1로 줄여 밝은 칸이 가로로 6칸 넘게 이어진 곳의 비율."""
    image = widget.grab().toImage()
    step = int(8 * image.devicePixelRatio())
    small = image.scaled(image.width() // step, image.height() // step, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    found = 0
    for y in range(small.height()):
        row = "".join("1" if qGray(small.pixel(x, y)) > 215 else "0" for x in range(small.width()))
        found += sum(len(run) for run in re.findall("1{6,}", row))
    return found / (small.width() * small.height())


def doc_text(view):
    """DocView 의 글 조각을 이어 붙인 글."""
    return "\n".join(piece.toPlainText() for piece in view.pieces if isinstance(piece, TextPiece))


class FakeJob:
    def __init__(self):
        self.cancel = threading.Event()


class FakeWindow(QMainWindow):
    """MainWindow 가 여행 화면에 주는 것만 흉내 냄. run_job 은 fn 을 바로 부르고 report 를 on_progress 로 넘김.
    회차 화면(RoundPage)을 같은 창에 두어 붙여넣기 예외가 문제 화면에만 걸리는지 봄."""

    def __init__(self, folder):
        super().__init__()
        self.settings = QSettings(os.path.join(folder, "settings.ini"), QSettings.Format.IniFormat)
        self.dialog, self.job = None, None
        self.journey = JourneySession("alice")
        self.opened, self.picks, self.pick_result, self.went, self.blocked = [], [], "", [], 0
        self.open_url = self.opened.append
        self.pages = QStackedWidget()
        self.journey_map, self.journey_page, self.round_page = JourneyMapPage(self), JourneyPage(self), RoundPage(self)
        for page in (self.journey_map, self.journey_page, self.round_page):
            self.pages.addWidget(page)
        self.setCentralWidget(self.pages)
        self.journey_map.restyle()
        self.journey_page.restyle()
        self.guard = Guard(self)
        guikit.APP.installEventFilter(self.guard)
        self.guard.blocked.connect(self._blocked)
        self.resize(1280, 800)

    @property
    def zoom(self):
        """MainWindow.zoom 과 같음. 옛 화면의 문서와 코드 글꼴이 받는 글자 단계의 px."""
        return theme.text_px()

    def set_text(self, step):
        """MainWindow.set_text 와 같은 순서: 단계를 고르고, 모든 부품의 글꼴을 다시 준 뒤 화면마다 restyle."""
        theme.set_text(step)
        kit.refont(self)
        self.journey_map.restyle()
        self.journey_page.restyle()

    def _blocked(self):
        self.blocked += 1

    def pick_file(self, title):
        self.picks.append(title)
        return self.pick_result

    def run_job(self, text, fn, on_done, on_fail=None, on_progress=None):
        page = self.pages.currentWidget()
        page.set_busy(True, text)
        self.job = (FakeJob(), page, on_done, on_fail)
        try:
            result = fn(on_progress, self.job[0].cancel) if on_progress else fn()
        except SessionError as error:
            self.job = None
            page.set_busy(False)
            self.ask("알림", str(error))
            if on_fail:
                on_fail()
            return
        self.job = None
        page.set_busy(False)
        on_done(result)

    def ask(self, title, text, buttons=(("확인", "ok"),), on_choice=None, detail="", link=""):
        self.dialog = MessageDialog(self, title, text, buttons, lambda key: key and on_choice and on_choice(key), detail, link)
        self.dialog.show()
        return self.dialog

    def go_home(self):
        self.went.append("home")

    def go_hub(self):
        self.went.append("hub")

    def go_journey(self, did=None):
        if self.journey_page.flush(offer=False):
            self.journey_map.refresh(did)
            self.pages.setCurrentWidget(self.journey_map)

    def open_problem(self, did, pid):
        try:
            self.journey_page.load(did, pid)
        except SessionError as error:
            self.ask("알림", str(error))
            return
        self.pages.setCurrentWidget(self.journey_page)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gui_journey_")
        self.addCleanup(self.tmp.cleanup)
        for target, name, value in ((study, "SUBMISSIONS_DIR", os.path.join(self.tmp.name, "submissions")),
                                    (runner, "CACHE_DIR", os.path.join(self.tmp.name, "cache")), (bank, "BANK_DIR", FIXTURE)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def boot(self, log=()):
        """진행 기록 log 로 시작해 지도를 띄움."""
        if log:
            self.write_log(log)
        self.win = win = FakeWindow(self.tmp.name)
        self.addCleanup(self.close)
        win.show()
        win.go_journey()
        guikit.pump()
        return win

    def close(self):
        guikit.APP.removeEventFilter(self.win.guard)
        if self.win.dialog is not None:
            self.win.dialog.close()
        if self.win.journey_page.cases_dialog is not None:
            self.win.journey_page.cases_dialog.close()
        self.win.close()
        self.win.deleteLater()
        guikit.pump()

    def write_log(self, entries):
        data = {"format": 1, "user": "alice", "created": adaptive.now(), "log": list(entries)}
        study.write_text(self.progress_path(), json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    def progress_path(self):
        return os.path.join(study.SUBMISSIONS_DIR, "alice", "journey", "progress.json")

    def read_log(self):
        return study.read_json(self.progress_path())["log"] if os.path.isfile(self.progress_path()) else []

    def code_path(self, pid, ext=".py"):
        return os.path.join(study.SUBMISSIONS_DIR, "alice", "journey", "t01", pid + ext)

    def open(self, pid):
        self.win.open_problem("t01", pid)
        guikit.pump()
        self.assertIs(self.win.pages.currentWidget(), self.win.journey_page, self.win.dialog and self.win.dialog.text.text())
        return self.win.journey_page

    def type_code(self, text):
        """편집기의 글을 통째로 바꿈. 사용자가 고친 것처럼 자동 저장이 걸림."""
        editor = self.win.journey_page.code_panel.editor
        cur = editor.textCursor()
        cur.select(cur.SelectionType.Document)
        cur.insertText(text)
        editor.setTextCursor(cur)

    def console(self):
        return self.win.journey_page.code_panel.console.toPlainText()

    def choose(self, key):
        """떠 있는 대화상자에서 key 단추를 누름."""
        self.assertTrue(self.win.dialog.isVisible())
        guikit.click(self.win.dialog.buttons[key])


def passed(pid, lang="python"):
    return {"at": adaptive.now(), "kind": "grade", "item": "t01/" + pid, "lang": lang, "score": 100.0, "acc": 100.0, "eff": 0.0,
            "passed": True, "tests": [1, 1, 0, 0]}


def rows_of(page):
    """지도 목록 줄의 (제목, 둘째 줄, 끝 caption)."""
    return [(row.title.text(), row.second.text(), row.end.text()) for row in page.rows.rows]


def first_px(view):
    """문서 칸 첫 글 조각의 첫 블록 글자 px."""
    piece = next(piece for piece in view.pieces if isinstance(piece, TextPiece))
    return piece.document().begin().begin().fragment().charFormat().font().pixelSize()


def press(widget, key):
    QTest.keyClick(widget, key)
    guikit.pump()


class MapTest(Base):
    def test_sixteen_nodes_and_picking_one_shows_its_detail(self):
        win = self.boot()
        page = win.journey_map
        self.assertEqual("2", page.property("ui"))
        self.assertEqual(16, len(page.view.nodes()))
        self.assertEqual("t01", page.view.selected)
        self.assertEqual(("던전 1 「시험 마을」", "4문제 중 0개 통과"), (page.title.text(), page.count.text()))
        self.assertEqual("합·최댓값 · 보스 난이도 S5 / Lv2", page.meta.text())
        self.assertEqual("보스 문제는 백준 실버 5, 프로그래머스 레벨 2 수준입니다.", page.meta.toolTip())
        self.assertFalse(page.meta_more.isVisible())
        self.assertEqual("4문제 중 0개 통과 · 클리어 0개", page.passed.text())
        self.assertEqual("todo", MapView.state(page.view.rows[0]), "시작 전 원은 흰 바탕에 테두리")
        self.assertTrue(page.bank_banner.isVisible())
        self.assertIn("던전 2", page.bank_banner.text.text())
        self.assertNotIn("t02", page.bank_banner.text.text())
        self.assertIn("t02", page.bank_banner.toolTip(), "서비스 원문은 도움말에만")
        nodes = dict(page.view.nodes())
        QTest.mouseClick(page.view, guikit.LEFT, pos=nodes["t03"].center().toPoint())
        guikit.pump()
        self.assertEqual("t03", page.view.selected)
        self.assertEqual(("던전 3 「준비 중 던전 3」", ""), (page.title.text(), page.count.text()))
        self.assertEqual(["주제 3 · 보스 난이도 G5 / Lv3", "던전 1 다음에 풀면 좋습니다."], [page.meta.text(), page.meta_more.text()])
        self.assertEqual(WAITING, page.note.text())
        self.assertFalse(page.rows.isVisible())
        self.assertFalse(page.about_box.isVisible())
        self.assertEqual("waiting", MapView.state(page.view.rows[2]))
        QTest.mouseClick(page.view, guikit.LEFT, pos=nodes["t02"].center().toPoint())
        guikit.pump()
        self.assertEqual(BROKEN, page.note.text())
        self.assertEqual("waiting", MapView.state(page.view.rows[1]))
        QTest.mouseClick(page.view, guikit.LEFT, pos=nodes["t01"].center().toPoint())
        guikit.pump()
        self.assertTrue(page.rows.isVisible())
        self.assertFalse(page.note_box.isVisible())
        self.assertIn("물통에 담긴 물의 양을 더하고", doc_text(page.intro))
        self.assertEqual("배열 합, 최댓값 찾기, 문자열 뒤집기", page.skills.text())
        self.assertEqual([("물통 합계", "1-1 · B2 / Lv1", "기초"), ("가장 큰 물통", "1-2 · B1 / Lv1 · 준비 문제 1-1", "중급"),
                          ("이름 뒤집기", "1-3 · B3 / Lv1", "선택"), ("물통 정리", "중급 1개를 모두 통과하면 열립니다.", "보스")], rows_of(page))
        self.assertEqual(["todo", "todo", "todo", "lock"], [row.mark.state for row in page.rows.rows])
        boss = page.rows.rows[3]
        self.assertTrue(boss.inert)
        self.assertTrue(boss.title.font().bold())
        self.assertFalse(page.rows.rows[0].title.font().bold())
        self.assertFalse(page.boss_new.isVisible())

    def test_rows_open_on_one_click_or_enter_and_the_locked_boss_stays_shut(self):
        win = self.boot()
        page = win.journey_map
        self.assertFalse(any(row.hasFocus() for row in page.rows.rows), "미리 고른 줄이 없음")
        guikit.click(page.rows.rows[1])
        self.assertIs(win.pages.currentWidget(), win.journey_page)
        self.assertEqual("1-2 · 중급 · 가장 큰 물통", win.journey_page.title.text())
        guikit.click(win.journey_page.map_btn)
        self.assertIs(win.pages.currentWidget(), page)
        self.assertEqual("t01", page.view.selected)
        guikit.click(page.rows.rows[3])
        self.assertIs(win.pages.currentWidget(), page, "잠긴 보스 줄은 눌러도 열리지 않음")
        self.assertIsNone(win.dialog)
        row = page.rows.rows[0]
        row.setFocus()
        press(row, Qt.Key.Key_Return)
        self.assertEqual((win.pages.currentWidget(), win.journey_page.pid), (win.journey_page, "p1"))
        win.open_problem("t01", "boss")
        self.assertIn("중급 문제를 모두 통과하면 열립니다", win.dialog.text.text())

    def test_next_card_holds_the_only_primary_button(self):
        win = self.boot([passed("p1")])
        page = win.journey_map
        self.assertEqual((page.next_card.title.text(), page.next_card.line.text(), page.next_btn.text()),
                         ("가장 큰 물통", "던전 1 「시험 마을」 · 중급", "문제 풀기"))
        self.assertEqual([page.next_btn], kit.visible_primary_buttons(page))
        win.settings.setValue("journey/last", "t01/p3")  # 지난번에 연 문제가 아직 통과 전이면 서비스 추천보다 먼저
        win.go_journey()
        guikit.pump()
        self.assertEqual((page.next_card.title.text(), page.next_card.line.text()), ("이름 뒤집기", "던전 1 「시험 마을」 · 선택"))
        guikit.click(page.next_btn)
        self.assertEqual((win.pages.currentWidget(), win.journey_page.did, win.journey_page.pid), (win.journey_page, "t01", "p3"))

    def test_without_a_next_problem_one_line_replaces_the_card(self):
        win = self.boot([passed("p1"), passed("p2"), passed("boss")])
        page = win.journey_map
        self.assertFalse(page.next_card.isVisible())
        self.assertEqual((page.next_note.isVisible(), page.next_note.text()), (True, ALL_CLEAR))
        self.assertEqual([], kit.visible_primary_buttons(page))
        self.assertEqual("cleared", MapView.state(page.view.rows[0]))
        self.assertEqual("t01", page.view.selected, "다음이 없으면 첫 준비된 던전")
        page.show_dungeon("t03")
        win.go_journey()
        self.assertEqual("t03", page.view.selected, "모두 클리어한 뒤에는 마지막으로 고른 던전에 머묾")

    def test_boss_skill_line_shows_only_after_the_boss_is_passed(self):
        win = self.boot([passed("p2"), passed("p1", "javascript"), {"at": adaptive.now(), "kind": "grade", "item": "t01/p3",
                                                                    "lang": "python", "score": 40.0, "passed": False}])
        page = win.journey_map
        self.assertEqual(["1-1 · B2 / Lv1 · 통과 · JavaScript", "1-2 · B1 / Lv1 · 통과 · Python · 준비 문제 1-1",
                          "1-3 · B3 / Lv1 · 최고 40점", "S5 / Lv2"], [row.second.text() for row in page.rows.rows])
        self.assertEqual(["done", "done", "progress", "todo"], [row.mark.state for row in page.rows.rows])
        self.assertFalse(page.rows.rows[3].inert)
        self.assertFalse(page.boss_new.isVisible())
        self.assertEqual("progress", MapView.state(page.view.rows[0]))
        self.write_log(self.read_log() + [passed("boss")])
        win.journey = JourneySession("alice")  # 기록을 밖에서 고쳤으므로 창이 [문제 받기] 뒤처럼 서비스를 새로 만듦
        page.refresh()
        guikit.pump()
        self.assertTrue(page.boss_new.isVisible())
        self.assertEqual("정렬한 뒤 앞에서 k개를 골라 더함", page.boss_new.text())
        self.assertEqual("cleared", MapView.state(page.view.rows[0]))
        self.assertEqual("4문제 중 3개 통과 · 클리어 1개", page.passed.text())

    def test_cache_button_shows_from_one_megabyte_and_hides_after_clearing(self):
        win = self.boot()
        page = win.journey_map
        self.assertFalse(page.clear_cache_btn.isVisible())
        chips = page.lang_bar.mapTo(page.top, page.lang_bar.rect().topRight())
        self.assertEqual(page.top.width() - 1 - chips.x(), kit.MARGIN, "단추가 숨으면 칩이 막대 끝 여백 32 에 맞음")
        os.makedirs(runner.CACHE_DIR)
        with open(os.path.join(runner.CACHE_DIR, "a" * 64 + ".json"), "wb") as handle:
            handle.write(b"0" * (3 * 1024 * 1024))
        page.refresh()
        guikit.pump()
        self.assertTrue(page.clear_cache_btn.isVisible())
        self.assertEqual(CACHE_TIP, page.clear_cache_btn.toolTip())
        guikit.click(page.clear_cache_btn)
        self.assertEqual(CLEAR_TEXT % "3MB", win.dialog.text.text())
        self.assertIn("3MB", win.dialog.text.text())
        self.choose("clear")
        self.assertFalse(page.clear_cache_btn.isVisible())
        self.assertEqual([], os.listdir(runner.CACHE_DIR))

    def test_keyboard_moves_on_the_map_by_screen_neighbours(self):
        win = self.boot()
        page = win.journey_map
        view = page.view
        self.assertEqual(Qt.FocusPolicy.StrongFocus, view.focusPolicy())
        win.activateWindow()
        guikit.pump()
        self.assertIs(QApplication.focusWidget(), page, "지도를 열면 초점은 화면 자체. 초점 테두리를 단 단추가 없음")
        view.setFocus()
        press(view, Qt.Key.Key_Right)
        self.assertEqual(("t02", "던전 2 「부서진 다리」"), (view.selected, page.title.text()))
        press(view, Qt.Key.Key_Left)
        press(view, Qt.Key.Key_Left)
        self.assertEqual("t01", view.selected, "첫 칸에서 왼쪽은 그대로")
        press(view, Qt.Key.Key_Down)
        self.assertEqual("t08", view.selected, "둘째 줄은 오른쪽에서 왼쪽으로 가므로 화면 아래 칸은 던전 8")
        press(view, Qt.Key.Key_Right)
        self.assertEqual("t07", view.selected)
        press(view, Qt.Key.Key_Up)
        self.assertEqual("t02", view.selected)
        press(view, Qt.Key.Key_End)
        self.assertEqual("t16", view.selected)
        press(view, Qt.Key.Key_Home)
        self.assertEqual("t01", view.selected)
        press(view, Qt.Key.Key_Return)
        self.assertIs(QApplication.focusWidget(), page.rows.rows[0], "Enter 는 그 던전의 첫 열 수 있는 줄로 초점을 옮김")
        press(page.rows.rows[0], Qt.Key.Key_Space)
        self.assertEqual((win.pages.currentWidget(), win.journey_page.pid), (win.journey_page, "p1"))

    def test_javascript_without_node_keeps_python_and_the_banner_finds_node(self):
        win = self.boot()
        page = win.journey_map
        self.assertFalse(page.node_banner.isVisible())
        state = {"ok": False}

        def find_node(probe=True):
            state["ok"] = True
            return HAS_NODE

        runtime = lambda lang: HAS_NODE if lang == "python" or state["ok"] else NO_NODE  # noqa: E731
        with mock.patch.object(win.journey, "runtime", runtime), mock.patch.object(win.journey, "find_node", find_node):
            guikit.click(page.lang_btns["javascript"])
            self.assertEqual((page.lang_btns["python"].isChecked(), page.lang_btns["javascript"].isChecked()), (True, False))
            self.assertTrue(page.node_banner.isVisible())
            self.assertFalse(page.lang_bar.note.isVisible(), "지도는 칩 옆 글 대신 띠로 알림")
            self.assertEqual(NODE_TITLE, win.dialog.windowTitle())
            win.dialog.close()
            guikit.click(page.node_banner.action)
            self.assertEqual(NODE_TITLE, win.dialog.windowTitle())
            self.choose("find")
            self.assertEqual((page.lang_btns["python"].isChecked(), page.lang_btns["javascript"].isChecked()), (False, True))
            self.assertFalse(page.node_banner.isVisible())
            self.assertEqual("javascript", win.settings.value("journey/lang"))

    def test_busy_map_turns_off_its_controls_and_names_the_job(self):
        win = self.boot()
        page = win.journey_map
        page.set_busy(True, NODE_BUSY)
        guikit.pump()
        self.assertEqual((page.busy_label.text(), page.busy_label.isVisible(), page.busy_bar.isVisible()), (NODE_BUSY, True, True))
        controls = [page.home_btn, page.next_btn, page.view] + list(page.lang_btns.values())
        self.assertEqual([], [widget for widget in controls + page.rows.rows if widget.isEnabled()])
        page.show_dungeon("t01")
        self.assertEqual([], [row for row in page.rows.rows if row.isEnabled()], "바쁜 동안 새로 만든 줄도 꺼짐")
        guikit.click(page.rows.rows[0])
        self.assertIs(win.pages.currentWidget(), page)
        page.set_busy(False)
        guikit.pump()
        self.assertEqual((page.busy_label.isVisible(), page.busy_bar.isVisible()), (False, False))
        self.assertTrue(all(widget.isEnabled() for widget in controls + page.rows.rows))

    def test_text_steps_resize_the_map_rows_chips_and_intro(self):
        self.addCleanup(theme.set_text, "normal")
        win = self.boot()
        page = win.journey_map
        for step, px, height in (("larger", 21, 394), ("large", 19, 378)):
            win.set_text(step)
            guikit.pump()
            self.assertEqual(height, page.view.height(), step)
            for chip in page.lang_btns.values():
                self.assertGreaterEqual(chip.width(), chip.sizeHint().width(), step)
                self.assertGreaterEqual(chip.minimumWidth(), chip.sizeHint().width(), step)
            self.assertEqual(px, page.rows.rows[0].title.font().pixelSize(), step)
            self.assertEqual(px, first_px(page.intro), step)
            card = page.map_card
            for item in page.legend.items:
                place = item.mapTo(card, item.rect().topLeft())
                self.assertGreaterEqual(place.x(), 24, step)
                self.assertLessEqual(place.x() + item.width(), card.width() - 24, step)

    def test_home_button_goes_to_the_hub(self):
        win = self.boot()
        guikit.click(win.journey_map.home_btn)
        self.assertEqual(["hub"], win.went)


class PageTest(Base):
    def test_only_the_chosen_language_function_block_shows(self):
        win = self.boot()
        page = self.open("p1")
        text = doc_text(page.problem_view)
        self.assertIn("def solution(nums: list[int]) -> int:", text)
        self.assertNotIn("function solution(nums) {}", text)
        self.assertEqual("solution.py", page.code_panel.hint.text())
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
        text = doc_text(page.problem_view)
        self.assertIn("function solution(nums) {}", text)
        self.assertNotIn("def solution", text)

    def test_language_switch_opens_the_other_file_and_highlighting(self):
        win = self.boot()
        page = self.open("p1")
        editor = page.code_panel.editor
        self.assertIn(("def", "keyword"), guikit.painted(editor, 0))
        self.type_code("# 파이썬 풀이\n" + editor.toPlainText())
        page.status.setText("코드 실행을 마쳤습니다.")
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
            self.assertEqual("javascript", page.lang)
            self.assertEqual("", page.status.text(), "앞 언어의 상태 글이 남지 않음")
            self.assertIs(JAVASCRIPT, editor.lang)
            self.assertEqual(values.starter(page.data["signature"], "javascript"), editor.toPlainText())
            self.assertIn(("function", "keyword"), guikit.painted(editor, 0))
            self.assertEqual("solution.js", page.code_panel.hint.text())
            self.assertEqual("javascript", win.settings.value("journey/lang"))
            self.assertIn("# 파이썬 풀이", study.read_text(self.code_path("p1")))
            self.type_code("// 자바스크립트\n" + editor.toPlainText())
            guikit.click(page.lang_btns["python"])
        self.assertIs(PYTHON, editor.lang)
        self.assertTrue(editor.toPlainText().startswith("# 파이썬 풀이"))
        self.assertIn(("# 파이썬 풀이", "comment"), guikit.painted(editor, 0))
        self.assertTrue(study.read_text(self.code_path("p1", ".js")).startswith("// 자바스크립트"))

    def test_code_is_saved_after_typing_stops(self):
        self.boot()
        page = self.open("p2")
        self.assertEqual(400, page.save_timer.interval())
        editor = page.code_panel.editor
        editor.moveCursor(editor.textCursor().MoveOperation.End)
        QTest.keyClicks(editor, "# note")  # keyClicks 는 ASCII 만 받음
        self.assertTrue(page.dirty)
        guikit.wait_until(lambda: not page.dirty, timeout=10)
        self.assertIn("# note", study.read_text(self.code_path("p2")))
        self.assertIn("자동 저장했습니다", page.status.text())

    def test_reset_returns_to_the_starter_code(self):
        self.boot()
        page = self.open("p2")
        editor = page.code_panel.editor
        self.type_code(MAX_SOLUTION)
        self.assertTrue(page.flush())
        guikit.click(page.code_panel.reset_btn)
        self.choose("reset")
        starter = values.starter(page.data["signature"], "python")
        self.assertEqual(starter, editor.toPlainText())
        self.assertEqual(starter, study.read_text(self.code_path("p2")))
        editor.undo()
        self.assertEqual(MAX_SOLUTION, editor.toPlainText())

    def test_boss_band_and_problem_lines_follow_uses_and_prep(self):
        self.boot([passed("p1"), passed("p2")])
        page = self.open("boss")
        self.assertTrue(page.band.isVisible())
        self.assertEqual("보스 문제입니다. 이 던전의 1-1, 1-2에서 익힌 기술을 함께 씁니다.", page.band.text())
        self.assertIn("이 보스에 쓰는 문제: 1-1, 1-2", doc_text(page.problem_view))
        page = self.open("p2")
        self.assertFalse(page.band.isVisible())
        self.assertIn("준비 문제: 1-1 물통 합계 (통과)", doc_text(page.problem_view))


class ClipboardTest(Base):
    def test_paste_and_copy_work_on_the_problem_page_only(self):
        win = self.boot()
        page = self.open("p1")
        editor = page.code_panel.editor
        QGuiApplication.clipboard().setText("print('붙임')")
        editor.setFocus()
        editor.moveCursor(editor.textCursor().MoveOperation.End)
        QTest.keyClick(editor, Qt.Key.Key_V, guikit.CTRL)
        guikit.pump()
        self.assertTrue(editor.toPlainText().endswith("print('붙임')"))
        self.assertEqual(0, win.blocked)
        piece = next(piece for piece in page.problem_view.pieces if isinstance(piece, TextPiece))
        piece.selectAll()
        QTest.keyClick(piece, Qt.Key.Key_C, guikit.CTRL)
        guikit.pump()
        self.assertIn("문제 설명", QGuiApplication.clipboard().text())
        self.assertEqual(0, win.blocked)
        answer = win.round_page.code_panel.editor
        answer.setPlainText("x = 1")
        QTest.keyClick(answer, Qt.Key.Key_V, guikit.CTRL)
        guikit.pump()
        self.assertEqual("x = 1", answer.toPlainText())
        self.assertEqual(1, win.blocked)


@SKIP_LEAN
class RunGradeTest(Base):
    def test_run_shows_input_expected_result_and_output(self):
        self.boot()
        page = self.open("p2")
        self.type_code(MAX_SOLUTION)
        with mock.patch.object(page, "on_progress", wraps=page.on_progress) as progress:
            guikit.click(page.run_btn)
        cases = [call.args[0] for call in progress.call_args_list if call.args[0].get("kind") == "case"]
        self.assertEqual([1, 2, 3], [event["case"]["no"] for event in cases])
        text = self.console()
        for line in ("테스트 1", "입력값 〉 [3, 9, 4]", "기댓값 〉 9", "실행 결과 〉 테스트를 통과하였습니다.", "출력 〉", "찍음",
                     "테스트 결과 3개 중 3개 성공", "채점에서는 Python 2초, JavaScript 1초 안에 끝나야 합니다."):
            self.assertIn(line, text)
        self.assertRegex(text, r"시간·메모리 〉 \d+\.\d\dms, \d+\.\dMB")
        self.assertEqual([], self.read_log())
        self.assertTrue(page.run_btn.isEnabled())
        self.assertFalse(page.stop_btn.isEnabled())
        page.load("t01", "p1")
        page.load("t01", "p2")
        self.assertIn("테스트 결과 3개 중 3개 성공", self.console(), "결과는 (문제, 언어)마다 기억함")

    def test_grade_shows_two_groups_and_the_total(self):
        win = self.boot()
        page = self.open("p2")
        self.type_code(FIRST_SOLUTION)
        guikit.click(page.grade_btn)
        text = self.console()
        self.assertIn("정확성 테스트", text)
        self.assertIn("효율성 테스트", text)
        self.assertRegex(text, r"테스트 3 〉 통과 \(\d+\.\d\dms, \d+\.\dMB\)")
        self.assertRegex(text, r"테스트 13 〉 (통과|실패) \(\d+\.\d\dms, \d+\.\dMB\) · 50건")
        self.assertRegex(text, r"합계: \d+\.\d / 100\.0")
        self.assertNotIn("합계: 100.0", text)
        self.assertEqual(1, len(self.read_log()))
        self.type_code(MAX_SOLUTION)
        guikit.click(page.grade_btn)
        text = self.console()
        self.assertIn("합계: 100.0 / 100.0", text)
        self.assertIn("처음으로 통과했습니다. 해설을 볼 수 있습니다.", text)
        self.assertIn("보스 문제가 열렸습니다.", text)
        self.assertTrue(page.give_up_btn.isHidden())
        self.assertIn("기준 풀이 (Python)", doc_text(page.explain_view))
        page.on_link(journey_html.BOSS_LINK)
        self.assertEqual("boss", page.pid)
        self.assertIs(win.pages.currentWidget(), page)

    def test_stop_during_grading_keeps_no_record(self):
        win = self.boot()
        page = self.open("p2")
        self.type_code(MAX_SOLUTION)
        seen = []

        def progress(event, original=page.on_progress):
            if event.get("kind") == "case" and not seen:
                seen.append((page.stop_btn.isEnabled(), page.run_btn.isEnabled(), page.code_panel.isEnabled()))
                guikit.click(page.stop_btn)
            original(event)

        with mock.patch.object(page, "on_progress", progress):
            guikit.click(page.grade_btn)
        self.assertEqual([(True, False, False)], seen)
        self.assertIn(journey_html.STOPPED_GRADE, self.console())
        self.assertNotIn("합계", self.console())
        self.assertEqual([], self.read_log())
        self.assertIsNone(win.job)

    def test_first_boss_pass_announces_the_clear(self):
        win = self.boot([passed("p2")])
        page = self.open("boss")
        self.type_code(BOSS_SOLUTION)
        guikit.click(page.grade_btn)
        self.assertIn("합계: 100.0 / 100.0", self.console())
        self.assertEqual("던전 1 「시험 마을」을 클리어했습니다. 출제된 던전을 모두 클리어했습니다.", win.dialog.text.text())


    @unittest.skipUnless(NODE, "Node.js 가 없어 JavaScript 채점을 건너뜁니다")
    def test_javascript_grading_uses_node(self):
        self.boot()
        page = self.open("p2")
        guikit.click(page.lang_btns["javascript"])
        self.assertEqual("javascript", page.lang)
        self.type_code("function solution(nums) {\n    console.log(nums.length);\n    return Math.max(...nums);\n}\n")
        guikit.click(page.run_btn)
        text = self.console()
        self.assertIn("입력값 〉 [-5, -2, -8]", text)
        self.assertIn("테스트 결과 3개 중 3개 성공", text)
        self.assertIn("출력 〉", text)
        guikit.click(page.grade_btn)
        text = self.console()
        self.assertIn("합계: 100.0 / 100.0", text)
        self.assertIn("Node.js %s로 실행했습니다." % NODE["version"], text)
        self.assertEqual(["javascript"], [entry["lang"] for entry in self.read_log()])
        self.assertTrue(os.path.isfile(self.code_path("p2", ".js")))


class NodeTest(Base):
    def test_missing_node_keeps_python_and_offers_a_node_path(self):
        win = self.boot()
        page = self.open("p1")
        state = {"ok": False, "set": []}

        def set_node(path):
            state["set"].append(path)
            state["ok"] = True
            return HAS_NODE

        runtime = lambda lang: HAS_NODE if lang == "python" or state["ok"] else NO_NODE  # noqa: E731
        with mock.patch.object(win.journey, "runtime", runtime), mock.patch.object(win.journey, "set_node", set_node):
            guikit.click(page.lang_btns["javascript"])
            self.assertEqual("python", page.lang)
            self.assertIs(PYTHON, page.code_panel.editor.lang)
            self.assertEqual((page.lang_btns["python"].isChecked(), page.lang_btns["javascript"].isChecked()), (True, False))
            self.assertTrue(page.lang_bar.note.isVisible())
            self.assertEqual(NODE_TITLE, win.dialog.windowTitle())
            self.assertIn("Node.js 20 이상", win.dialog.text.text())
            self.choose("pick")
            self.assertEqual(1, len(win.picks))
            self.assertEqual([], state["set"], "고르지 않고 닫으면 아무것도 바꾸지 않음")
            self.assertEqual("python", page.lang)
            guikit.click(page.lang_btns["javascript"])
            win.pick_result = "/opt/node/bin/node"
            self.choose("pick")
            self.assertEqual(["/opt/node/bin/node"], state["set"])
            self.assertEqual("/opt/node/bin/node", win.settings.value("journey/node"))
            self.assertEqual("javascript", page.lang)
            self.assertFalse(page.lang_bar.note.isVisible())

    def test_find_again_reports_when_node_is_still_missing(self):
        win = self.boot()
        page = self.open("p1")
        with mock.patch.object(win.journey, "runtime", lambda lang: NO_NODE), \
                mock.patch.object(win.journey, "find_node", lambda probe=True: NO_NODE):
            guikit.click(page.lang_btns["javascript"])
            self.choose("find")
        self.assertEqual("알림", win.dialog.windowTitle())
        self.assertEqual(NO_NODE["problem"], win.dialog.text.text())
        self.assertEqual("python", page.lang)

    def test_node_is_looked_up_only_after_javascript_was_chosen(self):
        win = self.boot()
        with mock.patch.object(win.journey, "runtime", return_value=HAS_NODE) as runtime:
            win.journey_map.refresh()
            self.open("p1")
            self.assertFalse(runtime.called)
            win.settings.setValue("journey/lang", "javascript")
            win.go_journey()
            runtime.assert_called_with("javascript")
        self.assertEqual("javascript", win.journey_map.lang_bar.lang)
        self.assertFalse(win.journey_map.node_banner.isVisible())
        with mock.patch.object(win.journey, "runtime", return_value=NO_NODE):
            win.journey_map.refresh()
            self.assertEqual("python", win.journey_map.lang_bar.lang)
            self.assertTrue(win.journey_map.lang_btns["python"].isChecked())
            self.assertTrue(win.journey_map.node_banner.isVisible())
            page = self.open("p1")
        self.assertEqual("python", page.lang)
        self.assertTrue(page.lang_bar.note.isVisible())

    def test_map_language_buttons_share_the_setting(self):
        win = self.boot()
        page = win.journey_map
        with mock.patch.object(win.journey, "runtime", lambda lang: NO_NODE):
            guikit.click(page.lang_btns["javascript"])
            self.assertEqual(NODE_TITLE, win.dialog.windowTitle())
            self.assertNotEqual("javascript", win.settings.value("journey/lang"))
            win.dialog.close()
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
            self.assertEqual("javascript", win.settings.value("journey/lang"))
            problem = self.open("p1")
            self.assertEqual("javascript", problem.lang)
            self.assertEqual("solution.js", problem.code_panel.hint.text())


class HintExplainTest(Base):
    def test_hints_open_in_order(self):
        self.boot()
        page = self.open("p1")
        self.assertEqual("힌트 0/3", page.tabs.tabText(1))
        self.assertEqual("힌트 1 보기", page.hint_btn.text())
        self.assertIn("힌트는 한 단계씩 열리고, 연 단계는 기록에 남습니다.", doc_text(page.hint_view))
        self.assertEqual("", page.hint_note.text())
        guikit.click(page.hint_btn)
        self.assertEqual("힌트 1/3", page.tabs.tabText(1))
        self.assertIn("한 변수에 모아 두세요", doc_text(page.hint_view))
        self.assertNotIn("변수를 0으로 시작하고", doc_text(page.hint_view))
        self.assertNotIn("힌트는 한 단계씩", doc_text(page.hint_view))
        guikit.click(page.hint_btn)
        guikit.click(page.hint_btn)
        self.assertEqual("힌트 3/3", page.tabs.tabText(1))
        text = doc_text(page.hint_view)
        self.assertLess(text.index("힌트 1"), text.index("힌트 2"))
        self.assertLess(text.index("힌트 2"), text.index("힌트 3"))
        self.assertTrue(page.hint_btn.isHidden())
        self.assertEqual("힌트를 모두 열었습니다.", page.hint_note.text())
        self.assertEqual([1, 2, 3], [entry["level"] for entry in self.read_log() if entry["kind"] == "hint"])

    def test_giving_up_opens_the_explanation_with_parts_solution_and_similar(self):
        win = self.boot([passed("p2")])
        page = self.open("boss")
        page.tabs.setCurrentIndex(2)
        self.assertIn("이 문제를 통과하면 해설이 열립니다.", doc_text(page.explain_view))
        guikit.click(page.give_up_btn)
        self.assertEqual(GIVE_UP_TEXT, win.dialog.text.text())
        self.choose("")
        self.assertFalse(page.give_up_btn.isHidden())
        self.assertNotIn("explain", [entry["kind"] for entry in self.read_log()])
        guikit.click(page.give_up_btn)
        self.choose("open")
        self.assertTrue(page.give_up_btn.isHidden())
        text = doc_text(page.explain_view)
        for line in ("느린 풀이", "합성표", "배열을 한 번 훑으며 값을 더함", "큰 값부터 고름", "기준 풀이 (Python)", "더 풀어 볼 문제",
                     "프로그래머스 · K번째수", "백준 2750 · 수 정렬하기"):
            self.assertIn(line, text)
        self.assertLess(text.index("느린 풀이"), text.index("합성표"))
        self.assertLess(text.index("합성표"), text.index("기준 풀이"))
        self.assertLess(text.index("기준 풀이"), text.index("더 풀어 볼 문제"))
        codes = [piece for piece in page.explain_view.pieces if isinstance(piece, CodeView)]
        self.assertEqual(1, len(codes))
        self.assertIn("def solution(nums, k):", codes[0].toPlainText())
        self.assertEqual(["explain"], [entry["kind"] for entry in self.read_log() if entry["item"] == "t01/boss"])
        link = next(piece for piece in page.explain_view.pieces if isinstance(piece, TextPiece) and "K번째수" in piece.toPlainText())
        link.anchorClicked.emit(QUrl("https://school.programmers.co.kr/learn/courses/30/lessons/42748"))
        self.assertEqual(["https://school.programmers.co.kr/learn/courses/30/lessons/42748"], win.opened)
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
        self.assertIn("기준 풀이 (JavaScript)", doc_text(page.explain_view))
        codes = [piece for piece in page.explain_view.pieces if isinstance(piece, CodeView)]
        self.assertIn("function solution(nums, k)", codes[0].toPlainText())


class CasesDialogTest(Base):
    def test_cells_are_checked_and_saved(self):
        self.boot()
        page = self.open("p3")
        guikit.click(page.cases_btn)
        dialog = page.cases_dialog
        self.assertTrue(dialog.isVisible())
        edits, _ = dialog.rows[0]
        edits[0].setText('"abc"')
        edits[1].setText("3")
        self.assertEqual("1번 케이스의 return 칸: 문자열이 아닙니다: 3", dialog.error.text())
        edits[1].setText("[1,")
        self.assertIn("1번 케이스의 return 칸: 값을 읽지 못했습니다.", dialog.error.text())
        guikit.click(dialog.save_btn)
        self.assertTrue(dialog.isVisible())
        edits[1].setText("'cba'")
        self.assertEqual("", dialog.error.text())
        guikit.click(dialog.add_btn)
        guikit.click(dialog.add_btn)
        self.assertEqual(3, len(dialog.rows))
        dialog.rows[1][0][0].setText("1")
        self.assertEqual("2번 케이스의 name 칸: 문자열이 아닙니다: 1", dialog.error.text())
        guikit.click(dialog.rows[1][1])
        self.assertEqual(2, len(dialog.rows))
        self.assertEqual("", dialog.error.text())
        guikit.click(dialog.save_btn)
        self.assertFalse(dialog.isVisible())
        self.assertEqual([{"args": ["abc"], "expected": "cba"}], page.data["cases"])
        saved = study.read_json(os.path.join(study.SUBMISSIONS_DIR, "alice", "journey", "t01", "p3.cases.json"))
        self.assertEqual([{"args": ["abc"], "expected": "cba"}], saved["cases"])
        self.assertIn("테스트 케이스 1개를 저장했습니다", page.status.text())
        guikit.click(page.cases_btn)
        self.assertEqual(["'abc'", "'cba'"], [edit.text() for edit in page.cases_dialog.rows[0][0]])

    def test_from_example_adds_a_row_in_the_chosen_language(self):
        win = self.boot()
        page = self.open("p3")
        guikit.click(page.cases_btn)
        dialog = page.cases_dialog
        self.assertEqual("예시에서 가져오기", dialog.example_btn.text(), "메뉴 화살표는 Qt 가 그림")
        self.assertEqual(["입출력 예 1", "입출력 예 2", "입출력 예 3"], [action.text() for action in dialog.example_menu.actions()])
        dialog.example_menu.actions()[1].trigger()
        self.assertEqual(2, len(dialog.rows))
        self.assertEqual(["'level'", "'level'"], [edit.text() for edit in dialog.rows[1][0]])
        dialog.close()
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
        guikit.click(page.cases_btn)
        page.cases_dialog.example_menu.actions()[0].trigger()
        self.assertEqual(['"abc"', '"cba"'], [edit.text() for edit in page.cases_dialog.rows[-1][0]])
        self.assertEqual("", page.cases_dialog.error.text())


class DarkThemeTest(Base):
    def test_map_and_problem_page_have_no_bright_area(self):
        mode = theme.state["mode"]
        self.addCleanup(theme.set_mode, mode)
        theme.set_mode("dark")
        win = self.boot([passed("p2"), passed("boss")])
        guikit.pump(60)
        self.assertEqual(0, bright_share(win))
        page = self.open("boss")
        page.tabs.setCurrentIndex(2)
        guikit.pump(60)
        self.assertIn("기준 풀이 (Python)", doc_text(page.explain_view))
        self.assertEqual(0, bright_share(win))
        page.code_panel.show_console(journey_html.grade_html({"groups": [], "score": 100.0, "runtime": "Python 3.14.4"}))
        page.tabs.setCurrentIndex(0)
        guikit.pump(60)
        self.assertEqual(0, bright_share(win))
        theme.set_mode("light")
        win.journey_page.restyle()
        guikit.pump(60)
        self.assertGreater(bright_share(win), 0.3)


if __name__ == "__main__":
    unittest.main()
