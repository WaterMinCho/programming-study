# -*- coding: utf-8 -*-
"""응용 7차시 노트 al07 의 그림.

  ~/.cache/rokey-dev/lib/bin/python -m tools.ai_art al07 a7a-1   이름을 적은 그림만 그림

Pillow 로 직접 그린 상자·칸·막대·곡선·수직선·표이고, 겹친 판은 tools/ai_art/iso.py 로 그림. 강의 슬라이드 그림, 노트북에 저장된
그림, MNIST 사진은 쓰지 않음. 사진 칸의 무늬는 이 파일에서 그린 선 하나임.
그림에 찍는 손실 값, 미분값, 배치 수, 텐서 모양, 파라미터 수, 판정 지도 크기는 이 파일에서 다시 계산하고 assert 로 본문 숫자와 견줌.
세 수준 그림은 화면 520×280(파일 1040×560)이고 levels.grid 를 쓰거나 Pillow 로 글자 31px 이상으로 그림.
나눔고딕에 없는 글자(U+2212, 그리스 문자, 결합 문자)가 든 글은 D2Coding 으로 씀. x̂ 는 x 위에 꺾쇠를 그려 씀.

a7a 색: 파랑 = 진짜 사진·정답 1·−ln p·생성기, 주황 = 가짜 사진·정답 0·−ln(1 − p), 보라 = 판별기, 회색 = ln(1 − D).
a7b 색: 파랑 = 생성기, 보라 = 판별기, 주황 = backward 와 채워진 grad, 회색 = None·그대로, 주황 칸 = 논문 값.
a7c 색: 파랑 = 모양 상자와 eps 기본값, 주황 = eps 0.8, 격자는 값마다 파랑·주황·초록·보라.
a7d 색: 파랑 = 판별기 블록 출력, 주황 = 바꿔야 하는 256, 빨강 = sorted 가 어긋난 줄.
a7e 색: 파랑 = 인코더·평균·z, 초록 = 디코더, 주황 = ε, 회색 점선 = 생성할 때 쓰지 않는 인코더.
a7f 색: 파랑 = 복원 항·N(μ, σ²), 회색 = N(0, 1), 주황 = KL 항·빠진 100장, 보라 = 판별기 손실.
a7g 색: 파랑 = 인코더·디코더 특징 맵, 주황 = 건너뛰기 연결, 보라 = 판별기, 초록 = 진짜 y.
"""
from math import exp, floor, log, pi, sqrt

from PIL import Image, ImageDraw

from tools.ai_art import COLORS, figure, fmt, iso, levels
from tools.ai_art.al04 import arrow
from tools.ai_art.al18 import _dash, _dash_line, _face

W = 1120
INK, MUTED, FAINT = COLORS["ink"], COLORS["muted"], COLORS["faint"]
BLUE, RED, ORANGE, GREEN, PURPLE = COLORS["blue"], COLORS["red"], COLORS["orange"], COLORS["green"], COLORS["purple"]
BLUE_L, GREEN_L, ORANGE_L, RED_L, PURPLE_L = "#dbeafe", "#d1fae5", "#ffedd5", "#fee2e2", "#ede9fe"
BLUE_D, ORANGE_D, GREEN_D, PURPLE_D = "#1d4ed8", "#c2410c", "#047857", "#6d28d9"
NOTE, LINE, LIGHT, GRID = "#f3f4f6", "#e5e7eb", "#9ca3af", COLORS["grid"]
PALE = {BLUE: BLUE_L, ORANGE: ORANGE_L, GREEN: GREEN_L, RED: RED_L, PURPLE: PURPLE_L, LIGHT: NOTE, MUTED: NOTE}
LW, LH = 1040, 560  # 세 수준 그림 파일 크기
LEVEL_MIN = 31  # 세 수준 그림 글자 하한(파일 px)
_BOXES = {}


# 공통 도우미

def _mono(value):
    """나눔고딕에 없는 글자(U+2212, 그리스 문자, 결합 문자)가 있으면 True."""
    return any(c == "−" or 0x300 <= ord(c) < 0x400 for c in value)


def _pieces(value):
    """[(조각, 코드글꼴)]. 나눔고딕에 없는 글자만 D2Coding 조각으로 나눔."""
    out = []
    for ch in value:
        mono = _mono(ch)
        if out and out[-1][1] == mono:
            out[-1][0] += ch
        else:
            out.append([ch, mono])
    return out


def _w(value, size, bold=False, code=False):
    value = str(value)
    if code:
        return _face(size, bold, True).getlength(value)
    return sum(_face(size, bold, mono).getlength(part) for part, mono in _pieces(value))


def _new(h, w=W):
    image = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(image)
    _BOXES[id(d)] = []
    return image, d


def _t(d, xy, value, size=21, color=INK, bold=False, code=False, anchor="la", low=19):
    """글자 한 줄. 그림 밖으로 나가거나, 하한보다 작거나, 같은 그림의 다른 글과 겹치면 assert 로 멈춤.
    code 가 아니면 나눔고딕으로 쓰고, 나눔고딕에 없는 글자만 D2Coding 으로 같은 기준선에 씀."""
    value = str(value)
    assert size >= low, (value, size)
    if code or not _mono(value):
        face = _face(size, bold, code)
        draws = [(xy, value, face, anchor)]
        box = d.textbbox(xy, value, font=face, anchor=anchor)
    else:
        plain = _face(size, bold, False)
        ascent, descent = plain.getmetrics()
        x = xy[0] - {"l": 0, "m": _w(value, size, bold) / 2.0, "r": _w(value, size, bold)}[anchor[0]]
        base = xy[1] + {"a": ascent, "m": (ascent - descent) / 2.0, "s": 0, "b": -descent, "d": -descent}[anchor[1]]
        draws, boxes = [], []
        for part, mono in _pieces(value):
            face = _face(size, bold, mono)
            draws.append(((x, base), part, face, "ls"))
            boxes.append(d.textbbox((x, base), part, font=face, anchor="ls"))
            x += face.getlength(part)
        box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    width, height = d.im.size
    assert box[0] >= 8 and box[1] >= 6 and box[2] <= width - 8 and box[3] <= height - 6, (value, box)
    for other, text in _BOXES.get(id(d), []):
        assert box[2] <= other[0] or other[2] <= box[0] or box[3] <= other[1] or other[3] <= box[1], (value, text)
    _BOXES.setdefault(id(d), []).append((box, value))
    for at, part, face, how in draws:
        d.text(at, part, font=face, fill=color, anchor=how)
    return box


def _hat_x(d, xy, size, color=INK, bold=True):
    """가운데가 xy 인 x̂. x 를 쓰고 그 위에 꺾쇠를 그림."""
    box = _t(d, (xy[0], xy[1] + size * 0.12), "x", size, color, bold, True, anchor="mm")
    cx, top = (box[0] + box[2]) / 2.0, box[1] - size * 0.42
    half = max(5, size * 0.2)
    d.line((cx - half, top + half * 0.7, cx, top, cx + half, top + half * 0.7), fill=color, width=max(2, size // 12))
    return box


def _title(d, text, size=25):
    return _t(d, (36, 24), text, size, INK, True)


def _foot(d, y, text, size=19, color=MUTED):
    return _t(d, (36, y), text, size, color)


def _box(d, rect, lines, fill="white", outline=LIGHT, size=21, color=INK, bold=False, code=False, width=2, gap=8,
         radius=10, low=19):
    """둥근 상자 가운데에 여러 줄. lines 항목은 글이나 (글, 색, 굵게, 코드글꼴)."""
    x0, y0, x1, y1 = rect
    d.rounded_rectangle(rect, radius, fill=fill, outline=outline, width=width)
    rows = [item if isinstance(item, tuple) else (item, color, bold, code) for item in lines]
    total = len(rows) * size + (len(rows) - 1) * gap
    assert total <= y1 - y0 - 6, (lines, rect)
    y = (y0 + y1) / 2.0 - total / 2.0 + size / 2.0
    for value, ink, heavy, mono in rows:
        assert _w(value, size, heavy, mono) <= x1 - x0 - 12, (value, rect)
        _t(d, ((x0 + x1) / 2.0, y), value, size, ink, heavy, mono, anchor="mm", low=low)
        y += size + gap
    return rect


def _cell(d, rect, text="", fill="white", outline=LIGHT, size=21, color=INK, bold=False, code=True, width=2, radius=8,
          low=19):
    d.rounded_rectangle(rect, radius, fill=fill, outline=outline, width=width)
    if text != "":
        assert _w(text, size, bold, code) <= rect[2] - rect[0] - 6, (text, rect)
        _t(d, ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0), text, size, color, bold, code, anchor="mm", low=low)


def _chip(d, xy, text, color, fill, size=19, anchor="mm", code=False, bold=True, low=19):
    """둥근 이름표. 차지한 상자를 돌려줌."""
    width = _w(text, size, bold, code) + 22
    x, y = xy
    x0 = {"mm": x - width / 2.0, "lm": x}.get(anchor, x - width)
    rect = (x0, y - size / 2.0 - 8, x0 + width, y + size / 2.0 + 8)
    d.rounded_rectangle(rect, 10, fill=fill, outline=color, width=2)
    _t(d, ((rect[0] + rect[2]) / 2.0, y), text, size, color, bold, code, anchor="mm", low=low)
    return rect


def _darrow(d, start, end, color=LIGHT, width=3, dash=8):
    """점선 화살표."""
    _dash_line(d, start + end, color, width, dash)
    arrow(d, (end[0] - (end[0] - start[0]) * 0.001, end[1] - (end[1] - start[1]) * 0.001), end, color, width)


def _st(s, xy, value, size=21, color=INK, bold=False, code=False, anchor="la"):
    """iso.Sheet 위 글자 한 줄. 같은 장의 다른 글이나 이름표와 겹치면 assert."""
    box = s.text(xy, value, size, color, bold, code, anchor)
    _sheet_room(s, box, value)
    return box


def _sheet_room(s, box, value):
    boxes = s.__dict__.setdefault("taken", [])
    for other, text in boxes:
        assert box[2] <= other[0] or other[2] <= box[0] or box[3] <= other[1] or other[3] <= box[1], (value, text)
    boxes.append((box, value))


def _slabel(s, center, value, tone, state, size=19, code=False):
    rect = s.label(center, value, tone, state, size, code)
    _sheet_room(s, rect, value)
    return rect


def _dot(d, x, y, color, r=9):
    d.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="white", width=2)


def _curve(d, f, lo, hi, px, py, ybox, color, width=5, steps=240):
    """y = f(x) 를 lo~hi 에서 그음. 세로 범위 ybox=(아래 값, 위 값)를 벗어난 곳은 긋지 않음."""
    points = []
    for k in range(steps + 1):
        x = lo + (hi - lo) * k / float(steps)
        y = f(x)
        if ybox[0] <= y <= ybox[1]:
            points.append((px(x), py(y)))
        elif len(points) > 1:
            d.line(points, fill=color, width=width, joint="curve")
            points = []
        else:
            points = []
    if len(points) > 1:
        d.line(points, fill=color, width=width, joint="curve")


def _axes(box, xr, yr):
    """그래프 칸 box=(x0, y0, x1, y1) 과 값 범위로 (px, py)."""
    x0, y0, x1, y1 = box

    def px(v):
        return x0 + (v - xr[0]) * (x1 - x0) / float(xr[1] - xr[0])

    def py(v):
        return y1 - (v - yr[0]) * (y1 - y0) / float(yr[1] - yr[0])

    return px, py


def _photo(d, rect, fill="#e5e7eb", ink="white", line=LIGHT):
    """사진 칸. 이 파일에서 그린 굵은 선 하나가 든 회색 판."""
    x0, y0, x1, y1 = rect
    d.rounded_rectangle(rect, 8, fill=fill, outline=line, width=2)
    w, h = x1 - x0, y1 - y0
    d.line((x0 + w * 0.3, y0 + h * 0.25, x0 + w * 0.7, y0 + h * 0.25, x0 + w * 0.42, y0 + h * 0.8), fill=ink,
           width=max(5, int(w / 12)), joint="curve")


def _ltable(d, x, y, widths, header, rows, size=LEVEL_MIN, row_h=72, head_h=64, marks=None, code=False, low=LEVEL_MIN):
    """세 수준 그림의 표. marks 는 {(행, 열): 색}. 칸 글은 가운데. 표 오른쪽 아래 좌표."""
    marks = marks or {}
    total = sum(widths)
    d.rectangle((x, y, x + total, y + head_h), fill=NOTE)
    cx = x
    for c, name in enumerate(header):
        _t(d, (cx + widths[c] / 2.0, y + head_h / 2.0), name, size, MUTED, anchor="mm", low=low)
        cx += widths[c]
    for r, row in enumerate(rows):
        top = y + head_h + r * row_h
        d.line((x, top, x + total, top), fill=LINE, width=2)
        cx = x
        for c, value in enumerate(row):
            color = marks.get((r, c))
            if color:
                d.rectangle((cx + 4, top + 4, cx + widths[c] - 4, top + row_h - 4), fill=PALE[color], outline=color, width=3)
            assert _w(value, size, bool(color), code) <= widths[c] - 12, (value, widths[c])
            _t(d, (cx + widths[c] / 2.0, top + row_h / 2.0), value, size, color or INK, bool(color), code, anchor="mm",
               low=low)
            cx += widths[c]
    bottom = y + head_h + len(rows) * row_h
    d.rectangle((x, y, x + total, bottom), outline=LINE, width=2)
    return x + total, bottom


def _r4(value):
    return round(value, 4)


def _n(value, digits=4):
    return fmt(value, digits)


# a7a 판별기와 생성기의 손실을 정답 레이블로 나누기

def _bce(p, label):
    return -log(p) if label == 1 else -log(1 - p)


def _a7a_numbers():
    real, fake = _r4(_bce(0.8, 1)), _r4(_bce(0.3, 0))
    assert (real, fake, _r4(real + fake)) == (0.2231, 0.3567, 0.5798)
    assert _r4(1 / 0.99) == 1.0101 and round(1 / 0.01, 6) == 100
    assert _r4(-log(0.5)) == 0.6931 and _r4(-2 * log(0.5)) == 1.3863
    assert _r4((real + fake) / 2) == 0.2899 and _r4(_bce(0.3, 1)) == 1.204
    return real, fake


def _a7a1_frame(k):
    image, d = _new(600)
    _title(d, "생성기는 가짜 사진을 만들고 판별기는 확률을 냅니다")
    # 노이즈 → 생성기 → 가짜 사진
    _t(d, (70, 288), "노이즈", 21, INK, True, anchor="mm")
    _t(d, (70, 314), "숫자 100개", 19, MUTED, anchor="mm")
    for j in range(10):
        d.rounded_rectangle((52, 336 + j * 15, 88, 345 + j * 15), 3, fill="#93c5fd" if j % 3 else BLUE)
    arrow(d, (100, 400), (160, 400), INK if k == 0 else LIGHT, 4)
    _box(d, (170, 350, 320, 450), [("생성기", "white", True, False)], fill=BLUE, outline=BLUE, size=24)
    arrow(d, (330, 400), (390, 400), INK if k == 0 else LIGHT, 4)
    _photo(d, (400, 350, 500, 450))
    _t(d, (450, 470), "가짜 사진", 20, ORANGE, True, anchor="mm")
    _t(d, (450, 496), "픽셀 784개", 19, MUTED, anchor="mm")
    if k >= 1:
        _box(d, (40, 130, 150, 190), ["MNIST"], fill=NOTE, size=20)
        arrow(d, (156, 160), (196, 160), INK if k == 1 else LIGHT, 4)
        _chip(d, (260, 160), "Normalize", INK if k == 1 else MUTED, NOTE, 19, code=True)
        _t(d, (260, 200), "값 −1 ~ 1", 19, BLUE if k == 1 else MUTED, k == 1, anchor="mm")
        arrow(d, (326, 160), (390, 160), INK if k == 1 else LIGHT, 4)
        _photo(d, (400, 110, 500, 210))
        _t(d, (450, 230), "진짜 사진", 20, BLUE, True, anchor="mm")
    if k >= 2:
        arrow(d, (510, 165), (612, 252), INK, 4)
        arrow(d, (510, 395), (612, 312), INK, 4)
        _box(d, (620, 220, 780, 340), [("판별기", "white", True, False)], fill=PURPLE, outline=PURPLE, size=24)
        arrow(d, (788, 255), (838, 206), PURPLE, 4)
        arrow(d, (788, 305), (838, 354), PURPLE, 4)
        _chip(d, (880, 200), "0.8", BLUE, BLUE_L, 26, code=True)
        _chip(d, (880, 360), "0.3", ORANGE, ORANGE_L, 26, code=True)
        _t(d, (880, 248), "진짜일 확률", 19, MUTED, anchor="mm")
    if k >= 3:
        _chip(d, (1010, 200), "정답 1", BLUE, "white", 22)
        _chip(d, (1010, 360), "정답 0", ORANGE, "white", 22)
    lines = ["숫자 100개로 된 노이즈가 생성기를 지나 픽셀 784개의 가짜 사진이 됩니다.",
             "진짜 사진은 Normalize를 지나 −1과 1 사이 값이 됩니다.",
             "판별기가 진짜 사진에 0.8, 가짜 사진에 0.3을 냅니다.",
             "진짜 사진 쪽에는 정답 1, 가짜 사진 쪽에는 정답 0 이름표가 붙습니다."]
    _t(d, (36, 552), lines[k], 21, INK)
    return image


@figure("a7a-1", 560, 300)
def a7a_flow():
    """노이즈 → 생성기 → 가짜 사진, 진짜 사진 → Normalize, 두 사진 → 판별기 → 확률, 정답 이름표(4장)."""
    _a7a_numbers()
    assert 28 * 28 == 784 and (0 - 0.5) / 0.5 == -1 and (1 - 0.5) / 0.5 == 1
    return [_a7a1_frame(k) for k in range(4)], [2200, 2200, 2200, 2400]


@figure("a7a-2", 560, 280)
def a7a_bce():
    real, fake = _a7a_numbers()
    image, d = _new(560)
    _title(d, "정답이 1일 때 −ln p, 정답이 0일 때 −ln(1 − p)")
    box = (120, 110, 780, 480)
    px, py = _axes(box, (0, 1), (0, 3))
    for v in (1, 2, 3):
        d.line((box[0], py(v), box[2], py(v)), fill=GRID, width=1)
        _t(d, (box[0] - 12, py(v)), v, 19, MUTED, anchor="rm")
    d.line((box[0], box[3], box[2] + 10, box[3]), fill=LIGHT, width=2)
    d.line((box[0], box[1] - 10, box[0], box[3]), fill=LIGHT, width=2)
    _t(d, (box[0] - 12, box[3]), "0", 19, MUTED, anchor="rm")
    _t(d, (box[0] - 14, box[1] - 18), "BCE", 19, MUTED, anchor="rb")
    for v in (0.3, 0.5, 0.8, 1):
        _t(d, (px(v), box[3] + 10), _n(v, 1), 19, MUTED, anchor="ma")
    _t(d, (box[2] + 18, box[3]), "판별기 출력 p", 19, MUTED, anchor="lm")
    _curve(d, lambda p: -log(p), 0.01, 1.0, px, py, (0, 3), BLUE)
    _curve(d, lambda p: -log(1 - p), 0.0, 0.99, px, py, (0, 3), ORANGE)
    _t(d, (px(0.1) + 16, py(2.3)), "−ln p", 22, BLUE, True, anchor="lm")
    _t(d, (px(0.9) - 16, py(2.3)), "−ln(1 − p)", 22, ORANGE, True, anchor="rm")
    for p, v, color, dx, dy in ((0.8, real, BLUE, 0, -18), (0.3, fake, ORANGE, -6, -24)):  # 주황 이름표는 곡선을 피해 왼쪽 위에 씀
        _dash_line(d, (px(p), py(v), px(p), box[3]), color, 2, 6)
        _dot(d, px(p), py(v), color, 10)
        _t(d, (px(p) + dx, py(v) + dy), "(%s, %s)" % (_n(p, 1), _n(v)), 20, color, True, anchor="mb")
    _box(d, (830, 120, 1084, 220), [("판별기 손실", MUTED, False, False), ("0.2231 + 0.3567", INK, False, True),
                                    ("= 0.5798", PURPLE, True, True)], fill=PURPLE_L, outline=PURPLE, size=20, gap=6)
    assert _r4(real + fake) == 0.5798
    return image


@figure("a7a-3", 560, 280)
def a7a_slope():
    _a7a_numbers()
    image, d = _new(560)
    _title(d, "D가 0 근처이면 ln(1 − D)는 평평하고 −ln D는 가파릅니다")
    box = (120, 100, 760, 500)
    px, py = _axes(box, (0, 1), (-5, 5))
    for v in (-4, -2, 0, 2, 4):
        d.line((box[0], py(v), box[2], py(v)), fill=GRID if v else LINE, width=1 if v else 2)
        _t(d, (box[0] - 12, py(v)), fmt(v, 0), 19, MUTED, anchor="rm")
    d.line((box[0], box[3], box[2] + 10, box[3]), fill=LIGHT, width=2)
    d.line((box[0], box[1] - 10, box[0], box[3]), fill=LIGHT, width=2)
    _t(d, (box[0] - 14, box[1] - 16), "손실", 19, MUTED, anchor="rb")
    for v in (0.5, 1):
        _t(d, (px(v), box[3] + 10), _n(v, 1), 19, MUTED, anchor="ma")
    _t(d, (box[2] + 18, box[3]), "D", 20, MUTED, anchor="lm")
    _curve(d, lambda x: log(1 - x), 0.0, 0.9999, px, py, (-5, 5), LIGHT)
    _curve(d, lambda x: -log(x), 0.0001, 1.0, px, py, (-5, 5), BLUE)
    x = px(0.01)
    _dash_line(d, (x, box[1] - 6, x, box[3]), INK, 2, 6)
    _t(d, (x + 8, box[1] - 12), "D = 0.01", 19, INK, code=True, anchor="lb")
    # 접선: −ln D 는 기울기 −100, ln(1 − D) 는 기울기 −1.0101
    y_blue, y_gray = -log(0.01), log(0.99)
    d.line((px(0.01 - 0.0039), py(y_blue + 0.39), px(0.01 + 0.03), py(y_blue - 3.0)), fill=BLUE_D, width=3)
    d.line((px(0.0), py(y_gray + 0.0101), px(0.35), py(y_gray - 0.34 * 1.0101)), fill=INK, width=3)
    _dot(d, x, py(y_blue), BLUE_D, 8)
    _dot(d, x, py(y_gray), INK, 7)
    _t(d, (x + 26, py(4.35)), "미분값 크기 100", 21, BLUE_D, True, anchor="lm")
    _t(d, (px(0.12), py(-0.95)), "미분값 크기 1.0101", 21, INK, True, anchor="la")
    _t(d, (px(0.3), py(-log(0.3)) - 14), "−ln D", 22, BLUE, True, anchor="lb")
    _t(d, (px(0.82) - 12, py(log(0.18)) + 10), "ln(1 − D)", 22, MUTED, True, anchor="ra")
    _box(d, (790, 140, 1084, 300), [("D = 0.01일 때", MUTED, False, False), ("1 ÷ 0.99 = 1.0101", INK, False, True),
                                    ("1 ÷ 0.01 = 100", BLUE_D, True, True)], fill="white", outline=LIGHT, size=20, gap=10)
    assert _r4(1 / (1 - 0.01)) == 1.0101 and round(1 / 0.01) == 100
    return image


@figure("a7a-4", 560, 280)
def a7a_balance():
    _a7a_numbers()
    image, d = _new(560)
    _title(d, "p = 0.5에서 판별기 손실 합은 1.3863, 생성기 손실은 0.6931")
    box = (120, 100, 740, 470)
    px, py = _axes(box, (0, 1), (0, 5))
    for v in (1, 2, 3, 4, 5):
        d.line((box[0], py(v), box[2], py(v)), fill=GRID, width=1)
        _t(d, (box[0] - 12, py(v)), v, 19, MUTED, anchor="rm")
    d.line((box[0], box[3], box[2] + 10, box[3]), fill=LIGHT, width=2)
    d.line((box[0], box[1] - 10, box[0], box[3]), fill=LIGHT, width=2)
    _t(d, (box[0] - 12, box[3]), "0", 19, MUTED, anchor="rm")
    _t(d, (box[0] - 14, box[1] - 16), "손실", 19, MUTED, anchor="rb")
    for v in (0.5, 1):
        _t(d, (px(v), box[3] + 10), _n(v, 1), 19, MUTED, anchor="ma")
    _t(d, ((box[0] + box[2]) / 2.0, box[3] + 44), "판별기 출력 p", 19, MUTED, anchor="ma")
    total, gen = lambda p: -log(p) - log(1 - p), lambda p: -log(p)
    best = min(range(1, 1000), key=lambda k: total(k / 1000.0)) / 1000.0
    assert best == 0.5 and _r4(total(0.5)) == 1.3863 and _r4(gen(0.5)) == 0.6931
    _curve(d, total, 0.001, 0.999, px, py, (0, 5), PURPLE)
    _curve(d, gen, 0.001, 1.0, px, py, (0, 5), BLUE)
    _dash_line(d, (px(0.5), box[1], px(0.5), box[3]), INK, 2, 6)
    _dot(d, px(0.5), py(total(0.5)), PURPLE, 10)
    _dot(d, px(0.5), py(gen(0.5)), BLUE, 10)
    _t(d, (px(0.5) + 16, py(total(0.5)) - 16), "1.3863", 21, PURPLE, True, anchor="lb")
    _t(d, (px(0.5) - 14, py(gen(0.5)) + 10), "0.6931", 21, BLUE, True, anchor="ra")
    for k, (color, name, formula) in enumerate(((PURPLE, "판별기 손실 합", "−ln p − ln(1 − p)"),
                                                (BLUE, "생성기 손실", "−ln p"))):
        y = 170 + k * 120
        d.line((780, y, 830, y), fill=color, width=5)
        _t(d, (846, y), name, 21, color, True, anchor="lm")
        _t(d, (846, y + 34), formula, 20, INK, anchor="lm")
    return image


# a7b detach와 옵티마이저 둘로 한쪽 신경망만 갱신하기

def _a7b_row(d, y, boxes, active):
    """한 줄의 상자 [(이름, 폭, 색, 코드글꼴)]. 상자 rect 목록."""
    x, rects = 40, []
    for n, (name, width, color, mono) in enumerate(boxes):
        rect = (x, y - 30, x + width, y + 30)
        if color in (BLUE, PURPLE):
            _box(d, rect, [(name, "white", True, mono)], fill=color, outline=color, size=20)
        else:
            _box(d, rect, [(name, INK, False, mono)], fill=NOTE, outline=LIGHT, size=20)
        rects.append(rect)
        if n + 1 < len(boxes):
            arrow(d, (x + width + 6, y), (x + width + 40, y), INK if active else LIGHT, 3)
        x += width + 46
    return rects


def _grad(d, rect, filled, y):
    cx = (rect[0] + rect[2]) / 2.0
    if filled:
        _chip(d, (cx, y), "grad 채움", ORANGE, ORANGE_L, 19, code=False)
    else:
        _chip(d, (cx, y), "grad None", MUTED, NOTE, 19, code=True)


def _backward(d, start_x, end_x, y_row, y_line, label):
    d.line((start_x, y_row - 32, start_x, y_line, end_x, y_line), fill=ORANGE, width=4)
    arrow(d, (end_x, y_line), (end_x, y_row - 34), ORANGE, 4)
    _t(d, ((start_x + end_x) / 2.0, y_line - 6), label, 19, ORANGE, True, code=True, anchor="mb")


def _a7b1_frame(k):
    image, d = _new(560)
    _title(d, "detach()가 있으면 기울기는 판별기 층에서 멈춥니다")
    top = [("노이즈", 100, None, False), ("생성기 층", 140, BLUE, False), ("fake_images", 160, None, True),
           ("detach()", 130, None, True), ("판별기 층", 140, PURPLE, False), ("loss_D", 120, None, True)]
    _chip(d, (40, 92), "detach() 있음", INK, NOTE, 19, anchor="lm", code=True)
    rects = _a7b_row(d, 190, top, k == 0)
    _grad(d, rects[1], False, 252)
    _grad(d, rects[4], k >= 1, 252)
    if k >= 1:
        _backward(d, (rects[5][0] + rects[5][2]) / 2.0, (rects[4][0] + rects[4][2]) / 2.0, 190, 132, "loss_D.backward()")
    if k >= 2:
        bottom = [("노이즈", 100, None, False), ("생성기 층", 140, BLUE, False), ("fake_images", 160, None, True),
                  ("판별기 층", 140, PURPLE, False), ("loss_D", 120, None, True)]
        _chip(d, (40, 312), "detach() 없음", RED, RED_L, 19, anchor="lm", code=True)
        rows = _a7b_row(d, 410, bottom, False)
        _grad(d, rows[1], True, 472)
        _grad(d, rows[3], True, 472)
        _backward(d, (rows[4][0] + rows[4][2]) / 2.0, (rows[1][0] + rows[1][2]) / 2.0, 410, 352, "loss_D.backward()")
    lines = ["노이즈가 생성기를 지나 fake_images가 되고, fake_images.detach()가 판별기로 들어갑니다.",
             "backward()의 화살표는 판별기 층까지 가고, 생성기 층의 grad는 None입니다.",
             "detach()를 빼면 화살표가 생성기 층까지 가고 생성기 grad도 채워집니다."]
    _t(d, (36, 528), lines[k], 20, INK)
    return image


@figure("a7b-1", 560, 280)
def a7b_detach():
    """detach() 가 있는 줄과 없는 줄의 backward 길과 grad 이름표(3장)."""
    return [_a7b1_frame(k) for k in range(3)], [2200, 2400, 2400]


@figure("a7b-2", 560, 180)
def a7b_grads():
    image, d = _new(360)
    _title(d, "생성기 단계 뒤 grad는 둘 다 채워지고 가중치는 생성기만 바뀝니다")
    x, widths = 40, [560, 240, 240]
    d.rectangle((x, 84, x + sum(widths), 136), fill=NOTE)
    for c, name in enumerate(("시점", "생성기", "판별기")):
        _t(d, (x + sum(widths[:c]) + (24 if c == 0 else widths[c] / 2.0), 110), name, 20, MUTED, True,
           anchor="lm" if c == 0 else "mm")
    rows = [("loss_G.backward() 뒤", ("grad 채움", ORANGE), ("grad 채움", ORANGE)),
            ("optimizer_G.step() 뒤", ("가중치 바뀜", BLUE), ("가중치 그대로", MUTED)),
            ("다음 배치 optimizer_D.zero_grad() 뒤", ("손대지 않음", MUTED), ("grad None", PURPLE))]
    for r, (when, gen, disc) in enumerate(rows):
        y = 136 + r * 66
        d.line((x, y, x + sum(widths), y), fill=LINE, width=2)
        _t(d, (x + 24, y + 33), when, 20, INK, code=True, anchor="lm")
        for c, (text, color) in enumerate((gen, disc)):
            _chip(d, (x + widths[0] + widths[1] * c + widths[1 + c] / 2.0, y + 33), text, color, PALE[color], 19,
                  code=text == "grad None")
    d.rectangle((x, 84, x + sum(widths), 334), outline=LINE, width=2)
    return image


@figure("a7b-3", 560, 170)
def a7b_betas():
    rows = [("Adam 기본값", 0.001, 0.9, 0.999), ("DCGAN 논문", 0.0002, 0.5, 0.999), ("넷째 단원 학습 코드", 0.001, 0.9, 0.999)]
    assert rows[1][1] < rows[0][1] and rows[1][2] < rows[0][2] and rows[2][1:] == rows[0][1:]
    image, d = _new(340)
    _title(d, "DCGAN 논문은 lr와 β1을 낮췄습니다")
    x, widths = 40, [360, 220, 220, 220]
    d.rectangle((x, 84, x + sum(widths), 134), fill=NOTE)
    for c, name in enumerate(("설정", "lr", "β1", "β2")):
        _t(d, (x + sum(widths[:c]) + (24 if c == 0 else widths[c] / 2.0), 109), name, 20, MUTED, True,
           anchor="lm" if c == 0 else "mm")
    for r, row in enumerate(rows):
        y = 134 + r * 64
        d.line((x, y, x + sum(widths), y), fill=LINE, width=2)
        _t(d, (x + 24, y + 32), row[0], 20, INK, r == 1, anchor="lm")
        for c, value in enumerate(row[1:]):
            cx = x + sum(widths[:c + 1]) + widths[c + 1] / 2.0
            text = ("%.4f" % value).rstrip("0")
            if r == 1 and c < 2:
                _chip(d, (cx, y + 32), text, ORANGE, ORANGE_L, 21, code=True)
            else:
                _t(d, (cx, y + 32), text, 21, INK, code=True, anchor="mm")
    d.rectangle((x, 84, x + sum(widths), 326), outline=LINE, width=2)
    return image


@figure("a7b-4", 560, 230)
def a7b_batches():
    total, size = 60000, 128
    count, last = -(-total // size), total - size * (total // size)
    assert (count, total // size, last) == (469, 468, 96)
    image, d = _new(460)
    _title(d, "60,000장을 128장씩 나누면 마지막 배치는 96장")
    _t(d, (60, 78), "배치 469개", 20, INK, True)
    base, full = 330, 190
    for n, x in enumerate((60, 150, 240)):
        d.rectangle((x, base - full, x + 66, base), fill=BLUE)
        _t(d, (x + 33, base - full - 8), "128", 20, BLUE, True, code=True, anchor="mb")
    for k in range(3):
        d.ellipse((337 + k * 18, base - 40, 345 + k * 18, base - 32), fill=MUTED)
    h = full * last / float(size)
    d.rectangle((420, base - h, 486, base), fill=ORANGE)
    _t(d, (453, base - h - 8), "96", 20, ORANGE, True, code=True, anchor="mb")
    d.line((40, base, 510, base), fill=LIGHT, width=2)
    d.line((60, base + 14, 60, base + 22, 306, base + 22, 306, base + 14), fill=MUTED, width=2)
    _t(d, (183, base + 30), "앞 468개", 19, MUTED, anchor="ma")
    _t(d, (453, base + 30), "마지막 1개", 19, ORANGE, anchor="ma")
    _t(d, (60, 412), "60,000 − 128 × 468 = 96", 24, INK, True)
    _box(d, (640, 150, 1080, 320), [("마지막 배치의 real_labels", MUTED, False, False), ("(96, 1)", ORANGE, True, True),
                                    ("current_batch_size = 96", INK, False, True)], fill="white", outline=LIGHT, size=22,
         gap=14)
    return image


# a7c DCGAN 생성기에서 16×16을 64×64로 키우기

def _conv_out(n, k, s=1, p=0):
    return floor((n + 2 * p - k) / s) + 1


def _tconv_out(n, k, s=1, p=0):
    return (n - 1) * s - 2 * p + k


def _gen_shapes():
    """DCGAN 생성기를 지나는 모양 목록(배치 2)."""
    inp = 64 // 4
    shapes = [(2, 64), (2, 128 * inp * inp), (2, 128, inp, inp)]
    side = inp
    side *= 2
    shapes.append((2, 128, _conv_out(side, 3, 1, 1), _conv_out(side, 3, 1, 1)))  # up1·cn1
    side *= 2
    shapes.append((2, 128, side, side))  # up2
    shapes.append((2, 64, _conv_out(side, 3, 1, 1), _conv_out(side, 3, 1, 1)))  # cn2
    shapes.append((2, 1, side, side))  # cn3·Tanh
    assert shapes[1] == (2, 32768) and 64 * 32768 + 32768 == 2129920
    return shapes


def _shape_text(shape):
    return "(" + ", ".join(str(v) for v in shape) + ")"


def _a7c1_frame(k, shapes):
    image, d = _new(520)
    _title(d, "노이즈 배치 (2, 64)가 생성기를 지나며 바뀌는 모양")
    widths = [120, 160, 196, 196, 196, 186, 176]
    labels = ["lin", "view", "up1·cn1", "up2", "cn2", "cn3·Tanh"]
    shown = [1, 2, 5, 6][k]
    new = {0: (0, 1), 1: (2,), 2: (3, 4, 5), 3: (6,)}[k]
    xs = [60, 60 + 120 + 110, 60 + 120 + 110 + 160 + 110, 60 + 120 + 110 + 160 + 110 + 196 + 110]
    xs += [60, 60 + 196 + 130, 60 + 196 + 130 + 186 + 130]
    ys = [150] * 4 + [360] * 3
    rects = []
    for n, shape in enumerate(shapes):
        rect = (xs[n], ys[n] - 34, xs[n] + widths[n], ys[n] + 34)
        rects.append(rect)
        if n > shown:
            _dash(d, rect, LIGHT, 2, 7)
            continue
        strong = n in new and n > 0
        if n == 6 and k == 3:
            _cell(d, rect, _shape_text(shape), BLUE, BLUE, 20, "white", True)
        else:
            _cell(d, rect, _shape_text(shape), BLUE_L if strong else "white", BLUE if strong else LIGHT, 20,
                  BLUE_D if strong else INK, strong, width=3 if strong else 2)
    for n, name in enumerate(labels):
        on = n + 1 <= shown
        color = BLUE if on and (n + 1) in new else (INK if on else LIGHT)
        a, b = rects[n], rects[n + 1]
        if n == 3:
            # 윗줄 끝 상자에서 아랫줄 첫 상자로 꺾어 내려감
            mx, my = (a[0] + a[2]) / 2.0, 255
            d.line((mx, a[3] + 4, mx, my, (b[0] + b[2]) / 2.0, my), fill=color, width=4)
            arrow(d, ((b[0] + b[2]) / 2.0, my), ((b[0] + b[2]) / 2.0, b[1] - 6), color, 4)
            _t(d, ((mx + (b[0] + b[2]) / 2.0) / 2.0, my - 8), name, 20, color, True, code=True, anchor="mb")
        else:
            arrow(d, (a[2] + 8, ys[n]), (b[0] - 8, ys[n]), color, 4)
            _t(d, ((a[2] + b[0]) / 2.0, ys[n] - 12), name, 20, color, True, code=True, anchor="mb")
    lines = ["Linear 층이 노이즈 (2, 64)를 (2, 32768)로 바꿉니다.",
             "view가 (2, 32768)을 채널 128개, 가로세로 16인 (2, 128, 16, 16)으로 바꿉니다.",
             "Upsample과 합성곱을 두 번 지나 가로세로가 16에서 32, 64로 커집니다.",
             "마지막 합성곱이 채널을 64개에서 1개로 줄이고 Tanh가 값을 −1과 1 사이로 만듭니다."]
    _t(d, (36, 476), lines[k], 20, INK)
    return image


@figure("a7c-1", 560, 260)
def a7c_shapes():
    shapes = _gen_shapes()
    assert [_shape_text(s) for s in shapes] == ["(2, 64)", "(2, 32768)", "(2, 128, 16, 16)", "(2, 128, 32, 32)",
                                               "(2, 128, 64, 64)", "(2, 64, 64, 64)", "(2, 1, 64, 64)"]
    return [_a7c1_frame(k, shapes) for k in range(4)], [2200, 2200, 2400, 2400]


GRID_COLORS = {1: (BLUE, BLUE_L), 2: (ORANGE, ORANGE_L), 3: (GREEN, GREEN_L), 4: (PURPLE, PURPLE_L)}


def _upsample(rows):
    """nearest 방식 두 배. 출력 (i, j) 칸 = 입력 (i // 2, j // 2) 칸."""
    n = len(rows)
    return [[rows[i // 2][j // 2] for j in range(2 * n)] for i in range(2 * n)]


def _num_grid(d, x, y, rows, cell, size, low=19, gap=8):
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            color, fill = GRID_COLORS[value]
            _cell(d, (x + c * cell, y + r * cell, x + (c + 1) * cell - gap, y + (r + 1) * cell - gap), str(value), fill,
                  color, size, color, True, width=3, low=low)


@figure("a7c-2", 560, 230)
def a7c_nearest():
    small = [[1, 2], [3, 4]]
    big = _upsample(small)
    assert big[0] == [1, 1, 2, 2] and big[3] == [3, 3, 4, 4]
    image, d = _new(460)
    _title(d, "nearest 방식으로 2×2 격자를 4×4로 키우기")
    _num_grid(d, 150, 170, small, 84, 30)
    _t(d, (234, 360), "가로세로 2", 19, MUTED, anchor="mm")
    arrow(d, (370, 250), (640, 250), BLUE, 5)
    _t(d, (505, 236), "nn.Upsample(scale_factor=2)", 19, BLUE, True, code=True, anchor="mb")
    _t(d, (505, 268), "mode='nearest'", 19, MUTED, code=True, anchor="ma")
    _num_grid(d, 690, 100, big, 72, 26)
    _t(d, (830, 400), "가로세로 4", 19, MUTED, anchor="mm")
    return image


@figure("a7c-3", 560, 280)
def a7c_eps():
    low, high = 0.2 / sqrt(0.04 + 0.00001), 0.2 / sqrt(0.04 + 0.8)
    assert _r4(low) == 0.9999 and _r4(high) == 0.2182
    image, d = _new(560)
    _title(d, "BatchNorm2d(128, 0.8)의 0.8은 eps 자리입니다")
    parts = [("BatchNorm2d(128, ", INK), ("0.8", ORANGE), (")", INK)]
    total = sum(_w(p, 28, True, True) for p, _ in parts)
    x = 560 - total / 2.0
    eps_x = None
    for text, color in parts:
        _t(d, (x, 104), text, 28, color, True, True, anchor="lm")
        if color == ORANGE:
            eps_x = x + _w(text, 28, True, True) / 2.0
        x += _w(text, 28, True, True)
    chips = [("num_features = 128", MUTED, NOTE, 290), ("eps = 0.8", ORANGE, ORANGE_L, 560), ("momentum = 0.1", MUTED, NOTE, 830)]
    for text, color, fill, cx in chips:
        _chip(d, (cx, 186), text, color, fill, 20, code=True)
    arrow(d, (eps_x, 124), (560, 168), ORANGE, 3)
    base, top = 468, 250
    for k, (value, name, color) in enumerate(((low, "eps 0.00001", BLUE), (high, "eps 0.8", ORANGE))):
        x0 = 380 + k * 260
        h = (base - top) * value
        d.rectangle((x0, base - h, x0 + 100, base), fill=color)
        _t(d, (x0 + 50, base - h - 8), _n(value), 22, color, True, code=True, anchor="mb")
        _t(d, (x0 + 50, base + 10), name, 19, INK, code=True, anchor="ma")
    d.line((300, base, 820, base), fill=LIGHT, width=2)
    _foot(d, 520, "분산 0.04인 채널에서 평균보다 0.2 큰 값을 정규화한 결과입니다.")
    return image


@figure("a7c-4", 560, 230)
def a7c_tconv():
    assert _tconv_out(4, 4, 2, 1) == 8 and _tconv_out(8, 4, 2, 1) == 16 and _tconv_out(1, 4, 1, 0) == 4
    image, d = _new(460)
    _title(d, "ConvTranspose2d(512, 256, 4, 2, 1)은 4를 8로 키웁니다")
    rows = [(150, 4, 8, "ConvTranspose2d(512, 256, 4, 2, 1)", "(4 − 1) × 2 − 2 × 1 + 4 = 8"),
            (330, 1, 4, "ConvTranspose2d(100, 512, 4, 1, 0)", "(1 − 1) × 1 − 2 × 0 + 4 = 4")]
    cell = 44
    for y, n_in, n_out, code, formula in rows:
        for c in range(n_in):
            d.rectangle((70 + c * cell, y - 22, 70 + (c + 1) * cell - 6, y + 22), fill=BLUE, outline=BLUE)
        _t(d, (70, y + 34), "가로세로 %d" % n_in, 19, MUTED)
        arrow(d, (300, y), (690, y), BLUE, 4)
        _t(d, (495, y - 14), code, 20, INK, True, True, anchor="mb")
        _t(d, (495, y + 14), formula, 20, BLUE_D, True, anchor="ma")
        for c in range(n_out):
            d.rectangle((720 + c * cell, y - 22, 720 + (c + 1) * cell - 6, y + 22), fill=BLUE_L, outline=BLUE, width=2)
        _t(d, (720, y + 34), "가로세로 %d" % n_out, 19, MUTED)
    return image


# a7d DCGAN 판별기에서 64를 4로 줄이고 2,048로 펴기

def _disc_sides(size, blocks):
    sides = [size]
    for _ in range(blocks):
        sides.append(_conv_out(sides[-1], 3, 2, 1))
    return sides


def _a7d1_frame(k, sides, chans):
    s = iso.Sheet(W, 520)
    _st(s, (36, 24), "판별기 블록 넷이 64를 4로 줄입니다", 25, INK, True)
    fronts = [12 * sqrt(v) + 20 for v in sides]
    depths = [max(6.0, 3.0 * sqrt(c)) for c in chans]
    spans = [w + dd * iso.DEPTH[0] for w, dd in zip(fronts, depths)]
    gap = 128
    x, base, xs = 70, 340, []
    for span in spans:
        xs.append(x)
        x += span + gap
    assert x - gap <= W - 60, x
    shown = [1, 2, 4, 4][k]
    new = {0: (1,), 1: (2,), 2: (3, 4), 3: ()}[k]
    for n, (side, ch) in enumerate(zip(sides, chans)):
        w, depth = fronts[n], depths[n]
        state = "normal" if n == 0 else ("todo" if n > shown else ("strong" if n in new else "seen"))
        a = s.box(xs[n], base - w, w, w, depth, state)
        cx = xs[n] + w / 2.0
        _st(s, (cx, base + 26), "%d × %d" % (side, side), 22, BLUE if n in new else INK, True, True, anchor="mm")
        _st(s, (cx + depth * iso.DEPTH[0] / 2.0, a["above"][1] - 12), "채널 %d" % ch, 20, BLUE if n in new else MUTED,
            n in new, anchor="mb")
        if n:
            left, right = xs[n - 1] + spans[n - 1] + 8, xs[n] - 8
            on = n <= shown
            s.arrow((left, base - 20), (right, base - 20), BLUE if n in new else (INK if on else iso.GRAY),
                    width=iso.ARROW_W, size=(12, 6))
            _st(s, ((left + right) / 2.0, base - 60), "stride 2", 19, MUTED, anchor="mm")
            _st(s, ((left + right) / 2.0, base - 36), "합성곱", 19, MUTED, anchor="mm")
    first = (xs[0] + spans[0] + 8 + xs[1] - 8) / 2.0
    _slabel(s, (first, base + 76), "배치 정규화 없음", "orange", "new" if k == 0 else "seen", 19)
    if k == 3:
        _slabel(s, (xs[4] + spans[4] / 2.0, base + 76), "(2, 128, 4, 4)", "blue", "new", 21, code=True)
    lines = ["첫 블록의 stride 2 합성곱이 64를 32로 줄이고 채널을 16개로 만듭니다. 배치 정규화는 없습니다.",
             "둘째 블록이 32를 16으로 줄이고 채널을 32개로 만듭니다.",
             "셋째 블록이 16을 8로, 넷째 블록이 8을 4로 줄이고 채널은 64개, 128개가 됩니다.",
             "disc_model의 출력은 (2, 128, 4, 4)입니다."]
    _st(s, (36, 480), lines[k], 20, INK, anchor="lm")
    return s.image()


@figure("a7d-1", 560, 260)
def a7d_blocks():
    sides, chans = _disc_sides(64, 4), [1, 16, 32, 64, 128]
    assert sides == [64, 32, 16, 8, 4] and _conv_out(64, 3, 2, 1) == 32
    return [_a7d1_frame(k, sides, chans) for k in range(4)], [2200, 2000, 2200, 2000]


@figure("a7d-2", 560, 220)
def a7d_flatten():
    sides = _disc_sides(64, 4)
    ds_size = 64 // 2 ** 4
    assert ds_size == sides[-1] == 4 and 128 * ds_size ** 2 == 2048
    s = iso.Sheet(W, 440)
    s.text((36, 24), "128 × 4 × 4를 길이 2,048인 한 줄로 폅니다", 25, INK, True)
    s.stack(60, 180, 120, 120, 6, rows=4, cols=4, thick=5, default="seen", states={0: "new"})
    s.text((150, 344), "채널 128개", 20, INK, True, anchor="mm")
    s.text((150, 372), "가로세로 4", 19, MUTED, anchor="mm")
    s.arrow((280, 240), (340, 240), BLUE, width=3, size=(14, 7))
    s.text((310, 214), "펴기", 19, BLUE, True, anchor="mb")
    x0, x1 = 360, 640
    for k in range(10):
        if k in (4, 5):
            continue
        a = x0 + k * (x1 - x0) / 10.0
        s.poly([(a, 222), (a + (x1 - x0) / 10.0 - 4, 222), (a + (x1 - x0) / 10.0 - 4, 258), (a, 258)],
               fill="#93c5fd" if k % 2 else "#bfdbfe", line=BLUE, width=1.5)
    s.text(((x0 + x1) / 2.0, 240), "…", 22, BLUE, True, anchor="mm")
    s.text(((x0 + x1) / 2.0, 200), "길이 2,048", 21, BLUE, True, anchor="mb")
    s.text(((x0 + x1) / 2.0, 284), "128 × 4 × 4 = 2,048", 21, INK, True, code=True, anchor="ma")
    s.arrow((656, 240), (700, 240), INK, width=3, size=(12, 6))
    s.card((800, 240), ["Linear(2048, 1)"], "blue", "seen", size=21, code=True, width=210)
    s.arrow((900, 240), (936, 240), INK, width=3, size=(12, 6))
    s.card((1010, 240), ["Sigmoid"], "purple", "seen", size=21, code=True, width=140)
    s.text((36, 410), "x.view(x.shape[0], -1)이 (2, 128, 4, 4)를 (2, 2048)로 바꾸고, Linear와 Sigmoid를 지나 (2, 1)이 됩니다.",
           19, MUTED, anchor="lm")
    return s.image()


@figure("a7d-3", 560, 280)
def a7d_blocks5():
    sides = _disc_sides(128, 5)
    ds_size = 128 // 2 ** 5
    assert sides == [128, 64, 32, 16, 8, 4] and ds_size == 4
    assert 128 * ds_size ** 2 == 2048 and 256 * ds_size ** 2 == 4096
    image, d = _new(560)
    _title(d, "다섯째 블록의 채널이 256이면 Linear 입력은 4,096")
    base, x = 220, 90
    centers = []
    for n, side in enumerate(sides):
        w = 10 * sqrt(side)
        d.rectangle((x, base - w, x + w, base), fill=BLUE if n == 5 else BLUE_L, outline=BLUE, width=2)
        _t(d, (x + w / 2.0, base + 12), side, 21, BLUE if n == 5 else INK, n == 5, True, anchor="ma")
        centers.append(x + w / 2.0)
        if n < 5:
            arrow(d, (x + w + 14, base - 20), (x + w + 66, base - 20), LIGHT, 3)
        x += w + 80
    last = centers[-1]
    d.line((last, base + 44, last, 290), fill=MUTED, width=2)
    d.line((290, 290, 830, 290), fill=MUTED, width=2)
    arrow(d, (290, 290), (290, 318), MUTED, 2)
    arrow(d, (830, 290), (830, 318), MUTED, 2)
    cards = [(60, 520, "disc_module(128, 128)", "128 × 4 × 4 = 2,048", [("nn.Linear(", INK), ("128", INK),
                                                                         (" * ds_size ** 2, 1)", INK)], False),
             (580, 1080, "disc_module(128, 256)", "256 × 4 × 4 = 4,096", [("nn.Linear(", INK), ("256", ORANGE),
                                                                           (" * ds_size ** 2, 1)", INK)], True)]
    for x0, x1, block, formula, parts, changed in cards:
        d.rounded_rectangle((x0, 326, x1, 530), 12, fill=BLUE_L if changed else NOTE, outline=BLUE if changed else LIGHT,
                            width=2)
        cx = (x0 + x1) / 2.0
        _t(d, (cx, 356), block, 20, INK, True, True, anchor="mm")
        _t(d, (cx, 400), formula, 22, BLUE_D if changed else INK, True, True, anchor="mm")
        total = sum(_w(p, 20, False, True) for p, _ in parts)
        px = cx - total / 2.0
        for text, color in parts:
            _t(d, (px, 450), text, 20, color, color == ORANGE, True, anchor="lm")
            px += _w(text, 20, False, True)
        if changed:
            _chip(d, (cx, 498), "128을 256으로 바꿈", ORANGE, ORANGE_L, 19)
    return image


@figure("a7d-4", 560, 210)
def a7d_sort():
    names = ["0.png", "200.png", "1000.png"]
    plain = sorted(names)
    natural = sorted(names, key=lambda n: int(n.split(".")[0]))
    assert plain == ["0.png", "1000.png", "200.png"] and natural == names
    image, d = _new(420)
    _title(d, "sorted와 natsort.natsorted의 정렬 결과")
    for c, (name, rows) in enumerate((("sorted", plain), ("natsort.natsorted", natural))):
        x = 100 + c * 500
        _t(d, (x, 104), name, 22, BLUE if c else INK, True, True, anchor="lm")
        for r, value in enumerate(rows):
            bad = c == 0 and r == 1
            rect = (x, 140 + r * 80, x + 400, 200 + r * 80)
            _cell(d, rect, "'%s'" % value, RED_L if bad else "white", RED if bad else LIGHT, 22, RED if bad else INK, bad,
                  width=3 if bad else 2)
    return image


# a7e VAE 인코더가 평균과 로그 분산을 내고 z 뽑기

def _trapezoid(d, x0, x1, y_mid, wide, narrow, fill, shrink=True):
    """왼쪽 높이 wide, 오른쪽 높이 narrow 인 사다리꼴(shrink=False 면 반대)."""
    a, b = (wide, narrow) if shrink else (narrow, wide)
    d.polygon([(x0, y_mid - a / 2.0), (x1, y_mid - b / 2.0), (x1, y_mid + b / 2.0), (x0, y_mid + a / 2.0)], fill=fill)


def _vector(d, x0, x1, y, color, fill, n=8):
    for k in range(n):
        a = x0 + k * (x1 - x0) / float(n)
        d.rectangle((a, y - 14, a + (x1 - x0) / float(n) - 3, y + 14), fill=fill, outline=color, width=1)


def _a7e1_frame(k):
    image, d = _new(560)
    _title(d, "인코더가 낸 평균과 로그 분산으로 z를 뽑습니다")
    y = 290
    _photo(d, (30, y - 45, 120, y + 45))
    _t(d, (75, y + 66), "사진 784칸", 19, MUTED, anchor="mm")
    arrow(d, (126, y), (150, y), BLUE if k == 0 else LIGHT, 4)
    _trapezoid(d, 156, 286, y, 200, 110, BLUE if k <= 1 else "#93c5fd")
    _t(d, (221, y - 12), "인코더", 22, "white", True, anchor="mm")
    _t(d, (221, y + 18), "400 · 400", 19, "white", True, True, anchor="mm")
    if k >= 1:
        hot = k == 1
        arrow(d, (290, y - 30), (326, 190), BLUE if hot else LIGHT, 3)
        arrow(d, (290, y + 30), (326, 390), BLUE if hot else LIGHT, 3)
        _vector(d, 330, 500, 190, BLUE, BLUE_L)
        _t(d, (330, 160), "평균 μ 200개", 20, BLUE_D, True, anchor="lb")
        _vector(d, 330, 500, 390, PURPLE, PURPLE_L)
        _t(d, (330, 360), "로그 분산 log σ² 200개", 20, PURPLE_D, True, anchor="lb")
    if k >= 2:
        hot = k == 2
        arrow(d, (506, 390), (544, 390), INK if hot else LIGHT, 3)
        _box(d, (550, 366, 676, 414), [("표준편차 σ", INK, True, False)], fill="white", outline=PURPLE, size=19)
        _box(d, (583, 456, 643, 500), [("ε", ORANGE, True, True)], fill=ORANGE_L, outline=ORANGE, size=22)
        arrow(d, (613, 452), (613, 420), ORANGE, 3)
        d.line((676, 390, 712, 390, 712, 316), fill=INK if hot else LIGHT, width=3)
        d.line((506, 190, 712, 190, 712, 264), fill=INK if hot else LIGHT, width=3)
        arrow(d, (712, 290), (736, 290), INK if hot else LIGHT, 3)
        d.line((712, 264, 712, 316), fill=INK if hot else LIGHT, width=3)
        _box(d, (742, 262, 846, 318), [("z 200개", "white", True, False)], fill=BLUE, outline=BLUE, size=20)
        _t(d, (794, 342), "z = μ + σ × ε", 19, BLUE_D, True, anchor="ma")
    if k >= 3:
        arrow(d, (850, y), (872, y), GREEN, 4)
        _trapezoid(d, 876, 1000, y, 200, 110, GREEN, shrink=False)
        _t(d, (938, y), "디코더", 22, "white", True, anchor="mm")
        arrow(d, (1004, y), (1024, y), GREEN, 4)
        _photo(d, (1028, y - 40, 1100, y + 40))
        _t(d, (1064, y + 62), "784칸", 19, MUTED, anchor="mm")
    lines = ["784개 픽셀인 사진 한 장이 인코더로 들어갑니다.",
             "인코더는 은닉층 두 개를 지나 평균 μ 200개와 로그 분산 log σ² 200개를 냅니다.",
             "로그 분산을 표준편차 σ로 바꾸고, 무작위로 뽑은 ε와 함께 z 200개를 만듭니다.",
             "디코더가 z 200개를 받아 784개 픽셀인 사진을 다시 만듭니다."]
    _t(d, (36, 532), lines[k], 20, INK, anchor="lm")
    return image


@figure("a7e-1", 560, 280)
def a7e_flow():
    assert 784 * 400 + 400 + 400 * 400 + 400 + 2 * (400 * 200 + 200) == 634800
    return [_a7e1_frame(k) for k in range(4)], [2000, 2200, 2200, 2000]


def _std(log_var):
    return exp(0.5 * log_var)


@figure("a7e-2", 560, 280)
def a7e_std():
    points = [(-2, _std(-2)), (0, _std(0)), (log(4), _std(log(4)))]
    assert [round(points[0][1], 3), points[1][1], round(points[2][1], 4)] == [0.368, 1.0, 2.0]
    assert _r4(log(4)) == 1.3863
    image, d = _new(560)
    _title(d, "로그 분산 −2, 0, ln 4의 표준편차는 0.368, 1, 2")
    box = (100, 110, 900, 470)
    px, py = _axes(box, (-3.5, 2.3), (0, 3))
    d.line((box[0], py(0), box[2] + 10, py(0)), fill=LIGHT, width=2)
    d.line((px(0), box[1] - 10, px(0), py(0)), fill=LIGHT, width=2)
    for v in (1, 2, 3):
        d.line((box[0], py(v), box[2], py(v)), fill=GRID, width=1)
        _t(d, (box[0] - 12, py(v)), v, 19, MUTED, anchor="rm")
    _t(d, (px(0), py(0) + 12), "0", 20, MUTED, anchor="ma")
    _t(d, (px(0) + 12, box[1] - 14), "표준편차 σ", 20, MUTED, anchor="lb")
    _t(d, (box[2] + 4, py(0) + 46), "로그 분산 log σ²", 20, MUTED, anchor="ra")
    _curve(d, _std, -3.5, 2.3, px, py, (0, 3), BLUE)
    _t(d, (px(1.9), py(_std(1.9)) - 8), "exp(0.5 × log σ²)", 20, BLUE, True, anchor="rb")
    for (x, v), text, tick in zip(points, ("0.368", "1", "2"), ("−2", None, "ln 4")):
        _dash_line(d, (px(x), py(v), px(x), py(0)), LIGHT, 2, 6)
        if x != 0:
            _dash_line(d, (px(x), py(v), px(0), py(v)), LIGHT, 2, 6)
        _dot(d, px(x), py(v), BLUE_D, 10)
        lift = 20 if x < 0 else 14  # 0.368 은 오른쪽 위로 오르는 곡선을 피해 6px 더 위에 씀
        _t(d, (px(x) - 14 if x > 0 else px(x) + 12, py(v) - lift), text, 22, BLUE_D, True, code=True,
           anchor="rb" if x > 0 else "lb")
        if tick:
            _t(d, (px(x), py(0) + 12), tick, 20, INK, code=True, anchor="ma")
    _foot(d, 520, "로그 분산이 음수여도 표준편차는 0보다 큽니다.", 20)
    return image


@figure("a7e-3", 560, 230)
def a7e_points():
    mu, sigma = 1, 2
    eps = [-1.5, -0.5, 0, 0.5, 1.5]
    zs = [mu + sigma * e for e in eps]
    assert zs == [-2, 0, 1, 2, 4]
    image, d = _new(460)
    _title(d, "μ = 1, σ = 2에서 ε 다섯 개로 뽑은 z")
    _chip(d, (1060, 38), "z = μ + σ × ε", INK, NOTE, 20, anchor="rm", code=True)
    px, _ = _axes((150, 0, 1030, 0), (-3, 5), (0, 1))
    for y, name, values, color in ((150, "ε", eps, ORANGE), (330, "z", zs, BLUE)):
        d.line((px(-3), y, px(5), y), fill=LIGHT, width=3)
        _t(d, (90, y), name, 26, color, True, True, anchor="mm")
        for v in values:
            _dot(d, px(v), y, color, 10)
            label = fmt(v, 1) if name == "ε" else fmt(v, 0)
            _t(d, (px(v), y - 18 if name == "ε" else y + 18), label, 21, color, True, True,
               anchor="mb" if name == "ε" else "ma")
    for e, z in zip(eps, zs):
        arrow(d, (px(e), 166), (px(z), 312), LIGHT, 3)
    _chip(d, (px(1), 400), "μ", BLUE, BLUE_L, 21, code=True)
    return image


@figure("a7e-4", 560, 200)
def a7e_paths():
    assert 100 * 784 == 100 * 1 * 28 * 28
    image, d = _new(400)
    _title(d, "새 사진을 만들 때는 디코더만 지납니다")
    cols = [(140, 130), (296, 100), (422, 150), (598, 100), (724, 130), (900, 180)]
    rows = [(150, "학습 경로", BLUE), (300, "생성 경로", ORANGE)]
    for y, name, color in rows:
        _chip(d, (36, y), name, color, PALE[color], 19, anchor="lm")
    texts = [[["사진", "(100, 784)"], ["인코더"], ["z", "(100, 200)"], ["디코더"], ["(100, 784)"], None],
             [None, ["인코더"], ["torch.randn", "(100, 200)"], ["디코더"], ["(100, 784)"], ["(100, 1, 28, 28)"]]]
    for r, (y, _, _) in enumerate(rows):
        prev = None
        for c, (x, w) in enumerate(cols):
            lines = texts[r][c]
            if lines is None:
                continue
            rect = (x, y - 40, x + w, y + 40)
            if r == 1 and c == 1:
                _dash(d, rect, LIGHT, 2, 7)
                _t(d, (x + w / 2.0, y), "인코더", 20, LIGHT, anchor="mm")
            elif lines == ["인코더"]:
                _box(d, rect, [("인코더", "white", True, False)], fill=BLUE, outline=BLUE, size=20)
            elif lines == ["디코더"]:
                _box(d, rect, [("디코더", "white", True, False)], fill=GREEN, outline=GREEN, size=20)
            else:
                _box(d, rect, [(t, INK, k == 0 and len(lines) > 1 and not t.startswith("("), True)
                               for k, t in enumerate(lines)], fill="white", outline=LIGHT, size=19, gap=6)
            if prev is not None and not (r == 1 and c == 2):
                arrow(d, (prev + 4, y), (x - 6, y), INK, 3)
            prev = x + w
            if r == 1 and c == 1:
                prev = None
        if r == 1:
            _t(d, ((cols[4][0] + cols[4][1] + cols[5][0]) / 2.0, y - 12), "view", 19, MUTED, code=True, anchor="mb")
    return image


# a7f VAE 손실의 복원 항과 KL 항 계산하기

def _kl(mu, log_var):
    return -0.5 * (1 + log_var - mu ** 2 - exp(log_var))


def _a7f_numbers():
    bces = [_bce(0.8, 1), _bce(0.1, 0), _bce(0.9, 1)]
    assert [_r4(b) for b in bces] == [0.2231, 0.1054, 0.1054]
    recon = sum(bces)
    assert _r4(recon) == 0.4339 and _r4(recon / 3) == 0.1446
    kls = [_kl(0, 0), _kl(1, 0), _kl(0, log(4)), _kl(0, log(0.25))]
    assert [_r4(v) for v in kls] == [0, 0.5, 0.8069, 0.3181]
    assert _r4(kls[1] + kls[2]) == 1.3069 and _r4(_kl(1, log(4))) == 1.3069
    assert _r4(0.4339 + 1.3069) == 1.7408 and round(recon + kls[1] + kls[2], 6) == 1.740717
    return bces, kls


@figure("a7f-1", 560, 240)
def a7f_recon():
    bces, _ = _a7f_numbers()
    image, d = _new(480)
    _title(d, "픽셀 셋의 BCE를 더하면 0.4339, 평균은 0.1446")
    x, y, widths, row_h = 180, 90, [140, 220, 220, 220], 60
    d.rectangle((x, y, x + sum(widths), y + 52), fill=NOTE)
    for c, name in enumerate(("픽셀 1", "픽셀 2", "픽셀 3")):
        _t(d, (x + sum(widths[:c + 1]) + widths[c + 1] / 2.0, y + 26), name, 20, MUTED, True, anchor="mm")
    rows = [("x", ["1", "0", "1"], INK), ("x̂", ["0.8", "0.1", "0.9"], INK), ("BCE", [_n(b) for b in bces], BLUE)]
    for r, (name, values, color) in enumerate(rows):
        top = y + 52 + r * row_h
        d.line((x, top, x + sum(widths), top), fill=LINE, width=2)
        if name == "x̂":
            _hat_x(d, (x + widths[0] / 2.0, top + row_h / 2.0), 24, INK)
        else:
            _t(d, (x + widths[0] / 2.0, top + row_h / 2.0), name, 22, color, True, True, anchor="mm")
        for c, value in enumerate(values):
            _t(d, (x + sum(widths[:c + 1]) + widths[c + 1] / 2.0, top + row_h / 2.0), value, 22, color, color == BLUE, True,
               anchor="mm")
    d.rectangle((x, y, x + sum(widths), y + 52 + 3 * row_h), outline=LINE, width=2)
    for k, (name, value, color) in enumerate((("reduction='sum'", 0.4339, BLUE), ("reduction='mean'", 0.1446, MUTED))):
        x0 = 180 + k * 410
        d.rounded_rectangle((x0, 340, x0 + 390, 410), 12, fill=BLUE_L if k == 0 else NOTE, outline=color, width=2)
        _t(d, (x0 + 20, 375), name, 20, color if k == 0 else INK, False, True, anchor="lm")
        _t(d, (x0 + 370, 375), _n(value), 26, color if k == 0 else INK, True, True, anchor="rm")
    assert _r4(sum(bces)) == 0.4339 and _r4(sum(bces) / 3) == 0.1446
    _foot(d, 440, "F.binary_cross_entropy의 reduction 기본값은 'mean'입니다.")
    return image


def _pdf(x, mu, var):
    return exp(-(x - mu) ** 2 / (2 * var)) / sqrt(2 * pi * var)


def _a7f2_frame(k, kls):
    image, d = _new(560)
    _title(d, "N(μ, σ²)가 N(0, 1)에서 벗어날수록 KL 항이 커집니다")
    box = (90, 130, 760, 470)
    px, py = _axes(box, (-5, 5), (0, 0.85))
    d.line((box[0], box[3], box[2], box[3]), fill=LIGHT, width=2)
    for v in range(-4, 5, 2):
        d.line((px(v), box[3], px(v), box[3] + 6), fill=LIGHT, width=2)
        _t(d, (px(v), box[3] + 10), fmt(v, 0), 19, MUTED, anchor="ma")
    _curve(d, lambda x: _pdf(x, 0, 1), -5, 5, px, py, (0, 1), LIGHT, 4)
    cases = [((0, 0), "0"), ((1, 0), "0"), ((0, log(4)), "ln 4"), ((0, log(0.25)), "ln 0.25")]
    if k < 4:
        (mu, lv), lv_text = cases[k]
        _curve(d, lambda x: _pdf(x, mu, exp(lv)), -5, 5, px, py, (0, 1), BLUE, 5)
        _box(d, (790, 140, 1084, 280), [("μ = %s" % fmt(mu, 0), INK, False, True), ("log σ² = %s" % lv_text, INK, False, True),
                                        ("KL 항 %s" % _n(kls[k]), ORANGE, True, True)], fill="white", outline=LIGHT, size=22,
             gap=12)
    else:
        _curve(d, lambda x: _pdf(x, 1, 1), -5, 5, px, py, (0, 1), BLUE, 5)
        _curve(d, lambda x: _pdf(x, 0, 4), -5, 5, px, py, (0, 1), BLUE_D, 4)
        _t(d, (px(1.1) + 30, py(_pdf(1.1, 1, 1)) - 4), "(1, 0)", 20, BLUE, True, anchor="lb")
        _t(d, (px(-2.8) - 8, py(_pdf(-2.8, 0, 4)) - 20), "(0, ln 4)", 20, BLUE_D, True, anchor="mb")  # 오르는 곡선을 피함
        _box(d, (790, 140, 1084, 280), [("두 차원의 합", MUTED, False, False), ("0.5 + 0.8069", INK, False, True),
                                        ("= 1.3069", ORANGE, True, True)], fill="white", outline=LIGHT, size=22, gap=12)
    d.line((800, 330, 840, 330), fill=LIGHT, width=4)
    _t(d, (852, 330), "N(0, 1)", 20, MUTED, anchor="lm")
    d.line((800, 370, 840, 370), fill=BLUE, width=5)
    _t(d, (852, 370), "N(μ, σ²)", 20, BLUE, anchor="lm")
    lines = ["μ = 0, log σ² = 0이면 두 곡선이 겹치고 KL 항은 0입니다.",
             "μ = 1, log σ² = 0이면 곡선이 오른쪽으로 1 옮겨 가고 KL 항은 0.5입니다.",
             "μ = 0, log σ² = ln 4이면 곡선이 넓게 퍼지고 KL 항은 0.8069입니다.",
             "μ = 0, log σ² = ln 0.25이면 곡선이 좁아지고 KL 항은 0.3181입니다.",
             "두 차원 (1, 0)과 (0, ln 4)의 KL 항을 더하면 1.3069입니다."]
    _t(d, (36, 532), lines[k], 20, INK, anchor="lm")
    return image


@figure("a7f-2", 560, 280)
def a7f_kl():
    _, kls = _a7f_numbers()
    return [_a7f2_frame(k, kls) for k in range(5)], [2000, 2200, 2200, 2200, 2400]


@figure("a7f-3", 560, 210)
def a7f_divide():
    total, batch = 60000, 100
    count = total // batch
    last = count - 1
    assert (count, last, last * batch, total - last * batch) == (600, 599, 59900, 100)
    assert round(total / float(last * batch), 5) == 1.00167
    image, d = _new(420)
    _title(d, "599 × 100 = 59,900은 마지막 배치 100장을 빼고 셉니다")
    y0, y1 = 180, 240
    x0, x1 = 150, 1040
    cell = 70
    # 앞 두 칸, 줄인 가운데(칸 2~598), 마지막 칸 599. 칸 폭은 모두 같은 칸 하나를 크게 그린 것임
    d.rectangle((x0, y0, x0 + cell, y1), fill=BLUE_L, outline=BLUE, width=2)
    d.rectangle((x0 + cell, y0, x0 + 2 * cell, y1), fill=BLUE_L, outline=BLUE, width=2)
    d.rectangle((x0 + 2 * cell, y0, x1 - cell, y1), fill=BLUE_L, outline=BLUE, width=2)
    for k in range(1, 28):
        a = x0 + 2 * cell + k * (x1 - x0 - 3 * cell) / 28.0
        d.line((a, y0 + 4, a, y1 - 4), fill="#93c5fd", width=1)
    d.rectangle((x1 - cell, y0, x1, y1), fill=ORANGE, outline=ORANGE_D, width=2)
    _t(d, (x1 - cell / 2.0, (y0 + y1) / 2.0), "100장", 19, "white", True, anchor="mm")
    _t(d, ((x0 + x1) / 2.0 + 20, (y0 + y1) / 2.0), "배치마다 100장", 19, BLUE_D, anchor="mm")
    _t(d, (x0 - 4, y1 + 12), "batch_idx", 19, MUTED, code=True, anchor="ra")
    for text, cx in (("0", x0 + cell / 2.0), ("1", x0 + 1.5 * cell), ("…", (x0 + x1) / 2.0), ("599", x1 - cell / 2.0)):
        _t(d, (cx, y1 + 12), text, 20, ORANGE_D if text == "599" else INK, text == "599", True, anchor="ma")
    d.line((x1 - cell, y0 - 4, x1 - cell, y0 - 40), fill=ORANGE_D, width=2)
    _t(d, (x1 - cell - 6, y0 - 40), "59,900", 20, ORANGE_D, True, True, anchor="rm")
    d.line((x1, y0 - 4, x1, y0 - 80), fill=INK, width=2)
    _t(d, (x1 - 6, y0 - 80), "60,000", 20, INK, True, True, anchor="rm")
    d.line((x0, y0 - 4, x0, y0 - 40), fill=INK, width=2)
    _t(d, (x0 + 6, y0 - 40), "0", 20, INK, True, True, anchor="lm")
    _t(d, (80, 330), "len(train_loader.dataset) = 60,000", 21, INK, code=True)
    _t(d, (80, 370), "batch_idx * batch_size = 599 × 100 = 59,900", 21, ORANGE_D, True, code=True)
    return image


@figure("a7f-4", 560, 280)
def a7f_compare():
    _, kls = _a7f_numbers()
    recon, kl = 0.4339, 1.3069
    gen, disc = _r4(-log(0.5)), _r4(-2 * log(0.5))
    assert (gen, disc) == (0.6931, 1.3863)
    image, d = _new(560)
    _title(d, "VAE 손실 1.7408과 균형에서 GAN의 두 손실")
    base, scale = 470, 170
    _t(d, (250, 96), "VAE", 22, INK, True, anchor="mm")
    x0 = 190
    d.rectangle((x0, base - recon * scale, x0 + 120, base), fill=BLUE)
    d.rectangle((x0, base - (recon + kl) * scale, x0 + 120, base - recon * scale), fill=ORANGE)
    _t(d, (x0 + 60, base - recon * scale / 2.0), "0.4339", 20, "white", True, True, anchor="mm")
    _t(d, (x0 + 60, base - (recon + kl / 2.0) * scale), "1.3069", 20, "white", True, True, anchor="mm")
    _t(d, (x0 + 60, base - (recon + kl) * scale - 10), "1.7408", 24, INK, True, True, anchor="mb")
    _t(d, (x0 + 140, base - recon * scale / 2.0), "복원 항", 20, BLUE, True, anchor="lm")
    _t(d, (x0 + 140, base - (recon + kl / 2.0) * scale), "KL 항", 20, ORANGE, True, anchor="lm")
    d.line((140, base, 420, base), fill=LIGHT, width=2)
    d.line((520, 110, 520, 500), fill=LINE, width=2)
    _t(d, (820, 96), "GAN 균형", 22, INK, True, anchor="mm")
    for k, (name, value, color) in enumerate((("생성기", gen, BLUE), ("판별기", disc, PURPLE))):
        x = 650 + k * 200
        d.rectangle((x, base - value * scale, x + 110, base), fill=color)
        _t(d, (x + 55, base - value * scale - 10), _n(value), 22, color, True, True, anchor="mb")
        _t(d, (x + 55, base + 12), name, 20, color, True, anchor="ma")
    d.line((610, base, 1000, base), fill=LIGHT, width=2)
    _t(d, (820, 528), "판별기 출력 0.5", 20, MUTED, anchor="mm")
    assert _r4(recon + kl) == 1.7408 and abs(kls[1] + kls[2] - kl) < 1e-4
    return image


# a7g U-Net 건너뛰기 연결과 pix2pix 판별기 입력

def _double_conv(i, o):
    """padding 1 인 3×3 합성곱 두 번(편향 없음)과 배치 정규화 두 번."""
    return i * o * 9 + 2 * o + o * o * 9 + 2 * o


def _up(i, o):
    return i * (i // 2) * 4 + i // 2 + _double_conv(i, o)


def _unet_params(n_classes):
    enc = _double_conv(3, 64) + sum(_double_conv(a, 2 * a) for a in (64, 128, 256, 512))
    dec = _up(1024, 512) + _up(512, 256) + _up(256, 128) + _up(128, 64)
    return enc + dec + 64 * n_classes + n_classes


def _unet_levels():
    sides, chans = [256], [64]
    for _ in range(4):
        sides.append(sides[-1] // 2)
        chans.append(chans[-1] * 2)
    assert sides == [256, 128, 64, 32, 16] and chans == [64, 128, 256, 512, 1024]
    assert _tconv_out(32, 2, 2, 0) == 64
    return sides, chans


def _a7g1_frame(k, sides, chans):
    s = iso.Sheet(W, 600)
    _st(s, (36, 24), "U-Net은 같은 크기의 인코더 특징 맵을 이어 붙입니다", 25, INK, True)
    ys = [138, 230, 316, 400, 484]
    enc_x, dec_x = 150, 790
    fronts = [5 * sqrt(v) for v in sides]

    def span(n, ch):
        return fronts[n] + 2.2 * sqrt(ch) * iso.DEPTH[0]

    def plate(cx, n, state, ch):
        w = fronts[n]
        return s.box(cx - span(n, ch) / 2.0, ys[n] - w / 2.0, w, w, 2.2 * sqrt(ch), state)

    _st(s, (enc_x, 70), "인코더", 20, MUTED, True, anchor="mm")
    _st(s, (dec_x, 70), "디코더", 20, MUTED, True, anchor="mm")
    for n in range(5):
        plate(enc_x, n, "strong" if k == 0 else "seen", chans[n])
        right = enc_x + span(n, chans[n]) / 2.0
        _st(s, (right + 14, ys[n] - 12), "%d채널" % chans[n], 20, BLUE if k == 0 else INK, True, anchor="lm")
        _st(s, (right + 14, ys[n] + 14), "%d × %d" % (sides[n], sides[n]), 19, MUTED, anchor="lm")
        if n < 4:
            s.arrow((enc_x - 74, ys[n] + 16), (enc_x - 74, ys[n + 1] - 16), iso.GRAY, width=2, size=(10, 5))
    # 디코더 단 3(32 × 32)은 Up(1024, 512) 출력, 단 2(64 × 64)는 Up(512, 256) 의 전치 합성곱 출력과 이어 붙인 결과
    state = {n: "todo" for n in range(4)}
    if k >= 1:
        state[3] = "strong" if k == 1 else "seen"
        state[2] = "strong" if k in (1, 2) else "seen"
    if k >= 3:
        state[0] = state[1] = state[2] = "strong"
    dec_ch = {3: 512, 2: 512 if k == 2 else 256, 1: 128, 0: 64}
    for n in range(4):
        plate(dec_x, n, state[n], dec_ch[n])
        if state[n] != "todo":
            text = "(1, %d, %d, %d)" % (dec_ch[n], sides[n], sides[n])
            _st(s, (dec_x + span(n, dec_ch[n]) / 2.0 + 12, ys[n]), text, 19, BLUE if state[n] == "strong" else INK, True,
                True, anchor="lm")
    if k >= 1:
        hot = BLUE if k == 1 else iso.GRAY
        s.path([(330, ys[4]), (dec_x, ys[4])], hot, 2.5)
        s.arrow((dec_x, ys[4]), (dec_x, ys[3] + fronts[3] / 2.0 + 6), hot, width=2.5, size=(12, 6))
        _slabel(s, (560, ys[4]), "Up(1024, 512)", "blue", "new" if k == 1 else "seen", 19, code=True)
        s.arrow((dec_x - 64, ys[3] - 14), (dec_x - 64, ys[2] + 22), hot, width=2.5, size=(10, 5))
        _st(s, (dec_x - 76, (ys[2] + ys[3]) / 2.0 + 4), "전치 합성곱", 19, BLUE if k == 1 else MUTED, k == 1, anchor="rm")
    for n in range(4):
        if not ((n == 3 and k >= 1) or (n == 2 and k >= 2) or (n <= 1 and k >= 3)):
            continue
        hot = (n == 2 and k == 2) or (n <= 1 and k == 3)
        left, right = 330, dec_x - span(n, dec_ch[n]) / 2.0 - 16
        s.arrow((left, ys[n]), (right, ys[n]), iso.TONES["orange"][1] if hot else iso.GRAY, width=2.5,
                dash=None if hot else iso.DASH)
        if n != 3 or k >= 3:
            _slabel(s, (500, ys[n] - 20), "%d + %d = %d" % (chans[n], chans[n], 2 * chans[n]), "orange",
                    "new" if hot else "seen", 19, code=True)
    lines = ["인코더가 3채널 256 × 256 입력을 1024채널 16 × 16까지 줄입니다.",
             "Up(1024, 512)가 (1, 512, 32, 32)를 내고, 전치 합성곱이 (1, 256, 64, 64)로 키웁니다.",
             "같은 64 × 64인 인코더 특징 맵 256채널을 이어 붙여 512채널이 됩니다.",
             "DoubleConv가 256채널로 줄이고, 다음 Up이 같은 일을 되풀이해 256 × 256까지 돌아갑니다."]
    _st(s, (36, 578), lines[k], 19, INK, anchor="lm")
    return s.image()


@figure("a7g-1", 560, 300)
def a7g_unet():
    sides, chans = _unet_levels()
    return [_a7g1_frame(k, sides, chans) for k in range(4)], [2400, 2200, 2200, 2400]


@figure("a7g-2", 560, 220)
def a7g_head():
    two, three = _unet_params(2), _unet_params(3)
    assert (64 * 2 + 2, 64 * 3 + 3) == (130, 195) and (two, three) == (31037698, 31037763) and three - two == 65
    s = iso.Sheet(W, 440)
    _st(s, (36, 24), "1×1 합성곱 출력층의 파라미터는 2채널 130개, 3채널 195개", 25, INK, True)
    s.stack(40, 196, 80, 80, 5, rows=1, cols=1, thick=5, default="seen", states={0: "new"})
    _st(s, (100, 310), "64채널", 21, BLUE, True, anchor="mm")
    _st(s, (100, 338), "특징 맵", 19, MUTED, anchor="mm")
    widths, gap, start = [140, 92, 140, 202, 192], 18, 234
    xs = [start + sum(widths[:c]) + gap * c for c in range(5)]
    assert xs[-1] + widths[-1] <= W - 16
    rows = [(150, ["1×1 합성곱", None, "출력 2채널", "64 × 2 + 2 = 130", "전체 31,037,698"], "blue"),
            (310, ["1×1 합성곱", "Tanh", "출력 3채널", "64 × 3 + 3 = 195", "전체 31,037,763"], "orange")]
    for y, items, tone in rows:
        s.arrow((196, 236), (xs[0] - 8, y), iso.GRAY, width=2, size=(10, 5))
        prev = None
        for c, text in enumerate(items):
            if text is None:
                continue
            kind = ("blue", "new") if c == 0 else (("orange", "new") if text == "Tanh" else
                                                    ((tone, "new") if c == 3 else ("gray", "seen")))
            rect = s.card((xs[c] + widths[c] / 2.0, y), [text], kind[0], kind[1], size=20, width=widths[c],
                          code=c >= 3)
            _sheet_room(s, rect, text)
            if prev is not None:
                assert rect[0] - prev >= 16, text
                s.arrow((prev + 4, y), (rect[0] - 4, y), iso.GRAY, width=2, size=(10, 5))
            prev = rect[2]
    return s.image()


@figure("a7g-3", 560, 280)
def a7g_patch():
    side = 256
    for k, st, p in ((4, 2, 1), (4, 2, 1), (4, 2, 1), (4, 1, 1), (4, 1, 1)):
        side = _conv_out(side, k, st, p)
    field = 1
    for k, st in reversed(((4, 2), (4, 2), (4, 2), (4, 1), (4, 1))):
        field = (field - 1) * st + k
    assert (side, field, 3 + 3) == (30, 70, 6)
    image, d = _new(560)
    _title(d, "pix2pix 판별기는 사진 쌍을 6채널로 받아 30 × 30 지도를 냅니다")
    size = 150
    inputs = [(92, "y", GREEN, GREEN_L, "6채널 (x, y)"), (330, "G(x)", BLUE, BLUE_L, "6채널 (x, G(x))")]
    for top, back, color, fill, name in inputs:
        d.rectangle((230, top, 230 + size, top + size), fill=fill, outline=color, width=2)
        _t(d, (230 + size - 8, top + 6), "%s · 3채널" % back, 19, color, True, anchor="ra")
        d.rectangle((206, top + 30, 206 + size, top + 30 + size), fill="#f8fafc", outline=LIGHT, width=2)
        _t(d, (216, top + 38), "x · 3채널", 19, MUTED, True)
        _t(d, (36, top + 90), name, 21, INK, True, anchor="lm")
        _t(d, (36, top + 120), "256 × 256", 19, MUTED, anchor="lm")
    patch = size * field / 256.0
    px0, py0 = 262, 172
    _dash(d, (px0, py0, px0 + patch, py0 + patch), ORANGE, 3, 6)
    _t(d, (px0 + patch / 2.0, py0 + patch + 6), "70 × 70", 19, ORANGE_D, True, anchor="ma")
    arrow(d, (392, 200), (560, 288), PURPLE, 4)
    arrow(d, (392, 430), (560, 332), PURPLE, 4)
    _box(d, (566, 270, 716, 350), [("판별기", PURPLE, True, False)], fill=PURPLE_L, outline=PURPLE, size=22, width=3)
    arrow(d, (722, 310), (770, 310), PURPLE, 4)
    gx, gy, cell = 780, 230, 5.4
    d.rectangle((gx, gy, gx + 30 * cell, gy + 30 * cell), fill="white", outline=LIGHT, width=2)
    for k in range(1, 30):
        d.line((gx + k * cell, gy, gx + k * cell, gy + 30 * cell), fill=LINE, width=1)
        d.line((gx, gy + k * cell, gx + 30 * cell, gy + k * cell), fill=LINE, width=1)
    hx, hy = gx + 6 * cell, gy + 6 * cell
    d.rectangle((hx, hy, hx + cell, hy + cell), fill=ORANGE)
    _dash_line(d, (px0 + patch, py0, hx, hy), ORANGE, 2, 6)
    _dash_line(d, (px0 + patch, py0 + patch, hx, hy + cell), ORANGE, 2, 6)
    _t(d, (gx + 15 * cell, gy + 30 * cell + 14), "30 × 30 판정 지도", 21, INK, True, anchor="ma")
    _t(d, (gx + 15 * cell, gy + 30 * cell + 46), "손실에는 평균을 씀", 19, MUTED, anchor="ma")
    return image


# 세 수준 블록 그림

@figure("a7a-31", 520, 280)
def a7a_level7():
    image, d = _new(LH, LW)
    x0, x1 = 300, 960

    def px(v):
        return x0 + (x1 - x0) * v

    for y, name, value, gap_from, gap_to, gap_text, color in ((170, "진짜 사진", 0.8, 0.8, 1.0, "0.2", BLUE),
                                                              (390, "가짜 사진", 0.3, 0.0, 0.3, "0.3", ORANGE)):
        _t(d, (60, y), name, LEVEL_MIN + 3, color, True, anchor="lm", low=LEVEL_MIN)
        d.rounded_rectangle((x0, y - 10, x1, y + 10), 10, fill=NOTE, outline=LIGHT, width=2)
        d.rectangle((px(gap_from), y - 10, px(gap_to), y + 10), fill=ORANGE_L, outline=ORANGE, width=2)
        _t(d, (x0, y + 26), "0", LEVEL_MIN, MUTED, code=True, anchor="ma", low=LEVEL_MIN)
        _t(d, (x1, y + 26), "1", LEVEL_MIN, MUTED, code=True, anchor="ma", low=LEVEL_MIN)
        bx0, bx1 = px(gap_from), px(gap_to)
        d.line((bx0, y - 30, bx0, y - 44, bx1, y - 44, bx1, y - 30), fill=ORANGE, width=4)
        _t(d, ((bx0 + bx1) / 2.0, y - 52), gap_text, LEVEL_MIN + 3, ORANGE_D, True, True, anchor="mb", low=LEVEL_MIN)
        _dot(d, px(value), y, color, 16)
        _t(d, (px(value), y + 26), _n(value, 1), LEVEL_MIN, color, True, True, anchor="ma", low=LEVEL_MIN)
    return image


@figure("a7a-32", 520, 280)
def a7a_level15():
    real, fake = _a7a_numbers()
    image, d = _new(LH, LW)
    rows = [["진짜", "0.8", "1", "−ln p", _n(real)], ["가짜", "0.3", "0", "−ln(1 − p)", _n(fake)]]
    right, bottom = _ltable(d, 40, 70, [150, 170, 130, 300, 210], ["사진", "출력 p", "정답", "식", "손실"], rows,
                            marks={(0, 4): BLUE, (1, 4): BLUE})
    _t(d, (right, bottom + 70), "합 0.5798", LEVEL_MIN + 5, BLUE_D, True, True, anchor="rm", low=LEVEL_MIN)
    return image


@figure("a7a-33", 520, 280)
def a7a_level20():
    real, fake = _a7a_numbers()
    image, d = _new(LH, LW)
    size = LEVEL_MIN
    for y, inp, out in ((80, "0.8", _n(real)), (180, "0.3", _n(fake))):
        _cell(d, (40, y - 34, 150, y + 34), inp, BLUE_L, BLUE, size, BLUE_D, True, low=LEVEL_MIN)
        arrow(d, (160, y), (200, y), INK, 4)
        _cell(d, (210, y - 34, 400, y + 34), "BCELoss", NOTE, LIGHT, size, INK, True, low=LEVEL_MIN)
        arrow(d, (410, y), (450, y), INK, 4)
        _cell(d, (460, y - 34, 610, y + 34), out, "white", LIGHT, size, INK, True, low=LEVEL_MIN)
    d.line((630, 46, 650, 46, 650, 214, 630, 214), fill=INK, width=4)
    _t(d, (690, 130), "+", LEVEL_MIN + 8, INK, True, True, anchor="mm", low=LEVEL_MIN)
    arrow(d, (720, 130), (770, 130), INK, 4)
    _cell(d, (780, 96, 960, 164), "0.5798", PURPLE_L, PURPLE, LEVEL_MIN + 2, PURPLE_D, True, low=LEVEL_MIN)
    d.line((40, 270, 1000, 270), fill=LINE, width=2)
    y = 400
    _cell(d, (40, y - 40, 330, y + 40), "[[0.8], [0.3]]", BLUE_L, BLUE, size, BLUE_D, True, low=LEVEL_MIN)
    arrow(d, (340, y), (380, y), INK, 4)
    _cell(d, (390, y - 40, 580, y + 40), "BCELoss", NOTE, LIGHT, size, INK, True, low=LEVEL_MIN)
    arrow(d, (590, y), (630, y), INK, 4)
    _cell(d, (640, y - 40, 820, y + 40), "0.2899", ORANGE_L, ORANGE, LEVEL_MIN + 2, ORANGE_D, True, low=LEVEL_MIN)
    return image


@figure("a7c-31", 520, 280)
def a7c_level7():
    small = [[1, 2], [3, 4]]
    big = _upsample(small)
    assert big[0][:2] == big[1][:2] == [1, 1]
    image, d = _new(LH, LW)
    _num_grid(d, 140, 180, small, 110, 44, low=LEVEL_MIN, gap=12)
    _num_grid(d, 600, 70, big, 104, 40, low=LEVEL_MIN, gap=10)
    d.rounded_rectangle((592, 62, 806, 276), 14, outline=BLUE, width=5)
    d.line((189, 176, 189, 40, 520, 40, 520, 110), fill=BLUE, width=6, joint="curve")
    arrow(d, (520, 110), (584, 110), BLUE, 6)
    return image


@figure("a7c-32", 520, 280)
def a7c_level15():
    sides = [16, 32, 64]
    assert [s * s for s in sides] == [256, 1024, 4096]
    rows = [["처음", "16", "256"], ["한 번 키운 뒤", "32", "1,024"], ["두 번 키운 뒤", "64", "4,096"]]
    return levels.grid(rows, col_names=("단계", "한 변", "칸 수"), marks=[(0, 1), (1, 1), (2, 1)], color="blue")


@figure("a7c-33", 520, 280)
def a7c_level20():
    assert (2 // 2, 1 // 2) == (1, 0) and _upsample([[1, 2], [3, 4]])[2][1] == 3
    image, d = _new(LH, LW)
    cell = 82
    ox, oy = 120, 130
    _t(d, (ox + 2 * cell, oy - 74), "출력", LEVEL_MIN, INK, True, anchor="mb", low=LEVEL_MIN)
    for i in range(4):
        _t(d, (ox - 26, oy + (i + 0.5) * cell), i, LEVEL_MIN, MUTED, code=True, anchor="mm", low=LEVEL_MIN)
        _t(d, (ox + (i + 0.5) * cell, oy - 26), i, LEVEL_MIN, MUTED, code=True, anchor="mm", low=LEVEL_MIN)
        for j in range(4):
            hit = (i, j) == (2, 1)
            d.rectangle((ox + j * cell, oy + i * cell, ox + (j + 1) * cell, oy + (i + 1) * cell), fill=BLUE if hit else "white",
                        outline=LIGHT, width=2)
    ix, iy = 760, 210
    _t(d, (ix + cell, iy - 74), "입력", LEVEL_MIN, INK, True, anchor="mb", low=LEVEL_MIN)
    for i in range(2):
        _t(d, (ix - 26, iy + (i + 0.5) * cell), i, LEVEL_MIN, MUTED, code=True, anchor="mm", low=LEVEL_MIN)
        _t(d, (ix + (i + 0.5) * cell, iy - 26), i, LEVEL_MIN, MUTED, code=True, anchor="mm", low=LEVEL_MIN)
        for j in range(2):
            hit = (i, j) == (1, 0)
            d.rectangle((ix + j * cell, iy + i * cell, ix + (j + 1) * cell, iy + (i + 1) * cell), fill=ORANGE_L if hit else "white",
                        outline=ORANGE if hit else LIGHT, width=5 if hit else 2)
    start = (ox + 1.5 * cell + 30, oy + 2.5 * cell)
    end = (ix - 50, iy + 1.5 * cell)
    arrow(d, start, end, INK, 5)
    _t(d, (560, 266), "2 // 2 = 1", LEVEL_MIN, INK, True, True, anchor="mb", low=LEVEL_MIN)
    _t(d, (560, 312), "1 // 2 = 0", LEVEL_MIN, INK, True, True, anchor="mb", low=LEVEL_MIN)
    return image


@figure("a7e-31", 520, 280)
def a7e_level7():
    image, d = _new(LH, LW)
    tops, bottoms = ["0보다 작은 수", "0", "0보다 큰 수"], ["1보다 작은 수", "1", "1보다 큰 수"]
    _t(d, (40, 150), "로그 분산", LEVEL_MIN, INK, True, anchor="lm", low=LEVEL_MIN)
    _t(d, (40, 400), "표준편차", LEVEL_MIN, INK, True, anchor="lm", low=LEVEL_MIN)
    for k, (top, bottom) in enumerate(zip(tops, bottoms)):
        x = 230 + k * 270
        mid = k == 1
        _cell(d, (x, 100, x + 250, 200), top, BLUE_L if mid else "white", BLUE if mid else LIGHT, LEVEL_MIN, BLUE_D if mid else INK,
              mid, code=False, width=3 if mid else 2, low=LEVEL_MIN)
        arrow(d, (x + 125, 214), (x + 125, 338), BLUE, 6)
        _cell(d, (x, 350, x + 250, 450), bottom, BLUE_L if mid else "white", BLUE if mid else LIGHT, LEVEL_MIN,
              BLUE_D if mid else INK, mid, code=False, width=3 if mid else 2, low=LEVEL_MIN)
    return image


@figure("a7e-32", 520, 280)
def a7e_level15():
    assert _r4(_std(-2)) == 0.3679 and round(_std(log(4)), 6) == 2
    rows = [[fmt(-2, 0), fmt(-1, 0), "0.3679"], ["ln 4", "ln 2", "2"]]
    return levels.grid(rows, col_names=("로그 분산", "절반", "표준편차"), marks=[(0, 2), (1, 2)], color="blue")


@figure("a7e-33", 520, 280)
def a7e_level20():
    outs = [-2.0, 0.0, 1.3863]
    std = [_std(v) for v in outs]
    bad = [None if v < 0 else sqrt(v) for v in outs]
    assert [_r4(v) for v in std] == [0.3679, 1, 2] and bad[0] is None and _r4(bad[2]) == 1.1774
    image, d = _new(LH, LW)
    rows = [("log_var", [fmt(v, 4) for v in outs], INK, None), ("std", ["0.3679", "1", "2"], GREEN, None),
            ("bad", ["nan", "0", "1.1774"], INK, 0)]
    for r, (name, values, color, red) in enumerate(rows):
        y = 110 + r * 160
        _t(d, (250, y), name, LEVEL_MIN + 2, color if color != INK else MUTED, True, True, anchor="rm", low=LEVEL_MIN)
        for c, value in enumerate(values):
            x = 290 + c * 240
            hot = red == c
            _cell(d, (x, y - 50, x + 210, y + 50), value, RED_L if hot else (GREEN_L if color == GREEN else "white"),
                  RED if hot else (GREEN if color == GREEN else LIGHT), LEVEL_MIN + 2, RED if hot else INK, hot or color == GREEN,
                  width=5 if hot else 2, low=LEVEL_MIN)
    return image


@figure("a7f-31", 520, 280)
def a7f_level7():
    values = [_kl(mu, 0) for mu in (0, 1, 2)]
    assert [_r4(v) for v in values] == [0, 0.5, 2]
    image, d = _new(LH, LW)
    x0, x1, base = 100, 940, 400
    px, py = _axes((x0, 60, x1, base), (-1.4, 3.4), (0, 1.8))
    d.line((x0, base, x1, base), fill=INK, width=3)
    for k, mu in enumerate((0, 1, 2)):
        color = LIGHT if k == 0 else BLUE
        _curve(d, lambda x: _pdf(x, mu, 0.06), mu - 1.2, mu + 1.2, px, py, (0.0005, 2), color, 6)
        d.line((px(mu), base - 8, px(mu), base + 8), fill=INK, width=3)
        _t(d, (px(mu), base + 18), mu, LEVEL_MIN + 2, INK, True, True, anchor="ma", low=LEVEL_MIN)
        _chip(d, (px(mu), base - 60), _n(values[k], 1), ORANGE, ORANGE_L, LEVEL_MIN, code=True, low=LEVEL_MIN)
    return image


@figure("a7f-32", 520, 280)
def a7f_level15():
    inside = 1 + log(4) - 1 - 4
    assert _r4(1 + 1.3863 - 1 - 4) == _r4(inside) == -2.6137 and _r4(-0.5 * inside) == 1.3069
    image, d = _new(LH, LW)
    _ltable(d, 120, 40, [200, 200, 200, 200], ["상수", "log σ²", "μ²", "σ²"], [["1", "1.3863", "1", "4"]], code=True)
    _t(d, (120, 260), "괄호 안", LEVEL_MIN, MUTED, True, anchor="lm", low=LEVEL_MIN)
    _t(d, (920, 260), "1 + 1.3863 − 1 − 4 = −2.6137", LEVEL_MIN, INK, True, True, anchor="rm", low=LEVEL_MIN)
    d.rounded_rectangle((100, 330, 940, 430), 14, fill=BLUE_L, outline=BLUE, width=3)
    _t(d, (130, 380), "KL 항", LEVEL_MIN, BLUE_D, True, anchor="lm", low=LEVEL_MIN)
    _t(d, (910, 380), "−0.5 × (−2.6137) = 1.3069", LEVEL_MIN, BLUE_D, True, True, anchor="rm", low=LEVEL_MIN)
    return image


@figure("a7f-33", 520, 280)
def a7f_level20():
    cells = [[1 + lv - mu ** 2 - exp(lv) for mu, lv in ((1, 0), (0, 1.3863))] for _ in range(2)]
    assert [[_r4(v) for v in row] for row in cells] == [[-1, -1.6137], [-1, -1.6137]]
    image, d = _new(LH, LW)
    x, y, cw, ch = 260, 150, 180, 110
    for c, name in enumerate(("차원 1", "차원 2")):
        _t(d, (x + c * cw + cw / 2.0, y - 34), name, LEVEL_MIN, MUTED, True, anchor="mm", low=LEVEL_MIN)
    for r in range(2):
        _t(d, (x - 20, y + r * ch + ch / 2.0), "데이터 %d" % (r + 1), LEVEL_MIN, MUTED, True, anchor="rm", low=LEVEL_MIN)
        for c in range(2):
            _cell(d, (x + c * cw + 8, y + r * ch + 8, x + (c + 1) * cw - 8, y + (r + 1) * ch - 8), _n(cells[r][c]), BLUE_L,
                  BLUE, LEVEL_MIN, BLUE_D, True, low=LEVEL_MIN)
    d.line((x - 190, y - 70, x - 206, y - 70, x - 206, y + 2 * ch + 14, x - 190, y + 2 * ch + 14), fill=INK, width=4)
    d.line((x + 2 * cw + 14, y - 70, x + 2 * cw + 30, y - 70, x + 2 * cw + 30, y + 2 * ch + 14, x + 2 * cw + 14,
            y + 2 * ch + 14), fill=INK, width=4)
    _chip(d, (x + 2 * cw + 60, y + ch - 30), "torch.sum", BLUE, BLUE_L, LEVEL_MIN, anchor="lm", code=True, low=LEVEL_MIN)
    _t(d, (x + 2 * cw + 60, y + ch + 34), "네 칸을 더해", LEVEL_MIN, INK, anchor="lm", low=LEVEL_MIN)
    _t(d, (x + 2 * cw + 60, y + ch + 80), "숫자 하나", LEVEL_MIN, INK, anchor="lm", low=LEVEL_MIN)
    return image
