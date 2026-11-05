# -*- coding: utf-8 -*-
"""학습 단계 왕복의 화면 상태를 확인함. 메모리 서비스를 쓰며 기본 offscreen과 지정한 Windows 플랫폼에서 그림."""
import copy
import os
import unittest
from unittest import mock

from tests import guikit

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtWidgets import QWidget

from gui import ai_learn, kit, theme
from gui.docview import TextPiece
from session import SessionError

GIF = os.path.join(guikit.ROOT, "ai", "learn", "l04", "assets", "4a-2.gif")
PROSE = "\n\n".join("%d번 문단입니다. " % n + "글자 크기를 바꿔도 읽던 부분을 찾습니다. " * 8 for n in range(12))


def recall(name="r1"):
    return {"kind": "recall", "id": name, "q": "빈칸에 값을 적습니다.", "answer": ["정답"], "mode": "word"}


def steps():
    return [
        {"no": 1, "title": "값을 골라 봅니다", "scope": "core", "blocks": [
            {"kind": "guess", "id": "g1", "q": "값을 고릅니다.", "options": ["가", "나"], "reveal_step": 3}]},
        {"no": 2, "title": "그림과 입력을 살펴봅니다", "scope": "core", "blocks": [
            {"kind": "text", "markdown": PROSE},
            {"kind": "figure", "path": GIF, "caption": "값이 바뀌는 순서입니다."}, recall(),
            {"kind": "levels", "concept": "앞 설명", "levels": [dict(recall("same"), level=n, text="앞 설명입니다.",
             figure={"path": GIF, "caption": "두 값을 비교합니다."}) for n in (7, 15)]},
            {"kind": "levels", "concept": "뒤 설명", "levels": [dict(recall("same"), level=n, text="뒤 설명입니다.",
             figure={"path": GIF, "caption": "변경한 값을 확인합니다."}) for n in (7, 15)]},
            {"kind": "text", "markdown": PROSE}]},
        {"no": 3, "title": "고른 답을 확인합니다", "scope": "core", "blocks": [
            {"kind": "reveal", "guess": "g1", "q": "값을 고릅니다.", "options": ["가", "나"], "answer": 0}, recall("r2")]},
        {"no": 4, "title": "외울 내용을 확인합니다", "scope": "memo", "blocks": []},
    ]


class LearningService:
    def __init__(self):
        self.notes = {"test": {"dir": ""}}
        self.units = {key: steps() for key in ("one", "two")}
        self.guesses, self.read, self.calls = {}, set(), []

    def unit_steps(self, lid, key):
        rows = copy.deepcopy(self.units[key])
        for step in rows:
            for block in step["blocks"]:
                if block["kind"] in ("guess", "reveal"):
                    block["picked"] = self.guesses.get(key)
        return {"title": "시험 단원", "name": "시험 단원", "steps": rows}

    def lesson(self, lid):
        return {"units": [{"key": key, "read": key in self.read} for key in self.units]}

    def place(self, lid):
        return {"back": "lesson", "label": "시험 차시"}

    def save_step(self, lid, key, number):
        self.calls.append(("step", key, number))

    def mark_read(self, lid, key):
        self.read.add(key)
        self.calls.append(("learn", key))

    def save_guess(self, lid, key, gid, picked):
        self.guesses[key] = picked
        self.calls.append(("guess", key, gid, picked))

    def check_recall(self, block, value):
        return value == "정답"

    def save_recall(self, lid, key, rid, ok, level=None):
        self.calls.append(("recall", key, rid, ok, level))


class LearningWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.ai = LearningService()
        self.page = ai_learn.AiLearnPage(self)
        kit.box(self).addWidget(self.page)

    def ask(self, *args):
        raise AssertionError(args)


class LearningStateTest(unittest.TestCase):
    def setUp(self):
        self.assertIn(guikit.APP.platformName(), ("offscreen", "windows") if os.name == "nt" else ("offscreen",))
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.win = LearningWindow()
        self.addCleanup(self.close)
        self.win.resize(1024, 700)
        self.win.show()
        self.win.activateWindow()
        self.page = self.win.page
        self.page.load("test", "one", 2)
        self.settle()

    def settle(self):
        guikit.wait_until(lambda: self.page.pending_position is None and not self.page.position_timer.isActive()
                         and self.page.scroll.widget().height() >= self.page.scroll.widget().minimumSizeHint().height())
        guikit.pump()

    def close(self):
        self.win.close()
        self.win.deleteLater()
        guikit.pump()

    def field(self):
        return self.page.view.findChildren(ai_learn.RecallBlock)[0].field

    def round_trip(self):
        self.page.show_step(2)
        self.settle()
        self.page.show_step(1)
        self.settle()

    def test_round_trip_keeps_draft_and_backward_selection(self):
        field = self.field()
        field.setText("한글🙂 이어 쓰기")
        field.setFocus()
        field.setSelection(8, -3)
        expected = field.text(), field.cursorPosition(), field.selectionStart(), field.selectedText()
        self.round_trip()
        field = self.field()
        self.assertEqual((field.text(), field.cursorPosition(), field.selectionStart(), field.selectedText()), expected)
        self.assertTrue(field.hasFocus())

    def test_round_trip_keeps_figure_frame(self):
        self.page.view.figures[0].go(2)
        self.round_trip()
        self.assertEqual(self.page.view.figures[0].frame(), 2)
        self.assertFalse(self.page.view.figures[0].playing)

    def test_round_trip_keeps_reading_position(self):
        bar = self.page.scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 400)
        bar.setValue(450)
        expected = bar.value()
        self.round_trip()
        self.assertAlmostEqual(bar.value(), expected, delta=2)

    def test_new_unit_and_reopened_unit_start_without_old_drafts(self):
        self.field().setText("이전 단원의 초안")
        self.page.view.figures[0].go(3)
        self.page.load("test", "two", 2)
        self.settle()
        self.assertEqual(self.field().text(), "")
        self.field().setText("다른 단원의 초안")
        self.page.load("test", "one", 2)
        self.settle()
        self.assertEqual(self.field().text(), "")
        self.assertEqual(self.page.view.figures[0].frame(), 0)
        self.field().setText("다시 열기 전 초안")
        self.page.load("test", "one", 2)
        self.settle()
        self.assertEqual(self.field().text(), "")

    def test_changed_service_discards_the_old_window_state(self):
        self.field().setText("이전 서비스의 초안")
        self.page.show_step(2)
        self.win.ai = LearningService()
        self.page.show_step(1)
        self.settle()
        self.assertEqual(self.field().text(), "")

    def test_changed_explanation_discards_drafts_and_frames(self):
        self.field().setText("이전 설명의 초안")
        self.page.view.figures[0].go(4)
        self.page.show_step(2)
        self.win.ai.units["one"][1]["blocks"][2]["q"] = "바뀐 설명의 물음입니다."
        self.page.show_step(1)
        self.settle()
        self.assertEqual(self.field().text(), "")
        self.assertEqual(self.page.view.figures[0].frame(), 0)

    def test_latest_guess_is_visible_with_the_returned_draft(self):
        self.win.ai.guesses["one"] = 0
        self.page.show_step(2)
        self.settle()
        self.field().setText("해설 아래 초안")
        old_view = self.page.view
        self.page.show_step(0)
        self.settle()
        self.win.ai.save_guess("test", "one", "g1", 1)
        self.page.show_step(2)
        self.settle()
        self.assertIsNot(self.page.view, old_view)
        reveal = self.page.view.findChildren(ai_learn.RevealBlock)[0]
        lines = [line.plain for line in reveal.findChildren(ai_learn.RichPara)]
        self.assertEqual(lines[1:], ["나", "가"])  # 바꾼 짐작 답과 서비스의 공개 정답
        self.assertEqual(self.field().text(), "해설 아래 초안")

    def test_nested_repeated_ids_keep_separate_drafts_and_frames(self):
        levels = self.page.view.findChildren(ai_learn.LevelsBlock)
        for block in levels:
            block.row.set_opened(True)
        self.settle()
        fields = self.page.view.findChildren(ai_learn.RecallBlock)
        for n, block in enumerate(fields):
            block.field.setText("%d번 초안" % n)
            block.field.setSelection(0, 2)
        for n, figure in enumerate(self.page.view.findChildren(ai_learn.AiFigure)):
            figure.go(n % figure.count)
        levels[1].row.set_opened(False)
        self.round_trip()
        levels = self.page.view.findChildren(ai_learn.LevelsBlock)
        self.assertEqual([block.row.opened for block in levels], [True, False])
        fields = self.page.view.findChildren(ai_learn.RecallBlock)
        self.assertEqual([block.field.text() for block in fields], ["%d번 초안" % n for n in range(5)])
        self.assertEqual([block.field.selectedText() for block in fields], ["%d번" % n for n in range(5)])
        self.assertEqual([figure.frame() for figure in self.page.view.findChildren(ai_learn.AiFigure)], list(range(5)))

    def test_rapid_moves_do_not_apply_a_previous_timer(self):
        self.field().setText("빠른 왕복의 초안")
        bar = self.page.scroll.verticalScrollBar()
        bar.setValue(650)
        self.page.show_step(2)
        self.page.show_step(1)
        self.page.show_step(2)
        self.page.show_step(1)
        self.settle()
        self.assertEqual(self.page.index, 1)
        self.assertEqual(self.field().text(), "빠른 왕복의 초안")
        self.assertAlmostEqual(bar.value(), 650, delta=2)
        self.page.show_step(2)
        self.page.load("test", "two", 2)
        self.settle()
        self.assertEqual(self.field().text(), "")
        self.assertEqual(bar.value(), 0)

    def test_restoring_drafts_does_not_submit_or_mark_learning(self):
        self.field().setText("정답")
        self.round_trip()
        self.assertFalse([call for call in self.win.ai.calls if call[0] != "step"])
        block = self.page.view.findChildren(ai_learn.RecallBlock)[0]
        block.check()
        self.page.show_step(3)
        self.settle()
        self.page.show_step(1)
        self.settle()
        self.assertEqual(self.field().text(), "")  # 제출한 칸의 판정과 완성 상태는 복원 범위 밖임
        self.page.show_step(3)
        self.settle()
        self.assertEqual([call[0] for call in self.win.ai.calls if call[0] != "step"], ["recall", "learn"])

    def test_read_failure_leaves_the_current_draft_in_place(self):
        self.field().setText("읽기 실패 전 초안")
        view = self.page.view
        with mock.patch.object(self.win.ai, "unit_steps", side_effect=SessionError("자료를 읽지 못했습니다.")), \
                mock.patch.object(self.win, "ask") as ask:
            self.page.show_step(2)
        ask.assert_called_once()
        self.assertIs(self.page.view, view)
        self.assertEqual(self.field().text(), "읽기 실패 전 초안")

    def test_resize_and_larger_text_keep_the_reading_block_in_both_themes(self):
        bar = self.page.scroll.verticalScrollBar()
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme):
                theme.set_mode(scheme)
                theme.set_text("normal")
                kit.refont(self.win)
                self.page.restyle()
                self.win.resize(1280, 800)
                self.settle()
                self.field().setText("크기를 바꾸기 전 초안")
                piece = self.page.view.findChildren(TextPiece)[0]
                top = piece.mapTo(self.page.scroll.widget(), QPoint()).y()
                bar.setValue(top + round(piece.height() * 0.6))
                expected = (bar.value() - top) / piece.height()
                self.win.resize(760, 480)
                theme.set_text("larger")
                kit.refont(self.win)
                self.page.restyle()
                self.settle()
                top = piece.mapTo(self.page.scroll.widget(), QPoint()).y()
                self.assertAlmostEqual((bar.value() - top) / piece.height(), expected, delta=0.02)
                self.assertEqual((self.win.width(), self.win.height()), (760, 480))
                self.round_trip()
                self.assertEqual(self.field().text(), "크기를 바꾸기 전 초안")
                self.assertEqual(self.page.next_btn.text(), "다음")
                self.assertTrue(self.win.rect().contains(self.page.next_btn.mapTo(self.win, QPoint())))
                self.assertTrue(self.win.rect().contains(self.page.next_btn.mapTo(self.win, self.page.next_btn.rect().bottomRight())))

    def test_resize_keeps_the_active_input_and_its_selection(self):
        field = self.field()
        field.setText("계속 적던 문장")
        field.setFocus()
        field.setSelection(5, -3)
        self.page.scroll.ensureWidgetVisible(field)
        self.settle()
        expected = field.cursorPosition(), field.selectionStart(), field.selectedText()
        self.win.resize(760, 480)
        theme.set_text("larger")
        kit.refont(self.win)
        self.page.restyle()
        self.settle()
        self.assertTrue(field.hasFocus())
        self.assertEqual((field.cursorPosition(), field.selectionStart(), field.selectedText()), expected)
        viewport = self.page.scroll.viewport()
        self.assertTrue(viewport.rect().intersects(QRect(field.mapTo(viewport, QPoint()), field.size())))

    def test_return_after_resize_uses_the_reading_block_in_the_new_layout(self):
        piece = self.page.view.findChildren(TextPiece)[0]
        bar = self.page.scroll.verticalScrollBar()
        top = piece.mapTo(self.page.scroll.widget(), QPoint()).y()
        bar.setValue(top + round(piece.height() * 0.65))
        expected = (bar.value() - top) / piece.height()
        self.page.show_step(2)
        self.settle()
        self.win.resize(760, 480)
        theme.set_text("larger")
        kit.refont(self.win)
        self.page.restyle()
        self.settle()
        self.page.show_step(1)
        self.settle()
        piece = self.page.view.findChildren(TextPiece)[0]
        top = piece.mapTo(self.page.scroll.widget(), QPoint()).y()
        self.assertAlmostEqual((bar.value() - top) / piece.height(), expected, delta=0.02)
