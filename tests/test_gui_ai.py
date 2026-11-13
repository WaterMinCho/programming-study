# -*- coding: utf-8 -*-
"""AI 비전 개론 화면(gui/ai_home.py, ai_learn.py, ai_quiz.py, ai_text.py)과 첫 화면의 AI 줄, 공유 오답 노트의 AI 탭.
실제 MainWindow 를 띄우되 AI 은행은 고정 은행 tests/ai_bank(상황별 코드를 보는 클래스는 tests/ai_bank_pc 를 더한 사본, 마지막 클래스만
저장소의 ai/ 1~9차시와 상황별 코드), 여행·웹 은행은 고정 은행, 풀이 폴더·AI 로컬 폴더·설정은 임시 폴더, 제출 모듈과 Node 찾기는 가짜를 씀.
시계는 aiprep.service.now 를 바꿔 학습일을 정함.

하루 목표와 새 문항 상한은 화면에 없음(2026-11-03 사용자 결정). 모의고사 화면은 다음 PR 이라 보지 않음.
PyQt6 가 없으면 전부 건너뜀."""
import datetime
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import aifix, guikit  # noqa: E402

from PyQt6 import sip  # noqa: E402
from PyQt6.QtCore import QMimeData, QPoint, QPointF, QRect, QSettings, Qt, QUrl  # noqa: E402
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFontMetricsF  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QAbstractButton, QApplication, QLabel, QPushButton, QScrollArea, QWidget  # noqa: E402

import session  # noqa: E402
import study  # noqa: E402
from aiprep import bank as ai_bank  # noqa: E402
from aiprep import grade, plan, service  # noqa: E402
from gui import ai_learn, ai_quiz, ai_text, kit, motion, theme  # noqa: E402
from gui.widgets import LinkLabel  # noqa: E402
from gui.docview import MISSING_TEXT, TextPiece  # noqa: E402
from gui.window import MainWindow  # noqa: E402
from journey import bank as journey_bank  # noqa: E402
from journey import runner  # noqa: E402
from tests.test_gui_hub import FakeGitFlow  # noqa: E402
from tests.test_gui_kit import WindowSpy  # noqa: E402
from webprep import bank as web_bank  # noqa: E402
from webprep import stack  # noqa: E402

AI_FIXTURE = os.path.join(guikit.ROOT, "tests", "ai_bank")
JOURNEY_FIXTURE = os.path.join(guikit.ROOT, "tests", "journey_bank")
WEB_FIXTURE = os.path.join(guikit.ROOT, "tests", "web_bank")
REAL_GIF = os.path.join(guikit.ROOT, "ai", "learn", "l04", "assets", "4a-2.gif")  # 6장, 1120×600
FAKE_NODE = {"path": "/fake/node", "version": "22.23.2", "major": 22}
USER = "tester"
GOAL_WORDS = ("목표", "새 문항", "상한")  # 하루 목표를 말하는 낱말. 화면 어디에도 없어야 함


def visible_text(widget):
    """widget 아래 보이는 글(라벨, 글 조각, 단추)을 이어 붙인 글."""
    parts = []
    for child in widget.findChildren(QWidget):
        if not child.isVisible():
            continue
        if isinstance(child, TextPiece):
            parts.append(child.toPlainText())
        elif isinstance(child, (QLabel, QAbstractButton)):
            parts.append(child.text())
    return "\n".join(parts)


class AiTest(unittest.TestCase):
    real_bank = False
    pc = False  # 참이면 상황별 코드(뼈대 S90, 노트 l18, 묶음 pc)를 더한 고정 은행 사본을 씀

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gui_ai_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.clock = "2026-11-04T20:00:00"
        patches = [(study, "SUBMISSIONS_DIR", os.path.join(self.tmp, "submissions")), (study, "USER_FILE", os.path.join(self.tmp, ".study_user")),
                   (runner, "CACHE_DIR", os.path.join(self.tmp, "cache")), (journey_bank, "BANK_DIR", JOURNEY_FIXTURE),
                   (web_bank, "BANK_DIR", WEB_FIXTURE), (stack, "find_node", lambda saved=None, probe=False: FAKE_NODE),
                   (service, "now", lambda: self.clock), (service.secrets, "randbelow", lambda n: 7)]  # 묶음 시드를 고정함
        if self.pc:
            self.root = aifix.pc_bank(os.path.join(self.tmp, "ai_bank"))
            patches.append((ai_bank, "AI_DIR", self.root))
        elif not self.real_bank:
            patches.append((ai_bank, "AI_DIR", AI_FIXTURE))
        for target, name, value in patches:
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        os.environ.pop("STUDY_USER", None)
        os.environ["STUDY_WEB_HOME"] = os.path.join(self.tmp, "web_home")
        os.environ["STUDY_AI_HOME"] = os.path.join(self.tmp, "ai_home")
        os.environ["STUDY_PYTHON_HOME"] = os.path.join(self.tmp, "python_home")
        self.addCleanup(setattr, sys, "excepthook", sys.excepthook)
        self.logs = os.path.join(self.tmp, ".study_logs")
        from gui import errors
        errors.install(self.logs)
        self.errors = errors
        session.save_user(USER)
        guikit.prepare_consent(USER)
        self.git = FakeGitFlow()
        self.settings = QSettings(os.path.join(self.tmp, "settings.ini"), QSettings.Format.IniFormat)
        self.settings.setValue("onboarding/hub/v1", True)  # 첫 안내는 전용 화면 검사에서 확인함.
        self.win = None

    def tearDown(self):
        win = self.win
        if win is not None:
            guikit.wait_until(lambda: win.job is None)
            if win.dialog is not None:
                win.dialog.close()
            guikit.wait_until(lambda: win.pending_job is None)
            win.close()
            win.deleteLater()
            guikit.pump()
        if self.errors.state["dialog"] is not None:
            self.errors.state["dialog"].close()
        crashed = os.path.isdir(self.logs)
        report = "".join(study.read_text(os.path.join(self.logs, name)) for name in os.listdir(self.logs)) if crashed else ""
        self.assertFalse(crashed, report)

    # 도우미

    def boot(self, size=(1280, 800)):
        self.win = win = MainWindow(self.settings, lambda root, user: (self.git, ""), identity_factory=guikit.identity_factory)
        win.open_url = lambda url: None
        win.resize(*size)
        win.show()
        win.activateWindow()  # 창 단축키(←·→, Ctrl+Enter)와 초점이 offscreen 에서도 돌게 함
        win.boot()
        self.idle()
        return win

    def idle(self):
        guikit.pump()
        guikit.wait_until(lambda: self.win.job is None)
        guikit.pump()

    def page(self):
        return self.win.pages.currentWidget()

    def log(self, kind=None):
        path = os.path.join(study.SUBMISSIONS_DIR, USER, "ai", "record.json")
        rows = study.read_json(path)["log"] if os.path.isfile(path) else []
        return [r for r in rows if kind is None or r.get("kind") == kind]

    def at(self, day, clock="20:00:00"):
        self.clock = "2026-11-%02dT%s" % (day, clock)

    def item_view(self):
        practice = self.win.ai_quiz.practice
        return practice._view(practice.queue[practice.pos])["item"]

    def answer(self, right=True, sure=True):
        """연습 화면의 지금 문항에 칸을 채우거나 보기를 골라 [확실함]·[긴가민가]를 누름."""
        page = self.win.ai_quiz
        item = self.item_view()
        if page.item["kind"] == "blank":
            values = [b["answer"][0] if right else "모름" for b in item["blanks"]]
            for field, value in zip(page.inputs, values):
                field.setText(value)
        else:
            good = set(grade.right_options(item))
            rows = [n for n, option in enumerate(page.item["options"]) if (option["no"] in good) == right]
            for n in (rows if right else rows[:1]):
                page.choices.rows[n].box.setChecked(True)
        guikit.click(page.sure_btn if sure else page.unsure_btn)

    def read_all(self, day=2):
        """그날 두 단원을 끝까지 읽은 기록."""
        self.at(day)
        for key in ("90a", "90b"):
            self.win.ai.mark_read("i90", key)


class HubAndHomeTest(AiTest):
    def test_hub_row_week_chart_and_track_colour(self):
        win = self.boot()
        hub = win.hub
        self.assertEqual((hub.ai_row.title.text(), hub.ai_row.second.text()), ("AI", "개론 · 90차시 첫째 단원부터 읽습니다."))  # 이어서 할 일 카드와 같은 단원
        self.assertFalse(hub.ai_row.inert)
        self.assertEqual(len(hub.chart.days[-1]), 5)  # 날짜와 트랙 넷
        self.assertEqual(theme.SERIES[-1], "series_ai")
        self.assertEqual([row.title.text() for _, row in hub.note_rows], ["파이썬 스터디", "AI"])
        guikit.click(hub.ai_row)
        self.assertEqual((self.page(), win.area), (win.ai_home, "ai"))
        guikit.click(win.ai_home.hub_btn)
        self.assertIs(self.page(), hub)

    def test_broken_record_shows_the_band_and_switches_the_row_off(self):
        path = os.path.join(study.SUBMISSIONS_DIR, USER, "ai", "record.json")
        study.write_text(path, "{ 깨진 기록")
        win = self.boot()
        hub = win.hub
        self.assertIsNone(win.ai)
        self.assertTrue(hub.ai_error.isVisible())
        self.assertIn("record.json", hub.ai_error.text.text())
        self.assertTrue(hub.ai_row.inert)
        self.assertEqual(hub.ai_row.second.text(), "기록을 읽지 못했습니다.")
        self.assertFalse(hub.journey_row.inert)

    def test_home_has_no_daily_goal_and_shows_lessons(self):
        win = self.boot((1024, 700))
        win.go_ai()
        home = win.ai_home
        self.assertTrue(home.info.text().startswith("12월 2일 시험까지 28일"))
        text = visible_text(home)
        for word in GOAL_WORDS:
            self.assertNotIn(word, text)
        self.assertEqual([row.title.text() for row in home.lesson_list.rows], ["90차시 시험 차시"])
        self.assertEqual(home.lesson_list.rows[0].second.text(), "단원 2개 중 0개 읽음")
        self.assertEqual(home.lesson_list.more_btn.text(), "준비 중 1개 보기")
        self.assertFalse(home.pattern_section.isVisibleTo(home))  # 상황별 코드 무리가 없는 은행이면 구역을 그리지 않음
        self.assertEqual([row.title.text() for row in home.books.rows], ["섞어 풀기", "90차시 문제집", "오답 노트"])
        self.assertTrue(home.mixed_row.inert)  # 읽은 단원이 없으면 섞어 풀 문항이 없음
        self.assertEqual(home.mixed_row.second.text(), ai_text.MIXED_EMPTY)
        book = home.books.rows[1]
        self.assertFalse(book.inert)  # 차시 문제집은 단원을 읽지 않아도 풂
        self.assertRegex(book.second.text(), r"^복습 확인 전 · 전체 \d+묶음$")
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(home)], ["학습 시작"])
        button = home.next_btn
        self.assertTrue(win.rect().contains(button.mapTo(win, QPoint(button.width(), button.height()))), "주 단추가 스크롤 없이 보임")
        self.assertEqual((home.next_card.title.text(), home.next_card.line.text()),
                         ("90차시 첫째 단원 읽기", "「기울기로 걸음 정하기」\n읽은 뒤 이 단원 문항부터 풉니다. 약 5분."))  # 할 일이 제목, 단원 제목은 둘째 줄

        def top(widget):
            return widget.mapTo(home, QPoint(0, 0)).y()
        steps = home.guide_btn
        terms = next(w for w in home.findChildren(QLabel) if w.text() == ai_text.TERMS)
        # 사용 안내 단추, 카드, 학습 단원, 낱말 풀이, 문제집 줄 순임.
        self.assertEqual(sorted([steps, home.next_card, home.lesson_list, terms, home.books], key=top),
                         [steps, home.next_card, home.lesson_list, terms, home.books])
        guikit.click(book)
        self.assertEqual((self.page(), win.ai_quiz.title.text()), (win.ai_quiz, "90차시 풀기"))

    def test_next_card_cases_in_order(self):
        """이어서에는 중단한 단원·연습을 두고 날짜별 복습 추천은 별도로 유지함."""
        win = self.boot()
        win.go_ai()
        home = win.ai_home

        def card():
            win.go_ai()
            return home.target["kind"], home.next_card.title.text(), home.next_btn.text()

        self.assertEqual(card(), ("unit", "90차시 첫째 단원 읽기", "학습 시작"))
        self.at(2)
        win.ai.save_step("i90", "90a", 4)
        win.ai.mark_read("i90", "90a")
        self.assertEqual(card(), ("unit", "90차시 첫째 단원 읽기", "이어서 학습"))
        self.assertEqual(home.target["step"], 4)
        win.open_ai_practice("unit", lesson="i90", unit="90a")
        self.answer(right=False)
        self.assertEqual(card()[0::2], ("practice", "이어서 풀기"))
        self.assertEqual(win.ai.overview()["next"]["kind"], "again")
        self.at(3)
        self.assertGreater(win.ai.overview()["due"], 0)
        self.assertEqual(card()[0], "practice")
        with mock.patch.object(plan, "REVIEW_FIRST", 1):
            self.assertEqual(card()[0], "practice")
            self.assertEqual(win.ai.overview()["next"]["kind"], "review")
        win.ai.mark_read("i90", "90b")
        self.assertEqual(card()[0::2], ("practice", "이어서 풀기"))
        guikit.click(home.next_btn)
        self.assertEqual((self.page(), win.ai_quiz.title.text()), (win.ai_quiz, "90차시 · 기울기로 걸음 정하기"))
        while win.ai_quiz.item is not None:
            if win.ai_quiz.feedback is None:
                self.answer()
            guikit.click(win.ai_quiz.next_btn)
        self.assertEqual(card(), ("unit", "90차시 둘째 단원 읽기", "학습 시작"))
        guikit.click(home.next_btn)
        self.assertEqual((self.page(), win.ai_learn.key), (win.ai_learn, "90b"))

    def test_hub_summary_counts_ai_review(self):
        win = self.boot()
        self.read_all(2)
        win.open_ai_practice("mixed")
        while win.ai_quiz.item is not None:
            if win.ai_quiz.feedback is None:
                self.answer()
            guikit.click(win.ai_quiz.next_btn)
        self.at(3)
        win.go_hub()
        due = win.ai.overview()["due"]
        self.assertGreater(due, 0)
        self.assertEqual(win.hub.summary.text(), "AI 복습 %d개가 있습니다." % due)
        self.assertTrue(win.hub.ai_row.second.text().endswith("복습 %d문항" % due))

    def test_home_rows_switch_off_while_busy(self):
        """문제 받기가 기록을 쓰는 동안 문제집 줄도 모두 꺼짐. 끝나면 섞어 풀기는 읽은 단원이 있을 때만 다시 켜짐."""
        win = self.boot()
        win.go_ai()
        home = win.ai_home
        home.set_busy(True)
        self.assertTrue(all(row.inert for row in home.books.rows + home.lesson_list.rows))
        guikit.click(home.books.rows[1])
        self.assertIs(self.page(), home)
        home.set_busy(False)
        self.assertEqual([row.inert for row in home.books.rows], [True, False, False])
        self.read_all(4)
        win.go_ai()
        home.set_busy(True)
        guikit.click(home.mixed_row)
        self.assertIs(self.page(), home)
        home.set_busy(False)
        self.assertFalse(home.mixed_row.inert)

    def test_broken_record_clears_the_home_numbers(self):
        """홈을 연 뒤 기록이 깨지면 띠에 이유를 보이고, 지난 수치(알림 줄, 공개된 차시 수, 문제집 줄 둘째 줄)를 남기지 않음."""
        win = self.boot()
        self.read_all(4)
        win.go_ai()
        home = win.ai_home
        self.assertTrue(home.info.text() and home.lesson_count.text())
        path = os.path.join(study.SUBMISSIONS_DIR, USER, "ai", "record.json")
        study.write_text(path, "{ 깨진 기록, 길이를 바꿔 다시 읽게 함")
        home.refresh()
        self.assertTrue(home.notice.isVisible())
        self.assertFalse(home.info.isVisible())
        self.assertEqual(home.lesson_count.text(), "")
        self.assertTrue(home.books.rows and all(row.inert and not row.second.text() for row in home.books.rows))

    def test_hub_next_card_opens_the_ai_unit_after_ai_was_used_last(self):
        win = self.boot()
        self.clock = "%sT21:00:00" % datetime.date.today().isoformat()  # 막대는 달력의 오늘을 봄
        win.ai.mark_read("i90", "90a")
        win.go_hub()
        hub = win.hub
        self.assertEqual((hub.next_card.title.text(), hub.next_btn.text()), ("90차시 첫째 단원 읽기", "이어서 학습"))  # 중단한 단원이 먼저임.
        self.assertIn("기울기로 걸음 정하기", hub.next_card.line.text())
        self.assertTrue(hub.next_card.line.text().startswith("AI · "))
        self.assertEqual(hub.chart.days[-1][4], 1)  # 끝까지 읽은 단원 하나
        guikit.click(hub.next_btn)
        self.assertEqual((self.page(), win.ai_learn.key), (win.ai_learn, "90a"))


class TextTest(unittest.TestCase):
    """화면 글을 만드는 함수(gui/ai_text.py)와 글 나누기(ai_learn.split_boxes, ai_quiz.split_stem)."""

    def test_refs_read_like_sentences(self):
        cases = {"4차시 슬 p21~p22": "4차시 슬라이드 21~22쪽", "2차시 슬 p5": "2차시 슬라이드 5쪽", "1차시 노트북 02 [30]": "1차시 노트북 02 셀 30",
                 "3차시 과제 2번": "3차시 과제 2번", "요약 1주차 p5": "강사 요약본 1주차 5쪽", "대학원 04 p26": "대학원 강의안 04 26쪽",
                 "10차시 강의노트 [3]": "10차시 강의 노트", "공식 13차시": "공식 커리큘럼 13차시", "문서 torch.no_grad": "공식 문서 torch.no_grad",
                 "5차시 슬 p21 그림": "5차시 슬라이드 21쪽 그림"}
        for ref, text in cases.items():
            self.assertEqual(ai_text.ref_one(ref), text)
        self.assertEqual(ai_text.ref_text(["2차시 슬 p5", "요약 1주차 p5"]), "2차시 슬라이드 5쪽 · 강사 요약본 1주차 5쪽")
        line = ai_text.errata_text([{"id": "X90-01", "where": "90차시 슬 p3", "right": "기록 말투의 출제 메모"}])
        self.assertIn("오류를 바로잡은 문항", line)
        self.assertNotIn("슬라이드", line)
        self.assertNotIn("출제 메모", line)  # errata 의 right 는 출제 기록이라 화면에 쓰지 않음

    def test_boxes_and_code_parts_are_split_out(self):
        text = "글\n\n> **[정정]** 슬라이드는 틀렸습니다.\n> 둘째 줄\n\n```python\n> 코드 안\n```\n\n> 그냥 인용"
        parts = ai_learn.split_boxes(text)
        self.assertEqual([p[0] for p in parts], ["text", "box", "text"])
        self.assertEqual(parts[1][1:], ("정정", "슬라이드는 틀렸습니다.\n둘째 줄"))
        self.assertIn("> 코드 안", parts[2][1])
        stem = "앞 글 `x.____`\n\n```python\nx = 1\n```\n\n```python\ny.____()\n```\n끝"
        self.assertEqual([p[0] for p in ai_quiz.split_stem(stem)], ["text", "code", "text"])
        self.assertIn("x = 1", ai_quiz.split_stem(stem)[0][1])  # 빈칸 없는 코드 울타리는 글에 남음

    def test_counts_use_one_name_each(self):
        """외운 문항은 "외운 문항 N/M", 복습은 "복습 N문항" 한 꼴로 씀. 학습 단원 줄은 읽은 단원 수만."""
        row = {"units_total": 3, "read": 1, "memorised": 2, "families": 9, "due": 4, "state": "level1"}
        self.assertEqual(ai_text.book_line(row), "복습 확인 2/9묶음 · 복습 4문항")
        self.assertEqual(ai_text.lesson_line(row), "단원 3개 중 1개 읽음")
        unit = {"read": True, "memorised": 0, "families": 5, "due": 3, "minutes": 5}
        self.assertEqual(ai_text.unit_line(unit), "읽기 마침 · 복습 확인 전 · 전체 5묶음 · 복습 3문항 · 약 5분")
        self.assertIn("단원 연습 미완료", ai_text.unit_line(dict(unit, practiced=False)))
        self.assertIn("단원 연습 마침", ai_text.unit_line(dict(unit, practiced=True)))
        self.assertIn("복습 확인 전", ai_text.unit_line(dict(unit, practiced=True)))
        self.assertEqual(ai_text.recent_label({"kind": "set", "n": 3, "first_pass": 1}), "AI 연습 1/3")
        self.assertEqual(ai_text.requeue_line(False, 3), "이 문항은 3문항 뒤에 다시 나옵니다.")
        self.assertEqual(ai_text.requeue_line(False, 0), "이 문항은 바로 다음에 다시 나옵니다.")
        self.assertTrue(ai_text.requeue_line(True, 5).startswith("한 번 더 맞히면 이 묶음에서 빠집니다."))

    def test_unit_line_reads_the_lesson_date_not_the_engine_sentence(self):
        overview = {"lessons": [{"id": "i05", "date": "2026-11-04", "units": [{"key": "5a", "minutes": 7}]}]}
        item = {"lesson": "i05", "unit": "5a", "why": "엔진 문장이 바뀌어도 됨"}
        self.assertEqual(ai_text.unit_why(item, overview, datetime.date(2026, 11, 5)), "어제 수업한 차시입니다. 읽은 뒤 이 단원 문항부터 풉니다. 약 7분.")
        self.assertTrue(ai_text.unit_why(item, overview, datetime.date(2026, 11, 4)).startswith("오늘 수업한 차시입니다. "))
        self.assertEqual(ai_text.unit_why(item, overview, datetime.date(2026, 11, 9)), "읽은 뒤 이 단원 문항부터 풉니다. 약 7분.")
        mock_next = dict(overview, next={"kind": "mock", "mock": "m1", "title": "모의고사 1회 · 30문항 · 60분", "count": 30})
        card = ai_text.next_item(mock_next, datetime.date(2026, 11, 14))
        self.assertEqual((card["title"], card["action"], card['mock']), ("모의고사 1회 · 30문항 · 60분", '모의고사 열기', 'm1'))

    def test_unit_card_title_says_what_to_do(self):
        """안 읽은 단원 카드 제목은 "N차시 첫째 단원 읽기"(상황별 코드는 "학습 루프 단원 읽기")이고 단원 제목은 둘째 줄 맨 앞."""
        overview = {"lessons": [{"id": "i05", "no": 5, "date": "", "ready": True, "units_total": 2, "read": 0,
                                 "units": [{"key": "5a", "title": "가", "minutes": 7}, {"key": "5b", "title": "나", "minutes": 4}]}],
                    "patterns": [{"id": "pc", "units": [{"key": "18a", "name": "학습 루프", "title": "한 에폭", "minutes": 6}]}]}
        today = datetime.date(2026, 11, 9)

        def card(lesson, unit):
            item = {"kind": "unit", "lesson": lesson, "unit": unit, "title": "엔진 제목", "name": "엔진 이름"}
            out = ai_text.next_item(dict(overview, next=item), today)
            return out["title"], out["line"], out["action"]
        self.assertEqual(card("i05", "5b"), ("5차시 둘째 단원 읽기", "「나」\n읽은 뒤 이 단원 문항부터 풉니다. 약 4분.", "학습 시작"))
        self.assertEqual(card("pc", "18a"), ("학습 루프 단원 읽기", "「한 에폭」\n읽은 뒤 이 단원 문항부터 풉니다. 약 6분.", "학습 시작"))
        self.assertEqual(card("i05", "5z")[:2], ("엔진 이름", "읽은 뒤 이 단원 문항부터 풉니다. 약 5분."))  # 찾지 못하면 서비스가 준 이름
        # 읽은 단원이 없을 때 허브 줄은 카드가 권하는 단원을 씀. 카드가 단원이 아니면 START_LINE
        unit_next = dict(overview, next={"kind": "unit", "lesson": "i05", "unit": "5b"})
        self.assertEqual(ai_text.track_line(unit_next), "5차시 둘째 단원부터 읽습니다.")
        self.assertEqual(ai_text.track_line(dict(overview, next={"kind": "again", "count": 2})), ai_text.START_LINE)

    def test_same_row_labels_are_numbered_by_card(self):
        items = ai_text.numbered([{"key": "i01-s03", "label": "고르기 · 같은 지문"}, {"key": "i01-s01", "label": "고르기 · 같은 지문"},
                                  {"key": "i01-b01", "label": "빈칸 · 다른 지문"}])
        self.assertEqual([i["label"] for i in items], ["고르기 · 같은 지문 (2)", "고르기 · 같은 지문 (1)", "빈칸 · 다른 지문"])

    def test_note_html_lines(self):
        item = {"lines": ["2번 틀림", "확실하다고 했지만 틀림"], "ref": [], "stem": "지문", "options": ["가", "나"], "mine": ["가"]}
        html_text = ai_text.note_html(item, {"answer": ["가"], "explain": "", "why": {}}, "옳지 않은 문장")
        self.assertIn("2번 틀림 · 확실하다고", html_text)
        self.assertIn("옳지 않은 문장: 가", html_text)
        self.assertEqual(ai_text.answer_word({"kind": "choice", "pick": "wrong"}), "옳지 않은 문장")
        self.assertEqual(ai_text.answer_word({"kind": "blank", "pick": None}), "정답")
        lines = ai_text.summary_lines({"first_today": 2, "again_day": 1, "up": 0, "down": 0, "memorised": 0, "sure_wrong": 0, "left": [],
                                       "next": None, "early": 0}, unlisted=1)
        self.assertEqual(lines, ["오늘 새로 접한 문항 중 이번 묶음에서 마친 문항 2개", "이전 학습일에 풀었던 문항 중 이번 첫 답에 맞힌 문항 1개",
                                 "단원을 읽은 날 틀린 1문항은 오답 노트에 넣지 않고 다음 복습에서 다시 냅니다."])

    def test_pattern_texts(self):
        """상황별 코드 줄, 나란히 보기 caption, 함께 가린 칸 줄, 뼈대 카드 오답 노트 줄과 코드 보기 HTML, 단원 이름을 쓰는 이어서 할 일."""
        unit = {"after_no": 6, "read": False, "minutes": 6, "memorised": 0, "families": 8, "due": 0}
        self.assertEqual(ai_text.pattern_line(unit), "6차시 뒤에 권함 · 약 6분")
        self.assertEqual(ai_text.pattern_line(dict(unit, read=True, due=2)), "6차시 뒤에 권함 · 읽기 마침 · 복습 확인 전 · 전체 8묶음 · 복습 2문항")
        self.assertEqual(ai_text.diff_caption(2, 13), "다른 줄 2개 · 같은 줄 13개")
        self.assertEqual(ai_text.also_line([1, 3]), "①·③ 칸은 틀렸습니다. 그 칸을 묻는 문항이 내일 복습에 나옵니다.")
        self.assertEqual(ai_text.card_head({"kind": "skel", "head": "opt.____()"}, None), "opt.____()")
        today = datetime.date(2026, 11, 9)
        overview = {"lessons": [], "patterns": [{"id": "pc", "units": [{"key": "18a", "minutes": 6}]}],
                    "next": {"kind": "revisit", "lesson": "pc", "unit": "18a", "title": "다시 보기 · 학습 루프 · 한 에폭", "name": "학습 루프 · 한 에폭"}}
        self.assertEqual(ai_text.next_item(overview, today)["title"], "학습 루프 · 한 에폭")
        self.assertEqual(ai_text.unit_why({"lesson": "pc", "unit": "18a"}, overview, today), "읽은 뒤 이 단원 문항부터 풉니다. 약 6분.")
        item = {"lines": [], "ref": [], "stem": "```python\na.____()\nb.____()\n```", "options": ["x = 1\ny = 2", "y = 2\nx = 1"],
                "mine": ["y = 2\nx = 1"], "code_options": True}
        html_text = ai_text.note_html(item, {"answer": ["x = 1\ny = 2"], "explain": "", "why": {"y = 2\nx = 1": "순서가 거꾸로입니다."}})
        self.assertIn("a.①____()\nb.②____()", html_text)  # 울타리 안 빈칸에도 번호
        self.assertEqual(html_text.count('class="codebox"'), 5)  # 지문, 보기 둘, 내 답, 정답
        self.assertIn("<p>2번: 순서가 거꾸로입니다.</p>", html_text)

    def test_track_line_has_no_daily_goal(self):
        overview = {"lessons": [{"ready": True, "units_total": 7, "read": 3}], "memorised": 0, "due": 4,
                    "plan": {"days_left": 28, "units_today": 7, "goal": False}, "today_answers": 0, "today_extra": 0}
        self.assertEqual(ai_text.track_line(overview), "단원 7개 중 3개 읽음 · 복습 4문항")
        self.assertEqual(ai_text.exam_line(overview, datetime.date(2026, 11, 4)), "12월 2일 시험까지 28일")


class LessonAndLearnTest(AiTest):
    def test_lesson_page_rows_and_lesson_practice(self):
        win = self.boot()
        win.go_ai()
        guikit.click(win.ai_home.lesson_list.rows[0])
        page = win.ai_lesson
        self.assertIs(self.page(), page)
        self.assertEqual(page.title.text(), "90차시 시험 차시")
        rows = [(row.title.text(), row.second.text(), row.end.text()) for row in page.unit_list.rows]
        self.assertEqual(rows, [("기울기로 걸음 정하기", "읽기 전 · 단원 연습 미완료 · 약 5분", ""),
                                ("과적합 알아보기", "읽기 전 · 단원 연습 미완료 · 약 4분", "심화 있음")])
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(page)], ["이 차시 풀기"])
        guikit.click(page.practice_btn)
        quiz = win.ai_quiz
        self.assertEqual((self.page(), quiz.title.text()), (quiz, "90차시 풀기"))
        self.assertEqual(self.log("open")[-1]["lesson"], "i90")
        guikit.click(quiz.back_btn)
        self.assertIs(self.page(), win.ai_home)

    def open_unit(self, key="90a", step=None):
        win = self.win
        self.assertTrue(win.open_ai_unit("i90", key, step))
        guikit.pump()
        return win.ai_learn

    def test_steps_blocks_and_the_last_step(self):
        win = self.boot()
        learn = self.open_unit()
        self.assertEqual(learn.back_btn.text(), "← 90차시")
        self.assertEqual(learn.title.text(), "기울기로 걸음 정하기")
        self.assertEqual(learn.stepper.steps, [(1, "먼저", "now"), (2, "", "todo"), (3, "", "todo"), (4, "복습 질문", "todo")])
        self.assertFalse(learn.prev_btn.isEnabled())
        guess = learn.view.findChildren(ai_learn.GuessBlock)[0]
        self.assertIsInstance(guess.choices.rows[0].box, ai_learn.RadioMark)  # 하나 고르기는 둥근 표시
        self.assertFalse(guess.note.isVisible())
        guikit.click(guess.choices.rows[1])
        self.assertEqual(guess.choices.picked(), [1])
        self.assertEqual(guess.note.text(), "2단계에서 답을 확인합니다.")  # 고르는 순간 기록하고 알림
        self.assertEqual(self.log("guess")[-1]["picked"], 1)
        guikit.click(guess.choices.rows[2])
        self.assertEqual(guess.choices.picked(), [2])  # 하나만 골라지고 단계를 떠나기 전까지 바꿀 수 있음
        guikit.click(guess.choices.rows[2])
        self.assertEqual(guess.choices.picked(), [2])  # 고른 보기를 다시 눌러도 꺼지지 않음
        self.assertEqual([r["picked"] for r in self.log("guess")], [1, 2])
        guikit.click(learn.next_btn)
        self.assertEqual(learn.stepper.steps[0][2], "done")
        reveal = learn.view.findChildren(ai_learn.RevealBlock)[0]
        self.assertIn("처음 고른 답", visible_text(reveal))
        self.assertIn("키웁니다.", visible_text(reveal))
        recall = learn.view.findChildren(ai_learn.RecallBlock)[0]
        guikit.click(recall.check_btn)  # 빈 칸은 채점하지 않고 안내만 함
        self.assertTrue(recall.empty_note.isVisible())
        self.assertFalse(recall.result.isVisible() or self.log("recall"))
        recall.field.setText("3")
        QTest.keyClick(recall.field, Qt.Key.Key_Return)
        self.assertEqual(recall.verdict.text(), "틀렸습니다")
        self.assertIn("정답: **2.8**", visible_text(recall))  # 라벨의 text() 는 넣은 마크다운 그대로
        self.assertEqual(self.log("recall")[-1]["ok"], False)
        self.assertEqual(recall.field.property("tone"), "danger")
        why = learn.view.findChildren(ai_learn.WhyBlock)[0]
        self.assertFalse(why.answer.isVisible())
        guikit.click(why.button)
        self.assertTrue(why.answer.isVisible())
        self.assertEqual(why.button.text(), "답 접기")
        guikit.click(learn.next_btn)
        text = "\n".join(piece.toPlainText() for piece in learn.view.findChildren(TextPiece))
        self.assertIn("optimizer.zero_grad()", text)  # python 코드 블록이 보임
        self.assertNotIn("facts:", text)
        self.assertNotIn("<!--", text)
        self.assertNotIn("정정", [badge.text() for badge in learn.view.findChildren(QLabel)])
        self.assertFalse(self.log("learn"))
        self.assertEqual(learn.memo_btn.text(), "복습 질문")
        self.assertIn("이 단원", learn.memo_btn.toolTip())
        guikit.click(learn.memo_btn)
        self.assertEqual(learn.index, 3)
        self.assertFalse(learn.memo_btn.isVisible())
        self.assertEqual(learn.next_btn.text(), "연습 시작")
        self.assertFalse(self.log("learn"))
        memo = learn.view.findChildren(ai_learn.MemoBlock)[0]
        answer = memo.layout().itemAt(1).widget()
        self.assertFalse(answer.isVisible())
        guikit.click(memo.rows[0])
        self.assertTrue(answer.isVisible())
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(learn)], ["연습 시작"])
        guikit.click(learn.next_btn)
        self.assertEqual((self.page(), win.ai_quiz.title.text()), (win.ai_quiz, "90차시 · 기울기로 걸음 정하기"))
        self.assertEqual(len(self.log("learn")), 1)  # 마지막 단계를 다시 보아도 한 번만 기록
        learn = self.open_unit(step=1)
        guess = learn.view.findChildren(ai_learn.GuessBlock)[0]
        self.assertEqual(guess.choices.picked(), [2])  # 다시 열면 고른 보기가 보이고 잠김
        self.assertFalse(guess.choices.rows[0].box.isEnabled())
        guikit.click(learn.memo_btn)
        self.assertEqual(len(self.log("learn")), 1)  # 이미 읽은 단원을 다시 끝까지 보아도 읽기 기록은 하나

    def test_step_keys_and_the_recall_field(self):
        """←·→ 는 단계를 넘기되 떠올리기 칸에서는 글자 커서를 옮기고, 그때 단계는 Alt+←·→ 로만 넘김. 중간 자리는 로컬에 남음."""
        self.boot()
        learn = self.open_unit(step=2)
        self.assertEqual(learn.index, 1)
        QTest.keyClick(learn.next_btn, Qt.Key.Key_Right)
        self.assertEqual(learn.index, 2)
        QTest.keyClick(learn.next_btn, Qt.Key.Key_Left)
        self.assertEqual(learn.index, 1)
        field = learn.view.findChildren(ai_learn.RecallBlock)[0].field
        field.setFocus()
        field.setText("12")
        QTest.keyClick(field, Qt.Key.Key_Left)
        self.assertEqual((learn.index, field.cursorPosition()), (1, 1))
        QTest.keyClick(field, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(learn.index, 2)
        state = json.loads(study.read_text(os.path.join(os.environ["STUDY_AI_HOME"], USER, "state.json")))
        self.assertEqual(state["at_step"]["i90/90a"], 3)
        learn = self.open_unit()
        self.assertEqual(learn.index, 2)  # 지난번 자리에서 엶
        learn = self.open_unit(step=2)
        figure = learn.view.figures[0]
        self.assertEqual((figure.prev_btn.text(), figure.next_btn.text()), ("이전 장", "다음 장"))  # 단계 넘김 [이전]·[다음]과 다른 이름
        figure.setFocus()
        QTest.keyClick(figure, Qt.Key.Key_Right)
        self.assertEqual((learn.index, figure.frame()), (1, 1))  # 그림에 초점이 있으면 → 는 장
        QTest.keyClick(figure, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(learn.index, 0)  # Alt+← 는 단계

    def test_boxes_scopes_and_trend(self):
        self.boot()
        learn = self.open_unit("90b", step=2)
        badges = [b.text() for b in learn.view.findChildren(QLabel) if b.isVisible()]
        self.assertEqual(badges.count("보충 설명"), 2)  # 단계 꼬리표와 인용 상자
        self.assertEqual(learn.view.title.text(), "검증 자료를 따로 두는 까닭")  # 꼬리표가 말하는 앞머리는 뺌
        learn.show_step(2)
        guikit.pump()
        self.assertIn("심화", [b.text() for b in learn.view.findChildren(QLabel) if b.isVisible()])
        learn.show_step(3)
        guikit.pump()
        trend = learn.view.findChildren(ai_learn.TrendBlock)[0]
        self.assertFalse(trend.doc.isVisible())
        guikit.click(trend.row)
        self.assertTrue(trend.doc.isVisible())

    def test_figure_waits_until_scrolled_into_view_before_autoplay(self):
        self.addCleanup(setattr, motion, "enabled", motion.enabled)
        motion.enabled = True
        content = QWidget()
        column = kit.box(content)
        spacer = QWidget()
        spacer.setFixedHeight(1000)
        column.addWidget(spacer)
        figure = ai_learn.AiFigure(REAL_GIF, "그림 2", [{"text": "설명", "ms": 2000}] * 6)
        column.addWidget(figure)
        holder = QScrollArea()
        holder.setWidget(content)
        holder.setWidgetResizable(True)
        holder.resize(700, 600)
        holder.show()
        self.addCleanup(holder.close)
        guikit.pump(100)
        self.assertFalse(figure.playing)
        self.assertEqual(0, figure.frame())
        holder.ensureWidgetVisible(figure.picture)
        guikit.pump(100)
        self.assertTrue(figure.playing)

    def test_queued_autoplay_rechecks_visibility_and_reduced_motion(self):
        self.addCleanup(setattr, motion, "enabled", motion.enabled)
        for interrupted in ("scroll", "reduced_motion"):
            with self.subTest(interrupted=interrupted):
                motion.enabled = True
                content = QWidget()
                column = kit.box(content)
                spacer = QWidget()
                spacer.setFixedHeight(1000)
                column.addWidget(spacer)
                image = ai_learn.AiFigure(REAL_GIF, "그림", [{"text":"설명", "ms":2000}] * 6)
                column.addWidget(image)
                holder = QScrollArea()
                holder.setWidget(content)
                holder.setWidgetResizable(True)
                holder.resize(700, 600)
                holder.show()
                self.addCleanup(holder.close)
                guikit.pump(30)
                queued = []
                with mock.patch.object(ai_learn, "QTimer") as timer:
                    timer.singleShot.side_effect = lambda delay, callback: queued.append(callback)
                    holder.ensureWidgetVisible(image.picture)
                    guikit.pump(30)
                self.assertTrue(queued)
                if interrupted == "scroll":
                    holder.verticalScrollBar().setValue(0)
                    guikit.pump(30)
                else:
                    motion.enabled = False
                for callback in queued:
                    callback()
                self.assertFalse(image.playing)
                self.assertEqual(0, image.frame())
                if interrupted == "scroll":
                    holder.ensureWidgetVisible(image.picture)
                    guikit.pump(30)
                    self.assertTrue(image.playing)
                    self.assertFalse(image.autoplay_pending)
                holder.close()
                guikit.pump(20)

    def test_figure_autoplays_once_and_moves_the_frame_line(self):
        """그림은 한 번 재생한 뒤 멈추고, 수동으로 장을 옮기면 장 설명도 바뀜. 뒤로 한 장 갈 때 frame_changed 는 한 번."""
        self.addCleanup(setattr, motion, "enabled", motion.enabled)
        motion.enabled = True
        frames = [{"text": "%d장 설명" % n, "ms": 2000} for n in range(1, 7)]
        figure = ai_learn.AiFigure(REAL_GIF, "그림 2", frames)
        holder = kit.page(QScrollArea())
        holder.setWidget(figure)
        holder.setWidgetResizable(True)
        holder.resize(700, 600)
        holder.show()
        self.addCleanup(holder.close)
        guikit.pump(200)
        self.assertEqual((figure.frame(), figure.playing, figure.frame_text.text()), (0, True, "1장 설명"))
        for _ in range(5):
            figure._tick()
        self.assertFalse(figure.playing)
        figure.hide()
        figure.show()
        guikit.pump(20)
        self.assertFalse(figure.playing)
        figure.go(5)
        self.assertEqual((figure.counter.text(), figure.frame_text.text()), ("6 / 6", "6장 설명"))
        calls = []
        figure.frame_changed = lambda n: (calls.append(n), figure.show_frame(n))
        figure.prev()
        self.assertEqual((calls, figure.frame_text.text()), ([4], "5장 설명"))
        figure.setFocus()
        QTest.keyClick(figure, Qt.Key.Key_Right)
        self.assertEqual(figure.frame(), 5)
        shown = figure.picture.pixmap().deviceIndependentSize()
        self.assertGreater(shown.height(), 300)
        self.assertAlmostEqual(shown.width() / shown.height(), figure.source.width() / figure.source.height(), delta=0.01)

    def test_figure_buttons_stay_put_when_frame_lines_differ(self):
        """장 설명 줄 수가 장마다 달라도 설명 칸이 가장 긴 설명의 높이를 지켜 넘김 줄과 캡션이 움직이지 않음. 폭이 바뀌면 다시 잼."""
        self.addCleanup(theme.set_text, theme.state["text"])
        theme.set_text("large")
        long = "길게 쓴 장 설명입니다. " * 12
        frames = [{"text": long if n in (0, 3) else "%d장" % (n + 1), "ms": 2000} for n in range(6)]
        figure = ai_learn.AiFigure(REAL_GIF, "그림 2", frames)
        holder = kit.page(QScrollArea())
        holder.setWidget(figure)
        holder.setWidgetResizable(True)
        holder.resize(700, 700)
        holder.show()
        self.addCleanup(holder.close)
        guikit.pump(100)
        places = set()
        for n in range(6):
            figure.go(n)
            guikit.pump(20)
            places.add((figure.controls.y(), figure.caption.y(), figure.height()))
        self.assertEqual(len(places), 1, places)
        figure.go(3)
        guikit.click(figure.prev_btn)  # 가운데 장에서 뒤로(QMovie 가 0번 장으로 못 돌아가던 곳)
        self.assertEqual((figure.frame(), figure.counter.text()), (2, "3 / 6"))
        guikit.click(figure.first_btn)
        self.assertEqual(figure.frame(), 0)
        held = figure.frame_text.height()
        self.assertGreater(held, theme.TYPE["body"][1] * 2)  # 짧은 장에서도 긴 설명의 높이
        holder.resize(1100, 700)
        guikit.pump(100)
        self.assertLess(figure.frame_text.minimumHeight(), held)  # 넓어지면 줄 수가 줄어 다시 잼

    def test_full_note_marks_the_guess_answer_and_keeps_units_above_steps(self):
        """전체 노트는 정답을 편 읽기 전용이라 먼저 풀어 보기에 고를 칸 대신 "정답" 꼬리표를 닮. 단원 이름은 단계 제목보다 큼."""
        win = self.boot()
        self.assertTrue(win.open_ai_note("i90"))
        page = win.ai_note
        guikit.pump()  # 줄이 자리를 잡은 뒤에 누름
        unit_row = page.findChildren(ai_learn.FoldRow)[0]
        guikit.click(unit_row)
        guess = page.findChildren(ai_learn.GuessBlock)[0]
        tags = [(n, row.tag.text()) for n, row in enumerate(guess.choices.rows) if row.tag.isVisible()]
        self.assertEqual(tags, [(0, "정답")])
        self.assertFalse(guess.choices.rows[0].box.isEnabled() or guess.note.isVisible())
        self.assertEqual(guess.choices.picked(), [])
        view = page.views[0]
        self.assertGreater(unit_row.label.font().pixelSize(), view.title.font().pixelSize())
        self.assertEqual(self.log(), [])  # 읽기 전용이라 기록하지 않음

    def test_revisit_then_mixed_set_starts_with_that_unit(self):
        win = self.boot()
        self.read_all()
        self.at(4)
        self.assertTrue(win.open_ai_revisit())
        page = win.ai_revisit
        self.assertTrue(page.title.text().startswith("90차시 · "))  # 다른 화면처럼 "N차시 · 단원"
        self.assertTrue(page.memo.rows and not page.memo.rows[0].opened)
        unit = page.data["unit"]
        guikit.click(page.start_btn)
        quiz = win.ai_quiz
        self.assertEqual((self.page(), quiz.title.text()), (quiz, "섞어 풀기"))
        self.assertEqual(win.ai.cards[quiz.item["card"]]["unit"], unit)
        self.assertEqual(self.log("revisit")[-1]["unit"], unit)


class LevelsTest(AiTest):
    """세 수준으로 다시 보기(90a 2단계 끝). 접힌 채 비어 있다가 펴면 수준 셋을 그리고, 확인 물음은 떠올리기처럼 기록에 수준을 남김.
    전체 노트와 [노트 보기]에서는 접힌 채 시작하고 펴면 정답을 편 채로 기록하지 않음."""

    def levels(self, view):
        found = view.findChildren(ai_learn.LevelsBlock)
        self.assertEqual(1, len(found))
        return found[0]

    def open_block(self, block):
        guikit.click(block.row)
        guikit.pump()
        self.assertTrue(block.row.opened and block.body.isVisible())
        return block.body.findChildren(ai_learn.RecallBlock)

    def test_folded_then_three_levels_and_recall_with_level(self):
        self.boot()
        self.assertTrue(self.win.open_ai_unit("i90", "90a", 2))
        guikit.pump()
        learn = self.win.ai_learn
        block = self.levels(learn.view)
        self.assertIs(learn.view.layout().itemAt(learn.view.layout().count() - 1).widget(), block)  # 단계 맨 아래
        self.assertEqual("well", block.layout().itemAt(0).widget().objectName())
        self.assertEqual(block.row.label.plain, "세 단계로 다시 보기 · 기울기")
        self.assertFalse(block.row.opened or block.body.isVisible())
        self.assertEqual((0, []), (block.body_box.count(), block.body.findChildren(ai_learn.RecallBlock)))  # 접힌 동안 비어 있음
        self.assertEqual(learn.view.findChildren(ai_learn.RecallBlock)[0].block["id"], "r1")
        recalls = self.open_block(block)
        self.assertEqual(3, block.body_box.count())
        text = visible_text(block)
        for name in ai_text.LEVEL_NAMES.values():
            self.assertIn(name, text)
        for word in (ai_text.LEVEL_CHECK, ai_text.LEVEL_MISTAKE):
            self.assertIn(word, text)
        self.assertNotIn('다루는 곳', text)
        self.assertNotIn('90차시 슬라이드 3쪽', text)
        self.assertEqual(3, len(block.figures))
        self.assertTrue(all(isinstance(f, ai_learn.AiFigure) for f in block.figures))
        for figure in block.figures:
            self.assertLessEqual(figure.picture.pixmap().deviceIndependentSize().width(), figure.width())
        code = "\n".join(piece.toPlainText() for piece in block.findChildren(TextPiece))
        self.assertIn("w = w - lr * grad", code)
        self.assertEqual([7, 15, 20], [r.block["level"] for r in recalls])
        self.assertTrue(all(r.entry.isVisible() and not r.result.isVisible() for r in recalls))
        guikit.click(recalls[1].check_btn)  # 빈 칸은 채점하지 않음
        self.assertTrue(recalls[1].empty_note.isVisible())
        self.assertEqual([], self.log("recall"))
        recalls[1].field.setText("2.4")
        guikit.click(recalls[1].check_btn)
        self.assertEqual(recalls[1].verdict.text(), "맞았습니다")
        recalls[0].field.setText("4")
        QTest.keyClick(recalls[0].field, Qt.Key.Key_Return)
        self.assertEqual([("90a", "v1", 15, True), ("90a", "v1", 7, False)],
                         [(r["unit"], r["id"], r["level"], r["ok"]) for r in self.log("recall")])
        self.assertEqual(learn.index, 1)
        recalls[2].field.setFocus()
        QTest.keyClick(recalls[2].field, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(learn.index, 2)  # 물음 칸에서도 Alt+→ 는 단계를 넘김

    def tab_through(self, block):
        """접힌 줄에서 Enter 로 펴고 Tab 을 눌러 가며 블록 안에서 초점을 받은 부품 목록. 블록을 벗어나면 멈춤."""
        block.row.setFocus()
        QTest.keyClick(block.row, Qt.Key.Key_Return)
        guikit.pump()
        self.assertTrue(block.row.opened)
        seen = []
        for _ in range(40):
            QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
            guikit.pump(10)
            widget = QApplication.focusWidget()
            if not block.isAncestorOf(widget):
                break
            seen.append(widget)
        return seen

    def test_tab_goes_through_the_opened_block_in_order(self):
        win = self.boot()
        self.assertTrue(win.open_ai_unit("i90", "90a", 2))
        guikit.pump()
        block = self.levels(win.ai_learn.view)
        seen = self.tab_through(block)
        recalls = block.body.findChildren(ai_learn.RecallBlock)
        self.assertEqual((3, 3, 3), (len(block.figures), len(block.docs), len(recalls)))
        expected = []
        for figure, doc, recall in zip(block.figures, block.docs, recalls):
            self.assertTrue(figure.zoom_btn.isVisibleTo(block))
            pieces = doc.findChildren(TextPiece)
            self.assertTrue(pieces)
            expected.extend([figure.zoom_btn, *pieces, recall.field, recall.check_btn])
        expected.append(block.deep_btn)
        self.assertEqual(expected, seen)
        win.open_ai_note("i90")
        page = win.ai_note
        guikit.pump()
        guikit.click(page.findChildren(ai_learn.FoldRow)[0])
        block = self.levels(page)
        seen = self.tab_through(block)
        self.assertEqual((3, 3), (len(block.figures), len(block.docs)))
        expected = []
        for figure, doc in zip(block.figures, block.docs):
            self.assertTrue(figure.zoom_btn.isVisibleTo(block))
            pieces = doc.findChildren(TextPiece)
            self.assertTrue(pieces)
            expected.extend([figure.zoom_btn, *pieces])
        expected.append(block.deep_btn)
        self.assertEqual(expected, seen)

    def test_restyle_while_open(self):
        win = self.boot()
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.assertTrue(win.open_ai_unit("i90", "90a", 2))
        guikit.pump()
        block = self.levels(win.ai_learn.view)
        self.open_block(block)
        sizes = []
        for step in theme.TEXT_STEPS:
            win.set_text(step)
            guikit.pump()
            sizes.append(block.docs[0].css)
            self.assertEqual(3, len(block.findChildren(ai_learn.RecallBlock)))
        win.set_text(theme.TEXT_DEFAULT)
        self.assertEqual(len(set(sizes)), len(theme.TEXT_STEPS))  # 펼친 블록의 글도 글자 단계를 따름
        for scheme in ("dark", "light"):
            theme.set_mode(scheme)
            win.restyle()
            guikit.pump()
            self.assertEqual(3, len(block.figures))

    def test_full_note_and_note_dialog_start_folded_and_keep_no_record(self):
        win = self.boot()
        self.assertTrue(win.open_ai_note("i90"))
        page = win.ai_note
        guikit.pump()
        guikit.click(page.findChildren(ai_learn.FoldRow)[0])
        block = self.levels(page)
        self.assertFalse(block.row.opened or block.body_box.count())
        recalls = self.open_block(block)
        self.assertEqual(3, len(recalls))
        self.assertTrue(all(r.result.isVisibleTo(page) and not r.entry.isVisibleTo(page) for r in recalls))  # 정답과 까닭을 편 채로
        self.assertIn("정답: **2.4**", visible_text(recalls[1]))
        dialog = ai_learn.NoteDialog(win, "i90", "90a/2")
        dialog.show()
        guikit.pump()
        block = self.levels(dialog.view)
        self.assertFalse(block.row.opened)
        recalls = self.open_block(block)
        self.assertTrue(all(r.result.isVisibleTo(dialog) and not r.entry.isVisibleTo(dialog) for r in recalls))
        dialog.close()
        guikit.pump()
        self.assertEqual([], self.log())


class PracticeTest(AiTest):
    def test_only_the_last_graded_answer_requests_automatic_file_submission(self):
        page = self.start()
        with mock.patch.object(self.win.auto_submission, "request") as checkpoint:
            while page.item is not None:
                last = page.practice.pos == len(page.practice.queue) - 1
                self.answer()
                if last:
                    checkpoint.assert_called_once()
                    break
                checkpoint.assert_not_called()
                guikit.click(page.next_btn)
            self.assertTrue(last)

    def start(self, mode="lesson"):
        win = self.boot()
        self.at(4)
        self.assertTrue(win.open_ai_practice(mode, lesson="i90"))
        return win.ai_quiz

    def skip_to(self, want):
        """맞혀 넘기며 want(문항) 가 참인 문항까지 감."""
        page = self.win.ai_quiz
        for _ in range(40):
            if page.item is None:
                break
            if want(page.item):
                return page.item
            self.answer()
            guikit.click(page.next_btn)
        self.fail("찾는 문항이 묶음에 없습니다")

    def badges(self):
        page = self.win.ai_quiz
        return [b.text() for b in page.card.findChildren(QLabel) if b.objectName() == "badge" and b.isVisible()]

    def test_practice_keeps_learning_text_and_input_sizes_after_scaling(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        page = self.start()
        self.skip_to(lambda item: item["card"] == "i90-b01")
        for step in ("large", "larger"):
            self.win.set_text(step)
            self.idle()
            piece = next(p for doc in page.docs for p in doc.findChildren(TextPiece) if p.toPlainText().strip())
            fragment = piece.document().begin().begin().fragment()
            font = fragment.charFormat().font().resolve(piece.document().defaultFont())
            self.assertEqual(QFontMetricsF(font).height(), QFontMetricsF(theme.font("learn_body")).height())
            self.assertEqual(page.fields[0].font().pixelSize(), theme.TYPE["learn_body"][0])
        self.answer()
        self.assertEqual(page.fields[0].font().pixelSize(), theme.TYPE["learn_body"][0])

    def test_wrong_blank_shows_answers_and_comes_back_three_later(self):
        page = self.start()
        self.assertEqual(page.count.text(), "1 / %d" % page.item["total"])
        self.assertTrue(page.guide.isVisible())  # 묶음 첫 문항에 [확실함]·[긴가민가] 안내
        self.assertIn("[확실함]", page.guide.text())
        item = self.skip_to(lambda item: item["card"] == "i90-b01")
        self.assertEqual(item["chips"][:2], ["90차시", "빈칸"])
        self.assertNotIn("90차시", self.badges())  # 묶음 제목 "90차시 풀기" 와 같은 말이라 화면에서는 뺌
        self.assertIn("빈칸", self.badges())
        if item["at"] > 1:
            self.assertFalse(page.guide.isVisible())
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(page)], ["확실함"])
        self.answer(right=False, sure=False)
        self.assertEqual(page.verdict_text.text(), "틀렸습니다")
        self.assertEqual(page.verdict_text.property("tone"), "danger")
        self.assertEqual(page.answer_line.text(), "정답: 반대")  # 정답은 판정 아래 한 곳에만
        self.assertEqual(page.fields[0].property("tone"), "danger")
        self.assertFalse(page.results[0].isVisible())  # 칸이 하나면 테두리와 판정 줄이 말함
        self.assertEqual(page.requeue.text(), "이 문항은 3문항 뒤에 다시 나옵니다.")  # 묶음 길이가 늘어난 까닭
        self.assertEqual(page.count.text(), "%d / %d" % (item["at"], item["total"] + 1))
        self.assertIn("참고:", visible_text(page.after))
        self.assertIn("단계", visible_text(page.after))
        self.assertNotIn("슬라이드", visible_text(page.after))
        self.assertTrue(page.mine_btn.isVisible() and page.note_btn.isVisible())
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(page)], ["다음"])
        at = item["at"]
        guikit.click(page.next_btn)
        for _ in range(3):
            self.assertNotEqual(page.item["card"], "i90-b01")
            self.answer()
            guikit.click(page.next_btn)
        self.assertEqual((page.item["card"], page.item["at"]), ("i90-b01", at + 4))
        self.assertIn("다시 나온 문항", page.item["chips"])
        self.answer()
        self.assertTrue(page.requeue.text().startswith("한 번 더 맞히면 이 묶음에서 빠집니다."))
        seen = 2
        guikit.click(page.next_btn)
        while page.item is not None:
            if page.item["card"] == "i90-b01":
                seen += 1
            if page.feedback is None:
                self.answer()
            guikit.click(page.next_btn)
        self.assertEqual(seen, 3)  # 틀림, 맞힘, 다시 맞힘
        self.assertRegex(visible_text(page.card), r"\d+문항 가운데 \d+문항을 처음 답에 맞혔습니다.")
        self.assertTrue(page.again_btn.isVisible())
        self.assertEqual(page.again_btn.text(), "한 번 더")
        self.assertTrue(self.log("set_end"))
        answers = [r for r in self.log("answer") if r["result"] == "pass"]
        self.assertFalse([r for r in answers if "value" in r])  # 맞힌 답의 글은 남기지 않음

    def test_sure_wrong_dont_know_and_override(self):
        page = self.start()
        self.skip_to(lambda item: item["kind"] == "blank" and not item["code"])
        self.answer(right=False, sure=True)
        self.assertEqual(page.verdict_text.text(), ai_text.SURE_WRONG)
        self.assertTrue(self.log("answer")[-1]["sure"])
        guikit.click(page.mine_btn)
        self.assertEqual(page.verdict_text.text(), ai_text.OVERRIDDEN)
        self.assertFalse(page.mine_btn.isVisible())
        self.assertEqual(self.log("override")[-1]["card"], page.item["card"])
        guikit.click(page.next_btn)
        guikit.click(page.dont_btn)
        self.assertEqual((page.verdict_text.text(), page.verdict_text.property("tone")), (ai_text.DONT_KNOW, "secondary"))
        self.assertFalse(page.mine_btn.isVisible())
        self.assertTrue(self.log("answer")[-1]["dontknow"])
        for field in page.fields:  # 읽기 전용 칸에 자리표시와 틀림 색을 남기지 않음(글 칸 문항일 때)
            self.assertEqual((field.placeholderText(), field.property("tone"), field.isReadOnly()), ("", None, True))
        self.assertTrue(page.answer_line.text().startswith("정답: "))

    def test_empty_answer_is_not_sent(self):
        page = self.start()
        count = len(self.log("answer"))
        guikit.click(page.sure_btn)
        self.assertEqual(page.status.text(), ai_text.EMPTY_ANSWER[page.item["kind"]])
        self.assertIsNone(page.feedback)
        self.assertEqual(len(self.log("answer")), count)

    def test_code_blank_uses_slots_and_tab_moves_between_them(self):
        page = self.start()
        item = self.skip_to(lambda item: item["code"])
        self.assertEqual(item["chips"][1], "코드 빈칸")
        self.assertEqual(len(page.slots), 1)
        slot = page.slots[0].fields[0]
        self.assertIsInstance(slot, ai_quiz.Slot)
        self.assertEqual(slot.height(), theme.learning_slot_height())
        self.assertFalse(page.fields)  # 코드 밖 칸이 없음
        self.addCleanup(theme.set_text, theme.state["text"])
        self.win.set_text("larger")
        self.idle()
        self.answer()
        self.assertEqual(slot.font().pixelSize(), theme.TYPE["learn_code"][0])
        self.assertEqual(page.answer_line.text(), "정답: `zero_grad`")
        fake = dict(page.item, stem="두 칸을 채우세요.\n\n```python\nx.____(2, 3)\ny = x.____()\n```",
                    blanks=[{"mode": "code", "hint": "메서드"}, {"mode": "code", "hint": "메서드"}], code=True, chips=["90차시", "코드 빈칸"])
        page.show_item(fake)
        guikit.pump()  # 새 칸은 다음 이벤트에서 보이고 그 뒤에 초점을 받음
        slots = page.slots[0]
        self.assertIs(QApplication.focusWidget(), slots.fields[0])  # 문항을 열면 첫 칸에 초점
        self.assertEqual(len(slots.fields), 2)
        self.assertEqual([label.text() for label in slots.inner.findChildren(QLabel) if label.text() in "①②"], ["①", "②"])
        slots.fields[0].setFocus()
        QTest.keyClick(slots.fields[0], Qt.Key.Key_Tab)
        self.assertIs(QApplication.focusWidget(), slots.fields[1])
        slots.fields[1].setText("contiguous_and_long_name")
        self.assertGreater(slots.fields[1].width(), slots.fields[0].width())  # 적은 만큼 넓어짐
        width = slots.fields[0].width()
        page.mark_blanks([True, False], ["view", "sum"])  # 칸마다 맞고 틀림을 색만이 아니라 글로도 보임
        self.assertEqual(page.answer_line.text(), "정답: ① `view` · ② `sum`")
        self.assertEqual(slots.result.text(), "① 맞음 · ② 틀림")
        self.assertTrue(slots.result.isVisible())
        self.assertEqual([f.property("tone") for f in slots.fields], ["success", "danger"])
        self.assertEqual(slots.fields[0].width(), width)  # 자리표시를 지워도 칸 폭이 그대로라 뒤 코드가 움직이지 않음
        numbers = [label for label in slots.inner.findChildren(QLabel) if label.text() in ("①", "②")]
        self.assertEqual({label.property("role") for label in numbers}, {"label"})  # 코드 밖 칸 번호와 같은 크기

    def test_drop_and_paste_leave_the_fields_alone(self):
        """칸에 글을 끌어다 놓거나 붙여넣기 키를 눌러도 글이 들어가지 않고 안내가 나옴."""
        page = self.start()
        self.skip_to(lambda item: item["card"] == "i90-b01")
        field = page.fields[0]
        data = QMimeData()
        data.setText("반대")
        point = QPointF(field.width() / 2, field.height() / 2)
        enter = QDragEnterEvent(point.toPoint(), Qt.DropAction.CopyAction, data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(field, enter)
        drop = QDropEvent(point, Qt.DropAction.CopyAction, data, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(field, drop)
        self.assertEqual(field.text(), "")
        page.status.hide()
        field.setFocus()
        QTest.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)  # 키는 창의 Guard 가 막고 같은 안내를 보임
        self.assertEqual(field.text(), "")
        self.assertTrue(page.status.isVisible())

    def test_ctrl_enter_commits_the_composing_hangul_first(self):
        """단축키는 초점을 옮기지 않아 조합 중인 글자가 칸에 들어가기 전에 답을 읽을 수 있음. 답을 읽기 전에 commit_input 을 부름."""
        page = self.start()
        self.skip_to(lambda item: item["card"] == "i90-b01")
        field = page.fields[0]
        field.setText("반")

        def commit():  # 입력기가 남은 "대" 를 칸에 넣는 것을 흉내 냄
            field.setText(field.text() + "대")

        with mock.patch.object(ai_quiz, "commit_input", commit):
            QTest.keyClick(field, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(page.verdict_text.text(), "맞았습니다")
        QTest.keyClick(page, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)  # 답한 뒤에는 [다음]
        self.assertIsNone(page.feedback)
        self.win.open_ai_practice("lesson", lesson="i90")  # 새 묶음의 첫 빈칸에서 [긴가민가] 단축키를 봄
        self.skip_to(lambda item: item["kind"] == "blank" and not item["code"])
        page.fields[0].setText("모름")
        QTest.keyClick(page.fields[0], Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertFalse(self.log("answer")[-1]["sure"])

    def test_choice_marks_every_option_and_errata(self):
        page = self.start()
        self.skip_to(lambda item: item["card"] == "i90-c01")
        self.assertEqual(page.item["chips"][:2], ["90차시", "고르기"])
        self.assertIsInstance(page.choices.rows[0].box, ai_learn.RadioMark)
        self.answer(right=False)
        tags = {row.tag.text() for row in page.choices.rows if row.tag.isVisible()}
        self.assertEqual(tags, {"정답", "내 답"})  # 색만이 아니라 글로도 알림
        self.assertTrue(all(holder.isVisible() for holder in page.whys))
        self.assertTrue(page.answer_line.text().startswith("정답: zero_grad"))
        text = visible_text(page.after)
        self.assertNotIn("정정", text)
        self.assertIn("맨 끝에 두어도 다음 반복 전에 비워지므로 결과가 같습니다", text)
        self.assertNotIn("슬라이드", text)
        self.assertFalse(page.mine_btn.isVisible())

    def test_pick_wrong_item_does_not_call_the_false_statement_the_answer(self):
        page = self.start()
        self.skip_to(lambda item: item["kind"] == "choice" and item["pick"] == "wrong")
        self.answer(right=False)
        self.assertTrue(page.answer_line.text().startswith("옳지 않은 문장: "), page.answer_line.text())

    def test_note_dialog_shows_the_step_read_only(self):
        page = self.start()
        self.skip_to(lambda item: item["card"] == "i90-b01")
        self.answer(right=False)
        count = len(self.log())
        guikit.click(page.note_btn)
        dialog = page.note_dialog
        self.assertTrue(dialog.isVisible())
        self.assertTrue(dialog.isModal())  # 열어 둔 채 다음 문항으로 넘어가지 못함
        self.assertEqual(dialog.view.title.text(), "손실이 줄어드는 쪽으로 W를 옮깁니다")
        recall = dialog.view.findChildren(ai_learn.RecallBlock)[0]
        self.assertFalse(recall.entry.isVisibleTo(dialog))
        self.assertTrue(recall.result.isVisibleTo(dialog))  # 정답을 편 채로
        self.assertTrue(dialog.view.findChildren(ai_learn.WhyBlock)[0].answer.isVisibleTo(dialog))
        dialog.close()
        guikit.pump()
        self.assertEqual(len(self.log()), count)  # 대화상자 안 블록은 기록하지 않음
        self.assertIs(self.page(), page)
        guikit.click(page.note_btn)
        dialog = page.note_dialog
        page.go_next()  # 단축키 같은 다른 길로 넘어가도 창이 남지 않음
        guikit.pump()
        self.assertTrue(sip.isdeleted(dialog) or not dialog.isVisible())
        self.assertIsNone(page.note_dialog)

    def test_reference_link_opens_only_the_current_visible_step(self):
        page = self.start()
        self.skip_to(lambda item: item["card"] == "i90-b01")
        self.answer(right=False)
        count = len(self.log())
        link = page.after.findChildren(LinkLabel)[0]
        link.linkActivated.emit("https://example.org/not-a-note")
        self.assertIsNone(page.note_dialog)
        QTest.mouseClick(link, Qt.MouseButton.LeftButton, pos=QPoint(16, link.height() // 2))
        guikit.pump()
        self.assertTrue(page.note_dialog.isVisible())
        self.assertEqual(page.note_dialog.view.title.text(), "손실이 줄어드는 쪽으로 W를 옮깁니다")
        page.close_note()
        card = self.win.ai.card_info(page.item["card"])
        for step in ("90a/999", "90a/../../other", "90z/2", ""):
            card["step"] = step
            page.set_buttons()
            self.assertFalse(page.note_btn.isVisible())
            link.linkActivated.emit("study-note")
            self.assertIsNone(page.note_dialog)
        card["step"] = "90a/2"
        self.win.ai.notes["i90"]["visible"].remove("90a")
        link.linkActivated.emit("study-note")
        self.assertIsNone(page.note_dialog)
        self.assertEqual(count, len(self.log()))

    def test_unit_set_ends_with_next_unit(self):
        win = self.boot()
        self.at(4)
        win.ai.mark_read("i90", "90a")
        win.open_ai_practice("unit", lesson="i90", unit="90a")
        page = win.ai_quiz
        while page.item is not None:
            if page.feedback is None:
                self.answer()
            guikit.click(page.next_btn)
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(page)], ["다음 단원"])
        self.assertEqual(page.count.text(), "끝남")
        guikit.click(page.again_btn)
        self.assertEqual((self.page(), win.ai_learn.key), (win.ai_learn, "90b"))
        win.ai.mark_read("i90", "90b")
        win.open_ai_practice("unit", lesson="i90", unit="90b")
        while page.item is not None:
            if page.feedback is None:
                self.answer()
            guikit.click(page.next_btn)
        self.assertEqual(page.again_btn.text(), "섞어 풀기")  # 안 읽은 단원이 없으면 단추 이름이 여는 화면을 말함
        guikit.click(page.again_btn)
        self.assertEqual((self.page(), page.title.text()), (page, "섞어 풀기"))

    def test_unit_day_wrong_answers_are_explained_in_the_summary(self):
        """단원을 읽은 날 처음 답을 틀린 문항은 오답 노트에 들어가지 않으므로, 끝 요약과 빈 오답 노트가 그 까닭을 말함."""
        win = self.boot()
        self.at(4)
        win.ai.mark_read("i90", "90a")
        win.open_ai_practice("unit", lesson="i90", unit="90a")
        page = win.ai_quiz
        self.answer(right=False, sure=False)
        while page.item is not None:
            if page.feedback is None:
                self.answer()
            guikit.click(page.next_btn)
        self.assertEqual(win.ai.wrong_notes(), [])
        self.assertIn("단원을 읽은 날 틀린 1문항은 오답 노트에 넣지 않고 다음 복습에서 다시 냅니다.", visible_text(page.card))
        self.assertIn("단원을 읽은 날 틀린 문항은", ai_text.AiNotes.EMPTY)

    def test_problem_fetch_sends_the_practice_page_home(self):
        page = self.start()
        self.answer()
        self.git.replies["sync"] = {"status": "ok", "changed": True, "message": "새 문제를 받았습니다."}
        self.win.fetch_problems()
        self.idle()
        if self.win.dialog is not None:
            self.win.dialog.close()
        self.assertEqual((self.page(), self.win.area), (self.win.ai_home, "ai"))
        self.assertIsNone(page.practice)


class WrongNoteTest(AiTest):
    def make_wrong(self):
        """11-02 에 읽고 11-03 복습에서 하나를 틀림(읽은 날의 오답은 오답 노트에 넣지 않음)."""
        win = self.win
        self.read_all(2)
        win.open_ai_practice("mixed")
        while win.ai_quiz.item is not None:
            if win.ai_quiz.feedback is None:
                self.answer()
            guikit.click(win.ai_quiz.next_btn)
        self.at(3)
        win.open_ai_practice("review")
        self.answer(right=False)
        return win.ai_quiz.item["card"]

    def test_ai_tab_rows_detail_and_retry(self):
        win = self.boot()
        card = self.make_wrong()
        self.at(4)
        win.go_hub()
        hub = win.hub
        row = dict((track.tid, r) for track, r in hub.note_rows)["ai"]
        self.assertEqual(row.second.text(), "개론 · 틀린 문항 1개")
        guikit.click(row)
        page = win.wrong_page
        self.assertEqual((self.page(), page.track.tid, page.back_btn.text()), (page, "ai", "← 처음 화면"))
        self.assertTrue(page.chip_row.isVisibleTo(page))
        self.assertTrue(page.chips["ai"].isChecked())
        self.assertEqual(page.selected()["key"], card)
        label = page.list.rows[0].title.text()
        self.assertNotIn("90차시", label)  # 묶음 이름이 차시를 말하므로 줄에는 문제 첫머리
        self.assertTrue(page.item_title.text().startswith("90차시 · "))
        text = page.detail.toPlainText()
        self.assertIn("내 답", text)
        self.assertNotIn("정답과 해설", text)
        guikit.click(page.explain_btn)
        self.assertIn("정답과 해설", page.detail.toPlainText())
        guikit.click(page.retry_btn)
        quiz = win.ai_quiz
        self.assertEqual((self.page(), quiz.title.text(), quiz.item["card"]), (quiz, "오답 다시 풀기", card))
        self.assertEqual(quiz.back_btn.text(), "← 오답 노트")
        guikit.click(quiz.back_btn)
        self.assertIs(self.page(), page)

    def test_wrong_note_reference_click_checks_the_target_without_writing_records(self):
        win = self.boot()
        card = self.make_wrong()
        self.at(4)
        win.go_ai()
        guikit.click(win.ai_home.notes_row)
        page = win.wrong_page
        count = len(self.log())
        html = page.detail.toHtml()
        self.assertIn('href="study-note"', html)
        self.assertNotIn("슬라이드", page.detail.toPlainText())
        target = win.ai.note_target(card)
        cursor = page.detail.document().find(target["label"])
        self.assertFalse(cursor.isNull())
        cursor.setPosition(cursor.selectionStart())
        page.detail.setTextCursor(cursor)
        page.detail.ensureCursorVisible()
        point = page.detail.cursorRect(cursor).center() + QPoint(3, 0)
        self.assertEqual("study-note", page.detail.anchorAt(point))
        with mock.patch.object(page.track, "open_reference", wraps=page.track.open_reference) as opened:
            page.detail.anchorClicked.emit(QUrl("https://example.org/not-a-note"))
            opened.assert_not_called()
            QTest.mouseClick(page.detail.viewport(), Qt.MouseButton.LeftButton, pos=point)
            guikit.pump()
            opened.assert_called_once()
        dialog = page.track.reference_dialog
        self.assertTrue(dialog.isVisible())
        key, number = target["step"].split("/")
        step = win.ai.notes[target["lesson"]]["units"][key]["steps"][int(number) - 1]
        self.assertEqual(dialog.view.title.text(), step["title"])
        dialog.close()
        guikit.pump()
        win.ai.card_info(card)["step"] = "90a/999"
        with mock.patch.object(ai_learn, "NoteDialog") as note:
            page.detail.anchorClicked.emit(QUrl("study-note"))
            note.assert_not_called()
        self.assertEqual(count, len(self.log()))

    def test_statement_rows_follow_the_form_they_were_missed_in(self):
        win = self.boot()
        sess = win.ai
        self.at(2)
        sess.mark_read("i90", "90b")
        sess._append({"kind": "answer", "set": "s0", "card": "i90-s01", "result": "pass", "again": 0})
        self.at(3)
        sess._append({"kind": "answer", "set": "s1", "card": "i90-s01", "result": "pass", "again": 0})
        self.at(4)
        service.PracticeSet(sess, "s2", "unit", ["i90-s01"], 1).answer(["엉뚱"], 2, False)
        choice = service.PracticeSet(sess, "s3", "unit", ["i90-s05"], 1)
        right = grade.right_options(choice._view(choice.queue[0])["item"])
        choice.answer([o["no"] for o in choice.current()["options"] if o["no"] not in right][:1], 2, False)
        win.go_ai()
        guikit.click(win.ai_home.notes_row)
        page = win.wrong_page
        cloze, wrong = sess.cards["i90-s01"]["stmt"], sess.cards["i90-s05"]["stmt"]
        label = page.list.row_of("i90-s01").title.text()
        self.assertTrue(label.startswith("빈칸 · "), label)
        self.assertNotIn(cloze["text"], label)  # 줄에 답이 보이지 않음
        self.assertNotIn(wrong["text"], page.list.row_of("i90-s05").title.text())
        page.list.pick(page.list.row_of("i90-s01"))
        guikit.click(page.explain_btn)
        self.assertIn("정답: %s" % cloze["cloze"]["answer"][0], page.detail.toPlainText())
        page.list.pick(page.list.row_of("i90-s05"))
        guikit.click(page.explain_btn)
        self.assertIn("옳지 않은 문장: %s" % wrong["text"], page.detail.toPlainText())

    def test_home_row_opens_the_tab_and_comes_back_home(self):
        win = self.boot()
        win.go_ai()
        home = win.ai_home
        self.assertEqual(home.notes_row.second.text(), "아직 틀린 문항이 없습니다.")
        guikit.click(home.notes_row)
        page = win.wrong_page
        self.assertEqual((self.page(), page.track.tid, page.back_btn.text()), (page, "ai", "← AI"))
        self.assertIs(page.stack.currentWidget(), page.empty)
        self.assertEqual(page.empty_text.text(), ai_text.AiNotes.EMPTY)
        guikit.click(page.back_btn)
        self.assertEqual((self.page(), win.area), (win.ai_home, "ai"))


class PatternTest(AiTest):
    """상황별 코드(고정 은행에 tests/ai_bank_pc 를 더한 사본): 홈 구역, 학습 단원의 나란히 보기·돌려 가며 빈칸, 뼈대 카드 연습(코드 보기,
    함께 가린 칸), [노트 보기], 이어서 할 일과 다시 보기, 오답 노트."""
    pc = True
    UNIT = "학습 루프 · 시험 뼈대 단원"

    def open_unit(self, step=None):
        self.assertTrue(self.win.open_ai_unit("pc", "18a", step))
        guikit.pump()
        return self.win.ai_learn

    def opened_slots(self):
        """18a 를 11-09 에 읽고 k01·k03 을 맞혀 11-10 에 k02 를 내면 점차 지우기 f = 1 이라 k01 을 함께 가림(test_ai_service 의
        PatternBase.opened_slots 와 같은 기록)."""
        sess = self.win.ai
        self.at(9)
        sess.mark_read("pc", "18a")
        for cid in ("pc-k01", "pc-k03"):
            sess._append({"kind": "answer", "set": "s9", "card": cid, "result": "pass", "again": 0})
        self.at(10)
        sess._append({"kind": "answer", "set": "s10", "card": "pc-k03", "result": "pass", "again": 0})
        self.at(10, "21:00:00")

    def badges(self):
        page = self.win.ai_quiz
        return [b.text() for b in page.card.findChildren(QLabel) if b.objectName() == "badge" and b.isVisible()]

    def test_home_section_opens_the_unit_and_comes_back_home(self):
        win = self.boot((1024, 700))
        win.go_ai()
        home = win.ai_home
        self.assertTrue(home.pattern_section.isVisibleTo(home))
        self.idle()
        self.assertGreater(home.pattern_section.mapTo(home, QPoint(0, 0)).y(), home.books.mapTo(home, QPoint(0, 0)).y())  # 맨 아래 구역
        self.assertEqual([(r.title.text(), r.second.text(), r.mark.state) for r in home.pattern_list.rows],
                         [(self.UNIT, "90차시 뒤에 권함 · 약 6분", "todo")])  # 권하는 차시를 읽기 전에도 열 수 있음
        self.assertEqual(home.pattern_list.more_btn.text(), "준비 중 1개 보기")
        guikit.click(home.pattern_list.more_btn)
        self.assertIn("평가 루프", visible_text(home.pattern_list))
        home.set_busy(True)
        self.assertTrue(home.pattern_list.rows[0].inert)
        home.set_busy(False)
        guikit.click(home.pattern_list.rows[0])
        learn = win.ai_learn
        self.assertEqual((self.page(), learn.lid, learn.back_btn.text(), learn.title.text()), (learn, "pc", "← AI", self.UNIT))
        guikit.click(learn.back_btn)
        self.assertEqual((self.page(), win.area), (home, "ai"))
        win.ai.mark_read("pc", "18a")
        win.go_ai()
        row = home.pattern_list.rows[0]
        self.assertEqual((row.second.text(), row.mark.state),
                         ("90차시 뒤에 권함 · 읽기 마침 · 단원 연습 미완료 · 복습 확인 전 · 전체 7묶음", "progress"))

    def test_broken_skeleton_shows_the_band_and_keeps_the_lessons(self):
        study.write_text(os.path.join(self.root, "patterns", "S90.json"), "{깨진 뼈대")
        win = self.boot()
        win.go_ai()
        home = win.ai_home
        self.assertTrue(home.notice.isVisible())
        self.assertEqual(home.notice.text.text(), ai_text.PATTERN_BROKEN % "상황별 코드")
        self.assertFalse(home.pattern_section.isVisibleTo(home))
        self.assertEqual([row.title.text() for row in home.lesson_list.rows], ["90차시 시험 차시"])

    def test_every_step_renders_without_hidden_lines(self):
        self.boot((1024, 700))
        learn = self.open_unit(1)
        for index in range(len(learn.steps)):
            learn.show_step(index)
            guikit.pump()
            text = "\n".join(piece.toPlainText() for piece in learn.view.findChildren(TextPiece))
            self.assertNotIn("<!--", text, index)
            self.assertNotIn(ai_text.BLOCK_BROKEN, visible_text(learn.view), index)
        learn.show_step(0)
        guikit.pump()
        self.assertIn("    opt.zero_grad()", "\n".join(piece.toPlainText() for piece in learn.view.findChildren(TextPiece)))

    def test_diff_block_draws_two_columns_without_wrapping(self):
        """1024×700 기본 글자에서 고정 뼈대(가장 긴 줄 26자)는 두 열이고, 다른 줄만 칠하고 같은 줄은 흐린 글자. 행 높이는 모두 코드 한 줄."""
        self.boot((1024, 700))
        learn = self.open_unit(2)
        block = learn.view.findChildren(ai_learn.DiffBlock)[0]
        self.assertTrue(block.two)
        text = visible_text(block)
        self.assertIn(ai_text.diff_caption(2, 6), text)
        self.assertIn("가\n나", text)  # 열 머리는 판 이름
        changed = [[cell.text() for cell in line.cells] for line in block.lines if line.changed]
        self.assertEqual(changed, [["net.train()", "net.eval()"], ["    n += c.argmax(1).sum()", "    n += c.argmax(0).sum()"]])
        same = [cell for line in block.lines if not line.changed for cell in line.cells]
        self.assertEqual({cell.property("tone") for cell in same}, {"secondary"})
        self.assertEqual({line.height() for line in block.lines}, {theme.TYPE["learn_code"][1]})
        self.assertLessEqual(learn.view.minimumSizeHint().width(), learn.view.width())

    def test_diff_block_stacks_when_a_column_cannot_hold_the_longest_line(self):
        """한 열이 가장 긴 줄을 코드 글자 그대로 담지 못하면(글자 단계를 키우거나 폭이 좁으면) 왼쪽 판 다음 오른쪽 판을 쌓고, 다시 넓어지면
        두 열로 돌아감. 코드 글자를 줄이지 않음."""
        self.addCleanup(theme.set_text, theme.state["text"])
        rows = [{"left": "a" * 44, "right": "b" * 44, "same": False}, {"left": "같은 줄", "right": "같은 줄", "same": True},
                {"left": None, "right": "c = 1", "same": False}]
        block = ai_learn.DiffBlock({"left": "가", "right": "나", "different": 2, "same": 1, "rows": rows})
        holder = kit.page(QWidget())
        kit.box(holder).addWidget(block)
        widths = []
        for step in ("normal", "large"):
            theme.set_text(step)
            widths.append(QFontMetricsF(ai_learn.code_font()).horizontalAdvance("a" * 44))
        boundary = round(sum(widths) + 2 * block.PAD + block.GAP)
        holder.resize(boundary, 600)
        holder.show()
        self.addCleanup(holder.close)
        for step, two in (("normal", True), ("large", False), ("larger", False), ("normal", True)):
            theme.set_text(step)
            block.restyle()
            guikit.pump()
            self.assertEqual(block.two, two, step)
            self.assertEqual(ai_learn.code_font().pixelSize(), theme.TYPE["learn_code"][0])
        holder.resize(600, 600)
        guikit.pump()
        self.assertFalse(block.two)
        self.assertEqual([[cell.text() for cell in line.cells] for line in block.lines], [["a" * 44], ["같은 줄"], ["b" * 44], ["같은 줄"], ["c = 1"]])
        self.assertEqual([line.changed for line in block.lines], [True, False, True, False, True])
        holder.resize(boundary, 600)
        guikit.pump()
        self.assertTrue(block.two)

    def test_rotate_block_moves_on_and_brings_a_wrong_slot_back_three_later(self):
        win = self.boot((1024, 700))
        learn = self.open_unit(3)
        block = learn.view.findChildren(ai_learn.RotateBlock)[0]
        self.addCleanup(theme.set_text, theme.state["text"])
        win.set_text("larger")
        self.idle()
        self.assertEqual(block.count.text(), "1 / 6")
        field = block.field()
        self.assertEqual(field.placeholderText(), "메서드 이름")
        guikit.click(block.check_btn)  # 빈 칸은 채점하지 않고 안내만
        self.assertTrue(block.empty_note.isVisible())
        self.assertEqual(self.log("recall"), [])
        field.setFocus()
        field.setText("eval")
        QTest.keyClick(field, Qt.Key.Key_Left)
        self.assertEqual((learn.index, field.cursorPosition()), (2, 3))  # 칸 안의 ← 는 글자 커서
        QTest.keyClick(field, Qt.Key.Key_Return)
        self.assertEqual((block.verdict.text(), block.answer.text(), field.property("tone")), ("틀렸습니다", "정답: `train`", "danger"))
        self.assertEqual(field.font().pixelSize(), theme.TYPE["learn_code"][0])
        self.assertTrue(block.next_btn.isVisible())
        self.assertFalse(block.check_btn.isVisible())
        self.assertEqual([(r["unit"], r["id"], r["slot"], r["ok"]) for r in self.log("recall")], [("18a", "t1", "pc-k01", False)])
        QTest.keyClick(field, Qt.Key.Key_Return)  # 답한 뒤 Enter 는 [다음 자리]
        self.assertEqual(block.count.text(), "2 / 7")
        self.assertEqual(block.queue, ["pc-k01", "pc-k02", "pc-k03", "pc-k04", "pc-k01", "pc-k05", "pc-k06"])
        self.assertIs(QApplication.focusWidget(), block.field())
        tokens = {spot["id"]: spot["token"] for spot in block.block["slots"]}
        for _ in range(10):
            if block.done.isVisible():
                break
            block.field().setText(tokens[block.queue[block.pos]])
            guikit.click(block.check_btn)
            self.assertEqual(block.verdict.text(), "맞았습니다")
            guikit.click(block.next_btn)
        self.assertTrue(block.done.isVisible())
        self.assertEqual(block.done.text(), ai_text.ROTATE_DONE)
        self.assertFalse(block.buttons.isVisible())
        self.assertEqual(block.slots.fields, [])  # 끝나면 가린 곳 없는 판 전체
        self.assertEqual(len(self.log("recall")), 7)
        self.assertIsNone(win.ai._state().box("pc-k01"))  # 상자는 움직이지 않음
        learn = self.open_unit(3)
        field = learn.view.findChildren(ai_learn.RotateBlock)[0].field()
        field.setFocus()
        QTest.keyClick(field, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(learn.index, 3)  # Alt+→ 는 단계

    def test_unit_set_draws_code_options(self):
        """순서 고르기는 2×2 이고 1024×700 에서 스크롤 없이 보임. 코드 보기는 판정 아래 정답 줄 없이 꼬리표만. 단원 묶음은 제목이 자리를
        말해 자리 꼬리표를 뺌."""
        win = self.boot((1024, 700))
        self.at(9)
        win.ai.mark_read("pc", "18a")
        self.assertTrue(win.open_ai_practice("unit", lesson="pc", unit="18a"))
        page = win.ai_quiz
        self.assertEqual((page.title.text(), page.item["card"]), (self.UNIT, "pc-o01"))
        self.assertEqual(page.item["chips"][:2], ["학습 루프", "순서 고르기"])
        self.assertEqual(self.badges(), ["순서 고르기"])
        choices = page.choices
        self.assertIsInstance(choices, ai_learn.CodeChoices)
        self.assertIsInstance(choices.rows[0].box, ai_learn.RadioMark)
        corners = [row.mapTo(choices, QPoint(0, 0)) for row in choices.rows]
        self.assertEqual(corners[0].y(), corners[1].y())
        self.assertLess(corners[0].x(), corners[1].x())
        self.assertGreater(corners[2].y(), corners[0].y())
        self.assertEqual(corners[0].x(), corners[2].x())
        viewport = page.scroll.viewport()
        self.assertLessEqual(choices.mapTo(viewport, QPoint(0, choices.height())).y(), viewport.height())
        self.assertEqual(len(choices.rows[0].code.labels), 5)  # 보기마다 줄을 지킨 코드
        self.answer(right=False)
        self.assertEqual({row.tag.text() for row in choices.rows if row.tag.isVisible()}, {"정답", "내 답"})
        self.assertFalse(page.answer_line.isVisible())
        self.assertFalse(any(holder.isVisible() for holder in page.whys))  # 순서 보기는 풀이 글이 없음
        guikit.click(page.next_btn)
        self.assertEqual(page.item["card"], "pc-p01")
        self.assertEqual(len({row.mapTo(page.choices, QPoint(0, 0)).x() for row in page.choices.rows}), 1)  # 한 열
        self.answer(right=False)
        self.assertTrue(any(holder.isVisible() for holder in page.whys))
        self.assertNotIn("정답:", visible_text(page.verdict))
        guikit.click(page.next_btn)
        self.assertEqual(page.item["card"], "pc-k01")
        self.assertEqual((len(page.slots), len(page.inputs)), (1, 1))
        self.answer()
        self.assertEqual(page.answer_line.text(), "정답: `train`")
        self.assertFalse(page.also_text.isVisible() or page.mine_btn.isVisible())

    def test_change_card_picks_several_lines_and_note_dialog_shows_the_diff(self):
        win = self.boot((1024, 700))
        self.at(9)
        win.ai.mark_read("pc", "18a")
        self.assertTrue(win.open_ai_practice("note", card="pc-x01"))
        page = win.ai_quiz
        self.assertEqual(self.badges()[:2], ["학습 루프", "고르기"])
        self.assertNotIsInstance(page.choices.rows[0].box, ai_learn.RadioMark)  # 여러 개 고르기는 네모 상자
        self.answer()
        self.assertEqual(page.verdict_text.text(), "맞았습니다")
        self.assertEqual({row.tag.text() for row in page.choices.rows if row.tag.isVisible()}, {"정답 · 내 답"})
        self.assertNotIn("정정", visible_text(page.after))
        count = len(self.log())
        guikit.click(page.note_btn)
        dialog = page.note_dialog
        self.assertEqual(dialog.windowTitle(), self.UNIT)
        self.assertTrue(dialog.view.findChildren(ai_learn.DiffBlock))
        dialog.close()
        guikit.pump()
        rotate = ai_learn.NoteDialog(win, "pc", "18a/3")
        rotate.open()
        guikit.pump()
        block = rotate.view.findChildren(ai_learn.RotateBlock)[0]
        self.assertFalse(hasattr(block, "check_btn"))  # 읽기 전용은 판 코드와 가리는 자리만
        self.assertEqual(block.slots.fields, [])
        self.assertIn(ai_text.ROTATE_SLOTS % "train · zero_grad · backward · step · argmax · sum", visible_text(rotate))
        self.assertEqual(len(self.log()), count)
        rotate.close()

    def test_shared_blank_wrong_shows_a_line_and_override_marks_every_blank(self):
        """주 자리를 맞히고 함께 가린 칸을 틀리면 판정은 맞음이고 그 칸 번호를 한 줄 더 씀. [내 답도 맞음]이 보이고 누르면 두 칸 모두 맞음."""
        win = self.boot((1024, 700))
        self.opened_slots()
        self.assertTrue(win.open_ai_practice("note", card="pc-k02"))
        page = win.ai_quiz
        slots = page.slots[0]
        self.assertEqual(len(page.inputs), 2)
        self.assertEqual([label.text() for label in slots.inner.findChildren(QLabel) if label.text() in "①②"], ["①", "②"])
        page.inputs[0].setFocus()
        QTest.keyClick(page.inputs[0], Qt.Key.Key_Tab)
        self.assertIs(QApplication.focusWidget(), page.inputs[1])
        page.inputs[0].setText("eval")
        page.inputs[1].setText("zero_grad")
        guikit.click(page.sure_btn)
        self.assertEqual(page.verdict_text.text(), "맞았습니다")
        self.assertEqual(page.answer_line.text(), "정답: ① `train` · ② `zero_grad`")
        self.assertEqual(slots.result.text(), "① 틀림 · ② 맞음")
        self.assertEqual(page.also_text.text(), ai_text.also_line([1]))
        self.assertTrue(page.also_text.isVisible() and page.mine_btn.isVisible())
        guikit.click(page.mine_btn)
        self.assertEqual(page.verdict_text.text(), ai_text.OVERRIDDEN)
        self.assertEqual([field.property("tone") for field in page.inputs], ["success", "success"])
        self.assertFalse(page.also_text.isVisible() or page.mine_btn.isVisible())
        self.assertEqual((self.log("override")[-1]["card"], self.log("override")[-1]["also_value"]), ("pc-k02", {"pc-k01": "eval"}))

    def test_lesson_set_keeps_the_place_chip_of_pattern_cards(self):
        """차시 묶음에 섞인 상황별 코드 문항은 자리가 달라 첫 꼬리표를 남김."""
        win = self.boot()
        self.at(4)
        self.assertTrue(win.open_ai_practice("lesson", lesson="i90"))
        page = win.ai_quiz
        self.assertEqual(page.chips({"chips": ["90차시", "빈칸"], "lesson": "i90"}), ["빈칸"])
        self.assertEqual(page.chips({"chips": ["학습 루프", "고르기"], "lesson": "pc"}), ["학습 루프", "고르기"])

    def test_next_card_and_revisit_use_the_unit_name(self):
        win = self.boot()
        sess = win.ai
        self.at(2)
        sess.mark_read("i90", "90a")
        sess.mark_read("i90", "90b")
        for key in ("90a", "90b"):
            sid = "finished-%s" % key
            sess._append({"kind": "set", "set": sid, "mode": "unit", "lesson": "i90", "unit": key})
            sess._append({"kind": "set_end", "set": sid, "n": 1, "first_pass": 1, "answers": 1})
        win.go_ai()
        home = win.ai_home
        self.assertEqual((home.target["kind"], home.next_card.title.text(), home.next_btn.text()), ("unit", "학습 루프 단원 읽기", "학습 시작"))
        self.assertEqual(home.next_card.line.text(), "「시험 뼈대 단원」\n읽은 뒤 이 단원 문항부터 풉니다. 약 6분.")  # 읽는 시간은 상황별 코드 단원 값
        guikit.click(home.next_btn)
        self.assertEqual((self.page(), win.ai_learn.lid, win.ai_learn.key), (win.ai_learn, "pc", "18a"))
        for card in sess.cards.values():
            if card["lesson"] == "i90" and card["core"]:
                sess._append({"kind": "answer", "set": "s2", "card": card["id"], "result": "pass", "again": 0})
        sess.mark_read("pc", "18a")
        win.go_ai()
        self.assertEqual((home.target["kind"], home.next_card.title.text(), home.next_btn.text()),
                         ("unit", "학습 루프 단원 읽기", "이어서 학습"))
        guikit.click(home.next_btn)
        self.assertEqual((self.page(), win.ai_learn.key), (win.ai_learn, "18a"))
        win.open_ai_revisit()
        self.assertEqual((self.page(), win.ai_revisit.title.text()), (win.ai_revisit, self.UNIT))

    def test_wrong_note_rows_and_code_boxes(self):
        win = self.boot()
        self.opened_slots()
        sess = win.ai
        service.PracticeSet(sess, "s10a", "unit", ["pc-k02"], 1).answer(["eval", "step"], 2, False)
        order = service.PracticeSet(sess, "s10b", "unit", ["pc-o01"], 1)
        right = grade.right_options(order._view(order.queue[0])["item"])
        order.answer([o["no"] for o in order.current()["options"] if o["no"] not in right][:1], 2, False)
        win.go_ai()
        guikit.click(win.ai_home.notes_row)
        page = win.wrong_page
        self.assertEqual((page.list.row_of("pc-k02").title.text(), page.list.row_of("pc-o01").title.text()),
                         ("코드 빈칸 · opt.____()", "순서 고르기 · 줄 순서로 옳은 것 고르기"))
        page.list.pick(page.list.row_of("pc-o01"))
        self.assertEqual(page.item_title.text(), self.UNIT)
        guikit.click(page.explain_btn)
        self.assertGreaterEqual(page.detail.toHtml().count("<pre"), 6)  # 보기 넷과 내 답, 정답이 줄을 지킨 코드 상자
        self.assertIn("1번", page.detail.toPlainText())
        page.list.pick(page.list.row_of("pc-k02"))
        text = page.detail.toPlainText()
        self.assertIn("net.①____()", text)  # 코드 울타리 안 빈칸에도 번호
        self.assertIn("opt.②____()", text)


class DesignTest(AiTest):
    pc = True  # 홈의 상황별 코드 구역, 나란히 보기·돌려 가며 빈칸, 코드 보기 연습도 봄

    def screens(self, win):
        """(이름, 띄우는 함수). 학습 단원은 단계마다와 세 수준 블록을 펴서 답한 뒤, 연습은 답하기 전과 뒤와 끝 요약. 상황별 코드는 단원 단계마다, 돌려 가며 빈칸을
        채점한 뒤, 순서 고르기(2×2) 문항의 답하기 전과 뒤."""
        def learn(lid, key, step):
            return lambda: win.open_ai_unit(lid, key, step)

        def practice_after():
            self.answer(right=False)

        def practice_end():
            page = win.ai_quiz
            while page.item is not None:
                if page.feedback is None:
                    self.answer()
                guikit.click(page.next_btn)

        def levels_open():
            win.open_ai_unit("i90", "90a", 2)
            block = win.ai_learn.view.findChildren(ai_learn.LevelsBlock)[0]
            block.row.set_opened(True)
            recall = block.body.findChildren(ai_learn.RecallBlock)[1]
            recall.field.setText("2.4")
            recall.check()

        def rotate_after():
            win.open_ai_unit("pc", "18a", 3)
            block = win.ai_learn.view.findChildren(ai_learn.RotateBlock)[0]
            block.field().setText("eval")
            block.check()

        def pattern_set():
            win.ai.mark_read("pc", "18a")
            win.open_ai_practice("unit", lesson="pc", unit="18a")

        return [("홈", win.go_ai), ("차시", lambda: win.open_ai_lesson("i90"))] + \
            [("단원 %d단계" % n, learn("i90", "90a", n)) for n in range(1, 5)] + [("세 수준 펼쳐 답한 뒤", levels_open)] + \
            [("다시 보기", win.open_ai_revisit), ("외울 것", lambda: win.open_ai_note("i90", True)),
             ("전체 노트", lambda: win.open_ai_note("i90")),
             ("연습", lambda: win.open_ai_practice("lesson", lesson="i90")), ("연습 답한 뒤", practice_after), ("연습 끝", practice_end)] + \
            [("상황별 단원 %d단계" % n, learn("pc", "18a", n)) for n in range(1, 5)] + \
            [("돌려 가며 빈칸 채점 뒤", rotate_after), ("상황별 연습", pattern_set), ("상황별 연습 답한 뒤", practice_after),
             ("상황별 연습 끝", practice_end)]

    def test_one_primary_button_and_control_sizes(self):
        """화면 상태마다 주 단추 하나, 단추·줄 높이, 단추 글자 8자 이하, 작업 화면 주 단추는 막대 오른쪽 끝. 부모 없는 부품이 따로 창으로
        뜨지 않음(뜨면 창이 초점을 잃어 단축키가 듣지 않음)."""
        win = self.boot((1024, 700))
        self.read_all(2)
        self.at(4)
        shown = []
        spy = WindowSpy(shown)
        QApplication.instance().installEventFilter(spy)
        self.addCleanup(QApplication.instance().removeEventFilter, spy)
        for step in theme.TEXT_STEPS:
            win.set_text(step)
            for name, show in self.screens(win):
                show()
                self.idle()
                page = self.page()
                name = "%s %s" % (step, name)
                self.assertEqual(page.property("ui"), "2", name)
                primaries = kit.visible_primary_buttons(page)
                self.assertLessEqual(len(primaries), 1, "%s: %s" % (name, [b.text() for b in primaries]))
                for button in page.findChildren(QPushButton):
                    if not (button.property("scale") and button.isVisible()):
                        continue
                    least = theme.CONTROL["l"] if button.objectName() == "primary" else theme.CONTROL["s"]
                    self.assertGreaterEqual(button.height(), least, "%s: %s" % (name, button.text()))
                    self.assertLessEqual(len(button.text().replace(" ", "")), 8, "%s: %s" % (name, button.text()))
                for row in page.findChildren(kit.Row):
                    if row.isVisible():
                        self.assertGreaterEqual(row.height(), theme.CONTROL["row"], "%s: %s" % (name, row.title.text()))
                if primaries and page is not win.ai_home:
                    corner = primaries[0].mapTo(win, QPoint(primaries[0].width(), primaries[0].height()))
                    self.assertEqual(corner.x(), win.width() - kit.MARGIN, "%s: %s" % (name, primaries[0].text()))
                self.assertLessEqual(page.minimumSizeHint().width(), win.width(), name)
                text = visible_text(page)
                for word in GOAL_WORDS:
                    self.assertNotIn(word, text, name)
                self.assertEqual(shown, [], name)
        win.set_text(theme.TEXT_DEFAULT)

    def test_code_slot_tokens_and_series_colour(self):
        self.assertEqual(theme.CONTROL["slot"], theme.BASE_TYPE["code"][1] + 8)
        self.assertIn("series_ai", theme.LIGHT)
        self.assertEqual((theme.LIGHT["series_ai"], theme.DARK["series_ai"]), ("#b35c00", "#e8833a"))


class RealLessonTest(AiTest):
    """저장소의 1~9차시 학습 노트와 상황별 코드(공개돼 있으면). 모든 단원의 모든 단계가 오류 없이 그려지고, 숨긴 줄이 보이지 않고,
    1024×700 에서 큰 그림과 넘김 줄을 각각 스크롤로 볼 수 있음. 나란히 보기는 행이 줄을 바꾸지 않고 단계 폭을
    넘지 않음. 세 수준 블록은 차시마다 3~5개이고, 수준마다 첫 답이 화면 채점에서 맞으며, [노트 보기]에서는 정답을 편 채로 그려짐."""
    real_bank = True

    def test_focusing_a_recall_reveals_the_whole_field_at_the_largest_size(self):
        from PyQt6.QtCore import QRect
        win = self.boot((760, 480))
        win.set_text("larger")
        win.open_ai_unit("i01", "1a", 2)
        learn = win.ai_learn
        guikit.wait_until(lambda: learn.pending_position is None)
        recall = learn.view.findChildren(ai_learn.RecallBlock)[0]
        recall.field.setText("draft")
        recall.field.setSelection(1, 3)
        recall.field.setFocus(Qt.FocusReason.TabFocusReason)
        guikit.wait_until(lambda: not win.input_timer.isActive() and win.focused_input is None and learn.pending_position is None)
        viewport = learn.scroll.viewport()
        for widget in (recall.field, recall.check_btn):
            self.assertTrue(viewport.rect().contains(QRect(widget.mapTo(viewport, QPoint()), widget.size())))
            self.assertTrue(widget.visibleRegion().contains(widget.rect()),
                            (widget.size(), widget.visibleRegion().boundingRect()))
        self.assertEqual(recall.field.selectedText(), "raf")

    def test_recall_input_remains_unclipped_after_reducing_the_font(self):
        win = self.boot((1280, 900))
        win.set_text("larger")
        win.open_ai_unit("i01", "1a", 2)
        learn = win.ai_learn
        guikit.wait_until(lambda: learn.pending_position is None)
        win.set_text("normal")
        guikit.wait_until(lambda: learn.pending_position is None)
        recall = learn.view.findChildren(ai_learn.RecallBlock)[0]
        recall.field.setFocus()
        guikit.wait_until(lambda: not win.input_timer.isActive() and win.focused_input is None)
        self.assertTrue(recall.field.visibleRegion().contains(recall.field.rect()),
                        (recall.field.geometry(), recall.entry.geometry(), recall.field.visibleRegion().boundingRect()))

    def test_every_step_of_lessons_one_to_nine_renders(self):
        win = self.boot((1024, 700))
        learn = win.ai_learn
        started = time.monotonic()
        figures = 0
        levels = {}
        patterns = [g["id"] for g in win.ai.overview()["patterns"] if g["ready"]]
        for lid in ("i01", "i02", "i03", "i04", "i05", "i06", "i07", "i08", "i09", *patterns):
            for unit in win.ai.unit_list(lid):
                self.assertTrue(win.open_ai_unit(lid, unit["key"], 1), (lid, unit["key"]))
                for index in range(len(learn.steps)):
                    learn.show_step(index)
                    guikit.pump(30)
                    where = "%s %s %d" % (lid, unit["key"], index + 1)
                    text = "\n".join(piece.toPlainText() for piece in learn.view.findChildren(TextPiece))
                    self.assertNotIn("<!--", text, where)
                    self.assertNotIn(ai_text.BLOCK_BROKEN, visible_text(learn.view), where)
                    for block in learn.view.findChildren(ai_learn.LevelsBlock):  # 세 수준 블록은 펴서 봄
                        block.row.set_opened(True)
                        guikit.pump(30)
                        levels[lid] = levels.get(lid, 0) + 1
                        for recall in block.body.findChildren(ai_learn.RecallBlock):
                            recall.field.setText(recall.block["answer"][0])
                            recall.check()
                            self.assertEqual("맞았습니다", recall.verdict.text(), "%s %d살" % (where, recall.block["level"]))
                        dialog = ai_learn.NoteDialog(win, lid, "%s/%s" % (unit["key"], learn.steps[index]["no"]))
                        dialog.show()
                        guikit.pump(30)
                        shown = dialog.view.findChildren(ai_learn.LevelsBlock)[0]
                        shown.row.set_opened(True)
                        guikit.pump(30)
                        recalls = shown.body.findChildren(ai_learn.RecallBlock)
                        self.assertEqual(3, len(recalls), where)
                        self.assertTrue(all(r.result.isVisibleTo(dialog) and not r.entry.isVisibleTo(dialog) for r in recalls), where)
                        self.assertNotIn(ai_text.BLOCK_BROKEN, visible_text(shown), where)
                        dialog.close()
                        guikit.pump()
                        shown = visible_text(block) + "\n".join(piece.toPlainText() for piece in block.findChildren(TextPiece))
                        for bad in (ai_text.BLOCK_BROKEN, "<!--", "그림 준비 중", MISSING_TEXT):
                            self.assertNotIn(bad, shown, where)
                        self.assertEqual(3, len(block.figures), where)
                        for figure in block.figures:
                            self.assertLessEqual(figure.picture.pixmap().deviceIndependentSize().width(), figure.width(), where)
                    for block in learn.view.findChildren(ai_learn.DiffBlock):
                        self.assertEqual({line.height() for line in block.lines}, {theme.TYPE["learn_code"][1]}, where)
                        self.assertLessEqual(learn.view.minimumSizeHint().width(), learn.view.width(), where)
                    for block in learn.view.findChildren(ai_learn.RotateBlock):
                        self.assertEqual(block.count.text(), "1 / %d" % len(block.queue), where)
                    for figure in learn.view.figures:
                        if figure.movie is None:
                            continue
                        figures += 1
                        for _ in range(3):  # 글 조각이 높이를 잡은 뒤 다시 맞춤. 그림 위쪽을 먼저 보이고 단추까지 내림
                            learn.scroll.ensureWidgetVisible(figure.picture, 0, 0)
                            guikit.pump(20)
                            learn.scroll.ensureWidgetVisible(figure.controls, 0, 0)
                            guikit.pump(20)
                        viewport = learn.scroll.viewport()
                        controls = QRect(figure.controls.mapTo(viewport, QPoint()), figure.controls.size())
                        self.assertTrue(viewport.rect().contains(controls), where)
                        learn.scroll.ensureWidgetVisible(figure.picture, 0, 0)
                        guikit.pump(20)
                        picture = QRect(figure.picture.mapTo(viewport, QPoint()), figure.picture.size())
                        if picture.height() <= viewport.height():
                            self.assertTrue(viewport.rect().contains(picture), where)
                        else:
                            self.assertTrue(viewport.rect().intersects(picture), where)
                        self.assertLessEqual(figure.picture.pixmap().deviceIndependentSize().width(), figure.width(), where)
        self.assertGreater(figures, 20)
        lessons = ("i01", "i02", "i03", "i04", "i05", "i06", "i07", "i08", "i09")
        self.assertEqual({lid: True for lid in lessons}, {lid: 3 <= levels.get(lid, 0) <= 5 for lid in lessons}, levels)  # 차시마다 3~5개
        self.assertLess(time.monotonic() - started, 600)


if __name__ == "__main__":
    unittest.main()
