# -*- coding: utf-8 -*-
"""학습할 때만 문항 일부를 UNK 로 바꾸는 함수와, 처음 보는 문제만 모은 채점 표를 확인함."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from learning_server import dataset, input_example, score, starter


def events_with(cards):
    """합성 AI 기록의 날짜별 문항 id 를 바꿈. cards 에는 날짜나 (날짜, 가명 순번) 마다 넣을 문항 id 를 적음."""
    events = dataset.synthetic_events()
    order = sorted({row["participant"] for row in events})
    for row in events:
        if row["track"] != "ai":
            continue
        day = int(row["at"][8:10])
        card = cards.get((day, order.index(row["participant"])), cards.get(day))
        if card:
            row["item"]["card"] = row["data"]["card"] = card
    return events


class HideQuestionsTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "bundle"
        starter.write_starter(events_with({1: "ai-a", 2: "ai-a", 3: "ai-b", 4: "ai-b"}), root)
        self.rows, self.vocabulary = input_example.load(root, "ai", "train")

    def test_question_unit_hides_query_and_history_together(self):
        self.assertEqual(["<PAD>", "<UNK>", "ai-a", "ai-b"], self.vocabulary["questions"])
        before = copy.deepcopy(self.rows)
        hidden = input_example.hide_questions(self.rows, self.vocabulary, rate=0.5, seed=3)
        self.assertEqual(before, self.rows)
        original = input_example.batch(self.rows, self.vocabulary, length=8)["inputs"]
        changed = input_example.batch(hidden, self.vocabulary, length=8)["inputs"]
        index = {"ai-a": 2, "ai-b": 3}
        gone = {index[row["question_id"]] for row in self.rows} - set(changed["query_question"])
        self.assertEqual(1, len(gone))
        number = gone.pop()
        for name in ("query_question", "questions"):
            flat = lambda values: values if name == "query_question" else [n for line in values for n in line]
            for old, new in zip(flat(original[name]), flat(changed[name])):
                self.assertEqual(1 if old == number else old, new)
        self.assertIn(1, changed["query_question"])
        self.assertIn(1, [n for line in changed["questions"] for n in line])
        for name in ("concepts", "query_concepts", "results", "mask", "difficulties", "query_difficulty", "courses"):
            self.assertEqual(original[name], changed[name])

    def test_same_seed_repeats_and_rate_limits_change(self):
        first = input_example.hide_questions(self.rows, self.vocabulary, rate=0.5, seed=7)
        self.assertEqual(first, input_example.hide_questions(self.rows, self.vocabulary, rate=0.5, seed=7))
        self.assertEqual(self.rows, input_example.hide_questions(self.rows, self.vocabulary, rate=0))
        for by in ("question", "slot"):
            every = input_example.batch(input_example.hide_questions(self.rows, self.vocabulary, rate=1, by=by),
                                        self.vocabulary, length=8)["inputs"]
            self.assertEqual([1] * len(self.rows), every["query_question"])
            for line, mask in zip(every["questions"], every["mask"]):
                self.assertEqual([1 if real else 0 for real in mask], line)
        self.assertEqual(self.rows, input_example.hide_questions(self.rows, self.vocabulary, rate=0, by="slot"))
        self.assertEqual(0.1, input_example.HIDE_RATE)

    def test_invalid_arguments_are_rejected(self):
        for kwargs in ({"rate": 1.5}, {"rate": -0.1}, {"rate": True}, {"rate": "0.1"}, {"seed": 1.0}, {"by": "row"}):
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                input_example.hide_questions(self.rows, self.vocabulary, **kwargs)

    def question_rows(self, questions, unit="question_id"):
        """각 문항이 query와 history에 한 번씩 있는 합성 입력을 만듦."""
        rows = []
        for number, (question, revision) in enumerate(questions):
            row = copy.deepcopy(self.rows[-1])
            row.update(event_id="small-%d" % number, question_id=question, question_revision=revision)
            past = copy.deepcopy(row["features"]["sequence_history"][0])
            past.update(question_id=question, question_revision=revision)
            row["features"]["sequence_history"] = [past]
            rows.append(row)
        tokens = [question if unit is not None else json.dumps([question, revision], separators=(",", ":"))
                  for question, revision in questions]
        vocabulary = copy.deepcopy(self.vocabulary)
        vocabulary.update(questions=["<PAD>", "<UNK>"] + tokens, question_unit=unit)
        return rows, vocabulary

    def test_small_question_pools_hide_at_least_one_only_for_positive_rates(self):
        for size in range(1, 6):
            rows, vocabulary = self.question_rows([("small-%d" % n, "r1") for n in range(size)])
            # vocabulary 전체가 아니라 입력에 있는 문항만 후보로 세는지 확인함.
            vocabulary["questions"].append("absent-from-rows")
            before = copy.deepcopy(rows)
            for rate, expected in ((0, 0), (1e-12, 1), (input_example.HIDE_RATE, 1), (1, size)):
                with self.subTest(size=size, rate=rate):
                    hidden = input_example.hide_questions(rows, vocabulary, rate=rate, seed=3, by="question")
                    changed = input_example.batch(hidden, vocabulary, length=2)
                    self.assertEqual(expected, changed["inputs"]["query_question"].count(1))
                    expected_rows = copy.deepcopy(rows)
                    for index, row in enumerate(hidden):
                        if row["question_id"] == "<UNK>":
                            expected_rows[index]["question_id"] = "<UNK>"
                            expected_rows[index]["features"]["sequence_history"][0]["question_id"] = "<UNK>"
                    self.assertEqual(expected_rows, hidden)
                    self.assertEqual([[number, 0] for number in changed["inputs"]["query_question"]],
                                     changed["inputs"]["questions"])
                    self.assertEqual(before, rows)
            default_hidden = input_example.hide_questions(rows, vocabulary)
            self.assertEqual(1, input_example.batch(default_hidden, vocabulary)["inputs"]["query_question"].count(1))

    def test_empty_question_pools_do_not_change_rows(self):
        rows, vocabulary = self.question_rows([("outside-vocabulary", "r1")])
        for label, selected, known in (("empty-rows", [], vocabulary),
                                       ("reserved-only", rows, dict(vocabulary, questions=["<PAD>", "<UNK>"])),
                                       ("no-overlap", rows, dict(vocabulary, questions=["<PAD>", "<UNK>", "other"]))):
            before = copy.deepcopy(selected)
            for rate in (0, input_example.HIDE_RATE, 1):
                with self.subTest(pool=label, rate=rate):
                    hidden = input_example.hide_questions(selected, known, rate=rate, by="question")
                    self.assertEqual(before, hidden)
                    self.assertEqual(before, selected)
                    self.assertEqual(input_example.batch(before, known), input_example.batch(hidden, known))

    def test_question_pool_can_contain_only_history_items(self):
        rows, vocabulary = self.question_rows([("history-only", "r1")])
        rows[0]["question_id"] = "outside-vocabulary"
        before = copy.deepcopy(rows)
        hidden = input_example.hide_questions(rows, vocabulary, by="question")
        self.assertEqual("outside-vocabulary", hidden[0]["question_id"])
        self.assertEqual("<UNK>", hidden[0]["features"]["sequence_history"][0]["question_id"])
        self.assertEqual([[1, 0]], input_example.batch(hidden, vocabulary, length=2)["inputs"]["questions"])
        self.assertEqual(before, rows)

    def test_legacy_question_unit_keeps_revisions_separate_and_encodes_unk(self):
        questions = [("same-question", revision) for revision in ("a" * 64, "b" * 64, None)]
        for missing_unit in (False, True):
            rows, vocabulary = self.question_rows(questions, unit=None)
            if missing_unit:
                vocabulary.pop("question_unit")
            before = copy.deepcopy(rows)
            self.assertEqual([2, 3, 4], input_example.batch(rows, vocabulary)["inputs"]["query_question"])
            for rate, expected in ((0, 0), (input_example.HIDE_RATE, 1), (1, 3)):
                with self.subTest(missing_unit=missing_unit, rate=rate):
                    hidden = input_example.hide_questions(rows, vocabulary, rate=rate, seed=3, by="question")
                    encoded = input_example.batch(hidden, vocabulary, length=2)["inputs"]
                    self.assertEqual(expected, encoded["query_question"].count(1))
                    expected_rows = copy.deepcopy(rows)
                    for index, row in enumerate(hidden):
                        if row["question_id"] == "<UNK>":
                            expected_rows[index]["question_id"] = "<UNK>"
                            expected_rows[index]["features"]["sequence_history"][0]["question_id"] = "<UNK>"
                        self.assertEqual(1 if row["question_id"] == "<UNK>" else index + 2,
                                         encoded["query_question"][index])
                    self.assertEqual(expected_rows, hidden)
                    self.assertEqual([[number, 0] for number in encoded["query_question"]], encoded["questions"])
                    self.assertEqual(before, rows)


class UnseenScoreTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)

    def score(self, cards, synthetic=None):
        root = self.tmp / ("bundle-%d" % len(list(self.tmp.iterdir())))
        starter.write_starter(events_with(cards), root)
        rows, _ = input_example.load(root, "ai", "validation")
        path = self.tmp / (root.name + ".csv")
        path.write_text("event_id,probability,model_version\n"
                        + "".join("%s,0.7,lstm-v1\n" % row["event_id"] for row in rows), encoding="utf-8")
        inspect = score.sample.inspect
        if synthetic is None:
            return score.evaluate(root, "ai", "validation", path), rows
        with mock.patch.object(score.sample, "inspect", lambda folder: (dict(inspect(folder)[0], synthetic=synthetic),)
                               + inspect(folder)[1:]):
            return score.evaluate(root, "ai", "validation", path), rows

    def test_rows_outside_training_vocabulary_get_their_own_table(self):
        result, rows = self.score({(5, 0): "ai-new"})
        unseen = result["unseen"]
        picked = [row for row in rows if row["question_id"] == "ai-new"]
        self.assertEqual(1, len(picked))
        self.assertEqual({"rows": 1, "wrong": 1 - picked[0]["target"], "participants": 1, "linked_rows": 0, "questions": 1},
                         unseen["cell"])
        self.assertEqual([line["name"] for line in result["table"]], [line["name"] for line in unseen["table"]])
        self.assertAlmostEqual((0.7 - picked[0]["target"]) ** 2, unseen["table"][0]["metrics"]["brier"]["value"])
        self.assertTrue(unseen["warning"].startswith("처음 보는 문제 행은 오답 "))
        self.assertEqual(len(rows), result["cell"]["rows"])
        text = score.render(result)
        self.assertIn("\n\n처음 보는 문제(학습 번호표에 없는 문제) 1개: 1행, ", text)
        self.assertEqual(unseen["warning"], text.splitlines()[-1])
        saved = json.dumps(result, ensure_ascii=False)
        self.assertIn('"unseen"', saved)
        self.assertNotIn("ai-new", text + saved)

    def test_no_unseen_rows_prints_count_without_table(self):
        result, _ = self.score({})
        self.assertEqual(0, result["unseen"]["cell"]["rows"])
        self.assertEqual([], result["unseen"]["table"])
        self.assertEqual("처음 보는 문제 행이 없어 표를 내지 않습니다.", result["unseen"]["warning"])
        lines = score.render(result).splitlines()
        self.assertEqual(["처음 보는 문제(학습 번호표에 없는 문제) 0개: 0행, 오답 0행, 가명 0개, 끼운 변형 0행",
                          "처음 보는 문제 행이 없어 표를 내지 않습니다."], lines[-2:])

    def test_real_data_hides_participant_count_in_unseen_table(self):
        result, _ = self.score({5: "ai-new"}, synthetic=False)
        unseen = result["unseen"]
        self.assertEqual(2, unseen["cell"]["rows"])
        self.assertEqual("3개 미만", unseen["cell"]["participants"])
        self.assertIn("가명 3개 미만이라", unseen["warning"])
        person = [line for line in unseen["table"] if line["name"] == "per-participant"][0]
        self.assertTrue(all(value == {"value": None, "se_row": None, "se_group": None}
                            for value in person["metrics"].values()))
        for line in unseen["table"]:
            self.assertTrue(all(value["se_group"] is None for value in line["metrics"].values()))
        self.assertNotIn("가명 2개", score.render(result))

    def test_one_sided_unseen_rows_explain_missing_roc_auc(self):
        with mock.patch.object(score, "warning", return_value=None):
            result, _ = self.score({(5, 0): "ai-new"})
        self.assertIsNone(result["unseen"]["table"][0]["metrics"]["roc_auc"]["value"])
        self.assertEqual("처음 보는 문제 행은 정답이나 오답 한쪽만 있어 ROC-AUC 를 계산할 수 없습니다.", result["unseen"]["warning"])

    def test_question_seen_once_in_train_is_unseen_when_excluded_from_vocabulary(self):
        events = events_with({(1, 0): "ai-rare", (5, 0): "ai-rare", (6, 0): "ai-rare"})
        for min_count in (1, 2):
            root = self.tmp / ("rare-%d" % min_count)
            starter.write_starter(events, root, min_count=min_count)
            train, vocabulary = input_example.load(root, "ai", "train")
            self.assertEqual(1, sum(row["question_id"] == "ai-rare" for row in train))
            self.assertEqual(min_count == 1, "ai-rare" in vocabulary["questions"])
            for split in ("validation", "test"):
                with self.subTest(min_count=min_count, split=split):
                    rows, _ = input_example.load(root, "ai", split)
                    rare = [row for row in rows if row["question_id"] == "ai-rare"]
                    self.assertEqual(1, len(rare))
                    predictions = self.tmp / ("rare-%d-%s.csv" % (min_count, split))
                    predictions.write_text("event_id,probability,model_version\n"
                                           + "".join("%s,0.7,lstm-v1\n" % row["event_id"] for row in rows),
                                           encoding="utf-8")
                    result = score.evaluate(root, "ai", split, predictions)
                    expected = int(min_count == 2)
                    self.assertEqual(expected, result["unseen"]["cell"]["rows"])
                    self.assertEqual(expected, result["unseen"]["cell"]["questions"])
                    encoded = input_example.batch(rare, vocabulary)["inputs"]["query_question"]
                    self.assertEqual(expected, encoded.count(1))

    def test_unseen_baseline_metrics_are_recomputed_on_the_subset(self):
        result, rows = self.score({(5, 0): "ai-new"})
        picked = [row for row in rows if row["question_id"] == "ai-new"]
        self.assertEqual(2, len(rows))
        self.assertEqual(1, len(picked))
        target = picked[0]["target"]
        # 합성 학습은 8행 중 정답 6행이며 각 가명도 4행 중 정답 3행임.
        # 마지막 기준선은 해당 가명의 지난 정답 3회에 1을 더하고, 풀이 4회에 2를 더해 4/6을 예측함.
        probabilities = {"majority": 1, "overall-mean": 3 / 4, "per-question": 3 / 4,
                         "per-concept": 3 / 4, "per-participant": 3 / 4, "past-concept-ratio-v1": 4 / 6}
        whole = {line["name"]: line["metrics"] for line in result["table"]}
        subset = {line["name"]: line["metrics"] for line in result["unseen"]["table"]}
        for name, probability in probabilities.items():
            with self.subTest(baseline=name):
                metrics = subset[name]
                self.assertAlmostEqual((probability - target) ** 2, metrics["brier"]["value"])
                self.assertEqual(int(target == 1), metrics["accuracy"]["value"])
                self.assertIsNone(metrics["roc_auc"]["value"])
                if name == "majority":
                    self.assertIsNone(metrics["log_loss"]["value"])
                else:
                    self.assertAlmostEqual(-math.log(probability if target else 1 - probability),
                                           metrics["log_loss"]["value"])
                self.assertNotAlmostEqual(whole[name]["brier"]["value"], metrics["brier"]["value"])
                self.assertIsNone(metrics["brier"]["se_row"])
                self.assertEqual(0, metrics["accuracy"]["se_row"])
                self.assertTrue(all(value["se_group"] is None for value in metrics.values()))

    def test_unseen_question_count_counts_unique_questions_not_rows(self):
        result, rows = self.score({5: "ai-new"})
        self.assertEqual(2, len(rows))
        self.assertEqual({"ai-new"}, {row["question_id"] for row in rows})
        self.assertEqual(2, result["unseen"]["cell"]["rows"])
        self.assertEqual(1, result["unseen"]["cell"]["questions"])
        self.assertIn("처음 보는 문제(학습 번호표에 없는 문제) 1개: 2행,", score.render(result))

    def test_render_keeps_the_last_baseline_in_the_full_table(self):
        result, _ = self.score({(5, 0): "ai-new"})
        full, unseen = score.render(result).split("\n\n", 1)
        lines = full.splitlines()
        names = [line.split(" | ", 1)[0] for line in lines if " | " in line][1:]
        self.assertEqual(["lstm-v1", "majority", "overall-mean", "per-question", "per-concept", "per-participant",
                          "past-concept-ratio-v1"], names)
        self.assertEqual("past-concept-ratio-v1 | 0.7520 ± 0.3466 / 0.3466 | 0.2778 ± 0.1667 / 0.1667"
                         " | 0.5000 ± 0.5000 / 계산할 수 없음 | 0.5000 ± 0.3536 / 0.5000", lines[-2])
        self.assertEqual(result["warning"], lines[-1])
        self.assertTrue(unseen.startswith("처음 보는 문제(학습 번호표에 없는 문제) 1개: 1행,"))


if __name__ == "__main__":
    unittest.main()
