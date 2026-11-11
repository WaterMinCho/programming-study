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
    def shown_answer(self, mock=False):
        answer = copy.deepcopy(dataset.synthetic_events()[0])
        answer["sequence"] = 2
        answer["data"].pop("prediction_at")
        answer["data"].update(position=0, course="intro")
        if mock:
            answer["kind"] = "mock_answer"
            answer["data"].update(mock="exam", try_=1)
            answer["data"]["try"] = answer["data"].pop("try_")
        shown = copy.deepcopy(answer)
        shown.update(kind="mock_question_returned" if mock else "question_returned",
                     event_id="returned", sequence=1, at="2026-01-01T09:00:00+00:00")
        shown["data"].pop("result")
        return shown, answer

    def test_ai_return_time_is_linked_without_rewriting_original_events(self):
        for mock in (False, True):
            shown, answer = self.shown_answer(mock)
            original = copy.deepcopy([shown, answer])
            row = dataset.prepare([shown, answer])[0]
            self.assertEqual(shown["at"], row["prediction_at"])
            self.assertEqual(shown["kind"] + ".at", row["prediction_source"])
            self.assertEqual(shown["event_id"], row["prediction_event"])
            self.assertEqual(original, [shown, answer])

    def test_ai_return_join_rejects_mismatch_ambiguity_and_collection_restart(self):
        for field, value in (("item_revision", "1" * 64), ("position", 1), ("course", "app")):
            shown, answer = self.shown_answer()
            (shown if field == "item_revision" else shown["data"])[field] = value
            self.assertIsNone(dataset.prepare([shown, answer])[0]["prediction_at"])
        for kind in ("withdraw", "consent", "question_returned"):
            shown, answer = self.shown_answer()
            middle = copy.deepcopy(shown)
            middle.update(kind=kind, event_id="middle", sequence=2)
            answer["sequence"] = 3
            self.assertIsNone(dataset.prepare([shown, middle, answer])[0]["prediction_at"])
        shown, answer = self.shown_answer()
        shown["data"].pop("position")
        self.assertIsNone(dataset.prepare([shown, answer])[0]["prediction_at"])
        self.assertIsNone(dataset.prepare([answer])[0]["prediction_at"])

    def test_ai_return_cutoff_excludes_results_released_while_question_was_open(self):
        shown, answer = self.shown_answer()
        other = copy.deepcopy(answer)
        other.update(event_id="other", sequence=2, at="2026-01-01T09:30:00+00:00")
        other["data"]["set"] = "another"
        answer["sequence"] = 3
        row = dataset.prepare([shown, other, answer])[-1]
        self.assertEqual([], row["features"]["sequence_history"])
        self.assertEqual(0, row["features"]["observed_history"]["demo"]["attempts"])

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
