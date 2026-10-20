# -*- coding: utf-8 -*-
"""여정 문제의 [테스트 케이스 추가하기] 대화상자. 줄마다 인자와 기댓값을 적고, 칸마다 values.parse_literal 과 values.check 로
바로 검사함. [저장]은 부른 쪽이 넘긴 save(cases) 로 저장하고(서비스가 한 번 더 검사함), 틀리면 그 문구를 아래에 보여 줌.
창 전체의 복사·붙여넣기 막기(gui/guard.py)는 메인 창에만 걸리므로 이 대화상자에서는 큰 입력도 붙여넣을 수 있음."""
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea, QVBoxLayout,
                             QWidget)

from gui.widgets import Para
from journey import values
from session import SessionError

MAX_CASES = 20
HINT = '값은 JSON 이나 파이썬 문법으로 적습니다. 예) ["a", "b"], 3, true'


class CasesDialog(QDialog):
    """problem 은 서비스의 problem() 결과(signature, examples, cases). lang 은 값을 보여 줄 언어 표기.
    save(cases) 는 정리된 목록을 돌려주거나 SessionError 를 내고, 저장하면 on_saved(목록)을 부름."""

    def __init__(self, parent, problem, lang, save, on_saved=None):
        super().__init__(parent)
        self.setWindowTitle("테스트 케이스 추가")
        self.setModal(True)
        self.resize(760, 460)
        self.lang, self.save_fn, self.on_saved = lang, save, on_saved
        self.params = problem["signature"]["params"]
        self.returns = problem["signature"]["returns"]
        self.examples = problem["examples"]
        self.rows = []  # 줄마다 (입력칸 목록, 삭제 단추)
        self.numbers = []  # 줄 번호 글자
        box = QVBoxLayout(self)
        box.setContentsMargins(22, 20, 22, 16)
        box.setSpacing(10)
        head = QLabel("테스트 케이스 추가")
        head.setObjectName("h2")
        box.addWidget(head)
        box.addWidget(Para(HINT, "muted"))

        inner = QWidget()
        inner.setObjectName("page")
        self.grid = QGridLayout(inner)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(6)
        names = ["#"] + ["%s (%s)" % (p["name"], p["type"]) for p in self.params] + ["return (%s)" % self.returns]
        for column, name in enumerate(names):
            label = QLabel(name)
            label.setObjectName("muted")
            self.grid.addWidget(label, 0, column)
            if column:
                self.grid.setColumnStretch(column, 1)
        self.grid.setRowStretch(MAX_CASES + 1, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        box.addWidget(scroll, 1)

        tools = QHBoxLayout()
        self.add_btn = QPushButton("케이스 추가")
        self.add_btn.clicked.connect(lambda: self.add_row())
        self.example_btn = QPushButton("예시에서 가져오기 ▾")
        self.example_menu = QMenu(self)
        for index in range(len(self.examples)):
            self.example_menu.addAction("입출력 예 %d" % (index + 1), lambda index=index: self.from_example(index))
        self.example_btn.setMenu(self.example_menu)
        self.example_btn.setEnabled(bool(self.examples))
        self.error = Para("", "error")
        tools.addWidget(self.add_btn)
        tools.addWidget(self.example_btn)
        tools.addSpacing(10)
        tools.addWidget(self.error, 1)
        box.addLayout(tools)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("취소")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("저장")
        self.save_btn.setObjectName("primary")
        self.save_btn.setAutoDefault(False)
        self.save_btn.clicked.connect(self.save)
        row.addWidget(cancel)
        row.addWidget(self.save_btn)
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
        """줄을 하나 더함. filled 는 인자들과 기댓값의 값 목록."""
        if len(self.rows) >= MAX_CASES:
            return
        edits = []
        for column in range(len(self.params) + 1):
            edit = QLineEdit()
            if filled is not None:
                edit.setText(self.show_value(filled[column]))
            edit.textChanged.connect(self.check)
            edits.append(edit)
        remove = QPushButton("삭제")
        remove.setObjectName("quiet")
        remove.setAutoDefault(False)
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
            label = QLabel(str(number))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.numbers.append(label)
            self.grid.addWidget(label, number, 0)
            for column, edit in enumerate(edits, 1):
                self.grid.addWidget(edit, number, column)
            self.grid.addWidget(remove, number, len(edits) + 1)
        self.add_btn.setEnabled(len(self.rows) < MAX_CASES)
        self.example_btn.setEnabled(bool(self.examples) and len(self.rows) < MAX_CASES)

    def collect(self):
        """(케이스 목록, 처음 틀린 칸의 문구). 칸이 모두 빈 줄은 건너뜀."""
        cases = []
        kinds = [p["type"] for p in self.params] + [self.returns]
        names = [p["name"] for p in self.params] + ["return"]
        for number, (edits, _) in enumerate(self.rows, 1):
            texts = [edit.text() for edit in edits]
            if not any(text.strip() for text in texts):
                continue
            row = []
            for text, kind, name in zip(texts, kinds, names):
                try:
                    value = values.parse_literal(text)
                except ValueError as error:
                    return None, "%d번 케이스의 %s 칸: %s" % (number, name, error)
                problem = values.check(value, kind)
                if problem:
                    return None, "%d번 케이스의 %s 칸: %s" % (number, name, problem)
                row.append(value)
            cases.append({"args": row[:-1], "expected": row[-1]})
        return cases, ""

    def check(self):
        _, problem = self.collect()
        self.error.setText(problem)
        return not problem

    def save(self):
        cases, problem = self.collect()
        if problem:
            self.error.setText(problem)
            return
        try:
            saved = self.save_fn(cases)
        except SessionError as error:
            self.error.setText(str(error))
            return
        self.accept()
        if self.on_saved:
            self.on_saved(saved)
