"""추천 입력·왕복·폐기와 작은 창의 조작 영역을 확인함."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests import guikit
from PyQt6.QtCore import QPoint, Qt, QSettings
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton, QWidget

from career.catalog import load_catalog
from gui import theme
from gui.career_recommend import CareerRecommendDialog
from gui.career_profile import ProfileStore, ProfileStorageError, decode
from career.recommend import Profile


class CareerRecommendGuiTest(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.state = dict(theme.state)
        self.windows = []
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = QSettings(str(Path(self.tmp.name) / "settings.ini"), QSettings.Format.IniFormat)
        self.store = ProfileStore(self.settings, "tester")

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        guikit.pump()
        theme.set_text(self.state["text"])
        theme.set_mode(self.state["mode"])

    def show(self, callback=None, store=None):
        parent = QWidget()
        parent.resize(792, 512)
        self.windows.append(parent)
        parent.show()
        dialog = CareerRecommendDialog(self.catalog, parent, on_select_goal=callback, profile_store=store)
        self.windows.append(dialog)
        dialog.resize(760, 480)
        dialog.move(dialog.screen().availableGeometry().topLeft() + QPoint(16, 32))
        dialog.show()
        self.capture_widget = dialog
        guikit.pump()
        return dialog

    def add_education(self, dialog, degree="bachelor", major="design"):
        dialog.education.add_row()
        fields = dialog.education.rows[-1][1]
        for field, value in zip(fields, (degree, major)):
            field.setCurrentIndex(field.findData(value))

    def test_partial_rows_block_only_until_selected_or_removed(self):
        dialog = self.show()
        for _ in range(6):
            self.add_education(dialog)
        dialog.education.add_row()
        guikit.click(dialog.next_button)
        self.assertEqual(dialog.stage, 0)
        self.assertTrue(dialog.error.isVisible())
        top = dialog.error.mapTo(dialog, QPoint())
        self.assertLessEqual(top.y() + dialog.error.height(), dialog.height())
        self.assertGreaterEqual(top.y(), dialog.shell.scroll.geometry().bottom())
        dialog.education.remove_row(dialog.education.rows[-1])
        self.assertFalse(dialog.error.isVisible())
        first = dialog.education.rows[0][1][0]
        QTest.keyClick(first, Qt.Key.Key_Return)
        self.assertEqual(len(dialog.education.rows), 6)
        guikit.click(dialog.next_button)
        self.assertEqual(dialog.stage, 1)
        dialog.experiences.add_row()
        field = dialog.experiences.rows[0][1][0]
        field.setCurrentIndex(field.findData("education"))
        guikit.click(dialog.next_button)
        self.assertEqual(dialog.stage, 2)

    def test_multiple_entries_interest_limit_and_no_automatic_goal_save(self):
        saved = Mock()
        dialog = self.show(saved)
        with patch("socket.socket", side_effect=AssertionError("네트워크 사용")):
            self.add_education(dialog)
            self.add_education(dialog, "master", "math")
            dialog.show_stage(1)
            dialog.experiences.add_row()
            field = dialog.experiences.rows[0][1][0]
            field.setCurrentIndex(field.findData("design"))
            dialog.activities["ui"].setChecked(True)
            dialog.show_stage(2)
            scenes = list(dialog.interests.cards)
            for scene in scenes[:3]:
                dialog.interests.cards[scene].click()
            self.assertFalse(dialog.interests.cards[scenes[3]].isEnabled())
            self.assertIn("해제하면", dialog.interests.cards[scenes[3]].accessibleDescription())
            dialog.interests.cards[scenes[0]].click()
            self.assertTrue(dialog.interests.cards[scenes[3]].isEnabled())
            before = dialog.profile()
            dialog.next()
            self.assertTrue(dialog.results)
            saved.assert_not_called()
            dialog.open_detail("frontend")
            self.assertEqual(dialog.stage, 4)
            saved.assert_not_called()
            dialog.detail.goal_button.click()
            saved.assert_called_once_with("frontend", "platform")
            dialog.back()
            self.assertEqual(dialog.stage, 3)
            self.assertEqual(dialog.profile(), before)
            dialog.open_detail("qa")
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
            self.assertEqual(dialog.stage, 3)
            self.assertEqual(dialog.profile(), before)

    def test_close_escape_and_clear_discard_input(self):
        for exit_kind in ("clear", "escape", "close"):
            dialog = self.show()
            self.add_education(dialog)
            dialog.activities["ui"].setChecked(True)
            dialog.interests._pick("frontend")
            if exit_kind == "clear":
                dialog.clear_button.click()
            elif exit_kind == "escape":
                QTest.keyClick(dialog, Qt.Key.Key_Escape)
            else:
                dialog.close()
            guikit.pump()
            profile = dialog.profile()
            self.assertFalse(profile.education or profile.experiences or profile.activities or profile.interests)
            self.assertEqual(dialog.results, ())

    def test_blank_answers_do_not_produce_fake_recommendations(self):
        dialog = self.show()
        for _ in range(3):
            dialog.next()
        self.assertEqual(dialog.stage, 3)
        self.assertFalse(dialog.results)
        self.assertTrue(dialog.back_button.isVisible())

    def test_resized_detail_does_not_leave_a_stale_scroll_restore(self):
        dialog = self.show()
        dialog.activities["ui"].setChecked(True)
        dialog.show_stage(2)
        dialog.next()
        guikit.pump()
        bar = dialog.shell.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        dialog.open_detail("frontend")
        dialog.resize(900, 700)
        guikit.pump()
        dialog.back()
        guikit.pump()
        self.assertFalse(dialog.restore_result)
        self.assertEqual(bar.value(), bar.maximum())
        dialog.show_stage(2)
        dialog.next()
        guikit.pump()
        self.assertFalse(dialog.restore_result)
        self.assertEqual(bar.value(), 0)

    def test_small_window_large_text_two_themes_and_detail_round_trip(self):
        theme.set_text("larger")
        for mode in ("light", "dark"):
            theme.set_mode(mode)
            dialog = self.show(store=self.store)
            dialog.clear_profile()
            for _ in range(6):
                self.add_education(dialog)
            dialog.activities["ui"].setChecked(True)
            for stage in range(3):
                dialog.show_stage(stage)
                self.assert_layout(dialog, mode, str(stage))
            dialog.interests._pick("frontend")
            dialog.next()
            self.assert_layout(dialog, mode, "results")
            bar = dialog.shell.scroll.verticalScrollBar()
            bar.setValue(bar.maximum() // 2)
            previous = bar.value()
            dialog.open_detail("frontend")
            self.assert_layout(dialog, mode, "detail")
            self.assertTrue(dialog.detail.sources_section.isHidden())
            dialog.back()
            guikit.pump()
            self.assertEqual(bar.value(), previous)
            self.assertEqual(len(dialog.profile().education), 6)

    def test_saved_input_survives_all_close_routes_and_can_be_edited_and_deleted(self):
        for exit_kind in ("button", "escape", "close"):
            with self.subTest(exit_kind=exit_kind), patch("socket.socket", side_effect=AssertionError("네트워크 사용")):
                dialog = self.show(store=self.store)
                self.add_education(dialog)
                dialog.education.add_row()  # 아직 고르지 않은 항목도 초안으로 보존함.
                dialog.experiences.add_row()
                dialog.activities["ui"].setChecked(True)
                dialog.interests._pick("frontend")
                expected = dialog.profile()
                if exit_kind == "button":
                    dialog.close_button.click()
                elif exit_kind == "escape":
                    QTest.keyClick(dialog, Qt.Key.Key_Escape)
                else:
                    dialog.close()
                guikit.pump()
                # 새 QSettings 인스턴스로 디스크 저장을 확인함.
                settings = QSettings(self.settings.fileName(), QSettings.Format.IniFormat)
                reopened = self.show(store=ProfileStore(settings, "tester"))
                self.assertEqual(reopened.profile(), expected)
                self.assertEqual(reopened.interest_count.text(), "1 / 3개 선택")
                field = reopened.education.rows[0][1][1]
                field.setCurrentIndex(field.findData("math"))
                self.assertEqual(self.store.load().education[0].major, "math")
                self.assertEqual(ProfileStore(settings, "someone-else").load(), Profile())
                settings.setValue("career/role/tester", "frontend")
                reopened.clear_button.click()
                self.assertEqual(reopened.profile(), Profile())
                self.assertFalse(settings.contains(self.store.key))
                reopened.close()
                guikit.pump()
                self.assertFalse(settings.contains(self.store.key))
                self.assertEqual(settings.value("career/role/tester"), "frontend")
                self.assertEqual(self.store.load(), Profile())

    def test_unreadable_input_is_preserved_until_explicit_delete(self):
        for raw in ('{broken', '{"version": 42}', '{"version": true}',
                    '{"version":1,"education":[],"experiences":[],"activities":[],"interests":["unknown"]}'):
            with self.subTest(raw=raw):
                self.settings.setValue(self.store.key, raw)
                dialog = self.show(store=self.store)
                self.assertTrue(dialog.storage_error.isVisible())
                self.assertFalse(dialog.next_button.isEnabled())
                self.assertFalse(dialog.education.isEnabled())
                dialog.close()
                guikit.pump()
                self.assertEqual(self.settings.value(self.store.key), raw)
                dialog = self.show(store=self.store)
                dialog.clear_button.click()
                self.assertTrue(dialog.next_button.isEnabled())
                self.assertTrue(dialog.education.isEnabled())
                self.assertFalse(self.settings.contains(self.store.key))
                self.add_education(dialog)
                self.assertEqual(self.store.load(), dialog.profile())
                dialog.close()

    def test_failed_save_or_delete_keeps_input_and_displays_error(self):
        dialog = self.show(store=self.store)
        self.assertFalse(self.settings.contains(self.store.key))
        self.add_education(dialog)
        expected = dialog.profile()
        raw = self.settings.value(self.store.key)
        with patch.object(self.settings, "status", return_value=QSettings.Status.AccessError):
            dialog.clear_button.click()
            self.assertTrue(dialog.storage_error.isVisible())
            theme.set_text("larger")
            self.assert_layout(dialog, "light", "storage-error")
            self.assertEqual(dialog.profile(), expected)
            self.assertEqual(self.settings.value(self.store.key), raw)
            dialog.activities["ui"].setChecked(True)
            self.assertEqual(self.settings.value(self.store.key), raw)
            dialog.show_stage(1)
            self.assertTrue(dialog.storage_error.isVisible())
        dialog.activities["ui"].setChecked(False)
        dialog.activities["ui"].setChecked(True)
        self.assertFalse(dialog.storage_error.isVisible())
        self.assertEqual(self.store.load(), dialog.profile())

    def test_profile_keys_and_values_cannot_escape_the_saved_scope(self):
        import json
        self.store.save(Profile(activities=("ui",)))
        for user in ("", "a/b", "a\\b", None):
            with self.assertRaises(ValueError):
                ProfileStore(self.settings, user)
        other = ProfileStore(self.settings, "someone-else")
        other.delete()
        self.assertEqual(self.store.load().activities, ("ui",))
        self.assertEqual(ProfileStore(self.settings, "TESTER").load(), self.store.load())
        value = json.loads(self.settings.value(self.store.key))
        for field, invalid in (("version", True), ("version", 2), ("education", [["bachelor"]]),
                               ("education", [[[], "math"]]), ("experiences", [1]),
                               ("activities", [["ui"]]), ("interests", ["interaction"] * 4),
                               ("activities", ["ui", "ui"]), ("school", "not allowed")):
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                decode(json.dumps(dict(value, **{field: invalid})))

    def test_actual_settings_write_failure_is_reported_without_input(self):
        parent_file = Path(self.tmp.name) / "not-a-directory"
        parent_file.write_text("unchanged")
        settings = QSettings(str(parent_file / "settings.ini"), QSettings.Format.IniFormat)
        store = ProfileStore(settings, "tester")
        with self.assertRaises(ProfileStorageError) as caught:
            store.save(Profile(activities=("ui",)))
        self.assertNotIn("ui", str(caught.exception))
        self.assertNotEqual(settings.status(), QSettings.Status.NoError)
        self.assertEqual(parent_file.read_text(), "unchanged")

    def assert_layout(self, dialog, mode, stage):
        guikit.pump(100)
        self.assertLessEqual(dialog.width(), 760)
        self.assertLessEqual(dialog.height(), 480)
        area = dialog.detail if dialog.stage == 4 else dialog.shell.scroll
        self.assertGreater(area.height(), 100)
        self.assertFalse(dialog.shell.scroll.horizontalScrollBar().isVisible())
        for button in (dialog.close_button, dialog.clear_button, dialog.back_button, dialog.next_button):
            if not button.isVisible():
                continue
            top = button.mapTo(dialog, QPoint())
            self.assertGreaterEqual(top.x(), 0)
            self.assertLessEqual(top.x() + button.width(), dialog.width())
            self.assertLessEqual(top.y() + button.height(), dialog.height())
            self.assertGreaterEqual(button.width(), button.sizeHint().width())
        evidence = os.environ.get("CAREER_EVIDENCE")
        if evidence:
            target = Path(evidence)
            target.mkdir(parents=True, exist_ok=True)
            self.assertTrue(dialog.grab().save(str(target / f"recommend-{mode}-{stage}.png")))
            if os.name == "nt":
                self.assertTrue(dialog.screen().grabWindow(int(dialog.winId())).save(str(target / f"recommend-{mode}-{stage}-native.png")))
