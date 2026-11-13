# -*- coding: utf-8 -*-
"""풀이·사용 안내만 바뀐 경우와 제품 변경·파일 이동을 구분함."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import ci_scope
from tools.ci_scope import needs_gui


class ScopeTest(unittest.TestCase):
    def test_shared_data_keeps_app_checks_and_readme_only_stays_light(self):
        for path in ("learning_data/collection.py", "learning_data/privacy.py", "learning_data/python.py"):
            with self.subTest(path=path):
                self.assertTrue(ci_scope.selection([path])["gui"])
                self.assertTrue(ci_scope.selection([path])["unit"])
        self.assertTrue(ci_scope.selection(["learning_data/collection.py"])["bank"])
        for old, new in (("aiprep/privacy.py", "learning_data/privacy.py"),
                         ("aiprep/sharing.py", "learning_data/sharing.py"),
                         ("submission_api.py", "learning_data/submission.py")):
            self.assertEqual(ci_scope.selection([old]), ci_scope.selection([new]))
        self.assertFalse(ci_scope.selection(["learning_data/README.md"])["gui"])
        self.assertFalse(ci_scope.selection([".dockerignore"])["gui"])

    def test_only_submissions_skip_gui(self):
        self.assertFalse(needs_gui(["submissions/learner/ai/record.json", "submissions/learner/r01/quiz.py"]))

    def test_user_guides_and_submissions_skip_gui(self):
        self.assertFalse(needs_gui(["README.md", "gui/README.md", "journey/README.md",
                                    "ai/README.md", "problems/README.md", "docs/GIT_GUIDE.md",
                                    "docs/roadmap/README.md", "submissions/learner/profile.json"]))

    def test_learning_content_assets_and_mixed_changes_keep_gui(self):
        for paths in (["README.md", "gui/theme.py"], ["ai/learning/i01.md"],
                      ["problems/s01/README.md"], ["dungeons/d01/p1/problem.md"],
                      ["docs/img/icon.png"], ["docs/img/screen-settings.png"],
                      ["docs/guide.json"], ["journey/README.md.bak"],
                      ["gui/widgets/README.md"], ["gui/window.py", "docs/window.md"]):
            with self.subTest(paths=paths):
                self.assertTrue(needs_gui(paths))

    def test_product_changes_and_unknown_diff_keep_gui(self):
        for paths in (["submissions/learner/profile.json", "gui/window.py"], ["adaptive.py"],
                      ["submissions_extra.py"], [".github/workflows/new-product.yml"], []):
            self.assertTrue(needs_gui(paths))

    def test_a_real_rename_keeps_the_deleted_product_path(self):
        with tempfile.TemporaryDirectory(prefix="scope_move_") as tmp:
            root = Path(tmp)
            def git(*args):
                result = subprocess.run(["git", "-c", "core.hooksPath=none", "-c", "user.name=Example",
                                         "-c", "user.email=example@example.invalid", *args], cwd=root,
                                        check=True, capture_output=True, text=True)
                return result.stdout.strip()

            git("init", "-q")
            (root / "gui").mkdir()
            (root / "docs").mkdir()
            (root / "gui/window.py").write_text("WINDOW = True\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "initial")
            base = git("rev-parse", "HEAD")
            git("mv", "gui/window.py", "docs/window.md")
            git("commit", "-qm", "move")
            head = git("rev-parse", "HEAD")
            previous = os.getcwd()
            try:
                os.chdir(root)
                with mock.patch.dict(os.environ, {"SCOPE_BASE": base, "SCOPE_HEAD": head, "GITHUB_OUTPUT": str(root / "output")}):
                    with contextlib.redirect_stdout(io.StringIO()):
                        ci_scope.main()
            finally:
                os.chdir(previous)
            self.assertIn("gui=true\n", (root / "output").read_text(encoding="utf-8"))


class SelectionTest(unittest.TestCase):
    def test_readme_and_model_notes_do_not_run_product_or_bank(self):
        self.assertEqual(dict(bank=False, unit=False, gui=False, model=False), ci_scope.selection(["README.md", "experiments/alice/README.md"]))
        self.assertEqual(dict(bank=False, unit=False, gui=False, model=False), ci_scope.selection(["docs/LEGACY_RECORDS.md", "docs/LEARNING_SERVER.md"]))
        self.assertEqual(dict(bank=False, unit=False, gui=False, model=False), ci_scope.selection(["docs/LEARNING_EXPERIMENT_TEMPLATE.md", "docs/LEARNING_DATA_ACCESS.md"]))

    def test_model_code_gets_syntax_check(self):
        self.assertEqual(dict(bank=False, unit=False, gui=False, model=True), ci_scope.selection(["experiments/alice/train.py"]))

    def test_unlisted_markdown_guides_keep_units_without_screen_tests(self):
        self.assertEqual(dict(bank=False, unit=True, gui=False, model=False),
                         ci_scope.selection(["docs/new-screen-guide.md"]))

    def test_server_changes_keep_function_tests(self):
        self.assertTrue(ci_scope.selection(["learning_server/app.py"])["unit"])
        self.assertFalse(ci_scope.selection(["learning_server/app.py"])["bank"])
        self.assertFalse(ci_scope.selection(["learning_server/app.py"])["gui"])
        self.assertTrue(ci_scope.selection(["aiprep/privacy.py"])["gui"])

    def test_unknown_and_renamed_product_paths_keep_full_checks(self):
        for paths in ([], ["adaptive.py"], ["gui/window.py", "docs/STUDY_START.md"]):
            selected = ci_scope.selection(paths)
            self.assertTrue(selected["unit"])
            self.assertTrue(selected["gui"])

    def test_model_and_product_changes_are_unioned_and_lookalike_paths_are_not_exempt(self):
        selected = ci_scope.selection(["experiments/alice/train.py", "gui/window.py"])
        self.assertTrue(all(selected.values()))
        for path in ("experiments/README.md", "experiments//train.py", "experiments/alice/../gui/window.py",
                     "experiments/alice/dir\\train.py", "experiments-old/alice/train.py"):
            with self.subTest(path=path):
                self.assertTrue(ci_scope.selection([path])["gui"])


class AutomationScopeTest(unittest.TestCase):
    def test_style_and_known_server_tests_keep_units_without_running_windows(self):
        for path in (".github/workflows/ci.yml", ".github/workflows/style.yml", ".github/workflows/slack-notify.yml", "tools/pr_checks.py", "tests/test_pr_checks.py", "tools/check_style.py", "tests/test_style.py", "tests/test_storage_capacity.py", "tests/test_sync_schedule.py", "tests/test_legacy_ai.py", ".github/workflows/learning-server.yml", "tools/collector_backup.py", "tests/test_collector_backup.py"):
            self.assertEqual(dict(bank=False, unit=True, gui=False, model=False), ci_scope.selection([path]))
        for path in ("docs/LEARNING_PILOT.md", "docs/LEARNING_READINESS.md", "docs/COLLECTOR_BACKUP.md"):
            self.assertEqual(dict(bank=False, unit=False, gui=False, model=False), ci_scope.selection([path]))
        self.assertTrue(ci_scope.selection(["tests/test_style_gui.py"])["gui"])

    def test_review_automation_keeps_function_checks_without_gui_or_bank(self):
        self.assertEqual(dict(bank=False, unit=True, gui=False, model=False),
                         ci_scope.selection(["tools/study_review_worker.py", "tests/test_study_review_worker.py"]))
        self.assertEqual(dict(bank=False, unit=True, gui=False, model=False),
                         ci_scope.selection(["tools/slack_threads.py", "tests/test_slack_threads.py"]))
        for path in ("tools/server_incident_alerts.py", "tests/test_server_incident_alerts.py",
                     ".github/workflows/server-incidents.yml"):
            self.assertEqual(dict(bank=False, unit=True, gui=False, model=False), ci_scope.selection([path]))
