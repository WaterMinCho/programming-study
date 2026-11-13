# -*- coding: utf-8 -*-
"""수식 블록의 입력 거부·그림 순서·서명 범위를 확인함."""
import json
from pathlib import Path
import tempfile
import unittest

from aiprep import bank
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
