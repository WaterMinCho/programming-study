# -*- coding: utf-8 -*-
"""응용 10차시 본문과 세 수준 블록 그림을 그림.

Pillow가 있는 Python에서 python -B -m tools.ai_art.al10 을 실행함.
그림 이름을 인자로 주면 해당 그림만 저장함.
"""
import argparse
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
import sys

from tools.ai_art import COLORS, FONTS, LIMITS, ROOT, figure, figures, iso

SIZE = (520, 280)
INK, BLUE, RED, PURPLE = (COLORS[key] for key in ("ink", "blue", "red", "purple"))
BLUE_D, RED_D, PURPLE_D = "#1d4ed8", "#b91c1c", "#6d28d9"
BLUE_L, RED_L, PURPLE_L = "#dbeafe", "#fee2e2", "#ede9fe"
WHITE, RULE, PANEL = "#ffffff", "#d1d5db", "#f8fafc"


@lru_cache(maxsize=40)
def font(size, bold, code):
    from PIL import ImageFont

    family = "D2Coding" if code else "NanumGothic"
    weight = "Bold" if bold else "Regular"
    return ImageFont.truetype(Path(FONTS) / f"{family}-{weight}.ttf", size)


class Sheet(iso.Sheet):
    def _face(self, size, bold, code):
        return font(round(size * self.ss), bold, code)


def sheet(title, accent=BLUE):
    s = Sheet(1040, 560, ss=3)
    s.plate((48, 41, 60, 80), accent, accent, 5)
    s.text((78, 60), title, 44, INK, True, anchor="lm")
    return s


def center(s, x, y, value, size=33, color=INK, bold=False, code=False):
    return s.text((x, y), value, size, color, bold, code, anchor="mm")


def left(s, x, y, value, size=33, color=INK, bold=False, code=False):
    return s.text((x, y), value, size, color, bold, code, anchor="lm")


def box(s, bounds, fill=PANEL, line=RULE):
    s.plate(bounds, fill, line, 18, 2)


def arrow(s, start, end, color=INK, width=4):
    s.arrow(start, end, color, width=width, size=(18, 9))


def dot(s, x, y, color, r=8):
    s.d.ellipse(
        ((x - r) * s.ss, (y - r) * s.ss, (x + r) * s.ss, (y + r) * s.ss),
        fill=color,
    )


def cat_scene(s, x, y, masked):
    """동일한 고양이 윤곽에 배경만 다르게 그림."""
    w, h = 202, 144
    s.plate((x, y, x + w, y + h), "#e5e7eb" if masked else BLUE_L, RULE, 14, 2)
    if not masked:
        dot(s, x + 163, y + 32, "#eab308", 14)
        s.poly([(x + 8, y + 126), (x + 40, y + 79), (x + 78, y + 126)], "#93c5fd")
        s.poly([(x + 119, y + 126), (x + 177, y + 76), (x + 195, y + 126)], "#93c5fd")
    head = [(53, 89), (57, 31), (83, 52), (119, 52), (145, 31), (149, 89),
            (145, 111), (126, 128), (77, 128), (57, 111)]
    s.poly([(x + a, y + b) for a, b in head], "#fde68a", INK, 4)
    for eye in (82, 121):
        dot(s, x + eye, y + 83, INK, 4)
    s.poly([(x + 95, y + 97), (x + 107, y + 97), (x + 101, y + 104)], INK)
    for a, b in ((66, 28), (136, 174)):
        for dy in (-6, 6):
            s.path([(x + a, y + 99), (x + b, y + 99 + dy)], INK, 2)


@figure("a10a-1", *SIZE)
def fixed_target():
    s = sheet("입력만 바꾸고 대상은 고정")
    s.text((989, 59), "가상 예시", 32, BLUE_D, True, anchor="rm")
    box(s, (253, 103, 787, 164), BLUE_L, BLUE)
    center(s, 520, 134, "두 입력의 대상 c는 고양이", 36, BLUE_D, True)
    for x, masked, label, score in (
        (51, False, "원본", Fraction(82, 100)), (531, True, "배경을 가린 입력", Fraction(39, 100))
    ):
        box(s, (x, 187, x + 458, 454))
        center(s, x + 229, 227, label, 35, INK, True)
        cat_scene(s, x + 23, 268, masked)
        center(s, x + 337, 315, "모델 점수", 31)
        center(s, x + 337, 371, f"{float(score):.2f}", 58, BLUE_D, True, True)
    assert Fraction(82, 100) - Fraction(39, 100) == Fraction(43, 100)
    center(s, 520, 511, "이 점수는 확률이 아니며 차이만으로 인과를 판단할 수 없습니다.", 31)
    return s.image()


@figure("a10b-1", *SIZE)
def kernel_and_maps():
    s = sheet("커널 가중치와 특징 맵", PURPLE)
    out_channels, in_channels, height, width, kernel = 16, 1, 28, 28, 3
    out_height, out_width = height - kernel + 1, width - kernel + 1
    assert (out_height, out_width) == (26, 26)
    box(s, (272, 105, 768, 244), PURPLE_L, PURPLE)
    center(s, 520, 133, "커널 가중치", 33, PURPLE_D, True)
    center(s, 520, 174, "[out, in, kH, kW]", 33, INK, code=True)
    center(s, 520, 215, f"[{out_channels}, {in_channels}, {kernel}, {kernel}]", 36, PURPLE_D, True, True)
    arrow(s, (520, 249), (520, 313), PURPLE)

    box(s, (48, 301, 410, 463), BLUE_L, BLUE)
    box(s, (630, 301, 992, 463), BLUE_L, BLUE)
    center(s, 229, 335, "입력 이미지 배치", 34, BLUE_D, True)
    center(s, 229, 377, "[N, Cin, H, W]", 31, INK, code=True)
    center(s, 229, 421, f"[2, {in_channels}, {height}, {width}]", 35, INK, True, True)
    center(s, 811, 335, "출력 특징 맵", 34, BLUE_D, True)
    center(s, 811, 377, "[N, Cout, H, W]", 31, INK, code=True)
    center(s, 811, 421, f"[2, {out_channels}, {out_height}, {out_width}]", 35, INK, True, True)
    arrow(s, (425, 377), (615, 377), BLUE)
    center(s, 520, 348, "3×3 합성곱", 30, BLUE_D, True)
    center(s, 520, 518, "stride 1 · 패딩 없음 · 이미지마다 출력 채널 16개", 33)
    return s.image()


def tiles(s, x, y, cell, fills, signs=()):
    for row, colors in enumerate(fills):
        for col, color in enumerate(colors):
            a, b = x + col * cell, y + row * cell
            s.plate((a, b, a + cell, b + cell), color, WHITE, 0, 2)
            if signs and signs[row][col]:
                center(s, a + cell / 2, b + cell / 2, signs[row][col], 35, INK, True, True)


@figure("a10c-1", *SIZE)
def cam_weights():
    s = sheet("CAM과 Grad-CAM의 채널 가중치", PURPLE)
    for y, model, tone, detail in (
        (103, "CAM", BLUE_D, "GAP 뒤 분류기에서 학습한 대상 가중치"),
        (168, "Grad-CAM", PURPLE_D, "채널마다 대상 점수 기울기를 공간 평균")
    ):
        box(s, (50, y, 990, y + 57))
        left(s, 76, y + 29, model, 34, tone, True, True)
        left(s, 291, y + 29, detail, 34)
    center(s, 190, 268, "채널별 가중합", 33, INK, True)
    center(s, 609, 268, "Grad-CAM", 31, PURPLE_D, True, True)
    center(s, 875, 268, "원본에 맞춘 위치", 30, BLUE_D, True)
    tiles(s, 103, 322, 46, (("#93c5fd", BLUE_L), (BLUE_L, BLUE_L)))
    tiles(s, 300, 322, 46, ((PURPLE_L, PURPLE_L), (PURPLE_L, "#93c5fd")))
    center(s, 75, 369, "w1×", 29, BLUE_D, True, True)
    center(s, 204, 369, "+", 34, INK, True, True)
    center(s, 270, 369, "w2×", 29, PURPLE_D, True, True)
    arrow(s, (406, 368), (473, 368), PURPLE)
    box(s, (485, 328, 723, 407), PURPLE_L, PURPLE)
    center(s, 604, 367, "가중합 후 ReLU", 30, PURPLE_D, True)
    arrow(s, (735, 368), (791, 368), BLUE)
    cat_scene(s, 799, 303, False)
    s.plate((807, 312, 897, 374), None, RED_D, 3, 4)
    s.plate((897, 374, 993, 438), None, RED_D, 3, 4)
    center(s, 520, 510, "작은 특징 맵을 원본에 맞춰 키워 대략적인 위치를 읽습니다.", 33)
    return s.image()


@figure("a10d-1", *SIZE)
def local_gradient():
    s = sheet("한 입력에서 읽는 기울기")
    left(s, 63, 122, "세로축은 대상 점수, 가로축은 입력", 33)
    for x, sign, color, label in (
        (278, 1, BLUE_D, "입력을 늘리면 점수가 오릅니다."),
        (762, -1, RED_D, "입력을 늘리면 점수가 내립니다."),
    ):
        assert abs(3 * sign) == 3
        center(s, x, 193, "+3" if sign == 1 else "−3", 61, color, True, True)
        arrow(s, (x - 172, 389), (x + 173, 389), INK, 3)
        arrow(s, (x - 160, 391), (x - 160, 242), INK, 3)
        s.path([(x, 391), (x, 308)], RULE, 3, dash=(5, 6))
        s.path([(x - 116, 309 + 54 * sign), (x + 116, 309 - 54 * sign)], color, 6)
        dot(s, x, 309, color)
        center(s, x, 412, "x0", 26, INK, code=True)
        center(s, x, 455, label, 30, color, True)
    center(s, 520, 510, "같은 크기 3 · 반대 방향 · x0 근처의 작은 변화", 34, INK, True)
    return s.image()


@figure("a10e-1", *SIZE)
def integrated_gradients():
    s = sheet("IG는 두 입력 사이의 기울기를 모읍니다.", PURPLE)
    baseline, observed = 0, 2
    difference = observed - baseline
    average = Fraction(observed**2 - baseline**2, difference)
    assert average == 2 and average * difference == 4

    origin_x, origin_y = 100, 389
    arrow(s, (origin_x, origin_y), (507, origin_y), INK, 3)
    arrow(s, (origin_x, origin_y), (origin_x, 131), INK, 3)
    center(s, 258, 155, "F(x) = x²", 36, PURPLE_D, True, True)
    s.path(
        [(origin_x + 170 * (i / 24), origin_y - 48 * (i / 24) ** 2) for i in range(49)],
        PURPLE, 6,
    )
    for x in (baseline, observed):
        px, py = origin_x + 170 * x, origin_y - 48 * x**2
        if x:
            s.path([(px, py), (px, origin_y)], RULE, 3, dash=(6, 6))
        dot(s, px, py, PURPLE)
    arrow(s, (104, 442), (440, 442), BLUE)
    center(s, 122, 482, "기준 0", 31, BLUE_D, True)
    center(s, 423, 482, "입력 2", 31, BLUE_D, True)

    box(s, (533, 123, 990, 471), PURPLE_L, PURPLE)
    left(s, 564, 166, "직선 위의 각 입력에서 미분", 33, PURPLE_D, True)
    center(s, 763, 225, "F'(x) = 2x", 40, INK, True, True)
    s.path([(567, 268), (955, 268)], PURPLE, 2)
    left(s, 564, 305, f"평균 기울기 {average}", 35)
    left(s, 564, 354, f"입력 차이 {difference}", 35)
    center(s, 763, 423, f"IG = {average} × {difference} = {average * difference}", 47, PURPLE_D, True, True)
    center(s, 520, 522, "경로에서 구한 기울기의 평균을 입력 차이에 곱합니다.", 32)
    return s.image()


@figure("a10f-1", *SIZE)
def deeplift_overlay():
    s = sheet("DeepLIFT는 기준 입력과 비교합니다.", PURPLE)
    s.path([(523, 106), (523, 466)], RULE, 2)
    left(s, 52, 127, "같은 모델의 활성 비교", 35, PURPLE_D, True)
    for y, label, symbol in ((162, "실제 입력", "활성 A"), (240, "기준 입력", "활성 A0")):
        box(s, (51, y, 218, y + 60), PANEL, RULE)
        center(s, 135, y + 30, label, 33, INK, True)
        arrow(s, (225, y + 30), (296, y + 30), PURPLE)
        box(s, (304, y, 473, y + 60), PURPLE_L, PURPLE)
        center(s, 388, y + 30, symbol, 33, PURPLE_D, True)
    s.path([(478, 192), (493, 192), (493, 309), (390, 309)], PURPLE, 3)
    s.path([(478, 270), (493, 270)], PURPLE, 3)
    arrow(s, (390, 309), (390, 327), PURPLE, 3)
    box(s, (51, 334, 474, 396), PURPLE_L, PURPLE)
    center(s, 262, 366, "활성 차이 A - A0", 35, PURPLE_D, True)
    center(s, 262, 436, "활성 차이를 따라 기여를 배분", 31, INK)

    left(s, 560, 127, "원본 위에 기여 표시", 35, BLUE_D, True)
    center(s, 765, 187, "CHW → HWC", 43, BLUE_D, True, True)
    center(s, 765, 231, "원본 이미지의 축 순서 변경", 31)
    cat_scene(s, 564, 263, False)
    s.plate((571, 270, 665, 334), None, RED_D, 3, 4)
    s.plate((665, 334, 759, 399), None, BLUE_D, 3, 4)
    tiles(s, 838, 263, 61, ((RED_L, PANEL), (PANEL, BLUE_L)), (("+", ""), ("", "−")))
    arrow(s, (832, 326), (776, 326), BLUE)
    center(s, 765, 438, "같은 공간 위치에 겹칩니다.", 30)
    s.path([(52, 474), (988, 474)], RULE, 2)
    center(s, 290, 516, "+ 대상 점수 증가에 기여", 34, RED_D, True)
    center(s, 750, 516, "- 대상 점수 감소에 기여", 34, BLUE_D, True)
    return s.image()



def thumbnail(s, x, y, w, h, scene=0):
    """배치 개념을 보여 주는 합성 사진을 그림."""
    sky, hill, sun = (
        (BLUE_L, "#93c5fd", "#eab308"),
        ("#ffedd5", "#c2410c", "#fde68a"),
        (PURPLE_L, "#9fb2c4", "#6d28d9"),
    )[scene]
    box(s, (x, y, x + w, y + h), sky, RULE)
    dx, dy = ((0.77, 0.27), (0.28, 0.23), (0.69, 0.30))[scene]
    dot(s, x + dx * w, y + dy * h, sun, h * 0.086)
    peaks = ((0.28, 0.32, 0.65, 0.45), (0.33, 0.53, 0.67, 0.37), (0.22, 0.44, 0.71, 0.29))
    a, b, c, d = peaks[scene]
    s.poly(
        [(x + 0.05 * w, y + 0.91 * h), (x + a * w, y + b * h),
         (x + 0.46 * w, y + 0.70 * h), (x + c * w, y + d * h),
         (x + 0.95 * w, y + 0.91 * h)],
        hill,
    )


@figure("a10b-31", *SIZE)
def batch_photos():
    s = sheet("사진을 모아 만든 배치")
    for i, x in enumerate((68, 386, 704)):
        thumbnail(s, x, 160, 268, 210, i)
    s.path([(68, 399), (68, 419), (972, 419), (972, 399)], BLUE, 5)
    s.path([(520, 419), (520, 448)], BLUE, 5)
    center(s, 520, 486, "배치", 42, BLUE_D, True)
    return s.image()


@figure("a10b-32", *SIZE)
def window_before_count():
    s = sheet("필터 창을 한 칸씩 옮기기")
    width, window = 9, 3
    start, size, top = 106, 92, 234
    end = start + width * size
    assert width == 9 and window == 3 and end == 934
    s.path([(start, 205), (start, 186), (end, 186), (end, 205)], INK, 4)
    center(s, 520, 152, "입력 너비 9", 39, INK, True)
    for col in range(width):
        x = start + col * size
        s.plate((x, top, x + size, top + size), BLUE_L if col < window else PANEL, RULE, 0, 2)
    s.plate((start, top, start + window * size, top + size), None, BLUE_D, 4, 5)
    center(s, start + window * size / 2, top + size / 2, "필터 창 3칸", 37, BLUE_D, True)
    arrow(s, (375, 367), (572, 367), BLUE_D, 6)
    center(s, 473, 410, "한 칸씩 이동", 34, BLUE_D, True)
    center(s, 520, 490, "창 전체가 띠 안에 들어가는 자리만 셉니다.", 37)
    return s.image()


@figure("a10b-33", *SIZE)
def pick_photo_then_channel():
    s = sheet("사진을 고른 다음 채널을 고릅니다", PURPLE)
    center(s, 236, 125, "사진마다 나온 특징맵", 35, INK, True)
    center(s, 783, 125, "선택한 사진의 채널", 35, PURPLE_D, True)
    for i, y in enumerate((168, 275, 382)):
        fill, edge = (PURPLE_L, PURPLE) if i == 1 else (PANEL, RULE)
        box(s, (67, y, 405, y + 87), fill, edge)
        thumbnail(s, 89, y + 10, 108, 67, i)
        s.stack(
            244, y + 26, 116, 49, n=3, rows=2, cols=3, thick=3,
            default="seen" if i == 1 else "normal", step=(12, -9),
        )
    arrow(s, (421, 319), (529, 319), PURPLE, 6)
    for i, x in enumerate((550, 708, 866)):
        y, cell = 250, 64
        border = BLUE_D if i == 1 else RULE
        fill = BLUE_L if i == 1 else PANEL
        tiles(s, x, y, cell, ((fill, fill), (fill, fill)))
        s.plate((x, y, x + 2 * cell, y + 2 * cell), None, border, 4, 5 if i == 1 else 2)
    arrow(s, (772, 435), (772, 386), BLUE_D, 6)
    center(s, 772, 465, "고른 채널", 34, BLUE_D, True)
    return s.image()


def slope_axes(s, x, top=164, bottom=435):
    arrow(s, (x - 172, bottom), (x + 177, bottom), INK, 3)
    arrow(s, (x - 159, bottom + 1), (x - 159, top), INK, 3)


@figure("a10d-31", *SIZE)
def tangent_direction():
    s = sheet("픽셀을 조금 밝게 하면")
    left(s, 66, 118, "대상 점수", 34, INK, True)
    for x, direction, color in ((268, 1, BLUE_D), (759, -1, RED_D)):
        slope_axes(s, x)
        def curve(t):
            return 302 - direction * 0.60 * t - 0.0018 * t * t

        samples = range(-124, 125, 4)
        s.path([(x + t, curve(t)) for t in samples], RULE, 4)
        s.path([(x - 68, 302 + direction * 0.60 * 68),
                (x + 68, 302 - direction * 0.60 * 68)], color, 7)
        dot(s, x, 302, color, 10)
        s.path([(x, 313), (x, 435)], RULE, 3, dash=(6, 7))
        arrow(s, (x, 479), (x + 100, 479), color, 4)
        center(s, x + 43, 518, "픽셀 값 증가", 34, color, True)
    return s.image()


@figure("a10d-32", *SIZE)
def two_slope_magnitudes():
    s = sheet("두 픽셀의 기울기 비교")
    left(s, 66, 119, "대상 점수", 34, INK, True)
    rise_per_unit, run_per_unit = 12, 36
    for x, slope, color in ((270, 2, BLUE_D), (764, -6, RED_D)):
        label = "+2" if slope == 2 else "−6"
        box(s, (x - 67, 123, x + 67, 199), BLUE_L if slope > 0 else RED_L, color)
        center(s, x, 161, label, 54, color, True, True)
        slope_axes(s, x, 216, 462)
        half_run = 1.35
        dx, dy = half_run * run_per_unit, half_run * rise_per_unit * slope
        s.path([(x - dx, 331 + dy), (x + dx, 331 - dy)], color, 7)
        dot(s, x, 331, color, 10)
    center(s, 520, 510, "가로축은 픽셀 값입니다.", 33)
    return s.image()


@figure("a10d-33", *SIZE)
def point_on_plateau():
    s = sheet("점수 곡선에서 현재 입력 보기", PURPLE)
    left(s, 75, 125, "대상 점수", 34, INK, True)
    x0, y0, bend, current, level = 111, 440, 403, 724, 211
    assert x0 < bend < current
    arrow(s, (x0, y0), (970, y0), INK, 4)
    arrow(s, (x0, y0), (x0, 170), INK, 4)
    s.path([(x0, y0), (bend, level), (935, level)], PURPLE, 7)
    s.path([(current, level), (current, y0)], RULE, 4, dash=(7, 7))
    dot(s, current, level, PURPLE_D, 13)
    center(s, current, 156, "현재 입력", 39, PURPLE_D, True)
    center(s, 876, 493, "픽셀 값", 35, INK, True)
    return s.image()


@figure("a10e-21", *SIZE)
def baseline_and_input():
    s = sheet("기준 입력에서 실제 입력까지", PURPLE)
    start, end, y = 183, 857, 303
    assert end > start
    arrow(s, (start, y), (end, y), PURPLE, 8)
    for x, value, label, color in ((start, 1, "기준 입력", BLUE_D), (end, 9, "실제 입력", PURPLE_D)):
        center(s, x, 177, label, 40, color, True)
        dot(s, x, y, color, 13)
        center(s, x, 407, str(value), 66, color, True, True)
    return s.image()


def linear_score_path(title, coefficient, baseline, observed, panel_title):
    s = sheet(title, PURPLE)
    origin_x, origin_y, x_scale, y_scale = 96, 437, 139, 40
    arrow(s, (origin_x, origin_y), (581, origin_y), INK, 4)
    arrow(s, (origin_x, origin_y), (origin_x, 154), INK, 4)
    left(s, 65, 120, "대상 점수", 33, INK, True)
    start = (origin_x + baseline * x_scale, origin_y - coefficient * baseline * y_scale)
    end = (origin_x + observed * x_scale, origin_y - coefficient * observed * y_scale)
    assert start[0] < end[0] < 570 and 157 < end[1] < start[1]
    if baseline:
        s.path([(origin_x, origin_y), start], RULE, 4, dash=(8, 8))
    for x, y in (start, end):
        if y != origin_y:
            s.path([(x, y), (x, origin_y)], RULE, 4, dash=(7, 7))
    s.path([start, end], PURPLE, 7)
    for x, y in (start, end):
        dot(s, x, y, PURPLE_D, 11)
    center(s, max(start[0], 117), 481, f"기준 {baseline}", 35, BLUE_D, True)
    center(s, end[0], 481, f"입력 {observed}", 35, BLUE_D, True)

    box(s, (618, 148, 982, 427), PURPLE_L, PURPLE)
    center(s, 800, 197, panel_title, 36, PURPLE_D, True)
    center(s, 800, 277, f"F(z) = {coefficient}z", 55, INK, True, True)
    center(s, 800, 363, f"기울기 {coefficient}", 43, PURPLE_D, True)
    return s.image()


@figure("a10e-22", *SIZE)
def constant_slope_three():
    return linear_score_path("경로에서 일정한 기울기 읽기", 3, 0, 2, "경로 위의 점수")


@figure("a10e-23", *SIZE)
def signed_contributions():
    s = sheet("두 기여의 크기와 방향", PURPLE)
    origin, scale = 430, 109
    s.path([(origin, 146), (origin, 443)], RULE, 4, dash=(7, 8))
    for value, label, y, color in ((4, "+4", 232, RED_D), (-1, "−1", 375, BLUE_D)):
        tip = origin + scale * value
        arrow(s, (origin, y), (tip, y), color, 11)
        dot(s, origin, y, color, 8)
        center(s, (origin + tip) / 2, y - 57, label, 51, color, True, True)
    return s.image()


@figure("a10e-2", *SIZE)
def formula_path():
    return linear_score_path("수식에서 기준과 입력 찾기", 2, 1, 3, "경로 위의 점수")


def main():
    from PIL import Image

    parser = argparse.ArgumentParser(description="AI 응용 10차시 그림을 저장합니다.")
    parser.add_argument("names", nargs="*", metavar="그림 이름")
    args = parser.parse_args()
    registered = {row[0]: row[1:] for row in figures(sys.modules[__name__])}
    missing = set(args.names) - registered.keys()
    if missing:
        parser.error("등록된 그림 이름을 확인하세요. " + ", ".join(sorted(missing)))

    out = Path(ROOT) / "ai" / "learn" / "al10" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    for name in dict.fromkeys(args.names or registered):
        width, height, render = registered[name]
        picture = render()
        assert picture.size == (2 * width, 2 * height)
        path = out / (name + ".png")
        picture.quantize(
            colors=LIMITS["colors"], dither=Image.Dither.NONE,
        ).save(path, optimize=True)
        assert path.stat().st_size <= LIMITS["png_bytes"]
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
