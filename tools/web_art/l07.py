#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습 페이지 l07 「state로 둘 값, effect, 서버 상태」의 그림. 값과 순서는 page.md 의 코드 블록과 figure 블록 설명을 따름.

  python3 tools/web_art/l07.py                 web/learn/l07/assets/ 에 그림을 모두 씀
  python3 tools/web_art/l07.py 7a-1 7b-2       이름을 적은 그림만
  python3 tools/web_art/l07.py --check         쓴 파일을 다시 읽어 밝은 면과 팔레트까지 확인
  python3 tools/web_art/l07.py --out DIR       다른 폴더에 씀

그리기는 tools/journey_art/draw.py, 이름 규칙과 명령줄은 tools/web_art/figure.py 를 씀. 그림 이름은 절 키(7a, 7b, 7c)를 붙인
사슬 절 그림 꼴임. Pillow 가 필요하므로 출제자 컴퓨터에서만 돌림.
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

OUT = "web/learn/l07/assets"
SECTIONS = ("7a", "7b", "7c")
TOP = 14  # 맨 위 설명 줄의 y


def head(c, s):
    c.text(20, TOP, fit(c, s, 13, c.width - 40), "comment", 13)


def note(c, s):
    """아래 띠의 설명. 띠보다 길면 그리기 전에 멈춤."""
    c.caption(fit(c, s, 13, c.width - 24))


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


def dashed_arrow(c, x1, y1, x2, y2, color_name="comment", head_len=7):
    """점선 화살표. 머리는 끝점에 둠."""
    angle = math.atan2(y2 - y1, x2 - x1)
    ux, uy = math.cos(angle), math.sin(angle)
    bx, by = x2 - ux * head_len, y2 - uy * head_len
    dashed(c, x1, y1, bx, by, color_name)
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


def rows(c, x, y, items, color_name="ink", size=11, gap=16, mono=False, anchor="la", width=None):
    """글자 여러 줄을 한 줄씩 적음. width 가 있으면 줄마다 넘치는지 확인함."""
    for i, s in enumerate(items):
        if width:
            fit(c, s, size, width, mono=mono)
        c.text(x, y + i * gap, s, color_name, size, mono=mono, anchor=anchor)


def panel(c, rect, title, fill="gutter", outline="edge", width=1):
    """제목 줄이 붙은 칸."""
    x, y, w, h = rect
    c.box(x, y, w, h, fill=fill, outline=outline, width=width, radius=4)
    c.text(x + 8, y + 7, fit(c, title, 11, w - 16), "comment", 11)
    return rect


# 7a-1: 상품 셋이 늦게 도착해도 filtered 는 첫 렌더링의 빈 배열로 남음

PROPS = (20, 50, 160, 124)
STATE = (196, 50, 160, 124)
VIEW = (392, 50, 148, 124)
ITEMS = ["USB-C 케이블", "usb 허브", "무선 충전기"]


def filtered_base(c, title, arrived):
    head(c, title)
    panel(c, PROPS, "props", outline="string" if arrived else "edge", width=2 if arrived else 1)
    if arrived:
        c.text(PROPS[0] + 10, PROPS[1] + 30, "products:", "ink", 11, mono=True)
        rows(c, PROPS[0] + 18, PROPS[1] + 50, ITEMS, "string", 11, width=PROPS[2] - 26)
    else:
        c.text(PROPS[0] + 10, PROPS[1] + 30, "products: []", "ink", 11, mono=True)
    panel(c, STATE, "state")
    c.text(STATE[0] + 10, STATE[1] + 30, "query: ''", "ink", 11, mono=True)
    c.text(STATE[0] + 10, STATE[1] + 50, "filtered: []", "ink", 11, mono=True)
    panel(c, VIEW, "화면")
    c.text(mid_x(VIEW), VIEW[1] + 66, fit(c, "검색 결과가 없습니다", 11, VIEW[2] - 12), "ink", 11, anchor="mm")


@figure("7a-1", 560, 260)
def stale_copy(fig):
    c = fig.frame(1400)
    filtered_base(c, "첫 렌더링, 응답 전", False)
    note(c, "첫 렌더링에서 filtered는 products의 빈 배열로 시작합니다.")

    c = fig.frame(1800)
    filtered_base(c, "응답 도착, 다시 렌더링", True)
    note(c, "products가 상품 셋으로 바뀌어도 filtered는 바뀌지 않습니다.")

    c = fig.frame(2200)
    filtered_base(c, "응답 도착, 다시 렌더링", True)
    filt = (STATE[0] + 6, STATE[1] + 44, STATE[2] - 12, 22)
    c.highlight(filt, "missing", width=2, pad=1)
    c.highlight(VIEW, "missing", width=2, pad=2)
    y = PROPS[1] + PROPS[3] + 22
    dashed(c, mid_x(PROPS), PROPS[1] + PROPS[3] + 2, mid_x(PROPS), y, "missing")
    dashed(c, mid_x(PROPS), y, mid_x(STATE), y, "missing")
    dashed_arrow(c, mid_x(STATE), y, mid_x(STATE), STATE[1] + STATE[3] + 3, "missing")
    c.tag(mid_x(STATE) + 10, y - 9, "useState 초기값은 첫 렌더링에서만", "missing", size=10)
    note(c, "사용자가 글자를 치기 전까지 화면에 상품이 보이지 않습니다.")


# 7a-2: state 로 둘지 가리는 세 질문

@figure("7a-2", 560, 300)
def three_questions(fig):
    c = fig.frame()
    head(c, "상품 검색 화면의 값을 세 질문에 차례로 대 봄")
    questions = [
        ("시간이 지나도 바뀌지 않나요?", "안내 글 '상품 검색'"),
        ("부모가 props로 넘기나요?", "products"),
        ("다른 state나 props로 계산할 수 있나요?", "visible, 결과 개수, 고른 상품 객체"),
    ]
    boxes = []
    for i, (q, example) in enumerate(questions):
        y = 40 + i * 60
        q_rect = c.box(20, y, 270, 42, fill="gutter", outline="edge", radius=4)
        c.text(32, y + 21, fit(c, q, 12, 250), "ink", 12, anchor="lm")
        e_rect = c.box(330, y, 210, 42, fill=shade("comment", 0.75), outline="edge", radius=4)
        c.text(340, y + 6, "state 아님", "comment", 10)
        c.text(340, y + 22, fit(c, example, 11, 192), "ink", 11)
        c.arrow(q_rect[0] + q_rect[2] + 2, mid_y(q_rect), e_rect[0] - 2, mid_y(e_rect), "comment", width=1, head=6)
        c.text(310, mid_y(q_rect) - 4, "예", "comment", 10, anchor="ms")
        boxes.append(q_rect)
    last = c.box(20, 222, 270, 36, fill=shade("string", 0.75), outline="string", width=2, radius=4)
    c.text(32, mid_y(last), "state로 둠: query, selectedId", "ink", 12, bold=True, anchor="lm")
    for a, b in zip(boxes, boxes[1:] + [last]):
        c.arrow(80, a[1] + a[3] + 1, 80, b[1] - 1, "comment", width=1, head=6)
        c.text(88, a[1] + a[3] + 11, "아니요", "comment", 10, anchor="lm")
    note(c, "세 질문에 모두 '아니요'인 값만 state로 둡니다.")


# 7b-1: productId 가 바뀌고 컴포넌트가 빠질 때 정리 함수가 불리는 차례

T_OPEN, T_P2, T_CLOSE = 46, 140, 300
CLEAN_W = 64
ROW1, ROW2, BAR_H = 92, 132, 22
CONSOLE = (400, 50, 140, 128)
VIEW_7B = (20, 190, 360, 26)


def stock_base(c, ticks, console, view):
    head(c, "재고 알림 effect와 정리 함수가 불리는 차례(운영 빌드)")
    c.line([(20, 66), (380, 66)], "edge", 1)
    for t, label in ticks:
        c.line([(t, 61), (t, 71)], "def", 2)
        c.text(t, 56, label, "def", 10, anchor="ms")
    panel(c, CONSOLE, "콘솔")
    rows(c, CONSOLE[0] + 10, CONSOLE[1] + 28, console, "ink", 11, gap=20, mono=True, width=CONSOLE[2] - 20)
    c.box(*VIEW_7B, fill="gutter", outline="edge", radius=4)
    c.text(VIEW_7B[0] + 8, mid_y(VIEW_7B), "화면", "comment", 11, anchor="lm")
    c.text(VIEW_7B[0] + 50, mid_y(VIEW_7B), view, "ink", 11, anchor="lm")


def effect_bar(c, x1, x2, y, label, open_end=False):
    fill = shade("builtin", 0.5)
    rect = c.box(x1, y, x2 - x1, BAR_H, fill=fill, outline=None if open_end else "builtin", radius=3)
    c.text(x1 + 6, y + BAR_H / 2, label, "ink", 11, mono=True, anchor="lm")
    return rect


def clean_box(c, x, y, label):
    rect = c.box(x, y, CLEAN_W, BAR_H, fill=shade("decorator", 0.5), outline="decorator", width=2, radius=3)
    c.text(x + 5, y + BAR_H / 2, label, "ink", 10, mono=True, anchor="lm")
    return rect


@figure("7b-1", 560, 260)
def cleanup_timeline(fig):
    open_tick = [(T_OPEN, "화면 열림")]
    p2_tick = open_tick + [(T_P2, "p2 보기 클릭")]
    close_tick = p2_tick + [(T_CLOSE, "닫기 클릭")]

    c = fig.frame(1400)
    stock_base(c, open_tick, ["구독 p1"], "p1 재고 알림 켜짐")
    effect_bar(c, T_OPEN, T_OPEN + 70, ROW1, "effect(p1)", open_end=True)
    note(c, "화면이 열리면 effect(p1)이 실행됩니다.")

    c = fig.frame(1800)
    stock_base(c, p2_tick, ["구독 p1", "구독 해지 p1"], "p2 재고 알림 켜짐")
    effect_bar(c, T_OPEN, T_P2, ROW1, "effect(p1)")
    clean_box(c, T_P2, ROW1, "정리(p1)")
    note(c, "productId가 p2로 바뀌면 p1 effect의 정리 함수가 먼저 불립니다.")

    c = fig.frame(1600)
    stock_base(c, p2_tick, ["구독 p1", "구독 해지 p1", "구독 p2"], "p2 재고 알림 켜짐")
    effect_bar(c, T_OPEN, T_P2, ROW1, "effect(p1)")
    clean_box(c, T_P2, ROW1, "정리(p1)")
    effect_bar(c, T_P2 + CLEAN_W, T_CLOSE - 10, ROW2, "effect(p2)", open_end=True)
    note(c, "그 뒤에 새 값으로 effect(p2)가 실행됩니다.")

    c = fig.frame(2200)
    stock_base(c, close_tick, ["구독 p1", "구독 해지 p1", "구독 p2", "구독 해지 p2"], "(StockBadge가 빠짐)")
    effect_bar(c, T_OPEN, T_P2, ROW1, "effect(p1)")
    clean_box(c, T_P2, ROW1, "정리(p1)")
    effect_bar(c, T_P2 + CLEAN_W, T_CLOSE, ROW2, "effect(p2)")
    clean_box(c, T_CLOSE, ROW2, "정리(p2)")
    note(c, "닫기를 누르면 컴포넌트가 빠지면서 마지막 정리 함수가 불립니다.")


# 7b-2: StrictMode 의 실행, 정리, 실행. 정리 함수가 없으면 키 함수가 둘 남음

COLS = {"missing": 20, "fixed": 290}
COL_W = 250
STEPS = ["실행", "정리", "다시 실행"]


def strict_column(c, key, title, step, handlers, removed=False, console=None, good=None):
    x = COLS[key]
    c.text(x, 40, title, "ink", 12, bold=True)
    for i, label in enumerate(STEPS):
        sx = x + i * 84
        lit = i == step
        rect = c.box(sx, 58, 76, 24, fill=shade("decorator", 0.5) if lit else "gutter",
                     outline="decorator" if lit else "edge", width=2 if lit else 1, radius=4)
        c.text(mid_x(rect), mid_y(rect), label, "ink", 11, anchor="mm")
        if i < len(STEPS) - 1:
            c.arrow(sx + 77, mid_y(rect), sx + 83, mid_y(rect), "comment", width=1, head=4)
    win = panel(c, (x, 94, COL_W, 54), "window의 keydown 함수")
    for n in range(handlers):
        c.tag(x + 10 + n * 74, 118, "키 함수", "builtin", size=11)
    if removed:
        chip = c.box(x + 10, 118, 62, 19, fill=None, outline="comment", radius=9)
        c.text(mid_x(chip), mid_y(chip), "떼어 냄", "comment", 10, anchor="mm")
    out = panel(c, (x, 160, COL_W, 58), "콘솔")
    if console:
        rows(c, x + 10, 184, console, "ink", 11, gap=16, width=COL_W - 20)
    if good is not None:
        c.highlight(out, "string" if good else "missing", width=2, pad=2)
    return win


@figure("7b-2", 560, 270)
def strict_double(fig):
    c = fig.frame(1400)
    head(c, "StrictMode가 처음 화면에 나타난 SearchBox에 하는 일")
    strict_column(c, "missing", "정리 함수 없음", 0, 1)
    strict_column(c, "fixed", "정리 함수 있음", 0, 1)
    note(c, "처음 화면에 나타나면 effect가 실행되어 키 함수가 하나 붙습니다.")

    c = fig.frame(1800)
    head(c, "StrictMode가 처음 화면에 나타난 SearchBox에 하는 일")
    strict_column(c, "missing", "정리 함수 없음", 1, 1)
    strict_column(c, "fixed", "정리 함수 있음", 1, 0, removed=True)
    note(c, "정리 단계에서 정리 함수가 없는 쪽은 붙인 함수가 남습니다.")

    c = fig.frame(1800)
    head(c, "StrictMode가 처음 화면에 나타난 SearchBox에 하는 일")
    strict_column(c, "missing", "정리 함수 없음", 2, 2)
    strict_column(c, "fixed", "정리 함수 있음", 2, 1)
    note(c, "effect를 다시 실행하면 왼쪽에는 키 함수가 둘 붙어 있습니다.")

    c = fig.frame(2200)
    head(c, "'/'를 한 번 눌렀을 때")
    strict_column(c, "missing", "정리 함수 없음", 2, 2, console=["검색창으로 이동", "검색창으로 이동"], good=False)
    strict_column(c, "fixed", "정리 함수 있음", 2, 1, console=["검색창으로 이동"], good=True)
    note(c, "'/'를 한 번 누르면 왼쪽은 두 줄, 오른쪽은 한 줄이 찍힙니다.")


# 7c-1: 같은 쿼리 키는 요청 하나를 함께 쓰고, 돌아온 탭은 캐시를 먼저 보여 줌

COMP = [(20, 56, 130, 44), (20, 116, 130, 44)]
COMP_NAMES = ["목록", "상품 수 배지"]
CACHE_X, CACHE_W = 196, 196
ROW_KITCHEN, ROW_ELEC = 64, 132
SERVER = (440, 80, 100, 64)


def cache_row(c, y, key, value, state="normal"):
    """캐시 칸 한 줄. state 는 normal, loading, idle(쓰는 곳 없음)."""
    fill = {"normal": shade("string", 0.75), "loading": "gutter", "idle": shade("comment", 0.75)}[state]
    outline = {"normal": "string", "loading": "edge", "idle": "edge"}[state]
    rect = c.box(CACHE_X, y, CACHE_W, 44, fill=fill, outline=outline, radius=4)
    c.text(CACHE_X + 8, y + 6, fit(c, key, 10, CACHE_W - 16, mono=True), "comment" if state == "idle" else "ink", 10, mono=True)
    c.text(CACHE_X + 8, y + 26, value, "comment" if state == "idle" else "ink", 11)
    return rect


def cache_base(c, title, tab, shown):
    head(c, title)
    c.text(20, 40, "탭: %s" % tab, "def", 11, bold=True)
    for (x, y, w, h), name in zip(COMP, COMP_NAMES):
        c.box(x, y, w, h, fill="gutter", outline="edge", radius=4)
        c.text(x + 8, y + 6, name, "comment", 10)
        c.text(x + 8, y + 24, shown, "ink", 11)
    c.text(CACHE_X, 40, "캐시", "comment", 11)
    c.box(*SERVER, fill="gutter", outline="edge", radius=4)
    c.text(mid_x(SERVER), mid_y(SERVER), "서버", "ink", 12, bold=True, anchor="mm")


def comp_arrows(c, row_y, color_name="comment"):
    for x, y, w, h in COMP:
        c.arrow(x + w + 2, y + h / 2, CACHE_X - 2, row_y + 22, color_name, width=1, head=5)


@figure("7c-1", 560, 260)
def query_cache(fig):
    c = fig.frame(1600)
    cache_base(c, "같은 쿼리 키를 두 컴포넌트가 씀: 요청 1번", "주방", "불러오는 중")
    row = cache_row(c, ROW_KITCHEN, "['products', '주방']", "불러오는 중", "loading")
    comp_arrows(c, ROW_KITCHEN)
    c.arrow(row[0] + row[2] + 2, mid_y(row), SERVER[0] - 2, SERVER[1] + 16, "builtin", width=2, head=6)
    note(c, "같은 쿼리 키를 쓰는 두 컴포넌트가 요청 하나를 함께 기다립니다.")

    c = fig.frame(1600)
    cache_base(c, "응답이 오면 두 컴포넌트가 같은 목록을 씀", "주방", "주방 목록")
    row = cache_row(c, ROW_KITCHEN, "['products', '주방']", "주방 목록")
    comp_arrows(c, ROW_KITCHEN, "string")
    c.arrow(SERVER[0] - 2, SERVER[1] + 28, row[0] + row[2] + 2, mid_y(row) + 6, "string", width=2, head=6)
    note(c, "응답이 캐시에 들어가면 두 컴포넌트가 같은 목록을 보여 줍니다.")

    c = fig.frame(1800)
    cache_base(c, "'전자기기' 탭: 새 키로 요청", "전자기기", "불러오는 중")
    idle = cache_row(c, ROW_KITCHEN, "['products', '주방']", "주방 목록", "idle")
    c.tag(idle[0] + 4, idle[1] + idle[3] + 3, "쓰는 곳 없음, 5분 뒤 지움", "comment", size=10)
    row = cache_row(c, ROW_ELEC + 18, "['products', '전자기기']", "불러오는 중", "loading")
    comp_arrows(c, ROW_ELEC + 18)
    c.arrow(row[0] + row[2] + 2, mid_y(row), SERVER[0] - 2, SERVER[1] + SERVER[3] - 12, "builtin", width=2, head=6)
    note(c, "탭을 바꾸면 쿼리 키가 바뀌어 새 칸을 만들고 요청을 보냅니다.")

    c = fig.frame(2200)
    cache_base(c, "다시 '주방' 탭: 캐시 먼저, 뒤에서 다시 받기", "주방", "주방 목록")
    row = cache_row(c, ROW_KITCHEN, "['products', '주방']", "주방 목록")
    cache_row(c, ROW_ELEC + 18, "['products', '전자기기']", "전자기기 목록", "idle")
    comp_arrows(c, ROW_KITCHEN, "string")
    dashed_arrow(c, row[0] + row[2] + 2, mid_y(row), SERVER[0] - 2, SERVER[1] + 16, "builtin")
    # 꼬리표를 서버 칸 아래 두 줄로 나눔. 한 줄이면 '전자기기' 캐시 칸과 겹침
    below = SERVER[1] + SERVER[3]
    c.text(mid_x(SERVER), below + 14, fit(c, "뒤에서 다시 받기", 11, SERVER[2]), "builtin", 11, anchor="mm")
    c.text(mid_x(SERVER), below + 30, fit(c, "staleTime 0", 11, SERVER[2], mono=True), "builtin", 11, mono=True, anchor="mm")
    note(c, "돌아온 탭은 받아 둔 목록을 바로 보여 주고 뒤에서 다시 받습니다.")


# 7c-2: 상품 화면의 값을 놓는 자리

@figure("7c-2", 560, 290)
def where_values_live(fig):
    c = fig.frame()
    head(c, "상품 화면의 값을 놓는 자리")
    code = True
    cols = [
        ("렌더링 중 계산", [("visible", code), ("결과 개수", False), ("고른 상품 객체", False)], None),
        ("컴포넌트 state", [("query", code), ("selectedId", code)], "builtin"),
        ("전역 상태", [("Context, store", False), ("테마", False), ("언어", False), ("비교함 id", False)], "keyword"),
        ("서버 상태 캐시", [("React Query", False), ("['products',", code), ("  category]", code)], "string"),
    ]
    rects = []
    for i, (title, items, color_name) in enumerate(cols):
        x = 20 + i * 132
        rect = (x, 44, 124, 146)
        if color_name is None:
            dashed_box(c, rect, "comment")
            c.text(x + 8, 52, title, "comment", 11, bold=True)
        else:
            c.box(*rect, fill=shade(color_name, 0.75), outline=color_name, radius=4)
            c.text(x + 8, 52, fit(c, title, 11, 108, bold=True), "ink", 11, bold=True)
        for k, (item, mono) in enumerate(items):
            c.text(x + 8, 76 + k * 18, fit(c, item, 11, 108, mono=mono), "ink", 11, mono=mono)
        rects.append(rect)
    c.text(mid_x(rects[0]), 178, "저장하지 않음", "comment", 10, anchor="ms")
    last = rects[-1]
    server = c.box(last[0] + 22, 206, 80, 28, fill="gutter", outline="edge", radius=4)
    c.text(mid_x(server), mid_y(server), "서버", "ink", 11, bold=True, anchor="mm")
    c.arrow(mid_x(last), last[1] + last[3] + 2, mid_x(server), server[1] - 2, "string", width=2, head=6)
    c.text(20, 222, "같은 데이터를 두 칸에 복사하지 않습니다", "missing", 11, anchor="lm")
    note(c, "계산할 수 있는 값은 어디에도 저장하지 않고 렌더링 중에 계산합니다.")


if __name__ == "__main__":
    sys.exit(main(sys.modules[__name__], OUT, owner="l07", sections=SECTIONS))
