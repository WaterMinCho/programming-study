# -*- coding: utf-8 -*-
"""문항 갱신 후의 복습과 과거 답안·미확인 기록 보존을 확인함."""
import copy
import os
from unittest import mock

from aiprep import service
from tests.test_ai_service import Base


class ContentVersionTest(Base):
    def answer(self, sess, cid="i90-b01"):
        sess._append({"kind": "answer", "card": cid, "result": "pass", "set": "test", "again": 0})

    def changed(self):
        sess = self.session()
        sess.cards["i90-b01"]["item"]["stem"] += " 새 조건"
        return sess

    def test_known_edit_restarts_only_that_card_and_preserves_answers(self):
        sess = self.session()
        self.answer(sess)
        self.answer(sess, "i90-b02")
        before = copy.deepcopy(sess.record.log)
        changed = self.changed()
        state = changed._state()
        self.assertNotIn("i90-b01", state.events)
        self.assertEqual(1, len(state.events["i90-b02"]))
        self.assertEqual(before, changed.record.log)
        self.answer(changed)
        self.assertEqual(1, len(changed._state().events["i90-b01"]))
        again = self.changed()
        self.assertEqual(1, len(again._state().events["i90-b01"]))
        self.assertEqual(3, len(again.record.log))

    def test_legacy_progress_is_kept_until_an_observed_change(self):
        sess = self.session()
        sess.record.append({"kind": "answer", "card": "i90-b01", "result": "pass", "set": "old"}, self.at)
        before = copy.deepcopy(sess.record.log)
        self.assertEqual(1, len(sess._state().events["i90-b01"]))
        self.assertEqual(1, sess.overview()["legacy_cards"])
        self.assertNotIn("content_revision", sess.record.log[0])
        changed = self.changed()
        self.assertNotIn("i90-b01", changed._state().events)
        self.assertEqual(before, changed.record.log)
        self.assertEqual(1, changed.overview()["revised_cards"])

    def test_changed_family_member_cannot_inherit_another_members_mastery(self):
        cards = [{"id": "a", "family": "same"}, {"id": "b", "family": "same"}]
        schedule = {"a": {"box": 4}}
        self.assertEqual(1, service.families_memorised(cards, schedule))
        self.assertEqual(0, service.families_memorised(cards, schedule, {"b"}))
        schedule["b"] = {"box": 4}
        self.assertEqual(1, service.families_memorised(cards, schedule, {"b"}))

    def test_allowed_answer_change_and_deleted_readded_card_are_detected(self):
        sess = self.session()
        self.answer(sess)
        removed = self.session()
        removed.cards.pop("i90-b01")
        removed._state()
        added = self.session()
        added.cards["i90-b01"]["item"]["blanks"][0]["answer"].append("추가 허용 답")
        self.assertNotIn("i90-b01", added._state().events)
        self.assertIn("i90-b01", added._state().revised)

    def test_missing_local_version_file_can_use_known_answer_versions(self):
        sess = self.session()
        self.answer(sess)
        os.unlink(os.path.join(sess.home, "state.json"))
        changed = self.changed()
        self.assertIn("i90-b01", changed._state().revised)
        self.assertNotIn("i90-b01", changed._state().events)

    def test_version_save_failure_keeps_original_records_and_reports_the_error(self):
        sess = self.session()
        self.answer(sess)
        before = copy.deepcopy(sess.record.log)
        changed = self.changed()
        with mock.patch.object(service.study, "write_text", side_effect=OSError("locked")):
            state = changed._state()
        self.assertNotIn("i90-b01", state.events)
        self.assertIn("card_versions", changed.errors)
        self.assertEqual(before, changed.record.log)

    def test_unrelated_terms_and_order_do_not_reset_review(self):
        from aiprep import grade
        sess = self.session()
        self.answer(sess)
        fresh = self.session()
        fresh.cards["i90-b01"]["order"] += 1
        fresh.terms["terms"].append({"term": "다른 개념", "accept": ["unrelated"]})
        fresh.term_map = grade.term_map(fresh.terms)
        self.assertEqual(1, len(fresh._state().events["i90-b01"]))
        self.assertNotIn("i90-b01", fresh._state().revised)

    def test_alias_change_applies_only_to_referenced_terms(self):
        from aiprep import grade
        sess = self.session()
        self.answer(sess)
        self.answer(sess, "i90-b04")
        fresh = self.session()
        fresh.terms["terms"][1]["accept"].append("지나친 학습")
        fresh.term_map = grade.term_map(fresh.terms)
        self.assertEqual(1, len(fresh._state().events["i90-b01"]))
        self.assertNotIn("i90-b04", fresh._state().events)

    def test_corrupt_local_state_is_preserved(self):
        from pathlib import Path
        sess = self.session()
        path = Path(sess.home) / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{broken")
        sess._state()
        self.assertEqual(b"{broken", path.read_bytes())
        self.assertIn("card_versions", sess.errors)

