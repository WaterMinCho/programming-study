# -*- coding: utf-8 -*-
"""응용 코딩 실습 노트 al18 의 그림.

  ~/.cache/rokey-dev/lib/bin/python -m tools.ai_art al18 a18a-2   이름을 적은 그림만 그림

Pillow 로 직접 그린 격자·마스크·좌표축·표임. 강의 그림과 사진은 쓰지 않음.
그림에 찍는 숫자·좌표·모양은 이 파일에서 NumPy 로 다시 계산하고 assert 로 본문 숫자와 견줌.
코드 줄은 ai/patterns/apc/S10N.json 에서 읽어 노트·카드와 같은 줄이 나옴.
글자는 파일에서 19px 이상(화면 폭이 파일의 절반이라 화면에서 9.5px 이상)으로 씀.

a18a 색: 노랑 = 자를 영역, 빨강 = preview 에 칠한 칸·두 값을 거꾸로 적은 값, 초록 = 슬라이스로 고른 칸·바르게 적은 값,
파랑 = 모양이 바뀌는 줄, 주황 = x 가 커지는 쪽, 보라 = y 가 커지는 쪽. 그림 3 의 빨강·초록·파랑 칸은 R·G·B 값임.
a18b 색: 파랑 = 행 번호 y 와 줄 화살표, 주황 = 열 번호 x 와 (x, y) 모서리, 초록 = H 범위 안의 칸과 patch 범위,
빨강 = 이번 장에서 바뀐 칸과 열기를 하지 않은 범위, 회색 = 입력·결과 상자와 배운 곳 꼬리표.
"""
import colorsys
import json
import os
import re
from functools import lru_cache
from math import hypot

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from tools.ai_art import COLORS, FONTS, ROOT, figure
from tools.ai_art.al04 import arrow

W = 1120
INK, MUTED, FAINT = COLORS["ink"], COLORS["muted"], COLORS["faint"]
BLUE, RED, ORANGE, GREEN, PURPLE = COLORS["blue"], COLORS["red"], COLORS["orange"], COLORS["green"], COLORS["purple"]
YELLOW = "#eab308"
BLUE_L, RED_L, GREEN_L, ORANGE_L = "#dbeafe", "#fee2e2", "#d1fae5", "#ffedd5"
NOTE, LINE, LIGHT = "#f3f4f6", "#e5e7eb", "#9ca3af"
PIXEL = "#e5e7eb"
MIN_SIZE = 19


# 공통 도우미

@lru_cache(maxsize=None)
def _face(size, bold=False, code=False):
    if code:
        name = "D2Coding-Bold.ttf" if bold else "D2Coding-Regular.ttf"
    else:
        name = "NanumGothic-Bold.ttf" if bold else "NanumGothic-Regular.ttf"
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _new(h):
    image = Image.new("RGB", (W, h), "white")
    return image, ImageDraw.Draw(image)


def _w(value, size, bold=False, code=False):
    return _face(size, bold, code).getlength(str(value))


def _t(d, xy, value, size=21, color=INK, bold=False, code=False, anchor="la", bg=None):
    """글자 한 줄. 그림 밖으로 나가거나 너무 작으면 assert 로 멈춤. 차지한 상자를 돌려줌."""
    value = str(value)
    assert size >= MIN_SIZE, (value, size)
    assert "−" not in value, value
    face = _face(size, bold, code)
    box = d.textbbox(xy, value, font=face, anchor=anchor)
    width, height = d.im.size
    assert box[0] >= 8 and box[1] >= 6 and box[2] <= width - 8 and box[3] <= height - 6, (value, box)
    if bg:
        d.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill=bg)
    d.text(xy, value, font=face, fill=color, anchor=anchor)
    return box


def _dash(d, box, color, width=3, dash=9):
    x0, y0, x1, y1 = box
    for a, b, c, e in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        _dash_line(d, (a, b, c, e), color, width, dash)


def _dash_line(d, seg, color, width=3, dash=9):
    a, b, c, e = seg
    length = hypot(c - a, e - b)
    k = 0.0
    while k < length:
        s, t = k / length, min(k + dash, length) / length
        d.line((a + (c - a) * s, b + (e - b) * s, a + (c - a) * t, b + (e - b) * t), fill=color, width=width)
        k += 2 * dash


def _cells(d, x, y, rows, cols, cell, fill=None, line="white", width=2):
    for r in range(rows):
        for c in range(cols):
            color = fill(r, c) if fill else PIXEL
            d.rectangle((x + c * cell, y + r * cell, x + (c + 1) * cell, y + (r + 1) * cell), fill=color, outline=line,
                        width=width)


def _around(x, y, cell, r0, r1, c0, c1, pad=0):
    """r0~r1-1 행, c0~c1-1 열 칸을 감싸는 상자(끝 번호는 넣지 않음)."""
    return (x + c0 * cell - pad, y + r0 * cell - pad, x + c1 * cell + pad, y + r1 * cell + pad)


def _tag(d, x, y, lines, size=19, width=None):
    """배운 곳 꼬리표. 회색 둥근 상자에 줄마다 글자. 상자 아래 y 를 돌려줌."""
    width = width or max(_w(s, size) for s in lines) + 24
    height = len(lines) * (size + 7) + 12
    d.rounded_rectangle((x, y, x + width, y + height), 10, fill=NOTE, outline=LIGHT, width=2)
    for k, s in enumerate(lines):
        assert _w(s, size) <= width - 20, (s, width)
        _t(d, (x + 12, y + 8 + k * (size + 7)), s, size, MUTED)
    return y + height


def _panel(d, box, title, color, items, size=19, title_size=22):
    """요약 상자. items 는 (글, 고정폭인지, 색) 이고 None 이면 빈 줄."""
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, 16, fill="white", outline=color, width=4)
    _t(d, (x0 + 18, y0 + 16), title, title_size, color, True)
    y = y0 + 16 + title_size + 18
    for item in items:
        if item is None:
            y += 10
            continue
        value, code, ink = item
        assert _w(value, size, code=code) <= x1 - x0 - 36, (value, box)
        _t(d, (x0 + 18, y), value, size, ink, code=code)
        y += size + 9
    assert y <= y1 - 8, (title, y, y1)


def _lines(skel, variant):
    with open(os.path.join(ROOT, "ai", "patterns", "apc", skel + ".json"), encoding="utf-8") as f:
        return json.load(f)["variants"][variant]["lines"]


def _unit(page, n, step=None, word=""):
    """노트 page 의 n 번째 ## 단원(step 이 있으면 그 단원의 step 번째 ### 단계)에 word 가 있는지 봄. 꼬리표 위치 확인용."""
    with open(os.path.join(ROOT, "ai", "learn", page, "page.md"), encoding="utf-8") as f:
        section = re.split(r"^## ", f.read(), flags=re.M)[n]
    if step:
        section = re.split(r"^### ", section, flags=re.M)[step]
    assert word in section, (page, n, step, word)


# a18a 사진 한 장을 잘라 모델 입력으로 바꾸기

def _a18a():
    """1단계 사진과 영역으로 그림에 찍는 값을 모두 계산함."""
    left, top, w, h = 2, 3, 8, 4
    image = np.full((8, 12, 3), 200, np.uint8)
    image[top:top + h, left:left + w] = (0, 51, 255)
    rows, cols = image.shape[:2]
    assert (rows, cols) == (8, 12)
    assert top + h == 7 and left + w == 10 and not (top + h > rows or left + w > cols)
    corner = (left + w - 1, top + h - 1)
    assert corner == (9, 6)
    # 채운 사각형은 두 꼭짓점이 놓인 칸까지 칠함
    painted = np.zeros((rows, cols), bool)
    painted[top:corner[1] + 1, left:corner[0] + 1] = True
    assert painted.sum() == 32
    x = image[top:top + h, left:left + w]
    chosen = np.zeros((rows, cols), bool)
    chosen[top:top + h, left:left + w] = True
    assert x.shape == (4, 8, 3) and (chosen == painted).all()
    rgb = x[..., ::-1]
    assert x[0, 0].tolist() == [0, 51, 255] and rgb[0, 0].tolist() == [255, 51, 0]
    # 영역 색이 하나라 cv2.resize 로 줄인 값도 같음. dsize (4, 2) 는 너비 4·높이 2
    small = np.broadcast_to(rgb[0, 0], (2, 4, 3)).copy()
    scaled = small.astype("float32") / 255.0
    assert scaled.dtype == np.float32 and (small / 255.0).dtype == np.float64
    assert [round(float(v), 1) for v in scaled[0, 0]] == [1.0, 0.2, 0.0]
    moved = scaled.transpose(2, 0, 1)
    assert moved.shape == (3, 2, 4) and (moved[0] == 1.0).sum() == 8
    batch = moved[None, ...]
    assert batch.shape == (1, 3, 2, 4)
    flipped = image[left:left + w, top:top + h]
    assert flipped.shape == (6, 4, 3)
    return dict(left=left, top=top, w=w, h=h, image=image, painted=painted, corner=corner, x=x, small=small,
                moved=moved, batch=batch, flipped=flipped)


def _a18a_lines():
    lines = _lines("S101", "표준형")
    assert len(lines) == 18
    assert lines[3] == "rows, cols = image.shape[:2]" and lines[7] == "corner = (left + w - 1, top + h - 1)"
    assert lines[12] == "x = image[top:top + h, left:left + w]"
    assert [s.split("(")[0] for s in lines[13:]] == ["x = cv2.cvtColor", "x = cv2.resize", "x = x.astype",
                                                     "x = x.transpose", "x = x[None, ...]"]
    return lines


def _photo(d, x, y, cell, v, painted=False, numbers=False, bold=False):
    """8×12 사진 격자. 노란 테두리는 자를 영역, painted 면 preview 처럼 빨간 칸을 칠함."""
    _cells(d, x, y, 8, 12, cell, lambda r, c: RED if painted and v["painted"][r, c] else PIXEL)
    d.rectangle(_around(x, y, cell, v["top"], v["top"] + v["h"], v["left"], v["left"] + v["w"], 2), outline=YELLOW,
                width=4)
    if numbers:
        for c in range(12):
            _t(d, (x + c * cell + cell / 2, y - 14), c, 19, INK if bold else MUTED, bold, anchor="mm")
        for r in range(8):
            _t(d, (x - 20, y + r * cell + cell / 2), r, 19, INK if bold else MUTED, bold, anchor="mm")


@figure("a18a-1", 560, 300)
def a18a_flow():
    """입력 사진, 표준형 열여덟 줄과 줄 묶음 꼬리표, 줄마다 바뀐 shape."""
    v = _a18a()
    lines = _a18a_lines()
    _unit("al01", 6, 2, "읽기 결과")
    _unit("al01", 5, 2, "크기")
    _unit("al01", 7, 3, "좌표와 배열 인덱스")
    _unit("al01", 2, 4, "모델 조건")
    groups = [(0, 2, "읽기 확인 · 응용 1차시 여섯째 단원 2단계"),
              (3, 12, "영역 확인과 자르기 · 응용 1차시 다섯째 단원 2단계, 일곱째 단원 3단계"),
              (13, 17, "입력 만들기 · 응용 1차시 둘째 단원 4단계")]
    assert [k for a, b, _ in groups for k in range(a, b + 1)] == list(range(18))
    shapes = {0: (str(v["image"].shape), MUTED), 12: (str(v["x"].shape), BLUE), 14: (str(v["small"].shape), BLUE),
              15: ("float32", MUTED), 16: (str(v["moved"].shape), BLUE), 17: (str(v["batch"].shape), BLUE)}
    assert [shapes[k][0] for k in (0, 12, 14, 16, 17)] == ["(8, 12, 3)", "(4, 8, 3)", "(2, 4, 3)", "(3, 2, 4)",
                                                           "(1, 3, 2, 4)"]
    image, d = _new(600)
    code_x, size = 326, 19
    shape_x = code_x + max(_w(s, size, code=True) for s in lines) + 18
    _t(d, (20, 14), "입력", 22, INK, True)
    _t(d, (code_x - 34, 14), "코드", 22, INK, True)
    _t(d, (shape_x, 14), "결과 shape", 22, INK, True)
    cell = 20
    _photo(d, 20, 60, cell, v)
    _t(d, (20, 236), "image (8, 12, 3)", 19, code=True)
    _t(d, (20, 262), "uint8 · BGR", 19, MUTED)
    _photo(d, 20, 330, cell, v, painted=True)
    _t(d, (20, 506), "preview", 19, code=True)
    _t(d, (20, 532), "빨간 칸 %d개 · 아홉째 줄" % v["painted"].sum(), 19, MUTED)
    y = 54
    for a, b, label in groups:
        d.rounded_rectangle((code_x - 36, y, W - 12, y + 25), 8, fill=NOTE)
        _t(d, (code_x - 26, y + 13), label, 19, MUTED, True, anchor="lm")
        y += 29
        for k in range(a, b + 1):
            mid = y + 12
            if k in shapes and shapes[k][1] == BLUE:
                d.rectangle((code_x - 42, y + 1, code_x - 36, y + 23), fill=BLUE)
            _t(d, (code_x - 8, mid), k + 1, 19, LIGHT, code=True, anchor="rm")
            _t(d, (code_x, mid), lines[k], size, code=True, anchor="lm")
            if k in shapes:
                assert code_x + _w(lines[k], size, code=True) < shape_x - 10
                _t(d, (shape_x, mid), shapes[k][0], size, shapes[k][1], shapes[k][1] == BLUE, code=True, anchor="lm")
            y += 24
    assert y <= 586, y
    return image


A18A_2_MS = [2200, 2400, 2400, 2400, 2400, 2200]


@figure("a18a-2", 560, 280)
def a18a_region():
    """같은 영역을 점, 꼭짓점, 슬라이스로 적는 여섯 장."""
    v = _a18a()
    lines = _a18a_lines()
    gx, gy, cell = 80, 96, 44
    rx = 650
    frames = []
    for k in range(6):
        image, d = _new(560)
        label = {3: "preview", 5: "preview와 x"}.get(k, "image")
        _t(d, (gx - 40, 16), label, 22, INK, True, code=True)
        painted = k in (3, 5)
        _photo(d, gx, gy, cell, v, painted=painted, numbers=True, bold=k == 0)
        if k in (4, 5):
            for r in range(v["top"], v["top"] + v["h"]):
                for c in range(v["left"], v["left"] + v["w"]):
                    d.rectangle(_around(gx, gy, cell, r, r + 1, c, c + 1, -3), outline=GREEN, width=4)
        texts = []
        if k == 0:
            texts = [(lines[3], True, INK), None, ("rows = 8 · cols = 12", False, INK),
                     ("행 번호 0~7 · 열 번호 0~11", False, MUTED)]
        elif k == 1:
            yb = gy + (v["top"] + v["h"]) * cell
            xb = gx + (v["left"] + v["w"]) * cell
            _dash_line(d, (gx - 6, yb, gx + 12 * cell + 6, yb), INK, 3)
            _dash_line(d, (xb, gy - 4, xb, gy + 8 * cell + 6), INK, 3)
            _t(d, (gx + 6, yb + cell / 2), "top + h = 7", 19, INK, code=True, anchor="lm", bg="white")
            _t(d, (xb, gy + 8 * cell + 12), "left + w = 10", 19, INK, code=True, anchor="ma")
            texts = [(lines[4], True, INK), None, ("7 > 8 → False", True, INK), ("10 > 12 → False", True, INK),
                     ("검사를 통과합니다", False, INK)]
        elif k == 2:
            for (px, py), name, dy in (((v["left"], v["top"]), "(2, 3)", -1), (v["corner"], "corner (9, 6)", 1)):
                cx, cy = gx + px * cell + cell / 2, gy + py * cell + cell / 2
                d.ellipse((cx - 15, cy - 15, cx + 15, cy + 15), outline=INK, width=4)
                _t(d, (cx, cy + dy * cell), name, 19, INK, True, code=True, anchor="mm", bg="white")
            texts = [("왼쪽 위 점 (left, top) = (2, 3)", False, INK), None, (lines[7], True, INK),
                     ("= (2 + 8 - 1, 3 + 4 - 1)", True, INK), ("= (9, 6)", True, INK)]
        elif k == 3:
            cut = lines[8].index(" corner") + 1
            texts = [(lines[8][:cut], True, INK), ("              " + lines[8][cut:].strip(), True, INK), None,
                     ("corner = (9, 6)", True, INK), ("빨간 칸 %d개" % v["painted"].sum(), False, RED)]
            _photo(d, rx, 400, 10, v)
            _t(d, (rx + 136, 420), "image", 19, INK, code=True)
            _t(d, (rx + 136, 448), "바뀌지 않습니다", 19, MUTED)
        elif k == 4:
            end = v["top"] + v["h"]
            _dash(d, _around(gx, gy, cell, end, end + 1, v["left"], v["left"] + v["w"] + 1, -4), MUTED, 3)
            _dash(d, _around(gx, gy, cell, v["top"], end, v["left"] + v["w"], v["left"] + v["w"] + 1, -4), MUTED, 3)
            texts = [(lines[12], True, INK), ("x = image[3:7, 2:10]", True, INK), None,
                     ("행 3~6 · 열 2~9", False, GREEN), ("점선 칸은 끝 위치 7행과 10열", False, MUTED),
                     ("슬라이스는 점선 칸을 고르지 않습니다", False, MUTED)]
        else:
            texts = [("x.shape = %s" % (v["x"].shape,), True, INK), None, ("행 4개 × 열 8개", False, INK),
                     ("빨간 칸 %d개 · 초록 칸 %d개" % (v["painted"].sum(), v["x"].shape[0] * v["x"].shape[1]), False, INK),
                     ("빨간 칸과 초록 칸이 같은 자리입니다", False, INK)]
        y = 96
        for item in texts:
            if item is None:
                y += 16
                continue
            value, code, color = item
            _t(d, (rx, y), value, 21, color, code=code)
            y += 38
        frames.append(image)
    return frames, A18A_2_MS


def _layers(d, x, y, rows, cols, cell, depth=3, step=12):
    """(rows, cols, depth) 배열을 칸 격자 depth 겹으로 그림. 맨 앞 격자의 상자를 돌려줌."""
    for k in reversed(range(depth)):
        ox, oy = x + k * step, y - k * step
        _cells(d, ox, oy, rows, cols, cell, lambda r, c: "white" if k == 0 else NOTE, LIGHT, 2)
    return (x, y, x + cols * cell, y + rows * cell)


A18A_3_MS = [2200, 2400, 2400, 2400, 2400, 2200]


@figure("a18a-3", 560, 280)
def a18a_pixel():
    """한 픽셀의 값과 배열 모양이 입력을 만드는 다섯 줄을 지나며 바뀌는 여섯 장."""
    v = _a18a()
    lines = _a18a_lines()
    bgr = v["x"][0, 0].tolist()
    rgb = v["small"][0, 0].tolist()
    unit = [round(float(c), 1) for c in v["moved"][:, 0, 0]]
    assert bgr == [0, 51, 255] and rgb == [255, 51, 0] and unit == [1.0, 0.2, 0.0]
    tone = {"R": (RED, RED_L), "G": (GREEN, GREEN_L), "B": (BLUE, BLUE_L)}
    ordinals = ["열셋째", "열넷째", "열다섯째", "열여섯째", "열일곱째", "열여덟째"]
    results = ["BGR [0, 51, 255]", "RGB [255, 51, 0]", "너비 4 · 높이 2", "[1.0, 0.2, 0.0]", "채널 축이 맨 앞",
               "맨 앞에 N = 1"]
    shapes = [str(v["x"].shape), str(v["x"].shape), str(v["small"].shape), str(v["small"].shape),
              str(v["moved"].shape), str(v["batch"].shape)]
    assert shapes == ["(4, 8, 3)", "(4, 8, 3)", "(2, 4, 3)", "(2, 4, 3)", "(3, 2, 4)", "(1, 3, 2, 4)"]
    frames = []
    for k in range(6):
        image, d = _new(560)
        dtype = "uint8" if k < 3 else "float32"
        _t(d, (40, 30), "한 픽셀", 22, INK, True)
        _t(d, (140, 30), dtype, 22, INK, True, code=True)
        names = "BGR" if k == 0 else "RGB"
        values = bgr if k == 0 else (rgb if k < 3 else unit)
        if k < 4:
            for i, (name, value) in enumerate(zip(names, values)):
                x0, y0 = 40 + i * 98, 210
                line, fill = tone[name]
                d.rectangle((x0, y0, x0 + 84, y0 + 84), fill=fill, outline=line, width=5)
                _t(d, (x0 + 42, y0 + 42), value, 24, INK, True, code=True, anchor="mm")
                _t(d, (x0 + 42, y0 + 112), "%d번 %s" % (i, name), 19, line, True, anchor="mm")
            if k == 1:
                a, b = 40 + 42, 40 + 2 * 98 + 42
                d.line((a, 196, a, 170, b, 170, b, 196), fill=INK, width=3)
                for px in (a, b):
                    d.polygon([(px, 206), (px - 8, 192), (px + 8, 192)], fill=INK)
                _t(d, ((a + b) / 2, 150), "0번과 2번을 맞바꿈", 19, INK, anchor="mm")
        else:
            for i, (name, value) in enumerate(zip(names, values)):
                x0, y0 = 130, 150 + i * 100
                line, fill = tone[name]
                d.rectangle((x0, y0, x0 + 84, y0 + 84), fill=fill, outline=line, width=5)
                _t(d, (x0 + 42, y0 + 42), value, 24, INK, True, code=True, anchor="mm")
                _t(d, (40, y0 + 42), "%d번 %s" % (i, name), 19, line, True, anchor="lm")
        _t(d, (370, 150), "%s 줄" % ordinals[k], 21, MUTED, True)
        _t(d, (370, 196), lines[12 + k], 21, INK, code=True)
        arrow(d, (370, 270), (440, 270), INK, 4)
        _t(d, (456, 270), results[k], 22, INK, True, anchor="lm")
        if k == 2:
            _t(d, (456, 310), "픽셀 값은 %s" % rgb, 21, MUTED, anchor="lm")
        if k < 4:
            rows, cols = (4, 8) if k < 2 else (2, 4)
            box = _layers(d, 800, 250, rows, cols, 30)
        else:
            for i, name in enumerate("RGB"):
                line, fill = tone[name]
                y0 = 180 + i * 84
                _cells(d, 800, y0, 2, 4, 30, lambda r, c: fill, line, 2)
                _t(d, (935, y0 + 30), "%d번 %s %s" % (i, name, unit[i]), 19, line, True, anchor="lm")
            box = (800, 180, 920, 180 + 2 * 84 + 60)
            if k == 5:
                d.rounded_rectangle((784, 164, 1092, box[3] + 16), 14, outline=INK, width=3)
                _t(d, (790, 130), "N = 1", 21, INK, True, code=True)
        _t(d, (800, 446), shapes[k], 24, MUTED, True, code=True)
        _t(d, (800, 482), dtype, 21, MUTED, code=True)
        frames.append(image)
    return frames, A18A_3_MS


@figure("a18a-4", 560, 180)
def a18a_compare():
    """같은 영역을 네 곳에 적은 값. 왼쪽 격자에 거꾸로 적은 슬라이스 범위, 오른쪽 표에 바른 값과 거꾸로 적은 값.
    왼쪽 위 점은 두 코드가 같아 오른쪽 칸을 회색으로 둠."""
    v = _a18a()
    flipped = _lines("S101", "두 값을 거꾸로 적은 코드")
    assert flipped[3] == "cols, rows = image.shape[:2]" and flipped[7] == "corner = (top + h - 1, left + w - 1)"
    assert flipped[12] == "x = image[left:left + w, top:top + h]"
    point = (v["left"], v["top"])
    rows = [
        (["점 (x, y)"], [str(point)], [str(point), "두 코드가 같음"], (GREEN, MUTED)),
        (["꼭짓점"], [str(v["corner"])], [str(v["corner"][::-1])], (GREEN, RED)),
        (["슬라이스", "[행, 열]"], ["image[3:7, 2:10]", "→ %s" % (v["x"].shape,)],
         ["image[2:10, 3:7]", "→ %s" % (v["flipped"].shape,)], (GREEN, RED)),
        (["크기와 shape", "두 표기 비교"], ["resize (4, 2)", "너비 · 높이"], ["shape %s" % (v["small"].shape,), "높이 · 너비 · 채널"],
         (MUTED, MUTED)),
    ]
    assert flipped[8] == "cv2.rectangle(preview, (left, top), corner, (0, 0, 255), -1)"
    assert rows[0][2][0] == "(2, 3)" and rows[1][2] == ["(6, 9)"] and rows[2][2][1] == "→ (6, 4, 3)"
    assert rows[2][1][1] == "→ (4, 8, 3)" and rows[3][2][0] == "shape (2, 4, 3)"
    image, d = _new(360)
    gx, gy, cell = 66, 64, 26
    _photo(d, gx, gy, cell, v)
    end = min(v["left"] + v["w"], 8)
    _dash(d, _around(gx, gy, cell, v["left"], end, v["top"], v["top"] + v["h"], 3), RED, 4, 8)
    arrow(d, (gx, 34), (gx + 12 * cell + 16, 34), ORANGE, 4)
    _t(d, (gx + 12 * cell + 26, 34), "x", 22, ORANGE, True, anchor="lm")
    arrow(d, (34, gy), (34, gy + 8 * cell + 16), PURPLE, 4)
    _t(d, (34, gy + 8 * cell + 26), "y", 22, PURPLE, True, anchor="mt")
    _t(d, (gx + 30, gy + 8 * cell + 22), "높이 8 · 너비 12", 19, MUTED)
    cols = [(436, "무엇", INK), (612, "바르게 적은 값", GREEN), (858, "거꾸로 적은 값", RED)]
    for x, name, color in cols:
        _t(d, (x, 18), name, 21, color, True)
    y = 56
    for first, good, bad, (c1, c2) in rows:
        d.line((424, y, W - 14, y), fill=LINE, width=2)
        for (x, _, _), cell_lines, color in ((cols[0], first, INK), (cols[1], good, c1), (cols[2], bad, c2)):
            for i, s in enumerate(cell_lines):
                mid = y + 37 + (i - (len(cell_lines) - 1) / 2) * 26
                code = x != cols[0][0] and not re.search("[가-힣]", s)
                _t(d, (x, mid), s, 20, color if code else (MUTED if i else color), code and color != MUTED, code=code,
                   anchor="lm")
            assert _w(max(cell_lines, key=len), 20, code=True) < 240
        y += 74
    assert y <= 352, y
    return image


@figure("a18a-5", 560, 240)
def a18a_summary():
    """외울 것 요약. 상자 셋과 두 값을 거꾸로 적은 세 줄의 결과."""
    v = _a18a()
    lines = _a18a_lines()
    flipped = _lines("S101", "두 값을 거꾸로 적은 코드")
    image, d = _new(480)
    _t(d, (24, 16), "사진 한 장을 잘라 모델 입력으로 바꾸기", 24, INK, True)
    _panel(d, (24, 62, 350, 336), "영역 확인", YELLOW, [
        (lines[3], True, INK), None, ("꼭짓점", False, INK), ("(left + w - 1, top + h - 1)", True, INK),
        ("= %s" % (v["corner"],), True, INK), None, ("복사본 preview에 칠하기", False, INK)])
    _panel(d, (362, 62, 650, 336), "자르기", GREEN, [
        ("image[top:top + h,", True, INK), ("      left:left + w]", True, INK), ("= image[3:7, 2:10]", True, INK),
        None, ("결과 %s" % (v["x"].shape,), True, INK), None, ("끝 위치는 고르지 않음", False, INK)])
    rgb = v["small"][0, 0].tolist()
    unit = [round(float(c), 1) for c in v["moved"][:, 0, 0]]
    _panel(d, (662, 62, 1096, 336), "입력 만들기", BLUE, [
        ("cvtColor → %s" % rgb, True, INK), ("resize (4, 2) → %s" % (v["small"].shape,), True, INK),
        ('astype("float32") / 255.0', True, INK), ("  → %s" % unit, True, INK),
        ("transpose(2, 0, 1) → %s" % (v["moved"].shape,), True, INK),
        ("x[None, ...] → %s" % (v["batch"].shape,), True, INK)])
    _t(d, (24, 352), "두 값을 거꾸로 적으면", 21, RED, True)
    wrong = [(flipped[3], "검사 오류"), (flipped[7], "꼭짓점 %s" % (v["corner"][::-1],)),
             (flipped[12], "shape %s" % (v["flipped"].shape,))]
    assert [b for _, b in wrong] == ["검사 오류", "꼭짓점 (6, 9)", "shape (6, 4, 3)"]
    x = 16
    for i, (code, result) in enumerate(wrong):
        width = [298, 378, 388][i]
        d.rounded_rectangle((x, 386, x + width, 464), 12, fill=RED_L)
        assert _w(code, 19, code=True) <= width - 16, code
        _t(d, (x + 8, 398), code, 19, INK, code=True)
        _t(d, (x + 8, 430), "→ " + result, 19, RED, True)
        x += width + 6
    assert x - 6 <= W - 16
    return image


# a18b 펼친 영상에서 정한 색 범위만 남기기

A18B_H = [[20, 20, 20, 20, 20, 20, 20, 20],
          [20, 60, 60, 60, 60, 20, 20, 20],
          [20, 60, 60, 60, 60, 20, 20, 20],
          [20, 60, 60, 60, 60, 20, 70, 20],
          [20, 20, 20, 20, 20, 20, 20, 20],
          [20, 20, 60, 20, 20, 20, 20, 20]]


def _morph(mask, erode):
    """값이 모두 1인 3×3 kernel 로 침식이나 팽창. 영상 밖은 침식에서 255, 팽창에서 0 으로 봄(OpenCV 기본 경계)."""
    padded = np.pad(mask, 1, constant_values=255 if erode else 0)
    stack = np.stack([padded[dy:dy + mask.shape[0], dx:dx + mask.shape[1]] for dy in range(3) for dx in range(3)])
    return (stack.min(0) if erode else stack.max(0)).astype(np.uint8)


def _a18b():
    hue = np.array(A18B_H)
    sat = np.full(hue.shape, 200)
    sat[5, 2] = 30
    val = np.full(hue.shape, 200)
    in_h = (40 <= hue) & (hue <= 80)
    assert in_h.sum() == 14
    inside = in_h & (60 <= sat) & (sat <= 255) & (60 <= val) & (val <= 255)
    mask = np.where(inside, 255, 0).astype(np.uint8)
    assert (mask == 255).sum() == 13 and mask[3, 6] == 255 and mask[5, 2] == 0
    eroded = _morph(mask, True)
    assert [(int(x), int(y)) for y, x in zip(*np.nonzero(eroded))] == [(2, 2), (3, 2)]
    opened = _morph(eroded, False)
    assert (opened == 255).sum() == 12 and opened[1:4, 1:5].all() and opened[3, 6] == 0
    ys, xs = np.nonzero(opened)
    assert ys.tolist() == [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3] and xs.tolist() == [1, 2, 3, 4] * 3
    left, right, top, bottom = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    assert (left, right, top, bottom) == (1, 4, 1, 3)
    # 8비트 HSV 의 H 는 도를 2로 나눈 값
    flat = np.zeros(hue.shape + (3,), np.uint8)
    for y in range(hue.shape[0]):
        for x in range(hue.shape[1]):
            r, g, b = colorsys.hsv_to_rgb(hue[y, x] * 2 / 360.0, sat[y, x] / 255.0, val[y, x] / 255.0)
            flat[y, x] = [round(b * 255), round(g * 255), round(r * 255)]
    kept = np.where(opened[..., None] > 0, flat, 0)
    patch = kept[top:bottom + 1, left:right + 1]
    assert patch.shape == (3, 4, 3)
    raw_ys, raw_xs = np.nonzero(mask)
    raw_right = int(raw_xs.max())
    assert raw_right == 6 and kept[top:bottom + 1, left:raw_right + 1].shape == (3, 6, 3)
    green = tuple(int(c) for c in flat[1, 1])
    assert green == (43, 200, 43) and len({tuple(flat[y, x]) for y, x in zip(ys, xs)}) == 1
    return dict(hue=hue, sat=sat, in_h=in_h, mask=mask, eroded=eroded, opened=opened, ys=ys, xs=xs, left=left,
                right=right, top=top, bottom=bottom, flat=flat, kept=kept, patch=patch, raw_right=raw_right, green=green)


def _a18b_lines(variant="표준형"):
    lines = _lines("S102", variant)
    assert len(lines) == 13
    starts = ["target", "M =", "flat", "hsv", "mask = cv2.inRange", "mask = cv2.morphologyEx", "kept", "ys, xs",
              "if len", "    raise", "left, right", "top, bottom", "patch"]
    assert all(s.startswith(p) for s, p in zip(lines, starts)), lines
    return lines


def _hex(bgr):
    return "#%02x%02x%02x" % (bgr[2], bgr[1], bgr[0])


def _paper(d, x, y, w, h, bars=True, dot=True, bg=None, ink=GREEN):
    """펼친 종이 한 장. 초록 글씨 막대 둘과 떨어진 점 하나."""
    if bg:
        d.rectangle((x, y, x + w, y + h), fill=bg)
    if bars:
        d.rounded_rectangle((x + w * 0.16, y + h * 0.28, x + w * 0.62, y + h * 0.40), 5, fill=ink)
        d.rounded_rectangle((x + w * 0.16, y + h * 0.52, x + w * 0.52, y + h * 0.64), 5, fill=ink)
    if dot:
        d.ellipse((x + w * 0.80 - 5, y + h * 0.58 - 5, x + w * 0.80 + 5, y + h * 0.58 + 5), fill=ink)


@figure("a18b-1", 560, 280)
def a18b_flow():
    """비스듬한 종이 사진 → 펼친 영상 → 마스크와 남긴 영상 → patch. 화살표마다 맡은 줄과 배운 곳."""
    lines = _a18b_lines()
    _unit("al02", 5, None, "대응점으로 펼치기")
    _unit("al02", 3, None, "출력 크기")
    _unit("al01", 4, 2, "inRange")
    _unit("al02", 2, None, "MORPH_OPEN")
    _unit("al01", 3, 4, "마스크로 남길 위치")
    dsize = tuple(int(n) for n in re.search(r"\((\d+), (\d+)\)\)", lines[2]).groups())
    assert dsize == (240, 160) and dsize[0] * 2 == dsize[1] * 3
    steps = [((0, 2), "첫째~셋째 줄", [["응용 2차시 다섯째 단원", "대응점으로 펼치기"], ["응용 2차시 셋째 단원", "출력 크기"]]),
             ((3, 6), "넷째~일곱째 줄", [["응용 1차시 넷째 단원", "HSV와 inRange"], ["응용 2차시 둘째 단원", "열기"],
                                     ["응용 1차시 셋째 단원", "마스크로 남기기"]]),
             ((7, 12), "여덟째~열셋째 줄", [["이 단원 4단계", "행 번호와 열 번호"]])]
    assert [k for (a, b), _, _ in steps for k in range(a, b + 1)] == list(range(13))
    assert "warpPerspective" in lines[2] and "bitwise_and" in lines[6] and lines[12].startswith("patch")
    image, d = _new(560)
    pw, gap, top = 200, 86, 40
    xs = [30 + i * (pw + gap) for i in range(4)]
    for x in xs:
        d.rounded_rectangle((x, top, x + pw, top + 226), 14, fill=NOTE, outline=LIGHT, width=3)
    # 비스듬히 찍힌 종이
    x0 = xs[0]
    quad = [(x0 + 34, top + 46), (x0 + 168, top + 26), (x0 + 182, top + 150), (x0 + 22, top + 136)]
    d.rectangle((x0 + 12, top + 14, x0 + pw - 12, top + 172), fill=PIXEL)
    d.polygon(quad, fill="white", outline=LIGHT)

    def warp(u, w):
        a = (quad[0][0] + (quad[1][0] - quad[0][0]) * u, quad[0][1] + (quad[1][1] - quad[0][1]) * u)
        b = (quad[3][0] + (quad[2][0] - quad[3][0]) * u, quad[3][1] + (quad[2][1] - quad[3][1]) * u)
        return (a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w)

    for u0, u1, w0, w1 in ((0.16, 0.62, 0.28, 0.40), (0.16, 0.52, 0.52, 0.64)):
        d.polygon([warp(u0, w0), warp(u1, w0), warp(u1, w1), warp(u0, w1)], fill=GREEN)
    cx, cy = warp(0.80, 0.58)
    d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=GREEN)
    for (px, py), name, (dx, dy) in zip(quad, "ABCD", ((-14, -8), (8, -10), (8, 6), (-14, 6))):
        _t(d, (px + dx, py + dy), name, 19, ORANGE, True, anchor="mm")
    _t(d, (x0 + pw / 2, top + 200), "photo", 21, INK, True, code=True, anchor="mm")
    # 펼친 영상, 너비:높이 = 3:2
    x1 = xs[1]
    fw, fh = 144, 96
    assert fw * dsize[1] == fh * dsize[0]
    fx, fy = x1 + (pw - fw) / 2, top + 36
    d.rectangle((fx, fy, fx + fw, fy + fh), fill="white", outline=LIGHT, width=2)
    _paper(d, fx, fy, fw, fh)
    for (px, py), name in zip(((fx, fy), (fx + fw, fy), (fx + fw, fy + fh), (fx, fy + fh)), "ABCD"):
        _t(d, (px + (-14 if px == fx else 14), py + (-12 if py == fy else 12)), name, 19, ORANGE, True, anchor="mm")
    _t(d, (x1 + pw / 2, top + 176), "flat", 21, INK, True, code=True, anchor="mm")
    _t(d, (x1 + pw / 2, top + 206), "(160, 240, 3)", 19, MUTED, code=True, anchor="mm")
    # 마스크와 남긴 영상
    x2 = xs[2]
    for i, (name, ink) in enumerate((("mask", "white"), ("kept", GREEN))):
        my = top + 18 + i * 100
        _paper(d, x2 + 14, my, 105, 70, dot=False, bg=INK, ink=ink)
        _t(d, (x2 + 130, my + 35), name, 21, INK, True, code=True, anchor="lm")
    # patch: 막대 둘을 꼭 맞게 감쌈
    x3 = xs[3]
    bw, bh = 300, 200
    px0, py0 = x3 + (pw - 0.46 * bw) / 2, top + 50
    d.rectangle((px0, py0, px0 + 0.46 * bw, py0 + 0.36 * bh), fill=INK)
    _paper(d, px0 - 0.16 * bw, py0 - 0.28 * bh, bw, bh, dot=False, ink=GREEN)
    _t(d, (x3 + pw / 2, top + 176), "patch", 21, INK, True, code=True, anchor="mm")
    for i in range(3):
        a, b = xs[i] + pw + 8, xs[i + 1] - 8
        arrow(d, (a, top + 113), (b, top + 113), BLUE, 5)
        mid = (a + b) / 2
        _dash_line(d, (mid, top + 128, mid, 292), BLUE, 2, 6)
        (s, e), label, tags = steps[i]
        _t(d, (mid, 312), label, 21, BLUE, True, anchor="mm")
        y = 336
        for tag in tags:
            width = max(_w(t, 19) for t in tag) + 24
            y = _tag(d, mid - width / 2, y, tag, 19, width) + 8
        assert y <= 552, y
    return image


A18B_2_MS = [2400, 2400, 2200, 2400, 2400, 2200]


@figure("a18b-2", 560, 280)
def a18b_mask():
    """6×8 격자로 H 값, S 범위 밖 칸, inRange, 침식, 팽창, bitwise_and 를 한 장씩."""
    v = _a18b()
    lines = _a18b_lines()
    gx, gy, cell = 96, 92, 52
    rx = 560
    inrange = lines[4]
    cut = inrange.index(" (40")
    texts = [
        [(lines[3], True, INK), None, ("H가 40~80인 칸 %d개" % v["in_h"].sum(), False, GREEN),
         ("x=1~4, y=1~3의 12칸", False, INK), ("x=6, y=3 칸과 x=2, y=5 칸", False, INK)],
        [("x=2, y=5 칸: H 60 · S %d" % v["sat"][5, 2], False, INK), ("S 범위 60~255 밖", False, ORANGE), None,
         ("다른 칸의 S와 V는 200", False, INK)],
        [(inrange[:cut], True, INK), ("    " + inrange[cut + 1:], True, INK), None,
         ("255인 칸 %d개" % (v["mask"] == 255).sum(), False, INK)],
        [("kernel로 침식", False, INK), None, ("y=2 행의 x=2, x=3만 남음", False, INK),
         ("x=6, y=3의 점이 사라짐", False, INK), ("255인 칸 %d개" % (v["eroded"] == 255).sum(), False, INK)],
        [("이어서 팽창", False, INK), None, ("직사각형 12칸이 돌아옴", False, INK), ("사라진 점은 돌아오지 않음", False, INK),
         ("255인 칸 %d개" % (v["opened"] == 255).sum(), False, INK)],
        [(lines[6], True, INK), None, ("마스크가 255인 12칸은", False, INK),
         ("flat의 BGR %s 그대로" % (v["green"],), False, INK), ("나머지 칸은 0", False, INK)],
    ]
    assert [r[-1][0] for r in texts[2:5]] == ["255인 칸 13개", "255인 칸 2개", "255인 칸 12개"]
    frames = []
    for k in range(6):
        image, d = _new(560)
        before = {3: v["mask"], 4: v["eroded"]}.get(k)
        now = {2: v["mask"], 3: v["eroded"], 4: v["opened"]}.get(k)
        for y in range(6):
            for x in range(8):
                box = (gx + x * cell, gy + y * cell, gx + (x + 1) * cell, gy + (y + 1) * cell)
                c = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                if k < 2:
                    fill = (GREEN if k == 0 else GREEN_L) if v["in_h"][y, x] else "white"
                    d.rectangle(box, fill=fill, outline=LINE, width=2)
                    color = "white" if k == 0 and v["in_h"][y, x] else INK
                    if k == 1 and (x, y) == (2, 5):
                        _t(d, (c[0], c[1] - 10), v["hue"][y, x], 19, INK, True, code=True, anchor="mm")
                        _t(d, (c[0], c[1] + 12), "S30", 19, ORANGE, True, code=True, anchor="mm")
                    else:
                        _t(d, c, v["hue"][y, x], 20, color, k == 0, code=True, anchor="mm")
                elif k < 5:
                    on = now[y, x] == 255
                    d.rectangle(box, fill="white" if on else INK, outline=LIGHT, width=2)
                    _t(d, c, 255 if on else 0, 19, INK if on else LIGHT, code=True, anchor="mm")
                    if before is not None and before[y, x] != now[y, x]:
                        d.rectangle((box[0] + 3, box[1] + 3, box[2] - 3, box[3] - 3), outline=RED, width=4)
                else:
                    on = v["opened"][y, x] == 255
                    d.rectangle(box, fill=_hex(v["kept"][y, x]) if on else INK, outline=LIGHT, width=2)
                    if not on:
                        _t(d, c, 0, 19, LIGHT, code=True, anchor="mm")
        if k == 1:
            x, y = gx + 2 * cell, gy + 5 * cell
            _dash(d, (x + 3, y + 3, x + cell - 3, y + cell - 3), ORANGE, 3, 6)
        if k == 4:
            x, y = gx + 6 * cell + cell / 2, gy + 3 * cell + cell / 2
            for i in range(12):
                a = i * np.pi / 6
                d.arc((x - 20, y - 20, x + 20, y + 20), np.degrees(a), np.degrees(a) + 15, fill=LIGHT, width=3)
        for x in range(8):
            _t(d, (gx + x * cell + cell / 2, gy - 16), x, 19, MUTED, anchor="mm")
        for y in range(6):
            _t(d, (gx - 18, gy + y * cell + cell / 2), y, 19, MUTED, anchor="mm")
        _t(d, (gx + 8 * cell + 8, gy - 16), "x", 19, MUTED, True, anchor="lm")
        _t(d, (gx - 18, gy + 6 * cell + 16), "y", 19, MUTED, True, anchor="mm")
        title = ["H 값", "H 값과 S 값", "mask", "침식 뒤", "열기 뒤 mask", "kept"][k]
        _t(d, (gx - 40, 18), title, 22, INK, True, code=title in ("mask", "kept"))
        y = 96
        for item in texts[k]:
            if item is None:
                y += 14
                continue
            value, code, color = item
            _t(d, (rx, y), value, 21, color, code=code)
            y += 38
        frames.append(image)
    return frames, A18B_2_MS


@figure("a18b-3", 560, 280)
def a18b_bounds():
    """열기 뒤 마스크, np.nonzero 가 돌려준 번호와 네 값, 잘라 낸 patch."""
    v = _a18b()
    lines = _a18b_lines()
    _unit("l02", 2, 2, "행 번호와 열 번호")
    _unit("al01", 7, 3, "좌표와 배열 인덱스")
    assert lines[12] == "patch = kept[top:bottom + 1, left:right + 1]"
    image, d = _new(560)
    gx, gy, cell = 70, 70, 44
    for y in range(6):
        for x in range(8):
            on = v["opened"][y, x] == 255
            d.rectangle((gx + x * cell, gy + y * cell, gx + (x + 1) * cell, gy + (y + 1) * cell),
                        fill="white" if on else INK, outline=LIGHT, width=2)
    for x in range(8):
        _t(d, (gx + x * cell + cell / 2, gy - 16), x, 19, ORANGE, True, anchor="mm")
    for y in range(6):
        _t(d, (gx - 20, gy + y * cell + cell / 2), y, 19, BLUE, True, anchor="mm")
    dot = (gx + 6 * cell + cell / 2, gy + 3 * cell + cell / 2)
    d.ellipse((dot[0] - 9, dot[1] - 9, dot[0] + 9, dot[1] + 9), fill=LIGHT)
    d.rectangle(_around(gx, gy, cell, v["top"], v["bottom"] + 1, v["left"], v["right"] + 1, 3), outline=GREEN, width=4)
    _dash(d, _around(gx, gy, cell, v["top"], v["bottom"] + 1, v["left"], v["raw_right"] + 1, 9), RED, 3, 8)
    _t(d, (gx, gy + 6 * cell + 24), "회색 점은 열기로 지운 x=6, y=3", 19, MUTED)
    ys, xs = v["ys"].tolist(), v["xs"].tolist()
    mx = 470
    _t(d, (mx, 60), "ys, xs = np.nonzero(mask)", 20, INK, code=True)
    for i, (name, values, color) in enumerate((("ys", ys, BLUE), ("xs", xs, ORANGE))):
        y0 = 112 + i * 84
        head = "%s = [" % name
        first = ", ".join(str(n) for n in values[:6]) + ","
        second = ", ".join(str(n) for n in values[6:]) + "]"
        _t(d, (mx, y0), head + first, 20, color, True, code=True)
        _t(d, (mx + _w(head, 20, code=True), y0 + 30), second, 20, color, True, code=True)
        assert "[" + first + " " + second == str(values)
    _t(d, (mx, 290), "left %d · right %d" % (v["left"], v["right"]), 21, ORANGE, True, code=True)
    _t(d, (mx, 326), "top %d · bottom %d" % (v["top"], v["bottom"]), 21, BLUE, True, code=True)
    _tag(d, mx, 380, ["개론 2차시 둘째 단원", "행 번호와 열 번호"])
    rx = 820
    sliced = "kept[%d:%d, %d:%d]" % (v["top"], v["bottom"] + 1, v["left"], v["right"] + 1)
    assert sliced == "kept[1:4, 1:5]"
    _t(d, (rx, 60), sliced, 21, GREEN, True, code=True)
    green = _hex(v["green"])
    _cells(d, rx, 104, 3, 4, 36, lambda r, c: green, "white", 2)
    _t(d, (rx, 228), "shape %s" % (v["patch"].shape,), 21, INK, code=True)
    _t(d, (rx, 290), "열기 없이", 19, MUTED)
    raw = "kept[%d:%d, %d:%d]" % (v["top"], v["bottom"] + 1, v["left"], v["raw_right"] + 1)
    raw_shape = v["kept"][v["top"]:v["bottom"] + 1, v["left"]:v["raw_right"] + 1].shape
    assert raw == "kept[1:4, 1:7]" and raw_shape == (3, 6, 3)
    _t(d, (rx, 318), raw, 19, RED, code=True)
    _t(d, (rx, 346), "→ %s" % (raw_shape,), 19, RED, code=True)
    _tag(d, rx, 400, ["응용 1차시 일곱째 단원", "좌표와 배열 인덱스"])
    return image


def _corners(line):
    return [tuple(int(n) for n in p) for p in re.findall(r"\[(\d+), (\d+)\]", line)]


@figure("a18b-4", 560, 280)
def a18b_corners():
    """가로 출력과 세로 출력의 모서리 좌표, dsize, shape. 같은 축척으로 그림."""
    wide, tall = _a18b_lines("표준형"), _a18b_lines("세로로 펼친 코드")
    image, d = _new(560)
    scale = 1.4
    for x0, lines in ((110, wide), (690, tall)):
        corners = _corners(lines[0])
        dsize = tuple(int(n) for n in re.search(r"\((\d+), (\d+)\)\)", lines[2]).groups())
        width, height = dsize
        assert corners == [(0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1)]
        w, h = width * scale, height * scale
        assert abs(w / h - width / height) < 1e-9
        y0 = 110
        d.rectangle((x0, y0, x0 + w, y0 + h), fill=NOTE, outline=INK, width=3)
        arrow(d, (x0, y0 - 40), (x0 + 110, y0 - 40), INK, 3)
        _t(d, (x0 + 118, y0 - 40), "x", 20, INK, True, anchor="lm")
        arrow(d, (x0 - 40, y0), (x0 - 40, y0 + 100), INK, 3)
        _t(d, (x0 - 40, y0 + 108), "y", 20, INK, True, anchor="mt")
        spots = [((x0 - 6, y0 - 6), "rb"), ((x0 + w + 6, y0 - 6), "lb"), ((x0 + w + 6, y0 + h + 6), "lt"),
                 ((x0 - 6, y0 + h + 6), "rt")]
        inner = [(14, 12), (-14, 12), (-14, -12), (14, -12)]
        for (spot, anchor), point, name, (ix, iy) in zip(spots, corners, "ABCD", inner):
            _t(d, spot, str(point), 20, ORANGE, True, code=True, anchor=anchor)
            cx = x0 if ix > 0 else x0 + w
            cy = y0 if iy > 0 else y0 + h
            _t(d, (cx + ix, cy + iy), name, 19, MUTED, True, anchor="mm")
        shape = (height, width, 3)
        _t(d, (x0, y0 + h + 42), "dsize %s" % (dsize,), 21, ORANGE, True, code=True)
        _t(d, (x0, y0 + h + 74), "shape %s" % (shape,), 21, BLUE, True, code=True)
        assert ("(240, 160)", "(160, 240, 3)") == (str(dsize), str(shape)) or \
            ("(160, 240)", "(240, 160, 3)") == (str(dsize), str(shape))
    return image


@figure("a18b-5", 560, 210)
def a18b_summary():
    """외울 것 요약. (x, y)와 (너비, 높이), 마스크, [행, 열] 상자 셋."""
    v = _a18b()
    lines = _a18b_lines()
    corners = _corners(lines[0])
    image, d = _new(420)
    _t(d, (24, 16), "펼친 영상에서 정한 색 범위만 남기기", 24, INK, True)
    _panel(d, (24, 62, 384, 400), "(x, y)와 (너비, 높이)", ORANGE, [
        ("target 모서리", False, INK), ("%s, %s," % (corners[0], corners[1]), True, INK),
        ("%s, %s" % (corners[2], corners[3]), True, INK), None,
        ("getPerspectiveTransform(", True, INK), ("    corners, target)", True, INK), None,
        ("warpPerspective(photo, M,", True, INK), ("    (240, 160))", True, INK),
        ("→ (160, 240, 3)", True, ORANGE)])
    count = [(v["mask"] == 255).sum(), (v["opened"] == 255).sum()]
    assert count == [13, 12]
    _panel(d, (396, 62, 736, 400), "마스크", GREEN, [
        ("inRange(hsv, 하한, 상한)", True, INK), None, ("MORPH_OPEN · 열기", True, INK), None,
        ("bitwise_and(flat, flat,", True, INK), ("            mask=mask)", True, INK), None,
        ("격자의 255 칸", False, INK), ("%d개 → %d개" % tuple(count), False, GREEN)])
    _panel(d, (748, 62, 1096, 400), "[행, 열]", BLUE, [
        ("ys, xs = np.nonzero(mask)", True, INK), None, ("kept[top:bottom + 1,", True, INK),
        ("     left:right + 1]", True, INK), None, ("격자의 patch", False, INK),
        ("%s" % (v["patch"].shape,), True, BLUE)])
    return image


# a18c 프레임마다 물체의 중심을 원본 좌표로 기록하기
# 색: 초록 = roi·찾은 값, 노랑 = 행 범위, 파랑 = 열 범위, 주황 = 이 단원에서 설명하는 줄·더하는 시작 위치,
# 빨강 = 잘못된 값·이 영상에 맞지 않는 결과, 회색 = None·배운 곳 꼬리표, 보라 = 프레임마다 기록.

A18C_BOX = (119, 179, 43)        # 프레임 0 상자의 시작 열, 시작 행, 한 변
A18C_STICKER = (7, 7, 20)        # 상자 왼쪽 위에서 스티커까지 열·행 간격과 한 변
A18C_SHIFT = 48
BELT = "#1f2937"
FLOOR = "#e5e7eb"


def _a18c_frame(shift):
    """높이 360·너비 480 회색조 프레임. shift 가 None 이면 상자가 없음."""
    frame = np.full((360, 480), 150, np.uint8)
    frame[120:280] = 40
    if shift is not None:
        c, r, n = A18C_BOX
        c += shift
        frame[r:r + n, c:c + n] = 230
        dc, dr, m = A18C_STICKER
        frame[r + dr:r + dr + m, c + dc:c + dc + m] = 40
    return frame


def _poly_moments(points):
    """다각형 꼭짓점으로 m00, m10, m01 을 구함(cv2.moments 가 윤곽에 쓰는 그린 정리 식)."""
    a00 = a10 = a01 = 0
    for (xa, ya), (xb, yb) in zip(points, points[1:] + points[:1]):
        cross = xa * yb - xb * ya
        a00 += cross
        a10 += (xa + xb) * cross
        a01 += (ya + yb) * cross
    return abs(a00) / 2, abs(a10) / 6, abs(a01) / 6


def _a18c():
    y0, y1, x0, x1 = 120, 280, 80, 400
    frames = [_a18c_frame(0), _a18c_frame(A18C_SHIFT), _a18c_frame(None)]
    color = np.dstack([frames[0]] * 3)
    roi = color[y0:y1, x0:x1]
    assert roi.shape == (160, 320, 3)
    assert color[x0:x1, y0:y1].shape == (280, 160, 3)
    gray = frames[0][y0:y1, x0:x1]
    binary = np.where(gray > 200, 255, 0)
    inverse = np.where(gray > 200, 0, 255)
    ys, xs = np.nonzero(binary)
    c, r, n = A18C_BOX
    assert (xs.min() + x0, xs.max() + x0, ys.min() + y0, ys.max() + y0) == (c, c + n - 1, r, r + n - 1)
    assert (binary == 255).sum() == n * n - A18C_STICKER[2] ** 2 and (inverse == 255).sum() == 160 * 320 - (binary == 255).sum()
    # 흐린 뒤 기준 200 을 넘는 범위는 한 칸씩 줄어 roi 40~80열, 60~100행이 255 라고 봄(본문 그림 13 의 이진 영상)
    square = [(c - x0 + 1, r - y0 + 1), (c - x0 + n - 2, r - y0 + 1), (c - x0 + n - 2, r - y0 + n - 2),
              (c - x0 + 1, r - y0 + n - 2)]
    assert square == [(40, 60), (80, 60), (80, 100), (40, 100)]
    m00, m10, m01 = _poly_moments(square)
    assert (m00, m10, m01) == (1600, 96000, 128000)
    inside = (m10 / m00, m01 / m00)
    assert inside == (60, 80)
    center = (inside[0] + x0, inside[1] + y0)
    assert center == (140.0, 200.0)
    assert (inside[0], inside[1] + y0) == (60, 200) and (inside[0] + y0, inside[1] + x0) == (180, 160)
    moved = [(a + A18C_SHIFT, b) for a, b in square]
    m00b, m10b, m01b = _poly_moments(moved)
    assert (m00b, m10b, m01b) == (1600, 172800, 128000)
    center1 = (m10b / m00b + x0, m01b / m00b + y0)
    assert center1 == (188.0, 200.0)
    dc, dr, m = A18C_STICKER
    hole = [(c + dc - x0, r + dr - y0), (c + dc + m - 1 - x0, r + dr - y0), (c + dc + m - 1 - x0, r + dr + m - 1 - y0),
            (c + dc - x0, r + dr + m - 1 - y0)]
    hole_area = _poly_moments(hole)[0]
    # 흐리기로 구멍이 한 칸씩 넓어져도(한 변 21) 300 과 5000 사이
    assert 300 < hole_area < 5000 and 300 < 21 * 21 < 5000
    hole_center = ((hole[0][0] + hole[1][0]) / 2 + x0, (hole[0][1] + hole[2][1]) / 2 + y0)
    assert hole_center != center
    standard, missed = [], []
    last = None
    for found in (center, center1, None):
        standard.append(found)
        if found is not None:
            last = found
            missed.append(found)
    assert standard == [(140.0, 200.0), (188.0, 200.0), None] and missed == [(140.0, 200.0), (188.0, 200.0)]
    assert last == (188.0, 200.0)
    return dict(y0=y0, y1=y1, x0=x0, x1=x1, frames=frames, binary=binary, inverse=inverse, square=square,
                moments=(int(m00), int(m10), int(m01)), inside=inside, center=center, center1=center1, hole=hole,
                standard=standard, missed=missed)


def _a18c_lines(variant="표준형"):
    lines = _lines("S103", variant)
    assert len(lines) == 19
    if variant == "표준형":
        assert lines[6] == "    roi = frame[y0:y1, x0:x1]" and lines[12] == "    center = None"
        assert lines[16].strip().startswith("center = (M[\"m10\"] / M[\"m00\"] + x0")
        assert lines[17] == "    centers.append(center)"
    return lines


def _tint(image, box, color, alpha):
    """box 안을 color 와 alpha 비율로 섞음."""
    box = tuple(int(round(v)) for v in box)
    part = image.crop(box)
    image.paste(Image.blend(part, Image.new("RGB", part.size, color), alpha), box[:2])


def _belt(d, x, y, s, shift, outline=None):
    """프레임 한 장을 s 배로. 바닥, 벨트, 상자, 스티커를 프레임 배열과 같은 좌표로 그림."""
    d.rectangle((x, y, x + 480 * s, y + 360 * s), fill=FLOOR)
    d.rectangle((x, y + 120 * s, x + 480 * s, y + 280 * s), fill=BELT)
    if shift is not None:
        c, r, n = A18C_BOX
        c += shift
        d.rectangle((x + c * s, y + r * s, x + (c + n) * s, y + (r + n) * s), fill="white")
        dc, dr, m = A18C_STICKER
        d.rectangle((x + (c + dc) * s, y + (r + dr) * s, x + (c + dc + m) * s, y + (r + dr + m) * s), fill=BELT)
    if outline:
        d.rectangle((x + 80 * s, y + 120 * s, x + 400 * s, y + 280 * s), outline=outline, width=2)
    d.rectangle((x, y, x + 480 * s, y + 360 * s), outline=LIGHT, width=2)


def _a18c_scene_check(v, shift, frame):
    """_belt 가 그리는 상자 자리가 프레임 배열의 상자 자리와 같은지 봄."""
    ys, xs = np.nonzero(frame == 230)
    if shift is None:
        assert len(xs) == 0
        return
    c, r, n = A18C_BOX
    assert (xs.min(), xs.max(), ys.min(), ys.max()) == (c + shift, c + shift + n - 1, r, r + n - 1)


def _code_tags(d, x, y, row, lines, tags, size=19, tag_x=0):
    """코드 줄과 줄 오른쪽 꼬리표. tags 는 {줄 번호(0부터): [(글, 색)]}. 회색은 글자만, 주황은 옅은 바탕 상자."""
    ends = {}
    for k, line in enumerate(lines):
        mid = y + k * row + row / 2
        _t(d, (x - 8, mid), k + 1, size, LIGHT, code=True, anchor="rm")
        _t(d, (x, mid), line, size, code=True, anchor="lm")
        end = x + _w(line, size, code=True)
        ends[k] = end
        tx = max(end + 16, tag_x)
        for label, color in tags.get(k, []):
            if color == ORANGE:
                box = _t(d, (tx + 6, mid), label, size, ORANGE, True, anchor="lm")
                d.rounded_rectangle((box[0] - 6, mid - row / 2 + 1, box[2] + 6, mid + row / 2 - 1), 6, fill=ORANGE_L)
                _t(d, (tx + 6, mid), label, size, ORANGE, True, anchor="lm")
                tx = box[2] + 18
            else:
                box = _t(d, (tx, mid), label, size, MUTED, anchor="lm")
                tx = box[2] + 14
    return ends


@figure("a18c-1", 560, 300)
def a18c_flow():
    """입력 프레임 띠와 표준형 열아홉 줄, 줄마다 배운 곳 꼬리표, 비워 둔 결과 칸."""
    v = _a18c()
    lines = _a18c_lines()
    _unit("al03", 1, 2, "반복")
    _unit("al03", 1, 3, "성공 여부")
    _unit("al03", 5, 2, "필요한 영역")
    _unit("l02", 2, 2, "행 번호와 열 번호")
    _unit("al03", 3, 2, "(3, 3)")
    _unit("al03", 6, 2, "두 값으로 나누기")
    _unit("al03", 6, 4, "기준")
    _unit("al03", 6, 5, "구멍의 경계")
    _unit("al03", 5, 3, "중심")
    _unit("al03", 1, 5, "해제")
    _unit("l05", 7, 5, "기록한 손실")
    _unit("l01", 7, 3, "나눗셈")
    gray, orange = MUTED, ORANGE
    tags = {
        0: [("응용 3차시 첫째 단원 2단계", gray)], 2: [("응용 3차시 첫째 단원 2단계", gray)],
        3: [("응용 3차시 첫째 단원 3단계", gray)], 4: [("응용 3차시 첫째 단원 3단계", gray)],
        5: [("응용 3차시 첫째 단원 3단계", gray)], 7: [("응용 3차시 첫째 단원 3단계", gray)],
        6: [("응용 3차시 다섯째 단원 2단계", gray), ("개론 2차시 둘째 단원 2단계", gray)],
        8: [("응용 3차시 셋째 단원 2단계", gray)],
        9: [("응용 3차시 여섯째 단원 2·4단계", gray)],
        10: [("응용 3차시 여섯째 단원 5단계", gray)], 11: [("응용 3차시 여섯째 단원 5단계", gray)],
        14: [("응용 3차시 다섯째 단원 3단계", gray)], 18: [("응용 3차시 첫째 단원 5단계", gray)],
        1: [("5단계", orange), ("개론 5차시 일곱째 단원 5단계", gray)],
        12: [("5단계", orange), ("개론 5차시 일곱째 단원 5단계", gray)],
        17: [("5단계", orange), ("개론 5차시 일곱째 단원 5단계", gray)],
        13: [("4단계", orange)], 15: [("4단계", orange)],
        16: [("4단계", orange), ("개론 1차시 일곱째 단원 3단계", gray)],
    }
    image, d = _new(600)
    s = 0.25
    names = ["프레임 0", "프레임 1", "프레임 2", "넷째 읽기"]
    for i in range(4):
        x = 16 + i * 140
        if i < 3:
            shift = [0, A18C_SHIFT, None][i]
            _a18c_scene_check(v, shift, v["frames"][i])
            _belt(d, x, 10, s, shift, GREEN)
        else:
            d.rectangle((x, 10, x + 120, 100), fill="white", outline=LIGHT, width=2)
            d.line((x + 44, 18, x + 76, 50), fill=RED, width=4)
            d.line((x + 76, 18, x + 44, 50), fill=RED, width=4)
            _t(d, (x + 60, 76), "ok = False", 19, RED, True, code=True, anchor="mm")
        _t(d, (x + 60, 116), names[i], 19, INK, True, anchor="mm")
    lx = 600
    d.rectangle((lx, 18, lx + 30, 38), outline=GREEN, width=3)
    _t(d, (lx + 42, 28), "살필 영역 120~279행, 80~399열", 19, INK, anchor="lm")
    _t(d, (lx, 62), "회색 글자", 19, MUTED, True, anchor="lm")
    _t(d, (lx + 92, 62), "그 줄을 배운 노트 자리", 19, INK, anchor="lm")
    box = _t(d, (lx + 6, 96), "4단계", 19, ORANGE, True, anchor="lm")
    d.rounded_rectangle((box[0] - 6, 85, box[2] + 6, 107), 6, fill=ORANGE_L)
    _t(d, (lx + 6, 96), "4단계", 19, ORANGE, True, anchor="lm")
    _t(d, (box[2] + 18, 96), "이 단원에서 그 줄을 설명하는 단계", 19, INK, anchor="lm")
    top, row = 140, 22
    ends = _code_tags(d, 44, top, row, lines, tags, tag_x=500)
    assert top + 19 * row <= 594
    # 결과 칸은 비워 둠(짐작 문항 g1·g2 의 답을 가리지 않으려고)
    bx0, by0, bx1, by1 = 836, top + 17 * row + 4, 1104, 594
    assert 500 + _w("5단계", 19, True) + 30 + _w("개론 5차시 일곱째 단원 5단계", 19) < bx0 - 6
    d.rounded_rectangle((bx0, by0, bx1, by1), 12, fill=NOTE, outline=PURPLE, width=3)
    _t(d, (bx0 + 16, by0 + 20), "centers = [ ?, ?, ? ]", 21, PURPLE, True, code=True, anchor="lm")
    _t(d, (bx0 + 16, by0 + 50), "4·5단계에서 채웁니다", 19, MUTED, anchor="lm")
    return image


A18C_2_MS = [2200, 2400, 2400, 2400, 2400]


def _binary_panel(d, x, y, s, values, outline):
    """roi 크기(160×320)의 0·255 배열을 s 배로. 255 는 흰색, 0 은 진회색."""
    d.rectangle((x, y, x + 320 * s, y + 160 * s), fill=BELT if values[0, 0] == 0 else "white")
    other = "white" if values[0, 0] == 0 else BELT
    rows = np.nonzero((values != values[0, 0]).any(axis=1))[0]
    for r in rows:
        cols = np.nonzero(values[r] != values[0, 0])[0]
        # 한 행에서 이어진 칸 묶음마다 사각형 하나
        runs = np.split(cols, np.nonzero(np.diff(cols) != 1)[0] + 1)
        for run in runs:
            d.rectangle((x + run[0] * s, y + r * s, x + (run[-1] + 1) * s - 1, y + (r + 1) * s - 1), fill=other)
    d.rectangle((x, y, x + 320 * s, y + 160 * s), outline=outline, width=4)


@figure("a18c-2", 560, 300)
def a18c_slice():
    """frame 을 40픽셀 격자로 놓고 행 범위, 열 범위, roi, THRESH_BINARY, THRESH_BINARY_INV 를 한 장씩."""
    v = _a18c()
    lines = _a18c_lines()
    gx, gy, s = 90, 96, 1
    rx = 620
    texts = [
        [("frame.shape = (360, 480, 3)", True, INK), None, ("한 칸은 40픽셀", False, INK),
         ("x는 오른쪽, y는 아래쪽으로 커집니다", False, MUTED)],
        [("frame[120:280, 80:400]", True, INK), None, ("첫째 자리 120:280", True, INK),
         ("120행부터 279행까지 160행", False, INK)],
        [(lines[6].strip(), True, INK), None, ("둘째 자리 80:400", True, INK), ("80열부터 399열까지 320열", False, INK),
         ("roi.shape = (160, 320, 3)", True, GREEN)],
        [("THRESH_BINARY, 기준 200", True, INK), ("밝기 > 200 → 255", False, INK), None,
         ("상자는 255, 벨트는 0", False, INK), ("스티커 자리는 구멍", False, MUTED)],
        [("THRESH_BINARY_INV, 기준 200", True, RED), ("어두운 쪽이 255", False, RED), None,
         ("벨트가 255, 상자가 0", False, INK), ("밝은 상자에는 맞지 않습니다", False, RED)],
    ]
    rows_sel = v["y1"] - v["y0"]
    cols_sel = v["x1"] - v["x0"]
    assert (rows_sel, cols_sel) == (160, 320)
    frames = []
    for k in range(5):
        image, d = _new(600)
        _belt(d, gx, gy, s, 0)
        for c in range(1, 12):
            d.line((gx + c * 40, gy, gx + c * 40, gy + 360), fill=LIGHT, width=1)
        for r in range(1, 9):
            d.line((gx, gy + r * 40, gx + 480, gy + r * 40), fill=LIGHT, width=1)
        # 벨트가 행 범위와 같은 자리라 노랑은 테두리로, 파랑은 벨트 밖 바닥에만 옅게 칠함
        if k == 2:
            _tint(image, (gx + v["x0"], gy, gx + v["x1"], gy + v["y0"]), BLUE, 0.3)
            _tint(image, (gx + v["x0"], gy + v["y1"], gx + v["x1"], gy + 360), BLUE, 0.3)
        d = ImageDraw.Draw(image)
        d.rectangle((gx, gy, gx + 480, gy + 360), outline=MUTED, width=2)
        if k in (1, 2):
            d.rectangle((gx, gy + v["y0"], gx + 480, gy + v["y1"]), outline=YELLOW, width=6)
        if k == 2:
            d.rectangle((gx + v["x0"], gy, gx + v["x1"], gy + 360), outline=BLUE, width=4)
        if k >= 2:
            d.rectangle((gx + v["x0"], gy + v["y0"], gx + v["x1"], gy + v["y1"]), outline=GREEN, width=6)
        arrow(d, (gx, gy - 40), (gx + 520, gy - 40), INK, 3)
        _t(d, (gx + 530, gy - 40), "x", 21, INK, True, anchor="lm")
        arrow(d, (gx - 56, gy), (gx - 56, gy + 400), INK, 3)
        _t(d, (gx - 56, gy + 410), "y", 21, INK, True, anchor="mt")
        for value in (0, 80, 400, 480):
            color = BLUE if k >= 2 and value in (80, 400) else MUTED
            _t(d, (gx + value, gy - 16), value, 19, color, color == BLUE, anchor="mm")
        for value in (0, 120, 280, 360):
            color = INK if k >= 1 and value in (120, 280) else MUTED
            _t(d, (gx - 10, gy + value), value, 19, color, color == INK, anchor="rm")
        if k >= 1:
            d.rectangle((gx + 488, gy + v["y0"], gx + 498, gy + v["y1"]), fill=YELLOW)
        if k >= 2:
            d.rectangle((gx + v["x0"], gy + 368, gx + v["x1"], gy + 378), fill=BLUE)
        y = 96
        for item in texts[k]:
            if item is None:
                y += 14
                continue
            value, code, color = item
            _t(d, (rx, y), value, 21, color, code=code)
            y += 36
        if k >= 3:
            values = v["binary"] if k == 3 else v["inverse"]
            _binary_panel(d, rx, 330, 1.4, values, GREEN if k == 3 else RED)
            _t(d, (rx, 330 + 224 + 14), "roi를 1.4배로", 19, MUTED)
        frames.append(image)
    return frames, A18C_2_MS


@figure("a18c-3", 560, 280)
def a18c_offset():
    """이진 영상의 roi 안 중심 (60, 80)에 시작 열과 시작 행을 더해 원본 (140, 200)으로 옮기기."""
    v = _a18c()
    image, d = _new(560)
    ox, oy, s = 130, 60, 1.25
    x0, y0 = v["x0"], v["y0"]

    def at(x, y):
        return ox + x * s, oy + y * s

    d.rectangle((*at(0, 0), *at(480, 360)), fill=FLOOR)
    d.rectangle((*at(0, 120), *at(480, 280)), fill=BELT)
    (sx0, sy0), (sx1, sy1) = v["square"][0], v["square"][2]
    d.rectangle((*at(x0 + sx0, y0 + sy0), *at(x0 + sx1, y0 + sy1)), fill="white")
    hole = v["hole"]
    hx0, hy0, hx1, hy1 = hole[0][0], hole[0][1], hole[2][0], hole[2][1]
    d.rectangle((*at(x0 + hx0, y0 + hy0), *at(x0 + hx1, y0 + hy1)), fill=BELT)
    a, b = at(x0 + hx0, y0 + hy0), at(x0 + hx1, y0 + hy1)
    _dash(d, (a[0] - 5, a[1] - 5, b[0] + 5, b[1] + 5), LIGHT, 3, 5)
    d.rectangle((*at(x0, y0), *at(v["x1"], v["y1"])), outline=GREEN, width=4)
    d.rectangle((*at(0, 0), *at(480, 360)), outline=MUTED, width=2)
    # 원본의 좌표축
    d.line((ox, oy, ox + 630, oy), fill=INK, width=3)
    arrow(d, (ox + 600, oy), (ox + 640, oy), INK, 3)
    _t(d, (ox + 648, oy), "x", 21, INK, True, anchor="lm")
    d.line((ox, oy, ox, oy + 480), fill=INK, width=3)
    arrow(d, (ox, oy + 450), (ox, oy + 488), INK, 3)
    _t(d, (ox - 12, oy + 480), "y", 21, INK, True, anchor="rm")
    _t(d, (ox - 8, oy - 8), "원본 (0, 0)", 19, INK, True, anchor="rb")
    # 더하는 시작 위치
    arrow(d, (ox, oy - 26), (ox + x0 * s, oy - 26), ORANGE, 4)
    _t(d, (ox + x0 * s + 8, oy - 26), "x0 = 80", 19, ORANGE, True, code=True, anchor="lm")
    arrow(d, (ox - 26, oy), (ox - 26, oy + y0 * s), ORANGE, 4)
    _t(d, (ox - 34, oy + y0 * s), "y0 = 120", 19, ORANGE, True, code=True, anchor="rm")
    # roi 안의 좌표축과 중심까지의 거리
    rx, ry = at(x0, y0)
    arrow(d, (rx, ry), (rx + 40, ry), GREEN, 3)
    arrow(d, (rx, ry), (rx, ry + 40), GREEN, 3)
    _t(d, (rx - 8, ry - 8), "roi (0, 0)", 19, GREEN, True, anchor="rb")
    cx, cy = v["inside"]
    _dash_line(d, (rx, ry + 4, rx + cx * s, ry + 4), GREEN, 3, 5)
    _dash_line(d, (rx + cx * s, ry, rx + cx * s, ry + cy * s), GREEN, 3, 5)
    _t(d, (rx + cx * s / 2, ry - 16), "%d" % cx, 21, GREEN, True, anchor="mm")
    _t(d, (rx + cx * s - 10, ry + cy * s / 2 - 8), "%d" % cy, 21, GREEN, True, anchor="rm", bg="white")
    px, py = at(*v["center"])
    d.ellipse((px - 7, py - 7, px + 7, py + 7), fill=ORANGE, outline="white", width=2)
    label = "(60 + 80, 80 + 120) = (140, 200)"
    assert label == "(%d + %d, %d + %d) = (%d, %d)" % (cx, x0, cy, y0, v["center"][0], v["center"][1])
    floor_y = oy + 300 * s
    d.line((px, py + 8, px, floor_y - 4), fill=ORANGE, width=2)
    _t(d, (px - 24, floor_y), label, 19, ORANGE, True, code=True, anchor="lt")
    wrong = [((cx, cy + y0), "(60, 200)"), ((cx + y0, cy + x0), "(180, 160)")]
    for (wx, wy), name in wrong:
        qx, qy = at(wx, wy)
        d.ellipse((qx - 7, qy - 7, qx + 7, qy + 7), fill=RED, outline="white", width=2)
    qx, qy = at(*wrong[0][0])
    d.line((qx, qy + 8, qx, floor_y - 4), fill=RED, width=2)
    _t(d, (qx, floor_y), wrong[0][1], 19, RED, True, code=True, anchor="mt")
    qx, qy = at(*wrong[1][0])
    _t(d, (qx + 12, qy), wrong[1][1], 19, RED, True, code=True, anchor="lm", bg="white")
    # 오른쪽 설명
    tx = 800
    m00, m10, m01 = v["moments"]
    _t(d, (tx, 30), "상자 바깥 윤곽의 모멘트", 21, INK, True)
    for i, (name, value) in enumerate((("m00", m00), ("m10", m10), ("m01", m01))):
        _t(d, (tx, 72 + i * 30), name, 19, MUTED, code=True)
        _t(d, (tx + 70, 72 + i * 30), "%d" % value, 19, INK, True, code=True)
    _t(d, (tx, 172), "%d ÷ %d = %d" % (m10, m00, cx), 19, GREEN, True, code=True)
    _t(d, (tx, 202), "%d ÷ %d = %d" % (m01, m00, cy), 19, GREEN, True, code=True)
    _dash(d, (tx, 262, tx + 26, 288), LIGHT, 3, 5)
    _t(d, (tx + 38, 275), "스티커 구멍", 19, INK, True, anchor="lm")
    _t(d, (tx, 300), "구멍 경계의 면적도 300과 5000 사이", 19, INK)
    _t(d, (tx, 328), "RETR_EXTERNAL은 찾지 않음", 19, INK)
    _t(d, (tx, 392), "잘못 옮긴 위치", 21, RED, True)
    _t(d, (tx, 430), "(60, 200)", 19, RED, True, code=True)
    _t(d, (tx + 110, 430), "x에 더하지 않음", 19, INK)
    _t(d, (tx, 462), "(180, 160)", 19, RED, True, code=True)
    _t(d, (tx + 110, 462), "x0와 y0를 바꿔 더함", 19, INK)
    return image


A18C_4_MS = [2200, 2400, 2400, 2500, 2400]


def _slot(d, x, y, value, w=196, h=56):
    """centers 의 한 칸. 찾은 값은 초록, None 은 회색."""
    if value is None:
        d.rounded_rectangle((x, y, x + w, y + h), 10, fill=NOTE, outline=LIGHT, width=3)
        _t(d, (x + w / 2, y + h / 2), "None", 21, MUTED, True, code=True, anchor="mm")
    else:
        d.rounded_rectangle((x, y, x + w, y + h), 10, fill=GREEN_L, outline=GREEN, width=3)
        _t(d, (x + w / 2, y + h / 2), "(%.1f, %.1f)" % value, 20, GREEN, True, code=True, anchor="mm")


@figure("a18c-4", 560, 280)
def a18c_record():
    """표준형과 기록을 놓친 코드에서 프레임마다 centers 에 쌓이는 칸."""
    v = _a18c()
    missed = _a18c_lines("기록을 놓친 코드")
    assert missed[2] == "center = None" and missed[17] == "            centers.append(center)"
    std, miss = v["standard"], v["missed"]
    frames = []
    shown = [None, 0, 1, 2, "fail"]
    heads = ["반복 앞", "프레임 0", "프레임 1", "프레임 2", "넷째 읽기"]
    for k in range(5):
        image, d = _new(560)
        tx, ty = 20, 60
        _t(d, (tx, 22), "지금 읽는 프레임", 21, INK, True)
        if shown[k] is None:
            d.rectangle((tx, ty, tx + 240, ty + 180), fill="white", outline=LIGHT, width=2)
            _t(d, (tx + 120, ty + 90), "아직 읽지 않음", 19, MUTED, anchor="mm")
        elif shown[k] == "fail":
            d.rectangle((tx, ty, tx + 240, ty + 180), fill="white", outline=LIGHT, width=2)
            d.line((tx + 80, ty + 50, tx + 160, ty + 130), fill=RED, width=5)
            d.line((tx + 160, ty + 50, tx + 80, ty + 130), fill=RED, width=5)
        else:
            shift = [0, A18C_SHIFT, None][shown[k]]
            _a18c_scene_check(v, shift, v["frames"][shown[k]])
            _belt(d, tx, ty, 0.5, shift, GREEN)
        _t(d, (tx + 120, ty + 204), heads[k], 21, INK, True, anchor="mm")
        if k == 4:
            _t(d, (tx + 120, ty + 240), "ok = False → break", 19, RED, True, code=True, anchor="mm")
        n = min(k, 3)
        rows = [("표준형", std[:n], 60), ("center = None이 while 앞, append가 if 안", miss[:min(k, 2)], 300)]
        for r, (title, cells, y) in enumerate(rows):
            _t(d, (320, y - 8), title, 21, PURPLE if r == 0 else INK, True, anchor="lb")
            _t(d, (320, y + 30), "centers =", 20, INK, code=True, anchor="lm")
            x = 440
            if not cells:
                _t(d, (x, y + 30), "[]", 21, INK, True, code=True, anchor="lm")
            for i, value in enumerate(cells):
                _slot(d, x + i * 206, y + 2, value)
            note, color = None, INK
            if r == 0 and 1 <= k <= 3:
                value = std[k - 1]
                note = "center = None" if value is None else "center = (%.1f, %.1f)" % value
                color = MUTED if value is None else GREEN
            if r == 1:
                if k == 0:
                    note, color = "center = None (한 번)", MUTED
                elif k in (1, 2):
                    note, color = "center = (%.1f, %.1f)" % miss[k - 1], GREEN
                elif k == 3:
                    note, color = "center = (%.1f, %.1f)" % miss[-1], RED
            if note:
                box = _t(d, (440, y + 84), note, 19, color, True, code=True, anchor="lm")
                if r == 1 and k == 3:
                    _t(d, (box[2] + 16, y + 84), "칸을 넣지 않습니다", 19, RED, True, anchor="lm")
            if k == 4:
                count = "%d칸" % len(cells)
                _t(d, (1100, y - 8), count, 26, PURPLE if r == 0 else RED, True, anchor="rb")
        if k >= 3:
            assert len(std[:3]) == 3 and std[2] is None and len(miss) == 2
        frames.append(image)
    return frames, A18C_4_MS


@figure("a18c-5", 560, 240)
def a18c_summary():
    """외울 것 요약. 영역 자르기, 원본 좌표로 옮기기, 프레임마다 기록하기."""
    v = _a18c()
    lines = _a18c_lines()
    image, d = _new(480)
    _t(d, (24, 16), "프레임마다 물체의 중심을 원본 좌표로 기록하기", 24, INK, True)
    _panel(d, (24, 62, 384, 368), "영역 자르기", GREEN, [
        ("frame[y0:y1, x0:x1]", True, INK), ("= frame[120:280, 80:400]", True, INK), ("→ (160, 320, 3)", True, GREEN),
        None, ("순서를 바꾸면", False, RED), ("frame[x0:x1, y0:y1]", True, INK), ("→ (280, 160, 3)", True, RED), None,
        ("행 범위 먼저, 열 범위 다음", False, INK)])
    cx, cy = v["inside"]
    _panel(d, (396, 62, 736, 368), "원본 좌표로 옮기기", ORANGE, [
        ("M[\"m10\"] / M[\"m00\"] + x0", True, INK), ("M[\"m01\"] / M[\"m00\"] + y0", True, INK), None,
        ("roi 안 (%d, %d)" % (cx, cy), False, INK), ("→ 원본 (%d, %d)" % v["center"], False, ORANGE), None,
        ("x에는 시작 열, y에는 시작 행", False, INK)])
    std = v["standard"]
    _panel(d, (748, 62, 1096, 368), "프레임마다 기록하기", PURPLE, [
        ("while 안, for 앞", False, MUTED), (lines[12].strip(), True, INK), None, ("for 뒤, while 안", False, MUTED),
        (lines[17].strip(), True, INK), None, ("[(%.1f, %.1f)," % std[0], True, PURPLE),
        (" (%.1f, %.1f)," % std[1], True, PURPLE), (" None]", True, PURPLE)])
    d.rounded_rectangle((24, 382, 1096, 464), 14, fill=NOTE)
    _t(d, (44, 406), "밝은 물체를 255로", 21, INK, True, anchor="lm")
    _t(d, (300, 406), "cv2.THRESH_BINARY", 21, INK, True, code=True, anchor="lm")
    _t(d, (44, 442), "어두운 물체를 255로", 21, INK, True, anchor="lm")
    _t(d, (300, 442), "cv2.THRESH_BINARY_INV", 21, INK, True, code=True, anchor="lm")
    assert "cv2.THRESH_BINARY)" in lines[9]
    return image


# a18d 성공한 점만 골라 변위를 구하고 다음 프레임으로 넘기기
# 색: 파랑 = 이전 좌표·old_gray·0번 축, 주황 = 현재 좌표·gray·1번 축, 회색 = status 가 0 인 행,
# 초록 = True 인 행·다음 호출에 넘기는 점, 빨강 = 고르지 않아 섞인 값.

A18D_PREV = [(40, 30), (100, 30), (70, 80), (120, 90)]
A18D_NEXT = [(43, 28), (104, 29), (15, 140), (122, 87)]
A18D_STATUS = [1, 1, 0, 1]


def _a18d():
    prev = np.array(A18D_PREV, np.float32).reshape(-1, 1, 2)
    nxt = np.array(A18D_NEXT, np.float32).reshape(-1, 1, 2)
    status = np.array(A18D_STATUS, np.uint8).reshape(-1, 1)
    assert prev.shape == nxt.shape == (4, 1, 2) and status.shape == (4, 1) and status.dtype == np.uint8
    flat = status.ravel()
    keep = flat == 1
    assert flat.tolist() == [1, 1, 0, 1] and keep.tolist() == [True, True, False, True]
    assert prev[keep].shape == (3, 1, 2) and nxt[keep].shape == (3, 1, 2)
    old_ok, new_ok = prev[keep].reshape(-1, 2), nxt[keep].reshape(-1, 2)
    assert old_ok.tolist() == [[40, 30], [100, 30], [120, 90]] and new_ok.tolist() == [[43, 28], [104, 29], [122, 87]]
    moves = new_ok - old_ok
    assert moves.tolist() == [[3, -2], [4, -1], [2, -3]]
    mean0, mean1, mean_all = moves.mean(axis=0), moves.mean(axis=1), moves.mean()
    assert mean0.tolist() == [3, -2] and mean0.shape == (2,)
    assert mean1.tolist() == [0.5, 1.5, -0.5] and mean1.shape == (3,) and mean_all == 0.5
    raw = (nxt - prev).reshape(-1, 2)
    assert raw.tolist() == [[3, -2], [4, -1], [-55, 60], [2, -3]] and raw.mean(axis=0).tolist() == [-11.5, 13.5]
    following = new_ok.reshape(-1, 1, 2)
    assert following.shape == (3, 1, 2)
    # status 를 그대로 넣으면 0 과 1 을 점 번호로 읽음
    assert prev[status].reshape(-1, 2).tolist() == [[100, 30], [100, 30], [40, 30], [100, 30]]
    assert prev[status == 1].shape == (3, 2)
    return dict(prev=prev, nxt=nxt, status=status, keep=keep, old_ok=old_ok, new_ok=new_ok, moves=moves,
                mean0=mean0, mean1=mean1, mean_all=mean_all, raw=raw, following=following)


def _a18d_lines():
    lines = _lines("S104", "표준형")
    assert len(lines) == 13
    assert lines[2] == "keep = status.ravel() == 1" and lines[7] == "    shifts.append(moves.mean(axis=0))"
    assert lines[12] == "old_gray = gray.copy()"
    return lines


def _n(value):
    """정수로 떨어지는 실수는 정수로 적음."""
    value = float(value)
    return str(int(value)) if value == int(value) else str(value)


def _pt(p):
    return "(%s, %s)" % (_n(p[0]), _n(p[1]))


def _points(d, x, y, s, pts, color, r=6, ring=False, labels=None):
    for i, p in enumerate(pts):
        px, py = x + p[0] * s, y + p[1] * s
        if ring:
            d.ellipse((px - r, py - r, px + r, py + r), outline=color, width=3)
        else:
            d.ellipse((px - r, py - r, px + r, py + r), fill=color)
        if labels:
            _t(d, (px + 9, py - 12), labels[i], 19, color, True, anchor="lm")


@figure("a18d-1", 560, 300)
def a18d_flow():
    """입력 점 네 개와 표, 표준형 열세 줄과 줄 꼬리표, shifts 에 넣은 값과 다음 prev_pts."""
    v = _a18d()
    lines = _a18d_lines()
    _unit("al04", 5, 3, "코드로")
    _unit("l02", 2, 4, "마스크로 행")
    _unit("l02", 4, 2, "같은 자리")
    _unit("l02", 5, 3, "axis")
    _unit("l02", 3, 3, "-1 자리")
    _unit("al03", 7, 3, "점 사이 거리")
    _unit("l01", 3, 4, "copy()")
    _unit("al01", 7, 3, "좌표와 배열 인덱스")
    image, d = _new(600)
    # 입력
    _t(d, (16, 8), "입력", 22, INK, True)
    ix, iy, s = 16, 44, 0.75
    d.rectangle((ix, iy, ix + 320 * s, iy + 240 * s), fill=NOTE, outline=LIGHT, width=2)
    _t(d, (ix + 320 * s - 6, iy + 240 * s - 6), "320×240", 19, MUTED, anchor="rd")
    kept = [p for p, k in zip(A18D_NEXT, A18D_STATUS) if k]
    _points(d, ix, iy, s, A18D_PREV, BLUE, 5)
    _points(d, ix, iy, s, kept, ORANGE, 8, ring=True)
    _points(d, ix, iy, s, [A18D_NEXT[2]], LIGHT, 7, ring=True)
    for i, p in enumerate(A18D_PREV):
        _t(d, (ix + p[0] * s - 9, iy + p[1] * s - 6), "%d" % i, 19, INK, True, anchor="rb")
    _t(d, (ix + 15 * s + 12, iy + 140 * s), "2번 점의 현재 좌표", 19, MUTED, anchor="lm")
    _t(d, (ix, iy + 240 * s + 6), "응용 1차시 일곱째 단원 3단계", 19, MUTED)
    cols = [(276, "번호", INK, False), (336, "prev_pts", BLUE, True), (446, "next_pts", ORANGE, True),
            (556, "status", INK, True)]
    for x, name, color, code in cols:
        _t(d, (x, 44), name, 19, color, True, code=code)
    for i in range(4):
        y = 74 + i * 30
        off = A18D_STATUS[i] == 0
        if off:
            d.rectangle((270, y - 3, 640, y + 25), fill=LINE)
        tone = MUTED if off else None
        _t(d, (276, y), "%d" % i, 19, tone or INK, True)
        _t(d, (336, y), _pt(A18D_PREV[i]), 19, tone or BLUE, code=True)
        _t(d, (446, y), _pt(A18D_NEXT[i]), 19, tone or ORANGE, code=True)
        _t(d, (556, y), "%d" % A18D_STATUS[i], 19, tone or INK, True, code=True)
    assert 556 + _w("status", 19, True) < 640
    # 결과
    rx = 700
    _t(d, (rx, 8), "결과", 22, INK, True)
    d.rounded_rectangle((rx, 44, 1104, 96), 12, fill="white", outline=ORANGE, width=3)
    _t(d, (rx + 16, 70), "shifts에 넣은 값", 19, INK, anchor="lm")
    _t(d, (rx + 190, 70), "[%s, %s]" % tuple(_n(c) for c in v["mean0"]), 22, ORANGE, True, code=True, anchor="lm")
    d.rounded_rectangle((rx, 108, 1104, 228), 12, fill="white", outline=GREEN, width=3)
    _t(d, (rx + 16, 130), "다음 prev_pts %s" % (v["following"].shape,), 19, INK, anchor="lm")
    for i, p in enumerate(v["following"].reshape(-1, 2)):
        _t(d, (rx + 16, 160 + i * 24), _pt(p), 19, GREEN, True, code=True, anchor="lm")
    mx, my, ms = 960, 124, 0.42
    d.rectangle((mx, my, mx + 320 * ms, my + 240 * ms), fill=NOTE, outline=LIGHT, width=2)
    _points(d, mx, my, ms, v["following"].reshape(-1, 2), GREEN, 5)
    # 코드
    top, row = 292, 23
    _t(d, (16, top - 6), "코드", 22, INK, True, anchor="lb")
    shade = [(2, 4, GREEN_L), (6, 7, ORANGE_L), (8, 12, BLUE_L)]
    for a, b, color in shade:
        d.rectangle((44, top + a * row, 626, top + (b + 1) * row), fill=color)
    tags = {0: "응용 4차시 다섯째 단원 3단계", 2: "개론 2차시 둘째 단원 4단계", 6: "개론 2차시 넷째 단원 2단계",
            7: "개론 2차시 다섯째 단원 3단계", 8: "개론 2차시 셋째 단원 3단계", 11: "응용 3차시 일곱째 단원 3단계",
            12: "개론 1차시 셋째 단원 4단계"}
    for k, line in enumerate(lines):
        mid = top + k * row + row / 2
        _t(d, (40, mid), k + 1, 19, LIGHT, code=True, anchor="rm")
        _t(d, (48, mid), line, 19, code=True, anchor="lm")
        assert 48 + _w(line, 19, code=True) < 626
        if k in tags:
            _t(d, (640, mid + (row / 2 if k == 0 else 0)), tags[k], 19, MUTED, anchor="lm")
    d.line((634, top + 4, 634, top + 2 * row - 4), fill=LIGHT, width=2)
    assert top + 13 * row <= 594
    arrow(d, (460, 196), (460, top - 8), INK, 4)
    arrow(d, (900, top + 2), (900, 234), INK, 4)
    return image


A18D_2_MS = [2200, 2400, 2400, 2400]


@figure("a18d-2", 560, 280)
def a18d_keep():
    """status 를 펴서 keep 을 만들고, 같은 keep 으로 prev_pts 와 next_pts 를 고르는 네 장."""
    v = _a18d()
    frames = []
    px, nx = 520, 820
    for k in range(4):
        image, d = _new(560)
        if k == 0:
            _t(d, (60, 70), "status", 21, INK, True, code=True)
            for i, value in enumerate(A18D_STATUS):
                y = 110 + i * 64
                d.rectangle((60, y, 140, y + 54), fill="white", outline=INK, width=2)
                _t(d, (100, y + 27), "[%d]" % value, 21, INK, True, code=True, anchor="mm")
        else:
            _t(d, (40, 70), "status.ravel()", 21, INK, True, code=True)
            for i, value in enumerate(v["status"].ravel()):
                d.rectangle((40 + i * 92, 110, 124 + i * 92, 164), fill="white", outline=INK, width=2)
                _t(d, (82 + i * 92, 137), "%d" % value, 21, INK, True, code=True, anchor="mm")
            _t(d, (40, 200), "keep = ... == 1", 21, INK, True, code=True)
            for i, value in enumerate(v["keep"]):
                fill, ink = (GREEN_L, GREEN) if value else (LINE, MUTED)
                d.rectangle((40 + i * 92, 240, 124 + i * 92, 294), fill=fill, outline=ink, width=3)
                _t(d, (82 + i * 92, 267), str(bool(value)), 19, ink, True, code=True, anchor="mm")
        names = ("prev_pts", "next_pts") if k < 3 else ("old_ok", "new_ok")
        for x, name, color, data in ((px, names[0], BLUE, A18D_PREV), (nx, names[1], ORANGE, A18D_NEXT)):
            _t(d, (x, 70), name, 21, color, True, code=True)
            if k < 3:
                for i, p in enumerate(data):
                    y = 110 + i * 64
                    off = k == 2 and not v["keep"][i]
                    d.rectangle((x, y, x + 200, y + 54), fill=LINE if off else "white", outline=LIGHT if off else color,
                                width=2)
                    text = "[[%d, %d]]" % p
                    _t(d, (x + 100, y + 27), text, 21, LIGHT if off else color, True, code=True, anchor="mm")
                    if off:
                        d.line((x + 20, y + 27, x + 180, y + 27), fill=MUTED, width=3)
            else:
                rows = (v["old_ok"] if name == "old_ok" else v["new_ok"]).tolist()
                for i, p in enumerate(rows):
                    y = 110 + i * 64
                    d.rectangle((x, y, x + 200, y + 54), fill="white", outline=color, width=2)
                    _t(d, (x + 100, y + 27), "[%s, %s]" % (_n(p[0]), _n(p[1])), 21, color, True, code=True, anchor="mm")
        for i in range(4):
            y = 110 + i * 64 + 27
            if k == 0:
                _t(d, (px - 14, y), "%d" % i, 19, MUTED, anchor="rm")
            elif k in (1, 2):
                on = v["keep"][i]
                d.rectangle((px - 34, y - 10, px - 14, y + 10), fill=GREEN if on else LIGHT)
                if k == 2 and on:
                    _t(d, (px - 44, y), "%d번" % i, 19, GREEN, True, anchor="rm")
        if k == 3:
            for i, n in enumerate(np.nonzero(v["keep"])[0]):
                y = 110 + i * 64 + 27
                _t(d, (px - 14, y), "%d번" % n, 19, GREEN, True, anchor="rm")
                d.line((px + 200, y, nx, y), fill=GREEN, width=3)
        shapes = [
            "status (4, 1) · prev_pts (4, 1, 2) · next_pts (4, 1, 2)",
            "keep = [True, True, False, True]",
            "prev_pts[keep] %s · next_pts[keep] %s" % (v["prev"][v["keep"]].shape, v["nxt"][v["keep"]].shape),
            "old_ok %s · new_ok %s · 같은 번호의 행이 같은 점" % (v["old_ok"].shape, v["new_ok"].shape),
        ]
        assert shapes[2] == "prev_pts[keep] (3, 1, 2) · next_pts[keep] (3, 1, 2)"
        assert shapes[3].startswith("old_ok (3, 2) · new_ok (3, 2)")
        assert v["keep"].tolist() == [True, True, False, True]
        d.rounded_rectangle((40, 440, 1080, 500), 12, fill=NOTE)
        _t(d, (60, 470), shapes[k], 21, INK, True, anchor="lm")
        frames.append(image)
    return frames, A18D_2_MS


@figure("a18d-3", 560, 280)
def a18d_mean():
    """moves 격자와 axis 에 따른 평균, 고르지 않고 뺀 값."""
    v = _a18d()
    image, d = _new(560)
    gx, gy, cw, ch = 220, 140, 90, 60
    _t(d, (gx, 30), "개론 2차시 넷째 단원 2단계", 19, MUTED)
    _t(d, (gx, 70), "moves", 22, INK, True, code=True)
    for j, name in enumerate(("dx", "dy")):
        _t(d, (gx + j * cw + cw / 2, gy - 16), name, 21, INK, True, code=True, anchor="mm")
    _t(d, (gx + 2 * cw + 30, 76), "응용 4차시 다섯째 단원 2단계", 19, MUTED)
    _t(d, (gx + 2 * cw + 30, 104), "dx > 0 오른쪽, dy > 0 아래쪽", 19, MUTED)
    moves = v["moves"].tolist()
    for i, (n, row) in enumerate(zip((0, 1, 3), moves)):
        _t(d, (gx - 14, gy + i * ch + ch / 2), "%d번 점" % n, 19, INK, True, anchor="rm")
        for j, value in enumerate(row):
            d.rectangle((gx + j * cw, gy + i * ch, gx + (j + 1) * cw, gy + (i + 1) * ch), fill="white", outline=INK,
                        width=2)
            _t(d, (gx + j * cw + cw / 2, gy + i * ch + ch / 2), _n(value), 22, INK, True, code=True, anchor="mm")
    bottom, right = gy + 3 * ch, gx + 2 * cw
    _t(d, (right + 8, bottom + 18), "mean() = %s" % _n(v["mean_all"]), 19, INK, True, code=True)
    arrow(d, (gx + cw, bottom + 8), (gx + cw, bottom + 64), BLUE, 5)
    m0 = "[%s, %s]" % tuple(_n(c) for c in v["mean0"])
    _t(d, (gx - 120, bottom + 84), "mean(axis=0) = %s" % m0, 21, BLUE, True, code=True)
    _t(d, (gx - 120, bottom + 116), "shape %s" % (v["mean0"].shape,), 19, BLUE, code=True)
    col = list(zip(*moves))
    calc0 = "(%s + %s + %s) ÷ 3 = %s" % (tuple(_n(c) for c in col[0]) + (_n(v["mean0"][0]),))
    calc1 = "(%s %s %s) ÷ 3 = %s" % (_n(col[1][0]), "- %s" % _n(-col[1][1]), "- %s" % _n(-col[1][2]), _n(v["mean0"][1]))
    assert calc0 == "(3 + 4 + 2) ÷ 3 = 3" and calc1 == "(-2 - 1 - 3) ÷ 3 = -2"
    _t(d, (gx - 120, bottom + 156), calc0, 19, INK, code=True)
    _t(d, (gx - 120, bottom + 186), calc1, 19, INK, code=True)
    arrow(d, (right + 8, gy + ch * 1.5), (right + 70, gy + ch * 1.5), ORANGE, 5)
    m1 = "[%s]" % ", ".join(_n(c) for c in v["mean1"])
    assert m1 == "[0.5, 1.5, -0.5]"
    _t(d, (right + 82, gy + ch * 1.5 - 16), "mean(axis=1) = %s" % m1, 21, ORANGE, True, code=True, anchor="lm")
    _t(d, (right + 82, gy + ch * 1.5 + 16), "shape %s" % (v["mean1"].shape,), 19, ORANGE, code=True, anchor="lm")
    # 고르지 않고 뺀 값
    bx, by = 640, 300
    d.rounded_rectangle((bx, by, 1104, 548), 14, fill="white", outline=RED, width=3)
    _t(d, (bx + 16, by + 14), "고르지 않고 next_pts - prev_pts를 구하면", 19, RED, True)
    raw = v["raw"].tolist()
    sx, sy, sw, sh = bx + 110, by + 56, 72, 40
    for i, row in enumerate(raw):
        bad = A18D_STATUS[i] == 0
        _t(d, (sx - 12, sy + i * sh + sh / 2), "%d번 점" % i, 19, RED if bad else INK, bad, anchor="rm")
        for j, value in enumerate(row):
            d.rectangle((sx + j * sw, sy + i * sh, sx + (j + 1) * sw, sy + (i + 1) * sh), fill=RED_L if bad else "white",
                        outline=RED if bad else LIGHT, width=2)
            _t(d, (sx + j * sw + sw / 2, sy + i * sh + sh / 2), _n(value), 20, RED if bad else INK, bad, code=True,
               anchor="mm")
    mean_raw = v["raw"].mean(axis=0)
    _t(d, (sx + 2 * sw + 24, sy + 2 * sh - 14), "평균", 19, RED, True, anchor="lm")
    _t(d, (sx + 2 * sw + 24, sy + 2 * sh + 14), "(%s, %s)" % (_n(mean_raw[0]), _n(mean_raw[1])), 21, RED, True,
       code=True, anchor="lm")
    return image


A18D_4_MS = [2200, 2400, 2400, 2500]


@figure("a18d-4", 560, 280)
def a18d_handoff():
    """프레임 t-1, t, t+1, t+2 띠를 따라 old_gray 와 prev_pts 가 넘어가는 네 장."""
    v = _a18d()
    lines = _a18d_lines()
    s, cw, ch = 0.625, 200, 150
    xs = [30 + i * 270 for i in range(4)]
    ty = 70
    names = ["t-1", "t", "t+1", "t+2"]
    old_at = [0, 0, 1, 2]
    gray_at = [1, 1, 2, 2]
    kept = v["new_ok"].tolist()
    # t+1 에서 성공한 점이 둘뿐인 경우와 gray 에서 다시 찾은 점. 값은 찍지 않음
    two = [(47, 27), (126, 85)]
    found = [(30, 60), (90, 110), (160, 70), (220, 150), (270, 40), (200, 200), (60, 180)]
    frames = []
    for k in range(4):
        image, d = _new(560)
        for i, x in enumerate(xs):
            d.rectangle((x, ty, x + cw, ty + ch), fill=NOTE, outline=LIGHT, width=2)
            _t(d, (x + cw / 2, ty - 22), "프레임 %s" % names[i], 21, INK, True, anchor="mm")
        if k == 0:
            _points(d, xs[0], ty, s, A18D_PREV, BLUE, 6)
        if k in (1, 2):
            _points(d, xs[1], ty, s, kept, GREEN, 6)
            qx, qy = xs[1] + A18D_NEXT[2][0] * s, ty + A18D_NEXT[2][1] * s
            d.line((qx - 7, qy - 7, qx + 7, qy + 7), fill=LIGHT, width=4)
            d.line((qx + 7, qy - 7, qx - 7, qy + 7), fill=LIGHT, width=4)
        if k == 3:
            _points(d, xs[2], ty, s, two, GREEN, 6)
            for p in found:
                cx, cy = xs[2] + p[0] * s, ty + p[1] * s
                star = [(cx + (8 if j % 2 == 0 else 3.5) * np.cos(np.pi / 2 + j * np.pi / 5),
                         cy - (8 if j % 2 == 0 else 3.5) * np.sin(np.pi / 2 + j * np.pi / 5)) for j in range(10)]
                d.polygon(star, fill=GREEN)
        for at, color, name, dy in ((old_at[k], BLUE, "old_gray", 0), (gray_at[k], ORANGE, "gray", 30)):
            x = xs[at]
            pad = 6 if color == BLUE else 12
            d.rectangle((x - pad, ty - pad, x + cw + pad, ty + ch + pad), outline=color, width=5)
            _t(d, (x + cw / 2, ty + ch + 30 + dy), name, 21, color, True, code=True, anchor="mm")
        if k == 3:
            _t(d, (xs[2] + cw / 2, ty + ch + 92), "다른 경우: 성공한 점 2개, 별은 다시 찾은 점", 19, MUTED, True, anchor="mm")
        # 아래 상자
        shifts = ["[]", "[[3, -2]]", "[[3, -2]]", "[[3, -2], None]"][k]
        assert "[[%s, %s]]" % tuple(_n(c) for c in v["mean0"]) == "[[3, -2]]"
        d.rounded_rectangle((30, 360, 520, 450), 12, fill="white", outline=INK, width=2)
        _t(d, (50, 386), "shifts", 21, INK, True, code=True, anchor="lm")
        _t(d, (50, 422), shifts, 22, ORANGE if k else INK, True, code=True, anchor="lm")
        d.rounded_rectangle((540, 360, 1090, 450), 12, fill="white", outline=GREEN if k else BLUE, width=2)
        _t(d, (560, 386), "prev_pts", 21, INK, True, code=True, anchor="lm")
        if k == 0:
            _t(d, (560, 422), "네 점 (4, 1, 2)", 21, BLUE, True, anchor="lm")
        elif k in (1, 2):
            _t(d, (560, 422), "세 점의 현재 좌표 %s" % (v["following"].shape,), 21, GREEN, True, anchor="lm")
        else:
            _t(d, (560, 422), lines[11].strip().split(" = ")[1], 19, GREEN, True, code=True, anchor="lm")
        if k == 1:
            _t(d, (560, 478), "개론 2차시 셋째 단원 3단계", 19, MUTED)
        if k == 2:
            _t(d, (30, 478), lines[12], 21, BLUE, True, code=True)
            _t(d, (30, 512), "개론 1차시 셋째 단원 4단계", 19, MUTED)
        if k == 3:
            _t(d, (30, 478), lines[10].strip(), 21, ORANGE, True, code=True)
            box = _t(d, (30, 512), lines[12], 21, BLUE, True, code=True)
            _t(d, (box[2] + 16, 512), "old_gray도 이 프레임으로 옮겨 갑니다", 19, INK)
        frames.append(image)
    return frames, A18D_4_MS


@figure("a18d-5", 560, 220)
def a18d_summary():
    """외울 것 요약. 같은 조건으로 고르기, 변위와 평균, 다음 프레임으로 넘기기."""
    v = _a18d()
    lines = _a18d_lines()
    image, d = _new(440)
    _t(d, (24, 16), "성공한 점만 골라 변위를 구하고 다음 프레임으로 넘기기", 24, INK, True)
    _panel(d, (24, 62, 384, 300), "같은 조건으로 고르기", GREEN, [
        (lines[2], True, INK), None, ("prev_pts[keep]", True, BLUE), ("next_pts[keep]", True, ORANGE),
        ("같은 keep으로 함께 고름", False, INK), None, ("(4, 1, 2) → (3, 2)", True, GREEN)])
    _panel(d, (396, 62, 736, 300), "변위와 평균", ORANGE, [
        ("moves = new_ok - old_ok", True, INK), ("현재 좌표 - 이전 좌표", False, MUTED), None,
        ("[[3, -2], [4, -1], [2, -3]]", True, INK), None, ("moves.mean(axis=0)", True, INK),
        ("→ [%s, %s]" % tuple(_n(c) for c in v["mean0"]), True, ORANGE)])
    assert str(v["moves"].astype(int).tolist()) == "[[3, -2], [4, -1], [2, -3]]"
    _panel(d, (748, 62, 1096, 300), "다음 프레임으로 넘기기", BLUE, [
        ("new_ok.reshape(-1, 1, 2)", True, INK), ("→ %s" % (v["following"].shape,), True, GREEN), None,
        ("점이 3개보다 적으면", False, INK), ("None을 넣고 다시 찾기", False, INK), None, (lines[12], True, BLUE)])
    d.rounded_rectangle((24, 316, 1096, 424), 14, fill=NOTE)
    call = "next_pts, status, err = cv2.calcOpticalFlowPyrLK(old_gray, gray, prev_pts, None)"
    assert call.replace(" ", "") == (lines[0] + lines[1]).replace(" ", "")
    _t(d, (44, 350), call, 19, INK, True, code=True, anchor="lm")
    _t(d, (44, 392), "반환값: 현재 점, status, err  ·  인자: 이전 영상, 현재 영상, 이전 점", 19, MUTED, anchor="lm")
    return image
