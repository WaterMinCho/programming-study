# -*- coding: utf-8 -*-
"""기록 판을 재사용할 때 요약·선택 순서와 파일 교체 반영을 확인함."""
import copy
import json
import os
import random
import shutil

import study
from aiprep import service
from tests.test_ai_service import Base, FIXTURE


class CachedStateTest(Base):
    def read_and_answer(self, sess):
        for unit in sess.unit_list('i90'):
            sess.record.append({'kind': 'learn', 'lesson': 'i90', 'unit': unit['key']}, at='2026-11-08T20:00:00')
        sess.record.append({'kind': 'open', 'lesson': 'i90'}, at='2026-11-08T20:00:00')
        for cid in sess.cards:
            sess.record.append({'kind': 'answer', 'card': cid, 'result': 'pass', 'sure': False,
                                'again': 0, 'set': 'baseline'}, at='2026-11-09T12:00:00')

    def test_weighted_selection_keeps_fixed_seed_order(self):
        sess = self.session()
        self.read_and_answer(sess)
        expected = {
            7: ['i90-s01', 'i90-g02', 'i90-s04', 'i90-c01', 'i90-s08', 'i90-b01', 'i90-s07', 'i90-b02',
                'i90-b04', 'i90-c03', 'i90-s06', 'i90-b03', 'i90-s05', 'i90-s02', 'i90-c02', 'i90-s03'],
            12: ['i90-s06', 'i90-b02', 'i90-s04', 'i90-c01', 'i90-b01', 'i90-s08', 'i90-g01', 'i90-s02',
                 'i90-g02', 'i90-c03', 'i90-b04', 'i90-s01', 'i90-s07', 'i90-s03', 'i90-s05', 'i90-c02'],
        }
        for seed, cards in expected.items():
            with self.subTest(seed=seed):
                self.assertEqual(cards, service.build_set(sess, sess._state(), 'mixed', random.Random(seed)))

    def test_overview_return_values_are_independent(self):
        sess = self.session()
        first = sess.overview()
        expected = copy.deepcopy(first)
        first['lessons'][0]['title'] = '바뀐 제목'
        first['lessons'][0]['units'].clear()
        first['errors']['i90'] = '오류'
        first['activity'].append('2020-01-01')
        self.assertEqual(expected, sess.overview())

    def test_overview_updates_after_answer_and_study_day_boundary(self):
        sess = self.session()
        before = sess.overview()
        self.read_and_answer(sess)
        after = sess.overview()
        self.assertGreater(after['today_answers'] + after['today_extra'], before['today_answers'] + before['today_extra'])
        self.assertEqual(after, self.session().overview())
        self.at = '2026-11-10T03:59:00'
        late = sess.overview()
        self.assertEqual(after['today_answers'] + after['today_extra'], late['today_answers'] + late['today_extra'])
        self.at = '2026-11-10T04:00:00'
        early = sess.overview()
        self.assertEqual(0, early['today_answers'] + early['today_extra'])
        self.assertEqual(early, self.session().overview())

    def test_overview_updates_after_mock_publication_and_error(self):
        self.root = os.path.join(self.tmp, 'bank')
        shutil.copytree(FIXTURE, self.root)
        sess = self.session()
        mid = next(iter(sess.mocks))
        self.assertFalse(next(row for row in sess.overview()['mocks'] if row['id'] == mid)['ready'])
        os.makedirs(os.path.join(self.root, 'mocks', mid))
        study.write_text(os.path.join(self.root, 'mocks', mid, 'meta.json'), '{}')
        self.assertTrue(next(row for row in sess.overview()['mocks'] if row['id'] == mid)['ready'])
        sess.errors['i91'] = '자료를 읽을 수 없습니다.'
        self.assertEqual(sess.errors, sess.overview()['errors'])

    def test_record_replacement_with_same_size_and_mtime_is_reloaded(self):
        sess = self.session()
        sess.record.append({'kind': 'open', 'lesson': 'i90'})
        data = copy.deepcopy(sess.record.load())
        before = os.stat(sess.record.path)
        reads = sess.record.reads
        data['log'][0]['lesson'] = 'i91'
        replacement = sess.record.path + '.replacement'
        study.write_text(replacement, json.dumps(data, ensure_ascii=False, indent=1) + '\n')
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        os.replace(replacement, sess.record.path)
        self.assertEqual(before.st_size, os.stat(sess.record.path).st_size)
        self.assertEqual(before.st_mtime_ns, os.stat(sess.record.path).st_mtime_ns)
        self.assertEqual('i91', sess.record.load()['log'][0]['lesson'])
        self.assertEqual(reads + 1, sess.record.reads)
