# -*- coding: utf-8 -*-
"""외부 게시·모델 실행 없이 검토 판정과 게시 복구를 검사함."""
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
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
    def test_feedback_separates_required_fixes_from_optional_suggestions(self):
        result = assessment(blocking=True)
        optional = dict(result["findings"][0], blocking=False, hint="입력의 단위를 설명에 남김.")
        result["findings"].append(optional)
        body = worker.body_for({"head": HEAD}, result, "marker", "REQUEST_CHANGES")
        self.assertIn("수정 필요 · train.py:1", body)
        self.assertIn(FILE+"#L1)", body)
        self.assertIn("수정 힌트: 반복 시작에서 기울기를 초기화함.", body)
        self.assertIn("수정 힌트: 입력의 단위를 설명에 남김.", body)
        self.assertIn("이전 기울기를 더함.", body)
        self.assertIn("기대 결과: 현재 배치의 기울기만 사용함.", body)
        self.assertLess(body.index("이전 기울기를 더함."), body.index("<details>"))
        self.assertIn("<summary>코드 근거와 수정 힌트</summary>", body)
        self.assertIn("<summary>선택 제안·질문 펼치기 · 승인 조건이 아닙니다</summary>", body)

    def test_followup_steps_only_appear_when_there_is_something_to_answer(self):
        optional = assessment(blocking=True)
        optional["findings"][0]["blocking"] = False
        for event, result, needs_guide, needs_reply in (
                ("APPROVE", assessment(), False, False),
                ("COMMENT", assessment("needs_context"), False, False),
                ("REQUEST_CHANGES", assessment(blocking=True), True, False),
                ("APPROVE", optional, False, False),
                ("COMMENT", assessment(), False, False)):
            with self.subTest(event=event, findings=bool(result["findings"])):
                body = worker.body_for({"head": HEAD}, result, "marker", event)
                self.assertEqual(needs_guide, worker.FOLLOWUP_GUIDE in body)
                self.assertEqual(needs_reply, worker.DISCUSSION_GUIDE in body)
                self.assertNotIn("Stage는", body)
                if needs_guide:
                    self.assertIn("같은 작업 브랜치에 Commit·Push", body)
                    self.assertIn("SourceTree·터미널", body)

    def test_reader_format_preserves_all_blockers_and_commit_evidence(self):
        result = assessment(blocking=True)
        result["format_version"] = 2
        result["summary"] = "학습 반복에서 기울기를 초기화해 주세요."
        item = result["findings"][0]
        item.update(title="반복 시작에서 기울기를 초기화해 주세요", condition="학습을 두 번 반복할 때",
                    actual="이전 기울기에 이번 값을 더합니다.", expected="현재 배치의 기울기만 사용합니다.",
                    reason="초기화가 빠져 이전 배치가 이번 계산에 섞입니다.", hint="각 반복의 시작 위치를 확인해 주세요.",
                    check="두 배치의 기울기를 따로 비교해 주세요.")
        result["findings"] = [dict(item, title="기울기 초기화 위치 확인 %d" % i) for i in range(5)]
        body = worker.body_for({"head": HEAD}, result, "marker", "REQUEST_CHANGES")
        self.assertEqual(5, body.count("### 수정 필요"))
        self.assertIn("검토한 커밋: `"+HEAD+"`", body)
        self.assertIn("/blob/"+HEAD+"/"+FILE+"#L1", body)
        data = {"files": [FILE], "changed_paths": [FILE], "diff": DIFF, "title": self.pr["title"]}
        self.assertEqual("REQUEST_CHANGES", worker.validate(data, result, "michae18"))
        for update in ({"format_version": True}, {"format_version": 3}, {"summary": "x" * 401}):
            with self.subTest(update=update), self.assertRaises(worker.review.ReviewError):
                worker.validate(data, dict(result, **update), "michae18")
        result["findings"][0]["title"] = "두 줄\n제목"
        with self.assertRaises(worker.review.ReviewError):
            worker.validate(data, result, "michae18")

    def test_approved_legacy_questions_are_optional_and_quotes_cannot_hide_the_review(self):
        result = assessment(blocking=True)
        result["findings"][0].update(blocking=False, quote="</details><script>x</script>")
        result["questions"] = ["빈 이력의 입력을 어떻게 처리할 계획인가요?"]
        body = worker.body_for({"head": HEAD}, result, "marker", "APPROVE")
        self.assertNotIn(worker.FOLLOWUP_GUIDE, body)
        self.assertNotIn("### 확인할 내용", body)
        self.assertGreater(body.index(result["questions"][0]), body.index("선택 제안·질문 펼치기"))
        self.assertIn("&lt;/details&gt;&lt;script&gt;x&lt;/script&gt;", body)
        self.assertNotIn("<script>", body)

    def test_new_reader_format_checks_authored_prose_without_rewriting_code_quotes(self):
        result = assessment(blocking=True)
        result.update(format_version=2, summary="입력 처리를 수정해 주세요.")
        item = result["findings"][0]
        item.update(title="입력 조건을 확인해 주세요", condition="두 값을 비교할 때", actual="경계값을 확인하지 않았습니다.",
                    expected="경계값에서도 같은 조건을 확인할 수 있습니다.", reason="경계값에서 결과가 달라질 수 있습니다.",
                    check="경계값을 넣고 결과를 비교해 주세요.", hint="", quote="x != y  # 매우 중요 "+chr(0x2014)+" 확인!")
        body = worker.body_for({"head": HEAD}, result, "marker", "REQUEST_CHANGES")
        self.assertIn(item["quote"], body)
        self.assertNotIn("수정 힌트:", body)
        result["summary"] = "입력 처리를 확인했음."
        with self.assertRaises(worker.review.ReviewError):
            worker.body_for({"head": HEAD}, result, "marker", "REQUEST_CHANGES")

    def test_comment_after_approval_is_distinct_from_a_manual_approval_hold(self):
        result = assessment()
        answered = worker.body_for({"head": HEAD}, result, "marker", "COMMENT", checked="APPROVE")
        held = worker.body_for({"head": HEAD}, result, "marker", "COMMENT", checked="COMMENT")
        self.assertIn("기존 승인은 유지", answered)
        self.assertIn("자동 승인 범위 밖", held)
        self.assertNotIn("기존 승인은 유지", held)
        data = {"files": [FILE], "changed_paths": [FILE], "diff": DIFF, "title": self.pr["title"],
                "previous_review_skipped": "content_check"}
        self.assertEqual("COMMENT", worker.validate(data, result, "michae18"))

    def test_missing_prior_context_is_explicit_and_blank_questions_cannot_be_posted(self):
        data = {"head": HEAD, "files": [FILE], "diff": DIFF, "title": self.pr["title"], "previous_review_skipped": "size_limit"}
        result = assessment()
        body = worker.body_for(data, result, "marker", "COMMENT", checked="COMMENT")
        self.assertIn("참고 내용을 포함하지 못해 자동 승인을 보류", body)
        self.assertNotIn("자동 승인 범위 밖", body)
        for question in ("", " "):
            with self.subTest(question=question), self.assertRaises(worker.review.ReviewError):
                worker.validate(data, dict(result, questions=[question]), "michae18")

    def test_review_with_separate_observations_is_not_checked_as_a_commit_message(self):
        result = assessment()
        result["summary"] = "확인한 범위\n\n" + "\n".join(
            "- 입력 %d의 조건과 근거를 확인했음." % index for index in range(6))
        body = worker.body_for({"head": HEAD}, result, "<!-- review -->", "APPROVE")
        self.assertIn("입력 5의 조건", body)
        result["summary"] = "결국 이것입니다."
        with self.assertRaises(worker.review.ReviewError):
            worker.body_for({"head": HEAD}, result, "<!-- review -->", "APPROVE")

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
        self.statuses = {}
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
            self.statuses[path.split("/")[1], data["context"]] = copy.deepcopy(data)
            return {}
        if path.startswith("commits/") and "/status?" in path:
            sha = path.split("/")[1]
            return {"statuses": [copy.deepcopy(row) for (head, _), row in self.statuses.items() if head == sha]}
        if path == "pulls/12":
            return copy.deepcopy(self.current)
        if path == "pulls/12/reviews" and data:
            row = {"id": 100 + len(self.reviews), "user": {"login": "WaterMinCho"}, "body": data["body"],
                   "commit_id": data["commit_id"], "html_url": "https://github.com/example/review/100",
                   "state": {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED", "COMMENT": "COMMENTED"}[data["event"]]}
            self.reviews.append(row)
            return copy.deepcopy(row)
        if path.endswith("/dismissals"):
            identity = int(path.split("/")[-2])
            next(row for row in self.reviews if row["id"] == identity)["state"] = "DISMISSED"
            return {}
        if path.startswith("pulls/12/reviews/"):
            return copy.deepcopy(next(row for row in self.reviews if row["id"] == int(path.rsplit("/", 1)[1])))
        raise AssertionError(path)

    def prepare(self, number, folder, discussion, previous_review=None):
        folder.mkdir(parents=True)
        data = {"number": number, "head": HEAD, "base": BASE, "title": self.pr["title"],
                "description": self.pr["body"], "files": [FILE], "changed_paths": [FILE], "diff": DIFF, "context": [],
                "discussion": discussion, "previous_review": previous_review, **self.packet_changes}
        worker.save(folder/"snapshot.json", data)
        return data

    def snapshot(self, folder):
        return folder, json.loads((folder/"snapshot.json").read_text())

    def model(self, folder, **kwargs):
        self.assertEqual(worker.SCHEMA, kwargs["schema"])
        worker.save(folder/"assessment.json", self.result)
        worker.save(folder/"review.json", {"head": json.loads((folder/"snapshot.json").read_text())["head"]})
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
        self.assertIn("자동 정적 검토이며", self.posted()[0]["body"])
        self.assertIn("PR 코드는 실행하지 않았습니다.", self.posted()[0]["body"])

    def test_previous_review_is_context_without_triggering_a_self_review_loop(self):
        self.reviews.append({"id": 77, "user": {"login": "WaterMinCho"}, "body": "이전 제안", "commit_id": BASE, "state": "APPROVED"})
        self.assertEqual("리뷰 게시함", self.process())
        self.assertEqual("이미 검토함", self.process())
        self.assertEqual(1, len(self.posted()))
        self.assertEqual("이전 제안", self.prepare_mock.call_args.kwargs["previous_review"]["body"])
        self.model_mock.assert_called_once()

    def test_scope_title_images_and_context_only_leave_comment(self):
        data = {"files": [FILE], "changed_paths": [FILE], "diff": DIFF, "title": self.pr["title"]}
        for update in ({"files": ["gui/view.py"]}, {"files": ["experiments/michae18/setup.py"]},
                       {"unreviewed_images": ["chart.png"]}, {"title": "wrong title"}, {"diff": "x" * 60001}):
            with self.subTest(update=update):
                self.assertEqual("COMMENT", worker.validate(dict(data, **update), assessment(), "michae18"))
        self.assertEqual("COMMENT", worker.validate(data, assessment("needs_context"), "michae18"))
        self.assertEqual("COMMENT", worker.validate(data, assessment("changes_requested"), "michae18"))

    def test_rename_from_outside_author_folder_cannot_be_approved(self):
        data = {"files": [FILE], "changed_paths": [FILE, "gui/view.py"], "diff": DIFF, "title": self.pr["title"]}
        self.assertEqual("COMMENT", worker.validate(data, assessment(), "michae18"))
        data["changed_paths"] = [FILE, "experiments/michae18/old_train.py"]
        self.assertEqual("APPROVE", worker.validate(data, assessment(), "michae18"))

    def test_all_changed_paths_must_use_permitted_text_types(self):
        data = {"files": [FILE], "diff": DIFF, "title": self.pr["title"]}
        for old in ("old.ipynb", "old.jsonl", "setup.py", "conftest.py", "../other/train.py"):
            with self.subTest(old=old):
                data["changed_paths"] = [FILE, "experiments/michae18/"+old]
                self.assertEqual("COMMENT", worker.validate(data, assessment(), "michae18"))

    def test_old_cache_without_changed_paths_holds_approval_but_keeps_blockers(self):
        data = {"files": [FILE], "diff": DIFF, "title": self.pr["title"]}
        self.assertEqual("COMMENT", worker.validate(data, assessment(), "michae18"))
        self.assertEqual("REQUEST_CHANGES", worker.validate(data, assessment(blocking=True), "michae18"))
        for paths in (None, [], FILE, ["experiments/michae18/other.py"]):
            with self.subTest(paths=paths):
                self.assertEqual("COMMENT", worker.validate(dict(data, changed_paths=paths), assessment(), "michae18"))

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

    def test_author_explanation_can_resolve_changes_request_on_same_head(self):
        self.prior()
        self.prior("CHANGES_REQUESTED", 2)
        self.author_comment()
        self.process()
        self.assertEqual("APPROVE", self.posted()[0]["event"])
        self.assertEqual("success", self.states()[-1])

    def test_comment_only_history_does_not_prevent_approval(self):
        self.prior("COMMENTED")
        self.author_comment()
        self.process()
        self.assertEqual("APPROVE", self.posted()[0]["event"])
        self.assertEqual("success", self.states()[-1])

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
        self.assertEqual("새 커밋 대기", self.process())
        self.model_mock.assert_not_called()
        self.assertEqual([], self.posted())

    def test_pre_publish_rechecks_head_base_target_and_description(self):
        for change in ({"head": {"sha": "c" * 40, "ref": "models/lstm"}}, {"base": {"sha": "c" * 40, "ref": "main"}},
                       {"base": {"sha": BASE, "ref": "dev"}}, {"draft": True}, {"body": "다른 설명임."},
                       {"title": "docs(model): 제목 수정"}, {"state": "closed"}):
            with self.subTest(change=change):
                self.current = dict(copy.deepcopy(self.pr), **change)
                self.assertEqual("새 커밋 대기", self.process())
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
        self.assertEqual("새 커밋 대기", self.process())
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
        self.assertEqual("새 커밋 대기", self.process())
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
        self.assertEqual("새 커밋 대기", self.process())
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
        self.assertEqual(2, self.model_mock.call_count)
        self.assertFalse((self.folder()/"assessment.json").exists())
        for number in (1, 2):
            self.assertTrue((self.folder()/"quarantine"/("attempt-%d" % number)/"assessment.json").exists())
        self.assertEqual([], self.posted())
        self.commands.assert_not_called()

    def test_validation_failure_quarantines_artifacts_then_allows_fresh_review(self):
        self.result = assessment(blocking=True)
        self.result["findings"][0]["quote"] = "not in diff"
        with self.assertRaises(worker.AttemptError):
            self.process()
        folder = self.folder()
        before = copy.deepcopy(self.result)
        quarantine = folder/"quarantine/attempt-1"
        self.assertEqual(before, json.loads((quarantine/"assessment.json").read_text()))
        self.assertEqual("validation_failed", json.loads((quarantine/"failure.json").read_text())["reason"])
        for name in ("assessment.json", "feedback.md", "review.json"):
            self.assertFalse((folder/name).exists())
            self.assertTrue((quarantine/name).exists())
        if os.name != "nt":
            self.assertEqual(0o700, quarantine.stat().st_mode & 0o777)
            self.assertEqual(0o600, (quarantine/"assessment.json").stat().st_mode & 0o777)
        self.assertEqual("대기", self.process())
        self.model_mock.assert_called_once()
        self.result = assessment()
        with mock.patch.object(worker.time, "time", return_value=10**12):
            self.assertEqual("리뷰 게시함", self.process())
        self.assertEqual(2, self.model_mock.call_count)
        self.assertEqual("done", json.loads((folder/"worker.json").read_text())["phase"])
        self.assertEqual(before, json.loads((quarantine/"assessment.json").read_text()))

    def test_body_failure_is_quarantined_with_a_distinct_reason(self):
        self.result["summary"] = "현재 배치와 이전 배치의 입력 분리를 확인했음."
        with mock.patch.object(worker, "body_for", side_effect=worker.review.ReviewError("게시 문장 확인 실패")), \
                self.assertRaises(worker.AttemptError):
            self.process()
        state = json.loads((self.folder()/"worker.json").read_text())
        self.assertEqual("body_failed", state["reason"])
        self.assertEqual("retry_wait", state["phase"])
        self.result = assessment()
        with mock.patch.object(worker.time, "time", return_value=state["retry_after"]+1):
            self.assertEqual("리뷰 게시함", self.process())
        self.assertEqual(2, self.model_mock.call_count)
        self.assertEqual("APPROVE", self.posted()[0]["event"])

    def test_invalid_assessments_stop_after_three_real_attempts(self):
        self.result["summary"] = "x" * 3001
        with mock.patch.object(worker.time, "time", return_value=1000) as clock:
            for attempt in range(1, 4):
                with self.assertRaises(worker.AttemptError):
                    self.process()
                state = json.loads((self.folder()/"worker.json").read_text())
                self.assertEqual(attempt, state["attempts"])
                self.assertEqual("validation_failed", state["reason"])
                self.assertEqual("대기" if attempt < 3 else "검토 종료", self.process())
                self.assertEqual(attempt, self.model_mock.call_count)
                clock.return_value = state["retry_after"]+1
            self.assertEqual("검토 종료", self.process())
        self.assertEqual(3, self.model_mock.call_count)
        self.assertEqual(3, len(list((self.folder()/"quarantine").iterdir())))
        self.assertEqual("exhausted", state["phase"])
        self.assertEqual([], self.posted())

    def test_legacy_attempt_limit_gets_a_terminal_reason_and_quarantine(self):
        self.result["summary"] = "x" * 3001
        with self.assertRaises(worker.AttemptError):
            self.process()
        folder = self.folder()
        self.model(folder, schema=worker.SCHEMA)
        worker.save(folder/"worker.json", {"phase": "reviewing", "attempts": 3})
        self.model_mock.reset_mock()
        with self.assertRaisesRegex(worker.AttemptError, "재시도 종료"):
            self.process()
        state = json.loads((folder/"worker.json").read_text())
        self.assertEqual("exhausted", state["phase"])
        self.assertEqual("attempt_limit", state["reason"])
        self.assertTrue((folder/"quarantine/attempt-3/assessment.json").exists())
        self.assertEqual("검토 종료", self.process())
        self.model_mock.assert_not_called()

    def test_prepare_failure_is_cached_per_input_version(self):
        self.prepare_mock.side_effect = worker.review.ReviewError("unsupported notebook")
        with self.assertRaises(worker.AttemptError):
            self.process()
        first = self.folder()
        self.assertEqual("prepare_failed", json.loads((first/"worker.json").read_text())["phase"])
        self.assertEqual("준비 실패", self.process())
        self.prepare_mock.assert_called_once()
        changes = (lambda: self.pr["head"].update(sha="c" * 40),
                   lambda: self.pr["base"].update(sha="d" * 40),
                   lambda: self.pr.update(title="docs(model): 입력 확인"),
                   lambda: self.pr.update(body="다른 설명임."), self.author_comment)
        for index, change in enumerate(changes, 2):
            change()
            with self.assertRaises(worker.AttemptError):
                self.process()
            self.assertEqual("준비 실패", self.process())
            self.assertEqual(index, self.prepare_mock.call_count)
        self.model_mock.assert_not_called()

    def test_partial_prepare_failure_does_not_retry_snapshot_forever(self):
        def prepare(number, folder, **kwargs):
            folder.mkdir()
            raise worker.review.ReviewError("partial prepare")
        self.prepare_mock.side_effect = prepare
        with self.assertRaises(worker.AttemptError):
            self.process()
        self.assertEqual("준비 실패", self.process())
        self.prepare_mock.assert_called_once()
        self.model_mock.assert_not_called()

    def test_unknown_old_head_does_not_block_new_head_and_late_review_is_dismissed(self):
        original = self.api
        def unknown(path, data=None, method=None):
            if path == "pulls/12/reviews" and data:
                raise worker.review.ReviewError("unknown acknowledgement")
            return original(path, data, method)
        self.api_mock.side_effect = unknown
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        previous = self.folder()
        ready = json.loads((previous/"publish-ready.json").read_text())
        self.pr["head"]["sha"] = "c" * 40
        self.current = copy.deepcopy(self.pr)
        self.packet_changes["head"] = self.pr["head"]["sha"]
        self.api_mock.side_effect = original
        self.assertEqual("리뷰 게시함", self.process())
        self.assertEqual("unconfirmed", json.loads((previous/"worker.json").read_text())["phase"])
        self.assertTrue((previous/"publish-ready.json").exists())
        self.assertEqual("이미 검토함", self.process())
        self.assertEqual(2, self.model_mock.call_count)
        self.assertEqual(self.pr["head"]["sha"], self.posted()[0]["commit_id"])
        self.reviews.insert(0, {"id": 99, "user": {"login": "WaterMinCho"}, "body": ready["body"],
                                "commit_id": HEAD, "state": "APPROVED", "html_url": "https://github.com/example/review/99"})
        self.assertEqual("이미 검토함", self.process())
        self.assertEqual("DISMISSED", self.reviews[0]["state"])
        self.assertEqual("APPROVED", self.reviews[1]["state"])
        self.assertEqual("superseded", json.loads((previous/"worker.json").read_text())["phase"])
        self.assertEqual(2, self.model_mock.call_count)
        self.assertEqual(1, len(self.posted()))

    def test_unknown_same_head_with_changed_base_still_blocks_reposting(self):
        original = self.api
        def unknown(path, data=None, method=None):
            if path == "pulls/12/reviews" and data:
                raise worker.review.ReviewError("unknown acknowledgement")
            return original(path, data, method)
        self.api_mock.side_effect = unknown
        with self.assertRaises(worker.review.ReviewError):
            self.process()
        self.api_mock.side_effect = original
        self.pr["base"]["sha"] = "c" * 40
        self.current = copy.deepcopy(self.pr)
        self.assertEqual("게시 확인 대기", self.process())
        self.model_mock.assert_called_once()

    def test_identical_status_is_not_posted_repeatedly(self):
        for _ in range(1001):
            worker.status(self.pr, "error", "게시 응답 확인 대기")
        self.assertEqual(["error"], self.states())
        worker.status(self.pr, "pending", "게시 응답 확인 대기")
        worker.status(self.pr, "pending", "새 설명 확인 중")
        worker.status(self.pr, "pending", "새 설명 확인 중", "https://github.com/example/review/2")
        self.pr["head"]["sha"] = "c" * 40
        worker.status(self.pr, "pending", "새 설명 확인 중", "https://github.com/example/review/2")
        self.assertEqual(5, len(self.states()))

    def test_status_post_ack_loss_is_recovered_from_combined_status(self):
        original = self.api
        def unknown(path, data=None, method=None):
            result = original(path, data, method)
            if path.startswith("statuses/"):
                raise worker.review.ReviewError("unknown acknowledgement")
            return result
        self.api_mock.side_effect = unknown
        with self.assertRaises(worker.review.ReviewError):
            worker.status(self.pr, "error", "게시 응답 확인 대기")
        self.api_mock.side_effect = original
        worker.status(self.pr, "error", "게시 응답 확인 대기")
        self.assertEqual(["error"], self.states())

    def test_status_finds_current_context_after_first_combined_page(self):
        current = {"context": worker.REVIEW_CONTEXT, "state": "error", "description": "게시 응답 확인 대기", "target_url": self.pr["html_url"]}
        self.api_mock.side_effect = [{"statuses": [{"context": "other-%d" % index} for index in range(100)]},
                                     {"statuses": [current]}]
        worker.status(self.pr, "error", "게시 응답 확인 대기")
        self.assertEqual(2, self.api_mock.call_count)
        self.assertTrue(self.api_mock.call_args.args[0].endswith("page=2"))

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
        self.result.update(format_version=2, summary="변경한 입력 처리를 확인했습니다.")
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


@unittest.skipIf(os.name == "nt", "Mac worker")
class RuntimeInstallTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="study-runtime-test-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        self.root = self.home/"operations"
        self.root.mkdir(mode=0o755)
        self.source = self.home/"trusted-main"
        original = Path(worker.__file__).resolve().parents[1]
        self.files = {name: (original/name).read_bytes() for name in (
            "tools/study_review_worker.py", "tools/learning_review.py", "tools/study_checks.py",
            "tools/pr_title.py", "tools/check_style.py", "learning_data/privacy.py")}
        for name, raw in {**self.files, "tools/__init__.py": b'raise RuntimeError("source initializer")\n',
                          "learning_data/__init__.py": b'raise RuntimeError("source initializer")\n',
                          ".git/config": b"excluded\n", "submissions/example/answer.py": b"excluded\n",
                          "account.json": b"excluded\n"}.items():
            path = self.source/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.native_run = subprocess.run
        for patcher in (mock.patch.object(worker, "__file__", str(self.source/"tools/study_review_worker.py")),
                        mock.patch.object(Path, "home", return_value=self.home),
                        mock.patch.object(worker.sys, "platform", "darwin")):
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(worker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0))
        self.commands = patcher.start()
        self.addCleanup(patcher.stop)

    def installed(self):
        plist = Path(worker.install(self.root))
        config = plistlib.loads(plist.read_bytes())
        return plist, config, Path(config["WorkingDirectory"])

    def test_install_copies_only_code_and_reads_back_manifest_and_private_settings(self):
        for name in ("worker.log", "worker-error.log"):
            (self.root/name).write_text("previous log\n")
            (self.root/name).chmod(0o644)
        plist, config, runtime = self.installed()
        manifest_raw = (runtime/"manifest.json").read_bytes()
        manifest = json.loads(manifest_raw)
        self.assertEqual(self.root/"runtime"/hashlib.sha256(manifest_raw).hexdigest(), runtime)
        expected = {**self.files, "tools/__init__.py": b"", "learning_data/__init__.py": b""}
        self.assertEqual(set(expected), set(manifest["files"]))
        self.assertEqual(set(expected) | {"manifest.json"},
                         {path.relative_to(runtime).as_posix() for path in runtime.rglob("*") if path.is_file()})
        for name, raw in expected.items():
            self.assertEqual(raw, (runtime/name).read_bytes())
            self.assertEqual({"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}, manifest["files"][name])
        self.assertEqual([sys.executable, "-I", "-B", str(runtime/"tools/study_review_worker.py"),
                          "--once", "--root", str(self.root)], config["ProgramArguments"])
        self.assertEqual(str(self.root/"worker.log"), config["StandardOutPath"])
        self.assertEqual(str(self.root/"worker-error.log"), config["StandardErrorPath"])
        self.assertEqual(63, config["Umask"])
        self.assertEqual(60, config["StartInterval"])
        self.assertTrue(config["RunAtLoad"])
        for folder in (self.root, runtime.parent, runtime, runtime/"tools", runtime/"learning_data"):
            self.assertEqual(0o700, folder.stat().st_mode & 0o777)
        for path in (plist, self.root/"worker.log", self.root/"worker-error.log",
                     *(path for path in runtime.rglob("*") if path.is_file())):
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertEqual("previous log\n", (self.root/"worker.log").read_text())
        self.commands.assert_called_once_with(["launchctl", "bootstrap", "gui/%d" % os.getuid(), str(plist)],
                                              check=True, capture_output=True)

    def test_same_content_reuses_verified_bytes_and_new_content_keeps_old_runtime(self):
        plist, _, first = self.installed()
        before = {path.relative_to(first): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in first.rglob("*") if path.is_file()}
        self.assertEqual(first, self.installed()[2])
        self.assertEqual(before, {path.relative_to(first): (path.read_bytes(), path.stat().st_mtime_ns)
                                  for path in first.rglob("*") if path.is_file()})
        path = self.source/"tools/pr_title.py"
        path.write_bytes(path.read_bytes()+b"\n")
        second = self.installed()[2]
        self.assertNotEqual(first, second)
        self.assertEqual(self.files["tools/pr_title.py"], (first/"tools/pr_title.py").read_bytes())
        self.assertEqual(path.read_bytes(), (second/"tools/pr_title.py").read_bytes())
        self.assertEqual(str(second), plistlib.loads(plist.read_bytes())["WorkingDirectory"])
        self.assertEqual(["launchctl", "bootout", "gui/%d/%s" % (os.getuid(), worker.LABEL)],
                         self.commands.call_args_list[-2].args[0])

    def test_existing_runtime_changes_stop_install_without_overwriting(self):
        for change in ("code", "manifest", "extra", "missing", "symlink", "mode"):
            with self.subTest(change=change):
                root = self.home/change
                root.mkdir(mode=0o700)
                runtime = worker.runtime_copy(root)
                path = runtime/"tools/pr_title.py"
                if change == "code":
                    path.write_bytes(b"changed\n")
                elif change == "manifest":
                    (runtime/"manifest.json").write_text("{}")
                elif change == "extra":
                    (runtime/"extra.py").write_text("pass\n")
                elif change == "missing":
                    path.unlink()
                elif change == "symlink":
                    path.unlink()
                    path.symlink_to(self.source/"tools/pr_title.py")
                else:
                    path.chmod(0o644)
                before = path.read_bytes() if path.exists() else None
                self.commands.reset_mock()
                with self.assertRaises(worker.review.ReviewError):
                    worker.install(root)
                self.commands.assert_not_called()
                self.assertEqual(before, path.read_bytes() if path.exists() else None)

    def test_source_symlink_or_missing_dependency_stops_before_launchctl(self):
        path = self.source/"tools/pr_title.py"
        path.unlink()
        with self.assertRaises(worker.review.ReviewError):
            worker.install(self.root)
        path.symlink_to(self.source/"tools/study_checks.py")
        with self.assertRaises(worker.review.ReviewError):
            worker.install(self.root)
        self.commands.assert_not_called()

    def test_copy_readback_failure_leaves_no_published_runtime(self):
        original = Path.read_bytes
        def read(path):
            raw = original(path)
            return b"changed\n" if ".runtime-" in str(path) and path.name == "pr_title.py" else raw
        with mock.patch.object(Path, "read_bytes", read), self.assertRaises(worker.review.ReviewError):
            worker.install(self.root)
        self.assertEqual([], list((self.root/"runtime").iterdir()))
        self.commands.assert_not_called()

    def test_cli_passes_explicit_root_to_install_and_once(self):
        for flag, target in (("--install", "install"), ("--once", "once")):
            with self.subTest(flag=flag), mock.patch.object(sys, "argv", ["worker", flag, "--root", str(self.root)]), \
                    mock.patch.object(worker, target, return_value="done") as action, mock.patch("builtins.print"), \
                    mock.patch.object(worker.os, "umask"):
                self.assertEqual(0, worker.main())
                action.assert_called_once_with(self.root)
        self.commands.assert_not_called()

    def test_runtime_imports_and_deferred_style_check_work_without_source_or_pythonpath(self):
        _, config, runtime = self.installed()
        self.source.rename(self.home/"unavailable-source")
        probe = self.home/"probe.py"
        probe.write_text('''import importlib
import json
from pathlib import Path
import runpy
import sys
from unittest import mock

runtime, root = map(Path, sys.argv[1:])
with mock.patch("subprocess.run", side_effect=AssertionError("external command")):
    with mock.patch.object(sys, "argv", ["worker", "--help"]):
        try:
            runpy.run_path(str(runtime/"tools/study_review_worker.py"), run_name="__main__")
        except SystemExit as error:
            assert error.code == 0
    worker = importlib.import_module("tools.study_review_worker")
    data = {"head": "a"*40}
    result = {"summary": "변경한 입력 처리를 확인했음.", "findings": [], "questions": []}
    assert "검토한 커밋" in worker.body_for(data, result, "marker", "APPROVE")
    worker.save(root/"probe.json", {"saved": True})
    assert json.loads((root/"probe.json").read_text()) == {"saved": True}
    assert worker.valid_title("fix(model): 입력 수정")
    names = ("tools", "learning_data", "tools.study_review_worker", "tools.learning_review",
             "tools.study_checks", "tools.pr_title", "tools.check_style", "learning_data.privacy")
    origins = {name: str(Path(importlib.import_module(name).__file__).resolve()) for name in names}
    assert Path(importlib.import_module("tools.check_style").ROOT) == runtime
    print(json.dumps(origins))
''', encoding="utf-8")
        result = self.native_run([*config["ProgramArguments"][:3], str(probe), str(runtime), str(self.root)],
                                 cwd=runtime, env={**os.environ, "PYTHONPATH": str(self.home/"unavailable-source")},
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)
        origins = json.loads(result.stdout.splitlines()[-1])
        for name, path in origins.items():
            expected = runtime/(name.replace(".", "/")+("/__init__.py" if name in {"tools", "learning_data"} else ".py"))
            self.assertEqual(expected, Path(path))
        self.assertEqual([], list(runtime.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
