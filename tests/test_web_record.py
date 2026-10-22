# -*- coding: utf-8 -*-
"""record.json 읽기·쓰기와 파생 상태, 복습 상자(설계 2.5) 테스트. 설계 4.7 의 기록 예시를 그대로 넣어 미션 상태를 계산해 봄.

실행: python -m unittest tests.test_web_record
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from webprep import record, review  # noqa: E402

# 설계 4.7 의 기록 예시
DESIGN_LOG = [
    {"at": "2026-10-20T09:00:00", "kind": "receive", "item": "w03", "try": 1},
    {"at": "2026-10-20T09:18:40", "kind": "live", "item": "w03", "try": 1, "no_ai": True},
    {"at": "2026-10-20T09:22:05", "kind": "step", "item": "w03", "try": 1, "step": 0, "result": "done", "said": [1, 1, 0, 1]},
    {"at": "2026-10-20T09:31:12", "kind": "check", "item": "w03", "try": 1, "open": 1, "pass": ["1a", "1b", "1c", "1d"], "fail": [], "ms": 3810},
    {"at": "2026-10-20T09:31:12", "kind": "step", "item": "w03", "try": 1, "step": 1, "result": "pass"},
    {"at": "2026-10-20T09:47:30", "kind": "hint", "item": "w03", "try": 1, "step": 3, "n": 1},
    {"at": "2026-10-20T09:58:02", "kind": "skip", "item": "w03", "try": 1, "step": 4},
    {"at": "2026-10-20T10:04:00", "kind": "finish", "item": "w03", "try": 1, "hidden": None},
    {"at": "2026-10-20T10:06:30", "kind": "self", "item": "w03", "try": 1, "ticks": {"c1": 1, "c2": 0, "m1": 1}},
    {"at": "2026-10-20T10:10:11", "kind": "drill", "chain": "w03-F", "q": 1, "secs": 48, "need": [1, 1], "extra": [0], "talked": None,
     "note": "status 하나로 묶어 조합을 막음"},
    {"at": "2026-10-20T10:14:50", "kind": "chain", "chain": "w03-F", "result": "partial"},
    {"at": "2026-10-20T20:01:00", "kind": "learn", "page": "l03"},
]


def day(text):
    return datetime.date.fromisoformat(text)


class RecordFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="web_record_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = os.path.join(self.tmp, "sub", "web", "record.json")

    def test_append_creates_file_and_keeps_order(self):
        rec = record.Record(self.path, "minsu")
        self.assertEqual([], rec.log)
        rec.append({"kind": "receive", "item": "w03", "try": 1}, at="2026-10-20T09:00:00")
        rec.append({"kind": "live", "item": "w03", "try": 1, "no_ai": True})
        data = study.read_json(self.path)
        self.assertEqual((1, "minsu", "2026-10-20T09:00:00"), (data["format"], data["user"], data["created"]))
        self.assertEqual(["receive", "live"], [e["kind"] for e in data["log"]])
        self.assertEqual("2026-10-20T09:00:00", data["log"][0]["at"])
        self.assertTrue(data["log"][1]["at"])
        self.assertEqual(data["log"], rec.log)

    def test_append_rereads_file_written_by_someone_else(self):
        rec = record.Record(self.path, "minsu")
        rec.append({"kind": "receive", "item": "w03", "try": 1})
        other = record.Record(self.path, "minsu")
        other.append({"kind": "live", "item": "w03", "try": 1})
        rec.append({"kind": "hint", "item": "w03", "try": 1, "step": 1, "n": 1})
        self.assertEqual(["receive", "live", "hint"], [e["kind"] for e in study.read_json(self.path)["log"]])

    def test_note_is_clipped_to_500(self):
        rec = record.Record(self.path, "minsu")
        row = rec.append({"kind": "drill", "chain": "3-A", "q": 1, "note": "가" * 700})
        self.assertEqual(500, len(row["note"]))
        self.assertEqual(500, len(study.read_json(self.path)["log"][0]["note"]))

    def test_broken_file_is_a_record_error(self):
        study.write_text(self.path, "{broken")
        with self.assertRaises(record.RecordError) as caught:
            record.Record(self.path, "minsu")
        self.assertIn("JSON", str(caught.exception))
        study.write_text(self.path, json.dumps({"log": [{"no_kind": 1}]}))
        with self.assertRaises(record.RecordError):
            record.Record(self.path, "minsu")


class MissionStateTest(unittest.TestCase):
    def test_design_example(self):
        state = record.mission_states(DESIGN_LOG)["w03"]
        self.assertEqual(("done", 1, "2026-10-20T09:00:00", "2026-10-20T09:18:40", "2026-10-20T10:04:00"),
                         (state["phase"], state["try"], state["received_at"], state["live_at"], state["finished_at"]))
        self.assertTrue(state["no_ai"])
        self.assertEqual({0: "done", 1: "pass", 4: "skip"}, {k: v["result"] for k, v in state["steps"].items()})
        self.assertEqual([1, 1, 0, 1], state["steps"][0]["said"])
        self.assertEqual({3: 1}, state["hints"])
        self.assertEqual(1, state["hint_count"])
        self.assertEqual([4], state["skips"])
        self.assertEqual(["1a", "1b", "1c", "1d"], state["last_check"]["pass"])
        self.assertIsNone(state["hidden"])
        self.assertEqual({"c1": 1, "c2": 0, "m1": 1}, state["self"])
        self.assertIsNone(state["current"])

    def test_phases_and_current_step(self):
        log = DESIGN_LOG[:1]
        state = record.mission_states(log)["w03"]
        self.assertEqual(("reading", None), (state["phase"], state["current"]))
        state = record.mission_states(DESIGN_LOG[:2])["w03"]
        self.assertEqual(("live", 0, "2026-10-20T09:18:40"), (state["phase"], state["current"], state["step_open_at"]))
        state = record.mission_states(DESIGN_LOG[:3])["w03"]
        self.assertEqual((1, "2026-10-20T09:22:05"), (state["current"], state["step_open_at"]))
        state = record.mission_states(DESIGN_LOG[:5])["w03"]
        self.assertEqual((2, "2026-10-20T09:31:12"), (state["current"], state["step_open_at"]))
        state = record.mission_states(DESIGN_LOG[:7])["w03"]
        self.assertEqual(5, state["current"])
        self.assertEqual("none", record.blank_mission()["phase"])
        self.assertEqual({}, record.mission_states([]))

    def test_new_try_resets_and_old_try_entries_are_ignored(self):
        log = DESIGN_LOG + [{"at": "2026-10-22T09:00:00", "kind": "receive", "item": "w03", "try": 2},
                            {"at": "2026-10-22T09:00:01", "kind": "hint", "item": "w03", "try": 1, "step": 1, "n": 1}]
        state = record.mission_states(log)["w03"]
        self.assertEqual(("reading", 2, {}, 0, []), (state["phase"], state["try"], state["steps"], state["hint_count"], state["skips"]))
        self.assertIsNone(state["finished_at"])

    def test_other_kinds_and_items(self):
        log = DESIGN_LOG + [{"at": "2026-10-20T11:00:00", "kind": "receive", "item": "w01", "try": 1}]
        found = record.mission_states(log)
        self.assertEqual({"w01", "w03"}, set(found))
        self.assertEqual("reading", found["w01"]["phase"])


class ChainRecordTest(unittest.TestCase):
    def test_chain_results_and_answers(self):
        self.assertEqual({"w03-F": [{"at": "2026-10-20T10:14:50", "result": "partial"}]}, record.chain_results(DESIGN_LOG))
        before, after = record.drill_answers(DESIGN_LOG, "w03-F")
        self.assertEqual(1, len(before))
        self.assertEqual([], after)
        log = DESIGN_LOG + [{"at": "2026-10-23T10:00:00", "kind": "drill", "chain": "w03-F", "q": 1, "secs": 30, "need": [1, 0], "extra": [1], "talked": 1}]
        before, after = record.drill_answers(log, "w03-F")
        self.assertEqual((1, 1), (len(before), len(after)))
        last = record.last_answers(log, "w03-F")
        self.assertEqual("status 하나로 묶어 조합을 막음", last[1]["note"])
        self.assertEqual({}, record.last_answers(DESIGN_LOG, "3-A"))

    def test_learned_talked_and_activity(self):
        self.assertEqual({"l03": "2026-10-20T20:01:00"}, record.learned(DESIGN_LOG))
        self.assertEqual((0, 0), record.talked_ratio(DESIGN_LOG))
        log = DESIGN_LOG + [{"kind": "drill", "chain": "3-A", "q": 2, "talked": 1}, {"kind": "drill", "chain": "3-A", "q": 3, "talked": 0}]
        self.assertEqual((1, 2), record.talked_ratio(log))
        self.assertEqual({"2026-10-20"}, record.activity_days(DESIGN_LOG))
        drills = [{"at": "2026-10-21T10:00:00", "kind": "drill", "chain": "3-A", "q": 1}, {"at": "2026-10-21T10:05:00", "kind": "chain", "chain": "3-A"}]
        graded = sum(1 for e in DESIGN_LOG if e["kind"] in ("check", "chain"))  # 검사 한 번과 끝낸 사슬 하나
        self.assertEqual({"2026-10-20": graded, "2026-10-21": 1}, record.activity_counts(DESIGN_LOG + drills))  # 드릴 질문 하나는 세지 않음

    def test_parse_at(self):
        self.assertEqual(datetime.datetime(2026, 10, 20, 9, 0, 0), record.parse_at("2026-10-20T09:00:00"))
        self.assertIsNone(record.parse_at("어제"))
        self.assertIsNone(record.parse_at(None))


class ReviewTest(unittest.TestCase):
    def test_question_and_chain_results(self):
        self.assertEqual("pass", review.question_result([1, 1]))
        self.assertEqual("partial", review.question_result([1, 0]))
        self.assertEqual("stuck", review.question_result([0, 0]))
        self.assertEqual("stuck", review.question_result([1, 1], gave_up=True))
        self.assertEqual("pass", review.chain_result(["pass", "pass"]))
        self.assertEqual("partial", review.chain_result(["pass", "partial"]))
        self.assertEqual("stuck", review.chain_result(["pass", "stuck", "partial"]))
        self.assertEqual("stuck", review.chain_result([]))

    def test_boxes_follow_the_design_table(self):
        self.assertEqual(2, review.next_box(None, "pass"))
        self.assertEqual(1, review.next_box(None, "partial"))
        self.assertEqual(1, review.next_box(None, "stuck"))
        self.assertEqual(3, review.next_box(2, "pass"))
        self.assertEqual(5, review.next_box(5, "pass"))
        self.assertEqual(4, review.next_box(4, "partial"))
        self.assertEqual(1, review.next_box(4, "stuck"))
        self.assertEqual({1: 1, 2: 3, 3: 7, 4: 14, 5: 30}, review.INTERVAL_DAYS)

    def test_schedule_adds_interval_to_last_day(self):
        results = [{"at": "2026-10-20T10:14:50", "result": "pass"}]
        plan = review.schedule(results)
        self.assertEqual((2, day("2026-10-20"), day("2026-10-23"), 1), (plan["box"], plan["last"], plan["due"], plan["times"]))
        results.append({"at": "2026-10-23T23:59:00", "result": "pass"})
        plan = review.schedule(results)
        self.assertEqual((3, day("2026-10-30")), (plan["box"], plan["due"]))
        results.append({"at": "2026-10-30T08:00:00", "result": "stuck"})
        plan = review.schedule(results)
        self.assertEqual((1, day("2026-10-31")), (plan["box"], plan["due"]))
        self.assertIsNone(review.schedule([]))

    def test_due_list_orders_old_first_then_new_chains(self):
        schedules = {"3-A": review.schedule([{"at": "2026-10-10T10:00:00", "result": "pass"}]),
                     "3-B": review.schedule([{"at": "2026-10-19T10:00:00", "result": "stuck"}]),
                     "7-A": review.schedule([{"at": "2026-10-20T10:00:00", "result": "pass"}])}
        rows = review.due_list(schedules, ["3-A", "7-A", "1-A", "1-B", "6-A"], day("2026-10-20"))
        self.assertEqual(["3-A", "3-B", "1-A", "1-B"], [r["chain"] for r in rows])
        self.assertEqual([2, 1, None, None], [r["box"] for r in rows])
        self.assertEqual([False, False, True, True], [r["new"] for r in rows])
        rows = review.due_list(schedules, ["1-A", "1-B", "6-A"], day("2026-10-20"), new_per_day=1)
        self.assertEqual(["3-A", "3-B", "1-A"], [r["chain"] for r in rows])
        rows = review.due_list(schedules, [], day("2026-10-09"))
        self.assertEqual([], rows)

    def test_retry_missions_once_after_seven_days(self):
        metas = {"w03": {"title": "거래내역 불러오기", "live_min": 45}}
        states = record.mission_states(DESIGN_LOG)  # 4단계를 넘어감
        self.assertEqual([], review.retry_missions(states, metas, day("2026-10-26")))
        rows = review.retry_missions(states, metas, day("2026-10-27"))
        self.assertEqual([{"mission": "w03", "title": "거래내역 불러오기", "why": "넘어간 단계가 있습니다"}], rows)
        clean = [e for e in DESIGN_LOG if e["kind"] != "skip"]
        self.assertEqual([], review.retry_missions(record.mission_states(clean), metas, day("2026-10-27")))
        late = [dict(e, at="2026-10-20T11:00:00") if e["kind"] == "finish" else e for e in clean]  # 실전 101분, 56분 넘김
        rows = review.retry_missions(record.mission_states(late), metas, day("2026-10-27"))
        self.assertEqual("실전 시간을 56분 넘겼습니다", rows[0]["why"])


if __name__ == "__main__":
    unittest.main()
