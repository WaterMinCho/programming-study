# -*- coding: utf-8 -*-
"""현재 PR의 검사와 리뷰가 모두 끝난 결과만 Slack에 한 번 전송함."""
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import sys
import time
from urllib.request import Request
from urllib.error import HTTPError

from tools.slack_notify import GitHub, REPO, WEB, RELAY, WORKFLOWS, association, card, development, endpoint, metadata, plain, read_url, send
from tools.study_checks import AUTHORS, checks_state, NOTIFY_CONTEXT
from tools.ci_scope import model_path
from tools.slack_threads import DailyThreads

SERVER_PATHS = ("learning_server/**", "learning_data/**", ".dockerignore", "tests/test_project_structure.py", "aiprep/collection.py", "aiprep/sharing.py", "aiprep/privacy.py", "aiprep/sync_schedule.py", "submission_api.py", "tests/test_submission_api.py",
                "tests/test_learning_privacy.py", "tests/test_private_submission.py", "tests/test_learning_server.py", "tests/test_team_access.py", "tests/test_identity.py", "tests/test_learning_sample.py", "tests/test_learning_starter.py", "tests/test_learning_operations.py", "tests/test_storage_capacity.py", "tests/test_sync_schedule.py", "tests/test_legacy_ai.py", "tests/test_legacy_transfer.py", ".github/workflows/learning-server.yml")
JOURNEY_PATHS = ("dungeons/**", "journey/**", "study.py", "tools/verify_journey.py", "tools/journey_seal.py", "tools/journey_art/**",
                 "tests/test_journey_*.py", "tests/journey_bank/**", ".github/workflows/journey.yml")
RELEASE = ".github/workflows/release-check.yml"
RELEASE_PATHS = ("tools/check_release.py", RELEASE, "bootstrap.py", "gitflow.py", "start.bat", "start.pyw", "gui/app.py", "gui/icon.py",
                 "gui/launcher_shortcut.py", "gui/navigation.py", "gui/career_*.py", "gui/paper_explainer.py", "gui/video_viewer.py", "career/**", "tools/video_setup.py", "tests/test_gui_career*.py", "tests/test_gui_paper_explainer.py", "tests/test_gui_video_player.py", "gui/identity.py", "gui/dialogs.py", "gui/dialog_layout.py", "gui/privacy.py", "gui/auto_submission.py", "gui/submission_setup.py", "gui/ai_data.py", "gui/onboarding.py", "gui/team_dashboard.py", "gui/window.py", "gui/workspace.py", "gui/theme.py", "gui/settings_menu.py", "gui/ai_learn.py", "gui/ai_home.py", "gui/hub_page.py", "gui/motion.py", "tests/test_gui_settings_menu.py", "tests/test_gui_local_identity_guard.py", "tests/test_gui_refresh.py", "learning_data/identity.py", "gui/ai_mock.py", "gui/kit.py", "tests/test_gui_ai_mock.py", "tests/test_gui_ai_courses.py", "tests/test_gui_navigation.py", "tests/test_gui_identity.py", "tests/test_gui_dialogs.py", "tests/test_gui_auto_submission.py", "tests/test_gui_submission.py", "tests/test_gui_onboarding.py", "tests/test_launcher_shortcut.py", "tests/test_gui_launcher.py")


def touches(files, patterns):
    return any(fnmatchcase(path, pattern) for path in files for pattern in patterns)


def release_expected(files, pr=None):
    if not touches(files, RELEASE_PATHS):
        return False
    if pr is None:
        return True
    return not pr["head"]["ref"].startswith("study/")


class Client(GitHub):
    def post(self, path, payload):
        if not path.startswith(endpoint("statuses/")):
            raise ValueError("알림 상태 경로를 확인해 주세요.")
        return json.loads(read_url(Request("https://api.github.com"+path, data=json.dumps(payload).encode(), method="POST",
                                          headers={"Authorization": "Bearer "+self.token, "Accept": "application/vnd.github+json",
                                                   "Content-Type": "application/json", "User-Agent": "study-notifications"})))


def rollup(pr):
    import subprocess
    completed = subprocess.run(["gh", "pr", "view", str(pr["number"]), "--repo", REPO, "--json", "headRefOid,statusCheckRollup"],
                               check=True, capture_output=True, text=True, timeout=20)
    result = json.loads(completed.stdout)
    return result if result["headRefOid"] == pr["head"]["sha"] else None


def required_names(files, pr=None):
    names = ["필수 검사", "PR 제목", "문장 검사", "변경 범위", "기능·자료 검사", "화면 테스트"]
    if any(model_path(path) and path.endswith(".py") for path in files):
        names.append("모델 제출 검사")
    if touches(files, SERVER_PATHS):
        names += ["운영 경로 (ubuntu-latest)", "운영 경로 (windows-latest)"]
    if touches(files, JOURNEY_PATHS):
        names += ["바뀐 곳 보기", "여정 문제 검증", "여정 JS 검증 (Node 22)"]
    if release_expected(files, pr):
        names += ["새 설치와 작은 창 (배율 1)", "새 설치와 작은 창 (배율 1.5)"]
    return names


def workflow_checks(pr, files, github):
    """아직 개별 검사가 등록되지 않은 실행도 완료 전까지 기다림."""
    paths = [("ci.yml", "pull_request"), ("style.yml", "pull_request")]
    if touches(files, SERVER_PATHS):
        paths.append(("learning-server.yml", "pull_request"))
    if touches(files, JOURNEY_PATHS):
        paths.append(("journey.yml", "pull_request"))
    if release_expected(files, pr):
        paths.append(("release-check.yml", "pull_request"))
    checks = []
    for path, event in paths:
        data = github.get(endpoint("actions/workflows/%s/runs?event=%s&head_sha=%s&per_page=100" % (path, event, pr["head"]["sha"])))
        runs = [run for run in data["workflow_runs"] if run["head_sha"] == pr["head"]["sha"]
                and run.get("event") == event and run.get("head_branch") == pr["head"]["ref"]
                and (run.get("head_repository") or {}).get("full_name") == (pr["head"].get("repo") or {}).get("full_name")]
        if not runs:
            return None
        run = max(runs, key=lambda row: (row["id"], row["run_attempt"]))
        if run["status"] != "completed" or not run.get("conclusion"):
            return None
        checks.append({"name": run["name"]+" 전체 실행", "status": "COMPLETED", "conclusion": run["conclusion"].upper(),
                       "detailsUrl": run["html_url"]})
    return checks


def same_pr(before, after):
    return (after["state"] == "open" and not after["draft"] and before["head"]["sha"] == after["head"]["sha"]
            and before["base"]["sha"] == after["base"]["sha"] and before["title"] == after["title"]
            and before.get("body") == after.get("body"))


def aggregate(number, github):
    pr = github.get(endpoint("pulls/%d" % number))
    if pr["state"] != "open" or pr["draft"] or not development(pr, github):
        return None
    files = [path for row in github.pages(endpoint("pulls/%d/files" % number)) for path in (row["filename"], row.get("previous_filename", row["filename"]))]
    workflows = workflow_checks(pr, files, github)
    if workflows is None:
        return None
    checks = rollup(pr)
    if checks is None:
        return None
    reviews = list(github.pages(endpoint("pulls/%d/reviews" % number)))
    current = github.get(endpoint("pulls/%d" % number))
    if not same_pr(pr, current):
        return None
    pr = current
    result = checks_state(pr, checks["statusCheckRollup"]+workflows, reviews, required_names(files, pr))
    if result is None:
        return None
    title = "머지 준비 완료" if result["ready"] else "확인 필요"
    team = pr["user"]["login"].lower() in AUTHORS
    details = ["검사 통과" if result["passed"] else "검사: " + plain(" · ".join(result["failed"]), 300)]
    if team:
        details.append("검토 완료" if result["approved"] else "피드백 확인 필요")
    details.append("운영자 확인 후 머지" if result["ready"] else "PR에서 남은 조건 확인")
    payload = card(title, " · ".join(details), pr, links=[("PR 보기", pr["html_url"])])
    return pr, result, payload


def candidates(event_name, event, github):
    if event.get("repository", {}).get("full_name") != REPO:
        return []
    if event_name == "workflow_dispatch":
        return [row["number"] for row in github.pages(endpoint("pulls?state=open&base=main"))]
    if event_name == "status":
        if event.get("context") != "스터디 코드 검토":
            return []
        sha = event["sha"]
        return [row["number"] for row in github.get(endpoint("commits/%s/pulls?per_page=100" % sha)) if row["head"]["sha"] == sha]
    if event_name != "workflow_run" or event.get("action") != "completed":
        return []
    run = github.get(endpoint("actions/runs/%d/attempts/%d" % (event["workflow_run"]["id"], event["workflow_run"]["run_attempt"])))
    if (run.get("repository", {}).get("full_name") != REPO or run["status"] != "completed"
            or (run["id"], run["run_attempt"]) != (event["workflow_run"]["id"], event["workflow_run"]["run_attempt"])):
        return []
    path = run["path"].split("@")[0]
    if path == RELAY:
        if run.get("conclusion") != "success":
            return []
        number = metadata(run, github)["pr"]
        pr = github.get(endpoint("pulls/%d" % number))
        return [number] if pr["head"]["sha"] == run["head_sha"] else []
    if path not in WORKFLOWS and path not in {".github/workflows/pr-title.yml", RELEASE}:
        return []
    if run.get("event") not in {"pull_request", "pull_request_target"}:
        return []
    if path == ".github/workflows/pr-title.yml" and run["event"] == "pull_request_target":
        # 대상 브랜치에서 실행한 제목 검사는 run의 SHA 대신 연결된 PR의 head를 대조함.
        return [row["number"] for row in run.get("pull_requests", [])
                if github.get(endpoint("pulls/%d" % row["number"]))["head"]["sha"] == row["head"]["sha"]]
    return [row["number"] for row in association(run, github) if row["head"]["sha"] == run["head_sha"]]


def deliver(pr, result, payload, github, webhook, threader=None):
    current = aggregate(pr["number"], github)
    if current is None or not same_pr(pr, current[0]) or current[1]["key"] != result["key"]:
        return False
    pr, result, payload = current
    key = result["key"]
    states = list(github.pages(endpoint("commits/%s/statuses" % pr["head"]["sha"])))
    latest_states = {}
    for row in states:
        if row["context"] == NOTIFY_CONTEXT:
            latest_states.setdefault(row.get("description", "").split(":")[-1], row)
    if any(row.get("description", "").startswith("sending:")
           and (not row.get("target_url") or row["target_url"] == pr["html_url"]) for row in latest_states.values()):
        return False
    prior = [row for row in states if row["context"] == NOTIFY_CONTEXT
             and row.get("description") in {"sending:"+key, "sent:"+key, "failed:"+key}]
    if any(row.get("description") == "sent:"+key for row in prior):
        return False
    if prior and prior[0].get("description") != "failed:"+key:
        return False
    location = endpoint("statuses/"+pr["head"]["sha"])
    # 알림 기록이 머지 상태를 막지 않도록 success로 쓰고 전송 결과는 설명으로 구분함.
    github.post(location, {"state": "success", "context": NOTIFY_CONTEXT, "description": "sending:"+key, "target_url": pr["html_url"]})
    refreshed = github.get(endpoint("pulls/%d" % pr["number"]))
    if (not same_pr(pr, refreshed) or refreshed.get("mergeable") != pr.get("mergeable")
            or refreshed.get("mergeable_state") != pr.get("mergeable_state")):
        github.post(location, {"state": "success", "context": NOTIFY_CONTEXT, "description": "failed:"+key})
        return False
    try:
        if threader is not None:
            threader.send(payload)
        else:
            send(payload, webhook)
    except (HTTPError, ValueError):
        # 명시적인 거절만 재시도하며 수신 여부를 모르는 연결 오류는 보류함.
        github.post(location, {"state": "success", "context": NOTIFY_CONTEXT, "description": "failed:"+key})
        raise
    github.post(location, {"state": "success", "context": NOTIFY_CONTEXT, "description": "sent:"+key, "target_url": pr["html_url"]})
    return True


def main():
    webhook = os.environ.get("SLACK_STUDY_WEBHOOK_URL", "")
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        event_name = os.environ["GITHUB_EVENT_NAME"]
        github = Client(os.environ["GH_TOKEN"])
        dry = os.environ.get("SLACK_DRY_RUN") == "1"
        threader = None
        if not dry and os.environ.get("SLACK_STUDY_DAILY_THREADS") == "1":
            threader = DailyThreads(github, os.environ.get("SLACK_STUDY_BOT_TOKEN", ""),
                                    os.environ.get("SLACK_STUDY_CHANNEL_ID", ""),
                                    os.environ.get("SLACK_STUDY_THREAD_ANCHOR", ""))
        for number in sorted(set(candidates(event_name, event, github))):
            final = None
            for attempt in range(3):
                final = aggregate(number, github)
                if final:
                    break
                if attempt < 2:
                    time.sleep(2)
            if final is None:
                print("PR #%d: 전체 검사 또는 현재 커밋의 리뷰를 기다립니다." % number)
                continue
            if dry:
                print(json.dumps(final[2], ensure_ascii=False))
            elif webhook or threader is not None:
                print("종합 결과 알림을 보냈습니다." if deliver(*final, github, webhook, threader) else "이미 알린 결과이거나 상태가 바뀌어 전송을 보류했습니다.")
        return 0
    except Exception:
        print("최종 알림을 확인하지 못했습니다. 인증 값은 로그에 남기지 않았습니다.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
