# -*- coding: utf-8 -*-
"""던전 2 「용암 평원」 해설 그림. 값은 각 문제의 입출력 예를 씀.

  python3 tools/journey_art/render.py d02 [--check]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.journey_art.draw import CAPTION_H, figure, mid_x, mid_y, shade  # noqa: E402

ADD, SUB, NEW = shade("string", 0.5), shade("missing", 0.5), shade("def", 0.5)  # 더하는 칸, 빼는 칸, 이번에 채우는 칸
DIM = shade("comment", 0.75)
OUT = shade("comment", 0.5)  # 격자 밖 칸의 빗금


def title(c, s):
    c.text(20, 14, s, "comment", 13)


def say(c, s):
    """캡션 한 줄. 띠를 넘치면 그리기 전에 멈춤."""
    width = c.text_size(s, 13)[0]
    if width > c.width - 24:
        raise ValueError("캡션이 %dpx 라 띠(%dpx)를 넘습니다: %s" % (width, c.width - 24, s))
    c.caption(s)


def sci(value):
    """3.1e10 꼴의 수를 해설과 같은 "3.1×10^10" 꼴로. 가수가 정수면 소수점을 뺌."""
    mant, exp = ("%.1e" % value).split("e")
    return "%s×10^%d" % (mant[:-2] if mant.endswith(".0") else mant, int(exp))


def obj(n):
    """정수 n 을 읽은 소리에 맞는 목적격 조사. 끝자리가 2, 4, 5, 9 면 받침이 없음."""
    return "를" if abs(n) % 10 in (2, 4, 5, 9) else "을"


def dashed(c, x1, y1, x2, y2, color_name="comment", dash=5, gap=4):
    """가로나 세로 점선."""
    length = abs(x2 - x1) + abs(y2 - y1)
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    t = 0
    while t < length:
        e = min(t + dash, length)
        c.line([(x1 + ux * t, y1 + uy * t), (x1 + ux * e, y1 + uy * e)], color_name, 1)
        t += dash + gap


def dashed_box(c, x, y, w, h, color_name="comment"):
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    for a, b in zip(corners, corners[1:]):
        dashed(c, a[0], a[1], b[0], b[1], color_name)


def legend(c, x, y, items, size=11):
    """[(채우는 색, 빗금 색 또는 None, 글자)] 를 가로로 늘어놓고 끝난 x 를 돌려줌."""
    for fill, hatch, label in items:
        c.box(x, y, 12, 12, fill=fill, outline="edge", radius=2)
        if hatch:
            c.hatch((x + 1, y + 1, 10, 10), hatch, step=4)
        x += 17 + c.text(x + 17, y + 6, label, "ink", size, anchor="lm")[0] + 14
    return x


def lines(c, x, y, rows, size=12, gap=19):
    """(글자, 색, mono) 줄들을 위에서 아래로 씀."""
    for s, color_name, mono in rows:
        c.text(x, y, s, color_name, size, mono=mono)
        y += gap


def span(rows, r1, c1, r2, c2):
    """grid() 가 돌려준 칸들에서 (r1, c1)~(r2, c2) 를 덮는 (x, y, w, h)."""
    x, y = rows[r1][c1][0], rows[r1][c1][1]
    right, bottom = rows[r2][c2][0] + rows[r2][c2][2], rows[r2][c2][1] + rows[r2][c2][3]
    return (x, y, right - x, bottom - y)


def prefix(values):
    out = [0]
    for v in values:
        out.append(out[-1] + v)
    return out


def table(grid):
    """0행·0열이 0 인 (N + 1) × (M + 1) 누적합 표."""
    n, m = len(grid), len(grid[0])
    s = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s[i][j] = s[i - 1][j] + s[i][j - 1] - s[i - 1][j - 1] + grid[i - 1][j - 1]
    return s


def corners(n, m, events):
    """(n + 2) × (m + 2) 네 모서리 표시 배열."""
    d = [[0] * (m + 2) for _ in range(n + 2)]
    for r1, c1, r2, c2, v in events:
        d[r1][c1] += v
        d[r1][c2 + 1] -= v
        d[r2 + 1][c1] -= v
        d[r2 + 1][c2 + 1] += v
    return d


def sweep(d, n, m, down=True):
    """표시 배열을 가로로 누적하고 down 이면 세로로도 누적해 1행 1열부터 n × m 을 돌려줌."""
    out = []
    for i in range(1, n + 1):
        acc, row = 0, []
        for j in range(1, m + 1):
            acc += d[i][j]
            row.append(acc)
        out.append(row)
    if down:
        for i in range(1, n):
            out[i] = [a + b for a, b in zip(out[i - 1], out[i])]
    return out


def sign_marks(rows, extra_row=None, extra_col=None):
    """0 이 아닌 값은 양수면 ADD, 음수면 SUB 로 칠하고 격자 밖 줄은 빗금."""
    marks, hatch = {}, {}
    for r, row in enumerate(rows):
        for col, value in enumerate(row):
            if value:
                marks[(r, col)] = ADD if value > 0 else SUB
            if r == extra_row or col == extra_col:
                hatch[(r, col)] = OUT
    return marks, hatch


def signed(value):
    return "+%d" % value if value > 0 else str(value)


def heads(c, rows, col_y, row_x, first=1):
    """grid() 칸 위에 열 번호, 왼쪽에 행 번호."""
    for k, rect in enumerate(rows[0]):
        c.text(mid_x(rect), col_y, str(first + k), "line_no", 10, mono=True, anchor="ms")
    for k, line in enumerate(rows):
        c.text(row_x, mid_y(line[0]), str(first + k), "line_no", 10, mono=True, anchor="rm")


TEMPS = [3, -1, 4, 1, -5]  # 2-1 예 1


@figure("2-1a", 560, 320)
def prefix_bars(fig):
    P = prefix(TEMPS)
    c = fig.frame()
    title(c, "예 1의 temps와 누적합 P, 질의 [2, 5]")
    step, x0, base, unit = 44, 70, 262, 120 / 7
    c.text(x0 + step - 10, 58, "temps", "comment", 12, mono=True, anchor="rm")
    rects = c.cells(x0 + step, 40, TEMPS, size=36, gap=step - 36, marks={i: shade("builtin", 0.5) for i in range(1, 5)}, index=1)
    c.bracket(rects[1][0], rects[4][0] + 36, 96, "2~5번 칸의 합 = -1", "builtin")
    marks = {i: shade("comment", 0.5) for i in range(len(P))}
    marks.update({1: "decorator", 5: "builtin"})
    bars = c.bars(x0 + 3, base, P, width=30, gap=step - 30, height=120, vmax=7, marks=marks)
    for i, rect in enumerate(bars):
        c.text(mid_x(rect), base + 5, "P[%d]" % i, "line_no", 10, mono=True, anchor="ma")
    top1, top5 = base - P[1] * unit, base - P[5] * unit
    right = bars[5][0] + bars[5][2]
    dashed(c, bars[1][0] + bars[1][2], top1, right + 14, top1, "decorator")
    c.arrow(right + 10, top1, right + 10, top5, "def", width=2, head=6)
    c.tag(right + 16, top1 - 2, "-1", "def", 11)
    board = c.number_board(400, 120, "P[5] - P[1]", -1, "def", w=110)
    c.text(mid_x(board), board[1] + board[3] + 16, "2 - 3 = -1", "ink", 13, mono=True, anchor="ma")
    say(c, "P[5] - P[1] = 2 - 3 = -1, 2번부터 5번 칸을 직접 더한 값과 같습니다.")


@figure("2-1b", 560, 300)
def missing_zero(fig):
    P = prefix(TEMPS)[1:]  # P[0] = 0 을 빼먹은 배열. 0번이 1번 칸까지의 합
    c = fig.frame()
    title(c, "P[0] 없이 만든 P에서 질의 [1, 3]을 P[r - 1] - P[l - 2]로 풀 때")
    x0, y, size, step = 120, 124, 40, 48
    c.text(x0 - step - 12, y + size / 2, "P", "comment", 13, mono=True, anchor="rm")
    ghost = (x0 - step, y, size, size)
    dashed_box(c, *ghost)
    c.text(mid_x(ghost), mid_y(ghost), "?", "comment", 14, bold=True, mono=True, anchor="mm")
    c.text(mid_x(ghost), y + size + 3, "0번 앞", "comment", 10, anchor="ma")
    rects = c.cells(x0, y, P, size=size, gap=step - size, marks={2: shade("builtin", 0.5), 4: SUB}, index=0)
    c.text(mid_x(rects[4]), y + size + 16, "= -1", "missing", 10, mono=True, anchor="ma")
    c.pointer(mid_x(rects[2]), y, "P[2] = 6", "builtin")
    top = 72
    c.line([(mid_x(ghost), y - 4), (mid_x(ghost), top), (mid_x(rects[4]), top)], "missing", 2)
    c.arrow(mid_x(rects[4]), top, mid_x(rects[4]), y - 4, "missing", width=2, head=7)
    c.text((mid_x(ghost) + mid_x(rects[4])) / 2, top - 5, "P[-1]은 0번 앞이 아니라 맨 끝 칸을 읽습니다", "missing", 12, anchor="ms")
    lines(c, 40, 196, [("Python: P[-1]은 마지막 원소 2를 읽어 답이 틀립니다.", "ink", False),
                       ("JavaScript: P[-1]은 undefined라 6 - undefined가 NaN입니다.", "ink", False)])
    c.number_board(400, 104, "나온 답", "6 - 2 = 4", "missing", w=130)
    c.number_board(400, 160, "맞는 답", 6, "string", w=130)
    say(c, "P[0] = 0이 없으면 l = 1일 때 P[l - 2]가 맨 끝 칸을 읽어 6 대신 4가 나옵니다.")


ERUPTIONS = [[1, 3, 2], [2, 5, 3], [3, 3, -4]]  # 2-2 예 1, n = 5, T = 3
N1, T1 = 5, 3


def diff1(n, eruptions):
    d = [0] * (n + 2)
    for l, r, v in eruptions:
        d[l] += v
        d[r + 1] -= v
    return d


@figure("2-2a", 560, 340)
def diff_sweep(fig):
    d = diff1(N1, ERUPTIONS)[1:]  # 1번 칸부터 n + 1번 칸까지
    heat = prefix(d[:N1])[1:]
    assert heat == [2, 5, 1, 3, 3]
    x0, step, size = 70, 46, 40
    base, unit = 290, 20
    for i in range(N1 + 1):  # 0 은 표시만 적은 장면, i 는 i번 칸까지 더한 장면
        c = fig.frame(1300 if i else 1800)
        title(c, "예 1: 차분 배열 d를 1번 칸부터 더해 나가기")
        marks = {k: (ADD if v > 0 else SUB) for k, v in enumerate(d) if v}
        c.text(x0 - 12, 80, "d", "comment", 13, mono=True, anchor="rm")
        rects = c.cells(x0, 60, d, size=size, gap=step - size, marks=marks, hatch={N1: OUT}, index=1)
        c.text(x0 - 12, 144, "온도", "comment", 12, anchor="rm")
        temp_marks = {k: (ADD if heat[k] >= T1 else DIM) for k in range(i)}
        c.cells(x0, 124, heat[:i] + [None] * (N1 - i), size=size, gap=step - size, marks=temp_marks)
        if i:
            c.highlight(rects[i - 1], "def")
            c.pointer(mid_x(rects[i - 1]), 60, "i")
        y_t = base - T1 * unit
        dashed(c, x0, y_t, x0 + N1 * step - 6, y_t, "decorator")
        c.text(x0 + N1 * step, y_t, "T = 3", "decorator", 11, mono=True, anchor="lm")
        c.line([(x0 - 4, base), (x0 + N1 * step - 2, base)], "edge", 1)
        for k in range(i):
            h = heat[k] * unit
            c.box(x0 + 5 + k * step, base - h, 30, h, fill="string" if heat[k] >= T1 else shade("builtin", 0.5), outline=None)
            c.text(x0 + 20 + k * step, base - h - 3, str(heat[k]), "ink", 11, mono=True, anchor="ms")
        c.number_board(400, 60, "더한 값 heat", heat[i - 1] if i else 0, "def", w=120)
        c.number_board(400, 124, "T 이상인 칸", sum(1 for k in range(i) if heat[k] >= T1), "string", w=120)
        lines(c, 400, 196, [("분출 [l, r, v]", "comment", False)] + [(str(e), "ink", True) for e in ERUPTIONS], size=11, gap=17)
        if not i:
            say(c, "분출마다 l번 칸에 +v, r + 1번 칸에 -v를 적었습니다.")
        else:
            prev = heat[i - 2] if i > 1 else 0
            add = "+ %d" % d[i - 1] if d[i - 1] >= 0 else "- %d" % -d[i - 1]
            judge = "T 이상입니다" if heat[i - 1] >= T1 else "T보다 낮습니다"
            say(c, "%d번 칸: heat = %d %s = %d, %s." % (i, prev, add, heat[i - 1], judge))


@figure("2-2b", 560, 290)
def paint_vs_marks(fig):
    c = fig.frame()
    title(c, "예 1의 분출 세 개를 적는 두 방법")
    size, step, left, right = 28, 31, 110, 340
    c.text(left, 44, "칸마다 칠하기", "ink", 13, bold=True)
    c.text(right, 44, "표시 두 개로 적기", "ink", 13, bold=True)
    painted = 0
    for k, (l, r, v) in enumerate(ERUPTIONS):
        y = 70 + k * 38
        c.text(left - 12, y + size / 2, str([l, r, v]), "comment", 11, mono=True, anchor="rm")
        row = [signed(v) if l <= j <= r else None for j in range(1, N1 + 1)]
        painted += r - l + 1
        c.cells(left, y, row, size=size, gap=step - size, marks={j - 1: shade("decorator", 0.5) for j in range(l, r + 1)},
                index=1 if k == len(ERUPTIONS) - 1 else None, text_px=11)
        mark = [None] * (N1 + 1)
        mark[l - 1], mark[r] = signed(v), signed(-v)
        c.cells(right, y, mark, size=size, gap=step - size, marks={l - 1: ADD if v > 0 else SUB, r: SUB if v > 0 else ADD},
                index=1 if k == len(ERUPTIONS) - 1 else None, text_px=11)
    c.number_board(left, 192, "칠한 칸", painted, "decorator")
    c.number_board(right, 192, "적은 표시", 2 * len(ERUPTIONS), "string")
    say(c, "칸이 200,000개가 되어도 오른쪽은 분출 하나에 표시 두 개로 끝납니다.")


GRID3 = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]  # 2-3 예 1


@figure("2-3a", 560, 270)
def inclusion_exclusion(fig):
    S = table(GRID3)
    c = fig.frame()
    title(c, "질의 [2, 2, 3, 3]")
    legend(c, 170, 9, [(shade("builtin", 0.5), None, "한 번 센 칸"), ("gutter", OUT, "빠진 칸"), (SUB, None, "두 번 빠진 칸")])
    count = [[1] * 3 for _ in range(3)]
    steps = [("S[3][3]", S[3][3], None, None), ("S[1][3]", S[1][3], (0, 0, 0, 2), -1),
             ("S[3][1]", S[3][1], (0, 0, 2, 0), -1), ("S[1][1]", S[1][1], (0, 0, 0, 0), 1)]
    total = 0
    for k, (name, value, area, sign) in enumerate(steps):
        x = 24 + k * 136
        if area:
            for r in range(area[0], area[2] + 1):
                for col in range(area[1], area[3] + 1):
                    count[r][col] += sign
        total += value if sign is None else sign * value
        fill = {1: shade("builtin", 0.5), 0: "gutter", -1: SUB}
        marks = {(r, col): fill[count[r][col]] for r in range(3) for col in range(3)}
        hatch = {(r, col): OUT for r in range(3) for col in range(3) if count[r][col] == 0}
        c.text(x + 47, 62, name, "ink", 13, bold=True, mono=True, anchor="ms")
        rows = c.grid(x, 70, GRID3, size=30, gap=2, marks=marks, hatch=hatch)
        c.highlight(span(rows, *(area or (0, 0, 2, 2))), "def" if sign is None or sign > 0 else "missing")
        c.text(x + 47, 176, str(value), "ink", 16, bold=True, mono=True, anchor="ma")
        c.text(x + 47, 202, "합 %d" % total, "comment", 12, mono=True, anchor="ma")
        if k:
            c.text(x - 21, 117, "-" if sign < 0 else "+", "def", 22, bold=True, mono=True, anchor="mm")
    assert total == 28
    say(c, "45 - 6 - 12 + 1 = 28, 파란 네 칸 5 + 6 + 8 + 9의 합과 같습니다.")


@figure("2-3b", 560, 300)
def fill_table(fig):
    S = table(GRID3)
    gx, gy, sx, sy, size, step = 50, 100, 280, 57, 40, 43
    for n in range(9):
        i, j = n // 3 + 1, n % 3 + 1
        c = fig.frame(1200)
        title(c, "예 1의 grid와 S 표")
        c.text(gx, 60, "grid", "comment", 12, mono=True)
        rows = c.grid(gx, gy, GRID3, size=size, gap=step - size, marks={(i - 1, j - 1): NEW})
        heads(c, rows, gy - 6, gx - 6)
        c.highlight(rows[i - 1][j - 1], "def")
        shown = [[S[a][b] if a == 0 or b == 0 or (a - 1) * 3 + b - 1 <= n else None for b in range(4)] for a in range(4)]
        marks = {(i - 1, j): ADD, (i, j - 1): ADD, (i - 1, j - 1): SUB, (i, j): NEW}
        srows = c.grid(sx, sy, shown, size=size, gap=step - size, marks=marks)
        heads(c, srows, sy - 4, sx - 6, first=0)
        c.text(sx - 24, mid_y(srows[0][0]), "S", "comment", 12, mono=True, anchor="rm")
        c.highlight(srows[i][j], "def")
        for k, (fill, label) in enumerate([(ADD, "더하는 칸"), (SUB, "빼는 칸"), (NEW, "채우는 칸")]):
            legend(c, 470, 120 + k * 22, [(fill, None, label)])
        formula = "S[%d][%d] = %d + %d - %d + %d = %d" % (i, j, S[i - 1][j], S[i][j - 1], S[i - 1][j - 1], GRID3[i - 1][j - 1], S[i][j])
        c.text(gx, 236, formula, "ink", 14, mono=True)
        up, left, corner, value = S[i - 1][j], S[i][j - 1], S[i - 1][j - 1], GRID3[i - 1][j - 1]
        say(c, "위 %d, 왼쪽 %d%s 더하고 왼쪽 위 %d%s 뺀 뒤 칸 값 %d%s 더합니다." % (up, left, obj(left), corner, obj(corner), value, obj(value)))


def strip(c, x, y, cols, labels, size=26, gap=2, marks=None, values=None):
    """세로 띠. labels 는 줄마다 행 번호 글자이고 None 이면 그 자리에 점 세 개를 찍음. 줄마다 칸 목록을 돌려줌."""
    marks, values = marks or {}, values or {}
    out = []
    for r, label in enumerate(labels):
        top = y + r * (size + gap)
        if label is None:
            for k in range(3):
                for col in range(cols):
                    c.box(x + col * (size + gap) + size / 2 - 2, top + 5 + k * 7, 4, 4, fill="comment", outline=None, radius=2)
            out.append(None)
            continue
        c.text(x - 6, top + size / 2, label, "line_no", 10, mono=True, anchor="rm")
        line = []
        for col in range(cols):
            cx = x + col * (size + gap)
            c.box(cx, top, size, size, fill=marks.get((r, col), "gutter"), outline="edge")
            if (r, col) in values:
                c.text(cx + size / 2, top + size / 2, values[(r, col)], "ink", 11, bold=True, mono=True, anchor="mm")
            line.append((cx, top, size, size))
        out.append(line)
    return out


@figure("2-3c", 560, 320)
def tall_grid(fig):
    c = fig.frame()
    title(c, "250,000×1 격자에 격자 전체를 묻는 질의 하나")
    c.text(30, 44, "행마다 누적합", "ink", 13, bold=True)
    c.text(300, 44, "S 표", "ink", 13, bold=True)
    labels = ["1", "2", "3", "4", None, "250,000"]
    rows = strip(c, 70, 66, 1, labels, marks={(r, 0): shade("builtin", 0.5) for r in (0, 1, 2, 3, 5)})
    bottom = rows[5][0][1] + rows[5][0][3]
    c.arrow(108, 68, 108, bottom, "builtin", width=2)
    lines(c, 118, 120, [("질의 하나에", "ink", False), ("250,000행을 더함", "ink", False)], size=12, gap=18)
    c.number_board(118, 176, "질의 200,000개", sci(200000 * 250000), "missing", w=120)
    s_labels = ["0", "1", "2", "3", None, "250,000"]
    four = {(0, 0): ADD, (0, 1): SUB, (5, 0): SUB, (5, 1): ADD}  # S[r2][c2] - S[r1 - 1][c2] - S[r2][c1 - 1] + S[r1 - 1][c1 - 1]
    values = {(r, 0): "0" for r in (0, 1, 2, 3, 5)}
    values[(0, 1)] = "0"
    srows = strip(c, 360, 66, 2, s_labels, marks=four, values=values)
    for col in (0, 1):
        c.text(mid_x(srows[0][col]), 60, str(col), "line_no", 10, mono=True, anchor="ms")
    legend(c, 300, 252, [(ADD, None, "더하는 칸"), (SUB, None, "빼는 칸")])
    c.number_board(440, 120, "질의 하나", "4칸", "string", w=100)
    c.number_board(440, 176, "질의 200,000개", sci(200000 * 4), "string", w=100)
    say(c, "같은 질의에 왼쪽은 250,000행을 더하고, 오른쪽은 S 표의 네 칸만 읽습니다.")


EVENTS4 = [[1, 1, 2, 2, 2], [2, 2, 3, 3, 3], [1, 3, 1, 3, -1]]  # 2-4 예 1, 3 × 3


@figure("2-4a", 560, 300)
def four_corners(fig):
    d = corners(3, 3, EVENTS4[:1])
    stages = [
        ([row[1:4] for row in d[1:4]], "1단계: 분출 [1, 1, 2, 2, 2]를 네 모서리 표시로 적습니다.",
         [("네 모서리 표시", "ink", False), ("(1, 1) +2   (1, 3) -2", "ink", True), ("(3, 1) -2   (3, 3) +2", "ink", True)]),
        (sweep(d, 3, 3, down=False), "2단계: 가로로 누적하면 r1행과 r2 + 1행에 띠 두 줄이 남습니다.",
         [("행마다 왼쪽부터 더함", "ink", False), ("1행: 2, 2, 0", "ink", True), ("3행: -2, -2, 0", "ink", True)]),
        (sweep(d, 3, 3), "3단계: 세로로 누적하면 (1, 1)~(2, 2) 직사각형만 2가 됩니다.",
         [("열마다 위부터 더함", "ink", False), ("1~2행, 1~2열만 2", "ink", True), ("3행은 2 - 2 = 0", "ink", True)]),
    ]
    x0, y0, size, step = 90, 76, 46, 49
    for k, (values, caption, notes) in enumerate(stages):
        c = fig.frame(1800)
        title(c, "2-4 예 1의 첫 분출 [1, 1, 2, 2, 2]")
        marks, _ = sign_marks(values)
        rows = c.grid(x0, y0, values, size=size, gap=step - size, marks=marks)
        c.text(mid_x(rows[0][0]), y0 - 6, "c1", "comment", 11, mono=True, anchor="ms")
        c.text(mid_x(rows[0][2]), y0 - 6, "c2 + 1", "comment", 11, mono=True, anchor="ms")
        c.text(x0 - 8, mid_y(rows[0][0]), "r1", "comment", 11, mono=True, anchor="rm")
        c.text(x0 - 8, mid_y(rows[2][0]), "r2 + 1", "comment", 11, mono=True, anchor="rm")
        right, bottom = x0 + 3 * step - 3, y0 + 3 * step - 3
        if k == 1:
            c.arrow(x0, bottom + 18, right, bottom + 18, "def", width=2)
            c.text((x0 + right) / 2, bottom + 24, "가로 누적", "def", 11, anchor="ma")
        if k == 2:
            c.arrow(right + 18, y0, right + 18, bottom, "def", width=2)
            c.text(right + 26, (y0 + bottom) / 2, "세로 누적", "def", 11, anchor="lm")
            c.highlight(span(rows, 0, 0, 1, 1), "def")
        lines(c, 330, 90, notes, size=12, gap=24)
        legend(c, 330, 190, [(ADD, None, "+v"), (SUB, None, "-v")])
        say(c, caption)


@figure("2-4b", 560, 300)
def two_eruptions(fig):
    d = corners(3, 3, EVENTS4[:2])
    shown = [row[1:5] for row in d[1:5]]  # 1~4행, 1~4열. 4행과 4열은 격자 밖
    final = sweep(d, 3, 3)
    assert final == [[2, 2, 0], [2, 5, 3], [0, 3, 3]]
    c = fig.frame()
    title(c, "2-4 예 1의 첫 두 분출")
    first, second = shade("def", 0.5), shade("builtin", 0.5)
    marks = {}
    for (r1, c1, r2, c2, _), fill in zip(EVENTS4[:2], (first, second)):
        for r, col in ((r1, c1), (r1, c2 + 1), (r2 + 1, c1), (r2 + 1, c2 + 1)):
            marks[(r - 1, col - 1)] = fill
    hatch = {(r, col): OUT for r in range(4) for col in range(4) if r == 3 or col == 3}
    size, step, y0 = 36, 39, 76
    c.text(50, 44, "모서리 표시를 더한 배열", "ink", 13, bold=True)
    rows = c.grid(50, y0, [[signed(v) if v else 0 for v in row] for row in shown], size=size, gap=step - size, marks=marks, hatch=hatch)
    heads(c, rows, y0 - 4, 44)
    arrow_y = y0 + 1.5 * step - 1.5
    c.arrow(228, arrow_y, 312, arrow_y, "def", width=2)
    c.text(270, arrow_y - 8, "두 번 누적", "def", 11, anchor="ms")
    c.text(330, 44, "최종 온도", "ink", 13, bold=True)
    fmarks = {}
    for r in range(3):
        for col in range(3):
            inside = [r1 - 1 <= r <= r2 - 1 and c1 - 1 <= col <= c2 - 1 for r1, c1, r2, c2, _ in EVENTS4[:2]]
            if all(inside):
                fmarks[(r, col)] = shade("string", 0.5)
            elif inside[0]:
                fmarks[(r, col)] = first
            elif inside[1]:
                fmarks[(r, col)] = second
    frows = c.grid(330, y0, final, size=size, gap=step - size, marks=fmarks)
    heads(c, frows, y0 - 4, 324)
    c.highlight(frows[1][1], "def")
    legend(c, 50, 240, [(first, None, "첫 분출 +2"), (second, None, "둘째 분출 +3"), (shade("string", 0.5), None, "겹친 칸"), ("gutter", OUT, "격자 밖")])
    say(c, "두 분출의 표시를 한 배열에 적고 두 번 누적하면 겹친 (2, 2)만 5가 됩니다.")


BN, BM, BT, BD = 3, 4, 5, 1  # 2-B 예 1
BEVENTS = [[1, 1, 2, 3, 5], [2, 2, 3, 4, -3], [1, 4, 3, 4, 4]]


def boss_maps():
    d = corners(BN, BM, BEVENTS)
    temp = sweep(d, BN, BM)
    lava = [[1 if t >= BT else 0 for t in row] for row in temp]
    L = table(lava)
    safe = []
    for i in range(1, BN + 1):
        a, b = max(1, i - BD) - 1, min(BN, i + BD)
        row = []
        for j in range(1, BM + 1):
            cc, e = max(1, j - BD) - 1, min(BM, j + BD)
            row.append(1 if L[b][e] - L[a][e] - L[b][cc] + L[a][cc] == 0 else 0)
        safe.append(row)
    return d, temp, lava, L, safe, table(safe)


@figure("2-ba", 560, 340)
def boss_steps(fig):
    d, temp, lava, L, safe, S = boss_maps()
    assert temp == [[5, 5, 5, 4], [5, 2, 2, 1], [0, -3, -3, 1]]
    assert safe == [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 1, 1]]
    x0, y0, size, step = 70, 100, 40, 43
    px = 318
    lava_marks = {(r, col): SUB for r in range(BN) for col in range(BM) if lava[r][col]}

    def frame(head, ms=1800):
        c = fig.frame(ms)
        title(c, "2-B 예 1: N = 3, M = 4, T = 5, d = 1")
        c.text(px, 52, head, "ink", 13, bold=True)
        return c

    c = frame("1. 모서리 표시 D")
    shown = [row[1:BM + 2] for row in d[1:BN + 2]]
    marks, hatch = sign_marks(shown, extra_row=BN, extra_col=BM)
    rows = c.grid(x0, y0, shown, size=size, gap=step - size, marks=marks, hatch=hatch)
    heads(c, rows, y0 - 6, x0 - 8)
    lines(c, px, 84, [("분출 [r1, c1, r2, c2, v]", "comment", False)] + [(str(e), "ink", True) for e in BEVENTS], size=11, gap=18)
    legend(c, px, 170, [(ADD, None, "+ 표시"), (SUB, None, "- 표시")])
    legend(c, px, 192, [("gutter", OUT, "격자 밖(4행, 5열)")])
    say(c, "1단계: 분출마다 네 모서리에 +v, -v를 적습니다.")

    c = frame("2. 최종 온도")
    rows = c.grid(x0, y0, temp, size=size, gap=step - size)
    heads(c, rows, y0 - 6, x0 - 8)
    lines(c, px, 84, [("가로로 한 번, 세로로 한 번 누적", "ink", False), ("1행 [5, 5, 5, 4]", "ink", True), ("2행 [5, 2, 2, 1]", "ink", True), ("3행 [0, -3, -3, 1]", "ink", True)], size=12, gap=22)
    say(c, "2단계: 두 방향으로 누적하면 칸마다 최종 온도가 나옵니다.")

    c = frame("3. 용암 지도 (온도 ≥ T)")
    rows = c.grid(x0, y0, lava, size=size, gap=step - size, marks=lava_marks)
    heads(c, rows, y0 - 6, x0 - 8)
    c.number_board(px, 84, "T", BT, "decorator", w=110)
    c.number_board(px, 140, "용암 칸", sum(map(sum, lava)), "missing", w=110)
    say(c, "3단계: 온도가 T = 5 이상인 칸에 1을 적은 용암 지도입니다.")

    c = frame("4. (3, 3)의 창, d = 1")
    marks = dict(lava_marks)
    marks[(2, 2)] = NEW
    rows = c.grid(x0, y0, lava, size=size, gap=step - size, marks=marks)
    heads(c, rows, y0 - 6, x0 - 8)
    win = (x0 + step - 3, y0 + step - 3, 3 * step + 3, 3 * step + 3)  # 2~4행, 2~4열. 4행은 격자 밖
    dashed_box(c, *win, "decorator")
    c.highlight(span(rows, 1, 1, 2, 3), "def", width=2)
    c.text(mid_x(win), win[1] + win[3] - 14, "4행은 격자 밖", "decorator", 11, anchor="mm")
    a, b, cc, e = 1, 3, 1, 4
    lines(c, px, 84, [("2~4행, 2~4열을 2~3행으로 자름", "ink", False), ("L은 용암 지도의 누적합", "comment", False),
                      ("L[3][4] - L[1][4]", "ink", True), ("- L[3][1] + L[1][1]", "ink", True),
                      ("= %d - %d - %d + %d = 0" % (L[b][e], L[a][e], L[b][cc], L[a][cc]), "ink", True)], size=12, gap=22)
    c.number_board(px, 200, "창 안 용암", 0, "string", w=110)
    say(c, "4단계: 창을 격자 안으로 잘라 L의 네 칸으로 용암 수를 셉니다.")

    c = frame("5. 안전 지도")
    marks = {}
    for r in range(BN):
        for col in range(BM):
            marks[(r, col)] = ADD if safe[r][col] else (SUB if lava[r][col] else shade("decorator", 0.5))
    rows = c.grid(x0, y0, safe, size=size, gap=step - size, marks=marks)
    heads(c, rows, y0 - 6, x0 - 8)
    legend(c, px, 84, [(SUB, None, "용암")])
    legend(c, px, 106, [(shade("decorator", 0.5), None, "위험(창 안에 용암)")])
    legend(c, px, 128, [(ADD, None, "안전")])
    c.number_board(px, 160, "안전 칸", sum(map(sum, safe)), "string", w=110)
    say(c, "5단계: 창 안에 용암이 있으면 위험, 없으면 안전 칸에 1을 적습니다.")

    c = frame("6. 질의 [3, 2, 3, 4]")
    marks = {(3, 4): ADD, (2, 4): SUB, (3, 1): SUB, (2, 1): ADD}  # S[r2][c2] - S[r1 - 1][c2] - S[r2][c1 - 1] + S[r1 - 1][c1 - 1]
    rows = c.grid(x0 - step, y0 - step, S, size=size, gap=step - size, marks=marks)
    heads(c, rows, y0 - step - 6, x0 - step - 8, first=0)
    c.highlight(span(rows, 3, 2, 3, 4), "def", width=2)
    legend(c, px, 244, [(ADD, None, "더하는 칸"), (SUB, None, "빼는 칸")])
    lines(c, px, 84, [("안전 지도의 누적합 S", "comment", False), ("S[3][4] - S[2][4]", "ink", True), ("- S[3][1] + S[2][1]", "ink", True),
                      ("= %d - %d - %d + %d" % (S[3][4], S[2][4], S[3][1], S[2][1]), "ink", True)], size=12, gap=22)
    c.number_board(px, 184, "답", S[3][4] - S[2][4] - S[3][1] + S[2][1], "string", w=110)
    say(c, "6단계: 안전 지도의 누적합 S에서 네 칸을 읽어 답 2를 구합니다.")


@figure("2-bb", 560, 320)
def square_vs_diamond(fig):
    c = fig.frame()
    title(c, "가운데 칸이 용암일 때. 칸의 숫자는 용암 칸과의 행 차이 + 열 차이입니다")
    legend(c, 20, 38, [(SUB, None, "용암"), (shade("decorator", 0.5), None, "마름모와 정사각형 모두"), ("gutter", shade("decorator", 0.25), "정사각형에만")])
    for x, n, size, dist in ((40, 5, 30, 1), (300, 7, 24, 2)):
        mid = n // 2
        values, marks, hatch = [], {}, {}
        for r in range(n):
            row = []
            for col in range(n):
                manhattan = abs(r - mid) + abs(col - mid)
                square = max(abs(r - mid), abs(col - mid)) <= dist
                row.append(manhattan if square else None)
                if not manhattan:
                    marks[(r, col)] = SUB
                elif manhattan <= dist:
                    marks[(r, col)] = shade("decorator", 0.5)
                elif square:
                    hatch[(r, col)] = shade("decorator", 0.25)
            values.append(row)
        c.text(x, 66, "d = %d" % dist, "ink", 13, bold=True, mono=True)
        c.text(x + 52, 67, "정사각형 %d칸, 마름모 %d칸" % ((2 * dist + 1) ** 2, 2 * dist * (dist + 1) + 1), "comment", 12)
        rows = c.grid(x, 90, values, size=size, gap=2, marks=marks, hatch=hatch)
        c.highlight(span(rows, mid - dist, mid - dist, mid + dist, mid + dist), "def")
    say(c, "빗금 칸은 두 차이가 모두 d 이하라 위험 칸이지만 마름모에서는 빠집니다.")


@figure("2-bc", 560, 280)
def tall_work(fig):
    n, d, q, e = 250000, 100000, 250000, 250000
    full, small = e // 2, e // 2  # tall 의 분출: 띠 전체 분출 짝 62,500쌍(125,000개)과 50칸 미만의 작은 분출
    safe = n - 2 * d  # 앞 d 칸이 용암이라 뒤쪽 n - 2d 칸만 안전함
    scan = sum(n - (i - d) + 1 for i in range(n - safe + 1, n + 1))  # 안전 칸은 창 안의 행을 끝까지 읽음. 위험 칸은 첫 행에서 멈춤
    rows_way = full * n + small * 50 + scan + q * n  # 분출을 행마다 적고, 칸마다 창의 행을 읽고, 질의마다 행을 도는 횟수. 작은 분출은 상한 50행으로 셈
    widen = n * d  # 띠 전체를 d번 훑음
    ours = 4 * e + 2 * n + n + 4 * n + n + 4 * q  # 표시 4칸, 두 방향 누적, L, 칸마다 L 네 칸, S, 질의마다 S 네 칸
    c = fig.frame()
    title(c, "tall(250,000×1 띠, d = 100,000)에서 칸을 읽고 쓰는 횟수")
    x0, length, top = 150, 300, rows_way
    for k, (label, value, color_name) in enumerate((("행 단위 풀이", rows_way, "missing"), ("d번 넓히기", widen, "decorator"), ("기준 풀이", ours, "string"))):
        y = 62 + k * 52
        c.text(x0 - 12, y + 13, label, "ink", 13, anchor="rm")
        w = max(2, length * value / top)
        c.box(x0, y, w, 26, fill=shade(color_name, 0.25), outline=None)
        c.text(x0 + w + 8, y + 13, "약 " + sci(value) + "번", color_name, 13, bold=True, mono=True, anchor="lm")
    c.line([(x0, 54), (x0, 62 + 2 * 52 + 34)], "edge", 1)
    c.text(x0, 212, "기준 풀이의 막대는 너무 짧아 선으로만 보입니다.", "comment", 12)
    say(c, "느린 두 풀이는 기준 풀이보다 수천 배 넘게 많은 칸을 읽고 씁니다.")
