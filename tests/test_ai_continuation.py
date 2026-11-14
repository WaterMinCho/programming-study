# -*- coding: utf-8 -*-
"""중단한 단계·연습과 단원 완료 뒤의 이동을 임시 기록으로 확인함."""
import copy
import json
import os
from types import SimpleNamespace

from aiprep import bank, plan, service
from tests.test_ai_service import Base


class ContinuationTest(Base):
    def test_course_resume_reads_the_practice_position_changed_by_another_session(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        practice = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        practice.answer(self.right(practice, practice.current()), 1, True)
        another = self.session().resume_set()
        another.next()
        path = os.path.join(sess.home, "state.json")
        with open(path, "rb") as source:
            before = source.read()
        log = list(another.sess.record.log)
        sess.resume_course()
        resumed = sess.resume_set()
        self.assertEqual(another.pos, resumed.pos)
        self.assertEqual(another.current(), resumed.current())
        self.assertEqual(log, sess.record.log)
        with open(path, "rb") as source:
            self.assertEqual(before, source.read())

    def test_saved_last_step_is_not_completion_and_survives_reload(self):
        sess = self.session()
        sess.save_step("i90", "90a", 4)
        sess.mark_read("i90", "90a")
        before = list(sess.record.log)
        resumed = self.session()
        item = resumed.continuation()
        self.assertEqual(("unit", "90a", 4), (item["kind"], item["unit"], item["step"]))
        self.assertEqual(set(), resumed.completed_units())
        self.assertEqual(before, resumed.record.log)

    def test_completed_unit_advances_even_when_review_is_due(self):
        sess = self.session()
        sess.save_step("i90", "90a", 4)
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        self.play(ps, lambda _: "pass")
        self.assertTrue(ps.ended)
        self.assertEqual({("i90", "90a")}, sess.completed_units())
        item = sess.continuation()
        self.assertEqual(("unit", "i90", "90b", 1), (item["kind"], item["lesson"], item["unit"], item["step"]))

    def test_order_uses_current_unit_and_next_lesson_without_dates(self):
        rows = [{"lesson": "i01", "unit": "1a", "no": 1, "order": 0},
                {"lesson": "i01", "unit": "1b", "no": 1, "order": 1},
                {"lesson": "i02", "unit": "2a", "no": 2, "order": 0}]
        self.assertEqual("1b", plan.continue_unit(rows, ("i01", "1b"))["unit"])
        self.assertEqual("1b", plan.continue_unit(rows, ("i01", "1a"), [("i01", "1a")])["unit"])
        self.assertEqual("2a", plan.continue_unit(rows, ("i01", "1b"), [("i01", "1b")])["unit"])
        self.assertIsNone(plan.continue_unit(rows, ("i02", "2a"), [("i02", "2a")]))

    def test_last_unit_moves_to_the_first_published_unit_of_next_lesson(self):
        sess = self.session()
        note = copy.deepcopy(sess.notes["i90"])
        note["visible"] = ["91a"]
        note["units"] = {"91a": note["units"]["90a"]}
        note["unit_meta"] = {"91a": {}}
        sess.notes["i91"] = note
        sess.save_step("i90", "90b", 4)
        sess.mark_read("i90", "90b")
        ps = sess.start_set("unit", lesson="i90", unit="90b", seed=2)
        self.play(ps, lambda _: "pass")
        target = sess.continuation()
        self.assertEqual(("i91", "91a", 1), (target["lesson"], target["unit"], target["step"]))

    def test_reopening_a_completed_unit_resumes_the_new_reading_position(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        self.play(ps, lambda _: "pass")
        sess.save_step("i90", "90a", 2)
        item = sess.continuation()
        self.assertEqual(("90a", 2), (item["unit"], item["step"]))

    def test_final_answer_waits_for_next_before_completing_the_unit(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        while ps.pos < len(ps.queue) - 1:
            cur = ps.current()
            ps.answer(self.right(ps, cur), 1, True)
            ps.next()
        ps.answer(self.right(ps, ps.current()), 1, True)
        restored = self.session().resume_set()
        self.assertIsNotNone(restored.answered)
        self.assertNotIn(("i90", "90a"), restored.sess.completed_units())
        self.assertIsNone(restored.next())
        self.assertIn(("i90", "90a"), restored.sess.completed_units())

    def test_finished_set_does_not_claim_every_card_is_memorised(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        self.play(ps, lambda _: "fail")
        self.assertTrue(ps.summary()["left"])
        self.assertEqual(0, sess.overview()["memorised"])
        self.assertIn(("i90", "90a"), sess.completed_units())
        self.assertEqual("90b", sess.continuation()["unit"])

    def test_legacy_local_keys_and_at_step_are_preserved(self):
        sess = self.session()
        os.makedirs(sess.home, exist_ok=True)
        path = os.path.join(sess.home, "state.json")
        original = {"at_step": {"i90/90a": 4, "i90/90b": 2}, "other": {"keep": 7}}
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(original, stream)
        self.assertEqual(("90b", 2), (sess.continuation()["unit"], sess.continuation()["step"]))
        with open(path, encoding="utf-8") as stream:
            self.assertEqual(original, json.load(stream))
        sess.save_step("i90", "90b", 3)
        with open(path, encoding="utf-8") as stream:
            saved = json.load(stream)
        self.assertEqual(4, saved["at_step"]["i90/90a"])
        self.assertEqual(original["other"], saved["other"])

    def test_current_set_draft_and_answer_state_resume_without_new_records(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=6)
        cur = ps.current()
        ps.draft = {"values": ["중간 입력"], "queued": len(ps.queue)}
        sess.save_practice(ps)
        before = list(sess.record.log)
        restored_session = self.session()
        restored = restored_session.resume_set("unit", "i90", "90a")
        self.assertEqual(cur, restored.current())
        self.assertEqual(["중간 입력"], restored.draft["values"])
        self.assertEqual(before, restored_session.record.log)
        restored.answer(self.right(restored, cur), 1, True)
        after_answer = list(restored_session.record.log)
        again = self.session().resume_set()
        self.assertIsNotNone(again.answered)
        self.assertEqual(restored.current(), again.current())
        self.assertEqual(after_answer, again.sess.record.log)
        self.assertEqual(restored.next(), again.next())

    def test_wrong_answer_override_and_requeue_survive_restart(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=4)
        cur = ps.current()
        self.assertEqual("blank", cur["kind"])
        ps.answer(["틀린 답"], 1, True)
        restored = self.session().resume_set()
        self.assertEqual(len(ps.queue), len(restored.queue))
        restored.override()
        self.assertEqual("pass", restored.answered["result"])
        self.assertEqual(1, len(self.log(restored.sess, "override")))
        self.assertIsNotNone(self.session().resume_set().next())

    def test_unrelated_read_record_does_not_discard_pending_practice(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        sess.save_recall("i90", "90b", "r1", True)
        self.assertEqual(ps.id, self.session().resume_set().id)

    def test_changed_bank_or_set_records_are_not_replayed(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        changed = self.session()
        changed.cards = copy.deepcopy(changed.cards)
        changed.cards[next(iter(ps.stats))]["tags"] = ["바뀐 문항"]
        self.assertIsNone(changed.resume_set())
        sess._append({"kind": "answer", "set": ps.id, "card": next(iter(ps.stats)), "result": "pass"})
        self.assertIsNone(self.session().resume_set())

    def source_corrected_session(self):
        changed = self.session()
        card = changed.cards['i90-b01']
        previous = list(card['item']['ref'])
        current = ['90차시 슬 p3']
        card['ref'] = current
        card['item']['ref'] = current
        changed.items['i90']['meta']['resume_source_refs'] = {
            card['id']: {'previous': previous, 'current': current}}
        return changed

    def test_registered_source_correction_keeps_draft_and_records(self):
        sess = self.session()
        practice = sess.start_set('note', card='i90-b01', seed=2)
        practice.current()
        practice.draft = {'values': ['작성 중']}
        sess.save_practice(practice)
        before_log = copy.deepcopy(sess.record.log)
        with open(os.path.join(sess.home, 'state.json'), encoding='utf-8') as stream:
            before_state = stream.read()
        changed = self.source_corrected_session()
        self.assertEqual(sess._card_versions()['i90-b01'], changed._card_versions()['i90-b01'])
        restored = changed.resume_set()
        self.assertIsNotNone(restored)
        self.assertEqual(practice.draft, restored.draft)
        self.assertEqual(practice.current(), restored.current())
        self.assertEqual(before_log, changed.record.log)
        with open(os.path.join(sess.home, 'state.json'), encoding='utf-8') as stream:
            self.assertEqual(before_state, stream.read())
        changed.save_practice(restored)
        self.assertEqual(restored.fingerprint(), changed._local()['practice']['fingerprint'])

    def test_source_correction_does_not_accept_changed_content_or_bad_fingerprint(self):
        sess = self.session()
        sess.start_set('note', card='i90-b01', seed=2)
        for field in ('stem', 'answer', 'terms', 'source', 'missing'):
            with self.subTest(field=field):
                changed = self.source_corrected_session()
                if field == 'stem':
                    changed.cards['i90-b01']['item']['stem'] += ' 다른 조건입니다.'
                elif field == 'answer':
                    changed.cards['i90-b01']['item']['blanks'][0]['answer'] = ['다른 답']
                elif field == 'terms':
                    changed.terms['different'] = '바뀐 용어'
                elif field == 'source':
                    changed.cards['i90-b01']['item']['ref'] = ['등록하지 않은 출처']
                else:
                    changed.items['i90']['meta'].pop('resume_source_refs')
                self.assertIsNone(changed.resume_set())
        data = sess._local()
        data['practice']['fingerprint'] = None
        sess._save_local(data)
        self.assertIsNone(self.source_corrected_session().resume_set())

    def test_published_a02_refs_match_the_prior_complete_card_content(self):
        root = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ai')
        data = bank.load_items({'id': 'a02'}, root)
        cards = {card['id']: card for card in bank.cards_of({'id': 'a02'}, data)
                 if card['kind'] != 'gen'}
        self.assertEqual(37, len(cards))
        fixes = data['meta']['resume_source_refs']
        self.assertEqual({'a02-b18', 'a02-c09', 'a02-c10'}, set(fixes))
        for cid, fix in fixes.items():
            self.assertIn(cards[cid]['kind'], ('blank', 'choice'))
            self.assertEqual(fix['current'], cards[cid]['ref'])
            self.assertEqual(fix['current'], cards[cid]['item']['ref'])
        practice = service.PracticeSet.__new__(service.PracticeSet)
        practice.sess = SimpleNamespace(cards=cards, items={'a02': data}, terms={}, skeletons={}, root=root)
        practice.stats = {cid: {} for cid in cards}
        # d7346a8의 37문항 전체를 용어·뼈대 없이 계산한 해시임.
        previous = '60acc9da498ba8cd4d8615f0562e212132a1c3c8c5414a279820809dd9dc657e'
        self.assertNotEqual(previous, practice.fingerprint())
        self.assertEqual(previous, practice.fingerprint(previous_refs=True))

    def test_reading_another_unit_keeps_its_cursor_when_practice_hides(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("unit", lesson="i90", unit="90a", seed=2)
        sess.save_step("i90", "90b", 2)
        ps.draft = {"values": ["보관할 입력"]}
        sess.save_practice(ps)
        self.assertEqual(("90b", 2), (sess.continuation()["unit"], sess.continuation()["step"]))

    def test_generator_question_and_partial_input_survive_restart(self):
        sess = self.session()
        sess.start_set("lesson", lesson="i90", seed=2)
        ps = sess.start_set("note", card="i90-g01", seed=2)
        current = ps.current()
        ps.draft = {"values": ["계산 중"]}
        sess.save_practice(ps)
        restored = self.session().resume_set("note", card="i90-g01")
        self.assertEqual(current, restored.current())
        self.assertEqual(ps.draft, restored.draft)

    def test_choice_selection_survives_restart(self):
        sess = self.session()
        sess.mark_read("i90", "90a")
        ps = sess.start_set("note", card="i90-c01", seed=2)
        current = ps.current()
        self.assertEqual("choice", current["kind"])
        ps.draft = {"values": [current["options"][1]["no"]]}
        sess.save_practice(ps)
        restored = self.session().resume_set("note", card="i90-c01")
        self.assertEqual(current, restored.current())
        self.assertEqual(ps.draft, restored.draft)
