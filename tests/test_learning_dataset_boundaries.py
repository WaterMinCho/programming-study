# -*- coding: utf-8 -*-
"""문제 반환 시각 누락과 정정 시점에 따른 모델 입력을 확인함."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from learning_server import dataset, input_example, starter
from tests import test_learning_dataset


class DatasetBoundaryTest(unittest.TestCase):
    def test_missing_prediction_time_excludes_label_but_keeps_released_history(self):
        events = dataset.synthetic_events()[:2]
        events[0]["data"].pop("prediction_at")
        original = copy.deepcopy(events)
        exclusions = {}
        rows = dataset.prepare(events, exclusions=exclusions)
        self.assertEqual([events[1]["event_id"]], [row["event_id"] for row in rows])
        self.assertEqual([events[0]["event_id"]],
                         [past["event_id"] for past in rows[0]["features"]["sequence_history"]])
        self.assertEqual({"missing_prediction_time": 1}, exclusions)
        self.assertEqual(original, events)

    def test_unmatched_return_cannot_use_intervening_answer_as_training_input(self):
        shown, answer = test_learning_dataset.DatasetTest().shown_answer()
        answer["item_revision"] = "1" * 64
        other = copy.deepcopy(answer)
        other.update(event_id="intervening", sequence=2, at="2026-01-01T09:30:00+00:00")
        other["data"].update(set="other", prediction_at=shown["at"])
        answer["sequence"] = 3
        exclusions = {}
        rows = dataset.prepare([shown, other, answer], exclusions=exclusions)
        self.assertEqual(["intervening"], [row["event_id"] for row in rows])
        self.assertEqual({"missing_prediction_time": 1}, exclusions)

    def corrected_events(self):
        first, last = dataset.synthetic_events()[:2]
        first["data"]["result"] = "stuck"
        correction = copy.deepcopy(first)
        correction.update(kind="override", event_id="correction", sequence=2,
                          at="2026-01-01T10:30:00+00:00")
        last["sequence"] = 3
        return first, correction, last

    def test_correction_only_changes_features_after_its_timestamp(self):
        first, correction, last = self.corrected_events()
        for query_at, expected in (("2026-01-01T10:15:00+00:00", 1),
                                   (correction["at"], 1),
                                   ("2026-01-01T10:45:00+00:00", 0)):
            with self.subTest(query_at=query_at):
                last["data"]["prediction_at"] = query_at
                original = copy.deepcopy([first, correction, last])
                rows = dataset.prepare(original)
                self.assertEqual([last["event_id"]], [row["event_id"] for row in rows])
                features = rows[0]["features"]
                self.assertEqual(expected, len(features["sequence_history"]))
                aggregate = features["observed_history"]["demo"]
                self.assertEqual(expected, aggregate["attempts"])
                self.assertEqual(0, aggregate["correct"])
                self.assertEqual(1 - expected, aggregate["overrides"])
                self.assertEqual(first["at"] if expected else None, aggregate["last_at"])
                self.assertEqual([first, correction, last], original)

    def test_duplicate_correction_is_counted_once_and_does_not_hide_other_results(self):
        first, correction, last = self.corrected_events()
        other = copy.deepcopy(first)
        other.update(event_id="other", sequence=2)
        other["data"].update(set="other", result="pass")
        correction["sequence"] = 3
        duplicate = copy.deepcopy(correction)
        duplicate.update(event_id="correction-again", sequence=4)
        last["sequence"] = 5
        row = dataset.prepare([first, other, correction, duplicate, last])[-1]
        self.assertEqual(["other"], [past["event_id"] for past in row["features"]["sequence_history"]])
        self.assertEqual({"attempts": 1, "correct": 1, "last_at": other["at"], "overrides": 1},
                         row["features"]["observed_history"]["demo"])

    def test_correction_before_mock_start_is_excluded_from_batch_history(self):
        first, correction, last = self.corrected_events()
        start = copy.deepcopy(last)
        start.update(kind="mock_start", event_id="start", sequence=3,
                     at="2026-01-01T11:00:00+00:00", data={"mock": "m", "try": 1})
        last.update(kind="mock_answer", sequence=4)
        last["data"].update(mock="m", prediction_at=start["at"])
        last["data"]["try"] = 1
        row = dataset.prepare([first, correction, start, last])[-1]
        self.assertEqual([], row["features"]["sequence_history"])
        self.assertEqual(0, row["features"]["observed_history"]["demo"]["attempts"])

    def test_correction_during_mock_keeps_the_start_history_for_all_questions(self):
        first, correction, last = self.corrected_events()
        start = copy.deepcopy(last)
        start.update(kind="mock_start", event_id="start", sequence=2,
                     at="2026-01-01T10:15:00+00:00", data={"mock": "m", "try": 1})
        correction["sequence"] = 3
        last.update(kind="mock_answer", sequence=4)
        last["data"].update(mock="m", prediction_at="2026-01-01T10:45:00+00:00")
        last["data"]["try"] = 1
        row = dataset.prepare([first, start, correction, last])[-1]
        self.assertEqual([first["event_id"]], [past["event_id"] for past in row["features"]["sequence_history"]])
        self.assertEqual({"attempts": 1, "correct": 0, "last_at": first["at"], "overrides": 0},
                         row["features"]["observed_history"]["demo"])

    def test_ambiguous_correction_is_rejected_without_choosing_a_target(self):
        first, correction, last = self.corrected_events()
        duplicate = copy.deepcopy(first)
        duplicate.update(event_id="duplicate-answer", sequence=2)
        correction["sequence"], last["sequence"] = 3, 4
        with self.assertRaisesRegex(ValueError, "정정 대상"):
            dataset.prepare([first, duplicate, correction, last])

    def test_unknown_time_last_answer_still_delays_release_of_the_whole_batch(self):
        events = [copy.deepcopy(dataset.synthetic_events()[0]) for _ in range(4)]
        for n, row in enumerate(events):
            row.update(sequence=n + 1, event_id="e%d" % n, at="2026-01-01T10:%02d:00+00:00" % n)
        events[0].update(kind="batch_start", data={"batch": "b", "set": "r"})
        for n in (1, 2):
            events[n]["data"].update(batch="b", set="r", card="q%d" % n, prediction_at=events[0]["at"])
        events[2]["data"].pop("prediction_at")
        events[3]["data"].update(set="later", prediction_at="2026-01-01T10:01:30+00:00")
        self.assertEqual([], dataset.prepare(events)[-1]["features"]["sequence_history"])
        events[3]["data"]["prediction_at"] = events[3]["at"]
        self.assertEqual(["e1", "e2"],
                         [past["event_id"] for past in dataset.prepare(events)[-1]["features"]["sequence_history"]])

    def test_track_with_only_unknown_prediction_times_is_counted_as_excluded(self):
        events = dataset.synthetic_events()
        for row in events:
            if row["track"] == "ai":
                row["data"].pop("prediction_at")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "starter"
            manifest = starter.write_starter(events, root)
            records = json.loads((root / "records/manifest.json").read_text())
            self.assertEqual(["python"], manifest["tracks"])
            self.assertEqual({"missing_prediction_time": 12}, records["excluded_rows"])
            self.assertEqual(24, records["eligible_rows"] + sum(records["excluded_rows"].values()))
            self.assertEqual(records["eligible_rows"], records["excluded_split_rows"] +
                             sum(info["rows"] for info in records["files"].values()))

    def test_version_six_bundle_remains_readable_without_relabelling(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "starter"
            starter.write_starter(dataset.synthetic_events(), root)
            record_path = root / "records/manifest.json"
            records = json.loads(record_path.read_text())
            self.assertEqual({"missing_prediction_time": 0}, records["excluded_rows"])
            records["features_version"] = 6
            records.pop("excluded_rows")
            record_path.write_text(json.dumps(records))
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["features_version"] = 6
            manifest["records_manifest_sha256"] = hashlib.sha256(record_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            before = {path: path.read_bytes() for path in (record_path, manifest_path)}
            rows, _ = input_example.load(root, "ai", "train")
            self.assertEqual(8, len(rows))
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_manifest_records_missing_time_exclusion_and_input_still_loads(self):
        events = dataset.synthetic_events()
        events[0]["data"].pop("prediction_at")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "starter"
            manifest = starter.write_starter(events, root)
            records = json.loads((root / "records/manifest.json").read_text())
            # 문항 번호표를 문항 id 단위로 바꾸면서 자료 버전을 8 로 올림(2026-11-17)
            self.assertEqual(dataset.FEATURES_VERSION, manifest["features_version"])
            self.assertEqual(23, records["eligible_rows"])
            self.assertEqual({"missing_prediction_time": 1}, records["excluded_rows"])
            rows, vocabulary = input_example.load(root, "ai", "train")
            result = input_example.batch(rows, vocabulary)
            self.assertEqual(len(rows), len(result["targets"]))
            self.assertTrue(all(row["prediction_at"] for row in rows))
