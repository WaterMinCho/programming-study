# -*- coding: utf-8 -*-
"""과정이 다른 같은 차시 번호와 기존 기록의 보존을 확인함."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import study
from aiprep import bank, service
from learning_server import dataset, starter


class CourseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bank = self.root / 'bank'
        shutil.copytree(Path(__file__).parent / 'ai_bank', self.bank)
        for source, dest in [('learn/l90', 'learn/al90'), ('items/i90', 'items/a90')]:
            shutil.copytree(self.bank / source, self.bank / dest)
            for p in (self.bank / dest).rglob('*'):
                if p.suffix in ('.json', '.md', '.py'):
                    text = p.read_text(encoding='utf-8').replace('i90', 'a90').replace('l90', 'al90')
                    text = text.replace('90a', 'a90a').replace('90b', 'a90b')
                    p.write_text(text, encoding='utf-8')
        # 봉인 대신 기존 평문 예제를 바꿔 독립된 시험 은행을 만듦.
        from webprep.bank import load_secrets
        original = load_secrets(str(self.bank / 'items/i90'))
        work = self.bank / 'items/a90/work'
        work.mkdir(exist_ok=True)
        for name, text in original.items():
            (work / name).write_text(text.replace('i90', 'a90').replace('90a', 'a90a').replace('90b', 'a90b'), encoding='utf-8')
        path = self.bank / 'index.json'
        index = json.loads(path.read_text(encoding='utf-8'))
        index['pages'].append({'id': 'al90', 'title': '응용 시험'})
        index['order'].append('al90')
        entry = dict(index['lessons'][0], id='a90', page='al90', course='app')
        index['lessons'].append(entry)
        path.write_text(json.dumps(index), encoding='utf-8')
        patch = mock.patch.object(study, 'SUBMISSIONS_DIR', str(self.root / 'subs'))
        patch.start()
        self.addCleanup(patch.stop)

    def session(self, course):
        return service.AiSession('alice', home=str(self.root / 'home'), root=str(self.bank), course=course)

    def test_same_number_has_distinct_cards_and_old_progress_survives(self):
        intro = self.session('intro')
        intro.mark_read('i90', '90a')
        intro.save_step('i90', '90a', 2)
        before = Path(intro.record.path).read_bytes()
        app = self.session('app')
        self.assertEqual(before, Path(intro.record.path).read_bytes())
        self.assertIn('a90-b01', app.cards)
        self.assertNotIn('i90-b01', app.cards)
        self.assertNotIn('a90-b01', intro.cards)
        self.assertFalse(app._state().reads)
        self.assertEqual(intro.collection.path, app.collection.path)
        self.assertNotEqual(intro.home, app.home)
        app.mark_read('a90', 'a90a')
        app.save_step('a90', 'a90a', 3)
        restored = self.session('intro')
        self.assertEqual(2, restored.unit_steps('i90', '90a')['at_step'])
        self.assertEqual(3, self.session('app').unit_steps('a90', 'a90a')['at_step'])
        self.assertNotIn(('a90', 'a90a'), restored._state().reads)
        self.assertEqual(json.loads(before)['log'], restored.record.log[:len(json.loads(before)['log'])])

    def test_shared_consent_participant_and_sequences_have_observed_course(self):
        intro, app = self.session('intro'), self.session('app')
        intro.collection.set_enabled(True)
        participant = intro.collection.status()['participant']
        self.assertEqual(participant, app.collection.status()['participant'])
        intro.save_recall('i90', '90a', 'r', True, value='x', block={'q':'무엇 ____', 'answer':['x']})
        app.save_recall('a90', 'a90a', 'r', True, value='x', block={'q':'무엇 ____', 'answer':['x']})
        rows = list(app.collection.snapshot())
        recalls = [r for r in rows if r.get('kind') == 'recall']
        self.assertEqual(['intro', 'app'], [r['data']['course'] for r in recalls])
        self.assertEqual(['intro', 'app'], [r['item']['course'] for r in recalls])
        self.assertEqual(len(rows), len({r['sequence'] for r in rows if 'sequence' in r}) + 1)
        app.collection.set_enabled(False)
        count = len(list(intro.collection.snapshot()))
        intro.mark_read('i90', '90a')
        self.assertEqual(count, len(list(intro.collection.snapshot())))

    def test_bank_course_mismatch_fails_and_app_has_no_intro_exam(self):
        self.assertEqual('a01', bank.lesson_of_unit('a1a'))
        self.assertIsNone(bank.lesson_of_unit('18a'))
        self.assertEqual('a18', bank.lesson_of_unit('a18a'))
        self.assertTrue(all(v is None for v in self.session('app').exam.values()))
        path = self.bank / 'index.json'
        index = json.loads(path.read_text(encoding='utf-8'))
        index['lessons'][-1]['course'] = 'intro'
        path.write_text(json.dumps(index), encoding='utf-8')
        with self.assertRaises(bank.AiBankError):
            bank.read_index(str(self.bank))


class CourseDatasetTest(unittest.TestCase):
    def test_first_source_reference_distinguishes_same_lesson_number(self):
        from tools.verify_ai import first_ref_ok
        self.assertTrue(first_ref_ok("응용 1차시 슬 p4", 1, "app"))
        self.assertFalse(first_ref_ok("1차시 슬 p4", 1, "app"))
        self.assertFalse(first_ref_ok("응용 1차시 슬 p4", 1, "intro"))
        self.assertTrue(first_ref_ok("1차시 슬 p4", 1, "intro"))

    def test_missing_course_stays_unknown_and_new_course_enters_history(self):
        events = dataset.synthetic_events()[:3]
        for n, e in enumerate(events):
            e['track'] = 'ai'
            e['item']['lesson'] = 'i01' if n == 0 else 'a01'
            e['item']['card'] = ('i01' if n == 0 else 'a01') + '-b01'
        for e in events[1:]:
            e['item']['course'] = e['data']['course'] = 'app'
        rows = dataset.prepare(events)
        self.assertIsNone(rows[0]['course'])
        self.assertEqual('intro', rows[0]['course_inferred'])
        self.assertEqual('app', rows[1]['course'])
        self.assertIsNone(rows[1]['course_inferred'])
        self.assertEqual('app', rows[2]['features']['sequence_history'][-1]['course'])
        changed = copy.deepcopy(events)
        changed[-1]['data']['result'] = 'wrong'
        self.assertEqual(rows[-1]['features'], dataset.prepare(changed)[-1]['features'])
        events[-1]['data']['course'] = 'intro'
        with self.assertRaises(ValueError):
            dataset.prepare(events)

    def test_train_only_course_vocabulary_and_separate_metrics(self):
        events = dataset.synthetic_events()
        for e in events:
            if e['track'] == 'ai':
                e['item']['course'] = 'app' if e['sequence'] >= 5 else 'intro'
        with tempfile.TemporaryDirectory() as root:
            starter.write_starter(events, Path(root) / 'starter')
            vocab = json.loads((Path(root) / 'starter/vocabulary.json').read_text(encoding='utf-8'))
            self.assertNotIn('app', vocab['ai']['courses'])
            result = json.loads((Path(root) / 'starter/baseline.json').read_text(encoding='utf-8'))
            self.assertEqual(result['ai']['test']['metrics']['rows'], result['ai']['test']['by_course']['app']['rows'])
