# -*- coding: utf-8 -*-
"""풀이·사용 안내만 바뀌었으면 화면 전체 검사를 생략함. 비교가 불확실하면 실행함."""
import os
import subprocess

GUIDE_READMES = frozenset(("README.md", "gui/README.md", "ai/README.md", "problems/README.md",
                          "journey/README.md", "web/README.md", "tools/README.md",
                          "submissions/README.md", "learning_server/README.md", "docs/README.md",
                          "docs/GIT_GUIDE.md", "docs/roadmap/README.md"))


def needs_gui(paths):
    return not paths or any(not path.startswith("submissions/") and path not in GUIDE_READMES for path in paths)


def main():
    run = True
    base, head = os.environ.get("SCOPE_BASE"), os.environ.get("SCOPE_HEAD")
    if base and head:
        try:
            result = subprocess.run(["git", "diff", "--no-renames", "--name-only", "-z", base, head, "--"],
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
