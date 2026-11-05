# -*- coding: utf-8 -*-
"""모의고사에서 저장·이동·시간 종료와 제출 전후 해설 표시를 임시 은행으로 확인함."""
import json
import os
import shutil
from pathlib import Path
from unittest import mock

from tests.test_gui_ai import AI_FIXTURE, AiTest, visible_text
from PyQt6.QtGui import QInputMethodEvent
from PyQt6.QtWidgets import QApplication
from aiprep import bank
from aiprep.mock import MockError
from gui import kit, theme
from tests import guikit
import study


class MockPageTest(AiTest):
    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, 'mock_bank')
        shutil.copytree(AI_FIXTURE, self.root)
        index_path = os.path.join(self.root, 'index.json')
        index = study.read_json(index_path)
        index['mocks'][0]['count'] = 4
        study.write_text(index_path, json.dumps(index, ensure_ascii=False))
        folder = Path(self.root) / 'mocks/m90'
        (folder / 'work').mkdir(parents=True)
        (folder / 'meta.json').write_text('{}')
        self.items = [
            {'id': 'm90-01', 'kind': 'blank', 'lesson': 'i90', 'unit': '90a', 'step': '90a/1',
             'stem': '숫자를 쓰세요: ____', 'blanks': [{'answer': ['3'], 'mode': 'number'}],
             'explain': '해설 검증문장입니다.'},
            {'id': 'm90-02', 'kind': 'choice', 'lesson': 'i90', 'unit': '90a', 'step': '90a/1',
             'stem': '옳은 것을 고르세요.', 'options': [{'text': '보기 %d입니다.' % n, 'ok': n == 2} for n in range(4)],
             'explain': '고르기 해설 검증문장입니다.'},
            {'id': 'm90-03', 'kind': 'blank', 'lesson': 'i90', 'unit': '90a', 'step': '90a/1',
             'stem': '```python\nvalue = ____\n```', 'blanks': [{'answer': ['3'], 'mode': 'code'}],
             'explain': '코드 해설 검증문장입니다.'},
            {'id': 'm90-04', 'kind': 'blank', 'lesson': 'i90', 'unit': '90a', 'step': '90a/1',
             'stem': '두 값을 쓰세요: ____와 ____', 'blanks': [{'answer': ['3'], 'mode': 'number'}] * 2,
             'explain': '두 값의 해설 검증문장입니다.'},
        ]
        (folder / 'work/items.json').write_text(json.dumps({'items': self.items}, ensure_ascii=False))
        patcher = mock.patch.object(bank, 'AI_DIR', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def open_mock(self, size=(1024, 700), start=True):
        win = self.boot(size)
        self.assertTrue(win.open_ai_mock('m90'))
        if start:
            win.ai_mock.begin()
        self.idle()
        return win.ai_mock

    def composing_answer(self):
        """첫 글자의 조합과 확정 이벤트를 나눠 보냄."""
        page = self.open_mock()
        pos = page.exam.draft['order'].index('m90-01')
        page.go(pos)
        field = page.inputs[0]
        field.setFocus()
        QApplication.sendEvent(field, QInputMethodEvent('가', []))
        self.assertEqual('', field.text())
        self.assertFalse(page.dirty)
        pending = ['가']

        def commit():
            if pending:
                event = QInputMethodEvent()
                event.setCommitString(pending.pop())
                QApplication.sendEvent(field, event)

        return page, pos, commit

    def test_first_hangul_is_saved_on_navigation(self):
        page, pos, commit = self.composing_answer()
        with mock.patch('gui.ai_mock.commit_input', side_effect=commit):
            guikit.click(page.nav[(pos + 1) % len(page.nav)])
        self.assertNotEqual('m90-01', page.item['card'])
        self.assertEqual(['가'], study.read_json(page.exam.path)['answers'].get('m90-01'))

    def test_first_hangul_is_saved_on_close(self):
        page, _, commit = self.composing_answer()
        with mock.patch('gui.ai_mock.commit_input', side_effect=commit):
            self.assertTrue(self.win.close())
        self.assertEqual(['가'], study.read_json(page.exam.path)['answers'].get('m90-01'))

    def test_composing_save_failure_blocks_leaving(self):
        page, pos, commit = self.composing_answer()
        with mock.patch('gui.ai_mock.commit_input', side_effect=commit), \
                mock.patch.object(page.exam, '_write_draft', side_effect=MockError('save failed')):
            page.go((pos + 1) % len(page.nav))
            self.win.go_ai()
            self.assertFalse(self.win.close())
        self.assertIs(self.win.pages.currentWidget(), page)
        self.assertEqual('m90-01', page.item['card'])
        self.assertEqual('가', page.inputs[0].text())
        self.assertTrue(page.dirty)
        self.assertTrue(page.persist())
        self.assertEqual(['가'], study.read_json(page.exam.path)['answers']['m90-01'])

    def test_answer_is_saved_and_restored_without_showing_feedback(self):
        page = self.open_mock()
        pos = page.exam.draft['order'].index('m90-01')
        page.go(pos)
        page.inputs[0].setText('3')
        page.changed()
        self.assertNotIn('해설 검증문장', visible_text(page))
        page.go((pos + 1) % 4)
        self.assertTrue(self.win.open_ai_mock('m90'))
        page.begin()
        page.go(pos)
        self.assertEqual('3', page.inputs[0].text())
        self.assertEqual(['mock_start'], [row['kind'] for row in self.win.ai.record.log])
        page.submit()
        self.assertIsNotNone(page.exam.result)
        self.assertIn('해설 검증문장', visible_text(page))
        self.assertTrue(page.inputs[0].isReadOnly())

    def test_choice_and_code_answers_survive_question_navigation(self):
        page = self.open_mock()
        page.go(page.exam.draft['order'].index('m90-02'))
        row = next(n for n, option in enumerate(page.item['options']) if option['no'] == 2)
        page.choices.rows[row].box.setChecked(True)
        page.go(page.exam.draft['order'].index('m90-03'))
        page.inputs[0].setText('3')
        page.changed()
        page.flag()
        page.go(page.exam.draft['order'].index('m90-02'))
        self.assertEqual([2], page.values())
        page.submit()
        self.assertEqual(2, page.exam.result['score'])

    def test_timeout_submits_even_after_returning_home(self):
        page = self.open_mock()
        self.win.go_ai()
        self.clock = '2026-11-04T21:01:00'
        page.tick()
        self.assertTrue(page.exam.result['auto'])
        self.assertIs(self.win.pages.currentWidget(), self.win.ai_home)
        self.assertTrue(self.win.open_ai_mock('m90'))
        page.begin()
        self.assertIn('0 / 4문항 맞음', page.heading.text())

    def test_preview_does_not_start_the_clock_or_write_a_record(self):
        page = self.open_mock(start=False)
        self.assertIsNone(page.exam)
        self.assertEqual([], self.win.ai.record.log)
        self.assertEqual([page.start_btn], kit.visible_primary_buttons(page))
        guikit.click(page.start_btn)
        self.assertIsNotNone(page.exam)
        self.assertEqual(['mock_start'], [row['kind'] for row in self.win.ai.record.log])

    def test_narrow_page_keeps_primary_action_inside(self):
        self.addCleanup(theme.set_text, 'normal')
        page = self.open_mock((800, 700))
        self.win.set_text('larger')
        self.idle()
        self.assertEqual(800, self.win.width())
        primary = page.submit_btn if page.item['at'] == page.item['total'] else page.next_btn
        self.assertEqual([primary], kit.visible_primary_buttons(page))
        self.assertLessEqual(page.submit_btn.geometry().right(), page.bar.width())
        self.assertGreater(page.card.width(), 0)
