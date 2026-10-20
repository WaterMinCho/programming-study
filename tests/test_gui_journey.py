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
from PyQt6.QtWidgets import QMainWindow, QStackedWidget  # noqa: E402

import adaptive  # noqa: E402
import study  # noqa: E402
from gui import journey_html, theme  # noqa: E402
from gui.dialogs import MessageDialog  # noqa: E402
from gui.docview import CodeView, TextPiece  # noqa: E402
from gui.editor import JAVASCRIPT, PYTHON  # noqa: E402
from gui.guard import Guard  # noqa: E402
from gui.journey_map import CLEAR_TEXT, JourneyMapPage, MapView  # noqa: E402
from gui.journey_page import GIVE_UP_TEXT, NODE_TITLE, JourneyPage  # noqa: E402
from gui.round_page import RoundPage  # noqa: E402
from journey import bank, node, runner, values  # noqa: E402
from journey.service import JourneySession  # noqa: E402
from session import SessionError  # noqa: E402

FIXTURE = os.path.join(guikit.ROOT, "tests", "journey_bank")
LEAN = bool(os.environ.get("STUDY_LEAN_CI"))
SKIP_LEAN = unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
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
        self.zoom, self.dialog, self.job = 0, None, None
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


class MapTest(Base):
    def test_sixteen_nodes_and_picking_one_shows_its_detail(self):
        win = self.boot()
        page = win.journey_map
        self.assertEqual(16, len(page.view.nodes()))
        self.assertEqual("t01", page.view.selected)
        self.assertIn("던전 1 · 합·최댓값 「시험 마을」", page.title.text())
        self.assertEqual("통과 0/4", page.passed.text())
        self.assertTrue(page.notice.isVisible())
        self.assertIn("t02", page.notice.text())
        nodes = dict(page.view.nodes())
        QTest.mouseClick(page.view, guikit.LEFT, pos=nodes["t03"].center().toPoint())
        guikit.pump()
        self.assertEqual("t03", page.view.selected)
        self.assertIn("던전 3 · 주제 3 「준비 중 던전 3」", page.title.text())
        self.assertIn("아직 출제되지 않은 던전입니다.", doc_text(page.intro))
        self.assertFalse(page.listw.isVisible())
        self.assertEqual("faint", MapView.state(page.view.rows[2]))
        QTest.mouseClick(page.view, guikit.LEFT, pos=nodes["t02"].center().toPoint())
        guikit.pump()
        self.assertIn("이 던전을 읽을 수 없습니다.", doc_text(page.intro))
        QTest.mouseClick(page.view, guikit.LEFT, pos=nodes["t01"].center().toPoint())
        guikit.pump()
        self.assertTrue(page.listw.isVisible())
        self.assertIn("물통에 담긴 물의 양을 더하고", doc_text(page.intro))
        self.assertEqual("익히는 기술: 배열 합, 최댓값 찾기, 문자열 뒤집기", page.skills.text())
        rows = [page.listw.item(n) for n in range(page.listw.count())]
        self.assertEqual(["1-1 기초 · 물통 합계", "1-2 중급 · 가장 큰 물통", "1-3 선택 · 이름 뒤집기", "1-B 보스 · 물통 정리"],
                         [row.text().split("\n")[0] for row in rows])
        self.assertIn("준비 문제 1-1", rows[1].text())
        boss = rows[3]
        self.assertFalse(boss.flags() & Qt.ItemFlag.ItemIsEnabled)
        self.assertEqual("중급 문제를 모두 통과하면 열립니다(1개 중 0개 통과).", boss.toolTip())
        self.assertIn("잠김 · 중급 1개 중 0개 통과", boss.text())
        self.assertTrue(boss.font().bold())
        self.assertFalse(page.boss_new.isVisible())

    def test_solve_button_opens_the_selected_problem(self):
        win = self.boot()
        page = win.journey_map
        page.listw.setCurrentRow(1)
        guikit.click(page.solve_btn)
        self.assertIs(win.pages.currentWidget(), win.journey_page)
        self.assertEqual("1-2 · 중급 · 가장 큰 물통", win.journey_page.title.text())
        guikit.click(win.journey_page.map_btn)
        self.assertIs(win.pages.currentWidget(), page)
        win.open_problem("t01", "boss")
        self.assertIn("중급 문제를 모두 통과하면 열립니다", win.dialog.text.text())

    def test_boss_skill_line_shows_only_after_the_boss_is_passed(self):
        win = self.boot([passed("p2"), passed("p1", "javascript"), {"at": adaptive.now(), "kind": "grade", "item": "t01/p3",
                                                                    "lang": "python", "score": 40.0, "passed": False}])
        page = win.journey_map
        rows = [page.listw.item(n).text() for n in range(page.listw.count())]
        self.assertIn("통과 (JavaScript)", rows[0])
        self.assertIn("최고 40.0점", rows[2])
        self.assertTrue(page.listw.item(3).flags() & Qt.ItemFlag.ItemIsEnabled)
        self.assertFalse(page.boss_new.isVisible())
        self.assertEqual("primary", MapView.state(page.view.rows[0]))
        self.write_log(self.read_log() + [passed("boss")])
        win.journey = JourneySession("alice")  # 기록을 밖에서 고쳤으므로 창이 [문제 받기] 뒤처럼 서비스를 새로 만듦
        page.refresh()
        guikit.pump()
        self.assertTrue(page.boss_new.isVisible())
        self.assertEqual("보스에서 익힌 기술: 정렬한 뒤 앞에서 k개를 골라 더함", page.boss_new.text())
        self.assertEqual("ok", MapView.state(page.view.rows[0]))
        self.assertEqual("통과 3/4", page.passed.text())

    def test_cache_line_and_clear_button(self):
        os.makedirs(runner.CACHE_DIR)
        with open(os.path.join(runner.CACHE_DIR, "a" * 64 + ".json"), "wb") as handle:
            handle.write(b"0" * (3 * 1024 * 1024))
        win = self.boot()
        page = win.journey_map
        self.assertEqual("생성 입력 캐시 3MB", page.cache.text())
        guikit.click(page.clear_cache_btn)
        self.assertEqual(CLEAR_TEXT, win.dialog.text.text())
        self.choose("clear")
        self.assertEqual("생성 입력 캐시 0MB", page.cache.text())
        self.assertEqual([], os.listdir(runner.CACHE_DIR))

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
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE):
            guikit.click(page.lang_btns["javascript"])
            self.assertEqual("javascript", page.lang)
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
        self.assertFalse(win.journey_map.lang_bar.note.isVisible())
        with mock.patch.object(win.journey, "runtime", return_value=NO_NODE):
            win.journey_map.refresh()
            self.assertEqual("python", win.journey_map.lang_bar.lang)
            self.assertTrue(win.journey_map.lang_bar.note.isVisible())
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
        guikit.click(page.hint_btn)
        self.assertEqual("힌트 1/3", page.tabs.tabText(1))
        self.assertIn("한 변수에 모아 두세요", doc_text(page.hint_view))
        self.assertNotIn("변수를 0으로 시작하고", doc_text(page.hint_view))
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
