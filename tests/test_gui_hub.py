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
from aiprep import bank as ai_bank  # noqa: E402
from gui import errors, hub_page, kit, theme  # noqa: E402
from gui.journey_page import NODE_RETRY, NODE_TITLE  # noqa: E402
from gui.window import MainWindow  # noqa: E402
from journey import bank, node, runner  # noqa: E402
from journey.service import JourneyError  # noqa: E402
from webprep import bank as web_bank  # noqa: E402
from webprep import stack  # noqa: E402

FIXTURE = os.path.join(guikit.ROOT, "tests", "journey_bank")
WEB_FIXTURE = os.path.join(guikit.ROOT, "tests", "web_bank")
AI_FIXTURE = os.path.join(guikit.ROOT, "tests", "ai_bank")
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
        self.has_pending = True
        self.has_updates = False
        self.update_checks = 0

    def pending(self):
        return {"status": "ok", "pending": self.has_pending, "count": int(self.has_pending)}

    def updates(self):
        self.update_checks += 1
        return {"status": "ok", "available": self.has_updates, "count": int(self.has_updates)}

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
                                    (web_bank, "BANK_DIR", WEB_FIXTURE), (ai_bank, "AI_DIR", AI_FIXTURE),
                                    (stack, "find_node", lambda saved=None, probe=False: FAKE_NODE)):
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
        errors.install(self.logs)
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
        if errors.state["dialog"] is not None:
            errors.state["dialog"].close()
        crashed = os.path.isdir(self.logs)  # 슬롯 안의 예외는 테스트로 올라오지 않고 기록만 남음
        report = "".join(study.read_text(os.path.join(self.logs, name)) for name in os.listdir(self.logs)) if crashed else ""
        self.assertFalse(crashed, report)

    # 도우미

    def boot(self):
        self.win = win = MainWindow(self.settings, lambda root, user: (self.git, ""), identity_factory=guikit.identity_factory)
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
        """첫 화면의 알고리즘 여행 줄 → 지도에서 pid 의 줄을 한 번 누름."""
        win = self.win
        if self.page() is not win.journey_map:
            guikit.click(win.hub.journey_row)
        page = win.journey_map
        guikit.click(next(row for row in page.rows.rows if row.data == pid))
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
    def test_commented_web_entry_is_absent_from_hub_and_both_navigation_layouts(self):
        self.assertNotIn("web", study.ENTRY_TRACKS)
        win = self.boot()
        self.assertNotIn(win.hub.web_row, win.hub.tracks.rows)
        self.assertFalse(win.hub.web_row.isVisible())
        self.assertNotIn("web", [row[0] for row in win.workspace.subjects])
        self.assertNotIn("go_web", [win.workspace.compact.itemData(i) for i in range(win.workspace.compact.count())])
        with mock.patch.object(win.web, "overview", side_effect=AssertionError("숨긴 과목을 조회했음")):
            win.hub.refresh()
        win.hub.show_next(win.session.overview(), None, {"missions": [{"phase": "live"}], "activity": ["2099-12-31"]})
        self.assertNotIn("웹 면접", win.hub.next_card.line.text())
        with mock.patch.object(win, "open_mission") as mission, mock.patch.object(win, "open_learn") as learn, \
                mock.patch.object(win, "open_drill") as drill:
            win.hub.open_next()
            mission.assert_not_called()
            learn.assert_not_called()
            drill.assert_not_called()
        with mock.patch.object(win.web_home, "refresh") as refresh:
            win.go_web()
            refresh.assert_not_called()
        self.assertEqual("hub", win.area)
        self.assertFalse(win.hub.web_error.isVisible())

    def test_submission_actions_remain_available_on_all_subject_overviews(self):
        entries = mock.patch.object(study, "ENTRY_TRACKS", study.ENTRY_TRACKS + ("web",))
        entries.start()
        self.addCleanup(entries.stop)
        self.git.has_updates = True
        win = self.boot()
        bar = win.workspace.submissions
        for open_page in (win.go_home, win.go_journey, win.go_web, win.go_ai,
                          lambda: win.open_ai_lesson("i90"), win.go_hub):
            open_page()
            self.idle()
            guikit.wait_until(lambda: win.pending_job is None)
            self.assertTrue(bar.isVisible())
            self.assertTrue(bar.submit.isVisible())
            self.assertTrue(bar.sync.isVisible())
            self.assertTrue(win.rect().contains(bar.mapTo(win, QPoint(bar.width() - 1, bar.height() - 1))))
        win.open_ai_unit("i90", "90a")
        self.idle()
        self.assertFalse(bar.isVisible())

    def test_closing_during_submission_check_keeps_events_running(self):
        win = self.boot()
        guikit.wait_until(lambda: win.pending_job is None)
        win.pending_timer.stop()
        started, release = threading.Event(), threading.Event()

        def pending():
            started.set()
            release.wait(3)
            return {"status": "ok", "pending": False, "count": 0}

        self.git.pending = pending
        win.check_pending_submission()
        guikit.wait_until(started.is_set)
        try:
            win.close()
            self.assertTrue(win.isVisible())
            self.assertTrue(win.pending_close)
            guikit.pump()
            self.assertTrue(win.pending_job.isRunning())
        finally:
            release.set()
        guikit.wait_until(lambda: not win.isVisible())
        self.assertIsNone(win.pending_job)

    def test_first_open_places_all_four_subjects_in_the_grid(self):
        entries = mock.patch.object(study, "ENTRY_TRACKS", study.ENTRY_TRACKS + ("web",))
        entries.start()
        self.addCleanup(entries.stop)
        win = self.boot()
        grid = win.hub.tracks.grid
        self.assertEqual(grid.count(), 4)
        for row, expected in zip(win.hub.tracks.rows, ((0, 0), (0, 1), (1, 0), (1, 1))):
            self.assertEqual(grid.getItemPosition(grid.indexOf(row))[:2], expected)
            self.assertTrue(row.isVisible())
            self.assertGreater(row.geometry().width(), 100)
            self.assertTrue(win.hub.tracks.rect().contains(row.geometry()))

    def test_submission_notice_only_for_pending_changes_and_fixed_while_scrolling(self):
        from PyQt6.QtWidgets import QScrollArea
        win = self.boot()
        self.git.has_pending = False
        guikit.wait_until(lambda: win.pending_job is None)
        win.check_pending_submission()
        guikit.wait_until(lambda: win.pending_job is None)
        bar = win.workspace.submissions
        self.assertTrue(bar.submit.isHidden())
        self.assertTrue(bar.isHidden())
        self.assertTrue(bar.sync.isHidden())
        self.assertTrue(win.hub.manual_sync.isHidden())
        self.assertFalse(win.hub.manual_sync.isEnabled())
        page_geometry = win.pages.geometry()
        scroll = win.hub.findChild(QScrollArea).verticalScrollBar()
        scroll.setValue(scroll.maximum() // 2)
        position, maximum = scroll.value(), scroll.maximum()
        self.git.has_pending = True
        win.check_pending_submission()
        guikit.wait_until(lambda: win.pending_job is None)
        self.assertTrue(bar.submit.isVisible())
        self.assertTrue(win.hub.submission_setup.isVisible())
        self.assertEqual(bar.message.text(), "제출할 풀이가 있습니다.")
        self.assertTrue(bar.sync.isHidden())
        self.assertEqual(win.pages.geometry(), page_geometry)
        self.assertEqual((scroll.value(), scroll.maximum()), (position, maximum))
        before = bar.geometry()
        scroll.setValue(scroll.maximum())
        guikit.pump()
        self.assertEqual(bar.geometry(), before)
        self.assertTrue(bar.submit.isVisible())

    def test_new_material_reminder_is_throttled_and_clears_after_receiving(self):
        self.git.has_pending, self.git.has_updates = False, True
        win = self.boot()
        guikit.wait_until(lambda: win.pending_job is None)
        win.pending_timer.stop()
        bar = win.workspace.submissions
        self.assertTrue(bar.isVisible())
        self.assertTrue(bar.submit.isHidden())
        self.assertTrue(bar.sync.isVisible())
        self.assertTrue(win.hub.manual_sync.isVisible())
        self.assertEqual(win.hub.manual_sync.text(), "프로그램 업데이트")
        self.assertEqual(bar.message.text(), "새 업데이트가 있습니다.")
        checks = self.git.update_checks
        win.check_pending_submission()
        guikit.wait_until(lambda: win.pending_job is None)
        self.assertEqual(self.git.update_checks, checks)
        self.git.has_updates = False
        QTest.mouseClick(bar.sync, Qt.MouseButton.LeftButton)
        self.idle()
        guikit.wait_until(lambda: win.pending_job is None)
        self.assertIn("sync", self.git.calls)
        self.assertTrue(bar.isHidden())
        self.assertTrue(win.hub.manual_sync.isHidden())
        self.assertFalse(win.hub.manual_sync.isEnabled())

    def test_update_failure_keeps_a_known_reminder_and_retry_stays_available(self):
        self.git.has_pending, self.git.has_updates = False, True
        win = self.boot()
        guikit.wait_until(lambda: win.pending_job is None)
        win.pending_timer.stop()
        self.git.updates = lambda: {"status": "error", "available": False, "count": 0}
        win.next_update_check = 0
        win.check_pending_submission()
        guikit.wait_until(lambda: win.pending_job is None)
        self.assertTrue(win.workspace.submissions.sync.isVisible())
        self.assertTrue(win.hub.manual_sync.isEnabled())

    def test_manual_update_check_only_queries_and_preserves_known_updates_on_failure(self):
        self.git.has_pending, self.git.has_updates = False, False
        win = self.boot()
        guikit.wait_until(lambda: win.pending_job is None)
        win.pending_timer.stop()
        syncs = self.git.calls.count("sync")
        with mock.patch.object(win, "ask") as ask:
            for available in (False, True):
                self.git.has_updates = available
                checks = self.git.update_checks
                win.check_updates()
                self.idle()
                self.assertGreater(self.git.update_checks, checks)
                self.assertEqual(win.hub.manual_sync.isVisible(), available)
                self.assertEqual(win.hub.manual_sync.isEnabled(), available)
            self.git.updates = lambda: {"status": "error", "available": False, "count": 0}
            win.check_updates()
            self.idle()
            self.assertTrue(win.hub.manual_sync.isVisible())
            self.assertIn("확인하지 못했습니다", ask.call_args.args[1])
        self.assertEqual(self.git.calls.count("sync"), syncs)

    def test_conditional_header_actions_keep_content_position_and_release_hidden_focus(self):
        self.git.has_pending, self.git.has_updates = False, False
        win = self.boot()
        guikit.wait_until(lambda: win.pending_job is None)
        win.pending_timer.stop()
        win.resize(800, 700)
        win.set_text("larger")
        guikit.pump()
        hub = win.hub
        scroll = hub.scroll.verticalScrollBar()
        scroll.setValue(scroll.maximum() // 2)
        initial = (hub.top.height(), hub.scroll.geometry(), scroll.value())
        win.pending_submission = {"status": "ok", "pending": True, "count": 1}
        win.problem_updates = {"status": "ok", "available": True, "count": 1}
        win.workspace.refresh()
        guikit.pump()
        self.assertEqual((hub.top.height(), hub.scroll.geometry(), scroll.value()), initial)
        for button, state in ((hub.submission_setup, "pending_submission"), (hub.manual_sync, "problem_updates")):
            button.setFocus(Qt.FocusReason.TabFocusReason)
            setattr(win, state, {"status": "ok", "pending": False, "available": False, "count": 0})
            win.workspace.refresh()
            guikit.pump()
            self.assertTrue(button.isHidden())
            self.assertFalse(button.isEnabled())
            self.assertTrue(win.workspace.hasFocus())
            self.assertEqual((hub.top.height(), hub.scroll.geometry(), scroll.value()), initial)

    def test_hiding_a_keyboard_focused_reminder_keeps_the_reading_position(self):
        from PyQt6.QtWidgets import QScrollArea
        win = self.boot()
        guikit.wait_until(lambda: win.pending_job is None)
        win.pending_timer.stop()
        scroll = win.hub.findChild(QScrollArea).verticalScrollBar()
        scroll.setValue(scroll.maximum() // 2)
        win.workspace.submissions.submit.setFocus(Qt.FocusReason.TabFocusReason)
        guikit.pump()
        before = scroll.value()
        self.git.has_pending = False
        win.check_pending_submission()
        guikit.wait_until(lambda: win.pending_job is None)
        self.assertTrue(win.workspace.submissions.isHidden())
        self.assertTrue(win.workspace.hasFocus())
        self.assertEqual(scroll.value(), before)

    def test_subject_navigation_fits_a_small_window_at_the_largest_text_size(self):
        win = self.boot()
        # 첫 show에서 화면 크기에 맞춰 줄어든 창도 넓은 배치부터 대조함.
        win.resize(1280, 800)
        guikit.pump()
        self.assertTrue(win.workspace.rail.isVisible())
        self.assertEqual(win.hub.tracks.columns, 2)
        win.set_text("larger")
        win.resize(800, 800)
        guikit.pump()
        self.assertEqual(win.width(), 800)
        self.assertFalse(win.workspace.rail.isVisible())
        self.assertTrue(win.workspace.compact.isVisible())
        bar = win.workspace.submissions
        self.assertLessEqual(bar.submit.geometry().right(), bar.width())
        self.assertLessEqual(bar.sync.geometry().right(), bar.width())
        win.workspace.compact.activated.emit(1)
        guikit.pump()
        self.assertEqual((win.pages.currentWidget(), win.area), (win.home, "python"))

        # 배율 1.5의 1080p 화면에서도 창 전체가 보이는 높이로 같은 이동을 확인함.
        win.resize(800, 600)
        guikit.pump()
        self.assertEqual((win.width(), win.height()), (800, 600))
        self.assertTrue(win.workspace.compact.isVisible())
        self.assertLessEqual(bar.submit.geometry().right(), bar.width())
        self.assertLessEqual(bar.sync.geometry().right(), bar.width())
        win.workspace.compact.activated.emit(0)
        guikit.pump()
        self.assertEqual((win.pages.currentWidget(), win.area), (win.hub, "hub"))

    def test_starts_at_the_hub_and_the_rows_show_their_numbers(self):
        prof = self.graded_round()
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(timespec="seconds")
        later = datetime.datetime.combine(datetime.date.today(), datetime.time(23, 59, 59)).isoformat()  # 파이썬 채점보다 뒤, 같은 날의 여행 채점
        self.write_log([grade_entry("p1", at=yesterday), grade_entry("p1", at=later), grade_entry("p2", at=later),
                        grade_entry("p2", "javascript", at=later)])
        win = self.boot()
        hub = win.hub
        self.assertIs(self.page(), hub)
        self.assertEqual((win.area, win.windowTitle()), ("hub", "프로그래밍 스터디"))
        self.assertIn("프로그래밍 스터디", [label.text() for label in hub.findChildren(QLabel)])
        self.assertEqual(hub.user.text(), "ID: tester")
        self.assertTrue(hub.theme_buttons["system"].isChecked())

        # 파이썬 줄: 서비스가 낸 값을 그대로 보임
        overview = win.session.overview()
        self.assertEqual(hub.python_row.second.text(), "다음은 2회차")
        self.assertEqual(hub.python_row.metric.text(), "숙달 단원 %d / %d" % (overview["mastered"], overview["total_units"]))

        # 여행 줄: 1-1·1-2 를 통과해 보스가 열리고 다음은 보스
        self.assertEqual(hub.journey_row.second.text(), "다음은 물통 정리")
        self.assertEqual(hub.journey_row.metric.text(), "통과한 문제 2 / 4")
        self.assertFalse(hub.journey_row.inert)
        self.assertFalse(hub.journey_error.isVisible())

        # 이어서 할 일: 웹에 진행 중인 것이 없고 가장 최근 기록이 여행이라 여행의 다음 문제. 주 단추는 화면에 하나
        self.assertEqual((hub.next_card.title.text(), hub.next_card.line.text(), hub.next_btn.text()),
                         ("물통 정리", "알고리즘 여행 · 던전 1 「시험 마을」", "문제 풀기"))
        self.assertEqual(len(kit.visible_primary_buttons(hub)), 1)
        self.assertEqual(hub.summary.text(), "공부할 과목을 고르거나 이어서 진행하세요.")

        # 막대: 25문항 회차를 한 번 채점한 날의 파이썬 값은 1, 여행은 채점 기록 수, 웹은 기록이 없어 0. 어제도 여행 채점이 있어 연속 2일
        today = datetime.date.today()
        self.assertEqual(len([a for a in prof["attempts"] if a["round"] == "r1"]), 25)
        self.assertEqual(hub.chart.days[-1], (today, 1, 3, 0, 0))  # 파이썬, 알고리즘, 웹, AI
        self.assertEqual(hub.chart.days[-2], (today - datetime.timedelta(days=1), 0, 1, 0, 0))
        self.assertEqual(len(hub.chart.days), 7)
        self.assertEqual((hub.streak.text(), hub.total.text()), ("연속 학습 2일", "기록된 활동 5회"))
        self.assertTrue(hub.recent_box.isVisible())
        self.assertEqual(len(hub.recent.rows), 5)  # 다섯 줄까지. 줄마다 (무엇을 채점했는지, 시각)
        labels, stamps = zip(*hub.recent.rows)
        self.assertIn("1-2 JavaScript 100점", labels)
        last = [r for r in overview["rounds"] if r["completed"]][-1]
        self.assertIn("파이썬 스터디 %s" % last["title"], labels)
        self.assertTrue(all(stamp.startswith("%d/%d " % (today.month, today.day)) for stamp in stamps[:4]), stamps)

        # 이어서 할 일의 단추는 그 문제를 바로 엶
        guikit.click(hub.next_btn)
        self.idle()
        self.assertEqual((self.page(), win.journey_page.pid), (win.journey_page, "boss"))

    def test_sections_stack_and_each_uses_the_whole_column(self):
        """공부 트랙, 오답 노트, 최근 7일 학습은 위아래로 쌓이고 저마다 가운데 단의 폭을 다 씀. 최근 7일 카드 안에서는 폭이 넉넉하면
        막대 칸(범례 줄과 막대) 오른쪽에 최근 채점이 오고(막대가 더 넓음), 좁으면 막대 아래로 내려감."""
        self.graded_round()
        win = self.boot()
        hub = win.hub
        parts = (hub.tracks, hub.notes, hub.week_card)
        tops = [part.mapTo(hub, QPoint(0, 0)) for part in parts]
        for upper, top in zip(parts, tops[1:]):
            self.assertLess(upper.mapTo(hub, QPoint(0, upper.height())).y(), top.y())
        self.assertEqual({top.x() for top in tops}, {tops[0].x()})
        self.assertEqual(len({part.width() for part in parts}), 1)
        self.assertLessEqual(parts[0].width(), kit.HOME_WIDTH)
        second = hub.python_row.second
        self.assertGreaterEqual(second.height(), second.heightForWidth(second.width()))  # 트랙 설명이 줄바꿈한 높이만큼 다 보임
        week = hub.week
        self.assertTrue(week.side)
        chart, recent = week.plot.geometry(), week.recent_box.geometry()
        self.assertEqual(chart.top(), recent.top())
        self.assertGreater(recent.left(), chart.right())
        self.assertGreater(chart.width(), recent.width())
        total = hub.total.mapTo(week, QPoint(hub.total.width(), 0)).x()  # 채점 수는 막대 칸 오른쪽 끝에 맞아 최근 채점 칸 위로 가지 않음
        self.assertEqual(total, hub.chart.mapTo(week, QPoint(hub.chart.width(), 0)).x())
        self.assertLess(total, recent.left())
        self.assertGreaterEqual(recent.width(), hub.recent.natural_width())  # 최근 채점 줄이 다 보임
        week.resize(560, week.height())  # 좁으면 막대 아래로 내려가고 폭을 다 씀
        self.assertFalse(week.side)
        self.assertEqual(week.row.direction(), week.row.Direction.TopToBottom)
        self.assertEqual(week.recent_box.maximumWidth(), hub_page.QWIDGETSIZE_MAX)
        win.set_text("larger")
        guikit.pump()
        self.assertTrue(week.side)
        self.assertEqual(week.recent_box.width(), min(hub.recent.natural_width(), int((week.width() - hub_page.SIDE_GAP) * hub_page.RECENT_SHARE)))

    def test_wrong_note_row_opens_the_notes_and_comes_back(self):
        """오답 노트 구역의 줄은 트랙마다 하나이고 갈래별 문항 수를 보임. 누르면 오답 노트가 그 트랙으로 열리고 돌아가기는 첫 화면으로 감."""
        self.graded_round()  # 아무것도 적지 않고 제출해 25문항이 모두 미응답
        win = self.boot()
        hub = win.hub
        self.assertEqual([(row.title.text(), row.second.text()) for _, row in hub.note_rows], [("파이썬 스터디", "미응답 문항 25개"), ("AI", "개론 · 아직 틀린 문항이 없습니다.")])
        row = hub.note_rows[0][1]
        guikit.click(row)
        page = win.wrong_page
        self.assertEqual((self.page(), win.area, page.track.tid, page.back_btn.text()), (page, "hub", "python", "← 처음 화면"))
        self.assertEqual([(fold.title.text(), fold.count.text(), fold.opened) for fold in page.list.folds], [("미응답 문항", "25", True)])
        self.assertEqual(page.selected()["key"], page.list.rows[0].data["key"])
        guikit.click(page.back_btn)
        self.assertEqual((self.page(), win.area), (hub, "hub"))
        hub.set_busy(True, "확인 중입니다.")
        self.assertTrue(row.inert)
        hub.set_busy(False)
        self.assertFalse(row.inert)

    def test_next_card_prefers_python_when_nothing_was_graded(self):
        win = self.boot()
        hub = win.hub
        self.assertEqual((hub.next_card.title.text(), hub.next_btn.text()), ("진단 테스트", "시작"))
        self.assertTrue(hub.next_card.line.text().startswith("파이썬 스터디 · "), hub.next_card.line.text())
        guikit.click(hub.next_btn)
        self.idle()
        self.assertEqual((self.page(), win.area), (win.round_page, "python"))

    def test_journey_next_starts_from_the_last_opened_problem(self):
        """설정 journey/last 의 문제가 아직 통과 전이고 열 수 있으면 여행 줄과 이어서 할 일이 그 문제를 말함. 다른 던전의 문제도
        같음. 은행에 없는 문제, 읽지 못한 던전, 통과한 문제, 잠긴 보스를 가리키면 서비스 추천으로 돌아감."""
        root = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, root)
        shutil.copytree(os.path.join(root, "t01"), os.path.join(root, "t03"))  # 준비된 던전을 하나 더 둠
        patcher = mock.patch.object(bank, "BANK_DIR", root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.write_log([grade_entry("p1")])
        self.settings.setValue("journey/last", "t03/p1")
        win = self.boot()
        hub = win.hub
        self.assertEqual(hub.journey_row.second.text(), "다음은 물통 합계")
        self.assertEqual(hub.journey_row.metric.text(), "통과한 문제 1 / 8")
        self.assertEqual((hub.next_card.title.text(), hub.next_card.line.text(), hub.next_btn.text()),
                         ("물통 합계", "알고리즘 여행 · 던전 3 「준비 중 던전 3」", "문제 풀기"))
        guikit.click(hub.journey_row)
        self.idle()
        page = win.journey_map
        self.assertEqual((self.page(), page.view.selected), (page, "t03"), "지도도 첫 화면이 말한 던전을 고름")
        self.assertEqual((page.next_card.title.text(), page.next_card.line.text()), ("물통 합계", "던전 3 「준비 중 던전 3」 · 기초"))
        guikit.click(page.home_btn)
        guikit.click(hub.next_btn)
        self.idle()
        self.assertEqual((self.page(), win.journey_page.did, win.journey_page.pid), (win.journey_page, "t03", "p1"))
        guikit.click(win.journey_page.map_btn)
        guikit.click(win.journey_map.home_btn)
        self.assertIs(self.page(), hub)
        self.assertEqual(hub.next_card.line.text(), "알고리즘 여행 · 던전 3 「준비 중 던전 3」")
        for last in ("t01/p9", "t02/p1", "t01/p1", "t01/boss"):
            self.settings.setValue("journey/last", last)
            hub.refresh()
            self.assertEqual((hub.journey_row.second.text(), hub.next_card.title.text(), hub.next_card.line.text()),
                             ("다음은 가장 큰 물통", "가장 큰 물통", "알고리즘 여행 · 던전 1 「시험 마을」"), last)
            win.journey_map.refresh()
            self.assertEqual((win.journey_map.view.selected, win.journey_map.next_card.title.text()), ("t01", "가장 큰 물통"), last)

    def test_rows_move_between_the_areas_and_the_theme_button_names_the_next_mode(self):
        win = self.boot()
        hub = win.hub
        guikit.click(hub.python_row)
        self.assertEqual((self.page(), win.area), (win.home, "python"))
        guikit.click(win.home.hub_btn)
        self.assertEqual((self.page(), win.area), (hub, "hub"))
        QTest.mouseClick(hub.python_row, guikit.LEFT, pos=QPoint(8, hub.python_row.height() - 8))  # 줄의 빈 곳을 눌러도 들어감
        guikit.pump()
        self.assertIs(self.page(), win.home)
        guikit.click(win.home.hub_btn)
        QTest.mouseClick(hub.journey_row, guikit.LEFT, pos=QPoint(8, hub.journey_row.height() - 8))
        guikit.pump()
        self.assertEqual((self.page(), win.area), (win.journey_map, "journey"))
        page = self.open_problem("p1")
        self.assertEqual((page.did, page.pid), ("t01", "p1"))
        self.assertEqual(self.settings.value("journey/last"), "t01/p1")
        guikit.click(page.map_btn)
        self.assertIs(self.page(), win.journey_map)
        guikit.click(win.journey_map.home_btn)
        self.assertEqual((self.page(), win.area), (hub, "hub"))
        self.addCleanup(theme.set_mode, "system")
        guikit.click(hub.settings_btn)
        guikit.click(hub.theme_buttons["light"])
        guikit.pump(400)
        self.assertEqual(theme.state["mode"], "light")
        self.assertTrue(hub.theme_buttons["light"].isChecked())
        guikit.click(hub.theme_buttons["dark"])
        guikit.pump(400)
        self.assertEqual(theme.state["mode"], "dark")
        self.assertTrue(hub.theme_buttons["dark"].isChecked())
        self.assertEqual(len(kit.visible_primary_buttons(hub)), 1)

    def test_hub_submit_writes_unsaved_journey_code_first(self):
        win = self.boot()
        self.assertTrue(win.hub.git_btn.isEnabled())
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
        win.hub.git_btn.clicked.emit()
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

        guikit.click(win.hub.journey_row)
        fetch()
        self.assertEqual((self.page(), win.area), (win.journey_map, "journey"))
        page = self.open_problem("p2")
        fetch()
        self.assertEqual((self.page(), page.pid), (page, "p2"))  # 같은 문제를 다시 읽음
        guikit.click(page.map_btn)
        guikit.click(win.journey_map.home_btn)
        guikit.click(win.hub.python_row)
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
        for language in ("python", "javascript"):
            win.settings.setValue("journey/lang", language)
            with mock.patch.object(win, "ask") as ask:
                win.go_journey()
                ask.assert_called_once()
                self.assertIn("progress.json", ask.call_args.args[1])
            self.assertIs(self.page(), hub)
        self.assertTrue(hub.journey_error.isVisible())
        self.assertIn("progress.json", hub.journey_error.text.text())
        self.assertIn("파일을 고친 뒤 프로그램을 다시 실행해 주세요.", hub.journey_error.text.text())
        self.assertTrue(hub.journey_row.inert)
        self.assertEqual(hub.journey_row.second.text(), "기록을 읽지 못했습니다.")
        guikit.click(hub.journey_row)
        self.assertIs(self.page(), hub)  # 꺼진 줄은 눌러도 그대로
        self.assertEqual(hub.chart.days[-1][2], 0)
        self.assertFalse(hub.recent_box.isVisible())  # 채점 기록이 없으면 최근 채점 칸을 빼고 막대만 보임
        self.assertFalse(hub.git_hint.isVisible())
        guikit.click(hub.python_row)
        self.assertIs(self.page(), win.home)
        self.assertEqual(win.home.action_btn.text(), "진단 테스트 시작")
        guikit.click(win.home.hub_btn)
        hub.set_busy(True, "확인 중입니다.")
        self.assertTrue(hub.python_row.inert and not hub.git_btn.isEnabled() and not hub.next_btn.isEnabled())
        hub.set_busy(False)
        self.assertFalse(hub.python_row.inert or not hub.git_btn.isEnabled())
        self.assertTrue(hub.journey_row.inert)  # 잠금이 풀려도 여행 줄은 꺼진 채로 남음

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

    def test_leaving_after_a_failed_save_keeps_the_raw_error_in_details(self):
        """코드를 저장하지 못한 채 문제 화면을 떠나면 묻는 창의 본문은 쉬운 글이고 원문(errno, 경로)은 [자세히]에만 있음."""
        win = self.boot()
        win.open_problem("t01", "p1")
        self.idle()
        page = win.journey_page
        page.on_code_changed("def solution(nums):\n    return 0\n")
        failure = "코드를 저장하지 못했습니다: [Errno 13] 권한 없음: '/home/alice/journey/t01/p1.py'"
        with mock.patch.object(win.journey, "save_code", side_effect=JourneyError(failure)):
            guikit.click(page.map_btn)
        self.assertEqual("저장하지 못한 코드", win.dialog.windowTitle())
        self.assertNotIn("Errno", win.dialog.text.text())
        self.assertNotIn("t01", win.dialog.text.text())
        self.assertIn("[Errno 13]", win.dialog.detail.toPlainText())
        self.choose("drop")
        self.idle()
        self.assertIs(self.page(), win.journey_map)

    def test_job_without_progress_is_called_with_no_arguments(self):
        win = self.boot()
        done = []
        win.run_job("인자 없는 일", lambda: "끝", done.append)
        self.idle()
        self.assertEqual(done, ["끝"])

    def test_a_problem_that_cannot_open_names_the_action(self):
        win = self.boot()
        win.open_problem("t01", "boss")
        self.assertIs(self.page(), win.hub)
        self.assertEqual("문제 열기", win.dialog.windowTitle())
        self.assertEqual("보스 문제는 중급 문제를 통과하면 열립니다.", win.dialog.text.text(), "지도 목록 줄과 같은 말")
        win.dialog.close()
        win.open_problem("t01", "p9")
        self.assertEqual(("문제 열기", "이 문제의 파일을 읽지 못했습니다. 프로그램을 다시 실행해 문제를 다시 받으세요."),
                         (win.dialog.windowTitle(), win.dialog.text.text()))
        self.assertIn("t01/p9", win.dialog.detail.toPlainText(), "내부 id 는 자세히에만 남음")

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
        entries = mock.patch.object(study, "ENTRY_TRACKS", study.ENTRY_TRACKS + ("web",))
        entries.start()
        self.addCleanup(entries.stop)
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
        guikit.click(win.hub.journey_row)
        self.idle()
        self.assertIs(self.page(), win.journey_map)
        self.assertEqual("javascript", win.journey_map.lang_bar.lang)
        page = self.open_problem("p1")
        self.assertEqual("javascript", page.lang)
        self.assertEqual([False], self.threads["search"], "한 번 찾은 결과를 기억하고, 찾기는 워커에서만 함")

    def test_javascript_button_and_node_path_are_checked_in_the_worker(self):
        win = self.boot()
        guikit.click(win.hub.journey_row)
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

    def test_a_picked_file_that_is_not_node_reopens_the_node_window(self):
        win = self.boot()
        guikit.click(win.hub.journey_row)
        page = win.journey_map
        guikit.click(page.lang_btns["javascript"])
        self.idle()
        win.pick_file = lambda title: "/opt/old/node"
        with mock.patch.object(node, "check", side_effect=ValueError("Node.js 20 이상이 필요한데 이 파일은 18.0.0 입니다.")):
            self.choose("pick")
            self.idle()
        self.assertEqual(NODE_TITLE, win.dialog.windowTitle(), "창의 일반 알림 대신 같은 Node 창")
        self.assertEqual("Node.js 20 이상이 필요한데 이 파일은 18.0.0 입니다. " + NODE_RETRY, win.dialog.text.text(), "필요한 버전을 두 번 말하지 않음")
        self.assertEqual("python", page.lang_bar.lang)
        self.assertFalse(self.settings.value("journey/node"))


if __name__ == "__main__":
    unittest.main()
