# -*- coding: utf-8 -*-
"""검토 자료의 노출·유료 전환·오래된 판 게시·중복 게시 경계를 검사함."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("learning_review", Path(__file__).parents[1] / "tools/learning_review.py")
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)
HEAD = "a" * 40
AUTH = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})


def response(initial=None, result=None):
    initial = dict({"type": "system", "subtype": "init", "model": "test-model", "apiKeySource": "none",
                    "tools": [], "mcp_servers": [], "slash_commands": [], "skills": []}, **(initial or {}))
    result = dict({"type": "result", "result": "변경분을 검토했음.", "modelUsage": {"test-model": {}}}, **(result or {}))
    return json.dumps(initial) + "\n" + json.dumps(result)


def pull():
    return {"state": "open", "base": {"ref": "main", "sha": "c" * 40}, "head": {"ref": "models/lstm", "sha": HEAD,
            "repo": {"full_name": review.REPO}}, "user": {"login": "michae18"}, "changed_files": 1,
            "title": "feat(model): LSTM 첫 학습", "body": "합성 입력으로 확인했음."}


class ReviewTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="learning_review_")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / "review"
        self.info = pull()

    def prepare(self, diff="+loss.backward()\n", files=None, previous_review=None):
        files = files or [{"filename": "experiments/michae18/train.py"}]
        def api(path):
            if "/compare/" in path:
                return {"merge_base_commit": {"sha": "d" * 40}}
            if "/files?" in path:
                return files
            return {"encoding": "base64", "size": 7, "content": base64.b64encode(b"context").decode()}
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review, "api", side_effect=api), \
                mock.patch.object(review, "run", return_value=diff) as command:
            data = review.prepare(12, self.folder, previous_review=previous_review)
            self.assertEqual(["gh", "api", "repos/%s/compare/%s...%s" % (review.REPO, "c" * 40, HEAD),
                              "-H", "Accept: application/vnd.github.diff"], command.call_args.args[0])
            return data

    def test_prepare_preserves_head_and_readback_without_running_code(self):
        data = self.prepare()
        self.assertEqual(HEAD, data["head"])
        self.assertEqual(list(review.CONTEXT), [c["path"] for c in data["context"]])
        manifest = json.loads((self.folder / "manifest.json").read_text())
        self.assertEqual(manifest["sha256"], hashlib.sha256((self.folder / "snapshot.json").read_bytes()).hexdigest())
        if os.name != "nt":
            self.assertEqual(0o700, self.folder.stat().st_mode & 0o777)
            self.assertEqual(0o600, (self.folder / "snapshot.json").stat().st_mode & 0o777)

    def test_previous_review_is_frozen_and_private_text_is_rejected(self):
        previous = {"id": 10, "head": "b" * 40, "body": "이전 제안", "state": "APPROVED"}
        data = self.prepare(previous_review=previous)
        self.assertEqual(previous, data["previous_review"])
        saved = json.loads((self.folder/"snapshot.json").read_text())
        self.assertEqual(previous, saved["previous_review"])
        self.folder = self.root/"private-previous"
        redacted = self.prepare(previous_review=dict(previous, body="ghp_"+"a" * 30))
        self.assertNotIn("previous_review", redacted)
        self.assertEqual("content_check", redacted["previous_review_skipped"])
        self.assertNotIn("ghp_", (self.folder/"snapshot.json").read_text())
        self.folder = self.root/"large-previous"
        bounded = self.prepare(previous_review=dict(previous, body="x" * review.MAX_BYTES))
        self.assertNotIn("previous_review", bounded)
        self.assertEqual("size_limit", bounded["previous_review_skipped"])

    def test_rename_keeps_both_source_and_destination_in_review_packet(self):
        data = self.prepare(diff="rename from tools/helper.py\nrename to experiments/michae18/helper.py\n",
                            files=[{"filename": "experiments/michae18/helper.py", "previous_filename": "tools/helper.py"}])
        self.assertEqual(["experiments/michae18/helper.py", "tools/helper.py"], data["changed_paths"])

    def test_blocked_path_and_renamed_private_source_stop_before_model(self):
        for name in ("submissions/alice/profile.json", "data/events.jsonl", ".env", "model.pth", "x.ipynb", "../x.py", ""):
            with self.subTest(name=name), self.assertRaises(review.ReviewError):
                review.check_path(name)
        with self.assertRaises(review.ReviewError):
            self.prepare(files=[{"filename": "experiments/michae18/train.py", "previous_filename": "submissions/x/a.py"}])
        self.assertFalse(self.folder.exists())

    def test_private_payload_in_diff_is_checked_before_json_escaping(self):
        identity = "-".join(("11111111", "1111", "4111", "8111", "111111111111"))
        raw = '+{"participant":"%s"}\n' % identity
        with self.assertRaises(review.ReviewError):
            self.prepare(raw)
        self.assertFalse(self.folder.exists())
        with self.assertRaises(review.ReviewError):
            review.check_text("ghp_" + "a" * 30)

    def test_existing_output_repository_and_tampering_are_rejected(self):
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()
        (self.folder / "snapshot.json").write_text("{}")
        with self.assertRaises(review.ReviewError):
            review.snapshot(self.folder)
        git = self.root / "repo"
        (git / ".git").mkdir(parents=True)
        with self.assertRaises(review.ReviewError):
            review.private_folder(git / "review")

    def test_study_pr_and_unknown_author_are_not_reviewed(self):
        for changed in ({"head": dict(self.info["head"], ref="study/michae18")}, {"user": {"login": "stranger"}}):
            with self.subTest(changed=changed), mock.patch.object(review, "api", return_value=dict(self.info, **changed)):
                with self.assertRaises(review.ReviewError):
                    review.pull(12)

    def test_review_uses_subscription_with_no_tools_or_provider_environment(self):
        self.prepare()
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review.shutil, "which", return_value="claude"), \
                mock.patch.object(review, "run", side_effect=["test-version", AUTH, response()]) as run, \
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "not-used", "CLAUDE_CODE_USE_BEDROCK": "1", "UNEXPECTED_PROVIDER": "1"}):
            body = review.review(self.folder)
        command = run.call_args_list[2].args[0]
        self.assertEqual("", command[command.index("--tools") + 1])
        self.assertIn("--strict-mcp-config", command)
        self.assertIn("--no-session-persistence", command)
        self.assertIn("--safe-mode", command)
        self.assertIn("--safe-mode", run.call_args_list[1].args[0])
        self.assertEqual(set(), set(run.call_args_list[2].kwargs["env"]) - set(review.ENVIRONMENT))
        self.assertTrue(body.startswith("검토한 커밋: `%s`" % HEAD))
        self.assertFalse(json.loads((self.folder / "review.json").read_text())["code_executed"])

    def test_api_auth_and_stale_head_do_not_call_model(self):
        self.prepare()
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review.shutil, "which", return_value="claude"), \
                mock.patch.object(review, "run", side_effect=["test-version", json.dumps({"loggedIn": True, "authMethod": "api_key"})]) as run:
            with self.assertRaises(review.ReviewError):
                review.review(self.folder)
            self.assertEqual(2, run.call_count)
        changed = dict(self.info, head=dict(self.info["head"], sha="b" * 40))
        with mock.patch.object(review, "pull", return_value=changed), mock.patch.object(review, "run") as run:
            with self.assertRaises(review.ReviewError):
                review.review(self.folder)
            run.assert_not_called()

    def test_schema_allows_only_the_output_formatter_and_saves_after_current_head_check(self):
        self.prepare()
        assessment = {"decision": "needs_context"}
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review.shutil, "which", return_value="claude"), \
                mock.patch.object(review, "run", side_effect=["test-version", AUTH, response(initial={"tools": ["StructuredOutput"]}, result={"structured_output": assessment})]):
            review.review(self.folder, schema={"type": "object"})
        self.assertEqual(assessment, json.loads((self.folder / "assessment.json").read_text()))

    def test_new_schema_rejects_missing_presentation_version_before_saving(self):
        self.prepare()
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review.shutil, "which", return_value="claude"), \
                mock.patch.object(review, "run", side_effect=["test-version", AUTH, response(result={"structured_output": {}})]):
            with self.assertRaises(review.ReviewError):
                review.review(self.folder, schema={"properties": {"format_version": {"const": 2}}})
        self.assertFalse((self.folder/"assessment.json").exists())
        self.assertFalse((self.folder/"feedback.md").exists())

    def test_schema_stale_head_and_unexpected_execution_tool_leave_no_assessment(self):
        self.prepare()
        changed = dict(self.info, head=dict(self.info["head"], sha="f" * 40))
        with mock.patch.object(review, "pull", side_effect=[self.info, changed]), mock.patch.object(review.shutil, "which", return_value="claude"), \
                mock.patch.object(review, "run", side_effect=["test-version", AUTH, response(initial={"tools": ["StructuredOutput"]}, result={"structured_output": {"decision": "approve"}})]):
            with self.assertRaises(review.ReviewError):
                review.review(self.folder, schema={"type": "object"})
        self.assertFalse((self.folder / "assessment.json").exists())
        payload = response(initial={"tools": ["StructuredOutput"]}, result={"structured_output": {}}) + '\n' + json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}})
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review.shutil, "which", return_value="claude"), \
                mock.patch.object(review, "run", side_effect=["test-version", AUTH, payload]):
            with self.assertRaises(review.ReviewError):
                review.review(self.folder, schema={"type": "object"})
        self.assertFalse((self.folder / "assessment.json").exists())

    def test_base_change_and_model_error_leave_no_publishable_feedback(self):
        self.prepare()
        changed = dict(self.info, base=dict(self.info["base"], sha="e" * 40))
        with mock.patch.object(review, "pull", return_value=changed), mock.patch.object(review, "run") as run:
            with self.assertRaises(review.ReviewError):
                review.review(self.folder)
            run.assert_not_called()
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review.shutil, "which", return_value="claude"), \
                mock.patch.object(review, "run", side_effect=["test-version", AUTH, response(result={"is_error": True, "result": "quota"})]):
            with self.assertRaises(review.ReviewError):
                review.review(self.folder)
        self.assertFalse((self.folder / "feedback.md").exists())
        self.assertFalse((self.folder / "review.json").exists())

    def test_unexpected_initialization_leaves_no_publishable_feedback(self):
        self.prepare()
        for initial in ({"apiKeySource": "api_key"}, {"tools": ["Bash"]}, {"mcp_servers": ["external"]},
                        {"skills": ["injected"]}, {"slash_commands": ["review"]}):
            with self.subTest(initial=initial), mock.patch.object(review, "pull", return_value=self.info), \
                    mock.patch.object(review.shutil, "which", return_value="claude"), \
                    mock.patch.object(review, "run", side_effect=["test-version", AUTH, response(initial)]):
                with self.assertRaises(review.ReviewError):
                    review.review(self.folder)
                self.assertFalse((self.folder / "feedback.md").exists())

    def test_directory_context_is_rejected_without_traceback(self):
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review, "run", return_value="diff"), \
                mock.patch.object(review, "api", side_effect=[[{"filename": "train.py"}], {"merge_base_commit": {"sha": "d" * 40}}, []]):
            with self.assertRaises(review.ReviewError):
                review.prepare(12, self.folder)

    def test_image_is_metadata_only_and_not_a_text_context_file(self):
        data = self.prepare(files=[{"filename": "experiments/michae18/figures/loss.png"}])
        self.assertEqual(["experiments/michae18/figures/loss.png"], data["unreviewed_images"])
        with self.assertRaises(review.ReviewError):
            review.check_path("experiments/michae18/figures/loss.png")

    def test_post_is_explicit_reads_back_and_rejects_duplicates_or_new_head(self):
        self.prepare()
        body = "검토한 커밋: `%s`\n\n작은 입력으로 확인할 질문을 남겼음.\n" % HEAD
        review.write(self.folder / "feedback.md", body)
        review.write(self.folder / "review.json", review.packed({"head": HEAD}))
        saved = {"id": 34, "body": body, "html_url": "https://github.com/example/comment"}
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review, "run", return_value=json.dumps(saved)) as run, \
                mock.patch.object(review, "api", return_value=saved):
            self.assertEqual(saved["html_url"], review.post(self.folder))
            with self.assertRaises(review.ReviewError):
                review.post(self.folder)
            self.assertEqual(1, run.call_count)
        changed = dict(self.info, head=dict(self.info["head"], sha="b" * 40))
        with mock.patch.object(review, "pull", return_value=changed), mock.patch.object(review, "run") as run:
            with self.assertRaises(review.ReviewError):
                review.post(self.folder)
            run.assert_not_called()

    def test_readback_failure_resumes_verification_without_posting_twice(self):
        self.prepare()
        body = "검토한 판: `%s`\n\n확인했음.\n" % HEAD
        review.write(self.folder / "feedback.md", body)
        review.write(self.folder / "review.json", review.packed({"head": HEAD}))
        saved = {"id": 34, "body": body, "html_url": "https://github.com/example/comment"}
        with mock.patch.object(review, "pull", return_value=self.info), mock.patch.object(review, "run", return_value=json.dumps(saved)) as run, \
                mock.patch.object(review, "api", side_effect=[review.ReviewError("읽기 실패"), saved]):
            with self.assertRaises(review.ReviewError):
                review.post(self.folder)
            self.assertEqual(saved["html_url"], review.post(self.folder))
            self.assertEqual(1, run.call_count)

    def test_uncertain_post_result_does_not_retry_network_write(self):
        self.prepare()
        review.write(self.folder / "feedback.md", "검토한 판: `%s`\n\n확인했음.\n" % HEAD)
        review.write(self.folder / "review.json", review.packed({"head": HEAD}))
        with mock.patch.object(review, "pull", return_value=self.info), \
                mock.patch.object(review, "run", side_effect=review.ReviewError("응답 손실")) as run:
            for _ in range(2):
                with self.assertRaises(review.ReviewError):
                    review.post(self.folder)
            self.assertEqual(1, run.call_count)


if __name__ == "__main__":
    unittest.main()
