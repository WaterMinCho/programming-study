# -*- coding: utf-8 -*-
"""풀이 폴더만 바뀌었을 때 화면 전체 검사를 생략함. 비교가 불확실하면 실행함."""
import os
import subprocess


def needs_gui(paths):
    return not paths or any(not path.startswith("submissions/") for path in paths)


def main():
    run = True
    base, head = os.environ.get("SCOPE_BASE"), os.environ.get("SCOPE_HEAD")
    if base and head:
        try:
            result = subprocess.run(["git", "diff", "--name-only", "-z", base, head, "--"],
                                    check=True, capture_output=True, timeout=15)
            paths = [value.decode("utf-8", errors="surrogateescape") for value in result.stdout.split(b"\0") if value]
            run = needs_gui(paths)
        except (OSError, subprocess.SubprocessError):
            pass
    value = "true" if run else "false"
    print("화면 검사 실행: %s" % value)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("gui=%s\n" % value)


if __name__ == "__main__":
    main()
