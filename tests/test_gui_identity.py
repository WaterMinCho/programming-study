# -*- coding: utf-8 -*-
"""기존 사용자의 첫 본인 확인과 팀 전용 통계의 배치를 확인함."""
import datetime
from types import SimpleNamespace
import unittest
from unittest import mock
from tests import guikit

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget

from gui import kit, theme
from gui.team_dashboard import TeamCard
from learning_data.collection import CollectionError
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
            return {"total": 1000, "period_total": sum(row["python"] for row in rows), "undated": 100, "days": days, "series": rows, "installations": 12, "period_installations": 3, "accounts": 10, "period_accounts": 2}
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


class TeamDashboardTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(theme.set_text, theme.state["text"])
        self.addCleanup(theme.set_mode, theme.state["mode"])
        self.identity = mock.Mock()
        self.identity.settings.return_value = {"verified": True, "team": True}
        self.identity.summary.side_effect = self.result
        self.controller = SimpleNamespace(identity=self.identity, job=None, ensure_identity=mock.Mock())
        self.controller.run_job = mock.Mock(side_effect=lambda message, work, done, **kwargs: done(work()))
        self.root = kit.page(QWidget())
        layout = kit.box(self.root, (32, 32, 32, 32))
        body = QWidget()
        inner = kit.box(body)
        self.card = TeamCard(self.controller)
        inner.addWidget(self.card)
        inner.addStretch(1)
        self.scroll = kit.scroll(body)
        layout.addWidget(self.scroll)
        self.root.resize(1400, 900)
        self.root.show()
        self.addCleanup(self.root.close)
        self.card.fetch()
        guikit.pump()

    @staticmethod
    def result(days):
        start = datetime.datetime(2026, 11, 13, tzinfo=datetime.timezone(datetime.timedelta(hours=9))) - datetime.timedelta(days=days - 1)
        rows = [{"at": (start + (datetime.timedelta(hours=n) if days == 1 else datetime.timedelta(days=n))).isoformat(),
                 "python": n + 1, "ai": 2 * n} for n in range(24 if days == 1 else days)]
        return {"total": 12000, "period_total": sum(row["python"] + row["ai"] for row in rows),
                "undated": 9, "days": days, "series": rows, "as_of": "2026-11-13T17:20:00+09:00",
                "installations": 41, "period_installations": 11, "accounts": 32, "period_accounts": 8}

    def test_period_changes_all_visible_counts_and_never_replaces_the_lifetime_totals(self):
        for days in (1, 7, 15, 30):
            self.card.buttons[days].click()
            result = self.result(days)
            self.assertEqual("12,000건", self.card.total.text())
            self.assertEqual("32개", self.card.accounts.text())
            self.assertEqual("41대", self.card.installations.text())
            self.assertEqual(format(result["period_total"], ",") + "건", self.card.period_total.text())
            for key in ("python", "ai"):
                count = sum(row[key] for row in result["series"])
                self.assertEqual(format(count, ",") + "건", self.card.subject_totals[key].text())
            self.assertEqual(result["series"], self.card.chart.rows)
            self.assertIn("시간별" if days == 1 else "일별", self.card.range.text())
            self.assertIn("시각 미확인 9건", self.card.note.text())
            self.assertIn("17:20 기준", self.card.note.text())

    def test_summary_and_chart_reflow_at_max_text_in_both_themes(self):
        theme.set_text("larger")
        kit.refont(self.root)
        available = self.root.screen().availableGeometry()
        wide = 1400 if guikit.APP.platformName() == "offscreen" else min(1400, available.width() - 48)
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for width, side in ((620, False), (wide, True), (620, False), (wide, True)):
                self.root.resize(width, 900)
                guikit.pump(60)
                self.assertEqual(side, self.card.metrics.side)
                self.assertEqual(side, self.card.chart_row.side)
                self.assertEqual(0, self.scroll.horizontalScrollBar().maximum())
                self.assertLessEqual(self.card.width(), self.scroll.viewport().width())
                for button in self.card.buttons.values():
                    point = button.mapTo(self.card, QPoint())
                    self.assertLessEqual(point.x() + button.width(), self.card.width())
                    self.assertGreaterEqual(button.width(), button.sizeHint().width())
                for value in (self.card.total, self.card.accounts, self.card.installations, self.card.period_total):
                    self.assertGreaterEqual(value.height(), value.heightForWidth(value.width()))
        self.capture_widget = self.root
        self.root.resize(760, 480)
        self.root.move(available.left() + 24, available.top() + 24)
        self.scroll.ensureWidgetVisible(self.card.chart)
        guikit.pump()

    def test_empty_and_failed_queries_are_distinct_and_retry_restores_counts(self):
        empty = self.result(7)
        empty["period_total"] = 0
        empty["series"] = [dict(row, python=0, ai=0) for row in empty["series"]]
        self.identity.summary.side_effect = None
        self.identity.summary.return_value = empty
        self.card.fetch()
        self.assertEqual("0건", self.card.period_total.text())
        self.assertIn("수집된 기록이 없습니다", self.card.chart.message)
        self.assertFalse(self.card.plot_card.isHidden())
        self.identity.summary.side_effect = CollectionError("연결을 확인해 주세요.")
        self.card.fetch()
        self.assertTrue(self.card.plot_card.isHidden())
        self.assertTrue(self.card.metrics.isHidden())
        self.assertIn("연결을 확인", self.card.note.text())
        self.assertTrue(self.card.reload.isEnabled())
        self.assertTrue(self.card.reverify.isHidden())
        self.identity.summary.side_effect = CollectionError("다시 인증해 주세요.", status=403)
        self.card.fetch()
        self.assertFalse(self.card.reverify.isHidden())
        self.identity.summary.side_effect = self.result
        self.card.fetch()
        self.assertFalse(self.card.metrics.isHidden())
        self.assertFalse(self.card.plot_card.isHidden())
        self.assertTrue(self.card.reverify.isHidden())
        self.assertEqual("12,000건", self.card.total.text())

    def test_late_reply_does_not_reopen_statistics_after_identity_change_or_revocation(self):
        for replacement in (False, True):
            self.controller.identity = self.identity
            self.identity.settings.return_value = {"team": True, "verified": True}
            self.controller.run_job.side_effect = None
            self.controller.run_job.return_value = True
            self.card.fetch()
            done = self.controller.run_job.call_args.args[2]
            if replacement:
                self.controller.identity = mock.Mock()
                self.controller.identity.settings.return_value = {"team": False, "verified": True}
            else:
                self.identity.settings.return_value = {"team": False, "verified": True}
            self.card.refresh_identity()
            done(self.result(7))
            self.assertTrue(self.card.isHidden())
            self.assertFalse(self.card.loading)

    def test_worker_failure_and_declined_job_restore_the_controls(self):
        self.controller.run_job.side_effect = None
        self.controller.run_job.return_value = True
        self.card.fetch()
        self.assertFalse(self.card.reload.isEnabled())
        self.controller.run_job.call_args.kwargs["on_fail"]()
        self.assertFalse(self.card.loading)
        self.assertTrue(self.card.reload.isEnabled())
        self.assertTrue(all(button.isEnabled() for button in self.card.buttons.values()))
        self.assertIn("불러오지 못했습니다", self.card.note.text())
        self.controller.run_job.return_value = False
        self.card.fetch()
        self.assertFalse(self.card.loading)
        self.assertTrue(self.card.reload.isEnabled())

    def test_new_team_identity_is_loaded_after_the_old_request_finishes(self):
        self.controller.run_job.side_effect = None
        self.controller.run_job.return_value = True
        self.card.fetch()
        done = self.controller.run_job.call_args.args[2]
        replacement = mock.Mock()
        replacement.settings.return_value = {"team": True, "verified": True}
        replacement.summary.side_effect = self.result
        self.controller.identity = replacement
        self.card.refresh_identity()
        self.controller.run_job.side_effect = lambda message, work, done, **kwargs: done(work())
        done(self.result(7))
        guikit.pump()
        self.assertIs(self.card.loaded, replacement)
        self.assertTrue(self.card.isVisible())
        replacement.summary.assert_called_once_with(7)

    def test_chart_dates_fit_and_keyboard_exposes_the_exact_bucket(self):
        for days in (1, 7, 15, 30):
            self.card.select(days)
            for width in (280, 450, 1200):
                self.card.chart.resize(width, 260)
                plot, ceiling, step = self.card.chart.plot_geometry()
                ticks = self.card.chart.tick_labels(plot)
                self.assertEqual(0, ceiling % step)
                for _, _, rect in ticks:
                    self.assertGreaterEqual(rect.left(), plot.left())
                    self.assertLessEqual(rect.right(), plot.right())
                for first, second in zip(ticks, ticks[1:]):
                    self.assertLessEqual(first[2].right(), second[2].left())
            self.card.chart.setFocus()
            QTest.keyClick(self.card.chart, Qt.Key.Key_Home)
            self.assertEqual(0, self.card.chart.active)
            self.assertIn("파이썬 1건", self.card.chart.accessibleDescription())
            QTest.keyClick(self.card.chart, Qt.Key.Key_End)
            self.assertEqual(len(self.card.chart.rows) - 1, self.card.chart.active)
