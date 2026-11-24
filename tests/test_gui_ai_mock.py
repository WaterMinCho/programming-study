# -*- coding: utf-8 -*-
"""모의고사에서 저장·이동·시간 종료와 제출 전후 해설 표시를 임시 은행으로 확인함."""
import json
import os
import shutil
from pathlib import Path
from unittest import mock

from tests.test_gui_ai import AI_FIXTURE, AiTest, visible_text
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QImage, QInputMethodEvent, QPainter
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton
from aiprep import bank
from aiprep.mock import MockError
from gui import kit, theme
from gui.ai_code_help import CodeReferenceDialog
from tests import guikit
import study

NATIVE = os.name == 'nt' and guikit.APP.platformName() == 'windows'


def place(win, size):
    """창 크기를 size 로 바꿈. Windows 실제 창에서 폭이 760 보다 넓은 창은 작업 영역 안으로 줄이고 왼쪽 위로 옮김.
    배율 1.5 에서 1280x800 창은 1920x1080 화면을 넘어 tools/check_release.py 의 운영체제 캡처가 창 전체를 담지 못함."""
    if NATIVE and size[0] > 760:
        area = win.screen().availableGeometry()
        size = min(size[0], area.width() - 32), min(size[1], area.height() - 64)
        win.move(area.topLeft() + QPoint(16, 32))
    win.resize(*size)


class MockPageTest(AiTest):
    def test_submitting_an_exam_requests_automatic_file_submission(self):
        page = self.open_mock()
        with mock.patch.object(self.win.auto_submission, "request") as checkpoint:
            page.submit()
            checkpoint.assert_called_once()
        self.assertIsNotNone(page.exam.result)

    def test_missing_draft_recovery_opens_without_resetting_the_clock_or_records(self):
        self.addCleanup(theme.set_text, 'normal')
        page = self.open_mock((760, 480))
        self.win.set_text('larger')
        deadline = page.exam.draft["deadline"]
        before = Path(self.win.ai.record.path).read_bytes()
        Path(page.exam.path).unlink()
        self.win.open_session()
        self.assertTrue(self.win.open_ai_mock("m90"))
        self.assertTrue(page.exam.recovered_draft)
        self.assertTrue(page.notice.isVisible())
        self.assertIn("원래 시작 시각", page.notice.text.text())
        self.assertEqual(deadline, page.exam.draft["deadline"])
        self.assertEqual(before, Path(self.win.ai.record.path).read_bytes())
        for mode in ('light', 'dark'):
            theme.set_mode(mode)
            self.win.restyle()
            self.idle()
            self.assertLessEqual(self.win.width(), 760)
            self.assertLessEqual(self.win.height(), 480)
            self.assertTrue(page.notice.isVisible())
            self.assertTrue(self.win.rect().contains(page.next_btn.mapTo(self.win, page.next_btn.rect().center())))

    def test_theme_and_text_changes_keep_live_answers_and_recolor_the_stem(self):
        from gui.docview import TextPiece

        page = self.open_mock((760, 480))
        page.go(page.exam.draft["order"].index("m90-01"))
        field = page.inputs[0]
        field.setText("3")
        page.changed()
        self.assertTrue(page.persist())
        field.selectAll()
        deadline = page.exam.draft["deadline"]
        before = Path(self.win.ai.record.path).read_bytes()
        self.addCleanup(theme.set_text, "normal")
        for mode, size in (("light", "normal"), ("dark", "larger"), ("light", "normal")):
            theme.set_mode(mode)
            self.win.set_text(size)
            self.idle()
            piece = next(p for p in page.card.findChildren(TextPiece) if "숫자를 쓰세요" in p.toPlainText())
            shot = piece.viewport().grab()
            image = QImage(shot.size(), QImage.Format.Format_ARGB32)
            image.fill(theme.qcolor("surface"))
            painter = QPainter(image)
            painter.drawPixmap(0, 0, shot)
            painter.end()
            ink = guikit.ink(image, theme.color("surface"))
            self.assertTrue(guikit.near(ink, "ink"), (mode, ink.name()))
            self.assertIs(field, page.inputs[0])
            self.assertEqual("3", field.text())
            self.assertEqual("3", field.selectedText())
            self.assertEqual(deadline, page.exam.draft["deadline"])
            self.assertEqual(before, Path(self.win.ai.record.path).read_bytes())

    def test_text_changes_resize_live_code_without_resetting_the_answer(self):
        self.addCleanup(theme.set_text, "normal")
        page = self.open_mock((760, 480))
        page.go(page.exam.draft["order"].index("m90-03"))
        field = page.inputs[0]
        field.setText("3")
        page.changed()
        self.assertTrue(page.persist())
        self.win.set_text("normal")
        normal = field.font().pixelSize()
        self.win.set_text("larger")
        self.idle()
        self.assertGreater(field.font().pixelSize(), normal)
        self.assertEqual("3", field.text())
        self.win.set_text("normal")
        self.idle()
        self.assertEqual(normal, field.font().pixelSize())
        self.assertEqual("3", field.text())

    def test_choice_text_size_returns_to_the_same_size_after_the_first_change(self):
        self.addCleanup(theme.set_text, "normal")
        page = self.open_mock((760, 480))
        page.go(page.exam.draft["order"].index("m90-02"))
        page.choices.rows[0].box.setChecked(True)
        picked = page.choices.picked()
        for size in ("normal", "larger", "normal"):
            self.win.set_text(size)
            self.idle()
            for row in page.choices.rows:
                self.assertEqual(theme.TYPE["learn_body"][0], row.label.font().pixelSize(), size)
            self.assertEqual(picked, page.choices.picked())

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
        (folder / 'meta.json').write_text('{}', encoding="utf-8")
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
        (folder / 'work/items.json').write_text(json.dumps({'items': self.items}, ensure_ascii=False), encoding="utf-8")
        patcher = mock.patch.object(bank, 'AI_DIR', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def open_mock(self, size=(1024, 700), start=True):
        win = self.boot(size)
        place(win, size)
        self.assertTrue(win.open_ai_mock('m90'))
        if start:
            win.ai_mock.begin()
        self.idle()
        return win.ai_mock

    def use_items(self, items):
        """임시 회차의 문항을 바꿔 씀. 44문항처럼 긴 회차는 m90 문항 넷을 번호만 바꿔 되풀이함."""
        if isinstance(items, int):
            items = [dict(self.items[n % 4], id='m90-%02d' % (n + 1)) for n in range(items)]
        (Path(self.root) / 'mocks/m90/work/items.json').write_text(json.dumps({'items': items}, ensure_ascii=False), encoding="utf-8")
        index_path = os.path.join(self.root, 'index.json')
        index = study.read_json(index_path)
        index['mocks'][0]['count'] = len(items)
        study.write_text(index_path, json.dumps(index, ensure_ascii=False))
        return items

    def test_number_chips_keep_one_width_and_grid_height_through_submit(self):
        theme.set_text('normal')
        self.addCleanup(theme.set_text, 'normal')
        self.use_items(44)
        page = self.open_mock((1280, 800))
        self.assertEqual(44, len(page.nav))
        self.assertTrue(page.grid_toggle.isChecked())
        widths = {}
        for size in ('normal', 'larger', 'normal'):
            self.win.set_text(size)
            self.idle()
            self.assertEqual(1, len({button.width() for button in page.nav}), size)
            for button in page.nav:
                self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
            widths.setdefault(size, page.nav[0].width())
            self.assertEqual(widths[size], page.nav[0].width(), size)
        self.assertGreater(widths['larger'], widths['normal'])
        before = (page.grid.height(), page.nav[0].width())
        for pos in (0, 9, 43):
            page.go(pos)
            if page.inputs:
                page.inputs[0].setText('3')
            else:
                page.choices.rows[0].box.setChecked(True)
            page.changed()
            page.flag()
        self.idle()
        self.assertEqual(before, (page.grid.height(), page.nav[0].width()))
        self.assertTrue(page.nav[9].text().endswith(' ★'))
        self.assertEqual('10번 · 답함 · 나중에 보기', page.nav[9].accessibleName())
        self.assertEqual('2번 · 비움', page.nav[1].accessibleName())
        page.submit()
        self.idle()
        self.assertEqual(before, (page.grid.height(), page.nav[0].width()))
        names = {'○': '맞음', '×': '틀림', '−': '비움'}
        for n, button in enumerate(page.nav):
            number, mark = button.text().split(' ')
            self.assertEqual(str(n + 1), number)
            self.assertEqual('%d번 · %s' % (n + 1, names[mark]), button.accessibleName())
            self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
        self.win.set_text('larger')
        self.idle()
        self.assertEqual(widths['larger'], page.nav[0].width())
        self.assertEqual(1, len({button.width() for button in page.nav}))

    def test_small_window_folds_the_grid_until_the_learner_picks(self):
        theme.set_text('normal')
        self.addCleanup(theme.set_text, 'normal')
        page = self.open_mock((760, 480))
        self.assertTrue(page.grid_toggle.isChecked())  # 4문항은 작은 창에서도 펼침
        self.assertTrue(page.nav[0].isVisible())
        self.win.close()
        self.use_items(44)
        page = self.open_mock((760, 480))
        self.assertFalse(page.grid_toggle.isChecked())
        self.assertFalse(page.grid.isVisible())
        self.assertTrue(page.grid_toggle.isVisible())
        self.assertEqual('문항 번호 · 1 / 44', page.grid_toggle.text())
        self.assertEqual('내용 접힘', page.grid_toggle.accessibleDescription())
        card = page.card.width()
        guikit.click(page.grid_toggle)
        self.assertTrue(page.grid.isVisible())
        self.assertTrue(all(button.isVisible() for button in page.nav))
        self.assertEqual('내용 펼쳐짐', page.grid_toggle.accessibleDescription())
        self.assertEqual(card, page.card.width())
        page.move(1)
        self.assertEqual('문항 번호 · 2 / 44', page.grid_toggle.text())
        self.assertTrue(page.grid.isVisible())
        self.win.resize(1280, 800)
        self.idle()
        self.assertTrue(page.grid.isVisible())
        guikit.click(page.grid_toggle)
        self.win.resize(760, 480)
        self.idle()
        self.win.resize(1280, 800)
        self.idle()
        self.assertFalse(page.grid.isVisible())
        page.begin()
        self.idle()
        self.assertTrue(page.grid_toggle.isChecked())  # 화면을 새로 열면 창 크기로 다시 정함
        self.win.resize(760, 480)
        self.idle()
        self.assertFalse(page.grid_toggle.isChecked())

    def test_grid_toggle_keyboard_and_focus_when_folding(self):
        from PyQt6.QtTest import QTest

        self.use_items(44)
        page = self.open_mock((1280, 800))
        self.assertEqual(Qt.FocusPolicy.TabFocus, page.grid_toggle.focusPolicy())
        self.assertIs(page.nav[0], page.grid_toggle.nextInFocusChain())
        self.assertIs(page.nav[1], page.nav[0].nextInFocusChain())
        page.grid_toggle.setFocus(Qt.FocusReason.TabFocusReason)
        self.idle()
        QTest.keyClick(page.grid_toggle, Qt.Key.Key_Tab)
        self.idle()
        self.assertIs(page.nav[0], QApplication.focusWidget())
        page.nav[3].setFocus(Qt.FocusReason.TabFocusReason)
        self.idle()
        QTest.keyClick(page.nav[3], Qt.Key.Key_Space)
        self.idle()
        self.assertEqual(4, page.item['at'])
        page.nav[3].setFocus(Qt.FocusReason.TabFocusReason)
        self.idle()
        self.assertIs(page.nav[3], QApplication.focusWidget())
        page.grid_toggle.click()
        self.idle()
        self.assertFalse(page.grid.isVisible())
        self.assertIs(page.grid_toggle, QApplication.focusWidget())
        QTest.keyClick(page.grid_toggle, Qt.Key.Key_Space)
        self.idle()
        self.assertTrue(page.grid.isVisible())
        self.assertEqual('내용 펼쳐짐', page.grid_toggle.accessibleDescription())

    def test_blank_cards_keep_number_name_and_format_lines(self):
        from gui import ai_text
        from gui.ai_learn import CodeSlots

        items = [dict(item) for item in self.items]
        items[3]['blanks'] = [{'answer': ['3'], 'mode': 'number', 'hint': '첫 값'}, {'answer': ['3'], 'mode': 'shape'}]
        self.use_items(items)
        page = self.open_mock((760, 480))
        order = page.exam.draft['order']

        def lines(text):
            return [label for label in page.card.findChildren(QLabel) if label.text() == text and label.isVisible()]

        page.go(order.index('m90-01'))
        self.idle()
        self.assertEqual(1, len(lines(ai_text.MODE_FORMAT['number'])))
        page.inputs[0].setText('3')
        page.changed()
        self.idle()
        self.assertEqual(1, len(lines(ai_text.MODE_FORMAT['number'])))
        self.assertEqual([], [label for label in page.card.findChildren(QLabel) if label.text() == ai_text.number_mark(1)])
        page.go(order.index('m90-04'))
        self.idle()
        self.assertEqual(1, len(lines(ai_text.MODE_FORMAT['number'])))
        self.assertEqual(1, len(lines(ai_text.MODE_FORMAT['shape'])))
        self.assertEqual(1, len(lines('첫 값')))
        self.assertTrue(lines('첫 값')[0].property('bold'))
        self.assertEqual(1, len(lines(ai_text.number_mark(2))))
        self.assertEqual(['① 첫 값', '② 모양'], [field.accessibleName() for field in page.inputs])
        self.assertEqual([ai_text.MODE_FORMAT['number'], ai_text.MODE_FORMAT['shape']], [field.accessibleDescription() for field in page.inputs])
        for label in lines(ai_text.MODE_FORMAT['shape']):
            self.assertLessEqual(label.width(), page.inputs[1].width())
        page.go(order.index('m90-03'))
        self.idle()
        slots = page.card.findChildren(CodeSlots)[0]
        self.assertEqual(page.card.contentsRect().width() - 48, slots.width())
        self.assertEqual(1, len(lines(ai_text.MODE_FORMAT['code'])))
        self.assertEqual(('코드', ai_text.MODE_FORMAT['code']), (page.inputs[0].accessibleName(), page.inputs[0].accessibleDescription()))
        page.go(order.index('m90-01'))
        page.submit()
        self.idle()
        page.go(order.index('m90-01'))
        self.idle()
        self.assertTrue(page.inputs[0].isReadOnly())
        self.assertEqual(1, len(lines(ai_text.MODE_FORMAT['number'])))

    def test_card_head_is_on_the_first_screen(self):
        theme.set_text('normal')
        self.addCleanup(theme.set_text, 'normal')
        items = self.use_items(44)
        code = '\n'.join('x%d = %d' % (n, n) for n in range(18))
        items[1] = dict(items[0], id='m90-02', stem='```python\n%s\n```\n\n마지막 값을 쓰세요: ____' % code)
        self.use_items(items)
        page = self.open_mock((760, 480))
        order = page.exam.draft['order']
        for size in ((760, 480), (1024, 700), (1280, 800)):
            for text in ('normal', 'larger'):
                for card in ('m90-01', 'm90-02'):
                    self.win.resize(*size)
                    self.win.set_text(text)
                    page.go(order.index(card))
                    self.idle()
                    at = '%d / 44' % (order.index(card) + 1)
                    head = next(label for label in page.card.findChildren(QLabel) if label.text() == at)
                    view = page.scroll.viewport()
                    top = head.mapTo(view, head.rect().topLeft())
                    bottom = head.mapTo(view, head.rect().bottomRight())
                    self.assertTrue(view.rect().contains(top) and view.rect().contains(bottom), (size, text, card))
                    self.assertIs(page.inputs[0], QApplication.focusWidget())

    def test_changed_active_exam_offers_a_new_attempt_from_the_start_button(self):
        self.addCleanup(theme.set_text, 'normal')
        page = self.open_mock((760, 480))
        win = page.win
        win.set_text('larger')
        original_path = Path(page.exam.path)
        original = original_path.read_bytes()
        self.items[0]["stem"] += " 바뀐 조건입니다."
        (Path(self.root) / "mocks/m90/work/items.json").write_text(json.dumps({"items": self.items}, ensure_ascii=False), encoding="utf-8")
        win.open_session()
        self.assertTrue(win.open_ai_mock("m90"))
        self.assertEqual("새 자료로 시작", page.start_btn.text())
        self.assertTrue(page.start_btn.isVisible())
        for mode in ('light', 'dark'):
            theme.set_mode(mode)
            win.restyle()
            self.idle()
            self.assertLessEqual(win.width(), 760)
            self.assertLessEqual(win.height(), 480)
            self.assertTrue(win.rect().contains(page.start_btn.mapTo(win, page.start_btn.rect().center())))
            self.assertGreaterEqual(page.start_btn.width(), page.start_btn.sizeHint().width())
        guikit.click(page.start_btn)
        self.assertEqual(2, page.exam.attempt)
        self.assertEqual(original, original_path.read_bytes())
        self.assertNotIn("m90", win.ai.errors)

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
        with mock.patch.object(self.win.auto_submission, "request") as checkpoint:
            page.tick()
            checkpoint.assert_called_once()
        self.assertTrue(page.exam.result['auto'])
        self.assertIs(self.win.pages.currentWidget(), self.win.ai_home)
        self.assertTrue(self.win.open_ai_mock('m90'))
        page.begin()
        self.assertIn('0 / 4문항 맞음', page.summary_text())

    def blocked_band_page(self):
        """코드 작성 문항이 없는 회차를 열고, 답을 바꾸지 않은 채 붙여넣기를 막았다는 오류 띠를 띄움."""
        page = self.open_mock((1024, 700))
        self.assertFalse(page.exam.has_code)
        page.note_blocked()
        self.assertTrue(page.notice.isVisible())
        return page

    def assert_result_without_band(self, page):
        self.idle()
        self.assertIsNotNone(page.exam.result)
        self.assertEqual('제출 완료', page.time.text())
        self.assertFalse(page.notice.isVisible())

    def test_error_band_hides_when_submitting_without_changing_the_answer(self):
        page = self.blocked_band_page()
        page.submit()
        self.assert_result_without_band(page)

    def test_error_band_hides_when_time_runs_out_without_changing_the_answer(self):
        page = self.blocked_band_page()
        self.clock = '2026-11-04T21:01:00'
        page.tick()
        self.assert_result_without_band(page)

    def test_preview_does_not_start_the_clock_or_write_a_record(self):
        page = self.open_mock(start=False)
        self.assertIsNone(page.exam)
        self.assertEqual([], self.win.ai.record.log)
        self.assertEqual([page.start_btn], kit.visible_primary_buttons(page))
        guikit.click(page.start_btn)
        self.assertIsNotNone(page.exam)
        self.assertEqual(['mock_start'], [row['kind'] for row in self.win.ai.record.log])

    def test_result_summary_card_and_lesson_rows_follow_the_dense_layout(self):
        self.addCleanup(theme.set_text, 'normal')
        page = self.open_mock((1280, 800))
        self.win.set_text('normal')
        self.idle()
        self.assertEqual(56, page.top.height())
        self.assertEqual(64, page.bar.height())
        self.assertEqual(0, page.summary.minimumHeight())
        self.assertEqual('secondary', page.heading.property('tone'))
        buttons = (page.flag_btn, page.previous_btn, page.next_btn, page.submit_btn, page.retry_btn, page.home_btn, page.notes_btn, page.start_btn)
        self.assertEqual({'m'}, {button.property('scale') for button in buttons})
        page.submit()
        self.idle()
        self.assertEqual(128, page.summary.minimumHeight())
        self.assertGreaterEqual(page.summary.height(), 128)
        self.assertEqual('label', page.heading.property('role'))
        self.assertIsNone(page.heading.property('tone'))
        self.assertIn('0 / 4문항 맞음', page.summary_text())
        rows = page.lesson_results.rows
        self.assertTrue(rows)
        summary = page.exam.summary()['lessons']
        for row in rows:
            self.assertEqual(48, row.height())
            self.assertEqual(Qt.FocusPolicy.NoFocus, row.focusPolicy())
            self.assertTrue(row.bar.isVisible())
            self.assertEqual(120, row.bar.width())
            self.assertLess(row.bar.geometry().right(), row.end.geometry().left())
            correct, total = (int(n) for n in row.end.text().split(' / '))
            self.assertEqual(round(100 * correct / total), row.bar.value())
        self.assertEqual(sum(c['total'] for c in summary.values()), sum(int(row.end.text().split(' / ')[1]) for row in rows))
        self.win.set_text('larger')
        self.idle()
        scale = theme.TYPE['body'][0] / theme.BASE_TYPE['body'][0]
        for row in rows:
            self.assertEqual(round(120 * scale), row.bar.width())
            self.assertGreaterEqual(row.height(), theme.TYPE['label'][1] + 24)
        self.assertTrue(self.win.open_ai_mock('m90'))
        self.assertEqual(0, page.summary.minimumHeight())
        self.assertEqual('body', page.heading.property('role'))

    def test_result_summary_splits_score_labels_and_lesson_prefix_column(self):
        page = self.open_mock((1280, 800))
        self.assertFalse(page.score_row.isVisible())
        page.submit()
        self.idle()
        summary = page.exam.summary()
        self.assertEqual(str(summary['score']), page.score_num.text())
        self.assertTrue(page.score_num.font().bold())
        self.assertEqual('/ %d문항 맞음' % summary['of'], page.score_of.text())
        self.assertEqual('· 걸린 시간 %d분 %d초' % (summary['secs'] // 60, summary['secs'] % 60), page.score_time.text())
        self.assertEqual('처음 점수 %d / %d' % (summary['first_score'], summary['of']), page.first_score.text())
        self.assertEqual(('accent', True), (page.first_score.value.property('tone'), page.first_score.value.font().bold()))  # 숫자만 주 색 굵게
        self.assertIn('%d / %d문항 맞음 · 걸린 시간' % (summary['score'], summary['of']), page.summary_text())
        self.assertEqual('제출 완료', page.time.text())
        self.assertEqual('label', page.time.property('role'))
        self.assertTrue(page.clock_caption.isHidden())
        for rows in (table.rows for table in page.lesson_results.lists):
            self.assertLessEqual(len({row.where.width() for row in rows}), 1)
            self.assertLessEqual(len({row.title.mapTo(page, row.title.rect().topLeft()).x() for row in rows}), 1)
            for row in rows:
                self.assertRegex(row.where.text(), r'^(응용 )?\d+차시$')
                self.assertEqual(row.accessibleName(), (row.where.text() + ' ' + row.title.text()).strip())
            self.assertEqual([bool(row.property('stripe')) for row in rows], [n % 2 == 1 for n in range(len(rows))])

    def split_items(self, code=False):
        """m90 문항을 i90·i91 두 차시에 나눔. code 면 i91 코드 작성 문항을 하나 더함."""
        from tests.test_ai_mock import code_item

        items = [dict(item) for item in self.items]
        items[1]['lesson'] = items[3]['lesson'] = 'i91'
        if code:
            items.append(code_item('m90-05', 'i91'))
        return self.use_items(items)

    def test_ready_screen_shows_type_cells_lesson_counts_and_one_clock_banner(self):
        theme.set_text('normal')
        self.addCleanup(theme.set_text, 'normal')
        for code in (False, True):
            if self.win is not None:  # 앞 차례 창을 닫음. 마지막 창은 tearDown 이 닫음
                self.win.close()
            items = self.split_items(code)
            page = self.open_mock((1280, 800), start=False)
            names = [cell.name.text() for cell in page.ready_types.cells]
            self.assertEqual(['빈칸 3문항', '객관식 1문항'] + (['코드 작성 1문항'] if code else []), names)
            self.assertEqual(len(items), sum(int(name.split()[-1][:-2]) for name in names))
            self.assertTrue(page.ready_types.isVisible() and page.lesson_counts.isVisible())
            self.assertFalse(page.result_types.isVisible() or page.lesson_results.isVisible())
            rows = page.lesson_counts.rows
            self.assertEqual(['90차시', '91차시'], [row.where.text() for row in rows])
            self.assertEqual(len(items), sum(int(row.end.text()[:-2]) for row in rows))
            self.assertTrue(all(row.bar is None for row in rows))
            self.assertNotIn('빈칸', page.heading.text())
            self.assertNotIn('객관식', page.heading.text())
            banners = [widget for widget in page.findChildren(QFrame) if widget.objectName() == 'banner' and widget.isVisible()]
            self.assertEqual([page.clock_note], banners)
            self.assertIn('시계가 멈추지 않습니다', page.clock_note.text.text())
            self.assertEqual('warning', page.clock_note.property('tone'))
            for above, below in ((page.summary, page.clock_note), (page.clock_note, page.ready_types),
                                 (page.ready_types, page.lesson_counts)):
                self.assertEqual(theme.GAP['group'], below.y() - above.y() - above.height())
            for cell in page.ready_types.cells:
                self.assertEqual(theme.GAP['title_description'],
                                 cell.second.y() - cell.name.y() - cell.name.height())
            # code=False 차례는 처음 응시라 다시 시작 안내와 지난 점수가 없어 카드를 숨김.
            # code=True 차례는 앞 차례에 시작한 초안과 문항이 달라 카드에 다시 시작 안내가 있음
            self.assertEqual(code, page.restart_required)
            self.assertEqual('새 자료로 시작' if code else '시작', page.start_btn.text())
            self.assertEqual(not code, page.card.isHidden())
            guikit.click(page.start_btn)
            self.idle()
            self.assertFalse(page.ready_types.isVisible() or page.lesson_counts.isVisible() or page.clock_note.isVisible())
            self.assertTrue(page.card.isVisible())
            self.assertTrue(page.grid.isVisible())
            self.assertEqual(theme.GAP['detail'],
                             page.grid.y() - page.grid_toggle.y() - page.grid_toggle.height())

    def test_result_type_cells_and_lesson_rows_in_lesson_order_with_zero_rows_in_danger(self):
        theme.set_text('normal')
        self.addCleanup(theme.set_text, 'normal')
        self.split_items()
        page = self.open_mock((1280, 800))
        page.exam.save_answer(['3'], 'm90-01')  # i90 은 1 / 2, i91 은 0 / 2
        page.submit()
        self.idle()
        summary = page.exam.summary()
        cells = page.result_types.cells
        self.assertTrue(page.result_types.isVisible())
        self.assertEqual(['빈칸', '객관식'], [cell.name.text() for cell in cells])
        pairs = [[int(n) for n in cell.second.text().replace(' 맞음', '').split(' / ')] for cell in cells]
        self.assertEqual(summary['score'], sum(right for right, _ in pairs))
        self.assertEqual(summary['of'], sum(total for _, total in pairs))
        self.assertTrue(all(cell.bar.isVisible() and cell.third.isHidden() for cell in cells))
        rows = page.lesson_results.rows
        self.assertEqual(['90차시', '91차시'], [row.where.text() for row in rows])
        self.assertEqual(['1 / 2', '0 / 2'], [row.end.text() for row in rows])
        for row, zero in zip(rows, (False, True)):
            for widget in (row.where, row.title, row.end):
                self.assertEqual(zero, widget.property('tone') == 'danger', widget.text())

    def test_lesson_tables_switch_between_two_and_one_column_with_the_window(self):
        theme.set_text('normal')
        self.addCleanup(theme.set_text, 'normal')
        self.split_items()
        page = self.open_mock((1280, 800), start=False)

        def lengthen(table):  # 두 열 기준은 가장 긴 차시 이름으로 재므로 이름을 14자로 늘려 760 에서 한 열이 되게 함
            table.fill([(row[0], '가' * 14) + tuple(row[2:]) for row in table.data])

        def check(table, columns):
            self.assertEqual(columns, table.columns)
            self.assertEqual(columns == 2, table.lists[1].isVisible())
            self.assertEqual(2, len(table.rows))
            self.assertEqual(['90차시 시험 차시', '91차시 준비 중 차시'], [row.accessibleName() for row in table.rows])
            if columns == 2:
                left, right = table.lists
                self.assertLess(left.geometry().right(), right.geometry().left())

        lengthen(page.lesson_counts)
        for size, columns in (((1280, 800), 2), ((760, 480), 1), ((1280, 800), 2)):
            place(self.win, size)
            self.idle()
            check(page.lesson_counts, columns)
            if columns == 2:  # 두 열이면 열마다 가장 긴 이름이 줄지 않고 들어감
                self.assertGreaterEqual(min(part.width() for part in page.lesson_counts.lists), page.lesson_counts.need())
        page.begin()
        page.submit()
        self.idle()
        lengthen(page.lesson_results)
        totals = [row.end.text() for row in page.lesson_results.rows]
        for size, columns in (((1280, 800), 2), ((760, 480), 1), ((1280, 800), 2)):
            place(self.win, size)
            self.idle()
            check(page.lesson_results, columns)
            self.assertEqual(totals, [row.end.text() for row in page.lesson_results.rows])
            self.assertEqual(0, page.scroll.horizontalScrollBar().maximum())

    def test_elided_lesson_names_show_the_whole_name_on_hover(self):
        """한 열, 큰 글자, 760x480 에서 줄임표로 줄어든 차시 이름은 마우스를 올리면 툴팁으로 전체 이름이 보임."""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QHelpEvent
        from PyQt6.QtWidgets import QToolTip

        self.addCleanup(theme.set_text, 'normal')
        self.addCleanup(QToolTip.hideText)
        self.split_items()
        page = self.open_mock((760, 480), start=False)
        self.win.set_text('larger')
        self.idle()

        def check(table):
            names = ['가' * 40, '나' * 40]  # 760 큰 글자 한 열에서도 줄임표로 줄어들 만큼 긴 이름
            table.fill([(row[0], name) + tuple(row[2:]) for row, name in zip(table.data, names)])
            self.idle()
            self.assertEqual(1, table.columns)
            for row, name in zip(table.rows, names):
                shown = QLabel.text(row.title)
                self.assertTrue(shown.endswith('…') and len(shown) < len(name), shown)
                self.assertEqual(name, row.title.toolTip())
                center = row.title.rect().center()
                QApplication.sendEvent(row.title, QHelpEvent(QEvent.Type.ToolTip, center, row.title.mapToGlobal(center)))
                guikit.pump()
                self.assertEqual(name, QToolTip.text())
                QToolTip.hideText()

        check(page.lesson_counts)
        page.begin()
        page.submit()
        self.idle()
        check(page.lesson_results)

    def test_ungraded_code_item_is_marked_after_the_third_environment_failure(self):
        from aiprep import mock_code
        from tests.test_ai_mock import RIGHT, env_grade

        self.split_items(code=True)
        page = self.open_mock((1280, 800))
        page.exam.save_answer(list(RIGHT), 'm90-05')
        with mock.patch.object(mock_code, 'grade', side_effect=env_grade):
            for _ in range(2):
                page.submit()
                self.idle()
                self.assertIsNone(page.exam.result)
                self.assertTrue(page.notice.isVisible())
            page.submit()
            self.idle()
        self.assertEqual('ungraded', page.exam.result['results']['m90-05'])
        button = page.nav[page.exam.draft['order'].index('m90-05')]
        self.assertTrue(button.text().endswith(' ?'))
        self.assertIn('이 기기에서 채점하지 못함', button.toolTip())
        self.assertEqual(button.toolTip(), button.accessibleName())
        self.assertIn('채점하지 못한 문항이 1개', page.heading.text())
        code = page.result_types.cells[-1]
        self.assertEqual(('코드 작성', '0 / 1 맞음', '채점하지 못한 문항 1개'), (code.name.text(), code.second.text(), code.third.text()))
        self.assertTrue(code.third.isVisible())

    def test_lesson_with_only_ungraded_items_is_not_marked_as_all_wrong(self):
        from aiprep import mock_code
        from tests.test_ai_mock import RIGHT, code_item, env_grade

        self.use_items([dict(item) for item in self.items] + [code_item('m90-05', 'i91')])
        page = self.open_mock((1280, 800))
        page.exam.save_answer(list(RIGHT), 'm90-05')
        with mock.patch.object(mock_code, 'grade', side_effect=env_grade):
            for _ in range(3):
                page.submit()
                self.idle()
        self.assertEqual('ungraded', page.exam.result['results']['m90-05'])
        rows = page.lesson_results.rows
        self.assertEqual(['0 / 4', '0 / 1'], [row.end.text() for row in rows])
        for row, zero in zip(rows, (True, False)):
            for widget in (row.where, row.title, row.end):
                self.assertEqual(zero, widget.property('tone') == 'danger', widget.text())

    def test_clock_caption_hides_after_submit_and_returns_on_retry(self):
        page = self.open_mock((1280, 800))
        self.assertTrue(page.clock_caption.isVisible())
        page.submit()
        self.idle()
        self.assertTrue(page.clock_caption.isHidden())
        self.assertEqual('제출 완료', page.time.text())
        guikit.click(page.retry_btn)
        self.idle()
        self.assertTrue(page.clock_caption.isVisible())
        self.assertRegex(page.time.text(), r'^\d\d:\d\d$')

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


class RealMockScreensTest(AiTest):
    """실제 회차 m1(30문항)·m4(32문항)·m11(모든 차시)의 시작 전 유형 카드와 차시 표를 봄. 예전 회차 m1·m4 의 legacy 는 이 검사 안에서만 뺌."""
    real_bank = True

    def setUp(self):
        super().setUp()
        real = bank.read_index

        def shown(path=None):
            index = real(path)
            for spec in index['mocks']:
                spec.pop('legacy', None)
            return index

        patcher = mock.patch.object(bank, 'read_index', shown)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_yolo_note_opens_from_submitted_exam_without_changing_progress(self):
        win = self.boot((760, 480))
        for mid in ('m13', 'm14'):
            with self.subTest(round=mid):
                self.assertTrue(win.open_ai_mock(mid))
                page = win.ai_mock
                page.begin()
                refs = [cid for cid, item in page.exam.items.items() if item.get('learning_reference')]
                self.assertEqual(1, len(refs))
                pos = page.exam.draft['order'].index(refs[0])
                page.go(pos)
                self.idle()
                self.assertFalse(any(b.text() == '관련 학습 보기' for b in page.card.findChildren(QPushButton)))
                page.submit()
                self.idle()
                page.go(pos)
                self.idle()
                record = Path(win.ai.record.path)
                before = record.read_bytes()
                button = next(b for b in page.card.findChildren(QPushButton) if b.isVisible() and b.text() == '관련 학습 보기')
                guikit.click(button)
                self.idle()
                note = next(d for d in win.findChildren(CodeReferenceDialog) if d.isVisible())
                self.assertIn('YOLO', visible_text(note))
                self.assertIn('검출 여부를 확인한 뒤 위치 읽기', visible_text(note))
                guikit.click(note.close_btn)
                self.idle()
                self.assertEqual(before, record.read_bytes())

    def test_ready_tables_add_up_and_empty_m11_result_marks_every_lesson(self):
        theme.set_text('normal')
        self.addCleanup(theme.set_text, 'normal')
        win = self.boot((1280, 800))
        place(win, (1280, 800))
        current_count = next(m['count'] for m in bank.read_index()['mocks'] if m['id'] == 'm11')
        for mid, count in (('m1', 30), ('m4', 32), ('m11', current_count)):
            self.assertTrue(win.open_ai_mock(mid), mid)
            page = win.ai_mock
            self.idle()
            self.assertEqual(count, sum(int(cell.name.text().split()[-1][:-2]) for cell in page.ready_types.cells), mid)
            self.assertEqual(count, sum(int(row.end.text()[:-2]) for row in page.lesson_counts.rows), mid)
            for row in page.lesson_counts.rows:
                self.assertRegex(row.where.text(), r'^(응용 )?\d+차시$')
                self.assertTrue(row.accessibleName().startswith(row.where.text() + ' '), row.accessibleName())
            win.go_ai()
        self.assertEqual(['빈칸', '객관식', '코드 작성'], [cell.name.text().rsplit(' ', 1)[0] for cell in page.ready_types.cells])
        self.assertTrue(win.open_ai_mock('m11'))
        page.begin()
        page.submit()
        self.idle()
        rows = page.lesson_results.rows
        self.assertEqual(current_count, sum(int(row.end.text().split(' / ')[1]) for row in rows))
        for row in rows:
            self.assertTrue(row.end.text().startswith('0 / '))
            self.assertEqual('danger', row.title.property('tone'))
