# -*- coding: utf-8 -*-
"""묶음 완료·시작 시점의 파일 제출을 화면을 잠그지 않고 직렬 처리함."""
import hashlib
import json
import os
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer

from learning_data.collection import CollectionError, digest
from learning_data.submission import submit_private
from learning_data import sync_schedule
from gui.worker import Job


def signature(api):
    """내용을 읽지 않고 파일 변경과 영구 오류의 재시도 여부를 구분함."""
    root = Path(api.root)/"submissions"/api.user
    rows = []
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "dist"))
        for name in sorted(names):
            path = Path(base)/name
            if name.startswith("."):
                continue
            try:
                st = path.lstat()
            except FileNotFoundError:
                continue
            rows.append((path.relative_to(root).as_posix(), st.st_size, st.st_mtime_ns))
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


class AutoSubmission(QObject):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.job = win, None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.tick)
        self.cancel = threading.Event()
        self.generation, self.wanted, self.closing, self.failures = 0, False, False, 0
        self.choice = None

    def request(self):
        if self.closing or os.environ.get("STUDY_AUTO_SYNC", "1") == "0":
            return
        self.generation += 1
        self.wanted = True
        if self.job is None and not self.timer.isActive():
            self.timer.start(min(1500, sync_schedule.initial_ms()))

    def changed(self):
        controller = getattr(self.win, "privacy", None)
        if controller is None:
            return
        try:
            choice = controller.consent.settings().get("choice")
        except CollectionError:
            return
        if self.choice != choice:
            self.choice = choice
            self.cancel.set()
            self.request()

    def key(self, api):
        value = os.path.realpath(str(api.path))
        return "automatic-submission/"+hashlib.sha256(value.encode()).hexdigest()

    def clear_blocked(self):
        api = getattr(self.win.gitflow, "api", None)
        if api:
            self.win.settings.remove(self.key(api))

    def tick(self):
        win = self.win
        if not self.wanted or self.closing or self.job is not None or os.environ.get("STUDY_AUTO_SYNC", "1") == "0":
            return
        if win.job is not None or win.submission_running or win.pending_close or win.close_pending:
            self.timer.start(1000)
            return
        api = getattr(win.gitflow, "api", None)
        controller = getattr(win, "privacy", None)
        if api is None or controller is None or not win.has_submission_consent():
            return
        try:
            state = controller.consent.settings()
            scope = state.get("receipt", {}).get("automatic_submission")
            if scope is None:
                return
            config = api.settings()
            if scope.get("accepted") is False and (not config.get("token") or config.get("consent_stamp") == digest(state["receipt"])):
                self.wanted = False
                return
            stamp = signature(api)
            config_at = api.path.stat().st_mtime_ns if api.path.exists() else None
        except FileNotFoundError:
            self.failures += 1
            if self.failures <= 3:
                self.timer.start(1000)
            else:
                self.wanted = False
            return
        except (CollectionError, OSError, ValueError):
            self.wanted = False
            return
        blocked = {"files": stamp, "choice": state["choice"], "connection": config_at}
        if win.settings.value(self.key(api), "", type=str) == json.dumps(blocked, sort_keys=True):
            self.wanted = False
            return
        generation, user, choice = self.generation, win.user, state["choice"]
        self.cancel.clear()
        win.submission_running = True
        win.pending_version += 1
        win.workspace.refresh()
        def work():
            if self.cancel.is_set():
                return {"status": "paused", "message": "자동 제출을 멈췄습니다."}
            return submit_private(api, automatic=True, canceled=self.cancel.is_set)
        job = self.job = Job(work)
        def done(result):
            same = win.user == user and getattr(win.gitflow, "api", None) is not None and win.gitflow.api.path == api.path
            try:
                same = same and win.privacy.consent.settings().get("choice") == choice
            except CollectionError:
                same = False
            if same and not self.closing:
                if result.get("status") == "error" and not result.get("retryable", False):
                    blocked["connection"] = api.path.stat().st_mtime_ns if api.path.exists() else None
                    win.settings.setValue(self.key(api), json.dumps(blocked, sort_keys=True))
                    self.wanted = generation != self.generation
                elif result.get("status") == "error":
                    self.failures = min(4, self.failures + 1)
                    self.wanted = True
                else:
                    self.failures = 0
                    self.wanted = generation != self.generation
                    self.clear_blocked()
                if scope.get("accepted") and result.get("status") not in ("nothing", "paused"):
                    if result.get("status") == "ok":
                        result = dict(result, message="풀이를 비공개 서버에 자동 제출했습니다.")
                    if result.get("status") == "ok":
                        win.pending_submission = {"status": "checking", "pending": False, "count": 0}
                    win.workspace.submissions.show_result(result)
        def release():
            job.deleteLater()
            self.job = None
            win.submission_running = False
            win.workspace.refresh()
            if not self.closing:
                win.check_pending_submission()
            if self.closing:
                win.close()
            elif self.wanted:
                self.timer.start(sync_schedule.delay_ms(self.failures) if self.failures else 0)
        job.done.connect(done)
        job.failed.connect(lambda *_: done({"status": "error", "message": "자동 제출을 마치지 못했습니다. 로컬 풀이는 유지합니다. [풀이 제출]로 다시 시도하거나 운영자에게 문의해 주세요.", "retryable": False}))
        job.finished.connect(release)
        job.start()

    def stop(self):
        self.closing = True
        self.timer.stop()
        self.cancel.set()
        return self.job is None

    def resume(self):
        if self.closing:
            self.closing = False
            self.cancel.clear()
            self.request()
