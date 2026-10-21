#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미션 w03 「거래내역 불러오기」 해설 그림. work/explain.md 의 figure 블록 네 개를 그려 web/missions/w03/assets/ 에 씀.

  python3 tools/web_art/w03.py            그림 네 장을 모두 씀
  python3 tools/web_art/w03.py --check    쓴 파일을 다시 읽어 한도와 밝은 면, 팔레트까지 봄
  python3 tools/web_art/w03.py --out DIR  저장소 밖 폴더에 씀

그리기는 알고리즘 여행의 tools/journey_art/draw.py 를 그대로 쓰고 한도도 같음(GIF 300KB, PNG 200KB, 프레임 12개,
프레임 800~2500ms, 논리 폭 560px). 그림 이름은 설계 4.5절의 w03-1 꼴이라 draw.Figure 의 던전식 이름 검사(1-1a)만 건너뜀.
출제자 컴퓨터에서만 돌고 Pillow 가 필요함.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.journey_art import LIMITS  # noqa: E402
from tools.journey_art import draw, render  # noqa: E402
from tools.journey_art.draw import figure, mid_x, mid_y, shade  # noqa: E402

MISSION = "w03"
ASSETS = os.path.join(ROOT, "web", "missions", MISSION, "assets")
USAGE = "쓰는 법: python3 tools/web_art/w03.py [--check] [--out DIR]"
TOP = 14  # 맨 위 설명 줄의 y

# 시간축. 0~1.6초를 X0~X1 에 폄
X0, X1, SECONDS = 70, 470, 1.6
AXIS_Y, BAR_H = 62, 20
ROW_Y = {"living": 84, "saving": 124}
TICKS = [(0, "0초"), (0.4, "0.4"), (0.7, "0.7"), (1.5, "1.5초")]
SCREEN = (330, 176, 200, 52)  # 오른쪽 아래 화면 칸 (x, y, w, h)


class MissionFigure(draw.Figure):
    """이름이 w03-1 꼴인 그림. 폭 한도는 같게 보고 던전식 이름 검사만 하지 않음."""

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


def lines(c, x, y, rows, color_name="ink", size=11, gap=15, bold=False, mono=False):
    """여러 줄 글자를 가운데 위 기준으로 한 줄씩 적음. Pillow 는 여러 줄 글자에 가운데 기준점을 받지 않음."""
    for i, row in enumerate(rows):
        c.text(x, y + i * gap, row, color_name, size, bold=bold, mono=mono, anchor="ma")


def card(c, x, y, w, h, rows, fill="gutter", outline="edge", width=1, ink="ink"):
    """테두리 상자와 그 안의 글자 몇 줄."""
    rect = c.box(x, y, w, h, fill=fill, outline=outline, width=width, radius=4)
    lines(c, x + w / 2, y + h / 2 - len(rows) * 7.5 + 1, rows, ink)
    return rect


def tx(seconds):
    """초를 시간축의 x 로."""
    return X0 + (X1 - X0) * seconds / SECONDS


def dashed(c, x1, y1, x2, y2, color_name="comment", dash=4):
    """점선. draw.line 은 실선만 그리므로 짧은 토막으로 이음."""
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if length == 0:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0
    while pos < length:
        end = min(pos + dash, length)
        c.line([(x1 + ux * pos, y1 + uy * pos), (x1 + ux * end, y1 + uy * end)], color_name, 1)
        pos += dash * 2


def timeline(c, title):
    """시간축과 눈금, 줄 이름."""
    head(c, title)
    c.line([(X0, AXIS_Y), (X1 + 10, AXIS_Y)], "edge", 1)
    for seconds, label in TICKS:
        x = tx(seconds)
        c.line([(x, AXIS_Y - 4), (x, AXIS_Y + 4)], "edge", 1)
        c.text(x, AXIS_Y - 7, label, "line_no", 10, mono=True, anchor="ms")
    for key, label in (("living", "생활비"), ("saving", "저축")):
        c.text(20, ROW_Y[key] + BAR_H / 2, label, "comment", 12, anchor="lm")


def bar(c, key, start, end, color_name, cut=False):
    """요청 막대. cut 이면 끊긴 요청이라 흐린 색으로 그림."""
    x1, x2 = tx(start), tx(end)
    fill = shade(color_name, 0.5) if cut else color_name
    return c.box(x1, ROW_Y[key], max(x2 - x1, 3), BAR_H, fill=fill, outline=None, radius=3)


def screen(c, text, outline=None):
    """오른쪽 아래의 화면 칸."""
    x, y, w, h = SCREEN
    c.text(x, y - 6, "화면", "comment", 11, anchor="ls")
    rect = c.box(x, y, w, h, fill="gutter", outline=outline or "edge", width=2 if outline else 1, radius=4)
    c.text(x + w / 2, y + h / 2, text, "ink", 13, bold=True, anchor="mm")
    return rect


def click_mark(c, seconds, label):
    """탭을 누른 순간의 눈금과 이름."""
    x = tx(seconds)
    c.line([(x, AXIS_Y + 6), (x, ROW_Y["saving"] + BAR_H + 6)], "def", 1)
    c.text(x + 4, ROW_Y["saving"] + BAR_H + 8, label, "def", 10, anchor="la")


@figure("w03-1", 560, 300)
def state_shapes(fig):
    c = fig.frame()
    head(c, "1단계: 값 세 개를 따로 둘 때와 status 하나로 묶을 때")
    c.text(20, 42, "isLoading, error, items를 따로 둘 때", "ink", 12, bold=True)
    cols = [("error 없음", 118), ("error 있음", 212)]
    rows = [("isLoading true", 88), ("isLoading false", 148)]
    for label, x in cols:
        c.text(x + 42, 72, label, "comment", 10, mono=True, anchor="ma")
    for label, y in rows:
        c.text(20, y + 25, label, "comment", 10, mono=True, anchor="lm")
    card(c, 118, 88, 84, 50, ["불러오는 중"], fill=shade("builtin", 0.75))
    bad = card(c, 212, 88, 84, 50, ["로딩 표시와", "실패 문구"], fill=shade("missing", 0.75), outline="missing", width=2)
    c.hatch((bad[0] + 1, bad[1] + 1, bad[2] - 2, bad[3] - 2), shade("missing", 0.5))
    lines(c, mid_x(bad), bad[1] + 11, ["로딩 표시와", "실패 문구"], "ink")
    card(c, 118, 148, 84, 50, ["목록 또는", "내역 없음"], fill=shade("string", 0.75))
    card(c, 212, 148, 84, 50, ["실패"], fill=shade("missing", 0.75))
    c.text(20, 212, "빗금 칸은 화면에 없어야 하는 조합", "missing", 11)
    c.text(20, 230, "세 값을 바꾸는 줄이 하나라도 빠지면 생김", "comment", 11)
    c.line([(312, 42), (312, 250)], "edge", 1)
    c.text(332, 42, "status 하나로 묶을 때", "ink", 12, bold=True)
    pills = [("loading", "builtin", []), ("error", "missing", []), ("success", "string", ["items: Transaction[]"])]
    for i, (name, color_name, extra) in enumerate(pills):
        y = 76 + i * 50
        rect = c.box(332, y, 196, 40, fill=shade(color_name, 0.75), outline=color_name, radius=4)
        c.text(344, mid_y(rect), "status: '%s'" % name, "ink", 12, mono=True, anchor="lm")
        for s in extra:
            c.text(344, y + 40 + 4, s, "comment", 10, mono=True, anchor="la")
    c.text(332, 236, "한 번에 한 상태만", "comment", 11)
    note(c, "status로 묶으면 로딩 중이면서 에러인 칸이 애초에 없습니다.")


@figure("w03-2", 560, 300)
def race_before(fig):
    title = "3단계 고치기 전: 생활비 통장을 누르고 0.4초 뒤 저축 통장을 누름"
    c = fig.frame(1400)
    timeline(c, title)
    bar(c, "living", 0, 0.02, "builtin")
    screen(c, "불러오는 중")
    note(c, "0초: 생활비 통장 요청이 나갑니다.")

    c = fig.frame(1400)
    timeline(c, title)
    bar(c, "living", 0, 0.4, "builtin")
    bar(c, "saving", 0.4, 0.42, "string")
    click_mark(c, 0.4, "저축 탭 클릭")
    screen(c, "불러오는 중")
    note(c, "0.4초: 저축 통장을 눌러 두 번째 요청이 나갑니다. 첫 요청은 그대로 진행됩니다.")

    c = fig.frame(1600)
    timeline(c, title)
    bar(c, "living", 0, 0.7, "builtin")
    done = bar(c, "saving", 0.4, 0.7, "string")
    click_mark(c, 0.4, "저축 탭 클릭")
    box = screen(c, "저축 통장 내역")
    c.arrow(done[0] + done[2] + 4, mid_y(done), box[0] - 3, mid_y(box), "string", width=1)
    note(c, "0.7초: 저축 응답이 와서 화면에 저축 내역이 보입니다.")

    c = fig.frame(2200)
    timeline(c, title)
    done = bar(c, "living", 0, 1.5, "builtin")
    bar(c, "saving", 0.4, 0.7, "string")
    click_mark(c, 0.4, "저축 탭 클릭")
    box = screen(c, "생활비 통장 내역", outline="missing")
    end_x = done[0] + done[2]
    c.arrow(end_x, done[1] + done[3] + 3, end_x, box[1] - 3, "missing", width=2)
    c.tag(box[0], box[1] + box[3] + 6, "마지막 setState가 덮음", "missing", size=11)
    note(c, "1.5초: 늦게 온 생활비 응답이 저축 내역을 덮습니다.")


@figure("w03-3", 560, 300)
def race_after(fig):
    title = "3단계 고친 뒤: 저축 탭을 누르면 정리 함수가 생활비 요청을 끊음"
    c = fig.frame(1400)
    timeline(c, title)
    bar(c, "living", 0, 0.02, "builtin")
    screen(c, "불러오는 중")
    note(c, "0초: 생활비 통장 요청이 나갑니다.")

    c = fig.frame(1800)
    timeline(c, title)
    cut = bar(c, "living", 0, 0.4, "builtin", cut=True)
    bar(c, "saving", 0.4, 0.42, "string")
    click_mark(c, 0.4, "저축 탭 클릭")
    c.tag(cut[0] + cut[2] + 6, cut[1] - 2, "abort()", "decorator", size=11)
    screen(c, "불러오는 중")
    note(c, "0.4초: 정리 함수가 abort()를 불러 생활비 요청이 끊깁니다.")

    c = fig.frame(2200)
    timeline(c, title)
    cut = bar(c, "living", 0, 0.4, "builtin", cut=True)
    done = bar(c, "saving", 0.4, 0.7, "string")
    click_mark(c, 0.4, "저축 탭 클릭")
    c.tag(cut[0] + cut[2] + 6, cut[1] - 2, "abort()", "decorator", size=11)
    box = screen(c, "저축 통장 내역", outline="string")
    c.arrow(done[0] + done[2] + 4, mid_y(done), box[0] - 3, mid_y(box), "string", width=2)
    x = tx(1.5)
    dashed(c, x, AXIS_Y + 6, x, ROW_Y["saving"] + BAR_H + 6)
    c.text(x - 4, ROW_Y["living"] - 4, "AbortError, 화면에 쓰지 않음", "comment", 10, anchor="rs")
    note(c, "1.5초: 끊긴 요청의 AbortError는 화면에 쓰지 않아 저축 내역이 남습니다.")


@figure("w03-4", 560, 220)
def effect_order(fig):
    c = fig.frame()
    head(c, "탭이 바뀔 때 React가 함수를 부르는 순서")
    boxes = [
        (["accountId", "'living'", "으로 그림"], "gutter", "edge"),
        (["effect(living)", "실행", "요청 1"], shade("builtin", 0.75), "builtin"),
        (["저축 탭 클릭", "accountId", "'saving'", "으로 그림"], "gutter", "edge"),
        (["정리(living)", "abort()"], shade("decorator", 0.5), "decorator"),
        (["effect(saving)", "실행", "요청 2"], shade("string", 0.75), "string"),
    ]
    w, h, gap, y = 96, 72, 14, 48
    rects = []
    for i, (rows, fill, outline) in enumerate(boxes):
        x = 12 + i * (w + gap)
        rects.append(card(c, x, y, w, h, rows, fill=fill, outline=outline, width=2 if outline != "edge" else 1))
    for left, right in zip(rects, rects[1:]):
        c.arrow(left[0] + left[2] + 2, mid_y(left), right[0] - 2, mid_y(right), "ink", width=2, head=6)
    tag = c.tag(mid_x(rects[1]) - 36, 150, "요청 1 진행 중", "builtin", size=11)
    gone = c.tag(mid_x(rects[3]) - 22, 150, "끊김", "decorator", size=11)
    c.arrow(gone[0] - 4, mid_y(gone), tag[0] + tag[2] + 4, mid_y(tag), "decorator", width=2, head=6)
    note(c, "React는 새 화면을 그린 뒤 정리(living)을 부르고 나서 effect(saving)을 실행합니다.")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    out_dir = ASSETS
    if "--out" in args:
        at = args.index("--out")
        if at + 1 >= len(args):
            print(USAGE)
            return 2
        out_dir = os.path.abspath(args[at + 1])
        del args[at:at + 2]
    if args:
        print(USAGE)
        return 2
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    try:
        for name, width, height, fn in draw.figures(sys.modules[__name__]):
            fig = MissionFigure(name, width, height)
            fn(fig)
            path = fig.save(out_dir)
            row = render.inspect(path, check)
            if not name.startswith(MISSION + "-"):
                row["problems"].insert(0, "이름이 %s- 로 시작해야 합니다" % MISSION)
            row.update(name=name, path=path)
            rows.append(row)
    except ValueError as e:
        print(e)
        return 1
    print("쓴 폴더: %s" % out_dir)
    return 1 if render.report(rows, out_dir) else 0


if __name__ == "__main__":
    sys.exit(main())
