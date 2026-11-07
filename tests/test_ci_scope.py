# -*- coding: utf-8 -*-
"""풀이만 바꾼 경우와 화면·공통 코드가 함께 바뀐 경우를 구분함."""
import unittest

from tools.ci_scope import needs_gui


class ScopeTest(unittest.TestCase):
    def test_only_submissions_skip_gui(self):
        self.assertFalse(needs_gui(["submissions/learner/ai/record.json", "submissions/learner/r01/quiz.py"]))

    def test_product_changes_and_unknown_diff_keep_gui(self):
        for paths in (["submissions/learner/profile.json", "gui/window.py"], ["adaptive.py"],
                      ["submissions_extra.py"], [".github/workflows/ci.yml"], []):
            self.assertTrue(needs_gui(paths))
