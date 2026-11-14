# -*- coding: utf-8 -*-
"""학습자 업데이트의 main 전환과 로컬 풀이 보존을 임시 저장소에서 확인함."""
import os
import unittest
from pathlib import Path
from unittest import mock

import gitflow
from tests import test_gitflow as fixtures


git = fixtures.git


@unittest.skipUnless(fixtures.git_version() >= (2, 38), "git 2.38 이상이 필요합니다")
class MainUpdateTest(unittest.TestCase):
    # 준비·정리 함수만 조합해 기존 검사 메서드의 상속 수집을 피함.
    setUpClass = classmethod(fixtures.GitFlowTest.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GitFlowTest.tearDownClass.__func__)
    tearDown = fixtures.GitFlowTest.tearDown

    def setUp(self):
        protocol = mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "file"})
        protocol.start()
        self.addCleanup(protocol.stop)
        http = mock.patch.object(gitflow.urllib.request, "urlopen",
                                 side_effect=AssertionError("외부 HTTP 요청을 허용하지 않습니다."))
        self.http = http.start()
        self.addCleanup(http.stop)
        self.addCleanup(self.http.assert_not_called)
        fixtures.GitFlowTest.setUp(self)

    def new_pc(self, name, *clone_options):
        pc = fixtures.GitFlowTest.new_pc(self, name, *clone_options)
        pc.flow = gitflow.GitFlow(pc.path, pc.user)
        pc.flow.find_pr = pc.find_pr
        pc.flow.pr_wait = 0
        self.assertFalse(pc.flow.legacy_contract)
        return pc

    def write_bytes(self, pc, rel, data):
        path = Path(pc.path, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def checkout_state(self, root):
        files = {}
        for base, dirs, names in os.walk(root):
            dirs[:] = [name for name in dirs if name != ".git"]
            for name in names:
                if name != ".git":
                    path = Path(base, name)
                    files[path.relative_to(root).as_posix()] = path.read_bytes()
        return {
            "files": files,
            "status": git(root, "status", "--porcelain=v1", "-z").stdout,
            "index": git(root, "ls-files", "--stage", "-z").stdout,
            "branch": git(root, "symbolic-ref", "--short", "HEAD").stdout,
            "refs": git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/").stdout,
            "upstream": git(root, "config", "--get-regexp", r"^branch\.main\.", check=False).stdout,
        }

    def assert_main(self, pc=None):
        pc = pc or self.pc
        self.assertEqual({
            "branch": git(pc.path, "branch", "--show-current").stdout.strip(),
            "head": git(pc.path, "rev-parse", "HEAD").stdout.strip(),
            "main": git(pc.path, "rev-parse", "main").stdout.strip(),
            "upstream": git(pc.path, "rev-parse", "--abbrev-ref", "main@{upstream}", check=False).stdout.strip(),
            "remote": git(pc.path, "config", "--get", "branch.main.remote", check=False).stdout.strip(),
            "merge": git(pc.path, "config", "--get", "branch.main.merge", check=False).stdout.strip(),
        }, {
            "branch": "main", "head": self.server.rev("main"), "main": self.server.rev("main"),
            "upstream": "origin/main", "remote": "origin", "merge": "refs/heads/main",
        })
        self.assertEqual(git(pc.path, "rev-parse", "HEAD").stdout,
                         git(pc.path, "rev-parse", "origin/main").stdout)

    def assert_result(self, result, status="ok", changed=False, restart=False):
        self.assertEqual((result["status"], result["changed"], result["restart"]),
                         (status, changed, restart), result)

    def test_fresh_clone_updates_code_and_deletions_on_main(self):
        pc = self.pc
        self.server.add_files({"study.py": "VERSION = 2\n", "learning_data/new.py": "VALUE = 2\n"},
                              "프로그램 갱신")
        git(self.server.dir, "rm", "problems/s02/quiz.md")
        git(self.server.dir, "commit", "-qm", "이전 문제 삭제")
        git(self.server.dir, "push", "-q", "origin", "main")
        self.assert_result(pc.flow.sync(), changed=True, restart=True)
        self.assert_main()
        self.assertEqual(Path(pc.path, "study.py").read_bytes(), b"VERSION = 2\n")
        self.assertEqual(Path(pc.path, "learning_data/new.py").read_bytes(), b"VALUE = 2\n")
        self.assertFalse(Path(pc.path, "problems/s02/quiz.md").exists())
        self.server.add_files({"problems/s01/quiz.md": "# Updated question\n"}, "문제 수정")
        self.assert_result(pc.flow.sync(), changed=True)
        self.assert_main()
        self.assert_result(pc.flow.sync())

    def test_sync_never_commits_adds_pushes_or_creates_a_study_branch(self):
        pc = self.pc
        self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 7\r\n")
        self.server.add_problems("s03")
        remote_refs = git(self.origin, "show-ref").stdout
        os.environ["GIT_CONFIG_GLOBAL"] = self.config_no_identity
        with mock.patch.object(pc.flow, "_git", wraps=pc.flow._git) as calls:
            result = pc.flow.sync()
        forbidden = [call.args for call in calls.call_args_list
                     if call.args and call.args[0] in ("commit", "commit-tree", "add", "push")]
        self.assertEqual(forbidden, [])
        self.assert_result(result, changed=True, restart=True)
        self.assertEqual(git(pc.path, "for-each-ref", "--format=%(refname)", "refs/heads/study/").stdout, "")
        self.assertEqual(git(self.origin, "show-ref").stdout, remote_refs)
        self.assertEqual(pc.lookups, [])
        self.assert_main()

    def test_tracked_untracked_deleted_and_crlf_answers_survive_remote_collisions(self):
        pc = self.pc
        prefix = "submissions/alice/"
        originals = {prefix + name: "answer = 1\n" for name in
                     ("tracked.py", "staged.py", "deleted.py", "staged-deleted.py", "unchanged.py")}
        self.server.add_files(originals, "기존 공개 풀이")
        git(pc.path, "config", "core.autocrlf", "true")
        git(pc.path, "fetch", "-q", "origin")
        git(pc.path, "merge", "--ff-only", "origin/main")
        self.write_bytes(pc, prefix + "tracked.py", b"answer = 21\r\n")
        self.write_bytes(pc, prefix + "staged.py", b"answer = 22\r\n")
        git(pc.path, "add", "--", prefix + "staged.py")
        Path(pc.path, prefix + "deleted.py").unlink()
        git(pc.path, "rm", "--", prefix + "staged-deleted.py")
        self.write_bytes(pc, prefix + "draft.py", b"answer = 23\r\n")
        self.write_bytes(pc, prefix + "raw.bin", b"\x00\xff\r\n\x80")
        before = pc.read()
        self.assertEqual(before[prefix + "unchanged.py"], b"answer = 1\r\n")
        incoming = {name: "answer = 99\n" for name in originals}
        incoming.update({prefix + "draft.py": "answer = 99\n", "study.py": "VERSION = 2\n"})
        self.server.add_files(incoming, "프로그램과 공개 풀이 갱신")
        result = pc.flow.sync()
        self.assertEqual(pc.read(), before)
        self.assert_result(result, changed=True, restart=True)
        self.assert_main()
        self.assert_result(pc.flow.sync())
        self.assertEqual(pc.read(), before)

    def test_ignored_own_folder_keeps_untracked_answers_when_remote_adds_the_same_path(self):
        pc = self.pc
        rel = "submissions/alice/nested/draft.py"
        Path(pc.gitdir("info", "exclude")).write_bytes(b"submissions/alice/\n")
        self.write_bytes(pc, rel, b"answer = 17\r\n")
        self.write_bytes(pc, "submissions/alice/raw.bin", b"\x00\xff\r\n\x80")
        self.assertEqual(git(pc.path, "ls-files", "--", rel).stdout, "")
        self.assertEqual(git(pc.path, "ls-files", "--others", "--ignored", "--exclude-standard",
                             "--", rel).stdout.strip(), rel)
        before = pc.read()
        self.server.add_files({rel: "answer = 99\n", "study.py": "VERSION = 2\n"},
                              "프로그램과 공개 풀이 추가")
        result = pc.flow.sync()
        self.assertEqual(pc.read(), before)
        self.assert_result(result, changed=True, restart=True)
        self.assert_main()
        self.assertEqual(Path(pc.path, "study.py").read_bytes(), b"VERSION = 2\n")

    def test_ignored_program_collision_preserves_original_or_backs_it_up(self):
        original = b"LOCAL_ONLY = 'keep'\r\n"
        incoming = b"REMOTE_VERSION = 2\n"
        cases = (
            ("file", "tools/local.py", "tools/local.py", "tools/local.py"),
            ("directory", "tools/local-dir.py/nested/keep.bin", "tools/local-dir.py", "tools/local-dir.py/"),
            ("parent-file", "tools/local-parent", "tools/local-parent/new.py", "tools/local-parent"),
            ("case", "tools/case/local.py", "tools/case/Local.py", "tools/case/local.py"),
        )
        for kind, local_rel, remote_rel, ignore in cases:
            pc = self.pc if kind == "file" else self.new_pc("ignored-" + kind)
            Path(pc.gitdir("info", "exclude")).write_bytes((ignore + "\n").encode("utf-8"))
            self.write_bytes(pc, local_rel, original)
            source, target = Path(pc.path, local_rel), Path(pc.path, remote_rel)
            alias = kind == "case" and target.exists() and target.samefile(source)
            with self.subTest(collision=kind, case_alias=alias):
                self.assertEqual(git(pc.path, "ls-files", "--", local_rel).stdout, "")
                self.assertEqual(git(pc.path, "ls-files", "--others", "--exclude-standard", "--", local_rel).stdout, "")
                self.assertEqual(git(pc.path, "ls-files", "--others", "--ignored", "--exclude-standard",
                                     "--", local_rel).stdout.strip(), local_rel)
                self.server.add_files({remote_rel: incoming.decode("utf-8")}, "프로그램 파일 추가")
                result = pc.flow.sync()
                current = source.read_bytes() if source.is_file() else None
                if kind == "case" and not alias:
                    # 대소문자를 구분하는 파일시스템에서는 소문자 파일을 건드리지 않음.
                    self.assertEqual(current, original, result)
                    self.assertIsNone(result["backup"], result)
                    self.assertEqual(result["status"], "ok", result)
                else:
                    if current != original or result["status"] == "ok":
                        self.assertIsNotNone(result["backup"], {"result": result, "original": original, "current": current})
                        saved = Path(result["backup"], "outside", local_rel)
                        self.assertTrue(saved.is_file(), result)
                        self.assertEqual(saved.read_bytes(), original)
                    self.assertIn(result["status"], ("blocked", "error", "ok"), result)
                    if result["status"] == "error":
                        self.assertEqual(current, original, result)
                if result["status"] == "ok":
                    self.assert_result(result, changed=True, restart=True)
                    self.assertEqual(target.read_bytes(), incoming)
                    self.assert_main(pc)

    def test_unique_staged_answer_blocks_before_files_index_or_branches_change(self):
        pc = self.pc
        rel = "submissions/alice/answer.py"
        self.server.add_files({rel: "answer = 1\n"}, "기존 공개 풀이")
        git(pc.path, "config", "core.autocrlf", "true")
        git(pc.path, "fetch", "-q", "origin")
        git(pc.path, "merge", "--ff-only", "origin/main")
        self.write_bytes(pc, rel, b"answer = 2\r\n")
        git(pc.path, "add", "--", rel)
        self.write_bytes(pc, rel, b"answer = 3\r\n")
        self.write_bytes(pc, "gui/app.py", b"LOCAL = True\n")
        head = git(pc.path, "rev-parse", "HEAD:" + rel).stdout.strip()
        staged = git(pc.path, "rev-parse", ":" + rel).stdout.strip()
        self.assertEqual(staged, fixtures.blob_sha(b"answer = 2\n"))
        self.assertEqual(len({head, staged, fixtures.blob_sha(Path(pc.path, rel).read_bytes())}), 3)
        before, answers = self.checkout_state(pc.path), pc.read()
        self.server.add_files({"study.py": "VERSION = 2\n"}, "프로그램 갱신")
        result = pc.flow.sync()
        self.assertEqual(pc.read(), answers)
        self.assertEqual(git(pc.path, "rev-parse", ":" + rel).stdout.strip(), staged)
        self.assertEqual(self.checkout_state(pc.path), before)
        self.assert_result(result, status="blocked")

    def test_renamed_program_file_backs_up_ignored_destination(self):
        pc = self.pc
        self.server.add_files({"tools/template.py": "VALUE = 1\n"}, "프로그램 예제")
        self.assert_result(pc.flow.sync(), changed=True, restart=True)
        Path(pc.gitdir("info", "exclude")).write_text("tools/config.py\n", encoding="utf-8")
        self.write_bytes(pc, "tools/config.py", b"LOCAL = True\r\n")
        git(self.server.dir, "mv", "tools/template.py", "tools/config.py")
        git(self.server.dir, "commit", "-qm", "프로그램 파일 이름 변경")
        git(self.server.dir, "push", "-q", "origin", "main")
        result = pc.flow.sync()
        self.assert_result(result, changed=True, restart=True)
        self.assertIsNotNone(result["backup"], result)
        self.assertEqual(Path(result["backup"], "outside/tools/config.py").read_bytes(), b"LOCAL = True\r\n")
        self.assertEqual(Path(pc.path, "tools/config.py").read_bytes(), b"VALUE = 1\n")
        self.assert_main()

    def test_main_ref_failure_restores_index_branch_and_answers_then_retries(self):
        pc = self.pc
        git(pc.path, "switch", "-qc", "study/alice")
        rel = "submissions/alice/answer.py"
        deleted = "submissions/alice/deleted.py"
        self.write_bytes(pc, rel, b"answer = 1\n")
        self.write_bytes(pc, deleted, b"answer = 0\n")
        git(pc.path, "add", "--", rel, deleted)
        git(pc.path, "commit", "-qm", "기존 로컬 풀이")
        self.write_bytes(pc, rel, b"answer = 2\n")
        git(pc.path, "add", "--", rel)
        Path(pc.path, deleted).unlink()
        self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 3\r\n")
        before, answers = self.checkout_state(pc.path), pc.read()
        self.server.add_files({"study.py": "VERSION = 2\n"}, "프로그램 갱신")
        real_git = pc.flow._git
        failed = []

        def reject_main_ref(*args, **kwargs):
            if args[0] == "update-ref" and "refs/heads/main" in args:
                failed.append(args)
                run = gitflow.Run(" ".join(args), 128, "", "fatal: cannot lock ref 'refs/heads/main'")
                if kwargs.get("check", True):
                    raise gitflow.GitError(run)
                return run
            return real_git(*args, **kwargs)

        with mock.patch.object(pc.flow, "_git", side_effect=reject_main_ref):
            result = pc.flow.sync()
        self.assertEqual(len(failed), 1)
        self.assertIn(result["status"], ("blocked", "error"), result)
        self.assertEqual(pc.read(), answers)
        after = self.checkout_state(pc.path)
        for key in ("index", "branch", "refs", "upstream"):
            with self.subTest(preserved=key):
                self.assertEqual(after[key], before[key])
        self.assert_result(pc.flow.sync(), changed=True, restart=True)
        self.assert_main()
        self.assertEqual(pc.read(), answers)
        self.assertEqual(Path(pc.path, "study.py").read_bytes(), b"VERSION = 2\n")
        self.assertEqual(git(pc.path, "rev-parse", "study/alice").stdout.strip(),
                         next(line.split()[1] for line in before["refs"].splitlines()
                              if line.startswith("refs/heads/study/alice ")))

    def test_first_migration_keeps_the_study_pointer_and_commits(self):
        pc = self.pc
        git(pc.path, "switch", "-qc", "study/alice")
        rel = "submissions/alice/committed.py"
        self.write_bytes(pc, rel, b"answer = 1\n")
        git(pc.path, "add", "--", rel)
        git(pc.path, "commit", "-qm", "기존 로컬 풀이")
        old = git(pc.path, "rev-parse", "study/alice").stdout.strip()
        history = git(pc.path, "rev-list", "study/alice").stdout
        commit = git(pc.path, "cat-file", "-p", old).stdout
        self.write_bytes(pc, rel, b"answer = 2\r\n")
        self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 3\r\n")
        before = pc.read()
        self.server.add_problems("s03")
        result = pc.flow.sync()
        self.assertEqual(git(pc.path, "rev-parse", "study/alice").stdout.strip(), old)
        self.assertEqual(git(pc.path, "rev-list", "study/alice").stdout, history)
        self.assertEqual(git(pc.path, "cat-file", "-p", old).stdout, commit)
        self.assertEqual(pc.read(), before)
        self.assert_result(result, changed=True, restart=True)
        self.assert_main()
        self.assert_result(pc.flow.sync())
        self.assertEqual(git(pc.path, "rev-parse", "study/alice").stdout.strip(), old)

    def test_local_main_commit_blocks_before_files_or_branches_change(self):
        self.server.add_problems("s03")
        for branch in ("main", "study/alice"):
            with self.subTest(branch=branch):
                pc = self.pc if branch == "main" else self.new_pc("local-main")
                self.write_bytes(pc, "submissions/alice/local.py", b"answer = 1\n")
                git(pc.path, "add", "--", "submissions/alice/local.py")
                git(pc.path, "commit", "-qm", "main의 별도 풀이 커밋")
                if branch != "main":
                    git(pc.path, "switch", "-qc", branch)
                self.write_bytes(pc, "gui/app.py", b"LOCAL = True\n")
                git(pc.path, "add", "gui/app.py")
                self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 2\r\n")
                before = self.checkout_state(pc.path)
                result = pc.flow.sync()
                self.assertEqual(self.checkout_state(pc.path), before)
                self.assert_result(result, status="blocked")

    def test_main_in_another_worktree_blocks_before_any_checkout_changes(self):
        pc = self.pc
        git(pc.path, "switch", "-qc", "study/alice")
        other = Path(self.tmp, "other-main")
        git(pc.path, "worktree", "add", "-q", str(other), "main")
        Path(other, "study.py").write_bytes(b"OTHER = True\n")
        self.write_bytes(pc, "gui/app.py", b"LOCAL = True\n")
        self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 2\r\n")
        self.server.add_problems("s03")
        before, other_before = self.checkout_state(pc.path), self.checkout_state(other)
        result = pc.flow.sync()
        self.assertEqual(self.checkout_state(pc.path), before)
        self.assertEqual(self.checkout_state(other), other_before)
        self.assert_result(result, status="blocked")

    def test_worktree_listing_fallback_updates_main_and_protects_other_checkout(self):
        pc = self.pc
        real_git = pc.flow._git

        def older_listing(*args, **kwargs):
            if args[:4] == ("worktree", "list", "--porcelain", "-z"):
                return gitflow.Run(" ".join(args), 129, "", "unknown option: z")
            return real_git(*args, **kwargs)

        self.server.add_problems("s03")
        with mock.patch.object(pc.flow, "_git", side_effect=older_listing):
            self.assert_result(pc.flow.sync(), changed=True, restart=True)
            self.assert_main()
            git(pc.path, "switch", "-qc", "study/alice")
            other = Path(self.tmp, "다른 main 폴더")
            git(pc.path, "worktree", "add", "-q", str(other), "main")
            before = self.checkout_state(pc.path)
            self.assert_result(pc.flow.sync(), status="blocked")
            self.assertEqual(self.checkout_state(pc.path), before)

    def test_interrupted_answer_merge_is_saved_aborted_and_updated(self):
        pc = self.pc
        rel = "submissions/alice/answer.py"
        self.server.add_files({rel: "answer = 1\n"}, "기존 풀이")
        self.assert_result(pc.flow.sync(), changed=False)
        # 첫 수신에서 개인 폴더를 쓰지 않으므로 직접 기존 공개 답안을 준비함.
        git(pc.path, "checkout", "HEAD", "--", rel)
        git(pc.path, "switch", "-qc", "study/alice")
        self.write_bytes(pc, rel, b"answer = 2\n")
        git(pc.path, "commit", "-qam", "개인 풀이")
        mine = pc.read()
        self.server.add_files({rel: "answer = 3\n", "study.py": "VERSION = 3\n"}, "프로그램 갱신")
        git(pc.path, "fetch", "-q", "origin")
        self.assertNotEqual(git(pc.path, "merge", "origin/main", check=False).returncode, 0)
        conflict = Path(pc.path, rel).read_bytes()
        result = pc.flow.sync()
        self.assert_result(result, changed=True, restart=True)
        self.assertEqual(pc.read(), mine)
        self.assertEqual(Path(result["backup"], "stalled", "answer.py").read_bytes(), conflict)
        self.assertFalse(Path(pc.gitdir("MERGE_HEAD")).exists())
        self.assert_main()

    def test_development_feature_branch_keeps_commits_index_and_files(self):
        pc = self.pc
        git(pc.path, "switch", "-qc", "feature/gui")
        self.write_bytes(pc, "study.py", b"FEATURE = True\n")
        git(pc.path, "commit", "-qam", "개발 중인 실행 코드")
        self.write_bytes(pc, "gui/app.py", b"STAGED = True\n")
        git(pc.path, "add", "gui/app.py")
        self.write_bytes(pc, "gui/app.py", b"UNSTAGED = True\n")
        self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 2\r\n")
        self.server.add_problems("s03")
        before = self.checkout_state(pc.path)
        result = pc.flow.sync()
        self.assertEqual(self.checkout_state(pc.path), before)
        self.assert_result(result, status="blocked")

    def test_offline_retries_preserve_state_and_reconnection_updates_once(self):
        pc = self.pc
        self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 3\r\n")
        pc.offline()
        before, answers = self.checkout_state(pc.path), pc.read()
        for attempt in range(2):
            with self.subTest(offline_attempt=attempt):
                self.assert_result(pc.flow.sync(), status="offline")
                self.assertEqual(self.checkout_state(pc.path), before)
        self.server.add_problems("s03")
        pc.offline(False)
        self.assert_result(pc.flow.sync(), changed=True, restart=True)
        self.assert_main()
        self.assertEqual(pc.read(), answers)
        self.assert_result(pc.flow.sync())

    def test_failed_index_update_can_retry_the_same_remote_without_losing_answers(self):
        pc = self.pc
        self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 4\r\n")
        answers = pc.read()
        self.server.add_problems("s03")
        lock = Path(pc.gitdir("index.lock"))
        lock.write_bytes(b"locked\n")
        try:
            for attempt in range(2):
                with self.subTest(locked_attempt=attempt):
                    result = pc.flow.sync()
                    self.assertIn(result["status"], ("blocked", "error"), result)
                    self.assertFalse(result["changed"], result)
                    self.assertFalse(result["restart"], result)
                    self.assertEqual(pc.read(), answers)
        finally:
            lock.unlink()
        self.assertEqual(git(pc.path, "rev-parse", "origin/main").stdout.strip(), self.server.rev("main"))
        self.assert_result(pc.flow.sync(), changed=True, restart=True)
        self.assert_main()
        self.assertEqual(pc.read(), answers)
        self.assertEqual(Path(pc.path, "problems/s03/quiz.md").read_bytes(), b"# s03\n")
        self.assert_result(pc.flow.sync())

    def test_unchanged_remote_repairs_program_files_and_then_needs_no_restart(self):
        pc = self.pc
        original = Path(pc.path, "study.py").read_bytes()
        original_gui = Path(pc.path, "gui/app.py").read_bytes()
        remote = git(pc.path, "rev-parse", "origin/main").stdout
        self.write_bytes(pc, "study.py", b"BROKEN = True\n")
        Path(pc.path, "gui/app.py").unlink()
        self.write_bytes(pc, "submissions/alice/draft.py", b"answer = 5\r\n")
        answers = pc.read()
        self.assert_result(pc.flow.sync(), changed=True, restart=True)
        self.assertEqual(Path(pc.path, "study.py").read_bytes(), original)
        self.assertEqual(Path(pc.path, "gui/app.py").read_bytes(), original_gui)
        self.assertEqual(pc.read(), answers)
        self.assertEqual(git(pc.path, "rev-parse", "origin/main").stdout, remote)
        self.assert_main()
        self.assert_result(pc.flow.sync())


if __name__ == "__main__":
    unittest.main()
