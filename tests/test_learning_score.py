# -*- coding: utf-8 -*-
"""예측 파일을 같은 구간에서 채점하고 기준선·표준오차·경고를 함께 내는지 확인함."""
import contextlib
import io
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import unittest
from unittest import mock

from learning_server import dataset, input_example, score, starter

REPOSITORY = Path(__file__).resolve().parent.parent


class ScoreTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)
        self.data = self.tmp / "bundle"
        starter.write_starter(dataset.synthetic_events(), self.data)
        self.rows, _ = input_example.load(self.data, "ai", "validation")

    def predictions(self, name="model.csv", rows=None, version="lstm-v1", probability=0.7):
        rows = self.rows if rows is None else rows
        path = self.tmp / name
        lines = ["event_id,probability,model_version"]
        lines += ["%s,%s,%s" % (row["event_id"], probability, version) for row in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_table_has_model_and_six_baselines_without_private_ids(self):
        result = score.evaluate(self.data, "ai", "validation", self.predictions())
        names = [line["name"] for line in result["table"]]
        self.assertEqual(["lstm-v1", "majority", "overall-mean", "per-question", "per-concept", "per-participant",
                          "past-concept-ratio-v1"], names)
        self.assertEqual(len(self.rows), result["cell"]["rows"])
        self.assertEqual(sum(1 - row["target"] for row in self.rows), result["cell"]["wrong"])
        self.assertEqual(len({row["participant"] for row in self.rows}), result["cell"]["participants"])
        self.assertIn("비교 근거로 쓰기 어렵습니다", result["warning"])
        majority = result["table"][1]["metrics"]
        self.assertIsNone(majority["log_loss"]["value"])
        self.assertIsNone(majority["roc_auc"]["value"])
        text = score.render(result) + json.dumps(result, ensure_ascii=False)
        for row in self.rows:
            self.assertNotIn(row["event_id"], text)
            self.assertNotIn(row["participant"], text)
        for metric in ("log_loss", "brier", "roc_auc", "accuracy"):
            self.assertEqual({"value", "se_row", "se_group"}, set(result["table"][0]["metrics"][metric]))

    def test_default_split_is_validation_and_cli_writes_outside_repository(self):
        output = self.tmp / "score.json"
        argv = ["score", "--dataset", str(self.data), "--track", "ai", "--predictions", str(self.predictions()),
                "--out", str(output)]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()) as printed:
            score.main()
        saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("validation", saved["split"])
        self.assertEqual(dataset.FEATURES_VERSION, saved["features_version"])
        self.assertIn("로그 손실", printed.getvalue())
        with mock.patch.object(sys, "argv", argv), self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                score.main()

    def test_mismatched_or_invalid_predictions_are_rejected(self):
        cases = {
            "빠진": self.predictions("missing.csv", rows=self.rows[1:]),
            "채점할 구간에 없는": self.predictions("extra.csv", rows=self.rows + [dict(self.rows[0], event_id="other")]),
            "두 번": self.predictions("twice.csv", rows=self.rows + self.rows[:1]),
            "0 이상 1 이하": self.predictions("range.csv", probability=1.5),
            "유한한": self.predictions("nan.csv", probability="nan"),
        }
        for message, path in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                score.evaluate(self.data, "ai", "validation", path)
        two = self.predictions("two.csv")
        text = two.read_text(encoding="utf-8").replace("lstm-v1", "lstm-v2", 1)
        two.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "model_version"):
            score.evaluate(self.data, "ai", "validation", two)
        with self.assertRaisesRegex(ValueError, "Git 저장소 밖"):
            score.evaluate(self.data, "ai", "validation", REPOSITORY / "predictions.csv")

    def test_jsonl_predictions_are_accepted(self):
        path = self.tmp / "model.jsonl"
        path.write_text("".join(json.dumps({"event_id": row["event_id"], "probability": 0.6, "model_version": "m"}) + "\n"
                                for row in self.rows), encoding="utf-8")
        result = score.evaluate(self.data, "ai", "validation", path)
        self.assertEqual("m", result["table"][0]["name"])

    def test_excel_bom_csv_is_read_and_non_object_jsonl_line_is_explained(self):
        path = self.predictions("excel.csv")
        path.write_bytes(path.read_text(encoding="utf-8").encode("utf-8-sig"))
        result = score.evaluate(self.data, "ai", "validation", path)
        self.assertEqual("lstm-v1", result["table"][0]["name"])
        bad = self.tmp / "list.jsonl"
        bad.write_text("\n[1, 2]\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "2번째 줄"):
            score.evaluate(self.data, "ai", "validation", bad)

    def test_standard_errors_follow_row_and_participant_formulas(self):
        targets = [1, 0, 1, 1, 0, 1]
        probabilities = [0.9, 0.6, 0.6, 0.4, 0.4, 0.7]
        groups = ["a", "a", "b", "b", "c", "c"]
        result = score.measure(targets, probabilities, groups)
        accuracy = result["accuracy"]
        self.assertAlmostEqual(4 / 6, accuracy["value"])
        self.assertAlmostEqual(math.sqrt(4 / 6 * 2 / 6 / 6), accuracy["se_row"])
        self.assertAlmostEqual(1 / 6, accuracy["se_group"])
        squared = [(p - y) ** 2 for y, p in zip(targets, probabilities)]
        self.assertAlmostEqual(statistics.stdev(squared) / math.sqrt(6), result["brier"]["se_row"])
        leave = [statistics.mean(squared[2:]), statistics.mean(squared[:2] + squared[4:]), statistics.mean(squared[:4])]
        center = statistics.mean(leave)
        self.assertAlmostEqual(math.sqrt(2 / 3 * sum((v - center) ** 2 for v in leave)), result["brier"]["se_group"])
        auc = result["roc_auc"]["value"]
        q1, q2 = auc / (2 - auc), 2 * auc ** 2 / (1 + auc)
        expected = math.sqrt((auc * (1 - auc) + 3 * (q1 - auc ** 2) + (q2 - auc ** 2)) / (4 * 2))
        self.assertAlmostEqual(expected, result["roc_auc"]["se_row"])
        single = score.measure(targets, probabilities, ["a"] * 6)
        self.assertIsNone(single["brier"]["se_group"])
        self.assertIsNone(single["roc_auc"]["se_group"])

    def test_warning_needs_fifty_wrong_rows_and_five_participants(self):
        self.assertIn("오답 49행", score.warning(49, 5))
        self.assertIn("가명 4개", score.warning(50, 4))
        self.assertIsNone(score.warning(50, 5))


if __name__ == "__main__":
    unittest.main()
