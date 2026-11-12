# -*- coding: utf-8 -*-
"""개발 PR 제목을 신뢰한 기본 브랜치의 규칙으로 확인함."""
import os
import re
import sys
import json
import subprocess

PATTERN = r"(?:feat|fix|docs|refactor|test|chore|style|perf|build|ci)(?:\([A-Za-z0-9_./-]+\))?: \S[^\r\n]*"


def valid(title):
    return isinstance(title, str) and len(title) <= 120 and re.fullmatch(PATTERN, title) is not None


def main():
    title = os.environ.get("PR_TITLE", "")
    if "--publish-status" in sys.argv:
        sha = os.environ.get("PR_HEAD_SHA", "")
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            return 1
        payload = {"state": "success" if valid(title) else "failure", "context": "PR 제목",
                   "description": "제목 형식 통과" if valid(title) else "종류(범위): 변경 내용 형식으로 수정해 주세요."}
        subprocess.run(["gh", "api", "repos/WaterMinCho/programming-study/statuses/"+sha, "--method", "POST", "--input", "-"],
                       input=json.dumps(payload), text=True, capture_output=True, check=True, timeout=20)
    if valid(title):
        print("PR 제목 형식을 확인했습니다.")
        return 0
    print("PR 제목은 docs(model): 공통 입력 확인처럼 종류(범위): 변경 내용으로 적어 주세요.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
