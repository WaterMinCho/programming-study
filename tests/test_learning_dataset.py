# -*- coding: utf-8 -*-
"""현재 정답의 입력 누출과 풀이 묶음의 분리 누출을 확인함."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
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
            if os.name != "nt":
                self.assertEqual(0o700, output.stat().st_mode & 0o777)
                self.assertTrue(all((p.stat().st_mode & 0o777) == 0o600 for p in output.iterdir()))
            with self.assertRaises(FileExistsError):
                dataset.write_dataset(dataset.synthetic_events(), str(output), synthetic=True)

    def test_future_override_does_not_rewrite_prior_features(self):
        events = dataset.synthetic_events()[:6]
        before = dataset.prepare(events)
        late = copy.deepcopy(events[0])
        late.update(kind="override", sequence=7, at="2026-01-07T10:00:00+00:00")
        after = dataset.prepare(events + [late])
        second = events[1]["event_id"]
        self.assertEqual(next(r["features"] for r in before if r["event_id"] == second),
                         next(r["features"] for r in after if r["event_id"] == second))
        self.assertNotIn(events[0]["event_id"], [r["event_id"] for r in after])

    def test_marked_synthetic_input_preserves_all_24_rows_without_flag(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "dataset"
            manifest = dataset.write_dataset(dataset.synthetic_events(), str(output))
            rows = [json.loads(line) for path in output.glob("*.jsonl") for line in path.read_text().splitlines()]
            self.assertEqual(24, len(rows))
            self.assertIs(manifest["synthetic"], True)
            self.assertEqual("synthetic", manifest["source"])
            self.assertTrue(all(row["synthetic"] is True and row["data_source"] == "synthetic" for row in rows))

    def test_unmarked_and_recorded_sources_are_not_inferred_as_each_other(self):
        for marker, expected in ((None, "unmarked"), (False, "recorded")):
            events = dataset.synthetic_events()
            for row in events:
                row.pop("synthetic")
            if marker is not None:
                events.insert(0, {"kind": "manifest", "synthetic": marker})
            with tempfile.TemporaryDirectory() as root:
                manifest = dataset.write_dataset(events, str(Path(root) / "dataset"))
                self.assertIs(manifest["synthetic"], marker)
                self.assertEqual(expected, manifest["source"])

    def test_mixed_sources_are_rejected_before_output_creation(self):
        for marker in (False, None):
            events = dataset.synthetic_events()
            if marker is None:
                events[0].pop("synthetic")
            else:
                events[0]["synthetic"] = marker
            with tempfile.TemporaryDirectory() as root:
                output = Path(root) / "dataset"
                with self.assertRaises(ValueError):
                    dataset.write_dataset(events, str(output))
                self.assertFalse(output.exists())

    def test_cli_preserves_marked_input_and_synthetic_generator(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "input.jsonl"
            source.write_text("".join(json.dumps(row) + "\n" for row in dataset.synthetic_events()), encoding="utf-8")
            for name, args in (("input", ["--input", str(source)]), ("generated", ["--synthetic"])):
                output = root / name
                result = subprocess.run([sys.executable, "-m", "learning_server.dataset", *args, "--out", str(output)],
                                        cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertIs(manifest["synthetic"], True)
                self.assertEqual("synthetic", manifest["source"])

    def test_mock_answers_use_pre_exam_history_together(self):
        events = dataset.synthetic_events()[:3]
        start = copy.deepcopy(events[0])
        start.update(kind="mock_start", sequence=1)
        start["data"] = {"mock": "m", "try": 1}
        for n, row in enumerate(events[1:], 2):
            row.update(kind="mock_answer", sequence=n)
            row["data"].update({"mock": "m", "try": 1})
        before = dataset.prepare([start] + events[1:])
        events[1]["data"]["result"] = "wrong"
        after = dataset.prepare([start] + events[1:])
        self.assertEqual(before[1]["features"], after[1]["features"])
        self.assertEqual(0, before[1]["features"]["observed_history"]["demo"]["attempts"])
