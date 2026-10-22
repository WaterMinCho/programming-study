# -*- coding: utf-8 -*-
"""첫 화면과 웹 면접 준비 화면이 디자인 시스템의 규칙을 지키는지(설계 검사 C5~C8). 화면 상태마다 보이는 주 단추는 하나 이하이고,
단추는 32 이상(주 단추 48), 목록 줄은 56 이상이며, 작업 화면의 주 단추는 아래 막대 오른쪽 끝(창 폭 − 32)에 있고, 홈 화면의 주 단추는
1024×700 에서 스크롤 없이 보임. 읽는 글의 폭은 1280 창에서 640 이하이고 넓은 창에서는 창을 따라 넓어지되 kit.doc_max 를 넘지 않음.
화면을 띄우는 순서는 tests/test_gui_web.py 의 LookTest.screens 를 그대로 씀.
PyQt6 가 없으면 전부 건너뜀."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import QLabel, QPushButton, QScrollArea  # noqa: E402

from gui import kit, theme  # noqa: E402
from gui.docview import TextPiece  # noqa: E402
from tests import test_gui_web  # noqa: E402  LookTest 를 이름으로 가져오면 discover 가 그 테스트를 한 번 더 돌림
from tests.test_gui_web import WebTest, inside  # noqa: E402

MARGIN = kit.MARGIN


def shown(widget, win):
    return widget.isVisible() and widget.isVisibleTo(win)


def kit_buttons(page):
    """새 규칙을 따르는 단추들(크기 속성이 있는 것)."""
    return [b for b in page.findChildren(QPushButton) if b.property("scale")]


class DesignTest(WebTest):
    def screens(self, win):
        return test_gui_web.LookTest.screens(self, win)

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
                if button.objectName() != "chip":  # 칩은 주제 제목이라 길이 규칙에서 뺌
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

    def test_reading_measure_follows_the_window(self):
        """읽는 글의 단은 1280 창에서 640(설계값)이고 2000 창에서는 본문 64자 폭(크게 848)까지 넓어짐. 미션의 오른쪽 카드는 480(글자 크기에 비례)까지만
        넓어지고 그 안에서 같이 읽을 노트 줄의 제목이 잘리지 않으며, 학습 노트와 꼬리 질문 카드도 같이 넓어짐."""
        self.assertEqual((kit.doc_width(1024), kit.doc_width(1280), kit.doc_width(2000)), (640, 640, min(1000, kit.doc_max())))
        self.addCleanup(theme.set_text, theme.state["text"])
        for step, widest in (("normal", 759), ("large", 848), ("larger", 937)):
            theme.set_text(step)
            self.assertEqual(kit.doc_max(), widest, step)
        theme.set_text(theme.TEXT_DEFAULT)
        for size, low, high in (((1280, 800), 600, 640), ((2000, 1070), 800, kit.doc_max())):
            win = self.boot(size)
            win.open_learn("l90")
            self.idle()
            learn = win.web_learn
            pieces = [p for p in learn.view.findChildren(TextPiece) if shown(p, win)]
            self.assertTrue(pieces)
            for piece in pieces:
                self.assertTrue(low <= piece.width() <= high, "%s 학습 노트 %d" % (size, piece.width()))
            page = self.open_mission()
            for piece in page.brief_view.findChildren(TextPiece):
                if shown(piece, win):
                    self.assertTrue(low <= piece.width() <= high, "%s 미션 안내 %d" % (size, piece.width()))
            row = page.note_rows.rows[0]
            drill = self.open_drill("90-A")
            if size[0] == 2000:
                self.assertEqual(page.brief_view.sheet.width(), kit.doc_width(2000) + 48)
                self.assertEqual(page.right_card.width(), round(480 * theme.TYPE["body"][0] / 17))
                self.assertEqual(QLabel.text(row.title), row.title.full)  # 제목이 줄임표 없이 다 보임
                self.assertEqual(learn.card.width(), kit.doc_width(2000) + 48)
                self.assertGreater(drill.ask_card.width(), 720)
            else:
                self.assertLessEqual(page.brief_view.sheet.width(), 640 + 48)
                self.assertEqual((learn.card.width(), drill.ask_card.width()), (688, 720))
            win.close()
            win.deleteLater()
            guikit.pump()
            self.win = None


if __name__ == "__main__":
    unittest.main()
