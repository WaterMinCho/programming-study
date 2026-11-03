#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2차시 학습 노트 l02 의 그림. 그림에 찍는 숫자는 모두 이 파일에서 numpy로 다시 계산하고 assert로 확인함.

  python tools/ai_art/l02.py                 ai/learn/l02/assets/ 에 그림을 모두 씀
  python tools/ai_art/l02.py l02-3 l02-7     이름을 적은 그림만
  python tools/ai_art/l02.py --out DIR       다른 폴더에 씀

matplotlib는 Agg 로만 씀(창을 띄우지 않음). numpy·matplotlib·Pillow가 있는 출제자 파이썬에서만 돌림.
파일 폭 1120px, 높이 600px 이하, GIF는 6~10장·장마다 1600~2500ms·64색, 마지막 장은 정지 요약임.
글꼴은 gui/fonts의 NanumGothic(글)과 D2Coding(코드·배열)을 씀.
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "ai", "learn", "l02", "assets")
FONTS = os.path.join(ROOT, "gui", "fonts")
for _name in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf", "D2Coding-Regular.ttf", "D2Coding-Bold.ttf"):
    font_manager.fontManager.addfont(os.path.join(FONTS, _name))
plt.rcParams.update({"font.family": ["NanumGothic", "DejaVu Sans"], "axes.unicode_minus": False,
                     "figure.facecolor": "white", "savefig.facecolor": "white"})

W = 1120
MAX_H = 600
COLORS = 64
INK, MUTED, FAINT, LINE = "#1f2937", "#6b7280", "#d1d5db", "#9ca3af"
BLUE, ORANGE, GREEN, RED, PURPLE = "#1d4ed8", "#c2410c", "#047857", "#b91c1c", "#6d28d9"
BLUE_L, ORANGE_L, GREEN_L, RED_L, GRAY_L, HL = "#dbeafe", "#ffedd5", "#d1fae5", "#fee2e2", "#f3f4f6", "#fef3c7"
PURPLE_L, YELLOW_L = "#ede9fe", "#fde68a"
CODE = "D2Coding"
# 2c 단원 색: 파랑은 0번 축, 주황은 1번 축, 보라는 2번 축, 초록은 결과, 노랑은 따라가는 값(M의 0번 행)

# 이 차시 전체에 쓰는 예
DATA = np.array([3, 8, 1, 6, 2, 9])
M = DATA.reshape(2, 3)
assert M.tolist() == [[3, 8, 1], [6, 2, 9]]

FIGS = []


def figure(name, kind):
    """그림 함수를 이름과 종류(gif·png)로 등록함."""
    def wrap(fn):
        FIGS.append((name, kind, fn))
        return fn
    return wrap


# ---------- 그리기 도우미

class Canvas:
    """픽셀 좌표(왼쪽 위가 0, 0)로 그리는 한 장."""

    def __init__(self, h=520):
        assert h <= MAX_H
        self.h = h
        self.fig = plt.figure(figsize=(W / 100, h / 100), dpi=100)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(h, 0)
        self.ax.axis("off")

    def text(self, x, y, s, size=21, color=INK, ha="left", va="center", code=False, bold=False, bg=None, z=6):
        kw = dict(fontsize=size, color=color, ha=ha, va=va, zorder=z)
        if code:
            kw["family"] = CODE
        if bold:
            kw["weight"] = "bold"
        if bg:
            kw["bbox"] = dict(boxstyle="round,pad=0.25", fc=bg, ec=bg)
        return self.ax.text(x, y, s, **kw)

    def title(self, s):
        self.text(28, 30, s, size=23, bold=True)

    def box(self, x, y, w, h, fc="white", ec=INK, lw=1.6, ls="-", z=2, round_=False):
        if round_:
            p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=10", fc=fc, ec=ec, lw=lw, ls=ls, zorder=z)
        else:
            p = Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, ls=ls, zorder=z)
        self.ax.add_patch(p)

    def grid(self, x, y, vals, cw=66, ch=52, fill=None, ec=INK, tc=None, size=22, ls="-", lw=1.6, note=None):
        """2차원 값 목록을 칸으로 그림. fill·tc는 (i, j)를 받아 색을 주는 함수나 한 색. 돌려주는 값은 칸 가운데 좌표."""
        centers = {}
        for i, row in enumerate(vals):
            for j, v in enumerate(row):
                fc = fill(i, j) if callable(fill) else (fill or "white")
                col = tc(i, j) if callable(tc) else (tc or INK)
                self.box(x + j * cw, y + i * ch, cw, ch, fc=fc, ec=ec, lw=lw, ls=ls)
                if v is not None and v != "":
                    self.text(x + j * cw + cw / 2, y + i * ch + ch / 2, str(v), size=size, color=col, ha="center", code=True)
                if note:
                    s = note(i, j)
                    if s is not None:
                        self.text(x + j * cw + 4, y + i * ch + 11, str(s), size=13, color=MUTED, code=True)
                centers[(i, j)] = (x + j * cw + cw / 2, y + i * ch + ch / 2)
        return centers

    def arrow(self, x1, y1, x2, y2, color=INK, lw=2.4, style="-|>", z=5, ls="-", rad=0.0):
        a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=20, color=color, lw=lw, zorder=z,
                            linestyle=ls, connectionstyle="arc3,rad=%s" % rad)
        self.ax.add_patch(a)

    def line(self, xs, ys, color=INK, lw=2, ls="-", z=3):
        self.ax.plot(xs, ys, color=color, lw=lw, ls=ls, zorder=z)

    def image(self):
        self.fig.canvas.draw()
        buf = np.asarray(self.fig.canvas.buffer_rgba())
        img = Image.fromarray(buf[..., :3].copy())
        plt.close(self.fig)
        return img


def fmt(v):
    """배열 원소 표기. 정수면 정수로, 아니면 짧은 소수로."""
    v = float(v)
    if v == int(v):
        return str(int(v))
    return ("%.3f" % v).rstrip("0")


def arr1(v):
    return "[" + ", ".join(fmt(x) for x in v) + "]"


def arr2(m):
    return "[" + ", ".join(arr1(r) for r in m) + "]"


def save_gif(path, frames, ms):
    assert 6 <= len(frames) <= 10, (path, len(frames))
    assert all(1600 <= d <= 2500 for d in ms), (path, ms)
    w, h = frames[0].size
    assert w <= W and h <= MAX_H
    sheet = Image.new("RGB", (w, h * len(frames)), "white")
    for k, f in enumerate(frames):
        assert f.size == (w, h)
        sheet.paste(f, (0, h * k))
    pal = sheet.quantize(colors=COLORS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True, disposal=1)


def save_png(path, img):
    assert img.size[0] <= W and img.size[1] <= MAX_H
    img.quantize(colors=COLORS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(path, optimize=True)


# ---------- 2a 리스트와 배열

@figure("l02-1", "png")
def list_vs_array():
    c = Canvas(500)
    c.title("리스트와 배열(ndarray)은 값을 다르게 저장함")
    c.text(28, 92, "파이썬 리스트", size=22, bold=True)
    c.text(250, 92, "칸에는 주소만, 값은 따로 만든 객체", size=17, color=MUTED)
    spots = [(520, 120), (650, 215), (790, 130), (920, 230), (1030, 140), (560, 255)]
    for k, v in enumerate(DATA):
        x = 60 + k * 54
        c.box(x, 150, 54, 44, fc=GRAY_L)
        c.text(x + 27, 172, "•", size=20, ha="center", color=MUTED)
        bx, by = spots[k]
        c.box(bx, by, 62, 48, fc="white", ec=MUTED, round_=True)
        c.text(bx + 31, by + 24, str(v), size=21, ha="center", code=True)
        c.arrow(x + 27, 172, bx, by + 24, color=LINE, lw=1.6)
    c.text(28, 240, "숫자와 문자열을 섞어 담을 수 있음", size=17, color=MUTED)
    c.line([20, 1100], [330, 330], color=FAINT, lw=1.5)
    c.text(28, 370, "numpy 배열 (ndarray)", size=22, bold=True)
    c.text(28, 400, "값을 연속 메모리에 바로 저장", size=17, color=MUTED)
    c.grid(60, 425, [list(DATA)], cw=70, ch=52, fill=BLUE_L)
    c.line([60, 60, 480, 480], [488, 494, 494, 488], color=BLUE, lw=2)
    c.text(560, 438, "dtype: int64", size=22, code=True, color=BLUE, bold=True)
    c.text(560, 472, "모든 원소가 같은 자료형", size=18, color=INK)
    return c.image()


VEC_LIST_MS = (10.7, 84.0)    # 원소 10만 개, 100만 개에서 리스트 방식으로 잰 시간
VEC_ARR_MS = (0.047, 1.1)     # 같은 개수에서 배열 방식으로 잰 시간


@figure("l02-2", "gif")
def vectorize():
    out = DATA * 2
    assert out.tolist() == [6, 16, 2, 12, 4, 18]
    frames, ms = [], []

    def base(done_list, done_arr, title):
        c = Canvas(500)
        c.title(title)
        c.text(28, 88, "리스트 컴프리헨션", size=20, bold=True)
        c.text(28, 120, "[x * 2 for x in data]", size=19, code=True, color=MUTED)
        c.grid(390, 72, [list(DATA)], cw=62, ch=50)
        c.grid(390, 150, [[fmt(out[k]) if k < done_list else "" for k in range(6)]], cw=62, ch=50,
               fill=lambda i, j: ORANGE_L if j < done_list else "white")
        c.text(375, 97, "입력", size=17, ha="right", color=MUTED)
        c.text(375, 175, "결과", size=17, ha="right", color=MUTED)
        c.line([20, 1100], [232, 232], color=FAINT, lw=1.5)
        c.text(28, 280, "numpy 배열", size=20, bold=True)
        c.text(28, 312, "data * 2", size=19, code=True, color=MUTED)
        c.grid(390, 264, [list(DATA)], cw=62, ch=50)
        c.grid(390, 342, [[fmt(v) if done_arr else "" for v in out]], cw=62, ch=50,
               fill=GREEN_L if done_arr else "white")
        c.text(375, 289, "입력", size=17, ha="right", color=MUTED)
        c.text(375, 367, "결과", size=17, ha="right", color=MUTED)
        return c

    c = base(0, False, "같은 결과를 내는 두 코드")
    frames.append(c.image()); ms.append(2000)
    for done in (1, 3, 6):
        c = base(done, False, "리스트 방식: 파이썬이 원소마다 곱셈을 처리")
        x = 390 + (done - 1) * 62 + 31
        c.arrow(x, 125, x, 148, color=ORANGE, lw=2.2)
        c.text(790, 110, "파이썬이 처리한 곱셈: %d번" % done, size=20, color=ORANGE, bg="white")
        frames.append(c.image()); ms.append(1800 if done < 6 else 2000)
    c = base(6, True, "배열 방식: 파이썬 줄은 한 번, 반복은 C 코드가")
    c.text(790, 110, "파이썬이 처리한 곱셈: 6번", size=20, color=ORANGE, bg="white")
    c.text(790, 300, "파이썬이 읽은 줄: 1번", size=18, color=GREEN, bg="white")
    c.text(790, 334, "곱셈 6번은 C 코드가 처리", size=18, color=GREEN, bg="white")
    frames.append(c.image()); ms.append(2400)
    c = Canvas(500)
    c.title("원소가 10배로 늘면 두 방식 모두 시간이 늘어남")
    c.text(28, 80, "한 컴퓨터에서 잰 값이며 컴퓨터마다 다름", size=18, color=MUTED)
    c.text(300, 140, "원소 10만 개", size=20, ha="center", bold=True)
    c.text(640, 140, "원소 100만 개", size=20, ha="center", bold=True)
    c.text(40, 210, "리스트 방식", size=21, color=ORANGE, bold=True)
    c.text(40, 300, "배열 방식", size=21, color=GREEN, bold=True)
    c.text(300, 210, "%sms" % fmt(VEC_LIST_MS[0]), size=24, ha="center", code=True)
    c.text(640, 210, "%sms" % fmt(VEC_LIST_MS[1]), size=24, ha="center", code=True)
    c.text(300, 300, "%sms" % fmt(VEC_ARR_MS[0]), size=24, ha="center", code=True)
    c.text(640, 300, "%sms" % fmt(VEC_ARR_MS[1]), size=24, ha="center", code=True)
    c.arrow(390, 210, 550, 210, color=ORANGE)
    c.arrow(390, 300, 550, 300, color=GREEN)
    c.text(800, 210, "늘어남", size=20, color=ORANGE)
    c.text(800, 300, "늘어남", size=20, color=GREEN)
    c.text(40, 400, "같은 개수에서 배열 방식이 훨씬 짧은 까닭은 반복을 C 코드가 맡아서임", size=19, color=INK)
    frames.append(c.image()); ms.append(2500)
    c = base(6, True, "결과는 같고, 배열 방식은 반복을 C 코드에 맡김")
    c.text(790, 110, "파이썬이 곱셈 6번", size=20, color=ORANGE, bg="white")
    c.text(790, 317, "파이썬 줄 1번 + C 반복", size=20, color=GREEN, bg="white")
    c.text(390, 440, "data * 2 = " + arr1(out), size=21, code=True)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-3", "png")
def shape_ndim():
    assert DATA.shape == (6,) and DATA.ndim == 1 and len(DATA) == 6
    assert M.shape == (2, 3) and M.ndim == 2 and len(M) == 2
    one = np.array([[1, 2, 3]])
    assert one.shape == (1, 3) and one.ndim == 2
    c = Canvas(520)
    c.title("shape은 축마다 원소 수, ndim은 축의 개수")
    c.text(40, 90, "data = np.array([3, 8, 1, 6, 2, 9])", size=16, code=True)
    c.grid(40, 150, [list(DATA)], cw=56, ch=50, fill=BLUE_L)
    for j in range(6):
        c.text(40 + j * 56 + 28, 135, str(j), size=15, color=BLUE, ha="center", code=True)
    c.arrow(40, 222, 376, 222, color=BLUE)
    c.text(40, 252, "0번 축: 6칸", size=19, color=BLUE)
    c.text(40, 310, "shape (6,)", size=22, code=True, bold=True)
    c.text(40, 350, "ndim 1    len 6", size=22, code=True)
    c.line([480, 480], [70, 500], color=FAINT, lw=1.5)
    c.text(510, 90, "M = np.array([[3, 8, 1], [6, 2, 9]])", size=16, code=True)
    c.grid(600, 150, M.tolist(), cw=66, ch=52, fill=GRAY_L)
    for i in range(2):
        c.text(585, 150 + i * 52 + 26, str(i), size=15, color=BLUE, ha="right", code=True)
    for j in range(3):
        c.text(600 + j * 66 + 33, 135, str(j), size=15, color=ORANGE, ha="center", code=True)
    c.arrow(560, 150, 560, 254, color=BLUE)
    c.text(545, 205, "0번 축\n2칸", size=18, color=BLUE, ha="right")
    c.arrow(600, 274, 798, 274, color=ORANGE)
    c.text(820, 274, "1번 축: 3칸", size=19, color=ORANGE)
    c.text(520, 330, "shape (2, 3)", size=22, code=True, bold=True)
    c.text(520, 370, "ndim 2    len 2", size=22, code=True)
    c.text(520, 425, "np.array([[1, 2, 3]])", size=18, code=True, color=MUTED)
    c.text(520, 460, "shape (1, 3), ndim 2", size=19, code=True, color=MUTED)
    return c.image()


@figure("l02-4", "png")
def fill_arrays():
    assert np.zeros(3).tolist() == [0, 0, 0]
    assert np.ones((2, 3)).tolist() == [[1, 1, 1], [1, 1, 1]]
    eye = np.eye(2, 3)
    assert eye.tolist() == [[1, 0, 0], [0, 1, 0]]
    assert np.random.randn(2, 3).shape == (2, 3)
    c = Canvas(520)
    c.title("모양을 정해 값을 채우는 함수")
    c.text(40, 85, "np.zeros(3)", size=20, code=True, bold=True)
    c.grid(40, 105, [["0.", "0.", "0."]], cw=60, ch=48)
    c.text(40, 180, "np.ones((2, 3))", size=20, code=True, bold=True)
    c.grid(40, 200, [["1."] * 3] * 2, cw=60, ch=48)
    c.text(40, 330, "모양은 튜플 하나로", size=18, color=MUTED)
    c.text(430, 85, "np.eye(2, 3)", size=20, code=True, bold=True)
    c.grid(430, 105, [[fmt(v) + "." for v in r] for r in eye], cw=60, ch=48,
           fill=lambda i, j: GREEN_L if i == j else "white")
    c.text(430, 225, "대각선 자리만 1", size=18, color=GREEN)
    c.text(780, 85, "np.random.randn(2, 3)", size=20, code=True, bold=True)
    c.grid(780, 105, [["?"] * 3] * 2, cw=60, ch=48, fill=GRAY_L, tc=MUTED)
    c.text(780, 225, "평균 0, 표준편차 1 인", size=18, color=MUTED)
    c.text(780, 252, "정규분포에서 뽑은 난수", size=18, color=MUTED)
    c.text(780, 279, "모양은 정수를 따로", size=18, color=MUTED)
    c.box(430, 330, 650, 130, fc=RED_L, ec=RED, round_=True)
    c.text(455, 365, "np.ones(2, 3)", size=21, code=True, color=RED, bold=True)
    c.text(455, 405, "TypeError: Cannot interpret '3' as a data type", size=16, code=True, color=RED)
    c.text(455, 440, "둘째 자리 3 을 자료형(dtype)으로 읽음", size=18, color=INK)
    return c.image()


@figure("l02-5", "png")
def arange_linspace():
    lin = np.linspace(-1, 1, 11)
    ar = np.arange(-1, 1, 0.2)
    assert len(lin) == 11 and lin[-1] == 1.0
    assert len(ar) == 10 and abs(ar[-1] - 0.8) < 1e-9
    assert np.arange(6).tolist() == [0, 1, 2, 3, 4, 5] and np.linspace(0, 5, 6).tolist() == [0, 1, 2, 3, 4, 5]
    c = Canvas(500)
    c.title("arange는 끝값을 빼고 linspace는 끝값을 넣음")
    x0, x1 = 120, 1000

    def px(v):
        return x0 + (v + 1) / 2 * (x1 - x0)

    for y, label, pts, n in ((150, "np.linspace(-1, 1, 11)", lin, 11), (290, "np.arange(-1, 1, 0.2)", ar, 10)):
        c.text(40, y - 52, label, size=20, code=True, bold=True)
        c.line([px(-1) - 20, px(1) + 20], [y, y], color=LINE, lw=2)
        for v in pts:
            c.ax.scatter([px(v)], [y], s=150, color=BLUE, zorder=5)
        if n == 10:
            c.ax.scatter([px(1.0)], [y], s=170, facecolor="white", edgecolor=RED, lw=2.5, zorder=5)
            c.text(px(1.0), y + 36, "1 빠짐", size=17, color=RED, ha="center")
        for v in (-1, 0, 1):
            c.text(px(v), y + 36 if not (n == 10 and v == 1) else y + 66, fmt(v), size=17, ha="center", code=True, color=MUTED)
        c.text(1040, y, "%d개" % n, size=21, bold=True, color=BLUE if n == 11 else INK)
    c.text(40, 420, "np.arange(6)       → [0 1 2 3 4 5]", size=19, code=True)
    c.text(40, 458, "np.linspace(0, 5, 6) → [0. 1. 2. 3. 4. 5.]", size=19, code=True)
    return c.image()


# ---------- 2b 꺼내기와 고르기

@figure("l02-6", "gif")
def indexing():
    assert M[1].tolist() == [6, 2, 9] and M[:, 2].tolist() == [1, 9] and M[1, 2] == 9
    assert repr(M[1, 2]) == "np.int64(9)" and M[1, 2].item() == 9
    frames, ms = [], []

    def base(title, pick=None, code="", result=None, res_note=""):
        c = Canvas(460)
        c.title(title)
        fill = (lambda i, j: GREEN_L if pick and pick(i, j) else "white")
        c.grid(140, 110, M.tolist(), cw=72, ch=58, fill=fill)
        for i in range(2):
            c.text(122, 110 + i * 58 + 29, str(i), size=17, color=BLUE, ha="right", code=True)
        for j in range(3):
            c.text(140 + j * 72 + 36, 94, str(j), size=17, color=ORANGE, ha="center", code=True)
        c.text(40, 139, "M", size=24, code=True, bold=True)
        c.text(40, 420, "행 번호(파랑)와 열 번호(주황)는 0 부터", size=17, color=MUTED)
        if code:
            c.text(480, 140, code, size=24, code=True, bold=True)
        if result is not None:
            c.text(480, 200, "→ " + result, size=24, code=True, color=GREEN)
            if res_note:
                c.text(480, 250, res_note, size=19, color=INK)
        return c

    frames.append(base("M의 행과 열 번호").image()); ms.append(2000)
    frames.append(base("M[1]: 1번 행 전체", lambda i, j: i == 1, "M[1]", "[6, 2, 9]", "shape (3,)").image()); ms.append(2000)
    frames.append(base("M[:, 2]: 모든 행의 2번 열", lambda i, j: j == 2, "M[:, 2]", "[1, 9]", "shape (2,), 1차원").image()); ms.append(2200)
    frames.append(base("M[1, 2]: 1번 행 2번 열 한 칸", lambda i, j: (i, j) == (1, 2), "M[1, 2]", "9", "M[1][2]도 같은 칸").image()); ms.append(2000)
    c = base("numpy 숫자를 파이썬 숫자로", lambda i, j: (i, j) == (1, 2), "M[1, 2]", "np.int64(9)", "")
    c.text(480, 260, "M[1, 2].item()", size=24, code=True, bold=True)
    c.text(480, 320, "→ 9  (파이썬 int)", size=24, code=True, color=GREEN)
    frames.append(c.image()); ms.append(2200)
    c = base("M[2]: 없는 행 번호")
    c.box(140, 226, 216, 58, fc=RED_L, ec=RED, ls="--")
    c.text(248, 255, "2번 행 없음", size=18, color=RED, ha="center")
    c.text(480, 140, "M[2]", size=24, code=True, bold=True)
    c.text(480, 200, "→ IndexError", size=24, code=True, color=RED)
    c.text(480, 250, "0번 축 길이가 2 라 행 번호는 0, 1", size=19)
    frames.append(c.image()); ms.append(2200)
    c = Canvas(460)
    c.title("행, 열, 한 칸 꺼내기")
    for k, (code, pick, res) in enumerate((("M[1]", lambda i, j: i == 1, "[6, 2, 9]"),
                                           ("M[:, 2]", lambda i, j: j == 2, "[1, 9]"),
                                           ("M[1, 2]", lambda i, j: (i, j) == (1, 2), "9"))):
        x = 50 + k * 360
        c.text(x, 95, code, size=23, code=True, bold=True)
        c.grid(x, 120, M.tolist(), cw=62, ch=50, fill=lambda i, j, p=pick: GREEN_L if p(i, j) else "white", size=20)
        c.text(x, 270, "→ " + res, size=23, code=True, color=GREEN)
    c.text(50, 360, "M[2] → IndexError", size=21, code=True, color=RED)
    c.text(50, 400, "M[1, 2].item() → 9", size=21, code=True)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-7", "gif")
def mask_select():
    mask = DATA > 5
    assert mask.tolist() == [False, True, False, True, False, True]
    assert DATA[mask].tolist() == [8, 6, 9] and int(mask.sum()) == 3
    frames, ms = [], []
    x0, cw = 300, 76

    def base(title, show_mask=False, fade=False):
        c = Canvas(480)
        c.title(title)
        c.text(40, 120, "data", size=22, code=True, bold=True)
        c.grid(x0, 95, [list(DATA)], cw=cw, ch=54,
               fill=lambda i, j: (GREEN_L if mask[j] else GRAY_L) if fade else "white",
               tc=lambda i, j: (INK if mask[j] else LINE) if fade else INK)
        for j in range(6):
            c.text(x0 + j * cw + cw / 2, 80, str(j), size=15, color=MUTED, ha="center", code=True)
        if show_mask:
            c.text(40, 210, "data > 5", size=22, code=True, bold=True)
            c.grid(x0, 185, [["True" if m else "False" for m in mask]], cw=cw, ch=54, size=17,
                   fill=lambda i, j: GREEN_L if mask[j] else GRAY_L, tc=lambda i, j: GREEN if mask[j] else MUTED)
        return c

    frames.append(base("data 여섯 칸").image()); ms.append(1800)
    c = base("data > 5: 칸마다 비교해 True·False", show_mask=True)
    c.text(40, 300, "True·False로 된 이 배열이 마스크", size=19, color=INK)
    frames.append(c.image()); ms.append(2200)
    c = base("True 자리만 남기기", show_mask=True, fade=True)
    frames.append(c.image()); ms.append(2000)
    c = base("data[data > 5]: True 자리 값을 모음", show_mask=True, fade=True)
    c.text(40, 320, "data[data > 5]", size=22, code=True, bold=True)
    c.grid(x0, 295, [[8, 6, 9]], cw=cw, ch=54, fill=GREEN_L)
    for src, dst in ((1, 0), (3, 1), (5, 2)):
        c.arrow(x0 + src * cw + cw / 2, 241, x0 + dst * cw + cw / 2, 293, color=GREEN, lw=1.8)
    c.text(x0 + 3 * cw + 20, 322, "길이 3", size=19, color=GREEN)
    frames.append(c.image()); ms.append(2400)
    c = base("mask.sum(): True의 개수", show_mask=True)
    c.text(40, 320, "더할 때", size=20)
    c.grid(x0, 295, [[1 if m else 0 for m in mask]], cw=cw, ch=54, fill=lambda i, j: GREEN_L if mask[j] else GRAY_L)
    c.text(x0 + 6 * cw + 24, 322, "합 3", size=24, color=GREEN, bold=True)
    c.text(40, 400, "True는 1, False는 0 으로 셈", size=19)
    frames.append(c.image()); ms.append(2400)
    c = base("조건으로 고르기", show_mask=True, fade=True)
    c.text(40, 320, "data[data > 5]", size=21, code=True)
    c.text(400, 320, "→ [8, 6, 9]", size=21, code=True, color=GREEN)
    c.text(40, 370, "(data > 5).sum()", size=21, code=True)
    c.text(400, 370, "→ 3", size=21, code=True, color=GREEN)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-8", "png")
def row_mask_uses():
    rows = np.array([False, True])
    assert M[rows].tolist() == [[6, 2, 9]] and M[rows].shape == (1, 3)
    c = Canvas(480)
    c.title("행 마스크와 불리언 인덱싱을 쓰는 곳")
    c.text(40, 90, "M[[False, True]]", size=21, code=True, bold=True)
    c.grid(70, 120, M.tolist(), cw=66, ch=52, fill=lambda i, j: GREEN_L if rows[i] else GRAY_L,
           tc=lambda i, j: INK if rows[i] else LINE)
    c.text(55, 146, "F", size=18, color=MUTED, ha="right", code=True)
    c.text(55, 198, "T", size=18, color=GREEN, ha="right", code=True)
    c.arrow(290, 198, 340, 198, color=GREEN)
    c.grid(350, 172, [[6, 2, 9]], cw=66, ch=52, fill=GREEN_L)
    c.text(350, 260, "shape (1, 3)", size=20, code=True, color=GREEN)
    uses = (("이상치 제거", "범위를 벗어난 값을 빼거나 0 으로"),
            ("0 과 1 로 나누기", "확률 0.5 이상만 1 로"),
            ("결측치 찾기", "NaN 인 자리 찾기"),
            ("정답으로 고르기", "정답이 1 인 데이터만"))
    for k, (head, body) in enumerate(uses):
        y = 105 + k * 88
        c.box(640, y - 30, 450, 74, fc=GRAY_L, ec=FAINT, round_=True)
        c.text(660, y - 6, head, size=20, bold=True)
        c.text(660, y + 24, body, size=17, color=MUTED)
    c.text(40, 330, "행 수와 길이가 같은 마스크를 넣으면", size=18, color=MUTED)
    c.text(40, 360, "True 인 행만 남음", size=18, color=MUTED)
    return c.image()


@figure("l02-9", "png")
def where_vs_mask():
    mask = DATA > 5
    a = DATA[mask]
    b = np.where(mask, DATA, 0)
    d = np.where(mask, 1, 0)
    assert a.tolist() == [8, 6, 9] and b.tolist() == [0, 8, 0, 6, 0, 9] and d.tolist() == [0, 1, 0, 1, 0, 1]
    c = Canvas(500)
    c.title("np.where는 길이를 지키고 불리언 인덱싱은 고른 것만 남김")
    x0, cw = 470, 70
    rows = (("data", list(DATA), None), ("data > 5", ["T" if m else "F" for m in mask], "m"),
            ("data[data > 5]", list(a), "a"), ("np.where(data > 5, data, 0)", list(b), "b"),
            ("np.where(data > 5, 1, 0)", list(d), "d"))
    for k, (label, vals, kind) in enumerate(rows):
        y = 80 + k * 80
        c.text(40, y + 26, label, size=19, code=True, bold=kind is None)
        fill = (lambda i, j: GREEN_L if mask[j] else GRAY_L) if kind in ("m", "b", "d") else (GREEN_L if kind == "a" else "white")
        c.grid(x0, y, [vals], cw=cw, ch=52, fill=fill, size=20)
        if kind in ("a", "b", "d"):
            c.text(x0 + 6 * cw + 18, y + 26, "길이 %d" % len(vals), size=18, color=GREEN if kind == "a" else INK)
    return c.image()


# ---------- 2c 모양 바꾸기

@figure("l02-10", "gif")
def reshape_order():
    r23, r32, r61 = DATA.reshape(2, 3), DATA.reshape(3, 2), DATA.reshape(6, 1)
    assert r23.tolist() == [[3, 8, 1], [6, 2, 9]] and r32.tolist() == [[3, 8], [1, 6], [2, 9]]
    assert r61.ravel().tolist() == list(DATA)
    pos = {v: k for k, v in enumerate(DATA)}
    frames, ms = [], []

    def strip(c, done=0):
        c.text(40, 108, "data", size=22, code=True, bold=True)
        c.grid(160, 85, [list(DATA)], cw=64, ch=48, fill=lambda i, j: GRAY_L if j < done else "white",
               tc=lambda i, j: LINE if j < done else INK, note=lambda i, j: j)

    def shaped(c, x, y, vals, label, upto=99, side=False):
        if side:
            c.text(x + len(vals[0]) * 64 + 20, y + 24, label, size=19, code=True, bold=True)
        else:
            c.text(x, y - 22, label, size=19, code=True, bold=True)
        cells = [[v if pos[v] < upto else "" for v in row] for row in vals]
        c.grid(x, y, cells, cw=64, ch=48, fill=lambda i, j: GREEN_L if vals[i][j] is not None and pos[vals[i][j]] < upto else "white",
               note=lambda i, j: pos[vals[i][j]] if pos[vals[i][j]] < upto else None)

    c = Canvas(460)
    c.title("원소 여섯 개, 작은 숫자는 원래 자리 번호")
    strip(c)
    frames.append(c.image()); ms.append(1800)
    c = Canvas(460)
    c.title("reshape(2, 3): 앞의 세 개가 0번 행")
    strip(c, 3)
    shaped(c, 160, 220, r23.tolist(), "data.reshape(2, 3)", upto=3, side=True)
    for j in range(3):
        c.arrow(160 + j * 64 + 32, 135, 160 + j * 64 + 32, 218, color=GREEN, lw=1.6)
    frames.append(c.image()); ms.append(2000)
    c = Canvas(460)
    c.title("reshape(2, 3): 다음 세 개가 1번 행")
    strip(c, 6)
    shaped(c, 160, 220, r23.tolist(), "data.reshape(2, 3)", side=True)
    frames.append(c.image()); ms.append(2000)
    c = Canvas(460)
    c.title("reshape(3, 2): 두 개씩 끊어 세 행")
    strip(c, 6)
    shaped(c, 160, 220, r32.tolist(), "data.reshape(3, 2)", side=True)
    frames.append(c.image()); ms.append(2000)
    c = Canvas(460)
    c.title("reshape(6, 1): 한 개씩 끊어 여섯 행")
    strip(c, 6)
    c.text(600, 198, "data.reshape(6, 1)", size=19, code=True, bold=True)
    c.grid(600, 215, [[v] for v in DATA[:4]], cw=64, ch=48, fill=GREEN_L, note=lambda i, j: i)
    c.text(632, 425, "…", size=22, ha="center")
    c.text(700, 300, "shape (6, 1)", size=20, code=True)
    frames.append(c.image()); ms.append(2000)
    c = Canvas(460)
    c.title("원소 순서는 같고 끊는 자리만 바뀜")
    shaped(c, 60, 130, r23.tolist(), "reshape(2, 3)")
    shaped(c, 380, 130, r32.tolist(), "reshape(3, 2)")
    c.text(680, 108, "reshape(6, 1)", size=19, code=True, bold=True)
    c.grid(680, 130, [[v] for v in DATA], cw=64, ch=48, fill=GREEN_L, note=lambda i, j: i)
    c.text(60, 300, "원소 수 6 = 2×3 = 3×2 = 6×1", size=20)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-11", "png")
def minus_one():
    assert DATA.reshape(3, -1).shape == (3, 2)
    assert np.arange(24).reshape(2, -1, 3).shape == (2, 4, 3)
    assert np.zeros((1, 3, 1)).squeeze().shape == (3,)
    for bad in ((4, -1), (-1, -1)):
        try:
            DATA.reshape(*bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    c = Canvas(520)
    c.title("-1 자리는 남은 길이를 나눗셈으로 정함")
    rows = (("data.reshape(3, -1)", "6 ÷ 3 = 2", "(3, 2)", True),
            ("n9.reshape(2, -1, 3)", "24 ÷ (2×3) = 4", "(2, 4, 3)", True),
            ("data.reshape(4, -1)", "6 ÷ 4 = 1.5", "ValueError", False),
            ("data.reshape(-1, -1)", "-1 은 한 자리만", "ValueError", False))
    for k, (code, calc, res, ok) in enumerate(rows):
        y = 100 + k * 78
        c.text(40, y, code, size=21, code=True, bold=True)
        c.text(470, y, calc, size=21)
        c.text(790, y, "→ " + res, size=21, code=True, color=GREEN if ok else RED)
    c.text(40, 210, "n9 는 원소 24개(np.arange(24))", size=16, color=MUTED)
    c.line([20, 1100], [430, 430], color=FAINT, lw=1.5)
    c.text(40, 470, "np.zeros((1, 3, 1)).squeeze()", size=21, code=True, bold=True)
    c.text(560, 470, "(1, 3, 1) → (3,)", size=20, code=True)
    c.text(790, 470, "길이 1 인 축을 지움", size=20)
    return c.image()


@figure("l02-12", "gif")
def transpose_2d():
    T = M.T
    R = M.reshape(3, 2)
    assert T.tolist() == [[3, 6], [8, 2], [1, 9]] and R.tolist() == [[3, 8], [1, 6], [2, 9]]
    assert DATA.T.shape == (6,) and DATA.reshape(6, 1).T.shape == (1, 6)
    row_of = {v: i for i, r in enumerate(M.tolist()) for v in r}
    tint = (YELLOW_L, "white")   # M의 0번 행에서 온 값만 노랑
    frames, ms = [], []

    def src(c, x=60, y=110):
        c.text(x, y - 24, "M  (2, 3)", size=20, code=True, bold=True)
        c.grid(x, y, M.tolist(), cw=64, ch=50, fill=lambda i, j: tint[i])

    def tgrid(c, x, y, vals, label, upto=None):
        c.text(x, y - 24, label, size=20, code=True, bold=True)
        cells = [[v if upto is None or row_of[v] < upto else "" for v in r] for r in vals]
        c.grid(x, y, cells, cw=64, ch=50, fill=lambda i, j: tint[row_of[vals[i][j]]] if cells[i][j] != "" else "white")

    c = Canvas(480)
    c.title("M의 0번 행을 노랑으로 칠함")
    src(c)
    frames.append(c.image()); ms.append(1800)
    c = Canvas(480)
    c.title("M.T: 0번 행이 0번 열로")
    src(c)
    tgrid(c, 460, 110, T.tolist(), "M.T  (3, 2)", upto=1)
    c.arrow(256, 135, 455, 135, color=INK, lw=1.8)
    frames.append(c.image()); ms.append(2000)
    c = Canvas(480)
    c.title("M.T: 1번 행이 1번 열로, [i, j]가 [j, i] 자리로")
    src(c)
    tgrid(c, 460, 110, T.tolist(), "M.T  (3, 2)")
    c.arrow(256, 185, 556, 264, color=INK, lw=1.8)
    frames.append(c.image()); ms.append(2200)
    c = Canvas(480)
    c.title("같은 (3, 2) 라도 값이 놓인 자리가 다름")
    src(c)
    tgrid(c, 460, 110, T.tolist(), "M.T")
    tgrid(c, 760, 110, R.tolist(), "M.reshape(3, 2)")
    c.text(460, 300, "열마다 한 행", size=18, color=MUTED)
    c.text(760, 300, "앞에서부터 두 개씩", size=18, color=MUTED)
    frames.append(c.image()); ms.append(2400)
    c = Canvas(480)
    c.title("1차원 배열의 .T: shape이 바뀌지 않음")
    c.text(60, 110, "data.T", size=21, code=True, bold=True)
    c.grid(60, 130, [list(DATA)], cw=60, ch=48)
    c.text(480, 154, "shape (6,), 바뀌지 않음", size=21, code=True, color=RED)
    c.text(60, 250, "축이 하나뿐이라 바꿀 축이 없음", size=19)
    frames.append(c.image()); ms.append(2000)
    c = Canvas(480)
    c.title("열벡터는 reshape(6, 1), 그 .T는 (1, 6)")
    c.text(60, 86, "data.reshape(6, 1)", size=19, code=True, bold=True)
    c.grid(60, 100, [[v] for v in DATA], cw=56, ch=46)
    c.text(140, 260, "(6, 1)", size=20, code=True)
    c.text(400, 186, "data.reshape(6, 1).T", size=19, code=True, bold=True)
    c.grid(400, 205, [list(DATA)], cw=56, ch=46)
    c.text(400, 290, "(1, 6)", size=20, code=True)
    frames.append(c.image()); ms.append(2200)
    c = Canvas(480)
    c.title("전치는 행과 열을 바꾸고 reshape는 끊는 자리를 바꿈")
    src(c)
    tgrid(c, 460, 110, T.tolist(), "M.T")
    tgrid(c, 760, 110, R.tolist(), "M.reshape(3, 2)")
    c.text(60, 330, "data.T → (6,)", size=20, code=True)
    c.text(60, 372, "data.reshape(6, 1).T → (1, 6)", size=20, code=True)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-13", "gif")
def transpose_3d():
    a = np.arange(24).reshape(2, 3, 4)
    b = np.transpose(a, (1, 2, 0))
    assert np.transpose(a).shape == (4, 3, 2) and b.shape == (3, 4, 2)
    assert a[1, 2, 3] == 23 and b[2, 3, 1] == 23
    chip_col = (BLUE, ORANGE, PURPLE)
    chip_fill = (BLUE_L, ORANGE_L, PURPLE_L)
    sizes = a.shape
    frames, ms = [], []

    def chips(c, x, y, order, label):
        c.text(x + 3 * 150 + 10, y + 12, label, size=18, code=True, bold=True)
        for k, ax_ in enumerate(order):
            c.box(x + k * 150, y, 136, 66, fc=chip_fill[ax_], ec=chip_col[ax_], round_=True)
            c.text(x + k * 150 + 68, y + 22, "옛 %d번 축" % ax_, size=16, color=chip_col[ax_], ha="center")
            c.text(x + k * 150 + 68, y + 48, str(sizes[ax_]), size=22, color=INK, ha="center", code=True, bold=True)
        c.text(x + 3 * 150 + 10, y + 50, "→ (" + ", ".join(str(sizes[o]) for o in order) + ")", size=22, code=True)

    c = Canvas(500)
    c.title("a = np.arange(24).reshape(2, 3, 4)")
    chips(c, 60, 120, (0, 1, 2), "a.shape")
    c.text(60, 260, "0번 축은 2개, 1번 축은 3개, 2번 축은 4개", size=20)
    frames.append(c.image()); ms.append(2000)
    c = Canvas(500)
    c.title("np.transpose(a): 축 순서를 뒤집음")
    chips(c, 60, 120, (0, 1, 2), "a.shape")
    chips(c, 60, 300, (2, 1, 0), "np.transpose(a).shape")
    for old, new in ((0, 2), (1, 1), (2, 0)):
        c.arrow(60 + old * 150 + 68, 190, 60 + new * 150 + 68, 298, color=chip_col[old], lw=1.8)
    frames.append(c.image()); ms.append(2200)
    c = Canvas(500)
    c.title("np.transpose(a, (1, 2, 0)): 새 i번 축에 옛 axes[i]번 축")
    chips(c, 60, 120, (0, 1, 2), "a.shape")
    chips(c, 60, 300, (1, 2, 0), "np.transpose(a, (1, 2, 0)).shape")
    for old, new in ((1, 0), (2, 1), (0, 2)):
        c.arrow(60 + old * 150 + 68, 190, 60 + new * 150 + 68, 298, color=chip_col[old], lw=1.8)
    frames.append(c.image()); ms.append(2400)
    c = Canvas(500)
    c.title("새 shape의 칸마다 옛 shape에서 가져옴")
    c.text(60, 110, "axes = (1, 2, 0)", size=22, code=True, bold=True)
    for k, ax_ in enumerate((1, 2, 0)):
        c.text(60, 175 + k * 56, "새 %d번 축 ← 옛 %d번 축 (길이 %d)" % (k, ax_, sizes[ax_]), size=21, code=True, color=chip_col[ax_])
    c.text(60, 370, "(2, 3, 4) → (3, 4, 2)", size=24, code=True, bold=True)
    frames.append(c.image()); ms.append(2200)
    c = Canvas(500)
    c.title("값은 번호 자리를 따라 옮겨 감")
    c.text(60, 120, "a[1, 2, 3]", size=24, code=True, bold=True)
    c.text(360, 120, "= 23", size=24, code=True)
    c.text(60, 200, "b = np.transpose(a, (1, 2, 0))", size=21, code=True)
    c.text(60, 270, "b[2, 3, 1]", size=24, code=True, bold=True)
    c.text(360, 270, "= 23", size=24, code=True, color=GREEN)
    c.text(60, 350, "옛 번호 (1, 2, 3)을 axes 순서 (1, 2, 0)으로 읽으면 (2, 3, 1)", size=19)
    frames.append(c.image()); ms.append(2400)
    c = Canvas(500)
    c.title("3차원 전치 정리")
    chips(c, 60, 110, (0, 1, 2), "a.shape")
    chips(c, 60, 250, (2, 1, 0), "np.transpose(a)")
    chips(c, 60, 390, (1, 2, 0), "np.transpose(a, (1, 2, 0))")
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-14", "png")
def stacking():
    B = M + 10
    v, h = np.vstack([M, B]), np.hstack([M, B])
    assert B.tolist() == [[13, 18, 11], [16, 12, 19]]
    assert v.shape == (4, 3) and h.shape == (2, 6)
    assert np.array_equal(v, np.concatenate([M, B])) and np.array_equal(h, np.concatenate([M, B], axis=1))
    c = Canvas(500)
    c.title("vstack은 위아래로, hstack은 옆으로 붙임")
    # M 과 B 는 색 대신 이름표와 굵은 이음선으로 나눔(2c 단원에서 파랑·주황은 축 번호에만 씀)
    c.text(40, 85, "M (2, 3), B = M + 10", size=19, code=True, color=MUTED)
    c.text(40, 130, "np.vstack([M, B])", size=20, code=True, bold=True)
    c.grid(40, 150, v.tolist(), cw=62, ch=48)
    c.line([40, 226], [246, 246], color=INK, lw=4, z=7)
    c.text(242, 198, "M", size=19, code=True, color=MUTED)
    c.text(242, 294, "B", size=19, code=True, color=MUTED)
    c.text(40, 370, "→ (4, 3)", size=21, code=True, color=GREEN)
    c.text(40, 410, "np.concatenate([M, B])와 같음", size=17, color=MUTED)
    c.text(40, 440, "(기본 axis=0)", size=17, color=MUTED)
    c.text(430, 130, "np.hstack([M, B])", size=20, code=True, bold=True)
    c.grid(430, 150, h.tolist(), cw=62, ch=48)
    c.line([616, 616], [150, 246], color=INK, lw=4, z=7)
    c.text(523, 268, "M", size=19, code=True, color=MUTED, ha="center")
    c.text(709, 268, "B", size=19, code=True, color=MUTED, ha="center")
    c.text(430, 310, "→ (2, 6)", size=21, code=True, color=GREEN)
    c.text(430, 350, "np.concatenate([M, B], axis=1)과 같음", size=17, color=MUTED)
    return c.image()


# ---------- 2d 브로드캐스팅과 행렬곱

@figure("l02-15", "png")
def elementwise():
    s, p, d = M + M, M * M, M - 3
    assert s.tolist() == [[6, 16, 2], [12, 4, 18]] and p.tolist() == [[9, 64, 1], [36, 4, 81]]
    assert d.tolist() == [[0, 5, -2], [3, -1, 6]]
    c = Canvas(400)
    c.title("같은 자리 원소끼리 계산")
    for k, (label, vals) in enumerate((("M + M", s), ("M * M", p), ("M - 3", d))):
        x = 50 + k * 360
        c.text(x, 100, label, size=23, code=True, bold=True)
        c.grid(x, 125, vals.tolist(), cw=70, ch=54, fill=GREEN_L)
        c.text(x, 270, "shape (2, 3)", size=19, code=True, color=MUTED)
    c.text(50, 340, "M * M은 같은 자리끼리 곱한 값(원소별 곱)", size=19)
    return c.image()


@figure("l02-16", "gif")
def broadcast_bias():
    b = np.array([10, 20, 30])
    r = M + b
    assert r.tolist() == [[13, 28, 31], [16, 22, 39]] and r.shape == (2, 3)
    frames, ms = [], []

    def base(title, ghost=False, rows_done=0):
        c = Canvas(480)
        c.title(title)
        c.text(40, 100, "M  (2, 3)", size=20, code=True, bold=True)
        c.grid(40, 120, M.tolist(), cw=70, ch=54)
        c.text(300, 174, "+", size=30, ha="center")
        c.text(360, 100, "b  (3,)", size=20, code=True, bold=True)
        c.grid(360, 120, [list(b)], cw=70, ch=54, fill=ORANGE_L)
        if ghost:
            c.grid(360, 174, [list(b)], cw=70, ch=54, fill="white", ec=ORANGE, tc=ORANGE, ls="--")
            c.text(360, 260, "복사하지 않고 같은 b를 다시 읽음", size=17, color=ORANGE)
        if rows_done:
            c.text(640, 174, "=", size=30, ha="center")
            cells = [[v if i < rows_done else "" for v in row] for i, row in enumerate(r.tolist())]
            c.grid(690, 120, cells, cw=70, ch=54, fill=lambda i, j: GREEN_L if i < rows_done else "white")
        return c

    frames.append(base("M에 b를 더하기").image()); ms.append(1800)
    c = base("오른쪽 끝 축부터 맞춰 봄")
    c.text(40, 330, "(2, 3)", size=24, code=True)
    c.text(40, 372, "   (3,)  →  (1, 3)", size=24, code=True, color=ORANGE)
    c.text(520, 330, "3 과 3: 같음", size=21, color=GREEN)
    c.text(520, 372, "2 와 1: 1 쪽이 2 로 늘어남", size=21, color=GREEN)
    frames.append(c.image()); ms.append(2400)
    frames.append(base("b가 1번 행에도 있는 것처럼 계산", ghost=True).image()); ms.append(2200)
    c = base("0번 행: [3, 8, 1] + [10, 20, 30]", ghost=True, rows_done=1)
    frames.append(c.image()); ms.append(2000)
    c = base("1번 행: [6, 2, 9] + [10, 20, 30]", ghost=True, rows_done=2)
    frames.append(c.image()); ms.append(2000)
    c = base("행마다 같은 b를 더함", rows_done=2)
    c.text(40, 300, "행 = 샘플 2개, 열 = 특징 3개", size=20)
    c.text(40, 340, "특징마다 같은 값을 모든 샘플에 더하는 계산", size=20)
    c.text(40, 400, "M + b  →  (2, 3)", size=22, code=True, color=GREEN)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-17", "gif")
def broadcast_both():
    a = np.array([1, 2, 3])
    col = np.array([[100], [200]])
    r = a + col
    assert r.tolist() == [[101, 102, 103], [201, 202, 203]] and r.shape == (2, 3)
    fix = M + np.array([100, 200]).reshape(2, 1)
    assert fix.tolist() == [[103, 108, 101], [206, 202, 209]]
    try:
        M + np.array([100, 200])
        raise AssertionError("(2,3)+(2,)")
    except ValueError:
        pass
    frames, ms = [], []

    def shapes(c, y, top, bottom, checks):
        c.text(60, y, top, size=24, code=True)
        c.text(60, y + 42, bottom, size=24, code=True)
        for k, (msg, ok) in enumerate(checks):
            c.text(520, y + k * 42, msg, size=20, color=GREEN if ok else RED)

    def operands(c, ghost=False):
        c.text(40, 90, "a  (3,)", size=20, code=True, bold=True)
        c.grid(40, 110, [list(a)], cw=70, ch=50, fill=BLUE_L)
        c.text(330, 90, "c  (2, 1)", size=20, code=True, bold=True)
        c.grid(330, 110, col.tolist(), cw=80, ch=50, fill=ORANGE_L)
        if ghost:
            c.grid(40, 160, [list(a)], cw=70, ch=50, fill="white", ec=BLUE, tc=BLUE, ls="--")
            c.grid(410, 110, col.tolist(), cw=80, ch=50, fill="white", ec=ORANGE, tc=ORANGE, ls="--")
            c.grid(490, 110, col.tolist(), cw=80, ch=50, fill="white", ec=ORANGE, tc=ORANGE, ls="--")

    c = Canvas(480)
    c.title("a + c: 모양이 서로 다른 두 배열")
    operands(c)
    frames.append(c.image()); ms.append(1800)
    c = Canvas(480)
    c.title("오른쪽 끝부터 축마다 비교")
    operands(c)
    shapes(c, 300, "   (3,) → (1, 3)", "(2, 1)", (("3 과 1: 1 쪽이 3 으로", True), ("1 과 2: 1 쪽이 2 로", True)))
    frames.append(c.image()); ms.append(2400)
    c = Canvas(480)
    c.title("두 배열이 모두 늘어나 (2, 3)")
    operands(c, ghost=True)
    frames.append(c.image()); ms.append(2200)
    c = Canvas(480)
    c.title("a + c 결과")
    operands(c)
    c.text(700, 90, "a + c  (2, 3)", size=20, code=True, bold=True)
    c.grid(700, 110, r.tolist(), cw=80, ch=50, fill=GREEN_L)
    frames.append(c.image()); ms.append(2200)
    c = Canvas(480)
    c.title("M (2, 3) + [100, 200] (2,)는 오류")
    shapes(c, 120, "(2, 3)", "   (2,)", (("3 과 2: 같지 않고 1 도 아님", False), ("ValueError", False)))
    c.text(60, 300, "행마다 다른 값을 더하려 해도 (2,)는 1번 축과 맞춰짐", size=19)
    frames.append(c.image()); ms.append(2400)
    c = Canvas(480)
    c.title("(2, 1)로 바꾸면 행마다 더해짐")
    shapes(c, 110, "(2, 3)", "(2, 1)", (("3 과 1: 1 쪽이 3 으로", True), ("2 와 2: 같음", True)))
    c.text(60, 250, "M + np.array([100, 200]).reshape(2, 1)", size=19, code=True)
    c.grid(60, 280, fix.tolist(), cw=80, ch=50, fill=GREEN_L)
    frames.append(c.image()); ms.append(2400)
    c = Canvas(480)
    c.title("브로드캐스팅 규칙")
    c.text(60, 110, "1. 오른쪽 끝 축부터 맞춰 봄", size=22)
    c.text(60, 160, "2. 축이 모자란 쪽은 왼쪽에 1 을 채움", size=22)
    c.text(60, 210, "3. 축마다 길이가 같거나 한쪽이 1 이면 됨", size=22)
    c.text(60, 290, "(2, 3) + (3,)   → (2, 3)", size=22, code=True, color=GREEN)
    c.text(60, 335, "(3,)   + (2, 1) → (2, 3)", size=22, code=True, color=GREEN)
    c.text(60, 380, "(2, 3) + (2,)   → 오류", size=22, code=True, color=RED)
    c.text(60, 425, "(3,)   + (2,)   → 오류", size=22, code=True, color=RED)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-18", "gif")
def matmul():
    Wm = np.array([[1, 0], [0, 1], [1, 1]])
    P = M @ Wm
    assert P.tolist() == [[4, 9], [15, 11]] and P.shape == (2, 2)
    assert (M @ M.T).shape == (2, 2)
    try:
        M @ M
        raise AssertionError("M@M")
    except ValueError:
        pass
    frames, ms = [], []

    def base(title, cell=None, done=()):
        c = Canvas(480)
        c.title(title)
        c.text(40, 90, "M  (2, 3)", size=20, code=True, bold=True)
        c.grid(40, 110, M.tolist(), cw=66, ch=52, fill=lambda i, j: ORANGE_L if cell and i == cell[0] else "white")
        c.text(285, 162, "@", size=28, ha="center", code=True)
        c.text(330, 90, "W  (3, 2)", size=20, code=True, bold=True)
        c.grid(330, 110, Wm.tolist(), cw=66, ch=52, fill=lambda i, j: ORANGE_L if cell and j == cell[1] else "white")
        c.text(510, 162, "=", size=28, ha="center")
        cells = [[P[i, j] if (i, j) in done else "" for j in range(2)] for i in range(2)]
        c.text(550, 90, "(2, 2)", size=20, code=True, bold=True)
        c.grid(550, 110, cells, cw=66, ch=52,
               fill=lambda i, j: GREEN_L if (i, j) == cell else (GRAY_L if (i, j) in done else "white"))
        return c

    c = base("M @ W: 안쪽 길이 3 과 3 이 같아야 곱함")
    c.text(40, 330, "(2, 3) @ (3, 2) → (2, 2)", size=23, code=True)
    c.text(40, 380, "결과의 [i, j] = M의 i번 행과 W의 j번 열을 곱해 더한 값", size=20)
    frames.append(c.image()); ms.append(2200)
    done = []
    for (i, j) in ((0, 0), (0, 1), (1, 0), (1, 1)):
        done.append((i, j))
        c = base("[%d, %d] 칸 = %d번 행 · %d번 열" % (i, j, i, j), (i, j), tuple(done))
        terms = " + ".join("%d×%d" % (M[i, k], Wm[k, j]) for k in range(3))
        c.text(40, 340, "%s = %d" % (terms, P[i, j]), size=24, code=True, color=GREEN)
        frames.append(c.image()); ms.append(2000)
    c = Canvas(480)
    c.title("* 는 원소별 곱, @ 는 행렬곱")
    c.text(40, 100, "M * M", size=22, code=True, bold=True)
    c.text(330, 100, "→ (2, 3), 같은 자리끼리 곱함", size=20, color=GREEN)
    c.text(40, 170, "M @ M", size=22, code=True, bold=True)
    c.text(330, 170, "→ 오류: (2, 3)과 (2, 3)의 안쪽 3 과 2 가 다름", size=20, color=RED)
    c.text(40, 240, "M @ M.T", size=22, code=True, bold=True)
    c.text(330, 240, "→ (2, 2): (2, 3) @ (3, 2)", size=20, color=GREEN)
    c.text(40, 320, "np.dot(M, W), np.matmul(M, W)도 2차원에서는 M @ W와 같은 행렬곱", size=19)
    frames.append(c.image()); ms.append(2500)
    c = base("M @ W 결과", None, ((0, 0), (0, 1), (1, 0), (1, 1)))
    c.text(40, 330, "M @ W = " + arr2(P), size=23, code=True, color=GREEN)
    c.text(40, 380, "(m, n) @ (n, p) → (m, p)", size=23, code=True)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


# ---------- 2e 집계와 axis

@figure("l02-19", "png")
def aggregate():
    assert int(DATA.sum()) == 29 and int(DATA.max()) == 9 and int(DATA.min()) == 1
    assert round(float(DATA.mean()), 2) == 4.83
    c = Canvas(420)
    c.title("집계는 여러 값을 숫자 하나로 줄임")
    c.text(40, 105, "data", size=22, code=True, bold=True)
    c.grid(170, 80, [list(DATA)], cw=66, ch=52)
    res = (("data.sum()", "29"), ("data.max()", "9"), ("data.min()", "1"), ("data.mean()", "약 4.83"))
    for k, (code, val) in enumerate(res):
        x = 60 + k * 265
        c.arrow(370, 136, x + 90, 200, color=LINE, lw=1.4)
        c.text(x, 230, code, size=20, code=True, bold=True)
        c.text(x, 280, val, size=26, code=True, color=GREEN)
    c.text(40, 360, "결과는 숫자 하나라 shape이 ()", size=19, color=MUTED)
    return c.image()


@figure("l02-20", "gif")
def axis_sum():
    s0, s1 = M.sum(axis=0), M.sum(axis=1)
    assert s0.tolist() == [9, 10, 10] and s1.tolist() == [12, 17] and int(M.sum()) == 29
    assert s0.shape == (3,) and s1.shape == (2,) and M.sum().shape == ()
    m0 = M.mean(axis=0)
    assert m0.tolist() == [4.5, 5.0, 5.0]
    frames, ms = [], []
    gx, gy, cw, ch = 140, 110, 76, 58

    def base(title, ax=None):
        c = Canvas(500)
        c.title(title)
        fill = {0: BLUE_L, 1: ORANGE_L}.get(ax, "white")
        c.grid(gx, gy, M.tolist(), cw=cw, ch=ch, fill=fill)
        c.text(40, gy + ch, "M", size=26, code=True, bold=True)
        c.text(gx, gy - 22, "shape (2, 3)", size=18, code=True, color=MUTED)
        return c

    c = base("M의 축 둘")
    c.arrow(gx - 30, gy, gx - 30, gy + 2 * ch, color=BLUE)
    c.text(gx - 40, gy + 2 * ch + 30, "0번 축 (2개)", size=18, color=BLUE)
    c.arrow(gx, gy + 2 * ch + 70, gx + 3 * cw, gy + 2 * ch + 70, color=ORANGE)
    c.text(gx + 3 * cw + 16, gy + 2 * ch + 70, "1번 축 (3개)", size=18, color=ORANGE)
    frames.append(c.image()); ms.append(2000)
    c = base("sum(axis=0): 위아래로 더해 0번 축이 사라짐", 0)
    for j in range(3):
        c.arrow(gx + j * cw + cw - 14, gy + 6, gx + j * cw + cw - 14, gy + 2 * ch + 40, color=BLUE, lw=2)
    c.grid(gx, gy + 2 * ch + 46, [s0.tolist()], cw=cw, ch=ch, fill=BLUE_L)
    c.text(480, 150, "M.sum(axis=0)", size=22, code=True, bold=True)
    c.text(480, 200, "→ [9, 10, 10]", size=22, code=True, color=BLUE)
    c.text(480, 250, "(2, 3) → (3,)", size=22, code=True)
    c.line([496, 512], [262, 238], color=BLUE, lw=2.5)
    frames.append(c.image()); ms.append(2400)
    c = base("sum(axis=1): 옆으로 더해 1번 축이 사라짐", 1)
    for i in range(2):
        c.arrow(gx + 6, gy + i * ch + ch - 10, gx + 3 * cw + 40, gy + i * ch + ch - 10, color=ORANGE, lw=2)
    c.grid(gx + 3 * cw + 46, gy, [[v] for v in s1.tolist()], cw=cw, ch=ch, fill=ORANGE_L)
    c.text(560, 340, "M.sum(axis=1)", size=22, code=True, bold=True)
    c.text(560, 390, "→ [12, 17]", size=22, code=True, color=ORANGE)
    c.text(560, 440, "(2, 3) → (2,)", size=22, code=True)
    c.line([621, 637], [452, 428], color=ORANGE, lw=2.5)
    frames.append(c.image()); ms.append(2400)
    c = base("axis를 주지 않으면 모든 원소를 더함")
    c.text(480, 150, "M.sum()", size=22, code=True, bold=True)
    c.text(480, 200, "→ 29", size=24, code=True, color=GREEN)
    c.text(480, 250, "(2, 3) → ()", size=22, code=True)
    c.text(660, 250, "숫자 하나", size=21)
    frames.append(c.image()); ms.append(2200)
    c = base("mean(axis=0)도 같은 방향으로 줄임", 0)
    c.grid(gx, gy + 2 * ch + 46, [[fmt(v) for v in m0]], cw=cw, ch=ch, fill=BLUE_L)
    c.text(480, 150, "M.mean(axis=0)", size=22, code=True, bold=True)
    c.text(480, 200, "→ [4.5, 5, 5]", size=22, code=True, color=BLUE)
    frames.append(c.image()); ms.append(2200)
    c = base("행이 샘플이면 axis=0 은 여러 샘플 사이의 집계")
    c.text(480, 120, "행 = 샘플(데이터 한 개)", size=20)
    c.text(480, 160, "열 = 특징", size=20)
    c.text(480, 230, "axis=0: 특징마다 여러 샘플을 모음", size=20, color=BLUE)
    c.text(480, 270, "axis=1: 샘플마다 여러 특징을 모음", size=20, color=ORANGE)
    frames.append(c.image()); ms.append(2400)
    c = Canvas(500)
    c.title("줄인 축의 숫자가 shape에서 빠짐")
    c.text(60, 110, "M.sum()        → 29          shape ()", size=22, code=True, color=GREEN)
    c.text(60, 170, "M.sum(axis=0)  → [9, 10, 10]  shape (3,)", size=22, code=True, color=BLUE)
    c.text(60, 230, "M.sum(axis=1)  → [12, 17]     shape (2,)", size=22, code=True, color=ORANGE)
    c.text(60, 320, "(2, 3)에서 axis번 자리의 숫자를 지우면 결과 shape", size=21)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


@figure("l02-21", "png")
def argmax_fig():
    assert int(M.max()) == 9 and int(M.argmax()) == 5
    assert M.max(axis=0).tolist() == [6, 8, 9] and M.max(axis=1).tolist() == [8, 9]
    c = Canvas(500)
    c.title("max는 가장 큰 값, argmax는 그 자리")
    c.grid(60, 90, M.tolist(), cw=70, ch=54, fill=lambda i, j: GREEN_L if (i, j) == (1, 2) else "white")
    c.text(60, 230, "펼친 순서", size=18, color=MUTED)
    c.grid(60, 245, [list(DATA)], cw=58, ch=48, fill=lambda i, j: GREEN_L if j == 5 else "white", note=lambda i, j: j)
    c.text(60, 330, "M.max() → 9", size=21, code=True)
    c.text(60, 370, "M.argmax() → 5", size=21, code=True, color=GREEN)
    c.text(60, 410, "펼친 1차원 순서에서 5번 자리", size=18, color=MUTED)
    c.text(560, 110, "M.max(axis=0) → [6, 8, 9]", size=21, code=True, color=BLUE)
    c.text(560, 150, "열마다 가장 큰 값", size=18, color=MUTED)
    c.text(560, 220, "M.max(axis=1) → [8, 9]", size=21, code=True, color=ORANGE)
    c.text(560, 260, "행마다 가장 큰 값", size=18, color=MUTED)
    return c.image()


@figure("l02-22", "png")
def sort_fig():
    srt = np.sort(DATA)
    arg = np.argsort(DATA)
    assert srt.tolist() == [1, 2, 3, 6, 8, 9] and arg.tolist() == [2, 4, 0, 3, 1, 5]
    d = DATA.copy()
    assert d.sort() is None and d.tolist() == srt.tolist()
    c = Canvas(540)
    c.title("np.sort는 새 배열, data.sort()는 원본을 바꿈")
    c.text(40, 100, "data", size=20, code=True, bold=True)
    c.grid(330, 75, [list(DATA)], cw=64, ch=48, note=lambda i, j: j)
    c.text(40, 175, "np.sort(data)", size=20, code=True, bold=True)
    c.grid(330, 150, [srt.tolist()], cw=64, ch=48, fill=GREEN_L)
    c.text(740, 175, "data는 바뀌지 않음", size=18, color=MUTED)
    c.text(40, 250, "np.argsort(data)", size=20, code=True, bold=True)
    c.grid(330, 225, [arg.tolist()], cw=64, ch=48, fill=BLUE_L)
    c.text(740, 250, "작은 값의 자리 번호부터", size=18, color=BLUE)
    for k in range(6):
        c.arrow(330 + arg[k] * 64 + 32, 126, 330 + k * 64 + 32, 148, color=LINE, lw=1.2)
    c.line([20, 1100], [310, 310], color=FAINT, lw=1.5)
    c.text(40, 355, "r = data.sort()", size=20, code=True, bold=True)
    c.text(430, 355, "r → None", size=20, code=True, color=RED)
    c.text(40, 410, "data", size=20, code=True, bold=True)
    c.grid(330, 386, [srt.tolist()], cw=64, ch=48, fill=GREEN_L)
    c.text(740, 410, "원본이 바뀜", size=18, color=GREEN)
    c.text(40, 480, "M.sort(axis=0)은 열마다, M.sort(axis=1)은 행마다 정렬", size=18, color=MUTED)
    return c.image()


@figure("l02-23", "gif")
def accuracy_minmax():
    yp = np.where(DATA > 5, 1, 0)
    yt = np.array([1, 1, 0, 1, 1, 0])
    eq = yt == yp
    assert yp.tolist() == [0, 1, 0, 1, 0, 1] and eq.tolist() == [False, True, True, True, False, False]
    assert int(eq.sum()) == 3 and float(eq.sum() / len(yt)) == 0.5
    mm = (DATA - DATA.min()) / (DATA.max() - DATA.min())
    assert mm.tolist() == [0.25, 0.875, 0.0, 0.625, 0.125, 1.0]
    frames, ms = [], []
    x0, cw = 320, 72

    def base(title, show_eq=False):
        c = Canvas(480)
        c.title(title)
        c.text(40, 106, "정답 yt", size=20, bold=True)
        c.grid(x0, 82, [yt.tolist()], cw=cw, ch=48)
        c.text(40, 166, "예측 yp", size=20, bold=True)
        c.grid(x0, 142, [yp.tolist()], cw=cw, ch=48)
        c.text(x0 + 6 * cw + 16, 166, "np.where(data > 5, 1, 0)", size=15, code=True, color=MUTED)
        if show_eq:
            c.text(40, 246, "yt == yp", size=20, code=True, bold=True)
            c.grid(x0, 222, [["T" if e else "F" for e in eq]], cw=cw, ch=48,
                   fill=lambda i, j: GREEN_L if eq[j] else GRAY_L, tc=lambda i, j: GREEN if eq[j] else MUTED)
        return c

    frames.append(base("정답과 예측 여섯 개").image()); ms.append(1800)
    frames.append(base("yt == yp: 자리마다 같은지", True).image()); ms.append(2200)
    c = base("(yt == yp).sum(): 맞은 개수", True)
    c.text(40, 330, "(yt == yp).sum()", size=21, code=True)
    c.text(420, 330, "→ 3", size=24, code=True, color=GREEN)
    frames.append(c.image()); ms.append(2000)
    c = base("맞은 개수 ÷ 전체 개수", True)
    c.text(40, 330, "(yt == yp).sum() / len(yt)", size=21, code=True)
    c.text(520, 330, "→ 3 / 6 = 0.5", size=24, code=True, color=GREEN)
    frames.append(c.image()); ms.append(2200)

    def scale(title, show_vals):
        c = Canvas(480)
        c.title(title)
        lx0, lx1 = 140, 1000
        c.text(40, 120, "data", size=20, code=True, bold=True)
        c.line([lx0, lx1], [120, 120], color=LINE)
        c.line([lx0, lx1], [300, 300], color=LINE)
        c.text(40, 300, "결과", size=20, bold=True)
        for v in range(1, 10):
            c.text(lx0 + (v - 1) / 8 * (lx1 - lx0), 92, str(v), size=15, ha="center", color=MUTED, code=True)
        for t in (0, 0.5, 1):
            c.text(lx0 + t * (lx1 - lx0), 336, fmt(t), size=16, ha="center", color=MUTED, code=True)
        for v, m in zip(DATA, mm):
            x1 = lx0 + (v - 1) / 8 * (lx1 - lx0)
            x2 = lx0 + m * (lx1 - lx0)
            c.ax.scatter([x1], [120], s=140, color=BLUE, zorder=5)
            c.ax.scatter([x2], [300], s=140, color=GREEN, zorder=5)
            c.arrow(x1, 132, x2, 288, color=LINE, lw=1.3)
            if show_vals:
                c.text(x2, 270, fmt(m), size=15, ha="center", code=True, color=GREEN, bg="white")
        c.text(40, 400, "(data - data.min()) / (data.max() - data.min())", size=19, code=True)
        c.text(40, 440, "가장 작은 1 은 0, 가장 큰 9 는 1 로", size=19)
        return c

    frames.append(scale("min-max: 가장 작은 값을 0, 가장 큰 값을 1 로", False).image()); ms.append(2200)
    frames.append(scale("min-max 결과: 빼고 나눠 0 과 1 사이로", True).image()); ms.append(2400)
    c = Canvas(480)
    c.title("배열 한 줄로 정확도와 min-max")
    c.text(40, 110, "정확도 = (yt == yp).sum() / len(yt) = 0.5", size=21, code=True)
    c.text(40, 180, "min-max(data) = " + arr1(mm), size=21, code=True)
    c.text(40, 260, "표준화 (data - data.mean()) / data.std()는 평균 0, 표준편차 1", size=19, color=MUTED)
    frames.append(c.image()); ms.append(2500)
    return frames, ms


# ---------- 2f Matplotlib

def mpl_panel(fig, rect, title):
    ax = fig.add_axes(rect)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_title(title, loc="left", fontsize=17, family=CODE, pad=8)
    ax.tick_params(labelsize=13)
    return ax


@figure("l02-24", "png")
def plot_scatter():
    x = np.arange(6)
    xp = np.linspace(-3, 3, 61)
    assert round(float(xp[1] - xp[0]), 6) == 0.1
    sig = lambda t, a: 1 / (1 + np.exp(-a * t))
    assert sig(0.0, 1) == 0.5
    fig = plt.figure(figsize=(W / 100, 4.4), dpi=100)
    a1 = mpl_panel(fig, [0.05, 0.14, 0.26, 0.7], "plt.plot(x, data)")
    a1.plot(x, DATA, color=BLUE, lw=2.5, marker="o")
    a2 = mpl_panel(fig, [0.38, 0.14, 0.26, 0.7], "plt.scatter(x, data)")
    a2.scatter(x, DATA, color=BLUE, s=60)
    for ax in (a1, a2):
        ax.set_xticks(range(6)); ax.set_ylim(0, 10)
    a3 = mpl_panel(fig, [0.71, 0.14, 0.27, 0.7], "sigmoid(x, a)")
    a3.plot(xp, sig(xp, 1.0), color=INK, lw=2.5)
    a3.plot(xp, sig(xp, 2.0), color=ORANGE, lw=2.5)
    a3.text(1.0, 0.42, "a = 1", fontsize=15, color=INK)
    a3.text(-2.9, 0.86, "a = 2", fontsize=15, color=ORANGE)
    a3.set_ylim(-0.05, 1.05)
    fig.text(0.05, 0.94, "선 그래프와 산점도, 그리고 a에 따라 달라지는 시그모이드", fontsize=19, weight="bold")
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(buf[..., :3].copy())
    plt.close(fig)
    return img


TRAIN = [0.90, 0.62, 0.45, 0.36, 0.30, 0.26, 0.23]   # 그림을 보이려고 만든 값
VAL = [0.95, 0.70, 0.57, 0.53, 0.55, 0.60, 0.66]


@figure("l02-25", "png")
def anatomy():
    ep = np.arange(1, 8)
    best = int(np.argmin(VAL)) + 1
    assert best == 4 and TRAIN[-1] < TRAIN[best - 1]
    fig = plt.figure(figsize=(W / 100, 5.4), dpi=100)
    ax = fig.add_axes([0.08, 0.13, 0.52, 0.72])
    ax.plot(ep, TRAIN, "b-", lw=2.5, label="Train")
    ax.plot(ep, VAL, "r--", lw=2.5, label="Val")
    ax.set_title("Loss Curve", fontsize=17)
    ax.set_xlabel("Epoch", fontsize=15)
    ax.set_ylabel("Loss", fontsize=15)
    ax.legend(fontsize=14)
    ax.grid(True)
    ax.set_ylim(0, 1.0)
    ax.tick_params(labelsize=13)
    ax.axvline(best, color=MUTED, lw=1.2, ls=":")
    notes = (("plt.title(...)", 0.80, BLUE), ("plt.xlabel(...)", 0.70, BLUE), ("plt.ylabel(...)", 0.60, BLUE),
             ("plt.legend()", 0.50, BLUE), ("plt.grid(True)", 0.40, BLUE), ("'b-' 파란 실선", 0.30, BLUE),
             ("'r--' 빨간 점선", 0.20, RED))
    for s, y, col in notes:
        fig.text(0.65, y, s, fontsize=16, family=CODE, color=col)
    fig.text(0.65, 0.12, "Epoch 4 뒤: Val은 오르고", fontsize=14, color=INK)
    fig.text(0.65, 0.07, "Train은 계속 내려감", fontsize=14, color=INK)
    fig.text(0.65, 0.02, "그림을 보이려고 만든 값", fontsize=13, color=MUTED)
    fig.text(0.08, 0.93, "그래프에 붙이는 제목, 가로축·세로축 이름, 범례, 격자", fontsize=19, weight="bold")
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(buf[..., :3].copy())
    plt.close(fig)
    return img


@figure("l02-26", "png")
def scatter_patterns():
    rng = np.random.default_rng(7)
    fig = plt.figure(figsize=(W / 100, 5.6), dpi=100)
    fig.text(0.04, 0.94, "산점도로 보는 네 가지", fontsize=19, weight="bold")
    boxes = ([0.05, 0.10, 0.2, 0.68], [0.29, 0.10, 0.2, 0.68], [0.53, 0.10, 0.2, 0.68], [0.77, 0.10, 0.2, 0.68])
    titles = ("상관관계", "군집", "이상치", "분리 가능성")
    axs = []
    for r, t in zip(boxes, titles):
        ax = fig.add_axes(r)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(t, fontsize=17, pad=8)
        axs.append(ax)
    x = rng.uniform(0, 10, 40)
    axs[0].scatter(x, 0.8 * x + rng.normal(0, 1.0, 40), s=22, color=BLUE)
    for cx, cy in ((2, 2), (7, 3), (4, 8)):
        axs[1].scatter(cx + rng.normal(0, 0.7, 15), cy + rng.normal(0, 0.7, 15), s=22, color=BLUE)
    xo = rng.uniform(0, 10, 30)
    axs[2].scatter(xo, 0.5 * xo + rng.normal(0, 0.6, 30), s=22, color=BLUE)
    axs[2].scatter([8.5], [0.2], s=70, color=RED)
    pa = rng.normal(0, 1, (20, 2)) + [2.5, 6.5]
    pb = rng.normal(0, 1, (20, 2)) + [6.5, 2.5]
    axs[3].scatter(pa[:, 0], pa[:, 1], s=22, color=BLUE)
    axs[3].scatter(pb[:, 0], pb[:, 1], s=22, color=ORANGE, marker="s")
    axs[3].plot([0, 9], [0, 9], color=INK, ls="--", lw=1.5)
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(buf[..., :3].copy())
    plt.close(fig)
    return img


@figure("l02-27", "png")
def random_ranges():
    c = Canvas(520)
    c.title("numpy 난수 함수가 내는 값의 범위")
    lx0, lx1 = 430, 1060
    c.text(40, 110, "np.random.rand()", size=20, code=True, bold=True)
    c.line([lx0, lx1], [110, 110], color=BLUE, lw=6)
    c.ax.scatter([lx0], [110], s=170, color=BLUE, zorder=5)
    c.ax.scatter([lx1], [110], s=170, facecolor="white", edgecolor=RED, lw=2.5, zorder=5)
    c.text(lx0, 146, "0 포함", size=16, ha="center", color=BLUE)
    c.text(lx1, 146, "1 빠짐", size=16, ha="center", color=RED)
    c.text(40, 220, "np.random.randint(1, 10)", size=20, code=True, bold=True)
    for v in range(1, 11):
        x = lx0 + (v - 1) / 9 * (lx1 - lx0)
        if v < 10:
            c.ax.scatter([x], [220], s=150, color=BLUE, zorder=5)
        else:
            c.ax.scatter([x], [220], s=170, facecolor="white", edgecolor=RED, lw=2.5, zorder=5)
        c.text(x, 256, str(v), size=16, ha="center", code=True, color=RED if v == 10 else INK)
    c.text(40, 300, "1 이상 10 미만 정수", size=17, color=MUTED)
    c.text(40, 380, "np.random.randn()", size=20, code=True, bold=True)
    xs = np.linspace(-3, 3, 121)
    ys = np.exp(-xs ** 2 / 2)
    px = lx0 + (xs + 3) / 6 * (lx1 - lx0)
    py = 480 - ys * 120
    c.line(px, py, color=BLUE, lw=2.5)
    for v in (-1, 0, 1):
        x = lx0 + (v + 3) / 6 * (lx1 - lx0)
        c.line([x, x], [480, 480 - np.exp(-v ** 2 / 2) * 120], color=MUTED, lw=1.2, ls="--")
        c.text(x, 500, str(v), size=15, ha="center", code=True, color=MUTED)
    c.text(40, 420, "평균 0, 표준편차 1 인 정규분포", size=17, color=MUTED)
    return c.image()


# ---------- 외울 것 그림(GIF 마지막 장을 PNG로)

LAST_FRAME = {"l02-28": "l02-7", "l02-29": "l02-10", "l02-30": "l02-17", "l02-31": "l02-20"}


def build(names, out):
    os.makedirs(out, exist_ok=True)
    made = {}
    want = set(names) if names else None
    gif_frames = {}
    for name, kind, fn in FIGS:
        need = want is None or name in want or any(src == name and (want is None or k in want) for k, src in LAST_FRAME.items())
        if not need:
            continue
        path = os.path.join(out, "%s.%s" % (name, kind))
        if kind == "gif":
            frames, ms = fn()
            gif_frames[name] = frames
            if want is None or name in want:
                save_gif(path, frames, ms)
                made[name] = path
        else:
            save_png(path, fn())
            made[name] = path
    for name, src in LAST_FRAME.items():
        if want is None or name in want:
            path = os.path.join(out, name + ".png")
            save_png(path, gif_frames[src][-1])
            made[name] = path
    for name, path in sorted(made.items(), key=lambda kv: int(kv[0].split("-")[1])):
        img = Image.open(path)
        frames = getattr(img, "n_frames", 1)
        size = os.path.getsize(path)
        limit = 250_000 if path.endswith(".gif") else 150_000
        assert size <= limit, (name, size)
        assert img.size[0] <= W and img.size[1] <= MAX_H, (name, img.size)
        print("%-7s %4dx%-4d 장 %2d  %6.1fKB" % (name, img.size[0], img.size[1], frames, size / 1000))
    return made


def main(argv):
    out = OUT
    names = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--out":
            out = args.pop(0)
        else:
            names.append(a)
    known = {n for n, _, _ in FIGS} | set(LAST_FRAME)
    bad = [n for n in names if n not in known]
    if bad:
        print("모르는 그림 이름:", " ".join(bad))
        return 2
    build(names, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
