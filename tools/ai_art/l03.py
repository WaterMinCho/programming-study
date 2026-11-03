# -*- coding: utf-8 -*-
"""3차시 학습 노트(ai/learn/l03) 그림. matplotlib(Agg)과 Pillow 로 그려 ai/learn/l03/assets/ 에 씀.

그림 하나에 함수 하나이고 @figure(이름, 논리 폭, 논리 높이) 로 등록함. 파일은 논리 크기의 2배(폭 1120px)로 그림.
그림에 찍는 숫자는 같은 함수 안에서 다시 계산해 assert 로 맞춤. 텐서 동작(shape, squeeze, max, sum, 행렬곱)은
torch 없이 파이썬 리스트로 흉내 냄. 창을 띄우는 호출은 쓰지 않음.

  python tools/ai_art/l03.py            모든 그림
  python tools/ai_art/l03.py 3a-1 3d-2  고른 그림만
"""
import math
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "ai", "learn", "l03", "assets")
for _font in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf", "D2Coding-Regular.ttf", "D2Coding-Bold.ttf"):
    font_manager.fontManager.addfont(os.path.join(ROOT, "gui", "fonts", _font))
plt.rcParams.update({"font.family": ["NanumGothic", "DejaVu Sans"], "axes.unicode_minus": False, "font.size": 20,
                     "figure.facecolor": "white", "savefig.facecolor": "white", "axes.facecolor": "white",
                     "mathtext.fontset": "dejavusans", "axes.edgecolor": "#9ca3af", "xtick.labelsize": 17,
                     "ytick.labelsize": 17})

SCALE = 2  # 논리 픽셀 하나를 파일에서 2픽셀로 그림
DPI = 100
KB = 1024
LIMIT = {"gif": 250 * KB, "png": 150 * KB, "frames": 10, "ms_min": 1600, "ms_max": 2500, "width": 1120, "height": 600}
COLORS = 64  # GIF 팔레트 색 수

INK, MUTED, FAINT, PALE = "#1f2937", "#6b7280", "#d1d5db", "#f3f4f6"
BLUE, BLUE_BG = "#1d4ed8", "#dbeafe"
ORANGE, ORANGE_BG = "#c2410c", "#ffedd5"
GREEN, GREEN_BG = "#047857", "#d1fae5"
RED, RED_BG = "#b91c1c", "#fee2e2"
PURPLE, PURPLE_BG = "#6d28d9", "#ede9fe"
YELLOW_BG = "#fef3c7"
MONO = "D2Coding"
MINUS = "−"

FIGS = []


def figure(name, width, height):
    """그림 함수를 이름과 논리 크기로 등록함. 함수는 (그림 목록, 장 시간 목록)을 돌려줌. PNG 는 그림 하나에 시간 None."""
    def wrap(fn):
        FIGS.append((name, width, height, fn))
        return fn
    return wrap


# 텐서 동작 흉내(torch 문서의 규칙대로)

def shape_of(x):
    out = []
    while isinstance(x, list):
        out.append(len(x))
        x = x[0] if x else None
    return out


def squeeze(shape, dim=None):
    """torch.squeeze: dim 이 없으면 크기 1 축을 모두 지우고, dim 축의 크기가 1 이 아니면 그대로 둠."""
    if dim is None:
        return [s for s in shape if s != 1]
    d = dim + len(shape) if dim < 0 else dim
    return shape[:d] + shape[d + 1:] if shape[d] == 1 else list(shape)


def unsqueeze(shape, dim):
    d = dim + len(shape) + 1 if dim < 0 else dim
    return shape[:d] + [1] + shape[d:]


def matmul(a, b):
    assert len(a[0]) == len(b), "안쪽 크기가 다름"
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def tmax(m, dim):
    """torch.max(m, dim) 의 (values, indices). 같은 최댓값이 여럿이면 첫 위치."""
    if dim == 1:
        vals = [max(row) for row in m]
        return vals, [row.index(v) for row, v in zip(m, vals)]
    cols = [[row[j] for row in m] for j in range(len(m[0]))]
    vals = [max(c) for c in cols]
    return vals, [c.index(v) for c, v in zip(cols, vals)]


def tsum(m, dim=None):
    if dim is None:
        return sum(sum(row) for row in m)
    if dim == 1:
        return [sum(row) for row in m]
    return [sum(row[j] for row in m) for j in range(len(m[0]))]


def view(flat, rows, cols):
    assert rows * cols == len(flat)
    return [flat[i * cols:(i + 1) * cols] for i in range(rows)]


def transpose(m):
    return [[m[i][j] for i in range(len(m))] for j in range(len(m[0]))]


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def num(v, dot=False):
    """그림에 찍는 숫자 글. 음수는 빼기표 U+2212, dot 이면 실수 꼴(5.)."""
    if isinstance(v, float) and not dot:
        s = ("%.4f" % v).rstrip("0").rstrip(".")
    elif dot:
        s = ("%g" % v) + ("." if float(v) == int(v) else "")
    else:
        s = str(v)
    return s.replace("-", MINUS)


def shape_text(shape):
    return "[" + ", ".join(str(s) for s in shape) + "]"


# 그리기 도구

class Canvas:
    """파일 픽셀 좌표(왼쪽 위가 0, 아래로 갈수록 y 가 커짐)에 그리는 판."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI)
        ax = self.fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, w)
        ax.set_ylim(h, 0)
        ax.axis("off")
        self.ax = ax

    def text(self, x, y, s, size=20, color=INK, ha="center", va="center", bold=False, mono=False, bg=None, ec=None,
             z=6):
        kw = dict(fontsize=size, color=color, ha=ha, va=va, fontweight="bold" if bold else "normal", zorder=z)
        if mono:
            kw["family"] = MONO
        if bg:
            kw["bbox"] = dict(boxstyle="round,pad=0.3", fc=bg, ec=ec or bg, lw=2)
        return self.ax.text(x, y, s, **kw)

    def box(self, x, y, w, h, fc="white", ec=INK, lw=2, rounded=False, z=2, ls="-"):
        if rounded:
            patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=12", fc=fc, ec=ec, lw=lw,
                                   zorder=z, ls=ls)
        else:
            patch = Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, zorder=z, ls=ls)
        self.ax.add_patch(patch)

    def arrow(self, x1, y1, x2, y2, color=INK, lw=3, rad=0.0, head=22, z=4, ls="-"):
        self.ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=head, color=color,
                                          lw=lw, zorder=z, connectionstyle="arc3,rad=%s" % rad, shrinkA=0,
                                          shrinkB=0, linestyle=ls))

    def line(self, xs, ys, color=INK, lw=3, ls="-", z=3):
        self.ax.plot(xs, ys, color=color, lw=lw, ls=ls, zorder=z, solid_capstyle="round")

    def cells(self, x, y, vals, cw=70, ch=56, fill=None, ec=INK, size=21, color=INK, mono=True, fmt=str, lw=2):
        """2차원 목록 vals 를 칸으로 그림. fill(i, j) 는 칸 바탕색, color 는 글자색(함수도 됨)."""
        for i, row in enumerate(vals):
            for j, v in enumerate(row):
                fc = fill(i, j) if fill else "white"
                self.box(x + j * cw, y + i * ch, cw, ch, fc=fc, ec=ec, lw=lw)
                s = fmt(v)
                if s != "":
                    c = color(i, j) if callable(color) else color
                    self.text(x + j * cw + cw / 2, y + i * ch + ch / 2, s, size=size, color=c, mono=mono)

    def title(self, s, x=36, y=38, size=23, color=INK):
        self.text(x, y, s, size=size, color=color, ha="left", bold=True)

    def cross(self, x, y, r=22, color=RED, lw=5):
        self.line([x - r, x + r], [y - r, y + r], color=color, lw=lw, z=7)
        self.line([x - r, x + r], [y + r, y - r], color=color, lw=lw, z=7)

    def image(self):
        self.fig.canvas.draw()
        buf = np.asarray(self.fig.canvas.buffer_rgba())
        img = Image.fromarray(buf[..., :3].copy())
        plt.close(self.fig)
        return img


def labels_row(c, words, y=96, color=PURPLE, bg=PURPLE_BG):
    """단원 첫 그림 위쪽의 낱말 이름표(사전 훈련)."""
    x = 36
    for word in words:
        t = c.text(x, y, word, size=19, color=color, ha="left", bg=bg, ec=color)
        c.fig.canvas.draw()
        box = t.get_window_extent()
        x += box.width + 26


# 3a 텐서의 차원과 모양

R2 = [[1, 5, 6], [4, 3, 2]]  # 3차시 노트북 01 [13] 의 r2


@figure("3a-1", 560, 230)
def fig_3a_1():
    vec = [1, 5, 6]
    shapes = [[], shape_of(vec), shape_of(R2), [3, 2, 2]]
    assert shapes == [[], [3], [2, 3], [3, 2, 2]]
    names = ["스칼라", "벡터", "행렬", "3차원 텐서"]
    centers = [150, 390, 650, 930]

    def draw(upto, summary=False):
        c = Canvas(1120, 460)
        c.title("축을 하나씩 늘린 텐서")
        for k, (cx, name) in enumerate(zip(centers, names)):
            on = k < upto
            c.text(cx, 100, name, size=21, color=PURPLE if on or upto == 0 else MUTED, bold=on,
                   bg=PURPLE_BG if on or upto == 0 else None, ec=PURPLE)
            if not on:
                c.box(cx - 95, 150, 190, 170, fc="white", ec=FAINT, lw=2, ls="--", rounded=True)
                continue
            if k == 0:
                c.cells(cx - 40, 205, [["1."]], cw=80, ch=60, fill=lambda i, j: BLUE_BG)
            elif k == 1:
                c.cells(cx - 105, 205, [[num(v, True) for v in vec]], cw=70, ch=60, fill=lambda i, j: BLUE_BG)
            elif k == 2:
                c.cells(cx - 105, 175, [[num(v, True) for v in row] for row in R2], cw=70, ch=60,
                        fill=lambda i, j: BLUE_BG)
            else:
                for s in range(3):  # 뒤 장부터 그려 앞 장이 위에 오게 함
                    off = (2 - s) * 22
                    c.cells(cx - 70 + off, 205 - off, [["", ""], ["", ""]], cw=55, ch=50,
                            fill=lambda i, j, s=s: ["#93c5fd", "#bfdbfe", BLUE_BG][s])
            c.text(cx, 365, "shape " + shape_text(shapes[k]), size=21, mono=True, color=INK)
            if summary:
                c.text(cx, 418, "축 %d개" % len(shapes[k]), size=22, color=ORANGE, bold=True, bg=ORANGE_BG, ec=ORANGE)
        return c.image()

    frames = [draw(0), draw(1), draw(2), draw(3), draw(4), draw(4, summary=True)]
    return frames, [2000, 2000, 2000, 2000, 2000, 2500]


@figure("3a-2", 560, 220)
def fig_3a_2():
    rows, cols = shape_of(R2)
    assert (rows, cols, rows * cols) == (2, 3, 6)
    c = Canvas(1120, 440)
    c.title("r2 의 축과 크기")
    x0, y0, cw, ch = 210, 150, 100, 80
    c.cells(x0, y0, [[num(v, True) for v in row] for row in R2], cw=cw, ch=ch, fill=lambda i, j: BLUE_BG, size=24)
    c.arrow(x0 - 40, y0, x0 - 40, y0 + rows * ch, color=ORANGE, lw=4)
    c.text(x0 - 60, y0 + rows * ch / 2, "축 0\n행 2칸", size=20, color=ORANGE, ha="right")
    c.arrow(x0, y0 - 30, x0 + cols * cw, y0 - 30, color=GREEN, lw=4)
    c.text(x0 + cols * cw / 2, y0 - 62, "축 1 · 열 3칸", size=20, color=GREEN)
    lines = [("r2.dim()", str(2)), ("r2.shape", "torch.Size([%d, %d])" % (rows, cols)),
             ("r2.numel()", "%d = %d × %d" % (rows * cols, rows, cols))]
    for k, (code, out) in enumerate(lines):
        y = 160 + k * 72
        c.text(600, y, code, size=22, mono=True, ha="left", color=INK)
        c.text(790, y, "→ " + out, size=22, mono=True, ha="left", color=BLUE)
    c.text(600, 385, "축 개수 2, 축마다 크기 [2, 3]", size=20, ha="left", color=MUTED)
    return [c.image()], None


@figure("3a-3", 560, 230)
def fig_3a_3():
    data = [[[1, 2, 3], [4, 5, 6], [7, 8, 9]]]
    shape = shape_of(data)
    assert shape == [1, 3, 3]
    code = "torch.tensor([[[1, 2, 3], [4, 5, 6], [7, 8, 9]]])"
    colors = [ORANGE, GREEN, BLUE]
    bgs = [ORANGE_BG, GREEN_BG, BLUE_BG]

    def draw(level, summary=False):
        c = Canvas(1120, 460)
        c.text(36, 40, code, size=21, mono=True, ha="left")
        ox, oy, ow, oh = 70, 95, 470, 330
        hl = summary or level == 1
        c.box(ox, oy, ow, oh, fc=ORANGE_BG if hl else "white", ec=ORANGE if (hl or level == 0) else FAINT, lw=4,
              rounded=True)
        for r in range(3):
            ry = oy + 30 + r * 98
            hl2 = summary or level == 2
            c.box(ox + 30, ry, ow - 60, 80, fc=GREEN_BG if hl2 else "white", ec=GREEN if (hl2 or level == 0) else FAINT,
                  lw=3, rounded=True, z=3)
            for k in range(3):
                hl3 = summary or (level == 3 and r == 0)
                c.box(ox + 60 + k * 125, ry + 12, 100, 56, fc=BLUE_BG if hl3 else "white",
                      ec=BLUE if (hl3 or level == 0) else INK, lw=2, z=4)
                c.text(ox + 110 + k * 125, ry + 40, str(data[0][r][k]), size=22, mono=True, z=6)
        parts = [str(s) for s in shape]
        shown = parts[:level] if not summary else parts
        if level == 0 and not summary:
            c.text(600, 170, "대괄호 3겹 → 축 3개", size=22, ha="left", color=INK)
        else:
            notes = ["바깥: 덩어리 1개", "가운데: 줄 3개", "안쪽: 숫자 3개"]
            for k in range(len(shown)):
                c.text(600, 140 + k * 60, notes[k], size=21, ha="left", color=colors[k], bg=bgs[k], ec=colors[k])
            text = "torch.Size([" + ", ".join(shown) + ("" if summary or level == 3 else ", …") + "])"
            c.text(600, 360, text, size=23, mono=True, ha="left", color=INK, bold=summary or level == 3)
        return c.image()

    frames = [draw(0), draw(1), draw(2), draw(3), draw_level_shape(shape), draw(3, summary=True)]
    return frames, [2200, 2000, 2000, 2000, 2000, 2400]


def draw_level_shape(shape):
    """3a-3 의 다섯째 장. 세 크기를 바깥부터 적은 shape 만 크게 보임."""
    c = Canvas(1120, 460)
    c.title("바깥 대괄호부터 크기를 적은 목록이 shape")
    words = ["바깥 1", "가운데 3", "안쪽 3"]
    colors = [ORANGE, GREEN, BLUE]
    bgs = [ORANGE_BG, GREEN_BG, BLUE_BG]
    for k, w in enumerate(words):
        c.text(140 + k * 280, 190, w, size=26, color=colors[k], bg=bgs[k], ec=colors[k])
        if k < 2:
            c.arrow(225 + k * 280, 190, 335 + k * 280, 190, color=MUTED, lw=3)
    c.text(560, 340, "torch.Size(%s)" % shape_text(shape), size=30, mono=True, bold=True)
    return c.image()


PIC1 = [[(255, 0, 0), (255, 0, 0), (255, 255, 0), (255, 255, 0)],
        [(255, 0, 0), (255, 0, 0), (255, 255, 0), (255, 255, 0)],
        [(0, 0, 255), (0, 0, 255), (0, 128, 0), (0, 128, 0)],
        [(0, 0, 255), (0, 0, 255), (0, 128, 0), (0, 128, 0)]]
PIC2 = [[(0, 0, 255), (0, 0, 255), (255, 0, 0), (255, 0, 0)],
        [(0, 0, 255), (0, 0, 255), (255, 0, 0), (255, 0, 0)],
        [(0, 128, 0), (0, 128, 0), (255, 255, 0), (255, 255, 0)],
        [(0, 128, 0), (0, 128, 0), (255, 255, 0), (255, 255, 0)]]


def channels(pic):
    return [[[pix[ch] for pix in row] for row in pic] for ch in range(3)]


def hexcolor(rgb):
    return "#%02x%02x%02x" % rgb


@figure("3a-4", 560, 260)
def fig_3a_4():
    for pic in (PIC1, PIC2):
        for row in pic:
            for pix in row:
                assert all(0 <= v <= 255 for v in pix)
    chs = channels(PIC1)
    assert shape_of(chs) == [3, 4, 4]
    batch = [channels(PIC1), channels(PIC2)]
    assert shape_of(batch) == [2, 3, 4, 4]
    keras = [[[list(pix) for pix in row] for row in pic] for pic in (PIC1, PIC2)]
    assert shape_of(keras) == [2, 4, 4, 3]
    assert PIC1[0][2] == (255, 255, 0)
    W, H = 1120, 520

    def picture(c, pic, x, y, cell=56, hl=None):
        for i in range(4):
            for j in range(4):
                c.box(x + j * cell, y + i * cell, cell, cell, fc=hexcolor(pic[i][j]), ec="white", lw=2)
        c.box(x, y, 4 * cell, 4 * cell, fc="none", ec=INK, lw=2, z=3)
        if hl:
            i, j = hl
            c.box(x + j * cell - 3, y + i * cell - 3, cell + 6, cell + 6, fc="none", ec=INK, lw=5, z=5)

    def sheet(c, vals, x, y, name, color, bg, cell=40):
        c.text(x + 2 * cell, y - 24, name, size=21, color=color, bold=True)
        c.cells(x, y, vals, cw=cell, ch=cell, fill=lambda i, j: bg, ec=color, size=16, lw=1.5)

    def stack(c, x, y, cell=26, label=None, pics=PIC1):
        cols = [RED, GREEN, BLUE]
        bgs = [RED_BG, GREEN_BG, BLUE_BG]
        for k in (2, 1, 0):
            off = k * 18
            c.box(x + off, y - off, 4 * cell, 4 * cell, fc=bgs[k], ec=cols[k], lw=2.5, z=2 + (2 - k))
        if label:
            c.text(x + 2 * cell + 18, y + 4 * cell + 30, label, size=18, color=MUTED)

    frames = []
    c = Canvas(W, H)
    c.title("작은 컬러 이미지 한 장")
    picture(c, PIC1, 120, 130)
    c.text(120 + 112, 108, "가로 W = 4", size=20, color=INK)
    c.text(95, 130 + 112, "세로\nH = 4", size=20, color=INK, ha="right")
    c.text(560, 200, "칸 하나가 픽셀", size=22, ha="left", color=INK)
    c.text(560, 260, "픽셀마다 색을 숫자로 적음", size=20, ha="left", color=MUTED)
    frames.append(c.image())

    c = Canvas(W, H)
    c.title("픽셀 하나에 숫자 셋")
    picture(c, PIC1, 120, 130, hl=(0, 2))
    r, g, b = PIC1[0][2]
    c.text(560, 190, "(R, G, B) = (%d, %d, %d)" % (r, g, b), size=24, mono=True, ha="left", bg=YELLOW_BG, ec=ORANGE)
    c.text(560, 270, "8비트 값: 0 ~ 255 (256단계)", size=21, ha="left", color=INK)
    c.text(560, 320, "0 은 어둡고 255 는 가장 밝음", size=19, ha="left", color=MUTED)
    frames.append(c.image())

    c = Canvas(W, H)
    c.title("색깔별로 나눈 판 세 장")
    picture(c, PIC1, 40, 170, cell=44)
    names = [("R 채널", RED, RED_BG), ("G 채널", GREEN, GREEN_BG), ("B 채널", BLUE, BLUE_BG)]
    for k, (name, col, bg) in enumerate(names):
        sheet(c, [[str(v) for v in row] for row in chs[k]], 300 + k * 262, 170, name, col, bg, cell=58)
    c.arrow(222, 258, 286, 258, color=MUTED, lw=3)
    frames.append(c.image())

    c = Canvas(W, H)
    c.title("세 장을 겹치면 3차원")
    stack(c, 150, 200, cell=48)
    c.text(520, 220, "(C, H, W) = (%d, %d, %d)" % tuple(shape_of(chs)), size=26, mono=True, ha="left", bold=True)
    c.text(520, 290, "C 채널 3 · H 세로 4 · W 가로 4", size=21, ha="left", color=MUTED)
    frames.append(c.image())

    c = Canvas(W, H)
    c.title("이미지 두 장을 묶으면 4차원")
    stack(c, 110, 200, cell=40, label="0번 이미지")
    stack(c, 380, 200, cell=40, label="1번 이미지")
    c.text(700, 210, "(N, C, H, W)", size=24, mono=True, ha="left", color=MUTED)
    c.text(700, 270, "= (%d, %d, %d, %d)" % tuple(shape_of(batch)), size=26, mono=True, ha="left", bold=True)
    c.text(700, 330, "N 장 수 2", size=21, ha="left", color=MUTED)
    frames.append(c.image())

    c = Canvas(W, H)
    c.title("축 순서는 프레임워크마다 다름")
    stack(c, 90, 210, cell=34)
    stack(c, 300, 210, cell=34)
    c.text(560, 180, "PyTorch  (N, C, H, W)", size=23, mono=True, ha="left", color=BLUE, bold=True)
    c.text(560, 230, "         = (%d, %d, %d, %d)" % tuple(shape_of(batch)), size=23, mono=True, ha="left")
    c.text(560, 320, "Keras    (N, H, W, C)", size=23, mono=True, ha="left", color=ORANGE, bold=True)
    c.text(560, 370, "         = (%d, %d, %d, %d)" % tuple(shape_of(keras)), size=23, mono=True, ha="left")
    frames.append(c.image())
    return frames, [2000, 2200, 2400, 2000, 2200, 2500]


# 3b 텐서 만들기와 자료형

@figure("3b-1", 560, 230)
def fig_3b_1():
    c = Canvas(1120, 460)
    c.title("넣은 값을 보고 정해지는 자료형")
    rows = [("torch.tensor([1, 5, 6])", [["1", "5", "6"]], "torch.int64", "64비트 정수", BLUE, BLUE_BG),
            ("torch.tensor([1., 5., 6.])", [["1.", "5.", "6."]], "torch.float32", "32비트 실수", ORANGE, ORANGE_BG),
            ("torch.full((2, 3), 7)", [["7"] * 3, ["7"] * 3], "torch.int64", "64비트 정수", BLUE, BLUE_BG)]
    assert shape_of(rows[2][1]) == [2, 3]
    y = 110
    for code, vals, dtype, word, col, bg in rows:
        c.text(36, y + 28, code, size=21, mono=True, ha="left")
        c.cells(470, y, vals, cw=64, ch=56, fill=lambda i, j, bg=bg: bg, ec=col, size=21)
        c.text(720, y + 28, dtype, size=22, mono=True, ha="left", color=col, bold=True)
        c.text(940, y + 28, word, size=19, ha="left", color=MUTED)
        y += 56 * len(vals) + 34
    return [c.image()], None


@figure("3b-2", 560, 230)
def fig_3b_2():
    r1 = [1, 2, 3, 4, 5]
    c = Canvas(1120, 460)
    c.title("자료형 바꾸기")
    c.text(36, 120, "torch.tensor([1, 2, 3, 4, 5])", size=20, mono=True, ha="left")
    c.cells(470, 92, [[str(v) for v in r1]], cw=62, ch=56, fill=lambda i, j: BLUE_BG, ec=BLUE)
    c.text(800, 120, "int64", size=22, mono=True, ha="left", color=BLUE, bold=True)
    c.arrow(625, 152, 625, 200, color=INK, lw=3)
    c.text(645, 176, ".float()", size=21, mono=True, ha="left", color=INK, bold=True)
    c.cells(470, 206, [[num(v, True) for v in r1]], cw=62, ch=56, fill=lambda i, j: ORANGE_BG, ec=ORANGE)
    c.text(800, 234, "float32", size=22, mono=True, ha="left", color=ORANGE, bold=True)
    c.arrow(625, 266, 625, 314, color=INK, lw=3)
    c.text(645, 290, ".long()", size=21, mono=True, ha="left", color=INK, bold=True)
    c.cells(470, 320, [[str(v) for v in r1]], cw=62, ch=56, fill=lambda i, j: BLUE_BG, ec=BLUE)
    c.text(800, 348, "int64", size=22, mono=True, ha="left", color=BLUE, bold=True)
    c.text(36, 230, "FloatTensor → float32", size=20, mono=True, ha="left", color=ORANGE)
    c.text(36, 285, "IntTensor   → int32", size=20, mono=True, ha="left", color=BLUE)
    c.text(36, 410, "값은 같고 자료형만 바뀜", size=19, ha="left", color=MUTED)
    return [c.image()], None


@figure("3b-3", 560, 230)
def fig_3b_3():
    c = Canvas(1120, 460)
    c.title("같은 값으로 채우기와 난수")
    grids = [("torch.zeros(2, 3)", "0."), ("torch.ones(2, 3)", "1."), ("torch.full((2, 3), 7)", "7")]
    for k, (code, v) in enumerate(grids):
        y = 82 + k * 122
        c.text(36, y + 18, code, size=19, mono=True, ha="left")
        c.cells(330, y, [[v] * 3, [v] * 3], cw=48, ch=40, fill=lambda i, j: PALE, ec=MUTED, size=18)
    ax = c.fig.add_axes([0.585, 0.16, 0.39, 0.62])
    xs = np.linspace(-3.5, 3.5, 701)
    normal = np.exp(-xs ** 2 / 2) / math.sqrt(2 * math.pi)
    assert abs(normal.max() - 1 / math.sqrt(2 * math.pi)) < 1e-6
    ax.plot(xs, normal, color=BLUE, lw=3)
    ax.plot([0, 0, 1, 1], [0, 1, 1, 0], color=ORANGE, lw=3)
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(0, 1.25)
    ax.set_xticks([-2, -1, 0, 1, 2])
    ax.set_xticklabels([num(v) for v in (-2, -1, 0, 1, 2)])
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.text(-3.4, 1.12, "rand: 0 이상 1 미만에서 고르게", color=ORANGE, fontsize=17, ha="left")
    ax.text(-3.4, 0.62, "randn: 평균 0,\n표준편차 1", color=BLUE, fontsize=17, ha="left")
    c.text(36, 440, "뽑힌 값은 실행마다 달라짐", size=17, color=MUTED, ha="left")
    return [c.image()], None


@figure("3b-4", 560, 230)
def fig_3b_4():
    rows, cols = shape_of(R2)
    c = Canvas(1120, 460)
    c.title("r2 = torch.tensor([[1., 5., 6.], [4., 3., 2.]])", size=20)
    c.box(36, 80, 500, 300, fc=BLUE_BG, ec=BLUE, lw=2.5, rounded=True)
    c.box(584, 80, 500, 300, fc=GREEN_BG, ec=GREEN, lw=2.5, rounded=True)
    c.text(60, 112, "속성 · 괄호 없이", size=21, color=BLUE, ha="left", bold=True)
    c.text(608, 112, "메서드 · 괄호를 붙여", size=21, color=GREEN, ha="left", bold=True)
    attrs = [("r2.shape", "torch.Size([%d, %d])" % (rows, cols)), ("r2.dtype", "torch.float32"),
             ("r2.device", "cpu"), ("r2.requires_grad", "False")]
    meths = [("r2.size()", "torch.Size([%d, %d])" % (rows, cols)), ("r2.dim()", str(len(shape_of(R2)))),
             ("r2.numel()", str(rows * cols))]
    for k, (code, out) in enumerate(attrs):
        c.text(60, 170 + k * 54, code, size=19, mono=True, ha="left")
        c.text(284, 170 + k * 54, out, size=19, mono=True, ha="left", color=BLUE)
    for k, (code, out) in enumerate(meths):
        c.text(608, 170 + k * 54, code, size=19, mono=True, ha="left")
        c.text(800, 170 + k * 54, out, size=19, mono=True, ha="left", color=GREEN)
    c.text(36, 420, "r2.dtype()  → TypeError", size=21, mono=True, ha="left", color=RED, bg=RED_BG, ec=RED)
    return [c.image()], None


# 3c 값 꺼내기

@figure("3c-1", 560, 190)
def fig_3c_1():
    c = Canvas(1120, 380)
    c.title("item() 은 원소가 하나일 때만")
    rows = [("torch.tensor(1.0)", [["1."]], "1.0", True), ("torch.ones(1)", [["1."]], "1.0", True),
            ("torch.tensor([1., 2., 3., 4., 5.])", [["1.", "2.", "3.", "4.", "5."]], "RuntimeError", False)]
    for k, (code, vals, out, ok) in enumerate(rows):
        y = 95 + k * 92
        c.text(36, y + 26, code, size=19, mono=True, ha="left")
        c.cells(500, y, vals, cw=56, ch=52, fill=lambda i, j, ok=ok: GREEN_BG if ok else RED_BG,
                ec=GREEN if ok else RED, size=19)
        x2 = 500 + 56 * len(vals[0]) + 24
        c.text(x2, y + 26, ".item() →", size=19, mono=True, ha="left")
        c.text(x2 + 140, y + 26, out, size=20, mono=True, ha="left", color=GREEN if ok else RED, bold=True)
    return [c.image()], None


def r2_board(c, x0, y0, cw=100, ch=76, fill=None, labels=True, size=26):
    c.cells(x0, y0, [[num(v, True) for v in row] for row in R2], cw=cw, ch=ch, fill=fill or (lambda i, j: "white"),
            size=size)
    if labels:
        for i in range(2):
            c.text(x0 - 18, y0 + i * ch + ch / 2, "행 %d" % i, size=18, color=MUTED, ha="right")
        for j in range(3):
            c.text(x0 + j * cw + cw / 2, y0 - 20, "열 %d" % j, size=18, color=MUTED)


@figure("3c-2", 560, 240)
def fig_3c_2():
    v1, i1 = tmax(R2, 1)
    v0, i0 = tmax(R2, 0)
    assert (v1, i1) == ([6, 4], [2, 0]) and (v0, i0) == ([4, 5, 6], [1, 0, 0])
    assert max(max(r) for r in R2) == 6
    x0, y0 = 120, 150
    frames = []

    c = Canvas(1120, 480)
    c.title("r2 와 두 축")
    r2_board(c, x0, y0)
    c.text(520, 170, "축 0 = 행 번호 (0, 1)", size=22, ha="left", color=ORANGE)
    c.text(520, 230, "축 1 = 열 번호 (0, 1, 2)", size=22, ha="left", color=GREEN)
    c.text(520, 320, "max 에 축을 주면 그 축이 사라짐", size=20, ha="left", color=MUTED)
    frames.append(c.image())

    c = Canvas(1120, 480)
    c.title("r2.max(): 전체에서 하나")
    r2_board(c, x0, y0, fill=lambda i, j: YELLOW_BG if (i, j) == (0, 2) else "white")
    c.text(520, 200, "r2.max()", size=24, mono=True, ha="left")
    c.text(520, 260, "→ tensor(6.)", size=24, mono=True, ha="left", color=BLUE, bold=True)
    frames.append(c.image())

    for upto in (1, 2):
        c = Canvas(1120, 480)
        c.title("torch.max(r2, 1): 행마다 하나")
        hl = {(0, i1[0])} if upto == 1 else {(0, i1[0]), (1, i1[1])}
        r2_board(c, x0, y0, fill=lambda i, j, hl=hl: GREEN_BG if (i, j) in hl else ("white" if i < upto else PALE))
        for i in range(upto):
            c.text(520, 165 + i * 60, "행 %d: 최댓값 %d, 위치 %d" % (i, v1[i], i1[i]), size=21, ha="left",
                   color=GREEN)
        if upto == 2:
            c.text(520, 310, "values  [%s]" % ", ".join(num(v, True) for v in v1), size=22, mono=True, ha="left")
            c.text(520, 360, "indices [%s]" % ", ".join(str(v) for v in i1), size=22, mono=True, ha="left",
                   color=GREEN, bold=True)
        frames.append(c.image())

    c = Canvas(1120, 480)
    c.title("torch.max(r2, 0): 열마다 하나")
    hl0 = {(i0[j], j) for j in range(3)}
    r2_board(c, x0, y0, fill=lambda i, j: ORANGE_BG if (i, j) in hl0 else "white")
    c.text(520, 200, "values  [%s]" % ", ".join(num(v, True) for v in v0), size=22, mono=True, ha="left")
    c.text(520, 250, "indices [%s]" % ", ".join(str(v) for v in i0), size=22, mono=True, ha="left", color=ORANGE,
           bold=True)
    frames.append(c.image())

    c = Canvas(1120, 480)
    c.title("결과의 원소 수 = 남은 축의 크기")
    r2_board(c, x0, y0, cw=80, ch=64, size=22)
    c.text(450, 150, "dim=1 → 열 축이 사라져 2개", size=21, ha="left", color=GREEN)
    c.text(450, 195, "values [%s] · indices [%s]" % (", ".join(num(v, True) for v in v1), ", ".join(map(str, i1))),
           size=20, mono=True, ha="left")
    c.text(450, 275, "dim=0 → 행 축이 사라져 3개", size=21, ha="left", color=ORANGE)
    c.text(450, 320, "values [%s] · indices [%s]" % (", ".join(num(v, True) for v in v0), ", ".join(map(str, i0))),
           size=20, mono=True, ha="left")
    c.text(450, 400, "[0] 은 values, [1] 은 indices", size=20, ha="left", color=MUTED)
    frames.append(c.image())
    return frames, [2200, 2000, 2000, 2200, 2200, 2500]


@figure("3c-3", 560, 240)
def fig_3c_3():
    s0, s1, s = tsum(R2, 0), tsum(R2, 1), tsum(R2)
    assert (s0, s1, s) == ([5, 8, 8], [12, 9], 21)
    x0, y0 = 120, 150
    frames = []
    c = Canvas(1120, 480)
    c.title("r2 의 합계")
    r2_board(c, x0, y0)
    c.text(520, 200, "shape [2, 3]", size=22, mono=True, ha="left")
    c.text(520, 260, "고른 축을 따라 더함", size=21, ha="left", color=MUTED)
    frames.append(c.image())
    for upto in (1, 3):
        c = Canvas(1120, 480)
        c.title("torch.sum(r2, dim=0): 열마다 위아래를 더함")
        r2_board(c, x0, y0, fill=lambda i, j, upto=upto: ORANGE_BG if j < upto else "white")
        for j in range(upto):
            c.arrow(x0 + j * 100 + 50, y0 + 160, x0 + j * 100 + 50, y0 + 200, color=ORANGE, lw=3)
            c.text(x0 + j * 100 + 50, y0 + 228, num(s0[j], True), size=24, mono=True, color=ORANGE, bold=True)
        if upto == 1:
            c.text(520, 200, "1 + 4 = 5", size=24, mono=True, ha="left")
        else:
            c.text(520, 200, "[%s]" % ", ".join(num(v, True) for v in s0), size=24, mono=True, ha="left", bold=True)
            c.text(520, 260, "shape [3]", size=22, mono=True, ha="left", color=MUTED)
        frames.append(c.image())
    for upto in (1, 2):
        c = Canvas(1120, 480)
        c.title("torch.sum(r2, dim=1): 행마다 세 수를 더함")
        r2_board(c, x0, y0, fill=lambda i, j, upto=upto: GREEN_BG if i < upto else "white")
        for i in range(upto):
            c.arrow(x0 + 310, y0 + i * 76 + 38, x0 + 350, y0 + i * 76 + 38, color=GREEN, lw=3)
            c.text(x0 + 390, y0 + i * 76 + 38, num(s1[i], True), size=24, mono=True, color=GREEN, bold=True)
        if upto == 1:
            c.text(620, 200, "1 + 5 + 6 = 12", size=24, mono=True, ha="left")
        else:
            c.text(620, 200, "[%s]" % ", ".join(num(v, True) for v in s1), size=24, mono=True, ha="left", bold=True)
            c.text(620, 260, "shape [2]", size=22, mono=True, ha="left", color=MUTED)
        frames.append(c.image())
    c = Canvas(1120, 480)
    c.title("세 가지 합계")
    r2_board(c, x0, y0, cw=80, ch=64, size=22)
    c.text(450, 160, "torch.sum(r2)        → %s" % num(s, True), size=21, mono=True, ha="left")
    c.text(450, 220, "torch.sum(r2, dim=0) → [%s]" % ", ".join(num(v, True) for v in s0), size=21, mono=True,
           ha="left", color=ORANGE)
    c.text(450, 280, "torch.sum(r2, dim=1) → [%s]" % ", ".join(num(v, True) for v in s1), size=21, mono=True,
           ha="left", color=GREEN)
    c.text(450, 360, "고른 축이 사라짐", size=20, ha="left", color=MUTED)
    frames.append(c.image())
    return frames, [2000, 2000, 2200, 2000, 2200, 2500]


OUTPUTS = [[0.1, 2.0, -1.0], [1.5, 0.3, 0.2]]


@figure("3c-4", 560, 200)
def fig_3c_4():
    vals, idx = tmax(OUTPUTS, 1)
    assert (vals, idx) == ([2.0, 1.5], [1, 0])
    c = Canvas(1120, 400)
    c.title("종류별 점수에서 가장 큰 위치 고르기")
    x0, y0, cw, ch = 200, 130, 110, 64
    hl = {(i, idx[i]) for i in range(2)}

    def one(v):
        """본문 코드처럼 소수 한 자리(2.0, −1.0)로 적음."""
        return ("%.1f" % v).replace("-", MINUS)

    c.cells(x0, y0, [[one(v) for v in row] for row in OUTPUTS], cw=cw, ch=ch,
            fill=lambda i, j: YELLOW_BG if (i, j) in hl else "white", size=22)
    for j in range(3):
        c.text(x0 + j * cw + cw / 2, y0 - 22, "종류 %d" % j, size=18, color=MUTED)
    for i in range(2):
        c.text(x0 - 18, y0 + i * ch + ch / 2, "데이터 %d" % i, size=18, color=MUTED, ha="right")
    c.text(590, 160, "torch.max(outputs, 1)", size=21, mono=True, ha="left")
    c.text(590, 220, "[0] 값    [%s]" % ", ".join(one(v) for v in vals), size=21, mono=True, ha="left")
    c.text(590, 275, "[1] 위치  [%s]" % ", ".join(map(str, idx)), size=21, mono=True, ha="left", color=BLUE,
           bold=True)
    c.text(590, 330, "위치가 예측한 종류 번호", size=19, ha="left", color=MUTED)
    return [c.image()], None


# 3d 모양 바꾸기

def strip(c, x, y, vals, cw=64, ch=52, fill=None, ec=INK, label=None, size=21):
    c.cells(x, y, [[str(v) for v in vals]], cw=cw, ch=ch, fill=fill, ec=ec, size=size)
    if label:
        c.text(x - 14, y + ch / 2, label, size=18, color=MUTED, ha="right")


def path_through(c, x0, y0, rows, cols, order, cw, ch, color=BLUE):
    """격자 위에서 order(값 순서)대로 칸 가운데를 잇는 선."""
    pos = {}
    for i in range(rows):
        for j in range(cols):
            pos[order[i][j]] = (x0 + j * cw + cw / 2, y0 + i * ch + ch / 2)
    keys = sorted(pos)
    for a, b in zip(keys, keys[1:]):
        (xa, ya), (xb, yb) = pos[a], pos[b]
        c.arrow(xa + (12 if ya == yb else 0), ya + (0 if ya == yb else 12), xb - (12 if ya == yb else 0),
                yb - (0 if ya == yb else 12), color=color, lw=2, head=14, z=7)


@figure("3d-1", 560, 240)
def fig_3d_1():
    a = list(range(6))
    v23, v32 = view(a, 2, 3), view(a, 3, 2)
    assert v23 == [[0, 1, 2], [3, 4, 5]] and v32 == [[0, 1], [2, 3], [4, 5]]
    assert 6 // 3 == 2
    frames = []

    def base(title):
        c = Canvas(1120, 480)
        c.title(title)
        strip(c, 330, 80, a, label="메모리 순서")
        return c

    c = base("a = torch.arange(6)")
    c.text(330, 190, "shape [6] · 원소 6개", size=22, ha="left")
    frames.append(c.image())
    for title, grid, rows, cols, note in (("a.view(2, 3)", v23, 2, 3, "shape [2, 3]"),
                                          ("a.view(3, 2)", v32, 3, 2, "shape [3, 2]"),
                                          ("a.view(3, -1)", v32, 3, 2, "-1 자리 = 6 ÷ 3 = 2")):
        c = base(title)
        c.cells(330, 190, [[str(v) for v in row] for row in grid], cw=72, ch=60, fill=lambda i, j: BLUE_BG)
        c.text(680, 260, note, size=22, ha="left", color=ORANGE if "-1" in note else INK, mono="-1" not in note)
        frames.append(c.image())
    c = base("a.view(-1)")
    strip(c, 330, 220, a, fill=lambda i, j: BLUE_BG)
    c.text(330, 320, "shape [6] · 한 줄로 폄", size=22, ha="left")
    frames.append(c.image())
    c = base("모양만 바뀌고 원소 6개는 그대로")
    for k, (txt, y) in enumerate((("view(2, 3)  → [2, 3]", 200), ("view(3, -1) → [3, 2]", 260),
                                 ("view(-1)    → [6]", 320))):
        c.text(330, y, txt, size=22, mono=True, ha="left")
    c.text(330, 400, "원소 수가 다른 모양은 오류", size=20, ha="left", color=RED)
    frames.append(c.image())
    return frames, [2000, 2200, 2000, 2200, 2000, 2500]


@figure("3d-2", 560, 260)
def fig_3d_2():
    x = view(list(range(6)), 2, 3)
    y = transpose(x)
    assert y == [[0, 3], [1, 4], [2, 5]] and shape_of(y) == [3, 2]
    read = [v for row in y for v in row]
    assert read == [0, 3, 1, 4, 2, 5]
    mem = list(range(6))
    sx, sy, cw = 300, 92, 64
    frames = []

    def base(title):
        c = Canvas(1120, 520)
        c.title(title)
        strip(c, sx, sy, mem, label="메모리")
        return c

    c = base("x = torch.arange(6).view(2, 3)")
    c.cells(120, 230, [[str(v) for v in row] for row in x], cw=72, ch=60, fill=lambda i, j: BLUE_BG)
    c.text(120, 380, "x 를 행마다 읽으면 0 1 2 3 4 5", size=20, ha="left")
    c.text(120, 420, "메모리 순서와 같음", size=20, ha="left", color=MUTED)
    frames.append(c.image())

    c = base("y = x.t(): 행과 열을 맞바꿈")
    c.cells(120, 230, [[str(v) for v in row] for row in x], cw=72, ch=60, fill=lambda i, j: PALE)
    c.cells(560, 200, [[str(v) for v in row] for row in y], cw=72, ch=60, fill=lambda i, j: ORANGE_BG)
    c.arrow(360, 290, 530, 290, color=MUTED, lw=3)
    c.text(760, 300, "shape [3, 2]", size=22, mono=True, ha="left")
    c.text(760, 350, "메모리는 그대로", size=20, ha="left", color=MUTED)
    frames.append(c.image())

    c = base("y 를 행마다 읽으면 메모리를 건너뜀")
    c.cells(760, 280, [[str(v) for v in row] for row in y], cw=72, ch=60, fill=lambda i, j: ORANGE_BG)
    centers = {v: sx + v * cw + cw / 2 for v in mem}
    for a_, b_ in zip(read, read[1:]):
        c.arrow(centers[a_], sy + 56, centers[b_], sy + 56, color=ORANGE, lw=2.5, rad=0.45 if b_ > a_ else -0.45,
                head=16)
    c.text(120, 330, "읽는 순서", size=20, ha="left", color=MUTED)
    c.text(120, 370, " ".join(map(str, read)), size=24, mono=True, ha="left", color=ORANGE, bold=True)
    frames.append(c.image())

    c = base("y.view(6)")
    c.cells(560, 200, [[str(v) for v in row] for row in y], cw=72, ch=60, fill=lambda i, j: ORANGE_BG)
    c.text(120, 250, "RuntimeError", size=26, mono=True, ha="left", color=RED, bold=True)
    c.text(120, 300, "메모리를 그대로 두고는", size=20, ha="left", color=MUTED)
    c.text(120, 335, "한 줄로 이어 읽을 수 없음", size=20, ha="left", color=MUTED)
    c.cross(470, 260)
    frames.append(c.image())

    c = base("y.reshape(6): 새 메모리에 복사")
    c.cells(560, 200, [[str(v) for v in row] for row in y], cw=72, ch=60, fill=lambda i, j: ORANGE_BG)
    strip(c, sx, 430, read, fill=lambda i, j: GREEN_BG, ec=GREEN, label="새 메모리")
    c.text(120, 250, "tensor([%s])" % ", ".join(map(str, read)), size=22, mono=True, ha="left", color=GREEN)
    frames.append(c.image())

    c = base("view 가 안 되면 reshape 나 contiguous()")
    strip(c, sx, 430, read, fill=lambda i, j: GREEN_BG, ec=GREEN, label="새 메모리")
    c.text(120, 210, "y.view(6)               → RuntimeError", size=20, mono=True, ha="left", color=RED)
    c.text(120, 265, "y.reshape(6)            → [0, 3, 1, 4, 2, 5]", size=20, mono=True, ha="left",
           color=GREEN)
    c.text(120, 320, "y.contiguous().view(6)  → [0, 3, 1, 4, 2, 5]", size=20, mono=True, ha="left",
           color=GREEN)
    frames.append(c.image())
    return frames, [2200, 2200, 2400, 2200, 2200, 2500]


def shape_boxes(c, x, y, shape, fill=None, ec=None, label_idx=False, size=26, w=78, h=66, gap=16):
    for k, s in enumerate(shape):
        fc = fill(k) if fill else (ORANGE_BG if s == 1 else BLUE_BG)
        e = ec(k) if ec else (ORANGE if s == 1 else BLUE)
        c.box(x + k * (w + gap), y, w, h, fc=fc, ec=e, lw=2.5, rounded=True)
        c.text(x + k * (w + gap) + w / 2, y + h / 2, str(s), size=size, mono=True, bold=True)
        if label_idx:
            c.text(x + k * (w + gap) + w / 2, y + h + 22, "축 %d" % k, size=16, color=MUTED)


@figure("3d-3", 560, 230)
def fig_3d_3():
    steps = []
    s = [3, 1, 4, 1]
    for code, fn in (("exam.squeeze(dim=1)", lambda t: squeeze(t, 1)), ("exam.squeeze(dim=-1)", lambda t: squeeze(t, -1)),
                     ("exam.unsqueeze(dim=0)", lambda t: unsqueeze(t, 0)), ("exam.squeeze(dim=1)",
                                                                             lambda t: squeeze(t, 1)),
                     ("exam.squeeze()", lambda t: squeeze(t))):
        new = fn(s)
        steps.append((code, s, new))
        s = new
    assert [st[2] for st in steps] == [[3, 4, 1], [3, 4], [1, 3, 4], [1, 3, 4], [3, 4]]
    notes = ["축 1 의 크기가 1 → 지움", "-1 은 맨 뒤 축 · 크기 1 → 지움", "0번 자리에 크기 1 축을 넣음",
             "축 1 의 크기가 3 → 그대로", "인자 없음 → 크기 1 축을 모두 지움"]
    frames = []
    c = Canvas(1120, 460)
    c.title("exam = torch.rand(3, 1, 4, 1)")
    shape_boxes(c, 300, 180, [3, 1, 4, 1], label_idx=True)
    c.text(300, 340, "주황 칸이 크기 1 인 축", size=20, ha="left", color=ORANGE)
    frames.append(c.image())
    for (code, before, after), note in zip(steps, notes):
        c = Canvas(1120, 460)
        c.title(code)
        shape_boxes(c, 120, 140, before, label_idx=True, w=70, h=60, size=24)
        c.arrow(560, 170, 640, 170, color=MUTED, lw=3)
        shape_boxes(c, 670, 140, after, w=70, h=60, size=24)
        c.text(120, 300, shape_text(before) + " → " + shape_text(after), size=24, mono=True, ha="left", bold=True)
        c.text(120, 360, note, size=21, ha="left", color=GREEN if before == after else INK)
        frames.append(c.image())
    return frames, [2000, 2200, 2200, 2200, 2400, 2500]


@figure("3d-4", 560, 250)
def fig_3d_4():
    base = [[1, 2], [3, 4], [5, 6]]
    assert unsqueeze(shape_of(base), 0) == [1, 3, 2]
    rep = [1 * 4, 3 * 1, 2 * 1]
    assert rep == [4, 3, 2]
    frames = []

    def block(c, x, y, vals, fc, ec, cw=40, ch=32, size=16, ls="-"):
        for i, row in enumerate(vals):
            for j, v in enumerate(row):
                c.box(x + j * cw, y + i * ch, cw, ch, fc=fc, ec=ec, lw=1.8, ls=ls)
                c.text(x + j * cw + cw / 2, y + i * ch + ch / 2, str(v), size=size, mono=True)

    def panels(c, vals_view, vals_copy, show_e=True, show_r=True, changed=False):
        c.text(70, 92, "base [3, 2]", size=19, ha="left", color=MUTED)
        block(c, 70, 110, base if not changed else [[9, 2], [3, 4], [5, 6]], BLUE_BG, BLUE, cw=46, ch=38, size=18)
        if show_e:
            c.text(330, 92, "expand(4, 3, 2)", size=19, mono=True, ha="left", color=BLUE)
            for k in range(4):
                block(c, 330 + k * 112, 120, vals_view, "white", BLUE, cw=46, ch=36, size=17, ls="--")
            c.arrow(175, 150, 325, 150, color=BLUE, lw=2.5)
            c.text(330, 252, "새 메모리 없이 base 를 4번 보여 줌", size=17, ha="left", color=BLUE)
        if show_r:
            c.text(330, 300, "repeat(4, 1, 1)", size=19, mono=True, ha="left", color=GREEN)
            for k in range(4):
                block(c, 330 + k * 112, 328, vals_copy, GREEN_BG, GREEN, cw=46, ch=36, size=17)
            c.text(330, 462, "값을 복사한 새 텐서 4벌", size=17, ha="left", color=GREEN)

    c = Canvas(1120, 500)
    c.title("base 에 앞쪽 축 하나 넣기")
    block(c, 120, 140, base, BLUE_BG, BLUE, cw=60, ch=50, size=22)
    c.text(120, 345, "[3, 2]", size=24, mono=True, ha="left")
    c.arrow(330, 215, 450, 215, color=MUTED, lw=3)
    c.text(390, 185, "unsqueeze(0)", size=19, mono=True)
    c.box(490, 125, 150, 180, fc="none", ec=ORANGE, lw=3, rounded=True)
    block(c, 505, 140, base, BLUE_BG, BLUE, cw=60, ch=50, size=22)
    c.text(490, 345, "[1, 3, 2]", size=24, mono=True, ha="left", color=ORANGE)
    frames.append(c.image())

    c = Canvas(1120, 500)
    c.title("expand: 같은 메모리를 4번 봄")
    panels(c, base, base, show_r=False)
    frames.append(c.image())

    c = Canvas(1120, 500)
    c.title("repeat: 4번 복사")
    panels(c, base, base)
    frames.append(c.image())

    changed = [[9, 2], [3, 4], [5, 6]]
    c = Canvas(1120, 500)
    c.title("base 의 첫 칸을 9 로 바꾸면")
    panels(c, changed, base, changed=True)
    frames.append(c.image())

    c = Canvas(1120, 500)
    c.title("expand 쪽만 함께 바뀜")
    panels(c, changed, base, changed=True)
    for k in range(4):
        c.box(328 + k * 112, 118, 50, 40, fc="none", ec=RED, lw=3.5, z=8)
    frames.append(c.image())

    c = Canvas(1120, 500)
    c.title("둘 다 shape [4, 3, 2]")
    c.text(70, 160, "expand(4, 3, 2)", size=23, mono=True, ha="left", color=BLUE, bold=True)
    c.text(70, 210, "원본과 메모리를 함께 씀 · 읽기만 할 때", size=21, ha="left")
    c.text(70, 310, "repeat(4, 1, 1)", size=23, mono=True, ha="left", color=GREEN, bold=True)
    c.text(70, 360, "축마다 적은 횟수만큼 복사 · 따로 바꿀 수 있음", size=21, ha="left")
    c.text(70, 430, "[1, 3, 2] → [1×4, 3×1, 2×1] = %s" % shape_text(rep), size=20, mono=True, ha="left", color=MUTED)
    frames.append(c.image())
    return frames, [2000, 2200, 2200, 2000, 2400, 2500]


@figure("3d-5", 560, 210)
def fig_3d_5():
    t = [1, 2, 3, 4, 5, 6]

    def chunk(xs, k):
        size = -(-len(xs) // k)
        return [xs[i:i + size] for i in range(0, len(xs), size)]

    def split(xs, size):
        return [xs[i:i + size] for i in range(0, len(xs), size)]

    rows = [("torch.chunk(t, 3)", chunk(t, 3), "덩어리 3개"), ("torch.split(t, 2)", split(t, 2), "크기 2씩"),
            ("torch.split(t, 4)", split(t, 4), "크기 4씩, 마지막은 남은 2개")]
    assert [r[1] for r in rows] == [[[1, 2], [3, 4], [5, 6]], [[1, 2], [3, 4], [5, 6]], [[1, 2, 3, 4], [5, 6]]]
    c = Canvas(1120, 420)
    c.title("t = torch.tensor([1, 2, 3, 4, 5, 6]) 나누기", size=21)
    fills = [BLUE_BG, ORANGE_BG, GREEN_BG]
    edges = [BLUE, ORANGE, GREEN]
    for k, (code, parts, note) in enumerate(rows):
        y = 100 + k * 100
        c.text(36, y + 26, code, size=20, mono=True, ha="left")
        x = 330
        for p, part in enumerate(parts):
            c.cells(x, y, [[str(v) for v in part]], cw=54, ch=52, fill=lambda i, j, p=p: fills[p], ec=edges[p],
                    size=20)
            x += 54 * len(part) + 22
        c.text(730, y + 26, note, size=18, ha="left", color=MUTED)
    return [c.image()], None


# 3e 텐서 연산

@figure("3e-1", 560, 240)
def fig_3e_1():
    a, b = [1, 2, 3], [4, 5, 6]
    ops = [("a + b", [x + y for x, y in zip(a, b)], a, b, BLUE, BLUE_BG, "int64"),
           ("a - b", [x - y for x, y in zip(a, b)], a, b, BLUE, BLUE_BG, "int64"),
           ("a * b", [x * y for x, y in zip(a, b)], a, b, BLUE, BLUE_BG, "int64")]
    assert [o[1] for o in ops] == [[5, 7, 9], [-3, -3, -3], [4, 10, 18]]
    p, q = [10, 20, 30], [2, 4, 5]
    div = [x / y for x, y in zip(p, q)]
    assert div == [5.0, 5.0, 6.0]
    sq = [x ** 2 for x in q]
    assert sq == [4, 16, 25]
    frames = []

    def layout(title, top, mid, res, sym, col, bg, dtype, dot=False):
        c = Canvas(1120, 480)
        c.title(title)
        c.cells(300, 100, [[num(v) for v in top]], cw=90, ch=60, fill=lambda i, j: PALE)
        if mid is not None:
            c.cells(300, 200, [[num(v) for v in mid]], cw=90, ch=60, fill=lambda i, j: PALE)
            c.text(260, 230, sym, size=28, mono=True, bold=True)
        else:
            c.text(600, 230, sym, size=26, mono=True, bold=True, ha="left")
        c.line([300, 570], [285, 285], color=INK, lw=2.5)
        if res is not None:
            c.cells(300, 305, [[num(v, dot) for v in res]], cw=90, ch=60, fill=lambda i, j: bg, ec=col)
            c.text(600, 335, dtype, size=22, mono=True, ha="left", color=col, bold=True)
        return c

    c = layout("a = [1, 2, 3], b = [4, 5, 6]: 같은 자리끼리 짝", a, b, None, "", INK, PALE, "")
    for j in range(3):
        c.line([345 + j * 90, 345 + j * 90], [162, 198], color=MUTED, lw=2, ls="--")
    frames.append(c.image())
    for title, res, top, mid, col, bg, dtype in ops:
        c = layout(title, top, mid, res, title.split()[1], col, bg, dtype)
        frames.append(c.image())
    c = layout("[10, 20, 30] / [2, 4, 5]: 정수끼리 나눠도 실수", p, q, div, "/", ORANGE, ORANGE_BG, "float32",
               dot=True)
    frames.append(c.image())
    c = layout("[2, 4, 5] ** 2: 정수 그대로", q, None, sq, "** 2", BLUE, BLUE_BG, "int64")
    frames.append(c.image())
    c = Canvas(1120, 480)
    c.title("같은 자리끼리 계산한 결과")
    lines = [("a + b", "[5, 7, 9]", BLUE), ("a - b", "[%s]" % ", ".join(num(v) for v in ops[1][1]), BLUE),
             ("a * b", "[4, 10, 18]", BLUE), ("[10, 20, 30] / [2, 4, 5]", "[5., 5., 6.]  float32", ORANGE),
             ("[2, 4, 5] ** 2", "[4, 16, 25]  int64", BLUE)]
    for k, (code, out, col) in enumerate(lines):
        c.text(80, 110 + k * 66, code, size=21, mono=True, ha="left")
        c.text(520, 110 + k * 66, "→ " + out, size=21, mono=True, ha="left", color=col)
    frames.append(c.image())
    return frames, [2000, 1800, 1800, 1800, 2400, 2200, 2500]


MA = [[1, 2, 3], [4, 5, 6]]  # 3차시 노트북 02 [37]
MB = [[7, 8], [9, 10], [11, 12]]


@figure("3e-2", 560, 260)
def fig_3e_2():
    mc = matmul(MA, MB)
    assert mc == [[58, 64], [139, 154]]
    assert 1 * 7 + 2 * 9 + 3 * 11 == 58
    ax_, ay, bx, by, cx, cy, cw, ch = 90, 290, 420, 80, 420, 290, 84, 64
    frames = []

    def draw(done, cur=None):
        c = Canvas(1120, 520)
        c.title("a @ b", x=36, y=40)
        c.cells(ax_, ay, [[str(v) for v in row] for row in MA], cw=cw, ch=ch,
                fill=lambda i, j: YELLOW_BG if cur and i == cur[0] else "white")
        c.cells(bx, by, [[str(v) for v in row] for row in MB], cw=cw, ch=ch,
                fill=lambda i, j: YELLOW_BG if cur and j == cur[1] else "white")
        vals = [[str(mc[i][j]) if (i, j) in done else "" for j in range(2)] for i in range(2)]
        c.cells(cx, cy, vals, cw=cw, ch=ch, fill=lambda i, j: BLUE_BG if (i, j) in done else PALE,
                color=lambda i, j: BLUE)
        c.text(ax_ + 1.5 * cw, ay - 24, "a [2, 3]", size=19, color=MUTED)
        c.text(bx + 2 * cw + 30, by + 1.5 * ch, "b [3, 2]", size=19, color=MUTED, ha="left")
        c.text(cx + cw, cy + 2 * ch + 26, "c = a @ b", size=19, color=MUTED)
        if cur:
            i, j = cur
            terms = " + ".join("%d×%d" % (MA[i][k], MB[k][j]) for k in range(3))
            c.text(640, 330, terms, size=22, mono=True, ha="left")
            c.text(640, 380, "= %d" % mc[i][j], size=26, mono=True, ha="left", color=BLUE, bold=True)
            c.text(640, 430, "a 의 %d번 행 · b 의 %d번 열" % (i, j), size=19, ha="left", color=MUTED)
        return c

    frames.append(draw(set()).image())
    order = [(0, 0), (0, 1), (1, 0), (1, 1)]
    for k, cur in enumerate(order):
        frames.append(draw(set(order[:k + 1]), cur).image())
    c = draw(set(order))
    c.text(640, 330, "[[58, 64], [139, 154]]", size=22, mono=True, ha="left", color=BLUE, bold=True)
    c.text(640, 380, "(2, 3) @ (3, 2) → (2, 2)", size=22, mono=True, ha="left")
    frames.append(c.image())
    return frames, [2000, 2400, 2200, 2200, 2200, 2500]


@figure("3e-3", 560, 210)
def fig_3e_3():
    rows = [((2, 3), (3, 2)), ((4, 3), (3, 5)), ((2, 3), (2, 3))]
    dot = sum(x * y for x, y in zip([1, 2, 3], [4, 5, 6]))
    assert dot == 32
    c = Canvas(1120, 420)
    c.title("행렬곱 shape: 안쪽 두 크기가 같아야 함")
    for k, (l, r) in enumerate(rows):
        y = 110 + k * 78
        ok = l[1] == r[0]
        c.text(60, y, "(%d, " % l[0], size=24, mono=True, ha="left")
        c.text(148, y, str(l[1]), size=24, mono=True, ha="left", color=GREEN if ok else RED, bold=True)
        c.text(168, y, ") @ (", size=24, mono=True, ha="left")
        c.text(258, y, str(r[0]), size=24, mono=True, ha="left", color=GREEN if ok else RED, bold=True)
        c.text(278, y, ", %d)" % r[1], size=24, mono=True, ha="left")
        if ok:
            c.text(420, y, "→ (%d, %d)" % (l[0], r[1]), size=24, mono=True, ha="left", color=BLUE, bold=True)
        else:
            c.text(420, y, "→ 오류: 안쪽 크기가 다름", size=22, ha="left", color=RED, bold=True)
    c.text(60, 360, "1차원끼리 torch.dot: 1×4 + 2×5 + 3×6 = %d" % dot, size=21, mono=True, ha="left", color=PURPLE)
    return [c.image()], None


# 3f 기울기, 미분, 편미분

def curve(x):
    return 2 * x * x + 2


@figure("3f-1", 560, 260)
def fig_3f_1():
    pts = [2.0, 1.5, 1.1]
    slopes = [round((curve(p) - curve(1.0)) / (p - 1.0), 6) for p in pts]
    assert slopes == [6.0, 5.0, 4.2] and curve(1.0) == 4.0 and abs(curve(1.1) - 4.42) < 1e-9
    assert curve(1.5) == 6.5 and curve(2.0) == 10.0
    tangent = 4 * 1.0
    frames = []

    def base(title, show_curve=True):
        c = Canvas(1120, 520)
        c.title(title)
        labels_row(c, ["기울기", "미분", "편미분", "시그모이드"], y=92)
        ax = c.fig.add_axes([0.08, 0.13, 0.5, 0.58])
        ax.set_xlim(-0.5, 2.5)
        ax.set_ylim(0, 13)
        ax.set_xticks([0, 1, 2])
        ax.set_yticks([0, 4, 8, 12])
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.set_xlabel("x", fontsize=18)
        if show_curve:
            xs = np.linspace(-0.5, 2.5, 301)
            ax.plot(xs, curve(xs), color=BLUE, lw=3)
            ax.plot([1.0], [4.0], "o", color=INK, ms=11, zorder=5)
        return c, ax

    c, ax = base("직선의 기울기", show_curve=False)
    xs = np.linspace(-0.5, 2.5, 10)
    ax.plot(xs, 2 * xs + 1, color=GREEN, lw=3)
    ax.plot([0, 1, 1], [1, 1, 3], color=ORANGE, lw=3)
    ax.text(0.5, 0.2, "1", color=ORANGE, fontsize=18, ha="center")
    ax.text(1.08, 2.0, "2", color=ORANGE, fontsize=18)
    c.text(700, 250, "y = 2x + 1", size=22, mono=True, ha="left", color=GREEN)
    c.text(700, 310, "x 가 1 늘면 y 는 2 늘어남", size=20, ha="left")
    c.text(700, 360, "기울기 = 2 (어디서나 같음)", size=20, ha="left", color=MUTED)
    frames.append(c.image())

    c, ax = base("곡선 $y = 2x^2 + 2$ 의 x = 1")
    c.text(700, 250, "$y = 2x^2 + 2$", size=22, ha="left", color=BLUE)
    c.text(700, 310, "x = 1 에서 y = 4", size=20, ha="left")
    c.text(700, 360, "자리마다 기울어진 정도가 다름", size=20, ha="left", color=MUTED)
    frames.append(c.image())

    for p, s in zip(pts, slopes):
        c, ax = base("두 점을 이은 직선의 기울기")
        xs = np.linspace(-0.5, 2.5, 10)
        ax.plot(xs, 4 + s * (xs - 1), color=MUTED, lw=2, ls="--")
        ax.plot([p], [curve(p)], "o", color=INK, ms=10, zorder=5)
        c.text(700, 250, "x = 1 과 x = %s" % num(p), size=21, ha="left")
        c.text(700, 300, "(%s %s 4) ÷ %s = %s" % (num(curve(p)), MINUS, num(round(p - 1, 6)), num(s)), size=21,
               ha="left", mono=True)
        c.text(700, 360, "간격을 좁히면 4 에 다가감", size=20, ha="left", color=MUTED)
        frames.append(c.image())

    c, ax = base("x = 1 의 접선: 기울기 4")
    xs = np.linspace(-0.5, 2.5, 10)
    ax.plot(xs, 4 + tangent * (xs - 1), color=ORANGE, lw=3)
    c.text(700, 250, "접선의 기울기 = %s" % num(tangent), size=22, ha="left", color=ORANGE, bold=True)
    c.text(700, 310, "이 값이 x = 1 의 미분", size=20, ha="left")
    frames.append(c.image())

    c, ax = base("직선의 기울기와 곡선 한 점의 미분")
    xs = np.linspace(-0.5, 2.5, 10)
    ax.plot(xs, 4 + tangent * (xs - 1), color=ORANGE, lw=3)
    c.text(700, 240, "직선: 어디서나 같은 기울기", size=20, ha="left", color=GREEN)
    c.text(700, 290, "곡선: 점마다 접선의 기울기", size=20, ha="left", color=ORANGE)
    c.text(700, 340, "$y = 2x^2 + 2$ 의 미분은 4x", size=20, ha="left")
    frames.append(c.image())
    return frames, [2200, 2000, 2000, 2000, 2000, 2200, 2500]


@figure("3f-2", 560, 260)
def fig_3f_2():
    a0, b0 = 1.0, 2.0
    ga, gb = 2.0, 6.0 * b0
    z0 = 2 * a0 + 3 * b0 ** 2
    assert (ga, gb, z0) == (2.0, 12.0, 14.0)
    c = Canvas(1120, 520)
    c.title("$z = 2a + 3b^2$ 의 기울기")
    ax = c.fig.add_axes([0.06, 0.13, 0.42, 0.74])
    A, B = np.meshgrid(np.linspace(-1, 3, 201), np.linspace(-0.2, 3.8, 201))
    Z = 2 * A + 3 * B ** 2
    levels = [2, 6, 10, 14, 22, 30]
    cs = ax.contour(A, B, Z, levels=levels, colors=[FAINT] * 2 + [MUTED] * 0 + [FAINT] * 4, linewidths=2)
    labels = ax.clabel(cs, levels=[14], fmt="z = %d", fontsize=16, manual=[(2.3, 1.55)], colors=[MUTED])
    ax.set_xlim(-1, 3)
    ax.set_ylim(-0.2, 3.8)
    ax.set_aspect("equal")
    ax.set_xlabel("a", fontsize=18)
    ax.set_ylabel("b", fontsize=18, rotation=0, labelpad=16)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    norm = math.hypot(ga, gb)
    ux, uy = ga / norm, gb / norm
    ax.annotate("", xy=(a0 + 1.2 * ux, b0 + 1.2 * uy), xytext=(a0, b0),
                arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=3.5, mutation_scale=22))
    ax.annotate("", xy=(a0 - 1.2 * ux, b0 - 1.2 * uy), xytext=(a0, b0),
                arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=3.5, mutation_scale=22))
    ax.plot([a0], [b0], "o", color=INK, ms=11, zorder=5)
    c.text(600, 130, "점 (a, b) = (1, 2), z = %s" % num(z0), size=21, ha="left")
    c.text(600, 200, "a 로 편미분: 2", size=21, ha="left")
    c.text(600, 250, "b 로 편미분: 6b = %s" % num(gb), size=21, ha="left")
    c.text(600, 320, "기울기 = (%s, %s)" % (num(ga), num(gb)), size=23, ha="left", color=ORANGE, bold=True)
    c.text(600, 375, "주황: z 가 가장 빨리 커지는 쪽", size=19, ha="left", color=ORANGE)
    c.text(600, 420, "초록: 반대쪽, z 가 가장 빨리 줄어드는 쪽", size=19, ha="left", color=GREEN)
    c.text(600, 470, "회색 선: z 가 같은 점을 이은 선", size=17, ha="left", color=MUTED)
    return [c.image()], None


@figure("3f-3", 560, 240)
def fig_3f_3():
    g0 = sigmoid(0) * (1 - sigmoid(0))
    g2 = sigmoid(2) * (1 - sigmoid(2))
    assert g0 == 0.25 and round(g2, 3) == 0.105 and round(sigmoid(-2) * (1 - sigmoid(-2)), 3) == 0.105
    grid = [-2 + 0.25 * k for k in range(17)]
    assert len(grid) == 17 and abs(sum(sigmoid(x) for x in grid) - 8.5) < 1e-9
    c = Canvas(1120, 480)
    c.title("시그모이드 y 와 그 미분 y(1 %s y)" % MINUS)
    ax = c.fig.add_axes([0.08, 0.12, 0.56, 0.7])
    xs = np.linspace(-5, 5, 501)
    ys = 1 / (1 + np.exp(-xs))
    ax.plot(xs, ys, color=BLUE, lw=3)
    ax.plot(xs, ys * (1 - ys), color=ORANGE, lw=3)
    ax.plot([0], [0.25], "o", color=ORANGE, ms=10)
    ax.plot([-2, 2], [g2, g2], "o", color=ORANGE, ms=8)
    ax.set_xlim(-5, 5)
    ax.set_ylim(-0.02, 1.08)
    ax.set_xticks([-4, -2, 0, 2, 4])
    ax.set_xticklabels([num(v) for v in (-4, -2, 0, 2, 4)])
    ax.set_yticks([0, 0.25, 0.5, 1])
    ax.set_yticklabels(["0", "0.25", "0.5", "1"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.text(2.4, 0.86, "y", color=BLUE, fontsize=19)
    ax.text(2.6, 0.17, "y(1 %s y)" % MINUS, color=ORANGE, fontsize=19)
    c.text(760, 170, "x = 0: 미분 0.25 (가장 큼)", size=19, ha="left", color=ORANGE)
    c.text(760, 225, "x = ±2: 미분 0.105", size=19, ha="left", color=ORANGE)
    c.text(760, 300, "y = 1 / (1 + e^(%sx))" % MINUS, size=19, ha="left", mono=True)
    return [c.image()], None


# 3g 자동 미분

CHAIN = [("x", 1.0), ("$x^2$", 1.0), ("$2x^2$", 2.0), ("y", 4.0)]
OPS = ["제곱", "× 2", "+ 2"]
LOCAL = [2.0, 2.0, 1.0]  # 각 계산의 미분: 제곱은 2x(x=1), ×2 는 2, +2 는 1


def chain_check():
    x = 1.0
    vals = [x, x * x, 2 * x * x, 2 * x * x + 2]
    assert [v for _, v in CHAIN] == vals
    assert LOCAL == [2 * x, 2.0, 1.0]
    assert LOCAL[0] * LOCAL[1] * LOCAL[2] == 4 * x


def chain_board(c, shown, y=210, grads=None, gfrom=None, hl=None, faded=False):
    xs = [110, 380, 650, 920]
    for k, ((name, v), x) in enumerate(zip(CHAIN, xs)):
        on = k < shown
        col = INK if on else FAINT
        fc = (YELLOW_BG if hl == k else BLUE_BG) if on and not faded else ("white" if not on else PALE)
        c.box(x - 85, y - 45, 170, 90, fc=fc, ec=col, lw=2.5, rounded=True)
        c.text(x, y - 15, name, size=20, color=MUTED if on else FAINT)
        c.text(x, y + 18, num(v, True) if on else "?", size=24, mono=True, bold=on, color=col)
        if k < 3:
            c.arrow(x + 88, y, xs[k + 1] - 88, y, color=INK if k + 1 < shown else FAINT, lw=3)
            c.text((x + xs[k + 1]) / 2, y - 32, OPS[k], size=19, color=INK if k + 1 < shown else FAINT)
    if grads:
        for k, g in grads.items():
            c.text(xs[k], y + 95, num(g, True), size=24, mono=True, color=ORANGE, bold=True, bg=ORANGE_BG, ec=ORANGE)
    if gfrom is not None:
        for k in gfrom:
            c.text((xs[k] + xs[k + 1]) / 2, y + 48, "미분 " + num(LOCAL[k]), size=17, color=ORANGE)
    return xs


@figure("3g-1", 560, 240)
def fig_3g_1():
    chain_check()
    frames = []
    for shown in range(1, 5):
        c = Canvas(1120, 480)
        c.title("y = 2 * x**2 + 2 를 계산하며 기록")
        labels_row(c, ["requires_grad", "계산 그래프", "backward", "grad"], y=92)
        chain_board(c, shown, y=250)
        if shown == 1:
            c.text(28, 345, "requires_grad=True", size=18, mono=True, color=PURPLE, ha="left")
        if shown == 4:
            c.text(920, 345, "grad_fn=<AddBackward0>", size=17, mono=True, color=PURPLE)
        frames.append(c.image())
    c = Canvas(1120, 480)
    c.title("requires_grad 가 False 면 기록하지 않음")
    chain_board(c, 4, y=230, faded=True)
    c.text(28, 330, "requires_grad=False", size=18, mono=True, color=MUTED, ha="left")
    c.text(920, 330, "grad_fn 없음", size=18, color=MUTED)
    c.text(560, 420, "값 4.0 은 같지만 거꾸로 따라갈 기록이 없음", size=20, color=INK)
    frames.append(c.image())
    c = Canvas(1120, 480)
    c.title("기록된 계산의 연결 = 계산 그래프")
    chain_board(c, 4, y=230)
    c.text(560, 350, "x 에서 y 까지 세 계산을 차례로 기록", size=21)
    c.text(560, 400, "y.grad_fn 에는 마지막 계산(더하기)이 적힘", size=20, color=PURPLE)
    frames.append(c.image())
    return frames, [2200, 2000, 2000, 2200, 2400, 2500]


@figure("3g-2", 560, 250)
def fig_3g_2():
    xv = 3
    av, bv, yv = xv * 2, xv * 2 + 1, (xv * 2 + 1) ** 2
    assert (av, bv, yv) == (6, 7, 49)
    frames = []
    nodes = [("a = x * 2", av), ("b = a + 1", bv), ("y = b ** 2", yv)]

    def draw(left_state, right_n, summary=False):
        c = Canvas(1120, 500)
        c.line([560, 560], [70, 480], color=FAINT, lw=2)
        c.text(280, 50, "Define-and-run", size=22, bold=True, color=ORANGE)
        c.text(280, 85, "그래프를 먼저 정의하고 실행", size=18, color=MUTED)
        c.text(840, 50, "Define-by-run", size=22, bold=True, color=BLUE)
        c.text(840, 85, "실행하면서 그래프가 생김", size=18, color=MUTED)
        for k, (code, v) in enumerate(nodes):
            y = 160 + k * 100
            if left_state >= 1:
                c.box(130, y - 32, 300, 64, fc="white" if left_state == 1 else ORANGE_BG, ec=ORANGE, lw=2.5,
                      rounded=True)
                c.text(280, y, code if left_state == 1 else "%s → %d" % (code.split(" =")[0], v), size=19,
                       mono=True)
                if k < 2:
                    c.arrow(280, y + 34, 280, y + 66, color=ORANGE, lw=2.5, head=16)
            if k < right_n:
                c.box(690, y - 32, 300, 64, fc=BLUE_BG, ec=BLUE, lw=2.5, rounded=True)
                c.text(840, y, "%s → %d" % (code, v), size=19, mono=True)
                if k < right_n - 1:
                    c.arrow(840, y + 34, 840, y + 66, color=BLUE, lw=2.5, head=16)
        if left_state == 1 and not summary:
            c.text(280, 455, "x 를 넣기 전에 연결부터", size=18, color=ORANGE)
        if left_state == 2 and not summary:
            c.text(280, 455, "x = 3 을 넣음", size=18, color=ORANGE)
        if 0 < right_n and not summary:
            c.text(840, 455, "코드 %d줄 실행" % right_n, size=18, color=BLUE)
        if summary:
            c.text(280, 455, "TensorFlow 1.x", size=19, color=ORANGE, bold=True)
            c.text(840, 455, "PyTorch · TensorFlow 2.0 부터 기본", size=19, color=BLUE, bold=True)
        return c.image()

    frames = [draw(0, 0), draw(1, 0), draw(2, 0), draw(2, 1), draw(2, 2), draw(2, 3)]
    frames.append(draw(2, 3, summary=True))
    return frames, [2000, 2200, 2200, 2000, 2000, 2200, 2500]


@figure("3g-3", 560, 260)
def fig_3g_3():
    chain_check()
    frames = []
    titles = ["계산: 값을 왼쪽에서 오른쪽으로 채움", "y 에서 1 로 시작", "+ 2 의 미분 1 을 곱함: 1 × 1 = 1",
              "× 2 의 미분 2 를 곱함: 1 × 2 = 2", "제곱의 미분 2x = 2 를 곱함: 2 × 2 = 4", "x.grad = 4 = 4 × x"]
    acc = {3: 1.0}
    acc_list = [None, {3: 1.0}, {3: 1.0, 2: 1.0}, {3: 1.0, 2: 1.0, 1: 2.0}, {3: 1.0, 2: 1.0, 1: 2.0, 0: 4.0},
                {0: 4.0}]
    gfrom_list = [None, None, [2], [2, 1], [2, 1, 0], [2, 1, 0]]
    assert acc_list[4][0] == LOCAL[2] * LOCAL[1] * LOCAL[0] and acc[3] == 1.0
    for k in range(6):
        c = Canvas(1120, 520)
        c.title(titles[k], size=22)
        chain_board(c, 4, y=200, grads=acc_list[k], gfrom=gfrom_list[k], hl=0 if k == 5 else None)
        if k >= 1:
            c.text(560, 470, "오른쪽에서 왼쪽으로 미분을 곱해 감", size=19, color=ORANGE)
        frames.append(c.image())
    return frames, [2000, 2000, 2200, 2200, 2400, 2500]


@figure("3g-4", 560, 240)
def fig_3g_4():
    once = 4.0
    seq = [("x = torch.tensor(1.0, requires_grad=True)", None), ("y = 2 * x**2 + 2; y.backward()", once),
           ("y = 2 * x**2 + 2; y.backward()", once + once), ("x.grad.zero_()", 0.0),
           ("y = 2 * x**2 + 2; y.backward()", once)]
    assert [s[1] for s in seq] == [None, 4.0, 8.0, 0.0, 4.0]
    frames = []
    for k in range(len(seq)):
        c = Canvas(1120, 480)
        c.title("backward 는 기울기를 더하고 zero_() 는 0 으로")
        for j, (code, _) in enumerate(seq[:k + 1]):
            c.text(40, 110 + j * 62, code, size=17, mono=True, ha="left", color=INK if j == k else MUTED,
                   bg=YELLOW_BG if j == k else None, ec=ORANGE)
        v = seq[k][1]
        c.box(820, 170, 230, 130, fc=ORANGE_BG if v else PALE, ec=ORANGE, lw=3, rounded=True)
        c.text(935, 205, "x.grad", size=20, mono=True, color=MUTED)
        c.text(935, 255, "None" if v is None else num(v, True), size=32, mono=True, bold=True, color=ORANGE)
        if k == 2:
            c.text(935, 350, "4. + 4. = 8.", size=20, mono=True, color=RED)
        frames.append(c.image())
    c = Canvas(1120, 480)
    c.title("반복마다 지우고 다시 구함")
    for j, (code, v) in enumerate(seq):
        c.text(40, 110 + j * 62, code, size=17, mono=True, ha="left", color=INK)
        c.text(820, 110 + j * 62, "x.grad = " + ("None" if v is None else num(v, True)), size=19, mono=True,
               ha="left", color=ORANGE)
    frames.append(c.image())
    return frames, [2000, 2200, 2400, 2200, 2000, 2500]


@figure("3g-5", 560, 230)
def fig_3g_5():
    c = Canvas(1120, 460)
    c.title("x = torch.tensor(1.0, requires_grad=True)", size=21)
    c.box(36, 80, 500, 330, fc=BLUE_BG, ec=BLUE, lw=2.5, rounded=True)
    c.box(584, 80, 500, 330, fc=PALE, ec=MUTED, lw=2.5, rounded=True)
    c.text(60, 115, "보통 계산", size=21, ha="left", color=BLUE, bold=True)
    c.text(60, 175, "y = 2 * x**2 + 2", size=21, mono=True, ha="left")
    c.text(60, 245, "y.requires_grad → True", size=19, mono=True, ha="left", color=BLUE)
    c.text(60, 305, "계산을 기록함", size=19, ha="left")
    c.text(608, 115, "no_grad 안", size=21, ha="left", color=MUTED, bold=True)
    c.text(608, 175, "with torch.no_grad():", size=19, mono=True, ha="left")
    c.text(640, 215, "y = 2 * x**2 + 2", size=21, mono=True, ha="left")
    c.text(608, 275, "y.requires_grad → False", size=19, mono=True, ha="left", color=RED)
    c.text(608, 335, "기록하지 않아 메모리와 시간이 줄어듦", size=18, ha="left")
    return [c.image()], None


# 3h 코드 읽기

@figure("3h-1", 560, 240)
def fig_3h_1():
    frames = []

    def draw(title, cpu_items, gpu_items, tag_on, device_text, note=None, gpu=True):
        c = Canvas(1120, 480)
        c.title(title, size=21)
        c.text(36, 95, device_text, size=18, mono=True, ha="left", color=MUTED)
        c.box(80, 150, 380, 220, fc=PALE, ec=MUTED, lw=2.5, rounded=True)
        c.text(270, 180, "CPU", size=22, bold=True, color=MUTED)
        c.box(660, 150, 380, 220, fc=GREEN_BG if gpu else "white", ec=GREEN if gpu else FAINT, lw=2.5,
              rounded=True, ls="-" if gpu else "--")
        c.text(850, 180, "GPU (cuda)" if gpu else "GPU 없음", size=22, bold=True, color=GREEN if gpu else FAINT)
        for x0, items in ((130, cpu_items), (710, gpu_items)):
            for k, label in enumerate(items):
                c.cells(x0, 230 + k * 70, [["1.", "2.", "3."]], cw=60, ch=50, fill=lambda i, j: BLUE_BG, size=18)
                c.text(x0 + 200, 255 + k * 70, label, size=17, color=MUTED, ha="left")
        if tag_on is not None:
            tx = 220 if tag_on == "cpu" else 800
            c.text(tx, 420, "x", size=26, mono=True, bold=True, color=ORANGE, bg=ORANGE_BG, ec=ORANGE)
            c.arrow(tx, 400, tx, 285, color=ORANGE, lw=3)
        if note:
            c.text(560, 455, note, size=18, color=INK)
        return c.image()

    dline = 'device = torch.device("cuda" if torch.cuda.is_available() else "cpu")'
    frames.append(draw("GPU 가 있으면 device 는 cuda", [], [], None, dline, "is_available() 이 True → cuda"))
    frames.append(draw("x 는 처음에 CPU 에", ["원본"], [], "cpu", "x = torch.tensor([1., 2., 3.])"))
    frames.append(draw("x.to(device) 만 쓰면", ["원본"], ["옮긴 사본"], "cpu", "x.to(device)",
                       "사본은 생겼지만 x 는 여전히 CPU 텐서"))
    frames.append(draw("x = x.to(device) 로 받으면", ["원본"], ["옮긴 사본"], "gpu", "x = x.to(device)",
                       "이제 x 가 GPU 텐서"))
    frames.append(draw("GPU 가 없는 컴퓨터", ["원본"], [], "cpu", "device = cpu", "이미 cpu 라 x.to(device) 는 x 자신",
                       gpu=False))
    c = Canvas(1120, 480)
    c.title("장치 고르기와 옮기기")
    c.text(60, 140, dline, size=16, mono=True, ha="left")
    c.text(60, 220, "x = x.to(device)", size=22, mono=True, ha="left", color=GREEN, bold=True)
    c.text(60, 275, "옮긴 텐서를 돌려주므로 받아서 씀", size=20, ha="left")
    c.text(60, 350, "x.to(device)", size=22, mono=True, ha="left", color=RED)
    c.text(60, 405, "받지 않으면 x 는 원래 장치에 남음", size=20, ha="left")
    frames.append(c.image())
    return frames, [2200, 2000, 2400, 2200, 2400, 2500]


@figure("3h-2", 560, 230)
def fig_3h_2():
    c = Canvas(1120, 460)
    c.title("텐서에서 파이썬 숫자와 numpy 배열 꺼내기")
    rows = [("loss", "원소 1개", ".item()", "0.25 (파이썬 float)", GREEN),
            ("y", "requires_grad=True", ".numpy()", "RuntimeError", RED),
            ("y", "requires_grad=True", ".detach().numpy()", "numpy 배열", GREEN),
            ("r2", "requires_grad=False", ".numpy()", "numpy 배열 (float32)", GREEN)]
    for k, (name, note, call, out, col) in enumerate(rows):
        y = 110 + k * 80
        c.text(40, y, name, size=22, mono=True, ha="left", bold=True)
        c.text(120, y, note, size=17, ha="left", color=MUTED)
        c.text(420, y, call, size=21, mono=True, ha="left", color=col)
        c.text(720, y, "→ " + out, size=20, ha="left", color=col, bold=col == RED)
    return [c.image()], None


@figure("3h-3", 560, 240)
def fig_3h_3():
    a = [1.5, 2.5, 3.5]
    shared = list(a)
    copied = list(a)
    shared[0] = 9.0  # a[0] = 9.0 은 같은 메모리를 보는 t1 에도 보임
    assert shared == [9.0, 2.5, 3.5] and copied == [1.5, 2.5, 3.5]
    frames = []

    def draw(title, a_vals, t1=False, t2=False, t2_vals=None, note=None, dtype=False):
        c = Canvas(1120, 480)
        c.title(title, size=21)
        c.text(60, 130, "a (numpy, float64)", size=19, ha="left", color=MUTED)
        c.cells(330, 105, [[num(v) for v in a_vals]], cw=80, ch=52, fill=lambda i, j: PALE, size=20)
        if t1:
            c.text(60, 220, "t1 = torch.from_numpy(a)", size=19, mono=True, ha="left", color=BLUE)
            for j in range(3):
                c.arrow(370 + j * 80, 200, 370 + j * 80, 162, color=BLUE, lw=2.5, head=16)
            c.text(600, 220, "메모리를 함께 씀", size=19, ha="left", color=BLUE)
        if t2:
            c.text(60, 300, "t2 = torch.tensor(a)", size=19, mono=True, ha="left", color=GREEN)
            c.cells(330, 325, [[num(v) for v in t2_vals]], cw=80, ch=52, fill=lambda i, j: GREEN_BG, ec=GREEN,
                    size=20)
            c.text(600, 352, "값을 복사한 새 텐서", size=19, ha="left", color=GREEN)
        if dtype:
            c.text(60, 430, "float64 → .float() → float32", size=20, mono=True, ha="left", color=ORANGE)
        if note:
            c.text(560, 455, note, size=19, color=INK)
        return c.image()

    frames.append(draw("a = np.array([1.5, 2.5, 3.5])", a))
    frames.append(draw("torch.from_numpy(a)", a, t1=True))
    frames.append(draw("torch.tensor(a)", a, t1=True, t2=True, t2_vals=copied))
    frames.append(draw("a[0] = 9.0 다음", shared, t1=True, t2=True, t2_vals=copied, note="t1[0] 은 9.0, t2[0] 은 1.5"))
    frames.append(draw("자료형 맞추기", shared, t1=True, t2=True, t2_vals=copied, dtype=True))
    c = Canvas(1120, 480)
    c.title("numpy 와 텐서 오가기")
    c.text(60, 140, "torch.from_numpy(a)  메모리를 함께 씀", size=21, ha="left", color=BLUE)
    c.text(60, 200, "t.numpy()            메모리를 함께 씀", size=21, ha="left", color=BLUE)
    c.text(60, 260, "torch.tensor(a)      복사", size=21, ha="left", color=GREEN)
    c.text(60, 340, "numpy 가 소수로 만드는 배열은 기본이 float64 → .float() 로 float32", size=20, ha="left",
           color=ORANGE)
    frames.append(c.image())
    return frames, [2000, 2200, 2200, 2400, 2200, 2500]


@figure("3h-4", 560, 200)
def fig_3h_4():
    c = Canvas(1120, 400)
    c.title("난수 고정")
    pats = {"A": [BLUE, ORANGE, GREEN, PURPLE, BLUE], "B": [GREEN, GREEN, PURPLE, ORANGE, BLUE],
            "C": [ORANGE, BLUE, BLUE, GREEN, PURPLE]}
    rows = [("manual_seed(123) 뒤 1번째 실행", "A"), ("manual_seed(123) 뒤 2번째 실행", "A"),
            ("시드 없이 1번째 실행", "B"), ("시드 없이 2번째 실행", "C")]
    assert pats[rows[0][1]] == pats[rows[1][1]] and pats[rows[2][1]] != pats[rows[3][1]]
    for k, (label, p) in enumerate(rows):
        y = 100 + k * 70
        c.text(40, y, label, size=19, ha="left", color=INK if k < 2 else MUTED)
        for j, col in enumerate(pats[p]):
            c.box(500 + j * 70, y - 24, 60, 48, fc=col, ec="white", lw=2)
        c.text(880, y, "같은 수열" if k < 2 else "매번 다른 수열", size=18, ha="left", color=GREEN if k < 2 else MUTED)
    return [c.image()], None


# 저장

def save(name, frames, ms):
    os.makedirs(OUT, exist_ok=True)
    w, h = frames[0].size
    assert w <= LIMIT["width"] and h <= LIMIT["height"], (name, w, h)
    if ms is None:
        assert len(frames) == 1
        img = frames[0].quantize(colors=COLORS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        path = os.path.join(OUT, name + ".png")
        img.save(path, optimize=True)
        assert os.path.getsize(path) <= LIMIT["png"], (name, os.path.getsize(path))
        return path
    assert len(frames) == len(ms) and len(frames) <= LIMIT["frames"], name
    assert all(LIMIT["ms_min"] <= t <= LIMIT["ms_max"] and t % 10 == 0 for t in ms), name
    for f in frames:
        assert f.size == (w, h), (name, f.size)
    for a, b in zip(frames, frames[1:]):
        assert a.tobytes() != b.tobytes(), "%s 에 같은 장이 이어짐" % name
    sheet = Image.new("RGB", (w, h * len(frames)), "white")
    for k, f in enumerate(frames):
        sheet.paste(f, (0, h * k))
    pal = sheet.quantize(colors=COLORS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    path = os.path.join(OUT, name + ".gif")
    q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=False, disposal=1)
    with Image.open(path) as check:
        assert check.n_frames == len(frames), (name, check.n_frames)
    assert os.path.getsize(path) <= LIMIT["gif"], (name, os.path.getsize(path))
    return path


def main(argv):
    wanted = set(argv)
    total = 0
    for name, width, height, fn in FIGS:
        if wanted and name not in wanted:
            continue
        frames, ms = fn()
        assert frames[0].size == (width * SCALE, height * SCALE), (name, frames[0].size)
        path = save(name, frames, ms)
        size = os.path.getsize(path)
        total += size
        print("%-6s %2d장 %4dx%-4d %6.1fKB" % (name, len(frames), frames[0].size[0], frames[0].size[1], size / KB))
    print("합계 %.1fKB" % (total / KB))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
