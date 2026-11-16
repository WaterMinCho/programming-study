# -*- coding: utf-8 -*-
"""첫 실행 동의를 공통으로 쓰는 수집 화면과 작은 창의 동작을 확인함."""
import json
import threading
from pathlib import Path
from unittest import mock

from tests import guikit

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFontMetricsF
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from gui import theme
from gui.ai_data import LearningDataDialog
from learning_data.collection import CollectionError
from tests.test_gui_ai import AiTest


class AiDataTest(AiTest):
    def test_consent_export_and_delete_leave_learning_records(self):
        win = self.boot(size=(760, 480))
        win.go_ai()
        guikit.click(win.ai_home.data_btn)
        dialog = win.ai_home.data_dialog
        self.assertTrue(win.ai.collection.status()["enabled"])
        guikit.click(dialog.toggle)
        self.assertFalse(win.ai.collection.status()["enabled"])
        guikit.click(dialog.toggle)
        self.assertTrue(win.ai.collection.status()["enabled"])
        win.ai.mark_read("i90", "90a")
        original = Path(win.ai.record.path).read_bytes()
        destination = Path(self.tmp) / "export.jsonl"
        dialog.export_to(str(destination))
        rows = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
        self.assertFalse(rows[0]["include_answers"])
        self.assertIn("learn", [r["kind"] for r in rows])
        dialog.open_privacy()
        privacy = win.privacy.dialog
        privacy.confirm_withdraw()
        guikit.click(privacy.confirmation.buttons["cancel"])
        self.assertTrue(Path(win.ai.collection.path).exists())
        privacy.confirm_withdraw()
        guikit.click(privacy.confirmation.buttons["withdraw"])
        self.assertFalse(Path(win.ai.collection.path).exists())
        self.assertEqual(original, Path(win.ai.record.path).read_bytes())
        privacy.close()
        dialog.close()

    def test_small_dialog_buttons_are_reachable_in_both_themes(self):
        win = self.boot(size=(760, 480))
        win.go_ai()
        win.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            dialog = LearningDataDialog(win, win.ai.collection)
            dialog.show()
            guikit.pump()
            self.assertLessEqual(dialog.width(), 760)
            self.assertLessEqual(dialog.height(), 480)
            for section in (dialog.transfer_section, dialog.export_section, dialog.goal_section):
                guikit.click(section.header)
            for button in (dialog.toggle, dialog.goal_save, dialog.export_button, dialog.send_button):
                dialog.scroll.ensureWidgetVisible(button)
                guikit.pump()
                self.assertGreaterEqual(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()) + 24)
                point = button.mapTo(dialog.scroll.viewport(), QPoint())
                self.assertGreaterEqual(point.x(), 0)
                self.assertGreaterEqual(point.y(), 0)
                self.assertLessEqual(point.x() + button.width(), dialog.scroll.viewport().width())
                self.assertLessEqual(point.y() + button.height(), dialog.scroll.viewport().height())
            for button in (dialog.privacy_button, dialog.close_button):
                self.assertTrue(dialog.rect().contains(button.mapTo(dialog, button.rect().bottomRight())))
            dialog.close()

    def test_sections_keep_export_choice_and_unsaved_goal_during_sync(self):
        win = self.boot(size=(760, 480))
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        guikit.pump()
        self.assertFalse(dialog.export_section.body.isVisible())
        self.assertFalse(dialog.goal_section.body.isVisible())
        self.assertTrue(dialog.toggle.isVisible())
        dialog.export_section.header.setFocus()
        QTest.keyClick(dialog.export_section.header, Qt.Key.Key_Space)
        guikit.pump()
        self.assertTrue(dialog.export_section.body.isVisible())
        self.assertTrue(dialog.export_section.body.isAncestorOf(dialog.with_answers))
        dialog.with_answers.setChecked(True)
        dialog.goal_section.set_opened(True)
        dialog.goal_combo.setCurrentIndex(dialog.goal_combo.findData("vision"))
        win.privacy.message = "서버에 새 기록 1건을 전송했습니다."
        win.privacy.changed.emit()
        self.assertEqual("vision", dialog.goal_combo.currentData())
        self.assertTrue(dialog.with_answers.isChecked())
        self.assertTrue(dialog.export_section.opened)
        dialog.with_answers.setFocus()
        dialog.export_section.set_opened(False)
        guikit.pump()
        self.assertIs(dialog.export_section.header, QApplication.focusWidget())
        self.assertFalse(dialog.export_section.body.isVisible())
        dialog.close()

    def test_local_file_choice_does_not_send_or_change_consent(self):
        win = self.boot()
        win.ai.collection.emit("answer", {"response": ["예시 답안"], "result": "pass"})
        before = win.privacy.consent.path.read_bytes()
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        dialog.goal_section.set_opened(True)
        dialog.goal_combo.setCurrentIndex(dialog.goal_combo.findData("vision"))
        with mock.patch.object(win.privacy, "tick") as send:
            for include in (False, True):
                dialog.with_answers.setChecked(include)
                path = Path(self.tmp) / ("with-answer.jsonl" if include else "without-answer.jsonl")
                dialog.export_to(str(path))
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                answer = next(row["data"] for row in rows if row["kind"] == "answer")
                self.assertEqual(include, "response" in answer)
                self.assertEqual(include, rows[0]["include_answers"])
                self.assertEqual("vision", dialog.goal_combo.currentData())
            send.assert_not_called()
        self.assertEqual(before, win.privacy.consent.path.read_bytes())
        self.assertIsNone(win.ai.collection.status()["goal"]["goal_id"])
        dialog.close()

    def test_declined_paused_and_withdrawal_states_have_distinct_actions(self):
        win = self.boot()
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        guikit.pump()
        dialog.change_consent()
        self.assertEqual("수집 다시 시작", dialog.toggle.text())
        self.assertIn("수집 중단", dialog.status_text.text())
        with mock.patch.object(win, "show_privacy") as show:
            win.privacy.consent.choose(False)
            dialog.refresh()
            self.assertEqual("기록 제공 동의하기", dialog.toggle.text())
            guikit.click(dialog.toggle)
            show.assert_called_once()
            self.assertFalse(dialog.collection.status()["enabled"])
        win.privacy.consent.choose(True)
        win.privacy.consent.withdraw()
        dialog.show()
        dialog.refresh()
        self.assertIn("삭제 대기", dialog.status_text.text())
        self.assertFalse(dialog.toggle.isVisible())
        self.assertFalse(dialog.send_button.isEnabled())
        dialog.close()

    def test_goal_selection_consent_reset_and_export(self):
        win = self.boot(size=(760, 480))
        win.go_ai()
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        guikit.pump()
        self.assertTrue(dialog.goal_save.isEnabled())
        guikit.click(dialog.goal_section.header)
        dialog.goal_combo.setCurrentIndex(dialog.goal_combo.findData("vision"))
        dialog.scroll.ensureWidgetVisible(dialog.goal_save)
        guikit.pump()
        guikit.click(dialog.goal_save)
        win.ai.mark_read("i90", "90a")
        destination = Path(self.tmp) / "goal-export.jsonl"
        dialog.export_to(str(destination))
        rows = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
        learned = next(r for r in rows if r["kind"] == "learn")
        self.assertEqual("vision", learned["data"]["goal"]["goal_id"])
        self.assertEqual(64, len(learned["data"]["goal"]["roadmap_revision"]))
        for _ in range(2):
            dialog.scroll.ensureWidgetVisible(dialog.toggle)
            guikit.pump()
            guikit.click(dialog.toggle)
        self.assertIsNone(dialog.goal_combo.currentData())
        self.assertIsNone(win.ai.collection.status()["goal"]["goal_id"])
        dialog.close()

    def test_transfer_retry_and_unreadable_consent_show_current_state(self):
        win = self.boot()
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        with mock.patch.dict("os.environ", {"STUDY_AUTO_SYNC": "1"}):
            win.privacy.failures = 1
            win.privacy.message = "서버에 연결하지 못했습니다."
            dialog.refresh_transfer()
            self.assertEqual("전송 확인 필요", dialog.status_text.text())
            self.assertIn("전송 상태와 수집 항목", dialog.status_hint.text())
            with mock.patch.object(win.privacy, "job", object()):
                dialog.refresh_transfer()
                self.assertEqual("기록 전송 중", dialog.status_text.text())
                self.assertEqual(dialog.sync_status.text(), dialog.status_hint.text())
                self.assertNotIn("못했습니다", dialog.status_hint.text())
                self.assertFalse(dialog.send_button.isEnabled())
        win.privacy.consent.withdraw()
        dialog.refresh_transfer()
        self.assertIn("삭제 요청을 보내지 못했습니다", dialog.status_hint.text())
        self.assertEqual(dialog.status_hint.text(), dialog.sync_status.text())
        with mock.patch.object(win.privacy.consent, "settings", side_effect=CollectionError("동의 기록 확인 필요")):
            dialog.refresh_transfer()
            self.assertFalse(dialog.toggle.isVisible())
            self.assertFalse(dialog.send_button.isEnabled())
        dialog.close()

    def test_sync_job_survives_dialog_close_and_reopens_status(self):
        win = self.boot(size=(760, 480))
        win.go_ai()
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        release = threading.Event()
        with mock.patch.dict("os.environ", {"STUDY_AUTO_SYNC": "1"}), mock.patch.object(
                win.privacy.consent, "synchronize", side_effect=lambda *args, **kwargs: (release.wait(2), {"sent": 3})[1]):
            dialog.send()
            self.assertTrue(dialog.working)
            self.assertFalse(dialog.send_button.isEnabled())
            dialog.close()
            self.assertFalse(dialog.isVisible())
            self.assertTrue(win.isVisible())
            release.set()
            guikit.wait_until(lambda: win.privacy.job is None)
            self.assertFalse(dialog.working)
            self.assertTrue(dialog.send_button.isEnabled())
            self.assertIn("3건", dialog.sync_status.text())
        dialog.close()
