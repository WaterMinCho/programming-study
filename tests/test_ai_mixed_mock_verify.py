# -*- coding: utf-8 -*-
"""혼합 회차의 배분·과정·보조 근거와 서명 경계를 합성 은행에서 확인함."""
import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from aiprep import bank
from tools import ai_seal, verify_ai
from tests import test_ai_mock_rules as legacy


class MixedValidationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy.ValidationTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bank = self.fixture.bank
        index = self.fixture.read('index.json')
        for n in range(1, 4):
            old, lid, page = 'i%02d' % n, 'a%02d' % n, 'al%02d' % n
            entry = dict(index['lessons'][n-1], id=lid, page=page, course='app')
            index['lessons'].append(entry)
            index['pages'].append({'id': page, 'title': '응용 검증 차시'})
            index['order'].append(page)
            for source, dest in (('learn/l%02d' % n, 'learn/'+page), ('items/'+old, 'items/'+lid)):
                for path in (self.bank/source).rglob('*'):
                    if path.is_file():
                        text = path.read_text(encoding='utf-8').replace(old, lid).replace('l%02d' % n, page)
                        text = text.replace('F%02d-' % n, 'FA%02d-' % n).replace('%da' % n, 'a%da' % n)
                        text = text.replace('%d차시' % n, '응용 %d차시' % n)
                        self.fixture.text(str(Path(dest)/path.relative_to(self.bank/source)), text)
        self.spec = dict(id='m4', title='혼합 검증', count=32, minutes=120, range=[1,17], window=[],
                         scope='mixed', courses=['intro','app'], course_counts={'intro':16,'app':16},
                         blueprint=dict(verify_ai.MIXED_BLUEPRINT), blueprint_revision='test-v1')
        self.meta = dict(self.spec, format=1, draft=True, time_basis='연습 기본 시간입니다. 공식 시간은 아닙니다.')
        index['mocks'].append(self.spec)
        self.fixture.write('index.json', index)
        lessons = [lid for lid, count in self.spec['blueprint'].items() for _ in range(count)]
        self.items = []
        for n, lid in enumerate(lessons):
            app = lid.startswith('a')
            no = int(lid[1:])
            unit = ('a%da' if app else '%da') % no
            fid = ('FA%02d-20' if app else 'F%02d-20') % no
            item = dict(id='m4-%02d' % (n+1), lesson=lid, course='app' if app else 'intro', unit=unit, step=unit+'/1',
                        facts=[fid], sourcefacts=[{'lesson':lid,'id':fid}], related_sources=[],
                        ref=[('응용 %d차시 슬 p1' if app else '%d차시 슬 p1') % no],
                        family='mixed-case-%d' % n, concept='연산 비교', topic='연산 비교',
                        level=1 if n<8 else 2 if n<24 else 3, format='short_calculation' if n<16 else 'concept_judgment',
                        transferaxis='comparison', conditions=['입력을 고정함'], level_reason='연산 조건을 비교함.',
                        blueprint_revision='test-v1', explain='입력과 연산의 조건을 비교합니다.')
            if n<16:
                item.update(kind='blank', stem='mixed_case_%d cobalt quartz의 값을 쓰세요. ____' % n,
                            blanks=[{'mode':'number','answer':['2']}], allowed_answers=[['2']])
            else:
                item.update(kind='choice', stem='mixed_case_%d copper velvet에서 옳은 것을 고르세요.' % n,
                            pick='right', multi=False, options=[{'text':'조건 %d' % k,'ok':k==0,
                            'why':'입력 조건을 비교합니다.','aim':'입력 혼동'} for k in range(4)])
            self.items.append(item)
        self.save()

    def save(self):
        self.fixture.write('mocks/m4/meta.json', self.meta)
        self.fixture.write('mocks/m4/work/items.json', {'format':1,'items':self.items})

    def verify(self, *args):
        output = io.StringIO()
        code = verify_ai.main(['m4','--bank',str(self.bank),'--seeds','2']+list(args), output)
        return code, output.getvalue()

    def test_native_parser_preserves_mixed_metadata_and_draft_is_checked(self):
        parsed = next(m for m in bank.read_index(str(self.bank))['mocks'] if m['id']=='m4')
        for key in ('scope','courses','course_counts','blueprint','blueprint_revision'):
            self.assertEqual(self.spec[key], parsed[key])
        code, output = self.verify()
        self.assertEqual(0, code, output)

    def test_actual_counts_levels_and_kinds_cannot_follow_forged_metadata(self):
        original = copy.deepcopy(self.items)
        for field, value in (('course','app'),('lesson','i02'),('level',2),('kind','choice')):
            with self.subTest(field=field):
                self.items = copy.deepcopy(original)
                self.items[0][field] = value
                if field == 'kind':
                    self.items[0].update(options=copy.deepcopy(self.items[-1]['options']), pick='right')
                self.save()
                code, output = self.verify()
                self.assertEqual(1, code, output)
                self.assertIn('실제 '+field+' 배분', output)

    def test_sourcefacts_course_range_and_related_errata_are_checked(self):
        row = self.items[0]
        row['related_sources'] = [{'lesson':'i10','facts':['F10-20']}]
        row['sourcefacts'].append({'lesson':'i10','id':'F10-20'})
        self.save()
        self.assertEqual(0, self.verify()[0])
        path = 'items/i10/work/facts.json'
        data = self.fixture.read(path)
        next(f for f in data['facts'] if f['id']=='F10-20')['errata'] = ['X10-01']
        self.fixture.write(path, data)
        self.assertIn('정정 근거 사실 i10/F10-20', self.verify()[1])
        row['related_sources'][0]['lesson'] = 'a04'
        self.save()
        self.assertIn('공개 범위', self.verify()[1])
        row['related_sources'] = []
        self.save()
        self.assertIn('sourcefacts가', self.verify()[1])

    def test_document_ref_must_exist_in_that_lesson_fact(self):
        row = self.items[0]
        row['ref'] = ['https://example.invalid/confirmed']
        self.save()
        self.assertEqual(1, self.verify()[0])
        data = self.fixture.read('items/i01/work/facts.json')
        next(f for f in data['facts'] if f['id']==row['facts'][0])['where'] = row['ref']
        self.fixture.write('items/i01/work/facts.json', data)
        self.assertEqual(0, self.verify()[0])

    def test_draft_blocks_signing_then_temporary_release_roundtrips_seal_and_review(self):
        code, output = self.verify('--sign', *legacy.NAMES)
        self.assertEqual(1, code, output)
        self.assertIn('초안 상태', output)
        self.assertFalse((self.bank/'mocks/m4/work/review.json').exists())
        self.meta['draft'] = False
        self.save()
        self.assertEqual(1, self.verify('--require-review')[0])
        code, output = self.verify('--sign', *legacy.NAMES)
        self.assertEqual(0, code, output)
        with redirect_stdout(io.StringIO()):
            ai_seal.seal(str(self.bank/'mocks/m4'), 'm4')
        self.assertFalse((self.bank/'mocks/m4/work/items.json').exists())
        code, output = self.verify('--require-review')
        self.assertEqual(0, code, output)
        self.meta['blueprint_revision'] = 'test-v2'
        self.fixture.write('mocks/m4/meta.json', self.meta)
        self.assertEqual(1, self.verify('--require-review')[0])

    def test_duplicate_with_legacy_fails_without_extending_fact_reuse_rule(self):
        original = self.fixture.read('mocks/m1/work/items.json')['items'][0]
        self.items[0].update(stem=original['stem'], blanks=original['blanks'], allowed_answers=[b['answer'] for b in original['blanks']])
        self.save()
        self.assertIn('회차 간 같은 문항', self.verify()[1])


class PublishedSecretCheckTest(unittest.TestCase):
    def test_published_content_passes_the_unchanged_secret_scanner(self):
        root=Path(__file__).resolve().parents[1]/'ai'
        verifier=verify_ai.Verifier(None,io.StringIO())
        verify_ai.check_secrets(verifier,str(root))
        self.assertEqual([],verifier.failures)
        self.assertIsNotNone(verify_ai.SECRET.search('sk-'+'test'*8))
