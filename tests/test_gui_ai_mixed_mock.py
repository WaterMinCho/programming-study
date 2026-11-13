# -*- coding: utf-8 -*-
"""두 과정 탭에서 혼합 회차의 안내·초안·결과 표시를 확인함."""
import unittest
from unittest import mock

from aiprep import bank
from tests import guikit, test_gui_ai
from PyQt6.QtGui import QFont
from gui import theme
from tests.test_ai_mixed_mock import make_bank, without_mixed_metadata
from tests.test_gui_ai import visible_text


class MixedMockPageTest(unittest.TestCase):
    real_bank = False
    pc = False
    tearDown = test_gui_ai.AiTest.tearDown
    boot = test_gui_ai.AiTest.boot
    idle = test_gui_ai.AiTest.idle

    def setUp(self):
        before=(dict(theme.state),QFont(guikit.APP.font()),guikit.APP.palette(),guikit.APP.styleSheet())
        test_gui_ai.AiTest.setUp(self)
        self.addCleanup(self.restore_theme,before)
        self.root = str(make_bank(self.tmp+'/mixed_bank'))
        for name,value in [('AI_DIR',self.root)]:
            patch=mock.patch.object(bank,name,value)
            patch.start()
            self.addCleanup(patch.stop)

    def restore_theme(self,before):
        state,font,palette,stylesheet=before
        theme.set_text(state['text'])
        theme.set_mode(state['mode'],force=True)
        guikit.APP.setFont(font)
        guikit.APP.setPalette(palette)
        guikit.APP.setStyleSheet(stylesheet)

    def test_unconnected_metadata_hides_start_and_shows_pending_text(self):
        with mock.patch.object(bank,'read_index',without_mixed_metadata):
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
        win=self.boot((760,480))
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
        for cid in page.exam.draft['order']:
            page.go(page.exam.draft['order'].index(cid))
            page.inputs[0].setText('4');page.changed();self.assertTrue(page.persist())
        self.assertEqual(32,sum(page.exam.answered(cid) for cid in page.exam.draft['order']))
        page.submit();self.idle()
        self.assertEqual(32,page.exam.summary()['of'])
        self.capture_widget=win

    def test_result_course_names_and_narrow_controls_keep_the_timer(self):
        self.addCleanup(theme.set_text,'normal')
        win=self.boot((760,480));self.assertTrue(win.open_ai_mock('m4'))
        page=win.ai_mock;page.begin();deadline=page.exam.draft['deadline']
        win.set_text('larger')
        for mode in ('light','dark'):
            theme.set_mode(mode);win.restyle();self.idle()
            self.assertEqual((760,480),(win.width(),win.height()))
            self.assertEqual(deadline,page.exam.draft['deadline'])
            self.assertTrue(win.rect().contains(page.next_btn.mapTo(win,page.next_btn.rect().center())))
            self.assertGreaterEqual(page.next_btn.width(),page.next_btn.sizeHint().width())
        page.submit();self.idle()
        self.assertIn('0 / 32문항 맞음',page.heading.text())
        text=visible_text(page.lesson_results)
        self.assertIn('응용 90차시',text)
        self.assertIn('90차시',text)
        self.assertEqual(2,len(page.lesson_results.rows))
        self.capture_widget=win


class PublishedMixedMockPageTest(unittest.TestCase):
    real_bank = True
    pc = False
    setUp = test_gui_ai.AiTest.setUp
    tearDown = test_gui_ai.AiTest.tearDown
    boot = test_gui_ai.AiTest.boot
    idle = test_gui_ai.AiTest.idle

    def test_actual_32_items_restore_across_tabs_at_largest_text_in_both_themes(self):
        self.addCleanup(theme.set_text,'normal')
        win=self.boot((760,480))
        self.assertTrue(win.open_ai_mock('m4'))
        page=win.ai_mock
        page.begin()
        exam=page.exam
        self.assertEqual(32,len(exam.items))
        deadline=exam.draft['deadline']
        fingerprint=exam.fingerprint
        win.set_text('larger')
        for mode in ('light','dark'):
            theme.set_mode(mode);win.restyle();self.idle()
            for cid,label in (('m4-10','intro-code'),('m4-20','app-choice')):
                page.go(exam.draft['order'].index(cid));self.idle()
                if page.inputs:
                    for field in page.inputs:
                        field.setText('검사답안')
                    target=page.inputs[0]
                else:
                    page.choices.rows[0].box.setChecked(True)
                    target=page.choices.rows[0].box
                page.changed();self.assertTrue(page.persist())
                page.scroll.ensureWidgetVisible(target,0,24);self.idle()
                self.assertEqual((760,480),(win.width(),win.height()))
                self.assertEqual('larger',theme.state['text'])
                self.assertEqual(deadline,exam.draft['deadline'])
                self.assertTrue(win.rect().contains(page.next_btn.mapTo(win,page.next_btn.rect().center())))
                self.assertGreaterEqual(page.next_btn.width(),page.next_btn.sizeHint().width())
                self.capture_widget=win
                capture=getattr(self,'capture_point',None)
                if capture:
                    capture(mode+'-'+label,win,{'card':cid,'course':exam.items[cid]['course'],
                            'theme':mode,'text':'larger','deadline':deadline,'fingerprint':fingerprint})
        current=page.item['card']
        mine=list(page.values())
        page.flag()
        win.go_ai();win.switch_ai_course('app')
        self.assertTrue(win.open_ai_mock('m4'));self.idle()
        self.assertIs(exam,page.exam)
        self.assertEqual(current,page.item['card'])
        self.assertEqual(mine,page.values())
        self.assertTrue(page.item['flagged'])
        self.assertEqual(fingerprint,page.exam.fingerprint)
        self.assertEqual(deadline,page.exam.draft['deadline'])
        self.assertEqual(1,page.exam.attempt)
        for pos,cid in enumerate(exam.draft['order']):
            page.go(pos)
            if page.inputs:
                for field in page.inputs:
                    field.setText('검사답안')
            else:
                page.choices.rows[0].box.setChecked(True)
            page.changed();self.assertTrue(page.persist())
        self.assertEqual(32,sum(exam.answered(cid) for cid in exam.items))
        page.submit();self.idle()
        self.assertEqual(32,exam.summary()['of'])
        self.assertEqual(32,len(exam.result['results']))
        for mode in ('light','dark'):
            theme.set_mode(mode);win.restyle();self.idle()
            page.scroll.verticalScrollBar().setValue(0);self.idle()
            self.assertEqual((760,480),(win.width(),win.height()))
            capture=getattr(self,'capture_point',None)
            if capture:
                capture(mode+'-result',win,{'theme':mode,'text':'larger','submitted':32,
                        'same_exam_after_tab_switch':True,'fingerprint':fingerprint})
        self.capture_widget=win
