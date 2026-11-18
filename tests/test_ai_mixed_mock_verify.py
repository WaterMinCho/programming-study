# -*- coding: utf-8 -*-
"""혼합 회차의 배분·과정·보조 근거와 서명 경계를 합성 은행에서 확인함."""
import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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


CODE_STARTER = 'def out_size(w, f, p, s):\n    if f == w:\n        return 1\n    ____\n    return size'
CODE_SOLUTION = ['size = (w - f + 2 * p) // s + 1']
CODE_EXAMPLES = [{'args': [32, 3, 1, 1], 'expected': 32}, {'args': [28, 5, 0, 1], 'expected': 24}]
CODE_TESTS = [{'args': [7, 3, 0, 2], 'expected': 3}, {'args': [9, 4, 1, 2], 'expected': 4},
              {'args': [224, 11, 2, 4], 'expected': 55}, {'args': [13, 3, 1, 3], 'expected': 5},
              {'args': [64, 7, 3, 2], 'expected': 32}, {'args': [17, 6, 2, 3], 'expected': 6}]


class CodeItemVerifyTest(unittest.TestCase):
    """혼합 회차 32번을 코드 작성 문항으로 바꿔 꼴 검사·출제 검증·재풀이 채점과 메시지 규칙을 봄.
    32문항 계약은 코드 작성을 받지 않으므로 실제 kind 배분 실패는 따로 빼고 셈."""

    def setUp(self):
        self.old = MixedValidationTest()
        self.old.setUp()
        self.addCleanup(self.old.doCleanups)
        row = self.old.items[31]
        for key in ('options', 'pick', 'multi'):
            row.pop(key)
        row.update(kind='code', stem='합성곱 출력 크기를 돌려주는 함수 out_size를 완성하세요.', solution=list(CODE_SOLUTION),
                   code={'starter': CODE_STARTER, 'entry': 'out_size', 'examples': copy.deepcopy(CODE_EXAMPLES),
                         'tests': copy.deepcopy(CODE_TESTS), 'limit_ms': 2000, 'tol': None})
        self.row = row

    def check(self, *args):
        self.old.save()
        output = io.StringIO()
        v = verify_ai.Verifier(verify_ai.parse_args(['--bank', str(self.old.bank), '--seeds', '2', *args]), output)
        spec = next(m for m in bank.read_index(str(self.old.bank))['mocks'] if m['id'] == 'm4')
        les = verify_ai.check_mock(v, str(self.old.bank), spec, {}, None)
        messages = [message for _, _, message in v.failures if '실제 kind 배분' not in message]
        return messages, output.getvalue(), les, v

    def hidden_texts(self):
        public = set().union(*(verify_ai._value_texts(case) for case in self.row['code']['examples']))
        return {text for case in self.row['code']['tests'] for text in verify_ai._value_texts(case)} - public

    def assert_no_hidden(self, text):
        flat = ''.join(text.split())
        for hidden in self.hidden_texts():
            self.assertNotIn(hidden, flat)

    def test_synthetic_code_item_passes_and_is_graded_by_the_resolver_answers(self):
        messages, output, les, v = self.check()
        self.assertEqual([], messages, output)
        self.assertIn('실제 kind 배분', output)
        self.assertIn('m4-32', [card['id'] for card in les.cards if card['kind'] == 'code'])
        path = self.old.bank / 'answers.json'
        for answer, correct in ((list(CODE_SOLUTION), 1), (['size = (w - f) // s + 1'], 0), (['a', 'b'], 0), ('size', 0)):
            with self.subTest(answer=answer):
                path.write_text(json.dumps({'m4-32': answer}), encoding='utf-8')
                graded = verify_ai.grade_answers(v, 'answers', str(path), [les], str(self.old.bank))
                self.assertEqual((1, correct), (graded['cards'], graded['correct']))

    def test_each_broken_code_item_fails_without_printing_hidden_values(self):
        def tests_like(expected):
            return [dict(case, expected=expected) for case in CODE_TESTS]
        same = [{'args': [64, 7, 3, 2], 'expected': 32}, {'args': [32, 5, 2, 1], 'expected': 32},
                {'args': [34, 3, 0, 1], 'expected': 32}, {'args': [63, 1, 0, 2], 'expected': 32},
                {'args': [32, 1, 0, 1], 'expected': 32}, {'args': [36, 5, 0, 1], 'expected': 32}]
        cases = (
            ('모르는 유형', {}, {'kind': 'essay'}, 'm4-32는 빈칸, 객관식, 코드 작성 가운데 하나여야 합니다.'),
            ('엔진이 읽지 못하는 꼴', {}, {'solution': CODE_SOLUTION * 2}, '코드 작성 꼴이 맞지 않습니다'),
            ('숨은 테스트 수', {'tests': CODE_TESTS[:5]}, None, '숨은 테스트는 6~10개'),
            ('예시 수', {'examples': CODE_EXAMPLES[:1]}, None, '예시는 2~3개'),
            ('입력 겹침', {'tests': [dict(CODE_TESTS[0], args=[32, 3, 1, 1])] + CODE_TESTS[1:]}, None,
             '숨은 테스트 1번 입력이 예시 입력과 같습니다'),
            ('반환 꼴', {'tests': CODE_TESTS[:5] + [dict(CODE_TESTS[5], expected={'size': 5})]}, None,
             '숨은 테스트 6번 기대값은 실행기가 돌려받을 수 없는 꼴'),
            ('None 반환', {'examples': [dict(CODE_EXAMPLES[0], expected=None), CODE_EXAMPLES[1]]}, None,
             '예시 1번 기대값은 실행기가'),
            ('지문 누출', {}, {'stem': '합성곱 출력 크기를 돌려주는 함수 out_size를 완성하세요. out_size(224, 11, 2, 4)도 확인합니다.'},
             'stem에 숨은 테스트 3번'),
            ('조건 누출', {}, {'conditions': ['입력 7, 3, 0, 2를 넣음']}, 'conditions에 숨은 테스트 1번'),
            ('모범 답안 오답', {'tests': CODE_TESTS[:2] + [dict(CODE_TESTS[2], expected=54)] + CODE_TESTS[3:]}, None,
             '숨은 테스트 3번에서 모범 답안이 틀립니다'),
            ('시작 코드 통과', {'tests': CODE_TESTS[:3] + [{'args': [5, 5, 0, 1], 'expected': 1}] + CODE_TESTS[4:]}, None,
             '시작 코드가 숨은 테스트 4번을 통과합니다'),
            ('첫 예시의 기대값만 돌려주는 답', {'tests': same}, None,
             '가짜 답(첫 예시의 기대값만 돌려주는 답)이 숨은 테스트를 모두 통과합니다. 첫 예시와 기대값이 다른 숨은 테스트를 넣으세요.'),
            ('빈 모범 답안 줄', {}, {'solution': ['']}, 'm4-32의 모범 답안 1번째 줄이 비어 있습니다.'),
            ('예시 오답', {'examples': [CODE_EXAMPLES[0], dict(CODE_EXAMPLES[1], expected=25)]}, None,
             '예시 2번에서 모범 답안이 틀립니다'),
            ('문장 끝 누출', {}, {'stem': '합성곱 출력 크기를 돌려주는 함수 out_size를 완성하세요. 입력은 224, 11, 2, 4.'},
             'stem에 숨은 테스트 3번'),
            ('3.10 문법', {}, {'solution': ['type Size = int; size = (w - f + 2 * p) // s + 1']}, 'Python 3.10 문법'),
        )
        original = copy.deepcopy(self.row)
        for name, code, fields, expected in cases:
            with self.subTest(name=name):
                self.row.clear()
                self.row.update(copy.deepcopy(original))
                self.row['code'].update(copy.deepcopy(code))
                self.row.update(copy.deepcopy(fields or {}))
                messages, output, _, _ = self.check()
                self.assertTrue(any(expected in message for message in messages), output)
                self.assert_no_hidden(output)

    def test_sourcefacts_leak_is_found(self):
        self.row['sourcefacts'] = self.row['sourcefacts'] + [{'lesson': 'a03', 'id': '224,11,2,4'}]
        messages = [message for message, _ in verify_ai._code_form_problems(self.row)]
        self.assertIn('m4-32의 sourcefacts에 숨은 테스트 3번의 입력이나 기대값이 적혀 있습니다.', messages)

    def test_string_values_leak_in_any_quote_style(self):
        self.row['solution'] = ['out = s[::-1]']
        self.row['code'].update(starter='def flip(s):\n    ____\n    return out', entry='flip',
                                examples=[{'args': ['abc'], 'expected': 'cba'}, {'args': ['rokey'], 'expected': 'yekor'}],
                                tests=[{'args': [word], 'expected': word[::-1]}
                                       for word in ('hello', 'python', 'ab', 'level', 'tensor', 'data')])
        for stem, number in (("문자열을 뒤집습니다. 'hello' 를 넣으면 'olleh' 가 나옵니다.", 1),
                             ('문자열을 뒤집습니다. "hello" 를 넣으면 "olleh" 가 나옵니다.', 1),
                             ('문자열을 뒤집습니다. hello 를 넣으면 olleh 가 나옵니다.', 1),
                             ("문자열을 뒤집습니다. 'ab' 를 넣으면 'ba' 가 나옵니다.", 3),
                             ("문자열을 뒤집습니다. 'abc' 를 넣으면 'cba' 가 나옵니다.", None)):
            with self.subTest(stem=stem):
                self.row['stem'] = stem
                found = [number for message, number in verify_ai._code_form_problems(self.row) if 'stem에' in message]
                self.assertEqual([number] if number else [], found)

    def test_number_leak_needs_number_boundaries(self):
        self.row['stem'] = '합성곱 출력 크기를 돌려주는 함수입니다. 예: out_size(77, 3, 0, 21) 처럼 부릅니다.'
        self.assertEqual([], verify_ai._code_form_problems(self.row))

    def test_table_of_example_answers_must_fail_a_hidden_test(self):
        """입력 겹침 검사가 먼저 막는 경우라 실행 검사만 따로 부름."""
        self.row['code']['tests'] = copy.deepcopy(CODE_EXAMPLES) * 3
        messages = [message for message, _ in verify_ai._code_run_problems(self.row)]
        self.assertIn('m4-32의 가짜 답(예시 입력과 기대값을 표로 외운 답)이 숨은 테스트를 모두 통과합니다. '
                      '예시와 다른 입력을 숨은 테스트에 넣으세요.', messages)
        self.assertFalse(any('첫 예시의 기대값만' in message for message in messages), messages)

    def test_same_expected_values_report_only_the_constant_answer(self):
        """입력은 모두 예시와 다르고 기대값이 모두 첫 예시와 같으면 표 답도 통과하지만 입력을 바꾸라는 안내는 틀린 처방임."""
        self.row['code']['tests'] = [dict(case, expected=32) for case in CODE_TESTS]
        messages = [message for message, _ in verify_ai._code_run_problems(self.row) if '가짜 답' in message]
        self.assertEqual(['m4-32의 가짜 답(첫 예시의 기대값만 돌려주는 답)이 숨은 테스트를 모두 통과합니다. '
                          '첫 예시와 기대값이 다른 숨은 테스트를 넣으세요.'], messages)

    def test_solution_must_finish_in_a_quarter_of_the_limit_and_repeat_its_result(self):
        self.row['code']['limit_ms'] = 400
        self.row['solution'] = ['import time; time.sleep(0.15); size = (w - f + 2 * p) // s + 1']
        messages, output, _, _ = self.check()
        self.assertIn('m4-32의 숨은 테스트 1번에서 모범 답안 호출이 시간 제한의 4분의 1(100ms)을 넘깁니다.', messages, output)
        self.assertFalse(any('모범 답안이 틀립니다' in message for message in messages), output)
        self.row['solution'] = list(CODE_SOLUTION)
        real = verify_ai.mock_code.grade

        def flaky(item, lines, workers=None):
            result = real(item, lines, workers)
            if item['code'].get('limit_ms') == 100 and lines == CODE_SOLUTION:
                result = dict(result, result='stuck', cases=[{'status': 'wrong', 'reason': '돌려준 값이 다릅니다.'}] * 6)
            return result
        with mock.patch.object(verify_ai.mock_code, 'grade', flaky):
            messages, output, _, _ = self.check()
        self.assertEqual(['m4-32의 모범 답안을 두 번 돌린 결과가 다릅니다.'], messages, output)

    def test_hidden_values_appear_only_with_the_author_option(self):
        self.row['code']['tests'][2]['expected'] = 54
        self.row['code']['tests'][4]['expected'] = 33
        messages, output, _, _ = self.check()
        self.assertIn('m4-32의 숨은 테스트 3번에서 모범 답안이 틀립니다. 돌려준 값이 다릅니다.', messages, output)
        self.assert_no_hidden(output)
        how = '걸린 숨은 테스트의 입력과 기대값은 출제자 컴퓨터에서 python tools/verify_ai.py m4 --show-hidden-tests 로 확인합니다.'
        self.assertEqual(1, output.count(how), output)
        messages, output, _, _ = self.check('--show-hidden-tests')
        self.assertIn('숨은 테스트 3번 입력 [224, 11, 2, 4], 기대값 54', output)
        self.assertNotIn(how, output)

    def test_how_to_see_hidden_values_is_not_printed_without_numbered_failures(self):
        self.row['code']['examples'] = CODE_EXAMPLES[:1]
        messages, output, _, _ = self.check()
        self.assertTrue(any('예시는 2~3개' in message for message in messages), output)
        self.assertNotIn('--show-hidden-tests', output)
