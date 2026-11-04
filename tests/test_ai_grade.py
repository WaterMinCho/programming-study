# -*- coding: utf-8 -*-
"""aiprep.grade 테스트(설계 3.2, 3.9). 모드별 정규화 표, 부분 점수, 낱말 사전 동의어, 고르기 채점을 봄.

실행: python -m unittest tests.test_ai_grade
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aiprep import grade  # noqa: E402

TERMS = {"terms": [{"term": "과적합", "also": ["과대적합"], "accept": ["과학습", "overfitting"]},
                   {"term": "기울기", "also": ["그래디언트"], "accept": ["gradient"]}]}


def ok(answer, value, mode="word", **extra):
    return grade.grade_blank(dict({"answer": [answer] if isinstance(answer, str) else answer, "mode": mode}, **extra), value)


class WordTest(unittest.TestCase):
    def test_spaces_hyphens_dots_and_case(self):
        self.assertTrue(ok("역전파", "역 전파"))
        self.assertTrue(ok("원핫", "원-핫"))
        self.assertTrue(ok("one-hot", "One Hot"))
        self.assertTrue(ok("가중치", " '가중치'. "))
        self.assertTrue(ok("평균", "`평균`"))
        self.assertTrue(ok("배치정규화", "배치·정규화"))

    def test_trailing_particle_or_ending_once(self):
        self.assertTrue(ok("역전파", "역전파를"))
        self.assertTrue(ok("역전파", "역전파입니다"))
        self.assertTrue(ok("검증", "검증으로"))
        self.assertTrue(ok("기울기", "기울기이다"))
        self.assertFalse(ok("역전파", "역전파기"))
        self.assertFalse(ok("역전파", "역전파를을"))
        self.assertFalse(ok("반대", "반"))

    def test_terms_also_and_accept(self):
        self.assertTrue(grade.grade_blank({"answer": ["과적합"], "mode": "word"}, "과대적합", TERMS))
        self.assertTrue(grade.grade_blank({"answer": ["과적합"], "mode": "word"}, "과학습", TERMS))
        self.assertTrue(grade.grade_blank({"answer": ["과적합"], "mode": "word"}, "Overfitting", TERMS))
        self.assertTrue(grade.grade_blank({"answer": ["경사"], "mode": "word", "term": "기울기"}, "그래디언트", TERMS))
        self.assertFalse(grade.grade_blank({"answer": ["과적합"], "mode": "word"}, "과소적합", TERMS))
        self.assertFalse(grade.grade_blank({"answer": ["과적합"], "mode": "word"}, "과대적합"))

    def test_accept_of_another_term_works_one_way(self):
        terms = {"terms": [{"term": "미분값", "accept": ["도함수 값", "기울기"]}, {"term": "기울기", "accept": ["경사"]}]}
        self.assertTrue(grade.grade_blank({"answer": ["미분값"], "mode": "word"}, "기울기", terms))
        self.assertTrue(grade.grade_blank({"answer": ["기울기"], "mode": "word"}, "경사", terms))
        self.assertFalse(grade.grade_blank({"answer": ["기울기"], "mode": "word"}, "미분값", terms))
        self.assertFalse(grade.grade_blank({"answer": ["기울기"], "mode": "word"}, "도함수 값", terms))

    def test_empty_is_wrong(self):
        self.assertFalse(ok("역전파", ""))
        self.assertFalse(ok("역전파", "   "))
        self.assertFalse(ok("역전파", None))


class CodeTest(unittest.TestCase):
    def test_spaces_quotes_and_case(self):
        self.assertTrue(ok("view(2,3)", "view( 2, 3 )", "code"))
        self.assertTrue(ok("x.view(2, 3)", "`x.view(2,3)`", "code"))
        self.assertTrue(ok("'cpu'", "“cpu”", "code"))
        self.assertTrue(ok("'cpu'", '"cpu"', "code"))
        self.assertFalse(ok("CrossEntropyLoss", "crossentropyloss", "code"))

    def test_parentheses_dot_and_context(self):
        item = {"stem": "```python\noptimizer.____()\n```", "blanks": [{"answer": ["zero_grad"], "mode": "code"}]}
        for value in ("zero_grad", "zero_grad()", ".zero_grad", "optimizer.zero_grad()", "optimizer.zero_grad"):
            self.assertEqual("pass", grade.grade_item(item, [value])["result"], value)
        self.assertEqual("stuck", grade.grade_item(item, ["step()"])["result"])
        item = {"stem": "`nn.Linear(____, 50)`", "blanks": [{"answer": ["784"], "mode": "code"}]}
        self.assertEqual("pass", grade.grade_item(item, ["784,"])["result"])
        self.assertTrue(ok(["zero_grad()"], "zero_grad()", "code"))

    def test_contexts(self):
        self.assertEqual([("optimizer.", "()"), ("nn.Linear(", ",")], grade.contexts("optimizer.____()\nnn.Linear(____, 50)"))


class NumberTest(unittest.TestCase):
    def test_commas_minus_fraction_unit(self):
        self.assertTrue(ok("101770", "101,770", "number"))
        self.assertTrue(ok("-0.5", "−0.5", "number"))
        self.assertTrue(ok("-0.5", "–0.5", "number"))
        self.assertTrue(ok("0.25", "1/4", "number"))
        self.assertTrue(ok("2.8", "２.８", "number"))
        self.assertTrue(ok("3457", "3457개", "number", unit="개"))
        self.assertTrue(ok("1e-3", "0.001", "number"))
        self.assertFalse(ok("2.8", "2.80001", "number"))
        self.assertFalse(ok("2.8", "약 2.8", "number"))

    def test_huge_or_deep_input_is_wrong_quickly(self):
        for value in ("1e100000000", "1" * 5000 + "/3"):
            self.assertFalse(ok("2.8", value, "number"))
        self.assertFalse(ok("[1, 2]", "[1e100000000, 2]", "values"))
        self.assertFalse(ok("[1, 2]", "[" * 3000 + "1", "values"))

    def test_places_round_half_up(self):
        self.assertTrue(ok("0.1429", "0.14286", "number", places=4))
        self.assertTrue(ok("0.125", "0.13", "number", places=2))
        self.assertTrue(ok("2.5", "3", "number", places=0))
        self.assertFalse(ok("0.1429", "0.1428", "number", places=4))


class ShapeTest(unittest.TestCase):
    def test_forms(self):
        for value in ("[100, 10]", "(100, 10)", "100×10", "100x10", "torch.Size([100, 10])"):
            self.assertTrue(ok("(100, 10)", value, "shape"), value)
        self.assertTrue(ok("torch.Size([])", "()", "shape"))
        self.assertTrue(ok("torch.Size([])", "[]", "shape"))
        self.assertTrue(ok("torch.Size([])", "torch.Size([])", "shape"))
        for value in ("x", ",", "*", "torch.Size"):
            self.assertFalse(ok("torch.Size([])", value, "shape"), value)
        self.assertTrue(ok("(3,)", "[3]", "shape"))
        self.assertFalse(ok("(100, 10)", "(10, 100)", "shape"))
        self.assertFalse(ok("(100, 10)", "(100, 10, a)", "shape"))


class ValuesTest(unittest.TestCase):
    def test_structure_matters(self):
        self.assertTrue(ok("[[70, 100], [150, 220]]", "[[70,100],[150,220]]", "values"))
        self.assertFalse(ok("[[70, 100], [150, 220]]", "[70, 100, 150, 220]", "values"))
        self.assertTrue(ok("[1, -1]", "tensor([1., -1.])", "values"))
        self.assertTrue(ok("[1, -1]", "tensor([1., −1.])", "values"))
        self.assertTrue(ok("[[1, 2], [3, 4]]", "array([[1, 2], [3, 4]], dtype=int64)", "values"))
        self.assertTrue(ok("[1, 2]", "(1, 2)", "values"))
        self.assertTrue(ok("3", "np.int64(3)", "values"))

    def test_bool_differs_from_number(self):
        self.assertTrue(ok("[True, False]", "tensor([True, False])", "values"))
        self.assertFalse(ok("[True, False]", "[1, 0]", "values"))

    def test_places_and_unreadable(self):
        self.assertTrue(ok("[0.33, 0.67]", "[0.333, 0.667]", "values", places=2))
        self.assertFalse(ok("[1, 2]", "[1, 2", "values"))
        self.assertIsNone(grade.norm("values", "[1, x]"))


class ExactTest(unittest.TestCase):
    def test_only_outer_spaces(self):
        self.assertTrue(ok("1.4286e-01", " 1.4286e-01 ", "exact"))
        self.assertFalse(ok("1.4286e-01", "1.4286E-01", "exact"))


class ItemTest(unittest.TestCase):
    def test_partial_and_stuck(self):
        item = {"stem": "____ 와 ____", "blanks": [{"answer": ["a"], "mode": "code"}, {"answer": ["b"], "mode": "code"}]}
        self.assertEqual({"result": "pass", "per_blank": [True, True]}, grade.grade_item(item, ["a", "b"]))
        self.assertEqual({"result": "partial", "per_blank": [True, False]}, grade.grade_item(item, ["a", "c"]))
        self.assertEqual({"result": "stuck", "per_blank": [False, False]}, grade.grade_item(item, ["", ""]))
        self.assertEqual("stuck", grade.grade_item(item, [])["result"])

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            grade.norm("nope", "x")


class ChoiceTest(unittest.TestCase):
    ITEM = {"pick": "wrong", "options": [{"ok": True}, {"ok": True}, {"ok": False}, {"ok": True}]}

    def test_pick_wrong_and_right(self):
        self.assertEqual({"result": "pass", "right": [2]}, grade.grade_choice(self.ITEM, [2]))
        self.assertEqual("stuck", grade.grade_choice(self.ITEM, [0])["result"])
        right = dict(self.ITEM, pick="right")
        self.assertEqual([0, 1, 3], grade.right_options(right))

    def test_multi_needs_same_set(self):
        item = {"pick": "right", "multi": True, "options": [{"ok": True}, {"ok": True}, {"ok": False}, {"ok": False}]}
        self.assertEqual("pass", grade.grade_choice(item, [1, 0])["result"])
        self.assertEqual("stuck", grade.grade_choice(item, [0])["result"])
        self.assertEqual("stuck", grade.grade_choice(item, [0, 1, 2])["result"])
        self.assertEqual("stuck", grade.grade_choice(item, [])["result"])


if __name__ == "__main__":
    unittest.main()
