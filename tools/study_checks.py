# -*- coding: utf-8 -*-
"""현재 PR 판의 검사·리뷰와 알림 중복 키를 계산함."""
import hashlib
import json

AUTHORS = frozenset(("michae18", "wamangdoo", "kimjs85529-a11y"))
REVIEW_CONTEXT = "스터디 코드 검토"
NOTIFY_CONTEXT = "스터디 알림 기록"
EXCLUDED = frozenset((NOTIFY_CONTEXT, "relay", "notify", "PR 제목 실행"))
TERMINAL = frozenset(("SUCCESS", "FAILURE", "ERROR", "NEUTRAL", "SKIPPED", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE", "STARTUP_FAILURE"))


def completed_state(row):
    status = str(row.get("status") or "").upper()
    if status and status != "COMPLETED":
        return None
    value = str(row.get("conclusion") if status else row.get("state") or "").upper()
    return value if value in TERMINAL else None


def created_at(row):
    value = (row.get("createdAt") or row.get("created_at") or row.get("startedAt") or row.get("submitted_at") or "")
    return "" if value.startswith("0001-") else value


def latest(rows):
    """API의 배열 순서 대신 생성 시각과 번호로 최신 항목을 고름."""
    if all(isinstance(row.get("id"), int) for row in rows):
        return max(rows, key=lambda row: row["id"])
    return max(rows, key=lambda row: (created_at(row), row.get("id", 0)))


def checks_state(pr, checks, reviews, expected=("필수 검사", "PR 제목", "문장 검사")):
    """등록되지 않은 필수 검사와 오래된 리뷰를 완료로 세지 않음."""
    grouped = {}
    for row in checks:
        name = row.get("name") or row.get("context")
        if name and name not in EXCLUDED:
            if name == "PR 제목" and row.get("context") != "PR 제목":
                continue
            if row.get("head_sha", pr["head"]["sha"]) != pr["head"]["sha"]:
                continue
            grouped.setdefault(name, []).append(row)
    by_name = {}
    for name, rows in grouped.items():
        # 순서를 확인할 수 없는 재실행은 이전 성공으로 완료를 알리지 않음.
        if len({completed_state(row) for row in rows}) > 1 and any(
                not (created_at(row) or row.get("id")) for row in rows):
            return None
        by_name[name] = latest(rows)
        if completed_state(by_name[name]) is None:
            return None
    if not all(name in by_name for name in expected):
        return None
    values = []
    for name, row in by_name.items():
        state = completed_state(row)
        values.append((name, state, row.get("detailsUrl") or row.get("targetUrl") or ""))
    author = pr["user"]["login"].lower()
    review_key = None
    if author in AUTHORS:
        review = by_name.get(REVIEW_CONTEXT)
        if not review or completed_state(review) not in {"SUCCESS", "FAILURE"}:
            return None
        own = [row for row in reviews if row["user"]["login"].lower() == "watermincho"]
        current = latest(own) if own else None
        if (not current or current.get("commit_id") != pr["head"]["sha"]
                or current.get("state") not in {"APPROVED", "CHANGES_REQUESTED", "COMMENTED"}):
            return None
        target = review.get("targetUrl") or review.get("detailsUrl")
        if target and current.get("html_url") and target != current["html_url"]:
            return None
        at = review.get("createdAt") or review.get("created_at")
        if at and current.get("submitted_at") and at < current["submitted_at"]:
            return None
        decisions = [row for row in own if row.get("commit_id") == pr["head"]["sha"]
                     and row.get("state") in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}]
        approved = bool(decisions and latest(decisions)["state"] == "APPROVED" and completed_state(review) == "SUCCESS")
        review_key = (current.get("id"), current["state"])
    else:
        approved = True
    failed = [name for name, state, _ in values if not (state == "SUCCESS"
              or (name not in expected and not name.endswith(" 전체 실행") and state in {"NEUTRAL", "SKIPPED"})
              or (name in {"기능·자료 검사", "화면 테스트"} and state == "SKIPPED"))]
    passed = not failed
    if pr.get("mergeable") is None or pr.get("mergeable_state") in (None, "", "unknown"):
        return None
    ready = passed and approved and not pr.get("draft") and pr.get("mergeable") is True and pr.get("mergeable_state") == "clean"
    digest = hashlib.sha256(json.dumps([pr.get("number"), pr["head"]["sha"], pr.get("base", {}).get("sha"),
                                      sorted((name, state) for name, state, _ in values), review_key, bool(approved), ready], ensure_ascii=False).encode()).hexdigest()[:24]
    return {"ready": bool(ready), "passed": passed, "approved": bool(approved), "checks": values, "failed": failed, "key": digest}
