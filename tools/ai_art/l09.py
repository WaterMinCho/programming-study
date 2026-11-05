#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""9차시 학습 노트 l09 의 그림(9a 출력과 가중치 행렬, 9b 소프트맥스의 성질, 9c 로그 소프트맥스·NLLLoss·CrossEntropyLoss,
9d KL divergence, 9e 예측 클래스와 정확도, 9f 3 × 3 혼동 행렬, 9g 붓꽃 학습 코드와 wine 다층 신경망).

그림에 찍는 숫자는 모두 이 파일에서 numpy 로 다시 계산하고 assert 로 확인함(9차시 노트북 01 [25]·[27]·[41]·[53]·[62],
노트북 02 [5]·[11]~[13]·[21], 노트북 03 [7]·[11]·[25] 의 출력과 맞춤).

  python -m tools.ai_art l09                 ai/learn/l09/assets/ 에 그림을 모두 쓰고 manifest 를 고침
  python -m tools.ai_art l09 9b-1            이름을 적은 그림만

numpy·matplotlib·Pillow 가 있는 출제자 파이썬에서만 돌림. matplotlib 는 Agg 로만 씀(창을 띄우지 않음).
파일은 1120×600 이하(화면 560×300), GIF 는 장 10개 이하·장마다 1600~2500ms·64색이고 마지막 장은 정지 요약임.
"""
import math
import os
import sys

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
YELLOW = "#fde68a"
SLATE, SLATE_D, SLATE_L, SLATE_LL = "#3d6187", "#253747", "#9fb2c4", "#e0e8f0"
CODE = "D2Coding"
# 단원마다 한 색은 한 뜻이고, 뜻은 그 그림의 캡션에 적음. 그림 안 설명 글은 회색(NOTE) 바탕이고 뜻이 없음
# 9a: 회색은 입력 특징, 파랑은 logit, 주황은 가중치(지금 계산하는 행과 가중치 행렬), 초록은 고른 열,
#     슬레이트는 학습 데이터, 보라는 검증 데이터
# 9b: 파랑은 logit, 보라는 e^(logit), 주황은 소프트맥스 확률, 회색은 비율 그대로·가장 큰 값만 1 로 만든 값,
#     초록 테두리는 합이 1 이 되는 묶음
# 9c: 파랑은 logit, 회색 점선은 log(e^(logit) 의 합), 보라는 로그 소프트맥스, 초록은 정답 칸과 손실,
#     빨강은 무한대와 권하지 않는 패턴, 슬레이트는 가장 큰 값을 뺀 뒤의 e^(logit), 회색 상자는 모델
# 9d: 초록은 정답 분포 P, 주황은 예측 분포 Q, 보라는 클래스마다 더하는 값
# 9e: 파랑은 logit, 노랑은 가장 큰 칸, 초록은 맞힌 예측, 빨강은 틀린 예측, 주황은 확률
# 9f: 초록은 맞힌 칸·바르게 읽은 값, 빨강은 틀린 칸·맞바뀐 값, 노랑 바탕은 지표가 쓰는 줄
# 9g: 파랑은 logit, 주황은 확률, 회색은 특징 2개, 보라는 특징 4개, 슬레이트는 Linear 층, 점선 상자는 파라미터가 없는 층,
#     빨강은 노트북 03 의 줄, 초록은 고친 줄
M = MINUS
SIZES = {"font.size": 20, "axes.titlesize": 20, "axes.labelsize": 19, "xtick.labelsize": 17, "ytick.labelsize": 17,
         "axes.linewidth": 1.2, "axes.edgecolor": "#9ca3af"}


def num(v, nd=4):
    """그림에 찍는 숫자. 빼기표는 U+2212, 끝의 0 은 지움."""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"
    return ("0" if s in ("-0", "0") else s).replace("-", M)


def fx(v, nd):
    """소수 nd 자리 고정(끝의 0 을 지우지 않음). 빼기표는 U+2212."""
    s = f"{v:.{nd}f}"
    if s.startswith("-") and float(s) == 0:
        s = s[1:]
    return s.replace("-", M)


def lst(vals, nd):
    return "[" + ", ".join(fx(v, nd) for v in vals) + "]"


def new(h=600):
    """(pyplot, Figure). 파일 폭 1120px, 높이 h px."""
    plt = setup()
    plt.rcParams.update(SIZES)
    return plt, plt.figure(figsize=(11.2, h / 100.0), dpi=100)


def image(fig):
    """Figure 를 RGB 그림으로 바꾸고 닫음."""
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
        ax.grid(True, axis="y", color=GRID, lw=1.0, zorder=0)
        ax.set_axisbelow(True)


def note(target, px, py, text, color=INK, size=18, bg=NOTE, ha="left", va="center", weight="normal", family=None,
         transform=None, ec=None):
    """설명 글자. bg 가 있으면 둥근 바탕을 깔아 선 위에서도 읽히게 함."""
    kw = dict(color=color, fontsize=size, ha=ha, va=va, weight=weight, zorder=12, linespacing=1.35)
    if family:
        kw["family"] = family
    if bg:
        kw["bbox"] = dict(boxstyle="round,pad=0.3", fc=bg, ec=ec or bg, lw=1.4)
    if transform is not None:
        kw["transform"] = transform
    return target.text(px, py, text, **kw)


def head(fig, text, size=21, y=0.955):
    """그림 맨 위 왼쪽 제목 줄."""
    fig.text(0.015, y, text, fontsize=size, color=INK, va="center", ha="left", weight="bold")


def board(h=500):
    """좌표가 (0~11.2, 0~h/100) 인 빈 판."""
    plt, fig = new(h)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, h / 100.0)
    ax.axis("off")
    return plt, fig, ax


def box(ax, x0, y0, w, h, fc="white", ec=INK, lw=2.0, ls="-", z=2, rounded=True):
    from matplotlib.patches import FancyBboxPatch, Rectangle
    if rounded:
        ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0.04", fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))
    else:
        ax.add_patch(Rectangle((x0, y0), w, h, fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))


def cell(ax, x0, y0, w, h, text, fc="white", ec=FAINT, lw=1.4, color=INK, size=19, weight="normal", family=None):
    box(ax, x0, y0, w, h, fc=fc, ec=ec, lw=lw, rounded=False)
    kw = dict(ha="center", va="center", fontsize=size, color=color, weight=weight, zorder=5)
    if family:
        kw["family"] = family
    ax.text(x0 + w / 2, y0 + h / 2, text, **kw)


def arrow(ax, x0, y0, x1, y1, color=MUTED, lw=2.2, z=4):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=20, shrinkA=0, shrinkB=0), zorder=z)


def card(ax, x0, y0, w, h, title, lines, edge, ink=INK, fill="white", size=17, title_size=20, code_lines=()):
    """둥근 상자 하나. lines 는 위에서부터 한 줄씩. code_lines 에 든 번호의 줄은 D2Coding 으로 씀."""
    box(ax, x0, y0, w, h, fc=fill, ec=edge, lw=2.2)
    ax.text(x0 + 0.18, y0 + h - 0.32, title, ha="left", va="center", fontsize=title_size, weight="bold", color=ink, zorder=3)
    yy = y0 + h - 0.85
    for k, text in enumerate(lines):
        kw = dict(ha="left", va="center", fontsize=size, color=INK, zorder=3)
        if k in code_lines:
            kw["family"] = CODE
        ax.text(x0 + 0.22, yy, text, **kw)
        yy -= 0.5


def memo(specs, foot):
    """외울 것 그림. specs 는 줄마다 [(x0, w, title, lines, edge, ink, code_lines)] 이고 위 줄부터 그림. 상자 높이는 줄 수로
    정하고 그림 높이도 그에 맞춤. foot 은 맨 아래 회색 바탕 한 줄."""
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
    ax.text(5.6, 0.45, foot, ha="center", va="center", fontsize=16, color=INK,
            bbox=dict(boxstyle="round,pad=0.3", fc=NOTE, ec="none"))
    return image(fig)


def seq(ax, fig, x, y, parts, size=22, family=None):
    """글 조각 [(글, 색, 바탕)] 을 왼쪽부터 이어 씀. 조각마다 (왼쪽, 오른쪽) x 를 돌려줌(그린 크기로 잼)."""
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    out = []
    for text, color, bg in parts:
        kw = dict(fontsize=size, color=color, va="center", ha="left", zorder=6)
        if family:
            kw["family"] = family
        if bg:
            kw["bbox"] = dict(boxstyle="square,pad=0.12", fc=bg, ec="none")
        t = ax.text(x, y, text, **kw)
        ext = t.get_window_extent(renderer=renderer)
        x1 = inv.transform((ext.x1, ext.y0))[0]
        out.append((x, x1))
        x = x1 + (0.06 if bg else 0.0)
    return out


def bars(ax, xs, vals, color, nd, lim, width=0.6, label_size=17, alpha=1.0, edge=None, z=3, texts=None):
    """막대와 막대 끝 숫자. 음수 막대는 숫자를 아래에 씀. texts 를 주면 그 글을 씀."""
    span = lim[1] - lim[0]
    out = ax.bar(xs, vals, color=color, width=width, zorder=z, alpha=alpha, edgecolor=edge or color)
    for k, (x, v) in enumerate(zip(xs, vals)):
        off = 0.035 * span
        ax.text(x, v + (off if v >= 0 else -off), texts[k] if texts else fx(v, nd), ha="center",
                va="bottom" if v >= 0 else "top", fontsize=label_size, color=INK, zorder=6)
    return out


def class_axes(fig, rect, lim, title=None, color=INK, labels=("0", "1", "2"), xlabel="클래스"):
    ax = fig.add_axes(rect)
    tidy(ax, grid=False)
    ax.set_ylim(*lim)
    n = len(labels)
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.axhline(0, color=INK, lw=1)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    if title:
        ax.set_title(title, fontsize=18, color=color, pad=8)
    return ax


# 공용 계산

def softmax(z):
    z = np.asarray(z, float)
    e = np.exp(z - z.max(-1, keepdims=True))
    return e / e.sum(-1, keepdims=True)


def lse(z):
    z = np.asarray(z, float)
    m = z.max(-1, keepdims=True)
    return (m + np.log(np.exp(z - m).sum(-1, keepdims=True))).squeeze(-1)


def log_softmax(z):
    z = np.asarray(z, float)
    return z - lse(z)[..., None]


def kl(p, q):
    p, q = np.asarray(p, float), np.asarray(q, float)
    m = p > 0
    return float(np.sum(p[m] * np.log(p[m] / q[m])))


# 9a 예: x = [1, 2], 가중치 행렬 [[1, 1], [0, 1], [1, −1]], bias [−1, −1, 1] → logit [2, 1, 0]
X = np.array([1.0, 2.0])
WM = np.array([[1.0, 1.0], [0.0, 1.0], [1.0, -1.0]])
BV = np.array([-1.0, -1.0, 1.0])
Z = WM @ X + BV
assert np.allclose(Z, [2, 1, 0]) and np.allclose(WM @ X, [3, 2, -1])
# 9b·9c 예: logit [2, 1, 0]
EZ = np.exp(Z)
P = softmax(Z)
LS = log_softmax(Z)
assert [fx(v, 3) for v in EZ] == ["7.389", "2.718", "1.000"] and fx(EZ.sum(), 3) == "11.107"
assert [fx(v, 3) for v in P] == ["0.665", "0.245", "0.090"] and abs(P.sum() - 1) < 1e-12
assert [fx(v, 4) for v in LS] == [M + "0.4076", M + "1.4076", M + "2.4076"] and fx(lse(Z), 4) == "2.4076"
# 9b 배치 예와 dim
BATCH = np.array([[2.0, 1.0, 0.0], [0.5, 0.2, 1.5]])
D1 = softmax(BATCH)
D0 = softmax(BATCH.T).T
assert [fx(v, 4) for v in D1[1]] == ["0.2243", "0.1661", "0.6096"]
assert [fx(v, 4) for v in D0.ravel()] == ["0.8176", "0.6900", "0.1824", "0.1824", "0.3100", "0.8176"]
assert [fx(v, 2) for v in D0.sum(1)] == ["1.69", "1.31"]
# 9c 배치 NLL
LSB = log_softmax(BATCH)
assert [fx(v, 4) for v in LSB[1]] == [M + "1.4949", M + "1.7949", M + "0.4949"]
assert fx(-(LSB[0, 0] + LSB[1, 2]) / 2, 4) == "0.4513"
# 9d 예
PD = np.array([1.0, 0.0, 0.0])
QN = np.array([0.7, 0.2, 0.1])
P2 = np.array([0.6, 0.3, 0.1])
assert fx(kl(PD, P), 4) == "0.4076" and fx(kl(PD, QN), 4) == "0.3567"
assert fx(kl(P2, QN), 4) == "0.0291" and fx(kl(QN, P2), 4) == "0.0268"
# 9e 예
OUT4 = np.array([[2.0, 1.0, 0.0], [0.5, 2.5, 1.0], [1.0, 0.2, 3.0], [1.5, 1.8, 0.4]])
LAB4 = np.array([0, 1, 1, 0])
PRED4 = OUT4.argmax(1)
assert list(PRED4) == [0, 1, 2, 1] and list(OUT4.max(1)) == [2.0, 2.5, 3.0, 1.8]
assert (PRED4 == LAB4).sum() == 2 and (PRED4 == LAB4).mean() == 0.5
# 9f 예: 붓꽃 60송이
CM = np.array([[20, 0, 0], [0, 16, 4], [0, 2, 18]])
NAMES = ["setosa", "versicolor", "virginica"]
PREC = np.array([CM[k, k] / CM[:, k].sum() for k in range(3)])
REC = np.array([CM[k, k] / CM[k].sum() for k in range(3)])
F1 = 2 * PREC * REC / (PREC + REC)
assert np.trace(CM) == 54 and CM.sum() == 60 and np.trace(CM) / CM.sum() == 0.9
assert [fx(v, 3) for v in PREC] == ["1.000", "0.889", "0.818"] and [fx(v, 3) for v in REC] == ["1.000", "0.800", "0.900"]
assert [fx(v, 3) for v in F1] == ["1.000", "0.842", "0.857"]


# 9a 다중 분류의 출력과 가중치 행렬

@figure("9a-1", 560, 260)
def outputs():
    """이진 분류는 logit 1개, 다중 분류는 클래스 수만큼 logit."""
    plt, fig, ax = board(520)
    ys = [3.55, 2.6, 1.65]
    for x0, title in ((0.25, "이진 분류"), (5.75, "다중 분류")):
        box(ax, x0, 0.3, 5.2, 4.7, fc="#fafafa", ec=FAINT, lw=1.6)
        ax.text(x0 + 0.25, 4.6, title, fontsize=21, weight="bold", color=INK, va="center")
        ax.text(x0 + 0.75, 3.95, "입력 특징", fontsize=15, ha="center", va="center", color=MUTED)
        for k, name in enumerate(("특징 1", "특징 2")):
            cell(ax, x0 + 0.25, 3.0 - k * 1.0, 1.0, 0.7, name, fc=NOTE, ec=GRAY, size=16)
        box(ax, x0 + 1.65, 1.75, 1.0, 1.7, fc="white", ec=INK, lw=2.0)
        ax.text(x0 + 2.15, 2.6, "모델", fontsize=18, ha="center", va="center", zorder=5)
        for k in range(2):
            arrow(ax, x0 + 1.27, 3.35 - k * 1.0, x0 + 1.62, 2.6, color=MUTED, lw=1.8)
    arrow(ax, 2.92, 2.6, 3.35, 2.6, color=MUTED)
    cell(ax, 3.4, 2.25, 1.6, 0.7, "logit", fc=BLUE_L, ec=BLUE, lw=2.2, color=BLUE, size=18, weight="bold")
    ax.text(4.2, 1.75, "1개", fontsize=17, ha="center", va="center", color=BLUE)
    for k, y in enumerate(ys):
        arrow(ax, 8.42, 2.6, 8.85, y, color=MUTED, lw=1.8)
        cell(ax, 8.9, y - 0.33, 1.95, 0.66, "클래스 %d logit" % k, fc=BLUE_L, ec=BLUE, lw=2.2, color=BLUE, size=15,
             weight="bold")
    ax.text(6.0, 0.75, "클래스 0 setosa, 1 versicolor, 2 virginica", fontsize=15, color=INK, va="center")
    assert len(ys) == 3
    return image(fig)


@figure("9a-2", 560, 280)
def rows_to_logits():
    """x = [1, 2] 와 3 × 2 가중치 행렬, bias 로 logit [2, 1, 0] 을 한 행씩 계산."""
    forms = ["1 × 1 + 1 × 2 " + M + " 1 = 2", "0 × 1 + 1 × 2 " + M + " 1 = 1", "1 × 1 " + M + " 1 × 2 + 1 = 0"]
    for k in range(3):
        assert WM[k] @ X + BV[k] == Z[k]
    assert num(WM[0] @ X, 0) == "3" and num(WM[1] @ X, 0) == "2" and num(WM[2] @ X, 0) == M + "1"
    titles = {1: "x = [1, 2] 와 가중치 행렬, bias", 2: "0번 행: logit 2", 3: "1번 행: logit 1", 4: "2번 행: logit 0",
              5: "행 셋이 logit 셋을 만듭니다"}

    def draw(stage):
        plt, fig, ax = board(560)
        ax.text(0.2, 5.25, titles[stage], fontsize=21, weight="bold", color=INK, va="center")
        # 입력 x
        ax.text(1.05, 4.45, "입력 x", fontsize=18, ha="center", color=MUTED)
        for j in range(2):
            cell(ax, 0.6, 3.25 - j * 0.9, 0.9, 0.8, num(X[j], 0), fc=NOTE, ec=GRAY, size=20)
        # 가중치 행렬과 bias
        ax.text(3.65, 4.45, "가중치 행렬 [3, 2]", fontsize=18, ha="center", color=ORANGE)
        ax.text(5.55, 4.45, "bias", fontsize=18, ha="center", color=MUTED)
        ax.text(8.2, 4.45, "logit", fontsize=18, ha="center", color=BLUE, weight="bold")
        for k in range(3):
            y = 3.35 - k * 1.05
            current = stage - 2 == k
            for j in range(2):
                cell(ax, 2.75 + j * 0.9, y, 0.9, 0.85, num(WM[k, j], 0), fc=ORANGE_L if current else "white",
                     ec=ORANGE if current else FAINT, lw=2.6 if current else 1.4, size=20)
            cell(ax, 5.1, y, 0.9, 0.85, num(BV[k], 0), fc="white", ec=FAINT, size=20)
            ax.text(2.55, y + 0.42, "%d번 행" % k, fontsize=15, ha="right", va="center", color=MUTED)
            shown = stage >= 5 or stage - 2 >= k
            cell(ax, 7.75, y, 0.9, 0.85, num(Z[k], 0) if shown else "", fc=BLUE_L if shown else "white",
                 ec=BLUE if shown else FAINT, lw=2.2 if shown else 1.4, color=BLUE, size=21, weight="bold")
            if current:
                arrow(ax, 6.1, y + 0.42, 7.65, y + 0.42, color=ORANGE, lw=2.4)
        if 2 <= stage <= 4:
            note(ax, 0.4, 0.45, forms[stage - 2], size=20, family=None)
        if stage == 5:
            note(ax, 0.4, 0.45, "weight [3, 2], bias [3] → logit [2, 1, 0]", size=19)
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2000, 2200, 2200, 2200, 2500]


@figure("9a-3", 560, 270)
def iris_setup():
    """x_org 의 0번·2번 열을 고르고, 75 와 75 로 나누고, set 으로 클래스 수 3 을 셈."""
    counts = [23, 30, 22]
    assert sum(counts) == 75 and len(set([0, 1, 2])) == 3
    plt, fig, ax = board(540)
    # 열 고르기
    ax.text(0.25, 5.05, "x_org (150, 4)", fontsize=18, family=CODE, color=INK, va="center")
    for j in range(4):
        pick = j in (0, 2)
        cell(ax, 0.25 + j * 0.85, 4.0, 0.85, 0.65, "%d번" % j, fc=GREEN_L if pick else "white", ec=GREEN if pick else FAINT,
             lw=2.2 if pick else 1.4, size=16)
        for r in range(3):
            cell(ax, 0.25 + j * 0.85, 3.4 - r * 0.6, 0.85, 0.6, "", fc=GREEN_L if pick else "white",
                 ec=GREEN if pick else FAINT, lw=1.2)
    ax.text(0.25, 1.75, "0번 꽃받침 길이, 2번 꽃잎 길이", fontsize=15, color=GREEN, va="center")
    ax.text(0.25, 1.15, "x_two = x_org[:, [0, 2]]", fontsize=16, family=CODE, color=GREEN, va="center")
    ax.text(0.25, 0.6, "모양 (150, 2)", fontsize=17, color=INK, va="center")
    # 나누기
    ax.text(4.25, 5.05, "150송이를 섞어 둘로", fontsize=18, color=INK, va="center")
    box(ax, 4.25, 3.6, 1.6, 0.8, fc=SLATE_LL, ec=SLATE, lw=2.2, rounded=False)
    box(ax, 5.85, 3.6, 1.6, 0.8, fc=PURPLE_L, ec=PURPLE, lw=2.2, rounded=False)
    ax.text(5.05, 4.0, "학습 75", fontsize=18, ha="center", va="center", color=SLATE_D, zorder=5)
    ax.text(6.65, 4.0, "검증 75", fontsize=18, ha="center", va="center", color=PURPLE, zorder=5)
    ax.text(4.25, 2.95, "학습 데이터의 품종 수", fontsize=16, color=INK, va="center")
    ax.text(4.25, 2.45, "23, 30, 22송이", fontsize=17, color=SLATE_D, va="center")
    # 출력 수
    ax.text(8.0, 5.05, "입력 수와 출력 수", fontsize=18, color=INK, va="center")
    steps = ["y_train", "set → {0, 1, 2}", "len → 3"]
    for k, s in enumerate(steps):
        ax.text(8.0, 4.35 - k * 0.7, s, fontsize=17, family=CODE, color=INK, va="center")
        if k < 2:
            arrow(ax, 8.35, 4.15 - k * 0.7, 8.35, 3.85 - k * 0.7, color=MUTED, lw=1.6)
    ax.text(8.0, 1.95, "n_input  = 2", fontsize=17, family=CODE, color=INK, va="center")
    ax.text(8.0, 1.45, "n_output = 3", fontsize=17, family=CODE, color=INK, va="center")
    note(ax, 7.85, 0.6, "nn.Linear(2, 3)", size=18, family=CODE)
    return image(fig)


@figure("9a-4", 560, 260)
def summary_9a():
    """외울 것: 클래스 수만큼 logit, 가중치 행렬 [3, 2], 파라미터 9, 출력 수 세기."""
    assert 2 * 3 + 3 == 9
    return memo([[(0.3, 3.0, "logit", ["클래스 수만큼", "붓꽃은 3개"], BLUE, BLUE, ()),
                  (3.55, 3.55, "가중치 행렬", ["weight [3, 2], bias [3]", "2 × 3 + 3 = 9개", "행 하나가 logit 하나"],
                   ORANGE, ORANGE, ()),
                  (7.35, 3.55, "입력 수와 출력 수", ["x_train.shape[1]", "len(list(set(y_train)))"], INK, INK, (0, 1))]],
                "x = [1, 2], 행 [1, 1]·[0, 1]·[1, " + M + "1], bias [" + M + "1, " + M + "1, 1] → logit [2, 1, 0]")


# 9b 소프트맥스의 성질

@figure("9b-1", 560, 290)
def softmax_steps():
    """logit [2, 1, 0] → e^(logit) [7.389, 2.718, 1] → 합 11.107 → 확률 [0.665, 0.245, 0.090]."""
    panels = [("logit", Z, BLUE, (0, 2.6), 0), ("e^(logit)", EZ, PURPLE, (0, 9.6), 3), ("확률", P, ORANGE, (0, 0.86), 3)]
    rects = [[0.04, 0.28, 0.26, 0.53], [0.37, 0.28, 0.26, 0.53], [0.71, 0.28, 0.26, 0.53]]
    titles = {1: "첫째 단원의 logit [2, 1, 0]", 2: "logit 마다 e 를 거듭제곱", 3: "세 값의 합 11.107",
              4: "합으로 나누면 확률", 5: "세 확률의 합은 1"}

    def draw(stage):
        plt, fig = new(580)
        head(fig, titles[stage])
        need = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3}[stage]
        for k in range(need):
            name, vals, color, lim, nd = panels[k]
            ax = class_axes(fig, rects[k], lim, name, color)
            bars(ax, [0, 1, 2], vals, color, nd, lim, texts=["7.389", "2.718", "1"] if k == 1 else None)
            if k < 2 and need > k + 1:
                fig.text(rects[k][0] + rects[k][2] + 0.035, 0.5, "→", fontsize=30, color=MUTED, ha="center", va="center")
        if stage >= 3:
            note(fig, 0.37, 0.07, "합 7.389 + 2.718 + 1 = 11.107", size=17, transform=fig.transFigure)
        if stage == 5:
            note(fig, 0.71, 0.07, "0.665 + 0.245 + 0.090 = 1", size=17, transform=fig.transFigure, bg=ORANGE_L)
        return image(fig)

    assert fx(EZ[0] + EZ[1] + EZ[2], 3) == "11.107"
    frames = [draw(k) for k in range(1, 6)]
    return frames, [2000, 2200, 2000, 2200, 2500]


@figure("9b-2", 560, 290)
def ratio_vs_softmax():
    """[2, 1, 0], [4, 2, 0], [12, 11, 10] 의 비율 그대로(회색)와 소프트맥스(주황)."""
    cases = [[2, 1, 0], [4, 2, 0], [12, 11, 10]]
    rat = [np.array(c, float) / sum(c) for c in cases]
    sms = [softmax(c) for c in cases]
    assert [fx(v, 3) for v in rat[0]] == ["0.667", "0.333", "0.000"] and np.allclose(rat[0], rat[1])
    assert [fx(v, 3) for v in rat[2]] == ["0.364", "0.333", "0.303"]
    assert [fx(v, 3) for v in sms[1]] == ["0.867", "0.117", "0.016"] and np.allclose(sms[0], sms[2])
    plt, fig = new(580)
    head(fig, "비율은 같아도 확률이 다르고, 같은 수를 더하면 확률이 같음", size=19)
    for k, c in enumerate(cases):
        rect = [0.04 + k * 0.33, 0.36, 0.28, 0.48]
        ax = class_axes(fig, rect, (0, 1.0), "logit " + str(c).replace(" ", " "), INK, xlabel=None)
        ax.bar(np.arange(3) - 0.2, rat[k], width=0.38, color=GRAY, zorder=3)
        ax.bar(np.arange(3) + 0.2, sms[k], width=0.38, color=ORANGE, zorder=3)
        fig.text(rect[0] + 0.005, 0.22, "비율 " + lst(rat[k], 3), fontsize=15, color=MUTED, ha="left", va="center")
        fig.text(rect[0] + 0.005, 0.14, "소프트맥스 " + lst(sms[k], 3), fontsize=15, color=ORANGE, ha="left", va="center")
    note(fig, 0.5, 0.045, "두 확률의 비 = e^(logit 의 차이)", size=17, ha="center", transform=fig.transFigure)
    return image(fig)


@figure("9b-3", 560, 270)
def soft_hard_sigmoid():
    """왼쪽: 가장 큰 값만 1([1, 0, 0])과 소프트맥스. 오른쪽: 시그모이드 곡선과 logit [2, 0] 의 소프트맥스."""
    two = softmax([2.0, 0.0])
    sig2 = 1 / (1 + math.exp(-2))
    assert fx(two[0], 4) == "0.8808" and fx(two[1], 4) == "0.1192" and abs(two[0] - sig2) < 1e-12
    plt, fig = new(540)
    ax = class_axes(fig, [0.05, 0.16, 0.4, 0.66], (0, 1.18), None, xlabel="클래스")
    ax.bar(np.arange(3) - 0.21, [1, 0, 0], width=0.34, color=GRAY, zorder=3)
    ax.bar(np.arange(3) + 0.21, P, width=0.34, color=ORANGE, zorder=3)
    for i in range(3):
        ax.text(i - 0.21, [1, 0, 0][i] + 0.03, ["1", "0", "0"][i], ha="center", va="bottom", fontsize=15, color=MUTED)
        ax.text(i + 0.25, P[i] + 0.03, fx(P[i], 3), ha="center", va="bottom", fontsize=15, color=ORANGE)
    fig.text(0.05, 0.92, "logit [2, 1, 0]", fontsize=19, weight="bold", color=INK, va="center")
    ax2 = fig.add_axes([0.58, 0.16, 0.38, 0.66])
    tidy(ax2)
    zz = np.linspace(-5, 5, 300)
    ax2.plot(zz, 1 / (1 + np.exp(-zz)), color=MUTED, lw=2.6)
    ax2.set_xlim(-5, 5)
    ax2.set_xticks([-4, -2, 0, 2, 4])
    ax2.set_xticklabels([M + "4", M + "2", "0", "2", "4"])
    ax2.set_ylim(0, 1.05)
    ax2.set_xlabel("logit 의 차이")
    ax2.set_ylabel("클래스 0 의 확률")
    ax2.scatter([2], [two[0]], s=110, color=ORANGE, zorder=6)
    ax2.annotate("", xy=(2, two[0]), xytext=(2, 0), arrowprops=dict(arrowstyle="-", color=ORANGE, lw=1.4, ls=":"))
    note(ax2, -4.6, 0.83, "σ(2) = 0.8808", size=17, color=ORANGE, bg="white", ec=ORANGE)
    fig.text(0.58, 0.92, "logit [2, 0] → [0.8808, 0.1192]", fontsize=19, weight="bold", color=INK, va="center")
    return image(fig)


@figure("9b-4", 560, 260)
def softmax_dim():
    """[2, 3] logit 에 dim=1 은 행마다, dim=0 은 열마다 합 1."""
    titles = {1: "데이터 2개의 logit, 모양 [2, 3]", 2: "dim=1: 행마다 합 1", 3: "dim=0: 열마다 합 1"}

    def table(ax, x0, y0, vals, nd, fc, ec, color):
        for r in range(2):
            for c in range(3):
                cell(ax, x0 + c * 1.15, y0 - r * 0.85, 1.15, 0.85, fx(vals[r][c], nd), fc=fc, ec=ec, color=color, size=19)

    def draw(stage):
        plt, fig, ax = board(520)
        ax.text(0.2, 4.85, titles[stage], fontsize=21, weight="bold", color=INK, va="center")
        ax.text(0.35, 4.05, "logit", fontsize=18, color=BLUE, va="center")
        for c in range(3):
            ax.text(0.95 + c * 1.15 + 0.575, 3.6, "클래스 %d" % c, fontsize=14, ha="center", color=MUTED)
        for r in range(2):
            ax.text(0.85, 2.6 - r * 0.85 + 0.42, "데이터 %d" % (r + 1), fontsize=14, ha="right", va="center", color=MUTED)
        table(ax, 0.95, 2.6, BATCH, 1, BLUE_L, BLUE, INK)
        if stage >= 2:
            vals = D1 if stage == 2 else D0
            arrow(ax, 4.6, 2.2, 5.2, 2.2, color=MUTED)
            ax.text(5.35, 4.05, "확률 dim=%d" % (1 if stage == 2 else 0), fontsize=18, color=ORANGE, va="center")
            table(ax, 5.35, 2.6, vals, 4, ORANGE_L, ORANGE, INK)
            if stage == 2:
                for r in range(2):
                    box(ax, 5.41, 2.67 - r * 0.85, 3.33, 0.71, fc="none", ec=GREEN, lw=3.0, z=8, rounded=False)
                    ax.text(9.05, 2.6 - r * 0.85 + 0.42, "합 1", fontsize=18, color=GREEN, va="center", weight="bold")
            else:
                for c in range(3):
                    box(ax, 5.42 + c * 1.15, 1.82, 1.01, 1.56, fc="none", ec=GREEN, lw=3.0, z=8, rounded=False)
                    ax.text(5.35 + c * 1.15 + 0.575, 1.3, "합 1", fontsize=17, color=GREEN, ha="center", weight="bold")
                note(ax, 5.35, 0.55, "행의 합 1.69, 1.31", size=17)
        return image(fig)

    assert np.allclose(D1.sum(1), 1) and np.allclose(D0.sum(0), 1)
    frames = [draw(k) for k in range(1, 4)]
    return frames, [2000, 2400, 2500]


@figure("9b-5", 560, 270)
def summary_9b():
    """외울 것: 식, 비율이 아님, 같은 수를 더해도 같음, 클래스 둘이면 시그모이드, dim=1."""
    return memo([[(0.3, 5.15, "식", ["e^(logit) ÷ 합", "[2, 1, 0] → [0.665, 0.245, 0.090]"], ORANGE, ORANGE, ()),
                  (5.75, 5.15, "확률의 비 = e^(logit 의 차이)", ["비율 그대로가 아님",
                                                           "[4, 2, 0] → [0.867, 0.117, 0.016]"], ORANGE, ORANGE, ())],
                 [(0.3, 5.15, "같은 수를 더해도 같음", ["[12, 11, 10] → [0.665, 0.245, 0.090]"], INK, INK, ()),
                  (5.75, 5.15, "클래스 둘이면", ["logit 차이의 시그모이드", "[2, 0] → σ(2) = 0.8808"], INK, INK, ())]],
                "배치 [데이터 수, 클래스 수] 는 dim=1: 행마다 합 1")


# 9c 로그 소프트맥스, NLLLoss, CrossEntropyLoss

@figure("9c-1", 560, 290)
def log_softmax_steps():
    """logit [2, 1, 0] 에서 log 11.107 = 2.4076 을 빼 로그 소프트맥스 [−0.4076, −1.4076, −2.4076]."""
    titles = {1: "logit [2, 1, 0]", 2: "log(7.389 + 2.718 + 1) = log 11.107 = 2.4076",
              3: "logit 마다 2.4076 을 뺌", 4: "e 를 거듭제곱하면 확률로 돌아감"}
    lim = (-2.9, 2.9)

    def draw(stage):
        plt, fig = new(580)
        head(fig, titles[stage], size=20)
        ax = fig.add_axes([0.07, 0.12, 0.55, 0.72])
        tidy(ax, grid=False)
        ax.set_xlim(-0.6, 2.6)
        ax.set_ylim(*lim)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["클래스 0", "클래스 1", "클래스 2"])
        ax.axhline(0, color=INK, lw=1.2)
        ax.set_yticks([-2, -1, 0, 1, 2])
        ax.set_yticklabels([M + "2", M + "1", "0", "1", "2"])
        bx = np.arange(3) - (0.2 if stage >= 3 else 0)
        ax.bar(bx, Z, width=0.36, color=BLUE, zorder=3)
        for i in range(3):
            if Z[i] >= 1:
                ax.text(bx[i], Z[i] - 0.1, num(Z[i], 0), ha="center", va="top", fontsize=17, color="white", weight="bold",
                        zorder=6)
            else:
                ax.text(bx[i], Z[i] + 0.08, num(Z[i], 0), ha="center", va="bottom", fontsize=17, color=BLUE)
        if stage >= 2:
            ax.axhline(lse(Z), color=GRAY, lw=2.4, ls="--", zorder=2)
            ax.text(2.55, lse(Z) + 0.12, "2.4076", ha="right", va="bottom", fontsize=16, color=MUTED)
        if stage >= 3:
            ax.bar(np.arange(3) + 0.2, LS, width=0.36, color=PURPLE, zorder=3)
            for i in range(3):
                ax.text(i + 0.2, LS[i] - 0.08, fx(LS[i], 4), ha="center", va="top", fontsize=15, color=PURPLE)
        if stage >= 3:
            note(fig, 0.66, 0.66, "이웃한 두 값의 차이는\nlogit 처럼 1", size=17, transform=fig.transFigure)
        if stage == 4:
            note(fig, 0.66, 0.36, "e^(" + M + "0.4076) = 0.665\ne^(" + M + "1.4076) = 0.245\ne^(" + M + "2.4076) = 0.090",
                 size=17, transform=fig.transFigure, bg=ORANGE_L)
        return image(fig)

    assert [fx(math.exp(v), 3) for v in LS] == ["0.665", "0.245", "0.090"]
    assert np.allclose(np.diff(LS), [-1, -1])
    frames = [draw(k) for k in range(1, 5)]
    return frames, [2000, 2200, 2400, 2500]


@figure("9c-2", 560, 260)
def nll_pick():
    """로그 소프트맥스 [2, 3] 에서 정답 [0, 2] 칸을 골라 부호를 바꿔 평균 0.4513."""
    labels = [0, 2]
    titles = {1: "로그 소프트맥스 값과 정답 [0, 2]", 2: "데이터 1: 0번 칸", 3: "데이터 2: 2번 칸", 4: "부호를 바꿔 평균"}
    picks = [LSB[0, 0], LSB[1, 2]]
    assert [fx(v, 4) for v in picks] == [M + "0.4076", M + "0.4949"]

    def draw(stage):
        plt, fig, ax = board(520)
        ax.text(0.2, 4.85, titles[stage], fontsize=21, weight="bold", color=INK, va="center")
        for c in range(3):
            ax.text(1.55 + c * 1.6 + 0.8, 3.95, "클래스 %d" % c, fontsize=15, ha="center", va="center", color=MUTED)
        ax.text(7.2, 3.95, "정답", fontsize=16, ha="center", va="center", color=MUTED)
        for r in range(2):
            y = 2.75 - r * 1.0
            ax.text(1.45, y + 0.45, "데이터 %d" % (r + 1), fontsize=15, ha="right", va="center", color=MUTED)
            for c in range(3):
                chosen = (stage >= 2 and r == 0 and c == labels[0]) or (stage >= 3 and r == 1 and c == labels[1])
                cell(ax, 1.55 + c * 1.6, y, 1.6, 0.9, fx(LSB[r, c], 4), fc=PURPLE_L, ec=GREEN if chosen else PURPLE,
                     lw=4.0 if chosen else 1.4, size=19)
            cell(ax, 6.75, y, 0.9, 0.9, str(labels[r]), fc="white", ec=FAINT, size=20)
        if stage == 4:
            note(ax, 0.5, 0.75, "(0.4076 + 0.4949) ÷ 2 = 0.4513", size=21, color=GREEN, bg="white", ec=GREEN)
        return image(fig)

    frames = [draw(k) for k in range(1, 5)]
    return frames, [2000, 2200, 2200, 2500]


@figure("9c-3", 560, 270)
def patterns():
    """세 패턴에서 소프트맥스와 log 를 계산하는 자리. 패턴 3 은 빨간 테두리."""
    assert fx(-LS[0], 4) == "0.4076"
    plt, fig, ax = board(540)
    rows = [("패턴 1", "Linear", "logit", "CrossEntropyLoss", "로그 소프트맥스 + 정답 칸", INK),
            ("패턴 2", "Linear → LogSoftmax(dim=1)", "로그 확률", "NLLLoss", "정답 칸, 확률은 torch.exp", INK),
            ("패턴 3", "Linear → Softmax(dim=1)", "확률", "torch.log → NLLLoss", "권하지 않음", RED)]
    for k, (name, model, out, loss, extra, edge) in enumerate(rows):
        y = 4.15 - k * 1.55
        if edge == RED:
            box(ax, 0.1, y - 0.2, 11.0, 1.35, fc="none", ec=RED, lw=2.6, z=1)
        ax.text(0.3, y + 0.48, name, fontsize=18, weight="bold", color=edge, va="center")
        box(ax, 1.45, y, 3.6, 0.95, fc=NOTE, ec=GRAY, lw=1.8)
        ax.text(3.25, y + 0.48, model, fontsize=15, family=CODE, ha="center", va="center", zorder=5)
        arrow(ax, 5.1, y + 0.48, 5.42, y + 0.48)
        ax.text(6.0, y + 0.48, out, fontsize=16, ha="center", va="center", color=INK)
        arrow(ax, 6.55, y + 0.48, 7.0, y + 0.48)
        box(ax, 7.05, y, 3.9, 0.95, fc=GREEN_L, ec=GREEN, lw=1.8)
        ax.text(9.0, y + 0.66, loss, fontsize=15, family=CODE, ha="center", va="center", zorder=5)
        ax.text(9.0, y + 0.26, extra, fontsize=13, ha="center", va="center", color=MUTED, zorder=5)
    note(ax, 0.3, 0.3, "logit [2, 1, 0], 정답 0 에서 세 패턴 모두 0.4076", size=17)
    return image(fig)


@figure("9c-4", 560, 270)
def big_logits():
    """logit [1000, 999, 995] 를 float32 로 바로 거듭제곱하면 inf, 1000 을 빼면 [1, 0.3679, 0.0067]."""
    big = np.array([1000.0, 999.0, 995.0])
    with np.errstate(over="ignore", invalid="ignore"):
        raw = np.exp(big.astype(np.float32))
        div = raw / raw.sum()
    assert np.all(np.isinf(raw)) and np.all(np.isnan(div))
    sh = np.exp(big - big.max())
    assert [fx(v, 4) for v in sh] == ["1.0000", "0.3679", "0.0067"] and fx(sh.sum(), 4) == "1.3746"
    assert fx(math.log(sh.sum()), 4) == "0.3182" and fx(-log_softmax(big)[0], 4) == "0.3182"
    plt, fig = new(540)
    head(fig, "logit [1000, 999, 995]", size=20)
    fig.text(0.04, 0.8, "float32 로 바로 거듭제곱", fontsize=18, color=RED, va="center", weight="bold")
    for k, (lhs, v) in enumerate((("e^1000", "inf"), ("e^999", "inf"), ("e^995", "inf"))):
        fig.text(0.06, 0.66 - k * 0.11, lhs + "  →  " + v, fontsize=19, color=RED, va="center", family=CODE)
    fig.text(0.06, 0.3, "합으로 나누면 nan", fontsize=19, color=RED, va="center")
    ax = class_axes(fig, [0.5, 0.2, 0.26, 0.56], (0, 1.2), "1000 을 뺀 [0, " + M + "1, " + M + "5]", SLATE, xlabel="클래스")
    bars(ax, [0, 1, 2], sh, SLATE, 4, (0, 1.2), label_size=15, texts=["1", "0.3679", "0.0067"])
    note(fig, 0.79, 0.62, "합 1.3746", size=17, transform=fig.transFigure)
    note(fig, 0.79, 0.47, "log 1.3746\n= 0.3182", size=17, transform=fig.transFigure)
    note(fig, 0.79, 0.27, "정답 0 의 손실\n0.3182", size=17, transform=fig.transFigure, color=GREEN, bg="white", ec=GREEN)
    return image(fig)


@figure("9c-5", 560, 270)
def summary_9c():
    """외울 것: 로그 소프트맥스 식과 값, NLLLoss, CrossEntropyLoss = LogSoftmax + NLLLoss."""
    return memo([[(0.3, 5.3, "로그 소프트맥스", ["logit " + M + " log(e^(logit) 의 합)",
                                              "[2, 1, 0] → [" + M + "0.4076, " + M + "1.4076, " + M + "2.4076]"],
                   PURPLE, PURPLE, ()),
                  (5.9, 5.0, "NLLLoss", ["정답 칸을 골라 부호를 바꿔 평균", "입력은 로그 확률"], GREEN, GREEN, ())],
                 [(0.3, 10.6, "CrossEntropyLoss = LogSoftmax + NLLLoss",
                   ["패턴 2 의 확률은 torch.exp(outputs)", "패턴 3 (Softmax 뒤 torch.log) 은 확률이 0 이 되면 log 0 = " + M + "inf"],
                   INK, INK, ())]],
                "logit [2, 1, 0], 정답 0: 세 패턴 모두 0.4076")


# 9d KL divergence

@figure("9d-1", 560, 270)
def kl_onehot():
    """P = [1, 0, 0], Q = [0.665, 0.245, 0.090] 의 클래스마다 P × log(P ÷ Q) 와 합 0.4076."""
    contrib = [PD[i] * math.log(PD[i] / P[i]) if PD[i] > 0 else 0.0 for i in range(3)]
    assert [fx(v, 4) for v in contrib] == ["0.4076", "0.0000", "0.0000"] and fx(sum(contrib), 4) == "0.4076"
    plt, fig = new(540)
    ax = class_axes(fig, [0.05, 0.17, 0.42, 0.64], (0, 1.22), None)
    ax.bar(np.arange(3) - 0.2, PD, width=0.38, color=GREEN, zorder=3)
    ax.bar(np.arange(3) + 0.2, P, width=0.38, color=ORANGE, zorder=3)
    for i in range(3):
        ax.text(i - 0.2, PD[i] + 0.03, num(PD[i], 0), ha="center", va="bottom", fontsize=16, color=GREEN)
        ax.text(i + 0.2, P[i] + 0.03, fx(P[i], 3), ha="center", va="bottom", fontsize=15, color=ORANGE)
    fig.text(0.05, 0.92, "정답 분포 P 와 예측 분포 Q", fontsize=19, weight="bold", color=INK, va="center")
    ax2 = class_axes(fig, [0.57, 0.17, 0.25, 0.64], (0, 0.55), None)
    bars(ax2, [0, 1, 2], contrib, PURPLE, 4, (0, 0.55), label_size=15, texts=["0.4076", "0", "0"])
    fig.text(0.57, 0.92, "P × log(P ÷ Q)", fontsize=19, weight="bold", color=PURPLE, va="center")
    note(fig, 0.845, 0.55, "합\nKL(P‖Q)\n= 0.4076\n= 교차 엔트로피", size=16, transform=fig.transFigure,
         color=PURPLE, bg="white", ec=PURPLE)
    return image(fig)


@figure("9d-2", 560, 270)
def kl_both_ways():
    """P = [0.6, 0.3, 0.1], Q = [0.7, 0.2, 0.1] 로 KL(P‖Q) = 0.0291, KL(Q‖P) = 0.0268."""
    pq = [P2[i] * math.log(P2[i] / QN[i]) for i in range(3)]
    qp = [QN[i] * math.log(QN[i] / P2[i]) for i in range(3)]
    assert [fx(v, 4) for v in pq] == [M + "0.0925", "0.1216", "0.0000"] and fx(sum(pq), 4) == "0.0291"
    assert [fx(v, 4) for v in qp] == ["0.1079", M + "0.0811", "0.0000"] and fx(sum(qp), 4) == "0.0268"
    plt, fig = new(540)
    ax = class_axes(fig, [0.04, 0.17, 0.27, 0.6], (0, 0.85), None)
    ax.bar(np.arange(3) - 0.2, P2, width=0.38, color=GREEN, zorder=3)
    ax.bar(np.arange(3) + 0.2, QN, width=0.38, color=ORANGE, zorder=3)
    for i in range(3):
        ax.text(i - 0.2, P2[i] + 0.02, fx(P2[i], 1), ha="center", va="bottom", fontsize=15, color=GREEN)
        ax.text(i + 0.2, QN[i] + 0.02, fx(QN[i], 1), ha="center", va="bottom", fontsize=15, color=ORANGE)
    fig.text(0.04, 0.9, "P 와 Q", fontsize=19, weight="bold", color=INK, va="center")
    for k, (vals, title, total) in enumerate(((pq, "KL(P‖Q)", sum(pq)), (qp, "KL(Q‖P)", sum(qp)))):
        rect = [0.39 + k * 0.31, 0.17, 0.25, 0.6]
        axk = class_axes(fig, rect, (-0.16, 0.18), None)
        bars(axk, [0, 1, 2], vals, PURPLE, 4, (-0.16, 0.18), label_size=14, texts=[fx(vals[0], 4), fx(vals[1], 4), "0"])
        fig.text(rect[0], 0.9, title + " = " + fx(total, 4), fontsize=19, weight="bold", color=PURPLE, va="center")
    return image(fig)


@figure("9d-3", 560, 230)
def kl_div_args():
    """F.kl_div(torch.log(Q), P, reduction='sum') 의 두 인자와 KL(P‖Q) 의 자리. 결과 0.3567."""
    assert fx(kl(PD, QN), 4) == "0.3567"
    plt, fig, ax = board(460)
    spans = seq(ax, fig, 0.4, 3.9, [("F.kl_div(", INK, None), ("torch.log(Q)", INK, ORANGE_L), (", ", INK, None),
                                    ("P", INK, GREEN_L), (", reduction='sum')", INK, None)], size=21, family=CODE)
    qx = sum(spans[1]) / 2
    px = sum(spans[3]) / 2
    arrow(ax, qx, 3.55, qx, 3.0, color=ORANGE)
    arrow(ax, px, 3.55, px, 3.0, color=GREEN)
    note(ax, px - 0.4, 2.65, "첫째: 예측 분포의 로그 확률", size=17, color=ORANGE, bg="white", ec=ORANGE, ha="right")
    note(ax, px - 0.12, 2.65, "둘째: 정답 분포의 확률", size=17, color=GREEN, bg="white", ec=GREEN, ha="left")
    seq(ax, fig, 0.4, 1.3, [("KL(", INK, None), ("P", INK, GREEN_L), ("‖", INK, None), ("Q", INK, ORANGE_L),
                            (") = 클래스마다 ", INK, None), ("P", INK, GREEN_L), (" × log(", INK, None), ("P", INK, GREEN_L),
                            (" ÷ ", INK, None), ("Q", INK, ORANGE_L), (") 의 합 = 0.3567", INK, None)], size=21)
    ax.text(0.4, 0.5, "P = [1, 0, 0], Q = [0.7, 0.2, 0.1]", fontsize=16, color=MUTED, va="center")
    return image(fig)


@figure("9d-4", 560, 270)
def summary_9d():
    """외울 것: KL 식, 원-핫 P 이면 −log Q, 방향을 바꾸면 다름, F.kl_div 인자."""
    return memo([[(0.3, 5.2, "KL(P‖Q)", ["클래스마다 P × log(P ÷ Q) 의 합", "두 분포가 같으면 0"], INK, INK, ()),
                  (5.85, 5.05, "원-핫 P", [M + "log Q(정답) = 교차 엔트로피", "Q = [0.7, 0.2, 0.1] → 0.3567"],
                   GREEN, GREEN, ())],
                 [(0.3, 10.6, "방향을 바꾸면 다름",
                   ["P = [0.6, 0.3, 0.1], Q = [0.7, 0.2, 0.1]: KL(P‖Q) 0.0291, KL(Q‖P) 0.0268"], PURPLE, PURPLE, ())]],
                "F.kl_div(torch.log(Q), P, reduction='sum'), 배치 평균은 'batchmean'")


# 9e 예측 클래스와 정확도

@figure("9e-1", 560, 290)
def max_rows():
    """[4, 3] logit 에서 행마다 가장 큰 칸을 골라 values·indices, 정답과 견줌."""
    titles = {1: "logit 모양 [4, 3] 과 정답", 2: "데이터 1: 2.0, 클래스 0", 3: "데이터 2·3: 클래스 1, 클래스 2",
              4: "데이터 4: 클래스 1", 5: "정답과 견주기"}
    done = {1: 0, 2: 1, 3: 3, 4: 4, 5: 4}

    def draw(stage):
        plt, fig, ax = board(580)
        ax.text(0.2, 5.5, titles[stage], fontsize=21, weight="bold", color=INK, va="center")
        heads = ["클래스 0", "클래스 1", "클래스 2", "values", "indices", "정답"]
        xs = [1.5, 2.75, 4.0, 5.6, 6.85, 8.4]
        for x, h in zip(xs, heads):
            ax.text(x + 0.575, 4.95, h, fontsize=15, ha="center", va="center", color=MUTED)
        for r in range(4):
            y = 3.85 - r * 0.95
            ax.text(1.35, y + 0.42, "데이터 %d" % (r + 1), fontsize=15, ha="right", va="center", color=MUTED)
            for c in range(3):
                top = r < done[stage] and c == PRED4[r]
                cell(ax, xs[c], y, 1.15, 0.85, fx(OUT4[r, c], 1), fc=YELLOW if top else BLUE_L, ec=BLUE, lw=1.4, size=19)
            if r < done[stage]:
                cell(ax, xs[3], y, 1.15, 0.85, fx(OUT4[r].max(), 1), fc="white", ec=FAINT, size=19)
                hit = PRED4[r] == LAB4[r]
                fc = (GREEN_L if hit else RED_L) if stage == 5 else "white"
                ec = (GREEN if hit else RED) if stage == 5 else FAINT
                cell(ax, xs[4], y, 1.15, 0.85, str(PRED4[r]), fc=fc, ec=ec, lw=2.6 if stage == 5 else 1.4, size=20,
                     weight="bold")
            cell(ax, xs[5], y, 1.15, 0.85, str(LAB4[r]), fc="white", ec=FAINT, size=20)
        if stage == 5:
            note(ax, 1.5, 0.3, "맞힌 데이터 1, 2", size=18, color=GREEN, bg="white", ec=GREEN)
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2000, 2000, 2200, 2200, 2500]


@figure("9e-2", 560, 260)
def logit_vs_prob():
    """데이터 4 의 logit [1.5, 1.8, 0.4] 와 확률 [0.373, 0.503, 0.124]. 가장 큰 칸은 둘 다 클래스 1."""
    p4 = softmax(OUT4[3])
    assert [fx(v, 3) for v in p4] == ["0.373", "0.503", "0.124"] and p4.argmax() == OUT4[3].argmax() == 1
    plt, fig = new(520)
    for k, (vals, color, lim, nd, title) in enumerate(((OUT4[3], BLUE, (0, 2.2), 1, "logit"),
                                                      (p4, ORANGE, (0, 0.62), 3, "확률"))):
        rect = [0.06 + k * 0.52, 0.17, 0.38, 0.62]
        ax = class_axes(fig, rect, lim, title, color)
        ax.axvspan(0.55, 1.45, color=YELLOW, zorder=0)
        bars(ax, [0, 1, 2], vals, color, nd, lim)
    fig.text(0.5, 0.5, "소프트맥스\n→", fontsize=19, color=MUTED, ha="center", va="center")
    fig.text(0.06, 0.92, "데이터 4", fontsize=19, weight="bold", color=INK, va="center")
    return image(fig)


@figure("9e-3", 560, 230)
def accuracy_count():
    """예측 [0, 1, 2, 1] 과 정답 [0, 1, 1, 0] 을 견줘 맞힌 수 2, 정확도 0.5."""
    same = PRED4 == LAB4
    assert list(same) == [True, True, False, False]
    plt, fig, ax = board(460)
    rows = [("예측", [str(v) for v in PRED4]), ("정답", [str(v) for v in LAB4]),
            ("같은가", ["True" if s else "False" for s in same])]
    for r, (name, vals) in enumerate(rows):
        y = 3.4 - r * 0.95
        ax.text(1.55, y + 0.42, name, fontsize=17, ha="right", va="center", color=MUTED)
        for c, v in enumerate(vals):
            if r == 2:
                fc, ec, color = (GREEN_L, GREEN, GREEN) if same[c] else (RED_L, RED, RED)
            else:
                fc, ec, color = "white", FAINT, INK
            cell(ax, 1.75 + c * 1.35, y, 1.35, 0.85, v, fc=fc, ec=ec, color=color, size=19, lw=2.2 if r == 2 else 1.4)
    note(ax, 7.6, 2.9, "맞힌 수 2", size=20, color=GREEN, bg="white", ec=GREEN)
    note(ax, 7.6, 1.9, "2 ÷ 4 = 0.5", size=20)
    return image(fig)


@figure("9e-4", 560, 270)
def summary_9e():
    """외울 것: torch.max 의 두 값, 소프트맥스와 예측, 정확도."""
    return memo([[(0.3, 5.3, "torch.max(outputs, 1)", ["(values, indices)", "예측은 [1] 이나 _, predicted",
                                                       "outputs.argmax(1) 과 같음"], INK, INK, ()),
                  (5.9, 5.0, "소프트맥스와 예측", ["순서를 지켜 예측이 같음", "inputs[i:i+1] 은 [1, 13]"], INK, INK, ())],
                 [(0.3, 10.6, "정확도", ["(predicted == labels).sum().item() ÷ len(labels)", "[0, 1, 2, 1] 과 [0, 1, 1, 0] → 2 ÷ 4 = 0.5"],
                   GREEN, GREEN, (0,))]],
                "가장 큰 logit 의 위치가 예측 클래스")


# 9f 3 × 3 혼동 행렬과 클래스별 지표

def matrix(ax, x0, y0, stage_fill=True, colour=False, band=None, size=20, w=1.55, h=0.9):
    """혼동 행렬 표. y0 은 0번 행의 가운데 높이. band 는 ("row"|"col", k) 이면 그 줄을 노랑 바탕으로."""
    top = y0 + h / 2
    ax.text(x0 + 1.5 * w, top + 0.85, "예측", fontsize=17, ha="center", va="center", color=MUTED)
    ax.text(x0 - 1.75, y0 - h, "실제", fontsize=17, ha="center", va="center", color=MUTED, rotation=90)
    for c in range(3):
        ax.text(x0 + c * w + w / 2, top + 0.35, NAMES[c], fontsize=15, ha="center", va="center", color=INK)
    for r in range(3):
        y = y0 - h / 2 - r * h
        ax.text(x0 - 0.15, y + h / 2, NAMES[r], fontsize=15, ha="right", va="center", color=INK)
        for c in range(3):
            fc, ec, color = "white", FAINT, INK
            if band and ((band[0] == "row" and band[1] == r) or (band[0] == "col" and band[1] == c)):
                fc = YELLOW
            if colour and r == c:
                fc, ec, color = GREEN_L, GREEN, GREEN
            elif colour and CM[r, c] > 0:
                fc, ec, color = RED_L, RED, RED
            cell(ax, x0 + c * w, y, w, h, str(CM[r, c]) if stage_fill else "", fc=fc, ec=ec, color=color, size=size,
                 lw=2.2 if colour and (r == c or CM[r, c] > 0) else 1.4)
        if band:
            cell(ax, x0 + r * w, y0 - h / 2 - r * h, w, h, str(CM[r, r]), fc=GREEN_L if not (
                (band[0] == "row" and band[1] == r) or (band[0] == "col" and band[1] == r)) else YELLOW, ec=GREEN,
                color=GREEN, size=size, lw=2.6)


@figure("9f-1", 560, 270)
def confusion_3x3():
    """붓꽃 60송이 3 × 3 혼동 행렬, 대각선이 맞힌 수, 정확도 54 ÷ 60 = 0.9."""
    titles = {1: "행은 실제, 열은 예측", 2: "칸마다 송이 수", 3: "대각선이 맞힌 수", 4: "정확도"}

    def draw(stage):
        plt, fig, ax = board(540)
        ax.text(0.2, 5.1, titles[stage], fontsize=21, weight="bold", color=INK, va="center")
        matrix(ax, 2.3, 3.4, stage_fill=stage >= 2, colour=stage >= 3)
        if stage == 4:
            note(ax, 7.4, 2.5, "(20 + 16 + 18) ÷ 60\n= 0.9", size=21, color=GREEN, bg="white", ec=GREEN)
        return image(fig)

    frames = [draw(k) for k in range(1, 5)]
    return frames, [2000, 2200, 2200, 2500]


@figure("9f-2", 560, 270)
def per_class():
    """versicolor 열·행, virginica 열·행으로 정밀도·재현율."""
    specs = [(("col", 1), "versicolor 정밀도: 열", "16 ÷ (0 + 16 + 2)\n= 0.889"),
             (("row", 1), "versicolor 재현율: 행", "16 ÷ (0 + 16 + 4)\n= 0.8"),
             (("col", 2), "virginica 정밀도: 열", "18 ÷ (0 + 4 + 18)\n= 0.818"),
             (("row", 2), "virginica 재현율: 행", "18 ÷ (0 + 2 + 18)\n= 0.9")]
    assert fx(16 / 18, 3) == "0.889" and 16 / 20 == 0.8 and fx(18 / 22, 3) == "0.818" and 18 / 20 == 0.9
    assert CM[:, 1].sum() == 18 and CM[1].sum() == 20 and CM[:, 2].sum() == 22 and CM[2].sum() == 20

    def draw(k):
        band, title, text = specs[k]
        plt, fig, ax = board(540)
        ax.text(0.2, 5.1, title, fontsize=21, weight="bold", color=INK, va="center")
        matrix(ax, 2.3, 3.4, band=band)
        note(ax, 7.4, 2.5, text, size=21)
        return image(fig)

    frames = [draw(k) for k in range(4)]
    return frames, [2200, 2200, 2200, 2500]


@figure("9f-3", 560, 260)
def per_class_table():
    """클래스별 정밀도·재현율·F1 과 행·열을 바꿔 읽었을 때 versicolor 의 두 값."""
    sp, sr = CM[1, 1] / CM[1].sum(), CM[1, 1] / CM[:, 1].sum()
    assert fx(sp, 3) == "0.800" and fx(sr, 3) == "0.889" and fx(2 * sp * sr / (sp + sr), 3) == "0.842"
    plt, fig, ax = board(520)
    heads = ["클래스", "정밀도", "재현율", "F1 점수"]
    xs = [0.3, 2.3, 3.6, 4.9]
    ws = [2.0, 1.3, 1.3, 1.3]
    for x, w, h in zip(xs, ws, heads):
        cell(ax, x, 3.9, w, 0.75, h, fc=NOTE, ec=FAINT, size=16)
    for r in range(3):
        y = 3.15 - r * 0.75
        cell(ax, xs[0], y, ws[0], 0.75, NAMES[r], size=17)
        for k, v in enumerate((PREC[r], REC[r], F1[r])):
            cell(ax, xs[k + 1], y, ws[k + 1], 0.75, num(v, 3), color=GREEN, size=18)
    ax.text(0.3, 4.95, "바르게 읽은 값", fontsize=19, weight="bold", color=GREEN, va="center")
    ax.text(7.0, 4.95, "행과 열을 바꿔 읽으면", fontsize=19, weight="bold", color=RED, va="center")
    ax.text(7.0, 4.15, "versicolor", fontsize=18, color=INK, va="center")
    ax.text(7.0, 3.55, "정밀도 16 ÷ 20 = 0.8", fontsize=18, color=RED, va="center")
    ax.text(7.0, 2.95, "재현율 16 ÷ 18 = 0.889", fontsize=18, color=RED, va="center")
    note(ax, 7.0, 1.85, "정확도 0.9, F1 0.842 는 같음", size=16)
    return image(fig)


@figure("9f-4", 560, 270)
def summary_9f():
    """외울 것: 행 실제·열 예측, 정확도, 정밀도는 열, 재현율은 행, F1, 맞바뀜."""
    return memo([[(0.3, 5.2, "혼동 행렬", ["행은 실제, 열은 예측", "대각선이 맞힌 수", "정확도 = 대각선의 합 ÷ 전체"],
                   GREEN, GREEN, ()),
                  (5.85, 5.05, "클래스 k", ["정밀도 = 대각선 칸 ÷ k 열의 합", "재현율 = 대각선 칸 ÷ k 행의 합",
                                          "F1 = 둘의 조화평균"], INK, INK, ())]],
                "행과 열을 바꿔 읽으면 정밀도와 재현율이 맞바뀜")


# 9g 붓꽃 학습 코드와 wine 다층 신경망

@figure("9g-1", 560, 260)
def first_epoch():
    """가중치·bias 를 1 로 채운 첫 에폭: logit 7.6 셋, 확률 1/3, 손실 log 3, 예측 모두 0, 정확도 23/75."""
    logit = 5.0 + 1.6 + 1
    assert fx(logit, 1) == "7.6" and fx(math.log(3), 4) == "1.0986" and fx(23 / 75, 5) == "0.30667"
    plt, fig = new(520)
    ax = class_axes(fig, [0.04, 0.17, 0.26, 0.6], (0, 9.0), "logit", BLUE)
    bars(ax, [0, 1, 2], [logit] * 3, BLUE, 1, (0, 9.0))
    ax2 = class_axes(fig, [0.37, 0.17, 0.26, 0.6], (0, 0.45), "확률", ORANGE)
    ax2.bar([0, 1, 2], [1 / 3] * 3, color=ORANGE, width=0.6, zorder=3)
    for i in range(3):
        ax2.text(i, 1 / 3 + 0.015, "1/3", ha="center", va="bottom", fontsize=17)
    fig.text(0.04, 0.92, "송이 [5.0, 1.6], 가중치와 bias 는 모두 1", fontsize=18, weight="bold", color=INK, va="center")
    note(fig, 0.68, 0.7, "손실 " + M + "log(1/3)\n= log 3 = 1.0986", size=17, transform=fig.transFigure)
    note(fig, 0.68, 0.38, "torch.max 는 첫 위치 0\n예측이 모두 0\n23 ÷ 75 = 0.30667", size=17, transform=fig.transFigure)
    return image(fig)


@figure("9g-2", 560, 250)
def two_vs_four():
    """특징 2개와 4개: 검증 손실 0.20501 과 0.14243, 정확도 0.96 과 0.96."""
    loss, acc = [0.20501, 0.14243], [0.96, 0.96]
    assert loss[1] < loss[0] and acc[0] == acc[1]
    plt, fig = new(500)
    for k, (vals, lim, title, nd) in enumerate(((loss, (0, 0.26), "검증 손실", 5), (acc, (0, 1.15), "검증 정확도", 2))):
        rect = [0.07 + k * 0.48, 0.2, 0.36, 0.6]
        ax = class_axes(fig, rect, lim, title, INK, labels=("특징 2개", "특징 4개"), xlabel=None)
        ax.set_xlim(-0.6, 1.6)
        ax.bar([0, 1], vals, color=[GRAY, PURPLE], width=0.55, zorder=3)
        for i, v in enumerate(vals):
            ax.text(i, v + 0.03 * lim[1], fx(v, nd), ha="center", va="bottom", fontsize=18)
    fig.text(0.5, 0.05, "노트북 01 의 에폭 번호 9,000 기록", fontsize=16, color=MUTED, ha="center", va="center")
    return image(fig)


@figure("9g-3", 560, 260)
def wine_layers():
    """13 → fc1 → 64 → fc2 → 32 → fc3 → 3. 층별 파라미터 896, 2,080, 99, 합 3,075."""
    layers = [(13, 64), (64, 32), (32, 3)]
    counts = [a * b + b for a, b in layers]
    assert counts == [896, 2080, 99] and sum(counts) == 3075
    labels = ["896", "2,080", "99"]
    titles = {1: "fc1: 13 → 64", 2: "fc2: 64 → 32", 3: "fc3: 32 → 3", 4: "합 3,075"}

    def draw(stage):
        plt, fig, ax = board(520)
        ax.text(0.2, 4.85, titles[stage], fontsize=21, weight="bold", color=INK, va="center")
        sizes = ["13", "64", "32", "3"]
        xs = [0.3, 3.15, 6.0, 8.85]
        for k, s in enumerate(sizes):
            cell(ax, xs[k], 2.7, 0.95, 0.85, s, fc="white", ec=FAINT, size=20)
        for k in range(3):
            x = xs[k] + 1.15
            on = stage > k
            box(ax, x, 2.55, 1.55, 1.15, fc=SLATE_LL if on else "white", ec=SLATE if on else FAINT, lw=2.2)
            ax.text(x + 0.775, 3.12, "fc%d" % (k + 1), fontsize=18, ha="center", va="center", color=SLATE_D, zorder=5)
            if on:
                ax.text(x + 0.775, 2.15, labels[k] + "개", fontsize=18, ha="center", va="center", color=SLATE_D)
            if k < 2:
                box(ax, x + 0.05, 1.05, 1.45, 0.6, fc="white", ec=GRAY, lw=1.6, ls="--")
                ax.text(x + 0.775, 1.35, "ReLU", fontsize=15, ha="center", va="center", color=MUTED, zorder=5)
        if stage == 4:
            note(ax, 2.6, 0.35, "896 + 2,080 + 99 = 3,075, ReLU·Dropout 은 0개", size=18)
        return image(fig)

    frames = [draw(k) for k in range(1, 5)]
    return frames, [2200, 2200, 2200, 2500]


@figure("9g-4", 560, 260)
def scaler_result():
    """fit_transform 의 결과를 받지 않으면 x_train 이 원래 값(마지막 특징 780, 1150, 570)으로 남음."""
    first3 = [780, 1150, 570]
    assert max(first3) > 1000
    plt, fig, ax = board(520)
    box(ax, 0.3, 2.75, 10.6, 1.95, fc=RED_L, ec=RED, lw=2.2)
    ax.text(0.6, 4.25, "scaler.fit_transform(x_train)", fontsize=19, family=CODE, color=RED, va="center", zorder=5)
    ax.text(0.6, 3.6, "표준화한 배열을 돌려주지만 받지 않아 버려짐", fontsize=17, color=INK, va="center", zorder=5)
    ax.text(0.6, 3.1, "x_train 의 마지막 특징은 780, 1150, 570 … 으로 남음", fontsize=17, color=INK, va="center", zorder=5)
    box(ax, 0.3, 0.45, 10.6, 1.95, fc=GREEN_L, ec=GREEN, lw=2.2)
    ax.text(0.6, 1.95, "x_train = scaler.fit_transform(x_train)", fontsize=19, family=CODE, color=GREEN, va="center",
            zorder=5)
    ax.text(0.6, 1.3, "돌려준 값을 받아 x_train 이 표준화한 값으로 바뀜", fontsize=17, color=INK, va="center", zorder=5)
    ax.text(0.6, 0.8, "x_val·x_test 는 scaler.transform", fontsize=17, color=INK, va="center", zorder=5)
    return image(fig)


@figure("9g-5", 560, 290)
def summary_9g():
    """외울 것: 붓꽃 코드와 wine 코드."""
    assert fx(math.log(3), 4) == "1.0986" and 106 + 36 + 36 == 178
    return memo([[(0.3, 5.2, "붓꽃 코드", ["inputs .float(), labels .long()", "logit 이 모두 같으면 log 3 = 1.0986",
                                         "첫 정확도 23 ÷ 75", "특징 넷: 손실 0.205 → 0.142"], INK, INK, ()),
                  (5.85, 5.05, "wine 코드", ["13-64-32-3 = 3,075개", "분할 106, 36, 36", "model.eval(), torch.no_grad()",
                                           "x_train = scaler.fit_transform(...)"], INK, INK, (2, 3))]],
                "forward 에서 부르지 않은 Dropout 은 계산에 쓰이지 않음")


# 세 수준으로 다시 보기 블록 그림. 화면 520×280(파일 1040×560), 글자 22 이상은 tools/ai_art/levels.py 를 따름.
# 그림 이름은 <단원>-<단계 번호><수준 번호>(7살 1, 15살 2, 20살 3). 색 뜻은 그 단원의 뜻을 그대로 씀.

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
    ax.add_patch(FancyBboxPatch((cx - w / 2.0, cy - h / 2.0), w, h, boxstyle="round,pad=0,rounding_size=8", fc=fc, ec=ec,
                                lw=lw, zorder=3))
    if s != "":
        ax.text(cx, cy, s, ha="center", va="center", fontsize=size or LV.FONT, color=color, zorder=4,
                weight="bold" if bold else "normal")


def _lv_text(ax, x, y, s, color=INK, size=None, ha="center", va="center", bold=False):
    ax.text(x, y, s, ha=ha, va=va, fontsize=size or LV.FONT, color=color, zorder=5, weight="bold" if bold else "normal")


def _lv_arrow(ax, x0, y0, x1, y1, color=INK, lw=2.4):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=4,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=20, shrinkA=0, shrinkB=0))


# 9b 셋째 단계: 확률의 비. 파랑은 logit, 주황은 소프트맥스 확률

def _levels_9b3(level):
    if level == 7:
        rows = [([2, 1, 0], 1), ([4, 2, 0], 2), ([12, 11, 10], 1)]
        fig, ax = _lv_board()
        _lv_text(ax, 95, 252, "모델이 낸 수", color=MUTED)
        _lv_text(ax, 320, 252, "바뀐 수", color=MUTED)
        _lv_text(ax, 470, 252, "차이", color=MUTED)
        for k, (zs, gap) in enumerate(rows):
            y = 200 - 62 * k
            ps = softmax(zs)
            assert all(b - a == -gap for a, b in zip(zs, zs[1:]))
            for n, z in enumerate(zs):
                _lv_box(ax, 45 + 50 * n, y, 44, 44, str(z), ec=BLUE, fc=BLUE_L)
            _lv_arrow(ax, 176, y, 214, y)
            for n, v in enumerate(ps):
                _lv_box(ax, 255 + 66 * n, y, 60, 44, fx(v, 3), ec=ORANGE, fc=ORANGE_L)
            _lv_text(ax, 470, y, "%d씩" % gap, bold=gap == 1, color=INK if gap == 1 else MUTED)
        assert np.allclose(softmax([12, 11, 10]), P) and [fx(v, 3) for v in softmax([4, 2, 0])] == ["0.867", "0.117", "0.016"]
        return fig
    if level == 15:
        xs = list(np.linspace(0, 2.5, 101))
        ys = [math.exp(x) for x in xs]
        assert fx(math.e, 3) == "2.718" and fx(math.e ** 2, 3) == "7.389" and fx(ys[-1], 1) == "12.2"
        return LV.graph(xs, [(ys, "orange", "")], "두 logit의 차이", "두 확률의 비", top="두 확률의 비 = e^(두 logit의 차이)",
                        marks=[(1, math.e, "2.718", "orange"), (2, math.e ** 2, "7.389", "orange")], xlim=(0, 2.6), ylim=(0, 14))
    rows = []
    for zs in ([2.0, 1.0, 0.0], [12.0, 11.0, 10.0], [4.0, 2.0, 0.0]):
        ps = softmax(zs)
        rows.append([fx(zs[0] - zs[1], 0), fx(ps[0] / ps[1], 4), fx(ps[0] / ps[2], 4)])
    assert rows == [["1", "2.7183", "7.3891"], ["1", "2.7183", "7.3891"], ["2", "7.3891", "54.5982"]]
    return LV.grid(rows, col_names=["z[0]-z[1]", "p[0]/p[1]", "p[0]/p[2]"], row_names=["z", "z + 10", "z * 2"],
                   marks=[(r, c) for r in range(3) for c in (1, 2)], color="orange", top="p = torch.softmax(z, dim=0)",
                   code=True)


@figure("9b-31", *LV.SIZE)
def levels_9b3_7():
    return _levels_9b3(7)


@figure("9b-32", *LV.SIZE)
def levels_9b3_15():
    return _levels_9b3(15)


@figure("9b-33", *LV.SIZE)
def levels_9b3_20():
    return _levels_9b3(20)


# 9c 셋째 단계: NLLLoss. 초록 테두리는 정답 칸과 손실

ONE12 = np.arange(1.0, 13.0).reshape(4, 3)
LAB12 = np.array([0, 1, 2, 0])


def _levels_9c3(level):
    pick = ONE12[np.arange(4), LAB12]
    lp = log_softmax(ONE12)[np.arange(4), LAB12]
    assert pick.tolist() == [1, 5, 9, 10] and -pick.mean() == -6.25 and -pick.sum() == -25
    assert fx(-lp.mean(), 4) == "1.6576" and fx(-lp.sum(), 4) == "6.6304"
    if level == 7:
        fig, ax = _lv_board()
        ys = [212, 170, 128, 86]
        for r in range(4):
            for c in range(3):
                hit = c == LAB12[r]
                _lv_box(ax, 40 + 40 * c, ys[r], 36, 34, "%d" % ONE12[r, c], ec=GREEN if hit else FAINT,
                        lw=3.2 if hit else 1.6, bold=hit)
            _lv_box(ax, 222, ys[r], 46, 34, "%d" % pick[r], ec=GREEN, lw=2.4)
            _lv_box(ax, 318, ys[r], 60, 34, M + "%d" % pick[r])
        _lv_arrow(ax, 150, 149, 190, 149)
        _lv_arrow(ax, 252, 149, 282, 149)
        _lv_arrow(ax, 354, 149, 386, 149)
        _lv_box(ax, 448, 149, 104, 56, fx(-pick.mean(), 2), ec=GREEN, lw=3, size=LV.BIG, bold=True)
        _lv_text(ax, 80, 252, "넣은 수", color=MUTED)
        _lv_text(ax, 222, 252, "고른 수", color=MUTED)
        _lv_text(ax, 318, 252, "빼기표 바꿈", color=MUTED)
        _lv_text(ax, 448, 200, "평균", color=MUTED)
        return fig
    if level == 15:
        rows = [["%d" % LAB12[r], "%d" % pick[r], fx(lp[r], 4)] for r in range(4)]
        rows.append(["", fx(-pick.mean(), 2), fx(-lp.mean(), 4)])
        assert [r[2] for r in rows[:4]] == [M + "2.4076", M + "1.4076", M + "0.4076", M + "2.4076"]
        return LV.grid(rows, col_names=["정답 칸", "그대로", "로그 소프트맥스"],
                       row_names=["데이터 %d" % k for k in range(1, 5)] + ["NLLLoss"], marks=[(4, 1), (4, 2)], color="green",
                       top="NLLLoss = " + M + "(정답 칸 값의 합) ÷ 4")
    rows = [["-6.2500", "1.6576"], ["-25.", "6.6304"]]  # 코드 출력처럼 빼기표는 ASCII
    assert float(rows[0][0]) == -pick.mean() and float(rows[1][0]) == -pick.sum()
    return LV.grid(rows, col_names=["x 그대로", "F.log_softmax(x, dim=1)"], row_names=["'mean'", "'sum'"],
                   marks=[(0, 1), (1, 1)], color="green", top="nn.NLLLoss(reduction=r)(입력, y)", code=True)


@figure("9c-31", *LV.SIZE)
def levels_9c3_7():
    return _levels_9c3(7)


@figure("9c-32", *LV.SIZE)
def levels_9c3_15():
    return _levels_9c3(15)


@figure("9c-33", *LV.SIZE)
def levels_9c3_20():
    return _levels_9c3(20)


# 9e 둘째 단계: 예측 클래스. 파랑은 logit, 노랑은 가장 큰 칸

def _levels_9e2(level):
    if level == 7:
        row = OUT4[3]
        assert row.tolist() == [1.5, 1.8, 0.4] and row.argmax() == 1
        fig, ax = _lv_board()
        xs = [170, 280, 390]
        for n, v in enumerate(row):
            top = n == row.argmax()
            _lv_text(ax, xs[n], 238, "%d번 칸" % n, color=MUTED)
            _lv_box(ax, xs[n], 188, 90, 56, fx(v, 1), ec=BLUE, fc=YELLOW if top else BLUE_L, size=LV.BIG, bold=top)
        _lv_text(ax, 62, 188, "넷째 줄")
        _lv_arrow(ax, 280, 158, 280, 104)
        _lv_box(ax, 280, 72, 90, 56, "1", ec=INK, size=LV.BIG, bold=True)
        _lv_text(ax, 190, 72, "예측")
        return fig
    if level == 15:
        assert OUT4.argmax(1).tolist() == [0, 1, 2, 1] and OUT4.max(0).tolist() == [2.0, 2.5, 3.0]
        rows = [["4", "열 번호 0, 1, 2, 1"], ["3", "값 2.0, 2.5, 3.0"]]
        return LV.grid(rows, col_names=["나온 수", "나온 것"], row_names=["행마다", "열마다"], marks=[(0, 0), (0, 1)],
                       color="highlight", top="예측 클래스 = 행마다 logit이 가장 큰 열 번호")
    assert np.asarray(OUT4.max()).shape == () and OUT4.argmax(0).shape == (3,) and OUT4.argmax(1).shape == (4,)
    rows = [["[]", "전체에서 가장 큰 값"], ["[4]", "행마다 가장 큰 값"], ["[4]", "행마다 그 열 번호"], ["[3]", "열마다 그 행 번호"]]
    return LV.grid(rows, col_names=["모양", "돌려주는 것"],
                   row_names=["max(outputs)", "max(outputs, 1)[0]", "max(outputs, 1)[1]", "max(outputs, 0)[1]"],
                   marks=[(2, 0), (2, 1)], color="highlight", top="outputs 모양 [4, 3]")


@figure("9e-21", *LV.SIZE)
def levels_9e2_7():
    return _levels_9e2(7)


@figure("9e-22", *LV.SIZE)
def levels_9e2_15():
    return _levels_9e2(15)


@figure("9e-23", *LV.SIZE)
def levels_9e2_20():
    return _levels_9e2(20)


# 9f 셋째 단계: 클래스별 정밀도와 재현율. 초록은 맞힌 칸, 빨강은 틀린 칸

def _levels_9f3(level):
    tp = np.diag(CM)
    fp, fn = CM.sum(0) - tp, CM.sum(1) - tp
    tn = CM.sum() - tp - fp - fn
    assert tp.tolist() == [20, 16, 18] and fp.tolist() == [0, 2, 4] and fn.tolist() == [0, 4, 2] and tn[1] == 38
    if level == 7:
        from matplotlib.patches import Circle
        fig, ax = _lv_board()
        for left, total, wrong, title in ((30, CM[:, 1].sum(), fp[1], "고른 쪽 18송이"), (275, CM[1].sum(), fn[1], "실제 쪽 20송이")):
            assert total - wrong == 16
            _lv_box(ax, left + 107, 132, 214, 170, "", ec=MUTED, lw=2)
            _lv_text(ax, left + 107, 245, title, bold=True)
            for k in range(total):
                cx, cy = left + 35 + 36 * (k % 5), 192 - 38 * (k // 5)
                ax.add_patch(Circle((cx, cy), 12, fc=GREEN if k < 16 else RED, ec="white", lw=1.5, zorder=5))
        assert CM[:, 1].sum() == 18 and CM[1].sum() == 20
        return fig
    if level == 15:
        assert 60 - 16 - 4 - 2 == 38 and fx(16 / 18, 3) == "0.889"
        rows = [["TP 16", "FN 4"], ["FP 2", "TN 38"]]
        return LV.grid(rows, col_names=["예측 양성", "예측 음성"], row_names=["실제 양성", "실제 음성"], marks=[(0, 0)],
                       color="green", top="정밀도 = 16 ÷ (16 + 2) = 0.889")
    prec, rec = tp / (tp + fp), tp / (tp + fn)
    rows = [["%d" % v for v in tp], ["%d" % v for v in fp], ["%d" % v for v in fn], [num(v, 3) for v in prec],
            [num(v, 3) for v in rec]]
    assert rows[3] == ["1", "0.889", "0.818"] and rows[4] == ["1", "0.8", "0.9"]
    return LV.grid(rows, col_names=["클래스 0", "클래스 1", "클래스 2"], row_names=["TP", "FP", "FN", "정밀도", "재현율"],
                   marks=[(0, c) for c in range(3)], color="green", top="average=None은 클래스마다 값 하나")


@figure("9f-31", *LV.SIZE)
def levels_9f3_7():
    return _levels_9f3(7)


@figure("9f-32", *LV.SIZE)
def levels_9f3_15():
    return _levels_9f3(15)


@figure("9f-33", *LV.SIZE)
def levels_9f3_20():
    return _levels_9f3(20)
