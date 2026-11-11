import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import zipfile

from tools import slack_notify as notify


SHA = "a" * 40
PR = {
    "number": 123, "title": "모델 입력 확인", "draft": False, "merged": False,
    "created_at": "2026-11-12T00:00:00Z", "user": {"login": "student"},
    "head": {"ref": "model/student-first", "sha": SHA, "repo": {"full_name": "student/programming-study"}},
    "base": {"repo": {"full_name": notify.REPO}},
}


def run(event="pull_request", path=notify.RELAY):
    return {
        "id": 7, "path": path, "event": event, "conclusion": "success",
        "status": "completed", "head_sha": SHA, "head_branch": "model/student-first",
        "created_at": "2026-11-12T00:00:02Z", "actor": {"login": "student"},
        "repository": {"full_name": notify.REPO}, "run_attempt": 1,
        "head_repository": {"full_name": "student/programming-study"},
        "pull_requests": [],
    }


class FakeGitHub:
    def __init__(self, pr=None, data=None, source=None):
        self.pr = copy.deepcopy(pr or PR)
        self.data = data or {"pr": 123, "action": "opened"}
        self.source = source or run()
        self.files = [{"filename": "experiments/student/README.md"}]
        self.review = {"id": 55, "state": "CHANGES_REQUESTED", "user": {"login": "student"},
                       "submitted_at": "2026-11-12T00:00:01Z"}
        self.timeline = []
        self.jobs = [{"name": "문제 은행 검증", "conclusion": "success"},
                     {"name": "채점", "conclusion": "success"},
                     {"name": "화면 테스트", "conclusion": "failure"}]
        self.associated = [self.pr]
        self.zip_name = "notification.json"

    def get(self, path, binary=False):
        tail = path.removeprefix(f"/repos/{notify.REPO}/")
        if tail == "pulls/123":
            return self.pr
        if tail in {"actions/runs/7/attempts/1", "actions/runs/7/attempts/2"}:
            return self.source
        if tail == f"commits/{SHA}/pulls?per_page=100":
            return self.associated
        if tail == "actions/runs/7/artifacts":
            return {"artifacts": [{"id": 8, "name": "study-notification-1", "expired": False,
                                    "size_in_bytes": 200}]}
        if tail == "actions/artifacts/8/zip":
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr(self.zip_name, json.dumps(self.data))
            return output.getvalue()
        if tail == "pulls/123/reviews/55":
            return self.review
        if tail == "pulls/comments/66":
            return {"id": 66, "user": {"login": "student", "type": "User"},
                    "in_reply_to_id": 55, "created_at": PR["created_at"],
                    "pull_request_url": f"https://api.github.com/repos/{notify.REPO}/pulls/123"}
        if tail.startswith("actions/runs/7/attempts/1/jobs?"):
            return {"jobs": self.jobs}
        raise AssertionError(path)

    def pages(self, path):
        if path.endswith("/files"):
            return iter(self.files)
        if path.endswith("/timeline"):
            return iter(self.timeline)
        raise AssertionError(path)


def event(source):
    return {"repository": {"full_name": notify.REPO}, "action": "completed",
            "workflow_run": {"id": source["id"], "run_attempt": source["run_attempt"]}}


class NotificationTest(unittest.TestCase):
    def test_fork_pr_without_pull_requests_uses_commit_association(self):
        source = run()
        payload = notify.notification("workflow_run", event(source), FakeGitHub(source=source))
        self.assertIn("새 PR", payload["text"])
        self.assertIn("PR 보기", json.dumps(payload, ensure_ascii=False))

    def test_study_branch_and_submission_only_pr_are_excluded(self):
        github = FakeGitHub()
        github.pr["head"]["ref"] = "study/student"
        self.assertIsNone(notify.relay_card(run(), github))
        github.pr["head"]["ref"] = "model/student"
        github.files = [{"filename": "submissions/student/answer.py"}]
        self.assertIsNone(notify.relay_card(run(), github))

    def test_forged_pr_and_path_traversal_are_rejected(self):
        github = FakeGitHub()
        github.associated = []
        self.assertIsNone(notify.relay_card(run(), github))
        github.zip_name = "../notification.json"
        with self.assertRaises(ValueError):
            notify.metadata(run(), github)

    def test_old_lifecycle_and_forged_actor_are_excluded(self):
        github = FakeGitHub()
        github.pr["created_at"] = "2026-11-01T00:00:00Z"
        self.assertIsNone(notify.relay_card(run(), github))
        github.pr["created_at"] = PR["created_at"]
        source = run()
        source["actor"]["login"] = "another"
        self.assertIsNone(notify.relay_card(source, github))

    def test_closed_event_needs_matching_timeline_and_reports_merge(self):
        github = FakeGitHub(data={"pr": 123, "action": "closed"})
        self.assertIsNone(notify.relay_card(run(), github))
        github.pr["merged"] = True
        github.timeline = [{"event": "closed", "created_at": PR["created_at"],
                            "actor": {"login": "student"}}]
        self.assertIn("머지", notify.relay_card(run(), github)["text"])

    def test_closed_unmerged_fork_checks_source_head_without_association(self):
        github = FakeGitHub(data={"pr": 123, "action": "closed"})
        github.associated = []
        github.timeline = [{"event": "closed", "created_at": PR["created_at"],
                            "actor": {"login": "student"}}]
        self.assertIn("머지 없이", notify.relay_card(run(), github)["text"])
        source = run()
        source["head_repository"]["full_name"] = "another/programming-study"
        self.assertIsNone(notify.relay_card(source, github))

    def test_review_uses_authoritative_id_author_and_time(self):
        source = run(event="pull_request_review")
        github = FakeGitHub(data={"pr": 123, "action": "submitted", "review": 55})
        payload = notify.relay_card(source, github)
        self.assertIn("수정 요청", json.dumps(payload, ensure_ascii=False))
        github.review["user"]["login"] = "another"
        self.assertIsNone(notify.relay_card(source, github))
        github.review["user"]["login"] = "student"
        github.review["submitted_at"] = "2026-11-01T00:00:00Z"
        self.assertIsNone(notify.relay_card(source, github))

    def test_review_bots_are_excluded(self):
        github = FakeGitHub(data={"pr": 123, "action": "submitted", "review": 55})
        github.review["user"]["type"] = "Bot"
        self.assertIsNone(notify.relay_card(run(event="pull_request_review"), github))

    def test_review_thread_reply_uses_dedicated_comment_event(self):
        github = FakeGitHub(data={"pr": 123, "action": "created", "review_comment": 66})
        payload = notify.relay_card(run(event="pull_request_review_comment"), github)
        self.assertIn("답글", payload["text"])
        self.assertIn("#discussion_r66", payload["text"])

    def test_ci_separates_job_results_from_merge_conditions(self):
        source = run(path=".github/workflows/ci.yml")
        source["conclusion"] = "failure"
        payload = notify.ci_card(source, FakeGitHub())
        text = json.dumps(payload, ensure_ascii=False)
        self.assertIn("문제 은행 검증\\n통과", text)
        self.assertIn("화면 테스트\\n실패", text)
        self.assertIn("전체 머지 조건은 PR에서", text)
        self.assertNotIn("모든 검사 통과", text)

    def test_ci_skips_push_cancellation_and_superseded_head(self):
        source = run(path=".github/workflows/ci.yml")
        github = FakeGitHub()
        source["event"] = "push"
        self.assertIsNone(notify.ci_card(source, github))
        source["event"] = "pull_request"
        source["conclusion"] = "cancelled"
        self.assertIsNone(notify.ci_card(source, github))
        source["conclusion"] = "success"
        github.pr["head"]["sha"] = "b" * 40
        self.assertIsNone(notify.ci_card(source, github))

    def test_unknown_workflow_cannot_loop(self):
        source = run(path=".github/workflows/slack-notify.yml")
        self.assertIsNone(notify.notification("workflow_run", event(source), FakeGitHub(source=source)))

    def test_event_attempt_cannot_be_replaced_by_newer_result(self):
        source = run(path=".github/workflows/ci.yml")
        original = event(source)
        source["run_attempt"] = 2
        github = FakeGitHub(source=source)
        self.assertIsNone(notify.notification("workflow_run", original, github))
        github.source["run_attempt"] = 1
        payload = notify.notification("workflow_run", original, github)
        self.assertIn("/attempts/1", payload["text"])

    def test_comment_has_link_but_no_body_and_bot_is_excluded(self):
        body = {"repository": {"full_name": notify.REPO}, "action": "created",
                "issue": {"number": 123, "pull_request": {}},
                "comment": {"id": 99, "body": "private-answer-never-send",
                            "user": {"login": "student", "type": "User"}}}
        body["issue"]["pull_request"] = {"url": "unused"}
        payload = notify.notification("issue_comment", body, FakeGitHub())
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("private-answer-never-send", text)
        self.assertIn("#issuecomment-99", text)
        body["comment"]["user"]["type"] = "Bot"
        self.assertIsNone(notify.notification("issue_comment", body, FakeGitHub()))

    def test_untrusted_text_cannot_mention_channel_or_create_links(self):
        pr = copy.deepcopy(PR)
        pr["title"] = "<!channel> <https://evil.example|click> & *title*"
        payload = notify.card("새 PR", "설명", pr)
        self.assertNotIn("<!channel>", payload["text"])
        blocks = payload["attachments"][0]["blocks"]
        self.assertEqual("plain_text", blocks[1]["text"]["type"])
        self.assertTrue(all(block.get("text", {}).get("type") != "mrkdwn" for block in blocks))

    def test_missing_webhook_skips_without_network(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(notify, "send") as send:
            self.assertEqual(0, notify.main())
            send.assert_not_called()

    def test_connection_message_does_not_claim_real_ci_success(self):
        payload = notify.notification("workflow_dispatch", {"repository": {"full_name": notify.REPO}}, FakeGitHub())
        self.assertIn("연결을 확인", payload["text"])
        self.assertIn("실제 PR이나 검사 결과가 아닙니다", json.dumps(payload, ensure_ascii=False))

    def test_invalid_webhook_rejected_and_transport_error_does_not_leak_it(self):
        with self.assertRaises(ValueError), patch.object(notify, "read_url") as read:
            notify.send({}, "https://evil.example/services/key")
        read.assert_not_called()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "event.json"
            path.write_text(json.dumps({"repository": {"full_name": notify.REPO}}))
            env = {"SLACK_STUDY_WEBHOOK_URL": "secret-value", "GITHUB_EVENT_PATH": str(path),
                   "GITHUB_EVENT_NAME": "workflow_dispatch", "GH_TOKEN": "token-value"}
            with patch.dict(os.environ, env), patch.object(notify, "send", side_effect=ValueError("secret-value")), patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(1, notify.main())
                self.assertNotIn("secret-value", stderr.getvalue())

    def test_artifact_redirect_never_forwards_github_authorization(self):
        error = HTTPError("https://api.github.com/unused", 302, "Found",
                          {"Location": "https://example.blob.core.windows.net/signed-file"}, None)
        with patch.object(notify, "read_url", side_effect=[error, b"zip"]) as read:
            self.assertEqual(b"zip", notify.GitHub("private-token").get(notify.endpoint("actions/artifacts/1/zip"), binary=True))
        first, second = [call.args[0] for call in read.call_args_list]
        self.assertEqual("Bearer private-token", first.get_header("Authorization"))
        self.assertIsNone(second.get_header("Authorization"))

    def test_artifact_redirect_to_unknown_host_is_rejected(self):
        error = HTTPError("https://api.github.com/unused", 302, "Found",
                          {"Location": "https://evil.example/download"}, None)
        with patch.object(notify, "read_url", side_effect=error) as read, self.assertRaises(ValueError):
            notify.GitHub("private-token").get(notify.endpoint("actions/artifacts/1/zip"), binary=True)
        self.assertEqual(1, read.call_count)


if __name__ == "__main__":
    unittest.main()
