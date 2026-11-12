# -*- coding: utf-8 -*-
"""풀이·사용 안내만 바뀌었으면 화면 전체 검사를 생략함. 비교가 불확실하면 실행함."""
import os
import subprocess

GUIDE_READMES = frozenset(("README.md", "gui/README.md", "ai/README.md", "problems/README.md",
                          "journey/README.md", "web/README.md", "tools/README.md",
                          "submissions/README.md", "learning_server/README.md", "docs/README.md",
                          "docs/GIT_GUIDE.md", "docs/roadmap/README.md", "docs/LEARNER_START.md",
                          "docs/STUDY_START.md", "docs/GUIDE_INDEX.md", "docs/PR_GUIDE.md",
                          "docs/LEARNING_REVIEW.md", "docs/SLACK_NOTIFICATIONS.md", "docs/LEGACY_RECORDS.md",
                          "docs/LEARNING_SERVER.md", "docs/LEARNING_DATA.md", "docs/LEARNING_PRIVACY.md",
                          "docs/API_SUBMISSIONS.md", "docs/ARCHITECTURE.md", "docs/LEARNING_MISSIONS.md",
                          "docs/LEARNING_WORKFLOW.md", "docs/LEARNING_STARTER.md", "docs/LEARNING_ROADMAP.md",
                          "docs/LEARNING_PILOT.md", "docs/LEARNING_READINESS.md"))


def needs_gui(paths):
    return selection(paths)["gui"]


def server_only(path):
    return path in ("tests/test_storage_capacity.py", "tests/test_sync_schedule.py", "tests/test_legacy_ai.py", ".github/workflows/learning-server.yml") or path.startswith("learning_server/") or path.startswith(("tests/test_learning_", "tests/test_private_submission", "tests/test_submission_api", "tests/test_legacy_transfer"))


def automation_only(path):
    return path in ("tools/ci_scope.py", "tools/check_style.py", "tests/test_style.py", "tools/pr_title.py", "tools/study_checks.py", "tools/study_review_worker.py", "tools/slack_summary.py", "tools/slack_notify.py", "tools/learning_review.py") or path.startswith(("tests/test_ci_scope", "tests/test_pr_title", "tests/test_study_", "tests/test_slack_", "tests/test_learning_review"))


def selection(paths):
    if not paths:
        return dict(bank=True, unit=True, gui=True, model=True)
    guide = lambda path: path in GUIDE_READMES or path.startswith("submissions/")
    work = [path for path in paths if not guide(path)]
    models = [path for path in work if path.startswith("experiments/")]
    other = [path for path in work if path not in models]
    server = lambda path: server_only(path) or path in ("submission_api.py", "aiprep/privacy.py", "aiprep/sharing.py")
    return dict(bank=any(not server(path) and not automation_only(path) and not path.startswith("docs/") for path in other),
                unit=bool(other), gui=any(not server_only(path) and not automation_only(path) for path in other),
                model=any(path.endswith(".py") for path in models))


def main():
    run = True
    selected = selection([])
    base, head = os.environ.get("SCOPE_BASE"), os.environ.get("SCOPE_HEAD")
    if base and head:
        try:
            result = subprocess.run(["git", "diff", "--no-renames", "--name-only", "-z", base, head, "--"],
                                    check=True, capture_output=True, timeout=15)
            paths = [value.decode("utf-8", errors="surrogateescape") for value in result.stdout.split(b"\0") if value]
            selected = selection(paths)
            run = selected["gui"]
        except (OSError, subprocess.SubprocessError):
            pass
    value = "true" if run else "false"
    print("화면 검사 실행: %s" % value)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("gui=%s\n" % value)
            for name in ("bank", "unit", "model"):
                output.write("%s=%s\n" % (name, "true" if selected[name] else "false"))


if __name__ == "__main__":
    main()
