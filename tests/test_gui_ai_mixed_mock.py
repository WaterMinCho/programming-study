# -*- coding: utf-8 -*-
"""두 과정 탭에서 혼합 회차의 안내·초안·결과 표시를 확인함."""
from unittest import mock

from aiprep import bank
from gui import theme
from tests.test_ai_mixed_mock import make_bank, parsed_index, READ_INDEX
from tests.test_gui_ai import AiTest, visible_text


class MixedMockPageTest(AiTest):
    def setUp(self):
        super().setUp()
        self.root = str(make_bank(self.tmp+'/mixed_bank'))
        for name,value in [('AI_DIR',self.root),('read_index',parsed_index)]:
            patch=mock.patch.object(bank,name,value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_unconnected_metadata_hides_start_and_shows_pending_text(self):
        with mock.patch.object(bank,'read_index',READ_INDEX):
            win=self.boot()
            win.go_ai()
            for course in ('intro','app'):
                win.switch_ai_course(course)
                self.idle()
                self.assertNotIn('m4',win.ai.mocks)
                self.assertTrue(win.ai_home.mock_pending.isVisible())
                self.assertIn('메타데이터',win.ai_home.mock_pending.text())
                self.assertFalse(win.open_ai_mock('m4'))

    def test_both_tabs_restore_the_same_timed_answer_and_attempt(self):
        win=self.boot((800,700))
        self.assertTrue(win.open_ai_mock('m4'))
        page=win.ai_mock
        self.assertIn('개론 16 · 응용 16 · 연습 기본 120분',page.heading.text())
        self.assertIn('공식 평가 시간을 뜻하지 않습니다',visible_text(page))
        page.begin()
        pos=page.exam.draft['order'].index('m4-17')
        page.go(pos)
        self.idle()
        self.assertIn('응용 90차시',visible_text(page))
        page.inputs[0].setText('4');page.changed();self.assertTrue(page.persist())
        page.flag()
        original=page.exam
        win.go_ai();win.switch_ai_course('app')
        self.assertTrue(win.open_ai_mock('m4'))
        self.assertIs(original,page.exam)
        self.assertEqual('← AI 응용',page.top.back.text())
        self.assertEqual(1,page.exam.attempt)
        self.assertEqual('4',page.inputs[0].text())
        self.assertTrue(page.item['flagged'])
        self.assertGreater(page.exam.remaining(),7100)
        self.assertFalse(any(cid.startswith('i90-') for cid in win.ai.cards))

    def test_result_course_names_and_narrow_controls_keep_the_timer(self):
        self.addCleanup(theme.set_text,'normal')
        win=self.boot((800,700));self.assertTrue(win.open_ai_mock('m4'))
        page=win.ai_mock;page.begin();deadline=page.exam.draft['deadline']
        win.set_text('larger')
        for mode in ('light','dark'):
            theme.set_mode(mode);win.restyle();self.idle()
            self.assertEqual(deadline,page.exam.draft['deadline'])
            self.assertTrue(win.rect().contains(page.next_btn.mapTo(win,page.next_btn.rect().center())))
            self.assertGreaterEqual(page.next_btn.width(),page.next_btn.sizeHint().width())
        page.submit();self.idle()
        self.assertIn('0 / 32문항 맞음',page.heading.text())
        text=visible_text(page.lesson_results)
        self.assertIn('응용 90차시',text)
        self.assertIn('90차시',text)
        self.assertEqual(2,len(page.lesson_results.rows))
