#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습 페이지 l21 「라이브 코딩 60분 운영표」의 그림. 분 단위 시각은 page.md 의 figure 블록 설명을 그대로 씀.

  python3 tools/web_art/l21.py                 web/learn/l21/assets/ 에 그림을 모두 씀
  python3 tools/web_art/l21.py l21-3           이름을 적은 그림만
  python3 tools/web_art/l21.py --check         쓴 파일을 다시 읽어 밝은 면과 팔레트까지 확인
  python3 tools/web_art/l21.py --out DIR       다른 폴더에 씀

그림 이름은 페이지 그림 규칙(l21-1)이라 던전 그림 이름 규칙(1-1a)과 달라서, 이름 검사만 건너뛰는 PageFigure 를 씀.
한도(GIF 300KB, PNG 200KB, 프레임 12개, 프레임 800~2500ms, 논리 폭 560px)와 색, 글꼴은 journey_art 와 같음.
Pillow 가 필요하므로 출제자 컴퓨터에서만 돌림.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.journey_art import LIMITS  # noqa: E402
from tools.journey_art import draw, render  # noqa: E402
from tools.journey_art.draw import figure, mid_x, shade  # noqa: E402

OUT = os.path.join(ROOT, "web", "learn", "l21", "assets")
USAGE = "쓰는 법: python3 tools/web_art/l21.py [그림 이름...] [--check] [--out DIR]"
TOP = 14  # 맨 위 설명 줄의 y


class PageFigure(draw.Figure):
    """학습 페이지 그림. 이름이 던전 규칙과 달라 이름 검사만 건너뛰고 나머지는 draw.Figure 와 같음."""

    def __init__(self, name, width, height):
        if width > LIMITS["width"]:
            raise ValueError("논리 폭은 %dpx 이하여야 합니다: %s 가 %dpx" % (LIMITS["width"], name, width))
        self.name, self.width, self.height = name, width, height
        self.frames, self.durations = [], []


def head(c, s):
    c.text(20, TOP, s, "comment", 13)


def note(c, s):
    """아래 띠의 설명. 띠보다 길면 그리기 전에 멈춤."""
    if c.text_size(s, 13)[0] > c.width - 24:
        raise ValueError("설명이 그림 폭보다 깁니다: %s" % s)
    c.caption(s)


def fit(c, s, size, width, bold=False, mono=False):
    """글자가 width 안에 들어가는지 확인함. 넘치면 그리기 전에 멈춤."""
    if c.text_size(s, size, bold, mono)[0] > width:
        raise ValueError("글자가 칸보다 깁니다(%dpx): %s" % (width, s))
    return s


def dashed(c, x1, y1, x2, y2, color_name="comment", dash=4, width=1):
    """점선. dash 길이만큼 긋고 같은 길이만큼 띄움."""
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    t = 0
    while t < length:
        end = min(t + dash, length)
        c.line([(x1 + ux * t, y1 + uy * t), (x1 + ux * end, y1 + uy * end)], color_name, width)
        t += dash * 2


class Timeline:
    """가로 시간축. 분을 논리 x 로 바꾸고 막대와 '지금' 선을 그림."""

    def __init__(self, c, x0, x1, max_value, y):
        self.c, self.x0, self.x1, self.max_value, self.y = c, x0, x1, max_value, y

    def x(self, value):
        return self.x0 + (self.x1 - self.x0) * value / self.max_value

    def axis(self, ticks, unit="분"):
        self.c.line([(self.x0, self.y), (self.x1, self.y)], "edge", 1)
        for t in ticks:
            x = self.x(t)
            self.c.line([(x, self.y - 3), (x, self.y + 3)], "edge", 1)
            self.c.text(x, self.y + 5, "%d%s" % (t, unit), "line_no", 10, mono=True, anchor="ma")

    def bar(self, start, end, y, h, fill, outline=None, label=None, ink="bg"):
        """start 에서 end 까지의 막대. outline 이 None 이면 아직 진행 중인 막대."""
        x = self.x(start)
        w = max(2, self.x(end) - x)
        rect = self.c.box(x, y, w, h, fill=fill, outline=outline, radius=3)
        if label and self.c.text_size(label, 11, True)[0] + 8 <= w:
            self.c.text(x + w / 2, y + h / 2, label, ink, 11, bold=True, anchor="mm")
        return rect

    def now(self, value, y_top, y_bottom, label="지금"):
        x = self.x(value)
        dashed(self.c, x, y_top, x, y_bottom, "def", 3)
        self.c.text(x + 4, y_top, label, "def", 10, anchor="la")
        return x


# l21-1: 읽기 60분 띠. 구간은 (시작 분, 끝 분, 이름, 색, 적는 것, 메모 줄)

BAND_Y, BAND_H = 56, 36
READING = [
    (0, 5, "실행", "builtin", "돌려 보고 눌러 봄", 0),
    (5, 20, "진입점에서 데이터까지", "string", "데이터가 오는 곳, 두는 곳, 그리는 곳 세 줄", 1),
    (20, 40, "state와 effect", "def", "state인 값, 계산되는 값, effect가 다시 도는 때", 0),
    (40, 50, "테스트", "decorator", "기존 테스트가 보장하는 것", 1),
    (50, 60, "설명 메모", "keyword", "3분 설명 메모, 고칠 곳 하나", 0),
]


@figure("l21-1", 560, 250)
def reading(fig):
    c = fig.frame()
    head(c, "코드를 받은 뒤 60분")
    tl = Timeline(c, 20, 540, 60, BAND_Y + BAND_H + 4)
    for start, end, name, color_name, memo, row in READING:
        x, w = tl.x(start), tl.x(end) - tl.x(start)
        c.box(x, BAND_Y, w, BAND_H, fill=shade(color_name, 0.5), outline=color_name, radius=0)
        size = 11 if c.text_size(name, 11, True)[0] + 8 <= w else 10
        c.text(x + w / 2, BAND_Y + BAND_H / 2, fit(c, name, size, w - 6, bold=True), "ink", size, bold=True, anchor="mm")
        mid = x + w / 2
        y = 120 + row * 30
        c.line([(mid, BAND_Y + BAND_H + 18), (mid, y - 4)], "comment", 1)
        mw = c.text_size(memo, 10)[0]
        mx = min(max(20, mid - mw / 2), 540 - mw)
        c.text(mx, y, memo, "ink", 10)
    tl.axis([0, 5, 20, 40, 50, 60])
    c.text(20, 184, "실험한 변경은 면접 전에 되돌려 받은 상태로 둡니다", "comment", 11)
    note(c, "처음 5분은 읽지 말고 돌려 봅니다. 메모는 구간마다 한 줄씩 남깁니다.")


# l21-2: 3분 설명의 순서. 칸은 (시작 초, 끝 초, 제목, 색, 예시 두 줄)

EXPLAIN = [
    (0, 30, "무엇을 하는 앱인지 한 문장", "builtin", ("통장 탭을 누르면 그 통장의 거래내역을", "받아 목록으로 보여 주는 화면")),
    (30, 90, "데이터의 길: 받는 곳, 두는 곳, 그리는 곳", "string", ("api.ts가 응답, 고른 통장 id는 App의 state,", "TransactionList가 요청해서 그림")),
    (90, 140, "다시 실행되는 조건", "def", ("useEffect 의존성에 accountId가 있어", "탭을 바꿀 때마다 요청")),
    (140, 180, "눈에 띈 점 하나와 이유", "decorator", ("기다리는 동안 빈 목록, 실패해도 표시 없음", "그 부분을 먼저 고치고 싶음")),
]
SCALE_X, SCALE_TOP, SCALE_H = 60, 50, 200


def sec_y(sec):
    return SCALE_TOP + SCALE_H * sec / 180


@figure("l21-2", 560, 310)
def explain(fig):
    c = fig.frame()
    head(c, "3분 설명의 순서 (미션 w03의 예)")
    c.line([(SCALE_X, SCALE_TOP), (SCALE_X, SCALE_TOP + SCALE_H)], "edge", 1)
    for start, end, title, color_name, example in EXPLAIN:
        y0, y1 = sec_y(start), sec_y(end)
        c.line([(SCALE_X - 4, y0), (SCALE_X, y0)], "edge", 1)
        c.text(SCALE_X - 8, y0, "%d:%02d" % (start // 60, start % 60), "line_no", 10, mono=True, anchor="rm")
        box = c.box(SCALE_X + 10, y0 + 2, 210, y1 - y0 - 4, fill=shade(color_name, 0.5), outline=color_name, radius=3)
        c.text(box[0] + 8, y0 + (y1 - y0) / 2, fit(c, title, 10, 196, bold=True), "ink", 10, bold=True, anchor="lm")
        ex_y = y0 + (y1 - y0) / 2 - 12
        for i, s in enumerate(example):
            c.text(290, ex_y + i * 14, fit(c, s, 10, 250), "ink", 10)
    c.line([(SCALE_X - 4, sec_y(180)), (SCALE_X, sec_y(180))], "edge", 1)
    c.text(SCALE_X - 8, sec_y(180), "3:00", "line_no", 10, mono=True, anchor="rm")
    s = "파일을 하나씩 읽어 내려가지 않습니다"
    w = c.text_size(s, 11)[0]
    c.text(290, 258, s, "comment", 11)
    c.line([(290, 265), (290 + w, 265)], "missing", 2)
    note(c, "한 문장 요약부터 말하고, 데이터의 길에 가장 긴 1분을 씁니다.")


# l21-3: 요구 하나에서 15분이 지났을 때. 위 줄은 방향을 확인한 쪽, 아래 줄은 혼자 붙잡은 쪽
# 막대는 (시작 분, 끝 분, 이름). 끝이 None 이면 그 줄의 마지막 미완 막대

ASK_ROW, ALONE_ROW, ROW_H = 76, 160, 26
ASK = [(0, 18, "요구 1"), (18, 32, "요구 2"), (32, 45, "요구 3")]
ALONE = [(0, 28, "요구 1"), (28, 43, "요구 2"), (43, 45, "요구 3")]
STUCK_NOTES = [
    (0, "요구 1을 시작합니다. 목표는 15분입니다."),
    (10, "10분이 지나도 에러 메시지가 같습니다."),
    (15, "15분에 위쪽은 면접관에게 방향을 확인합니다."),
    (18, "면접관의 한마디로 3분 만에 요구 1이 끝납니다."),
    (30, "아래쪽은 28분에야 혼자 풀어 요구 1을 끝냅니다."),
    (45, "위쪽은 요구 셋을 끝내고, 아래쪽은 요구 3을 시작도 못 합니다."),
]


def row_bars(c, tl, bars, y, now, done_color, cut=False):
    """줄 하나의 막대. now 이전에 끝난 막대는 닫고, 진행 중인 막대는 열어 둠. cut 이면 마지막 막대를 빗금으로 '못 함' 표시."""
    for i, (start, end, name) in enumerate(bars):
        if start >= now and not (cut and i == len(bars) - 1 and now >= tl.max_value):
            continue
        if end <= now:
            if cut and i == len(bars) - 1:
                rect = tl.bar(start, end, y, ROW_H, "gutter", outline="comment")
                c.hatch((rect[0] + 1, rect[1] + 1, rect[2] - 2, rect[3] - 2), "comment")
                c.text(rect[0] + rect[2] / 2, y - 6, "못 함", "missing", 10, anchor="ms")
            else:
                tl.bar(start, end, y, ROW_H, shade(done_color, 0.5), outline=done_color, label=name, ink="ink")
        else:
            tl.bar(start, now, y, ROW_H, done_color, label=name)


@figure("l21-3", 560, 300)
def stuck(fig):
    for now, text in STUCK_NOTES:
        c = fig.frame(1200 if now == 0 else 2500 if now == 45 else 1800 if now == 15 else 1400 if now in (10, 45) else 1600)
        head(c, "요구 하나에 15분이 지났을 때")
        tl = Timeline(c, 110, 540, 45, 56)
        tl.axis([0, 15, 30, 45])
        c.text(20, ASK_ROW + ROW_H / 2, "방향 확인", "ink", 12, anchor="lm")
        c.text(20, ALONE_ROW + ROW_H / 2, "혼자 붙잡음", "comment", 12, anchor="lm")
        for y in (ASK_ROW, ALONE_ROW):
            for k in range(3):
                c.box(tl.x(k * 15), y, tl.x(15) - tl.x(0), ROW_H, fill=None, outline="edge", radius=3)
        row_bars(c, tl, ASK, ASK_ROW, now, "string")
        row_bars(c, tl, ALONE, ALONE_ROW, now, "decorator", cut=True)
        if now >= 10 and now < 15:
            for y in (ASK_ROW, ALONE_ROW):
                # 아래 줄은 '지금' 글자가 같은 자리에 있어 그 오른쪽으로 비킴
                c.tag(tl.x(10) + (34 if y == ALONE_ROW else 6), y + ROW_H + 4, "에러 메시지가 같음", "missing", size=10)
        if now >= 15:
            x = tl.x(15)
            c.line([(x, ASK_ROW - 6), (x, ASK_ROW + ROW_H + 6)], "def", 2)
            c.text(x + 6, ASK_ROW + ROW_H + 6, "한 것, 막힌 곳, 후보 둘을 말함", "def", 10)
        if now >= 18:
            c.tag(tl.x(18) + 4, ASK_ROW - 20, "면접관 답", "string", size=10)
        if now > 0 and now < 45:
            x = tl.x(now)
            dashed(c, x, 50, x, ALONE_ROW + ROW_H + 22, "def", 3)
            c.text(x + 4, ALONE_ROW + ROW_H + 12, "지금", "def", 10, anchor="la")
        note(c, text)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    out_dir = OUT
    if "--out" in args:
        at = args.index("--out")
        if at + 1 >= len(args):
            print(USAGE)
            return 2
        out_dir = os.path.abspath(args[at + 1])
        del args[at:at + 2]
    names = args
    found = draw.figures(sys.modules[__name__])
    known = [item[0] for item in found]
    for name in names:
        if name not in known:
            print("그림 %s 가 없습니다. 있는 것: %s" % (name, ", ".join(known)))
            return 2
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    try:
        for name, width, height, fn in found:
            if names and name not in names:
                continue
            fig = PageFigure(name, width, height)
            fn(fig)
            path = fig.save(out_dir)
            row = render.inspect(path, check)
            row.update(name=name, path=path)
            rows.append(row)
    except ValueError as e:
        print(e)
        return 1
    print("쓴 폴더: %s" % out_dir)
    return 1 if render.report(rows, out_dir) else 0


if __name__ == "__main__":
    sys.exit(main())
