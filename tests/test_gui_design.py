# -*- coding: utf-8 -*-
"""첫 화면과 웹 면접 준비 화면이 디자인 시스템의 규칙을 지키는지(설계 검사 C5~C8). 화면 상태마다 보이는 주 단추는 하나 이하이고,
단추는 32 이상(주 단추 48), 목록 줄은 56 이상이며, 작업 화면의 주 단추는 아래 막대 오른쪽 끝(창 폭 − 32)에 있고, 홈 화면의 주 단추는
1024×700 에서 스크롤 없이 보임. 읽는 글의 폭은 640 이하. 화면을 띄우는 순서는 tests/test_gui_web.py 의 LookTest.screens 를 그대로 씀.
PyQt6 가 없으면 전부 건너뜀."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import QPushButton, QScrollArea  # noqa: E402

from gui import kit, theme  # noqa: E402
from gui.docview import TextPiece  # noqa: E402
from tests.test_gui_web import LookTest, WebTest, inside  # noqa: E402

MARGIN = kit.MARGIN


def shown(widget, win):
    return widget.isVisible() and widget.isVisibleTo(win)


def kit_buttons(page):
    """새 규칙을 따르는 단추들(크기 속성이 있는 것)."""
    return [b for b in page.findChildren(QPushButton) if b.property("scale")]


class DesignTest(WebTest):
    def screens(self, win):
        return LookTest.screens(self, win)

    def test_one_primary_button_and_control_sizes_on_every_screen(self):
        win = self.boot((1024, 700))
        for name, show, _ in self.screens(win):
            show()
            self.idle()
            page = self.page()
            self.assertEqual(page.property("ui"), "2", name)
            primaries = kit.visible_primary_buttons(page)
            self.assertLessEqual(len(primaries), 1, "%s: %s" % (name, [b.text() for b in primaries]))
            for button in kit_buttons(page):
                if not shown(button, win):
                    continue
                least = theme.CONTROL["l"] if button.objectName() == "primary" else theme.CONTROL["s"]
                self.assertGreaterEqual(button.height(), least, "%s: %s" % (name, button.text()))
                self.assertLessEqual(len(button.text().replace(" ", "")), 8, "%s: %s" % (name, button.text()))
            for row in page.findChildren(kit.Row):
                if shown(row, win):
                    self.assertGreaterEqual(row.height(), theme.CONTROL["row"], "%s: %s" % (name, row.title.text()))
            if page in (win.web_mission, win.web_drill) and primaries:
                button = primaries[0]
                right = button.mapTo(win, QPoint(button.width(), button.height()))
                self.assertEqual(right.x(), win.width() - MARGIN, "%s: %s" % (name, button.text()))
                self.assertTrue(inside(win, button), name)
            if page in (win.hub, win.web_home) and primaries:
                scroll = page.findChild(QScrollArea)
                self.assertEqual(scroll.verticalScrollBar().value(), 0, name)
                self.assertTrue(inside(win, primaries[0]), "%s: 주 단추가 스크롤 없이 보여야 함" % name)

    def test_reading_measure_is_640_or_less(self):
        win = self.boot()
        win.open_learn("l90")
        self.idle()
        pieces = [p for p in win.web_learn.view.findChildren(TextPiece) if shown(p, win)]
        self.assertTrue(pieces)
        for piece in pieces:
            self.assertLessEqual(piece.width(), 640, "학습 노트 %d" % piece.width())
        self.open_mission()
        for piece in win.web_mission.findChildren(TextPiece):
            if shown(piece, win):
                self.assertLessEqual(piece.width(), 640, "미션 안내 %d" % piece.width())


if __name__ == "__main__":
    unittest.main()
