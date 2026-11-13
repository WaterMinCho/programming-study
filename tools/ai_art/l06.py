#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6차시 학습 노트 l06 의 그림(6a MSE·MAE, 6b 이상치와 Huber, 6c BCE, 6d CE·라벨 스무딩, 6e 클래스 불균형,
6f 문제 유형별 손실·reduction·손실 곡면).

그림에 찍는 숫자는 모두 이 파일에서 numpy 로 다시 계산하고 assert 로 확인함(6차시 슬라이드 5·6·11·13·16·17쪽,
노트북 02 의 [2]~[7]·[10] 출력 10, 2.6667, 2.1667, 720.8, 12.8, 12.3, 26.85 와 맞춤).

  python -m tools.ai_art l06                 ai/learn/l06/assets/ 에 그림을 모두 쓰고 manifest 를 고침
  python -m tools.ai_art l06 6b-3            이름을 적은 그림만

numpy·matplotlib·Pillow 가 있는 출제자 파이썬에서만 돌림. matplotlib 는 Agg 로만 씀(창을 띄우지 않음).
파일은 1120×600 이하(화면 560×300), GIF 는 장 10개 이하·장마다 1600~2500ms·64색, 마지막 장은 정지 요약임.
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
SLATE, SLATE_D, SLATE_L = "#3d6187", "#253747", "#9fb2c4"
CODE = "D2Coding"
# 단원마다 한 색은 한 뜻이고, 뜻은 그 그림의 캡션에 적음. 그림 안 설명 글은 회색(NOTE) 바탕이고 뜻이 없음
# 6a: 검은 점은 정답, 파랑은 예측, 빨강은 오차 e, 주황은 제곱과 MSE, 초록은 절댓값과 MAE, 회색 점선은 평균
# 6b: 검은 점은 정답, 파랑은 예측, 빨강은 이상치가 된 넷째 예측, 주황은 MSE 와 0.5e², 초록은 MAE 와 |e|, 보라는 Huber,
#     옅은 보라 칸은 제곱 구간
# 6c: 파랑은 정답이 1 인 데이터와 −log p, 보라는 정답이 0 인 데이터와 −log(1 − p), 초록은 BCE 와 안정한 식,
#     빨강은 float32 로 식을 그대로 계산한 값, 주황은 시그모이드 뒤 MSE, 회색은 logit
# 6d: 파랑은 logit, 주황은 소프트맥스 확률, 보라는 log 값, 초록은 정답 클래스와 손실, 회색은 원-핫 목표,
#     슬레이트(SLATE)는 라벨 스무딩 목표
# 6e: 파랑은 정상(데이터가 많은 클래스), 빨강은 질병(데이터가 적은 클래스), 회색은 γ = 0(보통 CE), 슬레이트 세 단계는
#     γ = 1·2·5 의 Focal Loss, 주황은 학습 전에 데이터를 바꾸는 방법, 초록은 학습할 때 손실을 바꾸는 방법.
#     외울 것 그림의 가중 교차 엔트로피 상자는 검은 테두리(뜻 없음)
# 6f: 주황은 제곱 오차, 회색 점선은 평균, 파랑은 매끄러운 손실 곡선, 회색은 울퉁불퉁한 손실 곡선, 별은 손실이 가장 작은 곳
M = MINUS
SIZES = {"font.size": 20, "axes.titlesize": 20, "axes.labelsize": 19, "xtick.labelsize": 17, "ytick.labelsize": 17,
         "axes.linewidth": 1.2, "axes.edgecolor": "#9ca3af"}


def num(v, nd=4):
    """그림에 찍는 숫자. 빼기표는 U+2212, 끝의 0 은 지움."""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"
    return ("0" if s in ("-0", "0") else s).replace("-", M)


def fx(v, nd):
    """소수 nd 자리 고정(끝의 0 을 지우지 않음). 빼기표는 U+2212."""
    return f"{v:.{nd}f}".replace("-", M)


def lst(vals, nd=4):
    return "[" + ", ".join(num(v, nd) for v in vals) + "]"


def new(h=600):
    """(pyplot, Figure). 파일 폭 1120px, 높이 h px."""
    plt = setup()
    plt.rcParams.update(SIZES)
    return plt, plt.figure(figsize=(11.2, h / 100.0), dpi=100)


def image(fig, symbols=False):
    """Figure 를 RGB 그림으로 바꾸고 닫음."""
    from PIL import Image
    import matplotlib.pyplot as plt
    if symbols:
        from tools.ai_art import math_symbols
        math_symbols(fig)
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
    """좌표가 (0~11.2, 0~h/100) 인 빈 판. 글 상자 그림에 씀."""
    plt, fig = new(h)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, h / 100.0)
    ax.axis("off")
    return plt, fig, ax


def card(ax, x0, y0, w, h, title, lines, edge, ink=INK, fill="white", size=17, title_size=20, code_lines=()):
    """둥근 상자 하나. lines 는 위에서부터 한 줄씩. code_lines 에 든 번호의 줄은 D2Coding 으로 씀."""
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0.05", fc=fill, ec=edge, lw=2.2, zorder=2))
    ax.text(x0 + 0.18, y0 + h - 0.32, title, ha="left", va="center", fontsize=title_size, weight="bold", color=ink,
            zorder=3)
    yy = y0 + h - 0.85
    for k, text in enumerate(lines):
        kw = dict(ha="left", va="center", fontsize=size, color=INK, zorder=3)
        if k in code_lines:
            kw["family"] = CODE
        ax.text(x0 + 0.22, yy, text, **kw)
        yy -= 0.5


def memo(specs, foot, symbols=False):
    """외울 것 그림. specs 는 줄마다 [(x0, w, title, lines, edge, ink, code_lines)] 이고 위 줄부터 그림. 상자 높이는 줄 수로
    정하고 그림 높이도 그에 맞춤. foot 은 맨 아래 회색 바탕 한 줄."""
    heights = [0.75 + 0.5 * max(len(c[3]) for c in row) for row in specs]
    total = sum(heights) + 0.25 * (len(specs) - 1) + 1.15
    h = int(round(total * 100))
    plt, fig, ax = board(h)
    top = total - 0.15
    for row, rh in zip(specs, heights):
        for x0, w, title, lines, edge, ink, code in row:
            card(ax, x0, top - rh, w, rh, title, lines, edge, ink=ink, code_lines=code)
        top -= rh + 0.25
    ax.text(5.6, 0.45, foot, ha="center", va="center", fontsize=16, color=INK,
            bbox=dict(boxstyle="round,pad=0.3", fc=NOTE, ec="none"))
    return image(fig, symbols=symbols)


# 공용 계산

def huber(e, d):
    a = np.abs(np.asarray(e, float))
    return np.where(a <= d, 0.5 * a ** 2, d * (a - 0.5 * d))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.asarray(z, float)))


def logsumexp(z):
    z = np.asarray(z, float)
    m = z.max()
    return m + math.log(np.exp(z - m).sum())


# 6a·6b 회귀 예: 정답 [10, 20, 30], 예측 [12, 19, 35] (6차시 슬 p5, 노트북 02 [1])
YT = np.array([10.0, 20, 30])
YP = np.array([12.0, 19, 35])
E = YP - YT
assert np.allclose(E, [2, -1, 5]) and (E ** 2).mean() == 10 and abs(np.abs(E).mean() - 2.6667) < 1e-4
assert abs(huber(E, 1.0).mean() - 2.1667) < 1e-4
# 6b 이상치 예: 노트북 02 [7]
YT5 = np.array([10.0, 20, 30, 40, 50])
YP5 = np.array([11.0, 19, 31, 39, 51])


def reg5(p4):
    yp = YP5.copy()
    yp[3] = p4
    e = yp - YT5
    return yp, e, (e ** 2).mean(), np.abs(e).mean(), huber(e, 1.0).mean()


assert np.allclose(reg5(100)[2:], (720.8, 12.8, 12.3)) and np.allclose(reg5(39)[2:], (1.0, 1.0, 0.5))
# 6c 예: 정답 [1, 0, 1], logit [2, 0, −1]
Z3 = np.array([2.0, 0.0, -1.0])
Y3 = np.array([1.0, 0.0, 1.0])
P3 = sigmoid(Z3)
B3 = -(Y3 * np.log(P3) + (1 - Y3) * np.log(1 - P3))
assert np.allclose(P3, [0.8808, 0.5, 0.2689], atol=5e-5) and np.allclose(B3, [0.1269, 0.6931, 1.3133], atol=5e-5)
assert abs(B3.mean() - 0.7111) < 5e-5
# 6d 예: logit [2.0, 1.0, 0.1]
ZC = np.array([2.0, 1.0, 0.1])
SM = np.exp(ZC) / np.exp(ZC).sum()
LG = np.log(SM)
assert np.allclose(SM, [0.659, 0.2424, 0.0986], atol=5e-4) and np.allclose(LG, [-0.417, -1.417, -2.317], atol=5e-4)
# 6e 예: 정상 9,900, 질병 100
NC = np.array([9900.0, 100.0])
WC = NC.sum() / (2 * NC)
assert abs(WC[0] - 0.505) < 5e-4 and WC[1] == 50 and np.allclose(WC * NC, 5000)


# 6a 손실 함수, MSE, MAE

def reg_axes(fig, rect, ymax=40, title=None):
    ax = fig.add_axes(rect)
    tidy(ax)
    ax.set_xlim(0.4, 3.6)
    ax.set_ylim(0, ymax)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["데이터 1", "데이터 2", "데이터 3"], fontsize=17)
    ax.set_ylabel("값")
    if title:
        ax.set_title(title, loc="left", pad=10)
    return ax


@figure("6a-1", 560, 280)
def names_6a():
    """6a 의 이름표 그림. 세 데이터의 정답·예측·오차와 이 단원의 이름."""
    plt, fig = new(560)
    ax = reg_axes(fig, [0.08, 0.12, 0.42, 0.78])
    xs = np.array([1.0, 2, 3])
    ax.scatter(xs, YT, s=90, color=INK, zorder=5)
    ax.scatter(xs, YP, s=150, facecolor="white", edgecolor=BLUE, lw=2.6, zorder=6)
    for i in range(3):
        ax.plot([xs[i], xs[i]], [YT[i], YP[i]], color=RED, lw=3.5, zorder=4)
        ax.text(xs[i] + 0.12, (YT[i] + YP[i]) / 2, ("+" if E[i] > 0 else "") + num(E[i], 0), color=RED, fontsize=18,
                weight="bold", va="center")
    arrow = dict(arrowstyle="-", color=MUTED, lw=1.4)
    box = dict(boxstyle="round,pad=0.2", fc="white", ec="none")
    ax.annotate("정답", (xs[2], YT[2]), xytext=(1.6, 31), fontsize=18, color=INK, arrowprops=arrow, bbox=box, zorder=9,
                va="center")
    ax.annotate("예측", (xs[2], YP[2]), xytext=(2.0, 37), fontsize=18, color=BLUE, arrowprops=arrow, bbox=box, zorder=9,
                va="center")
    ax.annotate("오차 e", (xs[0] + 0.05, 11), xytext=(1.0, 21), fontsize=18, color=RED, weight="bold", arrowprops=arrow,
                bbox=box, zorder=9, va="center", ha="center")
    rows = [(RED, "오차", "e = 예측 " + M + " 정답 = [2, " + M + "1, 5]"),
            (INK, "손실 함수", "여러 오차를 숫자 하나로 바꾸는 함수"),
            (ORANGE, "MSE", "오차를 제곱해 평균 냄"),
            (GREEN, "MAE", "오차의 절댓값을 평균 냄")]
    fig.text(0.56, 0.86, "이 단원의 이름표", fontsize=21, color=INK, weight="bold", va="center")
    for k, (color, name, desc) in enumerate(rows):
        yy = 0.71 - k * 0.165
        fig.text(0.56, yy, name, fontsize=20, color=color, weight="bold", va="center")
        fig.text(0.56, yy - 0.065, desc, fontsize=17, color=INK, va="center")
    return image(fig)


@figure("6a-2", 560, 300)
def mse_steps():
    """오차 → 제곱 → 평균(MSE 10). 왼쪽은 정답과 예측, 오른쪽은 막대."""
    sq = E ** 2
    assert np.allclose(sq, [4, 1, 25]) and sq.sum() == 30 and sq.mean() == 10
    xs = np.array([1.0, 2, 3])

    def draw(stage):
        plt, fig = new(600)
        ax = reg_axes(fig, [0.075, 0.13, 0.40, 0.72], title="정답(검은 점)과 예측(빈 원)")
        ax.scatter(xs, YT, s=80, color=INK, zorder=5)
        ax.scatter(xs, YP, s=120, facecolor="white", edgecolor=BLUE, lw=2.4, zorder=6)
        if stage >= 2:
            for i in range(3):
                ax.plot([xs[i], xs[i]], [YT[i], YP[i]], color=RED, lw=3.2, zorder=4)
        bx = fig.add_axes([0.58, 0.13, 0.40, 0.72])
        tidy(bx)
        bx.set_xlim(0.4, 3.6)
        bx.set_xticks([1, 2, 3])
        bx.set_xticklabels(["데이터 1", "데이터 2", "데이터 3"], fontsize=17)
        if stage <= 2:
            bx.set_ylim(-3, 7)
            bx.axhline(0, color=INK, lw=1)
            bx.set_title("오차 e = 예측 " + M + " 정답", loc="left", pad=10)
            if stage == 2:
                bx.bar(xs, E, color=RED, width=0.5, zorder=3)
                for i, v in enumerate(E):
                    bx.text(xs[i], v + (0.2 if v > 0 else -0.2), ("+" if v > 0 else "") + num(v, 0), ha="center",
                            va="bottom" if v > 0 else "top", fontsize=18, weight="bold")
        else:
            bx.set_ylim(0, 30)
            bx.set_title("제곱 $e^2$", loc="left", pad=10)
            bx.bar(xs, sq, color=ORANGE, width=0.5, zorder=3)
            for i, v in enumerate(sq):
                bx.text(xs[i], v + 0.5, num(v, 0), ha="center", va="bottom", fontsize=18)
            if stage == 4:
                note(bx, 0.03, 0.96, "합 4 + 1 + 25 = 30", size=18, va="top", transform=bx.transAxes)
            if stage >= 5:
                bx.axhline(sq.mean(), color=MUTED, lw=2.5, ls="--", zorder=4)
                note(bx, 0.03, 0.96, "평균 30 ÷ 3 = 10", size=18, va="top", transform=bx.transAxes)
            if stage == 6:
                note(bx, 0.5, 0.55, "MSE = 10", color=ORANGE, size=20, ha="center", weight="bold", bg="white",
                     ec=ORANGE, transform=bx.transAxes)
        return image(fig)

    frames = [draw(k) for k in range(1, 7)]
    return frames, [1800, 2200, 2200, 1800, 2200, 2500]


@figure("6a-3", 560, 280)
def square_vs_abs():
    """오차를 제곱할 때와 절댓값을 낼 때. 오차 −1, 2, 5 에 점."""
    plt, fig = new(560)
    ax = fig.add_axes([0.08, 0.13, 0.50, 0.78])
    tidy(ax)
    e = np.linspace(-6, 6, 400)
    ax.plot(e, e ** 2, color=ORANGE, lw=3, label="제곱 $e^2$")
    ax.plot(e, np.abs(e), color=GREEN, lw=3, label="절댓값 |e|")
    ax.set_xlim(-6, 6)
    ax.set_ylim(0, 28)
    ax.set_xlabel("오차 e")
    ax.set_ylabel("손실에 보태는 값")
    for v in E:
        ax.scatter([v], [v * v], s=90, color=ORANGE, zorder=5)
        ax.scatter([v], [abs(v)], s=90, color=GREEN, zorder=5)
    ax.text(5 - 0.2, 25, "25", color=ORANGE, fontsize=18, ha="right", va="center", weight="bold")
    ax.text(5 + 0.15, 5 + 1.6, "5", color=GREEN, fontsize=18, ha="center", va="bottom", weight="bold")
    ax.text(2 - 0.2, 4 + 1.2, "4", color=ORANGE, fontsize=18, ha="right", va="bottom")
    ax.text(2 + 0.25, 2 - 0.4, "2", color=GREEN, fontsize=18, ha="left", va="top")
    ax.annotate("0 에서 꺾임", (0, 0.1), xytext=(-5.6, 7), fontsize=17, color=GREEN,
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.6),
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    ax.legend(loc="upper center", fontsize=17, frameon=False)
    assert E.tolist() == [2, -1, 5]
    mse, mae = (E ** 2).mean(), np.abs(E).mean()
    assert mse == 10 and abs(mae - 8 / 3) < 1e-12
    note(fig, 0.63, 0.80, "오차 [2, " + M + "1, 5]", size=19, bg=None, weight="bold", transform=fig.transFigure)
    note(fig, 0.63, 0.64, "제곱 [4, 1, 25]\nMSE = 30 ÷ 3 = 10", color=ORANGE, size=19, bg="white", ec=ORANGE,
         transform=fig.transFigure)
    note(fig, 0.63, 0.40, "절댓값 [2, 1, 5]\nMAE = 8 ÷ 3 = " + fx(mae, 4), color=GREEN, size=19, bg="white", ec=GREEN,
         transform=fig.transFigure)
    note(fig, 0.63, 0.17, "오차 5 는 제곱하면 25,\n절댓값은 5", size=17, transform=fig.transFigure)
    return image(fig)


@figure("6a-4", 560, 250)
def summary_6a():
    """외울 것 그림. 오차 → MSE·MAE 와 PyTorch 손실."""
    mse, mae = (E ** 2).mean(), np.abs(E).mean()
    assert mse == 10 and fx(mae, 4) == "2.6667"
    return memo([[(0.3, 3.3, "오차", ["정답 [10, 20, 30]", "예측 [12, 19, 35]", "e = [2, " + M + "1, 5]"], RED, RED, ()),
                  (3.85, 3.45, "MSE", ["(4 + 1 + 25) ÷ 3 = 10", "nn.MSELoss()", "제곱의 평균"], ORANGE, ORANGE, (1,)),
                  (7.55, 3.35, "MAE", ["(2 + 1 + 5) ÷ 3 = 2.6667", "nn.L1Loss()", "절댓값의 평균"], GREEN, GREEN, (1,))]],
                "손실 함수는 여러 오차를 숫자 하나로 바꿈. 작을수록 예측이 정답에 가까움")


# 6b 이상치와 Huber 손실

@figure("6b-1", 560, 300)
def outlier():
    """넷째 예측이 39 → 60 → 80 → 100 으로 갈 때 MSE·MAE."""
    steps = [39, 60, 80, 100]
    rows = [reg5(p) for p in steps]
    assert [round(r[2], 4) for r in rows] == [1.0, 80.8, 320.8, 720.8]
    assert [round(r[3], 4) for r in rows] == [1.0, 4.8, 8.8, 12.8]
    assert rows[-1][1].tolist() == [1, -1, 1, 60, 1]
    assert round(rows[-1][2] - rows[0][2], 1) == 719.8 and round(rows[-1][3] - rows[0][3], 1) == 11.8
    assert 60 ** 2 / 5 == 720
    xs = np.arange(1, 6)
    cols = [0.67, 0.775, 0.875, 0.965]

    def draw(stage):
        plt, fig = new(600)
        ax = fig.add_axes([0.09, 0.13, 0.41, 0.72])
        tidy(ax)
        ax.set_xlim(0.4, 5.6)
        ax.set_ylim(0, 110)
        ax.set_xticks(xs)
        ax.set_xticklabels(["1", "2", "3", "4", "5"])
        ax.set_xlabel("데이터 번호")
        ax.set_ylabel("값")
        k = min(stage, 4) - 1
        yp, e = rows[k][0], rows[k][1]
        for i in range(5):
            hot = i == 3 and k > 0
            ax.plot([xs[i], xs[i]], [YT5[i], yp[i]], color=(RED if hot else MUTED), lw=2.6, zorder=4)
            ax.scatter([xs[i]], [yp[i]], s=150, facecolor="white", edgecolor=(RED if hot else BLUE), lw=2.5, zorder=6)
        ax.scatter(xs, YT5, s=45, color=INK, zorder=7)
        ax.set_title("넷째 예측 " + num(yp[3], 0) + ", 오차 " + lst(e, 0), loc="left", pad=10, fontsize=18)
        fig.text(0.545, 0.80, "넷째 예측", fontsize=18, color=MUTED, va="center")
        for c, p in enumerate(steps):
            fig.text(cols[c], 0.80, str(p), fontsize=18, color=(RED if c else BLUE), ha="center", va="center",
                     weight="bold" if c == k else "normal")
        fig.lines.append(plt.Line2D([0.54, 0.995], [0.755, 0.755], transform=fig.transFigure, color=FAINT, lw=1.4))
        for r, (name, color, j) in enumerate([("MSE", ORANGE, 2), ("MAE", GREEN, 3)]):
            yy = 0.66 - r * 0.13
            fig.text(0.545, yy, name, fontsize=19, color=color, weight="bold", va="center")
            for c in range(4):
                if c <= k:
                    fig.text(cols[c], yy, num(rows[c][j], 1), fontsize=18, color=INK, ha="center", va="center")
        if stage == 5:
            fig.lines.append(plt.Line2D([0.54, 0.995], [0.45, 0.45], transform=fig.transFigure, color=FAINT, lw=1.4))
            note(fig, 0.545, 0.36, "늘어난 값  MSE +719.8,  MAE +11.8", size=17, transform=fig.transFigure)
            note(fig, 0.545, 0.22, "MSE 720.8 가운데 720 은\n넷째 하나가 보탠 60$^2$ ÷ 5", size=17, transform=fig.transFigure)
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2200, 2000, 2000, 2200, 2500]


def huber_axes(fig, rect, ymax=14):
    ax = fig.add_axes(rect)
    tidy(ax)
    ax.set_xlim(-6, 6)
    ax.set_ylim(0, ymax)
    ax.set_xlabel("오차 e")
    ax.set_ylabel("손실에 보태는 값")
    return ax


@figure("6b-2", 560, 300)
def huber_one():
    """δ = 1 인 Huber 곡선과 0.5e², |e|. 오차 [2, −1, 5] 의 값 1.5, 0.5, 4.5."""
    plt, fig = new(600)
    ax = huber_axes(fig, [0.08, 0.13, 0.52, 0.76], ymax=9)
    e = np.linspace(-6, 6, 600)
    ax.axvspan(-1, 1, color=PURPLE_L, zorder=0)
    ax.plot(e, 0.5 * e ** 2, color=ORANGE, lw=2.2, ls="--", label="0.5$e^2$")
    ax.plot(e, np.abs(e), color=GREEN, lw=2.2, ls="--", label="|e|")
    ax.plot(e, huber(e, 1.0), color=PURPLE, lw=3.4, label="Huber (δ = 1)")
    vals = huber(E, 1.0)
    assert np.allclose(vals, [1.5, 0.5, 4.5]) and abs(vals.mean() - 2.1667) < 1e-4
    for v, h in zip(E, vals):
        ax.scatter([v], [h], s=100, color=PURPLE, zorder=6)
        # 오차 −1 의 값은 점 오른쪽 위(제곱 구간 칸 안)에 둠. 점 아래에 두면 가로축 눈금 −2 옆에 붙어 눈금 숫자로 읽힘
        px, py, ha, va = (v + 0.25, h - 0.25, "left", "top") if v > 0 else (v + 0.12, h + 0.55, "left", "bottom")
        ax.text(px, py, num(h, 1), color=PURPLE, fontsize=18, ha=ha, va=va, zorder=8,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.text(0, 8.4, "제곱 구간\n|e| ≤ 1", color=PURPLE, linespacing=1.5, fontsize=16, ha="center", va="top")
    # 범례는 축 위 한 줄에 둠. 축 안 왼쪽 위에 두면 0.5e² 점선이 글자를 지나감
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=16, frameon=False, ncol=3)
    note(fig, 0.64, 0.83, "|e| ≤ δ  →  0.5$e^2$", color=PURPLE, size=19, bg="white", ec=PURPLE, transform=fig.transFigure)
    note(fig, 0.64, 0.68, "|e| > δ  →  δ(|e| " + M + " 0.5δ)", color=PURPLE, size=19, bg="white", ec=PURPLE,
         transform=fig.transFigure)
    note(fig, 0.64, 0.46, "오차 [2, " + M + "1, 5], δ = 1\n[1.5, 0.5, 4.5]\n평균 6.5 ÷ 3 = 2.1667", size=18,
         transform=fig.transFigure)
    note(fig, 0.64, 0.20, "오차 5: 1 × (5 " + M + " 0.5) = 4.5", size=17, transform=fig.transFigure)
    return image(fig)


@figure("6b-3", 560, 300)
def huber_delta():
    """δ = 0.5, 1, 2, 5 로 바꿀 때 제곱 구간과 오차 [2, −1, 5] 의 Huber 평균."""
    deltas = [0.5, 1.0, 2.0, 5.0]
    means = [huber(E, d).mean() for d in deltas]
    assert [round(m, 4) for m in means] == [1.2083, 2.1667, 3.5, 5.0]
    assert means[-1] == 0.5 * (E ** 2).mean()
    e = np.linspace(-6, 6, 600)

    def kinds(d):
        return ["제곱" if abs(v) <= d else "직선" for v in E]

    assert kinds(0.5) == ["직선"] * 3 and kinds(5.0) == ["제곱"] * 3 and kinds(1.0) == ["직선", "제곱", "직선"]

    def draw(stage):
        plt, fig = new(600)
        ax = huber_axes(fig, [0.08, 0.13, 0.50, 0.66], ymax=14)
        ax.plot(e, 0.5 * e ** 2, color=ORANGE, lw=2.0, ls="--", label="0.5$e^2$")
        ax.plot(e, np.abs(e), color=GREEN, lw=2.0, ls="--", label="|e|")
        if stage <= 4:
            d = deltas[stage - 1]
            ax.axvspan(-d, d, color=PURPLE_L, zorder=0)
            ax.plot(e, huber(e, d), color=PURPLE, lw=3.4, label="Huber")
            for v in E:
                ax.scatter([v], [huber(v, d)], s=90, color=PURPLE, zorder=6)
            head(fig, "δ = " + num(d, 1) + ": 옅은 보라 칸 |e| ≤ " + num(d, 1) + " 이 제곱 구간")
        else:
            for d in deltas:
                ax.plot(e, huber(e, d), color=PURPLE, lw=2.4, alpha=0.35 + 0.15 * deltas.index(d))
                xe = 5.9 if d < 5 else 4.6
                # δ=1 글자 위로 |e| 점선이 지나가서 그 글자만 흰 바탕을 깔아 가림
                ax.text(xe, float(huber(xe, d)) + 0.2, "δ=" + num(d, 1), color=PURPLE, fontsize=15, ha="right",
                        va="bottom", bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none") if d == 1 else None)
            head(fig, "δ 가 클수록 제곱 구간이 넓어짐")
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=16, frameon=False, ncol=3)
        # 오른쪽 표: 오차마다 어느 구간인지와 평균
        fig.text(0.62, 0.80, "δ", fontsize=19, color=PURPLE, weight="bold", ha="center", va="center")
        for c, v in enumerate(E):
            fig.text(0.71 + c * 0.075, 0.80, num(v, 0), fontsize=19, color=INK, ha="center", va="center", weight="bold")
        fig.text(0.94, 0.80, "평균", fontsize=18, color=INK, ha="center", va="center")
        fig.lines.append(plt.Line2D([0.60, 0.995], [0.755, 0.755], transform=fig.transFigure, color=FAINT, lw=1.4))
        shown = range(len(deltas)) if stage == 5 else range(stage)
        for r in shown:
            d = deltas[r]
            yy = 0.67 - r * 0.115
            hot = r == stage - 1
            if hot:
                fig.patches.append(plt.Rectangle((0.60, yy - 0.045), 0.395, 0.09, transform=fig.transFigure, fc=HL,
                                                 ec="none"))
            fig.text(0.62, yy, num(d, 1), fontsize=18, color=PURPLE, ha="center", va="center")
            for c, kind in enumerate(kinds(d)):
                fig.text(0.71 + c * 0.075, yy, kind, fontsize=17, color=(PURPLE if kind == "제곱" else INK),
                         ha="center", va="center")
            fig.text(0.94, yy, num(means[r], 4), fontsize=18, color=INK, ha="center", va="center")
        if stage == 4:
            note(fig, 0.61, 0.17, "세 오차가 모두 제곱 구간\n0.5 × MSE 10 = 5", size=17, transform=fig.transFigure)
        if stage == 5:
            note(fig, 0.61, 0.17, "δ 가 크면 제곱 쪽(MSE),\n작으면 직선 쪽(MAE)", size=17, transform=fig.transFigure)
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2200, 2200, 2200, 2400, 2500]


@figure("6b-4", 560, 250)
def summary_6b():
    """외울 것 그림. 이상치 하나에 세 손실이 늘어난 값과 Huber 식."""
    r0, r1 = reg5(39), reg5(100)
    assert (round(r1[2] - r0[2], 1), round(r1[3] - r0[3], 1), round(r1[4] - r0[4], 1)) == (719.8, 11.8, 11.8)
    assert (round(r1[2], 1), round(r1[3], 1), round(r1[4], 1)) == (720.8, 12.8, 12.3)
    return memo([[(0.3, 3.3, "MSE", ["1 → 720.8", "큰 오차가 손실을 끌어올림", r"RMSE = $\sqrt{\mathrm{MSE}}$"], ORANGE, ORANGE, ()),
                  (3.8, 3.15, "MAE", ["1 → 12.8", "늘어나는 폭이 작음", "nn.L1Loss()"], GREEN, GREEN, (2,)),
                  (7.15, 3.75, "Huber", ["0.5 → 12.3, delta 기본값 1.0", "|e| ≤ δ: 0.5$e^2$",
                                         "|e| > δ: δ(|e| " + M + " 0.5δ)"], PURPLE, PURPLE, ())]],
                "오차 [1, " + M + "1, 1, 60, 1]: 넷째 하나만 이상치. δ 가 클수록 제곱 구간이 넓어짐", symbols=True)


# 6c 이진 분류: BCE 와 BCEWithLogitsLoss

@figure("6c-1", 560, 300)
def bce_curves():
    """정답 1 의 −log p 와 정답 0 의 −log(1 − p). p = 0.1, 0.5, 0.9 에 점."""
    plt, fig = new(600)
    ax = fig.add_axes([0.08, 0.13, 0.55, 0.78])
    tidy(ax)
    p = np.linspace(0.005, 0.995, 500)
    ax.plot(p, -np.log(p), color=BLUE, lw=3.2, label="정답 1: " + M + "log p")
    ax.plot(p, -np.log(1 - p), color=PURPLE, lw=3.2, label="정답 0: " + M + "log(1 " + M + " p)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 4.6)
    ax.set_xlabel("예측 확률 p (정답이 1 일 확률)")
    ax.set_ylabel("BCE")
    vals = {0.9: -math.log(0.9), 0.5: -math.log(0.5), 0.1: -math.log(0.1)}
    assert (fx(vals[0.9], 3), fx(vals[0.5], 3), fx(vals[0.1], 3)) == ("0.105", "0.693", "2.303")
    for pp, v in vals.items():
        ax.scatter([pp], [v], s=90, color=BLUE, zorder=6)
        # p = 0.5 의 값은 두 곡선 사이 점 바로 위에 둠. 오른쪽 위에 두면 보라 곡선이 글자를 지나감
        if pp == 0.5:
            ax.text(pp, v + 0.3, fx(v, 3), color=BLUE, fontsize=18, ha="center", va="bottom")
        else:
            ax.text(pp + 0.02, v + 0.12, fx(v, 3), color=BLUE, fontsize=18, va="bottom")
    ax.legend(loc="upper center", fontsize=17, frameon=False)
    note(fig, 0.67, 0.80, "정답이 1 인 데이터", color=BLUE, size=19, bg=None, weight="bold", transform=fig.transFigure)
    note(fig, 0.67, 0.64, "p = 0.9 → 0.105\np = 0.5 → 0.693\np = 0.1 → 2.303", size=18, transform=fig.transFigure)
    note(fig, 0.67, 0.36, "확신하고 틀릴수록\n손실이 크게 늘어남", size=18, transform=fig.transFigure)
    note(fig, 0.67, 0.15, "log 는 자연로그", size=16, transform=fig.transFigure)
    return image(fig)


@figure("6c-2", 560, 300)
def logit_to_bce():
    """logit [2, 0, −1] → 시그모이드 → BCE → 평균 0.7111, BCEWithLogitsLoss 도 같은 값."""
    stable = np.maximum(Z3, 0) - Z3 * Y3 + np.log1p(np.exp(-np.abs(Z3)))
    assert np.allclose(stable, B3) and fx(B3.mean(), 4) == "0.7111"
    assert [fx(v, 4) for v in P3] == ["0.8808", "0.5000", "0.2689"]
    assert [fx(v, 4) for v in B3] == ["0.1269", "0.6931", "1.3133"]
    cols = [0.47, 0.555, 0.655, 0.775, 0.93]
    heads = ["데이터", "정답", "logit", "p", "BCE"]
    zz = np.linspace(-4, 4, 300)

    def draw(stage):
        plt, fig = new(600)
        titles = {1: "모델이 낸 logit", 2: "시그모이드로 확률 p 를 만듦", 3: "정답에 맞는 식으로 BCE",
                  4: "세 BCE 의 평균이 손실", 5: "BCEWithLogitsLoss 는 logit 에서 바로 같은 값"}
        head(fig, titles[stage])
        ax = fig.add_axes([0.07, 0.15, 0.31, 0.68])
        tidy(ax)
        ax.plot(zz, sigmoid(zz), color=MUTED, lw=2.4)
        ax.set_xlim(-4, 4)
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("logit z")
        ax.set_ylabel("p = σ(z)")
        for r in range(3):
            color = BLUE if Y3[r] == 1 else PURPLE
            ax.axvline(Z3[r], color=color, lw=1.2, ls=":", ymax=0.06)
            ax.text(Z3[r], 0.075, num(Z3[r], 0), color=color, fontsize=16, ha="center", va="bottom", weight="bold")
            if stage >= 2:
                ax.scatter([Z3[r]], [P3[r]], s=110, color=color, zorder=6)
        for c, h in enumerate(heads):
            fig.text(cols[c], 0.82, h, fontsize=18, color=(MUTED if c < 3 else INK), ha="center", va="center",
                     weight="bold")
        fig.lines.append(plt.Line2D([0.43, 0.99], [0.775, 0.775], transform=fig.transFigure, color=FAINT, lw=1.4))
        for r in range(3):
            yy = 0.69 - r * 0.12
            color = BLUE if Y3[r] == 1 else PURPLE
            fig.text(cols[0], yy, str(r + 1), fontsize=18, color=INK, ha="center", va="center")
            fig.text(cols[1], yy, num(Y3[r], 0), fontsize=18, color=color, ha="center", va="center", weight="bold")
            fig.text(cols[2], yy, num(Z3[r], 0), fontsize=18, color=MUTED, ha="center", va="center")
            if stage >= 2:
                fig.text(cols[3], yy, fx(P3[r], 4), fontsize=18, color=INK, ha="center", va="center")
            if stage >= 3:
                fig.text(cols[4], yy, fx(B3[r], 4), fontsize=18, color=GREEN, ha="center", va="center")
                form = (M + "log p" if Y3[r] == 1 else M + "log(1 " + M + " p)")
                fig.text(cols[4], yy - 0.05, form, fontsize=15, color=color, ha="center", va="center")
        if stage >= 4:
            fig.lines.append(plt.Line2D([0.43, 0.99], [0.36, 0.36], transform=fig.transFigure, color=FAINT, lw=1.4))
            fig.text(cols[3], 0.305, "평균", fontsize=18, color=INK, ha="center", va="center")
            fig.text(cols[4], 0.305, fx(B3.mean(), 4), fontsize=19, color=GREEN, ha="center", va="center")
        if stage == 5:
            note(fig, 0.44, 0.15, "nn.BCEWithLogitsLoss()(logit, 정답) = 0.7111\n시그모이드와 BCE 를 한 번에 계산", size=16,
                 transform=fig.transFigure, bg=GREEN_L)
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2000, 2200, 2400, 2000, 2500]


@figure("6c-3", 560, 300)
def stability():
    """정답 1 의 손실을 logit z 로: float32 로 σ 뒤 log 를 그대로 계산한 값과 안정한 식."""
    with np.errstate(over="ignore", divide="ignore"):
        z = np.linspace(-120, 10, 1301).astype(np.float32)
        s = np.float32(1) / (np.float32(1) + np.exp(-z))
        naive = -np.log(s)
        stable = np.maximum(-z, 0) + np.log1p(np.exp(-np.abs(z)))
    finite = np.isfinite(naive)
    assert finite[-1] and not finite[0] and np.allclose(naive[finite], stable[finite], atol=1e-3)
    assert abs(float(stable[0]) - 120) < 1e-3 and abs(float(stable[np.argmin(np.abs(z + 100))]) - 100) < 1e-3
    cut = float(z[finite][0])
    # 1 ÷ (1 + e^(−z)) 를 float32 로 차례대로 계산하면 e^(−z) 가 float32 가장 큰 수(약 3.4 × 10³⁸)를 넘는 z < 약 −88.7 에서 끊김
    assert -88.8 < cut < -88.6 and fx(cut, 1) == M + "88.7"
    plt, fig = new(600)
    ax = fig.add_axes([0.08, 0.13, 0.55, 0.78])
    tidy(ax)
    ax.set_xlim(-120, 10)
    ax.set_ylim(0, 140)
    ax.set_xlabel("logit z (정답은 1)")
    ax.set_ylabel("BCE")
    ax.plot(z, stable, color=GREEN, lw=5, label="안정한 식")
    ax.plot(z[finite], naive[finite], color=RED, lw=2.2, ls="--", label="식 그대로 float32")
    ax.annotate("", xy=(cut, 138), xytext=(cut, float(stable[finite][0])),
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=2.2, mutation_scale=20))
    ax.text(cut + 3, 128, "무한대(inf)", color=RED, fontsize=18, weight="bold", va="center")
    ax.legend(loc="upper right", fontsize=16, frameon=False)
    note(fig, 0.67, 0.79, "z 가 약 " + fx(cut, 1) + " 보다 작으면\ne^(" + M + "z) 가 무한대,\n시그모이드 값이 0 이 되어\n"
         + M + "log 0 = 무한대", color=RED, size=17, bg="white", ec=RED, transform=fig.transFigure)
    note(fig, 0.67, 0.47, "BCEWithLogitsLoss 는\n시그모이드와 log 를 한 식으로\n계산해 손실이 숫자로 나옴", color=GREEN,
         size=17, bg="white", ec=GREEN, transform=fig.transFigure)
    note(fig, 0.67, 0.17, "z = " + M + "100 이면 손실 100", size=17, transform=fig.transFigure)
    return image(fig)


@figure("6c-4", 560, 300)
def mse_vs_bce_grad():
    """정답 1 인 데이터에서 logit 에 대한 기울기 크기: 시그모이드 뒤 MSE 2(1−p)p(1−p) 와 BCE 1 − p."""
    p = np.linspace(0.005, 0.995, 400)
    g_mse = 2 * (1 - p) * p * (1 - p)
    g_bce = 1 - p
    assert abs(2 * 0.99 * 0.01 * 0.99 - 0.0196) < 1e-4 and abs(1 - 0.01 - 0.99) < 1e-12
    plt, fig = new(600)
    ax = fig.add_axes([0.08, 0.13, 0.55, 0.78])
    tidy(ax)
    ax.plot(p, g_bce, color=GREEN, lw=3.4, label="BCE")
    ax.plot(p, g_mse, color=ORANGE, lw=3.4, label="시그모이드 뒤 MSE")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("예측 확률 p (정답은 1)")
    ax.set_ylabel("logit 기울기의 크기")
    ax.scatter([0.01], [0.99], s=100, color=GREEN, zorder=6)
    ax.scatter([0.01], [0.0196], s=100, color=ORANGE, zorder=6)
    ax.legend(loc="upper right", fontsize=17, frameon=False)
    note(fig, 0.67, 0.78, "p = 0.01: 정답 1 인데\n0 에 가깝게 확신하고 틀림", size=18, transform=fig.transFigure)
    note(fig, 0.67, 0.50, "BCE 기울기 0.99", color=GREEN, size=19, bg="white", ec=GREEN, transform=fig.transFigure)
    note(fig, 0.67, 0.35, "MSE 기울기 0.0196", color=ORANGE, size=19, bg="white", ec=ORANGE, transform=fig.transFigure)
    note(fig, 0.67, 0.15, "p가 0에 가까우면\nMSE의 logit 기울기도\n작아집니다", size=17, transform=fig.transFigure)
    return image(fig)


@figure("6c-5", 560, 250)
def summary_6c():
    """외울 것 그림. BCE 식과 값, BCEWithLogitsLoss 짝."""
    assert fx(-math.log(0.9), 3) == "0.105" and fx(-math.log(0.1), 3) == "2.303"
    return memo([[(0.3, 4.2, "BCE", ["정답 1: " + M + "log p", "정답 0: " + M + "log(1 " + M + " p)",
                                     "정답 1, p 0.9 → 0.105", "정답 1, p 0.1 → 2.303"], GREEN, GREEN, ()),
                  (4.75, 6.15, "손실의 짝", ["끝에 시그모이드 없음 → nn.BCEWithLogitsLoss()",
                                            "확률을 넣음 → nn.BCELoss()", "BCEWithLogitsLoss 는 log 0 을",
                                            "만들지 않아 안정적"], GREEN, GREEN, ())]],
                "정답은 0. 과 1. 실수, 모양은 출력과 같은 [N, 1]. 모델 끝에 시그모이드를 두지 않음")


# 6d 다중 분류: CrossEntropyLoss 와 라벨 스무딩

@figure("6d-1", 560, 300)
def ce_flow():
    """logit [2.0, 1.0, 0.1] → 소프트맥스 → log → 정답 칸 → 부호 바꿈 = 0.417. 정답이 2 면 2.317."""
    assert [fx(v, 3) for v in SM] == ["0.659", "0.242", "0.099"]
    assert [fx(v, 3) for v in LG] == [M + "0.417", M + "1.417", M + "2.317"]
    assert abs(sum(SM) - 1) < 1e-12
    panels = [("logit", ZC, BLUE, (0, 2.6), 1), ("소프트맥스 확률", SM, ORANGE, (0, 1.0), 3),
              ("log 값", LG, PURPLE, (-2.9, 0.45), 3)]
    rects = [[0.06, 0.28, 0.24, 0.54], [0.38, 0.28, 0.24, 0.54], [0.70, 0.28, 0.24, 0.54]]

    def draw(stage):
        plt, fig = new(600)
        titles = {1: "모델이 낸 logit 세 개", 2: "소프트맥스: 합이 1 인 확률", 3: "각 확률에 log",
                  4: "정답 0 의 칸을 골라 부호를 바꿈: 손실 0.417", 5: "정답이 2 였다면 손실 2.317"}
        head(fig, titles[stage])
        target = 2 if stage == 5 else 0
        for k, (name, vals, color, lim, nd) in enumerate(panels):
            if stage < k + 1:
                continue
            ax = fig.add_axes(rects[k])
            tidy(ax, grid=False)
            ax.set_ylim(*lim)
            ax.set_xlim(-0.6, 2.6)
            ax.set_xticks([0, 1, 2])
            ax.set_xticklabels(["0", "1", "2"])
            ax.set_xlabel("클래스")
            ax.set_title(name, fontsize=18, color=color, pad=8)
            ax.axhline(0, color=INK, lw=1)
            ax.set_yticks([])
            ax.spines["left"].set_visible(False)
            bars = ax.bar([0, 1, 2], vals, color=color, width=0.6, zorder=3)
            for i, v in enumerate(vals):
                ax.text(i, v + (0.04 * (lim[1] - lim[0]) if v >= 0 else -0.04 * (lim[1] - lim[0])), fx(v, nd),
                        ha="center", va="bottom" if v >= 0 else "top", fontsize=17)
            if stage >= 4 and k == 2:
                for i in range(3):
                    if i != target:
                        bars[i].set_alpha(0.3)
                bars[target].set_edgecolor(GREEN)
                bars[target].set_linewidth(4)
            if k < 2 and stage >= k + 2:
                fig.text(rects[k][0] + rects[k][2] + 0.035, 0.49, "→", fontsize=30, color=MUTED, ha="center",
                         va="center")
        if stage >= 4:
            v = -LG[target]
            note(fig, 0.66, 0.07, "정답 " + str(target) + ": " + M + "(" + fx(LG[target], 3) + ") = " + fx(v, 3), color=GREEN,
                 size=19, bg="white", ec=GREEN, transform=fig.transFigure)
        return image(fig)

    assert fx(-LG[0], 3) == "0.417" and fx(-LG[2], 3) == "2.317"
    frames = [draw(k) for k in range(1, 6)]
    return frames, [2000, 2200, 2200, 2500, 2500]


@figure("6d-2", 560, 230)
def ce_shapes():
    """CrossEntropyLoss 에 넣는 꼴: logit [2, 3] 과 정답 번호 [2]. 손실은 두 데이터의 평균 0.3069."""
    from matplotlib.patches import Rectangle
    z = np.array([[2.0, 1.0, 0.1], [0.5, 2.5, 0.0]])
    t = [0, 1]
    losses = [logsumexp(z[i]) - z[i][t[i]] for i in range(2)]
    assert [fx(v, 4) for v in losses] == ["0.4170", "0.1967"] and fx(sum(losses) / 2, 4) == "0.3069"
    plt, fig, ax = board(460)
    ax.text(1.35, 4.25, "outputs  모양 [2, 3]", fontsize=19, family=CODE, color=BLUE, va="center")
    for r in range(2):
        for c in range(3):
            x0, y0 = 1.35 + c * 1.1, 2.55 - r * 0.9
            ax.add_patch(Rectangle((x0, y0), 1.0, 0.8, fc=BLUE_L, ec=BLUE, lw=1.8))
            ax.text(x0 + 0.5, y0 + 0.4, fx(z[r][c], 1), ha="center", va="center", fontsize=19, color=INK)
        ax.text(1.2, 2.55 - r * 0.9 + 0.4, "데이터 %d" % (r + 1), ha="right", va="center", fontsize=16, color=MUTED)
    for c in range(3):
        ax.text(1.35 + c * 1.1 + 0.5, 3.6, "클래스 %d" % c, ha="center", va="center", fontsize=15, color=MUTED)
    ax.text(5.05, 4.25, "labels  모양 [2]", fontsize=19, family=CODE, color=GREEN, va="center")
    for r in range(2):
        x0, y0 = 5.25, 2.55 - r * 0.9
        ax.add_patch(Rectangle((x0, y0), 0.9, 0.8, fc=GREEN_L, ec=GREEN, lw=1.8))
        ax.text(x0 + 0.45, y0 + 0.4, str(t[r]), ha="center", va="center", fontsize=20, color=INK, weight="bold")
    ax.text(6.35, 2.95, "클래스 번호\n정수(long)", ha="left", va="center", linespacing=1.5, fontsize=16, color=GREEN)
    note(ax, 7.75, 3.15, "nn.CrossEntropyLoss()", size=17, family=CODE, bg="white", ec=INK)
    note(ax, 7.75, 1.95, "데이터 1: 0.4170\n데이터 2: 0.1967\n평균 0.3069", color=GREEN, size=17, bg="white", ec=GREEN,
         va="center")
    note(ax, 0.3, 0.5, "이 예제는 클래스 번호를 정답으로 쓰고 logit을 그대로 넣습니다", size=17)
    return image(fig)


@figure("6d-3", 560, 280)
def smoothing():
    """원-핫 목표 [1, 0, 0] 과 라벨 스무딩 목표(K = 3, α = 0.1) [0.933, 0.033, 0.033]."""
    k, a = 3, 0.1
    q = np.full(k, a / k)
    q[0] += 1 - a
    assert [fx(v, 3) for v in q] == ["0.933", "0.033", "0.033"] and abs(q.sum() - 1) < 1e-12
    smooth_ce = float((q * (logsumexp(ZC) - ZC)).sum())
    assert fx(smooth_ce, 4) == "0.5137" and fx(-LG[0], 4) == "0.4170"
    plt, fig = new(560)
    ax = fig.add_axes([0.08, 0.14, 0.50, 0.74])
    tidy(ax)
    xs = np.arange(3)
    ax.bar(xs - 0.18, [1, 0, 0], width=0.34, color=GRAY, label="원-핫 벡터", zorder=3)
    ax.bar(xs + 0.18, q, width=0.34, color=SLATE, label="라벨 스무딩 목표", zorder=3)
    for i in range(3):
        ax.text(i - 0.18, [1, 0, 0][i] + 0.02, num([1, 0, 0][i], 0), ha="center", va="bottom", fontsize=17, color=INK)
        ax.text(i + 0.18, q[i] + 0.02, fx(q[i], 3), ha="center", va="bottom", fontsize=17, color=SLATE)
    ax.set_xticks(xs)
    ax.set_xticklabels(["클래스 0\n(정답)", "클래스 1", "클래스 2"], linespacing=1.4)
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("목표값")
    ax.legend(loc="upper right", fontsize=16, frameon=False)
    note(fig, 0.62, 0.82, "y × (1 " + M + " α) + α ÷ K", color=SLATE, size=19, bg="white", ec=SLATE,
         transform=fig.transFigure)
    note(fig, 0.62, 0.62, "정답: 1 × 0.9 + 0.1 ÷ 3 = 0.933\n나머지: 0 × 0.9 + 0.1 ÷ 3 = 0.033", size=17,
         transform=fig.transFigure)
    note(fig, 0.62, 0.38, "logit [2.0, 1.0, 0.1], 정답 0\n스무딩 없음: 0.4170\nα = 0.1: 0.5137", size=17,
         transform=fig.transFigure)
    note(fig, 0.62, 0.13, "K = 10 이면 0.91 과 0.01", size=17, transform=fig.transFigure)
    return image(fig)


@figure("6d-4", 560, 250)
def summary_6d():
    """외울 것 그림. CE 계산 순서, 입력 꼴, 라벨 스무딩."""
    assert fx(-LG[0], 3) == "0.417" and fx(-LG[2], 3) == "2.317"
    return memo([[(0.3, 10.6, "CrossEntropyLoss 클래스 번호 예제", ["logit [2.0, 1.0, 0.1] → 소프트맥스 → log → 정답 칸 고르기 → 부호 바꿈",
                                                   "정답 0: 0.417,  정답 2: 2.317"], GREEN, GREEN, ())],
                 [(0.3, 5.15, "이 예제의 입력", ["logit [N, 클래스 수]", "정답 [N], 클래스 번호"], BLUE, BLUE, ()),
                  (5.75, 5.15, "라벨 스무딩", ["label_smoothing=0.1", "K = 3: 0.933, 0.033, 0.033"], SLATE, SLATE, (0,))]],
                "모델은 logit을 냅니다. 이 예제의 정답은 클래스 번호입니다.")


# 6e 클래스 불균형

@figure("6e-1", 560, 280)
def imbalance():
    """정상 9,900, 질병 100 과 '모두 정상' 모델의 정확도 99%."""
    acc = NC[0] / NC.sum()
    assert acc == 0.99
    plt, fig = new(560)
    ax = fig.add_axes([0.13, 0.14, 0.38, 0.74])
    tidy(ax)
    ax.bar([0, 1], NC, color=[BLUE, RED], width=0.55, zorder=3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["정상", "질병"])
    ax.set_ylim(0, 11000)
    ax.set_yticks([0, 2500, 5000, 7500, 10000])
    ax.set_yticklabels(["0", "2,500", "5,000", "7,500", "10,000"])
    ax.set_ylabel("데이터 수")
    ax.text(0, NC[0] + 150, "9,900", ha="center", va="bottom", fontsize=19, color=BLUE, weight="bold")
    ax.text(1, NC[1] + 150, "100", ha="center", va="bottom", fontsize=19, color=RED, weight="bold")
    note(fig, 0.56, 0.84, "모델이 모두 \"정상\" 이라고 답함", size=19, bg=None, weight="bold", transform=fig.transFigure)
    note(fig, 0.56, 0.68, "정상 9,900 명: 모두 맞힘", color=BLUE, size=18, bg="white", ec=BLUE, transform=fig.transFigure)
    note(fig, 0.56, 0.54, "질병 100 명: 모두 틀림", color=RED, size=18, bg="white", ec=RED, transform=fig.transFigure)
    note(fig, 0.56, 0.36, "정확도 9,900 ÷ 10,000 = 99%", size=19, transform=fig.transFigure)
    note(fig, 0.56, 0.17, "찾아낸 질병은 0 명", color=RED, size=19, transform=fig.transFigure)
    return image(fig)


@figure("6e-2", 560, 280)
def class_weights():
    """가중치 w_c = N ÷ (K × n_c): 0.505, 50. 개수 × 가중치는 둘 다 5,000."""
    assert fx(WC[0], 3) == "0.505" and num(WC[1], 1) == "50"
    prod = WC * NC
    assert np.allclose(prod, [5000, 5000])
    panels = [("데이터 수 n_c", NC, (0, 11000), ["9,900", "100"]),
              ("가중치 w_c", WC, (0, 58), ["0.505", "50"]),
              ("n_c × w_c", prod, (0, 6000), ["5,000", "5,000"])]
    rects = [[0.07, 0.17, 0.24, 0.62], [0.40, 0.17, 0.24, 0.62], [0.73, 0.17, 0.24, 0.62]]

    def draw(stage):
        plt, fig = new(560)
        titles = {1: "정상 9,900, 질병 100 (전체 N = 10,000, 클래스 K = 2)",
                  2: "w_c = N ÷ (K × n_c): 10,000 ÷ (2 × 9,900) ≈ 0.505, 10,000 ÷ (2 × 100) = 50",
                  3: "데이터 수에 가중치를 곱하면 두 클래스 모두 5,000"}
        head(fig, titles[stage], size=18)
        for k, (name, vals, lim, labels) in enumerate(panels):
            if k >= stage:
                continue
            ax = fig.add_axes(rects[k])
            tidy(ax)
            ax.bar([0, 1], vals, color=[BLUE, RED], width=0.6, zorder=3)
            ax.set_ylim(*lim)
            ax.set_xticks([0, 1])
            ax.set_xticklabels(["정상", "질병"])
            ax.set_yticks([])
            ax.set_title(name, fontsize=18, pad=8)
            for i in range(2):
                ax.text(i, vals[i] + 0.02 * lim[1], labels[i], ha="center", va="bottom", fontsize=18,
                        color=[BLUE, RED][i])
            if k < 2 and stage >= k + 2:
                fig.text(rects[k][0] + rects[k][2] + 0.045, 0.48, "→", fontsize=30, color=MUTED, ha="center",
                         va="center")
        return image(fig)

    frames = [draw(k) for k in range(1, 4)]
    return frames, [2000, 2500, 2500]


@figure("6e-3", 560, 300)
def focal():
    """Focal Loss (α = 1) 곡선, γ = 0·1·2·5. p = 0.9 에서 CE 0.105 가 γ = 2 면 0.00105."""
    plt, fig = new(600)
    ax = fig.add_axes([0.08, 0.13, 0.55, 0.78])
    tidy(ax)
    p = np.linspace(0.01, 0.999, 500)
    styles = [(0, GRAY, "γ = 0 (교차 엔트로피)"), (1, SLATE_L, "γ = 1"), (2, SLATE, "γ = 2"), (5, SLATE_D, "γ = 5")]
    for g, color, label in styles:
        ax.plot(p, (1 - p) ** g * -np.log(p), color=color, lw=3.2 if g == 2 else 2.4, label=label)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 4.6)
    ax.set_xlabel("정답 클래스의 예측 확률 p")
    ax.set_ylabel("손실")
    ce9 = -math.log(0.9)
    f9 = (1 - 0.9) ** 2 * ce9
    assert fx(ce9, 3) == "0.105" and fx(f9, 5) == "0.00105" and abs((1 - 0.9) ** 2 - 0.01) < 1e-12
    assert abs((1 - 0.1) ** 2 - 0.81) < 1e-12
    ax.scatter([0.9], [ce9], s=90, color=GRAY, zorder=6)
    ax.scatter([0.9], [f9], s=90, color=SLATE, zorder=6)
    ax.annotate("p = 0.9: 0.105 → 0.00105", (0.9, 0.06), xytext=(0.45, 1.3), fontsize=17, color=SLATE,
                arrowprops=dict(arrowstyle="->", color=SLATE, lw=1.6),
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    ax.legend(loc="upper right", fontsize=16, frameon=False)
    note(fig, 0.67, 0.80, r"$-\alpha(1-p)^{\gamma}\log p$", color=SLATE, size=19, bg="white", ec=SLATE,
         transform=fig.transFigure)
    note(fig, 0.67, 0.60, "γ = 2 일 때 교차 엔트로피에\n곱하는 수\np = 0.9 → 0.01\np = 0.1 → 0.81", size=17,
         transform=fig.transFigure)
    note(fig, 0.67, 0.33, "쉬운 샘플(p 큼)의\n손실을 크게 줄임", size=17, transform=fig.transFigure)
    note(fig, 0.67, 0.13, "이 그림은 α = 1", size=16, transform=fig.transFigure)
    return image(fig, symbols=True)


@figure("6e-4", 560, 270)
def strategies():
    """불균형 대응 다섯 가지를 적용하는 때로 나눔."""
    plt, fig, ax = board(540)
    # 6e 에서 빨강·파랑은 질병·정상이라 여기서는 주황(데이터 쪽)과 초록(손실 쪽)을 씀
    card(ax, 0.3, 0.9, 5.15, 4.2, "학습 전에 데이터를 바꿈", ["오버샘플링: 질병 데이터를 늘림", "언더샘플링: 정상 데이터를 줄임",
                                                      "SMOTE: 질병 데이터를 바탕으로", "         새 데이터를 합성"], ORANGE,
         ink=ORANGE)
    card(ax, 5.75, 0.9, 5.15, 4.2, "학습할 때 손실을 바꿈", ["가중 교차 엔트로피:", "  적은 클래스에 큰 가중치",
                                                     "Focal Loss:", "  쉬운 샘플의 손실을 줄임"], GREEN, ink=GREEN)
    ax.text(5.6, 0.42, "강사 요약본 2주차 2쪽의 적용 단계 구분", ha="center", va="center", fontsize=16, color=MUTED)
    return image(fig)


@figure("6e-5", 560, 250)
def summary_6e():
    """외울 것 그림. 클래스 불균형, 가중치 식, Focal Loss."""
    assert NC[0] / NC.sum() == 0.99 and fx(WC[0], 3) == "0.505" and abs((1 - 0.9) ** 2 - 0.01) < 1e-12
    return memo([[(0.3, 3.2, "클래스 불균형", ["9,900 : 100", "모두 정상 → 99%", "질병은 0 명 찾음"], RED, RED, ()),
                  (3.75, 3.65, "가중 교차 엔트로피", ["전체 ÷ (클래스 수 × n_c)", "0.505 와 50", "weight=weights"], INK,
                   INK, (2,)),
                  (7.65, 3.25, "Focal Loss", [r"$-\alpha(1-p)^{\gamma}\log p$", "γ = 2, α = 0.25", "p 0.9 → × 0.01"],
                   SLATE, SLATE, ())]],
                "학습 전 데이터: 오버샘플링, 언더샘플링, SMOTE.  학습할 때 손실: 가중 교차 엔트로피, Focal Loss", symbols=True)


# 6f 문제 유형별 손실, reduction, 손실 곡면

@figure("6f-1", 560, 290)
def problem_types():
    """회귀·이진 분류·다중 분류의 마지막 출력, 손실 줄, 정답 꼴."""
    plt, fig, ax = board(580)
    heads = [(0.3, "문제"), (2.35, "마지막 출력"), (5.05, "손실 줄"), (8.55, "예제의 정답 꼴")]
    for x0, h in heads:
        ax.text(x0, 5.35, h, fontsize=19, color=MUTED, weight="bold", va="center")
    ax.plot([0.2, 11.0], [5.0, 5.0], color=FAINT, lw=1.6)
    rows = [("회귀", "숫자 1개", "nn.MSELoss()", "실수, [N, 1]", "집값처럼 연속된 숫자"),
            ("이진 분류", "logit 1개", "nn.BCEWithLogitsLoss()", "0. 과 1., [N, 1]", "시그모이드는 손실 안에"),
            ("다중 분류", "logit K개", "nn.CrossEntropyLoss()", "번호(long), [N]", "소프트맥스는 손실 안에")]
    for r, (name, out, loss, label, memo) in enumerate(rows):
        yy = 4.3 - r * 1.45
        ax.text(0.3, yy, name, fontsize=20, color=INK, weight="bold", va="center")
        ax.text(0.3, yy - 0.5, memo, fontsize=15, color=MUTED, va="center")
        ax.text(2.35, yy, out, fontsize=19, color=INK, va="center")
        ax.text(5.05, yy, loss, fontsize=18, color=INK, va="center", family=CODE)
        ax.text(8.55, yy, label, fontsize=18, color=INK, va="center")
        if r < 2:
            ax.plot([0.2, 11.0], [yy - 0.85, yy - 0.85], color=BAND, lw=1.2)
    return image(fig)


@figure("6f-2", 560, 280)
def reduction():
    """오차 [2, −1, 5] 의 제곱 [4, 1, 25] 와 reduction 셋: none, mean 10, sum 30."""
    sq = E ** 2
    assert sq.tolist() == [4, 1, 25] and sq.mean() == 10 and sq.sum() == 30
    plt, fig = new(560)
    ax = fig.add_axes([0.08, 0.14, 0.40, 0.72])
    tidy(ax)
    xs = np.array([1, 2, 3])
    ax.bar(xs, sq, color=ORANGE, width=0.5, zorder=3)
    for i, v in enumerate(sq):
        ax.text(xs[i], v + 0.5, num(v, 0), ha="center", va="bottom", fontsize=18)
    ax.axhline(sq.mean(), color=MUTED, lw=2.4, ls="--", zorder=4)
    ax.text(2.65, sq.mean() + 0.6, "평균 10", color=MUTED, fontsize=17, ha="right", va="bottom")
    ax.set_xlim(0.4, 3.6)
    ax.set_ylim(0, 30)
    ax.set_xticks(xs)
    ax.set_xticklabels(["데이터 1", "데이터 2", "데이터 3"], fontsize=17)
    ax.set_title("제곱 오차 [4, 1, 25]", loc="left", pad=10)
    rows = [("reduction='none'", "tensor([4., 1., 25.])", "데이터마다 하나씩"),
            ("reduction='mean'", "tensor(10.)", "기본값, 평균"),
            ("reduction='sum'", "tensor(30.)", "합")]
    for r, (arg, val, memo) in enumerate(rows):
        yy = 0.80 - r * 0.25
        fig.text(0.53, yy, arg, fontsize=17, family=CODE, color=INK, va="center")
        fig.text(0.53, yy - 0.085, val, fontsize=17, family=CODE, color=ORANGE, va="center", weight="bold")
        fig.text(0.97, yy - 0.04, memo, fontsize=16, color=MUTED, va="center", ha="right")
    return image(fig)


@figure("6f-3", 560, 300)
def loss_surface():
    """왼쪽: 4차시 직선 예의 손실 곡면 L(W, B). 오른쪽: 예로 그린 매끄러운 곡선과 울퉁불퉁한 곡선."""
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 - 3차원 축 등록
    X4 = np.array([-5.0, 5, 0, 2, -2])
    Y4 = np.array([-6.7, 10.3, -3.3, 5.0, -5.3])
    w = np.linspace(0, 3.6, 60)
    b = np.linspace(-3, 3, 60)
    W, B = np.meshgrid(w, b)
    L = (((W[..., None] * X4 + B[..., None]) - Y4) ** 2).mean(-1)
    wbest = float((X4 * Y4).sum() / (X4 ** 2).sum())
    lbest = float(((wbest * X4 - Y4) ** 2).mean())
    assert fx(wbest, 4) == "1.8207" and fx(lbest, 3) == "4.539"
    assert abs(float((((1.0 * X4 + 1.0) - Y4) ** 2).mean()) - 13.352) < 1e-9
    plt, fig = new(600)
    ax = fig.add_axes([0.0, 0.05, 0.50, 0.85], projection="3d", computed_zorder=False)
    ax.plot_surface(W, B, L, cmap="Blues_r", linewidth=0, antialiased=True, alpha=0.85, zorder=1)
    ax.scatter([wbest], [0], [lbest], s=420, color=INK, marker="*", depthshade=False, zorder=5)
    ax.scatter([1.0], [1.0], [13.352], s=110, color=INK, depthshade=False, zorder=5)
    ax.text(wbest + 0.25, 0, lbest + 2, "가장 작은 곳", fontsize=15, color=INK, zorder=6,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.text(1.0, 1.0, 13.352 + 5, "시작 (1, 1)", fontsize=15, color=INK, zorder=6,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.set_xlabel("W", labelpad=8)
    ax.set_ylabel("B", labelpad=8)
    ax.set_zlabel("손실", labelpad=13)
    ax.view_init(elev=28, azim=-60)
    ax.tick_params(labelsize=13)
    fig.text(0.02, 0.93, "4차시 직선 예: 파라미터 W, B 와 손실", fontsize=18, color=INK, weight="bold", va="center")
    bx = fig.add_axes([0.58, 0.16, 0.39, 0.64])
    tidy(bx)
    t = np.linspace(-3, 3, 600)
    smooth = 0.5 * t ** 2
    bumpy = 0.5 * t ** 2 + 0.9 * np.sin(4.2 * t) ** 2
    bx.plot(t, smooth + 4.5, color=BLUE, lw=3, label="매끄러운 곡선")
    bx.plot(t, bumpy, color=GRAY, lw=3, label="울퉁불퉁한 곡선")
    bx.set_xticks([])
    bx.set_yticks([])
    bx.set_xlabel("파라미터 하나")
    bx.set_ylabel("손실")
    bx.legend(loc="upper center", fontsize=15, frameon=False, ncol=1)
    bx.set_ylim(0, 11)
    fig.text(0.58, 0.88, "예로 그린 곡선", fontsize=17, color=MUTED, va="center")
    return image(fig)


@figure("6f-4", 560, 250)
def summary_6f():
    """외울 것 그림. 상황별 손실 줄, reduction, 손실 곡면."""
    assert (E ** 2).mean() == 10 and (E ** 2).sum() == 30
    return memo([[(0.3, 10.6, "상황별 손실 줄", ["회귀 nn.MSELoss()   이진 분류 nn.BCEWithLogitsLoss()",
                                                "다중 분류 nn.CrossEntropyLoss()"], INK, INK, (0, 1))],
                 [(0.3, 5.15, "reduction", ["mean(기본값) 10, sum 30", "none [4, 1, 25]"], ORANGE, ORANGE, ()),
                  (5.75, 5.15, "손실 곡면", ["파라미터를 바꿔 가며 잰", "손실의 모양"], BLUE, BLUE, ())]],
                "정답 꼴: 회귀와 이진 분류는 실수 [N, 1], 다중 분류는 클래스 번호 [N]")



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


# 6b 셋째 단계: Huber 손실. 보라는 Huber 손실, 옅은 보라는 제곱 구간

def _levels_6b(level):
    assert huber(E, 1.0).tolist() == [1.5, 0.5, 4.5] and f"{huber(E, 1.0).mean():.4f}" == "2.1667"
    if level == 7:
        fig, ax = _lv_board()
        for n, (d, rule) in enumerate(((1, "두 번 곱해 절반"), (2, "0.5 빼기"), (5, "0.5 빼기"))):
            y = 200 - 68 * n
            small = d <= 1
            _lv_box(ax, 80, y, 70, 50, str(d), ec=PURPLE if small else MUTED, fc=LV.PALE["purple"] if small else "white")
            _lv_arrow(ax, 122, y, 350, y)
            _lv_text(ax, 236, y + 18, rule, color=MUTED)
            _lv_box(ax, 405, y, 90, 50, num(float(huber(d, 1.0)), 1), ec=PURPLE, color=PURPLE, bold=True, lw=2.5)
        _lv_text(ax, 80, 255, "차이", color=MUTED)
        _lv_text(ax, 405, 255, "나오는 수", color=MUTED)
        return fig
    if level == 15:
        es = [1, 2, 3, 4, 5]
        sq, hub = [0.5 * e * e for e in es], [float(huber(e, 1.0)) for e in es]
        assert hub == [e - 0.5 for e in es] and sq == [0.5, 2, 4.5, 8, 12.5]
        rows = [[str(e) for e in es], [num(v, 1) for v in sq], [num(v, 1) for v in hub]]
        fig = LV.grid(rows, row_names=["|e|", "0.5 × e²", "Huber"], marks=[(2, c) for c in range(5)], color="purple",
                      top="|e| > 1 이면 Huber = |e| " + M + " 0.5")
        for t in fig.axes[0].texts:  # 나눔고딕의 ² 가 작아서 이 머리만 식 글꼴로 씀
            if t.get_text() == "0.5 × e²":
                t.set_fontfamily(LV.MATH_FONT)
        return fig
    pred, true = np.array([12, 19, 35.0]), np.array([10, 20, 30.0])
    diff = np.abs(pred - true)
    small = diff <= 1.0
    sq, lin = 0.5 * diff ** 2, 1.0 * (diff - 0.5)
    each = np.where(small, sq, lin)
    assert diff.tolist() == [2, 1, 5] and each.tolist() == [1.5, 0.5, 4.5] and sq.tolist() == [2, 0.5, 12.5]
    rows = [["%g" % v for v in diff], [str(bool(v)) for v in small], ["%g" % v for v in sq], ["%g" % v for v in lin],
            ["%g" % v for v in each]]
    return LV.grid(rows, col_names=["데이터 1", "데이터 2", "데이터 3"],
                   row_names=["diff", "small", "0.5 * diff**2", "diff - 0.5", "each"],
                   marks=[(2, 1), (3, 0), (3, 2)], color="purple", top="torch.where(small, a, b)", code=True)


@figure("6b-31", *LV.SIZE)
def levels_6b_7():
    return _levels_6b(7)


@figure("6b-32", *LV.SIZE)
def levels_6b_15():
    return _levels_6b(15)


@figure("6b-33", *LV.SIZE)
def levels_6b_20():
    return _levels_6b(20)


# 6c 둘째 단계: 이진 교차 엔트로피. 파랑은 정답이 1인 데이터, 보라는 정답이 0인 데이터

def _levels_6c(level):
    nl = lambda p: -math.log(p)  # noqa: E731
    assert [f"{nl(p):.3f}" for p in (0.9, 0.5, 0.1)] == ["0.105", "0.693", "2.303"]
    if level == 7:
        from matplotlib.patches import Rectangle
        fig, ax = _lv_board()
        base, top = 72, 150.0
        for x, p in ((70, 0.9), (150, 0.5), (230, 0.1)):
            h = top * nl(p) / nl(0.1)
            ax.add_patch(Rectangle((x - 24, base), 48, h, fc=LV.PALE["blue"], ec=BLUE, lw=2.5, zorder=3))
            _lv_text(ax, x, base + h + 16, f"{nl(p):.3f}", color=BLUE, bold=True)
            _lv_text(ax, x, base - 20, str(p))
        ax.plot([30, 270], [base, base], color=MUTED, lw=2)
        _lv_text(ax, 150, 22, "모델이 낸 수", color=MUTED)
        _lv_text(ax, 150, 262, "정답 1", color=BLUE)
        _lv_text(ax, 395, 262, "정답 0", color=PURPLE)
        _lv_box(ax, 370, 205, 84, 46, "0.9", ec=PURPLE)
        _lv_box(ax, 370, 128, 84, 46, "0.1", ec=PURPLE)
        _lv_box(ax, 370, 51, 100, 46, f"{nl(1 - 0.9):.3f}", ec=PURPLE, fc=LV.PALE["purple"], bold=True, color=PURPLE)
        _lv_arrow(ax, 370, 180, 370, 153)
        _lv_arrow(ax, 370, 103, 370, 76)
        _lv_text(ax, 420, 166, "1에서 빼기", color=MUTED, ha="left")
        return fig
    if level == 15:
        vals = [nl(p) for p in (1.0, 0.1, 0.01)]
        assert abs(vals[2] - 2 * vals[1]) < 1e-12 and f"{vals[2]:.4f}" == "4.6052" == f"{2 * 2.3026:.4f}"
        rows = [["1", "0", ""], ["0.1", f"{vals[1]:.4f}", f"{vals[1]:.4f}"], ["0.01", f"{vals[2]:.4f}", f"{vals[2] - vals[1]:.4f}"]]
        return LV.grid(rows, col_names=["p", "BCE", "늘어난 양"], marks=[(1, 2), (2, 2)], color="blue",
                       top="정답 1 이면 BCE = " + M + "log p")
    ps = np.array([0.9, 0.5, 0.1], dtype=np.float32)
    ln, l10 = np.log(ps), np.log10(ps)
    rows = [[f"{v:.4f}" for v in ln], [f"{-v:.4f}" for v in ln], [f"{v:.4f}".rstrip("0").rstrip(".") for v in l10]]
    assert rows[1] == ["0.1054", "0.6931", "2.3026"] and rows[2] == ["-0.0458", "-0.301", "-1"]
    return LV.grid(rows, col_names=["p = 0.9", "p = 0.5", "p = 0.1"], row_names=["torch.log", "BCE", "torch.log10"],
                   marks=[(1, 0), (1, 1), (1, 2)], color="blue", top="p = torch.tensor([0.9, 0.5, 0.1])", code=True)


@figure("6c-21", *LV.SIZE)
def levels_6c_7():
    return _levels_6c(7)


@figure("6c-22", *LV.SIZE)
def levels_6c_15():
    return _levels_6c(15)


@figure("6c-23", *LV.SIZE)
def levels_6c_20():
    return _levels_6c(20)


# 6d 둘째 단계: 소프트맥스와 교차 엔트로피. 파랑은 logit, 주황은 소프트맥스 확률, 초록은 정답 클래스와 손실

def _levels_6d(level):
    z = np.array([2.0, 1.0, 0.1])
    p = np.exp(z) / np.exp(z).sum()
    loss = -np.log(p)
    lse = math.log(np.exp(z).sum())
    assert [f"{v:.3f}" for v in p] == ["0.659", "0.242", "0.099"] and [f"{v:.3f}" for v in loss] == ["0.417", "1.417", "2.317"]
    assert np.allclose(lse - z, loss) and abs(p.sum() - 1) < 1e-12
    if level == 7:
        fig, ax = _lv_board()
        ys = [200, 135, 70]
        for k, y in enumerate(ys):
            _lv_box(ax, 80, y, 84, 48, f"{z[k]:.1f}", ec=BLUE, fc=LV.PALE["blue"])
            _lv_arrow(ax, 126, y, 202, y)
            right = k == 0
            _lv_box(ax, 255, y, 96, 48, f"{p[k]:.3f}", ec=GREEN if right else ORANGE, fc=LV.PALE["orange"], lw=3.5 if right else 2,
                    bold=right)
        _lv_arrow(ax, 307, ys[0], 383, ys[0], color=GREEN)
        _lv_box(ax, 435, ys[0], 96, 48, f"{loss[0]:.3f}", ec=GREEN, fc=LV.PALE["green"], bold=True)
        _lv_text(ax, 80, 255, "모델이 낸 수", color=MUTED)
        _lv_text(ax, 255, 255, "바꾼 수", color=MUTED)
        _lv_text(ax, 435, 255, "정답 칸", color=GREEN)
        _lv_text(ax, 255, 26, "모두 더하면 1", color=ORANGE)
        return fig
    if level == 15:
        rows = [[f"{z[k]:.1f}", f"{loss[k]:.3f}", num(loss[k] - loss[0], 1)] for k in range(3)]
        assert [r[2] for r in rows] == ["0", "1", "1.9"]
        rows[1][2] = "1.0"
        return LV.grid(rows, col_names=["logit", "손실", "정답 0과 차이"], row_names=["정답 0", "정답 1", "정답 2"],
                       marks=[(1, 2), (2, 2)], color="green", top="손실 차이 = logit 차이")
    dim0 = np.exp(z) / np.exp(z)
    rows = [[f"{v:.4f}" for v in p], ["%g" % v for v in dim0], [f"{v:.4f}" for v in lse - z]]
    assert rows[0] == ["0.6590", "0.2424", "0.0986"] and rows[1] == ["1", "1", "1"]
    return LV.grid(rows, col_names=["클래스 0", "클래스 1", "클래스 2"], row_names=["softmax dim=1", "softmax dim=0", "logsumexp " + M + " z"],
                   marks=[(2, 0), (2, 1), (2, 2)], color="green", top="z = torch.tensor([[2.0, 1.0, 0.1]])", code=True)


@figure("6d-21", *LV.SIZE)
def levels_6d_7():
    return _levels_6d(7)


@figure("6d-22", *LV.SIZE)
def levels_6d_15():
    return _levels_6d(15)


@figure("6d-23", *LV.SIZE)
def levels_6d_20():
    return _levels_6d(20)


# 6e 셋째 단계: 가중 교차 엔트로피. 파랑은 정상, 빨강은 질병, 노랑은 손실 객체가 내는 값

def _levels_6e(level):
    N, K = 10000, 2
    w = lambda n: N / (K * n)  # noqa: E731
    assert f"{w(9900):.3f}" == "0.505" and w(100) == 50 and abs(w(100) / w(9900) - 99) < 1e-9
    if level == 7:
        fig, ax = _lv_board()
        _lv_box(ax, 100, 185, 160, 54, "정상 9,900명", ec=BLUE, fc=LV.PALE["blue"], size=LV.FONT)
        _lv_box(ax, 100, 100, 160, 54, "질병 100명", ec=RED, fc=LV.PALE["red"], size=LV.FONT)
        _lv_arrow(ax, 192, 142, 330, 142, color=RED)
        _lv_text(ax, 261, 175, "한 명을", color=RED)
        _lv_text(ax, 261, 112, "99명처럼", color=RED)
        _lv_box(ax, 420, 185, 130, 54, "9,900", ec=BLUE, fc=LV.PALE["blue"], bold=True)
        _lv_box(ax, 420, 100, 130, 54, "9,900", ec=RED, fc=LV.PALE["red"], bold=True)
        _lv_text(ax, 100, 250, "한 명씩 세기", color=MUTED)
        _lv_text(ax, 420, 250, "다시 센 수", color=MUTED)
        _lv_text(ax, 260, 32, "다시 센 수가 같습니다")
        return fig
    if level == 15:
        xs = list(np.linspace(100, 9900, 300))
        ys = [5000.0 / x for x in xs]
        assert w(2000) == 2.5 and w(5000) == 1 and w(1000) == 5
        fig = LV.graph(xs, [(ys, "ink", "")], "클래스의 데이터 수 n", "가중치", top="가중치 = 10,000 ÷ (2 × n) = 5,000 ÷ n",
                       marks=[(100, 50, "", "red"), (1000, 5, "5", "ink"), (5000, 1, "1", "ink"), (9900, w(9900), "0.505", "blue")],
                       xlim=(0, 10400), ylim=(0, 60))
        fig.axes[0].text(500, 50, "50", ha="left", va="center", fontsize=LV.FONT, color=RED)  # 세로축 숫자와 겹치지 않게 오른쪽에 씀
        return fig
    zl = np.array([2.0, 0.0])
    pl = np.exp(zl) / np.exp(zl).sum()
    l0, l1 = -math.log(pl[0]), -math.log(pl[1])
    wt = (0.505, 50.0)
    top_sum = wt[0] * l0 + wt[1] * l1
    val = top_sum / (wt[0] + wt[1])
    assert f"{l0:.4f}" == "0.1269" and f"{l1:.4f}" == "2.1269" and f"{val:.4f}" == "2.1069"
    rows = [[f"{l0:.4f}", "0.505", f"{wt[0] * l0:.4f}"], [f"{l1:.4f}", "50", f"{wt[1] * l1:.2f}"],
            ["", "50.505", f"{top_sum:.2f}"], ["", "", f"{val:.4f}"]]
    return LV.grid(rows, col_names=[M + "log p", "가중치", "곱"], row_names=["정상", "질병", "합", "나눈 값"],
                   marks=[(3, 2)], color="highlight", top="criterion(z, torch.tensor([0, 1]))", code=True)


@figure("6e-31", *LV.SIZE)
def levels_6e_7():
    return _levels_6e(7)


@figure("6e-32", *LV.SIZE)
def levels_6e_15():
    return _levels_6e(15)


@figure("6e-33", *LV.SIZE)
def levels_6e_20():
    return _levels_6e(20)

if __name__ == "__main__":
    from tools.ai_art.__main__ import main as _main
    sys.exit(_main(["l06"] + sys.argv[1:]))
