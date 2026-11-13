# -*- coding: utf-8 -*-
"""혼합 회차의 공통 초안과 과정별 수집·복습을 임시 자료로 확인함."""
import copy
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest import mock

import study
from aiprep import bank, mixed_mock, service
from aiprep.mock import MockError, MockExam, load_items
from learning_data import collection
from learning_server import dataset
from webprep.bank import load_secrets

READ_INDEX = bank.read_index


def make_bank(root):
    """고정 예제에서 두 과정과 합성 32문항을 만듦. 실제 풀이 자료를 읽지 않음."""
    root = Path(root)
    shutil.copytree(Path(__file__).parent / 'ai_bank', root)
    for source, dest in [('learn/l90', 'learn/al90'), ('items/i90', 'items/a90')]:
        shutil.copytree(root/source, root/dest)
        for path in (root/dest).rglob('*'):
            if path.suffix in ('.json', '.md', '.py'):
                path.write_text(path.read_text(encoding='utf-8').replace('i90', 'a90').replace('l90', 'al90').replace('90a', 'a90a').replace('90b', 'a90b'), encoding='utf-8')
    work = root/'items/a90/work'
    work.mkdir(exist_ok=True)
    for name, text in load_secrets(str(root/'items/i90')).items():
        (work/name).write_text(text.replace('i90', 'a90').replace('90a', 'a90a').replace('90b', 'a90b'), encoding='utf-8')
    index = study.read_json(root/'index.json')
    index['pages'].append({'id':'al90','title':'응용 검사용 차시'})
    index['order'].append('al90')
    index['lessons'].append(dict(index['lessons'][0], id='a90', page='al90', course='app'))
    spec = dict(id='m4', title='혼합 모의고사', scope='mixed', courses=['intro','app'], minutes=120,
                count=32, range=[90,90], window=[], course_counts={'intro':16,'app':16},
                blueprint={'i90':16,'a90':16}, blueprint_revision='fixture-v1')
    index['mocks'].append(spec)
    study.write_text(root/'index.json', json.dumps(index))
    folder = root/'mocks/m4'
    (folder/'work').mkdir(parents=True)
    study.write_text(folder/'meta.json', json.dumps(dict(spec, draft=False)))
    items = []
    for n in range(1,33):
        app = n > 16
        items.append(dict(id='m4-%02d' % n, course='app' if app else 'intro', lesson='a90' if app else 'i90',
                          unit='a90a' if app else '90a', step='a90a/2' if app else '90a/2', family='shared-topic',
                          tags=['학습 루프'], level=2, kind='blank', stem='값을 쓰세요. ____',
                          concept='조건 비교', format='short_calculation', transferaxis='comparison',
                          conditions=['입력을 고정함'], sourcefacts=[{'lesson':'a90' if app else 'i90','id':'F90-01'}],
                          blanks=[{'mode':'number','answer':['3']}], explain='이 예제의 값은 3입니다.'))
    study.write_text(folder/'work/items.json', json.dumps({'items':items}))
    return root


def without_mixed_metadata(root):
    """불완전한 목록을 받은 경로만 별도로 확인함."""
    index = READ_INDEX(str(root))
    for spec in index['mocks']:
        for key in ('scope','courses','course_counts','blueprint','blueprint_revision'):
            spec.pop(key, None)
    return index


class MixedMockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mixed_mock_')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bank = make_bank(self.root/'bank')
        self.at = '2026-11-14T03:00:00+09:00'
        for obj, key, value in [(study,'SUBMISSIONS_DIR',str(self.root/'subs')),
                                 (service,'now',lambda:self.at),
                                 (collection,'stamp',lambda:self.at)]:
            patch = mock.patch.object(obj,key,value)
            patch.start()
            self.addCleanup(patch.stop)

    def session(self, course='intro'):
        return service.AiSession('learner',home=str(self.root/'home'),root=str(self.bank),course=course)

    def tick(self, seconds=1):
        self.at = (datetime.datetime.fromisoformat(self.at)+datetime.timedelta(seconds=seconds)).isoformat()

    def rows(self, sess, kind):
        return [r for r in sess.collection.snapshot(include_answers=True) if r['kind']==kind]

    def test_missing_parser_metadata_and_unreviewed_draft_are_hidden(self):
        with mock.patch.object(bank,'read_index',without_mixed_metadata):
            for course in ('intro','app'):
                sess=self.session(course)
                self.assertNotIn('m4',sess.mocks)
                self.assertIn('메타데이터',sess.overview()['mock_pending'])
                with self.assertRaises(service.AiError): sess.start_mock('m4')
        meta=study.read_json(self.bank/'mocks/m4/meta.json')
        meta['draft']=True
        study.write_text(self.bank/'mocks/m4/meta.json',json.dumps(meta))
        self.assertNotIn('m4',self.session().mocks)
        for invalid in ('[]','null'):
            study.write_text(self.bank/'mocks/m4/meta.json',invalid)
            self.assertNotIn('m4',self.session().mocks)

    def test_two_tabs_share_exam_answers_order_deadline_and_try(self):
        intro,app=self.session(),self.session('app')
        self.assertEqual(intro.collection.path,app.collection.path)
        self.assertNotEqual(intro.home,app.home)
        exam=intro.start_mock('m4',seed=17)
        exam.save_answer(['3'],'m4-17')
        exam.move(3)
        exam.toggle_flag()
        snapshot=copy.deepcopy(exam.draft)
        self.tick(31)
        other=app.start_mock('m4')
        self.assertIs(exam,other)
        self.assertEqual(exam.fingerprint,other.fingerprint)
        self.assertEqual(snapshot,other.draft)
        self.assertTrue(str(exam.path).startswith(intro.mock_home))
        self.assertEqual(7169,other.remaining())
        mixed_mock._EXAMS.clear()
        restored=self.session('app').start_mock('m4')
        self.assertEqual(snapshot,restored.draft)
        self.assertEqual(1,restored.attempt)
        self.assertFalse(any(cid.startswith('a90-') for cid in intro.cards))
        self.assertFalse(any(cid.startswith('i90-') for cid in app.cards))
        restored.submit()
        self.assertEqual(2,self.session().start_mock('m4',repeat=True).attempt)

    def test_classification_and_blueprint_changes_block_restore_without_touching_old_files(self):
        sess=self.session();exam=sess.start_mock('m4');before=Path(exam.path).read_bytes()
        path=self.bank/'mocks/m4/work/items.json';source=study.read_json(path)
        source['items'][0]['family']='changed-family'
        study.write_text(path,json.dumps(source))
        with self.assertRaisesRegex(service.AiError,'자료가 바뀌었습니다'): self.session().start_mock('m4')
        self.assertEqual(before,Path(exam.path).read_bytes())
        source['items'][0]['family']='shared-topic';study.write_text(path,json.dumps(source))
        spec=dict(sess.mocks['m4'],blueprint_revision='fixture-v2')
        meta=study.read_json(self.bank/'mocks/m4/meta.json');meta.update(blueprint_revision='fixture-v2')
        study.write_text(self.bank/'mocks/m4/meta.json',json.dumps(meta))
        self.assertNotEqual(exam.fingerprint,load_items(str(self.bank),spec,sess.mock_lessons)[1])
        first=load_items(str(self.bank),spec,sess.mock_lessons)[1]
        source['items'][0]['transferaxis']='new-condition'
        study.write_text(path,json.dumps(source))
        self.assertNotEqual(first,load_items(str(self.bank),spec,sess.mock_lessons)[1])
        source['items'][0]['course']='app';study.write_text(path,json.dumps(source))
        with self.assertRaises(MockError): load_items(str(self.bank),spec,sess.mock_lessons)

    def test_actual_items_and_legacy_fingerprints_keep_their_contracts(self):
        root=Path(__file__).resolve().parents[1]
        items=json.loads(load_secrets(str(root/'ai/mocks/m4'))['items.json'])['items']
        self.assertEqual(['m4-%02d' % n for n in range(1,33)],sorted(i['id'] for i in items))
        self.assertEqual(16,sum(i['course']=='intro' for i in items))
        self.assertEqual(16,sum(i['course']=='app' for i in items))
        specs=READ_INDEX(str(root/'ai'))['mocks']
        for spec in specs:
            if spec['id'] not in ('m1','m2','m3'):
                continue
            items,fingerprint=load_items(str(root/'ai'),spec)
            stable=[dict({k:i.get(k) for k in ('id','kind','stem','pick','multi')},
                         blanks=[{k:b.get(k) for k in ('answer','mode','places','unit','term','context')} for b in i.get('blanks') or []],
                         options=[{k:o.get(k) for k in ('text','ok')} for o in i.get('options') or []]) for i in items.values()]
            self.assertEqual(fingerprint,hashlib.sha256(json.dumps(stable,ensure_ascii=False,sort_keys=True).encode()).hexdigest())

    def test_item_course_snapshot_dedup_and_future_labels_are_preserved(self):
        sess=self.session();sess.collection.set_enabled(True);exam=sess.start_mock('m4',seed=41)
        for cid in ('m4-01','m4-17'):
            pos=exam.draft['order'].index(cid);exam.question(pos);exam.question(pos)
            self.tick();exam.save_answer(['3'],cid)
        self.assertEqual(2,len(self.rows(sess,'mock_question_returned')))
        self.assertEqual([],self.rows(sess,'mock_answer'))
        self.tick();exam.submit();exam.submit()
        returned=self.rows(sess,'mock_question_returned');answers=self.rows(sess,'mock_answer')
        self.assertEqual(32,len(answers))
        self.assertEqual(['intro','app'],[r['data']['course'] for r in returned])
        for row in returned:
            self.assertEqual(41,row['item']['seed'])
            self.assertEqual(90,row['item']['course_no'])
            self.assertEqual(row['data']['course'],row['item']['course'])
            for key in ('concept','format','transferaxis','conditions','sourcefacts'):
                self.assertEqual(exam.items[row['data']['card']][key],row['item'][key])
            self.assertEqual('author',row['item']['classification_basis'])
            self.assertNotIn('answer',json.dumps(row['item']))
        submissions=self.rows(sess,'mock_submit')
        self.assertEqual([16,16],[r['data']['of'] for r in submissions])
        self.assertEqual(1,len({r['at'] for r in submissions+answers}))
        prepared=dataset.prepare(sess.collection.snapshot())
        self.assertEqual(2,len(prepared))
        for cid in ('m4-01','m4-17'):
            shown=next(r for r in returned if r['data']['card']==cid)
            result=next(r for r in prepared if r['question_id']==cid)
            self.assertEqual(shown['at'],result['prediction_at'])
            self.assertEqual([],result['features']['sequence_history'])
        count=len(sess.collection.snapshot());self.session('app').start_mock('m4').question(0)
        self.assertEqual(count,len(sess.collection.snapshot()))

    def test_preconsent_and_prior_epoch_answers_are_not_copied(self):
        sess=self.session();exam=sess.start_mock('m4');exam.save_answer(['3'],'m4-01')
        sess.collection.set_enabled(True);self.tick();exam.save_answer(['3'],'m4-17')
        sess.collection.set_enabled(False);sess.collection.set_enabled(True)
        self.tick();exam.save_answer(['3'],'m4-18');self.tick();exam.submit()
        by_id={r['data']['card']:r['data'] for r in self.rows(sess,'mock_answer')}
        for cid in ('m4-01','m4-17'):
            self.assertEqual('not_collected',by_id[cid]['result'])
            self.assertIsNone(by_id[cid]['response'])
        self.assertEqual(['3'],by_id['m4-18']['response'])
        self.assertEqual(2,sum(r['data']['omitted_before_consent'] for r in self.rows(sess,'mock_submit')))

    def test_application_owner_keeps_intro_context_and_the_same_revision(self):
        app=self.session('app');app.collection.set_enabled(True)
        exam=app.start_mock('m4',seed=99)
        intro=self.session();other=intro.start_mock('m4')
        self.assertEqual(exam.fingerprint,other.fingerprint)
        self.assertEqual(exam.path,other.path)
        for cid in ('m4-01','m4-17'):
            other.question(other.draft['order'].index(cid));self.tick();other.save_answer(['3'],cid)
        self.tick();other.submit()
        returned=self.rows(app,'mock_question_returned');answered=self.rows(app,'mock_answer')
        for cid,course in (('m4-01','intro'),('m4-17','app')):
            shown=next(row for row in returned if row['data']['card']==cid)
            answer=next(row for row in answered if row['data']['card']==cid)
            self.assertEqual(course,shown['data']['course'])
            self.assertEqual(course,answer['item']['course'])
            self.assertEqual(99,answer['item']['seed'])
            self.assertEqual(shown['item_revision'],answer['item_revision'])
            self.assertEqual(shown['item']['options'],answer['item']['options'])

    def test_generic_override_is_ignored_and_only_valid_exam_items_use_other_course(self):
        sess=self.session();sess.collection.set_enabled(True);exam=sess.start_mock('m4',seed=8)
        sess.collect_event('recall',{'course':'app','scope':'mixed','marker':'ordinary'})
        row=self.rows(sess,'recall')[-1]
        self.assertEqual('intro',row['data']['course']);self.assertNotIn('scope',row['data'])
        count=len(sess.collection.snapshot())
        sess.collect_event('mock_answer',{'mock':'m4','try':1,'card':'m4-17','course':'app'},_mock_exam=types.SimpleNamespace())
        self.assertEqual(count,len(sess.collection.snapshot()))
        sess.collect_event('mock_question_returned',{'mock':'m4','try':1,'card':'m4-17','course':'intro'},
                           item={'content':{'course':'intro'},'revision':'forged'},_mock_exam=exam)
        row=self.rows(sess,'mock_question_returned')[-1]
        self.assertEqual('app',row['data']['course']);self.assertEqual('app',row['item']['course'])
        exam.items['m4-17']['course']='intro';count=len(sess.collection.snapshot())
        sess.collect_event('mock_question_returned',{'mock':'m4','try':1,'card':'m4-17'},_mock_exam=exam)
        self.assertEqual(count,len(sess.collection.snapshot()))

    def test_stop_withdrawal_blocks_both_tabs_and_new_epoch_does_not_replay_old_input(self):
        intro,app=self.session(),self.session('app');intro.collection.set_enabled(True)
        exam=app.start_mock('m4');exam.question();exam.save_answer(['3'],'m4-17')
        intro.collection.set_enabled(False);count=len(intro.collection.snapshot())
        exam.question(1);exam.save_answer(['3'],'m4-18')
        self.assertEqual(count,len(intro.collection.snapshot()))
        intro.collection.delete();exam.question(2);exam.save_answer(['3'],'m4-19')
        self.assertFalse(Path(app.collection.path).exists())
        intro.collection.set_enabled(True);self.tick();exam.save_answer(['3'],'m4-20');self.tick();exam.submit()
        answers={r['data']['card']:r['data'] for r in self.rows(intro,'mock_answer')}
        for cid in ('m4-17','m4-18','m4-19'):
            self.assertEqual('not_collected',answers[cid]['result'])
            self.assertIsNone(answers[cid]['response'])
        self.assertEqual('pass',answers['m4-20']['result'])

    def test_results_and_review_cards_stay_in_the_item_course(self):
        intro=self.session();exam=intro.start_mock('m4');exam.save_answer(['4'],'m4-17');result=exam.submit()
        self.assertTrue(any(cid.startswith('a90-') for cid in result['related']))
        app=self.session('app');intro.resume_course();app.resume_course()
        for sess,expected in ((intro,'intro'),(app,'app')):
            sess.overview()
            cards=[c for c in sess.cards.values() if c.get('mock')=='m4']
            self.assertEqual(16,len(cards))
            self.assertTrue(all(bank.course_of(c['after'])==expected for c in cards))
            self.assertEqual(0,sess.mock_state('m4')['first_score'])
        self.assertEqual('a90',app.wrong_item('m4-17')['lesson'])
        self.assertEqual('a90a/2',app.note_target('m4-17')['step'])

    def test_return_in_old_epoch_then_edit_in_new_epoch_keeps_summary_and_answer_together(self):
        sess=self.session();sess.collection.set_enabled(True);exam=sess.start_mock('m4')
        exam.question(exam.draft['order'].index('m4-01'));exam.save_answer(['4'],'m4-01')
        sess.collection.set_enabled(False);sess.collection.set_enabled(True)
        self.tick();exam.save_answer(['3'],'m4-01');exam.submit()
        answer=next(r for r in self.rows(sess,'mock_answer') if r['data']['card']=='m4-01')['data']
        summary=next(r for r in self.rows(sess,'mock_submit') if r['data']['course']=='intro')['data']
        self.assertEqual(['3'],answer['response'])
        self.assertEqual('pass',answer['result'])
        self.assertEqual('pass',summary['results']['m4-01'])
        self.assertEqual(exam.draft['collection_epochs']['m4-01'],exam.draft['collection_observations']['m4-01']['epoch'])

    def test_changed_classification_blocks_summary_as_well_as_item_events(self):
        sess=self.session();sess.collection.set_enabled(True);exam=sess.start_mock('m4')
        sess.mock_lessons['a90']['course']='intro'
        exam.submit()
        self.assertEqual([],self.rows(sess,'mock_submit'))
        self.assertFalse(any(r['data']['card']=='m4-17' for r in self.rows(sess,'mock_answer')))
        self.assertIn('분류',sess.collection.error)

    def test_actual_32_items_have_same_lesson_fact_fallback_without_family_or_tags(self):
        root=Path(__file__).resolve().parents[1]/'ai'
        raw=load_secrets(str(root/'mocks/m4')).get('items.json')
        if raw is None:
            self.skipTest('초안 문항은 검토 경로에서만 보관함')
        sess=service.AiSession('synthetic',home=str(self.root/'real-home'),root=str(root))
        exam=MockExam.__new__(MockExam)
        exam.id='m4';exam.sess=sess;exam.mixed=True
        exam.items={i['id']:dict(i,family='unmatched-test-family',tags=[]) for i in json.loads(raw)['items']}
        exam.draft={'order':list(exam.items)}
        cards=mixed_mock.related_cards(sess)
        app=service.AiSession('synthetic',home=str(self.root/'real-home'),root=str(root),course='app')
        self.assertEqual(set(cards),set(mixed_mock.related_cards(app)))
        self.assertFalse(any(c['kind']=='gen' for c in cards.values()))
        with mock.patch.object(mixed_mock,'related_cards',return_value=cards):
            for cid,item in exam.items.items():
                results={key:'pass' if key!=cid else 'fail' for key in exam.items}
                related=exam._related(results)
                self.assertEqual(1,len(related),cid)
                card=cards[related[0]]
                self.assertEqual(item['course'],bank.course_of(card['lesson']))
                self.assertEqual(item['lesson'],card['lesson'])
                self.assertTrue(set(item['facts']) & set(card['facts']))
                overlaps=[len(set(item['facts']) & set(c.get('facts') or [])) for c in cards.values()
                          if c.get('lesson')==item['lesson'] and not c.get('errata')]
                self.assertEqual(max(overlaps),len(set(item['facts']) & set(card['facts'])))
            all_wrong=exam._related(dict.fromkeys(exam.items,'fail'))
            self.assertEqual(len(set(all_wrong)),len(all_wrong))
            self.assertGreater(len(all_wrong),0)

    def test_fact_fallback_rejects_other_lesson_and_empty_overlap(self):
        sess=self.session();exam=sess.start_mock('m4')
        for item in exam.items.values():
            item.update(family='unmatched',tags=[],facts=['F90-01'])
        cards={'other':{'id':'other','lesson':'a89','facts':['F90-01']},
               'none':{'id':'none','lesson':'a90','facts':['other']},
               'intro':{'id':'intro','lesson':'i90','facts':['F90-01']}}
        results={cid:'pass' if cid!='m4-17' else 'fail' for cid in exam.items}
        with mock.patch.object(mixed_mock,'related_cards',return_value=cards):
            self.assertEqual([],exam._related(results))

    def test_actual_32_snapshots_match_for_both_starting_courses_without_answer_leaks(self):
        source=Path(__file__).resolve().parents[1]/'ai'
        raw=load_secrets(str(source/'mocks/m4')).get('items.json')
        if raw is None:
            self.skipTest('초안 문항은 검토 경로에서만 보관함')
        root=self.root/'snapshot-bank'
        shutil.copytree(source,root)
        meta=study.read_json(root/'mocks/m4/meta.json')
        study.write_text(root/'mocks/m4/meta.json',json.dumps(dict(meta,draft=False)))
        observed={}
        for owner in ('intro','app'):
            with self.subTest(owner=owner):
                home=str(self.root/('snapshot-home-'+owner))
                user='synthetic-'+owner
                sess=service.AiSession(user,home=home,root=str(root),course=owner)
                sess.collection.set_enabled(True)
                exam=sess.start_mock('m4',seed=103)
                other=service.AiSession(user,home=home,root=str(root),course='app' if owner=='intro' else 'intro')
                self.assertIs(exam,other.start_mock('m4'))
                self.assertEqual(sess.collection.path,other.collection.path)
                for position,cid in enumerate(exam.draft['order']):
                    exam.question(position)
                    item=exam.items[cid]
                    values=['검사답안']*len(item['blanks']) if item['kind']=='blank' else [0]
                    self.tick();exam.save_answer(values,cid)
                self.assertEqual([],self.rows(sess,'mock_answer'))
                self.tick();exam.submit()
                returned=self.rows(sess,'mock_question_returned')
                answered={r['data']['card']:r for r in self.rows(sess,'mock_answer')}
                self.assertEqual(32,len(returned))
                self.assertEqual(32,len(answered))
                for row in returned:
                    cid=row['data']['card'];item=exam.items[cid];content=row['item']
                    for key in ('course','concept','format','transferaxis','conditions','sourcefacts'):
                        self.assertEqual(item[key],content[key],(owner,cid,key))
                    self.assertEqual('mixed',content['scope'])
                    self.assertEqual('author',content['classification_basis'])
                    self.assertEqual(item['course'],row['data']['course'])
                    self.assertEqual(int(item['lesson'][1:]),content['course_no'])
                    self.assertEqual(103,content['seed'])
                    self.assertEqual(row['item_revision'],answered[cid]['item_revision'])
                    for hidden in ('answer','allowed_answers','explain','ok'):
                        self.assertNotIn(hidden,content)
                    for option in content['options']:
                        self.assertNotIn('ok',option)
                    for blank in content['blanks']:
                        self.assertNotIn('answer',blank)
                prepared=dataset.prepare(sess.collection.snapshot())
                self.assertEqual(32,len(prepared))
                self.assertTrue(all(not r['features']['sequence_history'] for r in prepared))
                self.assertEqual([16,16],[r['data']['of'] for r in self.rows(sess,'mock_submit')])
                observed[owner]={'fingerprint':exam.fingerprint,'order':list(exam.draft['order']),
                                 'revisions':{r['data']['card']:r['item_revision'] for r in returned}}
        self.assertEqual({'intro','app'},set(observed))
        self.assertEqual(observed['intro'],observed['app'])
        self.actual_snapshot_receipt={'items':32,'starting_courses':['intro','app'],
                                      'same_fingerprint_order_revisions':True,'author_metadata_preserved':True,
                                      'pre_submit_answers_absent':True,'same_exam_future_history_absent':True,
                                      'qa_copy_only_draft_false':True,'runtime':observed}
