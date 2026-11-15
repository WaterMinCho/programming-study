"""일반 오답 복습의 조건 변형 연결과 원래 풀이·출제 경계를 확인함."""
import copy
import datetime
import json
import os
import random
from unittest import mock

from aiprep import bank, service
from tests.test_ai_service import Base


class NoteVariationTest(Base):
    def session(self, course='intro'):
        return service.AiSession('note-' + course, home=os.path.join(self.tmp, 'home'), root=bank.AI_DIR, course=course)

    def wrong(self, sess, cid):
        sess._append({'kind': 'answer', 'card': cid, 'set': 'earlier', 'result': 'stuck', 'again': 0, 'sure': True})

    def select(self, sess, cid):
        trace = {}
        ids = service.build_set(sess, sess._state(), 'note', random.Random(7), card=cid, trace=trace)
        return ids, trace

    def opened(self, course='intro', cid='i01-b02'):
        sess = self.session(course)
        sess._append({'kind': 'open', 'lesson': sess.cards[cid]['lesson']})
        self.wrong(sess, cid)
        return sess

    def test_both_courses_revisit_original_then_existing_variant_and_restore_display(self):
        for course, cid, gid in [('intro', 'i01-b02', 'i01-g01'), ('app', 'a01-b07', 'a01-g01')]:
            with self.subTest(course=course):
                sess = self.opened(course, cid)
                original = copy.deepcopy(sess.record.log)
                sess.collection.set_enabled(True)
                ids, trace = self.select(sess, cid)
                self.assertEqual([cid, gid], ids)
                self.assertEqual('rules-v4', trace['policy'])
                self.assertEqual('transfer', trace['selected_pools'][gid])
                practice = sess.start_set('note', card=cid, seed=7)
                first = practice.current()
                practice.answer(self.right(practice, first), 2, True)
                practice.next()
                second = practice.current()
                self.assertEqual(gid, second['card'])
                content = practice._collection_item(practice.queue[practice.pos])['content']
                self.assertTrue(content['generation']['instance_id'])
                self.assertEqual('declared' if course == 'app' else 'undeclared', content['generation']['params_status'])
                restored = service.PracticeSet.restore(sess, json.loads(json.dumps(practice.snapshot())))
                self.assertEqual(second, restored.current())
                practice.answer(self.right(practice, second), 3, True)
                self.assertEqual(original, sess.record.log[:len(original)])

    def test_locked_unit_and_unfinished_cores_do_not_open_new_variant(self):
        sess = self.session()
        self.wrong(sess, 'i01-b02')
        self.assertEqual(['i01-b02'], self.select(sess, 'i01-b02')[0])
        sess.mark_read('i01', '1a')
        self.assertEqual(['i01-b02'], self.select(sess, 'i01-b02')[0])

    def test_unanswered_card_is_not_a_note_transfer_trigger(self):
        sess = self.session()
        sess._append({'kind': 'open', 'lesson': 'i01'})
        self.assertEqual(['i01-b02'], self.select(sess, 'i01-b02')[0])

    def test_daily_cap_blocks_new_variant_but_keeps_already_answered_one(self):
        sess = self.opened()
        with mock.patch.object(service, 'NEW_PER_DAY', 0):
            self.assertEqual(['i01-b02'], self.select(sess, 'i01-b02')[0])
            sess._append({'kind': 'answer', 'card': 'i01-g01', 'set': 'known', 'result': 'pass', 'again': 0})
            self.assertEqual(['i01-b02', 'i01-g01'], self.select(sess, 'i01-b02')[0])

    def test_last_new_date_blocks_unseen_variant_in_read_unit(self):
        sess = self.session()
        sess.mark_read('i01', '1a')
        self.wrong(sess, 'i01-b02')
        state = sess._state()
        state.exam = dict(state.exam, last_new=state.today - datetime.timedelta(days=1))
        with mock.patch.object(state, 'core_ready', return_value=True):
            ids = service.build_set(sess, state, 'note', random.Random(7), card='i01-b02')
        self.assertEqual(['i01-b02'], ids)

    def test_unrelated_tags_other_unit_errata_and_deep_do_not_supply_variant(self):
        for change in ({'facts': []}, {'unit': '1b'}, {'lesson': 'a01'}, {'errata': ['bad']}, {'deep': True}):
            with self.subTest(change=change):
                sess = self.opened()
                sess.cards['i01-g01'].update(change)
                sess._cache = None
                state = sess._state()
                ids = service.build_set(sess, state, 'note', random.Random(7), card='i01-b02')
                self.assertEqual(['i01-b02'], ids)

    def test_less_practised_equivalent_variant_is_selected_deterministically(self):
        sess = self.opened()
        other = dict(sess.cards['i01-g01'], id='i01-g99', order=99)
        sess.cards[other['id']] = other
        sess._append({'kind': 'answer', 'card': 'i01-g01', 'set': 'known', 'result': 'pass', 'again': 0})
        ids, trace = self.select(sess, 'i01-b02')
        self.assertEqual(['i01-b02', 'i01-g99'], ids)
        self.assertEqual((ids, trace), self.select(sess, 'i01-b02'))

    def test_same_family_pair_survives_short_round_cap_without_other_duplicates(self):
        sess = self.opened()
        with mock.patch.object(service, 'GEN_SHARE', 0):
            ids, _ = self.select(sess, 'i01-b02')
        self.assertEqual(['i01-b02', 'i01-g01'], ids)
        self.assertEqual(sess.cards[ids[0]]['family'], sess.cards[ids[1]]['family'])

    def test_generator_lead_already_varies_and_does_not_add_another_generator(self):
        sess = self.opened(cid='i01-g01')
        ids, trace = self.select(sess, 'i01-g01')
        self.assertEqual(['i01-g01'], ids)
        self.assertEqual('rules-v2', trace['policy'])

    def test_pair_stays_first_with_other_wrong_answers_and_a_different_family(self):
        sess = self.opened()
        self.wrong(sess, 'i01-b07')
        sess.cards['i01-g01']['family'] = 'other-update-example'
        with mock.patch.object(service, 'GEN_SHARE', 0):
            ids, trace = self.select(sess, 'i01-b02')
        self.assertEqual(['i01-b02', 'i01-g01'], ids[:2])
        self.assertIn('i01-b07', ids[2:])
        self.assertEqual('rules-v4', trace['policy'])

    def test_answering_new_variant_consumes_daily_budget_before_next_note(self):
        sess = self.opened()
        self.assertTrue(sess.cards['i01-b07']['core'])
        self.wrong(sess, 'i01-b07')
        with mock.patch.object(service, 'NEW_PER_DAY', 1):
            practice = sess.start_set('note', card='i01-b02', seed=7)
            for cid in ('i01-b02', 'i01-g01'):
                cur = practice.current()
                self.assertEqual(cid, cur['card'])
                practice.answer(self.right(practice, cur), 2, True)
                practice.next()
            self.assertEqual(0, sess._state().new_cap_left())
            ids, trace = self.select(sess, 'i01-b07')
            self.assertNotIn('i01-g02', ids)
            self.assertNotIn('transfer', trace['selected_pools'].values())

    def test_no_existing_variant_keeps_original_flow(self):
        sess = self.opened()
        del sess.cards['i01-g01']
        ids, trace = self.select(sess, 'i01-b02')
        self.assertEqual(['i01-b02'], ids)
        self.assertEqual('rules-v2', trace['policy'])

    def test_deep_comparison_lead_keeps_its_existing_comparison_pair(self):
        sess = self.opened()
        sess.cards['i01-b02'].update(deep=True, confuse=['comparison'])
        sess.cards['i01-c02'].update(deep=True, confuse=['comparison'], family='comparison-mate')
        self.wrong(sess, 'i01-c02')
        with mock.patch.object(service, 'DEEP_SHARE', 1):
            self.assertEqual(['i01-b02', 'i01-c02'], self.select(sess, 'i01-b02')[0])

    def test_trace_reports_transfer_only_when_pair_is_selected(self):
        sess = self.opened()
        with mock.patch.object(service, 'NOTE_MAX', 1):
            ids, trace = self.select(sess, 'i01-b02')
        self.assertEqual(['i01-b02'], ids)
        self.assertEqual('rules-v2', trace['policy'])
        self.assertEqual({'i01-b02': 'lead'}, trace['selected_pools'])

    def test_existing_single_question_draft_is_not_expanded_on_restore(self):
        sess = self.opened()
        old = service.PracticeSet(sess, 'old-draft', 'note', ['i01-b02'], 7)
        before = old.current()
        restored = service.PracticeSet.restore(sess, json.loads(json.dumps(old.snapshot())))
        self.assertEqual(before, restored.current())
        self.assertEqual(['i01-b02'], [row['card'] for row in restored.queue])

    def test_generator_revisit_uses_new_seed_without_changing_saved_wrong_display(self):
        sess = self.opened(course='app', cid='a01-g01')
        first = sess.start_set('note', card='a01-g01', seed=7)
        cur = first.current()
        first.dont_know(2)
        saved = sess.wrong_item('a01-g01')['stem']
        second = sess.start_set('note', card='a01-g01', seed=19)
        self.assertNotEqual(first.queue[0]['seed'], second.queue[0]['seed'])
        self.assertNotEqual(cur['stem'], second.current()['stem'])
        self.assertEqual(saved, sess.wrong_item('a01-g01')['stem'])
