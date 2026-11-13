#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""7차시 학습 노트 l07 의 그림(7a nn.Linear, 7b 최소제곱법, 7c 다항 회귀, 7d 모델 클래스와 손실, 7e 보스턴 학습과 학습률,
7f R² 와 규제, 7g 학습 기록과 회귀 직선).

그림에 찍는 숫자는 모두 이 파일에서 numpy 와 Fraction 으로 다시 계산하고 assert 로 확인함(7차시 노트북 01 [14]·[18]·[21]·
[54]·[56] 출력, 4차시 다섯 사람 자료, 출제 기록 pr4/checks/l07_values.py 와 같은 값). 7e-3 의 손실 곡선만 보스턴 RM 자료
(노트북 01 [35]·[51] 출력에서 뽑은 506개)로 다시 학습한 값이고, 그 자료가 없으면 그 그림은 건너뜀.

  python -m tools.ai_art l07                 ai/learn/l07/assets/ 에 그림을 모두 쓰고 manifest 를 고침
  python -m tools.ai_art l07 7b-1            이름을 적은 그림만

numpy·matplotlib·Pillow 가 있는 출제자 파이썬에서만 돌림. matplotlib 는 Agg 로만 씀(창을 띄우지 않음).
파일은 1120×600 이하(화면 560×300), GIF 는 장 10개 이하·장마다 1600~2500ms·64색, 마지막 장은 정지 요약임.
"""
import os
import sys
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from tools.ai_art import COLORS, MINUS, figure, setup  # noqa: E402

INK, MUTED, FAINT, GRID = COLORS["ink"], COLORS["muted"], COLORS["faint"], COLORS["grid"]
BLUE, RED, ORANGE, GREEN, PURPLE, HL = (COLORS["blue"], COLORS["red"], COLORS["orange"], COLORS["green"],
                                        COLORS["purple"], COLORS["highlight"])
NOTE, BAND, GRAY = "#f3f4f6", "#e5e7eb", "#9ca3af"
PURPLE_L, ORANGE_L, GREEN_L, BLUE_L, RED_L = "#ede9fe", "#ffedd5", "#d1fae5", "#eff6ff", "#fee2e2"
CODE = "D2Coding"
MATH = "DejaVu Sans"
BOSTON = os.environ.get("L07_BOSTON", os.path.expanduser("~/.cache/rokey-dev/aiintro-design/factcheck/scripts/i07_boston_rm.npz"))
# 단원마다 한 색은 한 뜻이고, 뜻은 그 그림의 캡션에 적음. 그림 안 설명 글은 회색(NOTE) 바탕이고 뜻이 없음
# 7a: 파랑은 입력 x, 초록은 출력 y, 보라는 파라미터 weight·bias, 노랑은 지금 계산하는 칸
# 7b: 검은 점은 다섯 사람, 파랑은 식으로 구한 직선, 빨강은 잔차와 잔차 제곱합, 회색 점선은 경사하강법 직선, 보라는 1 열과 b
# 7c: 검은 점은 자료, 파랑은 직선, 초록은 다항식 곡선, 빨강은 잔차, 주황은 극값, 회색은 앞 장의 곡선,
#     보라 테두리는 파라미터에 대해 선형인 모델
# 7d: 파랑은 __init__, 초록은 forward, 보라는 파라미터 이름, 노랑은 지금 실행되는 칸, 빨강은 손실, 주황은 접선
# 7e: 파랑은 출력, 초록은 정답, 빨강은 뺀 값과 손실, 회색 열은 노트북 01, 보라 열은 손실 ÷ 2 인 슬라이드 코드, 주황은 학습률
# 7f: 회색은 정답 평균과 SS_tot, 파랑은 최소제곱 직선, 빨강은 잔차, 보라는 Ridge, 주황은 Lasso
# 7g: 보라는 쌓인 history 행, 노랑은 방금 붙인 행, 파랑은 회귀 직선, 초록은 학습 데이터를 쓰는 줄, 주황은 테스트 데이터를
#     쓰는 줄, 빨강은 zero_grad 를 둘 수 없는 자리
M = MINUS
SIZES = {"font.size": 20, "axes.titlesize": 20, "axes.labelsize": 19, "xtick.labelsize": 17, "ytick.labelsize": 17,
         "axes.linewidth": 1.2, "axes.edgecolor": "#9ca3af"}


def sup(t):
    """그림 글의 ² 를 mathtext 위첨자로. 나눔고딕의 ² 는 작아서 도(°)처럼 보임."""
    if "²" not in t:
        return t
    # mathtext 가 섞인 글은 나눔고딕에 없는 글자를 대체 글꼴로 찾지 못해서 그 글자도 mathtext 로 씀
    for a, b in (("²", "$^{2}$"), (MINUS, "$-$"), ("∞", r"$\infty$"), ("≤", r"$\leq$"), ("Σ", r"$\Sigma$"),
                 ("÷", r"$\div$"), ("×", r"$\times$"), ("λ", r"$\lambda$")):
        t = t.replace(a, b)
    return t


def num(v, nd=4):
    """그림에 찍는 숫자. 빼기표는 U+2212, 끝의 0 은 지움."""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"
    return ("0" if s in ("-0", "0") else s).replace("-", M)


def fx(v, nd):
    """소수 nd 자리 고정. 빼기표는 U+2212."""
    return f"{v:.{nd}f}".replace("-", M)


def lst(vals, nd=4):
    return "[" + ", ".join(num(v, nd) for v in vals) + "]"


def new(h=600):
    plt = setup()
    plt.rcParams.update(SIZES)
    return plt, plt.figure(figsize=(11.2, h / 100.0), dpi=100)


def image(fig):
    from PIL import Image
    import matplotlib.pyplot as plt
    fig.canvas.draw()
    data = np.asarray(fig.canvas.buffer_rgba())
    img = Image.fromarray(data[..., :3].copy())
    plt.close(fig)
    return img


def tidy(ax, grid=True):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if grid:
        ax.grid(True, color=GRID, lw=1.0, zorder=0)
        ax.set_axisbelow(True)


def minus_ticks(ax, axis="both"):
    """눈금 글자의 빼기를 U+2212 로."""
    import matplotlib.ticker as mt
    fmt = mt.FuncFormatter(lambda v, _: num(v, 2))
    if axis in ("x", "both"):
        ax.xaxis.set_major_formatter(fmt)
    if axis in ("y", "both"):
        ax.yaxis.set_major_formatter(fmt)


def note(target, px, py, text, color=INK, size=18, bg=NOTE, ha="left", va="center", weight="normal", family=None,
         transform=None, ec=None):
    kw = dict(color=color, fontsize=size, ha=ha, va=va, weight=weight, zorder=12, linespacing=1.35)
    if family:
        kw["family"] = family
    if bg:
        kw["bbox"] = dict(boxstyle="round,pad=0.3", fc=bg, ec=ec or bg, lw=1.4)
    if transform is not None:
        kw["transform"] = transform
    return target.text(px, py, sup(text), **kw)


def head(fig, text, size=21, y=0.955, x=0.015, color=INK):
    fig.text(x, y, sup(text), fontsize=size, color=color, va="center", ha="left", weight="bold")


def board(h=500):
    plt, fig = new(h)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, h / 100.0)
    ax.axis("off")
    return plt, fig, ax


def rbox(ax, x0, y0, w, h, edge, fill="white", lw=2.2, ls="-", z=2):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0.04", fc=fill, ec=edge, lw=lw, ls=ls, zorder=z))


def cell(ax, x0, y0, w, h, text, edge=GRAY, fill="white", color=INK, size=18, weight="normal", family=None, lw=1.6):
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((x0, y0), w, h, fc=fill, ec=edge, lw=lw, zorder=3))
    kw = dict(ha="center", va="center", fontsize=size, color=color, weight=weight, zorder=4)
    if family:
        kw["family"] = family
    ax.text(x0 + w / 2, y0 + h / 2, sup(text), **kw)


def arrow(ax, x0, y0, x1, y1, color=MUTED, lw=2.2, ms=18):
    ax.annotate("", (x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=ms),
                zorder=5)


def card(ax, x0, y0, w, h, title, lines, edge, ink=INK, fill="white", size=17, title_size=20, code_lines=()):
    rbox(ax, x0, y0, w, h, edge, fill)
    ax.text(x0 + 0.18, y0 + h - 0.32, sup(title), ha="left", va="center", fontsize=title_size, weight="bold", color=ink,
            zorder=3)
    yy = y0 + h - 0.85
    for k, text in enumerate(lines):
        kw = dict(ha="left", va="center", fontsize=size, color=INK, zorder=3)
        if k in code_lines:
            kw["family"] = CODE
        ax.text(x0 + 0.22, yy, sup(text), **kw)
        yy -= 0.5


def memo(specs, foot):
    """외울 것 그림. specs 는 줄마다 [(x0, w, title, lines, edge, ink, code_lines)]. foot 은 맨 아래 회색 바탕 한 줄."""
    heights = [0.75 + 0.5 * max(len(c[3]) for c in row) for row in specs]
    total = sum(heights) + 0.25 * (len(specs) - 1) + 1.15
    h = int(round(total * 100))
    assert h <= 600, h
    plt, fig, ax = board(h)
    top = total - 0.15
    for row, rh in zip(specs, heights):
        for x0, w, title, lines, edge, ink, code in row:
            card(ax, x0, top - rh, w, rh, title, lines, edge, ink=ink, code_lines=code)
        top -= rh + 0.25
    ax.text(5.6, 0.45, sup(foot), ha="center", va="center", fontsize=16, color=INK,
            bbox=dict(boxstyle="round,pad=0.3", fc=NOTE, ec="none"))
    return image(fig)


# 공용 숫자

# 7a: 노트북 01 [14]·[18]·[21]
XA = np.arange(-2.0, 2.1, 1.0)
assert XA.tolist() == [-2, -1, 0, 1, 2] and (2 * XA + 1).tolist() == [-3, -1, 1, 3, 5]
X4 = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], float)
W3 = np.array([[1, 1], [2, 2], [3, 3]], float)
Y3 = X4 @ W3.T + 2
assert (X4 @ np.ones(2) + 2).tolist() == [2, 3, 3, 4]
assert Y3.tolist() == [[2, 2, 2], [3, 4, 5], [3, 4, 5], [4, 6, 8]]
# 7b: 4차시 다섯 사람(평균 뺀 값)
HT = np.array([166.0, 176, 171, 173, 169])
WT = np.array([58.7, 75.7, 62.1, 70.4, 60.1])
XP = HT - HT.mean()
YP = WT - WT.mean()
W_OLS = (XP * YP).sum() / (XP ** 2).sum()
assert XP.tolist() == [-5, 5, 0, 2, -2] and np.allclose(YP, [-6.7, 10.3, -3.3, 5.0, -5.3])
assert abs((XP * YP).sum() - 105.6) < 1e-9 and (XP ** 2).sum() == 58 and fx(W_OLS, 4) == "1.8207"
B_RAW = WT.mean() - W_OLS * HT.mean()
assert fx(B_RAW, 2) == M + "245.94"


def sse(w, b=0.0):
    return float(((YP - (w * XP + b)) ** 2).sum())


assert abs(sse(1, 1) - 66.76) < 1e-9 and fx(sse(W_OLS), 2) == "22.70" and abs(sse(1, 1) / 5 - 13.352) < 1e-9
WS = [0.6, 1.0, 1.4, W_OLS, 2.2, 2.6]
assert [fx(sse(w), 2) for w in WS] == ["109.12", "61.76", "32.96", "22.70", "31.04", "57.92"]
# 7c: 이 단원에서 정한 자료
XC = np.array([-2.0, -1, 0, 1, 2])
YC = np.array([4.3, 1.5, 0.2, 0.9, 4.1])
T1 = np.linalg.lstsq(np.column_stack([np.ones(5), XC]), YC, rcond=None)[0]
T2 = np.linalg.lstsq(np.column_stack([np.ones(5), XC, XC ** 2]), YC, rcond=None)[0]
assert np.allclose(T1, [2.2, -0.1]) and np.allclose(T2, [0.2, -0.1, 1.0])
R1 = YC - (T1[0] + T1[1] * XC)
R2 = YC - (T2[0] + T2[1] * XC + T2[2] * XC ** 2)
assert np.allclose(R1, [1.9, -0.8, -2.0, -1.2, 2.1]) and abs((R1 ** 2).sum() - 14.1) < 1e-9
assert np.allclose(R2, [-0.1, 0.2, 0, -0.2, 0.1]) and abs((R2 ** 2).sum() - 0.1) < 1e-9
POLYS = {0: [2.0], 1: [0.8, 1.0], 2: [-1.5, 0, 0.6], 3: [0, -2.4, 0, 0.6], 4: [1.6, 0, -2.6, 0, 0.5],
         5: [0, 3.2, 0, -2.8, 0, 0.45]}


def extrema(deg):
    p = np.polynomial.Polynomial(POLYS[deg])
    if deg < 2:
        return []
    roots = p.deriv().roots()
    return sorted(float(z.real) for z in np.atleast_1d(roots) if abs(z.imag) < 1e-9)


assert [len(extrema(d)) for d in range(6)] == [0, 0, 1, 2, 3, 4]
# 7d: Net(1, 1) 처음 값 1, ones(100, 1), zeros(100, 1)
assert (1 * 1 + 1) == 2 and (2 - 0) ** 2 == 4 and 2 * 2 * 1 == 4
# 7e-4: y = w x, w* = 2
XA_IN, XB_IN = [5, 6, 7], [10, 13, 16]


def steps_lr(xs, lr, n=4):
    m2 = Fraction(sum(v * v for v in xs), len(xs))
    r = 1 - 2 * Fraction(lr) * m2
    w = Fraction(1)
    out = [w]
    for _ in range(n):
        w = 2 + (w - 2) * r
        out.append(w)
    return out, r, m2


WA, RA, MA = steps_lr(XA_IN, Fraction(1, 100))
WB, RB, MB = steps_lr(XB_IN, Fraction(1, 100))
WC, RC, _ = steps_lr(XB_IN, Fraction(1, 1000))
assert [fx(float(v), 4) for v in WA[1:4]] == ["1.7333", "1.9289", "1.9810"] and RA == Fraction(4, 15)
assert [float(v) for v in WB[1:4]] == [4.5, -4.25, 17.625] and RB == Fraction(-5, 2) and MB == 175
assert [fx(float(v), 4) for v in WC[1:4]] == ["1.3500", "1.5775", "1.7254"] and RC == Fraction(13, 20)
assert fx(float((WB[3] - 2) ** 2 * MB), 1) == "42724.6" and fx(float(MA), 2) == "36.67"
# 7f
SST = float((YP ** 2).sum())
assert fx(SST, 2) == "214.96" and fx(1 - sse(W_OLS) / SST, 4) == "0.8944"


def ridge_w(lam):
    return 0.3 / (1 + lam)


def lasso_w(lam):
    return max(0.0, 0.3 - lam / 2)


LAMS = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
assert [fx(ridge_w(v), 4) for v in LAMS] == ["0.3000", "0.2500", "0.2143", "0.1875", "0.1667", "0.1500"]
assert [fx(lasso_w(v), 4) for v in LAMS] == ["0.3000", "0.2000", "0.1000", "0.0000", "0.0000", "0.0000"]
# 7g
assert [e for e in range(5000) if e % 1000 == 0] == [0, 1000, 2000, 3000, 4000]
assert fx(W_OLS * (166 - 171) + 65.4, 2) == "56.30" and fx(W_OLS * (176 - 171) + 65.4, 2) == "74.50"


def boston_run(epochs, half=True, every=50):
    """보스턴 RM 단순 회귀를 SGD lr 0.01, w = b = 1 에서 학습. (기록 [(에폭, 손실)], 끝 손실)."""
    data = np.load(BOSTON)
    x, y = data["rm"].astype(np.float64), data["y"].astype(np.float64)
    w = b = 1.0
    rec = []
    s = 0.5 if half else 1.0
    for ep in range(epochs):
        e = w * x + b - y
        if ep % every == 0:
            rec.append((ep, s * float((e ** 2).mean())))
        gw, gb = s * float((2 * e * x).mean()), s * float((2 * e).mean())
        w -= 0.01 * gw
        b -= 0.01 * gb
    e = w * x + b - y
    return rec, s * float((e ** 2).mean())


# 7a 회귀와 nn.Linear

@figure("7a-1", 560, 280)
def names_7a():
    """이름표: x [5, 1] → nn.Linear(1, 1)(weight 2, bias 1) → y [5, 1] 과 직선 y = 2x + 1 위 다섯 점."""
    plt, fig = new(560)
    ax = fig.add_axes([0, 0, 0.42, 1])
    ax.set_xlim(0, 4.7)
    ax.set_ylim(0, 5.6)
    ax.axis("off")
    rbox(ax, 0.5, 4.3, 3.6, 0.9, BLUE, BLUE_L)
    ax.text(2.3, 4.75, "입력 x  [5, 1]", ha="center", va="center", fontsize=19, color=BLUE, weight="bold", zorder=4)
    rbox(ax, 0.5, 2.15, 3.6, 1.4, PURPLE, PURPLE_L)
    ax.text(2.3, 3.15, "nn.Linear(1, 1)", ha="center", va="center", fontsize=19, family=CODE, color=INK, zorder=4)
    ax.text(2.3, 2.55, "weight 2,  bias 1", ha="center", va="center", fontsize=18, color=PURPLE, weight="bold", zorder=4)
    rbox(ax, 0.5, 0.45, 3.6, 0.9, GREEN, GREEN_L)
    ax.text(2.3, 0.9, "출력 y  [5, 1]", ha="center", va="center", fontsize=19, color=GREEN, weight="bold", zorder=4)
    arrow(ax, 2.3, 4.25, 2.3, 3.62)
    arrow(ax, 2.3, 2.08, 2.3, 1.42)
    ax2 = fig.add_axes([0.5, 0.15, 0.46, 0.75])
    tidy(ax2)
    ax2.set_xlim(-2.6, 2.6)
    ax2.set_ylim(-4.2, 6.2)
    ax2.set_xticks([-2, -1, 0, 1, 2])
    ax2.set_yticks([-3, -1, 1, 3, 5])
    minus_ticks(ax2)
    xx = np.linspace(-2.5, 2.5, 50)
    ax2.plot(xx, 2 * xx + 1, color=PURPLE, lw=2.4, zorder=3)
    ax2.scatter(XA, 2 * XA + 1, s=110, color=GREEN, zorder=5)
    ax2.scatter(XA, np.full(5, -4.2), s=80, color=BLUE, zorder=6, clip_on=False)
    ax2.set_xlabel("입력 x", color=BLUE)
    ax2.set_ylabel("출력 y", color=GREEN)
    ax2.plot([0, 1, 1], [1, 1, 3], color=PURPLE, lw=1.8, ls="--", zorder=4)
    note(ax2, 1.12, 2.0, "weight 2", color=PURPLE, size=16, bg="white")
    note(ax2, 0.15, 0.25, "bias 1", color=PURPLE, size=16, bg="white")
    ax2.scatter([0], [1], s=120, facecolor="white", edgecolor=PURPLE, lw=2.4, zorder=6)
    note(ax2, -2.45, 5.2, "y = 2x + 1", color=PURPLE, size=18, bg="white")
    return image(fig)


def mat(ax, x0, y0, vals, cw, ch, edge, fill, color=INK, hl_rows=(), hl_cols=(), hl_cells=(), size=18, blank=None):
    """값 표. vals 는 2차원 목록, (x0, y0) 은 왼쪽 위. blank 는 비워 둘 칸의 (i, j) 집합."""
    for i, rowv in enumerate(vals):
        for j, v in enumerate(rowv):
            f = HL if (i in hl_rows or j in hl_cols or (i, j) in hl_cells) else fill
            text = "" if blank and (i, j) in blank else (num(v, 2) if isinstance(v, (int, float)) else v)
            cell(ax, x0 + j * cw, y0 - (i + 1) * ch, cw, ch, text, edge=edge, fill=f, color=color, size=size)


@figure("7a-2", 560, 300)
def linear23():
    """nn.Linear(2, 3) 이 출력 [4, 3] 을 열마다 채우는 순서. 행 1·2·3, bias 2(노트북 01 [21])."""
    frames, ms = [], [2000, 2400, 2400, 2200, 2500]
    for k in range(5):
        plt, fig, ax = board(600)
        head(fig, ["nn.Linear(2, 3): 입력 [4, 2] → 출력 [4, 3]", "출력 0번 열 = weight 0번 행 · 입력 + bias",
                   "출력 1번 열 = weight 1번 행 · 입력 + bias", "출력 2번 열 = weight 2번 행 · 입력 + bias",
                   "출력 [4, 3] 이 다 찼습니다"][k], size=20)
        ax.text(1.3, 5.05, "입력 x", ha="center", fontsize=19, color=BLUE, weight="bold")
        mat(ax, 0.5, 4.8, X4.astype(int).tolist(), 0.8, 0.62, BLUE, BLUE_L, hl_rows=(1,) if k in (1, 2) else ())
        ax.text(4.3, 5.05, "weight [3, 2]", ha="center", fontsize=19, color=PURPLE, weight="bold")
        mat(ax, 3.5, 4.8, W3.astype(int).tolist(), 0.8, 0.62, PURPLE, PURPLE_L,
            hl_rows=(k - 1,) if 1 <= k <= 3 else ())
        ax.text(6.0, 5.05, "bias", ha="center", fontsize=19, color=PURPLE, weight="bold")
        mat(ax, 5.6, 4.8, [[2], [2], [2]], 0.8, 0.62, PURPLE, PURPLE_L, hl_rows=(k - 1,) if 1 <= k <= 3 else ())
        ax.text(9.2, 5.05, "출력 y [4, 3]", ha="center", fontsize=19, color=GREEN, weight="bold")
        filled = {j for j in range(3) if j < k} if k < 4 else {0, 1, 2}
        blank = {(i, j) for i in range(4) for j in range(3) if j not in filled}
        hl_cells = {(1, k - 1)} if 1 <= k <= 2 else ({(i, 2) for i in range(4)} if k == 3 else set())
        mat(ax, 8.0, 4.8, Y3.astype(int).tolist(), 0.8, 0.62, GREEN, GREEN_L, hl_cells=hl_cells, blank=blank)
        if k in (1, 2):
            wr = W3[k - 1]
            val = wr @ X4[1] + 2
            assert val == [3, 4][k - 1]
            note(ax, 5.6, 1.3, "입력 [0, 1]:  %s × 0 + %s × 1 + 2 = %s" % (num(wr[0]), num(wr[1]), num(val)), size=20,
                 ha="center")
        elif k == 3:
            note(ax, 5.6, 1.3, "weight 2번 행 [3, 3] → 출력 2번 열 [2, 5, 5, 8]", size=20, ha="center")
        elif k == 4:
            note(ax, 5.6, 1.3, "weight 의 행 하나가 출력 하나:  y = xWᵀ + b", size=20, ha="center")
        else:
            note(ax, 5.6, 1.3, "weight 는 (출력 수, 입력 수) = [3, 2]", size=20, ha="center")
        frames.append(image(fig))
    return frames, ms


@figure("7a-3", 560, 260)
def params23():
    """nn.Linear(2, 3) 의 weight 3행 2열과 bias, constant_ 로 1번 행을 2 로 채움."""
    plt, fig, ax = board(520)
    ax.text(0.6, 4.75, "weight", fontsize=20, color=PURPLE, weight="bold", va="center")
    for j, name in enumerate(["입력 0", "입력 1"]):
        ax.text(2.35 + j * 1.1, 4.25, name, ha="center", fontsize=16, color=MUTED, va="center")
    for i in range(3):
        ax.text(1.1, 3.62 - i * 0.75, "출력 %d" % i, ha="center", fontsize=16, color=MUTED, va="center")
    mat(ax, 1.8, 4.0, W3.astype(int).tolist(), 1.1, 0.75, PURPLE, PURPLE_L, hl_rows=(1,), size=19)
    ax.text(4.65, 4.25, "bias", ha="center", fontsize=16, color=PURPLE, va="center", weight="bold")
    mat(ax, 4.2, 4.0, [[2], [2], [2]], 0.9, 0.75, PURPLE, PURPLE_L, size=19)
    ax.text(3.0, 1.2, "nn.init.constant_(l3.weight[1, :], 2.0)", ha="center", fontsize=16, family=CODE, color=INK,
            bbox=dict(boxstyle="round,pad=0.3", fc=HL, ec="none"))
    lines = [("requires_grad=True", True), ("학습할 때 기울기를 받음", False), ("bias=True (기본값)", True),
             ("파라미터 수", False), ("3 × 2 + 3 = 9", False)]
    yy = 4.4
    for text, code in lines:
        ax.text(6.3, yy, text, fontsize=18, color=INK, family=CODE if code else None, va="center")
        yy -= 0.72
    assert 3 * 2 + 3 == 9
    return image(fig)


@figure("7a-4", 560, 300)
def memo_7a():
    return memo([[(0.3, 3.35, "회귀", ["크기가 이어지는 수", "단순 회귀: 특징 하나", "다중 회귀: 둘 이상"], GRAY, INK, ()),
                  (3.85, 3.4, "nn.Linear(1, 1)", ["constant_: w 2, b 1", "view(" + M + "1, 1)", "[5] → [5, 1]",
                                                  "[" + M + "3, " + M + "1, 1, 3, 5]"], PURPLE, PURPLE, ()),
                  (7.45, 3.45, "nn.Linear(2, 3)", ["weight [3, 2]", "행 하나 = 출력 하나", "y = xWᵀ + b",
                                                   "bias=True 기본값"], PURPLE, PURPLE, ())]],
                "weight 모양은 (출력 수, 입력 수). 입력의 마지막 축이 입력 수와 같아야 함")


# 7b 최소제곱법

def people_axes(fig, rect):
    ax = fig.add_axes(rect)
    tidy(ax)
    ax.set_xlim(-6.5, 6.5)
    ax.set_ylim(-14, 14)
    ax.set_xticks([-5, 0, 5])
    ax.set_yticks([-10, -5, 0, 5, 10])
    minus_ticks(ax)
    ax.set_xlabel("X (평균을 뺀 신장)")
    ax.set_ylabel("Y (평균을 뺀 체중)")
    return ax


@figure("7b-1", 560, 300)
def sse_sweep():
    """B = 0 으로 두고 W 를 0.6 → 2.6 으로 바꾸며 잔차와 잔차 제곱합. 마지막 장은 W 에 따른 잔차 제곱합 곡선."""
    frames = []
    ms = [2000, 2200, 2200, 1800, 2200, 2200, 2500]
    ww = np.linspace(0.45, 2.75, 100)
    curve = [sse(w) for w in ww]
    plan = [None, 0.6, 1.0, 1.4, W_OLS, 2.6, W_OLS]  # 장마다 왼쪽에 그릴 직선
    upto = [0, 1, 2, 3, 4, 6, 6]  # 오른쪽에 찍힌 점 수
    heads = ["다섯 사람과 잔차 제곱합 자리", "W = 0.6   잔차 제곱합 109.12", "W = 1   잔차 제곱합 61.76",
             "W = 1.4   잔차 제곱합 32.96", "W = 1.8207   잔차 제곱합 22.70", "W = 2.2 → 31.04,  W = 2.6 → 57.92",
             "잔차 제곱합이 가장 작은 곳은 W = 1.8207"]
    for k in range(7):
        plt, fig = new(600)
        ax = people_axes(fig, [0.09, 0.14, 0.4, 0.74])
        ax2 = fig.add_axes([0.6, 0.14, 0.37, 0.74])
        tidy(ax2)
        ax2.set_xlim(0.4, 2.8)
        ax2.set_ylim(0, 125)
        ax2.set_xlabel("W")
        ax2.set_ylabel("잔차 제곱합")
        ax.scatter(XP, YP, s=80, color=INK, zorder=6)
        w = plan[k]
        if w is not None:
            xx = np.linspace(-6.5, 6.5, 2)
            ax.plot(xx, w * xx, color=BLUE, lw=2.6, zorder=4)
            for xv, yv in zip(XP, YP):
                ax.plot([xv, xv], [yv, w * xv], color=RED, lw=2.4, zorder=5)
        head(fig, heads[k], size=19, y=0.95)
        if k == 6:
            ax2.plot(ww, curve, color=RED, lw=2.4, zorder=3)
            note(ax2, W_OLS, 45, "W = 1.8207\n22.70", color=RED, size=16, bg="white", ha="center")
        for wv in WS[:upto[k]]:
            ax2.scatter([wv], [sse(wv)], s=70, color=RED, zorder=5)
        frames.append(image(fig))
    return frames, ms


@figure("7b-2", 560, 300)
def gd_vs_ols():
    """경사하강법 500번(W 1.8207, B 0.3675)과 식(W 1.8207, B 0)."""
    plt, fig = new(600)
    ax = people_axes(fig, [0.09, 0.14, 0.4, 0.78])
    xx = np.linspace(-6.5, 6.5, 2)
    ax.plot(xx, W_OLS * xx + 0.3675, color=GRAY, lw=2.6, ls="--", zorder=3)
    ax.plot(xx, W_OLS * xx, color=BLUE, lw=2.6, zorder=4)
    ax.scatter(XP, YP, s=80, color=INK, zorder=6)
    mse_gd = float(((YP - (1.820683 * XP + 0.3675114)) ** 2).mean())
    assert fx(mse_gd, 4) == "4.6741" and fx(sse(W_OLS) / 5, 3) == "4.539"
    bx = fig.add_axes([0.52, 0, 0.48, 1])
    bx.set_xlim(0, 5.4)
    bx.set_ylim(0, 6)
    bx.axis("off")
    rbox(bx, 0.15, 3.25, 5.0, 2.45, GRAY, "white", ls="--")
    bx.text(0.35, 5.3, "경사하강법 500번", fontsize=19, weight="bold", color=MUTED, va="center")
    for k, t in enumerate(["W 1.8207,  B 0.3675", "손실 4.6741"]):
        bx.text(0.4, 4.6 - k * 0.6, t, fontsize=18, color=INK, va="center")
    rbox(bx, 0.15, 0.35, 5.0, 2.55, BLUE, BLUE_L)
    bx.text(0.35, 2.5, "식으로 한 번에", fontsize=19, weight="bold", color=BLUE, va="center")
    for k, t in enumerate(["W = ΣXY ÷ ΣX² = 105.6 ÷ 58", "= 1.8207,  B = 0", "손실 4.539"]):
        bx.text(0.4, 1.85 - k * 0.55, sup(t), fontsize=17, color=INK, va="center")
    return image(fig)


@figure("7b-3", 560, 280)
def dummy_matrix():
    """5행 2열 [신장, 1] 과 (w, b) 의 곱. 정규방정식 결과 w 1.8207, b −245.94."""
    Xt = np.column_stack([HT, np.ones(5)])
    sol = np.linalg.solve(Xt.T @ Xt, Xt.T @ WT)
    assert fx(sol[0], 4) == "1.8207" and fx(sol[1], 2) == M + "245.94"
    preds = Xt @ sol
    plt, fig, ax = board(560)
    ax.text(1.65, 5.15, "X  (5행 2열)", ha="center", fontsize=19, weight="bold", color=INK)
    for i, h in enumerate(HT):
        cell(ax, 0.6, 4.65 - (i + 1) * 0.66, 1.3, 0.66, num(h, 0), edge=BLUE, fill=BLUE_L, size=18)
        cell(ax, 1.9, 4.65 - (i + 1) * 0.66, 0.9, 0.66, "1", edge=PURPLE, fill=PURPLE_L, size=18, color=PURPLE,
             weight="bold")
    ax.text(1.25, 4.85, "신장", ha="center", fontsize=16, color=BLUE)
    ax.text(2.35, 4.85, "1 열", ha="center", fontsize=16, color=PURPLE)
    ax.text(3.3, 3.0, "×", ha="center", va="center", fontsize=28, color=INK)
    cell(ax, 3.8, 3.33, 1.0, 0.66, "w", edge=BLUE, fill="white", size=19, color=BLUE)
    cell(ax, 3.8, 2.67, 1.0, 0.66, "b", edge=PURPLE, fill="white", size=19, color=PURPLE, weight="bold")
    ax.text(5.3, 3.0, "=", ha="center", va="center", fontsize=28, color=INK)
    ax.text(6.9, 5.15, "예측  w × 신장 + b × 1", ha="center", fontsize=17, color=INK)
    for i, p in enumerate(preds):
        cell(ax, 5.8, 4.65 - (i + 1) * 0.66, 2.2, 0.66, fx(p, 2), edge=GRAY, fill="white", size=17)
    note(ax, 9.65, 3.35, "역행렬 식\n$(X^{T}X)^{-1}X^{T}y$", size=17, ha="center")
    note(ax, 9.65, 1.9, "w = 1.8207\nb = " + M + "245.94", size=17, ha="center")
    return image(fig)


@figure("7b-4", 560, 300)
def memo_7b():
    return memo([[(0.3, 3.4, "잔차", ["정답 " + M + " 예측", "제곱해 더한 값이", "잔차 제곱합", "처음 직선 66.76"], RED, RED, ()),
                  (3.9, 3.7, "식으로 구한 직선", ["W = ΣXY ÷ ΣX²", "105.6 ÷ 58 = 1.8207", "B = 0",
                                                  "b = y 평균 " + M + " w × x 평균"], BLUE, BLUE, ()),
                  (7.8, 3.1, "두 길", ["경사하강법", "1 열을 붙인", "정규방정식", "w 1.8207, b " + M + "245.94"],
                   PURPLE, PURPLE, ())]],
                "요약본 기호 y = β0 + β1x + ε: β1 은 직선의 기울기, β0 는 절편, ε 은 오차항")


# 7c 다항 회귀

def poly_axes(fig, rect):
    ax = fig.add_axes(rect)
    tidy(ax)
    ax.set_xlim(-2.6, 2.6)
    ax.set_ylim(-0.6, 5.2)
    ax.set_xticks([-2, -1, 0, 1, 2])
    minus_ticks(ax)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    return ax


@figure("7c-1", 560, 300)
def line_vs_quad():
    """같은 다섯 점에 직선(SSE 14.1)과 이차식(SSE 0.1)."""
    frames, ms = [], [2000, 2400, 2200, 2400, 2500]
    xx = np.linspace(-2.5, 2.5, 120)
    for k in range(5):
        plt, fig = new(600)
        ax = poly_axes(fig, [0.08, 0.14, 0.5, 0.74])
        ax.scatter(XC, YC, s=90, color=INK, zorder=6)
        if k in (1, 4):
            ax.plot(xx, T1[0] + T1[1] * xx, color=BLUE, lw=2.6, zorder=3)
        if k == 1:
            for xv, yv, rv in zip(XC, YC, R1):
                ax.plot([xv, xv], [yv, yv - rv], color=RED, lw=2.4, zorder=5)
        if k in (3, 4):
            ax.plot(xx, T2[0] + T2[1] * xx + T2[2] * xx ** 2, color=GREEN, lw=2.8, zorder=4)
        if k == 3:
            for xv, yv, rv in zip(XC, YC, R2):
                ax.plot([xv, xv], [yv, yv - rv], color=RED, lw=3.0, zorder=5)
        title = ["가운데가 낮고 양쪽이 높은 다섯 점", "직선 y = 2.2 " + M + " 0.1x   잔차 제곱합 14.1",
                 "x² 을 새 열로 붙입니다", "이차식 y = 0.2 " + M + " 0.1x + x²   잔차 제곱합 0.1",
                 "직선 14.1,  이차식 0.1"][k]
        head(fig, title, size=19, y=0.95)
        bx = fig.add_axes([0.62, 0.1, 0.36, 0.78])
        bx.set_xlim(0, 3.6)
        bx.set_ylim(0, 4.2)
        bx.axis("off")
        cols = ["x", "x²", "y"] if k >= 2 else ["x", "y"]
        cw = 1.1 if k >= 2 else 1.5
        for j, name in enumerate(cols):
            bx.text(0.2 + cw * (j + 0.5), 3.95, sup(name), ha="center", fontsize=18, weight="bold",
                    color=GREEN if name == "x²" else INK)
        for i in range(5):
            vals = [XC[i], XC[i] ** 2, YC[i]] if k >= 2 else [XC[i], YC[i]]
            for j, v in enumerate(vals):
                fill = GREEN_L if (k >= 2 and j == 1) else "white"
                cell(bx, 0.2 + cw * j, 3.55 - (i + 1) * 0.62, cw, 0.62, num(v, 1), edge=GRAY, fill=fill, size=17)
        assert (XC ** 2).tolist() == [4, 1, 0, 1, 4]
        frames.append(image(fig))
    return frames, ms


@figure("7c-2", 560, 300)
def degrees():
    """차수 0~5 다항식과 극값. 마지막 장은 여섯 곡선을 작게 모음."""
    frames, ms = [], [2000, 2000, 2000, 2000, 2000, 2000, 2500]
    xx = np.linspace(-2.4, 2.4, 200)
    words = ["극값 0개", "극값 0개", "극값 1개", "극값 2개", "극값 3개", "극값 4개"]
    for k in range(6):
        plt, fig = new(600)
        ax = fig.add_axes([0.1, 0.14, 0.86, 0.72])
        tidy(ax)
        ax.set_xlim(-2.6, 2.6)
        ax.set_ylim(-5, 5)
        ax.set_xticks([-2, -1, 0, 1, 2])
        ax.set_yticks([-4, -2, 0, 2, 4])
        minus_ticks(ax)
        for d in range(k):
            ax.plot(xx, np.polynomial.Polynomial(POLYS[d])(xx), color=FAINT, lw=1.8, zorder=2)
        p = np.polynomial.Polynomial(POLYS[k])
        ax.plot(xx, p(xx), color=GREEN, lw=3.0, zorder=4)
        ex = extrema(k)
        assert len(ex) == [0, 0, 1, 2, 3, 4][k]
        ax.scatter(ex, p(np.array(ex)), s=110, color=ORANGE, zorder=6)
        head(fig, "차수 %d:  %s" % (k, words[k]), size=21, y=0.94)
        frames.append(image(fig))
    plt, fig = new(600)
    head(fig, "차수 p 가 1 이상이면 극값은 많아야 p " + M + " 1개", size=20, y=0.95)
    for k in range(6):
        r, c = divmod(k, 3)
        ax = fig.add_axes([0.04 + c * 0.33, 0.5 - r * 0.44, 0.27, 0.34])
        ax.set_xlim(-2.6, 2.6)
        ax.set_ylim(-5, 5)
        ax.set_xticks([])
        ax.set_yticks([])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        p = np.polynomial.Polynomial(POLYS[k])
        ax.plot(xx, p(xx), color=GREEN, lw=2.4)
        ex = extrema(k)
        ax.scatter(ex, p(np.array(ex)), s=50, color=ORANGE, zorder=5)
        ax.set_title("차수 %d, %s" % (k, words[k]), fontsize=17, pad=4)
    frames.append(image(fig))
    return frames, ms


@figure("7c-3", 560, 260)
def param_linear():
    """파라미터에 대해 선형인 모델(정규방정식)과 아닌 모델(되풀이)."""
    plt, fig, ax = board(520)
    rbox(ax, 0.3, 0.45, 5.0, 4.4, PURPLE, PURPLE_L)
    ax.text(0.55, 4.45, "파라미터에 대해 선형", fontsize=20, weight="bold", color=PURPLE, va="center")
    for k, t in enumerate([r"$y = \theta_0 + \theta_1 x + \theta_2 x^2$", r"$= [1,\ x,\ x^2] \cdot (\theta_0, \theta_1, \theta_2)$",
                           "열에 파라미터를 곱해 더함",
                           "정규방정식으로 한 번에"]):
        ax.text(0.6, 3.7 - k * 0.72, t, fontsize=18, color=INK, va="center")
    rbox(ax, 5.9, 0.45, 5.0, 4.4, GRAY, "white")
    ax.text(6.15, 4.45, "파라미터에 대해 비선형", fontsize=20, weight="bold", color=MUTED, va="center")
    for k, t in enumerate([r"$y = e^{wx}$", r"$y = \sigma(wx + b)$", "w 가 함수 안에 있음", "갱신을 되풀이해 줄임"]):
        ax.text(6.2, 3.7 - k * 0.72, t, fontsize=18, color=INK, va="center")
    return image(fig)


@figure("7c-4", 560, 300)
def memo_7c():
    return memo([[(0.3, 3.6, "다항 회귀", ["x² 를 열로 넣음", "nn.Linear(2, 1)", "직선 14.1", "이차식 0.1"], GREEN, GREEN,
                   (1,)),
                  (4.1, 3.5, "차수와 극값", ["p ≥ 1: 극값 ≤ p " + M + " 1", "짝수: 두 끝 같은 쪽", "홀수: 두 끝 반대쪽",
                                           "극값 넷, 반대쪽 → 5"], ORANGE, ORANGE, ()),
                  (7.8, 3.1, "파라미터 선형", ["정규방정식으로", "한 번에 풂", "e^(wx) 는", "되풀이"], PURPLE, PURPLE, ())]],
                "차수를 높이면 복잡한 모양을 나타내지만 과적합이 생기기 쉬움")


# 7d 모델 클래스와 손실

@figure("7d-1", 560, 300)
def class_names():
    """Net(n_input, n_output) 클래스와 named_parameters, print(net)."""
    plt, fig, ax = board(600)
    ax.text(0.35, 5.55, "class Net(nn.Module):", fontsize=15, family=CODE, color=INK, va="center")
    ax.text(6.4, 5.55, "__init__: 층을 만듦", fontsize=17, color=BLUE, weight="bold", ha="right", va="center")
    rbox(ax, 0.25, 2.55, 6.2, 2.7, BLUE, BLUE_L)
    rbox(ax, 0.25, 0.4, 6.2, 1.55, GREEN, GREEN_L)
    init = ["  def __init__(self, n_input, n_output):", "    super().__init__()",
            "    self.l1 = nn.Linear(n_input, n_output)", "    nn.init.constant_(self.l1.weight, 1.0)",
            "    nn.init.constant_(self.l1.bias, 1.0)"]
    for k, t in enumerate(init):
        ax.text(0.4, 4.95 - k * 0.5, t, fontsize=15, family=CODE, color=INK, va="center", zorder=4)
    ax.text(0.4, 1.55, "  def forward(self, x):", fontsize=15, family=CODE, color=INK, va="center", zorder=4)
    ax.text(0.4, 1.0, "    return self.l1(x)", fontsize=15, family=CODE, color=INK, va="center", zorder=4)
    ax.text(6.3, 1.0, "forward: 계산 순서", fontsize=17, color=GREEN, weight="bold", ha="right", va="center", zorder=4)
    ax.text(6.9, 5.4, "named_parameters()", fontsize=17, family=CODE, color=INK, va="center")
    ax.text(7.0, 4.8, "l1.weight  [[1.]]", fontsize=17, family=CODE, color=PURPLE, va="center", weight="bold")
    ax.text(7.0, 4.25, "l1.bias    [1.]", fontsize=17, family=CODE, color=PURPLE, va="center", weight="bold")
    ax.text(6.9, 3.4, "print(net)", fontsize=17, family=CODE, color=INK, va="center")
    ax.text(7.0, 2.85, "Net(", fontsize=15, family=CODE, color=INK, va="center")
    ax.text(7.2, 2.4, "(l1): Linear(1, 1)", fontsize=15, family=CODE, color=INK, va="center")
    ax.text(7.0, 1.95, ")", fontsize=15, family=CODE, color=INK, va="center")
    note(ax, 8.9, 1.0, "Net(1, 1) 의 파라미터 2개", size=16, ha="center")
    return image(fig)


@figure("7d-2", 560, 260)
def call_path():
    """net(inputs) → nn.Module.__call__ → forward → self.l1 → outputs."""
    frames, ms = [], [2000, 2400, 2000, 2200, 2500]
    boxes = [("net(inputs)", 0.2, INK, True), ("nn.Module\n__call__", 2.42, INK, False), ("forward(x)", 4.64, GREEN, True),
             ("self.l1(x)\n1 × 1 + 1 = 2", 6.86, GREEN, False), ("outputs\n[100, 1]\n모두 2", 9.08, INK, False)]
    tips = ["net 은 nn.Module 을 물려받은 인스턴스", "net 에 건 hook 이 있으면 __call__ 이 함께 실행",
            "__call__ 이 클래스에 적은 forward 를 부름", "forward 안의 층이 계산", "forward 를 직접 부르면 net 에 건 hook 을 건너뜀"]
    for k in range(5):
        plt, fig, ax = board(520)
        for j, (t, x0, col, code) in enumerate(boxes):
            fill = HL if j == k else ("white" if j > k else NOTE)
            rbox(ax, x0, 2.3, 1.92, 1.7, GREEN if col == GREEN else GRAY, fill)
            ax.text(x0 + 0.96, 3.15, t, ha="center", va="center", fontsize=15, family=CODE if code else None,
                    color=INK, zorder=4, linespacing=1.35)
            if j < 4:
                arrow(ax, x0 + 1.95, 3.15, x0 + 2.4, 3.15)
        rbox(ax, 2.6, 4.45, 1.55, 0.6, GRAY, "white", ls="--")
        ax.text(3.38, 4.75, "hook", ha="center", va="center", fontsize=16, color=MUTED, zorder=4)
        ax.plot([3.38, 3.38], [4.4, 4.05], color=GRAY, lw=1.6, ls="--", zorder=3)
        note(ax, 5.6, 1.2, tips[k], size=19, ha="center")
        frames.append(image(fig))
    return frames, ms


@figure("7d-3", 560, 280)
def half_loss():
    """bias 1, 입력 1, 정답 0 에서 weight w 에 따른 MSE (w + 1)² 과 그 절반. w = 1 의 접선 기울기 4, 2."""
    plt, fig = new(560)
    ax = fig.add_axes([0.1, 0.15, 0.6, 0.75])
    tidy(ax)
    ax.set_xlim(-3, 2)
    ax.set_ylim(-0.3, 9.5)
    ax.set_xticks([-3, -2, -1, 0, 1, 2])
    minus_ticks(ax)
    ax.set_xlabel("weight w")
    ax.set_ylabel("손실")
    ww = np.linspace(-3, 2, 200)
    L = (ww + 1) ** 2
    assert (1 + 1) ** 2 == 4 and 2 * (1 + 1) == 4
    ax.plot(ww, L, color=RED, lw=2.8, zorder=3)
    ax.plot(ww, L / 2, color=RED, lw=2.6, ls="--", zorder=3)
    for val, slope in ((4, 4), (2, 2)):
        t = np.linspace(0.3, 1.7, 2)
        ax.plot(t, val + slope * (t - 1), color=ORANGE, lw=2.2, zorder=4)
        ax.scatter([1], [val], s=90, color=INK, zorder=6)
    note(ax, 0.55, 3.9, "기울기 4", color=ORANGE, size=16, bg="white", ha="right")
    note(ax, 1.25, 1.2, "기울기 2", color=ORANGE, size=16, bg="white")
    ax.axvline(-1, color=GRAY, lw=1.4, ls=":", zorder=2)
    note(ax, -1, 8.6, "가장 작은 곳 w = " + M + "1", size=16, bg="white", ha="center")
    bx = fig.add_axes([0.73, 0.1, 0.26, 0.8])
    bx.axis("off")
    bx.set_xlim(0, 3)
    bx.set_ylim(0, 6)
    bx.text(0.1, 5.2, "MSE", fontsize=19, color=RED, weight="bold", va="center")
    bx.text(0.1, 4.6, "4, 기울기 4", fontsize=17, color=INK, va="center")
    bx.text(0.1, 3.5, "MSE ÷ 2", fontsize=19, color=RED, weight="bold", va="center")
    bx.text(0.1, 2.9, "2, 기울기 2", fontsize=17, color=INK, va="center")
    bx.text(0.1, 1.8, "w = 1 에서", fontsize=16, color=MUTED, va="center")
    return image(fig)


@figure("7d-4", 560, 300)
def memo_7d():
    return memo([[(0.3, 3.6, "__init__", ["n_input, n_output", "self.l1 = nn.Linear", "constant_ 로 1",
                                          "l1.weight, l1.bias"], BLUE, BLUE, ()),
                  (4.1, 3.45, "호출", ["net(inputs)", "→ __call__ → forward", "직접 forward 는 net 에", "건 hook 을 건너뜀"], GREEN,
                   GREEN, (0,)),
                  (7.75, 3.15, "손실", ["출력 2, 정답 0", "MSE 4, 기울기 4", "÷ 2: 2, 기울기 2", "가장 작은 곳 같음"], RED,
                   RED, ())]],
                "슬라이드 코드는 손실을 2.0 으로 나누고 노트북 01 은 나누지 않음")


# 7e 보스턴 집값

@figure("7e-1", 560, 300)
def broadcast():
    """출력 [3, 1] − 정답 [3] 이 [3, 3] 으로 늘어나 MSE 1.3333(바른 값 0)."""
    o = np.array([[1.0], [2.0], [3.0]])
    t = np.array([1.0, 2.0, 3.0])
    D = o - t
    assert D.shape == (3, 3) and D.tolist() == [[0, -1, -2], [1, 0, -1], [2, 1, 0]]
    assert abs((D ** 2).mean() - 4 / 3) < 1e-12 and (D ** 2).sum() == 12 and ((o[:, 0] - t) ** 2).mean() == 0
    frames, ms = [], [2200, 2400, 2400, 2400, 2500]
    heads = ["출력 [3, 1] 과 정답 [3]", "출력 " + M + " 정답: [3, 3] 으로 늘어남", "칸마다 뺀 값",
             "아홉 칸 제곱의 평균 12 ÷ 9 = 1.3333", "view((" + M + "1, 1)) 로 맞추면 손실 0"]
    for k in range(5):
        plt, fig, ax = board(600)
        head(fig, heads[k], size=20, y=0.95)
        if k < 4:
            ax.text(1.0, 4.95, "출력", ha="center", fontsize=18, color=BLUE, weight="bold")
            for i in range(3):
                cell(ax, 0.6, 4.6 - (i + 1) * 0.8, 0.8, 0.8, num(o[i, 0]), edge=BLUE, fill=BLUE_L, size=19)
            ax.text(4.6, 4.95, "정답", ha="center", fontsize=18, color=GREEN, weight="bold")
            for j in range(3):
                cell(ax, 3.4 + j * 0.8, 4.6 - 0.8, 0.8, 0.8, num(t[j]), edge=GREEN, fill=GREEN_L, size=19)
        if k >= 1 and k < 4:
            ax.text(8.3, 4.95, "출력 " + M + " 정답 [3, 3]", ha="center", fontsize=18, color=RED, weight="bold")
            for i in range(3):
                for j in range(3):
                    text = "" if k == 1 else num(D[i, j])
                    cell(ax, 7.1 + j * 0.8, 4.6 - (i + 1) * 0.8, 0.8, 0.8, text, edge=RED,
                         fill=RED_L if i != j else "white", size=18)
            if k == 1:
                note(ax, 3.4, 1.0, "출력은 열을 셋으로, 정답은 행을 셋으로 늘림", size=18)
            if k == 2:
                note(ax, 3.4, 1.0, "빨간 칸은 다른 데이터의 정답과 뺀 값", size=18)
            if k == 3:
                note(ax, 3.4, 1.0, "제곱: 0, 1, 4, 1, 0, 1, 4, 1, 0  →  합 12", size=18)
        if k == 4:
            ax.text(1.0, 4.95, "출력", ha="center", fontsize=18, color=BLUE, weight="bold")
            ax.text(2.6, 4.95, "정답", ha="center", fontsize=18, color=GREEN, weight="bold")
            ax.text(4.6, 4.95, "뺀 값", ha="center", fontsize=18, color=RED, weight="bold")
            for i in range(3):
                cell(ax, 0.6, 4.6 - (i + 1) * 0.8, 0.8, 0.8, num(o[i, 0]), edge=BLUE, fill=BLUE_L, size=19)
                cell(ax, 2.2, 4.6 - (i + 1) * 0.8, 0.8, 0.8, num(t[i]), edge=GREEN, fill=GREEN_L, size=19)
                cell(ax, 4.2, 4.6 - (i + 1) * 0.8, 0.8, 0.8, "0", edge=RED, fill="white", size=19)
            note(ax, 6.0, 3.2, "정답도 [3, 1]\n같은 자리끼리만 빼서\nMSE = 0", size=18)
        frames.append(image(fig))
    return frames, ms


@figure("7e-2", 560, 280)
def first_step_table():
    """노트북 01(손실 그대로)과 슬라이드(손실 ÷ 2)의 첫 손실·기울기·한 번 갱신."""
    L, gw, gb = 308.4499, -199.6421, -30.4963
    vals = [("첫 손실", L, L / 2, 2), ("weight 기울기", gw, gw / 2, 2), ("bias 기울기", gb, gb / 2, 2),
            ("갱신 뒤 weight", 1 - 0.01 * gw, 1 - 0.01 * gw / 2, 4), ("갱신 뒤 bias", 1 - 0.01 * gb, 1 - 0.01 * gb / 2, 4)]
    shown = [(fx(a, d), fx(b, d)) for _, a, b, d in vals]
    assert shown == [("308.45", "154.22"), (M + "199.64", M + "99.82"), (M + "30.50", M + "15.25"),
                     ("2.9964", "1.9982"), ("1.3050", "1.1525")]
    plt, fig, ax = board(560)
    cell(ax, 0.6, 4.6, 3.6, 0.7, "", edge="white")
    cell(ax, 4.2, 4.6, 3.1, 0.7, "노트북 01", edge=GRAY, fill=BAND, size=18, weight="bold")
    cell(ax, 7.3, 4.6, 3.3, 0.7, "슬라이드 (손실 ÷ 2)", edge=PURPLE, fill=PURPLE_L, size=18, weight="bold", color=PURPLE)
    for i, ((name, _, _, _), (a, b)) in enumerate(zip(vals, shown)):
        y0 = 4.6 - (i + 1) * 0.72
        cell(ax, 0.6, y0, 3.6, 0.72, name, edge=GRAY, size=18)
        cell(ax, 4.2, y0, 3.1, 0.72, a, edge=GRAY, size=19)
        cell(ax, 7.3, y0, 3.3, 0.72, b, edge=PURPLE, size=19, color=PURPLE)
    ax.text(5.6, 0.45, "학습률 0.01, 처음 weight 와 bias 는 1", ha="center", fontsize=17, color=INK,
            bbox=dict(boxstyle="round,pad=0.3", fc=NOTE, ec="none"))
    return image(fig)


@figure("7e-3", 560, 280)
def boston_curve():
    """보스턴 RM 을 SGD lr 0.01, 손실 ÷ 2 로 학습한 손실(0~5000, 5000~50000)."""
    rec, end5 = boston_run(5000, every=25)
    assert fx(rec[0][1], 2) == "154.22" and fx(end5, 2) == "24.21"
    rec2, end50 = boston_run(50000, every=500)
    _, end20 = boston_run(20000, every=20000)
    assert fx(end20, 2) == "21.87" and fx(end50, 2) == "21.80"
    plt, fig = new(560)
    ax = fig.add_axes([0.09, 0.15, 0.38, 0.72])
    tidy(ax)
    ax.plot([r[0] for r in rec], [r[1] for r in rec], color=RED, lw=2.6)
    ax.axhline(21.8003, color=GRAY, lw=1.6, ls="--")
    ax.set_xlim(0, 5000)
    ax.set_ylim(0, 165)
    ax.set_xticks([0, 2500, 5000])
    ax.set_xlabel("에폭")
    ax.set_ylabel("손실 ÷ 2")
    ax.scatter([5000], [end5], s=70, color=RED, zorder=5, clip_on=False)
    note(ax, 2600, 70, "5000 에폭\n24.21", color=RED, size=16, bg="white", ha="center")
    note(ax, 250, 150, "154.22", color=RED, size=16, bg="white")
    ax2 = fig.add_axes([0.58, 0.15, 0.38, 0.72])
    tidy(ax2)
    xs = [r[0] for r in rec2 if r[0] >= 5000]
    ys = [r[1] for r in rec2 if r[0] >= 5000]
    ax2.plot(xs, ys, color=RED, lw=2.6)
    ax2.axhline(21.8003, color=GRAY, lw=1.8, ls="--")
    ax2.set_xlim(5000, 50000)
    ax2.set_ylim(21.5, 24.6)
    ax2.set_xticks([5000, 20000, 50000])
    ax2.set_xticklabels(["5000", "20000", "50000"])
    ax2.set_xlabel("에폭(확대)")
    ax2.scatter([5000, 20000, 50000], [end5, end20, end50], s=70, color=RED, zorder=5, clip_on=False)
    note(ax2, 8000, 24.25, "24.21", color=RED, size=16, bg="white")
    note(ax2, 20500, 22.25, "21.87", color=RED, size=16, bg="white")
    note(ax2, 37000, 22.2, "21.80", color=RED, size=16, bg="white")
    note(ax2, 27500, 21.62, "최소제곱 직선 21.80", color=MUTED, size=15, bg="white", ha="center")
    head(fig, "슬라이드 26쪽 코드로 다시 계산한 손실", size=19, y=0.95)
    return image(fig)


@figure("7e-4", 560, 300)
def lr_inputs():
    """y = w x, 정답 w = 2. 입력 A [5, 6, 7] 과 B [10, 13, 16] 을 lr 0.01 로, B 를 lr 0.001 로.
    B 의 세로 눈금은 장마다 지금 손실이 들어가게 넓힘."""
    frames, ms = [], [2200, 2400, 2000, 2200, 2400, 2500]

    def panel(fig, rect, m2, path, title, ymax, xlim):
        ax = fig.add_axes(rect)
        tidy(ax)
        ax.set_xlim(*xlim)
        ax.set_ylim(-ymax * 0.03, ymax)
        minus_ticks(ax, "x")
        wgrid = np.linspace(xlim[0], xlim[1], 400)
        ax.plot(wgrid, (wgrid - 2) ** 2 * float(m2), color=RED, lw=2.4, zorder=3)
        pts = [float(v) for v in path]
        for p in pts[:-1]:
            ax.scatter([p], [(p - 2) ** 2 * float(m2)], s=55, color=FAINT, zorder=4)
        last = pts[-1]
        ax.scatter([last], [(last - 2) ** 2 * float(m2)], s=90, color=INK, zorder=6)
        ax.set_title(title, fontsize=17, loc="left", pad=6)
        ax.set_xlabel("w")
        return ax, last, (last - 2) ** 2 * float(m2)

    texts = ["처음 w = 1", "1번 갱신: A 1.7333, B 4.5", "2번 갱신: A 1.9289, B " + M + "4.25",
             "3번 갱신: A 1.981, B 17.625", "B 를 학습률 0.001 로 다시", "w " + M + " 2 가 갱신마다 몇 배인가"]
    ymax_b = [400, 1400, 9000, 52000]
    for k in range(6):
        plt, fig = new(600)
        head(fig, texts[k], size=19, y=0.955)
        if k <= 3:
            panel(fig, [0.07, 0.13, 0.4, 0.7], MA, WA[:k + 1], "입력 A [5, 6, 7], 학습률 0.01", 60, (0, 3))
            ax, last, loss = panel(fig, [0.57, 0.13, 0.4, 0.7], MB, WB[:k + 1], "입력 B [10, 13, 16], 학습률 0.01",
                                   ymax_b[k], (-6, 19))
            assert loss <= ymax_b[k]
            ax.ticklabel_format(axis="y", style="plain")
            text = "손실 " + "{:,.1f}".format(loss)
            if k in (1, 2):
                # 2번 장은 왼쪽 가지가 글 상자 왼끝을 지나서 글을 오른쪽으로 더 뗌
                note(ax, last + (2.0 if k == 2 else 1.0), loss * 0.85, text, size=15, bg="white", ha="left")
            elif k == 3:
                note(ax, -5.5, ymax_b[k] * 0.88, text, size=15, bg="white", ha="left")
        elif k == 4:
            panel(fig, [0.07, 0.13, 0.4, 0.7], MA, WA[:4], "입력 A [5, 6, 7], 학습률 0.01", 60, (0, 3))
            panel(fig, [0.57, 0.13, 0.4, 0.7], MB, WC[:4], "입력 B, 학습률 0.001", 200, (0, 3))
        else:
            bx = fig.add_axes([0, 0, 1, 0.88])
            bx.axis("off")
            bx.set_xlim(0, 11.2)
            bx.set_ylim(0, 5.3)
            rows = [("입력 A, 학습률 0.01", "x² 평균 36.67", "1 " + M + " 2 × 0.01 × 36.67", "0.2667 배", INK),
                    ("입력 B, 학습률 0.01", "x² 평균 175", "1 " + M + " 2 × 0.01 × 175", M + "2.5 배 (발산)", RED),
                    ("입력 B, 학습률 0.001", "x² 평균 175", "1 " + M + " 2 × 0.001 × 175", "0.65 배", INK)]
            assert fx(float(RA), 4) == "0.2667" and float(RB) == -2.5 and float(RC) == 0.65
            for i, (a, b, c, d, col) in enumerate(rows):
                y = 4.2 - i * 1.35
                rbox(bx, 0.3, y - 0.5, 10.6, 1.0, RED if col == RED else GRAY, RED_L if col == RED else "white")
                bx.text(0.55, y, a, fontsize=18, va="center", color=INK, weight="bold", zorder=4)
                bx.text(3.9, y, sup(b), fontsize=17, va="center", color=INK, zorder=4)
                bx.text(5.95, y, c, fontsize=17, va="center", color=INK, zorder=4)
                bx.text(10.7, y, d, fontsize=18, va="center", ha="right", color=col, weight="bold", zorder=4)
        frames.append(image(fig))
    return frames, ms


@figure("7e-5", 560, 300)
def memo_7e():
    return memo([[(0.3, 3.5, "정답 모양", ["view((" + M + "1, 1))", "[506] → [506, 1]", "안 하면 [506, 506]",
                                           "경고만 뜸"], GREEN, GREEN, (0,)),
                  (4.0, 3.55, "첫 단계", ["손실 308.45", "기울기 " + M + "199.64, " + M + "30.50", "갱신 뒤 2.9964, 1.3050",
                                         "슬라이드 ÷ 2: 154.22"], GRAY, INK, ()),
                  (7.75, 3.15, "학습률", ["입력 둘 (506, 2)", "0.01 → nan", "0.001 → 30.56", "1 " + M + " 2 × lr × x² 평균"],
                   ORANGE, ORANGE, ())]],
                "optimizer.step() 은 .grad 를 지우지 않음. 지우는 것은 zero_grad()")


# 7f R² 와 규제

@figure("7f-1", 560, 280)
def r2_parts():
    """다섯 사람의 SS_tot(평균선까지)과 SS_res(최소제곱 직선까지)."""
    plt, fig = new(560)
    xx = np.linspace(-6.5, 6.5, 2)
    for c, (title, kind) in enumerate([("SS_tot = 214.96", "tot"), ("SS_res = 22.70", "res")]):
        ax = fig.add_axes([0.08 + c * 0.48, 0.24, 0.4, 0.62])
        tidy(ax)
        ax.set_xlim(-6.5, 6.5)
        ax.set_ylim(-9, 13)
        ax.set_xticks([-5, 0, 5])
        minus_ticks(ax)
        ax.set_xlabel("X")
        if kind == "tot":
            ax.axhline(0, color=GRAY, lw=2.4)
            for xv, yv in zip(XP, YP):
                ax.plot([xv, xv], [0, yv], color=GRAY, lw=2.6)
            ax.set_title(title, fontsize=19, color=MUTED, loc="left")
        else:
            ax.plot(xx, W_OLS * xx, color=BLUE, lw=2.6)
            for xv, yv in zip(XP, YP):
                ax.plot([xv, xv], [W_OLS * xv, yv], color=RED, lw=2.6)
            ax.set_title(title, fontsize=19, color=RED, loc="left")
        ax.scatter(XP, YP, s=80, color=INK, zorder=6)
    fig.text(0.5, 0.06, sup("R² = 1 " + M + " 22.70 ÷ 214.96 = 0.8944"), ha="center", fontsize=19, color=INK,
             bbox=dict(boxstyle="round,pad=0.3", fc=NOTE, ec="none"))
    return image(fig)


@figure("7f-2", 560, 260)
def ridge_curves():
    """(w − 0.3)² + λw² 의 λ = 0, 0.5, 1 곡선과 가장 작은 w 0.3, 0.2, 0.15."""
    plt, fig = new(520)
    ax = fig.add_axes([0.1, 0.17, 0.56, 0.74])
    tidy(ax)
    ax.set_xlim(-0.2, 0.6)
    ax.set_ylim(0, 0.32)
    ax.set_xlabel("w")
    ax.set_ylabel("손실")
    minus_ticks(ax, "x")
    ww = np.linspace(-0.2, 0.6, 300)
    styles = ((0, ":"), (0.5, "--"), (1.0, "-"))
    for lam, ls in styles:
        L = (ww - 0.3) ** 2 + lam * ww ** 2
        wm = ridge_w(lam)
        assert abs(ww[np.argmin(L)] - wm) < 0.003
        ax.plot(ww, L, color=PURPLE, lw=2.6, ls=ls)
        ax.scatter([wm], [(wm - 0.3) ** 2 + lam * wm ** 2], s=80, color=INK, zorder=5)
    assert [num(ridge_w(v), 2) for v in (0, 0.5, 1)] == ["0.3", "0.2", "0.15"]
    bx = fig.add_axes([0.69, 0.1, 0.3, 0.8])
    bx.axis("off")
    bx.set_xlim(0, 3.2)
    bx.set_ylim(0, 5)
    for k, ((lam, ls), t) in enumerate(zip(styles, ["λ = 0 → w = 0.3", "λ = 0.5 → w = 0.2", "λ = 1 → w = 0.15"])):
        y = 4.3 - k * 0.75
        bx.plot([0.05, 0.55], [y, y], color=PURPLE, lw=2.6, ls=ls)
        bx.text(0.7, y, t, fontsize=17, color=INK, va="center")
    bx.text(0.05, 1.6, "w = 0.3 ÷ (1 + λ)", fontsize=17, color=PURPLE, va="center", weight="bold")
    bx.text(0.05, 0.9, "0 이 되지 않음", fontsize=16, color=MUTED, va="center")
    return image(fig)


@figure("7f-3", 560, 300)
def ridge_vs_lasso():
    """λ = 0, 0.2, 0.4, 0.6, 1 에서 Ridge·Lasso 손실과 가장 작은 w. 마지막 장은 λ 에 따른 가장 작은 w."""
    frames, ms = [], [2000, 2000, 2000, 2200, 2200, 2500]
    ww = np.linspace(-0.2, 0.5, 400)
    lams = [0, 0.2, 0.4, 0.6, 1.0]
    for k, lam in enumerate(lams):
        plt, fig = new(600)
        ax = fig.add_axes([0.09, 0.14, 0.52, 0.72])
        tidy(ax)
        ax.set_xlim(-0.2, 0.5)
        ax.set_ylim(0, 0.4)
        ax.set_xlabel("w")
        ax.set_ylabel("손실")
        minus_ticks(ax, "x")
        Lr = (ww - 0.3) ** 2 + lam * ww ** 2
        Ll = (ww - 0.3) ** 2 + lam * np.abs(ww)
        wr, wl = ridge_w(lam), lasso_w(lam)
        assert abs(ww[np.argmin(Lr)] - wr) < 0.002 and abs(ww[np.argmin(Ll)] - wl) < 0.002
        ax.plot(ww, Lr, color=PURPLE, lw=2.6)
        ax.plot(ww, Ll, color=ORANGE, lw=2.6)
        ax.scatter([wr], [(wr - 0.3) ** 2 + lam * wr ** 2], s=90, color=PURPLE, zorder=5)
        ax.scatter([wl], [(wl - 0.3) ** 2 + lam * abs(wl)], s=90, color=ORANGE, zorder=6)
        ax.axvline(0, color=FAINT, lw=1.2, zorder=1)
        head(fig, "λ = %s" % num(lam, 1) + ("   두 손실이 같아 곡선이 겹침" if lam == 0 else ""), size=21, y=0.95)
        bx = fig.add_axes([0.65, 0.1, 0.34, 0.8])
        bx.axis("off")
        bx.set_xlim(0, 3.4)
        bx.set_ylim(0, 5)
        bx.text(0.05, 4.2, "Ridge", fontsize=19, color=PURPLE, weight="bold", va="center")
        bx.text(0.05, 3.55, "w = " + num(wr, 4), fontsize=18, color=INK, va="center")
        bx.text(0.05, 2.5, "Lasso", fontsize=19, color=ORANGE, weight="bold", va="center")
        bx.text(0.05, 1.85, "w = " + num(wl, 4), fontsize=18, color=INK, va="center")
        frames.append(image(fig))
    plt, fig = new(600)
    ax = fig.add_axes([0.1, 0.15, 0.62, 0.72])
    tidy(ax)
    lg = np.linspace(0, 1, 200)
    ax.plot(lg, [ridge_w(v) for v in lg], color=PURPLE, lw=2.8)
    ax.plot(lg, [lasso_w(v) for v in lg], color=ORANGE, lw=2.8)
    ax.scatter(lams, [ridge_w(v) for v in lams], s=60, color=PURPLE, zorder=5)
    ax.scatter(lams, [lasso_w(v) for v in lams], s=60, color=ORANGE, zorder=5)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(-0.01, 0.32)
    ax.set_xlabel("λ")
    ax.set_ylabel("손실이 가장 작은 w")
    note(ax, 0.62, 0.025, "λ = 0.6 부터 0", color=ORANGE, size=16, bg="white")
    head(fig, "λ 에 따른 가장 작은 w", size=20, y=0.95)
    fig.text(0.76, 0.62, "Ridge: 0 에\n다가가기만 함", fontsize=17, color=PURPLE, va="center")
    fig.text(0.76, 0.32, "Lasso: 0 이 됨", fontsize=17, color=ORANGE, va="center")
    frames.append(image(fig))
    return frames, ms


@figure("7f-4", 560, 300)
def memo_7f():
    return memo([[(0.3, 3.7, "R²", ["SS_tot > 0일 때", "1 " + M + " SS_res ÷ SS_tot", M + "∞ < R² ≤ 1", "인과를 보여 주지 않음"],
                   GRAY, INK, ()),
                  (4.2, 3.4, "Ridge", ["MSE=(w−0.3)²인 예", "벌점 λw², 유한 λ≥0", "최적의 w=0.3/(1+λ)"], PURPLE, PURPLE, ()),
                  (7.8, 3.1, "Lasso", ["같은 MSE에 λ|w| 추가", "λ≥0.6이면 w=0", "손실에 직접 더함"], ORANGE, ORANGE, ())]],
                "SGD weight_decay=λ는 손실 벌점 (λ/2)w²에 해당합니다.")


# 7g 학습 기록과 회귀 직선

@figure("7g-1", 560, 300)
def history_rows():
    """history 가 행 0개에서 [epoch, 손실] 을 1000 에폭마다 쌓아 (5, 2) 가 됨. 손실은 7e-3 과 같은 학습(SGD lr 0.01, 손실 ÷ 2)."""
    recs = [(0, 154.2249), (1000, 28.0961), (2000, 26.7504), (3000, 25.6923), (4000, 24.8603)]
    if os.path.isfile(BOSTON):
        got, _ = boston_run(4001, half=True, every=1000)
        assert [(e, fx(v, 4)) for e, v in got] == [(e, fx(v, 4)) for e, v in recs]
    counts = [0, 1, 2, 5, 5]
    heads = ["history = np.zeros((0, 2))", "epoch 0 → (1, 2)", "epoch 1000 → (2, 2)", "epoch 2000, 3000, 4000 → (5, 2)",
             "range(5000) 은 4999 까지라 5000 은 기록되지 않음"]
    frames, ms = [], [2000, 2000, 1800, 2200, 2500]
    for k in range(5):
        plt, fig, ax = board(600)
        head(fig, heads[k], size=19, y=0.95)
        cell(ax, 1.0, 4.75, 2.0, 0.6, "epoch", edge=GRAY, fill=BAND, size=17, weight="bold")
        cell(ax, 3.0, 4.75, 2.6, 0.6, "손실", edge=GRAY, fill=BAND, size=17, weight="bold")
        n = counts[k]
        newest = {1: [0], 2: [1], 3: [2, 3, 4]}.get(k, [])
        for i in range(5):
            y0 = 4.75 - (i + 1) * 0.66
            if i < n:
                fill = HL if i in newest else PURPLE_L
                cell(ax, 1.0, y0, 2.0, 0.66, str(recs[i][0]), edge=PURPLE, fill=fill, size=18)
                cell(ax, 3.0, y0, 2.6, 0.66, fx(recs[i][1], 4), edge=PURPLE, fill=fill, size=18)
            else:
                cell(ax, 1.0, y0, 2.0, 0.66, "", edge=BAND, fill="white")
                cell(ax, 3.0, y0, 2.6, 0.66, "", edge=BAND, fill="white")
        note(ax, 6.2, 3.6, "모양 (%d, 2)" % n, size=20)
        if k == 4:
            note(ax, 6.2, 2.6, "history[" + M + "1, 1] = 24.8603", size=18, family=CODE)
            note(ax, 6.2, 1.75, "epoch 4000, 갱신하기 전", size=18)
        frames.append(image(fig))
    return frames, ms


@figure("7g-2", 560, 280)
def two_points():
    """신장 최솟값 166, 최댓값 176 두 점으로 그린 회귀 직선."""
    y166 = W_OLS * (166 - HT.mean()) + WT.mean()
    y176 = W_OLS * (176 - HT.mean()) + WT.mean()
    assert fx(y166, 2) == "56.30" and fx(y176, 2) == "74.50"
    plt, fig = new(560)
    ax = fig.add_axes([0.09, 0.15, 0.5, 0.75])
    tidy(ax)
    ax.set_xlim(164, 178)
    ax.set_ylim(52, 80)
    ax.set_xlabel("신장 (cm)")
    ax.set_ylabel("체중 (kg)")
    ax.plot([166, 176], [y166, y176], color=BLUE, lw=2.8, zorder=3)
    ax.scatter(HT, WT, s=80, color=INK, zorder=5)
    ax.scatter([166, 176], [y166, y176], s=140, marker="s", color=BLUE, zorder=6)
    note(ax, 166.3, 53.6, "(166, 56.30)", color=BLUE, size=16, bg="white")
    note(ax, 175.6, 78.6, "(176, 74.50)", color=BLUE, size=16, bg="white", ha="right")
    bx = fig.add_axes([0.62, 0.1, 0.37, 0.8])
    bx.axis("off")
    bx.set_xlim(0, 4)
    bx.set_ylim(0, 5)
    for k, (t, code) in enumerate([("reshape(" + M + "1, 1)", True), ("(2,) → (2, 1)", False), ("with torch.no_grad():", True),
                                   ("Yse.cpu().numpy()", True)]):
        bx.text(0.05, 4.2 - k * 0.95, t, fontsize=16, family=CODE if code else None, color=INK, va="center")
    return image(fig)


@figure("7g-3", 560, 280)
def two_codes():
    """노트북 02 의 scikit-learn 흐름과 PyTorch 루프, zero_grad 를 둘 수 있는 자리."""
    plt, fig, ax = board(560)
    ax.text(0.4, 5.25, "scikit-learn", fontsize=19, weight="bold", color=INK, va="center")
    steps = [("train_test_split", None), ("fit(X_train, y_train)", GREEN), ("predict(X_test)", ORANGE),
             ("accuracy_score", ORANGE)]
    for i, (t, col) in enumerate(steps):
        y0 = 4.1 - i * 1.0
        rbox(ax, 0.4, y0, 4.0, 0.65, col or GRAY, GREEN_L if col == GREEN else (ORANGE_L if col == ORANGE else "white"))
        ax.text(2.4, y0 + 0.325, t, ha="center", va="center", fontsize=16, family=CODE, color=INK, zorder=4)
        if i < 3:
            arrow(ax, 2.4, y0 - 0.02, 2.4, y0 - 0.32)
    ax.text(5.2, 5.25, "PyTorch 루프", fontsize=19, weight="bold", color=INK, va="center")
    loop = ["예측", "손실", "backward", "step"]
    xs = [5.6, 7.0, 8.4, 9.8]
    for x0, t in zip(xs, loop):
        rbox(ax, x0, 2.9, 1.1, 0.75, GRAY, "white")
        ax.text(x0 + 0.55, 3.27, t, ha="center", va="center", fontsize=16, color=INK, zorder=4)
    for x0 in xs[:-1]:
        arrow(ax, x0 + 1.12, 3.27, x0 + 1.38, 3.27)
    for xc in (5.3, 8.25, 10.98):
        rbox(ax, xc - 0.18, 3.95, 0.36, 0.55, GRAY, "white", ls="--", lw=1.6)
        ax.text(xc, 4.22, "Z", ha="center", va="center", fontsize=15, color=MUTED, zorder=4)
    ax.text(9.65, 4.22, "X", ha="center", va="center", fontsize=24, color=RED, weight="bold", zorder=4)
    note(ax, 8.2, 1.9, "Z = zero_grad() 를 둘 수 있는 자리\n(맨 앞, 손실 다음, step 다음)", size=16, ha="center")
    note(ax, 8.2, 0.75, "X: backward 와 step 사이는 안 됨", size=16, ha="center", color=RED)
    return image(fig)


@figure("7g-4", 560, 300)
def memo_7g():
    return memo([[(0.3, 3.6, "history", ["np.zeros((0, 2))", "np.vstack", "1000 마다 → (5, 2)", "마지막 행은 4000"], PURPLE,
                   PURPLE, (0, 1)),
                  (4.1, 3.6, "회귀 직선", ["최솟값, 최댓값 두 점", "reshape(" + M + "1, 1)", "no_grad 안에서 예측",
                                         ".cpu().numpy()"], BLUE, BLUE, (1, 3)),
                  (7.9, 3.0, "노트북 02", ["fit 은 학습 데이터", "zero_grad 는", "backward 전이면", "어디든"], GRAY, INK, ())]],
                "기록한 마지막 손실은 갱신 전에 잰 값이라 학습을 마친 모델의 손실이 아님")


# 세 수준으로 다시 보기 블록 그림. 화면 520×280(파일 1040×560), 글자 22 이상은 tools/ai_art/levels.py 를 따름.
# 그림 이름은 <단원>-<단계 번호><수준 번호>(7살 1, 15살 2, 20살 3). 색 뜻은 그 단원의 뜻을 그대로 씀.
# 숫자는 이 파일의 단계 상수에서 다시 계산하고 assert 함(출제 기록 pr6/checks/l07_levels.py 와 같은 값).

from tools.ai_art import SCALE, levels as LV  # noqa: E402


def _lv_board():
    """세 수준 그림 판. 좌표는 화면 논리 px(가로 0~520, 세로 0~280)."""
    plt = setup()
    width, height = LV.SIZE
    fig = plt.figure(figsize=(width * SCALE / 100.0, height * SCALE / 100.0), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    return fig, ax


def _lv_box(ax, cx, cy, w, h, s, ec=MUTED, fc="white", size=None, bold=False, lw=2.0, color=INK):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((cx - w / 2.0, cy - h / 2.0), w, h, boxstyle="round,pad=0,rounding_size=10", fc=fc, ec=ec,
                                lw=lw, zorder=3))
    if s != "":
        ax.text(cx, cy, s, ha="center", va="center", fontsize=size or LV.BIG, color=color, zorder=4,
                weight="bold" if bold else "normal")


def _lv_text(ax, x, y, s, color=INK, size=None, ha="center", va="center", bold=False):
    ax.text(x, y, s, ha=ha, va=va, fontsize=size or LV.FONT, color=color, zorder=5, weight="bold" if bold else "normal")


def _lv_arrow(ax, x0, y0, x1, y1, color=INK, lw=2.4):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=4,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=20, shrinkA=0, shrinkB=0))


# 7b 둘째 단계: 최소제곱법. 검은 점은 다섯 사람, 파랑은 직선, 빨강은 잔차와 잔차 제곱합

def _levels_7b(level):
    first = YP - (XP + 1)
    assert np.allclose(first, [-2.7, 4.3, -4.3, 2.0, -4.3]) and abs((first ** 2).sum() - 66.76) < 1e-9
    if level == 7:
        fig, ax0 = _lv_board()
        ax = fig.add_axes([0.04, 0.2, 0.92, 0.76])
        ax.axis("off")
        ax.set_xlim(-7.5, 7.5)
        ax.set_ylim(-8.5, 12.5)
        xx = np.array([-6.5, 6.5])
        ax.plot(xx, xx + 1, color=BLUE, lw=3, zorder=2)
        for k, (x, y) in enumerate(zip(XP, YP)):
            bold = k in (1, 2)
            ax.plot([x, x], [y, x + 1], color=RED, lw=4 if bold else 2.2, zorder=3)
            ax.plot([x], [y], "o", ms=12, color=INK, zorder=5)
        ax.text(XP[1] - 0.35, (YP[1] + XP[1] + 1) / 2 + 0.4, "사람 2\n4.3", ha="right", va="center", fontsize=LV.FONT,
                color=RED, linespacing=1.15, zorder=6)
        ax.text(XP[2] + 0.35, (YP[2] + XP[2] + 1) / 2, "사람 3\n" + M + "4.3", ha="left", va="center", fontsize=LV.FONT,
                color=RED, linespacing=1.15, zorder=6)
        _lv_text(ax0, 260, 26, "4.3과 " + M + "4.3을 그냥 더하면 0")
        return fig
    if level == 15:
        r = YP - 2 * XP
        assert np.allclose(r, [3.3, 0.3, -3.3, 1.0, -1.3]) and abs((r ** 2).sum() - 24.56) < 1e-9
        rows = [[num(x, 1), num(y, 1), num(e, 1), num(e * e, 2)] for x, y, e in zip(XP, YP, r)]
        rows.append(["", "", "", num((r ** 2).sum(), 2)])
        return LV.grid(rows, col_names=["X", "Y", "잔차", "잔차 제곱"], row_names=["사람 %d" % k for k in range(1, 6)] + ["합"],
                       marks=[(0, 3), (2, 3), (5, 3)], color="red", top="잔차 = Y " + M + " 2 × X")
    x_code = np.array([-5, 5, 0, 2, -2])
    y_code = np.array([-6.7, 10.3, -3.3, 5.0, -5.3])  # 블록 코드와 같은 배열이라 r.sum().round(4) 가 0.0 으로 찍힘
    assert np.allclose(x_code, XP) and np.allclose(y_code, YP)
    rows = []
    for w, b in ((0.6, 0), (2.6, 0), (1, 1)):
        e = y_code - (w * x_code + b)
        rows.append([str(e.sum().round(4)), str((e ** 2).sum().round(2))])
    assert rows == [["0.0", "109.12"], ["0.0", "57.92"], ["-5.0", "66.76"]], rows
    return LV.grid(rows, col_names=["r.sum()", "(r ** 2).sum()"], row_names=["W 0.6, B 0", "W 2.6, B 0", "W 1, B 1"],
                   marks=[(0, 0), (1, 0)], color="red", top="r = Y - (W * X + B)", code=True)


@figure("7b-21", *LV.SIZE)
def levels_7b_7():
    return _levels_7b(7)


@figure("7b-22", *LV.SIZE)
def levels_7b_15():
    return _levels_7b(15)


@figure("7b-23", *LV.SIZE)
def levels_7b_20():
    return _levels_7b(20)


# 7c 셋째 단계: 차수와 곡선 모양. 초록은 다항식 곡선, 주황은 극값, 검은 점선은 미분한 식

def _levels_7c(level):
    if level == 7:
        assert [len(extrema(d)) for d in (1, 2, 3, 4)] == [0, 1, 2, 3]
        return LV.chain(["0곳", "1곳", "2곳", "3곳"], labels=["수 1개", "수 2개", "수 3개", "수 4개"],
                        note="오르다 내려가거나 내려가다 오르는 곳은 많아야 이만큼")
    if level == 15:
        xs = np.linspace(-2.5, 2.5, 201)
        cubic = np.polynomial.Polynomial(POLYS[3])
        slope = cubic.deriv()
        assert np.allclose(slope.coef, [-2.4, 0, 1.8])
        roots = sorted(float(v) for v in slope.roots())
        assert [fx(v, 4) for v in roots] == [M + "1.1547", "1.1547"]
        assert [fx(cubic(v), 4) for v in roots] == ["1.8475", M + "1.8475"]
        fig = LV.graph(list(xs), [(list(cubic(xs)), "green", ""), (list(slope(xs)), "ink", "")], "x", "y",
                       top="극값의 수 ≤ 차수 " + M + " 1", marks=[(v, cubic(v), "", "orange") for v in roots],
                       xlim=(-2.7, 2.7), ylim=(-4.2, 9.6))
        ax = fig.axes[0]
        ax.lines[1].set_linestyle("--")
        ax.axhline(0, color=COLORS["faint"], lw=2, zorder=1)
        for v in roots:
            ax.plot([v, v], [0, cubic(v)], color=MUTED, lw=1.5, ls=":", zorder=2)
            ax.plot([v], [0], "o", ms=10, color=INK, zorder=6)
        minus_ticks(ax)
        ax.text(-1.9, 7.6, "미분한 식", ha="left", va="center", fontsize=LV.FONT, color=INK)
        ax.text(1.6, -3.2, "곡선", ha="left", va="center", fontsize=LV.FONT, color=GREEN)
        LV._inside(fig)
        return fig
    five = np.polynomial.Polynomial(POLYS[5]).deriv()
    roots = sorted(float(v.real) for v in five.roots() if abs(v.imag) < 1e-12)
    assert [fx(v, 4) for v in roots] == [M + "1.8173", M + "0.6562", "0.6562", "1.8173"]
    signs = [("+" if five(v - 1e-3) > 0 else "-", "+" if five(v + 1e-3) > 0 else "-") for v in roots]
    assert signs == [("+", "-"), ("-", "+"), ("+", "-"), ("-", "+")]
    cube = np.polynomial.Polynomial([0, 0, 0, 1]).deriv()
    assert cube(-1e-3) > 0 and cube(1e-3) > 0
    rows = [["%.4f" % v, "%s → %s" % s, "예"] for v, s in zip(roots, signs)] + [["0, 0", "+ → +", "아님"]]
    return LV.grid(rows, col_names=["근", "부호", "극값"], row_names=["f5"] * 4 + ["$x^{3}$"], marks=[(k, 2) for k in range(4)],
                   color="orange", top="np.roots(np.polyder(f))", code=True)


@figure("7c-31", *LV.SIZE)
def levels_7c_7():
    return _levels_7c(7)


@figure("7c-32", *LV.SIZE)
def levels_7c_15():
    return _levels_7c(15)


@figure("7c-33", *LV.SIZE)
def levels_7c_20():
    return _levels_7c(20)


# 7e 둘째 단계: 정답 모양. 파랑은 출력, 초록은 정답, 빨강은 뺀 값과 손실

def _levels_7e(level):
    out = np.array([[1.0], [2.0], [3.0]])
    ans = np.array([1.0, 2.0, 3.0])
    assert (out - ans).shape == (3, 3) and abs(((out - ans) ** 2).mean() - 4 / 3) < 1e-12
    if level == 7:
        two = np.array([[1.0], [2.0]]) - np.array([1.0, 2.0])
        assert two.tolist() == [[0, -1], [1, 0]]
        fig, ax = _lv_board()
        right_rows = [(185, "1", "1", "0"), (143, "1", "2", M + "1"), (101, "2", "1", "1"), (59, "2", "2", "0")]
        left_rows = [(164, "1", "1", "0"), (80, "2", "2", "0")]
        for rows, left, right, title in ((left_rows, 55, 185, "같은 데이터끼리"), (right_rows, 335, 465, "모든 짝")):
            _lv_text(ax, (left + right) / 2.0, 255, title, bold=True)
            _lv_text(ax, left, 222, "모델", color=BLUE)
            _lv_text(ax, right, 222, "정답", color=GREEN)
            for y, a, b, d in rows:
                _lv_box(ax, left, y, 46, 34, a, ec=BLUE, fc=BLUE_L, size=LV.FONT)
                _lv_box(ax, right, y, 46, 34, b, ec=GREEN, fc=GREEN_L, size=LV.FONT)
                _lv_arrow(ax, left + 28, y, right - 28, y, color=RED, lw=2.2)
                _lv_text(ax, (left + right) / 2.0, y + 11, d, color=RED, bold=True, va="bottom")
        _lv_text(ax, 260, 20, "모든 짝을 빼면 뺄셈이 네 번")
        return fig
    if level == 15:
        cs = np.linspace(0, 4, 201)
        loss = [float(((c - ans) ** 2).mean()) for c in cs]
        assert fx(min(loss), 4) == "0.6667" and abs(cs[int(np.argmin(loss))] - 2) < 1e-12
        assert fx(loss[0], 4) == "4.6667" and fx(loss[-1], 4) == "4.6667"
        fig = LV.graph(list(cs), [(loss, "red", "")], "세 출력에 똑같이 낸 수", "틀린 손실",
                       top="틀린 손실 = (아홉 칸 제곱의 합) ÷ 9", marks=[(2, 2 / 3.0, "", "red")],
                       xlim=(-0.1, 4.1), ylim=(0, 5.2))
        ax = fig.axes[0]
        ax.axhline(4 / 3.0, color=RED, lw=2.4, ls="--", zorder=2)
        ax.text(1.85, 0.42, "0.6667", ha="right", va="center", fontsize=LV.FONT, color=RED)
        ax.text(2, 4 / 3.0 + 0.2, "[1, 2, 3]: 1.3333", ha="center", va="bottom", fontsize=LV.FONT, color=RED)
        LV._inside(fig)
        return fig
    rows = []
    for name, target in (("y", ans), ("unsqueeze(0)", ans[None, :]), ("unsqueeze(1)", ans[:, None])):
        diff = out - target
        shape = "[%s]" % ", ".join(str(n) for n in target.shape)
        rows.append([shape, "[%s]" % ", ".join(str(n) for n in diff.shape), "%.4f" % (diff ** 2).mean()])
    rows[2][2] = "0"
    assert rows == [["[3]", "[3, 3]", "1.3333"], ["[1, 3]", "[3, 3]", "1.3333"], ["[3, 1]", "[3, 1]", "0"]], rows
    return LV.grid(rows, col_names=["정답", "뺀 모양", "손실"], row_names=["y", "unsqueeze(0)", "unsqueeze(1)"],
                   marks=[(0, 2), (1, 2)], color="red", top="out: [3, 1]", code=True)


@figure("7e-21", *LV.SIZE)
def levels_7e_7():
    return _levels_7e(7)


@figure("7e-22", *LV.SIZE)
def levels_7e_15():
    return _levels_7e(15)


@figure("7e-23", *LV.SIZE)
def levels_7e_20():
    return _levels_7e(20)


# 7f 넷째 단계: Lasso 회귀. 주황은 Lasso, 보라는 Ridge

def _lasso_a(a, lam):
    return float(np.sign(a) * max(abs(a) - lam / 2.0, 0.0))


def _levels_7f(level):
    if level == 7:
        lams = [0, 0.3, 0.6, 0.9]
        lasso = [lasso_w(v) for v in lams]
        ridge = [ridge_w(v) for v in lams]
        assert [fx(v, 4) for v in lasso] == ["0.3000", "0.1500", "0.0000", "0.0000"]
        assert [fx(v, 4) for v in ridge] == ["0.3000", "0.2308", "0.1875", "0.1579"]
        fig, ax = _lv_board()
        xs = [80, 200, 320, 440]
        _lv_text(ax, 260, 264, "벌점에 곱하는 수", color=MUTED)
        for x, lam in zip(xs, lams):
            _lv_text(ax, x, 225, num(lam, 1), color=MUTED)
        for k, (x, v) in enumerate(zip(xs, lasso)):
            zero = v == 0
            _lv_box(ax, x, 175, 92, 50, num(v, 4), ec=ORANGE, fc=ORANGE_L if zero else "white", size=LV.FONT, bold=zero,
                    lw=3 if zero else 2)
            if k < 3:
                _lv_arrow(ax, x + 48, 175, x + 72, 175, color=ORANGE, lw=2)
        for k, (x, v) in enumerate(zip(xs, ridge)):
            _lv_box(ax, x, 95, 92, 50, num(v, 4), ec=PURPLE, fc="white", size=LV.FONT)
            if k < 3:
                _lv_arrow(ax, x + 48, 95, x + 72, 95, color=PURPLE, lw=2)
        _lv_text(ax, 260, 30, "위 줄은 0이 된 뒤 0에 머묾")
        return fig
    if level == 15:
        ws = np.linspace(0, 0.4, 81)
        low, high = 2 * (ws - 0.3) + 0.3, 2 * (ws - 0.3) + 0.9
        assert abs(ws[int(np.argmin(np.abs(low)))] - 0.15) < 1e-12 and high.min() >= 0.3 - 1e-12
        fig = LV.graph(list(ws), [(list(low), "orange", "λ = 0.3"), (list(high), "orange", "λ = 0.9")], "w", "기울기",
                       top="기울기 = 2(w " + M + " 0.3) + λ", marks=[(0.15, 0.0, "", "ink")], xlim=(0, 0.56), ylim=(-0.45, 1.3))
        ax = fig.axes[0]
        ax.lines[1].set_linestyle("--")
        ax.axhline(0, color=COLORS["faint"], lw=2.2, zorder=1)
        ax.text(0.15, -0.08, "w = 0.15", ha="left", va="top", fontsize=LV.FONT, color=INK)
        LV._inside(fig)
        return fig
    a = [0.3, -0.5, 0.08]
    lasso = [_lasso_a(v, 0.2) for v in a]
    ridge = [v / 1.2 for v in a]
    assert [fx(v, 4) for v in lasso] == ["0.2000", M + "0.4000", "0.0000"]
    assert [fx(v, 4) for v in ridge] == ["0.2500", M + "0.4167", "0.0667"]
    rows = [["0.2", "0.25"], ["-0.4", "-0.4167"], ["0", "0.0667"]]  # 코드 출력처럼 빼기표는 ASCII
    return LV.grid(rows, col_names=["lasso", "ridge"], row_names=["a = 0.3", "a = " + M + "0.5", "a = 0.08"], marks=[(2, 0)],
                   color="orange", top="lam = 0.2", code=True)


@figure("7f-41", *LV.SIZE)
def levels_7f_7():
    return _levels_7f(7)


@figure("7f-42", *LV.SIZE)
def levels_7f_15():
    return _levels_7f(15)


@figure("7f-43", *LV.SIZE)
def levels_7f_20():
    return _levels_7f(20)
