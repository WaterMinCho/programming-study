"""직무 목록과 상세를 왕복하며 필터·저장 의도·읽던 위치를 확인함."""
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tests import guikit
from tests import test_gui_career as career_checks
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton
from gui import kit, theme
from gui.career_roadmap import CareerRoadmapPage


class CareerNavigationTest(unittest.TestCase):
    settle = career_checks.CareerGuiTest.settle

    def setUp(self):
        self.saved = Mock()
        self.page = CareerRoadmapPage(on_select_goal=self.saved)
        self.theme_state = dict(theme.state)
        self.page.resize(760, 480)
        self.page.show()
        self.settle(self.page)

    def tearDown(self):
        self.page.close()
        self.page.deleteLater()
        guikit.pump()
        theme.set_text(self.theme_state["text"])
        theme.set_mode(self.theme_state["mode"])

    def test_first_entry_filter_keyboard_detail_and_explicit_save(self):
        p = self.page
        self.assertTrue(p.browsing)
        self.assertTrue(p.gallery.isVisible())
        self.assertTrue(p.details.isHidden())
        self.assertEqual(list(p.gallery.cards), [r["id"] for r in p.catalog.roles])
        p.industry.setCurrentIndex(p.industry.findData("mobility"))
        self.settle(p)
        expected = [r["id"] for r in p.catalog.roles_for("mobility", None)]
        self.assertEqual(list(p.gallery.cards), expected)
        self.assertEqual(p.catalog_count.text(), f"직무 {len(expected)}개")
        card = p.gallery.cards[expected[-1]]
        card.setFocus()
        QTest.keyClick(card, Qt.Key.Key_Return)
        self.settle(p)
        self.assertFalse(p.browsing)
        self.assertEqual(p.role_title.text(), p.catalog.role(expected[-1])["title"])
        self.assertTrue(p.work_panel.isVisible())
        self.assertTrue(p.path_panel.isHidden())
        self.saved.assert_not_called()
        guikit.click(p.goal_button)
        self.saved.assert_called_once()
        p.set_saved_role(expected[-1])
        guikit.click(p.catalog_button)
        self.settle(p)
        self.assertEqual(p.industry.currentData(), "mobility")
        self.assertEqual(list(p.gallery.cards), expected)
        self.assertTrue(p.gallery.isVisible())
        self.assertIs(p.focusWidget(), card)

    def test_list_return_and_tabs_keep_their_reading_positions(self):
        p = self.page
        card = p.gallery.cards["qa"]
        p.scroll.ensureWidgetVisible(card)
        card.setFocus()
        self.settle(p)
        p._remember()
        anchor, offset = p._anchor
        QTest.keyClick(card, Qt.Key.Key_Space)
        self.settle(p)
        guikit.click(p.detail_tabs.buttons[1])
        self.settle(p)
        self.assertTrue(p.work_panel.isHidden())
        self.assertTrue(p.path_panel.isVisible())
        p.scroll.ensureWidgetVisible(p.learning_path.steps[-1])
        self.settle(p)
        before = p.scroll.verticalScrollBar().value()
        p.show_detail_tab(0)
        self.settle(p)
        p.show_detail_tab(1)
        self.settle(p)
        self.assertAlmostEqual(p.scroll.verticalScrollBar().value(), before, delta=1)
        p.show_catalog()
        self.settle(p)
        self.assertLessEqual(abs(anchor.mapTo(p.scroll.viewport(), QPoint()).y() - offset), 1)
        self.saved.assert_not_called()

    def test_detail_switch_outside_filter_restores_original_catalog_card(self):
        p = self.page
        p.industry.setCurrentIndex(p.industry.findData("mobility"))
        self.settle(p)
        expected = list(p.gallery.cards)
        filters = (p.industry.currentData(), p.product.currentData())
        origin = expected[-1]
        card = p.gallery.cards[origin]
        p.scroll.ensureWidgetVisible(card)
        card.setFocus()
        self.settle(p)
        p._remember()
        anchor, offset = p._anchor
        QTest.keyClick(card, Qt.Key.Key_Return)
        self.settle(p)
        catalog_anchor = p._catalog_anchor
        self.assertEqual(p._catalog_role_id, origin)
        actions = {action.data(): action for action in p.role_menu.actions()}
        self.assertEqual(set(actions), {role["id"] for role in p.catalog.roles})
        outside = [role["id"] for role in p.catalog.roles if role["id"] not in expected]
        self.assertGreaterEqual(len(outside), 2)
        p.show_detail_tab(1)
        self.settle(p)
        for role_id in outside[:2] + outside[:1]:
            p.scroll.verticalScrollBar().setValue(p.scroll.verticalScrollBar().maximum())
            self.settle(p)
            actions[role_id].trigger()
            self.settle(p)
            self.assertFalse(p.browsing)
            self.assertEqual(p.selected_role_id, role_id)
            self.assertTrue(p.path_panel.isVisible())
            self.assertTrue(p.detail_tabs.buttons[1].isChecked())
            self.assertEqual(p.scroll.verticalScrollBar().value(), 0)
            self.assertEqual(p._catalog_anchor, catalog_anchor)
            self.assertEqual(p._catalog_role_id, origin)
            self.assertEqual((p.industry.currentData(), p.product.currentData()), filters)
        guikit.click(p.catalog_button)
        self.settle(p)
        self.assertTrue(p.browsing)
        self.assertTrue(p.gallery.isVisible())
        self.assertTrue(p.details.isHidden())
        self.assertEqual(list(p.gallery.cards), expected)
        self.assertEqual((p.industry.currentData(), p.product.currentData()), filters)
        self.assertIs(p.focusWidget(), card)
        self.assertTrue(card.isChecked())
        self.assertAlmostEqual(anchor.mapTo(p.scroll.viewport(), QPoint()).y(), offset, delta=1)
        self.saved.assert_not_called()
        p.select_role(outside[-1])
        self.settle(p)
        self.assertIsNone(p._catalog_anchor)
        self.assertEqual(p._catalog_role_id, outside[-1])
        p.show_catalog()
        self.settle(p)
        self.assertTrue(p.gallery.cards[outside[-1]].isChecked())

    def test_detail_menu_updates_content_checks_and_only_saves_on_request(self):
        p = self.page
        p._open_catalog_role("qa")
        p.set_saved_role("qa")
        self.settle(p)
        self.assertEqual(p.role_switch_button.text(), "직무 바꾸기")
        self.assertTrue(p.controls.isAncestorOf(p.role_switch_button))
        actions = {action.data(): action for action in p.role_menu.actions()}
        self.assertEqual([a.data() for a in actions.values() if a.isChecked()], ["qa"])
        for role_id in ("backend", "frontend"):
            actions[role_id].trigger()
            self.settle(p)
            role = p.catalog.role(role_id)
            self.assertEqual(p.role_title.text(), role["title"])
            self.assertEqual(p.scene.role["id"], role_id)
            self.assertEqual(p.learning_path.nodes, tuple(role["roadmap_nodes"]))
            self.assertEqual(p.learning_path.outputs, tuple(role["outputs"]))
            self.assertEqual(p.work_flow.nodes[1], ("하는 일", "\n".join(role["tasks"])))
            self.assertEqual([a.data() for a in actions.values() if a.isChecked()], [role_id])
            self.assertEqual(p.goal_button.text(), "관심 직무로 저장")
            self.assertEqual(p.saved_role_id, "qa")
            self.saved.assert_not_called()
        guikit.click(p.goal_button)
        self.saved.assert_called_once_with("frontend", p.catalog.role("frontend")["goal_links"][0]["goal_id"])
        p.set_saved_role("frontend")
        self.assertEqual(p.goal_button.text(), "저장한 관심 직무")
        actions["qa"].trigger()
        self.settle(p)
        self.assertEqual(p.goal_button.text(), "관심 직무로 저장")
        actions["frontend"].trigger()
        self.settle(p)
        self.assertEqual(p.goal_button.text(), "저장한 관심 직무")
        self.saved.assert_called_once()

    def test_fixed_detail_menu_keyboard_cancel_choose_and_return_to_list(self):
        self.page.close()
        self.page.deleteLater()
        guikit.pump()
        back = Mock()
        p = self.page = CareerRoadmapPage(on_back=back, on_select_goal=self.saved)
        theme.set_text("larger")
        kit.refont(p)
        p.resize(760, 480)
        p.show()
        self.settle(p)
        origin = p.catalog.roles[-1]["id"]
        p._open_catalog_role(origin)
        self.settle(p)
        button, menu = p.role_switch_button, p.role_menu
        self.assertTrue(p.top.isAncestorOf(button))
        self.assertTrue(p.controls.isHidden())
        position = button.mapTo(p, QPoint())
        p.scroll.verticalScrollBar().setValue(p.scroll.verticalScrollBar().maximum())
        self.settle(p)
        self.assertEqual(button.mapTo(p, QPoint()), position)
        self.assertFalse(button.visibleRegion().isEmpty())
        actions = [action for action in menu.actions() if action.data() is not None]
        self.assertGreaterEqual(len(actions), 3)
        target = actions[1]
        self.assertNotEqual(target.data(), origin)

        def assert_button_focus():
            self.assertIs(p.focusWidget(), button)
            if guikit.APP.platformName() == "offscreen":
                # 메뉴 닫기 뒤 offscreen이 창을 비활성화하므로 창만 다시 활성화함.
                p.activateWindow()
                guikit.pump()
            self.assertTrue(button.hasFocus())

        try:
            for mode in ("light", "dark"):
                theme.set_mode(mode)
                kit.refont(p)
                self.settle(p)
                centers = [widget.mapTo(p, QPoint(0, widget.height() // 2)).y()
                           for widget in (p.top.back, button)]
                self.assertLessEqual(max(centers) - min(centers), 1)
                self.assertGreaterEqual(button.width(), button.fontMetrics().horizontalAdvance(button.text()))
                menu.popup(button.mapToGlobal(QPoint(0, button.height())))
                guikit.pump()
                for action in actions:
                    self.assertGreaterEqual(menu.actionGeometry(action).width(),
                                            menu.fontMetrics().horizontalAdvance(action.text()) + 44)
                menu.hide()
                self.capture(mode + "-detail-switch")
            p.activateWindow()
            guikit.pump()
            button.setFocus()
            self.assertTrue(button.hasFocus())
            before = p.scroll.verticalScrollBar().value()
            QTest.keyClick(button, Qt.Key.Key_Space)
            guikit.wait_until(menu.isVisible)
            menu.setActiveAction(actions[0])
            QTest.keyClick(menu, Qt.Key.Key_Down)
            self.assertIs(menu.activeAction(), target)
            QTest.keyClick(menu, Qt.Key.Key_Escape)
            self.settle(p)
            self.assertFalse(menu.isVisible())
            self.assertEqual(p.selected_role_id, origin)
            self.assertEqual(p.scroll.verticalScrollBar().value(), before)
            assert_button_focus()
            QTest.keyClick(button, Qt.Key.Key_Space)
            guikit.wait_until(menu.isVisible)
            menu.setActiveAction(actions[0])
            QTest.keyClick(menu, Qt.Key.Key_Down)
            QTest.keyClick(menu, Qt.Key.Key_Return)
            self.settle(p)
            self.assertFalse(menu.isVisible())
            self.assertEqual(p.selected_role_id, target.data())
            self.assertEqual([a.data() for a in actions if a.isChecked()], [target.data()])
            assert_button_focus()
            guikit.click(p.top.back)
            self.settle(p)
            self.assertTrue(p.browsing)
            self.assertIs(p.focusWidget(), p.gallery.cards[origin])
            back.assert_not_called()
            self.saved.assert_not_called()
        finally:
            menu.hide()

    def test_filters_preserve_choice_without_rebuilding_hidden_details(self):
        p = self.page
        self.assertIsNone(p.selected_role_id)
        p._open_catalog_role("qa")
        self.settle(p)
        p.show_catalog()
        with patch.object(p.scene, "set_role", wraps=p.scene.set_role) as build:
            p.industry.setCurrentIndex(p.industry.findData("mobility"))
            self.settle(p)
            p.industry.setCurrentIndex(0)
            self.settle(p)
            build.assert_not_called()
        self.assertEqual(p.selected_role_id, "qa")
        self.assertTrue(p.gallery.cards["qa"].isChecked())
        p.scroll.verticalScrollBar().setValue(80)
        self.settle(p)
        before = p.controls.mapTo(p.scroll.viewport(), QPoint()).y()
        guikit.click(p.filter_toggle)
        self.settle(p)
        self.assertAlmostEqual(p.controls.mapTo(p.scroll.viewport(), QPoint()).y(), before, delta=1)
        self.assertTrue(p.filters.isVisible())

    def test_work_tab_expansion_and_tab_return_preserve_position(self):
        p = self.page
        p.select_role("qa")
        self.settle(p)
        p.scroll.ensureWidgetVisible(p.sources_button)
        self.settle(p)
        before = p.sources_button.mapTo(p.scroll.viewport(), QPoint()).y()
        guikit.click(p.sources_button)
        self.settle(p)
        self.assertAlmostEqual(p.sources_button.mapTo(p.scroll.viewport(), QPoint()).y(), before, delta=1)
        p.scroll.verticalScrollBar().setValue(p.scroll.verticalScrollBar().maximum())
        self.settle(p)
        bottom = p.scroll.verticalScrollBar().value()
        p.show_detail_tab(1)
        self.settle(p)
        p.show_detail_tab(0)
        self.settle(p)
        self.assertAlmostEqual(p.scroll.verticalScrollBar().value(), bottom, delta=1)

    def test_missing_map_notice_stays_next_to_its_button(self):
        p = self.page
        p.select_role("robot_navigation")
        p.show_detail_tab(1)
        self.settle(p)
        with tempfile.TemporaryDirectory() as folder:
            p.repository = Path(folder)
            guikit.click(p.image_button)
        self.settle(p)
        self.assertTrue(p.image_notice.isVisible())
        self.assertTrue(p.path_panel.isAncestorOf(p.image_notice))
        self.assertFalse(p.image_notice.visibleRegion().isEmpty())
        p.show_detail_tab(0)
        self.settle(p)
        self.assertFalse(p.image_notice.isVisible())

    def test_small_window_maximum_text_two_themes_catalog_and_tabs(self):
        p = self.page
        self.capture_widget = p
        theme.set_text("larger")
        room = p.screen().availableGeometry()
        if guikit.APP.platformName() != "offscreen":
            p.move(room.topLeft() + QPoint(16, 16))
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            kit.refont(p)
            p.show_catalog()
            p.scroll.verticalScrollBar().setValue(0)
            self.settle(p)
            self.assertEqual((p.width(), p.height()), (760, 480))
            self.assertEqual(p.scroll.horizontalScrollBar().maximum(), 0)
            for card in p.gallery.cards.values():
                card.grab()
                self.assertLessEqual(card.x() + card.width(), p.gallery.width() + 1)
            self.capture(mode + "-catalog")
            p._open_catalog_role("robot_navigation")
            self.settle(p)
            for tab in (0, 1):
                guikit.click(p.detail_tabs.buttons[tab])
                self.settle(p)
                self.assertEqual(p.scroll.horizontalScrollBar().maximum(), 0)
                for button in p.findChildren(QPushButton):
                    if button.isVisibleTo(p):
                        self.assertGreaterEqual(button.width(), button.fontMetrics().horizontalAdvance(button.text()))
                p.scroll.ensureWidgetVisible(p.scene if tab == 0 else p.learning_path.steps[0], 0, 0)
                self.settle(p)
                target = p.scene if tab == 0 else p.learning_path.steps[0]
                self.assertFalse(target.visibleRegion().isEmpty())
                self.capture(f"{mode}-tab-{tab}")

    def capture(self, name):
        folder = os.environ.get("CAREER_EVIDENCE")
        if not folder:
            return
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        self.page.repaint()
        guikit.pump()
        self.assertTrue(self.page.grab().save(str(path / ("navigation-" + guikit.APP.platformName() + "-" + name + ".png"))))
        if guikit.APP.platformName() != "offscreen":
            screen = self.page.screen()
            if sys.platform == "win32":
                desktop = screen.grabWindow(0)
                ratio = desktop.devicePixelRatioF()
                origin = self.page.mapToGlobal(QPoint()) - screen.geometry().topLeft()
                native = desktop.copy(round(origin.x() * ratio), round(origin.y() * ratio),
                                      round(self.page.width() * ratio), round(self.page.height() * ratio))
            else:
                native = screen.grabWindow(int(self.page.winId()))
            self.assertTrue(native.save(str(path / (
                "navigation-" + guikit.APP.platformName() + "-" + name + "-native.png"))))
