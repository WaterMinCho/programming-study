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
                      ["docs/guide.json"], ["docs/new-screen-guide.md"], ["journey/README.md.bak"],
                      ["gui/widgets/README.md"], ["gui/window.py", "docs/window.md"]):
            with self.subTest(paths=paths):
                self.assertTrue(needs_gui(paths))

    def test_product_changes_and_unknown_diff_keep_gui(self):
        for paths in (["submissions/learner/profile.json", "gui/window.py"], ["adaptive.py"],
                      ["submissions_extra.py"], [".github/workflows/ci.yml"], []):
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
            self.assertEqual("gui=true\n", (root / "output").read_text(encoding="utf-8"))
