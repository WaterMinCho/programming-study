#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미션 w01 「상품 목록에 검색 붙이기」 해설 그림. work/explain.md 의 figure 블록 네 개를 그려 web/missions/w01/assets/ 에 씀.

  python3 tools/web_art/w01.py                 그림 네 장을 모두 씀
  python3 tools/web_art/w01.py w01-2           이름을 적은 그림만
  python3 tools/web_art/w01.py --check         쓴 파일을 다시 읽어 한도와 밝은 면, 팔레트까지 봄
  python3 tools/web_art/w01.py --out DIR       저장소 밖 폴더에 씀

상품 이름과 검색어는 work/checks/ 의 검사용 상품 여섯 개와 같게 둠. 그리기는 tools/journey_art/draw.py, 명령줄과 이름 검사는
tools/web_art/figure.py 를 씀. 출제자 컴퓨터에서만 돌고 Pillow 가 필요함.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.journey_art.draw import mid_x, mid_y, shade  # noqa: E402
from tools.web_art.figure import figure, main  # noqa: E402

TOP = 14  # 맨 위 설명 줄의 y
ITEMS = ["텀블러 500", "텀블러 350", "케이블", "가습기", "마우스", "의자"]  # 검사용 상품 여섯 개의 짧은 이름
TUMBLERS = (0, 1)


def head(c, s):
    c.text(20, TOP, s, "comment", 13)


def note(c, s):
    """아래 띠의 설명. 띠보다 길면 그리기 전에 멈춤."""
    if c.text_size(s, 13)[0] > c.width - 24:
        raise ValueError("설명이 그림 폭보다 깁니다: %s" % s)
    c.caption(s)


def card(c, x, y, w, h, rows, fill="gutter", outline="edge", width=1, ink="ink", size=11, mono=False):
    """테두리 상자와 그 안에 가운데 맞춘 글자 몇 줄. 상자 자리 (x, y, w, h) 를 돌려줌."""
    rect = c.box(x, y, w, h, fill=fill, outline=outline, width=width, radius=4)
    gap = size + 4
    top = y + h / 2 - (len(rows) - 1) * gap / 2
    for i, row in enumerate(rows):
        if c.text_size(row, size, mono=mono)[0] > w - 6:
            raise ValueError("상자보다 긴 글자입니다: %s" % row)
        c.text(x + w / 2, top + i * gap, row, ink, size, mono=mono, anchor="mm")
    return rect


# w01-1: 왼쪽은 visible 까지 state 로 둔 판, 오른쪽은 그릴 때 계산하는 판

@figure("w01-1", 560, 300)
def state_or_compute(fig):
    c = fig.frame()
    head(c, "1단계: 걸러 낸 목록을 state로 둘 때와 그릴 때 계산할 때")

    c.text(20, 36, "visible까지 state로 둘 때", "ink", 12, bold=True)
    got = card(c, 20, 74, 104, 34, ["상품을 받을 때"], fill=shade("builtin", 0.75), outline="builtin")
    typed = card(c, 20, 146, 104, 34, ["입력할 때"], fill=shade("builtin", 0.75), outline="builtin")
    products = card(c, 168, 64, 104, 32, ["products"], mono=True)
    query = card(c, 168, 116, 104, 32, ["query"], mono=True)
    visible = card(c, 168, 168, 104, 32, ["visible"], outline="missing", width=2, mono=True)
    for source, target in ((got, products), (got, visible), (typed, query), (typed, visible)):
        c.arrow(source[0] + source[2] + 2, mid_y(source), target[0] - 3, mid_y(target), "builtin", width=1, head=6)
    c.text(168, 61, "state", "comment", 10, anchor="ls")
    c.text(20, 222, "두 곳에서 모두 setVisible을 불러야 함", "comment", 11)
    c.text(20, 240, "한 곳이라도 빠지면 옛 목록이 남음", "missing", 11)

    c.line([(292, 42), (292, 250)], "edge", 1)

    c.text(310, 36, "그릴 때 계산할 때", "ink", 12, bold=True)
    c.text(310, 61, "state", "comment", 10, anchor="ls")
    products = card(c, 310, 64, 96, 32, ["products"], mono=True)
    query = card(c, 310, 116, 96, 32, ["query"], mono=True)
    calc = card(c, 436, 72, 104, 68, ["products", ".filter(…)", "그릴 때마다"], fill=shade("def", 0.75), outline="def", size=10, mono=True)
    for source in (products, query):
        c.arrow(source[0] + source[2] + 2, mid_y(source), calc[0] - 3, mid_y(calc), "def", width=1, head=6)
    shown = card(c, 436, 168, 104, 32, ["화면 목록"], fill=shade("string", 0.75), outline="string")
    c.arrow(mid_x(calc), calc[1] + calc[3] + 2, mid_x(shown), shown[1] - 3, "string", width=2, head=6)
    c.text(310, 222, "state는 두 개만 둠", "comment", 11)
    c.text(310, 240, "맞춰 바꿀 값이 없음", "string", 11)
    note(c, "visible을 그릴 때 계산하면 맞춰 바꾸는 코드가 필요 없습니다.")


# w01-2: 받은 목록을 덮어쓰는 판(1~3 프레임)과 그릴 때 계산하는 판(4 프레임)

ROW_X, CARD_W, CARD_H, CARD_GAP = 96, 70, 30, 6
PRODUCTS_Y, SCREEN_Y = 100, 166


def search_box(c, text):
    c.text(20, 58, "입력칸", "comment", 11, anchor="lm")
    c.box(ROW_X, 44, 180, 28, fill="gutter", outline="edge", radius=4)
    c.text(ROW_X + 10, 58, text or " ", "ink", 12, anchor="lm")


def item_row(c, y, label, shown, gone=(), outline="edge"):
    """상품 카드 한 줄. shown 은 보이는 번호, gone 은 state 에서 사라져 빗금 친 번호."""
    c.text(20, y + CARD_H / 2, label, "comment", 11, mono=label == "products", anchor="lm")
    for i, name in enumerate(ITEMS):
        x = ROW_X + i * (CARD_W + CARD_GAP)
        if i in shown:
            card(c, x, y, CARD_W, CARD_H, [name], fill=shade("string", 0.75), outline=outline, size=10)
        elif i in gone:
            rect = c.box(x, y, CARD_W, CARD_H, fill=shade("missing", 0.75), outline="missing", radius=4)
            c.hatch((rect[0] + 1, rect[1] + 1, rect[2] - 2, rect[3] - 2), shade("missing", 0.5))
        else:
            c.box(x, y, CARD_W, CARD_H, fill=None, outline="edge", radius=4)


@figure("w01-2", 560, 260)
def overwrite(fig):
    title = "덮어쓰는 판: setProducts(products.filter(…))"
    everything = range(len(ITEMS))
    rest = [i for i in everything if i not in TUMBLERS]

    c = fig.frame(1400)
    head(c, title)
    search_box(c, "")
    item_row(c, PRODUCTS_Y, "products", everything)
    item_row(c, SCREEN_Y, "화면", everything)
    note(c, "처음에는 받은 상품 여섯 개가 모두 보입니다.")

    c = fig.frame(1800)
    head(c, title)
    search_box(c, "텀블")
    item_row(c, PRODUCTS_Y, "products", TUMBLERS, gone=rest)
    item_row(c, SCREEN_Y, "화면", TUMBLERS)
    c.tag(ROW_X + 196, 47, "setProducts", "missing", size=11)
    note(c, "'텀블'을 치면 걸러 낸 두 개로 products를 덮어씁니다.")

    c = fig.frame(2000)
    head(c, title)
    search_box(c, "")
    item_row(c, PRODUCTS_Y, "products", TUMBLERS, gone=rest)
    item_row(c, SCREEN_Y, "화면", TUMBLERS, outline="missing")
    c.text(ROW_X, SCREEN_Y + CARD_H + 12, "지운 네 개는 돌아오지 않음", "missing", 11)
    note(c, "검색어를 지워도 products에는 두 개만 남아 있습니다.")

    c = fig.frame(2000)
    head(c, "계산하는 판: products는 두고 visible만 계산")
    search_box(c, "")
    item_row(c, PRODUCTS_Y, "products", everything)
    item_row(c, SCREEN_Y, "화면", everything, outline="string")
    c.tag(ROW_X + 196, 47, "visible", "string", size=11)
    note(c, "products를 고치지 않고 계산하면 여섯 개가 다시 보입니다.")


# w01-3: 주소, query, 화면 사이로 값이 오가는 순서

ADDRESS = (60, 40, 480, 30)
QUERY = (60, 130, 170, 44)
SCREEN = (330, 118, 210, 72)


def address(c, text, outline="edge"):
    x, y, w, h = ADDRESS
    c.text(20, y + h / 2, "주소", "comment", 11, anchor="lm")
    c.box(x, y, w, h, fill="gutter", outline=outline, width=2 if outline != "edge" else 1, radius=4)
    c.text(x + 12, y + h / 2, "localhost:5173" + text, "ink", 12, mono=True, anchor="lm")


def query_box(c, value):
    x, y, w, h = QUERY
    c.text(x, y - 6, "state", "comment", 10, anchor="ls")
    card(c, x, y, w, h, ["query = '%s'" % value], mono=True, size=12)


def screen_box(c, typed, listed, outline="edge"):
    x, y, w, h = SCREEN
    c.text(x, y - 6, "화면", "comment", 10, anchor="ls")
    c.box(x, y, w, h, fill="gutter", outline=outline, width=2 if outline != "edge" else 1, radius=4)
    c.box(x + 10, y + 10, w - 20, 22, fill="bg", outline="edge", radius=3)
    c.text(x + 18, y + 21, typed or " ", "ink", 11, anchor="lm")
    c.text(x + w / 2, y + 52, listed, "ink", 12, bold=True, anchor="mm")
    c.arrow(QUERY[0] + QUERY[2] + 2, mid_y(QUERY), x - 3, mid_y(QUERY), "comment", width=1, head=6)


def read_arrow(c):
    x = QUERY[0] + 40
    c.arrow(x, ADDRESS[1] + ADDRESS[3] + 3, x, QUERY[1] - 16, "def", width=2, head=7)
    c.text(x + 8, 92, "처음 그릴 때 readQuery()", "def", 11, mono=True, anchor="lm")


def write_arrow(c):
    x = QUERY[0] + 130
    c.arrow(x, QUERY[1] - 16, x, ADDRESS[1] + ADDRESS[3] + 3, "decorator", width=2, head=7)
    c.text(x + 8, 92, "입력할 때 writeQuery()", "decorator", 11, mono=True, anchor="lm")


@figure("w01-3", 560, 250)
def address_flow(fig):
    title = "3단계: 주소의 q와 query state가 오가는 순서"

    c = fig.frame(1600)
    head(c, title)
    address(c, "/?q=텀블러", outline="def")
    read_arrow(c)
    query_box(c, "텀블러")
    screen_box(c, "텀블러", "불러오는 중")
    note(c, "처음 그릴 때 주소의 q를 읽어 query의 처음 값으로 씁니다.")

    c = fig.frame(1400)
    head(c, title)
    address(c, "/?q=텀블러")
    query_box(c, "텀블러")
    screen_box(c, "텀블러", "텀블러 2개", outline="string")
    note(c, "상품이 도착하면 query로 걸러 텀블러 두 개만 보입니다.")

    c = fig.frame(1800)
    head(c, title)
    address(c, "/?q=usb", outline="decorator")
    write_arrow(c)
    query_box(c, "usb")
    screen_box(c, "usb", "USB-C 케이블 1개", outline="string")
    note(c, "입력이 바뀌면 setQuery와 함께 replaceState로 주소를 고칩니다.")

    c = fig.frame(1600)
    head(c, title)
    address(c, "/", outline="decorator")
    write_arrow(c)
    query_box(c, "")
    screen_box(c, "", "상품 10개", outline="string")
    note(c, "검색어를 지우면 주소에서 q를 뺍니다.")


# w01-4: "usb" 를 한 글자씩 친 뒤의 방문 기록. 아래 칸이 먼저 쌓인 기록

ENTRY_W, ENTRY_H, ENTRY_GAP, STACK_BOTTOM = 170, 22, 5, 196


def stack(c, x, title, entries):
    """방문 기록을 아래에서 위로 쌓아 그림. 맨 위 칸이 지금 기록. 칸마다 (x, y, w, h) 를 돌려줌."""
    c.text(x, 42, title, "ink", 12, bold=True)
    rects = []
    for i, entry in enumerate(entries):
        y = STACK_BOTTOM - (i + 1) * ENTRY_H - i * ENTRY_GAP
        now = i == len(entries) - 1
        rects.append(card(c, x, y, ENTRY_W, ENTRY_H, [entry], fill=shade("def", 0.75) if now else "gutter",
                          outline="def" if now else "edge", mono=entry.startswith("/"), size=11))
    top = rects[-1]
    c.tag(top[0] + top[2] + 8, top[1] + 4, "지금", "def", size=10)
    return rects


def back_arrow(c, upper, lower):
    x = upper[0] - 14
    c.arrow(x, mid_y(upper), x, mid_y(lower), "decorator", width=2, head=6)


@figure("w01-4", 560, 260)
def history_stack(fig):
    c = fig.frame()
    head(c, "\"usb\"를 한 글자씩 친 뒤의 방문 기록")
    pushed = stack(c, 44, "입력마다 pushState", ["이전 페이지", "/", "/?q=u", "/?q=us", "/?q=usb"])
    back_arrow(c, pushed[-1], pushed[-2])
    c.text(44, 216, "뒤로 가기 한 번에 /?q=us", "decorator", 11, anchor="ls")
    c.line([(292, 42), (292, 214)], "edge", 1)
    replaced = stack(c, 330, "입력마다 replaceState", ["이전 페이지", "/?q=usb"])
    back_arrow(c, replaced[-1], replaced[-2])
    c.text(330, 216, "뒤로 가기 한 번에 이전 페이지", "decorator", 11, anchor="ls")
    note(c, "pushState는 기록을 쌓고, replaceState는 지금 기록만 바꿉니다.")


if __name__ == "__main__":
    sys.exit(main(sys.modules[__name__], "web/missions/w01/assets", owner="w01"))
