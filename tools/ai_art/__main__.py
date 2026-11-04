# -*- coding: utf-8 -*-
"""python -m tools.ai_art lNN [그림 이름...] [--bank DIR] [--manifest FILE]: 학습 노트 그림을 그려 assets/ 에 쓰고 manifest 를
고침. 출제자 컴퓨터의 numpy·matplotlib·Pillow 가 있는 파이썬으로 돌림. 한도를 넘은 그림이 있으면 1.
--record 면 그리지 않고 스크립트가 이미 그린 assets/ 의 그림을 manifest 에 적음(자기 명령줄로 그리는 스크립트용, 표준 라이브러리만)."""
import argparse
import os
import sys

from tools.ai_art import ROOT, image_problems, record, render


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m tools.ai_art")
    parser.add_argument("page", help="학습 노트 id(l05)")
    parser.add_argument("names", nargs="*", help="이 그림만 그림")
    parser.add_argument("--bank", default=os.path.join(ROOT, "ai"))
    parser.add_argument("--manifest")
    parser.add_argument("--record", action="store_true", help="그리지 않고 assets/ 의 그림을 manifest 에 적음")
    opts = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if opts.record:
        bank_dir = os.path.abspath(opts.bank)
        done = record(opts.page, bank_dir, opts.manifest)
        bad = 0
        for rel in done:
            problems = image_problems(os.path.join(bank_dir, *rel.split("/")))
            print(rel)
            for problem in problems:
                print("  문제: %s" % problem)
            bad += len(problems)
        print("manifest 에 그림 %d장을 적었습니다. 문제 %d개" % (len(done), bad))
        return 1 if bad else 0
    rows = render(opts.page, opts.names, os.path.abspath(opts.bank), opts.manifest)
    bad = 0
    for row in rows:
        print("%s  %s" % (row["name"], os.path.relpath(row["path"], ROOT)))
        for problem in row["problems"]:
            print("  문제: %s" % problem)
            bad += 1
    print("그림 %d장, 문제 %d개" % (len(rows), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
