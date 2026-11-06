# -*- coding: utf-8 -*-
"""강조 표시가 원문·코드·문항 조건을 바꾸지 않는지 확인함."""
import unittest

import mdlite
from tools import web_lint


class EmphasisTest(unittest.TestCase):
    def test_mark_and_underline_keep_nested_code_and_plain_text(self):
        text = "<mark>기울기와 `w.grad`</mark>, <u>갱신 뒤에는 예측을 다시 계산합니다</u>."
        self.assertEqual(mdlite.inline_plain(text), "기울기와 w.grad, 갱신 뒤에는 예측을 다시 계산합니다.")
        rendered = mdlite.inline_html(text)
        self.assertIn('<span class="highlight"><b>', rendered)
        self.assertIn("<code>w.grad</code>", rendered)
        self.assertIn("<u>갱신 뒤에는 예측을 다시 계산합니다</u>", rendered)

    def test_only_exact_paired_tags_are_formatting(self):
        text = '<mark onclick="x">값</mark> <u>닫히지 않음 <script>x</script>'
        rendered = mdlite.inline_html(text)
        self.assertNotIn('<mark onclick=', rendered)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;u&gt;', rendered)
        self.assertEqual(mdlite.inline_plain('`<mark>원문</mark>`'), '<mark>원문</mark>')

    def test_fenced_code_is_not_parsed_as_emphasis(self):
        source = '```python\ns = "<mark>문자열</mark>"\n```'
        self.assertEqual(mdlite.parse(source)[0]["text"], 's = "<mark>문자열</mark>"')

    def test_highlighting_a_definition_does_not_hide_its_introduction(self):
        text = "양수 T로 나누는 방법을 <mark>온도 스케일링</mark>이라고 부릅니다."
        shown = web_lint.plain(text)
        self.assertTrue(web_lint.definition_form(shown, "온도 스케일링"))
        self.assertFalse(web_lint.pseudo_definition(shown, "온도 스케일링"))
        self.assertEqual(web_lint.plain("<u>식 `z / T`</u>"), "식 " + web_lint.CODE_MARK)

    def test_legacy_box_heading_does_not_act_as_code_before_a_particle(self):
        self.assertEqual(web_lint.plain("> **[정정]** 이 줄을 확인합니다."), "이 줄을 확인합니다.")
        self.assertIsNone(web_lint.SPACED.search(web_lint.plain("> **[정정]** 이 줄을 확인합니다.")))
        self.assertIsNotNone(web_lint.SPACED.search(web_lint.plain("`x[0]` 을 확인합니다.")))


if __name__ == "__main__":
    unittest.main()
