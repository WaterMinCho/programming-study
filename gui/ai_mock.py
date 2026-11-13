# -*- coding: utf-8 -*-
"""모의고사 답안을 로컬에 저장하고 제출한 뒤에만 판정과 해설을 보임."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget

from aiprep import bank, mixed_mock
from aiprep.grade import BLANK
from aiprep.mock import MockError
from gui import ai_text, kit, theme
from gui.ai_learn import ChoiceList, CodeChoices, CodeSlots, RichPara, doc, reading_column
from gui.docview import Doc
from gui.ai_quiz import commit_input, split_stem
from gui.widgets import AnswerLine, PasteBlock
from session import SessionError


class MockPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.setObjectName('page')
        self.win, self.exam, self.item, self.mid = win, None, None, None
        self.intro, self.showing_result, self.leaving_hint = True, False, False
        self.restart_required = False
        self.inputs, self.choices, self.nav = [], None, []
        self.busy, self.dirty = False, False
        self.paste = PasteBlock(self)
        self.paste.blocked.connect(self.note_blocked)
        root = kit.box(self)
        self.top = kit.TopBar('← AI 개론', '')
        self.clock_box, self.clock_caption, self.time = kit.clock()
        self.top.add_right(self.clock_box)
        self.top_submit = self.top.add_right(kit.button('제출', 'text', 's'))
        self.top_submit.setToolTip('모의고사를 끝내고 답안을 채점해 정답과 해설을 표시합니다. 풀이 파일의 자동 제출은 별도 동의에 따릅니다.')
        self.top_submit.clicked.connect(self.confirm_submit)
        self.top.back.clicked.connect(self.go_back)
        root.addWidget(self.top)
        body = QWidget()
        self.body = kit.box(body, spacing=theme.GAP["group"])
        self.notice = kit.banner('', 'danger')
        self.notice.hide()
        self.body.addWidget(self.notice)
        self.heading = kit.para('', 'body', 'secondary')
        self.body.addWidget(self.heading)
        self.lesson_results = kit.RowList()
        self.body.addWidget(self.lesson_results)
        self.lesson_results.hide()
        self.summary_key = None
        self.numbers = QWidget()
        self.number_row = kit.FlowLayout(self.numbers, 8)
        self.body.addWidget(self.numbers)
        self.card, self.card_box = kit.card(24, theme.GAP["group"])
        self.body.addWidget(self.card)
        self.scroll, _ = reading_column(body)
        root.addWidget(self.scroll, 1)
        self.bar = kit.BottomBar()
        self.flag_btn = self.bar.add_tool(kit.button('나중에 보기', 'text', 'l'))
        self.previous_btn = self.bar.add_action(kit.button('이전', 'secondary', 'l'))
        self.next_btn = self.bar.add_action(kit.button('다음', 'primary', 'l'))
        self.submit_btn = self.bar.add_action(kit.button('제출', 'primary', 'l'))
        self.submit_btn.setToolTip(self.top_submit.toolTip())
        self.retry_btn = self.bar.add_action(kit.button('다시 풀기', 'secondary', 'l'))
        self.retry_btn.setToolTip('같은 모의고사의 새 응시를 시작합니다. 이전 응시 기록은 보관합니다.')
        self.home_btn = self.bar.add_action(kit.button('홈으로', 'secondary', 'l'))
        self.notes_btn = self.bar.add_action(kit.button('오답 노트로', 'primary', 'l'))
        self.start_btn = self.bar.add_action(kit.button('시작', 'primary', 'l'))
        root.addWidget(self.bar)
        self.flag_btn.clicked.connect(self.flag)
        self.previous_btn.clicked.connect(lambda: self.move(-1))
        self.next_btn.clicked.connect(lambda: self.move(1))
        self.submit_btn.clicked.connect(self.confirm_submit)
        self.retry_btn.clicked.connect(self.retry)
        self.home_btn.clicked.connect(self.go_back)
        self.notes_btn.clicked.connect(lambda: self.win.show_wrong('ai', 'ai'))
        self.start_btn.clicked.connect(self.begin)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(2000)
        self.save_timer.timeout.connect(self.persist)
        for button in (self.flag_btn, self.previous_btn, self.next_btn, self.submit_btn, self.retry_btn, self.home_btn, self.notes_btn, self.start_btn, self.top_submit):
            button.hide()
        self.timer.start()

    def load(self, mid):
        if not self.persist():
            raise MockError('쓰던 답안을 먼저 저장하세요.')
        self.mid = mid
        info = self.win.ai.mock_info(mid)
        self.top.back.setText('← ' + bank.COURSES[self.win.ai.course])
        self.restart_required = info["restart_required"]
        self.top.title.setText(info['title'])
        self.top.title.show()
        if info['active'] and not self.restart_required:
            self.begin()
            return
        self.exam, self.item, self.intro = None, None, True
        self.empty_card()
        self.numbers.hide()
        self.lesson_results.hide()
        self.clock_box.hide()
        if mixed_mock.candidate(info):
            self.heading.setText(mixed_mock.description(info) + '\n빈칸 %d · 고르기 %d' % (info['blanks'], info['choices']))
            doc('120분은 약 2시간 연습을 위한 기본값입니다. 공식 평가 시간을 뜻하지 않습니다.', '', self.card_box)
        else:
            self.heading.setText('%d문항 · %d분 · %d~%d차시 · 빈칸 %d · 고르기 %d' %
                                 (info['count'], info['minutes'], *info['range'], info['blanks'], info['choices']))
        doc('시작하면 시계가 멈추지 않습니다. 프로그램을 꺼도 시간이 흐르고, 시간이 다 되면 그때까지 쓴 답으로 제출됩니다. 부분 점수는 없습니다.', '', self.card_box)
        if self.restart_required:
            doc("시작 당시 문항 버전과 현재 자료가 일치하지 않습니다. [새 자료로 시작]을 누르면 새 응시를 시작합니다. 이전 초안과 응시 기록은 보관합니다.", "", self.card_box)
        if info['taken']:
            self.card_box.addWidget(kit.para('처음 점수 %d/%d · 마지막 점수 %d/%d' %
                                            (info['first_score'], info['count'], info['last_score'], info['count']), 'headline'))
        start_label = '결과 보기' if info['taken'] else '시작'
        if self.restart_required:
            start_label = "새 자료로 시작"
        self.start_btn.setText(start_label)
        self.start_btn.setToolTip('새 자료로 새 응시를 시작하고 이전 초안과 응시 기록은 보관합니다.' if self.restart_required else
                                  '채점한 모의고사의 결과와 정답·해설을 엽니다.' if info['taken'] else
                                  '모의고사를 시작합니다. 프로그램을 꺼도 제한 시간은 계속 흐릅니다.')
        for button in (self.flag_btn, self.previous_btn, self.next_btn, self.submit_btn, self.home_btn, self.notes_btn, self.top_submit):
            button.hide()
        self.retry_btn.setVisible(info['taken'])
        self.start_btn.show()

    def begin(self, checked=False, repeat=False):
        try:
            self.exam = self.win.ai.start_mock(self.mid, repeat=repeat or self.restart_required)
        except SessionError as error:
            self.fail(error)
            return
        self.intro, self.leaving_hint = False, False
        self.restart_required = False
        self.numbers.show()
        self.clock_box.show()
        self.start_btn.hide()
        while self.number_row.count():
            item = self.number_row.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.nav = []
        for pos in range(len(self.exam.items)):
            button = kit.button(str(pos + 1), 'chip', 's')
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, pos=pos: self.go(pos))
            self.number_row.addWidget(button)
            self.nav.append(button)
        self.notice.hide()
        self.show_question()
        if self.exam.recovered_draft:
            self.notice.text.setText("이 기기의 모의고사 초안이 없어 저장된 답을 복원하지 못했습니다. 원래 시작 시각과 제한 시간을 적용합니다.")
            self.notice.show()

    def clear(self):
        self.save_timer.stop()
        self.exam, self.item, self.mid, self.dirty = None, None, None, False
        self.intro = True
        self.empty_card()

    def empty_card(self):
        while self.card_box.count():
            item = self.card_box.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self.inputs, self.choices = [], None

    def fail(self, error):
        self.notice.text.setText(str(error))
        self.notice.show()

    def values(self):
        if self.item['kind'] == 'blank':
            return [field.text() for field in self.inputs]
        return [self.item['options'][n]['no'] for n in self.choices.picked()]

    def changed(self, *_):
        self.dirty = True
        if self.exam and self.exam.result is None:
            try:
                self.exam.save_answer(self.values(), self.item['card'], flush=False)
                self.save_timer.start()
                self.update_navigation()
            except SessionError as error:
                self.fail(error)

    def persist(self):
        if self.exam is None or self.item is None or self.exam.result is not None:
            return True
        try:
            commit_input()
            if not self.dirty:
                return True
            self.exam.save_answer(self.values(), self.item['card'])
            self.dirty = False
            self.save_timer.stop()
            self.notice.hide()
            self.update_navigation()
            return True
        except MockError as error:
            self.fail(error)
            return False

    def show_question(self, pos=None):
        self.empty_card()
        self.item = item = self.exam.question(pos)
        done = self.exam.result is not None
        self.showing_result = done
        self.dirty = False
        self.card_box.addWidget(kit.label('%d / %d' % (item['at'], item['total']), 'headline'))
        if item.get('course'):
            self.card_box.addWidget(kit.para(ai_text.lesson_title(item['course_no'], '', item['course']), 'caption', 'secondary'))
        if item['kind'] == 'blank':
            blanks, count = item['blanks'], 0
            stem = bank.number_blanks(item['stem']) if len(blanks) > 1 else item['stem']
            for kind, text in split_stem(stem):
                if kind == 'code':
                    here = len(BLANK.findall(text))
                    hints = [b.get('hint') or ai_text.MODE_HINT.get(b['mode'], '') for b in blanks[count:count + here]]
                    slots = CodeSlots(text, hints, [ai_text.number_mark(count + n + 1) if len(blanks) > 1 else '' for n in range(here)])
                    self.card_box.addWidget(slots)
                    self.inputs += list(slots.fields)
                    count += here
                else:
                    doc(text, '', self.card_box)
                    for _ in BLANK.findall(text):
                        field = AnswerLine()
                        kit.typed(field, 'body')
                        field.setPlaceholderText(blanks[count].get('hint') or ai_text.MODE_HINT.get(blanks[count]['mode'], ''))
                        if len(blanks) > 1:
                            holder = QWidget()
                            row = kit.box(holder, spacing=12, horizontal=True)
                            row.addWidget(kit.label(ai_text.number_mark(count + 1), 'label'))
                            row.addWidget(field, 1)
                            self.card_box.addWidget(holder)
                        else:
                            self.card_box.addWidget(field)
                        self.inputs.append(field)
                        count += 1
            for n, field in enumerate(self.inputs):
                field.setText((item['mine'] or [])[n] if item['mine'] and n < len(item['mine']) else '')
                field.setReadOnly(done)
                self.paste.watch(field)
                field.textEdited.connect(self.changed)
        else:
            doc(item['stem'], '', self.card_box)
            texts = [option['text'] for option in item['options']]
            self.choices = CodeChoices(texts, single=not item['multi'], grid=item['grid']) if item['code_options'] else ChoiceList(texts, single=not item['multi'])
            self.card_box.addWidget(self.choices)
            for n, row in enumerate(self.choices.rows):
                row.box.setChecked(item['options'][n]['no'] in (item['mine'] or []))
            self.choices.set_enabled(not done)
            self.choices.changed.connect(self.changed)
        if done:
            info = self.exam.explain(item['card'])
            self.card_box.addWidget(kit.label({'pass': '맞음', 'stuck': '틀림', 'blank': '비움'}[info['result']], 'headline'))
            correct = info['correct'] if item['kind'] == 'blank' else [self.exam.items[item['card']]['options'][n]['text'] for n in info['right']]
            doc('정답: ' + ' / '.join(correct), '', self.card_box)
            doc(info['explain'], '', self.card_box)
            if item['kind'] == 'choice':
                for option in item['options']:
                    why = info['why'].get(option['no'])
                    if why:
                        doc('%s\n\n%s' % (option['text'], why), '', self.card_box)
        self.update_navigation()
        self.scroll.verticalScrollBar().setValue(0)
        if not done and self.inputs:
            self.inputs[0].setFocus(Qt.FocusReason.OtherFocusReason)
        self.tick()

    def update_navigation(self):
        done = self.exam.result is not None
        for n, (button, progress) in enumerate(zip(self.nav, self.exam.progress())):
            suffix = ' ★' if progress['flagged'] else (' ✓' if progress['answered'] else '')
            if done:
                suffix = ' · ' + {'pass': '맞음', 'stuck': '틀림', 'blank': '비움'}[self.exam.result['results'][progress['card']]]
            button.setText(str(n + 1) + suffix)
            button.setToolTip('%d번 · %s%s' % (n + 1, '답함' if progress['answered'] else '비움', ' · 나중에 보기' if progress['flagged'] else ''))
            button.setAccessibleName(button.toolTip())
            button.setChecked(self.item['at'] == n + 1)
        self.previous_btn.setEnabled(self.item['at'] > 1 and not self.busy)
        last = self.item['at'] == self.item['total']
        self.next_btn.setEnabled(not last and not self.busy)
        self.flag_btn.setText('표시 해제' if self.item.get('flagged') else '나중에 보기')
        self.flag_btn.setToolTip('현재 문항의 나중에 볼 표시를 지웁니다. 다른 문항으로 이동하지 않습니다.' if self.item.get('flagged') else
                                 '현재 문항에 나중에 볼 표시를 남깁니다. 다른 문항으로 이동하지 않습니다.')
        self.flag_btn.setVisible(not done)
        self.previous_btn.show()
        self.lesson_results.setVisible(done)
        self.next_btn.setVisible(done or not last)
        self.next_btn.setObjectName('' if done else 'primary')
        kit.repolish(self.next_btn)
        self.submit_btn.setVisible(not done and last)
        self.top_submit.setVisible(not done)
        self.retry_btn.setVisible(done)
        self.home_btn.setVisible(done)
        self.notes_btn.setVisible(done)
        if done:
            summary = self.exam.summary()
            rows = sorted(summary['lessons'].items(), key=lambda pair: (pair[1]['correct'] / pair[1]['total'], pair[0]))
            summary_key = (self.exam.id, summary['try'], tuple(summary['results'].items()))
            if self.summary_key != summary_key:
                self.lesson_results.clear()
                for lid, counts in rows:
                    entries = self.exam.sess.mock_lessons if self.exam.mixed else self.win.ai.lessons
                    entry = entries.get(lid, {})
                    title = ai_text.lesson_title(entry.get('no', lid), entry.get('title', ''), entry.get('course', 'intro'))
                    self.lesson_results.add(kit.Row(title.strip(), end='%d / %d' % (counts['correct'], counts['total']), inert=True))
                self.summary_key = summary_key
            self.heading.setText('%d / %d문항 맞음 · 걸린 시간 %d분 %d초\n처음 점수 %d / %d\n틀리거나 비운 문항은 첫 풀이 결과를 기준으로 다음 날부터 복습합니다.' %
                                 (summary['score'], summary['of'], summary['secs'] // 60, summary['secs'] % 60,
                                  summary['first_score'], summary['of']))
            if summary['auto']:
                self.heading.setText('시간이 끝나 자동으로 제출했습니다.\n' + self.heading.text())
            if not self.exam.local_answers:
                self.heading.setText(self.heading.text() + '\n이 기기에 저장된 답안이 없어 내 답은 표시하지 않습니다.')
        else:
            answered = sum(row['answered'] for row in self.exam.progress())
            self.heading.setText('%d / %d문항 답함 · 답은 자동으로 저장됩니다.\n제출한 뒤 정답과 해설을 확인할 수 있습니다.' % (answered, len(self.exam.items)))

    def go(self, pos):
        if self.busy or not self.persist():
            return
        try:
            if self.exam.result is None:
                self.exam.move(pos)
                self.show_question()
            else:
                self.show_question(pos)
        except MockError as error:
            self.fail(error)

    def move(self, amount):
        self.go(self.item['at'] - 1 + amount)

    def flag(self):
        if self.busy or not self.persist():
            return
        try:
            self.exam.toggle_flag()
            self.item['flagged'] = self.item['card'] in self.exam.draft['flags']
            self.update_navigation()
        except MockError as error:
            self.fail(error)

    def confirm_submit(self):
        if not self.persist():
            return
        blank = sum(not row['answered'] for row in self.exam.progress())
        text = '모의고사를 제출하고 결과를 확인합니다.'
        if blank:
            text += '\n답을 채우지 않은 문항이 %d개 있습니다.' % blank
        self.win.ask('모의고사 제출', text, (('계속 풀기', 'cancel'), ('제출', 'submit')),
                     lambda choice: self.submit() if choice == 'submit' else None)

    def submit(self, auto=False):
        if self.busy or not self.persist():
            return
        try:
            self.exam.submit(auto=auto)
            self.win.auto_submission.request()
            self.show_question(self.item['at'] - 1)
        except MockError as error:
            self.fail(error)

    def tick(self):
        if self.busy:
            return
        if self.exam is not None and self.exam.result is None and self.exam.remaining() <= 1 and self.dirty:
            self.persist()
        if getattr(self.win, 'ai', None) is not None:
            self.win.ai.expire_mocks()
        if self.exam is None:
            return
        if self.exam.result is not None:
            if not self.showing_result and self.item is not None:
                self.win.auto_submission.request()
                self.show_question(self.item['at'] - 1)
                return
            self.time.setText('제출 완료')
            return
        seconds = self.exam.remaining()
        self.time.setText('%02d:%02d' % divmod(seconds, 60))
        kit.set_tone(self.time, 'danger' if seconds <= 60 else ('warning' if seconds <= 600 else ''))
        if seconds == 0:
            self.submit(auto=True)

    def go_back(self):
        if self.persist():
            if self.exam is not None and self.exam.result is None and not self.leaving_hint:
                self.leaving_hint = True
                self.win.ask('모의고사', '시간은 계속 흐릅니다. 홈에서 다시 열 수 있습니다.',
                             on_choice=lambda _: self.win.go_ai())
            else:
                self.win.go_ai()

    def retry(self):
        self.begin(repeat=True)

    def note_blocked(self):
        self.fail('시험과 같은 조건으로 풀 수 있도록 붙여넣기를 막았습니다.')

    def set_busy(self, busy, text=''):
        self.busy = busy
        for widget in (self.top.back, self.flag_btn, self.submit_btn, self.retry_btn, self.numbers, self.card, self.start_btn, self.notes_btn, self.home_btn, self.top_submit):
            widget.setEnabled(not busy)
        if self.exam and self.item:
            self.update_navigation()

    def restyle(self):
        for widget in self.findChildren(Doc):
            widget.restyle(theme.learning_css())
        for widget in self.findChildren(RichPara):
            widget.restyle()
        for widget in self.findChildren(CodeSlots):
            widget.restyle()
        for widget in self.findChildren(kit.Chevron):
            widget.update()
