# -*- coding: utf-8 -*-
"""공통 동작 줄의 줄바꿈·숨김·글자 변경과 기존 키보드 순서를 확인함."""
import unittest

from tests import guikit
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QBoxLayout, QDialog, QWidget

from gui import kit, theme
from gui.action_layout import ActionLayout
from gui.dialog_layout import ActionLayout as DialogActionLayout, DialogLayout


def bounds(widget, parent):
    return widget.rect().translated(widget.mapTo(parent, QPoint(0, 0)))


class ActionLayoutTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.root = kit.page(QWidget())
        self.addCleanup(self.root.deleteLater)
        self.addCleanup(self.root.close)
        self.outer = kit.box(self.root)

    def show(self, width=760):
        self.root.resize(width, 650)
        self.root.show()
        self.root.activateWindow()
        guikit.pump()
        self.assertEqual(self.root.width(), width)

    def assert_visible_fit(self, container, buttons):
        visible = [button for button in buttons if button.isVisibleTo(container)]
        for index, button in enumerate(visible):
            self.assertTrue(container.rect().contains(bounds(button, container)), button.text())
            self.assertTrue(self.root.rect().contains(bounds(button, self.root)), button.text())
            hint = button.sizeHint().expandedTo(button.minimumSizeHint()).expandedTo(button.minimumSize())
            self.assertGreaterEqual(button.width(), hint.width(), button.text())
            self.assertGreaterEqual(button.height(), hint.height(), button.text())
            for other in visible[index + 1:]:
                self.assertFalse(bounds(button, container).intersects(bounds(other, container)))

    def test_dialog_keeps_primary_first_and_hidden_actions_release_space(self):
        self.assertIs(DialogActionLayout, ActionLayout)
        theme.set_text("larger")
        self.show()
        dialog = QDialog(self.root)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        shell = DialogLayout(dialog, "변경한 풀이 확인")
        shell.content.addWidget(kit.para("보낼 파일을 확인한 뒤 선택합니다."))
        help_button = kit.button("자세한 안내", "text")
        buttons = [kit.button(text, "primary" if n == 2 else "secondary", "l")
                   for n, text in enumerate(("지금 화면에서 계속 공부하기", "파일 목록을 다시 확인하기", "확인한 풀이를 서버로 제출하기"))]
        shell.actions.set_actions([help_button], buttons)
        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                theme.set_mode(mode)
                shell.fit(728)
                dialog.show()
                guikit.pump()
                self.assertEqual(shell.actions.sizeHint(), shell.actions.minimumSize())
                self.assertLess(buttons[2].y(), buttons[1].y())
                self.assertLess(buttons[1].y(), buttons[0].y())
                for button in [help_button, *buttons]:
                    self.assertTrue(shell.footer.rect().contains(bounds(button, shell.footer)))
                    self.assertGreaterEqual(button.width(), button.sizeHint().width())
                    self.assertTrue(dialog.rect().contains(bounds(button, dialog)))
        old_height = shell.actions.heightForWidth(shell.footer.width())
        buttons[1].hide()
        buttons[0].setEnabled(False)
        guikit.pump()
        self.assertLess(shell.actions.heightForWidth(shell.footer.width()), old_height)
        self.assertFalse(buttons[0].isEnabled())
        self.assertTrue(buttons[1].isHidden())

    def test_natural_width_uses_visible_minimums_margins_and_spacing(self):
        footer = QWidget()
        self.outer.addWidget(footer)
        layout = ActionLayout(footer, margins=(11, 7, 13, 9), spacing=8, reverse_stacked=False)
        first, second = kit.button("저장"), kit.button("이어서 공부하기")
        first.setMinimumWidth(180)
        layout.addWidget(first)
        layout.addSpacing(16)
        layout.addWidget(second)
        self.show()
        self.assertEqual(layout.left_count, 0)
        expected = first.sizeHint().expandedTo(first.minimumSize()).width() + second.sizeHint().width() + 16 + 8 + 24
        self.assertEqual(layout.natural_width(), expected)
        self.assertEqual(second.x() - first.geometry().right() - 1, 24)
        before = layout.natural_width()
        theme.set_text("larger")
        kit.refont(self.root)
        guikit.pump()
        self.assertGreater(layout.natural_width(), before)
        policy = second.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        second.setSizePolicy(policy)
        second.hide()
        guikit.pump()
        self.assertEqual(layout.natural_width(), first.sizeHint().expandedTo(first.minimumSize()).width() + 24)
        first.hide()
        guikit.pump()
        self.assertEqual(layout.natural_width(), 24)
        self.assertEqual(layout.heightForWidth(760), 16)

    def test_bottom_actions_keep_order_focus_signals_and_external_spacing(self):
        theme.set_text("larger")
        self.outer.addStretch(1)
        bar = kit.BottomBar()
        self.outer.addWidget(bar)
        buttons = []
        for n, text in enumerate(("이전 문제로 돌아가기", "다음 문제로 이동하기", "풀이 파일 다시 확인하기", "이 회차의 풀이 제출하기")):
            if n == 2:
                bar.action_row.addSpacing(16)
            buttons.append(bar.add_action(kit.button(text, "primary" if n == 3 else "secondary", "l")))
        clicked = []
        buttons[-1].clicked.connect(lambda: clicked.append(True))
        self.assertIsInstance(bar.row, QBoxLayout)
        self.assertIsInstance(bar.action_row, ActionLayout)
        self.assertEqual(bar.action_row.left_count, 0)
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for width in (760, 1800, 760):
                with self.subTest(mode=mode, width=width):
                    self.show(width)
                    self.assert_visible_fit(bar, buttons)
                    if width == 760:
                        self.assertEqual([button.y() for button in buttons], sorted(button.y() for button in buttons))
                        self.assertEqual(len({button.y() for button in buttons}), 4)
                    else:
                        self.assertEqual(len({button.y() for button in buttons}), 1)
                    buttons[1].setFocus(Qt.FocusReason.TabFocusReason)
                    bar.arrange()
                    guikit.pump()
                    self.assertIs(self.root.focusWidget(), buttons[1])
        buttons[0].setFocus(Qt.FocusReason.TabFocusReason)
        for expected in buttons[1:]:
            QTest.keyClick(self.root.focusWidget(), Qt.Key.Key_Tab)
            self.assertIs(self.root.focusWidget(), expected)
        QTest.keyClick(buttons[-1], Qt.Key.Key_Space)
        self.assertEqual(clicked, [True])
        self.assertIs(bar.action_row.itemAt(0).widget(), buttons[0])
        self.assertIsNotNone(bar.action_row.itemAt(2).spacerItem())

    def test_bottom_reflows_after_hide_show_text_and_font_changes(self):
        self.outer.addStretch(1)
        bar = kit.BottomBar()
        self.outer.addWidget(bar)
        tools = [bar.add_tool(kit.button(text, "text", "l")) for text in ("노트에서 개념 확인하기", "이 문제는 모르겠어요")]
        buttons = [bar.add_action(kit.button(text, "secondary", "l"))
                   for text in ("이전 문제로 돌아가기", "다음 문제로 이동하기", "답안을 확인하고 제출하기")]
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for step in ("normal", "larger", "normal"):
                theme.set_text(step)
                kit.refont(self.root)
                self.show()
                self.assert_visible_fit(bar, tools + buttons)
        full_height = bar.height()
        for widget in tools + buttons[:-1]:
            widget.hide()
        buttons[-1].setText("제출")
        buttons[-1].setEnabled(False)
        guikit.pump()
        self.assertEqual(bar.height(), theme.CONTROL["bottombar"])
        self.assertLess(bar.height(), full_height)
        for widget in tools + buttons[:-1]:
            widget.show()
        buttons[-1].setText("답안을 확인하고 제출하기")
        theme.set_text("larger")
        kit.refont(self.root)
        guikit.pump()
        self.assert_visible_fit(bar, tools + buttons)
        self.assertGreater(bar.height(), theme.CONTROL["bottombar"])
        self.assertFalse(buttons[-1].isEnabled())

    def test_bottom_height_matches_allocated_action_width_with_tools(self):
        theme.set_text("larger")
        self.outer.addStretch(1)
        bar = kit.BottomBar()
        self.outer.addWidget(bar)
        status = bar.add_tool(kit.ElideLabel("풀이 파일을 확인했습니다.", "caption"))
        status.setFixedWidth(280)
        tool = bar.add_tool(kit.button("파일 목록 다시 보기", "text", "l"))
        buttons = [bar.add_action(kit.button(text, "secondary", "l"))
                   for text in ("이전 문제로", "다음 문제로", "풀이 제출하기", "프로그램 업데이트")]
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            self.show(1280)
            left, _, right, _ = bar.row.getContentsMargins()
            tool_width = status.width() + tool.sizeHint().width() + bar.tools.spacing()
            boundary = left + right + tool_width + theme.GAP["group"] + bar.action_row.natural_width()
            for width in (760, 960, 1280, boundary - 1, boundary, boundary + 1, 960):
                with self.subTest(mode=mode, width=width):
                    self.show(width)
                    self.assert_visible_fit(bar, buttons + [tool])
                    self.assertTrue(bar.rect().contains(bounds(status, bar)))
                    required = bar.action_row.heightForWidth(bar.actions.width())
                    self.assertEqual(bar.actions.height(), required)
                    self.assertGreaterEqual(bar.tool_box.height(), bar.tools.heightForWidth(bar.tool_box.width()))
                    for button in buttons:
                        self.assertTrue(bar.actions.rect().contains(bounds(button, bar.actions)))
                    if width == boundary:
                        self.assertEqual(bar.row.direction(), QBoxLayout.Direction.LeftToRight)
                        self.assertEqual(bar.actions.width(), bar.action_row.natural_width())
                    if width == boundary - 1:
                        self.assertEqual(bar.row.direction(), QBoxLayout.Direction.TopToBottom)
