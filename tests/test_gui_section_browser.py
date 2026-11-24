"""자료가 늘어나도 분류를 찾고 읽던 목록으로 돌아오는지 확인함."""
import json
import os
from pathlib import Path
from unittest import mock

from tests import guikit
from tests.test_gui_ai import AiTest
from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QAbstractSlider

from gui import ai_text, kit, theme
from gui.career_roadmap import ReadingPage
from session import SessionError


class AiSectionBrowserTest(AiTest):
    real_bank = True

    def test_application_course_keeps_topbar_and_tab_reaches_selected_course(self):
        win, home, browser = self.home()
        self.capture_widget = win
        win.set_theme("dark")
        win.set_text("larger")
        self.settle()
        before = (home.top.geometry(), home.hub_btn.mapTo(win, QPoint()), home.hub_btn.size())
        guikit.click(home.course_tabs.buttons[1])
        self.settle()
        self.assertEqual("app", win.ai.course)
        self.assertEqual(before, (home.top.geometry(), home.hub_btn.mapTo(win, QPoint()), home.hub_btn.size()))
        self.assertIs(home.hub_btn, home.top.back)
        home.hub_btn.setFocus()
        QTest.keyClick(home.hub_btn, Qt.Key.Key_Tab)
        self.assertTrue(home.settings_btn.hasFocus())
        QTest.keyClick(home.settings_btn, Qt.Key.Key_Tab)
        self.assertTrue(home.course_tabs.buttons[1].isChecked())
        self.assertTrue(home.course_tabs.buttons[1].hasFocus())
        QTest.keyClick(home.course_tabs.buttons[1], Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(home.settings_btn.hasFocus())
        QTest.keyClick(home.settings_btn, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(home.hub_btn.hasFocus())
        QTest.keyClick(home.hub_btn, Qt.Key.Key_Tab)
        QTest.keyClick(home.settings_btn, Qt.Key.Key_Tab)
        self.assertTrue(home.course_tabs.buttons[1].hasFocus())
        self.assertFalse(browser.isAncestorOf(home.hub_btn))
        destination = os.environ.get("STUDY_UI_ARTIFACT_DIR")
        if destination:
            target = Path(destination)
            target.mkdir(parents=True, exist_ok=True)
            self.assertTrue(win.grab().save(str(target / "ai-home-header-app-dark-760-larger.png")))

    def test_home_back_matches_shared_topbar_outside_content_column(self):
        self.settings.setValue("onboarding/career/catalog/v1", True)
        win, home, browser = self.home()
        self.capture_widget = win
        self.assertIsInstance(home.top, kit.TopBar)
        self.assertIs(home.hub_btn, home.top.back)
        self.assertIs(home.top.parentWidget(), home)
        self.assertFalse(browser.isAncestorOf(home.hub_btn))
        native = guikit.APP.platformName() != "offscreen"
        room = win.screen().availableGeometry()
        frame_width = win.frameGeometry().width() - win.width()
        frame_height = win.frameGeometry().height() - win.height()
        destination = os.environ.get("STUDY_UI_ARTIFACT_DIR")
        measurements = []
        for mode in ("light", "dark"):
            win.set_theme(mode)
            for requested in ((760, 480), (2048, 1000)):
                width, height = requested
                if native:
                    width = min(width, room.width() - frame_width - 32)
                    height = min(height, room.height() - frame_height - 32)
                win.resize(width, height)
                if native:
                    win.move(room.topLeft() + QPoint(16, 16))
                for step in ("normal", "larger"):
                    win.set_text(step)
                    self.settle()
                    if native:
                        self.assertTrue(room.contains(win.frameGeometry()))
                    top, back = home.top, home.hub_btn
                    self.assertEqual((0, 0, home.width(), theme.CONTROL["topbar_dense"]), top.geometry().getRect())
                    self.assertEqual(top.height(), browser.y())
                    self.assertEqual(kit.DENSE_MARGIN - kit.FLUSH, back.x())
                    self.assertGreaterEqual(back.width(), back.sizeHint().width())
                    self.assertGreaterEqual(back.height(), back.sizeHint().height())
                    bounds = back.rect().translated(back.mapTo(win, QPoint()))
                    self.assertTrue(win.rect().contains(bounds))
                    global_back = back.mapToGlobal(QPoint())
                    comparisons = []
                    for move in (win.go_home, win.go_career):
                        move()
                        self.idle()
                        page = win.pages.currentWidget()
                        if move == win.go_home:
                            self.assertIs(page, win.home)
                            other = page.hub_btn
                        else:
                            self.assertIsInstance(page, ReadingPage)
                            other = page.top.back
                        other_top = other.parentWidget()
                        # AI 홈과 파이썬 홈은 촘촘한 위 막대(높이 topbar_dense, 좌우 여백 DENSE_MARGIN)를 쓰고 커리어만 높이 64·여백 MARGIN 임.
                        # 그래서 커리어의 돌아가기 단추가 두 여백 차이만큼 오른쪽에 있고 막대가 높음. 단추 높이·막대 위치·가운데 맞춤은 같게 봄.
                        dense = move == win.go_home
                        shift = 0 if dense else kit.MARGIN - kit.DENSE_MARGIN
                        self.assertEqual(global_back.x() + shift, other.mapToGlobal(QPoint()).x())
                        self.assertEqual(top.mapToGlobal(QPoint()), other_top.mapToGlobal(QPoint()))
                        self.assertEqual(back.height(), other.height())
                        self.assertEqual(top.height() if dense else theme.CONTROL["topbar"], other_top.height())
                        # 선이 있는 파이썬 막대는 안쪽 높이가 1px 작음. 각 막대의 실제 내용 칸에서 가운데를 확인함.
                        self.assertEqual(other_top.contentsRect().y() + (other_top.contentsRect().height() - other.height()) // 2,
                                         other.y())
                        comparisons.append(dict(page=type(page).__name__,
                                                back_global=[other.mapToGlobal(QPoint()).x(), other.mapToGlobal(QPoint()).y()],
                                                button_height=other.height(), top_height=other.parentWidget().height()))
                    win.go_ai()
                    self.settle()
                    bar = home.scroll.verticalScrollBar()
                    bar.setValue(bar.maximum())
                    guikit.pump()
                    self.assertEqual(bounds, back.rect().translated(back.mapTo(win, QPoint())))
                    bar.setValue(0)
                    self.settle()
                    back.setFocus()
                    QTest.keyClick(back, Qt.Key.Key_Tab)
                    self.assertTrue(home.settings_btn.hasFocus())
                    QTest.keyClick(home.settings_btn, Qt.Key.Key_Tab)
                    self.assertTrue(home.course_tabs.buttons[0].hasFocus())
                    if destination:
                        target = Path(destination)
                        target.mkdir(parents=True, exist_ok=True)
                        stem = "ai-home-header-%s-%d-%s" % (mode, requested[0], step)
                        self.assertTrue(win.grab().save(str(target / (stem + ".png"))))
                        measurements.append(dict(mode=mode, text=step, requested=requested,
                                                 window=[win.width(), win.height()], back=bounds.getRect(),
                                                 top=top.geometry().getRect(), viewport=home.scroll.viewport().height(),
                                                 back_global=[global_back.x(), global_back.y()], comparisons=comparisons,
                                                 head_sha=os.environ.get("STUDY_UI_HEAD_SHA", ""),
                                                 platform=guikit.APP.platformName(), dpr=win.devicePixelRatioF()))
                        (target / "ai-home-header.json").write_text(json.dumps(measurements, indent=2), encoding="utf-8")
        guikit.click(home.hub_btn)
        self.assertIs(win.pages.currentWidget(), win.hub)
        win.go_ai()
        win.resize(760, 480)
        self.settle()

    def home(self, size=(760, 480)):
        win = self.boot(size)
        win.go_ai()
        self.settle()
        return win, win.ai_home, win.ai_home.browser

    def test_category_cards_keep_descriptions_inside_and_compact_when_height_shrinks(self):
        """넓은 분류 카드의 설명을 확인하고 낮은 창에서 본문 공간을 되돌림."""
        win, home, browser = self.home((1600, 1000))
        win.set_text("larger")
        for mode in ("light", "dark"):
            win.set_theme(mode)
            for height, expanded in ((1000, True), (600, False), (1000, True)):
                win.resize(1600, height)
                self.settle()
                self.assertEqual("lessons", browser.current)
                self.assertGreaterEqual(home.scroll.viewport().height(), 200)
                self.assertEqual(0, home.scroll.horizontalScrollBar().maximum())
                for button in browser.buttons.values():
                    self.assertEqual(expanded, button.expanded)
                    if not expanded:
                        continue
                    title = QFontMetricsF(theme.font("label", True)).boundingRect(
                        QRectF(0, 0, button.width() - 64, 1000), Qt.TextFlag.TextWordWrap, button.text())
                    detail = QFontMetricsF(theme.font("caption")).boundingRect(
                        QRectF(0, 0, button.width() - 32, 1000), Qt.TextFlag.TextWordWrap, button.description)
                    top = max(56, title.height() + 32)
                    self.assertLessEqual(top + detail.height() + 8, button.height())
                    self.assertLessEqual(title.width(), button.width() - 64)
                    self.assertLessEqual(detail.width(), button.width() - 32)

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
                    self.assertEqual(["AI 개론", "AI 응용", "모의고사"], [button.text() for button in courses])
                    for other in courses[1:]:
                        self.assertAlmostEqual(courses[0].width(), other.width(), delta=1)
                        self.assertEqual(courses[0].font(), other.font())
                        self.assertEqual(courses[0].height(), other.height())
                        self.assertEqual(courses[0].mapTo(home, QPoint()).y(), other.mapTo(home, QPoint()).y())
                    self.assertEqual(theme.TYPE["headline"][0], courses[0].font().pixelSize())
                    heights.append(courses[0].height())
                    # 세 탭은 surface_alt 틀 안에 안쪽 4 를 두고 놓임. 틀의 양 끝이 구역 탭 줄과 같은 세로선에 옴
                    frame = home.course_tabs
                    self.assertEqual(frame.mapTo(home, QPoint()).x(), browser.navigation.mapTo(home, QPoint()).x())
                    self.assertEqual(frame.mapTo(home, QPoint(frame.width(), 0)).x(),
                                     browser.navigation.mapTo(home, QPoint(browser.navigation.width(), 0)).x())
                    self.assertEqual(courses[0].mapTo(home, QPoint()).x(), frame.mapTo(home, QPoint(4, 0)).x())
                    self.assertEqual(courses[-1].mapTo(home, QPoint(courses[-1].width(), 0)).x(),
                                     frame.mapTo(home, QPoint(frame.width() - 4, 0)).x())
                    self.assertLess(home.hub_btn.mapTo(home, QPoint(0, home.hub_btn.height())).y(),
                                    courses[0].mapTo(home, QPoint()).y())
                    self.assertGreaterEqual(home.scroll.viewport().height(), 200)
                    for button in courses:
                        self.assertTrue(win.rect().contains(button.rect().translated(button.mapTo(win, QPoint()))))
                        self.assertGreaterEqual(button.width() - 32, QFontMetricsF(button.font()).horizontalAdvance(button.text()))
                        self.assertTrue(button.accessibleDescription())
                    course_positions = [button.mapTo(home, QPoint()) for button in courses]
                    buttons = list(browser.buttons.values())
                    ys = {button.mapTo(home, QPoint()).y() for button in buttons}
                    single_line_width = max(sum(button.sizeHint().width() for button in buttons),
                                            max(button.minimumSizeHint().width() for button in buttons) * len(buttons)) + browser.grid.spacing() * (len(buttons) - 1)
                    self.assertEqual(1 if browser.navigation.width() >= single_line_width else 2, len(ys))
                    self.assertEqual(1, len(ys))
                    self.assertEqual(1, len({button.height() for button in buttons}))
                    self.assertLessEqual(max(button.width() for button in buttons) - min(button.width() for button in buttons), 1)
                    self.assertEqual(0, home.scroll.horizontalScrollBar().maximum())
                    before = [button.mapTo(home, QPoint()) for button in buttons]
                    for button in buttons:
                        rectangle = button.rect().translated(button.mapTo(win, QPoint()))
                        self.assertTrue(win.rect().contains(rectangle))
                        metrics = QFontMetricsF(theme.font("label", True))
                        text = metrics.boundingRect(QRectF(0, 0, button.width() - 24, 1000),
                                                    Qt.TextFlag.TextWordWrap, button.text())
                        self.assertLessEqual(text.width(), button.width() - 24)
                        self.assertLessEqual(text.height(), button.height() - 16)
                        self.assertTrue(button.accessibleName())
                        self.assertTrue(button.toolTip())
                    bar = home.scroll.verticalScrollBar()
                    bar.setValue(bar.maximum())
                    guikit.pump()
                    self.assertEqual(before, [button.mapTo(home, QPoint()) for button in buttons])
                    self.assertEqual(course_positions, [button.mapTo(home, QPoint()) for button in courses])
                    guikit.click(courses[2])
                    self.settle()
                    self.assertEqual(course_positions, [button.mapTo(home, QPoint()) for button in courses])
                    self.assertFalse(browser.navigation.isVisible())
                    self.assertEqual(0, home.scroll.horizontalScrollBar().maximum())
                    self.assertGreaterEqual(home.scroll.viewport().height(), 200)
                    home.scroll.ensureWidgetVisible(home.mock_list.rows[0])
                    guikit.pump()
                    row = home.mock_list.rows[0]
                    self.assertTrue(row.isVisible())
                    self.assertFalse(home.lesson_list.isVisible())
                    self.assertFalse(home.next_card.isVisible())
                    guikit.click(courses[0])
                    self.settle()
                    self.assertEqual(before, [button.mapTo(home, QPoint()) for button in buttons])
                    guikit.click(browser.buttons["lessons"])
                    self.settle()
                self.assertGreater(heights[0], heights[1], (mode, size, heights))
                self.assertEqual(heights[0], heights[2], (mode, size, heights))
        self.capture_widget = win

    def test_real_lesson_titles_wrap_and_selection_stays_distinct_from_focus(self):
        win, home, browser = self.home()
        self.capture_widget = win
        destination = os.environ.get("STUDY_UI_ARTIFACT_DIR")
        measurements = []
        room = win.screen().availableGeometry()
        native = guikit.APP.platformName() != "offscreen"
        frame = win.frameGeometry().size() - win.size()
        win.set_text("larger")
        for mode in ("light", "dark"):
            win.set_theme(mode)
            for requested in ((760, 480), (1600, 1000)):
                width, height = requested
                if native:
                    width = min(width, room.width() - frame.width() - 32)
                    height = min(height, room.height() - frame.height() - 32)
                    win.move(room.topLeft() + QPoint(16, 16))
                win.resize(width, height)
                for course, count in (("intro", 17), ("app", 9)):
                    win.switch_ai_course(course)
                    browser.select("lessons")
                    self.settle()
                    self.assertEqual((width, height), (win.width(), win.height()))
                    overview = win.ai.overview()
                    expected = [row for row in overview["lessons"] if row["ready"]]
                    self.assertEqual(count, len(home.lesson_list.rows))
                    self.assertEqual([row["id"] for row in expected], [row.data for row in home.lesson_list.rows])
                    for row, spec in zip(home.lesson_list.rows, expected):
                        self.assertTrue(row.wrap)
                        self.assertNotIsInstance(row.title, kit.ElideLabel)
                        self.assertEqual(ai_text.lesson_title(spec["no"], spec["title"], course), row.title.text())
                        self.assertEqual("예습" if spec["preview"] else "", row.end.text())
                        self.assertGreaterEqual(row.title.height(), row.title.heightForWidth(row.title.width()))
                        self.assertTrue(row.rect().contains(row.title.rect().translated(row.title.mapTo(row, QPoint()))))
                    pending = [row for row in overview["lessons"] if not row["ready"] and not row.get("error")]
                    self.assertEqual(bool(pending), home.lesson_list.more_btn is not None)
                    self.assertGreaterEqual(home.scroll.viewport().height(), 200)
                    self.assertEqual(0, home.scroll.horizontalScrollBar().maximum())
                    self.assertEqual(home.guide_btn.y(), home.data_btn.y())
                    for button in (home.guide_btn, home.data_btn):
                        self.assertGreaterEqual(button.width(), button.sizeHint().width())
                    selected, other = browser.buttons["lessons"], browser.buttons["books"]
                    home.hub_btn.setFocus()
                    guikit.pump()
                    unfocused = selected.grab().toImage()
                    selected.setFocus()
                    guikit.pump()
                    self.assertNotEqual(unfocused, selected.grab().toImage())
                    other.setFocus()
                    guikit.pump()
                    self.assertTrue(selected.isChecked())
                    self.assertTrue(other.hasFocus())
                    self.assertFalse(other.isChecked())
                    home.hub_btn.setFocus()
                    guikit.pump()
                    image = selected.grab().toImage()
                    scale = image.devicePixelRatio()
                    self.assertTrue(guikit.near(image.pixelColor(int(selected.width() * scale / 2), int(6 * scale)), "primary"))
                    if destination:
                        target = Path(destination)
                        target.mkdir(parents=True, exist_ok=True)
                        stem = "ai-sections-%s-%s-%d-larger" % (course, mode, requested[0])
                        home.scroll.verticalScrollBar().setValue(0)
                        guikit.pump()
                        self.assertTrue(win.grab().save(str(target / (stem + ".png"))))
                        longest = max(home.lesson_list.rows, key=lambda row: row.title.height())
                        home.scroll.ensureWidgetVisible(longest)
                        guikit.pump()
                        self.assertTrue(win.grab().save(str(target / (stem + "-lesson.png"))))
                        measurements.append(dict(course=course, mode=mode, requested=requested,
                                                 window=[win.width(), win.height()], viewport=home.scroll.viewport().height(),
                                                 section_sizes=[[button.width(), button.height()] for button in browser.buttons.values()],
                                                 lessons=count, pending=len(pending), platform=guikit.APP.platformName(),
                                                 dpr=win.devicePixelRatioF(), head_sha=os.environ.get("STUDY_UI_HEAD_SHA", "")))
                        (target / "ai-sections.json").write_text(json.dumps(measurements, indent=2), encoding="utf-8")

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
        self.assertTrue(home.pattern_section.isVisible())
        self.assertFalse(home.pattern_empty.isVisible())
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
        self.assertTrue(browser.buttons["coding"].hasFocus())
        self.assertTrue(home.pattern_list.isVisible())
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
        home.course_tabs.buttons[2].setFocus()
        QTest.keyClick(home.course_tabs.buttons[2], Qt.Key.Key_Space)
        self.settle()
        self.assertTrue(home.mock_list.isVisible())
        home.set_busy(True)
        QTest.keyClick(home.course_tabs.buttons[0], Qt.Key.Key_Space)
        self.settle()
        self.assertEqual("mock", home.tab)
        home.set_busy(False)
        self.assertEqual(before, self.log())

    def test_disabled_category_keeps_selection_without_changing_busy_navigation(self):
        win, home, browser = self.home()
        self.capture_widget = win
        for mode in ("light", "dark"):
            win.set_theme(mode)
            home.set_busy(True)
            self.settle()
            self.assertFalse(home.course_tabs.isEnabled())
            self.assertTrue(all(button.isEnabled() for button in browser.buttons.values()))
            selected, other = browser.buttons["lessons"], browser.buttons["books"]
            browser.setEnabled(False)
            try:
                guikit.click(other)
                self.assertEqual("lessons", browser.current)
                self.assertTrue(selected.isChecked())
                self.assertFalse(other.isChecked())
                for button, token in ((selected, "selection"), (other, "surface_alt")):
                    self.assertFalse(button.isEnabled())
                    image = button.grab().toImage()
                    scale = image.devicePixelRatio()
                    color = image.pixelColor(int(button.width() * scale / 2), int(6 * scale))
                    self.assertTrue(guikit.near(color, token), (mode, token))
            finally:
                browser.setEnabled(True)
                home.set_busy(False)
            self.assertTrue(selected.isChecked())
            self.assertTrue(home.course_tabs.isEnabled())

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
        guikit.click(home.course_tabs.buttons[2])
        guikit.click(home.course_tabs.buttons[0])
        self.settle()
        home.course_tabs.buttons[0].setFocus()
        QTest.keyClick(home.course_tabs.buttons[0], Qt.Key.Key_Tab)
        self.assertTrue(browser.buttons["lessons"].hasFocus())
        QTest.keyClick(browser.buttons["lessons"], Qt.Key.Key_Down)
        self.assertTrue(browser.buttons["lessons"].hasFocus())
        self.assertIsNone(browser.pending)
        QTest.keyClick(browser.buttons["lessons"], Qt.Key.Key_Right)
        QTest.keyClick(browser.buttons["books"], Qt.Key.Key_Home)
        self.assertTrue(browser.buttons["lessons"].hasFocus())
        QTest.keyClick(browser.buttons["lessons"], Qt.Key.Key_Tab)
        self.assertTrue(home.guide_btn.hasFocus())

    def test_narrow_category_row_wraps_and_keyboard_follows_visual_rows(self):
        win, home, browser = self.home()
        win.set_text("larger")
        browser.setFixedWidth(480)
        self.settle()
        buttons = list(browser.buttons.values())
        self.assertEqual(2, browser.columns)
        self.assertEqual(2, len({button.mapTo(home, QPoint()).y() for button in buttons}))
        for button in buttons:
            text = QFontMetricsF(button.font()).boundingRect(
                QRectF(0, 0, button.width() - 24, 1000), Qt.TextFlag.TextWordWrap, button.text())
            self.assertLessEqual(text.width(), button.width() - 24)
            self.assertLessEqual(text.height(), button.height() - 16)
        buttons[0].setFocus()
        QTest.keyClick(buttons[0], Qt.Key.Key_Down)
        self.assertTrue(buttons[2].hasFocus())
        self.assertEqual("coding", browser.current)
        QTest.keyClick(buttons[2], Qt.Key.Key_Up)
        self.assertTrue(buttons[0].hasFocus())
        browser.setMaximumWidth(16777215)
        browser.setMinimumWidth(0)
        self.settle()
        self.assertEqual(3, browser.columns)
        win.set_text("normal")
        self.settle()
        for button in buttons:  # 접힌 꼴의 아이콘은 자리가 모자라면 먼저 빠지므로 한 줄 기준은 아이콘 없는 폭임
            button.iconic = False
        needed = max(sum(max(button.sizeHint().width(), button.minimumSizeHint().width()) for button in buttons),
                     max(button.minimumSizeHint().width() for button in buttons) * len(buttons)) + browser.grid.spacing() * (len(buttons) - 1)
        browser.navigation.setFixedWidth(needed - 1)
        self.settle()
        self.assertEqual(2, browser.columns)
        browser.navigation.setFixedWidth(needed)
        self.settle()
        self.assertEqual(3, browser.columns)
        for button in buttons:
            text = QFontMetricsF(button.font()).boundingRect(
                QRectF(0, 0, button.width() - 24, 1000), Qt.TextFlag.TextWordWrap, button.text())
            self.assertLessEqual(text.width(), button.width() - 24)
            self.assertLessEqual(text.height(), button.height() - 16)

    def test_collapsed_tabs_draw_icons_only_when_they_keep_rows_and_height(self):
        win, home, browser = self.home((1280, 800))
        buttons = list(browser.buttons.values())
        self.assertFalse(buttons[0].expanded)
        self.assertEqual(len(buttons), browser.columns)
        self.assertTrue(all(button.iconic for button in buttons))
        height = buttons[0].height()
        for button in buttons:
            button.iconic = False
        self.assertEqual(height, max(button.heightForWidth(button.width()) for button in buttons))
        needed = max(sum(max(button.sizeHint().width(), button.minimumSizeHint().width()) for button in buttons),
                     max(button.minimumSizeHint().width() for button in buttons) * len(buttons)) + browser.grid.spacing() * (len(buttons) - 1)
        browser.navigation.setFixedWidth(needed - 1)
        self.settle()
        self.assertEqual(2, browser.columns)
        for button in buttons:
            if button.iconic:
                self.assertLessEqual(button.sizeHint().width(), button.width())

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
            guikit.click(home.course_tabs.buttons[2])
            self.settle()
            self.assertIn("시험 자료 확인 필요", home.mock_list.rows[0].second.text())
            self.assertTrue(home.mock_list.rows[0].wrap)

    def test_selection_restoration_moves_focus_off_unselected_category(self):
        win, home, browser = self.home()
        browser.buttons["coding"].setFocus()
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
        self.assertFalse(home.pattern_empty.isVisible())
        self.assertEqual("공개된 단원 4개", home.pattern_count.text())
        empty = dict(win.ai.overview(), patterns=[])  # 응용 코딩 실습을 공개했으므로 무리가 없는 목록은 바꿔 넣어 확인함
        with mock.patch.object(win.ai, "overview", return_value=empty):
            home.refresh()
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
            guikit.click(home.course_tabs.buttons[2])
            self.settle()
            self.assertEqual(0, home.scroll.verticalScrollBar().value())
            self.assertLess(home.scroll.verticalScrollBar().maximum(), long_maximum // 5)
            self.assertFalse(home.mock_list.rows[0].visibleRegion().isEmpty())
            self.assertFalse(home.course_tabs.buttons[2].visibleRegion().isEmpty())
