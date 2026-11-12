#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub Actions에서 채점 결과와 과목별 학습 기록을 남김.

PR 에서는 풀이가 바뀐 사람만 채점해 report.md 로 남김. 풀이 PR 이 자기 폴더(submissions/<ID>/) 밖을 건드리면 실패함.
main 푸시에서는 전체 현황판을 남김.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import study  # noqa: E402
import adaptive  # noqa: E402

NO_REPORT = "이 PR 에서 바뀐 풀이 중에 채점할 것이 없습니다.\n"


def changed_files(base_ref):
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "diff", "--name-only", "origin/%s...HEAD" % base_ref],
        cwd=study.ROOT, check=True, stdout=subprocess.PIPE,
    ).stdout.decode("utf-8")
    return [line for line in out.splitlines() if line.strip()]


def main():
    # PR 이면 GITHUB_BASE_REF, [제출] 버튼이 올린 study/<ID> 브랜치면 워크플로가 STUDY_BASE_REF 를 줌
    base_ref = os.environ.get("GITHUB_BASE_REF") or os.environ.get("STUDY_BASE_REF")
    problems = []
    if base_ref:
        files = changed_files(base_ref)
        candidates = {f.split("/")[1] for f in files if f.startswith("submissions/") and f.count("/") >= 2}
        users = sorted(user for user in candidates if study.USER_RE.fullmatch(user))
        if len(users) != len(candidates):
            problems.append("학습자 ID의 형식을 확인하세요.")
        others = [f for f in files if not f.startswith("submissions/")]
        if len(users) > 1:
            problems.append("한 PR 에는 한 사람의 풀이만 담아 주세요: " + ", ".join(users))
        if users and others:
            problems.append("풀이 PR 에서는 `submissions/<내 ID>/` 밖의 파일을 바꿀 수 없습니다: " + ", ".join(others[:5]))
        parts = []
        if not users:
            parts.append("이 PR 에는 풀이(submissions/) 변경이 없습니다.\n")
        for user in users:
            if not os.path.isdir(os.path.join(study.SUBMISSIONS_DIR, user)):
                continue
            parts.append(adaptive.user_analysis_markdown(user))
            try:
                if study.started_sets(user):
                    # 기존 세트의 채점은 유지하고 상태 표시는 글로 옮김. 원시 채점 로그는 내보내지 않음.
                    graded = study.render_markdown(user, study.grade_user(user))
                    parts.append(graded.replace(chr(0x2705), "통과").replace(chr(0x2014), "미통과"))
            except (OSError, ValueError, KeyError, TypeError):
                parts.append("### 기존 세트의 채점 결과를 확인하세요\n\n기존 세트 채점은 확인 불가 상태입니다. 세트와 제출 파일을 확인한 뒤 다시 채점하세요.\n")
        report = "\n".join(parts)
        if not report.strip():  # 풀이 폴더를 지운 PR에서도 비어 있지 않은 본문을 남김
            report = NO_REPORT
    else:
        report, shortages = adaptive.team_analysis_markdown()
        if shortages:  # 워크플로가 shortage.md 로 출제 요청 이슈를 만들거나 갱신함
            study.write_text(os.path.join(study.ROOT, "shortage.md"), adaptive.shortage_request_markdown(shortages, adaptive.catalog()))

    if problems:
        report = "### PR 규칙 확인\n\n" + "\n".join("- " + p for p in problems) + "\n\n" + report
    study.write_text(os.path.join(study.ROOT, "report.md"), report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    print(report)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
