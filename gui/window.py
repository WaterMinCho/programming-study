# -*- coding: utf-8 -*-
"""메인 창. 시작 순서(ID → 새 문제 받기 → 풀이 기록 열기 → 웹 트랙의 Node 찾기), 화면 전환, 워커, 제출 흐름, 테마를 맡음.
첫 화면은 허브이고, 파이썬 스터디(홈 이하), 알고리즘 여행(지도·문제 화면), 웹 면접 준비(웹 홈·미션·드릴·학습 노트)로 나뉨.
area 가 지금 어느 쪽에 있는지 기억함. 웹 트랙의 Node 는 허브 카드가 설치 상태를 보이므로 허브를 열기 전에 워커에서 한 번 찾아 두고,
여행의 [다시 찾기]가 기억을 버렸으면 허브나 웹 홈을 열기 전에 다시 찾음."""
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QFileDialog, QLabel, QMainWindow, QProgressBar, QPushButton, QStackedWidget, QVBoxLayout,
                             QWidget)

import session
import study
from gui import errors, journey_text, kit, motion, theme, web_text
from gui.dialogs import IdDialog, MessageDialog
from gui.guard import Guard
from gui.home_page import HomePage
from gui.hub_page import HubPage
from gui.journey_map import JourneyMapPage
from gui.journey_page import JourneyPage, saved_lang, with_node
from gui.result_page import ResultPage
from gui.round_page import RoundPage
from gui.team_page import TeamPage
from gui.web_drill import WebDrillPage
from gui.web_home import WebHomePage
from gui.web_learn import WebLearnPage
from gui.web_mission import WebMissionPage, open_folder
from gui.widgets import Para
from gui.worker import Job
from gui.wrong_page import WrongPage
from journey import node as node_finder
from journey.service import JourneyError, JourneySession
from session import SessionError
from webprep import service as web_service
from webprep import stack
from webprep.record import RecordError
from webprep.service import WebError


def saved_text(settings):
    """저장된 글자 크기 단계. 없으면 옛 확대 단계(zoom: 문서와 코드만 키우던 값)를 단계로 옮기고 그 키를 지움. 줄였으면 보통,
    0~2 는 크게(새 기본), 3 이상은 더 크게. 둘 다 없으면 기본."""
    step = settings.value("text", "", type=str)
    if step in theme.TEXT_PX:
        return step
    if settings.contains("zoom"):
        zoom = settings.value("zoom", 0, type=int)
        step = "normal" if zoom < 0 else ("large" if zoom < 3 else "larger")
        settings.remove("zoom")
        settings.setValue("text", step)
        return step
    return theme.TEXT_DEFAULT


def load_gitflow(root, user):
    """제출 모듈을 불러와 (GitFlow | None, 못 쓰는 이유)를 돌려줌. 모듈이 없거나 깨져도 풀이와 채점은 돼야 해서 예외를 삼킴."""
    try:
        import gitflow
        return gitflow.GitFlow(root, user), ""
    except Exception as error:
        return None, "제출 모듈(gitflow.py)을 불러오지 못했습니다: %s" % error


class StartPage(QWidget):
    """시작 화면. 새 문제를 확인하는 동안과 풀이 기록을 열지 못했을 때 보임."""

    def __init__(self, win):
        super().__init__()
        self.setObjectName("page")
        box = QVBoxLayout(self)
        box.setSpacing(14)
        title = QLabel("프로그래밍 스터디")
        title.setObjectName("h1")
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedWidth(260)
        self.busy_bar.hide()
        self.error = Para(name="error")
        self.error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.retry = QPushButton("다시 시도")
        self.retry.hide()
        self.retry.clicked.connect(lambda: win.open_session())
        box.addStretch(2)
        for widget in (title, self.status, self.busy_bar):
            box.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(self.error)  # 정렬 플래그를 주면 줄바꿈한 글이 제 높이를 받지 못해 잘림
        box.addWidget(self.retry, 0, Qt.AlignmentFlag.AlignHCenter)
        box.addStretch(3)

    def set_busy(self, busy, text=""):
        self.status.setText(text if busy else "")
        self.busy_bar.setVisible(busy)

    def show_error(self, text):
        self.error.setText(text)
        self.retry.setVisible(bool(text))


class MainWindow(QMainWindow):
    def __init__(self, settings, gitflow_factory=load_gitflow):
        super().__init__()
        self.setWindowTitle("프로그래밍 스터디")
        self.settings, self.gitflow_factory = settings, gitflow_factory
        self.user, self.session, self.gitflow, self.git_reason = None, None, None, ""
        self.journey, self.journey_error = None, ""  # 알고리즘 여행 서비스와 그것을 열지 못한 이유
        self.web, self.web_error = None, ""  # 웹 면접 준비 서비스와 열지 못한 이유
        self.web_node_known, self.web_node_seen = False, False  # 웹 트랙의 Node 를 찾아 봤는지, 그때 node 모듈이 결과를 기억했는지
        self.area = "hub"  # 지금 있는 쪽: hub, python(홈 이하), journey(지도·문제 화면), web(웹 홈·미션·드릴·학습 노트)
        self.job = None  # 도는 중인 워커 (Job, 잠근 화면, 끝났을 때, 실패했을 때)
        self.dialog = None  # 가장 최근에 띄운 대화상자
        self.notice = None  # 허브와 홈 위쪽에 한 줄로 보여 줄 제출 모듈의 결과
        self.restart, self.close_pending = False, False
        self.open_url = lambda url: QDesktopServices.openUrl(QUrl(url))
        self.pick_file = lambda title: QFileDialog.getOpenFileName(self, title)[0]
        self.open_folder = lambda path: open_folder(path, settings)  # 미션 폴더를 편집기로 엶. 테스트는 가짜로 바꿈
        theme.set_text(saved_text(settings))  # 화면을 만들기 전에 정해야 부품이 그 크기로 만들어짐
        theme.set_mode(settings.value("theme", "system", type=str))

        self.pages = QStackedWidget()
        self.start, self.hub, self.home, self.round_page = StartPage(self), HubPage(self), HomePage(self), RoundPage(self)
        self.result_page, self.team_page, self.wrong_page = ResultPage(self), TeamPage(self), WrongPage(self)
        self.journey_map, self.journey_page = JourneyMapPage(self), JourneyPage(self)
        self.web_home, self.web_mission, self.web_drill, self.web_learn = WebHomePage(self), WebMissionPage(self), WebDrillPage(self), WebLearnPage(self)
        for page in (self.start, self.hub, self.home, self.round_page, self.result_page, self.team_page, self.wrong_page,
                     self.journey_map, self.journey_page, self.web_home, self.web_mission, self.web_drill, self.web_learn):
            self.pages.addWidget(page)
        self.setCentralWidget(self.pages)
        self.restyle()  # 스타일시트가 있으면 부모가 바뀔 때 위젯 글꼴이 초기화되므로 창에 붙인 뒤에 글꼴을 줌
        theme.signals.changed.connect(self.restyle)
        room = self.screen().availableGeometry()  # 작은 노트북 화면에서 아래쪽 버튼이 화면 밖으로 나가지 않게
        self.resize(min(1280, room.width() - 40), min(800, room.height() - 60))
        if settings.value("geometry"):
            self.restoreGeometry(settings.value("geometry"))
        for keys, step in ((QKeySequence.StandardKey.ZoomIn, 1), ("Ctrl+=", 1), (QKeySequence.StandardKey.ZoomOut, -1)):
            QShortcut(QKeySequence(keys), self, lambda step=step: self.step_text(step))
        QShortcut(QKeySequence("Ctrl+0"), self, lambda: self.set_text(theme.TEXT_DEFAULT))
        self.guard = Guard(self)
        QApplication.instance().installEventFilter(self.guard)
        self.guard.blocked.connect(self.round_page.note_blocked)

    # 시작 순서

    def boot(self):
        user = session.saved_user()
        if user:
            self.sync_first(user)
            return
        self.dialog = IdDialog(self, self.sync_first)
        self.dialog.rejected.connect(self.close)  # ID 없이는 진행할 수 없음
        self.dialog.show()

    def sync_first(self, user):
        """새 컴퓨터에서 빈 기록이 먼저 생기지 않게, 풀이 기록을 열기 전에 새 문제부터 받음."""
        self.user = user
        self.gitflow, self.git_reason = self.gitflow_factory(study.ROOT, user)
        if self.gitflow is None:
            self.open_session()
            return
        self.run_job("새 문제 확인 중입니다.", self.gitflow.sync, self._synced_first, on_fail=self.open_session)

    def _synced_first(self, result):
        if result.get("restart"):
            self._restart(result)
            return
        diverged = result.get("status") == "diverged"
        if not diverged and (result.get("status") not in ("ok", "nothing") or result.get("changed") or result.get("backup")):
            self.notice = result  # 오프라인·git 없음 같은 결과는 홈에 한 줄로만 알리고 계속 진행함
        if self.open_session() and diverged:
            self._git_done("문제 받기", dict(result, changed=False))

    def open_session(self, then=None):
        """풀이 기록과 문제 은행을 새로 읽고 then()(없으면 허브)으로 감. 풀이 기록을 읽지 못하면 시작 화면에 이유를 보여 주고 False 를 돌려줌.
        알고리즘 여행 기록을 읽지 못하면 파이썬 스터디는 그대로 열고, 허브의 여행 카드에 이유를 보여 줌. 여기서는 node 를 찾지 않음."""
        try:
            self.session = session.Session(self.user)
        except SessionError as error:
            self.start.show_error("%s\n파일을 고친 뒤 '다시 시도'를 눌러 주세요. 고치기 어려우면 스터디장에게 알려 주세요." % error)
            motion.switch(self.pages, self.start)
            return False
        saved_node = self.settings.value("journey/node", "", type=str) or None
        try:
            self.journey = JourneySession(self.user, node_path=saved_node)
            self.journey_error = ""
        except JourneyError as error:
            self.journey, self.journey_error = None, str(error)
        if self.web is not None:
            self.web.stop_serving()  # 서비스를 새로 만들면 옛 서비스가 띄운 화면 서버를 끌 길이 없어짐
        try:
            self.web = web_service.WebSession(self.user, node_path=saved_node)
            self.web_error = ""
        except WebError as error:
            self.web, self.web_error = None, str(error)
        self.start.show_error("")
        go = then or self.go_hub
        if not self.web_node_first(go):
            go()
        return True

    def web_node_first(self, then):
        """웹 트랙의 Node 를 아직 찾지 않았거나 여행의 [다시 찾기]가 기억을 버렸으면 워커에서 찾은 뒤 then() 을 부르고 True 를 돌려줌.
        허브의 웹 카드와 웹 홈이 Node 상태를 보이므로 화면 스레드에서 node 를 띄우지 않음. 테스트처럼 찾기를 가짜로 바꾼 곳에서는
        node 모듈이 결과를 기억하지 않으므로(web_node_seen 이 거짓) 한 번 찾은 뒤 다시 찾지 않음."""
        if self.web is None:
            return False
        forgotten = self.web_node_seen and not node_finder.searched(stack.MIN_NODE)
        if self.web_node_known and not forgotten:
            return False
        return self.run_job("Node.js 를 찾는 중입니다.", self.web.node, lambda info: self._web_node_found(then),
                            on_fail=lambda: self._web_node_found(then))

    def _web_node_found(self, then):
        self.web_node_known, self.web_node_seen = True, node_finder.searched(stack.MIN_NODE)
        then()

    def _stay_here(self):
        """문제 받기로 은행이나 풀이 폴더가 바뀐 뒤, 보던 쪽에 머묾. 문제 화면은 같은 문제를 다시 읽고, 그 문제가 사라졌으면 지도로 감."""
        if self.area == "python":
            self.go_home()
        elif self.area == "journey" and self.journey is not None:
            if self.pages.currentWidget() is self.journey_page and self.journey_page.reload():
                return
            self.go_journey()
        elif self.area == "web" and self.web is not None:
            if self.pages.currentWidget() is self.web_mission and self.web_mission.reload():
                return
            self.go_web()
        else:
            self.go_hub()

    # 화면 전환

    def go_hub(self):
        if not self.leave_pages(self.go_hub, "저장하지 않고 나가기"):
            return
        if self.web_node_first(self.go_hub):
            return
        self.hub.refresh()
        self.area = "hub"
        motion.switch(self.pages, self.hub)

    def go_home(self):
        if not self.leave_round(self.go_home, "저장하지 않고 나가기"):
            return
        self.home.refresh()
        self.area = "python"
        motion.switch(self.pages, self.home)

    def go_journey(self, did=None):
        if not self.leave_pages(lambda: self.go_journey(did), "저장하지 않고 나가기"):
            return
        if self.node_first(lambda: self.go_journey(did)):
            return
        self.journey_map.refresh(did)
        self.area = "journey"
        motion.switch(self.pages, self.journey_map)

    def go_web(self):
        if not self.leave_pages(self.go_web, "저장하지 않고 나가기"):
            return
        if self.web_node_first(self.go_web):
            return
        self.web_home.refresh()
        self.area = "web"
        motion.switch(self.pages, self.web_home)

    def open_mission(self, mid):
        try:
            self.web_mission.load(mid)
        except (SessionError, RecordError) as error:  # 출제되지 않은 미션, 깨진 봉인 파일, 도는 동안 깨진 기록
            self.ask("알림", str(error))
            return
        self.area = "web"
        motion.switch(self.pages, self.web_mission)

    def open_drill(self, cid, back=None, resume=False):
        """사슬 cid 를 처음부터 풂. resume 이면 같은 사슬이 화면에 남아 있을 때(학습 노트를 읽고 돌아올 때) 그 자리로 돌아감."""
        if not (resume and self.web_drill.cid == cid):
            try:
                self.web_drill.load(cid, back)
            except (SessionError, RecordError) as error:  # 끝내지 않은 미션의 꼬리 질문, 없는 사슬, 도는 동안 깨진 기록
                self.ask("알림", str(error))
                return
        self.area = "web"
        motion.switch(self.pages, self.web_drill)

    def open_learn(self, pid, section="", back=None):
        try:
            self.web_learn.load(pid, section, back)
        except (SessionError, RecordError) as error:
            self.ask("알림", str(error))
            return
        self.area = "web"
        motion.switch(self.pages, self.web_learn)

    def open_problem(self, did, pid):
        if self.node_first(lambda: self.open_problem(did, pid)):
            return
        try:
            self.journey_page.load(did, pid)
        except SessionError as error:  # 잠긴 보스, 사라진 문제, 앞 문제의 코드를 저장하지 못한 경우
            title, text, detail = journey_text.error_text("open", error)
            self.ask(title, text, detail=detail)
            return
        self.area = "journey"
        self.settings.setValue("journey/last", "%s/%s" % (did, pid))
        motion.switch(self.pages, self.journey_page)

    def node_first(self, then):
        """JavaScript 를 고른 적이 있는데 node 를 아직 찾아 보지 않았으면 워커에서 찾은 뒤 then() 을 부르고 True 를 돌려줌.
        지도와 문제 화면은 언어를 정할 때 기억한 결과만 읽으므로, 화면 스레드에서 node 를 띄우지 않음."""
        if saved_lang(self.settings) != "javascript" or self.journey.node_checked():
            return False
        with_node(self, lambda ok: then())
        return True

    def leave_pages(self, then, leave):
        """회차 화면의 답과 문제 화면의 코드를 모두 저장했으면 True. 인자는 leave_round 와 같음."""
        return self.leave_round(then, leave) and self.leave_journey(then, leave)

    def leave_round(self, then, leave):
        """회차 화면을 떠나기 전에 쓰던 답을 저장하고 True 를 돌려줌. 저장하지 못하면 알리고 False 를 돌려줌.
        leave 는 그 답을 버리고 떠나는 버튼의 글자. 그 버튼을 고르면 then() 을 부름."""
        page = self.round_page
        if page.flush(offer=False):
            return True

        def drop(_):
            page.dirty.clear()
            then()

        self.ask("저장하지 못한 답", "%s\n\n쓰던 답 %d개가 파일에 저장되지 않았습니다. [돌아가기]를 누르면 회차 화면으로 돌아가고 쓰던 답은 화면에 남습니다. "
                 "풀이 폴더의 파일을 다른 프로그램에서 열어 두었다면 닫고 다시 나가 보세요.\n"
                 "[%s]를 누르면 저장되지 않은 답은 지워집니다." % (page.status.text(), len(page.dirty), leave),
                 (("돌아가기", ""), (leave, "drop")), drop)
        return False

    def leave_journey(self, then, leave):
        """문제 화면을 떠나기 전에 쓰던 코드를 저장하고 True 를 돌려줌. 저장하지 못하면 알리고 False 를 돌려줌. 인자는 leave_round 와 같음."""
        page = self.journey_page
        if page.flush(offer=False):
            return True

        def drop(_):
            page.dirty.clear()
            then()

        self.ask("저장하지 못한 코드", "쓰던 코드가 파일에 저장되지 않았습니다. [돌아가기]를 누르면 문제 화면으로 돌아가고 쓰던 코드는 화면에 남습니다. "
                 "풀이 폴더의 파일을 다른 프로그램에서 열어 두었다면 닫고 다시 나가 보세요.\n"
                 "[%s]를 누르면 저장되지 않은 코드는 지워집니다." % leave,
                 (("돌아가기", ""), (leave, "drop")), drop, detail=page.save_error)
        return False

    def next_action(self, overview):
        """'지금 할 일' 버튼의 글자와 설명."""
        current = overview["current"]
        if not overview["rounds"]:
            return "진단 테스트 시작", "단원마다 몇 문항씩 풀어 출발 레벨을 정합니다. 모르는 문항은 비워 두고 제출하면 됩니다."
        if current is None:
            return "다음 회차 시작", "지난 회차를 모두 제출했습니다."
        name = "진단 테스트" if current["kind"] == "diag" else "%d회차" % int(current["id"][1:])
        try:
            pending = self.session.pending(current["id"])
            written = pending["total"] - len(pending["blank"])
        except SessionError:  # 답안지를 읽지 못한 경우. 회차를 열 때 복구를 제안함
            written = 1
        desc = "%s · %d문항" % (current["title"], current["size"])
        if written:
            desc += " · 작성한 문항 %d개" % written
        if current["size_reason"]:
            desc += "\n문항 수 기준: %s" % current["size_reason"]
        return "%s %s" % (name, "이어 풀기" if written else "시작"), desc

    def start_next(self):
        """풀던 회차가 있으면 그 회차를, 없으면 다음 회차(처음이면 진단)를 만들어 띄움."""
        try:
            rnd, _ = self.session.ensure_round()
        except SessionError as error:
            self.ask("알림", str(error))
            return
        if rnd is None:
            self.ask("알림", "전 단원을 심화까지 끝내 더 낼 문항이 없습니다.\n터미널에서 python study.py start m1 (2회는 m2, 3회는 m3)로 모의고사를 볼 수 있습니다.")
            return
        self.open_round(rnd["id"])

    def open_round(self, rid, review=False, select=None):
        try:
            self.round_page.load(rid, review, select)
        except SessionError as error:
            self._session_error(error, rid, lambda: self.open_round(rid, review, select))
            return
        motion.switch(self.pages, self.round_page)

    def show_result(self, rid, result=None):
        try:
            self.result_page.load(rid, result)
        except SessionError as error:
            self._session_error(error, rid, lambda: self.show_result(rid, result))
            return
        motion.switch(self.pages, self.result_page)

    def show_team(self):
        self.team_page.refresh()
        motion.switch(self.pages, self.team_page)

    def show_wrong(self):
        self.wrong_page.refresh()
        motion.switch(self.pages, self.wrong_page)

    # 대화상자

    def ask(self, title, text, buttons=(("확인", "ok"),), on_choice=None, detail="", link=""):
        """대화상자를 띄움. 빈 키("")가 아닌 버튼을 고르면 on_choice(키)를 부름. 글에 든 터미널 명령은 단추 이름으로 바꿈."""
        if self.dialog is not None and not self.dialog.isVisible():
            self.dialog.deleteLater()  # 닫힌 대화상자가 창에 쌓이지 않게
        self.dialog = MessageDialog(self, title, web_text.gui_text(text), buttons, lambda key: key and on_choice and on_choice(key), detail, link)
        self.dialog.show()
        return self.dialog

    def show_notice_detail(self):
        self.ask("자세히", self.notice.get("message") or "", detail=self.notice.get("detail") or "")

    def _session_error(self, error, rid, retry):
        """SessionError 의 문구를 대화상자로 보여 줌. 답안지가 깨진 경우에는 복구를 제안함."""
        if self.session.quiz_problem(rid):
            self.offer_repair(rid, retry)
        else:
            self.ask("알림", str(error))

    def offer_repair(self, rid, then):
        """깨진 답안지(quiz.py)의 복구를 제안하고, 복구한 뒤 then() 을 부름."""
        if self.dialog is not None and self.dialog.isVisible():  # 자동 저장이 거듭 실패해도 대화상자는 하나만
            return
        problem = self.session.quiz_problem(rid)
        if not problem:
            return

        def repair(_):
            kept = self.session.repair_quiz(rid)
            then()
            self.ask("답안지 복구", "답안지를 복구했습니다. 읽을 수 있던 답 %d개를 남겼습니다.\n원본은 같은 폴더의 quiz.py.bak 에 있습니다." % kept)

        self.ask("답안지 복구", "%s\n\n복구하면 읽을 수 있는 답만 남기고 답안지를 새로 씁니다. 원본은 같은 폴더에 quiz.py.bak 으로 보관합니다." % problem,
                 (("답안지 복구", "repair"), ("닫기", "")), repair)

    # 워커

    def run_job(self, text, fn, on_done, on_fail=None, on_progress=None):
        """fn 을 워커 스레드에서 돌리고, 끝나면 화면 스레드에서 on_done(결과)을 부름. 도는 동안 지금 화면을 잠금.
        on_progress 가 있으면 fn(진행 알림, 취소 신호)로 부르고, 워커가 낸 진행 알림마다 화면 스레드에서 on_progress(알림)를 부름.
        다른 일이 도는 중이면 시작하지 않고 False 를 돌려줌."""
        if self.job is not None:
            return False
        page = self.pages.currentWidget()
        page.set_busy(True, text)
        job = Job(fn, progress=on_progress is not None)
        self.job = (job, page, on_done, on_fail)
        if on_progress is not None:
            job.progress.connect(on_progress)
        job.done.connect(self._job_done)
        job.failed.connect(self._job_failed)
        job.start()
        return True

    def _job_end(self):
        job, page, on_done, on_fail = self.job
        job.wait()
        self.job = None
        page.set_busy(False)
        return on_done, on_fail

    def _job_done(self, result):
        on_done, _ = self._job_end()
        on_done(result)
        if self.close_pending:
            self.close()

    def _job_failed(self, message, trace):
        _, on_fail = self._job_end()
        if trace:
            errors.report(trace)
        else:
            self.ask("알림", message)
        if on_fail:
            on_fail()
        if self.close_pending:
            self.close()

    # 제출 · 문제 받기

    def submit_pr(self):
        if self.round_page.flush() and self.journey_page.flush():  # 쓰다 만 답과 코드가 빠진 채 올라가지 않게
            self.run_job("제출하는 중입니다.", self.gitflow.submit, lambda result: self._git_done("제출", result))

    def fetch_problems(self):
        if self.round_page.flush() and self.journey_page.flush():
            self.run_job("새 문제 확인 중입니다.", self.gitflow.sync, self._fetched)

    def _fetched(self, result):
        if self.web_node_first(lambda: self._fetched(result)):
            return
        self.notice = None  # 시작할 때 받지 못했다는 알림은 방금 결과가 대신함
        self.home.refresh()
        self.hub.refresh()
        self._git_done("문제 받기", result)

    def _git_done(self, title, result):
        if result.get("restart"):
            self._restart(result)
            return
        if result.get("changed") and not self.open_session(self._stay_here):  # 문제나 내 풀이 폴더가 바뀌었으면 새로 읽음
            return
        message = result.get("message") or "(안내 문구가 없습니다)"
        if result.get("backup"):
            message += "\n보관한 사본: %s" % result["backup"]
        detail = result.get("detail") or ""
        if result.get("status") == "diverged":
            self.ask(title, message, (("다른 컴퓨터의 풀이 가져오기", "remote"), ("이 컴퓨터 풀이로 올리기", "local"), ("나중에 정하기", "")),
                     lambda choice: self.run_job("처리하는 중입니다.", lambda: self._resolve(title, choice),
                                                 lambda done: self._git_done(title, done)), detail)
            return
        url = result.get("pr_url") if result.get("status") == "ok" else None
        if url:
            self.open_url(url)
            message += "\n\n브라우저에서 PR 페이지를 열었습니다. 열리지 않았으면 아래 주소를 누르세요."
        self.ask(title, message, detail=detail, link=url or "")

    def _resolve(self, title, choice):
        """갈라진 풀이를 정함. 문제 받기 도중이었으면 그 전에는 새 문제가 들어오지 않았으므로 받기를 마저 함."""
        done = self.gitflow.resolve(choice)
        if title == "문제 받기" and done.get("status") in ("ok", "nothing"):
            again = self.gitflow.sync()
            again["changed"] = again.get("changed") or done.get("changed")
            again["backup"] = again.get("backup") or done.get("backup")
            return again
        return done

    def _restart(self, result):
        """도구 파일이 바뀌었으면 옛 코드로 새 파일을 다루지 않게, 대화상자를 어떻게 닫든 다시 시작함."""
        dialog = self.ask("프로그램 갱신", result.get("message") or "프로그램이 새 버전으로 바뀌었습니다. 다시 시작합니다.", (("다시 시작", "ok"),))
        dialog.finished.connect(self._quit_for_restart)

    def _quit_for_restart(self):
        self.restart = True
        self.close()

    # 글자 크기 · 테마 · 닫기

    @property
    def zoom(self):
        """옛 화면의 문서와 코드 글꼴이 받는 확대 단계. 글자 크기 단계가 더하는 px 와 같음."""
        return theme.text_px()

    def set_text(self, step):
        """글자 크기 단계를 고르고 기억함. 모든 부품의 글꼴을 다시 주고 화면마다 문서를 다시 넣음."""
        theme.set_text(step)
        self.settings.setValue("text", theme.state["text"])
        kit.refont(self)  # 열려 있는 대화상자도 창의 자식이라 같이 바뀜
        self.restyle()

    def step_text(self, step):
        """Ctrl+= 와 Ctrl+- 로 한 단계 키우거나 줄임. 끝에서는 그대로."""
        steps = list(theme.TEXT_STEPS)
        self.set_text(steps[max(0, min(len(steps) - 1, steps.index(theme.state["text"]) + step))])

    def cycle_theme(self):
        """시스템 → 밝게 → 어둡게 순서로 다음 테마를 고르고 기억함."""
        modes = list(theme.MODES)
        mode = modes[(modes.index(theme.state["mode"]) + 1) % len(modes)]
        self.settings.setValue("theme", mode)

        def change():
            theme.set_mode(mode)
            self.home.restyle()  # 밝기가 그대로여도 단추의 글자는 바뀜
            self.hub.restyle()

        motion.fade_over(self, change)

    def restyle(self):
        """글자 크기나 테마가 바뀌면 화면마다 본문과 색을 다시 넣음."""
        for page in (self.hub, self.home, self.round_page, self.result_page, self.wrong_page, self.journey_map, self.journey_page,
                     self.web_home, self.web_mission, self.web_drill, self.web_learn):
            page.restyle()

    def closeEvent(self, event):
        if self.job is not None:  # 스레드를 도중에 버리면 프로세스가 죽으므로 채점·제출이 끝난 뒤에 닫음
            self.job[0].cancel.set()  # 여행 채점은 곧 멈추고 기록하지 않음. [테스트 돌리기]는 vitest 를 끊고 대화상자 없이 끝남. 다른 일은 이 신호를 보지 않음
            self.close_pending = True
            self.job[1].set_busy(True, "하던 작업이 끝나면 창을 닫습니다.")
            event.ignore()
            return
        if not self.leave_pages(self.close, "저장하지 않고 닫기"):
            event.ignore()
            return
        if self.web is not None:
            self.web.stop_serving()  # 미션 화면의 [화면 띄우기]로 띄운 서버가 프로그램보다 오래 남지 않게 끔
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()
