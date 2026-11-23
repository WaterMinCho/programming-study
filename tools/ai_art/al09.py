# -*- coding: utf-8 -*-
"""AI 응용 9차시의 본문 그림과 세 수준 연습 그림을 작성함.

python -B -m tools.ai_art.al09 --all
python -B -m tools.ai_art.al09 a9a-1 a9a-31
"""
import argparse
from fractions import Fraction
from itertools import product
from math import cos, isclose, radians, sin, tau
from pathlib import Path
import sys

from tools.ai_art import COLORS, ROOT, figure, figures, fmt, iso, save
from tools.ai_art.levels import SIZE

INK, GRAY, FAINT = (COLORS[name] for name in ("ink", "muted", "faint"))
BLUE, RED, GREEN, PURPLE, ORANGE = (COLORS[name] for name in ("blue", "red", "green", "purple", "orange"))
BLUE_L, RED_L, GREEN_L, PURPLE_L, ORANGE_L = "#dbeafe", "#fee2e2", "#d1fae5", "#ede9fe", "#ffedd5"
PANEL, WHITE = "#f8fafc", "#ffffff"
BODY = (560, 260)
RAY_SIZE = (560, 280)
DASH = (8, 7)


def sheet(size=BODY):
    return iso.Sheet(2 * size[0], 2 * size[1])


def mid(s, x, y, value, size=34, color=INK, bold=False, code=False):
    return s.text((x, y), value, size, color, bold, code, anchor="mm")


def node(s, x, y, value, width, tone="gray", size=34, code=False):
    s.card((x, y), [value], tone, "seen", size=size, pad=(16, 16), width=width, code=code)


def oval(center, rx, ry, angle=0):
    x, y = center
    a = radians(angle)
    return [
        (x + rx * cos(t) * cos(a) - ry * sin(t) * sin(a),
         y + rx * cos(t) * sin(a) + ry * sin(t) * cos(a))
        for t in (tau * i / 72 for i in range(72))
    ]


def dot(s, point, color=BLUE, radius=8):
    s.poly(oval(point, radius, radius), color, WHITE, 2)


def lerp(start, end, fraction):
    return tuple(a + (b - a) * fraction for a, b in zip(start, end))


def camera(s, x, y):
    s.plate((x - 99, y - 34, x - 30, y + 34), PANEL, INK, 9, 4)
    s.poly([(x - 30, y - 18), (x, y - 26), (x, y + 26), (x - 30, y + 18)], BLUE_L, INK, 4)
    dot(s, (x, y), INK)


@figure("a9a-1", *BODY)
def triangle_projection():
    s = sheet()
    left = [(103, 349), (230, 154), (329, 302)]
    right = [(719, 339), (839, 174), (927, 300)]
    labels = ("A", "B", "C")
    assert len(set(left)) == len(set(right)) == len(labels) == 3

    bl, tl, tr, br = [(648, 393), (761, 100), (1034, 119), (931, 417)]
    s.poly([bl, tl, tr, br], PANEL, FAINT, 3)
    for t in (0.25, 0.5, 0.75):
        s.path([lerp(bl, br, t), lerp(tl, tr, t)], FAINT, 1.5)
        s.path([lerp(bl, tl, t), lerp(br, tr, t)], FAINT, 1.5)
    for x, points, color, fill in ((232, left, BLUE, BLUE_L), (825, right, PURPLE, PURPLE_L)):
        s.poly(points, fill, color, 4)
        for label, (px, py), (dx, dy) in zip(labels, points, [(-21, 20), (0, -30), (25, 14)]):
            dot(s, (px, py), color, 9)
            mid(s, px + dx, py + dy, label, 32, INK, True, True)
        mid(s, x, 459, "공간의 삼각형" if x < 500 else "카메라 이미지 평면", 34, INK, True)

    s.arrow((374, 258), (656, 258), GRAY, width=5, size=(24, 10))
    mid(s, 514, 216, "정점 투영", 32)
    return s.image()


def pixel_rays(s, origin, rect, pixels):
    left, top, right, bottom = rect
    cols, rows = 3, 4
    assert len(set(pixels)) == len(pixels)
    assert all(0 <= col < cols and 0 <= row < rows for col, row, _ in pixels)
    cell_w, cell_h = (right - left) / cols, (bottom - top) / rows
    s.plate(rect, PANEL, FAINT, 3, 3)
    for col in range(1, cols):
        x = left + col * cell_w
        s.path([(x, top), (x, bottom)], FAINT, 2)
    for row in range(1, rows):
        y = top + row * cell_h
        s.path([(left, y), (right, y)], FAINT, 2)
    for col, row, color in pixels:
        point = (left + (col + 0.5) * cell_w, top + (row + 0.5) * cell_h)
        dx, dy = point[0] - origin[0], point[1] - origin[1]
        scale = (s.width - 68 - origin[0]) / dx
        if dy < 0:
            scale = min(scale, (origin[1] - 42) / -dy)
        elif dy > 0:
            scale = min(scale, (s.height - 70 - origin[1]) / dy)
        assert scale > 1
        end = lerp(origin, point, scale)
        s.arrow(origin, end, color, width=4.5, size=(21, 10))
        dot(s, point, color, 10)
    camera(s, *origin)


@figure("a9a-2", *RAY_SIZE)
def rays_from_camera():
    s = sheet(RAY_SIZE)
    pixel_rays(s, (222, 270), (513, 124, 735, 416), [(0, 0, BLUE), (1, 1, PURPLE), (1, 3, ORANGE)])
    mid(s, 182, 356, "카메라 위치 o", 32, INK, True)
    mid(s, 623, 463, "이미지 평면의 픽셀", 33, INK, True)
    mid(s, 905, 526, "광선마다 방향 d가 다릅니다.", 30, GRAY)
    return s.image()


@figure("a9a-31", *SIZE)
def rays_practice():
    s = sheet(SIZE)
    pixel_rays(s, (207, 267), (456, 135, 654, 395), [(0, 0, BLUE), (1, 2, PURPLE), (2, 3, ORANGE)])
    mid(s, 169, 350, "카메라", 35, INK, True)
    mid(s, 555, 460, "픽셀", 35, INK, True)
    return s.image()


@figure("a9a-32", *SIZE)
def ray_direction_practice():
    s = sheet(SIZE)
    world, origin = (262, 157), (504, 157)
    o = (2, 0, 0)
    d = (0, 0, -1)
    t = 2
    assert sum(component ** 2 for component in d) == 1 and t > 0
    assert origin[0] - world[0] == 121 * o[0] and d[2] < 0

    s.arrow((172, 157), (889, 157), GRAY, width=3)
    s.arrow((262, 107), (262, 456), GRAY, width=3)
    mid(s, 917, 157, "x", 34, INK, code=True)
    mid(s, 262, 484, "−z", 34, INK, code=True)
    dot(s, world, GRAY)
    mid(s, 264, 83, "(0, 0, 0)", 34, GRAY, code=True)

    s.arrow(origin, (504, 445), BLUE, width=6, size=(24, 11))
    dot(s, origin)
    mid(s, 504, 99, "o = %s" % (o,), 36, INK, True, True)
    mid(s, 692, 311, "d = (0, 0, −1)", 36, BLUE, True, True)
    mid(s, 504, 491, "방향 표시", 32, GRAY)
    node(s, 834, 450, "t = %d" % t, 155, "blue", 36, True)
    return s.image()


def matrix(s, x, y, values, accent=None):
    step, dy = 39, 50
    for row, cells in enumerate(values):
        for col, value in enumerate(cells):
            marked = (row, col) == accent
            if marked:
                px, py = x + col * step, y + row * dy
                s.plate((px - 18, py - 22, px + 18, py + 22), BLUE_L, None, 4)
            mid(s, x + col * step, y + row * dy, value, 31, BLUE if marked else INK, marked, True)
    left, right = x - 28, x + 3 * step + 28
    top, bottom = y - 25, y + 3 * dy + 25
    s.path([(left + 9, top), (left, top), (left, bottom), (left + 9, bottom)], GRAY, 3)
    s.path([(right - 9, top), (right, top), (right, bottom), (right - 9, bottom)], GRAY, 3)


@figure("a9a-33", *SIZE)
def translated_camera_practice():
    s = sheet(SIZE)
    shift = 3
    identity = [[int(i == j) for j in range(4)] for i in range(4)]
    translated = [row[:] for row in identity]
    translated[0][3] = shift
    camera_origin = (0, 0, 0, 1)
    assert [sum(v * c for v, c in zip(row, camera_origin)) for row in translated] == [3, 0, 0, 1]

    mid(s, 154, 76, "단위 행렬", 35, INK, True)
    mid(s, 408, 76, "이동 행렬", 35, INK, True)
    matrix(s, 95, 157, identity)
    matrix(s, 350, 157, translated, accent=(0, 3))
    s.path([(540, 72), (540, 470)], FAINT, 2)
    s.arrow((600, 221), (972, 221), GRAY, width=3)
    mid(s, 985, 194, "x", 33, code=True)
    for x, color in [(640, GRAY), (875, BLUE)]:
        s.arrow((x, 221), (x, 355), color, width=5, size=(20, 10))
        dot(s, (x, 221), color)
    mid(s, 640, 173, "o", 35, GRAY, True, True)
    mid(s, 875, 173, "o′", 35, BLUE, True, True)
    s.arrow((648, 114), (866, 114), BLUE, width=4, size=(20, 9))
    mid(s, 755, 77, "x로 3 이동", 34, BLUE, True)
    mid(s, 685, 424, "o = (0, 0, 0)", 34, code=True)
    mid(s, 765, 481, "두 카메라의 방향은 같습니다.", 32, GRAY)
    return s.image()


@figure("a9b-1", *BODY)
def position_and_direction():
    s = sheet()
    node(s, 145, 137, "위치 x", 200, "blue")
    node(s, 444, 137, "위치 특징", 207, "blue")
    node(s, 145, 361, "시선 d", 200, "orange")
    node(s, 909, 137, "밀도 σ(x)", 303, "blue", code=True)
    node(s, 909, 361, "색 RGB(x, d)", 303, "purple")
    s.arrow((249, 137), (332, 137), BLUE, width=4)
    s.arrow((552, 137), (749, 137), BLUE, width=4)
    s.path([(612, 137), (612, 361)], BLUE, 4)
    s.path([(249, 361), (612, 361)], ORANGE, 4)
    dot(s, (612, 361), PURPLE, 9)
    s.arrow((620, 361), (749, 361), PURPLE, width=4)
    mid(s, 909, 198, "위치로 계산합니다.", 30, GRAY)
    mid(s, 909, 422, "위치와 시선으로 계산합니다.", 30, GRAY)
    return s.image()


@figure("a9b-2", *BODY)
def tiny_nerf_encoding():
    s = sheet()
    coords = ("x", "y", "z")
    frequencies = [2 ** k for k in range(2)]
    bands = [(fn, freq) for freq in frequencies for fn in ("sin", "cos")]
    original, encoded = len(coords), len(coords) * len(bands)
    assert (original, encoded, original + encoded) == (3, 12, 15)

    mid(s, 560, 58, "Tiny NeRF  ·  L = %d 예시" % len(frequencies), 37, INK, True)
    headers = ["원래 좌표"] + [fn + ("(u)" if freq == 1 else "(2u)") for fn, freq in bands]
    for i, header in enumerate(headers):
        x = 130 + i * 215
        mid(s, x, 146, header, code=i != 0, color=BLUE if i else INK)
        for row, coord in enumerate(coords):
            y = 211 + row * 58
            s.plate((x - 93, y - 26, x + 93, y + 26), BLUE_L if i else PANEL, FAINT, 5, 2)
            if i:
                fn, freq = bands[i - 1]
                value = fn + "(" + (str(freq) if freq > 1 else "") + coord + ")"
            else:
                value = coord
            mid(s, x, y, value, 34, code=True)
    mid(s, 560, 443, "원래 좌표 %d개 + sin·cos 값 %d개 = %d개" % (original, encoded, original + encoded), 38, INK, True)
    return s.image()


@figure("a9c-1", *BODY)
def stratified_sampling():
    s = sheet()
    x0, x1, count = 139, 956, 3
    bounds = [x0 + (x1 - x0) * i / count for i in range(count + 1)]
    offsets = [0.29, 0.7, 0.45]
    samples = [a + (b - a) * k for a, b, k in zip(bounds, bounds[1:], offsets)]
    assert len(samples) == count and all(a < x < b for a, x, b in zip(bounds, samples, bounds[1:]))
    assert all(isclose(b - a, (x1 - x0) / count) for a, b in zip(bounds, bounds[1:]))

    for i, (a, b, x) in enumerate(zip(bounds, bounds[1:], samples), start=1):
        s.plate((a, 176, b, 307), BLUE_L if i % 2 else PANEL, FAINT, 0, 2)
        mid(s, (a + b) / 2, 368, "구간 %d" % i, 35)
        mid(s, x, 129, "표본", 31, BLUE)
        s.path([(x, 152), (x, 228)], BLUE, 3, dash=DASH)
    s.arrow((85, 242), (1032, 242), GRAY, width=4, size=(21, 10))
    for x in bounds:
        s.path([(x, 161), (x, 328)], GRAY, 2)
    for x in samples:
        dot(s, (x, 242), BLUE, 13)
    mid(s, x0, 430, "near", 36, INK, True, True)
    mid(s, x1, 430, "far", 36, INK, True, True)
    mid(s, 1054, 242, "t", 32, code=True)
    mid(s, 560, 472, "같은 길이로 나누고 각 구간에서 한 점을 무작위로 뽑습니다.", 32, GRAY)
    return s.image()


@figure("a9c-2", *BODY)
def alpha_composite():
    s = sheet()
    front = rear = Fraction(1, 2)
    weights = [front, (1 - front) * rear, (1 - front) * (1 - rear)]
    assert weights == [Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)] and sum(weights) == 1

    s.arrow((88, 169), (1029, 169), GRAY, width=4, size=(22, 10))
    for x, label, info, tone, width in [
        (252, "앞 빨간색", "α = " + fmt(front), "red", 225),
        (575, "뒤 파란색", "α = " + fmt(rear), "blue", 225),
        (897, "배경", "남은 빛", "gray", 190),
    ]:
        node(s, x, 169, label, width, tone)
        mid(s, x, 238, info, 32, code=tone != "gray")
    mid(s, 560, 307, "최종 픽셀의 색을 섞는 가중치", 34, INK, True)
    x = 86
    for weight, fill, line in zip(weights, [RED_L, BLUE_L, PANEL], [RED, BLUE, GRAY]):
        right = x + 948 * weight
        s.plate((x, 346, right, 432), fill, line, 0, 3)
        mid(s, (x + right) / 2, 389, fmt(weight), 41, INK, True, True)
        x = right
    return s.image()


def filter_practice(level):
    s = sheet(SIZE)
    if level == 1:
        entries, names, last = ("절반 통과", "절반 통과"), ("앞 필터", "뒤 필터"), "얼마나 남을까요?"
    else:
        values = (0.25, 0.5) if level == 2 else (1, 0.5)
        assert all(0 <= a <= 1 for a in values)
        entries = tuple("α = " + fmt(a) for a in values)
        names = ("앞 표본", "뒤 표본")
        last = "뒤 표본의 가중치는?" if level == 2 else "뒤쪽 색이 섞일까요?"
    s.arrow((124, 266), (893, 266), GRAY, width=5, size=(22, 10))
    mid(s, 110, 219, "빛" if level == 1 else "광선", 34, GRAY, True)
    for x, entry, name, tone in zip((349, 666), entries, names, ("red", "blue")):
        fill, edge, _ = iso.TONES[tone]
        s.poly([(x - 46, 200), (x + 33, 172), (x + 46, 331), (x - 33, 360)], fill, edge, 4)
        mid(s, x, 112, name, 36, INK, True)
        node(s, x, 421, entry, 222, tone, 35, level != 1)
    mid(s, 838, 421, "?", 50, PURPLE, True)
    mid(s, 779, 490, last, 34, GRAY)
    return s.image()


@figure("a9c-41", *SIZE)
def filter_beginner():
    return filter_practice(1)


@figure("a9c-42", *SIZE)
def filter_intermediate():
    return filter_practice(2)


@figure("a9c-43", *SIZE)
def filter_advanced():
    return filter_practice(3)


def rgb_thumbnail(s, x, y, tiles):
    cell = 43
    for row, colors in enumerate(tiles):
        for col, color in enumerate(colors):
            x0, y0 = x + col * cell, y + row * cell
            s.plate((x0, y0, x0 + cell, y0 + cell), color, WHITE, 0, 2)


@figure("a9d-1", *BODY)
def color_training_loop():
    s = sheet()
    node(s, 157, 201, "NeRF 가중치", 235, "blue")
    s.arrow((283, 201), (412, 201), BLUE, width=4)
    mid(s, 350, 165, "렌더링", 30, GRAY)
    for x, label, tiles in [
        (450, "합성 RGB", [[PANEL, BLUE_L, PANEL], [BLUE_L, RED_L, BLUE], [PANEL, BLUE, PANEL]]),
        (851, "촬영 RGB", [[PANEL, BLUE_L, PANEL], [BLUE, ORANGE_L, BLUE], [PANEL, BLUE, PANEL]]),
    ]:
        mid(s, x + 64, 102, label, 35, INK, True)
        rgb_thumbnail(s, x, 137, tiles)
        s.path([(x + 64, 277), (x + 64, 317)], GRAY, 3)
    s.path([(514, 317), (915, 317)], GRAY, 3)
    s.arrow((714.5, 317), (714.5, 364), GRAY, width=3)
    node(s, 715, 414, "RGB 오차", 270, "purple")
    s.path([(570, 414), (157, 414), (157, 254)], PURPLE, 4, dash=DASH)
    s.arrow((157, 280), (157, 242), PURPLE, width=4)
    mid(s, 362, 378, "오차 역전파로 가중치 갱신", 32, PURPLE)
    return s.image()


@figure("a9d-2", *BODY)
def rgb_mse():
    s = sheet()
    target = (0, 1, 0)
    prediction = (Fraction(3, 10), Fraction(7, 10), 0)
    squares = [(p - t) ** 2 for t, p in zip(target, prediction)]
    mse = sum(squares) / len(squares)
    assert squares == [Fraction(9, 100), Fraction(9, 100), 0] and mse == Fraction(6, 100)

    x_columns = (498, 731, 960)
    rows = [
        ("정답", target),
        ("예측", prediction),
        ("차이의 제곱", squares),
    ]
    for x, name, color in zip(x_columns, "RGB", [RED, "#047857", BLUE]):
        mid(s, x, 105, name, 39, color, True, True)
    for i, (label, values) in enumerate(rows):
        y = 179 + i * 75
        s.plate((53, y - 33, 1067, y + 33), BLUE_L if i == 2 else PANEL, None, 9)
        s.text((78, y), label, 35, INK, True, anchor="lm")
        for x, value in zip(x_columns, values):
            mid(s, x, y, fmt(value), 38, INK, i == 2, True)
    mid(s, 560, 428, "MSE = (%s) / %d = %s" % (" + ".join(fmt(v) for v in squares), len(squares), fmt(mse)),
        42, INK, True, True)
    return s.image()


def ellipsoid(s, center, rx, ry, angle, color, fill):
    s.poly(oval(center, rx, ry, angle), fill, color, 4)
    s.path(oval(center, rx, ry * 0.36, angle), color, 2.5, closed=True)
    s.path(oval(center, rx * 0.34, ry, angle), color, 2.5, dash=DASH, closed=True)
    dot(s, center, color, 7)


def ellipse_overlap(s, first, second):
    from PIL import Image, ImageChops, ImageDraw

    masks = []
    for points in (first, second):
        mask = Image.new("1", s.big.size)
        ImageDraw.Draw(mask).polygon(s._p(points), fill=1)
        masks.append(mask)
    s.big.paste(BLUE_L, (0, 0, *s.big.size), masks[0])
    s.big.paste(ORANGE_L, (0, 0, *s.big.size), masks[1])
    s.big.paste(PURPLE_L, (0, 0, *s.big.size), ImageChops.logical_and(*masks))
    s.path(first, BLUE, 4, closed=True)
    s.path(second, ORANGE, 4, dash=(10, 6), closed=True)


@figure("a9e-1", *BODY)
def splat_projection():
    s = sheet()
    mid(s, 268, 96, "3차원 가우시안", 36, INK, True)
    mid(s, 863, 96, "2D 화면의 타원", 36, INK, True)
    ellipsoid(s, (190, 288), 113, 70, -32, BLUE, BLUE_L)
    ellipsoid(s, (363, 224), 93, 61, 34, ORANGE, ORANGE_L)
    mid(s, 261, 407, "퍼짐을 타원체로 표시", 30, GRAY)
    s.arrow((481, 251), (646, 251), GRAY, width=5, size=(24, 10))
    mid(s, 562, 203, "카메라 투영", 30, GRAY)
    s.plate((678, 145, 1047, 381), PANEL, FAINT, 9, 3)
    ellipse_overlap(s, oval((812, 255), 111, 51, -27), oval((901, 262), 112, 62, 21))
    s.path([(864, 276), (864, 396)], PURPLE, 2.5, dash=DASH)
    dot(s, (864, 276), PURPLE, 7)
    mid(s, 864, 420, "같은 픽셀 영역에 겹칩니다.", 30, GRAY)
    return s.image()


@figure("a9e-2", *BODY)
def different_spread():
    s = sheet()
    for x, tone, label, spread in [(295, "blue", "좁은 퍼짐", (75, 44)), (825, "purple", "넓은 퍼짐", (147, 87))]:
        fill, color, dark = iso.TONES[tone]
        y = 247
        s.plate((x - 212, 120, x + 212, 374), PANEL, FAINT, 8, 2)
        s.poly(oval((x, y), *spread, -17), fill, color, 4)
        s.path([(x - 179, y), (x + 179, y)], GRAY, 2, dash=DASH)
        s.path([(x, y - 103), (x, y + 103)], GRAY, 2, dash=DASH)
        dot(s, (x, y), INK, 9)
        mid(s, x, 418, label, 35, dark, True)
    mid(s, 560, 64, "중심 좌표는 같습니다.", 37, INK, True)
    return s.image()


CUBE = tuple(product((-1, 1), repeat=3))
CUBE_EDGES = [(i, j) for i, a in enumerate(CUBE) for j, b in enumerate(CUBE)
              if i < j and sum(u != v for u, v in zip(a, b)) == 1]


def frame(s, x, y, angle, size):
    s.plate((x - size, y - size, x + size, y + size), PANEL, FAINT, 8, 2.5)
    scale = size * 0.46
    a = radians(angle)
    tilt = radians(19)
    points = []
    for cx, cy, cz in CUBE:
        u = cos(a) * cx - sin(a) * cy
        depth = sin(a) * cx + cos(a) * cy
        assert isclose(u * u + depth * depth, cx * cx + cy * cy)
        v = cos(tilt) * cz - sin(tilt) * depth
        points.append((x + scale * u, y - scale * v))
    assert all(abs(px - x) < size and abs(py - y) < size for px, py in points)
    for i, j in CUBE_EDGES:
        s.path([points[i], points[j]], GRAY, 2.5)
    s.path([points[6], points[7]], BLUE, 4)
    dot(s, points[7], BLUE, 7)


@figure("a9f-1", *BODY)
def cube_to_sequence():
    s = sheet()
    assert len(CUBE) == 8 and len(CUBE_EDGES) == 12
    s.box(98, 184, 126, 126, 72, "new")
    for point in dict.fromkeys(sum(iso.box_faces(98, 184, 126, 126, 72).values(), [])):
        dot(s, point, BLUE, 6)
    mid(s, 186, 371, "큐브 정점", 34, INK, True)
    s.arrow((319, 228), (467, 228), GRAY, width=4, size=(23, 10))
    mid(s, 397, 176, "정사영", 31, GRAY)
    for i, (x, angle) in enumerate(zip((566, 768, 970), (12, 33, 54)), start=1):
        frame(s, x, 228, angle, 76)
        mid(s, x, 353, "프레임 %d" % i, 31)
    s.arrow((489, 411), (1038, 411), BLUE, width=4, size=(20, 9))
    mid(s, 767, 454, "시간 순서", 33, BLUE, True)
    return s.image()


@figure("a9f-2", *BODY)
def cnn_lstm_scores():
    s = sheet()
    for y, angle in zip((141, 254, 367), (12, 33, 54)):
        frame(s, 109, y, angle, 43)
        s.arrow((162, y), (228, y), GRAY, width=3)
        node(s, 289, y, "CNN", 109, "gray", 29, True)
        s.arrow((352, y), (412, y), GRAY, width=3)
        node(s, 486, y, "D차원", 133, "blue", 33)
        s.path([(561, y), (577, y), (577, 254)], BLUE, 3)
    mid(s, 109, 448, "프레임별 입력", 29, GRAY)
    mid(s, 484, 448, "프레임별 특징", 29, GRAY)
    s.arrow((577, 254), (664, 254), BLUE, width=4)
    mid(s, 631, 198, "(B,T,D)", 30, BLUE, True, True)
    node(s, 738, 254, "LSTM", 136, "purple", 35, True)
    s.path([(813, 254), (842, 254), (842, 176)], PURPLE, 3)
    s.path([(842, 254), (842, 332)], PURPLE, 3)
    s.arrow((842, 176), (881, 176), PURPLE, width=3)
    s.arrow((842, 332), (881, 332), PURPLE, width=3)
    node(s, 996, 176, "시계 점수", 213, "purple", 31)
    node(s, 996, 332, "반시계 점수", 213, "purple", 31)
    mid(s, 737, 347, "시간 순서 처리", 29, GRAY)
    return s.image()


def star(center, radius):
    x, y = center
    points = []
    for i in range(10):
        angle = -tau / 4 + i * tau / 10
        r = radius * 0.44 if i % 2 else radius
        points.append((x + r * cos(angle), y + r * sin(angle)))
    return points


@figure("a9f-41", *SIZE)
def reordered_frames_practice():
    s = sheet(SIZE)
    order = ("나", "가", "다")
    angles = {"가": -110, "나": -50, "다": 10}
    assert set(order) == set(angles) and order != tuple(angles)
    for x, name in zip((174, 520, 866), order):
        y, radius = 257, 69
        s.plate((x - 111, y - 122, x + 111, y + 122), PANEL, FAINT, 10, 3)
        s.path(oval((x, y), radius, radius), FAINT, 3, dash=DASH, closed=True)
        a = radians(angles[name])
        tip = (x + radius * cos(a), y + radius * sin(a))
        s.path([(x, y), tip], GRAY, 3)
        dot(s, (x, y), GRAY, 7)
        s.poly(star(tip, 26), COLORS["highlight"], "#c2410c", 3)
        mid(s, x, 429, name, 40, INK, True)
    for x in (303, 649):
        s.arrow((x, 257), (x + 86, 257), GRAY, width=4, size=(20, 9))
    return s.image()


@figure("a9f-42", *SIZE)
def cnn_feature_count_practice():
    s = sheet(SIZE)
    b, t, d = 2, 4, 8
    starts = (138, 588)
    assert len(starts) == b and (t, d) == (4, 8)
    mid(s, 520, 79, "B = %d     T = %d     D = %d" % (b, t, d), 42, INK, True, True)
    for i, x in enumerate(starts, start=1):
        s.stack(x, 215, 318, 195, n=1, rows=t, cols=d, thick=9, default="new")
        mid(s, x + 159, 161, "영상 %d" % i, 35, INK, True)
        mid(s, x + 159, 450, "프레임당 특징 D개", 32, BLUE)
    for i in range(t):
        y = 215 + (i + 0.5) * 195 / t
        mid(s, 103, y, str(i + 1), 31, GRAY, code=True)
    mid(s, 520, 503, "각 행은 한 프레임의 CNN 특징입니다.", 32, GRAY)
    return s.image()


@figure("a9f-43", *SIZE)
def lstm_last_feature_practice():
    s = sheet(SIZE)
    positions = (223, 420, 619, 818)
    s.arrow((130, 104), (917, 104), GRAY, width=3, size=(19, 8))
    mid(s, 524, 67, "시간 T", 35, INK, True)
    for x, value in zip(positions, ("h_1", "h_2", "…", "h_T")):
        last = x == positions[-1]
        node(s, x, 207, value, 128, "purple" if last else "blue", 36, True)
    s.path([(151, 278), (151, 299), (888, 299), (888, 278)], BLUE, 4)
    mid(s, 493, 349, "전체 시퀀스", 35, BLUE, True)
    s.path([(895, 207), (965, 207), (965, 363), (854, 363)], PURPLE, 3.5)
    s.arrow((870, 363), (842, 363), PURPLE, width=3.5)
    mid(s, 895, 409, "마지막 특징", 33, PURPLE, True)
    mid(s, 520, 489, "영상 B개에 각각 적용  ·  각 시점의 특징은 H개", 33, GRAY)
    return s.image()


def main():
    parser = argparse.ArgumentParser(description="AI 응용 9차시 그림을 저장합니다.")
    parser.add_argument("names", nargs="*", metavar="그림 이름")
    parser.add_argument("--all", action="store_true", help="9차시 그림 21개를 저장합니다.")
    args = parser.parse_args()
    if args.all == bool(args.names):
        parser.error("--all 또는 그림 이름을 입력하세요.")
    registered = {name: fn for name, _, _, fn in figures(sys.modules[__name__])}
    names = list(registered) if args.all else list(dict.fromkeys(args.names))
    unknown = [name for name in names if name not in registered]
    if unknown:
        parser.error("등록된 그림 이름을 확인하세요. " + ", ".join(unknown))
    out_dir = Path(ROOT) / "ai" / "learn" / "al09" / "assets"
    for name in names:
        path = save(name, registered[name](), out_dir)
        print(Path(path).relative_to(ROOT))


if __name__ == "__main__":
    main()
