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
    mid = 'm4'
    app_lessons = 3
    revision = 'mixed32-blueprint-v1'
    blueprint = None
    variation_types = None

    def setUp(self):
        self.fixture = legacy.ValidationTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bank = self.fixture.bank
        index = self.fixture.read('index.json')
        for n in range(1, self.app_lessons + 1):
            self.add_app_lesson(index, n)
        self.spec = dict(id=self.mid, title='혼합 검증', count=32, minutes=120, range=[1,17], window=[],
                         scope='mixed', courses=['intro','app'], course_counts={'intro':16,'app':16},
                         blueprint=dict(self.blueprint or verify_ai.MIXED_BLUEPRINT), blueprint_revision=self.revision)
        self.meta = dict(self.spec, format=1, draft=True, time_basis='연습 기본 시간입니다. 공식 시간은 아닙니다.')
        if self.variation_types:
            self.meta['variation_types'] = list(self.variation_types)
        index['mocks'].append(self.spec)
        self.fixture.write('index.json', index)
        lessons = [lid for lid, count in self.spec['blueprint'].items() for _ in range(count)]
        self.items = []
        for n, lid in enumerate(lessons):
            app = lid.startswith('a')
            no = int(lid[1:])
            unit = ('a%da' if app else '%da') % no
            fid = ('FA%02d-20' if app else 'F%02d-20') % no
            item = dict(id='%s-%02d' % (self.mid, n+1), lesson=lid, course='app' if app else 'intro', unit=unit, step=unit+'/1',
                        facts=[fid], sourcefacts=[{'lesson':lid,'id':fid}], related_sources=[],
                        ref=[('응용 %d차시 슬 p1' if app else '%d차시 슬 p1') % no],
                        family='mixed-case-%d' % n, concept='연산 비교', topic='연산 비교',
                        level=1 if n<8 else 2 if n<24 else 3, format='short_calculation' if n<16 else 'concept_judgment',
                        transferaxis='comparison', conditions=['입력을 고정함'], level_reason='연산 조건을 비교함.',
                        blueprint_revision=self.revision, explain='입력과 연산의 조건을 비교합니다.')
            if self.variation_types:
                item['transferaxis'] = self.variation_types[n % len(self.variation_types)]
            if n<16:
                item.update(kind='blank', stem='mixed_case_%d cobalt quartz의 값을 쓰세요. ____' % n,
                            blanks=[{'mode':'number','answer':['2']}], allowed_answers=[['2']])
            else:
                item.update(kind='choice', stem='mixed_case_%d copper velvet에서 옳은 것을 고르세요.' % n,
                            pick='right', multi=False, options=[{'text':'조건 %d' % k,'ok':k==0,
                            'why':'입력 조건을 비교합니다.','aim':'입력 혼동'} for k in range(4)])
            self.items.append(item)
        self.save()

    def add_app_lesson(self, index, n):
        """개론 n차시 자료를 복사해 응용 n차시를 만듦. index는 호출한 쪽에서 저장함."""
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

    def publish_app_lesson(self, n):
        """회차를 만든 뒤 공개된 응용 차시를 목록에 더함."""
        index = self.fixture.read('index.json')
        self.add_app_lesson(index, n)
        self.fixture.write('index.json', index)

    def save(self):
        self.fixture.write('mocks/'+self.mid+'/meta.json', self.meta)
        self.fixture.write('mocks/'+self.mid+'/work/items.json', {'format':1,'items':self.items})

    def verify(self, *args):
        output = io.StringIO()
        code = verify_ai.main([self.mid,'--bank',str(self.bank),'--seeds','2']+list(args), output)
        return code, output.getvalue()

    def test_native_parser_preserves_mixed_metadata_and_draft_is_checked(self):
        parsed = next(m for m in bank.read_index(str(self.bank))['mocks'] if m['id']==self.mid)
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
        row['related_sources'][0]['lesson'] = 'a%02d' % (self.app_lessons + 1)
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
        self.assertFalse((self.bank/'mocks'/self.mid/'work/review.json').exists())
        self.meta['draft'] = False
        self.save()
        self.assertEqual(1, self.verify('--require-review')[0])
        code, output = self.verify('--sign', *legacy.NAMES)
        self.assertEqual(0, code, output)
        with redirect_stdout(io.StringIO()):
            ai_seal.seal(str(self.bank/'mocks'/self.mid), self.mid)
        self.assertFalse((self.bank/'mocks'/self.mid/'work/items.json').exists())
        code, output = self.verify('--require-review')
        self.assertEqual(0, code, output)
        self.meta['blueprint_revision'] = 'test-v2'
        self.fixture.write('mocks/'+self.mid+'/meta.json', self.meta)
        self.assertEqual(1, self.verify('--require-review')[0])

    def test_duplicate_with_legacy_fails_without_extending_fact_reuse_rule(self):
        original = self.fixture.read('mocks/m1/work/items.json')['items'][0]
        self.items[0].update(stem=original['stem'], blanks=original['blanks'], allowed_answers=[b['answer'] for b in original['blanks']])
        self.save()
        self.assertIn('회차 간 같은 문항', self.verify()[1])


class Applied04MixedValidationTest(MixedValidationTest):
    mid = 'm6'
    app_lessons = 4
    revision = 'mixed32-applied04-v1'
    blueprint = dict({'i%02d' % n: 1 for n in range(1, 18) if n != 10}, a01=4, a02=4, a03=4, a04=4)
    variation_types = ['condition', 'application', 'code_analysis', 'comparison']

    def update_index(self):
        index = self.fixture.read('index.json')
        index['mocks'] = [self.spec if row['id'] == self.mid else row for row in index['mocks']]
        self.fixture.write('index.json', index)

    def test_revision_rejects_forged_blueprint_even_when_items_match_it(self):
        self.spec['blueprint'] = dict(self.blueprint, a01=5, a04=3)
        self.meta['blueprint'] = dict(self.spec['blueprint'])
        target = next(item for item in self.items if item['lesson'] == 'a01')
        moved = next(item for item in self.items if item['lesson'] == 'a04')
        for key in ('lesson', 'unit', 'step', 'facts', 'sourcefacts', 'ref'):
            moved[key] = copy.deepcopy(target[key])
        self.update_index()
        self.save()
        code, output = self.verify()
        self.assertEqual(1, code, output)
        self.assertIn('blueprint', output)
        self.assertIn('실제 lesson 배분', output)

    def test_legacy_revision_cannot_declare_the_applied04_blueprint(self):
        self.spec['blueprint_revision'] = self.meta['blueprint_revision'] = 'mixed32-transfer-v1'
        for item in self.items:
            item['blueprint_revision'] = self.spec['blueprint_revision']
        self.update_index()
        self.save()
        code, output = self.verify()
        self.assertEqual(1, code, output)
        self.assertIn('blueprint', output)

    def test_applied04_supporting_facts_are_checked_and_applied05_is_rejected(self):
        row = self.items[0]
        row['related_sources'] = [{'lesson':'a04', 'facts':['FA04-20']}]
        row['sourcefacts'].append({'lesson':'a04', 'id':'FA04-20'})
        self.save()
        code, output = self.verify()
        self.assertEqual(0, code, output)
        self.publish_app_lesson(5)
        row['related_sources'] = [{'lesson':'a05', 'facts':['FA05-20']}]
        row['sourcefacts'][-1] = {'lesson':'a05', 'id':'FA05-20'}
        self.save()
        code, output = self.verify()
        self.assertEqual(1, code, output)
        self.assertIn('공개 범위', output)

    def test_each_course_must_cover_all_four_variation_types(self):
        original = copy.deepcopy(self.items)
        for course in ('intro', 'app'):
            with self.subTest(course=course):
                self.items = copy.deepcopy(original)
                for item in self.items:
                    if item['course'] == course:
                        item['transferaxis'] = 'condition'
                self.save()
                code, output = self.verify()
                self.assertEqual(1, code, output)
                self.assertIn(course+' 문항에 변형 유형', output)

    def test_missing_variation_types_are_rejected(self):
        self.meta.pop('variation_types')
        self.save()
        code, output = self.verify()
        self.assertEqual(1, code, output)
        self.assertIn('variation_types', output)

    def test_unknown_revision_is_rejected(self):
        self.spec['blueprint_revision'] = self.meta['blueprint_revision'] = 'mixed32-unregistered-v1'
        for item in self.items:
            item['blueprint_revision'] = self.spec['blueprint_revision']
        self.update_index()
        self.save()
        code, output = self.verify()
        self.assertEqual(1, code, output)
        self.assertIn('blueprint_revision', output)

    def test_revision_that_is_not_text_fails_without_raising(self):
        self.spec['blueprint_revision'] = self.meta['blueprint_revision'] = ['mixed32-applied04-v1']
        self.update_index()
        self.save()
        code, output = self.verify()
        self.assertEqual(1, code, output)
        self.assertIn('blueprint_revision이 등록되지 않았습니다', output)

    def test_lesson_practice_cannot_be_reused_as_an_exam_question(self):
        practice = self.fixture.read('items/a04/work/items.json')['items'][0]
        self.items[-1]['stem'] = practice['stem']
        self.save()
        code, output = self.verify()
        self.assertEqual(1, code, output)
        self.assertIn('연습 지문 토큰 자카드', output)


class PublishedSecretCheckTest(unittest.TestCase):
    def test_published_content_passes_the_unchanged_secret_scanner(self):
        root=Path(__file__).resolve().parents[1]/'ai'
        verifier=verify_ai.Verifier(None,io.StringIO())
        verify_ai.check_secrets(verifier,str(root))
        self.assertEqual([],verifier.failures)
        self.assertIsNotNone(verify_ai.SECRET.search('sk-'+'test'*8))


class AdditionalMixedExamTest(unittest.TestCase):
    def test_new_mixed_exam_keeps_count_source_draft_and_duplicate_checks(self):
        old = MixedValidationTest()
        old.setUp()
        old.meta['draft'] = False
        old.save()
        self.addCleanup(old.doCleanups)
        index = old.fixture.read('index.json')
        spec = dict(old.spec, id='m5', blueprint_revision='mixed32-transfer-v1')
        index['mocks'].append(spec)
        old.fixture.write('index.json', index)
        axes = ['condition', 'application', 'code_analysis', 'comparison']
        meta = dict(spec, format=1, draft=True, time_basis='연습 시간입니다.', variation_types=axes)
        items = copy.deepcopy(old.items)
        for n, item in enumerate(items):
            item['transferaxis'] = axes[n % 4]
            item['id'] = item['id'].replace('m4-', 'm5-')
            item['blueprint_revision'] = 'mixed32-transfer-v1'
            item['stem'] = '달라진 조건을 비교합니다. ' + item['stem']
        old.fixture.write('mocks/m5/meta.json', meta)
        old.fixture.write('mocks/m5/work/items.json', {'items': items})

        def verify(*args):
            output = io.StringIO()
            code = verify_ai.main(['m5', '--bank', str(old.bank), '--seeds', '2', *args], output)
            return code, output.getvalue()

        code, output = verify()
        self.assertEqual(0, code, output)
        self.assertIn('초안 상태', verify('--sign', *legacy.NAMES)[1])
        items[0]['stem'] = old.items[0]['stem']
        old.fixture.write('mocks/m5/work/items.json', {'items': items})
        self.assertIn('회차 간 같은 문항', verify()[1])
        items[0]['course'] = 'app'
        old.fixture.write('mocks/m5/work/items.json', {'items': items})
        self.assertIn('실제 course 배분', verify()[1])

    def test_legacy_blueprint_rejects_supporting_facts_from_applied04_published_later(self):
        old = MixedValidationTest()
        old.setUp()
        self.addCleanup(old.doCleanups)
        old.publish_app_lesson(4)
        code, output = old.verify()
        self.assertEqual(0, code, output)
        row = old.items[0]
        row['related_sources'] = [{'lesson':'a04', 'facts':['FA04-20']}]
        row['sourcefacts'].append({'lesson':'a04', 'id':'FA04-20'})
        old.save()
        code, output = old.verify()
        self.assertEqual(1, code, output)
        self.assertIn('공개 범위', output)

    def test_variation_types_are_required_by_revision_for_a_later_exam_id(self):
        later = Applied04MixedValidationTest()
        later.mid = 'm7'
        later.setUp()
        self.addCleanup(later.doCleanups)
        code, output = later.verify()
        self.assertEqual(0, code, output)
        later.meta.pop('variation_types')
        later.save()
        code, output = later.verify()
        self.assertEqual(1, code, output)
        self.assertIn('variation_types', output)

    def test_unfinished_mixed_draft_does_not_block_published_exam_and_cannot_be_signed(self):
        old = MixedValidationTest()
        old.setUp()
        self.addCleanup(old.doCleanups)
        index = old.fixture.read('index.json')
        spec = dict(old.spec, id='m7')
        index['mocks'].append(spec)
        old.fixture.write('index.json', index)
        old.fixture.write('mocks/m7/meta.json', dict(spec, format=1, draft=True, time_basis='연습 시간입니다.'))
        old.meta['draft'] = False
        old.save()
        code, output = old.verify()
        self.assertEqual(0, code, output)
        opts = type('Options', (), {'sign': True, 'require_review': False})()
        output = io.StringIO()
        verifier = verify_ai.Verifier(opts, output)
        verify_ai.signature_step(verifier, str(old.bank), 'm7', str(old.bank/'mocks/m7'))
        self.assertIn('초안 상태', output.getvalue())
