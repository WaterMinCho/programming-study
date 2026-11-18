# -*- coding: utf-8 -*-
"""문항을 고쳐 다시 봉인한 회차에서 예전 버전 보존본으로 제출자의 결과·해설·오답 복습을 여는지 합성 은행으로 확인함.
실제 은행 회차는 다시 봉인하지 않음."""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock as patch

import study
from aiprep import mock
from aiprep.mock import MockError
from aiprep.service import AiError, AiSession
from tests import test_ai_mixed_mock_verify as mixed_verify
from tests import test_ai_mock_rules as legacy
from tests.test_ai_service import Base, FIXTURE
from tools import ai_seal
from webprep import bank as webbank


def quiet(fn, *args):
    out = io.StringIO()
    with redirect_stdout(out):
        result = fn(*args)
    return result, out.getvalue()


def sealed_files(folder):
    return study.unseal_blob(study.read_json(os.path.join(folder, webbank.SEALED_NAME))["blob"])


def write_sealed(folder, files):
    study.write_text(os.path.join(folder, webbank.SEALED_NAME), webbank.seal_text(files, ai_seal.NOTE))


def versions(files):
    return sorted(rel for rel in files if rel.startswith(mock.VERSIONS + "/"))


class SealedVersionTest(Base):
    """m90 을 서명한 봉인 묶음으로 만들고 unseal → 고침 → seal 순서로 다시 봉인함. review.json 은 서명 내용과 관계없이 있기만 하면 됨."""

    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, self.root)
        index_path = os.path.join(self.root, "index.json")
        index = study.read_json(index_path)
        index["mocks"][0]["count"] = 4
        study.write_text(index_path, json.dumps(index, ensure_ascii=False))
        self.folder = os.path.join(self.root, "mocks", "m90")
        self.items = [
            {"id": "m90-%02d" % n, "kind": "blank", "lesson": "i90", "unit": "90a", "step": "90a/1",
             "stem": "숫자를 쓰세요: ____", "blanks": [{"answer": ["3"], "mode": "number"}],
             "explain": "정답은 3입니다.", "ref": ["검증 기록"]} for n in range(1, 5)
        ]
        study.write_text(os.path.join(self.folder, "meta.json"), "{}\n")
        self.write_items()
        study.write_text(os.path.join(self.folder, "work", "review.json"), '{"format": 1, "id": "m90"}\n')
        quiet(ai_seal.seal, self.folder, "m90")

    def write_items(self):
        study.write_text(os.path.join(self.folder, "work", "items.json"), json.dumps({"items": self.items}, ensure_ascii=False))

    def reseal(self, change=None):
        """unseal 로 예전 문항을 남기고 고친 뒤 다시 봉인함."""
        _, said = quiet(ai_seal.unseal, self.folder, "m90")
        if change is not None:
            change(self.items)
            self.write_items()
        quiet(ai_seal.seal, self.folder, "m90")
        return said

    @staticmethod
    def new_second_item(items):
        items[1]["stem"] = "새 숫자를 쓰세요: ____"
        items[1]["blanks"][0]["answer"] = ["9"]

    def add_item_and_time(self, items):
        """차시가 늘 때처럼 문항을 하나 더하고 회차 줄의 문항 수와 시간도 바꿈."""
        self.new_second_item(items)
        items.append(dict(items[0], id="m90-05", stem="다섯째 숫자를 쓰세요: ____"))
        index_path = os.path.join(self.root, "index.json")
        index = study.read_json(index_path)
        index["mocks"][0].update(count=5, minutes=90)
        study.write_text(index_path, json.dumps(index, ensure_ascii=False))

    def submit_first_try(self):
        sess = self.session()
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(["3"], "m90-01")
        exam.save_answer(["4"], "m90-02")
        exam.submit()
        return sess, exam

    def test_submitted_attempt_opens_result_explain_and_review_with_the_kept_version(self):
        _, first = self.submit_first_try()
        old_stem = first.items["m90-02"]["stem"]
        record_before = Path(first.sess.record.path).read_bytes()
        draft_before = Path(first.path).read_bytes()
        said = self.reseal(self.new_second_item)
        self.assertIn("work/versions/%s/" % first.fingerprint, said)
        files = sealed_files(self.folder)
        self.assertEqual(["versions/%s/items.json" % first.fingerprint, "versions/%s/spec.json" % first.fingerprint], versions(files))
        self.assertEqual({"minutes": 60, "count": 4}, json.loads(files["versions/%s/spec.json" % first.fingerprint]))
        self.assertFalse(os.path.isdir(os.path.join(self.folder, "work")))

        fresh = self.session()
        opened = fresh.start_mock("m90")
        self.assertEqual((1, first.fingerprint), (opened.attempt, opened.fingerprint))
        self.assertIsNotNone(opened.result)
        self.assertEqual(old_stem, opened.question(opened.draft["order"].index("m90-02"))["stem"])
        self.assertEqual(1, opened.summary()["score"])
        explained = opened.explain("m90-02")
        self.assertEqual((["3"], "stuck", old_stem), (explained["correct"], explained["result"], explained["question"]["stem"]))
        self.assertEqual(["4"], explained["question"]["mine"])
        self.assertEqual(0, fresh.overview()["due"])
        self.assertNotIn("m90", fresh.errors)
        self.assertEqual({"m90-02", "m90-03", "m90-04"}, {cid for cid in fresh.cards if cid.startswith("m90-")})
        note = fresh.wrong_item("m90-02")
        self.assertEqual((old_stem, ["4"]), (note["stem"], note["mine"]))
        self.at = "2026-11-10T20:00:00"
        later = self.session()
        self.assertEqual(3, later.overview()["due"])
        self.assertEqual(["3"], later.explain("m90-02")["answer"])
        self.assertEqual(record_before, Path(first.sess.record.path).read_bytes())
        self.assertEqual(draft_before, Path(first.path).read_bytes())

        retry = later.start_mock("m90", repeat=True, seed=2)
        self.assertEqual(2, retry.attempt)
        self.assertNotEqual(first.fingerprint, retry.fingerprint)
        self.assertEqual("새 숫자를 쓰세요: ____", retry.question(retry.draft["order"].index("m90-02"))["stem"])
        self.assertEqual(retry.fingerprint, self.session().start_mock("m90").fingerprint)

    def test_added_item_and_new_time_keep_the_old_count_and_time_for_the_submitted_attempt(self):
        _, first = self.submit_first_try()
        self.reseal(self.add_item_and_time)
        opened = self.session().start_mock("m90")
        self.assertEqual((first.fingerprint, 60, 4), (opened.fingerprint, opened.spec["minutes"], opened.spec["count"]))
        self.assertEqual(sorted(first.items), sorted(opened.items))
        self.assertEqual((1, 4), (opened.summary()["score"], opened.summary()["of"]))
        retry = self.session().start_mock("m90", repeat=True, seed=2)
        self.assertEqual((5, 90 * 60), (len(retry.items), retry.draft["duration"]))

    def test_another_device_rebuilds_the_result_from_the_kept_version_without_a_draft(self):
        _, first = self.submit_first_try()
        self.reseal(self.new_second_item)
        os.unlink(first.path)
        opened = self.session().start_mock("m90")
        self.assertEqual(first.fingerprint, opened.fingerprint)
        self.assertEqual(first.draft["order"], opened.draft["order"])
        self.assertFalse(os.path.exists(first.path))
        self.assertIsNone(opened.explain("m90-02")["question"]["mine"])

    def test_unsubmitted_attempt_still_asks_for_a_new_try(self):
        sess = self.session()
        exam = sess.start_mock("m90", seed=1)
        exam.save_answer(["3"], "m90-01")
        self.reseal(self.new_second_item)
        fresh = self.session()
        self.assertIn("문제 자료가 바뀌었습니다", fresh.errors.get("m90", ""))
        self.assertTrue(fresh.mock_info("m90")["restart_required"])
        with self.assertRaisesRegex(AiError, "문제 자료가 바뀌었습니다"):
            fresh.start_mock("m90")
        self.assertEqual(2, fresh.start_mock("m90", repeat=True).attempt)

    def test_kept_version_that_does_not_match_its_name_is_refused(self):
        _, first = self.submit_first_try()
        self.reseal(self.new_second_item)
        files = sealed_files(self.folder)
        name = "versions/%s/items.json" % first.fingerprint
        data = json.loads(files[name])
        data["items"][0]["stem"] = "다른 숫자를 쓰세요: ____"
        files[name] = json.dumps(data, ensure_ascii=False)
        write_sealed(self.folder, files)
        fresh = self.session()
        fresh.overview()
        self.assertIn("보존한 문항이 제출 당시 문항과 맞지 않습니다", fresh.errors.get("m90", ""))
        self.assertFalse(any(cid.startswith("m90-") for cid in fresh.cards))
        with self.assertRaisesRegex(AiError, "보존한 문항이 제출 당시 문항과 맞지 않습니다"):
            fresh.start_mock("m90")

    def test_seal_keeps_a_version_only_when_the_items_change(self):
        said = self.reseal()
        self.assertIn("work/versions/", said)
        self.assertEqual([], versions(sealed_files(self.folder)))
        _, first = self.submit_first_try()
        self.reseal(self.new_second_item)
        kept = versions(sealed_files(self.folder))
        self.assertEqual(2, len(kept))
        self.reseal()
        self.assertEqual(kept, versions(sealed_files(self.folder)))
        self.reseal(lambda items: items[2].update(stem="셋째 숫자를 쓰세요: ____"))
        self.assertEqual(4, len(versions(sealed_files(self.folder))))
        self.assertTrue(set(kept) < set(versions(sealed_files(self.folder))))

    def test_seal_refuses_changed_items_that_skipped_unseal(self):
        before = Path(self.folder, webbank.SEALED_NAME).read_bytes()
        self.new_second_item(self.items)
        self.write_items()
        with self.assertRaisesRegex(SystemExit, "unseal m90"):
            quiet(ai_seal.seal, self.folder, "m90")
        self.assertEqual(before, Path(self.folder, webbank.SEALED_NAME).read_bytes())
        quiet(ai_seal.unseal, self.folder, "m90")
        self.assertEqual("새 숫자를 쓰세요: ____", study.read_json(os.path.join(self.folder, "work", "items.json"))["items"][1]["stem"])
        quiet(ai_seal.seal, self.folder, "m90")
        files = sealed_files(self.folder)
        self.assertEqual(2, len(versions(files)))
        self.assertEqual("새 숫자를 쓰세요: ____", json.loads(files["items.json"])["items"][1]["stem"])

    def test_unsigned_bundle_is_resealed_without_versions(self):
        files = sealed_files(self.folder)
        files.pop("review.json")
        write_sealed(self.folder, files)
        self.reseal(self.new_second_item)
        files = sealed_files(self.folder)
        self.assertEqual([], versions(files))
        self.assertEqual("새 숫자를 쓰세요: ____", json.loads(files["items.json"])["items"][1]["stem"])


class LoadVersionTest(unittest.TestCase):
    """혼합 회차의 배분 버전·문항 수·시간이 바뀌어도 spec.json 에 남긴 값으로 예전 fingerprint 를 다시 계산함."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ai_mock_version_")
        self.addCleanup(temp.cleanup)
        self.root = temp.name
        self.folder = os.path.join(self.root, "mocks", "m9")
        self.old = dict(id="m9", title="모의고사", minutes=120, count=2, range=[1, 17], window=[], scope="mixed",
                        courses=["intro", "app"], course_counts={"intro": 1, "app": 1}, blueprint={"i01": 1, "a01": 1},
                        blueprint_revision="test-old")
        self.items = [
            {"id": "m9-01", "kind": "blank", "course": "intro", "lesson": "i01", "stem": "값을 쓰세요: ____",
             "blanks": [{"answer": ["2"], "mode": "number"}]},
            {"id": "m9-02", "kind": "choice", "course": "app", "lesson": "a01", "stem": "옳은 것을 고르세요.",
             "options": [{"text": "보기 %d" % n, "ok": n == 0} for n in range(4)]},
        ]
        self.fingerprint = mock.fingerprint_of(self.old, self.items)
        self.current = dict(self.old, title="모의고사 새 이름", minutes=90, count=3, blueprint_revision="test-new")
        self.files = {"items.json": json.dumps({"items": self.items + [dict(self.items[0], id="m9-03")]}),
                      "versions/%s/items.json" % self.fingerprint: json.dumps({"items": self.items}),
                      "versions/%s/spec.json" % self.fingerprint: json.dumps({key: self.old[key] for key in mock.VERSION_KEYS})}
        os.makedirs(self.folder)
        write_sealed(self.folder, self.files)

    def test_old_spec_values_rebuild_the_old_fingerprint(self):
        spec, items = mock.load_version(self.root, self.current, self.fingerprint)
        self.assertEqual(("test-old", 2, 120, "모의고사 새 이름"),
                         (spec["blueprint_revision"], spec["count"], spec["minutes"], spec["title"]))
        self.assertEqual(["m9-01", "m9-02"], list(items))
        self.assertEqual(self.fingerprint, mock.fingerprint_of(spec, list(items.values())))
        self.assertNotEqual(self.fingerprint, mock.fingerprint_of(self.current, self.items))

    def test_missing_or_unnamed_versions_are_absent(self):
        for fingerprint in ("0" * 64, None, "", "not-a-fingerprint", self.fingerprint.upper()):
            with self.subTest(fingerprint=fingerprint):
                self.assertIsNone(mock.load_version(self.root, self.current, fingerprint))

    def test_broken_versions_raise(self):
        head = "versions/%s/" % self.fingerprint
        cases = {
            "spec 키": (head + "spec.json", json.dumps(dict({key: self.old[key] for key in mock.VERSION_KEYS}, title="x"))),
            "spec 없음": (head + "spec.json", None),
            "다른 배분 버전": (head + "spec.json", json.dumps(dict({key: self.old[key] for key in mock.VERSION_KEYS},
                                                              blueprint_revision="test-new"))),
            "문항 수": (head + "spec.json", json.dumps(dict({key: self.old[key] for key in mock.VERSION_KEYS}, count=3))),
            "고친 문항": (head + "items.json", json.dumps({"items": [dict(self.items[0], stem="다른 값: ____"), self.items[1]]})),
            "읽지 못하는 문항": (head + "items.json", json.dumps({"items": [dict(self.items[0], kind="essay"), self.items[1]]})),
        }
        for name, (rel, text) in cases.items():
            with self.subTest(name):
                files = dict(self.files)
                if text is None:
                    files.pop(rel)
                else:
                    files[rel] = text
                write_sealed(self.folder, files)
                with self.assertRaisesRegex(MockError, "보존한 예전 버전 문항을 읽을 수 없습니다"):
                    mock.load_version(self.root, self.current, self.fingerprint)

    def test_unreadable_items_are_refused_even_when_the_name_matches(self):
        items = [dict(self.items[0], kind="essay"), self.items[1]]
        fingerprint = mock.fingerprint_of(self.old, items)
        files = dict(self.files)
        files["versions/%s/items.json" % fingerprint] = json.dumps({"items": items})
        files["versions/%s/spec.json" % fingerprint] = files["versions/%s/spec.json" % self.fingerprint]
        write_sealed(self.folder, files)
        with self.assertRaisesRegex(MockError, "코드 작성 문항만"):
            mock.load_version(self.root, self.current, fingerprint)


class KeepByNameTest(unittest.TestCase):
    """같은 문항 글을 다른 배분 버전의 이름으로 이미 남긴 혼합 회차에서도 서명한 버전의 이름으로 보존본을 남기고 확인하는지 봄."""

    def setUp(self):
        self.items = [{"id": "m9-01", "kind": "blank", "course": "intro", "lesson": "i01", "stem": "값을 쓰세요: ____",
                       "blanks": [{"answer": ["2"], "mode": "number"}]}]
        self.text = json.dumps({"items": self.items})
        self.old = dict(id="m9", scope="mixed", courses=["intro", "app"], minutes=10, count=1, course_counts={"intro": 1},
                        blueprint={"i01": 1}, blueprint_revision="test-old")
        self.new = dict(self.old, blueprint_revision="test-new")
        self.a, self.b = mock.fingerprint_of(self.old, self.items), mock.fingerprint_of(self.new, self.items)
        self.assertNotEqual(self.a, self.b)
        self.recorded = json.dumps({"version": {"fingerprint": self.b, "spec": {k: self.new[k] for k in mock.VERSION_KEYS}}})
        self.sealed = {"items.json": self.text, "versions/%s/items.json" % self.a: self.text,
                       "versions/%s/spec.json" % self.a: json.dumps({k: self.old[k] for k in mock.VERSION_KEYS})}

    def call(self, fn, review, spec, files):
        sealed = dict(self.sealed, **{"review.json": review})
        with patch.patch.object(ai_seal, "_mock_spec", return_value=spec), \
                patch.patch.object(ai_seal, "_sealed_only", return_value=sealed):
            return fn("unused", "m9", files)

    def test_unseal_keeps_the_signed_version_even_when_the_same_text_is_kept(self):
        cases = {"서명에 적은 회차 줄": (self.recorded, self.new), "회차 줄을 먼저 고침": (self.recorded, dict(self.new, blueprint_revision="x")),
                 "값이 없는 예전 서명": ('{"format": 1}', self.new)}
        for name, (review, spec) in cases.items():
            with self.subTest(name):
                files = dict(self.sealed, **{"review.json": review})
                self.assertEqual(self.b, self.call(ai_seal.keep_version, review, spec, files))
                self.assertEqual(self.text, files["versions/%s/items.json" % self.b])
                self.assertEqual("test-new", json.loads(files["versions/%s/spec.json" % self.b])["blueprint_revision"])
                again = dict(files)
                self.assertIsNone(self.call(ai_seal.keep_version, review, spec, again))
                self.assertEqual(files, again)

    def test_seal_stops_when_only_another_name_holds_the_signed_text(self):
        files = dict(self.sealed, **{"review.json": self.recorded,
                                     "items.json": json.dumps({"items": [dict(self.items[0], stem="새 값을 쓰세요: ____")]})})
        with self.assertRaisesRegex(SystemExit, "unseal m9"):
            self.call(ai_seal.settle_versions, self.recorded, self.new, files)


class VerifyVersionTest(unittest.TestCase):
    """서명·봉인한 혼합 회차를 고쳐 다시 서명·봉인하고 verify_ai 의 보존본 검사와 삭제 막음을 확인함."""

    def setUp(self):
        self.case = mixed_verify.MixedValidationTest()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.folder = str(self.case.bank / "mocks" / self.case.mid)
        self.case.meta["draft"] = False
        self.case.save()
        code, output = self.case.verify("--sign", *legacy.NAMES)
        self.assertEqual(0, code, output)
        quiet(ai_seal.seal, self.folder, self.case.mid)

    def change_and_reseal(self):
        quiet(ai_seal.unseal, self.folder, self.case.mid)
        path = os.path.join(self.folder, "work", "items.json")
        data = study.read_json(path)
        data["items"][0]["stem"] = data["items"][0]["stem"].replace("값을 쓰세요", "결과를 쓰세요")
        study.write_text(path, json.dumps(data, ensure_ascii=False))
        code, output = self.case.verify("--sign", *legacy.NAMES)
        self.assertEqual(0, code, output)
        quiet(ai_seal.seal, self.folder, self.case.mid)

    def test_resealed_round_keeps_the_signed_version_and_passes_review(self):
        spec = next(m for m in study.read_json(str(self.case.bank / "index.json"))["mocks"] if m["id"] == self.case.mid)
        old = mock.fingerprint_of(spec, json.loads(sealed_files(self.folder)["items.json"])["items"])
        self.change_and_reseal()
        files = sealed_files(self.folder)
        self.assertEqual(["versions/%s/items.json" % old, "versions/%s/spec.json" % old], versions(files))
        kept = json.loads(files["versions/%s/spec.json" % old])
        self.assertEqual(self.case.revision, kept["blueprint_revision"])
        self.assertEqual(set(mock.VERSION_KEYS), set(kept))
        review = json.loads(files["review.json"])
        self.assertIn("work/versions/%s/items.json" % old, review["files"])
        code, output = self.case.verify("--require-review")
        self.assertEqual(0, code, output)

    def test_unchanged_round_can_be_signed_and_sealed_again(self):
        before = sealed_files(self.folder)["items.json"]
        for _ in range(2):
            quiet(ai_seal.unseal, self.folder, self.case.mid)
            code, output = self.case.verify("--sign", *legacy.NAMES)
            self.assertEqual(0, code, output)
            quiet(ai_seal.seal, self.folder, self.case.mid)
            code, output = self.case.verify("--require-review")
            self.assertEqual(0, code, output)
        files = sealed_files(self.folder)
        self.assertEqual(before, files["items.json"])
        self.assertEqual(2, len(versions(files)))
        self.assertTrue(set("work/" + rel for rel in versions(files)) <= set(json.loads(files["review.json"])["files"]))

    def test_version_with_a_wrong_name_or_shape_fails(self):
        self.change_and_reseal()
        files = sealed_files(self.folder)
        name = next(rel for rel in versions(files) if rel.endswith("spec.json"))
        broken = dict(files)
        broken[name] = json.dumps(dict(json.loads(files[name]), blueprint_revision="mixed32-transfer-v1"))
        write_sealed(self.folder, broken)
        code, output = self.case.verify()
        self.assertEqual(1, code, output)
        self.assertIn("보존한 문항이 제출 당시 문항과 맞지 않습니다", output)
        broken = dict(files)
        broken["versions/abc/items.json"] = "{}"
        broken.pop(name)
        write_sealed(self.folder, broken)
        code, output = self.case.verify()
        self.assertEqual(1, code, output)
        self.assertIn("<fingerprint>/items.json 과 spec.json 만 둡니다", output)
        self.assertIn("items.json 과 spec.json 이 함께 있어야 합니다", output)

    def test_removing_a_kept_version_fails_review_and_signing(self):
        self.change_and_reseal()
        files = sealed_files(self.folder)
        for rel in versions(files):
            files.pop(rel)
        write_sealed(self.folder, files)
        code, output = self.case.verify("--require-review")
        self.assertEqual(1, code, output)
        self.assertIn("검토 뒤에 바뀐 파일", output)
        code, output = self.case.verify("--sign", *legacy.NAMES)
        self.assertEqual(1, code, output)
        self.assertIn("예전 버전 문항이 봉인에서 빠졌습니다", output)
        self.assertEqual(files["review.json"], sealed_files(self.folder)["review.json"])

    def commit(self):
        env = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        with patch.patch.dict(os.environ, env):
            for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "chore: 시작"]):
                subprocess.run(["git"] + args, cwd=str(self.case.bank), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_row_changed_before_unseal_still_keeps_the_submitted_version(self):
        subs = tempfile.TemporaryDirectory(prefix="ai_mock_version_home_")
        self.addCleanup(subs.cleanup)
        with patch.patch.object(study, "SUBMISSIONS_DIR", os.path.join(subs.name, "subs")):
            home = os.path.join(subs.name, "home")
            exam = AiSession("alice", home=home, root=str(self.case.bank)).start_mock(self.case.mid, seed=3)
            first = exam.draft["order"][0]
            exam.save_answer([0] if exam.items[first]["kind"] == "choice" else ["2"], first)
            exam.submit()
            signed = json.loads(sealed_files(self.folder)["review.json"])["version"]
            self.assertEqual((exam.fingerprint, self.case.revision), (signed["fingerprint"], signed["spec"]["blueprint_revision"]))
            index = self.case.fixture.read("index.json")
            next(m for m in index["mocks"] if m["id"] == self.case.mid)["blueprint_revision"] = "mixed32-transfer-v1"
            self.case.fixture.write("index.json", index)
            self.case.fixture.write("mocks/%s/meta.json" % self.case.mid, dict(self.case.meta, blueprint_revision="mixed32-transfer-v1"))
            quiet(ai_seal.unseal, self.folder, self.case.mid)
            path = os.path.join(self.folder, "work", "items.json")
            data = study.read_json(path)
            for item in data["items"]:
                item["blueprint_revision"] = "mixed32-transfer-v1"
            data["items"][0]["stem"] = data["items"][0]["stem"].replace("값을 쓰세요", "결과를 쓰세요")
            study.write_text(path, json.dumps(data, ensure_ascii=False))
            quiet(ai_seal.seal, self.folder, self.case.mid)
            files = sealed_files(self.folder)
            self.assertEqual(["versions/%s/items.json" % exam.fingerprint, "versions/%s/spec.json" % exam.fingerprint], versions(files))
            self.assertEqual(self.case.revision, json.loads(files["versions/%s/spec.json" % exam.fingerprint])["blueprint_revision"])
            opened = AiSession("alice", home=home, root=str(self.case.bank)).start_mock(self.case.mid)
            self.assertEqual((exam.fingerprint, self.case.revision), (opened.fingerprint, opened.spec["blueprint_revision"]))
            self.assertIsNotNone(opened.result)

    def test_signing_a_new_version_without_the_signed_one_is_refused(self):
        quiet(ai_seal.unseal, self.folder, self.case.mid)
        shutil.rmtree(os.path.join(self.folder, "work", mock.VERSIONS))
        path = os.path.join(self.folder, "work", "items.json")
        data = study.read_json(path)
        data["items"][0]["stem"] = data["items"][0]["stem"].replace("값을 쓰세요", "결과를 쓰세요")
        study.write_text(path, json.dumps(data, ensure_ascii=False))
        before = study.read_text(os.path.join(self.folder, "work", "review.json"))
        code, output = self.case.verify("--sign", *legacy.NAMES)
        self.assertEqual(1, code, output)
        self.assertIn("서명한 버전의 문항을 work/versions/ 에 남기지 않아 서명하지 않았습니다", output)
        self.assertEqual(before, study.read_text(os.path.join(self.folder, "work", "review.json")))

    @unittest.skipUnless(shutil.which("git"), "git 이 있어야 함")
    def test_versions_in_the_last_commit_cannot_be_dropped_with_the_signature(self):
        self.change_and_reseal()
        files = sealed_files(self.folder)
        kept = versions(files)[0].split("/")[1][:12]
        self.commit()
        code, output = self.case.verify("--require-review")
        self.assertEqual(0, code, output)
        message = "직전 커밋의 봉인에 있던 예전 버전 문항이 빠지거나 바뀌었습니다: %s" % kept
        write_sealed(self.folder, {rel: text for rel, text in files.items() if rel != "review.json" and rel not in versions(files)})
        code, output = self.case.verify("--sign", *legacy.NAMES)
        self.assertEqual(1, code, output)
        self.assertIn(message, output)
        self.assertNotIn("cobalt quartz", output)
        self.assertFalse(os.path.exists(os.path.join(self.folder, "work", "review.json")))

        write_sealed(self.folder, files)
        quiet(ai_seal.unseal, self.folder, self.case.mid)
        shutil.rmtree(os.path.join(self.folder, "work", mock.VERSIONS))
        os.remove(os.path.join(self.folder, "work", "review.json"))
        outside = tempfile.TemporaryDirectory(prefix="ai_mock_version_sealed_")
        self.addCleanup(outside.cleanup)
        shutil.move(os.path.join(self.folder, webbank.SEALED_NAME), os.path.join(outside.name, webbank.SEALED_NAME))
        code, output = self.case.verify("--sign", *legacy.NAMES)
        self.assertEqual(1, code, output)
        self.assertIn(message, output)
        self.assertFalse(os.path.exists(os.path.join(self.folder, "work", "review.json")))

    def test_mixed_submission_opens_with_the_kept_version(self):
        subs = tempfile.TemporaryDirectory(prefix="ai_mock_version_home_")
        self.addCleanup(subs.cleanup)
        with patch.patch.object(study, "SUBMISSIONS_DIR", os.path.join(subs.name, "subs")):
            home = os.path.join(subs.name, "home")
            exam = AiSession("alice", home=home, root=str(self.case.bank)).start_mock(self.case.mid, seed=3)
            first = exam.draft["order"][0]
            exam.save_answer([0] if exam.items[first]["kind"] == "choice" else ["2"], first)
            exam.submit()
            old_stem = exam.items["%s-01" % self.case.mid]["stem"]
            self.change_and_reseal()
            for course in ("intro", "app"):
                with self.subTest(course=course):
                    opened = AiSession("alice", home=home, root=str(self.case.bank), course=course).start_mock(self.case.mid)
                    self.assertEqual((exam.fingerprint, 1), (opened.fingerprint, opened.attempt))
                    self.assertTrue(opened.mixed)
                    self.assertEqual(self.case.revision, opened.spec["blueprint_revision"])
                    self.assertEqual(old_stem, opened.items["%s-01" % self.case.mid]["stem"])
                    self.assertEqual(exam.result["score"], opened.summary()["score"])


if __name__ == "__main__":
    unittest.main()
