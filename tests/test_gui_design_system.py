"""공통 설정의 진입·종료와 하단 알림, 수업 범위 표시를 합성 상태로 확인함."""
import copy
import os
from pathlib import Path
from unittest import mock

from tests import guikit, test_gui_hub
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from gui import theme
from gui.career_roadmap import OrganisationGuide
from gui.career_learning_path import CareerLearningPath
from gui import kit


class DesignSystemTest(test_gui_hub.HubTest):
    def window_sizes(self, win):
        if guikit.APP.platformName() != "windows":
            return ((1280, 800), (760, 480))
        area = win.screen().availableGeometry()
        return ((min(1280, area.width() - 32), min(800, area.height() - 64)), (760, 480))

    def test_course_badge_matches_title_text_pixels_in_both_themes(self):
        path = CareerLearningPath(({"label": "C++ 실전", "course_status": "extra"},), ())
        kit.page(path)
        self.addCleanup(path.deleteLater)
        self.addCleanup(path.close)
        self.capture_widget = path
        step = path.steps[0]
        step.title.setText("같은 글자\n둘째 줄")
        step.status.setText("같은 글자")
        path.show()

        def first_line_bounds(widget, token, bg_token):
            image = widget.grab().toImage()
            target = theme.qcolor(token)
            background = theme.qcolor(bg_token)
            bg = (background.red(), background.green(), background.blue())
            delta = tuple(fg - base for fg, base in zip((target.red(), target.green(), target.blue()), bg))
            norm = sum(channel * channel for channel in delta)
            self.assertGreater(norm, 0)
            rows = []
            for y in range(image.height()):
                count = 0
                for x in range(1, image.width() - 1):
                    color = image.pixelColor(x, y)
                    # 전경·배경 대비로 정규화해 서로 다른 색의 글자 가장자리를 같은 비율로 셈.
                    coverage = sum((channel - base) * direction for channel, base, direction in
                                   zip((color.red(), color.green(), color.blue()), bg, delta)) / norm
                    # 투명 위젯 캡처는 지정한 배경에 알파 합성한 뒤 같은 커버리지로 비교함.
                    coverage *= color.alphaF()
                    if coverage >= .5:
                        count += 1
                if count >= 3:
                    if rows and y - rows[-1] > 3:
                        break
                    rows.append(y)
            self.assertTrue(rows)
            return tuple(widget.y() * image.devicePixelRatio() + row for row in (rows[0], rows[-1]))

        for mode in ("light", "dark"):
            for cycle, text in enumerate(("normal", "larger", "normal")):
                theme.set_mode(mode)
                theme.set_text(text)
                kit.refont(path)
                area = path.screen().availableGeometry()
                width = min(656, max(1, area.width() - 32))
                path.resize(width, path.heightForWidth(width))
                path.move(area.topLeft() + QPoint(16, 16))
                guikit.pump()
                self.assertTrue(area.contains(path.frameGeometry()))
                destination = os.environ.get("STUDY_UI_ARTIFACT_DIR")
                if destination:
                    target = Path(destination)
                    target.mkdir(parents=True, exist_ok=True)
                    self.assertTrue(step.grab().save(str(target / f"course-badge-{mode}-{cycle}-{text}.png")))
                title_bounds = first_line_bounds(step.title, "ink", "surface")
                status_bounds = first_line_bounds(step.status, "muted", "surface_alt")
                for title_edge, status_edge in zip(title_bounds, status_bounds):
                    self.assertLessEqual(abs(title_edge - status_edge), 1, (mode, text, title_bounds, status_bounds))
                self.assertGreaterEqual(step.title.height(), step.title.heightForWidth(step.title.width()))
                self.assertGreaterEqual(step.status.height(), step.status.heightForWidth(step.status.width()))

    def test_settings_reuse_actions_across_subject_and_career_overviews(self):
        win = self.boot()
        before = copy.deepcopy(win.session.prof)
        for move in (win.go_hub, win.go_home, win.go_journey, win.go_ai,
                     lambda: win.open_ai_lesson("i90"), win.go_career, win.go_magazine):
            move()
            guikit.wait_until(lambda: win.job is None)
            guikit.pump()
            for mode, size in ((mode, size) for mode in ("light", "dark") for size in self.window_sizes(win)):
                win.set_theme(mode)
                win.set_text("larger")
                win.resize(*size)
                guikit.pump()
                workspace = win.workspace
                page = win.pages.currentWidget()
                trigger = page.settings_btn
                if page is win.journey_map:
                    page.show_cache({"bytes": 10 * 1024 * 1024})
                    guikit.pump()
                if page.top.back is not None:
                    win.activateWindow()
                    guikit.pump()
                    page.top.back.setFocus()
                    self.assertTrue(page.top.back.hasFocus(), (type(page).__name__, page.top.back.isEnabled()))
                    for _ in range(20):
                        focused = guikit.APP.focusWidget()
                        if focused is trigger:
                            break
                        self.assertIsNotNone(focused)
                        self.assertTrue(page.top.isAncestorOf(focused), (type(page).__name__, mode, size, focused, trigger.isEnabled(), trigger.isVisible()))
                        QTest.keyClick(focused, Qt.Key.Key_Tab)
                    self.assertTrue(trigger.hasFocus())
                self.assertTrue(trigger.isVisible())
                self.assertGreaterEqual(trigger.width(), trigger.sizeHint().width())
                guikit.click(trigger)
                menu = page.settings_panel
                self.assertIs(trigger.parentWidget(), page.top.controls if page is win.hub else page.top)
                rect = trigger.rect().translated(trigger.mapTo(page.top, QPoint()))
                self.assertTrue(page.top.rect().contains(rect), (page, rect, page.top.rect()))
                self.assertLessEqual(abs(page.top.width() - rect.right() - 1 - (kit.MARGIN - kit.FLUSH)), 1)
                self.assertEqual(trigger.sizeHint().height(), win.hub.settings_btn.sizeHint().height())
                # 같은 막대의 기존 도구를 밀어 가리거나 겹치지 않는지 확인함.
                siblings = []
                for sibling in page.top.findChildren(type(trigger)):
                    if sibling is trigger or not sibling.isVisible():
                        continue
                    other = sibling.rect().translated(sibling.mapTo(page.top, QPoint()))
                    self.assertTrue(page.top.rect().contains(other), (sibling.text(), other, page.top.rect()))
                    self.assertGreaterEqual(sibling.width(), sibling.sizeHint().width(), sibling.text())
                    self.assertFalse(rect.intersects(other), (trigger.text(), sibling.text()))
                    for seen in siblings:
                        self.assertFalse(seen.intersects(other), sibling.text())
                    siblings.append(other)
                if page.top.title.isVisible():
                    self.assertGreater(page.top.title.width(), 0)
                self.assertTrue(menu.isVisible())
                self.assertEqual([b.text() for b in menu.actions], [b.text() for b in win.hub.settings_panel.actions])
                self.assertTrue(menu.screen().availableGeometry().contains(menu.geometry()))
                destination = os.environ.get("STUDY_UI_ARTIFACT_DIR")
                if destination:
                    target = Path(destination)
                    target.mkdir(parents=True, exist_ok=True)
                    self.assertTrue(win.grab().save(str(target / f"workspace-settings-{win.area}-{type(page).__name__}-{mode}-{win.width()}.png")))
                    self.assertTrue(menu.grab().save(str(target / f"workspace-settings-popup-{win.area}-{type(page).__name__}-{mode}-{win.width()}.png")))
                menu.dismiss(immediate=True)
                guikit.pump()
                self.assertTrue(trigger.hasFocus(), (type(page).__name__, mode, size, guikit.APP.activePopupWidget(), guikit.APP.activeModalWidget(), guikit.APP.focusWidget()))
        self.assertEqual(before, win.session.prof)
        win.go_hub()
        guikit.pump()
        self.assertEqual(sum(menu.trigger.isVisible() for menu in win.workspace.settings_menus), 0)
        self.assertTrue(win.hub.settings_btn.isVisible())

    def test_settings_cancel_pending_actions_on_navigation_and_lock_during_jobs(self):
        win = self.boot()
        win.go_home()
        guikit.pump()
        workspace = win.workspace
        menu = win.home.settings_panel
        menu.open_menu()
        callback = mock.Mock()
        menu.dismiss(after=callback, immediate=True)
        win.go_ai()
        guikit.pump()
        callback.assert_not_called()
        self.assertFalse(menu.isVisible())
        with mock.patch.object(win, "job", object()):
            workspace.refresh()
            for item in workspace.settings_menus:
                self.assertFalse(item.update_btn.isEnabled())
                self.assertFalse(item.identity_btn.isEnabled())
        workspace.refresh()
        for item in workspace.settings_menus:
            self.assertTrue(item.identity_btn.isEnabled())

    def test_settings_visibility_does_not_change_navigation_breakpoint(self):
        win = self.boot()
        win.set_text("larger")
        win.go_home()
        guikit.pump()
        workspace = win.workspace
        required = workspace.rail.minimumSizeHint().height()
        for height in (required - 1, required, required + 1):
            win.resize(1280, max(480, height))
            guikit.pump()
            shown = workspace.rail.isVisible()
            for move in (win.go_hub, win.go_home, win.go_ai, win.go_hub):
                move()
                guikit.pump()
                self.assertEqual(workspace.rail.minimumSizeHint().height(), required)
                self.assertEqual(workspace.rail.isVisible(), shown)

    def test_settings_tutorial_moves_to_hub_before_replay(self):
        win = self.boot()
        win.go_ai()
        guikit.pump()
        menu = win.ai_home.settings_panel
        seen = []
        with mock.patch.object(win, "show_hub_tour", side_effect=lambda **kw: seen.append((win.pages.currentWidget(), kw))):
            menu.show_first_tour()
            guikit.pump()
        self.assertTrue(any(page is win.hub and kw.get("replay") for page, kw in seen))

    def test_submission_actions_fit_without_losing_callbacks_or_visibility(self):
        win = self.boot()
        win.pending_submission = {"status": "ok", "pending": True, "count": 2}
        win.problem_updates = {"status": "ok", "available": True}
        bar = win.workspace.submissions
        bar.result = {"status": "error", "message": "연결을 확인해 주세요.", "detail": "합성 오류 설명"}
        for mode in ("light", "dark"):
            win.set_theme(mode)
            win.set_text("larger")
            for size in self.window_sizes(win):
                win.resize(*size)
                win.workspace.refresh()
                guikit.pump()
                self.assertEqual((win.width(), win.height()), size)
                for button in (bar.submit, bar.sync, bar.details, bar.dismiss):
                    self.assertTrue(button.isVisible())
                    rect = button.rect().translated(button.mapTo(bar, QPoint()))
                    self.assertTrue(bar.rect().contains(rect), (button.text(), rect, bar.rect()))
                    self.assertGreaterEqual(button.width(), button.sizeHint().width())
        guikit.click(bar.dismiss)
        self.assertIsNone(bar.result)
        self.assertTrue(bar.submit.isVisible())
        self.assertTrue(bar.sync.isVisible())
        self.assertFalse(bar.details.isVisible())

    def test_organisation_guide_uses_shared_dialog_and_keeps_learning_records(self):
        win = self.boot()
        win.resize(760, 480)
        before = copy.deepcopy(win.session.prof)
        for mode in ("light", "dark"):
            win.set_theme(mode)
            win.set_text("larger")
            dialog = OrganisationGuide(win)
            dialog.show()
            guikit.pump()
            self.assertLessEqual(dialog.height(), win.height())
            self.assertLessEqual(dialog.width(), win.width())
            rect = dialog.close_button.rect().translated(dialog.close_button.mapTo(dialog, QPoint()))
            self.assertTrue(dialog.rect().contains(rect))
            guikit.click(dialog.close_button)
            dialog.deleteLater()
        self.assertEqual(before, win.session.prof)
