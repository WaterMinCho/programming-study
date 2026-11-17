"""모의고사 오답에서 관련 연습으로 이어질 때 기록과 과정 경계를 확인함."""
import copy
import json
from pathlib import Path
import os
import random
from unittest import mock

from aiprep import bank, grade, mixed_mock, service
from tests.test_ai_service import Base


class MockTransferTest(Base):
    def session(self, course='intro'):
        return service.AiSession('transfer-' + course, home=os.path.join(self.tmp, 'home'), root=bank.AI_DIR, course=course)

    def submitted(self, course, cid):
        sess = self.session(course)
        exam = sess.start_mock('m4', seed=31)
        for key, item in exam.items.items():
            answer = [b['answer'][0] for b in item['blanks']] if item['kind'] == 'blank' else grade.right_options(item)
            if key != cid:
                exam.save_answer(answer, key)
        result = exam.submit()
        sess.overview()
        return sess, result

    def test_new_exam_links_all_32_wrong_answers_within_each_course(self):
        self.check_wrong_links('m5')

    def test_applied04_wrong_practice_and_repeat_preserve_first_score(self):
        self.check_wrong_links('m6', complete=True)

    def check_wrong_links(self, mid, complete=False):
        sess = self.session()
        exam = sess.start_mock(mid, seed=31)
        self.assertFalse(set(exam.items) & set(sess.cards))
        first = copy.deepcopy(exam.submit())
        checked = set()
        for course in ('intro', 'app'):
            current = service.AiSession(sess.user, home=os.path.join(self.tmp, 'home'), root=bank.AI_DIR, course=course)
            state = current._state()
            wrong = [cid for cid, item in exam.items.items() if item['course'] == course]
            self.assertEqual(16, len(wrong))
            self.assertEqual(set(wrong), {cid for cid, card in current.cards.items() if card.get('mock') == mid})
            for cid in wrong:
                with self.subTest(card=cid, course=course):
                    selected = service.build_set(current, state, 'note', random.Random(7), card=cid)
                    self.assertEqual(cid, selected[0])
                    self.assertGreaterEqual(len(selected), 2)
                    linked = current.cards[selected[1]]
                    self.assertEqual(course, bank.course_of(linked['lesson']))
                    self.assertFalse(linked.get('mock'))
                    self.assertTrue(set(exam.items[cid]['facts']) & set(linked['facts']))
                    if complete:
                        self.assertEqual(exam.items[cid]['lesson'], linked['lesson'])
                        self.assertEqual(exam.items[cid]['lesson'], current.wrong_item(cid)['lesson'])
                        target = current.note_target(cid)
                        self.assertIsNotNone(target, cid)
                        self.assertEqual((exam.items[cid]['lesson'], exam.items[cid]['step']),
                                         (target['lesson'], target['step']))
                        ps = current.start_set('note', card=cid, seed=7)
                        self.assertEqual(selected[:2], [entry['card'] for entry in ps.queue[:2]])
                        played = self.play(ps, lambda _: 'pass')
                        self.assertIn(cid, played)
                        self.assertIn(linked['id'], played)
                    checked.add(cid)
            if complete:
                self.assertEqual(0, current.mock_state(mid)['first_score'])
        self.assertEqual(set(exam.items), checked)
        if complete:
            saved = [row for row in sess.record.reload() if row.get('kind') == 'mock_submit' and row['mock'] == mid]
            self.assertEqual([first], saved)
            repeated = sess.start_mock(mid, repeat=True, seed=32)
            for cid, item in repeated.items.items():
                answer = [b['answer'][0] for b in item['blanks']] if item['kind'] == 'blank' else grade.right_options(item)
                repeated.save_answer(answer, cid)
            self.assertEqual(32, repeated.submit()['score'])
            self.assertEqual(2, repeated.attempt)
            self.assertEqual(0, repeated.summary()['first_score'])
            for course in ('intro', 'app'):
                reopened = service.AiSession(sess.user, home=os.path.join(self.tmp, 'home'), root=bank.AI_DIR, course=course)
                self.assertEqual(0, reopened.mock_state(mid)['first_score'])
                rows = [row for row in reopened.record.log if row.get('kind') == 'mock_submit' and row['mock'] == mid]
                self.assertEqual(2, len(rows))
                self.assertEqual(first, rows[0])

    def test_both_courses_connect_one_wrong_to_a_generator_and_keep_first_result(self):
        for course, cid, genid in [('intro', 'm4-02', 'i02-g03'), ('app', 'm4-19', 'a01-g01')]:
            with self.subTest(course=course):
                sess, result = self.submitted(course, cid)
                self.assertEqual(genid, result['related_by_question'][cid])
                self.assertIn(genid, result['related'])
                before = copy.deepcopy(result)
                trace = {}
                selected = service.build_set(sess, sess._state(), 'note', random.Random(7), card=cid, trace=trace)
                self.assertEqual([cid, genid], selected)
                self.assertEqual('rules-v3', trace['policy'])
                self.assertEqual('transfer', trace['selected_pools'][genid])
                ps = sess.start_set('note', card=cid, seed=7)
                self.play(ps, lambda _: 'pass')
                saved = [r for r in sess.record.log if r.get('kind') == 'mock_submit'][-1]
                self.assertEqual(before, saved)
                self.assertTrue(any(r.get('kind') == 'answer' and r.get('card') == genid for r in sess.record.log))
                self.assertEqual(31, saved['score'])

    def test_related_pair_survives_same_family_and_short_set_generator_trim(self):
        sess, _ = self.submitted('intro', 'm4-02')
        sess.cards['m4-02']['family'] = sess.cards['i02-g03']['family']
        sess.cards['m4-02']['deep'] = sess.cards['i02-g03']['deep'] = True
        with mock.patch.object(service, 'GEN_SHARE', 0), mock.patch.object(service, 'DEEP_SHARE', 0):
            selected = service.build_set(sess, sess._state(), 'note', random.Random(1), card='m4-02')
        self.assertEqual(['m4-02', 'i02-g03'], selected)
        self.assertEqual(2, len(selected))

    def test_explicit_transfer_keeps_other_deep_comparison_pairs(self):
        sess = self.session()
        sess.cards = {cid: dict(id=cid, kind='blank', family=cid, deep=cid in ('a', 'b'),
                               confuse=['pair'] if cid in ('a', 'b') else [])
                      for cid in ('lead', 'variant', 'a', 'other', 'b')}
        sess.cards['lead']['mock'] = 'm5'
        pools = [('lead', ['lead']), ('transfer', ['variant']), ('rest', ['a', 'other', 'b'])]
        with mock.patch.object(service, 'DEEP_SHARE', 1):
            chosen = service._choose(sess, None, pools, 4, random.Random(0))
        self.assertEqual(['lead', 'variant', 'a', 'b'], [cid for cid, _ in chosen])

    def test_unsubmitted_exam_never_exposes_mock_cards_and_other_courses_are_excluded(self):
        sess = self.session()
        sess.start_mock('m4')
        self.assertNotIn('m4-02', sess.cards)
        with self.assertRaises(service.AiError):
            sess.start_set('note', card='m4-02')
        item = {'lesson': 'i02', 'family': 'same', 'facts': ['f'], 'tags': ['tag']}
        cards = {key: {'id': key, 'lesson': lid, 'family': 'same', 'facts': ['f'], **extra}
                 for key, lid, extra in [('app', 'a02', {}), ('wrong', 'i02', {'errata': ['x']}),
                                         ('future', 'i02', {'mock': 'm5'}), ('valid', 'i02', {})]}
        self.assertEqual(['valid'], [c['id'] for c in mixed_mock.practice_candidates(item, cards)])

    def test_exact_family_beats_unrelated_tags_and_equal_evidence_prefers_generator(self):
        item = {'lesson': 'i03', 'family': 'axis', 'facts': ['axis-fact'], 'tags': ['tensor']}
        cards = {key: {'id': key, 'lesson': 'i03', 'family': family, 'kind': kind, 'facts': facts, 'tags': ['tensor']}
                 for key, family, kind, facts in [('weak', 'other', 'gen', []), ('fixed', 'axis', 'blank', ['axis-fact']),
                                                  ('variant', 'axis', 'gen', ['axis-fact'])]}
        self.assertEqual(['variant', 'fixed', 'weak'], [c['id'] for c in mixed_mock.practice_candidates(item, cards)])
        self.assertEqual(['fixed', 'weak'], [c['id'] for c in mixed_mock.practice_candidates(item, cards, ['variant'])])

    def test_next_day_review_contains_related_generator_without_marking_it_solved(self):
        sess, _ = self.submitted('app', 'm4-19')
        self.assertNotIn('a01-g01', sess._state().events)
        self.assertNotIn('a01-g01', sess._state().due_cards())
        self.at = '2026-11-10T20:00:00'
        sess = self.session('app')
        self.assertIn('a01-g01', sess._state().due_cards())
        selected = service.build_set(sess, sess._state(), 'review', random.Random(0))
        self.assertIn('a01-g01', selected)

    def test_review_generator_resumes_the_same_input_and_new_attempt_changes_conditions(self):
        sess, _ = self.submitted('app', 'm4-19')
        sess.collection.set_enabled(True)
        ps = sess.start_set('note', card='m4-19', seed=8)
        ps.current()
        ps.answer(self.right(ps, ps.current()), 2, True)
        ps.next()
        shown = ps.current()
        self.assertEqual('a01-g01', shown['card'])
        original = copy.deepcopy(ps._view(ps.queue[ps.pos]))
        saved_result = ps.snapshot()
        restored = service.PracticeSet.restore(sess, saved_result)
        self.assertEqual(original, restored._view(restored.queue[restored.pos]))
        restored.answer(self.right(restored, restored.current()), 2, True)
        records = sess.collection.snapshot(include_answers=True)
        answers = [r for r in records if r['kind'] == 'answer' and r['data']['card'] == 'a01-g01']
        self.assertEqual(1, len(answers))
        self.assertEqual('app', answers[0]['data']['course'])
        self.assertTrue(answers[0]['item'].get('generation'))
        different = sess.start_set('note', card='m4-19', seed=9)
        variant = next(e for e in different.queue if e['card'] == 'a01-g01')
        self.assertNotEqual(original['item']['params'], different._view(variant)['item']['params'])

    def test_no_candidate_keeps_original_and_a_static_candidate_stays_second(self):
        sess, _ = self.submitted('intro', 'm4-01')
        selected = service.build_set(sess, sess._state(), 'note', random.Random(0), card='m4-01')
        self.assertEqual(['m4-01', 'i01-c16'], selected)
        sess.cards = {cid: c for cid, c in sess.cards.items() if c.get('mock')}
        selected = service.build_set(sess, sess._state(), 'note', random.Random(0), card='m4-01')
        self.assertEqual(['m4-01'], selected)

    def test_old_submissions_without_per_question_links_still_offer_variations(self):
        sess, _ = self.submitted('app', 'm4-19')
        path = Path(sess.record.path)
        data = json.loads(path.read_text())
        for row in data['log']:
            row.pop('related_by_question', None)
        path.write_text(json.dumps(data))
        sess = self.session('app')
        sess._state()
        self.assertNotIn('related_practice', sess.cards['m4-19'])
        selected = service.build_set(sess, sess._state(), 'note', random.Random(0), card='m4-19')
        self.assertEqual(['m4-19', 'a01-g01'], selected)

    def test_application_wrong_note_reads_the_shared_exam_answer_file(self):
        sess = self.session('app')
        exam = sess.start_mock('m4', seed=2)
        exam.save_answer(['999'], 'm4-17')
        exam.submit()
        self.assertEqual(['999'], sess.wrong_item('m4-17')['mine'])

    def test_saved_link_is_reused_and_not_copied_to_collection(self):
        sess = self.session('app')
        sess.collection.set_enabled(True)
        exam = sess.start_mock('m4')
        result = exam.submit()
        self.assertTrue(result['related_by_question'])
        collected = [row for row in sess.collection.snapshot() if row['kind'] == 'mock_submit']
        self.assertTrue(collected)
        for row in collected:
            self.assertFalse(row['data'].get('related_by_question'))
        sess._state()
        sess.cards['m4-19']['related_practice'] = 'a01-b07'
        selected = service.build_set(sess, sess._state(), 'note', random.Random(0), card='m4-19')
        self.assertEqual(['m4-19', 'a01-b07'], selected[:2])
        self.assertNotIn('a01-g01', selected)
        repeated = sess.start_mock('m4', repeat=True)
        repeated.submit()
        reopened = self.session('app')
        reopened._state()
        self.assertEqual(result['related_by_question']['m4-19'], reopened.cards['m4-19']['related_practice'])
