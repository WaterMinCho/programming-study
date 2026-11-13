# -*- coding: utf-8 -*-
"""모의고사 시간·초안 복구·제출 판정과 기록을 임시 자료로 확인함."""
import datetime
import json
import os
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from aiprep import grade, review
from aiprep.mock import MockError, MockExam
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


if __name__ == '__main__':
    unittest.main()
