# -*- coding: utf-8 -*-
"""모의고사 답안을 로컬에 저장하고 제출한 뒤에만 판정과 해설을 보임."""
import math
from time import monotonic

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtWidgets import QApplication, QBoxLayout, QFrame, QSizePolicy, QTextBrowser, QWidget

from aiprep import bank, mixed_mock, mock_code
from aiprep.grade import BLANK
from aiprep.mock import ENV_FAILED, MockError
from journey import values as journey_values
from gui import ai_text, kit, theme
from gui.ai_learn import ChoiceList, CodeChoices, CodeSlots, RichPara, doc, reading_column
from gui.disclosure import DisclosureButton
from gui.docview import Doc
from gui.ai_quiz import commit_input, split_stem
from gui.round_page import CONSOLE_CSS, run_html
from gui.widgets import AnswerLine, CodePanel, PasteBlock, content_height
from session import SessionError


SUMMARY_LEAST = 128  # 제출 뒤 요약 카드 최소 높이
BAR_WIDTH = 120  # 보통 글자에서 차시별 막대 폭
GRID_SHARE = 3  # 펼친 번호 칸 묶음이 스크롤 영역 높이의 1/3 을 넘으면 접음
RESULT_NAME = {'pass': '맞음', 'stuck': '틀림', 'blank': '비움', 'ungraded': '이 기기에서 채점하지 못함'}
RETRY_SECONDS = 60  # 마감 채점이 실행 환경 문제로 실패하면 다시 시도하기까지 기다리는 시간
CODE_GUIDE = '채울 줄에 코드를 한 줄씩 씁니다. 다른 줄은 고칠 수 없습니다.'
GRADING = '답안을 채점하고 있습니다. 채점이 끝날 때까지 답을 바꿀 수 없습니다.'
AUTO_GRADING = '제한 시간이 끝나 저장해 둔 답안을 채점하고 있습니다. 채점이 끝날 때까지 답을 바꿀 수 없습니다.'
AUTO_ENV = '시간이 끝나 제출하려 했지만 이 기기에서 코드 작성 문항을 채점하지 못했습니다. 1분 뒤 다시 채점합니다.'
RUNNING = '공개 예시로 코드를 실행하고 있습니다.'
JOB_BUSY = '다른 작업이 아직 끝나지 않았습니다. 잠시 뒤 같은 단추를 다시 눌러 주세요.'
TYPE_CELL = 240  # 보통 글자에서 유형 카드 하나의 최소 폭. 카드 수만큼 들어가지 않으면 세로로 쌓음
TYPES = (('blank', '빈칸', '지문이나 코드의 빈칸에 답을 씁니다.'), ('choice', '객관식', '보기에서 답을 고릅니다.'),
         ('code', '코드 작성', '함수의 빈 줄을 채워 숨은 테스트를 모두 통과하면 맞습니다.'))


def solution_code(starter, lines):
    """시작 코드의 채울 줄에 모범 답안 줄을 넣은 코드. 들여쓰기는 시작 코드를 따름(mock_code.source 와 같음)."""
    rows, answers = starter.rstrip('\n').split('\n'), iter(lines)
    return '\n'.join(row[:len(row) - len(row.lstrip())] + next(answers, '').lstrip() if row.strip() == mock_code.FILL else row
                     for row in rows)


def console_run(entry, result):
    """MockExam.run_code 결과를 round_page.run_html 이 읽는 꼴로 바꿈. 'input' 값에는 함수 호출 글을 씀."""
    cases = []
    for case in result['cases']:
        ran = case['status'] in ('pass', 'wrong')
        cases.append({'ok': case['status'] == 'pass',
                      'input': '%s(%s)' % (entry, journey_values.show_args(case['args'], 'python')),
                      'want': journey_values.show(case['expected'], 'python'),
                      'got': journey_values.show(case['actual'], 'python') if ran else (case['error'] or case['reason']),
                      'printed': case['printed']})
    return {'cases': cases, 'message': result['reason']}


def lesson_parts(entries, lid):
    """차시 id 의 (앞 칸 'N차시'·'응용 N차시', 이름, 전체 이름, 정렬 키). 정렬은 개론 → 응용, 번호 순."""
    entry = entries.get(lid, {})
    no, course = entry.get('no', lid), entry.get('course', 'intro')
    title = ai_text.lesson_title(no, entry.get('title', ''), course).strip()
    prefix = ai_text.lesson_title(no, '', course)
    name = title[len(prefix):].strip() if title.startswith(prefix) else title
    return prefix, name, title, (course != 'intro', no if isinstance(no, int) else 10 ** 6, str(lid))


def scaled(width):
    return round(width * theme.TYPE['body'][0] / theme.BASE_TYPE['body'][0])


class LessonTable(QFrame):
    """차시별 표. 줄 자료를 받아 폭이 넉넉하면 두 열(왼쪽 앞 차시, 오른쪽 뒤 차시), 모자라면 한 열로 둠.
    열마다 RowList(striped) 하나를 쓰고 'N차시' 칸 폭을 열마다 맞춤. rows 는 왼쪽 열 줄 다음 오른쪽 열 줄."""

    def __init__(self):
        super().__init__()
        self.setObjectName('card')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = kit.box(self, horizontal=True)
        self.lists = [kit.RowList(inside_card=True, least=48, pad=12, striped=True) for _ in range(2)]
        self.divider = kit.frame('rowline')
        self.divider.setFixedWidth(1)
        row.addWidget(self.lists[0], 1, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.divider)
        row.addWidget(self.lists[1], 1, Qt.AlignmentFlag.AlignTop)
        self.data, self.columns = [], 0

    @property
    def rows(self):
        return self.lists[0].rows + self.lists[1].rows

    def fill(self, data):
        """data 는 (앞 칸, 이름, 전체 이름, 끝 글, 막대 값 또는 None, danger 글자로 쓸지) 줄의 목록.
        마지막 값은 채점한 문항이 있는데 하나도 못 맞힌 차시에서 참임."""
        self.data = list(data)
        self.columns = 0
        self.refit()

    def need(self):
        """한 열에 필요한 폭. 줄 좌우 여백, 가장 긴 앞 칸, 가장 긴 이름, 막대, 가장 긴 끝 글과 그 사이 간격.
        두 열에서 이름이 줄임표로 줄지 않게 가장 긴 이름을 재고, 줄 배치가 칸마다 정수 폭을 주므로 칸마다 올림함."""
        caption, label = QFontMetricsF(theme.font('caption')), QFontMetricsF(theme.font('label'))
        lead = max((math.ceil(caption.horizontalAdvance(row[0])) for row in self.data), default=0)
        name = max((math.ceil(label.horizontalAdvance(row[1])) for row in self.data), default=0)
        end = max((math.ceil(caption.horizontalAdvance(row[3])) for row in self.data), default=0)
        bar = scaled(BAR_WIDTH) + 12 if any(row[4] is not None for row in self.data) else 0
        return 48 + lead + 2 + 12 + name + 12 + bar + end

    def refit(self):
        """폭과 글자 크기에 맞춰 열 수를 정하고, 바뀌었으면 줄을 다시 만듦. 막대 폭과 앞 칸 폭은 늘 다시 맞춤."""
        if not self.data:
            return
        room = (self.contentsRect().width() - 1 - 2 * self.layout().spacing()) // 2  # 세로선 1px 과 그 양옆 간격을 뺀 한 열 폭
        columns = 2 if len(self.data) > 1 and room >= self.need() else 1
        if columns != self.columns:
            self.columns = columns
            split = math.ceil(len(self.data) / columns)
            for n, part in enumerate((self.data[:split], self.data[split:])):
                self.lists[n].clear()
                for prefix, name, title, end, value, zero in part:
                    where = kit.label(prefix, 'caption', 'secondary')
                    row = self.lists[n].add(kit.Row(name, end=end, inert=True, lead=where))
                    row.setAccessibleName(title)
                    row.where, row.bar = where, None
                    if value is not None:
                        row.bar = kit.progress(thin=True)
                        row.bar.setValue(value)
                        row.layout().insertWidget(row.layout().indexOf(row.end), row.bar, 0, Qt.AlignmentFlag.AlignVCenter)
                    if zero:
                        for widget in (where, row.title, row.end):
                            kit.set_tone(widget, 'danger')
            self.lists[1].setVisible(columns == 2)
            self.divider.setVisible(columns == 2)
        for rows in (self.lists[0].rows, self.lists[1].rows):
            column = max((math.ceil(QFontMetricsF(theme.font('caption')).horizontalAdvance(row.where.text())) for row in rows), default=0)
            for row in rows:
                if row.bar is not None:
                    row.bar.setFixedWidth(scaled(BAR_WIDTH))
                row.where.setFixedWidth(column + 2)
                row.fit_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refit()


class TypeCells(QWidget):
    """문항 유형 카드. 카드마다 이름 줄과 설명(시작 전) 또는 맞은 수 줄과 막대(결과). 폭이 모자라면 세로로 쌓음."""

    def __init__(self):
        super().__init__()
        self.row = kit.box(self, spacing=theme.SPACE[2], horizontal=True)
        self.cells = []

    def fill(self, cells):
        """cells 는 (이름, 둘째 줄, 셋째 줄, 막대 값 또는 None) 의 목록. 빈 줄은 숨김."""
        for cell in self.cells:
            self.row.removeWidget(cell)
            cell.hide()
            cell.deleteLater()
        self.cells = []
        for name, second, third, value in cells:
            cell, inner = kit.card(16, theme.GAP["detail"])
            cell.name = kit.label(name, 'label', bold=True)
            cell.second = kit.para(second, 'caption', 'secondary')
            cell.third = kit.para(third, 'caption', 'secondary')
            inner.addWidget(kit.heading(cell.name, cell.second))
            inner.addWidget(cell.third)
            cell.third.setVisible(bool(third))
            cell.bar = None
            if value is not None:
                cell.bar = kit.progress(thin=True)
                cell.bar.setValue(value)
                inner.addWidget(cell.bar)
            inner.addStretch(1)
            self.row.addWidget(cell, 1)
            self.cells.append(cell)
        self.refit()

    def refit(self):
        wide = self.width() >= len(self.cells) * scaled(TYPE_CELL) + (len(self.cells) - 1) * self.row.spacing()
        direction = QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom
        if self.row.direction() != direction:
            self.row.setDirection(direction)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refit()


def name_blank(field, blanks, n):
    """빈칸 입력 칸의 접근성 이름은 번호와 이름표(없으면 입력 종류), 설명은 형식 줄과 같은 글로 둠."""
    blank = blanks[n]
    mark = ai_text.number_mark(n + 1) if len(blanks) > 1 else ''
    field.setAccessibleName(' '.join(filter(None, (mark, blank.get('hint') or ai_text.MODE_HINT.get(blank['mode'], '')))))
    field.setAccessibleDescription(ai_text.MODE_FORMAT[blank['mode']])


class FirstScore(QWidget):
    """제출 뒤 '처음 점수' 줄. 이름은 label 글, 점수 숫자는 주 색 굵은 글로 나눠 둠. text() 는 두 글을 이어 붙인 글."""

    def __init__(self):
        super().__init__()
        row = kit.box(self, spacing=theme.SPACE[0], horizontal=True)
        self.name = kit.label('처음 점수', 'label')
        self.value = kit.label('', 'label', 'accent', bold=True)
        row.addWidget(self.name)
        row.addWidget(self.value)
        row.addStretch(1)

    def set_value(self, text):
        self.value.setText(text)

    def text(self):
        return '%s %s' % (self.name.text(), self.value.text())


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
        self.grading, self.retry_at = False, 0.0  # 마감 채점이 도는지, 실패 뒤 다시 시도할 monotonic 시각
        self.split, self.console = None, None
        self.paste = PasteBlock(self)
        self.paste.blocked.connect(self.note_blocked)
        root = kit.box(self)
        self.top = kit.TopBar('← AI 개론', '', dense=True)
        self.clock_box, self.clock_caption, self.time = kit.clock()
        self.top.add_right(self.clock_box)
        self.top_submit = self.top.add_right(kit.button('제출', 'text', 's'))
        self.top_submit.setToolTip('모의고사를 끝내고 답안을 채점해 정답과 해설을 표시합니다. 풀이 파일의 자동 제출은 별도 동의에 따릅니다.')
        self.top_submit.clicked.connect(self.confirm_submit)
        self.top.back.clicked.connect(self.go_back)
        root.addWidget(self.top)
        body = kit.dense(QWidget())
        self.body = kit.box(body, spacing=theme.GAP["group"])
        self.notice = kit.banner('', 'danger')
        self.notice.hide()
        self.body.addWidget(self.notice)
        self.busy_note = kit.banner('', '')  # 채점과 [코드 실행]이 도는 동안 하는 일을 적는 띠. 글은 set_busy 와 wait_note 가 넣음
        self.busy_note.hide()
        self.body.addWidget(self.busy_note)
        self.summary, summary_box = kit.card(24, theme.GAP["title_description"])
        self.summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        # 제출 뒤에는 자동 제출 안내, 맞은 수 줄, 처음 점수를 따로 두고 heading 에는 복습 안내와 내 답 없음 안내만 둠
        self.auto_note = kit.para('', 'label')
        self.score_row = QWidget()
        score_box = kit.box(self.score_row, spacing=8, horizontal=True)
        self.score_num = kit.label('', 'title', bold=True)
        self.score_of = kit.label('', 'headline')
        self.score_time = kit.label('', 'caption', 'secondary')
        for widget in (self.score_num, self.score_of, self.score_time):
            score_box.addWidget(widget, 0, Qt.AlignmentFlag.AlignBottom)
        score_box.addStretch(1)
        kit.baseline(self.score_num, self.score_of, self.score_time)
        self.first_score = FirstScore()
        self.heading = kit.para('', 'body', 'secondary')
        for widget in (self.auto_note, self.score_row, self.first_score):
            summary_box.addWidget(widget)
            widget.hide()
        summary_box.addWidget(self.heading)
        self.body.addWidget(self.summary)
        # 시작 전에는 시계 안내 띠, 유형 카드와 차시별 문항 수, 제출 뒤에는 유형별·차시별 맞은 수를 요약 카드 아래에 둠
        self.clock_note = kit.banner('', 'warning')
        self.clock_note.hide()
        self.body.addWidget(self.clock_note)
        self.ready_types, self.result_types = TypeCells(), TypeCells()
        self.lesson_counts, self.lesson_results = LessonTable(), LessonTable()
        for widget in (self.ready_types, self.lesson_counts, self.result_types, self.lesson_results):
            self.body.addWidget(widget)
            widget.hide()
        self.summary_key = None
        self.numbers = QWidget()
        numbers_box = kit.box(self.numbers, spacing=theme.GAP["detail"])
        self.grid_toggle = DisclosureButton('문항 번호', role='label')
        self.grid_toggle.setChecked(True)
        self.grid = QWidget()
        self.number_row = kit.FlowLayout(self.grid, 8)
        numbers_box.addWidget(self.grid_toggle)
        numbers_box.addWidget(self.grid)
        self.grid_toggle.toggled.connect(self.show_grid)
        self.grid_toggle.clicked.connect(self.pick_grid)
        self.fold_auto = True  # 참이면 창 높이로 접고 펼침. 학습자가 접거나 펼치면 거짓이 되어 그 회차 화면이 열려 있는 동안 고른 상태를 지킴
        self.body.addWidget(self.numbers)
        self.card, self.card_box = kit.card(24, theme.GAP["group"])
        self.body.addWidget(self.card)
        self.scroll, _ = reading_column(body)
        self.scroll.installEventFilter(self)
        root.addWidget(self.scroll, 1)
        self.bar = kit.BottomBar(dense=True)
        self.flag_btn = self.bar.add_tool(kit.button('나중에 보기', 'text', 'm'))
        self.run_btn = self.bar.add_tool(kit.button('코드 실행', 'text', 'm'))
        self.run_btn.setToolTip('공개 예시로 코드를 실행합니다. 실행 결과는 기록하지 않고 점수에 넣지 않습니다.')
        self.run_btn.clicked.connect(self.run_code)
        self.previous_btn = self.bar.add_action(kit.button('이전', 'secondary', 'm'))
        self.next_btn = self.bar.add_action(kit.button('다음', 'primary', 'm'))
        self.submit_btn = self.bar.add_action(kit.button('제출', 'primary', 'm'))
        self.submit_btn.setToolTip(self.top_submit.toolTip())
        self.retry_btn = self.bar.add_action(kit.button('다시 풀기', 'secondary', 'm'))
        self.retry_btn.setToolTip('같은 모의고사의 새 응시를 시작합니다. 이전 응시 기록은 보관합니다.')
        self.home_btn = self.bar.add_action(kit.button('홈으로', 'secondary', 'm'))
        self.notes_btn = self.bar.add_action(kit.button('오답 노트로', 'primary', 'm'))
        self.start_btn = self.bar.add_action(kit.button('시작', 'primary', 'm'))
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
        self.head_timer = QTimer(self)  # 창이 초점 받은 칸을 보이게 하는 타이머보다 나중에 시작해 그 뒤에 돎
        self.head_timer.setSingleShot(True)
        self.head_timer.timeout.connect(self.keep_head)
        for button in (self.flag_btn, self.run_btn, self.previous_btn, self.next_btn, self.submit_btn, self.retry_btn, self.home_btn, self.notes_btn, self.start_btn, self.top_submit):
            button.hide()
        self.timer.start()

    def load(self, mid):
        if not self.persist():
            raise MockError('쓰던 답안을 먼저 저장하세요.')
        self.mid = mid
        info = self.win.ai.mock_info(mid)
        self.top.back.setText('← 모의고사' if self.win.ai_home.tab == 'mock' else '← ' + bank.COURSES[self.win.ai.course])
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
        self.result_types.hide()
        self.clock_box.hide()
        self.show_summary(False)
        clock_note = '시작하면 시계가 멈추지 않습니다. 프로그램을 꺼도 시간이 흐르고, 시간이 다 되면 그때까지 쓴 답으로 제출됩니다. 부분 점수는 없습니다.'
        if mixed_mock.candidate(info):
            self.heading.setText(mixed_mock.description(info))
            clock_note = '120분은 약 2시간 연습을 위한 기본값입니다. 공식 평가 시간을 뜻하지 않습니다. ' + clock_note
            entries = self.win.ai.mock_lessons
        else:
            self.heading.setText('%d문항 · %d분 · %d~%d차시' % (info['count'], info['minutes'], *info['range']))
            entries = self.win.ai.lessons
        counts = {'blank': info['blanks'], 'choice': info['choices'], 'code': info['codes']}
        self.ready_types.fill([('%s %d문항' % (name, counts[kind]), note, '', None) for kind, name, note in TYPES if counts[kind]])
        lessons = sorted(((lesson_parts(entries, lid), count) for lid, count in info['lessons'].items()), key=lambda pair: pair[0][3])
        self.lesson_counts.fill([(prefix, name, title, '%d문항' % count, None, False) for (prefix, name, title, _), count in lessons])
        self.ready_types.show()
        self.lesson_counts.show()
        self.clock_note.text.setText(clock_note)
        self.clock_note.show()
        if self.restart_required:
            doc("시작 당시 문항 버전과 현재 자료가 일치하지 않습니다. [새 자료로 시작]을 누르면 새 응시를 시작합니다. 이전 초안과 응시 기록은 보관합니다.", "", self.card_box)
        if info['taken']:
            self.card_box.addWidget(kit.para('처음 점수 %d/%d · 마지막 점수 %d/%d' %
                                            (info['first_score'], info['count'], info['last_score'], info['count']), 'headline'))
        self.card.setVisible(self.card_box.count() > 0)  # 다시 시작 안내와 지난 점수가 없으면 빈 카드를 숨김
        start_label = '결과 보기' if info['taken'] else '시작'
        if self.restart_required:
            start_label = "새 자료로 시작"
        self.start_btn.setText(start_label)
        self.start_btn.setToolTip('새 자료로 새 응시를 시작하고 이전 초안과 응시 기록은 보관합니다.' if self.restart_required else
                                  '채점한 모의고사의 결과와 정답·해설을 엽니다.' if info['taken'] else
                                  '모의고사를 시작합니다. 프로그램을 꺼도 제한 시간은 계속 흐릅니다.')
        for button in (self.flag_btn, self.run_btn, self.previous_btn, self.next_btn, self.submit_btn, self.home_btn, self.notes_btn, self.top_submit):
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
        self.clock_note.hide()
        self.card.show()
        self.ready_types.hide()
        self.lesson_counts.hide()
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
        for before, after in zip([self.grid_toggle] + self.nav, self.nav):
            QWidget.setTabOrder(before, after)
        self.fold_auto = True
        self.size_chips()
        self.notice.hide()
        self.show_question()
        self.fit_grid()
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
        self.inputs, self.choices, self.head = [], None, None
        self.split, self.console = None, None
        if not self.busy:  # 다른 화면의 작업은 끝나도 이 화면의 set_busy 를 부르지 않아 wait_note 띠가 남으므로 문항을 바꿀 때 숨김
            self.busy_note.hide()

    def fail(self, error):
        self.notice.text.setText(str(error))
        self.notice.show()

    def wait_note(self):
        """다른 작업이 돌고 있어 [코드 실행]이나 제출을 시작하지 못했을 때 오류 띠가 아니라 안내 띠에 JOB_BUSY 를 띄움.
        같은 단추를 다시 눌러 작업이 시작되면 set_busy 가 띠 글을 바꾸고, 그 작업이 끝나면 띠를 숨김.
        다시 누르지 않으면 답을 저장하거나 문항을 바꿀 때 persist 와 empty_card 가 띠를 숨김."""
        self.busy_note.text.setText(JOB_BUSY)
        self.busy_note.show()

    def values(self):
        if self.item['kind'] in ('blank', 'code'):
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
            self.expire_when_due()

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
            if not self.busy:
                self.busy_note.hide()
            self.update_navigation()
            self.expire_when_due()
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
        self.head = top = QWidget()
        head = kit.box(top, spacing=theme.SPACE[2], horizontal=True)
        head.addWidget(kit.label('%d / %d' % (item['at'], item['total']), 'headline'))
        if item.get('course'):
            head.addWidget(kit.badge(ai_text.lesson_title(item['course_no'], '', item['course']), 'accent'))
        head.addStretch(1)
        self.card_box.addWidget(top)
        if item['kind'] == 'code':
            self.build_code(item, done)
        elif item['kind'] == 'blank':
            blanks, count = item['blanks'], 0
            stem = bank.number_blanks(item['stem']) if len(blanks) > 1 else item['stem']
            for kind, text in split_stem(stem):
                if kind == 'code':
                    here = len(BLANK.findall(text))
                    hints = [b.get('hint') or ai_text.MODE_HINT.get(b['mode'], '') for b in blanks[count:count + here]]
                    slots = CodeSlots(text, hints, [ai_text.number_mark(count + n + 1) if len(blanks) > 1 else '' for n in range(here)])
                    self.card_box.addWidget(slots)
                    self.inputs += list(slots.fields)
                    for n, field in enumerate(slots.fields):
                        name_blank(field, blanks, count + n)
                    for n, blank in enumerate(blanks[count:count + here]):
                        parts = [ai_text.number_mark(count + n + 1)] if len(blanks) > 1 else []
                        parts.append(' · '.join(filter(None, (blank.get('hint'), ai_text.MODE_FORMAT[blank['mode']]))))
                        self.card_box.addWidget(kit.para(' '.join(parts), 'caption', 'secondary'))
                    count += here
                else:
                    doc(text, '', self.card_box)
                    for _ in BLANK.findall(text):
                        field = AnswerLine()
                        kit.typed(field, 'body')
                        field.setPlaceholderText(blanks[count].get('hint') or ai_text.MODE_HINT.get(blanks[count]['mode'], ''))
                        name_blank(field, blanks, count)
                        holder = QWidget()
                        column = kit.box(holder, spacing=theme.SPACE[1])
                        if len(blanks) > 1 or blanks[count].get('hint'):
                            row = kit.box(None, spacing=theme.SPACE[1], horizontal=True)
                            if len(blanks) > 1:
                                row.addWidget(kit.label(ai_text.number_mark(count + 1), 'label'))
                            if blanks[count].get('hint'):
                                row.addWidget(kit.label(blanks[count]['hint'], 'label', bold=True))
                            row.addStretch(1)
                            column.addLayout(row)
                        column.addWidget(field)
                        column.addWidget(kit.para(ai_text.MODE_FORMAT[blanks[count]['mode']], 'caption', 'secondary'))
                        self.card_box.addWidget(holder)
                        self.inputs.append(field)
                        count += 1
        else:
            doc(item['stem'], '', self.card_box)
            texts = [option['text'] for option in item['options']]
            self.choices = CodeChoices(texts, single=not item['multi'], grid=item['grid']) if item['code_options'] else ChoiceList(texts, single=not item['multi'])
            self.card_box.addWidget(self.choices)
            for n, row in enumerate(self.choices.rows):
                row.box.setChecked(item['options'][n]['no'] in (item['mine'] or []))
            self.choices.set_enabled(not done)
            self.choices.changed.connect(self.changed)
        for n, field in enumerate(self.inputs):
            field.setText((item['mine'] or [])[n] if item['mine'] and n < len(item['mine']) else '')
            field.setReadOnly(done)
            self.paste.watch(field)
            field.textEdited.connect(self.changed)
        if done:
            info = self.exam.explain(item['card'])
            self.card_box.addWidget(kit.label(RESULT_NAME[info['result']], 'headline'))
            if item['kind'] == 'code':
                if info['passed']:
                    self.card_box.addWidget(kit.para('채점에 쓴 숨은 테스트 %d개 중 %d개 통과' % (info['passed'][1], info['passed'][0]), 'body'))
                doc('**모범 답안**\n\n```python\n%s\n```' % solution_code(item['starter'], info['solution']), '', self.card_box)
            else:
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
            self.head_timer.start(0)
        self.tick()

    def build_code(self, item, done):
        """코드 작성 문항. 지문, 코드, 실행 결과 순서로 한 열에 둠.
        시작 코드의 ____ 줄마다 한 줄 칸을 두어 그 줄만 고칠 수 있음. 칸 사이는 Tab 으로 옮겨 감."""
        self.split = QWidget()
        box = kit.box(self.split, spacing=theme.GAP['group'])
        left, right = QWidget(), QWidget()
        stem = kit.box(left, spacing=theme.GAP['paragraph'])
        doc(item['stem'], '', stem)
        if item['examples']:
            stem.addWidget(kit.para('예시', 'label', bold=True))
            calls = ('>>> %s(%s)\n%s' % (item['entry'], journey_values.show_args(example['args'], 'python'),
                                         journey_values.show(example['expected'], 'python')) for example in item['examples'])
            doc('```python\n%s\n```' % '\n'.join(calls), '', stem)
        stem.addStretch(1)
        code = kit.box(right, spacing=theme.SPACE[2])
        if not done:
            code.addWidget(kit.para(CODE_GUIDE, 'caption', 'secondary'))
        count = len(BLANK.findall(item['starter']))
        slots = CodeSlots(item['starter'], [''] * count, [''] * count)
        code.addWidget(slots)
        for n, field in enumerate(slots.fields):
            field.setAccessibleName('채울 줄 %d' % (n + 1))
        self.inputs = list(slots.fields)
        if not done:
            self.console = QTextBrowser()
            self.console.setObjectName('console')
            self.console.setOpenLinks(False)
            self.console.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.console.html = ''
            self.console.installEventFilter(self)
            code.addWidget(self.console)
            self.show_console('')
        code.addStretch(1)
        box.addWidget(left, 1)
        box.addWidget(right, 1)
        self.card_box.addWidget(self.split)

    def show_console(self, html):
        self.console.html = html
        self.console.document().setDefaultStyleSheet(theme.learning_css() + CONSOLE_CSS % {name: theme.color(name) for name in ('ok', 'track')})
        self.console.setHtml(html or '<body><p class="muted">%s</p></body>' % CodePanel.HINT)
        self.fit_console()

    def fit_console(self):
        """실행 결과 상자 높이를 내용에 맞춤. 상자의 Resize 를 받을 때는 viewport 크기가 아직 옛 값이라 지금 크기로 잰 contentsRect 를 씀.
        테두리 둥근 모서리 때문에 좌우와 위아래 안쪽 여백이 달라 frameWidth 를 쓰지 않음."""
        if self.console is None:
            return
        document, inner = self.console.document(), self.console.contentsRect()
        document.setTextWidth(inner.width())
        self.console.setFixedHeight(math.ceil(content_height(document)) + self.console.height() - inner.height())

    def run_code(self):
        if self.busy or self.item is None or self.item['kind'] != 'code' or not self.persist() or self.grading:
            return  # 마감 뒤에는 persist 가 마감 채점을 띄우므로 실행하지 않음
        exam, lines, cid, entry = self.exam, self.values(), self.item['card'], self.item['entry']
        if not self.win.run_job(RUNNING, lambda: exam.run_code(lines, cid), lambda result: self.ran(cid, entry, result)):
            self.wait_note()

    def ran(self, cid, entry, result):
        if self.console is not None and self.item is not None and self.item['card'] == cid:
            self.show_console(run_html(console_run(entry, result)))

    def expire_when_due(self):
        """코드 작성 회차는 마감 뒤 답 저장·문항 이동·나중에 보기 표시에서 제출하지 않고 거짓을 돌려줌. 그때 작업 스레드에서 마감 채점을 띄움."""
        exam = self.exam
        if exam is not None and exam.has_code and exam.result is None and exam.remaining() <= 0:
            self.expire_code()

    def expire_code(self):
        """마감이 지난 코드 작성 회차를 작업 스레드에서 expire_mocks 로 제출함. 이미 채점 중이거나, 실패 뒤 다시 시도할 시각 전이거나,
        다른 작업이 돌고 있으면 아무것도 하지 않음."""
        if self.grading or monotonic() < self.retry_at or getattr(self.win, 'job', None) is not None:
            return
        self.grading = True
        if not self.win.run_job(AUTO_GRADING, self.win.ai.expire_mocks, self.expired, self.expire_failed):
            self.grading = False

    def expired(self, _):
        self.grading = False
        ai = self.win.ai
        if ai.expired_code_mocks:
            self.retry_at = monotonic() + RETRY_SECONDS
        if self.exam is not None and self.exam.result is None and self.exam.id in ai.expired_code_mocks:
            error = ai.errors.get(self.exam.id, '')
            self.fail(AUTO_ENV if error == ENV_FAILED else error)
        elif self.exam is not None and self.exam.result is not None:
            self.notice.hide()
        self.tick()

    def expire_failed(self):
        self.grading = False
        self.retry_at = monotonic() + RETRY_SECONDS

    def keep_head(self):
        """첫 칸에 초점을 준 뒤 창이 그 칸까지 스크롤해도 카드 머리는 화면에 남게 함."""
        if self.head is None:
            return
        bar = self.scroll.verticalScrollBar()
        bar.setValue(min(bar.value(), max(0, self.head.mapTo(self.scroll.widget(), self.head.rect().topLeft()).y() - 16)))

    def update_navigation(self):
        done = self.exam.result is not None
        for n, (button, progress) in enumerate(zip(self.nav, self.exam.progress())):
            suffix = ' ★' if progress['flagged'] else (' ✓' if progress['answered'] else '')
            if done:
                result = self.exam.result['results'][progress['card']]
                button.setText('%d %s' % (n + 1, ai_text.RESULT_MARK[result]))
                button.setToolTip('%d번 · %s' % (n + 1, RESULT_NAME[result]))
            else:
                button.setText(str(n + 1) + suffix)
                button.setToolTip('%d번 · %s%s' % (n + 1, '답함' if progress['answered'] else '비움', ' · 나중에 보기' if progress['flagged'] else ''))
            button.setAccessibleName(button.toolTip())
            button.setChecked(self.item['at'] == n + 1)
        self.grid_toggle.setText('문항 번호 · %d / %d' % (self.item['at'], self.item['total']))
        self.previous_btn.setEnabled(self.item['at'] > 1 and not self.busy)
        last = self.item['at'] == self.item['total']
        self.next_btn.setEnabled(not last and not self.busy)
        self.flag_btn.setText('표시 해제' if self.item.get('flagged') else '나중에 보기')
        self.flag_btn.setToolTip('현재 문항의 나중에 볼 표시를 지웁니다. 다른 문항으로 이동하지 않습니다.' if self.item.get('flagged') else
                                 '현재 문항에 나중에 볼 표시를 남깁니다. 다른 문항으로 이동하지 않습니다.')
        self.flag_btn.setVisible(not done)
        self.run_btn.setVisible(not done and self.item['kind'] == 'code')
        self.previous_btn.show()
        self.lesson_results.setVisible(done)
        self.result_types.setVisible(done)
        self.show_summary(done)
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
            summary_key = (self.exam.id, summary['try'], tuple(summary['results'].items()))
            ungraded = sum(result == 'ungraded' for result in summary['results'].values())
            if self.summary_key != summary_key:
                kinds = {kind: [0, 0, 0] for kind, _, _ in TYPES}
                for cid, result in summary['results'].items():
                    counts = kinds[self.exam.items[cid]['kind']]
                    counts[0] += result == 'pass'
                    counts[1] += 1
                    counts[2] += result == 'ungraded'
                cells = []
                for kind, name, _ in TYPES:
                    right, total, missed = kinds[kind]
                    if total:
                        cells.append((name, '%d / %d 맞음' % (right, total), '채점하지 못한 문항 %d개' % missed if missed else '', round(100 * right / total)))
                self.result_types.fill(cells)
                entries = self.exam.sess.mock_lessons if self.exam.mixed else self.win.ai.lessons
                missed = {}
                for cid, result in summary['results'].items():
                    lesson = self.exam.items[cid].get('lesson', '')
                    missed[lesson] = missed.get(lesson, 0) + (result == 'ungraded')
                rows = sorted(((lesson_parts(entries, lid), counts, missed.get(lid, 0)) for lid, counts in summary['lessons'].items()),
                              key=lambda row: row[0][3])
                self.lesson_results.fill([(prefix, name, title, '%d / %d' % (counts['correct'], counts['total']),
                                           round(100 * counts['correct'] / counts['total']), counts['correct'] == 0 and counts['total'] > skipped)
                                          for (prefix, name, title, _), counts, skipped in rows])
                self.summary_key = summary_key
            self.auto_note.setText('시간이 끝나 자동으로 제출했습니다.' if summary['auto'] else '')
            self.auto_note.setVisible(bool(summary['auto']))
            self.score_num.setText('%d' % summary['score'])
            self.score_of.setText('/ %d문항 맞음' % summary['of'])
            self.score_time.setText('· 걸린 시간 %d분 %d초' % (summary['secs'] // 60, summary['secs'] % 60))
            self.first_score.set_value('%d / %d' % (summary['first_score'], summary['of']))
            self.heading.setText('틀리거나 비운 문항은 첫 풀이 결과를 기준으로 다음 날부터 복습합니다.')
            if not self.exam.local_answers:
                self.heading.setText(self.heading.text() + '\n이 기기에 저장된 답안이 없어 내 답은 표시하지 않습니다.')
            if ungraded:
                self.heading.setText(self.heading.text() + '\n이 기기에서 코드를 실행하지 못해 채점하지 못한 문항이 %d개 있습니다. '
                                     '이 문항은 전체 문항 수에는 들어가지만 맞은 문항으로 세지 않고 복습에도 넣지 않습니다.' % ungraded)
        else:
            answered = sum(row['answered'] for row in self.exam.progress())
            self.heading.setText('%d / %d문항 답함 · 답은 자동으로 저장됩니다.\n제출한 뒤 정답과 해설을 확인할 수 있습니다.' % (answered, len(self.exam.items)))

    def summary_text(self):
        """요약 카드에 보이는 글 전체. 맞은 수 줄은 한 줄로 잇고 나머지는 줄을 바꿔 이음."""
        lines = [self.auto_note.text()] if not self.auto_note.isHidden() else []
        if not self.score_row.isHidden():
            lines.append(' '.join(label.text() for label in (self.score_num, self.score_of, self.score_time)))
        if not self.first_score.isHidden():
            lines.append(self.first_score.text())
        return '\n'.join(lines + [self.heading.text()])

    def show_summary(self, done):
        """제출 뒤에는 요약 카드를 최소 128 로 두고 맞은 수 줄·처음 점수를 따로 보이며 안내 글을 label ink 로 보임.
        그 밖에는 최소 높이 없이 heading 하나를 body secondary 로 둠."""
        if not done:
            self.auto_note.hide()
        self.score_row.setVisible(done)
        self.first_score.setVisible(done)
        role = 'label' if done else 'body'
        if self.heading.property('role') != role:
            kit.typed(self.heading, role)
            self.heading.line = theme.TYPE[role][1]
            self.heading.setText(self.heading.text())
            kit.set_tone(self.heading, '' if done else 'secondary')
        self.summary.setMinimumHeight(SUMMARY_LEAST if done else 0)

    def size_chips(self):
        """번호 칸을 모두 같은 폭으로 둠. 가장 큰 번호에 상태 기호를 하나씩 붙인 글을 고른 칸과 고르지 않은 칸 양쪽으로 재서
        그중 가장 넓은 폭을 씀. 고른 칸은 굵은 글자라 보통 그쪽이 가장 넓음.
        그래서 답하거나 표시를 달거나 제출해도 칸 폭과 줄 수가 바뀌지 않음."""
        if not self.nav:
            return
        probe, text, checked = self.nav[-1], self.nav[-1].text(), self.nav[-1].isChecked()
        probe.setMinimumWidth(0)
        probe.setMaximumWidth(16777215)
        widest = 0
        marks = ['', ' ★', ' ✓'] + [' ' + mark for mark in ai_text.RESULT_MARK.values()]
        for state in (False, True):
            probe.setChecked(state)
            kit.repolish(probe)
            for mark in marks:
                probe.setText(str(len(self.nav)) + mark)
                widest = max(widest, probe.sizeHint().width())
        probe.setText(text)
        probe.setChecked(checked)
        kit.repolish(probe)
        for button in self.nav:
            button.setFixedWidth(widest)

    def show_grid(self, opened):
        focus = QApplication.focusWidget()
        if not opened and focus is not None and self.grid.isAncestorOf(focus):
            self.grid_toggle.setFocus(Qt.FocusReason.OtherFocusReason)
        self.grid.setVisible(opened)

    def pick_grid(self):
        self.fold_auto = False

    def fit_grid(self):
        """학습자가 고르지 않았으면 펼친 번호 칸 묶음의 높이가 스크롤 영역 높이의 1/3 이하면 펼치고 넘으면 접음.
        폭은 스크롤 영역 폭에서 세로 스크롤 막대 폭을 미리 빼서 셈. 그래서 막대가 생기거나 없어져도 값이 바뀌지 않음.
        묶음 높이는 한 줄에 들어가는 칸 수로 줄 수를 구해 셈. 새로 만든 칸은 아직 보이기 전이라 FlowLayout 이 높이를 0으로 돌려주기 때문임.
        창이 아직 그려지지 않아 높이가 0이면 미룸."""
        if not self.fold_auto or not self.nav or self.scroll.height() <= 0:
            return
        width = min(self.scroll.width() - 2 * kit.DENSE_MARGIN - self.scroll.verticalScrollBar().sizeHint().width(),
                    self.numbers.parentWidget().maximumWidth())
        if width <= 0:
            return
        gap, chip = self.number_row.spacing(), self.nav[0]
        rows = math.ceil(len(self.nav) / max(1, (width + gap) // (chip.width() + gap)))
        opened = (rows * (chip.sizeHint().height() + gap) - gap) * GRID_SHARE <= self.scroll.height()
        if opened != self.grid_toggle.isChecked():
            self.grid_toggle.setChecked(opened)

    def eventFilter(self, watched, event):
        if watched is self.scroll and event.type() == QEvent.Type.Resize:
            self.fit_grid()
        if watched is self.console and event.type() == QEvent.Type.Resize:
            self.fit_console()
        return super().eventFilter(watched, event)

    def refont(self):
        for widget in (self.lesson_counts, self.lesson_results, self.ready_types, self.result_types):
            widget.refit()
        self.size_chips()
        self.fit_grid()

    def go(self, pos):
        if self.busy or not self.persist():
            return
        try:
            if self.exam.result is None:
                self.exam.move(pos)
                if self.exam.has_code and self.exam.result is None and self.exam.remaining() <= 0:
                    self.expire_code()  # 마감 뒤에는 옮기지 않고 지금 문항에 둠
                    return
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
        self.expire_when_due()

    def confirm_submit(self):
        if not self.persist() or self.busy:
            return
        blank = sum(not row['answered'] for row in self.exam.progress())
        text = '모의고사를 제출하고 결과를 확인합니다.'
        if blank:
            text += '\n답을 채우지 않은 문항이 %d개 있습니다.' % blank
        self.win.ask('모의고사 제출', text, (('계속 풀기', 'cancel'), ('제출', 'submit')),
                     lambda choice: self.submit() if choice == 'submit' else None)

    def submit(self, auto=False):
        if self.busy or not self.persist() or self.grading:
            return
        if self.exam.has_code:  # 숨은 테스트를 실행하는 몇 초 동안 화면이 멈추지 않게 작업 스레드에서 채점함
            exam = self.exam

            def grade():  # MockError 는 창의 알림 대화 상자 대신 다른 회차처럼 문항 위 띠에 보임
                try:
                    exam.submit(auto=auto)
                except MockError as error:
                    return error
            if not self.win.run_job(GRADING, grade, lambda error: self.submitted(exam, error)):
                self.wait_note()
            return
        try:
            self.exam.submit(auto=auto)
            self.notice.hide()  # 답을 바꾸지 않고 제출하면 persist 가 띠를 숨기지 않으므로 앞선 오류 띠를 여기서 숨김
            self.win.auto_submission.request()
            self.show_question(self.item['at'] - 1)
        except MockError as error:
            self.fail(error)

    def submitted(self, exam, error=None):
        if self.exam is not exam:
            return
        if error is not None:
            self.fail(error)
        else:
            self.notice.hide()  # 앞선 실행 환경 실패 띠가 결과 화면에 남지 않게 함. 마감 채점의 expired 와 같음
            self.win.auto_submission.request()
            self.show_question(self.item['at'] - 1)

    def tick(self):
        if self.busy or self.grading:
            return
        if self.exam is not None and self.exam.result is None and self.exam.remaining() <= 1 and self.dirty:
            self.persist()
        if getattr(self.win, 'ai', None) is not None:
            self.win.ai.expire_mocks(code=False)
            if self.win.ai.expired_code_mocks:
                self.expire_code()
        if self.exam is None:
            return
        if self.exam.result is not None:
            if not self.showing_result and self.item is not None:
                self.notice.hide()  # expire_mocks 가 제출한 회차에서도 앞선 오류 띠가 결과 화면에 남지 않게 함
                self.win.auto_submission.request()
                self.show_question(self.item['at'] - 1)
                return
            self.set_clock_role('label')
            self.time.setText('제출 완료')
            self.clock_caption.hide()  # '남은 시간 제출 완료' 로 읽히지 않게 함
            return
        seconds = self.exam.remaining()
        self.clock_caption.show()
        self.set_clock_role('display')
        self.time.setText('%02d:%02d' % divmod(seconds, 60))
        kit.set_tone(self.time, 'danger' if seconds <= 60 else ('warning' if seconds <= 600 else ''))
        if seconds == 0 and not self.exam.has_code:
            self.submit(auto=True)

    def set_clock_role(self, role):
        """시계 숫자 글자. 시험 중에는 display, 제출한 뒤 '제출 완료' 는 label 굵게. 최소 폭은 그 글꼴의 '88:88' 폭으로 다시 잼."""
        if self.time.property('role') == role:
            return
        kit.typed(self.time, role, True if role == 'label' else None)
        if role != 'label':
            self.time.setProperty('bold', None)
        self.time.setMinimumWidth(math.ceil(QFontMetricsF(self.time.font()).horizontalAdvance(self.time.property('measure'))))

    def go_back(self):
        if self.persist() and not self.busy:
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
        self.busy_note.text.setText(text)
        self.busy_note.setVisible(busy and bool(text))
        for widget in (self.top.back, self.flag_btn, self.run_btn, self.submit_btn, self.retry_btn, self.numbers, self.card, self.start_btn, self.notes_btn, self.home_btn, self.top_submit):
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
        if self.console is not None:  # 스타일은 다음에 넣는 HTML 부터 적용되므로 결과를 다시 넣음
            self.show_console(self.console.html)
        for widget in self.findChildren(kit.Chevron):
            widget.update()
