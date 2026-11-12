# -*- coding: utf-8 -*-
"""첫 실행 동의를 공통으로 쓰는 수집 화면과 작은 창의 동작을 확인함."""
import json
import threading
from pathlib import Path
from unittest import mock

from tests import guikit

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QFontMetricsF

from gui import theme
from gui.ai_data import LearningDataDialog
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
        dialog.confirm_delete()
        guikit.click(dialog.confirmation.buttons["cancel"])
        self.assertTrue(Path(win.ai.collection.path).exists())
        dialog.confirm_delete()
        guikit.click(dialog.confirmation.buttons["delete"])
        self.assertFalse(Path(win.ai.collection.path).exists())
        self.assertEqual(original, Path(win.ai.record.path).read_bytes())
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
            for button in (dialog.toggle, dialog.goal_save, dialog.export_button, dialog.delete_button, dialog.send_button, dialog.privacy_button):
                dialog.scroll.ensureWidgetVisible(button)
                guikit.pump()
                self.assertGreaterEqual(button.width(), QFontMetricsF(button.font()).horizontalAdvance(button.text()) + 24)
                point = button.mapTo(dialog.scroll.viewport(), QPoint())
                self.assertGreaterEqual(point.x(), 0)
                self.assertGreaterEqual(point.y(), 0)
                self.assertLessEqual(point.x() + button.width(), dialog.scroll.viewport().width())
                self.assertLessEqual(point.y() + button.height(), dialog.scroll.viewport().height())
            dialog.close()

    def test_goal_selection_consent_reset_and_export(self):
        win = self.boot(size=(760, 480))
        win.go_ai()
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        guikit.pump()
        self.assertTrue(dialog.goal_save.isEnabled())
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
