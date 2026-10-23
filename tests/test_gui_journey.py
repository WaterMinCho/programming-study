# -*- coding: utf-8 -*-
"""여행 화면: 던전 지도(gui/journey_map.py), 문제 화면(gui/journey_page.py, 결과 카드 gui/journey_result.py), 테스트 추가 창(gui/cases_dialog.py),
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
from PyQt6.QtGui import QFontMetricsF, QGuiApplication, qGray  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QFrame, QMainWindow, QPushButton, QStackedWidget  # noqa: E402

import adaptive  # noqa: E402
import study  # noqa: E402
from gui import journey_html, journey_text, kit, theme  # noqa: E402
from gui.cases_dialog import HINT, TITLE  # noqa: E402
from gui.dialogs import MessageDialog  # noqa: E402
from gui.docview import CodeView, FigureView, TextPiece  # noqa: E402
from gui.editor import JAVASCRIPT, PYTHON  # noqa: E402
from gui.guard import Guard  # noqa: E402
from gui.journey_map import ALL_CLEAR, BROKEN, CACHE_TIP, CLEAR_TEXT, WAITING, JourneyMapPage, MapView  # noqa: E402
from gui.journey_page import (GIVE_UP_TEXT, GIVE_UP_TITLE, NODE_BUSY, NODE_LINK, NODE_MISSING, NODE_TEXT, NODE_TITLE, RESET_TITLE,  # noqa: E402
                               JourneyPage)
from gui.round_page import RoundPage  # noqa: E402
from gui.widgets import Para  # noqa: E402
from journey import bank, node, runner, values  # noqa: E402
from journey.service import JourneyError, JourneySession  # noqa: E402
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
            title, text, detail = journey_text.error_text("open", error)
            self.ask(title, text, detail=detail)
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
        """결과 카드의 머리, 띠, 본문 글."""
        return self.win.journey_page.result.text()

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


def button_line(dialog):
    """대화상자 단추를 왼쪽부터 (키, 글자, 종류). 종류는 objectName 이고 보조 단추는 빈 글."""
    keys = sorted(dialog.buttons, key=lambda key: dialog.buttons[key].mapTo(dialog, dialog.buttons[key].rect().topLeft()).x())
    return [(key, dialog.buttons[key].text(), dialog.buttons[key].objectName()) for key in keys]


def edge_ink(edit):
    """입력칸 위 테두리 가운데 화소의 색 이름."""
    return edit.grab().toImage().pixelColor(edit.width() // 2, 1).name()


def has_underline(link):
    """링크 글을 그린 그림에 글 폭의 9할 넘게 이어지는 가로 줄(밑줄)이 있는지. 글자 획은 그만큼 길게 이어지지 않음."""
    image, back = link.grab().toImage(), link.palette().color(link.backgroundRole())
    width = QFontMetricsF(link.font()).horizontalAdvance(link.text().split(">", 1)[1].split("<", 1)[0])
    for y in range(image.height()):
        run = sum(1 for x in range(image.width()) if abs(image.pixelColor(x, y).lightness() - back.lightness()) > 40)
        if run >= 0.9 * width:
            return True
    return False


def full_lines(editor):
    """편집기에 다 보이는 줄 수."""
    return int((editor.viewport().height() - 2 * editor.document().documentMargin()) // QFontMetricsF(editor.font()).lineSpacing())


def run_case(no, ok=True, printed=""):
    """grading.run 이 진행 알림과 결과에 넣는 줄과 같은 꼴."""
    return {"no": no, "source": "example", "args_text": "[3, 9, 4]", "want_text": "9", "got_text": "9" if ok else "3",
            "status": "pass" if ok else "wrong", "ok": ok, "ms": 0.01, "mb": 10.2, "printed": printed, "printed_cut": False, "error": "", "note": ""}


def fake_run(cases, seen=None, check=None):
    """자식 프로세스 없이 cases 를 하나씩 알리고 결과를 돌려주는 service.run 대신. 알릴 때마다 check() 를 부르고 seen 에 부른 인자를 남김."""

    def run(did, pid, lang, report, cancel):
        if seen is not None:
            seen.append((did, pid, lang))
        for case in cases:
            report({"kind": "case", "case": case})
            if check:
                check()
        return {"lang": lang, "fatal": None, "cases": list(cases), "passed": sum(case["ok"] for case in cases), "total": len(cases),
                "cancelled": False, "limit_note": "", "runtime": "Python 3.14.4"}

    return run


def fake_grade(result, seen=None, check=None):
    """자식 프로세스 없이 result 를 돌려주는 service.grade 대신. 단계 문장 하나를 알리고 check() 를 부름."""

    def grade(did, pid, lang, report, cancel):
        if seen is not None:
            seen.append((did, pid, lang))
        report({"kind": "status", "text": "정확성 테스트를 채점하는 중입니다."})
        if check:
            check()
        return dict({"groups": [], "score": 0.0, "runtime": "Python 3.14.4"}, **result)

    return grade


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
        self.assertEqual(("가장 큰 물통", "중급", "1-2"), (win.journey_page.title.text(), win.journey_page.badge.text(), win.journey_page.number.text()))
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
        self.assertEqual("문제 열기", win.dialog.windowTitle())
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
        self.assertEqual("캐시 비우기", win.dialog.windowTitle())
        self.assertEqual(CLEAR_TEXT % "3MB", win.dialog.text.text())
        self.assertIn("3MB", win.dialog.text.text())
        self.assertEqual([("", "닫기", ""), ("clear", "지우기", "primary")], button_line(win.dialog))
        self.assertFalse(win.dialog.buttons["clear"].isDefault(), "단추가 둘이라 Enter 로 지우지 않음")
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
        page.set_status("내 테스트 1개를 저장했습니다.")
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
            self.assertEqual("javascript", page.lang)
            self.assertEqual("", page.status.text(), "앞 언어의 상태 글이 남지 않음")
            self.assertIs(JAVASCRIPT, editor.lang)
            self.assertEqual(values.starter(page.data["signature"], "javascript"), editor.toPlainText())
            self.assertIn(("function", "keyword"), guikit.painted(editor, 0))
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
        self.assertEqual("저장했습니다", page.status.text())
        self.assertRegex(page.status.toolTip(), r"^\d\d:\d\d:\d\d 에 저장했습니다\.$")

    def test_reset_returns_to_the_starter_code(self):
        win = self.boot()
        page = self.open("p2")
        editor = page.code_panel.editor
        self.type_code(MAX_SOLUTION)
        self.assertTrue(page.flush())
        guikit.click(page.code_panel.reset_btn)
        self.assertEqual(RESET_TITLE, win.dialog.windowTitle())
        self.assertIn("Ctrl+Z", win.dialog.text.text())
        self.assertEqual([("", "닫기", ""), ("reset", "되돌리기", "danger")], button_line(win.dialog))
        self.choose("reset")
        starter = values.starter(page.data["signature"], "python")
        self.assertEqual(starter, editor.toPlainText())
        self.assertEqual(starter, study.read_text(self.code_path("p2")))
        editor.undo()
        self.assertEqual(MAX_SOLUTION, editor.toPlainText())

    def test_service_errors_name_the_action_and_keep_the_original_in_details(self):
        win = self.boot()
        page = self.open("p2")
        with mock.patch.object(win.journey, "reveal_hint", side_effect=JourneyError("문제 t01/p2 를 찾을 수 없습니다.")):
            guikit.click(page.hint_btn)
        self.assertEqual(("힌트 열기", journey_text.REFETCH), (win.dialog.windowTitle(), win.dialog.text.text()))
        self.assertEqual("문제 t01/p2 를 찾을 수 없습니다.", win.dialog.detail.toPlainText())
        self.assertNotIn("t01", win.dialog.text.text())
        win.dialog.close()
        with mock.patch.object(win.journey, "run", side_effect=JourneyError("코드를 실행하지 못했습니다. [Errno 2] python3")):
            guikit.click(page.run_btn)
        self.assertEqual(("코드 실행", "코드를 실행하지 못했습니다."), (win.dialog.windowTitle(), win.dialog.text.text()))
        self.assertEqual("[Errno 2] python3", win.dialog.detail.toPlainText())
        self.assertTrue(page.run_btn.isEnabled() and page.code_panel.editor.isEnabled(), "바쁜 상태가 풀림")
        self.assertIsNone(page.live)
        win.dialog.close()
        with mock.patch.object(win.journey, "grade", side_effect=JourneyError("채점하지 못했습니다. 디스크가 가득 찼습니다.")):
            guikit.click(page.grade_btn)
        self.assertEqual(("채점하기", "채점하지 못했습니다."), (win.dialog.windowTitle(), win.dialog.text.text()))
        self.assertEqual([], self.read_log())

    def test_top_bar_and_problem_head_follow_the_role(self):
        """위 막대는 이름, 역할 꼬리표, 번호이고 보스는 번호 대신 "던전 1 보스". 지문 머리 첫 줄은 난이도와 지금 언어의 시간 제한,
        둘째 줄은 보스가 쓰는 앞 문제, 선택 문제의 안내, 중급의 준비 문제 링크와 통과 꼬리표. 보스의 노란 띠는 없음."""
        win = self.boot([passed("p1"), passed("p2")])
        page = self.open("boss")
        self.assertEqual(("물통 정리", "보스", "던전 1 보스"), (page.title.text(), page.badge.text(), page.number.text()))
        self.assertEqual("난이도 S5 / Lv2 · 시간 제한 2초 이 던전의 1-1~1-2에서 익힌 기술을 함께 씁니다.", page.facts.text())
        self.assertEqual("백준 실버 5, 프로그래머스 레벨 2 수준입니다.", page.facts.first.toolTip())
        self.assertEqual([], [banner for banner in page.findChildren(QFrame, "banner") if banner.isVisible()])
        self.assertNotIn("이 보스에 쓰는 문제", doc_text(page.problem_view))
        page = self.open("p3")
        self.assertEqual(("이름 뒤집기", "선택", "1-3"), (page.title.text(), page.badge.text(), page.number.text()))
        self.assertEqual("난이도 B3 / Lv1 · 시간 제한 2초 풀지 않아도 보스가 열립니다.", page.facts.text())
        page = self.open("p2")
        self.assertEqual("난이도 B1 / Lv1 · 시간 제한 2초 준비 문제 1-1 물통 합계 통과", page.facts.text())
        self.assertNotIn("준비 문제", doc_text(page.problem_view))
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
        self.assertIn("시간 제한 1초", page.facts.text(), "시간 제한은 고른 언어의 값")
        page.facts.links[0].linkActivated.emit("p1")
        guikit.pump()
        self.assertEqual("p1", page.pid, "준비 문제 링크를 누르면 그 문제를 엶")
        self.assertEqual("난이도 B2 / Lv1 · 시간 제한 1초", page.facts.text())

    def test_the_prep_link_keeps_its_underline(self):
        """통과 꼬리표가 없으면 둘째 줄이 링크 높이로 줄어드는데, 그때도 링크 밑줄이 잘리지 않음."""
        self.addCleanup(theme.set_text, "normal")
        win = self.boot()
        page = self.open("p2")
        for step in ("normal", "large"):
            win.set_text(step)
            page.load("t01", "p2")
            guikit.pump()
            self.assertEqual("준비 문제 1-1 물통 합계", page.facts.text().split("초 ", 1)[1], step)
            self.assertTrue(has_underline(page.facts.links[0]), step)


class WorkFrameTest(Base):
    """문제 화면의 작업 틀: 결과 카드 머리와 접힘, 높이 예산, 단축키, 바쁜 상태, 초점, 다시 연 자리, 글자 단계, 읽는 단, 최소 폭.
    실행·채점은 service 의 run·grade 를 가짜로 바꿔 자식 프로세스 없이 결과 dict 를 넣음."""

    def small(self, log=()):
        """1024×700 창으로 시작함."""
        win = self.boot(log)
        win.resize(1024, 700)
        guikit.pump()
        return win

    def test_result_card_heads_the_run_and_the_grade(self):
        win = self.boot([passed("p2")])
        page = self.open("p1")
        with mock.patch.object(win.journey, "run", fake_run([run_case(1), run_case(2, False), run_case(3, False)])):
            guikit.click(page.run_btn)
        text = page.result.text()
        self.assertTrue(text.startswith("테스트 3개 중 1개 통과\n고친 뒤 다시 실행하세요.\n"), text)
        self.assertIn("입력값 〉 [3, 9, 4]", text)
        self.assertEqual((1 * 10, 3 * 10, ""), (page.result.bar.value(), page.result.bar.maximum(), page.result.bar.property("tone") or ""))
        result = {"score": 41.5, "groups": [{"name": "정확성", "earned": 29.5, "points": 70.0, "cases": []},
                                            {"name": "효율성", "earned": 12.0, "points": 30.0, "cases": []}]}
        with mock.patch.object(win.journey, "grade", fake_grade(result)):
            guikit.click(page.grade_btn)
        self.assertTrue(page.result.text().startswith("100점 중 41.5점\n정확성 29.5 / 70 · 효율성 12 / 30"), page.result.text())
        self.assertFalse(page.result.banners.isVisible())
        with mock.patch.object(win.journey, "grade", fake_grade({"score": 100.0, "first_pass": True, "boss_opened": True})):
            guikit.click(page.grade_btn)
        self.assertEqual("success", page.result.bar.property("tone"))
        explain, boss = [banner.action for banner in page.result.banners.findChildren(QFrame, "banner")]
        self.assertEqual(0, page.result.scroll.verticalScrollBar().value(), "끝나면 스크롤 칸 맨 위")
        guikit.click(explain)
        self.assertEqual(2, page.tabs.currentIndex())
        guikit.click(boss)
        self.assertEqual(("boss", "물통 정리"), (page.pid, page.title.text()))

    def test_the_result_card_folds_until_the_first_run(self):
        """1024×700 에서 결과 전에는 결과 카드가 머리 글만 남아 편집기가 길어지고 손잡이가 잠김. [코드 실행]을 누르는 순간 펼치고,
        끈 몫은 0~1 값으로 남아 다시 열어도 같음. 기억한 결과가 있는 문제는 펼친 채 열림."""
        win = self.small()
        win.journey.save_cases("t01", "p3", [{"args": ["ab"], "expected": "ba"}])
        page = self.open("p3")
        guikit.pump()
        panel, result, editor = page.code_panel, page.result, page.code_panel.editor
        self.assertEqual("[코드 실행]은 입출력 예와 내 테스트 1개를 돌립니다.", result.caption.text())
        self.assertTrue(result.collapsed)
        self.assertLessEqual(result.height(), 120)
        self.assertEqual(result.height(), result.folded_height())
        self.assertGreaterEqual(full_lines(editor), 19)
        self.assertTrue(panel.split.locked)
        self.assertFalse(panel.split.handle(1).isEnabled())
        self.assertFalse(result.scroll.isVisible())
        seen = []
        with mock.patch.object(win.journey, "run", fake_run([run_case(1)], check=lambda: seen.append(result.height()))):
            guikit.click(page.run_btn)
        self.assertGreaterEqual(min(seen), 160, "누른 순간 펼침")
        self.assertFalse(panel.split.locked)
        self.assertGreaterEqual(result.height(), 160)
        self.assertGreaterEqual(full_lines(editor), 10, "펼친 뒤에도 편집기 10줄")
        guikit.drag(panel.split.handle(1), 0, 40)
        ratio = float(win.settings.value("journey/split_v"))
        self.assertTrue(0 < ratio < 1, ratio)
        heights = (editor.height(), result.height())
        page.load("t01", "p1")
        guikit.pump()
        self.assertTrue(result.collapsed, "결과가 없는 다른 문제는 다시 접힘")
        page.load("t01", "p3")
        guikit.pump()
        self.assertFalse(result.collapsed)
        self.assertEqual(heights, (editor.height(), result.height()), "끈 몫 그대로")

    def test_dragging_the_result_card_down_keeps_its_head(self):
        """1024×700 에서 실행 뒤 세로 손잡이를 끝까지 내려도 결과 카드 머리(headline, 막대, caption)는 제 높이를 지키고 스크롤 칸만 줄어듦."""
        win = self.small()
        page = self.open("p1")
        with mock.patch.object(win.journey, "run", fake_run([run_case(1), run_case(2, False)])):
            guikit.click(page.run_btn)
        result = page.result
        guikit.drag(page.code_panel.split.handle(1), 0, 600)
        self.assertEqual(result.head.sizeHint().height(), result.head.height())
        caption = result.caption.mapTo(result.head, result.caption.rect().bottomLeft()).y()
        self.assertLess(caption, result.head.height(), "caption 이 머리 안에 다 보임")
        self.assertTrue(result.bar.isVisible())
        self.assertEqual(result.minimumHeight(), result.height())

    def test_language_switch_keeps_the_card_open_without_a_result(self):
        win = self.boot()
        page = self.open("p1")
        with mock.patch.object(win.journey, "run", fake_run([run_case(1)])):
            guikit.click(page.run_btn)
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
        self.assertFalse(page.result.collapsed, "한 번 펼치면 문제를 닫을 때까지 접지 않음")
        self.assertEqual((journey_text.NOT_RUN, journey_text.RUN_HINT), (page.result.title.text(), page.result.caption.text()))
        self.assertEqual("", page.result.body.toPlainText())

    def test_shortcuts_run_grade_save_and_leave_the_editor(self):
        win = self.boot()
        page = self.open("p2")
        editor = page.code_panel.editor
        win.activateWindow()
        editor.setFocus()
        guikit.pump()
        before, runs, grades = editor.toPlainText(), [], []
        with mock.patch.object(win.journey, "run", fake_run([run_case(1)], runs)), mock.patch.object(win.journey, "grade", fake_grade({}, grades)):
            QTest.keyClick(editor, Qt.Key.Key_Return, guikit.CTRL)
            guikit.pump()
            self.assertEqual((1, 0), (len(runs), len(grades)), "Ctrl+Enter 는 코드 실행")
            self.assertEqual(before, editor.toPlainText(), "편집기에 줄바꿈이 들어가지 않음")
            self.assertEqual([], self.read_log())
            editor.setFocus()
            QTest.keyClick(editor, Qt.Key.Key_Enter, guikit.CTRL | Qt.KeyboardModifier.KeypadModifier)
            QTest.keyClick(editor, Qt.Key.Key_Return, guikit.CTRL | guikit.SHIFT)
            guikit.pump()
        self.assertEqual((2, 1), (len(runs), len(grades)), "키패드 Enter 도 실행, Ctrl+Shift+Enter 는 채점")
        self.assertIn("Ctrl+Enter", page.run_btn.toolTip())
        self.assertIn("Ctrl+Shift+Enter", page.grade_btn.toolTip())
        editor.setFocus()
        self.type_code(MAX_SOLUTION)
        QTest.keyClick(editor, Qt.Key.Key_S, guikit.CTRL)
        self.assertEqual({}, page.dirty, "기다리지 않고 바로 저장")
        self.assertEqual(MAX_SOLUTION, study.read_text(self.code_path("p2")))
        self.assertEqual("저장했습니다", page.status.text())
        self.assertEqual(journey_text.SAVED, page.status.text())
        editor.setFocus()
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.assertIs(win.focusWidget(), page.tabs.bar.buttons[0], "Esc 는 고른 탭으로 초점을 옮김")
        self.assertIn("Esc", editor.accessibleDescription())
        editor.setFocus()
        QTest.keyClick(editor, Qt.Key.Key_F, guikit.CTRL)
        self.assertTrue(page.find_bar.isVisible())
        editor.setFocus()
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.assertFalse(page.find_bar.isVisible(), "찾기 막대가 떠 있으면 Esc 는 막대를 닫음")
        self.assertIs(win.focusWidget(), editor)
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.assertIs(win.focusWidget(), page.tabs.bar.buttons[0])

    def test_find_bar_follows_the_scope_and_the_text_steps(self):
        self.addCleanup(theme.set_text, "normal")
        win = self.boot()
        page = self.open("p1")
        for step, highest in (("normal", 40), ("large", 44)):
            win.set_text(step)
            page.find_bar.reveal()
            guikit.pump()
            self.assertLessEqual(page.find_bar.height(), highest, step)
            self.assertEqual(theme.TYPE["code"][0], page.find_bar.next_btn.font().pixelSize(), step)
            self.assertEqual(theme.TYPE["code"][0], page.find_bar.input.font().pixelSize(), step)
            page.find_bar.dismiss()

    def test_busy_keeps_the_tabs_and_locks_the_rest(self):
        win = self.boot([passed("p1")])
        page = self.open("p2")
        states = []

        def check():
            chip = page.lang_btns["python"]
            image = chip.grab().toImage()
            states.append({"tabs": page.tabs.isEnabled() and all(tab.isEnabled() for tab in page.tabs.bar.buttons),
                           "locked": [widget.isEnabled() for widget in (page.code_panel.editor, page.map_btn, page.cases_btn, page.hint_btn,
                                                                        page.facts.links[0])] + [chip.isEnabled() for chip in page.lang_btns.values()],
                           "buttons": (page.run_btn.text(), page.run_btn.isEnabled(), page.grade_btn.text(), page.grade_btn.isEnabled()),
                           "stop": (page.stop_btn.isVisible(), page.stop_btn.isEnabled(), page.stop_btn.text()), "reset": page.reset_btn.isVisible(),
                           "chip": (guikit.near(image.pixelColor(image.width() // 2, 4), "selection"),
                                    guikit.near(guikit.ink(image, theme.color("selection")), "faint"))})

        with mock.patch.object(win.journey, "run", fake_run([run_case(1)], check=check)):
            guikit.click(page.run_btn)
        with mock.patch.object(win.journey, "grade", fake_grade({}, check=check)):
            guikit.click(page.grade_btn)
        run, grade = states
        for state in states:
            self.assertTrue(state["tabs"], "탭과 문서는 읽을 수 있음")
            self.assertEqual([False] * 7, state["locked"])
            self.assertEqual((True, True, "중지"), state["stop"])
            self.assertFalse(state["reset"])
            self.assertEqual((True, True), state["chip"], "꺼진 고른 칩은 알약을 남기고 글만 faint")
        self.assertEqual(("실행 중", False, "채점하기", False), run["buttons"])
        self.assertEqual(("코드 실행", False, "채점 중", False), grade["buttons"])
        self.assertEqual((False, True, True), (page.stop_btn.isVisible(), page.reset_btn.isVisible(), page.code_panel.editor.isEnabled()))
        self.assertEqual("", page.status.text(), "실행·채점의 진행은 결과 카드 머리가 말함")
        page.set_busy(True, NODE_BUSY)
        self.assertEqual((NODE_BUSY, False, False), (page.status.text(), page.stop_btn.isVisible(), page.reset_btn.isVisible()))
        page.set_busy(False)
        self.assertEqual(("", True), (page.status.text(), page.reset_btn.isVisible()))

    def test_opening_a_problem_focuses_the_editor_and_returns_to_the_last_place(self):
        win = self.small()
        win.activateWindow()
        page = self.open("p2")
        guikit.pump()
        self.assertIs(win.focusWidget(), page.code_panel.editor, "문제를 열면 바로 코드를 씀")
        bar = page.problem_view.verticalScrollBar()
        self.assertGreater(bar.maximum(), 120)
        bar.setValue(120)
        page.tabs.setCurrentIndex(1)
        self.open("p1")
        self.assertEqual((0, 0), (page.tabs.currentIndex(), bar.value()))
        self.open("p2")
        guikit.pump()
        self.assertEqual(1, page.tabs.currentIndex(), "같은 실행 안에서 다시 연 문제는 떠날 때의 탭")
        page.tabs.setCurrentIndex(0)
        guikit.pump()
        self.assertEqual(120, bar.value(), "숨어 있던 칸도 보이면 떠날 때의 자리")

    def test_a_failed_save_shows_a_banner_above_the_editor(self):
        """저장하지 못하면 편집기 위에 오류 띠가 뜨고(원문은 도움말) 위 막대의 "저장했습니다" 가 사라짐. 다음 저장이 되면 띠를 숨김."""
        win = self.boot()
        page = self.open("p2")
        banner = page.code_panel.save_banner
        self.type_code(MAX_SOLUTION)
        self.assertTrue(page.flush())
        self.assertEqual((journey_text.SAVED, True), (page.status.text(), banner.isHidden()))
        self.type_code(FIRST_SOLUTION)
        with mock.patch.object(win.journey, "save_code", side_effect=JourneyError("코드를 저장하지 못했습니다: [Errno 13] 권한 없음")):
            self.assertFalse(page.flush(offer=False))
        self.assertTrue(banner.isVisible())
        self.assertEqual(journey_text.SAVE_FAILED, banner.text.text())
        self.assertEqual("코드를 저장하지 못했습니다: [Errno 13] 권한 없음", banner.toolTip())
        self.assertEqual("", page.status.text())
        self.assertLess(banner.mapTo(page, banner.rect().topLeft()).y(), page.code_panel.editor.mapTo(page, page.code_panel.editor.rect().topLeft()).y())
        with mock.patch.object(win.journey, "save_code", side_effect=JourneyError("코드를 저장하지 못했습니다: [Errno 13] 권한 없음")):
            win.open_problem("t01", "p1")
        self.assertEqual(("문제 열기", "코드를 저장하지 못했습니다."), (win.dialog.windowTitle(), win.dialog.text.text()))
        self.assertEqual("p2", page.pid, "앞 문제의 코드를 저장하지 못하면 화면을 바꾸지 않음")
        win.dialog.close()
        self.assertTrue(page.flush())
        self.assertTrue(banner.isHidden())
        self.assertEqual(journey_text.SAVED, page.status.text())
        self.type_code(MAX_SOLUTION)
        with mock.patch.object(win.journey, "save_code", side_effect=JourneyError("코드를 저장하지 못했습니다: [Errno 13] 권한 없음")):
            self.assertFalse(page.flush(offer=False))
        page.dirty.clear()  # 창의 [저장하지 않고 나가기]가 쓰던 코드를 버림
        win.go_journey()
        self.open("p1")
        self.assertEqual((True, ""), (banner.isHidden(), page.save_error), "버린 코드의 실패 띠가 다음 문제에 남지 않음")

    def test_the_save_banner_keeps_the_window_small(self):
        """저장 실패 띠가 떠도 창의 최소 높이가 480 이하라 1366×768(125%) 화면의 1053×514 창이 커지지 않음. 띠만큼 편집기가 줄어듦."""
        self.addCleanup(theme.set_text, "normal")
        win = self.boot()
        win.resize(1053, 514)
        page = self.open("p2")
        for step in theme.TEXT_STEPS:
            win.set_text(step)
            self.type_code(MAX_SOLUTION if step != "large" else FIRST_SOLUTION)
            with mock.patch.object(win.journey, "save_code", side_effect=JourneyError("코드를 저장하지 못했습니다: [Errno 13] 권한 없음")):
                self.assertFalse(page.flush(offer=False))
            guikit.pump()
            self.assertTrue(page.code_panel.save_banner.isVisible(), step)
            self.assertLessEqual(win.minimumSizeHint().height(), 480, step)
            self.assertEqual((1053, 514), (win.width(), win.height()), step)
            self.assertTrue(page.flush())
            self.assertTrue(page.code_panel.save_banner.isHidden(), step)

    def test_the_explanation_ends_with_the_next_problem(self):
        self.boot([passed("p1")])
        page = self.open("p1")
        self.assertTrue(page.next_box.isVisibleTo(page.explain_view))
        row = page.next_rows.rows[0]
        self.assertEqual(("가장 큰 물통", "던전 1 「시험 마을」 · 중급"), (row.title.text(), row.second.text()))
        page.tabs.setCurrentIndex(2)
        guikit.click(row)
        self.assertEqual("p2", page.pid)
        page.tabs.setCurrentIndex(2)
        self.assertFalse(page.next_box.isVisible(), "해설이 잠긴 문제에는 없음")
        self.assertFalse(page.give_up_btn.isHidden())

    def test_the_head_stays_while_long_output_scrolls(self):
        """1024×700 에서 줄마다 출력 200줄인 실행 알림을 20번 넣어도 결과 카드 머리는 카드 안에 보이고 스크롤 칸만 맨 아래로 감."""
        win = self.small()
        page = self.open("p1")
        result, seen = page.result, []
        printed = "\n".join("줄 %d" % n for n in range(200))

        def check():
            guikit.pump(5)
            bar = result.scroll.verticalScrollBar()
            top = result.title.mapTo(result, result.title.rect().topLeft())
            seen.append((not result.title.visibleRegion().isEmpty(), top.y() >= 0, bar.maximum() > 0 and bar.value() == bar.maximum()))

        with mock.patch.object(win.journey, "run", fake_run([run_case(n, printed=printed) for n in range(1, 21)], check=check)):
            guikit.click(page.run_btn)
        self.assertEqual([(True, True, True)] * 20, seen)
        guikit.pump()
        self.assertEqual(0, result.scroll.verticalScrollBar().value(), "끝나면 맨 위")

    def test_text_steps_resize_the_problem_page(self):
        """문제를 연 채 보통 → 더 크게 → 크게. 돌아가기·칩은 글자가 잘리지 않고, 지문·편집기·기준 풀이·접힌 카드가 같이 커지며 읽던 자리를 지킴.
        테마를 바꿔도 글자 크기는 그대로."""
        self.addCleanup(theme.set_text, "normal")
        mode = theme.state["mode"]
        self.addCleanup(theme.set_mode, mode)
        win = self.small([passed("p1")])
        page = self.open("p1")
        page.tabs.setCurrentIndex(2)
        code = next(piece for piece in page.explain_view.pieces if isinstance(piece, CodeView))
        bar = page.problem_view.verticalScrollBar()
        bar.setValue(60)
        heights = {}
        for step in ("normal", "larger", "large"):
            win.set_text(step)
            guikit.pump()
            px = theme.text_px()
            self.assertEqual((16 + px, 15 + px), (page.code_panel.editor.font().pixelSize(), code.font().pixelSize()), step)
            self.assertEqual(theme.TYPE["body"][0], first_px(page.problem_view), step)
            for button in [page.map_btn] + list(page.lang_btns.values()):
                self.assertGreaterEqual(button.width(), button.sizeHint().width(), (step, button.text()))
            self.assertEqual(page.result.folded_height(), page.result.height(), step)
            heights[step] = page.result.height()
            self.assertEqual(60, bar.value(), step)
        self.assertLess(heights["normal"], heights["large"])
        self.assertLess(heights["large"], heights["larger"])
        theme.set_mode("dark")
        page.restyle()
        self.assertEqual((18, 17), (page.code_panel.editor.font().pixelSize(), code.font().pixelSize()))

    def test_the_problem_card_stops_at_the_reading_width(self):
        self.addCleanup(theme.set_text, "normal")
        win = self.boot()
        page = self.open("p1")
        piece = next(piece for piece in page.problem_view.pieces if isinstance(piece, TextPiece))
        self.assertEqual(534, piece.width(), "1280×800 의 6:6 칸")
        win.set_text("large")
        win.resize(2000, 1070)
        guikit.pump()
        doc = kit.doc_width(page.width())
        self.assertEqual(848, doc)
        self.assertLessEqual(piece.width(), doc)
        self.assertGreaterEqual(piece.width(), 800)
        self.assertLessEqual(page.problem_card.width(), doc + 62)
        self.assertGreater(page.code_panel.width(), page.problem_card.width(), "남는 폭은 편집기 칸이 받음")

    def test_the_page_never_widens_a_small_window(self):
        """더 크게, 보스, Node 없음, 긴 상태 글에서도 문제 화면의 최소 폭이 1024 이하라 1024 창이 넓어지지 않음."""
        self.addCleanup(theme.set_text, "normal")
        win = self.small([passed("p2")])
        win.set_text("larger")
        with mock.patch.object(win.journey, "runtime", lambda lang: NO_NODE):
            win.settings.setValue("journey/lang", "javascript")
            page = self.open("boss")
        page.set_busy(True, "하던 작업이 끝나면 창을 닫습니다.")
        guikit.pump()
        self.assertTrue(page.node_missing)
        self.assertLessEqual(page.minimumSizeHint().width(), 1024)
        self.assertEqual((1024, 700), (win.width(), win.height()))
        self.assertLessEqual(page.status.height(), 2 * theme.TYPE["caption"][1], "상태 글은 두 줄까지")
        for button in [page.map_btn] + list(page.lang_btns.values()):
            self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
        page.set_busy(False)


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
        self.assertTrue(text.startswith("테스트 3개 중 3개 통과\n[채점하기]로 숨은 테스트까지 채점하세요."), text)
        for line in ("테스트 1", "입력값 〉 [3, 9, 4]", "기댓값 〉 9", "실행 결과 〉 테스트를 통과하였습니다.", "출력 〉", "찍음", "실행 환경 Python"):
            self.assertIn(line, text)
        self.assertNotIn("테스트 결과 3개 중 3개 성공", text, "요약 줄은 머리가 말함")
        self.assertNotIn("안에 끝나야 합니다", text, "시간 제한은 지문 머리에 있음")
        self.assertIn("시간 제한 2초", page.facts.text())
        self.assertRegex(text, r"시간·메모리 〉 \d+\.\d\dms, \d+\.\dMB")
        self.assertEqual([], self.read_log())
        self.assertTrue(page.run_btn.isEnabled())
        self.assertTrue(page.stop_btn.isHidden(), "[중지]는 도는 동안에만 보임")
        page.load("t01", "p1")
        self.assertTrue(page.result.collapsed, "결과가 없는 문제는 접힌 채 열림")
        page.load("t01", "p2")
        self.assertFalse(page.result.collapsed, "기억한 결과가 있는 문제는 펼친 채 열림")
        self.assertTrue(self.console().startswith("테스트 3개 중 3개 통과"), "결과는 (문제, 언어)마다 기억함")

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
        self.assertRegex(text, r"^100점 중 \d+(\.\d)?점\n정확성 [\d.]+ / 80 · 효율성 [\d.]+ / 20\n")
        self.assertIn(journey_html.HIDDEN_NOTE, text, "숨은 테스트가 틀리면 본문 끝에 안내")
        self.assertNotIn("100점 중 100점", text)
        self.assertNotIn("합계", text, "요약 줄은 머리가 말함")
        self.assertEqual(1, len(self.read_log()))
        self.type_code(MAX_SOLUTION)
        guikit.click(page.grade_btn)
        text = self.console()
        self.assertTrue(text.startswith("100점 중 100점\n정확성 80 / 80 · 효율성 20 / 20"), text)
        self.assertIn("처음으로 통과했습니다. 해설이 열렸습니다.", text)
        self.assertIn("보스 문제가 열렸습니다.", text)
        self.assertTrue(page.give_up_btn.isHidden())
        self.assertIn("기준 풀이 (Python)", doc_text(page.explain_view))
        explain, boss = [banner.action for banner in page.result.banners.findChildren(QFrame, "banner")]
        self.assertEqual(("해설 보기", "보스 풀기"), (explain.text(), boss.text()))
        guikit.click(explain)
        self.assertEqual(2, page.tabs.currentIndex())
        guikit.click(boss)
        self.assertEqual("boss", page.pid)
        self.assertIs(win.pages.currentWidget(), page)

    def test_stop_during_grading_keeps_no_record(self):
        win = self.boot()
        page = self.open("p2")
        self.type_code(MAX_SOLUTION)
        seen = []

        def progress(event, original=page.on_progress):
            if event.get("kind") == "case" and not seen:
                seen.append((page.stop_btn.isEnabled(), page.run_btn.isEnabled(), page.code_panel.editor.isEnabled()))
                guikit.click(page.stop_btn)
            original(event)

        with mock.patch.object(page, "on_progress", progress):
            guikit.click(page.grade_btn)
        self.assertEqual([(True, False, False)], seen)
        self.assertTrue(self.console().startswith("채점을 멈췄습니다\n이번 채점은 기록에 남지 않습니다."), self.console())
        self.assertEqual([], self.read_log())
        self.assertIsNone(win.job)

    def test_first_boss_pass_announces_the_clear(self):
        win = self.boot([passed("p2")])
        page = self.open("boss")
        self.type_code(BOSS_SOLUTION)
        guikit.click(page.grade_btn)
        self.assertTrue(self.console().startswith("100점 중 100점"))
        self.assertEqual("던전 클리어", win.dialog.windowTitle())
        self.assertEqual("「시험 마을」 던전을 클리어했습니다. 준비된 던전을 모두 클리어했습니다.", win.dialog.text.text())
        self.assertEqual([("ok", "확인", "primary")], button_line(win.dialog))

    def test_the_clear_window_opens_the_next_dungeon_on_the_map(self):
        win = self.boot([passed("p2")])
        page = self.open("boss")
        overview = win.journey.overview()
        overview["next"] = {"did": "t03", "pid": "p1", "title": "첫 문제", "role": "basic"}
        with mock.patch.object(win.journey, "overview", return_value=overview):
            page.celebrate()
        self.assertEqual("「시험 마을」 던전을 클리어했습니다. 다음은 「준비 중 던전 3」 던전입니다.", win.dialog.text.text())
        self.assertEqual([("", "닫기", ""), ("next", "다음 던전 보기", "primary")], button_line(win.dialog))
        self.choose("next")
        self.assertIs(win.pages.currentWidget(), win.journey_map)
        self.assertEqual("t03", win.journey_map.view.selected)
        overview["next"] = {"did": "t01", "pid": "p3", "title": "선택 문제", "role": "side"}
        self.open("boss")
        with mock.patch.object(win.journey, "overview", return_value=overview):
            page.celebrate()
        self.assertIn("준비된 던전을 모두 클리어했습니다.", win.dialog.text.text(), "방금 클리어한 던전을 다음 던전으로 알리지 않음")


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
        self.assertTrue(text.startswith("테스트 3개 중 3개 통과"))
        self.assertIn("출력 〉", text)
        guikit.click(page.grade_btn)
        text = self.console()
        self.assertTrue(text.startswith("100점 중 100점"))
        self.assertIn("실행 환경 Node.js %s" % NODE["version"], text)
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
            self.assertEqual([("pick", "직접 고르기", ""), ("", "닫기", ""), ("find", "다시 찾기", "primary")], button_line(win.dialog))
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
        self.assertEqual(NODE_TITLE, win.dialog.windowTitle(), "못 찾으면 같은 창을 다시 띄워 [직접 고르기]로 이어 감")
        self.assertEqual("%s %s" % (NODE_MISSING, NODE_TEXT), win.dialog.text.text())
        self.assertEqual("python", page.lang)

    def test_node_window_links_the_download_page_and_explains_a_wrong_pick(self):
        win = self.boot()
        page = win.journey_map
        win.pick_result = "/usr/bin/node18"
        problem = "Node.js 20 이상이 필요한데 이 파일은 v18.19.0 입니다."
        with mock.patch.object(win.journey, "runtime", lambda lang: NO_NODE), \
                mock.patch.object(win.journey, "set_node", side_effect=JourneyError(problem)):
            guikit.click(page.lang_btns["javascript"])
            self.assertEqual(NODE_TEXT, win.dialog.text.text())
            self.assertNotIn("http", NODE_TEXT, "주소는 본문 아래 누르는 글자로만 보임")
            self.assertIn(NODE_LINK, win.dialog.link.text())
            win.dialog.link.linkActivated.emit(NODE_LINK)
            self.assertEqual([NODE_LINK], win.opened)
            right = win.dialog.buttons["find"].mapTo(win.dialog, win.dialog.buttons["find"].rect().topRight()).x()
            self.assertEqual(win.dialog.width() - 1 - 32, right, "주 단추가 창 안쪽 오른쪽 끝")
            self.assertFalse(any(button.isDefault() for button in win.dialog.buttons.values()), "단추가 셋이라 Enter 로 넘어가지 않음")
            self.choose("pick")
        self.assertEqual(NODE_TITLE, win.dialog.windowTitle())
        self.assertEqual("%s %s" % (problem, NODE_TEXT), win.dialog.text.text())
        self.assertIsNone(win.settings.value("journey/node"), "쓸 수 없는 파일은 기억하지 않음")
        self.assertEqual("python", page.lang_bar.lang)

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
            self.assertIs(JAVASCRIPT, problem.code_panel.editor.lang)


class HintExplainTest(Base):
    def test_hints_open_in_order(self):
        self.boot()
        page = self.open("p1")
        self.assertEqual("힌트 0/3", page.tabs.tabText(1))
        self.assertEqual("힌트 1 보기", page.hint_btn.text())
        self.assertEqual(journey_text.HINT_INTRO, doc_text(page.hint_view))
        self.assertEqual("힌트는 한 단계씩 열립니다. 연 힌트는 기록에 남습니다.", journey_text.HINT_INTRO)
        self.assertEqual(("", True), (page.hint_note.text(), page.hint_note.isHidden()))
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
        self.assertEqual(("힌트를 모두 열었습니다.", False), (page.hint_note.text(), page.hint_note.isHidden()))
        self.assertEqual([1, 2, 3], [entry["level"] for entry in self.read_log() if entry["kind"] == "hint"])

    def test_giving_up_opens_the_explanation_with_parts_solution_and_similar(self):
        win = self.boot([passed("p2")])
        page = self.open("boss")
        page.tabs.setCurrentIndex(2)
        self.assertIn("이 문제를 통과하면 해설이 열립니다.", doc_text(page.explain_view))
        guikit.click(page.give_up_btn)
        self.assertEqual((GIVE_UP_TITLE, GIVE_UP_TEXT), (win.dialog.windowTitle(), win.dialog.text.text()))
        self.assertEqual([("", "닫기", ""), ("open", "해설 열기", "danger")], button_line(win.dialog))
        self.choose("")
        self.assertFalse(page.give_up_btn.isHidden())
        self.assertNotIn("explain", [entry["kind"] for entry in self.read_log()])
        guikit.click(page.give_up_btn)
        self.choose("open")
        self.assertTrue(page.give_up_btn.isHidden())
        text = doc_text(page.explain_view)
        for line in ("느린 풀이", "보스에 쓰인 기술", "배열을 한 번 훑으며 값을 더함", "큰 값부터 고름", "기준 풀이 (Python)", "더 풀어 볼 문제",
                     "프로그래머스 · K번째수", "백준 2750 · 수 정렬하기"):
            self.assertIn(line, text)
        self.assertLess(text.index("느린 풀이"), text.index("보스에 쓰인 기술"))
        self.assertLess(text.index("보스에 쓰인 기술"), text.index("기준 풀이"))
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
        self.assertEqual("1번 줄의 return 칸: 문자열이 아닙니다: 3", dialog.error.text())
        self.assertTrue(dialog.error.isVisible())
        self.assertEqual(("danger", None), (edits[1].property("tone"), edits[0].property("tone")))
        edits[1].setText("[1,")
        self.assertIn("1번 줄의 return 칸: 값을 읽지 못했습니다.", dialog.error.text())
        edits[0].setFocus()
        guikit.click(dialog.save_btn)
        self.assertTrue(dialog.isVisible())
        self.assertTrue(edits[1].hasFocus(), "[저장]이 틀린 칸으로 초점을 옮김")
        self.assertEqual("[1,", edits[1].text(), "쓴 값은 지우지 않음")
        self.assertEqual(theme.color("wrong"), edge_ink(edits[1]), "초점이 있어도 틀린 칸은 빨간 테두리")
        edits[1].setText("'cba'")
        self.assertEqual("", dialog.error.text())
        self.assertFalse(dialog.error.isVisible())
        self.assertIsNone(edits[1].property("tone"))
        self.assertNotEqual(theme.color("wrong"), edge_ink(edits[1]))
        guikit.click(dialog.add_btn)
        guikit.click(dialog.add_btn)
        self.assertEqual(3, len(dialog.rows))
        dialog.rows[1][0][0].setText("1")
        self.assertEqual("2번 줄의 name 칸: 문자열이 아닙니다: 1", dialog.error.text())
        guikit.click(dialog.rows[1][1])
        self.assertEqual(2, len(dialog.rows))
        self.assertEqual("", dialog.error.text())
        guikit.click(dialog.save_btn)
        self.assertFalse(dialog.isVisible())
        self.assertEqual([{"args": ["abc"], "expected": "cba"}], page.data["cases"])
        saved = study.read_json(os.path.join(study.SUBMISSIONS_DIR, "alice", "journey", "t01", "p3.cases.json"))
        self.assertEqual([{"args": ["abc"], "expected": "cba"}], saved["cases"])
        self.assertEqual("내 테스트 1개를 저장했습니다.", page.status.text())
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

    def test_dialog_uses_the_new_parts_and_follows_the_text_steps(self):
        self.addCleanup(theme.set_text, "normal")
        win = self.boot()
        page = self.open("p3")
        guikit.click(page.cases_btn)
        dialog = page.cases_dialog
        guikit.pump()
        self.assertEqual("2", dialog.property("ui"), "부모와 상관없이 창 자신에 새 규칙을 걸음")
        self.assertEqual((760, 520), (dialog.width(), dialog.height()))
        self.assertEqual(TITLE, dialog.windowTitle())
        texts = [label.text() for label in dialog.findChildren(Para)]
        self.assertEqual([TITLE, HINT], texts[:2])
        self.assertEqual("값은 파이썬이나 JSON 문법으로 적으세요. 예: [\"a\", \"b\"], 3, True", HINT)
        close = next(button for button in dialog.findChildren(QPushButton) if button.text() == "닫기")
        self.assertEqual("줄 추가", dialog.add_btn.text())
        self.assertEqual([dialog.save_btn], kit.visible_primary_buttons(dialog))
        self.assertFalse(any(button.isDefault() or button.autoDefault() for button in dialog.findChildren(QPushButton)),
                         "입력칸에서 Enter 를 눌러도 저장하지 않음")
        edits, remove = dialog.rows[0]
        for step in ("normal", "large"):
            win.set_text(step)
            guikit.pump()
            self.assertEqual(theme.TYPE["code"][0], edits[0].font().pixelSize(), step)
            heights = [button.height() for button in (dialog.save_btn, close, dialog.add_btn, dialog.example_btn, remove)]
            self.assertEqual([48, 48, 40, 40, 32], heights, step)
            self.assertEqual(48, edits[0].height(), step)
            self.assertEqual("삭제", remove.text())
            self.assertEqual(("primary", "", "text", "text", "danger_text"),
                             tuple(button.objectName() for button in (dialog.save_btn, close, dialog.add_btn, dialog.example_btn, remove)))
            right = dialog.save_btn.mapTo(dialog, dialog.save_btn.rect().topRight()).x()
            self.assertEqual(dialog.width() - 1 - 32, right, step)
        guikit.click(dialog.add_btn)
        self.assertEqual(theme.TYPE["code"][0], dialog.rows[1][0][0].font().pixelSize(), "새 줄도 지금 단계의 코드 글꼴")
        self.assertEqual(17, theme.TYPE["code"][0])


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
        page.expand_result()
        page.result.show_result("grade", {"groups": [], "score": 100.0, "runtime": "Python 3.14.4"})
        page.tabs.setCurrentIndex(0)
        guikit.pump(60)
        self.assertEqual(0, bright_share(win))
        theme.set_mode("light")
        win.journey_page.restyle()
        guikit.pump(60)
        self.assertGreater(bright_share(win), 0.3)

    def test_first_problem_and_its_windows_have_no_bright_area(self):
        """설계 10.1-17 의 나머지 상태: 결과 전에 접힌 문제 화면, 테스트 추가 창, 해설 그림 창."""
        mode = theme.state["mode"]
        self.addCleanup(theme.set_mode, mode)
        theme.set_mode("dark")
        self.boot([passed("p1")])
        page = self.open("p2")
        guikit.pump(60)
        self.assertTrue(page.result.collapsed)
        self.assertEqual(0, bright_share(self.win))
        guikit.click(page.cases_btn)
        guikit.pump(60)
        self.assertEqual(0, bright_share(page.cases_dialog))
        page.cases_dialog.close()
        page = self.open("p1")
        page.tabs.setCurrentIndex(2)
        figure = next(piece for piece in page.explain_view.pieces if isinstance(piece, FigureView))
        figure.open_dialog()
        guikit.pump(60)
        self.assertEqual(0, bright_share(figure.dialog))
        figure.dialog.close()


if __name__ == "__main__":
    unittest.main()
