# -*- coding: utf-8 -*-
"""기존 사용자의 첫 본인 확인과 팀 전용 통계의 배치를 확인함."""
import datetime
from types import SimpleNamespace
import unittest
from unittest import mock
from tests import guikit

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QToolTip, QWidget

from gui import kit, theme
from gui.team_dashboard import MetricCard, MetricInfo, PERIODS, TeamCard
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
            return {"total": 5000, "days": days, "installations": 12, "period_installations": 3, "accounts": 10, "period_accounts": 2,
                    "graded": {"total": 1000, "period_total": sum(row["python"] for row in rows), "undated": 100, "unknown": 0, "series": rows}}
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
        return {"total": 20000, "period_total": 4000, "undated": 20, "series": [dict(row, ai=0) for row in rows],
                "graded": {"total": 12000, "period_total": sum(row["python"] + row["ai"] for row in rows),
                           "undated": 9, "unknown": 13, "series": rows}, "days": days, "as_of": "2026-11-13T17:20:00+09:00",
                "installations": 41, "period_installations": 11, "accounts": 32, "period_accounts": 8}

    def test_period_changes_all_visible_counts_and_never_replaces_the_lifetime_totals(self):
        for days in (1, 7, 15, 30):
            self.card.buttons[days].click()
            result = self.result(days)["graded"]
            self.assertEqual("12,000건", self.card.total.text())
            self.assertEqual("32개", self.card.accounts.text())
            self.assertEqual("41대", self.card.installations.text())
            self.assertEqual(f"{PERIODS[days]} 채점 {result['period_total']:,}건", self.card.graded_period.text())
            self.assertEqual(format(result["period_total"], ",") + "건", self.card.period_total.text())
            for key in ("python", "ai"):
                count = sum(row[key] for row in result["series"])
                self.assertEqual(format(count, ",") + "건", self.card.subject_totals[key].text())
            self.assertEqual(result["series"], self.card.chart.rows)
            self.assertIn("시간별" if days == 1 else "일별", self.card.range.text())
            self.assertIn("채점 시각을 알 수 없는 9건", self.card.total_info.toolTip())
            self.assertIn("답 작성 여부를 확인할 수 없는 13건", self.card.total_info.toolTip())
            self.assertIn("시각을 알 수 없는 20건", self.card.raw_info.toolTip())
            self.assertNotIn("미확인", self.card.note.text())
            self.assertEqual("11월 13일 17:20 기준", self.card.as_of.text())
            self.assertNotIn("17:20", self.card.note.text())

    def test_as_of_belongs_to_the_displayed_response_and_uses_korean_time(self):
        self.identity.summary.side_effect = None
        result = self.result(7)
        del result["graded"]
        for timestamp, expected in (("2026-11-13T23:15:00+00:00", "11월 14일 08:15 기준"),
                                    (None, "기준 시각 미확인"), ("invalid", "기준 시각 미확인"),
                                    ("2026-11-13T17:20:00", "기준 시각 미확인")):
            self.identity.summary.return_value = dict(result, as_of=timestamp)
            self.card.fetch()
            self.assertTrue(self.card.as_of.isVisible())
            self.assertEqual(expected, self.card.as_of.text())
            self.assertNotIn(expected, self.card.note.text())

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
                title, stamp, reload = [w.rect().translated(w.mapTo(self.card, QPoint()))
                                        for w in (self.card.heading, self.card.as_of, self.card.reload)]
                self.assertFalse(stamp.intersects(reload))
                self.assertFalse(title.intersects(reload))
                if stamp.top() < title.bottom():
                    self.assertEqual(stamp.left() - title.right() - 1, 12)
                else:
                    self.assertFalse(side)
                    self.assertEqual(stamp.left(), title.left())
                self.assertGreaterEqual(stamp.width(), self.card.as_of.sizeHint().width())
                points = [value.mapTo(self.card, QPoint()) for value in self.card.values.values()]
                self.assertEqual(1 if side else 2, len({point.y() for point in points}))
                self.assertEqual(4 if side else 2, len({point.x() for point in points}))
                totals = [self.card.total, self.card.raw, self.card.accounts, self.card.installations]
                activity_cards = [v.parentWidget().parentWidget() for v in self.card.values.values()]
                total_cards = [v.parentWidget().parentWidget() for v in totals]
                for upper, lower in zip(activity_cards, total_cards):
                    self.assertIsInstance(lower, MetricCard)
                    self.assertEqual(upper.width(), lower.width())
                    self.assertEqual(upper.mapTo(self.card, QPoint()).x(), lower.mapTo(self.card, QPoint()).x())
                    self.assertEqual(upper.value.font(), lower.value.font())
                positions = [v.mapTo(self.card, QPoint()).y() for v in totals]
                self.assertEqual(1 if side else 2, len(set(positions)))
                for key, value in self.card.values.items():
                    info = self.card.infos[key]
                    self.assertIs(value.parentWidget(), info.parentWidget())
                    self.assertGreater(info.x(), value.x())
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
        empty["graded"]["period_total"] = 0
        empty["graded"]["series"] = [dict(row, python=0, ai=0) for row in empty["graded"]["series"]]
        self.identity.summary.side_effect = None
        self.identity.summary.return_value = empty
        self.card.fetch()
        self.assertEqual("0건", self.card.period_total.text())
        self.assertIn("채점한 풀이가 없습니다", self.card.chart.message)
        self.assertFalse(self.card.plot_card.isHidden())
        self.identity.summary.side_effect = CollectionError("연결을 확인해 주세요.")
        self.card.fetch()
        self.assertTrue(self.card.plot_card.isHidden())
        self.card.show_metric("opens")
        self.assertIsNone(self.card.result)
        self.assertTrue(self.card.metrics.isHidden())
        self.assertTrue(self.card.summary.isHidden())
        self.assertTrue(self.card.as_of.isHidden())
        self.assertTrue(self.card.note.isVisible())
        self.assertIn("연결을 확인", self.card.note.text())
        self.assertTrue(self.card.reload.isEnabled())
        self.assertTrue(self.card.reverify.isHidden())
        self.identity.summary.side_effect = CollectionError("다시 인증해 주세요.", status=403)
        self.card.fetch()
        self.assertFalse(self.card.reverify.isHidden())
        self.identity.summary.side_effect = self.result
        self.card.fetch()
        self.assertFalse(self.card.metrics.isHidden())
        self.assertFalse(self.card.summary.isHidden())
        self.assertTrue(self.card.as_of.isVisible())
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

    def test_old_server_keeps_accounts_without_showing_event_counts_as_attempts(self):
        old = self.result(7)
        del old["graded"]
        self.identity.summary.side_effect = None
        self.identity.summary.return_value = old
        self.card.fetch()
        self.card.show_metric("inputs")
        self.assertFalse(self.card.metric_buttons["inputs"].isEnabled())
        self.assertEqual("–", self.card.values["cards"].text())
        self.assertEqual("–", self.card.total.text())
        self.assertEqual("최근 7일 채점 미확인", self.card.graded_period.text())
        self.assertTrue(self.card.plot_card.isHidden())
        self.assertEqual("32개", self.card.accounts.text())
        self.assertIn("아직 제공하지 않습니다", self.card.note.text())
        self.identity.summary.side_effect = self.result
        self.card.fetch()
        self.assertFalse(self.card.plot_card.isHidden())
        self.assertEqual("12,000건", self.card.total.text())

    def test_metric_switch_uses_cached_period_and_preserves_unmeasured_inputs(self):
        result = self.result(7)
        open_rows = [dict(row, python=1, ai=0) for row in result["series"]]
        result["activity"] = dict(distinct_cards=4, opens=open_rows,
                                  inputs=[dict(row, python=1, ai=None, ai_unmeasured=True) for row in open_rows],
                                  graded_metadata=dict(stem=1, concepts=2, revision=3, difficulty=0, ordered_timed=4,
                                                       linked_input=0), period_first_ai_measurement_at=None, ai_input_schema=1)
        self.identity.summary.side_effect = None
        self.identity.summary.return_value = result
        self.card.fetch()
        self.identity.summary.reset_mock()
        self.assertTrue(self.card.metric_buttons["graded"].isChecked())
        self.assertTrue(self.card.note.isHidden())
        self.assertEqual("20,000건", self.card.raw.text())
        self.assertEqual("최근 7일 수집 4,000건", self.card.raw_period.text())
        self.assertEqual("최근 7일 신규 8개", self.card.account_period.text())
        self.assertEqual("최근 7일 첫 실행 11대", self.card.device_period.text())
        self.assertIs(self.card.raw_info.anchor, self.card.raw)
        self.assertEqual("4개", self.card.values["cards"].text())
        self.assertEqual("7회", self.card.values["opens"].text())
        self.assertEqual("7회", self.card.values["inputs"].text())
        self.assertIn("기록된 입력 변경", self.card.infos["inputs"].accessibleName())
        self.assertNotIn("다시 풀고", self.card.note.text())
        self.card.metric_buttons["inputs"].click()
        self.assertEqual("관측 7건", self.card.period_total.text())
        self.assertEqual("미측정", self.card.subject_totals["ai"].text())
        self.assertIn("AI 미측정", self.card.chart.describe(0))
        self.card.metric_buttons["opens"].click()
        self.assertIn("문제 열기", self.card.chart.accessibleName())
        self.identity.summary.assert_not_called()
        self.assertEqual(4, len({info.toolTip() for info in self.card.infos.values()}))
        info = self.card.infos["graded"]
        self.assertIn("다시 풀고", info.toolTip())
        QApplication.setActiveWindow(self.root)
        with mock.patch("gui.team_dashboard.QToolTip.showText") as show, mock.patch("gui.team_dashboard.QToolTip.hideText") as hide:
            info.setFocus(Qt.FocusReason.TabFocusReason)
            guikit.pump()
            self.assertTrue(show.called)
            show.reset_mock()
            info.click()
            show.assert_called_once()
            QTest.keyClick(info, Qt.Key.Key_Escape)
            self.assertTrue(hide.called)
        result["activity"]["distinct_cards"] = 0
        result["activity"]["opens"] = [dict(row, python=0, ai=0) for row in open_rows]
        self.card.fetch()
        self.assertEqual("0개", self.card.values["cards"].text())
        self.assertEqual("0회", self.card.values["opens"].text())

    def test_count_tooltips_follow_max_text_and_fit_both_themes(self):
        theme.set_text("larger")
        kit.refont(self.root)
        available = self.root.screen().availableGeometry()
        self.root.resize(620, min(700, available.height() - 96))
        self.root.move(available.topLeft() + QPoint(24, 24))
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            for info in self.card.findChildren(MetricInfo):
                self.scroll.ensureWidgetVisible(info)
                info.setFocus(Qt.FocusReason.TabFocusReason)
                info.show_tip()
                guikit.pump(30)
                tips = [w for w in QApplication.topLevelWidgets() if w.windowType() == Qt.WindowType.ToolTip
                        and w.isVisible() and getattr(w, "text", lambda: "")() == info.toolTip()]
                self.assertEqual(len(tips), 1)
                tip = tips[0]
                self.assertTrue(tip.screen().availableGeometry().contains(tip.frameGeometry()))
                self.assertEqual(tip.font().pixelSize(), theme.TYPE["caption"][0])
                self.assertEqual(info.accessibleDescription(), info.toolTip())
                QTest.keyClick(info, Qt.Key.Key_Escape)
        QToolTip.hideText()
        self.capture_widget = self.root

    def test_metric_info_matches_actual_text_pixels_in_both_themes_and_sizes(self):
        self.alignment_samples = []
        def center(widget):
            image = widget.grab().toImage()
            bg = image.pixelColor(0, 0)
            rows = []
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    ink = color.alpha() > 64 if bg.alpha() < 64 else max(
                        abs(color.red() - bg.red()), abs(color.green() - bg.green()), abs(color.blue() - bg.blue())) > 64
                    if ink:
                        rows.append(y)
                        break
            self.assertTrue(rows, widget.objectName())
            return widget.mapTo(self.root, QPoint()).y() * image.devicePixelRatio() + (min(rows) + max(rows)) / 2

        measured = self.result(7)
        rows = measured['graded']['series']
        open_rows = [dict(row, python=row['python'] + 12) for row in rows]
        measured['activity'] = dict(distinct_cards=128, opens=open_rows, inputs=[dict(row, ai=None) for row in rows],
            graded_metadata=dict(stem=1, concepts=2, revision=3, difficulty=4, ordered_timed=5, linked_input=0),
            period_first_ai_measurement_at=None, ai_input_schema=1)
        self.assertLessEqual(measured['activity']['distinct_cards'],
                             sum(row['python'] + row['ai'] for row in open_rows))
        unmeasured = self.result(7)
        unsupported = dict(self.result(7), graded=None, period_total=None)
        self.identity.summary.side_effect = None
        for state, result in (('measured', measured), ('unmeasured', unmeasured), ('unsupported', unsupported)):
            self.identity.summary.return_value = result
            self.card.fetch()
            if result['period_total'] is None:
                self.assertIn('기간별 수집 기록 수를 아직 제공하지 않습니다', self.card.raw_info.toolTip())
                self.assertEqual("최근 7일 수집 미확인", self.card.raw_period.text())
            for mode in ('light', 'dark'):
                theme.set_mode(mode)
                for step in ('normal', 'larger'):
                    theme.set_text(step)
                    kit.refont(self.root)
                    self.root.resize(620, min(700, self.root.screen().availableGeometry().height() - 48))
                    for info in self.card.findChildren(MetricInfo):
                        self.scroll.ensureWidgetVisible(info)
                        info.clearFocus()
                        QToolTip.hideText()
                        guikit.pump(20)
                        difference = abs(center(info) - center(info.anchor))
                        self.alignment_samples.append(dict(state=state, mode=mode, text_size=step,
                            metric=info.accessibleName(), text=info.anchor.text(), difference_device_px=difference,
                            device_ratio=info.devicePixelRatioF(), font=info.anchor.font().toString()))
                        self.assertLessEqual(difference, 1,
                                             (mode, step, info.accessibleName(), info.anchor.text()))
        self.capture_widget = self.root

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
