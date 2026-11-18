# -*- coding: utf-8 -*-
"""모의고사 코드 작성 문항 채점을 실제 하네스로 확인함. 비교 규칙, 숨은 테스트 내용이 결과 글에 나가지 않는지,
[코드 실행]의 임시 폴더, 실행 환경 실패 판정을 봄.

실행: python -m unittest tests.test_ai_mock_code
시간 값은 단언하지 않고 판정만 봄.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import mock_code  # noqa: E402
from journey import runner  # noqa: E402

MARK = "mark-3141"


def item(entry, params, fills, examples, tests, solution, limit_ms=2000, tol=None):
    starter = "def %s(%s):\n" % (entry, params) + "    ____\n" * fills
    return {"kind": "code", "format": "code",
            "code": {"starter": starter, "entry": entry, "examples": examples, "tests": tests,
                     "limit_ms": limit_ms, "tol": tol},
            "solution": solution}


def add_item(fills=1, limit_ms=2000, solution=None):
    tests = [{"args": [987650 + k, 456700 + k], "expected": 1444350 + 2 * k} for k in range(1, 7)]
    return item("add", "a, b", fills, [{"args": [1, 2], "expected": 3}, {"args": [10, 20], "expected": 30}],
                tests, solution or ["return a + b"] + ["pass"] * (fills - 1), limit_ms)


def mean_item(tests=None):
    tests = tests or [{"args": [[1, 2, 3, 4]], "expected": 2.5}, {"args": [[7, 8]], "expected": 7.5},
                      {"args": [[1, 2]], "expected": 1.5}, {"args": [[0.1, 0.2]], "expected": 0.15}]
    return item("mean", "xs", 1, [{"args": [[2, 4]], "expected": 3.0}, {"args": [[5]], "expected": 5.0}],
                tests, ["return sum(xs) / len(xs)"])


def hidden_texts(code_item):
    texts = []
    for test in code_item["code"]["tests"]:
        texts += [json.dumps(arg, ensure_ascii=False) for arg in test["args"]]
        texts.append(json.dumps(test["expected"], ensure_ascii=False))
    return texts


class SourceTest(unittest.TestCase):
    def test_lines_take_the_indent_of_each_slot_and_entry_becomes_solution(self):
        starter = "def f(a):\n    ____\n    if a:\n        ____\n    return a\n"
        text = mock_code.source(starter, "f", ["a += 1", "a *= 2"])
        self.assertEqual(text, "def f(a):\n    a += 1\n    if a:\n        a *= 2\n    return a\n\n\nsolution = f\n")
        self.assertEqual(mock_code.fill_count(starter), 2)
        with self.assertRaises(ValueError):
            mock_code.source(starter, "f", ["a += 1"])


class CompareTest(unittest.TestCase):
    def test_reason_follows_type_then_length_then_first_position(self):
        diff = mock_code._difference
        self.assertIsNone(diff([1, [2.0, "a"]], [1, [2.0000001, "a"]], 1e-6))
        self.assertEqual(diff(3.0, 3, 1e-6), "돌려준 값의 자료형이 다릅니다.")
        self.assertIsNone(diff(3, 3.0, 1e-6))
        self.assertEqual(diff(True, 1.0, 1e-6), "돌려준 값의 자료형이 다릅니다.")
        self.assertEqual(diff(1, True, 1e-6), "돌려준 값의 자료형이 다릅니다.")
        self.assertEqual(diff([1, 2], [1, 2, 3], 1e-6), "돌려준 값의 길이가 다릅니다.")
        self.assertEqual(diff([1, [2, 4]], [1, [2, 3]], 1e-6), "돌려준 값에서 2번째 원소 안의 2번째 원소의 값이 다릅니다.")
        self.assertEqual(diff(5, 4, 1e-6), "돌려준 값이 다릅니다.")
        self.assertEqual(diff(1.1, 1.0, 1e-6), "돌려준 값이 다릅니다.")
        self.assertIsNone(diff(1.1, 1.0, 0.2))


class GradeTest(unittest.TestCase):
    def assertResult(self, result, expected):
        self.assertEqual(result["result"], expected, result)

    def test_pass_and_runtime_timeout_bad_return_fatal_are_stuck(self):
        passed = mock_code.grade(add_item(), ["return a + b"])
        self.assertResult(passed, "pass")
        self.assertEqual((passed["passed"], passed["total"], passed["reason"]), (6, 6, ""))
        answers = {"runtime": ["raise ValueError('x')"], "timeout": ["while True: pass"],
                   "bad_return": ["return (a, b)"], "fatal": ["return (a +"]}
        for status, lines in answers.items():
            with self.subTest(status=status):
                result = mock_code.grade(add_item(limit_ms=300), lines)
                self.assertResult(result, "stuck")
                self.assertEqual(result["passed"], 0)
                self.assertEqual({case["status"] for case in result["cases"]}, {status})
                self.assertEqual(result["reason"], "숨은 테스트 1번: " + mock_code.REASONS[status])

    def test_values_alone_wrong_are_stuck_in_exact_and_float_comparison(self):
        exact = mock_code.grade(add_item(), ["return a - b"])
        self.assertResult(exact, "stuck")
        self.assertEqual(exact["cases"][0], {"status": "wrong", "reason": "돌려준 값이 다릅니다."})
        close = mock_code.grade(mean_item(), ["return sum(xs) / len(xs) + 0.5"])
        self.assertResult(close, "stuck")
        self.assertEqual(close["passed"], 0)
        self.assertResult(mock_code.grade(mean_item(), ["return sum(xs) / len(xs)"]), "pass")

    def test_int_float_and_bool_rules(self):
        as_float = mock_code.grade(add_item(), ["return float(a + b)"])
        self.assertResult(as_float, "stuck")
        self.assertEqual(as_float["cases"][0]["reason"], "돌려준 값의 자료형이 다릅니다.")
        whole = mean_item([{"args": [[2, 4]], "expected": 3.0}, {"args": [[9, 9, 9]], "expected": 9.0}])
        self.assertResult(mock_code.grade(whole, ["return sum(xs) // len(xs)"]), "pass")
        self.assertResult(mock_code.grade(whole, ["return True"]), "stuck")
        huge = mock_code.grade(whole, ["return 10 ** 400"])
        self.assertResult(huge, "stuck")
        self.assertEqual(huge["cases"][0], {"status": "wrong", "reason": "돌려준 값이 다릅니다."})
        code = whole["code"]
        tried = mock_code.try_code(code["starter"], code["entry"], code["examples"], ["return 10 ** 400"])
        self.assertResult(tried, "stuck")
        even = item("even", "n", 1, [{"args": [2], "expected": True}],
                    [{"args": [4], "expected": True}, {"args": [7], "expected": False}], ["return n % 2 == 0"])
        self.assertResult(mock_code.grade(even, ["return n % 2 == 0"]), "pass")
        self.assertResult(mock_code.grade(even, ["return 1 - n % 2"]), "stuck")

    def test_hidden_inputs_and_expected_values_stay_out_of_the_result(self):
        code_item = add_item(fills=2)
        answers = (["print(a, b, flush=True)", "raise ValueError(repr((a, b)))"],
                   ["print('입력', a, b)", "return [a, b]"],
                   ["print(a, b)", "return a + b + 1"],
                   ["import sys", "sys.exit(str(a))"])
        for lines in answers:
            with self.subTest(lines=lines):
                result = mock_code.grade(code_item, lines)
                self.assertResult(result, "stuck")
                text = json.dumps(result, ensure_ascii=False)
                for hidden in hidden_texts(code_item):
                    self.assertNotIn(hidden, text)
                for case in result["cases"]:
                    self.assertEqual(set(case), {"status", "reason"})

    def test_every_hidden_test_runs_and_the_count_does_not_depend_on_workers(self):
        code_item = add_item()
        lines = ["return a + b if a % 2 else 0"]
        one = mock_code.grade(code_item, lines, workers=1)
        four = mock_code.grade(code_item, lines, workers=4)
        self.assertEqual(one, four)
        self.assertEqual((one["passed"], one["total"]), (3, 6))
        self.assertEqual([case["status"] for case in one["cases"]], ["pass", "wrong"] * 3)
        self.assertEqual(one["reason"], "숨은 테스트 2번: 돌려준 값이 다릅니다.")

    def test_numpy_is_not_importable_and_ends_as_runtime(self):
        with mock.patch.object(mock_code, "_solution_runs", wraps=mock_code._solution_runs) as check:
            result = mock_code.grade(add_item(fills=2), ["import numpy", "return a + b"])
        self.assertResult(result, "stuck")
        self.assertEqual({case["status"] for case in result["cases"]}, {"runtime"})
        check.assert_not_called()


class TryCodeTest(unittest.TestCase):
    def test_folder_and_job_hold_only_examples(self):
        code_item = add_item(fills=4)
        code = code_item["code"]
        lines = ["import os",
                 "top = os.path.dirname(os.getcwd())",
                 "seen = [open(os.path.join(r, f), encoding='utf-8', errors='replace').read()"
                 " for r, _, fs in os.walk(top) for f in fs if f != 'harness.py']",
                 "return ' '.join(seen)"]
        result = mock_code.try_code(code["starter"], code["entry"], code["examples"], lines)
        files = " ".join(case["actual"] for case in result["cases"])
        self.assertIn('"args"', files)
        self.assertIn("[[10,20]]", files)
        for hidden in hidden_texts(code_item):
            self.assertNotIn(hidden, files)

    def test_answer_failing_only_hidden_tests_passes_every_example(self):
        code_item = add_item()
        code = code_item["code"]
        lines = ["return {(1, 2): 3, (10, 20): 30}[(a, b)]"]
        tried = mock_code.try_code(code["starter"], code["entry"], code["examples"], lines)
        self.assertEqual((tried["result"], tried["passed"], tried["total"]), ("pass", 2, 2), tried)
        self.assertEqual(tried["cases"][1]["actual"], 30)
        graded = mock_code.grade(code_item, lines)
        self.assertEqual((graded["result"], graded["passed"]), ("stuck", 0))

    def test_examples_show_output_and_error(self):
        code = add_item(fills=2)["code"]
        result = mock_code.try_code(code["starter"], code["entry"], code["examples"],
                                    ["print('합', a + b)", "raise ValueError('끝')"])
        first = result["cases"][0]
        self.assertEqual((first["status"], first["args"], first["expected"]), ("runtime", [1, 2], 3))
        self.assertIn("합 3", first["printed"])
        self.assertIn("ValueError: 끝", first["error"])
        self.assertEqual(result["reason"], "예시 1번: " + mock_code.REASONS["runtime"])

    def test_child_sees_no_repository_path(self):
        code = item("where", "a", 2, [{"args": [1], "expected": []}], [], [])["code"]
        lines = ["import os, sys", "return [sys.argv[0], os.getcwd()] + sys.path"]
        result = mock_code.try_code(code["starter"], code["entry"], code["examples"], lines)
        seen = result["cases"][0]["actual"]
        self.assertGreaterEqual(len(seen), 2)
        for path in seen:
            self.assertNotIn(study.ROOT, path)


class EnvironmentTest(unittest.TestCase):
    def test_popen_os_error_is_an_environment_failure(self):
        with mock.patch.object(runner.subprocess, "Popen", side_effect=OSError("막힘")):
            result = mock_code.grade(add_item(), ["return a + b"])
            tried = mock_code.try_code(add_item()["code"]["starter"], "add", [{"args": [1, 2], "expected": 3}],
                                       ["return a + b"])
        self.assertEqual((result["result"], result["passed"], result["cases"]), ("env", 0, []))
        self.assertEqual(result["reason"], mock_code.ENV_REASON)
        self.assertEqual(tried["result"], "env")

    def test_learner_crash_with_working_solution_is_stuck(self):
        result = mock_code.grade(add_item(fills=2), ["import os", "os._exit(3)"])
        self.assertEqual(result["result"], "stuck", result)
        self.assertEqual({case["status"] for case in result["cases"]}, {"runtime"})

    def test_crash_in_both_learner_and_solution_is_an_environment_failure(self):
        code_item = add_item(fills=2, solution=["import os", "os._exit(3)"])
        self.assertEqual(mock_code.grade(code_item, ["import os", "os._exit(3)"])["result"], "env")

    def test_learner_cannot_find_the_solution_folder_while_graded(self):
        code_item = add_item(fills=3, solution=["return a + b  # " + MARK, "pass", "pass"])
        lines = ["import os",
                 "home = os.path.dirname(os.getcwd()); root = os.path.dirname(home)",
                 "return a + b if any(os.path.join(root, d) != home and '%s' in open(os.path.join(root, d,"
                 " 'solution.py'), errors='replace').read() for d in os.listdir(root) if d.startswith('journey_')"
                 " and os.path.isfile(os.path.join(root, d, 'solution.py'))) else os._exit(3)" % MARK]
        result = mock_code.grade(code_item, lines)
        self.assertEqual((result["result"], result["passed"]), ("stuck", 0), result)
        root = tempfile.gettempdir()
        left = [name for name in os.listdir(root) if name.startswith("journey_")
                and os.path.isfile(os.path.join(root, name, "solution.py"))
                and MARK in study.read_text(os.path.join(root, name, "solution.py"))]
        self.assertEqual(left, [])


if __name__ == "__main__":
    unittest.main()
