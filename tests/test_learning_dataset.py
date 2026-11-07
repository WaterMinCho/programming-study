# -*- coding: utf-8 -*-
"""현재 정답의 입력 누출과 풀이 묶음의 분리 누출을 확인함."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from learning_server import dataset


class DatasetTest(unittest.TestCase):
    def test_current_and_future_labels_do_not_change_current_features(self):
        original = dataset.synthetic_events()
        changed = copy.deepcopy(original)
        changed[2]["data"]["result"] = "wrong"
        before = {row["event_id"]: row for row in dataset.prepare(original)}
        after = {row["event_id"]: row for row in dataset.prepare(changed)}
        for row in changed[:3]:
            self.assertEqual(before[row["event_id"]]["features"], after[row["event_id"]]["features"])

    def test_dates_do_not_overlap_and_sessions_are_not_split(self):
        records = dataset.prepare(dataset.synthetic_events())
        records[4]["session"] = records[3]["session"]
        parts = dataset.split(records)
        sets = [{(r["participant"], r["track"], r["session"]) for r in rows} for rows in parts.values()]
        self.assertTrue(all(not sets[i] & sets[j] for i in range(3) for j in range(i + 1, 3)))
        self.assertLess(max(row["at"] for row in parts["train"]), min(row["at"] for row in parts["validation"]))
        self.assertLess(max(row["at"] for row in parts["validation"]), min(row["at"] for row in parts["test"]))

    def test_synthetic_manifest_and_files_are_read_back(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "dataset"
            manifest = dataset.write_dataset(dataset.synthetic_events(), str(output), synthetic=True)
            self.assertTrue(json.loads((output / "manifest.json").read_text())["synthetic"])
            self.assertEqual(6, len(manifest["files"]))
            self.assertTrue(all(item["rows"] for item in manifest["files"].values()))
            with self.assertRaises(FileExistsError):
                dataset.write_dataset(dataset.synthetic_events(), str(output), synthetic=True)
