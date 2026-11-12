# -*- coding: utf-8 -*-
"""현재 판의 검사·리뷰 완료 조건과 중복 키를 확인함."""
import copy
import unittest

from tools import study_checks as checks

SHA = "a" * 40
PR = {"number": 123, "user": {"login": "WaterMinCho"}, "head": {"sha": SHA},
      "base": {"sha": "b" * 40}, "draft": False, "mergeable": True, "mergeable_state": "clean"}


def job(name, state="SUCCESS", **fields):
    return {"name": name, "status": "COMPLETED", "conclusion": state, **fields}


def review(state="APPROVED", **fields):
    return {"id": 5, "user": {"login": "WaterMinCho"}, "commit_id": SHA, "state": state,
            "submitted_at": "2026-11-12T01:00:00Z", **fields}


def base_checks():
    return [job("필수 검사"), {"context": "PR 제목", "state": "SUCCESS"}, job("문장 검사")]


class ChecksTest(unittest.TestCase):
    def setUp(self):
        self.pr = copy.deepcopy(PR)
        self.rows = base_checks()

    def state(self, reviews=(), expected=("필수 검사", "PR 제목", "문장 검사")):
        return checks.checks_state(self.pr, self.rows, reviews, expected)

    def team(self, state="SUCCESS"):
        self.pr["user"]["login"] = "michae18"
        self.rows.append({"context": checks.REVIEW_CONTEXT, "state": state})

    def test_general_pr_needs_no_own_approval(self):
        self.assertTrue(self.state()["ready"])

    def test_every_missing_required_check_waits(self):
        for index in range(3):
            with self.subTest(index=index):
                self.rows = base_checks()
                self.rows.pop(index)
                self.assertIsNone(self.state())

    def test_title_waits_for_head_status_context_instead_of_base_job(self):
        self.rows = [job("필수 검사"), job("PR 제목 실행"), job("문장 검사")]
        self.assertIsNone(self.state())
        self.rows.append(job("PR 제목"))
        self.assertIsNone(self.state())
        self.rows.append({"context": "PR 제목", "state": "SUCCESS", "head_sha": SHA})
        self.assertTrue(self.state()["ready"])
        self.rows[1]["status"] = "IN_PROGRESS"
        self.assertTrue(self.state()["ready"])
        self.rows[-1]["head_sha"] = "c" * 40
        self.assertIsNone(self.state())

    def test_nonterminal_and_unknown_checks_wait(self):
        for status in ("QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED", "PENDING", "EXPECTED", "FUTURE"):
            with self.subTest(status=status):
                self.rows = base_checks()+[job("추가 검사", status=status)]
                self.assertIsNone(self.state())
        self.rows = base_checks()+[{"context": "추가 검사", "state": "PENDING"}]
        self.assertIsNone(self.state())

    def test_terminal_failures_finish_without_ready(self):
        for conclusion in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE", "STARTUP_FAILURE"):
            with self.subTest(conclusion=conclusion):
                self.rows = base_checks()+[job("추가 검사", conclusion)]
                self.assertFalse(self.state()["passed"])

    def test_mandatory_neutral_and_skipped_do_not_pass(self):
        for conclusion in ("NEUTRAL", "SKIPPED"):
            self.rows[0] = job("필수 검사", conclusion)
            self.assertFalse(self.state()["passed"])

    def test_unselected_conditional_jobs_may_be_skipped(self):
        self.rows += [job("기능·자료 검사", "SKIPPED"), job("화면 테스트", "SKIPPED")]
        self.assertTrue(self.state(expected=("필수 검사", "PR 제목", "문장 검사", "기능·자료 검사", "화면 테스트"))["passed"])

    def test_old_head_and_notification_records_do_not_complete_checks(self):
        self.rows[0]["head_sha"] = "c" * 40
        self.assertIsNone(self.state())
        self.rows = base_checks()+[{"context": checks.NOTIFY_CONTEXT, "state": "PENDING"}, job("notify", "FAILURE")]
        self.assertTrue(self.state()["ready"])

    def test_duplicate_terminal_checks_use_latest_in_either_order(self):
        old = job("문장 검사", "FAILURE", startedAt="2026-11-12T00:00:00Z")
        new = job("문장 검사", startedAt="2026-11-12T01:00:00Z")
        for rows in ([old, new], [new, old]):
            self.rows = base_checks()[:2]+rows
            self.assertTrue(self.state()["ready"])

    def test_duplicate_checks_wait_when_new_attempt_is_queued_or_order_unknown(self):
        self.rows.append(job("문장 검사", status="QUEUED"))
        self.assertIsNone(self.state())
        self.rows[-1] = job("문장 검사", "FAILURE")
        self.assertIsNone(self.state())

    def test_queued_check_without_start_time_does_not_reuse_old_success(self):
        self.rows[-1]["startedAt"] = "2026-11-12T01:00:00Z"
        self.rows.append(job("문장 검사", status="QUEUED", startedAt="0001-01-01T00:00:00Z"))
        self.assertIsNone(self.state())

    def test_old_pending_status_does_not_override_new_completion(self):
        self.rows += [{"context": "추가 검사", "state": "PENDING", "createdAt": "2026-11-12T00:00:00Z"},
                      {"context": "추가 검사", "state": "SUCCESS", "createdAt": "2026-11-12T01:00:00Z"}]
        self.assertTrue(self.state()["passed"])

    def test_skipped_whole_workflow_is_not_a_success(self):
        self.rows.append(job("CI 전체 실행", "SKIPPED"))
        self.assertFalse(self.state()["passed"])

    def test_each_teammate_waits_for_current_review_and_status(self):
        for author in checks.AUTHORS:
            with self.subTest(author=author):
                self.pr["user"]["login"] = author.upper()
                self.rows = base_checks()
                self.assertIsNone(self.state([review()]))
                self.rows.append({"context": checks.REVIEW_CONTEXT, "state": "SUCCESS"})
                self.assertIsNone(self.state())
                self.assertIsNone(self.state([review(commit_id="c" * 40)]))
                self.assertTrue(self.state([review()])["ready"])

    def test_review_status_pending_or_tool_error_does_not_finish(self):
        for status in ("PENDING", "ERROR"):
            self.rows = base_checks()
            self.team(status)
            self.assertIsNone(self.state([review()]))

    def test_current_feedback_finishes_without_approval(self):
        self.team("FAILURE")
        for state in ("CHANGES_REQUESTED", "COMMENTED"):
            result = self.state([review(state)])
            self.assertFalse(result["ready"])
            self.assertFalse(result["approved"])

    def test_latest_review_overrides_old_approval_even_if_input_reversed(self):
        self.team()
        old = review()
        new = review("CHANGES_REQUESTED", id=6, submitted_at="2026-11-12T02:00:00Z")
        for rows in ([old, new], [new, old]):
            self.assertFalse(self.state(rows)["approved"])

    def test_dismissal_and_pending_review_do_not_reuse_approval(self):
        self.team()
        for state in ("DISMISSED", "PENDING"):
            self.assertIsNone(self.state([review(state)]))

    def test_unsubmitted_new_review_does_not_reuse_old_approval(self):
        self.team()
        self.assertIsNone(self.state([review(), review("PENDING", id=6, submitted_at=None)]))

    def test_later_comment_keeps_effective_approval_only_with_success_status(self):
        self.team()
        rows = [review(), review("COMMENTED", id=6, submitted_at="2026-11-12T02:00:00Z")]
        self.assertTrue(self.state(rows)["approved"])
        self.rows[-1]["state"] = "FAILURE"
        self.assertFalse(self.state(rows)["approved"])

    def test_status_for_previous_review_waits(self):
        self.team()
        self.rows[-1]["targetUrl"] = "https://github.com/review/4"
        self.assertIsNone(self.state([review(html_url="https://github.com/review/5")]))
        self.rows[-1].pop("targetUrl")
        self.rows[-1]["createdAt"] = "2026-11-12T00:00:00Z"
        self.assertIsNone(self.state([review()]))

    def test_another_reviewer_cannot_supply_the_team_review(self):
        self.team()
        self.assertIsNone(self.state([review(user={"login": "someone"})]))

    def test_mergeability_unknown_waits_even_after_failure(self):
        for mergeable, state in ((None, "unknown"), (True, "unknown"), (True, None)):
            self.pr.update(mergeable=mergeable, mergeable_state=state)
            self.rows[0] = job("필수 검사", "FAILURE")
            self.assertIsNone(self.state())

    def test_known_conflict_produces_feedback(self):
        self.pr.update(mergeable=False, mergeable_state="dirty")
        self.assertFalse(self.state()["ready"])

    def test_key_ignores_order_urls_and_identical_rerun(self):
        key = self.state()["key"]
        self.rows.reverse()
        self.rows[0]["detailsUrl"] = "https://github.com/run/another"
        self.assertEqual(key, self.state()["key"])
        self.pr["number"] += 1
        self.assertNotEqual(key, self.state()["key"])

    def test_key_changes_with_head_base_and_result_but_not_repeated_approval(self):
        key = self.state()["key"]
        self.pr["head"]["sha"] = "d" * 40
        self.assertNotEqual(key, self.state()["key"])
        self.pr = copy.deepcopy(PR)
        self.pr["base"]["sha"] = "e" * 40
        self.assertNotEqual(key, self.state()["key"])
        self.team()
        self.assertEqual(self.state([review()])["key"], self.state([review(id=6)])["key"])
        approved = self.state([review()])["key"]
        self.assertEqual(approved, self.state([review(), review("COMMENTED", id=6)])["key"])
        self.rows[-1]["state"] = "FAILURE"
        self.assertNotEqual(approved, self.state([review("CHANGES_REQUESTED")])["key"])


if __name__ == "__main__":
    unittest.main()
