# -*- coding: utf-8 -*-
"""예측 파일을 같은 구간에서 채점하고 기준선·표준오차·경고를 함께 내는지 확인함."""
import contextlib
import io
import json
import math
from datetime import date
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

    def test_validation_reads_only_the_selected_training_and_validation_records(self):
        ids = [row["event_id"] for row in self.rows]
        with mock.patch.object(input_example, "load", wraps=input_example.load) as load:
            result, run_dir = score.score_validation(
                dataset_path=self.data, track="ai", event_ids=ids, probabilities=[0.7] * len(ids),
                model_name="example", output_root=self.tmp / "scores",
            )
        self.assertEqual(load.call_args_list, [
            mock.call(self.data.resolve(), "ai", "train"),
            mock.call(self.data.resolve(), "ai", "validation"),
        ])
        self.assertTrue(result["synthetic"])
        self.assertEqual(result["split"], "validation")
        self.assertEqual(run_dir.name, "example-v1")

    def test_default_output_uses_the_repository_results_folder_and_run_date(self):
        checkout = (self.tmp / "checkout").resolve()
        checkout.mkdir()
        (checkout / ".git").mkdir()
        results = checkout / ".local" / "validation-results"
        ids = [row["event_id"] for row in self.rows]
        args = dict(
            dataset_path=self.data, track="ai", event_ids=ids, probabilities=[0.7] * len(ids),
            model_name="example",
        )
        with mock.patch.object(score, "VALIDATION_RESULTS", results), mock.patch.object(score, "date") as clock:
            clock.today.return_value = date(2026, 11, 25)
            first, run1 = score.score_validation(**args)
            second, run2 = score.score_validation(**args)
            clock.today.return_value = date(2026, 11, 26)
            third, run3 = score.score_validation(**args)
            with self.assertRaisesRegex(ValueError, "저장소 밖"):
                score.score_validation(**args, output_root=checkout / "not-results")
        self.assertEqual(run1, results / "2026-11-25" / "example-2026-11-25-v1")
        self.assertEqual(run2, results / "2026-11-25" / "example-2026-11-25-v2")
        self.assertEqual(run3, results / "2026-11-26" / "example-2026-11-26-v1")
        for result, run_dir in ((first, run1), (second, run2), (third, run3)):
            self.assertEqual(json.loads((run_dir / "score.json").read_text()), result)
            self.assertTrue((run_dir / "predictions.csv").is_file())

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

    def scored(self, synthetic, names, split="validation", train=None):
        """합성 자료의 synthetic 표시와 구간 행의 가명을 바꿔 채점함. train 을 주면 학습 구간 행에 그 가명을 돌려 붙임.
        결과, 화면 출력, JSON 문자열을 돌려줌."""
        inspect = score.sample.inspect

        def changed(folder):
            report, content, digest = inspect(folder)
            for index, row in enumerate(content["ai"][split][0] if names else ()):
                row["participant"] = names[index % len(names)]
            for index, row in enumerate(content["ai"]["train"][0] if train else ()):
                row["participant"] = train[index % len(train)]
            return dict(report, synthetic=synthetic), content, digest

        rows, _ = input_example.load(self.data, "ai", split)
        with mock.patch.object(score.sample, "inspect", changed):
            result = score.evaluate(self.data, "ai", split, self.predictions(split + ".csv", rows=rows))
        return result, score.render(result), json.dumps(result, ensure_ascii=False)

    def test_real_data_hides_one_or_two_participants(self):
        shown = []
        for names in (["p1"], ["p1", "p2"]):
            with self.subTest(people=len(names)):
                result, text, saved = self.scored(False, names)
                first = text.splitlines()[0]
                last = next(line for line in text.splitlines() if line.startswith("이 구간은"))
                self.assertIn("가명 3개 미만,", first)
                self.assertEqual("이 구간은 오답 1행, 가명 3개 미만이라 모델 비교 근거로 쓰기 어렵습니다.", last)
                self.assertEqual("3개 미만", result["cell"]["participants"])
                self.assertEqual(result["warning"], last)
                for count in ("가명 1개", "가명 2개", '"participants": 1', '"participants": 2'):
                    self.assertNotIn(count, text + saved)
                for line in result["table"]:
                    for value in line["metrics"].values():
                        self.assertIsNone(value["se_group"])
                person = [line for line in text.splitlines() if line.startswith("per-participant ")]
                self.assertEqual(["per-participant | - | - | - | -"], person)
                shown.append((first.split(",")[2], last, result["cell"]["participants"], person,
                              [[value["se_group"] for value in line["metrics"].values()] for line in result["table"]]))
        self.assertEqual(shown[0], shown[1])
        # synthetic 값이 True 가 아니면 문자열 "false" 처럼 자료형이 어긋나도 가명 수를 가림
        self.assertEqual("3개 미만", self.scored("false", ["p1", "p2"])[0]["cell"]["participants"])

    def test_masked_bucket_hides_per_participant_baseline(self):
        # 학습 구간에서 두 가명의 정답 비율이 다르면 per-participant 값은 가명이 1개일 때만 모두 같아서, 값만 보고 가명이 1개인지 2개인지 알 수 있음
        names = ["p1", "p2", "p2"]
        rows = input_example.load(self.data, "ai", "train")[0]
        ratio = {name: statistics.mean(row["target"] for index, row in enumerate(rows) if names[index % 3] == name)
                 for name in ("p1", "p2")}
        self.assertNotEqual(ratio["p1"], ratio["p2"])
        result, _, _ = self.scored(True, ["p1", "p2"], train=names)
        person = result["table"][5]
        self.assertEqual("per-participant", person["name"])
        self.assertIsNotNone(person["metrics"]["brier"]["value"])
        shown = []
        for people in (["p1"], ["p1", "p2"]):
            result, text, _ = self.scored(False, people, train=names)
            person = result["table"][5]
            self.assertEqual("per-participant", person["name"])
            for value in person["metrics"].values():
                self.assertEqual({"value": None, "se_row": None, "se_group": None}, value)
            shown.append([line for line in text.splitlines() if line.startswith("per-participant ")])
        self.assertEqual([["per-participant | - | - | - | -"]] * 2, shown)

    def test_synthetic_or_three_participants_keep_exact_count(self):
        result, text, _ = self.scored(True, None)
        self.assertTrue(text.startswith("ai validation 구간: 2행, 오답 1행, 가명 2개, 끼운 변형 0행 "))
        self.assertEqual("이 구간은 오답 1행, 가명 2개라 모델 비교 근거로 쓰기 어렵습니다.", result["warning"])
        self.assertEqual(2, result["cell"]["participants"])
        self.assertIsNotNone(result["table"][0]["metrics"]["brier"]["se_group"])
        plain = score.evaluate(self.data, "ai", "validation", self.predictions())
        self.assertEqual(score.render(plain), text)
        result, text, _ = self.scored(True, ["p1"])
        self.assertIn("가명 1개,", text.splitlines()[0])
        self.assertIn("가명 1개라", result["warning"])
        result, text, saved = self.scored(False, ["p1", "p2", "p3"], split="train")
        self.assertIn("가명 3개,", text.splitlines()[0])
        self.assertIn("가명 3개라", result["warning"])
        self.assertIn('"participants": 3', saved)
        self.assertIsNotNone(result["table"][0]["metrics"]["brier"]["se_group"])


if __name__ == "__main__":
    unittest.main()
