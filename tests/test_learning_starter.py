# -*- coding: utf-8 -*-
"""기존 기록의 누락·시각 가정과 공통 입력의 미래 정보 배제를 확인함."""
import copy
import datetime
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from learning_server import dataset, input_example, legacy, starter


MOCK_CARDS = {"m4": (("m4-01", "i01", "intro"), ("m4-32", "a03", "app")),
              "m11": (("m11-01", "i01", "intro"), ("m11-25", "i09", "intro"), ("m11-41", "a01", "app"))}


def mixed_mock_events():
    """두 사람이 홀수 날에 m4, 짝수 날에 m11 을 푼 합성 수집 기록. 둘째 날 m11 의 빈칸은 비우고 코드 작성은 채점하지 못함."""
    rows = []
    for person in range(2):
        participant = "synthetic-person-%d" % person
        sequence = 0
        for day in range(1, 7):
            mid, attempt = ("m4" if day % 2 else "m11"), (day + 1) // 2
            at = "2026-01-%02dT10:%02d:00+00:00"

            def add(kind, minute, data, card=None):
                nonlocal sequence
                sequence += 1
                row = {"participant": participant, "track": "ai", "sequence": sequence, "synthetic": True,
                       "event_id": "%s-%d" % (participant, sequence), "at": at % (day, minute), "kind": kind,
                       "data": dict(data, mock=mid, **{"try": attempt})}
                if card:
                    cid, lesson, course = card
                    row["item_revision"] = hashlib.sha256(cid.encode()).hexdigest()
                    row["item"] = {"card": cid, "lesson": lesson, "course": course, "tags": ["concept-" + lesson], "difficulty": 2}
                    row["data"].update(card=cid, course=course)
                rows.append(row)

            add("mock_start", 0, {"course": "intro"})
            for position, card in enumerate(MOCK_CARDS[mid]):
                add("mock_question_returned", 1 + position, {"position": position}, card)
            for position, card in enumerate(MOCK_CARDS[mid]):
                result = "pass" if (person + day + position) % 2 else "stuck"
                if day == 2 and card[0] == "m11-25":
                    result = "blank"
                elif day == 2 and card[0] == "m11-41":
                    result = "ungraded"
                elif card[0] == "m11-41":
                    result = "pass" if person == 0 else "stuck"
                add("mock_answer", 30 + position, {"position": position, "result": result}, card)
    return rows


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
        for row in (events[1], events[2], events[4]):
            row["item"]["tags"] = ["demo", "earlier"]
        events[2]["data"].update(set="other", prediction_at=events[2]["at"])
        events[4]["data"].update(set="after", prediction_at=events[2]["at"])
        rows = dataset.prepare(events)
        self.assertEqual(0, rows[-1]["features"]["observed_history"]["demo"]["attempts"])
        self.assertEqual([], rows[-1]["features"]["sequence_history"])
        events[-1]["data"]["prediction_at"] = events[-1]["at"]
        row = dataset.prepare(events)[-1]
        self.assertEqual(3, row["features"]["observed_history"]["demo"]["attempts"])
        self.assertEqual(events[3]["at"], row["features"]["observed_history"]["demo"]["last_at"])
        self.assertEqual(events[2]["at"], row["features"]["observed_history"]["earlier"]["last_at"])

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
        rows = dataset.prepare(dataset.synthetic_events()[:3])
        # 이전 버전 자료의 미확인 시각도 계속 읽을 수 있는지 확인함.
        for row in rows:
            row["prediction_at"] = None
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
        catalog = {"q":{"unit":"s01", "tags":["loops"], "kind":"quiz", "type":"output", "level":3}}
        original = copy.deepcopy(profile)
        events = legacy.profile_events(profile, catalog, "+09:00")
        rows = dataset.prepare(events)
        self.assertEqual(original, profile)
        self.assertEqual(1, len(rows))
        self.assertIsNone(rows[0]["question_revision"])
        self.assertIsNone(rows[0]["difficulty"])
        self.assertEqual("+09:00", rows[0]["provenance"]["timezone_assumption"])
        self.assertNotIn("private-person", json.dumps(events))
        self.assertEqual("2026-01-01T00:00:00+00:00", rows[0]["prediction_at"])

    def test_baseline_metrics_use_known_answers_and_handle_single_class(self):
        self.assertEqual(1, starter.metrics([0,1], [0.1,0.9])["roc_auc"])
        self.assertEqual(0.5, starter.metrics([0,1], [0.5,0.5])["roc_auc"])
        self.assertAlmostEqual(0.01, starter.metrics([0,1], [0.1,0.9])["brier"])
        self.assertIsNone(starter.metrics([1,1], [0.5,0.5])["roc_auc"])

    def test_metrics_reject_mismatched_rows_before_computing_or_empty_result(self):
        for targets, probabilities in (([0, 1], [.2]), ([1], [.1, .8]), ([], [.5]), ([1], [])):
            with self.subTest(targets=targets, probabilities=probabilities):
                with self.assertRaises(ValueError):
                    starter.metrics(targets, probabilities)
        self.assertEqual({"rows": 0, "brier": None, "log_loss": None, "roc_auc": None}, starter.metrics([], []))

    def test_metrics_reject_invalid_probabilities_and_labels(self):
        for probability in (float("nan"), float("inf"), -float("inf"), -.01, 1.01, None, "0.5", 2 ** 10000, 1j):
            with self.subTest(probability=probability):
                with self.assertRaises(ValueError):
                    starter.metrics([0, 1], [probability, .9])
        for target in (-1, 2, .5, float("nan"), float("inf"), None, "1", 1j):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    starter.metrics([0, target], [.1, .9])

    def test_metrics_keep_probability_boundaries_finite_and_inputs_unchanged(self):
        targets, probabilities = [0, 1], [1., 0.]
        result = starter.metrics(targets, probabilities)
        self.assertEqual(1., result["brier"])
        self.assertEqual(0., result["roc_auc"])
        self.assertTrue(math.isfinite(result["log_loss"]))
        self.assertGreaterEqual(result["log_loss"], 0.)
        self.assertEqual([0, 1], targets)
        self.assertEqual([1., 0.], probabilities)

    def test_old_and_all_lesson_mock_records_share_version_8_inputs(self):
        """예전 회차 m4 와 모든 차시 회차 m11 기록이 섞여도 공통 입력 버전은 8 로 남고 두 회차 문항이 번호표에 들어감.
        모의고사 빈 답(blank)과 이 기기에서 채점하지 못한 코드 작성 답(ungraded)은 학습 행이 되지 않음."""
        events = mixed_mock_events()
        skipped = {row["event_id"] for row in events if row["data"].get("result") in ("blank", "ungraded")}
        self.assertEqual(4, len(skipped))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "starter"
            manifest = starter.write_starter(events, root)
            self.assertEqual(8, manifest["features_version"])
            records = json.loads((root / "records/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual((8, {"missing_prediction_time": 0}), (records["features_version"], records["excluded_rows"]))
            rows, vocabulary = [], None
            for part in ("train", "validation", "test"):
                part_rows, vocabulary = input_example.load(root, "ai", part)
                rows += part_rows
        self.assertLessEqual({"m4-01", "m4-32", "m11-01", "m11-25", "m11-41"}, set(vocabulary["questions"]))
        self.assertEqual(["app", "intro"], sorted(set(vocabulary["courses"]) - {"<PAD>", "<UNK>"}))
        self.assertFalse(skipped & {row["event_id"] for row in rows})
        sessions = {}
        for row in rows:
            sessions.setdefault((row["participant"], row["session"]), set()).add(row["question_id"].split("-")[0])
        self.assertTrue(all(len(mocks) == 1 for mocks in sessions.values()), sessions)
        self.assertEqual({"m4:1", "m4:2", "m4:3", "m11:1", "m11:2", "m11:3"}, {session for _, session in sessions})

    def test_answer_whose_revision_changed_after_return_counts_as_missing_prediction_time(self):
        """응시 중에 프로그램이 갱신되어 문항 버전 해시가 바뀌면(코드 작성 문항은 실행기 파일이 바뀔 때 code_runtime_revision 으로 바뀜)
        답 기록이 반환 기록과 이어지지 않아 예측 시각 없음(missing_prediction_time)으로 세고 학습 행에서 뺌.
        이 경우를 줄이려고 예전 회차의 응시 기간에는 모의고사 엔진을 바꾸는 변경을 합치지 않음."""
        events = mixed_mock_events()
        changed = next(row for row in events if row["kind"] == "mock_answer" and row["data"]["card"] == "m11-41"
                       and row["data"]["result"] == "pass")
        changed["item_revision"] = "f" * 64
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "starter"
            starter.write_starter(events, root)
            records = json.loads((root / "records/manifest.json").read_text(encoding="utf-8"))
            rows = [row for part in ("train", "validation", "test") for row in input_example.load(root, "ai", part)[0]]
        self.assertEqual({"missing_prediction_time": 1}, records["excluded_rows"])
        self.assertNotIn(changed["event_id"], {row["event_id"] for row in rows})

    def test_metrics_accept_zero_dimensional_scalars_but_not_array_rows(self):
        class Scalar:
            ndim = 0
            def __init__(self, value):
                self.value = value
            def item(self):
                return self.value

        self.assertEqual(starter.metrics([False, True], [.2, .8]),
                         starter.metrics([Scalar(False), Scalar(True)], [Scalar(.2), Scalar(.8)]))
        for value in (Scalar(float("nan")), Scalar(1j), Scalar([.5])):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    starter.metrics([0], [value])
        with self.assertRaises(ValueError):
            starter.metrics([[0]], [.2])
