# -*- coding: utf-8 -*-
"""AiSession·PracticeSet 테스트(설계 2.4~2.9, 2.13, 9.1). 고정 은행 tests/ai_bank 와 임시 submissions·홈
폴더, 바꿔 끼운 service.now 로 학습 단원, 묶음 구성(모드별, 시드, 작을 때, 꼴 비율, family), 묶음 안 반복, 확신도·[모르겠어요]
기록, 맞힌 값 없음, 문장 also, override, 요약, 깨진 기록, 준비 중 차시, AiRecord 캐시, 오답 노트 문항을 봄. Pattern 으로 시작하는
클래스는 tests/aifix.pc_bank 로 상황별 코드(뼈대 S90, l18, pc)를 더한 은행에서 뼈대 카드를 봄.

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
from tests import aifix  # noqa: E402

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


class LevelsServiceTest(Base):
    """세 수준 블록(90a 2단계 끝). 서비스는 블록을 그대로 넘기고, 확인 물음은 떠올리기처럼 채점·기록하며 상자와 외울 것에 들어가지 않음."""

    def test_unit_steps_check_and_record(self):
        sess = self.session()
        step = sess.unit_steps("i90", "90a")["steps"][1]
        block = step["blocks"][-1]
        self.assertEqual(("levels", "v1", [7, 15, 20]), (block["kind"], block["id"], [x["level"] for x in block["levels"]]))
        fifteen = block["levels"][1]
        self.assertTrue(os.path.isfile(fifteen["figure"]["path"]))
        self.assertTrue(fifteen["figure"]["path"].endswith(os.path.join("l90", "assets", "90a-22.png")))
        self.assertTrue(sess.check_recall(fifteen, "2.40"))
        self.assertFalse(sess.check_recall(fifteen, "2.8"))
        before = {key: sess.overview()[key] for key in ("due", "memorised", "cards")}
        sess.save_recall("i90", "90a", fifteen["id"], True, level=fifteen["level"])
        sess.save_recall("i90", "90a", "r1", False)
        rows = self.log(sess, "recall")
        self.assertEqual([("v1", 15, True), ("r1", None, False)], [(r["id"], r.get("level"), r["ok"]) for r in rows])
        self.assertNotIn("level", rows[1])
        self.assertEqual(before, {key: sess.overview()[key] for key in ("due", "memorised", "cards")})  # 상자는 움직이지 않음

    def test_check_recall_rounds_places_and_takes_unit(self):
        sess = self.session()
        self.assertTrue(sess.check_recall({"answer": ["1.417"], "mode": "number", "places": 3}, "1.41703"))
        self.assertFalse(sess.check_recall({"answer": ["1.417"], "mode": "number", "places": 3}, "1.42"))
        self.assertTrue(sess.check_recall({"answer": ["90"], "mode": "number", "unit": "%"}, "90%"))
        fifteen = dict(sess.unit_steps("i90", "90a")["steps"][1]["blocks"][-1]["levels"][1], places=1)
        self.assertTrue(sess.check_recall(fifteen, "2.43"))

    def test_note_memo_and_revisit_leave_the_block_out(self):
        sess = self.session()
        full = sess.note("i90")
        self.assertEqual(["levels"], [b["kind"] for u in full["units"] for s in u["steps"] for b in s["blocks"] if b["kind"] == "levels"])
        memo = sess.note("i90", only_memo=True)
        self.assertEqual({"memo"}, {b["kind"] for u in memo["units"] for s in u["steps"] for b in s["blocks"]})
        sess.mark_read("i90", "90a")
        found = sess.revisit()
        self.assertEqual("90a", found["unit"])
        self.assertTrue(found["figure"].endswith("90a-1.gif"))  # 블록 그림을 고르지 않음
        self.assertEqual(3, len(found["memo"]))


class RealLevelsTest(Base):
    """저장소의 1~9차시 노트. 세 수준 확인 물음의 받는 답은 모두 화면 채점에서 맞음이 되고, 떠올리기와 확인 물음의 끝나지 않는 소수는
    더 자세히 적어도 맞음(places·unit 을 채점에 넘김)."""

    def setUp(self):
        super().setUp()
        self.root = bank.AI_DIR

    def blocks(self, sess, lid, key, no, kind, bid):
        step = next(s for s in sess.unit_steps(lid, key)["steps"] if s["no"] == no)
        return next(b for b in step["blocks"] if b["kind"] == kind and b.get("id") == bid)

    def test_every_level_answer_grades_right(self):
        sess = self.session()
        count = 0
        for lid in ("i01", "i02", "i03", "i04", "i05", "i06", "i07", "i08", "i09"):
            for unit in sess.unit_list(lid):
                for step in sess.unit_steps(lid, unit["key"])["steps"]:
                    for level in (x for b in step["blocks"] if b["kind"] == "levels" for x in b["levels"]):
                        count += 1
                        for answer in level["answer"]:
                            self.assertTrue(sess.check_recall(level, answer), (lid, unit["key"], step["no"], level["level"], answer))
        self.assertGreaterEqual(count, 3 * 3 * 9)

    def test_longer_decimals_and_units(self):
        sess = self.session()
        levels = {(key, no): self.blocks(sess, "i06", key, no, "levels", "v1")["levels"] for key, no in (("6c", 2), ("6d", 2), ("6e", 3))}
        for (key, no, level), value in {("6c", 2, 0): "0.10536", ("6d", 2, 2): "0.41703", ("6e", 3, 2): "0.12693"}.items():
            self.assertTrue(sess.check_recall(levels[(key, no)][level], value), (key, no, value))
        for key, no, value in (("6c", 2, "2.30259"), ("6d", 2, "1.41703"), ("6e", 2, "90%")):
            self.assertTrue(sess.check_recall(self.blocks(sess, "i06", key, no, "recall", "r1"), value), (key, no, value))


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

    def test_unit_pattern_counts_the_new_choices_after_r(self):
        # 새 카드가 고르기 셋 뒤 빈칸이면 R 자리에 고르기를 넣는 순간 고르기가 넷 이어짐(18a 단원 묶음 꼴)
        cards = {c: self.card(c, "pc", form="choice") for c in ("n1", "n2", "n3")}
        cards["n4"] = self.card("n4", "pc")
        cards.update({c: self.card(c, "i0%d" % n, form="choice") for n, c in enumerate(("r1", "r2", "r3", "r4"))})
        cards.update({c: self.card(c, "i0%d" % n) for n, c in enumerate(("r5", "r6"))})
        chosen = [(c, "new") for c in ("n1", "n2", "n3", "n4")] + [(c, "again") for c in ("r1", "r2", "r3", "r4", "r5", "r6")]
        for seed in range(30):
            seq = service._arrange(self.Fake(cards), self.State(), list(chosen), random.Random(seed), "NNR")
            run = longest = 0
            for cid in seq:
                run = run + 1 if cards[cid]["form"] == "choice" else 0
                longest = max(longest, run)
            self.assertEqual(["n1", "n2"], seq[:2])
            self.assertLessEqual(longest, service.CHOICE_RUN, seq)

    def test_slot_waits_for_its_choice_even_against_the_lesson_spread(self):
        # 고르기 셋 뒤 i06 빈칸은 같은 차시라, pc 고르기는 넷째 고르기라 막힐 때 pc slot 을 내면 뒤 pc 고르기의 답이 먼저 보임
        cards = {c: self.card(c, "i06", form="choice") for c in ("a1", "a2", "a3", "a4")}
        cards.update({c: self.card(c, "i06") for c in ("b1", "b2", "b3")})
        for cid, part, form in (("p1", "pick", "choice"), ("p2", "pick", "choice"), ("k1", "slot", "blank")):
            cards[cid] = dict(self.card(cid, "pc", form=form), kind="skel", part=part, pattern="S90", variant="가",
                              situations={"가": ""})
        for seed in range(200):
            seq = service._arrange(self.Fake(cards), self.State(), [(c, "rest") for c in sorted(cards)], random.Random(seed))
            self.assertGreater(seq.index("k1"), max(seq.index("p1"), seq.index("p2")), (seed, seq))


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


class ReadTodayTest(Base):
    def test_only_the_day_the_unit_was_read(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        self.assertTrue(sess.read_today("i90-b01"))
        self.assertFalse(sess.read_today("i90-b04"))
        self.at = "2026-11-10T20:00:00"
        self.assertFalse(sess.read_today("i90-b01"))


class LocalStateTest(Base):
    def test_broken_state_file_is_ignored(self):
        sess = self.session()
        path = os.path.join(sess.home, "state.json")
        for text in ('{"at_step": []}', '{"at_step": {"i90/90a": "x"}}', "[]", "{"):
            study.write_text(path, text)
            self.assertIsNone(sess.unit_steps("i90", "90a")["at_step"])
            sess.save_step("i90", "90a", 2)
            self.assertEqual(2, sess.unit_steps("i90", "90a")["at_step"])


class FailedWriteTest(Base):
    def test_next_can_be_pressed_again_after_a_read_or_write_error(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = service.PracticeSet(sess, "s1", "unit", ["i90-b01", "i90-b02"], 1)
        for n in range(2):
            ps.answer(self.right(ps, ps.current()), 2, True)
            target = "_state" if n == 0 else "_append"
            with mock.patch.object(sess, target, side_effect=AiError("저장하지 못했습니다.")):
                with self.assertRaises(AiError):
                    ps.next()
            got = ps.next()
            if n == 0:
                self.assertEqual("i90-b02", got["card"])
        self.assertEqual(1, len(self.log(sess, "set_end")))


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
        self.assertIn("1번 틀림", detail["lines"])  # 하루 안에 틀린 것이면 "1일에 걸쳐" 를 붙이지 않음
        self.assertEqual(["엉뚱"], detail["mine"])
        explain = sess.explain(cur["card"])
        self.assertTrue(explain["answer"] and explain["explain"])
        note = sess.start_set("note", card=cur["card"], seed=2)
        self.assertEqual(cur["card"], note.queue[0]["card"])

    def test_retry_keeps_a_generator_card_in_a_small_set(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        self.at = "2026-11-10T20:00:00"
        for cid in ("i90-b01", "i90-b02", "i90-g01"):
            sess._append({"kind": "answer", "set": "s1", "card": cid, "result": "stuck", "again": 0, "seed": 3})
        note = sess.start_set("note", card="i90-g01", seed=2)
        self.assertEqual("i90-g01", note.queue[0]["card"])
        self.assertEqual(3, len(note.queue))
        note = sess.start_set("note", card="i90-b01", seed=2)  # 고르지 않은 생성기는 작은 묶음에서 빠짐
        self.assertEqual(["i90-b01", "i90-b02"], [e["card"] for e in note.queue])

    def test_generator_choice_keeps_my_answer(self):
        sess = self.session()
        sess.mark_read("i90", "90b")
        ps = service.PracticeSet(sess, "s1", "unit", ["i90-g02"], 1)
        cur = ps.current()
        item = ps._view(ps.queue[0])["item"]
        wrong = [o["no"] for o in cur["options"] if o["no"] not in self.right(ps, cur)][:1]
        ps.answer(wrong, 2, False)
        self.assertEqual([item["options"][wrong[0]]["text"]], sess.wrong_item("i90-g02")["mine"])

    def test_cloze_statement_is_redrawn_as_cloze(self):
        for how in ("wrong", "dk"):
            self.at = "2026-11-09T20:00:00"
            sess = AiSession(how, home=os.path.join(self.tmp, how), root=self.root)
            sess.mark_read("i90", "90b")
            sess._append({"kind": "answer", "set": "s0", "card": "i90-s01", "result": "pass", "again": 0})
            self.at = "2026-11-10T20:00:00"
            sess._append({"kind": "answer", "set": "s1", "card": "i90-s01", "result": "pass", "again": 0})
            cloze = sess.cards["i90-s01"]["stmt"]["cloze"]
            ps = service.PracticeSet(sess, "s2", "unit", ["i90-s01"], 1)
            self.assertEqual("blank", ps.current()["kind"])
            ps.dont_know(2) if how == "dk" else ps.answer(["엉뚱"], 2, False)
            detail = sess.wrong_item("i90-s01")
            self.assertEqual(("blank", cloze["text"], []), (detail["kind"], detail["stem"], detail["options"]))
            self.assertEqual(["모르겠어요"] if how == "dk" else ["엉뚱"], detail["mine"])
            self.assertEqual(cloze["answer"][:1], sess.explain("i90-s01")["answer"])

    def test_choice_statement_names_the_statement_to_pick(self):
        sess = self.session()
        sess.mark_read("i90", "90b")
        ps = service.PracticeSet(sess, "s1", "unit", ["i90-s05"], 1)
        cur = ps.current()
        right = self.right(ps, cur)
        ps.answer([o["no"] for o in cur["options"] if o["no"] not in right][:1], 2, False)
        detail = sess.wrong_item("i90-s05")
        self.assertEqual(("choice", "wrong", 4), (detail["kind"], detail["pick"], len(detail["options"])))
        explain = sess.explain("i90-s05")
        self.assertEqual([sess.cards["i90-s05"]["stmt"]["text"]], explain["answer"])
        self.assertEqual(set(detail["options"]), set(explain["why"]))
        self.assertTrue(explain["why"][detail["mine"][0]])


class PatternBase(Base):
    UNIT = "학습 루프 · 시험 뼈대 단원"

    def setUp(self):
        super().setUp()
        self.root = aifix.pc_bank(os.path.join(self.tmp, "bank"))

    def answer(self, sess, cid, result="pass", day="09", **extra):
        self.at = "2026-11-%sT20:00:00" % day
        sess._append(dict({"kind": "answer", "set": "s%s" % day, "card": cid, "result": result, "again": 0}, **extra))

    def opened_slots(self):
        """18a 를 11-09 에 읽고 k01·k03 을 답해 11-10 에 k01 상자 1, k03 상자 2 가 되게 함(k02 를 주 자리로 내면 f = 1)."""
        sess = self.session()
        sess.mark_read("pc", "18a")
        self.answer(sess, "pc-k01")
        self.answer(sess, "pc-k03")
        self.answer(sess, "pc-k03", day="10")
        self.at = "2026-11-10T21:00:00"
        return sess


class PatternLoadTest(PatternBase):
    def test_cards_overview_place_and_lesson(self):
        sess = self.session()
        self.assertEqual({}, sess.errors)
        pc = sorted(c for c in sess.cards if c.startswith("pc-"))
        self.assertEqual(["pc-k01", "pc-k02", "pc-k03", "pc-k04", "pc-k05", "pc-k06", "pc-o01", "pc-p01", "pc-x01"], pc)
        self.assertEqual(17 + 9, len(sess.cards))
        row = sess.overview()["patterns"][0]
        self.assertEqual(("pc", "상황별 코드", True, None), (row["id"], row["title"], row["ready"], row["error"]))
        first, second = row["units"]
        self.assertEqual(("18a", "학습 루프", "시험 뼈대 단원", self.UNIT, "i90", 90, True, False, 9, 7, 6),
                         tuple(first[k] for k in ("key", "name", "title", "label", "after", "after_no", "ready", "read", "cards",
                                                  "families", "minutes")))
        self.assertEqual(("18b", "", "평가 루프", False, 0, 0), tuple(second[k] for k in ("key", "title", "label", "ready", "cards", "minutes")))
        self.assertEqual({"id": "pc", "kind": "pattern", "no": None, "label": "상황별 코드", "title": "상황별 코드", "back": "home"},
                         sess.place("pc"))
        self.assertEqual(("lesson", 90, "90차시", "lesson"), tuple(sess.place("i90")[k] for k in ("kind", "no", "label", "back")))
        with self.assertRaises(AiError):
            sess.place("pz")
        lesson = sess.lesson("pc")
        self.assertEqual(("pc", None, "상황별 코드", "", False, False), tuple(lesson[k] for k in ("id", "no", "title", "date", "preview", "opened")))
        self.assertEqual([("18a", "pattern")], [(u["key"], u["kind"]) for u in lesson["units"]])
        with self.assertRaises(AiError) as caught:
            sess.note("pc")
        self.assertIn("단원 화면", str(caught.exception))

    def test_lesson_mode_is_refused_before_any_record(self):
        sess = self.session()
        with self.assertRaises(AiError):
            sess.start_set("lesson", lesson="pc")
        self.assertEqual([], self.log(sess))

    def test_broken_skeleton_keeps_lessons(self):
        study.write_text(os.path.join(self.root, "patterns", "S90.json"), "{깨짐")
        sess = self.session()
        self.assertIn("patterns", sess.errors)
        self.assertFalse(any(c.startswith("pc-") for c in sess.cards))
        self.assertEqual(17, len(sess.cards))
        self.assertEqual(sess.errors["patterns"], sess.overview()["patterns"][0]["error"])
        self.assertTrue(sess.overview()["lessons"][0]["ready"])

    def test_token_missing_drops_the_group(self):
        path = os.path.join(self.root, "patterns", "S90.json")
        study.write_text(path, study.read_text(path).replace('"token": "argmax"', '"token": "argmin"'))
        sess = self.session()
        self.assertIn("pc", sess.errors)
        with self.assertRaises(AiError) as caught:
            sess.lesson("pc")
        self.assertIn("읽을 수 없습니다", str(caught.exception))
        self.assertFalse(any(c.startswith("pc-") for c in sess.cards))

    def test_not_ready_without_items(self):
        shutil.rmtree(os.path.join(self.root, "items", "pc"))
        sess = self.session()
        with self.assertRaises(AiError) as caught:
            sess.lesson("pc")
        self.assertIn("준비 중", str(caught.exception))
        self.assertFalse(sess.overview()["patterns"][0]["ready"])


class PatternStepsTest(PatternBase):
    def test_blocks(self):
        sess = self.session()
        steps = sess.unit_steps("pc", "18a")
        self.assertEqual(self.UNIT, steps["name"])
        blocks = [b for s in steps["steps"] for b in s["blocks"]]
        text = "\n".join(b.get("markdown", "") for b in blocks)
        self.assertNotIn("<!--", text)
        diff = next(b for b in blocks if b["kind"] == "diff")
        self.assertEqual((2, 6, 8, "가", "나"), (diff["different"], diff["same"], len(diff["rows"]), diff["left"], diff["right"]))
        rotate = next(b for b in blocks if b["kind"] == "rotate")
        self.assertEqual(("t1", "S90", "가"), (rotate["id"], rotate["skel"], rotate["variant"]))
        self.assertTrue(rotate["code"].startswith("net.train()\n"))
        self.assertEqual(["pc-k01", "pc-k02", "pc-k03", "pc-k04", "pc-k05", "pc-k06"], [s["id"] for s in rotate["slots"]])
        self.assertEqual({"id", "line", "token", "hint", "mode", "code"}, set(rotate["slots"][0]))
        self.assertFalse(any(b.get("error") for b in blocks))

    def test_unknown_variant_is_an_error_block(self):
        page = os.path.join(self.root, "learn", "l18", "page.md")
        study.write_text(page, study.read_text(page).replace('"right": "나"', '"right": "다"').replace('"variant": "가"}', '"variant": "가", "slots": ["pc-k09"]}'))
        sess = self.session()
        blocks = [b for s in sess.unit_steps("pc", "18a")["steps"] for b in s["blocks"]]
        self.assertIn("다", next(b for b in blocks if b["kind"] == "diff")["error"])
        self.assertIn("pc-k09", next(b for b in blocks if b["kind"] == "rotate")["error"])

    def test_check_rotate(self):
        sess = self.session()
        self.assertEqual({"ok": True, "answer": "zero_grad"}, sess.check_rotate("pc", "18a", "t1", "pc-k02", "opt.zero_grad()"))
        self.assertEqual({"ok": False, "answer": "argmax"}, sess.check_rotate("pc", "18a", "t1", "pc-k05", "max"))
        self.assertTrue(sess.check_rotate("pc", "18a", "t1", "pc-k05", "argmax(1)")["ok"])
        rows = self.log(sess, "recall")
        self.assertEqual([("t1", "pc-k02", True), ("t1", "pc-k05", False), ("t1", "pc-k05", True)],
                         [(r["id"], r["slot"], r["ok"]) for r in rows])
        self.assertEqual(("pc", "18a"), (rows[0]["lesson"], rows[0]["unit"]))
        sess.check_rotate("pc", "18a", "t1", "pc-k02", "step", readonly=True)
        self.assertEqual(3, len(self.log(sess, "recall")))
        self.assertIsNone(sess._state().box("pc-k02"))
        for args in (("t9", "pc-k02"), ("t1", "pc-k99")):
            with self.assertRaises(AiError):
                sess.check_rotate("pc", "18a", args[0], args[1], "x")


class PatternPlanTest(PatternBase):
    def test_next_card_offers_the_pattern_unit_after_its_lesson(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        sess.mark_read("i90", "90b")
        got = sess.overview()["next"]
        self.assertEqual(("unit", "pc", "18a", self.UNIT, self.UNIT), (got["kind"], got["lesson"], got["unit"], got["title"], got["name"]))
        self.assertEqual(self.UNIT, sess.title_of("unit", "pc", "18a"))

    def test_revisit_can_pick_a_pattern_unit(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        sess.mark_read("i90", "90b")
        for card in sess.cards.values():
            if card["lesson"] == "i90" and card["core"]:
                self.answer(sess, card["id"])
        sess.mark_read("pc", "18a")
        overview = sess.overview()  # 18a 만 막 읽은 기록에서 오류 없이 돎
        self.assertEqual(("revisit", "pc", "18a"), (overview["next"]["kind"], overview["next"]["lesson"], overview["next"]["unit"]))
        self.assertEqual(("다시 보기 · " + self.UNIT, self.UNIT), (overview["next"]["title"], overview["next"]["name"]))
        found = sess.revisit()
        self.assertEqual(("pc", "18a", self.UNIT), (found["lesson"], found["unit"], found["name"]))
        self.assertEqual(3, len(found["memo"]))
        mixed = sess.start_set("mixed", lesson="pc", unit="18a", seed=4)
        self.assertTrue(all(c.startswith("pc-") for c in [e["card"] for e in mixed.queue][:3]))

    def test_revisit_lead_keeps_slots_after_their_choices(self):
        # k01 만 상자 1 로 날짜가 되면 lead 정렬(날짜, 상자)이 k01 을 맨 앞에 두는데, k01 은 판 전체를 보여 o01·p01 의 답이 됨
        sess = self.session()
        sess.mark_read("pc", "18a")
        for cid in ("pc-k01", "pc-o01", "pc-p01"):
            self.answer(sess, cid)
        for cid in ("pc-o01", "pc-p01"):
            self.answer(sess, cid, day="10")
        self.at = "2026-11-11T20:00:00"
        state = sess._state()
        self.assertEqual((1, ["pc-k01"]), (state.box("pc-k01"), [c for c in state.due_cards() if c.startswith("pc-")]))
        for seed in range(6):
            order = [e["card"] for e in sess.start_set("mixed", lesson="pc", unit="18a", seed=seed).queue]
            self.assertEqual((["pc-o01", "pc-p01"], "pc-k01"), (order[:2], order[2]), order)

    def test_revisit_lead_pulls_the_cards_it_waits_for(self):
        sess = self.session()
        rest = [("i90-b01", "rest"), ("pc-x01", "due"), ("pc-o01", "rest")]
        self.assertEqual((["pc-o01", "pc-x01", "pc-k02"], [("i90-b01", "rest")]), service._hold_lead(sess, ["pc-k02"], rest))


class PatternSetTest(PatternBase):
    def test_choose_separates_pick_from_a_change_that_reveals_its_line(self):
        sess = self.session()
        state = sess._state()
        for ids in (["pc-p01", "pc-x01"], ["pc-x01", "pc-p01"]):
            chosen = service._choose(sess, state, [("rest", ids)], 20, random.Random(7))
            self.assertEqual([(ids[0], "rest")], chosen)
        chosen = service._choose(sess, state, [("rest", ["pc-x01", "i90-b01"])], 20, random.Random(7),
                                 taken=[("pc-p01", "lead")])
        self.assertEqual([("pc-p01", "lead"), ("i90-b01", "rest")], chosen)

    def test_choose_keeps_pick_when_the_change_edits_other_lines(self):
        path = os.path.join(self.root, "patterns", "S90.json")
        data = study.read_json(path)
        data["variants"]["나"]["lines"][7] = data["variants"]["가"]["lines"][7]
        data["variants"]["나"]["lines"][5] = "    e.backward(retain_graph=True)"
        study.write_text(path, json.dumps(data, ensure_ascii=False))
        sess = self.session()
        chosen = service._choose(sess, sess._state(), [("rest", ["pc-p01", "pc-x01"])], 20, random.Random(7))
        self.assertEqual([("pc-p01", "rest"), ("pc-x01", "rest")], chosen)

    def test_locked_until_read_then_core_first(self):
        sess = self.session()
        with self.assertRaises(AiError):
            sess.start_set("unit", lesson="pc", unit="18a", seed=1)
        sess.mark_read("pc", "18a")
        ps = sess.start_set("unit", lesson="pc", unit="18a", seed=1)
        self.assertEqual(["pc-o01", "pc-p01", "pc-k01"], [e["card"] for e in ps.queue])
        self.assertEqual(self.UNIT, ps.title)
        chips = {}
        while ps.current() is not None:
            cur = ps.current()
            chips[cur["card"]] = (cur["chips"], cur["kind"], cur["code_options"], cur["grid"], cur["code"])
            ps.answer(self.right(ps, cur), 1, True)
            ps.next()
        self.assertEqual((["학습 루프", "순서 고르기"], "choice", True, 2, False), chips["pc-o01"])
        self.assertEqual((["학습 루프", "고르기"], "choice", True, 1, False), chips["pc-p01"])
        self.assertEqual((["학습 루프", "코드 빈칸"], "blank", False, 1, True), chips["pc-k01"])

    def test_pick_cards_before_slot_cards_and_one_family(self):
        sess = self.session()
        sess.mark_read("pc", "18a")
        for cid in ("pc-k01", "pc-o01", "pc-p01"):
            self.answer(sess, cid)
            self.answer(sess, cid, day="10")
        self.at = "2026-11-12T20:00:00"
        state = sess._state()
        self.assertTrue(state.core_ready("pc", "18a"))
        for seed in range(12):
            ps = sess.start_set("unit", lesson="pc", unit="18a", seed=seed)
            order = [e["card"] for e in ps.queue]
            self.assertLessEqual(len({"pc-k05", "pc-k06", "pc-p01"} & set(order)), 1, order)
            slots = [n for n, c in enumerate(order) if c.startswith("pc-k")]
            picks = [n for n, c in enumerate(order) if c[3] in "opx"]
            self.assertTrue(not slots or not picks or max(picks) < min(slots), order)
        chosen = [(c, "rest") for c in ("pc-k02", "pc-k04", "pc-o01", "pc-x01")]
        for seed in range(20):
            seq = service._arrange(sess, state, list(chosen), random.Random(seed))
            self.assertEqual({"pc-o01", "pc-x01"}, set(seq[:2]), seq)

    def test_change_waits_for_the_choices_of_its_variants(self):
        # x01 의 같은 줄 보기(가 판 줄)가 같은 묶음 뒤 pick 의 답과 order 의 줄 순서를 보이지 않게 x01 을 그 뒤에 냄
        sess = self.session()
        state = sess._state()
        chosen = [(c, "rest") for c in ("pc-x01", "pc-k02", "pc-p01", "pc-o01")]
        for seed in range(20):
            seq = service._arrange(sess, state, list(chosen), random.Random(seed))
            self.assertEqual(({"pc-o01", "pc-p01"}, "pc-x01", "pc-k02"), (set(seq[:2]), seq[2], seq[3]), seq)

    def test_lesson_mode_adds_pattern_cards_after_reading(self):
        sess = self.session()
        ps = sess.start_set("lesson", lesson="i90", seed=3)
        self.assertFalse(any(e["card"].startswith("pc-") for e in ps.queue))
        sess.mark_read("pc", "18a")
        ps = sess.start_set("lesson", lesson="i90", seed=3)
        cards = {e["card"] for e in ps.queue}
        self.assertTrue({"pc-o01", "pc-p01", "pc-k01"} <= cards, cards)
        self.assertFalse({"pc-k02", "pc-x01"} & cards)

    def test_mixed_and_review_with_pattern_cards(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        sess.mark_read("pc", "18a")
        for cid in ("pc-k01", "pc-o01", "pc-p01", "i90-b01"):
            self.answer(sess, cid, result="stuck")
        self.at = "2026-11-10T20:00:00"
        for mode in ("mixed", "review"):
            ps = sess.start_set(mode, seed=7)
            self.assertTrue(any(e["card"].startswith("pc-") for e in ps.queue), mode)
            self.play(ps, lambda cur: "pass")


class PatternAnswerTest(PatternBase):
    def test_slot_answer_records_fade_masked_and_also(self):
        sess = self.opened_slots()
        ps = service.PracticeSet(sess, "s1", "unit", ["pc-k02"], 1)
        cur = ps.current()
        self.assertEqual(2, len(cur["blanks"]))
        self.assertIn("net.____()", cur["stem"])
        feedback = ps.answer(["eval", "zero_grad"], 3, True)
        self.assertEqual(("pass", [{"blank": 0, "slot": "pc-k01"}], ["train", "zero_grad"]),
                         (feedback["result"], feedback["also"], feedback["correct"]))
        row = self.log(sess, "answer")[-1]
        self.assertEqual(({"pc-k01": "stuck"}, {"pc-k01": "eval"}, 1, ["pc-k01"], False),
                         (row["also"], row["also_value"], row["fade"], row["masked"], row["whole"]))
        self.assertIn("seed", row)
        self.assertNotIn("value", row)
        self.at = "2026-11-11T20:00:00"
        self.assertEqual((1, "2026-11-11"), (sess._state().box("pc-k01"), str(sess._state().due_day("pc-k01"))))
        ps = service.PracticeSet(sess, "s2", "unit", ["pc-k04"], 2)
        blanks = ps._view(ps.queue[0])["item"]["blanks"]
        self.assertEqual("pc-k04", blanks[-1]["slot"])  # 칸은 코드 위치 순이라 마지막 줄의 주 자리가 끝
        ps.answer(["x"] * (len(blanks) - 1) + ["step"], 3, True)
        row = self.log(sess, "answer")[-1]
        self.assertEqual("pass", row["result"])
        self.assertNotIn("value", row)
        self.assertEqual(set(row["masked"]), set(row["also"]))

    def test_override_also_only(self):
        sess = self.opened_slots()
        before = (sess._state().box("pc-k01"), sess._state().due_day("pc-k01"))
        ps = service.PracticeSet(sess, "s1", "unit", ["pc-k02"], 1)
        ps.answer(["eval", "zero_grad"], 3, True)
        size = len(ps.queue)
        result = ps.override()
        self.assertEqual(("pass", True, []), (result["result"], result["overridden"], result["also"]))
        self.assertEqual(size, len(ps.queue))
        row = self.log(sess, "override")[-1]
        self.assertEqual(({"pc-k01": "eval"}, "pc-k02"), (row["also_value"], row["card"]))
        self.assertNotIn("value", row)
        self.assertEqual(before, (sess._state().box("pc-k01"), sess._state().due_day("pc-k01")))
        with self.assertRaises(AiError):
            ps.override()

    def test_override_main_and_also(self):
        sess = self.opened_slots()
        ps = service.PracticeSet(sess, "s1", "unit", ["pc-k02"], 1)
        feedback = ps.answer(["eval", "step"], 3, True)
        self.assertEqual("stuck", feedback["result"])
        ps.override()
        row = self.log(sess, "override")[-1]
        self.assertEqual((["eval", "step"], {"pc-k01": "eval"}), (row["value"], row["also_value"]))
        from aiprep import review
        events = review.card_events(sess.record.log)
        self.assertEqual("pass", events["pc-k02"][-1]["result"])
        self.assertEqual(["answer"], [e["src"] for e in events["pc-k01"]])

    def test_dont_know_keeps_the_view(self):
        sess = self.opened_slots()
        ps = service.PracticeSet(sess, "s1", "unit", ["pc-k02", "pc-x01"], 1)
        ps.dont_know(2)
        row = self.log(sess, "answer")[-1]
        self.assertEqual((True, 1, ["pc-k01"]), (row["dontknow"], row["fade"], row["masked"]))
        self.assertNotIn("also", row)
        with self.assertRaises(AiError):
            ps.override()


class PatternNotesTest(PatternBase):
    def test_slot_and_choice_are_redrawn(self):
        sess = self.opened_slots()
        ps = service.PracticeSet(sess, "s1", "unit", ["pc-k02", "pc-o01"], 1)
        stem = ps.current()["stem"]
        ps.answer(["train", "step"], 3, True)
        ps.next()
        cur = ps.current()
        view = ps._view(ps.queue[ps.pos])["item"]
        wrong = [o["no"] for o in cur["options"] if not view["options"][o["no"]]["ok"]][:1]
        ps.answer(wrong, 3, True)
        detail = sess.wrong_item("pc-k02")
        self.assertEqual((stem, ["train", "step"], self.UNIT, False, "blank"),
                         (detail["stem"], detail["mine"], detail["name"], detail["code_options"], detail["kind"]))
        self.assertEqual(["zero_grad", "train"][::-1], sess.explain("pc-k02")["answer"])
        detail = sess.wrong_item("pc-o01")
        self.assertEqual(([o["text"] for o in view["options"]], True, [view["options"][wrong[0]]["text"]]),
                         (detail["options"], detail["code_options"], detail["mine"]))
        groups = sess.wrong_notes()
        group = next(g for g in groups if g["title"] == "상황별 코드")
        labels = {i["key"]: i["label"] for i in group["items"]}
        self.assertEqual("코드 빈칸 · 상황별 코드", labels["pc-k02"])
        self.assertEqual("순서 고르기 · 상황별 코드", labels["pc-o01"])

    def test_masked_only_wrong_shows_what_i_wrote(self):
        sess = self.opened_slots()
        ps = service.PracticeSet(sess, "s1", "unit", ["pc-k02"], 1)
        ps.answer(["eval", "zero_grad"], 3, True)
        detail = sess.wrong_item("pc-k01")
        self.assertEqual((["eval"], "net.____()"), (detail["mine"], sess.cards["pc-k01"]["head"]))
        self.assertEqual(1, len(sess.cards["pc-k01"]["head"].split("\n")))

    def test_change_back_is_redrawn(self):
        path = os.path.join(self.root, "patterns", "S90.json")
        data = study.read_json(path)
        data["changes"][0]["back"] = "학습 판(가)을 평가 판(나)으로 바꿀 때 고칠 줄을 **모두** 고르세요."
        study.write_text(path, json.dumps(data, ensure_ascii=False))
        sess = self.session()
        sess.mark_read("pc", "18a")
        ps = service.PracticeSet(sess, "s1", "unit", ["pc-x01"], 1)
        ps.queue[0]["again"] = 1
        cur = ps.current()
        self.assertEqual(["학습 루프", "고르기", "다시 나온 문항"], cur["chips"])
        ps.answer([cur["options"][0]["no"]], 2, False)
        row = self.log(sess, "answer")[-1]
        self.assertTrue(row["back"])
        self.assertIn("학습 판(가)을", sess.wrong_item("pc-x01")["stem"])


if __name__ == "__main__":
    unittest.main()
