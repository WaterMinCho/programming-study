#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습 페이지 l06 「React 렌더링과 key」의 그림. 값과 순서는 page.md 의 코드 블록과 figure 블록 설명을 따름.

  python3 tools/web_art/l06.py                 web/learn/l06/assets/ 에 그림을 모두 씀
  python3 tools/web_art/l06.py 6a-1 6d-1       이름을 적은 그림만
  python3 tools/web_art/l06.py --check         쓴 파일을 다시 읽어 밝은 면과 팔레트까지 확인
  python3 tools/web_art/l06.py --out DIR       다른 폴더에 씀

그리기는 tools/journey_art/draw.py, 이름 규칙과 명령줄은 tools/web_art/figure.py 를 씀. 그림 이름은 절 키(6a, 6b, 6c, 6d)를
붙인 사슬 절 그림 꼴임. Pillow 가 필요하므로 출제자 컴퓨터에서만 돌림.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.journey_art.draw import mid_x, mid_y, shade  # noqa: E402
from tools.web_art.figure import figure, main  # noqa: E402

OUT = "web/learn/l06/assets"
SECTIONS = ("6a", "6b", "6c", "6d")
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


def panel(c, rect, title, fill="gutter", outline="edge", width=1):
    """제목 줄이 붙은 칸."""
    x, y, w, h = rect
    c.box(x, y, w, h, fill=fill, outline=outline, width=width, radius=4)
    c.text(x + 8, y + 7, fit(c, title, 11, w - 16), "comment", 11)
    return rect


def strike(c, rect, color_name="missing"):
    """칸 가운데를 가로지르는 줄. 지워질 행 표시."""
    c.line([(rect[0] + 2, mid_y(rect)), (rect[0] + rect[2] - 2, mid_y(rect))], color_name, 2)


# 6a-1: set 함수가 요청한 다시 렌더링, 렌더링의 비교, 커밋 단계

STEPS_6A = ["요청", "렌더링", "커밋 단계"]
SCREEN = (380, 40, 160, 148)
OLD = (20, 92, 166, 84)
NEW = (198, 92, 166, 84)


def step_chips(c, lit):
    for i, label in enumerate(STEPS_6A):
        x = 20 + i * 118
        on = i == lit
        rect = c.box(x, 40, 104, 26, fill=shade("decorator", 0.5) if on else "gutter",
                     outline="decorator" if on else "edge", width=2 if on else 1, radius=4)
        c.text(mid_x(rect), mid_y(rect), label, "ink", 12, bold=on, anchor="mm")
        if i < len(STEPS_6A) - 1:
            c.arrow(x + 106, mid_y(rect), x + 116, mid_y(rect), "comment", width=1, head=5)


def cart_screen(c, count, good=False):
    panel(c, SCREEN, "화면")
    h2 = (SCREEN[0] + 10, SCREEN[1] + 30, SCREEN[2] - 20, 26)
    c.text(h2[0], mid_y(h2), "장바구니 %d개" % count, "ink", 13, bold=True, anchor="lm")
    field = c.box(SCREEN[0] + 10, SCREEN[1] + 70, SCREEN[2] - 20, 26, fill="bg", outline="edge", radius=3)
    c.text(field[0] + 6, mid_y(field), fit(c, "문 앞에 놓아 주세요", 11, field[2] - 12), "ink", 11, anchor="lm")
    if good:
        num_x = h2[0] + c.text_size("장바구니 ", 13, bold=True)[0]
        num_w = c.text_size(str(count), 13, bold=True)[0]
        c.highlight((num_x - 1, h2[1] + 4, num_w + 2, 18), "string", width=2, pad=1)
    return field


def result_box(c, rect, title, count, mark=None):
    """렌더링 결과 칸. mark 가 있으면 숫자에 그 색 테두리를 두르고 input 줄에 '같음' 을 적음."""
    panel(c, rect, title)
    x, y = rect[0] + 10, rect[1] + 30
    c.text(x, y, "<h2>장바구니 %d개</h2>" % count, "ink", 11, mono=True)
    c.text(x, y + 26, "<input />", "ink", 11, mono=True)
    if mark:
        num_x = x + c.text_size("<h2>장바구니 ", 11, mono=True)[0]
        num_w = c.text_size(str(count), 11, mono=True)[0]
        c.highlight((num_x - 1, y - 2, num_w + 2, 16), mark, width=2, pad=1)
        c.text(rect[0] + rect[2] - 10, y + 26, "같음", "comment", 10, anchor="ra")


@figure("6a-1", 560, 240)
def render_commit(fig):
    c = fig.frame(1400)
    head(c, "[맨 위 상품 빼기] 클릭")
    step_chips(c, 0)
    c.text(20, 92, "setItems(items.slice(1))", "builtin", 12, mono=True)
    c.text(20, 116, "다시 렌더링을 React에 요청함", "ink", 12)
    cart_screen(c, 3)
    note(c, "set 함수는 state를 바로 고치지 않고 다시 렌더링을 요청합니다.")

    c = fig.frame(2000)
    head(c, "React가 CartPage와 CartHeader를 다시 부름")
    step_chips(c, 1)
    result_box(c, OLD, "앞 결과", 3, "decorator")
    result_box(c, NEW, "새 결과", 2, "decorator")
    c.tag(NEW[0] + NEW[2] - 46, NEW[1] + 6, "다름", "decorator", size=10)
    cart_screen(c, 3)
    note(c, "렌더링에서는 새 결과를 앞 결과와 비교만 하고 DOM에는 손대지 않습니다.")

    c = fig.frame(2200)
    head(c, "달라진 숫자만 DOM에 고침")
    step_chips(c, 2)
    result_box(c, OLD, "앞 결과", 3)
    result_box(c, NEW, "새 결과", 2)
    field = cart_screen(c, 2, good=True)
    c.tag(field[0], field[1] + field[3] + 6, "노드를 새로 만들지 않음", "comment", size=10)
    note(c, "커밋 단계는 h2의 숫자만 바꾸고, 입력칸 글자는 남습니다.")


# 6b-1: index key 와 id key 로 텀블러를 뺐을 때

COLS = {"index": 20, "id": 290}
COL_W = 250
ROW_Y = (68, 108, 148)
ROW_H = 32


def cart_row(c, x, y, key, name, value, mark=None, faded=False, new_key=None):
    """key 꼬리표, 상품 이름, 요청 사항 칸이 든 행. new_key 가 있으면 꼬리표 옆에 새 배열의 key 를 적음. (x, y, w, h) 를 돌려줌."""
    ink = "comment" if faded else "ink"
    rect = c.box(x, y, COL_W, ROW_H, fill="gutter", outline="edge", radius=4)
    c.tag(x + 6, y + 8, key, "comment" if faded else "builtin", size=10)
    if new_key is not None:
        c.text(x + 36, mid_y(rect), "→" + new_key, "def", 11, bold=True, mono=True, anchor="lm")
    c.text(x + 68, mid_y(rect), fit(c, name, 11, 72), ink, 11, anchor="lm")
    field = c.box(x + 144, y + 5, COL_W - 150, ROW_H - 10, fill="bg", outline="edge", radius=3)
    if value:
        c.text(field[0] + 6, mid_y(field), fit(c, value, 11, field[2] - 12), ink, 11, anchor="lm")
    if mark:
        c.highlight(field, mark, width=2, pad=1)
    return rect


def key_columns(c):
    c.text(COLS["index"], 44, "key={index}", "def", 12, bold=True, mono=True)
    c.text(COLS["id"], 44, "key={item.id}", "def", 12, bold=True, mono=True)


@figure("6b-1", 560, 260)
def list_keys(fig):
    items = [("텀블러", "파란색으로"), ("머그컵", ""), ("드립백 세트", "디카페인")]

    c = fig.frame(1600)
    head(c, "요청 사항을 적은 장바구니 목록")
    key_columns(c)
    for i, (name, value) in enumerate(items):
        cart_row(c, COLS["index"], ROW_Y[i], str(i), name, value)
        cart_row(c, COLS["id"], ROW_Y[i], "c%d" % (i + 1), name, value)
    note(c, "왼쪽은 순서 번호를, 오른쪽은 상품 id를 key로 줍니다.")

    c = fig.frame(1800)
    head(c, "[텀블러 빼기] 클릭: 새 배열의 key")
    key_columns(c)
    new_keys = [(None, None), ("0", "c2"), ("1", "c3")]
    for i, (name, value) in enumerate(items):
        left = cart_row(c, COLS["index"], ROW_Y[i], str(i), name, value, new_key=new_keys[i][0])
        right = cart_row(c, COLS["id"], ROW_Y[i], "c%d" % (i + 1), name, value, new_key=new_keys[i][1])
        if i == 0:
            strike(c, left)
            strike(c, right)
    note(c, "텀블러를 빼면 index는 머그컵 0, 드립백 세트 1로 당겨집니다.")

    c = fig.frame(2400)
    head(c, "React가 key로 짝지은 결과")
    key_columns(c)
    cart_row(c, COLS["index"], ROW_Y[0], "0", "머그컵", "파란색으로", mark="missing")
    cart_row(c, COLS["index"], ROW_Y[1], "1", "드립백 세트", "")
    gone = cart_row(c, COLS["index"], ROW_Y[2], "2", "(지워짐)", "디카페인", faded=True)
    strike(c, gone, "comment")
    gone = cart_row(c, COLS["id"], ROW_Y[0], "c1", "(지워짐)", "파란색으로", faded=True)
    strike(c, gone, "comment")
    cart_row(c, COLS["id"], ROW_Y[1], "c2", "머그컵", "")
    cart_row(c, COLS["id"], ROW_Y[2], "c3", "드립백 세트", "디카페인", mark="string")
    note(c, "index key는 텀블러의 요청 사항을 머그컵에 남기고, id key는 상품을 따라갑니다.")


# 6c-1: 쿠폰을 칠 때 RecommendList 가 다시 렌더링되는지

CASES = [
    ("memo 없음", "비교 안 함", False),
    ("memo, 새 화살표 함수", "아니요", False),
    ("memo, useCallback", "예", True),
]


@figure("6c-1", 560, 260)
def memo_cases(fig):
    c = fig.frame()
    head(c, "쿠폰 코드를 한 글자 칠 때")
    for i, (title, answer, skipped) in enumerate(CASES):
        x = 20 + i * 180
        c.text(x, 40, fit(c, title, 12, 170, bold=True), "def", 12, bold=True)
        parent = c.box(x, 62, 168, 34, fill=shade("builtin", 0.75), outline="builtin", radius=4)
        c.text(mid_x(parent), parent[1] + 9, "CartPage 다시 렌더링", "ink", 11, anchor="mm")
        c.text(mid_x(parent), parent[1] + 25, "coupon 바뀜", "comment", 10, anchor="mm")
        h2 = c.box(x, 124, 40, 30, fill="gutter", outline="edge", radius=4)
        c.text(mid_x(h2), mid_y(h2), "h2", "ink", 11, mono=True, anchor="mm")
        child = c.box(x + 52, 124, 116, 80, fill="gutter", outline="string" if skipped else "missing", width=2, radius=4)
        c.text(child[0] + 8, child[1] + 8, "RecommendList", "ink", 11, mono=True)
        c.text(child[0] + 8, child[1] + 30, "onAdd 같음?", "comment", 10)
        c.text(child[0] + 8, child[1] + 44, answer, "ink", 11, bold=True)
        c.text(child[0] + 8, child[1] + 62, "건너뜀" if skipped else "다시 렌더링", "string" if skipped else "missing", 11, bold=True)
        c.arrow(mid_x(parent) - 40, parent[1] + parent[3] + 2, mid_x(h2), h2[1] - 2, "comment", width=1, head=5)
        c.arrow(mid_x(parent) + 20, parent[1] + parent[3] + 2, mid_x(child), child[1] - 2, "comment", width=1, head=5)
    note(c, "memo는 같은 onAdd 함수를 받을 때만 렌더링을 건너뜁니다.")


# 6d-1: 값 세 번과 업데이트 함수 세 번이 쌓였다가 차례로 적용됨

QCOLS = {"value": 20, "updater": 290}
QROW_Y = (98, 130, 162)
QROW_H = 26
LEFT_RESULT = ["2", "2", "2"]
RIGHT_RESULT = ["1 → 2", "2 → 3", "3 → 4"]


def queue_column(c, key, title, request, results, lit):
    x = QCOLS[key]
    c.text(x, 40, fit(c, title, 11, 250, mono=True), "def", 11, bold=True, mono=True)
    now = c.box(x, 62, 110, 24, fill="gutter", outline="edge", radius=4)
    c.text(mid_x(now), mid_y(now), "지금 state 1", "ink", 11, anchor="mm")
    for i, y in enumerate(QROW_Y):
        on = i < lit
        cur = i == lit - 1
        rect = c.box(x, y, 130, QROW_H, fill=shade("decorator", 0.5) if cur else "gutter",
                     outline="decorator" if cur else "edge", width=2 if cur else 1, radius=4)
        c.text(x + 8, mid_y(rect), request, "ink", 11, mono=True, anchor="lm")
        if on:
            c.arrow(x + 134, mid_y(rect), x + 150, mid_y(rect), "comment", width=1, head=5)
            c.text(x + 156, mid_y(rect), results[i], "ink", 12, bold=True, mono=True, anchor="lm")


@figure("6d-1", 560, 270)
def update_queue(fig):
    for lit, ms in ((0, 1600), (1, 1400), (2, 1400), (3, 2200)):
        c = fig.frame(ms)
        head(c, "[3개 더] 한 번 클릭 뒤 다음 렌더링" if lit else "[3개 더] 한 번 클릭: 쌓인 요청")
        queue_column(c, "value", "setQty(qty + 1) 세 번", "2로 바꿈", LEFT_RESULT, lit)
        queue_column(c, "updater", "setQty((q) => q + 1) 세 번", "q => q + 1", RIGHT_RESULT, lit)
        if lit == 3:
            for key, text, color_name in (("value", "2개", "missing"), ("updater", "4개", "string")):
                screen = c.box(QCOLS[key], 196, 110, 28, fill="gutter", outline="edge", radius=4)
                c.text(mid_x(screen), mid_y(screen), text, "ink", 13, bold=True, anchor="mm")
                c.highlight(screen, color_name, width=2, pad=2)
        notes = ["클릭 한 번에 요청 세 개가 쌓입니다.",
                 "다음 렌더링에서 첫 요청부터 차례로 적용합니다.",
                 "업데이트 함수는 앞 결과를 받아 1을 더합니다.",
                 "값을 넘긴 쪽은 2개, 업데이트 함수를 넘긴 쪽은 4개가 됩니다."]
        note(c, notes[lit])


if __name__ == "__main__":
    sys.exit(main(sys.modules[__name__], OUT, owner="l06", sections=SECTIONS))
