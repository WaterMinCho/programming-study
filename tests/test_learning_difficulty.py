# -*- coding: utf-8 -*-
"""출제 난이도의 출처·누락·배열과 이전 공통 자료 호환을 확인함."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from learning_server import dataset, input_example, sample, starter


class DifficultyTest(unittest.TestCase):
    def test_only_snapshot_difficulty_is_used_and_education_level_is_ignored(self):
        events = dataset.synthetic_events()
        for event in events:
            event["item"].pop("difficulty")
            event["item"]["level"] = 3 if event["track"] == "python" else 15
        records = dataset.prepare(events)
        self.assertTrue(all(row["difficulty"] == 3 for row in records if row["track"] == "python"))
        self.assertTrue(all(row["difficulty"] is None for row in records if row["track"] == "ai"))
        saved = copy.deepcopy(events)
        dataset.prepare(events)
        self.assertEqual(saved, events)

    def test_unknown_question_can_have_known_difficulty_and_padding_is_unknown(self):
        rows = dataset.prepare(dataset.synthetic_events())[:2]
        rows[0]["difficulty"] = 3
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>", "demo"]}
        result = input_example.batch(rows, vocabulary, length=3)
        inputs = result["inputs"]
        self.assertEqual([1, 1], inputs["query_question"])
        self.assertEqual([3, 2], inputs["query_difficulty"])
        self.assertEqual([True, True], inputs["query_difficulty_known"])
        self.assertEqual([[0, 0, 0], [2, 0, 0]], inputs["difficulties"])
        self.assertEqual([[False, False, False], [True, False, False]], inputs["difficulty_known"])
        changed = copy.deepcopy(rows)
        for row in changed:
            row["target"] = 1 - row["target"]
        self.assertEqual(inputs, input_example.batch(changed, vocabulary, length=3)["inputs"])

    def test_invalid_difficulty_does_not_become_easy_or_missing(self):
        for value in (True, 0, 4, "2", 2.0):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "난이도"):
                dataset.author_difficulty({"difficulty": value})
        self.assertIsNone(dataset.author_difficulty({}))

    def test_version_four_bundle_stays_version_four_and_has_unknown_difficulty(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "data"
            starter.write_starter(dataset.synthetic_events(), root)
            manifest = json.loads((root / "manifest.json").read_bytes())
            records = json.loads((root / "records/manifest.json").read_bytes())
            for name, info in records["files"].items():
                path = root / "records" / name
                rows = [json.loads(line) for line in path.read_bytes().splitlines()]
                for row in rows:
                    row.pop("difficulty")
                    for past in row["features"]["sequence_history"]:
                        past.pop("difficulty")
                path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            records["features_version"] = 4
            (root / "records/manifest.json").write_text(json.dumps(records), encoding="utf-8")
            manifest["features_version"] = 4
            manifest["records_manifest_sha256"] = hashlib.sha256((root / "records/manifest.json").read_bytes()).hexdigest()
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report = sample.write_sample(root, "python", "train", 4, 42, 3, Path(folder) / "sample.json")
            saved = json.loads((Path(folder) / "sample.json").read_bytes())
            self.assertEqual(4, report["features_version"])
            self.assertEqual(4, saved["features_version"])
            self.assertEqual([0] * 4, saved["batch"]["inputs"]["query_difficulty"])
            self.assertFalse(any(saved["batch"]["inputs"]["query_difficulty_known"]))


if __name__ == "__main__":
    unittest.main()
