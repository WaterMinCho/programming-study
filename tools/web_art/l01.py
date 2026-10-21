#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습 페이지 l01 「이벤트 루프」의 그림. 코드 줄, 출력, 시간 값은 page.md 의 코드 블록과 figure 블록의 프레임 설명을 따름.

  python3 tools/web_art/l01.py                 web/learn/l01/assets/ 에 그림을 모두 씀
  python3 tools/web_art/l01.py l01-2 l01-6     이름을 적은 그림만
  python3 tools/web_art/l01.py --check         쓴 파일을 다시 읽어 밝은 면과 팔레트까지 확인
  python3 tools/web_art/l01.py --out DIR       다른 폴더에 씀

그리기는 tools/journey_art/draw.py, 이름 규칙과 명령줄은 tools/web_art/figure.py 를 씀. 그림 이름은 페이지 그림 꼴(l01-1)임.
그림 1~3·5 는 왼쪽 코드, 오른쪽 콜 스택·타이머·두 큐, 아래 출력 칸을 같은 자리에 두고 프레임마다 상태만 바꿈.
Pillow 가 필요하므로 출제자 컴퓨터에서만 돌림.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.journey_art import draw  # noqa: E402
from tools.journey_art.draw import mid_x, mid_y, shade  # noqa: E402
from tools.web_art.figure import figure, main  # noqa: E402

OUT = "web/learn/l01/assets"
SECTIONS = ("1a", "1b")
W = 560
TOP = 14  # 맨 위 설명 줄의 y


def fit(c, s, size, width, bold=False, mono=False):
    """글자가 width 안에 들어가는지 확인함. 넘치면 그리기 전에 멈춤."""
    if c.text_size(s, size, bold, mono)[0] > width:
        raise ValueError("글자가 칸보다 깁니다(%dpx): %s" % (width, s))
    return s


def head(c, s):
    c.text(20, TOP, fit(c, s, 13, c.width - 40), "comment", 13)


def note(c, s):
    """아래 띠의 설명. 띠보다 길면 그리기 전에 멈춤."""
    c.caption(fit(c, s, 13, c.width - 24))


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


def dashed_arrow(c, x1, y1, x2, y2, color_name="comment", head_len=7, width=1):
    """점선 화살표. 머리는 끝점에 둠."""
    angle = math.atan2(y2 - y1, x2 - x1)
    ux, uy = math.cos(angle), math.sin(angle)
    bx, by = x2 - ux * head_len, y2 - uy * head_len
    dashed(c, x1, y1, bx, by, color_name, width=width)
    side = head_len * 0.55
    tri = [(x2, y2), (bx - uy * side, by + ux * side), (bx + uy * side, by - ux * side)]
    c.d.polygon([c._pt(x, y) for x, y in tri], fill=draw.color(color_name))


def dashed_box(c, rect, color_name="comment"):
    x, y, w, h = rect
    dashed(c, x, y, x + w, y, color_name)
    dashed(c, x + w, y, x + w, y + h, color_name)
    dashed(c, x + w, y + h, x, y + h, color_name)
    dashed(c, x, y + h, x, y, color_name)
    return rect


# 그림 1~3·5 의 공통 배치: 왼쪽 코드, 오른쪽 콜 스택과 타이머, 그 아래 두 큐, 맨 아래 출력 칸

CODE_X, CODE_Y, CODE_W = 12, 34, 268
LINE_H, GUTTER = 18, 24
STACK = (296, 52, 136, 118)
TIMER = (440, 52, 96, 60)
CELL_H, CELL_GAP = 22, 3
CARD_H = 22
STRIP_X, STRIP_W, STRIP_H = 296, 240, 30  # 큐 띠. 왼쪽이 맨 앞이고 카드는 오른쪽 끝으로 들어옴
LEFT_LANE, RIGHT_LANE = 288, 547  # 이벤트 루프 화살표가 지나는 왼쪽 길, 타이머에서 큐로 가는 오른쪽 길
MICRO_Y, TASK_Y = 196, 250  # 두 큐가 다 있을 때 띠의 y
TASK_ONLY_Y = 196  # 태스크 큐만 있을 때
TASK_COLOR, MICRO_COLOR = "builtin", "keyword"


class Board:
    """한 프레임의 상태. stack 은 아래부터 칸 이름, timer·micro·task 는 카드 이름 목록, out 은 찍힌 글자 목록."""

    def __init__(self, code, timer=False, micro=False, task=False):
        self.code, self.has_timer, self.has_micro, self.has_task = code, timer, micro, task
        self.hl = ()
        self.stack, self.timer, self.micro, self.task, self.out = ["스크립트"], [], [], [], []
        self.ghost = None  # 막 빠진 칸(점선)
        self.fresh = None  # 막 올라갔다 빠질 칸(노란 테두리)
        self.empty = False
        self.loop_from = None  # ("micro"|"task", 카드 번호): 이벤트 루프 화살표가 꺼내는 카드
        self.move = None  # ("timer", "task") 처럼 카드가 옮겨 가는 길(점선 화살표)
        self.note = ""
        self.out_all = False
        self.out_new = 1  # 맨 뒤에서 몇 글자를 새로 찍힌 것으로 칠할지
        self.queue_done = None  # "micro" 면 마이크로태스크 큐 빈 표시

    @property
    def strips(self):
        """[(이름, 글자, 색, y)]."""
        out = []
        if self.has_micro:
            out.append(("micro", "마이크로태스크 큐", MICRO_COLOR, MICRO_Y))
            if self.has_task:
                out.append(("task", "태스크 큐", TASK_COLOR, TASK_Y))
        elif self.has_task:
            out.append(("task", "태스크 큐", TASK_COLOR, TASK_ONLY_Y))
        return out

    def bottom(self):
        strips = self.strips
        if strips:
            return strips[-1][3] + STRIP_H
        return max(STACK[1] + STACK[3], CODE_Y + len(self.code) * LINE_H + 12)


def board_height(board):
    return board.bottom() + 12 + 26 + 10 + draw.CAPTION_H


def code_panel(c, board, bottom):
    h = bottom - CODE_Y
    c.box(CODE_X, CODE_Y, CODE_W, h, fill="gutter", outline="edge", radius=4)
    for i, line in enumerate(board.code, 1):
        y = CODE_Y + 8 + (i - 1) * LINE_H
        if i in board.hl:
            c.box(CODE_X + 2, y - 2, CODE_W - 4, LINE_H, fill="selection", outline=None, radius=2)
        c.text(CODE_X + GUTTER - 6, y + LINE_H / 2 - 2, str(i), "line_no", 10, mono=True, anchor="rm")
        c.text(CODE_X + GUTTER + 2, y + LINE_H / 2 - 2, fit(c, line, 10, CODE_W - GUTTER - 8, mono=True), "ink", 10,
               mono=True, anchor="lm")


def stack_box(c, board):
    x, y, w, h = STACK
    c.text(x, y - 16, "콜 스택", "comment", 11)
    c.line([(x, y), (x, y + h), (x + w, y + h), (x + w, y)], "edge", 2)  # 위가 열린 상자
    cells = list(board.stack) + ([board.fresh] if board.fresh else [])
    rects = []
    for i, name in enumerate(cells):
        cy = y + h - 4 - (i + 1) * CELL_H - i * CELL_GAP
        rect = (x + 6, cy, w - 12, CELL_H)
        is_fresh = board.fresh is not None and i == len(cells) - 1
        fill = shade("def", 0.75) if is_fresh else shade("selection", 0.25)
        c.box(*rect, fill=fill, outline="def" if is_fresh else "edge", radius=3)
        size = 10 if c.text_size(name, 10, mono=True)[0] <= rect[2] - 8 else 9
        c.text(mid_x(rect), mid_y(rect), fit(c, name, size, rect[2] - 6, mono=True), "ink", size, mono=True, anchor="mm")
        rects.append(rect)
    if board.ghost:
        i = len(cells)
        cy = y + h - 4 - (i + 1) * CELL_H - i * CELL_GAP
        rect = (x + 6, cy, w - 12, CELL_H)
        dashed_box(c, rect, "comment")
        c.text(mid_x(rect), mid_y(rect), fit(c, board.ghost, 10, rect[2] - 6, mono=True), "comment", 10, mono=True,
               anchor="mm")
    if board.empty:
        c.text(mid_x(STACK), y + h - 30, "비었음", "string", 12, bold=True, anchor="mm")
    return rects


def card(c, x, y, s, color_name):
    w = c.text_size(s, 10, mono=True)[0] + 14
    rect = (x, y, w, CARD_H)
    c.box(*rect, fill=shade(color_name, 0.5), outline=color_name, radius=4)
    c.text(mid_x(rect), mid_y(rect), s, "ink", 10, mono=True, anchor="mm")
    return rect


def timer_box(c, board):
    x, y, w, h = TIMER
    c.text(x, y - 16, "브라우저 타이머", "comment", 11)
    c.box(x, y, w, h, fill="gutter", outline="edge", radius=4)
    rects = []
    for i, name in enumerate(board.timer):
        rects.append(card(c, x + 8, y + 8 + i * (CARD_H + 4), name, TASK_COLOR))
    return rects


def strip(c, board, key, label, color_name, y):
    c.text(STRIP_X + STRIP_W, y - 8, label, color_name, 11, anchor="rs")
    c.box(STRIP_X, y, STRIP_W, STRIP_H, fill="gutter", outline=color_name, radius=4)
    cards = getattr(board, key)
    rects, cx = [], STRIP_X + 6
    for name in cards:
        rect = card(c, cx, y + (STRIP_H - CARD_H) / 2, name, color_name)
        rects.append(rect)
        cx += rect[2] + 6
    if board.queue_done == key and not cards:
        c.text(STRIP_X + 10, y + STRIP_H / 2, "비었음", "string", 11, bold=True, anchor="lm")
    return rects


def output_row(c, board, y):
    c.text(CODE_X, y + 13, "출력", "comment", 11, anchor="lm")
    x = CODE_X + 36
    c.box(x, y, W - x - 12, 26, fill="gutter", outline="edge", radius=4)
    cx = x + 10
    for i, s in enumerate(board.out):
        last = i >= len(board.out) - board.out_new
        color_name = "def" if (last or board.out_all) else "ink"
        w = c.text(cx, y + 13, s, color_name, 12, bold=last or board.out_all, mono=True, anchor="lm")[0]
        cx += w + 14


def draw_board(c, board):
    bottom = board.bottom()
    code_panel(c, board, bottom)
    stack_rects = stack_box(c, board)
    timer_rects = timer_box(c, board) if board.has_timer else []
    strip_rects = {}
    for key, label, color_name, y in board.strips:
        strip_rects[key] = (strip(c, board, key, label, color_name, y), y, color_name)
    if board.move:
        src, dst = board.move
        rects, y, color_name = strip_rects[dst]
        if src == "timer":  # 타이머 오른쪽에서 오른쪽 길을 따라 내려가 큐 끝으로 들어감
            ty = mid_y(TIMER)
            dashed(c, TIMER[0] + TIMER[2], ty, RIGHT_LANE, ty, color_name)
            dashed(c, RIGHT_LANE, ty, RIGHT_LANE, y + STRIP_H / 2, color_name)
            dashed_arrow(c, RIGHT_LANE, y + STRIP_H / 2, STRIP_X + STRIP_W + 2, y + STRIP_H / 2, color_name, 6)
        else:  # 콜 스택 바닥에서 바로 큐의 마지막 카드로
            tx = mid_x(rects[-1]) if rects else STRIP_X + 30
            dashed_arrow(c, mid_x(STACK), STACK[1] + STACK[3] + 2, tx, y - 2, color_name)
    if board.loop_from:
        key, _ = board.loop_from
        rects, y, color_name = strip_rects[key]
        top = stack_rects[-1] if stack_rects else None
        sy = y + STRIP_H / 2
        ty = (top[1] + top[3] / 2) if top else STACK[1] + STACK[3] - 20
        c.line([(STRIP_X - 1, sy), (LEFT_LANE, sy), (LEFT_LANE, ty)], "def", 2)
        c.arrow(LEFT_LANE, ty, STACK[0] + 8, ty, "def", 2, 6)
        c.text(STRIP_X + 4, STACK[1] + STACK[3] + 13, "이벤트 루프", "def", 10, bold=True, anchor="lm")
    output_row(c, board, bottom + 12)
    if board.note:
        note(c, board.note)


def frame(fig, board, ms, **changes):
    for key, value in changes.items():
        setattr(board, key, value)
    c = fig.frame(ms)
    draw_board(c, board)
    return c


# l01-1: greet() 와 콜 스택

GREET = ["function greet() {", "  console.log('안녕하세요');", "}", "console.log('시작');", "greet();", "console.log('끝');"]


def greet_board():
    return Board(GREET)


@figure("l01-1", W, board_height(greet_board()))
def call_stack(fig):
    b = greet_board()
    frame(fig, b, 1400, note="실행하기 전, 콜 스택 맨 아래에 스크립트 칸이 있습니다.")
    frame(fig, b, 1600, hl=(4,), fresh="console.log('시작')", out=["'시작'"],
          note="4번 줄: console.log('시작')이 올라갔다 빠지고 '시작'이 찍힙니다.")
    frame(fig, b, 1400, hl=(5,), fresh=None, stack=["스크립트", "greet"], note="5번 줄: greet()를 부르면 greet 칸이 올라갑니다.")
    frame(fig, b, 1800, hl=(2,), fresh="console.log('안녕하세요')", out=["'시작'", "'안녕하세요'"],
          note="2번 줄: greet 안의 console.log가 올라갔다 빠집니다.")
    frame(fig, b, 1200, hl=(3,), fresh=None, stack=["스크립트"], ghost="greet", note="greet가 끝나 콜 스택에서 빠집니다.")
    frame(fig, b, 1600, hl=(6,), ghost=None, fresh="console.log('끝')", out=["'시작'", "'안녕하세요'", "'끝'"],
          note="6번 줄: '끝'은 greet가 빠진 다음에야 찍힙니다.")


# l01-2: setTimeout 콜백과 태스크 큐

ABC = ["console.log('A');", "setTimeout(() => console.log('B'), 0);", "console.log('C');"]


def abc_board():
    return Board(ABC, timer=True, task=True)


@figure("l01-2", W, board_height(abc_board()))
def task_queue(fig):
    b = abc_board()
    frame(fig, b, 1400, hl=(1,), out=["A"], note="1번 줄: 'A'가 찍힙니다.")
    frame(fig, b, 1800, hl=(2,), timer=["B 찍기"], ghost="setTimeout",
          note="2번 줄: setTimeout은 콜백을 타이머에 맡기고 바로 끝납니다.")
    frame(fig, b, 1800, hl=(3,), ghost=None, timer=[], task=["B 찍기"], move=("timer", "task"), out=["A", "C"],
          note="0ms가 지나 콜백이 태스크 큐로 가고, 3번 줄이 'C'를 찍습니다.")
    frame(fig, b, 1200, hl=(), move=None, stack=[], empty=True, note="스크립트가 끝나 콜 스택이 비었습니다.")
    frame(fig, b, 1800, empty=False, task=[], stack=["B 찍기"], loop_from=("task", 0), out=["A", "C", "B"],
          note="이벤트 루프가 태스크 큐의 콜백을 꺼내 'B'를 찍습니다.")


# l01-3: Promise 콜백과 마이크로태스크 큐

ADCB = ["console.log('A');", "setTimeout(() => console.log('B'), 0);", "Promise.resolve().then(() => console.log('C'));",
        "console.log('D');"]


def adcb_board():
    return Board(ADCB, timer=True, micro=True, task=True)


@figure("l01-3", W, board_height(adcb_board()))
def microtask_queue(fig):
    b = adcb_board()
    frame(fig, b, 1400, hl=(1,), out=["A"], note="1번 줄: 'A'가 찍힙니다.")
    frame(fig, b, 1600, hl=(2,), task=["B 찍기"], move=("timer", "task"),
          note="2번 줄: B 찍기 콜백은 타이머를 거쳐 태스크 큐로 갑니다.")
    frame(fig, b, 1600, hl=(3,), micro=["C 찍기"], move=("stack", "micro"),
          note="3번 줄: C 찍기 콜백은 바로 마이크로태스크 큐로 갑니다.")
    frame(fig, b, 1400, hl=(4,), move=None, stack=[], empty=True, out=["A", "D"],
          note="4번 줄이 'D'를 찍고 스크립트가 끝나 콜 스택이 빕니다.")
    frame(fig, b, 1800, hl=(), empty=False, micro=[], stack=["C 찍기"], loop_from=("micro", 0), out=["A", "D", "C"],
          note="이벤트 루프는 마이크로태스크 큐를 먼저 비웁니다.")
    frame(fig, b, 2000, task=[], stack=["B 찍기"], queue_done="micro", loop_from=("task", 0), out=["A", "D", "C", "B"],
          note="마이크로태스크 큐가 빈 뒤에야 태스크 큐의 'B'를 꺼냅니다.")


# l01-5: 출력 순서 문제

AEG = ["console.log('A');", "setTimeout(() => console.log('B'), 0);", "Promise.resolve().then(() => console.log('C'));",
       "queueMicrotask(() => console.log('D'));", "(async () => {", "  console.log('E');", "  await null;",
       "  console.log('F');", "})();", "console.log('G');"]


def aeg_board():
    return Board(AEG, timer=True, micro=True, task=True)


@figure("l01-5", W, board_height(aeg_board()))
def output_order(fig):
    b = aeg_board()
    frame(fig, b, 1400, hl=(1,), out=["A"], note="1번 줄: 'A'가 찍힙니다.")
    frame(fig, b, 1400, hl=(2,), task=["B"], move=("timer", "task"), note="2번 줄: B 콜백이 타이머를 거쳐 태스크 큐로 갑니다.")
    frame(fig, b, 1400, hl=(3,), micro=["C"], move=("stack", "micro"), note="3번 줄: C 콜백이 마이크로태스크 큐로 갑니다.")
    frame(fig, b, 1400, hl=(4,), micro=["C", "D"], note="4번 줄: D 콜백이 C 뒤에 섭니다.")
    frame(fig, b, 1600, hl=(5, 6), move=None, stack=["스크립트", "async 함수"], out=["A", "E"],
          note="5~6번 줄: async 함수는 첫 await까지 바로 실행되어 'E'를 찍습니다.")
    frame(fig, b, 2000, hl=(7,), stack=["스크립트"], ghost="async 함수", micro=["C", "D", "F (await 다음)"],
          move=("stack", "micro"), note="7번 줄: 함수가 멈추고 F를 찍는 나머지가 D 뒤에 섭니다.")
    frame(fig, b, 1400, hl=(10,), ghost=None, move=None, stack=[], empty=True, out=["A", "E", "G"],
          note="10번 줄이 'G'를 찍고 스크립트가 끝나 콜 스택이 빕니다.")
    frame(fig, b, 2500, hl=(), empty=False, micro=[], stack=["F (await 다음)"], loop_from=("micro", 0),
          out=["A", "E", "G", "C", "D", "F"], out_new=3, note="마이크로태스크 큐를 앞에서부터 비워 C, D, F가 찍힙니다.")
    frame(fig, b, 2500, task=[], stack=["B"], queue_done="micro", loop_from=("task", 0),
          out=["A", "E", "G", "C", "D", "F", "B"], out_new=1, out_all=True, note="마이크로태스크 큐가 빈 뒤에 태스크 큐의 B가 찍힙니다.")


# l01-4: 이벤트 루프 한 바퀴. 위 줄 셋, 아래 줄 그리기 띠, 예·아니요·돌아가기 화살표

def flow_row(c, y, items, gap, h=32):
    """[(글자, 색, 고정폭 글꼴)] 를 가운데 맞춰 한 줄로 놓고 칸 사이를 화살표로 이음. 칸 (x, y, w, h) 목록."""
    widths = [c.text_size(s, 12 if not mono else 11, not mono, mono)[0] + 22 for s, _, mono in items]
    x = (W - sum(widths) - gap * (len(items) - 1)) / 2
    rects = []
    for (s, color_name, mono), w in zip(items, widths):
        rect = (x, y, w, h)
        c.box(*rect, fill=shade(color_name, 0.5), outline=color_name, width=2, radius=6)
        c.text(mid_x(rect), mid_y(rect), s, "ink", 11 if mono else 12, bold=not mono, mono=mono, anchor="mm")
        if rects:
            prev = rects[-1]
            c.arrow(prev[0] + prev[2] + 3, mid_y(rect), rect[0] - 3, mid_y(rect), "ink", 2, 7)
        rects.append(rect)
        x += w + gap
    return rects


@figure("l01-4", W, 300)
def loop_ring(fig):
    c = fig.frame()
    c.text(W / 2, TOP + 2, "메인 스레드에서 도는 이벤트 루프 한 바퀴", "comment", 13, bold=True, anchor="ma")
    top = flow_row(c, 70, [("태스크 하나 실행", TASK_COLOR, False), ("마이크로태스크 큐 비우기", MICRO_COLOR, False),
                           ("그릴 차례인가?", "def", False)], 34)
    band = flow_row(c, 176, [("requestAnimationFrame 콜백", "string", True), ("스타일", "string", False),
                             ("레이아웃", "string", False), ("페인트", "string", False)], 22)
    first, ask = top[0], top[-1]
    # 아니요: 위로 돌아 첫 칸으로
    c.line([(mid_x(ask), ask[1] - 2), (mid_x(ask), 50), (mid_x(first), 50)], "comment", 2)
    c.arrow(mid_x(first), 50, mid_x(first), first[1] - 3, "comment", 2, 7)
    c.text((mid_x(first) + mid_x(ask)) / 2, 46, "아니요", "comment", 11, bold=True, anchor="ms")
    # 예: 아래로 내려가 그리기 띠의 첫 칸으로
    yes_y = 146
    c.line([(mid_x(ask), ask[1] + ask[3] + 2), (mid_x(ask), yes_y), (mid_x(band[0]), yes_y)], "string", 2)
    c.arrow(mid_x(band[0]), yes_y, mid_x(band[0]), band[0][1] - 3, "string", 2, 7)
    c.text(mid_x(ask) + 6, (ask[1] + ask[3] + yes_y) / 2, "예", "string", 11, bold=True, anchor="lm")
    # 그린 뒤: 띠 끝에서 바깥을 돌아 첫 칸으로
    last = band[-1]
    right, bottom, left = W - 14, 236, 14
    c.line([(last[0] + last[2] + 2, mid_y(last)), (right, mid_y(last)), (right, bottom), (left, bottom),
            (left, mid_y(first))], "string", 2)
    c.arrow(left, mid_y(first), first[0] - 3, mid_y(first), "string", 2, 7)
    c.text(W / 2, bottom - 4, "다음 바퀴", "string", 11, bold=True, anchor="ms")
    note(c, "태스크 하나, 마이크로태스크 전부, 그릴 차례면 화면 그리기 순서로 돕니다.")


# l01-6·7·8: 시간축 그림

class Timeline:
    """가로 시간축. ms 를 논리 x 로 바꿈."""

    def __init__(self, c, x0, x1, ms_max, y):
        self.c, self.x0, self.x1, self.ms_max, self.y = c, x0, x1, ms_max, y

    def x(self, ms):
        return self.x0 + (self.x1 - self.x0) * ms / self.ms_max

    def axis(self, ticks):
        self.c.line([(self.x0, self.y), (self.x1, self.y)], "edge", 1)
        for t in ticks:
            x = self.x(t)
            self.c.line([(x, self.y - 3), (x, self.y + 3)], "edge", 1)
            label = "%dms" % t if t == ticks[-1] else str(t)
            self.c.text(x, self.y + 5, label, "line_no", 10, mono=True, anchor="ma")

    def bar(self, ms_from, ms_to, y, h, color_name, label=None, faded=False, outline=None):
        x = self.x(ms_from)
        w = max(2, self.x(ms_to) - x)
        fill = shade(color_name, 0.75) if faded else shade(color_name, 0.25)
        rect = self.c.box(x, y, w, h, fill=fill, outline=outline, radius=3)
        if label and self.c.text_size(label, 10, mono=True)[0] + 8 <= w:
            self.c.text(x + 5, y + h / 2, label, "comment" if faded else "bg", 10, mono=True, bold=not faded, anchor="lm")
        return rect

    def tick(self, ms, y, label, color_name="ink"):
        x = self.x(ms)
        self.c.line([(x, y - 9), (x, y + 9)], color_name, 2)
        self.c.text(x, y - 11, label, color_name, 10, mono=True, anchor="ms")
        return x


def row_label(c, y, s):
    c.text(12, y, s, "comment", 11, anchor="lm")


def long_mark(c, rect):
    """롱 태스크 표시: 막대 오른쪽 위의 빨간 삼각형과 글자. 글자 뒤는 배경색으로 칠해 지나가는 선을 가림."""
    x, y, w, h = rect
    tri = [(x + w, y), (x + w - 9, y), (x + w, y + 9)]
    c.d.polygon([c._pt(px, py) for px, py in tri], fill=draw.color("missing"))
    tw, th = c.text_size("롱 태스크", 10, True)
    c.box(x + w - 2 - tw - 2, y + h + 2, tw + 4, th + 5, fill="bg", outline=None)
    c.text(x + w - 2, y + h + 3, "롱 태스크", "missing", 10, bold=True, anchor="ra")


# l01-6: 글자마다 300ms 렌더링

KEYS = [(0, "r"), (100, "e"), (200, "a")]


def typing_base(c, upto_key, title):
    head(c, title)
    tl = Timeline(c, 92, 540, 1000, 196)
    tl.axis([0, 200, 400, 600, 800, 1000])
    row_label(c, 62, "키 입력")
    row_label(c, 112, "메인 스레드")
    row_label(c, 166, "화면")
    for ms, key in KEYS[:upto_key]:
        tl.tick(ms, 62, "'%s'" % key, "def")
    return tl


@figure("l01-6", W, 270)
def typing_lag(fig):
    def render(c, tl, n, done):
        """n 번째 렌더링까지 그림. done 이 거짓이면 마지막 막대는 '지금' 까지만 자람."""
        rects = []
        for i in range(n):
            start = 300 * i
            end = start + 300 if (i < n - 1 or done) else start + 100
            rects.append(tl.bar(start, end - 4, 100, 24, "missing", "'%s' 렌더링" % KEYS[i][1] if end - start >= 300 else None))
        return rects

    c = fig.frame(1400)
    tl = typing_base(c, 1, "글자마다 거르고 그리는 데 300ms가 걸릴 때")
    render(c, tl, 1, False)
    note(c, "0ms에 'r'을 치자 렌더링이 메인 스레드를 차지합니다.")

    c = fig.frame(1800)
    tl = typing_base(c, 3, "글자마다 거르고 그리는 데 300ms가 걸릴 때")
    rects = render(c, tl, 1, True)
    long_mark(c, rects[0])
    for ms, _ in KEYS[1:]:
        c.text(tl.x(ms), 76, "기다림", "comment", 9, anchor="ma")
    note(c, "100ms, 200ms에 친 'e', 'a'는 렌더링이 끝날 때까지 기다립니다.")

    shown = [(300, "'r'"), (600, "'re'"), (900, "'rea'")]
    for k, ms in ((2, 1600), (3, 1600), (3, 2200)):
        c = fig.frame(ms)
        tl = typing_base(c, 3, "글자마다 거르고 그리는 데 300ms가 걸릴 때")
        rects = render(c, tl, k, True)
        if ms == 2200:
            y = 186
            x1, x2 = tl.x(200), tl.x(900)
            c.line([(x1, 70), (x1, y)], "def", 1)
            dashed(c, x1, y - 2, x2, y - 2, "def")
            # 're'·'rea' 표시와 겹치지 않게 600~900ms 사이에 둠
            c.text((tl.x(600) + x2) / 2 + 15, y - 6, "친 뒤 700ms", "def", 10, bold=True, anchor="ms")
        for rect in rects:
            long_mark(c, rect)
        upto = k - 1 if ms != 2200 else 3
        for at, s in shown[:upto]:
            x = tl.x(at)
            c.line([(x, 154), (x, 178)], "string", 2)
            c.text(x + 4, 166, s, "string", 11, bold=True, mono=True, anchor="lm")
        if ms == 2200:
            note(c, "'a'는 친 뒤 700ms가 지나서야 화면에 나타납니다.")
        elif k == 2:
            note(c, "300ms에 'r'이 보이고, 그제야 'e' 렌더링이 시작됩니다.")
        else:
            note(c, "600ms에 're'가 보이고, 'a' 렌더링은 900ms에 끝납니다.")


# l01-7: 디바운스 타이머

CALLS = [(0, "r"), (100, "re"), (200, "rea"), (300, "reac"), (400, "react"), (1000, "reactive")]


def debounce_base(c, upto):
    head(c, "debounce(fn, 300)이 돌려준 함수에 검색어를 넘길 때")
    tl = Timeline(c, 92, 540, 1600, 202)
    tl.axis([0, 200, 400, 600, 800, 1000, 1200, 1400, 1600])
    row_label(c, 64, "호출")
    row_label(c, 112, "타이머")
    row_label(c, 162, "거르기")
    for ms, q in CALLS[:upto]:
        tl.tick(ms, 64, q, "def")
    return tl


def timers(c, tl, upto, cut_all_before=None):
    """upto 개 호출의 타이머 막대. 다음 호출이 300ms 안에 오면 그 자리에서 잘린 회색 막대."""
    for i, (ms, _) in enumerate(CALLS[:upto]):
        nxt = CALLS[i + 1][0] if i + 1 < upto else None
        if nxt is not None and nxt - ms < 300:
            rect = tl.bar(ms, nxt, 102, 20, "comment", faded=True)
            c.text(rect[0] + rect[2] - 2, 126, "지움", "comment", 9, anchor="ra")
        else:
            tl.bar(ms, ms + 300, 102, 20, "builtin", "300ms")


@figure("l01-7", W, 276)
def debounce_timeline(fig):
    c = fig.frame(1400)
    tl = debounce_base(c, 1)
    timers(c, tl, 1)
    note(c, "0ms에 'r'을 넘기면 300ms 타이머가 걸립니다.")

    c = fig.frame(1800)
    tl = debounce_base(c, 4)
    timers(c, tl, 4)
    note(c, "100ms마다 다시 부르면 앞 타이머를 지우고 새로 겁니다.")

    c = fig.frame(1400)
    tl = debounce_base(c, 5)
    timers(c, tl, 5)
    note(c, "400ms에 'react'를 넘기고 더 부르지 않습니다.")

    c = fig.frame(1600)
    tl = debounce_base(c, 5)
    timers(c, tl, 5)
    tl.bar(700, 880, 150, 24, "string", "react")
    note(c, "700ms에 타이머가 끝나 'react'로 한 번 거릅니다.")

    c = fig.frame(2000)
    tl = debounce_base(c, 6)
    timers(c, tl, 6)
    tl.bar(700, 880, 150, 24, "string", "react")
    tl.bar(1300, 1520, 150, 24, "string", "reactive")
    note(c, "1000ms에 넘긴 'reactive'는 1300ms에 거릅니다.")


# l01-8: 한 번에 거르기와 나눠 거르기

LANE_A, LANE_B = 74, 160  # 두 줄의 막대 y
BLOCK = 96  # 1만 건을 거르는 막대 폭(논리 px)
X0 = 96


def chunk_base(c, show_b):
    head(c, "3만 건을 거르는 동안 클릭이 들어오면")
    row_label(c, LANE_A + 12, "한 번에")
    row_label(c, LANE_B + 12, "나눠서")
    c.text(12, LANE_A + 28, "거르기", "comment", 11, anchor="lm")
    if show_b:
        c.text(12, LANE_B + 28, "거르기", "comment", 11, anchor="lm")
    c.arrow(X0, 236, W - 20, 236, "edge", 1, 6)
    c.text(W - 20, 240, "시간", "line_no", 10, anchor="ra")


def arrive(c, x, y, waiting):
    c.line([(x, y - 14), (x, y + 30)], "def", 2)
    c.text(x + 4, y - 14, "클릭 도착", "def", 10, bold=True, anchor="la")
    if waiting:
        c.text(x + 4, y + 32, "기다림", "comment", 9, anchor="la")


def click_box(c, x, y):
    rect = (x, y, 62, 24)
    c.box(*rect, fill=shade("def", 0.5), outline="def", radius=3)
    c.text(mid_x(rect), mid_y(rect), "클릭 처리", "ink", 10, bold=True, anchor="mm")
    return rect


def chunk_bar(c, x, y, w, label, color_name="builtin"):
    rect = (x, y, w, 24)
    c.box(*rect, fill=shade(color_name, 0.25), outline=None, radius=3)
    c.text(x + 12, mid_y(rect), label, "bg", 10, bold=True, anchor="lm")
    return rect


@figure("l01-8", W, 290)
def chunks(fig):
    def lane_a(c, done):
        rect = chunk_bar(c, X0, LANE_A, BLOCK * 3, "3만 건 거르기", "missing")
        arrive(c, X0 + 8, LANE_A, not done)
        if done:
            long_mark(c, rect)
            return click_box(c, X0 + BLOCK * 3 + 4, LANE_A)
        return None

    c = fig.frame(1600)
    chunk_base(c, False)
    lane_a(c, False)
    note(c, "한 번에 거르면 도착한 클릭은 막대가 끝날 때까지 기다립니다.")

    c = fig.frame(1800)
    chunk_base(c, False)
    lane_a(c, True)
    note(c, "3만 건을 다 거른 뒤에야 클릭이 처리됩니다.")

    c = fig.frame(1400)
    chunk_base(c, True)
    lane_a(c, True)
    chunk_bar(c, X0, LANE_B, BLOCK - 2, "1만 건")
    arrive(c, X0 + 8, LANE_B, True)
    note(c, "나눠 거르면 첫 1만 건만 먼저 거릅니다.")

    c = fig.frame(1600)
    chunk_base(c, True)
    lane_a(c, True)
    chunk_bar(c, X0, LANE_B, BLOCK - 2, "1만 건")
    arrive(c, X0 + 8, LANE_B, False)
    click_box(c, X0 + BLOCK + 2, LANE_B)
    note(c, "묶음 사이에 클릭 태스크가 끼어들어 바로 처리됩니다.")

    c = fig.frame(2200)
    chunk_base(c, True)
    a_click = lane_a(c, True)
    chunk_bar(c, X0, LANE_B, BLOCK - 2, "1만 건")
    arrive(c, X0 + 8, LANE_B, False)
    b_click = click_box(c, X0 + BLOCK + 2, LANE_B)
    x = b_click[0] + b_click[2] + 4
    chunk_bar(c, x, LANE_B, BLOCK - 2, "1만 건")
    chunk_bar(c, x + BLOCK, LANE_B, BLOCK - 2, "1만 건")
    rest = (x + BLOCK * 2 + 2, LANE_B, 76, 24)
    c.box(*rest, fill=shade("string", 0.5), outline="string", radius=3)
    c.text(mid_x(rest), mid_y(rest), "결과 4286건", "ink", 10, bold=True, anchor="mm")
    dashed_arrow(c, mid_x(a_click), a_click[1] + a_click[3] + 2, mid_x(b_click) + 4, b_click[1] - 2, "def")
    # 점선 화살표의 오른쪽 아래에 둬서 선과 겹치지 않게 함
    c.text((mid_x(a_click) + mid_x(b_click)) / 2 + 30, (a_click[1] + b_click[1]) / 2 + 7, "앞당겨진 만큼", "def", 10,
           bold=True, anchor="la")
    note(c, "다 거르는 데는 조금 더 걸리지만 클릭은 첫 묶음 바로 뒤에 처리됩니다.")


if __name__ == "__main__":
    sys.exit(main(sys.modules[__name__], OUT, owner="l01", sections=SECTIONS))
