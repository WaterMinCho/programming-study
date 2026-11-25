"""개론 변형 문항의 단원 출제·복습·표시 조건 보존을 확인함."""
import ast
import copy
import datetime as dt
import json
import os
import random
from unittest import mock

from aiprep import bank, gen, grade, service
from learning_data import generation
from learning_server import dataset, input_example
from tests.test_ai_service import Base


class IntroVariationTest(Base):
    def session(self):
        return service.AiSession('alice', home=os.path.join(self.tmp, 'home'), root=bank.AI_DIR)

    def ready(self, sess, lesson='i04', unit='4c'):
        sess.mark_read(lesson, unit)
        for day in ('08', '09'):
            self.at = f'2026-11-{day}T20:00:00'
            for c in sess.cards.values():
                if (c['lesson'], c['unit']) == (lesson, unit) and c['core']:
                    sess._append({'kind': 'answer', 'set': day, 'card': c['id'], 'result': 'pass', 'again': 0})

    def crowded(self, sess):
        source = next(c for c in sess.cards.values() if c['lesson'] == 'i04' and c['unit'] == '4c'
                      and not c['core'] and c['kind'] != 'gen')
        for n in range(9):
            card = copy.deepcopy(source)
            card.update(id=f'i04-test-{n}', family=f'test-family-{n}', order=-20 + n)
            sess.cards[card['id']] = card

    def select(self, sess, mode='unit'):
        trace = {}
        chosen = service.build_set(sess, sess._state(), mode, random.Random(7), lesson='i04', unit='4c', trace=trace)
        return chosen, trace

    def test_unit_promotes_one_eligible_generator_and_preserves_other_new_order(self):
        sess = self.session()
        self.crowded(sess)
        self.ready(sess)
        chosen, trace = self.select(sess)
        fresh = next(p['ids'] for p in trace['candidate_pools'] if p['name'] == 'new' and not p['overflow'])
        self.assertEqual('i04-g03', fresh[0])
        self.assertEqual([f'i04-test-{n}' for n in range(7)], fresh[1:])
        self.assertIn('i04-g03', chosen)
        self.assertEqual('new', trace['selected_pools']['i04-g03'])
        self.assertEqual('rules-v8', trace['policy'])
        self.assertEqual(len(chosen), len({sess.cards[c]['family'] for c in chosen}))
        self.assertLessEqual(sum(sess.cards[c]['kind'] == 'gen' for c in chosen), max(1, int(len(chosen) * service.GEN_SHARE)))

    def test_unread_or_not_ready_unit_does_not_open_generator(self):
        sess = self.session()
        self.assertFalse(any(sess.cards[c]['kind'] == 'gen' for c in self.select(sess)[0]))
        sess.mark_read('i04', '4c')
        self.assertFalse(any(sess.cards[c]['kind'] == 'gen' for c in self.select(sess)[0]))

    def test_one_unanswered_core_keeps_noncore_generator_closed(self):
        sess = self.session()
        sess.mark_read('i04', '4c')
        cores = [c for c in sess.cards.values() if (c['lesson'], c['unit']) == ('i04', '4c') and c['core']]
        for day in ('08', '09'):
            self.at = f'2026-11-{day}T20:00:00'
            for c in cores[1:]:
                sess._append({'kind': 'answer', 'set': day, 'card': c['id'], 'result': 'pass', 'again': 0})
        chosen, _ = self.select(sess)
        self.assertIn(cores[0]['id'], chosen)
        self.assertFalse(any(sess.cards[c]['kind'] == 'gen' and not sess.cards[c]['core'] for c in chosen))

    def test_again_family_collision_uses_next_generator(self):
        sess = self.session()
        self.crowded(sess)
        self.ready(sess)
        cid = 'i04-test-0'
        sess.cards[cid]['family'] = sess.cards['i04-g03']['family']
        sess._append({'kind': 'answer', 'set': 'wrong', 'card': cid, 'result': 'fail', 'again': 0})
        chosen, trace = self.select(sess)
        self.assertIn(cid, chosen)
        self.assertNotIn('i04-g03', chosen)
        self.assertIn('i04-g09', chosen)
        self.assertEqual('new', trace['selected_pools']['i04-g09'])

    def test_due_generator_keeps_its_place_without_promoting_another(self):
        sess = self.session()
        self.crowded(sess)
        self.ready(sess)
        self.at = '2026-11-07T20:00:00'
        sess.mark_read('i03', '3g')
        sess._append({'kind': 'answer', 'set': 'old', 'card': 'i03-g03', 'result': 'pass', 'again': 0})
        self.at = '2026-11-09T20:00:00'
        chosen, trace = self.select(sess)
        self.assertIn('i03-g03', chosen)
        self.assertEqual('due', trace['selected_pools']['i03-g03'])
        fresh = next(p['ids'] for p in trace['candidate_pools'] if p['name'] == 'new' and not p['overflow'])
        self.assertEqual([f'i04-test-{n}' for n in range(8)], fresh)

    def test_due_static_family_is_not_displaced_by_a_new_generator(self):
        sess = self.session()
        self.crowded(sess)
        self.ready(sess)
        cid = 'i04-test-0'
        sess.cards[cid]['family'] = sess.cards['i04-g03']['family']
        self.at = '2026-11-07T20:00:00'
        sess._append({'kind': 'answer', 'set': 'old', 'card': cid, 'result': 'pass', 'again': 0})
        self.at = '2026-11-09T20:00:00'
        chosen, trace = self.select(sess)
        self.assertIn(cid, chosen)
        self.assertEqual('due', trace['selected_pools'][cid])
        self.assertNotIn('i04-g03', chosen)
        self.assertIn('i04-g09', chosen)

    def test_new_limit_and_last_new_day_still_apply(self):
        sess = self.session()
        self.crowded(sess)
        self.ready(sess)
        with mock.patch.object(service, 'NEW_PER_DAY', 1):
            chosen, trace = self.select(sess)
        self.assertEqual(['i04-test-0'], [c for c in chosen if trace['selected_pools'][c] == 'new'])
        sess.exam['last_new'] = dt.date(2026, 11, 8)
        _, trace = self.select(sess)
        self.assertFalse(any(p['ids'] for p in trace['candidate_pools'] if p['name'] == 'new'))

    def test_unanswered_core_cards_stay_ahead_of_variants(self):
        sess = self.session()
        self.crowded(sess)
        for n in range(9):
            sess.cards[f'i04-test-{n}']['core'] = True
        sess._append({'kind': 'open', 'lesson': 'i04'})
        _, trace = self.select(sess)
        fresh = next(p['ids'] for p in trace['candidate_pools'] if p['name'] == 'new' and not p['overflow'])
        self.assertEqual(8, len(fresh))
        self.assertTrue(all(sess.cards[c]['core'] for c in fresh))

    def test_review_and_sweep_reuse_answered_variants_without_opening_unseen_cards(self):
        sess = self.session()
        self.ready(sess)
        cid = 'i04-g09'
        for mode in ('review', 'sweep'):
            self.assertNotIn(cid, self.select(sess, mode)[0])
        self.at = '2026-11-07T20:00:00'
        sess._append({'kind': 'answer', 'set': 'old', 'card': cid, 'result': 'pass', 'again': 0})
        self.at = '2026-11-09T20:00:00'
        for mode in ('review', 'sweep'):
            chosen, trace = self.select(sess, mode)
            self.assertIn(cid, chosen)
            self.assertEqual('due', trace['selected_pools'][cid])
            self.assertNotIn('new', {p['name'] for p in trace['candidate_pools']})

    def test_new_families_enter_unit_practice_after_earlier_generators(self):
        sess = self.session()
        for cid in ('i03-g04', 'i04-g09', 'i06-g05', 'i14-g05', 'i16-g07', 'i17-g06'):
            card = sess.cards[cid]
            self.ready(sess, card['lesson'], card['unit'])
            for other in sess.cards.values():
                if (other['lesson'], other['unit']) == (card['lesson'], card['unit']) and other['kind'] == 'gen' and other['id'] != cid:
                    sess._append({'kind': 'answer', 'set': 'earlier', 'card': other['id'], 'result': 'pass', 'again': 0})
            trace = {}
            chosen = service.build_set(sess, sess._state(), 'unit', random.Random(7),
                                       lesson=card['lesson'], unit=card['unit'], trace=trace)
            self.assertIn(cid, chosen, cid)
            self.assertEqual('new', trace['selected_pools'][cid])

    def test_display_conditions_restore_and_reach_model_input_without_answers(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        provenance = []
        for cid in ('i03-g04', 'i04-g09', 'i06-g05', 'i14-g05', 'i16-g07', 'i17-g06'):
            practice = service.PracticeSet(sess, cid, 'unit', [cid], 7)
            first = practice.current()
            entry = practice.queue[0]
            source = practice._collection_item(entry)['content']['generation']
            provenance.append(source)
            self.assertEqual('declared', source['params_status'])
            self.assertEqual(set(sess.cards[cid]['gen'].meta['display_params']), set(source['params']))
            self.assertFalse(set(source['params']) & generation.RESERVED_PARAMS)
            restored = service.PracticeSet.restore(sess, json.loads(json.dumps(practice.snapshot())))
            self.assertEqual(first, restored.current())
            practice.answer(self.wrong(first), 1, False)
            self.assertEqual(first['stem'], sess.wrong_item(cid)['stem'])
            self.assertEqual(first['stem'], practice._view(entry)['item']['stem'])
            retry = practice.queue[-1]
            self.assertNotEqual(entry['seed'], retry['seed'])
            self.assertNotEqual(source['instance_id'], practice._collection_item(retry)['content']['generation']['instance_id'])
        rows = dataset.prepare(sess.collection.snapshot())
        vocabulary = {'questions': ['<PAD>', '<UNK>'], 'concepts': ['<PAD>', '<UNK>']}
        self.assertEqual(provenance, input_example.batch(rows, vocabulary)['question_provenance']['query'])

    def test_all_condition_branches_are_displayed_in_parseable_code(self):
        seen = {'i03-g04': set(), 'i04-g09': set(), 'i16-g07': set()}
        for lid, cid in (('i03', 'i03-g04'), ('i04', 'i04-g09'), ('i16', 'i16-g07')):
            spec = next(g for g in bank.load_items({'id': lid})['gens'] if g.id == cid)
            for seed in range(1, 31):
                item = gen.run(spec, seed)
                code = item['stem'].split('```python\n')[1].split('```')[0]
                ast.parse(code)
                p = item['params']
                if cid == 'i03-g04':
                    self.assertIn(f'torch.tensor({p["values"]})', code)
                    self.assertIn(f'sum(dim={p["dim"]})', code)
                    seen[cid].add(p['dim'])
                elif cid == 'i04-g09':
                    self.assertEqual(p['clear'], 'opt.zero_grad(set_to_none=True)' in code)
                    self.assertIn(f'loss2 = ({p["b"]}) * w', code)
                    seen[cid].add(p['clear'])
                else:
                    self.assertIn(f'start_dim={p["start_dim"]}', code)
                    self.assertIn(f'nn.Linear({p["in_features"]}, {p["classes"]})', code)
                    seen[cid].add((p['start_dim'], p['in_features'] == p['c'] * p['h'] * p['w']))
        self.assertEqual({0, 1}, seen['i03-g04'])
        self.assertEqual({False, True}, seen['i04-g09'])
        self.assertEqual({(0, False), (0, True), (1, False), (1, True)}, seen['i16-g07'])

    def test_equivalent_axis_shape_and_number_answers_are_accepted(self):
        specs = {g.id: g for lid in ('i14', 'i17') for g in bank.load_items({'id': lid})['gens']}
        cases = [gen.run(specs['i17-g06'], seed) for seed in range(1, 101)]
        axis = next(item for item in cases if item['params']['ask'] == 'concat_axis')
        for value in ('1', '-1'):
            self.assertEqual('pass', grade.grade_item(axis, [value])['result'])
        for value in ('0', '-2'):
            self.assertEqual('stuck', grade.grade_item(axis, [value])['result'])
        shape = next(item for item in cases if item['params']['ask'] == 'shape')
        value = shape['blanks'][0]['answer'][0]
        self.assertEqual('pass', grade.grade_item(shape, [str(list(ast.literal_eval(value)))])['result'])
        self.assertEqual('pass', grade.grade_item(shape, [value])['result'])
        self.assertEqual('pass', grade.grade_item(shape, [f'torch.Size({list(ast.literal_eval(value))})'])['result'])
        number = gen.run(specs['i14-g05'], 1)
        value = number['blanks'][0]['answer'][0]
        self.assertEqual('pass', grade.grade_item(number, [str(float(value))])['result'])

    def test_loss_optimizer_and_lstm_conditions_cover_all_question_branches(self):
        seen = {'i06-g05': set(), 'i14-g05': set(), 'i17-g06': set()}
        for lid, cid in (('i06', 'i06-g05'), ('i14', 'i14-g05'), ('i17', 'i17-g06')):
            spec = next(g for g in bank.load_items({'id': lid})['gens'] if g.id == cid)
            for seed in range(1, 101):
                item = gen.run(spec, seed)
                code = item['stem'].split('```python\n')[1].split('```')[0]
                ast.parse(code)
                p = item['params']
                if cid == 'i06-g05':
                    self.assertEqual(p['apply_sigmoid'], 'torch.sigmoid(outputs)' in code)
                    self.assertIn(f'nn.{p["loss_name"]}()', code)
                    self.assertIn(str(tuple(p['output_shape'])), item['stem'])
                    self.assertIn(str(tuple(p['label_shape'])), item['stem'])
                    seen[cid].add((p['output_shape'] == p['label_shape'], p['apply_sigmoid'], p['loss_name']))
                elif cid == 'i14-g05':
                    self.assertIn('SGD([p]' if p['registered'] else 'SGD([q]', code)
                    self.assertIn(f'p.requires_grad_({p["requires_grad"]})', code)
                    seen[cid].add((p['registered'], p['requires_grad'], p['stored_grad'] is None))
                else:
                    self.assertIn(f'bidirectional={p["bidirectional"]}', code)
                    self.assertIn(f'num_layers={p["layers"]}', code)
                    self.assertIn('batch_first=True, proj_size=0', code)
                    seen[cid].add((p['readout'], p['ask']))
        self.assertEqual(8, len(seen['i06-g05']))
        self.assertEqual(8, len(seen['i14-g05']))
        self.assertEqual({(readout, ask) for readout in ('output', 'h_n', 'c_n', 'last')
                          for ask in ('shape', 'batch_axis')} | {('last', 'concat_axis')}, seen['i17-g06'])
