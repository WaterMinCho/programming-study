# -*- coding: utf-8 -*-
"""화면 테스트. 창을 화면에 내보내지 않고(offscreen) 위젯을 직접 눌러 처음 실행부터 다시 채점까지 돌려 봄.

실제 문제 은행을 쓰되 풀이 폴더는 임시 폴더로 돌리고, 제출 모듈은 가짜를 끼움. PyQt6 가 없으면 전부 건너뜀.
실행: python -m unittest discover -s tests
"""
import contextlib
import io
import itertools
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

try:
    from PyQt6.QtCore import QEvent, QEventLoop, QMimeData, QPoint, QPointF, QSettings, Qt, QTimer, qInstallMessageHandler
    from PyQt6.QtGui import (QColor, QContextMenuEvent, QDragEnterEvent, QDropEvent, QFontDatabase, QGuiApplication, QInputMethodEvent,
                             QFontMetricsF, QKeyEvent, QKeySequence, QTextCursor, QTextDocument, qGray)
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QListWidget, QPushButton, QWidget
except ImportError:
    raise unittest.SkipTest("PyQt6 가 설치돼 있지 않아 화면 테스트를 건너뜁니다")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adaptive  # noqa: E402
import mdlite  # noqa: E402
import session  # noqa: E402
import study  # noqa: E402
from gui import app, dialogs, errors, icon, motion, theme, widgets  # noqa: E402
from gui.mascot import Mascot  # noqa: E402
from gui.guard import NOTE as PASTE_NOTE  # noqa: E402
from gui.team_page import Avatar, EmptyCard, MemberCard  # noqa: E402
from gui.round_page import ROW_GAP  # noqa: E402
from gui.widgets import ChoiceCard, ChoicePanel, CodeEditor, Para, TextPanel, content_height  # noqa: E402
from gui.window import MainWindow  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
NOISE = ("propagateSizeHints", "Populating font family aliases")  # offscreen 플랫폼이 창을 띄울 때마다 찍는 안내
qInstallMessageHandler(lambda mode, context, text: None if any(n in text for n in NOISE) else print(text, file=sys.stderr))
APP = QApplication.instance() or QApplication(sys.argv[:1])
theme.apply(APP)
motion.enabled = False  # 움직임은 MotionTest 에서만 켬
LEFT = Qt.MouseButton.LeftButton
SHIFT = Qt.KeyboardModifier.ShiftModifier
CTRL = Qt.KeyboardModifier.ControlModifier


def pump(ms=30):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_until(predicate, timeout=30.0):
    start = time.monotonic()
    while not predicate():
        if time.monotonic() - start > timeout:
            raise TimeoutError("화면이 기다리던 상태가 되지 않았습니다")
        pump(20)


def click(widget):
    QTest.mouseClick(widget, LEFT)
    pump()


def gray(value):
    """색의 밝기(0~255)."""
    return qGray(QColor(value).rgb())


def contrast(ink, back):
    """글자색과 바탕색의 대비(WCAG 2 의 계산식)."""
    def luminance(value):
        color = QColor(value)
        red, green, blue = (v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in (color.redF(), color.greenF(), color.blueF()))
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue
    low, high = sorted((luminance(ink), luminance(back)))
    return (high + 0.05) / (low + 0.05)


def backgrounds(text):
    """스타일시트나 HTML 에 적힌 바탕색. Qt 는 표 칸의 바탕색을 bgcolor 속성으로 내보냄."""
    return re.findall(r"(?:background(?:-color)?:\s*|bgcolor=\")(#[0-9a-fA-F]{6})", text)


def bright_share(widget):
    """위젯에서 밝은 바탕이 차지하는 비율. 찍은 그림을 가로세로 8분의 1로 줄여 밝은 칸이 가로로 6칸(48px) 넘게 이어진 곳만 셈.
    글자는 줄어들며 바탕과 섞이고 굵은 획도 그만큼 이어지지 않아서, 밝은 글자는 빠지고 밝은 바탕만 남음."""
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
    """제출 모듈처럼 예외 없이 dict 를 돌려주는 가짜. replies 에 메서드별 응답을 넣어 상황을 만듦."""

    def __init__(self):
        self.calls, self.replies, self.delay = [], {}, 0

    def _reply(self, name):
        self.calls.append(name)
        time.sleep(self.delay)
        base = {"status": "nothing", "message": "", "detail": "", "pr_url": None, "restart": False, "changed": False, "backup": None}
        return dict(base, **self.replies.get(name.split(":")[0], {}))

    def sync(self):
        return self._reply("sync")

    def submit(self):
        return self._reply("submit")

    def resolve(self, choice):
        return self._reply("resolve:" + choice)


def right_answer(sess, view):
    it = sess.cat[view["key"]]
    if it["kind"] == "quiz":
        q = it["q"]
        return q["answer"] if q["type"] != "short" else q["answer"][0]
    return it["set"]["secrets"][it["spec"]["id"] + "/solution.py"]


class GuiTest(unittest.TestCase):
    user = "tester"  # None 이면 처음 실행이라 ID 를 물음
    git_reason = ""  # 채우면 제출 모듈을 불러오지 못한 상황
    expect_error = False  # 오류 대화상자가 뜨는 것이 정상인 테스트

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="study_gui_")
        self._saved = (study.SUBMISSIONS_DIR, study.USER_FILE, os.environ.pop("STUDY_USER", None), sys.excepthook)
        study.SUBMISSIONS_DIR = os.path.join(self.tmp, "submissions")
        study.USER_FILE = os.path.join(self.tmp, ".study_user")
        self.logs = os.path.join(self.tmp, ".study_logs")
        errors.install(self.logs)
        if self.user:
            session.save_user(self.user)
        self.git, self.opened = FakeGitFlow(), []
        self.settings = QSettings(os.path.join(self.tmp, "settings.ini"), QSettings.Format.IniFormat)
        self.win = MainWindow(self.settings, lambda root, user: (None if self.git_reason else self.git, self.git_reason))
        self.win.open_url = self.opened.append
        self.win.show()

    def tearDown(self):
        wait_until(lambda: self.win.job is None)
        self.win.close()
        self.win.deleteLater()
        pump()
        crashed = os.path.isdir(self.logs) and not self.expect_error  # 슬롯 안의 예외는 테스트로 올라오지 않고 기록만 남음
        report = "".join(study.read_text(os.path.join(self.logs, name)) for name in os.listdir(self.logs)) if crashed else ""
        if errors.state["dialog"] is not None:
            errors.state["dialog"].close()
        study.SUBMISSIONS_DIR, study.USER_FILE, user, sys.excepthook = self._saved
        if user is not None:
            os.environ["STUDY_USER"] = user
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.assertFalse(crashed, report)

    # 도우미

    def idle(self):
        pump()
        wait_until(lambda: self.win.job is None)
        pump()

    def boot(self):
        self.win.boot()
        self.idle()

    def page(self):
        return self.win.pages.currentWidget()

    def choose(self, key):
        """떠 있는 대화상자에서 버튼을 누름."""
        dialog = self.win.dialog
        self.assertTrue(dialog.isVisible())
        click(dialog.buttons[key])
        return dialog

    def select(self, predicate):
        """회차 화면에서 조건에 맞는 첫 문항으로 감."""
        page = self.win.round_page
        item = next(it for it in page.view["items"] if predicate(it))
        page.listw.setCurrentRow(item["no"] - 1)
        pump()
        self.assertIs(page.current, item)
        return item

    def fill(self, item, value):
        """지금 보이는 문항에 위젯으로 답을 넣음."""
        page = self.win.round_page
        if item["kind"] == "code":
            page.code_panel.editor.setPlainText(value)
        elif item["type"] == "choice":
            for number, button in enumerate(page.choice_panel.buttons, 1):
                if button.isChecked() != (number in value):
                    click(button)
        elif item["type"] == "output":
            page.text_panel.multi.setPlainText(value)
        else:
            page.text_panel.single.setText(value)

    def answer_round(self, skip=()):
        """정답을 위젯으로 넣음. skip 의 번호는 비워 둠."""
        page = self.win.round_page
        for item in list(page.view["items"]):
            if item["no"] not in skip:
                self.select(lambda it: it is item)
                self.fill(item, right_answer(self.win.session, item))

    def make_round(self, rid, keys, completed=False):
        """진단·회차는 무작위라 유형이 빠질 수 있어, 고른 문항으로 회차를 직접 만듦."""
        sess = self.win.session
        rnd = {"id": rid, "kind": "round", "focus": [], "items": keys, "retest": [], "shortages": [], "created": adaptive.now(),
               "tries": 0, "avg_level": 1}
        if completed:
            rnd.update(completed_at=adaptive.now(), score="0/0", first_score="0/0", results={key: "skipped" for key in keys})
        sess.prof["rounds"].append(rnd)
        adaptive.write_round("tester", rnd, sess.cat)
        adaptive.save_profile(sess.prof)

    def saved_quiz(self, rid):
        return study.parse_quiz_answers(os.path.join(self.win.session.folder(rid), "quiz.py"))[0]

    def submit_round(self):
        click(self.win.round_page.submit_btn)
        dialog = self.choose("submit")
        self.idle()
        return dialog

    def attempts(self):
        return adaptive.load_profile("tester")["attempts"]

    def first(self, **want):
        """조건에 맞는 은행의 첫 문항 키."""
        cat = self.win.session.cat
        multi = want.pop("multi", None)
        return next(key for key in sorted(cat, key=study.natural_key)
                    if all(cat[key][name] == value for name, value in want.items())
                    and (multi is None or (len(cat[key]["q"]["answer"]) > 1) == multi))


class FirstRunTest(GuiTest):
    user = None

    def test_from_first_run_to_regrade(self):
        win, home, page, result = self.win, self.win.home, self.win.round_page, self.win.result_page

        # 처음 실행: ID 를 묻고 형식을 검사한 뒤 새 문제부터 받음
        win.boot()
        dialog = win.dialog
        self.assertTrue(dialog.isVisible())
        self.assertFalse(dialog.ok.isEnabled())
        QTest.keyClicks(dialog.edit, "a b")
        self.assertFalse(dialog.ok.isEnabled())
        self.assertIn("영문", dialog.error.text())
        dialog.edit.clear()
        QTest.keyClicks(dialog.edit, "tester")
        click(dialog.ok)
        self.idle()
        self.assertEqual(session.saved_user(), "tester")
        self.assertEqual(self.git.calls, ["sync"])
        self.assertIs(self.page(), home)
        self.assertEqual(home.action_btn.text(), "진단 테스트 시작")
        self.assertEqual(home.ready.text(), "0%")
        self.assertEqual(home.strip.cells.count(), len(adaptive.units()))
        first_unit = adaptive.units()[0]
        self.assertEqual(home.strip.cells.itemAt(0).widget().toolTip(),
                         "%s %s\n미진단" % (first_unit["id"], adaptive.short_title(first_unit)))

        # 진단 시작 → 문항 목록
        click(home.action_btn)
        self.assertIs(self.page(), page)
        self.assertEqual(page.view["id"], "d1")
        self.assertEqual(page.listw.count(), len(page.view["items"]))
        self.assertFalse(page.run_btn.isVisible())
        self.assertFalse(page.banner.isVisible())

        # 객관식: 하나만 선택되고 다시 누르면 풀림
        choice = self.select(lambda it: it["type"] == "choice" and not it["multi"])
        buttons = page.choice_panel.buttons
        self.assertEqual(len(buttons), choice["choices"])
        click(buttons[0])
        click(buttons[1])
        self.assertEqual([b.isChecked() for b in buttons[:2]], [False, True])
        self.assertTrue(page.listw.item(choice["no"] - 1).data(Qt.ItemDataRole.UserRole))  # 목록의 동그라미가 채워짐
        click(buttons[1])
        self.assertFalse(any(b.isChecked() for b in buttons))
        self.assertFalse(page.listw.item(choice["no"] - 1).data(Qt.ItemDataRole.UserRole))
        click(buttons[1])
        pump(save_delay())  # 다른 문항으로 가지 않아도 잠시 뒤 저장됨
        self.assertEqual(self.saved_quiz("d1")[choice["id"]], 2)

        # 정답으로 채우되 두 문항은 비워 둠 → 확인 대화상자가 번호를 보여 줌
        self.answer_round(skip={2, 5})
        self.select(lambda it: it["no"] == 2)
        self.fill(page.current, [] if page.current["type"] == "choice" else "")
        self.select(lambda it: it["no"] == 5)
        self.fill(page.current, [] if page.current["type"] == "choice" else "")
        click(page.submit_btn)
        self.assertIn("미응답 문항: 2, 5번", win.dialog.text.text())
        self.assertIn("미응답은 오답으로 처리됩니다", win.dialog.text.text())
        self.choose("")  # 계속 풀기
        self.idle()
        self.assertIs(self.page(), page)
        self.assertEqual(self.attempts(), [])
        self.submit_round()

        # 결과: 점수 · 준비도 · 문항별 결과 · 해설
        size = len(page.view["items"])
        self.assertIs(self.page(), result)
        self.assertEqual(len(self.attempts()), size)
        self.assertEqual(sum(1 for a in self.attempts() if a["ok"]), size - 2)
        self.assertEqual(result.listw.count(), size + 1)
        self.assertIn("진단 테스트 결과", result.title.text())
        self.assertNotEqual(result.ready.text(), "시험 준비도 0%")
        self.assertIn("미응답 2문항", result.detail.toPlainText())
        self.assertFalse(result.explain_btn.isEnabled())
        result.listw.setCurrentRow(2)  # 비워 둔 2번
        self.assertIn("미응답", result.listw.item(2).text())
        self.assertIn("내 답", result.detail.toPlainText())
        self.assertNotIn("해설", result.detail.toPlainText())
        self.assertTrue(result.retry_btn.isEnabled())
        click(result.explain_btn)
        quiz = result.selected()
        info = win.session.explain("d1", quiz["id"])
        self.assertIn("정답", result.detail.toPlainText())
        self.assertIn(info["explain"].replace("`", "").replace("**", "")[:12], result.detail.toPlainText())
        result.listw.setCurrentRow(1)
        self.assertFalse(result.retry_btn.isEnabled())  # 맞힌 문항

        # 다음 회차: 코드 문항에서 코드 입력 → 코드 실행(기록 없음)
        self.assertEqual(result.next_btn.text(), "1회차 시작")
        click(result.next_btn)
        self.assertEqual(page.view["id"], "r01")
        code = self.select(lambda it: it["kind"] == "code")
        self.assertTrue(page.run_btn.isVisible())
        self.assertEqual(page.code_panel.editor.toPlainText(), code["starter"])
        before = len(self.attempts())
        self.fill(code, right_answer(win.session, code))
        click(page.run_btn)
        self.assertFalse(page.stack.isEnabled())  # 실행 중에는 입력을 잠금
        self.idle()
        self.assertTrue(page.stack.isEnabled())
        self.assertIn("통과", page.code_panel.console.toPlainText())
        self.assertIn("기록되지 않습니다", page.code_panel.console.toPlainText())
        self.assertEqual(study.read_text(os.path.join(win.session.folder("r01"), code["id"] + ".py")).rstrip("\n"),
                         right_answer(win.session, code).rstrip("\n"))
        self.assertEqual(len(self.attempts()), before)

        # 1회차 제출 → 단원별 판정과 코드 문제 해설(모범 답안)
        self.answer_round(skip={1})
        self.submit_round()
        self.assertIs(self.page(), result)
        self.assertIn("1회차", result.title.text())
        self.assertIn("판정", result.detail.toPlainText())
        self.assertIn("레벨", result.detail.toPlainText())
        result.listw.setCurrentRow(code["no"])
        click(result.explain_btn)
        self.assertIn("모범 답안", result.detail.toPlainText())
        self.assertIn(win.session.explain("r01", code["id"])["solution"].split("\n")[0], result.detail.toPlainText())

        # 홈: 준비도와 지난 회차 목록
        click(result.home_btn)
        self.assertIs(self.page(), home)
        self.assertEqual(home.rounds.count(), 2)
        self.assertIn("진단 테스트", home.rounds.item(1).text())
        self.assertEqual(home.action_btn.text(), "2회차 시작")
        self.assertNotEqual(home.ready.text(), "0%")
        self.assertIn("정답률", home.strip.cells.itemAt(0).widget().toolTip())

        # 지난 회차를 눌러 결과 보기 → 틀린 문항 다시 풀기 → 다시 채점(연습)
        QTest.mouseClick(home.rounds.viewport(), LEFT, pos=home.rounds.visualItemRect(home.rounds.item(1)).center())
        pump()
        self.assertIs(self.page(), result)
        self.assertEqual(result.view["id"], "d1")
        old_score = result.score.text()
        result.listw.setCurrentRow(2)
        click(result.retry_btn)
        self.assertIs(self.page(), page)
        self.assertTrue(page.banner.isVisible())
        self.assertIn("첫 제출만 반영", page.banner.text())
        self.assertEqual(page.submit_btn.text(), "다시 채점")
        self.assertEqual(page.current["no"], 2)
        tried = len(self.attempts())
        self.fill(page.current, right_answer(win.session, page.current))
        click(page.submit_btn)
        self.idle()
        self.assertIs(self.page(), result)
        self.assertNotEqual(result.score.text(), old_score)
        self.assertIn("첫 제출", result.note.text())
        again = self.attempts()[tried:]
        self.assertEqual([(a["round"], a["try"], a["ok"]) for a in again], [("d1", 2, True)])
        rnd = adaptive.find_round(adaptive.load_profile("tester"), "d1")
        self.assertNotEqual(rnd["score"], rnd["first_score"])

    def test_id_box_accepts_paste(self):
        self.win.boot()
        dialog = self.win.dialog
        QGuiApplication.clipboard().setText("tester")
        QTest.keyClick(dialog.edit, Qt.Key.Key_V, CTRL)
        self.assertEqual(dialog.edit.text(), "tester")
        click(dialog.ok)
        self.idle()
        self.assertEqual(session.saved_user(), "tester")

    def test_id_that_already_has_a_record_is_confirmed_once(self):
        """이미 풀이 기록이 있는 ID 를 넣으면 한 번 확인받고, 대소문자가 달라도 그 폴더의 철자로 이어 감."""
        session.Session("Tester").ensure_round()
        self.win.boot()
        dialog = self.win.dialog
        self.assertNotIn("WaterMinCho", dialog.edit.placeholderText())  # 예시가 실제 ID 면 그대로 넣는 사람이 생김
        QTest.keyClicks(dialog.edit, "tester")
        click(dialog.ok)
        self.assertTrue(dialog.isVisible())  # 아직 저장하지 않음
        self.assertIsNone(session.saved_user())
        self.assertIn("Tester 의 풀이 기록", dialog.error.text())
        self.assertEqual(dialog.ok.text(), "이 기록으로 시작")
        for label in dialog.findChildren(QLabel):  # 안내가 두 줄로 늘어도 위의 설명이 눌려 잘리지 않음
            self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()), label.text())
        click(dialog.ok)
        self.idle()
        self.assertEqual(session.saved_user(), "Tester")
        self.assertEqual(self.win.home.user.text(), "ID: Tester")
        self.assertEqual(self.win.home.action_btn.text(), "진단 테스트 시작")
        self.assertEqual(os.listdir(study.SUBMISSIONS_DIR), ["Tester"])


class HomeAndGitTest(GuiTest):
    def test_offline_at_start_is_one_line_notice_and_work_continues(self):
        self.git.replies["sync"] = {"status": "offline", "message": "인터넷에 연결되지 않아 새 문제를 받지 못했습니다.", "detail": "git fetch 실패"}
        self.boot()
        home = self.win.home
        self.assertIs(self.page(), home)
        self.assertTrue(home.notice.isVisible())
        self.assertIn("인터넷에 연결되지 않아", home.notice.text())
        self.assertTrue(home.action_btn.isEnabled())
        self.assertTrue(home.git_btn.isEnabled())
        self.win.show_notice_detail()
        self.assertEqual(self.win.dialog.detail.toPlainText(), "git fetch 실패")
        self.choose("ok")

    def test_tool_update_at_start_restarts(self):
        self.git.replies["sync"] = {"status": "ok", "message": "프로그램이 새 버전으로 바뀌었습니다. 다시 시작합니다.", "restart": True, "changed": True}
        self.boot()
        self.assertIsNone(self.win.session)  # 옛 코드로 풀이 기록을 열지 않음
        self.assertIn("새 버전", self.win.dialog.text.text())
        self.choose("ok")
        self.assertTrue(self.win.restart)
        self.assertFalse(self.win.isVisible())

    def test_submit_opens_the_pr_page(self):
        self.boot()
        url = "https://github.com/WaterMinCho/rokey-python-study/compare/main...study/tester?quick_pull=1"
        self.git.replies["submit"] = {"status": "ok", "message": "제출했습니다. 브라우저에서 PR 을 확인하세요.", "pr_url": url}
        self.git.delay = 0.3
        click(self.win.home.git_btn)
        self.assertFalse(self.win.home.git_btn.isEnabled())  # 도는 동안 잠금
        self.assertTrue(self.win.home.busy_bar.isVisible())
        self.idle()
        self.git.delay = 0
        self.assertEqual(self.git.calls, ["sync", "submit"])
        self.assertEqual(self.opened, [url])
        self.assertIn("제출했습니다", self.win.dialog.text.text())
        self.assertIn(url, self.win.dialog.link.text())
        self.choose("ok")
        self.assertTrue(self.win.home.git_btn.isEnabled())
        self.git.replies["submit"] = {"status": "auth", "message": "저장소에 올릴 권한이 없습니다.", "pr_url": None, "detail": "git push: 403"}
        click(self.win.home.git_btn)
        self.idle()
        self.assertEqual(self.opened, [url])  # 실패하면 브라우저를 열지 않음
        self.assertIn("권한이 없습니다", self.win.dialog.text.text())
        self.choose("ok")

    def test_diverged_offers_two_choices_and_reloads_after_taking_remote(self):
        self.boot()
        before = self.win.session
        self.git.replies["submit"] = {"status": "diverged", "message": "다른 컴퓨터에서 올린 풀이가 있고, 이 컴퓨터의 풀이와 이어지지 않습니다."}
        self.git.replies["resolve"] = {"status": "ok", "message": "다른 컴퓨터의 풀이를 가져왔습니다.", "changed": True, "backup": "/보관함/사본"}
        click(self.win.home.git_btn)
        self.idle()
        self.assertEqual([b.text() for b in self.win.dialog.buttons.values()][::-1],
                         ["다른 컴퓨터의 풀이 가져오기", "이 컴퓨터 풀이로 올리기", "나중에 정하기"])
        self.choose("remote")
        self.idle()
        self.assertEqual(self.git.calls, ["sync", "submit", "resolve:remote"])
        self.assertIsNot(self.win.session, before)  # 내 풀이 폴더가 바뀌었으므로 새로 읽음
        self.assertIn("가져왔습니다", self.win.dialog.text.text())
        self.assertIn("/보관함/사본", self.win.dialog.text.text())
        self.choose("ok")
        click(self.win.home.git_btn)
        self.idle()
        self.choose("local")
        self.idle()
        self.assertEqual(self.git.calls[-1], "resolve:local")
        self.choose("ok")

    def test_diverged_at_start_still_opens_and_asks(self):
        self.git.replies["sync"] = {"status": "diverged", "message": "다른 컴퓨터에서 올린 풀이가 있고, 이 컴퓨터의 풀이와 이어지지 않습니다."}
        self.boot()
        self.assertIs(self.page(), self.win.home)
        self.assertFalse(self.win.home.notice.isVisible())
        self.assertIn("remote", self.win.dialog.buttons)
        self.choose("")  # 나중에 정하기
        self.idle()
        self.assertEqual(self.git.calls, ["sync"])
        self.assertTrue(self.win.home.action_btn.isEnabled())

    def test_fetching_new_problems_rebuilds_the_session(self):
        self.git.replies["sync"] = {"status": "offline", "message": "인터넷에 연결되지 않아 새 문제를 받지 못했습니다."}
        self.boot()
        self.assertTrue(self.win.home.notice.isVisible())
        before = self.win.session
        self.git.replies["sync"] = {"status": "ok", "message": "새 문제를 받았습니다.", "changed": True}
        click(self.win.home.sync_btn)
        self.idle()
        self.assertIsNot(self.win.session, before)
        self.assertIn("새 문제를 받았습니다", self.win.dialog.text.text())
        self.assertFalse(self.win.home.notice.isVisible())  # 시작할 때의 알림은 지움
        self.choose("ok")

    def test_pending_answers_are_written_before_submitting(self):
        self.boot()
        click(self.win.home.action_btn)
        page = self.win.round_page
        item = self.select(lambda it: it["type"] == "choice")
        click(page.choice_panel.buttons[2])
        self.assertIn(item["id"], page.dirty)  # 아직 저장 전
        click(page.home_btn)
        self.assertEqual(self.saved_quiz("d1")[item["id"]], 3)
        self.assertEqual(self.win.home.action_btn.text(), "진단 테스트 이어 풀기")
        self.assertIn("작성한 문항 1개", self.win.home.action_desc.text())

    def test_closing_the_window_saves_what_was_being_typed(self):
        self.boot()
        click(self.win.home.action_btn)
        item = self.select(lambda it: it["type"] == "choice")
        click(self.win.round_page.choice_panel.buttons[0])
        self.win.close()
        self.assertFalse(self.win.isVisible())
        self.assertEqual(self.saved_quiz("d1")[item["id"]], 1)

    def test_answers_that_could_not_be_saved_are_not_dropped_silently(self):
        """자동 저장이 실패한 답을 화면을 떠나거나 창을 닫을 때 말없이 버리지 않음."""
        self.boot()
        click(self.win.home.action_btn)
        page = self.win.round_page
        item = self.select(lambda it: it["type"] == "choice")
        with mock.patch.object(self.win.session, "set_answer", side_effect=PermissionError(13, "잠김")):
            click(page.choice_panel.buttons[1])
            click(page.home_btn)
            self.assertIs(self.page(), page)  # 홈으로 가지 않음
            self.assertIn("저장되지 않았습니다", self.win.dialog.text.text())
            self.assertNotIn("복사", self.win.dialog.text.text())  # 붙여넣기를 막았으므로 복사해 두라고 안내하지 않음
            self.choose("")
            self.assertFalse(self.win.close())  # 닫히지 않음
            self.assertTrue(self.win.isVisible())
            self.choose("")
            self.assertEqual(list(page.dirty), [item["id"]])
        click(page.home_btn)  # 저장이 되면 그대로 나감
        self.assertIs(self.page(), self.win.home)
        self.assertEqual(self.saved_quiz("d1")[item["id"]], 2)
        click(self.win.home.action_btn)
        self.select(lambda it: it is not None and it["id"] == item["id"])
        with mock.patch.object(self.win.session, "set_answer", side_effect=PermissionError(13, "잠김")):
            click(page.choice_panel.buttons[2])
            click(page.home_btn)
            self.choose("drop")  # 저장하지 않고 나가기
        self.assertIs(self.page(), self.win.home)
        self.assertEqual(self.saved_quiz("d1")[item["id"]], 2)

    def test_broken_answer_sheet_offers_repair(self):
        self.boot()
        click(self.win.home.action_btn)
        page = self.win.round_page
        for number in (1, 2, 3):
            item = self.select(lambda it: it["no"] == number)
            self.fill(item, [1] if item["type"] == "choice" else "x")
        click(page.home_btn)
        path = os.path.join(self.win.session.folder("d1"), "quiz.py")
        good = study.read_text(path)
        study.write_text(path, "<<<<<<< HEAD\n" + good + "=======\n>>>>>>> main\n")
        click(self.win.home.action_btn)
        self.assertIs(self.page(), self.win.home)  # 열지 않고 복구를 제안함
        self.assertIn("quiz.py.bak", self.win.dialog.text.text())
        self.choose("repair")
        self.assertTrue(os.path.isfile(path + ".bak"))
        self.assertIs(self.page(), page)
        self.assertEqual(sum(1 for it in page.view["items"] if it["answered"]), 3)
        self.assertIn("3개", self.win.dialog.text.text())
        self.choose("ok")
        # 풀던 중에 답안지가 깨지면 저장을 거부하고, 복구한 뒤에 방금 답을 다시 씀
        study.write_text(path, study.read_text(path) + "x = (\n")
        item = self.select(lambda it: it["no"] == 4)
        self.fill(item, [2] if item["type"] == "choice" else "y")
        pump(save_delay())
        self.assertIn("저장하지 못했습니다", page.status.text())
        self.choose("repair")
        self.choose("ok")
        self.assertEqual(sum(1 for v in self.saved_quiz("d1").values() if v is not None), 4)

    def test_copy_paste_and_right_click_are_blocked(self):
        self.boot()
        click(self.win.home.action_btn)
        page = self.win.round_page
        clipboard = QApplication.clipboard()
        clipboard.setText("밖에서 복사한 글")
        for box in (page.body, page.text_panel.multi, page.code_panel.editor):
            box.setPlainText("화면의 글")
            box.selectAll()
            for key in (Qt.Key.Key_C, Qt.Key.Key_X, Qt.Key.Key_V):
                QTest.keyClick(box, key, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual((box.toPlainText(), clipboard.text()), ("화면의 글", "밖에서 복사한 글"))
            menu = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, box.rect().center())
            QApplication.sendEvent(box.viewport(), menu)
            self.assertIsNone(QApplication.activePopupWidget())
        self.assertTrue(page.paste_note.isVisible())
        QTest.keyClick(page.code_panel.editor, Qt.Key.Key_A)  # 보통 글자는 그대로 들어감
        self.assertEqual(page.code_panel.editor.toPlainText(), "a")

    def test_font_size_is_adjustable_and_remembered(self):
        self.boot()
        page = self.win.round_page
        self.assertEqual(page.code_panel.editor.font().pixelSize(), theme.CODE_PX)
        self.assertTrue(page.code_panel.editor.font().fixedPitch())
        click(self.win.home.action_btn)
        self.select(lambda it: it["type"] == "choice")
        card = page.choice_panel.buttons[0]
        self.assertIn("body { font-size: %dpx" % (14 + theme.DOC_PX), card.doc.defaultStyleSheet())
        self.win.set_zoom(2)
        self.assertEqual(page.code_panel.editor.font().pixelSize(), theme.CODE_PX + 2)
        self.assertEqual(page.text_panel.multi.font().pixelSize(), theme.CODE_PX + 2)
        self.assertIn("body { font-size: %dpx" % (14 + theme.DOC_PX + 2), page.body.document().defaultStyleSheet())
        self.assertIn("body { font-size: %dpx" % (14 + theme.DOC_PX + 2), card.doc.defaultStyleSheet())  # 떠 있는 보기 카드도 같이 커짐
        page.body.setHtml(mdlite.to_html("## 제목\n\n본문"))
        sizes, block = [], page.body.document().begin()
        while block.isValid():
            sizes += [block.begin().fragment().charFormat().font().pixelSize()] if block.text() else []
            block = block.next()
        self.assertEqual(sizes, [18 + theme.DOC_PX + 2, 14 + theme.DOC_PX + 2])  # 본문의 제목도 본문 글자와 같이 커짐
        click(page.home_btn)
        self.win.set_zoom(99)
        self.assertEqual(self.win.zoom, theme.ZOOM_RANGE[1])
        self.win.activateWindow()
        QTest.keyClick(self.win, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.win.zoom, 0)
        QTest.keyClick(self.win, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(self.win, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(self.win, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.win.zoom, -1)
        self.win.set_zoom(3)
        self.win.resize(760, 680)
        size = self.win.size()
        self.win.close()
        again = MainWindow(self.settings, lambda root, user: (self.git, ""))
        self.assertEqual(again.zoom, 3)
        self.assertEqual(again.size(), size)
        again.deleteLater()

    def test_closing_while_a_job_runs_waits_for_it(self):
        self.boot()
        self.win.run_job("오래 걸리는 일", lambda: time.sleep(0.4), lambda result: None)
        self.win.close()
        self.assertTrue(self.win.isVisible())
        wait_until(lambda: not self.win.isVisible(), 5)
        self.assertIsNone(self.win.job)


    def test_submitting_an_untouched_round_warns_first(self):
        self.boot()
        click(self.win.home.action_btn)
        click(self.win.round_page.submit_btn)
        dialog = self.win.dialog
        self.assertIn("아직 작성한 문항이 없습니다", dialog.text.text())
        self.assertFalse(any(button.isDefault() or button.autoDefault() for button in dialog.buttons.values()))  # Enter 로 제출되지 않음
        self.choose("")
        self.assertEqual(self.attempts(), [])


class NoGitTest(GuiTest):
    git_reason = "제출 모듈(gitflow.py)을 불러오지 못했습니다: No module named 'gitflow'"

    def test_screen_works_without_the_submit_module(self):
        self.boot()
        home = self.win.home
        self.assertIs(self.page(), home)
        self.assertFalse(home.git_btn.isEnabled())
        self.assertFalse(home.sync_btn.isEnabled())
        self.assertIn("gitflow.py", home.git_hint.text())
        click(home.action_btn)
        self.assertIs(self.page(), self.win.round_page)
        self.submit_round()
        self.assertIs(self.page(), self.win.result_page)
        self.assertFalse(self.win.result_page.git_btn.isEnabled())


class ErrorTest(GuiTest):
    expect_error = True

    def test_exception_in_a_slot_keeps_the_window_alive(self):
        self.boot()
        boom = QPushButton("boom", self.win)
        boom.clicked.connect(lambda: 1 / 0)
        boom.show()
        with contextlib.redirect_stderr(io.StringIO()):
            click(boom)
        dialog = errors.state["dialog"]
        self.assertTrue(self.win.isVisible())
        self.assertTrue(dialog.isVisible())
        self.assertIn("ZeroDivisionError", dialog.view.toPlainText())
        logs = os.listdir(self.logs)
        self.assertEqual(len(logs), 1)
        self.assertIn("ZeroDivisionError", study.read_text(os.path.join(self.logs, logs[0])))
        click(dialog.copy)
        self.assertIn("ZeroDivisionError", QGuiApplication.clipboard().text())
        dialog.close()
        click(self.win.home.action_btn)  # 오류 뒤에도 계속 쓸 수 있음
        self.assertIs(self.page(), self.win.round_page)

    def test_core_exit_in_the_worker_does_not_kill_the_window(self):
        self.boot()
        done = []
        with contextlib.redirect_stderr(io.StringIO()):
            self.win.run_job("코어가 종료를 부르는 경우", lambda: study.die("없는 세트"), done.append, on_fail=lambda: done.append("fail"))
            self.idle()
        self.assertEqual(done, ["fail"])
        self.assertTrue(self.win.isVisible())
        self.assertIn("SystemExit", errors.state["dialog"].view.toPlainText())
        self.assertTrue(self.win.home.action_btn.isEnabled())  # 잠금이 풀림

    def test_session_error_is_shown_as_is(self):
        self.expect_error = False
        self.boot()

        def fail():
            raise session.SessionError("회차 r99 를 찾을 수 없습니다.")

        self.win.run_job("없는 회차", fail, lambda result: None)
        self.idle()
        self.assertEqual(self.win.dialog.text.text(), "회차 r99 를 찾을 수 없습니다.")
        self.choose("ok")
        self.win.show_result("r99")
        self.assertIn("r99", self.win.dialog.text.text())
        self.choose("ok")

    def test_unreadable_profile_stops_at_the_start_page(self):
        self.expect_error = False
        os.makedirs(os.path.join(study.SUBMISSIONS_DIR, "tester"), exist_ok=True)
        study.write_text(adaptive.profile_path("tester"), '{"rounds": [<<<<<<<')
        self.boot()
        start = self.win.start
        self.assertIs(self.page(), start)
        self.assertIn("profile.json", start.error.text())
        self.assertIn("다시 시도", start.error.text())
        self.assertGreaterEqual(start.error.height(), start.error.heightForWidth(start.error.width()))  # 줄바꿈한 글이 잘리지 않음
        self.assertTrue(start.retry.isVisible())
        os.remove(adaptive.profile_path("tester"))
        click(start.retry)
        self.assertIs(self.page(), self.win.home)


class BankTest(GuiTest):
    def test_question_list_keeps_the_two_lines_of_a_row_apart(self):
        """문항 목록의 한 줄은 유형과 단원 두 줄. 글꼴의 줄 높이가 낮아 붙어 보이던 두 줄 사이를 띄워서 그림."""
        self.boot()
        self.make_round("r90", [self.first(type="choice"), self.first(type="short")])
        self.win.open_round("r90")
        self.win.resize(1280, 800)
        self.win.show()
        pump()
        listw = self.win.round_page.listw
        plain = QListWidget()  # 기본 그리기로 잰 같은 줄
        plain.setIconSize(listw.iconSize())
        plain.addItem(listw.item(1).text())
        plain.item(0).setIcon(listw.item(1).icon())
        self.assertEqual(listw.sizeHintForRow(1), plain.sizeHintForRow(0) + ROW_GAP)
        image = listw.viewport().grab(listw.visualItemRect(listw.item(1))).toImage()  # 고르지 않은 줄
        left, back = image.width() // 4, gray(image.pixel(image.width() - 4, 4))
        inked = [any(abs(gray(image.pixel(x, y)) - back) > 60 for x in range(left, image.width())) for y in range(image.height())]
        bands = re.findall("1+", "".join("1" if row else "0" for row in inked))
        gap = re.search("10+1", "".join("1" if row else "0" for row in inked))
        self.assertEqual(len(bands), 2, inked)  # 유형 줄과 단원 줄
        self.assertGreaterEqual(len(gap.group()) - 2, ROW_GAP * image.devicePixelRatio())

    def test_each_answer_type_saves_what_the_widgets_show(self):
        self.boot()
        keys = [self.first(type="choice", multi=False), self.first(type="choice", multi=True), self.first(type="short"),
                self.first(type="output"), self.first(type="return"), self.first(type="fill"), self.first(type="print")]
        self.make_round("r90", keys)
        self.win.open_round("r90")
        page = self.win.round_page
        single, multi, short, output, code, fill, _ = page.view["items"]

        # 복수 정답 객관식: 여러 개가 함께 선택됨
        self.select(lambda it: it is multi)
        self.assertIn("모두", page.choice_panel.hint.text())
        click(page.choice_panel.buttons[2])
        click(page.choice_panel.buttons[0])
        self.assertEqual([b.isChecked() for b in page.choice_panel.buttons[:3]], [True, False, True])
        pump(save_delay())  # 다른 문항으로 가지 않아도 입력이 멈추면 저장됨
        self.assertEqual(self.saved_quiz("r90")[multi["id"]], [1, 3])

        # 단답: 한 줄, 한글도 입력한 대로 저장됨
        self.select(lambda it: it is short)
        self.assertIn("따옴표 없이", page.text_panel.hint.text())
        self.assertTrue(page.text_panel.single.isVisible())
        self.assertFalse(page.text_panel.multi.isVisible())
        QTest.keyClicks(page.text_panel.single, "abc 1")
        page.text_panel.single.insert(" 한글")
        pump(save_delay())
        self.assertEqual(self.saved_quiz("r90")[short["id"]], "abc 1 한글")

        # 출력 예측: 여러 줄과 앞 공백이 보이는 대로 저장됨
        self.select(lambda it: it is output)
        self.assertTrue(page.text_panel.multi.isVisible())
        self.assertTrue(page.text_panel.multi.font().fixedPitch())
        QTest.keyClicks(page.text_panel.multi, "line 1")
        QTest.keyClick(page.text_panel.multi, Qt.Key.Key_Return)
        QTest.keyClicks(page.text_panel.multi, "  line 2")
        self.select(lambda it: it is single)  # 문항을 옮기면 기다리지 않고 바로 저장됨
        self.assertEqual(self.saved_quiz("r90")[output["id"]].strip("\n"), "line 1\n  line 2")
        self.assertEqual(self.saved_quiz("r90")[multi["id"]], [1, 3])

        # 코드: 키로 친 내용이 파일에 똑같이 들어가고, 실행 결과에는 함수 안에서 출력한 내용도 보임
        self.select(lambda it: it is code)
        path = os.path.join(self.win.session.folder("r90"), code["id"] + ".py")
        name = self.win.session.cat[code["key"]]["spec"]["cases"][0]["call"].split("(")[0]
        editor = page.code_panel.editor
        editor.clear()
        QTest.keyClicks(editor, "def %s(*args):" % name)
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QTest.keyClicks(editor, "print('debug', len(args))")
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QTest.keyClicks(editor, "return None")
        pump(save_delay())
        self.assertEqual(study.read_text(path), "def %s(*args):\n    print('debug', len(args))\n    return None\n" % name)
        self.assertIn("자동 저장했습니다", page.status.text())
        click(page.run_btn)
        self.idle()
        shown = page.code_panel.console.toPlainText()
        for word in ("실패", "기대한 반환값", "실제 반환값", "None", "함수 안 출력", "debug", "기록되지 않습니다"):
            self.assertIn(word, shown)

        # 무한 루프 코드도 화면을 멈추지 않음
        editor.setPlainText("def %s(*args):\n    while True:\n        pass\n" % name)
        ticks = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(time.monotonic()))
        timer.start()
        click(page.run_btn)
        self.assertFalse(page.stack.isEnabled())
        self.assertFalse(page.submit_btn.isEnabled())
        self.assertTrue(page.busy_bar.isVisible())
        self.idle()
        timer.stop()
        self.assertIn("시간 초과", page.code_panel.console.toPlainText())
        self.assertGreater(len(ticks), 100)
        self.assertLess(max(b - a for a, b in zip(ticks, ticks[1:])), 0.5)
        self.assertTrue(page.stack.isEnabled())

        # 메모리를 너무 많이 쓰는 코드는 제한 시간 전에 멈추고 이유를 알려 줌
        editor.setPlainText("import time\ndata = b'x' * (200 * 1024 * 1024)\ntime.sleep(60)\n")
        with mock.patch.object(study, "MEMORY_LIMIT_MB", 128):
            click(page.run_btn)
            self.idle()
        self.assertIn("메모리 초과", page.code_panel.console.toPlainText())

        # 문법 오류는 줄 번호와 함께
        editor.setPlainText("def broken(:\n")
        click(page.run_btn)
        self.idle()
        self.assertIn("문법 오류", page.code_panel.console.toPlainText())

        # 시작 코드로 되돌리기
        click(page.code_panel.reset_btn)
        self.choose("reset")
        self.assertEqual(editor.toPlainText(), code["starter"])
        self.assertEqual(study.read_text(path), code["starter"])
        self.assertFalse(code["answered"])

        # 빈칸 채우기: 안내가 나오고, 빈칸을 안 채우고 실행하면 이유를 알려 줌
        self.select(lambda it: it is fill)
        self.assertIn("빈칸(____)만", page.code_panel.hint.text())
        click(page.run_btn)
        self.idle()
        self.assertIn("빈칸", page.code_panel.console.toPlainText())
        self.assertEqual(self.attempts(), [])  # 실행은 기록하지 않음

    def test_paste_is_blocked_in_every_answer_box(self):
        self.boot()
        self.make_round("r93", [self.first(type="short"), self.first(type="output"), self.first(type="return")])
        self.win.open_round("r93")
        page, clip = self.win.round_page, QGuiApplication.clipboard()
        boxes = {"short": page.text_panel.single, "output": page.text_panel.multi, "return": page.code_panel.editor, "": page.choice_panel.entry}
        for kind, box in boxes.items():
            if kind:
                self.select(lambda it: it["type"] == kind)
                self.fill(page.current, "")
            else:  # 번호 입력칸은 보기 수를 세지 못한 객관식에서만 보여서 화면 밖에 둔 채로 확인함
                box.blockSignals(True)
            read = box.toPlainText if hasattr(box, "toPlainText") else box.text
            target = box.viewport() if hasattr(box, "viewport") else box  # 마우스 이벤트를 받는 위젯
            tries = {"Ctrl+V": lambda: QTest.keyClick(box, Qt.Key.Key_V, CTRL),
                     "Shift+Insert": lambda: QTest.keyClick(box, Qt.Key.Key_Insert, SHIFT),
                     "가운데 버튼": lambda: QTest.mouseClick(target, Qt.MouseButton.MiddleButton),
                     "끌어다 놓기": lambda: self.assertFalse(self.drop(target, "끌어온 글"))}
            clip.setText("붙여넣을 글")
            for name, attempt in tries.items():
                page.paste_note.hide()
                attempt()
                self.assertEqual(read(), "", "%s %s" % (kind, name))
                self.assertTrue(page.paste_note.isVisible(), "%s %s" % (kind, name))
            QApplication.sendEvent(target, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), target.mapToGlobal(QPoint(5, 5))))
            self.assertIsNone(QApplication.activePopupWidget(), kind)  # 우클릭 메뉴는 뜨지 않음
            QTest.keyClicks(box, "abc")  # 복사와 잘라내기도 막고, 실행 취소는 그대로 둠
            QTest.keyClick(box, Qt.Key.Key_A, CTRL)
            for key in (Qt.Key.Key_C, Qt.Key.Key_X):
                QTest.keyClick(box, key, CTRL)
            self.assertEqual((read(), clip.text()), ("abc", "붙여넣을 글"), kind)
            QTest.keyClick(box, Qt.Key.Key_Z, CTRL)
            self.assertLess(len(read()), 3, kind)

        # 글자를 친 직후에 붙여넣어도 안내가 자동 저장 문구에 덮이지 않고, 조금 뒤에 스스로 사라짐
        self.select(lambda it: it["type"] == "short")
        page.paste_note.hide()
        QTest.keyClicks(page.text_panel.single, "ab")
        QTest.keyClick(page.text_panel.single, Qt.Key.Key_V, CTRL)
        pump(save_delay())
        self.assertIn("자동 저장했습니다", page.status.text())
        self.assertEqual((page.paste_note.isVisible(), page.paste_note.text()), (True, PASTE_NOTE))
        page.note_timer.setInterval(20)
        QTest.keyClick(page.text_panel.single, Qt.Key.Key_V, CTRL)
        pump(120)
        self.assertFalse(page.paste_note.isVisible())

    def drop(self, target, text):
        """글을 끌어다 놓는 이벤트를 보내고, 받아들였으면 True 를 돌려줌."""
        data = QMimeData()
        data.setText(text)
        events = (QDragEnterEvent(QPoint(5, 5), Qt.DropAction.CopyAction, data, LEFT, Qt.KeyboardModifier.NoModifier),
                  QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, data, LEFT, Qt.KeyboardModifier.NoModifier))
        for event in events:
            QApplication.sendEvent(target, event)
        return any(event.isAccepted() for event in events)

    def test_result_page_says_why_a_code_item_is_wrong(self):
        self.boot()
        self.make_round("r91", [self.first(type="return")])
        self.win.open_round("r91")
        result = self.win.result_page
        self.fill(self.select(lambda it: it["kind"] == "code"), "print('오답')\n")
        self.submit_round()
        self.assertIs(self.page(), result)
        result.listw.setCurrentRow(1)
        self.assertIn("틀린 이유", result.detail.toPlainText())
        self.win.show_result("r91")  # 지난 회차를 다시 열면 채점 결과가 없어 다시 채점을 안내함
        result.listw.setCurrentRow(1)
        self.assertIn("다시 채점", result.detail.toPlainText())

    def test_number_written_by_hand_in_the_answer_sheet_opens_in_the_text_box(self):
        """터미널 방식으로 따옴표 없이 적은 숫자 답(Q14 = 3)이 든 답안지를 열어도 입력칸과 저장할 문항이 어긋나지 않음."""
        self.boot()
        self.make_round("r92", [self.first(type="return"), self.first(type="short")])
        path = os.path.join(self.win.session.folder("r92"), "quiz.py")
        name = adaptive.fname_of(self.first(type="short"))
        study.write_text(path, study.read_text(path).replace("%s = None" % name, "%s = 3" % name))
        self.win.open_round("r92")
        page = self.win.round_page
        item = self.select(lambda it: it["type"] == "short")
        self.assertIs(page.stack.currentWidget(), page.text_panel)
        self.assertEqual(page.text_panel.single.text(), "3")
        self.fill(item, "4")
        click(page.home_btn)
        self.assertEqual(self.saved_quiz("r92")[name], "4")

    def test_every_bank_item_shows_without_errors(self):
        self.boot()
        sess = self.win.session
        keys = sorted(sess.cat, key=study.natural_key)
        self.make_round("r99", keys, completed=True)
        self.win.open_round("r99")
        page = self.win.round_page
        self.assertEqual(page.listw.count(), len(keys))
        for row in range(page.listw.count()):
            page.listw.setCurrentRow(row)
            item = page.current
            self.assertEqual(item["key"], keys[row])
            self.assertTrue(page.body.toPlainText().strip(), item["id"])
            if item["type"] == "choice":
                cards = page.choice_panel.buttons
                self.assertEqual((len(cards), len(item["options"])), (item["choices"], item["choices"]), item["id"])
                self.assertTrue(all(card.doc.toPlainText().strip() for card in cards), item["id"])
                self.assertFalse(page.choice_panel.entry.isVisible())
            if item["kind"] == "code":
                self.assertEqual(page.code_panel.editor.toPlainText(), item["starter"])
                self.assertNotIn("\t", item["starter"])
        self.assertEqual(page.dirty, {})  # 보기만 해서는 아무것도 저장하지 않음
        self.win.show_result("r99")
        result = self.win.result_page
        for row in range(1, result.listw.count()):
            result.listw.setCurrentRow(row)
            result.reveal()
            text = result.detail.toPlainText()
            self.assertIn("해설", text, keys[row - 1])
            self.assertIn("모범 답안" if result.selected()["kind"] == "code" else "정답", text, keys[row - 1])


class ChoiceCardTest(GuiTest):
    def open_choices(self):
        """글 보기 · 코드 보기(번호 목록) · 복수 정답 · `**N번**` 문단으로 적은 보기 · 단답 순서의 회차를 띄움."""
        self.boot()
        keys = [self.first(type="choice", multi=False), "s04/Q5", self.first(type="choice", multi=True), "s04/Q20", self.first(type="short")]
        self.make_round("r95", keys)
        self.win.open_round("r95")
        self.win.activateWindow()
        return self.win.round_page

    def test_body_keeps_the_question_and_cards_take_the_options(self):
        page = self.open_choices()
        plain, code, _, labeled, _ = page.view["items"]
        cards = page.choice_panel.buttons
        self.assertEqual(len(cards), plain["choices"])
        self.assertTrue(page.body.toPlainText().strip())
        self.assertNotIn("<ol", page.body.toHtml())
        self.select(lambda it: it is code)
        cards = page.choice_panel.buttons
        self.assertEqual(len(cards), 4)
        self.assertIn("t.insert(0, 'X')", cards[3].doc.toPlainText())
        self.assertIn("출력되는 것은", page.body.toPlainText())
        self.assertNotIn("t.insert", page.body.toPlainText())
        self.assertGreater(cards[3].height(), cards[0].height())  # 코드가 세 줄인 보기가 두 줄인 보기보다 큼
        self.select(lambda it: it is labeled)
        cards = page.choice_panel.buttons
        self.assertEqual(len(cards), 5)
        self.assertIn("a[len(a)] = 4", cards[1].doc.toPlainText())
        self.assertIn("모두 고르세요", page.body.toPlainText())
        self.assertNotRegex(page.body.toPlainText() + "".join(card.doc.toPlainText() for card in cards), r"\d번")
        self.assertEqual(page.dirty, {})

    def test_cards_follow_mouse_and_keyboard_and_save_what_they_show(self):
        page = self.open_choices()
        single, _, multi, _, short = page.view["items"]
        cards = page.choice_panel.buttons

        # 카드 어디를 눌러도 골라지고, 단일 정답은 하나만 남고 다시 누르면 풀림
        QTest.mouseClick(cards[1], LEFT, pos=QPoint(cards[1].width() - 5, cards[1].height() - 5))
        self.assertEqual([card.isChecked() for card in cards[:3]], [False, True, False])
        click(cards[3])
        self.assertEqual((single["answer"], [card.isChecked() for card in cards].count(True)), ([4], 1))
        click(cards[3])
        self.assertEqual(single["answer"], [])

        # 숫자 키는 포커스가 문항 목록이나 다른 버튼에 있어도 듣고, 없는 번호는 넘김
        page.listw.setFocus()
        QTest.keyClick(page.listw, Qt.Key.Key_3)
        self.assertEqual((single["answer"], page.listw.currentRow()), ([3], single["no"] - 1))
        QTest.keyClick(page.next_btn, Qt.Key.Key_9)
        self.assertEqual(single["answer"], [3])
        pump(save_delay())
        self.assertEqual(self.saved_quiz("r95")[single["id"]], 3)

        # 위·아래 키로 옮기고 Space 로 고름. 끝에서는 더 가지 않음
        cards[0].setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(cards[0], Qt.Key.Key_Down)
        self.assertIs(QApplication.focusWidget(), cards[1])
        self.assertTrue(cards[1].ring)
        QTest.keyClick(cards[1], Qt.Key.Key_Space)
        self.assertEqual(single["answer"], [2])
        QTest.keyClick(cards[1], Qt.Key.Key_Up)
        QTest.keyClick(cards[0], Qt.Key.Key_Up)
        self.assertIs(QApplication.focusWidget(), cards[0])

        # 복수 정답은 여러 개가 남고, 다시 누른 것만 풀림
        self.select(lambda it: it is multi)
        self.assertEqual(self.saved_quiz("r95")[single["id"]], 2)  # 문항을 옮기면 바로 저장됨
        cards = page.choice_panel.buttons
        QTest.keyClick(page.listw, Qt.Key.Key_3)
        QTest.keyClick(page.listw, Qt.Key.Key_1)
        click(cards[1])
        click(cards[1])
        self.assertEqual((multi["answer"], [card.isChecked() for card in cards[:3]]), ([1, 3], [True, False, True]))

        # 잠겨 있을 때와 다른 유형의 문항에서는 숫자 키가 답을 바꾸지 않음
        page.set_busy(True, "채점하는 중입니다.")
        QTest.keyClick(self.win, Qt.Key.Key_2)
        page.set_busy(False)
        self.assertEqual(multi["answer"], [1, 3])
        self.select(lambda it: it is short)
        QTest.keyClicks(page.text_panel.single, "12")
        QTest.keyClick(page.listw, Qt.Key.Key_2)
        self.assertEqual((page.text_panel.single.text(), multi["answer"]), ("12", [1, 3]))
        self.assertEqual(self.saved_quiz("r95")[multi["id"]], [1, 3])

        # 제출한 뒤 다시 풀기로 열어도 고른 보기가 그대로 보이고, 결과 화면에는 보기까지 든 문제 전체가 나옴
        self.submit_round()
        result = self.win.result_page
        result.listw.setCurrentRow(single["no"])
        self.assertIn(cards_text(self.win.session, single)[1], result.detail.toPlainText())
        self.assertIn("2번", result.detail.toPlainText())
        self.win.open_round("r95", review=True, select=single["id"])
        cards = page.choice_panel.buttons
        self.assertEqual([card.isChecked() for card in cards[:3]], [False, True, False])
        click(cards[0])
        click(page.home_btn)
        self.assertEqual(self.saved_quiz("r95")[single["id"]], 1)

    def test_double_click_and_held_keys_pick_only_once(self):
        """버튼을 두 번 누른 것이 같은 자리의 카드로 들어와 답이 바뀌지 않고, 카드를 더블클릭하거나 키를 누르고 있어도 한 번만 고름."""
        self.boot()
        win, page = self.win, self.win.round_page
        button = win.home.action_btn
        win.resize(1280, 800)  # 창 좌표로 누르므로 버튼이 화면 밖으로 밀리지 않는 크기로 둠
        pump()
        QTest.mouseDClick(win.windowHandle(), LEFT, pos=button.mapTo(win, button.rect().center()))
        pump()
        self.assertIs(self.page(), page)
        self.assertTrue(all(it["answer"] is None for it in page.view["items"] if it["type"] == "choice"))
        single = self.select(lambda it: it["type"] == "choice" and not it["multi"])
        cards = page.choice_panel.buttons
        QTest.mouseDClick(cards[0], LEFT)  # 더블클릭의 뒷부분(더블클릭 · 뗌)만 이 카드로 들어온 경우
        QTest.mouseRelease(cards[0], LEFT)
        self.assertEqual((single["answer"], cards[0].isChecked()), (None, False))
        click(cards[1])  # 카드를 더블클릭하면 누름 · 뗌 · 더블클릭 · 뗌 순서로 들어옴
        QTest.mouseDClick(cards[1], LEFT)
        QTest.mouseRelease(cards[1], LEFT)
        self.assertEqual((single["answer"], cards[1].isChecked()), ([2], True))  # 골랐다가 바로 풀리지 않음

        self.assertFalse(any(key.autoRepeat() for key in page.choice_panel.keys))
        cards[2].setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(cards[2], Qt.Key.Key_Space)
        for _ in range(3):  # 누르고 있을 때 운영체제가 되풀이해 보내는 키
            QApplication.sendEvent(cards[2], QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ", True))
        self.assertEqual(single["answer"], [3])
        click(page.home_btn)
        self.assertEqual(self.saved_quiz("d1")[single["id"]], 3)

    def test_hand_written_value_that_matches_no_card_is_pointed_out(self):
        """답안지에 손으로 적은 값이 카드와 맞지 않으면(따옴표로 감싼 번호, 없는 번호) 고른 카드가 없는 까닭을 알리고, 다시 고르면 안내가 사라짐."""
        self.boot()
        keys = [self.first(type="choice", multi=False), "s04/Q5", "s04/Q20"]
        self.make_round("r96", keys)
        path = os.path.join(self.win.session.folder("r96"), "quiz.py")
        text = study.read_text(path)
        for key, value in zip(keys, ('"2"', "9", "[2, 9]")):
            text = text.replace("%s = None" % adaptive.fname_of(key), "%s = %s" % (adaptive.fname_of(key), value))
        study.write_text(path, text)
        self.win.open_round("r96")
        page, panel = self.win.round_page, self.win.round_page.choice_panel
        for row, (stray, checked) in enumerate((("'2'", []), ("9", []), ("9", [2]))):
            page.listw.setCurrentRow(row)
            self.assertTrue(panel.stray.isVisible(), row)
            self.assertIn("(%s)" % stray, panel.stray.text())
            self.assertEqual([number for number, card in enumerate(panel.buttons, 1) if card.isChecked()], checked)
        click(panel.buttons[0])
        self.assertFalse(panel.stray.isVisible())
        click(page.home_btn)
        self.assertEqual(self.saved_quiz("r96")[adaptive.fname_of("s04/Q20")], [1, 2])
        self.win.open_round("r96", select=adaptive.fname_of("s04/Q20"))  # 카드와 맞는 값만 남으면 안내가 없음
        self.assertEqual((panel.stray.isVisible(), [card.isChecked() for card in panel.buttons[:3]]), (False, [True, True, False]))

    def test_question_that_cannot_be_split_keeps_the_whole_body_and_number_cards(self):
        with mock.patch.object(session, "split_choices", return_value=([], [])):
            page = self.open_choices()
        code = self.select(lambda it: it["key"] == "s04/Q5")
        cards = page.choice_panel.buttons
        self.assertEqual([card.doc.toPlainText() for card in cards], ["1번", "2번", "3번", "4번"])
        self.assertIn("t.insert(0, 'X')", page.body.toPlainText())
        click(cards[3])
        click(page.home_btn)
        self.assertEqual(self.saved_quiz("r95")[code["id"]], 4)


def cards_text(sess, item):
    """문항의 보기를 은행의 본문에서 읽어 글자로 돌려줌."""
    body = adaptive.quiz_section(sess.cat[item["key"]]["set"], sess.cat[item["key"]]["q"]["id"])
    return [mdlite.inline_plain(option[0]["text"]) for option in session.split_choices(body)[1]]


class TeamTest(GuiTest):
    def add_member(self, user, correct):
        """풀이 기록을 만듦. 진단에서 앞의 correct 문항만 맞히고 제출함."""
        sess = session.Session(user)
        sess.ensure_round()
        for view in sess.open_round("d1")["items"][:correct]:
            sess.set_answer("d1", view["id"], right_answer(sess, view))
        sess.grade("d1", finalize=True)

    def test_team_page_shows_a_card_per_member_in_readiness_order(self):
        for user, correct in (("tester", 16), ("alpha-kim", 30), ("beta_lee", 3)):
            self.add_member(user, correct)
        study.write_text(adaptive.profile_path("broken"), '{"rounds": [<<<<<<<')  # 읽을 수 없는 기록은 건너뜀
        self.boot()
        win, team = self.win, self.win.team_page
        click(win.home.team_btn)
        self.assertIs(self.page(), team)
        rows = win.session.team()
        self.assertEqual([row["user"] for row in rows], ["alpha-kim", "tester", "beta_lee"])
        self.assertEqual([card.user.text() for card in team.cards], [row["user"] for row in rows])
        self.assertEqual([hasattr(card, "me") for card in team.cards], [False, True, False])
        self.assertEqual([avatar.text for avatar in team.findChildren(Avatar)], ["AK", "TE", "BL"])
        self.assertEqual(len({avatar.back.name() for avatar in team.findChildren(Avatar)}), 3)
        self.assertIsNone(team.empty)
        for card, row in zip(team.cards, rows):
            self.assertEqual((card.ready.text(), card.bar.value()), ("%d%%" % row["readiness"], row["readiness"]))
            self.assertEqual(card.mastered.text(), "숙달한 단원 %d / %d" % (row["mastered"], len(adaptive.units())))
            self.assertEqual(card.facts.text(), "회차 %d · 정답률 %d%% · 마지막 풀이 %s" % (row["rounds"], round(row["accuracy"] * 100), row["last"]))
            self.assertEqual(card.strip.cells.count(), len(adaptive.units()))
            self.assertIn("정답률", card.strip.cells.itemAt(0).widget().toolTip())
            titles = {unit["unit"]: unit["title"] for unit in row["units"]}  # 단원은 이름으로 보여 줌
            self.assertEqual(card.weak.text(), "약한 단원: " + (", ".join(titles[unit] for unit in row["weak"]) or "-"))
            self.assertEqual(card.strong.text(), "능숙한 단원: " + (", ".join(titles[unit] for unit in row["strong"]) or "-"))
        self.assertEqual(len(rows[2]["weak"]), 3)
        self.assertEqual(team.cards[1].ready.text(), win.home.ready.text())
        click(team.home_btn)
        self.assertIs(self.page(), win.home)

    def test_long_id_is_cut_short_and_both_columns_stay_the_same_width(self):
        long = "a" * 20 + "-" + "b" * 18  # 깃허브 ID 의 최대 길이(39자)
        for user, correct in ((long, 30), ("tester", 16)):
            self.add_member(user, correct)
        self.win.resize(1024, 700)
        self.boot()
        click(self.win.home.team_btn)
        first, second = self.win.team_page.cards
        self.assertEqual(first.width(), second.width())
        self.assertTrue(first.user.text().endswith("…") and len(first.user.text()) < len(long), first.user.text())
        self.assertEqual((first.user.full, first.user.toolTip()), (long, long))  # 전체 ID 는 툴팁으로
        self.assertEqual((second.user.text(), second.user.toolTip()), ("tester", ""))

    def test_team_page_explains_when_nobody_else_has_a_record(self):
        self.boot()
        win, team = self.win, self.win.team_page
        click(win.home.team_btn)
        self.assertEqual(team.cards, [])
        self.assertIn("다른 사람의 풀이가 없습니다", team.empty.title.text())
        self.assertIn("진단 테스트를 시작하면", team.empty.text.text())
        self.assertIsNotNone(team.empty.findChild(Mascot))
        click(team.home_btn)
        click(win.home.action_btn)  # 진단을 시작하면 내 카드가 생김
        click(win.round_page.home_btn)
        click(win.home.team_btn)
        self.assertEqual([hasattr(card, "me") for card in team.cards], [True])
        self.assertEqual(team.cards[0].facts.text(), "회차 1 · 정답률 - · 마지막 풀이 -")
        self.assertNotIn("진단 테스트를 시작하면", team.empty.text.text())
        self.add_member("other", 5)
        click(team.home_btn)
        click(win.home.team_btn)
        self.assertEqual((len(team.cards), team.empty), (2, None))
        self.assertEqual((len(team.findChildren(MemberCard)), team.findChildren(EmptyCard)), (2, []))  # 앞서 놓았던 카드는 남지 않음


class WrongNotesTest(GuiTest):
    def submit(self, rid, keys, right=(), wrong=()):
        """고른 문항으로 회차를 만들어 화면에서 풀고 제출함. right 는 정답, wrong 은 오답을 적고 나머지는 비움."""
        self.make_round(rid, keys)
        self.win.open_round(rid)
        for key in keys:
            if key in right or key in wrong:
                item = self.select(lambda it: it["key"] == key)
                self.fill(item, right_answer(self.win.session, item) if key in right else "print('오답')\n")
        self.submit_round()
        self.assertIs(self.page(), self.win.result_page)

    def open_notes(self):
        self.win.go_home()
        click(self.win.home.wrong_btn)
        self.assertIs(self.page(), self.win.wrong_page)
        return self.win.wrong_page

    def rows(self, page):
        return [page.listw.item(row).text() for row in range(page.listw.count())]

    def test_notes_list_misses_by_unit_and_open_each_item(self):
        self.boot()
        choice, output, code = self.first(type="choice", multi=False), self.first(type="output"), self.first(type="return")
        cat = self.win.session.cat
        self.assertEqual([cat[key]["unit"] for key in (choice, output, code)], ["s01", "s01", "s02"])
        self.submit("r91", [choice, output, code], right=[choice], wrong=[code])
        page = self.open_notes()
        self.assertEqual(page.summary.text(), "틀린 문항 2개 · 그 뒤에 맞힌 문항 0개")
        self.assertFalse(page.hide_fixed.isChecked())
        self.assertIs(page.stack.currentWidget(), page.split)
        self.assertEqual(self.rows(page), ["1차시 · %s · 1문항" % cat[output]["unit_title"], "출력 예측 · 91회차 미니 모의고사 · 미응답",
                                           "2차시 · %s · 1문항" % cat[code]["unit_title"], "반환값 · 91회차 미니 모의고사"])
        for row in (0, 2):  # 단원 머리 줄은 누르거나 화살표 키로 고를 수 없음
            self.assertFalse(page.listw.item(row).flags() & (Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled))
            self.assertTrue(page.listw.item(row).font().bold())
        self.assertEqual(page.listw.currentRow(), 1)
        QTest.mouseClick(page.listw.viewport(), LEFT, pos=page.listw.visualItemRect(page.listw.item(0)).center())
        self.assertEqual(page.listw.currentRow(), 1)
        page.listw.setFocus()
        QTest.keyClick(page.listw, Qt.Key.Key_Down)
        self.assertEqual(page.listw.currentRow(), 3)
        QTest.keyClick(page.listw, Qt.Key.Key_Up)
        self.assertEqual(page.listw.currentRow(), 1)
        for key, row in ((Qt.Key.Key_End, 3), (Qt.Key.Key_Home, 1), (Qt.Key.Key_PageDown, 3), (Qt.Key.Key_PageUp, 1)):
            QTest.keyClick(page.listw, key)  # Home 과 PageUp 이 0번 단원 머리 줄을 가리키면 그 아래 문항 줄로 감
            self.assertEqual(page.listw.currentRow(), row, key)
        self.assertEqual([page.listw.item(row).foreground().color().name() for row in (1, 3)], [theme.color("blank"), theme.color("wrong")])

        item = self.win.session.wrong_item("r91", adaptive.fname_of(output))
        self.assertEqual(page.item_title.text(), "출력 예측 · %s · %d점" % (cat[output]["unit_title"], cat[output]["points"]))
        text = page.detail.toPlainText()
        self.assertIn("미응답 · 91회차 미니 모의고사", text)
        self.assertIn(mdlite.inline_plain(item["body_md"].split("\n")[0]), text)
        self.assertIn("내 답", text)
        self.assertIn("(작성하지 않았습니다)", text)
        self.assertNotIn("정답과 해설", text)
        self.assertTrue(page.explain_btn.isEnabled())
        click(page.explain_btn)
        self.assertIn("정답과 해설", page.detail.toPlainText())
        self.assertIn(cat[output]["q"]["answer"].strip("\n").split("\n")[0], page.detail.toPlainText())
        self.assertFalse(page.explain_btn.isEnabled())

        page.listw.setCurrentRow(3)
        self.assertIn("print('오답')", page.detail.toPlainText())
        self.assertTrue(page.item_title.text().startswith(cat[code]["spec"]["title"] + " · 반환값"))
        click(page.explain_btn)
        self.assertIn("모범 답안", page.detail.toPlainText())
        click(page.retry_btn)  # 그 회차의 다시 풀기 화면에서 그 문항을 엶
        round_page = self.win.round_page
        self.assertIs(self.page(), round_page)
        self.assertEqual((round_page.view["id"], round_page.review, round_page.current["key"]), ("r91", True, code))
        self.assertEqual(round_page.title.text(), "91회차 미니 모의고사 · 다시 풀기")

    def test_items_answered_right_later_are_marked_and_can_be_hidden(self):
        self.boot()
        output, code = self.first(type="output"), self.first(type="return")
        self.submit("r91", [output, code], wrong=[code])
        self.submit("r92", [output], right=[output])
        page = self.open_notes()
        self.assertEqual(page.summary.text(), "틀린 문항 2개 · 그 뒤에 맞힌 문항 1개")
        self.assertEqual(self.rows(page)[1], "출력 예측 · 91회차 미니 모의고사 · 미응답 · 다시 맞힘")
        self.assertEqual(page.listw.item(1).foreground().color().name(), theme.color("ok"))
        self.assertIn("그 뒤에 다시 맞힘", page.detail.toPlainText())
        page.listw.setCurrentRow(3)
        click(page.hide_fixed)
        self.assertEqual(self.rows(page), ["2차시 · %s · 1문항" % self.win.session.cat[code]["unit_title"], "반환값 · 91회차 미니 모의고사"])
        self.assertEqual(page.selected()["key"], code)  # 고르던 문항이 남아 있으면 그대로
        click(page.hide_fixed)
        self.assertEqual(len(self.rows(page)), 4)
        self.assertEqual(page.selected()["key"], code)

        click(page.retry_btn)  # 다시 풀기에서 고쳐 다시 채점하고 돌아오면 다시 맞힌 문항이 됨
        self.fill(self.win.round_page.current, right_answer(self.win.session, self.win.round_page.current))
        click(self.win.round_page.submit_btn)
        self.idle()
        page = self.open_notes()
        self.assertEqual(page.summary.text(), "틀린 문항 2개 · 그 뒤에 맞힌 문항 2개")
        click(page.hide_fixed)
        self.assertIs(page.stack.currentWidget(), page.empty)
        self.assertIn("모두 다시 맞혔습니다", page.empty_text.text())
        self.assertFalse(page.explain_btn.isEnabled() or page.retry_btn.isEnabled())

    def test_empty_notes_say_where_misses_come_from(self):
        self.boot()
        page = self.open_notes()
        self.assertIs(page.stack.currentWidget(), page.empty)
        self.assertEqual(page.empty_text.text(), "아직 틀린 문항이 없습니다. 회차를 제출하면 틀린 문항이 여기에 모입니다.")
        self.assertEqual(page.summary.text(), "틀린 문항 0개 · 그 뒤에 맞힌 문항 0개")
        click(page.home_btn)
        self.assertIs(self.page(), self.win.home)

    def test_explain_opens_only_after_the_round_is_submitted(self):
        """터미널에서 일부만 채점한 회차의 오답도 목록에 나오지만, 해설은 회차를 제출한 뒤에 열림."""
        self.boot()
        output, code = self.first(type="output"), self.first(type="return")
        self.make_round("r91", [output, code])
        self.win.session.set_answer("r91", adaptive.fname_of(output), "틀린 답")
        self.win.session.grade("r91")
        page = self.open_notes()
        self.assertEqual(self.rows(page)[1:], ["출력 예측 · 91회차 미니 모의고사"])
        click(page.explain_btn)
        self.assertIn("제출한 뒤에", self.win.dialog.text.text())
        self.choose("ok")
        self.assertNotIn("정답과 해설", page.detail.toPlainText())
        self.assertTrue(page.explain_btn.isEnabled())
        click(page.retry_btn)  # 끝나지 않은 회차는 다시 풀기가 아니라 이어 풀기와 같은 풀이 화면으로 열림
        round_page = self.win.round_page
        self.assertIs(self.page(), round_page)
        self.assertEqual((round_page.view["id"], round_page.review, round_page.current["key"]), ("r91", False, output))
        self.assertEqual(round_page.submit_btn.text(), "회차 제출")

    def test_broken_answer_sheet_is_reported_and_retry_offers_repair(self):
        self.boot()
        output, code = self.first(type="output"), self.first(type="return")
        self.submit("r91", [output, code], wrong=[code])
        path = os.path.join(self.win.session.folder("r91"), "quiz.py")
        study.write_text(path, study.read_text(path) + "x = (\n")
        page = self.open_notes()
        self.assertIn("답안지 복구", page.detail.toPlainText())
        self.assertFalse(page.explain_btn.isEnabled())
        click(page.retry_btn)
        self.assertIs(self.page(), page)  # 열지 않고 복구를 제안함
        self.choose("repair")
        self.assertIs(self.page(), self.win.round_page)
        self.assertEqual(self.win.round_page.current["key"], output)
        self.choose("ok")

    def test_notes_follow_the_dark_theme_and_font_size(self):
        self.boot()
        output, code = self.first(type="output"), self.first(type="return")
        self.submit("r91", [output, code], wrong=[code])
        page = self.open_notes()
        page.listw.setCurrentRow(3)
        click(page.explain_btn)
        theme.set_mode("dark")
        pump()
        self.assertEqual([page.listw.item(row).foreground().color().name() for row in (1, 3)], [theme.DARK["blank"], theme.DARK["wrong"]])
        self.assertIn(theme.DARK["ink"], page.detail.document().defaultStyleSheet())
        self.assertIn("모범 답안", page.detail.toPlainText())  # 펼친 해설은 다시 그려도 남음
        self.assertEqual(page.hide_fixed.palette().color(page.hide_fixed.palette().ColorRole.Base).name(), theme.DARK["track"])
        self.assertEqual(bright_share(self.win), 0)
        shown = backgrounds(page.detail.document().toHtml())  # 구역 띠와 코드 상자
        self.assertTrue(shown and all(gray(value) <= 200 for value in shown), shown)
        self.win.set_zoom(2)
        self.assertIn("body { font-size: %dpx" % (14 + theme.DOC_PX + 2), page.detail.document().defaultStyleSheet())
        theme.set_mode("light")
        pump()
        self.assertEqual(page.listw.item(3).foreground().color().name(), theme.LIGHT["wrong"])
        self.assertGreater(bright_share(self.win), 0.5)


class WidgetTest(unittest.TestCase):
    def test_choice_falls_back_to_a_number_box_when_options_cannot_be_counted(self):
        panel, seen = ChoicePanel(), []
        panel.changed.connect(seen.append)
        panel.set_item({"choices": 0, "multi": False, "answer": [3, 1]})
        self.assertEqual(panel.buttons, [])
        self.assertFalse(panel.entry.isHidden())
        self.assertEqual(panel.entry.text(), "3, 1")
        panel.entry.clear()
        QTest.keyClicks(panel.entry, "2, 4")
        self.assertEqual(seen[-1], [2, 4])
        panel.set_item({"choices": 4, "multi": False, "answer": 2})  # 보기 수만 아는 문항은 번호만 든 카드
        self.assertTrue(panel.entry.isHidden())
        self.assertEqual([b.isChecked() for b in panel.buttons], [False, True, False, False])
        self.assertEqual([b.doc.toPlainText() for b in panel.buttons], ["1번", "2번", "3번", "4번"])
        click(panel.buttons[3])
        self.assertEqual(seen[-1], [4])

    def test_choice_card_is_as_tall_as_its_content_and_wraps_long_code(self):
        short = ChoiceCard(1, mdlite.to_html("`a`"), theme.doc_css(), False)
        code = ChoiceCard(2, mdlite.to_html("```python\n%s\n```" % "\n".join("x%d = %d" % (n, n) for n in range(6))), theme.doc_css(), False)
        long = ChoiceCard(3, mdlite.to_html("```python\nprint(%s)\n```" % ", ".join("'값 %d'" % n for n in range(40))), theme.doc_css(), True)
        for card in (short, code, long):
            card.resize(440, card.height())
            card.arrange()
            self.assertGreaterEqual(card.height(), card.top + content_height(card.doc) + card.PAD - 1)
            self.assertLessEqual(card.height(), card.top + content_height(card.doc) + 2 * card.PAD + card.BADGE)
        self.assertEqual(short.height(), short.BADGE + 2 * short.PAD)  # 한 줄짜리는 번호 배지 높이에 맞춤
        self.assertEqual(content_height(code.doc), code.doc.size().height() - 10)  # 코드 상자 아래 여백은 뺌
        line = short.doc.firstBlock().layout().lineAt(0)
        glyphs = line.ascent() + line.descent()
        self.assertGreater(short.doc.size().height(), glyphs + 1)  # 본문은 줄 간격을 넓혀서 그림. 코드 글꼴은 운영체제마다 높이가 달라 넉넉히 봄
        self.assertAlmostEqual(content_height(short.doc), glyphs, delta=1)  # 마지막 줄의 글자 아래에 붙는 줄 간격은 뺌
        self.assertGreater(code.height(), 4 * short.height() // 2)
        narrow = long.height()
        long.resize(1600, narrow)
        long.arrange()
        self.assertGreater(narrow, long.height())  # 좁으면 긴 코드 줄을 잘라 내지 않고 줄바꿈함

    def test_message_dialog_shrinks_back_when_the_detail_is_folded(self):
        dialog = dialogs.MessageDialog(None, "제목", "안내 글", detail="자세한 내용")
        self.addCleanup(dialog.close)
        dialog.show()
        pump()
        more = next(button for button in dialog.findChildren(QPushButton) if button.text() == "자세히")
        closed = dialog.height()
        click(more)
        self.assertTrue(dialog.detail.isVisible())
        self.assertGreaterEqual(dialog.height(), closed + dialog.detail.minimumHeight())
        click(more)
        self.assertFalse(dialog.detail.isVisible())
        self.assertEqual(dialog.height(), closed)  # 접으면 펼치기 전 높이로 돌아감

    def test_guide_label_spaces_its_lines_and_hands_back_plain_text(self):
        label = Para("첫 줄 <b>굵게</b> & 끝\n둘째 줄", "muted")
        self.assertEqual((label.text(), label.objectName(), label.wordWrap()), ("첫 줄 <b>굵게</b> & 끝\n둘째 줄", "muted", True))
        line = label.fontMetrics().height()
        self.assertGreater(label.sizeHint().height(), 2 * line + 4)  # 두 줄이 붙지 않음
        one, plain = Para("한 줄"), QLabel("한 줄")
        self.assertLessEqual(abs(one.sizeHint().width() - plain.sizeHint().width()), 2)
        self.assertLessEqual(one.sizeHint().height(), plain.sizeHint().height() + 2)  # 한 줄짜리는 전과 같은 자리를 차지함
        self.assertEqual(one.heightForWidth(400), one.sizeHint().height())
        row, button = QWidget(), QPushButton("단추")  # 단추 옆에 놓으면 글이 단추 글자와 같은 높이에 옴
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.addLayout(widgets.centered(one), 1)
        box.addWidget(button)
        row.resize(300, row.sizeHint().height())
        row.show()
        pump()
        self.assertLessEqual(abs(one.geometry().center().y() - button.geometry().center().y()), 1)
        self.assertEqual(one.height(), one.heightForWidth(one.width()))
        row.close()
        long = Para("가나다라마바사 " * 30)
        self.assertGreater(long.sizeHint().width(), 400)  # 좁고 길게 어림하지 않아서 대화상자가 헐겁게 열리지 않음
        link = widgets.LinkLabel('앞 <a href="https://example.com">링크</a>')
        self.assertEqual(link.text(), '앞 <a href="https://example.com">링크</a>')
        self.assertIn('<a href="https://example.com">링크</a>', QLabel.text(link))  # 링크는 글자로 바꾸지 않음
        shown = QTextDocument()
        shown.setHtml(QLabel.text(label))
        self.assertEqual(shown.toPlainText(), "첫 줄 <b>굵게</b> & 끝\n둘째 줄")  # 태그로 읽지 않고 글자로 보여 줌
        label.setText("")
        self.assertEqual((label.text(), QLabel.text(label)), ("", ""))
        label.setText("다시")
        self.assertEqual(label.text(), "다시")

    def test_problem_text_spaces_its_lines_but_code_boxes_do_not(self):
        doc = QTextDocument()
        doc.setDefaultStyleSheet(theme.doc_css())
        doc.setHtml(mdlite.to_html("## 제목\n\n본문\n\n- 항목\n\n  ```python\n  y = 2\n  ```\n\n```python\nx = 1\n```\n\n| 이름 | 뜻 |\n|---|---|\n| a | 칸 |"))
        found, block = {}, doc.begin()
        while block.isValid():
            found[block.text()] = block.blockFormat().lineHeight()
            block = block.next()
        spaced = theme.line_pct(theme.DOC_LINE)
        self.assertEqual([found[text] for text in ("본문", "항목", "칸")], [spaced, spaced, spaced])
        metrics = QFontMetricsF(APP.font())  # 운영체제가 글꼴의 줄 높이를 다르게 읽어도 줄 간격은 글자 크기의 같은 배수
        self.assertAlmostEqual(metrics.lineSpacing() * spaced / 100, theme.DOC_LINE * APP.font().pixelSize(), delta=0.2)
        self.assertGreater(spaced, 100)
        self.assertEqual([found[text] for text in ("제목", "x = 1", "y = 2")], [100, 100, 100])  # 목록 안의 코드 상자도 그대로

    def test_bundled_font_is_used_everywhere(self):
        """같이 배포하는 나눔고딕이 등록되고 화면 글꼴로 쓰임. 굵은 글자도 같은 글꼴의 Bold 로 나옴."""
        theme.apply(APP)
        self.addCleanup(theme.apply, APP)
        self.assertIn("NanumGothic", QFontDatabase.families())
        self.assertEqual(APP.font().family(), "NanumGothic")
        self.assertIn("Bold", QFontDatabase.styles("NanumGothic"))
        self.assertEqual(theme.code_families(), ["D2Coding", "NanumGothic"])  # 코드 글꼴도 같이 배포해서 어느 컴퓨터에서나 같음
        self.assertIn("Bold", QFontDatabase.styles("D2Coding"))
        code = QFontMetricsF(theme.code_font())
        self.assertEqual(code.horizontalAdvance("한"), 2 * code.horizontalAdvance("a"))  # 한글이 영문 두 칸 폭이라 코드 안의 한글도 줄이 맞음
        self.assertIn("font-family: 'D2Coding'", theme.doc_css())  # 문제 본문의 코드도 같은 글꼴

    def test_corner_between_two_scroll_bars_is_not_drawn_as_a_box(self):
        edit = CodeEditor()
        edit.setPlainText("\n".join("x" * 200 for _ in range(60)))
        edit.resize(260, 180)
        edit.show()
        self.addCleanup(edit.close)
        pump()
        across, down = edit.horizontalScrollBar(), edit.verticalScrollBar()
        self.assertTrue(across.isVisible() and down.isVisible())
        left, top = down.mapTo(edit, QPoint(0, 0)).x(), across.mapTo(edit, QPoint(0, 0)).y()
        image = edit.grab().toImage()
        colors = {image.pixelColor(left + x, top + y).name() for x in range(8) for y in range(8)}  # 바깥쪽은 입력칸의 둥근 테두리와 겹침
        self.assertEqual(colors, {theme.EDITOR["bg"]})

    def test_run_hint_wraps_inside_a_narrow_result_box(self):
        """실행하기 전의 안내는 칸이 좁아도 줄을 바꿔 끝까지 보임."""
        panel = widgets.CodePanel()
        panel.resize(300, 520)
        panel.show()
        self.addCleanup(panel.close)
        panel.set_item({"type": "return", "answer": "x = 1\n"})
        pump()
        console = panel.console
        start, end = QTextCursor(console.document()), QTextCursor(console.document())
        end.movePosition(QTextCursor.MoveOperation.End)
        self.assertEqual((console.toPlainText(), panel.console_html, console.horizontalScrollBar().maximum()), (panel.HINT, "", 0))
        self.assertGreater(console.cursorRect(end).top(), console.cursorRect(start).top())  # 한 줄에 다 들어가지 않아 줄이 바뀜
        self.assertTrue(console.viewport().rect().contains(console.cursorRect(end)))  # 마지막 글자까지 칸 안에 있음
        panel.show_console("<body><p>결과</p></body>")  # 결과가 나오면 안내는 사라짐
        self.assertEqual(console.toPlainText(), "결과")

    def test_standard_menu_of_an_answer_box_is_in_korean(self):
        translator = app.korean(APP)
        self.addCleanup(APP.removeTranslator, translator)
        if translator.isEmpty():
            self.skipTest("이 PyQt6 에는 한글 번역 파일이 없습니다")
        editor = CodeEditor()
        menu = editor.createStandardContextMenu()
        self.assertTrue(any("복사" in action.text() for action in menu.actions()), [action.text() for action in menu.actions()])

    def test_mascot_changes_face_and_blinks_only_while_shown(self):
        bot = Mascot(96)
        plain = bot.grab().toImage()
        bot.set_happy(True)
        self.assertNotEqual(bot.grab().toImage(), plain)
        bot.set_happy(False)
        self.assertEqual(bot.grab().toImage(), plain)
        bot.open = 0.0
        self.assertNotEqual(bot.grab().toImage(), plain)  # 감은 눈
        self.assertFalse(bot.timer.isActive())
        bot.show()
        self.assertTrue(bot.timer.isActive() and bot.timer.interval() >= 2000)
        bot.hide()
        self.assertFalse(bot.timer.isActive())


class EditorTest(unittest.TestCase):
    def setUp(self):
        self.ed = CodeEditor()
        self.ed.setFont(theme.code_font())

    def keys(self, *steps):
        for step in steps:
            if isinstance(step, str):
                for ascii_run, chars in itertools.groupby(step, str.isascii):
                    if ascii_run:
                        QTest.keyClicks(self.ed, "".join(chars))
                    else:
                        self.compose(chars)
            else:
                QTest.keyClick(self.ed, *(step if isinstance(step, tuple) else (step,)))
        return self.ed.toPlainText()

    def test_ctrl_slash_comments_lines_and_undoes_in_one_step(self):
        """Ctrl+/ 는 커서 줄이나 고른 줄을 '# ' 로 주석 처리하고, 다시 누르면 풂. 들여쓰기 모양과 빈 줄은 그대로 둠."""
        slash = (Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier)
        self.put("x = 1\nprint(|x)")
        self.assertEqual(self.keys(slash), "x = 1\n# print(x)")
        self.assertEqual(self.keys(slash), "x = 1\nprint(x)")
        self.put("def f():\n|    a = 1\n\n        b = 2\n|    return a")
        self.assertEqual(self.keys(slash), "def f():\n    # a = 1\n\n    #     b = 2\n    return a")  # 가장 얕은 들여쓰기 자리에 맞춤
        self.assertEqual(self.ed.textCursor().selectedText().count("\u2029"), 3)  # 고른 줄은 고른 채로 남음
        self.assertEqual(self.keys(slash), "def f():\n    a = 1\n\n        b = 2\n    return a")
        self.put("|# 설명\nx = 1|")
        self.assertEqual(self.keys(slash), "# # 설명\n# x = 1")  # 주석이 아닌 줄이 섞이면 모두 주석으로 만듦
        self.ed.undo()
        self.assertEqual(self.ed.toPlainText(), "# 설명\nx = 1")  # 한 번에 되돌아감
        self.put("#x = 1|")
        self.assertEqual(self.keys(slash), "x = 1")  # 공백 없이 붙은 # 도 풂
        self.put("\n|\n")
        self.assertEqual(self.keys(slash), "\n\n")  # 빈 줄만 고르면 아무것도 하지 않음

    def compose(self, text):
        """한글은 키가 아니라 입력기가 조합해서 확정한 글자로 들어옴."""
        for ch in text:
            QApplication.sendEvent(self.ed, QInputMethodEvent(ch, []))
            done = QInputMethodEvent()
            done.setCommitString(ch)
            QApplication.sendEvent(self.ed, done)

    def put(self, text):
        """| 를 뺀 글을 넣고 | 자리에 커서를 둠. | 가 둘이면 그 사이를 선택함."""
        parts = text.split("|")
        self.ed.setPlainText("".join(parts))
        cursor = self.ed.textCursor()
        cursor.setPosition(len(parts[0]))
        cursor.setPosition(len("".join(parts[:-1])), QTextCursor.MoveMode.KeepAnchor)
        self.ed.setTextCursor(cursor)

    def view(self):
        """커서와 선택 양 끝을 | 로 표시한 글."""
        text, cursor = self.ed.toPlainText(), self.ed.textCursor()
        for spot in sorted({cursor.selectionStart(), cursor.selectionEnd()}, reverse=True):
            text = text[:spot] + "|" + text[spot:]
        return text

    def typed(self, start, *steps):
        self.put(start)
        self.keys(*steps)
        return self.view()

    def test_tab_inserts_spaces_up_to_the_next_stop(self):
        self.assertEqual(self.keys(Qt.Key.Key_Tab, "x", Qt.Key.Key_Tab, "# t"), "    x   # t")
        self.assertNotIn("\t", self.ed.toPlainText())

    def test_enter_keeps_indent_and_adds_a_level_after_colon(self):
        typed = self.keys("def f(x):", Qt.Key.Key_Return, "if x:  ", Qt.Key.Key_Return, "return 1", Qt.Key.Key_Return, "y = 2")
        self.assertEqual(typed, "def f(x):\n    if x:  \n        return 1\n        y = 2")

    def test_backspace_in_indent_removes_one_level(self):
        typed = self.keys("if x:", Qt.Key.Key_Return, "if y:", Qt.Key.Key_Return, Qt.Key.Key_Backspace, "a", Qt.Key.Key_Return,
                          "  ", Qt.Key.Key_Backspace, "b", Qt.Key.Key_Backspace, "c", Qt.Key.Key_Return, Qt.Key.Key_Backspace, "d")
        self.assertEqual(typed, "if x:\n    if y:\n    a\n    c\nd")

    def test_shift_tab_outdents_and_tab_indents_selected_lines(self):
        self.ed.setPlainText("a\n    b\n      c")
        cursor = self.ed.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.ed.setTextCursor(cursor)
        self.assertEqual(self.keys(Qt.Key.Key_Backtab), "a\n    b\n  c")
        self.assertEqual(self.keys((Qt.Key.Key_Tab, SHIFT)), "a\n    b\nc")
        self.ed.selectAll()
        self.assertEqual(self.keys(Qt.Key.Key_Tab), "    a\n        b\n    c")
        self.assertEqual(self.keys(Qt.Key.Key_Backtab), "a\n    b\nc")

    def test_paste_is_blocked(self):
        data = QMimeData()
        data.setText("if x:\r\n\treturn 1")
        self.assertFalse(self.ed.canInsertFromMimeData(data))
        self.ed.insertFromMimeData(data)
        QGuiApplication.clipboard().setText("붙여넣을 글")
        self.ed.paste()
        self.assertEqual(self.ed.toPlainText(), "")

    def test_fixed_pitch_font_and_no_completer(self):
        self.assertTrue(self.ed.font().fixedPitch())
        self.assertFalse(hasattr(self.ed, "completer"))
        self.ed.setReadOnly(True)
        self.assertEqual(self.keys(Qt.Key.Key_Tab, Qt.Key.Key_Return, "("), "")  # 잠겨 있을 때는 키로도 바뀌지 않음

    def test_opening_bracket_or_quote_brings_its_closer(self):
        for ch, pair in (("(", "(|)"), ("[", "[|]"), ("{", "{|}"), ('"', '"|"'), ("'", "'|'")):
            self.assertEqual(self.typed("|", ch), pair)
            self.assertEqual(self.typed("x = | + 1", ch), "x = %s + 1" % pair)
        self.assertEqual(self.typed("f(a|, b)", "["), "f(a[|], b)")
        self.assertEqual(self.typed("d = {|: 1}", '"'), 'd = {"|": 1}')
        self.assertEqual(self.typed("x[|]", "("), "x[(|)]")

    def test_no_closer_when_text_follows_the_cursor(self):
        for ch in "([{\"'":
            self.assertEqual(self.typed("x = |name", ch), "x = %s|name" % ch)
        self.assertEqual(self.typed('print(|"a")', "("), 'print((|"a")')

    def test_opening_bracket_or_quote_wraps_the_selection(self):
        self.assertEqual(self.typed("x = |a + b|", "("), "x = (|a + b|)")
        self.assertEqual(self.typed("x = |a + b|", "(", '"'), 'x = ("|a + b|")')  # 감싼 글이 선택된 채라 이어서 또 감쌈
        self.assertEqual(self.typed("|a\nb|", "["), "[|a\nb|]")
        self.assertEqual(self.typed("x = |a + b|", ")"), "x = )|")  # 닫는 괄호는 여느 글자처럼 선택한 글을 바꿈

    def test_closing_bracket_steps_over_the_one_already_there(self):
        self.assertEqual(self.typed("f(a|)", ")"), "f(a)|")
        self.assertEqual(self.typed("x[{1|}]", "}", "]"), "x[{1}]|")
        self.assertEqual(self.typed("f(a|]", ")"), "f(a)|]")
        self.assertEqual(self.typed("f(g(a|)", ")"), "f(g(a)|)")  # 닫는 괄호가 모자라면 새로 넣음
        self.assertEqual(self.typed('print("(" + x|)  # (', ")"), 'print("(" + x)|  # (')  # 문자열과 주석 안의 괄호는 세지 않음

    def test_quote_closes_only_where_a_string_starts(self):
        cases = (('s = "abc|"', '"', 's = "abc"|'),  # 뒤가 같은 따옴표면 넘어감
                 ('s = "abc|', '"', 's = "abc"|'),  # 문자열을 닫는 중
                 ("x1|", '"', 'x1"|'),
                 ("don|", "'", "don'|"),
                 ('""|', '"', '"""|'),
                 ("# 메모 # |", '"', '# 메모 # "|'),  # 주석은 줄 끝까지
                 ('"1 + |"', "'", '"1 + \'|"'),  # 문자열 안의 아포스트로피
                 ("'it\\|'", "'", "'it\\'|'"),  # 역슬래시 뒤는 넘어가지 않고 넣음
                 ('print("#", |)', "'", 'print("#", \'|\')'),  # 문자열 안의 # 은 주석이 아님
                 ('x = "it\'s" + |', "'", 'x = "it\'s" + \'|\''),
                 ("print(f|)", '"', 'print(f"|")'),  # 문자열 접두사 뒤
                 ("x = rb|", "'", "x = rb'|'"),
                 ("x = ab|", '"', 'x = ab"|'))
        for start, key, expected in cases:
            self.assertEqual(self.typed(start, key), expected)

    def test_brackets_inside_strings_and_comments_are_plain_characters(self):
        """문자열과 주석 안의 괄호는 짝을 맞출 까닭이 없는 글자라 닫지도, 넘어가지도, 함께 지우지도 않음."""
        cases = (('print("|")', "(", 'print("(|")'),
                 ('print(f"|")', "{", 'print(f"{|")'),
                 ('s = "abc |', "[", 's = "abc [|'),
                 ('"a|)"', ")", '"a)|)"'),
                 ("# 1|", ")", "# 1)|"),
                 ("# |", "(", "# (|"),
                 ("# (a|)", ")", "# (a)|)"),
                 ('s = "(|)"', Qt.Key.Key_Backspace, 's = "|)"'),
                 ("# [|]", Qt.Key.Key_Backspace, "# |]"),
                 ('s = "{|}"', Qt.Key.Key_Return, 's = "{\n|}"'),
                 ("# it|'s", "'", "# it'|'s"),  # 주석 안의 따옴표도 넘어가지 않음
                 ('"it|\'s"', "'", '"it\'|\'s"'),  # 문자열을 닫는 따옴표가 아니면 넘어가지 않음
                 ('print("a", |"b")', '"', 'print("a", "|"b")'))  # 다른 문자열을 여는 따옴표 앞
        for start, key, expected in cases:
            self.assertEqual(self.typed(start, key), expected)

    def test_triple_quoted_string_stays_a_string_on_every_line_it_covers(self):
        """삼중 따옴표로 연 문자열은 닫을 때까지 여러 줄이 문자열임. 그 안의 괄호와 따옴표는 친 대로 들어가고 바깥 괄호의 짝을 세는 데 들지 않음."""
        enter = Qt.Key.Key_Return
        typed = self.typed("|", 'print("""첫째 줄', enter, '둘째 줄""")', enter, 'print("끝")')
        self.assertEqual(typed, 'print("""첫째 줄\n둘째 줄""")\nprint("끝")|')  # 닫는 줄에서 친 괄호는 먼저 들어와 있던 괄호를 넘어감
        self.assertEqual(self.typed("|", "x = ['''a", enter, "b''', 1]"), "x = ['''a\nb''', 1]|")
        for line in ("print('''it's''')", 'print("""키 5" 이상""")', 'print("""그는 "네" 라고 함""")'):  # 한 줄 안에서도 따옴표 하나로는 닫히지 않음
            self.assertEqual(self.typed("|", line), line + "|")
        for line in ("(that's all)", "rock 'n roll", '값이 "a 일 때 [예', "f(x)"):  # 문서 문자열의 가운데 줄
            self.assertEqual(self.typed('"""\n|\n"""', line), '"""\n%s|\n"""' % line)
        self.assertEqual(self.typed('"""\n(|)\n"""', Qt.Key.Key_Backspace), '"""\n|)\n"""')
        self.assertEqual(self.typed('"""\n{|}\n"""', enter), '"""\n{\n|}\n"""')
        self.assertEqual(self.typed('"""\n끝"""|', " + str("), '"""\n끝""" + str(|)')  # 닫은 뒤는 다시 코드
        typed = self.typed("|", "def f(a):", enter, '"""', enter, "Return a (that's all)", enter, '"""', enter, "return a")
        self.assertEqual(typed, 'def f(a):\n    """\n    Return a (that\'s all)\n    """\n    return a|')

    def test_string_typed_in_front_of_another_string_keeps_its_closing_quote(self):
        """닫는 따옴표를 쳤는데 바로 뒤가 다른 문자열을 여는 따옴표면 넘어가지 않고 새로 넣음. 넘어가면 따옴표가 하나 모자라게 됨."""
        cases = (('names = ["kim", |"park"]', '"lee", ', 'names = ["kim", "lee", |"park"]'),
                 ('print(|"점")', '"총", ', 'print("총", |"점")'),
                 ("return |'b'", "'a' + ", "return 'a' + |'b'"),
                 ('d = {|"b": 2}', '"a": 1, ', 'd = {"a": 1, |"b": 2}'),
                 ('print(|f"{x}")', '"a", ', 'print("a", |f"{x}")'),
                 ('x = ["a|", "b"]', '"', 'x = ["a"|, "b"]'),  # 따옴표의 짝이 맞는 줄에서는 넘어감
                 ('x = [| "b"]', '"a",', 'x = ["a",| "b"]'))
        for start, keys, expected in cases:
            self.assertEqual(self.typed(start, keys), expected)

    def test_backspace_between_an_empty_pair_removes_both(self):
        for left, right in ("()", "[]", "{}", '""', "''"):
            self.assertEqual(self.typed("x = %s|%s" % (left, right), Qt.Key.Key_Backspace), "x = |")
        self.assertEqual(self.typed("f(a|)", Qt.Key.Key_Backspace), "f(|)")
        self.assertEqual(self.typed("x = (|]", Qt.Key.Key_Backspace), "x = |]")
        self.assertEqual(self.typed('"a"|"b"', Qt.Key.Key_Backspace), '"a|"b"')  # 닫는 따옴표와 여는 따옴표가 맞닿은 자리
        self.assertEqual(self.typed("    (|)", Qt.Key.Key_Backspace, Qt.Key.Key_Backspace), "|")  # 들여쓰기는 전처럼 한 단계씩

    def test_enter_between_empty_brackets_puts_the_closer_on_its_own_line(self):
        self.assertEqual(self.typed("    x = [|]", Qt.Key.Key_Return, "1,"), "    x = [\n        1,|\n    ]")
        self.assertEqual(self.typed("def f(|):", Qt.Key.Key_Return), "def f(\n    |\n):")
        self.assertEqual(self.typed("d = {|}", Qt.Key.Key_Enter), "d = {\n    |\n}")
        self.assertEqual(self.typed("f(|a)", Qt.Key.Key_Return), "f(\n|a)")  # 사이에 글이 있으면 전과 같음
        self.assertEqual(self.typed('s = "|"', Qt.Key.Key_Return), 's = "\n|"')

    def test_one_keystroke_is_one_undo(self):
        undo = (Qt.Key.Key_Z, CTRL)
        self.assertEqual(self.typed("|", "print", "("), "print(|)")
        self.assertEqual(self.keys(undo), "print")  # 앞서 친 글은 남음
        for start, key, changed in (("x = |a + b|", "(", "x = (a + b)"), ("x = (|)", Qt.Key.Key_Backspace, "x = "),
                                    ("x = (|)", Qt.Key.Key_Return, "x = (\n    \n)")):
            self.put(start)
            self.assertEqual(self.keys(key), changed)
            self.assertEqual(self.keys(undo), start.replace("|", ""))
        redo = (Qt.Key.Key_Z, CTRL | SHIFT)  # 줄 나눔을 다시 실행하면 커서가 가운데 줄에 놓임
        self.assertEqual(self.typed("d = {|}", Qt.Key.Key_Return, undo, redo, "1"), "d = {\n    1|\n}")

    def test_bracket_left_open_for_a_later_line_brings_no_closer(self):
        """여는 괄호가 아랫줄에서 닫히는 문장의 첫 줄에서는 같은 종류의 새 괄호를 닫지 않음. 닫으면 친 닫는 괄호가 넘어가지 못하고 하나 남음."""
        cases = (('print("합:",|\n      b)', " len(a),", 'print("합:", len(a),|\n      b)'),
                 ("print(|____|,\n      sep='')", "len(a)", "print(len(a)|,\n      sep='')"),
                 ("x = [|____|,\n     2]", "a[0]", "x = [a[0]|,\n     2]"),
                 ('d = {"a": 1,|\n     "b": 2}', ' "c": {"x": 1},', 'd = {"a": 1, "c": {"x": 1},|\n     "b": 2}'),
                 ("x = max(|\n    b,\n)", "a[0](", "x = max(a[0](|\n    b,\n)"),  # 다른 종류의 괄호는 전처럼 닫음
                 ("x = max(\n    |\n)", "len(a),", "x = max(\n    len(a),|\n)"),  # 짝이 맞는 가운데 줄
                 ('print("(", |)', "(", 'print("(", (|))'))  # 문자열 안의 괄호는 세지 않음
        for start, keys, expected in cases:
            self.assertEqual(self.typed(start, keys), expected)

    def test_filling_a_blank_keeps_brackets_balanced(self):
        """빈칸을 지운 자리는 원래 있던 닫는 괄호 앞임. 안에서 연 괄호는 닫히고 원래 있던 닫는 괄호는 하나로 남음."""
        self.assertEqual(self.typed("print(|____|)", "len(a"), "print(len(a|))")
        self.assertEqual(self.typed("print(|____|)", "len(a))"), "print(len(a))|")  # 닫는 괄호를 버릇대로 다 쳐도 같음
        self.assertEqual(self.typed("    for j in range(|):", "len(letters)"), "    for j in range(len(letters)|):")
        self.assertEqual(self.typed('print(letters[|], end=" ")', "(i + j) % 9"), 'print(letters[(i + j) % 9|], end=" ")')
        self.assertEqual(self.typed("while |:", 'text != ""'), 'while text != ""|:')

    def test_typing_over_a_selected_blank_replaces_it_instead_of_wrapping_it(self):
        """빈칸을 선택하고 괄호나 따옴표로 시작하는 답을 쳐도 빈칸이 감싸여 남지 않음. 빈칸을 지운 자리에 친 것과 같음."""
        cases = (("print(line, end=|____|)", '""', 'print(line, end=""|)'),
                 ("self.stack = |____|", "[]", "self.stack = []|"),
                 ('with open("a.txt", |____|, encoding="utf-8") as f:', '"r"', 'with open("a.txt", "r"|, encoding="utf-8") as f:'),
                 ("d = |____|", '{"a": 1}', 'd = {"a": 1}|'),
                 ('if __name__ == "|____|":', '__main__"', 'if __name__ == "__main__"|:'),
                 ("x = |____|(a)", "(", "x = (|(a)"),  # 뒤에 글자가 이어지면 닫지 않음
                 ("x = |____ + 1|", "(", "x = (|____ + 1|)"))  # 빈칸보다 넓게 선택하면 감쌈
        for start, keys, expected in cases:
            self.assertEqual(self.typed(start, keys), expected)
        self.put("self.stack = |____|")  # 끝에서 앞으로 선택해도 같음
        cursor = self.ed.textCursor()
        cursor.setPosition(cursor.selectionEnd())
        cursor.setPosition(cursor.position() - 4, QTextCursor.MoveMode.KeepAnchor)
        self.ed.setTextCursor(cursor)
        self.assertEqual(self.keys("[]"), "self.stack = []")
        for start, key, changed in (("d = |____|", "{", "d = {|}"), ('x = "|____|"', '"', 'x = ""|')):  # 뒤와 같은 닫는 글자를 치면 빈칸을 지우고 넘어감
            self.assertEqual(self.typed(start, key), changed)
            self.assertEqual(self.keys((Qt.Key.Key_Z, CTRL)), start.replace("|", ""))  # 한 번 친 것은 한 번에 되돌아감

    def test_typing_python_the_usual_way_gives_what_was_typed(self):
        """닫는 글자가 먼저 들어가 있어도 평소 치는 순서대로 끝까지 치면 친 글이 그대로 나옴."""
        lines = ("def solution(a, b):", 'print("합:", a + b)', 'd = {"a": [1, 2]}', "s = 'it\\'s'", '"""두 수의 합을 돌려줌."""',
                 'print(f"{a} + {b} = {a + b}")', "print('{}점'.format(scores[len(scores) - 1]))", 'x = ["", (1, 2), {}]',
                 "# 주석의 (괄호)와 '따옴표'도 친 대로 나옴", 'if s[i] == "(":', 'pairs = {")": "(", "}": "{", "]": "["}',
                 'return text + " (" + name + ")"', 'm = re.findall(r"\\d+(?:\\.\\d+)?", text)', '"""설명 (예: f(1))"""')
        for line in lines:
            self.assertEqual(self.typed("|", line), line + "|")
        typed = self.typed("|", "def solution(a, b):", Qt.Key.Key_Return, '"""', Qt.Key.Key_Return, "두 수의 합", Qt.Key.Key_Return, '"""',
                           Qt.Key.Key_Return, "return (a + b)")
        self.assertEqual(typed, 'def solution(a, b):\n    """\n    두 수의 합\n    """\n    return (a + b)|')

    def type_out(self, text):
        """사람이 치듯 한 글자씩 침. 줄을 바꾸면 편집기가 넣은 들여쓰기에서 Backspace 나 공백으로 맞추고, 닫는 글자까지 전부 침.
        빈 괄호 사이에서 줄을 바꿔 닫는 괄호가 먼저 내려가 있으면 그 줄은 아래 화살표로 내려가 나머지만 침."""
        self.ed.clear()
        for number, line in enumerate(text.split("\n")):
            below = self.ed.textCursor().block().next().text()
            if number and below.strip() and line.startswith(below):
                self.keys(Qt.Key.Key_Down, Qt.Key.Key_End, line[len(below):])
                continue
            body = line.lstrip(" ")
            if number:
                self.keys(Qt.Key.Key_Return)
            while body and self.ed.textCursor().positionInBlock() > len(line) - len(body):
                self.keys(Qt.Key.Key_Backspace)
            if body:
                self.keys(" " * (len(line) - len(body) - self.ed.textCursor().positionInBlock()), body)
        return [line.rstrip() for line in self.ed.toPlainText().split("\n")]  # 빈 줄에 남은 들여쓰기는 보지 않음

    def test_typing_the_bank_solutions_the_usual_way_gives_the_same_text(self):
        nested = 'data = {\n    "a": [\n        1,\n    ],\n}\nprint(data)'
        self.assertEqual(self.type_out(nested), nested.split("\n"))
        for sid in study.all_set_ids():
            bank = study.load_set(sid)
            for spec in bank["problems"]:
                answer = bank["secrets"][spec["id"] + "/solution.py"].rstrip("\n")
                self.assertEqual(self.type_out(answer), answer.split("\n"), "%s/%s" % (sid, spec["id"]))

    def test_filling_every_blank_of_the_bank_gives_the_model_answer(self):
        """빈칸 채우기 문항의 빈칸을 앞에서부터 하나씩 선택하고 모범 답안의 그 자리 글을 침."""
        for sid in study.all_set_ids():
            bank = study.load_set(sid)
            for spec in bank["problems"]:
                if spec["type"] != "fill":
                    continue
                starter = study.read_text(os.path.join(spec["dir"], "starter.py")).rstrip("\n")
                answer = bank["secrets"][spec["id"] + "/solution.py"].rstrip("\n")
                self.ed.setPlainText(starter)
                for number, (before, after) in enumerate(zip(starter.split("\n"), answer.split("\n"))):
                    parts = before.split("____")
                    for piece in re.fullmatch("(.*?)".join(map(re.escape, parts)), after).groups():
                        block = self.ed.document().findBlockByNumber(number)
                        cursor = self.ed.textCursor()
                        cursor.setPosition(block.position() + block.text().index("____"))
                        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 4)
                        self.ed.setTextCursor(cursor)
                        self.keys(piece or Qt.Key.Key_Delete)
                self.assertEqual(self.ed.toPlainText(), answer, "%s/%s" % (sid, spec["id"]))

    def test_characters_outside_the_basic_plane_do_not_shift_the_cursor(self):
        """Qt 는 이모지를 두 칸으로 세지만, 그 뒤에서도 커서 앞뒤의 글자를 바로 봄."""
        self.ed.setPlainText('print("\U0001F389")')
        cursor = self.ed.textCursor()
        cursor.setPosition(len('print("') + 2)
        self.ed.setTextCursor(cursor)
        self.assertEqual(self.keys('"', ")"), 'print("\U0001F389")')  # 닫는 따옴표와 괄호를 넘어감
        self.assertEqual(self.ed.textCursor().position(), len('print("")') + 2)
        self.assertEqual(self.keys(" + (", '"'), 'print("\U0001F389") + ("")')

    def test_pairs_follow_the_typed_character_not_the_key_code(self):
        """괄호 키의 코드는 자판 배열과 입력기에 따라 다르고, 글자 없이 오는 키 이벤트도 있음."""
        none, altgr = Qt.KeyboardModifier.NoModifier, CTRL | Qt.KeyboardModifier.AltModifier
        cases = ((Qt.Key.Key_unknown, none, "(", "(|)"),  # 입력기를 거쳐 키 코드 없이 온 글자
                 (Qt.Key.Key_8, altgr, "[", "[|]"),  # 독일어 자판의 AltGr+8
                 (Qt.Key.Key_ParenLeft, none, "", "|"),
                 (Qt.Key.Key_ParenLeft, CTRL | SHIFT, "(", "|"))  # Ctrl 조합은 글자를 넣지 않음
        for key, modifiers, text, expected in cases:
            self.put("|")
            QApplication.sendEvent(self.ed, QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text))
            self.assertEqual(self.view(), expected)
        self.assertEqual(self.typed("|", 'print("안녕'), 'print("안녕|")')  # 조합해 넣은 한글은 따옴표 사이에 들어감
        self.assertEqual(self.typed("|", 'print("안녕")'), 'print("안녕")|')

    def test_other_answer_boxes_do_not_close_brackets(self):
        """출력 예측과 단답은 답 글자를 그대로 적는 칸이라 닫는 글자가 따라 들어가면 오답이 됨."""
        panel = TextPanel()
        QTest.keyClicks(panel.multi, "[('")
        QTest.keyClicks(panel.single, "{\"")
        self.assertEqual((panel.multi.toPlainText(), panel.single.text()), ("[('", "{\""))


class ThemeTest(GuiTest):
    def setUp(self):
        self.system = "light"  # 운영체제 설정을 흉내 냄
        patch = mock.patch.object(theme, "system_scheme", lambda: self.system)
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()

    def test_text_is_readable_and_unit_colors_differ_in_both_themes(self):
        self.assertEqual(set(theme.LIGHT), set(theme.DARK))
        pairs = [("ink", "bg"), ("ink", "surface"), ("ink", "surface_alt"), ("ink", "hover"), ("heading", "bg"), ("heading", "surface"),
                 ("muted", "bg"), ("muted", "surface"), ("primary_ink", "primary"), ("primary_ink", "primary_hover"),
                 ("selection_ink", "selection"), ("ink", "text_selection"), ("ink", "notice_bg"), ("link", "notice_bg"), ("ink", "code_bg"),
                 ("ink", "codebox_bg"), ("ink", "table_head"), ("doc_heading", "surface"), ("link", "surface"), ("link", "bg"),
                 ("ink", "selection"), ("muted", "surface_alt"),  # 고른 보기 카드의 글, 번호 배지의 숫자
                 ("placeholder", "surface")]  # 입력칸의 예시와 실행 결과 칸의 안내
        pairs += [(name, "surface") for name in ("ok", "wrong", "blank", "up", "retry")]
        pairs += [("unit_%s_ink" % name, "unit_" + name) for name in theme.UNIT]
        for scheme, tokens in theme.TOKENS.items():
            for ink, back in pairs:
                self.assertGreaterEqual(contrast(tokens[ink], tokens[back]), 4.5, "%s: %s / %s" % (scheme, ink, back))
            groups = (["unit_" + name for name in theme.UNIT], ["ok", "wrong", "blank"], ["up", "ok", "muted", "retry"])
            for group in groups:  # 단원 상태색, 결과색, 판정색은 같은 묶음 안에서 서로 구분됨
                for one, other in itertools.combinations([QColor(tokens[name]) for name in group], 2):
                    gap = abs(one.red() - other.red()) + abs(one.green() - other.green()) + abs(one.blue() - other.blue())
                    self.assertGreater(gap, 90, "%s: %s / %s" % (scheme, one.name(), other.name()))
            for back in ("bg", "surface"):  # 미진단 칸은 바탕과 색이 비슷해 테두리로 구분함
                self.assertGreaterEqual(contrast(tokens["unit_none_edge"], tokens[back]), 3, "%s: unit_none_edge / %s" % (scheme, back))
        self.assertIn("QLabel#unit_none { border: 1px solid %s; }" % theme.color("unit_none_edge"), APP.styleSheet())
        for back in theme.AVATARS:  # 이니셜 원의 글자
            self.assertGreaterEqual(contrast(theme.BRAND[2], back), 4.5, back)

    def test_dark_theme_keeps_guide_text_bright_and_panels_apart(self):
        """어두운 바탕에서는 회색 글자가 가늘어 보여서 안내 글을 7:1 이상으로, 꺼진 단추의 글자도 4.5:1 이상으로 둠."""
        dark = theme.DARK
        for back in ("bg", "surface", "surface_alt"):
            self.assertGreaterEqual(contrast(dark["muted"], dark[back]), 7, back)
        for ink, back in (("faint", "bg"), ("faint", "surface"), ("primary_off_ink", "primary_off"), ("placeholder", "bg")):
            self.assertGreaterEqual(contrast(dark[ink], dark[back]), 4.5, "%s / %s" % (ink, back))
        for ink in ("muted", "placeholder", "faint"):  # 본문 글자보다는 어두워서 덜 중요한 글로 읽힘
            self.assertGreater(contrast(dark["ink"], dark["surface"]), contrast(dark[ink], dark["surface"]) + 3, ink)
        for back in ("bg", "surface"):  # 판과 입력칸의 테두리가 바탕에서 보임
            self.assertGreaterEqual(contrast(dark["border"], dark[back]), 1.5, back)

    def test_button_cycles_system_light_dark_and_the_choice_is_remembered(self):
        self.boot()
        home = self.win.home
        self.assertEqual((home.theme_btn.text(), theme.state["scheme"]), ("테마: 시스템", "light"))
        click(home.theme_btn)
        self.assertEqual((home.theme_btn.text(), theme.state["scheme"]), ("테마: 밝게", "light"))
        click(home.theme_btn)
        self.assertEqual((home.theme_btn.text(), theme.state["scheme"]), ("테마: 어둡게", "dark"))
        self.assertEqual(self.settings.value("theme"), "dark")
        self.assertIn(theme.DARK["bg"], APP.styleSheet())
        again = MainWindow(self.settings, lambda root, user: (self.git, ""))  # 다시 켜면 고른 테마로 열림
        self.assertEqual((again.home.theme_btn.text(), theme.state["scheme"]), ("테마: 어둡게", "dark"))
        again.deleteLater()
        click(home.theme_btn)
        self.assertEqual((home.theme_btn.text(), theme.state["scheme"]), ("테마: 시스템", "light"))
        self.assertIn(theme.LIGHT["bg"], APP.styleSheet())

    def test_system_mode_follows_the_os_setting(self):
        hints = APP.styleHints()
        if not hasattr(hints, "colorSchemeChanged"):
            self.skipTest("Qt 6.5 미만은 운영체제 설정이 바뀐 것을 알려 주지 않습니다")
        self.boot()
        self.system = "dark"
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        self.assertEqual((theme.state["mode"], theme.state["scheme"]), ("system", "dark"))
        self.assertIn(theme.DARK["ink"], self.win.round_page.body.document().defaultStyleSheet())
        click(self.win.home.theme_btn)  # 밝게로 정해 두면 따라가지 않음
        self.assertEqual(theme.state["scheme"], "light")
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        self.assertEqual((theme.state["mode"], theme.state["scheme"]), ("light", "light"))

    def test_result_buttons_stay_locked_when_restyled_while_a_job_runs(self):
        """제출이 도는 중에 글자 크기나 테마가 바뀌어 결과 화면을 다시 그려도, 잠근 [해설 보기]·[다시 풀기]는 켜지지 않음."""
        self.boot()
        win, result = self.win, self.win.result_page
        click(win.home.action_btn)
        self.submit_round()
        result.listw.setCurrentRow(1)
        buttons = (result.explain_btn, result.retry_btn)
        self.assertTrue(all(button.isEnabled() for button in buttons))
        self.git.delay = 0.5
        click(result.git_btn)
        self.assertIsNotNone(win.job)
        for change in (lambda: win.set_zoom(1), lambda: theme.set_mode("dark")):
            change()
            self.assertFalse(any(button.isEnabled() for button in buttons))
        self.idle()
        self.git.delay = 0
        self.choose("ok")
        self.assertTrue(all(button.isEnabled() for button in buttons))

    def test_dark_theme_reaches_open_screens_and_leaves_no_light_patches(self):
        self.boot()
        win, page, result = self.win, self.win.round_page, self.win.result_page
        self.make_round("r94", [self.first(type="choice", multi=False), self.first(type="output"), self.first(type="return")])
        win.open_round("r94")
        self.fill(self.select(lambda it: it["kind"] == "code"), "def solution(*args):\n    return None\n")
        click(page.run_btn)
        self.idle()
        self.assertGreater(bright_share(win), 0.5)  # 밝은 테마에서는 화면 대부분이 밝음
        cards = page.choice_panel.buttons  # 밝은 테마에서 만든 보기 카드
        self.assertIn(theme.LIGHT["ink"], cards[0].doc.defaultStyleSheet())
        page.body.setFixedHeight(120)  # 본문을 반쯤 내려 둠
        pump()
        bar = page.body.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        place = bar.value()
        self.assertGreater(place, 0)
        theme.set_mode("dark")  # 화면을 띄워 둔 채로 바꿈
        pump()
        self.assertEqual(bar.value(), place)  # 읽던 자리는 남음
        page.body.setMaximumHeight(16777215)
        pump()
        for card in cards:  # 이미 만들어 둔 카드도 어두운 테마의 글자색으로 다시 칠함
            self.assertIn(theme.DARK["ink"], card.doc.defaultStyleSheet())
            self.assertNotIn(theme.LIGHT["ink"], card.doc.defaultStyleSheet())

        sheet = APP.styleSheet() + page.body.document().defaultStyleSheet()
        self.assertIn(theme.DARK["ink"], page.body.document().defaultStyleSheet())
        self.assertTrue(all(gray(value) <= 200 for value in backgrounds(sheet)), backgrounds(sheet))
        for name in ("bg", "surface", "surface_alt", "hover", "notice_bg", "code_bg", "codebox_bg", "table_head", "selection", "track"):
            self.assertNotIn(theme.LIGHT[name], sheet, name)

        def check(widget, *browsers):
            """밝은 조각이 없는지 봄. browsers 는 바탕색을 가진 조각(표 머리, 구역 띠, 코드 상자)이 든 본문."""
            self.assertEqual(bright_share(widget), 0, widget)
            for browser in browsers:
                shown = backgrounds(browser.document().toHtml())
                self.assertTrue(shown and all(gray(value) <= 200 for value in shown), shown)

        check(win, page.body, page.code_panel.console)  # 코드 문항: 본문의 표와 인라인 코드, 실행 결과 표
        editor = page.code_panel.editor.grab().toImage()
        self.assertEqual(editor.pixelColor(editor.width() // 2, editor.height() - 12).name(), theme.EDITOR["bg"])
        for kind in ("choice", "output"):
            self.select(lambda it: it["type"] == kind)
            check(win)
        self.submit_round()
        self.assertIs(self.page(), result)
        check(win)
        for row, item in enumerate(result.view["items"], 1):
            self.assertEqual(result.listw.item(row).foreground().color().name(), theme.DARK[theme.result_label(item["state"])[1]])
            result.listw.setCurrentRow(row)
            result.reveal()
            check(win, result.detail)  # 구역 띠, 코드 상자, 해설
        click(result.home_btn)
        check(win)
        click(win.home.team_btn)  # 팀 현황: 내 카드와 빈 자리 안내
        self.assertEqual((len(win.team_page.cards), win.team_page.empty is not None), (1, True))
        check(win)
        click(win.team_page.home_btn)
        big = win.home.foot.font()  # 획이 굵어야 가장자리가 섞이지 않은 링크 색 픽셀이 글꼴과 플랫폼에 상관없이 생김
        big.setPixelSize(40)
        win.home.foot.setFont(big)
        win.home.foot.resize(win.home.foot.sizeHint())
        foot = win.home.foot.grab().toImage()  # 링크 색은 글을 넣을 때 굳으므로 테마가 바뀌면 다시 넣어야 함
        colors = {foot.pixelColor(x, y).name() for x in range(foot.width()) for y in range(foot.height())}
        self.assertIn(theme.DARK["link"], colors)
        self.assertNotIn(theme.LIGHT["link"], colors)
        boxes = [win.ask("알림", "글", (("확인", "ok"), ("닫기", "")), detail="자세한 내용", link="https://example.com/pr"),
                 dialogs.IdDialog(win, lambda user: None), dialogs.ErrorDialog("오류 내용", None, errors.ISSUE_URL)]
        for box in boxes:
            box.show()
            pump()
            check(box)
            box.close()

        win.show_result("r94")
        result.listw.setCurrentRow(result.listw.count() - 1)
        result.reveal()
        result.detail.setFixedHeight(120)
        pump()
        bar = result.detail.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        place = bar.value()
        self.assertGreater(place, 0)
        theme.set_mode("light")  # 되돌리면 밝은 색으로 돌아오고 읽던 자리는 남음
        pump()
        self.assertEqual(bar.value(), place)
        result.detail.setMaximumHeight(16777215)
        pump()
        self.assertGreater(bright_share(win), 0.5)
        self.assertIn(theme.LIGHT["ink"], result.detail.document().defaultStyleSheet())
        self.assertEqual(result.listw.item(1).foreground().color().name(), theme.LIGHT[theme.result_label(result.view["items"][0]["state"])[1]])


SAMPLE = "def solution(numbers):\n    total = 0\n    for n in numbers:\n        total += n\n    Total = total\n    return Total\n"


def find_marks(editor):
    """찾기가 편집기에 칠한 곳을 (줄 번호, 글, 진하게 칠했는지)로 돌려줌."""
    colors = {(theme.EDITOR[name], theme.EDITOR[name + "_ink"]): name == "find_current" for name in ("find", "find_current")}  # 바탕과 글자색
    return [(mark.cursor.blockNumber() + 1, mark.cursor.selectedText(),
             colors[mark.format.background().color().name(), mark.format.foreground().color().name()]) for mark in editor.extraSelections()]


class LineNumberTest(unittest.TestCase):
    def setUp(self):
        theme.set_mode("light")
        self.addCleanup(theme.set_mode, "system")
        self.ed = CodeEditor()
        self.ed.setFont(theme.code_font())
        self.ed.resize(360, 200)
        self.ed.show()
        self.addCleanup(self.ed.close)
        pump()

    def lines(self, count):
        self.ed.setPlainText("\n".join("line %d" % number for number in range(1, count + 1)))
        pump()

    def drawn(self):
        """줄 번호 칸을 다시 그리게 하고, 그려진 번호를 위에서부터 (글자, 글자색, 오른쪽 끝, 글자 크기)로 돌려줌."""
        seen, real = [], widgets.QPainter.drawText

        def spy(painter, point, text):
            seen.append((text, painter.pen().color().name(), point.x() + painter.fontMetrics().horizontalAdvance(text), painter.font().pixelSize()))
            return real(painter, point, text)

        with mock.patch.object(widgets.QPainter, "drawText", spy):
            self.ed.numbers.grab()
        return seen

    def test_width_follows_the_digit_count_and_never_drops_below_two_digits(self):
        strip, char, widths = self.ed.numbers, self.ed.fontMetrics().horizontalAdvance("9"), {}
        for count in (1, 9, 99, 100, 999, 1000):
            self.lines(count)
            widths[count] = strip.width()
            self.assertEqual(self.ed.viewportMargins().left(), strip.width(), count)  # 본문은 칸의 폭만큼 밀림
            self.assertEqual(self.ed.viewport().x(), strip.geometry().right() + 1, count)
        self.assertEqual(widths[1], 2 * strip.PAD + 2 * char)
        self.assertEqual((widths[9], widths[99]), (widths[1], widths[1]))
        self.assertEqual((widths[100] - widths[99], widths[999], widths[1000] - widths[999]), (char, widths[100], char))
        self.lines(3)  # 줄을 지우면 다시 좁아짐
        self.assertEqual(strip.width(), widths[1])

    def test_numbers_start_at_one_are_right_aligned_and_follow_scrolling_and_the_cursor(self):
        self.lines(60)
        ink, dim, strip = theme.EDITOR["ink"], theme.EDITOR["line_no"], self.ed.numbers
        shown = self.drawn()
        rows = int(self.ed.viewport().height() // self.ed.blockBoundingRect(self.ed.firstVisibleBlock()).height())  # 실제로 앉은 줄 높이로 셈
        self.assertEqual([text for text, *_ in shown[:rows]], [str(number) for number in range(1, rows + 1)])  # 오류 내용의 줄 번호처럼 1부터
        self.assertLessEqual(len(shown), rows + 2)  # 보이는 줄만 그림
        self.assertEqual({round(right) for _, _, right, _ in shown}, {strip.width() - strip.PAD})  # 오른쪽 정렬
        self.assertEqual({size for *_, size in shown}, {theme.CODE_PX})
        self.assertEqual([color for _, color, *_ in shown], [ink] + [dim] * (len(shown) - 1))  # 커서는 첫 줄에 있음
        self.ed.verticalScrollBar().setValue(20)
        pump()
        self.assertEqual([text for text, *_ in self.drawn()[:3]], ["21", "22", "23"])
        cursor = self.ed.textCursor()
        cursor.setPosition(self.ed.document().findBlockByNumber(22).position())
        self.ed.setTextCursor(cursor)
        self.assertEqual([text for text, color, *_ in self.drawn() if color == ink], ["23"])
        QTest.keyClick(self.ed, Qt.Key.Key_Return)  # 줄이 늘면 번호도 늘고, 커서가 내려간 줄의 번호가 진해짐
        self.assertEqual(self.ed.blockCount(), 61)
        self.assertEqual([text for text, color, *_ in self.drawn() if color == ink], ["24"])
        image = strip.grab().toImage()
        self.assertEqual(image.pixelColor(2, image.height() // 2).name(), theme.EDITOR["gutter"])  # 칸 바탕은 편집기 바탕과 다른 색
        self.assertEqual(image.pixelColor(image.width() - 1, image.height() // 2).name(), theme.EDITOR["edge"])  # 본문과 맞닿은 쪽에 그은 줄
        self.assertNotEqual(theme.EDITOR["gutter"], theme.EDITOR["bg"])

    def test_numbers_follow_font_size_and_window_size_and_keep_their_colors_in_the_dark_theme(self):
        self.lines(120)
        strip, view = self.ed.numbers, self.ed.viewport()
        before, rows = strip.width(), len(self.drawn())
        self.ed.setFont(theme.code_font(6))  # 글자 크기를 키움
        pump()
        self.assertEqual(strip.width(), 2 * strip.PAD + 3 * self.ed.fontMetrics().horizontalAdvance("9"))
        self.assertGreater(strip.width(), before)
        self.assertEqual(self.ed.viewportMargins().left(), strip.width())
        shown = self.drawn()
        self.assertEqual(({size for *_, size in shown}, {round(right) for _, _, right, _ in shown}), ({theme.CODE_PX + 6}, {strip.width() - strip.PAD}))
        self.assertLess(len(shown), rows)
        self.ed.setFont(theme.code_font())
        self.ed.resize(300, 120)  # 창을 줄임
        pump()
        self.assertEqual((strip.width(), strip.geometry().bottom()), (before, view.geometry().bottom()))
        self.assertLess(len(self.drawn()), rows)
        self.ed.appendPlainText("x" * 200)  # 가로 스크롤 막대가 생기면 칸은 그 위에서 끝남
        pump()
        across = self.ed.horizontalScrollBar()
        self.assertTrue(across.isVisible())
        self.assertLess(strip.geometry().bottom(), across.mapTo(self.ed, QPoint(0, 0)).y())
        self.assertEqual(strip.geometry().bottom(), view.geometry().bottom())
        theme.set_mode("dark")  # 앱 테마를 바꿔도 편집기의 색은 같음
        pump()
        image = strip.grab().toImage()
        self.assertEqual(image.pixelColor(2, image.height() // 2).name(), theme.EDITOR["gutter"])
        self.assertEqual(image.pixelColor(image.width() - 1, image.height() // 2).name(), theme.EDITOR["edge"])
        self.assertEqual({color for _, color, *_ in self.drawn()}, {theme.EDITOR["ink"], theme.EDITOR["line_no"]})

    def test_clicking_the_numbers_changes_nothing_and_the_wheel_scrolls_the_text(self):
        from PyQt6.QtGui import QMouseEvent, QWheelEvent
        self.lines(60)
        strip, bar = self.ed.numbers, self.ed.verticalScrollBar()
        cursor = self.ed.textCursor()
        cursor.setPosition(self.ed.document().findBlockByNumber(2).position() + 3)
        self.ed.setTextCursor(cursor)
        before = (self.ed.toPlainText(), self.ed.textCursor().position(), self.ed.textCursor().hasSelection())
        spot = QPoint(strip.width() // 2, 5 * self.ed.fontMetrics().lineSpacing())
        kinds = QEvent.Type
        for kind, button in ((kinds.MouseButtonPress, LEFT), (kinds.MouseButtonRelease, LEFT), (kinds.MouseButtonDblClick, LEFT),
                             (kinds.MouseButtonRelease, LEFT), (kinds.MouseButtonPress, Qt.MouseButton.MiddleButton)):
            QApplication.sendEvent(strip, QMouseEvent(kind, QPointF(spot), QPointF(strip.mapToGlobal(spot)), button, button, Qt.KeyboardModifier.NoModifier))
        self.assertEqual((self.ed.toPlainText(), self.ed.textCursor().position(), self.ed.textCursor().hasSelection()), before)
        wheel = QWheelEvent(QPointF(spot), QPointF(strip.mapToGlobal(spot)), QPoint(0, 0), QPoint(0, -240), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(strip, wheel)
        self.assertGreater(bar.value(), 0)
        self.assertEqual(self.drawn()[0][0], str(bar.value() + 1))


class FindBarTest(unittest.TestCase):
    """찾기 막대와 편집기. 회차 화면과 맞물리는 부분은 FindTest 에서 봄."""

    def setUp(self):
        theme.set_mode("light")
        self.addCleanup(theme.set_mode, "system")
        self.panel, self.seen = widgets.CodePanel(), []
        self.ed = self.panel.editor
        self.bar = widgets.FindBar(self.ed, self.panel)
        self.panel.changed.connect(self.seen.append)  # 자동 저장으로 가는 신호
        self.ed.setFont(theme.code_font())
        self.panel.resize(480, 520)
        self.panel.show()
        self.addCleanup(self.panel.close)
        self.panel.set_code(SAMPLE)
        self.panel.activateWindow()
        self.ed.setFocus()
        pump()

    def open(self, text=None):
        QTest.keyClick(self.ed, Qt.Key.Key_F, CTRL)
        if text is not None:
            self.bar.input.clear()
            QTest.keyClicks(self.bar.input, text)

    def at(self):
        """편집기의 커서: (줄 번호, 선택한 글)."""
        cursor = self.ed.textCursor()
        return self.ed.document().findBlock(cursor.selectionStart()).blockNumber() + 1, cursor.selectedText()

    def test_ctrl_f_opens_the_bar_above_the_text_and_typing_paints_every_match(self):
        self.assertTrue(self.bar.isHidden())
        self.assertEqual((self.ed.head, self.ed.extraSelections()), (0, []))
        self.open()
        self.assertTrue(self.bar.isVisible())
        self.assertIs(QApplication.focusWidget(), self.bar.input)
        self.assertEqual((self.bar.count.text(), find_marks(self.ed), bool(self.bar.input.property("missing"))), ("", [], False))
        view = self.ed.viewport()
        top, box = view.mapTo(self.panel, QPoint(0, 0)), self.bar.geometry()
        self.assertEqual(self.ed.viewportMargins().top(), box.height() + 2 * self.bar.GAP)  # 본문이 막대의 높이만큼 내려가 글이 가려지지 않음
        self.assertEqual((box.bottom() + 1, box.right() + 1), (top.y() - self.bar.GAP, top.x() + view.width() - self.bar.GAP))  # 오른쪽 위
        self.assertGreaterEqual(box.top(), self.ed.mapTo(self.panel, QPoint(0, 0)).y())
        QTest.keyClicks(self.bar.input, "total")  # 대소문자를 가리지 않음
        self.assertEqual(self.bar.count.text(), "1/5")
        self.assertEqual(find_marks(self.ed), [(2, "total", True), (4, "total", False), (5, "Total", False), (5, "total", False), (6, "Total", False)])
        QTest.keyClicks(self.bar.input, " +")  # 입력하는 대로 다시 찾음
        self.assertEqual((self.bar.count.text(), find_marks(self.ed)), ("1/1", [(4, "total +", True)]))
        self.assertEqual((self.ed.toPlainText(), self.seen), (SAMPLE, []))  # 친 글자는 편집기와 답으로 가지 않음
        self.ed.setFocus()
        self.open()  # 떠 있을 때 다시 누르면 입력칸으로 돌아가 쓰던 글을 전부 선택함
        self.assertIs(QApplication.focusWidget(), self.bar.input)
        self.assertEqual(self.bar.input.selectedText(), "total +")

    def test_enter_buttons_and_keys_walk_the_matches_and_wrap_around(self):
        self.open("total")
        steps = [(lambda: QTest.keyClick(self.bar.input, Qt.Key.Key_Return), "2/5", 4),
                 (lambda: click(self.bar.next_btn), "3/5", 5),
                 (lambda: QTest.keyClick(self.bar.input, Qt.Key.Key_Enter), "4/5", 5),
                 (lambda: QTest.keyClick(self.bar.input, Qt.Key.Key_G, CTRL), "5/5", 6),
                 (lambda: QTest.keyClick(self.bar.input, Qt.Key.Key_Return), "1/5", 2),  # 끝에서 처음으로
                 (lambda: QTest.keyClick(self.bar.input, Qt.Key.Key_Return, SHIFT), "5/5", 6),  # 처음에서 끝으로
                 (lambda: click(self.bar.prev_btn), "4/5", 5),
                 (lambda: QTest.keyClick(self.bar.input, Qt.Key.Key_G, CTRL | SHIFT), "3/5", 5)]
        for number, (press, count, line) in enumerate(steps):
            press()
            self.assertEqual((self.bar.count.text(), self.at()), (count, (line, "")), number)
            marks = find_marks(self.ed)
            self.assertEqual(([mark[2] for mark in marks].index(True), sum(mark[2] for mark in marks)), (int(count[0]) - 1, 1), number)
            self.assertIs(QApplication.focusWidget(), self.bar.input, number)  # 단추를 눌러도 입력칸에 남음
        self.ed.setFocus()  # 편집기에 포커스가 있어도 다음·이전 키는 들음
        QTest.keyClick(self.ed, Qt.Key.Key_G, CTRL)
        self.assertEqual((self.bar.count.text(), self.at()), ("4/5", (5, "")))
        self.assertEqual((self.ed.toPlainText(), self.seen), (SAMPLE, []))

    def test_f3_walks_the_matches_on_every_platform_and_escape_closes_from_the_editor_too(self):
        none = Qt.KeyboardModifier.NoModifier
        self.open("total")
        for key, modifiers, count in ((Qt.Key.Key_F3, none, "2/5"), (Qt.Key.Key_F3, none, "3/5"), (Qt.Key.Key_F3, SHIFT, "2/5")):
            QTest.keyClick(self.bar.input, key, modifiers)
            self.assertEqual(self.bar.count.text(), count)  # 한 번에 한 곳씩
        self.ed.setFocus()
        QTest.keyClick(self.ed, Qt.Key.Key_F3)
        self.assertEqual((self.bar.count.text(), self.at(), self.bar.escape.isEnabled()), ("3/5", (5, ""), True))
        QTest.keyClick(self.ed, Qt.Key.Key_Escape)  # 포커스가 편집기에 있어도 닫힘
        self.assertEqual((self.bar.isHidden(), self.ed.extraSelections(), self.at(), self.bar.escape.isEnabled()), (True, [], (5, "Total"), False))
        self.assertIs(QApplication.focusWidget(), self.ed)
        QTest.keyClick(self.ed, Qt.Key.Key_Escape)  # 닫힌 뒤의 Esc 는 선택을 건드리지 않음
        self.assertEqual((self.at(), self.ed.toPlainText(), self.seen), ((5, "Total"), SAMPLE, []))

        keys = QKeySequence.StandardKey  # 맥의 표준 키에는 F3 이 없어서 따로 들음
        mac = {keys.Find: ["Ctrl+F"], keys.FindNext: ["Ctrl+G"], keys.FindPrevious: ["Ctrl+Shift+G"]}
        with mock.patch.object(widgets.QKeySequence, "keyBindings", lambda key: [QKeySequence(text) for text in mac[key]]):
            panel = widgets.CodePanel()
            bar = widgets.FindBar(panel.editor, panel)
        panel.show()
        self.addCleanup(panel.close)
        panel.set_code(SAMPLE)
        panel.activateWindow()
        panel.editor.setFocus()
        pump()
        QTest.keyClick(panel.editor, Qt.Key.Key_F, CTRL)
        self.assertIs(QApplication.focusWidget(), bar.input)
        QTest.keyClicks(bar.input, "total")
        steps = ((Qt.Key.Key_F3, none, "2/5"), (Qt.Key.Key_G, CTRL, "3/5"), (Qt.Key.Key_F3, SHIFT, "2/5"), (Qt.Key.Key_G, CTRL | SHIFT, "1/5"))
        for target in (bar.input, panel.editor):
            target.setFocus()
            for key, modifiers, count in steps:
                QTest.keyClick(target, key, modifiers)
                self.assertEqual(bar.count.text(), count)

    def test_match_outside_the_view_is_scrolled_into_it(self):
        self.panel.set_code("\n".join("row %d" % number for number in range(1, 201)) + "\nneedle\n" + "\n".join("x" * 150 for _ in range(60)))
        pump()
        self.open("needle")
        self.assertEqual((self.bar.count.text(), self.at()), ("1/1", (201, "")))
        self.assertGreater(self.ed.verticalScrollBar().value(), 150)
        shown = self.ed.cursorRect()
        self.assertTrue(self.ed.viewport().rect().contains(shown), shown)
        self.assertLess(abs(shown.center().y() - self.ed.viewport().height() // 2), 2 * shown.height())  # 가운데쯤에 옴

    def test_no_match_says_so_and_marks_the_input(self):
        self.open("totla")
        self.assertEqual((self.bar.count.text(), find_marks(self.ed), self.bar.input.property("missing")), ("없음", [], True))
        self.assertFalse(self.bar.prev_btn.isEnabled() or self.bar.next_btn.isEnabled())
        pump()
        image = self.bar.input.grab().toImage()
        self.assertEqual(image.pixelColor(image.width() // 2, 0).name(), theme.EDITOR["missing"])  # 입력칸 테두리가 오류 색
        before = self.at()
        QTest.keyClick(self.bar.input, Qt.Key.Key_Return)  # 갈 곳이 없으면 커서가 옮겨지지 않음
        self.assertEqual((self.bar.count.text(), self.at()), ("없음", before))
        for _ in range(2):
            QTest.keyClick(self.bar.input, Qt.Key.Key_Backspace)
        self.assertEqual((self.bar.count.text(), self.bar.input.property("missing"), self.bar.next_btn.isEnabled()), ("1/5", False, True))
        image = self.bar.input.grab().toImage()
        self.assertEqual(image.pixelColor(image.width() // 2, 0).name(), theme.EDITOR["focus"])
        self.bar.input.clear()  # 찾을 글이 없으면 개수도 비움
        self.assertEqual((self.bar.count.text(), find_marks(self.ed), self.bar.input.property("missing")), ("", [], False))

    def test_text_selected_within_one_line_becomes_the_query(self):
        cursor = self.ed.textCursor()
        start = SAMPLE.index("Total")
        cursor.setPosition(start)
        cursor.setPosition(start + 5, QTextCursor.MoveMode.KeepAnchor)
        self.ed.setTextCursor(cursor)
        self.open()
        self.assertEqual((self.bar.input.text(), self.bar.input.selectedText(), self.bar.count.text()), ("Total", "Total", "3/5"))  # 선택했던 곳을 가리킴
        self.assertEqual(find_marks(self.ed)[2], (5, "Total", True))
        QTest.keyClick(self.bar.input, Qt.Key.Key_Escape)
        self.assertEqual(self.at(), (5, "Total"))
        cursor.setPosition(0)  # 여러 줄을 선택하고 열면 쓰던 글이 남음
        cursor.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
        self.ed.setTextCursor(cursor)
        self.open()
        self.assertEqual((self.bar.input.text(), self.bar.count.text()), ("Total", "1/5"))

    def test_closing_clears_the_paint_selects_the_current_match_and_returns_focus(self):
        for close in (lambda: QTest.keyClick(self.bar.input, Qt.Key.Key_Escape), lambda: click(self.bar.close_btn)):
            self.open("total")
            QTest.keyClick(self.bar.input, Qt.Key.Key_Return)
            QTest.keyClick(self.bar.input, Qt.Key.Key_Return)
            self.assertEqual((self.bar.count.text(), len(find_marks(self.ed))), ("3/5", 5))
            close()
            self.assertTrue(self.bar.isHidden())
            self.assertEqual((self.ed.extraSelections(), self.ed.head, self.ed.viewportMargins().top()), ([], 0, 0))
            self.assertEqual(self.at(), (5, "Total"))  # 가리키던 곳이 선택된 채로 남음
            self.assertIs(QApplication.focusWidget(), self.ed)
            cursor = self.ed.textCursor()
            cursor.setPosition(0)
            self.ed.setTextCursor(cursor)
        self.open("zzz")  # 맞는 곳이 없는 채로 닫으면 커서가 옮겨지지 않음
        before = self.at()
        QTest.keyClick(self.bar.input, Qt.Key.Key_Escape)
        self.assertEqual((self.at(), self.bar.isHidden()), (before, True))
        self.assertIs(QApplication.focusWidget(), self.ed)
        QTest.keyClick(self.ed, Qt.Key.Key_G, CTRL)  # 닫힌 채로 다음 키를 누르면 쓰던 글로 다시 띄움
        self.assertEqual((self.bar.isVisible(), self.bar.input.text()), (True, "zzz"))
        self.assertEqual((self.ed.toPlainText(), self.seen), (SAMPLE, []))

    def test_closing_leaves_the_cursor_where_the_editor_was_being_edited(self):
        """막대를 띄운 채 편집기의 다른 곳을 고치다가 닫으면 커서가 찾은 곳으로 끌려가지 않음. 끌려가 선택되면 이어 친 글자가 그 글을 덮어씀."""
        for close in (lambda: QTest.keyClick(self.ed, Qt.Key.Key_Escape), lambda: click(self.bar.close_btn)):
            self.panel.set_code(SAMPLE)
            self.ed.moveCursor(QTextCursor.MoveOperation.Start)
            self.open("total")
            self.assertEqual((self.bar.count.text(), self.at()), ("1/5", (2, "")))
            self.ed.setFocus()
            self.ed.moveCursor(QTextCursor.MoveOperation.End)
            QTest.keyClicks(self.ed, "# memo")
            close()
            self.assertEqual((self.bar.isHidden(), self.at()), (True, (7, "")))
            self.assertIs(QApplication.focusWidget(), self.ed)
            QTest.keyClicks(self.ed, "x")
            self.assertEqual((self.ed.toPlainText(), self.seen[-1]), (SAMPLE + "# memox", SAMPLE + "# memox"))
        self.panel.set_code(SAMPLE)  # 편집기에서 선택해 둔 글도 그대로 남음
        self.open("total")
        self.ed.setFocus()
        cursor = self.ed.textCursor()
        cursor.setPosition(SAMPLE.index("numbers"))
        cursor.setPosition(SAMPLE.index("total"), QTextCursor.MoveMode.KeepAnchor)  # 커서 쪽 끝이 찾은 곳의 시작과 같은 선택
        self.ed.setTextCursor(cursor)
        QTest.keyClick(self.ed, Qt.Key.Key_Escape)
        self.assertEqual(self.ed.textCursor().selectedText(), "numbers):     ")

    def test_count_and_input_are_not_cut_off_in_a_narrow_editor(self):
        """답안 칸을 끝까지 좁히고 맞는 곳이 천 개를 넘어도 개수가 다 보이고 입력칸에 찾는 글이 몇 글자는 보임."""
        self.panel.set_code("\n".join("row = %d" % number for number in range(2500)))
        self.panel.resize(251, 520)
        pump()
        self.open("row")
        QTest.keyClick(self.bar.input, Qt.Key.Key_Return, SHIFT)  # 처음에서 끝으로
        pump()
        count, view = self.bar.count, self.ed.viewport()

        def whole():
            """막대 안의 칸들이 서로 겹치거나 막대 밖으로 나가지 않고 개수가 다 보이는지."""
            boxes = [part.geometry() for part in (self.bar.input, count, self.bar.prev_btn, self.bar.next_btn, self.bar.close_btn)]
            apart = all(left.right() < right.left() for left, right in zip(boxes, boxes[1:]))
            return apart and boxes[0].left() >= 0 and boxes[-1].right() < self.bar.width() and count.width() >= count.fontMetrics().horizontalAdvance(count.text())

        box = self.bar.geometry()
        self.assertEqual((count.text(), whole()), ("2500/2500", True))
        self.assertGreater(self.bar.input.width(), 40)
        self.assertGreater(box.width(), view.width() - 2 * self.bar.GAP)  # 본문 폭으로는 모자라서 줄 번호 칸 위의 빈 자리까지 씀
        self.assertGreaterEqual(box.left(), self.ed.mapTo(self.panel, QPoint(0, 0)).x() + self.bar.GAP)  # 편집기 밖으로는 나가지 않음
        self.assertEqual((box.right() + 1, box.bottom() + 1),
                         (view.mapTo(self.panel, QPoint(view.width(), 0)).x() - self.bar.GAP, view.mapTo(self.panel, QPoint(0, 0)).y() - self.bar.GAP))
        for text, shown in (("row = 7", "1/111"), ("row = 77", "1/11")):  # 개수가 짧아지면 그만큼 입력칸이 넓어짐
            self.bar.input.setText(text)
            pump()
            self.assertEqual((count.text(), whole()), (shown, True))
        self.assertGreaterEqual(self.bar.input.width(), self.bar.INPUT)

    def test_find_input_takes_no_dropped_text(self):
        """편집기에서 끌어온 글을 입력칸이 받으면 그 글이 답에서 빠짐."""
        self.open("to")
        data = QMimeData()
        data.setText("tal")
        events = (QDragEnterEvent(QPoint(8, 8), Qt.DropAction.MoveAction, data, LEFT, Qt.KeyboardModifier.NoModifier),
                  QDropEvent(QPointF(8, 8), Qt.DropAction.MoveAction, data, LEFT, Qt.KeyboardModifier.NoModifier))
        for event in events:
            QApplication.sendEvent(self.bar.input, event)
        self.assertFalse(events[0].isAccepted())
        self.assertEqual((self.bar.input.text(), self.ed.toPlainText(), self.seen), ("to", SAMPLE, []))

    def test_editing_the_text_recounts_at_once_without_moving_the_cursor(self):
        self.open("total")
        QTest.keyClick(self.bar.input, Qt.Key.Key_Return)
        self.assertEqual(self.bar.count.text(), "2/5")
        self.ed.setFocus()  # 막대를 띄워 둔 채로 편집기를 고침
        cursor = self.ed.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.ed.setTextCursor(cursor)
        QTest.keyClicks(self.ed, "total = 1")
        self.assertEqual((self.bar.count.text(), len(find_marks(self.ed)), find_marks(self.ed)[-1]), ("2/6", 6, (7, "total", False)))
        self.assertEqual(self.at(), (7, ""))  # 치던 자리에 남음
        cursor.setPosition(0)
        self.ed.setTextCursor(cursor)
        QTest.keyClicks(self.ed, "# total")  # 앞쪽에 생겨도 가리키던 곳은 같은 곳
        QTest.keyClick(self.ed, Qt.Key.Key_Return)
        self.assertEqual((self.bar.count.text(), find_marks(self.ed)[2]), ("3/7", (5, "total", True)))
        for _ in range(8):  # 맞는 곳이 지워지면 개수가 줄어듦
            QTest.keyClick(self.ed, Qt.Key.Key_Backspace)
        self.assertEqual((self.bar.count.text(), find_marks(self.ed)[1]), ("2/6", (4, "total", True)))
        self.assertEqual(self.seen[-1], self.ed.toPlainText())  # 편집기에 친 글은 그대로 답이 됨
        self.ed.selectAll()
        QTest.keyClick(self.ed, Qt.Key.Key_Delete)
        self.assertEqual((self.bar.count.text(), find_marks(self.ed), self.bar.input.property("missing")), ("없음", [], True))

    def test_find_works_on_a_locked_editor_and_never_changes_it(self):
        for lock, unlock in ((lambda: self.ed.setReadOnly(True), lambda: self.ed.setReadOnly(False)),
                             (lambda: self.ed.setEnabled(False), lambda: self.ed.setEnabled(True))):
            self.ed.setFocus()
            self.ed.moveCursor(QTextCursor.MoveOperation.Start)
            self.open("total")
            lock()
            self.bar.input.setFocus()
            QTest.keyClick(self.bar.input, Qt.Key.Key_Return)
            click(self.bar.next_btn)
            self.assertEqual((self.bar.count.text(), self.at(), find_marks(self.ed)[2]), ("3/5", (5, ""), (5, "Total", True)))
            QTest.keyClicks(self.bar.input, " =")
            self.assertEqual((self.bar.count.text(), find_marks(self.ed)), ("2/2", [(2, "total =", False), (5, "Total =", True)]))
            QTest.keyClick(self.bar.input, Qt.Key.Key_Escape)
            self.assertEqual((self.at(), self.ed.extraSelections()), ((5, "Total ="), []))
            unlock()
        self.assertEqual((self.ed.toPlainText(), self.seen, self.ed.document().isModified()), (SAMPLE, [], False))


class FindTest(GuiTest):
    """회차 화면의 찾기: 답과 자동 저장, 문항 이동, 숫자 키, 잠금, 앱 테마와 글자 크기."""

    def open_code(self):
        self.boot()
        self.make_round("r96", [self.first(type="return"), self.first(type="choice", multi=False), self.first(type="print")])
        self.win.open_round("r96")
        page = self.win.round_page
        item = self.select(lambda it: it["kind"] == "code")
        self.win.activateWindow()
        page.code_panel.editor.setFocus()
        return page, page.code_panel.editor, page.find_bar, item

    def test_find_stays_out_of_the_answer_the_autosave_and_the_number_keys(self):
        page, editor, bar, code = self.open_code()
        path = os.path.join(self.win.session.folder("r96"), code["id"] + ".py")
        saved, progress, word = study.read_text(path), page.progress.text(), code["starter"].split()[0]
        self.assertTrue(bar.isHidden())
        QTest.keyClick(editor, Qt.Key.Key_F, CTRL)
        self.assertTrue(bar.isVisible())
        self.assertIs(QApplication.focusWidget(), bar.input)
        QTest.keyClicks(bar.input, word + " 12")  # 숫자도 입력칸에 글자로 들어감
        self.assertEqual((bar.input.text(), bar.count.text()), (word + " 12", "없음"))
        for _ in range(3):
            QTest.keyClick(bar.input, Qt.Key.Key_Backspace)
        self.assertEqual((bar.input.text(), bar.count.text()[:2], find_marks(editor)[0][1:]), (word, "1/", (word, True)))
        pump(save_delay())
        self.assertEqual((editor.toPlainText(), study.read_text(path)), (code["starter"], saved))  # 친 글자는 편집기와 답안 파일로 가지 않음
        self.assertEqual((page.dirty, page.save_timer.isActive(), page.status.text()), ({}, False, ""))  # 자동 저장도 돌지 않음
        self.assertEqual((code["answered"], page.progress.text(), page.listw.item(code["no"] - 1).data(Qt.ItemDataRole.UserRole)),
                         (False, progress, False))  # 작성한 문항으로 치지 않음
        editor.setFocus()  # 막대를 띄워 둔 채로 편집기에 친 글은 답이 되고 개수도 따라감
        editor.moveCursor(QTextCursor.MoveOperation.End)
        QTest.keyClicks(editor, word)
        self.assertEqual((bar.count.text(), code["answered"]), ("1/%d" % (code["starter"].lower().count(word) + 1), True))
        pump(save_delay())
        self.assertEqual(study.read_text(path).rstrip("\n"), (code["starter"] + word).rstrip("\n"))

        choice = self.select(lambda it: it["type"] == "choice")  # 문항을 옮기면 막대가 닫힘
        self.assertTrue(bar.isHidden())
        self.assertEqual((editor.extraSelections(), editor.viewportMargins().top()), ([], 0))
        page.listw.setFocus()
        QTest.keyClick(page.listw, Qt.Key.Key_2)  # 숫자 키는 보기를 고르고 찾을 글은 바뀌지 않음
        self.assertEqual((choice["answer"], bar.input.text()), ([2], word))
        QTest.keyClick(page.listw, Qt.Key.Key_F, CTRL)  # 편집기가 없는 문항에서는 뜨지 않음
        self.assertTrue(bar.isHidden())
        self.select(lambda it: it is code)  # 돌아와도 닫힌 채로 있고, 다시 띄우면 찾던 글이 남아 있음
        self.assertEqual((bar.isHidden(), editor.extraSelections()), (True, []))
        editor.setFocus()
        QTest.keyClick(editor, Qt.Key.Key_F, CTRL)
        self.assertEqual((bar.isVisible(), bar.input.text(), bar.input.selectedText()), (True, word, word))
        self.assertEqual(self.saved_quiz("r96")[choice["id"]], 2)

    def test_find_works_while_the_screen_is_locked_and_follows_font_size_and_keeps_its_colors_in_the_dark_theme(self):
        page, editor, bar, _ = self.open_code()
        self.fill(page.current, SAMPLE)
        self.addCleanup(theme.set_mode, "system")
        editor.moveCursor(QTextCursor.MoveOperation.Start)
        QTest.keyClick(editor, Qt.Key.Key_F, CTRL)
        QTest.keyClicks(bar.input, "total")
        self.assertEqual(bar.count.text(), "1/5")

        page.set_busy(True, "채점하는 중입니다.")  # 실행·채점 중에는 답안 칸이 잠기지만 찾기는 됨
        self.assertFalse(editor.isEnabled())
        self.assertTrue(bar.isEnabled() and bar.isVisible())
        bar.input.setFocus()
        QTest.keyClick(bar.input, Qt.Key.Key_Return)
        click(bar.next_btn)
        self.assertEqual((bar.count.text(), find_marks(editor)[2], editor.textCursor().blockNumber() + 1), ("3/5", (5, "Total", True), 5))
        QTest.keyClicks(bar.input, " =")
        self.assertEqual((bar.count.text(), len(find_marks(editor))), ("2/2", 2))
        for _ in range(2):
            QTest.keyClick(bar.input, Qt.Key.Key_Backspace)
        page.set_busy(False)
        self.assertEqual((editor.toPlainText(), bar.count.text(), bar.isVisible()), (SAMPLE, "3/5", True))

        view, right = editor.viewport(), bar.parentWidget()

        def placed():
            """막대가 본문 위에 비운 자리의 오른쪽 끝에 놓였는지."""
            top, box = view.mapTo(right, QPoint(0, 0)), bar.geometry()
            return (box.bottom() + 1, box.right() + 1) == (top.y() - bar.GAP, top.x() + view.width() - bar.GAP) and box.width() <= bar.WIDTH

        self.assertTrue(placed())
        marks = find_marks(editor)
        theme.set_mode("dark")  # 띄워 둔 채로 앱 테마를 바꿔도 칠과 줄 번호 칸은 편집기의 색으로 남음
        pump()
        self.assertEqual((find_marks(editor), [mark[2] for mark in marks]), (marks, [False, False, True, False, False]))
        strip = editor.numbers.grab().toImage()
        self.assertEqual(strip.pixelColor(2, strip.height() - 4).name(), theme.EDITOR["gutter"])
        self.assertEqual(bright_share(self.win), 0)
        width = editor.numbers.width()
        self.win.set_zoom(4)  # 글자를 키우면 줄 번호 칸이 넓어지고 막대는 제자리를 따라감
        pump()
        self.assertGreater(editor.numbers.width(), width)
        self.assertTrue(placed())
        self.assertEqual((bar.count.text(), len(find_marks(editor))), ("3/5", 5))
        self.win.resize(1024, 700)  # 창을 줄여도 편집기 안에 놓임
        pump()
        self.assertTrue(placed())
        self.assertGreaterEqual(bar.geometry().left(), editor.mapTo(right, QPoint(0, 0)).x())
        click(bar.close_btn)
        self.assertEqual((editor.textCursor().selectedText(), editor.extraSelections()), ("Total", []))


SYNTAX = ("keyword", "def", "builtin", "string", "comment", "number", "decorator", "self", "blank")  # 문법 색칠이 나누는 종류


def painted(editor, line):
    """문법 색칠이 한 줄에 입힌 조각을 (글, 종류)로 돌려줌. 색을 입히지 않은 글은 빠짐."""
    kinds = {theme.EDITOR[name]: name for name in SYNTAX}
    block = editor.document().findBlockByNumber(line)
    raw = block.text().encode("utf-16-le")  # Qt 의 위치는 UTF-16 단위
    return [(raw[2 * part.start:2 * (part.start + part.length)].decode("utf-16-le"), kinds[part.format.foreground().color().name()])
            for part in block.layout().formats()]


class HighlightTest(unittest.TestCase):
    """편집기의 바탕과 파이썬 문법 색칠."""

    def setUp(self):
        theme.set_mode("light")
        self.addCleanup(theme.set_mode, "system")
        self.panel, self.seen = widgets.CodePanel(), []
        self.ed = self.panel.editor
        self.panel.changed.connect(self.seen.append)  # 자동 저장으로 가는 신호
        self.ed.setFont(theme.code_font())
        self.panel.resize(520, 560)
        self.panel.show()
        self.addCleanup(self.panel.close)
        pump()

    def kinds(self, code):
        self.panel.set_code(code)
        return [painted(self.ed, line) for line in range(self.ed.blockCount())]

    def test_each_kind_of_token_gets_its_own_color(self):
        code = ("import re\n"
                "class Dog(Animal):\n"
                "    @property\n"
                "    def speak(self, times=2):  # 울음 for 3\n"
                "        for n in range(times):\n"
                "            print(self.sound, \"멍\", 0x1F + 3.5e2, .5, 1_000)\n"
                "        return None if not self.items else self.items.index(max(self.items))\n"
                "classes, define, printer, selfish, x1, in_ = text.format(a), d.keys\n"
                "@app.route\n"
                "y = a @ b\n")
        self.assertEqual(self.kinds(code), [
            [("import", "keyword")],
            [("class", "keyword"), ("Dog", "def")],  # 부모 클래스 같은 여느 이름은 칠하지 않음
            [("@property", "decorator")],
            [("def", "keyword"), ("speak", "def"), ("self", "self"), ("2", "number"), ("# 울음 for 3", "comment")],
            [("for", "keyword"), ("in", "keyword"), ("range", "builtin")],
            [("print", "builtin"), ("self", "self"), ('"멍"', "string"), ("0x1F", "number"), ("3.5e2", "number"), (".5", "number"),
             ("1_000", "number")],
            [("return", "keyword"), ("None", "keyword"), ("if", "keyword"), ("not", "keyword"), ("self", "self"), ("else", "keyword"),
             ("self", "self"), ("max", "builtin"), ("self", "self")],  # 점 뒤의 index 는 속성
            [],  # 예약어나 내장 함수로 시작할 뿐인 이름, 점 뒤의 format
            [("@app.route", "decorator")],
            [],  # 줄 가운데의 @ 는 연산자
            []])
        colors = [QColor(theme.EDITOR[name]) for name in SYNTAX[:-1] + ("ink",)]
        for one, other in itertools.combinations(colors, 2):  # 종류마다 색이 서로 구분됨. 빈칸은 바탕으로 구분함
            gap = abs(one.red() - other.red()) + abs(one.green() - other.green()) + abs(one.blue() - other.blue())
            self.assertGreater(gap, 60, "%s / %s" % (one.name(), other.name()))

    def test_strings_keep_one_color_through_prefixes_escapes_and_several_lines(self):
        code = ("a = f\"{x}점\" + r'\\d+' + Rb\"\\x00\" + 'it\\'s' + \"\" + str(1)\n"
                "b = \"# 아님\"  # 주석 if\n"
                "def f():\n"
                "    \"\"\"첫 줄\n"
                "    for x in range(3):  # 문자열 안\n"
                "    끝\"\"\" + str(2)\n"
                "c = '''여는 줄에서 \"\"\" 는 닫지 않음\n"
                "'''\n"
                "d = 3\n")
        self.assertEqual(self.kinds(code), [
            [('f"{x}점"', "string"), ("r'\\d+'", "string"), ('Rb"\\x00"', "string"), ("'it\\'s'", "string"), ('""', "string"), ("str", "builtin"),
             ("1", "number")],
            [('"# 아님"', "string"), ("# 주석 if", "comment")],
            [("def", "keyword"), ("f", "def")],
            [('"""첫 줄', "string")],
            [("    for x in range(3):  # 문자열 안", "string")],
            [('    끝"""', "string"), ("str", "builtin"), ("2", "number")],
            [("'''여는 줄에서 \"\"\" 는 닫지 않음", "string")],
            [("'''", "string")],
            [("3", "number")],
            []])
        cursor = self.ed.textCursor()  # 여는 따옴표를 지우면 아랫줄이 코드로 돌아가고, 다시 치면 문자열이 됨
        cursor.setPosition(self.ed.document().findBlockByNumber(3).position() + 4)
        self.ed.setTextCursor(cursor)
        for _ in range(3):
            QTest.keyClick(self.ed, Qt.Key.Key_Delete)
        self.assertEqual(painted(self.ed, 4), [("for", "keyword"), ("in", "keyword"), ("range", "builtin"), ("3", "number"),
                                               ("# 문자열 안", "comment")])
        self.assertEqual(painted(self.ed, 5)[0], ('""" + str(2)', "string"))  # 닫던 따옴표가 이제 문자열을 엶
        QTest.keyClicks(self.ed, '"""')
        self.assertEqual((painted(self.ed, 4), painted(self.ed, 5)[1:]),
                         ([("    for x in range(3):  # 문자열 안", "string")], [("str", "builtin"), ("2", "number")]))

    def test_unfinished_code_is_colored_without_errors(self):
        """치는 중에는 따옴표와 괄호가 닫히지 않은 글이 계속 지나감."""
        pieces = ('s = "abc', "t = 'it\\", 'u = f"{', 'x = (1, [2, {"a": ', "0x", "1e", "1.", "@", "def", "def (", "class ", "self.", "print(",
                  "\\", "#", "____", "\U0001F389 = '\U0001F389' + str(1)  # \U0001F389", "w = '''", 'v = """문서')
        failures = []
        with mock.patch.object(sys, "excepthook", lambda *args: failures.append(args)):
            for piece in pieces:
                for length in range(len(piece) + 1):
                    self.panel.set_code("y = 0\n%s\nz = None" % piece[:length])
            self.panel.set_code("\n".join(pieces))
        self.assertEqual(failures, [])
        rows = [painted(self.ed, line) for line in range(len(pieces))]
        self.assertEqual(rows[:4], [[('"abc', "string")], [("'it\\", "string")], [('f"{', "string")],  # 닫지 않은 문자열은 줄 끝까지만
                                    [("1", "number"), ("2", "number"), ('"a"', "string")]])
        self.assertEqual(rows[8:13], [[("def", "keyword")], [("def", "keyword")], [("class", "keyword")], [("self", "self")], [("print", "builtin")]])
        self.assertEqual(rows[16], [("'\U0001F389'", "string"), ("str", "builtin"), ("1", "number"), ("# \U0001F389", "comment")])  # 이모지 뒤에서도 제자리
        self.assertEqual(rows[17:], [[("'''", "string")], [('v = """문서', "string")]])  # 닫지 않은 삼중 따옴표는 글 끝까지

    def test_blanks_of_a_fill_item_stand_out(self):
        rows = self.kinds('print(____, "____")  # ____\nif __name__ == "____":\n    ____.info()\n')
        self.assertEqual(rows[0], [("print", "builtin"), ("____", "blank"), ('"', "string"), ("____", "blank"), ('"', "string"),
                                   ("# ", "comment"), ("____", "blank")])
        self.assertEqual(rows[1], [("if", "keyword"), ('"', "string"), ("____", "blank"), ('"', "string")])  # __name__ 은 빈칸이 아님
        self.assertEqual(rows[2], [("____", "blank")])
        ground = {part.format.background().color().name() for line in range(3)
                  for part in self.ed.document().findBlockByNumber(line).layout().formats()
                  if part.format.foreground().color().name() == theme.EDITOR["blank"]}
        self.assertEqual(ground, {theme.EDITOR["blank_bg"]})  # 글자색에 더해 옅은 바탕을 깖
        image = self.ed.grab().toImage()
        colors = {image.pixelColor(x, y).name() for x in range(image.width()) for y in range(0, 40)}
        self.assertIn(theme.EDITOR["blank_bg"], colors)

    def test_selected_blank_looks_different_from_the_other_blanks(self):
        """빈칸만 선택하고 치면 그 자리에 들어가므로 어느 빈칸을 선택했는지 보여야 함. 빈칸의 바탕은 선택 영역, 찾은 곳, 편집기 바탕과 색이 다름."""
        code = "result = ____ * ____\n"
        self.panel.set_code(code)
        first = code.index("____")
        cursor = self.ed.textCursor()
        cursor.setPosition(first)
        cursor.setPosition(first + 4, QTextCursor.MoveMode.KeepAnchor)
        self.ed.setTextCursor(cursor)
        pump()
        image, view = self.ed.grab().toImage(), self.ed.viewport()

        def ground(position):
            """position 번째 글자 칸의 바탕색. 밑줄 글자가 닿지 않는 위쪽을 봄."""
            spot = QTextCursor(self.ed.document())
            spot.setPosition(position)
            box = self.ed.cursorRect(spot)
            return image.pixelColor(view.mapTo(self.ed, QPoint(box.left() + 5, box.top() + 3))).name()

        tokens = theme.EDITOR
        self.assertEqual((ground(first), ground(code.rindex("____")), ground(0)), (tokens["selection"], tokens["blank_bg"], tokens["bg"]))
        blank = QColor(tokens["blank_bg"])
        for name in ("selection", "find", "find_current", "bg"):
            other = QColor(tokens[name])
            gap = abs(blank.red() - other.red()) + abs(blank.green() - other.green()) + abs(blank.blue() - other.blue())
            self.assertGreater(gap, 60, name)

    def test_editor_keeps_the_same_navy_ground_in_both_app_themes(self):
        other = TextPanel()
        other.set_item({"type": "output", "answer": ""})
        other.resize(300, 200)
        other.show()
        self.addCleanup(other.close)
        self.panel.set_code("\n".join("        row = %d" % number for number in range(80)))
        self.ed.selectAll()
        down, seen = self.ed.verticalScrollBar(), []
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            pump()
            image = self.ed.grab().toImage()
            view, handle = self.ed.viewport().geometry(), down.mapTo(self.ed, QPoint(down.width() // 2, 12))
            seen.append((image.pixelColor(view.right() - 20, view.bottom() - 4).name(),  # 글이 없는 바탕
                         image.pixelColor(view.left() + 10, view.top() + 14).name(),  # 선택한 들여쓰기
                         image.pixelColor(handle).name(),  # 스크롤 막대의 손잡이
                         image.pixelColor(3, image.height() // 2).name(),  # 줄 번호 칸
                         self.ed.palette().color(self.ed.foregroundRole()).name()))  # 기본 글자색. 커서도 이 색으로 그림
            for box in (other.multi, self.panel.console):  # 다른 답 칸과 실행 결과 칸은 앱 테마를 따름
                shot = box.grab().toImage()
                self.assertEqual(shot.pixelColor(shot.width() // 2, shot.height() // 2).name(), theme.TOKENS[mode]["surface"])
        ground = theme.EDITOR["bg"]
        self.assertEqual(seen, [(ground, theme.EDITOR["selection"], theme.EDITOR["scroll"], theme.EDITOR["gutter"], theme.EDITOR["ink"])] * 2)
        color = QColor(ground)
        self.assertTrue(color.red() < color.green() < color.blue() and gray(ground) < 80, ground)  # 어두운 남색
        for tokens in theme.TOKENS.values():  # 문제 칸의 바탕과 구분됨
            self.assertGreater(contrast(ground, tokens["surface"]), 1.2)

    def test_locked_editor_turns_darker_and_stays_navy_in_both_app_themes(self):
        """실행·채점 중에는 키를 쳐도 들어가지 않으므로 잠긴 것이 편집기에서 보여야 함. 글자 대비는 평소보다 낮아지지 않음."""
        self.panel.set_code("\n".join("        row = %d" % number for number in range(80)))
        tokens, view = theme.EDITOR, self.ed.viewport().geometry()

        def grounds():
            image = self.ed.grab().toImage()
            return image.pixelColor(view.right() - 20, view.bottom() - 4).name(), image.pixelColor(3, image.height() // 2).name()  # 본문, 줄 번호 칸

        for mode in ("light", "dark"):
            theme.set_mode(mode)
            self.ed.setEnabled(True)
            pump()
            self.assertEqual(grounds(), (tokens["bg"], tokens["gutter"]), mode)
            self.ed.setEnabled(False)
            pump()
            self.assertEqual(grounds(), (tokens["locked"], tokens["locked_gutter"]), mode)
        color = QColor(tokens["locked"])
        self.assertTrue(color.red() < color.green() < color.blue(), tokens["locked"])  # 남색 계열
        self.assertGreater(contrast(tokens["bg"], tokens["locked"]), 1.2)  # 잠기기 전과 구분됨
        for ink, back, locked in (("ink", "bg", "locked"), ("comment", "bg", "locked"), ("line_no", "gutter", "locked_gutter")):
            self.assertGreaterEqual(contrast(tokens[ink], tokens[locked]), contrast(tokens[ink], tokens[back]), ink)

    def test_editor_colors_are_readable_on_the_navy_ground(self):
        tokens = theme.EDITOR
        pairs = [(name, "bg") for name in ("ink", "keyword", "def", "builtin", "string", "number", "decorator", "self", "blank", "muted")]
        pairs += [("blank", "blank_bg"), ("find_ink", "find"), ("find_current_ink", "find_current"), ("ink", "selection"), ("ink", "gutter"),
                  ("ink", "bar"), ("muted", "bar"), ("ink", "field"), ("muted", "field")]
        for ink, back in pairs:
            self.assertGreaterEqual(contrast(tokens[ink], tokens[back]), 4.5, "%s / %s" % (ink, back))
        for ink, back in (("comment", "bg"), ("line_no", "bg"), ("line_no", "gutter"), ("missing", "field"), ("focus", "bg")):
            self.assertGreaterEqual(contrast(tokens[ink], tokens[back]), 3, "%s / %s" % (ink, back))
        self.assertGreater(contrast(tokens["find_current"], tokens["find"]), 3)  # 가리키는 곳은 다른 곳보다 뚜렷함
        self.assertGreater(contrast(tokens["ink"], tokens["bg"]), contrast(tokens["line_no"], tokens["bg"]))  # 커서 줄의 번호가 더 밝음

    def test_coloring_leaves_the_text_the_answer_and_the_undo_history_alone(self):
        code = 'def f(x):\n    """문서"""\n    return [x, "a"]  # 끝\n'
        document = self.ed.document()
        self.panel.set_code(code)
        pump()
        self.assertTrue(painted(self.ed, 0) and painted(self.ed, 2))
        self.assertEqual((self.ed.toPlainText(), self.seen), (code, []))  # 칠만으로는 답이 바뀌었다는 신호가 나가지 않음
        self.assertEqual((document.isModified(), document.isUndoAvailable(), document.availableUndoSteps()), (False, False, 0))
        for mode in ("dark", "light"):  # 앱 테마와 글자 크기를 바꿔도 같음
            theme.set_mode(mode)
            self.ed.setFont(theme.code_font(3))
            pump()
        self.ed.highlighter.rehighlight()  # 전부 다시 칠하면 Qt 는 글이 같아도 바뀌었다고 알림
        self.assertEqual((self.ed.toPlainText(), self.seen, document.isModified(), document.isUndoAvailable()), (code, [], False, False))
        self.ed.setFocus()
        self.ed.moveCursor(QTextCursor.MoveOperation.End)
        QTest.keyClicks(self.ed, "x")
        self.assertEqual((self.seen, document.availableUndoSteps()), ([code + "x"], 1))  # 친 글자만큼만 신호와 되돌리기가 생김
        self.ed.moveCursor(QTextCursor.MoveOperation.Start)
        QTest.keyClicks(self.ed, '"""')  # 아랫줄의 색이 전부 바뀌는 입력
        self.assertEqual(painted(self.ed, 2)[-1][1], "string")
        self.assertEqual((self.ed.toPlainText(), self.seen[-1]), ('"""' + code + "x", '"""' + code + "x"))
        steps = document.availableUndoSteps()
        self.assertLessEqual(steps, 4)  # 칠이 되돌리기 기록을 늘리지 않음
        for _ in range(steps):
            QTest.keyClick(self.ed, Qt.Key.Key_Z, CTRL)
        self.assertEqual((self.ed.toPlainText(), document.isUndoAvailable(), document.isModified()), (code, False, False))
        self.assertEqual(painted(self.ed, 2)[0], ("return", "keyword"))  # 되돌린 글에 맞게 다시 칠함
        self.ed.redo()
        self.assertEqual((self.ed.toPlainText(), self.seen[-1]), (code + "x", code + "x"))

    def test_typing_stays_quick_in_a_file_of_5000_lines(self):
        unit = ("class Step%d(Base):\n    \"\"\"단계.\"\"\"\n    def run(self, value, times=3):\n        total = 0  # 합계\n"
                "        for n in range(times):\n            total += int(value) + len(\"문자열\")\n        return f\"{total}점\"\n\n")
        self.panel.set_code("".join(unit % number for number in range(625)))
        self.assertEqual(self.ed.blockCount(), 5001)
        self.assertEqual(painted(self.ed, 4998), [("return", "keyword"), ('f"{total}점"', "string")])  # 끝줄까지 칠함

        def spent(press, times=1):
            """press 를 times 번 하고 화면까지 그리는 데 든 시간을 한 번에 든 초로 돌려줌."""
            start = time.perf_counter()
            for _ in range(times):
                press()
                APP.processEvents()
            return (time.perf_counter() - start) / times

        cursor = self.ed.textCursor()
        cursor.setPosition(self.ed.document().findBlockByNumber(2500).position())
        self.ed.setTextCursor(cursor)
        self.ed.setFocus()
        self.assertLess(spent(lambda: QTest.keyClick(self.ed, Qt.Key.Key_X), 30), 0.05)  # 한 글자
        self.assertLess(spent(lambda: QTest.keyClick(self.ed, Qt.Key.Key_Return), 5), 0.05)
        self.ed.moveCursor(QTextCursor.MoveOperation.Start)
        self.assertLess(spent(lambda: QTest.keyClicks(self.ed, '"""')), 0.5)  # 아래 5000줄이 전부 문자열이 되는 입력
        self.assertEqual(painted(self.ed, 4998)[0][1], "string")
        self.assertEqual(len(self.seen), 30 + 5 + 3)


class HighlightRoundTest(GuiTest):
    def test_opening_a_code_item_colors_it_and_saves_nothing(self):
        self.boot()
        fill = next(key for key in sorted(self.win.session.cat, key=study.natural_key) if self.win.session.cat[key]["type"] == "fill")
        self.make_round("r97", [fill, self.first(type="output")])
        self.win.open_round("r97")
        page = self.win.round_page
        item = self.select(lambda it: it["type"] == "fill")
        editor = page.code_panel.editor
        path = os.path.join(self.win.session.folder("r97"), item["id"] + ".py")
        saved = study.read_text(path)
        rows = [painted(editor, line) for line in range(editor.blockCount())]
        self.assertEqual(sum(row.count(("____", "blank")) for row in rows), item["starter"].count("____"))  # 빈칸마다 표시
        self.assertTrue(any(kind != "blank" for row in rows for _, kind in row))
        self.addCleanup(theme.set_mode, "system")
        for change in (lambda: theme.set_mode("dark"), lambda: self.win.set_zoom(2), lambda: theme.set_mode("light")):
            change()
            pump()
            shot = editor.grab().toImage()
            self.assertEqual(shot.pixelColor(shot.width() - 30, shot.height() - 30).name(), theme.EDITOR["bg"])
        editor.highlighter.rehighlight()
        pump(save_delay())
        self.assertEqual((editor.toPlainText(), study.read_text(path)), (item["starter"], saved))
        self.assertEqual((page.dirty, page.save_timer.isActive(), page.status.text(), item["answered"]), ({}, False, "", False))
        self.select(lambda it: it["type"] == "output")  # 다른 답 칸에는 색칠이 없음
        self.fill(page.current, "for x in range(3)")
        self.assertEqual(page.text_panel.multi.document().firstBlock().layout().formats(), [])
        self.assertEqual(page.text_panel.multi.objectName(), "")

    def test_theme_change_keeps_the_scroll_position_at_the_end_of_a_long_answer(self):
        """앱 테마를 바꾸는 동안 편집기의 글꼴이 잠깐 앱 글꼴로 돌아감. 그 글꼴로 줄 번호 칸을 다시 맞추면 끝까지 내린 스크롤이 위로 밀림."""
        self.boot()
        self.make_round("r99", [self.first(type="return")])
        self.win.open_round("r99")
        item = self.select(lambda it: it["kind"] == "code")
        editor = self.win.round_page.code_panel.editor
        self.fill(item, "\n".join("row = %d" % number for number in range(300)))
        self.addCleanup(theme.set_mode, "system")
        down = editor.verticalScrollBar()
        down.setValue(down.maximum())
        pump()
        place, width = down.value(), editor.numbers.width()
        self.assertGreater(place, 200)
        for mode in ("dark", "light"):
            theme.set_mode(mode)
            pump()
            self.assertEqual((down.value(), down.maximum(), editor.numbers.width()), (place, place, width), mode)
        self.win.set_zoom(3)  # 글자 크기를 바꾸면 줄 번호 칸은 따라감
        pump()
        self.assertGreater(editor.numbers.width(), width)

    def test_blanks_of_a_starter_stay_in_view_at_the_default_window_size(self):
        """줄 번호 칸이 생겨 글이 보이는 폭이 줄어든 만큼 답안 칸을 넓혀 둠. 기본 창 크기에서 s03/p08 의 세 번째 빈칸이 편집기 밖으로 잘리지 않음."""
        self.boot()
        self.win.resize(1280, 800)
        self.make_round("r98", ["s03/p08"])
        self.win.open_round("r98")
        item = self.select(lambda it: it["type"] == "fill")
        editor = self.win.round_page.code_panel.editor
        blanks = [found.end() for found in re.finditer("_{4,}", item["starter"])]
        self.assertGreaterEqual(len(blanks), 3)
        spot = QTextCursor(editor.document())
        for end in blanks:
            spot.setPosition(end)
            self.assertLessEqual(editor.cursorRect(spot).right(), editor.viewport().width(), item["starter"][:end].split("\n")[-1])
        self.assertEqual(editor.horizontalScrollBar().value(), 0)


class IconTest(unittest.TestCase):
    def test_icon_draws_a_readable_r_at_every_size(self):
        for size in icon.SIZES:
            image = icon.pixmap(size).toImage()
            self.assertEqual((image.width(), image.height()), (size, size))
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0, size)  # 둥근 모서리 밖은 비어 있음

            def at(x, y):
                return image.pixelColor(int(x * size / 100), int(y * size / 100))

            self.assertGreater(at(35, 50).lightness(), 240, size)  # 세로 기둥은 흰색
            self.assertLess(at(12, 88).lightness(), 200, size)  # 바탕은 그라데이션
            eye = at(icon.EYE[0], icon.EYE[1])
            if size >= 32:
                self.assertGreater(eye.lightness(), 240, size)  # 눈동자
            else:
                self.assertLess(eye.lightness(), 225, size)  # 작은 크기에서는 구멍을 비워 R 로 읽히게 함

    def test_install_sets_the_window_icon_and_survives_without_the_windows_api(self):
        with mock.patch.object(icon.sys, "platform", "win32"), mock.patch("ctypes.windll", None, create=True):
            icon.install(APP)
        self.assertEqual(sorted(size.width() for size in APP.windowIcon().availableSizes()), list(icon.SIZES))


class MotionTest(GuiTest):
    def setUp(self):
        super().setUp()
        motion.enabled = True
        self.addCleanup(setattr, motion, "enabled", False)

    def covers(self, widget):
        return widget.findChildren(motion.Cover)

    def test_page_change_fades_without_holding_up_input(self):
        self.assertTrue(150 <= motion.FADE_MS <= 200)
        self.boot()
        win, page = self.win, self.win.round_page
        wait_until(lambda: not self.covers(win), 5)
        QTest.mouseClick(win.home.action_btn, LEFT)
        self.assertIs(self.page(), page)  # 화면은 바로 바뀌고 앞 화면을 찍은 그림만 위에서 옅어짐
        self.assertEqual(len(self.covers(win.pages)), 1)
        self.assertIsNone(page.body.graphicsEffect())
        self.assertIsNone(page.code_panel.editor.graphicsEffect())
        self.assertIs(win.childAt(page.submit_btn.mapTo(win, page.submit_btn.rect().center())), page.submit_btn)  # 그림이 마우스를 가로채지 않음
        item = self.select(lambda it: it["type"] == "choice")
        click(page.choice_panel.buttons[0])
        self.assertEqual(item["answer"], [1])
        wait_until(lambda: not self.covers(win), 5)
        win.cycle_theme()  # 테마를 바꿀 때도 같은 방식으로 넘어감
        self.assertEqual(len(self.covers(win)), 1)
        wait_until(lambda: not self.covers(win), 5)

    def test_numbers_count_up_and_stop_at_the_final_value(self):
        self.assertTrue(500 <= motion.COUNT_MS <= 700)
        self.boot()
        label, seen = self.win.home.ready, []
        motion.count(label, 73, seen.append)
        wait_until(lambda: seen and seen[-1] == 73, 5)
        self.assertEqual(seen, sorted(seen))
        self.assertLess(seen[0], 73)
        motion.count_text(label, "%d%%", 45)
        self.assertGreaterEqual(label.minimumWidth(), label.fontMetrics().horizontalAdvance("45%"))  # 끝 글자의 폭을 미리 잡음
        early, late = [], []
        motion.count(self.win.home.ready_bar, 90, early.append)
        motion.count(self.win.home.ready_bar, 20, late.append)  # 다시 부르면 앞의 것은 멈춤
        wait_until(lambda: label.text() == "45%" and late and late[-1] == 20, 5)
        pump(motion.COUNT_MS)
        self.assertNotIn(90, early)

    def test_switched_off_everything_lands_on_the_final_state_at_once(self):
        self.boot()
        wait_until(lambda: not self.covers(self.win), 5)
        motion.enabled = False
        seen = []
        motion.count(self.win.home.ready, 73, seen.append)
        motion.count_text(self.win.home.ready, "%d%%", 88)
        click(self.win.home.action_btn)
        self.assertEqual((seen, self.win.home.ready.text(), self.covers(self.win)), ([73], "88%", []))

    def test_check_mark_blink_and_team_bars_end_the_same_with_or_without_motion(self):
        self.assertTrue(120 <= motion.CHECK_MS <= 150)
        self.assertLessEqual(motion.BLINK_MS, 400)
        self.boot()
        win, page = self.win, self.win.round_page
        bot, lids = win.home.findChild(Mascot), []
        with mock.patch.object(bot, "_lid", side_effect=lambda t, real=bot._lid: (lids.append(t), real(t))):
            bot.blink()
            wait_until(lambda: lids and lids[-1] == 1.0, 5)
        self.assertTrue(len(lids) > 2 and bot.open == 1.0)  # 감았다가 다시 뜬 눈으로 끝남
        click(win.home.action_btn)
        item = self.select(lambda it: it["type"] == "choice" and not it["multi"])  # 복수 정답이면 아래에서 둘 다 골라진 채로 남음
        cards = page.choice_panel.buttons
        QTest.mouseClick(cards[0], LEFT)
        self.assertEqual((item["answer"], cards[0].isChecked()), ([1], True))  # 답은 체크가 그려지기를 기다리지 않음
        self.assertLess(cards[0].tick, 1.0)
        wait_until(lambda: cards[0].tick == 1.0, 5)
        click(page.home_btn)
        click(win.home.team_btn)
        wait_until(lambda: not self.covers(win), 5)
        card = win.team_page.cards[0]
        wait_until(lambda: getattr(card.bar, "_motion", None) is None, 5)
        moving = card.bar.value()

        motion.enabled = False
        bot.blink()
        self.assertEqual(bot.open, 1.0)
        click(win.team_page.home_btn)
        click(win.home.team_btn)
        self.assertEqual(win.team_page.cards[0].bar.value(), moving)
        click(win.team_page.home_btn)
        click(win.home.action_btn)
        self.select(lambda it: it is not None and it["id"] == item["id"])
        cards = page.choice_panel.buttons
        self.assertEqual((cards[0].isChecked(), cards[0].tick), (True, 1.0))
        click(cards[1])
        self.assertEqual((cards[1].tick, [card.isChecked() for card in cards[:2]]), (1.0, [False, True]))

    def test_confetti_falls_after_a_good_round_lets_clicks_through_and_removes_itself(self):
        self.assertTrue(1200 <= motion.CONFETTI_MS <= 1800)
        self.boot()
        win, result = self.win, self.win.result_page
        click(win.home.action_btn)
        self.answer_round(skip={1})
        self.submit_round()
        self.assertIs(self.page(), result)
        papers = result.findChildren(motion.Confetti)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].geometry(), result.rect())
        self.assertTrue(result.mascot.happy)
        earned = sum(it["points"] for it in result.view["items"][1:])
        wait_until(lambda: result.score.text().split(" / ")[0] == str(earned), 5)  # 점수는 색종이와 상관없이 끝 값까지 올라감
        wait_until(lambda: not self.covers(win), 5)
        self.assertEqual(len(result.findChildren(motion.Confetti)), 1)
        row = result.listw.visualItemRect(result.listw.item(2)).center()
        QTest.mouseClick(win.windowHandle(), LEFT, pos=result.listw.viewport().mapTo(win, row))  # 색종이 아래의 목록이 그대로 눌림
        self.assertEqual(result.listw.currentRow(), 2)
        self.assertIs(win.childAt(result.next_btn.mapTo(win, result.next_btn.rect().center())), result.next_btn)
        wait_until(lambda: not result.findChildren(motion.Confetti), 5)
        win.show_result("d1")  # 지난 회차를 다시 열 때는 떨어지지 않음
        self.assertEqual(result.findChildren(motion.Confetti), [])
        self.assertTrue(result.mascot.happy)
        motion.confetti(result)  # 떨어지는 동안 다른 결과를 열면 그 화면 위에 남지 않음
        win.show_result("d1")
        pump()
        self.assertEqual(result.findChildren(motion.Confetti), [])

    def test_no_confetti_for_a_poor_round_or_with_motion_off(self):
        self.boot()
        win, result = self.win, self.win.result_page
        click(win.home.action_btn)
        self.submit_round()  # 전부 미응답
        self.assertIs(self.page(), result)
        self.assertEqual((result.findChildren(motion.Confetti), result.mascot.happy), ([], False))
        motion.enabled = False
        click(result.next_btn)
        self.answer_round()
        self.submit_round()
        self.assertEqual((result.findChildren(motion.Confetti), result.mascot.happy), ([], True))


def save_delay():
    """자동 저장이 돌 만큼의 시간(ms)."""
    from gui.round_page import SAVE_DELAY_MS
    return SAVE_DELAY_MS + 250


if __name__ == "__main__":
    unittest.main()
