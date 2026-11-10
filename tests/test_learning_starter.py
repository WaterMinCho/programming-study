# -*- coding: utf-8 -*-
"""기존 기록의 누락·시각 가정과 공통 입력의 미래 정보 배제를 확인함."""
import copy
import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from learning_server import dataset, input_example, legacy, starter


class StarterTest(unittest.TestCase):
    def test_same_batch_answers_cannot_use_each_others_labels(self):
        events = dataset.synthetic_events()[:3]
        start = copy.deepcopy(events[0])
        start.update(kind="batch_start", sequence=1, data={"batch": "b", "set": "r"})
        for n, row in enumerate(events[1:], 2):
            row["sequence"] = n
            row["data"]["batch"] = "b"
        before = dataset.prepare([start] + events[1:])
        events[1]["data"]["result"] = "wrong"
        after = dataset.prepare([start] + events[1:])
        self.assertEqual(before[1]["features"], after[1]["features"])
        self.assertEqual([], before[1]["features"]["sequence_history"])

    def test_query_cutoff_excludes_results_released_after_problem_opened(self):
        events = dataset.synthetic_events()[:3]
        events[2]["data"]["prediction_at"] = events[1]["at"]
        row = dataset.prepare(events)[-1]
        self.assertEqual([events[0]["event_id"]], [past["event_id"] for past in row["features"]["sequence_history"]])
        self.assertEqual(1, row["features"]["observed_history"]["demo"]["attempts"])

    def test_query_aggregate_keeps_older_concepts_beyond_model_history_limit(self):
        template = dataset.synthetic_events()[0]
        events = []
        for n in range(132):
            row = copy.deepcopy(template)
            at = (datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(minutes=n)).isoformat()
            row.update(sequence=n+1, event_id="event-%d" % n, at=at)
            row["item"]["tags"] = ["old"] if n in (0, 131) else ["other"]
            row["data"].update(set="s%d" % n, prediction_at=at)
            events.append(row)
        row = dataset.prepare(events)[-1]
        self.assertEqual(128, len(row["features"]["sequence_history"]))
        self.assertEqual(1, row["features"]["observed_history"]["old"]["attempts"])
        self.assertEqual(events[0]["at"], row["features"]["observed_history"]["old"]["last_at"])
        events[-1]["data"]["prediction_at"] = events[2]["at"]
        old_query = dataset.prepare(events)[-1]
        self.assertEqual(["event-0", "event-1"], [past["event_id"] for past in old_query["features"]["sequence_history"]])

    def test_query_cutoff_counts_only_already_revealed_overrides(self):
        events = dataset.synthetic_events()[:3]
        override = copy.deepcopy(events[0])
        override.update(kind="override", sequence=3, at=events[1]["at"])
        events[2]["sequence"] = 4
        events[2]["data"]["prediction_at"] = events[2]["at"]
        row = dataset.prepare(events[:2] + [override, events[2]])[-1]
        self.assertEqual(1, row["features"]["observed_history"]["demo"]["overrides"])
        events[2]["data"]["prediction_at"] = override["at"]
        row = dataset.prepare(events[:2] + [override, events[2]])[-1]
        self.assertEqual(0, row["features"]["observed_history"]["demo"]["overrides"])

    def test_batch_labels_are_available_only_after_whole_batch_is_released(self):
        events = [copy.deepcopy(dataset.synthetic_events()[0]) for _ in range(5)]
        for n, row in enumerate(events):
            row.update(sequence=n+1, event_id="event-%d" % n, at="2026-01-01T10:%02d:00+00:00" % n)
        events[0].update(kind="batch_start", data={"batch": "b", "set": "r"})
        for row in (events[1], events[3]):
            row["data"].update(batch="b", set="r", prediction_at=events[0]["at"])
        events[2]["data"].update(set="other", prediction_at=events[2]["at"])
        events[4]["data"].update(set="after", prediction_at=events[2]["at"])
        rows = dataset.prepare(events)
        self.assertEqual(0, rows[-1]["features"]["observed_history"]["demo"]["attempts"])
        self.assertEqual([], rows[-1]["features"]["sequence_history"])
        events[-1]["data"]["prediction_at"] = events[-1]["at"]
        row = dataset.prepare(events)[-1]
        self.assertEqual(3, row["features"]["observed_history"]["demo"]["attempts"])
        self.assertEqual(events[3]["at"], row["features"]["observed_history"]["demo"]["last_at"])

    def test_old_feature_bundle_is_rejected_even_when_its_hashes_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "starter"
            starter.write_starter(dataset.synthetic_events(), root)
            record_path = root / "records/manifest.json"
            records = json.loads(record_path.read_text())
            records.pop("features_version")
            record_path.write_text(json.dumps(records), encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest.pop("features_version")
            manifest["records_manifest_sha256"] = hashlib.sha256(record_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "이전 이력 집계"):
                input_example.load(root, "python", "train")

    def test_shared_files_roundtrip_unknown_tokens_padding_and_tamper(self):
        events = dataset.synthetic_events()
        for row in events:
            if row["at"].startswith("2026-01-06"):
                row["item"]["card"] = "unseen-test-only"
                row["item"]["tags"] = ["unseen-concept"]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "starter"
            starter.write_starter(events, root)
            train, vocabulary = input_example.load(root, "python", "train")
            test, _ = input_example.load(root, "python", "test")
            first = input_example.batch(train[:1], vocabulary, length=4)
            self.assertEqual([0], first["inputs"]["lengths"])
            self.assertEqual([[False]*4], first["inputs"]["mask"])
            self.assertEqual([1], input_example.batch(test[:1], vocabulary)["inputs"]["query_question"])
            self.assertNotIn("unseen-concept", vocabulary["concepts"])
            changed = copy.deepcopy(train[:1])
            changed[0]["target"] = 1 - changed[0]["target"]
            self.assertEqual(first["inputs"], input_example.batch(changed, vocabulary, length=4)["inputs"])
            (root / "records/python-train.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                input_example.load(root, "python", "train")

    def test_missing_query_time_is_not_a_zero_day_observation(self):
        events = dataset.synthetic_events()[:3]
        for row in events:
            row["data"].pop("prediction_at")
        rows = dataset.prepare(events)
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>", "demo"]}
        result = input_example.batch(rows, vocabulary)
        self.assertFalse(any(any(values) for values in result["inputs"]["query_gap_known"]))

    def test_evaluation_query_cannot_precede_training_result_availability(self):
        records = dataset.prepare(dataset.synthetic_events())
        validation = dataset.split(records)["validation"]
        bad_id = validation[0]["event_id"]
        next(row for row in records if row["event_id"] == bad_id)["prediction_at"] = "2026-01-01T00:00:00+00:00"
        parts = dataset.split(records)
        self.assertNotIn(bad_id, [row["event_id"] for row in parts["validation"]])

    def test_legacy_keeps_unknown_revision_and_never_copies_identity_or_answers(self):
        profile = {"user": "private-person", "rounds": [{"id":"r1", "created":"2026-01-01T09:00:00"}],
                   "attempts":[{"round":"r1", "item":"q", "try":1, "ok":True, "at":"2026-01-01T10:00:00"},
                               {"round":"r1", "item":"q", "try":2, "ok":False, "at":"2026-01-02T10:00:00"}]}
        catalog = {"q":{"unit":"s01", "tags":["loops"], "kind":"quiz", "type":"output"}}
        original = copy.deepcopy(profile)
        events = legacy.profile_events(profile, catalog, "+09:00")
        rows = dataset.prepare(events)
        self.assertEqual(original, profile)
        self.assertEqual(1, len(rows))
        self.assertIsNone(rows[0]["question_revision"])
        self.assertEqual("+09:00", rows[0]["provenance"]["timezone_assumption"])
        self.assertNotIn("private-person", json.dumps(events))
        self.assertEqual("2026-01-01T00:00:00+00:00", rows[0]["prediction_at"])

    def test_baseline_metrics_use_known_answers_and_handle_single_class(self):
        self.assertEqual(1, starter.metrics([0,1], [0.1,0.9])["roc_auc"])
        self.assertEqual(0.5, starter.metrics([0,1], [0.5,0.5])["roc_auc"])
        self.assertAlmostEqual(0.01, starter.metrics([0,1], [0.1,0.9])["brier"])
        self.assertIsNone(starter.metrics([1,1], [0.5,0.5])["roc_auc"])
