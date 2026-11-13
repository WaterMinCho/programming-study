# -*- coding: utf-8 -*-
"""가짜 조회·전송으로 종합 알림의 완료 시점과 재시도를 확인함."""
import copy
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from tools import slack_summary as summary
from tools.study_checks import NOTIFY_CONTEXT, REVIEW_CONTEXT
from tests.test_study_checks import SHA, job, review

PR = {"number": 123, "title": "docs: 사용 안내 수정", "body": "사용 안내를 수정함.", "state": "open", "draft": False,
      "user": {"login": "WaterMinCho"}, "html_url": summary.WEB+"/pull/123", "mergeable": True, "mergeable_state": "clean",
      "head": {"sha": SHA, "ref": "dev/example", "repo": {"full_name": "WaterMinCho/programming-study"}},
      "base": {"sha": "b" * 40, "ref": "main", "repo": {"full_name": summary.REPO}}}


def workflow(path="ci.yml", **fields):
    return {"id": 7, "run_attempt": 1, "head_sha": SHA, "head_branch": PR["head"]["ref"],
            "head_repository": PR["head"]["repo"], "repository": {"full_name": summary.REPO}, "name": path,
            "event": "pull_request", "path": ".github/workflows/"+path, "status": "completed", "conclusion": "success",
            "html_url": summary.WEB+"/actions/runs/7", **fields}


class FakeGitHub:
    def __init__(self):
        self.pr = copy.deepcopy(PR)
        self.files = [{"filename": "README.md"}]
        self.reviews = []
        self.statuses = []
        self.runs = {path: [workflow(path)] for path in ("ci.yml", "style.yml", "journey.yml", "learning-server.yml")}
        self.runs["release-check.yml"] = [workflow("release-check.yml")]
        self.source = workflow()
        self.associated = [self.pr]
        self.posts = []
        self.after_get = None

    def get(self, path):
        tail = path.removeprefix(summary.endpoint(""))
        if tail == "pulls/123":
            result = copy.deepcopy(self.pr)
            if self.after_get:
                self.after_get(self.pr)
                self.after_get = None
            return result
        if tail.startswith("actions/workflows/"):
            return {"workflow_runs": self.runs[tail.split("/")[2]]}
        if tail.startswith("actions/runs/"):
            return self.source
        if tail.startswith("commits/") and tail.endswith("/pulls?per_page=100"):
            return self.associated
        raise AssertionError(path)

    def pages(self, path):
        if path.endswith("/files"):
            return iter(self.files)
        if path.endswith("/reviews"):
            return iter(self.reviews)
        if path.endswith("/statuses"):
            return iter(self.statuses)
        if path.endswith("pulls?state=open&base=main"):
            return iter([self.pr])
        raise AssertionError(path)

    def post(self, path, payload):
        if not path.startswith(summary.endpoint("statuses/")):
            raise AssertionError(path)
        self.posts.append(copy.deepcopy(payload))
        self.statuses.insert(0, copy.deepcopy(payload))
        return payload


class SummaryTest(unittest.TestCase):
    def setUp(self):
        self.github = FakeGitHub()
        self.rows = self.checks_for(["README.md"])
        self.rollup_patch = patch.object(summary, "rollup", side_effect=lambda pr: {"headRefOid": SHA, "statusCheckRollup": self.rows})
        self.rollup_patch.start()
        self.addCleanup(self.rollup_patch.stop)
        self.transport = patch.object(summary, "send")
        self.send = self.transport.start()
        self.addCleanup(self.transport.stop)

    def aggregate(self):
        return summary.aggregate(123, self.github)

    def checks_for(self, files):
        return [{"context": name, "state": "SUCCESS"} if name == "PR 제목" else job(name)
                for name in summary.required_names(files, self.github.pr)]

    def final(self):
        result = self.aggregate()
        self.assertIsNotNone(result)
        return result

    def event(self):
        return {"repository": {"full_name": summary.REPO}, "action": "completed", "workflow_run": {"id": 7, "run_attempt": 1}}

    def test_general_pr_has_no_claim_of_code_review_or_self_approval(self):
        text = json.dumps(self.final()[2], ensure_ascii=False)
        self.assertIn("검사 통과", text)
        self.assertNotIn("자동 검토 대상이 아닙니다", text)
        self.assertNotIn("검토 완료", text)
        self.assertEqual([], self.github.posts)

    def test_ready_card_keeps_only_status_title_result_and_link(self):
        self.github.pr["user"]["login"] = "wamangdoo"
        self.rows.append({"context": REVIEW_CONTEXT, "state": "SUCCESS"})
        self.github.reviews = [review()]
        pr, result, payload = self.final()
        self.assertTrue(result["ready"])
        self.assertLessEqual(len(payload["blocks"]), 4)
        self.assertEqual("머지 준비 완료", payload["blocks"][0]["text"]["text"])
        self.assertIn(pr["title"], payload["blocks"][1]["text"]["text"])
        self.assertEqual("검사 통과 · 검토 완료 · 운영자 확인 후 머지", payload["blocks"][2]["text"]["text"])
        self.assertFalse(any("fields" in block or block["type"] == "context" for block in payload["blocks"]))
        self.assertNotIn(pr["head"]["sha"][:10], payload["text"])
        self.assertIn(pr["html_url"], payload["text"])

    def test_workflow_sparse_checkout_can_import_the_notification_module(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root/".github/workflows/slack-notify.yml").read_text(encoding="utf-8")
        files = re.findall(r"^            (tools/[^\s]+)$", workflow, re.M)
        self.assertTrue(files)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            for name in files:
                path = target/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((root/name).read_bytes())
            result = subprocess.run([sys.executable, "-I", "-c",
                                     "import sys; sys.path.insert(0, sys.argv[1]); import tools.slack_summary", str(target)],
                                    cwd=target, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_failed_card_keeps_a_bounded_result_without_extra_rows(self):
        self.rows[0] = job("필수 검사", "FAILURE")
        self.rows.append(job("긴 검사 이름\n" + "x" * 4000, "FAILURE"))
        payload = self.final()[2]
        description = payload["blocks"][2]["text"]["text"]
        self.assertEqual("확인 필요", payload["blocks"][0]["text"]["text"])
        self.assertIn("검사: 필수 검사", description)
        self.assertIn("PR에서 남은 조건 확인", description)
        self.assertLess(len(description), 400)
        self.assertNotIn("\n", description)

    def test_team_review_is_required_even_after_ci_failure(self):
        self.github.pr["user"]["login"] = "wamangdoo"
        self.rows[0] = job("필수 검사", "FAILURE")
        self.assertIsNone(self.aggregate())
        self.rows.append({"context": REVIEW_CONTEXT, "state": "FAILURE"})
        self.github.reviews = [review("CHANGES_REQUESTED")]
        self.assertIn("피드백 확인 필요", self.final()[2]["text"])

    def test_all_ci_jobs_must_be_registered(self):
        for name in ("변경 범위", "기능·자료 검사", "화면 테스트"):
            original = self.rows
            self.rows = [row for row in original if (row.get("name") or row.get("context")) != name]
            self.assertIsNone(self.aggregate())
            self.rows = original

    def test_conditionally_triggered_workflow_cannot_arrive_late(self):
        for path, workflow_path, expected in (("experiments/alice/train.py", "ci.yml", "모델 제출 검사"),
                                             ("learning_server/app.py", "learning-server.yml", "운영 경로 (windows-latest)"),
                                             ("dungeons/d01/p1/problem.md", "journey.yml", "여정 문제 검증")):
            with self.subTest(path=path):
                self.github.files = [{"filename": path}]
                self.rows = [row for row in self.checks_for([path]) if (row.get("name") or row.get("context")) != expected]
                self.assertIsNone(self.aggregate())
                self.rows.append(job(expected))
                self.github.runs[workflow_path][0]["status"] = "queued"
                self.assertIsNone(self.aggregate())
                self.github.runs[workflow_path][0]["status"] = "completed"
                self.assertIsNotNone(self.aggregate())

    def test_path_filters_do_not_match_unrelated_similar_names(self):
        names = summary.required_names(["aiprep/privacy.py.bak", "tests/test_learning_server.py.old", "journey-old/notes.md"])
        self.assertNotIn("운영 경로 (ubuntu-latest)", names)
        self.assertNotIn("여정 문제 검증", names)
        for path in ("tests/test_journey_runner.py", "tools/journey_art/d01.py", ".github/workflows/journey.yml"):
            self.assertIn("여정 문제 검증", summary.required_names([path]))

    def test_release_paths_match_pr_filter_and_not_unrelated_gui_changes(self):
        for files in (["gui/mascot.py"], ["tools/check_release.py.bak"], [".github/workflows/release-check.yml.old"]):
            self.assertFalse(summary.release_expected(files, self.github.pr))
            self.assertNotIn("새 설치와 작은 창 (배율 1)", summary.required_names(files, self.github.pr))
        for path in summary.RELEASE_PATHS:
            self.assertTrue(summary.release_expected([path], self.github.pr))
            self.assertIn("새 설치와 작은 창 (배율 1.5)", summary.required_names([path], self.github.pr))

    def test_planned_paths_and_names_match_the_actual_workflow_files(self):
        root = Path(__file__).resolve().parents[1]/".github/workflows"
        for filename, patterns in (("journey.yml", summary.JOURNEY_PATHS), ("learning-server.yml", summary.SERVER_PATHS),
                                   ("release-check.yml", summary.RELEASE_PATHS)):
            text = (root/filename).read_text(encoding="utf-8")
            paths = re.findall(r"^\s+- [\"']([^\"']+)[\"']\s*$", text, re.M)
            self.assertEqual(set(patterns), set(paths), filename)
        journey = (root/"journey.yml").read_text(encoding="utf-8")
        for name in ("바뀐 곳 보기", "여정 문제 검증", "여정 JS 검증 (Node 22)"):
            self.assertIn("    name: "+name+"\n", journey)
        self.assertIn("name: 여정 실행기 (Python ${{ matrix.python }})", journey)
        self.assertIn('python: ["3.10", "3.11", "3.12", "3.13", "3.14"]', journey)
        server = (root/"learning-server.yml").read_text(encoding="utf-8")
        self.assertIn("name: 운영 경로 (${{ matrix.os }})", server)
        self.assertIn("os: [ubuntu-latest, windows-latest]", server)
        release = (root/"release-check.yml").read_text(encoding="utf-8")
        self.assertIn("name: 새 설치와 작은 창 (배율 ${{ matrix.scale }})", release)
        self.assertIn("scale: ['1', '1.5']", release)

    def test_release_waits_for_fork_pr_but_excludes_legacy_submissions(self):
        self.github.pr["head"].update(ref="study/learner")
        self.assertFalse(summary.release_expected(["tools/check_release.py"], self.github.pr))
        self.github.pr["head"].update(ref="main", repo={"full_name": "learner/fork"})
        self.assertTrue(summary.release_expected(["tools/check_release.py"], self.github.pr))

    def test_late_windows_workflow_and_both_scale_jobs_must_finish(self):
        self.github.files = [{"filename": "tools/check_release.py"}]
        self.rows = self.checks_for(["tools/check_release.py"])
        run = self.github.runs["release-check.yml"][0]
        run["status"] = "in_progress"
        self.assertIsNone(self.aggregate())
        run["status"] = "completed"
        self.rows[-1]["status"] = "IN_PROGRESS"
        self.assertIsNone(self.aggregate())
        self.rows.pop()
        self.assertIsNone(self.aggregate())
        self.rows.append(job("새 설치와 작은 창 (배율 1.5)"))
        self.assertIsNotNone(self.aggregate())

    def test_gui_change_does_not_wait_for_untriggered_release_workflow(self):
        self.github.files = [{"filename": "gui/mascot.py"}]
        self.github.runs["release-check.yml"] = []
        self.assertIsNotNone(self.aggregate())

    def test_journey_uses_actual_job_names_and_waits_for_late_matrix(self):
        self.github.files = [{"filename": "tools/verify_journey.py"}]
        self.rows = self.checks_for(["tools/verify_journey.py"])
        for version in ("3.10", "3.11", "3.12", "3.13", "3.14"):
            self.rows.append(job("여정 실행기 (Python %s)" % version))
        self.rows[-1]["status"] = "QUEUED"
        self.assertIsNone(self.aggregate())
        self.rows[-1]["status"] = "COMPLETED"
        self.assertIsNotNone(self.aggregate())

    def test_windows_pr_completion_selects_current_pr(self):
        self.github.source = workflow("release-check.yml")
        self.assertEqual([123], summary.candidates("workflow_run", self.event(), self.github))
        self.github.pr["head"]["sha"] = "c" * 40
        self.assertEqual([], summary.candidates("workflow_run", self.event(), self.github))

    def test_rename_preserves_old_path_for_conditional_work(self):
        self.github.files = [{"filename": "docs/old.md", "previous_filename": "journey/engine.py"}]
        self.assertIsNone(self.aggregate())

    def test_latest_workflow_in_progress_or_missing_waits(self):
        self.github.runs["ci.yml"].append(workflow(id=8, status="in_progress"))
        self.assertIsNone(self.aggregate())
        self.github.runs["ci.yml"] = []
        self.assertIsNone(self.aggregate())

    def test_workflow_failure_cannot_be_hidden_by_stale_success_rollup(self):
        self.github.runs["ci.yml"][0]["conclusion"] = "failure"
        self.assertFalse(self.final()[1]["passed"])

    def test_workflow_head_branch_and_source_repository_must_match(self):
        for field, value in (("head_sha", "c" * 40), ("head_branch", "other"),
                             ("head_repository", {"full_name": "other/fork"}), ("event", "push")):
            with self.subTest(field=field):
                self.github.runs["ci.yml"] = [workflow(**{field: value})]
                self.assertIsNone(self.aggregate())

    def test_mergeability_unknown_defers_success_and_failure(self):
        self.github.pr["mergeable_state"] = "unknown"
        self.assertIsNone(self.aggregate())
        self.rows[0]["conclusion"] = "FAILURE"
        self.assertIsNone(self.aggregate())

    def test_pr_changes_during_aggregation_are_not_sent(self):
        for field in ("head", "base", "title", "body", "draft", "state"):
            with self.subTest(field=field):
                self.github.pr = copy.deepcopy(PR)
                def change(pr):
                    if field in ("head", "base"):
                        pr[field]["sha"] = "c" * 40
                    else:
                        pr[field] = True if field == "draft" else "changed"
                self.github.after_get = change
                self.assertIsNone(self.aggregate())

    def test_closed_draft_and_solution_prs_are_excluded(self):
        for field, value in (("state", "closed"), ("draft", True)):
            self.github.pr = copy.deepcopy(PR)
            self.github.pr[field] = value
            self.assertIsNone(self.aggregate())
        self.github.pr = copy.deepcopy(PR)
        self.github.pr["head"]["ref"] = "study/student"
        self.assertIsNone(self.aggregate())
        self.github.pr = copy.deepcopy(PR)
        self.github.files = [{"filename": "submissions/student/a.py"}]
        self.assertIsNone(self.aggregate())

    def test_duplicate_delivery_and_identical_rerun_send_once(self):
        final = self.final()
        self.assertTrue(summary.deliver(*final, self.github, "unused"))
        self.github.runs["ci.yml"][0].update(id=8, run_attempt=2, html_url=summary.WEB+"/actions/runs/8")
        self.assertFalse(summary.deliver(*self.final(), self.github, "unused"))
        self.assertEqual(1, self.send.call_count)
        self.assertEqual(["success", "success"], [row["state"] for row in self.github.posts])
        self.assertEqual(["sending", "sent"], [row["description"].split(":")[0] for row in self.github.posts])

    def test_notification_markers_do_not_make_mergeability_unstable(self):
        original = self.github.post
        def post(path, payload):
            result = original(path, payload)
            if payload["context"] == NOTIFY_CONTEXT and payload["state"] != "success":
                self.github.pr["mergeable_state"] = "unstable"
            return result
        with patch.object(self.github, "post", side_effect=post):
            self.assertTrue(summary.deliver(*self.final(), self.github, "unused"))
        self.assertEqual("clean", self.github.pr["mergeable_state"])
        self.assertTrue(all(row["state"] == "success" for row in self.github.posts))
        self.send.assert_called_once()

    def test_changed_head_or_review_before_delivery_defers_without_writes(self):
        final = self.final()
        self.github.pr["head"]["sha"] = "c" * 40
        self.assertFalse(summary.deliver(*final, self.github, "unused"))
        self.send.assert_not_called()
        self.assertEqual([], self.github.posts)

    def test_review_changes_before_delivery_defer_without_writes(self):
        self.github.pr["user"]["login"] = "michae18"
        self.github.reviews = [review()]
        self.rows.append({"context": REVIEW_CONTEXT, "state": "SUCCESS"})
        final = self.final()
        self.github.reviews = [review("CHANGES_REQUESTED")]
        self.assertFalse(summary.deliver(*final, self.github, "unused"))
        self.send.assert_not_called()
        self.assertEqual([], self.github.posts)

    def test_pr_changes_after_reservation_prevent_send(self):
        original = self.github.post
        def post(path, payload):
            result = original(path, payload)
            if payload["description"].startswith("sending:"):
                self.github.pr["head"]["sha"] = "c" * 40
            return result
        with patch.object(self.github, "post", side_effect=post):
            self.assertFalse(summary.deliver(*self.final(), self.github, "unused"))
        self.send.assert_not_called()
        self.assertEqual("success", self.github.statuses[0]["state"])
        self.assertTrue(self.github.statuses[0]["description"].startswith("failed:"))

    def test_unknown_mergeability_after_reservation_prevents_send(self):
        original = self.github.post
        def post(path, payload):
            result = original(path, payload)
            if payload["description"].startswith("sending:"):
                self.github.pr["mergeable_state"] = "unknown"
            return result
        with patch.object(self.github, "post", side_effect=post):
            self.assertFalse(summary.deliver(*self.final(), self.github, "unused"))
        self.send.assert_not_called()

    def test_explicit_slack_rejection_allows_retry(self):
        for error in (ValueError("not acknowledged"), HTTPError("unused", 429, "retry", {}, None)):
            with self.subTest(error=type(error).__name__):
                self.github.statuses = []
                self.send.side_effect = error
                with self.assertRaises(type(error)):
                    summary.deliver(*self.final(), self.github, "unused")
                self.assertEqual("success", self.github.statuses[0]["state"])
                self.assertTrue(self.github.statuses[0]["description"].startswith("failed:"))
                self.send.side_effect = None
                self.assertTrue(summary.deliver(*self.final(), self.github, "unused"))

    def test_lost_slack_ack_preserves_sending_and_prevents_retry(self):
        self.send.side_effect = URLError("connection lost")
        with self.assertRaises(URLError):
            summary.deliver(*self.final(), self.github, "unused")
        self.send.side_effect = None
        self.assertFalse(summary.deliver(*self.final(), self.github, "unused"))
        self.assertEqual(1, self.send.call_count)
        self.assertEqual("success", self.github.statuses[0]["state"])
        self.assertTrue(self.github.statuses[0]["description"].startswith("sending:"))

    def test_uncertain_delivery_is_not_retried_when_result_key_changes(self):
        self.send.side_effect = URLError("connection lost")
        with self.assertRaises(URLError):
            summary.deliver(*self.final(), self.github, "unused")
        self.send.side_effect = None
        self.github.runs["ci.yml"][0]["conclusion"] = "failure"
        self.assertFalse(summary.deliver(*self.final(), self.github, "unused"))
        self.assertEqual(1, self.send.call_count)

    def test_legacy_pending_record_without_target_url_blocks_retry(self):
        self.github.statuses = [{"context": NOTIFY_CONTEXT, "state": "pending", "description": "sending:previous-key", "target_url": None}]
        self.assertFalse(summary.deliver(*self.final(), self.github, "unused"))
        self.send.assert_not_called()

    def test_github_ack_failure_after_slack_success_does_not_resend(self):
        original = self.github.post
        def post(path, payload):
            if payload["description"].startswith("sent:"):
                raise URLError("lost github ack")
            return original(path, payload)
        with patch.object(self.github, "post", side_effect=post):
            with self.assertRaises(URLError):
                summary.deliver(*self.final(), self.github, "unused")
            self.assertFalse(summary.deliver(*self.final(), self.github, "unused"))
        self.assertEqual(1, self.send.call_count)

    def test_reservation_failure_prevents_slack_send(self):
        with patch.object(self.github, "post", side_effect=URLError("no github")):
            with self.assertRaises(URLError):
                summary.deliver(*self.final(), self.github, "unused")
        self.send.assert_not_called()

    def test_late_workflow_attempt_push_and_obsolete_head_are_excluded(self):
        for change in ({"run_attempt": 2}, {"event": "push"}, {"head_sha": "c" * 40}):
            with self.subTest(change=change):
                self.github.source = workflow(**change)
                self.assertEqual([], summary.candidates("workflow_run", self.event(), self.github))

    def test_status_only_selects_current_head_and_known_context(self):
        event = {"repository": {"full_name": summary.REPO}, "context": REVIEW_CONTEXT, "sha": SHA}
        self.assertEqual([123], summary.candidates("status", event, self.github))
        self.github.pr["head"]["sha"] = "c" * 40
        self.assertEqual([], summary.candidates("status", event, self.github))
        event["context"] = NOTIFY_CONTEXT
        self.assertEqual([], summary.candidates("status", event, self.github))

    def test_late_relay_does_not_trigger_new_head(self):
        self.github.source = workflow("slack-events.yml", head_sha="c" * 40)
        with patch.object(summary, "metadata", return_value={"pr": 123}):
            self.assertEqual([], summary.candidates("workflow_run", self.event(), self.github))

    def test_title_workflow_targets_associated_pr_head_instead_of_base_sha(self):
        self.github.source = workflow("pr-title.yml", event="pull_request_target", head_sha="b" * 40,
                                      pull_requests=[{"number": 123, "head": {"sha": SHA}}])
        self.assertEqual([123], summary.candidates("workflow_run", self.event(), self.github))
        self.github.pr["head"]["sha"] = "c" * 40
        self.assertEqual([], summary.candidates("workflow_run", self.event(), self.github))

    def test_failed_required_check_is_named_even_when_skipped(self):
        self.rows[0]["conclusion"] = "SKIPPED"
        final = self.final()
        self.assertFalse(final[1]["passed"])
        self.assertIn("검사: 필수 검사", final[2]["text"])

    def test_rollup_rejects_head_change_without_running_gh(self):
        with patch("subprocess.run", return_value=type("Result", (), {"stdout": json.dumps({"headRefOid": "c" * 40, "statusCheckRollup": []})})()) as run:
            self.rollup_patch.stop()
            self.assertIsNone(summary.rollup(PR))
            run.assert_called_once()

    def test_main_dry_run_never_posts_or_sends(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"event.json"
            path.write_text(json.dumps({"repository": {"full_name": summary.REPO}}), encoding="utf-8")
            env = {"GITHUB_EVENT_PATH": str(path), "GITHUB_EVENT_NAME": "workflow_dispatch", "GH_TOKEN": "unused",
                   "SLACK_DRY_RUN": "1", "SLACK_STUDY_WEBHOOK_URL": "unused"}
            with patch.dict(os.environ, env), patch.object(summary, "Client", return_value=self.github), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(0, summary.main())
            self.send.assert_not_called()
            self.assertEqual([], self.github.posts)

    def test_main_routes_enabled_daily_alerts_through_the_thread_sender(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"event.json"
            path.write_text(json.dumps({"repository": {"full_name": summary.REPO}}), encoding="utf-8")
            env = {"GITHUB_EVENT_PATH": str(path), "GITHUB_EVENT_NAME": "workflow_dispatch", "GH_TOKEN": "unused",
                   "SLACK_DRY_RUN": "0", "SLACK_STUDY_WEBHOOK_URL": "", "SLACK_STUDY_DAILY_THREADS": "1",
                   "SLACK_STUDY_BOT_TOKEN": "xoxb-example", "SLACK_STUDY_CHANNEL_ID": "C123ABC456",
                   "SLACK_STUDY_THREAD_ANCHOR": "a" * 40}
            with patch.dict(os.environ, env), patch.object(summary, "Client", return_value=self.github), \
                    patch.object(summary, "DailyThreads") as sender, patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(0, summary.main())
            sender.return_value.send.assert_called_once()
            self.send.assert_not_called()
            self.assertEqual("sent:", self.github.posts[-1]["description"][:5])

    def test_daily_dry_run_does_not_create_a_parent_or_need_bot_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"event.json"
            path.write_text(json.dumps({"repository": {"full_name": summary.REPO}}), encoding="utf-8")
            env = {"GITHUB_EVENT_PATH": str(path), "GITHUB_EVENT_NAME": "workflow_dispatch", "GH_TOKEN": "unused",
                   "SLACK_DRY_RUN": "1", "SLACK_STUDY_DAILY_THREADS": "1", "SLACK_STUDY_BOT_TOKEN": ""}
            with patch.dict(os.environ, env), patch.object(summary, "Client", return_value=self.github), \
                    patch.object(summary, "DailyThreads") as sender, patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(0, summary.main())
            sender.assert_not_called()
            self.send.assert_not_called()
            self.assertEqual([], self.github.posts)

    def test_main_waits_bounded_time_without_partial_notification(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_PATH": "unused", "GITHUB_EVENT_NAME": "workflow_dispatch", "GH_TOKEN": "unused"}), \
                patch.object(summary.Path, "read_text", return_value="{}"), patch.object(summary, "Client", return_value=self.github), \
                patch.object(summary, "candidates", return_value=[123]), patch.object(summary, "aggregate", return_value=None) as aggregate, \
                patch.object(summary.time, "sleep") as sleep, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(0, summary.main())
        self.assertEqual(3, aggregate.call_count)
        self.assertEqual(2, sleep.call_count)
        self.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
