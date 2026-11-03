# -*- coding: utf-8 -*-
"""1차시 학습 노트 그림(ai/learn/l01/assets). matplotlib(Agg)과 Pillow 로 그림.

출제자 컴퓨터에서만 돌림. 창을 띄우지 않고 파일만 씀. 그림에 찍는 숫자는 여기서 다시 계산하고 assert 로 확인함.
  python tools/ai_art/l01.py            전부 그림
  python tools/ai_art/l01.py 1a-2 1d-3  고른 것만 그림
한도(설계 7.4): 파일 폭 1120px, 높이 600px 이하, GIF 250KB·10장·장 1600~2500ms·64색, PNG 150KB.
"""
import math
import os
import sys
from decimal import Decimal
from fractions import Fraction

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "ai", "learn", "l01", "assets")
FONTS = os.path.join(ROOT, "gui", "fonts")
for name in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf", "D2Coding-Regular.ttf", "D2Coding-Bold.ttf"):
    font_manager.fontManager.addfont(os.path.join(FONTS, name))
plt.rcParams.update({
    "font.family": ["NanumGothic", "DejaVu Sans"], "axes.unicode_minus": False, "font.size": 22,
    "axes.titlesize": 24, "axes.labelsize": 22, "xtick.labelsize": 20, "ytick.labelsize": 20,
    "axes.edgecolor": "#9ca3af", "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "mathtext.fontset": "dejavusans",
})

INK, MUTED, FAINT, GRID = "#1f2937", "#6b7280", "#d1d5db", "#eef0f3"
BLUE, RED, ORANGE, GREEN, PURPLE = "#2563eb", "#dc2626", "#ea580c", "#059669", "#7c3aed"
BLUE_L, RED_L, ORANGE_L, GREEN_L, GRAY_L, HL = "#dbeafe", "#fee2e2", "#ffedd5", "#d1fae5", "#f3f4f6", "#fef3c7"
CODE = ["D2Coding", "DejaVu Sans Mono"]
M = "−"  # 빼기표
WIDTH = 1120
MAX_H = 600
KB = 1024
FIGS = {}


def figure(name):
    def wrap(fn):
        FIGS[name] = fn
        return fn
    return wrap


def sign(text):
    """화면에 보일 숫자 글. 빼기는 빼기표로."""
    return str(text).replace("-", M)


def dec(value, places=None):
    """Fraction·float 을 짧은 소수 글로."""
    if places is not None:
        value = round(float(value), places)
    d = Decimal(str(float(value))) if not isinstance(value, Fraction) else Decimal(value.numerator) / Decimal(value.denominator)
    out = format(d.normalize(), "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return sign("0" if out == "-0" else out)


# 그리기 도우미. 캔버스는 가로 112칸(칸 하나 10px), 세로 h칸

def canvas(h):
    assert h * 10 <= MAX_H
    fig = plt.figure(figsize=(WIDTH / 100, h / 10), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 112)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text="", fc="white", ec=INK, size=22, color=INK, lw=2.0, weight="normal", family=None, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=ec, lw=lw, ls=ls, zorder=2))
    if text:
        kw = {"family": family} if family else {}
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=color, weight=weight, zorder=3, **kw)


def label(ax, x, y, text, size=22, color=INK, ha="left", va="center", weight="normal", family=None, bg=None):
    kw = {"family": family} if family else {}
    if bg:
        kw["bbox"] = {"boxstyle": "round,pad=0.25", "fc": bg, "ec": bg}
    return ax.text(x, y, text, ha=ha, va=va, fontsize=size, color=color, weight=weight, zorder=4, **kw)


def arrow(ax, x1, y1, x2, y2, color=INK, lw=2.5, style="-|>", rad=0.0, ms=22):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=ms, color=color, lw=lw,
                                 connectionstyle="arc3,rad=%s" % rad, zorder=3))


def title(ax, text, h, size=24):
    label(ax, 3, h - 3.2, text, size=size, weight="bold")


def tidy(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(True, color=GRID, lw=1.0)
    ax.set_axisbelow(True)


def to_image(fig):
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(buf[..., :3].copy())
    plt.close(fig)
    assert img.size[0] == WIDTH and img.size[1] <= MAX_H, img.size
    return img


def save_gif(name, frames, durations):
    assert 2 <= len(frames) <= 10 and len(frames) == len(durations), name
    assert all(1600 <= d <= 2500 for d in durations), name
    w, h = frames[0].size
    sheet = Image.new("RGB", (w, h * len(frames)), "white")
    for k, f in enumerate(frames):
        assert f.size == (w, h)
        sheet.paste(f, (0, h * k))
    pal = sheet.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    path = os.path.join(OUT, name + ".gif")
    q[0].save(path, save_all=True, append_images=q[1:], duration=durations, loop=0, optimize=False, disposal=1)
    size = os.path.getsize(path)
    assert size <= 250 * KB, (name, size)
    with Image.open(path) as check:
        assert check.n_frames == len(frames), (name, check.n_frames)
    return path, size


def save_png(name, img):
    q = img.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    path = os.path.join(OUT, name + ".png")
    q.save(path, optimize=True)
    size = os.path.getsize(path)
    assert size <= 150 * KB, (name, size)
    return path, size


# 1a 학습 한 바퀴: x = 2, w = 2, 정답 5, 손실 = (예측 − 정답)^2, 학습률 0.1

X1A, T1A, LR1A = 2, 5, Fraction(1, 10)


def rounds(n):
    w, out = Fraction(2), []
    for _ in range(n):
        pred = w * X1A
        loss = (pred - T1A) ** 2
        grad = 2 * (pred - T1A) * X1A
        new = w - LR1A * grad
        out.append((w, pred, loss, grad, new))
        w = new
    return out


R1A = rounds(3)
assert [dec(r[0]) for r in R1A] == ["2", "2.4", "2.48"]
assert [dec(r[1]) for r in R1A] == ["4", "4.8", "4.96"]
assert [dec(r[2]) for r in R1A] == ["1", "0.04", "0.0016"]
assert [dec(r[3]) for r in R1A] == [M + "4", M + "0.8", M + "0.16"]
assert dec(R1A[1][4]) == "2.48"


@figure("1a-1")
def loss_png():
    fig, ax = canvas(36)
    title(ax, "순전파로 예측을 내고 정답과 비교해 손실을 잽니다", 36)
    pred = 2 * X1A
    loss = (pred - T1A) ** 2
    assert (pred, loss) == (4, 1)
    for x, w, name, val, fc in ((3, 13, "입력", "x = 2", GRAY_L), (21, 17, "파라미터", "× w(= 2)", GRAY_L), (43, 11, "예측", "4", BLUE_L)):
        label(ax, x + w / 2, 25, name, size=20, color=MUTED, ha="center")
        box(ax, x, 15, w, 7, val, fc=fc, ec=BLUE if name == "예측" else INK, size=24)
    arrow(ax, 16.4, 18.5, 20.6, 18.5)
    arrow(ax, 38.4, 18.5, 42.6, 18.5)
    label(ax, 3, 8, "순전파: 2 × 2 = 4", size=22, color=BLUE)
    # 수직선
    x0, x1 = 62, 108
    def at(v):
        return x0 + (x1 - x0) * v / 6
    ax.plot([x0, x1], [14, 14], color=INK, lw=2)
    for v in range(7):
        ax.plot([at(v), at(v)], [13.3, 14.7], color=INK, lw=2)
        label(ax, at(v), 11.3, str(v), size=20, color=MUTED, ha="center")
    ax.add_patch(Circle((at(4), 14), 0.9, color=BLUE, zorder=5))
    ax.add_patch(Circle((at(5), 14), 0.9, color=INK, zorder=5))
    label(ax, at(4) - 0.6, 18, "예측 4", size=22, color=BLUE, ha="right")
    label(ax, at(5) + 0.6, 18, "정답 5", size=22, color=INK, ha="left")
    ax.annotate("", xy=(at(5), 22), xytext=(at(4), 22), arrowprops={"arrowstyle": "<->", "color": RED, "lw": 2.5})
    label(ax, (at(4) + at(5)) / 2, 24.5, "차이 1", size=22, color=RED, ha="center")
    label(ax, 62, 5, "손실 = $(4 - 5)^2$ = 1", size=24, color=RED, weight="bold")
    return save_png("1a-1", to_image(fig))


RING = {"순전파": (30, 40), "손실 계산": (50, 24), "역전파": (30, 8), "갱신": (10, 24)}
RING_COLOR = {"순전파": BLUE, "손실 계산": RED, "역전파": ORANGE, "갱신": GREEN}
RING_FILL = {"순전파": BLUE_L, "손실 계산": RED_L, "역전파": ORANGE_L, "갱신": GREEN_L}


def ring(ax, on=None):
    order = ["순전파", "손실 계산", "역전파", "갱신"]
    for name in order:
        x, y = RING[name]
        lit = name == on
        box(ax, x - 9, y - 3.5, 18, 7, name, fc=RING_FILL[name] if lit else "white",
            ec=RING_COLOR[name] if lit else FAINT, lw=3.5 if lit else 2, size=22,
            color=RING_COLOR[name] if lit else MUTED, weight="bold" if lit else "normal")
    arrow(ax, 39.5, 39, 48, 28, color=MUTED, rad=-0.25)
    arrow(ax, 48, 20, 39.5, 9, color=MUTED, rad=-0.25)
    arrow(ax, 20.5, 9, 12, 20, color=MUTED, rad=-0.25)
    arrow(ax, 12, 28, 20.5, 39, color=MUTED, rad=-0.25)


def panel(ax, lines, top=44):
    box(ax, 64, 4, 45, top - 4, fc=GRAY_L, ec=FAINT)
    y = top - 5
    for text, color in lines:
        label(ax, 67, y, text, size=22, color=color)
        y -= 6


@figure("1a-2")
def cycle_gif():
    frames, durs = [], []
    r1, r2, r3 = R1A
    steps = [
        (None, [("시작: w = 2", INK), ("입력 x = 2, 정답 5", MUTED), ("학습률 0.1", MUTED)], 2200),
        ("순전파", [("w = 2", INK), ("예측 = 2 × 2 = %s" % dec(r1[1]), BLUE)], 2000),
        ("손실 계산", [("w = 2", INK), ("예측 4", BLUE), ("손실 = $(4 - 5)^2$ = %s" % dec(r1[2]), RED)], 2000),
        ("역전파", [("w = 2", INK), ("예측 4, 손실 1", MUTED), ("w의 기울기 = %s" % dec(r1[3]), ORANGE)], 2200),
        ("갱신", [("w = 2 %s 0.1 × (%s)" % (M, dec(r1[3])), GREEN), ("   = %s" % dec(r1[4]), GREEN), ("기울기가 음수라 w가 커집니다", MUTED)], 2400),
        (None, [("둘째 바퀴", INK), ("예측 %s, 손실 %s" % (dec(r2[1]), dec(r2[2])), BLUE), ("기울기 %s" % dec(r2[3]), ORANGE), ("새 w = %s" % dec(r2[4]), GREEN)], 2400),
    ]
    for on, lines, ms in steps:
        fig, ax = canvas(50)
        title(ax, "학습 한 바퀴", 50)
        ring(ax, on)
        panel(ax, lines)
        frames.append(to_image(fig))
        durs.append(ms)
    fig, ax = canvas(50)
    title(ax, "학습 한 바퀴를 세 번", 50)
    ring(ax)
    box(ax, 64, 4, 45, 40, fc=GRAY_L, ec=FAINT)
    label(ax, 67, 39, "바퀴    w       손실", size=22, color=MUTED, family=CODE)
    for k, r in enumerate(R1A):
        label(ax, 67, 32 - 7 * k, "%d       %-7s %s" % (k + 1, dec(r[0]), dec(r[2])), size=24, family=CODE)
    label(ax, 67, 9, "손실이 1 → 0.04 → 0.0016", size=22, color=RED)
    frames.append(to_image(fig))
    durs.append(2500)
    frames[-1].save(os.path.join(OUT, "_1a-5.tmp.png"))
    out = save_gif("1a-2", frames, durs)
    img = Image.open(os.path.join(OUT, "_1a-5.tmp.png")).convert("RGB")
    os.remove(os.path.join(OUT, "_1a-5.tmp.png"))
    save_png("1a-5", img)
    return out


def lr_path(lr, n):
    ws = [Fraction(2)]
    for _ in range(n):
        ws.append(ws[-1] - lr * (8 * ws[-1] - 20))
    return ws


def L(w):
    return (2 * w - 5) ** 2


LRS = (Fraction(1, 100), Fraction(1, 10), Fraction(3, 10))
PATHS = [lr_path(lr, 4) for lr in LRS]
assert [dec(w, 2) for w in PATHS[0]] == ["2", "2.04", "2.08", "2.11", "2.14"]
assert [dec(w) for w in PATHS[1]] == ["2", "2.4", "2.48", "2.496", "2.4992"]
assert [dec(w, 2) for w in PATHS[2]] == ["2", "3.2", "1.52", "3.87", "0.58"]
assert [dec(L(w), 2) for w in PATHS[2]] == ["1", "1.96", "3.84", "7.53", "14.76"]
assert dec(L(PATHS[0][4]), 2) == "0.51"


@figure("1a-3")
def lr_gif():
    frames, durs = [], []
    ws = np.linspace(0, 4.4, 200)
    texts = ["시작: 세 칸 모두 w = 2, 손실 1", "1번 갱신", "2번 갱신", "3번 갱신", "4번 갱신"]
    for k in range(6):
        fig = plt.figure(figsize=(11.2, 5.2), dpi=100)
        upto = min(k, 4)
        fig.text(0.015, 0.94, texts[k] if k < 5 else "네 번 갱신한 뒤", fontsize=24, weight="bold", color=INK)
        for p, (lr, path) in enumerate(zip(LRS, PATHS)):
            ax = fig.add_axes([0.06 + p * 0.325, 0.22, 0.27, 0.6])
            tidy(ax)
            ax.plot(ws, (2 * ws - 5) ** 2, color=MUTED, lw=2)
            ax.set_xlim(0, 4.4)
            ax.set_ylim(-0.8, 16)
            ax.set_xticks([0, 1, 2, 2.5, 4])
            ax.set_xticklabels(["0", "1", "2", "", "4"])
            ax.set_yticks([0, 5, 10, 15])
            ax.set_title("학습률 %s" % dec(lr), fontsize=22, color=[BLUE, GREEN, RED][p], pad=6)
            ax.axvline(2.5, color=FAINT, lw=1.5, ls="--")
            xs = [float(w) for w in path[:upto + 1]]
            ys = [float(L(w)) for w in path[:upto + 1]]
            col = [BLUE, GREEN, RED][p]
            ax.plot(xs, ys, color=col, lw=2, marker="o", ms=9, zorder=4)
            ax.plot(xs[-1:], ys[-1:], marker="o", ms=14, color=col, zorder=5)
            w_now = path[upto]
            loss_now = L(w_now)
            loss_txt = "0.0001 미만" if loss_now < Fraction(1, 10000) else dec(loss_now, 4 if p == 1 else 2)
            ax.set_xlabel("w = %s,  손실 %s" % (dec(w_now, 4 if p == 1 else 2), loss_txt), fontsize=20, color=col)
            if k == 5:
                ax.text(2.2, 12.5, ["느림", "최적점에 닿음", "발산"][p], fontsize=24, color=col, weight="bold", ha="center",
                        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": col})
        frames.append(to_image(fig))
        durs.append(2500 if k == 5 else 2400 if k == 4 else 2200)
    return save_gif("1a-3", frames, durs)


@figure("1a-4")
def traits_png():
    fig, ax = canvas(40)
    title(ax, "학습의 세 특징", 40)
    label(ax, 3, 31.5, "점진적 개선", size=22, color=BLUE, weight="bold")
    vals = [float(r[2]) for r in R1A]
    for k, v in enumerate(vals):
        hgt = max(0.4, 18 * v)
        ax.add_patch(Rectangle((5 + 10 * k, 6), 6, hgt, color=BLUE, zorder=2))
        label(ax, 8 + 10 * k, 6 + hgt + 1.6, dec(R1A[k][2]), size=19, ha="center", color=INK)
        label(ax, 8 + 10 * k, 3.5, "%d바퀴" % (k + 1), size=17, ha="center", color=MUTED)
    label(ax, 39, 31.5, "자동화", size=22, color=GREEN, weight="bold")
    box(ax, 39, 17, 34, 9, "사람이 정하는 것\n모델, 손실, 학습률", fc=GRAY_L, ec=FAINT, size=18)
    box(ax, 39, 5, 34, 9, "컴퓨터가 하는 것\n기울기 계산, 갱신", fc=GREEN_L, ec=GREEN, size=18, color=GREEN)
    label(ax, 77, 31.5, "일반화", size=22, color=PURPLE, weight="bold")
    box(ax, 77, 17, 32, 9, "학습에 쓴 데이터\n손실을 줄이며 학습", fc=GRAY_L, ec=FAINT, size=18)
    box(ax, 77, 5, 32, 9, "처음 보는 데이터\n잘 맞히는지 따로 확인", fc="white", ec=PURPLE, size=18, color=PURPLE)
    return save_png("1a-4", to_image(fig))


# 1b PyTorch 다섯 줄

@figure("1b-1")
def roles_png():
    fig, ax = canvas(40)
    title(ax, "누가 무엇을 맡나", 40)
    box(ax, 3, 3, 40, 29, fc=GRAY_L, ec=FAINT)
    label(ax, 6, 28, "사람이 정하는 것", size=22, weight="bold")
    for k, t in enumerate(["모델 구조(층을 몇 개, 어떻게)", "손실 함수 고르기", "학습률"]):
        label(ax, 7, 22 - 6 * k, "· " + t, size=20)
    box(ax, 48, 3, 61, 29, fc=BLUE_L, ec=BLUE)
    label(ax, 51, 28, "PyTorch가 맡는 것", size=22, weight="bold", color=BLUE)
    for k, t in enumerate(["자동 미분(Autograd): 기울기 계산", "손실 함수와 옵티마이저 모듈",
                           "텐서 연산(numpy와 비슷한 문법)", "GPU 가속"]):
        label(ax, 52, 22 - 5.2 * k, "· " + t, size=20)
    return save_png("1b-1", to_image(fig))


CODE5 = ["optimizer.zero_grad()", "output = model(input)", "loss = fn(output, target)", "loss.backward()", "optimizer.step()"]


def five_lines(ax, on, h=50):
    box(ax, 3, 4, 54, h - 12, fc="#253747", ec="#253747")
    for k, line in enumerate(CODE5):
        y = h - 13 - 7 * k
        if k == on:
            ax.add_patch(Rectangle((4, y - 3), 52, 6, color="#3d6187", zorder=2.5))
        label(ax, 6, y, "%d  %s" % (k + 1, line), size=21, family=CODE, color="#e0e8f0" if k == on else "#9fb2c4")


def cells(ax, vals, lit, h=50):
    names = ["w", "w의 기울기", "예측", "손실"]
    colors = [GREEN, ORANGE, BLUE, RED]
    for k, (n, v) in enumerate(zip(names, vals)):
        y = h - 16 - 8.5 * k
        label(ax, 62, y, n, size=21, color=MUTED)
        box(ax, 82, y - 3, 26, 6, v, fc=HL if n in lit else "white", ec=colors[k] if n in lit else FAINT,
            size=22, color=colors[k] if v not in ("", "비어 있음") else MUTED, lw=3 if n in lit else 2)


@figure("1b-2")
def five_gif():
    r1, r2 = R1A[0], R1A[1]
    states = [
        (None, ["2", "비어 있음", "", ""], [], 2200),
        (0, ["2", "비어 있음", "", ""], ["w의 기울기"], 1800),
        (1, ["2", "비어 있음", dec(r1[1]), ""], ["예측"], 1800),
        (2, ["2", "비어 있음", dec(r1[1]), dec(r1[2])], ["손실"], 1800),
        (3, ["2", dec(r1[3]), dec(r1[1]), dec(r1[2])], ["w의 기울기"], 2200),
        (4, [dec(r1[4]), dec(r1[3]), dec(r1[1]), dec(r1[2])], ["w"], 2200),
    ]
    frames, durs = [], []
    for on, vals, lit, ms in states:
        fig, ax = canvas(50)
        title(ax, "다섯 줄을 한 줄씩 실행하기 (x = 2, 정답 5, 학습률 0.1)", 50, size=22)
        five_lines(ax, on)
        cells(ax, vals, lit)
        frames.append(to_image(fig))
        durs.append(ms)
    frames[-1].copy().save(os.path.join(OUT, "_1b-5.tmp.png"))
    fig, ax = canvas(50)
    title(ax, "다음 바퀴도 같은 다섯 줄", 50, size=22)
    five_lines(ax, None)
    cells(ax, [dec(r2[4]), dec(r2[3]), dec(r2[1]), dec(r2[2])], ["예측", "손실"])
    frames.append(to_image(fig))
    durs.append(2500)
    out = save_gif("1b-2", frames, durs)
    img = Image.open(os.path.join(OUT, "_1b-5.tmp.png")).convert("RGB")
    os.remove(os.path.join(OUT, "_1b-5.tmp.png"))
    save_png("1b-5", img)
    return out


@figure("1b-3")
def train_eval_png():
    fig, ax = canvas(40)
    title(ax, "학습할 때와 평가할 때", 40)
    label(ax, 3, 28, "학습", size=22, weight="bold", color=GREEN)
    names = ["zero_grad", "model", "fn", "backward", "step"]
    for k, n in enumerate(names):
        box(ax, 14 + 19 * k, 24.5, 16, 7, n, fc=GREEN_L if k in (3, 4) else GRAY_L, ec=GREEN if k in (3, 4) else FAINT,
            size=20, family=CODE)
        if k:
            arrow(ax, 14 + 19 * k - 3, 28, 14 + 19 * k - 0.4, 28, lw=2)
    label(ax, 14, 21, "기울기 기록을 켜 두고 다섯 줄을 모두 실행", size=18, color=MUTED)
    label(ax, 3, 11, "평가", size=22, weight="bold", color=BLUE)
    box(ax, 13, 4, 55, 13, fc=BLUE_L, ec=BLUE, ls="--")
    label(ax, 15, 14.5, "with torch.no_grad():", size=19, family=CODE, color=BLUE)
    box(ax, 17, 5.5, 18, 6, "model", fc="white", ec=FAINT, size=20, family=CODE)
    arrow(ax, 35.5, 8.5, 39, 8.5, lw=2)
    box(ax, 39.5, 5.5, 26, 6, "정확도 계산", fc="white", ec=FAINT, size=20)
    for k, n in enumerate(["backward", "step"]):
        box(ax, 73 + 18 * k, 7, 15, 6, n, fc="white", ec=FAINT, size=19, family=CODE, color=FAINT)
        ax.plot([73 + 18 * k, 88 + 18 * k], [7, 13], color=RED, lw=2.5, zorder=4)
    label(ax, 73, 3, "평가에서는 부르지 않는 줄", size=18, color=RED)
    return save_png("1b-3", to_image(fig))


@figure("1b-4")
def dev_order_png():
    fig, ax = canvas(46)
    title(ax, "딥러닝 개발 순서 아홉 단계와 노트북 01", 46)
    steps = ["문제 정의", "데이터 수집", "전처리", "모델 설계", "학습", "평가", "개선", "배포", "모니터링"]
    notes = {"데이터 수집": "이미지 폴더\n받기", "전처리": "크기와 값\n맞추기", "모델 설계": "마지막 층\n바꾸기",
             "학습": "fit 의\n다섯 줄", "평가": "fit 의\n평가 부분"}
    assert len(steps) == 9
    for k, s in enumerate(steps):
        row, col = divmod(k, 5)
        x = 3 + col * 22 if row == 0 else 3 + (col + 0.5) * 22
        y = 30 if row == 0 else 9
        lit = s in notes
        box(ax, x, y, 18, 7, s, fc=BLUE_L if lit else GRAY_L, ec=BLUE if lit else FAINT, size=20,
            color=BLUE if lit else INK, weight="bold" if s == "학습" else "normal")
        if lit:
            label(ax, x + 9, y - 4.2, notes[s], size=16, color=MUTED, ha="center", va="center")
        if k % 5 != 0 and not (row == 1 and col == 0):
            px = x - 4 + 0.4
            arrow(ax, px, y + 3.5, x - 0.4, y + 3.5, lw=2)
    ax.plot([100, 100, 25], [30, 20, 20], color=MUTED, lw=2, zorder=2)
    arrow(ax, 25, 20, 25, 16.4, color=MUTED, lw=2)
    label(ax, 64, 2.5, "파란 칸: 노트북 01 이 미리 보여 주는 부분", size=18, color=BLUE)
    return save_png("1b-4", to_image(fig))


# 1c 대입과 copy

def cells_row(ax, x, y, vals, fc="white", ec=INK, w=6, h=6, lit=None, size=22, color=INK):
    for k, v in enumerate(vals):
        box(ax, x + w * k, y, w, h, sign(v), fc=HL if lit == k else fc, ec=ec, size=size, color=color, lw=2)


@figure("1c-1")
def plus_png():
    fig, ax = canvas(40)
    title(ax, "리스트의 +와 numpy 배열의 +", 40)
    label(ax, 3, 27, "리스트", size=22, weight="bold")
    cells_row(ax, 22, 24, [1, 2, 3], fc=GRAY_L)
    label(ax, 42, 27, "+", size=26, ha="center")
    cells_row(ax, 45, 24, [4, 5, 6], fc=GRAY_L)
    label(ax, 64.5, 27, "→", size=26, ha="center")
    cells_row(ax, 68, 24, [1, 2, 3, 4, 5, 6], fc=GRAY_L)
    label(ax, 68, 20.5, "이어 붙이기: 원소 여섯 개", size=18, color=MUTED)
    assert [1, 2, 3] + [4, 5, 6] == [1, 2, 3, 4, 5, 6]
    label(ax, 3, 10, "numpy 배열", size=22, weight="bold")
    cells_row(ax, 22, 7, [1, 2, 3], fc=BLUE_L, ec=BLUE)
    label(ax, 42, 10, "+", size=26, ha="center")
    cells_row(ax, 45, 7, [4, 5, 6], fc=BLUE_L, ec=BLUE)
    label(ax, 64.5, 10, "→", size=26, ha="center")
    total = [a + b for a, b in zip([1, 2, 3], [4, 5, 6])]
    assert total == [5, 7, 9]
    cells_row(ax, 68, 7, total, fc=HL, ec=BLUE)
    label(ax, 68, 3.5, "같은 자리끼리 더하기: 1+4, 2+5, 3+6", size=18, color=MUTED)
    return save_png("1c-1", to_image(fig))


def tag(ax, x, y, name, color):
    box(ax, x, y, 9, 6, name, fc="white", ec=color, size=24, color=color, weight="bold", family=CODE, lw=3)


@figure("1c-2")
def alias_gif():
    a = [5, 7, 9]
    b_alias = a
    b_alias[0] = 100
    assert b_alias == [100, 7, 9] and a is b_alias
    a2 = [5, 7, 9]
    b2 = list(a2)
    a2[0] = 100
    assert (a2, b2) == ([100, 7, 9], [5, 7, 9])
    states = [
        ("x = np.array([5, 7, 9])", [5, 7, 9], None, False, None, 2200),
        ("y = x", [5, 7, 9], None, True, None, 2200),
        ("x[0] = 100", [100, 7, 9], None, True, 0, 2000),
        ("print(y)  →  [100, 7, 9]", [100, 7, 9], None, True, None, 2400),
        ("y = x.copy()", [5, 7, 9], [5, 7, 9], False, None, 2400),
        ("x[0] = 100", [100, 7, 9], [5, 7, 9], False, 0, 2400),
    ]
    frames, durs = [], []
    for code, box_a, box_b, shared, lit, ms in states:
        fig, ax = canvas(46)
        label(ax, 3, 41, code, size=26, family=CODE, color=INK, weight="bold", bg=GRAY_L)
        label(ax, 60, 34, "메모리", size=20, color=MUTED)
        box(ax, 58, 3, 51, 28, fc="#fafafa", ec=FAINT, ls="--")
        tag(ax, 6, 22, "x", BLUE)
        cells_row(ax, 66, 21, box_a, w=10, h=7, lit=lit, size=24)
        arrow(ax, 15.5, 25, 65.5, 24.5, color=BLUE, lw=3)
        if shared or box_b is not None:
            tag(ax, 6, 8, "y", GREEN)
        if shared:
            arrow(ax, 15.5, 11, 65.5, 22.5, color=GREEN, lw=3)
        if box_b is not None:
            cells_row(ax, 66, 7, box_b, w=10, h=7, size=24, fc=GREEN_L, ec=GREEN)
            arrow(ax, 15.5, 11, 65.5, 10.5, color=GREEN, lw=3)
            label(ax, 97, 4.5, "새 상자", size=18, color=GREEN)
        frames.append(to_image(fig))
        durs.append(ms)
    return save_gif("1c-2", frames, durs)


@figure("1c-3")
def assign_copy_png():
    fig, ax = canvas(40)
    title(ax, "x[0] = 100 을 실행한 뒤", 40)
    for side, (code, shared) in enumerate((("y = x", True), ("y = x.copy()", False))):
        ox = 3 + side * 56
        box(ax, ox, 3, 52, 30, fc=GRAY_L if shared else GREEN_L, ec=FAINT)
        label(ax, ox + 2, 29, code, size=24, family=CODE, weight="bold")
        tag(ax, ox + 2, 17, "x", BLUE)
        tag(ax, ox + 2, 6, "y", GREEN)
        cells_row(ax, ox + 22, 17, [100, 7, 9], w=8, h=6, lit=0, size=22)
        arrow(ax, ox + 11.5, 20, ox + 21.5, 20, color=BLUE, lw=3)
        if shared:
            arrow(ax, ox + 11.5, 9, ox + 21.5, 18.5, color=GREEN, lw=3)
            label(ax, ox + 22, 9, "y도 [100, 7, 9]", size=20, color=GREEN)
        else:
            cells_row(ax, ox + 22, 6, [5, 7, 9], w=8, h=6, size=22, fc="white", ec=GREEN)
            arrow(ax, ox + 11.5, 9, ox + 21.5, 9, color=GREEN, lw=3)
    return save_png("1c-3", to_image(fig))


@figure("1c-4")
def tensor_share_png():
    fig, ax = canvas(40)
    title(ax, "텐서와 numpy 배열의 메모리", 40)
    x1 = [1.0] * 5
    x2 = x1  # .data.numpy() 는 같은 메모리를 봄
    x3 = list(x1)  # .copy() 는 새 메모리
    x1[1] = -1.0
    assert x2 == [1.0, -1.0, 1.0, 1.0, 1.0] and x3 == [1.0] * 5
    box(ax, 3, 18, 15, 6, "x1 (텐서)", fc="white", ec=BLUE, size=19, color=BLUE)
    box(ax, 3, 9, 15, 6, "x2", fc="white", ec=PURPLE, size=20, color=PURPLE, family=CODE)
    cells_row(ax, 30, 14, ["1.", "-1.", "1.", "1.", "1."], w=9, h=6, lit=1, size=22)
    arrow(ax, 18.5, 21, 29.5, 18, color=BLUE, lw=3)
    arrow(ax, 18.5, 12, 29.5, 16, color=PURPLE, lw=3)
    label(ax, 30, 24, "같은 메모리: x1[1] = −1 이 x2에도 보임", size=18, color=MUTED)
    label(ax, 30, 10.5, "x2 = x1.data.numpy()", size=18, family=CODE, color=PURPLE)
    box(ax, 3, 1.5, 15, 6, "x3", fc="white", ec=GREEN, size=20, color=GREEN, family=CODE)
    cells_row(ax, 30, 1.5, ["1."] * 5, w=9, h=6, size=22, fc=GREEN_L, ec=GREEN)
    arrow(ax, 18.5, 4.5, 29.5, 4.5, color=GREEN, lw=3)
    label(ax, 77, 4.5, "x3 = x1.data.numpy().copy()", size=17, family=CODE, color=GREEN)
    return save_png("1c-4", to_image(fig))


# 1d 합성 함수와 미분: f(x) = 2x^2 + 2

def f2x(x):
    return 2 * x * x + 2


assert f2x(3) == 20 and (3 ** 2, 2 * 9, 18 + 2) == (9, 18, 20)


@figure("1d-1")
def compose_gif():
    vals = [3, 9, 18, 20]
    assert vals[1] == vals[0] ** 2 and vals[2] == vals[1] * 2 and vals[3] == vals[2] + 2 == f2x(3)
    names = [("f1", "제곱"), ("f2", "× 2"), ("f3", "+ 2")]
    frames, durs = [], []
    for k in range(6):
        fig, ax = canvas(40)
        title(ax, "합성 함수 f3(f2(f1(x)))", 40)
        box(ax, 3, 15, 12, 8, "x = 3", fc=GRAY_L, ec=FAINT, size=22)
        for j, (n, op) in enumerate(names):
            x = 22 + 24 * j
            lit = k in (j + 1,)
            box(ax, x, 13, 15, 12, "%s\n%s" % (n, op), fc=BLUE_L if lit else "white", ec=BLUE if (k >= j + 1 and k < 5) or lit else FAINT,
                size=22, color=BLUE if k >= j + 1 else INK)
            arrow(ax, x - 6.5, 19, x - 0.5, 19, color=BLUE if k >= j + 1 else FAINT, lw=2.5)
            if k >= j + 1:
                label(ax, x - 3.5, 23, str(vals[j]), size=22, color=BLUE, ha="center")
        arrow(ax, 89.5, 19, 95.5, 19, color=BLUE if k >= 3 else FAINT, lw=2.5)
        box(ax, 96, 15, 13, 8, "20" if k >= 3 else "y", fc=HL if k >= 3 else "white", ec=FAINT, size=24,
            weight="bold" if k >= 3 else "normal")
        if k >= 3:
            label(ax, 92.5, 23, str(vals[3]), size=22, color=BLUE, ha="center")
        if k == 3:
            label(ax, 22, 7, "입력에서 출력 쪽으로 차례로 계산: 순전파", size=20, color=BLUE)
        if k == 4:
            box(ax, 19, 10, 69, 18, fc="none", ec=PURPLE, lw=3, ls="--")
            label(ax, 22, 6, "세 상자를 묶은 함수  f(x) = $2x^2 + 2$,  f(3) = 20", size=21, color=PURPLE)
        if k == 5:
            arrow(ax, 102, 9, 9, 9, color=ORANGE, lw=3.5)
            label(ax, 55, 5, "역전파: 출력에서 입력 쪽으로 거슬러 가기", size=20, color=ORANGE, ha="center")
        frames.append(to_image(fig))
        durs.append([2200, 1800, 1800, 2400, 2200, 2400][k])
    return save_gif("1d-1", frames, durs)


@figure("1d-2")
def tangent_png():
    d = f2x(Fraction(3001, 1000)) - f2x(3)
    assert d == Fraction(12002, 1000000) and 4 * 3 == 12
    fig = plt.figure(figsize=(11.2, 5.0), dpi=100)
    ax = fig.add_axes([0.08, 0.14, 0.52, 0.74])
    tidy(ax)
    xs = np.linspace(0, 4.5, 200)
    ax.plot(xs, f2x(xs), color=INK, lw=2.5)
    ax.plot(xs, 20 + 12 * (xs - 3), color=ORANGE, lw=3)
    ax.plot([3], [20], "o", color=INK, ms=12)
    ax.set_xlim(0, 4.5)
    ax.set_ylim(0, 44)
    ax.set_xlabel("x")
    ax.set_ylabel("f(x)")
    ax.set_title("f(x) = $2x^2 + 2$ 와 x = 3 의 접선", loc="left", fontsize=22)
    ax.annotate("접선 기울기 12", (3.15, 7), color=ORANGE, fontsize=22)
    fig.text(0.64, 0.80, "x = 3 에서 0.001 키우면", fontsize=21, color=INK)
    fig.text(0.64, 0.66, "x: 3 → 3.001", fontsize=21, color=MUTED, family=CODE)
    fig.text(0.64, 0.55, "f: 20 → %s" % dec(f2x(Fraction(3001, 1000))), fontsize=21, color=MUTED, family=CODE)
    fig.text(0.64, 0.40, "약 0.012 증가", fontsize=21, color=ORANGE)
    fig.text(0.64, 0.29, "0.012 ÷ 0.001 = 12", fontsize=21, color=ORANGE)
    fig.text(0.64, 0.13, "미분 4x 에 x = 3 을 넣은 값", fontsize=19, color=MUTED)
    assert dec(f2x(Fraction(3001, 1000))) == "20.012002"
    return save_png("1d-2", to_image(fig))


DIFFS = []
for _h in (Fraction(1), Fraction(1, 2), Fraction(1, 10)):
    DIFFS.append((_h, (f2x(3 + _h) - f2x(3)) / _h, (f2x(3 + _h) - f2x(3 - _h)) / (2 * _h)))
assert [(dec(h), dec(fw), dec(c)) for h, fw, c in DIFFS] == [("1", "14", "12"), ("0.5", "13", "12"), ("0.1", "12.2", "12")]
assert (f2x(4), f2x(2), f2x(4) - f2x(2)) == (34, 10, 24)


@figure("1d-3")
def central_gif():
    xs = np.linspace(1.4, 4.6, 200)
    frames, durs = [], []

    def base(t):
        fig = plt.figure(figsize=(11.2, 5.4), dpi=100)
        ax = fig.add_axes([0.08, 0.13, 0.56, 0.75])
        tidy(ax)
        ax.plot(xs, f2x(xs), color=INK, lw=2.5)
        ax.plot(xs, 20 + 12 * (xs - 3), color=ORANGE, lw=2.5)
        ax.plot([3], [20], "o", color=INK, ms=11)
        ax.set_xlim(1.4, 4.6)
        ax.set_ylim(0, 46)
        ax.set_xlabel("x")
        ax.set_ylabel("f(x)")
        ax.set_title(t, loc="left", fontsize=22)
        return fig, ax

    def secant(ax, a, b, color, ls):
        fa, fb = float(f2x(a)), float(f2x(b))
        s = (fb - fa) / float(b - a)
        ax.plot(xs, fa + s * (xs - float(a)), color=color, lw=2.5, ls=ls)
        ax.plot([float(a), float(b)], [fa, fb], "o", color=color, ms=10)

    def side(fig, lines):
        y = 0.82
        for t, c in lines:
            fig.text(0.67, y, t, fontsize=21, color=c)
            y -= 0.11

    fig, ax = base("x = 3 에서 닿는 접선")
    side(fig, [("접선의 기울기 12", ORANGE)])
    frames.append(to_image(fig)); durs.append(2200)
    h, fw, c = DIFFS[0]
    fig, ax = base("h = 1 전진 차분")
    secant(ax, 3, 4, MUTED, "--")
    side(fig, [("점 (3, 20), (4, 34)", MUTED), ("(34 %s 20) ÷ 1 = %s" % (M, dec(fw)), MUTED), ("접선 12", ORANGE)])
    frames.append(to_image(fig)); durs.append(2200)
    fig, ax = base("h = 1 중앙 차분")
    secant(ax, 3, 4, FAINT, "--")
    secant(ax, 2, 4, GREEN, "-")
    side(fig, [("점 (2, 10), (4, 34)", GREEN), ("24 ÷ 2 = %s" % dec(c), GREEN), ("접선과 나란한 선", GREEN), ("전진 차분 14", MUTED)])
    frames.append(to_image(fig)); durs.append(2400)
    for (h, fw, c), ms in zip(DIFFS[1:], (2200, 2400)):
        fig, ax = base("h = %s" % dec(h))
        secant(ax, 3, 3 + h, MUTED, "--")
        secant(ax, 3 - h, 3 + h, GREEN, "-")
        side(fig, [("전진 차분 %s" % dec(fw), MUTED), ("중앙 차분 %s" % dec(c), GREEN), ("접선 12", ORANGE)])
        frames.append(to_image(fig)); durs.append(ms)
    fig, ax = base("정리: 이차 함수에서 중앙 차분은 늘 12")
    for h, fw, c in DIFFS:
        secant(ax, 3, 3 + h, FAINT, "--")
    secant(ax, 2, 4, GREEN, "-")
    fig.text(0.67, 0.82, "h      전진   중앙", fontsize=21, color=MUTED, family=CODE)
    for k, (h, fw, c) in enumerate(DIFFS):
        fig.text(0.67, 0.70 - 0.1 * k, "%-6s %-6s %s" % (dec(h), dec(fw), dec(c)), fontsize=22, family=CODE)
    fig.text(0.67, 0.30, "접선 기울기 12", fontsize=21, color=ORANGE)
    frames.append(to_image(fig)); durs.append(2500)
    frames[-1].save(os.path.join(OUT, "_1d-5.tmp.png"))
    out = save_gif("1d-3", frames, durs)
    img = Image.open(os.path.join(OUT, "_1d-5.tmp.png")).convert("RGB")
    os.remove(os.path.join(OUT, "_1d-5.tmp.png"))
    save_png("1d-5", img)
    return out


@figure("1d-4")
def hog_png():
    grid = [[15, 20, 25], [10, 30, 40], [35, 60, 55]]
    left, right, up, down = grid[1][0], grid[1][2], grid[0][1], grid[2][1]
    dx, dy = right - left, down - up
    mag, ang = math.hypot(dx, dy), math.degrees(math.atan2(dy, dx))
    assert (dx, dy, mag, round(ang, 1)) == (30, 40, 50.0, 53.1)
    fig, ax = canvas(44)
    title(ax, "가운데 칸의 밝기 변화 구하기", 44)
    for r in range(3):
        for c in range(3):
            v = grid[r][c]
            shade = 1 - v / 80
            fc = (shade, shade, shade)
            ec = ORANGE if (r, c) in ((1, 0), (1, 2)) else BLUE if (r, c) in ((0, 1), (2, 1)) else FAINT
            box(ax, 6 + 10 * c, 26 - 10 * r, 9, 9, str(v), fc=fc, ec=ec, lw=3 if ec != FAINT else 1.5, size=24,
                color="white" if v >= 45 else INK)
    label(ax, 6, 3.5, "칸 숫자 = 밝기(직접 만든 예)", size=17, color=MUTED)
    label(ax, 40, 31, "dx = 오른쪽 %s 왼쪽 = 40 %s 10 = %d" % (M, M, dx), size=22, color=ORANGE)
    label(ax, 40, 24, "dy = 아래 %s 위 = 60 %s 20 = %d" % (M, M, dy), size=22, color=BLUE)
    label(ax, 40, 16, "크기 $\\sqrt{30^2 + 40^2}$ = %d" % mag, size=22, color=INK)
    label(ax, 40, 9, "방향 arctan(40 ÷ 30) ≈ %.1f°" % ang, size=22, color=INK)
    label(ax, 40, 3.5, "[%s1, 0, 1] 필터 = 중앙 차분의 분자" % M, size=19, color=GREEN)
    ox, oy, s = 96, 6, 0.24
    arrow(ax, ox, oy, ox + dx * s, oy, color=ORANGE, lw=3)
    arrow(ax, ox + dx * s, oy, ox + dx * s, oy + dy * s, color=BLUE, lw=3)
    arrow(ax, ox, oy, ox + dx * s, oy + dy * s, color=INK, lw=3.5)
    return save_png("1d-4", to_image(fig))


# 1e 수치 미분 코드와 자동 미분

def fdiff(f):
    def diff(x):
        h = 1e-6
        return (f(x + h) - f(x - h)) / (2 * h)
    return diff


FD = fdiff(lambda x: 2 * x ** 2 + 2)(3.0)
assert repr(FD) == "12.000000001677336"


@figure("1e-1")
def fdiff_png():
    fig, ax = canvas(36)
    title(ax, "fdiff는 함수를 받아 함수를 돌려줍니다", 36)
    box(ax, 3, 18, 22, 8, "함수 f\n$2x^2 + 2$", fc=GRAY_L, ec=FAINT, size=20)
    arrow(ax, 25.5, 22, 32.5, 22)
    box(ax, 33, 17, 20, 10, "fdiff", fc=BLUE_L, ec=BLUE, size=26, family=CODE, color=BLUE, weight="bold")
    arrow(ax, 53.5, 22, 60.5, 22)
    box(ax, 61, 18, 22, 8, "함수 diff", fc=GREEN_L, ec=GREEN, size=22, color=GREEN)
    label(ax, 3, 13, "함수를 넣으면 함수가 나옵니다", size=19, color=MUTED)
    box(ax, 33, 3, 12, 7, "3.0", fc=GRAY_L, ec=FAINT, size=22, family=CODE)
    arrow(ax, 45.5, 6.5, 52.5, 6.5)
    box(ax, 53, 3, 14, 7, "diff", fc=GREEN_L, ec=GREEN, size=22, family=CODE, color=GREEN)
    arrow(ax, 67.5, 6.5, 72.5, 6.5)
    label(ax, 73, 6.5, repr(FD), size=22, family=CODE, color=INK, weight="bold")
    label(ax, 73, 12, "숫자를 넣어야 숫자가 나옵니다", size=19, color=MUTED)
    return save_png("1e-1", to_image(fig))


HS = [10.0 ** -e for e in range(1, 13)]
ERRS = [abs(((1 + h) ** 3 - (1 - h) ** 3) / (2 * h) - 3) for h in HS]
assert "%.1e" % ERRS[0] == "1.0e-02" and "%.1e" % ERRS[3] == "1.0e-08" and "%.1e" % ERRS[5] == "8.0e-11"
assert "%.1e" % ERRS[11] == "1.0e-04" and min(range(12), key=lambda k: ERRS[k]) == 5


@figure("1e-2")
def h_error_png():
    fig = plt.figure(figsize=(11.2, 5.0), dpi=100)
    ax = fig.add_axes([0.11, 0.16, 0.58, 0.72])
    tidy(ax)
    ax.loglog(HS, ERRS, "o-", color=BLUE, lw=2.5, ms=9)
    ax.invert_xaxis()
    ax.set_xlabel("h (오른쪽으로 갈수록 작음)")
    ax.set_title("$x^3$ 의 x = 1 에서 중앙 차분 오차", loc="left", fontsize=22)
    ax.plot([HS[5]], [ERRS[5]], "o", color=ORANGE, ms=14, zorder=5)
    ax.set_ylim(1e-12, 1)
    ax.xaxis.set_major_locator(FixedLocator([10.0 ** -e for e in (1, 3, 6, 9, 12)]))
    ax.yaxis.set_major_locator(FixedLocator([10.0 ** -e for e in (0, 3, 6, 9, 12)]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_minor_locator(NullLocator())
    tick = FuncFormatter(lambda v, _: "1" if v >= 1 else "1e%s%d" % (M, round(-math.log10(v))))
    ax.xaxis.set_major_formatter(tick)
    ax.yaxis.set_major_formatter(tick)
    rows = [("h", "오차", MUTED), ("0.1", sign("%.1e" % ERRS[0]), INK), ("1e%s4" % M, sign("%.1e" % ERRS[3]), INK),
            ("1e%s6" % M, sign("%.1e" % ERRS[5]), ORANGE), ("1e%s12" % M, sign("%.1e" % ERRS[11]), INK)]
    for k, (a, b, c) in enumerate(rows):
        fig.text(0.73, 0.82 - 0.09 * k, a, fontsize=20, color=c, family=CODE)
        fig.text(0.84, 0.82 - 0.09 * k, b, fontsize=20, color=c, family=CODE)
    fig.text(0.73, 0.30, "1e%s6 근처에서 가장 작고" % M, fontsize=19, color=ORANGE)
    fig.text(0.73, 0.21, "더 줄이면 반올림 오차로", fontsize=19)
    fig.text(0.73, 0.12, "다시 커집니다", fontsize=19)
    return save_png("1e-2", to_image(fig))


@figure("1e-3")
def compare_png():
    fig, ax = canvas(52)
    title(ax, "같은 기울기를 구하는 두 방법 (f(x) = $2x^2 + 2$, x = 3)", 52, size=22)
    box(ax, 3, 30, 51, 15, fc=GRAY_L, ec=FAINT)
    label(ax, 6, 41.5, "수치 미분 (fdiff)", size=22, weight="bold")
    label(ax, 6, 36.5, "f(3 + h)와 f(3 %s h)를 두 번 계산" % M, size=19, color=MUTED)
    label(ax, 6, 32.5, repr(FD), size=22, family=CODE)
    box(ax, 58, 30, 51, 15, fc=BLUE_L, ec=BLUE)
    label(ax, 61, 41.5, "자동 미분 (backward)", size=22, weight="bold", color=BLUE)
    label(ax, 61, 36.5, "계산 기록을 거꾸로 따라가며 미분 규칙", size=19, color=MUTED)
    label(ax, 61, 32.5, "tensor(12.)", size=22, family=CODE, color=BLUE)
    rows = [("방식", "두 점의 값 차이로 어림", "미분 규칙을 그대로 적용"),
            ("오차", "h에 따라 오차가 있음", "식으로 구한 값"),
            ("속도", "파라미터마다 두 번 계산", "순전파 한 번 + 역전파 한 번"),
            ("쓰는 곳", "검증, 디버깅", "학습")]
    for k, (a, b, c) in enumerate(rows):
        y = 23 - 5.4 * k
        label(ax, 4, y, a, size=19, weight="bold", color=MUTED)
        label(ax, 16, y, b, size=19)
        label(ax, 61, y, c, size=19, color=BLUE)
    return save_png("1e-3", to_image(fig))


@figure("1e-4")
def sigmoid_png():
    sig = lambda v: 1 / (1 + np.exp(-v))  # noqa: E731
    y2 = float(sig(2))
    assert round(y2, 4) == 0.8808 and round(y2 * (1 - y2), 3) == 0.105 and float(sig(0)) == 0.5
    fig = plt.figure(figsize=(11.2, 5.0), dpi=100)
    ax = fig.add_axes([0.08, 0.15, 0.6, 0.72])
    tidy(ax)
    xs = np.linspace(-6, 6, 300)
    ys = sig(xs)
    ax.plot(xs, ys, color=BLUE, lw=3, label="g(x)")
    ax.plot(xs, ys * (1 - ys), color=ORANGE, lw=3, label="기울기")
    ax.plot([0], [0.25], "o", color=ORANGE, ms=11)
    ax.plot([2, 2], [y2, y2 * (1 - y2)], "o", color=INK, ms=9)
    ax.annotate("x = 0 에서 0.25", (0, 0.25), xytext=(-5.8, 0.36), fontsize=20, color=ORANGE)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("x")
    ax.set_title("시그모이드와 그 기울기", loc="left", fontsize=22)
    fig.text(0.71, 0.80, "파란 선 g(x): 0 과 1 사이", fontsize=19, color=BLUE)
    fig.text(0.71, 0.70, "주황 선 기울기 y(1 %s y)" % M, fontsize=19, color=ORANGE)
    fig.text(0.71, 0.52, "x = 0: y = 0.5", fontsize=20)
    fig.text(0.71, 0.43, "  0.5 × 0.5 = 0.25", fontsize=20, color=ORANGE)
    fig.text(0.71, 0.29, "x = 2: y ≈ %.4f" % y2, fontsize=20)
    fig.text(0.71, 0.20, "  기울기 ≈ %.3f" % (y2 * (1 - y2)), fontsize=20, color=ORANGE)
    return save_png("1e-4", to_image(fig))


# 1f 클래스

@figure("1f-1")
def class_png():
    fig, ax = canvas(44)
    title(ax, "클래스(설계도) 하나로 인스턴스(실체) 여럿", 44)
    box(ax, 3, 4, 34, 32, fc=BLUE_L, ec=BLUE)
    label(ax, 6, 32, "class Point", size=24, family=CODE, weight="bold", color=BLUE)
    label(ax, 6, 25.5, "속성", size=20, color=MUTED)
    label(ax, 6, 21, "x, y", size=22, family=CODE)
    label(ax, 6, 14.5, "메서드", size=20, color=MUTED)
    label(ax, 6, 10, "move(dx, dy)", size=21, family=CODE)
    label(ax, 6, 6, "coord()", size=21, family=CODE)
    for k, (name, x, y) in enumerate((("p1", 2, 3), ("p2", -1, -2))):
        oy = 22 - 15 * k
        box(ax, 45, oy, 30, 12, fc="white", ec=INK)
        label(ax, 47, oy + 8.5, "%s = Point(%s, %s)" % (name, sign(x), sign(y)), size=20, family=CODE)
        label(ax, 47, oy + 3.5, "x = %s, y = %s" % (sign(x), sign(y)), size=20, color=MUTED)
        arrow(ax, 37.5, 20, 44.5, oy + 6, color=BLUE)
    label(ax, 45, 3, "인스턴스마다 자기 속성 값", size=18, color=MUTED)
    gx, gy, s = 92, 20, 3.2
    ax.plot([gx - 4 * s, gx + 4 * s], [gy, gy], color=FAINT, lw=1.5)
    ax.plot([gx, gx], [gy - 4 * s, gy + 4 * s], color=FAINT, lw=1.5)
    for name, x, y in (("p1", 2, 3), ("p2", -1, -2)):
        ax.add_patch(Circle((gx + x * s, gy + y * s), 1.0, color=INK, zorder=5))
        label(ax, gx + x * s + 1.5, gy + y * s, "%s(%s, %s)" % (name, sign(x), sign(y)), size=18)
    return save_png("1f-1", to_image(fig))


@figure("1f-2")
def point_gif():
    states = [((2, 3), "p = Point(2, 3)", "p.x = 2, p.y = 3", 2200),
              ((2, 3), "p.move(1, -1)", "self → p", 2000),
              ((3, 3), "self.x += 1", "p.x: 2 → 3", 2000),
              ((3, 2), "self.y += -1", "p.y: 3 → 2", 2200),
              ((3, 2), "p.coord()", "(3, 2) 를 돌려줌", 2000),
              ((4, 1), "p.move(1, -1)", "다시 옮기면 (4, 1)", 2400)]
    x, y = 2, 3
    x, y = x + 1, y - 1
    assert (x, y) == (3, 2) and (x + 1, y - 1) == (4, 1)
    frames, durs = [], []
    trail = []
    for (px, py), code, note, ms in states:
        fig = plt.figure(figsize=(11.2, 5.0), dpi=100)
        ax = fig.add_axes([0.07, 0.14, 0.42, 0.76])
        tidy(ax)
        ax.set_xlim(-1, 5)
        ax.set_ylim(-1, 4)
        ax.set_xticks(range(-1, 6))
        ax.set_yticks(range(-1, 5))
        ax.set_aspect("equal")
        for t in trail:
            ax.plot(*t, "o", color=FAINT, ms=12)
        ax.plot(px, py, "o", color=BLUE, ms=16, zorder=5)
        ax.annotate("(%d, %d)" % (px, py), (px, py), xytext=(10, 10), textcoords="offset points", fontsize=21, color=BLUE)
        fig.text(0.55, 0.80, code.replace("-", M), fontsize=26, family=CODE, weight="bold",
                 bbox={"boxstyle": "round,pad=0.3", "fc": GRAY_L, "ec": GRAY_L})
        fig.text(0.55, 0.60, note.replace("-", M), fontsize=24, color=GREEN)
        fig.text(0.55, 0.36, "속성", fontsize=20, color=MUTED)
        fig.text(0.55, 0.24, "p.x = %d,  p.y = %d" % (px, py), fontsize=24, family=CODE)
        trail.append((px, py))
        frames.append(to_image(fig))
        durs.append(ms)
    return save_gif("1f-2", frames, durs)


@figure("1f-3")
def override_png():
    fig = plt.figure(figsize=(11.2, 4.6), dpi=100)
    cases = [("Circle1", "draw를 정의하지 않은 자식", True, False), ("Circle2", "draw를 재정의한 자식", False, True),
             ("Circle3", "super().draw() 뒤 원 그리기", True, True)]
    for k, (name, how, dot, circ) in enumerate(cases):
        ax = fig.add_axes([0.04 + 0.33 * k, 0.08, 0.27, 0.62])
        ax.set_xlim(-2, 4)
        ax.set_ylim(-3, 3)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(FAINT)
        if circ:
            ax.add_patch(Circle((1, 0), 2, fc=BLUE_L, ec=BLUE, lw=2.5))
        if dot:
            ax.plot(1, 0, "o", color=INK, ms=12, zorder=5)
        fig.text(0.04 + 0.33 * k, 0.88, name, fontsize=24, family=CODE, weight="bold")
        fig.text(0.04 + 0.33 * k, 0.77, how, fontsize=19, color=MUTED)
        res = "점만" if dot and not circ else "원만" if circ and not dot else "점과 원"
        fig.text(0.04 + 0.33 * k + 0.2, 0.88, res, fontsize=22, color=GREEN)
    return save_png("1f-3", to_image(fig))


@figure("1f-4")
def call_png():
    assert 2 * 3 + 2 == 8
    fig, ax = canvas(36)
    title(ax, "괄호로 부르면 __call__ 이 불립니다", 36)
    row = [("h(3)", GRAY_L, FAINT), ("h.__call__(3)", BLUE_L, BLUE), ("2 × 3 + 2", GRAY_L, FAINT), ("8", HL, FAINT)]
    xs = [3, 25, 61, 90]
    ws = [17, 31, 24, 19]
    for (t, fc, ec), x, w in zip(row, xs, ws):
        box(ax, x, 18, w, 7, t, fc=fc, ec=ec, size=21, family=CODE)
    for x0, x1 in ((20.4, 24.6), (56.4, 60.6), (85.4, 89.6)):
        arrow(ax, x0, 21.5, x1, 21.5)
    row = [("model(x)", GRAY_L, FAINT), ("nn.Module 의 __call__", BLUE_L, BLUE), ("forward(x)", GREEN_L, GREEN), ("출력", HL, FAINT)]
    for (t, fc, ec), x, w in zip(row, xs, ws):
        box(ax, x, 5, w, 7, t, fc=fc, ec=ec, size=18 if len(t) > 12 else 21, family=CODE if t != "출력" else None)
    for x0, x1 in ((20.4, 24.6), (56.4, 60.6), (85.4, 89.6)):
        arrow(ax, x0, 8.5, x1, 8.5)
    label(ax, 25, 1.8, "등록한 훅도 함께 실행", size=17, color=MUTED)
    return save_png("1f-4", to_image(fig))


# 1g 파이썬 기초

@figure("1g-1")
def notebook_png():
    fig, ax = canvas(50)
    box(ax, 3, 43, 106, 5, "", fc=GRAY_L, ec=FAINT)
    label(ax, 5, 45.5, "노트북 (.ipynb)", size=20, weight="bold")
    label(ax, 106, 45.5, "런타임 유형: GPU", size=18, color=GREEN, ha="right")
    cells = [("글 셀", "파이썬 입문", "white", None, None),
             ("코드 셀", "print(1 + 2)", "#f8fafc", "3", None),
             ("코드 셀", "!pip install matplotlib", "#f8fafc", None, "! 줄: 셸 명령"),
             ("코드 셀", "%pwd", "#f8fafc", None, "% 줄: 매직 명령")]
    y = 35
    for kind, text, fc, out, note in cells:
        hh = 9 if out else 6
        box(ax, 16, y - hh + 6, 60, hh, fc=fc, ec=FAINT)
        label(ax, 3, y + 3, kind, size=17, color=MUTED)
        label(ax, 18, y + 3.5 if out else y + 3, text, size=20, family=CODE if kind == "코드 셀" else None,
              weight="bold" if kind == "글 셀" else "normal")
        if out:
            label(ax, 18, y - 1.2, "출력  " + out, size=18, family=CODE, color=MUTED)
        if note:
            label(ax, 78, y + 3, note, size=17, color=ORANGE)
        y -= hh + 2
    assert 1 + 2 == 3
    return save_png("1g-1", to_image(fig))


@figure("1g-2")
def division_png():
    q, r = divmod(13, 5)
    assert (q, r, 13 / 5) == (2, 3, 2.6) and 5 * q + r == 13
    fig, ax = canvas(36)
    title(ax, "13 을 5 개씩 묶기", 36)
    for k in range(13):
        g, j = divmod(k, 5)
        x = 6 + g * 22 + j * 4
        color = BLUE if g < q else ORANGE
        ax.add_patch(Circle((x, 22), 1.4, color=color, zorder=3))
    for g in range(q):
        box(ax, 3 + g * 22, 18, 20, 8, fc="none", ec=BLUE, lw=2)
        label(ax, 13 + g * 22, 14.5, "묶음 %d" % (g + 1), size=18, color=BLUE, ha="center")
    label(ax, 3 + q * 22 + 6, 14.5, "남은 %d개" % r, size=18, color=ORANGE, ha="center")
    label(ax, 72, 26, "13 / 5  = 2.6", size=22, family=CODE)
    label(ax, 72, 20, "13 // 5 = 2   몫", size=22, family=CODE, color=BLUE)
    label(ax, 72, 14, "13 %% 5  = %d   나머지" % r, size=22, family=CODE, color=ORANGE)
    label(ax, 3, 5, "13 = 5 × 2 + 3   (나누는 수 × 몫 + 나머지)", size=21)
    return save_png("1g-2", to_image(fig))


@figure("1g-3")
def slice_png():
    data = [1, 2, 3, 4, 5]
    assert data[1:-1] == [2, 3, 4] and data[:-1] == [1, 2, 3, 4] and data[::-1] == [5, 4, 3, 2, 1]
    fig, ax = canvas(42)
    title(ax, "인덱스와 슬라이스", 42)
    x0, w = 6, 10
    for k, v in enumerate(data):
        inside = 1 <= k <= 3
        box(ax, x0 + w * k, 17, w, 8, str(v), fc=GREEN_L if inside else "white", ec=GREEN if inside else INK, size=24)
        label(ax, x0 + w * k + w / 2, 28, str(k), size=20, color=MUTED, ha="center")
        label(ax, x0 + w * k + w / 2, 13.5, sign(k - 5), size=20, color=MUTED, ha="center")
    label(ax, x0 - 1, 31.5, "인덱스", size=17, color=MUTED)
    ax.plot([x0 + w + 0.5, x0 + w * 4 - 0.5], [10, 10], color=GREEN, lw=3)
    for xx in (x0 + w + 0.5, x0 + w * 4 - 0.5):
        ax.plot([xx, xx], [10, 11.5], color=GREEN, lw=3)
    label(ax, x0, 6, "[1:%s1]: 인덱스 1 부터 %s1 앞까지" % (M, M), size=19, color=GREEN)
    label(ax, 64, 26, "list1[:%s1]   → [1, 2, 3, 4]" % M, size=20, family=CODE)
    label(ax, 64, 20, "list1[1:%s1]  → [2, 3, 4]" % M, size=20, family=CODE, color=GREEN)
    label(ax, 64, 14, "list1[::%s1]  → [5, 4, 3, 2, 1]" % M, size=20, family=CODE)
    label(ax, 64, 9, "[::%s1] 은 정렬이 아니라 뒤집기" % M, size=18, color=MUTED)
    return save_png("1g-3", to_image(fig))


@figure("1g-4")
def tuple_dict_png():
    scores = {"수학": 90, "영어": 85}
    assert list(scores.items()) == [("수학", 90), ("영어", 85)]
    fig, ax = canvas(36)
    title(ax, "튜플, 딕셔너리, items()", 36)
    label(ax, 3, 27, "튜플", size=21, weight="bold")
    cells_row(ax, 3, 15, [1, 2, 3, 4], w=7, h=7, fc=GRAY_L, ec=MUTED)
    label(ax, 3, 10.5, "t[1] = 10 → TypeError", size=17, family=CODE, color=RED)
    label(ax, 3, 6, "원소를 바꿀 수 없는 묶음", size=17, color=MUTED)
    label(ax, 40, 27, "딕셔너리", size=21, weight="bold")
    for k, (key, val) in enumerate(scores.items()):
        y = 18 - 8 * k
        box(ax, 40, y, 12, 6, "'%s'" % key, fc=BLUE_L, ec=BLUE, size=20)
        arrow(ax, 52.5, y + 3, 57.5, y + 3, color=BLUE)
        box(ax, 58, y, 9, 6, str(val), fc="white", ec=INK, size=21)
    label(ax, 40, 6, "키 → 값", size=17, color=MUTED)
    label(ax, 75, 27, "scores.items()", size=21, weight="bold", family=CODE)
    for k, (key, val) in enumerate(scores.items()):
        label(ax, 77, 20 - 7 * k, "('%s', %d)" % (key, val), size=21, family=CODE, color=GREEN)
    label(ax, 75, 6, "for k, v in ... 로 나눠 받기", size=17, color=MUTED)
    return save_png("1g-4", to_image(fig))


@figure("1g-5")
def fstring_png():
    a1, a2 = 1 / 7, 123
    rows = [(".4f", f"{a1:.4f}", "a1"), ("04", f"{a2:04}", "a2"), (".04e", f"{a1:.04e}", "a1"), ("#x", f"{a2:#x}", "a2"),
            (".1%", f"{0.9:.1%}", "0.9")]
    assert [r[1] for r in rows] == ["0.1429", "0123", "1.4286e-01", "0x7b", "90.0%"]
    fig, ax = canvas(46)
    title(ax, "f-string 서식 읽기", 46)
    cw = 2.09  # D2Coding 30pt 한 글자 폭(칸)
    parts = [("f'{", INK), ("a1", BLUE), (":", MUTED), (".4", GREEN), ("f", ORANGE), ("}'", INK)]
    i = 0
    for text, color in parts:
        for ch in text:
            label(ax, 6 + i * cw, 32.5, ch, size=30, family=CODE, weight="bold", color=color)
            i += 1
    assert "".join(t for t, _ in parts) == "f'{a1:.4f}'"
    for x, text, color in ((6, "a1: 끼워 넣을 값", BLUE), (32, "콜론: 서식 시작", MUTED), (56, ".4: 소수점 아래 네 자리", GREEN),
                           (88, "f: 고정소수점", ORANGE)):
        label(ax, x, 26, text, size=18, color=color)
    label(ax, 40, 32.5, "a1 = 1 / 7 = 0.142857…,  a2 = 123", size=20, color=MUTED)
    for k, (spec, out, var) in enumerate(rows):
        y = 20 - 4.2 * k
        label(ax, 6, y, "{%s:%s}" % (var, spec), size=21, family=CODE)
        label(ax, 34, y, "→ %s" % out.replace("-", M), size=21, family=CODE, color=GREEN)
    notes = ["소수 넷째 자리까지 반올림", "0 으로 채운 네 자리", "지수 표기(1.4286 × 10의 %s1제곱)" % M, "0x를 붙인 16진수", "100 을 곱하고 % 붙임"]
    for k, t in enumerate(notes):
        label(ax, 62, 20 - 4.2 * k, t, size=18, color=MUTED)
    return save_png("1g-5", to_image(fig))


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    names = argv or sorted(FIGS)
    for name in names:
        path, size = FIGS[name]()
        with Image.open(path) as img:
            w, h = img.size
            n = getattr(img, "n_frames", 1)
        print("%-5s %4dx%-3d %2d장 %6.1fKB" % (name, w, h, n, size / KB))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
