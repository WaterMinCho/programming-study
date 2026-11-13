# -*- coding: utf-8 -*-
"""기존 사용자의 첫 본인 확인과 팀 전용 통계의 배치를 확인함."""
import datetime
from unittest import mock

from PyQt6.QtCore import QPoint

from gui import theme
from tests import guikit
from tests.test_gui_hub import HubTest


class IdentityGuiTest(HubTest):
    def test_unverified_existing_device_is_prompted_and_fits_max_text_both_themes(self):
        win = self.boot()
        before = win.session.prof.copy()
        win.identity.path.unlink()
        win.resize(760, 480)
        win.set_text("larger")
        self.assertFalse(win.ensure_identity())
        dialog = self.capture_widget = win.identity_dialog
        self.assertTrue(dialog.isVisible())
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            guikit.pump()
            for button in (dialog.begin_button, dialog.cancel_button):
                point = button.mapTo(dialog, QPoint())
                self.assertGreaterEqual(point.y(), 0)
                self.assertLessEqual(point.y() + button.height(), dialog.height())
                self.assertGreaterEqual(button.width(), button.sizeHint().width())
        self.assertEqual(before, win.session.prof)

    def test_team_statistics_switch_period_and_are_hidden_for_other_users(self):
        win = self.boot()
        win.resize(760, 480)
        win.set_text("larger")
        def summary(days):
            count = 24 if days == 1 else days
            rows = [{"at": (datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=n)).isoformat(), "python": n + 1, "ai": 0} for n in range(count)]
            return {"total": 1000, "period_total": sum(row["python"] for row in rows), "undated": 100, "days": days, "series": rows, "installations": 12, "period_installations": 3}
        identity = mock.Mock()
        identity.settings.return_value = {"verified": True, "team": True}
        identity.summary.side_effect = summary
        win.identity = identity
        win.hub.refresh()
        self.idle()
        card = win.hub.team_card
        self.assertTrue(card.isVisible())
        self.assertIn("1,000", card.total.text())
        for days in (1, 7, 15, 30):
            guikit.click(card.buttons[days])
            self.idle()
            self.assertEqual(24 if days == 1 else days, len(card.chart.rows))
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            win.restyle()
            guikit.pump()
            self.assertLessEqual(card.width(), win.width())
            self.assertEqual(0, win.hub.findChildren(type(win.ai_home.scroll))[0].horizontalScrollBar().maximum())
        identity.settings.return_value = {"verified": True, "team": False}
        win.hub.refresh()
        self.assertFalse(card.isVisible())
        identity.settings.return_value = {"verified": True, "team": True}
        card.loaded = None
        win.hub.refresh()
        self.idle()
        self.assertTrue(card.isVisible())
        scroll = win.hub.findChildren(type(win.ai_home.scroll))[0]
        scroll.verticalScrollBar().setValue(card.mapTo(scroll.widget(), QPoint()).y())
        guikit.pump()
