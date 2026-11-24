# -*- coding: utf-8 -*-
"""응용 6차시 노트 al06 의 그림.

  ~/.cache/rokey-dev/lib/bin/python -m tools.ai_art al06 a6a-1   이름을 적은 그림만 그림

Pillow 로 직접 그린 상자·칸·막대·수직선·표임. 강의 슬라이드 그림, 노트북에 저장된 그림, 사진은 쓰지 않음.
콘텐츠 이미지와 스타일 이미지 칸의 무늬는 이 파일에서 그린 도형임.
그림에 찍는 Gram 행렬, 계수, 특징 맵 크기, 전처리 범위, 개수는 이 파일에서 다시 계산하고 assert 로 본문 숫자와 견줌.
LBFGS 의 closure 호출 수와 기록 길이는 PyTorch 없이 셀 수 없어 본문 숫자를 상수로 두고, 기록 길이만 history_size 규칙으로 다시 셈.
세 수준 그림은 화면 520×280(파일 1040×560)이고 levels.grid·graph 를 쓰거나 Pillow 로 글자 31px 이상으로 그림.

a6a 색: 파랑 = 옵티마이저가 바꾸는 생성 이미지와 그 화살표, 회색 = 고정한 CNN 가중치, 빨강 = 오류·기울기가 가지 않는 길,
주황 = 쌓이는 파라미터 grad·스타일 손실, 초록 = 콘텐츠 손실.
a6b 색: 파랑 = 1행 2열 원소와 결과, 주황·보라·파랑 테두리 = 섞기 전 위치 1·2·3, 초록 = 같음·대각 원소, 빨강 = 오류.
a6c 색: 파랑 = 원소 수와 1000 막대, 주황 = 스타일 층(S)과 1e3/n 막대, 초록 = 콘텐츠 층(C), 빨강 = 다른 칸.
a6d 색: 파랑 = 합성곱, 회색 = ReLU, 주황 = 풀링, 주황 칩 = 스타일 층, 초록 칩 = 콘텐츠 층, 빨강 = 자르는 자리.
a6e 색: 빨강·초록·파랑 = R·G·B 채널, 빨강 막대 = 0 이나 1 로 잘린 값, 파랑 막대 = 남은 값, 주황 = bad 식·짧은 변.
a6f 색: 파랑 = gen 과 step, 회색 = 고정한 model, 주황 = 스타일 손실, 초록 = 콘텐츠 손실, 보라 = closure 호출.
"""
from math import floor, sqrt

from PIL import Image, ImageDraw

from tools.ai_art import COLORS, figure, fmt
from tools.ai_art import levels
from tools.ai_art.al04 import arrow
from tools.ai_art.al05 import _box, _cross, _t
from tools.ai_art.al18 import _dash, _dash_line, _w

W = 1120
INK, MUTED, FAINT = COLORS["ink"], COLORS["muted"], COLORS["faint"]
BLUE, RED, ORANGE, GREEN, PURPLE = COLORS["blue"], COLORS["red"], COLORS["orange"], COLORS["green"], COLORS["purple"]
BLUE_L, GREEN_L, ORANGE_L, RED_L, PURPLE_L = "#dbeafe", "#d1fae5", "#ffedd5", "#fee2e2", "#ede9fe"
NOTE, LINE, LIGHT = "#f3f4f6", "#e5e7eb", "#9ca3af"
LW, LH = 1040, 560  # 세 수준 그림 파일 크기
LEVEL_MIN = 31  # 세 수준 그림 글자 하한(파일 px)


# 공통 도우미

def _new(h, w=W):
    image = Image.new("RGB", (w, h), "white")
    return image, ImageDraw.Draw(image)


def _title(d, text, right=None):
    _t(d, (36, 24), text, 25, INK, bold=True)
    if right:
        _t(d, (W - 36, 30), right, 20, MUTED, anchor="ra")


def _cell(d, rect, text="", fill="white", outline=LIGHT, size=24, color=INK, bold=False, code=True, width=2, radius=8,
          low=19):
    d.rounded_rectangle(rect, radius, fill=fill, outline=outline, width=width)
    if text != "":
        assert _w(text, size, bold, code) <= rect[2] - rect[0] - 6, (text, rect)
        _t(d, ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0), text, size, color, bold, code, anchor="mm", low=low)


def _matrix(d, x, y, rows, cw=64, ch=52, marks=None, size=24, gap=6, low=19):
    """칸 표. marks 는 {(행, 열): 색}. 오른쪽 아래 끝 좌표를 돌려줌."""
    marks = marks or {}
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            color = marks.get((r, c))
            pale = {BLUE: BLUE_L, ORANGE: ORANGE_L, GREEN: GREEN_L, RED: RED_L, PURPLE: PURPLE_L}.get(color, "white")
            _cell(d, (x + c * cw, y + r * ch, x + (c + 1) * cw - gap, y + (r + 1) * ch - gap), value, pale,
                  color or LIGHT, size, INK, bool(color), width=3 if color else 2, low=low)
    return x + len(rows[0]) * cw - gap, y + len(rows) * ch - gap


def _chip(d, xy, text, color, fill, size=19, anchor="mm", code=False, bold=True):
    """둥근 꼬리표. 차지한 상자를 돌려줌."""
    width = _w(text, size, bold, code) + 20
    x, y = xy
    if anchor == "mm":
        x0 = x - width / 2.0
    elif anchor == "lm":
        x0 = x
    else:
        x0 = x - width
    rect = (x0, y - size / 2.0 - 8, x0 + width, y + size / 2.0 + 8)
    d.rounded_rectangle(rect, 10, fill=fill, outline=color, width=2)
    _t(d, ((rect[0] + rect[2]) / 2.0, y), text, size, color, bold, code, anchor="mm")
    return rect


def _check(d, cx, cy, color=GREEN, r=12, width=5):
    d.line((cx - r, cy, cx - r / 3.0, cy + r * 0.7, cx + r, cy - r * 0.8), fill=color, width=width)


def _lock(d, cx, cy, color=MUTED, s=1.0):
    """자물쇠 표시. 고정해서 바뀌지 않는 칸에 붙임."""
    w, h = 30 * s, 24 * s
    d.arc((cx - 11 * s, cy - h / 2 - 20 * s, cx + 11 * s, cy - h / 2 + 4 * s), 180, 360, fill=color, width=max(3, int(4 * s)))
    d.line((cx - 11 * s, cy - h / 2 - 8 * s, cx - 11 * s, cy - h / 2), fill=color, width=max(3, int(4 * s)))
    d.line((cx + 11 * s, cy - h / 2 - 8 * s, cx + 11 * s, cy - h / 2), fill=color, width=max(3, int(4 * s)))
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 4, fill=color)
    d.ellipse((cx - 3 * s, cy - 4 * s, cx + 3 * s, cy + 2 * s), fill="white")


def _darrow(d, start, end, color=RED, width=4):
    """점선 화살표."""
    _dash_line(d, start + end, color, width, 10)
    arrow(d, (end[0] - (end[0] - start[0]) * 0.001, end[1] - (end[1] - start[1]) * 0.001), end, color, width)


def _r3(value):
    return round(value, 3)


def _num(value, digits=3):
    return fmt(value, digits)


def _content_art(d, rect):
    """콘텐츠 이미지 칸: 이 파일에서 그린 강가 건물 도형."""
    x0, y0, x1, y1 = rect
    d.rounded_rectangle(rect, 8, fill="#eff6ff", outline=LIGHT, width=2)
    river = y0 + (y1 - y0) * 0.72
    d.rectangle((x0 + 3, river, x1 - 3, y1 - 3), fill="#bfdbfe")
    for k, (fx, fw, fh) in enumerate(((0.12, 0.2, 0.42), (0.38, 0.24, 0.55), (0.68, 0.2, 0.34))):
        bx = x0 + (x1 - x0) * fx
        d.rectangle((bx, river - (y1 - y0) * fh, bx + (x1 - x0) * fw, river), fill="#9ca3af" if k != 1 else MUTED)


def _style_art(d, rect):
    """스타일 이미지 칸: 이 파일에서 그린 굵은 붓 자국 도형."""
    x0, y0, x1, y1 = rect
    d.rounded_rectangle(rect, 8, fill=ORANGE_L, outline=LIGHT, width=2)
    for k in range(5):
        y = y0 + 12 + k * (y1 - y0 - 24) / 4.0
        d.line((x0 + 12, y + 8, x1 - 12, y - 8), fill=(ORANGE, PURPLE, "#fde68a", BLUE, ORANGE)[k], width=7)


# a6a 가중치를 고정하고 생성 이미지의 픽셀 갱신하기

VGG19_CFG = [64, 64, "M", 128, 128, "M", 256, 256, 256, 256, "M", 512, 512, 512, 512, "M", 512, 512, 512, 512, "M"]


def _vgg_params():
    """VGG19 features 합성곱 16개의 가중치와 편향 수."""
    total, cin, convs = 0, 3, 0
    for v in VGG19_CFG:
        if v == "M":
            continue
        total += 3 * 3 * cin * v + v
        cin, convs = v, convs + 1
    return convs, total


def _update(x, g, lr=0.1):
    return round(x - lr * g, 4)


@figure("a6a-1", 560, 250)
def a6a_roles():
    """콘텐츠·스타일 이미지가 CNN 에 들어가고 옵티마이저는 생성 이미지만 바꿈."""
    image, d = _new(500)
    _title(d, "옵티마이저는 생성 이미지 하나만 바꿉니다")
    _content_art(d, (60, 110, 200, 210))
    _t(d, (216, 160), "콘텐츠 이미지", 22, INK, True, anchor="lm")
    _style_art(d, (60, 290, 200, 390))
    _t(d, (216, 340), "스타일 이미지", 22, INK, True, anchor="lm")
    arrow(d, (380, 160), (470, 230), MUTED, 4)
    arrow(d, (380, 340), (470, 270), MUTED, 4)
    # 글자 두 줄을 위로 올리고 자물쇠를 그 아래에 둬 고리가 글자에 닿지 않게 함
    d.rounded_rectangle((480, 170, 680, 330), 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (580, 210), "CNN", 24, INK, True, anchor="mm")
    _t(d, (580, 242), "가중치 고정", 24, MUTED, anchor="mm")
    _lock(d, 580, 294, MUTED, 0.8)
    d.rounded_rectangle((820, 90, 1000, 210), 8, fill=BLUE_L, outline=BLUE, width=3)
    _t(d, (910, 150), "생성 이미지", 22, BLUE, True, anchor="mm")
    _box(d, (800, 330, 1020, 400), [("옵티마이저", "white", True, False)], fill=BLUE, outline=BLUE, size=24)
    arrow(d, (910, 326), (910, 218), BLUE, 6)
    _t(d, (930, 270), "픽셀 갱신", 20, BLUE, anchor="lm")
    _t(d, (36, 460), "콘텐츠 이미지와 스타일 이미지는 특징 맵 계산에만 쓰이고, 옵티마이저가 바꾸는 것은 생성 이미지의 픽셀뿐입니다.", 19,
       MUTED)
    return image


def _a6a2_frame(k):
    image, d = _new(600)
    _title(d, "바뀌는 것은 생성 이미지 x의 픽셀입니다")
    rows = [("콘텐츠 이미지", 120), ("스타일 이미지", 220), ("생성 이미지 x", 320)]
    _content_art(d, (40, 92, 130, 148))
    _style_art(d, (40, 192, 130, 248))
    d.rounded_rectangle((40, 292, 130, 348), 8, fill=BLUE_L, outline=BLUE, width=3)
    _t(d, (85, 320), "x", 26, BLUE, True, anchor="mm")
    for name, y in rows:
        _t(d, (142, y), name, 20, BLUE if name.endswith("x") else INK, name.endswith("x"), anchor="lm")
        arrow(d, (290, y), (360, 220 + (y - 220) * 0.3), INK if k == 0 else LIGHT, 4 if k == 0 else 3)
    cnn = (370, 150, 560, 290)
    d.rounded_rectangle(cnn, 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (465, 183), "가중치를 고정한", 22, MUTED, anchor="mm")
    _t(d, (465, 213), "CNN", 22, INK, True, anchor="mm")
    _lock(d, 465, 260, MUTED, 0.7)
    if k >= 1:
        _box(d, (650, 90, 1090, 160), [("스타일 손실 L_style", ORANGE, True, False),
                                         ("여러 층의 Gram 행렬 차이", INK, False, False)], fill=ORANGE_L, outline=ORANGE, size=20, gap=6)
        _box(d, (650, 180, 1090, 250), [("콘텐츠 손실 L_content", GREEN, True, False),
                                          ("한 층의 특징 맵 차이", INK, False, False)], fill=GREEN_L, outline=GREEN, size=20, gap=6)
        arrow(d, (566, 200), (644, 125), ORANGE, 4)
        arrow(d, (566, 225), (644, 215), GREEN, 4)
    if k >= 2:
        _box(d, (650, 290, 1090, 370), [("총손실", INK, True, False), ("L_total = α·L_content + β·L_style", INK, False, True)],
             fill="white", outline=BLUE if k == 2 else LIGHT, size=20, gap=8, width=3)
        arrow(d, (870, 254), (870, 286), INK, 3)
    if k >= 3:
        d.line((1050, 374, 1050, 470, 85, 470), fill=BLUE, width=5)
        arrow(d, (85, 470), (85, 356), BLUE, 5)
        _chip(d, (560, 470), "x := x − λ·∂L/∂x  (x만 갱신)", BLUE, BLUE_L, 20, code=True)
        # 점선은 꼬리표 위쪽 테두리 밖에서 시작하고, 설명 글은 점선 오른쪽으로 띄움
        _darrow(d, (690, 444), (520, 300), RED, 4)
        _cross(d, 609, 375, 14, RED, 5)
        _t(d, (676, 398), "CNN 가중치로는 가지 않음", 19, RED, anchor="la")
    lines = ["세 이미지가 가중치를 고정한 같은 CNN을 지납니다.", "스타일 손실은 여러 층, 콘텐츠 손실은 한 층에서 계산합니다.",
             "두 손실에 α와 β를 곱해 더한 L_total이 나옵니다.", "L_total의 기울기로 x만 바꿉니다."]
    _t(d, (36, 548), lines[k], 21, INK, code=k == 2)
    return image


@figure("a6a-2", 560, 300)
def a6a_total_loss():
    """세 이미지 → 고정 CNN → 두 손실 → 총손실 → x 갱신(4장)."""
    return [_a6a2_frame(k) for k in range(4)], [2200, 2200, 2200, 2400]


def _pixel_grid(d, x, y, n, cell, fills):
    for r in range(n):
        for c in range(n):
            d.rectangle((x + c * cell, y + r * cell, x + (c + 1) * cell - 5, y + (r + 1) * cell - 5), fill=fills[(r * n + c) % len(fills)])


@figure("a6a-3", 560, 230)
def a6a_list():
    """옵티마이저 목록의 gen 만 바뀌고 CNN 가중치는 그대로."""
    assert _update(0.40, 0.5) == 0.35 and _update(0.40, -0.4) == 0.44
    image, d = _new(460)
    _title(d, "옵티마이저 목록에 넣은 gen의 픽셀만 바뀝니다")
    d.rounded_rectangle((36, 120, 410, 330), 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (56, 150), "옵티마이저를 만드는 줄", 20, MUTED)
    _t(d, (56, 214), "optim.Adam(", 24, INK, code=True, anchor="lm")
    x = 56 + _w("optim.Adam(", 24, False, True)
    rect = _chip(d, (x + 4, 214), "[gen]", BLUE, BLUE_L, 24, anchor="lm", code=True)
    _t(d, (rect[2] + 4, 214), ", lr=0.1)", 24, INK, code=True, anchor="lm")
    assert rect[2] + 4 + _w(", lr=0.1)", 24, False, True) <= 410 - 16
    _t(d, (56, 290), "목록에 든 텐서만 step()이 바꿉니다", 19, MUTED)
    arrow(d, (420, 225), (480, 225), BLUE, 6)
    d.rounded_rectangle((490, 100, 750, 380), 12, fill="white", outline=BLUE, width=3)
    _t(d, (620, 130), "gen 픽셀", 22, BLUE, True, anchor="mm")
    _pixel_grid(d, 545, 160, 4, 40, [BLUE_L, "#93c5fd", BLUE_L, "#bfdbfe", "#3b82f6"])
    _t(d, (620, 350), "값이 바뀜", 20, BLUE, True, anchor="mm")
    d.rounded_rectangle((810, 100, 1084, 380), 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (947, 130), "CNN 가중치", 22, MUTED, True, anchor="mm")
    _pixel_grid(d, 867, 160, 4, 40, ["#d1d5db", "#9ca3af", "#e5e7eb"])
    _lock(d, 947, 240, INK, 1.0)
    _t(d, (947, 350), "바뀌지 않음", 20, MUTED, True, anchor="mm")
    _t(d, (36, 420), "목록에 model.parameters()를 넣지 않았으므로 CNN 가중치 칸은 회색으로 남습니다.", 19, MUTED)
    return image


@figure("a6a-41", 520, 280)
def a6a_level7():
    """숫자 칸 세 개와 쪽지, 바뀌지 않는 계산 상자."""
    values, notes = [0.40, 0.70, 0.20], [("0.05 줄이기", -0.05), ("0.02 늘리기", 0.02), ("0.03 줄이기", -0.03)]
    assert round(values[0] + notes[0][1], 2) == 0.35 and round(values[1] + notes[1][1], 2) == 0.72
    assert round(values[2] + notes[2][1], 2) == 0.17
    image, d = _new(LH, LW)
    for k, (value, (note, _)) in enumerate(zip(values, notes)):
        x = 40 + k * 215
        _chip(d, (x + 95, 130), note, ORANGE, ORANGE_L, LEVEL_MIN)
        _cell(d, (x, 190, x + 190, 300), "%.2f" % value, BLUE_L if k == 0 else "white", BLUE if k == 0 else LIGHT, 44,
              bold=True, width=3 if k == 0 else 2, low=LEVEL_MIN)
    arrow(d, (135, 312), (135, 370), BLUE, 5)
    _t(d, (135, 420), "0.35", 44, BLUE, True, code=True, anchor="mm", low=LEVEL_MIN)
    d.rounded_rectangle((720, 150, 1000, 420), 16, fill=NOTE, outline=LIGHT, width=3)
    _t(d, (860, 210), "계산 상자", LEVEL_MIN, INK, True, anchor="mm", low=LEVEL_MIN)
    _lock(d, 860, 320, MUTED, 1.8)
    return image


@figure("a6a-42", 520, 280)
def a6a_level15():
    rows = [["0.40", "0.5", fmt(0.1 * 0.5, 2)], ["0.70", fmt(-0.2, 1), ""], ["0.20", "0.3", ""]]
    assert rows[0][2] == "0.05" and _update(0.20, 0.3) == 0.17
    return levels.grid(rows, col_names=("지금 값", "기울기", "학습률 × 기울기"), marks=[(0, 2)], color="blue",
                       top="새 값 = 지금 값 − 학습률 × 기울기   (학습률 0.1)")


@figure("a6a-43", 520, 280)
def a6a_level20():
    """SGD 목록에 model.parameters() 를 넣은 경우와 x 를 넣은 경우."""
    image, d = _new(LH, LW)
    for k, (code, changed) in enumerate((("SGD(model.parameters())", False), ("SGD([x])", True))):
        top = 40 + k * 260
        fill = BLUE_L if changed else NOTE
        d.rounded_rectangle((24, top, LW - 24, top + 230), 16, fill=fill, outline=BLUE if changed else LIGHT, width=3)
        _t(d, (48, top + 40), code, 34, BLUE if changed else INK, True, code=True, anchor="lm", low=LEVEL_MIN)
        for c, value in enumerate(("0.40", "0.70", "0.20")):
            _cell(d, (48 + c * 112, top + 100, 148 + c * 112, top + 170), value, "white", LIGHT, LEVEL_MIN, low=LEVEL_MIN)
        if not changed:
            _t(d, (LW - 48, top + 40), "x.grad 채워짐", LEVEL_MIN, BLUE, True, anchor="rm", low=LEVEL_MIN)
        arrow(d, (390, top + 135), (520, top + 135), INK, 5)
        _t(d, (455, top + 200), "opt.step() 뒤", LEVEL_MIN, MUTED, anchor="mm", code=True, low=LEVEL_MIN)
        for c in range(3):
            rect = (540 + c * 112, top + 100, 640 + c * 112, top + 170)
            if changed:
                _cell(d, rect, "", BLUE_L, BLUE, width=4)
            else:
                _dash(d, rect, LIGHT, 3, 8)
        if changed:
            _t(d, (880, top + 200), "값 바뀜", LEVEL_MIN, BLUE, True, anchor="mm", low=LEVEL_MIN)
    return image


@figure("a6a-4", 560, 290)
def a6a_freeze():
    """고정한 경우와 고정하지 않은 경우의 grad."""
    convs, params = _vgg_params()
    assert convs == 16 and params == 20024384
    image, d = _new(580)
    _title(d, "가중치를 고정해도 gen의 grad는 채워집니다")
    rows = [("고정함 · requires_grad_(False)", "파라미터 grad = None", MUTED, BLUE, BLUE_L),
            ("고정하지 않음", "파라미터 grad 계산 · 쌓임 (파라미터 20,024,384개)", ORANGE, ORANGE, ORANGE_L)]
    for k, (head, note, ink, edge, pale) in enumerate(rows):
        top = 80 + k * 240
        d.rounded_rectangle((36, top, 790, top + 220), 12, fill="white", outline=edge, width=3)
        _chip(d, (56, top + 30), head, edge, pale, 19, anchor="lm")
        _cell(d, (70, top + 80, 190, top + 140), "gen", BLUE_L, BLUE, 26, BLUE, True, width=3)
        _t(d, (130, top + 170), "gen의 grad 채워짐", 19, BLUE, True, anchor="mm")
        for c in range(3):
            fill, line = (NOTE, LIGHT) if k == 0 else (ORANGE_L, ORANGE)
            _cell(d, (380 + c * 78, top + 80, 450 + c * 78, top + 140), "합성곱", fill, line, 19, MUTED if k == 0 else ORANGE,
                  code=False)
        _cell(d, (680, top + 80, 770, top + 140), "총손실", NOTE, LIGHT, 20, INK, True, code=False)
        arrow(d, (674, top + 110), (616, top + 110), BLUE, 4)
        arrow(d, (372, top + 110), (200, top + 110), BLUE, 4)
        _t(d, (286, top + 92), "backward()", 19, BLUE, code=True, anchor="mm")
        _t(d, (520, top + 175), note, 19, ink, True, anchor="mm")
    d.rounded_rectangle((820, 80, 1084, 540), 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (840, 110), "두 경우 공통", 20, MUTED, True)
    _box(d, (840, 160, 1064, 260), ["옵티마이저에 넣은 것", ("gen 하나", BLUE, True, False)], fill="white", outline=BLUE, size=20)
    _box(d, (840, 290, 1064, 390), ["파라미터 값은", "두 경우 모두", ("바뀌지 않음", GREEN, True, False)], fill="white",
         outline=GREEN, size=19, gap=6)
    _t(d, (952, 440), "zero_grad()는", 19, MUTED, anchor="mm")
    _t(d, (952, 470), "gen의 grad만 지움", 19, MUTED, anchor="mm")
    return image


@figure("a6a-5", 560, 250)
def a6a_leaf():
    """clone → detach → requires_grad_(True) 와 is_leaf·requires_grad."""
    image, d = _new(500)
    _title(d, "clone(), detach(), requires_grad_(True)로 잎 텐서 만들기")
    notes = ["계산에서 나온 값", "값을 복사한 새 텐서", "계산 기록에서 떼어 낸 텐서", "기울기를 기록하는 잎 텐서"]
    boxes = [("content", ["is_leaf False"], LIGHT, "white"),
             (".clone()", ["is_leaf False"], LIGHT, "white"),
             (".detach()", ["is_leaf True", "requires_grad False"], LIGHT, "white"),
             (".requires_grad_(True)", ["is_leaf True", "requires_grad True"], BLUE, BLUE_L)]
    for k, (head, lines, edge, fill) in enumerate(boxes):
        x0 = 36 + k * 264
        d.rounded_rectangle((x0, 90, x0 + 244, 220), 12, fill=fill, outline=edge, width=3 if edge == BLUE else 2)
        _t(d, (x0 + 122, 122), head, 20, BLUE if edge == BLUE else INK, True, code=True, anchor="mm")
        for n, line in enumerate(lines):
            _t(d, (x0 + 122, 162 + n * 30), line, 19, INK, code=True, anchor="mm")
        _t(d, (x0 + 122, 246), notes[k], 19, MUTED, anchor="mm")
        if k < 3:
            arrow(d, (x0 + 248, 155), (x0 + 262, 155), MUTED, 3)
    d.rounded_rectangle((300, 300, 1084, 420), 12, fill=RED_L, outline=RED, width=2)
    arrow(d, (422, 266), (422, 352), RED, 4)
    _t(d, (440, 318), "detach()를 빼고 바로", 19, RED, anchor="la")
    _cell(d, (440, 360, 640, 405), "optim.Adam", "white", RED, 20, RED, True)
    _cross(d, 680, 382, 13, RED, 5)
    _t(d, (710, 370), "ValueError:", 20, RED, True, code=True, anchor="lm")
    _t(d, (710, 398), "can't optimize a non-leaf Tensor", 19, RED, code=True, anchor="lm")
    _t(d, (36, 460), "gen = content.clone().detach().requires_grad_(True)", 20, INK, code=True)
    return image


# a6b Gram 행렬

CH1, CH2 = [1, 0, 2], [3, 1, 0]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _gram(rows):
    return [[_dot(a, b) for b in rows] for a in rows]


def _corr(a, b):
    ma, mb = sum(a) / float(len(a)), sum(b) / float(len(b))
    da, db = [x - ma for x in a], [y - mb for y in b]
    return _dot(da, db) / (sqrt(_dot(da, da)) * sqrt(_dot(db, db)))


def _a6b_numbers():
    assert _gram([CH1, CH2]) == [[5, 3], [3, 10]]
    assert [x * y for x, y in zip(CH1, CH2)] == [3, 0, 0]
    shuffled = [[2, 1, 0], [0, 3, 1]]
    assert shuffled == [[CH1[2], CH1[0], CH1[1]], [CH2[2], CH2[0], CH2[1]]] and _gram(shuffled) == [[5, 3], [3, 10]]
    assert round(_corr(CH1, CH2), 3) == -0.327
    return shuffled


@figure("a6b-1", 560, 250)
def a6b_element():
    _a6b_numbers()
    image, d = _new(500)
    _title(d, "같은 위치끼리 곱해 더한 3이 Gram 행렬의 1행 2열")
    for c in range(3):
        _t(d, (225 + c * 100, 100), "위치 %d" % (c + 1), 19, MUTED, anchor="mm")
    for r, (name, row) in enumerate((("채널 1", CH1), ("채널 2", CH2))):
        y = 125 + r * 110
        _t(d, (90, y + 32), name, 21, INK, True, anchor="mm")
        for c, value in enumerate(row):
            _cell(d, (190 + c * 100, y, 260 + c * 100, y + 64), str(value), BLUE_L if r == 0 else PURPLE_L,
                  BLUE if r == 0 else PURPLE, 26, INK, True, width=2)
    for c, value in enumerate(x * y for x, y in zip(CH1, CH2)):
        d.line((225 + c * 100, 191, 225 + c * 100, 233), fill=LIGHT, width=3)
        _t(d, (225 + c * 100, 330), "곱 %d" % value, 21, ORANGE, True, anchor="mm")
    _chip(d, (325, 395), "곱의 합: 3 + 0 + 0 = 3", ORANGE, ORANGE_L, 21)
    arrow(d, (520, 260), (640, 260), BLUE, 6)
    _t(d, (580, 230), "1행 2열로", 19, BLUE, anchor="mm")
    _t(d, (850, 100), "Gram 행렬 (2 × 2)", 21, INK, True, anchor="mm")
    for k, name in enumerate(("1열", "2열")):
        _t(d, (798 + k * 104, 140), name, 19, MUTED, anchor="mm")
        _t(d, (720, 196 + k * 104), ("1행", "2행")[k], 19, MUTED, anchor="mm")
    _matrix(d, 750, 160, [["5", "3"], ["3", "10"]], cw=104, ch=104, marks={(0, 1): BLUE}, size=32)
    return image


def _a6b2_frame(k):
    image, d = _new(560)
    _title(d, "특징 맵을 펴서 Gram 행렬 만들기")
    if k == 0:
        for r, (name, row) in enumerate((("채널 1", CH1), ("채널 2", CH2))):
            y = 150 + r * 90
            _t(d, (60, y + 30), name, 21, INK, True, anchor="lm")
            for c, value in enumerate(row):
                _cell(d, (160 + c * 74, y, 222 + c * 74, y + 60), str(value), "white", LIGHT, 26)
    else:
        _chip(d, (100, 120), "view", BLUE, BLUE_L, 20, code=True)
        d.rounded_rectangle((40, 150, 300, 330), 12, fill=NOTE, outline=BLUE, width=3)
        _t(d, (170, 172), "F (2행 3열)", 20, BLUE, True, anchor="mm")
        _matrix(d, 62, 195, [[str(v) for v in CH1], [str(v) for v in CH2]], cw=74, ch=66, size=26)
    if k >= 2:
        _t(d, (350, 250), "@", 34, INK, True, code=True, anchor="mm")
        d.rounded_rectangle((400, 110, 600, 420), 12, fill=NOTE, outline=PURPLE, width=3)
        _t(d, (500, 132), "F의 전치 (3행 2열)", 19, PURPLE, True, anchor="mm")
        _matrix(d, 430, 156, [[str(a), str(b)] for a, b in zip(CH1, CH2)], cw=74, ch=86, size=26)
    if k >= 3:
        _t(d, (650, 250), "=", 34, INK, True, code=True, anchor="mm")
        d.rounded_rectangle((700, 140, 950, 370), 12, fill=BLUE_L, outline=BLUE, width=3)
        _t(d, (825, 164), "Gram 행렬 (2×2)", 20, BLUE, True, anchor="mm")
        _matrix(d, 730, 195, [["5", "3"], ["3", "10"]], cw=98, ch=84, size=30, marks={(0, 1): BLUE})
        _chip(d, (560, 470), "(b, c, h*w) @ (b, h*w, c) = (b, c, c)", BLUE, "white", 21, code=True)
    lines = ["채널 1과 채널 2의 값이 위치 셋에 놓인 칸 줄 두 개입니다.", "view로 펴서 2행 3열 행렬 F가 됩니다.",
             "F의 전치 행렬은 3행 2열입니다.", "h*w 축은 곱해 더해져 사라지고 c×c가 남습니다."]
    _t(d, (36, 520), lines[k], 21, INK)
    return image


@figure("a6b-2", 560, 280)
def a6b_view_bmm():
    _a6b_numbers()
    return [_a6b2_frame(k) for k in range(4)], [2200, 2200, 2200, 2400]


@figure("a6b-31", 520, 280)
def a6b_level7():
    image, d = _new(LH, LW)
    for r, row in enumerate((CH1, CH2)):
        for c, value in enumerate(row):
            _cell(d, (60 + c * 140, 110 + r * 220, 160 + c * 140, 210 + r * 220), str(value), "white", MUTED, 44, bold=True,
                  low=LEVEL_MIN)
    for c in range(3):
        d.line((110 + c * 140, 214, 110 + c * 140, 326), fill=LIGHT, width=4)
    assert _gram([CH1, CH2])[0][1] == 3
    for r in range(2):
        for c in range(2):
            rect = (640 + c * 160, 140 + r * 160, 780 + c * 160, 280 + r * 160)
            if (r, c) == (0, 1):
                _cell(d, rect, "3", BLUE_L, BLUE, 48, BLUE, True, width=4, low=LEVEL_MIN)
            elif (r, c) == (1, 1):
                _dash(d, rect, MUTED, 3, 9)
            else:
                _cell(d, rect, "", "white", LIGHT)
    return image


@figure("a6b-32", 520, 280)
def a6b_level15():
    assert 2 * 2 == 4 and 32 * 32 == 1024
    return levels.grid([["2", "3", "4"], ["64", "1,024", ""]], col_names=("줄 수", "줄마다 숫자 개수", "결과 표 칸 수"),
                       marks=[(0, 2)], color="blue", top="결과 표 칸 수 = 줄 수 × 줄 수")


def _shape_after(shape, op):
    if op == "view":
        b, c, h, w = shape
        return (b, c, h * w)
    if op == "transpose12":
        b, n, m = shape
        return (b, m, n)
    raise ValueError(op)


@figure("a6b-33", 520, 280)
def a6b_level20():
    x = (3, 16, 8, 8)
    f = _shape_after(x, "view")
    ft = _shape_after(f, "transpose12")
    assert f == (3, 16, 64) and ft == (3, 64, 16)
    image, d = _new(LH, LW)
    texts = ["(3, 16, 8, 8)", "(3, 16, 64)", "(3, 64, 16)", ""]
    assert texts[:3] == [str(s) for s in (x, f, ft)]
    names = ["x", "f", "f의 전치", "g"]
    ops = ["view", "transpose(1, 2)", "bmm"]
    widths = [_w(t, LEVEL_MIN, False, True) + 28 if t else 150 for t in texts]
    gap = (LW - 48 - sum(widths)) / 3.0
    x0 = 24
    for k, (text, name, width) in enumerate(zip(texts, names, widths)):
        rect = (x0, 250, x0 + width, 330)
        if text:
            _cell(d, rect, text, NOTE, LIGHT, LEVEL_MIN, low=LEVEL_MIN)
        else:
            _dash(d, rect, MUTED, 3, 9)
        _t(d, (x0 + width / 2.0, 380), name, LEVEL_MIN, MUTED, anchor="mm", low=LEVEL_MIN)
        if k < 3:
            arrow(d, (x0 + width + 8, 290), (x0 + width + gap - 8, 290), INK, 4)
            _t(d, (x0 + width + gap / 2.0, 200), ops[k], LEVEL_MIN, BLUE, True, code=True, anchor="mm", low=LEVEL_MIN)
        x0 += width + gap
    return image


@figure("a6b-3", 560, 260)
def a6b_shuffle():
    shuffled = _a6b_numbers()
    image, d = _new(520)
    _title(d, "위치를 섞어도 Gram 행렬은 같습니다")
    edges = [ORANGE, PURPLE, BLUE]
    before = [(CH1[c], CH2[c], edges[c], "위치 %d" % (c + 1)) for c in range(3)]
    after = [(shuffled[0][c], shuffled[1][c], edges[(c + 2) % 3], "새 위치 %d" % (c + 1)) for c in range(3)]
    for r, (name, cols, top) in enumerate((("섞기 전", before, 90), ("섞은 뒤", after, 290))):
        d.rounded_rectangle((36, top, 1084, top + 170), 12, fill=NOTE if r == 0 else "white",
                            outline=LIGHT if r == 0 else GREEN, width=2)
        _t(d, (60, top + 30), name, 21, INK if r == 0 else GREEN, True, anchor="la")
        _t(d, (60, top + 80), "채널 1", 19, MUTED, anchor="la")
        _t(d, (60, top + 122), "채널 2", 19, MUTED, anchor="la")
        for c, (a, b, edge, label) in enumerate(cols):
            x0 = 200 + c * 170
            d.rounded_rectangle((x0, top + 14, x0 + 140, top + 156), 10, fill="white", outline=edge, width=3)
            _t(d, (x0 + 70, top + 36), label, 19, edge, True, anchor="mm")
            _t(d, (x0 + 70, top + 88), str(a), 26, INK, True, code=True, anchor="mm")
            _t(d, (x0 + 70, top + 128), str(b), 26, INK, True, code=True, anchor="mm")
        _t(d, (760, top + 85), "곱의 합", 19, MUTED, anchor="mm")
        arrow(d, (720, top + 110), (800, top + 110), MUTED, 3)
        _matrix(d, 830, top + 30, [["5", "3"], ["3", "10"]], cw=66, ch=56, size=24, marks={(0, 1): BLUE})
    _chip(d, (1030, 275), "= 같음", GREEN, GREEN_L, 20)
    _t(d, (36, 490), "같은 색 테두리 = 섞기 전에 같은 위치에 있던 두 값. 두 값은 함께 옮겨져 곱이 바뀌지 않습니다.", 19, MUTED)
    return image


@figure("a6b-4", 560, 270)
def a6b_errors():
    assert _shape_after((2, 3, 4, 5), "view") == (2, 3, 20)
    image, d = _new(540)
    _title(d, "Gram 계산에서 RuntimeError가 나는 세 경우")
    tops = [80, 220, 360]
    for k, top in enumerate(tops):
        d.rounded_rectangle((36, top, 1084, top + 120), 12, fill=NOTE, outline=LIGHT, width=2)
        _chip(d, (56, top + 60), "경우 %d" % (k + 1), RED, RED_L, 19, anchor="lm")
    y = tops[0] + 50

    for rect, parts, label in (((170, y - 28, 330, y + 28), ("(", "2", ", 3, 20)"), "f"),
                               ((470, y - 28, 630, y + 28), ("(", "3", ", 2, 20)"), "f.transpose(0, 1)")):
        _cell(d, rect, "", "white", LIGHT)
        x = (rect[0] + rect[2]) / 2.0 - sum(_w(part, 22, n == 1, True) for n, part in enumerate(parts)) / 2.0
        for n, part in enumerate(parts):
            _t(d, (x, y), part, 22, RED if n == 1 else INK, n == 1, code=True, anchor="lm")
            x += _w(part, 22, n == 1, True)
        _t(d, ((rect[0] + rect[2]) / 2.0, y + 46), label, 19, MUTED, code=True, anchor="mm")
    _t(d, (400, y), "bmm", 22, BLUE, True, code=True, anchor="mm")
    _cross(d, 680, y, 11, RED, 4)
    _t(d, (705, y), "배치 크기 2와 3이 달라 곱하지 못함", 19, RED, True, anchor="lm")
    y = tops[1] + 60
    _cell(d, (170, y - 28, 400, y + 28), "3차원 (2, 3, 20)", "white", LIGHT, 21)
    arrow(d, (410, y), (450, y), MUTED, 3)
    _cell(d, (460, y - 28, 640, y + 28), "torch.mm", "white", RED, 22, RED, True)
    _cross(d, 670, y, 11, RED, 4)
    _t(d, (695, y), "torch.mm은 2차원 행렬끼리만 곱합니다", 19, RED, anchor="lm")
    y = tops[2] + 60
    _cell(d, (170, y - 28, 330, y + 28), "(2, 3, 4, 5)", "white", LIGHT, 21)
    arrow(d, (336, y), (356, y), MUTED, 3)
    _cell(d, (362, y - 28, 552, y + 28), "transpose(2, 3)", "white", BLUE, 20, BLUE)
    arrow(d, (558, y), (578, y), MUTED, 3)
    _cell(d, (584, y - 28, 744, y + 28), "(2, 3, 5, 4)", "white", LIGHT, 21)
    _cell(d, (770, y - 50, 1000, y - 6), "view(2, 3, 20)", RED_L, RED, 20, RED, True)
    _cross(d, 1030, y - 28, 10, RED, 4)
    _cell(d, (770, y + 6, 1000, y + 50), "reshape(2, 3, 20)", GREEN_L, GREEN, 20, GREEN, True)
    _check(d, 1032, y + 28, GREEN, 11, 4)
    _t(d, (36, 512), "transpose로 바꾼 축은 메모리 순서와 모양이 맞지 않아 view로 펴지 못합니다.", 19, MUTED)
    return image


@figure("a6b-5", 560, 240)
def a6b_corr():
    _a6b_numbers()
    r = fmt(_corr(CH1, CH2), 3)
    assert r == "−0.327"
    image, d = _new(480)
    _title(d, "같은 두 채널의 Gram 행렬과 상관계수 행렬")
    marks = {(0, 0): GREEN, (1, 1): GREEN, (0, 1): ORANGE}
    _t(d, (300, 100), "Gram 행렬", 22, INK, True, anchor="mm")
    _matrix(d, 190, 130, [["5", "3"], ["3", "10"]], cw=112, ch=96, marks=marks, size=30)
    _t(d, (560, 225), "vs", 26, MUTED, True, anchor="mm")
    _t(d, (820, 100), "상관계수 행렬", 22, INK, True, anchor="mm")
    _matrix(d, 710, 130, [["1", r], [r, "1"]], cw=112, ch=96, marks=marks, size=26)
    _t(d, (300, 350), "대각선: 채널마다 제곱합", 19, MUTED, anchor="mm")
    _t(d, (820, 350), "대각선: 늘 1", 19, MUTED, anchor="mm")
    _t(d, (36, 420), "초록 테두리 = 대각 원소, 주황 테두리 = 1행 2열 원소입니다.", 19, MUTED)
    return image


# a6c 나눗셈과 계수

STYLE_NS = [64, 128, 256, 512, 512]


def _div(rows, n):
    return [[_r3(v / float(n)) for v in row] for row in rows]


def _mat_text(rows):
    return [[fmt(v, 3) for v in row] for row in rows]


@figure("a6c-1", 560, 260)
def a6c_hw():
    g3 = _gram([CH1, CH2])
    g6 = _gram([CH1 + CH1, CH2 + CH2])
    assert g6 == [[10, 6], [6, 20]] and _div(g3, 3) == _div(g6, 6) == [[1.667, 1.0], [1.0, 3.333]]
    image, d = _new(520)
    _title(d, "h*w로 나누면 위치 수가 달라도 같은 Gram 행렬")
    rows = [("위치 3개", [CH1, CH2], g3, 3, 90), ("이어 붙여 위치 6개", [CH1 + CH1, CH2 + CH2], g6, 6, 280)]
    for name, cells, gram, n, top in rows:
        d.rounded_rectangle((36, top, 760, top + 170), 12, fill=NOTE, outline=LIGHT, width=2)
        _t(d, (56, top + 26), name, 20, BLUE if n == 3 else PURPLE, True, anchor="la")
        _matrix(d, 56, top + 62, [[str(v) for v in row] for row in cells], cw=44, ch=46, size=21)
        arrow(d, (340, top + 108), (380, top + 108), MUTED, 3)
        _matrix(d, 400, top + 50, [[str(v) for v in row] for row in gram], cw=70, ch=56, size=24)
        _chip(d, (650, top + 108), "÷ %d" % n, BLUE if n == 3 else PURPLE, "white", 22, code=True)
        arrow(d, (700, top + 108), (800, 270), BLUE if n == 3 else PURPLE, 4)
    d.rounded_rectangle((810, 120, 1084, 420), 12, fill=BLUE_L, outline=BLUE, width=3)
    _t(d, (947, 150), "h*w로 나눈 Gram 행렬", 20, BLUE, True, anchor="mm")
    _matrix(d, 836, 190, _mat_text(_div(g3, 3)), cw=114, ch=84, size=28)
    _t(d, (947, 395), "두 경우 모두 같은 값", 19, BLUE, anchor="mm")
    _t(d, (36, 490), "같은 특징 맵을 두 번 이어 붙이면 곱의 합이 두 배가 되고, 위치 수로 나누면 그 차이가 없어집니다.", 19, MUTED)
    return image


@figure("a6c-2", 560, 250)
def a6c_mse():
    G, A = [[5, 3], [3, 10]], [[5, 3], [3, 4]]
    sq = sum((g - a) ** 2 for gr, ar in zip(G, A) for g, a in zip(gr, ar))
    n, m = 2, 3
    assert sq == 36 and 4 * n ** 2 * m ** 2 == 144 and sq / 144.0 == 0.25 and sq / 4.0 == 9
    mse_m = sum((g / 3.0 - a / 3.0) ** 2 for gr, ar in zip(G, A) for g, a in zip(gr, ar)) / 4.0
    assert round(mse_m, 9) == 1 and round(mse_m / 0.25, 9) == 4
    image, d = _new(500)
    _title(d, "제곱 차이의 합 36을 무엇으로 나누나", "N = 2, M = 3")
    for k, (name, rows, color) in enumerate((("G (생성)", G, BLUE), ("A (스타일)", A, PURPLE))):
        x0 = 50 + k * 230
        _t(d, (x0 + 80, 100), name, 20, color, True, anchor="mm")
        _matrix(d, x0, 130, [[str(v) for v in row] for row in rows], cw=84, ch=74, size=28, marks={(1, 1): RED})
    _box(d, (90, 310, 410, 400), [("2행 2열만 차이 6", RED, True, False), ("6² = 36", RED, False, True)], fill=RED_L,
         outline=RED, size=21)
    lines = [("E_l", "36 ÷ 144 = 0.25", BLUE, BLUE_L, "4·N²·M² = 144로 나눔"),
             ("MSELoss", "36 ÷ 4 = 9", ORANGE, ORANGE_L, "원소 수 4로 나눈 평균"),
             ("G ÷ 3, A ÷ 3", "MSELoss = 1 = 4 × 0.25", GREEN, GREEN_L, "36 ÷ 3² ÷ 4")]
    for k, (name, value, color, pale, note) in enumerate(lines):
        top = 96 + k * 116
        d.rounded_rectangle((540, top, 1084, top + 96), 12, fill=pale, outline=color, width=2)
        _t(d, (560, top + 30), name, 20, color, True, code=True, anchor="lm")
        _t(d, (560, top + 66), value, 22, INK, True, code=True, anchor="lm")
        _t(d, (1064, top + 30), note, 19, MUTED, anchor="rm")
    _t(d, (36, 470), "M으로 나눈 두 Gram 행렬을 MSELoss에 넣은 값은 원 논문 E_l의 4배입니다.", 19, MUTED)
    return image


@figure("a6c-3", 560, 280)
def a6c_weights():
    weights = [1e3 / n ** 2 for n in STYLE_NS]
    texts = ["0.244140625", "0.06103515625", "0.0152587890625", "0.003814697265625", "0.003814697265625"]
    assert [repr(w) for w in weights] == texts and all(w * n * n == 1000 for w, n in zip(weights, STYLE_NS))
    assert [n * n for n in STYLE_NS] == [4096, 16384, 65536, 262144, 262144]
    image, d = _new(560)
    _title(d, "계수 × Gram 행렬 원소 수는 다섯 층 모두 1000")
    d.rounded_rectangle((36, 80, 430, 520), 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (56, 106), "Gram 행렬 원소 수 n²", 20, INK, True, anchor="la")
    for k, n in enumerate(STYLE_NS):
        top = 150 + k * 72
        _t(d, (56, top), "층 %d · n=%d · %s" % (k + 1, n, "{:,}".format(n * n)), 19, INK, anchor="la")
        d.rectangle((56, top + 30, 410, top + 46), fill=LINE)
        d.rectangle((56, top + 30, 56 + 354 * n * n / 262144.0, top + 46), fill=BLUE)
    d.rounded_rectangle((450, 80, 730, 520), 12, fill="white", outline=LIGHT, width=2)
    _t(d, (590, 106), "계수 1e3/n²", 20, ORANGE, True, anchor="mm", code=True)
    for k, text in enumerate(texts):
        top = 158 + k * 72
        _t(d, (470, top), "층 %d" % (k + 1), 19, MUTED, anchor="la")
        _t(d, (712, top + 32), text, 19, INK, code=True, anchor="ra")
    d.rounded_rectangle((750, 80, 1084, 520), 12, fill="white", outline=BLUE, width=2)
    _t(d, (917, 106), "계수 × n²", 20, BLUE, True, anchor="mm")
    for k in range(5):
        x0 = 776 + k * 60
        d.rectangle((x0, 170, x0 + 44, 440), fill=BLUE)
        _t(d, (x0 + 22, 150), "1000", 19, BLUE, True, code=True, anchor="mm")
        _t(d, (x0 + 22, 466), "층 %d" % (k + 1), 19, MUTED, anchor="mm")
    return image


@figure("a6c-41", 520, 280)
def a6c_level7():
    assert 65536 // 4096 == 16
    image, d = _new(LH, LW)
    for k, (label, n, x0, cell, color, pale) in enumerate((("4,096칸", 4, 70, 50, BLUE, BLUE_L),
                                                            ("65,536칸", 7, 500, 50, ORANGE, ORANGE_L))):
        _t(d, (x0 + n * cell / 2.0, 40), label, LEVEL_MIN, INK, True, anchor="mm", low=LEVEL_MIN)
        d.rounded_rectangle((x0 - 8, 70, x0 + n * cell + 2, 70 + n * cell + 10), 8, fill=pale, outline=color, width=2)
        for r in range(n):
            for c in range(n):
                _t(d, (x0 + c * cell + cell / 2.0 - 3, 75 + r * cell + cell / 2.0), "1", LEVEL_MIN, color, anchor="mm",
                   low=LEVEL_MIN)
    d.rectangle((70, 470, 70 + 30, 500), fill=BLUE)
    d.rectangle((500, 470, 500 + 480, 500), fill=ORANGE)
    return image


@figure("a6c-42", 520, 280)
def a6c_level15():
    assert repr(1e3 / 512 ** 2) == "0.003814697265625" and 512 ** 2 == 262144 and round(1e3 / 50 ** 2, 9) == 0.4
    # levels.grid 는 표 폭이 1px 넘쳐 같은 꼴(위 식 한 줄, 회색 머리 행, 강조 칸 한 색)을 Pillow 로 그림
    image, d = _new(LH, LW)
    _t(d, (LW / 2.0, 70), "계수 = 1000 ÷ (채널 수 × 채널 수)", LEVEL_MIN + 3, INK, anchor="mm", low=LEVEL_MIN)
    heads = ["채널 수", "원소 수", "계수", "계수 × 원소 수"]
    rows = [["512", "262,144", "0.003814697265625", "1000"], ["50", "", "", ""]]
    widths = [max(_w(h, LEVEL_MIN), max(_w(r[c], LEVEL_MIN, c == 2, c == 2) for r in rows)) + 44 for c, h in enumerate(heads)]
    x0 = (LW - sum(widths)) / 2.0
    assert x0 >= 24, x0
    for r, row in enumerate([heads] + rows):
        x = x0
        for c, (text, width) in enumerate(zip(row, widths)):
            rect = (x, 150 + r * 110, x + width, 260 + r * 110)
            fill = NOTE if r == 0 else BLUE_L if (r, c) == (1, 2) else "white"
            d.rectangle(rect, fill=fill, outline=FAINT, width=3)
            if text:
                _t(d, ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0), text, LEVEL_MIN, MUTED if r == 0 else INK,
                   (r, c) == (1, 2), r > 0 and c == 2, anchor="mm", low=LEVEL_MIN)
            x += width
    return image


@figure("a6c-43", 520, 280)
def a6c_level20():
    blue = [1e3 / n ** 2 * n * n for n in STYLE_NS]
    orange = [1e3 / n * n * n for n in STYLE_NS]
    assert all(v == 1000 for v in blue) and orange[3] == 512000
    image, d = _new(LH, LW)
    _chip(d, (600, 50), "파랑 1e3 / n²", BLUE, BLUE_L, LEVEL_MIN, code=True)
    _chip(d, (880, 50), "주황 1e3 / n", ORANGE, ORANGE_L, LEVEL_MIN, code=True)
    base, top = 460, 110
    d.line((90, base, 1010, base), fill=LIGHT, width=3)
    d.line((90, top, 90, base), fill=LIGHT, width=3)
    scale = (base - top - 10) / float(max(orange))
    for k, n in enumerate(STYLE_NS):
        x0 = 140 + k * 175
        d.rectangle((x0, base - blue[k] * scale - 6, x0 + 50, base), fill=BLUE)
        d.rectangle((x0 + 60, base - orange[k] * scale, x0 + 110, base), fill=ORANGE)
        _t(d, (x0 + 55, base + 40), "n=%d" % n, LEVEL_MIN, INK, anchor="mm", code=True, low=LEVEL_MIN)
    _t(d, (30, 70), "계수 × 원소 수", LEVEL_MIN, MUTED, anchor="lm", low=LEVEL_MIN)
    return image


def _style_layers():
    """VGG19 다섯 블록의 합성곱 수와 스타일 층(블록마다 첫째), 콘텐츠 층(블록 4 둘째)."""
    blocks = [2, 2, 4, 4, 4]
    styles = [(b, 1) for b in range(1, 6)]
    content = (4, 2)
    return blocks, styles, content


@figure("a6c-4", 560, 260)
def a6c_layers():
    blocks, styles, content = _style_layers()
    weights = [1e3 / n ** 2 for n in STYLE_NS] + [1e0]
    texts = ["0.244140625", "0.06103515625", "0.0152587890625", "0.003814697265625", "0.003814697265625", "1"]
    assert sum(blocks) == 16 and [repr(w) for w in weights[:5]] == texts[:5] and weights[5] == 1.0
    image, d = _new(520)
    _title(d, "스타일 층 다섯과 콘텐츠 층 하나")
    cell, x = 27, 40
    for b, convs in enumerate(blocks, 1):
        width = convs * 2 * cell + 16
        d.rounded_rectangle((x, 90, x + width, 290), 10, fill=NOTE, outline=LIGHT, width=2)
        _t(d, (x + width / 2.0, 112), "블록 %d" % b, 19, INK, True, anchor="mm")
        for c in range(convs):
            cx = x + 8 + c * 2 * cell
            _cell(d, (cx, 190, cx + cell - 3, 236), "C", BLUE, BLUE, 19, "white", True, radius=4)
            relu = (cx + cell, 190, cx + 2 * cell - 3, 236)
            mark = ORANGE if (b, c + 1) in styles else GREEN if (b, c + 1) == content else None
            _cell(d, relu, "R", "white", mark or LIGHT, 19, mark or MUTED, bool(mark), width=3 if mark else 2, radius=4)
            if mark:
                letter = "S" if mark == ORANGE else "C"
                _cell(d, (relu[0] - 2, 146, relu[2] + 2, 180), letter, ORANGE_L if letter == "S" else GREEN_L, mark, 19,
                      mark, True, radius=6)
                _t(d, ((relu[0] + relu[2]) / 2.0, 260), "r%d%d" % (b, c + 1), 19, mark, True, code=True, anchor="mm")
        x += width + 14
    assert x <= W - 30, x
    _t(d, (40, 330), "C: 합성곱, R: ReLU, S: 스타일 층(주황), C 꼬리표: 콘텐츠 층(초록)", 19, MUTED)
    _t(d, (40, 390), "weights = style_weights + content_weights", 20, INK, code=True)
    line = "[" + ", ".join(texts) + "]"
    assert _w(line, 19, False, True) <= W - 80
    x = 40
    _t(d, (x, 440), "[", 19, INK, code=True, anchor="lm")
    x += _w("[", 19, False, True)
    for k, text in enumerate(texts):
        color = ORANGE if k < 5 else GREEN
        _t(d, (x, 440), text, 19, color, True, code=True, anchor="lm")
        _t(d, (x + _w(text, 19, True, True) / 2.0, 476), ["r11", "r21", "r31", "r41", "r51", "r42"][k], 19, color, code=True,
           anchor="mm")
        x += _w(text, 19, True, True)
        tail = ", " if k < 5 else "]"
        _t(d, (x, 440), tail, 19, INK, code=True, anchor="lm")
        x += _w(tail, 19, False, True)
    return image


@figure("a6c-5", 560, 260)
def a6c_scale():
    n, m = 6, 20
    values = [4, 4.0 / n ** 2, 2.0 / (n * m)]
    assert fmt(values[1], 3) == "0.111" and fmt(values[2], 4) == "0.0167"
    image, d = _new(520)
    _title(d, "손실의 상수 배는 기울기 방향을 바꾸지 않습니다")
    d.rounded_rectangle((36, 80, 640, 480), 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (56, 106), "원 논문 식과 비교한 상수 배", 20, INK, True, anchor="la")
    _chip(d, (620, 106), "N = 6, M = 20", BLUE, "white", 19, anchor="rm", code=True)
    rows = [("스타일 · 4", "4"), ("스타일 · 4/N²", "0.111"), ("콘텐츠 · 2/(N·M)", "0.0167")]
    for k, ((name, text), value) in enumerate(zip(rows, values)):
        top = 160 + k * 100
        _t(d, (56, top), name, 20, INK, anchor="la")
        _t(d, (620, top), text, 20, BLUE, True, code=True, anchor="ra")
        d.rectangle((56, top + 36, 620, top + 56), fill=LINE)
        d.rectangle((56, top + 36, 56 + max(4, 564 * value / 4.0), top + 56), fill=BLUE)
    d.rounded_rectangle((660, 80, 1084, 480), 12, fill="white", outline=LIGHT, width=2)
    _t(d, (680, 106), "기울기 화살표", 20, INK, True, anchor="la")
    for k, length in enumerate((360, 220, 110)):
        y = 200 + k * 90
        d.ellipse((684, y - 7, 698, y + 7), fill=INK)
        arrow(d, (691, y), (691 + length, y), BLUE, 6)
    _t(d, (872, 440), "길이만 다르고 방향은 같음", 19, BLUE, anchor="mm")
    return image


# a6d VGG19 features

def _features(avg=False):
    """VGG19 features 37칸의 종류 목록. 'C' 합성곱, 'R' ReLU, 'P' 풀링."""
    kinds = []
    for v in VGG19_CFG:
        kinds += ["P"] if v == "M" else ["C", "R"]
    return kinds


def _conv_positions():
    return [i for i, kind in enumerate(_features()) if kind == "C"]


def _a6d_numbers():
    kinds = _features()
    assert len(kinds) == 37 and kinds.count("C") == 16 and kinds.count("R") == 16 and kinds.count("P") == 5
    pos = _conv_positions()
    assert pos == [0, 2, 5, 7, 10, 12, 14, 16, 19, 21, 23, 25, 28, 30, 32, 34]
    assert dict(enumerate(pos, 1))[4] == 7 and dict(enumerate(pos))[4] == 10
    return kinds, pos


def _blocks_of(kinds):
    """블록마다 (시작, 끝) 위치. 끝은 그 블록의 풀링."""
    out, start = [], 0
    for i, kind in enumerate(kinds):
        if kind == "P":
            out.append((start, i))
            start = i + 1
    return out


def _strip(d, x0, y, cell, kinds, dashed=(), h=44, size=19):
    colors = {"C": (BLUE, BLUE, "white"), "R": ("white", LIGHT, MUTED), "P": (ORANGE, ORANGE, "white")}
    for i, kind in enumerate(kinds):
        rect = (x0 + i * cell, y, x0 + (i + 1) * cell - 4, y + h)
        if i in dashed:
            _dash(d, rect, LIGHT, 2, 5)
            _t(d, ((rect[0] + rect[2]) / 2.0, y + h / 2.0), kind, size, LIGHT, anchor="mm")
            continue
        fill, line, ink = colors[kind]
        _cell(d, rect, kind, fill, line, size, ink, True, radius=4)


@figure("a6d-1", 560, 200)
def a6d_count():
    kinds, _ = _a6d_numbers()
    image, d = _new(400)
    _title(d, "VGG19 features 37칸의 세 종류")
    cell, x0 = 28, 42
    for b, (s, e) in enumerate(_blocks_of(kinds), 1):
        _chip(d, (x0 + (s + e + 1) * cell / 2.0 - 2, 105), "블록 %d" % b, MUTED, NOTE, 19)
    _strip(d, x0, 140, cell, kinds, h=56)
    items = [(BLUE, "합성곱 16칸"), (MUTED, "ReLU 16칸"), (ORANGE, "MaxPool2d 5칸")]
    x = 42
    for color, text in items:
        _cell(d, (x, 250, x + 30, 280), "", color if color != MUTED else "white", color, radius=4)
        _t(d, (x + 42, 265), text, 20, INK, True, anchor="lm")
        x += 60 + _w(text, 20, True)
    _chip(d, (1076, 265), "16 + 16 + 5 = 37", INK, NOTE, 20, anchor="rm", code=True)
    _t(d, (42, 340), "C: 합성곱(Conv2d), R: ReLU, P: MaxPool2d(kernel_size=2, stride=2)", 19, MUTED)
    return image


@figure("a6d-2", 560, 280)
def a6d_pool():
    window = [[1, 3], [2, 6]]
    flat = [v for row in window for v in row]
    assert max(flat) == 6 and sum(flat) / 4.0 == 3
    image, d = _new(560)
    _title(d, "같은 2×2 창에서 최대 풀링과 평균 풀링")
    panels = [("최대 풀링", "가장 큰 값 하나", "6", [["0", "0"], ["0", "1"]], {(1, 1): BLUE}),
              ("평균 풀링", "(1 + 3 + 2 + 6) ÷ 4", "3", [["0.25", "0.25"], ["0.25", "0.25"]],
               {(0, 0): BLUE, (0, 1): BLUE, (1, 0): BLUE, (1, 1): BLUE})]
    for k, (name, how, out, grads, marks) in enumerate(panels):
        x0 = 36 + k * 530
        d.rounded_rectangle((x0, 80, x0 + 514, 520), 12, fill=NOTE, outline=LIGHT, width=2)
        _t(d, (x0 + 20, 106), name, 21, INK, True, anchor="la")
        _t(d, (x0 + 494, 108), how, 19, MUTED, anchor="ra")
        _t(d, (x0 + 30, 150), "2×2 창", 19, MUTED, anchor="la")
        _matrix(d, x0 + 30, 170, [[str(v) for v in row] for row in window], cw=70, ch=62, size=24,
                marks={(1, 1): BLUE} if k == 0 else {})
        arrow(d, (x0 + 200, 230), (x0 + 330, 230), INK, 4)
        _t(d, (x0 + 420, 160), "출력", 19, MUTED, anchor="mm")
        _cell(d, (x0 + 370, 190, x0 + 470, 270), out, BLUE_L, BLUE, 34, BLUE, True, width=3)
        _t(d, (x0 + 30, 320), "기울기 1을 넘김", 19, MUTED, anchor="la")
        _matrix(d, x0 + 30, 340, grads, cw=86 if k else 70, ch=62, size=22, marks=marks)
        arrow(d, (x0 + 370, 400), (x0 + 220, 400), ORANGE, 4)
        _cell(d, (x0 + 380, 360, x0 + 470, 440), "1", ORANGE_L, ORANGE, 30, ORANGE, True, width=3)
        _t(d, (x0 + 425, 470), "출력이 받은 기울기", 19, ORANGE, anchor="mm")
    return image


@figure("a6d-3", 560, 300)
def a6d_keys():
    kinds, pos = _a6d_numbers()
    layers = {1: "s", 2: "s", 3: "s", 4: "sc", 5: "s"}
    paper_style, paper_content = [1, 3, 5, 9, 13], 10
    names = {}
    for b, (s, e) in enumerate(_blocks_of(kinds), 1):
        for n, p in enumerate([p for p in pos if s <= p < e], 1):
            names[p] = "conv%d_%d" % (b, n)
    keyname = {k: names[p] for k, p in enumerate(pos, 1)}
    assert keyname[4] == "conv2_2" and [keyname[k] for k in paper_style] == ["conv1_1", "conv2_1", "conv3_1", "conv4_1",
                                                                             "conv5_1"]
    assert keyname[paper_content] == "conv4_2"
    image, d = _new(600)
    _title(d, "features 37칸과 합성곱 번호")
    cell, x0 = 25, 170
    _strip(d, x0, 80, cell, kinds, h=36)
    _t(d, (36, 154), "합성곱 번호", 19, BLUE, True, anchor="lm")
    _t(d, (36, 190), "위치", 19, MUTED, anchor="lm")
    for k, p in enumerate(pos, 1):
        cx = x0 + p * cell + (cell - 4) / 2.0
        _t(d, (cx, 154), str(k), 19, BLUE, True, code=True, anchor="mm")
        _t(d, (cx, 190), str(p), 19, MUTED, code=True, anchor="mm")
    rows = [("layers", 240, BLUE), ("원 논문", 380, PURPLE)]
    for name, top, color in rows:
        d.rounded_rectangle((30, top, 1090, top + (100 if name == "layers" else 180)), 12, fill="white", outline=color, width=2)
        _t(d, (46, top + 34), name, 20, color, True, code=name == "layers", anchor="lm")
    for k, use in layers.items():
        cx = x0 + pos[k - 1] * cell + (cell - 4) / 2.0
        text = use.upper()
        _cell(d, (cx - 20, 256, cx + 20, 292), text, ORANGE_L if use == "s" else GREEN_L, ORANGE if use == "s" else GREEN, 19,
              ORANGE if use == "s" else GREEN, True, radius=6)
    _t(d, (46, 314), "스타일: 키 1~5, 콘텐츠: 키 4(conv2_2)", 19, MUTED, anchor="lm")
    for n, k in enumerate(paper_style + [paper_content]):
        cx = x0 + pos[k - 1] * cell + (cell - 4) / 2.0
        style = k != paper_content
        color = ORANGE if style else GREEN
        _cell(d, (cx - 14, 396, cx + 14, 432), "S" if style else "C", ORANGE_L if style else GREEN_L, color, 19, color, True,
              radius=6)
        y = 462 if k != paper_content else 502
        _t(d, (cx, y), keyname[k], 19, color, True, code=True, anchor="mm")
    _t(d, (46, 535), "스타일 키 1, 3, 5, 9, 13 · 콘텐츠 키 10", 19, MUTED, anchor="lm")
    return image


@figure("a6d-4", 560, 220)
def a6d_cut():
    kinds, pos = _a6d_numbers()
    cut = pos[15] + 1
    assert cut == 35 and len(kinds[:cut]) == 35 and kinds[cut - 1] == "C" and kinds[35] == "R" and kinds[36] == "P"
    assert kinds[:cut].count("P") == 4 and len(kinds[:cut - 1]) == 34 and kinds[cut - 2] == "R"
    image, d = _new(440)
    _title(d, "위치 34까지 잘라 35칸 남기기")
    cell, x0 = 28, 42
    _chip(d, (560, 105), "[:conv_indices[16] + 1] = [:35]", RED, "white", 20, code=True)
    _strip(d, x0, 150, cell, kinds, dashed=(35, 36), h=52)
    xc = x0 + 35 * cell - 2
    _dash_line(d, (xc, 128, xc, 230), RED, 3, 7)
    _chip(d, (42, 280), "35칸 남음", BLUE, BLUE_L, 20, anchor="lm")
    _t(d, (42, 330), "위치 34 · conv5_4 (마지막 합성곱)", 20, INK, True, anchor="lm")
    _t(d, (1078, 280), "빠지는 칸: 위치 35 ReLU, 위치 36 평균 풀링", 19, MUTED, anchor="rm")
    d.line((x0 + 35 * cell + 12, 206, x0 + 35 * cell + 12, 262), fill=LIGHT, width=2)
    _t(d, (42, 400), "P: 평균 풀링(AvgPool2d). 남은 평균 풀링은 4개입니다.", 19, MUTED)
    return image


def _pool_sizes(h, w, times=4):
    out = [(h, w)]
    for _ in range(times):
        h, w = h // 2, w // 2
        out.append((h, w))
    return out


@figure("a6d-5", 560, 240)
def a6d_sizes():
    sizes = _pool_sizes(128, 170)
    assert sizes == [(128, 170), (64, 85), (32, 42), (16, 21), (8, 10)]
    assert _pool_sizes(128, 161, 2) == [(128, 161), (64, 80), (32, 40)]
    groups = ["합성곱 1~2", "합성곱 3~4", "합성곱 5~8", "합성곱 9~12", "합성곱 13~16"]
    image, d = _new(480)
    _title(d, "평균 풀링을 지날 때마다 높이와 너비가 반")
    base = 330
    # 첫 칸이 넓어 칸 사이를 고르게 두지 않고, 화살표와 글자는 앞 칸 오른쪽 끝과 뒤 칸 왼쪽 끝의 가운데에 둠
    cxs = [120, 370, 580, 790, 1000]
    for k, ((h, w), group) in enumerate(zip(sizes, groups)):
        cx = cxs[k]
        _chip(d, (cx, 100), group, MUTED, NOTE, 19)
        d.rectangle((cx - w / 2.0, base - h, cx + w / 2.0, base), fill=BLUE_L, outline=BLUE, width=3)
        _t(d, (cx, base + 34), "%d×%d" % (h, w), 21, BLUE, True, code=True, anchor="mm")
        if k < 4:
            right, left = cx + w / 2.0, cxs[k + 1] - sizes[k + 1][1] / 2.0
            ax = (right + left) / 2.0
            assert ax - _w("평균 풀링", 19, True) / 2.0 >= right + 16 and ax + 32 <= left - 16, (k, right, left)
            _t(d, (ax, base - 90), "평균 풀링", 19, ORANGE, True, anchor="mm")
            arrow(d, (ax - 32, base - 60), (ax + 32, base - 60), ORANGE, 4)
    _t(d, (36, 430), "128×170 입력. 높이와 너비를 2로 나누고 소수점 아래는 버립니다(85 → 42, 21 → 10).", 19, MUTED)
    return image


# a6e 정규화

MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
CAFFE = [103.939, 116.779, 123.68]


def _norm(v, c):
    return (v - MEAN[c]) / STD[c]


def _a6e_numbers():
    assert fmt(_norm(0, 0), 4) == "−2.1179" and fmt(_norm(1, 0), 4) == "2.2489" and fmt(_norm(1, 2), 4) == "2.64"
    assert round(255 - CAFFE[0], 3) == 151.061 and -CAFFE[2] == -123.68 and round(255 - CAFFE[2], 2) == 131.32


@figure("a6e-1", 560, 230)
def a6e_range():
    _a6e_numbers()
    image, d = _new(460)
    _title(d, "R 채널 값 0~1이 정규화로 옮겨 가는 범위")
    lo, hi = -2.5, 2.5

    def px(v):
        return 260 + (v - lo) / (hi - lo) * 780

    _chip(d, (650, 100), "(값 − 0.485) ÷ 0.229", BLUE, BLUE_L, 20, code=True)
    top, bottom = 170, 360
    _t(d, (40, top), "R 채널 값", 20, INK, True, anchor="lm")
    _t(d, (40, bottom), "정규화한 값", 20, INK, True, anchor="lm")
    d.line((px(0) - 40, top, px(1) + 40, top), fill=MUTED, width=3)
    d.line((px(lo) + 10, bottom, px(hi) - 10, bottom), fill=MUTED, width=3)
    for v, label in ((0, "0"), (MEAN[0], "0.485"), (1, "1")):
        target = _norm(v, 0)
        d.line((px(v), top - 10, px(v), top + 10), fill=INK, width=3)
        _t(d, (px(v), top - 26), label, 19, BLUE if label == "0.485" else INK, code=True, anchor="mm")
        arrow(d, (px(v), top + 14), (px(target), bottom - 14), BLUE, 3)
        d.line((px(target), bottom - 10, px(target), bottom + 10), fill=INK, width=3)
        text = fmt(target, 4)
        _t(d, (px(target), bottom + 30), text, 20, ORANGE if text != "0" else BLUE, True, code=True, anchor="mm")
    _t(d, (36, 430), "평균과 같은 값 0.485는 0이 되고, 0~1 범위를 벗어난 값이 생깁니다.", 19, MUTED)
    return image


@figure("a6e-2", 560, 260)
def a6e_broadcast():
    shape = (3, 1, 1)
    target = (3, 128, 170)
    assert all(a == b or a == 1 for a, b in zip(shape, target))
    image, d = _new(520)
    _title(d, "(3, 1, 1) 평균이 (3, 128, 170)으로 늘어납니다")
    _t(d, (150, 110), "(3, 1, 1)", 22, INK, True, code=True, anchor="mm")
    chans = [("R", RED, RED_L), ("G", GREEN, GREEN_L), ("B", BLUE, BLUE_L)]
    for k, ((name, color, pale), mean) in enumerate(zip(chans, MEAN)):
        y = 150 + k * 80
        _cell(d, (70, y, 120, y + 56), name, pale, color, 21, color, True, code=False)
        _cell(d, (130, y, 250, y + 56), "%.3f" % mean, "white", LIGHT, 22)
    _chip(d, (420, 210), "높이 쪽으로 128", BLUE, "white", 19)
    _chip(d, (420, 290), "너비 쪽으로 170", BLUE, "white", 19)
    arrow(d, (330, 250), (510, 250), BLUE, 4)
    _t(d, (830, 96), "(3, 128, 170)", 22, INK, True, code=True, anchor="mm")
    for k, ((name, color, pale), mean) in enumerate(reversed(list(zip(chans, MEAN)))):
        off = (2 - k) * 50
        pts = [(600 + 2 * off - 50, 250 + off - 60), (860 + 2 * off - 50, 170 + off - 60),
               (960 + 2 * off - 50, 250 + off - 60), (700 + 2 * off - 50, 330 + off - 60)]
        d.polygon(pts, fill=pale, outline=color)
        d.line(pts + [pts[0]], fill=color, width=3)

        def at(u, v):
            # 판 위의 점. 앞 판이 v 0.27 위쪽을 덮으므로 이름과 값은 v 0.635 줄에 둠
            return (pts[0][0] + u * (pts[1][0] - pts[0][0]) + v * (pts[3][0] - pts[0][0]),
                    pts[0][1] + u * (pts[1][1] - pts[0][1]) + v * (pts[3][1] - pts[0][1]))

        _t(d, at(0.15, 0.635), name, 20, color, True, anchor="mm")
        _t(d, at(0.55, 0.635), "%.3f" % mean, 20, color, True, code=True, anchor="mm")
    _t(d, (36, 480), "크기가 1인 두 축이 128과 170으로 늘어나, 채널마다 모든 칸이 그 채널의 평균 하나로 채워집니다.", 19, MUTED)
    return image


@figure("a6e-3", 560, 260)
def a6e_two_ways():
    _a6e_numbers()
    caffe_lo = min(0 - m for m in CAFFE)
    caffe_hi = max(255 - m for m in CAFFE)
    net_lo = min(_norm(0, c) for c in range(3))
    net_hi = max(_norm(1, c) for c in range(3))
    assert round(caffe_lo, 3) == -123.68 and round(caffe_hi, 3) == 151.061
    assert fmt(net_lo, 4) == "−2.1179" and fmt(net_hi, 4) == "2.64"
    image, d = _new(520)
    _title(d, "Caffe 방식과 ImageNet 방식 전처리")
    rows = [("Caffe 방식", 80, BLUE, [("채널 순서", "BGR"), ("값 범위", "0~255"),
                                    ("평균 빼기", "B 103.939", "G 116.779 · R 123.68")],
             "%s ~ %s" % (fmt(caffe_lo, 3), fmt(caffe_hi, 3))),
            ("ImageNet 방식", 290, PURPLE, [("채널 순서", "RGB"), ("값 범위", "0~1"),
                                          ("평균 빼기", "R 0.485 · G 0.456", "B 0.406"),
                                          ("표준편차로 나누기", "R 0.229 · G 0.224", "B 0.225")],
             "%s ~ %s" % (fmt(net_lo, 4), fmt(net_hi, 4)))]
    for name, top, color, steps, result in rows:
        d.rounded_rectangle((36, top, 1084, top + 190), 12, fill=NOTE, outline=LIGHT, width=2)
        _chip(d, (56, top + 28), name, color, "white", 20, anchor="lm")
        x = 56
        widths = [110, 110, 230, 230][:len(steps)]
        for k, (step, width) in enumerate(zip(steps, widths)):
            rect = (x, top + 60, x + width, top + 170)
            d.rounded_rectangle(rect, 10, fill="white", outline=LIGHT, width=2)
            _t(d, (x + width / 2.0, top + 84), step[0], 19, MUTED, anchor="mm")
            for n, line in enumerate(step[1:]):
                _t(d, (x + width / 2.0, top + 118 + n * 30), line, 19, INK, True, code=True, anchor="mm")
            arrow(d, (x + width + 4, top + 115), (x + width + 22, top + 115), MUTED, 3)
            x += width + 26
        rect = (x, top + 60, 1064, top + 170)
        d.rounded_rectangle(rect, 10, fill=BLUE_L if color == BLUE else PURPLE_L, outline=color, width=3)
        _t(d, ((x + 1064) / 2.0, top + 88), "전처리한 값의 범위", 19, color, anchor="mm")
        _t(d, ((x + 1064) / 2.0, top + 128), result, 20, color, True, code=True, anchor="mm")
    _t(d, (36, 494), "두 방식의 평균은 255로 나누고 순서를 맞추면 소수 둘째 자리까지 같지만, 값의 범위는 크게 다릅니다.", 19, MUTED)
    return image


def _clip_counts():
    """시험용 이미지 (3, 16, 256): 줄마다 픽셀 값 0~255. ImageNet 방식 정규화 뒤 바로 자른 값과 되돌린 뒤 자른 값."""
    zero = one = mid = 0
    bins = [0] * 8
    for c in range(3):
        for _ in range(16):
            for p in range(256):
                x = (p / 255.0 - MEAN[c]) / STD[c]
                cut = min(max(x, 0.0), 1.0)
                zero += cut == 0.0
                one += cut == 1.0
                mid += 0.0 < cut < 1.0
                back = min(max(x * STD[c] + MEAN[c], 0.0), 1.0)
                assert abs(back - p / 255.0) < 1e-7
                bins[min(int(back * 8), 7)] += 1
    return zero, one, mid, bins


@figure("a6e-4", 560, 280)
def a6e_clip():
    zero, one, mid, bins = _clip_counts()
    assert (zero, one, mid) == (5520, 4000, 2768) and zero + one == 9520 and zero + one + mid == 12288
    assert bins == [1536] * 8
    image, d = _new(560)
    _title(d, "정규화한 값을 바로 0~1로 자르면", "시험용 이미지 (3, 16, 256) · 값 12,288개")
    panels = [("바로 자름", RED, 36), ("되돌린 뒤 자름", GREEN, 576)]
    for name, color, x0 in panels:
        d.rounded_rectangle((x0, 80, x0 + 508, 450), 12, fill="white", outline=color, width=2)
        _t(d, (x0 + 20, 106), name, 21, color, True, anchor="la")
    base, top = 390, 178
    scale = (base - top) / 5520.0
    for k, (label, count, color) in enumerate((("0", zero, RED), ("0과 1 사이", mid, BLUE), ("1", one, RED))):
        cx = 120 + k * 170
        d.rectangle((cx - 40, base - count * scale, cx + 40, base), fill=color)
        _t(d, (cx, base - count * scale - 20), "{:,}개".format(count), 19, color, True, anchor="mm")
        _t(d, (cx, base + 24), label, 19, INK, anchor="mm")
    d.line((60, base, 520, base), fill=LIGHT, width=2)
    for k, count in enumerate(bins):
        x = 610 + k * 56
        d.rectangle((x, base - count * scale, x + 44, base), fill=BLUE)
    _t(d, (830, base - bins[0] * scale - 22), "칸마다 1,536개", 19, BLUE, True, anchor="mm")
    d.line((600, base, 1064, base), fill=LIGHT, width=2)
    _t(d, (606, base + 24), "0", 19, INK, code=True, anchor="mm")
    _t(d, (1058, base + 24), "1", 19, INK, code=True, anchor="mm")
    _t(d, (830, base + 24), "0~1을 여덟 칸으로 나눔", 19, MUTED, anchor="mm")
    _box(d, (36, 470, 544, 530), [("바로 자름: 9,520개가 0이나 1", RED, True, False)], fill=RED_L, outline=RED, size=20)
    _box(d, (576, 470, 1084, 530), [("되돌린 뒤 자름: 0~1에 고르게 퍼짐", GREEN, True, False)], fill=GREEN_L, outline=GREEN, size=20)
    return image


@figure("a6e-51", 520, 280)
def a6e_level7():
    values = list(range(10))
    minus = [round(v - 3.6, 1) for v in values]
    cut = [min(max(v, 0), 1) for v in minus]
    assert minus[4] == 0.4 and sum(1 for v in cut if v == 1) == 5
    image, d = _new(LH, LW)
    labels = ["원래 값", "3.6을 뺀 값", "자른 값"]
    x0, cw = 230, 78
    for r, label in enumerate(labels):
        y = 90 + r * 150
        _t(d, (24, y + 35), label, LEVEL_MIN, BLUE if r == 2 else MUTED, r == 2, anchor="lm", low=LEVEL_MIN)
        for c in range(10):
            rect = (x0 + c * cw, y, x0 + (c + 1) * cw - 8, y + 70)
            mark = c == 4
            if r == 0:
                _cell(d, rect, str(values[c]), BLUE_L if mark else "white", BLUE if mark else LIGHT, LEVEL_MIN + 3, INK, mark,
                      low=LEVEL_MIN)
            elif r == 1:
                _cell(d, rect, fmt(minus[c], 1), BLUE_L if mark else NOTE, BLUE if mark else LIGHT, LEVEL_MIN - 3 if c < 4 else
                      LEVEL_MIN, INK, mark, low=LEVEL_MIN - 3 if c < 4 else LEVEL_MIN)
            else:
                _cell(d, rect, "0.4" if mark else "", BLUE_L if mark else "white", BLUE if mark else LIGHT, LEVEL_MIN, BLUE, True,
                      low=LEVEL_MIN)
    return image


@figure("a6e-52", 520, 280)
def a6e_level15():
    rows = []
    for p in (103, 104, 105):
        v = round(p - CAFFE[0], 3)
        rows.append([str(p), fmt(v, 3), fmt(min(max(v, 0), 1), 3)])
    assert rows == [["103", "−0.939", "0"], ["104", "0.061", "0.061"], ["105", "1.061", "1"]]
    assert fmt(min(max(117 - CAFFE[1], 0), 1), 3) == "0.221"
    return levels.grid(rows, col_names=("픽셀 값", "103.939를 뺀 값", "자른 값"), marks=[(1, 1), (1, 2)], color="blue",
                       top="B 값 = 픽셀 값 − 103.939")


@figure("a6e-53", 520, 280)
def a6e_level20():
    m, s = MEAN[0], STD[0]
    xs = [0, 0.2, m, 0.6, round(m + s, 3), 0.85, 1]
    good = list(xs)
    bad = [float("nan") if x < m else min(max((x - m) / s, 0), 1) * s + m for x in xs]
    assert round(m + s, 3) == 0.714 and round(min(max((0.2 - m) / s, 0), 1) * s + m, 3) == 0.485
    return levels.graph(xs, [(good, "blue", "good"), (bad, "orange", "bad")], "원래 값", "돌려받은 값",
                        marks=[(m, m, "0.485", "orange"), (round(m + s, 3), round(m + s, 3), "0.714", "orange")],
                        xlim=(0, 1.22), ylim=(0, 1.08))


@figure("a6e-5", 560, 260)
def a6e_resize():
    w, h = 960, 760
    new_w = int(w * 128 / float(h))
    wrong_h = int(h * 128 / float(w))
    assert round(w * 128 / float(h), 2) == 161.68 and new_w == 161 and wrong_h == 101
    assert int(960 * 128 / 720.0) == 170
    image, d = _new(520)
    _title(d, "Resize(128)은 짧은 변을 128로 맞춥니다")
    s1 = 0.3
    x0, y0 = 70, 120
    d.rectangle((x0, y0, x0 + w * s1, y0 + h * s1), fill=NOTE, outline=MUTED, width=3)
    d.line((x0 + w * s1 + 1, y0, x0 + w * s1 + 1, y0 + h * s1), fill=ORANGE, width=6)
    _t(d, (x0 + w * s1 / 2.0, y0 - 20), "960", 20, INK, code=True, anchor="mm")
    _t(d, (x0 + w * s1 + 16, y0 + h * s1 / 2.0), "760", 20, ORANGE, True, code=True, anchor="lm")
    _t(d, (x0 + w * s1 / 2.0, y0 + h * s1 / 2.0), "960×760", 22, INK, True, code=True, anchor="mm")
    _t(d, (x0 + w * s1 / 2.0, y0 + h * s1 + 26), "짧은 변 760", 19, ORANGE, anchor="mm")
    _chip(d, (530, 230), "Resize(128)", BLUE, BLUE_L, 20, code=True)
    arrow(d, (460, 270), (600, 270), BLUE, 5)
    s2 = 1.5
    x1, y1 = 700, 140
    d.rectangle((x1, y1, x1 + new_w * s2, y1 + 128 * s2), fill=BLUE_L, outline=BLUE, width=3)
    _dash(d, (x1, y1, x1 + 128 * s2, y1 + wrong_h * s2), RED, 3, 8)
    d.line((x1 + new_w * s2 + 1, y1, x1 + new_w * s2 + 1, y1 + 128 * s2), fill=ORANGE, width=6)
    _t(d, (x1 + new_w * s2 / 2.0, y1 - 20), "161", 20, BLUE, True, code=True, anchor="mm")
    _t(d, (x1 + new_w * s2 + 16, y1 + 64 * s2), "128", 20, ORANGE, True, code=True, anchor="lm")
    _t(d, (x1 + new_w * s2 / 2.0 + 30, y1 + 128 * s2 - 30), "161×128", 22, BLUE, True, code=True, anchor="mm")
    _t(d, (x1 + 12, y1 + 20), "128×101", 19, RED, code=True, anchor="la")
    _box(d, (630, 360, 1084, 420), [("점선: 긴 변을 128로 맞췄다고 잘못 읽은 128×101", RED, False, False)], fill=RED_L, outline=RED,
         size=19)
    _cell(d, (300, 450, 820, 500), "960 × 128 ÷ 760 = 161.68 → 161", NOTE, LIGHT, 21)
    return image


# a6f 갱신 루프와 LBFGS

@figure("a6f-1", 560, 250)
def a6f_epoch():
    image, d = _new(500)
    _title(d, "한 에폭은 다섯 칸을 차례로 지납니다")
    steps = [("zero_grad", None), ("층별 손실", None), ("총손실", "10 × loss_c + 1e5 × loss_s"), ("backward", None), ("step", None)]
    widths = [150, 150, 330, 150, 140]
    x = 36
    centers = []
    for k, ((name, sub), width) in enumerate(zip(steps, widths)):
        last = k == 4
        rect = (x, 110, x + width, 200)
        d.rounded_rectangle(rect, 12, fill=BLUE if last else "white", outline=BLUE if last or k == 2 else LIGHT, width=3)
        if sub:
            _t(d, (x + width / 2.0, 138), name, 20, INK, True, anchor="mm")
            _t(d, (x + width / 2.0, 174), sub, 19, INK, code=True, anchor="mm")
        else:
            _t(d, (x + width / 2.0, 155), name, 21, "white" if last else INK, True, code=name in ("zero_grad", "backward", "step"),
               anchor="mm")
        centers.append(x + width / 2.0)
        if k < 4:
            arrow(d, (x + width + 4, 155), (x + width + 22, 155), MUTED, 3)
        x += width + 26
    assert x - 26 <= W - 30, x
    for k, cx in enumerate(centers):
        _t(d, (cx, 90), "%d단계" % (k + 1), 19, MUTED, anchor="mm")
    gx = centers[4]
    arrow(d, (gx, 204), (gx, 300), BLUE, 6)
    _box(d, (gx - 110, 306, gx + 110, 390), [("gen", BLUE, True, True), ("픽셀 값 갱신", BLUE, False, False)], fill=BLUE_L,
         outline=BLUE, size=21, width=3)
    d.rounded_rectangle((36, 300, 420, 400), 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (60, 330), "고정한 model", 21, INK, True, anchor="lm")
    _t(d, (60, 368), "requires_grad=False", 19, MUTED, code=True, anchor="lm")
    _lock(d, 380, 350, MUTED, 0.9)
    _chip(d, (560, 350), "바뀌지 않음", MUTED, NOTE, 19)
    _t(d, (36, 460), "step은 옵티마이저 목록에 든 gen만 바꿉니다. 에폭마다 loss_c와 loss_s는 0에서 다시 셉니다.", 19, MUTED)
    return image


@figure("a6f-2", 560, 260)
def a6f_targets():
    layers = {1: "s", 2: "s", 3: "s", 4: "sc", 5: "s"}
    content = [k for k, u in layers.items() if "c" in u]
    style = [k for k, u in layers.items() if "s" in u]
    assert content == [4] and style == [1, 2, 3, 4, 5] and len(content) + len(style) == 6 and 6 * 300 == 1800
    image, d = _new(520)
    _title(d, "목표 값은 루프 앞에서 한 번 구합니다")
    d.rounded_rectangle((36, 80, 1084, 220), 12, fill=NOTE, outline=LIGHT, width=2)
    _chip(d, (56, 108), "루프 앞 · 한 번 · 목표 값 6개", INK, "white", 19, anchor="lm")
    _box(d, (60, 136, 540, 204), [("content_img의 키 4 특징 맵 → content_targets", GREEN, True, False)], fill="white",
         outline=GREEN, size=19)
    _box(d, (580, 136, 1060, 204), [("style_img의 키 1~5 Gram 행렬 → style_grams", ORANGE, True, False)], fill="white",
         outline=ORANGE, size=19)
    # 루프 상자와 꼬리표를 먼저 그리고 화살표를 그 위에 그어 머리가 루프 안에서 보이게 함
    d.rounded_rectangle((36, 300, 1084, 460), 12, fill=BLUE_L, outline=BLUE, width=3)
    tag = _chip(d, (56, 300), "for epoch in range(300):", BLUE, "white", 20, anchor="lm", code=True)
    _box(d, (300, 340, 820, 420), [("gen의 특징 맵", BLUE, True, False), ("에폭마다 다시 구함", MUTED, False, False)], fill="white",
         outline=BLUE, size=20, gap=6)
    assert tag[2] + 20 <= 400
    arrow(d, (400, 208), (400, 336), GREEN, 4)
    arrow(d, (720, 208), (720, 336), ORANGE, 4)
    _t(d, (416, 262), "콘텐츠 목표 1개", 19, GREEN, anchor="lm")
    _t(d, (736, 262), "스타일 목표 5개", 19, ORANGE, anchor="lm")
    _t(d, (36, 494), "루프 안에서 목표 값까지 다시 구하면 300 에폭에 part(...)를 1,800번 더 부릅니다.", 19, MUTED)
    return image


@figure("a6f-3", 560, 260)
def a6f_log():
    marks = [e + 1 for e in range(300) if (e + 1) % 50 == 0]
    assert marks == list(range(50, 301, 50)) == [50, 100, 150, 200, 250, 300] and len(range(50, 300, 50)) == 5
    image, d = _new(520)
    _title(d, "300 에폭 동안 손실은 6번 기록됩니다")
    # 실제 손실을 돌려 보지 않았으므로 곡선 대신 줄마다 같은 높이의 점으로 기록하는 자리만 그림
    x0, x1, base = 190, 1040, 360

    def px(e):
        return x0 + (x1 - x0) * e / 300.0

    d.line((x0, base, x1 + 20, base), fill=MUTED, width=2)
    for e in (0, 50, 100, 150, 200, 250, 300):
        d.line((px(e), base - 6, px(e), base + 6), fill=MUTED, width=2)
        _t(d, (px(e), base + 24), str(e), 19, INK, code=True, anchor="mm")
    _t(d, ((x0 + x1) / 2.0, base + 60), "마친 에폭 수 (epoch + 1)", 19, INK, anchor="mm")
    for e in marks:
        _dash_line(d, (px(e), 130, px(e), base - 10), LINE, 2, 6)
    for name, y, color in (("스타일 손실", 170, ORANGE), ("콘텐츠 손실", 270, GREEN)):
        _t(d, (x0 - 24, y), name, 20, color, True, anchor="rm")
        d.line((x0, y, x1, y), fill=LINE, width=2)
        for e in marks:
            d.ellipse((px(e) - 9, y - 9, px(e) + 9, y + 9), fill=color)
    _t(d, (36, 470), "점은 epoch + 1이 50, 100, 150, 200, 250, 300일 때만 있습니다. 점의 높이는 손실 값이 아닙니다.", 19, MUTED)
    return image


LBFGS = {"max_iter1_calls_per_step": 1, "default_calls": 3, "returns": ["3.0", "1.3333", "0.0"]}


def _lbfgs_frame(k):
    image, d = _new(520)
    _title(d, "LBFGS의 step과 closure 호출 수", "optimizer.step(closure)")
    d.rounded_rectangle((36, 80, 1084, 250), 12, fill="white", outline=LIGHT, width=2)
    _chip(d, (56, 108), "max_iter=1", INK, NOTE, 20, anchor="lm", code=True)
    shown = 1 if k == 0 else 5
    for s in range(shown):
        x = 70 + s * 200
        _cell(d, (x, 140, x + 150, 190), "step %d" % (s + 1), BLUE_L, BLUE, 20, BLUE, True)
        d.ellipse((x + 20, 205, x + 36, 221), fill=PURPLE)
        _t(d, (x + 44, 213), "closure", 19, PURPLE, anchor="lm")
    _t(d, (1064, 108), "closure %d번" % (shown * LBFGS["max_iter1_calls_per_step"]), 20, PURPLE, True, anchor="rm")
    if k == 2:
        d.rounded_rectangle((36, 270, 1084, 470), 12, fill=BLUE_L, outline=BLUE, width=2)
        _chip(d, (56, 298), "기본값 max_iter=20", INK, "white", 20, anchor="lm", code=True)
        _cell(d, (70, 330, 400, 380), "step 1 (한 번)", "white", BLUE, 20, BLUE, True)
        for c in range(LBFGS["default_calls"]):
            x = 80 + c * 130
            d.ellipse((x, 400, x + 16, 416), fill=PURPLE)
            _t(d, (x + 24, 408), "closure %d" % (c + 1), 19, PURPLE, anchor="lm")
        _t(d, (1064, 298), "closure 3번", 20, PURPLE, True, anchor="rm")
        _t(d, (1064, 360), "Σ(p − 1)²을 줄이면", 19, INK, code=True, anchor="rm")
        _t(d, (1064, 400), "p = [0, 0, 0] → [1, 1, 1]", 20, INK, True, code=True, anchor="rm")
    lines = ["max_iter=1에서 step을 한 번 부르면 closure도 한 번 불립니다.", "step을 다섯 번 부르면 closure도 다섯 번 불립니다.",
             "기본값에서는 step 한 번 안에서 closure가 세 번 불립니다."]
    _t(d, (36, 494), lines[k], 21, INK, anchor="lm")
    return image


@figure("a6f-4", 560, 260)
def a6f_closure():
    return [_lbfgs_frame(k) for k in range(3)], [2200, 2200, 2400]


def _history(steps=6, size=2):
    """history_size 개까지 남기는 기록. step 1 은 비교할 앞 step 이 없어 넣지 않음. step 마다 (남은 기록, 빠진 기록)."""
    kept, out = [], []
    for step in range(1, steps + 1):
        dropped = None
        if step > 1:
            kept.append(step)
            if len(kept) > size:
                dropped = kept.pop(0)
        out.append((list(kept), dropped))
    return out


@figure("a6f-5", 560, 270)
def a6f_history():
    rows = _history()
    assert [len(k) for k, _ in rows] == [0, 1, 2, 2, 2, 2] and [x for _, x in rows] == [None, None, None, 2, 3, 4]
    image, d = _new(540)
    _title(d, "history_size=2이면 old_dirs에 두 칸만 남습니다")
    for s, (kept, dropped) in enumerate(rows):
        x = 40 + s * 176
        _t(d, (x + 76, 100), "step %d" % (s + 1), 20, INK, True, code=True, anchor="mm")
        if dropped:
            _cell(d, (x + 6, 124, x + 146, 164), "", RED_L, RED, radius=6)
            _t(d, (x + 76, 144), "step %d 기록" % dropped, 19, RED, anchor="mm")
            d.line((x + 20, 144, x + 132, 144), fill=RED, width=2)
        d.rounded_rectangle((x, 180, x + 152, 380), 10, fill="white", outline=BLUE if kept else LIGHT, width=2)
        _t(d, (x + 8, 194), "old_dirs", 19, MUTED, code=True, anchor="la")
        for n in range(2):
            rect = (x + 10, 228 + n * 74, x + 142, 290 + n * 74)
            order = list(reversed(kept))
            if n < len(order):
                new = n == 0
                _cell(d, rect, "", BLUE if new else BLUE_L, BLUE, radius=6)
                _t(d, ((rect[0] + rect[2]) / 2.0, rect[1] + 20), "step %d 기록" % order[n], 19, "white" if new else BLUE, True,
                   anchor="mm")
                _t(d, ((rect[0] + rect[2]) / 2.0, rect[1] + 44), "새 기록" if new else "이전 기록", 19,
                   "white" if new else MUTED, anchor="mm")
            else:
                _dash(d, rect, LIGHT, 2, 6)
                _t(d, ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0), "비어 있음", 19, LIGHT, anchor="mm")
        _t(d, (x + 76, 410), str(len(kept)), 24, INK, True, code=True, anchor="mm")
    _t(d, (36, 470), "len(old_dirs): 0, 1, 2, 2, 2, 2. 셋째 기록이 들어오는 step 4부터 가장 오래된 기록이 빠집니다.", 19, MUTED)
    return image
