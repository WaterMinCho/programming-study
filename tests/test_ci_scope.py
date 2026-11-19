# -*- coding: utf-8 -*-
"""풀이·사용 안내만 바뀐 경우와 제품 변경·파일 이동을 구분함."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
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
    def test_exact_launcher_paths_plan_both_os_without_screen_or_question_checks(self):
        paths = ("start.bat", "start.command", "ROKEY.app/Contents/MacOS/ROKEY",
                 "tools/install_python.ps1", "tools/install_python_macos.sh",
                 "tests/test_windows_start.py", "tests/test_mac_start.py", "tests/test_windowed.py")
        self.assertEqual(set(paths), ci_scope.LAUNCHER_PATHS)
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(dict(bank=False, unit=True, gui=False, model=False), ci_scope.selection([path]))
                self.assertTrue(ci_scope.needs_launcher([path]))
                self.assertFalse(ci_scope.needs_release_gui([path]))
        combined = [*paths, "README.md", ".github/workflows/ci.yml", ".github/workflows/release-check.yml",
                    "tools/ci_scope.py", "tests/test_ci_scope.py", "tools/slack_summary.py", "tests/test_slack_summary.py"]
        self.assertFalse(ci_scope.needs_release_gui(combined))
        self.assertFalse(ci_scope.selection(combined)["bank"])
        self.assertTrue(ci_scope.needs_release_gui([".github/workflows/release-check.yml"]))

    def test_launcher_mixed_runtime_and_lookalikes_keep_full_checks(self):
        for path in ("bootstrap.py", "start.pyw", "gui/window.py", "tests/test_bootstrap.py",
                     "ROKEY.app/Contents/Info.plist", "ROKEY.app/Contents/MacOS/ROKEY.old",
                     "tools/install_python_extra.ps1", "tests/test_windows_start_extra.py",
                     "tools/install_python_macos.sh.bak", "new-runtime.py"):
            with self.subTest(path=path):
                paths = ["start.bat", path]
                self.assertTrue(ci_scope.needs_launcher(paths))
                self.assertTrue(ci_scope.needs_release_gui(paths))
                self.assertTrue(all(ci_scope.selection(paths)[name] for name in ("bank", "unit", "gui")))
                self.assertFalse(ci_scope.terminal_launcher_only(path))
        self.assertTrue(ci_scope.selection(["start.bat", "experiments/alice/train.py"])["model"])
        self.assertTrue(ci_scope.needs_launcher(["start.bat", "experiments/alice/train.py"]))

    def test_scope_outputs_and_failed_diff_plan_all_checks(self):
        for paths in (["start.bat"], ["README.md"], ["start.bat", "gui/window.py"], [], None):
            with self.subTest(paths=paths), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "output"
                change = mock.patch.object(ci_scope, "changed_paths", return_value=paths,
                                           side_effect=OSError("diff failed") if paths is None else None)
                with change, mock.patch.dict(os.environ, {"SCOPE_BASE": "a" * 40, "SCOPE_HEAD": "b" * 40,
                                                          "GITHUB_OUTPUT": str(output)}):
                    with contextlib.redirect_stdout(io.StringIO()):
                        ci_scope.main()
                found = dict(line.split("=", 1) for line in output.read_text().splitlines())
                expected_paths = paths or []
                expected = dict(ci_scope.selection(expected_paths), launcher=ci_scope.needs_launcher(expected_paths),
                                release_gui=ci_scope.needs_release_gui(expected_paths))
                self.assertEqual({key: str(value).lower() for key, value in expected.items()}, found)

    def test_mac_shell_launcher_keeps_functions_without_screen_or_question_checks(self):
        for paths in (["start.command"], ["tests/test_mac_start.py"],
                      ["start.command", "tests/test_mac_start.py", "docs/LEARNER_START.md",
                       "gui/README.md", "docs/CHANGE_IMPACT.md", "tools/ci_scope.py", "tests/test_ci_scope.py"]):
            with self.subTest(paths=paths):
                self.assertEqual(dict(bank=False, unit=True, gui=False, model=False), ci_scope.selection(paths))

    def test_launcher_exemption_does_not_cover_mixed_or_unknown_paths(self):
        for path in ("gui/app.py", "bootstrap.py", "start.pyw", "ai/learning/i01.md",
                     "tests/test_gui_launcher.py", "start.command.bak", "tests/test_mac_start_extra.py"):
            with self.subTest(path=path):
                selected = ci_scope.selection(["start.command", path])
                self.assertTrue(selected["unit"])
                self.assertTrue(selected["gui"])
                self.assertTrue(selected["bank"])
        selected = ci_scope.selection(["start.command", "experiments/alice/train.py"])
        self.assertEqual(dict(bank=False, unit=True, gui=False, model=True), selected)

    def test_readme_and_model_notes_do_not_run_product_or_bank(self):
        self.assertEqual(dict(bank=False, unit=False, gui=False, model=False), ci_scope.selection(["README.md", "experiments/alice/README.md"]))
        self.assertEqual(dict(bank=False, unit=False, gui=False, model=False), ci_scope.selection(["docs/LEGACY_RECORDS.md", "docs/LEARNING_SERVER.md"]))
        self.assertEqual(dict(bank=False, unit=False, gui=False, model=False), ci_scope.selection(["docs/LEARNING_EXPERIMENT_TEMPLATE.md", "docs/LEARNING_DATA_ACCESS.md"]))

    def test_model_code_gets_syntax_check(self):
        self.assertEqual(dict(bank=False, unit=False, gui=False, model=True), ci_scope.selection(["experiments/alice/train.py"]))

    def test_underscore_model_folder_matches_hyphen_folder(self):
        self.assertTrue(ci_scope.model_path("experiments/kimjs85529_a11y/train.py"))
        for paths in (["experiments/kimjs85529_a11y/train.py"], ["experiments/kimjs85529_a11y/README.md"],
                      ["experiments/kimjs85529_a11y/train.py", "gui/window.py"]):
            with self.subTest(paths=paths):
                hyphen = [path.replace("kimjs85529_a11y", "kimjs85529-a11y") for path in paths]
                self.assertEqual(ci_scope.selection(hyphen), ci_scope.selection(paths))

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


class WorkflowPlanTest(unittest.TestCase):
    def test_required_job_rejects_missing_failed_or_skipped_planned_launcher(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        script = textwrap.dedent(workflow.split("python3 - <<'PYCODE'\n", 1)[1].split("          PYCODE", 1)[0])
        self.assertIn("needs: [scope, bank, gui, model, launcher]", workflow)
        for planned in (True, False):
            outputs = dict(bank="false", unit="true", gui="false", model="false", launcher=str(planned).lower())
            for status in ("success", "skipped", "failure", "cancelled", None):
                with self.subTest(planned=planned, status=status):
                    result = {"scope": {"result": "success", "outputs": outputs},
                              "bank": {"result": "success"}, "gui": {"result": "skipped"},
                              "model": {"result": "skipped"}}
                    if status is not None:
                        result["launcher"] = {"result": status}
                    with mock.patch.dict(os.environ, RESULTS=json.dumps(result)), contextlib.redirect_stdout(io.StringIO()):
                        if status == ("success" if planned else "skipped"):
                            exec(compile(script, "required-job", "exec"), {})
                        else:
                            with self.assertRaises((AssertionError, KeyError)):
                                exec(compile(script, "required-job", "exec"), {})


class AutomationScopeTest(unittest.TestCase):
    def test_title_workflow_keeps_function_checks_and_mixed_ui_keeps_gui(self):
        path = ".github/workflows/pr-title.yml"
        self.assertEqual(dict(bank=False, unit=True, gui=False, model=False), ci_scope.selection([path]))
        self.assertTrue(ci_scope.selection([path, "gui/theme.py"])["gui"])
        self.assertTrue(ci_scope.selection([".github/workflows/pr-title-extra.yml"])["gui"])

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
