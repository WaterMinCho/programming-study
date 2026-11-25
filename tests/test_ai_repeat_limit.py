# -*- coding: utf-8 -*-
"""#220 같은 지문 반복을 줄인 규칙을 확인함. 같은 지문은 한 묶음에서 두 번까지 내고 바로 잇지 않음. 다시 낼 지문이 같은 문항을
틀리면 검토한 변형을 끼우고 원문항과 변형은 따로 기록함. 같은 날 다음 묶음은 오늘 마친 문항을 SET_MIN 까지만 채움.

실행: python -m unittest tests.test_ai_repeat_limit
"""
import contextlib
import json
import os
import random
import sqlite3
from unittest import mock

from aiprep import bank, service
from tests.test_ai_service import Base


def text(ps):
    return ps._text(ps.queue[ps.pos])


class SameTextTest(Base):
    def lesson_set(self, seed=5):
        sess = self.session()
        for unit in sess.unit_list("i90"):
            sess.mark_read("i90", unit["key"])
        return sess, sess.start_set("lesson", lesson="i90", seed=seed)

    def run_set(self, ps, decide):
        rows = []
        while (cur := ps.current()) is not None:
            rows.append((cur["card"], text(ps)))
            if decide(cur) == "pass":
                ps.answer(self.right(ps, cur), 1, True)
            else:
                ps.dont_know(1)
            ps.next()
        return rows

    def test_fixed_card_shows_same_text_at_most_twice(self):
        sess, ps = self.lesson_set()
        target = "i90-b02"
        self.assertIn(target, [e["card"] for e in ps.queue])
        rows = self.run_set(ps, lambda cur: "fail" if cur["card"] == target else "pass")
        self.assertEqual(2, [c for c, _ in rows].count(target))
        self.assertIn(target, ps.summary()["left"])
        self.assertIn(target, ps.summary()["again"])
        self.assertIn(target, sess._state().again)

    def test_same_text_never_back_to_back(self):
        for seed in range(1, 8):
            with self.subTest(seed=seed):
                sess, ps = self.lesson_set(seed)
                rows = self.run_set(ps, lambda cur: "fail")
                self.assertFalse(any(a == b for a, b in zip(rows, rows[1:])))
                counts = {}
                for row in rows:
                    counts[row] = counts.get(row, 0) + 1
                fixed = [n for (cid, _), n in counts.items() if sess.cards[cid]["kind"] != "gen"]
                self.assertLessEqual(max(fixed), 2)

    def test_generator_keeps_max_fail(self):
        sess, ps = self.lesson_set()
        target = next(e["card"] for e in ps.queue if sess.cards[e["card"]]["kind"] == "gen")
        rows = self.run_set(ps, lambda cur: "fail" if cur["card"] == target else "pass")
        shown = [t for c, t in rows if c == target]
        self.assertEqual(len(shown), len(set(shown)))  # 숫자가 매번 바뀌는 문항
        self.assertEqual(service.MAX_FAIL, len(shown))

    def test_pass_after_fail_ends_in_set_and_stays_for_next_set(self):
        sess, ps = self.lesson_set()
        target = "i90-b02"
        state = {"n": 0}

        def decide(cur):
            if cur["card"] != target:
                return "pass"
            state["n"] += 1
            return "fail" if state["n"] == 1 else "pass"
        rows = self.run_set(ps, decide)
        self.assertEqual(2, [c for c, _ in rows].count(target))
        answers = [(e["result"], e["again"]) for e in self.log(sess, "answer") if e["card"] == target]
        self.assertEqual([("stuck", 0), ("pass", 1)], answers)
        self.assertNotIn(target, ps.summary()["left"])
        self.assertIn(target, ps.summary()["again"])
        self.assertIn(target, sess._state().again)  # 두 번 이어 맞혀야 빠지는 규칙(plan.again_cards)은 그대로
        nxt = sess.start_set("lesson", lesson="i90", seed=11)
        self.assertIn(target, [e["card"] for e in nxt.queue])

    def test_statement_choice_avoids_shown_option_set(self):
        sess, ps = self.lesson_set()
        state = sess._state()
        card = sess.cards["i90-s01"]  # 참 문장. 같은 주제의 거짓 문장이 넷이라 보기 조합이 넷임
        first = ps._statement_choice(card, state, random.Random(3), 0)
        shown = {o["id"] for o in first["options"]}
        for seed in range(20):
            again = ps._statement_choice(card, state, random.Random(seed), 1, [shown])
            self.assertNotEqual(shown, {o["id"] for o in again["options"]})
            self.assertIn("i90-s01", {o["id"] for o in again["options"]})

    def test_statement_card_compares_question_and_answer_not_options(self):
        # 문장 카드는 다시 낼 때 오답 보기만 바뀌므로 발문과 정답 문장으로 같은 지문을 셈
        sess, ps = self.lesson_set()
        target = "i90-s01"
        rows = self.run_set(ps, lambda cur: "fail" if cur["card"] == target else "pass")
        shown = [e for e in ps.queue if e["card"] == target]
        self.assertEqual(2, len(shown))
        self.assertNotEqual(set(shown[0]["view"]["shown"]), set(shown[1]["view"]["shown"]))
        self.assertEqual(1, len({t for c, t in rows if c == target}))
        self.assertIn(target, ps.summary()["left"])


class VariantTest(Base):
    def unit_set(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=3)
        self.assertEqual(["i90-b01", "i90-b02", "i90-b03"], [e["card"] for e in ps.queue])
        return sess, ps

    def until(self, ps, target):
        while ps.current()["card"] != target:
            ps.answer(self.right(ps, ps.current()), 1, True)
            ps.next()

    def test_wrong_fixed_card_gets_variant_without_core_lock(self):
        sess, ps = self.unit_set()
        state = sess._state()
        self.assertFalse(state.eligible_new(sess.cards["i90-g01"]))  # 묶음을 만들 때는 핵심 상자 조건으로 막힘
        self.until(ps, "i90-b03")
        ps.answer(["틀린 답"], 1, False)
        self.assertEqual([("i90-b03", 0, None), ("i90-g01", 0, "i90-b03"), ("i90-b03", 1, None)],
                         [(e["card"], e["again"], e.get("for")) for e in ps.queue[ps.pos:]])
        self.assertIn("i90-g01", ps.stats)

    def test_variant_and_original_are_recorded_and_counted_separately(self):
        sess, ps = self.unit_set()
        self.until(ps, "i90-b03")
        ps.dont_know(1)
        ps.next()
        self.assertEqual("i90-g01", ps.current()["card"])
        ps.dont_know(1)
        ps.next()
        while ps.current() is not None:
            ps.answer(self.right(ps, ps.current()), 1, True)
            ps.next()
        rows = [e for e in self.log(sess, "answer") if e["card"] in ("i90-b03", "i90-g01")]
        self.assertEqual([("i90-b03", "stuck", 0), ("i90-g01", "stuck", 0), ("i90-b03", "pass", 1)],
                         [(e["card"], e["result"], e["again"]) for e in rows][:3])
        keys = {"kind", "set", "card", "result", "dontknow", "secs", "again", "seed", "sure", "at", "content_revision",
                "content_revisions"}
        self.assertTrue(all(set(e) <= keys for e in rows))  # 답 행에 새 키가 없음
        summary = ps.summary()
        self.assertEqual(4, summary["n"])
        self.assertEqual("stuck", ps.stats["i90-g01"]["first"])
        self.assertIn("i90-b03", summary["again"])
        state = sess._state()
        self.assertEqual(1, state.box("i90-b03"))
        self.assertIsNotNone(state.box("i90-g01"))  # 변형은 자기 답으로 상자가 정해짐
        self.assertNotIn("i90-g01", state.again)  # 변형은 뒤에 두 번 이어 맞혀 빠짐
        self.assertEqual(4, self.log(sess, "set_end")[-1]["n"])

    def test_variant_is_kept_in_snapshot_and_removed_by_override(self):
        sess, ps = self.unit_set()
        self.until(ps, "i90-b03")
        size, memorised = len(ps.queue), ps.memorised_before
        ps.answer(["틀린 답"], 1, False)
        self.assertEqual(size + 2, len(ps.queue))
        restored = service.PracticeSet.restore(sess, json.loads(json.dumps(ps.snapshot())))
        self.assertEqual(ps.queue, restored.queue)
        self.assertEqual(ps.stats, restored.stats)
        resumed = self.session().resume_set()
        self.assertEqual([e.get("for") for e in ps.queue], [e.get("for") for e in resumed.queue])
        result = resumed.override()
        self.assertEqual("pass", result["result"])
        self.assertEqual(size, len(resumed.queue))
        self.assertFalse(any(e.get("for") for e in resumed.queue))
        self.assertNotIn("i90-g01", resumed.stats)
        self.assertNotIn("i90-g01", resumed.before)
        self.assertEqual(memorised, resumed.memorised_before)
        self.assertIsNone(resumed.next())
        self.assertEqual(3, resumed.summary()["n"])

    def test_wrong_notes_list_original_and_variant_separately(self):
        sess = self.session()
        ps = sess.start_set("lesson", lesson="i90", seed=1)  # 단원을 읽지 않고 차시를 열어 오답 노트에 들어감
        self.until(ps, "i90-b03")
        ps.answer(["틀린 답"], 1, False)
        ps.next()
        while ps.current() is not None:
            cur = ps.current()
            if cur["card"] == "i90-g01":
                ps.dont_know(1)
            else:
                ps.answer(self.right(ps, cur), 1, True)
            ps.next()
        listed = {item["key"] for group in sess.wrong_notes() for item in group["items"]}
        self.assertTrue({"i90-b03", "i90-g01"} <= listed)
        note = sess.start_set("note", card="i90-b03", seed=2)
        self.assertEqual("i90-b03", note.queue[0]["card"])

    def test_completed_today_or_listed_variant_is_not_inserted(self):
        sess, ps = self.unit_set()
        sess._append({"kind": "answer", "card": "i90-g01", "set": "earlier", "result": "pass", "again": 0})
        self.until(ps, "i90-b03")
        ps.answer(["틀린 답"], 1, False)
        self.assertFalse(any(e.get("for") for e in ps.queue))
        self.assertEqual(3, len(ps.queue))  # 남은 문항이 없어 같은 지문을 바로 잇지 않음
        self.assertTrue(ps.stats["i90-b03"]["left"])

    def test_variant_caps_and_other_course(self):
        with mock.patch.object(service, "RETRY_VARIANT_MAX", 0):
            sess, ps = self.unit_set()
            self.until(ps, "i90-b03")
            ps.answer(["틀린 답"], 1, False)
            self.assertFalse(any(e.get("for") for e in ps.queue))
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=3)
        sess.cards["a90-b01"] = dict(sess.cards["i90-g01"], id="a90-b01", lesson="a90", family="other")
        with mock.patch.object(service, "_variants", lambda *args, **kw: ["a90-b01"]):
            self.until(ps, "i90-b03")
            ps.answer(["틀린 답"], 1, False)
        self.assertFalse(any(e.get("for") for e in ps.queue))

    def test_variant_with_same_text_as_original_is_redrawn(self):
        sess, ps = self.unit_set()
        self.until(ps, "i90-b03")
        real, drawn = service.PracticeSet._text, []

        def same_first(practice, entry):
            if entry["card"] == "i90-g01" and not drawn:
                drawn.append(entry["seed"])
                return real(practice, ps.queue[ps.pos])
            return real(practice, entry)
        with mock.patch.object(service.PracticeSet, "_text", same_first):
            ps.answer(["틀린 답"], 1, False)
        linked = [e for e in ps.queue if e.get("for")]
        self.assertEqual(["i90-g01"], [e["card"] for e in linked])
        self.assertNotEqual(drawn[0], linked[0]["seed"])

    def test_variant_always_same_as_original_is_not_inserted(self):
        sess, ps = self.unit_set()
        self.until(ps, "i90-b03")
        real = service.PracticeSet._text
        with mock.patch.object(service.PracticeSet, "_text",
                               lambda practice, entry: real(practice, ps.queue[ps.pos] if entry["card"] == "i90-g01" else entry)):
            ps.answer(["틀린 답"], 1, False)
        self.assertFalse(any(e.get("for") for e in ps.queue))
        self.assertNotIn("i90-g01", ps.stats)

    def test_snapshot_saved_before_this_change_restores(self):
        sess, ps = self.unit_set()
        self.until(ps, "i90-b02")
        ps.answer(["틀린 답"], 1, False)
        saved = json.loads(json.dumps(ps.snapshot()))
        saved.pop("fill")
        saved["_undo"][0] = saved["_undo"][0][:2]  # 예전 되돌리기 값은 (큐, 상태) 두 개
        for entry in saved["queue"][ps.pos + 1:]:
            entry.pop("view", None)
        restored = service.PracticeSet.restore(sess, saved)
        self.assertIsNone(restored.fill)
        self.assertEqual("pass", restored.override()["result"])
        self.assertEqual("i90-b03", restored.next()["card"])


class AppVariantTest(Base):
    def test_real_bank_wrong_card_gets_reviewed_variant(self):
        sess = service.AiSession("app", home=os.path.join(self.tmp, "app"), root=bank.AI_DIR, course="app")
        ps = sess.start_set("lesson", lesson="a01", seed=7)
        state = sess._state()
        families = {sess.cards[c]["family"] for c in ps.stats}

        def linkable(cid):
            card = sess.cards[cid]
            return any(v not in ps.stats and (sess.cards[v]["family"] == card["family"] or sess.cards[v]["family"] not in families)
                       for v in service._variants(state, card, fixed=True, ready=False))
        target = next(e["card"] for e in ps.queue if sess.cards[e["card"]]["kind"] in ("blank", "choice")
                      and not isinstance(sess.cards[e["card"]]["item"].get("alt"), dict) and linkable(e["card"]))
        while ps.current()["card"] != target:
            ps.answer(self.right(ps, ps.current()), 1, True)
            ps.next()
        at = ps.pos
        ps.dont_know(1)
        linked = [n for n, e in enumerate(ps.queue) if e.get("for") == target]
        self.assertEqual([at + 1 + service.GAP_WRONG], linked)
        back = [n for n, e in enumerate(ps.queue) if e["card"] == target and n > at]
        self.assertEqual([min(linked[0] + 1 + service.GAP_CONFIRM, len(ps.queue) - 1)], back)


    def test_pending_pair_is_used_instead_of_new_variant(self):
        sess = service.AiSession("note", home=os.path.join(self.tmp, "note"), root=bank.AI_DIR, course="app")
        sess._append({"kind": "open", "lesson": "a01"})
        sess._append({"kind": "answer", "card": "a01-b19", "set": "earlier", "result": "stuck", "again": 0})
        ps = sess.start_set("note", card="a01-b19", seed=7)
        self.assertEqual(["a01-b19", "a01-c08"], [e["card"] for e in ps.queue])
        ps.dont_know(1)
        self.assertEqual(["a01-b19", "a01-c08", "a01-b19"], [e["card"] for e in ps.queue])
        self.assertFalse(any(e.get("for") for e in ps.queue))
        ps.next()
        while ps.current() is not None:
            ps.answer(self.right(ps, ps.current()), 1, True)
            ps.next()
        rows = [(e["card"], e["result"], e["again"]) for e in self.log(sess, "answer") if e["set"] == ps.id]
        self.assertEqual([("a01-b19", "stuck", 0), ("a01-c08", "pass", 0), ("a01-b19", "pass", 1)], rows)
        self.assertIn("a01-b19", sess._state().again)


class CompletedTodayTest(Base):
    def finish(self, sess, mode, seed=3, **kw):
        ps = sess.start_set(mode, seed=seed, **kw)
        while (cur := ps.current()) is not None:
            ps.answer(self.right(ps, cur), 1, True)
            ps.next()
        return ps

    def test_lesson_set_puts_completed_today_last(self):
        sess = self.session()
        first = set(self.finish(sess, "lesson", lesson="i90").stats)
        trace = {}
        state = sess._state()
        picked = service.build_set(sess, state, "lesson", random.Random(4), lesson="i90", trace=trace)
        done = [c for c in picked if c in first]
        self.assertTrue(set(done) <= state.completed_today)
        self.assertLessEqual(len(picked), service.SET_MIN)
        self.assertTrue(all(trace["selected_pools"][c] == "done" for c in done))
        pool = next(p for p in trace["candidate_pools"] if p["name"] == "done")
        self.assertTrue(pool["overflow"])
        self.assertEqual(sorted(state.completed_today & set(pool["ids"])), sorted(pool["ids"]))

    def test_cards_wrong_today_come_first_in_done_pool(self):
        sess = self.session()
        ps = sess.start_set("lesson", lesson="i90", seed=3)
        wrong = ps.current()["card"]
        while (cur := ps.current()) is not None:
            if cur["card"] == wrong and not cur["again"]:
                ps.dont_know(1)
            else:
                ps.answer(self.right(ps, cur), 1, True)
            ps.next()
        if wrong in sess._state().again:  # 한 번만 맞혔으면 again 에 남으니 한 번 더 맞힘
            sess._append({"kind": "answer", "card": wrong, "set": "extra", "result": "pass", "again": 2})
        trace = {}
        service.build_set(sess, sess._state(), "lesson", random.Random(4), lesson="i90", trace=trace)
        pool = next(p for p in trace["candidate_pools"] if p["name"] == "done")
        self.assertEqual(wrong, pool["ids"][0])

    def test_start_set_notes_how_completed_cards_were_used(self):
        sess = self.session()
        first = set(self.finish(sess, "lesson", lesson="i90").stats)
        ps = sess.start_set("lesson", lesson="i90", seed=4)
        self.assertEqual(sum(e["card"] in first for e in ps.queue), ps.fill["done"])
        self.assertGreater(ps.fill["done"], 0)
        self.assertGreater(ps.fill["skipped"], 0)
        restored = self.session().resume_set()
        self.assertEqual(ps.fill, restored.fill)

    def test_fill_note_only_when_done_cards_would_have_fitted(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        self.finish(sess, "unit", lesson="i90", unit="90a")
        sess.mark_read("i90", "90b")
        with mock.patch.object(service, "SET_SIZE", 3), mock.patch.object(service, "SET_MIN", 2):
            ps = sess.start_set("unit", lesson="i90", unit="90b", seed=5)
        self.assertEqual(3, len(ps.queue))
        self.assertIsNone(ps.fill)  # 새 문항만으로 찼으니 오늘 마친 문항을 빼서 짧아진 것이 아님
        ps = sess.start_set("unit", lesson="i90", unit="90b", seed=5)
        self.assertLess(len(ps.queue), service.SET_SIZE)
        self.assertIsNotNone(ps.fill)
        for cid in ("i90-b01", "i90-b02", "i90-b03"):  # 오늘 마친 문항이 새 문항과 문항군이 겹쳐 빼지 않았어도 못 들어감
            sess.cards[cid] = dict(sess.cards[cid], family="i90-b04")
        ps = sess.start_set("unit", lesson="i90", unit="90b", seed=5)
        self.assertLess(len(ps.queue), service.SET_SIZE)
        self.assertIsNone(ps.fill)

    def test_real_bank_third_lesson_set_skips_cards_done_today(self):
        sess = service.AiSession("intro", home=os.path.join(self.tmp, "intro"), root=bank.AI_DIR)
        seen = set()
        for seed in (7, 8, 9):
            ps = self.finish(sess, "lesson", seed=seed, lesson="i01")
            cards = [e["card"] for e in ps.queue]
            if len(cards) > service.SET_MIN:
                self.assertFalse(set(cards) & seen)
            seen.update(cards)

    def test_manual_unit_practice_still_opens_after_all_done(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        self.finish(sess, "unit", lesson="i90", unit="90a")
        sess.mark_read("i90", "90b")
        self.finish(sess, "unit", lesson="i90", unit="90b")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=5)
        self.assertTrue(ps.queue)


class LinkedSourceRecordTest(VariantTest):
    """끼운 변형의 원문항과 묶음 규칙 이름이 수집 기록에만 남고 학습 기록 행은 그대로인지 확인함."""

    def collected(self, sess, kind):
        with contextlib.closing(sqlite3.connect(sess.collection.path)) as conn:
            return [json.loads(r[0]) for r in conn.execute("SELECT payload FROM events WHERE kind=? ORDER BY seq", (kind,))]

    def test_linked_variant_records_original_card_and_rules(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=3)
        self.until(ps, "i90-b03")
        ps.answer(["틀린 답"], 1, False)
        ps.next()
        self.assertEqual("i90-g01", ps.current()["card"])
        shown = {(e["card"], e["again"]): e for e in self.collected(sess, "question_returned")}
        self.assertEqual("i90-b03", shown[("i90-g01", 0)]["queued_for"])
        self.assertNotIn("queued_for", shown[("i90-b03", 0)])
        self.assertEqual({"retry-v2"}, {e["retry_policy"] for e in shown.values()})
        selection = self.collected(sess, "set")[0]["selection"]
        self.assertEqual(("rules-v9", "retry-v2"), (selection["policy"], selection["retry_policy"]))
        for row in self.log(sess):
            self.assertFalse({"queued_for", "retry_policy", "selection"} & set(row))

    def test_policy_name_distinguishes_scoped_and_course_wide_sets(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        state = sess._state()
        for mode in ("unit", "mixed", "lesson", "review", "sweep", "note"):
            kwargs = {"lesson": "i90", "unit": "90a"}
            if mode == "note":
                kwargs["card"] = "i90-b01"
            trace = {}
            service.build_set(sess, state, mode, random.Random(4), trace=trace, **kwargs)
            with self.subTest(mode=mode):
                self.assertEqual("retry-v2", trace["retry_policy"])
                expected = {"unit": "rules-v9", "mixed": "rules-v8", "lesson": "rules-v6"}
                self.assertEqual(expected.get(mode, "rules-v2"), trace["policy"])
