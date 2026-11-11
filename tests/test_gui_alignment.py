"""글자와 표시의 실제 배치, 입력 상태가 바뀐 뒤의 높이를 확인함."""
import unittest

from tests import guikit
from gui import kit, theme
from gui.ai_learn import OptionRow
from gui.widgets import CodePanel
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFontMetricsF, QPalette
from PyQt6.QtWidgets import QLineEdit, QWidget


def first_ink_center(label):
    """투명한 배경을 제외하고 실제로 그린 첫 글줄의 위아래 끝을 읽음."""
    image = label.grab().toImage()
    color = label.palette().color(QPalette.ColorRole.WindowText)
    rows = []
    for y in range(image.height()):
        count = 0
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() >= 128 and max(abs(pixel.red() - color.red()), abs(pixel.green() - color.green()),
                                             abs(pixel.blue() - color.blue())) < 50:
                count += 1
        if count >= 3:
            if rows and y - rows[-1] > 3:
                break
            rows.append(y)
    if not rows:
        raise AssertionError("첫 글줄을 찾지 못했음")
    return (rows[0] + rows[-1]) / (2 * image.devicePixelRatio())


class AlignmentTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.root = kit.page(QWidget())
        self.box = kit.box(self.root, (24, 24, 24, 24), 24)
        self.addCleanup(self.root.close)

    def show(self, width=680, height=900):
        self.box.addStretch(1)
        self.root.resize(width, height)
        self.root.show()
        self.root.activateWindow()
        guikit.pump()

    def test_flow_centers_mixed_heights_in_each_wrapped_line(self):
        host = QWidget()
        flow = kit.FlowLayout(host, 12)
        label = kit.label("그림 넘기기", "caption")
        button = kit.button("다음 장", "secondary", "m")
        other = kit.button("처음으로 돌아가기", "secondary", "l")
        for widget in (label, button, other):
            flow.addWidget(widget)
        self.box.addWidget(host)
        self.show()
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(self.root)
            for width in (680, 310):
                self.root.resize(width, 900)
                guikit.pump()
                self.assertLessEqual(abs(label.geometry().center().y() - button.geometry().center().y()), 1)
                self.assertLessEqual(other.geometry().bottom(), host.height())
                self.assertEqual(flow.heightForWidth(host.width()), host.height())
        other.hide()
        guikit.pump()
        self.assertLessEqual(abs(label.geometry().center().y() - button.geometry().center().y()), 1)

    def test_bottom_bar_centers_a_caption_with_its_main_action(self):
        bar = kit.BottomBar()
        note = bar.add_tool(kit.label("저장했습니다", "caption"))
        action = bar.add_action(kit.button("다음 문제", "primary", "l"))
        self.box.addWidget(bar)
        self.show()
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(self.root)
            guikit.pump()
            one = note.mapTo(bar, QPoint()).y() + note.height() / 2
            two = action.mapTo(bar, QPoint()).y() + action.height() / 2
            self.assertLessEqual(abs(one - two), 1)

    def test_check_note_and_radio_follow_the_painted_first_line(self):
        short = kit.Check("문제를 풀고 결과를 확인합니다.", tag="필수", note="약 5분")
        long = kit.Check("문제를 풀고 결과를 확인합니다. " * 6, note="약 5분")
        radio = OptionRow("파라미터를 갱신합니다. " * 5)
        for widget in (short, long, radio):
            self.box.addWidget(widget)
        self.show()
        for scheme in ("light", "dark"):
            theme.set_mode(scheme)
            for step in theme.TEXT_STEPS:
                theme.set_text(step)
                kit.refont(self.root)
                guikit.pump()
                for widget in (short, long, radio):
                    text = widget.label.mapTo(self.root, QPoint()).y() + first_ink_center(widget.label)
                    mark = widget.box.mapTo(self.root, QPoint()).y() + widget.box.height() / 2
                    self.assertLessEqual(abs(mark - text), 1.5, (scheme, step))
                    if widget.note.isVisible():
                        note = widget.note.mapTo(self.root, QPoint()).y() + first_ink_center(widget.note)
                        self.assertLessEqual(abs(note - text), 1.5, (scheme, step))

    def test_mixed_fonts_keep_the_same_text_baseline_after_refont(self):
        number = kit.label("12", "display")
        caption = kit.label("완료한 단계", "caption")
        row = kit.box(None, spacing=12, horizontal=True)
        for label in (number, caption):
            row.addWidget(label, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        kit.baseline(number, caption)
        self.box.addLayout(row)
        self.show()
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(self.root)
            guikit.pump()
            baselines = []
            for label in (number, caption):
                rect = label.contentsRect()
                metrics = QFontMetricsF(label.font())
                top = label.mapTo(self.root, rect.topLeft()).y()
                baselines.append(top + (rect.height() - metrics.height()) / 2 + metrics.ascent())
            self.assertLessEqual(abs(baselines[0] - baselines[1]), 1)

    def test_input_focus_and_verdicts_keep_the_outer_height(self):
        fields = []
        for slot, learning in ((False, False), (True, False), (True, True)):
            field = kit.typed(QLineEdit("값"), "learn_body")
            if slot:
                field.setProperty("slot", True)
            if learning:
                field.setProperty("learning", True)
            self.box.addWidget(field)
            fields.append(field)
        away = kit.button("다음", "secondary", "l")
        self.box.addWidget(away)
        self.show()
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(self.root)
            for field in fields:
                kit.set_tone(field, "")
                away.setFocus()
                guikit.pump()
                expected = theme.learning_slot_height() if field.property("learning") else (
                    theme.slot_height() if field.property("slot") else theme.CONTROL["field"])
                self.assertEqual(field.height(), expected)
                field.setFocus()
                guikit.pump()
                self.assertTrue(field.hasFocus())
                self.assertEqual(field.height(), expected)
                for tone in ("success", "danger", ""):
                    kit.set_tone(field, tone)
                    guikit.pump()
                    self.assertEqual(field.height(), expected, (step, tone, field.property("slot")))

    def test_code_reset_button_fits_below_its_wrapped_hint(self):
        panel = CodePanel()
        panel.set_item({"type": "fill", "answer": "____('Hello')"})
        self.box.addWidget(panel)
        self.show(273, 600)
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(self.root)
            guikit.pump()
            button = panel.reset_btn
            self.assertGreater(button.y(), panel.hint.geometry().bottom())
            self.assertGreaterEqual(button.width(), button.sizeHint().width())
            self.assertTrue(panel.rect().contains(button.geometry()))
