# -*- coding: utf-8 -*-
"""화면 간 전송·철회·닫기와 공통 글자·하단 알림의 충돌을 확인함."""
from pathlib import Path
from unittest import mock

from tests import guikit, test_gui_hub, test_learning_privacy
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QBoxLayout, QScrollArea
from aiprep import privacy
from gui import theme
from gui.ai_data import LearningDataDialog
from gui.privacy import ConsentDialog, SyncController
from gui.submission_setup import SubmissionSetup
from learning_server.app import Database, application
from submission_api import PrivateClient


class GlobalConsistencyTest(test_gui_hub.HubTest):
    def test_populated_hub_and_map_reflow_without_horizontal_scroll_after_screen_changes(self):
        win = self.boot()
        win.start_next()
        self.idle()
        rid = win.round_page.view["id"]
        win.session.grade(rid, finalize=True)
        for step in ("larger", "normal", "larger"):
            win.set_text(step)
            for width in (760, 1280, 760):
                win.resize(width, 700)
                for selected in ("light", "dark"):
                    theme.set_mode(selected)
                    win.go_hub()
                    self.idle()
                    scroll = win.hub.findChild(QScrollArea)
                    self.assertEqual(0, scroll.horizontalScrollBar().maximum(), (step, width, selected, "hub"))
                    button = win.hub.next_btn
                    point = button.mapTo(scroll.viewport(), QPoint())
                    self.assertLessEqual(point.x() + button.width(), scroll.viewport().width())
                    win.go_journey()
                    self.idle()
                    self.assertEqual(0, win.journey_map.scroll.horizontalScrollBar().maximum(), (step, width, selected, "map"))

    def setup_submission(self, empty=False):
        win = self.boot()
        repo = Path(self.tmp) / "submit-repo"
        folder = repo / "submissions/tester/r01"
        folder.mkdir(parents=True)
        if not empty:
            (folder / "quiz.py").write_text("ANSWERS = {}\n", encoding="utf-8")
        self.git.api = PrivateClient(str(repo), "tester", {"python": win.session.collection, "ai": win.ai.collection})
        dialog = SubmissionSetup(win)
        dialog.show()
        guikit.pump()
        return win, dialog

    def test_canceling_close_keeps_sync_timer_and_resumes_a_deferred_close(self):
        win = self.boot()
        controller = win.privacy
        controller.timer.start(60000)
        with mock.patch.object(win, "leave_pages", return_value=False):
            win.close()
            self.assertTrue(win.isVisible())
            self.assertTrue(controller.timer.isActive())
            self.assertFalse(controller.closing)
            idle = SyncController(win, controller.consent.collections)
            win.privacy_controllers["second-profile"] = idle
            for item in (controller, idle):
                item.stop()
                self.assertTrue(item.closing)
                item.cancel.set()
            with mock.patch.dict("os.environ", {"STUDY_AUTO_SYNC": "1"}), mock.patch(
                    "gui.privacy.sync_schedule.initial_ms", return_value=60000):
                win.close()
            for item in (controller, idle):
                self.assertTrue(item.timer.isActive())
                self.assertFalse(item.closing)
                self.assertFalse(item.cancel.is_set())

    def test_outdated_consent_and_old_submission_can_be_deleted_without_new_agreement(self):
        win = self.boot()
        state = win.privacy.consent.settings()
        state["policy"] = "old-policy"
        privacy.save(win.privacy.consent.path, state)
        win.show_privacy()
        dialog = win.privacy.dialog
        guikit.pump()
        self.assertTrue(dialog.withdraw.isVisible())
        self.assertIn("동의 내용이 바뀌었습니다", dialog.status_text.text())
        self.assertFalse(dialog.agree.isEnabled())
        dialog.close()
        Path(win.ai.collection.path).touch()
        saved = win.privacy.consent.path.with_name("private-submission.json")
        saved.write_text("{}", encoding="utf-8")
        first = ConsentDialog(win, win.privacy, first=True)
        first.show()
        first.reject()
        self.assertFalse(win.privacy.consent.settings().get("withdraw_pending", False))
        self.assertTrue(Path(win.ai.collection.path).exists())
        self.assertTrue(saved.exists())
        state["accepted"] = False
        privacy.save(win.privacy.consent.path, state)
        for store in win.privacy.consent.collections.values():
            store.delete()
        win.privacy.consent.path.with_name("private-submission.json").write_text("{}", encoding="utf-8")
        win.show_privacy()
        guikit.pump()
        self.assertTrue(win.privacy.dialog.withdraw.isVisible())

    def test_data_delete_stops_every_track_and_cannot_reupload_after_confirmation(self):
        win = self.boot()
        wire = test_learning_privacy.PrivacyTest()
        wire.db = Database(Path(self.tmp) / "server/learning.sqlite3")
        wire.app = application(wire.db)
        win.ai.mark_read("i90", "90a")
        win.privacy.consent.server = "https://example.test"
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        with mock.patch.dict("os.environ", {"STUDY_OPEN_REGISTRATION": "1"}), mock.patch(
                "aiprep.sharing.request", side_effect=wire.transport):
            self.assertGreater(win.privacy.consent.synchronize()["sent"], 0)
            dialog.confirm_delete()
            guikit.click(dialog.confirmation.buttons["delete"])
            self.assertTrue(win.privacy.consent.settings()["withdraw_pending"])
            for store in win.privacy.consent.collections.values():
                self.assertFalse(store.status()["enabled"])
            self.assertTrue(win.privacy.consent.synchronize()["withdrawn"])
            self.assertEqual(0, win.privacy.consent.synchronize()["sent"])
        with wire.db.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM events").fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM participants WHERE revoked=0").fetchone()[0])

    def test_sync_status_does_not_overwrite_an_unsaved_goal(self):
        win = self.boot()
        dialog = LearningDataDialog(win, win.ai.collection)
        dialog.show()
        dialog.goal_combo.setCurrentIndex(dialog.goal_combo.findData("vision"))
        win.privacy.message = "서버에 새 기록 1건을 전송했습니다."
        win.privacy.changed.emit()
        self.assertEqual("vision", dialog.goal_combo.currentData())
        self.assertIsNone(win.ai.collection.status()["goal"]["goal_id"])
        self.assertIn("1건", dialog.sync_status.text())
        self.assertFalse(hasattr(dialog, "invite"))
        self.assertFalse(hasattr(dialog, "share_answers"))

    def test_busy_submission_keeps_confirmation_open_without_starting_a_second_job(self):
        win, dialog = self.setup_submission()
        dialog.confirm_private.setChecked(True)
        with mock.patch.object(win, "run_job", return_value=False) as job:
            guikit.click(dialog.connect_button)
        job.assert_called_once()
        self.assertTrue(dialog.isVisible())
        self.assertTrue(dialog.confirm_private.isChecked())
        self.assertIn("다른 작업", dialog.message.text())
        self.assertIn("r01/quiz.py", dialog.files.toPlainText())

    def test_empty_submission_explains_why_confirmation_is_disabled(self):
        win, dialog = self.setup_submission(empty=True)
        self.assertFalse(dialog.confirm_private.isEnabled())
        self.assertFalse(dialog.connect_button.isEnabled())
        self.assertIn("아직 제출할 풀이 파일이 없습니다", dialog.message.text())
        dialog.confirm_private.setChecked(True)
        with mock.patch.object(win, "run_job") as job:
            dialog.connect_and_submit()
        self.assertFalse(dialog.connect_button.isEnabled())
        job.assert_not_called()

    def test_native_list_and_confirmation_follow_font_changes_without_losing_selection(self):
        win, dialog = self.setup_submission()
        win.start_next()
        self.idle()
        win.round_page.listw.setCurrentRow(2)
        for step in ("normal", "larger", "normal"):
            win.set_text(step)
            for widget in (win.home.rounds, win.round_page.listw, win.result_page.listw):
                self.assertEqual(theme.TYPE["caption"][0], widget.font().pixelSize())
            self.assertEqual(theme.TYPE["body"][0], dialog.confirm_private.font().pixelSize())
            self.assertEqual(2, win.round_page.listw.currentRow())
        self.assertTrue(win.round_page.listw.item(2).toolTip())

    def test_single_pending_action_keeps_the_small_reminder_on_one_row(self):
        win = self.boot()
        win.resize(760, 480)
        win.set_text("larger")
        win.pending_submission = {"status": "ok", "pending": True, "count": 1}
        win.problem_updates = {"status": "ok", "available": False}
        win.workspace.refresh()
        guikit.pump()
        bar = win.workspace.submissions
        self.assertTrue(bar.isVisible())
        self.assertEqual(QBoxLayout.Direction.LeftToRight, bar.row.direction())
        self.assertLessEqual(bar.height(), bar.submit.height() + 34)
        self.assertGreaterEqual(bar.submit.width(), bar.submit.sizeHint().width())
