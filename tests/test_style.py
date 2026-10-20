# -*- coding: utf-8 -*-
"""문장 검사기 tools/check_style.py 의 테스트. 일부러 틀린 문장을 담고 있어 검사기의 select() 가 이 파일은 빼놓음.

고정 패턴마다 걸리는 문장과 통과하는 문장을 하나씩 두고, 기록·가이드 말투, 커밋 메시지 규칙, 바뀐 파일 고르기(임시 git 저장소),
훅 설치, sealed.json 안의 글, .gitignore 의 평문 규칙을 봄. 걸리는 문장은 지적받아 고친 문장의 꼴을 이 프로그램의 글로 옮겨 씀.

실행: python -m unittest tests.test_style
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402

_spec = importlib.util.spec_from_file_location("check_style", os.path.join(ROOT, "tools", "check_style.py"))
check_style = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_style)

HAS_GIT = shutil.which("git") is not None


def git_env():
    """개발자의 전역·시스템 git 설정과 바깥 훅이 넘긴 GIT_DIR 류를 끊은 환경. 전역 core.hooksPath 에 훅이 복사되지 않게 함."""
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
               XDG_CONFIG_HOME=os.path.join(tempfile.gettempdir(), "check-style-no-config"))  # 전역 ignore·attributes 파일도 끊음
    return env


# 규칙 이름 → (걸리는 문장, 같은 뜻으로 고친 문장). 고친 문장은 다른 규칙에도 걸리지 않아야 함
FIXED_CASES = {
    "em-dash(\u2014)": ("단추를 누르면 PR 이 올라갑니다 \u2014 프로그램이 대신 올립니다.", "단추를 누르면 프로그램이 PR 을 대신 올립니다."),
    "예고형 도입": ("이번 글에서는 제출 흐름을 알아보겠습니다.", "제출 단추를 누르면 풀이가 브랜치로 올라갑니다."),
    "기계 순서": ("먼저 저장소를 받습니다.", "저장소를 받은 뒤 프로그램을 켭니다."),
    "단정 요약(개수 세기)": ("채점 방법은 하나입니다.", "답을 테스트의 기대 출력과 비교해 채점합니다."),
    "은유": ("이 문제가 이번 던전의 관문이에요.", "이 문제를 풀어야 다음 방이 열립니다."),
    "담화표지": ("정리하면 제출은 단추를 누르는 것으로 끝납니다.", "제출은 단추를 누르면 끝납니다."),
    "해석 덧붙이기": ("검사를 통과했다는 뜻입니다.", "검사를 통과했습니다."),
    "빈 예고문": ("설치 순서는 다음과 같습니다.", "설치는 아래 순서로 합니다."),
    "추상 서술어": ("윈도우는 사정이 다릅니다.", "윈도우에서는 설치 파일을 따로 받습니다."),
    "속 빈 수식": ("다양한 문제를 손쉽게 풀 수 있습니다.", "문제를 고르고 바로 풉니다."),
    "정형 마무리": ("도움이 되셨길 바랍니다.", "다음 회차는 월요일에 엽니다."),
    "강조 부사": ("채점이 정말 빠릅니다.", "채점은 1초 안에 끝납니다."),
    "이모지": ("채점 완료 ✅ 100점입니다.", "채점이 끝났습니다. 100점입니다."),
    "느낌표": ("축하합니다! 보스를 통과했습니다.", "축하합니다. 보스를 통과했습니다."),
}


def names(fails):
    return [name for name, _ in fails]


def run(cwd, *args):
    """GitRepoTest 가 os.environ 을 git_env() 로 바꿔 둔 상태에서 git 을 부름."""
    done = subprocess.run(["git"] + list(args), cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid"))
    if done.returncode != 0:
        raise AssertionError("git %s → %d\n%s%s" % (" ".join(args), done.returncode, done.stdout, done.stderr))
    return done.stdout


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class FixedPatternTest(unittest.TestCase):
    def test_each_rule_catches_one_sentence_and_passes_the_fix(self):
        for rule, (bad, good) in FIXED_CASES.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, names(check_style.check(bad + "\n", path="docs/x.md")))
                self.assertEqual([], check_style.check(good + "\n", path="docs/x.md"))

    def test_short_summary_after_long_sentence(self):
        bad = "검사 통과를 확인하고 단추를 누르면 폴더가 브랜치로 올라가고 PR 만들기입니다. 프로그램이 대신 합니다.\n"
        good = "검사 통과를 확인하고 단추를 누르면 폴더가 브랜치로 올라가고 PR 이 만들어집니다.\n"
        self.assertIn("긴 설명 뒤 짧은 정리문", names(check_style.check(bad, path="README.md")))
        self.assertEqual([], check_style.check(good, path="README.md"))

    def test_pointer_closing_sentence(self):
        bad = "입력이 10만 개를 넘으면 이중 반복문 풀이는 시간 초과가 납니다. 10만 개가 그 경계입니다.\n"
        good = "입력이 10만 개를 넘으면 이중 반복문 풀이는 시간 초과가 납니다.\n"
        self.assertIn("앞 내용을 가리키며 닫는 단문", names(check_style.check(bad, path="README.md")))
        self.assertEqual([], check_style.check(good, path="README.md"))

    def test_same_shaped_bullets(self):
        bad = "- **풀기**: 문항을 골라 풉니다.\n- **채점**: 답을 맞춥니다.\n- **제출**: PR 을 올립니다.\n"
        good = "- 문항을 골라 풉니다.\n- 답을 맞춥니다.\n- PR 을 올립니다.\n"
        self.assertIn("불릿마다 같은 '**라벨** 설명' 꼴", names(check_style.check(bad, path="README.md")))
        self.assertEqual([], check_style.check(good, path="README.md"))
        two = "- **풀기**: 문항을 골라 풉니다.\n- **채점**: 답을 맞춥니다.\n"
        self.assertNotIn("불릿마다 같은 '**라벨** 설명' 꼴", names(check_style.check(two, path="README.md")))

    def test_code_blocks_tables_and_inline_code_are_skipped(self):
        text = "설치는 아래 순서로 합니다.\n\n```\n먼저 받습니다.\n```\n\n| 열 | 정말 빠릅니다 |\n|---|---|\n\n`정말 빠릅니다` 라는 글자를 찍습니다.\n"
        self.assertEqual([], check_style.check(text, path="README.md"))


class ToneTest(unittest.TestCase):
    def test_record_tone_in_python_comments_and_docstrings(self):
        bad = '"""python study.py 로 창이 열린다."""\n# 채점은 자식 프로세스에서 한다.\nX = 1\n'
        good = '"""python study.py 로 창이 열림."""\n# 채점은 자식 프로세스에서 함\nX = 1\n'
        fails = check_style.check(bad, path="gui/x.py")
        self.assertEqual(["기록 문장은 ~함/~음/~했음/~임 체"] * 2, names(fails))
        self.assertEqual([], check_style.check(good, path="gui/x.py"))

    def test_screen_strings_in_python_are_guide(self):
        self.assertEqual([], check_style.check('MSG = "창이 열립니다."\n', path="gui/x.py"))
        text = 'BAD = "제출 흐름을 알아보겠습니다."\nPAT = r"알아보겠습니다"\n'
        self.assertEqual(["예고형 도입"] * 2, names(check_style.check(text, path="gui/x.py")))  # raw 문자열도 글로 봄

    def test_guide_tone_in_markdown(self):
        self.assertIn("가이드 문장은 ~니다 체", names(check_style.check("회차를 골라 풀었음.\n", path="README.md")))
        self.assertEqual([], check_style.check("회차를 골라 풉니다.\n", path="README.md"))

    def test_yaml_comments_are_record_and_values_are_guide(self):
        bad = "name: 문장 검사\n# 풀이만 바꾼 PR 에서는 돌지 않는다.\n"
        good = "name: 문장 검사\n# 풀이만 바꾼 PR 에서는 돌지 않음\nrun: echo 검사를 시작합니다.\n"
        self.assertEqual(["기록 문장은 ~함/~음/~했음/~임 체"], names(check_style.check(bad, path=".github/workflows/x.yml")))
        self.assertEqual([], check_style.check(good, path=".github/workflows/x.yml"))

    def test_exclamation_and_emoji_are_not_checked_in_code(self):
        self.assertEqual([], check_style.check('MARK = "✅ 통과!"\n', path="gui/x.py"))


class CommitTest(unittest.TestCase):
    def check(self, text):
        return names(check_style.check(text, commit=True))

    def test_subject_format(self):
        self.assertIn("커밋 제목 형식(type(scope): 내용)", self.check("세션 서비스 계층 추가 (GUI·CLI 공용)\n"))
        self.assertEqual([], self.check("feat(gui): 창에서 풀기·채점·해설·제출까지 (PyQt6)\n"))
        self.assertEqual([], self.check("Merge branch 'dev'\n"))

    def test_body_tone_and_bullets(self):
        self.assertIn("기록 문장은 ~함/~음/~했음/~임 체", self.check("fix(gui): 창 크기를 고침\n\n창이 작게 열리던 것을 고쳤다.\n"))
        self.assertEqual([], self.check("fix(gui): 창 크기를 고침\n\n창이 작게 열리던 것을 고침.\n"))
        many = "feat(x): 더함\n\n" + "".join("- 항목 %d 를 더함\n" % k for k in range(5))
        self.assertIn("커밋 본문에 불릿 5개 이상(요약 나열 대신 한두 문장으로)", self.check(many))

    def test_co_authored_by_line_is_rejected(self):
        text = "feat(journey): 던전 지도를 그림\n\nCo-Authored-By: Someone <someone@example.invalid>\n"
        self.assertEqual(["커밋에 넣지 않는 줄(Co-Authored-By:)"], self.check(text))
        lower = "feat(journey): 던전 지도를 그림\n\n   co-authored-by: someone <someone@example.invalid>\n"
        self.assertEqual(["커밋에 넣지 않는 줄(Co-Authored-By:)"], self.check(lower))

    def test_generated_with_line_is_rejected(self):
        text = "docs: README 에 여정 안내를 더함\n\nGenerated with some editor plugin\n"
        self.assertEqual(["커밋에 넣지 않는 줄(Generated with)"], self.check(text))
        self.assertEqual(["커밋에 넣지 않는 줄(Generated with)"], self.check("docs: 안내를 더함\n\n이 글은 generated with 표시가 있음\n"))

    def test_sentence_about_the_rule_passes(self):
        text = "docs: 커밋 규칙을 적음\n\n공동 작성자 줄은 넣지 않음. 제목은 type(scope) 꼴로 씀.\n"
        self.assertEqual([], self.check(text))

    def test_git_comment_lines_are_ignored(self):
        text = "feat(x): 더함\n# Please enter the commit message. Generated with care.\n# Co-Authored-By: 라고 쓰지 마세요\n"
        self.assertEqual([], self.check(text))

    def test_em_dash_in_commit_is_not_checked(self):
        self.assertEqual([], self.check("chore: 이름을 바꿈 \u2014 프로그램 이름도\n"))

    def test_main_with_commit_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "msg.txt", "feat(x): 더함\n\nCo-Authored-By: Someone <s@example.invalid>\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = check_style.main(["--commit", path])
            self.assertEqual(1, rc)
            self.assertIn("Co-Authored-By:", out.getvalue())
            path = write(tmp, "ok.txt", "feat(x): 더함\n")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, check_style.main(["--commit", path]))


class SelectTest(unittest.TestCase):
    def test_which_changed_files_are_checked(self):
        paths = [
            "README.md", "docs/CRITERIA.md", "problems/s01/p1/problem.md", "dungeons/d01/intro.md", "dungeons/d01/p1/problem.md",
            "dungeons/d01/sealed.json", "dungeons/d01/p1/problem.json", "dungeons/d01/assets/1-1a.gif", "dungeons/index.json",
            "study.py", "gitflow.py", "gui/hub_page.py", "journey/runner.py", "tools/journey_art/d01.py", "tests/test_gui.py",
            "tests/test_style.py", "submissions/alice/README.md", "submissions/alice/journey/progress.json",
            ".github/workflows/style.yml", ".github/workflows/ci.yml", "start.bat", "gui\\window.py",
        ]
        self.assertEqual([
            "README.md", "docs/CRITERIA.md", "problems/s01/p1/problem.md", "dungeons/d01/intro.md", "dungeons/d01/p1/problem.md",
            "dungeons/d01/sealed.json", "study.py", "gitflow.py", "gui/hub_page.py", "journey/runner.py", "tools/journey_art/d01.py",
            ".github/workflows/style.yml", ".github/workflows/ci.yml", "gui/window.py",
        ], check_style.select(paths))


@unittest.skipUnless(HAS_GIT, "git 이 있어야 함")
class GitRepoTest(unittest.TestCase):
    """임시 git 저장소에서 --changed, --staged, --install-hooks 를 봄. 실제 저장소와 전역 git 설정은 건드리지 않음.
    검사기가 부르는 git 도 같은 환경을 쓰도록 테스트 동안 os.environ 을 git_env() 로 바꿔 둠."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ, git_env(), clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        run(self.repo, "init", "-q", "-b", "main")
        write(self.repo, "README.md", "프로그램을 켭니다.\n")
        write(self.repo, "submissions/alice/README.md", "풀이\n")
        write(self.repo, "gui/a.py", "# 창을 엶\n")
        shutil.copytree(os.path.join(ROOT, "tools", "hooks"), os.path.join(self.repo, "tools", "hooks"))
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-qm", "chore: 시작")

    def test_changed_lists_files_since_merge_base_and_select_filters(self):
        run(self.repo, "checkout", "-qb", "work")
        write(self.repo, "README.md", "프로그램을 켜고 문제를 풉니다.\n")
        write(self.repo, "dungeons/d01/intro.md", "무대입니다.\n")
        write(self.repo, "submissions/alice/README.md", "바뀐 풀이\n")
        write(self.repo, "tests/test_style.py", "# 테스트\n")
        os.remove(os.path.join(self.repo, "gui", "a.py"))
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-qm", "feat: 바꿈")
        run(self.repo, "checkout", "-q", "main")  # main 이 더 나아가도 merge-base 기준이라 결과가 같음
        write(self.repo, "docs/x.md", "안내입니다.\n")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-qm", "docs: 더함")
        run(self.repo, "checkout", "-q", "work")
        changed = check_style.changed_paths("main", root=self.repo)
        self.assertEqual(["README.md", "dungeons/d01/intro.md", "submissions/alice/README.md", "tests/test_style.py"], sorted(changed))
        self.assertEqual(["README.md", "dungeons/d01/intro.md"], check_style.select(sorted(changed)))

    def test_staged_lists_only_the_index(self):
        write(self.repo, "README.md", "프로그램을 켜고 문제를 풉니다.\n")
        write(self.repo, "docs/new.md", "안내입니다.\n")
        run(self.repo, "add", "README.md")
        self.assertEqual(["README.md"], check_style.changed_paths(staged=True, root=self.repo))

    def test_staged_reads_the_index_not_the_working_copy(self):
        bad = "이번 글에서는 제출 흐름을 알아보겠습니다.\n"
        good = "프로그램을 켜고 문제를 풉니다.\n"
        write(self.repo, "README.md", bad)
        run(self.repo, "add", "README.md")
        write(self.repo, "README.md", good)
        with mock.patch.object(check_style, "ROOT", self.repo), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, check_style.main(["--staged"]))
        run(self.repo, "add", "README.md")
        write(self.repo, "README.md", bad)
        with mock.patch.object(check_style, "ROOT", self.repo), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, check_style.main(["--staged"]))
        run(self.repo, "add", "README.md")
        write(self.repo, "dungeons/d01/sealed.json", json.dumps({"blob": study.seal_blob({"p1/hints.md": bad})}))
        run(self.repo, "add", "dungeons/d01/sealed.json")
        write(self.repo, "dungeons/d01/sealed.json", "{}")
        out = io.StringIO()
        with mock.patch.object(check_style, "ROOT", self.repo), contextlib.redirect_stdout(out):
            self.assertEqual(1, check_style.main(["--staged"]))
        self.assertIn("예고형 도입", out.getvalue())
        self.assertIn("[dungeons/d01/sealed.json:p1/hints.md]", out.getvalue())

    def test_main_changed_checks_the_picked_files(self):
        run(self.repo, "checkout", "-qb", "work")
        write(self.repo, "README.md", "이번 글에서는 제출 흐름을 알아보겠습니다.\n")
        write(self.repo, "submissions/alice/README.md", "이번 글에서는 제출 흐름을 알아보겠습니다.\n")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-qm", "docs: 바꿈")
        out = io.StringIO()
        with mock.patch.object(check_style, "ROOT", self.repo), contextlib.redirect_stdout(out):
            rc = check_style.main(["--changed", "main"])
        self.assertEqual(1, rc)
        self.assertIn("[README.md]", out.getvalue())
        self.assertNotIn("submissions", out.getvalue())
        with mock.patch.object(check_style, "ROOT", self.repo), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(2, check_style.main(["--changed"]))
            self.assertEqual(0, check_style.main(["--staged"]))

    def hooks_dir(self):
        return os.path.join(run(self.repo, "rev-parse", "--absolute-git-dir").strip(), "hooks")

    def test_install_hooks_copies_both_and_makes_them_executable(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, check_style.install_hooks(self.repo))
        for name in ("pre-commit", "commit-msg"):
            dst = os.path.join(self.hooks_dir(), name)
            self.assertEqual(read(os.path.join(ROOT, "tools", "hooks", name)), read(dst))
            if os.name != "nt":  # 윈도우에는 실행 비트가 없음
                self.assertTrue(os.stat(dst).st_mode & stat.S_IXUSR)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, check_style.install_hooks(self.repo))  # 같은 내용이면 다시 설치해도 0

    def test_install_hooks_keeps_a_different_existing_hook(self):
        mine = "#!/bin/sh\nexec python3 /somewhere/else/checker.py --commit \"$1\"\n"
        write(self.hooks_dir(), "commit-msg", mine)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(1, check_style.install_hooks(self.repo))
        self.assertEqual(mine, read(os.path.join(self.hooks_dir(), "commit-msg")))
        self.assertIn("이미 있는 훅을 그대로 두었습니다", out.getvalue())
        self.assertIn("tools/hooks/commit-msg", out.getvalue())
        self.assertEqual(read(os.path.join(ROOT, "tools", "hooks", "pre-commit")), read(os.path.join(self.hooks_dir(), "pre-commit")))

    def test_install_hooks_from_a_worktree_lands_in_the_shared_hooks_dir(self):
        wt = os.path.join(self.tmp, "wt")
        run(self.repo, "worktree", "add", "-q", "-b", "side", wt)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, check_style.install_hooks(wt))
        self.assertTrue(os.path.isfile(os.path.join(self.hooks_dir(), "pre-commit")))
        self.assertFalse(os.path.isdir(os.path.join(wt, ".git")))

    def test_install_hooks_outside_a_repo(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(2, check_style.install_hooks(plain))


class SealedTest(unittest.TestCase):
    def test_notes_inside_sealed_json_are_checked_and_secrets_are_not(self):
        files = {
            "p1/hints.md": "## 1\n이번 힌트에서는 두 포인터를 알아보겠습니다.\n",
            "p1/explain.md": "## 풀이\n왼쪽 끝과 오른쪽 끝에서 안쪽으로 좁힙니다.\n",
            "p1/solution.py": "def solution(a):\n    return a  # 정말 빠르다.\n",
            "review.json": "{}",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "sealed.json", json.dumps({"note": "봉인", "blob": study.seal_blob(files)}))
            got = check_style.check_path(path, shown="dungeons/d01/sealed.json")
            self.assertEqual(["dungeons/d01/sealed.json:p1/explain.md", "dungeons/d01/sealed.json:p1/hints.md"], [n for n, _ in got])
            self.assertEqual([], got[0][1])
            self.assertEqual(["예고형 도입"], names(got[1][1]))
            broken = write(tmp, "d02/sealed.json", '{"note": "봉인", "blob": "not-a-blob"}')
            got = check_style.check_path(broken)
            self.assertEqual(1, len(got))
            self.assertEqual(["sealed.json 을 풀 수 없음"], names(got[0][1]))


class RepoFilesTest(unittest.TestCase):
    """저장소에 든 훅, style.yml, .gitignore 가 명세대로인지 봄."""

    SECRET = ["solution.py", "solution.js", "brute.py", "certify.py", "alt.py", "alt.js", "gen.py", "validate.py", "tests.json",
              "extra.json", "wrong.json", "hints.md", "explain.md", "review.json"]
    PUBLIC = ["dungeons/index.json", "dungeons/d01/meta.json", "dungeons/d01/intro.md", "dungeons/d01/sealed.json",
              "dungeons/d01/assets/1-1a.gif", "dungeons/d01/p1/problem.md", "dungeons/d01/p1/problem.json",
              "tests/journey_bank/t01/p1/solution.py", "tests/journey_bank/t01/p1/tests.json"]

    def test_hook_scripts(self):
        pre = read(os.path.join(ROOT, "tools", "hooks", "pre-commit"))
        msg = read(os.path.join(ROOT, "tools", "hooks", "commit-msg"))
        self.assertTrue(pre.startswith("#!/bin/sh\n") and msg.startswith("#!/bin/sh\n"))
        self.assertIn("exec python3 tools/check_style.py --staged", pre)
        self.assertIn('exec python3 tools/check_style.py --commit "$1"', msg)
        for name in check_style.HOOK_NAMES:
            if os.name != "nt":
                self.assertTrue(os.access(os.path.join(ROOT, "tools", "hooks", name), os.X_OK), name)

    def test_style_workflow_runs_on_pull_requests_except_submissions(self):
        text = read(os.path.join(ROOT, ".github", "workflows", "style.yml"))
        self.assertIn("name: 문장 검사\n", text)
        self.assertIn("pull_request:\n    types: [opened, synchronize, reopened, edited]\n    paths-ignore:\n      - \"submissions/**\"\n", text)
        self.assertNotIn("\n  push:", text)
        self.assertIn("check_style.py --changed", text)
        self.assertIn("check_style.py --commit", text)
        self.assertEqual([], check_style.check(text, path="style.yml"))

    @unittest.skipUnless(HAS_GIT, "git 이 있어야 함")
    def test_gitignore_hides_plaintext_bank_files_only(self):
        def ignored(rel):
            return subprocess.run(["git", "check-ignore", "-q", "--no-index", rel], cwd=ROOT, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=git_env()).returncode == 0
        for name in self.SECRET:
            self.assertTrue(ignored("dungeons/d01/p1/" + name), name)
            self.assertTrue(ignored("dungeons/d01/boss/" + name), name)
        self.assertTrue(ignored("dungeons/d01/p1/wrong/rescan.py"))
        self.assertTrue(ignored("dungeons/d01/p1/wrong/rescan.js"))
        self.assertTrue(ignored("dungeons/d01/review.json"))
        for rel in self.PUBLIC:
            self.assertFalse(ignored(rel), rel)

    @unittest.skipUnless(HAS_GIT, "git 이 있어야 함")
    def test_gitattributes_marks_images_binary_and_hooks_lf(self):
        def attr(name, *paths):
            return subprocess.run(["git", "check-attr", name] + list(paths), cwd=ROOT, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, text=True, encoding="utf-8", env=git_env()).stdout.strip().splitlines()
        self.assertEqual(["dungeons/d01/assets/a.gif: binary: set", "dungeons/d01/assets/a.png: binary: set"],
                         attr("binary", "dungeons/d01/assets/a.gif", "dungeons/d01/assets/a.png"))
        self.assertEqual(["tools/hooks/pre-commit: eol: lf", "tools/hooks/commit-msg: eol: lf"],
                         attr("eol", "tools/hooks/pre-commit", "tools/hooks/commit-msg"))


class MainTest(unittest.TestCase):
    def test_no_targets(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, check_style.main([]))
        self.assertIn("검사할 파일이 없습니다.", out.getvalue())

    def test_workflow_passes_and_the_checker_is_left_out(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, check_style.main([os.path.join(ROOT, ".github", "workflows", "style.yml")]))
        self.assertEqual([], check_style.select(["tools/check_style.py"]))
        path = os.path.join(ROOT, "tools", "check_style.py")
        text = read(path)
        self.assertNotIn("\u2014", text)  # 고르기에서 빠지므로 줄표 글자와 주석 말투는 여기서 봄
        records, _ = check_style.code_text(path, text)
        self.assertEqual([], check_style.record_fails(records))


if __name__ == "__main__":
    unittest.main()
