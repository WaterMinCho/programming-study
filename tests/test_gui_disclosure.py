"""접힌 답의 글자·화살표·줄바꿈과 키보드 동작을 검사함."""
import unittest
from types import SimpleNamespace

from tests import guikit
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget

from gui import ai_learn, kit, theme
from gui.disclosure import DisclosureButton


class DisclosureTest(unittest.TestCase):
    def setUp(self):
        state = dict(theme.state)
        self.addCleanup(theme.set_text, state["text"])
        self.addCleanup(theme.set_mode, state["mode"])
        self.root = kit.page(QWidget())
        self.capture_widget = self.root
        self.addCleanup(self.root.deleteLater)
        self.addCleanup(self.root.close)
        self.column = kit.box(self.root, (32, 24, 32, 24), 24)

    def settle(self):
        previous, stable = None, 0
        for _ in range(80):
            guikit.pump(5)
            current = tuple((w.pos(), w.size()) for w in self.root.findChildren(QWidget) if w.isVisible())
            stable = stable + 1 if current == previous else 0
            if stable >= 3:
                return
            previous = current
        self.fail("접힌 설명의 배치가 안정되지 않았음")

    def test_question_answer_and_wrapped_arrow_align_in_both_themes(self):
        why = ai_learn.WhyBlock({"q": "기울기를 구하기 전에 zero_grad()를 호출하는 이유는 무엇인가요?",
                                "a": "이전 계산에서 남은 기울기를 지워 이번 데이터로 구한 기울기만 사용합니다."},
                               SimpleNamespace(readonly=False))
        memo = ai_learn.MemoBlock([{"q": "학습 데이터의 오차가 줄어도 검증 데이터의 오차가 커지는 이유는 무엇인가요?",
                                   "a": "새로운 데이터에서 모델의 예측 결과를 확인합니다."}])
        content = QWidget()
        body = kit.box(content, spacing=24)
        body.addWidget(why)
        body.addWidget(memo)
        body.addStretch()
        self.column.addWidget(kit.scroll(content))
        self.root.show()
        for step in ("larger", "normal", "larger"):
            theme.set_text(step)
            kit.refont(self.root)
            for mode in ("light", "dark"):
                theme.set_mode(mode)
                for width, height in ((760, 480), (960, 860)):
                    self.root.resize(width, height)
                    for opened in (True, False):
                        why.button.setChecked(opened)
                        memo.rows[0].set_opened(opened)
                        self.settle()
                        question = why.layout().itemAt(1).widget()
                        self.assertEqual(question.mapTo(why, QPoint()).x(), why.button.label.mapTo(why, QPoint()).x())
                        self.assertEqual(why.answer.mapTo(why, QPoint()).x(), question.x())
                        self.assertEqual(why.answer.isHidden(), not opened)
                        for button in (why.button, memo.rows[0]):
                            self.assertGreaterEqual(button.height(), button.heightForWidth(button.width()))
                            self.assertGreaterEqual(button.label.height(), button.label.heightForWidth(button.label.width()))
                            self.assertEqual(button.label.mapTo(button, QPoint()).x(), 0)
                            self.assertEqual(button.arrow.mapTo(button, QPoint()).x() + button.arrow.width(), button.width())
                            self.assertTrue(button.rect().contains(button.arrow.mapTo(button, QPoint())))
                            self.assertAlmostEqual(button.pair.text_center() + button.label.mapTo(button.pair, QPoint()).y(),
                                                   button.arrow.mapTo(button.pair, QPoint()).y() + 10, delta=1)
                            self.assertEqual(button.arrow.opened, opened)
        self.root.resize(760, 480)
        why.button.setChecked(True)
        self.settle()

    def test_keyboard_and_child_clicks_change_state_once_without_moving_header(self):
        button = DisclosureButton("추가 설명과 관련 자료 펼치기", role="learn_caption")
        self.column.addWidget(button)
        self.column.addStretch()
        self.root.resize(340, 480)
        self.root.show()
        self.settle()
        changes = []
        button.toggled.connect(changes.append)
        button.toggled.connect(lambda opened: button.setText("추가 설명과 관련 자료 접기" if opened else "추가 설명과 관련 자료 펼치기"))
        initial = button.geometry()
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            button.setFocus(Qt.FocusReason.TabFocusReason)
            QTest.keyClick(button, key)
            self.settle()
            self.assertEqual(button.geometry(), initial)
            self.assertTrue(button.hasFocus())
        self.assertEqual(changes, [True, False])
        point = button.arrow.mapTo(button, button.arrow.rect().center())
        QTest.mouseClick(button, Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(changes, [True, False, True])
        button.blockSignals(True)
        button.setChecked(False)
        button.blockSignals(False)
        self.assertFalse(button.arrow.opened)

    def test_fold_arrows_keep_existing_shortcuts_and_readonly_answers_stay_open(self):
        row = ai_learn.FoldRow("기울기는 어느 방향을 나타내나요?")
        readonly = ai_learn.WhyBlock({"q": "기울기가 양수면?", "a": "값을 줄입니다."}, SimpleNamespace(readonly=True))
        self.column.addWidget(row)
        self.column.addWidget(readonly)
        self.root.resize(760, 480)
        self.root.show()
        self.settle()
        row.setFocus()
        for modifier in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier):
            for key, opened in ((Qt.Key.Key_Right, True), (Qt.Key.Key_Left, False),
                                (Qt.Key.Key_Enter, True), (Qt.Key.Key_Enter, False)):
                QTest.keyClick(row, key, modifier)
                self.assertEqual(row.opened, opened)
                self.assertTrue(row.hasFocus())
        self.assertTrue(readonly.answer.isVisible())
        self.assertTrue(readonly.button.isHidden())

    def test_rich_question_height_uses_rendered_text(self):
        row = ai_learn.FoldRow("**기울기**와 `zero_grad()`의 관계를 설명해 보세요. " * 3)
        self.column.addWidget(row)
        self.column.addStretch()
        self.root.resize(760, 480)
        self.root.show()
        self.settle()
        self.assertEqual(row.heightForWidth(row.width()), max(48, row.pair.layout().totalHeightForWidth(row.width()) + 24))
