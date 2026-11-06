# -*- coding: utf-8 -*-
"""제목·설명 묶음과 좁은 그림 넘김 줄의 배치 및 조작을 검사함."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import guikit

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget

from gui import docview, kit, theme
from gui.ai_learn import AiFigure
from tests.test_gui_docview import GIF


def ten_frame_gif():
    """기존 3장 GIF의 이미지 블록을 반복해 10장 경계를 만듦."""
    marker = b"\x21\xf9\x04"
    head, *frames = GIF[:-1].split(marker)
    assert len(frames) == 3 and GIF[-1:] == b";"
    return head + b"".join(marker + frames[n % 3] for n in range(10)) + b";"


class SpacingTest(unittest.TestCase):
    def setUp(self):
        self.old_text = theme.state["text"]
        self.old_mode = theme.state["mode"]
        self.addCleanup(theme.set_text, self.old_text)
        self.addCleanup(theme.set_mode, self.old_mode)

    def show(self, widget, width=320):
        widget.resize(width, 800)
        widget.show()
        self.addCleanup(widget.deleteLater)
        self.addCleanup(widget.close)
        guikit.pump()

    def test_heading_gap_survives_wrapping_and_hidden_description(self):
        for step in ("normal", "larger"):
            theme.set_text(step)
            for mode in ("light", "dark"):
                theme.set_mode(mode)
                for width in (320, 620):
                    with self.subTest(step=step, mode=mode, width=width):
                        root = kit.page(QWidget())
                        box = kit.box(root)
                        head = kit.heading(kit.para("단원별 학습", "headline"),
                                           kit.para("문제를 풀고 노트를 읽습니다. " * 5, "body", "secondary"))
                        box.addWidget(head)
                        box.addStretch(1)
                        self.show(root, width)
                        title, description = head.title, head.description
                        self.assertEqual(description.y() - title.geometry().bottom() - 1,
                                         theme.GAP["title_description"])
                        self.assertGreaterEqual(description.height(), description.heightForWidth(description.width()))
                        description.hide()
                        guikit.pump()
                        self.assertEqual(head.height(), title.height())
                        root.close()

    def test_row_detail_keeps_its_gap_at_the_largest_text_size(self):
        theme.set_text("larger")
        root = kit.page(QWidget())
        box = kit.box(root)
        row = kit.Row("줄바꿈하는 학습 단원의 제목 " * 3, "단원 아래의 보조 설명 " * 4, wrap=True)
        box.addWidget(row)
        box.addStretch(1)
        self.show(root)
        self.assertEqual(row.second.y() - row.title.geometry().bottom() - 1, theme.GAP["detail"])
        self.assertGreaterEqual(row.second.height(), row.second.heightForWidth(row.second.width()))
        self.assertLessEqual(row.second.mapTo(row, row.second.rect().bottomRight()).y(), row.height() - 12)

    def test_frame_caption_remeasures_after_the_actual_font_is_applied(self):
        theme.set_text("normal")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(docview, "SCALE", 0.125):
            path = Path(tmp, "three.gif")
            path.write_bytes(GIF)
            root = kit.page(QWidget())
            column = kit.box(root)
            figure = AiFigure(os.fspath(path), "그림 설명", frames=[
                {"text": "첫 장"}, {"text": "설명이 길어도 넘김 단추 자리를 유지합니다. " * 3}, {"text": "마지막 장"}])
            figure.setMaximumWidth(520)
            column.addWidget(figure)
            column.addStretch()
            root.resize(760, 600)
            root.show()
            self.addCleanup(root.deleteLater)
            self.addCleanup(root.close)
            kit.refont(figure)
            figure.draw()
            guikit.pump()
            theme.set_text("larger")
            figure.draw()  # 글꼴 갱신 전에 온 크기 변경도 처리함.
            kit.refont(figure)
            figure.draw()
            figure.first()
            guikit.pump()
            before = figure.controls.geometry()
            figure.go(1)
            guikit.pump()
            self.assertEqual(figure.controls.geometry(), before)
            self.assertGreaterEqual(figure.frame_text.height(), figure.frame_text.heightForWidth(figure.frame_text.width()))

    def test_narrow_figure_controls_keep_text_and_actions_after_refont(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(docview, "SCALE", 0.125):
            path = Path(tmp, "three.gif")
            path.write_bytes(GIF)
            figure = kit.page(AiFigure(os.fspath(path), "그림 설명", frames=[
                {"text": "첫 장"}, {"text": "설명이 길어도 넘김 단추 자리를 유지합니다. " * 3}, {"text": "마지막 장"}]))
            self.show(figure)
            for step in ("normal", "larger"):
                theme.set_text(step)
                kit.refont(figure)
                for mode in ("light", "dark"):
                    theme.set_mode(mode)
                    for width in (520, 320):
                        with self.subTest(step=step, mode=mode, width=width):
                            figure.resize(width, 1000)
                            guikit.pump()
                            buttons = (figure.first_btn, figure.prev_btn, figure.play_btn, figure.next_btn)
                            for button in buttons:
                                self.assertGreaterEqual(button.width(), button.sizeHint().width())
                                self.assertTrue(figure.controls.rect().contains(button.geometry()))
                            if width == 320:
                                self.assertGreater(len({button.y() for button in buttons} | {figure.counter.y()}), 1)
                            figure.first()
                            guikit.pump()
                            before = figure.controls.geometry()
                            figure.setFocus()
                            QTest.keyClick(figure, Qt.Key.Key_Right)
                            guikit.pump()
                            self.assertEqual(figure.counter.text(), "2 / 3")
                            self.assertEqual(figure.controls.geometry(), before)
                            QTest.keyClick(figure, Qt.Key.Key_Left)
                            self.assertEqual(figure.counter.text(), "1 / 3")
                            figure.play_btn.click()
                            self.assertTrue(figure.playing)
                            figure.play_btn.click()
                            self.assertFalse(figure.playing)
            figure.go(1)
            figure.zoom_btn.click()
            guikit.pump()
            self.addCleanup(figure.dialog.close)
            self.assertEqual(figure.dialog.view.counter.text(), "2 / 3")
            figure.dialog.view.next_btn.click()
            self.assertEqual(figure.dialog.view.counter.text(), "3 / 3")

    def test_ten_frame_counter_and_play_labels_keep_the_same_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ten.gif")
            path.write_bytes(ten_frame_gif())
            figure = kit.page(AiFigure(os.fspath(path), frames=[{"text": "장 설명"}] * 10))
            self.show(figure)
            self.assertEqual(figure.count, 10)
            for step in ("normal", "larger"):
                theme.set_text(step)
                kit.refont(figure)
                for mode in ("light", "dark"):
                    theme.set_mode(mode)
                    kit.refont(figure)
                    guikit.pump()
                    metrics = QFontMetricsF(figure.counter.font())
                    short = metrics.horizontalAdvance("1 / 10")
                    longest = max(metrics.horizontalAdvance("%d / 10" % n) for n in range(1, 11))
                    buttons = (figure.first_btn, figure.prev_btn, figure.play_btn, figure.next_btn)
                    boundary = round(sum(b.sizeHint().width() for b in buttons) + 4 * theme.GAP["detail"]
                                     + (short + longest) / 2)
                    for width in (320, boundary):
                        with self.subTest(step=step, mode=mode, width=width):
                            figure.resize(width, 800)
                            figure.first()
                            guikit.pump()
                            def positions():
                                return (figure.controls.geometry(), [w.geometry() for w in (*buttons, figure.counter)])
                            before = positions()
                            for frame in range(10):
                                figure.go(frame)
                                guikit.pump()
                                self.assertEqual(positions(), before)
                                self.assertEqual(figure.counter.text(), "%d / 10" % (frame + 1))
                                current_metrics = QFontMetricsF(figure.counter.font())
                                current_widest = max(current_metrics.horizontalAdvance("%d / 10" % n)
                                                     for n in range(1, 11))
                                self.assertGreaterEqual(figure.counter.width(), current_widest)
                                for button in buttons:
                                    self.assertGreaterEqual(button.width(), button.sizeHint().width())
                                    self.assertTrue(figure.controls.rect().contains(button.geometry()))
                            figure.first()
                            guikit.pump()
                            figure.play_btn.click()
                            self.assertEqual(figure.play_btn.text(), "멈춤")
                            self.assertEqual(positions(), before)
                            figure.play_btn.click()
                            self.assertEqual(figure.play_btn.text(), "재생")
                            self.assertEqual(positions(), before)


if __name__ == "__main__":
    unittest.main()
