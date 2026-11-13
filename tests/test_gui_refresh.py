# -*- coding: utf-8 -*-
"""허브의 좁은 창, 줄바꿈, 키보드 초점과 공통 하단 막대를 검사함. 설정과 기록은 임시 폴더에만 남김."""
import unittest

from tests import guikit, test_gui_hub
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton, QScrollArea, QWidget

from gui import kit, theme

LONG_TITLE = "학습과 평가에서 기울기 계산과 모델 상태를 나누어 확인하는 연습"
LONG_LINE = "단원 21개 중 12개 숙달 · 다음은 문자열을 나누고 조건에 따라 결과를 모아 출력하는 문제입니다."


def bounds(widget, parent):
    return widget.rect().translated(widget.mapTo(parent, QPoint(0, 0)))


class HubLayoutTest(test_gui_hub.HubTest):
    def test_header_controls_fit_all_text_steps_and_both_themes(self):
        win = self.boot()
        hub = win.hub
        guikit.click(hub.settings_btn)
        self.addCleanup(theme.set_mode, theme.state["mode"])
        for step in theme.TEXT_STEPS:
            win.set_text(step)
            hub.user.setText("ID: a-long-study-account-name-with-39-letters")
            hub.restyle()
            for width in (1280, 1024, 800):
                win.resize(width, 700)
                for mode in ("light", "dark"):
                    with self.subTest(step=step, width=width, mode=mode):
                        theme.set_mode(mode)
                        guikit.pump()
                        self.assertEqual(win.width(), width)
                        self.assertLessEqual(win.minimumSizeHint().height(), 480)
                        controls = [*hub.text_buttons.values(), *hub.theme_buttons.values()]
                        for button in controls:
                            self.assertTrue(hub.settings_panel.rect().contains(bounds(button, hub.settings_panel)), button.text())
                            self.assertGreaterEqual(button.width(), button.sizeHint().width(), button.text())
                            self.assertGreaterEqual(button.height(), theme.control_height("s"))
                        for left, right in zip(controls, controls[1:]):
                            self.assertFalse(bounds(left, hub).intersects(bounds(right, hub)))
                        self.assertTrue(hub.top.identity.rect().contains(bounds(hub.user, hub.top.identity)))
                        self.assertGreaterEqual(hub.user.width(), min(hub.user.sizeHint().width(), hub.user.maximumWidth()))
                        self.assertFalse(bounds(hub.top.identity, hub.top).intersects(bounds(hub.top.controls, hub.top)))
                        self.assertIn("39-letters", hub.user.toolTip())
                        scroll = hub.findChild(QScrollArea)
                        scroll.verticalScrollBar().setValue(0)
                        guikit.pump()
                        self.assertTrue(win.rect().contains(bounds(hub.next_btn, win)))

    def test_track_descriptions_wrap_and_shrink_after_shorter_text(self):
        win = self.boot()
        win.resize(800, 700)
        row = win.hub.python_row
        for step in theme.TEXT_STEPS:
            with self.subTest(step=step):
                win.set_text(step)
                row.set_second(LONG_LINE * 2)
                guikit.pump()
                tall = row.height()
                self.assertGreater(row.second.height(), theme.TYPE["caption"][1])
                for label in (row.title, row.second):
                    self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
                    self.assertTrue(row.rect().contains(bounds(label, row)))
                self.assertFalse(bounds(row.title, row).intersects(bounds(row.second, row)))
                row.set_second("다음은 문자열 연습입니다.")
                guikit.pump()
                self.assertLess(row.height(), tall)
                self.assertEqual(row.second.text(), "다음은 문자열 연습입니다.")

    def test_tab_focus_reaches_tracks_and_space_opens_the_track(self):
        win = self.boot()
        win.resize(800, 700)
        hub = win.hub
        win.activateWindow()
        hub.next_btn.setFocus(Qt.FocusReason.TabFocusReason)
        guikit.pump()
        self.assertTrue(hub.next_btn.hasFocus())
        QTest.keyClick(hub.next_btn, Qt.Key.Key_Tab)
        guikit.pump()
        self.assertTrue(hub.python_row.hasFocus())
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            guikit.pump()
            image = hub.python_row.grab().toImage()
            self.assertTrue(guikit.near(image.pixelColor(image.width() // 2, 1), "focus"))
        QTest.keyClick(hub.python_row, Qt.Key.Key_Space)
        self.idle()
        self.assertIs(self.page(), win.home)


class CommonLayoutTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.root = kit.page(QWidget())
        self.addCleanup(self.root.deleteLater)
        self.addCleanup(self.root.close)
        self.layout = kit.box(self.root)

    def show(self, width=800):
        self.root.resize(width, 550)
        self.root.show()
        guikit.pump()

    def test_long_next_card_keeps_text_and_action_separate(self):
        card = kit.NextCard()
        card.set_item(LONG_TITLE, LONG_LINE, "이어서 학습")
        self.layout.addWidget(card)
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(self.root)
            for width in (800, 1280, 800):
                with self.subTest(step=step, width=width):
                    self.show(width)
                    for widget in (card.title, card.line, card.button):
                        self.assertTrue(card.rect().contains(bounds(widget, card)))
                    for label in (card.title, card.line):
                        self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
                        self.assertFalse(bounds(label, card).intersects(bounds(card.button, card)))
                    self.assertEqual(kit.visible_primary_buttons(self.root), [card.button])

    def test_bottom_tools_wrap_and_hidden_tools_release_their_space(self):
        self.layout.addStretch(1)
        bar = kit.BottomBar()
        tools = [bar.add_tool(kit.button(name, "text", "l"))
                 for name in ("이 단계 건너뛰기", "폴더 열기", "안내 다시 보기")]
        actions = [bar.add_action(kit.button("설명 끝내기", "secondary", "l")),
                   bar.add_action(kit.button("검사하기", "primary", "l"))]
        self.layout.addWidget(bar)
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(self.root)
            for width in (800, 1024, 1280, 800):
                with self.subTest(step=step, width=width):
                    self.show(width)
                    self.assertEqual(self.root.width(), width)
                    for widget in tools + actions:
                        self.assertTrue(bar.rect().contains(bounds(widget, bar)), widget.text())
                        self.assertGreaterEqual(widget.width(), widget.sizeHint().width())
                    for index, widget in enumerate(tools + actions):
                        for other in (tools + actions)[index + 1:]:
                            self.assertFalse(bounds(widget, bar).intersects(bounds(other, bar)))
                    self.assertEqual(bounds(actions[-1], self.root).right() + 1, width - kit.MARGIN)
        for tool in tools:
            tool.hide()
        guikit.pump()
        self.assertEqual(bar.height(), theme.CONTROL["bottombar"])

    def test_fixed_width_status_does_not_cover_the_run_button(self):
        bar = kit.BottomBar()
        status = kit.ElideLabel("예시 실행을 마쳤습니다.", "caption")
        status.setFixedWidth(160)
        bar.add_tool(status)
        run = bar.add_tool(kit.button("코드 실행", "text", "l"))
        action = bar.add_action(kit.button("회차 제출", "primary", "l"))
        self.layout.addWidget(bar)
        for step in theme.TEXT_STEPS:
            theme.set_text(step)
            kit.refont(self.root)
            for mode in ("light", "dark"):
                theme.set_mode(mode)
                for width in (800, 1440):
                    with self.subTest(step=step, mode=mode, width=width):
                        self.show(width)
                        for widget in (status, run, action):
                            self.assertTrue(bar.rect().contains(bounds(widget, bar)))
                        self.assertFalse(bounds(status, bar).intersects(bounds(run, bar)))
                        self.assertFalse(bounds(run, bar).intersects(bounds(action, bar)))

    def test_button_focus_changes_the_border_in_both_themes(self):
        for kind in ("primary", "secondary", "text"):
            button = kit.button("계속하기", kind, "l")
            self.layout.addWidget(button)
        self.show()
        self.root.activateWindow()
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            guikit.pump()
            for button in self.root.findChildren(QPushButton):
                button.clearFocus()
                guikit.pump()
                before = button.grab().toImage()
                button.setFocus(Qt.FocusReason.TabFocusReason)
                guikit.pump()
                self.assertTrue(button.hasFocus())
                after = button.grab().toImage()
                token = "surface" if button.objectName() == "primary" else "focus"
                changed = sum(before.pixel(x, 1) != after.pixel(x, 1) and guikit.near(after.pixelColor(x, 1), token)
                              for x in range(16, after.width() - 16))
                self.assertGreater(changed, 10, (mode, button.objectName()))


if __name__ == "__main__":
    unittest.main()
