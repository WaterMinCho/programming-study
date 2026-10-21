# -*- coding: utf-8 -*-
"""첫 화면(gui/hub_page.py)과 창 연결(gui/window.py, gui/worker.py). 실제 MainWindow 를 띄우되 여행 은행은 고정 은행
tests/journey_bank, 웹 은행은 tests/web_bank, 풀이 폴더는 임시 폴더, 제출 모듈은 가짜를 씀. 웹 트랙의 Node 찾기는 가짜로 바꿔
자식 프로세스를 띄우지 않음(웹 줄 카드 자체는 tests/test_gui_web.py 가 봄). PyQt6 가 없으면 전부 건너뜀.

채점 도중 창을 닫는 테스트는 실제 Python 하네스를 띄우므로 STUDY_LEAN_CI 가 있으면 건너뜀. 시간 값(ms)은 단언하지 않음."""
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import guikit  # noqa: E402

from PyQt6.QtCore import QPoint, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import qGray  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QLabel  # noqa: E402

import adaptive  # noqa: E402
import session  # noqa: E402
import study  # noqa: E402
from gui import errors, theme  # noqa: E402
from gui.journey_page import NODE_TITLE  # noqa: E402
from gui.window import MainWindow  # noqa: E402
from journey import bank, node, runner  # noqa: E402
from webprep import bank as web_bank  # noqa: E402
from webprep import stack  # noqa: E402

FIXTURE = os.path.join(guikit.ROOT, "tests", "journey_bank")
WEB_FIXTURE = os.path.join(guikit.ROOT, "tests", "web_bank")
FAKE_NODE = {"path": "/fake/node", "version": "22.23.2", "major": 22}
SKIP_LEAN = unittest.skipIf(os.environ.get("STUDY_LEAN_CI"), "자식 프로세스를 띄우는 테스트는 ci.yml 의 화면 테스트 작업에서 돎")
USER = "tester"


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


class FakeGitFlow:
    """제출 모듈처럼 dict 를 돌려주는 가짜. replies 에 메서드별 응답을 넣고, before_submit 은 제출 직전에 부름."""

    def __init__(self):
        self.calls, self.replies, self.before_submit = [], {}, None

    def _reply(self, name):
        self.calls.append(name)
        base = {"status": "nothing", "message": "", "detail": "", "pr_url": None, "restart": False, "changed": False, "backup": None}
        return dict(base, **self.replies.get(name, {}))

    def sync(self):
        return self._reply("sync")

    def submit(self):
        if self.before_submit:
            self.before_submit()
        return self._reply("submit")


def grade_entry(pid, lang="python", passed=True, at=None):
    return {"at": at or adaptive.now(), "kind": "grade", "item": "t01/" + pid, "lang": lang, "score": 100.0 if passed else 40.0,
            "acc": 100.0, "eff": 0.0, "passed": passed, "tests": [1, 1, 0, 0]}


class HubTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gui_hub_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for target, name, value in ((study, "SUBMISSIONS_DIR", os.path.join(self.tmp, "submissions")),
                                    (study, "USER_FILE", os.path.join(self.tmp, ".study_user")),
                                    (runner, "CACHE_DIR", os.path.join(self.tmp, "cache")), (bank, "BANK_DIR", FIXTURE),
                                    (web_bank, "BANK_DIR", WEB_FIXTURE), (stack, "find_node", lambda saved=None, probe=False: FAKE_NODE)):
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
        self.git = FakeGitFlow()
        self.settings = QSettings(os.path.join(self.tmp, "settings.ini"), QSettings.Format.IniFormat)
        self.win = None

    def tearDown(self):
        win = self.win
        if win is not None:
            guikit.wait_until(lambda: win.job is None)
            if win.dialog is not None:
                win.dialog.close()
            win.close()
            win.deleteLater()
            guikit.pump()
        if errors.state["dialog"] is not None:
            errors.state["dialog"].close()
        crashed = os.path.isdir(self.logs)  # 슬롯 안의 예외는 테스트로 올라오지 않고 기록만 남음
        report = "".join(study.read_text(os.path.join(self.logs, name)) for name in os.listdir(self.logs)) if crashed else ""
        self.assertFalse(crashed, report)

    # 도우미

    def boot(self):
        self.win = win = MainWindow(self.settings, lambda root, user: (self.git, ""))
        win.open_url = lambda url: None
        win.resize(1280, 800)
        win.show()
        win.boot()
        self.idle()
        return win

    def idle(self):
        guikit.pump()
        guikit.wait_until(lambda: self.win.job is None)
        guikit.pump()

    def page(self):
        return self.win.pages.currentWidget()

    def choose(self, key):
        self.assertTrue(self.win.dialog.isVisible())
        guikit.click(self.win.dialog.buttons[key])

    def progress_path(self):
        return os.path.join(study.SUBMISSIONS_DIR, USER, "journey", "progress.json")

    def write_log(self, entries):
        data = {"format": 1, "user": USER, "created": adaptive.now(), "log": list(entries)}
        study.write_text(self.progress_path(), json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    def read_log(self):
        return study.read_json(self.progress_path())["log"] if os.path.isfile(self.progress_path()) else []

    def graded_round(self, size=25):
        """퀴즈 size 문항짜리 회차를 만들고 한 번 제출해 채점함. 문항마다 같은 시각의 시도 기록이 하나씩 남음."""
        sess = session.Session(USER)
        keys = sorted((key for key, item in sess.cat.items() if item["kind"] == "quiz"), key=study.natural_key)[:size]
        self.assertEqual(len(keys), size)
        rnd = {"id": "r1", "kind": "round", "focus": [], "items": keys, "retest": [], "shortages": [], "created": adaptive.now(),
               "tries": 0, "avg_level": 1}
        sess.prof["rounds"].append(rnd)
        adaptive.write_round(USER, rnd, sess.cat)
        adaptive.save_profile(sess.prof)
        sess.grade("r1", finalize=True)
        return adaptive.load_profile(USER)

    def open_problem(self, pid):
        """허브에서 [여행 떠나기] → 지도에서 pid 를 골라 [문제 풀기]."""
        win = self.win
        if self.page() is not win.journey_map:
            guikit.click(win.hub.journey_btn)
        page = win.journey_map
        row = next(n for n in range(page.listw.count()) if page.listw.item(n).data(Qt.ItemDataRole.UserRole) == pid)
        page.listw.setCurrentRow(row)
        guikit.click(page.solve_btn)
        self.assertIs(self.page(), win.journey_page, win.dialog and win.dialog.text.text())
        return win.journey_page

    def type_code(self, text):
        editor = self.win.journey_page.code_panel.editor
        cur = editor.textCursor()
        cur.select(cur.SelectionType.Document)
        cur.insertText(text)
        editor.setTextCursor(cur)

    def code_path(self, pid):
        return os.path.join(study.SUBMISSIONS_DIR, USER, "journey", "t01", pid + ".py")


class HubScreenTest(HubTest):
    def test_starts_at_the_hub_and_both_cards_show_their_numbers(self):
        prof = self.graded_round()
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(timespec="seconds")
        self.write_log([grade_entry("p1", at=yesterday), grade_entry("p1"), grade_entry("p2"), grade_entry("p2", "javascript")])
        win = self.boot()
        hub = win.hub
        self.assertIs(self.page(), hub)
        self.assertEqual((win.area, win.windowTitle()), ("hub", "프로그래밍 스터디"))
        self.assertIn("프로그래밍 스터디", [label.text() for label in hub.findChildren(QLabel)])
        self.assertEqual(hub.user.text(), "ID: tester")

        # 파이썬 카드: 서비스가 낸 값을 그대로 보임
        overview = win.session.overview()
        last = [r for r in overview["rounds"] if r["completed"]][-1]
        earned = int(last["first_score"].split("/")[0])
        self.assertEqual((hub.ready_label.text(), hub.ready.text()), ("시험 준비도", "%d%%" % overview["readiness"]))
        self.assertEqual(hub.mastered.text(), "%d / %d" % (overview["mastered"], overview["total_units"]))
        self.assertEqual(hub.python_next.text(), win.next_action(overview)[0])
        self.assertEqual((hub.python_last.text(), hub.python_last_label.text()), ("%d / 100" % earned, "%s 첫 채점" % last["title"]))
        self.assertTrue(hub.python_last_stat.isVisible())

        # 여행 카드: 1-1·1-2 를 통과해 보스가 열리고 다음 추천은 보스. 언어별 통과 수는 수치 하나씩. 띠에는 던전 16개가 모두 나옴
        self.assertEqual((hub.journey_passed.text(), hub.journey_boss.text()), ("2 / 4", "0 / 1"))
        self.assertEqual({lang: item.value.text() for lang, item in hub.journey_langs.items()}, {"python": "2", "javascript": "1"})
        self.assertEqual(hub.journey_langs["javascript"].name.text(), "JavaScript 통과")
        self.assertTrue(hub.journey_next.text().startswith("1-B "), hub.journey_next.text())
        self.assertTrue(hub.journey_next.text().endswith(" · 던전 1 「시험 마을」"), hub.journey_next.text())
        self.assertEqual(len(hub.strip.rows), 16)
        self.assertTrue(hub.journey_btn.isEnabled())
        self.assertFalse(hub.journey_error.isVisible())

        # 막대: 25문항 회차를 한 번 채점한 날의 파이썬 값은 1, 여행은 채점 기록 수, 웹은 기록이 없어 0. 어제도 여행 채점이 있어 연속 2일
        today = datetime.date.today()
        self.assertEqual(len([a for a in prof["attempts"] if a["round"] == "r1"]), 25)
        self.assertEqual(hub.chart.days[-1], (today, 1, 3, 0))
        self.assertEqual(hub.chart.days[-2], (today - datetime.timedelta(days=1), 0, 1, 0))
        self.assertEqual(len(hub.chart.days), 7)
        self.assertEqual(hub.streak.text(), "연속 학습 2일")
        self.assertTrue(hub.recent_box.isVisible())
        self.assertEqual(len(hub.recent.rows), 5)  # 다섯 줄까지. 줄마다 (무엇을 채점했는지, 시각)
        labels, stamps = zip(*hub.recent.rows)
        self.assertIn("1-2 JavaScript 100.0점", labels)
        self.assertIn("파이썬 스터디 %s" % last["title"], labels)
        self.assertTrue(all(stamp.startswith("%d/%d " % (today.month, today.day)) for stamp in stamps[:4]), stamps)

    def test_buttons_and_cards_move_between_the_two_areas(self):
        win = self.boot()
        hub = win.hub
        guikit.click(hub.python_btn)
        self.assertEqual((self.page(), win.area), (win.home, "python"))
        guikit.click(win.home.hub_btn)
        self.assertEqual((self.page(), win.area), (hub, "hub"))
        QTest.mouseClick(hub.python_card, guikit.LEFT, pos=QPoint(8, hub.python_card.height() - 8))  # 카드의 빈 곳을 눌러도 들어감
        guikit.pump()
        self.assertIs(self.page(), win.home)
        guikit.click(win.home.hub_btn)
        QTest.mouseClick(hub.journey_card, guikit.LEFT, pos=QPoint(8, hub.journey_card.height() - 8))
        guikit.pump()
        self.assertEqual((self.page(), win.area), (win.journey_map, "journey"))
        page = self.open_problem("p1")
        self.assertEqual((page.did, page.pid), ("t01", "p1"))
        self.assertEqual(self.settings.value("journey/last"), "t01/p1")
        guikit.click(page.map_btn)
        self.assertIs(self.page(), win.journey_map)
        guikit.click(win.journey_map.home_btn)
        self.assertEqual((self.page(), win.area), (hub, "hub"))

    def test_hub_submit_writes_unsaved_journey_code_first(self):
        win = self.boot()
        guikit.click(win.hub.git_btn)
        self.idle()
        self.assertEqual(self.git.calls, ["sync", "submit"])
        self.choose("ok")
        self.open_problem("p1")
        code = "def solution(nums):\n    return sum(nums)  # 제출 직전\n"
        path, seen = self.code_path("p1"), []
        self.git.before_submit = lambda: seen.append(study.read_text(path) if os.path.isfile(path) else None)
        self.type_code(code)
        self.assertTrue(win.journey_page.dirty)  # 자동 저장을 기다리지 않음
        win.hub.git_btn.click()
        self.idle()
        self.assertEqual(seen, [code])
        self.assertEqual(win.journey_page.dirty, {})
        self.choose("ok")

    def test_fetching_changed_problems_keeps_the_area(self):
        win = self.boot()
        self.git.replies["sync"] = {"status": "ok", "message": "새 문제를 받았습니다.", "changed": True}

        def fetch():
            before = win.journey
            win.fetch_problems()
            self.idle()
            self.assertIsNot(win.journey, before)  # 은행과 기록을 새로 읽음
            self.assertIn("새 문제를 받았습니다", win.dialog.text.text())
            self.choose("ok")

        guikit.click(win.hub.journey_btn)
        fetch()
        self.assertEqual((self.page(), win.area), (win.journey_map, "journey"))
        page = self.open_problem("p2")
        fetch()
        self.assertEqual((self.page(), page.pid), (page, "p2"))  # 같은 문제를 다시 읽음
        guikit.click(page.map_btn)
        guikit.click(win.journey_map.home_btn)
        guikit.click(win.hub.python_btn)
        fetch()
        self.assertEqual((self.page(), win.area), (win.home, "python"))
        guikit.click(win.home.hub_btn)
        fetch()
        self.assertEqual((self.page(), win.area), (win.hub, "hub"))

    def test_broken_journey_record_still_opens_python_study(self):
        os.makedirs(os.path.dirname(self.progress_path()), exist_ok=True)
        study.write_text(self.progress_path(), '{"log": [<<<<')
        win = self.boot()
        hub = win.hub
        self.assertIs(self.page(), hub)
        self.assertIsNone(win.journey)
        self.assertTrue(hub.journey_error.isVisible())
        self.assertIn("progress.json", hub.journey_error.text())
        self.assertIn("파일을 고친 뒤 프로그램을 다시 실행해 주세요.", hub.journey_error.text())
        self.assertFalse(hub.journey_btn.isEnabled())
        self.assertFalse(hub.journey_passed.isVisible())
        self.assertFalse(hub.python_last_stat.isVisible())  # 제출한 회차가 없으면 지난 회차 수치를 빼고 보임
        QTest.mouseClick(hub.journey_card, guikit.LEFT, pos=QPoint(8, hub.journey_card.height() - 8))
        guikit.pump()
        self.assertIs(self.page(), hub)  # 꺼진 카드는 눌러도 그대로
        self.assertEqual(hub.chart.days[-1][2], 0)
        self.assertFalse(hub.recent_box.isVisible())  # 채점 기록이 없으면 최근 채점 칸을 빼고 막대만 보임
        self.assertTrue(hub.git_tips.isVisible())
        guikit.click(hub.python_btn)
        self.assertIs(self.page(), win.home)
        self.assertEqual(win.home.action_btn.text(), "진단 테스트 시작")
        guikit.click(win.home.hub_btn)
        hub.set_busy(True, "확인 중입니다.")
        hub.set_busy(False)
        self.assertFalse(hub.journey_btn.isEnabled())  # 잠금이 풀려도 여행 단추는 꺼진 채로 남음

    def test_dark_theme_leaves_no_light_patches(self):
        self.write_log([grade_entry("p1")])
        win = self.boot()
        self.addCleanup(theme.set_mode, theme.state["mode"])
        theme.set_mode("dark")
        guikit.pump()
        self.assertIs(self.page(), win.hub)
        self.assertEqual(bright_share(win), 0)
        win.notice = {"message": "인터넷에 연결되지 않아 새 문제를 받지 못했습니다.", "detail": "git fetch 실패"}
        win.hub.refresh()
        guikit.pump()
        self.assertTrue(win.hub.notice.isVisible())
        self.assertEqual(bright_share(win), 0)


class JobTest(HubTest):
    def test_progress_reaches_the_screen_and_closing_cancels(self):
        win = self.boot()
        seen, done = [], []

        def work(report, cancel):
            report({"kind": "status", "text": "하나"})
            report({"kind": "status", "text": "둘"})
            return cancel.wait(30)

        win.run_job("진행 알림", work, done.append, on_progress=seen.append)
        guikit.wait_until(lambda: len(seen) == 2, 5)
        self.assertEqual([event["text"] for event in seen], ["하나", "둘"])
        self.assertEqual(done, [])
        win.close()
        self.assertTrue(win.isVisible())  # 일이 끝나기를 기다림
        guikit.wait_until(lambda: not win.isVisible(), 10)
        self.assertEqual(done, [True])  # 취소 신호를 받고 끝남
        self.assertIsNone(win.job)

    def test_job_without_progress_is_called_with_no_arguments(self):
        win = self.boot()
        done = []
        win.run_job("인자 없는 일", lambda: "끝", done.append)
        self.idle()
        self.assertEqual(done, ["끝"])

    @SKIP_LEAN
    def test_closing_while_grading_cancels_and_records_nothing(self):
        win = self.boot()
        page = self.open_problem("p1")
        self.type_code("def solution(nums):\n    while True:\n        pass\n")
        guikit.click(page.grade_btn)
        self.assertIsNotNone(win.job)
        guikit.pump(300)  # 채점 프로세스가 뜰 시간
        win.close()
        self.assertTrue(win.isVisible())
        self.assertTrue(win.job[0].cancel.is_set())
        guikit.wait_until(lambda: not win.isVisible(), 30)
        self.assertIsNone(win.job)
        self.assertEqual([e for e in self.read_log() if e["kind"] == "grade"], [])
        self.assertTrue(study.read_text(self.code_path("p1")).startswith("def solution(nums):\n    while True"))


class NodeLookupTest(HubTest):
    """node 찾기와 버전 확인은 워커에서 함. 느린 node 후보가 있어도 누른 단추가 화면을 멈추지 않게 함."""

    NODE_INFO = {"path": "/opt/node/bin/node", "version": "22.0.0", "major": 22}

    def setUp(self):
        super().setUp()
        self.threads = {"search": [], "check": []}  # 부른 스레드가 화면 스레드였는지
        self.found = None

        def search(probe=False, saved=None):
            self.threads["search"].append(threading.current_thread() is threading.main_thread())
            return self.found

        def check(path):
            self.threads["check"].append(threading.current_thread() is threading.main_thread())
            return dict(self.NODE_INFO, path=path)

        for patcher in (mock.patch.object(node, "_found", {}), mock.patch.object(node, "search", search),
                        mock.patch.object(node, "check", check)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_saved_javascript_is_checked_before_the_map_opens(self):
        self.found = self.NODE_INFO
        self.settings.setValue("journey/lang", "javascript")
        win = self.boot()
        guikit.click(win.hub.journey_btn)
        self.idle()
        self.assertIs(self.page(), win.journey_map)
        self.assertEqual("javascript", win.journey_map.lang_bar.lang)
        page = self.open_problem("p1")
        self.assertEqual("javascript", page.lang)
        self.assertEqual([False], self.threads["search"], "한 번 찾은 결과를 기억하고, 찾기는 워커에서만 함")

    def test_javascript_button_and_node_path_are_checked_in_the_worker(self):
        win = self.boot()
        guikit.click(win.hub.journey_btn)
        self.assertEqual([], self.threads["search"], "Python 이면 node 를 찾지 않음")
        page = win.journey_map
        guikit.click(page.lang_btns["javascript"])
        self.idle()
        self.assertEqual([False], self.threads["search"])
        self.assertEqual(NODE_TITLE, win.dialog.windowTitle())
        self.assertEqual("python", page.lang_bar.lang)
        win.pick_file = lambda title: "/opt/node/bin/node"
        self.choose("pick")
        self.idle()
        self.assertEqual([False], self.threads["check"])
        self.assertEqual("javascript", page.lang_bar.lang)
        self.assertEqual("/opt/node/bin/node", self.settings.value("journey/node"))


if __name__ == "__main__":
    unittest.main()
