#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""그림 도구의 기준 그림. 던전 스크립트는 여기 쓰인 도구(칸·포인터·막대·숫자판·격자·괄호·빗금·표시)만 써서 그림 품질이 문제마다 갈리지 않게 함.

  python3 tools/journey_art/sample.py [DIR]    DIR(없으면 임시 폴더)에 0-1a.gif(3프레임)와 0-1b.png 를 쓰고 표를 찍음
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.journey_art.draw import figure, mid_x, shade  # noqa: E402

VALUES = [1, 2, 3, 5, 8, 13]  # 정렬된 값. 합이 10 이하인 쌍을 두 포인터로 셈
STEPS = [  # (l, r, 더한 쌍 수, 설명)
    (0, 5, 0, "합 14 가 10 을 넘어 r 을 왼쪽으로 당깁니다."),
    (0, 4, 4, "합 9 는 10 이하라 l 과 r 사이 4쌍을 셉니다."),
    (1, 4, 3, "l 을 오른쪽으로 옮기고 3쌍을 더합니다."),
]


@figure("0-1a", 560, 300)
def two_pointers(fig):
    total = 0
    for l, r, added, note in STEPS:
        c = fig.frame(1400)
        total += added
        ok = VALUES[l] + VALUES[r] <= 10
        c.text(20, 14, "정렬된 값에서 합이 10 이하인 쌍 세기", "comment", 13)
        marks = {i: shade("string", 0.5) for i in range(l + 1, r + 1)} if ok else {r: shade("missing", 0.75)}
        rects = c.cells(20, 70, VALUES, size=40, gap=8, marks=marks, index=0)
        c.pointer(mid_x(rects[l]), 70, "l")
        c.pointer(mid_x(rects[r]), 70, "r", "decorator")
        bars = c.bars(20, 240, VALUES, width=32, gap=16, height=90, marks={} if ok else {r: shade("builtin", 0.75)})
        c.highlight(bars[l], "def", width=1)
        c.highlight(bars[r], "decorator", width=1)
        c.number_board(360, 70, "l 값 + r 값", VALUES[l] + VALUES[r], "string" if ok else "missing")
        c.number_board(360, 130, "답", total)
        if added:
            c.tag(466, 142, "+%d" % added, "string")
        c.caption(note)


@figure("0-1b", 560, 260)
def prefix_table(fig):
    c = fig.frame()
    table = [[1, 3, 6, 10], [3, 8, 15, 24], [6, 15, 27, 42]]  # 2차원 누적합 S
    marks = {(r, col): shade("builtin", 0.5) for r in (1, 2) for col in (1, 2, 3)}
    marks.update({(0, col): shade("missing", 0.75) for col in (1, 2, 3)})
    marks.update({(r, 0): shade("missing", 0.75) for r in (1, 2)})
    marks[(0, 0)] = shade("def", 0.5)
    hatch = {key: shade("missing", 0.5) for key in marks if key != (0, 0) and 0 in key}  # 빼는 위 띠와 왼쪽 띠
    c.text(20, 14, "누적합 표에서 구간 합을 네 칸으로 구하기", "comment", 13)
    rects = c.grid(20, 50, table, size=36, gap=3, marks=marks, hatch=hatch)
    c.highlight(rects[2][3], "def")
    c.bracket(rects[0][1][0], rects[0][3][0] + 36, 50 + 3 * 39 - 3, "1~3열", below=True)
    board = c.number_board(300, 80, "구간 합", 27, "builtin")
    c.arrow(rects[2][3][0] + 36 + 4, rects[2][3][1] + 18, board[0] - 4, board[1] + board[3] / 2, "def")
    c.text(300, 140, "S[2][3] - S[0][3] - S[2][0] + S[0][0]", "ink", 13, mono=True)
    c.text(300, 160, "= 42 - 10 - 6 + 1 = 27", "ink", 13, mono=True)
    c.caption("큰 사각형에서 위 띠와 왼쪽 띠를 빼고 겹친 모서리를 더합니다.")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    out_dir = args[0] if args else tempfile.mkdtemp(prefix="journey_art_")
    from tools.journey_art import render
    return render.main(["sample", "--out", out_dir, "--check"])


if __name__ == "__main__":
    sys.exit(main())
