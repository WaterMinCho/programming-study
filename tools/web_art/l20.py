#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습 페이지 l20 「꼬리 질문에 답하는 법」의 그림. 글자와 초 단위 시각은 page.md 의 figure 블록 설명을 그대로 씀.

  python3 tools/web_art/l20.py                 web/learn/l20/assets/ 에 그림을 모두 씀
  python3 tools/web_art/l20.py l20-2           이름을 적은 그림만
  python3 tools/web_art/l20.py --check         쓴 파일을 다시 읽어 밝은 면과 팔레트까지 확인
  python3 tools/web_art/l20.py --out DIR       다른 폴더에 씀

그림 이름은 페이지 그림 규칙(l20-1)이라 던전 그림 이름 규칙(1-1a)과 달라서, 이름 검사만 건너뛰는 PageFigure 를 씀.
한도(GIF 300KB, PNG 200KB, 프레임 12개, 프레임 800~2500ms, 논리 폭 560px)와 색, 글꼴은 journey_art 와 같음.
Pillow 가 필요하므로 출제자 컴퓨터에서만 돌림.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.journey_art import LIMITS  # noqa: E402
from tools.journey_art import draw, render  # noqa: E402
from tools.journey_art.draw import figure, mid_x, shade  # noqa: E402

OUT = os.path.join(ROOT, "web", "learn", "l20", "assets")
USAGE = "쓰는 법: python3 tools/web_art/l20.py [그림 이름...] [--check] [--out DIR]"
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


def lines(c, x, y, texts, color_name="ink", size=11, gap=4, anchor="la", width=None, mono=False):
    """여러 줄 글자. x, y 는 첫 줄의 기준점이고 anchor 는 Pillow 기준점. width 를 주면 줄마다 폭을 확인함."""
    for i, s in enumerate(texts):
        if width is not None:
            fit(c, s, size, width, mono=mono)
        c.text(x, y + i * (size + gap), s, color_name, size, mono=mono, anchor=anchor)


# l20-1: 질문 상자(왼쪽)와 답 상자(오른쪽) 세 줄. 답의 낱말 하나에서 다음 질문으로 화살표

Q_X, A_X, BOX_W, BOX_H, ROW_GAP = 20, 300, 240, 50, 80
ROWS = (46, 126, 206)
CHAIN = [
    (("'re'를 치고 'react'를 쳤는데", "'re' 결과가 남았습니다. 왜 그럴까요?"), ("'re' 응답이 늦게 와서", "", "마지막 setResults", "가 덮습니다")),
    (("그러면 어떻게 고치나요?", ""), ("effect가 돌려주는 함수에서", "이전 요청을 ", "끊습니다", "")),
    (("끊긴 요청의 fetch는", "어떻게 되나요?"), ("AbortError로 거부됩니다.", "실패 화면과 구분합니다", "", "")),
]


def marked_line(c, x, y, prefix, word, suffix, size=11):
    """한 줄 글자 가운데 word 만 노란색으로 칠하고 밑줄을 그음. 밑줄 가운데 x 를 돌려줌."""
    px = c.text(x, y, prefix, "ink", size)[0] if prefix else 0
    wx = x + px
    ww = c.text_size(word, size, True)[0] if word else 0
    if word:
        c.text(wx, y, word, "def", size, bold=True)
        c.line([(wx, y + size + 3), (wx + ww, y + size + 3)], "def", 1)
    if suffix:
        c.text(wx + ww, y, suffix, "ink", size)
    fit(c, prefix + word + suffix, size, BOX_W - 20, bold=True)
    return wx + ww / 2


@figure("l20-1", 560, 320)
def chain(fig):
    c = fig.frame()
    head(c, "답에 나온 낱말이 다음 질문이 됩니다")
    c.text(Q_X + BOX_W / 2, 40, "면접관", "comment", 11, anchor="ms")
    c.text(A_X + BOX_W / 2, 40, "지원자", "comment", 11, anchor="ms")
    word_x = None
    for row, (question, answer) in zip(ROWS, CHAIN):
        q = c.box(Q_X, row, BOX_W, BOX_H, fill="gutter", outline="edge", radius=4)
        lines(c, Q_X + 10, row + 9, [s for s in question if s], "ink", 11, width=BOX_W - 20)
        if word_x is not None:
            c.line([(word_x, row - ROW_GAP + BOX_H + 2), (word_x, row - 14), (mid_x(q), row - 14)], "def", 1)
            c.arrow(mid_x(q), row - 14, mid_x(q), row - 2, "def", width=1, head=6)
        a = c.box(A_X, row, BOX_W, BOX_H, fill="gutter", outline="edge", radius=4)
        first, prefix, word, suffix = answer
        c.text(A_X + 10, row + 9, fit(c, first, 11, BOX_W - 20), "ink", 11)
        if word:
            word_x = marked_line(c, A_X + 10, row + 9 + 15, prefix, word, suffix)
        else:
            word_x = None
            if prefix:
                c.text(A_X + 10, row + 9 + 15, fit(c, prefix, 11, BOX_W - 20), "ink", 11)
        c.arrow(Q_X + BOX_W + 2, row + BOX_H / 2, A_X - 2, row + BOX_H / 2, "comment", width=1, head=6)
    c.text(A_X, 266, "설명할 수 없는 낱말은 꺼내지 않습니다", "comment", 11)
    note(c, "세 번째 질문은 둘째 답의 '끊습니다'라는 낱말에서 나왔습니다.")


# l20-2: 같은 답을 결론부터 말한 열과 이유부터 말한 열. 칸은 (이름, 시작 초, 끝 초, 내용)

COL_W, COL_GAP, CELL_H, CELL_Y = 250, 20, 40, 60
FIRST = [("결론", 0, 10, "'re' 응답이 늦게 와 옛 결과를 넣음"), ("이유", 10, 35, "요청은 보낸 순서대로 돌아오지 않음"), ("예", 35, 50, "짧은 검색어가 더 오래 걸림")]
REASON_FIRST = [("이유", 0, 25, "요청은 보낸 순서대로 돌아오지 않음"), ("예", 25, 40, "짧은 검색어가 더 오래 걸림"), ("결론", 40, 50, "'re' 응답이 늦게 와 옛 결과를 넣음")]
ORDER_NOTES = [
    (0, "두 지원자가 같은 답을 다른 순서로 말합니다."),
    (10, "결론부터 말한 쪽은 10초에 면접관이 방향을 압니다."),
    (25, "이유부터 말한 쪽은 25초가 지나도 결론이 없습니다."),
    (40, "왼쪽은 예까지 말하고, 오른쪽은 이제 결론을 시작합니다."),
    (50, "같은 내용인데 면접관이 방향을 안 시각은 10초와 50초입니다."),
]


def column(c, x, title, cells, now):
    c.text(x, 36, title, "ink", 12, bold=True)
    c.text(x + COL_W, 36, "%d초" % now, "def", 12, bold=True, mono=True, anchor="ra")
    known_at = None
    for i, (name, start, end, content) in enumerate(cells):
        y = CELL_Y + i * (CELL_H + 8)
        c.box(x, y, COL_W, CELL_H, fill="gutter", outline="edge", radius=4)
        if now > start:
            done = min(1.0, (now - start) / (end - start))
            color_name = "string" if name == "결론" else "builtin"
            c.box(x + 1, y + 1, (COL_W - 2) * done, CELL_H - 2, fill=shade(color_name, 0.5), outline=None, radius=3)
        c.text(x + 10, y + 7, name, "ink", 11, bold=True)
        if now >= end:
            c.text(x + 10, y + 22, fit(c, content, 10, COL_W - 20), "ink", 10)
        if name == "결론" and now >= end:
            known_at = end
    y = CELL_Y + len(cells) * (CELL_H + 8) + 4
    if known_at is None:
        c.box(x, y, COL_W, 26, fill="gutter", outline="comment", radius=4)
        c.text(x + COL_W / 2, y + 13, "면접관: 아직 방향을 모름", "comment", 11, anchor="mm")
    else:
        c.box(x, y, COL_W, 26, fill=shade("string", 0.5), outline="string", radius=4)
        c.text(x + COL_W / 2, y + 13, "면접관: %d초에 방향을 알고 다음 질문을 고름" % known_at, "ink", 11, anchor="mm")


@figure("l20-2", 560, 270)
def order(fig):
    for now, text in ORDER_NOTES:
        c = fig.frame(1200 if now == 0 else 2200 if now == 50 else 1800 if now == 10 else 1600)
        head(c, "같은 답을 결론부터 말할 때와 이유부터 말할 때")
        column(c, 20, "결론부터", FIRST, now)
        column(c, 20 + COL_W + COL_GAP, "이유부터", REASON_FIRST, now)
        note(c, text)


# l20-3: 막힌 자리에서 꺼낼 말 셋과 피할 것 둘

STUCK = [
    ("아는 것과 모르는 것 나누기", ("끊어 본 적은 없습니다.", "목표는 're' 응답을", "화면에 안 쓰는 것입니다")),
    ("목표에서 거꾸로 말하기", ("'react'를 친 뒤에는", "'re' 응답이 와도", "화면에 쓰지 않아야 합니다")),
    ("추측이라고 밝히기", ("확실하지 않은데,", "끊긴 요청은 에러로", "떨어질 것 같습니다")),
]


@figure("l20-3", 560, 320)
def stuck(fig):
    c = fig.frame()
    head(c, "답이 떠오르지 않을 때")
    top = c.box(180, 40, 200, 34, fill=shade("missing", 0.75), outline="missing", radius=4)
    c.text(mid_x(top), 57, "답이 떠오르지 않음", "ink", 12, bold=True, anchor="mm")
    box_w, gap = 168, 8
    for i, (title, quote) in enumerate(STUCK):
        x = 20 + i * (box_w + gap)
        box = c.box(x, 104, box_w, 34, fill=shade("builtin", 0.5), outline="builtin", radius=4)
        c.text(mid_x(box), 121, fit(c, title, 11, box_w - 12, bold=True), "ink", 11, bold=True, anchor="mm")
        c.arrow(mid_x(top), 76, mid_x(box), 102, "comment", width=1, head=6)
        lines(c, mid_x(box), 148, quote, "ink", 10, gap=3, anchor="ma", width=box_w - 8)
    c.text(20, 232, "피할 것", "comment", 11)
    for i, s in enumerate(("말없이 생각함", "모르겠습니다로 끝냄")):
        x = 80 + i * 160
        w = c.text_size(s, 11)[0] + 20
        c.box(x, 226, w, 24, fill="gutter", outline="comment", radius=4)
        c.text(x + w / 2, 238, s, "comment", 11, anchor="mm")
        c.line([(x + 6, 238), (x + w - 6, 238)], "missing", 2)
    note(c, "셋 가운데 할 수 있는 것을 말하면 면접관이 방향을 잡아 줍니다.")


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
