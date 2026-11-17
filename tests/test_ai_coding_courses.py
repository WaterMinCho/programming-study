# -*- coding: utf-8 -*-
"""과정마다 코딩 실습 무리를 따로 두는 엔진 규칙을 확인함. tests/aifix.apc_bank 는 개론 무리 pc(뼈대 patterns/S90)와 응용 무리
apc(뼈대 patterns/apc/S190)를 함께 둔 은행이고, app_lesson 은 응용 차시 a90 을 실제로 읽히게 함.

과정별 노출, 기록·수집의 과정 값, 복습·오답 후보, 뼈대 폴더 분리와 같은 id 오류, 뼈대 오류 격리, 미완료 묶음 복원, 카드 키 집합을 봄.
S190 의 note_only 자리(apc-n101, apc-n102)는 노트의 돌려 가며 빈칸에서만 쓰고 카드가 되지 않는지, 응용 무리의 생성 문항
apc-g101 이 단원 연습·수집에 응용 과정으로 들어가는지도 봄.

실행: python -m unittest tests.test_ai_coding_courses
"""
import contextlib
import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import bank, notes, service, skel  # noqa: E402
from learning_server import dataset  # noqa: E402
from tests import aifix  # noqa: E402

SKEL_CARD_KEYS = {"id", "kind", "lesson", "unit", "step", "facts", "core", "prio", "family", "confuse", "level", "tags", "deep",
                  "errata", "ref", "order", "part", "pattern", "variant", "after", "name", "head", "situations", "entry"}
APC_CARDS = ["apc-g101", "apc-k01", "apc-k02", "apc-k03", "apc-k04", "apc-k05", "apc-k06", "apc-o01", "apc-p01", "apc-x01"]
NOTE_SLOTS = ["apc-n101", "apc-n102"]


class CodingBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ai_coding_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.object(study, "SUBMISSIONS_DIR", os.path.join(self.tmp, "subs"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.at = "2026-11-09T20:00:00"
        patcher = mock.patch.object(service, "now", lambda: self.at)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = aifix.app_lesson(aifix.apc_bank(os.path.join(self.tmp, "bank")))

    def session(self, course="intro", root=None):
        return service.AiSession("alice", home=os.path.join(self.tmp, "home"), root=root or self.root, course=course)

    def path(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def edit_index(self, fn):
        data = study.read_json(self.path("index.json"))
        fn(data)
        study.write_text(self.path("index.json"), json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    def play_wrong(self, practice):
        while True:
            cur = practice.current()
            if cur is None:
                return
            practice.dont_know(2)
            practice.next()


class ExposureTest(CodingBase):
    def test_each_course_sees_only_its_own_group(self):
        intro, app = self.session("intro"), self.session("app")
        self.assertEqual(["pc"], list(intro.patterns))
        self.assertEqual(["apc"], list(app.patterns))
        self.assertEqual({}, intro.errors)
        self.assertEqual({}, app.errors)
        self.assertEqual(["S90"], sorted(intro.skeletons))
        self.assertEqual(["S190"], sorted(app.skeletons))
        self.assertFalse([cid for cid in intro.cards if cid.startswith("apc-")])
        self.assertFalse([cid for cid in app.cards if cid.startswith("pc-")])
        self.assertEqual(APC_CARDS, sorted(cid for cid in app.cards if cid.startswith("apc-")))
        self.assertEqual(["pc"], [row["id"] for row in intro.overview()["patterns"]])
        rows = app.overview()["patterns"]
        self.assertEqual(["apc"], [row["id"] for row in rows])
        first = rows[0]["units"][0]
        self.assertEqual(("a18a", "a90", 90, True), (first["key"], first["after"], first["after_no"], first["ready"]))
        self.assertEqual("응용 루프 · 시험 응용 단원", first["label"])

    def test_course_values_follow_the_index_and_reject_a_mismatch(self):
        groups = {g["id"]: g for g in bank.read_index(self.root)["patterns"]}
        self.assertEqual(("intro", ""), (groups["pc"]["course"], groups["pc"]["folder"]))
        self.assertEqual(("app", "apc"), (groups["apc"]["course"], groups["apc"]["folder"]))
        self.edit_index(lambda d: d["patterns"][1].update(course="intro"))
        with self.assertRaisesRegex(bank.AiBankError, "patterns 의 course"):
            bank.read_index(self.root)
        self.edit_index(lambda d: d["patterns"][1].update(course="app", folder="../items"))
        with self.assertRaisesRegex(bank.AiBankError, "patterns 의 folder"):
            bank.read_index(self.root)

    def test_pc_entry_without_new_keys_reads_as_before(self):
        raw = study.read_json(self.path("index.json"))["patterns"][0]
        self.assertNotIn("course", raw)
        self.assertNotIn("folder", raw)
        self.assertEqual(aifix.PATTERNS, raw)

    def test_card_key_sets_do_not_grow(self):
        intro, app = self.session("intro"), self.session("app")
        for sess, cid in ((intro, "pc-k01"), (app, "apc-k01")):
            self.assertEqual(SKEL_CARD_KEYS, set(sess.cards[cid]))
            self.assertNotIn("course", sess.cards[cid])
        lesson = next(card for card in intro.cards.values() if card["kind"] == "blank")
        self.assertNotIn("course", lesson)
        self.assertNotIn("folder", lesson)

    def test_app_reading_is_recorded_for_the_app_course_only(self):
        app = self.session("app")
        app.mark_read("apc", "a18a")
        row = app.record.log[-1]
        self.assertEqual(("learn", "apc", "a18a", "app"), (row["kind"], row["lesson"], row["unit"], row["course"]))
        self.assertTrue(app.overview()["patterns"][0]["units"][0]["read"])
        intro = self.session("intro")
        self.assertFalse(intro.overview()["patterns"][0]["units"][0]["read"])
        self.assertNotIn(("apc", "a18a"), intro._state().reads)

    def test_unit_steps_fill_blocks_from_the_group_folder(self):
        app = self.session("app")
        steps = app.unit_steps("apc", "a18a")["steps"]
        diff = next(b for s in steps for b in s["blocks"] if b["kind"] == "diff")
        self.assertEqual("S190", diff["skel"])
        self.assertNotIn("error", diff)
        with self.assertRaises(service.AiError):
            self.session("intro").unit_steps("apc", "a18a")


class CollectionCourseTest(CodingBase):
    def events(self, sess, kind):
        with contextlib.closing(sqlite3.connect(sess.collection.path)) as conn:
            return [json.loads(r[0]) for r in conn.execute("SELECT payload FROM events WHERE kind=? ORDER BY seq", (kind,))]

    def answer_first(self, sess, lid, key):
        sess.mark_read(lid, key)
        sess.collection.set_enabled(True)
        practice = sess.start_set("unit", lesson=lid, unit=key)
        cur = practice.current()
        practice.dont_know(2)
        return cur

    def test_app_card_is_collected_as_app(self):
        app = self.session("app")
        cur = self.answer_first(app, "apc", "a18a")
        self.assertTrue(cur["card"].startswith("apc-"))
        for kind in ("question_returned", "answer"):
            row = self.events(app, kind)[0]
            self.assertEqual("app", row["course"])
        items = [r["item"] for r in app.collection.snapshot() if r["kind"] in ("question_returned", "answer")]
        self.assertTrue(items)
        for item in items:
            content = item
            self.assertEqual(("app", "apc", None), (content["course"], content["lesson"], content["course_no"]))
            self.assertEqual("app", dataset.course_fields("ai", content, {"course": "app"})["course"])

    def test_intro_card_is_collected_as_intro(self):
        intro = self.session("intro")
        cur = self.answer_first(intro, "pc", "18a")
        self.assertTrue(cur["card"].startswith("pc-"))
        items = [r["item"] for r in intro.collection.snapshot() if r["kind"] in ("question_returned", "answer")]
        self.assertTrue(items)
        for item in items:
            content = item
            self.assertEqual(("intro", "pc", None), (content["course"], content["lesson"], content["course_no"]))
        self.assertEqual(intro.collection_terms_revision, self.session("app").collection_terms_revision)


class CandidateTest(CodingBase):
    def test_review_and_notes_keep_each_course_apart(self):
        self.at = "2026-11-08T20:00:00"
        app, intro = self.session("app"), self.session("intro")
        app.mark_read("apc", "a18a")
        intro.mark_read("pc", "18a")
        self.at = "2026-11-09T20:00:00"
        self.play_wrong(app.start_set("unit", lesson="apc", unit="a18a"))
        self.play_wrong(intro.start_set("unit", lesson="pc", unit="18a"))
        self.at = "2026-11-10T20:00:00"
        app, intro = self.session("app"), self.session("intro")
        app_due, intro_due = app._state().due_cards(), intro._state().due_cards()
        self.assertTrue(app_due)
        self.assertTrue(all(cid.startswith("apc-") for cid in app_due), app_due)
        self.assertTrue(intro_due)
        self.assertTrue(all(cid.startswith("pc-") for cid in intro_due), intro_due)
        for sess, mine in ((app, "apc-"), (intro, "pc-")):
            trace = {}
            service.build_set(sess, sess._state(), "review", random.Random(3), trace=trace)
            others = [cid for cid in trace["candidate_ids"] if cid.split("-")[0] in ("pc", "apc") and not cid.startswith(mine)]
            self.assertEqual([], others)
            groups = sess.wrong_notes()
            keys = [item["key"] for group in groups for item in group["items"]]
            self.assertTrue(keys)
            self.assertTrue(all(key.startswith(mine) for key in keys), keys)
            self.assertEqual([bank.CODING_TITLE], [group["title"] for group in groups])

    def test_wrong_note_group_title_and_order(self):
        app, intro = self.session("app"), self.session("intro")
        self.assertEqual((bank.CODING_TITLE, (2, "pc")), notes.group_title(intro.cards["pc-k01"], intro.lessons, intro.mocks))
        title, order = notes.group_title(app.cards["apc-k01"], app.lessons, app.mocks, patterns=app.patterns)
        self.assertEqual((bank.CODING_TITLE, (2, "apc")), (title, order))
        self.assertNotIn("0차시", title)


class SkeletonFolderTest(CodingBase):
    def test_default_reads_only_the_top_folder(self):
        self.assertEqual(["S90"], sorted(skel.load_patterns(self.root)))
        self.assertEqual(["S190"], sorted(skel.load_patterns(self.root, "apc")))
        self.assertEqual({}, skel.load_patterns(self.root, "없는폴더"))
        self.assertEqual(["S190", "S90"], sorted(skel.load_all_patterns(self.root)))

    def test_same_id_in_two_folders_is_an_error(self):
        shutil.copy(self.path("patterns/S90.json"), self.path("patterns/apc/S90.json"))
        with self.assertRaisesRegex(bank.AiBankError, "S90"):
            skel.load_patterns(self.root, "apc")
        with self.assertRaisesRegex(bank.AiBankError, "S90"):
            skel.load_all_patterns(self.root)
        self.assertEqual(["S90"], sorted(skel.load_patterns(self.root)))
        intro, app = self.session("intro"), self.session("app")
        self.assertEqual({}, intro.errors)
        self.assertIn("pc-k01", intro.cards)
        self.assertIn("apc", app.errors)
        self.assertFalse([cid for cid in app.cards if cid.startswith("apc-")])

    def test_broken_app_skeleton_keeps_intro_open(self):
        study.write_text(self.path("patterns/apc/S190.json"), "{ 깨진 파일")
        intro = self.session("intro")
        self.assertEqual({}, intro.errors)
        self.assertIsNone(intro.overview()["patterns"][0]["error"])
        self.assertIn("pc-k01", intro.cards)
        intro.mark_read("pc", "18a")
        self.assertTrue(intro.start_set("unit", lesson="pc", unit="18a").queue)
        app = self.session("app")
        row = app.overview()["patterns"][0]
        self.assertTrue(row["error"])
        self.assertFalse([cid for cid in app.cards if cid.startswith("apc-")])

    def test_broken_top_skeleton_keeps_app_open(self):
        study.write_text(self.path("patterns/S90.json"), "{ 깨진 파일")
        app = self.session("app")
        self.assertEqual({}, app.errors)
        self.assertIn("apc-k01", app.cards)
        self.assertTrue(self.session("intro").overview()["patterns"][0]["error"])

    def test_empty_group_folder_is_not_ready(self):
        os.remove(self.path("patterns/apc/S190.json"))
        self.assertFalse(bank.pattern_ready(bank.read_index(self.root)["patterns"][1], self.root))
        self.assertTrue(bank.pattern_ready(bank.read_index(self.root)["patterns"][0], self.root))
        app = self.session("app")
        row = app.overview()["patterns"][0]
        self.assertFalse(row["ready"])
        self.assertFalse(any(unit["ready"] for unit in row["units"]))

    def test_variant_figures_reach_the_question_view_only(self):
        def add(data):
            data["variants"]["가"]["figures"] = {"input": "learn/al18/assets/a18a-1.png", "output": "learn/al18/assets/a18a-2.png"}
        data = study.read_json(self.path("patterns/apc/S190.json"))
        add(data)
        study.write_text(self.path("patterns/apc/S190.json"), json.dumps(data, ensure_ascii=False))
        app = self.session("app")
        self.assertEqual(SKEL_CARD_KEYS, set(app.cards["apc-k01"]))
        app.mark_read("apc", "a18a")
        practice = app.start_set("unit", lesson="apc", unit="a18a")
        seen = {}
        while True:
            cur = practice.current()
            if cur is None:
                break
            seen[cur["card"]] = cur.get("figures")
            practice.dont_know(2)
            practice.next()
        self.assertEqual({"input": self.path("learn/al18/assets/a18a-1.png"), "output": self.path("learn/al18/assets/a18a-2.png")},
                         seen["apc-k01"])
        intro = self.session("intro")
        intro.mark_read("pc", "18a")
        cur = intro.start_set("unit", lesson="pc", unit="18a").current()
        self.assertFalse(cur.get("figures"))
        data["variants"]["가"]["figures"] = {"input": "../밖.png"}
        study.write_text(self.path("patterns/apc/S190.json"), json.dumps(data, ensure_ascii=False))
        with self.assertRaisesRegex(bank.AiBankError, "figures"):
            skel.load_patterns(self.root, "apc")


class ResumeTest(CodingBase):
    """뼈대 폴더를 나누기 전 엔진은 무리가 없는 응용 세션에도 맨 위 뼈대를 읽어 묶음 fingerprint 에 넣었음."""

    def saved_practice(self, sess):
        return sess._local()["practice"]

    def test_app_set_saved_before_the_group_was_added_still_restores(self):
        before = aifix.app_lesson(aifix.pc_bank(os.path.join(self.tmp, "before")))
        app = self.session("app", root=before)
        self.assertEqual(["S90"], sorted(app.skeletons))
        app.mark_read("a90", "a90a")
        practice = app.start_set("unit", lesson="a90", unit="a90a")
        practice.dont_know(2)
        app.save_practice(practice)
        saved = self.saved_practice(app)
        after = self.session("app")
        self.assertEqual(["S190"], sorted(after.skeletons))
        self.assertNotEqual(saved["fingerprint"], service.PracticeSet.restore(after, saved).fingerprint())
        restored = after.resume_set()
        self.assertIsNotNone(restored)
        self.assertEqual(saved["queue"][0]["card"], restored.queue[0]["card"])

    def test_intro_sets_restore_after_the_app_group_is_added(self):
        before = aifix.pc_bank(os.path.join(self.tmp, "before"))
        intro = self.session("intro", root=before)
        versions = dict(intro._card_versions())
        intro.mark_read("pc", "18a")
        practice = intro.start_set("unit", lesson="pc", unit="18a")
        practice.dont_know(2)
        intro.save_practice(practice)
        after = self.session("intro")
        self.assertEqual(versions, {cid: v for cid, v in after._card_versions().items() if cid in versions})
        self.assertIsNotNone(after.resume_set())

    def test_changed_app_skeleton_does_not_restore(self):
        app = self.session("app")
        app.mark_read("apc", "a18a")
        practice = app.start_set("unit", lesson="apc", unit="a18a")
        practice.dont_know(2)
        app.save_practice(practice)
        data = study.read_json(self.path("patterns/apc/S190.json"))
        data["title"] = "바뀐 제목"
        study.write_text(self.path("patterns/apc/S190.json"), json.dumps(data, ensure_ascii=False))
        self.assertIsNone(self.session("app").resume_set())


class NoteReferenceTest(CodingBase):
    def test_app_lesson_reference_reads_app_skeletons(self):
        page = self.path("learn/al90/page.md")
        text = study.read_text(page)
        fence = chr(96) * 3
        marker = "\n### "
        first = text.index(marker)
        second = text.index(marker, first + 1)
        block = '\n%sai-diff\n{"skel": "S190", "left": "가", "right": "나"}\n%s\n' % (fence, fence)
        study.write_text(page, text[:second] + block + text[second:])
        app = self.session("app")
        unit = app.notes["a90"]["units"]["a90a"]
        step = unit["steps"][0]
        ref = {"course": "applied", "lesson": "al90", "unit": "a90a", "step": step["no"], "title": step["title"]}
        data = service.read_note_reference(ref, self.root)
        diff = next(b for b in data["step"]["blocks"] if b["kind"] == "diff")
        self.assertEqual("S190", diff["skel"])
        self.assertNotIn("error", diff)



class NoteOnlySlotTest(CodingBase):
    def group(self, sess):
        return sess.patterns["apc"]

    def test_note_only_slots_do_not_become_cards(self):
        app = self.session("app")
        self.assertEqual({}, app.errors)
        for sid in NOTE_SLOTS:
            self.assertNotIn(sid, app.cards)
        group = next(g for g in bank.read_index(self.root)["patterns"] if g["id"] == "apc")
        units = {"a18a": {"after": "a90", "name": "응용 루프", "title": "시험 응용 단원"}}
        skeletons = skel.load_patterns(self.root, "apc")
        for entry in skeletons["S190"]["slots"]:  # 카드가 될 수 있는 step 을 붙여도 note_only 자리는 빠짐
            if entry["id"] in NOTE_SLOTS:
                entry.update(step="a18a/1", facts=["FA18-01"], level=1, ref=["시험"])
        made = skel.cards(group, skeletons, units)
        self.assertEqual([c for c in APC_CARDS if c != "apc-g101"], sorted(c["id"] for c in made))
        self.assertEqual(list(range(len(made))), [c["order"] for c in made])
        self.assertEqual(SKEL_CARD_KEYS, set(app.cards["apc-k06"]))

    def test_note_only_text_changes_no_card_version_or_set(self):
        app = self.session("app")
        app.mark_read("apc", "a18a")
        practice = app.start_set("unit", lesson="apc", unit="a18a", seed=4)
        saved = practice.snapshot()
        before = app._card_versions()
        path = self.path("patterns/apc/S190.json")
        data = study.read_json(path)
        for entry in data["slots"]:
            if entry["id"] == "apc-n101":
                entry.update(hint="손실 함수", explain="crit 은 손실을 계산합니다.")
        study.write_text(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        app = self.session("app")
        self.assertEqual("손실 함수", next(e for e in app.skeletons["S190"]["slots"] if e["id"] == "apc-n101")["hint"])
        self.assertEqual(before, app._card_versions())
        self.assertEqual(saved["fingerprint"], type(practice).restore(app, saved).fingerprint())

    def test_rotate_block_lists_only_the_note_only_slots(self):
        app = self.session("app")
        steps = app.unit_steps("apc", "a18a")["steps"]
        rotate = next(b for s in steps for b in s["blocks"] if b["kind"] == "rotate")
        self.assertNotIn("error", rotate)
        self.assertEqual(["apc-n102", "apc-n101"], [s["id"] for s in rotate["slots"]])
        self.assertIn("for a, b in ____:", rotate["slots"][0]["code"])
        self.assertIn("    e = ____(c, b)", rotate["slots"][1]["code"])

    def test_rotate_grades_a_note_only_slot_without_touching_cards(self):
        app = self.session("app")
        app.mark_read("apc", "a18a")
        app.collection.set_enabled(True)
        got = app.check_rotate("apc", "a18a", "t1", "apc-n101", "crit")
        self.assertEqual((True, "crit", "crit 은 예측과 정답으로 손실을 계산합니다."), (got["ok"], got["answer"], got["explain"]))
        self.assertFalse(app.check_rotate("apc", "a18a", "t1", "apc-n102", "loader")["ok"])
        row = app.record.log[-1]
        self.assertEqual(("recall", "apc", "a18a", "t1", "apc-n102", False),
                         (row["kind"], row["lesson"], row["unit"], row["id"], row["slot"], row["ok"]))
        with self.assertRaises(service.AiError):
            app.check_rotate("apc", "a18a", "t1", "apc-k01", "train")
        self.at = "2026-11-10T20:00:00"
        app = self.session("app")
        state = app._state()
        for sid in NOTE_SLOTS:
            self.assertNotIn(sid, state.due_cards())
            self.assertIsNone(state.box(sid))
        keys = [item["key"] for group in app.wrong_notes() for item in group["items"]]
        self.assertFalse([key for key in keys if key in NOTE_SLOTS])
        cards = [r["item"].get("card") for r in app.collection.snapshot() if r.get("item")]
        self.assertFalse([cid for cid in cards if cid in NOTE_SLOTS])

    def test_fading_never_masks_a_note_only_slot(self):
        skeleton = skel.load_patterns(self.root, "apc")["S190"]
        app = self.session("app")
        card = app.cards["apc-k01"]
        every = {e["id"]: 4 for e in skeleton["slots"]}
        for again in range(6):
            made = skel.slot_view(card, skeleton, every, again)
            self.assertEqual(3, made["skel"]["fade"])
            self.assertFalse([b["slot"] for b in made["blanks"] if b["slot"] in NOTE_SLOTS])
        made = skel.view(card, skeleton, 1, record={"masked": ["apc-n101", "apc-k02"], "whole": False, "fade": 1})
        self.assertEqual(["apc-k01", "apc-k02"], [b["slot"] for b in made["blanks"]])

    def test_unit_set_never_shows_a_note_only_slot(self):
        app = self.session("app")
        app.mark_read("apc", "a18a")
        for day in ("09", "10"):
            self.at = "2026-11-%sT20:00:00" % day
            for cid in ("apc-k01", "apc-o01", "apc-p01"):
                app._append({"kind": "answer", "set": "s" + day, "card": cid, "result": "pass", "again": 0})
        self.at = "2026-11-12T20:00:00"
        app = self.session("app")
        practice = app.start_set("unit", lesson="apc", unit="a18a", seed=4)
        seen = []
        while True:
            cur = practice.current()
            if cur is None:
                break
            seen.append(cur["card"])
            self.assertFalse([b for b in cur.get("blanks") or [] if b.get("slot") in NOTE_SLOTS])
            practice.dont_know(2)
            practice.next()
        self.assertFalse(set(seen) & set(NOTE_SLOTS))
        self.assertIn("apc-g101", seen)
        self.assertIn("apc-k02", seen)


class AppGeneratorTest(CodingBase):
    def test_generator_card_belongs_to_the_app_group(self):
        app, intro = self.session("app"), self.session("intro")
        card = app.cards["apc-g101"]
        self.assertEqual(("gen", "apc", "a18a", "a18a/1", "a90", "응용 루프"),
                         (card["kind"], card["lesson"], card["unit"], card["step"], card["after"], card["name"]))
        self.assertNotIn("apc-g101", intro.cards)
        self.assertIn("apc-g101", app._card_versions())

    def test_generator_answer_is_collected_as_app(self):
        app = self.session("app")
        app.mark_read("apc", "a18a")
        for day in ("09", "10"):
            self.at = "2026-11-%sT20:00:00" % day
            for cid in ("apc-k01", "apc-o01", "apc-p01"):
                app._append({"kind": "answer", "set": "s" + day, "card": cid, "result": "pass", "again": 0})
        self.at = "2026-11-12T20:00:00"
        app = self.session("app")
        app.collection.set_enabled(True)
        practice = app.start_set("unit", lesson="apc", unit="a18a", seed=4)
        while practice.current() is not None and practice.current()["card"] != "apc-g101":
            practice.dont_know(2)
            practice.next()
        self.assertIsNotNone(practice.current())
        practice.dont_know(2)
        items = [r["item"] for r in app.collection.snapshot() if r.get("item") and r["item"].get("card") == "apc-g101"]
        self.assertTrue(items)
        for item in items:
            self.assertEqual(("app", "apc", None), (item["course"], item["lesson"], item["course_no"]))
            self.assertIn("generation", item)
        answers = [e for e in app.record.log if e.get("kind") == "answer" and e.get("card") == "apc-g101"]
        self.assertTrue(answers)
        self.assertTrue(all(e.get("course") == "app" for e in answers))

    def test_broken_app_skeleton_drops_the_generator_card_too(self):
        study.write_text(self.path("patterns/apc/S190.json"), "{ 깨진 파일")
        app = self.session("app")
        self.assertIn("apc", app.errors)
        self.assertNotIn("apc-g101", app.cards)

if __name__ == "__main__":
    unittest.main()
