# -*- coding: utf-8 -*-
"""웹 면접 준비 화면(gui/web_home.py, web_mission.py, web_drill.py, web_learn.py, web_setup.py)과 첫 화면의 웹 줄.
실제 MainWindow 를 띄우되 웹 은행은 tests/web_bank, 여행 은행은 tests/journey_bank, 풀이 폴더·웹 홈 폴더·검사 도구 폴더는 임시 폴더,
제출 모듈·Node·vitest·설치·폴더 열기·화면 서버·브라우저 열기는 가짜를 씀. 시계는 서비스의 now(기록 시각)와 화면의 clock(흐른 초)을 같이 돌림.
PyQt6 가 없으면 전부 건너뜀."""
import ast
import base64
import datetime
import os
import re
import shutil
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QPoint, QRect, QSettings, Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QLabel, QPushButton, QScrollArea  # noqa: E402

import session  # noqa: E402
import study  # noqa: E402
from gui import errors, kit, theme, web_text  # noqa: E402
from gui.docview import FigureView, TextPiece  # noqa: E402
from gui.web_home import NO_STUCK  # noqa: E402
from gui.web_learn import scroll_to_heading  # noqa: E402
from gui.web_mission import RESUMED_TEXT, SERVE_STOPPED, SERVE_TIP, open_folder  # noqa: E402
from gui.web_setup import BUSY_ELSEWHERE, SetupDialog  # noqa: E402
from gui.window import MainWindow  # noqa: E402
from journey import bank as journey_bank  # noqa: E402
from journey import node as node_finder  # noqa: E402
from journey import runner  # noqa: E402
from tests.test_gui_hub import FakeGitFlow, bright_share  # noqa: E402
from tests.test_web_dev import (FakeServer, FakeTestRun, HangingRun, fake_popen, group_gone, reset_fakes, start_child,  # noqa: E402
                                 vitest_report, wait_file)
from tests.test_web_service import FAKE_NODE, FakeVitest  # noqa: E402
from webprep import bank, checks, dev, service, stack  # noqa: E402

FIXTURE = os.path.join(guikit.ROOT, "tests", "web_bank")
JOURNEY_FIXTURE = os.path.join(guikit.ROOT, "tests", "journey_bank")
USER = "tester"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAMgAAAAUAQMAAADyauCJAAAAA1BMVEUlN0fhQ83WAAAAD0lEQVR42mNgGAWjgIEBAAIIAAFQMUmAAAAAAElFTkSuQmCC")


def doc_text(view):
    """DocView 의 글 조각을 이어 붙인 글."""
    return "\n".join(piece.toPlainText() for piece in view.pieces if isinstance(piece, TextPiece))


def doc_sizes(view):
    """DocView 첫 글 조각의 줄마다 (글, 글자 크기 px)."""
    piece = next(p for p in view.pieces if isinstance(p, TextPiece))
    out, block = {}, piece.document().begin()
    while block.isValid():
        if block.text().strip():
            out[block.text().strip()] = block.begin().fragment().charFormat().font().pixelSize()
        block = block.next()
    return out


def inside(win, widget):
    """widget 이 창 안에 다 들어와 있는지."""
    return win.rect().contains(QRect(widget.mapTo(win, QPoint(0, 0)), widget.size()))


def scroll_to(widget):
    """widget 이 스크롤 칸 안에 있으면 그 칸을 widget 이 보이는 자리로 굴림. 굴린 칸을 돌려줌(없으면 None)."""
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QScrollArea):
            parent.ensureWidgetVisible(widget)
            guikit.pump()
            return parent
        parent = parent.parentWidget()
    return None


def name_of(widget):
    """단추나 목록 줄의 글. 목록 줄(kit.Row)은 제목으로 부름."""
    return widget.text() if hasattr(widget, "text") else widget.title.text()


def shows_whole(label):
    """글이 잘리지 않고 다 보이는지. 줄바꿈하는 글은 지금 폭에서 필요한 높이를, 한 줄 글은 필요한 폭을 봄."""
    if label.wordWrap():
        return label.height() >= label.heightForWidth(label.width())
    return label.width() >= label.sizeHint().width()


def layout_height(dialog):
    """대화상자의 레이아웃이 지금 폭에서 줄바꿈까지 셈한 높이."""
    layout = dialog.layout()
    return layout.totalHeightForWidth(dialog.width()) if layout.hasHeightForWidth() else layout.totalSizeHint().height()


class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gui_web_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        study.write_text(os.path.join(self.repo, stack.VITEST_MJS), "")
        shutil.copyfile(os.path.join(guikit.ROOT, "package-lock.json"), os.path.join(self.repo, "package-lock.json"))
        study.write_text(stack.marker_path(self.repo), stack.lock_hash(self.repo) + "\n")
        self.clock, self.mono, self.node = "2026-10-21T09:00:00", 1000.0, FAKE_NODE
        real = service.WebSession
        for target, name, value in ((study, "SUBMISSIONS_DIR", os.path.join(self.tmp, "submissions")),
                                    (study, "USER_FILE", os.path.join(self.tmp, ".study_user")),
                                    (runner, "CACHE_DIR", os.path.join(self.tmp, "cache")), (journey_bank, "BANK_DIR", JOURNEY_FIXTURE),
                                    (bank, "BANK_DIR", FIXTURE), (checks, "_popen", FakeVitest), (service, "now", lambda: self.clock),
                                    (stack, "find_node", lambda saved=None, probe=False: self.node),
                                    (service, "WebSession", lambda user, repo=None, home=None, node_path=None:
                                     real(user, repo=self.repo, home=home, node_path=node_path))):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        os.environ.pop("STUDY_USER", None)
        os.environ["STUDY_WEB_HOME"] = os.path.join(self.tmp, "web_home")
        self.addCleanup(setattr, sys, "excepthook", sys.excepthook)
        self.logs = os.path.join(self.tmp, ".study_logs")
        errors.install(self.logs)
        session.save_user(USER)
        FakeVitest.calls = []
        self.git = FakeGitFlow()
        self.settings = QSettings(os.path.join(self.tmp, "settings.ini"), QSettings.Format.IniFormat)
        self.win, self.opened = None, []

    def tearDown(self):
        win = self.win
        if win is not None:
            guikit.wait_until(lambda: win.job is None)
            for dialog in (win.dialog, win.web_home.setup_dialog, win.web_mission.setup_dialog):
                if dialog is not None:
                    dialog.close()
            win.close()
            win.deleteLater()
            guikit.pump()
        if errors.state["dialog"] is not None:
            errors.state["dialog"].close()
        crashed = os.path.isdir(self.logs)  # 슬롯 안의 예외는 테스트로 올라오지 않고 기록만 남음
        report = "".join(study.read_text(os.path.join(self.logs, name)) for name in os.listdir(self.logs)) if crashed else ""
        self.assertFalse(crashed, report)

    # 도우미

    def boot(self, size=(1280, 800)):
        self.win = win = MainWindow(self.settings, lambda root, user: (self.git, ""))
        win.open_url = lambda url: None
        win.open_folder = self.open_folder
        win.web_mission.clock = lambda: self.mono
        win.web_drill.clock = lambda: self.mono
        win.resize(*size)
        win.show()
        win.boot()
        self.idle()
        return win

    def open_folder(self, path):
        self.opened.append(path)
        return "Cursor 에서 폴더를 열었습니다."

    def idle(self):
        guikit.pump()
        guikit.wait_until(lambda: self.win.job is None)
        guikit.pump()

    def page(self):
        return self.win.pages.currentWidget()

    def choose(self, key):
        self.assertTrue(self.win.dialog.isVisible())
        guikit.click(self.win.dialog.buttons[key])
        self.idle()

    def tick(self, minutes=0, seconds=0):
        """기록 시각과 화면의 시계를 같이 돌림."""
        when = datetime.datetime.fromisoformat(self.clock) + datetime.timedelta(minutes=minutes, seconds=seconds)
        self.clock = when.isoformat(timespec="seconds")
        self.mono += minutes * 60 + seconds

    def record_path(self):
        return os.path.join(study.SUBMISSIONS_DIR, USER, "web", "record.json")

    def log(self):
        return study.read_json(self.record_path())["log"] if os.path.isfile(self.record_path()) else []

    def kinds(self):
        return [e["kind"] for e in self.log()]

    def web(self):
        """창과 같은 기록을 쓰는 서비스. 화면을 거치지 않고 기록을 만들 때 씀."""
        return service.WebSession(USER)

    def solve(self, upto):
        secrets = bank.load_secrets(os.path.join(FIXTURE, "missions", "x01"))
        for rel, text in bank.solution_files(secrets, upto).items():
            study.write_text(os.path.join(study.SUBMISSIONS_DIR, USER, "web", "missions", "x01", *rel.split("/")), text)

    def to_live(self, web=None, explained=True):
        web = web or self.web()
        web.get("x01")
        web.start("x01", no_ai=True)
        if explained:
            web.explain_done("x01", [1, 1])
        return web

    def open_mission(self, mid="x01"):
        self.win.open_mission(mid)
        self.idle()
        self.assertIs(self.page(), self.win.web_mission, self.win.dialog and self.win.dialog.text.text())
        return self.win.web_mission

    def open_drill(self, cid):
        self.win.open_drill(cid)
        self.idle()
        self.assertIs(self.page(), self.win.web_drill, self.win.dialog and self.win.dialog.text.text())
        return self.win.web_drill


class HubRowTest(WebTest):
    def test_a_due_review_becomes_the_next_card_on_both_homes(self):
        """한 번 푼 사슬의 복습 날이 되면 첫 화면과 웹 홈의 이어서 할 일이 그 사슬이고, 단추를 누르면 드릴이 열림."""
        web = self.web()
        web.answer("90-B", 1, 10, [1], [])
        web.finish_chain("90-B")
        later = datetime.date.fromisoformat(self.clock[:10]) + datetime.timedelta(days=30)
        with mock.patch.object(service, "today", lambda: later):
            win = self.boot()
            hub = win.hub
            title = web.chains["90-B"]["title"]
            self.assertEqual((hub.next_card.title.text(), hub.next_btn.text()), (title, "복습 시작"))
            self.assertIn("오늘 복습 1개", hub.summary.text())
            win.go_web()
            self.idle()
            home = win.web_home
            self.assertEqual((home.next_card.title.text(), home.next_btn.text()), (title, "복습 시작"))
            guikit.click(home.next_btn)
            self.idle()
            self.assertEqual((self.page(), win.web_drill.cid), (win.web_drill, "90-B"))

    def test_row_numbers_follow_the_service_and_web_days_reach_the_chart(self):
        win = self.boot()
        hub = win.hub
        self.assertTrue(win.web_node_known)
        self.assertEqual(hub.web_row.second.text(), "미션 1개 중 0개 끝남 · 새 사슬 2개")
        self.assertFalse(hub.web_row.inert)
        today = datetime.date.today()
        self.assertEqual(hub.chart.days[-1], (today, 0, 0, 0))
        self.assertEqual(hub.streak.text(), "연속 학습 0일")
        self.assertEqual(hub.summary.text(), "진행 중인 미션과 오늘 복습이 없습니다.")
        self.assertEqual((hub.next_card.title.text(), hub.next_btn.text()), ("진단 테스트", "시작"))  # 어느 트랙에도 기록이 없으면 파이썬
        self.assertTrue(hub.next_card.line.text().startswith("파이썬 스터디 · "), hub.next_card.line.text())
        self.assertEqual(len(kit.visible_primary_buttons(hub)), 1)
        self.clock = datetime.datetime.now().isoformat(timespec="seconds")  # 검사와 드릴을 오늘 기록함
        web = self.to_live()
        web.check("x01")
        web.answer("90-A", 1, 10, [1], [1])
        web.finish_chain("90-A")
        web.show("l90")
        hub.refresh()
        self.assertEqual(hub.chart.days[-1], (today, 0, 0, 2))  # 검사 한 번과 끝낸 사슬 하나
        self.assertEqual((hub.streak.text(), hub.total.text()), ("연속 학습 1일", "채점 2회"))
        self.assertEqual(hub.web_row.second.text(), "미션 1개 중 0개 끝남 · 새 사슬 1개")
        self.assertEqual(hub.summary.text(), "진행 중인 미션 1개가 있습니다.")
        self.assertEqual((hub.next_card.title.text(), hub.next_btn.text()), (win.web.missions["x01"]["title"], "이어 하기"))
        self.assertTrue(hub.next_card.line.text().startswith("웹 면접 준비 · 라이브 코딩 미션 · 1단계 · "), hub.next_card.line.text())
        guikit.click(hub.next_btn)
        self.idle()
        self.assertEqual((self.page(), win.web_mission.mid), (win.web_mission, "x01"))
        win.go_hub()
        self.node = None
        hub.refresh()
        self.assertEqual(hub.web_row.second.text(), "미션 1개 중 0개 끝남 · 새 사슬 1개 · Node.js 없음")

    def test_broken_web_record_disables_the_row_and_the_other_tracks_still_work(self):
        study.write_text(self.record_path(), '{"log": [<<<<')
        win = self.boot()
        hub = win.hub
        self.assertIsNone(win.web)
        self.assertTrue(hub.web_error.isVisible())
        self.assertIn("record.json", hub.web_error.text.text())
        self.assertTrue(hub.web_row.inert)
        self.assertEqual(hub.web_row.second.text(), "기록을 읽지 못했습니다.")
        self.assertFalse(hub.journey_row.inert)
        self.assertEqual(hub.chart.days[-1][3], 0)
        guikit.click(hub.web_row)
        self.assertIs(self.page(), hub)
        guikit.click(hub.python_row)
        self.assertIs(self.page(), win.home)

    def test_entering_and_leaving_the_web_home(self):
        win = self.boot()
        guikit.click(win.hub.web_row)
        self.assertEqual((self.page(), win.area), (win.web_home, "web"))
        guikit.click(win.web_home.hub_btn)
        self.assertEqual((self.page(), win.area), (win.hub, "hub"))

    def test_node_is_looked_for_again_in_the_worker_after_the_journey_forgets_it(self):
        win = self.boot()
        workers = []  # node() 를 부른 스레드가 워커인지. 현황(overview)도 node() 를 부르는데 그때는 node 모듈의 기억을 읽음
        real = win.web.node
        win.web.node = lambda probe=False: workers.append(threading.current_thread() is not threading.main_thread()) or real(probe)
        win.web_node_seen = True  # 진짜 찾기는 node 모듈이 결과를 기억함
        with mock.patch.object(node_finder, "searched", return_value=False):  # 여행의 [다시 찾기]가 기억을 모두 버린 뒤
            guikit.click(win.hub.web_row)
            self.idle()
        self.assertEqual((workers, self.page()), ([True, False], win.web_home))  # 워커에서 한 번 찾은 뒤 웹 홈이 현황을 읽음
        guikit.click(win.web_home.hub_btn)
        self.idle()
        self.assertEqual((workers, self.page()), ([True, False, False], win.hub))  # 다시 찾지 않음


class HomeTest(WebTest):
    def test_lists_show_today_missions_topics_and_pages(self):
        win = self.boot()
        win.go_web()
        self.idle()
        home = win.web_home
        self.assertEqual((home.stack_dot.state, home.stack_label.text()), ("ready", "검사 도구 준비됨"))
        self.assertFalse(home.problem.isVisible())
        self.assertEqual((home.next_card.title.text(), home.next_card.line.text(), home.next_btn.text()),
                         ("시험 페이지: state 가 바뀌면 무엇이 다시 그려지나요", "학습 노트", "노트 읽기"))
        rows = [(r.title.text(), r.second.text(), r.mark.state) for r in home.today_list.rows]
        self.assertEqual(rows, [("버튼을 눌렀는데 화면이 그대로일 때", "시작 전 · 시험 주제: state 와 렌더링", "todo"),
                                ("state 를 두 번 바꿀 때", "시작 전 · 시험 주제: state 와 렌더링", "todo")])
        self.assertEqual(home.today_minutes.text(), "약 8분")
        self.assertTrue(all(r.height() >= 72 for r in home.today_list.rows))  # 두 줄짜리 줄은 72 이상
        rows = home.mission_list.rows
        self.assertEqual([(r.title.text(), r.second.text(), r.end.text(), r.mark.state) for r in rows],
                         [("횟수 세기 버튼", "시작 전 · 읽기 2분, 실전 6분", "워밍업", "todo")])
        self.assertEqual((home.mission_list.more_btn.text(), home.mission_count.text()), ("준비 중 1개 보기", "1개 중 0개 끝남"))
        self.assertEqual(sorted(home.chips), ["t90"])  # 준비 중인 주제는 칩이 아니라 접힌 글
        self.assertTrue(home.chips["t90"].isChecked())
        self.assertEqual((home.more_topics_btn.text(), home.more_topics.isVisible()), ("준비 중 1개 보기", False))
        guikit.click(home.more_topics_btn)
        self.assertTrue(home.more_topics.isVisible())
        self.assertEqual(home.topic_count.text(), "사슬 2개 중 0개 끝남")
        self.assertEqual([(r.title.text(), r.second.text(), r.mark.state) for r in home.chain_list.rows],
                         [("버튼을 눌렀는데 화면이 그대로일 때", "시작 전", "todo"), ("state 를 두 번 바꿀 때", "시작 전", "todo")])
        self.assertEqual([(r.title.text(), r.second.isVisible(), r.mark.state) for r in home.page_list.rows],
                         [("시험 페이지: state 가 바뀌면 무엇이 다시 그려지나요", False, "todo")])
        self.assertEqual((home.page_list.more_btn.text(), home.page_count.text()), ("준비 중 1개 보기", "1개 중 0개 끝남"))
        self.assertEqual(home.talked.text(), NO_STUCK)
        texts = " ".join(label.text() for label in home.findChildren(QLabel))
        for hidden in ("x01", "x02", "t90", "l90", "90-A", "상자"):  # 내부 ID 는 화면에 없음
            self.assertNotIn(hidden, texts)
        web = self.to_live()
        web.answer("90-A", 1, 10, [0], [], False)
        web.finish_chain("90-A")
        web.show("l90")
        self.tick(minutes=1)
        home.refresh()
        self.assertEqual(home.talked.text(), "막혀도 끝까지 말함 0/1")
        self.assertEqual((home.next_card.title.text(), home.next_card.line.text(), home.next_btn.text()),
                         ("횟수 세기 버튼", "라이브 코딩 미션 · 1단계 · 5분 남음", "이어 하기"))
        row = home.mission_list.rows[0]
        self.assertEqual((row.second.text(), row.mark.state), ("진행 중 · 1단계 · 5분 남음", "progress"))
        # 막힌 사슬은 바로 오늘 다시 풀게 잡혀서 사슬 줄과 오늘 복습에 '오늘 복습'으로 보임
        self.assertEqual([(r.second.text(), r.mark.state) for r in home.chain_list.rows], [("오늘 복습", "review"), ("시작 전", "todo")])
        self.assertEqual([(r.title.text(), r.second.text(), r.mark.state) for r in home.today_list.rows][0],
                         ("버튼을 눌렀는데 화면이 그대로일 때", "시험 주제: state 와 렌더링 · 두 번째 복습", "review"))
        self.assertEqual(home.page_list.rows[0].mark.state, "done")
        self.assertEqual(home.page_count.text(), "1개 중 1개 끝남")

    def test_rows_and_the_card_open_the_screens(self):
        win = self.boot()
        win.go_web()
        self.idle()
        home = win.web_home
        guikit.click(home.next_btn)  # 이어서 할 일: 학습 노트
        self.assertEqual((self.page(), win.web_learn.pid), (win.web_learn, "l90"))
        guikit.click(win.web_learn.back_btn)
        self.assertIs(self.page(), home)
        guikit.click(home.today_list.rows[0])
        self.assertEqual((self.page(), win.web_drill.cid), (win.web_drill, "90-A"))
        guikit.click(win.web_drill.back_btn)
        self.assertIs(self.page(), home)
        guikit.click(home.chain_list.rows[1])
        self.assertEqual((self.page(), win.web_drill.cid), (win.web_drill, "90-B"))
        guikit.click(win.web_drill.back_btn)
        guikit.click(home.mission_list.rows[0])
        self.assertEqual((self.page(), win.web_mission.mid), (win.web_mission, "x01"))
        guikit.click(win.web_mission.home_btn)
        guikit.click(home.page_list.rows[0])
        self.assertEqual((self.page(), win.web_learn.pid), (win.web_learn, "l90"))
        guikit.click(win.web_learn.back_btn)
        self.assertIs(self.page(), home)
        self.assertEqual(self.kinds(), ["learn", "learn"])
        home.set_busy(True, "제출하는 중입니다.")  # 일이 도는 동안은 줄을 눌러도 열리지 않음
        guikit.click(home.mission_list.rows[0])
        self.assertIs(self.page(), home)
        self.assertEqual((home.status.text(), home.busy_bar.isVisible(), home.next_btn.isEnabled()), ("제출하는 중입니다.", True, False))
        home.set_busy(False)
        self.assertEqual(len(kit.visible_primary_buttons(home)), 1)  # 주 단추는 이어서 할 일 카드의 것 하나

    def test_unreadable_items_are_named_by_title_in_a_warning_band(self):
        """읽지 못한 미션은 준비 중으로 세지 않고, 알림 띠에 id 없이 제목만 나옴. 파일과 까닭은 도움말에 있음."""
        win = self.boot()
        win.go_web()
        self.idle()
        home, real = win.web_home, win.web.overview

        def broken():
            view = real()
            view["missions"][0].update(ready=False, error="meta.json 을 읽을 수 없습니다")
            view["bank_errors"] = ["x01: meta.json 을 읽을 수 없습니다"]
            return view

        title = real()["missions"][0]["title"]
        with mock.patch.object(win.web, "overview", broken):
            home.refresh()
        self.assertTrue(home.notice.isVisible())
        self.assertEqual((home.notice.property("tone"), home.notice.word.text()), ("warning", "주의"))
        self.assertIn(title, home.notice.text.text())
        self.assertNotIn("x01", home.notice.text.text())
        self.assertIn("x01", home.notice.toolTip())
        self.assertNotIn(title, [row.title.text() for row in home.mission_list.rows])
        waiting = sum(1 for row in real()["missions"] if not row["ready"])
        self.assertEqual(home.mission_list.more_btn.text(), "준비 중 %d개 보기" % waiting)  # 준비 중으로도 세지 않음

    def test_a_record_broken_while_running_clears_the_page_and_the_screens_say_why(self):
        win = self.boot()
        win.go_web()
        self.idle()
        home = win.web_home
        study.write_text(self.record_path(), '{"log": [<<<<')
        home.refresh()
        self.assertTrue(home.notice.isVisible())
        self.assertIn("record.json", home.notice.text.text())
        self.assertEqual((home.chips, home.mission_list.rows, home.stack_label.text(), home.chain_list.rows), ({}, [], "", []))
        self.assertFalse(home.next_card.isVisible())
        win.open_mission("x01")
        guikit.pump()
        self.assertIn("record.json", win.dialog.text.text())
        self.assertIs(self.page(), home)

    def test_without_node_the_problem_line_shows(self):
        self.node = None
        win = self.boot()
        win.go_web()
        self.idle()
        home = win.web_home
        self.assertTrue(home.problem.isVisible())
        self.assertIn("Node.js 22.12", home.problem.text.text())
        self.assertEqual((home.stack_dot.state, home.stack_label.text()), ("todo", "Node.js 없음"))

    def test_setup_dialog_installs_removes_and_shows_failures(self):
        win = self.boot()
        win.go_web()
        self.idle()
        home = win.web_home
        guikit.click(home.setup_btn)
        dialog = home.setup_dialog
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.state.text(), "검사 도구가 설치되어 있어 미션의 [검사하기]를 쓸 수 있습니다.")
        self.assertEqual((dialog.badge.text(), dialog.badge.property("tone")), ("설치됨", "success"))
        self.assertFalse(dialog.install_btn.isVisible())  # 설치된 상태에서는 주 단추 없이 [닫기]
        self.assertFalse(dialog.details.isVisible() or dialog.work.isVisible())  # 경로·Node 판·다시 설치·지우기는 [자세히] 안
        gap = dialog.close_btn.mapTo(dialog, dialog.close_btn.rect().topLeft()).y() - dialog.state.geometry().bottom() - 1
        self.assertEqual(gap, 32)  # 본문과 단추 사이
        guikit.click(dialog.more_btn)
        self.assertIn("약 80MB", dialog.consent.toPlainText())
        self.assertIn("/fake/node", dialog.consent.toPlainText())  # 경로와 Node 판은 동의 글에만
        self.assertTrue(dialog.again_btn.isVisible() and dialog.remove_btn.isEnabled())
        self.assertGreaterEqual(dialog.height(), layout_height(dialog))
        self.assertEqual(kit.visible_primary_buttons(dialog), [])
        guikit.click(dialog.remove_btn)
        self.assertEqual(win.dialog.buttons["remove"].objectName(), "danger")  # 되돌릴 수 없는 확인은 빨간 단추, Enter 없음
        self.assertFalse(win.dialog.buttons["remove"].isDefault())
        self.choose("remove")  # 지우기는 워커에서 돌고 choose 가 끝나기를 기다림
        self.assertFalse(os.path.isdir(os.path.join(self.repo, "node_modules")))
        self.assertEqual((dialog.result.text.text(), dialog.result.property("tone"), dialog.busy), ("지웠습니다: node_modules", "success", False))
        self.assertEqual((dialog.install_btn.text(), dialog.install_btn.isVisible(), dialog.remove_btn.isVisible()), ("설치하기", True, False))
        self.assertEqual((dialog.badge.text(), home.stack_label.text()), ("설치 전", "검사 도구 설치 전"))
        self.assertTrue(home.problem.isVisible())
        log = stack.log_path()

        def fake_install(root, node, report=None):
            report("검사 도구를 설치하는 중입니다. 몇 분 걸릴 수 있습니다.")
            study.write_text(log, "$ node npm-cli.js ci\nadded 240 packages\n")
            study.write_text(os.path.join(root, stack.VITEST_MJS), "")
            study.write_text(stack.marker_path(root), stack.lock_hash(root) + "\n")
            return {"ok": True, "message": "검사 도구를 설치했습니다(3초).", "seconds": 3.0, "log": log}

        with mock.patch.object(stack, "install", fake_install):
            guikit.click(dialog.install_btn)
            self.idle()
        self.assertEqual(dialog.result.text.text(), "검사 도구를 설치했습니다(3초).")
        self.assertFalse(dialog.busy)
        self.assertFalse(dialog.install_btn.isVisible())
        self.assertTrue(dialog.log.isVisible())  # 로그 칸은 설치가 끝나도 남아 실패할 때 창이 크게 늘지 않음
        installed_height = dialog.height()
        self.assertEqual(home.stack_label.text(), "검사 도구 준비됨")
        self.assertFalse(home.problem.isVisible())
        failed = {"ok": False, "message": "설치가 실패했습니다(종료 코드 1). 로그를 확인해 주세요: %s" % log, "seconds": 1.0, "log": log}
        with mock.patch.object(stack, "install", return_value=failed):
            guikit.click(dialog.again_btn)
            self.idle()
        self.assertEqual(dialog.result.text.text(), failed["message"])
        self.assertEqual(dialog.result.property("tone"), "danger")
        self.assertIn("added 240 packages", dialog.log.toPlainText())
        self.assertTrue(dialog.log.isVisible())
        self.assertGreaterEqual(dialog.height(), layout_height(dialog))  # 로그와 결과 띠가 나타나도 위젯이 겹치지 않음
        self.assertLessEqual(abs(dialog.height() - installed_height), 2 * theme.TYPE["body"][1])  # 실패 문구가 한두 줄 더 길 뿐
        self.assertEqual((dialog.install_btn.text(), dialog.install_btn.isVisible(), dialog.again_btn.isVisible()), ("다시 설치하기", True, False))
        with mock.patch.object(win, "run_job", return_value=False):  # 다른 일이 도는 중이면 잠긴 채 남지 않음
            dialog.install()
        self.assertEqual((dialog.busy, dialog.status.text(), dialog.install_btn.isEnabled()), (False, BUSY_ELSEWHERE, True))
        self.node = None
        guikit.click(dialog.install_btn)  # Node 가 없으면 설치 단추는 꺼짐
        self.idle()
        dialog.refresh()
        self.assertFalse(dialog.again_btn.isEnabled() or dialog.install_btn.isEnabled())
        self.assertEqual((dialog.badge.text(), dialog.badge.property("tone")), ("Node.js 없음", "danger"))
        dialog.close()


class MissionTest(WebTest):
    def test_before_and_reading_states_and_the_reading_timer(self):
        win = self.boot()
        page = self.open_mission()
        self.assertEqual((page.view["phase"], page.title.text()), ("none", "횟수 세기 버튼"))
        self.assertIs(page.left.currentWidget(), page.brief_view)
        self.assertIs(page.right.currentWidget(), page.info_page)
        self.assertTrue(doc_text(page.brief_view).startswith("읽기 시간에 보는 안내"))  # 미션 이름은 위 막대에만, id 는 어디에도 없음
        self.assertNotIn("x01.", doc_text(page.brief_view))
        self.assertEqual(page.info_values["시간"].text(), "읽기 2분, 실전 6분")
        self.assertEqual(page.info_values["단계"].text(), "0~2단계. 0단계는 말로 설명합니다.")
        self.assertEqual([row.title.text() for row in page.note_rows.rows], ["시험 페이지: state 가 바뀌면 무엇이 다시 그려지나요"])
        self.assertFalse(page.clock_box.isVisible() or page.done_badge.isVisible())  # 읽기·실전 시간은 미션 정보에만
        self.assertFalse(page.ai_box.isVisible())  # 실전 전 확인은 읽는 중에만
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(page)], ["미션 받기"])
        self.assertFalse(page.start_btn.isVisible())
        self.assertFalse(page.folder_btn.isEnabled())
        self.assertFalse(page.brief_btn.isVisible())
        self.assertEqual([state for _, _, state in page.stepper.steps], ["lock", "lock", "lock"])
        guikit.click(page.get_btn)
        self.assertEqual(page.view["phase"], "reading")
        self.assertEqual(self.kinds(), ["receive"])
        self.assertTrue(page.folder_btn.isEnabled())
        guikit.click(page.folder_btn)
        self.assertEqual(self.opened, [page.view["dir"]])
        self.assertEqual(page.status.text(), "Cursor 에서 폴더를 열었습니다.")
        self.assertTrue(page.clock_box.isVisible())
        self.assertEqual((page.clock_caption.text(), page.timer_label.text()), ("읽기 남은 시간", "2:00"))
        self.tick(seconds=30)
        page.tick()
        self.assertEqual(page.timer_label.text(), "1:30")
        self.tick(minutes=2, seconds=30)
        page.tick()
        self.assertEqual((page.clock_caption.text(), page.timer_label.text()), ("읽기 시간 끝", "+1:00"))
        self.assertEqual(page.timer_label.property("tone"), "danger")
        self.assertTrue(page.ai_box.isVisible())
        page.ai_box.box.setChecked(True)
        guikit.click(page.note_rows.rows[0])  # 같이 읽을 노트를 보고 돌아와도 표시가 남음
        self.idle()
        self.assertIs(self.page(), win.web_learn)
        guikit.click(win.web_learn.back_btn)
        self.idle()
        self.assertIs(self.page(), page)
        self.assertTrue(page.ai_box.box.isChecked())
        guikit.click(page.start_btn)
        self.assertEqual((page.view["phase"], page.view["current"]["no"]), ("live", 0))
        self.assertTrue(self.log()[-1]["no_ai"])
        self.assertEqual((page.clock_caption.text(), page.timer_label.text()), ("남은 시간", "6:00"))
        self.assertEqual([state for _, _, state in page.stepper.steps], ["now", "lock", "lock"])

    def test_live_flow_from_explaining_to_the_explanation(self):
        win = self.boot()
        page = self.open_mission()
        guikit.click(page.get_btn)
        guikit.click(page.start_btn)
        # 0단계: 목표 시간이 지나야 점검 항목이 열림
        self.assertIs(page.left.currentWidget(), page.request_page)
        self.assertEqual((page.step_caption.text(), page.step_title.text()), ("0단계", "코드 설명"))
        self.assertEqual(page.quote_text.text(), "받은 코드를 어떻게 읽으셨는지 1분 정도 설명해 주세요. 버튼을 눌렀을 때 무슨 일이 일어나는지 위주로요.")
        self.assertIn("목표 시간 1분이 지나면 열립니다", doc_text(page.request_view))
        self.assertFalse(page.request_items.isVisible())
        self.assertFalse(page.explain_btn.isEnabled())
        self.assertFalse(page.check_btn.isVisible())
        self.assertFalse(page.skip_btn.isVisible())
        self.assertEqual((page.time_note.text(), page.time_left.text()), ("목표 1분 중 0분 지났습니다", "1:00 남음"))
        self.assertTrue(page.result_view.text().startswith("자동 검사 없음\n0단계는"))  # 검사가 없는 단계에 '아직 검사하지 않았다'를 붙이지 않음
        guikit.click(page.brief_btn)  # 읽기 안내를 보는 동안 목표 시간이 지나도 끌어오지 않음
        self.assertEqual(page.brief_btn.text(), "요구로 돌아가기")
        self.tick(minutes=1)
        page.tick()
        self.assertIs(page.left.currentWidget(), page.brief_view)
        guikit.click(page.brief_btn)
        self.assertIs(page.left.currentWidget(), page.request_page)
        self.assertTrue(page.request_items.isVisible())
        self.assertEqual(len(page.request_items.rows), 2)
        self.assertEqual(page.request_items.rows[0].label.text(), "횟수가 App의 state 에 있다고 말했습니다.")  # `코드` 표시를 뺀 글
        self.assertTrue(page.explain_btn.isEnabled())
        self.assertEqual(page.time_left.text(), "0:00 남음")
        page.request_items.rows[0].box.setChecked(True)
        guikit.click(page.explain_btn)
        self.assertEqual(self.log()[-1]["said"], [1, 0])
        # 1단계: 요구, 검사 내용, 힌트, 건너뛰기
        self.assertEqual(page.view["current"]["no"], 1)
        self.assertEqual((page.step_caption.text(), page.step_title.text()), ("1단계", "더하기 버튼"))
        text = doc_text(page.request_view)
        self.assertIn("검사는 아래 내용을 확인합니다.", text)
        self.assertEqual([state for _, _, state in page.stepper.steps], ["done", "now", "lock"])
        self.assertIn("[검사하기]를 누르면", page.result_view.text())
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(page)], ["검사하기"])
        self.assertTrue(page.check_btn.isEnabled())
        self.assertFalse(page.skip_btn.isEnabled())
        self.assertEqual(page.skip_note.text(), "2분 뒤 열립니다")
        self.assertEqual((page.hint_btn.text(), page.hint_btn.toolTip()[:10]), ("힌트 듣기", "들은 힌트 0/1."))
        guikit.click(page.hint_btn)
        self.assertIn("면접관 힌트 1", doc_text(page.request_view))
        self.assertIn("접근성 이름", doc_text(page.request_view))
        self.assertFalse(page.hint_btn.isVisible())  # 힌트를 다 들으면 단추를 숨김
        self.assertEqual(self.kinds()[-1], "hint")
        page.check_btn.click()  # 누르면 바로 꺼지고 글자가 바뀜
        self.assertEqual((page.check_btn.text(), page.check_btn.isEnabled()), ("검사 중", False))
        self.idle()
        self.assertEqual((page.check_btn.text(), page.check_btn.isEnabled()), ("검사하기", True))
        text = page.result_view.text()
        self.assertIn("검사 2개 중 0개 통과", text)
        self.assertIn("실패", text)
        self.assertNotIn("Unable to find role button", text)  # 영어 오류 원문은 접힌 원문 안에만
        self.assertNotIn("<body />", text)
        page.on_result_link("more:1a")
        self.assertIn("Unable to find role button", page.result_view.text())
        self.assertIn("<body />", page.result_view.text())
        self.assertIn("원문 접기", [b.text() for b in page.result_view.findChildren(QPushButton)])
        page.on_result_link("fold:1a")
        self.assertNotIn("<body />", page.result_view.text())
        self.assertEqual(page.status.text(), "")  # 통과 수는 결과 칸 머리에만 보임
        self.tick(minutes=2)
        page.tick()
        self.assertTrue(page.skip_btn.isEnabled())
        self.assertEqual(page.skip_note.text(), "")
        self.solve(1)
        guikit.click(page.check_btn)
        self.idle()
        self.assertEqual((page.view["current"]["no"], page.status.text()), (2, ""))
        self.assertEqual([state for _, _, state in page.stepper.steps], ["done", "done", "now"])
        # 2단계 통과 뒤 질문에 답하면 끝남
        self.solve(2)
        guikit.click(page.check_btn)
        self.idle()
        self.assertIsNotNone(page.after)
        guikit.click(page.home_btn)  # 답하는 중에 나가려 하면 기록되지 않는다고 물음
        self.assertIn("통과 뒤 질문", win.dialog.text.text())
        self.assertEqual(win.dialog.buttons["leave"].objectName(), "danger")
        self.choose("")
        self.assertIs(self.page(), page)
        self.assertIsNotNone(page.after)
        self.assertEqual(page.step_title.text(), "통과 뒤 질문")
        self.assertIn("초 안에 소리 내어 답한 뒤", doc_text(page.request_view))
        self.assertEqual([row.tag.text() for row in page.request_items.rows], ["필수", "보충"])
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(page)], ["답을 마쳤습니다"])
        self.assertFalse(page.check_btn.isVisible())
        self.assertEqual((page.clock_caption.text(), page.timer_label.text()), ("답 시간", "0:30"))
        self.assertEqual(page.view["phase"], "done")  # 마지막 단계를 통과해 끝났어도 답 시계가 보이고 끝남 꼬리표는 숨음
        self.assertEqual((page.clock_box.isVisible(), page.done_badge.isVisible()), (True, False))
        self.tick(seconds=35)
        page.tick()
        self.assertEqual(page.timer_label.text(), "+0:05")
        page.request_items.rows[0].box.setChecked(True)
        guikit.click(page.after_btn)
        entry = self.log()[-1]
        self.assertEqual((entry["kind"], entry["need"], entry["extra"], entry["secs"]), ("after", [1], [0], 35))
        self.assertEqual(page.status.text(), "통과 뒤 질문 판정: 통과 (답 시간 35초)")
        self.assertEqual(page.view["phase"], "done")
        self.assertTrue(page.done_badge.isVisible())
        self.assertIs(page.left.currentWidget(), page.done_page)
        self.assertIs(page.right.currentWidget(), page.summary_page)
        text = doc_text(page.done_view)
        self.assertIn("단계별 결과", text)
        self.assertIn("1단계 더하기 버튼: 통과 · 힌트 1번", text)
        self.assertIn("모범 답안", text)
        self.assertEqual(page.passed_count.text(), "2/2")
        self.assertIn("힌트를 1번 들었습니다.", page.summary.text())
        self.assertEqual(page.mine_diff.toPlainText(), "모범 답안과 같습니다.")
        self.assertTrue(page.template_diff.toPlainText().startswith("모범 답안과 다른 파일 1개: src/App.tsx"))
        self.assertIn("+        초기화", page.template_diff.toPlainText())
        self.assertEqual([b.text() for b in page.tabs.buttons], ["해설", "내 코드와 비교", "스스로 점검"])
        self.assertTrue(page.tabs.buttons[2].isVisible())  # 스스로 점검은 해설을 가리지 않게 탭에 있음
        common, mine = page.done_groups["c"][1], page.done_groups["m"][1]
        self.assertEqual((len(common.rows), len(mine.rows)), (3, 2))  # 모든 미션 공통과 이 미션 항목을 나눠 보임
        page.tabs.buttons[2].click()
        guikit.pump()
        self.assertIs(page.tab_pages.currentWidget(), page.check_page)
        for number in (0, 2):  # 표시하면 바로 저장함
            common.rows[number].box.setChecked(True)
        self.assertEqual(self.log()[-1]["ticks"], {"c1": 1, "c2": 0, "c3": 1, "m1": 0, "m2": 0})
        self.assertEqual(page.saved_note.text(), "저장했습니다")
        self.assertEqual([(row.title.text(), row.second.text()) for row in page.next_rows.rows],
                         [("이 미션의 꼬리 질문", "질문 2개 · 약 3분"), ("시험 페이지: state 가 바뀌면 무엇이 다시 그려지나요", "학습 노트")])
        page.next_rows.rows[0].clicked.emit()
        guikit.pump()
        self.assertEqual((self.page(), win.web_drill.cid, win.web_drill.back), (win.web_drill, "x01-F", ("mission", "x01")))
        guikit.click(win.web_drill.back_btn)
        self.assertEqual((self.page(), page.view["phase"]), (page, "done"))
        guikit.click(page.brief_btn)
        self.assertIs(page.left.currentWidget(), page.brief_view)
        self.assertEqual(page.brief_btn.text(), "해설로 돌아가기")
        guikit.click(page.brief_btn)
        self.assertIs(page.left.currentWidget(), page.done_page)
        self.assertEqual([b.text() for b in kit.visible_primary_buttons(page)], ["다음 할 일 보기"])
        guikit.click(page.next_btn)
        self.assertIs(self.page(), win.web_home)

    def test_timers_come_from_record_timestamps_and_survive_a_restart(self):
        self.to_live(explained=False)
        self.tick(minutes=7)
        for shown, ticked in (("1:00", "1:10"), ("1:10", "1:20")):  # 창을 새로 띄워도 기록 시각에서 이어 셈. 6분 실전을 넘긴 시간
            win = self.boot()
            page = self.open_mission()
            self.assertEqual((page.clock_caption.text(), page.timer_label.text()), ("시간 지남", "+" + shown))
            self.assertEqual(page.time_left.text(), "+%s 지남" % ("6:00" if shown == "1:00" else "6:10"))
            self.assertTrue(page.request_items.isVisible())  # 목표 시간이 이미 지나 점검 항목이 열려 있음
            self.assertTrue(page.explain_btn.isEnabled())
            self.tick(seconds=10)
            page.tick()
            self.assertEqual(page.timer_label.text(), "+" + ticked)
            win.close()
            win.deleteLater()
            guikit.pump()
            self.win = None

    def test_skip_finish_and_again(self):
        self.to_live()
        win = self.boot()
        page = self.open_mission()
        self.assertFalse(page.skip_btn.isEnabled())
        self.tick(minutes=2)
        page.tick()
        self.assertTrue(page.skip_btn.isEnabled())
        guikit.click(page.skip_btn)
        self.assertEqual(win.dialog.buttons["skip"].objectName(), "danger")
        self.choose("skip")
        self.assertEqual((self.kinds()[-1], page.view["current"]["no"]), ("skip", 2))
        self.assertEqual([state for _, _, state in page.stepper.steps], ["done", "skip", "now"])
        guikit.click(page.finish_btn)
        self.assertEqual(win.dialog.buttons["finish"].objectName(), "danger")
        self.choose("finish")
        self.assertEqual((page.view["phase"], self.kinds()[-1]), ("done", "finish"))
        self.assertIn("2단계 초기화 버튼: 하지 않음", doc_text(page.done_view))
        self.assertNotIn("잠김", doc_text(page.done_view))
        self.assertEqual(page.passed_count.text(), "0/2")
        self.assertTrue(page.summary.text().startswith("1단계는 넘어갔습니다. 실전에 2분 걸렸습니다."))
        self.assertTrue(page.mine_diff.toPlainText().startswith("모범 답안과 다른 파일 1개: src/App.tsx"))
        self.assertFalse(page.finish_btn.isVisible())
        self.assertTrue(page.again_btn.isVisible())
        guikit.click(page.again_btn)
        self.assertEqual(win.dialog.buttons["again"].objectName(), "danger")
        self.choose("again")
        self.assertEqual((page.view["phase"], page.view["try"]), ("reading", 2))
        self.assertEqual(self.kinds()[-1], "receive")

    def test_receiving_without_the_stack_offers_the_install_dialog(self):
        os.remove(os.path.join(self.repo, stack.VITEST_MJS))
        win = self.boot()
        page = self.open_mission()
        self.assertTrue(page.stack_banner.isVisible())
        self.assertIn("[설치 관리]에서 설치해 주세요", page.stack_banner.text.text())  # 터미널 명령 대신 단추 이름
        self.assertNotIn("study.py", page.stack_banner.text.text())
        guikit.click(page.get_btn)
        self.assertEqual(set(win.dialog.buttons), {"install", "get", ""})
        self.assertNotIn("study.py", win.dialog.text.text())
        self.choose("install")
        dialog = page.setup_dialog
        self.assertTrue(dialog.isVisible())
        self.assertTrue(dialog.install_btn.text().startswith("설치"))
        dialog.close()
        guikit.pump()
        self.assertEqual(page.view["phase"], "none")  # 설치하지 않고 닫으면 받지 않음
        guikit.click(page.get_btn)
        self.choose("get")
        self.assertEqual(page.view["phase"], "reading")

    def test_receiving_again_asks_to_continue_or_start_over(self):
        """받은 코드가 있는데 받기 전으로 보이면(기록이 사라짐) [미션 받기]가 이어서 할지 처음부터 다시 받을지 묻고,
        화면 어디에도 터미널 명령이 없음. 받기 전으로 보이는 사이에 다른 곳에서 받아 서비스가 거절해도 같은 창이 뜸."""
        self.web().get("x01")
        app = os.path.join(study.SUBMISSIONS_DIR, USER, "web", "missions", "x01", "src", "App.tsx")
        study.write_text(app, "내 코드")
        os.remove(self.record_path())
        win = self.boot()
        page = self.open_mission()
        self.assertEqual(page.view["phase"], "none")
        calls, real_get = [], win.web.get
        with mock.patch.object(win.web, "get", lambda mid, again=False: calls.append(again) or real_get(mid, again)):
            guikit.click(page.get_btn)
            dialog = win.dialog
            self.assertEqual({key: b.text() for key, b in dialog.buttons.items()}, {"resume": "이어서 하기", "again": "처음부터 다시 받기", "": "닫기"})
            self.assertEqual((dialog.buttons["resume"].objectName(), dialog.buttons["again"].objectName()), ("primary", "danger_text"))
            self.assertFalse(dialog.buttons["again"].isDefault())
            guikit.pump()
            self.assertLess(dialog.buttons["again"].geometry().right(), dialog.buttons[""].x())  # 되돌릴 수 없는 단추는 왼쪽 끝이고 [닫기]가 사이에 옴
            self.assertLess(dialog.buttons[""].geometry().right(), dialog.buttons["resume"].x())
            for hidden in ("--", "study.py"):
                self.assertNotIn(hidden, dialog.text.text())
            self.choose("")
            self.assertEqual((page.view["phase"], self.kinds(), calls), ("none", [], []))
            guikit.click(page.get_btn)
            self.choose("resume")
        self.assertEqual((page.view["phase"], page.view["try"], self.kinds()), ("reading", 1, ["receive"]))
        self.assertEqual((study.read_text(app), page.status.text(), calls), ("내 코드", RESUMED_TEXT, []))  # 폴더는 그대로
        self.assertTrue(page.folder_btn.isEnabled())
        os.remove(self.record_path())
        win.open_session(lambda: win.open_mission("x01"))
        self.idle()
        self.assertEqual((self.page(), page.view["phase"]), (page, "none"))
        with mock.patch.object(win.web, "received", return_value=False), \
                mock.patch.object(win.web, "get", side_effect=service.AlreadyReceived("none")):  # 서비스가 거절하는 경우
            guikit.click(page.get_btn)
        self.assertEqual(set(win.dialog.buttons), {"resume", "again", ""})
        self.assertEqual(page.view["phase"], "none")
        self.choose("again")
        self.assertEqual((page.view["phase"], page.view["try"], self.kinds()), ("reading", 1, ["receive"]))
        self.assertNotEqual(study.read_text(app), "내 코드")  # 템플릿으로 덮어씀

    def test_locked_mission_and_unknown_mission_show_a_message(self):
        win = self.boot()
        win.open_mission("x02")
        guikit.pump()
        self.assertIn("아직 출제되지 않은", win.dialog.text.text())
        self.assertIs(self.page(), win.hub)


class ServeTest(WebTest):
    """[화면 띄우기]와 [테스트 돌리기]. 화면 서버와 vitest 는 test_web_dev 의 가짜를 쓰고, 브라우저 열기는 주소만 모음."""

    def setUp(self):
        super().setUp()
        study.write_text(os.path.join(self.repo, dev.VITE_JS), "")
        reset_fakes()
        for name, value in (("_popen", fake_popen), ("_kill_tree", lambda proc: proc.kill()), ("_hold", lambda proc: None)):
            patcher = mock.patch.object(dev, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(dev.stop_all)
        self.urls = []

    def boot(self, size=(1280, 800)):
        win = super().boot(size)
        win.open_url = self.urls.append
        return win

    def serve(self, page):
        guikit.click(page.serve_btn)
        self.idle()
        return FakeServer.procs[-1]

    def test_serve_opens_the_browser_and_stops_when_pressed_left_or_closed(self):
        win = self.boot()
        page = self.open_mission()
        self.assertFalse(page.serve_btn.isEnabled())  # 받기 전
        self.assertFalse(page.test_btn.isEnabled())
        guikit.click(page.get_btn)
        self.assertTrue(page.serve_btn.isEnabled())
        self.assertTrue(page.test_btn.isEnabled())
        proc = self.serve(page)
        self.assertEqual(self.urls, ["http://localhost:5173"])
        self.assertEqual(page.status.text(), "화면을 띄웠습니다: http://localhost:5173")
        self.assertEqual(page.serve_btn.text(), "화면 끄기")
        self.assertIn("http://localhost:5173", page.serve_btn.toolTip())  # 상태 줄이 바뀌어도 주소를 볼 수 있음
        self.assertEqual(proc.options["cwd"], page.view["dir"])
        guikit.click(page.serve_btn)
        self.assertEqual((page.serve_btn.text(), page.status.text()), ("화면 띄우기", "화면을 껐습니다."))
        self.assertEqual(page.serve_btn.toolTip(), SERVE_TIP)
        self.assertIsNone(win.web.serving())
        dev.settle()  # 끊기는 화면 스레드가 기다리지 않음
        self.assertTrue(proc.killed)
        proc = self.serve(page)
        win.go_web()
        self.idle()
        dev.settle()
        self.assertTrue(proc.killed)  # 미션 화면을 떠나면 끔. 창을 내려 둘 때(event.spontaneous())는 offscreen 에서 흉내 낼 수 없음
        page = self.open_mission()
        self.assertEqual(page.serve_btn.text(), "화면 띄우기")
        proc = self.serve(page)
        win.close()
        guikit.pump()
        self.assertTrue(proc.killed)  # 프로그램을 닫으면 끔
        self.assertEqual(dev._running, set())

    def test_a_server_that_stops_by_itself_resets_the_button(self):
        self.web().get("x01")
        self.boot()
        page = self.open_mission()
        proc = self.serve(page)
        proc.end(1)
        page.tick()
        self.assertEqual((page.serve_btn.text(), page.status.text()), ("화면 띄우기", SERVE_STOPPED))
        self.assertIsNone(self.win.web.serving())  # 멈춘 서버는 치움
        self.assertIn("서버가 마지막으로 남긴 출력입니다.", self.win.dialog.text.text())
        self.assertIn("Local:   http://localhost:5173/", self.win.dialog.text.text())
        self.choose("ok")
        page.tick()
        self.assertFalse(self.win.dialog.isVisible())  # 한 번만 알림

    def test_again_and_a_new_session_stop_the_server(self):
        web = self.to_live()
        web.finish("x01")
        win = self.boot()
        page = self.open_mission()
        proc = self.serve(page)
        killed_before_get, get = [], win.web.get

        def slow_kill(target):  # Windows 의 taskkill 처럼 오래 걸리는 끊기
            time.sleep(0.3)
            target.kill()

        def recording_get(mid, again=False):
            killed_before_get.append(proc.killed)
            return get(mid, again)

        with mock.patch.object(dev, "_kill_tree", slow_kill), mock.patch.object(win.web, "get", recording_get):
            guikit.click(page.again_btn)
            self.choose("again")
        self.assertEqual(killed_before_get, [True])  # 다시 하기는 서버가 지켜보는 폴더를 새로 쓰기 전에 끝날 때까지 기다림
        self.assertEqual(page.serve_btn.text(), "화면 띄우기")
        proc = self.serve(page)
        win.open_session(win.go_web)
        self.idle()
        self.assertTrue(proc.killed)
        self.assertEqual(dev._running, set())

    def test_turning_off_or_leaving_does_not_wait_for_the_kill(self):
        self.web().get("x01")
        win = self.boot()
        page = self.open_mission()
        gate = threading.Event()

        def gated_kill(target):  # 화면 스레드가 기다리면 gate 가 열릴 때까지 멈춤
            gate.wait(5)
            target.kill()

        for leave in (lambda: guikit.click(page.serve_btn), win.go_web):
            proc = self.serve(page) if win.pages.currentWidget() is page else self.serve(self.open_mission())
            gate.clear()
            with mock.patch.object(dev, "_kill_tree", gated_kill):
                started = time.monotonic()
                leave()
                self.assertLess(time.monotonic() - started, 2)
                self.assertFalse(proc.killed)
                gate.set()
                dev.settle()
            self.assertTrue(proc.killed)

    def test_closing_the_window_stops_a_test_run_that_hangs(self):
        self.web().get("x01")
        win = self.boot()
        page = self.open_mission()
        HangingRun.procs = []
        with mock.patch.object(dev, "_popen", HangingRun):
            page.test_btn.click()
            guikit.wait_until(lambda: HangingRun.procs)
            started = time.monotonic()
            win.close()  # 끝나지 않는 테스트를 한도(60초)까지 기다리지 않고 끊고 닫음
            guikit.wait_until(lambda: not win.isVisible(), timeout=10)
        self.assertLess(time.monotonic() - started, 5)
        self.assertTrue(HangingRun.procs[-1].killed.is_set())
        self.assertEqual(dev._tests, {})
        self.assertIsNone(win.dialog)  # 멈췄다는 대화상자 없이 닫음

    def test_closing_while_the_server_starts_does_not_open_the_browser(self):
        self.web().get("x01")
        win = self.boot()
        page = self.open_mission()
        page.serve_btn.click()  # 워커가 끝났다는 알림을 받기 전에 창을 닫음
        win.close()
        self.assertTrue(win.close_pending)
        self.idle()
        guikit.pump()
        self.assertEqual(self.urls, [])
        self.assertTrue(FakeServer.procs[-1].killed)
        self.assertEqual(dev._running, set())

    def test_a_server_that_fails_to_start_shows_why(self):
        self.web().get("x01")
        self.boot()
        page = self.open_mission()
        FakeServer.lines, FakeServer.code = (b"error when starting dev server:\n", b"Error: Cannot find module 'vite'\n"), 1
        guikit.click(page.serve_btn)
        self.idle()
        self.assertIn("종료 코드 1", self.win.dialog.text.text())
        self.assertIn("Cannot find module 'vite'", self.win.dialog.text.text())
        self.assertEqual((page.serve_btn.text(), self.urls), ("화면 띄우기", []))

    def test_without_the_stack_the_buttons_stay_off(self):
        os.remove(os.path.join(self.repo, stack.VITEST_MJS))
        self.web().get("x01")
        self.boot()
        page = self.open_mission()
        self.assertTrue(page.folder_btn.isEnabled())
        self.assertFalse(page.serve_btn.isEnabled())
        self.assertFalse(page.test_btn.isEnabled())

    def test_run_tests_shows_the_summary_and_the_first_failure(self):
        web = self.to_live()
        self.boot()
        page = self.open_mission()
        FakeTestRun.report = vitest_report(web.learner_dir("x01"), fail=True)
        guikit.click(page.test_btn)
        self.idle()
        self.assertTrue(page.status.text().startswith("내 테스트 2개 가운데 1개 통과"))
        text = self.win.dialog.text.text()
        self.assertIn("src/App.test.tsx > App > 더하기를 누르면 1", text)
        self.assertIn("AssertionError: expected '0' to be '1'", text)
        self.assertEqual(self.win.dialog.detail.toPlainText(), "")  # 실패가 하나면 [자세히]가 없음
        self.assertEqual(FakeTestRun.calls[-1][1]["cwd"], page.view["dir"])
        self.choose("ok")
        FakeTestRun.report = vitest_report(web.learner_dir("x01"))
        guikit.click(page.test_btn)
        self.idle()
        self.assertTrue(page.status.text().startswith("내 테스트 1개 가운데 1개 통과"))
        self.assertFalse(self.win.dialog.isVisible())
        self.assertEqual(self.kinds()[-1], "step")  # 내 테스트는 기록하지 않음


class WordingTest(unittest.TestCase):
    """화면 문구에 터미널 명령이 없음. 서비스와 검사 도구의 안내는 터미널에서도 쓰여 명령이 들어 있는데, gui_text 를 거치면 사라져야 함."""

    FLAG = re.compile(r"(^|\s)--[a-z]")

    def test_no_terminal_commands_reach_the_screen(self):
        for name in sorted(os.listdir(os.path.join(guikit.ROOT, "gui"))):
            if name.endswith(".py") and name != "web_text.py":  # 바꿀 명령의 표는 web_text 에 있음
                text = study.read_text(os.path.join(guikit.ROOT, "gui", name))
                self.assertNotIn("--again", text, name)
                self.assertNotIn("study.py web", text, name)
        found = 0
        for name in ("service", "stack", "checks", "dev", "record", "bank", "review"):
            tree = ast.parse(study.read_text(os.path.join(guikit.ROOT, "webprep", name + ".py")))
            docs = {ast.get_docstring(node, clean=False) for node in ast.walk(tree) if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))}
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or node.value in docs:
                    continue
                if re.search("[가-힣]", node.value) and ("study.py" in node.value or self.FLAG.search(node.value)):
                    found += 1
                    shown = web_text.gui_text(node.value)
                    self.assertFalse("study.py" in shown or self.FLAG.search(shown), "%s: %s" % (name, node.value))
        self.assertGreater(found, 0)  # 검사 도구 설치 안내처럼 명령이 든 문구가 있음


class NextItemTest(unittest.TestCase):
    def test_review_card_names_the_round_like_the_web_home_row(self):
        """이어서 할 일 카드의 복습 차수는 주제 목록의 times 에서 가져옴. 미션 뒤 사슬처럼 주제에 없으면 차수를 쓰지 않음."""
        topics = [{"title": "React 상태", "chains": [{"id": "90-A", "times": 1}]}]
        for iid, line in (("90-A", "꼬리 질문 복습 · 두 번째 복습"), ("w03-F", "꼬리 질문 복습")):
            overview = {"next": {"kind": "chain", "id": iid, "title": "제목"}, "topics": topics,
                        "today": {"chains": [{"chain": iid, "box": 1, "due": "2026-10-22", "new": False}]}}
            self.assertEqual(web_text.next_item(overview)["line"], line)

    def test_minutes_text_reads_as_a_duration(self):
        self.assertEqual([web_text.minutes_text(s) for s in (40, 120, 90, 0)], ["40초", "2분", "1분 30초", "0초"])
        self.assertEqual((web_text.day_text("2026-10-24"), web_text.day_text("어제")), ("10/24(토)", "어제"))  # 사슬 줄의 다음 복습 날짜


@unittest.skipIf(sys.platform == "win32", "SIGHUP 은 POSIX 에만 있음")
class HangupGuiTest(unittest.TestCase):
    def test_closing_the_terminal_stops_the_server_of_a_window_started_from_it(self):
        """start.command 처럼 터미널에서 띄운 창. 창이 이벤트 루프에서 기다리는 동안 SIGHUP 을 받아도 서버를 끊고 끝남."""
        child, pid, tmp = start_child(self, "gui", {"QT_QPA_PLATFORM": "offscreen"})
        wait_file(self, child, tmp, os.path.join("mission", "looping"))  # 이벤트 루프에 들어간 뒤에 보냄
        child.send_signal(signal.SIGHUP)
        self.assertEqual(child.wait(10), -signal.SIGHUP)
        self.assertTrue(group_gone(pid))


class DrillTest(WebTest):
    def test_ctrl_enter_presses_the_primary_button_from_either_enter_key(self):
        """작업 화면의 주 단추는 Ctrl+Enter 로 눌림. 숫자 키패드의 Enter 도 같음."""
        win = self.boot()
        page = self.open_drill("90-A")
        win.activateWindow()
        page.note.setFocus()
        QTest.keyClick(page.note, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(page.confirm_btn.isVisible())  # [답 확인]이 눌림
        page.items.rows[0].box.setChecked(True)
        QTest.keyClick(page, Qt.Key.Key_Enter, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.KeypadModifier)
        self.assertEqual(page.timer_label.text(), "질문 2/3")  # [다음 질문]이 눌림

    def test_marks_verdicts_and_the_chain_end(self):
        win = self.boot()
        page = self.open_drill("90-A")
        self.assertEqual((page.title.text(), page.timer_label.text()), ("버튼을 눌렀는데 화면이 그대로일 때", "질문 1/3"))
        self.assertEqual(page.back_btn.text(), "← 웹 면접 준비")
        self.assertEqual(page.ask.text(), "버튼을 눌러도 화면의 숫자가 바뀌지 않습니다. 왜 그럴까요?")  # "면접관:" 없이 질문만
        self.assertEqual((page.limit_label.text(), page.left_label.text()), ("답 시간 1분", "1:00 남음"))
        self.assertEqual([view.toPlainText().strip().splitlines()[0] for view in page.code_views], ["let count = 0;"])
        self.assertFalse(page.intro.isVisible())  # 사슬 소개는 [배경 보기]로 펼침
        guikit.click(page.bg_btn)
        self.assertTrue(page.intro.isVisible())
        self.assertTrue(page.intro.text().startswith("일반 변수와 state 의 차이를"))
        self.assertEqual(page.bg_btn.text(), "배경 접기")
        self.assertFalse(page.answer_box.isVisible())
        self.assertEqual(len(kit.visible_primary_buttons(page)), 1)
        self.mono += 50
        page.tick()
        self.assertEqual((page.left_label.text(), page.left_label.property("tone")), ("0:10 남음", "warning"))
        self.mono += 20
        page.tick()
        self.assertEqual((page.left_label.text(), page.left_label.property("tone"), page.time_bar.value()), ("+0:10 시간 지남", "danger", 100))
        page.note.setPlainText("일반 변수는 React 가 모름")
        guikit.click(page.confirm_btn)
        self.assertEqual(page.mine_head.text(), "내 답 · 1:10 · 0:10 넘김")
        self.assertEqual(page.mine_note.text(), "일반 변수는 React 가 모름")
        self.assertFalse(page.confirm_btn.isVisible())  # 한 번 쓴 [답 확인] [모르겠습니다]는 숨김
        self.assertFalse(page.give_up_btn.isVisible())
        self.assertFalse(page.time_box.isVisible())
        self.assertTrue(inside(win, page.next_btn))
        self.assertEqual([row.tag.text() for row in page.items.rows], ["필수", "보충"])
        self.assertTrue(page.items.rows[0].label.text().startswith("count는 바뀌지만"))
        self.assertTrue(page.stuck_box.isVisible())
        self.assertTrue(page.talked.isVisible())
        page.items.rows[0].box.setChecked(True)
        self.assertFalse(page.stuck_box.isVisible())
        page.items.rows[1].box.setChecked(True)
        guikit.click(page.next_btn)
        entry = self.log()[-1]
        self.assertEqual({k: entry[k] for k in ("kind", "chain", "q", "secs", "need", "extra", "talked", "note")},
                         {"kind": "drill", "chain": "90-A", "q": 1, "secs": 70, "need": [1], "extra": [1], "talked": None,
                          "note": "일반 변수는 React 가 모름"})
        self.assertEqual((page.timer_label.text(), page.note.toPlainText()), ("질문 2/3", ""))
        self.assertTrue(page.confirm_btn.isVisible())
        guikit.click(page.give_up_btn)
        self.assertFalse(page.items.rows[0].box.isEnabled())
        self.assertIn("다시 그려 달라", page.stuck.text.text())
        self.assertTrue(page.talked.isVisible())
        page.talked.rows[0].box.setChecked(True)
        guikit.click(page.next_btn)
        entry = self.log()[-1]
        self.assertEqual((entry["q"], entry["need"], entry["talked"]), (2, [0], 1))
        guikit.click(page.confirm_btn)
        page.items.rows[0].box.setChecked(True)
        self.assertEqual(page.next_btn.text(), "사슬 끝내기")
        guikit.click(page.next_btn)
        self.assertIs(page.stack.currentWidget(), page.end_page)
        self.assertTrue(page.end_badge.isVisible())
        self.assertEqual((page.score.text(), page.due_text.text()), ("2/3", "다음 복습은 10월 22일(목)입니다."))
        self.assertEqual(page.talked_text.text(), "막힌 질문 1개에서 아는 데까지 말했습니다.")
        self.assertEqual([row.findChild(QLabel).text() for row in page.result_rows], ["통과", "막힘", "통과"])
        self.assertEqual(page.weak_quote.text(), '"리렌더링이 안 돼서 그렇습니다."')
        self.assertTrue(page.follow_block.isVisible())
        self.assertEqual(self.kinds()[-1], "chain")
        self.assertEqual(len(kit.visible_primary_buttons(page)), 1)
        self.assertEqual(page.learn_row.title.text(), "시험 페이지: state 가 바뀌면 무엇이 다시 그려지나요")  # 노트 id 없이 제목만
        guikit.click(page.learn_row)
        learn = win.web_learn
        self.assertEqual((self.page(), learn.pid, learn.section, learn.back_btn.text()), (learn, "l90", "90a", "← 꼬리 질문"))
        self.assertTrue(scroll_to_heading(learn.view, "일반 변수는 화면을 바꾸지 못합니다"))
        guikit.click(learn.back_btn)
        self.assertEqual((self.page(), page.stack.currentWidget()), (page, page.end_page))  # 끝난 자리로 돌아옴
        guikit.click(page.done_btn)
        self.assertIs(self.page(), win.web_home)

    def test_review_shows_the_previous_answer_and_marks(self):
        web = self.web()
        web.answer("90-A", 1, 40, [1], [0], None, "플래그 변수를 말함")
        web.answer("90-A", 2, 40, [0], [], True)
        web.answer("90-A", 3, 40, [1], [1])
        web.finish_chain("90-A")
        self.clock = "2026-10-22T09:00:00"
        self.boot()
        page = self.open_drill("90-A")
        self.assertEqual(page.timer_label.text(), "두 번째 복습 · 질문 1/3")
        guikit.click(page.confirm_btn)
        self.assertEqual((page.mine_head.text(), page.mine_note.text()), ("내 답 · 0초", "적은 내용 없음"))
        self.assertEqual(page.last.text(), "지난 답 · 10월 21일(수) · 40초: 플래그 변수를 말함")
        self.assertEqual([row.note.text() for row in page.items.rows], ["지난번 표시함", "지난번 빠뜨림"])
        page.items.rows[0].box.setChecked(True)
        guikit.click(page.next_btn)
        guikit.click(page.confirm_btn)
        self.assertEqual(page.last.text(), "지난 답 · 10월 21일(수) · 40초: 적은 내용 없음")
        self.assertEqual([row.note.text() for row in page.items.rows], ["지난번 빠뜨림"])

    def test_mission_followups_stay_locked_until_the_mission_ends(self):
        win = self.boot()
        win.open_drill("x01-F")
        guikit.pump()
        self.assertIn("미션을 끝낸 뒤에", win.dialog.text.text())
        self.assertIs(self.page(), win.hub)


class TextSizeTest(WebTest):
    """글자 크기 단계. 새로 설치하면 크게이고, 단계를 바꾸면 이름표·문단·단추·문서의 글자가 같이 커지며, 첫 화면의 단추와 Ctrl 키로 바꾸고
    창을 다시 열어도 남음. 옛 확대 단계(zoom)는 단계로 옮김."""

    def test_default_is_large_and_the_step_scales_labels_buttons_and_documents(self):
        win = self.boot()
        hub = win.hub
        self.assertEqual((theme.state["text"], win.zoom, self.settings.value("text")), ("large", 2, None))
        self.assertEqual([step for step, button in hub.text_buttons.items() if button.isChecked()], ["large"])
        self.assertEqual([button.text() for button in hub.text_buttons.values()], ["보통 글자", "큰 글자", "더 큰 글자"])
        self.assertTrue(all(inside(win, button) for button in hub.text_buttons.values()))
        self.assertEqual((hub.summary.font().pixelSize(), hub.summary.line, hub.next_btn.font().pixelSize()), (19, 32, 19))
        win.open_learn("l90")
        self.idle()
        learn = win.web_learn
        sizes = doc_sizes(learn.view)
        head = max(sizes, key=sizes.get)  # 문서의 절 제목(headline)
        self.assertEqual((head, sizes[head]), ("state 가 바뀌면 무엇이 다시 그려지나요", 24))  # headline +2
        row = win.web_home.page_list.rows[0] if win.web_home.page_list.rows else None
        hub.text_buttons["larger"].click()
        guikit.pump()
        self.assertEqual((theme.state["text"], win.zoom, self.settings.value("text")), ("larger", 4, "larger"))
        self.assertEqual([step for step, button in hub.text_buttons.items() if button.isChecked()], ["larger"])
        self.assertEqual((hub.summary.font().pixelSize(), hub.summary.line, hub.next_btn.font().pixelSize()), (21, 36, 21))
        self.assertEqual(hub.theme_btn.font().pixelSize(), 18)  # 작은 글자 단추는 caption
        self.assertEqual((learn.title.font().pixelSize(), doc_sizes(learn.view)[head]), (26, 26))
        self.assertEqual(learn.card.maximumWidth(), kit.doc_width(win.width()) + 48)
        if row is not None:
            self.assertEqual((row.title.font().pixelSize(), row.title.height()), (21, 28))
        win.activateWindow()
        QTest.keyClick(win, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(win, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual((theme.state["text"], hub.summary.font().pixelSize(), hub.summary.line, doc_sizes(learn.view)[head]), ("normal", 17, 28, 22))
        self.assertTrue(hub.text_buttons["normal"].isChecked())
        QTest.keyClick(win, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual((theme.state["text"], hub.summary.font().pixelSize()), ("large", 19))
        win.set_text("larger")
        win.close()
        win.deleteLater()
        guikit.pump()
        self.win = None
        again = self.boot()  # 다시 열어도 고른 단계
        self.assertEqual((theme.state["text"], again.zoom, again.hub.summary.font().pixelSize()), ("larger", 4, 21))
        self.assertEqual([step for step, button in again.hub.text_buttons.items() if button.isChecked()], ["larger"])

    def test_old_zoom_setting_moves_to_a_step(self):
        for zoom, step in ((-2, "normal"), (0, "large"), (2, "large"), (3, "larger")):
            self.settings.remove("text")
            self.settings.setValue("zoom", zoom)
            win = self.boot()
            self.assertEqual((theme.state["text"], self.settings.value("text"), self.settings.contains("zoom")), (step, step, False), zoom)
            win.close()
            win.deleteLater()
            guikit.pump()
            self.win = None


class LearnTest(WebTest):
    def test_figures_sections_and_the_record(self):
        win = self.boot()
        win.open_learn("l90")
        self.idle()
        learn = win.web_learn
        self.assertEqual((learn.title.text(), learn.back_btn.text()), ("시험 페이지: state 가 바뀌면 무엇이 다시 그려지나요", "← 웹 면접 준비"))
        text = doc_text(learn.view)
        self.assertIn("그림 준비 중. 그림 1. 두 호출이 같은 값을 넣어", text)  # 고정 은행에는 그림 파일이 없음
        self.assertNotIn("내용:", text)
        self.assertEqual([p for p in learn.view.pieces if isinstance(p, FigureView)], [])
        self.assertLessEqual(learn.view.width(), 640 + 2)  # 읽는 글 폭
        self.assertEqual(len(kit.visible_primary_buttons(learn)), 0)  # 읽기 화면에는 주 단추가 없음
        self.assertEqual((learn.next_row.isVisible(), learn.next_title.text()), (True, "일반 변수는 화면을 바꾸지 못합니다"))
        guikit.click(learn.next_btn)
        self.assertEqual(learn.next_title.text(), "같은 렌더의 값을 두 번 쓰면")
        guikit.click(learn.next_btn)
        self.assertFalse(learn.next_row.isVisible())  # 마지막 절 뒤에는 다음 절이 없음
        root = os.path.join(self.tmp, "bank_with_png")
        shutil.copytree(FIXTURE, root)
        os.makedirs(os.path.join(root, "learn", "l90", "assets"))
        with open(os.path.join(root, "learn", "l90", "assets", "l90-1.png"), "wb") as handle:
            handle.write(PNG)
        with mock.patch.object(bank, "BANK_DIR", root):
            win.open_session()
            win.open_learn("l90", "90b")
            self.idle()
        figures = [p for p in learn.view.pieces if isinstance(p, FigureView)]
        self.assertEqual(len(figures), 1)
        self.assertEqual(figures[0].caption.text(), "그림 1. 두 호출이 같은 값을 넣어 숫자가 1 만 오릅니다.")
        self.assertEqual(learn.section, "90b")
        self.assertTrue(scroll_to_heading(learn.view, "같은 렌더의 값을 두 번 쓰면"))
        self.assertEqual(self.kinds(), ["learn", "learn"])


LONG_STATUS = ("검사 5개 중 3개 통과 (1.2초).", "실전 45분이 시작되었습니다.", "Cursor 에서 폴더를 열었습니다.",
               "내 테스트 12개 가운데 11개 통과 (3.2초)", SERVE_STOPPED)  # 아래 막대의 상태 글 가운데 긴 것들. 작은 창에서도 끝까지 보여야 함


class LookTest(WebTest):
    """어두운 테마에서 밝은 조각이 남지 않고, 작은 창(1024x700)에서 단추가 창 밖으로 나가지 않음. 화면마다 한 번씩 봄."""

    def screens(self, win):
        """(이름, 그 화면을 띄우는 함수, 살펴볼 단추들). 미션은 네 상태를 모두 거침."""
        mission, drill = win.web_mission, win.web_drill

        def mission_reading():
            guikit.click(mission.get_btn)

        def mission_live():
            guikit.click(mission.start_btn)
            self.tick(minutes=1)
            mission.tick()
            mission.request_items.rows[0].box.setChecked(True)
            guikit.click(mission.explain_btn)
            guikit.click(mission.check_btn)
            self.idle()
            mission.on_result_link("more:1a")

        def mission_done():
            self.tick(minutes=2)
            mission.tick()
            guikit.click(mission.skip_btn)
            self.choose("skip")
            guikit.click(mission.finish_btn)
            self.choose("finish")
            mission.tabs.buttons[2].click()

        def drill_checklist():
            self.open_drill("90-A")
            guikit.click(drill.confirm_btn)

        def drill_end():
            for number in range(3):
                if not drill.checked:
                    guikit.click(drill.confirm_btn)
                drill.items.rows[0].box.setChecked(True)
                guikit.click(drill.next_btn)

        return (("hub", win.go_hub, (win.hub.next_btn, win.hub.web_row)),
                ("home", win.go_web, (win.web_home.next_btn, win.web_home.setup_btn, win.web_home.hub_btn)),
                ("mission_before", lambda: self.open_mission(), (mission.get_btn, mission.folder_btn, mission.serve_btn, mission.test_btn)),
                ("mission_reading", mission_reading, (mission.folder_btn, mission.serve_btn, mission.test_btn, mission.start_btn)),
                ("mission_live", mission_live, (mission.check_btn, mission.finish_btn, mission.hint_btn, mission.skip_btn, mission.serve_btn,
                                                mission.test_btn)),
                ("mission_done", mission_done, (mission.again_btn, mission.next_btn, mission.brief_btn, mission.serve_btn)),
                ("drill_checklist", drill_checklist, (drill.next_btn, drill.give_up_btn)),
                ("drill_end", drill_end, (drill.done_btn, drill.again_btn)),
                ("learn", lambda: win.open_learn("l90"), (win.web_learn.back_btn,)))

    def test_dark_theme_leaves_no_light_patches_on_every_screen(self):
        win = self.boot()
        self.addCleanup(theme.set_mode, theme.state["mode"])
        theme.set_mode("dark")
        guikit.pump()
        for name, show, _ in self.screens(win):
            show()
            self.idle()
            self.assertEqual(bright_share(win), 0, name)
        dialog = SetupDialog(win)
        dialog.show()
        guikit.pump()
        self.assertEqual(bright_share(dialog), 0, "setup")
        dialog.close()

    def test_small_window_keeps_every_button_inside(self):
        self.check_small_window(theme.TEXT_DEFAULT)

    def test_small_window_keeps_every_button_inside_at_the_largest_text(self):
        self.check_small_window("larger")

    def check_small_window(self, step):
        win = self.boot((1024, 700))
        win.set_text(step)
        self.assertEqual((win.width(), win.height()), (1024, 700))
        self.assertLessEqual(win.minimumSizeHint().height(), 480)  # 1366x768 125% 배율(작업 영역 약 576)에도 창 전체가 들어감
        for name, show, buttons in self.screens(win):
            show()
            self.idle()
            page = self.page()
            self.assertLessEqual(page.minimumSizeHint().width(), 1024, name)
            self.assertLessEqual(page.minimumSizeHint().height(), 700, name)
            self.assertEqual((win.width(), win.height()), (1024, 700), name)
            if name == "hub":
                buttons = buttons + tuple(win.hub.text_buttons.values()) + (win.hub.theme_btn,)
            for button in buttons:
                if not button.isVisible():
                    continue
                scroll_to(button)  # 허브·웹 홈과 카드 안의 칸은 작은 창에서 스크롤함
                self.assertTrue(inside(win, button), "%s: %s" % (name, name_of(button)))
            mission = win.web_mission
            if page is mission:  # 상태 줄은 작은 창에서도 끝까지 보임
                for text in LONG_STATUS:
                    mission.status.setText(text)
                    guikit.pump()
                    self.assertTrue(shows_whole(mission.status), "%s: %s" % (name, text))
                mission.set_busy(True, "하던 작업이 끝나면 창을 닫습니다.")
                guikit.pump()
                self.assertTrue(shows_whole(mission.status), name)
                mission.set_busy(False)
        win.go_web()
        guikit.pump()
        self.assertGreater(win.web_home.findChild(QScrollArea).verticalScrollBar().maximum(), 0)


class OpenFolderTest(unittest.TestCase):
    """[폴더 열기]가 고르는 프로그램. 실제로는 아무것도 띄우지 않음."""

    def setUp(self):
        self.calls = []
        patcher = mock.patch("gui.web_mission._popen", lambda cmd, **options: self.calls.append(cmd))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.settings = QSettings(os.path.join(tempfile.mkdtemp(prefix="gui_web_folder_"), "settings.ini"), QSettings.Format.IniFormat)

    def test_mac_prefers_the_remembered_editor_then_cursor_then_finder(self):
        apps = {"/Applications/Cursor.app", "/Applications/Visual Studio Code.app"}
        self.assertEqual(open_folder("/work", self.settings, "darwin", exists=apps.__contains__), "Cursor 에서 폴더를 열었습니다.")
        self.assertEqual(self.calls[-1], ["open", "-a", "/Applications/Cursor.app", "/work"])
        self.assertEqual(self.settings.value("web/editor"), "Cursor")
        self.settings.setValue("web/editor", "Visual Studio Code")
        self.assertEqual(open_folder("/work", self.settings, "darwin", exists=apps.__contains__), "Visual Studio Code 에서 폴더를 열었습니다.")
        self.assertEqual(self.calls[-1], ["open", "-a", "/Applications/Visual Studio Code.app", "/work"])
        self.assertEqual(open_folder("/work", self.settings, "darwin", exists=lambda path: False), "Finder 에서 폴더를 열었습니다.")
        self.assertEqual(self.calls[-1], ["open", "/work"])

    def test_windows_uses_code_on_path_or_the_explorer(self):
        self.assertEqual(open_folder("C:\\work", self.settings, "win32", which=lambda name: "C:\\code.cmd" if name == "code" else None),
                         "VS Code 에서 폴더를 열었습니다.")
        self.assertEqual(self.calls[-1], ["C:\\code.cmd", "C:\\work"])
        opened = []
        with mock.patch("gui.web_mission._startfile", opened.append):
            self.assertEqual(open_folder("C:\\work", self.settings, "win32", which=lambda name: None), "탐색기에서 폴더를 열었습니다.")
        self.assertEqual(opened, ["C:\\work"])

    def test_failure_is_reported_not_raised(self):
        with mock.patch("gui.web_mission._popen", side_effect=OSError("no open")):
            self.assertEqual(open_folder("/work", None, "linux"), "폴더를 열지 못했습니다: no open")


if __name__ == "__main__":
    unittest.main()
