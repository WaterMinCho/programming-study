# -*- coding: utf-8 -*-
"""공통 자료의 전체 무결성·고정 시드 샘플·비공개 출력 경계를 확인함."""
import contextlib
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

from learning_server import dataset, input_example, sample, starter


class SampleTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.data = self.root / "dataset"
        starter.write_starter(dataset.synthetic_events(), self.data)

    def test_reproducible_sample_keeps_source_split_vocabulary_and_input_boundaries(self):
        before = {p.relative_to(self.data): p.read_bytes() for p in self.data.rglob("*") if p.is_file()}
        state = random.getstate()
        outputs = [self.root / name for name in ("a.json", "b.json")]
        reports = [sample.write_sample(self.data, "python", "train", 4, 42, 4, path) for path in outputs]
        self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(state, random.getstate())
        stored = json.loads(outputs[0].read_text(encoding="utf-8"))
        rows, vocabulary = input_example.load(self.data, "python", "train")
        ids = stored["batch"]["event_ids"]
        self.assertEqual(4, len(set(ids)))
        self.assertTrue(set(ids) <= {row["event_id"] for row in rows})
        self.assertEqual(vocabulary, stored["vocabulary"])
        chosen = [row for row in rows if row["event_id"] in ids]
        self.assertEqual(input_example.batch(chosen, vocabulary, 4), stored["batch"])
        self.assertEqual(before, {p.relative_to(self.data): p.read_bytes() for p in self.data.rglob("*") if p.is_file()})
        self.assertNotIn("event_ids", json.dumps(reports[0]))
        self.assertNotIn("targets", reports[0])

    def test_check_rejects_a_changed_file_even_outside_the_requested_split(self):
        (self.data / "records/python-test.jsonl").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "해시"):
            sample.write_sample(self.data, "python", "train", 4, 42, 4, self.root / "sample.json")
        self.assertFalse((self.root / "sample.json").exists())

    def test_smoke_detects_current_answer_leaking_into_inputs(self):
        batch = input_example.batch
        def leaking(rows, vocabulary, length):
            value = batch(rows, vocabulary, length)
            value["inputs"]["leaked_target"] = [row["target"] for row in rows]
            return value
        with mock.patch.object(input_example, "batch", side_effect=leaking):
            with self.assertRaisesRegex(ValueError, "정답이 모델 입력"):
                sample.write_sample(self.data, "ai", "train", 4, 42, 4, self.root / "sample.json")
        self.assertFalse((self.root / "sample.json").exists())

    def test_private_output_does_not_overwrite_or_enter_a_git_repository(self):
        path = self.root / "existing.json"
        path.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "덮어쓰지"):
            sample.write_sample(self.data, "python", "train", 1, 42, 4, path)
        self.assertEqual("keep", path.read_text())
        repo = self.root / "fork"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Git 저장소 밖"):
            sample.write_sample(self.data, "python", "train", 1, 42, 4, repo / "out.json")
        self.assertFalse((repo / "out.json").exists())

    def test_real_array_shapes_and_padding_are_checked_before_saving(self):
        batch = input_example.batch
        for failure in ("length", "width", "question-padding", "concept-padding"):
            def broken(rows, vocabulary, length):
                value = batch(rows, vocabulary, length)
                inputs = value["inputs"]
                if failure == "length":
                    inputs["questions"][0].pop()
                elif failure == "width":
                    inputs["concepts"][0][-1].pop()
                elif failure == "question-padding":
                    inputs["questions"][0][-1] = 1
                else:
                    inputs["concepts"][0][-1][0] = 1
                return value
            path = self.root / (failure + ".json")
            with self.subTest(failure=failure), mock.patch.object(input_example, "batch", side_effect=broken):
                with self.assertRaisesRegex(ValueError, "길이|너비|빈 자리"):
                    sample.write_sample(self.data, "python", "train", 8, 42, 32, path)
            self.assertFalse(path.exists())
        report = sample.write_sample(self.data, "python", "train", 8, 42, 1, self.root / "short.json")
        rows, _ = input_example.load(self.data, "python", "train")
        lengths = [len(row["features"]["sequence_history"]) for row in rows]
        self.assertEqual(sum(length == 0 for length in lengths), report["empty_histories"])
        self.assertEqual(sum(length > 1 for length in lengths), report["truncated_histories"])
        self.assertGreater(report["empty_histories"], 0)
        self.assertGreater(report["truncated_histories"], 0)

    def test_batch_identity_targets_and_lengths_match_the_source_rows(self):
        batch = input_example.batch
        for failure in ("history", "identity", "target"):
            def broken(rows, vocabulary, length):
                value = batch(rows, vocabulary, length)
                if failure == "identity":
                    value["event_ids"].reverse()
                elif failure == "target":
                    value["targets"][0] = 1 - value["targets"][0]
                else:
                    inputs = value["inputs"]
                    for i in range(len(rows)):
                        inputs["lengths"][i] = 0
                        for name in ("questions", "courses", "results", "mask"):
                            inputs[name][i] = [0] * length
                        inputs["concepts"][i] = [[0] * len(vocabulary["concepts"]) for _ in range(length)]
                return value
            path = self.root / (failure + ".json")
            with self.subTest(failure=failure), mock.patch.object(input_example, "batch", side_effect=broken):
                with self.assertRaisesRegex(ValueError, "원본과"):
                    sample.write_sample(self.data, "python", "train", 8, 42, 32, path)
            self.assertFalse(path.exists())

    def test_unavailable_track_empty_split_and_oversized_sample_are_explicit(self):
        python_only = self.root / "python-only"
        starter.write_starter([row for row in dataset.synthetic_events() if row["track"] == "python"], python_only)
        with self.assertRaisesRegex(ValueError, "포함 과목: python"):
            sample.write_sample(python_only, "ai", "train", 1, 42, 4, self.root / "sample.json")
        with self.assertRaisesRegex(ValueError, "8건"):
            sample.write_sample(self.data, "python", "train", 9, 42, 4, self.root / "sample.json")
        report, content, digest = sample.inspect(self.data)
        content["python"]["test"] = ([], content["python"]["test"][1])
        with mock.patch.object(sample, "inspect", return_value=(report, content, digest)):
            with self.assertRaisesRegex(ValueError, "0건"):
                sample.write_sample(self.data, "python", "test", 1, 42, 4, self.root / "sample.json")

    def test_cli_prints_shapes_without_private_values(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), mock.patch("sys.argv", ["sample", "sample", "--dataset", str(self.data),
                "--track", "ai", "--size", "4", "--length", "4", "--out", str(self.root / "sample.json")]):
            sample.main()
        result = json.loads(stream.getvalue())
        self.assertEqual("input_checked", result["status"])
        self.assertEqual([4, 4], result["shapes"]["questions"])
        self.assertNotIn("event_ids", stream.getvalue())
        self.assertNotIn("vocabulary", stream.getvalue())
        self.assertNotIn("batch", result)


if __name__ == "__main__":
    unittest.main()
