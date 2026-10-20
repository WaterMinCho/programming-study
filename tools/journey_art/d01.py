# -*- coding: utf-8 -*-
"""던전 1 「향신료 시장」 해설 그림. 값은 문제마다 입출력 예와 explain.md 의 표를 그대로 씀.

  python3 tools/journey_art/render.py d01 [--check]
"""
from tools.journey_art.draw import figure, mid_x, mid_y, shade

TOP = 14  # 맨 위 설명 줄의 y


def head(c, s):
    c.text(20, TOP, s, "comment", 13)


def note(c, s):
    """아래 띠의 설명. 띠보다 길면 그리기 전에 멈춤."""
    if c.text_size(s, 13)[0] > c.width - 24:
        raise ValueError("설명이 그림 폭보다 깁니다: %s" % s)
    c.caption(s)


def dot(c, x, y, color_name, r=6):
    c.box(x - r, y - r, 2 * r, 2 * r, fill=color_name, outline=None, radius=r)


def span(rects, i, j):
    """칸 i..j(0부터, 양끝 포함)를 덮는 (x, y, w, h)."""
    x, y, _, h = rects[i]
    return (x, y, rects[j][0] + rects[j][2] - x, h)


def band(c, rects, i, j, y, h, fill, outline=None):
    """칸 i..j 아래에 같은 폭으로 띠를 그림."""
    x = rects[i][0]
    w = rects[j][0] + rects[j][2] - x
    return c.box(x, y, w, h, fill=fill, outline=outline, radius=3)


# 1-1 장부 정산

LEDGER = [("pepper", 3), ("salt", 5), ("pepper", 4), ("cumin", 2), ("salt", 1)]
LEDGER_NOTES = [
    "1번 줄 pepper 3: pepper 칸을 새로 만들고 3을 적습니다.",
    "2번 줄 salt 5: salt 칸을 새로 만들고 5를 적습니다.",
    "3번 줄 pepper 4: 이름으로 pepper 칸을 바로 찾아 7이 됩니다.",
    "4번 줄 cumin 2: cumin 칸을 새로 만들고 2를 적습니다.",
    "5번 줄 salt 1: salt 칸이 6이 되고, 장부를 한 번 읽어 끝납니다.",
]


def ledger_rows(c, x, y, current):
    """장부 줄 상자들. current 앞의 줄은 흐리게, current 줄은 테두리로 강조함."""
    rects = []
    for i, (name, qty) in enumerate(LEDGER):
        ry = y + i * 36
        done = i < current
        rect = c.box(x, ry, 130, 28, fill="gutter", outline="def" if i == current else "edge", width=2 if i == current else 1, radius=3)
        c.text(x + 12, ry + 14, "%s %d" % (name, qty), "comment" if done else "ink", 13, mono=True, anchor="lm")
        rects.append(rect)
    return rects


def item_box(c, x, y, name, value, strong=False):
    rect = c.box(x, y, 150, 40, fill=shade("builtin", 0.75) if strong else "gutter", outline="def" if strong else "edge", width=2 if strong else 1, radius=4)
    c.text(x + 12, y + 20, name, "ink", 13, mono=True, anchor="lm")
    c.text(x + 138, y + 20, str(value), "def" if strong else "ink", 17, bold=True, mono=True, anchor="rm")
    return rect


@figure("1-1a", 560, 300)
def ledger_to_cells(fig):
    for step, (name, qty) in enumerate(LEDGER):
        c = fig.frame(1500)
        head(c, "장부 다섯 줄을 위에서부터 읽으며 품목 칸에 더하기")
        lines = ledger_rows(c, 20, 50, step)
        c.text(20 + 65, 50 + 5 * 36 + 6, "장부", "comment", 12, anchor="ma")
        total, order = {}, []
        for item, q in LEDGER[:step + 1]:
            if item not in total:
                order.append(item)
            total[item] = total.get(item, 0) + q
        c.text(370 + 75, 36, "품목 칸 (딕셔너리, Map)", "comment", 12, anchor="ma")
        boxes = {}
        for k, item in enumerate(order):
            boxes[item] = item_box(c, 370, 60 + k * 56, item, total[item], strong=item == name)
        src, dst = lines[step], boxes[name]
        c.arrow(src[0] + src[2] + 6, mid_y(src), dst[0] - 6, mid_y(dst), "def")
        c.tag(dst[0] + dst[2] + 6, mid_y(dst) - 10, "+%d" % qty, "string")
        note(c, LEDGER_NOTES[step])
    c = fig.frame(2500)
    head(c, "4번 줄 cumin 2 를 넣을 때 두 방법이 이름을 찾는 길")
    c.text(20, 44, "딕셔너리, Map", "def", 13, bold=True)
    src = c.box(20, 120, 100, 28, fill="gutter", outline="def", width=2, radius=3)
    c.text(32, 134, "cumin 2", "ink", 13, mono=True, anchor="lm")
    cells = [("pepper", 7), ("salt", 5), ("cumin", 2)]
    for k, (item, value) in enumerate(cells):
        y = 72 + k * 50
        rect = c.box(160, y, 100, 36, fill=shade("builtin", 0.75) if item == "cumin" else "gutter", outline="def" if item == "cumin" else "edge", radius=4)
        c.text(170, y + 18, item, "ink", 12, mono=True, anchor="lm")
        c.text(250, y + 18, str(value), "ink", 14, bold=True, mono=True, anchor="rm")
        if item == "cumin":
            c.arrow(src[0] + src[2] + 4, mid_y(src), rect[0] - 4, mid_y(rect), "def")
    c.text(20, 236, "이름으로 칸을 바로 찾음", "comment", 12)
    c.line([(285, 44), (285, 250)], "edge", 1)
    c.text(305, 44, "리스트", "decorator", 13, bold=True)
    src = c.box(305, 120, 90, 28, fill="gutter", outline="decorator", width=2, radius=3)
    c.text(317, 134, "cumin 2", "ink", 13, mono=True, anchor="lm")
    for k, (item, value) in enumerate(cells):
        y = 72 + k * 50
        new = item == "cumin"
        rect = c.box(455, y, 90, 36, fill=shade("decorator", 0.75) if new else "gutter", outline="decorator" if new else "edge", radius=4)
        c.text(465, y + 18, item, "ink", 12, mono=True, anchor="lm")
        c.text(535, y + 18, str(value), "ink", 14, bold=True, mono=True, anchor="rm")
        x1, y1, x2, y2 = src[0] + src[2] + 4, mid_y(src), rect[0] - 4, mid_y(rect)
        c.arrow(x1, y1, x2, y2, "decorator" if new else "comment", width=2 if new else 1)
        if new:
            c.text(mid_x(rect), y + 40, "없어서 끝에 붙임", "decorator", 10, anchor="ma")
        else:
            label = "%d. 다름" % (k + 1)
            w = c.text_size(label, 10, True, True)[0] + 8
            c.tag(x1 + (x2 - x1) * 0.5 - w / 2, y1 + (y2 - y1) * 0.5 - 9, label, "comment", size=10)
    c.text(305, 236, "앞에서부터 이름을 하나씩 비교함", "comment", 12)
    note(c, "리스트는 이름을 찾을 때마다 목록을 처음부터 훑습니다.")


@figure("1-1b", 560, 320)
def sort_cards(fig):
    c = fig.frame()
    head(c, "예 2: 합을 모은 표를 정렬 키 (-합, 이름) 으로 줄 세우기")
    c.text(20, 52, "모은 표", "comment", 12)
    gathered = [("mint", 10), ("basil", 10), ("anise", 6), ("clove", 10)]
    for k, (name, total) in enumerate(gathered):
        x = 90 + k * 112
        c.box(x, 42, 100, 34, fill="gutter", outline="edge", radius=4)
        c.text(x + 10, 59, name, "ink", 12, mono=True, anchor="lm")
        c.text(x + 90, 59, str(total), "ink", 13, bold=True, mono=True, anchor="rm")
    c.arrow(300, 84, 300, 118, "def")
    c.text(312, 94, "sorted(key=lambda item: (-item[1], item[0]))", "comment", 11, mono=True)
    ordered = [("basil", 10), ("clove", 10), ("mint", 10)]
    cards = []
    for k, (name, total) in enumerate(ordered):
        x = 40 + k * 130
        card = c.box(x, 142, 118, 92, fill=shade("builtin", 0.75), outline="def", width=2, radius=6)
        c.text(x + 59, 168, "-%d" % total, "comment", 18, bold=True, mono=True, anchor="mm")
        c.line([(x + 14, 186), (x + 104, 186)], "edge", 1)
        width = c.text_size(name, 18, True, True)[0]
        left = x + 59 - width / 2
        first = c.text(left, 210, name[0], "def", 18, bold=True, mono=True, anchor="lm")
        c.text(left + first[0], 210, name[1:], "ink", 18, bold=True, mono=True, anchor="lm")
        cards.append(card)
    x = 40 + 3 * 130
    c.box(x, 160, 90, 56, fill="gutter", outline="edge", radius=6)
    c.text(x + 45, 176, "-6", "comment", 14, bold=True, mono=True, anchor="mm")
    c.text(x + 45, 202, "anise", "ink", 14, bold=True, mono=True, anchor="mm")
    c.bracket(cards[0][0], cards[2][0] + cards[2][2], 136, "첫째 기준 -10 이 모두 같음", below=False)
    c.bracket(cards[0][0], cards[2][0] + cards[2][2], 240, "둘째 기준 이름: b < c < m", "def")
    c.text(x + 45, 228, "합 6 이 가장 작음", "comment", 11, anchor="ma")
    note(c, "합이 같은 세 장은 이름 순서대로 basil, clove, mint가 됩니다.")


@figure("1-1c", 560, 380)
def js_traps(fig):
    c = fig.frame()
    head(c, "Node 에서 그대로 돌려 본 JavaScript 함정 세 개")
    lines = [
        ("// 비교 함수 없이 숫자 정렬", "comment"),
        ("> [10, 9, 2, 100].sort()", "ink"),
        ("[10, 100, 2, 9]", "missing"),
        ("// 일반 객체 {} 를 표로 쓰기", "comment"),
        ("> const total = {};", "ink"),
        ('> total["constructor"] = (total["constructor"] || 0) + 9;', "ink"),
        ("'function Object() { [native code] }9'", "missing"),
        ('> total["__proto__"] = (total["__proto__"] || 0) + 2;', "ink"),
        ("> Object.keys(total)", "ink"),
        ("[ 'constructor' ]", "missing"),
        ("// true/false 를 돌려주는 비교 함수. nums 는 1~25 를 섞은 배열", "comment"),
        ("> nums.slice(0, 8)", "ink"),
        ("[13, 2, 25, 7, 18, 1, 22, 9]", "string"),
        ("> nums.slice().sort((a, b) => a > b).slice(0, 8)", "ink"),
        ("[13, 2, 25, 7, 18, 1, 22, 9]", "missing"),
    ]
    c.box(16, 38, 528, len(lines) * 19 + 16, fill="gutter", outline="edge", radius=4)
    for k, (s, color_name) in enumerate(lines):
        c.text(28, 46 + k * 19, s, color_name, 12, mono=True)
    note(c, "빨간 줄이 기대와 다른 결과입니다. 셋째 정렬은 순서를 바꾸지 않습니다.")


# 1-2 낙타 짐 짝짓기

CAMEL_W, CAMEL_X = [1, 3, 4, 5], 6
CAMEL_STEPS = [  # (l, r, 이번에 더하는 수, 빠지는 r 막대들, 설명)
    (0, 3, None, [], "weights를 정렬한 w의 양쪽 끝에 l과 r을 둡니다."),
    (0, 3, 3, [], "1 + 5 = 6이 X 이하라 1번부터 3번까지 3개를 한꺼번에 셉니다."),
    (1, 3, 0, [3], "3 + 5 = 8은 X보다 커서 5는 남은 짐과 짝이 되지 않습니다. r을 내립니다."),
    (1, 2, 0, [3, 2], "3 + 4 = 7도 X보다 커서 r을 한 칸 더 내립니다."),
    (1, 1, None, [3, 2], "l과 r이 만나 반복이 끝나고 답은 3입니다."),
]


@figure("1-2a", 560, 300)
def camel_pointers(fig):
    answer = 0
    for l, r, added, gone, text in CAMEL_STEPS:
        c = fig.frame(1600)
        head(c, "예 1: weights = [5, 1, 3, 4], X = 6 을 정렬한 w = [1, 3, 4, 5]")
        marks = {i: shade("builtin", 0.75) for i in range(l)}
        if added:
            marks.update({i: "string" for i in range(l + 1, r + 1)})
        marks.update({i: shade("comment", 0.75) for i in gone})
        bars = c.bars(50, 200, CAMEL_W, width=50, gap=30, height=120, vmax=5, marks=marks)
        for i, rect in enumerate(bars):
            c.text(mid_x(rect), 205, str(i), "line_no", 10, mono=True, anchor="ma")
        shift = 10 if l == r else 0  # 두 포인터가 한 막대에 모이면 옆으로 비켜 그림
        c.pointer(mid_x(bars[l]) - shift, 222, "l", above=False)
        c.pointer(mid_x(bars[r]) + shift, 222, "r", "decorator", above=False)
        if added is not None:
            answer += added
            pair = CAMEL_W[l] + CAMEL_W[r]
            c.number_board(380, 60, "w[l] + w[r]", pair, "string" if pair <= CAMEL_X else "missing", w=120)
            if added:
                c.bracket(bars[l + 1][0], bars[r][0] + bars[r][2], 214 + 30, "l과 짝이 되는 짐 %d개" % added, "string")
        c.number_board(380, 120, "답", answer, w=120)
        if added:
            c.tag(510, 132, "+%d" % added, "string")
        c.text(380, 186, "X = %d" % CAMEL_X, "comment", 13, mono=True)
        note(c, text)


@figure("1-2b", 560, 340)
def pair_triangle(fig):
    c = fig.frame()
    w, limit = [1, 2, 3, 4, 5, 6, 7, 8], 9
    head(c, "w = [1, 2, ..., 8], X = 9 에서 짐 쌍 (i, j) 의 표 (i < j)")
    size, gap, x0, y0 = 26, 2, 70, 66
    step = size + gap
    for j in range(1, len(w)):
        c.text(x0 + j * step + size / 2, y0 - 6, str(j), "line_no", 10, mono=True, anchor="ms")
    for i in range(len(w) - 1):
        c.text(x0 + (i + 1) * step - 8, y0 + i * step + size / 2, str(i), "line_no", 10, mono=True, anchor="rm")
    centers = {}
    for i in range(len(w)):
        for j in range(i + 1, len(w)):
            fill = shade("string", 0.5) if w[i] + w[j] <= limit else shade("comment", 0.75)
            rect = c.box(x0 + j * step, y0 + i * step, size, size, fill=fill, outline="edge", radius=2)
            centers[(i, j)] = (mid_x(rect), mid_y(rect))
    path, l, r = [], 0, len(w) - 1
    while l < r:
        path.append((l, r))
        if w[l] + w[r] <= limit:
            l += 1
        else:
            r -= 1
    c.line([centers[p] for p in path], "def", 2)
    for p in path:
        x, y = centers[p]
        c.box(x - size / 2, y - size / 2, size, size, fill=None, outline="def", width=2, radius=2)
    pairs = len(w) * (len(w) - 1) // 2
    c.number_board(340, 70, "이중 반복이 보는 쌍", pairs, "ink", w=150)
    c.number_board(340, 130, "l, r 이 보는 쌍", len(path), "def", w=150)
    c.box(340, 200, 14, 14, fill=shade("string", 0.5), outline="edge", radius=2)
    c.text(362, 207, "합이 9 이하", "comment", 12, anchor="lm")
    c.box(340, 222, 14, 14, fill=shade("comment", 0.75), outline="edge", radius=2)
    c.text(362, 229, "합이 9 보다 큼", "comment", 12, anchor="lm")
    c.box(340, 244, 14, 14, fill=None, outline="def", width=2, radius=2)
    c.text(362, 251, "l, r 이 지나간 쌍", "comment", 12, anchor="lm")
    c.text(340, 276, "줄 번호가 i, 칸 번호가 j 입니다", "comment", 11, anchor="lm")
    note(c, "이중 반복은 삼각형 28칸을 모두, l과 r은 경계를 따라 7칸만 봅니다.")


# 1-3 대상단 하루 일정

FUEL = [2, 1, 3, 2]
FUEL_STEPS = [  # (l, r, 창의 합, 더하는 수 또는 None(넘침), 설명)
    (0, 0, 2, 1, "r = 0: 합 2가 S 이하라 1을 더합니다."),
    (0, 1, 3, 2, "r = 1: 합 3, 왼쪽 끝이 0번이나 1번인 묶음 2개를 더합니다."),
    (0, 2, 6, None, "r = 2: 합 6이 S = 5를 넘어 l을 당겨야 합니다."),
    (1, 2, 4, 2, "fuel[0]을 빼 합이 4가 되고, r - l + 1 = 2를 더합니다."),
    (1, 3, 6, None, "r = 3: 합 6이 다시 S를 넘습니다."),
    (2, 3, 5, 2, "fuel[1]을 빼 합이 5가 되고 2를 더합니다."),
]


def fuel_frame(c, l, r, total, over):
    head(c, "예 1: fuel = [2, 1, 3, 2] 에서 합이 S = 5 이하인 묶음 세기 g(5)")
    marks = {}
    if r is not None:
        color_name = shade("missing", 0.5) if over else shade("builtin", 0.5)
        marks = {i: color_name for i in range(l, r + 1)}
    rects = c.cells(40, 70, FUEL, size=48, gap=8, marks=marks)
    if r is not None:
        c.pointer(mid_x(rects[l]), 70, "l")
        c.pointer(mid_x(rects[r]), 70 + 48, "r", "decorator", above=False)
        c.number_board(300, 60, "창의 합", total, "missing" if over else "builtin", w=110)


@figure("1-3a", 560, 300)
def fuel_window(fig):
    c = fig.frame(1600)
    fuel_frame(c, 0, None, 0, False)
    c.number_board(420, 60, "g(5)", 0, w=110)
    c.text(40, 160, "r 마다 더한 r - l + 1", "comment", 12)
    note(c, "창은 비어 있고, r을 0번부터 한 칸씩 늘립니다.")
    adds = []
    for l, r, total, add, text in FUEL_STEPS:
        c = fig.frame(1600)
        fuel_frame(c, l, r, total, add is None)
        if add is not None:
            adds.append(add)
        c.number_board(420, 60, "g(5)", sum(adds), w=110)
        if add:
            c.tag(500, 72, "+%d" % add, "string")
        c.text(40, 160, "r 마다 더한 r - l + 1", "comment", 12)
        bars = c.bars(40, 244, adds, width=48, gap=8, height=56, vmax=2, color_name=shade("string", 0.25))
        for i, rect in enumerate(bars):
            c.text(mid_x(rect), 248, "r=%d" % i, "line_no", 10, mono=True, anchor="ma")
        note(c, text)
    c = fig.frame(2200)
    fuel_frame(c, 0, None, 0, False)
    c.number_board(300, 60, "g(5)", 7, w=110)
    c.number_board(420, 60, "g(2)", 3, "missing", w=110)
    c.text(40, 160, "r 마다 더한 수:", "comment", 12)
    c.text(140, 160, "g(5)", "string", 12, bold=True, mono=True)
    c.text(182, 160, "g(2)", "missing", 12, bold=True, mono=True)
    bars = c.bars(40, 244, [1, 2, 2, 2], width=22, gap=34, height=56, vmax=2, color_name=shade("string", 0.25))
    c.bars(66, 244, [1, 1, 0, 1], width=22, gap=34, height=56, vmax=2, color_name=shade("missing", 0.5))
    for i, rect in enumerate(bars):
        c.text(rect[0] + 24, 248, "r=%d" % i, "line_no", 10, mono=True, anchor="ma")
    c.text(300, 140, "g(5) = 1 + 2 + 2 + 2 = 7", "ink", 13, mono=True)
    c.text(300, 162, "g(2) = 1 + 1 + 0 + 1 = 3", "ink", 13, mono=True)
    c.text(300, 196, "답 = 7 - 3 = 4", "def", 15, bold=True, mono=True)
    note(c, "같은 방법으로 g(2) = 3을 세고, 답은 g(5) - g(2) = 4입니다.")


@figure("1-3b", 560, 280)
def range_band(fig):
    c = fig.frame()
    head(c, "예 1 의 묶음 10개를 합의 자리에 쌓은 수직선 (L = 3, R = 5)")
    sums = [1, 2, 2, 3, 3, 4, 5, 6, 6, 8]

    def px(v):
        return 50 + v * 54

    base = 166
    c.box(px(2.5), 46, px(5.5) - px(2.5), base - 46, fill=None, outline="string", width=2, radius=4)
    c.line([(px(0) - 10, base), (px(8) + 14, base)], "edge", 1)
    for v in range(9):
        c.line([(px(v), base), (px(v), base + 5)], "edge", 1)
        c.text(px(v), base + 8, str(v), "line_no", 11, mono=True, anchor="ma")
    stack = {}
    for v in sums:
        k = stack.get(v, 0)
        stack[v] = k + 1
        color_name = "string" if 3 <= v <= 5 else ("missing" if v <= 2 else "comment")
        dot(c, px(v), base - 14 - k * 18, color_name)
    c.box(px(0), 196, px(5.5) - px(0), 18, fill=shade("builtin", 0.5), outline=None, radius=3)
    c.text(px(5.5) + 8, 205, "합 ≤ 5 : g(5) = 7", "builtin", 12, mono=True, anchor="lm")
    c.box(px(0), 220, px(2.5) - px(0), 18, fill=shade("missing", 0.75), outline=None, radius=3)
    c.hatch((px(0) + 1, 221, px(2.5) - px(0) - 2, 16), shade("missing", 0.25))
    c.text(px(2.5) + 8, 229, "합 ≤ 2 : g(2) = 3", "missing", 12, mono=True, anchor="lm")
    c.text(px(5.5) + 16, 70, "남는 띠", "string", 12, bold=True)
    c.text(px(5.5) + 16, 88, "3 ≤ 합 ≤ 5", "string", 12, mono=True)
    c.text(px(5.5) + 16, 106, "7 - 3 = 4개", "string", 12, mono=True)
    note(c, "5 이하 7개에서 2 이하 3개를 빼면 3 이상 5 이하 4개가 남습니다.")


def pull_rows(c, values, last, rows, size):
    """values 의 0..last 칸 창에서 왼쪽 끝 l 을 한 칸씩 당긴 줄들. rows 는 (l, 창의 합, 설명).
    합이 앞 줄보다 커진 줄은 빨갛게 그림. l 이 last 를 지나 창이 비면 테두리를 그리지 않음."""
    bx = 80 + len(values) * (size + 6) + 26
    prev = None
    prev_total = None
    for k, (l, total, why) in enumerate(rows):
        y = 52 + k * 66
        c.text(20, y + size / 2, "l = %d" % l, "def", 13, bold=True, mono=True, anchor="lm")
        marks = {i: shade("builtin", 0.5) for i in range(l, last + 1)}
        marks.update({i: shade("comment", 0.75) for i in range(l)})
        rects = c.cells(80, y, values, size=size, gap=6, marks=marks)
        if l <= last:
            c.highlight(span(rects, l, last), "def", width=1)
        up = prev_total is not None and total > prev_total
        prev_total = total
        board = c.number_board(bx, y + size / 2 - 23, "창의 합", total, "missing" if up else "builtin", w=96)
        if prev:
            c.arrow(mid_x(board), prev[1] + prev[3] + 2, mid_x(board), board[1] - 2, "missing" if up else "comment", width=2 if up else 1, head=6 if up else 5)
        if why:
            c.text(bx + 108, y + size / 2, why, "missing" if up else "comment", 12, bold=up, anchor="lm")
        prev = board


@figure("1-3c", 560, 280)
def negative_breaks(fig):
    c = fig.frame()
    head(c, "음수가 섞인 [2, -3, 4] 에서 왼쪽 끝 l 을 한 칸씩 당기기")
    pull_rows(c, [2, -3, 4], 2, [(0, 3, None), (1, 1, "2 를 빼서 3 → 1"), (2, 4, "-3 을 빼서 1 → 4")], 40)
    note(c, "음수를 빼면 합이 커지므로, l을 당겨도 합이 줄지 않을 수 있습니다.")


# 1-4 주문서를 채우는 최단 진열

STALLS = ["salt", "cumin", "cumin", "pepper", "cumin", "salt", "cumin"]
NEED = [("cumin", 2), ("salt", 1)]
ORDER_STEPS = [  # (l, r, cumin 개수, salt 개수, best, 테두리 구간, 설명). 노점 번호는 1부터
    (1, 1, 0, 1, 0, None, "r = 1 salt: salt가 필요 수 1에 닿아 채워진 종류가 1입니다."),
    (1, 2, 1, 1, 0, None, "r = 2 cumin: cumin은 1개라 아직 필요 수 2에 못 미칩니다."),
    (1, 3, 2, 1, 0, None, "r = 3 cumin: cumin도 2개가 되어 주문이 처음 찹니다."),
    (2, 3, 2, 0, 3, (1, 3), "salt를 빼면 주문이 깨지므로 1~3번 길이 3을 적고 뺍니다."),
    (2, 4, 2, 0, 3, None, "r = 4 pepper: 주문서에 없는 향신료라 표에 더하지 않습니다."),
    (2, 5, 3, 0, 3, None, "r = 5 cumin: 3개로 늘어도 채워진 종류는 바뀌지 않습니다."),
    (2, 6, 3, 1, 3, None, "r = 6 salt: salt가 다시 들어와 주문이 찹니다."),
    (3, 6, 2, 1, 3, None, "2번 cumin은 남는 하나라 빼도 주문이 그대로 찹니다."),
    (4, 6, 1, 1, 3, (3, 6), "3번 cumin을 빼면 깨지므로 3~6번 길이 4를 재고 뺍니다."),
    (6, 7, 1, 1, 3, (5, 7), "r = 7에서 다시 차고, pepper를 뺀 뒤 5~7번 길이 3을 잽니다."),
]


@figure("1-4a", 560, 340)
def order_window(fig):
    for l, r, cumin, salt, best, border, text in ORDER_STEPS:
        c = fig.frame(1700)
        head(c, "예 1: 주문서 cumin 2개, salt 1개")
        marks = {i - 1: shade("builtin", 0.5) for i in range(l, r + 1)}
        rects = c.cells(20, 66, STALLS, size=60, gap=6, marks=marks, text_px=12, index=1)
        c.pointer(mid_x(rects[l - 1]), 66, "l")
        c.pointer(mid_x(rects[r - 1]) + (8 if l == r else 0), 66 + 60 + 16, "r", "decorator", above=False)
        if border:
            c.highlight(span(rects, border[0] - 1, border[1] - 1), "def", width=2, pad=4)
            c.tag(rects[border[1] - 1][0] + 30, 40, "길이 %d" % (border[1] - border[0] + 1), "def")
        have = {"cumin": cumin, "salt": salt}
        ok = sum(1 for name, need in NEED if have[name] >= need)
        base = 280
        for k, (name, need) in enumerate(NEED):
            x = 60 + k * 120
            filled = have[name] >= need
            h = 26 * have[name]
            if h:
                c.box(x, base - h, 44, h, fill="string" if filled else shade("builtin", 0.25), outline=None)
            c.line([(x - 8, base - 26 * need), (x + 52, base - 26 * need)], "def", 2)
            c.text(x + 22, base - 84, "%d/%d" % (have[name], need), "ink", 12, mono=True, anchor="ms")
            dot(c, x + 52, base - 89, "string" if filled else shade("comment", 0.75), r=6)
            c.text(x + 22, base + 4, name, "comment", 11, mono=True, anchor="ma")
        c.line([(40, base), (284, base)], "edge", 1)
        c.line([(300, 254), (322, 254)], "def", 2)
        c.text(330, 254, "필요 수", "comment", 11, anchor="lm")
        dot(c, 410, 254, "string", r=6)
        c.text(422, 254, "채운 품목", "comment", 11, anchor="lm")
        c.number_board(300, 176, "채워진 종류", "%d/2" % ok, "string" if ok == 2 else "missing", w=110)
        c.number_board(420, 176, "가장 짧은 길이", best if best else "-", w=110)
        note(c, text)


@figure("1-4b", 560, 330)
def shortest_per_r(fig):
    c = fig.frame()
    head(c, "예 1: 오른쪽 끝 r 마다 r 에서 끝나며 주문을 채우는 가장 짧은 구간")
    rects = c.cells(90, 44, STALLS, size=46, gap=4, text_px=10, index=1)
    shortest = {3: 1, 4: 1, 5: 1, 6: 3, 7: 5}  # r: 그 구간의 왼쪽 끝
    for r in range(1, 8):
        y = 118 + (r - 1) * 24
        c.text(20, y + 8, "r = %d" % r, "comment", 12, mono=True, anchor="lm")
        if r not in shortest:
            c.text(rects[0][0], y + 8, "아직 주문을 채우는 구간이 없음", "comment", 11, anchor="lm")
            continue
        l = shortest[r]
        best = r - l + 1 == 3
        rect = band(c, rects, l - 1, r - 1, y, 16, "string" if best else shade("builtin", 0.5))
        if best:
            c.highlight(rect, "def", width=2, pad=2)
        c.text(452, y + 8, "%d~%d번 길이 %d" % (l, r, r - l + 1), "def" if best else "ink", 12, anchor="lm")
    c.number_board(462, 44, "답", 3, w=80)
    note(c, "길이 3인 줄이 가장 짧으므로 답은 3입니다.")


# 1-5 음수가 섞인 장부

TARGET = 2
PREFIX = [0, 3, 2, 4, 2, 3]  # 예 1 의 deltas = [3, -1, 2, -2, 1] 의 누적합


@figure("1-5b", 560, 300)
def prefix_pairs(fig):
    c = fig.frame()
    head(c, "예 1: deltas = [3, -1, 2, -2, 1] 의 누적합 P 꺾은선 (K = 2)")

    def px(j):
        return 60 + j * 62

    def py(v):
        return 222 - v * 36

    for v in range(5):
        c.line([(px(0) - 14, py(v)), (px(5) + 14, py(v))], "edge" if v == 0 else shade("edge", 0.5), 1)
        c.text(px(0) - 22, py(v), str(v), "line_no", 10, mono=True, anchor="rm")
    for j in range(6):
        c.text(px(j), py(0) + 22, "P[%d]" % j, "line_no", 10, mono=True, anchor="ma")
    c.line([(px(j), py(v)) for j, v in enumerate(PREFIX)], "builtin", 2)
    pairs = [(0, 2, "def", 0, "[3, -1]"), (2, 3, "decorator", 0, "[2]"), (0, 4, "string", 10, "[3, -1, 2, -2]")]
    for i, j, color_name, drop, _ in pairs:
        y = py(PREFIX[i]) + drop
        if drop:
            c.line([(px(i), py(PREFIX[i])), (px(i), y)], color_name, 1)
        c.arrow(px(i) + 4, y, px(j) - 2, y, color_name, width=2, head=6)
        c.line([(px(j), y), (px(j), py(PREFIX[j]))], color_name, 1)
        c.text(px(j) + 5, (y + py(PREFIX[j])) / 2, "+2", color_name, 11, bold=True, mono=True, anchor="lm")
    for j, v in enumerate(PREFIX):
        dot(c, px(j), py(v), "ink", r=5)
        c.text(px(j), py(v) - 9, str(v), "ink", 11, mono=True, anchor="ms")
    for k, (i, j, color_name, _, label) in enumerate(pairs):
        y = 70 + k * 46
        c.box(420, y, 12, 12, fill=color_name, outline=None, radius=2)
        c.text(440, y + 6, "P[%d] - P[%d]" % (j, i), color_name, 12, mono=True, anchor="lm")
        c.text(440, y + 24, label, "comment", 12, mono=True, anchor="lm")
    note(c, "높이가 K = 2만큼 차이 나는 점 쌍이 합이 2인 묶음 셋입니다.")


PREFIX_STEPS = [  # (j, 답에 더한 수, 설명)
    (0, None, "P[0] = 0을 표에 한 번 넣고 시작합니다."),
    (1, 0, "P = 3: 3 - 2 = 1은 표에 없어 0을 더하고 3을 적습니다."),
    (2, 1, "P = 2: 0이 한 번 나왔으므로 답에 1을 더합니다."),
    (3, 1, "P = 4: 2가 한 번 나왔으므로 답은 2가 됩니다."),
    (4, 1, "P = 2: 0을 읽어 답이 3이 되고 2의 횟수가 2로 오릅니다."),
    (5, 0, "P = 3: 1은 표에 없어 답이 3에서 늘지 않습니다."),
]


@figure("1-5c", 560, 300)
def prefix_scan(fig):
    def px(i):
        return 40 + i * 46

    def py(v):
        return 216 - v * 32

    answer = 0
    for j, added, text in PREFIX_STEPS:
        c = fig.frame(1700)
        head(c, "누적합 P 를 왼쪽부터 훑으며 표에서 P - K 의 횟수 읽기 (K = 2)")
        for v in range(5):
            c.line([(px(0) - 10, py(v)), (px(5) + 10, py(v))], "edge" if v == 0 else shade("edge", 0.5), 1)
            c.text(px(0) - 16, py(v), str(v), "line_no", 10, mono=True, anchor="rm")
        c.line([(px(i), py(v)) for i, v in enumerate(PREFIX[:j + 1])], "builtin", 2)
        for i, v in enumerate(PREFIX[:j + 1]):
            dot(c, px(i), py(v), "def" if i == j else "ink", r=6 if i == j else 4)
        for i in range(6):
            c.text(px(i), py(0) + 8, "P[%d]" % i, "line_no", 9, mono=True, anchor="ma")
        counts = {}
        for v in PREFIX[:j]:
            counts[v] = counts.get(v, 0) + 1
        p = PREFIX[j]
        want = p - TARGET
        if added is not None:
            answer += added
            c.line([(px(0) - 10, py(want)), (px(j), py(want))], "decorator", 1)
            c.line([(px(j), py(want)), (px(j), py(p))], "decorator", 1)
            c.text(px(j) + 6, (py(want) + py(p)) / 2, "K", "decorator", 11, bold=True, mono=True, anchor="lm")
        counts[p] = counts.get(p, 0) + 1
        c.text(330, 46, "누적합", "comment", 11, anchor="ma")
        c.text(400, 46, "횟수", "comment", 11, anchor="ma")
        for k, value in enumerate(sorted(counts)):
            y = 62 + k * 34
            fill = shade("string", 0.5) if value == p else "gutter"
            c.box(300, y, 60, 28, fill=fill, outline="edge", radius=3)
            c.box(370, y, 60, 28, fill=fill, outline="edge", radius=3)
            c.text(330, y + 14, str(value), "ink", 13, bold=True, mono=True, anchor="mm")
            c.text(400, y + 14, str(counts[value]), "ink", 13, bold=True, mono=True, anchor="mm")
            if added is not None and value == want:
                c.highlight((300, y, 130, 28), "decorator", width=2)
        if added is not None:
            c.text(452, 124, "P - K = %d" % want, "decorator", 12, mono=True)
            c.text(452, 142, "읽은 횟수 %d" % added, "decorator", 12)
        c.number_board(452, 62, "답", answer, w=90)
        if added:
            c.tag(510, 52, "+%d" % added, "string")
        note(c, text)


@figure("1-5a", 560, 280)
def window_breaks(fig):
    c = fig.frame()
    head(c, "[-2, 5, -1], K = 2 에서 r 이 5 에 닿아 합이 K 를 넘을 때 l 을 당기기")
    pull_rows(c, [-2, 5, -1], 1, [(0, 3, "합 3 > K = 2"), (1, 5, "-2 를 빼서 3 → 5"), (2, 0, "5 를 빼서 5 → 0")], 40)
    note(c, "손해 -2를 빼자 합이 3에서 5로 오히려 커집니다.")


# 1-B 감사관의 구간 세기

AUDIT = ["salt", "mint", "salt", "mint", "cumin"]


@figure("1-ba", 560, 320)
def one_window_misses(fig):
    c = fig.frame()
    head(c, "예 1 (K = 2, C = 2): 오른쪽 끝이 4번인 구간들")
    rects = c.cells(110, 58, AUDIT, size=58, gap=6, text_px=12, index=1)
    c.pointer(mid_x(rects[3]), 58, "r", "decorator")
    for k, l in enumerate([1, 2, 3, 4]):
        y = 150 + k * 32
        kinds = len(set(AUDIT[l - 1:4]))
        exact = kinds == 2
        c.text(20, y + 10, "%d~4번" % l, "comment", 12, mono=True, anchor="lm")
        rect = band(c, rects, l - 1, 3, y, 20, shade("string", 0.5) if exact else shade("comment", 0.75))
        c.text(rect[0] + rect[2] + 12, y + 10, "종류 %d" % kinds, "ink" if exact else "comment", 12, anchor="lm")
        if l == 1:
            c.highlight(rect, "def", width=2)
            c.text(rect[0] + rect[2] + 70, y + 10, "창 하나가 보는 구간", "def", 12, bold=True, anchor="lm")
        elif exact:
            c.text(rect[0] + rect[2] + 70, y + 10, "창이 놓치는 구간", "missing", 12, anchor="lm")
    note(c, "종류가 정확히 2인 구간이 셋인데, 창 하나는 1~4번만 봅니다.")


AUDIT_STEPS = [  # (예, C, r, f(2)의 l, f(1)의 l, 이번에 뺀 칸들, 답, 설명). 번호는 1부터
    (1, 2, None, None, None, [], 0, "같은 r에서 두 창을 위아래로 놓고 길이의 차를 셉니다."),
    (1, 2, 1, 1, 1, [], 0, "r = 1: 두 창이 같아 차는 0입니다."),
    (1, 2, 2, 1, 2, [], 1, "r = 2: 아래 창은 1가지를 넘어 1번을 빼고, 차 1을 더합니다."),
    (1, 2, 3, 1, 3, [], 3, "r = 3: 위 창 3칸, 아래 창 1칸이라 차 2를 더합니다."),
    (1, 2, 4, 1, 4, [], 6, "r = 4: 차 3을 더합니다. 그림 1-Ba의 세 구간입니다."),
    (1, 2, 5, 4, 5, [], 7, "r = 5: cumin이 들어와 위 창이 4번까지 줄고, 답은 7입니다."),
    (2, 1, 3, 2, 3, [(0, 1), (1, 2)], 2, "예 2 (C = 1)의 r = 3: 두 창이 함께 한 칸씩 줄어듭니다."),
    (2, 1, 5, 4, 5, [], 4, "예 2는 r마다 차가 0, 1, 1, 1, 1이라 답은 4입니다."),
]


@figure("1-bb", 560, 300)
def two_windows(fig):
    for case, cap, r, a, b, gone, answer, text in AUDIT_STEPS:
        c = fig.frame(1800)
        head(c, "예 %d: K = 2, C = %d. 위는 2가지 이하 창, 아래는 1가지 이하 창" % (case, cap))
        rects = c.cells(120, 62, AUDIT, size=56, gap=6, text_px=12, index=1)
        c.text(20, 160, "2가지 이하", "builtin", 12, bold=True, anchor="lm")
        c.text(20, 196, "1가지 이하", "decorator", 12, bold=True, anchor="lm")
        if r is not None:
            c.pointer(mid_x(rects[r - 1]), 62, "r", "decorator")
            for row, i in gone:
                ghost = band(c, rects, i - 1, i - 1, 148 + row * 36, 24, shade("missing", 0.75))
                c.text(mid_x(ghost), mid_y(ghost), "뺀 칸", "ink", 11, anchor="mm")
            top = band(c, rects, a - 1, r - 1, 148, 24, shade("builtin", 0.5))
            band(c, rects, b - 1, r - 1, 184, 24, shade("decorator", 0.5))
            if b > a:
                diff = (top[0], 149, rects[b - 2][0] + rects[b - 2][2] - top[0], 22)
                c.hatch(diff, "string")
                c.text(mid_x(diff), 226, "차 %d" % (b - a), "string", 12, bold=True, anchor="ma")
        c.number_board(470, 140, "답", answer, w=80)
        note(c, text)


@figure("1-bc", 560, 350)
def cap_one_side(fig):
    c = fig.frame()
    stalls = ["salt", "salt", "salt", "mint", "mint", "mint"]  # 숨은 테스트가 아닌 그림용 입력. 답 4
    head(c, "K = 2, C = 2 에서 아래 창만 C 를 빼고 셀 때")
    panels = [(3, 2, 1, "1~3번: salt 3곳"), (6, 5, 4, "4~6번: mint 3곳")]
    for k, (r, good, bad, why) in enumerate(panels):
        y = 60 + k * 126
        rects = c.cells(160, y, stalls, size=34, gap=4, text_px=10, index=1)
        c.pointer(mid_x(rects[r - 1]), y, "r", "decorator", size=11, gap=2)
        c.text(20, y + 17, "r = %d" % r, "ink", 13, bold=True, mono=True, anchor="lm")
        c.text(20, y + 60, "2가지 이하, C 적용", "builtin", 11, anchor="lm")
        c.text(20, y + 86, "1가지 이하, C 없음", "decorator", 11, anchor="lm")
        band(c, rects, good - 1, r - 1, y + 50, 20, shade("builtin", 0.5))
        lower = band(c, rects, bad - 1, r - 1, y + 76, 20, shade("decorator", 0.5))
        wrong = band(c, rects, bad - 1, bad - 1, y + 76, 20, shade("missing", 0.5))
        c.hatch((wrong[0] + 1, wrong[1] + 1, wrong[2] - 2, wrong[3] - 2), "missing")
        c.text(lower[0] + lower[2] + 10, y + 86, why, "missing", 12, anchor="lm")
    c.text(20, 300, "f(2) - f(1) = 14 - 12 = 2   (맞는 답은 14 - 10 = 4)", "ink", 12, mono=True, anchor="lm")
    note(c, "C 없이 센 f(1)이 1~3번과 4~6번을 더 빼서 답이 4에서 2가 됩니다.")
