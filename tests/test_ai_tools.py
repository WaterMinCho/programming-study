# -*- coding: utf-8 -*-
"""AI 비전 개론 출제 도구 테스트. tools/ai_seal.py(봉인·해제·검사·공개본), tools/verify_ai.py(일부러 망가뜨린 사본마다 실패,
서명·--require-review·--answers), tools/ai_overlap.py(가짜 강의 말뭉치), tools/ai_art(manifest·한도·팔레트), verify_web --bank·--total-mb,
web_lint --bank 를 봄. 고정 은행 tests/ai_bank 를 임시 폴더에 복사해서 고침. Pattern 으로 시작하는 클래스는 tests/aifix.pc_bank 로
상황별 코드(뼈대 S90, l18, pc)를 더한 사본에서 뼈대 검사, 서명, 두 단계 공개본, 겹침 대상을 봄.

실행: python -m unittest tests.test_ai_tools
numpy·matplotlib·Pillow 가 없으면 팔레트 그리기 테스트를 건너뜀.
"""
import contextlib
import io
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import gen as genlib  # noqa: E402
from tests import aifix  # noqa: E402
from tools import ai_art, ai_overlap, ai_seal, verify_ai, verify_web, web_lint  # noqa: E402

try:
    import matplotlib  # noqa: F401
    import numpy
    from PIL import Image
except ImportError:
    numpy = Image = None

FIXTURE = os.path.join(ROOT, "tests", "ai_bank")
DASH = "\u2014"
NAMES = ["--writer", "출제 1", "--resolver", "재풀이 2", "--checker", "대조 3", "--reviewer", "검토 4"]


def quiet(fn, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            result = fn(*args)
        except SystemExit as error:
            result = error.code
    return result, out.getvalue()


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ai_tools_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bank = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, self.bank, ignore=shutil.ignore_patterns("__pycache__"))

    def path(self, rel):
        return os.path.join(self.bank, *rel.split("/"))

    def read_json(self, rel):
        return study.read_json(self.path(rel))

    def write(self, rel, text):
        study.write_text(self.path(rel), text)

    def edit_json(self, rel, fn):
        data = self.read_json(rel)
        fn(data)
        self.write(rel, json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    def edit_item(self, cid, fn):
        def change(data):
            for item in data["items"]:
                if item["id"] == cid:
                    fn(item)
        self.edit_json("items/i90/work/items.json", change)

    def replace(self, rel, old, new):
        text = study.read_text(self.path(rel))
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new, 1))

    def verify(self, *args):
        out = io.StringIO()
        code = verify_ai.main(list(args) + ["--bank", self.bank, "--manifest", self.path("art_manifest.json"), "--seeds", "30"],
                              out)
        return code, out.getvalue()

    def assertFails(self, needle, *args):
        code, out = self.verify(*args)
        self.assertEqual(1, code, out)
        self.assertIn(needle, out)


class VerifyTest(Case):
    def test_fixture_passes(self):
        code, out = self.verify()
        self.assertEqual(0, code, out)
        self.assertIn("OK: 묶음 2개 통과", out)

    def test_misspelled_block_name_fails(self):
        self.replace("learn/l90/page.md", "```ai-recall", "```ai-recal")
        self.assertFails("모르는 블록 이름입니다: ai-recal")

    def test_blank_count(self):
        self.edit_item("i90-b01", lambda item: item.update(stem=item["stem"] + " ____ 도 채우세요."))
        self.assertFails("____ 가 2개인데 blanks 가 1개입니다")

    def test_alt_keeps_blank_count(self):
        self.edit_item("i90-b01", lambda item: item["alt"].update(stem="____ 와 ____"))
        self.assertFails("alt stem 의 빈칸 수가 원래 지문과 다릅니다")

    def test_pointing_option(self):
        self.edit_item("i90-c01", lambda item: item["options"][1].update(text="모두 옳습니다."))
        self.assertFails("다른 보기를 가리킵니다")

    def test_missing_aim(self):
        self.edit_item("i90-c01", lambda item: item["options"][1].pop("aim"))
        self.assertFails("aim")

    def test_topic_shortage(self):
        def drop(data):
            data["topics"][0]["statements"] = [s for s in data["topics"][0]["statements"] if s["id"] != "i90-s08"]
        self.edit_json("items/i90/work/statements.json", drop)
        self.edit_json("items/i90/meta.json", lambda d: d["units"]["90b"].update(stmt=7))
        self.assertFails("참 4·거짓 3")

    def test_oracle_mismatch(self):
        self.replace("items/i90/oracle.py", "return str((n + b - 1) // b)", "return str(n // b)")
        self.assertFails("oracle")

    def test_ref_form_and_first_ref(self):
        self.edit_item("i90-b01", lambda item: item.update(ref=["슬라이드 2쪽"]))
        self.assertFails("ref 꼴이 3.8 표에 없습니다")
        self.edit_item("i90-b01", lambda item: item.update(ref=["5차시 슬 p2"]))
        self.assertFails("첫 ref 는 90차시")

    def test_em_dash_in_explain(self):
        self.edit_item("i90-b01", lambda item: item.update(explain="반대로 옮깁니다 %s 손실이 줄어듭니다." % DASH))
        self.assertFails("em-dash")

    def test_facts_rules(self):
        self.edit_item("i90-b01", lambda item: item.update(facts=[]))
        self.assertFails("facts 가 없습니다")

    def test_bad_verdict(self):
        self.edit_item("i90-c01", lambda item: item.update(facts=["F90-02", "F90-11"]))
        self.assertFails("판정이 '틀림'인 사실 F90-11")

    def test_concept_only_as_number(self):
        self.edit_item("i90-b03", lambda item: item.update(facts=["F90-03", "F90-10"]))
        self.assertFails("개념 문항으로만 쓰는 사실 F90-10")

    def test_ask_as_missing(self):
        def change(data):
            for fact in data["facts"]:
                if fact["id"] == "F90-09":
                    fact.pop("ask_as")
        self.edit_json("items/i90/work/facts.json", change)
        self.edit_item("i90-b01", lambda item: item.update(facts=["F90-01", "F90-09"]))
        self.assertFails("ask_as 가 없습니다")

    def test_errata_needs_correction_line(self):
        self.edit_item("i90-c01", lambda item: item.update(explain="이번 값만 남기 때문입니다."))
        self.assertFails("정정 문구가 없습니다")

    def test_errata_card_in_mock(self):
        self.write("mocks/m90/meta.json", '{"format": 1, "id": "m90"}\n')
        item = {"id": "m90-01", "kind": "blank", "stem": "값은 ____ 입니다.", "blanks": [{"answer": ["1"], "mode": "number"}],
                "errata": ["X90-01"]}
        self.write("mocks/m90/work/items.json", json.dumps({"format": 1, "items": [item]}, ensure_ascii=False))
        self.assertFails("정정 주제(errata)라 모의고사에 넣지 않습니다", "m90")

    def test_memo_must_cover_core(self):
        self.replace("learn/l90/page.md", '"cards": ["i90-b04", "i90-s01", "i90-s02"]', '"cards": ["i90-b04", "i90-s01"]')
        self.assertFails("외울 것이 핵심 카드를 덮지 않습니다: i90-s02")

    def test_step_facts_must_overlap(self):
        self.edit_item("i90-b02", lambda item: item.update(step="90a/2"))
        self.assertFails("step 90a/2 단계의 <!-- facts --> 줄과 겹치지 않습니다")

    def test_frame_lines_must_match_gif(self):
        self.replace("learn/l90/page.md", "2. W를 2.8로 옮기면 손실이 줄어듭니다. (2000ms)",
                     "2. W를 2.8로 옮기면 손실이 줄어듭니다. (2000ms)\n3. 손실이 더 줄어듭니다. (2000ms)")
        self.assertFails("장이 2개인데 프레임 줄이 3개입니다")

    def test_figure_not_in_manifest(self):
        self.write("art_manifest.json", '{"format": 1, "files": {}}\n')
        self.assertFails("manifest 에 없는 그림입니다: assets/90a-1.gif")

    def test_retired_and_duplicate_ids(self):
        self.write("retired.json", '{"format": 1, "ids": ["i90-b01"]}\n')
        self.assertFails("retired.json 에 있는 지운 id 를 다시 썼습니다: i90-b01")

    def test_core_count_and_meta_counts(self):
        self.edit_item("i90-b03", lambda item: item.update(core=False))
        code, out = self.verify()
        self.assertIn("90a 단원의 핵심 문항이 2개입니다", out)
        self.assertIn("meta.json 의 90a core 수 3 가 봉인 안 수 2 와 다릅니다", out)

    def test_overlapping_answers_and_particle_warning(self):
        def change(item):
            item["stem"] = "____ 와 ____ 를 채우세요."
            item["blanks"] = [{"answer": ["반대"], "mode": "word"}, {"answer": ["반대"], "mode": "word"}]
        self.edit_item("i90-b01", change)
        code, out = self.verify()
        self.assertIn("1번 칸과 2번 칸 정답이 겹칩니다", out)
        self.assertIn("받침에 따라 갈리는 조사", out)

    def test_term_from_a_later_lesson(self):
        self.edit_json("terms.json", lambda d: d["terms"].append({"term": "역전파", "also": [], "page": "l91"}))
        self.edit_item("i90-b01", lambda item: item.update(explain=item["explain"] + " 역전파로 구합니다."))
        self.assertFails("91차시에서 소개하는 낱말 '역전파'")

    def test_intro_page_needs_definition(self):
        self.edit_json("terms.json", lambda d: d["terms"].append({"term": "학습률", "also": [], "page": "l91", "intro": "l90"}))
        self.assertFails("'학습률'의 intro 페이지 l90 에 한 문장 정의가 없습니다")

    @unittest.skipUnless(shutil.which("git"), "git 이 있어야 함")
    def test_id_that_disappears_from_the_last_commit(self):
        env = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        with mock.patch.dict(os.environ, env):
            quiet(ai_seal.main, ["seal", "--bank", self.bank])
            for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "chore: 시작"]):
                import subprocess
                subprocess.run(["git"] + args, cwd=self.bank, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            quiet(ai_seal.main, ["unseal", "i90", "--bank", self.bank])
            self.edit_json("items/i90/work/items.json", lambda d: d.update(items=[i for i in d["items"] if i["id"] != "i90-c01"]))
            self.edit_json("items/i90/meta.json", lambda d: d["units"]["90a"].update(choice=0))
            self.assertFails("직전 커밋에 있던 id 가 retired.json 없이 사라졌습니다: i90-c01")
            self.write("retired.json", '{"format": 1, "ids": ["i90-b99", "i90-c01"]}\n')
            code, out = self.verify()
            self.assertNotIn("사라졌습니다", out)

    def test_secret_pattern(self):
        self.replace("learn/l90/page.md", "시험용 노트입니다.", "시험용 노트입니다. hf_abcdefghijklmnop")
        self.assertFails("키나 토큰처럼 보이는 글")


class SignTest(Case):
    def sign(self, *extra):
        return self.verify("i90", "--sign", *(NAMES + list(extra)))

    def test_sign_and_require_review(self):
        self.assertFails("검토 서명(review.json)이 없습니다", "--require-review")
        code, out = self.sign("--finding", "재풀이 첫판 통과")
        self.assertEqual(0, code, out)
        self.assertIn("서명했습니다", out)
        self.verify("common", "--sign", *NAMES)
        code, out = self.verify("--require-review")
        self.assertEqual(0, code, out)
        review = json.loads(study.read_text(self.path("items/i90/work/review.json")))
        self.assertIn("work/facts.json", review["files"])
        self.assertIn("gens.py", review["files"])
        self.assertEqual(["재풀이 첫판 통과"], review["findings"])
        text = study.read_text(self.path("items/i90/gens.py"))
        with open(self.path("items/i90/gens.py"), "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        code, out = self.verify("--require-review")
        self.assertEqual(0, code, out)
        self.replace("items/i90/oracle.py", "def i90_g02", "# 고침\ndef i90_g02")
        self.assertFails("검토 뒤에 바뀐 파일: oracle.py", "--require-review")

    def test_sealed_signature_still_matches(self):
        self.sign()
        self.verify("common", "--sign", *NAMES)
        code, out = quiet(ai_seal.main, ["seal", "--bank", self.bank])
        self.assertEqual(0, code, out)
        self.assertFalse(os.path.isdir(self.path("items/i90/work")))
        code, out = self.verify("--require-review")
        self.assertEqual(0, code, out)

    def test_roles_must_differ(self):
        names = list(NAMES)
        names[names.index("--resolver") + 1] = "출제 1"
        self.assertFails("출제자는 재풀이·대조·검토를 겸하지 않습니다", "i90", "--sign", *names)
        names = list(NAMES)
        names[names.index("--checker") + 1] = "재풀이 2"
        self.assertFails("재풀이자와 대조자는 달라야 합니다", "i90", "--sign", *names)
        self.assertFalse(os.path.isfile(self.path("items/i90/work/review.json")))

    def test_failures_block_signing(self):
        self.edit_item("i90-b01", lambda item: item.update(facts=[]))
        self.assertFails("실패가 있어 서명하지 않았습니다", "i90", "--sign", *NAMES)

    def test_answers_and_first_pass(self):
        out_dir = os.path.join(self.tmp, "brief")
        code, out = quiet(ai_seal.main, ["brief", "i90", "--out", out_dir, "--bank", self.bank])
        self.assertEqual(0, code, out)
        answers = study.read_json(os.path.join(out_dir, "answers.json"))
        sheet = study.read_text(os.path.join(out_dir, "sheet.md"))
        self.assertNotIn("aim", sheet)
        self.assertNotIn("반대", sheet.split("## i90-b02")[0].split("## i90-b01")[1])
        answers["i90-b01"] = ["반대"]
        answers["i90-b02"] = ["zero_grad()"]
        answers["i90-b03"] = ["2.8"]
        answers["i90-b04"] = ["과대적합"]
        self.assertEqual({"picked": []}, answers["i90-c01"])
        item = next(i for i in self.read_json("items/i90/work/items.json")["items"] if i["id"] == "i90-c01")
        answers["i90-c01"]["picked"] = [ai_seal.option_order(item).index(0) + 1]
        topic = self.read_json("items/i90/work/statements.json")["topics"][0]
        tag = {s["id"]: t for t, s in ai_seal.statement_rows(topic)}
        answers[tag["i90-s05"]] = {"ok": False, "cloze": [""]}
        answers[tag["i90-s01"]] = {"ok": True, "cloze": ["검증"]}
        answers[tag["i90-s02"]] = {"ok": True, "cloze": [""]}
        path = os.path.join(self.tmp, "answers.json")
        study.write_text(path, json.dumps(answers, ensure_ascii=False))
        code, out = self.verify("i90", "--answers", path)
        self.assertIn("재풀이 대조: 맞음 7 /", out)
        self.assertIn("i90-s02 를 재풀이자가 틀렸습니다", out)
        answers[tag["i90-s02"]]["cloze"] = "검증"
        study.write_text(path, json.dumps(answers, ensure_ascii=False))
        code, out = self.verify("i90", "--answers", path)
        self.assertIn("재풀이 대조: 맞음 8 /", out)
        answers[tag["i90-s02"]]["cloze"] = [""]
        study.write_text(path, json.dumps(answers, ensure_ascii=False))
        code, out = self.sign("--first-pass", path, "--minutes", "40")
        self.assertEqual(0, code, out)
        review = json.loads(study.read_text(self.path("items/i90/work/review.json")))
        self.assertEqual(7, review["first_pass"]["correct"])
        self.assertEqual(40, review["first_pass"]["minutes"])

    def test_old_answers_still_grade(self):
        answers = {"i90-s05": {"ok": False}, "i90-s01": {"ok": True, "cloze": ["검증"]},
                   "i90-c01": {"order": [3, 0, 1, 2], "picked": [2]}}
        path = os.path.join(self.tmp, "answers.json")
        study.write_text(path, json.dumps(answers, ensure_ascii=False))
        code, out = self.verify("i90", "--answers", path)
        self.assertIn("재풀이 대조: 맞음 3 / 3", out)

    def test_brief_hides_which_statements_are_true(self):
        def keep_two(data):
            data["topics"][0]["statements"] = [s for s in data["topics"][0]["statements"] if s["id"] in ("i90-s01", "i90-s05")]
        self.edit_json("items/i90/work/statements.json", keep_two)
        true, false = self.read_json("items/i90/work/statements.json")["topics"][0]["statements"]
        self.assertTrue(true["ok"] and true.get("cloze"))
        self.assertFalse(false["ok"] or false.get("cloze"))
        out_dir = os.path.join(self.tmp, "brief")
        code, out = quiet(ai_seal.main, ["brief", "i90", "--out", out_dir, "--bank", self.bank])
        self.assertEqual(0, code, out)
        sheet = study.read_text(os.path.join(out_dir, "sheet.md"))
        answers = study.read_json(os.path.join(out_dir, "answers.json"))
        tags = [key for key in answers if key.startswith("i90-t01-")]
        self.assertEqual(2, len(tags))
        self.assertEqual({"ok": None, "cloze": [""]}, answers[tags[0]])
        self.assertEqual(answers[tags[0]], answers[tags[1]])
        shapes = set()
        for statement in (true, false):
            rows = [line for line in sheet.splitlines() if statement["text"] in line]
            self.assertEqual(1, len(rows), sheet)
            shape = rows[0].replace(statement["text"], "{글}")
            for tag in tags:
                shape = shape.replace(tag, "{꼬리표}")
            shapes.add(shape)
            self.assertNotIn(statement["id"], sheet + json.dumps(answers))
        self.assertEqual({"- {꼬리표}: {글} (참/거짓)"}, shapes)
        self.assertNotIn(true["cloze"]["text"], sheet)
        self.assertIn(true["cloze"]["text"], study.read_text(os.path.join(out_dir, "cloze.md")))

    def test_brief_shuffles_generator_options_and_hides_params(self):
        text = study.read_text(self.path("items/i90/gens.py"))
        self.write("items/i90/gens.py", text + '''

from aiprep.gen import choice  # noqa: E402


@gen("i90-g03", unit="90a", level=2, tags=["경사하강"], ref=["90차시 슬 p2"], facts=["F90-03"], basis="lecture-formula",
     step="90a/2", prio=3, family="sign")
def sign(r):
    """기울기 부호로 W 가 어느 쪽으로 바뀌는지 고르기."""
    g = r.pick([-3, -2, 2, 3])
    up, down = "W 가 커집니다", "W 가 작아집니다"
    return choice(stem="기울기가 %d 일 때 한 번 갱신하면?" % g,
                  options=[(up if g < 0 else down, True), (down if g < 0 else up, False), ("W 가 바뀌지 않습니다", False)],
                  params={"g": g, "form": "up" if g < 0 else "down"})
''')
        self.edit_json("items/i90/meta.json", lambda m: m["units"]["90a"]["gen"].append("i90-g03"))
        out_dir = os.path.join(self.tmp, "brief")
        code, out = quiet(ai_seal.main, ["brief", "i90", "--out", out_dir, "--bank", self.bank])
        self.assertEqual(0, code, out)
        sheet = study.read_text(os.path.join(out_dir, "sheet.md"))
        answers = study.read_json(os.path.join(out_dir, "answers.json"))
        self.assertNotIn("params", sheet)
        self.assertNotIn("form", sheet)
        spec = next(s for s in genlib.load_module(self.path("items/i90/gens.py"), "ai_brief_test") if s.id == "i90-g03")
        firsts = set()
        for seed in answers["i90-g03"]:
            self.assertEqual({"picked": []}, answers["i90-g03"][seed])
            made = genlib.run(spec, int(seed))
            order = ai_seal.gen_option_order("i90-g03", seed, len(made["options"]))
            firsts.add(order.index(0))
            answers["i90-g03"][seed] = {"picked": [order.index(0) + 1]}
        self.assertGreater(len(firsts), 1)
        path = os.path.join(self.tmp, "answers.json")
        study.write_text(path, json.dumps({"i90-g03": answers["i90-g03"]}, ensure_ascii=False))
        code, out = self.verify("i90", "--answers", path)
        self.assertIn("재풀이 대조: 맞음 1 / 1", out)
        old = {seed: [1] for seed in answers["i90-g03"]}
        study.write_text(path, json.dumps({"i90-g03": old}, ensure_ascii=False))
        code, out = self.verify("i90", "--answers", path)
        self.assertIn("재풀이 대조: 맞음 1 / 1", out)


class SealTest(Case):
    def test_seal_unseal_check(self):
        code, out = quiet(ai_seal.main, ["check", "--bank", self.bank])
        self.assertEqual(1, code)
        self.assertIn("items/i90/work/items.json", out)
        code, out = quiet(ai_seal.main, ["seal", "i90", "--bank", self.bank])
        self.assertEqual(0, code, out)
        self.assertTrue(os.path.isfile(self.path("items/i90/sealed.json")))
        self.assertFalse(os.path.isdir(self.path("items/i90/work")))
        code, out = quiet(ai_seal.main, ["check", "--bank", self.bank])
        self.assertEqual(0, code, out)
        code, out = quiet(ai_seal.main, ["unseal", "i90", "--bank", self.bank])
        self.assertTrue(os.path.isfile(self.path("items/i90/work/facts.json")))
        self.write("items/i90/sealed.json", '{"blob": "깨짐"}')
        code, out = quiet(ai_seal.main, ["check", "--bank", self.bank])
        self.assertIn("풀리지 않는 sealed.json", out)

    def test_brief_refuses_inside_repo(self):
        code, out = quiet(ai_seal.main, ["brief", "i90", "--out", os.path.join(ROOT, "tmp_brief"), "--bank", self.bank])
        self.assertIn("저장소 밖", str(code) + out)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "tmp_brief")))
        code, out = quiet(ai_seal.main, ["brief", "i90", "--out", os.path.join(self.bank, "x"), "--bank", self.bank])
        self.assertIn("저장소 밖", str(code) + out)

    def test_usage(self):
        code, out = quiet(ai_seal.main, [])
        self.assertEqual(2, code)
        self.assertIn("ai_seal.py seal", out)


class LeechTest(Case):
    def test_read_day_of_the_cards_own_unit(self):
        log = [{"kind": "learn", "lesson": "i90", "unit": "90a", "at": "2026-11-01T20:00:00"},
               {"kind": "learn", "lesson": "i90", "unit": "90b", "at": "2026-11-03T20:00:00"}]
        for card in ("i90-b04", "i90-g02"):  # 두 카드 모두 90b 단원이고 g02 는 생성기
            for day, result in (("03", "pass"), ("04", "stuck"), ("05", "pass"), ("07", "stuck"), ("08", "pass"), ("10", "stuck")):
                log.append({"kind": "answer", "card": card, "set": "s" + day, "result": result, "again": 0, "seed": 1,
                            "at": "2026-11-%sT21:00:00" % day})
        subs = os.path.join(self.tmp, "subs")
        study.write_text(os.path.join(subs, "alice", "ai", "record.json"), json.dumps({"format": 1, "user": "alice", "log": log}))
        with mock.patch.object(study, "SUBMISSIONS_DIR", subs):
            code, out = self.verify("--leeches")
        self.assertEqual(0, code, out)
        self.assertIn("자주 틀리는 문항 0개", out)


class OverlapTest(Case):
    def test_fake_corpus(self):
        lecture = os.path.join(self.bank, "lecture")
        out = io.StringIO()
        code = ai_overlap.main(["--lecture", lecture, "--bank", self.bank, "--no-pdf"], out)
        self.assertEqual(0, code, out.getvalue())
        self.assertIn("PDF 안 봄", out.getvalue())
        self.replace("learn/l90/page.md", "시험용 노트입니다.", "가중치를 갱신하기 전에 누적된 기울기를 반드시 초기화해야 합니다.")
        out = io.StringIO()
        code = ai_overlap.main(["--lecture", lecture, "--bank", self.bank, "--no-pdf", "l90"], out)
        self.assertEqual(1, code, out.getvalue())
        self.assertIn("실패 l90 page.md", out.getvalue())
        self.assertNotIn("누적된 기울기를 반드시", out.getvalue())

    def test_code_run(self):
        code_block = "```python\nfor epoch in range(num_epochs):\n    optimizer.zero_grad()\n    outputs = model(inputs)\n" \
                     "    loss = criterion(outputs, labels)\n```"
        self.replace("learn/l90/page.md", "한 번 반복할 때 부르는 세 줄입니다.", "한 번 반복할 때 부르는 줄입니다.\n\n" + code_block)
        out = io.StringIO()
        code = ai_overlap.main(["--lecture", os.path.join(self.bank, "lecture"), "--bank", self.bank, "--no-pdf", "l90"], out)
        self.assertEqual(1, code, out.getvalue())
        self.assertIn("코드 줄 3개가 이어 같음", out.getvalue())

    def test_reads_folders_named_in_nfd(self):
        lecture = os.path.join(self.tmp, "nfd")
        for name in ("강의_90차시_실습", "대학원_강의안"):
            folder = os.path.join(lecture, unicodedata.normalize("NFD", name))
            os.makedirs(folder)
            study.write_text(os.path.join(folder, "a.py"), "print('%s')\n" % name)
        self.assertEqual(1, len(ai_overlap.lesson_folders(lecture, [90])))
        found = ai_overlap.corpus(lecture, [90], use_pdf=False)["code"]
        self.assertEqual(["print('강의_90차시_실습')\n", "print('대학원_강의안')\n"], [unicodedata.normalize("NFC", t) for t in found])

    def test_needs_lecture_dir(self):
        out = io.StringIO()
        env = dict(os.environ)
        env.pop("AI_LECTURE_DIR", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(2, ai_overlap.main(["--bank", self.bank], out))


class ArtTest(Case):
    def test_names_and_limits(self):
        self.assertEqual("l05", ai_art.page_of("l05-3"))
        self.assertEqual("l05", ai_art.page_of("5c-1"))
        self.assertEqual("l18", ai_art.page_of("18a-2"))
        self.assertIsNone(ai_art.page_of("lpc-1"))
        with self.assertRaises(ValueError):
            ai_art.figure("l05-1", 560, 400)(lambda: None)
        with self.assertRaises(ValueError):
            ai_art.figure("pc-a-1")(lambda: None)
        self.assertEqual([], ai_art.image_problems(self.path("learn/l90/assets/90a-1.gif")))
        big = os.path.join(self.tmp, "big.png")
        with open(big, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 1400, 700) + b"\0" * 9)
        self.assertIn("파일 크기가 1400×700 입니다(한도 1120×600)", ai_art.image_problems(big))

    def test_record_writes_hashes(self):
        script = os.path.join(ROOT, "tools", "ai_art", "l90.py")
        self.assertFalse(os.path.exists(script))
        manifest = os.path.join(self.tmp, "manifest.json")
        with self.assertRaises(ValueError):
            ai_art.record("l90", self.bank, manifest)
        done = ai_art.record("l90", self.bank, manifest, script="tools/ai_art/__init__.py")
        self.assertEqual(["learn/l90/assets/90a-1.gif", "learn/l90/assets/90b-1.png"], done)
        data = ai_art.read_manifest(manifest)
        self.assertEqual(ai_art.file_sha(self.path("learn/l90/assets/90a-1.gif")), data["files"][done[0]]["sha256"])


class ArtPaletteTest(unittest.TestCase):
    def test_fixed_has_every_script_color(self):
        folder = os.path.join(ROOT, "tools", "ai_art")
        for name in sorted(os.listdir(folder)):
            if name.endswith(".py"):
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    for value in re.findall(r'"(#[0-9a-fA-F]{6})"', f.read()):
                        self.assertIn(value.lower(), ai_art.FIXED, name)

    @unittest.skipUnless(Image, "numpy·matplotlib·Pillow 없음")
    def test_pale_fills_stay_apart(self):
        from matplotlib.patches import Rectangle
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        gray, purple = "#f3f4f6", "#ede9fe"
        frames = []
        for k in range(2):
            ai_art.setup()
            fig, ax = ai_art.canvas(560, 300)
            ax.set_xlim(0, 2)
            ax.set_ylim(0, 1)
            ax.add_patch(Rectangle((0, 0), 1, 1, fc=gray, ec="none"))
            ax.add_patch(Rectangle((1, 0), 1, 1, fc=purple, ec="none"))
            for n, color in enumerate(list(ai_art.COLORS.values()) * 3):
                ax.text(0.02 + 0.2 * (n % 10), 0.55 + 0.12 * (n // 10) + 0.05 * k, "W = 0.%d" % n, color=color)
            frames.append(ai_art.to_image(fig))
        png = ai_art.save("l90-1", frames[0], folder)
        gif = ai_art.save("l90-2", (frames, [2000, 2000]), folder)
        for path, drawn in ((png, frames[:1]), (gif, frames)):
            with Image.open(path) as image:
                for k, raw in enumerate(drawn):
                    image.seek(k)
                    saved = numpy.asarray(image.convert("RGB"))
                    raw = numpy.asarray(raw)
                    for value in (gray, purple):
                        rgb = [int(value[i:i + 2], 16) for i in (1, 3, 5)]
                        mask = (raw == rgb).all(-1)
                        self.assertGreater(mask.sum(), 10000, value)
                        self.assertTrue((saved[mask] == rgb).all(), "%s %d번째 장의 %s" % (os.path.basename(path), k + 1, value))


class WebToolTest(Case):
    def test_verify_web_and_lint_on_ai_bank(self):
        out = io.StringIO()
        self.assertEqual(0, verify_web.main(["--bank", self.bank, "--total-mb", "32"], out=out), out.getvalue())
        out = io.StringIO()
        self.assertEqual(1, verify_web.main(["--bank", self.bank, "--total-mb", "0.001"], out=out))
        self.assertIn("bank/ 의 그림 합계", out.getvalue())
        out = io.StringIO()
        self.assertEqual(0, web_lint.main(["--bank", self.bank, "--no-external"], out=out), out.getvalue())


class PatternCase(Case):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ai_tools_pc_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bank = aifix.pc_bank(os.path.join(self.tmp, "bank"))

    def edit_skeleton(self, fn):
        self.edit_json("patterns/S90.json", fn)

    def edit_entry(self, key, cid, fn):
        def change(data):
            for entry in data[key]:
                if entry["id"] == cid:
                    fn(entry)
        self.edit_skeleton(change)

    def assertFailsPc(self, needle):
        self.assertFails(needle, "pc")


class PatternVerifyTest(PatternCase):
    def test_fixture_passes(self):
        code, out = self.verify()
        self.assertEqual(0, code, out)
        self.assertIn("OK: 묶음 3개 통과", out)
        self.assertIn("[pc] 상황별 코드", out)

    def test_slot_rules(self):
        self.edit_entry("slots", "pc-k01", lambda e: e.update(token="eval", answer=["eval"]))
        self.assertFailsPc("토큰 'eval' 가 0번 줄에 없습니다")

    def test_token_must_appear_once_in_the_variant(self):
        self.edit_entry("slots", "pc-k04", lambda e: e.update(token="opt", answer=["opt"], line_answer=None))
        self.assertFailsPc("판 전체에 2번 나옵니다")

    def test_answers_of_one_variant_must_not_overlap(self):
        self.edit_entry("slots", "pc-k03", lambda e: e["answer"].append("zero_grad"))
        self.assertFailsPc("pc-k02 와 pc-k03 의 answer 가 겹칩니다")

    def test_line_out_of_range_and_line_answer(self):
        self.edit_entry("slots", "pc-k02", lambda e: e.update(line_answer=["opt.zero_grad( )"]))
        self.assertFailsPc("line_answer 첫째는 들여쓰기를 뺀 2번 줄")
        self.edit_entry("slots", "pc-k02", lambda e: e.update(line=99))
        self.assertFailsPc("줄 번호가 판 밖입니다")

    def test_order_valid(self):
        self.edit_entry("orders", "pc-o01", lambda e: e.update(valid=[[0, 1, 2, 3, 3]]))
        self.assertFailsPc("순열 목록")
        self.edit_entry("orders", "pc-o01", lambda e: e.update(valid=[[1, 0, 2, 3, 4]]))
        self.assertFailsPc("판 순서 [0, 1, 2, 3, 4] 가 없습니다")

    def test_pick_options(self):
        self.edit_entry("picks", "pc-p01", lambda e: e["wrong"][0].update(text="n += c.argmax(1).sum( )"))
        self.assertFailsPc("코드로 같습니다")
        self.edit_entry("picks", "pc-p01", lambda e: e["wrong"][0].update(text="n += c.argmax(0).sum()", aim=""))
        self.assertFailsPc("1번 오답의 aim 칸이 비었습니다")

    def test_change_needs_two_different_lines(self):
        self.edit_skeleton(lambda d: d["variants"]["나"]["lines"].__setitem__(7, "    n += c.argmax(1).sum()"))
        self.assertFailsPc("다른 줄이 1개입니다")

    def test_level_ref_and_first_ref(self):
        self.edit_entry("slots", "pc-k03", lambda e: e.pop("level"))
        self.assertFailsPc("pc-k03 의 level 은 1~3")
        self.edit_entry("slots", "pc-k03", lambda e: e.update(level=2, ref=[]))
        self.assertFailsPc("pc-k03 에 ref 가 없습니다")
        self.edit_entry("slots", "pc-k03", lambda e: e.update(ref=["PyTorch 문서 Tensor.backward"]))
        self.assertFailsPc("첫 ref 는 그 줄을 가르친")

    def test_note_blocks_and_marked_fence(self):
        self.replace("learn/l18/page.md", '"right": "나"', '"right": "다"')
        self.assertFailsPc("판 '다' 이 뼈대 S90 에 없습니다")
        self.replace("learn/l18/page.md", '"right": "다"', '"right": "나"')
        self.replace("learn/l18/page.md", '"variant": "가"}', '"variant": "가", "slots": ["pc-k09"]}')
        self.assertFailsPc("ai-rotate: 뼈대 S90 의 가 판에 자리 pc-k09 가 없습니다")
        self.replace("learn/l18/page.md", ', "slots": ["pc-k09"]}', "}")
        self.replace("learn/l18/page.md", "    e.backward()\n    opt.step()", "    opt.step()\n    e.backward()")
        self.assertFailsPc("울타리가 뼈대 S90 가 판과 다릅니다(6번째 줄부터)")

    def test_facts_steps_and_errata(self):
        self.edit_entry("slots", "pc-k03", lambda e: e.update(facts=["F18-09"]))
        self.assertFailsPc("사실 F18-09 가 facts.json 에 없습니다")
        self.edit_entry("slots", "pc-k03", lambda e: e.update(facts=["F18-01"], step="18a/2"))
        self.assertFailsPc("pc-k03 의 facts 가 step 18a/2 단계의")
        self.edit_entry("slots", "pc-k03", lambda e: e.update(step="18a/1"))
        self.edit_entry("changes", "pc-x01", lambda e: e.update(explain="모드 줄과 축 줄이 다릅니다."))
        self.assertFailsPc("pc-x01 는 errata 가 있는데 해설에 정정 문구가 없습니다")

    def test_ids_retired_and_counts(self):
        self.edit_entry("slots", "pc-k06", lambda e: e.update(id="pc-q06"))
        self.assertFailsPc("id 꼴이")
        self.edit_entry("slots", "pc-q06", lambda e: e.update(id="pc-k06"))
        self.write("retired.json", json.dumps({"format": 1, "ids": ["i90-b99", "pc-k06"]}))
        self.assertFailsPc("retired.json 에 있는 지운 id 를 다시 썼습니다: pc-k06")
        self.write("retired.json", json.dumps({"format": 1, "ids": ["i90-b99"]}))
        self.edit_json("items/pc/meta.json", lambda d: d["units"]["18a"].update(slot=5))
        self.assertFailsPc("meta.json 의 18a slot 수 5 가 봉인 안 수 6 와 다릅니다")

    def test_tone_memo_and_index_name(self):
        self.edit_skeleton(lambda d: d["variants"]["가"].update(situation="묶음마다 %s 파라미터를 바꿉니다." % DASH))
        self.assertFailsPc("em-dash")
        self.edit_skeleton(lambda d: d["variants"]["가"].update(situation="묶음마다 파라미터를 한 번 바꾸며 학습합니다."))
        self.replace("learn/l18/page.md", '"cards": ["pc-p01"]', '"cards": ["pc-k03"]')
        self.assertFailsPc("외울 것이 핵심 카드를 덮지 않습니다: pc-p01")
        self.replace("learn/l18/page.md", '"cards": ["pc-k03"]', '"cards": ["pc-p01"]')
        self.edit_json("index.json", lambda d: d["patterns"][0]["units"]["18a"].update(name=""))
        self.assertFailsPc("18a 단원에 name 이 없습니다")

    @unittest.skipUnless(shutil.which("git"), "git 이 있어야 함")
    def test_pattern_id_that_disappears_from_the_last_commit(self):
        import subprocess
        env = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        with mock.patch.dict(os.environ, env):
            quiet(ai_seal.main, ["seal", "--bank", self.bank])
            for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "chore: 시작"]):
                subprocess.run(["git"] + args, cwd=self.bank, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.edit_skeleton(lambda d: d.update(slots=[e for e in d["slots"] if e["id"] != "pc-k06"]))
            self.edit_json("items/pc/meta.json", lambda d: d["units"]["18a"].update(slot=5))
            self.assertFailsPc("직전 커밋에 있던 id 가 retired.json 없이 사라졌습니다: pc-k06")
            self.write("retired.json", '{"format": 1, "ids": ["i90-b99", "pc-k06"]}\n')
            code, out = self.verify("pc")
            self.assertEqual(0, code, out)

    def test_static_cards_are_not_allowed(self):
        self.write("items/pc/work/items.json", json.dumps({"format": 1, "items": []}))
        self.assertFailsPc("뼈대에서 만듭니다: items.json")


class PatternSignTest(PatternCase):
    def test_signature_covers_patterns(self):
        self.assertFails("검토 서명(review.json)이 없습니다", "pc", "--require-review")
        code, out = self.verify("pc", "--sign", *NAMES)
        self.assertEqual(0, code, out)
        review = json.loads(study.read_text(self.path("items/pc/work/review.json")))
        self.assertIn("patterns/S90.json", review["files"])
        self.assertIn("work/facts.json", review["files"])
        code, out = self.verify("pc", "--require-review")
        self.assertEqual(0, code, out)
        self.edit_entry("slots", "pc-k03", lambda e: e.update(hint="메서드"))
        self.assertFails("검토 뒤에 바뀐 파일: patterns/S90.json", "pc", "--require-review")

    def brief(self):
        out_dir = os.path.join(self.tmp, "brief")
        code, out = quiet(ai_seal.main, ["brief", "pc", "--out", out_dir, "--bank", self.bank])
        self.assertEqual(0, code, out)
        read = lambda name: study.read_text(os.path.join(out_dir, name))  # noqa: E731
        return read("sheet.md"), read("skel.md"), study.read_json(os.path.join(out_dir, "answers.json"))

    def test_brief_has_two_stages_and_no_answers(self):
        sheet, samples, answers = self.brief()
        self.assertIn("## S90 가 전체", sheet)
        self.assertLess(sheet.index("## S90 가 전체"), sheet.index("## pc-o01 시드 1"))
        for key in ("pc-o01 시드 1", "pc-o01 시드 3", "pc-p01", "pc-x01 시드 2"):
            self.assertIn("## %s" % key, sheet)
            self.assertEqual({"picked": []}, answers[key])
        self.assertNotIn(" f0", sheet)
        self.assertNotIn("## S90 나 전체", sheet)  # 나 판에는 자리가 없음
        for hidden in ("set_to_none", "valid", "0번 축이 아니라", "축을 0번으로 씀", "F18-", "정정"):
            self.assertNotIn(hidden, sheet + samples)
        self.assertEqual([""] * 6, answers["S90 가 전체"])
        self.assertIn("net.①____()", sheet)
        self.assertIn("## pc-k02 f0", samples)
        self.assertIn("## pc-k06 f3", samples)
        self.assertEqual(18, len([k for k in answers if ai_seal.SAMPLE_KEY.match(k)]))
        self.assertIn("학습 모드로 바꾸는 메서드 이름은 ____ 입니다.", sheet)  # 노트의 떠올리기

    def fill(self, answers, wrong=()):
        cards = {c["id"]: c for c in ai_seal.pattern_cards(self.bank, aifix.PATTERNS)[1]}
        skeleton = verify_ai.skel.load_patterns(self.bank)["S90"]
        for key in answers:
            whole = ai_seal.WHOLE_KEY.match(key)
            sample = ai_seal.SAMPLE_KEY.match(key)
            seed = ai_seal.SEED_KEY.match(key)
            if whole:
                view = ai_seal.whole_view(skeleton, "가", list(cards.values()))
                answers[key] = [b["answer"][0] for b in view["blanks"]]
            elif sample:
                view = dict(ai_seal.skel_samples(cards[sample.group(1)], skeleton, list(cards.values())))[sample.group(2)]
                answers[key] = [b["answer"][-1] for b in view["blanks"]]
            else:
                card = cards[seed.group(1) if seed else key]
                view = ai_seal.skel_choice(card, skeleton, int(seed.group(2)) if seed else None)
                order = ai_seal.skel_option_order(card, len(view["options"]))
                right = [order.index(n) + 1 for n, o in enumerate(view["options"]) if o["ok"]]
                answers[key] = {"picked": [p % len(order) + 1 for p in right] if key in wrong else right}
        return answers

    def test_answers_grade_and_first_pass_counts_stage_one(self):
        _, _, answers = self.brief()
        path = os.path.join(self.tmp, "answers.json")
        study.write_text(path, json.dumps(self.fill(answers), ensure_ascii=False))
        code, out = self.verify("pc", "--answers", path)
        total = len(answers)
        self.assertIn("재풀이 대조: 맞음 %d / %d" % (total, total), out)
        answers = self.fill(answers, wrong=("pc-o01 시드 2",))
        answers["pc-k02 f2"][0] = "eval"
        study.write_text(path, json.dumps(answers, ensure_ascii=False))
        code, out = self.verify("pc", "--answers", path)
        self.assertIn("재풀이 대조: 맞음 %d / %d" % (total - 2, total), out)
        self.assertIn("pc-o01 시드 2 를 재풀이자가 틀렸습니다", out)
        self.assertIn("pc-k02 f2(pc-k01)", out)
        code, out = self.verify("pc", "--sign", *(NAMES + ["--first-pass", path]))
        self.assertEqual(0, code, out)
        review = json.loads(study.read_text(self.path("items/pc/work/review.json")))
        stage_one = total - 18
        self.assertEqual((stage_one, stage_one - 1), (review["first_pass"]["cards"], review["first_pass"]["correct"]))


class PatternOverlapTest(PatternCase):
    def lecture(self, folder, name, text):
        path = os.path.join(self.tmp, "lecture", folder, name)
        study.write_text(path, text)
        return os.path.join(self.tmp, "lecture")

    def run_overlap(self, *targets):
        out = io.StringIO()
        code = ai_overlap.main(["--lecture", os.path.join(self.tmp, "lecture"), "--bank", self.bank, "--no-pdf"] + list(targets), out)
        return code, out.getvalue()

    def test_one_target_brings_every_pattern_file_and_folder(self):
        self.lecture("강의_03차시_실습", "a.py", "print('다른 코드입니다')\n")
        code, out = self.run_overlap("l18")
        self.assertEqual(0, code, out)
        self.assertIn("대상 17곳", out)
        names = [t[0] for t in ai_overlap.targets(self.bank, ["S90"])]
        self.assertIn("l18 page.md", names)
        self.assertIn("patterns/S90.json 가 판", names)
        self.assertIn("patterns/S90.json pc-p01", names)
        self.assertIn("pc facts F18-02", names)
        self.assertIn("pc errata X18-01", names)
        self.assertEqual(names, [t[0] for t in ai_overlap.targets(self.bank, ["pc"])])

    def test_skeleton_lines_copied_from_any_lesson_fail(self):
        self.lecture("강의_03차시_실습", "a.py", "net.train()\nfor a, b in data:\n    opt.zero_grad()\n")
        code, out = self.run_overlap("l18")
        self.assertEqual(1, code, out)
        self.assertIn("실패 patterns/S90.json 가 판: 10자 넘는 코드 줄 3개가 이어 같음", out)
        self.assertNotIn("net.train()", out)

    def test_pattern_fact_copied_from_lecture_fails(self):
        sentence = "학습 모드로 바꾸면 배치 정규화 층은 지금 배치의 평균과 분산으로 정규화합니다."
        self.edit_json("items/pc/work/facts.json", lambda d: d["facts"][1].update(text=sentence))
        self.lecture("강의_05차시_실습", "note.md", "# 노트\n\n%s\n" % sentence)
        code, out = self.run_overlap("pc")
        self.assertEqual(1, code, out)
        self.assertIn("실패 pc facts F18-02: 산문 20자 이상 같음", out)


class PatternOverridesTest(PatternCase):
    def test_also_value_is_listed_by_slot(self):
        log = [{"kind": "override", "set": "s1", "again": 0, "card": "pc-k02", "also_value": {"pc-k01": "eval()"},
                "at": "2026-11-10T20:00:00"},
               {"kind": "override", "set": "s1", "again": 0, "card": "i90-b01", "value": ["반대쪽"], "at": "2026-11-10T20:01:00"}]
        subs = os.path.join(self.tmp, "subs")
        study.write_text(os.path.join(subs, "alice", "ai", "record.json"), json.dumps({"format": 1, "user": "alice", "log": log}))
        with mock.patch.object(study, "SUBMISSIONS_DIR", subs):
            code, out = self.verify("--overrides")
        self.assertEqual(0, code, out)
        self.assertIn("[내 답도 맞음] 답 2개 문항", out)
        self.assertIn("pc-k01: eval()(alice)", out)
        self.assertNotIn("pc-k02:", out)


if __name__ == "__main__":
    unittest.main()
