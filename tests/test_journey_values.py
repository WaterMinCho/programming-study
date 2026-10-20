# -*- coding: utf-8 -*-
"""여정 값 처리·난수·Node 후보 테스트. 자식 프로세스를 띄우지 않는 것만 모음(하네스·genrun·캐시는 test_journey_runner).

실행: python -m unittest tests.test_journey_values
"""
import os

os.environ.setdefault("STUDY_NODE_PROBE", "0")

import ast  # noqa: E402
import ntpath  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from journey import gen, node, values  # noqa: E402

# Rng(7) 의 처음 세 값과 distinct_words 결과. 구현 뒤 한 번 계산해 박은 값이고, 바뀌면 모든 기대값 sha 가 어긋남
RNG7_FIRST3 = [7191089600892374487, 309689372594955804, 16616101746815609346]
RNG7_WORDS = ["a_", "ba", "aa", "__b", "ab_"]
SPLITMIX_SEED0 = 0xE220A8397B1DCDAF  # splitmix64 참조 구현의 seed 0 첫 출력


class TypeTest(unittest.TestCase):
    def test_parse_type_reads_nested_lists(self):
        self.assertEqual(values.parse_type("int"), "int")
        self.assertEqual(values.parse_type(" list[str] "), ("list", "str"))
        self.assertEqual(values.parse_type("list[list[int]]"), ("list", ("list", "int")))
        self.assertEqual(values.type_text(("list", ("list", "bool"))), "list[list[bool]]")

    def test_parse_type_rejects_other_types(self):
        for text in ("float", "dict", "tuple[int]", "list[", "List[int]"):
            with self.assertRaises(ValueError):
                values.parse_type(text)

    def test_check_tells_bool_and_int_apart(self):
        self.assertIsNone(values.check(1, "int"))
        self.assertIsNone(values.check(True, "bool"))
        self.assertIn("불리언이 있습니다", values.check(True, "int"))
        self.assertIn("불리언이 아닙니다", values.check(1, "bool"))

    def test_check_messages_per_type(self):
        self.assertIn("정수가 아닙니다", values.check("x", "int"))
        self.assertIn("2^53-1", values.check(2 ** 53, "int"))
        self.assertIsNone(values.check(2 ** 53 - 1, "int"))
        self.assertIn("문자열이 아닙니다", values.check(1, "str"))
        self.assertIn("리스트가 아닙니다", values.check(1, "list[int]"))
        self.assertIn("2번째 원소: 정수가 아닙니다", values.check([1, "a"], "list[int]"))
        self.assertIn("1번째 원소: 2번째 원소: 문자열이 아닙니다", values.check([["a", 1]], "list[list[str]]"))
        self.assertIsNone(values.check([[1], []], ("list", ("list", "int"))))


class CanonicalTest(unittest.TestCase):
    def test_bool_and_int_differ_in_json(self):
        self.assertEqual(values.canonical(True), "true")
        self.assertEqual(values.canonical(1), "1")
        self.assertNotEqual(values.canonical([True, 1]), values.canonical([1, 1]))

    def test_canonical_json_has_no_spaces_and_keeps_unicode(self):
        self.assertEqual(values.canonical(["a", 1, None, False]), '["a",1,null,false]')
        self.assertEqual(values.canonical("후추"), '"후추"')
        self.assertEqual(values.canonical([]), "[]")
        with self.assertRaises(ValueError):
            values.canonical(float("nan"))

    def test_digest_and_result_text(self):
        self.assertEqual(values.digest("[]"), "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945")
        self.assertEqual(values.result_text(["1", "2"], True), "[1,2]")
        self.assertEqual(values.result_text(["[1,2]"], False), "[1,2]")

    def test_matches_compares_literal_or_sha(self):
        self.assertTrue(values.matches("[1,2]", expected="[1,2]"))
        self.assertFalse(values.matches("[1,2]", expected="[1, 2]"))
        self.assertTrue(values.matches("[1,2]", expected_sha=values.digest("[1,2]")))
        self.assertFalse(values.matches("[1,2]", expected_sha=values.digest("[2,1]")))

    def test_digest_accepts_a_lone_surrogate(self):
        text = values.canonical("\ud800")
        self.assertEqual(len(values.digest(text)), 64)
        self.assertNotEqual(values.digest(text), values.digest(values.canonical("\ud801")))
        self.assertFalse(values.matches(text, expected_sha=values.digest('"a"')))

    def test_encode_py_rejects_with_notes(self):
        self.assertEqual(values.encode_py([1, "a", True]), ('[1,"a",true]', ""))
        self.assertEqual(values.encode_py(None), (None, values.NONE_NOTE))
        self.assertEqual(values.encode_py((1, 2)), (None, values.TUPLE_NOTE))
        self.assertEqual(values.encode_py({1}), (None, values.SET_NOTE))
        self.assertEqual(values.encode_py({"a": 1}), (None, values.DICT_NOTE))
        self.assertEqual(values.encode_py(x for x in [1]), (None, values.GENERATOR_NOTE))
        self.assertEqual(values.encode_py([1, [2, (3,)]]), (None, values.TUPLE_NOTE))
        self.assertIn("inf", values.encode_py(float("inf"))[1])
        self.assertIn("object", values.encode_py(object())[1])
        self.assertEqual(values.encode_py(3.0), ("3.0", ""))
        deep = [1]
        for _ in range(63):
            deep = [deep]
        self.assertEqual(values.encode_py(deep)[1], "")  # 64겹까지 받음
        self.assertEqual(values.encode_py([deep]), (None, values.DEPTH_NOTE))


class ShowTest(unittest.TestCase):
    def test_show_follows_language(self):
        value = ["a", True, None, 3]
        self.assertEqual(values.show(value, "python"), "['a', True, None, 3]")
        self.assertEqual(values.show(value, "javascript"), '["a", true, null, 3]')
        self.assertEqual(values.show("x", "python"), "'x'")
        self.assertEqual(values.show("x", "javascript"), '"x"')

    def test_show_cuts_long_values(self):
        text = values.show(list(range(1000)), "python", limit=40)
        self.assertEqual(len(text), 40 + len("… (전체 %d자)" % len(repr(list(range(1000))))))
        self.assertTrue(text.endswith("자)"))
        self.assertIn("(전체 ", text)

    def test_show_args_joins_with_commas(self):
        self.assertEqual(values.show_args([["a"], 2], "python"), "['a'], 2")
        self.assertEqual(values.show_args([["a"], 2], "javascript"), '["a"], 2')


class LiteralTest(unittest.TestCase):
    def test_json_literals(self):
        self.assertEqual(values.parse_literal("[1, 2, 3]"), [1, 2, 3])
        self.assertEqual(values.parse_literal('"abc"'), "abc")
        self.assertIs(values.parse_literal("true"), True)
        self.assertIsNone(values.parse_literal("null"))
        self.assertEqual(values.parse_literal(' [["a", "b"], []] '), [["a", "b"], []])

    def test_python_literals(self):
        self.assertEqual(values.parse_literal("[1, 'a', True, None]"), [1, "a", True, None])
        self.assertEqual(values.parse_literal("(1, 2)"), [1, 2])
        self.assertEqual(values.parse_literal("'x'"), "x")
        self.assertIs(values.parse_literal("False"), False)

    def test_dict_and_set_are_rejected(self):
        for text in ('{"a": 1}', "{1, 2}", "[{'a': 1}]", "set()"):
            with self.assertRaises(ValueError) as caught:
                values.parse_literal(text)
            self.assertIn("딕셔너리와 집합", str(caught.exception))

    def test_unreadable_text_is_rejected(self):
        for text in ("", "abc", "[1, 2", "1 +", "b'x'", "1j"):
            with self.assertRaises(ValueError) as caught:
                values.parse_literal(text)
            self.assertIn("읽지 못했습니다", str(caught.exception))


class StarterTest(unittest.TestCase):
    SIGNATURE = {"params": [{"name": "records", "type": "list[str]"}, {"name": "k", "type": "int"}], "returns": "list[str]"}

    def test_python_starter_matches_spec(self):
        self.assertEqual(values.starter(self.SIGNATURE, "python"),
                         "def solution(records, k):\n    answer = []\n    return answer\n")

    def test_javascript_starter_matches_spec(self):
        self.assertEqual(values.starter(self.SIGNATURE, "javascript"),
                         "function solution(records, k) {\n    var answer = [];\n    return answer;\n}\n")

    def test_initial_value_follows_return_type(self):
        for returns, py, js in (("int", "0", "0"), ("str", "''", "''"), ("bool", "True", "true"), ("list[int]", "[]", "[]")):
            signature = {"params": [{"name": "n", "type": "int"}], "returns": returns}
            self.assertIn("answer = %s\n" % py, values.starter(signature, "python"))
            self.assertIn("answer = %s;\n" % js, values.starter(signature, "javascript"))


def gen_violations(source):
    """verify 가 gen.py 에 거는 검사와 같은 규칙. 어긴 곳의 설명 목록을 돌려줌."""
    found = []
    tree = ast.parse(source)
    for node_ in ast.walk(tree):
        if isinstance(node_, ast.Import):
            names = [alias.name for alias in node_.names if alias.name != "journey.gen"]
            if names:
                found.append("import %s" % ", ".join(names))
        elif isinstance(node_, ast.ImportFrom) and node_.module != "journey.gen":
            found.append("from %s import" % node_.module)
        elif isinstance(node_, (ast.Set, ast.SetComp)):
            found.append("집합 표현")
        elif isinstance(node_, ast.Call) and isinstance(node_.func, ast.Name):
            if node_.func.id in ("set", "frozenset", "hash", "__import__", "eval", "exec", "compile", "open"):
                found.append("%s() 호출" % node_.func.id)
    return found


class RngTest(unittest.TestCase):
    def test_rng7_first_values_are_fixed(self):
        rng = gen.Rng(7)
        self.assertEqual([rng.next64() for _ in range(3)], RNG7_FIRST3)

    def test_matches_splitmix64_reference(self):
        self.assertEqual(gen.Rng(0).next64(), SPLITMIX_SEED0)

    def test_seed_is_masked_to_64_bits(self):
        self.assertEqual(gen.Rng(2 ** 64 + 7).next64(), gen.Rng(7).next64())
        self.assertEqual(gen.Rng(-1).state, 2 ** 64 - 1)

    def test_ranges(self):
        rng = gen.Rng(11)
        draws = [rng.below(5) for _ in range(500)]
        self.assertEqual(sorted(set(draws)), [0, 1, 2, 3, 4])
        self.assertTrue(all(3 <= rng.between(3, 4) <= 4 for _ in range(100)))
        self.assertTrue(all(rng.chance(1, 1) for _ in range(10)))
        self.assertFalse(any(rng.chance(0, 1) for _ in range(10)))
        self.assertIn(rng.pick(["x", "y"]), ("x", "y"))
        with self.assertRaises(ValueError):
            rng.below(0)
        with self.assertRaises(ValueError):
            rng.between(5, 4)

    def test_shuffle_and_sample(self):
        rng = gen.Rng(5)
        items = list(range(20))
        shuffled = rng.shuffle(list(items))
        self.assertEqual(sorted(shuffled), items)
        self.assertNotEqual(shuffled, items)
        picked = rng.sample(range(20), 7)
        self.assertEqual(len(picked), 7)
        self.assertEqual(len(set(picked)), 7)
        with self.assertRaises(ValueError):
            rng.sample([1, 2], 3)

    def test_same_seed_same_sequence(self):
        a, b = gen.Rng(99), gen.Rng(99)
        self.assertEqual([a.between(0, 10 ** 9) for _ in range(50)], [b.between(0, 10 ** 9) for _ in range(50)])


class WordsTest(unittest.TestCase):
    def test_distinct_words_are_fixed(self):
        self.assertEqual(gen.distinct_words(gen.Rng(7), 5, 1, 3, alphabet="ab_"), RNG7_WORDS)

    def test_distinct_words_keep_the_drawn_order(self):
        rng = gen.Rng(7)
        drawn = []
        while len(drawn) < 5:
            candidate = gen.word(rng, 1, 3, "ab_")
            if candidate not in drawn:
                drawn.append(candidate)
        self.assertEqual(gen.distinct_words(gen.Rng(7), 5, 1, 3, alphabet="ab_"), drawn)
        many = gen.distinct_words(gen.Rng(3), 200, 1, 4)
        self.assertEqual(len(set(many)), 200)
        self.assertTrue(all(1 <= len(w) <= 4 and set(w) <= set(gen.LOWER) for w in many))

    def test_impossible_count_raises(self):
        with self.assertRaises(ValueError):
            gen.distinct_words(gen.Rng(1), 3, 1, 1, alphabet="a")
        self.assertEqual(sorted(gen.distinct_words(gen.Rng(1), 2, 1, 1, alphabet="ab")), ["a", "b"])

    def test_word_length_is_in_range(self):
        rng = gen.Rng(2)
        for _ in range(100):
            self.assertTrue(2 <= len(gen.word(rng, 2, 4)) <= 4)

    def test_gen_module_passes_the_generator_rules(self):
        with open(gen.__file__, encoding="utf-8") as f:
            self.assertEqual(gen_violations(f.read()), [])

    def test_generator_rules_catch_set_and_imports(self):
        bad = "import random\nfrom journey.gen import Rng\ndef g(rng):\n    return [list(set([1])), {1, 2}, hash('a')]\n"
        self.assertCountEqual(gen_violations(bad), ["import random", "집합 표현", "set() 호출", "hash() 호출"])
        self.assertCountEqual(gen_violations("import time\nx = __import__('os')\n"), ["import time", "__import__() 호출"])
        self.assertEqual(gen_violations("import journey.gen\nfrom journey.gen import Rng\n"), [])


class FakeRun(object):
    """subprocess.run 자리에 들어가 부른 명령만 남김. 출력은 stdout 에 둔 글."""

    def __init__(self, stdout=b""):
        self.calls = []
        self.stdout = stdout

    def __call__(self, args, **options):
        self.calls.append((list(args), options))
        return mock.Mock(stdout=self.stdout, returncode=0)


class CandidatesTest(unittest.TestCase):
    def index(self, paths, ending):
        for i, path in enumerate(paths):
            if path.replace("\\", "/").endswith(ending):
                return i
        self.fail("%s 가 후보에 없음: %s" % (ending, paths))

    def test_mac_order(self):
        home = "/Users/me"
        files = {"/Users/me/.nvm/alias/default": "20.10.0\n",
                 "/Users/me/.volta/tools/user/platform.json": '{"node": {"runtime": "20.11.1", "npm": null}}'}
        env = {"STUDY_NODE": "/custom/node", "PATH": "/usr/bin:/Users/me/.volta/bin:/opt/x/bin"}
        paths = node.candidates(env, home, "darwin", saved="/saved/node", read=files.get)
        self.assertEqual(paths[:2], ["/custom/node", "/saved/node"])
        self.assertIn("/usr/bin/node", paths)
        self.assertIn("/opt/x/bin/node", paths)
        self.assertNotIn("/Users/me/.volta/bin/node", paths)
        order = [self.index(paths, e) for e in (
            "/usr/bin/node", "/opt/x/bin/node", ".nvm/versions/node/v20.10.0*/bin/node", ".nvm/versions/node/v*/bin/node",
            "/opt/homebrew/bin/node", "/usr/local/bin/node", "/opt/local/bin/node",
            ".volta/tools/image/node/20.11.1/bin/node", ".local/share/fnm/aliases/default/bin/node",
            "Library/Application Support/fnm/aliases/default/bin/node")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(len(paths), len(set(paths)))

    def test_mac_nvm_alias_names_fall_back_to_highest(self):
        files = {"/h/.nvm/alias/default": "lts/*\n"}
        paths = node.candidates({"PATH": ""}, "/h", "linux", read=files.get)
        self.assertEqual([p for p in paths if ".nvm" in p], ["/h/.nvm/versions/node/v*/bin/node"])
        paths = node.candidates({"PATH": "", "NVM_DIR": "/opt/nvm"}, "/h", "linux", read=lambda p: "v22\n" if p == "/opt/nvm/alias/default" else None)
        self.assertEqual([p for p in paths if "nvm" in p], ["/opt/nvm/versions/node/v22*/bin/node", "/opt/nvm/versions/node/v*/bin/node"])

    def test_windows_order(self):
        env = {"PATH": r"C:\Windows\system32;C:\Users\me\AppData\Local\Volta\bin;C:\tools",
               "ProgramFiles": r"C:\Program Files", "ProgramFiles(x86)": r"C:\Program Files (x86)",
               "NVM_SYMLINK": r"C:\nvm\current", "LOCALAPPDATA": r"C:\Users\me\AppData\Local",
               "APPDATA": r"C:\Users\me\AppData\Roaming"}
        read = lambda p: '{"node": {"runtime": "22.3.0"}}' if p.endswith(r"Volta\tools\user\platform.json") else None
        paths = node.candidates(env, r"C:\Users\me", "win32", read=read)
        self.assertTrue(all(p.lower().endswith("node.exe") for p in paths), paths)
        self.assertNotIn(r"C:\Users\me\AppData\Local\Volta\bin\node.exe", paths)
        order = [self.index(paths, e) for e in (
            "C:/Windows/system32/node.exe", "C:/tools/node.exe", "C:/Program Files/nodejs/node.exe",
            "C:/Program Files (x86)/nodejs/node.exe", "C:/nvm/current/node.exe", "C:/nvm4w/nodejs/node.exe",
            "C:/Users/me/AppData/Local/nvm/v*/node.exe", "C:/Users/me/AppData/Roaming/nvm/v*/node.exe",
            "C:/Users/me/AppData/Local/Volta/tools/image/node/22.3.0/node.exe", "C:/Users/me/scoop/apps/nodejs/current/node.exe")]
        self.assertEqual(order, sorted(order))

    def test_windows_nvm_home_and_volta_without_version(self):
        env = {"PATH": "", "NVM_HOME": r"D:\nvm", "LOCALAPPDATA": r"C:\Users\me\AppData\Local"}
        paths = node.candidates(env, r"C:\Users\me", "win32")
        self.assertLess(self.index(paths, "D:/nvm/v*/node.exe"), self.index(paths, "AppData/Local/nvm/v*/node.exe"))
        self.assertIn(r"C:\Users\me\AppData\Local\Volta\tools\image\node\*\node.exe", paths)

    def test_path_entry_with_cmd_shim_yields_only_exe(self):
        tmp = tempfile.mkdtemp(prefix="journey_node_")
        self.addCleanup(shutil.rmtree, tmp, True)
        for name in ("node.cmd", "node.exe"):
            with open(os.path.join(tmp, name), "w") as f:
                f.write("")
            os.chmod(os.path.join(tmp, name), 0o755)
        paths = node.candidates({"PATH": tmp}, tmp, "win32")
        exe = ntpath.join(tmp, "node.exe")
        self.assertIn(exe, paths)
        self.assertFalse(any(p.lower().endswith((".cmd", ".bat")) for p in paths))
        # 두 파일이 다 있는 것처럼 꾸며도 .cmd 는 후보가 아니라서 node.exe 가 골라짐
        fake = FakeRun(b"v20.0.0\n")
        with mock.patch.object(node, "_run", fake):
            with mock.patch.object(node, "runnable", lambda p: p.startswith(tmp) and p.lower().endswith(("node.exe", "node.cmd"))):
                found = node.search(env={"PATH": tmp}, home=tmp, platform="win32")
        self.assertEqual(found, {"path": exe, "version": "20.0.0", "major": 20})

    def test_expand_sorts_versions_high_first(self):
        tmp = tempfile.mkdtemp(prefix="journey_node_")
        self.addCleanup(shutil.rmtree, tmp, True)
        for version in ("v20.10.0", "v9.11.2", "v22.23.2", "v20.9.0"):
            os.makedirs(os.path.join(tmp, version, "bin"))
            with open(os.path.join(tmp, version, "bin", "node"), "w") as f:
                f.write("")
        found = node.expand(os.path.join(tmp, "v*", "bin", "node"))
        self.assertEqual([p.split(os.sep)[-3] for p in found], ["v22.23.2", "v20.10.0", "v20.9.0", "v9.11.2"])
        self.assertEqual(node.expand("/plain/node"), ["/plain/node"])


class FinderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journey_node_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(node.forget)
        node.forget()
        patch = mock.patch.object(node, "MAC_FIXED", ())
        patch.start()
        self.addCleanup(patch.stop)

    def test_inspect_rejects_old_versions(self):
        with mock.patch.object(node, "_run", FakeRun(b"v18.20.4\n")):
            info = node.inspect("/x/node")
        self.assertEqual(info, {"path": "/x/node", "version": "18.20.4", "major": 18, "ok": False})
        with mock.patch.object(node, "_run", FakeRun(b"v20.10.0\n")):
            self.assertTrue(node.inspect("/x/node")["ok"])
        with mock.patch.object(node, "_run", FakeRun(b"Python 3.14.4\n")):
            self.assertIsNone(node.inspect("/x/python"))

    def test_check_explains_rejection(self):
        with self.assertRaises(ValueError) as caught:
            node.check(os.path.join(self.tmp, "missing"))
        self.assertIn("실행할 수 있는 파일이 아닙니다", str(caught.exception))
        fake_node = os.path.join(self.tmp, "node")
        with open(fake_node, "w") as f:
            f.write("")
        os.chmod(fake_node, 0o755)
        with mock.patch.object(node, "_run", FakeRun(b"v18.0.0\n")):
            with self.assertRaises(ValueError) as caught:
                node.check(fake_node)
        self.assertIn("20", str(caught.exception))
        with mock.patch.object(node, "_run", FakeRun(b"v22.1.0\n")):
            self.assertEqual(node.check(fake_node), {"path": fake_node, "version": "22.1.0", "major": 22})

    def test_probe_is_skipped_when_disabled(self):
        fake = FakeRun(b"")
        env = {"PATH": "", "STUDY_NODE_PROBE": "0", "SHELL": "/bin/zsh"}
        with mock.patch.object(node, "_run", fake):
            self.assertIsNone(node.search(probe=True, env=env, home=self.tmp, platform="darwin"))
        self.assertFalse(any("-lc" in args for args, _ in fake.calls))
        with mock.patch.object(node, "_run", fake):
            node.search(probe=False, env={"PATH": "", "SHELL": "/bin/zsh"}, home=self.tmp, platform="darwin")
        self.assertEqual(fake.calls, [])

    def test_probe_uses_login_shell_without_interactive_flag(self):
        fake = FakeRun(b"")
        env = {"PATH": "", "SHELL": "/bin/bash", "TERM": "xterm"}
        with mock.patch.object(node, "_run", fake):
            node.search(probe=True, env=env, home=self.tmp, platform="darwin")
        shell_calls = [(args, options) for args, options in fake.calls if "command -v node" in args]
        self.assertEqual(len(shell_calls), 1)
        args, options = shell_calls[0]
        self.assertEqual(args, ["/bin/bash", "-lc", "command -v node"])
        self.assertNotIn("-i", args)
        self.assertNotIn("-lic", args)
        self.assertEqual(options["env"]["TERM"], "dumb")
        with mock.patch.object(node, "_run", fake):
            node.search(probe=True, env={"PATH": "", "SHELL": "/usr/local/bin/fish"}, home=self.tmp, platform="darwin")
        self.assertEqual(fake.calls[-1][0][0], "/bin/zsh")
        with mock.patch.object(node, "_run", fake):
            node.search(probe=True, env={"PATH": ""}, home=self.tmp, platform="win32")
        self.assertEqual(fake.calls[-1][0][0], "/bin/zsh")  # Windows 에서는 셸에 묻지 않아 마지막 호출이 그대로임

    def test_probe_result_must_be_a_runnable_absolute_path(self):
        fake_node = os.path.join(self.tmp, "node")
        with open(fake_node, "w") as f:
            f.write("")
        os.chmod(fake_node, 0o755)
        with mock.patch.object(node, "_run", FakeRun(("banner line\n%s\n" % fake_node).encode())):
            self.assertEqual(node.shell_probe({"SHELL": "/bin/zsh"}), fake_node)
        with mock.patch.object(node, "_run", FakeRun(b"node\n")):
            self.assertIsNone(node.shell_probe({}))
        with mock.patch.object(node, "_run", FakeRun(b"")):
            self.assertIsNone(node.shell_probe({}))

    def test_find_remembers_until_probe_or_forget(self):
        calls = []

        def fake_search(probe=False, saved=None, env=None, home=None, platform=None):
            calls.append(probe)
            return None

        with mock.patch.object(node, "search", fake_search):
            self.assertIsNone(node.find())
            self.assertIsNone(node.find())
            self.assertEqual(calls, [False])
            self.assertIsNone(node.find(probe=True))
            self.assertEqual(calls, [False, True])
            node.remember({"path": "/x/node", "version": "20.0.0", "major": 20})
            self.assertEqual(node.find()["path"], "/x/node")
            self.assertEqual(calls, [False, True])
            node.forget()
            node.find()
            self.assertEqual(calls, [False, True, False])

    @unittest.skipIf(sys.platform == "win32", "platform=darwin 으로 진짜 임시 경로를 쓰므로 Windows 에서는 건너뜀")
    def test_volta_shim_is_replaced_by_the_image_file(self):
        volta = os.path.join(self.tmp, ".volta")
        image = os.path.join(volta, "tools", "image", "node", "20.10.0", "bin")
        os.makedirs(os.path.join(volta, "bin"))
        os.makedirs(image)
        os.makedirs(os.path.join(volta, "tools", "user"))
        for path in (os.path.join(volta, "bin", "node"), os.path.join(image, "node")):
            with open(path, "w") as f:
                f.write("")
            os.chmod(path, 0o755)
        with open(os.path.join(volta, "tools", "user", "platform.json"), "w") as f:
            f.write('{"node": {"runtime": "20.10.0", "npm": "10.2.3"}}')
        env = {"PATH": os.path.join(volta, "bin"), "STUDY_NODE_PROBE": "0"}
        with mock.patch.object(node, "_run", FakeRun(b"v20.10.0\n")):
            found = node.search(env=env, home=self.tmp, platform="darwin")
        self.assertEqual(found["path"], os.path.join(image, "node"))


if __name__ == "__main__":
    unittest.main()
