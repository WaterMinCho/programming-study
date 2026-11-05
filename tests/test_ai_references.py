# -*- coding: utf-8 -*-
"""문항의 참고 대상이 공개된 학습 단계인지 확인함."""
from tests.test_ai_service import Base


class ReferenceTest(Base):
    def test_reference_uses_the_note_step_without_exposing_source_locations(self):
        sess = self.session()
        card = sess.card_info("i90-b01")
        target = sess.note_target(card["id"])
        self.assertEqual(target["lesson"], "i90")
        self.assertEqual(target["step"], card["step"])
        self.assertIn("단계", target["label"])
        self.assertNotIn("슬라이드", str(target))
        self.assertNotIn("ref", target)
        self.assertTrue(card["ref"])
        self.assertEqual(self.log(sess), [])

    def test_missing_hidden_and_invalid_steps_do_not_become_links(self):
        sess = self.session()
        self.assertIsNone(sess.note_target("missing"))
        card = sess.card_info("i90-b01")
        old = card["step"]
        for step in ("90a/999", "90a/0", "90a/../../other", "", "90z/2"):
            card["step"] = step
            self.assertIsNone(sess.note_target(card["id"]), step)
        card["step"] = old
        key = old.split("/")[0]
        sess.notes["i90"]["visible"].remove(key)
        self.assertIsNone(sess.note_target(card["id"]))

    def test_pattern_prerequisites_do_not_replace_the_source_lesson(self):
        sess = self.session()
        card = sess.card_info("i90-b01")
        card["after"] = "not-a-note"
        self.assertEqual(sess.note_target(card["id"])["lesson"], "i90")
        card["after"] = "missing"
        self.assertEqual(sess.note_target(card["id"])["lesson"], "i90")
