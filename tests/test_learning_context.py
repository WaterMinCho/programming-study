# -*- coding: utf-8 -*-
"""전체 학습 그림의 연결 목록과 공개 단원 목록을 대조함."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LearningContextTest(unittest.TestCase):
    def test_every_published_unit_has_a_valid_context(self):
        data = json.loads((ROOT / "ai" / "learning-map.json").read_text(encoding="utf-8"))
        expected = set()
        for path in (ROOT / "ai" / "learn").glob("*/meta.json"):
            expected.update(json.loads(path.read_text(encoding="utf-8"))["sections"])
        self.assertEqual(set(data["units"]), expected)
        for unit, stages in data["units"].items():
            with self.subTest(unit=unit):
                self.assertTrue(stages)
                self.assertEqual(len(stages), len(set(stages)))
                self.assertTrue(set(stages) <= set(data["stages"]))

    def test_gradient_update_and_evaluation_remain_distinct(self):
        data = json.loads((ROOT / "ai" / "learning-map.json").read_text(encoding="utf-8"))
        self.assertEqual(data["units"]["3g"], ["gradient"])
        self.assertEqual(data["units"]["14b"], ["gradient", "update"])
        self.assertEqual(data["units"]["18b"], ["evaluate"])


if __name__ == "__main__":
    unittest.main()
