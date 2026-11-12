# -*- coding: utf-8 -*-
"""모델 Python의 구문과 공통 파일의 문장만 확인하며 제출 코드는 실행하지 않음."""
import argparse
import os
from pathlib import Path
import subprocess
import tokenize

from tools import check_style
from tools.ci_scope import changed_paths, model_path


def model(paths, root=None):
    root = Path(root or Path.cwd()).resolve()
    checked = 0
    for name in paths:
        if not model_path(name) or not name.endswith(".py"):
            continue
        path = root / name
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("일반 Python 파일을 지정해 주세요: " + name)
        try:
            with tokenize.open(path) as stream:
                source = stream.read()
            compile(source, name, "exec", dont_inherit=True)
        except SyntaxError as error:
            raise ValueError("%s:%s 구문 오류: %s" % (name, error.lineno or 1, error.msg)) from None
        except RecursionError:
            raise ValueError("너무 깊게 중첩된 모델 코드입니다: " + name) from None
        checked += 1
    print("바뀐 모델 Python 파일 %d개의 구문을 확인했습니다. 코드 실행·의존성 설치·모델 학습은 하지 않았습니다." % checked)
    return 0


def style(paths, title, body):
    common = [path for path in paths if not model_path(path)]
    if paths and not common:
        print("모델 코드·설명의 문장은 코드 검토에서 확인합니다. 프로그램 문서용 문장 규칙으로 차단하지 않습니다.")
        return 0
    targets = []
    root = Path.cwd().resolve()
    for name in check_style.select(common):
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("저장소 안의 일반 문서·코드 파일을 지정해 주세요: " + name)
        if path.is_file():
            targets.append(name)
    bad = check_style.main(targets) if targets else 0
    for name, fails in check_style.check_path("PR", commit=True, shown="PR 제목·본문", text=title + "\n\n" + body):
        for rule, where in fails:
            print("  X %s: %s  [%s]" % (rule, where, name))
        bad = bool(bad or fails)
    return int(bad)


def main():
    parser = argparse.ArgumentParser(description="바뀐 파일에 맞는 가벼운 PR 검사를 실행합니다.")
    parser.add_argument("kind", choices=("model", "style"))
    args = parser.parse_args()
    try:
        paths = changed_paths(os.environ.get("SCOPE_BASE"), os.environ.get("SCOPE_HEAD"))
        if args.kind == "model":
            return model(paths)
        return style(paths, os.environ.get("TITLE", ""), os.environ.get("BODY", ""))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("PR 검사 실패: %s" % error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
