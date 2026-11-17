# -*- coding: utf-8 -*-
"""문항 번호표를 문항 id 로 만들고 드문 문항을 UNK 로 보내는지, 이전 버전 자료를 그대로 읽는지 확인함."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from learning_data.collection import packed
from learning_server import dataset, input_example, sample, starter


def daily_revisions(events):
    """같은 문항 id 에 날마다 다른 버전 해시를 붙임. 화면에 낼 때마다 해시가 바뀌는 AI 기록과 같은 꼴임."""
    events = copy.deepcopy(events)
    for row in events:
        day = int(row["at"][8:10])
        row["item_revision"] = ("%x" % day) * 64
    return events


def rewrite(root, version, vocabulary=None):
    """같은 묶음의 버전 숫자와 번호표만 바꾸고 해시를 다시 맞춤."""
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    records_path = root / "records/manifest.json"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    records["features_version"] = version
    records_path.write_text(json.dumps(records), encoding="utf-8")
    manifest["features_version"] = version
    manifest["records_manifest_sha256"] = hashlib.sha256(records_path.read_bytes()).hexdigest()
    if vocabulary is not None:
        (root / "vocabulary.json").write_text(json.dumps(vocabulary), encoding="utf-8")
        manifest["files"]["vocabulary.json"] = hashlib.sha256((root / "vocabulary.json").read_bytes()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class QuestionTokenTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)

    def test_versions_of_one_question_share_one_token(self):
        root = self.tmp / "bundle"
        manifest = starter.write_starter(daily_revisions(dataset.synthetic_events()), root)
        self.assertEqual(dataset.FEATURES_VERSION, manifest["features_version"])
        for track in ("ai", "python"):
            rows, vocabulary = input_example.load(root, track, "train")
            self.assertEqual(["<PAD>", "<UNK>", track + "-demo"], vocabulary["questions"])
            self.assertEqual("question_id", vocabulary["question_unit"])
            for part in ("validation", "test"):
                rows, vocabulary = input_example.load(root, track, part)
                result = input_example.batch(rows, vocabulary, length=4)
                self.assertEqual([2] * len(rows), result["inputs"]["query_question"])

    def test_synthetic_sample_has_several_versions_of_one_question(self):
        revisions = {}
        for row in dataset.synthetic_events():
            revisions.setdefault((row["track"], row["item"]["card"]), set()).add(row["item_revision"])
        self.assertTrue(all(len(values) > 1 for values in revisions.values()))

    def rare_events(self):
        events = dataset.synthetic_events()
        rare = next(row for row in events if row["track"] == "ai" and row["at"].startswith("2026-01-01"))
        test = next(row for row in events if row["track"] == "ai" and row["at"].startswith("2026-01-06"))
        for row in (rare, test):
            row["item"]["card"] = row["data"]["card"] = "ai-rare"
        return events, rare["event_id"], test["event_id"]

    def test_question_seen_once_in_training_goes_to_unknown(self):
        events, rare_id, test_id = self.rare_events()
        root = self.tmp / "bundle"
        starter.write_starter(events, root)
        train, vocabulary = input_example.load(root, "ai", "train")
        self.assertNotIn("ai-rare", vocabulary["questions"])
        self.assertEqual(2, vocabulary["question_min_count"])
        self.assertEqual(1, vocabulary["rare_questions"])
        result = input_example.batch(train, vocabulary, length=4)
        queries = dict(zip(result["event_ids"], result["inputs"]["query_question"]))
        self.assertEqual(1, queries[rare_id])
        self.assertTrue(all(value == 2 for key, value in queries.items() if key != rare_id))
        later = [row for row in train if rare_id in [past["event_id"] for past in row["features"]["sequence_history"]]]
        self.assertTrue(later)
        history = input_example.batch(later, vocabulary, length=8)["inputs"]["questions"]
        self.assertTrue(all(1 in values for values in history))
        test, _ = input_example.load(root, "ai", "test")
        queries = dict(zip([row["event_id"] for row in test], input_example.batch(test, vocabulary)["inputs"]["query_question"]))
        self.assertEqual(1, queries[test_id])
        sample.write_sample(root, "ai", "train", len(train), 1, 4, self.tmp / "sample.json")

    def test_min_count_one_keeps_every_training_question(self):
        events, rare_id, _ = self.rare_events()
        root = self.tmp / "bundle"
        starter.write_starter(events, root, min_count=1)
        train, vocabulary = input_example.load(root, "ai", "train")
        self.assertIn("ai-rare", vocabulary["questions"])
        self.assertEqual(0, vocabulary["rare_questions"])
        queries = dict(zip([row["event_id"] for row in train], input_example.batch(train, vocabulary)["inputs"]["query_question"]))
        self.assertNotEqual(1, queries[rare_id])
        with self.assertRaises(ValueError):
            starter.write_starter(events, self.tmp / "zero", min_count=0)

    def test_vocabulary_ignores_validation_and_test_targets_and_question_ids(self):
        def build(name, change=None):
            events = dataset.synthetic_events()
            for row in events:
                day = int(row["at"][8:10])
                if row["track"] == "ai" and day == 1 and row["participant"] == events[0]["participant"]:
                    row["item"]["card"] = row["data"]["card"] = "ai-once"
                if row["track"] == "ai" and day == 2:
                    row["item"]["card"] = row["data"]["card"] = "ai-twice"
                if row["track"] == "ai" and day >= 5:
                    row["item"]["card"] = row["data"]["card"] = "ai-once" if day == 5 else "ai-twice"
                    if change:
                        change(row, day)
            root = self.tmp / name
            starter.write_starter(events, root)
            return root, json.loads((root / "vocabulary.json").read_text(encoding="utf-8"))

        def flip(row, day):
            row["data"]["result"] = "stuck" if row["data"]["result"] == "pass" else "pass"

        def rename(row, day):
            row["item"]["card"] = row["data"]["card"] = "ai-later-%d" % day

        base_root, base = build("base")
        _, flipped = build("flipped", flip)
        _, renamed = build("renamed", rename)
        self.assertEqual(base, flipped)
        self.assertEqual(base, renamed)
        # 학습 구간에 한 번 나온 문항은 검증·평가에 여러 번 나와도 빠지고, 두 번 나온 문항은 남음
        self.assertNotIn("ai-once", base["ai"]["questions"])
        self.assertIn("ai-twice", base["ai"]["questions"])
        for part in ("validation", "test"):
            rows, _ = input_example.load(base_root, "ai", part)
            self.assertGreater(len(rows), 1)

    def test_version_seven_bundle_keeps_its_question_and_revision_tokens(self):
        root = self.tmp / "bundle"
        starter.write_starter(daily_revisions(dataset.synthetic_events()), root)
        vocabulary = json.loads((root / "vocabulary.json").read_text(encoding="utf-8"))
        for track, values in vocabulary.items():
            train, _ = input_example.load(root, track, "train")
            tokens = {packed([row["question_id"], row["question_revision"]]) for row in train}
            tokens |= {packed([past["question_id"], past["question_revision"]])
                       for row in train for past in row["features"]["sequence_history"]}
            vocabulary[track] = {"questions": ["<PAD>", "<UNK>"] + sorted(tokens),
                                 "concepts": values["concepts"], "courses": values["courses"]}
        rewrite(root, 7, vocabulary)
        for track in ("ai", "python"):
            for part in ("train", "test"):
                rows, loaded = input_example.load(root, track, part)
                self.assertNotIn("question_unit", loaded)
                index = {token: n for n, token in enumerate(loaded["questions"])}
                expected = [index.get(packed([row["question_id"], row["question_revision"]]), 1) for row in rows]
                self.assertEqual(expected, input_example.batch(rows, loaded)["inputs"]["query_question"])
            test, loaded = input_example.load(root, track, "test")
            self.assertEqual([1] * len(test), input_example.batch(test, loaded)["inputs"]["query_question"])

    def test_version_eight_without_rule_and_newer_versions_are_rejected(self):
        root = self.tmp / "bundle"
        starter.write_starter(dataset.synthetic_events(), root)
        vocabulary = json.loads((root / "vocabulary.json").read_text(encoding="utf-8"))
        changed = copy.deepcopy(vocabulary)
        for values in changed.values():
            values.pop("question_unit")
        rewrite(root, 8, changed)
        with self.assertRaisesRegex(ValueError, "번호표 규칙"):
            input_example.load(root, "ai", "train")
        for values in changed.values():
            values["question_unit"] = "question_text"
        rewrite(root, 8, changed)
        with self.assertRaisesRegex(ValueError, "번호표 규칙"):
            input_example.load(root, "ai", "train")
        rewrite(root, dataset.FEATURES_VERSION + 1, vocabulary)
        with self.assertRaisesRegex(ValueError, "더 새 도구"):
            input_example.load(root, "ai", "train")
        with self.assertRaisesRegex(ValueError, "더 새 도구"):
            sample.inspect(root)

    def test_member_call_shape_stays_the_same(self):
        root = self.tmp / "bundle"
        starter.write_starter(dataset.synthetic_events(), root)
        rows, vocabulary = input_example.load(root, "python", "train")
        self.assertEqual(["<PAD>", "<UNK>"], vocabulary["questions"][:2])
        self.assertEqual(["<PAD>", "<UNK>"], vocabulary["concepts"][:2])
        names = {"questions", "concepts", "results", "mask", "lengths", "query_question", "query_concepts",
                 "query_gap_seconds", "query_gap_known", "courses", "query_course", "difficulties",
                 "difficulty_known", "query_difficulty", "query_difficulty_known"}
        for length in (32, 4):
            result = input_example.batch(rows[:4], vocabulary, length=length)
            self.assertEqual({"inputs", "question_provenance", "targets", "event_ids"}, set(result))
            self.assertEqual(names, set(result["inputs"]))
            self.assertEqual(4, len(result["targets"]))
        self.assertEqual(input_example.batch(rows[:4], vocabulary, 32), input_example.batch(rows[:4], vocabulary, length=32))


if __name__ == "__main__":
    unittest.main()
