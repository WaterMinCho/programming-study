#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습 페이지 l03 「비동기와 Promise」의 그림. 시간 값은 page.md 의 코드 블록과 figure 블록의 프레임 설명을 그대로 씀.

  python3 tools/web_art/l03.py                 web/learn/l03/assets/ 에 그림을 모두 씀
  python3 tools/web_art/l03.py 3a-1 3b-3       이름을 적은 그림만
  python3 tools/web_art/l03.py --check         쓴 파일을 다시 읽어 밝은 면과 팔레트까지 확인
  python3 tools/web_art/l03.py --out DIR       다른 폴더에 씀

그림 이름은 사슬 절 그림 규칙(3a-1, 3b-2)이라 던전 그림 이름 규칙(1-1a)과 달라서, 이름 검사만 건너뛰는 PageFigure 를 씀.
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
from tools.journey_art.draw import figure, mid_x, mid_y, shade  # noqa: E402

OUT = os.path.join(ROOT, "web", "learn", "l03", "assets")
USAGE = "쓰는 법: python3 tools/web_art/l03.py [그림 이름...] [--check] [--out DIR]"
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


def dashed_arrow(c, x1, y1, x2, y2, color_name="comment", head_len=7):
    """점선 화살표. 머리는 끝점에 둠."""
    angle = math.atan2(y2 - y1, x2 - x1)
    ux, uy = math.cos(angle), math.sin(angle)
    bx, by = x2 - ux * head_len, y2 - uy * head_len
    dashed(c, x1, y1, bx, by, color_name)
    side = head_len * 0.55
    tri = [(x2, y2), (bx - uy * side, by + ux * side), (bx + uy * side, by - ux * side)]
    c.d.polygon([c._pt(x, y) for x, y in tri], fill=draw.color(color_name))


def two_lines(c, x, y, first, second, color_name="ink", size=11, mono=False):
    """가운데 맞춘 두 줄 글자. x 는 가운데, y 는 첫 줄의 위."""
    c.text(x, y, first, color_name, size, mono=mono, anchor="ma")
    c.text(x, y + size + 4, second, color_name, size, mono=mono, anchor="ma")


class Timeline:
    """가로 시간축. ms 를 논리 x 로 바꾸고 요청 막대와 '지금' 선을 그림."""

    def __init__(self, c, x0, x1, ms_max, y):
        self.c, self.x0, self.x1, self.ms_max, self.y = c, x0, x1, ms_max, y

    def x(self, ms):
        return self.x0 + (self.x1 - self.x0) * ms / self.ms_max

    def axis(self, ticks, unit="ms"):
        self.c.line([(self.x0, self.y), (self.x1, self.y)], "edge", 1)
        for t in ticks:
            x = self.x(t)
            self.c.line([(x, self.y - 3), (x, self.y + 3)], "edge", 1)
            self.c.text(x, self.y + 5, "%d%s" % (t, unit) if t == ticks[-1] else str(t), "line_no", 10, mono=True, anchor="ma")

    def bar(self, ms_from, ms_to, y, h, fill, outline=None, label=None, short=None, ink="bg"):
        """ms_from 에서 ms_to 까지의 막대. outline 이 None 이면 아직 진행 중인 막대(오른쪽이 열려 있음).
        label 이 막대보다 길면 short 를 쓰고, 그것도 길면 글자를 두지 않음."""
        x = self.x(ms_from)
        w = max(2, self.x(ms_to) - x)
        rect = self.c.box(x, y, w, h, fill=fill, outline=outline, radius=3)
        if label and self.c.text_size(label, 11, True, True)[0] + 12 > w and short is not None:
            label = short
        if label and self.c.text_size(label, 11, True, True)[0] + 8 <= w:
            self.c.text(x + 6, y + h / 2, label, ink, 11, bold=True, mono=True, anchor="lm")
        return rect

    def now(self, ms, y_top, y_bottom, label="지금"):
        """지금 시각의 세로 점선. 이름은 축 눈금 글자와 겹치지 않게 선 오른쪽 위에 두고, 그림 오른쪽 끝에 닿으면 선 왼쪽에 둠."""
        x = self.x(ms)
        dashed(self.c, x, y_top, x, y_bottom, "def", 3)
        if x + 4 + self.c.text_size(label, 10)[0] > self.c.width - 4:
            self.c.text(x - 4, y_top, label, "def", 10, anchor="ra")
        else:
            self.c.text(x + 4, y_top, label, "def", 10, anchor="la")
        return x


# 3a: 늦게 온 응답과 요청 취소. 're' 는 0ms 에 나가 900ms 에, 'react' 는 200ms 에 나가 500ms 에 돌아옴

RE_ROW, REACT_ROW, BAR_H = 96, 146, 24
NOW_TOP, NOW_BOTTOM = 80, 178
SCREEN = (410, 86, 130, 80)


def race_base(c, title):
    """3a-1·3a-3 공통 배치: 시간축, 두 요청 줄 이름, 오른쪽 화면 칸."""
    head(c, title)
    tl = Timeline(c, 70, 380, 1000, 66)
    tl.axis([0, 200, 400, 600, 800, 1000])
    c.text(20, RE_ROW + BAR_H / 2, "'re'", "ink", 12, mono=True, anchor="lm")
    c.text(20, REACT_ROW + BAR_H / 2, "'react'", "ink", 12, mono=True, anchor="lm")
    x, y, w, h = SCREEN
    c.text(x + w / 2, y - 16, "화면 (results)", "comment", 12, anchor="ma")
    c.box(x, y, w, h, fill="gutter", outline="edge", radius=4)
    return tl


def screen_text(c, s, color_name):
    x, y, w, h = SCREEN
    c.text(x + w / 2, y + h / 2, s, color_name, 14, bold=True, anchor="mm")


def to_screen(c, tl, ms, row, color_name):
    """막대 끝에서 화면 칸으로 가는 화살표."""
    x, y, w, h = SCREEN
    c.arrow(tl.x(ms) + 4, row + BAR_H / 2, x - 4, y + h / 2, color_name, width=2)


@figure("3a-1", 560, 300)
def race(fig):
    title = "'re' 요청이 'react' 요청보다 늦게 돌아올 때"
    c = fig.frame(1400)
    tl = race_base(c, title)
    tl.bar(0, 150, RE_ROW, BAR_H, shade("builtin", 0.5), label="re 요청", short="re")
    tl.now(150, NOW_TOP, NOW_BOTTOM)
    note(c, "0ms에 're' 요청이 나갑니다. 화면은 아직 비어 있습니다.")

    c = fig.frame(1400)
    tl = race_base(c, title)
    tl.bar(0, 350, RE_ROW, BAR_H, shade("builtin", 0.5), label="re 요청", short="re")
    tl.bar(200, 350, REACT_ROW, BAR_H, shade("string", 0.5), label="react 요청", short="react")
    tl.now(350, NOW_TOP, NOW_BOTTOM)
    note(c, "200ms에 'react' 요청이 나갑니다. 're' 응답은 아직 오지 않았습니다.")

    c = fig.frame(1600)
    tl = race_base(c, title)
    tl.bar(0, 500, RE_ROW, BAR_H, shade("builtin", 0.5), label="re 요청", short="re")
    tl.bar(200, 500, REACT_ROW, BAR_H, "string", outline="string", label="react 요청", short="react")
    to_screen(c, tl, 500, REACT_ROW, "string")
    screen_text(c, "react 결과", "string")
    tl.now(500, NOW_TOP, NOW_BOTTOM)
    note(c, "500ms에 'react' 응답이 와서 화면에 'react 결과'가 들어갑니다.")

    c = fig.frame(2200)
    tl = race_base(c, title)
    tl.bar(0, 900, RE_ROW, BAR_H, "builtin", outline="builtin", label="re 요청", short="re")
    tl.bar(200, 500, REACT_ROW, BAR_H, shade("string", 0.5), outline="edge", label="react 요청", short="react")
    to_screen(c, tl, 900, RE_ROW, "missing")
    screen_text(c, "re 결과", "missing")
    c.highlight(SCREEN, "missing", width=2, pad=3)
    c.tag(SCREEN[0] + 8, SCREEN[1] + SCREEN[3] + 10, "마지막 setResults", "missing", size=10)
    tl.now(900, NOW_TOP, NOW_BOTTOM)
    note(c, "900ms에 're' 응답이 와서 화면이 옛 결과인 're 결과'로 돌아갑니다.")


@figure("3a-2", 560, 210)
def cleanup_order(fig):
    c = fig.frame()
    head(c, "query가 're'에서 'rea'로 바뀔 때 React가 부르는 순서")
    labels = [("query='re'", "로 그림"), ("effect('re')", "실행, 요청 1"), ("query='rea'", "로 그림"), ("정리('re')", "요청 1 끊기"), ("effect('rea')", "실행, 요청 2")]
    boxes = []
    for i, (first, second) in enumerate(labels):
        x = 20 + i * 108
        cleanup = i == 3
        rect = c.box(x, 84, 96, 56, fill=shade("decorator", 0.5) if cleanup else "gutter", outline="decorator" if cleanup else "edge", width=2 if cleanup else 1, radius=4)
        two_lines(c, x + 48, 94, first, second, "ink", 11, mono=True)
        boxes.append(rect)
    for a, b in zip(boxes, boxes[1:]):
        c.arrow(a[0] + a[2] + 1, mid_y(a), b[0] - 1, mid_y(b), "comment", width=2, head=6)
    x_from, x_to = mid_x(boxes[3]), mid_x(boxes[1])
    c.line([(x_from, 82), (x_from, 66), (x_to, 66)], "decorator", 1)
    dashed_arrow(c, x_to, 66, x_to, 80, "decorator")
    c.text((x_from + x_to) / 2, 58, "요청 1을 버리거나 끊음", "decorator", 10, anchor="ms")
    note(c, "정리('re')가 요청 1을 처리한 뒤에야 effect('rea')가 실행됩니다.")


@figure("3a-3", 560, 300)
def abort_race(fig):
    title = "정리 함수가 're' 요청을 끊을 때"
    c = fig.frame(1400)
    tl = race_base(c, title)
    tl.bar(0, 80, RE_ROW, BAR_H, shade("builtin", 0.5), label="re 요청", short="re")
    tl.now(80, NOW_TOP, NOW_BOTTOM)
    note(c, "0ms에 're' 요청이 나갑니다.")

    def aborted_re(c, tl):
        tl.bar(0, 100, RE_ROW, BAR_H, shade("comment", 0.5), outline="comment", label="re 요청", short="re", ink="ink")
        x = tl.x(100)
        c.line([(x, 60), (x, 66)], "decorator", 2)
        c.text(x, 58, "'rea' 입력", "decorator", 10, anchor="ms")
        c.tag(x + 6, RE_ROW + 3, "abort()", "decorator", size=10)

    c = fig.frame(1800)
    tl = race_base(c, title)
    aborted_re(c, tl)
    tl.bar(200, 350, REACT_ROW, BAR_H, shade("string", 0.5), label="react 요청", short="react")
    tl.now(350, NOW_TOP, NOW_BOTTOM)
    note(c, "100ms에 'rea'가 들어오자 정리 함수가 're' 요청을 끊습니다.")

    c = fig.frame(1600)
    tl = race_base(c, title)
    aborted_re(c, tl)
    tl.bar(200, 500, REACT_ROW, BAR_H, "string", outline="string", label="react 요청", short="react")
    to_screen(c, tl, 500, REACT_ROW, "string")
    screen_text(c, "react 결과", "string")
    tl.now(500, NOW_TOP, NOW_BOTTOM)
    note(c, "500ms에 'react' 응답이 와서 화면에 들어갑니다.")

    c = fig.frame(2200)
    tl = race_base(c, title)
    aborted_re(c, tl)
    tl.bar(200, 500, REACT_ROW, BAR_H, "string", outline="string", label="react 요청", short="react")
    screen_text(c, "react 결과", "string")
    c.highlight(SCREEN, "string", width=2, pad=3)
    x = tl.x(900)
    dashed(c, x, NOW_TOP, x, NOW_BOTTOM, "comment", 3)
    c.text(x, NOW_BOTTOM + 10, "AbortError, 화면에 쓰지 않음", "comment", 10, anchor="ma")
    tl.now(900, NOW_TOP, NOW_BOTTOM)
    note(c, "900ms의 're' 응답은 AbortError로 거부되어 화면에 쓰이지 않습니다.")


# 3b: 요청 묶기. A 는 300ms 에 이행, B 는 100ms 에 거부, C 는 200ms 에 이행

ALL_ROWS = {"A": 94, "B": 134, "C": 174}
ALL_BOX = (370, 86, 170, 44)
CATCH_BOX = (370, 160, 170, 40)


def all_base(c):
    head(c, "Promise.all([A, B, C])에서 B가 100ms에 거부될 때")
    tl = Timeline(c, 60, 330, 300, 66)
    tl.axis([0, 100, 200, 300])
    for name, y in ALL_ROWS.items():
        c.text(24, y + 11, name, "ink", 12, bold=True, mono=True, anchor="lm")
    return tl


def all_box(c, status, failed):
    x, y, w, h = ALL_BOX
    c.box(x, y, w, h, fill=shade("missing", 0.5) if failed else "gutter", outline="missing" if failed else "edge", width=2 if failed else 1, radius=4)
    c.text(x + 10, y + h / 2, "Promise.all", "ink", 12, bold=True, mono=True, anchor="lm")
    c.text(x + w - 10, y + h / 2, status, "missing" if failed else "comment", 12, bold=failed, anchor="rm")


def catch_box(c):
    x, y, w, h = CATCH_BOX
    c.arrow(mid_x(ALL_BOX), ALL_BOX[1] + ALL_BOX[3] + 2, mid_x(ALL_BOX), y - 2, "missing", width=2)
    c.box(x, y, w, h, fill="gutter", outline="missing", radius=4)
    c.text(x + w / 2, y + h / 2, "catch 실행, 에러 화면", "missing", 12, anchor="mm")


def unheard(c, tl, ms, name):
    """이행됐지만 받는 곳이 없는 요청. 막대는 회색으로 닫고 아래에 글자."""
    y = ALL_ROWS[name]
    tl.bar(0, ms, y, 22, shade("comment", 0.5), outline="comment", label=name, ink="ink")
    c.text(tl.x(ms), y + 24, "이행, 받는 곳 없음", "comment", 10, anchor="ra")


@figure("3b-1", 560, 300)
def all_rejects(fig):
    c = fig.frame(1400)
    tl = all_base(c)
    for name, y in ALL_ROWS.items():
        tl.bar(0, 50, y, 22, shade("builtin", 0.5), label=name)
    all_box(c, "대기 중", False)
    tl.now(50, NOW_TOP, 202)
    note(c, "요청 셋이 함께 나갑니다. Promise.all은 셋을 기다리는 중입니다.")

    c = fig.frame(2000)
    tl = all_base(c)
    tl.bar(0, 100, ALL_ROWS["A"], 22, shade("builtin", 0.5), label="A")
    tl.bar(0, 100, ALL_ROWS["B"], 22, "missing", outline="missing", label="B")
    c.tag(tl.x(100) + 6, ALL_ROWS["B"] + 2, "거부", "missing", size=10)
    tl.bar(0, 100, ALL_ROWS["C"], 22, shade("builtin", 0.5), label="C")
    all_box(c, "거부됨", True)
    catch_box(c)
    tl.now(100, NOW_TOP, 202)
    note(c, "100ms에 B가 거부되자 Promise.all도 그 순간 거부됩니다.")

    c = fig.frame(1600)
    tl = all_base(c)
    tl.bar(0, 200, ALL_ROWS["A"], 22, shade("builtin", 0.5), label="A")
    tl.bar(0, 100, ALL_ROWS["B"], 22, "missing", outline="missing", label="B")
    c.tag(tl.x(100) + 6, ALL_ROWS["B"] + 2, "거부", "missing", size=10)
    unheard(c, tl, 200, "C")
    all_box(c, "거부됨", True)
    catch_box(c)
    tl.now(200, NOW_TOP, 202)
    note(c, "200ms에 C가 이행되지만 결과를 받는 곳이 없습니다.")

    c = fig.frame(2000)
    tl = all_base(c)
    unheard(c, tl, 300, "A")
    tl.bar(0, 100, ALL_ROWS["B"], 22, "missing", outline="missing", label="B")
    c.tag(tl.x(100) + 6, ALL_ROWS["B"] + 2, "거부", "missing", size=10)
    unheard(c, tl, 200, "C")
    all_box(c, "거부됨", True)
    catch_box(c)
    tl.now(300, NOW_TOP, 202)
    note(c, "300ms에 A도 이행되지만 Promise.all은 거부된 채입니다.")


@figure("3b-2", 560, 270)
def settled_array(fig):
    c = fig.frame()
    head(c, "Promise.allSettled([A, B, C])가 이행되는 값")
    cards = [("fulfilled", "value: 'A'", "string"), ("rejected", "reason: Error", "missing"), ("fulfilled", "value: 'C'", "string")]
    rects = []
    for i, (status, detail, color_name) in enumerate(cards):
        x = 40 + i * 170
        rect = c.box(x, 50, 150, 70, fill=shade(color_name, 0.75), outline=color_name, width=2, radius=5)
        c.text(x + 10, 60, "[%d]" % i, "line_no", 11, mono=True)
        c.text(x + 75, 76, "status: '%s'" % status, "ink", 11, bold=True, mono=True, anchor="ma")
        c.text(x + 75, 96, detail, "ink", 11, mono=True, anchor="ma")
        rects.append(rect)
    ok_box = c.box(40, 176, 220, 46, fill="gutter", outline="string", radius=4)
    two_lines(c, mid_x(ok_box), 182, "성공 2개", "\"2개를 중지했습니다\" 안내", "string", 11)
    bad_box = c.box(300, 176, 220, 46, fill="gutter", outline="missing", radius=4)
    two_lines(c, mid_x(bad_box), 182, "실패 1개", "[다시 시도] 단추에 id 전달", "missing", 11)
    for i, rect in enumerate(rects):
        target = bad_box if cards[i][0] == "rejected" else ok_box
        c.arrow(mid_x(rect), rect[1] + rect[3] + 2, mid_x(target), target[1] - 2, cards[i][2], width=2, head=6)
    note(c, "자리마다 status를 보고 성공한 id와 실패한 id를 나눕니다.")


# 3b-3: 작업 여섯 개(300, 100, 150, 100, 300, 100ms)를 작업자 둘로. 시작·끝 시각은 page.md 의 runPool 실행 결과와 같음

POOL = [(0, 0, 300), (1, 0, 100), (1, 100, 250), (1, 250, 350), (0, 300, 600), (1, 350, 450)]  # 작업 i 의 (작업자, 시작, 끝)
POOL_ROWS = (92, 134)
POOL_NOTES = [
    (40, "작업자 둘이 0번과 1번을 집고, 나머지는 줄에서 기다립니다."),
    (100, "100ms에 1번이 끝나자 작업자 2가 바로 2번을 집습니다."),
    (250, "250ms에 2번이 끝나고 작업자 2가 3번을 집습니다."),
    (300, "300ms에 0번이 끝나고 작업자 1이 4번을 집습니다."),
    (350, "350ms에 3번이 끝나고 작업자 2가 마지막 5번을 집습니다."),
    (450, "450ms에 5번이 끝납니다. 줄이 비어 작업자 2는 쉽니다."),
    (600, "600ms에 4번이 끝나고 결과 배열은 넘긴 순서대로 차 있습니다."),
]


@figure("3b-3", 560, 320)
def pool(fig):
    for now, text in POOL_NOTES:
        c = fig.frame(2200 if now == 600 else 1400)
        head(c, "작업 여섯 개를 작업자 둘로 돌릴 때 (걸리는 시간 300, 100, 150, 100, 300, 100ms)")
        tl = Timeline(c, 110, 540, 600, 66)
        tl.axis([0, 100, 200, 300, 400, 500, 600])
        for k, y in enumerate(POOL_ROWS):
            c.text(20, y + 13, "작업자 %d" % (k + 1), "ink", 12, anchor="lm")
        for i, (worker, start, end) in enumerate(POOL):
            if start > now:
                continue
            y = POOL_ROWS[worker]
            if end <= now:
                tl.bar(start, end, y, 26, shade("builtin", 0.75), outline="edge", label=str(i), ink="ink")
            else:
                tl.bar(start, min(end, now), y, 26, "builtin", label=str(i))
        waiting = [i for i, (_, start, _) in enumerate(POOL) if start > now]
        c.text(20, 203, "남은 작업", "comment", 12, anchor="lm")
        c.cells(110, 190, waiting or [None], size=26, gap=6, fill="gutter")
        done = [i if end <= now else None for i, (_, _, end) in enumerate(POOL)]
        c.text(20, 249, "결과 배열", "comment", 12, anchor="lm")
        c.cells(110, 236, done, size=26, gap=6, fill="gutter", marks={i: shade("builtin", 0.75) for i, v in enumerate(done) if v is not None}, index=0)
        tl.now(now, NOW_TOP, 166)
        note(c, text)


@figure("3b-4", 560, 250)
def backoff(fig):
    c = fig.frame()
    head(c, "실패한 요청을 네 번째에 성공할 때까지 다시 보내는 시간표")
    tl = Timeline(c, 50, 530, 8, 120)
    tl.axis([0, 1, 2, 3, 4, 5, 6, 7, 8], unit="초")
    attempts = [(0, "1차", "503", 54, "missing"), (1, "2차", "네트워크 오류", 78, "missing"), (3, "3차", "429, Retry-After: 4", 54, "decorator"), (7, "4차", "200 성공", 78, "string")]
    for sec, label, result, y, color_name in attempts:
        x = tl.x(sec)
        c.line([(x, y + 14), (x, 120)], color_name, 2)
        c.box(x - 4, 116, 8, 8, fill=color_name, outline=None, radius=4)
        c.text(x, y, "%s: %s" % (label, result), color_name, 11, bold=True, anchor="ma")
    c.bracket(tl.x(0), tl.x(1), 134, "1초 + 무작위", below=True)
    c.bracket(tl.x(1), tl.x(3), 134, "2초 + 무작위", below=True)
    c.bracket(tl.x(3), tl.x(7), 134, "Retry-After가 적어 준 4초", below=True)
    box = c.box(50, 168, 480, 30, fill="gutter", outline="missing", radius=4)
    c.text(mid_x(box), mid_y(box), "다시 보내지 않음: 400, 403, 404 (요청 자체가 잘못되어 결과가 같음)", "missing", 11, anchor="mm")
    note(c, "간격은 두 배씩 늘리고, 429는 서버가 적어 준 시간을 따릅니다.")


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
