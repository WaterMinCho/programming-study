# -*- coding: utf-8 -*-
"""여정 실행기 테스트. 진짜 하네스를 자식 프로세스로 띄워 판정·줄 번호·시간 초과·메모리·재귀·묶음·취소를 보고, genrun 과
생성 캐시, 가짜 node 로 Node 찾기를 봄.

실행: python -m unittest tests.test_journey_runner
시간 값(ms)은 단언하지 않고 판정만 봄. STUDY_LEAN_CI 가 있으면 모듈 전체를 건너뛰고, Node 가 없으면 JS 테스트를 건너뜀.
"""
import os

os.environ.setdefault("STUDY_NODE_PROBE", "0")

import json  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from journey import gen, node, runner, values  # noqa: E402

LEAN = bool(os.environ.get("STUDY_LEAN_CI"))
NODE = None if LEAN else node.find()
MB = 1024 * 1024
LIMIT_MB = 128  # 메모리 테스트가 빨리 끝나게 상한을 낮춤
LONG_MS = 30000  # 취소 테스트에서 끊기지 않게 두는 제한. 단언이 아니라 멈추지 않게 하는 값임

COUNT = "def f(n):\n    return 0 if n == 0 else 1 + f(n - 1)\n"
STYLES = {
    "plain": COUNT,
    "cache_default": "from functools import cache\n\n\n@cache\n" + COUNT,
    "builtin": "def f(n):\n    return 0 if n == 0 else 1 + max(f(m) for m in (n - 1,))\n",
    "raised": "import sys\nsys.setrecursionlimit(10**6)\n" + COUNT,
    "raised_small": "import sys\nfrom functools import cache\nsys.setrecursionlimit(3000)\n\n\n@cache\n" + COUNT,
    "cache": "import sys\nfrom functools import lru_cache\nsys.setrecursionlimit(10**6)\n\n\n@lru_cache(None)\n" + COUNT,
    "memo": ("import sys\nsys.setrecursionlimit(10**6)\nmemo = {}\n\n\ndef f(n):\n    if n in memo:\n        return memo[n]\n"
             "    memo[n] = 0 if n == 0 else 1 + f(n - 1)\n    return memo[n]\n"),
}
SOLUTION_F = "\n\ndef solution(n):\n    return f(n)\n"
NEST_PY = "def solution(n):\n    x = []\n    for _ in range(n - 1):\n        x = [x]\n    return x\n"
NEST_JS = "function solution(n) {\n    let x = [];\n    for (let i = 1; i < n; i++) {\n        x = [x];\n    }\n    return x;\n}\n"

HEAVY_JS = """function heavy(a, b, c, d, e, f, g) {
    let [x, y] = [a, b];
    let p = c + 1, q = d + 1, r = e + 1, s = f + 1, t = g + 1, u = x + y;
    if (a === 0) {
        return p + q + r + s + t + u - 5;
    }
    return 1 + heavy(a - 1, b, c, d, e, f, g);
}
function solution(n) {
    return heavy(n, 0, 0, 0, 0, 0, 0);
}
"""


# 하네스보다 먼저 읽히는 모듈. Windows 에서 부모가 calling 파일을 읽는 동안 바꿔치기가 거부되는 일을 흉내 내고,
# 하네스가 다시 하기 전에 Atomics.wait 로 쉬는지 셈
REFUSE_RENAME_JS = """"use strict";
const fs = require("fs");
const path = require("path");
const realRename = fs.renameSync;
const realWait = Atomics.wait;
const limit = Number(process.env.FAIL_RENAMES);
let failed = 0;
let waits = 0;
fs.renameSync = function (from, to) {
    if (path.basename(to) === "calling" && failed < limit) {
        failed++;
        const error = new Error("EPERM: operation not permitted, rename");
        error.code = "EPERM";
        throw error;
    }
    return realRename.apply(fs, arguments);
};
Atomics.wait = function () {
    waits++;
    return realWait.apply(Atomics, arguments);
};
process.on("exit", function () {
    fs.writeFileSync("retries.json", JSON.stringify({failed: failed, waits: waits}));
});
"""


def nested(depth):
    """depth 겹으로 감싼 빈 리스트. NEST_PY·NEST_JS 가 돌려주는 값임."""
    value = []
    for _ in range(depth - 1):
        value = [value]
    return value


class RunnerCase(unittest.TestCase):
    lang = "python"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journey_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def source(self, text):
        path = os.path.join(self.tmp, "sol%d%s" % (len(os.listdir(self.tmp)), runner.EXT[self.lang]))
        study.write_text(path, text)
        return path

    def case(self, args, expected=None, limit_ms=3000, **extra):
        case = dict({"args": args, "calls": len(args), "limit_ms": limit_ms}, **extra)
        if expected is not None:
            case["expected"] = values.canonical(expected)
        return case

    def run_one(self, text, args, expected=None, limit_ms=3000, cancel=None, **extra):
        workdir = tempfile.mkdtemp(prefix="w", dir=self.tmp)
        return runner.run_case(self.lang, self.source(text), self.case(args, expected, limit_ms, **extra), workdir,
                               cancel=cancel, node=NODE)

    def assertPasses(self, text, args, expected, **options):
        result = self.run_one(text, args, expected, **options)
        self.assertEqual(result["status"], "pass", result)
        return result


@unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
class PythonRunnerTest(RunnerCase):
    def test_pass_and_wrong(self):
        result = self.assertPasses("def solution(a, b):\n    return a + b\n", [[1, 2]], 3)
        self.assertEqual(result["values"], ["3"])
        self.assertEqual(len(result["calls_ms"]), 1)
        self.assertIsNotNone(result["peak_mb"])
        wrong = self.run_one("def solution(a, b):\n    return a - b\n", [[1, 2]], 3)
        self.assertEqual((wrong["status"], wrong["values"]), ("wrong", ["-1"]))

    def test_sha_expected_and_bool_int_difference(self):
        text = "def solution(a):\n    return [a > 0, a]\n"
        case = self.case([[1]], expected_sha=values.digest("[true,1]"))
        self.assertEqual(runner.run_case("python", self.source(text), case, tempfile.mkdtemp(dir=self.tmp))["status"], "pass")
        self.assertEqual(self.run_one(text, [[1]], [1, 1])["status"], "wrong")

    def test_runtime_error_has_line_number(self):
        result = self.run_one("def solution(a):\n    x = 1\n    return a[5]\n", [[[1]]], 1)
        self.assertEqual(result["status"], "runtime")
        self.assertIn("IndexError", result["error"])
        self.assertIn("(3번째 줄)", result["error"])
        self.assertEqual(result["failed_call"], 0)

    def test_syntax_error_is_fatal_with_line(self):
        result = self.run_one("def solution(a):\n    return 1\n\nif True\n    pass\n", [[1]], 1)
        self.assertEqual(result["status"], "fatal")
        self.assertEqual(result["fatal"]["kind"], "syntax")
        self.assertEqual(result["fatal"]["line"], 4)
        self.assertIn("SyntaxError", result["fatal"]["message"])
        indent = self.run_one("def solution(a):\nreturn 1\n", [[1]], 1)
        self.assertEqual((indent["status"], indent["fatal"]["kind"], indent["fatal"]["line"]), ("fatal", "syntax", 2))

    def test_missing_solution_is_fatal(self):
        result = self.run_one("def answer(a):\n    return a\n", [[1]], 1)
        self.assertEqual((result["status"], result["fatal"]["kind"]), ("fatal", "no_solution"))
        not_function = self.run_one("solution = 3\n", [[1]], 1)
        self.assertEqual(not_function["fatal"]["kind"], "no_solution")

    def test_error_at_load_is_fatal(self):
        result = self.run_one("x = 1 // 0\n\n\ndef solution(a):\n    return a\n", [[1]], 1)
        self.assertEqual((result["status"], result["fatal"]["kind"], result["fatal"]["line"]), ("fatal", "load", 1))
        self.assertIn("ZeroDivisionError", result["fatal"]["message"])

    def test_output_from_top_level_and_function_is_collected(self):
        result = self.assertPasses("print('top')\n\n\ndef solution(a):\n    print('in', a)\n    return a\n", [[1]], 1)
        self.assertEqual(result["printed"], "top\nin 1\n")
        self.assertFalse(result["printed_cut"])

    def test_endless_loop_is_timeout(self):
        result = self.run_one("def solution(a):\n    while True:\n        pass\n", [[1]], 1, limit_ms=300)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["failed_call"], 0)
        self.assertIsNone(result["elapsed_ms"])

    def test_slow_call_that_finishes_is_still_timeout(self):
        result = self.run_one("import time\n\n\ndef solution(a):\n    time.sleep(0.4)\n    return a\n", [[1]], 1,
                              limit_ms=300, kill_ms=5000)
        self.assertEqual((result["status"], result["failed_call"]), ("timeout", 0))

    def test_endless_top_level_code_is_timeout_with_note(self):
        with mock.patch.object(runner, "START_LIMIT_S", 0.5):
            result = self.run_one("while True:\n    pass\n", [[1]], 1, limit_ms=LONG_MS)
        self.assertEqual(result["status"], "timeout")
        self.assertIn("solution 을 부르기 전에", result["note"])

    def test_memory_limit_stops_c_loop(self):
        with mock.patch.object(study, "MEMORY_LIMIT_MB", LIMIT_MB):
            result = self.run_one("import itertools\n\n\ndef solution(a):\n    return list(itertools.count())\n", [[1]], 1,
                                  limit_ms=LONG_MS)
        self.assertEqual(result["status"], "memory")

    def test_tuple_return_is_bad_return_with_note(self):
        result = self.run_one("def solution(a):\n    return (1, 2)\n", [[1]], [1, 2])
        self.assertEqual((result["status"], result["note"]), ("bad_return", values.TUPLE_NOTE))
        self.assertEqual(result["failed_call"], 0)
        none = self.run_one("def solution(a):\n    pass\n", [[1]], 1)
        self.assertEqual((none["status"], none["note"]), ("bad_return", values.NONE_NOTE))
        nested = self.run_one("def solution(a):\n    return [1, {2}]\n", [[1]], 1)
        self.assertEqual((nested["status"], nested["note"]), ("bad_return", values.SET_NOTE))

    def test_bundle_calls_start_fresh(self):
        text = "counter = 0\n\n\ndef solution(a):\n    global counter\n    counter += 1\n    return counter\n"
        result = self.assertPasses(text, [[1], [2], [3]], [1, 1, 1])
        self.assertEqual(result["values"], ["1", "1", "1"])
        self.assertEqual(len(result["calls_ms"]), 3)

    def test_bundle_wrong_in_one_call_fails_the_line(self):
        result = self.run_one("def solution(a):\n    return a * 2\n", [[1], [2], [3]], [2, 4, 7])
        self.assertEqual((result["status"], result["values"]), ("wrong", ["2", "4", "6"]))

    def test_input_is_runtime_with_note(self):
        result = self.run_one("def solution(a):\n    return input()\n", [[1]], "x")
        self.assertEqual(result["status"], "runtime")
        self.assertIn("EOFError", result["error"])
        self.assertIn("input()", result["note"])

    def test_system_exit_is_runtime(self):
        result = self.run_one("import sys\n\n\ndef solution(a):\n    sys.exit(0)\n", [[1]], 1)
        self.assertEqual(result["status"], "runtime")
        self.assertIn("SystemExit", result["error"])

    def test_output_over_limit_is_runtime(self):
        result = self.run_one("def solution(a):\n    print('x' * 600000)\n    print('y' * 600000)\n    return 1\n", [[1]], 1)
        self.assertEqual(result["status"], "runtime")
        self.assertIn("1,000,000자", result["note"])
        self.assertTrue(result["printed_cut"])

    def test_output_over_limit_at_top_level_is_fatal_with_note(self):
        result = self.run_one("print('x' * 1000001)\n\n\ndef solution(a):\n    return a\n", [[1]], 1)
        self.assertEqual((result["status"], result["fatal"]["kind"]), ("fatal", "load"))
        self.assertIn("1,000,000자", result["fatal"]["message"])
        self.assertIn("1,000,000자", result["note"])

    def test_list_nested_over_64_is_bad_return_with_note(self):
        """반복문에서 answer = [answer, i] 로 쌓은 수천 겹 리스트가 부모로 가면 GUI 스레드의 json.loads 가 스택을 넘기므로 하네스가 막음."""
        self.assertPasses(NEST_PY, [[64]], nested(64))
        over = self.run_one(NEST_PY, [[65]], 1)
        self.assertEqual((over["status"], over["note"]), ("bad_return", values.DEPTH_NOTE), over)
        text = "import sys\nsys.setrecursionlimit(10**6)\n\n\ndef solution(n):\n    answer = []\n    for i in range(n):\n        answer = [answer, i]\n    return answer\n"
        deep = self.run_one(text, [[100000]], 1)
        self.assertEqual((deep["status"], deep["failed_call"], deep["note"]), ("bad_return", 0, values.DEPTH_NOTE), deep)

    def test_value_that_cannot_be_encoded_is_bad_return(self):
        if hasattr(sys, "get_int_max_str_digits"):  # 3.10.7 부터 4300자 제한이 있음
            big = self.run_one("def solution(a):\n    return 10 ** 5000\n", [[1]], 1)
            self.assertEqual(big["status"], "bad_return", big)
            self.assertIn("ValueError", big["note"])
            self.assertNotIn("비정상 종료", big["note"])

    def test_lone_surrogate_gets_a_verdict(self):
        text = "def solution(a):\n    print('\\ud800')\n    return '\\ud800'\n"
        self.assertEqual(self.run_one(text, [[1]], expected_sha=values.digest('"a"'))["status"], "wrong")
        result = self.run_one(text, [[1]], expected_sha=values.digest(values.canonical("\ud800")))
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["printed"], "\ud800\n")

    def test_run_cases_share_one_copy_through_workdir(self):
        path = self.source("def solution(a):\n    return 1\n")
        with runner.workspace() as workdir:
            first = runner.run_cases("python", path, [self.case([[1]], 1)], workdir=workdir)
            study.write_text(path, "def solution(a):\n    return 2\n")
            second = runner.run_cases("python", path, [self.case([[1]], 1), self.case([[2]], 1), self.case([[3]], 1)],
                                      workers=2, workdir=workdir)
        self.assertEqual([r["status"] for r in first + second], ["pass"] * 4)
        self.assertEqual(runner.run_cases("python", path, [self.case([[1]], 2)])[0]["status"], "pass")

    def test_cancel_flag_gives_cancelled(self):
        cancel = threading.Event()
        timer = threading.Timer(0.3, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        result = self.run_one("def solution(a):\n    while True:\n        pass\n", [[1]], 1, limit_ms=LONG_MS, cancel=cancel)
        self.assertEqual(result["status"], "cancelled")
        already = self.run_one("def solution(a):\n    return a\n", [[1]], 1, cancel=cancel)
        self.assertEqual(already["status"], "cancelled")

    def test_run_cases_keeps_order_with_workers(self):
        text = "import time\n\n\ndef solution(a):\n    time.sleep(a)\n    return a\n"
        delays = [0.3, 0.0, 0.2, 0.0, 0.1, 0.0]
        cases = [self.case([[d]], d) for d in delays]
        seen = []
        results = runner.run_cases("python", self.source(text), cases, workers=3,
                                   on_case=lambda index, result: seen.append((index, result["status"])))
        self.assertEqual(seen, [(i, "pass") for i in range(len(delays))])
        self.assertEqual([r["values"] for r in results], [[values.canonical(d)] for d in delays])

    def test_run_cases_fatal_first_fills_rest(self):
        cases = [self.case([[1]], 1) for _ in range(4)]
        seen = []
        results = runner.run_cases("python", self.source("def solution(a)\n    return a\n"), cases, workers=2,
                                   on_case=lambda index, result: seen.append(index))
        self.assertEqual(seen, [0, 1, 2, 3])
        self.assertTrue(all(r["status"] == "fatal" and r["fatal"]["kind"] == "syntax" for r in results))

    def test_run_cases_with_no_cases(self):
        self.assertEqual(runner.run_cases("python", self.source("x = 1\n"), []), [])


@unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
class RecursionTest(RunnerCase):
    def style(self, name, depth, expected_pass):
        result = self.run_one(STYLES[name] + SOLUTION_F, [[depth]], depth)
        if expected_pass:
            self.assertEqual(result["status"], "pass", (name, depth, result["error"], result["note"]))
        else:
            self.assertEqual(result["status"], "runtime", (name, depth, result))
            self.assertIn("RecursionError", result["error"])
            self.assertIsNone(result["fatal"])
            self.assertIn("재귀가 멈췄습니다", result["note"])
        return result

    def test_wrapper_caps_limits_above_1000(self):
        text = ("import sys\n\n\ndef solution(a):\n    out = []\n    for n in (3000, 10**6, 500, 1000):\n"
                "        sys.setrecursionlimit(n)\n        out.append(sys.getrecursionlimit())\n    return out\n")
        self.assertPasses(text, [[1]], [10000, 10000, 500, 1000])

    def test_bundle_second_call_starts_at_1000(self):
        text = "import sys\n\n\ndef solution(a):\n    before = sys.getrecursionlimit()\n    sys.setrecursionlimit(5000)\n    return before\n"
        self.assertPasses(text, [[1], [2]], [1000, 1000])

    def test_depth_300_passes_with_default_limit(self):
        for name in ("plain", "cache_default", "builtin"):
            self.style(name, 300, True)

    def test_depth_1200_fails_with_default_limit(self):
        for name in ("plain", "cache_default", "builtin"):
            result = self.style(name, 1200, False)
            self.assertIn("sys.setrecursionlimit", result["note"])
            self.assertIn("지금 한도 1000", result["note"])

    def test_depth_1500_passes_with_raised_limit(self):
        for name in ("raised", "raised_small", "cache", "memo"):
            self.style(name, 1500, True)

    def test_depth_200000_fails_without_crash(self):
        for name in ("raised", "cache", "memo"):
            result = self.style(name, 200000, False)
            self.assertIn("10,000으로 맞추므로", result["note"])
            self.assertIn("지금 한도 10000", result["note"])
            if name == "cache":
                self.assertIn("@cache", result["note"])
            else:
                self.assertNotIn("@cache", result["note"])


@unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
class BundleTimingTest(RunnerCase):
    SLEEPER = "import time\n\n\ndef solution(a):\n    time.sleep(a)\n    return a\n"

    def test_each_call_gets_its_own_limit(self):
        result = self.assertPasses(self.SLEEPER, [[0.3], [0.3], [0.3]], [0.3, 0.3, 0.3], limit_ms=500)
        self.assertEqual(len(result["calls_ms"]), 3)
        self.assertEqual(result["elapsed_ms"], max(result["calls_ms"]))

    def test_slow_top_level_code_is_not_measured(self):
        text = "import time\ntime.sleep(0.3)\n\n\ndef solution(a):\n    return a\n"
        self.assertPasses(text, [[1], [2], [3]], [1, 2, 3], limit_ms=200)

    def test_second_call_over_limit_is_timeout(self):
        result = self.run_one(self.SLEEPER, [[0.0], [0.6], [0.0]], [0.0, 0.6, 0.0], limit_ms=200)
        self.assertEqual((result["status"], result["failed_call"]), ("timeout", 1))


@unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
class HardeningTest(RunnerCase):
    def test_patched_time_and_json_do_not_break_the_harness(self):
        text = ("import time\nimport json\nimport builtins\ntime.perf_counter_ns = lambda: 0\ntime.perf_counter = lambda: 0\n"
                "json.dumps = None\nbuiltins.open = None\n\n\ndef solution(a):\n    return a\n")
        result = self.assertPasses(text, [[1]], 1)
        self.assertGreater(result["elapsed_ms"], 0)

    def test_child_sees_no_repository_path(self):
        text = "import os\nimport sys\n\n\ndef solution(a):\n    return [sys.argv[0], os.getcwd()] + sys.path\n"
        result = self.run_one(text, [[1]], 1)
        self.assertEqual(result["status"], "wrong", result)
        seen = json.loads(result["values"][0])
        self.assertGreaterEqual(len(seen), 2)
        for item in seen:
            self.assertNotIn(study.ROOT, item, seen)

    def test_source_is_copied_once_per_run(self):
        path = self.source("def solution(a):\n    return 1\n")
        workdir = tempfile.mkdtemp(prefix="w", dir=self.tmp)
        self.assertEqual(runner.run_case("python", path, self.case([[1]], 1), workdir)["status"], "pass")
        study.write_text(path, "def solution(a):\n    return 2\n")
        self.assertEqual(runner.run_case("python", path, self.case([[1]], 1), workdir)["status"], "pass")


@unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
@unittest.skipUnless(NODE, "Node.js 20 이상이 없음")
class NodeRunnerTest(RunnerCase):
    lang = "javascript"

    def test_pass_and_wrong(self):
        result = self.assertPasses("function solution(a, b) {\n    return a + b;\n}\n", [[1, 2]], 3)
        self.assertEqual(result["values"], ["3"])
        self.assertIsNotNone(result["peak_mb"])
        self.assertEqual(self.run_one("const solution = (a, b) => a - b;\n", [[1, 2]], 3)["status"], "wrong")
        self.assertEqual(self.run_one("let solution = function (a) { return [a, 'x', true]; };\n", [[1]], [1, "x", True])["status"], "pass")

    def test_runtime_error_has_line_number(self):
        result = self.run_one("function solution(a) {\n    let x = 1;\n    return a.b.c;\n}\n", [[1]], 1)
        self.assertEqual(result["status"], "runtime")
        self.assertIn("TypeError", result["error"])
        self.assertIn("(3번째 줄)", result["error"])

    def test_syntax_error_is_fatal(self):
        result = self.run_one("function solution(a) {\n    return 1\n}}\n", [[1]], 1)
        self.assertEqual((result["status"], result["fatal"]["kind"]), ("fatal", "syntax"))
        self.assertIn("SyntaxError", result["fatal"]["message"])

    def test_export_is_fatal_with_require_note(self):
        result = self.run_one("export function solution(a) {\n    return a;\n}\n", [[1]], 1)
        self.assertEqual((result["status"], result["fatal"]["kind"]), ("fatal", "syntax"))
        self.assertIn("require", result["note"])
        imported = self.run_one("import fs from 'fs';\nfunction solution(a) {\n    return a;\n}\n", [[1]], 1)
        self.assertEqual(imported["fatal"]["kind"], "syntax")
        self.assertIn("require", imported["note"])

    def test_missing_solution_is_fatal(self):
        result = self.run_one("const x = 1;\n", [[1]], 1)
        self.assertEqual((result["status"], result["fatal"]["kind"]), ("fatal", "no_solution"))

    def test_endless_loop_is_timeout(self):
        result = self.run_one("function solution(a) {\n    while (true) {}\n}\n", [[1]], 1, limit_ms=300)
        self.assertEqual((result["status"], result["failed_call"]), ("timeout", 0))

    def test_memory_limit_stops_array_growth(self):
        text = "function solution(a) {\n    const arr = [];\n    while (true) {\n        arr.push(new Array(100000).fill(1));\n    }\n}\n"
        with mock.patch.object(study, "MEMORY_LIMIT_MB", LIMIT_MB):
            result = self.run_one(text, [[1]], 1, limit_ms=LONG_MS)
        self.assertEqual(result["status"], "memory")

    def test_heavy_frame_recursion_passes_at_1500(self):
        self.assertPasses(HEAVY_JS, [[1500]], 1500)

    def test_deep_recursion_and_spread_are_runtime_with_note(self):
        deep = self.run_one(COUNT.replace("def f(n):", "function f(n) {").replace("    return 0 if n == 0 else 1 + f(n - 1)\n", "    return n === 0 ? 0 : 1 + f(n - 1);\n}\n")
                            + "function solution(n) {\n    return f(n);\n}\n", [[20000]], 20000)
        self.assertEqual(deep["status"], "runtime")
        self.assertIn("RangeError", deep["error"])
        self.assertIn("펼쳐", deep["note"])
        spread = self.run_one("function solution(a) {\n    return Math.max(...new Array(300000).fill(1));\n}\n", [[1]], 1)
        self.assertEqual(spread["status"], "runtime")
        self.assertIn("펼쳐", spread["note"])

    def test_bad_returns_have_notes(self):
        checks = (("function solution(a) {\n    const x = a;\n}\n", "undefined"),
                  ("function solution(a) {\n    return 10n;\n}\n", "BigInt"),
                  ("function solution(a) {\n    return 2 ** 53 + 2;\n}\n", "2^53"),
                  ("function solution(a) {\n    return new Map();\n}\n", "Map"),
                  ("function solution(a) {\n    return new Set([1]);\n}\n", "Set"),
                  ("function solution(a) {\n    return [1, , 3];\n}\n", "빈 칸"),
                  ("function solution(a) {\n    return NaN;\n}\n", "NaN"),
                  ("function solution(a) {\n    return {a: 1};\n}\n", "객체"),
                  ("function solution(a) {\n    return new Int32Array(2);\n}\n", "TypedArray"),
                  ("async function solution(a) {\n    return a;\n}\n", "Promise"))
        for text, word in checks:
            result = self.run_one(text, [[1]], 1)
            self.assertEqual(result["status"], "bad_return", (text, result))
            self.assertIn(word, result["note"], text)

    def test_console_output_is_collected(self):
        result = self.assertPasses("console.log('top');\nfunction solution(a) {\n    console.log('in', a);\n    console.error('err');\n    return a;\n}\n", [[1]], 1)
        self.assertEqual(result["printed"], "top\nin 1\nerr\n")

    def test_process_exit_is_runtime(self):
        result = self.run_one("function solution(a) {\n    process.exit(0);\n}\n", [[1]], 1)
        self.assertEqual(result["status"], "runtime")
        self.assertIn("process.exit", result["error"])

    def test_bundle_calls_start_fresh(self):
        text = "let count = 0;\nfunction solution(a) {\n    count += 1;\n    return count;\n}\n"
        result = self.assertPasses(text, [[1], [2], [3]], [1, 1, 1])
        self.assertEqual(result["values"], ["1", "1", "1"])

    def test_require_main_is_not_module(self):
        self.assertPasses("function solution(a) {\n    return require.main === module;\n}\n", [[1]], False)
        self.assertPasses("const fs = require('fs');\nfunction solution(a) {\n    return typeof fs.readFileSync;\n}\n", [[1]], "function")

    def test_patched_stringify_does_not_break_encoding(self):
        text = ("JSON.stringify = () => '\"hacked\"';\nArray.prototype.map = null;\nprocess.hrtime.bigint = () => 0n;\n"
                "function solution(a) {\n    return [a, 'b', true];\n}\n")
        result = self.assertPasses(text, [[1]], [1, "b", True])
        self.assertEqual(result["values"], ['[1,"b",true]'])
        self.assertGreater(result["elapsed_ms"], 0)

    def test_array_nested_over_64_is_bad_return_with_note(self):
        """하네스는 8,000겹 가까이 인코딩하지만 부모의 json.loads 가 그보다 얕은 곳에서 스택을 넘기므로 64겹에서 막음."""
        self.assertPasses(NEST_JS, [[64]], nested(64))
        over = self.run_one(NEST_JS, [[65]], 1)
        self.assertEqual(over["status"], "bad_return", over)
        self.assertIn("64겹", over["note"])
        text = "function solution(n) {\n    let answer = [];\n    for (let i = 0; i < n; i++) {\n        answer = [answer, i];\n    }\n    return answer;\n}\n"
        deep = self.run_one(text, [[6000]], 1)
        self.assertEqual((deep["status"], deep["failed_call"], deep["note"]), ("bad_return", 0, over["note"]), deep)

    def test_value_that_cannot_be_encoded_is_bad_return(self):
        text = "function solution(a) {\n    const x = [1];\n    Object.defineProperty(x, 0, {get() {\n        throw new Error('boom');\n    }});\n    return x;\n}\n"
        result = self.run_one(text, [[1]], 1)
        self.assertEqual((result["status"], result["failed_call"]), ("bad_return", 0), result)
        self.assertIn("Error: boom", result["note"])

    def test_output_over_limit_at_top_level_is_fatal_with_note(self):
        result = self.run_one("process.stdout.write('x'.repeat(1000001));\nfunction solution(a) {\n    return a;\n}\n", [[1]], 1)
        self.assertEqual((result["status"], result["fatal"]["kind"]), ("fatal", "load"))
        self.assertIn("1,000,000자", result["note"])

    def test_lone_surrogate_gets_a_verdict(self):
        text = "function solution(a) {\n    return '\\ud800';\n}\n"
        self.assertEqual(self.run_one(text, [[1]], expected_sha=values.digest('"a"'))["status"], "wrong")
        result = self.run_one(text, [[1]], expected_sha=values.digest(values.canonical("\ud800")))
        self.assertEqual(result["status"], "pass", result)

    def rename_refused(self, failures):
        """calling 파일 바꿔치기를 처음 failures 번 EPERM 으로 거부하는 미리 읽기 모듈을 끼워 돌림. (결과, 거부 수, 쉰 수)."""
        preload = os.path.join(self.tmp, "refuse.js")
        study.write_text(preload, REFUSE_RENAME_JS)
        workdir = tempfile.mkdtemp(prefix="w", dir=self.tmp)
        real = runner.command

        def with_preload(lang, folder, node=None, python=None):
            cmd, env = real(lang, folder, node, python)
            env["FAIL_RENAMES"] = str(failures)
            return [cmd[0], "-r", preload] + cmd[1:], env

        with mock.patch.object(runner, "command", with_preload):
            result = runner.run_case("javascript", self.source("function solution(a) {\n    return a;\n}\n"),
                                     self.case([[1]], 1), workdir, node=NODE)
        counts = [study.read_json(os.path.join(workdir, name, "retries.json")) for name in os.listdir(workdir)
                  if os.path.isfile(os.path.join(workdir, name, "retries.json"))]
        self.assertEqual(len(counts), 1)
        return result, counts[0]["failed"], counts[0]["waits"]

    def test_refused_rename_waits_and_retries(self):
        result, failed, waits = self.rename_refused(3)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual((failed, waits), (3, 3))

    def test_rename_gives_up_after_twenty_tries(self):
        result, failed, waits = self.rename_refused(1000)
        self.assertEqual(result["status"], "runtime", result)
        self.assertEqual((failed, waits), (20, 19))

    def test_run_cases_in_parallel(self):
        cases = [self.case([[i]], i * 2) for i in range(5)]
        results = runner.run_cases("javascript", self.source("function solution(a) {\n    return a * 2;\n}\n"), cases,
                                   workers=3, node=NODE)
        self.assertEqual([r["status"] for r in results], ["pass"] * 5)


@unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
@unittest.skipIf(sys.platform == "win32", "가짜 node 는 셸 스크립트라 Windows 에서는 건너뜀")
class FakeNodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journey_node_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patch = mock.patch.object(node, "MAC_FIXED", ())
        patch.start()
        self.addCleanup(patch.stop)

    def fake_node(self, version):
        path = os.path.join(self.tmp, "node-%s" % version)
        with open(path, "w") as f:
            f.write("#!/bin/sh\necho v%s\n" % version)
        os.chmod(path, 0o755)
        return path

    def test_old_node_is_rejected_and_new_node_accepted(self):
        old = self.fake_node("18.20.4")
        self.assertFalse(node.inspect(old)["ok"])
        env = {"STUDY_NODE": old, "PATH": "", "STUDY_NODE_PROBE": "0"}
        self.assertIsNone(node.search(env=env, home=self.tmp, platform=sys.platform))
        with self.assertRaises(ValueError) as caught:
            node.check(old)
        self.assertIn("20", str(caught.exception))
        new = self.fake_node("20.1.0")
        env["STUDY_NODE"] = new
        self.assertEqual(node.search(env=env, home=self.tmp, platform=sys.platform),
                         {"path": new, "version": "20.1.0", "major": 20})
        self.assertEqual(node.check(new)["version"], "20.1.0")

    def test_saved_path_comes_after_env_and_before_path(self):
        saved = self.fake_node("22.0.0")
        env = {"PATH": "", "STUDY_NODE_PROBE": "0"}
        self.assertEqual(node.search(saved=saved, env=env, home=self.tmp, platform=sys.platform)["path"], saved)


@unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
class GenrunTest(unittest.TestCase):
    SET_GEN = ("def words(rng):\n    seen = set()\n    for _ in range(12):\n        seen.add('w%d' % rng.below(100000))\n"
               "    return [list(seen)]\n")
    SMALL_GEN = ("from journey.gen import distinct_words\n\n\ndef small(rng):\n"
                 "    names = distinct_words(rng, rng.between(1, 3), 1, 3, alphabet='ab_')\n"
                 "    return [names, rng.between(1, 3)]\n")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journey_gen_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def out(self, name):
        return os.path.join(self.tmp, name)

    def test_command_and_environment(self):
        cmd = runner.genrun_command("/g/gen.py", "/g/spec.json", "/g/out.json")
        self.assertNotIn("-I", cmd)
        self.assertEqual(cmd[1:5], ["-S", "-B", "-X", "utf8"])
        self.assertEqual(cmd[5:], [runner.GENRUN_PY, study.ROOT, "/g/gen.py", "/g/spec.json", "/g/out.json"])
        self.assertEqual(runner.genrun_command("a", "b", "c", "/g/validate.py")[-2:], ["--validate", "/g/validate.py"])
        with mock.patch.dict(os.environ, {"PYTHONPATH": "/x", "PYTHONHASHSEED": "random", "PYTHONDONTWRITEBYTECODE": "1"}):
            env = runner.genrun_env()
        self.assertEqual(env["PYTHONHASHSEED"], "0")
        self.assertEqual([key for key in env if key.startswith("PYTHON")], ["PYTHONHASHSEED"])

    def test_set_order_is_the_same_in_two_processes(self):
        spec = {"gen": "words", "seed": 3}
        runner.generate_to(self.SET_GEN, spec, self.out("a.json"))
        runner.generate_to(self.SET_GEN, spec, self.out("b.json"))
        a, b = study.read_json(self.out("a.json")), study.read_json(self.out("b.json"))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 1)
        self.assertGreater(len(a[0][0]), 5)

    def test_bundle_uses_one_rng_and_journey_gen_import(self):
        spec = {"gen": "small", "seed": 11, "count": 4}
        report = runner.generate_to(self.SMALL_GEN, spec, self.out("c.json"))
        self.assertEqual(report, {"invalid": None})
        inputs = study.read_json(self.out("c.json"))
        rng = gen.Rng(11)
        want = []
        for _ in range(4):
            names = gen.distinct_words(rng, rng.between(1, 3), 1, 3, alphabet="ab_")
            want.append([names, rng.between(1, 3)])
        self.assertEqual(inputs, want)

    def test_params_are_passed_as_keywords(self):
        source = "def sized(rng, n, lo=0):\n    return [[rng.between(lo, lo + 1) for _ in range(n)], n]\n"
        runner.generate_to(source, {"gen": "sized", "seed": 1, "params": {"n": 5, "lo": 7}}, self.out("d.json"))
        inputs = study.read_json(self.out("d.json"))
        self.assertEqual(len(inputs), 1)
        self.assertEqual(len(inputs[0][0]), 5)
        self.assertTrue(all(value in (7, 8) for value in inputs[0][0]))

    def test_validate_reports_the_first_violation(self):
        validate = ("def validate(names, k):\n    if k == 3:\n        return '5번 줄: k = %d' % k\n    return None\n")
        spec = {"gen": "small", "seed": 11, "count": 30}
        report = runner.generate_to(self.SMALL_GEN, spec, self.out("e.json"), validate_source=validate)
        inputs = study.read_json(self.out("e.json"))
        first = [index for index, args in enumerate(inputs) if args[1] == 3]
        self.assertTrue(first, "seed 11 의 30건 안에 k == 3 이 없음")
        self.assertEqual(report["invalid"], {"index": first[0], "message": "5번 줄: k = 3"})
        clean = runner.generate_to(self.SMALL_GEN, spec, self.out("f.json"),
                                   validate_source="def validate(names, k):\n    return None\n")
        self.assertEqual(clean, {"invalid": None})

    def test_failing_generator_raises_gen_error(self):
        with self.assertRaises(runner.GenError) as caught:
            runner.generate_to("def broken(rng):\n    raise ValueError('boom')\n", {"gen": "broken", "seed": 1}, self.out("g.json"))
        self.assertIn("broken", str(caught.exception))
        self.assertIn("boom", str(caught.exception))
        with self.assertRaises(runner.GenError):
            runner.generate_to("x = 1\n", {"gen": "missing", "seed": 1}, self.out("h.json"))
        self.assertFalse(os.path.exists(self.out("g.json")))


@unittest.skipIf(LEAN, "자식 프로세스를 띄우는 테스트는 journey.yml 에서 돎")
class CacheTest(unittest.TestCase):
    GEN = "def nums(rng, n):\n    return [[rng.below(10) for _ in range(n)]]\n"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journey_cache_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patch = mock.patch.object(runner, "CACHE_DIR", os.path.join(self.tmp, "cache"))
        patch.start()
        self.addCleanup(patch.stop)
        self.calls = []
        real = runner.generate_to

        def counting(gen_source, spec, out_path, validate_source=None):
            self.calls.append(spec["seed"])
            return real(gen_source, spec, out_path, validate_source)

        patch = mock.patch.object(runner, "generate_to", counting)
        patch.start()
        self.addCleanup(patch.stop)

    def test_same_spec_is_generated_once(self):
        spec = {"gen": "nums", "seed": 1, "params": {"n": 20}}
        first = runner.generated_args(self.GEN, spec)
        second = runner.generated_args(self.GEN, spec)
        self.assertEqual(first, second)
        self.assertEqual(self.calls, [1])
        self.assertEqual(len(study.read_json(first)[0][0]), 20)
        self.assertEqual(runner.cache_info()["files"], 1)

    def test_changed_generator_source_is_regenerated(self):
        spec = {"gen": "nums", "seed": 1, "params": {"n": 20}}
        a = runner.generated_args(self.GEN, spec)
        b = runner.generated_args(self.GEN.replace("10", "11"), spec)
        self.assertNotEqual(a, b)
        self.assertEqual(self.calls, [1, 1])
        self.assertNotEqual(runner.cache_key(self.GEN, spec), runner.cache_key(self.GEN, dict(spec, count=2)))
        self.assertEqual(runner.cache_key(self.GEN, spec), runner.cache_key(self.GEN, {"params": {"n": 20}, "seed": 1, "gen": "nums"}))

    def test_broken_cache_file_is_regenerated(self):
        spec = {"gen": "nums", "seed": 1, "params": {"n": 20}}
        path = runner.generated_args(self.GEN, spec)
        with open(path, "w") as f:
            f.write("[[1, 2")
        self.assertEqual(runner.generated_args(self.GEN, spec), path)
        self.assertEqual(self.calls, [1, 1])
        self.assertEqual(len(study.read_json(path)[0][0]), 20)

    def test_least_recently_used_file_is_removed_over_the_limit(self):
        spec_a = {"gen": "nums", "seed": 1, "params": {"n": 400}}
        spec_b = {"gen": "nums", "seed": 2, "params": {"n": 400}}
        spec_c = {"gen": "nums", "seed": 3, "params": {"n": 400}}
        a = runner.generated_args(self.GEN, spec_a)
        time.sleep(0.05)
        b = runner.generated_args(self.GEN, spec_b)
        time.sleep(0.05)
        self.assertEqual(runner.generated_args(self.GEN, spec_a), a)  # A 를 읽어 B 보다 최근에 쓴 것으로 만듦
        time.sleep(0.05)
        size = os.path.getsize(a)
        with mock.patch.object(runner, "CACHE_LIMIT_MB", (size * 2 + size // 2) / MB):
            c = runner.generated_args(self.GEN, spec_c)
        self.assertTrue(os.path.exists(a))
        self.assertFalse(os.path.exists(b))
        self.assertTrue(os.path.exists(c))
        self.assertEqual(self.calls, [1, 2, 3])

    def test_clear_cache(self):
        runner.generated_args(self.GEN, {"gen": "nums", "seed": 1, "params": {"n": 5}})
        runner.generated_args(self.GEN, {"gen": "nums", "seed": 2, "params": {"n": 5}})
        self.assertEqual(runner.cache_info()["files"], 2)
        self.assertGreater(runner.cache_info()["bytes"], 0)
        self.assertEqual(runner.clear_cache(), {"bytes": 0, "files": 0})
        self.assertEqual(runner.cache_info(), {"bytes": 0, "files": 0})


class HelperTest(unittest.TestCase):
    def test_workers_follow_environment(self):
        with mock.patch.dict(os.environ, {"STUDY_JOURNEY_WORKERS": "3"}):
            self.assertEqual(runner.workers(), 3)
        with mock.patch.dict(os.environ, {"STUDY_JOURNEY_WORKERS": "x"}):
            self.assertTrue(1 <= runner.workers() <= 4)
        with mock.patch.dict(os.environ, {"STUDY_JOURNEY_WORKERS": "0"}):
            self.assertEqual(runner.workers(), 1)

    def test_kill_limits(self):
        self.assertEqual(runner.grade_kill_ms(1000), 1500)
        self.assertEqual(runner.RUN_KILL_MS, runner.RUN_LIMIT_MS + 500)

    def test_child_memory_subtracts_the_stack_on_windows(self):
        with mock.patch.object(study, "runner_memory", return_value=100 * MB):
            with mock.patch.object(runner.sys, "platform", "win32"):
                self.assertEqual(runner.child_memory("pid", "python"), 36 * MB)
                self.assertEqual(runner.child_memory("pid", "javascript"), 100 * MB)
            with mock.patch.object(runner.sys, "platform", "darwin"):
                self.assertEqual(runner.child_memory("pid", "python"), 100 * MB)
        with mock.patch.object(study, "runner_memory", return_value=0):
            self.assertEqual(runner.child_memory("pid", "python"), 0)

    def test_values_the_parent_cannot_read_give_a_verdict(self):
        """result.json 의 반환값을 부모가 읽다가 RecursionError·MemoryError 가 나도 채점 전체가 멈추지 않고 그 줄만 runtime 이 됨."""
        case_dir = tempfile.mkdtemp(prefix="journey_test_")
        self.addCleanup(shutil.rmtree, case_dir, True)
        study.write_text(os.path.join(case_dir, "result.json"), json.dumps({"status": "done", "values": ["[1]"], "times_ns": [1000]}))
        case = {"calls": 1, "limit_ms": 1000, "expected": "[1]"}
        self.assertEqual(runner.compose("python", case_dir, case, None, None, 0)["status"], "pass")
        for error in (RecursionError, MemoryError):
            with mock.patch.object(values, "canonical", side_effect=error):
                self.assertEqual(runner.compose("python", case_dir, case, None, None, 0)["status"], "runtime", error)

    def test_command_lines(self):
        cmd, env = runner.command("python", "/w")
        self.assertEqual(cmd[1:5], ["-I", "-S", "-B", "-X"])
        self.assertEqual(cmd[-2:], [os.path.join("/w", "harness.py"), "job.json"])
        self.assertIsNone(env)
        with mock.patch.dict(os.environ, {"NODE_OPTIONS": "--x", "NODE_PATH": "/y"}):
            cmd, env = runner.command("javascript", "/w", node={"path": "/n/node"})
        self.assertEqual(cmd, ["/n/node", "--max-old-space-size=%d" % study.MEMORY_LIMIT_MB, os.path.join("/w", "harness.js"),
                               "job.json"])
        self.assertNotIn("NODE_OPTIONS", env)
        self.assertNotIn("NODE_PATH", env)
        with mock.patch.object(node, "find", return_value=None):
            with self.assertRaises(RuntimeError):
                runner.command("javascript", "/w")


if __name__ == "__main__":
    unittest.main()
