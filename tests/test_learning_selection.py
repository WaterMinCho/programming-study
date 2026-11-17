# -*- coding: utf-8 -*-
"""묶음 선정 기록과 끼운 변형 출처를 학습 자료 행에 남기고, 끼운 변형 행을 예측 대상에서 뺄 수 있는지 확인함."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from learning_server import dataset, starter

PERSON = "11111111-1111-4111-8111-111111111111"


def practice_events(selection, shown_extra=None):
    """A 를 틀린 뒤 B 가 끼워지고 C 가 이어지는 AI 연습 묶음 하나."""
    shown_extra = shown_extra or {}
    rows = [{"participant": PERSON, "track": "ai", "sequence": 1, "synthetic": True, "event_id": "set-1",
             "at": "2026-01-01T10:00:00+00:00", "kind": "set",
             "data": {"set": "s1", "mode": "unit", "n": 2, "seed": 3, "selection": selection}}]
    for n, (card, result) in enumerate((("A", "stuck"), ("B", "pass"), ("C", "pass"))):
        at = "2026-01-01T10:%02d:00+00:00" % (n * 2 + 1)
        item = {"card": card, "tags": ["t-" + card], "lesson": "i90"}
        data = {"set": "s1", "card": card, "position": n, "again": 0}
        rows.append({"participant": PERSON, "track": "ai", "sequence": n * 2 + 2, "synthetic": True,
                     "event_id": "shown-" + card, "at": at, "kind": "question_returned", "item_revision": "a" * 64,
                     "item": item, "data": dict(data, **shown_extra.get(card, {}))})
        rows.append({"participant": PERSON, "track": "ai", "sequence": n * 2 + 3, "synthetic": True,
                     "event_id": "answer-" + card, "at": at.replace(":00+", ":30+"), "kind": "answer",
                     "item_revision": "a" * 64, "item": item,
                     "data": dict(data, result=result, first_in_set=True)})
    return rows


SELECTION = {"policy": "rules-v6", "retry_policy": "retry-v2", "selected": ["A", "C"],
             "selected_pools": {"A": "new", "C": "done"}}
RECORDED = {"A": {"retry_policy": "retry-v2"}, "B": {"retry_policy": "retry-v2", "queued_for": "A"},
            "C": {"retry_policy": "retry-v2"}}


class SelectionFieldTest(unittest.TestCase):
    def test_rows_keep_policy_pool_and_linked_source(self):
        rows = {row["question_id"]: row for row in dataset.prepare(practice_events(SELECTION, RECORDED))}
        self.assertEqual({"policy": "rules-v6", "retry_policy": "retry-v2", "pool": "new", "queued_for": None},
                         rows["A"]["selection"])
        self.assertEqual({"policy": "rules-v6", "retry_policy": "retry-v2", "pool": "linked", "queued_for": "A"},
                         rows["B"]["selection"])
        self.assertEqual("done", rows["C"]["selection"]["pool"])

    def test_card_missing_from_selected_list_is_marked_linked_without_new_fields(self):
        selection = {key: value for key, value in SELECTION.items() if key != "retry_policy"}
        rows = {row["question_id"]: row for row in dataset.prepare(practice_events(selection))}
        self.assertEqual({"policy": "rules-v6", "retry_policy": None, "pool": "linked", "queued_for": None},
                         rows["B"]["selection"])
        self.assertEqual("new", rows["A"]["selection"]["pool"])

    def test_rows_without_selection_record_stay_unknown(self):
        events = practice_events(SELECTION, RECORDED)[1:]
        rows = dataset.prepare(events)
        self.assertEqual([None, None, None], [row["selection"]["policy"] for row in rows])
        self.assertEqual([None, "linked", None], [row["selection"]["pool"] for row in rows])
        plain = dataset.prepare(dataset.synthetic_events())
        self.assertTrue(all(row["selection"] is None for row in plain))

    def test_same_set_id_in_two_courses_keeps_each_selection(self):
        intro = practice_events(SELECTION, RECORDED)
        app = practice_events(dict(SELECTION, policy="rules-v2"), RECORDED)
        for row in intro:
            row["sequence"] += 10
        for row in app:
            # 응용 묶음을 먼저 만들고 개론 묶음을 푼 뒤 응용 문항을 풂
            row["data"]["course"] = "app"
            if "item" in row:
                row["item"].update(course="app", lesson="a90")
                row["sequence"] += 20
                row["at"] = row["at"].replace("T10:", "T11:")
            else:
                row["at"] = row["at"].replace("T10:", "T09:")
            row["event_id"] += "-app"
        rows = dataset.prepare(intro + app)
        self.assertEqual(["rules-v6"] * 3 + ["rules-v2"] * 3, [row["selection"]["policy"] for row in rows])

    def test_excluding_linked_rows_keeps_them_in_later_history(self):
        exclusions = {}
        rows = dataset.prepare(practice_events(SELECTION, RECORDED), exclusions=exclusions, exclude_linked=True)
        self.assertEqual(["A", "C"], [row["question_id"] for row in rows])
        self.assertEqual(1, exclusions["linked_variant"])
        self.assertIn("answer-B", [past["event_id"] for past in rows[-1]["features"]["sequence_history"]])

    def test_manifest_counts_linked_exclusion_only_when_requested(self):
        events = dataset.synthetic_events()
        with tempfile.TemporaryDirectory() as folder:
            plain = starter.write_starter(copy.deepcopy(events), Path(folder) / "plain")
            records = json.loads((Path(folder) / "plain/records/manifest.json").read_text())
            self.assertEqual({"missing_prediction_time": 0}, records["excluded_rows"])
            starter.write_starter(copy.deepcopy(events), Path(folder) / "linked", exclude_linked=True)
            records = json.loads((Path(folder) / "linked/records/manifest.json").read_text())
            self.assertEqual({"missing_prediction_time": 0, "linked_variant": 0}, records["excluded_rows"])
            self.assertEqual(dataset.FEATURES_VERSION, plain["features_version"])


if __name__ == "__main__":
    unittest.main()
