"""자동 복습의 변형 연결·하루 완료·복습 일정·개별 답안 보존을 확인함."""
import copy
import json
import os
import random
from unittest import mock

from aiprep import bank, service
from tests.test_ai_service import Base


class AutoVariationTest(Base):
    def session(self, course='intro'):
        self.session_number = getattr(self, 'session_number', 0) + 1
        return service.AiSession('auto-%s-%s' % (course, self.session_number), home=os.path.join(self.tmp, 'home'), root=bank.AI_DIR, course=course)

    def answer_before(self, sess, cid, result='pass', day='07'):
        self.at = f'2026-11-{day}T20:00:00'
        sess._append({'kind': 'answer', 'card': cid, 'set': 'old', 'result': result, 'again': 0})
        self.at = '2026-11-09T20:00:00'

    def opened(self, course='intro', cid='i01-b02'):
        sess = self.session(course)
        sess._append({'kind': 'open', 'lesson': sess.cards[cid]['lesson']})
        self.answer_before(sess, cid)
        return sess

    def select(self, sess, mode='review'):
        trace = {}
        ids = service.build_set(sess, sess._state(), mode, random.Random(7), trace=trace)
        return ids, trace

    def crowded(self, total, again=False, variants=1):
        sess = self.opened()
        source = copy.deepcopy(sess.cards['i01-b02'])
        target = copy.deepcopy(sess.cards['i01-g01'])
        sess.cards = {}
        for n in range(total):
            cid = f'i01-b{n + 50:02d}'
            sess.cards[cid] = dict(source, id=cid, family=cid, facts=[f'fact-{n}'], order=n)
            self.answer_before(sess, cid, 'stuck' if again else 'pass', '09' if again else '07')
            if n < variants:
                gid = f'i01-g{n + 50:02d}'
                sess.cards[gid] = dict(target, id=gid, family=cid, facts=[f'fact-{n}'], order=n)
        sess._cache = None
        return sess

    def test_next_unit_mixes_a_different_task_and_keeps_original_wrong(self):
        for course, source, target, next_unit in (
            ('intro', 'i01-b02', 'i01-c02', '1b'),
            ('app', 'a01-b07', 'a01-c03', 'a1d'),
        ):
            with self.subTest(course=course):
                sess = self.session(course)
                lead = sess.cards[source]
                lesson = lead['lesson']
                sess.collection.set_enabled(True)
                sess.mark_read(lesson, lead['unit'])
                first = sess.start_set('unit', lesson=lesson, unit=lead['unit'], seed=7)
                while first.current()['card'] != source:
                    first.answer(self.right(first, first.current()), 2, True)
                    first.next()
                first.dont_know(2)
                sess.mark_read(lesson, next_unit)
                before = copy.deepcopy(sess.record.log)
                practice = sess.start_set('unit', lesson=lesson, unit=next_unit, seed=7)
                ids = [e['card'] for e in practice.queue]
                self.assertIn(target, ids)
                self.assertNotIn(source, ids)
                self.assertTrue(any(sess.cards[cid]['unit'] == next_unit for cid in ids))
                set_rows = [row for row in sess.collection.snapshot() if row['kind'] == 'set']
                trace = set_rows[-1]['data']['selection']
                self.assertEqual('rules-v7', trace['policy'])
                self.assertEqual({source: target}, trace['unit_transfers'])
                self.assertEqual('unit_transfer', trace['selected_pools'][target])
                self.assertEqual(ids, [e['card'] for e in sess.resume_set().queue])
                while practice.current()['card'] != target:
                    practice.answer(self.right(practice, practice.current()), 2, True)
                    practice.next()
                practice.answer(self.right(practice, practice.current()), 2, True)
                self.assertEqual(before, sess.record.log[:len(before)])
                self.assertEqual(target, sess.record.log[-1]['card'])
                self.assertIn(source, sess._state().again)
                self.assertIn(source, [e['card'] for e in sess.start_set('review', seed=7).queue])

    def test_next_lesson_can_review_the_same_concept_after_exam_cutoff(self):
        self.at = '2026-11-25T20:00:00'
        sess = self.session()
        source, target = 'i01-b02', 'i01-c02'
        sess.mark_read('i01', '1a')
        sess._append({'kind': 'answer', 'card': source, 'set': 'old', 'result': 'fail', 'again': 0})
        sess.mark_read('i02', '2a')
        state = sess._state()
        self.assertFalse(state.eligible_new(sess.cards[target], ready=False))
        trace = {}
        ids = service.build_set(sess, state, 'unit', random.Random(9), lesson='i02', unit='2a', trace=trace)
        self.assertEqual({source: target}, trace['unit_transfers'])
        self.assertIn(target, ids)
        self.assertNotIn(source, ids)
        with mock.patch.object(service, 'NEW_PER_DAY', 0):
            ids = service.build_set(sess, state, 'unit', random.Random(9), lesson='i02', unit='2a')
            self.assertNotIn(target, ids)
            self.assertIn(source, ids)

    def test_next_unit_uses_exact_original_only_if_other_cards_run_out(self):
        sess = self.session()
        sess.mark_read('i01', '1a')
        self.answer_before(sess, 'i01-b02', result='stuck', day='09')
        # 연결 후보도 오늘 틀렸으므로 새 복습 후보로 다시 뽑지 않음.
        self.answer_before(sess, 'i01-c02', result='stuck', day='09')
        sess.mark_read('i01', '1b')
        kw = dict(lesson='i01', unit='1b')
        with mock.patch.object(service, 'SET_MIN', 1):
            ids = service.build_set(sess, sess._state(), 'unit', random.Random(7), **kw)
            self.assertNotIn('i01-b02', ids)
            self.assertNotIn('i01-c02', ids)
        trace = {}
        ids = service.build_set(sess, sess._state(), 'unit', random.Random(7), trace=trace, **kw)
        self.assertIn('i01-b02', ids)
        self.assertEqual('carry', trace['selected_pools']['i01-b02'])

    def test_next_unit_does_not_repeat_two_originals_with_the_same_counterpart(self):
        sess = self.session('app')
        sess.mark_read('a01', 'a1c')
        for cid in ('a01-b07', 'a01-b08'):
            self.answer_before(sess, cid, result='stuck', day='09')
        sess.mark_read('a01', 'a1d')
        trace = {}
        ids = service.build_set(sess, sess._state(), 'unit', random.Random(7),
                                lesson='a01', unit='a1d', trace=trace)
        self.assertEqual(1, ids.count('a01-c03'))
        self.assertTrue({'a01-b07', 'a01-b08'}.isdisjoint(ids))
        self.assertEqual({'a01-b07': 'a01-c03'}, trace['unit_transfers'])
        self.assertEqual({'a01-b07', 'a01-b08'}, set(sess._state().again))

    def test_unit_transfer_catalog_uses_distinct_fixed_tasks_in_same_unit(self):
        for course in ('intro', 'app'):
            sess = self.session(course)
            for source, targets in sess.unit_transfers.items():
                if bank.course_of(source) != course:
                    continue
                self.assertEqual(len(targets), len(set(targets)))
                lead = sess.cards[source]
                for cid in targets:
                    with self.subTest(source=source, target=cid):
                        card = sess.cards[cid]
                        self.assertEqual((lead['lesson'], lead['unit']), (card['lesson'], card['unit']))
                        self.assertEqual({'blank', 'choice'}, {lead['kind'], card['kind']})
                        self.assertFalse(lead['deep'] or card['deep'])
                        self.assertNotEqual(lead['item']['stem'], card['item']['stem'])

    def test_review_and_sweep_pair_both_courses_and_record_actual_ids(self):
        for course, source, target in [('intro', 'i01-b02', 'i01-g01'), ('app', 'a01-b07', 'a01-g01')]:
            for mode in ('review', 'sweep'):
                with self.subTest(course=course, mode=mode):
                    sess = self.opened(course, source)
                    ids, trace = self.select(sess, mode)
                    self.assertEqual([source, target], ids)
                    self.assertEqual('rules-v5', trace['policy'])
                    self.assertEqual({source: target}, trace['paired'])
                    self.assertIn(target, trace['candidate_ids'])
                    old = copy.deepcopy(sess.record.log)
                    sess.collection.set_enabled(True)
                    ps = sess.start_set(mode, seed=7)
                    self.assertEqual(source, ps.current()['card'])
                    ps.dont_know(2)
                    ps.next()
                    self.assertEqual(target, ps.current()['card'])
                    restored = service.PracticeSet.restore(sess, json.loads(json.dumps(ps.snapshot())))
                    self.assertEqual(ps.current(), restored.current())
                    ps.answer(self.right(ps, ps.current()), 2, True)
                    self.assertEqual(old, sess.record.log[:len(old)])
                    self.assertEqual(target, sess.record.log[-1]['card'])
                    self.assertEqual('pass', sess.record.log[-1]['result'])
                    self.assertIn(source, sess._state().again)
                    self.assertNotIn(source, sess._state().completed_today)
                    rows = sess.collection.snapshot()
                    saved_trace = next(row['data']['selection'] for row in rows if row['kind'] == 'set')
                    self.assertEqual(trace['paired'], saved_trace['paired'])
                    self.assertEqual(ids, saved_trace['selected'])
                    returned = [row for row in rows if row['kind'] == 'question_returned']
                    self.assertEqual([source, target], [row['data']['card'] for row in returned])
                    self.assertTrue(returned[-1]['item']['generation']['instance_id'])


    def test_no_pending_does_not_open_unseen_variants(self):
        sess = self.session()
        sess._append({'kind': 'open', 'lesson': 'i01'})
        self.assertEqual([], self.select(sess)[0])

    def test_full_due_backlog_defers_only_tail_and_next_round_recovers_it(self):
        sess = self.crowded(21)
        before = copy.deepcopy(sess.record.log)
        ids, trace = self.select(sess)
        self.assertEqual(20, len(ids))
        self.assertEqual(['i01-b69'], trace['deferred'])
        pos = ids.index('i01-b50')
        self.assertEqual('i01-g50', ids[pos + 1])
        self.assertEqual(before, sess.record.log)
        ps = sess.start_set('review', seed=7)
        self.play(ps, lambda cur: 'pass')
        next_ids, _ = self.select(sess)
        self.assertIn('i01-b69', next_ids)
        self.assertIn('i01-b70', next_ids)
        self.assertNotIn('i01-g50', next_ids)

    def test_exactly_full_due_and_full_again_do_not_create_an_extra_round(self):
        for total, again in ((20, False), (21, True)):
            with self.subTest(total=total, again=again):
                sess = self.crowded(total, again=again)
                ids, trace = self.select(sess)
                self.assertEqual(20, len(ids))
                self.assertFalse(any(sess.cards[c]['kind'] == 'gen' for c in ids))
                self.assertEqual('rules-v2', trace['policy'])

    def test_pair_limit_and_daily_new_cap_are_shared(self):
        for cap, expected in ((20, 3), (1, 1), (0, 0)):
            with self.subTest(cap=cap):
                sess = self.crowded(5, variants=5)
                with mock.patch.object(service, 'NEW_PER_DAY', cap):
                    ids, trace = self.select(sess)
                self.assertEqual(expected, sum(sess.cards[c]['kind'] == 'gen' for c in ids))
                self.assertEqual(5 + expected, len(ids))
                self.assertEqual(expected, len(trace.get('paired', {})))

    def test_completed_variant_is_excluded_and_due_variant_is_not_duplicated(self):
        sess = self.opened()
        self.answer_before(sess, 'i01-g01', day='09')
        self.assertNotIn('i01-g01', self.select(sess)[0])
        sess = self.opened('app', 'a01-b07')
        self.answer_before(sess, 'a01-g01')
        ids, trace = self.select(sess)
        self.assertLessEqual(ids.count('a01-g01'), 1)
        self.assertNotIn('a01-g01', trace.get('paired', {}).values())

    def test_fixed_candidates_require_explicit_mapping_and_same_unit(self):
        sess = self.opened()
        source = sess.cards['i01-b02']
        sess.cards.pop('i01-g01')
        fixed = copy.deepcopy(sess.cards['i01-c02'])
        fixed.update(id='i01-c99', family='different-condition', facts=source['facts'], unit=source['unit'])
        sess.cards['i01-c99'] = fixed
        sess.review_variants = {}
        sess._cache = None
        self.assertNotIn('i01-c99', self.select(sess)[0])
        sess.review_variants = {source['id']: ['i01-c99']}
        ids, trace = self.select(sess)
        self.assertEqual([source['id'], 'i01-c99'], ids)
        for change in ({'unit': '1b'}, {'deep': True}):
            with self.subTest(change=change):
                sess.cards['i01-c99'] = dict(fixed, **change)
                sess._cache = None
                self.assertNotIn('i01-c99', self.select(sess)[0])
        sess.cards['i01-c99'] = dict(fixed, facts=['reviewed-related-fact'])
        sess._cache = None
        self.assertIn('i01-c99', self.select(sess)[0])

    def test_reviewed_deep_pair_keeps_level_and_existing_comparison_pair(self):
        sess = self.opened(cid='i13-b16')
        sess.review_variants = {'i13-b16': ['i13-c06']}
        self.assertIn('i13-c06', service._variants(sess._state(), sess.cards['i13-b16'], fixed=True))
        sess.cards['i13-c06']['deep'] = False
        sess._cache = None
        self.assertNotIn('i13-c06', service._variants(sess._state(), sess.cards['i13-b16'], fixed=True))
        sess.cards['i13-c06']['deep'] = True
        sess.cards['i13-b16']['confuse'] = ['existing-pair']
        sess._cache = None
        self.assertEqual([], service._variants(sess._state(), sess.cards['i13-b16'], fixed=True))

    def test_reviewed_generator_reuses_verified_condition_without_changing_source(self):
        for source, target in [('i05-b08', 'i05-g02'), ('i05-b23', 'i05-g05')]:
            with self.subTest(source=source):
                sess = self.opened(cid=source)
                sess.review_variants = {}
                self.assertNotIn(target, service._variants(sess._state(), sess.cards[source], fixed=True))
                sess.review_variants = {source: [target]}
                ids, trace = self.select(sess)
                self.assertEqual([source, target], ids)
                self.assertEqual('rules-v5', trace['policy'])
                self.answer_before(sess, source, result='stuck', day='09')
                note_trace = {}
                service.build_set(sess, sess._state(), 'note', random.Random(7), card=source, trace=note_trace)
                self.assertEqual('rules-v5', note_trace['policy'])
                self.assertEqual(trace['variant_catalog_revision'], note_trace['variant_catalog_revision'])

    def test_locked_unit_and_same_family_third_card_do_not_add_a_pair(self):
        sess = self.session()
        self.answer_before(sess, 'i01-b02')
        self.assertEqual(['i01-b02'], self.select(sess)[0])
        sess = self.crowded(3)
        sess.cards['i01-g50']['family'] = sess.cards['i01-b51']['family']
        self.assertNotIn('i01-g50', self.select(sess)[0])

    def test_optional_fillers_are_replaced_before_due_and_deep_pairs_are_protected(self):
        sess = self.crowded(21)
        state = sess._state()
        chosen = [(f'i01-b{n + 50}', 'due') for n in range(20)]
        pools = [('due', [f'i01-b{n + 50}' for n in range(21)])]
        chosen[-1] = ('i01-b69', 'low')
        result, pairs, _, deferred = service._review_pairs(sess, state, chosen, pools, 20)
        self.assertNotIn('i01-b69', dict(result))
        self.assertEqual([], deferred)
        chosen[-1] = ('i01-b69', 'due')
        for cid in ('i01-b68', 'i01-b69'):
            sess.cards[cid].update(deep=True, confuse=['protected'])
        result, pairs, _, deferred = service._review_pairs(sess, state, chosen, pools, 20)
        self.assertEqual(['i01-b67'], deferred)
        self.assertIn('i01-b68', dict(result))
        self.assertIn('i01-b69', dict(result))

    def test_no_pair_does_not_rewrite_saved_draft(self):
        sess = self.opened()
        with mock.patch.object(service, '_review_pairs', side_effect=lambda s, st, c, p, size: (c, {}, {}, [])):
            ps = sess.start_set('review', seed=7)
            ps.current()
            saved = json.loads(json.dumps(ps.snapshot()))
        restored = service.PracticeSet.restore(sess, saved)
        self.assertEqual(saved, json.loads(json.dumps(restored.snapshot())))
        self.assertEqual(1, len(restored.queue))

    def test_review_mapping_missing_or_invalid_is_explicit(self):
        self.assertEqual({}, bank.read_review_variants(self.tmp))
        path = os.path.join(self.tmp, 'review_variants.json')
        for value in ([], {'version': 2, 'pairs': {}}, {'version': 1, 'pairs': {'i01-b01': 'i01-c01'}}):
            with open(path, 'w') as stream:
                json.dump(value, stream)
            with self.assertRaises(bank.AiBankError):
                bank.read_review_variants(self.tmp)
        with open(path, 'w') as stream:
            json.dump({'version': 1, 'pairs': {'i01-b01': ['i01-c01']}}, stream)
        self.assertEqual({'i01-b01': ['i01-c01']}, bank.read_review_variants(self.tmp))

    def test_filler_generator_is_replaced_but_due_generator_is_not(self):
        sess = self.crowded(1)
        template = sess.cards['i01-g50']
        filler = []
        for n in range(3):
            cid = f'i01-g{n + 70}'
            sess.cards[cid] = dict(template, id=cid, family=cid, facts=['unrelated'])
            filler.append(cid)
        sess._cache = None
        state = sess._state()
        for name, expected in (('gen', True), ('due', False)):
            chosen = [('i01-b50', 'due')] + [(cid, name) for cid in filler]
            pools = [('due', ['i01-b50'] + (filler if name == 'due' else []))]
            selected, pairs, _, deferred = service._review_pairs(sess, state, chosen, pools, 20)
            self.assertEqual(expected, 'i01-g50' in dict(selected))
            self.assertEqual(4, len(selected))
            self.assertEqual([], deferred)

    def test_arrangement_counts_choice_companions_before_placing_them(self):
        sess = self.crowded(6, variants=0)
        state = sess._state()
        sources = ['i01-b50', 'i01-b51', 'i01-b52']
        pairs = {}
        for n, source in enumerate(sources):
            cid = f'i01-c{n + 70}'
            sess.cards[cid] = dict(sess.cards[source], id=cid)
            pairs[source] = cid
        choices = set(sources) | set(pairs.values())
        with mock.patch.object(sess, 'card_form', side_effect=lambda card, box: 'choice' if card['id'] in choices else 'blank'):
            for seed in range(20):
                ids = service._arrange(sess, state, [(cid, 'due') for cid in sess.cards if cid not in pairs.values()],
                                       random.Random(seed), after=pairs)
                run = 0
                for cid in ids:
                    run = run + 1 if cid in choices else 0
                    self.assertLessEqual(run, service.CHOICE_RUN)
                for source, target in pairs.items():
                    self.assertEqual(target, ids[ids.index(source) + 1])

    def test_published_mapping_uses_available_same_unit_evidence_and_different_questions(self):
        mapping = bank.read_review_variants(bank.AI_DIR)
        self.assertTrue(mapping)
        for course in ('intro', 'app'):
            sess = self.session(course)
            for lid in sess.lessons:
                sess._append({'kind': 'open', 'lesson': lid})
            state = sess._state()
            for source, targets in mapping.items():
                if bank.course_of(source) != course:
                    continue
                with self.subTest(source=source):
                    lead = sess.cards[source]
                    options = service._variants(state, lead, fixed=True)
                    self.assertTrue(targets)
                    self.assertEqual(len(targets), len(set(targets)))
                    for target in targets:
                        self.assertIn(target, options)
                        other = sess.cards[target]
                        self.assertIn(other['kind'], ('blank', 'choice', 'gen'))
                        self.assertEqual((lead['lesson'], lead['unit']), (other['lesson'], other['unit']))
                        if other['kind'] != 'gen':
                            self.assertNotEqual(lead.get('item', {}).get('stem'), other['item']['stem'])

    def test_full_selection_keeps_pair_after_filler_limits_and_blank_balancing(self):
        sess = self.crowded(1)
        template = sess.cards['i01-g50']
        for n in range(3):
            cid = f'i01-g{n + 70}'
            sess.cards[cid] = dict(template, id=cid, family=cid, facts=['unrelated'])
            for day in ('04', '05', '06'):
                self.answer_before(sess, cid, day=day)
        sess._cache = None
        state = sess._state()
        self.assertTrue(all(cid not in state.due_cards() for cid in ('i01-g70', 'i01-g71', 'i01-g72')))
        ids, trace = self.select(sess)
        self.assertEqual(['i01-b50', 'i01-g50'], ids)
        self.assertEqual(set(ids), set(trace['selected_pools']))
        self.assertEqual({'i01-b50': 'i01-g50'}, trace['paired'])

    def test_reviewed_correction_reference_does_not_hide_a_valid_fixed_pair(self):
        sess = self.opened(cid='i01-b04')
        sess.review_variants = {'i01-b04': ['i01-c04']}
        self.assertTrue(sess.cards['i01-c04']['errata'])
        ids, trace = self.select(sess)
        self.assertEqual(['i01-b04', 'i01-c04'], ids)
        self.assertEqual('rules-v5', trace['policy'])
        self.answer_before(sess, 'i01-b04', result='stuck', day='09')
        trace = {}
        ids = service.build_set(sess, sess._state(), 'note', random.Random(7), card='i01-b04', trace=trace)
        self.assertEqual(['i01-b04', 'i01-c04'], ids)
        self.assertEqual('rules-v5', trace['policy'])
        self.assertTrue(trace['variant_catalog_revision'])
        self.answer_before(sess, 'i01-c04', day='09')
        self.assertNotIn('i01-c04', self.select(sess)[0])


class StableCardOrderTest(Base):
    def test_fixed_only_loading_keeps_full_order_and_rejects_missing_fixed_cards(self):
        bank.load_common()
        for lid in ('i01', 'a02'):
            with self.subTest(lesson=lid):
                full = bank.cards_of({'id': lid}, bank.load_items({'id': lid}))
                with mock.patch.object(bank.genlib, 'load_module', side_effect=AssertionError('생성기는 읽지 않음')):
                    partial = bank.load_items({'id': lid}, with_gens=False)
                fixed = bank.cards_of({'id': lid}, partial)
                expected = {card['id']: card['order'] for card in full if card['kind'] != 'gen'}
                self.assertEqual(expected, {card['id']: card['order'] for card in fixed})
                original = copy.deepcopy(partial)
                for defect in ('missing_fixed', 'duplicate_fixed', 'unknown_order', 'duplicate_order', 'missing_generator'):
                    with self.subTest(defect=defect):
                        partial = copy.deepcopy(original)
                        if defect == 'missing_fixed':
                            partial['items'].pop()
                        elif defect == 'duplicate_fixed':
                            partial['items'].append(copy.deepcopy(partial['items'][0]))
                        elif defect == 'unknown_order':
                            partial['meta']['card_order'].append(lid + '-unknown')
                        elif defect == 'duplicate_order':
                            partial['meta']['card_order'].append(fixed[0]['id'])
                        else:
                            gid = next(card['id'] for card in full if card['kind'] == 'gen')
                            partial['meta']['card_order'].remove(gid)
                        with self.assertRaises(bank.AiBankError):
                            bank.cards_of({'id': lid}, partial)

    def test_adding_fixed_question_keeps_saved_statement_and_generator(self):
        sess = self.session()
        data = copy.deepcopy(sess.items['i90'])
        original = bank.cards_of({'id': 'i90'}, data)
        ids = [card['id'] for card in original]
        preserved = [card for card in original if card['kind'] in ('stmt', 'gen')]
        self.assertTrue(any(card['kind'] == 'gen' for card in preserved))
        self.assertTrue(any(card['kind'] == 'stmt' for card in preserved))
        saved = []
        for card in preserved:
            ps = sess.start_set('note', card=card['id'], seed=3)
            ps.current()
            saved.append(json.loads(json.dumps(ps.snapshot())))
        added = copy.deepcopy(data['items'][0])
        added.update(id='i90-b99', family='i90-b99')
        data['items'].append(added)
        data['meta']['card_order'] = ids + ['i90-b99']
        current = bank.cards_of({'id': 'i90'}, data)
        sess.cards.update({card['id']: card for card in current})
        for snapshot in saved:
            restored = service.PracticeSet.restore(sess, snapshot)
            self.assertEqual(snapshot['fingerprint'], restored.fingerprint())
        changed = next(card for card in preserved if card['kind'] == 'stmt')['id']
        sess.cards[changed]['stmt']['text'] += ' 바뀐 내용'
        snapshot = next(value for value in saved if changed in value['stats'])
        with self.assertRaisesRegex(ValueError, '문항이 바뀐'):
            service.PracticeSet.restore(sess, snapshot)

    def test_invalid_saved_order_is_rejected(self):
        data = self.session().items['i90']
        ids = [card['id'] for card in bank.cards_of({'id': 'i90'}, data)]
        for invalid in (ids[:-1], ids + [ids[0]], ids[:-1] + ['i90-unknown'], 'not-a-list'):
            with self.subTest(order=invalid):
                data['meta']['card_order'] = invalid
                with self.assertRaises(bank.AiBankError):
                    bank.cards_of({'id': 'i90'}, data)
