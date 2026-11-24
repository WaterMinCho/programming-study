# -*- coding: utf-8 -*-
"""모의고사 시간·초안 복구·제출 판정과 기록을 임시 자료로 확인함."""
import copy
import datetime
import json
import os
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from aiprep import bank, grade, mock_code, review, service
from aiprep.mock import MockError, MockExam, load_items
from learning_data import collection
from aiprep.service import AiError
from webprep.record import Record, RecordError
from tests.test_ai_service import Base, FIXTURE
import shutil
import study


class Clock:
    def __init__(self):
        self.at = datetime.datetime(2026, 11, 5, 12, tzinfo=datetime.timezone.utc)
        self.mono = 100.0

    def advance(self, seconds):
        self.at += datetime.timedelta(seconds=seconds)
        self.mono += seconds


class ExamTest(unittest.TestCase):
    def test_unknown_start_version_cannot_rebuild_a_missing_draft_from_current_items(self):
        first = self.exam(seed=4)
        path = Path(self.session.record.path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["log"][0].pop("fingerprint")
        path.write_text(json.dumps(data), encoding="utf-8")
        self.session.record = Record(str(path), "learner")
        Path(first.path).unlink()
        before = path.read_bytes()
        with self.assertRaisesRegex(MockError, "문항 버전을 확인하지 못해"):
            self.exam()
        self.assertFalse(Path(first.path).exists())
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(2, self.exam(repeat=True).attempt)
        self.assertNotIn("fingerprint", self.session.record.log[0])

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ai_mock_")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / 'bank/mocks/m1'
        (self.folder / 'work').mkdir(parents=True)
        self.items = [
            {"id": "m1-01", "kind": "blank", "lesson": "i03", "stem": "숫자는 ____ 이고 메서드는 ____ 입니다.",
             "blanks": [{"answer": ["2"], "mode": "number"}, {"answer": ["zero_grad"], "mode": "code"}], "explain": "설명입니다."},
            {"id": "m1-02", "kind": "choice", "lesson": "i04", "stem": "옳은 것을 모두 고르세요.", "multi": True,
             "options": [{"text": str(n), "ok": n in (0, 2), "why": "설명입니다."} for n in range(4)]},
            {"id": "m1-03", "kind": "blank", "lesson": "i03", "stem": "정답은 ____ 입니다.",
             "blanks": [{"answer": ["3"], "mode": "number"}]},
            {"id": "m1-04", "kind": "choice", "lesson": "i05", "stem": "옳지 않은 것을 고르세요.", "pick": "wrong",
             "options": [{"text": str(n), "ok": n != 1} for n in range(4)]},
        ]
        (self.folder / 'meta.json').write_text('{}', encoding="utf-8")
        self.write_items()
        self.clock = Clock()
        self.session = types.SimpleNamespace(root=str(self.root/'bank'), home=str(self.root/'local'),
                                             mocks={'m1': {'id': 'm1', 'minutes': 1, 'count': 4}},
                                             record=Record(str(self.root/'record.json'), 'learner'), term_map=grade.term_map([]),
                                             _lock=threading.RLock())

    def write_items(self):
        (self.folder/'work/items.json').write_text(json.dumps({'items': self.items}, ensure_ascii=False), encoding="utf-8")

    def exam(self, **kwargs):
        return MockExam(self.session, 'm1', clock=lambda: self.clock.at, monotonic=lambda: self.clock.mono, **kwargs)

    def test_public_question_has_no_grading_fields(self):
        exam = self.exam(seed=3)
        def keys(value):
            if isinstance(value, dict):
                return set(value).union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()
        for pos in range(4):
            self.assertFalse(keys(exam.question(pos)) & {'answer', 'ok', 'why', 'explain', 'right', 'result', 'correct'})
        with self.assertRaises(MockError):
            exam.explain('m1-01')
        with self.assertRaises(MockError):
            exam.summary()
        self.assertEqual(['mock_start'], [r['kind'] for r in self.session.record.log])

    def test_restore_preserves_ids_answers_flags_and_shuffle(self):
        exam = self.exam(seed=4)
        exam.save_answer(['2', 'zero_grad'], 'm1-01')
        exam.move(2)
        exam.toggle_flag()
        self.clock.advance(17)
        restored = self.exam(seed=99)
        self.assertEqual(exam.draft, restored.draft)
        self.assertEqual(43, restored.remaining())
        self.assertEqual(2, restored.draft['current'])
        self.assertEqual(1, len(self.session.record.log))

    def test_submit_grades_once_without_raw_inputs(self):
        exam = self.exam(seed=2)
        exam.save_answer(['2', 'zero_grad'], 'm1-01')
        exam.save_answer([0], 'm1-02')
        exam.save_answer([1], 'm1-04')
        self.clock.advance(12)
        result = exam.submit()
        self.assertEqual({'m1-01': 'pass', 'm1-02': 'stuck', 'm1-03': 'blank', 'm1-04': 'pass'}, result['results'])
        self.assertEqual((2, 4, 12), (result['score'], result['of'], result['secs']))
        self.assertEqual(result, exam.submit())
        self.assertEqual(2, len(self.session.record.log))
        saved = json.dumps(self.session.record.load())
        self.assertNotIn('zero_grad', saved)
        self.assertNotIn('answers', saved)
        self.assertEqual(['2', 'zero_grad'], exam.explain('m1-01')['correct'])

    def test_some_empty_blanks_receive_no_partial_score(self):
        exam = self.exam()
        exam.save_answer(['2', ''], 'm1-01')
        self.assertFalse(exam.answered('m1-01'))
        result = exam.submit()
        self.assertEqual('stuck', result['results']['m1-01'])
        self.assertEqual(0, result['score'])

    def test_expired_exam_auto_submits_on_reopen(self):
        exam = self.exam()
        exam.save_answer(['3'], 'm1-03')
        self.clock.advance(70)
        restored = self.exam()
        self.assertTrue(restored.result['auto'])
        self.assertEqual((1, 60), (restored.result['score'], restored.result['secs']))
        self.assertEqual(0, restored.remaining())

    def test_late_answer_is_not_saved(self):
        exam = self.exam()
        self.clock.advance(61)
        self.assertFalse(exam.save_answer(['3'], 'm1-03'))
        self.assertNotIn('m1-03', exam.draft['answers'])
        self.assertEqual(0, exam.result['score'])

    def test_submit_checks_the_same_try_again_after_releasing_the_lock(self):
        exam = self.exam(seed=2)
        exam.save_answer(['3'], 'm1-03')
        other = self.exam(seed=2)
        out = {}

        def meanwhile():
            calls = (('save', lambda: exam.save_answer(['4'], 'm1-03')), ('submit', exam.submit),
                     ('other', lambda: other.submit(auto=True)))
            for name, call in calls:
                try:
                    out[name] = call()
                except MockError as error:
                    out[name] = str(error)

        exam.lock = BeforeSecondLock(exam.lock, lambda: in_thread(meanwhile))
        result = exam.submit()
        self.assertIn('채점하고 있습니다', out['save'])
        self.assertIn('채점하고 있습니다', out['submit'])
        self.assertEqual(out['other'], result)
        self.assertEqual(1, len(mock_submits(self.session.record.reload())))
        self.assertEqual(['3'], study.read_json(exam.path)['answers']['m1-03'])
        self.assertFalse(exam.submitting)

    def test_backwards_wall_clock_does_not_extend_time(self):
        exam = self.exam()
        self.clock.advance(20)
        self.clock.at -= datetime.timedelta(seconds=120)
        self.assertEqual(40, exam.remaining())
        self.clock.mono += 41
        self.assertFalse(exam.move(1))
        self.assertEqual(60, exam.result['secs'])

    def test_resumed_elapsed_time_survives_backwards_wall_clock(self):
        self.exam()
        self.clock.advance(30)
        restored = self.exam()
        self.clock.at -= datetime.timedelta(seconds=120)
        self.clock.mono += 10
        self.assertEqual(20, restored.remaining())
        self.assertEqual(40, restored.submit()['secs'])

    def test_retry_keeps_first_score_and_first_try_learning_results(self):
        first = self.exam(seed=1)
        first.submit()
        second = self.exam(repeat=True, seed=2)
        second.save_answer(['3'], 'm1-03')
        second.submit()
        summary = second.summary()
        self.assertEqual((0, 1, 2), (summary['first_score'], summary['score'], summary['try']))
        events = review.card_events(self.session.record.log)
        self.assertEqual(['stuck'], [row['result'] for row in events['m1-03']])

    def test_finished_score_is_available_without_local_draft(self):
        exam = self.exam(seed=2)
        exam.save_answer(['3'], 'm1-03')
        exam.submit()
        os.unlink(exam.path)
        restored = self.exam()
        self.assertEqual(1, restored.summary()['score'])
        self.assertIsNone(restored.question()['mine'])

    def test_active_exam_cannot_be_replaced_by_retry(self):
        self.exam()
        with self.assertRaises(MockError):
            self.exam(repeat=True)
        self.assertEqual(1, len(self.session.record.log))

    def test_missing_active_draft_keeps_the_original_deadline(self):
        first = self.exam(seed=3)
        deadline = first.draft["deadline"]
        self.clock.advance(15)
        Path(first.path).unlink()
        resumed = self.exam()
        self.assertEqual(1, resumed.attempt)
        self.assertEqual(deadline, resumed.draft["deadline"])
        self.assertEqual({}, resumed.draft["answers"])
        self.assertTrue(resumed.recovered_draft)
        self.assertEqual(45, resumed.remaining())
        self.assertEqual(1, len(self.session.record.log))

    def test_changed_active_exam_can_start_a_new_attempt_without_replacing_the_old_draft(self):
        first = self.exam(seed=3)
        original = Path(first.path).read_bytes()
        self.items[0]["stem"] += " 바뀐 조건입니다."
        self.write_items()
        second = self.exam(repeat=True, seed=4)
        self.assertEqual(2, second.attempt)
        self.assertEqual(original, Path(first.path).read_bytes())
        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(["mock_start", "mock_start"], [row["kind"] for row in self.session.record.log])

    def test_damaged_draft_is_preserved(self):
        exam = self.exam()
        Path(exam.path).write_text('{bad', encoding="utf-8")
        with self.assertRaises(MockError):
            self.exam()
        self.assertEqual('{bad', Path(exam.path).read_text(encoding="utf-8"))

    def test_changed_question_blocks_resume_but_explanation_change_does_not(self):
        exam = self.exam()
        self.items[1]['options'][0]['why'] = '고친 설명입니다.'
        self.write_items()
        self.exam()
        before = Path(exam.path).read_bytes()
        self.items[0]['stem'] += ' 바뀐 문제입니다.'
        self.write_items()
        with self.assertRaisesRegex(MockError, '문제 자료가 바뀌었습니다'):
            self.exam()
        self.assertEqual(before, Path(exam.path).read_bytes())

    def test_failed_draft_write_keeps_previous_answer(self):
        exam = self.exam()
        exam.save_answer(['3'], 'm1-03')
        before = Path(exam.path).read_bytes()
        with mock.patch('aiprep.mock.study.write_text', side_effect=OSError('test')):
            with self.assertRaises(MockError):
                exam.save_answer(['4'], 'm1-03')
        self.assertEqual(['3'], exam.draft['answers']['m1-03'])
        self.assertEqual(before, Path(exam.path).read_bytes())

    def test_failed_record_write_can_be_retried_without_duplicate_submit(self):
        exam = self.exam()
        with mock.patch.object(self.session.record, 'append', side_effect=RecordError('test')):
            with self.assertRaises(MockError):
                exam.submit()
        self.assertIsNone(exam.result)
        exam.submit()
        self.assertEqual(1, sum(row['kind'] == 'mock_submit' for row in self.session.record.log))

    def test_damaged_record_is_reported_without_replacing_the_draft(self):
        exam = self.exam()
        before = Path(exam.path).read_bytes()
        Path(self.session.record.path).write_text('{bad', encoding="utf-8")
        with self.assertRaises(MockError):
            exam.submit()
        self.assertEqual(before, Path(exam.path).read_bytes())
        self.assertEqual('{bad', Path(self.session.record.path).read_text(encoding="utf-8"))

    def test_changed_bank_keeps_old_score_and_allows_a_new_attempt(self):
        exam = self.exam()
        exam.submit()
        old = self.session.record.load()
        os.unlink(exam.path)
        self.items[0]['stem'] += ' 새 지문입니다.'
        self.write_items()
        with self.assertRaisesRegex(MockError, '문제 자료가 바뀌었습니다'):
            self.exam()
        self.assertEqual(old, self.session.record.load())
        self.assertEqual(2, self.exam(repeat=True).attempt)


class MockServiceTest(Base):
    def test_cached_course_resume_keeps_the_deadline_and_submits_only_once(self):
        sess = self.session()
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(["3"], "m90-01")
        self.at = "2026-11-09T20:01:00"
        sess.resume_course()
        self.assertEqual(3540, sess.mock_state("m90")["remaining"])
        self.assertEqual([], self.log(sess, "mock_submit"))
        self.at = "2026-11-09T21:01:00"
        sess.resume_course()
        self.assertFalse(sess.mock_state("m90")["active"])
        self.assertEqual(1, len(self.log(sess, "mock_submit")))
        sess.resume_course()
        self.assertEqual(1, len(self.log(sess, "mock_submit")))
        self.assertEqual(["3"], study.read_json(exam.path)["answers"]["m90-01"])

    def test_first_submission_after_a_bank_restart_keeps_review_score_and_history(self):
        sess = self.session()
        first = sess.start_mock("m90", seed=1)
        original = Path(first.path).read_bytes()
        self.mock_items[0]["stem"] += " 바뀐 조건입니다."
        self.mock_items[1]["tags"] = ["공유 주제"]
        path = Path(self.root) / "mocks/m90/work/items.json"
        path.write_text(json.dumps({"items": self.mock_items}, ensure_ascii=False), encoding="utf-8")
        sess = self.session()
        self.assertTrue(sess.mock_info("m90")["restart_required"])
        sess.cards["i90-b01"]["tags"] = ["공유 주제"]
        exam = sess.start_mock("m90", repeat=True, seed=2)
        exam.save_answer(["3"], "m90-01")
        exam.save_answer(["4"], "m90-02")
        submitted = exam.submit()
        self.assertEqual(2, submitted["try"])
        self.assertTrue(submitted["related"])
        self.assertEqual(original, Path(first.path).read_bytes())
        self.assertEqual(1, sess.mock_state("m90")["first_score"])
        self.assertEqual(["4"], sess.wrong_item("m90-02")["mine"])
        self.at = "2026-11-10T20:00:00"
        fresh = self.session()
        self.assertEqual(4, fresh.overview()["due"])
        self.assertEqual(1, fresh.hub_overview()["recent"][0]["score"])
        retry = fresh.start_mock("m90", repeat=True, seed=3)
        for cid in retry.items:
            retry.save_answer(["3"], cid)
        self.assertFalse(retry.submit()["related"])
        self.assertEqual(1, fresh.mock_state("m90")["first_score"])
        self.assertEqual(4, fresh.overview()["due"])
        self.assertEqual(1, fresh.hub_overview()["recent"][0]["score"])

    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, 'bank')
        shutil.copytree(FIXTURE, self.root)
        index_path = os.path.join(self.root, 'index.json')
        index = study.read_json(index_path)
        index['mocks'][0]['count'] = 4
        study.write_text(index_path, json.dumps(index, ensure_ascii=False))
        folder = Path(self.root) / 'mocks/m90'
        (folder / 'work').mkdir(parents=True)
        (folder / 'meta.json').write_text('{}', encoding="utf-8")
        self.mock_items = [
            {'id': 'm90-%02d' % n, 'kind': 'blank', 'lesson': 'i90', 'unit': '90a', 'step': '90a/1',
             'stem': '숫자를 쓰세요: ____', 'blanks': [{'answer': ['3'], 'mode': 'number'}],
             'explain': '정답은 3입니다.', 'ref': ['검증 기록']} for n in range(1, 5)
        ]
        (folder / 'work/items.json').write_text(json.dumps({'items': self.mock_items}, ensure_ascii=False), encoding="utf-8")

    def test_unsubmitted_questions_do_not_enter_practice(self):
        sess = self.session()
        sess.start_mock('m90', seed=1)
        self.assertFalse(any(cid.startswith('m90-') for cid in sess.cards))
        self.assertEqual(0, sess.overview()['due'])

    def test_first_wrong_results_enter_next_day_review_and_keep_note_links(self):
        sess = self.session()
        exam = sess.start_mock('m90', seed=1)
        exam.save_answer(['3'], 'm90-01')
        exam.save_answer(['4'], 'm90-02')
        exam.submit()
        self.assertEqual(0, sess.overview()['due'])
        self.assertEqual({'m90-02', 'm90-03', 'm90-04'}, {cid for cid in sess.cards if cid.startswith('m90-')})
        self.assertEqual('i90', sess.wrong_item('m90-02')['lesson'])
        self.assertEqual('90a/1', sess.wrong_item('m90-02')['step'])
        self.assertEqual(['4'], sess.wrong_item('m90-02')['mine'])
        log_before = self.log(sess)
        target = sess.note_target('m90-02')
        self.assertEqual(('i90', '90a/1'), (target['lesson'], target['step']))
        self.assertNotIn('ref', target)
        self.assertEqual(log_before, self.log(sess))
        card = sess.card_info('m90-02')
        card['after'] = 'missing'
        self.assertIsNone(sess.note_target(card['id']))
        card['after'] = 'i90'
        self.at = '2026-11-10T20:00:00'
        self.assertEqual(3, sess.overview()['due'])
        practice = sess.start_set('review', seed=7)
        self.assertEqual({'m90-02', 'm90-03', 'm90-04'}, {entry['card'] for entry in practice.queue})
        self.assertEqual('i90', practice.current()['lesson'])
        self.assertEqual(['3'], sess.explain('m90-02')['answer'])
        retry = sess.start_mock('m90', repeat=True, seed=2)
        for cid in retry.items:
            retry.save_answer(['3'], cid)
        retry.submit()
        fresh = self.session()
        self.assertEqual(3, fresh.overview()['due'])
        self.assertEqual({'m90-02', 'm90-03', 'm90-04'}, {cid for cid in fresh.cards if cid.startswith('m90-')})

    def test_replaced_record_drops_old_mock_review_cards(self):
        sess = self.session()
        sess.start_mock('m90').submit()
        sess.overview()
        self.assertEqual(4, len([cid for cid in sess.cards if cid.startswith('m90-')]))
        data = study.read_json(sess.record.path)
        data['log'] = []
        study.write_text(sess.record.path, json.dumps(data, ensure_ascii=False))
        self.assertEqual(0, sess.overview()['due'])
        self.assertFalse(any(cid.startswith('m90-') for cid in sess.cards))

    def test_wrong_notes_reject_changed_bank(self):
        sess = self.session()
        exam = sess.start_mock('m90', seed=1)
        exam.save_answer(['4'], 'm90-01')
        exam.submit()
        record_before = Path(sess.record.path).read_bytes()
        draft_before = Path(exam.path).read_bytes()
        self.mock_items[0]['stem'] = '새 숫자를 쓰세요: ____'
        self.mock_items[0]['blanks'][0]['answer'] = ['9']
        path = Path(self.root) / 'mocks/m90/work/items.json'
        path.write_text(json.dumps({'items': self.mock_items}, ensure_ascii=False), encoding="utf-8")

        restored = self.session()
        self.assertEqual(0, restored.overview()['due'])
        self.assertIn('문제 자료가 바뀌었습니다', restored.errors.get('m90', ''))
        self.assertFalse(any(cid.startswith('m90-') for cid in restored.cards))
        with self.assertRaises(AiError):
            restored.wrong_item('m90-01')
        self.assertEqual(0, restored.mock_state('m90')['first_score'])
        self.assertEqual(record_before, Path(sess.record.path).read_bytes())
        self.assertEqual(draft_before, Path(exam.path).read_bytes())

    def test_wrong_note_ignores_draft_from_another_version(self):
        sess = self.session()
        exam = sess.start_mock('m90', seed=1)
        exam.save_answer(['4'], 'm90-01')
        exam.submit()
        self.assertEqual(['4'], sess.wrong_item('m90-01')['mine'])
        record_before = Path(sess.record.path).read_bytes()
        draft = study.read_json(exam.path)
        for fingerprint in ('another-version', None):
            with self.subTest(fingerprint=fingerprint):
                draft['fingerprint'] = fingerprint
                study.write_text(exam.path, json.dumps(draft, ensure_ascii=False))
                before = Path(exam.path).read_bytes()
                note = sess.wrong_item('m90-01')
                self.assertIsNone(note['mine'])
                self.assertEqual(self.mock_items[0]['stem'], note['stem'])
                self.assertEqual(before, Path(exam.path).read_bytes())
        self.assertEqual(record_before, Path(sess.record.path).read_bytes())

    def recover_after_write_failure(self, target):
        sess = self.session()
        exam = sess.start_mock('m90', seed=1)
        exam.save_answer(['3'], 'm90-01')
        before = Path(exam.path).read_bytes()
        self.at = '2026-11-09T21:01:00'
        path = exam.path if target == 'draft' else sess.record.path
        original = study.write_text

        def fail(path_to_write, text):
            if path_to_write == path:
                raise OSError('temporary write failure')
            return original(path_to_write, text)

        with mock.patch('aiprep.mock.study.write_text', side_effect=fail):
            restored = self.session()
        restored.record.reload()
        self.assertEqual([], self.log(restored, 'mock_submit'))
        self.assertIn('m90', restored.errors)
        self.assertEqual(before, Path(exam.path).read_bytes())
        restored.expire_mocks()
        submitted = self.log(restored, 'mock_submit')
        self.assertEqual(1, len(submitted))
        self.assertEqual((True, 1, 3600), (submitted[0]['auto'], submitted[0]['score'], submitted[0]['secs']))
        self.assertNotIn('m90', restored.errors)
        self.assertFalse(restored.mock_state('m90')['active'])
        restored.expire_mocks()
        self.assertEqual(1, len(self.log(restored, 'mock_submit')))
        self.assertEqual(['3'], study.read_json(exam.path)['answers']['m90-01'])

    def test_expired_recovery_retries_draft_write(self):
        self.recover_after_write_failure('draft')

    def test_expired_recovery_retries_record_write(self):
        self.recover_after_write_failure('record')

    def test_expired_draft_is_submitted_when_the_session_is_loaded(self):
        self.session().start_mock('m90')
        self.at = '2026-11-09T21:01:00'
        restored = self.session()
        submitted = [row for row in restored.record.log if row['kind'] == 'mock_submit']
        self.assertEqual(1, len(submitted))
        self.assertTrue(submitted[0]['auto'])
        self.assertFalse(restored.mock_info('m90')['active'])

    def test_related_practice_card_is_due_next_day_without_a_fabricated_answer(self):
        self.mock_items[0]['tags'] = ['공유 주제']
        path = Path(self.root) / 'mocks/m90/work/items.json'
        path.write_text(json.dumps({'items': self.mock_items}, ensure_ascii=False), encoding="utf-8")
        sess = self.session()
        sess.cards['i90-b01']['tags'] = ['공유 주제']
        result = sess.start_mock('m90').submit()
        self.assertEqual(['i90-b01'], result['related'])
        self.assertEqual(0, sess.overview()['due'])
        self.assertEqual([], [row for row in sess.record.log if row['kind'] == 'answer'])
        self.at = '2026-11-10T20:00:00'
        self.assertEqual(5, sess.overview()['due'])
        practice = sess.start_set('review', seed=7)
        self.assertIn('i90-b01', [row['card'] for row in practice.queue])
        self.play(practice, lambda _: 'pass')
        self.assertNotIn('i90-b01', sess._state().related_due)

    def test_related_card_is_due_on_last_review_day(self):
        self.mock_items[0]['tags'] = ['공유 주제']
        path = Path(self.root) / 'mocks/m90/work/items.json'
        path.write_text(json.dumps({'items': self.mock_items}, ensure_ascii=False), encoding="utf-8")
        sess = self.session()
        last_day = sess.exam['last_review']
        self.at = (last_day - datetime.timedelta(days=1)).isoformat() + 'T20:00:00'
        sess.cards['i90-b01']['tags'] = ['공유 주제']
        result = sess.start_mock('m90', seed=1).submit()
        self.assertEqual(['i90-b01'], result['related'])
        self.assertEqual(0, sess.overview()['due'])
        self.assertEqual([], self.log(sess, 'answer'))

        self.at = last_day.isoformat() + 'T20:00:00'
        self.assertEqual(last_day, sess._state().related_due['i90-b01'])
        self.assertEqual(5, sess.overview()['due'])
        practice = sess.start_set('review', seed=7)
        self.assertIn('i90-b01', [row['card'] for row in practice.queue])
        self.play(practice, lambda _: 'pass')
        self.assertNotIn('i90-b01', sess._state().related_due)


def code_item(cid, lesson):
    """두 줄을 채우는 코드 작성 문항. 숨은 테스트 값은 예시와 겹치지 않음."""
    return {"id": cid, "kind": "code", "lesson": lesson, "unit": "90a", "step": "90a/1",
            "stem": "두 수를 더한 값을 돌려주는 함수를 완성하세요.",
            "code": {"starter": "def add(a, b):\n    ____\n    ____\n", "entry": "add",
                     "examples": [{"args": [1, 2], "expected": 3}, {"args": [10, 20], "expected": 30}],
                     "tests": [{"args": [40017, 2], "expected": 40019}, {"args": [-50013, 50013], "expected": 0}],
                     "limit_ms": 2000, "tol": None},
            "solution": ["total = a + b", "return total"], "explain": "두 값을 더해 돌려줍니다.", "ref": ["검증 기록"]}


RIGHT = ["total = a + b", "return total"]
WRONG = ["total = a - b", "return total"]


def env_grade(item, lines, workers=None):
    return {"result": mock_code.ENV, "passed": 0, "total": 2, "reason": mock_code.ENV_REASON, "cases": []}


def stuck_grade(item, lines, workers=None):
    return {"result": "stuck", "passed": 1, "total": 2, "reason": "숨은 테스트 2번: 돌려준 값이 다릅니다.", "cases": []}


class CodeExamTest(unittest.TestCase):
    setUp_base, write_items, exam = ExamTest.setUp, ExamTest.write_items, ExamTest.exam

    def setUp(self):
        self.setUp_base()
        self.items.append(code_item("m1-05", "i05"))
        self.write_items()
        self.session.mocks["m1"]["count"] = 5

    def test_question_shows_only_public_code_and_rejects_broken_lines(self):
        exam = self.exam(seed=3)
        position = exam.draft["order"].index("m1-05")
        question = exam.question(position)
        self.assertEqual(("code", "add"), (question["kind"], question["entry"]))
        self.assertEqual(self.items[-1]["code"]["starter"], question["starter"])
        self.assertEqual(self.items[-1]["code"]["examples"], question["examples"])
        text = json.dumps(question, ensure_ascii=False)
        for hidden in ("40017", "40019", "50013", "total = a + b", "tests", "solution"):
            self.assertNotIn(hidden, text)
        self.assertFalse(exam.answered("m1-05"))
        for broken, message in ((["return a + b"], "형식"), (["return a", 1], "형식"),
                                (["x = 1\nreturn x", ""], "한 줄"), (["  ____", ""], "____")):
            with self.subTest(broken=broken):
                with self.assertRaisesRegex(MockError, message):
                    exam.save_answer(broken, "m1-05")
        self.assertNotIn("m1-05", exam.draft["answers"])

    def test_fingerprint_follows_hidden_tests_but_not_the_explanation(self):
        before = self.exam(seed=1).fingerprint
        self.items[-1]["explain"] = "다른 해설입니다."
        self.write_items()
        self.assertEqual(before, load_items(self.session.root, self.session.mocks["m1"])[1])
        self.items[-1]["code"]["tests"][0]["expected"] = 40020
        self.write_items()
        self.assertNotEqual(before, load_items(self.session.root, self.session.mocks["m1"])[1])

    def test_broken_code_item_is_not_loaded(self):
        def drop_tests(item):
            item["code"]["tests"] = []

        def short_solution(item):
            item["solution"] = ["return a + b"]

        def no_examples(item):
            del item["code"]["examples"]

        def bad_entry(item):
            item["code"]["entry"] = "add numbers"

        def bad_limit(key, value):
            def breaker(item):
                item["code"][key] = value
            breaker.__name__ = "%s=%r" % (key, value)
            return breaker

        limits = [bad_limit("limit_ms", value) for value in (0, -1, 1.5, True)]
        limits += [bad_limit("tol", value) for value in (-0.1, "0.1")]
        for breaker in (drop_tests, short_solution, no_examples, bad_entry, *limits):
            with self.subTest(breaker=breaker.__name__):
                broken = copy.deepcopy(self.items)
                breaker(broken[-1])
                text = json.dumps({"items": broken}, ensure_ascii=False)
                (self.folder / "work/items.json").write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(MockError, "코드 작성 문항"):
                    load_items(self.session.root, self.session.mocks["m1"])

    def test_blank_rule_is_the_same_for_submit_progress_and_collection(self):
        repo = self.root / "repo"
        repo.mkdir()
        store = collection.Collection(str(self.root / "private"), str(repo))
        store.set_enabled(True)
        cases = [(["", ""], True), ([" ", "　"], True), (["\t", "  "], True),
                 (["# 아직 모름", ""], False), (["", "return a"], False)]
        for n, (value, blank) in enumerate(cases):
            with self.subTest(value=value):
                exam = self.exam(repeat=n > 0, seed=n)
                exam.save_answer(value, "m1-05")
                progress = {row["card"]: row["answered"] for row in exam.progress()}
                with mock.patch.object(mock_code, "grade", side_effect=stuck_grade) as grader:
                    result = exam.submit()["results"]["m1-05"]
                store.emit("mock_answer", {"card": "m1-05", "response": value, "result": result}, key="case-%d" % n)
                collected = store.snapshot()[-1]["data"]["answered"]
                self.assertEqual(blank, result == "blank")
                self.assertEqual(not blank, exam.answered("m1-05"))
                self.assertEqual(not blank, progress["m1-05"])
                self.assertEqual(not blank, collected)
                self.assertEqual(0 if blank else 1, grader.call_count)

    def test_code_is_graded_by_hidden_tests_and_pass_count_stays_in_the_draft(self):
        exam = self.exam(seed=2)
        exam.save_answer(["  total = a + b", "    return total"], "m1-05")  # 앞 공백은 시작 코드 들여쓰기로 바뀜
        self.clock.advance(12)
        result = exam.submit()
        self.assertEqual(("pass", 1, 5, 12), (result["results"]["m1-05"], result["score"], result["of"], result["secs"]))
        self.assertEqual({"m1-05": [2, 2]}, study.read_json(exam.path)["code_passed"])
        self.assertEqual(RIGHT, exam.explain("m1-05")["solution"])
        saved = json.dumps(self.session.record.load(), ensure_ascii=False)
        for text in ("total = a + b", "code_passed", "passed"):
            self.assertNotIn(text, saved)
        retry = self.exam(repeat=True, seed=3)
        retry.save_answer(WRONG, "m1-05")
        self.assertEqual("stuck", retry.submit()["results"]["m1-05"])
        self.assertEqual({"m1-05": [0, 2]}, study.read_json(retry.path)["code_passed"])

    def test_environment_failures_keep_the_attempt_open_until_the_third_try(self):
        exam = self.exam(seed=2)
        exam.save_answer(["3"], "m1-03")
        exam.save_answer(WRONG, "m1-05")
        with mock.patch.object(mock_code, "grade", side_effect=env_grade):
            for count in (1, 2):
                with self.assertRaisesRegex(MockError, "채점하지 못해"):
                    exam.submit()
                self.assertEqual(count, study.read_json(exam.path)["env_failures"])
                self.assertEqual(["mock_start"], [row["kind"] for row in self.session.record.log])
                self.assertIsNone(exam.result)
            result = exam.submit()
        self.assertEqual("ungraded", result["results"]["m1-05"])
        self.assertEqual(("pass", "blank"), (result["results"]["m1-03"], result["results"]["m1-01"]))
        self.assertEqual((1, 5), (result["score"], result["of"]))
        self.assertNotIn("m1-05", review.card_events(self.session.record.log))
        self.assertEqual({}, study.read_json(exam.path)["code_passed"])

    def test_answers_are_refused_while_code_is_graded_outside_the_lock(self):
        exam = self.exam(seed=2)
        exam.save_answer(RIGHT, "m1-05")
        started, release = threading.Event(), threading.Event()

        def slow_grade(item, lines, workers=None):
            started.set()
            release.wait(5)
            return {"result": "pass", "passed": 2, "total": 2, "reason": "", "cases": []}

        out = {}
        with mock.patch.object(mock_code, "grade", side_effect=slow_grade):
            worker = threading.Thread(target=lambda: out.setdefault("result", exam.submit()))
            worker.start()
            self.assertTrue(started.wait(5))
            self.assertTrue(exam.lock.acquire(timeout=1))
            exam.lock.release()
            self.assertEqual(exam.draft["order"][0], exam.question(0)["card"])
            with self.assertRaisesRegex(MockError, "채점하고 있습니다"):
                exam.save_answer(WRONG, "m1-05")
            with self.assertRaisesRegex(MockError, "채점하고 있습니다"):
                exam.submit()
            release.set()
            worker.join(5)
        self.assertEqual("pass", out["result"]["results"]["m1-05"])
        self.assertEqual(RIGHT, study.read_json(exam.path)["answers"]["m1-05"])
        self.assertEqual(1, len(mock_submits(self.session.record.log)))
        self.assertFalse(exam.submitting)

    def test_expired_code_exam_is_not_graded_while_the_lock_is_held(self):
        exam = self.exam(seed=2)
        exam.save_answer(WRONG, "m1-05")
        self.clock.advance(61)
        with mock.patch.object(mock_code, "grade", side_effect=stuck_grade) as grader:
            self.assertFalse(exam.save_answer(RIGHT, "m1-05"))
            self.assertFalse(exam.move(1))
            self.assertFalse(exam.toggle_flag())
            self.assertEqual(0, grader.call_count)
            self.assertEqual([], mock_submits(self.session.record.log))
            self.assertIsNone(exam.result)
            result = exam.submit()
        self.assertEqual(("stuck", True, 1), (result["results"]["m1-05"], result["auto"], grader.call_count))
        self.assertEqual(WRONG, study.read_json(exam.path)["answers"]["m1-05"])

    def test_reopening_or_reading_an_expired_code_exam_does_not_grade_it(self):
        """코드 작성 회차는 생성자와 question 이 마감 뒤에도 채점하지 않음. 빈칸·객관식만 있는 회차는
        test_expired_exam_auto_submits_on_reopen 처럼 예전대로 자동 제출함."""
        exam = self.exam(seed=2)
        exam.save_answer(WRONG, "m1-05")
        self.clock.advance(61)
        with mock.patch.object(mock_code, "grade", side_effect=stuck_grade) as grader:
            exam.question(0)
            reopened = self.exam()
            reopened.question()
            self.assertEqual((0, None, None), (grader.call_count, exam.result, reopened.result))
            self.assertEqual([], mock_submits(self.session.record.log))
            result = reopened.submit()
        self.assertEqual(("stuck", True, 1), (result["results"]["m1-05"], result["auto"], grader.call_count))

    def test_run_code_uses_the_item_limits_without_hidden_tests_or_records(self):
        exam = self.exam(seed=2)
        exam.save_answer(RIGHT, "m1-05")
        self.items[-1]["code"].update(limit_ms=1500, tol=0.25)
        exam.items["m1-05"]["code"].update(limit_ms=1500, tol=0.25)
        before = Path(self.session.record.path).read_bytes()
        draft = Path(exam.path).read_bytes()
        reply = {"result": "pass", "passed": 2, "total": 2, "reason": "", "cases": []}
        with mock.patch.object(mock_code, "try_code", return_value=reply) as runner:
            self.assertEqual(reply, exam.run_code(WRONG, "m1-05"))
        code = self.items[-1]["code"]
        runner.assert_called_once_with(code["starter"], "add", code["examples"], WRONG, 1500, 0.25)
        self.assertNotIn("40017", json.dumps([list(runner.call_args.args), runner.call_args.kwargs]))
        self.assertEqual((before, draft), (Path(self.session.record.path).read_bytes(), Path(exam.path).read_bytes()))
        with self.assertRaisesRegex(MockError, "코드 작성 문항에서만"):
            exam.run_code(["3"], "m1-03")

    def test_explain_gives_the_local_pass_count_only_after_submit(self):
        exam = self.exam(seed=2)
        exam.save_answer(WRONG, "m1-05")
        with mock.patch.object(mock_code, "grade", side_effect=stuck_grade):
            exam.submit()
        self.assertEqual([1, 2], exam.explain("m1-05")["passed"])
        self.assertNotIn("passed", exam.explain("m1-03"))
        self.assertNotIn("passed", json.dumps(self.session.record.load()))

    def test_only_code_revision_follows_the_runner_files(self):
        exam = self.exam(seed=2)
        code_before, blank_before = exam.collection_item("m1-05"), exam.collection_item("m1-03")
        self.assertEqual(mock_code.runtime_revision(), code_before["content"]["code_runtime_revision"])
        self.assertNotIn("code_runtime_revision", blank_before["content"])
        content = json.dumps(code_before["content"], ensure_ascii=False)
        for hidden in ("40017", "total = a + b", "solution", "tests"):
            self.assertNotIn(hidden, content)
        with mock.patch.object(mock_code, "runtime_revision", return_value="changed"):
            self.assertNotEqual(code_before["revision"], exam.collection_item("m1-05")["revision"])
            self.assertEqual(blank_before["revision"], exam.collection_item("m1-03")["revision"])
        copy_root = self.root / "copy"
        for name in mock_code.RUNTIME_FILES:
            (copy_root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(os.path.join(study.ROOT, name), copy_root / name)
        with mock.patch.object(mock_code, "__file__", str(copy_root / "aiprep/mock_code.py")):
            first = mock_code.runtime_revision.__wrapped__()
            with open(copy_root / "journey/values.py", "a", encoding="utf-8") as stream:
                stream.write("\n")
            self.assertNotEqual(first, mock_code.runtime_revision.__wrapped__())


def mock_submits(log):
    return [row for row in log if row["kind"] == "mock_submit"]


class BeforeSecondLock:
    """submit 이 채점 뒤 잠금을 다시 잡기 직전에 hook 을 한 번 부름. 엔진에서 acquire 를 직접 부르는 곳은 submit 뿐임."""

    def __init__(self, inner, hook):
        self.inner, self.hook = inner, hook

    def __enter__(self):
        return self.inner.__enter__()

    def __exit__(self, *exc):
        return self.inner.__exit__(*exc)

    def acquire(self, *args, **kwargs):
        hook, self.hook = self.hook, None
        if hook:
            hook()
        return self.inner.acquire(*args, **kwargs)

    def release(self):
        return self.inner.release()


def in_thread(target):
    worker = threading.Thread(target=target)
    worker.start()
    worker.join(5)


class CodeServiceTest(Base):
    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, self.root)
        index_path = os.path.join(self.root, "index.json")
        index = study.read_json(index_path)
        index["mocks"][0]["count"] = 5
        study.write_text(index_path, json.dumps(index, ensure_ascii=False))
        folder = Path(self.root) / "mocks/m90"
        (folder / "work").mkdir(parents=True)
        (folder / "meta.json").write_text("{}", encoding="utf-8")
        items = [{"id": "m90-%02d" % n, "kind": "blank", "lesson": "i90", "unit": "90a", "step": "90a/1",
                  "stem": "숫자를 쓰세요: ____", "blanks": [{"answer": ["3"], "mode": "number"}]} for n in range(1, 5)]
        items.append(code_item("m90-05", "i90"))
        (folder / "work/items.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")

    def test_format_counts_skip_items_without_format(self):
        """mock_info()와 summary()는 format별 수를 세고, format이 없는 문항(m1~m3 꼴)은 칸을 만들지 않음. 화면은 아직 이 값을 쓰지 않음."""
        path = Path(self.root) / "mocks/m90/work/items.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for item, form in zip(data["items"], ("predict", "predict", None, None, "code")):
            if form:
                item["format"] = form
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        sess = self.session()
        self.assertEqual({"predict": 2, "code": 1}, sess.mock_info("m90")["formats"])
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(["3"], "m90-01")
        exam.save_answer(["3"], "m90-03")
        exam.save_answer(WRONG, "m90-05")
        exam.submit()
        self.assertEqual({"predict": [1, 2], "code": [0, 1]}, exam.summary()["formats"])

    def test_lesson_counts_cover_every_item(self):
        """시작 전 차시 표가 쓰는 mock_info()['lessons'] 는 문항에서 센 차시별 수이고 합이 문항 수와 같음.
        blueprint 가 있는 실제 회차(m4·m11)는 blueprint 와 같음. 예전 회차 m1·m4 의 legacy 는 이 검사 안에서만 뺌."""
        self.assertEqual({"i90": 5}, self.session().mock_info("m90")["lessons"])
        source = str(Path(__file__).resolve().parents[1] / "ai")
        real = bank.read_index

        def shown(path=None):
            index = real(path)
            for spec in index["mocks"]:
                spec.pop("legacy", None)
            return index

        with mock.patch.object(bank, "read_index", shown):
            sess = service.AiSession("synthetic", home=os.path.join(self.tmp, "real-home"), root=source, course="intro")
            for mid in ("m1", "m4", "m11"):
                info = sess.mock_info(mid)
                self.assertEqual(info["count"], sum(info["lessons"].values()), mid)
                if "blueprint" in info:
                    self.assertEqual(info["blueprint"], info["lessons"], mid)

    def test_wrong_code_answer_is_a_read_only_wrong_note(self):
        sess = self.session()
        self.assertEqual((4, 0, 1), tuple(sess.mock_info("m90")[k] for k in ("blanks", "choices", "codes")))
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(["3"], "m90-01")
        exam.save_answer(["4"], "m90-02")
        exam.save_answer(WRONG, "m90-05")
        self.assertEqual("stuck", exam.submit()["results"]["m90-05"])
        labels = {item["key"]: item["label"] for group in sess.wrong_notes() for item in group["items"]}
        self.assertNotIn("m90-05", sess.cards)
        self.assertEqual("code", sess.card_info("m90-05")["kind"])
        self.assertTrue(labels["m90-05"].startswith("코드 작성 · "))
        note = sess.wrong_item("m90-05")
        self.assertEqual(("code", [], WRONG), (note["kind"], note["options"], note["mine"]))
        self.assertIn("def add(a, b):", note["stem"])
        self.assertEqual(RIGHT, sess.explain("m90-05")["answer"])
        self.at = "2026-11-10T20:00:00"
        self.assertEqual(3, sess.overview()["due"])
        self.assertNotIn("m90-05", [row["card"] for row in sess.start_set("review", seed=7).queue])
        self.assertNotIn("m90-05", [row["card"] for row in sess.start_set("note", card="m90-02", seed=7).queue])
        with self.assertRaisesRegex(AiError, "문항을 찾을 수 없습니다"):
            sess.start_set("note", card="m90-05")

    def test_expired_code_exam_waits_for_the_worker_and_ungraded_is_left_out(self):
        exam = self.session().start_mock("m90", seed=1)
        exam.save_answer(WRONG, "m90-05")
        self.at = "2026-11-09T21:01:00"
        with mock.patch.object(mock_code, "grade", side_effect=env_grade) as grader:
            restored = self.session()
            self.assertEqual((0, {"m90"}), (grader.call_count, restored.expired_code_mocks))
            self.assertEqual([], self.log(restored, "mock_submit"))
            with mock.patch.object(restored.collection, "mark_graded") as marked:
                for count in (1, 2):
                    restored.expire_mocks()
                    self.assertIn("채점하지 못해", restored.errors["m90"])
                    self.assertEqual([], self.log(restored, "mock_submit"))
                marked.assert_not_called()
                restored.expire_mocks()
            marked.assert_called_once()  # ungraded 는 답한 것이라 오늘 공부한 계정에 듦
        submitted = self.log(restored, "mock_submit")
        self.assertEqual(1, len(submitted))
        self.assertEqual(("ungraded", True, 5), (submitted[0]["results"]["m90-05"], submitted[0]["auto"], submitted[0]["of"]))
        self.assertEqual(set(), restored.expired_code_mocks)
        self.assertNotIn("m90", restored.errors)
        self.assertNotIn("m90-05", submitted[0]["related_by_question"])
        keys = {item["key"] for group in restored.wrong_notes() for item in group["items"]}
        self.assertEqual({"m90-01", "m90-02", "m90-03", "m90-04"}, keys)
        self.assertNotIn("m90-05", restored.mock_code_cards)

    def test_answer_saved_after_grading_is_refused_and_the_graded_answer_is_collected(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(RIGHT, "m90-05")
        out = {}

        def save_wrong():
            try:
                out["saved"] = exam.save_answer(WRONG, "m90-05")
            except MockError as error:
                out["saved"] = str(error)

        exam.lock = BeforeSecondLock(exam.lock, lambda: in_thread(save_wrong))
        self.assertEqual("pass", exam.submit()["results"]["m90-05"])
        self.assertIn("채점하고 있습니다", out["saved"])
        self.assertEqual(RIGHT, study.read_json(exam.path)["answers"]["m90-05"])
        rows = [row["data"] for row in sess.collection.snapshot(include_answers=True)
                if row["kind"] == "mock_answer" and row["data"]["card"] == "m90-05"]
        self.assertEqual([(RIGHT, "pass")], [(row["response"], row["result"]) for row in rows])
        keys = {item["key"] for group in sess.wrong_notes() for item in group["items"]}
        self.assertEqual({"m90-01", "m90-02", "m90-03", "m90-04"}, keys)
        self.assertNotIn("m90-05", sess.mock_code_cards)

    def test_expired_code_exam_opened_by_start_mock_waits_for_expire_mocks(self):
        sess = self.session()
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(WRONG, "m90-05")
        self.at = "2026-11-09T21:01:00"
        with mock.patch.object(mock_code, "grade", side_effect=stuck_grade) as grader:
            fresh = self.session()
            fresh._mock_exams.clear()
            reopened = fresh.start_mock("m90")
            self.assertEqual((0, None), (grader.call_count, reopened.result))
            fresh.expire_mocks(code=False)
            self.assertEqual((0, {"m90"}), (grader.call_count, fresh.expired_code_mocks))
            fresh.expire_mocks()
        submitted = self.log(fresh, "mock_submit")
        self.assertEqual((1, 1, True), (grader.call_count, len(submitted), submitted[0]["auto"]))

    def test_ticker_skips_an_exam_while_its_code_is_graded(self):
        sess = self.session()
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(RIGHT, "m90-05")
        self.at = "2026-11-09T21:01:00"
        started, release = threading.Event(), threading.Event()

        def slow_grade(item, lines, workers=None):
            started.set()
            release.wait(5)
            return {"result": "pass", "passed": 2, "total": 2, "reason": "", "cases": []}

        with mock.patch.object(mock_code, "grade", side_effect=slow_grade) as grader:
            worker = threading.Thread(target=sess.expire_mocks)
            worker.start()
            self.assertTrue(started.wait(5))
            sess.expire_mocks()
            self.assertNotIn("m90", sess.errors)
            release.set()
            worker.join(5)
        self.assertEqual(1, grader.call_count)
        self.assertEqual(1, len(self.log(sess, "mock_submit")))

    def test_untouched_code_answer_is_not_counted_and_code_text_stays_local(self):
        sess = self.session()
        sess.collection.set_enabled(True)
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(["", ""], "m90-05")
        with mock.patch.object(sess.collection, "mark_graded") as marked:
            self.assertEqual("blank", exam.submit()["results"]["m90-05"])
        marked.assert_not_called()
        answers = [row["data"] for row in sess.collection.snapshot() if row["kind"] == "mock_answer"]
        self.assertEqual([False], [row["answered"] for row in answers if row["card"] == "m90-05"])

        retry = sess.start_mock("m90", repeat=True, seed=2)
        retry.save_answer(RIGHT, "m90-05")
        with mock.patch.object(sess.collection, "mark_graded") as marked:
            self.assertEqual("pass", retry.submit()["results"]["m90-05"])
        marked.assert_called_once()
        inputs = [row["data"] for row in sess.collection.snapshot() if row["kind"] == "ai_input"]
        self.assertEqual([(1, "m90-05")], [(row["input_schema"], row["card"]) for row in inputs])
        shared = json.dumps(sess.collection.snapshot(), ensure_ascii=False)
        record_text = Path(sess.record.path).read_text(encoding="utf-8")
        for text in ("total = a + b", "passed", "40017", "solution"):
            self.assertNotIn(text, shared)
            self.assertNotIn(text, record_text)
        items = [row["item"] for row in sess.collection.snapshot()
                 if row["kind"] == "mock_answer" and row["data"]["card"] == "m90-05"]
        self.assertEqual({"def add(a, b):\n    ____\n    ____\n"}, {item["starter"] for item in items})
        self.assertEqual({2}, {len(item["examples"]) for item in items})
        self.assertNotIn("tests", items[0])


if __name__ == '__main__':
    unittest.main()
