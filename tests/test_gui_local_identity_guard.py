# -*- coding: utf-8 -*-
"""합성 풀이로 ID 확인 실패·업데이트 중단·복원 뒤 재시도를 확인함."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests import guikit
from PyQt6.QtCore import QPoint, QSettings
from PyQt6.QtWidgets import QLabel

import session
import study
from gui import theme
from gui.window import MainWindow


class LocalIdentityGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="study_gui_identity_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])
        for patcher in (mock.patch.object(study, "ROOT", str(self.root)),
                        mock.patch.object(study, "SUBMISSIONS_DIR", str(self.root / "submissions")),
                        mock.patch.object(study, "USER_FILE", str(self.root / ".study_user")),
                        mock.patch.dict(os.environ, {"STUDY_AUTO_SYNC": "0", "STUDY_NODE_PROBE": "0",
                                                     "STUDY_AI_HOME": str(self.root / "ai-home"),
                                                     "STUDY_PYTHON_HOME": str(self.root / "python-home"),
                                                     "STUDY_WEB_HOME": str(self.root / "web-home")}),
                        mock.patch("socket.create_connection", side_effect=AssertionError("unexpected network")),
                        mock.patch("socket.socket.connect", side_effect=AssertionError("unexpected network"))):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop("STUDY_USER", None)
        for key in list(os.environ):
            if key.upper().startswith("GIT_"):
                del os.environ[key]
        os.environ["GIT_ALLOW_PROTOCOL"] = "file"
        self.slot_errors = []
        patcher = mock.patch.object(sys, "excepthook", lambda *args: self.slot_errors.append(args))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.settings = QSettings(str(self.root / "settings.ini"), QSettings.Format.IniFormat)
        self.settings.setValue("text", "larger")
        self.settings.setValue("theme", "light")
        self.flow = mock.Mock()
        self.flow.sync.return_value = {"status": "nothing"}
        self.factory = mock.Mock(return_value=(self.flow, ""))
        self.win = MainWindow(self.settings, self.factory)
        self.open_patcher = mock.patch.object(self.win, "open_session", return_value=True)
        self.open_session = self.open_patcher.start()
        self.addCleanup(self.open_patcher.stop)
        self.opened = []
        self.win.open_url = self.opened.append
        self.win.resize(760, 480)
        self.win.show()
        guikit.pump()

    def tearDown(self):
        guikit.wait_until(lambda: self.win.job is None and self.win.pending_job is None)
        self.win.close()
        self.win.deleteLater()
        guikit.pump()
        self.assertEqual(self.slot_errors, [])
        self.assertEqual(self.opened, [])

    def write(self, name, data=b'{"fixture": true}\n'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def baseline(self):
        self.write("submissions/.gitkeep", b"")
        for args in (("init", "-q"), ("add", "--", "submissions"), ("commit", "-qm", "fixture"),
                     ("update-ref", "refs/remotes/origin/main", "HEAD")):
            subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "user.name=Fixture",
                            "-c", "user.email=fixture@example.invalid", "-C", str(self.root), *args],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def assert_stopped(self):
        self.assertIsNone(self.win.user)
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win.gitflow)
        self.assertIs(self.win.pages.currentWidget(), self.win.start)
        self.assertTrue(self.win.start.retry.isVisible())
        self.assertFalse(self.win.start.busy_bar.isVisible())
        self.factory.assert_not_called()
        self.flow.sync.assert_not_called()
        self.open_session.assert_not_called()

    def test_invalid_id_never_saves_or_updates_even_after_retry(self):
        path = self.write(".study_user", b"valid-file-learner\n")
        with mock.patch.dict(os.environ, STUDY_USER="../invalid"), mock.patch.object(session, "save_user") as save:
            self.win.boot()
            self.assert_stopped()
            guikit.click(self.win.start.retry)
            self.assert_stopped()
            save.assert_not_called()
        self.assertEqual(path.read_bytes(), b"valid-file-learner\n")

    def test_missing_id_stops_before_sync_and_restored_id_retries_boot(self):
        self.baseline()
        path = self.write("submissions/previous-learner/r01/quiz.py", b"answer = 3\n")
        with mock.patch.object(session, "save_user", wraps=session.save_user) as save:
            self.win.boot()
            self.assert_stopped()
            guikit.click(self.win.start.retry)
            self.assert_stopped()
            self.write(".study_user", b"\xef\xbb\xbfprevious-learner\r\n")
            guikit.click(self.win.start.retry)
            guikit.wait_until(lambda: self.win.job is None)
            save.assert_not_called()
        self.assertEqual(self.win.user, "previous-learner")
        self.factory.assert_called_once_with(str(self.root), "previous-learner")
        self.flow.sync.assert_called_once_with()
        self.open_session.assert_called_once_with()
        self.assertEqual(path.read_bytes(), b"answer = 3\n")
        self.assertEqual(self.win.start.error.text(), "")

    def test_fresh_empty_install_and_explicit_valid_id_keep_normal_sync(self):
        for explicit in (None, "explicit-learner"):
            with self.subTest(explicit=explicit):
                if explicit is not None:
                    os.environ["STUDY_USER"] = explicit
                with mock.patch.object(session, "save_user", wraps=session.save_user) as save:
                    self.win.boot()
                    guikit.wait_until(lambda: self.win.job is None)
                    if explicit is None:
                        save.assert_called_once()
                        self.assertTrue(self.win.user.startswith("learner-"))
                    else:
                        save.assert_not_called()
                        self.assertEqual(self.win.user, explicit)
                self.factory.assert_called_once()
                self.flow.sync.assert_called_once_with()
                self.open_session.assert_called_once_with()
                self.factory.reset_mock()
                self.flow.reset_mock()
                self.open_session.reset_mock()

    def test_existing_record_error_keeps_open_session_retry(self):
        self.open_patcher.stop()
        self.win.user = "known-learner"
        with mock.patch.object(self.win, "ensure_identity", return_value=True), \
                mock.patch.object(session, "Session", side_effect=session.SessionError("기록 파일을 읽지 못했습니다.")), \
                mock.patch.object(self.win, "boot") as boot:
            self.assertFalse(self.win.open_session())
            with mock.patch.object(self.win, "open_session", wraps=self.win.open_session) as reopened:
                guikit.click(self.win.start.retry)
                reopened.assert_called_once_with()
            boot.assert_not_called()
        self.factory.assert_not_called()

    def test_error_and_retry_fit_small_window_at_max_text_both_themes(self):
        for number in range(4):
            self.write(f"submissions/shared-{number}/profile.json", b'{"fixture": 3}\r\n')
        self.baseline()
        subprocess.run(["git", "-C", str(self.root), "config", "core.autocrlf", "true"], check=True, timeout=5)
        self.assertIsNone(session.saved_user())
        record = self.write("submissions/previous-learner/ai/record.json")
        output = os.environ.get("LOCAL_IDENTITY_EVIDENCE") or os.environ.get("CAREER_EVIDENCE")
        if output:
            Path(output).mkdir(parents=True, exist_ok=True)
        for mode in ("light", "dark"):
            self.win.set_theme(mode)
            for state in ("missing", "invalid", "unreadable", "git-failure"):
                with self.subTest(mode=mode, state=state):
                    path = self.root / ".study_user"
                    if path.exists():
                        path.unlink()
                    if state == "invalid":
                        self.write(".study_user", b" \r\n")
                    if state == "unreadable":
                        failure = mock.patch.object(study, "read_text", side_effect=PermissionError("fixture"))
                    elif state == "git-failure":
                        failure = mock.patch.object(session.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 3))
                    else:
                        failure = mock.patch.dict(os.environ)
                    with failure, mock.patch.object(session, "save_user") as save:
                        self.win.boot()
                        self.assert_stopped()
                        first = self.win.start.error.text()
                        guikit.click(self.win.start.retry)
                        self.assert_stopped()
                        self.assertEqual(self.win.start.error.text(), first)
                        save.assert_not_called()
                    error, retry = self.win.start.error, self.win.start.retry
                    guikit.wait_until(lambda: error.height() >= error.heightForWidth(error.width())
                                      and self.win.start.rect().contains(error.geometry())
                                      and self.win.start.rect().contains(retry.geometry()), timeout=3)
                    self.assertEqual((self.win.width(), self.win.height()), (760, 480))
                    self.assertEqual(theme.state["text"], "larger")
                    self.assertEqual(error.font().pixelSize(), theme.TYPE["body"][0])
                    self.assertEqual(retry.font().pixelSize(), theme.TYPE["label"][0])
                    heading = next(label for label in self.win.start.findChildren(QLabel) if label.text() == "프로그래밍 스터디")
                    self.assertEqual(heading.font().pixelSize(), theme.TYPE["title"][0])
                    self.assertGreater(heading.font().pixelSize(), error.font().pixelSize())
                    self.assertGreaterEqual(retry.width(), retry.fontMetrics().horizontalAdvance(retry.text()) + 16)
                    self.assertGreaterEqual(retry.height(), retry.fontMetrics().height())
                    self.assertLess(error.geometry().bottom(), retry.geometry().top())
                    for widget in (error, retry):
                        top = widget.mapTo(self.win, QPoint())
                        self.assertTrue(self.win.rect().contains(top))
                        self.assertTrue(self.win.rect().contains(top + widget.rect().bottomRight()))
                    if output:
                        self.assertTrue(self.win.grab().save(str(Path(output) / f"local-identity-{mode}-{state}.png")))
                    self.assertEqual(record.read_bytes(), b'{"fixture": true}\n')


if __name__ == "__main__":
    unittest.main()
