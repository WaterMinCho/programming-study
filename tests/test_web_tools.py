# -*- coding: utf-8 -*-
"""웹 출제 도구 테스트. tools/web_seal.py(봉인·해제·검사·공개본), tools/web_lint.py(말투·맥락·그 밖의 규칙),
tools/verify_web.py(형식·비밀 파일·글·템플릿·단계 답안·최종 답안·반복·시간·페이지 출력·그림·검토 서명), tools/web_art 를 봄.

고정 은행 tests/web_bank 를 임시 폴더에 복사해 일부러 망가뜨린 사본마다 검사가 잡는지 확인함. 단계 검사는 가짜 vitest 로
흉내 내고, 실제 vitest 는 저장소 맨 위에 node_modules 가 있고 Node 22.12 이상이 있을 때 한 번만 돌림. npm install 은 하지 않음.
실행: python -m unittest tests.test_web_tools
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
import types
import unittest
from unittest import mock

os.environ.setdefault("STUDY_NODE_PROBE", "0")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from tools import verify_web, web_art, web_lint, web_seal  # noqa: E402
from webprep import bank, checks, stack  # noqa: E402

try:
    from PIL import Image
except ImportError:  # Pillow 는 출제자 컴퓨터에만 있음
    Image = None

LEAN = bool(os.environ.get("STUDY_LEAN_CI"))
REAL_NODE = None if LEAN else stack.find_node()
HAS_STACK = os.path.isfile(os.path.join(ROOT, stack.VITEST_MJS))
FIXTURE = os.path.join(ROOT, "tests", "web_bank")
FAKE_NODE = {"path": "/fake/node", "version": "22.23.2", "major": 22}
PARTICLE = re.compile(r"(?<=[A-Za-z`)\]])\s+(%s)(?=[\s,.?!)]|$)" % web_lint.PARTICLES)
# 말투 검사기에 일부러 걸리는 글. 검사기가 이 파일을 보지 않게 유니코드 이스케이프로 적음(em-dash, 강조 부사+속 빈 수식, 속 빈 수식)
DASH = "\u2014"
PUFF = "\ud14c\uc2a4\ud2b8\ub97c \uc544\uc8fc \uac04\ud3b8\ud558\uac8c \ub3cc\ub9bd\ub2c8\ub2e4"
HOLLOW = "\uc774 \ubc84\ud2bc\uc740 \uc815\ub9d0 \uc911\uc694\ud569\ub2c8\ub2e4."
NAMES = ["--writer", "출제 1", "--resolver", "재풀이 2", "--reviewer", "검토 2"]


def quiet(fn, *args):
    """표준 출력을 모아 (돌려준 값, 글). SystemExit 은 코드로 바꿈."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            result = fn(*args)
        except SystemExit as error:
            result = error.code
    return result, out.getvalue()


def tidy(bank_dir):
    """고정 은행 사본을 lint 가 통과하는 꼴로 손봄. 글(코드 블록 밖)에서 영어 낱말·인라인 코드 뒤에 띄어 쓴 조사를 붙이고,
    x01 이 l90 의 낱말(렌더링)을 쓰므로 needs 에 l90 을 넣음. 고정 은행이 그렇게 고쳐지면 아무것도 바꾸지 않음."""
    for folder, _, names in os.walk(bank_dir):
        for name in names:
            if not name.endswith(".md"):
                continue
            path = os.path.join(folder, name)
            out, fence = [], False
            for line in study.read_text(path).split("\n"):
                if re.match(r"^\s*(```|~~~)", line):
                    fence = not fence
                elif not fence:
                    line = PARTICLE.sub(r"\1", line)
                out.append(line)
            study.write_text(path, "\n".join(out))
    meta_path = os.path.join(bank_dir, "missions", "x01", "meta.json")
    meta = study.read_json(meta_path)
    if not meta.get("needs"):
        meta["needs"] = ["l90"]
        study.write_text(meta_path, json.dumps(meta, ensure_ascii=False, indent=1) + "\n")


class BankCase(unittest.TestCase):
    """고정 은행을 임시 폴더에 복사해 고치는 테스트의 바탕. self.repo 는 node_modules 가 없는 가짜 저장소 맨 위."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="web_tools_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bank = os.path.join(self.tmp, "bank")
        shutil.copytree(FIXTURE, self.bank)
        tidy(self.bank)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)

    def path(self, rel):
        return os.path.join(self.bank, *rel.split("/"))

    def read(self, rel):
        return study.read_text(self.path(rel))

    def write(self, rel, text):
        study.write_text(self.path(rel), text)

    def read_json(self, rel):
        return study.read_json(self.path(rel))

    def write_json(self, rel, data):
        self.write(rel, json.dumps(data, ensure_ascii=False, indent=1) + "\n")

    def edit_json(self, rel, fn):
        data = self.read_json(rel)
        fn(data)
        self.write_json(rel, data)

    def replace(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text, rel)
        self.write(rel, text.replace(old, new, 1))

    def append(self, rel, text):
        self.write(rel, self.read(rel).rstrip("\n") + "\n\n" + text + "\n")

    # 도구

    def seal(self, *args):
        return quiet(web_seal.main, list(args) + ["--bank", self.bank])

    def lint(self, *args):
        out = io.StringIO()
        code = web_lint.main(list(args) + ["--bank", self.bank, "--no-external"], out=out)
        return code, out.getvalue()

    def verify(self, *args, steps=None, root=None):
        out = io.StringIO()
        code = verify_web.main(list(args) + ["--bank", self.bank, "--root", root or self.repo], steps=steps, out=out)
        return code, out.getvalue()

    def assertFails(self, needle, *args, steps=None, root=None):
        code, out = self.verify(*args, steps=steps, root=root)
        self.assertEqual(1, code, out)
        self.assertIn(needle, out)
        return out

    def assertLintError(self, needle, *targets):
        code, out = self.lint(*targets)
        self.assertEqual(1, code, out)
        self.assertIn(needle, out)
        return out


STATIC = {1, 2, 3, 10}


class SealTest(BankCase):
    def test_seal_then_unseal_gives_back_the_same_files(self):
        mdir = self.path("missions/x01")
        before = bank.load_secrets(mdir)
        code, out = self.seal("seal", "x01")
        self.assertEqual(0, code, out)
        self.assertIn("봉인: x01 (파일 %d개)" % len(before), out)
        self.assertFalse(os.path.exists(os.path.join(mdir, "work")))
        self.assertTrue(os.path.isfile(os.path.join(mdir, "sealed.json")))
        self.assertEqual(before, bank.load_secrets(mdir))
        code, out = self.seal("unseal", "x01")
        self.assertEqual(0, code, out)
        self.assertIn("봉인 해제: x01", out)
        for rel, text in before.items():
            self.assertEqual(text, self.read("missions/x01/work/" + rel))

    def test_check_catches_plain_files_and_broken_sealed(self):
        code, out = self.seal("check")
        self.assertEqual(1, code)
        self.assertIn("봉인되지 않은 평문 작업본", out)
        self.assertIn("missions/x01/work/steps.md", out)
        self.assertIn("drills/t90/work/chains.md", out)
        self.assertEqual(0, self.seal("seal")[0])
        code, out = self.seal("check")
        self.assertEqual(0, code, out)
        self.assertIn("OK", out)
        self.write("drills/t90/sealed.json", '{"note": "x", "blob": "깨짐"}\n')
        code, out = self.seal("check")
        self.assertEqual(1, code)
        self.assertIn("풀리지 않는 sealed.json", out)
        self.assertIn("drills/t90/sealed.json", out)

    def test_seal_keeps_plain_with_keep_and_plain_wins_when_merging(self):
        code, out = self.seal("seal", "x01", "--keep")
        self.assertEqual(0, code, out)
        self.assertIn("평문 유지", out)
        self.assertTrue(os.path.isfile(self.path("missions/x01/work/steps.md")))
        self.write("missions/x01/work/check.md", "- 새 점검 항목입니다.\n")
        self.assertEqual(0, self.seal("seal", "x01")[0])
        self.assertEqual("- 새 점검 항목입니다.\n", bank.load_secrets(self.path("missions/x01"))["check.md"])

    def test_seal_without_secrets_reports_and_removes_sealed_json(self):
        self.assertEqual(0, self.seal("seal", "t90")[0])
        self.assertEqual(0, self.seal("unseal", "t90")[0])
        os.remove(self.path("drills/t90/sealed.json"))
        shutil.rmtree(self.path("drills/t90/work"))
        code, out = self.seal("seal", "t90")
        self.assertEqual(0, code)
        self.assertIn("봉인할 비밀 파일이 없습니다", out)
        self.assertFalse(os.path.exists(self.path("drills/t90/sealed.json")))

    def test_unreadable_sealed_json_stops_seal_and_unseal_with_a_message(self):
        self.write("missions/x01/sealed.json", "{ 깨진 json\n")
        for command in ("seal", "unseal"):
            code, out = self.seal(command, "x01")
            self.assertIsInstance(code, str, command)
            self.assertIn("sealed.json 을 git 에서 되돌리거나", code)

    def test_brief_holds_only_public_parts_and_refuses_folders_in_the_repo(self):
        out_dir = os.path.join(self.tmp, "brief_x01")
        code, out = self.seal("brief", "x01", "--out", out_dir)
        self.assertEqual(0, code, out)
        self.assertEqual(sorted(["app", "brief.md", "meta.json"]), sorted(os.listdir(out_dir)))
        meta = study.read_json(os.path.join(out_dir, "meta.json"))
        self.assertEqual("x01", meta["id"])
        self.assertNotIn("defines_inline", meta)
        self.assertNotIn("sources", meta)
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "app", "src", "App.tsx")))
        self.assertFalse(os.path.exists(os.path.join(out_dir, "work")))
        for inside in (os.path.join(ROOT, "brief_here"), os.path.join(self.bank, "brief_here")):
            code, out = self.seal("brief", "x01", "--out", inside)
            self.assertIn("저장소 밖에 만들어 주세요", str(code))
            self.assertFalse(os.path.exists(inside))
        code, out = self.seal("brief", "x02", "--out", out_dir + "_2")
        self.assertIn("meta.json 과 brief.md 가 있어야", str(code))

    def test_usage_and_unknown_target(self):
        code, out = quiet(web_seal.main, [])
        self.assertEqual(2, code)
        self.assertIn("python tools/web_seal.py seal", out)
        code, out = self.seal("seal", "w99")
        self.assertIn("미션이나 주제 폴더가 없습니다: w99", str(code))


class LintTest(BankCase):
    def test_fixture_passes_with_known_warnings_only(self):
        code, out = self.lint()
        self.assertEqual(0, code, out)
        self.assertIn("오류 0", out)
        self.assertIn("defines 누락", out)  # 90-A 가 '커밋'을 정의하지만 defines_inline 에 없음
        self.assertIn("[x01 횟수 세기 버튼]", out)

    def test_external_checker_is_loaded_from_a_path_and_missing_one_is_reported(self):
        checker = os.path.join(self.tmp, "fake_tone.py")
        study.write_text(checker, "def check(text, commit=False, path=''):\n    return [('가짜 규칙', '마법낱말')] if '마법낱말' in text else []\n")
        self.replace("missions/x01/brief.md", "버튼을 누르면 숫자가 오릅니다.", "버튼을 누르면 마법낱말 숫자가 오릅니다.")
        out = io.StringIO()
        code = web_lint.main(["x01", "--bank", self.bank, "--checker", checker], out=out)
        self.assertEqual(1, code, out.getvalue())
        self.assertIn("말투 가짜 규칙", out.getvalue())
        out = io.StringIO()
        code = web_lint.main(["x01", "--bank", self.bank, "--checker", os.path.join(self.tmp, "없는_파일.py")], out=out)
        self.assertEqual(0, code, out.getvalue())
        self.assertIn("바깥 말투 검사기를 찾지 못해", out.getvalue())

    def test_spaced_particle_after_an_english_word_or_inline_code(self):
        self.replace("missions/x01/brief.md", "버튼을 누르면 숫자가 오릅니다.", "버튼을 누르면 state 가 바뀌어 숫자가 오릅니다.")
        out = self.assertLintError("띄어 쓴 조사", "x01")
        self.assertIn("state 가", out)
        self.replace("learn/l90/page.md", "`setCount`를 부르면", "`setCount` 를 부르면")
        self.assertLintError("`…` 를", "l90")

    def test_term_used_before_definition_needs_a_needs_entry(self):
        self.edit_json("missions/x01/meta.json", lambda m: m.update(needs=[]))
        out = self.assertLintError("정의 전 사용", "x01")
        self.assertIn("'렌더링'", out)
        self.assertIn("needs 에 l90", out)

    def test_definition_after_use_is_an_error(self):
        self.replace("learn/l90/page.md", "## 일반 변수는 화면을 바꾸지 못합니다\n\n",
                     "## 일반 변수는 화면을 바꾸지 못합니다\n\nReact는 커밋 단계에서 DOM을 바꿉니다.\n\n")
        out = self.assertLintError("정의가 사용 뒤에 옴", "l90")
        self.assertIn("'커밋'", out)

    def test_definition_in_the_same_paragraph_is_not_late(self):
        self.replace("learn/l90/page.md", "컴포넌트 함수를 다시 실행해 화면에 보일 내용을 계산하는 일을 렌더링이라고 합니다.",
                     "렌더링은 자주 일어납니다. 컴포넌트 함수를 다시 실행해 화면에 보일 내용을 계산하는 일을 렌더링이라고 합니다.")
        code, out = self.lint("l90")
        self.assertEqual(0, code, out)
        self.assertNotIn("렌더링", out)

    def test_listed_term_without_definition_form_warns(self):
        self.replace("learn/l90/page.md", "계산하는 일을 렌더링이라고 합니다.", "계산하는 일이 렌더링입니다.")
        code, out = self.lint("l90")
        self.assertEqual(0, code, out)
        self.assertIn("정의 꼴", out)
        self.assertIn("'렌더링'", out)

    def test_pseudo_definition_warns(self):
        self.replace("learn/l90/page.md", "컴포넌트 함수를 다시 실행해 화면에 보일 내용을 계산하는 일을 렌더링이라고 합니다.",
                     "이것을 렌더링이라고 합니다.")
        code, out = self.lint("l90")
        self.assertEqual(0, code, out)
        self.assertIn("가짜 정의", out)

    def test_informal_titles(self):
        self.replace("learn/l90/page.md", "## 일반 변수는 화면을 바꾸지 못합니다", "## 왜 화면이 안 바뀔까?")
        self.assertLintError("반말 질문 제목", "l90")
        self.replace("learn/l90/page.md", "## 왜 화면이 안 바뀔까?", "## 뭐가 다른 건지")
        self.assertLintError("반말 제목", "l90")

    def test_pointing_to_code_or_figure_that_is_not_there(self):
        self.append("missions/x01/brief.md", "아래 코드를 보세요.")
        out = self.assertLintError("가리키는 것이 없음", "x01")
        self.assertIn("'아래 코드'", out)
        self.replace("learn/l90/page.md", "React는 state가 바뀔 때", "위 그림처럼 React는 state가 바뀔 때")
        self.assertLintError("'위 그림'", "l90")

    def test_brief_leaking_a_step_request_or_title(self):
        self.append("missions/x01/brief.md", "면접관은 누를 때마다 횟수가 1씩 오르게 해 달라고 할 것입니다.")
        out = self.assertLintError("요구 유출", "x01")
        self.assertIn("1단계 요구와 겹칩니다", out)
        shutil.rmtree(self.bank)
        shutil.copytree(FIXTURE, self.bank)
        tidy(self.bank)
        self.append("missions/x01/brief.md", "두 번째 요구는 초기화 버튼입니다.")
        self.assertLintError("2단계 제목이 그대로 나옵니다", "x01")

    def test_prediction_followed_by_the_answer_warns(self):
        self.append("learn/l90/page.md", "한 번 눌렀을 때 숫자가 몇이 될지 예상해 보세요. 숫자는 1이 됩니다.")
        code, out = self.lint("l90")
        self.assertEqual(0, code, out)
        self.assertIn("예상 뒤 바로 답", out)
        self.replace("learn/l90/page.md", "숫자는 1이 됩니다.", "실행해 보면 1이 됩니다.")
        self.assertNotIn("예상 뒤 바로 답", self.lint("l90")[1])

    def test_lone_short_closing_paragraph_warns(self):
        self.replace("learn/l90/page.md", "`setCount`를 부르면 React가 이 컴포넌트를 다시 실행합니다.\n",
                     "`setCount`를 부르면 React가 이 컴포넌트를 다시 실행합니다.\n\n화면은 바뀌지 않습니다.\n")
        code, out = self.lint("l90")
        self.assertEqual(0, code, out)
        self.assertIn("외딴 짧은 문단", out)

    def test_captions_cells_meta_strings_and_test_names_go_through_the_style_checker(self):
        self.replace("learn/l90/page.md", "캡션: 그림 1. 두 호출이 같은 값을 넣어 숫자가 1 만 오릅니다.", "캡션: 그림 1. 두 호출이 같은 값을 넣음.")
        out = self.assertLintError("(캡션)", "l90")
        self.assertIn("가이드 문장은 ~니다 체", out)
        self.append("missions/x01/brief.md", "| 명령 | 하는 일 |\n|---|---|\n| npm test | %s |" % PUFF)
        out = self.assertLintError("(표 칸)", "x01")
        self.assertIn("속 빈 수식", out)
        self.edit_json("drills/t90/meta.json", lambda m: m["chains"][0].update(goal="일반 변수와 state %s 다시 그리기로 설명합니다." % DASH))
        out = self.assertLintError("meta.json(90-A goal)", "t90")
        self.assertIn("em-dash", out)
        self.replace("missions/x01/work/checks/step1.test.tsx", "1a 이름이 \"더하기\"인 버튼이 있습니다", "1a 이름이 더하기인 버튼이 있음")
        out = self.assertLintError("checks/step1.test.tsx", "x01")
        self.assertIn("~니다 체", out)

    def test_help_and_unknown_target(self):
        out = io.StringIO()
        self.assertEqual(0, web_lint.main(["--help"], out=out))
        self.assertIn("python tools/web_lint.py", out.getvalue())
        code, out = self.lint("w99")
        self.assertEqual(2, code)
        self.assertIn("출제된 미션·주제·페이지가 아닙니다: w99", out)


class VerifyStaticTest(BankCase):
    def test_fixture_passes_static_steps(self):
        code, out = self.verify(steps=STATIC)
        self.assertEqual(0, code, out)
        self.assertIn("OK: 항목 3개 통과", out)
        self.assertIn("그림 파일이 아직 없습니다", out)  # l90-1.png 는 고정 은행에 없음(경고)

    def test_index_problems(self):
        os.makedirs(self.path("missions/x09"))
        self.write("missions/x09/meta.json", "{}\n")
        self.assertFails("missions/x09 폴더가 index.json 에 없습니다", steps={1})
        shutil.rmtree(self.path("missions/x09"))
        self.edit_json("index.json", lambda d: d["order"].append("zz9"))
        self.assertFails("order 에 목록에 없는 id", steps={1})
        self.edit_json("index.json", lambda d: (d["order"].pop(), d["topics"][1].update(no=90)))
        self.assertFails("topics 의 no 가 겹칩니다", steps={1})

    def test_terms_must_match_the_page_that_introduces_them(self):
        self.edit_json("learn/l90/meta.json", lambda m: m["defines"].remove("커밋"))
        self.assertFails("페이지 l90 의 defines 에 그 낱말이 없습니다", steps={1})
        self.edit_json("terms.json", lambda t: t["terms"].append({"term": "새 낱말", "page": "l99"}))
        self.assertFails("page l99 가 index.json 의 페이지가 아닙니다", steps={1})

    def test_mission_meta(self):
        self.edit_json("missions/x01/meta.json", lambda m: m.update(level="고급"))
        self.assertFails("level 은 워밍업, 기본, 응용, 실전 가운데 하나", "x01", steps={1})
        self.edit_json("missions/x01/meta.json", lambda m: m.update(level="기본", steps=[1]))
        self.assertFails("0단계(코드 설명)와 요구 단계 하나 이상", "x01", steps={1})
        self.edit_json("missions/x01/meta.json", lambda m: m.update(steps=[1, 3, 3]))
        code, out = self.verify("x01", steps={1})
        self.assertIn("단계 목표 합계 7분이 실전 시간 6분의 90% 를 넘습니다", out)
        self.edit_json("missions/x01/meta.json", lambda m: m.update(steps=[1, 2, 2], hidden=True))
        self.assertFails("hidden 이 true 인데 checks/hidden.test.tsx 가 없습니다", "x01", steps={2})
        self.edit_json("missions/x01/meta.json", lambda m: m.update(hidden=False, pages=["l99"], chains=["99-Z"]))
        out = self.assertFails("pages 의 l99 가 index.json 의 페이지가 아닙니다", "x01", steps={1})
        self.assertIn("chains 의 99-Z 가 어느 주제의 meta.json 에도 없습니다", out)

    def test_steps_md(self):
        self.replace("missions/x01/work/steps.md", "### 검사\n- 이름이 \"더하기\"인 버튼이 있는지 봅니다.\n- 더하기 버튼을 두 번 누르면 \"지금까지 2번\"이 보이는지 봅니다.\n", "")
        self.assertFails("1단계 에 `### 검사` 목록이 없습니다", "x01", steps={2})
        self.replace("missions/x01/work/steps.md", "## 2. 초기화 버튼", "## 3. 초기화 버튼")
        self.assertFails("단계 번호 [0, 1, 3] 가 meta.json 의 steps(0~2단계)와 맞지 않습니다", "x01", steps={2})

    def test_check_files(self):
        self.replace("missions/x01/work/checks/step1.test.tsx", "test('1a ", "test('2a ")
        self.assertFails("검사 이름은 \"1<a-z> 학습자용 문장\" 으로 시작해야 합니다: 2a", "x01", steps={2})
        self.replace("missions/x01/work/checks/step1.test.tsx", "import { App } from '@app/App';", "import { App } from '../app/src/App';")
        self.assertFails("상대 경로로 import 합니다(../app/src/App)", "x01", steps={2})
        self.replace("missions/x01/work/checks/step2.test.tsx", "from '@kit/render'", "from '@kit/deferred'")
        self.assertFails("@kit/deferred 를 import 하지만 kit/ 에 그 파일이 없습니다", "x01", steps={2})
        self.replace("missions/x01/work/checks/step2.test.tsx", "test('2a ", "test('2a 같은 id 입니다', () => {});\ntest('2a ")
        self.assertFails("같은 검사 id 가 두 번 있습니다", "x01", steps={2})

    def test_solutions_explain_and_followups(self):
        shutil.rmtree(self.path("missions/x01/work/solution/step2"))
        self.assertFails("solution/step2/ 에 그 단계에서 바뀐 파일이 없습니다", "x01", steps={2})
        self.replace("missions/x01/work/explain.md", "## 모범 답안", "## 답")
        out = self.assertFails("explain.md 에 「모범 답안」 절이 없습니다", "x01", steps={2})
        self.assertIn("「답」 절은 정해진 절", out)
        self.replace("missions/x01/work/followups.md", "## x01-F", "## x01-G")
        self.assertFails("followups.md 의 사슬 id 는 x01-F 여야 합니다", "x01", steps={2})
        self.replace("missions/x01/work/followups.md", "## x01-G", "## x01-F")
        self.replace("missions/x01/work/followups.md", "### 약한 답", "### 약한 답이었던 것")
        self.assertFails("「### 약한 답」(인용 한 줄과 왜 약한지)이 없습니다", "x01", steps={2})
        self.replace("missions/x01/work/followups.md", "### 약한 답이었던 것", "### 약한 답")
        self.replace("missions/x01/work/followups.md", "> 막히면: `let count = 0`으로", "> 막히면 `let count = 0`으로")
        self.assertFails("Q1 에 「> 막히면: …」 줄이 없습니다", "x01", steps={2})
        self.replace("drills/t90/work/chains.md", "- [필수] `useState`로 값을 두고", "- [보충] `useState`로 값을 두고")
        self.assertFails("Q2 의 [필수] 항목이 0개입니다", "t90", steps={2})

    def test_template_folder(self):
        self.edit_json("missions/x01/app/package.json", lambda p: p.update(devDependencies={"react": "19.2.3"}))
        self.assertFails("더 있는 키: devDependencies", "x01", steps={1})
        self.edit_json("missions/x01/app/package.json", lambda p: (p.pop("devDependencies"), p["scripts"].update(test="vitest")))
        self.assertFails("app/package.json 의 scripts 는", "x01", steps={1})
        self.edit_json("missions/x01/app/package.json", lambda p: p["scripts"].update(test="vitest run"))
        self.edit_json("missions/x01/app/package.json", lambda p: p["scripts"].pop("typecheck"))
        self.assertEqual(0, self.verify("x01", steps={1})[0])  # typecheck 는 두지 않아도 됨
        self.replace("missions/x01/app/src/App.tsx", "<h1>횟수 세기</h1>", "<h1>횟수 세기</h1><a href=\"https://example.com/x\">x</a>")
        self.assertFails("app/src/App.tsx 에 바깥 주소가 있습니다: https://example.com/x", "x01", steps={1})
        self.replace("missions/x01/app/src/App.tsx", "<a href=\"https://example.com/x\">x</a>", "<p>토스 앱</p>")
        self.assertFails("app/src/App.tsx 에 회사 이름이 있습니다: 토스", "x01", steps={1})
        self.replace("missions/x01/app/src/App.tsx", "<p>토스 앱</p>", "")
        self.write("missions/x01/app/src/big.ts", "// " + "x" * (210 * 1024) + "\n")
        self.assertFails("app/ 크기가", "x01", steps={1})
        os.remove(self.path("missions/x01/app/src/big.ts"))
        os.makedirs(self.path("missions/x01/app/node_modules/.vite/vitest"))  # app/ 안에서 npm test 를 돌리면 생기는 캐시
        self.assertNotIn("app/node_modules", self.verify("x01", steps={1})[1])
        os.makedirs(self.path("missions/x01/app/node_modules/react"))
        self.assertFails("app/node_modules 폴더를 지우세요", "x01", steps={1})
        shutil.rmtree(self.path("missions/x01/app/node_modules"))
        os.remove(self.path("missions/x01/app/src/App.test.tsx"))
        self.assertFails("기존 테스트(*.test.tsx)가 없습니다", "x01", steps={1})

    def test_topic(self):
        self.edit_json("drills/t90/meta.json", lambda m: m["chains"][0].update(id="91-A"))
        self.assertFails("사슬 91-A 의 번호는 주제 번호 90 로 시작해야 합니다", "t90", steps={1})
        self.edit_json("drills/t90/meta.json", lambda m: m["chains"][0].update(id="90-A", section="99z"))
        self.assertFails("section 99z 가 페이지 l90 의 sections 에 없습니다", "t90", steps={1})
        self.edit_json("drills/t90/meta.json", lambda m: (m["chains"][0].update(section="90a"), m.update(no=91)))
        self.assertFails("meta.json 의 no(91)가 index.json 의 no(90)와 다릅니다", "t90", steps={1})
        self.edit_json("drills/t90/meta.json", lambda m: m.update(no=90))
        self.replace("drills/t90/work/chains.md", "## 90-B", "## 90-C")
        out = self.assertFails("chains.md 에 사슬 90-B 가 없습니다", "t90", steps={2})
        self.assertIn("chains.md 의 사슬 90-C 가 meta.json 의 chains 에 없습니다", out)

    def test_page(self):
        self.edit_json("learn/l90/meta.json", lambda m: m.update(needs=["l90"]))
        self.assertFails("needs 에 자기 자신이 있습니다", "l90", steps={1})
        self.edit_json("learn/l90/meta.json", lambda m: m.update(needs=["l91"]))
        self.write_json("learn/l91/meta.json", {"format": 1, "id": "l91", "title": "준비 중 페이지", "defines": [], "needs": ["l90"],
                                                "sections": {}, "outputs": [], "sources": []})
        self.write("learn/l91/page.md", "# 준비 중 페이지\n\n## 첫 절\n\n글입니다.\n")
        self.assertFails("needs 가 돌고 돕니다: l90 → l91 → l90", "l90", steps={1})
        self.edit_json("learn/l90/meta.json", lambda m: m.update(needs=[], sections={"90a": "없는 절 제목"}))
        self.assertFails("sections 의 90a(「없는 절 제목」)가 page.md 의 제목에 없습니다", "l90", steps={1})
        self.edit_json("learn/l90/meta.json", lambda m: m.update(sections={}, outputs=[{"block": 5, "expect": "x"}]))
        self.assertFails("outputs[1].block 5 번 코드 블록이 없습니다(figure 를 뺀 블록 1개)", "l90", steps={1})
        self.edit_json("learn/l90/meta.json", lambda m: m.update(outputs=[{"block": 1, "expect": "x"}]))
        self.assertFails("1번 블록은 node 로 돌리는 js 블록이어야 합니다(지금 'tsx')", "l90", steps={1})
        self.edit_json("learn/l90/meta.json", lambda m: m.update(outputs=[]))
        self.append("learn/l90/page.md", "# 또 다른 제목")
        self.assertFails("H1 제목이 하나 있어야 합니다", "l90", steps={1})

    def test_learner_text_must_pass_check_style(self):
        self.replace("missions/x01/brief.md", "버튼을 누르면 숫자가 오릅니다.", "버튼을 누르면 숫자가 오릅니다. " + HOLLOW)
        out = self.assertFails("3 글", "x01", steps={3})
        self.assertIn("속 빈 수식", out)

    def test_figures(self):
        page = "learn/l90/page.md"
        self.replace(page, "파일: assets/l90-1.png", "파일: pictures/l90-1.png")
        self.assertFails("파일은 assets/<이름>.gif 나 .png 여야 합니다", "l90", steps={10})
        self.replace(page, "파일: pictures/l90-1.png", "파일: assets/x-1.png")
        self.assertFails("그림 이름 x-1 가 l01-1, 3a-1, w03-1 꼴이 아닙니다", "l90", steps={10})
        self.replace(page, "파일: assets/x-1.png", "파일: assets/l91-1.png")
        self.assertFails("그림 이름 l91-1 는 이 페이지(l90-1)나 그 절(90a-1, 90b-1)의 꼴이 아닙니다", "l90", steps={10})
        self.replace(page, "파일: assets/l91-1.png", "파일: assets/90a-1.gif")
        out = self.assertFails("GIF 인데 프레임: 설명이 두 줄 이상 없습니다", "l90", steps={10})
        self.replace(page, "내용: 왼쪽에 count=0 상자, 오른쪽에 setCount(1) 두 번.", "프레임:\n1. 첫 장면. (5000ms)\n2. 둘째 장면 (시간 없음)")
        out = self.assertFails("프레임 시간 5000ms 가 800~2500ms 를 벗어납니다", "l90", steps={10})
        self.assertIn("\"(1400ms)\" 로 끝나야 합니다", out)
        self.replace(page, "파일: assets/90a-1.gif", "파일: assets/l90-1.png")
        self.assertFails("PNG 인데 내용: 설명이 없습니다", "l90", steps={10})
        self.replace(page, "캡션: 그림 1.", "설명: 그림 1.")
        self.assertFails("캡션: 줄이 없습니다", "l90", steps={10})

    def test_image_files_are_measured_and_unreferenced_ones_warn(self):
        assets = self.path("learn/l90/assets")
        os.makedirs(assets)
        big = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 1200, 100) + b"\0" * (250 * 1024)
        with open(os.path.join(assets, "l90-1.png"), "wb") as f:
            f.write(big)
        out = self.assertFails("assets/l90-1.png: 크기가 250.0KB 입니다(한도 200KB)", "l90", steps={10})
        self.assertIn("파일 폭이 1200px 입니다(한도 1120px)", out)
        with open(os.path.join(assets, "l90-9.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 100, 100) + b"\0" * 16)
        code, out = self.verify("l90", steps={10})
        self.assertIn("assets/l90-9.png 는 어느 글도 가리키지 않습니다", out)

    def test_unknown_target_and_pages_mode(self):
        code, out = self.verify("w99", steps=STATIC)
        self.assertEqual(2, code)
        self.assertIn("출제된 미션·주제·페이지가 아닙니다: w99", out)
        code, out = self.verify("--pages", steps=STATIC)
        self.assertEqual(0, code, out)
        self.assertIn("[l90]", out)
        self.assertNotIn("[x01]", out)


class ReviewTest(BankCase):
    def sign(self, target, *extra):
        return self.verify(target, "--sign", *(NAMES + list(extra)), steps=set())

    def require(self, target):
        return self.verify(target, "--require-review", steps=set())

    def test_sign_then_edit_needs_review_again(self):
        code, out = self.require("x01")
        self.assertEqual(1, code)
        self.assertIn("검토 서명(review.json)이 없습니다", out)
        code, out = self.sign("x01", "--finding", "1단계 힌트를 고침")
        self.assertEqual(0, code, out)
        review = self.read_json("missions/x01/work/review.json")
        self.assertEqual(["출제 1", "재풀이 2", "검토 2"], [review["writer"], review["resolver"], review["reviewer"]])
        self.assertEqual(["1단계 힌트를 고침"], review["findings"])
        for name in ("meta.json", "brief.md", "app/src/App.tsx", "app/package.json", "work/steps.md", "work/checks/step1.test.tsx",
                     "work/solution/step2/src/App.tsx"):
            self.assertIn(name, review["files"])
        self.assertNotIn("work/review.json", review["files"])
        self.assertEqual(0, self.require("x01")[0])
        self.append("missions/x01/brief.md", "한 줄을 더합니다.")
        code, out = self.require("x01")
        self.assertEqual(1, code)
        self.assertIn("검토 뒤에 바뀐 파일: brief.md", out)
        code, out = self.sign("x01", "--finding", "brief 를 고침")
        self.assertEqual(0, code, out)
        self.assertEqual(["1단계 힌트를 고침", "brief 를 고침"], self.read_json("missions/x01/work/review.json")["findings"])

    def test_writer_must_differ_from_resolver_and_reviewer(self):
        code, out = self.verify("x01", "--sign", "--writer", "같은 사람", "--resolver", "재풀이 2", "--reviewer", "같은 사람", steps=set())
        self.assertEqual(1, code)
        self.assertIn("출제자는 재풀이자나 검토자를 겸하지 않습니다", out)
        self.assertFalse(os.path.exists(self.path("missions/x01/work/review.json")))
        code, out = self.verify("x01", "--sign", "--writer", "출제 1", steps=set())
        self.assertIn("--resolver, --reviewer 가 필요합니다", out)
        self.sign("x01")
        self.edit_json("missions/x01/work/review.json", lambda r: r.update(reviewer=r["writer"]))
        code, out = self.require("x01")
        self.assertEqual(1, code)
        self.assertIn("출제자(출제 1)가 재풀이자나 검토자와 같습니다", out)

    def test_topic_and_page_reviews_survive_sealing(self):
        for target in ("t90", "l90"):
            self.assertEqual(0, self.sign(target)[0])
        topic = self.read_json("drills/t90/work/review.json")
        self.assertEqual(["meta.json", "work/chains.md"], sorted(topic["files"]))
        page = self.read_json("learn/l90/review.json")
        self.assertEqual(["meta.json", "page.md"], sorted(page["files"]))
        self.assertEqual(0, self.seal("seal")[0])
        self.assertFalse(os.path.exists(self.path("drills/t90/work")))
        code, out = self.verify("t90", "l90", "--require-review", steps=set())
        self.assertEqual(0, code, out)
        self.append("learn/l90/page.md", "한 줄을 더합니다.")
        code, out = self.require("l90")
        self.assertEqual(1, code)
        self.assertIn("검토 뒤에 바뀐 파일: page.md", out)

    def test_sign_refuses_when_verification_fails(self):
        self.edit_json("missions/x01/meta.json", lambda m: m.update(level="고급"))
        code, out = self.verify("x01", "--sign", *NAMES, steps={1})
        self.assertEqual(1, code)
        self.assertIn("실패가 있어 서명하지 않았습니다", out)
        self.assertFalse(os.path.exists(self.path("missions/x01/work/review.json")))


class FakeVitest(object):
    """checks._popen 자리. 설정 파일에서 학습자 폴더와 돌릴 단계 파일을 읽고, App.tsx 에 "더하기"가 있으면 1단계, "초기화"가
    있으면 2단계를 통과시키는 vitest JSON 보고서를 씀. flaky 면 실행마다 1단계 결과를 뒤집고, slow_ms 는 파일 하나의 시간."""

    calls = []
    flaky = False
    slow_ms = 100

    def __init__(self, cmd, **options):
        FakeVitest.calls.append((cmd, options))
        self.returncode = 0
        config = study.read_text(cmd[cmd.index("--config") + 1])
        out = [a for a in cmd if a.startswith("--outputFile=")][0].split("=", 1)[1]
        app = re.search(r"'@app': \"(.*?)\"", config).group(1)
        src = study.read_text(os.path.join(app, "App.tsx"))
        flip = FakeVitest.flaky and len(FakeVitest.calls) % 2 == 0
        results = []
        for rel in re.findall(r'"([^"]*(?:step\d|hidden)\.test\.tsx)"', config):
            path = os.path.join(options["cwd"], *rel.split("/"))
            ids = bank.check_ids(study.read_text(path))
            found = re.search(r"step(\d)", rel)
            ok = True if not found else (("더하기" in src) if found.group(1) == "1" else ("초기화" in src))
            if flip and found and found.group(1) == "1":
                ok = not ok
            rows = [{"ancestorTitles": [], "fullName": cid, "title": "%s 검사 %s" % (cid, cid), "duration": 10,
                     "status": "passed" if ok else "failed",
                     "failureMessages": [] if ok else ["TestingLibraryElementError: Unable to find role button\n\nIgnored nodes\n<body />"]}
                    for cid in ids]
            results.append({"name": path, "status": "passed" if ok else "failed", "message": "", "startTime": 1000,
                            "endTime": 1000 + FakeVitest.slow_ms, "assertionResults": rows})
        study.write_text(out, json.dumps({"testResults": results}))

    def communicate(self, timeout=None):
        return b"", b""


class FakeRun(object):
    """verify_web._run 자리(템플릿의 기존 테스트). --outputFile 에 통과 보고서를 쓰고, fail 이면 실패 보고서를 씀."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __call__(self, args, **options):
        self.calls.append((list(args), options))
        out = [a for a in args if a.startswith("--outputFile=")][0].split("=", 1)[1]
        row = {"title": "제목이 보입니다", "status": "failed" if self.fail else "passed", "failureMessages": []}
        study.write_text(out, json.dumps({"testResults": [{"name": "/app/src/App.test.tsx", "status": row["status"], "assertionResults": [row]}]}))
        return mock.Mock(returncode=1 if self.fail else 0, stdout=b"")


RUN = {4, 5, 6, 7, 8}


class FakeRunTest(BankCase):
    def setUp(self):
        super().setUp()
        study.write_text(os.path.join(self.repo, stack.VITEST_MJS), "")
        FakeVitest.calls = []
        FakeVitest.flaky = False
        FakeVitest.slow_ms = 100
        self.own = FakeRun()
        for patcher in (mock.patch.object(checks, "_popen", FakeVitest), mock.patch.object(verify_web, "_run", self.own),
                        mock.patch.object(stack, "find_node", lambda saved=None, probe=False: FAKE_NODE)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_fixture_passes_run_steps_and_cleans_up(self):
        code, out = self.verify("x01", "--runs", "2", steps=RUN)
        self.assertEqual(0, code, out)
        self.assertIn("템플릿의 기존 테스트 1개 통과", out)
        self.assertIn("모범 답안 검사 2번 반복, 결과 같음", out)
        self.assertIn("typescript 가 설치되어 있지 않아", out)
        self.assertEqual(4, len(FakeVitest.calls))  # 템플릿, step1, step2, 반복 1번
        self.assertEqual(1, len(self.own.calls))
        args, options = self.own.calls[0]
        self.assertEqual(["/fake/node", os.path.join(self.repo, "node_modules", "vitest", "vitest.mjs"), "run", "--root"], args[:4])
        self.assertEqual(study.NO_WINDOW, options["creationflags"])
        self.assertEqual("1", options["env"]["CI"])
        cmd, options = FakeVitest.calls[0]
        self.assertEqual("/fake/node", cmd[0])
        self.assertEqual(self.repo, options["cwd"])
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".web-check")))

    def test_template_that_already_passes_a_step_fails(self):
        self.replace("missions/x01/app/src/App.tsx", "누르기", "더하기")
        self.assertFails("1단계 검사가 템플릿에서 모두 통과합니다", "x01", steps=RUN)

    def test_solution_that_does_not_pass_its_step_fails(self):
        self.replace("missions/x01/work/solution/step2/src/App.tsx", "초기화", "리셋")
        out = self.assertFails("2단계까지 고친 코드에서 2단계 검사가 실패합니다", "x01", steps=RUN)
        self.assertIn("2a(", out)

    def test_solution_that_solves_the_next_step_early_fails(self):
        self.write("missions/x01/work/solution/step1/src/App.tsx", self.read("missions/x01/work/solution/step2/src/App.tsx"))
        self.assertFails("1단계까지 고친 코드에서 2단계 검사가 미리 통과합니다", "x01", steps=RUN)

    def test_flaky_checks_fail_the_repeat_step(self):
        FakeVitest.flaky = True
        self.assertFails("결과가 첫 실행과 다릅니다(불안정한 검사)", "x01", "--runs", "3", steps={6, 7})

    def test_slow_check_file_fails_the_timing_step(self):
        FakeVitest.slow_ms = 6000
        out = self.assertFails("검사 파일 하나가 5초를 넘습니다", "x01", "--runs", "1", steps={8})
        self.assertIn("step1.test.tsx 6.0초", out)

    def test_failing_template_tests_fail_step_4(self):
        self.own.fail = True
        self.assertFails("템플릿의 기존 테스트가 실패합니다: 제목이 보입니다", "x01", steps={4})

    def test_without_stack_or_node_the_run_steps_explain(self):
        os.remove(os.path.join(self.repo, stack.VITEST_MJS))
        self.assertFails("web install", "x01", steps=RUN)
        with mock.patch.object(stack, "find_node", lambda saved=None, probe=False: None):
            self.assertFails("Node.js 22.12 이상을 찾지 못해", "x01", steps=RUN)


@unittest.skipUnless(REAL_NODE, "Node.js 22.12 이상이 있어야 함")
class PageOutputTest(BankCase):
    BLOCK = "```js\nconsole.log('a');\nsetTimeout(() => console.log('b'), 0);\nconsole.log('c');\n```"

    def test_output_blocks_run_with_node_and_are_compared(self):
        self.append("learn/l90/page.md", self.BLOCK)
        self.edit_json("learn/l90/meta.json", lambda m: m.update(outputs=[{"block": 2, "expect": "a\nc\nb"}]))
        code, out = self.verify("l90", steps={1, 9})
        self.assertEqual(0, code, out)
        self.assertIn("2번 블록 출력 일치", out)
        self.edit_json("learn/l90/meta.json", lambda m: m.update(outputs=[{"block": 2, "expect": "a\nb\nc"}]))
        out = self.assertFails("2번 블록의 출력이 outputs[1].expect 와 다릅니다", "l90", steps={9})
        self.assertIn("실제: a c b", out)
        self.replace("learn/l90/page.md", "console.log('c');", "console.log('c'")
        self.assertFails("2번 블록이 node 에서 에러로 끝났습니다", "l90", steps={9})


@unittest.skipUnless(REAL_NODE and HAS_STACK, "저장소 맨 위 node_modules 와 Node 22.12 이상이 있어야 함")
class RealVitestTest(BankCase):
    """실제 vitest·jsdom 으로 고정 은행 x01 을 검증함. 템플릿은 두 단계 모두 떨어지고, step1 답은 1단계만, step2 답은 모두 통과함."""

    def test_fixture_mission_passes_and_a_broken_solution_fails(self):
        code, out = self.verify("x01", "--runs", "2", root=ROOT)
        self.assertEqual(0, code, out)
        self.assertIn("템플릿의 기존 테스트 1개 통과", out)
        self.assertIn("모범 답안 검사 2번 반복, 결과 같음", out)
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".web-check")))
        self.replace("missions/x01/work/solution/step2/src/App.tsx", "초기화", "리셋")
        out = self.assertFails("2단계까지 고친 코드에서 2단계 검사가 실패합니다", "x01", "--runs", "1", root=ROOT, steps={4, 5})
        self.assertIn('2a(이름이 "초기화"이고 역할(role)이 button인 요소를 화면에서 찾지 못했습니다.)', out)
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".web-check")))


class WebArtTest(unittest.TestCase):
    def test_names_and_limits(self):
        self.assertEqual(("page", "l01"), web_art.owner_of("l01-1"))
        self.assertEqual(("section", "3a"), web_art.owner_of("3a-12"))
        self.assertEqual(("mission", "w03"), web_art.owner_of("w03-4"))
        for bad in ("1-1a", "l1-1", "3A-1", "w03_1", "l01-1.gif"):
            self.assertIsNone(web_art.name_kind(bad), bad)
        self.assertEqual(6 * 1024 * 1024, web_art.LIMITS["total_bytes"])
        self.assertEqual(300 * 1024, web_art.LIMITS["gif_bytes"])

    @unittest.skipUnless(Image, "Pillow 없음")
    def test_figure_helper_checks_names_and_renders_a_module(self):
        from tools.web_art import figure as helper
        with self.assertRaises(ValueError):
            helper.WebFigure("1-1a", 560, 100)
        with self.assertRaises(ValueError):
            helper.WebFigure("l01-1", 600, 100)
        self.assertTrue(helper.belongs("3a-1", "l03", ("3a", "3b")))
        self.assertFalse(helper.belongs("4a-1", "l03", ("3a", "3b")))
        self.assertTrue(helper.belongs("w03-2", "w03"))
        module = types.ModuleType("fake_art")

        @helper.figure("l90-1", 200, 80)
        def box(fig):
            c = fig.frame(1400)
            c.box(10, 10, 60, 30, fill="selection")
            c.text(20, 50, "글", "ink", 12)

        module.box = box
        tmp = tempfile.mkdtemp(prefix="web_art_")
        self.addCleanup(shutil.rmtree, tmp, True)
        rows = helper.render_module(module, tmp, check=True, owner="l90")
        self.assertEqual(1, len(rows))
        self.assertEqual(("l90-1", "png", []), (rows[0]["name"], rows[0]["kind"], rows[0]["problems"]))
        self.assertTrue(os.path.isfile(os.path.join(tmp, "l90-1.png")))
        rows = helper.render_module(module, tmp, owner="l91")
        self.assertIn("이름이 l91 의 그림 규칙에 맞지 않습니다", rows[0]["problems"])


if __name__ == "__main__":
    unittest.main()
