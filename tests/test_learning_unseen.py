# -*- coding: utf-8 -*-
"""학습할 때만 문항 일부를 UNK 로 바꾸는 함수와, 처음 보는 문제만 모은 채점 표를 확인함."""
import copy
import json
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


if __name__ == "__main__":
    unittest.main()
