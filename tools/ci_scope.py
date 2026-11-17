# -*- coding: utf-8 -*-
"""풀이·사용 안내만 바뀌었으면 화면 전체 검사를 생략함. 비교가 불확실하면 실행함."""
import os
import re
import subprocess

GUIDE_READMES = frozenset(("README.md", "gui/README.md", "ai/README.md", "problems/README.md",
                          "journey/README.md", "web/README.md", "tools/README.md",
                          "submissions/README.md", "learning_server/README.md", "learning_data/README.md", "docs/README.md",
                          "docs/GIT_GUIDE.md", "docs/roadmap/README.md", "docs/LEARNER_START.md",
                          "docs/STUDY_START.md", "docs/GUIDE_INDEX.md", "docs/PR_GUIDE.md",
                          "docs/LEARNING_REVIEW.md", "docs/SLACK_NOTIFICATIONS.md", "docs/LEGACY_RECORDS.md",
                          "docs/LEARNING_SERVER.md", "docs/LEARNING_DATA.md", "docs/LEARNING_DATA_ACCESS.md", "docs/LEARNING_PRIVACY.md",
                          "docs/API_SUBMISSIONS.md", "docs/ARCHITECTURE.md", "docs/LEARNING_MISSIONS.md",
                          "docs/LEARNING_WORKFLOW.md", "docs/LEARNING_STARTER.md", "docs/LEARNING_ROADMAP.md", "docs/LEARNING_EXPERIMENT_TEMPLATE.md",
                          "docs/LEARNING_PILOT.md", "docs/LEARNING_READINESS.md", "docs/COLLECTOR_BACKUP.md"))

LAUNCHER_PATHS = frozenset(("start.bat", "start.command", "ROKEY.app/Contents/MacOS/ROKEY",
                           "tools/install_python.ps1", "tools/install_python_macos.sh",
                           "tests/test_windows_start.py", "tests/test_mac_start.py", "tests/test_windowed.py"))


def needs_gui(paths):
    return selection(paths)["gui"]


def model_path(path):
    parts = path.split("/")
    return ("\\" not in path and len(parts) >= 3 and parts[0] == "experiments" and
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", parts[1]) is not None and
            not any(part in ("", ".", "..") for part in parts))


def changed_paths(base, head):
    """main의 후속 커밋을 PR 변경에 섞지 않고 삭제·이동 전 경로도 보존함."""
    if not all(re.fullmatch(r"[0-9a-fA-F]{40}", value or "") and set(value) != {"0"} for value in (base, head)):
        raise ValueError("비교할 커밋을 확인해 주세요.")
    common = subprocess.run(["git", "merge-base", base, head], check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    result = subprocess.run(["git", "diff", "--no-renames", "--name-only", "-z", common, head, "--"],
                            check=True, capture_output=True, timeout=15)
    return [value.decode("utf-8", errors="surrogateescape") for value in result.stdout.split(b"\0") if value]


def server_only(path):
    return path in (".dockerignore", "tools/collector_backup.py", "tests/test_collector_backup.py", "tests/test_storage_capacity.py", "tests/test_sync_schedule.py", "tests/test_legacy_ai.py", ".github/workflows/learning-server.yml") or path.startswith("learning_server/") or path.startswith(("tests/test_learning_", "tests/test_private_submission", "tests/test_submission_api", "tests/test_legacy_transfer"))


def automation_only(path):
    if path in (".github/workflows/pr-title.yml", ".github/workflows/release-check.yml", "tools/slack_threads.py", "tools/server_incident_alerts.py",
                "tests/test_server_incident_alerts.py", ".github/workflows/server-incidents.yml"):
        return True
    return path in (".github/workflows/ci.yml", ".github/workflows/style.yml", ".github/workflows/slack-notify.yml", "tools/ci_scope.py", "tools/pr_checks.py", "tests/test_pr_checks.py", "tools/check_style.py", "tests/test_style.py", "tools/pr_title.py", "tools/study_checks.py", "tools/study_review_worker.py", "tools/slack_summary.py", "tools/slack_notify.py", "tools/learning_review.py") or path.startswith(("tests/test_ci_scope", "tests/test_pr_title", "tests/test_study_", "tests/test_slack_", "tests/test_learning_review"))


def terminal_launcher_only(path):
    return path in LAUNCHER_PATHS


def needs_launcher(paths):
    return not paths or any(terminal_launcher_only(path) for path in paths)


def needs_release_gui(paths):
    """실행기와 기존 경량 검사 대상만 함께 바뀐 경우에만 화면 매트릭스를 생략함."""
    return not needs_launcher(paths) or needs_gui(paths)


def selection(paths):
    if not paths:
        return dict(bank=True, unit=True, gui=True, model=True)
    guide = lambda path: path in GUIDE_READMES or path.startswith("submissions/")
    work = [path for path in paths if not guide(path)]
    models = [path for path in work if model_path(path)]
    other = [path for path in work if path not in models]
    server = lambda path: server_only(path) or path in ("submission_api.py", "aiprep/privacy.py", "aiprep/sharing.py", "learning_data/submission.py", "learning_data/privacy.py", "learning_data/sharing.py")
    return dict(bank=any(not server(path) and not automation_only(path) and not terminal_launcher_only(path) and not path.startswith("docs/") for path in other),
                unit=bool(other), gui=any(not server_only(path) and not automation_only(path) and not terminal_launcher_only(path) and not
                                        (path.startswith("docs/") and path.endswith(".md")) for path in other),
                model=any(path.endswith(".py") for path in models))


def main():
    run = True
    launcher = release_gui = True
    selected = selection([])
    base, head = os.environ.get("SCOPE_BASE"), os.environ.get("SCOPE_HEAD")
    if base and head:
        try:
            paths = changed_paths(base, head)
            selected = selection(paths)
            run = selected["gui"]
            launcher = needs_launcher(paths)
            release_gui = needs_release_gui(paths)
            print("실제 변경 파일: %d개" % len(paths))
            print("모델 코드·설명: %d개, 공통 파일: %d개" % (sum(model_path(path) for path in paths), sum(not model_path(path) for path in paths)))
        except (OSError, ValueError, subprocess.SubprocessError):
            print("변경 범위를 확인하지 못해 제품 검사를 실행합니다.")
            pass
    value = "true" if run else "false"
    print("화면 검사 실행: %s" % value)
    print("문항=%s 기능=%s 모델구문=%s" % tuple(str(selected[name]).lower() for name in ("bank", "unit", "model")))
    print("실행기=%s 첫실행화면=%s" % (str(launcher).lower(), str(release_gui).lower()))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("gui=%s\n" % value)
            for name in ("bank", "unit", "model"):
                output.write("%s=%s\n" % (name, "true" if selected[name] else "false"))
            for name, enabled in (("launcher", launcher), ("release_gui", release_gui)):
                output.write("%s=%s\n" % (name, "true" if enabled else "false"))


if __name__ == "__main__":
    main()
