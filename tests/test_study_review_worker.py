# -*- coding: utf-8 -*-
"""외부 게시·모델 실행 없이 검토 판정과 게시 복구를 검사함."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import study_review_worker as worker


HEAD, BASE = "a" * 40, "b" * 40
FILE = "experiments/michae18/train.py"
DIFF = "diff --git a/{0} b/{0}\n--- a/{0}\n+++ b/{0}\n@@ -0,0 +1 @@\n+loss.backward()\n".format(FILE)


def assessment(decision="approve", blocking=False):
    result = {"decision": decision, "summary": "변경한 입력 처리를 확인했음.", "findings": [], "questions": []}
    if blocking:
        result["findings"] = [{"path": FILE, "line": 1, "quote": "loss.backward()", "blocking": True,
                               "condition": "학습을 두 번 반복할 때", "actual": "이전 기울기를 더함.",
                               "expected": "현재 배치의 기울기만 사용함.", "reason": "초기화가 빠졌음.",
                               "hint": "반복 시작에서 기울기를 초기화함.", "check": "두 배치의 기울기를 따로 비교함."}]
    return result


class WorkerTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="study-worker-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pr = {"number": 12, "state": "open", "draft": False, "user": {"login": "michae18"},
                   "head": {"sha": HEAD, "ref": "models/lstm"}, "base": {"sha": BASE, "ref": "main"},
                   "title": "feat(model): 입력 확인", "body": "작은 합성 입력을 확인했음.",
                   "html_url": "https://github.com/example/pull/12"}
        self.current = copy.deepcopy(self.pr)
        self.reviews, self.issues, self.inline, self.writes = [], [], [], []
        self.result = assessment()
        self.packet_changes = {}
        self.api_mock = self.patch(worker, "api", side_effect=self.api)
        self.pages_mock = self.patch(worker, "pages", side_effect=self.pages)
        self.prepare_mock = self.patch(worker.review, "prepare", side_effect=self.prepare)
        self.patch(worker.review, "snapshot", side_effect=self.snapshot)
        self.native_review = worker.review.review
        self.model_mock = self.patch(worker.review, "review", side_effect=self.model)
        self.commands = self.patch(worker.review, "run", side_effect=AssertionError("external command"))
        self.patch(subprocess, "run", side_effect=AssertionError("external process"))

    def patch(self, obj, name, **kwargs):
        patcher = mock.patch.object(obj, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def pages(self, path):
        return copy.deepcopy({"pulls/12/reviews": self.reviews, "issues/12/comments": self.issues,
                              "pulls/12/comments": self.inline, "pulls?state=open&base=main": [self.pr]}[path])

    def api(self, path, data=None, method=None):
        if data is not None:
            self.writes.append((path, copy.deepcopy(data), method))
        if path.startswith("statuses/"):
            return {}
        if path == "pulls/12":
            return copy.deepcopy(self.current)
        if path == "pulls/12/reviews" and data:
            row = {"id": 100 + len(self.reviews), "user": {"login": "WaterMinCho"}, "body": data["body"],
                   "commit_id": data["commit_id"], "html_url": "https://github.com/example/review/100",
                   "state": {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED", "COMMENT": "COMMENTED"}[data["event"]]}
            self.reviews.append(row)
            return copy.deepcopy(row)
        if path.endswith("/dismissals"):
            self.reviews[-1]["state"] = "DISMISSED"
            return {}
        if path.startswith("pulls/12/reviews/"):
            return copy.deepcopy(next(row for row in self.reviews if row["id"] == int(path.rsplit("/", 1)[1])))
        raise AssertionError(path)

    def prepare(self, number, folder, discussion):
        folder.mkdir(parents=True)
        data = {"number": number, "head": HEAD, "base": BASE, "title": self.pr["title"],
                "description": self.pr["body"], "files": [FILE], "diff": DIFF, "context": [],
                "discussion": discussion, **self.packet_changes}
        worker.save(folder/"snapshot.json", data)
        return data

    def snapshot(self, folder):
        return folder, json.loads((folder/"snapshot.json").read_text())

    def model(self, folder, **kwargs):
        self.assertEqual(worker.SCHEMA, kwargs["schema"])
        worker.save(folder/"assessment.json", self.result)
        worker.save(folder/"review.json", {"head": HEAD})
        (folder/"feedback.md").write_text("검토를 마쳤음.\n", encoding="utf-8")

    def process(self):
        return worker.process(self.pr, self.root)

    def posted(self):
        return [data for path, data, _ in self.writes if path == "pulls/12/reviews"]

    def states(self):
        return [data["state"] for path, data, _ in self.writes if path.startswith("statuses/")]

    def folder(self):
        return next((self.root/"12").iterdir())

    def prior(self, state="APPROVED", identity=1):
        row = {"id": identity, "user": {"login": "WaterMinCho"}, "commit_id": HEAD, "state": state,
               "body": "<!-- study-review:12:previous -->\n입력 분리를 확인했음.",
               "submitted_at": "2026-11-12T01:00:00Z"}
        self.reviews.append(row)
        return row

    def author_comment(self):
        self.issues.append({"id": 20, "user": {"login": "michae18"}, "body": "두 번째 입력도 확인했음.",
                            "created_at": "2026-11-12T02:00:00Z", "updated_at": "2026-11-12T02:00:00Z"})

    def lose_status_ack(self):
        original = self.api
        def api(path, data=None, method=None):
            if path.startswith("statuses/") and data["state"] == "success":
                raise worker.review.ReviewError("response lost")
            return original(path, data, method)
        self.api_mock.side_effect = api
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.api_mock.side_effect = original

    def test_three_members_and_excluded_pull_requests(self):
        for author in worker.AUTHORS:
            self.assertTrue(worker.eligible(dict(self.pr, user={"login": author.upper()})))
        for change in ({"user": {"login": "stranger"}}, {"draft": True}, {"state": "closed"},
                       {"base": {"sha": BASE, "ref": "dev"}}, {"head": {"sha": HEAD, "ref": "study/michae18"}}):
            with self.subTest(change=change):
                self.assertEqual("제외", worker.process(dict(self.pr, **change), self.root))
        self.pages_mock.assert_not_called()
        self.model_mock.assert_not_called()

    def test_approval_readback_is_idempotent_and_never_merges(self):
        self.assertEqual("리뷰 게시함", self.process())
        self.assertEqual("이미 검토함", self.process())
        self.assertEqual(["APPROVE"], [row["event"] for row in self.posted()])
        self.assertEqual(["pending", "success"], self.states())
        self.model_mock.assert_called_once()
        self.commands.assert_not_called()
        self.assertTrue(json.loads((self.folder()/"worker.json").read_text())["passed"])
        self.assertFalse(any("merge" in path for path, _, _ in self.writes))

    def test_scope_title_images_and_context_only_leave_comment(self):
        data = {"files": [FILE], "diff": DIFF, "title": self.pr["title"]}
        for update in ({"files": ["gui/view.py"]}, {"files": ["experiments/michae18/setup.py"]},
                       {"unreviewed_images": ["chart.png"]}, {"title": "wrong title"}, {"diff": "x" * 60001}):
            with self.subTest(update=update):
                self.assertEqual("COMMENT", worker.validate(dict(data, **update), assessment(), "michae18"))
        self.assertEqual("COMMENT", worker.validate(data, assessment("needs_context"), "michae18"))
        self.assertEqual("COMMENT", worker.validate(data, assessment("changes_requested"), "michae18"))

    def test_grounded_blocker_overrides_approve_on_same_head(self):
        self.prior()
        self.author_comment()
        self.result = assessment(blocking=True)
        self.process()
        self.assertEqual("REQUEST_CHANGES", self.posted()[0]["event"])
        self.assertEqual("failure", self.states()[-1])

    def test_comment_uses_latest_terminal_review_not_latest_comment(self):
        self.prior()
        self.prior("COMMENTED", 2)
        self.author_comment()
        self.process()
        self.assertEqual("COMMENT", self.posted()[0]["event"])
        self.assertEqual("success", self.states()[-1])

    def test_comment_does_not_override_changes_request_or_missing_context(self):
        self.prior()
        self.prior("CHANGES_REQUESTED", 2)
        self.author_comment()
        self.process()
        self.assertEqual("COMMENT", self.posted()[0]["event"])
        self.assertEqual("failure", self.states()[-1])

    def test_needs_context_comment_does_not_keep_approval_status(self):
        self.prior()
        self.author_comment()
        self.result = assessment("needs_context")
        self.process()
        self.assertEqual("failure", self.states()[-1])

    def test_malformed_or_ungrounded_findings_are_rejected(self):
        data = {"files": [FILE], "diff": DIFF, "title": self.pr["title"]}
        for update in ({"path": "other.py"}, {"line": 2}, {"line": True}, {"quote": "not in diff"}, {"blocking": "yes"}):
            value = assessment(blocking=True)
            value["findings"][0].update(update)
            with self.subTest(update=update), self.assertRaises(worker.review.ReviewError):
                worker.validate(data, value, "michae18")
        value["findings"] = [None]
        with self.assertRaises(worker.review.ReviewError):
            worker.validate(data, value, "michae18")

    def test_diff_metadata_and_added_header_like_text_keep_correct_lines(self):
        diff = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -0,0 +1,2 @@\n+++ b/pretend.py\n+value\n"
        diff += "diff --git a/b.bin b/b.bin\nBinary files differ\n"
        self.assertEqual({("a.txt", 1): "++ b/pretend.py", ("a.txt", 2): "value"}, worker.lines_in_diff(diff))

    def test_prepare_race_stops_before_model(self):
        self.packet_changes["base"] = "c" * 40
        self.assertEqual("새 판 대기", self.process())
        self.model_mock.assert_not_called()
        self.assertEqual([], self.posted())

    def test_pre_publish_rechecks_head_base_target_and_description(self):
        for change in ({"head": {"sha": "c" * 40, "ref": "models/lstm"}}, {"base": {"sha": "c" * 40, "ref": "main"}},
                       {"base": {"sha": BASE, "ref": "dev"}}, {"draft": True}, {"body": "다른 설명임."},
                       {"title": "docs(model): 제목 수정"}, {"state": "closed"}):
            with self.subTest(change=change):
                self.current = dict(copy.deepcopy(self.pr), **change)
                self.assertEqual("새 판 대기", self.process())
                self.assertEqual([], self.posted())
                for path in self.folder().iterdir():
                    path.unlink()
                self.folder().rmdir()

    def test_post_publish_base_change_dismisses_review(self):
        original = self.api
        def api(path, data=None, method=None):
            result = original(path, data, method)
            if path == "pulls/12/reviews" and data:
                self.current["base"]["sha"] = "c" * 40
            return result
        self.api_mock.side_effect = api
        self.assertEqual("새 판 대기", self.process())
        self.assertEqual("DISMISSED", self.reviews[-1]["state"])
        self.assertNotIn("success", self.states())
        self.assertEqual("superseded", json.loads((self.folder()/"worker.json").read_text())["phase"])
        self.pr = copy.deepcopy(self.current)
        self.packet_changes["base"] = self.pr["base"]["sha"]
        self.api_mock.side_effect = original
        self.assertEqual("리뷰 게시함", self.process())
        self.assertEqual(2, len(self.posted()))

    def test_comment_recovery_preserves_success_after_status_ack_loss(self):
        self.prior()
        self.author_comment()
        self.lose_status_ack()
        self.assertEqual("이미 검토함", self.process())
        self.assertEqual("success", self.states()[-1])
        self.assertEqual(1, len(self.posted()))

    def test_legacy_comment_recovery_recomputes_status(self):
        self.prior()
        self.author_comment()
        self.lose_status_ack()
        folder = self.folder()
        ready = json.loads((folder/"publish-ready.json").read_text())
        del ready["passed"]
        worker.save(folder/"publish-ready.json", ready)
        worker.save(folder/"worker.json", {"phase": "posting"})
        self.process()
        self.assertEqual("success", self.states()[-1])
        self.assertEqual(1, len(self.posted()))

    def test_legacy_comment_recovery_with_new_discussion_preserves_status(self):
        self.prior()
        self.author_comment()
        self.lose_status_ack()
        previous = self.folder()
        ready = json.loads((previous/"publish-ready.json").read_text())
        del ready["passed"]
        worker.save(previous/"publish-ready.json", ready)
        self.issues[0]["body"] = "다른 입력도 확인했음."
        self.process()
        self.assertTrue(json.loads((previous/"worker.json").read_text())["passed"])

    def test_duplicate_marker_is_not_reposted(self):
        self.process()
        duplicate = dict(self.reviews[-1], id=200)
        self.reviews.append(duplicate)
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.assertEqual(1, len(self.posted()))

    def test_post_ack_loss_recovers_existing_review_without_second_write(self):
        original = self.api
        def api(path, data=None, method=None):
            result = original(path, data, method)
            if path == "pulls/12/reviews" and data:
                raise worker.review.ReviewError("response lost")
            return result
        self.api_mock.side_effect = api
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.api_mock.side_effect = original
        self.assertEqual("이미 검토함", self.process())
        self.assertEqual(1, len(self.posted()))

    def test_unknown_ack_blocks_new_discussion_too(self):
        original = self.api
        def api(path, data=None, method=None):
            if path == "pulls/12/reviews" and data:
                raise worker.review.ReviewError("unknown acknowledgement")
            return original(path, data, method)
        self.api_mock.side_effect = api
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.api_mock.side_effect = original
        self.assertEqual("게시 확인 대기", self.process())
        self.author_comment()
        self.assertEqual("게시 확인 대기", self.process())
        self.assertEqual([], self.posted())
        self.model_mock.assert_called_once()

    def test_readback_mismatch_never_marks_success_or_reposts(self):
        original = self.api
        for index, update in enumerate(({"body": "changed"}, {"state": "COMMENTED"}, {"commit_id": BASE},
                                        {"user": {"login": "other"}}, {"id": 999})):
            with self.subTest(update=update):
                self.root = self.root/str(index)
                self.root.mkdir()
                self.reviews, self.writes = [], []
                def api(path, data=None, method=None):
                    result = original(path, data, method)
                    if path.startswith("pulls/12/reviews/") and not data:
                        return dict(result, **update)
                    return result
                self.api_mock.side_effect = api
                with self.assertRaises(worker.review.ReviewError):
                    self.process()
                self.assertNotIn("success", self.states())
                self.api_mock.side_effect = original
                self.assertEqual("이미 검토함", self.process())
                self.assertEqual(1, len(self.posted()))

    def test_recovery_rechecks_base_before_restoring_success(self):
        self.lose_status_ack()
        self.current["base"]["sha"] = "c" * 40
        self.assertEqual("새 판 대기", self.process())
        self.assertEqual("DISMISSED", self.reviews[-1]["state"])
        self.assertNotIn("success", self.states())

    def test_prior_pending_review_is_dismissed_when_new_version_arrives(self):
        self.lose_status_ack()
        previous = self.folder()
        self.pr["base"]["sha"] = "c" * 40
        self.current = copy.deepcopy(self.pr)
        self.packet_changes["base"] = self.pr["base"]["sha"]
        self.assertEqual("리뷰 게시함", self.process())
        self.assertEqual("DISMISSED", self.reviews[0]["state"])
        self.assertEqual("superseded", json.loads((previous/"worker.json").read_text())["phase"])
        self.assertEqual(2, len(self.posted()))

    def test_inline_reply_includes_original_review_location_and_parent(self):
        self.prior("CHANGES_REQUESTED")
        self.inline = [{"id": 10, "user": {"login": "WaterMinCho"}, "body": "현재 입력과 정답을 분리했는지 확인함.",
                        "path": FILE, "line": 1, "commit_id": HEAD, "pull_request_review_id": 1},
                       {"id": 11, "user": {"login": "michae18"}, "body": "이전 입력만 사용했음.", "in_reply_to_id": 10,
                        "updated_at": "2026-11-12T02:00:00Z", "path": FILE, "line": 1}]
        self.process()
        discussion = self.prepare_mock.call_args.kwargs["discussion"]
        self.assertEqual({("inline", 10), ("inline", 11), ("review", 1)}, {(row["kind"], row["id"]) for row in discussion})
        self.assertEqual(FILE, discussion[0]["path"])
        self.assertEqual("이미 검토함", self.process())
        self.model_mock.assert_called_once()

    def test_missing_inline_parent_blocks_review(self):
        self.inline = [{"id": 11, "user": {"login": "michae18"}, "body": "확인했음.", "in_reply_to_id": 999}]
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.model_mock.assert_not_called()

    def test_sensitive_diff_context_and_reply_are_not_sent_to_model(self):
        for update in ({"diff": DIFF + "\n+token='ghp_" + "x" * 30 + "'"},
                       {"context": [{"path": "example.py", "content": "sk-" + "x" * 40}]},
                       {"discussion": [{"body": '{"participant":"11111111-1111-4111-8111-111111111111"}'}]},
                       {"context": [{"participant": "11111111-1111-4111-8111-111111111111"}]}):
            with self.subTest(update=update):
                data = {"diff": DIFF, "context": [], "discussion": [], **update}
                with self.assertRaises(worker.review.ReviewError):
                    worker.check_packet(data)
        self.packet_changes["diff"] = DIFF + "\n+token='ghp_" + "x" * 30 + "'"
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.model_mock.assert_not_called()

    def test_cached_discussion_is_checked_before_model(self):
        self.author_comment()
        self.result = assessment("needs_context")
        self.current["base"]["sha"] = "c" * 40
        self.assertEqual("새 판 대기", self.process())
        folder = self.folder()
        data = json.loads((folder/"snapshot.json").read_text())
        data["context"] = [{"path": "example.py", "content": "ghp_" + "x" * 30}]
        worker.save(folder/"snapshot.json", data)
        self.model_mock.reset_mock()
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.model_mock.assert_not_called()

    def test_failed_review_cannot_reuse_partial_assessment(self):
        def fail(folder, **kwargs):
            worker.save(folder/"assessment.json", assessment())
            raise worker.review.ReviewError("quota")
        self.model_mock.side_effect = fail
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.assertEqual("대기", self.process())
        with mock.patch.object(worker.time, "time", return_value=10**12), self.assertRaises(worker.review.ReviewError):
            self.process()
        self.model_mock.assert_called_once()
        self.assertEqual([], self.posted())
        self.commands.assert_not_called()

    @unittest.skipIf(os.name == "nt", "POSIX lock")
    def test_once_lock_prevents_concurrent_api_or_model_work(self):
        import fcntl
        with (self.root/"worker.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(["이미 실행 중"], worker.once(self.root))
        self.pages_mock.assert_not_called()
        self.model_mock.assert_not_called()

    @unittest.skipIf(os.name == "nt", "Mac worker")
    def test_once_reports_quota_as_tool_error_not_code_feedback(self):
        self.model_mock.side_effect = worker.review.ReviewError("quota")
        self.assertEqual([(12, "검토 보류")], worker.once(self.root))
        self.assertEqual("error", self.states()[-1])
        self.assertEqual([], self.posted())

    def test_subscription_runner_is_isolated_and_only_mocked(self):
        self.model_mock.side_effect = self.native_review
        initial = {"type": "system", "subtype": "init", "model": "test-model", "apiKeySource": "none",
                   "tools": ["StructuredOutput"], "mcp_servers": [], "slash_commands": [], "skills": []}
        result = {"type": "result", "structured_output": self.result, "modelUsage": {"test-model": {}}}
        internal = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "StructuredOutput", "input": self.result}]}}
        self.commands.side_effect = ["test-version", json.dumps({"loggedIn": True, "authMethod": "claude.ai"}),
                                     "\n".join(map(json.dumps, (initial, internal, result)))]
        with mock.patch.object(worker.review.shutil, "which", return_value="mock-subscription-cli"), \
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "not-used", "CLAUDE_CODE_USE_BEDROCK": "1"}):
            self.process()
        command = self.commands.call_args_list[-1].args[0]
        self.assertEqual("", command[command.index("--tools")+1])
        for flag in ("--safe-mode", "--strict-mcp-config", "--no-session-persistence", "--json-schema"):
            self.assertIn(flag, command)
        self.assertNotIn("ANTHROPIC_API_KEY", self.commands.call_args.kwargs["env"])
        self.assertEqual("APPROVE", self.posted()[0]["event"])

    def test_unexpected_tool_call_blocks_worker_publication(self):
        self.model_mock.side_effect = self.native_review
        initial = {"type": "system", "subtype": "init", "model": "test-model", "apiKeySource": "none",
                   "tools": ["StructuredOutput"], "mcp_servers": [], "slash_commands": [], "skills": []}
        unexpected = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}
        result = {"type": "result", "structured_output": self.result}
        self.commands.side_effect = ["test-version", json.dumps({"loggedIn": True, "authMethod": "claude.ai"}),
                                     "\n".join(map(json.dumps, (initial, unexpected, result)))]
        with mock.patch.object(worker.review.shutil, "which", return_value="mock-subscription-cli"):
            with self.assertRaises(worker.review.ReviewError):
                self.process()
        self.assertEqual([], self.posted())

    def test_subscription_quota_never_uses_api_fallback_or_publishes(self):
        self.model_mock.side_effect = self.native_review
        initial = {"type": "system", "subtype": "init", "model": "test-model", "apiKeySource": "none",
                   "tools": [], "mcp_servers": [], "slash_commands": [], "skills": []}
        result = {"type": "result", "is_error": True, "result": "quota"}
        self.commands.side_effect = ["test-version", json.dumps({"loggedIn": True, "authMethod": "claude.ai"}),
                                     json.dumps(initial) + "\n" + json.dumps(result)]
        with mock.patch.object(worker.review.shutil, "which", return_value="mock-subscription-cli"):
            with self.assertRaises(worker.review.ReviewError):
                self.process()
        self.assertEqual(3, self.commands.call_count)
        self.assertEqual([], self.posted())
        self.assertFalse((self.folder()/"assessment.json").exists())

    def test_api_auth_stops_before_model_request(self):
        self.model_mock.side_effect = self.native_review
        self.commands.side_effect = ["test-version", json.dumps({"loggedIn": True, "authMethod": "api_key"})]
        with mock.patch.object(worker.review.shutil, "which", return_value="mock-subscription-cli"):
            with self.assertRaises(worker.review.ReviewError):
                self.process()
        self.assertEqual(2, self.commands.call_count)
        self.assertEqual([], self.posted())


if __name__ == "__main__":
    unittest.main()
