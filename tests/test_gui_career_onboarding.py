"""커리어 첫 안내의 표시·키보드·기록 보존과 실제 배치를 검사함."""
import copy
import os
import unittest
from unittest import mock

from PyQt6.QtCore import QEvent, QPoint, QSettings, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

from tests import guikit, test_gui_hub
from gui import motion, theme
from gui.career_onboarding import TOUR_KEYS


class CareerOnboardingTest(unittest.TestCase):
    def setUp(self):
        self.fixture = test_gui_hub.HubTest()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        for key in TOUR_KEYS.values():
            self.fixture.settings.remove(key)

    def visible_tour(self, win, context):
        guikit.wait_until(lambda: win.career.tour is not None and win.career.tour.isVisible())
        tour = win.career.tour
        self.assertEqual(tour.context, context)
        return tour

    def test_first_visits_skip_complete_and_settings_replay(self):
        win = self.fixture.boot()
        before = copy.deepcopy(win.session.prof)
        keys = set(win.settings.allKeys())
        win.go_career()
        tour = self.visible_tour(win, "catalog")
        win.career._start_tour()
        self.assertIs(win.career.tour, tour)
        guikit.click(tour.skip)
        self.assertTrue(win.settings.value(TOUR_KEYS["catalog"], False, type=bool))
        page = win.career.roadmap
        role = next(iter(page.gallery.cards))
        page._open_catalog_role(role)
        tour = self.visible_tour(win, "detail")
        while tour.isVisible():
            guikit.click(tour.next)
        self.assertIsNone(page.saved_role_id)
        win.go_magazine()
        tour = self.visible_tour(win, "magazine")
        QTest.keyClick(tour.next, Qt.Key.Key_Escape)
        guikit.pump()
        self.assertFalse(tour.isVisible())
        self.assertIsNone(win.career.video)
        self.assertEqual(win.session.prof, before)
        self.assertEqual(set(win.settings.allKeys()), keys | set(TOUR_KEYS.values()))
        win.settings.sync()
        stored = QSettings(win.settings.fileName(), QSettings.Format.IniFormat)
        self.assertTrue(all(stored.value(key, False, type=bool) for key in TOUR_KEYS.values()))
        win.go_hub()
        win.go_career()
        guikit.pump()
        self.assertFalse(win.career.tour.isVisible())
        win.go_hub()
        guikit.click(win.hub.settings_btn)
        guikit.click(win.hub.settings_panel.replay_career)
        tour = self.visible_tour(win, "catalog")
        self.assertFalse(any(win.settings.contains(key) for key in TOUR_KEYS.values()))

    def test_modal_navigation_and_interrupted_tour(self):
        win = self.fixture.boot()
        modal = QDialog(win)
        modal.setModal(True)
        modal.open()
        win.go_career()
        guikit.pump()
        self.assertIsNone(win.career.tour)
        modal.accept()
        tour = self.visible_tour(win, "catalog")
        win.go_hub()
        guikit.pump()
        self.assertFalse(tour.isVisible())
        self.assertFalse(win.settings.contains(TOUR_KEYS["catalog"]))
        win.go_career()
        tour = self.visible_tour(win, "catalog")
        guikit.click(tour.skip)
        win.career.show_magazine(win.career.catalog.videos[0].video_id)
        guikit.pump()
        self.assertFalse(win.career.tour.isVisible())
        self.assertIsNone(win.career.video)
        win.go_hub()
        win.go_magazine()
        self.visible_tour(win, "magazine")

    def test_keyboard_does_not_activate_targets_and_replay_restores_reading(self):
        win = self.fixture.boot()
        win.go_career()
        tour = self.visible_tour(win, "catalog")
        for _ in range(5):
            QTest.keyClick(guikit.APP.focusWidget(), Qt.Key.Key_Tab)
            self.assertIn(guikit.APP.focusWidget(), (tour.skip, tour.back, tour.next))
        guikit.click(tour.skip)
        page = win.career.roadmap
        page._open_catalog_role(next(iter(page.gallery.cards)))
        tour = self.visible_tour(win, "detail")
        guikit.click(tour.next)
        page.goal_button.setFocus()
        QTest.keyClick(page.goal_button, Qt.Key.Key_Space)
        center = tour.mapFromGlobal(page.goal_button.mapToGlobal(page.goal_button.rect().center()))
        QTest.mouseClick(tour, guikit.LEFT, pos=center)
        self.assertIsNone(page.saved_role_id)
        self.assertFalse(win.settings.contains("career/role/" + win.user))
        guikit.click(tour.skip)
        page.show_catalog()
        guikit.pump()
        bar = page.scroll.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        guikit.pump()
        original = bar.value()
        guikit.click(page.tour_help)
        tour = self.visible_tour(win, "catalog")
        guikit.click(tour.next)
        guikit.click(tour.skip)
        guikit.pump()
        self.assertEqual(bar.value(), original)
        self.assertTrue(page.tour_help.hasFocus())

    def test_empty_targets_and_navigation_during_fade_do_not_mark_complete(self):
        win = self.fixture.boot()
        win.go_career()
        tour = self.visible_tour(win, "catalog")
        win.career.dismiss_tour()
        page = win.career.roadmap
        with mock.patch("gui.career_onboarding.steps_for", return_value=[]):
            win.career.queue_tour(page)
            guikit.pump()
            self.assertFalse(win.career.tour.active)
            self.assertFalse(win.settings.contains(TOUR_KEYS["catalog"]))
        with mock.patch.object(motion, "enabled", True):
            win.career.queue_tour(page)
            tour = self.visible_tour(win, "catalog")
            win.go_hub()
            guikit.pump(motion.FADE_MS + 20)
            self.assertFalse(tour.active)
            self.assertFalse(win.settings.contains(TOUR_KEYS["catalog"]))

    def test_held_key_deleted_target_and_missing_previous_focus(self):
        win = self.fixture.boot()
        win.go_career()
        tour = self.visible_tour(win, "catalog")
        for _ in range(4):
            guikit.APP.sendEvent(tour.next, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return,
                                                     Qt.KeyboardModifier.NoModifier, "", True))
        self.assertEqual(tour.step, 0)
        self.assertFalse(win.settings.contains(TOUR_KEYS["catalog"]))
        tour.previous_focus = None
        guikit.click(tour.skip)
        self.assertTrue(win.career.roadmap.tour_help.hasFocus())
        QTest.keyClick(guikit.APP.focusWidget(), Qt.Key.Key_Tab)
        self.assertTrue(guikit.APP.focusWidget().isVisible())
        self.assertNotIn(guikit.APP.focusWidget(), (tour.skip, tour.back, tour.next))
        win.settings.remove(TOUR_KEYS["catalog"])
        guikit.click(win.career.roadmap.tour_help)
        tour = self.visible_tour(win, "catalog")
        tour.steps[1][0].deleteLater()
        guikit.pump()
        guikit.click(tour.next)
        self.assertFalse(tour.active)
        self.assertFalse(win.settings.contains(TOUR_KEYS["catalog"]))

    def test_small_window_large_text_both_themes_and_all_contexts(self):
        self.win = win = self.fixture.boot()
        win.resize(760, 480)
        win.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.career.replay_tours()
            for context in ("catalog", "detail", "magazine"):
                if context == "detail":
                    page = win.career.roadmap
                    page._open_catalog_role(next(iter(page.gallery.cards)))
                elif context == "magazine":
                    win.go_magazine()
                tour = self.visible_tour(win, context)
                for step in range(len(tour.steps)):
                    guikit.pump()
                    self.assertTrue(tour.rect().contains(tour.card.geometry()), (context, step, tour.card.geometry(), tour.rect()))
                    self.assertFalse(tour.anchor.intersects(tour.card.geometry()), (context, step))
                    for button in (tour.skip, tour.back, tour.next):
                        self.assertTrue(tour.card.rect().contains(button.rect().translated(button.mapTo(tour.card, QPoint()))))
                        self.assertGreaterEqual(button.width(), button.sizeHint().width())
                    self.capture(win, f"career-tour-{context}-{step}-{mode}")
                    guikit.click(tour.next)
            page = win.career.magazine
            page._change_tab(1)
            guikit.click(page.tour_help)
            tour = self.visible_tour(win, "magazine")
            guikit.click(tour.next)
            self.assertTrue(tour.rect().contains(tour.card.geometry()))
            self.assertFalse(tour.anchor.intersects(tour.card.geometry()))
            self.capture(win, f"career-tour-paper-{mode}")
            guikit.click(tour.next)

    def capture(self, win, name):
        if not os.environ.get("CAREER_EVIDENCE"):
            return
        from tests.test_gui_career_integration import CareerIntegrationTest
        CareerIntegrationTest.capture_navigation(self, win, name)


if __name__ == "__main__":
    unittest.main()
