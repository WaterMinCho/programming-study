"""커리어 첫 안내의 표시·키보드·기록 보존과 실제 배치를 검사함."""
import copy
import json
import os
from pathlib import Path
import threading
import unittest
from unittest import mock

from tests import guikit, test_gui_hub
from PyQt6.QtCore import QEvent, QPoint, QSettings, Qt
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

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

    def settle_tour(self, tour):
        previous, stable = None, 0

        def ready():
            nonlocal previous, stable
            self.assertTrue(tour.active, (tour.context, tour.step, tour.anchor, tour.card.geometry()))
            self.assertTrue(tour.isVisible())
            current = (tour.size(), tour.anchor, tour.card.geometry(), tour.target.size(),
                       tour.target.mapTo(tour.page, QPoint()), tour.description.size())
            stable = stable + 1 if current == previous else 0
            previous = current
            return stable >= 2 and not tour.timer.isActive()

        guikit.wait_until(ready, timeout=5)

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

    def test_background_job_dismisses_tour_and_waits_for_result_dialog(self):
        win = self.fixture.boot()
        win.go_career()
        tour = self.visible_tour(win, "catalog")
        release = threading.Event()

        def updates():
            release.wait(3)
            return {"status": "ok", "available": False, "count": 0}

        with mock.patch.object(win.gitflow, "updates", side_effect=updates):
            try:
                win.check_updates()
                self.assertIsNone(win.career.tour)
                self.assertFalse(win.career.tour_timer.isActive())
                self.assertFalse(tour.active)
                self.assertFalse(win.settings.contains(TOUR_KEYS["catalog"]))
            finally:
                release.set()
            self.fixture.idle()
        self.assertTrue(win.dialog.isVisible())
        self.assertIsNone(win.career.tour)
        win.dialog.close()
        self.visible_tour(win, "catalog")

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
                    self.settle_tour(tour)
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
            self.settle_tour(tour)
            self.assertTrue(tour.rect().contains(tour.card.geometry()))
            self.assertFalse(tour.anchor.intersects(tour.card.geometry()))
            self.capture(win, f"career-tour-paper-{mode}")
            guikit.click(tour.next)

    def test_magazine_tour_fits_wider_text_without_dismissing(self):
        for key in TOUR_KEYS.values():
            self.fixture.settings.setValue(key, True)
        self.win = win = self.fixture.boot()
        win.resize(760, 480)
        win.set_text("larger")
        win.go_magazine()
        page = win.career.magazine
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for extra_height in (0, 4):
                guikit.wait_until(lambda: not page._settling, timeout=5)
                original_scroll = page.scroll.verticalScrollBar().value()
                win.career.queue_tour(page, replay=True)
                tour = self.visible_tour(win, "magazine")
                self.settle_tour(tour)
                # 임시 화면에서 글꼴 폭과 높이가 모두 늘어난 조건을 재현함.
                font = QFont(tour.description.font())
                font.setStretch(120)
                font.setPixelSize(font.pixelSize() + extra_height)
                tour.description.setFont(font)
                guikit.click(tour.next)
                self.settle_tour(tour)
                self.assertTrue(tour.rect().contains(tour.card.geometry()))
                self.assertFalse(tour.anchor.intersects(tour.card.geometry()))
                self.assertEqual(1, tour.step)
                viewport = page.scroll.viewport()
                room = viewport.rect().translated(viewport.mapTo(tour.page, QPoint()))
                self.assertTrue(room.contains(tour.anchor))
                self.assertGreaterEqual(tour.anchor.height(), min(tour.target.height(), theme.control_height("l")))
                for button in (tour.skip, tour.back, tour.next):
                    self.assertTrue(tour.card.rect().contains(button.rect().translated(button.mapTo(tour.card, QPoint()))))
                self.capture(win, f"career-tour-wider-text-{mode}-{extra_height}")
                guikit.click(tour.next)
                self.assertFalse(tour.isVisible())
                guikit.wait_until(lambda: not page._settling, timeout=5)
                self.assertEqual(original_scroll, page.scroll.verticalScrollBar().value())

    def capture(self, win, name):
        if not os.environ.get("CAREER_EVIDENCE"):
            return
        from tests.test_gui_career_integration import CareerIntegrationTest
        CareerIntegrationTest.capture_navigation(self, win, name)
        tour = win.career.tour
        measured = dict(active=tour.active, context=tour.context, step=tour.step,
                        window=[win.width(), win.height()], page=[tour.width(), tour.height()],
                        anchor=tour.anchor.getRect(), card=tour.card.geometry().getRect(),
                        scroll=tour.page.scroll.verticalScrollBar().value(), previous_scroll=tour.previous_scroll,
                        platform=guikit.APP.platformName(), dpr=win.devicePixelRatioF())
        (Path(os.environ["CAREER_EVIDENCE"]) / (name + ".json")).write_text(
            json.dumps(measured, indent=2), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
