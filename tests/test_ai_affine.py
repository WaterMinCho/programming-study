# -*- coding: utf-8 -*-
"""수식 블록의 입력 거부·그림 순서·서명 범위를 확인함."""
import json
from pathlib import Path
import tempfile
import unittest

from aiprep import bank, gen, grade
from tools import verify_web

ROOT = Path(__file__).resolve().parents[1]


def formula_data():
    page = (ROOT / "ai/learn/al02/page.md").read_text(encoding="utf-8")
    return json.loads(page.split("```ai-formula\n", 1)[1].split("\n```", 1)[0])


class FormulaParserTest(unittest.TestCase):
    def test_strict_block_and_nested_figure(self):
        data = formula_data()
        text = "```ai-formula\n" + json.dumps(data, ensure_ascii=False) + "\n```"
        block, = bank.parse_blocks(text.splitlines(), "/note")
        self.assertNotIn("error", block)
        self.assertEqual("/note/assets/a2d-4.gif", block["figure"]["path"])
        found, = verify_web.figure_blocks(text)
        self.assertEqual([2200] * 4, found["frames"])
        self.assertEqual("assets/a2d-4.gif", found["file"])
        self.assertFalse(any(b["kind"] == "text" for b in bank.parse_blocks(text.splitlines())))

    def test_rejects_unknown_fields_paths_and_broken_json_without_showing_source(self):
        changes = [lambda d: d.update(answer="hidden"), lambda d: d.pop("output"),
                   lambda d: d.update(operation="```python\nsecret"),
                   lambda d: d["figure"].update(file="assets/../private.png"),
                   lambda d: d["figure"]["frames"][0].update(ms=3000),
                   lambda d: d["figure"].update(frames=[]), lambda d: d.update(input=[])]
        for change in changes:
            data = formula_data()
            change(data)
            block = bank._formula_block(json.dumps(data))
            self.assertEqual({"kind", "error"}, set(block))
        self.assertIn("error", bank._formula_block("{"))

    def test_nested_figure_keeps_document_order_with_either_fence(self):
        for fence in ("```", "~~~", "``` ", "~~~ "):
            main = "```figure\n파일: assets/a2d-1.gif\n```\n"
            nested = fence + "ai-formula\n" + json.dumps(formula_data()) + "\n" + fence
            last = "\n```figure\n파일: assets/a2d-2.png\n```\n"
            self.assertEqual(["assets/a2d-1.gif", "assets/a2d-4.gif", "assets/a2d-2.png"],
                             [b["file"] for b in verify_web.figure_blocks(main + nested + last)])

    def test_signature_covers_formula_text_and_asset_without_signing(self):
        folder = str(ROOT / "ai/learn/al02")
        files = verify_web.review_files("page", {"dir": folder}, {})
        self.assertIn("page.md", files)
        self.assertIn("assets/a2d-4.gif", files)
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "page.md"
            page.write_text((ROOT / "ai/learn/al02/page.md").read_text(encoding="utf-8"), encoding="utf-8")
            before = verify_web.review_files("page", {"dir": temp}, {})
            page.write_text(page.read_text(encoding="utf-8").replace(formula_data()["a"], "6"), encoding="utf-8")
            after = verify_web.review_files("page", {"dir": temp}, {})
            self.assertNotEqual(before["page.md"], after["page.md"])


class AffineGeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, = gen.load_module(str(ROOT / "ai/items/a02/gens.py"))
        cls.oracle = staticmethod(gen.load_oracle(str(ROOT / "ai/items/a02/oracle.py"))["a02_g01"])

    def test_300_seeds_keep_one_family_and_match_independent_oracle(self):
        stems, directions, zero, negative = set(), set(), False, False
        for seed in range(300):
            item = gen.run(self.spec, seed)
            params = item["params"]
            self.assertEqual({"point", "translation", "direction"}, set(params))
            got = [b["answer"][0] for b in item["blanks"]]
            self.assertEqual(self.oracle(params), got)
            self.assertEqual(item, gen.run(self.spec, seed))
            self.assertEqual(2, item["stem"].count("____"))
            for b, value in zip(item["blanks"], got):
                self.assertEqual(grade.norm("number", value, b), grade.norm("number", value.replace("-", "−"), b))
            stems.add(item["stem"])
            directions.add(params["direction"])
            zero |= 0 in params["translation"]
            negative |= any(int(x) < 0 for x in got)
        self.assertGreaterEqual(len(stems), 20)
        self.assertEqual(2, len(directions))
        self.assertTrue(zero and negative)
        self.assertEqual(("affine-coordinate-direction", 2, 2, "affine-translation-1"),
                         tuple(self.spec.meta[k] for k in ("family", "level", "author_difficulty", "template_revision")))

    def test_explicit_origin_zero_negative_asymmetry_and_boundaries(self):
        examples = [((2, 1), (3, 2), True, (5, 3)), ((2, 1), (-3, 2), True, (-1, 3)),
                    ((0, 0), (0, 0), True, (0, 0)), ((0, 0), (0, 0), False, (0, 0)),
                    ((5, 3), (3, 2), False, (2, 1)), ((-1, 3), (-3, 2), False, (2, 1)),
                    ((1, -2), (4, -3), True, (5, -5)), ((-8, 8), (-4, 4), True, (-12, 12)),
                    ((8, -8), (-4, 4), False, (12, -12)), ((4, 0), (1, 0), True, (5, 0))]
        for point, shift, forward, expected in examples:
            class Fixed:
                values = iter((*point, *shift))
                def int(self, lo, hi):
                    return next(self.values)
                def pick(self, options):
                    return options[0 if forward else 1]
            item = self.spec.fn(Fixed())
            got = [b["answer"][0] for b in item["blanks"]]
            self.assertEqual(list(map(str, expected)), got)
            self.assertEqual(got, self.oracle(item["params"]))

    def test_oracle_roundtrip_and_leaked_target_rejected(self):
        for point, shift in [((-2, 5), (4, -3)), ((0, 0), (0, 0)), ((8, -8), (-4, 4))]:
            params = dict(point=point, translation=shift, direction="source_to_destination")
            dest = list(map(int, self.oracle(params)))
            self.assertEqual(list(map(str, point)), self.oracle(dict(params, point=dest, direction="destination_to_source")))
            with self.assertRaises(ValueError):
                self.oracle(dict(params, target=dest))
        with self.assertRaises(ValueError):
            self.oracle(dict(point=[True, 0], translation=[1, 0], direction="source_to_destination"))

    def test_published_affine_declares_only_visible_inputs(self):
        from learning_data import collection
        spec, = bank.load_items({"id": "a02"}, str(ROOT / "ai"))["gens"]
        item = gen.run(spec, 9)
        item["_generation"] = bank.generation_source(spec)
        observed = collection.question(item, card=spec.id)["content"]["generation"]
        self.assertEqual("declared", observed["params_status"])
        self.assertEqual(item["params"], observed["params"])
        self.assertEqual("affine-translation-1", observed["template_revision"])
        self.assertEqual({"point", "translation", "direction"}, set(observed["params"]))
