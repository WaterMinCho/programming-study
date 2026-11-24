# -*- coding: utf-8 -*-
"""공개 여부(hidden)·예전 회차(legacy) 표시와 회차 계약 표를 합성 은행에서 확인함."""
import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import study
from aiprep import bank, mixed_mock, service
from learning_data import collection
from tests.test_ai_mixed_mock import READ_INDEX, make_bank, submitted_before
from tools import verify_ai


def all44_spec(**changes):
    blueprint = dict({"i%02d" % n: 1 for n in range(1, 18)}, a01=4, a02=2, a03=3, a04=1, a05=3)
    for lid in ("i02", "i03", "i05", "i06", "i07", "i08", "i09", "i10", "i11", "i12", "i13", "i16"):
        blueprint[lid] = 2
    blueprint["i04"] = 3
    spec = dict(id="m90", title="모의고사 1회", minutes=120, count=44, range=[1, 17], window=[], scope="mixed",
                courses=["intro", "app"], course_counts={"intro": 31, "app": 13}, blueprint=blueprint,
                blueprint_revision="all44-v1")
    spec.update(changes)
    return spec


class MockVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mock_visibility_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bank = make_bank(self.root/"bank")
        self.at = "2026-11-14T03:00:00+09:00"
        for obj, key, value in [(study, "SUBMISSIONS_DIR", str(self.root/"subs")),
                                (service, "now", lambda: self.at),
                                (collection, "stamp", lambda: self.at)]:
            patch = mock.patch.object(obj, key, value)
            patch.start()
            self.addCleanup(patch.stop)
        mixed_mock._EXAMS.clear()
        self.addCleanup(mixed_mock._EXAMS.clear)

    def session(self, course="intro"):
        mixed_mock._EXAMS.clear()
        return service.AiSession("learner", home=str(self.root/"home"), root=str(self.bank), course=course)

    def tick(self, seconds):
        self.at = (datetime.datetime.fromisoformat(self.at) + datetime.timedelta(seconds=seconds)).isoformat()

    def mark(self, mid="m4", **flags):
        index = study.read_json(self.bank/"index.json")
        spec = next(m for m in index["mocks"] if m["id"] == mid)
        spec.update(flags)
        study.write_text(self.bank/"index.json", json.dumps(index))

    def rows(self, kind):
        return [r for r in study.read_json(self.root/"subs/learner/ai/record.json")["log"]
                if r.get("kind") == kind and r.get("mock") == "m4"]

    def test_hidden_mock_is_left_out_without_pending_until_the_learner_submits_it(self):
        self.mark(hidden=True)
        for course in ("intro", "app"):
            with self.subTest(course=course):
                sess = self.session(course)
                self.assertNotIn("m4", sess.mocks)
                self.assertNotIn("m4", sess.mock_pending)
                self.assertNotIn("m4", sess.errors)
                self.assertEqual("", sess.overview()["mock_pending"])
                self.assertEqual([], sess.legacy_drafts)
                with self.assertRaises(service.AiError):
                    sess.start_mock("m4")
        self.mark(hidden=False)
        self.session().start_mock("m4").submit()
        self.mark(hidden=True)
        for course in ("intro", "app"):
            with self.subTest(course=course, submitted=True):
                sess = self.session(course)
                self.assertIn("m4", sess.mocks)
                self.assertTrue(sess.mocks["m4"]["hidden"])
                self.assertEqual(1, len(self.rows("mock_submit")))

    def test_legacy_mock_is_listed_only_for_learners_who_submitted_it(self):
        self.mark(legacy=True)
        for course in ("intro", "app"):
            with self.subTest(course=course):
                sess = self.session(course)
                self.assertNotIn("m4", sess.mocks)
                self.assertNotIn("m4", sess.mock_pending)
                self.assertEqual([], sess.legacy_drafts)
        self.mark(legacy=False)
        self.session().start_mock("m4").submit()
        self.mark(legacy=True)
        for course in ("intro", "app"):
            with self.subTest(course=course, submitted=True):
                sess = self.session(course)
                self.assertIn("m4", sess.mocks)
                row = next(m for m in sess.overview()["mocks"] if m["id"] == "m4")
                self.assertTrue(row["legacy"])
                self.assertEqual([], sess.overview()["legacy_drafts"])

    def test_unexpired_legacy_draft_is_kept_out_of_the_list_and_not_submitted(self):
        exam = self.session().start_mock("m4", seed=5)
        exam.save_answer(["3"], "m4-01")
        draft = Path(exam.path)
        before = draft.read_bytes()
        del exam
        self.mark(legacy=True)
        self.tick(60 * 60)
        for course in ("intro", "app"):
            with self.subTest(course=course):
                sess = self.session(course)
                self.assertNotIn("m4", sess.mocks)
                self.assertNotIn("m4", sess.mock_pending)
                self.assertEqual(["m4"], sess.legacy_drafts)
                self.assertEqual(["m4"], sess.overview()["legacy_drafts"])
                sess.expire_mocks()
        self.assertEqual(before, draft.read_bytes())
        self.assertEqual([], self.rows("mock_submit"))

    def test_unexpired_hidden_draft_is_not_reported_as_a_legacy_draft(self):
        """학습자가 hidden 회차를 시작하고 시간이 남아 있어도 legacy_drafts 에 넣지 않음."""
        exam = self.session().start_mock("m4", seed=5)
        exam.save_answer(["3"], "m4-01")
        draft = Path(exam.path)
        before = draft.read_bytes()
        del exam
        self.mark(hidden=True)
        self.tick(60 * 60)
        for course in ("intro", "app"):
            with self.subTest(course=course):
                sess = self.session(course)
                self.assertNotIn("m4", sess.mocks)
                self.assertNotIn("m4", sess.mock_pending)
                self.assertEqual([], sess.legacy_drafts)
                self.assertEqual([], sess.overview()["legacy_drafts"])
        self.assertEqual(before, draft.read_bytes())
        self.assertEqual([], self.rows("mock_submit"))

    def test_intro_only_legacy_draft_is_reported_only_in_the_intro_session(self):
        """개론 전용 회차의 legacy 초안은 응용 세션의 legacy_drafts 에 넣지 않음."""
        self.session().record.append({"kind": "mock_start", "mock": "m90", "try": 1}, at=self.at)
        self.mark("m90", legacy=True)
        self.tick(30 * 60)
        self.assertEqual(["m90"], self.session("intro").legacy_drafts)
        app = self.session("app")
        self.assertNotIn("m90", app.mocks)
        self.assertEqual([], app.legacy_drafts)
        self.assertEqual([], app.overview()["legacy_drafts"])

    def test_expired_legacy_draft_is_submitted_and_listed(self):
        exam = self.session().start_mock("m4", seed=5)
        exam.save_answer(["3"], "m4-01")
        del exam
        self.mark(legacy=True)
        self.tick(120 * 60)
        sess = self.session()
        self.assertIn("m4", sess.mocks)
        self.assertEqual([], sess.legacy_drafts)
        submitted = self.rows("mock_submit")
        self.assertEqual(1, len(submitted))
        self.assertTrue(submitted[0]["auto"])
        self.assertIn("m4", self.session("app").mocks)

    def test_unregistered_revision_and_broken_contracts_are_hidden(self):
        meta_path = self.bank/"mocks/m4/meta.json"
        meta = study.read_json(meta_path)
        meta["blueprint_revision"] = "mixed32-unregistered-v1"
        study.write_text(meta_path, json.dumps(meta))
        self.mark(blueprint_revision="mixed32-unregistered-v1")
        sess = self.session()
        self.assertNotIn("m4", sess.mocks)
        self.assertIn("준비하고 있습니다", sess.mock_pending["m4"])
        good = all44_spec()
        mixed_mock.validate(good, dict(good, draft=False))
        self.assertEqual("44문항 · 120분 · 개론 1~17차시 · 응용 1~5차시", mixed_mock.description(good))
        shifted = {lid: n for lid, n in good["blueprint"].items() if lid not in ("i01", "i02", "a01")}
        self.assertEqual("44문항 · 120분 · 개론 3~17차시 · 응용 2~5차시",
                         mixed_mock.description(all44_spec(blueprint=shifted)))
        zero = dict(good["blueprint"], a05=0)
        broken = {"unregistered": all44_spec(blueprint_revision="all44-unregistered"),
                  "count_32": all44_spec(count=32, course_counts={"intro": 16, "app": 16}),
                  "minutes": all44_spec(minutes=90),
                  "zero": all44_spec(blueprint=zero),
                  "not_int": all44_spec(blueprint=dict(good["blueprint"], a05=True))}
        for name, spec in broken.items():
            with self.subTest(case=name):
                with self.assertRaisesRegex(ValueError, "준비하고 있습니다"):
                    mixed_mock.validate(spec, dict(spec, draft=False))
        with self.assertRaisesRegex(ValueError, "일치하지 않습니다"):
            mixed_mock.validate(good, dict(good, draft=False, count=32))

    def test_only_legacy_intro_mock_may_drop_its_window(self):
        """예전 개론 회차는 제출한 사람에게만 보이므로 응시 기간을 비워도 됨. legacy 가 아닌 개론 회차는 기간이 있어야 함."""
        for legacy, failed in ((True, False), (False, True)):
            with self.subTest(legacy=legacy):
                self.mark("m90", window=[], legacy=legacy)
                out = io.StringIO()
                verifier = verify_ai.Verifier(None, out=out)
                verify_ai.check_index(verifier, str(self.bank))
                self.assertEqual(failed, verifier.failed("index"), out.getvalue())
                self.assertEqual(failed, "m90 의 window 는 [시작, 끝] 날짜여야 합니다." in out.getvalue())

    def test_switch_values_must_be_booleans(self):
        self.mark(hidden="yes")
        with self.assertRaisesRegex(bank.AiBankError, "hidden"):
            bank.read_index(str(self.bank))
        out = io.StringIO()
        verifier = verify_ai.Verifier(None, out=out)
        self.assertIsNone(verify_ai.check_index(verifier, str(self.bank)))
        self.assertTrue(verifier.failed("index"))
        self.assertIn("hidden", out.getvalue())


class PublishedBankListTest(unittest.TestCase):
    """실제 은행의 회차 목록. 예전 회차 m1~m6 은 legacy 라 제출한 사람에게만 보이고, 새 사용자는 hidden·legacy 가 아닌 회차만 봄."""
    root = Path(__file__).resolve().parents[1]/"ai"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="mock_visibility_actual_")
        self.addCleanup(tmp.cleanup)
        self.home = str(Path(tmp.name)/"home")
        patch = mock.patch.object(study, "SUBMISSIONS_DIR", str(Path(tmp.name)/"subs"))
        patch.start()
        self.addCleanup(patch.stop)
        mixed_mock._EXAMS.clear()
        self.addCleanup(mixed_mock._EXAMS.clear)
        self.specs = READ_INDEX(str(self.root))["mocks"]
        self.fresh = {spec["id"] for spec in self.specs if not spec.get("hidden") and not spec.get("legacy")}

    def session(self, user, course="intro"):
        mixed_mock._EXAMS.clear()
        return service.AiSession(user, home=self.home, root=str(self.root), course=course)

    def test_index_marks_old_rounds_legacy_and_keeps_the_new_rounds_open(self):
        specs = {spec["id"]: spec for spec in self.specs}
        for n in range(1, 7):
            with self.subTest(mock="m%d" % n):
                self.assertIs(True, specs["m%d" % n].get("legacy"))
                self.assertEqual("이전 모의고사 %d회" % n, specs["m%d" % n]["title"])
        self.assertEqual([], specs["m2"]["window"])
        self.assertEqual([], specs["m3"]["window"])
        self.assertEqual({"m11", "m12"}, self.fresh)
        self.assertEqual(("모의고사 1회", "모의고사 2회"), (specs["m11"]["title"], specs["m12"]["title"]))

    def test_new_learner_sees_only_open_rounds(self):
        """hidden·legacy 회차는 회차 목록(mocks)과 오류 목록(errors) 어디에도 나오지 않고 준비 중 안내(mock_pending)도 비어 있음.
        모든 차시 회차 m11·m12 는 두 과정 목록에 모두 나옴."""
        closed = {spec["id"] for spec in self.specs} - self.fresh
        for course in ("intro", "app"):
            with self.subTest(course=course):
                sess = self.session("synthetic", course)
                self.assertEqual({spec["id"]: spec for spec in self.specs if spec["id"] in self.fresh}, sess.mocks)
                self.assertFalse(closed & (set(sess.mocks) | set(sess.errors)))
                self.assertEqual({}, sess.mock_pending)
                self.assertEqual([], sess.legacy_drafts)
                titles = [row["title"] for row in sess.overview()["mocks"]]
                self.assertEqual(len(titles), len(set(titles)))

    def test_learner_who_submitted_an_old_round_keeps_it_listed(self):
        submitted_before("m4-taker", self.home, str(self.root), "m4")
        submitted_before("m1-taker", self.home, str(self.root), "m1")
        for course in ("intro", "app"):
            with self.subTest(course=course):
                self.assertEqual(self.fresh | ({"m1"} if course == "intro" else set()), set(self.session("m1-taker", course).mocks))
                sess = self.session("m4-taker", course)
                self.assertEqual(self.fresh | {"m4"}, set(sess.mocks))
                row = next(m for m in sess.overview()["mocks"] if m["id"] == "m4")
                self.assertTrue(row["legacy"])
                self.assertEqual("이전 모의고사 4회", row["title"])
                self.assertEqual([], sess.legacy_drafts)

if __name__ == "__main__":
    unittest.main()
