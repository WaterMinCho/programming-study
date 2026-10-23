# -*- coding: utf-8 -*-
"""첫 화면, 웹 면접 준비 화면, 알고리즘 여행 화면이 디자인 시스템의 규칙을 지키는지(설계 검사 C5~C8). 화면 상태마다 보이는 주 단추는
하나 이하이고, 단추는 32 이상(주 단추 48), 목록 줄은 56 이상이며, 작업 화면의 주 단추는 아래 막대 오른쪽 끝(창 폭 − 32)에 있고,
홈 화면의 주 단추는 1024×700 에서 스크롤 없이 보임. 읽는 글의 폭은 1280 창에서 640 이하이고 넓은 창에서는 창을 따라 넓어지되
kit.doc_max 를 넘지 않음. 첫 화면과 웹 화면을 띄우는 순서는 tests/test_gui_web.py 의 LookTest.screens 를 그대로 쓰고,
여행 화면은 tests/test_gui_journey.py 의 가짜 창과 고정 은행으로 띄움.
PyQt6 가 없으면 전부 건너뜀."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import QLabel, QPushButton, QScrollArea  # noqa: E402

from gui import journey_text, kit, theme  # noqa: E402
from gui.docview import FigureView, TextPiece  # noqa: E402
from gui.journey_page import NODE_BUSY  # noqa: E402
from journey.grading import ACC_TEXT, EFF_TEXT  # noqa: E402
from journey.service import JourneyError, JourneySession  # noqa: E402
from tests import test_gui_journey, test_gui_web  # noqa: E402  TestCase 를 이름으로 가져오면 discover 가 그 테스트를 한 번 더 돌림
from tests.test_gui_journey import HAS_NODE, NO_NODE, fake_grade, fake_run, passed, run_case  # noqa: E402
from tests.test_gui_web import WebTest, inside, scroll_to  # noqa: E402

MARGIN = kit.MARGIN
LONGEST = "주문서를 채우는 최단 진열"  # 은행(dungeons/)에서 가장 긴 문제 이름
TOO_LONG = "위 막대의 상한보다 길어서 끝을 줄임표로 줄여야 하는 문제 이름"
CLOSING = "하던 작업이 끝나면 창을 닫습니다."  # 창을 닫을 때 window.py 가 문제 화면의 set_busy 로 넘기는 글
# 위 막대를 재는 다섯 경우: (이름, 상태 글, 문제, 번호). 이름·번호가 None 이면 은행의 것. 모두 Node 가 없어 "Node.js 필요" 가 붙음
TOP_CASES = ((LONGEST, journey_text.SAVED, "p1", None), (LONGEST, "내 테스트 3개를 저장했습니다.", "p2", None), (LONGEST, CLOSING, "p2", None),
             (None, CLOSING, "boss", None), (TOO_LONG, journey_text.SAVED, "p3", "16-6"))
GRADED = {"score": 41.5, "runtime": "Python 3.14.4",
          "groups": [{"name": "정확성", "earned": 29.5, "points": 70.0,
                      "cases": [{"no": 1, "id": "ex1", "status": "pass", "label": "통과 (0.01ms, 10.2MB)", "name": ""},
                                {"no": 2, "id": "t2", "status": "wrong", "label": "실패", "name": ""}]},
                     {"name": "효율성", "earned": 12.0, "points": 30.0, "cases": []}]}
FIRST_PASS = {"score": 100.0, "first_pass": True, "boss_opened": True, "runtime": "Python 3.14.4",
              "groups": [{"name": "정확성", "earned": 100.0, "points": 100.0, "cases": []}]}


def shown(widget, win):
    return widget.isVisible() and widget.isVisibleTo(win)


def kit_buttons(page):
    """새 규칙을 따르는 단추들(크기 속성이 있는 것)."""
    return [b for b in page.findChildren(QPushButton) if b.property("scale")]


def own(widget, root):
    """widget 이 root 와 같은 창에서 보이는지. 화면을 부모로 둔 대화상자(테스트 추가 창)의 부품은 그 창 몫으로 셈."""
    return widget.isVisible() and widget.window() is root.window()


def screen_sizes():
    """화면 글이 쓰는 글자 크기(설계 10.1-22). label 은 body 와 크기가 같고, code 는 앱 기본 크기(15)와 겹쳐 옮기지 않은 글을 못 잡으므로 뺌."""
    return {theme.TYPE[role][0] for role in ("display", "title", "headline", "body", "caption")}


def holder(widget):
    """widget 을 담은 가장 가까운 스크롤 칸. 없으면 None."""
    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QScrollArea):
        parent = parent.parentWidget()
    return parent


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



class JourneyDesignTest(test_gui_journey.Base):
    """알고리즘 여행의 던전 지도와 문제 화면, 그 위에 뜨는 창(설계 10.1-1~3, 22, 24, 26, 27). 실행·채점은 자식 프로세스 없이
    결과 dict 를 넣음. 상태마다 보는 규칙은 1024×700 의 보통·크게(기본)에서 보고, 더 크게에서는 작은 창에 다 들어오는지를 더 봄."""

    def setUp(self):
        super().setUp()
        self.win = None
        self.addCleanup(theme.set_text, "normal")

    def close(self):
        """한 시험에서 창을 여러 번 띄우므로 지금 창만 닫음. 이미 닫았으면 아무것도 하지 않음."""
        if self.win is not None:
            super().close()
            self.win = None

    def start(self, step=theme.TEXT_DEFAULT, size=(1024, 700), log=()):
        """앞 창을 닫고 step 글자 단계, size 크기의 창으로 지도를 띄움. MainWindow 처럼 단계를 먼저 정한 뒤 화면을 만듦.
        만든 뒤에 단계를 바꾸면 refont 가 옛 objectName 의 QSS 글자 크기(QLabel#h1 의 21px)를 덮어 그려진 크기 검사가 그것을 못 봄."""
        self.close()
        theme.set_text(step)
        win = self.boot(log)
        win.resize(*size)
        guikit.pump()
        return win

    def walk(self, step, check):
        """step 글자 단계의 1024×700 창에서 여행 화면의 상태를 차례로 띄우고 상태마다 check(이름, 화면, [화면 위에 뜬 창])를 부름.
        설계 10.1-1 의 목록에 지도 바쁨, Node 창, 잠긴 보스 창, 찾기 막대, 저장 실패, 채점 중을 더함."""
        win = self.start(step)
        home = win.journey_map
        check("지도 처음", home, [])
        home.show_dungeon("t03")
        check("준비 중 던전", home, [])
        home.show_dungeon("t02")
        check("못 읽은 던전", home, [])
        home.show_dungeon("t01")
        home.set_busy(True, NODE_BUSY)
        check("지도 바쁨", home, [])
        home.set_busy(False)
        with mock.patch.object(win.journey, "runtime", lambda lang: HAS_NODE if lang == "python" else NO_NODE):
            guikit.click(home.lang_btns["javascript"])
        check("Node 띠와 읽지 못한 던전 띠", home, [win.dialog])
        win.dialog.close()
        win.open_problem("t01", "boss")
        check("잠긴 보스", home, [win.dialog])
        win.dialog.close()
        for pid, name in (("p1", "문제 처음"), ("p2", "중급"), ("p3", "선택")):
            page = self.open(pid)
            check(name, page, [])
        page = self.open("p1")
        page.tabs.setCurrentIndex(1)
        guikit.click(page.hint_btn)
        check("힌트 하나 연 뒤", page, [])
        page.tabs.setCurrentIndex(2)
        check("해설 잠김", page, [])
        page.tabs.setCurrentIndex(0)
        guikit.click(page.cases_btn)
        check("테스트 추가 창", page, [page.cases_dialog])
        page.cases_dialog.close()
        page.code_panel.editor.setFocus()
        page.find_bar.reveal()
        check("찾기 막대", page, [])
        page.find_bar.dismiss()
        self.type_code(test_gui_journey.MAX_SOLUTION)
        with mock.patch.object(win.journey, "save_code", side_effect=JourneyError("코드를 저장하지 못했습니다: [Errno 13] 권한 없음")):
            page.flush(offer=False)
        check("저장 실패", page, [])
        with mock.patch.object(win.journey, "run", fake_run([run_case(1), run_case(2, False)], check=lambda: check("실행 중", page, []))):
            guikit.click(page.run_btn)
        check("실행 결과", page, [])
        with mock.patch.object(win.journey, "grade", fake_grade(GRADED, check=lambda: check("채점 중", page, []))):
            guikit.click(page.grade_btn)
        check("채점 결과", page, [])
        with mock.patch.object(win.journey, "grade", fake_grade(FIRST_PASS)):
            guikit.click(page.grade_btn)
        check("처음 통과", page, [])
        self.write_log([passed("p1"), passed("p2")])
        win.journey = JourneySession("alice")  # 기록을 밖에서 고쳤으므로 [문제 받기] 뒤처럼 서비스를 새로 만듦
        page = self.open("p1")
        page.tabs.setCurrentIndex(2)
        check("해설 열림", page, [])
        figure = next(piece for piece in page.explain_view.pieces if isinstance(piece, FigureView))
        page.explain_view.ensureWidgetVisible(figure)
        figure.open_dialog()
        check("그림 창", page, [figure.dialog])
        figure.dialog.close()
        page.tabs.setCurrentIndex(0)
        check("보스", self.open("boss"), [])
        win.go_journey()
        check("몇 문제 통과", home, [])

    def check_rules(self, name, page, others):
        """한 상태의 규칙(설계 10.1-1·2). 새 규칙 범위, 창마다 주 단추 하나 이하, 모든 단추가 kit 단추이고 높이가 설계값이며
        글자가 잘리지 않음, 단추 글 8자 이하(칩 빼고), 목록 줄 56 이상. 문제 화면의 주 단추는 아래 막대 오른쪽 끝, 지도의 [문제 풀기]는
        스크롤 없이 창 안."""
        guikit.pump()
        win = self.win
        self.assertIs(win.pages.currentWidget(), page, name)
        self.assertLessEqual(win.minimumSizeHint().height(), 480, "%s: 1366×768(125%%) 화면에 창이 다 들어옴" % name)
        for root in [page] + others:
            where = "%s %s" % (name, "" if root is page else root.windowTitle())
            self.assertEqual("2", root.property("ui"), where)
            primaries = [button for button in kit.visible_primary_buttons(root) if button.window() is root.window()]
            self.assertLessEqual(len(primaries), 1, "%s: %s" % (where, [button.text() for button in primaries]))
            for button in root.findChildren(QPushButton):
                if not own(button, root) or button.objectName() == "tool":  # 찾기 막대의 작은 단추는 편집기 부품이라 뺌
                    continue
                label = "%s: %s" % (where, button.text())
                scale = button.property("scale")
                self.assertIn(scale, ("l", "m", "s"), "kit 단추가 아님 " + label)
                want = theme.CONTROL["l"] if button.objectName() == "tab" else theme.CONTROL[scale]  # 탭은 아래 선까지 48
                self.assertEqual(want, button.height(), label)
                if button.objectName() != "chip":  # 칩은 언어 이름이라 길이 규칙에서 뺌
                    self.assertLessEqual(len(button.text().replace(" ", "")), 8, label)
                self.assertGreaterEqual(button.width(), button.sizeHint().width(), "글자가 잘림 " + label)
            for row in root.findChildren(kit.Row):
                if own(row, root):
                    self.assertGreaterEqual(row.height(), theme.CONTROL["row"], "%s: %s" % (where, row.title.text()))
        primaries = [button for button in kit.visible_primary_buttons(page) if button.window() is win]
        if page is win.journey_page:
            button = primaries[0]
            right = button.mapTo(win, QPoint(button.width(), button.height()))
            self.assertEqual(win.width() - MARGIN, right.x(), name)
            self.assertTrue(inside(win, button), name)
        elif page.next_btn.isVisible():
            self.assertEqual(0, page.scroll.verticalScrollBar().value(), name)
            self.assertTrue(inside(win, page.next_btn), "%s: [문제 풀기]가 스크롤 아래에 있음" % name)

    def check_type(self, name, page, others):
        """그려진 글자 크기(설계 10.1-22). 보이는 글과 단추의 글자 크기가 screen_sizes() 안에 듦. 코드 글꼴 부품, 찾기 막대 단추,
        글 없이 그림만 담은 칸(그림 조각)은 뺌."""
        allowed, code = screen_sizes(), theme.code_font(0).family()
        for root in [page] + others:
            for widget in root.findChildren(QLabel) + root.findChildren(QPushButton):
                if not own(widget, root) or not widget.text() or widget.objectName() == "tool" or widget.font().family() == code:
                    continue
                self.assertIn(widget.font().pixelSize(), allowed, "%s %s: %s" % (theme.state["text"], name, widget.text()[:20]))

    def check_fits(self, name, page, others):
        """작은 창(설계 10.1-1 의 규칙에 더해): 화면이 창을 넓히지 않고, 보이는 단추와 목록 줄은 스크롤하면 창 안에 다 들어옴.
        굴린 칸은 제자리로 돌림."""
        self.check_rules(name, page, others)
        win = self.win
        self.assertLessEqual(page.minimumSizeHint().width(), 1024, name)
        self.assertLessEqual(page.minimumSizeHint().height(), 700, name)
        self.assertEqual((1024, 700), (win.width(), win.height()), name)
        for root in [page] + others:
            for widget in root.findChildren(QPushButton) + root.findChildren(kit.Row):
                if not own(widget, root):
                    continue
                area = holder(widget)
                place = area.verticalScrollBar().value() if area else 0
                scroll_to(widget)
                self.assertTrue(inside(root.window(), widget), "%s: %s" % (name, test_gui_web.name_of(widget)))
                if area:
                    area.verticalScrollBar().setValue(place)

    def test_every_state_keeps_the_rules_at_the_default_step(self):
        self.walk(theme.TEXT_DEFAULT, lambda *state: (self.check_rules(*state), self.check_type(*state)))

    def test_every_state_keeps_the_rules_at_the_normal_step(self):
        self.walk("normal", lambda *state: (self.check_rules(*state), self.check_type(*state)))

    def test_every_state_fits_a_small_window_at_the_largest_step(self):
        self.walk("larger", self.check_fits)

    def test_reading_text_stays_within_the_measure_at_1280(self):
        """1280×800 에서 지문·힌트·해설과 던전 소개의 글 폭은 글자 단계와 상관없이 640 이하(설계 10.1-3)."""
        def measure(name, view):
            pieces = [piece for piece in view.findChildren(TextPiece) if piece.isVisible()]
            self.assertTrue(pieces, name)
            for piece in pieces:
                self.assertLessEqual(piece.width(), 640, "%s %s" % (step, name))

        for step in theme.TEXT_STEPS:
            win = self.start(step, (1280, 800), [passed("p1")])
            measure("던전 소개", win.journey_map.intro)
            page = self.open("p1")
            guikit.click(page.hint_btn)
            for number, name in enumerate(("문제", "힌트", "해설")):
                page.tabs.setCurrentIndex(number)
                guikit.pump()
                measure(name, page.views[number])

    def corner_inks(self, card):
        """card 네 모서리 안쪽 1px 화소의 색. 스크롤 칸 안이면 모서리마다 그 자리가 보이게 굴린 뒤 창을 찍음."""
        inks, area = [], holder(card)
        for x, y in ((1, 1), (card.width() - 2, 1), (1, card.height() - 2), (card.width() - 2, card.height() - 2)):
            if area is not None:
                spot = card.mapTo(area.widget(), QPoint(x, y))
                area.ensureVisible(spot.x(), spot.y(), 24, 24)
                guikit.pump()
            inks.append(self.win.grab().toImage().pixelColor(card.mapTo(self.win, QPoint(x, y))))
        return inks

    def test_cards_keep_round_corners(self):
        """지도 두 카드, 지문 카드, 펼친 결과 카드의 네 모서리 안쪽 1px 은 바탕색임(설계 10.1-24). 카드 끝에 닿는 스크롤 칸이 면을
        칠하면 모서리가 네모가 됨."""
        mode = theme.state["mode"]
        self.addCleanup(theme.set_mode, mode)
        for scheme in ("light", "dark"):
            theme.set_mode(scheme)
            for size in ((1024, 700), (1280, 800)):
                win = self.start(size=size, log=[passed("p1")])
                cards = [("지도", win.journey_map.map_card), ("던전", win.journey_map.card)]
                inks = [(name, self.corner_inks(card)) for name, card in cards]
                page = self.open("p2")
                with mock.patch.object(win.journey, "run", fake_run([run_case(1), run_case(2, False)])):
                    guikit.click(page.run_btn)
                guikit.pump()
                self.assertFalse(page.result.collapsed)
                inks += [(name, self.corner_inks(card)) for name, card in (("지문", page.problem_card), ("결과", page.result))]
                for name, colors in inks:
                    self.assertEqual([True] * 4, [guikit.near(color, "bg") for color in colors],
                                     "%s %s %s: %s" % (scheme, size, name, [color.name() for color in colors]))

    def test_top_bar_keeps_its_buttons_and_the_tag_beside_the_name(self):
        """1024×700 위 막대(설계 10.1-26). 다섯 경우와 글자 세 단계를 봄. 돌아가기·칩 글자가 잘리지 않음. 꼬리표는 이름 바로 옆에 붙음.
        상태 글은 두 줄까지임. 화면이 1024 창을 넓히지 않음. 보통에서는 가장 긴 이름이 "저장했습니다" 옆에 다 보임."""
        for step in theme.TEXT_STEPS:
            win = self.start(step, log=[passed("p2")])
            for title, status, pid, number in TOP_CASES:
                original = win.journey.problem

                def problem(did, wanted, lang, title=title, number=number, original=original):
                    data = original(did, wanted, lang)
                    return dict(data, title=title or data["title"], no=number or data["no"])

                with mock.patch.object(win.journey, "problem", problem):
                    page = self.open(pid)
                page.show_node_note(True)
                page.set_status(status)
                guikit.pump()
                where = "%s %s · %s" % (step, page.title.text(), status)
                for button in [page.map_btn] + list(page.lang_btns.values()):
                    self.assertGreaterEqual(button.width(), button.sizeHint().width(), "%s: %s" % (where, button.text()))
                title_end = page.title.mapTo(page.top, QPoint(page.title.width(), 0)).x()
                tag = page.badge.mapTo(page.top, QPoint(0, 0)).x()
                self.assertTrue(0 <= tag - title_end <= 16, "%s: 꼬리표 %d, 이름 끝 %d" % (where, tag, title_end))
                self.assertLessEqual(page.status.height(), 2 * theme.TYPE["caption"][1], where)
                self.assertGreaterEqual(page.title.width(), min(120, page.title.sizeHint().width()), where)
                self.assertLessEqual(page.minimumSizeHint().width(), 1024, where)
                self.assertEqual((1024, 700), (win.width(), win.height()), where)
                if step == "normal" and (title, status) == (LONGEST, journey_text.SAVED):
                    self.assertEqual(LONGEST, QLabel.text(page.title), "보통에서는 가장 긴 이름이 줄지 않음")

    def test_result_captions_stay_on_one_line_at_1024(self):
        """결과 카드 머리 caption 은 1024 창의 결과 카드 글 칸에서 한 줄(설계 10.1-27). 접힌 카드 셋과 실행·채점 머리를 봄.
        채점 단계 문장은 grading 의 글이라 GEN_TEXT 는 빼고, 지난 시간을 붙인 문장은 더 크게에서 두 줄이 되어 보통·크게에서만 봄."""
        head = journey_text.result_head
        texts = [head(best=41.5), head(mine=12), head(), head("run", {"total": 99, "cases": [{}] * 98}, done=False),
                 head("run", {"cancelled": True}), head("run", {"fatal": {"line": 120}}), head("run", {"total": 99, "passed": 99}),
                 head("run", {"total": 99, "passed": 98}), head("grade", {}, done=False), head("grade", {}, done=False, stage=ACC_TEXT),
                 head("grade", {}, done=False, stage=EFF_TEXT), head("grade", {"cancelled": True}), head("grade", {"fatal": {"line": 120}}),
                 head("grade", GRADED)]
        timed = [head("grade", {}, done=False, stage=stage, seconds=3599) for stage in (ACC_TEXT, EFF_TEXT)]
        for step in theme.TEXT_STEPS:
            self.start(step)
            caption = self.open("p1").result.caption
            width = caption.width()
            caption.setText("가")
            line = caption.heightForWidth(width)
            for text in [item["caption"] for item in texts + (timed if step != "larger" else [])]:
                caption.setText(text)
                self.assertEqual(line, caption.heightForWidth(width), "%s %d: %s" % (step, width, text))


if __name__ == "__main__":
    unittest.main()
