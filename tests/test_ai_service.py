# -*- coding: utf-8 -*-
"""AiSession·PracticeSet 테스트(설계 2.4~2.9, 2.13, 9.1). 고정 은행 tests/ai_bank 와 임시 submissions·홈
폴더, 바꿔 끼운 service.now 로 학습 단원, 묶음 구성(모드별, 시드, 작을 때, 꼴 비율, family), 묶음 안 반복, 확신도·[모르겠어요]
기록, 맞힌 값 없음, 문장 also, override, 요약, 깨진 기록, 준비 중 차시, AiRecord 캐시, 오답 노트 문항을 봄.

실행: python -m unittest tests.test_ai_service
"""
import json
import os
import random
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import bank, service  # noqa: E402
from aiprep.service import AiError, AiSession  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "ai_bank")
RIGHT = {"i90-b01": ["반대"], "i90-b02": ["zero_grad"], "i90-b03": ["2.8"], "i90-b04": ["과적합"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ai_service_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.object(study, "SUBMISSIONS_DIR", os.path.join(self.tmp, "subs"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.at = "2026-11-09T20:00:00"
        patcher = mock.patch.object(service, "now", lambda: self.at)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = FIXTURE

    def session(self):
        return AiSession("alice", home=os.path.join(self.tmp, "home"), root=self.root)

    def log(self, sess, kind=None):
        return [e for e in sess.record.log if kind is None or e.get("kind") == kind]

    def right(self, ps, cur):
        """지금 문항의 정답(빈칸 글 목록이나 고르기 번호 목록)."""
        entry = ps.queue[ps.pos]
        item = ps._view(entry)["item"]
        if cur["kind"] == "blank":
            return [b["answer"][0] for b in item["blanks"]]
        from aiprep import grade
        return grade.right_options(item)

    def wrong(self, cur):
        if cur["kind"] == "blank":
            return ["틀린 답"] * len(cur["blanks"])
        from aiprep import grade  # noqa: F401
        return [o["no"] for o in cur["options"]][:1] if cur["pick"] == "never" else None

    def play(self, ps, decide):
        """decide(cur) 가 "pass"·"fail"·"dk" 를 돌려주는 대로 끝까지 풂. 나온 카드 id 순서."""
        seen = []
        while True:
            cur = ps.current()
            if cur is None:
                return seen
            seen.append(cur["card"])
            how = decide(cur)
            if how == "dk":
                ps.dont_know(2)
            elif how == "pass":
                ps.answer(self.right(ps, cur), 3, True)
            else:
                good = self.right(ps, cur)
                if cur["kind"] == "blank":
                    ps.answer(["틀린 답"] * len(good), 3, True)
                else:
                    other = [o["no"] for o in cur["options"] if o["no"] not in good][:1]
                    ps.answer(other, 3, True)
            ps.next()


class LearnTest(Base):
    def test_load_and_not_ready(self):
        sess = self.session()
        self.assertEqual({}, sess.errors)
        self.assertEqual(17, len(sess.cards))
        with self.assertRaises(AiError) as caught:
            sess.lesson("i91")
        self.assertIn("준비 중", str(caught.exception))
        with self.assertRaises(AiError):
            sess.lesson("i99")
        overview = sess.overview()
        self.assertEqual([True, False], [row["ready"] for row in overview["lessons"]])
        for key in ("lessons", "patterns", "mocks", "due", "again", "today_answers", "today_extra", "memorised", "cards", "plan",
                    "next", "notes", "activity", "activity_counts", "recent", "last_at"):
            self.assertIn(key, overview)

    def test_unit_steps_blocks(self):
        sess = self.session()
        steps = sess.unit_steps("i90", "90a")["steps"]
        self.assertEqual(["먼저 풀어 보기", "손실이 줄어드는 쪽으로 W를 옮깁니다", "학습 루프의 세 줄", "외울 것"], [s["title"] for s in steps])
        guess = steps[0]["blocks"][1]
        self.assertEqual("guess", guess["kind"])
        self.assertNotIn("answer", guess)
        text = "\n".join(b.get("markdown", "") for s in steps for b in s["blocks"])
        self.assertNotIn("<!--", text)
        self.assertIn("```python", text)
        figure = steps[1]["blocks"][0]
        self.assertEqual(("figure", 2), (figure["kind"], len(figure["frames"])))
        self.assertTrue(os.path.isfile(figure["path"]))
        sess.save_guess("i90", "90a", "g1", 1)
        reveal = next(b for b in sess.unit_steps("i90", "90a")["steps"][1]["blocks"] if b["kind"] == "reveal")
        self.assertEqual((1, 0), (reveal["picked"], reveal["answer"]))
        recall = next(b for b in steps[1]["blocks"] if b["kind"] == "recall")
        self.assertTrue(sess.check_recall(recall, "2.80"))
        sess.save_recall("i90", "90a", "r1", True)
        sess.save_step("i90", "90a", 2)
        self.assertEqual(2, sess.unit_steps("i90", "90a")["at_step"])
        self.assertFalse(os.path.exists(os.path.join(study.SUBMISSIONS_DIR, "alice", "ai", "state.json")))
        self.assertEqual(["guess", "recall"], [e["kind"] for e in self.log(sess)])

    def test_note_memo_and_revisit(self):
        sess = self.session()
        memo = sess.note("i90", only_memo=True)
        self.assertEqual([["memo"], ["memo"]], [[b["kind"] for s in u["steps"] for b in s["blocks"]] for u in memo["units"]])
        self.assertIsNone(sess.revisit())
        sess.mark_read("i90", "90b")
        found = sess.revisit()
        self.assertEqual(("i90", "90b"), (found["lesson"], found["unit"]))
        self.assertTrue(found["figure"].endswith("90b-1.png"))
        self.assertEqual(2, len(found["memo"]))


class SetTest(Base):
    def test_unit_mode_starts_with_new_cards_and_mixes(self):
        sess = self.session()
        sess.mark_read("i90", "90b")
        self.at = "2026-11-11T20:00:00"
        for cid in ("i90-b04", "i90-c02", "i90-s01", "i90-s02"):
            sess._append({"kind": "answer", "set": "s0", "card": cid, "result": "pass", "again": 0})
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=11)
        cards = [e["card"] for e in ps.queue]
        self.assertEqual(["i90-b01", "i90-b02"], cards[:2])
        self.assertIn("i90-b03", cards)
        self.assertGreaterEqual(sum(1 for c in cards if sess.cards[c]["unit"] != "90a") / float(len(cards)), 0.3)
        entry = self.log(sess, "set")[-1]
        self.assertEqual(("unit", "i90", "90a", 11, len(cards)), (entry["mode"], entry["lesson"], entry["unit"], entry["seed"], entry["n"]))
        self.assertEqual("90차시 · 기울기로 걸음 정하기", ps.title)

    def test_same_seed_same_set(self):
        sess = self.session()
        sess.start_set("lesson", lesson="i90", seed=1)
        first = [service.build_set(sess, sess._state(), "lesson", random.Random(7), lesson="i90") for _ in range(2)]
        self.assertEqual(first[0], first[1])
        other = service.build_set(sess, sess._state(), "lesson", random.Random(8), lesson="i90")
        self.assertEqual(sorted(first[0]), sorted(other))

    def test_lesson_set_shape(self):
        sess = self.session()
        ps = sess.start_set("lesson", lesson="i90", seed=2)
        cards = [e["card"] for e in ps.queue]
        self.assertLess(len(cards), service.SET_SIZE)
        families = [sess.cards[c]["family"] for c in cards]
        self.assertEqual(len(families), len(set(families)))
        self.assertFalse({"i90-b03", "i90-g01"} <= set(cards))
        gens = [c for c in cards if sess.cards[c]["kind"] == "gen"]
        self.assertLessEqual(len(gens), int(len(cards) * service.GEN_SHARE))
        forms = [sess.card_form(sess.cards[c], None) for c in cards]
        self.assertGreaterEqual(forms.count("blank"), service.BLANK_MIN * len(cards) - 4)
        run = longest = 0
        for form in forms:
            run = run + 1 if form == "choice" else 0
            longest = max(longest, run)
        self.assertLessEqual(longest, service.CHOICE_RUN)

    def test_unit_caps_give_way_up_to_set_min(self):
        sess = self.session()
        sess.start_set("lesson", lesson="i90", seed=1)
        sess.mark_read("i90", "90b")
        with mock.patch.object(service, "UNIT_NEW", 3):
            cards = service.build_set(sess, sess._state(), "unit", random.Random(1), lesson="i90", unit="90b")
        self.assertEqual(service.SET_MIN, len(cards))
        cards = service.build_set(sess, sess._state(), "unit", random.Random(1), lesson="i90", unit="90b")
        self.assertEqual(service.UNIT_NEW, len(cards))

    def test_nothing_to_practice(self):
        sess = self.session()
        with self.assertRaises(AiError):
            sess.start_set("review")
        with self.assertRaises(AiError):
            sess.start_set("nope")

    def test_review_orders_by_relative_delay(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        sess._append({"kind": "answer", "set": "s0", "card": "i90-b01", "result": "pass", "again": 0})
        self.at = "2026-11-10T20:00:00"
        sess._append({"kind": "answer", "set": "s1", "card": "i90-b02", "result": "pass", "again": 0})
        self.at = "2026-11-12T20:00:00"
        sess._append({"kind": "answer", "set": "s2", "card": "i90-b02", "result": "pass", "again": 0})
        self.at = "2026-11-20T20:00:00"
        due = sess._state().due_cards()
        self.assertEqual(["i90-b01", "i90-b02"], due)


class ArrangeTest(unittest.TestCase):
    """_arrange 의 섞는 규칙을 가짜 카드로."""

    class Fake(object):
        def __init__(self, cards):
            self.cards = cards

        def card_form(self, card, box):
            return card["form"]

    class State(object):
        def box(self, cid):
            return None

    def card(self, cid, lesson, form="blank", tags=(), confuse=()):
        return {"id": cid, "lesson": lesson, "form": form, "tags": list(tags), "confuse": list(confuse)}

    def test_confuse_pair_one_apart_and_lessons_spread(self):
        cards = {"a": self.card("a", "i01", confuse=["confuse:x"]), "b": self.card("b", "i01", confuse=["confuse:x"]),
                 "c": self.card("c", "i02"), "d": self.card("d", "i03"), "e": self.card("e", "i02"), "f": self.card("f", "i03")}
        for seed in range(20):
            seq = service._arrange(self.Fake(cards), self.State(), [(c, "rest") for c in sorted(cards)], random.Random(seed))
            pa, pb = seq.index("a"), seq.index("b")
            if min(pa, pb) < len(seq) - 2:
                self.assertEqual(2, abs(pa - pb), seq)
            self.assertEqual(sorted(cards), sorted(seq))

    def test_choice_runs_broken(self):
        cards = {str(n): self.card(str(n), "i0%d" % (n % 3), form="choice" if n < 6 else "blank") for n in range(8)}
        seq = service._arrange(self.Fake(cards), self.State(), [(c, "rest") for c in sorted(cards)], random.Random(1))
        run = longest = 0
        for cid in seq:
            run = run + 1 if cards[cid]["form"] == "choice" else 0
            longest = max(longest, run)
        self.assertLessEqual(longest, 3)

    def test_unit_pattern(self):
        cards = {c: self.card(c, "i0%d" % n) for n, c in enumerate("abcdefg")}
        chosen = [("a", "new"), ("b", "new"), ("c", "new"), ("d", "new"), ("e", "due"), ("f", "due"), ("g", "other")]
        seq = service._arrange(self.Fake(cards), self.State(), chosen, random.Random(3), "NNR")
        self.assertEqual(["a", "b"], seq[:2])
        self.assertNotIn(seq[2], "abcd")
        self.assertEqual(["c", "d"], seq[3:5])


class RepeatTest(Base):
    def start(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        return sess, sess.start_set("unit", lesson="i90", unit="90a", seed=3)

    def test_first_pass_ends(self):
        sess, ps = self.start()
        seen = self.play(ps, lambda cur: "pass")
        self.assertEqual(sorted(seen), sorted(set(seen)))
        summary = ps.summary()
        self.assertEqual((3, 3, 3), (summary["n"], summary["first_pass"], summary["first_today"]))
        end = self.log(sess, "set_end")[-1]
        self.assertEqual((3, 3, 3), (end["n"], end["first_pass"], end["answers"]))

    def test_wrong_comes_back_after_three_then_needs_two_passes(self):
        sess, ps = self.start()
        target = ps.current()["card"]
        state = {"n": 0}

        def decide(cur):
            if cur["card"] == target:
                state["n"] += 1
                return "fail" if state["n"] == 1 else "pass"
            return "pass"
        stems = []
        original = ps.queue[ps.pos]

        def watch(cur):
            if cur["card"] == target:
                stems.append(cur["stem"])
            return decide(cur)
        seen = self.play(ps, watch)
        self.assertEqual(3, seen.count(target))
        self.assertEqual(sess.cards[target]["item"]["stem"], stems[0])
        self.assertEqual(sess.cards[target]["item"]["alt"]["stem"], stems[1])
        self.assertTrue(original["card"] == target)
        rows = [e for e in self.log(sess, "answer") if e["card"] == target]
        self.assertEqual([("stuck", 0), ("pass", 1), ("pass", 2)], [(e["result"], e["again"]) for e in rows])
        self.assertIn(target, seen[1:])

    def test_requeue_gaps(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("lesson", lesson="i90", seed=9)
        first = ps.current()["card"]
        size = len(ps.queue)
        ps.answer(self.wrong(ps.current()) or [9], 1, False)
        cards = [e["card"] for e in ps.queue]
        self.assertEqual(first, cards[1 + service.GAP_WRONG])
        self.assertEqual(size + 1, len(ps.queue))

    def test_fourth_fail_leaves_set(self):
        sess, ps = self.start()
        target = ps.current()["card"]
        seen = self.play(ps, lambda cur: "fail" if cur["card"] == target else "pass")
        self.assertEqual(service.MAX_FAIL, seen.count(target))
        self.assertEqual([target], ps.summary()["left"])
        self.assertEqual([target], sess._state().again)
        self.assertEqual("again", sess.overview()["next"]["kind"])

    def test_sure_dontknow_and_no_value_on_pass(self):
        sess, ps = self.start()
        cur = ps.current()
        ps.answer(self.right(ps, cur), 4.04, True)
        ps.next()
        cur = ps.current()
        feedback = ps.dont_know(1.5)
        self.assertEqual("stuck", feedback["result"])
        ps.next()
        cur = ps.current()
        feedback = ps.answer(["틀린 답"], 2, True)
        self.assertTrue(feedback["sure_wrong"])
        rows = self.log(sess, "answer")
        self.assertEqual((True, 4.0), (rows[0]["sure"], rows[0]["secs"]))
        self.assertNotIn("value", rows[0])
        self.assertTrue(rows[1]["dontknow"])
        self.assertNotIn("sure", rows[1])
        self.assertEqual(["틀린 답"], rows[2]["value"])
        with self.assertRaises(AiError):
            ps.answer(["또"], 1, True)

    def test_override(self):
        sess, ps = self.start()
        cur = ps.current()
        ps.answer(["엉뚱한 답"], 2, False)
        size = len(ps.queue)
        result = ps.override()
        self.assertEqual("pass", result["result"])
        self.assertEqual(size - 1, len(ps.queue))
        row = self.log(sess, "override")[-1]
        answer = self.log(sess, "answer")[-1]
        self.assertEqual((answer["set"], answer["again"], cur["card"]), (row["set"], row["again"], row["card"]))
        events = __import__("aiprep.review", fromlist=["card_events"]).card_events(sess.record.log)
        self.assertEqual("pass", events[cur["card"]][0]["result"])
        with self.assertRaises(AiError):
            ps.override()

    def test_chips_and_code(self):
        sess, ps = self.start()
        chips = {}
        while ps.current() is not None:
            cur = ps.current()
            chips[cur["card"]] = (cur["chips"], cur["code"])
            ps.answer(self.right(ps, cur), 1, True)
            ps.next()
        self.assertEqual((["90차시", "코드 빈칸"], True), chips["i90-b02"])
        self.assertEqual((["90차시", "빈칸"], False), chips["i90-b01"])


class StatementTest(Base):
    def test_choice_form_and_also_only_open(self):
        sess = self.session()
        sess.mark_read("i90", "90b")
        ps = sess.start_set("unit", lesson="i90", unit="90b", seed=5)
        while ps.current() is not None and not ps.current()["card"].startswith("i90-s"):
            ps.answer(self.right(ps, ps.current()), 1, True)
            ps.next()
        cur = ps.current()
        self.assertEqual("choice", cur["kind"])
        self.assertEqual(4, len(cur["options"]))
        right = self.right(ps, cur)
        other = [o["no"] for o in cur["options"] if o["no"] not in right][0]
        ps.answer([other], 2, False)
        row = self.log(sess, "answer")[-1]
        self.assertEqual(4, len(row["shown"]))
        self.assertIn("seed", row)
        picked = row["picked"][0]
        st = sess._state()
        opened = st.is_open(sess.cards[picked])
        self.assertEqual(opened, picked in row.get("also", {}))

    def test_cloze_after_box_two(self):
        sess = self.session()
        sess.mark_read("i90", "90b")
        sess._append({"kind": "answer", "set": "s0", "card": "i90-s01", "result": "pass", "again": 0})
        self.at = "2026-11-10T20:00:00"
        sess._append({"kind": "answer", "set": "s1", "card": "i90-s01", "result": "pass", "again": 0})
        card = sess.cards["i90-s01"]
        self.assertEqual("blank", sess.card_form(card, sess._state().box("i90-s01")))
        self.assertEqual("choice", sess.card_form(sess.cards["i90-s05"], 3))


class RecordTest(Base):
    def test_broken_record(self):
        path = os.path.join(study.SUBMISSIONS_DIR, "alice", "ai", "record.json")
        study.write_text(path, "{")
        with self.assertRaises(AiError) as caught:
            self.session()
        self.assertIn("AI 비전 개론 기록", str(caught.exception))

    def test_record_cache_rereads_only_when_file_changes(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        sess.overview()  # 처음 만든 파일은 한 번 다시 읽음
        reads = sess.record.reads
        for _ in range(3):
            sess.save_recall("i90", "90a", "r1", True)
            sess.overview()
        self.assertEqual(reads, sess.record.reads)
        path = sess.record.path
        data = study.read_json(path)
        data["log"].append({"at": "2026-11-09T21:00:00", "kind": "learn", "lesson": "i90", "unit": "90b"})
        study.write_text(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        os.utime(path, ns=(os.stat(path).st_atime_ns, os.stat(path).st_mtime_ns + 10 ** 9))
        overview = sess.overview()
        self.assertGreater(sess.record.reads, reads)
        self.assertEqual(2, overview["lessons"][0]["read"])
        sess.save_recall("i90", "90b", "r3", False)
        self.assertEqual(4, len([e for e in study.read_json(path)["log"] if e["kind"] == "recall"]))

    def test_bank_error_is_reported_per_lesson(self):
        root = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, root)
        study.write_text(os.path.join(root, "items", "i90", "work", "items.json"), "{")
        self.root = root
        sess = self.session()
        self.assertIn("i90", sess.errors)
        with self.assertRaises(AiError):
            sess.lesson("i90")
        self.assertEqual(sess.errors["i90"], sess.overview()["lessons"][0]["error"])

    def test_bad_index(self):
        root = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, root)
        study.write_text(os.path.join(root, "index.json"), "{}")
        self.root = root
        with self.assertRaises(AiError):
            self.session()


class NotesTest(Base):
    def test_wrong_item_and_explain(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=1)
        cur = ps.current()
        ps.answer(["엉뚱"] * len(cur["blanks"]) if cur["kind"] == "blank" else [0], 2, True)
        groups = sess.wrong_notes()
        self.assertEqual("90차시 시험 차시", groups[0]["title"])
        item = groups[0]["items"][0]
        self.assertEqual((cur["card"], "wrong", True), (item["key"], item["state"], item["sure"]))
        detail = sess.wrong_item(cur["card"])
        self.assertIn("확실하다고 했지만 틀림", detail["lines"])
        self.assertEqual(["엉뚱"], detail["mine"])
        explain = sess.explain(cur["card"])
        self.assertTrue(explain["answer"] and explain["explain"])
        note = sess.start_set("note", card=cur["card"], seed=2)
        self.assertEqual(cur["card"], note.queue[0]["card"])


if __name__ == "__main__":
    unittest.main()
