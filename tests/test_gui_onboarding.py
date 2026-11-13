# -*- coding: utf-8 -*-
"""첫 화면 안내의 시작 순서·실제 대상·다시 보기를 검사함."""
import copy
import os
from pathlib import Path
import unittest

from tests import guikit, test_gui_hub
from PyQt6.QtCore import QPoint, QSettings, Qt
from PyQt6.QtTest import QTest

from gui import theme
from gui.onboarding import TOUR_KEY


class OnboardingTest(unittest.TestCase):
    def setUp(self):
        self.fixture = test_gui_hub.HubTest()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.settings.remove(TOUR_KEY)

    def test_identity_then_consent_then_one_tour(self):
        Path(os.environ["STUDY_AI_HOME"], "identity.json").unlink()
        consent = next(Path(os.environ["STUDY_PYTHON_HOME"]).rglob("learning-privacy.json"))
        consent.unlink()
        win = self.fixture.boot()
        self.assertTrue(win.identity_dialog.isVisible())
        self.assertIsNone(win.hub_tour)
        guikit.complete_identity(win)
        guikit.wait_until(lambda: hasattr(getattr(win, "privacy", None), "dialog"))
        dialog = win.privacy.dialog
        self.assertTrue(dialog.isVisible())
        self.assertIsNone(win.hub_tour)
        guikit.click(dialog.decline)
        guikit.wait_until(lambda: win.hub_tour and win.hub_tour.isVisible())
        self.assertFalse(win.privacy.consent.settings()["accepted"])
        self.assertFalse(win.settings.contains(TOUR_KEY))
        keys = set(win.settings.allKeys())
        guikit.click(win.hub_tour.skip)
        self.assertFalse(win.hub_tour.isVisible())
        self.assertEqual(set(win.settings.allKeys()), keys | {TOUR_KEY})
        win.go_home()
        win.go_hub()
        guikit.pump()
        self.assertFalse(win.hub_tour.isVisible())
        win.settings.sync()
        stored = QSettings(win.settings.fileName(), QSettings.Format.IniFormat)
        self.assertTrue(stored.value(TOUR_KEY, False, type=bool))

    def test_visible_controls_fit_and_switch_without_activating_targets(self):
        self.win = win = self.fixture.boot()
        guikit.wait_until(lambda: win.hub_tour and win.hub_tour.isVisible())
        tour, hub = win.hub_tour, win.hub
        before = copy.deepcopy(win.session.prof)
        calls = list(self.fixture.git.calls)
        win.resize(1280, 800)
        win.set_text("larger")
        guikit.wait_until(lambda: tour.target is win.workspace.buttons["python"])
        win.resize(760, 480)
        guikit.wait_until(lambda: tour.target is win.workspace.compact)
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            guikit.pump()
            panel = win.workspace.grab().toImage()
            ratio = panel.devicePixelRatio()
            point = tour.card.pos() + QPoint(24, 5)
            self.assertTrue(guikit.near(panel.pixelColor(int(point.x() * ratio), int(point.y() * ratio)), "surface"))
            for target in (win.workspace.compact, hub.next_btn, hub.settings_btn, hub.privacy_btn, hub.settings_panel.report_btn):
                with self.subTest(mode=mode, target=target.objectName()):
                    self.assertIs(tour.target, target)
                    self.assertTrue(tour.rect().contains(tour.card.geometry()))
                    self.assertFalse(tour.anchor.intersects(tour.card.geometry()))
                    center = tour.mapFromGlobal(target.mapToGlobal(target.rect().center()))
                    self.assertTrue(tour.anchor.contains(center))
                    self.assertIs(tour.parentWidget().childAt(center), tour)
                    if target is hub.settings_panel.report_btn:
                        self.assertTrue(hub.settings_panel.isVisible())
                        self.assertIs(tour.parentWidget(), hub.settings_panel)
                    for button in (tour.skip, tour.back, tour.next):
                        self.assertTrue(tour.card.rect().contains(button.rect().translated(button.mapTo(tour.card, QPoint()))))
                        self.assertGreaterEqual(button.width(), button.sizeHint().width())
                    QTest.mouseClick(tour, guikit.LEFT, pos=center)
                    guikit.click(tour.next)
            self.assertFalse(tour.isVisible())
            self.assertFalse(hub.settings_panel.isVisible())
            self.assertIs(win.pages.currentWidget(), hub)
            self.assertEqual(win.session.prof, before)
            self.assertEqual(self.fixture.git.calls, calls)
            win.show_hub_tour(replay=True)
            guikit.wait_until(lambda: tour.card.isVisible() and tour.target is win.workspace.compact)

    def test_replay_skips_disabled_target_and_restores_focus_and_scroll(self):
        self.fixture.settings.setValue(TOUR_KEY, True)
        win = self.fixture.boot()
        self.assertIsNone(win.hub_tour)
        hub = win.hub
        guikit.click(hub.settings_btn)
        hub.replay_tour.setFocus()
        scrollbar = hub.scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum() // 2)
        original = scrollbar.value()
        hub.next_btn.setEnabled(False)
        guikit.click(hub.replay_tour)
        tour = win.hub_tour
        guikit.click(tour.next)
        self.assertIs(tour.target, hub.settings_btn)
        guikit.click(tour.back)
        self.assertEqual(tour.step, 0)
        for target in (hub.settings_btn, hub.privacy_btn, hub.settings_panel.report_btn):
            guikit.click(tour.next)
            self.assertIs(tour.target, target)
        self.assertEqual(scrollbar.value(), original)
        scrollbar.setValue(0 if original else scrollbar.maximum())
        self.assertNotEqual(scrollbar.value(), original)
        for _ in range(5):
            QTest.keyClick(guikit.APP.focusWidget(), Qt.Key.Key_Tab)
            self.assertIn(guikit.APP.focusWidget(), (tour.skip, tour.back, tour.next))
        QTest.keyClick(guikit.APP.focusWidget(), Qt.Key.Key_Escape)
        guikit.pump()
        self.assertFalse(tour.isVisible())
        self.assertFalse(hub.settings_panel.isVisible())
        self.assertTrue(hub.settings_btn.hasFocus())
        self.assertEqual(scrollbar.value(), original)

    def test_report_step_reopens_settings_and_returns_to_previous_step(self):
        self.fixture.settings.setValue(TOUR_KEY, True)
        win = self.fixture.boot()
        menu = win.hub.settings_panel
        guikit.click(win.hub.settings_btn)
        guikit.click(menu.replay_tour)
        tour = win.hub_tour
        self.assertFalse(menu.isVisible())
        while tour.step < 4:
            guikit.click(tour.next)
        self.assertIs(tour.target, menu.report_btn)
        self.assertTrue(menu.isVisible())
        guikit.click(tour.back)
        self.assertFalse(menu.isVisible())
        self.assertIs(tour.target, win.hub.privacy_btn)
        guikit.click(tour.next)
        self.assertIs(tour.target, menu.report_btn)
        self.assertTrue(menu.isVisible())
        menu.dismiss()
        guikit.pump()
        self.assertFalse(tour.isVisible())
        self.assertIs(tour.parentWidget(), win.workspace)
        win.show_hub_tour(replay=True)
        while tour.step < 4:
            guikit.click(tour.next)
        self.assertTrue(menu.isVisible())
        guikit.click(tour.next)
        self.assertFalse(menu.isVisible())
        self.assertFalse(tour.isVisible())
