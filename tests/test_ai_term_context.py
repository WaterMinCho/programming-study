# -*- coding: utf-8 -*-
"""긴 용어 안의 짧은 용어와 독립해서 쓴 짧은 용어를 구분함."""
from tests.test_ai_tools import Case


class TermContextTest(Case):
    def setUp(self):
        super().setUp()
        self.edit_json("terms.json", lambda d: d["terms"].extend([
            {"term": "잔차 연결", "also": [], "accept": [], "page": "l90"},
            {"term": "잔차", "also": [], "accept": [], "page": "l91"}]))

    def test_introduced_long_term_does_not_require_its_shorter_word(self):
        self.edit_item("i90-b01", lambda d: d.update(explain="잔차 연결을 사용합니다."))
        code, output = self.verify()
        self.assertEqual(0, code, output)

    def test_standalone_short_term_still_needs_an_introduction(self):
        self.edit_item("i90-b01", lambda d: d.update(explain="잔차 연결을 봅니다. 잔차는 뒤에서 배웁니다."))
        self.assertFails("91차시에서 소개하는 낱말 '잔차'")
