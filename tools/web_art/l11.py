#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습 페이지 l11 「바꾸기 쉬운 코드와 테스트」의 그림. 값과 순서는 page.md 의 코드 블록과 figure 블록 설명을 따름.

  python3 tools/web_art/l11.py                 web/learn/l11/assets/ 에 그림을 모두 씀
  python3 tools/web_art/l11.py 11a-1 11c-2     이름을 적은 그림만
  python3 tools/web_art/l11.py --check         쓴 파일을 다시 읽어 밝은 면과 팔레트까지 확인
  python3 tools/web_art/l11.py --out DIR       다른 폴더에 씀

그리기는 tools/journey_art/draw.py, 이름 규칙과 명령줄은 tools/web_art/figure.py 를 씀. 그림 이름은 절 키(11a, 11b, 11c)를
붙인 사슬 절 그림 꼴임. Pillow 가 필요하므로 출제자 컴퓨터에서만 돌림.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.journey_art.draw import mid_x, mid_y, shade  # noqa: E402
from tools.web_art.figure import figure, main  # noqa: E402

OUT = "web/learn/l11/assets"
SECTIONS = ("11a", "11b", "11c")
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


def panel(c, rect, title, fill="gutter", outline="edge", width=1):
    """제목 줄이 붙은 칸."""
    x, y, w, h = rect
    c.box(x, y, w, h, fill=fill, outline=outline, width=width, radius=4)
    c.text(x + 8, y + 7, fit(c, title, 11, w - 16), "comment", 11)
    return rect


def name_box(c, rect, name, fill="gutter", outline="edge", ink="ink", width=1, size=11):
    """컴포넌트·함수 이름 하나가 가운데 든 칸."""
    c.box(*rect, fill=fill, outline=outline, width=width, radius=4)
    c.text(mid_x(rect), mid_y(rect), fit(c, name, size, rect[2] - 10, mono=True), ink, size, mono=True, anchor="mm")
    return rect


class Timeline:
    """가로 시간축. 값을 논리 x 로 바꾸고 막대를 그림."""

    def __init__(self, c, x0, x1, max_value, y):
        self.c, self.x0, self.x1, self.max_value, self.y = c, x0, x1, max_value, y

    def x(self, value):
        return self.x0 + (self.x1 - self.x0) * value / self.max_value

    def axis(self, ticks, unit):
        self.c.line([(self.x0, self.y), (self.x1, self.y)], "edge", 1)
        for t in ticks:
            x = self.x(t)
            self.c.line([(x, self.y - 3), (x, self.y + 3)], "edge", 1)
            self.c.text(x, self.y + 5, "%d%s" % (t, unit), "line_no", 10, mono=True, anchor="ma")

    def bar(self, start, end, y, h, fill, outline=None, label=None, ink="ink", width=1):
        x = self.x(start)
        w = max(2, self.x(end) - x)
        rect = self.c.box(x, y, w, h, fill=fill, outline=outline, width=width, radius=3)
        if label:
            self.c.text(x + w / 2, y + h / 2, fit(self.c, label, 10, w - 6, bold=True), ink, 10, bold=True, anchor="mm")
        return rect


# 11a-1: canEdit 이 지나가는 길. 왼쪽은 고치기 전, 오른쪽은 CampaignTable 이 children 을 받은 뒤

LEFT, RIGHT = (20, 40, 250, 196), (290, 40, 250, 196)


def can_edit_tag(c, x, y, color_name="def"):
    c.tag(x, y, "canEdit", color_name, size=10)


@figure("11a-1", 560, 310)
def drilling(fig):
    c = fig.frame()
    head(c, "canEdit이 CampaignRow까지 가는 길")
    panel(c, LEFT, "고치기 전")
    page = name_box(c, (70, 64, 150, 30), "CampaignPage")
    table = name_box(c, (70, 128, 150, 30), "CampaignTable", fill=shade("comment", 0.75), ink="comment")
    row = name_box(c, (70, 192, 150, 30), "CampaignRow", outline="def", width=2)
    for a, b in ((page, table), (table, row)):
        c.arrow(mid_x(a), a[1] + a[3] + 1, mid_x(b), b[1] - 1, "def", width=2, head=6)
        can_edit_tag(c, mid_x(a) + 8, a[1] + a[3] + 8)
    c.text(table[0] + table[2] + 6, mid_y(table) - 7, "읽지 않고", "comment", 10)
    c.text(table[0] + table[2] + 6, mid_y(table) + 6, "넘김", "comment", 10)

    panel(c, RIGHT, "children으로 받은 뒤")
    page2 = name_box(c, (340, 64, 150, 30), "CampaignPage")
    frame = (318, 124, 194, 104)
    dashed(c, frame[0], frame[1], frame[0] + frame[2], frame[1], "comment")
    dashed(c, frame[0] + frame[2], frame[1], frame[0] + frame[2], frame[1] + frame[3], "comment")
    dashed(c, frame[0] + frame[2], frame[1] + frame[3], frame[0], frame[1] + frame[3], "comment")
    dashed(c, frame[0], frame[1] + frame[3], frame[0], frame[1], "comment")
    c.text(frame[0] + 8, frame[1] + 6, "CampaignTable (표 틀)", "comment", 10, mono=True)
    row2 = name_box(c, (340, 176, 150, 30), "CampaignRow", outline="def", width=2)
    c.arrow(mid_x(page2), page2[1] + page2[3] + 1, mid_x(row2), row2[1] - 1, "def", width=2, head=6)
    can_edit_tag(c, mid_x(page2) + 8, page2[1] + page2[3] + 8)

    c.text(mid_x(LEFT), 246, "canPause를 더할 때 고칠 곳: 셋", "missing", 11, anchor="ma")
    c.text(mid_x(RIGHT), 246, "canPause를 더할 때 고칠 곳: 둘", "string", 11, anchor="ma")
    note(c, "표가 행을 children으로 받으면 canEdit이 표를 거치지 않습니다.")


# 11b-1: 따로 둘 코드와 한곳에 모을 코드

@figure("11b-1", 560, 270)
def change_reasons(fig):
    c = fig.frame()
    head(c, "생김새가 아니라 바뀌는 이유로 정함")
    left = panel(c, (20, 40, 255, 180), "따로 둠: 바뀌는 이유가 다름")
    for i, (name, reason) in enumerate((("validateCampaignName", "광고 심사 기준"), ("validateMemo", "운영 팀 메모 규칙"))):
        y = 72 + i * 70
        box = name_box(c, (30, y, 150, 30), name, size=10)
        c.text(box[0] + box[2] + 8, mid_y(box), fit(c, reason, 10, left[0] + left[2] - box[0] - box[2] - 12), "def", 10, anchor="lm")
        c.text(box[0], y + 36, "심사 기준이 바뀌면 이 함수만 고침" if i == 0 else "메모 규칙이 바뀌면 이 함수만 고침", "comment", 10)

    right = panel(c, (290, 40, 250, 180), "한곳에 모음: 바뀌는 이유가 같음")
    places = ["표의 예산 칸", "예산 수정 확인 창", "요약 카드"]
    target = name_box(c, (430, 100, 100, 34), "formatBudget", fill=shade("string", 0.75), outline="string", width=2, size=10)
    for i, place in enumerate(places):
        box = c.box(300, 66 + i * 40, 104, 26, fill="gutter", outline="edge", radius=3)
        c.text(mid_x(box), mid_y(box), fit(c, place, 10, box[2] - 8), "ink", 10, anchor="mm")
        c.arrow(box[0] + box[2] + 2, mid_y(box), target[0] - 2, target[1] + 8 + i * 9, "string", width=1, head=5)
    c.text(mid_x(target), target[1] + target[3] + 8, "예산 표기 규칙", "def", 10, anchor="ma")
    c.text(mid_x(right), 196, "표기를 바꾸면 이 함수만 고침", "comment", 10, anchor="ma")
    note(c, "합칠지는 바뀌는 이유로 정합니다.")


# 11b-2: 남은 10분을 쓰는 두 순서. 막대는 (시작 분, 끝 분, 이름, 색)

TIDY_FIRST = [(0, 4, "파일 나누기", "decorator"), (4, 7, "공통 함수 만들기", "decorator"), (7, 10, "요구 동작", None)]
WORK_FIRST = [(0, 4, "요구 동작", "string"), (4, 5, "확인", "builtin"), (5, 7, "이름 정리", "keyword"),
              (7, 10, "남은 일을 말함", "string")]
ROW_TIDY, ROW_WORK, ROW_H = 66, 140, 28
TEN_MIN = [(0, "남은 시간은 10분입니다."), (4, "4분: 위는 파일을 나누고, 아래는 요구를 동작하게 만듭니다."),
           (7, "7분: 아래는 확인과 이름 정리까지 끝냈습니다."), (10, "10분: 위는 요구가 끝나지 않았고, 아래는 남은 일을 말합니다.")]


def lane(c, tl, bars, y, now):
    for start, end, name, color_name in bars:
        if start >= now:
            continue
        stop = min(end, now)
        if color_name is None:
            rect = tl.bar(start, stop, y, ROW_H, "gutter", outline="comment")
            c.hatch((rect[0] + 1, rect[1] + 1, rect[2] - 2, rect[3] - 2), "comment")
            c.text(mid_x(rect), y + ROW_H + 4, "%s: 끝나지 않음" % name, "missing", 10, anchor="ma")
            continue
        last = name == "남은 일을 말함"
        tl.bar(start, stop, y, ROW_H, shade(color_name, 0.5), outline="string" if last else color_name,
               label=name, width=2 if last else 1)


@figure("11b-2", 560, 260)
def last_ten(fig):
    for now, text in TEN_MIN:
        c = fig.frame({0: 1400, 4: 1600, 7: 1800, 10: 2500}[now])
        head(c, "요구 하나에 10분이 남았을 때")
        tl = Timeline(c, 110, 530, 10, 196)
        c.text(20, ROW_TIDY + ROW_H / 2, "정리부터", "ink", 12, bold=True, anchor="lm")
        c.text(20, ROW_WORK + ROW_H / 2, "동작부터", "ink", 12, bold=True, anchor="lm")
        end_x = tl.x(10)
        dashed(c, end_x, 46, end_x, 190, "def")
        c.text(end_x - 4, 46, "면접 끝", "def", 10, anchor="ra")
        lane(c, tl, TIDY_FIRST, ROW_TIDY, now)
        lane(c, tl, WORK_FIRST, ROW_WORK, now)
        tl.axis([0, 2, 4, 6, 8, 10], "분")
        note(c, text)


# 11c-1: getBy 는 클릭이 끝난 순간 한 번 찾고, findBy 는 안내가 그려질 때까지 다시 찾음

CLICK_END, REPLY = 3, 20
ROW_TEST, ROW_SERVER, ROW_FIND = 60, 108, 166
SCREEN = (420, 46, 120, 120)


def screen_box(c, lines, good=False):
    panel(c, SCREEN, "화면")
    for i, (s, color_name) in enumerate(lines):
        c.text(SCREEN[0] + 10, SCREEN[1] + 30 + i * 20, fit(c, s, 10, SCREEN[2] - 16), color_name, 10)
    if good:
        c.highlight(SCREEN, "string", width=2, pad=2)


@figure("11c-1", 560, 260)
def get_vs_find(fig):
    def base(c, title, server_end, server_open=True):
        head(c, title)
        c.text(20, ROW_TEST + 10, "테스트", "ink", 11, bold=True, anchor="lm")
        c.text(20, ROW_SERVER + 10, "가짜 서버", "ink", 11, bold=True, anchor="lm")
        c.text(20, ROW_FIND + 10, "findByText", "ink", 11, mono=True, anchor="lm")
        tl = Timeline(c, 110, 400, 30, 208)
        tl.axis([0, 10, 20, 30], "ms")
        c.text(tl.x(0), ROW_TEST - 4, "user.click", "comment", 10, mono=True, anchor="ls")
        c.text(tl.x(0), ROW_SERVER - 4, "중지 요청", "comment", 10, anchor="ls")
        if server_open:
            tl.bar(0, server_end, ROW_SERVER, 20, shade("decorator", 0.5))
        else:
            tl.bar(0, server_end, ROW_SERVER, 20, shade("decorator", 0.5), outline="decorator")
            rx = tl.x(server_end)
            c.line([(rx, ROW_SERVER - 6), (rx, ROW_SERVER + 26)], "def", 2)
            c.text(rx + 4, ROW_SERVER - 6, "응답", "def", 10)
        return tl

    c = fig.frame(1400)
    tl = base(c, "클릭과 중지 요청이 함께 시작됨", 1)
    tl.bar(0, 1, ROW_TEST, 20, "builtin")
    screen_box(c, [("진행 중", "ink"), ("[중지]", "comment")])
    note(c, "0ms에 클릭과 중지 요청이 함께 시작됩니다.")

    c = fig.frame(2000)
    tl = base(c, "await user.click이 끝난 순간", CLICK_END + 1)
    tl.bar(0, CLICK_END, ROW_TEST, 20, shade("builtin", 0.5), outline="builtin")
    x = tl.x(CLICK_END)
    c.box(x + 6, ROW_TEST + 4, 12, 12, fill="missing", outline=None, radius=6)
    c.tag(x + 24, ROW_TEST + 1, "getByText: 안내 없음, 에러", "missing", size=10)
    screen_box(c, [("진행 중", "ink"), ("[중지]", "comment")])
    note(c, "클릭이 끝난 순간 getByText가 한 번 찾고 바로 실패합니다.")

    c = fig.frame(1800)
    tl = base(c, "20ms에 응답이 옴", REPLY, server_open=False)
    tl.bar(0, CLICK_END, ROW_TEST, 20, shade("builtin", 0.5), outline="builtin")
    screen_box(c, [("중지됨", "ink"), ("캠페인을", "string"), ("중지했습니다", "string")])
    note(c, "응답이 오면 상태가 바뀌고 안내가 그려집니다.")

    c = fig.frame(2200)
    tl = base(c, "findByText는 화면이 바뀌면 다시 찾음", REPLY, server_open=False)
    tl.bar(0, CLICK_END, ROW_TEST, 20, shade("builtin", 0.5), outline="builtin")
    sx, gx, fy = tl.x(CLICK_END), tl.x(REPLY), ROW_FIND + 10
    c.box(sx - 5, fy - 5, 10, 10, fill="comment", outline=None, radius=5)
    c.text(sx, fy + 10, "없음", "comment", 10, anchor="ma")
    dashed(c, sx + 8, fy, gx - 9, fy, "comment")
    c.text((sx + gx) / 2, fy - 8, "기다림", "comment", 10, anchor="ms")
    c.box(gx - 7, fy - 7, 14, 14, fill="string", outline=None, radius=7)
    c.text(gx + 12, fy, "찾음", "string", 11, bold=True, anchor="lm")
    screen_box(c, [("중지됨", "ink"), ("캠페인을", "string"), ("중지했습니다", "string")], good=True)
    note(c, "findByText는 없으면 기다리다가 화면이 바뀔 때 다시 찾아 안내를 찾습니다.")


# 11c-2: 진짜 시계의 waitFor 는 1초에 포기하고, 가짜 시계는 테스트가 2초와 1초를 앞당김

REAL_ROW, FAKE_ROW = 54, 140
NOTICE = (452, 0, 88, 40)


def clock_row(c, y, title):
    c.text(20, y + 22, title, "ink", 12, bold=True, anchor="lm")
    tl = Timeline(c, 110, 420, 3, y + 52)
    tl.axis([0, 1, 2, 3], "초")
    gone = tl.x(3)
    c.line([(gone, y + 10), (gone, y + 48)], "missing", 1)
    c.text(gone, y + 6, "안내 사라짐", "missing", 10, anchor="ms")
    return tl


def notice_box(c, y, shown, good=False):
    rect = (NOTICE[0], y + 12, NOTICE[2], NOTICE[3])
    c.box(*rect, fill="gutter", outline="string" if good else "edge", width=2 if good else 1, radius=4)
    if shown:
        c.text(mid_x(rect), mid_y(rect), "안내 보임", "string", 11, anchor="mm")
    else:
        c.text(mid_x(rect), mid_y(rect), "(비어 있음)", "comment", 10, anchor="mm")


def needle(c, tl, y, value):
    x = tl.x(value)
    c.line([(x, y + 14), (x, y + 48)], "def", 2)
    c.box(x - 5, y + 9, 10, 10, fill="def", outline=None, radius=5)


@figure("11c-2", 560, 260)
def fake_clock(fig):
    def base(c):
        head(c, "안내가 3초 뒤에 사라지는지 확인하기")
        return clock_row(c, REAL_ROW, "진짜 시계"), clock_row(c, FAKE_ROW, "가짜 시계")

    c = fig.frame(1400)
    real, fake = base(c)
    needle(c, fake, FAKE_ROW, 0)
    notice_box(c, REAL_ROW, True)
    notice_box(c, FAKE_ROW, True)
    note(c, "0초에 안내가 보입니다. 안내는 3초에 사라집니다.")

    c = fig.frame(2000)
    real, fake = base(c)
    bar = real.bar(0, 1, REAL_ROW + 16, 20, shade("builtin", 0.5), outline="builtin", label="waitFor")
    c.tag(bar[0] + bar[2] + 6, REAL_ROW + 17, "1초에 포기, 실패", "missing", size=10)
    needle(c, fake, FAKE_ROW, 0)
    notice_box(c, REAL_ROW, True)
    notice_box(c, FAKE_ROW, True)
    note(c, "진짜 시계에서 waitFor는 기본 1초만 기다리고 실패합니다.")

    c = fig.frame(1800)
    real, fake = base(c)
    real.bar(0, 1, REAL_ROW + 16, 20, shade("builtin", 0.5), outline="builtin", label="waitFor")
    dashed(c, fake.x(0), FAKE_ROW + 30, fake.x(2), FAKE_ROW + 30, "def")
    needle(c, fake, FAKE_ROW, 2)
    c.text(fake.x(0), FAKE_ROW + 25, "advanceTimersByTimeAsync(2000)", "def", 10, mono=True, anchor="ls")
    notice_box(c, REAL_ROW, True)
    notice_box(c, FAKE_ROW, True)
    note(c, "가짜 시계는 테스트가 2초를 한 번에 앞당깁니다. 안내는 남아 있습니다.")

    c = fig.frame(2200)
    real, fake = base(c)
    real.bar(0, 1, REAL_ROW + 16, 20, shade("builtin", 0.5), outline="builtin", label="waitFor")
    dashed(c, fake.x(0), FAKE_ROW + 30, fake.x(2), FAKE_ROW + 30, "comment")
    dashed(c, fake.x(2), FAKE_ROW + 30, fake.x(3), FAKE_ROW + 30, "def")
    needle(c, fake, FAKE_ROW, 3)
    c.text(fake.x(3) - 12, FAKE_ROW + 25, "advanceTimersByTimeAsync(1000)", "def", 10, mono=True, anchor="rs")
    notice_box(c, REAL_ROW, True)
    notice_box(c, FAKE_ROW, False, good=True)
    c.text(fake.x(0), FAKE_ROW + 72, "실제 걸린 시간: 몇십 ms", "string", 11)
    note(c, "1초를 더 앞당기면 안내가 사라지고, 테스트는 몇십 ms 안에 끝납니다.")


# 11c-3: 코드 셋에 두 테스트를 돌린 결과. 칸은 (결과, 맞게 가렸는지)

COLUMNS = [("맞는 코드", ""), ("콜백을 비운 코드", "(안내가 남음)"), ("setInterval로 바꾼 코드", "(3초 뒤 사라짐)")]
ROWS = [("setTimeout을 엿보는 테스트", [("통과", True), ("통과", False), ("실패", False)]),
        ("화면을 보는 테스트", [("통과", True), ("실패", True), ("통과", True)])]


@figure("11c-3", 560, 250)
def spy_vs_screen(fig):
    c = fig.frame()
    head(c, "코드 셋에 두 테스트를 돌린 결과")
    x0, col_w, y0, row_h = 160, 126, 44, 56
    for i, (title, sub) in enumerate(COLUMNS):
        x = x0 + i * (col_w + 4)
        c.text(x + col_w / 2, y0, fit(c, title, 10, col_w, bold=True), "ink", 10, bold=True, anchor="ma")
        if sub:
            c.text(x + col_w / 2, y0 + 15, sub, "comment", 10, anchor="ma")
    for r, (label, cells) in enumerate(ROWS):
        y = y0 + 38 + r * (row_h + 8)
        c.text(20, y + row_h / 2 - 7, fit(c, label.split("을 ")[0] + ("을" if "을 " in label else ""), 11, 136), "ink", 11, anchor="lm")
        c.text(20, y + row_h / 2 + 9, label.split("을 ")[1] if "을 " in label else "", "ink", 11, anchor="lm")
        for i, (result, right) in enumerate(cells):
            x = x0 + i * (col_w + 4)
            ink = "string" if result == "통과" else "missing"
            rect = c.box(x, y, col_w, row_h, fill="gutter", outline="string" if right else "missing", width=2, radius=4)
            c.text(mid_x(rect), mid_y(rect), result, ink, 13, bold=True, anchor="mm")
    note(c, "초록 테두리는 맞게 가린 칸, 빨간 테두리는 틀리게 가린 칸입니다.")


if __name__ == "__main__":
    sys.exit(main(sys.modules[__name__], OUT, owner="l11", sections=SECTIONS))
