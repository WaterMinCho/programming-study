"""임시 사용자 설정으로 추천 저장·복원·무효화와 입력 보존을 확인함."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests import guikit
from PyQt6.QtCore import QPoint, QSettings

from career.catalog import load_catalog
import career.recommend as recommendation
from career.recommend import Profile, recommend
from gui import theme
from gui.career_profile import ProfileStore, ProfileStorageError, decode
from gui.career_recommend import CareerRecommendDialog


class RecommendationResultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "settings.ini")
        self.settings = QSettings(self.path, QSettings.Format.IniFormat)
        self.store = ProfileStore(self.settings, "tester")
        self.catalog = load_catalog()
        self.profile = Profile(experiences=("backend",))
        self.results = recommend(self.profile, self.catalog, include_experience_only=True)
        self.windows = []
        blocker = patch("socket.socket", side_effect=AssertionError("외부 연결 사용"))
        blocker.start()
        self.addCleanup(blocker.stop)

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        guikit.pump()

    def save(self):
        self.store.save(self.profile)
        self.store.save_result(self.profile, self.catalog, self.results)

    def dialog(self, store=None, callback=None):
        dialog = CareerRecommendDialog(self.catalog, profile_store=store or self.store,
                                       on_select_goal=callback, saved_role_id="qa")
        self.windows.append(dialog)
        return dialog

    def test_round_trip_uses_separate_key_and_minimal_fields(self):
        self.save()
        fresh = ProfileStore(QSettings(self.path, QSettings.Format.IniFormat), "TESTER")
        self.assertEqual(fresh.load_result(fresh.load(), self.catalog), self.results)
        raw = json.loads(self.settings.value(self.store.result_key))
        self.assertEqual(set(raw), {"input_fingerprint", "rules_version", "catalog_fingerprint", "role_ids"})
        self.assertEqual(raw["role_ids"], [row.role_id for row in self.results])
        self.assertEqual(raw["rules_version"], recommendation.VERSION)
        for key in ("input_fingerprint", "catalog_fingerprint"):
            self.assertRegex(raw[key], r"^[0-9a-f]{64}$")
        self.assertEqual(decode(self.settings.value(self.store.key)), self.profile)

    def test_another_user_cannot_load_or_delete_results(self):
        self.save()
        other = ProfileStore(self.settings, "other-tester")
        self.assertIsNone(other.load_result(self.profile, self.catalog))
        other.save(Profile(activities=("ui",)))
        other.delete()
        self.assertEqual(self.store.load_result(self.profile, self.catalog), self.results)
        self.assertEqual(self.store.load(), self.profile)

    def test_input_change_invalidates_result_but_identical_save_does_not(self):
        self.save()
        self.store.save(self.profile)
        self.assertTrue(self.settings.contains(self.store.result_key))
        changed = replace(self.profile, activities=("ui",))
        self.store.save(changed)
        self.assertFalse(self.settings.contains(self.store.result_key))
        self.assertEqual(self.store.load(), changed)

    def test_rule_version_change_invalidates_without_touching_profile(self):
        self.save()
        raw = self.settings.value(self.store.key)
        with patch.object(recommendation, "VERSION", "changed-rule"):
            self.assertIsNone(self.store.load_result(self.profile, self.catalog))
        self.assertFalse(self.settings.contains(self.store.result_key))
        self.assertEqual(self.settings.value(self.store.key), raw)

    def test_catalog_version_or_content_change_invalidates_result(self):
        roles = deepcopy(self.catalog.roles)
        roles[0]["title"] += " 변경"
        for changed in (replace(self.catalog, version="changed-catalog"), replace(self.catalog, roles=roles)):
            with self.subTest(version=changed.version):
                self.save()
                self.assertIsNone(self.store.load_result(self.profile, changed))
                self.assertFalse(self.settings.contains(self.store.result_key))
                self.assertEqual(self.store.load(), self.profile)

    def test_corrupt_missing_extra_or_reordered_result_does_not_damage_input(self):
        self.save()
        saved = json.loads(self.settings.value(self.store.result_key))
        cases = ["{broken", "null", "[]", "{}", "[" * 1200 + "]" * 1200, json.dumps(dict(saved, extra=1)),
                 json.dumps(dict(saved, role_ids=["not-a-role"])),
                 json.dumps(dict(saved, role_ids=saved["role_ids"][::-1])),
                 json.dumps(dict(saved, role_ids=saved["role_ids"] * 2)),
                 json.dumps(dict(saved, input_fingerprint="0" * 64))]
        original = self.settings.value(self.store.key)
        for raw in cases:
            with self.subTest(raw=raw):
                self.settings.setValue(self.store.result_key, raw)
                self.assertIsNone(self.store.load_result(self.profile, self.catalog))
                self.assertFalse(self.settings.contains(self.store.result_key))
                self.assertEqual(self.settings.value(self.store.key), original)

    def test_delete_also_removes_orphan_result_and_preserves_selected_role(self):
        self.save()
        self.settings.setValue("career/role/tester", "qa")
        self.store.delete()
        self.assertFalse(self.settings.contains(self.store.key))
        self.assertFalse(self.settings.contains(self.store.result_key))
        self.assertEqual(self.settings.value("career/role/tester"), "qa")
        self.settings.setValue(self.store.result_key, "{broken")
        self.store.delete()
        self.assertFalse(self.settings.contains(self.store.result_key))

    def test_legacy_v1_profile_can_be_used_without_rewriting_it(self):
        raw = '{"version": 1, "education": [], "experiences": ["backend"], "activities": [], "interests": []}'
        self.settings.setValue(self.store.key, raw)
        self.assertEqual(self.store.load(), self.profile)
        self.assertIsNone(self.store.load_result(self.profile, self.catalog))
        self.store.save_result(self.profile, self.catalog, self.results)
        self.assertEqual(self.settings.value(self.store.key), raw)
        self.assertEqual(self.store.load_result(self.profile, self.catalog), self.results)

    def test_result_cannot_be_saved_for_unsaved_or_different_input(self):
        with self.assertRaises(ProfileStorageError):
            self.store.save_result(self.profile, self.catalog, self.results)
        self.store.save(Profile(activities=("ui",)))
        with self.assertRaises(ProfileStorageError):
            self.store.save_result(self.profile, self.catalog, self.results)
        self.assertFalse(self.settings.contains(self.store.result_key))

    def test_failed_combined_delete_restores_both_values(self):
        self.save()
        original = {key: self.settings.value(key) for key in (self.store.key, self.store.result_key)}
        with patch.object(QSettings, "status", side_effect=[QSettings.Status.NoError] * 3 + [QSettings.Status.AccessError]):
            with self.assertRaises(ProfileStorageError):
                self.store.delete()
        self.assertEqual({key: self.settings.value(key) for key in original}, original)

    def test_request_then_reopen_restores_results_without_selecting_goal(self):
        callback = Mock()
        dialog = self.dialog(callback=callback)
        dialog.experiences.add_row()
        field = dialog.experiences.rows[-1][1][0]
        field.setCurrentIndex(field.findData("backend"))
        self.assertFalse(self.settings.contains(self.store.result_key))
        dialog.show_stage(2)
        self.assertEqual(dialog.next_button.text(), "추천받기")
        dialog.next_button.click()
        self.assertEqual(dialog.stage, 3)
        self.assertEqual(dialog.results, self.results)
        callback.assert_not_called()
        dialog.close()
        fresh = ProfileStore(QSettings(self.path, QSettings.Format.IniFormat), "tester")
        reopened = self.dialog(store=fresh, callback=callback)
        self.assertEqual(reopened.stage, 3)
        self.assertEqual(reopened.results, self.results)
        self.assertEqual(reopened.saved_role_id, "qa")
        callback.assert_not_called()
        reopened.back_button.click()
        reopened.activities["ui"].setChecked(True)
        self.assertFalse(self.settings.contains(self.store.result_key))
        self.assertEqual(reopened.results, ())
        reopened.close()
        self.assertEqual(self.dialog().stage, 0)

    def test_bad_result_reopens_editable_input_and_can_be_replaced(self):
        self.save()
        original = self.settings.value(self.store.key)
        self.settings.setValue(self.store.result_key, "{broken")
        dialog = self.dialog()
        self.assertEqual(dialog.stage, 0)
        self.assertTrue(dialog.next_button.isEnabled())
        self.assertEqual(dialog.profile(), self.profile)
        self.assertEqual(self.settings.value(self.store.key), original)
        dialog.show_stage(2)
        dialog.next()
        self.assertEqual(self.store.load_result(self.profile, self.catalog), self.results)

    def test_reopen_empty_results_starts_at_input_and_preserves_profile_and_goal(self):
        goal_key = "career/role/tester"
        goal = '{"role_id":"qa","catalog_version":"saved-version"}'
        for profile in (Profile(), Profile(experiences=("research",)), self.profile):
            with self.subTest(profile=profile):
                self.store.delete()
                self.store.save(profile)
                self.settings.setValue(goal_key, goal)
                original = self.settings.value(self.store.key)
                dialog = self.dialog()
                for _ in range(3):
                    dialog.next_button.click()
                results = dialog.results
                self.assertEqual(dialog.stage, 3)
                self.assertTrue(dialog.storage_error.isHidden())
                dialog.close()
                fresh = ProfileStore(QSettings(self.path, QSettings.Format.IniFormat), "tester")
                reopened = self.dialog(store=fresh)
                self.assertEqual(reopened.stage, 3 if results else 0)
                self.assertEqual(reopened.profile(), profile)
                self.assertEqual(reopened.results, results)
                self.assertTrue(reopened.storage_error.isHidden())
                self.assertEqual(self.settings.value(self.store.key), original)
                self.assertEqual(self.settings.value(goal_key), goal)
                reopened.close()

    def test_unreadable_profile_blocks_next_clicks_and_preserves_saved_values(self):
        self.save()
        self.settings.setValue(self.store.key, "{broken")
        self.settings.setValue("career/role/tester", "qa")
        original = {key: self.settings.value(key) for key in
                    (self.store.key, self.store.result_key, "career/role/tester")}
        dialog = self.dialog()
        dialog.show()
        guikit.pump()
        self.assertTrue(dialog.unreadable_profile)
        self.assertFalse(dialog.next_button.isEnabled())
        self.assertTrue(all(not panel.isEnabled() for panel in dialog.panels[:3]))
        for _ in range(3):
            guikit.click(dialog.next_button)
        self.assertEqual(dialog.stage, 0)
        dialog.close()
        self.assertEqual({key: self.settings.value(key) for key in original}, original)

    def test_failed_result_write_keeps_input_and_allows_retry(self):
        dialog = self.dialog()
        dialog.activities["ui"].setChecked(True)
        dialog.show_stage(2)
        with patch.object(self.store, "save_result", side_effect=ProfileStorageError("추천 결과를 저장하지 못했습니다.")):
            dialog.next()
        self.assertFalse(dialog.storage_error.isHidden())
        self.assertEqual(self.store.load(), Profile(activities=("ui",)))
        self.assertFalse(self.settings.contains(self.store.result_key))
        dialog.show_stage(2)
        dialog.next()
        self.assertTrue(dialog.storage_error.isHidden())
        self.assertEqual(self.store.load_result(dialog.profile(), self.catalog), dialog.results)

    def test_failed_corrupt_cache_cleanup_does_not_lock_the_profile(self):
        self.save()
        self.settings.setValue(self.store.result_key, "{broken")
        original = self.settings.value(self.store.key)
        with patch.object(self.store, "_write_values", side_effect=ProfileStorageError("추천 결과를 지우지 못했습니다.")):
            dialog = self.dialog()
        self.assertTrue(dialog.next_button.isEnabled())
        self.assertTrue(dialog.education.isEnabled())
        self.assertFalse(dialog.storage_error.isHidden())
        self.assertEqual(self.settings.value(self.store.key), original)
        dialog.activities["ui"].setChecked(True)
        self.assertTrue(dialog.storage_error.isHidden())
        self.assertFalse(self.settings.contains(self.store.result_key))

    def test_restored_experience_candidates_fit_small_window_in_both_themes(self):
        state = dict(theme.state)
        try:
            theme.set_text("larger")
            for mode in ("light", "dark"):
                theme.set_mode(mode)
                self.save()
                dialog = self.dialog()
                dialog.resize(760, 480)
                dialog.show()
                guikit.pump(100)
                self.assertEqual(dialog.stage, 3)
                self.assertEqual(dialog.results, self.results)
                self.assertLessEqual(dialog.width(), 760)
                self.assertLessEqual(dialog.height(), 480)
                self.assertFalse(dialog.shell.scroll.horizontalScrollBar().isVisible())
                for button in (dialog.back_button, dialog.clear_button, dialog.close_button):
                    top = button.mapTo(dialog, QPoint())
                    self.assertGreaterEqual(top.x(), 0)
                    self.assertLessEqual(top.x() + button.width(), dialog.width())
                    self.assertLessEqual(top.y() + button.height(), dialog.height())
                    self.assertGreaterEqual(button.width(), button.sizeHint().width())
                dialog.close()
        finally:
            theme.set_text(state["text"])
            theme.set_mode(state["mode"])

