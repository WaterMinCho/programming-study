# -*- coding: utf-8 -*-
"""정답 없는 후보와 평가용 문항의 입력 일치·시각·원본 보존을 확인함."""
import copy
import unittest

from learning_server import dataset, input_example, starter


class CandidateBatchTest(unittest.TestCase):
    def setUp(self):
        self.rows = dataset.prepare(dataset.synthetic_events())
        self.row = next(row for row in self.rows if len(row["features"]["sequence_history"]) >= 3)
        self.snapshot = {key: copy.deepcopy(self.row[key]) for key in ("prediction_at", "features")}
        self.candidate = {key: copy.deepcopy(self.row[key]) for key in (
            "question_id", "question_revision", "concepts", "course", "difficulty", "generation")}
        self.candidate["candidate_id"] = "candidate-1"
        self.vocabulary = {"question_unit": "question_id", "questions": ["<PAD>", "<UNK>", self.row["question_id"]],
                           "concepts": ["<PAD>", "<UNK>"] + self.row["concepts"],
                           "courses": ["<PAD>", "<UNK>", "intro", "app"]}

    def encode(self, candidates=None, snapshot=None):
        return input_example.candidate_batch(candidates if candidates is not None else [self.candidate],
                                             self.vocabulary, snapshot or self.snapshot, length=2)

    def test_matches_training_arrays_without_target_or_answer_event(self):
        for track in ("ai", "python"):
            row = next(row for row in self.rows if row["track"] == track and len(row["features"]["sequence_history"]) >= 3)
            candidate = {key: copy.deepcopy(row[key]) for key in self.candidate if key != "candidate_id"}
            candidate["candidate_id"] = "candidate-1"
            snapshot = {key: row[key] for key in ("prediction_at", "features")}
            expected = input_example.batch([row], self.vocabulary, length=2)
            actual = self.encode([candidate], snapshot)
            self.assertEqual(expected["inputs"], actual["inputs"])
            self.assertEqual(expected["question_provenance"], actual["question_provenance"])
            self.assertEqual({"inputs", "question_provenance", "candidate_ids", "prediction_at"}, set(actual))
            row["target"] = 1 - row["target"]
            self.assertEqual(actual["inputs"], input_example.batch([row], self.vocabulary, length=2)["inputs"])

    def test_keeps_candidate_order_and_does_not_add_candidates_to_history(self):
        other = dict(self.candidate, candidate_id="candidate-2", question_id="new-question", difficulty=3, course="app")
        saved = copy.deepcopy(([self.candidate, other], self.snapshot, self.vocabulary))
        result = self.encode([self.candidate, other])
        self.assertEqual(["candidate-1", "candidate-2"], result["candidate_ids"])
        self.assertEqual([2, 1], result["inputs"]["query_question"])
        self.assertEqual([2, 3], result["inputs"]["query_difficulty"])
        self.assertEqual([True, True], result["inputs"]["query_difficulty_known"])
        for key in ("questions", "concepts", "mask", "results", "lengths"):
            self.assertEqual(result["inputs"][key][0], result["inputs"][key][1])
        self.assertEqual([1, 2], self.encode([other, self.candidate])["inputs"]["query_question"])
        self.assertEqual(saved, ([self.candidate, other], self.snapshot, self.vocabulary))

    def test_empty_history_and_unknown_concepts_do_not_imply_known_time(self):
        snapshot = {"prediction_at": self.row["prediction_at"],
                    "features": {"sequence_history": [], "observed_history": {}}}
        candidate = dict(self.candidate, question_id="unseen", concepts=["new-concept"], difficulty=None, course=None)
        inputs = self.encode([candidate], snapshot)["inputs"]
        self.assertEqual([[0, 0]], inputs["questions"])
        self.assertEqual([[False, False]], inputs["mask"])
        self.assertEqual([0], inputs["lengths"])
        self.assertEqual([1], inputs["query_question"])
        self.assertEqual(1, inputs["query_concepts"][0][1])
        self.assertFalse(any(inputs["query_gap_known"][0]))
        self.assertEqual([False], inputs["query_difficulty_known"])
        self.assertEqual([1], inputs["query_course"])

    def test_empty_candidates_return_empty_batch(self):
        result = self.encode([])
        self.assertEqual([], result["candidate_ids"])
        self.assertTrue(all(value == [] for value in result["inputs"].values()))
        self.assertEqual({"query": [], "history": []}, result["question_provenance"])

    def test_generation_is_retained_separately_without_mutable_alias(self):
        provenance = {"version": 1, "generator_id": "a01-g01", "template_id": "a01-g01",
                      "template_revision": "v1", "source_hashes": {"generator": "a" * 64, "common": None, "runtime": "b" * 64},
                      "version_hash": "c" * 64, "seed": 3, "params": {"width": 4}, "params_status": "declared",
                      "instance_id": "d" * 64}
        candidate = dict(self.candidate, generation=provenance)
        result = self.encode([candidate])
        self.assertEqual([provenance], result["question_provenance"]["query"])
        result["question_provenance"]["query"][0]["params"]["width"] = 8
        self.assertEqual(4, provenance["params"]["width"])
        provenance["params"]["answer"] = 1
        with self.assertRaises(ValueError):
            self.encode([candidate])

    def test_gap_uses_full_observed_history_when_sequence_is_truncated(self):
        import datetime
        tag = self.row["concepts"][0]
        last_at = self.snapshot["features"]["sequence_history"][0]["at"]
        self.snapshot["features"]["observed_history"][tag]["last_at"] = last_at
        result = self.encode()["inputs"]
        index = self.vocabulary["concepts"].index(tag)
        elapsed = (datetime.datetime.fromisoformat(self.snapshot["prediction_at"])
                   - datetime.datetime.fromisoformat(last_at)).total_seconds()
        self.assertEqual([2], result["lengths"])
        self.assertEqual(elapsed, result["query_gap_seconds"][0][index])
        self.assertTrue(result["query_gap_known"][0][index])

    def test_old_vocabulary_keeps_revision_based_question_ids(self):
        self.vocabulary.pop("question_unit")
        self.vocabulary["questions"][2] = starter.question_token(self.row, None)
        updated = dict(self.candidate, candidate_id="new-revision", question_revision="b" * 64)
        self.assertEqual([2, 1], self.encode([self.candidate, updated])["inputs"]["query_question"])

    def test_each_candidate_uses_only_its_own_concept_gaps(self):
        history = [dict(question_id="qA", concepts=["A"], result=1, at="2026-01-01T00:00:00+00:00"),
                   dict(question_id="qB", concepts=["B"], result=0, at="2026-01-01T23:00:00+00:00")]
        observed = {name: {"last_at": past["at"]} for name, past in zip(("A", "B"), history)}
        snapshot = {"prediction_at": "2026-01-02T00:00:00+00:00",
                    "features": {"sequence_history": history, "observed_history": observed}}
        candidates = [dict(self.candidate, candidate_id=name, concepts=[name]) for name in ("A", "B", "C")]
        original = copy.deepcopy((snapshot, candidates))
        for names in (["A", "B", "C"], []):
            with self.subTest(known=names):
                self.vocabulary["concepts"] = ["<PAD>", "<UNK>"] + names
                inputs = self.encode(candidates, snapshot)["inputs"]
                expected = [[0.0, 0.0, 86400.0, 0.0, 0.0], [0.0, 0.0, 0.0, 3600.0, 0.0], [0.0] * 5] if names else [
                    [0.0, 86400.0], [0.0, 3600.0], [0.0, 0.0]]
                self.assertEqual(expected, inputs["query_gap_seconds"])
                self.assertEqual([[value > 0 for value in row] for row in expected], inputs["query_gap_known"])
                rows = [dict(candidate, prediction_at=snapshot["prediction_at"], target=0, event_id=name,
                             features={"sequence_history": history,
                                       "observed_history": {name: observed[name]} if name in observed else {}})
                        for name, candidate in zip(("A", "B", "C"), candidates)]
                self.assertEqual(input_example.batch(rows, self.vocabulary, length=2)["inputs"], inputs)
        self.assertEqual(original, (snapshot, candidates))

    def test_future_equal_or_timezone_missing_history_is_rejected(self):
        for value in (self.row["prediction_at"], "2099-01-01T00:00:00+00:00", "2026-01-01T00:00:00", None):
            for field in ("sequence_history", "observed_history"):
                snapshot = copy.deepcopy(self.snapshot)
                if field == "sequence_history":
                    snapshot["features"][field][0]["at"] = value
                else:
                    next(iter(snapshot["features"][field].values()))["last_at"] = value
                    if value is None:
                        continue
                with self.subTest(value=value, field=field), self.assertRaises(ValueError):
                    self.encode(snapshot=snapshot)
        for value in (None, "not-a-time", "2026-01-01T12:00:00"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.encode(snapshot=dict(self.snapshot, prediction_at=value))

    def test_history_order_and_unknown_grades_are_rejected(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["features"]["sequence_history"].reverse()
        with self.assertRaises(ValueError):
            self.encode(snapshot=snapshot)
        for value in (None, True, 2, "ok"):
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["features"]["sequence_history"][0]["result"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.encode(snapshot=snapshot)

    def test_timezone_offsets_describe_the_same_prediction_instant(self):
        import datetime
        instant = datetime.datetime.fromisoformat(self.snapshot["prediction_at"])
        snapshot = dict(self.snapshot, prediction_at=instant.astimezone(datetime.timezone(datetime.timedelta(hours=9))).isoformat())
        self.assertEqual(self.encode()["inputs"], self.encode(snapshot=snapshot)["inputs"])

    def test_targets_and_duplicate_candidate_ids_are_rejected(self):
        for key in ("target", "result", "answer", "event_id"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.encode([dict(self.candidate, **{key: 1})])
        with self.assertRaises(ValueError):
            self.encode([self.candidate, self.candidate])
        with self.assertRaises(ValueError):
            self.encode(snapshot=dict(self.snapshot, target=1))
        for update in ({"candidate_id": ""}, {"question_id": "<PAD>"}, {"concepts": "demo"}, {"concepts": ["<PAD>"]}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.encode([dict(self.candidate, **update)])


if __name__ == "__main__":
    unittest.main()
