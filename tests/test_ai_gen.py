# -*- coding: utf-8 -*-
"""aiprep.gen 테스트(설계 3.6, 부록 A.3). Rng 의 고정 시드 열, Retry 와 다시 부르기, fixed 의 반올림 경계, 공용 생성기 등록,
고정 은행 생성기를 oracle 과 300 시드 대조, numpy·torch import 거부를 봄.

실행: python -m unittest tests.test_ai_gen
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import bank, gen, grade  # noqa: E402
from tools import verify_ai  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "ai_bank")


class RngTest(unittest.TestCase):
    def test_fixed_sequence(self):
        """random() 열 위에 만든 값이라 파이썬 판이 바뀌어도 같아야 함(Windows 임시 실행에서 3.10·3.13 도 봄)."""
        r = gen.Rng(12345)
        self.assertEqual([3, 1, 5, 2, 3, 2, 4, 1], [r.int(1, 6) for _ in range(8)])
        r = gen.Rng(12345)
        self.assertEqual("c", r.pick("abcde"))
        self.assertEqual([0, 8, 3], r.sample(range(10), 3))
        self.assertEqual([1, 3, 4, 5, 0, 2], r.shuffle(list(range(6))))
        self.assertTrue(r.chance(0.5))
        self.assertAlmostEqual(0.323832764833, gen.Rng(7).random(), places=12)

    def test_bounds(self):
        r = gen.Rng(1)
        values = {r.int(0, 2) for _ in range(200)}
        self.assertEqual({0, 1, 2}, values)
        with self.assertRaises(ValueError):
            r.int(3, 2)
        with self.assertRaises(ValueError):
            r.pick([])
        with self.assertRaises(ValueError):
            r.sample([1], 2)


class RunTest(unittest.TestCase):
    def test_retry_uses_next_seed_and_gives_up(self):
        seen = []

        def picky(r):
            value = r.int(1, 100)
            seen.append(value)
            if len(seen) < 3:
                raise gen.Retry("다시")
            return gen.blank("값은 ____ 입니다.", [{"answer": [str(value)], "mode": "number"}], "까닭입니다.", {"v": value})

        spec = gen.GenSpec("i99-g01", picky, {})
        made = gen.run(spec, 5)
        self.assertEqual(3, len(seen))
        self.assertEqual(5, made["seed"])
        self.assertEqual(str(seen[-1]), made["blanks"][0]["answer"][0])
        again = []
        spec2 = gen.GenSpec("i99-g01", lambda r: again.append(1) or picky(r), {})
        del seen[:]
        self.assertEqual(made["params"], gen.run(spec2, 5)["params"])

        def never(r):
            raise gen.Retry("늘")
        with self.assertRaises(gen.GenError):
            gen.run(gen.GenSpec("i99-g02", never, {}), 1, tries=5)

    def test_bad_return(self):
        with self.assertRaises(gen.GenError):
            gen.run(gen.GenSpec("i99-g03", lambda r: {"stem": "x"}, {}), 1)

    def test_fixed_boundary(self):
        self.assertEqual("0.14", gen.fixed(0.1428, 2))
        self.assertEqual("0.15", gen.fixed(0.1471, 2))
        for x in (0.1245, 0.1256, 0.1264):
            with self.assertRaises(gen.Retry):
                gen.fixed(x, 2)

    def test_num_and_choice_rows(self):
        self.assertEqual("101,770", gen.num(101770))
        self.assertEqual("1,234.5", gen.num(1234.5))
        made = gen.choice("고르세요.", [("a", True, "맞음"), {"text": "b", "ok": False, "why": "틀림"}], explain="까닭")
        self.assertEqual([{"text": "a", "ok": True, "why": "맞음"}, {"text": "b", "ok": False, "why": "틀림"}], made["options"])


class RegisterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ai_gen_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        study.write_text(path, text)
        return path

    def test_base_and_register_keep_ranges_and_family(self):
        common = self.write("common.py", "from aiprep.gen import base, blank\n\n\n@base('pairs_t')\n"
                                         "def pairs(r, ranges):\n    n = r.int(*ranges['n'])\n"
                                         "    return blank('값 ____', [{'answer': [str(n * 2)], 'mode': 'number'}], '두 배입니다.', {'n': n})\n")
        gen.load_module(common, "t_common")
        path = self.write("gens.py", "from aiprep.gen import register\n\nregister('i98-g01', base='pairs_t', unit='98a', "
                                     "ranges={'n': [3, 5]}, ref=['98차시 슬 p1'], facts=['F98-01'], basis='lecture-example')\n"
                                     "register('i97-g01', base='pairs_t', unit='97a', ranges={'n': [40, 41]}, family='pairs')\n")
        specs = gen.load_module(path, "t_gens")
        self.assertEqual(["i98-g01", "i97-g01"], [s.id for s in specs])
        self.assertEqual("pairs_t", specs[0].meta["family"])
        self.assertEqual("pairs", specs[1].meta["family"])
        self.assertEqual({"n": [3, 5]}, specs[0].meta["ranges"])
        values = {gen.run(specs[0], seed)["params"]["n"] for seed in range(1, 60)}
        self.assertEqual({3, 4, 5}, values)
        self.assertEqual({40, 41}, {gen.run(specs[1], seed)["params"]["n"] for seed in range(1, 60)})
        self.assertFalse(os.path.isdir(os.path.join(self.tmp, "__pycache__")))

    def test_missing_base_and_broken_file(self):
        path = self.write("gens.py", "from aiprep.gen import register\nregister('i98-g02', base='nope_t', unit='98a')\n")
        spec = gen.load_module(path, "t_missing")[0]
        with self.assertRaises(gen.GenError):
            gen.run(spec, 1)
        broken = self.write("broken.py", "def (:\n")
        with self.assertRaises(gen.GenError):
            gen.load_module(broken, "t_broken")


class FixtureOracleTest(unittest.TestCase):
    """고정 은행 i90 의 생성기 둘을 300 시드로 돌려 oracle.py 와 맞춤."""

    def test_generators_match_oracle(self):
        bank.load_common(FIXTURE)
        specs = gen.load_module(os.path.join(FIXTURE, "items", "i90", "gens.py"), "t_i90")
        oracles = gen.load_oracle(os.path.join(FIXTURE, "items", "i90", "oracle.py"))
        self.assertEqual(["i90-g01", "i90-g02"], [s.id for s in specs])
        for spec in specs:
            stems = set()
            for seed in range(1, 301):
                made = gen.run(spec, seed)
                stems.add(made["stem"])
                want = oracles[gen.oracle_name(spec.id)](made["params"])
                if made["kind"] == "blank":
                    blank = made["blanks"][0]
                    self.assertTrue(grade.grade_blank(blank, want[0]), (spec.id, seed, want))
                else:
                    right = [made["options"][n]["text"] for n in grade.right_options(made)]
                    self.assertEqual([want], right, (spec.id, seed))
                    self.assertEqual(4, len({o["text"] for o in made["options"]}))
            self.assertGreaterEqual(len(stems), 20, spec.id)


class ImportTest(unittest.TestCase):
    def test_numpy_and_torch_import_fail(self):
        tmp = tempfile.mkdtemp(prefix="ai_gen_import_")
        self.addCleanup(shutil.rmtree, tmp, True)
        study.write_text(os.path.join(tmp, "gens.py"), "import numpy as np\n")
        study.write_text(os.path.join(tmp, "oracle.py"), "from torch import nn\n")
        out = io.StringIO()
        v = verify_ai.Verifier(verify_ai.parse_args([]), out)
        verify_ai.check_imports(v, "i99", tmp)
        self.assertEqual(2, len(v.failures))
        study.write_text(os.path.join(tmp, "gens.py"), "import math\n# numpy 는 쓰지 않음\n")
        study.write_text(os.path.join(tmp, "oracle.py"), "import fractions\n")
        v = verify_ai.Verifier(verify_ai.parse_args([]), io.StringIO())
        verify_ai.check_imports(v, "i99", tmp)
        self.assertEqual([], v.failures)


if __name__ == "__main__":
    unittest.main()
