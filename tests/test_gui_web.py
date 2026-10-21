# -*- coding: utf-8 -*-
"""웹 면접 준비 화면(gui/web_home.py, web_mission.py, web_drill.py, web_learn.py, web_setup.py)과 첫 화면의 웹 줄 카드.
실제 MainWindow 를 띄우되 웹 은행은 tests/web_bank, 여행 은행은 tests/journey_bank, 풀이 폴더·웹 홈 폴더·검사 도구 폴더는 임시 폴더,
제출 모듈·Node·vitest·설치·폴더 열기는 가짜를 씀. 시계는 서비스의 now(기록 시각)와 화면의 clock(흐른 초)을 같이 돌림.
PyQt6 가 없으면 전부 건너뜀."""
import base64
import datetime
import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QPoint, QRect, QSettings  # noqa: E402
from PyQt6.QtWidgets import QScrollArea  # noqa: E402

import session  # noqa: E402
import study  # noqa: E402
from gui import errors, theme  # noqa: E402
from gui.docview import FigureView, TextPiece  # noqa: E402
from gui.web_home import NO_STUCK  # noqa: E402
from gui.web_learn import scroll_to_heading  # noqa: E402
from gui.web_mission import open_folder  # noqa: E402
from gui.web_setup import BUSY_ELSEWHERE, SetupDialog  # noqa: E402
from gui.window import MainWindow  # noqa: E402
from journey import bank as journey_bank  # noqa: E402
from journey import node as node_finder  # noqa: E402
from journey import runner  # noqa: E402
from tests.test_gui_hub import FakeGitFlow, bright_share  # noqa: E402
from tests.test_web_service import FAKE_NODE, FakeVitest  # noqa: E402
from webprep import bank, checks, service, stack  # noqa: E402

FIXTURE = os.path.join(guikit.ROOT, "tests", "web_bank")
JOURNEY_FIXTURE = os.path.join(guikit.ROOT, "tests", "journey_bank")
USER = "tester"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAMgAAAAUAQMAAADyauCJAAAAA1BMVEUlN0fhQ83WAAAAD0lEQVR42mNgGAWjgIEBAAIIAAFQMUmAAAAAAElFTkSuQmCC")


def doc_text(view):
    """DocView 의 글 조각을 이어 붙인 글."""
    return "\n".join(piece.toPlainText() for piece in view.pieces if isinstance(piece, TextPiece))


def inside(win, widget):
    """widget 이 창 안에 다 들어와 있는지."""
    return win.rect().contains(QRect(widget.mapTo(win, QPoint(0, 0)), widget.size()))


def rows_height(listw, rows):
    """목록이 rows 줄에 맞춘 높이."""
    return sum(listw.sizeHintForRow(n) for n in range(rows)) + 2 * listw.frameWidth()


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
    def test_row_numbers_follow_the_service_and_web_days_reach_the_chart(self):
        win = self.boot()
        hub = win.hub
        self.assertTrue(win.web_node_known)
        self.assertEqual((hub.web_done.text(), hub.web_due.text()), ("0 / 1", "2"))
        self.assertEqual(hub.web_stack.text(), "Node.js 22.23.2 · 검사 도구 설치됨 (약 80MB)")
        self.assertEqual(hub.web_next.text(), "학습 노트 l90 시험 페이지: state 가 바뀌면 무엇이 다시 그려지나요")
        self.assertTrue(hub.web_btn.isEnabled())
        today = datetime.date.today()
        self.assertEqual(hub.chart.days[-1], (today, 0, 0, 0))
        self.assertEqual(hub.streak.text(), "연속 학습 0일")
        self.clock = datetime.datetime.now().isoformat(timespec="seconds")  # 검사와 드릴을 오늘 기록함
        web = self.to_live()
        web.check("x01")
        web.answer("90-A", 1, 10, [1], [1])
        web.finish_chain("90-A")
        web.show("l90")
        hub.refresh()
        self.assertEqual(hub.chart.days[-1], (today, 0, 0, 1))
        self.assertEqual(hub.streak.text(), "연속 학습 1일")
        self.assertEqual((hub.web_done.text(), hub.web_due.text()), ("0 / 1", "1"))
        self.assertTrue(hub.web_next.text().startswith("미션 x01 "), hub.web_next.text())
        self.node = None
        hub.refresh()
        self.assertEqual(hub.web_stack.text(), "Node.js 없음 · 검사 도구 설치됨 (약 80MB)")
        self.assertIn("웹 면접 준비", hub.series.text())

    def test_broken_web_record_disables_the_row_and_the_other_tracks_still_work(self):
        study.write_text(self.record_path(), '{"log": [<<<<')
        win = self.boot()
        hub = win.hub
        self.assertIsNone(win.web)
        self.assertTrue(hub.web_error.isVisible())
        self.assertIn("record.json", hub.web_error.text())
        self.assertFalse(hub.web_btn.isEnabled())
        self.assertFalse(hub.web_body.isVisible())
        self.assertTrue(hub.journey_btn.isEnabled())
        self.assertEqual(hub.chart.days[-1][3], 0)
        hub.web_btn.click()
        guikit.pump()
        self.assertIs(self.page(), hub)
        guikit.click(hub.python_btn)
        self.assertIs(self.page(), win.home)

    def test_entering_and_leaving_the_web_home(self):
        win = self.boot()
        guikit.click(win.hub.web_btn)
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
            guikit.click(win.hub.web_btn)
            self.idle()
        self.assertEqual((workers, self.page()), ([True, False], win.web_home))  # 워커에서 한 번 찾은 뒤 웹 홈이 현황을 읽음
        guikit.click(win.web_home.hub_btn)
        self.idle()
        self.assertEqual((workers, self.page()), ([True, False, False], win.hub))  # 다시 찾지 않음


class HomeTest(WebTest):
    def test_lists_show_today_missions_topics_and_pages(self):
        win = self.boot()
        guikit.click(win.hub.web_btn)
        home = win.web_home
        self.assertEqual(home.stack_label.text(), "Node.js 22.23.2 · 검사 도구 설치됨 (약 80MB)")
        self.assertFalse(home.problem.isVisible())
        rows = [home.today_list.item(n).text() for n in range(home.today_list.count())]
        self.assertEqual(rows, ["사슬 90-A 버튼을 눌렀는데 화면이 그대로일 때\n새 사슬", "사슬 90-B state 를 두 번 바꿀 때\n새 사슬"])
        self.assertEqual(home.today_minutes.text(), "약 8분")
        self.assertEqual(home.today_list.height(), rows_height(home.today_list, 2))  # 목록은 줄 수만큼의 높이
        rows = [home.mission_list.item(n) for n in range(home.mission_list.count())]
        self.assertEqual([r.text() for r in rows], ["x01 횟수 세기 버튼 · 워밍업\n받기 전", "x02 준비 중 미션 · 기본\n준비 중"])
        self.assertEqual(home.mission_list.height(), rows_height(home.mission_list, 2))
        self.assertFalse(rows[1].flags() & rows[1].flags().ItemIsEnabled)
        self.assertEqual((home.mission_btn.text(), home.mission_note.text()), ("받기", "읽기 2분 · 실전 6분 · 2단계"))
        self.assertEqual(sorted(home.chips), ["t90", "t91"])
        self.assertEqual((home.chips["t90"].ready, home.chips["t91"].ready), (True, False))
        self.assertEqual((home.chips["t90"].count.text(), home.chips["t91"].count.text()), ("0/2", "준비 중"))
        self.assertEqual(home.chips["t90"].toolTip(), "90 시험 주제: state 와 렌더링 · 사슬 2개 가운데 0개 풂")
        self.assertEqual(home.chain_title.text(), "주제 90 「시험 주제: state 와 렌더링」의 사슬")
        self.assertEqual([home.chain_list.item(n).text().split("\n")[1] for n in range(home.chain_list.count())], ["새 사슬", "새 사슬"])
        rows = [home.page_list.item(n) for n in range(home.page_list.count())]
        self.assertEqual([r.text().split("\n")[1] for r in rows], ["아직 읽지 않음", "준비 중"])
        self.assertEqual(home.talked.text(), NO_STUCK)
        web = self.to_live()
        web.answer("90-A", 1, 10, [0], [], False)
        web.show("l90")
        home.refresh()
        self.assertEqual(home.talked.text(), "막힌 질문에서 아는 데까지 말한 비율 0 / 1")
        self.assertEqual(home.mission_list.item(0).text(), "x01 횟수 세기 버튼 · 워밍업\n실전 중 0:00 / 6:00 · 1단계")
        self.assertEqual(home.mission_btn.text(), "이어 하기")
        self.assertTrue(home.page_list.item(0).text().endswith("읽음 10/21"))

    def test_buttons_open_the_screens(self):
        win = self.boot()
        guikit.click(win.hub.web_btn)
        home = win.web_home
        guikit.click(home.review_btn)
        self.assertIs(self.page(), win.web_drill)
        self.assertEqual(win.web_drill.cid, "90-A")
        guikit.click(win.web_drill.back_btn)
        self.assertIs(self.page(), home)
        home.chain_list.setCurrentRow(1)
        guikit.click(home.drill_btn)
        self.assertEqual((self.page(), win.web_drill.cid), (win.web_drill, "90-B"))
        guikit.click(win.web_drill.back_btn)
        guikit.click(home.mission_btn)
        self.assertEqual((self.page(), win.web_mission.mid), (win.web_mission, "x01"))
        guikit.click(win.web_mission.home_btn)
        guikit.click(home.read_btn)
        self.assertEqual((self.page(), win.web_learn.pid), (win.web_learn, "l90"))
        guikit.click(win.web_learn.back_btn)
        self.assertIs(self.page(), home)
        self.assertEqual(self.kinds(), ["learn"])

    def test_a_record_broken_while_running_clears_the_page_and_the_screens_say_why(self):
        win = self.boot()
        guikit.click(win.hub.web_btn)
        home = win.web_home
        study.write_text(self.record_path(), '{"log": [<<<<')
        home.refresh()
        self.assertTrue(home.notice.isVisible())
        self.assertIn("record.json", home.notice.text())
        self.assertEqual((home.chips, home.mission_list.count(), home.stack_label.text(), home.chain_title.text()), ({}, 0, "", ""))
        self.assertFalse(home.mission_btn.isEnabled() or home.drill_btn.isEnabled() or home.read_btn.isEnabled())
        win.open_mission("x01")
        guikit.pump()
        self.assertIn("record.json", win.dialog.text.text())
        self.assertIs(self.page(), home)

    def test_without_node_the_problem_line_shows(self):
        self.node = None
        win = self.boot()
        guikit.click(win.hub.web_btn)
        home = win.web_home
        self.assertTrue(home.problem.isVisible())
        self.assertIn("Node.js 22.12", home.problem.text())
        self.assertEqual(home.stack_label.text(), "Node.js 없음 · 검사 도구 설치됨 (약 80MB)")

    def test_setup_dialog_installs_removes_and_shows_failures(self):
        win = self.boot()
        guikit.click(win.hub.web_btn)
        home = win.web_home
        guikit.click(home.setup_btn)
        dialog = home.setup_dialog
        self.assertTrue(dialog.isVisible())
        self.assertIn("약 80MB", dialog.consent.toPlainText())
        self.assertIn("/fake/node", dialog.consent.toPlainText())  # 경로는 동의 글에만, 상태 줄은 한 줄
        self.assertEqual(dialog.state.text(), "Node.js 22.23.2 · 검사 도구 설치됨 (약 80MB)")
        self.assertEqual(dialog.install_btn.text(), "다시 설치")
        self.assertTrue(dialog.remove_btn.isEnabled())
        guikit.click(dialog.remove_btn)
        self.choose("remove")  # 지우기는 워커에서 돌고 choose 가 끝나기를 기다림
        self.assertFalse(os.path.isdir(os.path.join(self.repo, "node_modules")))
        self.assertEqual((dialog.result.text(), dialog.busy), ("지웠습니다: node_modules", False))
        self.assertEqual((dialog.install_btn.text(), dialog.remove_btn.isEnabled()), ("설치", False))
        self.assertEqual(home.stack_label.text(), "Node.js 22.23.2 · 검사 도구 설치 전")
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
        self.assertEqual(dialog.result.text(), "검사 도구를 설치했습니다(3초).")
        self.assertFalse(dialog.busy)
        self.assertEqual(dialog.install_btn.text(), "다시 설치")
        self.assertEqual(home.stack_label.text(), "Node.js 22.23.2 · 검사 도구 설치됨 (약 80MB)")
        self.assertFalse(home.problem.isVisible())
        failed = {"ok": False, "message": "설치가 실패했습니다(종료 코드 1). 로그를 확인해 주세요: %s" % log, "seconds": 1.0, "log": log}
        with mock.patch.object(stack, "install", return_value=failed):
            guikit.click(dialog.install_btn)
            self.idle()
        self.assertEqual(dialog.result.text(), failed["message"])
        self.assertEqual(dialog.result.objectName(), "error")
        self.assertIn("added 240 packages", dialog.log.toPlainText())
        self.assertTrue(dialog.log.isVisible())
        self.assertGreaterEqual(dialog.height(), layout_height(dialog))  # 로그와 결과 글이 나타나도 위젯이 겹치지 않음
        with mock.patch.object(win, "run_job", return_value=False):  # 다른 일이 도는 중이면 잠긴 채 남지 않음
            dialog.install()
        self.assertEqual((dialog.busy, dialog.status.text(), dialog.install_btn.isEnabled()), (False, BUSY_ELSEWHERE, True))
        self.node = None
        guikit.click(dialog.install_btn)  # Node 가 없으면 설치 단추는 꺼짐
        self.idle()
        dialog.refresh()
        self.assertFalse(dialog.install_btn.isEnabled())
        dialog.close()


class MissionTest(WebTest):
    def test_before_and_reading_states_and_the_reading_timer(self):
        win = self.boot()
        page = self.open_mission()
        self.assertEqual((page.view["phase"], page.phase_tag.text()), ("none", "받기 전"))
        self.assertIs(page.left.currentWidget(), page.brief_view)
        self.assertIn("x01. 횟수 세기 버튼", doc_text(page.brief_view))
        self.assertIn("읽기 2분, 실전 6분", doc_text(page.info_view))
        self.assertEqual(page.timer_label.text(), "읽기 2분 · 실전 6분")
        self.assertTrue(page.get_btn.isVisible())
        self.assertFalse(page.start_btn.isVisible())
        self.assertFalse(page.folder_btn.isEnabled())
        self.assertEqual(page.split_key, "none")
        self.assertGreater(*page.split.sizes())  # 받기 전에는 읽기 안내가 넓음
        self.assertFalse(page.brief_btn.isVisible())
        self.assertEqual(page.strip.text().count("잠김"), 3)
        guikit.click(page.get_btn)
        self.assertEqual((page.view["phase"], page.phase_tag.text()), ("reading", "읽는 중"))
        self.assertEqual(self.kinds(), ["receive"])
        self.assertTrue(page.folder_btn.isEnabled())
        guikit.click(page.folder_btn)
        self.assertEqual(self.opened, [page.view["dir"]])
        self.assertEqual(page.status.text(), "Cursor 에서 폴더를 열었습니다.")
        self.assertEqual(page.timer_label.text(), "읽기 남은 시간 2:00")
        self.tick(seconds=30)
        page.tick()
        self.assertEqual(page.timer_label.text(), "읽기 남은 시간 1:30")
        self.tick(minutes=2, seconds=30)
        page.tick()
        self.assertIn("읽기 시간 끝", page.timer_label.text())
        self.assertIn("1:00 지남", page.timer_label.text())
        self.assertIn(theme.color("wrong"), page.timer_label.text())
        self.assertTrue(page.ai_box.isVisible())
        page.ai_box.setChecked(True)
        guikit.click(page.start_btn)
        self.assertEqual((page.view["phase"], page.view["current"]["no"]), ("live", 0))
        self.assertTrue(self.log()[-1]["no_ai"])
        self.assertEqual(page.timer_label.text(), "실전 0:00 / 6:00")
        self.assertEqual(page.split_key, "step0")

    def test_live_flow_from_explaining_to_the_explanation(self):
        win = self.boot()
        page = self.open_mission()
        guikit.click(page.get_btn)
        guikit.click(page.start_btn)
        # 0단계: 목표 시간이 지나야 점검 항목이 열림
        self.assertIs(page.left.currentWidget(), page.request_page)
        self.assertIn("0단계. 코드 설명", doc_text(page.request_view))
        self.assertIn("목표 시간 1분이 지나면 열립니다", doc_text(page.request_view))
        self.assertFalse(page.request_items.isVisible())
        self.assertFalse(page.explain_btn.isEnabled())
        self.assertFalse(page.check_btn.isEnabled())
        self.assertFalse(page.skip_btn.isVisible())
        self.assertIn("0 진행 중 (목표 1분, 1:00 남음)", page.strip.text())
        self.assertIn("0단계에는 자동 검사가 없습니다", page.result_view.toPlainText())
        guikit.click(page.brief_btn)  # 읽기 안내를 보는 동안 목표 시간이 지나도 끌어오지 않음
        self.tick(minutes=1)
        page.tick()
        self.assertIs(page.left.currentWidget(), page.brief_view)
        guikit.click(page.brief_btn)
        self.assertIs(page.left.currentWidget(), page.request_page)
        self.assertTrue(page.request_items.isVisible())
        self.assertEqual(len(page.request_items.rows), 2)
        self.assertEqual(page.request_items.rows[0].label.text(), "횟수가 App의 state 에 있다고 말했습니다.")  # `코드` 표시를 뺀 글
        self.assertTrue(page.explain_btn.isEnabled())
        self.assertIn("0 진행 중 (목표 1분, 0:00 지남)", page.strip.text())
        page.request_items.rows[0].box.setChecked(True)
        guikit.click(page.explain_btn)
        self.assertEqual(self.log()[-1]["said"], [1, 0])
        # 1단계: 요구, 검사 내용, 힌트, 넘어가기
        self.assertEqual(page.view["current"]["no"], 1)
        text = doc_text(page.request_view)
        self.assertIn("1단계. 더하기 버튼", text)
        self.assertIn("검사는 아래 내용을 확인합니다.", text)
        self.assertIn("0 끝", page.strip.text())
        self.assertIn("1 진행 중", page.strip.text())
        self.assertIn("[검사]를 누르면", page.result_view.toPlainText())
        self.assertEqual(page.split_key, "live")
        self.assertLess(*page.split.sizes())  # 1단계부터는 검사 결과가 넓음
        self.assertTrue(page.check_btn.isEnabled())
        self.assertFalse(page.skip_btn.isEnabled())
        self.assertEqual(page.hint_btn.text(), "힌트 듣기 (0/1)")
        guikit.click(page.hint_btn)
        self.assertIn("면접관 힌트 1", doc_text(page.request_view))
        self.assertIn("접근성 이름", doc_text(page.request_view))
        self.assertFalse(page.hint_btn.isEnabled())
        self.assertEqual(self.kinds()[-1], "hint")
        guikit.click(page.check_btn)
        self.idle()
        text = page.result_view.toPlainText()
        self.assertIn("검사 2개 가운데 0개 통과", text)
        self.assertIn("1a 실패", text)
        self.assertIn("Unable to find role button", text)
        self.assertIn("자세히", text)
        self.assertNotIn("<body />", text)
        page.on_result_link("more:1a")
        self.assertIn("<body />", page.result_view.toPlainText())
        self.assertIn("접기", page.result_view.toPlainText())
        page.on_result_link("fold:1a")
        self.assertNotIn("<body />", page.result_view.toPlainText())
        self.assertIn("고친 뒤 다시 [검사]", page.status.text())
        self.tick(minutes=2)
        page.tick()
        self.assertTrue(page.skip_btn.isEnabled())
        self.solve(1)
        guikit.click(page.check_btn)
        self.idle()
        self.assertEqual((page.view["current"]["no"], page.status.text()), (2, "1단계를 통과했습니다."))
        self.assertIn("1 통과", page.strip.text())
        self.assertIn("2 진행 중", page.strip.text())
        # 2단계 통과 뒤 질문에 답하면 끝남
        self.solve(2)
        guikit.click(page.check_btn)
        self.idle()
        self.assertIsNotNone(page.after)
        guikit.click(page.home_btn)  # 답하는 중에 나가려 하면 기록되지 않는다고 물음
        self.assertIn("통과 뒤 질문", win.dialog.text.text())
        self.choose("")
        self.assertIs(self.page(), page)
        self.assertIsNotNone(page.after)
        self.assertIn("통과 뒤 질문", doc_text(page.request_view))
        self.assertEqual([row.tag.text() for row in page.request_items.rows], ["필수", "보충"])
        self.assertTrue(page.after_btn.isVisible())
        self.assertFalse(page.check_btn.isEnabled())
        self.assertEqual(page.timer_label.text(), "답 시간 0:00 / 0:30")
        self.tick(seconds=35)
        page.tick()
        self.assertIn("0:05 넘김", page.timer_label.text())
        page.request_items.rows[0].box.setChecked(True)
        guikit.click(page.after_btn)
        entry = self.log()[-1]
        self.assertEqual((entry["kind"], entry["need"], entry["extra"], entry["secs"]), ("after", [1], [0], 35))
        self.assertEqual(page.status.text(), "통과 뒤 질문 판정: 통과 (답 시간 35초)")
        self.assertEqual((page.view["phase"], page.phase_tag.text()), ("done", "끝남"))
        self.assertIs(page.left.currentWidget(), page.done_page)
        self.assertIs(page.right.currentWidget(), page.diff_tabs)
        self.assertEqual(page.split_key, "done")
        text = doc_text(page.done_view)
        self.assertIn("단계별 결과", text)
        self.assertIn("1단계 더하기 버튼: 통과 (힌트 1)", text)
        self.assertIn("모범 답안", text)
        self.assertEqual(page.mine_diff.toPlainText(), "모범 답안과 같습니다.")
        self.assertTrue(page.template_diff.toPlainText().startswith("모범 답안과 다른 파일 1개: src/App.tsx"))
        self.assertIn("+        초기화", page.template_diff.toPlainText())
        self.assertEqual([page.diff_tabs.tabText(n) for n in range(3)], ["내 코드와 모범 답안", "템플릿과 모범 답안", "스스로 점검"])
        self.assertTrue(page.diff_tabs.isTabVisible(2))  # 스스로 점검은 해설을 가리지 않게 오른쪽 탭에 있음
        self.assertEqual(len(page.done_items.rows), 5)
        page.diff_tabs.setCurrentWidget(page.check_tab)
        guikit.pump()
        self.assertTrue(inside(win, page.save_btn))
        for number in (0, 2):
            page.done_items.rows[number].box.setChecked(True)
        guikit.click(page.save_btn)
        self.assertEqual(self.log()[-1]["ticks"], {"c1": 1, "c2": 0, "c3": 1, "m1": 0, "m2": 0})
        self.assertEqual([b.text() for b in page.page_btns], ["학습 노트 l90"])
        guikit.click(page.followup_btn)
        self.assertEqual((self.page(), win.web_drill.cid, win.web_drill.back), (win.web_drill, "x01-F", ("mission", "x01")))
        guikit.click(win.web_drill.back_btn)
        self.assertEqual((self.page(), page.view["phase"]), (page, "done"))
        guikit.click(page.brief_btn)
        self.assertIs(page.left.currentWidget(), page.brief_view)
        self.assertEqual(page.brief_btn.text(), "해설로 돌아가기")
        guikit.click(page.brief_btn)
        self.assertIs(page.left.currentWidget(), page.done_page)

    def test_timers_come_from_record_timestamps_and_survive_a_restart(self):
        self.to_live(explained=False)
        self.tick(minutes=7)
        for shown, ticked in (("7:00", "7:10"), ("7:10", "7:20")):  # 창을 새로 띄워도 기록 시각에서 이어 셈
            win = self.boot()
            page = self.open_mission()
            self.assertEqual(page.timer_label.text().split(" · ")[0], "실전 %s / 6:00" % shown)
            self.assertIn("넘김", page.timer_label.text())
            self.assertIn("0 진행 중 (목표 1분, %s 지남)" % ("6:00" if shown == "7:00" else "6:10"), page.strip.text())
            self.assertTrue(page.request_items.isVisible())  # 목표 시간이 이미 지나 점검 항목이 열려 있음
            self.assertTrue(page.explain_btn.isEnabled())
            self.tick(seconds=10)
            page.tick()
            self.assertIn("실전 %s / 6:00" % ticked, page.timer_label.text())
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
        self.choose("skip")
        self.assertEqual((self.kinds()[-1], page.view["current"]["no"]), ("skip", 2))
        self.assertIn("1 넘어감", page.strip.text())
        guikit.click(page.finish_btn)
        self.choose("finish")
        self.assertEqual((page.view["phase"], self.kinds()[-1]), ("done", "finish"))
        self.assertIn("2단계 초기화 버튼: 잠김", doc_text(page.done_view))
        self.assertIn("실전 2:00", doc_text(page.done_view))
        self.assertTrue(page.mine_diff.toPlainText().startswith("모범 답안과 다른 파일 1개: src/App.tsx"))
        self.assertFalse(page.finish_btn.isVisible())
        self.assertTrue(page.again_btn.isVisible())
        guikit.click(page.again_btn)
        self.choose("again")
        self.assertEqual((page.view["phase"], page.view["try"]), ("reading", 2))
        self.assertEqual(self.kinds()[-1], "receive")

    def test_receiving_without_the_stack_offers_the_install_dialog(self):
        os.remove(os.path.join(self.repo, stack.VITEST_MJS))
        win = self.boot()
        page = self.open_mission()
        self.assertIn("web install", doc_text(page.info_view))
        guikit.click(page.get_btn)
        self.assertEqual(set(win.dialog.buttons), {"install", "get", ""})
        self.choose("install")
        dialog = page.setup_dialog
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.install_btn.text(), "설치")
        dialog.close()
        guikit.pump()
        self.assertEqual(page.view["phase"], "none")  # 설치하지 않고 닫으면 받지 않음
        guikit.click(page.get_btn)
        self.choose("get")
        self.assertEqual(page.view["phase"], "reading")

    def test_locked_mission_and_unknown_mission_show_a_message(self):
        win = self.boot()
        win.open_mission("x02")
        guikit.pump()
        self.assertIn("아직 출제되지 않은", win.dialog.text.text())
        self.assertIs(self.page(), win.hub)


class DrillTest(WebTest):
    def test_marks_verdicts_and_the_chain_end(self):
        win = self.boot()
        page = self.open_drill("90-A")
        self.assertEqual((page.title.text(), page.counter.text(), page.timer_label.text()),
                         ("사슬 90-A 버튼을 눌렀는데 화면이 그대로일 때", "질문 1 / 3", "답 시간 1:00"))
        self.assertIn("사슬 90-A. 버튼을 눌렀는데 화면이 그대로일 때", doc_text(page.intro_view))
        self.assertIn("let count = 0;", doc_text(page.intro_view))
        self.assertTrue(page.ask.text().startswith("면접관: 버튼을 눌러도 화면의 숫자가 바뀌지 않습니다."))
        self.assertFalse(page.items.isVisible())
        card_height = page.card_scroll.height()
        self.assertGreater(page.intro_view.height(), card_height)  # 짚을 내용이 열리기 전에는 사슬 소개가 더 넓음
        self.mono += 70
        page.tick()
        self.assertIn("0:10 넘김", page.timer_label.text())
        page.note.setPlainText("일반 변수는 React 가 모름")
        guikit.click(page.confirm_btn)
        self.assertTrue(page.timer_label.text().startswith("답 시간 1:10 · "), page.timer_label.text())  # 답하는 동안과 같은 m:ss
        self.assertIn("0:10 넘김", page.timer_label.text())
        self.assertFalse(page.answer_row.isVisible())  # 한 번 쓴 [답 확인] [모르겠어요]는 숨겨 그 줄을 짚을 내용에 돌려줌
        self.assertGreater(page.card_scroll.height(), card_height)  # 짚을 내용만큼 질문 칸이 커짐
        self.assertTrue(inside(win, page.next_btn))
        self.assertEqual([row.tag.text() for row in page.items.rows], ["필수", "보충"])
        self.assertTrue(page.items.rows[0].label.text().startswith("count는 바뀌지만"))
        self.assertTrue(page.stuck.isVisible())
        self.assertTrue(page.talked.isVisible())
        page.items.rows[0].box.setChecked(True)
        self.assertFalse(page.stuck.isVisible())
        self.assertFalse(page.talked.isVisible())
        page.items.rows[1].box.setChecked(True)
        guikit.click(page.next_btn)
        entry = self.log()[-1]
        self.assertEqual({k: entry[k] for k in ("kind", "chain", "q", "secs", "need", "extra", "talked", "note")},
                         {"kind": "drill", "chain": "90-A", "q": 1, "secs": 70, "need": [1], "extra": [1], "talked": None,
                          "note": "일반 변수는 React 가 모름"})
        self.assertEqual((page.counter.text(), page.status.text(), page.progress.text()), ("질문 2 / 3", "Q1 판정: 통과", "Q1 통과"))
        self.assertEqual(page.note.toPlainText(), "")
        self.assertTrue(page.answer_row.isVisible())
        guikit.click(page.give_up_btn)
        self.assertFalse(page.items.rows[0].box.isEnabled())
        self.assertIn("다시 그려 달라", page.stuck.text())
        self.assertTrue(page.talked.isVisible())
        page.talked.rows[0].box.setChecked(True)
        guikit.click(page.next_btn)
        entry = self.log()[-1]
        self.assertEqual((entry["q"], entry["need"], entry["talked"]), (2, [0], 1))
        self.assertEqual(page.progress.text(), "Q1 통과 · Q2 막힘")
        guikit.click(page.confirm_btn)
        page.items.rows[0].box.setChecked(True)
        self.assertEqual(page.next_btn.text(), "사슬 끝내기")
        guikit.click(page.next_btn)
        self.assertIs(page.stack.currentWidget(), page.end_page)
        text = doc_text(page.end_view)
        self.assertIn("사슬 결과: 막힘", text)
        self.assertIn("질문별 통과, 막힘, 통과", text)
        self.assertIn("상자 1, 다음 복습 10/22", text)
        self.assertIn("리렌더링이 안 돼서 그렇습니다.", text)
        self.assertIn("이어 말하기", text)
        self.assertEqual(self.kinds()[-1], "chain")
        self.assertEqual(page.learn_btn.text(), "학습 노트 l90 읽기 (90a 절)")
        guikit.click(page.learn_btn)
        learn = win.web_learn
        self.assertEqual((self.page(), learn.pid, learn.where.text()), (learn, "l90", "90a 절"))
        self.assertTrue(scroll_to_heading(learn.view, "일반 변수는 화면을 바꾸지 못합니다"))
        guikit.click(learn.back_btn)
        self.assertEqual((self.page(), page.stack.currentWidget()), (page, page.end_page))  # 끝난 자리로 돌아옴
        guikit.click(page.done_btn)
        self.assertIs(self.page(), win.web_home)
        self.assertEqual(win.web_home.chain_list.item(0).text().split("\n")[1], "상자 1 · 다음 복습 10/22")

    def test_review_shows_the_previous_answer_and_marks(self):
        web = self.web()
        web.answer("90-A", 1, 40, [1], [0], None, "플래그 변수를 말함")
        web.answer("90-A", 2, 40, [0], [], True)
        web.answer("90-A", 3, 40, [1], [1])
        web.finish_chain("90-A")
        self.clock = "2026-10-22T09:00:00"
        win = self.boot()
        page = self.open_drill("90-A")
        self.assertIn("상자 1, 2번째 복습", doc_text(page.intro_view))
        guikit.click(page.confirm_btn)
        self.assertEqual(page.timer_label.text(), "답 시간 0:00 (1:00 안)")
        self.assertEqual(page.last.text(), "지난 답 (10/21, 40초): 플래그 변수를 말함")
        self.assertEqual([row.note.text() for row in page.items.rows], ["지난번 표시함", "지난번 빠뜨림"])
        page.items.rows[0].box.setChecked(True)
        guikit.click(page.next_btn)
        guikit.click(page.confirm_btn)
        self.assertEqual(page.last.text(), "지난 답 (10/21, 40초): 적은 내용 없음")
        self.assertEqual([row.note.text() for row in page.items.rows], ["지난번 빠뜨림"])

    def test_mission_followups_stay_locked_until_the_mission_ends(self):
        win = self.boot()
        win.open_drill("x01-F")
        guikit.pump()
        self.assertIn("미션을 끝낸 뒤에", win.dialog.text.text())
        self.assertIs(self.page(), win.hub)


class LearnTest(WebTest):
    def test_figures_sections_and_the_record(self):
        win = self.boot()
        win.open_learn("l90")
        self.idle()
        learn = win.web_learn
        text = doc_text(learn.view)
        self.assertIn("그림 준비 중. 그림 1. 두 호출이 같은 값을 넣어", text)  # 고정 은행에는 그림 파일이 없음
        self.assertNotIn("내용:", text)
        self.assertEqual([p for p in learn.view.pieces if isinstance(p, FigureView)], [])
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
        self.assertEqual(learn.where.text(), "90b 절")
        self.assertTrue(scroll_to_heading(learn.view, "같은 렌더의 값을 두 번 쓰면"))
        self.assertEqual(self.kinds(), ["learn", "learn"])


class LookTest(WebTest):
    """어두운 테마에서 밝은 조각이 남지 않고, 작은 창(1024x700)에서 단추가 창 밖으로 나가지 않음. 화면마다 한 번씩 봄."""

    def screens(self, win):
        """(이름, 그 화면을 띄우는 함수, 살펴볼 단추들). 미션은 네 상태를 모두 거침."""
        mission, drill = win.web_mission, win.web_drill

        def mission_live():
            self.open_mission()
            guikit.click(mission.get_btn)
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
            mission.diff_tabs.setCurrentWidget(mission.check_tab)

        def drill_checklist():
            self.open_drill("90-A")
            guikit.click(drill.confirm_btn)

        def drill_end():
            for number in range(3):
                if not drill.checked:
                    guikit.click(drill.confirm_btn)
                drill.items.rows[0].box.setChecked(True)
                guikit.click(drill.next_btn)

        return (("hub", win.go_hub, (win.hub.web_btn,)),
                ("home", win.go_web, (win.web_home.review_btn, win.web_home.mission_btn, win.web_home.drill_btn, win.web_home.read_btn)),
                ("mission_before", lambda: self.open_mission(), (mission.get_btn, mission.folder_btn)),
                ("mission_live", mission_live, (mission.check_btn, mission.finish_btn, mission.hint_btn, mission.skip_btn)),
                ("mission_done", mission_done, (mission.again_btn, mission.save_btn, mission.followup_btn)),
                ("drill_checklist", drill_checklist, (drill.next_btn, drill.give_up_btn)),
                ("drill_end", drill_end, (drill.done_btn, drill.learn_btn)),
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
        win = self.boot((1024, 700))
        self.assertEqual((win.width(), win.height()), (1024, 700))
        for name, show, buttons in self.screens(win):
            show()
            self.idle()
            page = self.page()
            self.assertLessEqual(page.minimumSizeHint().width(), 1024, name)
            self.assertLessEqual(page.minimumSizeHint().height(), 700, name)
            self.assertEqual((win.width(), win.height()), (1024, 700), name)
            scroll = page.findChild(QScrollArea) if name in ("hub", "home") else None  # 허브와 웹 홈은 작은 창에서 스크롤함
            for button in buttons:
                if not button.isVisible():
                    continue
                if scroll is not None:
                    scroll.ensureWidgetVisible(button)
                    guikit.pump()
                self.assertTrue(inside(win, button), "%s: %s" % (name, button.text()))
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
