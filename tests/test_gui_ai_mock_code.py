# -*- coding: utf-8 -*-
"""모의고사 코드 작성 문항의 칸, 배치, [코드 실행], 작업 스레드 채점을 임시 은행으로 확인함."""
import json
import math
import os
import shutil
import threading
from pathlib import Path
from unittest import mock

from tests.test_gui_ai import AI_FIXTURE, AiTest, visible_text  # PyQt6 가 없으면 여기서 모듈 전체를 건너뜀
from PyQt6.QtCore import QMimeData, QPointF, Qt, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QBoxLayout, QLabel, QWidget

from aiprep import bank, mock_code
from gui import ai_mock, theme
from gui.ai_learn import CodeSlots, Slot
from tests import guikit
from aiprep.mock import ENV_FAILED
from gui.widgets import content_height
from tests.test_ai_mock import RIGHT, code_item, env_grade
import study

MINE = ["result = a + b", "return result"]
HIDDEN = ("40017", "50013", "total = a + b")  # 숨은 테스트 값과 모범 답안 줄


def stuck_grade(item, lines, workers=None):
    return {"result": "stuck", "passed": 1, "total": 2, "reason": "숨은 테스트 2번: 돌려준 값이 다릅니다.", "cases": []}


def example_run(starter, entry, examples, lines, limit_ms=None, tol=None, workers=None):
    cases = [{"status": "pass", "reason": "", "args": e["args"], "expected": e["expected"], "actual": e["expected"],
              "printed": "", "error": "", "note": ""} for e in examples]
    return {"result": "pass", "passed": len(cases), "total": len(cases), "reason": "", "cases": cases}


class Gate:
    """작업 스레드에서 불리면 풀어 줄 때까지 붙잡는 가짜. 불린 스레드와 받은 줄을 남김."""

    def __init__(self, reply):
        self.reply, self.calls = reply, []
        self.started, self.release = threading.Event(), threading.Event()

    def __call__(self, *args, **kwargs):
        self.calls.append((threading.current_thread(), args))
        self.started.set()
        self.release.wait(10)
        return self.reply(*args, **kwargs)


def all_text(page):
    """화면의 보이는 글, 실행 결과 html, 툴팁, 접근성 이름을 모두 이음."""
    parts = [visible_text(page)]
    for child in page.findChildren(QWidget):
        parts += [child.toolTip(), child.accessibleName()]
    if page.console is not None:
        parts.append(page.console.toHtml())
    return "\n".join(parts)


class MockCodeTest(AiTest):
    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, "mock_bank")
        shutil.copytree(AI_FIXTURE, self.root)
        index_path = os.path.join(self.root, "index.json")
        index = study.read_json(index_path)
        index["mocks"][0]["count"] = 3
        study.write_text(index_path, json.dumps(index, ensure_ascii=False))
        folder = Path(self.root) / "mocks/m90"
        (folder / "work").mkdir(parents=True)
        (folder / "meta.json").write_text("{}", encoding="utf-8")
        items = [{"id": "m90-%02d" % n, "kind": "blank", "lesson": "i90", "unit": "90a", "step": "90a/1",
                  "stem": "숫자를 쓰세요: ____", "blanks": [{"answer": ["3"], "mode": "number"}], "explain": "해설입니다."}
                 for n in (1, 2)]
        items.append(code_item("m90-03", "i90"))
        (folder / "work/items.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
        patcher = mock.patch.object(bank, "AI_DIR", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        theme.set_text("normal")
        self.addCleanup(theme.set_text, theme.state["text"])

    def open_code(self, size=(1280, 800)):
        win = self.boot(size)
        self.assertTrue(win.open_ai_mock("m90"))
        win.ai_mock.begin()
        self.idle()
        page = win.ai_mock
        page.timer.stop()  # 시계 tick 은 테스트가 직접 부름
        page.go(page.exam.draft["order"].index("m90-03"))
        self.idle()
        return page

    def type_answer(self, page, lines=MINE):
        for field, text in zip(page.inputs, lines):
            field.setFocus()
            QTest.keyClicks(field, text)
        self.assertTrue(page.persist())

    def expire(self):
        self.clock = "2026-11-04T21:01:00"

    def test_only_fill_lines_take_input_and_paste_copy_are_blocked(self):
        page = self.open_code()
        slots = page.card.findChild(CodeSlots)
        self.assertEqual(2, mock_code.fill_count(page.item["starter"]))
        self.assertEqual(slots.fields, page.inputs)
        self.assertTrue(all(isinstance(field, Slot) for field in page.inputs))
        self.assertEqual(["채울 줄 1", "채울 줄 2"], [field.accessibleName() for field in page.inputs])
        self.assertIn("def add(a, b):", [label.text() for label in slots.inner.findChildren(QLabel)])
        self.assertIn(">>> add(10, 20)", visible_text(page))  # 공개 예시는 지문 아래에 보임
        self.assertIn(ai_mock.CODE_GUIDE, visible_text(page))
        self.assertTrue(page.run_btn.isVisible())
        self.type_answer(page)
        self.assertEqual(MINE, page.exam.draft["answers"]["m90-03"])
        field = page.inputs[0]
        QApplication.clipboard().setText("붙인 글")
        field.setFocus()
        field.setCursorPosition(3)
        page.notice.hide()
        QTest.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(MINE[0], field.text())
        self.assertTrue(page.notice.isVisible())
        self.assertIn("붙여넣기를 막았습니다", page.notice.text.text())
        self.assertIs(QApplication.focusWidget(), field)
        self.assertEqual(3, field.cursorPosition())
        QTest.mouseClick(field, Qt.MouseButton.MiddleButton)
        data = QMimeData()
        data.setText("끌어 온 글")
        point = QPointF(field.width() / 2, field.height() / 2)
        QApplication.sendEvent(field, QDragEnterEvent(point.toPoint(), Qt.DropAction.CopyAction, data,
                                                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        QApplication.sendEvent(field, QDropEvent(point, Qt.DropAction.CopyAction, data, Qt.MouseButton.LeftButton,
                                                 Qt.KeyboardModifier.NoModifier))
        self.assertEqual(MINE[0], field.text())
        field.selectAll()
        for key in (Qt.Key.Key_C, Qt.Key.Key_X):
            QTest.keyClick(field, key, Qt.KeyboardModifier.ControlModifier)
        field.cut()
        self.assertEqual(("붙인 글", MINE[0]), (QApplication.clipboard().text(), field.text()))
        QTest.keyClick(page.inputs[0], Qt.Key.Key_Tab)
        self.assertIs(QApplication.focusWidget(), page.inputs[1])  # 칸 사이는 Tab 으로 옮겨 감
        text = all_text(page)
        for hidden in HIDDEN:
            self.assertNotIn(hidden, text)

    def test_answers_survive_moving_tabs_text_size_and_theme(self):
        page = self.open_code()
        self.type_answer(page)
        page.go(0)
        page.go(page.exam.draft["order"].index("m90-03"))
        self.assertEqual(MINE, [field.text() for field in page.inputs])
        self.win.go_ai()
        self.idle()
        self.win.select_ai_tab("mock")
        self.idle()
        self.assertTrue(self.win.open_ai_mock("m90"))
        self.idle()
        page.timer.stop()
        self.assertEqual("m90-03", page.item["card"])
        self.assertEqual(MINE, [field.text() for field in page.inputs])
        fields = list(page.inputs)
        for mode, size in (("dark", "larger"), ("light", "normal")):
            theme.set_mode(mode)
            self.win.set_text(size)
            self.idle()
            self.assertEqual(fields, page.inputs)
            self.assertEqual(MINE, [field.text() for field in page.inputs])

    def test_code_item_is_one_column_at_every_size(self):
        """코드 작성 문항은 창 크기와 글자 크기와 상관없이 지문, 코드, 실행 결과를 차례로 한 열에 두고, 코드와 실행 결과를 담은 칸이 문항 폭을 다 씀.
        테스트를 760x480 창에서 끝내야 Windows 배율 1.5 캡처가 작업 영역 안에 듦."""
        page = self.open_code((760, 480))
        self.assertEqual(QBoxLayout.Direction.TopToBottom, page.split.layout().direction())
        for size in ((1024, 700), (1280, 800), (760, 480)):
            self.win.resize(*size)
            for step in ("normal", "larger"):
                self.win.set_text(step)
                self.idle()
                self.assertEqual(QBoxLayout.Direction.TopToBottom, page.split.layout().direction(), (size, step))
                self.assertEqual(page.split.width(), page.split.layout().itemAt(1).widget().width(), (size, step))

    def test_resize_and_run_keep_answers_cursor_and_result(self):
        page = self.open_code((1280, 800))
        self.type_answer(page)
        page.inputs[1].setFocus()
        page.inputs[1].setCursorPosition(4)
        record = Path(self.win.ai.record.path).read_bytes()
        gate, ticks = Gate(example_run), []
        with mock.patch.object(mock_code, "try_code", side_effect=gate):
            page.run_btn.click()
            self.assertTrue(gate.started.wait(10))
            QTimer.singleShot(0, lambda: ticks.append(1))
            guikit.pump()
            self.assertEqual([1], ticks)  # 실행하는 동안 이벤트 루프가 돎
            self.assertTrue(page.busy)
            self.assertTrue(page.busy_note.isVisible())
            self.assertFalse(page.run_btn.isEnabled())
            gate.release.set()
            self.idle()
        self.assertIsNot(threading.main_thread(), gate.calls[0][0])
        self.assertEqual(MINE, gate.calls[0][1][3])
        self.assertIn("예시 2개 중 2개 통과", page.console.toPlainText())
        self.assertIn("add(1, 2)", page.console.toPlainText())
        self.assertEqual(record, Path(self.win.ai.record.path).read_bytes())
        result, fields = page.console.html, list(page.inputs)
        line = page.console.fontMetrics().lineSpacing()
        for size in ((1024, 700), (900, 700), (1280, 800), (760, 480)):  # 테스트를 760x480 창에서 끝내야 Windows 배율 1.5 캡처가 작업 영역 안에 듦
            self.win.resize(*size)
            self.idle()
            shown, need = page.console.viewport().height(), math.ceil(content_height(page.console.document()))
            self.assertGreaterEqual(shown, need, size)  # 실행 결과가 잘리지 않음
            self.assertLessEqual(shown - need, line, size)  # 빈 틈이 한 줄을 넘지 않음
            self.assertEqual(fields, page.inputs)
            self.assertEqual(MINE, [field.text() for field in page.inputs])
            self.assertEqual(4, page.inputs[1].cursorPosition())
            self.assertEqual(result, page.console.html)
        theme.set_mode("dark")
        self.addCleanup(theme.set_mode, "light")
        self.win.set_text("larger")
        self.idle()
        self.assertEqual(result, page.console.html)
        self.assertGreaterEqual(page.console.viewport().height(), math.ceil(content_height(page.console.document())))

    def test_submit_is_graded_on_a_worker_and_shows_the_model_answer(self):
        page = self.open_code()
        self.type_answer(page)
        gate, ticks = Gate(lambda item, lines, workers=None: {"result": "pass", "passed": 2, "total": 2, "reason": "", "cases": []}), []
        with mock.patch.object(mock_code, "grade", side_effect=gate), \
                mock.patch.object(self.win.auto_submission, "request") as checkpoint:
            page.submit()
            self.assertTrue(gate.started.wait(10))
            QTimer.singleShot(0, lambda: ticks.append(1))
            guikit.pump()
            self.assertEqual([1], ticks)
            self.assertTrue(page.busy)
            self.assertFalse(page.card.isEnabled())
            self.assertIn(ai_mock.GRADING, page.busy_note.text.text())
            self.assertEqual([], self.log("mock_submit"))
            gate.release.set()
            self.idle()
            checkpoint.assert_called_once()
        self.assertIsNot(threading.main_thread(), gate.calls[0][0])
        self.assertEqual(1, len(self.log("mock_submit")))
        self.assertFalse(page.busy_note.isVisible())
        text = visible_text(page)
        self.assertIn("채점에 쓴 숨은 테스트 2개 중 2개 통과", text)
        self.assertIn("모범 답안", text)
        self.assertIn(RIGHT[0], text)
        self.assertFalse(page.run_btn.isVisible())
        self.assertTrue(all(field.isReadOnly() for field in page.inputs))
        for hidden in ("40017", "50013"):
            self.assertNotIn(hidden, all_text(page))

    def test_environment_failure_on_submit_shows_the_notice_band(self):
        page = self.open_code()
        self.type_answer(page)
        with mock.patch.object(mock_code, "grade", side_effect=env_grade), \
                mock.patch.object(self.win, "ask") as ask:
            page.submit()
            self.idle()
        ask.assert_not_called()
        self.assertTrue(page.notice.isVisible())
        self.assertEqual(ENV_FAILED, page.notice.text.text())
        self.assertIsNone(page.exam.result)
        self.assertEqual("m90-03", page.item["card"])
        self.assertEqual([], self.log("mock_submit"))

    def test_other_job_shows_the_wait_note_instead_of_the_error_band(self):
        """다른 작업이 돌고 있어 [코드 실행]이나 제출을 시작하지 못하면 '안내' 띠에 JOB_BUSY 를 띄우고 오류 띠는 쓰지 않음.
        같은 단추를 다시 눌러 실행이 끝나면 안내 띠가 사라짐."""
        page = self.open_code()
        self.type_answer(page)
        self.win.job = object()  # 다른 화면이 시작한 작업이 도는 중
        try:
            for start in (page.run_btn.click, page.submit):
                page.busy_note.hide()
                start()
                self.assertTrue(page.busy_note.isVisible())
                self.assertEqual(("안내", ai_mock.JOB_BUSY), (page.busy_note.word.text(), page.busy_note.text.text()))
                self.assertFalse(page.notice.isVisible())
        finally:
            self.win.job = None
        self.assertIsNone(page.exam.result)
        with mock.patch.object(mock_code, "try_code", side_effect=example_run):
            page.run_btn.click()
            self.idle()
        self.assertFalse(page.busy_note.isVisible())
        self.assertIn("add(1, 2)", page.console.toPlainText())

    def test_wait_note_goes_away_after_the_other_job_ends(self):
        """다른 작업이 끝난 뒤 [코드 실행]을 다시 누르지 않아도 답을 저장하거나 다른 문항으로 옮기면 안내 띠가 사라짐."""
        page = self.open_code()
        self.type_answer(page)
        self.win.job = object()
        page.run_btn.click()
        self.assertTrue(page.busy_note.isVisible())
        self.win.job = None
        self.type_answer(page, ["", " "])
        self.assertFalse(page.busy_note.isVisible())
        self.win.job = object()
        page.run_btn.click()
        self.assertTrue(page.busy_note.isVisible())
        self.win.job = None
        page.go(page.exam.draft["order"].index("m90-02"))
        self.idle()
        self.assertEqual("blank", page.item["kind"])
        self.assertFalse(page.busy_note.isVisible())

    def test_error_band_goes_away_when_a_later_submit_is_graded(self):
        page = self.open_code()
        self.type_answer(page)
        with mock.patch.object(mock_code, "grade", side_effect=env_grade):
            page.submit()
            self.idle()
        self.assertTrue(page.notice.isVisible())
        with mock.patch.object(mock_code, "grade", side_effect=stuck_grade):
            page.submit()
            self.idle()
        self.assertIsNotNone(page.exam.result)
        self.assertFalse(page.notice.isVisible())
        self.assertEqual("제출 완료", page.time.text())

    def test_third_environment_failure_on_submit_leaves_no_error_band(self):
        """[제출]을 세 번 눌러 세 번째 실행 환경 실패에서 회차가 ungraded 결과로 제출되면, 앞의 두 번에 띄운 오류 띠가 결과 화면에 남지 않음."""
        page = self.open_code()
        self.type_answer(page)
        with mock.patch.object(mock_code, "grade", side_effect=env_grade):
            for _ in range(2):
                page.submit()
                self.idle()
                self.assertIsNone(page.exam.result)
                self.assertTrue(page.notice.isVisible())
            page.submit()
            self.idle()
        self.assertEqual("ungraded", page.exam.result["results"]["m90-03"])
        self.assertFalse(page.notice.isVisible())
        self.assertEqual("제출 완료", page.time.text())

    def test_run_after_the_deadline_only_starts_grading(self):
        page = self.open_code()
        self.type_answer(page)
        self.expire()
        grader = Gate(stuck_grade)
        with mock.patch.object(mock_code, "grade", side_effect=grader), \
                mock.patch.object(mock_code, "try_code") as tried:
            page.dirty = True
            page.run_code()
            self.assertTrue(grader.started.wait(10))
            self.assertTrue(page.grading)
            self.assertNotEqual(ai_mock.JOB_BUSY, page.busy_note.text.text())
            grader.release.set()
            self.idle()
        tried.assert_not_called()
        self.assertTrue(page.exam.result["auto"])

    def test_back_and_submit_do_nothing_while_a_run_is_going(self):
        """[코드 실행]이 도는 동안에는 go_back 이 안내 창을 열거나 홈으로 가지 않고, confirm_submit 도 제출 확인 창을 열지 않음. 두 단추는 set_busy 가 끄므로 함수를 직접 불러 봄."""
        page = self.open_code()
        self.type_answer(page)
        run = Gate(example_run)
        with mock.patch.object(mock_code, "try_code", side_effect=run), \
                mock.patch.object(self.win, "ask") as ask, mock.patch.object(self.win, "go_ai") as home:
            page.run_btn.click()
            self.assertTrue(run.started.wait(10))
            self.assertTrue(page.busy)
            page.go_back()
            page.confirm_submit()
            ask.assert_not_called()
            home.assert_not_called()
            run.release.set()
            self.idle()
        self.assertIs(self.win.pages.currentWidget(), page)

    def test_moving_after_the_deadline_keeps_the_question_and_its_run_result(self):
        page = self.open_code()
        self.type_answer(page)
        with mock.patch.object(mock_code, "try_code", side_effect=example_run):
            page.run_btn.click()
            self.idle()
        console, result = page.console, page.console.html
        self.assertIn("add(1, 2)", page.console.toPlainText())
        self.expire()
        grader = Gate(stuck_grade)
        with mock.patch.object(mock_code, "grade", side_effect=grader):
            page.go(0)
            self.assertTrue(grader.started.wait(10))
            self.assertEqual("m90-03", page.item["card"])
            self.assertIs(console, page.console)  # 문항 카드를 다시 그리지 않아 실행 결과가 남음
            self.assertEqual(result, page.console.html)
            grader.release.set()
            self.idle()
        self.assertTrue(page.exam.result["auto"])

    def test_timeout_during_a_run_waits_and_grades_the_saved_answer(self):
        page = self.open_code()
        self.type_answer(page)
        run, grader = Gate(example_run), Gate(stuck_grade)
        with mock.patch.object(mock_code, "try_code", side_effect=run), \
                mock.patch.object(mock_code, "grade", side_effect=grader):
            page.run_btn.click()
            self.assertTrue(run.started.wait(10))
            self.expire()
            page.tick()
            self.assertFalse(page.submit_btn.isEnabled())
            self.assertFalse(page.top_submit.isEnabled())
            self.assertFalse(page.grading)
            run.release.set()
            self.idle()
            self.assertEqual([], grader.calls)
            grader.release.set()
            page.tick()
            self.idle()
        self.assertIsNot(threading.main_thread(), grader.calls[0][0])
        self.assertEqual(MINE, grader.calls[0][1][1])
        submitted = self.log("mock_submit")
        self.assertEqual((1, True), (len(submitted), submitted[0]["auto"]))

    def test_typing_after_the_deadline_starts_grading_on_a_worker(self):
        page = self.open_code()
        self.type_answer(page)
        self.expire()
        grader = Gate(stuck_grade)
        grader.release.set()
        with mock.patch.object(mock_code, "grade", side_effect=grader):
            QTest.keyClicks(page.inputs[0], "x")
            self.idle()
        self.assertEqual(1, len(grader.calls))
        self.assertIsNot(threading.main_thread(), grader.calls[0][0])
        self.assertEqual(MINE, grader.calls[0][1][1])
        self.assertEqual("m90-03", page.item["card"])
        self.assertTrue(page.exam.result["auto"])

    def test_reopened_expired_exam_is_graded_after_the_page_shows(self):
        page = self.open_code()
        self.type_answer(page)
        self.expire()
        grader = Gate(stuck_grade)
        grader.release.set()
        with mock.patch.object(mock_code, "grade", side_effect=grader):
            self.win.open_session()
            self.assertEqual(([], []), (grader.calls, self.log("mock_submit")))
            self.assertTrue(self.win.open_ai_mock("m90"))
            self.idle()
        self.assertEqual(1, len(grader.calls))
        self.assertIsNot(threading.main_thread(), grader.calls[0][0])
        self.assertTrue(self.log("mock_submit")[0]["auto"])

    def test_environment_failure_waits_a_minute_before_trying_again(self):
        page = self.open_code()
        self.type_answer(page)
        self.expire()
        now = [1000.0]
        with mock.patch.object(mock_code, "grade", side_effect=env_grade) as grader, \
                mock.patch.object(ai_mock, "monotonic", lambda: now[0]):
            page.tick()
            self.idle()
            self.assertEqual(1, grader.call_count)
            self.assertEqual(ai_mock.AUTO_ENV, page.notice.text.text())
            self.assertTrue(page.notice.isVisible())
            now[0] += ai_mock.RETRY_SECONDS - 1
            page.tick()
            self.idle()
            self.assertEqual(1, grader.call_count)
            now[0] += 1
            page.tick()
            self.idle()
            self.assertEqual(2, grader.call_count)
        self.assertEqual([], self.log("mock_submit"))
        self.assertIsNone(page.exam.result)

    def test_course_tab_waits_while_the_timed_out_exam_is_graded(self):
        page = self.open_code()
        self.type_answer(page)
        self.win.go_ai()
        self.idle()
        self.expire()
        grader = Gate(stuck_grade)
        session = self.win.ai
        with mock.patch.object(mock_code, "grade", side_effect=grader):
            page.tick()
            self.assertTrue(grader.started.wait(10))
            self.assertTrue(self.win.ai_home.busy)
            tab = self.win.ai_home.tab
            other = "intro" if tab == "mock" else "mock"
            with mock.patch.object(type(session), "resume_course") as resumed:
                self.win.select_ai_tab(other)
                self.win.select_ai_tab("app")
                resumed.assert_not_called()
            self.assertEqual((session, tab), (self.win.ai, self.win.ai_home.tab))
            grader.release.set()
            self.idle()
        self.assertEqual(1, len(self.log("mock_submit")))
        self.assertFalse(self.win.ai_home.busy)
        self.win.select_ai_tab(other)
        self.assertEqual(other, self.win.ai_home.tab)
