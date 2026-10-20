# -*- coding: utf-8 -*-
"""던전 3 「모래시계 탑」 해설 그림. 값은 문제마다 입출력 예와 explain.md 의 표를 씀. 탐색 단계와 놓는 자리는
이 파일의 작은 함수로 다시 계산해서 해설의 표와 같은지 그릴 때 확인함.

  python3 tools/journey_art/render.py d03 [--check]
"""
from tools.journey_art.draw import figure, mid_x, shade

TRUE, FALSE = shade("string", 0.5), shade("missing", 0.75)  # F/T 띠의 칸
DIM = shade("comment", 0.5)
ZONE = shade("builtin", 0.75)  # 3-B 구역 띠
HATCH = shade("missing", 0.5)  # 3-3 에서 D 보다 가까워 쓸 수 없는 곳


def head(c, s):
    c.text(20, 14, s, "comment", 13)


def note(c, s):
    """아래 띠의 설명. 띠보다 길면 그리기 전에 멈춤."""
    if c.text_size(s, 13)[0] > c.width - 24:
        raise ValueError("설명이 그림 폭보다 깁니다: %s" % s)
    c.caption(s)


def dot(c, x, y, color_name, r=6):
    c.box(x - r, y - r, 2 * r, 2 * r, fill=color_name, outline=None, radius=r)


def ring(c, x, y, color_name="def", r=10):
    c.box(x - r, y - r, 2 * r, 2 * r, fill=None, outline=color_name, width=2, radius=r)


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


def pointers(c, x_lo, x_hi, y):
    """lo 와 hi 포인터. 한 칸에 모이면 옆으로 비켜 그림."""
    shift = 12 if x_lo == x_hi else 0
    c.pointer(x_lo - shift, y, "lo", "def")
    c.pointer(x_hi + shift, y, "hi", "decorator")


def strip(c, x, y, answers, size, gap, first, mid=None):
    """F/T 띠. answers 는 칸마다 "T", "F", None(아직 모름). mid 칸은 테두리로 강조함. 칸들의 (x, y, w, h) 를 돌려줌."""
    marks = {i: TRUE if a == "T" else FALSE for i, a in enumerate(answers) if a}
    rects = c.cells(x, y, [a or "" for a in answers], size=size, gap=gap, marks=marks, index=first, text_px=12)
    if mid is not None:
        c.highlight(rects[mid - first], "builtin", width=2)
    return rects


def legend(c, x, y, items, size=11):
    """[(그리는 함수, 글자)] 를 가로로 늘어놓음. 그리는 함수는 (c, 가운데 x, 가운데 y) 를 받음."""
    for draw_mark, label in items:
        draw_mark(c, x + 6, y)
        x += 16 + c.text(x + 16, y, label, "ink", size, anchor="lm")[0] + 16


def row_table(c, x, y, heads, rows, widths, row_h=24, colors=None):
    """머리줄과 줄들. rows 는 칸 글자 목록, colors 는 줄마다 글자 색(없으면 ink)."""
    colors = colors or []
    cx = x
    for head_text, w in zip(heads, widths):
        c.text(cx + w / 2, y, head_text, "comment", 11, anchor="mm")
        cx += w
    for k, row in enumerate(rows):
        ry = y + 14 + k * row_h
        color_name = colors[k] if k < len(colors) and colors[k] else "ink"
        c.box(x, ry, sum(widths), row_h - 4, fill="gutter", outline="edge" if color_name == "ink" else color_name, radius=3)
        cx = x
        for value, w in zip(row, widths):
            c.text(cx + w / 2, ry + (row_h - 4) / 2, str(value), color_name, 12, mono=True, anchor="mm")
            cx += w


# 3-1 기록관 질의

SORTED = [1, 3, 5, 5, 9]  # 예 1 의 times 를 정렬한 배열


def first_true(n, ok):
    """[lo, hi) 꼴로 처음 참인 자리를 찾고 (lo, hi, mid, 참 여부) 단계들과 답을 돌려줌."""
    lo, hi, steps = 0, n, []
    while lo < hi:
        mid = (lo + hi) // 2
        steps.append((lo, hi, mid, ok(mid)))
        if ok(mid):
            hi = mid
        else:
            lo = mid + 1
    return steps, lo


@figure("3-1c", 560, 300)
def lower_bound_steps(fig):
    steps, answer = first_true(len(SORTED), lambda i: SORTED[i] >= 5)
    assert [s[:3] for s in steps] == [(0, 5, 2), (0, 2, 1)] and answer == 2  # 해설의 단계
    frames = [(0, 5, None, None, "찾는 자리는 [0, 5) 안에 있고, lo = 0, hi = 5에서 시작합니다.")]
    rows = []
    for lo, hi, mid, ok in steps:
        word = "5 이상이라 T" if ok else "5보다 작아 F"
        frames.append((lo, hi, mid, ok, "mid = %d, 그 자리의 %d는 %s입니다." % (mid, SORTED[mid], word)))
        nlo, nhi = (lo, mid) if ok else (mid + 1, hi)
        moved = "hi = %d로 옮깁니다." % nhi if ok else "lo = %d로 옮깁니다." % nlo
        why = "찾는 자리는 %d이거나 그 앞이라 " % mid if ok else "찾는 자리는 %d보다 뒤라 " % mid
        frames.append((nlo, nhi, None, None, why + moved))
    frames.append((answer, answer, None, None, "lo와 hi가 %d에서 만나 5의 lower bound는 %d입니다." % (answer, answer)))
    for k, (lo, hi, mid, ok, text) in enumerate(frames):
        c = fig.frame(2000 if k == len(frames) - 1 else 1500)
        head(c, "예 1의 정렬된 배열에서 \"5 이상인가?\"의 첫 T 찾기")
        known = {i: TRUE for i in range(hi, len(SORTED))}
        known.update({i: FALSE for i in range(lo)})
        if mid is not None:
            known[mid] = TRUE if ok else FALSE
        rects = c.cells(20, 92, SORTED, size=40, gap=8, marks=known, index=0)
        ghost = (20 + 5 * 48, 92, 40, 40)
        dashed_box(c, *ghost)
        c.text(mid_x(ghost), 92 + 43, "5", "line_no", 10, mono=True, anchor="ma")
        c.text(mid_x(ghost), 92 + 20, "n", "comment", 13, mono=True, anchor="mm")
        slots = rects + [ghost]
        pointers(c, mid_x(slots[lo]), mid_x(slots[hi]), 92)
        if mid is not None:
            c.highlight(rects[mid], "builtin", width=2)
            c.pointer(mid_x(rects[mid]), 92 + 56, "mid", "builtin", above=False)
        if k == len(frames) - 1:
            c.number_board(20, 196, "lower bound", answer, "string", w=120)
        if mid is not None:
            rows.append((lo, hi, mid, SORTED[mid], "T" if ok else "F"))
        shown = rows + ([(answer, answer, "", "", "끝")] if k == len(frames) - 1 else [])
        row_table(c, 334, 74, ["lo", "hi", "mid", "값", "판정"], shown, [38, 38, 42, 42, 48],
                  colors=["string" if r[4] == "T" else ("missing" if r[4] == "F" else "def") for r in shown])
        note(c, text)


@figure("3-1a", 560, 260)
def first_true_strip(fig):
    c = fig.frame()
    head(c, "예 1의 정렬된 배열 [1, 3, 5, 5, 9]에 a = 5를 대기")
    x = 150
    rects = c.cells(x, 50, SORTED, size=44, gap=10, index=0)
    c.text(x - 14, 72, "정렬된 배열", "comment", 12, anchor="rm")
    answers = ["T" if v >= 5 else "F" for v in SORTED]
    band = strip(c, x, 124, answers, 44, 10, 0)
    c.text(x - 14, 146, "5 이상인가?", "comment", 12, anchor="rm")
    for top, bottom in zip(rects, band):
        c.line([(mid_x(top), 50 + 44 + 14), (mid_x(bottom), 120)], "edge", 1)
    c.pointer(mid_x(band[2]), 124 + 44 + 14, "lower bound", "def", above=False)
    c.number_board(440, 112, "첫 T의 자리", 2, "def", w=100)
    note(c, "F가 이어지다가 처음 T가 나오는 2번 자리가 5의 lower bound입니다.")


@figure("3-1b", 560, 320)
def two_bounds(fig):
    c = fig.frame()
    head(c, "같은 배열에 질의 [5, 5]를 대고 두 경계 찾기")
    x = 150
    rects = c.cells(x, 70, SORTED, size=44, gap=10, index=0)
    c.text(x - 14, 92, "정렬된 배열", "comment", 12, anchor="rm")
    c.pointer(mid_x(rects[2]), 70, "lower bound", "def")
    c.pointer(mid_x(rects[4]), 70, "upper bound", "decorator")
    c.bracket(rects[2][0], rects[3][0] + 44, 134, "시각 5 두 개", "string")
    strip(c, x, 170, ["T" if v >= 5 else "F" for v in SORTED], 44, 10, None)
    c.text(x - 14, 192, "5 이상인가?", "def", 12, anchor="rm")
    strip(c, x, 222, ["T" if v > 5 else "F" for v in SORTED], 44, 10, None)
    c.text(x - 14, 244, "5보다 큰가?", "decorator", 12, anchor="rm")
    c.highlight((rects[2][0], 170, 44, 44), "def", width=2)
    c.highlight((rects[4][0], 222, 44, 44), "decorator", width=2)
    c.number_board(440, 170, "4 - 2", 2, "string", w=100)
    note(c, "upper bound 4에서 lower bound 2를 빼면 [5, 5]에 드는 사건 수 2가 나옵니다.")


# 3-2 예열하는 연금로

FURNACES, ORDER = [[4, 2], [0, 5]], 4  # 예 2


def made(T, furnace):
    w, c = furnace
    return (T - w) // c if T > w else 0


def furnace_steps():
    """처음 참인 T 를 [lo, hi] 꼴로 찾는 단계 (lo, hi, mid, 개수). 기준 풀이와 같은 탐색."""
    lo, hi, steps = 1, min(w + c * ORDER for w, c in FURNACES), []
    while lo < hi:
        mid = (lo + hi) // 2
        count = sum(made(mid, f) for f in FURNACES)
        steps.append((lo, hi, mid, count))
        if count >= ORDER:
            hi = mid
        else:
            lo = mid + 1
    return steps, lo


def timeline(c, x_of, rows_y, until, marked, last=None):
    """연금로마다 0..until 분의 줄에 예열 구간(회색)과 last 분(없으면 until)까지의 완성 눈금. marked(T) 가 돌려준 색으로
    눈금을 칠함(None 이면 흐리게)."""
    for (w, cyc), y in zip(FURNACES, rows_y):
        c.text(16, y, "[%d, %d]" % (w, cyc), "ink", 12, mono=True, anchor="lm")
        c.line([(x_of(0), y), (x_of(until), y)], "edge", 1)
        if w:
            c.box(x_of(0), y - 7, x_of(w) - x_of(0), 14, fill=DIM, outline=None, radius=2)
            c.text((x_of(0) + x_of(w)) / 2, y, "예열", "ink", 10, anchor="mm")
        t = w + cyc
        while t <= (until if last is None else last):
            c.box(x_of(t) - 2, y - 11, 4, 22, fill=marked(t) or DIM, outline=None)
            t += cyc


def axis(c, x_of, y, lo, hi):
    c.line([(x_of(lo), y), (x_of(hi), y)], "edge", 1)
    for t in range(lo, hi + 1):
        c.line([(x_of(t), y), (x_of(t), y + 4)], "edge", 1)
        c.text(x_of(t), y + 7, str(t), "line_no", 10, mono=True, anchor="ma")


@figure("3-2a", 560, 300)
def furnace_timeline(fig):
    c = fig.frame()
    head(c, "예 2: furnaces = [[4, 2], [0, 5]], M = 4")

    def x_of(t):
        return 70 + 26 * t

    rows_y = [96, 150]
    timeline(c, x_of, rows_y, 12, lambda t: "string" if t <= 9 else "def", last=10)
    axis(c, x_of, 190, 0, 12)
    dashed(c, x_of(9), 58, x_of(9), 186, "missing")
    c.text(x_of(9) - 4, 54, "T = 9", "missing", 12, bold=True, mono=True, anchor="rs")
    c.line([(x_of(10), 58), (x_of(10), 186)], "def", 2)
    c.text(x_of(10) + 4, 54, "T = 10", "def", 12, bold=True, mono=True, anchor="ls")
    nine = [made(9, f) for f in FURNACES]
    ten = [made(10, f) for f in FURNACES]
    cols = [(440, "9분까지", nine, "missing", "missing"), (510, "10분까지", ten, "def", "string")]
    for x, label, counts, line_color, total_color in cols:
        c.text(x, 62, label, line_color, 12, bold=True, anchor="mm")
        for y, n in zip(rows_y, counts):
            c.text(x, y, "%d개" % n, "ink", 13, anchor="mm")
        c.text(x, 202, "합 %d개" % sum(counts), total_color, 13, bold=True, anchor="mm")
    c.line([(410, 182), (548, 182)], "edge", 1)
    legend(c, 70, 238, [
        (lambda c, x, y: c.box(x - 6, y - 6, 12, 12, fill=DIM, outline=None, radius=2), "예열"),
        (lambda c, x, y: c.box(x - 2, y - 8, 4, 16, fill="string", outline=None), "9분까지 완성"),
        (lambda c, x, y: c.box(x - 2, y - 8, 4, 16, fill="def", outline=None), "10분에 완성"),
    ])
    note(c, "T = 9까지는 3개로 M = 4에 못 미치고, T = 10까지 세면 5개가 됩니다.")


@figure("3-2b", 560, 320)
def furnace_search(fig):
    steps, answer = furnace_steps()
    assert [s[2:] for s in steps] == [(6, 2), (9, 3), (11, 5), (10, 5)] and answer == 10  # 해설의 표
    first_hi = steps[0][1]
    frames = [(1, first_hi, None, None, "hi는 4 + 2 × 4 = 12와 0 + 5 × 4 = 20 가운데 작은 12입니다.")]
    for lo, hi, mid, count in steps:
        if count >= ORDER:
            text = "%d분까지 %d개라 예, hi = %d로 옮깁니다." % (mid, count, mid)
        else:
            text = "%d분까지 %d개라 아니오, lo = %d로 옮깁니다." % (mid, count, mid + 1)
        frames.append((lo, hi, mid, count, text))
    frames.append((answer, answer, None, None, "lo와 hi가 10에서 만나 답은 10분입니다."))

    def x_of(t):
        return 61 + 34 * t

    for k, (lo, hi, mid, count, text) in enumerate(frames):
        c = fig.frame(2000 if k in (0, len(frames) - 1) else 1600)
        head(c, "예 2: \"T분까지 M = 4개 이상인가?\"가 처음 예가 되는 T 찾기")
        answers = [None] * first_hi
        for t in range(1, first_hi + 1):
            if t < lo:
                answers[t - 1] = "F"
            elif t >= hi:
                answers[t - 1] = "T"
        if mid is not None:
            answers[mid - 1] = "T" if count >= ORDER else "F"
        cells = strip(c, 80, 62, answers, 30, 4, 1, mid)
        pointers(c, mid_x(cells[lo - 1]), mid_x(cells[hi - 1]), 62)
        T = mid if mid is not None else (answer if k == len(frames) - 1 else None)
        rows_y = [150, 190]
        timeline(c, x_of, rows_y, 12, lambda t: "string" if T is not None and t <= T else None)
        axis(c, x_of, 222, 0, 12)
        if T is not None:
            c.line([(x_of(T), 126), (x_of(T), 216)], "builtin" if mid is not None else "def", 2)
            c.text(x_of(T), 122, "T = %d" % T, "builtin" if mid is not None else "def", 12, bold=True, mono=True, anchor="ms")
            for f, y in zip(FURNACES, rows_y):
                c.text(500, y, "%d개" % made(T, f), "ink", 12, anchor="lm")
            total = sum(made(T, f) for f in FURNACES)
            c.text(500, 222, "합 %d개" % total, "string" if total >= ORDER else "missing", 12, bold=True, anchor="lm")
        if k == len(frames) - 1:
            c.highlight(cells[answer - 1], "def", width=2)
        note(c, text)


@figure("3-2c", 560, 340)
def js_mid_traps(fig):
    c = fig.frame()
    head(c, "Node 22에서 그대로 돌려 본 결과")
    lines = [
        ("// >> 1과 Math.floor로 가운데 값 구하기", "comment"),
        ("> 1e14 >> 1", "ink"),
        ("138223616", "missing"),
        ("> Math.floor(1e14 / 2)", "ink"),
        ("50000000000000", "string"),
        ("> (1 + 2500000000) >> 1", "ink"),
        ("-897483648", "missing"),
        ("> Math.floor((1 + 2500000000) / 2)", "ink"),
        ("1250000000", "string"),
        ("// 원소 200,000개를 함수의 인자로 펼치기", "comment"),
        ("> Math.min(...new Array(200000).fill(1))", "ink"),
        ("RangeError: Maximum call stack size exceeded", "missing"),
    ]
    c.box(16, 38, 528, len(lines) * 19 + 16, fill="gutter", outline="edge", radius=4)
    for k, (s, color_name) in enumerate(lines):
        c.text(28, 46 + k * 19, s, color_name, 12, mono=True)
    note(c, "빨간 줄이 기대와 다른 결과입니다. 큰 값의 가운데는 Math.floor로 구하세요.")


# 3-3 이미 놓인 수정

STANDS, FIXED, NEED = [1, 4, 9, 12], [6], 2  # 예 2


def greedy(stands, fixed, D):
    """받침대를 왼쪽부터 보며 올릴 수 있는 곳에 모두 올린 위치들. 놓인 수정끼리의 간격은 보지 않음."""
    placed, last, j = [], None, 0
    for p in stands:
        while j < len(fixed) and fixed[j] <= p:
            last = fixed[j] if last is None else max(last, fixed[j])
            j += 1
        right = fixed[j] if j < len(fixed) else None
        if (last is None or p - last >= D) and (right is None or right - p >= D):
            placed.append(p)
            last = p
    return placed


def pedestal(c, x, y, used):
    c.box(x - 8, y - 5, 16, 5, fill="edge" if not used else shade("string", 0.25), outline=None, radius=1)


def corridor(c, x_of, y, stands, fixed, placed, D, left=0, right=13):
    """회랑 한 줄. 놓인 수정(금색)과 그 둘레에서 D 보다 가까운 곳의 빗금, 받침대, 올린 수정, 위치 숫자."""
    for f in fixed:
        a, b = max(x_of(left), x_of(f - D) + 3), min(x_of(right), x_of(f + D) - 3)
        if b > a:
            c.box(a, y - 30, b - a, 34, fill=shade("missing", 0.75), outline=None)
            c.hatch((a, y - 30, b - a, 34), HATCH)
    c.line([(x_of(left) - 8, y), (x_of(right) + 8, y)], "edge", 1)
    for p in stands:
        pedestal(c, x_of(p), y, p in placed)
        if p in placed:
            dot(c, x_of(p), y - 13, "string")
    for f in fixed:
        dot(c, x_of(f), y - 13, "def", r=7)
    for p in sorted(set(stands) | set(fixed)):
        c.text(x_of(p), y + 6, str(p), "def" if p in fixed else "line_no", 11, mono=True, anchor="ma")


@figure("3-3a", 560, 300)
def crystal_slider(fig):
    counts = [len(greedy(STANDS, FIXED, D)) for D in range(1, 7)]
    assert counts == [4, 4, 3, 2, 2, 1]  # 해설의 개수
    texts = [
        "D = 1: 받침대 1, 4, 9, 12에 모두 올려 4개입니다.",
        "D = 2: 4는 6과 2만큼 떨어져 아직 올릴 수 있어 4개입니다.",
        "D = 3: 4가 6과 너무 가까워 빠지고 3개입니다.",
        "D = 4: 9도 6과 너무 가까워 빠지고 1과 12, 2개입니다.",
        "D = 5: 1은 6과 5만큼 떨어져 아직 올릴 수 있어 2개입니다.",
        "D = 6: 1도 빠져 12 하나만 남고 K = 2 밑으로 떨어집니다.",
    ]

    def x_of(p):
        return 44 + 36 * p

    for D in range(1, 7):
        c = fig.frame(1600)
        head(c, "예 2: stands = [1, 4, 9, 12], fixed = [6], K = 2")
        c.text(30, 64, "D", "def", 14, bold=True, mono=True, anchor="mm")
        c.line([(60, 64), (310, 64)], "edge", 2)
        for d in range(1, 7):
            sx = 60 + (d - 1) * 50
            c.line([(sx, 58), (sx, 70)], "edge", 1)
            c.text(sx, 76, str(d), "def" if d == D else "line_no", 11, mono=True, anchor="ma")
        dot(c, 60 + (D - 1) * 50, 64, "def", r=8)
        placed = greedy(STANDS, FIXED, D)
        count = len(placed)
        c.number_board(400, 40, "올린 수 (K = 2)", count, "string" if count >= NEED else "missing", w=130)
        corridor(c, x_of, 182, STANDS, FIXED, placed, D)
        legend(c, 24, 228, [
            (lambda c, x, y: dot(c, x, y, "def", r=6), "이미 놓인 수정"),
            (lambda c, x, y: dot(c, x, y, "string", r=6), "올린 수정"),
            (lambda c, x, y: pedestal(c, x, y + 3, False), "받침대"),
            (lambda c, x, y: c.hatch((x - 6, y - 6, 12, 12), HATCH, step=4), "6과 D보다 가까운 곳"),
        ])
        note(c, texts[D - 1])


@figure("3-3b", 560, 300)
def leftmost_swap(fig):
    stands, fixed, D = [3, 7, 10, 13, 16, 20, 23, 26], [0, 30], 6
    other = [10, 16, 23]
    moved = [7, 16, 23]
    assert greedy(stands, fixed, D)[0] == 7  # 옮긴 자리는 쓸 수 있는 가장 왼쪽 받침대

    def x_of(p):
        return 40 + 16 * p

    c = fig.frame()
    head(c, "놓인 수정 0과 30 사이에 D = 6을 지키며 올린 두 배치")
    rows = [(110, other, 20, "어떤 배치: 10, 16, 23"), (214, moved, 230, "첫 수정을 가장 왼쪽 받침대 7로 옮긴 배치")]
    for y, placed, label_x, label in rows:
        c.text(label_x, y - 66, label, "ink", 12)
        corridor(c, x_of, y, stands, fixed, placed, D, right=30)
        chain = [fixed[0]] + placed + [fixed[1]]
        for a, b in zip(chain, chain[1:]):
            grew = placed is moved and a == 7
            c.bracket(x_of(a) + 3, x_of(b) - 3, y - 32, str(b - a), "string" if grew else "comment", 12, below=False, tick=4)
    c.arrow(x_of(10), 128, x_of(7) + 3, 192, "def", width=2)
    legend(c, 24, 252, [
        (lambda c, x, y: dot(c, x, y, "def", r=6), "놓인 수정"),
        (lambda c, x, y: dot(c, x, y, "string", r=6), "올린 수정"),
        (lambda c, x, y: pedestal(c, x, y + 3, False), "받침대"),
        (lambda c, x, y: c.hatch((x - 6, y - 6, 12, 12), HATCH, step=4), "놓인 수정과 6보다 가까운 곳"),
    ])
    note(c, "7로 옮겨도 0과 7만큼 떨어져 D = 6을 지키고, 16과는 6에서 9로 멀어집니다.")


def search_last_true(lo, hi, ok, ceil=True, limit=6):
    """마지막 참을 lo = mid, hi = mid - 1 로 찾는 단계 (lo, hi, mid, 참 여부). ceil 이 거짓이면 mid 를 내려 잡고,
    같은 mid 가 되풀이되어도 limit 단계에서 멈춤."""
    steps = []
    while lo < hi and len(steps) < limit:
        mid = (lo + hi + 1) // 2 if ceil else (lo + hi) // 2
        good = ok(mid)
        steps.append((lo, hi, mid, good))
        if good:
            lo = mid
        else:
            hi = mid - 1
    return steps, lo


@figure("3-3c", 560, 300)
def floor_mid_loops(fig):
    stands, K = [0, 3, 6, 7, 10], 3  # 예 1

    def ok(D):
        return len(greedy(stands, [], D)) >= K

    floor_steps, _ = search_last_true(0, 10, ok, ceil=False, limit=5)
    assert [s[:3] for s in floor_steps] == [(0, 10, 5), (0, 4, 2), (2, 4, 3), (3, 4, 3), (3, 4, 3)]
    c = fig.frame()
    head(c, "예 1에서 mid를 (lo + hi)를 2로 나눈 몫으로 내려 잡을 때")
    rows, colors = [], []
    for k, (lo, hi, mid, good) in enumerate(floor_steps):
        nxt = ("lo = %d" % mid) if good else ("hi = %d" % (mid - 1))
        rows.append((lo, hi, mid, "예" if good else "아니오", nxt))
        colors.append("missing" if k >= 3 else None)
    rows.append(("…", "…", "…", "", ""))
    colors.append("missing")
    row_table(c, 20, 50, ["lo", "hi", "mid", "판정", "다음"], rows, [44, 44, 44, 70, 76], row_h=28, colors=colors)
    top, bottom = 50 + 14 + 3 * 28, 50 + 14 + 6 * 28 - 4
    c.line([(306, top), (314, top), (314, bottom), (306, bottom)], "missing", 2)
    c.text(322, (top + bottom) / 2 - 10, "lo = 3, hi = 4에서", "missing", 12, anchor="lm")
    c.text(322, (top + bottom) / 2 + 10, "mid = 3이 되풀이됩니다", "missing", 12, anchor="lm")
    ceil_steps, answer = search_last_true(3, 4, ok)
    assert ceil_steps == [(3, 4, 4, True)] and answer == 4
    c.box(322, 52, 222, 86, fill="gutter", outline="string", radius=4)
    c.text(334, 66, "lo = 3, hi = 4에서 올려 잡으면", "string", 12, bold=True, anchor="lm")
    c.text(334, 90, "(3 + 4 + 1)을 2로 나눈 몫 4가 mid", "ink", 12, anchor="lm")
    c.text(334, 114, "예, lo = 4 = hi, 답 4", "string", 12, mono=True, anchor="lm")
    note(c, "lo = mid로 옮겨도 lo가 3에서 움직이지 않아 탐색이 끝나지 않습니다.")


# 3-B 수정 구역 배치

ZONES, K = [[0, 3], [20, 29]], 5  # 예 1


def batch(zones, D, K):
    """구역마다 (첫 자리 s, 놓은 위치들, 누적 개수)를 내고 K 에 닿으면 멈춤. 기준 풀이의 kth 와 같은 계산."""
    out, count, last = [], 0, None
    for l, r in zones:
        s = l if last is None else max(l, last + D)
        if s > r:
            out.append((s, [], count))
            continue
        c = (r - s) // D + 1
        count += c
        out.append((s, [s + i * D for i in range(c)], count))
        last = s + (c - 1) * D
        if count >= K:
            break
    return out


def kth(zones, D, K):
    seen = 0
    for s, spots, total in batch(zones, D, K):
        if total >= K:
            return spots[K - seen - 1]
        seen = total
    return -1


def bx(p):
    return 40 + 16 * p


def zone_line(c, y, labels=True):
    """예 1 의 구역을 띠로 칠한 0~30 수직선. labels 면 띠 위에 [l, r] 을 적음."""
    c.line([(bx(0) - 8, y), (bx(30) + 8, y)], "edge", 1)
    for l, r in ZONES:
        c.box(bx(l) - 5, y - 8, bx(r) - bx(l) + 10, 16, fill=ZONE, outline=None, radius=4)
        if labels:
            c.text((bx(l) + bx(r)) / 2, y - 22, "[%d, %d]" % (l, r), "builtin", 11, mono=True, anchor="ms")


@figure("3-ba", 560, 300)
def zone_batch(fig):
    D = 3
    placed = batch(ZONES, D, 99)
    assert [spots for _, spots, _ in placed] == [[0, 3], [20, 23, 26, 29]]
    c = fig.frame()
    head(c, "예 1: zones = [[0, 3], [20, 29]], D = 3으로 왼쪽부터 놓기")
    y = 96
    zone_line(c, y)
    for (s, spots, _) in placed:
        for p in spots:
            dot(c, bx(p), y, "def")
            c.text(bx(p), y + 12, str(p), "line_no", 11, mono=True, anchor="ma")
        for a, b in zip(spots, spots[1:]):
            c.bracket(bx(a) + 2, bx(b) - 2, y + 30, "3", "comment", 11, tick=4)
        c.text(bx(s), y + 58, "s = %d" % s, "def", 12, bold=True, mono=True, anchor="ma")
    c.text(20, 186, "[0, 3]: s = 0, (3 - 0)을 3으로 나눈 몫 1에 1을 더해 2개", "ink", 12)
    c.text(20, 208, "[20, 29]: s는 20과 3 + 3 = 6 가운데 큰 20", "ink", 12)
    c.text(20 + c.text_size("[20, 29]: ", 12)[0], 228, "(29 - 20)을 3으로 나눈 몫 3에 1을 더해 4개", "ink", 12)
    note(c, "구역 안에서는 s, s + D, s + 2D, …에 같은 간격으로 놓입니다.")


@figure("3-bd", 560, 300)
def zone_search(fig):
    hi0 = (ZONES[-1][1] - ZONES[0][0]) // (K - 1)
    steps, answer = search_last_true(1, hi0, lambda D: kth(ZONES, D, K) >= 0)
    assert hi0 == 7 and [s[2:] for s in steps] == [(4, False), (2, True), (3, True)] and answer == 3  # 해설의 표
    frames = [(1, hi0, None, 0, None, "hi는 (29 - 0)을 4로 나눈 몫 7이고, D는 1부터 7 사이에 있습니다.")]
    for lo, hi, mid, good in steps:
        parts = batch(ZONES, mid, K)
        for z in range(len(parts)):
            if z < len(parts) - 1:
                text = "D = %d: [0, 3]에 %d개를 한꺼번에 놓아 누적 %d개입니다." % (mid, len(parts[z][1]), parts[z][2])
                frames.append((lo, hi, mid, z, None, text))
            elif good:
                text = "D = %d: 누적 %d개로 K = 5에 닿아 예, lo = %d로 옮깁니다." % (mid, parts[z][2], mid)
                frames.append((lo, hi, mid, z, True, text))
            else:
                text = "D = %d: [20, 29]까지 %d개뿐이라 아니오, hi = %d로 옮깁니다." % (mid, parts[z][2], mid - 1)
                frames.append((lo, hi, mid, z, False, text))
    frames.append((answer, answer, answer, 1, "end", "lo와 hi가 3에서 만나고, D = 3의 K번째 수정 26이 답 [3, 26]입니다."))
    for k, (lo, hi, mid, upto, verdict, text) in enumerate(frames):
        c = fig.frame(2200 if verdict == "end" or k == 0 else 1600)
        head(c, "예 1: 수정 K = 5개를 놓을 수 있는 가장 큰 D 찾기")
        answers = [None] * hi0
        for d in range(1, hi0 + 1):
            if d <= lo:
                answers[d - 1] = "T"
            elif d > hi:
                answers[d - 1] = "F"
        if verdict in (True, False):
            answers[mid - 1] = "T" if verdict else "F"
        cells = strip(c, 60, 62, answers, 30, 4, 1, mid if verdict != "end" else None)
        c.text(48, 77, "D", "comment", 13, bold=True, mono=True, anchor="rm")
        pointers(c, mid_x(cells[lo - 1]), mid_x(cells[hi - 1]), 62)
        y = 186
        zone_line(c, y)
        total = 0
        if mid is not None:
            parts = batch(ZONES, mid, K)[:upto + 1]
            target = kth(ZONES, mid, K)
            for z, (s, spots, run) in enumerate(parts):
                fresh = z == upto and verdict != "end"
                for p in spots:
                    late = target >= 0 and p > target
                    dot(c, bx(p), y, DIM if late else ("string" if fresh else shade("string", 0.25)))
                    c.text(bx(p), y + 12, str(p), "line_no", 10, mono=True, anchor="ma")
                if fresh and spots:
                    w = c.text_size("+%d" % len(spots), 11, True, True)[0] + 8
                    c.tag(bx((ZONES[z][0] + ZONES[z][1]) / 2) - w / 2, y - 60, "+%d" % len(spots), "string", 11)
                total = run
            if verdict in (True, "end") and target >= 0:
                ring(c, bx(target), y)
                c.text(bx(target), y + 26, "K번째", "def", 11, bold=True, anchor="ma")
            c.number_board(352, 40, "판정하는 D", mid, "builtin" if verdict != "end" else "def", w=82)
        c.number_board(444, 40, "누적 개수 (K = 5)", total, "string" if total >= K else "missing", w=106)
        note(c, text)


@figure("3-bb", 560, 300)
def kth_spot(fig):
    D = 3
    parts = batch(ZONES, D, K)
    cnt, (s, spots, _) = parts[0][2], parts[1]
    spot = s + (K - cnt - 1) * D
    assert cnt == 2 and s == 20 and spot == kth(ZONES, D, K) == 26
    c = fig.frame()
    head(c, "예 1, D = 3: K = 5번째 수정이 놓이는 자리")
    y = 104
    zone_line(c, y)
    order = 0
    for _, places, _ in parts:
        for p in places:
            order += 1
            late = p > spot
            dot(c, bx(p), y, DIM if late else ("def" if p == spot else "string"))
            c.text(bx(p), y + 12, str(p), "line_no", 11, mono=True, anchor="ma")
            c.text(bx(p), y - 38, "%d번째" % order, "def" if p == spot else ("comment" if late else "ink"), 10, anchor="ms")
    ring(c, bx(spot), y)
    c.bracket(bx(0) - 4, bx(3) + 4, y + 30, "cnt = %d" % cnt, "comment", 12)
    c.text(bx(20), y + 34, "s = %d" % s, "string", 12, bold=True, mono=True, anchor="ma")
    c.arrow(bx(spot), 196, bx(spot), y + 30, "def", width=2)
    c.text(548, 210, "s + (K - cnt - 1) × D", "ink", 13, mono=True, anchor="rm")
    c.text(548, 234, "= %d + (%d - %d - 1) × %d = %d" % (s, K, cnt, D, spot), "def", 13, bold=True, mono=True, anchor="rm")
    note(c, "앞 구역까지 2개라 K번째 수정은 이 구역의 3번째 자리 26에 놓입니다.")


@figure("3-bc", 560, 300)
def greedy_proof(fig):
    D = 3
    other = [1, 20, 23, 26, 29]
    left = [p for _, spots, _ in batch(ZONES, D, K) for p in spots][:K]
    assert left == [0, 3, 20, 23, 26] and all(g <= o for g, o in zip(left, other))
    assert all(b - a >= D for a, b in zip(other, other[1:]))
    c = fig.frame()
    head(c, "예 1, D = 3: 어떤 배치 o와 왼쪽부터 놓은 배치 g")
    top, bottom = 82, 204
    for l, r in ZONES:
        c.text((bx(l) + bx(r)) / 2, 50, "[%d, %d]" % (l, r), "builtin", 11, mono=True, anchor="ms")
    for y, places, name, color_name in ((top, other, "o", "decorator"), (bottom, left, "g", "string")):
        zone_line(c, y, labels=False)
        c.text(18, y, name, color_name, 15, bold=True, mono=True, anchor="mm")
        for i, p in enumerate(places):
            dot(c, bx(p), y, color_name)
            c.text(bx(p), y + 12, str(p), "line_no", 10, mono=True, anchor="ma")
            if name == "o":
                c.text(bx(p), y - 12, "o%d" % (i + 1), color_name, 10, mono=True, anchor="ms")
            else:
                c.text(bx(p), y + 26, "g%d" % (i + 1), color_name, 10, mono=True, anchor="ma")
    for o, g in zip(other, left):
        c.arrow(bx(o), top + 28, bx(g), bottom - 12, "comment", width=1, head=6)
    c.text(150, (top + bottom) / 2 + 8, "gi ≤ oi", "def", 14, bold=True, mono=True, anchor="mm")
    note(c, "같은 번호끼리 이으면 g의 수정은 늘 o와 같은 자리이거나 그보다 왼쪽입니다.")
