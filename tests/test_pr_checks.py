# -*- coding: utf-8 -*-
"""main 분기 뒤의 변경만 검사하고 제출 코드를 실행하지 않는지 확인함."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools import ci_scope, pr_checks


class PRChecksTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        previous = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return path

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=none", "-c", "user.name=Example",
                                       "-c", "user.email=example@example.invalid", *args], text=True).strip()

    def test_branch_behind_main_only_reports_its_own_model_notes(self):
        self.git("init", "-q")
        self.write("README.md", "공통 실행 안내를 읽습니다.\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        common = self.git("rev-parse", "HEAD")
        self.write("gui/window.py", "WINDOW = 1\n")
        self.git("add", ".")
        self.git("commit", "-qm", "program")
        base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-b", "model", common)
        name = self.write("experiments/alice/README.md", "내 모델 설명\n")
        self.git("add", ".")
        self.git("commit", "-qm", "notes")
        paths = ci_scope.changed_paths(base, self.git("rev-parse", "HEAD"))
        self.assertEqual([name], paths)
        self.assertFalse(any(ci_scope.selection(paths).values()))
        with self.assertRaises(ValueError):
            ci_scope.changed_paths("0" * 40, base)

    def test_only_changed_python_is_parsed_and_never_imported_or_executed(self):
        target = self.write("experiments/alice/train.py", 'from pathlib import Path\nPath("executed").write_text("bad")\n')
        self.write("experiments/bob/train.py", "this is invalid python :\n")
        self.assertEqual(0, pr_checks.model([target]))
        self.assertFalse((self.root / "executed").exists())
        for broken in ("def broken(:\n", "return 3\n"):
            self.write(target, broken)
            with self.subTest(source=broken), self.assertRaisesRegex(ValueError, "구문 오류"):
                pr_checks.model([target])

    def test_model_prose_is_reviewed_without_product_style_rules(self):
        target = self.write("experiments/alice/README.md", "\uBA3C\uC800 \uD574\uBD24\uC5B4\uC694!\n")
        self.assertEqual(0, pr_checks.style([target], "feat(model): 실습", "아직 학습은 안 해봤어요!"))

    def test_mixed_common_documents_still_use_the_product_style_rules(self):
        model = self.write("experiments/alice/README.md", "\uBA3C\uC800 \uD574\uBD24\uC5B4\uC694!\n")
        common = self.write("README.md", "\uBA3C\uC800 \uD574\uBD24\uC5B4\uC694!\n")
        self.assertEqual(1, pr_checks.style([model, common], "docs: 실행 안내 수정", "안내를 수정했음."))
        self.write(common, "설치 파일을 실행한 뒤 첫 화면에서 과목을 선택합니다.\n")
        self.assertEqual(0, pr_checks.style([model, common], "docs: 실행 안내 수정", "안내를 수정했음."))

    def test_removed_files_are_not_opened_and_outside_symlinks_are_rejected(self):
        self.assertEqual(0, pr_checks.model(["experiments/alice/deleted.py"]))
        self.assertEqual(0, pr_checks.style(["docs/deleted.md"], "docs: 오래된 안내 삭제", "안내를 삭제했음."))
        if os.name != "nt":
            target = self.root / "experiments/alice/link.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(self.root.parent / "outside.py")
            with self.assertRaisesRegex(ValueError, "일반 Python"):
                pr_checks.model(["experiments/alice/link.py"])


if __name__ == "__main__":
    unittest.main()
