# -*- coding: utf-8 -*-
"""합성 환경·예외로 문의 URL과 개인정보 제외 조건을 확인함."""
import copy
import datetime
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from gui import feedback


SECRET = "private-user@example.invalid /Users/private-user/answer.txt token=secret-answer"


def fields(url):
    query = parse_qs(urlsplit(url).query)
    return query, dict(line.split(": ", 1) for line in query["env"][0].splitlines())


def failure(filename):
    """실제 파일을 읽지 않고 지정 경로의 프레임을 가진 합성 예외를 만듦."""
    try:
        exec(compile("raise ValueError(secret)", str(filename), "exec"), {"secret": SECRET})
    except ValueError as error:
        return error, error.__traceback__


class FeedbackTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(feedback, "commit", return_value="a" * 40)
        self.commit = patcher.start()
        self.addCleanup(patcher.stop)

    def test_plain_report_has_only_template_and_editable_environment(self):
        url = feedback.issue_url()
        query, env = fields(url)
        self.assertEqual(urlsplit(url)._replace(query="").geturl(), feedback.ISSUE_URL)
        self.assertEqual(set(query), {"template", "env"})
        self.assertEqual(query["template"], ["trouble.yml"])
        self.assertEqual(set(env), {"OS", "OS_version", "Python", "PyQt", "Qt", "commit", "screen",
                                   "window", "DPR", "DPI", "text", "theme", "scheme"})
        self.assertEqual(env["commit"], "a" * 40)
        self.assertLess(len(url), 2000)

    def test_template_keeps_the_field_ids_and_other_form_link(self):
        text = (feedback.ROOT / ".github" / "ISSUE_TEMPLATE" / "trouble.yml").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^    id: (\w+)$", text, re.MULTILINE), ["what", "happened", "env"])
        self.assertIn("  - type: textarea\n    id: env\n", text)
        self.assertIn(feedback.CHOOSE_URL, text)

    def test_os_is_a_fixed_category_and_versions_are_numeric(self):
        cases = (("win32", "Windows", "10.0.26100"), ("darwin", "macOS", "15.2.1"),
                 ("linux", "Linux", feedback.UNKNOWN), (SECRET, feedback.UNKNOWN, feedback.UNKNOWN))
        for system, category, version in cases:
            with self.subTest(system=system), mock.patch.object(sys, "platform", system), \
                    mock.patch.object(sys, "getwindowsversion", create=True,
                                      return_value=SimpleNamespace(major=10, minor=0, build=26100)), \
                    mock.patch.object(feedback.platform, "mac_ver", return_value=("15.2.1", (), "arm64")):
                env = feedback.environment()
                self.assertEqual((env["OS"], env["OS_version"]), (category, version))
        for invalid in (SECRET, "3.12.0+private-user", "3.12.0rc1", "6.8\n" + SECRET, "１２.３", None):
            self.assertEqual(feedback._version(invalid), feedback.UNKNOWN)

    def test_python_uses_version_info_without_full_version_or_environment(self):
        with mock.patch.object(sys, "version", SECRET), mock.patch.dict(os.environ, {"PRIVATE_TOKEN": SECRET}), \
                mock.patch.object(feedback.platform, "uname", side_effect=AssertionError("uname")), \
                mock.patch.object(feedback.platform, "node", side_effect=AssertionError("node")):
            url = feedback.issue_url()
        self.assertEqual(fields(url)[1]["Python"], ".".join(str(n) for n in sys.version_info[:3]))
        self.assertNotIn(SECRET, fields(url)[0]["env"][0])

    def test_git_probe_is_fixed_quiet_bounded_and_validates_output(self):
        with mock.patch.object(feedback, "commit", ORIGINAL_COMMIT):
            for output, expected in (("b" * 40 + "\n", "b" * 40), ("c" * 64, "c" * 64), (SECRET, feedback.UNKNOWN)):
                with self.subTest(output=output), mock.patch.object(subprocess, "run", return_value=SimpleNamespace(stdout=output)) as run:
                    self.assertEqual(feedback.commit(), expected)
                    args, kwargs = run.call_args
                    self.assertEqual(args, (["git", "rev-parse", "HEAD"],))
                    self.assertEqual(kwargs["cwd"], feedback.ROOT)
                    self.assertLessEqual(kwargs["timeout"], 0.5)
                    self.assertTrue(kwargs["capture_output"])
                    self.assertTrue(kwargs["check"])
                    self.assertNotIn("shell", kwargs)
            for error in (FileNotFoundError(SECRET), subprocess.TimeoutExpired("git", 0.5),
                          subprocess.CalledProcessError(128, "git", stderr=SECRET)):
                with self.subTest(error=type(error).__name__), mock.patch.object(subprocess, "run", side_effect=error):
                    self.assertEqual(feedback.commit(), feedback.UNKNOWN)

    def test_commit_failure_does_not_block_the_form(self):
        self.commit.return_value = feedback.UNKNOWN
        self.assertEqual(fields(feedback.issue_url())[1]["commit"], feedback.UNKNOWN)

    def test_zip_folder_does_not_report_the_parent_repository_or_git_environment(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(feedback, "commit", ORIGINAL_COMMIT):
            root = Path(folder) / "programming-study"
            root.mkdir()
            with mock.patch.object(feedback, "ROOT", root), mock.patch.object(subprocess, "run") as run:
                self.assertEqual(feedback.commit(), feedback.UNKNOWN)
                run.assert_not_called()
            (root / ".git").mkdir()
            with mock.patch.object(feedback, "ROOT", root), \
                    mock.patch.dict(os.environ, {"GIT_DIR": SECRET, "GIT_WORK_TREE": SECRET}), \
                    mock.patch.object(subprocess, "run", return_value=SimpleNamespace(stdout="b" * 40)) as run:
                self.assertEqual(feedback.commit(), "b" * 40)
                env = run.call_args.kwargs["env"]
                self.assertNotIn("GIT_DIR", env)
                self.assertNotIn("GIT_WORK_TREE", env)
                self.assertEqual(env["GIT_CEILING_DIRECTORIES"], str(root.parent))

    def test_exception_string_and_attributes_are_never_serialized(self):
        class SensitiveError(Exception):
            def __str__(self):
                raise AssertionError("raw exception")
        error = SensitiveError()
        error.answer = error.token = error.filename = SECRET
        error.code = 403
        with mock.patch("builtins.open", side_effect=AssertionError("file read")), \
                mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            env = fields(feedback.issue_url(error=error))[1]
        self.assertEqual(env["exception"], "OtherError")
        self.assertNotIn("status", env)
        self.assertNotIn(SECRET, str(env))

    def test_custom_exception_names_including_a_64_character_token_are_excluded(self):
        token = "a1" * 32
        self.assertEqual(len(token), 64)
        for name in (token, "private_user", "개인아이디/영문토큰문자열"):
            with self.subTest(name=name):
                error = type(name, (Exception,), {})(SECRET)
                url = feedback.issue_url(error=error)
                env = fields(url)[1]
                self.assertEqual(env["exception"], "OtherError")
                self.assertNotIn(name, str(env))
                self.assertNotIn(name, url)

    def test_builtin_and_official_project_exception_names_are_preserved(self):
        from session import SessionError
        for kind in (ValueError, FileNotFoundError, SessionError):
            with self.subTest(kind=kind.__name__):
                self.assertEqual(feedback.error_details(kind(SECRET))["exception"], kind.__name__)

    def test_error_time_is_observed_utc_and_not_a_submission_time(self):
        before = datetime.datetime.now(datetime.timezone.utc)
        env = fields(feedback.issue_url(error=ValueError(SECRET)))[1]
        after = datetime.datetime.now(datetime.timezone.utc)
        observed = datetime.datetime.fromisoformat(env["error_observed_at_utc"])
        self.assertEqual(observed.utcoffset(), datetime.timedelta())
        self.assertLessEqual(before.replace(microsecond=0), observed)
        self.assertLessEqual(observed, after)
        self.assertNotIn("submitted_at", env)
        plain = fields(feedback.issue_url())[1]
        for key in ("exception", "status", "location", "error_observed_at_utc"):
            self.assertNotIn(key, plain)

    def test_http_status_has_to_be_an_integer_in_range(self):
        error = HTTPError("https://example.invalid/" + SECRET, 503, SECRET, {}, None)
        self.addCleanup(error.close)
        self.assertEqual(feedback.error_details(error)["status"], "503")
        for code in (True, "403", 99, 600, SECRET, None):
            error.code = code
            self.assertNotIn("status", feedback.error_details(error))
        self.assertNotIn("status", feedback.error_details(ValueError(SECRET)))

    def test_source_location_uses_only_known_program_relative_paths(self):
        error, tb = failure(feedback.ROOT / "gui" / "window.py")
        details = feedback.error_details(error, tb)
        self.assertEqual(details["location"], "gui/window.py:1")
        self.assertNotIn(str(feedback.ROOT), str(details))
        self.assertNotIn(SECRET, str(details))

    def test_user_files_are_excluded_even_inside_a_program_folder(self):
        for filename in (feedback.ROOT / "gui" / "private_user.py", feedback.ROOT / "submissions" / "answer.py",
                         feedback.ROOT / "experiments" / "private_user" / "model.py", Path("/private/tmp/window.py")):
            with self.subTest(filename=filename):
                error, tb = failure(filename)
                self.assertNotIn("location", feedback.error_details(error, tb))

    def test_raw_text_without_exception_does_not_become_error_metadata(self):
        self.assertEqual(feedback.error_details(SECRET), {})


ORIGINAL_COMMIT = feedback.commit

try:
    from tests import guikit
    from PyQt6.QtWidgets import QLabel, QStackedWidget, QWidget
    from gui import dialogs, errors, theme
except unittest.SkipTest:
    guikit = None


@unittest.skipIf(guikit is None, "PyQt6가 없어 화면 연결 검사를 건너뜁니다")
class FeedbackGuiTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(feedback, "commit", return_value="d" * 40)
        patcher.start()
        self.addCleanup(patcher.stop)
        old_theme = copy.deepcopy(theme.state)
        self.addCleanup(theme.state.update, old_theme)
        self.window = QWidget()
        self.addCleanup(self.window.deleteLater)
        self.window.pages = QStackedWidget(self.window)
        self.window.hub = QWidget()
        self.window.pages.addWidget(self.window.hub)
        self.window.resize(760, 480)

    def test_window_dimensions_scale_and_only_known_screen_keys(self):
        screen = SimpleNamespace(devicePixelRatio=lambda: 1.5, logicalDotsPerInch=lambda: 96.0)
        with mock.patch.object(self.window, "screen", return_value=screen):
            for mode in ("light", "dark"):
                theme.state.update(mode=mode, scheme=mode, text="larger")
                env = fields(feedback.issue_url(self.window))[1]
                self.assertEqual((env["screen"], env["window"], env["DPR"], env["DPI"]), ("hub", "760x480", "1.5", "96"))
                self.assertEqual((env["text"], env["theme"], env["scheme"]), ("larger", mode, mode))
            self.window.pages.addWidget(QWidget())
            self.window.pages.setCurrentIndex(1)
            self.window.screen_key = self.window.user = self.window.answer = SECRET
            self.assertEqual(feedback.environment(self.window)["screen"], feedback.UNKNOWN)
        for value in (float("nan"), float("inf"), SECRET, True, -1, 10 ** 300):
            self.assertEqual(feedback._number(value, 0.25, 16), feedback.UNKNOWN)

    def test_unavailable_window_or_theme_does_not_block_the_form(self):
        with mock.patch.object(self.window, "screen", side_effect=RuntimeError(SECRET)), \
                mock.patch.dict(theme.state, {"text": SECRET, "mode": SECRET, "scheme": SECRET}):
            env = fields(feedback.issue_url(self.window))[1]
        for key in ("DPR", "DPI", "text", "theme", "scheme"):
            self.assertEqual(env[key], feedback.UNKNOWN)
        self.assertNotIn(SECRET, str(env))

    def test_error_in_a_dialog_or_inactive_application_uses_the_main_window(self):
        from PyQt6.QtWidgets import QApplication, QDialog
        dialog = QDialog(self.window)
        self.addCleanup(dialog.deleteLater)
        dialog.resize(300, 200)
        for active in (dialog, None):
            with self.subTest(active=active), \
                    mock.patch.object(QApplication, "activeWindow", return_value=active), \
                    mock.patch.object(QApplication, "topLevelWidgets", return_value=[dialog, self.window]):
                env = fields(feedback.issue_url(error=ValueError(SECRET)))[1]
                self.assertEqual((env["screen"], env["window"]), ("hub", "760x480"))

    def test_error_hook_uses_safe_url_without_opening_or_submitting(self):
        old_hook, old_state = sys.excepthook, errors.state.copy()
        self.addCleanup(setattr, sys, "excepthook", old_hook)
        self.addCleanup(errors.state.update, old_state)
        errors.state["dialog"] = None
        error, tb = failure(feedback.ROOT / "gui" / "window.py")
        with mock.patch.object(errors, "write_log", return_value="/private/log/secret.log"), \
                mock.patch.object(sys, "stderr", None), mock.patch.object(dialogs, "ErrorDialog") as dialog:
            errors.install("/private/log")
            sys.excepthook(type(error), error, tb)
        env = fields(dialog.call_args.args[2])[1]
        self.assertEqual((env["exception"], env["location"]), ("ValueError", "gui/window.py:1"))
        self.assertNotIn(SECRET, str(env))
        self.assertNotIn("/private/log", str(env))
        dialog.return_value.show.assert_called_once_with()

    def test_python_home_report_uses_the_environment_at_each_click(self):
        from gui.home_page import HomePage
        window = mock.Mock()
        page = HomePage(window)
        self.addCleanup(page.deleteLater)
        urls = [feedback.ISSUE_URL + "?env=first", feedback.ISSUE_URL + "?env=second"]
        with mock.patch.object(feedback, "issue_url", side_effect=urls) as build, \
                mock.patch("gui.home_page.QDesktopServices.openUrl") as opened:
            for url in urls:
                page.foot.linkActivated.emit(feedback.ISSUE_URL)
                self.assertEqual(opened.call_args.args[0].toString(), url)
            self.assertEqual(build.call_args_list, [mock.call(window), mock.call(window)])
        self.assertFalse(page.foot.openExternalLinks())

    def test_startup_dialog_link_has_environment_and_keeps_form_choice(self):
        with mock.patch("PyQt6.QtWidgets.QApplication.activeWindow", return_value=None):
            url = feedback.issue_url()
        dialog = dialogs.ErrorDialog(SECRET, "/private/log/secret.log", url)
        self.addCleanup(dialog.deleteLater)
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        note = next(text for text in labels if "불편 신고 양식" in text)
        self.assertIn("template=trouble.yml&amp;env=", note)
        self.assertIn(feedback.CHOOSE_URL, note)
        self.assertNotIn(SECRET, note)
        self.assertNotIn("/private/log", note)


if __name__ == "__main__":
    unittest.main()
