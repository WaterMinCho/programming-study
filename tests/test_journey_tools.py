# -*- coding: utf-8 -*-
"""여정 도구 테스트. tools/journey_seal.py(봉인·해제·검사·공개본)와 tools/verify_journey.py(은행 검증, --fill, --timing,
--styles, --changed, --plan, --lang, 검토 서명), 여정 워크플로 파일을 봄.

고정 은행 tests/journey_bank 를 임시 폴더에 복사해 일부러 망가뜨린 사본마다 검증이 실패하는지 확인함. 빨리 돌게 대부분은
그 실패를 잡는 단계만 돌림(verify_journey.main 의 steps). 시간 값(ms)은 단언하지 않고 판정만 봄.
실행: python -m unittest tests.test_journey_tools
STUDY_LEAN_CI 가 있으면 setUpModule 에서 모듈 전체를 건너뛰고(ci.yml 의 bank 작업), Node 가 없으면 JS 테스트를 건너뜀.
"""
import os

os.environ.setdefault("STUDY_NODE_PROBE", "0")

import contextlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from journey import bank, node, runner, values  # noqa: E402
from tools import check_style, journey_seal, verify_journey  # noqa: E402

LEAN = bool(os.environ.get("STUDY_LEAN_CI"))
NODE = None if LEAN else node.find()
HAS_GIT = shutil.which("git") is not None
FIXTURE = os.path.join(ROOT, "tests", "journey_bank")
NEEDS_NODE = unittest.skipUnless(NODE, "Node.js 20 이상이 있어야 함")
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")
_cache = {}


def setUpModule():
    if LEAN:
        raise unittest.SkipTest("자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
    _cache["old"] = runner.CACHE_DIR
    _cache["dir"] = tempfile.mkdtemp(prefix="journey_tools_cache_")
    runner.CACHE_DIR = os.path.realpath(_cache["dir"])


def tearDownModule():
    runner.CACHE_DIR = _cache["old"]
    shutil.rmtree(_cache["dir"], ignore_errors=True)


def read(path):
    return study.read_text(path)


def quiet(fn, *args):
    """표준 출력을 모아 (돌려준 값, 글). SystemExit 은 코드로 바꿈."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            result = fn(*args)
        except SystemExit as error:
            result = error.code
    return result, out.getvalue()


class BankCase(unittest.TestCase):
    """고정 은행을 임시 폴더에 복사해 고치는 테스트의 바탕."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journey_tools_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bank = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, self.bank)

    def path(self, rel):
        return os.path.join(self.bank, "t01", *rel.split("/"))

    def read(self, rel):
        return study.read_text(self.path(rel))

    def write(self, rel, text):
        study.write_text(self.path(rel), text)

    def read_json(self, rel):
        return study.read_json(self.path(rel))

    def write_json(self, rel, data):
        self.write(rel, json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    def replace(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new, 1))

    def edit_tests(self, rel, fn):
        data = self.read_json(rel)
        fn(data)
        self.write_json(rel, data)

    def verify(self, *args, **kwargs):
        out = io.StringIO()
        code = verify_journey.main(list(args) + ["--bank", self.bank], steps=kwargs.get("steps"), out=out)
        return code, out.getvalue()

    def assertFails(self, target, steps, *needles):
        code, out = self.verify(target, "--lang", "python", steps=steps)
        self.assertEqual(1, code, out)
        for needle in needles:
            self.assertIn(needle, out)
        return out


class SealTest(BankCase):
    def seal(self, *args):
        return quiet(journey_seal.main, list(args) + ["--bank", self.bank])

    def test_seal_then_unseal_gives_back_the_same_files(self):
        ddir = os.path.join(self.bank, "t01")
        before = bank.load_secrets(ddir)
        self.assertIn("p1/wrong/first_only.py", before)
        code, out = self.seal("seal", "t01")
        self.assertEqual(0, code)
        self.assertIn("봉인: t01", out)
        self.assertEqual([], bank.plain_secret_paths(ddir))
        self.assertFalse(os.path.exists(os.path.join(ddir, "p1", "wrong")))
        self.assertTrue(os.path.isfile(os.path.join(ddir, "p1", "problem.json")))
        self.assertEqual(before, study.unseal_blob(study.read_json(os.path.join(ddir, "sealed.json"))["blob"]))
        self.assertEqual(0, self.seal("check")[0])
        self.assertEqual(0, self.seal("unseal", "t01")[0])
        for rel, text in before.items():
            self.assertEqual(text, read(os.path.join(ddir, *rel.split("/"))), rel)

    def test_check_catches_plain_files_and_broken_sealed(self):
        code, out = self.seal("check")
        self.assertEqual(1, code)
        self.assertIn("t01/p1/solution.py", out)
        self.assertIn("t01/boss/wrong/first_k.js", out)
        self.seal("seal", "t01")
        self.assertEqual(0, self.seal("check")[0])
        study.write_text(os.path.join(self.bank, "t01", "sealed.json"), '{"note": "봉인", "blob": "not-a-blob"}')
        code, out = self.seal("check")
        self.assertEqual(1, code)
        self.assertIn("풀리지 않는 sealed.json", out)

    def test_seal_keeps_plain_with_keep_and_drops_removed_problems(self):
        ddir = os.path.join(self.bank, "t01")
        self.seal("seal", "t01", "--keep")
        self.assertIn("p1/solution.py", bank.plain_secret_paths(ddir))
        shutil.rmtree(os.path.join(ddir, "p3"))
        self.seal("seal", "t01")
        files = study.unseal_blob(study.read_json(os.path.join(ddir, "sealed.json"))["blob"])
        self.assertFalse([rel for rel in files if rel.startswith("p3/")])
        self.assertIn("boss/solution.py", files)

    def test_seal_removes_sealed_json_when_no_problem_is_left(self):
        ddir = os.path.join(self.bank, "t01")
        self.seal("seal", "t01")
        for pid in bank.problem_ids(ddir):
            shutil.rmtree(os.path.join(ddir, pid))
        code, out = self.seal("seal", "t01")
        self.assertEqual(0, code)
        self.assertIn("sealed.json 을 지웠습니다", out)
        self.assertFalse(os.path.exists(os.path.join(ddir, "sealed.json")))
        self.assertEqual(0, self.seal("check")[0])

    def test_unreadable_sealed_json_stops_seal_and_unseal_with_a_message(self):
        ddir = os.path.join(self.bank, "t01")
        study.write_text(os.path.join(ddir, "sealed.json"), '{"note": "봉인", "blob": "not-a-blob"}')
        for command in ("seal", "unseal"):
            with self.subTest(command=command):
                code, _ = self.seal(command, "t01")
                self.assertIn("t01: sealed.json 을 풀 수 없습니다", str(code))
        self.assertIn("p1/solution.py", bank.plain_secret_paths(ddir))

    def test_brief_holds_only_public_parts_and_refuses_folders_in_the_repo(self):
        out_dir = os.path.join(self.tmp, "brief")
        code, out = self.seal("brief", "t01/p3", "--out", out_dir)
        self.assertEqual(0, code, out)
        self.assertEqual(["alt.js", "alt.py", "problem.json", "problem.md"], sorted(os.listdir(out_dir)))
        public = study.read_json(os.path.join(out_dir, "problem.json"))
        self.assertEqual(list(journey_seal.BRIEF_KEYS), list(public))
        self.assertEqual(read(self.path("p3/problem.md")), read(os.path.join(out_dir, "problem.md")))
        self.assertEqual(values.starter(public["signature"], "python"), read(os.path.join(out_dir, "alt.py")))
        self.assertEqual(values.starter(public["signature"], "javascript"), read(os.path.join(out_dir, "alt.js")))
        text = "".join(read(os.path.join(out_dir, name)) for name in os.listdir(out_dir))
        for secret in ("brute_ok", "LOWER = re.compile", "reversed(name)", "name[::-1]"):
            self.assertNotIn(secret, text)
        inside = os.path.join(ROOT, "tmp_journey_brief")
        code, out = self.seal("brief", "t01/p3", "--out", inside)
        self.assertNotEqual(0, code)
        self.assertFalse(os.path.exists(inside))
        code, _ = self.seal("brief", "t01/p3", "--out", os.path.join(self.bank, "t01", "brief"))
        self.assertNotEqual(0, code)


class VerifyFixtureTest(BankCase):
    def test_fixture_dungeon_passes(self):
        args = ["t01"] if NODE else ["t01", "--lang", "python"]
        code, out = self.verify(*args)
        self.assertEqual(0, code, out)
        self.assertIn("OK: 문제 4개를 검증했습니다", out)
        self.assertIn("정확성 15줄(이름 붙인 테스트 9개, 50건 묶음 6줄)", out)

    def test_sealed_dungeon_passes_too(self):
        quiet(journey_seal.main, ["seal", "t01", "--bank", self.bank])
        code, out = self.verify("t01/boss", "--lang", "python", steps={1, 2, 3, 4, 5, 7, 8, 12, 14})
        self.assertEqual(0, code, out)


class BrokenCopyTest(BankCase):
    def test_wrong_reference_solution(self):
        self.write("p1/solution.py", "def solution(nums):\n    return sum(nums) + 1\n")
        self.assertFails("t01/p1", {7}, "solution.py 가 통과하지 못한 테스트", "ex1")

    def test_wrong_answer_that_passes(self):
        self.write("p1/wrong/first_only.py", "def solution(nums):\n    return sum(nums)\n")
        self.assertFails("t01/p1", {12}, "first_only 은 wrong 이어야 하는데")

    def test_example_table_differs_from_examples(self):
        self.replace("p1/problem.md", "| [5, -2] | 3 |", "| [5, -2] | 4 |")
        self.assertFails("t01/p1", {3}, "입출력 예 표 2행")

    def test_function_block_parameter_names_differ(self):
        self.replace("p1/problem.md", "def solution(nums: list[int])", "def solution(values: list[int])")
        self.assertFails("t01/p1", {3}, "Python 매개변수 values")
        self.replace("p1/problem.md", "function solution(nums)", "function solution(arr)")
        self.assertFails("t01/p1", {3}, "JavaScript 매개변수 arr")

    def test_missing_image(self):
        os.remove(self.path("assets/1-1a.gif"))
        self.assertFails("t01/p1", {14}, "가리키는 그림이 없습니다: assets/1-1a.gif")

    def test_integer_over_2_53(self):
        def edit(data):
            data["accuracy"][0]["args"] = [[2 ** 53]]
            data["accuracy"][0]["expected"] = 2 ** 53
        self.edit_tests("p1/tests.json", edit)
        self.assertFails("t01/p1", {4}, "one_item 의 1번째 인자", "2^53-1")

    def test_example_breaks_constraints(self):
        data = self.read_json("p1/problem.json")
        data["examples"][0] = {"args": [[1, 2, 3000]], "expected": 3003}
        self.write_json("p1/problem.json", data)
        self.assertFails("t01/p1", {5}, "입출력 예 1 가 제한사항을 어깁니다: 2번 줄")

    def test_validate_that_always_passes(self):
        self.write("p1/validate.py", "def validate(nums):\n    return None\n")
        self.assertFails("t01/p1", {5}, "invalid 1번째(1번 줄)", "invalid 2번째(2번 줄)")

    def test_constraint_line_without_invalid(self):
        self.edit_tests("p1/tests.json", lambda data: data.update(invalid=[{"line": 1, "args": [[]]}]))
        self.assertFails("t01/p1", {5}, "제한사항 2번 줄에 invalid 도 DESCRIPTIVE 도 없습니다")
        self.edit_tests("p1/tests.json", lambda data: data.update(invalid=[{"args": [[]]}, {"line": 2, "args": [[1001]]}]))
        self.assertFails("t01/p1", {5}, "invalid 1번째에 line(제한사항 번호)과 args 가 있어야 합니다")

    def test_descriptive_line_counts_as_covered(self):
        self.edit_tests("p1/tests.json", lambda data: data.update(invalid=[{"line": 1, "args": [[]]}]))
        self.write("p1/validate.py", self.read("p1/validate.py").replace(
            "def validate", 'DESCRIPTIVE = {2: "원소 범위는 생성기가 지킴"}\n\n\ndef validate', 1))
        code, out = self.verify("t01/p1", "--lang", "python", steps={5})
        self.assertEqual(0, code, out)

    def test_gen_uses_set(self):
        self.replace("p1/gen.py", "return [[rng.between(-5, 5) for _ in range(rng.between(1, 8))]]",
                     "return [sorted(set([rng.between(-5, 5) for _ in range(rng.between(1, 8))]))]")
        self.assertFails("t01/p1", {6}, "set() 호출")

    def test_gen_imports_other_modules(self):
        original = self.read("p1/gen.py")
        cases = [("import random\n", "import random"), ("import time\n", "import time"),
                 ("X = __import__('os').getpid()\n", "__import__() 호출"), ("from os import getpid\n", "from os import")]
        for line, needle in cases:
            with self.subTest(line=line):
                self.write("p1/gen.py", original.replace('"""\n', '"""\n' + line, 1))
                self.assertFails("t01/p1", {6}, needle)

    def test_gen_differs_between_processes(self):
        self.replace("p1/gen.py", "return [[rng.between(-5, 5) for _ in range(rng.between(1, 8))]]",
                     "seed = id(rng) ^ id([]) ^ id(object())\n    return [[(seed >> shift) % 11 - 5 for shift in range(4, 36, 4)]]")
        self.assertFails("t01/p1", {6}, "생성기가 프로세스마다 다른 입력을 냅니다: rand1")

    def test_solution_differs_from_brute_on_small_stress_inputs(self):
        self.write("p1/solution.py", "def solution(nums):\n    return sum(nums) + (1 if len(nums) == 200 else 0)\n")
        out = self.assertFails("t01/p1", {9}, "의 stress 입력 20개에서 답이 갈립니다", "brute.py", "solution.py", "alt.py")
        self.assertNotIn("solution.js", out)

    def test_brute_ok_false_needs_certify(self):
        self.replace("p1/brute.py", "return len(nums) <= 5000", "return len(nums) <= 2")
        self.assertFails("t01/p1", {8}, "certify.py 가 없습니다")

    def test_certify_reports_a_violation(self):
        self.replace("p1/brute.py", "return len(nums) <= 5000", "return len(nums) <= 2")
        self.write("p1/certify.py", "def certify(args, value):\n    return None if value == sum(args[0]) else '합이 다릅니다'\n")
        code, out = self.verify("t01/p1", "--lang", "python", steps={8})
        self.assertEqual(0, code, out)
        self.write("p1/certify.py", "def certify(args, value):\n    return '원소가 너무 많습니다' if len(args[0]) > 4 else None\n")
        self.assertFails("t01/p1", {8}, "의 정의 대조 실패: 원소가 너무 많습니다")

    def test_only_eight_named_accuracy_tests(self):
        def edit(data):
            data["accuracy"] = [t for t in data["accuracy"] if t["id"] != "zeros"]
            data["accuracy"].append({"id": "pair", "name": "작은 무작위 두 개", "gen": "small", "seed": 99, "count": 2, "expected": [0, 0]})
        self.edit_tests("p1/tests.json", edit)
        out = self.assertFails("t01/p1", {4}, "이름 붙인 정확성 테스트(count 없음)가 8개입니다")
        self.assertIn("정확성 15줄", out)
        self.assertNotIn("정확성 테스트가 15줄입니다", out)

    def test_only_five_bundles(self):
        self.edit_tests("p1/tests.json", lambda data: data.update(accuracy=[t for t in data["accuracy"] if t["id"] != "rand6"]))
        self.assertFails("t01/p1", {4}, "50건 묶음(count: 50)이 5줄입니다")

    def test_limit_depth_needs_a_heavy_js_entry(self):
        def edit(data):
            data["accuracy"][0]["depth"] = "limit"
        self.edit_tests("p1/tests.json", edit)
        self.assertFails("t01/p1", {4}, "JavaScript heavy 항목이 없습니다")

    def test_boss_needs_boss_new(self):
        data = self.read_json("boss/extra.json")
        del data["boss_new"]
        self.write_json("boss/extra.json", data)
        self.assertFails("t01/boss", {2}, "보스의 extra.json 에 boss_new 가 없습니다")

    def add_known(self, name, entry, source):
        wrong = self.read_json("p1/wrong.json")
        wrong[name] = dict(entry, langs=["python"], why="시험용")
        self.write_json("p1/wrong.json", wrong)
        self.write("p1/wrong/%s.py" % name, source)

    def test_known_runtime_that_never_loads_fails(self):
        self.add_known("broken", {"expect": "runtime", "on": ["ex1", "mixed"]}, "def solution(nums)\n    return nums[100]\n")
        self.assertFails("t01/p1", {12}, "broken 은 runtime 이어야 하는데", "ex1(실행 전 오류", "mixed(실행 전 오류")

    def test_known_runtime_counts_a_later_load_failure_as_runtime(self):
        loads = os.path.join(self.tmp, "loads")
        source = ("import os\n\nLOADS = int(open(%r).read()) if os.path.exists(%r) else 0\n"
                  "with open(%r, 'w') as f:\n    f.write(str(LOADS + 1))\n"
                  "if LOADS:\n    raise RuntimeError('두 번째 불러오기')\n\n\n"
                  "def solution(nums):\n    return nums[100]\n") % (loads, loads, loads)
        self.add_known("later_load", {"expect": "runtime", "on": ["ex1", "mixed"]}, source)
        code, out = self.verify("t01/p1", "--lang", "python", steps={12})
        self.assertEqual(0, code, out)
        self.assertEqual("2", read(loads))

    def test_alt_files_are_needed_only_for_signing(self):
        os.remove(self.path("p1/alt.py"))
        code, out = self.verify("t01/p1", "--lang", "python", steps={2})
        self.assertEqual(0, code, out)
        code, out = self.verify("t01/p1", "--lang", "python", "--require-review", steps={2})
        self.assertEqual(1, code, out)
        self.assertIn("alt.py 가 없습니다", out)
        code, out = self.verify("t01/p1", "--lang", "python", "--sign", "--writer", "출제 1", "--resolver", "재풀이 2",
                                "--reviewer", "검토 2", steps={2})
        self.assertEqual(1, code, out)
        self.assertIn("alt.py 가 없습니다", out)
        self.assertFalse(os.path.exists(self.path("p1/review.json")))

    def test_alt_differs_from_the_reference(self):
        self.write("p1/alt.py", "def solution(nums):\n    return sum(nums) - 1\n")
        self.assertFails("t01/p1", {10}, "alt.py 의 답이 기대값과 다른 테스트")

    def test_alt_dir_is_checked_before_it_moves_in(self):
        alt_dir = os.path.join(self.tmp, "alt")
        study.write_text(os.path.join(alt_dir, "alt.py"), "def solution(nums):\n    return sum(nums)\n")
        code, out = self.verify("t01/p1", "--lang", "python", "--alt", alt_dir)
        self.assertEqual(0, code, out)
        study.write_text(os.path.join(alt_dir, "alt.py"), "def solution(nums):\n    return sum(nums) if len(nums) != 200 else 0\n")
        code, out = self.verify("t01/p1", "--lang", "python", "--alt", alt_dir)
        self.assertEqual(1, code, out)
        self.assertIn("답이 갈립니다", out)

    def test_broken_problem_json_does_not_stop_the_run(self):
        data = self.read_json("p1/problem.json")
        del data["time_limit_ms"]
        self.write_json("p1/problem.json", data)
        code, out = self.verify("t01/p1", "t01/p3", "--lang", "python", steps={1, 7})
        self.assertEqual(1, code, out)
        self.assertIn("time_limit_ms.python 가 양의 정수가 아닙니다", out)
        self.assertIn("이 단계를 끝까지 돌리지 못했습니다", out)
        self.assertIn("[t01/p3]", out)
        self.assertNotIn("[t01/p3]\n  실패", out)

    def test_starter_must_fail_an_example(self):
        data = self.read_json("p3/problem.json")
        data["examples"] = [{"args": ["a"], "expected": ""}, {"args": ["b"], "expected": ""}]
        self.write_json("p3/problem.json", data)
        self.assertFails("t01/p3", {11}, "시작 코드")


@NEEDS_NODE
class LangJavascriptTest(BankCase):
    def test_javascript_mode_skips_python_steps_and_still_catches_js_failures(self):
        self.write("p1/solution.js", "function solution(nums) {\n    return nums.length;\n}\n")
        trap = mock.Mock(side_effect=AssertionError("JavaScript 단계에서 돌면 안 됨"))
        with mock.patch.object(verify_journey, "step_brute", trap), \
                mock.patch.object(verify_journey, "step_determinism", trap), \
                mock.patch.object(verify_journey, "step_validate", trap), \
                mock.patch.object(verify_journey, "step_starter", trap):
            code, out = self.verify("t01/p1", "--lang", "javascript")
        self.assertEqual(1, code, out)
        self.assertIn("solution.js 가 통과하지 못한 테스트", out)
        self.assertNotIn("solution.py 가 통과하지 못한", out)
        trap.assert_not_called()

    def test_javascript_known_solution_is_judged(self):
        self.write("p1/wrong/first_only.js", "function solution(nums) {\n    return nums.reduce((a, b) => a + b, 0);\n}\n")
        code, out = self.verify("t01/p1", "--lang", "javascript", steps={12})
        self.assertEqual(1, code, out)
        self.assertIn("JavaScript first_only 은 wrong 이어야 하는데", out)


SLOW_SOURCE = """import time


def solution(nums):
    if nums[0] == nums[-1] == 1000:
        time.sleep(%(all_max)s)
    elif nums[0] != nums[-1] or nums[0] != -1000:
        time.sleep(%(many)s)
    return sum(nums)
"""


class TimingTest(BankCase):
    """제한을 300ms 로 낮춘 1-1 사본에서 sleep 으로 시간을 정한 풀이로 회색 지대 규칙을 봄(1/15 = 20ms, 10배 = 3초)."""

    def setUp(self):
        super().setUp()
        data = self.read_json("p1/problem.json")
        data["time_limit_ms"]["python"] = 300
        self.write_json("p1/problem.json", data)
        self.wrong = self.read_json("p1/wrong.json")

    def add(self, name, entry, many=0, all_max=0):
        self.wrong[name] = dict(entry, langs=["python"], why="시험용")
        self.write_json("p1/wrong.json", self.wrong)
        self.write("p1/wrong/%s.py" % name, SLOW_SOURCE % {"many": many, "all_max": all_max})

    def timing(self, *extra):
        return self.verify("t01/p1", "--timing", "--lang", "python", "--pythons", sys.executable, *extra)

    def test_pass_entry_slower_than_one_fifteenth_fails_and_report_does_not_judge(self):
        self.add("slow_pass", {"expect": "pass"}, many=0.06, all_max=0.06)
        code, out = self.timing()
        self.assertEqual(1, code, out)
        self.assertIn("통과시킬 풀이 slow_pass", out)
        self.assertIn("1/15", out)
        self.assertRegex(out, r"t01/p1 +Python +.*slow_pass +many +[\d.]+ +300 +[\d.]+ +회색")
        self.assertIn("16.5배 규칙의 값 2000ms", out)
        code, out = self.timing("--report")
        self.assertEqual(0, code, out)
        self.assertIn("slow_pass", out)

    def test_timeout_entry_that_finishes_its_on_test_fails(self):
        self.add("slow_many", {"expect": "timeout", "on": ["many"]}, many=0.6)
        code, out = self.timing()
        self.assertEqual(1, code, out)
        self.assertIn("죽일 풀이 slow_many 가 on 의 테스트 many", out)

    def test_gray_zone_outside_on_must_be_listed(self):
        self.add("slow_many", {"expect": "timeout", "on": ["many"]}, many=5, all_max=0.6)
        code, out = self.timing()
        self.assertEqual(1, code, out)
        self.assertIn("all_max 에서 제한의", out)
        self.assertIn("gray 에 적거나", out)
        self.add("slow_many", {"expect": "timeout", "on": ["many"], "gray": {"python": ["all_max"]}}, many=5, all_max=0.6)
        code, out = self.timing()
        self.assertEqual(0, code, out)
        self.assertIn("회색(gray)", out)
        self.assertIn("어디서나 실패", out)
        self.assertIn("경고 15 시간", out)


STYLE_CODE = {
    "plain": "def go(nums, i):\n    return 0 if i == len(nums) else nums[i] + go(nums, i + 1)\n\n\n"
             "def solution(nums):\n    return go(nums, 0)\n",
    "iterative": "def solution(nums):\n    total = 0\n    for x in nums:\n        total += x\n    return total\n",
}
STYLE_CODE["raised"] = "import sys\nsys.setrecursionlimit(10 ** 6)\n\n\n" + STYLE_CODE["plain"]


class StylesTest(BankCase):
    def setUp(self):
        super().setUp()

        def edit(data):
            data["accuracy"].append({"id": "deep_limit", "name": "1이 1,200개", "args": [[1] * 1200], "expected": 1200,
                                     "depth": "limit"})
            for test in data["efficiency"]:
                test["depth"] = "chain"
        self.edit_tests("p1/tests.json", edit)

    def styles(self, labels):
        wrong = self.read_json("p1/wrong.json")
        for name, (style, code) in labels.items():
            wrong[name] = {"langs": ["python"], "style": style, "why": "재귀 방식 확인"}
            self.write("p1/wrong/%s.py" % name, STYLE_CODE[code])
        self.write_json("p1/wrong.json", wrong)
        return self.verify("t01/p1", "--styles", "--lang", "python")

    def test_styles_follow_the_recursion_table(self):
        code, out = self.styles({"rec_plain": ("plain", "plain"), "rec_raised": ("raised", "raised"),
                                 "loop": ("iterative", "iterative")})
        self.assertEqual(0, code, out)

    def test_wrong_style_label_fails(self):
        code, out = self.styles({"rec_plain": ("raised", "plain")})
        self.assertEqual(1, code, out)
        self.assertIn("rec_plain(style raised)", out)
        self.assertIn("deep_limit(기대 통과", out)

    def test_unknown_style_fails(self):
        code, out = self.styles({"rec_plain": ("recursive", "plain")})
        self.assertEqual(1, code, out)
        self.assertIn("style 은 plain, raised", out)


GIT_CLEAN = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}


def git_run(repo, *args):
    subprocess.run(["git", "-c", "user.name=tester", "-c", "user.email=tester@example.com", "-c", "commit.gpgsign=false"]
                   + list(args), cwd=repo, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


@unittest.skipUnless(HAS_GIT, "git 이 있어야 함")
class ChangedAndPlanTest(unittest.TestCase):
    """임시 git 저장소: dungeons/ 에 t01 과 그 사본 t03, 실행기 자리 journey/x.py. base 브랜치와 비교함."""

    def setUp(self):
        # 바깥 훅이 넘긴 GIT_DIR 류와 개발자의 전역 git 설정(훅 폴더 등)을 끊음. 검증 도구의 git 호출에도 같이 적용됨
        environ = mock.patch.dict(os.environ, GIT_CLEAN)
        environ.start()
        self.addCleanup(environ.stop)
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            os.environ.pop(key, None)
        self.repo = tempfile.mkdtemp(prefix="journey_git_")
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.bank = os.path.join(self.repo, "dungeons")
        os.makedirs(self.bank)
        shutil.copy(os.path.join(FIXTURE, "index.json"), self.bank)
        for did in ("t01", "t03"):
            shutil.copytree(os.path.join(FIXTURE, "t01"), os.path.join(self.bank, did))
        study.write_text(os.path.join(self.repo, "journey", "x.py"), "X = 1\n")
        git_run(self.repo, "init", "-q")
        self.commit("시작")
        git_run(self.repo, "branch", "base")

    def commit(self, message):
        git_run(self.repo, "add", "-A")
        git_run(self.repo, "commit", "-q", "--no-verify", "-m", message)

    def change(self, rel, text="바뀜\n"):
        study.write_text(os.path.join(self.repo, *rel.split("/")), text)
        self.commit("바꿈")

    def add_style(self, did):
        path = os.path.join(self.bank, did, "p1", "wrong.json")
        data = study.read_json(path)
        data["rec"] = {"langs": ["python"], "style": "plain", "why": "재귀"}
        study.write_text(path, json.dumps(data, ensure_ascii=False))

    def verify(self, *args, **kwargs):
        out = io.StringIO()
        code = verify_journey.main(list(args) + ["--bank", self.bank], steps=kwargs.get("steps", set()), out=out)
        return code, out.getvalue()

    def test_changed_picks_only_the_changed_dungeon(self):
        self.change("dungeons/t03/p1/explain.md")
        self.assertEqual((False, ["t03"], False), verify_journey.changed_scope(self.bank, "base"))
        code, out = self.verify("--changed", "base")
        self.assertEqual(0, code, out)
        self.assertIn("[t03/p1]", out)
        self.assertNotIn("[t01/p1]", out)

    def test_engine_change_picks_every_dungeon(self):
        self.change("journey/x.py", "X = 2\n")
        self.assertTrue(verify_journey.changed_scope(self.bank, "base")[0])
        code, out = self.verify("--changed", "base")
        self.assertEqual(0, code, out)
        self.assertIn("OK: 문제 8개를 검증했습니다", out)

    def test_nothing_changed_checks_nothing(self):
        self.change("README.md")
        code, out = self.verify("--changed", "base")
        self.assertEqual(0, code, out)
        self.assertIn("검증할 던전이 없습니다", out)

    def test_index_change_alone_checks_the_index(self):
        path = os.path.join(self.bank, "index.json")
        data = study.read_json(path)
        data["dungeons"][1]["title"] = "다른 다리"
        self.change("dungeons/index.json", json.dumps(data, ensure_ascii=False))
        self.assertEqual((False, [], True), verify_journey.changed_scope(self.bank, "base"))
        self.assertEqual({"engine": False, "styles": False}, verify_journey.plan(self.bank, "base"))
        code, out = self.verify("--require-review", "--changed", "base", steps={1})
        self.assertEqual(0, code, out)
        self.assertIn("OK: index.json 을 검증했습니다", out)
        data["dungeons"][15]["no"] = 15
        self.change("dungeons/index.json", json.dumps(data, ensure_ascii=False))
        code, out = self.verify("--require-review", "--changed", "base", steps={1})
        self.assertEqual(1, code, out)
        self.assertIn("같은 no 가 두 번 이상 있습니다: 15", out)

    def test_plan_with_empty_ref_runs_everything(self):
        self.assertEqual({"engine": True, "styles": True}, verify_journey.plan(self.bank, ""))
        out = io.StringIO()
        self.assertEqual(0, verify_journey.main(["--plan", "", "--bank", self.bank], out=out))
        self.assertEqual("engine=true\nstyles=true\n", out.getvalue())

    def test_plan_for_a_dungeon_without_style_entries(self):
        self.change("dungeons/t01/p2/explain.md")
        self.assertEqual({"engine": False, "styles": False}, verify_journey.plan(self.bank, "base"))

    def test_plan_for_a_dungeon_with_style_entries(self):
        self.add_style("t03")
        self.commit("재귀 항목")
        git_run(self.repo, "branch", "-f", "base")
        self.change("dungeons/t03/p2/explain.md")
        self.assertEqual({"engine": False, "styles": True}, verify_journey.plan(self.bank, "base"))
        self.change("dungeons/t01/p2/explain.md")
        self.assertEqual({"engine": False, "styles": True}, verify_journey.plan(self.bank, "base"))

    def test_plan_for_engine_changes(self):
        for rel in ("journey/x.py", "tests/test_journey_runner.py", "tests/journey_bank/t01/meta.json",
                    "tools/journey_seal.py", ".github/workflows/journey.yml"):
            with self.subTest(rel=rel):
                git_run(self.repo, "branch", "-f", "base")
                self.change(rel, "# %s\n" % rel)
                self.assertEqual({"engine": True, "styles": True}, verify_journey.plan(self.bank, "base"))


class FillTest(BankCase):
    def test_fill_writes_missing_expected_values(self):
        p1, p3 = self.read_json("p1/tests.json"), self.read_json("p3/tests.json")

        def strip_p1(data):
            del data["accuracy"][0]["expected"]
            del data["accuracy"][9]["expected"]
            del data["efficiency"][0]["expected"]

        self.edit_tests("p1/tests.json", strip_p1)
        self.edit_tests("p3/tests.json", lambda data: data["efficiency"][0].pop("expected_sha"))
        code, out = self.verify("t01/p1", "t01/p3", "--fill")
        self.assertEqual(0, code, out)
        self.assertIn("기대값을 채웠습니다: one_item(expected), rand1(expected), many(expected)", out)
        self.assertIn("long_a(expected_sha)", out)
        self.assertEqual(p1, self.read_json("p1/tests.json"))
        self.assertEqual(p3, self.read_json("p3/tests.json"))
        lines = self.read("p1/tests.json").splitlines()
        self.assertEqual(len(p1["accuracy"]) + len(p1["efficiency"]) + len(p1["invalid"]) + 8, len(lines))
        self.assertTrue(lines[2].startswith('    {"id": "one_item"'))

    def test_fill_reports_a_wrong_literal_and_keeps_it(self):
        def edit(data):
            data["accuracy"][3]["expected"] = 999
        self.edit_tests("p1/tests.json", edit)
        code, out = self.verify("t01/p1", "--fill")
        self.assertEqual(1, code, out)
        self.assertIn("mixed 의 expected 999 가 기준 풀이의 답 2 와 다릅니다", out)
        self.assertEqual(999, self.read_json("p1/tests.json")["accuracy"][3]["expected"])

    def test_fill_needs_plain_tests_json(self):
        quiet(journey_seal.main, ["seal", "t01", "--bank", self.bank])
        code, out = self.verify("t01/p1", "--fill")
        self.assertEqual(1, code, out)
        self.assertIn("평문 tests.json 이 없습니다", out)


class ReviewTest(BankCase):
    NAMES = ["--writer", "출제 1", "--resolver", "재풀이 2", "--reviewer", "검토 2"]

    def sign(self, target, *extra):
        return self.verify(target, "--sign", *(self.NAMES + list(extra)), steps=set())

    def require(self, target):
        return self.verify(target, "--require-review", steps=set())

    def test_sign_then_edit_needs_review_again(self):
        code, out = self.require("t01/p1")
        self.assertEqual(1, code)
        self.assertIn("review.json 이 없습니다", out)
        code, out = self.sign("t01/p1", "--finding", "예 2 의 설명을 고침")
        self.assertEqual(0, code, out)
        review = self.read_json("p1/review.json")
        self.assertEqual(["출제 1", "재풀이 2", "검토 2"], [review["writer"], review["resolver"], review["reviewer"]])
        self.assertEqual(["예 2 의 설명을 고침"], review["findings"])
        for name in ("problem.json", "problem.md", "solution.py", "alt.js", "wrong/first_only.py", "tests.json"):
            self.assertIn(name, review["files"])
        self.assertNotIn("review.json", review["files"])
        self.assertEqual(0, self.require("t01/p1")[0])
        self.write("p1/explain.md", self.read("p1/explain.md") + "\n한 줄을 더합니다.\n")
        code, out = self.require("t01/p1")
        self.assertEqual(1, code)
        self.assertIn("검토 뒤에 바뀐 파일: p1/explain.md", out)

    def test_writer_must_differ_from_reviewer(self):
        code, out = self.verify("t01/p1", "--sign", "--writer", "같은 사람", "--resolver", "재풀이 2", "--reviewer", "같은 사람",
                                steps=set())
        self.assertEqual(1, code)
        self.assertFalse(os.path.exists(self.path("p1/review.json")))
        self.sign("t01/p1")
        review = self.read_json("p1/review.json")
        review["reviewer"] = review["writer"]
        self.write_json("p1/review.json", review)
        code, out = self.require("t01/p1")
        self.assertEqual(1, code)
        self.assertIn("출제자(출제 1)가 재풀이자나 검토자와 같습니다", out)

    def test_dungeon_review_covers_intro_meta_and_images_and_survives_sealing(self):
        for target in ("t01", "t01/p1", "t01/p2", "t01/p3", "t01/boss"):
            self.assertEqual(0, self.sign(target)[0])
        review = study.read_json(os.path.join(self.bank, "t01", "review.json"))
        self.assertEqual(["assets/1-1a.gif", "assets/1-ba.png", "intro.md", "meta.json"], sorted(review["files"]))
        self.assertEqual(0, self.require("t01")[0])
        quiet(journey_seal.main, ["seal", "t01", "--bank", self.bank])
        self.assertFalse(os.path.exists(self.path("p1/review.json")))
        code, out = self.require("t01")
        self.assertEqual(0, code, out)
        with open(self.path("assets/1-1a.gif"), "ab") as f:
            f.write(b"\0")
        code, out = self.require("t01")
        self.assertEqual(1, code)
        self.assertIn("검토 뒤에 바뀐 파일: assets/1-1a.gif", out)


class ImageAndGenTest(unittest.TestCase):
    def test_gif_header_reader_counts_frames(self):
        with open(os.path.join(FIXTURE, "t01", "assets", "1-1a.gif"), "rb") as f:
            info = verify_journey.gif_info(f.read())
        self.assertEqual({"width": 400, "height": 180, "frames": 3, "durations": [1000, 1000, 1000]}, info)
        self.assertEqual([], verify_journey.image_problems(os.path.join(FIXTURE, "t01", "assets", "1-ba.png")))
        with self.assertRaises(ValueError):
            verify_journey.gif_info(b"GIF89a\x01")

    def test_gen_check_passes_journey_gen_and_the_fixture(self):
        self.assertEqual([], verify_journey.gen_violations(read(os.path.join(ROOT, "journey", "gen.py"))))
        for pid in ("p1", "p2", "p3", "boss"):
            self.assertEqual([], verify_journey.gen_violations(read(os.path.join(FIXTURE, "t01", pid, "gen.py"))))

    def test_gen_check_finds_each_rule(self):
        cases = {
            "import random\n": "import random", "from journey.gen import Rng\nimport os.path\n": "import os.path",
            "from random import randint\n": "from random import", "x = {1, 2}\n": "집합 표현",
            "x = {c for c in 'ab'}\n": "집합 표현", "x = frozenset()\n": "frozenset() 호출", "x = hash('a')\n": "hash() 호출",
            "x = eval('1')\n": "eval() 호출", "exec('x = 1')\n": "exec() 호출", "f = open('x')\n": "open() 호출",
            "c = compile('1', 'x', 'eval')\n": "compile() 호출",
        }
        for source, needle in cases.items():
            with self.subTest(source=source):
                self.assertTrue(any(needle in item for item in verify_journey.gen_violations(source)))
        self.assertEqual([], verify_journey.gen_violations("from journey.gen import Rng, word\nimport journey.gen\n"))


def load_yaml(text):
    """워크플로 파일에 쓰는 YAML 의 부분집합을 읽음. 들여쓴 맵, '- ' 목록, [a, b] 꼴 목록, 따옴표 글, | 블록 글, # 주석.
    값은 모두 글로 둠(true, 0 도 글)."""
    lines = text.split("\n")
    pos = [0]

    def indent(line):
        return len(line) - len(line.lstrip(" "))

    def skip():
        while pos[0] < len(lines) and (not lines[pos[0]].strip() or lines[pos[0]].strip().startswith("#")):
            pos[0] += 1

    def scalar(raw):
        raw = raw.strip()
        if raw[:1] in ("'", '"'):
            return raw[1:raw.index(raw[0], 1)]
        if " #" in raw:
            raw = raw.split(" #", 1)[0].rstrip()
        if raw.startswith("[") and raw.endswith("]"):
            return [scalar(item) for item in raw[1:-1].split(",") if item.strip()]
        return raw

    def block(level):
        skip()
        if pos[0] >= len(lines) or indent(lines[pos[0]]) < level:
            return None
        line = lines[pos[0]]
        return sequence(indent(line)) if line.lstrip().startswith("- ") else mapping(indent(line))

    def mapping(level):
        found = {}
        while True:
            skip()
            if pos[0] >= len(lines):
                return found
            line = lines[pos[0]]
            if indent(line) != level or line.lstrip().startswith("- "):
                return found
            key, _, rest = line.strip().partition(":")
            pos[0] += 1
            rest = rest.strip()
            if rest == "|":
                found[scalar(key)] = literal(level)
            elif rest and not rest.startswith("#"):
                found[scalar(key)] = scalar(rest)
            else:
                found[scalar(key)] = block(level + 1)

    def sequence(level):
        found = []
        while True:
            skip()
            if pos[0] >= len(lines):
                return found
            line = lines[pos[0]]
            if indent(line) != level or not line.lstrip().startswith("- "):
                return found
            body = line.strip()[2:]
            if re.match(r"[\w.-]+:(\s|$)", body):
                lines[pos[0]] = " " * (level + 2) + body
                found.append(mapping(level + 2))
            else:
                found.append(scalar(body))
                pos[0] += 1

    def literal(level):
        body = []
        while pos[0] < len(lines) and (not lines[pos[0]].strip() or indent(lines[pos[0]]) > level):
            body.append(lines[pos[0]])
            pos[0] += 1
        while body and not body[-1].strip():
            body.pop()
        cut = min(indent(line) for line in body if line.strip()) if body else 0
        return "\n".join(line[cut:] for line in body) + "\n"

    return block(0)


def runs(job):
    return [step.get("run", "") for step in job["steps"]]


class WorkflowTest(unittest.TestCase):
    """워크플로 파일을 YAML 로 읽어 키와 명령을 봄."""

    def load(self, name):
        text = read(os.path.join(WORKFLOWS, name))
        return text, load_yaml(text)

    def test_yaml_reader_reads_the_subset(self):
        data = load_yaml("a:\n  b: [x, 'y']  # 주석\n  c: |\n    one\n    two\n  d:\n    - e: 1\n      f: \"g\"  # 주석\n    - h\n")
        self.assertEqual({"a": {"b": ["x", "y"], "c": "one\ntwo\n", "d": [{"e": "1", "f": "g"}, "h"]}}, data)

    def test_journey_workflow(self):
        text, data = self.load("journey.yml")
        self.assertEqual("알고리즘 여행 검증", data["name"])
        self.assertEqual(["pull_request", "workflow_dispatch"], list(data["on"]))
        self.assertEqual(["dungeons/**", "journey/**", "study.py", "tools/verify_journey.py", "tools/journey_seal.py",
                          "tools/journey_art/**", "tests/test_journey_*.py", "tests/journey_bank/**",
                          ".github/workflows/journey.yml"], data["on"]["pull_request"]["paths"])
        self.assertEqual({"group": "journey-${{ github.ref }}", "cancel-in-progress": "true"}, data["concurrency"])
        jobs = data["jobs"]
        self.assertEqual(["plan", "runner", "verify", "verify-node22"], list(jobs))
        self.assertEqual(["engine", "styles"], list(jobs["plan"]["outputs"]))
        self.assertTrue(any("verify_journey.py --plan" in run and "$GITHUB_OUTPUT" in run for run in runs(jobs["plan"])))
        runner_job = jobs["runner"]
        self.assertEqual("plan", runner_job["needs"])
        self.assertEqual(["3.10", "3.11", "3.12", "3.13", "3.14"], runner_job["strategy"]["matrix"]["python"])
        self.assertEqual("false", runner_job["strategy"]["fail-fast"])
        self.assertIn("python -m unittest tests.test_journey_values tests.test_journey_runner tests.test_journey_service "
                      "tests.test_journey_tools", runs(runner_job))
        self.assertTrue(any(run.startswith("python tools/verify_journey.py --styles") for run in runs(runner_job)))
        self.assertEqual(["python tools/journey_seal.py check"], [r for r in runs(jobs["verify"]) if "journey_seal" in r])
        self.assertTrue(any("--require-review" in run and '${BASE:+--changed "origin/$BASE"}' in run for run in runs(jobs["verify"])))
        self.assertTrue(any("--lang javascript" in run for run in runs(jobs["verify-node22"])))
        nodes = {name: [s["with"]["node-version"] for s in job["steps"] if s.get("uses", "").startswith("actions/setup-node@")]
                 for name, job in jobs.items()}
        self.assertEqual({"plan": [], "runner": ["24"], "verify": ["24"], "verify-node22": ["22"]}, nodes)
        for name, job in jobs.items():
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/checkout@"):
                    self.assertEqual("0", step["with"]["fetch-depth"], name)
        self.assertNotIn("--timing", text)
        self.assertEqual([], check_style.check(text, path=".github/workflows/journey.yml"))

    def test_ci_workflow_changes_only_the_three_lines(self):
        text, data = self.load("ci.yml")
        jobs = data["jobs"]
        self.assertEqual(["bank", "grade", "gui"], list(jobs))
        self.assertEqual(["문제 은행 검증", "채점", "화면 테스트"], [job["name"] for job in jobs.values()])
        bank_runs = runs(jobs["bank"])
        at = bank_runs.index("python tools/verify_bank.py")
        self.assertEqual(["python tools/journey_seal.py check", "python -m unittest discover -s tests"], bank_runs[at + 1:])
        self.assertEqual({"STUDY_LEAN_CI": "1"}, jobs["bank"]["steps"][-1]["env"])
        self.assertEqual(6, len(jobs["bank"]["steps"]))
        gui = jobs["gui"]["steps"][-1]
        self.assertEqual('python -m unittest discover -s tests -p "test_gui*.py"', gui["run"])
        self.assertEqual({"QT_QPA_PLATFORM": "offscreen"}, gui["env"])
        self.assertEqual("3.13", jobs["gui"]["steps"][1]["with"]["python-version"])
        self.assertEqual([], check_style.check(text, path=".github/workflows/ci.yml"))

    def test_style_workflow_reads_as_yaml(self):
        _, data = self.load("style.yml")
        self.assertEqual("문장 검사", data["name"])
        self.assertEqual(["submissions/**"], data["on"]["pull_request"]["paths-ignore"])
        self.assertEqual(["style"], list(data["jobs"]))


class CommandLineTest(unittest.TestCase):
    def run_tool(self, *args):
        env = dict(os.environ, STUDY_JOURNEY_CACHE=runner.CACHE_DIR)
        return subprocess.run([sys.executable] + list(args), cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env, creationflags=study.NO_WINDOW)

    def test_plan_from_the_command_line(self):
        done = self.run_tool(os.path.join("tools", "verify_journey.py"), "--plan", "")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual("engine=true\nstyles=true\n", done.stdout)

    def test_seal_without_a_command_prints_usage(self):
        done = self.run_tool(os.path.join("tools", "journey_seal.py"))
        self.assertEqual(2, done.returncode)
        self.assertIn("python tools/journey_seal.py brief d01/p3 --out DIR", done.stdout)

    def test_unknown_target_stops(self):
        done = self.run_tool(os.path.join("tools", "verify_journey.py"), "zz9", "--bank", FIXTURE)
        self.assertNotEqual(0, done.returncode)
        self.assertIn("출제된 던전이나 문제가 아닙니다: zz9", done.stderr)


if __name__ == "__main__":
    unittest.main()
