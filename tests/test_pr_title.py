# -*- coding: utf-8 -*-
"""제목의 형식·줄바꿈·셸 기호를 실행 없이 확인함."""
import unittest
from tools.pr_title import valid


class TitleTest(unittest.TestCase):
    def test_commit_and_pr_scope_rules_match(self):
        from tools import check_style
        for title in ("fix(learning): 저장 처리", "fix(model/lstm): 입력 확인", "fix(학습): 저장 처리"):
            errors = check_style.check(title, commit=True)
            rejected = any(rule.startswith("커밋 제목 형식") for rule, _ in errors)
            self.assertEqual(valid(title), not rejected, title)

    def test_types_and_optional_scope(self):
        for title in ("docs(model): 공통 입력 확인", "fix: 빈 이력 처리", "feat(model/lstm): 학습·평가 추가"):
            self.assertTrue(valid(title))

    def test_typo_missing_description_and_extra_lines_are_rejected(self):
        for title in ("dosc: 기록", "docs: ", "docs:x", "docs: 제목\n추가", "Merge branch", "x"*121):
            self.assertFalse(valid(title))

    def test_shell_characters_remain_plain_title_text(self):
        self.assertTrue(valid("test(model): `mask`와 $value 확인"))
