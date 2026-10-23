# -*- coding: utf-8 -*-
"""여행 문제의 [테스트 추가] 대화상자. 줄마다 인자와 기댓값을 적음. 칸마다 values.parse_literal 과 values.check 로
바로 검사함. 틀린 칸은 빨간 테두리를 두르고 칸 묶음 아래에 그 까닭을 한 줄로 보임. 쓴 값은 지우지 않음.
[저장]은 부른 쪽이 넘긴 save(cases) 로 저장함. 서비스가 한 번 더 검사함. 틀린 칸이 있으면 그 칸으로 초점을 옮기고 저장하지 않음.
부모가 문제 화면이라도 창 자신에 새 규칙 범위를 걸어 문제 화면이 어느 모양이든 같은 모양으로 보임.
창 전체의 복사·붙여넣기 막기(gui/guard.py)는 메인 창에만 걸리므로 이 대화상자에서는 큰 입력도 붙여넣을 수 있음."""
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QMenu, QScrollArea, QVBoxLayout, QWidget

from gui import kit, theme
from journey import values
from session import SessionError

MAX_CASES = 20
TITLE = "테스트 추가"  # 창 제목과 안 제목. 문제 화면에서 여는 단추 이름과 같음
HINT = '값은 파이썬이나 JSON 문법으로 적으세요. 예: ["a", "b"], 3, True'
SIZE = (760, 520)


class CasesDialog(QDialog):
    """problem 은 서비스의 problem() 결과(signature, examples, cases). lang 은 값을 보여 줄 언어 표기.
    save(cases) 는 정리된 목록을 돌려주거나 SessionError 를 냄. 저장하면 on_saved(목록)을 부름.
    단추는 [닫기]와 주 단추 [저장]이고 기본 단추가 없어 입력칸에서 Enter 를 눌러도 저장하지 않음."""

    def __init__(self, parent, problem, lang, save, on_saved=None):
        super().__init__(parent)
        kit.page(self)
        self.setWindowTitle(TITLE)
        self.setModal(True)
        self.resize(*SIZE)
        self.lang, self.save_fn, self.on_saved = lang, save, on_saved
        self.params = problem["signature"]["params"]
        self.returns = problem["signature"]["returns"]
        self.examples = problem["examples"]
        self.rows = []  # 줄마다 (입력칸 목록, 삭제 단추)
        self.numbers = []  # 줄 번호 글자
        box = QVBoxLayout(self)
        box.setContentsMargins(32, 32, 32, 24)
        box.setSpacing(0)
        box.addWidget(kit.para(TITLE, "headline"))
        box.addSpacing(4)
        box.addWidget(kit.para(HINT, "caption", "secondary"))
        box.addSpacing(16)

        inner = QWidget()
        self.grid = QGridLayout(inner)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(8)
        names = ["#"] + ["%s (%s)" % (p["name"], p["type"]) for p in self.params] + ["return (%s)" % self.returns]
        for column, name in enumerate(names):
            align = Qt.AlignmentFlag.AlignCenter if not column else None
            self.grid.addWidget(kit.label(name, "caption", "tertiary", align=align), 0, column)
            if column:
                self.grid.setColumnStretch(column, 1)
        self.grid.setRowStretch(MAX_CASES + 1, 1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(inner)
        cells = QVBoxLayout()
        cells.setSpacing(8)  # 오류 줄이 숨으면 이 간격도 같이 빠짐
        cells.addWidget(self.scroll, 1)
        self.error = kit.para("", "caption", "danger")
        self.error.hide()
        cells.addWidget(self.error)
        box.addLayout(cells, 1)
        box.addSpacing(16)

        self.add_btn = kit.button("줄 추가", "text", "m")
        self.add_btn.clicked.connect(lambda: self.add_row())
        self.example_btn = kit.button("예시에서 가져오기", "text", "m")
        self.example_menu = QMenu(self)
        for index in range(len(self.examples)):
            self.example_menu.addAction("입출력 예 %d" % (index + 1), lambda index=index: self.from_example(index))
        self.example_btn.setMenu(self.example_menu)
        close = kit.button("닫기", "secondary", "l")
        close.clicked.connect(self.reject)
        self.save_btn = kit.button("저장", "primary", "l")
        self.save_btn.clicked.connect(self.save)
        row = QHBoxLayout()
        row.setSpacing(8)
        for widget in (self.add_btn, self.example_btn):
            row.addWidget(widget)
            kit.flush_left(row, widget)  # 글자 단추의 글자가 위 제목·칸과 같은 세로선에 옴
        row.addStretch(1)
        for widget in (close, self.save_btn):
            row.addWidget(widget)
        box.addLayout(row)

        for case in problem.get("cases") or []:
            self.add_row(list(case["args"]) + [case["expected"]])
        if not self.rows:
            self.add_row()
        self.check()

    def show_value(self, value):
        """고른 언어의 표기로, 자르지 않고."""
        return values.show(value, self.lang, sys.maxsize)

    def add_row(self, filled=None):
        """줄을 하나 더함. filled 는 인자들과 기댓값의 값 목록. 값은 코드 글이라 문서 코드와 같은 글꼴로 보임."""
        if len(self.rows) >= MAX_CASES:
            return
        edits = []
        for column in range(len(self.params) + 1):
            edit = QLineEdit()
            edit.setFont(theme.code_font(theme.text_px() - 1))
            if filled is not None:
                edit.setText(self.show_value(filled[column]))
            edit.textChanged.connect(self.check)
            edits.append(edit)
        remove = kit.button("삭제", "danger_text", "s")
        remove.clicked.connect(lambda: self.remove_row(next(n for n, (_, btn) in enumerate(self.rows) if btn is remove)))
        self.rows.append((edits, remove))
        self._lay_out()
        edits[0].setFocus()
        self.check()

    def remove_row(self, index):
        edits, remove = self.rows.pop(index)
        for widget in edits + [remove]:
            self.grid.removeWidget(widget)
            widget.deleteLater()
        self._lay_out()
        self.check()

    def from_example(self, index):
        example = self.examples[index]
        self.add_row(list(example["args"]) + [example["expected"]])

    def _lay_out(self):
        """줄 번호를 다시 매기고 줄을 격자에 다시 놓음."""
        for old in self.numbers:
            self.grid.removeWidget(old)
            old.deleteLater()
        self.numbers = []
        for edits, remove in self.rows:
            for widget in edits + [remove]:
                self.grid.removeWidget(widget)
        for number, (edits, remove) in enumerate(self.rows, 1):
            label = kit.label(str(number), "caption", "secondary", align=Qt.AlignmentFlag.AlignCenter)
            self.numbers.append(label)
            self.grid.addWidget(label, number, 0)
            for column, edit in enumerate(edits, 1):
                self.grid.addWidget(edit, number, column)
            self.grid.addWidget(remove, number, len(edits) + 1, Qt.AlignmentFlag.AlignVCenter)
        self.add_btn.setEnabled(len(self.rows) < MAX_CASES)
        self.example_btn.setEnabled(bool(self.examples) and len(self.rows) < MAX_CASES)

    def collect(self):
        """(케이스 목록, 처음 틀린 칸의 문구, 그 칸). 칸이 모두 빈 줄은 건너뜀. 틀린 칸이 없으면 문구는 "" 이고 칸은 None."""
        cases = []
        kinds = [p["type"] for p in self.params] + [self.returns]
        names = [p["name"] for p in self.params] + ["return"]
        for number, (edits, _) in enumerate(self.rows, 1):
            texts = [edit.text() for edit in edits]
            if not any(text.strip() for text in texts):
                continue
            row = []
            for edit, text, kind, name in zip(edits, texts, kinds, names):
                try:
                    value = values.parse_literal(text)
                except ValueError as error:
                    return None, "%d번 줄의 %s 칸: %s" % (number, name, error), edit
                problem = values.check(value, kind)
                if problem:
                    return None, "%d번 줄의 %s 칸: %s" % (number, name, problem), edit
                row.append(value)
            cases.append({"args": row[:-1], "expected": row[-1]})
        return cases, "", None

    def show_error(self, text, wrong=None):
        """칸 묶음 아래 오류 줄과 틀린 칸의 빨간 테두리. text 가 비면 둘 다 거둠."""
        self.error.setText(text)
        self.error.setVisible(bool(text))
        for edits, _ in self.rows:
            for edit in edits:
                kit.set_tone(edit, "danger" if edit is wrong else "")

    def check(self):
        _, problem, wrong = self.collect()
        self.show_error(problem, wrong)
        return not problem

    def save(self):
        cases, problem, wrong = self.collect()
        if problem:
            self.show_error(problem, wrong)
            self.scroll.ensureWidgetVisible(wrong)
            wrong.setFocus()
            return
        try:
            saved = self.save_fn(cases)
        except SessionError as error:
            self.show_error(str(error))
            return
        self.accept()
        if self.on_saved:
            self.on_saved(saved)

    def refont(self):
        """글자 크기 단계가 바뀌면 창의 kit.refont 가 부름. 제목·안내·이름표는 역할 글꼴이라 kit.refont 가 다시 줌. 입력칸의 코드 글꼴만 여기서 다시 줌."""
        for edits, _ in self.rows:
            for edit in edits:
                edit.setFont(theme.code_font(theme.text_px() - 1))
