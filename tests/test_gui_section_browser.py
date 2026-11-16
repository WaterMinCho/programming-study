"""자료가 늘어나도 분류를 찾고 읽던 목록으로 돌아오는지 확인함."""
from unittest import mock

from tests import guikit
from tests.test_gui_ai import AiTest
from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QAbstractSlider

from gui import theme
from session import SessionError


class AiSectionBrowserTest(AiTest):
    real_bank = True

    def home(self, size=(760, 480)):
        win = self.boot(size)
        win.go_ai()
        self.settle()
        return win, win.ai_home, win.ai_home.browser

    def settle(self):
        home = self.win.ai_home
        browser = home.browser
        previous, stable = None, 0

        def ready():
            nonlocal previous, stable
            buttons = home.course_tabs.buttons + list(browser.buttons.values())
            current = (tuple((button.mapTo(home, QPoint()), button.size()) for button in buttons),
                       home.scroll.viewport().size(),
                       home.scroll.verticalScrollBar().maximum())
            stable = stable + 1 if current == previous else 0
            previous = current
            heights_ready = all(button.height() == button.sizeHint().height() for button in home.course_tabs.buttons)
            return stable >= 3 and heights_ready and browser.pending is None

        guikit.wait_until(ready)

    def test_categories_fit_small_wide_max_text_both_themes_and_remain_visible(self):
        win, home, browser = self.home()
        native = guikit.APP.platformName() != "offscreen"
        room = win.screen().availableGeometry()
        frame_width = win.frameGeometry().width() - win.width()
        frame_height = win.frameGeometry().height() - win.height()
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            for size in ((760, 480), (1600, 1000)):
                width, height = size
                if native:
                    width = min(width, room.width() - frame_width - 32)
                    height = min(height, room.height() - frame_height - 32)
                win.resize(width, height)
                if native:
                    win.move(room.topLeft() + QPoint(16, 16))
                heights = []
                for step in ("larger", "normal", "larger"):
                    win.set_text(step)
                    self.settle()
                    if native:
                        self.assertTrue(room.contains(win.frameGeometry()))
                    courses = home.course_tabs.buttons
                    self.assertEqual(["AI 개론", "AI 응용"], [button.text() for button in courses])
                    self.assertAlmostEqual(courses[0].width(), courses[1].width(), delta=1)
                    self.assertEqual(courses[0].font(), courses[1].font())
                    self.assertEqual(theme.TYPE["headline"][0], courses[0].font().pixelSize())
                    self.assertEqual(courses[0].height(), courses[1].height())
                    heights.append(courses[0].height())
                    self.assertEqual(courses[0].mapTo(home, QPoint()).y(), courses[1].mapTo(home, QPoint()).y())
                    self.assertEqual(courses[1].mapTo(home, QPoint(courses[1].width(), 0)).x(),
                                     browser.navigation.mapTo(home, QPoint(browser.navigation.width(), 0)).x())
                    self.assertGreaterEqual(home.scroll.viewport().height(), 200)
                    for button in courses:
                        self.assertTrue(win.rect().contains(button.rect().translated(button.mapTo(win, QPoint()))))
                        self.assertGreaterEqual(button.width() - 32, QFontMetricsF(button.font()).horizontalAdvance(button.text()))
                        self.assertTrue(button.accessibleDescription())
                    course_positions = [button.mapTo(home, QPoint()) for button in courses]
                    buttons = list(browser.buttons.values())
                    ys = {button.mapTo(home, QPoint()).y() for button in buttons}
                    single_line_width = max(button.sizeHint().width() for button in buttons) * 4 + 24
                    self.assertEqual(1 if browser.navigation.width() >= single_line_width else 2, len(ys))
                    if size[0] == 760:
                        self.assertEqual(2, len(ys))
                    elif not native:
                        self.assertEqual(1, len(ys))
                    self.assertEqual(1, len({button.height() for button in buttons}))
                    self.assertEqual(0, home.scroll.horizontalScrollBar().maximum())
                    before = [button.mapTo(home, QPoint()) for button in buttons]
                    for button in buttons:
                        rectangle = button.rect().translated(button.mapTo(win, QPoint()))
                        self.assertTrue(win.rect().contains(rectangle))
                        metrics = QFontMetricsF(theme.font("label", True))
                        text = metrics.boundingRect(QRectF(0, 0, button.width() - 40, 1000),
                                                    Qt.TextFlag.TextWordWrap, button.text())
                        self.assertLessEqual(text.height(), button.height() - 16)
                        self.assertTrue(button.accessibleName())
                        self.assertTrue(button.toolTip())
                    bar = home.scroll.verticalScrollBar()
                    bar.setValue(bar.maximum())
                    guikit.pump()
                    self.assertEqual(before, [button.mapTo(home, QPoint()) for button in buttons])
                    self.assertEqual(course_positions, [button.mapTo(home, QPoint()) for button in courses])
                    guikit.click(browser.buttons["mocks"])
                    self.settle()
                    self.assertEqual(before, [button.mapTo(home, QPoint()) for button in buttons])
                    home.scroll.ensureWidgetVisible(home.mock_list.rows[0])
                    guikit.pump()
                    row = home.mock_list.rows[0]
                    self.assertTrue(row.isVisible())
                    self.assertFalse(home.lesson_list.isVisible())
                    self.assertFalse(home.next_card.isVisible())
                    guikit.click(browser.buttons["lessons"])
                    self.settle()
                self.assertGreater(heights[0], heights[1], (mode, size, heights))
                self.assertEqual(heights[0], heights[2], (mode, size, heights))
        self.capture_widget = win

    def test_refresh_and_course_switch_restore_each_category_position(self):
        win, home, browser = self.home()
        bar = home.scroll.verticalScrollBar()
        bar.setValue(min(640, bar.maximum()))
        lesson_position = bar.value()
        self.assertGreater(lesson_position, 300)
        guikit.click(browser.buttons["books"])
        self.settle()
        bar.setValue(min(380, bar.maximum()))
        book_position = bar.value()
        self.assertGreater(book_position, 200)
        guikit.click(browser.buttons["lessons"])
        self.settle()
        self.assertEqual(lesson_position, bar.value())
        home.refresh()
        self.settle()
        self.assertEqual(lesson_position, bar.value())
        win.go_hub()
        win.go_ai()
        self.settle()
        self.assertEqual(lesson_position, bar.value())
        guikit.click(browser.buttons["books"])
        self.settle()
        self.assertEqual(book_position, bar.value())
        guikit.click(home.course_tabs.buttons[1])
        self.settle()
        guikit.click(browser.buttons["coding"])
        self.settle()
        self.assertTrue(home.pattern_empty.isVisible())
        guikit.click(home.course_tabs.buttons[0])
        self.settle()
        self.assertTrue(browser.buttons["books"].isChecked())
        self.assertEqual(book_position, bar.value())
        guikit.click(home.course_tabs.buttons[1])
        self.settle()
        self.assertTrue(browser.buttons["coding"].isChecked())
        self.assertEqual(0, bar.value())

    def test_keyboard_and_busy_navigation_do_not_write_learning_records(self):
        win, home, browser = self.home()
        before = self.log()
        first = browser.buttons["lessons"]
        first.setFocus()
        QTest.keyClick(first, Qt.Key.Key_Right)
        self.settle()
        self.assertTrue(browser.buttons["books"].hasFocus())
        self.assertTrue(home.books.isVisible())
        QTest.keyClick(browser.buttons["books"], Qt.Key.Key_End)
        self.settle()
        self.assertTrue(home.mock_list.isVisible())
        home.set_busy(True)
        home.refresh()
        guikit.click(browser.buttons["coding"])
        self.settle()
        self.assertTrue(home.pattern_list.isVisible())
        self.assertTrue(all(row.inert for row in home.pattern_list.rows))
        self.assertFalse(home.course_tabs.isEnabled())
        home.set_busy(False)
        first.setFocus()
        QTest.keyClick(first, Qt.Key.Key_Return)
        self.settle()
        self.assertTrue(home.lesson_list.isVisible())
        browser.buttons["mocks"].setFocus()
        QTest.keyClick(browser.buttons["mocks"], Qt.Key.Key_Space)
        self.settle()
        self.assertTrue(home.mock_list.isVisible())
        self.assertEqual(before, self.log())

    def test_manual_scroll_takes_priority_over_pending_position_restore(self):
        win, home, browser = self.home()
        bar = home.scroll.verticalScrollBar()
        bar.setValue(500)
        browser.select("books")
        browser.select("lessons")
        self.assertIsNotNone(browser.pending)
        bar.triggerAction(QAbstractSlider.SliderAction.SliderSingleStepAdd)
        chosen = bar.value()
        self.settle()
        self.assertEqual(chosen, bar.value())

    def test_tab_order_follows_selected_category_after_course_switch(self):
        win, home, browser = self.home()
        guikit.click(home.course_tabs.buttons[1])
        guikit.click(browser.buttons["mocks"])
        guikit.click(home.course_tabs.buttons[0])
        self.settle()
        home.course_tabs.buttons[0].setFocus()
        QTest.keyClick(home.course_tabs.buttons[0], Qt.Key.Key_Tab)
        self.assertTrue(browser.buttons["lessons"].hasFocus())
        QTest.keyClick(browser.buttons["lessons"], Qt.Key.Key_Down)
        self.assertTrue(browser.buttons["coding"].hasFocus())
        QTest.keyClick(browser.buttons["coding"], Qt.Key.Key_Up)
        QTest.keyClick(browser.buttons["lessons"], Qt.Key.Key_Right)
        QTest.keyClick(browser.buttons["books"], Qt.Key.Key_Home)
        self.assertTrue(browser.buttons["lessons"].hasFocus())
        QTest.keyClick(browser.buttons["lessons"], Qt.Key.Key_Tab)
        self.assertTrue(home.guide_btn.hasFocus())

    def test_partial_read_error_and_mock_error_are_visible_in_their_lists(self):
        win, home, browser = self.home()
        overview = win.ai.overview()
        overview["lessons"][0].update(ready=False, error="차시 파일 확인 필요")
        overview["patterns"].append(dict(overview["patterns"][0], error="실습 파일 확인 필요", units=[]))
        state = dict(win.ai.mock_state("m1"), error="시험 자료 확인 필요")
        with mock.patch.object(win.ai, "overview", return_value=overview), mock.patch.object(win.ai, "mock_state", return_value=state):
            home.refresh()
            self.settle()
            self.assertTrue(home.lesson_empty.isVisible())
            self.assertIn("일부 차시", home.lesson_empty.text())
            guikit.click(browser.buttons["coding"])
            self.settle()
            self.assertTrue(home.pattern_empty.isVisible())
            self.assertIn("일부 코딩 실습", home.pattern_empty.text())
            guikit.click(browser.buttons["mocks"])
            self.settle()
            self.assertIn("시험 자료 확인 필요", home.mock_list.rows[0].second.text())
            self.assertTrue(home.mock_list.rows[0].wrap)

    def test_selection_restoration_moves_focus_off_unselected_category(self):
        win, home, browser = self.home()
        browser.buttons["mocks"].setFocus()
        browser.select("lessons")
        self.assertTrue(browser.buttons["lessons"].hasFocus())
        home.course_tabs.buttons[0].setFocus()
        browser.select("books")
        self.assertTrue(home.course_tabs.buttons[0].hasFocus())

    def test_missing_content_and_read_error_have_different_messages(self):
        win, home, browser = self.home()
        guikit.click(home.course_tabs.buttons[1])
        guikit.click(browser.buttons["coding"])
        self.settle()
        self.assertIn("아직", home.pattern_empty.text())
        self.assertEqual("", home.pattern_count.text())
        with mock.patch.object(win.ai, "overview", side_effect=SessionError("기록 확인 필요")):
            home.refresh()
            self.settle()
            self.assertTrue(home.notice.isVisible())
            self.assertIn("읽지 못해", home.pattern_empty.text())
            self.assertEqual("", home.pattern_count.text())
            guikit.click(browser.buttons["books"])
            home.set_busy(True)
            home.set_busy(False)
            self.assertTrue(home.books.rows)
            self.assertTrue(all(row.inert for row in home.books.rows))

    def test_more_lessons_do_not_push_mock_navigation_out_of_view(self):
        win, home, browser = self.home()
        overview = win.ai.overview()
        overview["lessons"] = [dict(overview["lessons"][0], title="긴 차시 이름 " + str(n)) for n in range(70)]
        with mock.patch.object(win.ai, "overview", return_value=overview):
            home.refresh()
            self.settle()
            long_maximum = home.scroll.verticalScrollBar().maximum()
            home.scroll.verticalScrollBar().setValue(long_maximum)
            guikit.click(browser.buttons["mocks"])
            self.settle()
            self.assertEqual(0, home.scroll.verticalScrollBar().value())
            self.assertLess(home.scroll.verticalScrollBar().maximum(), long_maximum // 5)
            self.assertFalse(home.mock_list.rows[0].visibleRegion().isEmpty())
            self.assertTrue(browser.buttons["lessons"].isVisible())
