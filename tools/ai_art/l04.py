#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4차시 학습 노트 l04 의 그림(4a 선형 모델과 손실, 4b 경사와 경사하강법, 4c 연쇄법칙·역전파·학습 코드).

다섯 사람의 신장·체중 예 하나를 세 단원 끝까지 씀. 그림에 찍는 숫자는 모두 이 파일에서 numpy 로 다시 계산하고 assert 로
확인함(노트북 4차시 01 의 출력 13.3520, -19.04, 2.0, W 1.820683, B 0.3675114 와 맞춤).

  python -m tools.ai_art l04                 ai/learn/l04/assets/ 에 그림을 모두 쓰고 manifest 를 고침
  python -m tools.ai_art l04 4a-2 4b-1       이름을 적은 그림만

numpy·matplotlib·Pillow 가 있는 출제자 파이썬에서만 돌림. matplotlib 는 Agg 로만 씀(창을 띄우지 않음).
파일은 1120×600 이하(화면 560×300), GIF 는 장 10개 이하·장마다 1600~2500ms·64색, 마지막 장은 정지 요약임.
글자 크기는 화면에서 13~14px 이 되게 pt 로 정함(파일은 화면의 2배라 20pt ≈ 화면 14px).
"""
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
SKY, PALE, CODEBG = "#93c5fd", "#bfdbfe", "#f8fafc"
CODE = "D2Coding"
M = MINUS
SIZES = {"font.size": 20, "axes.titlesize": 20, "axes.labelsize": 19, "xtick.labelsize": 17, "ytick.labelsize": 17,
         "axes.linewidth": 1.2, "axes.edgecolor": "#9ca3af"}

# 예: 다섯 사람의 신장(x)과 체중(y), 평균을 뺀 X, Y
x = np.array([166, 176, 171, 173, 169.0])
y = np.array([58.7, 75.7, 62.1, 70.4, 60.1])
X = x - x.mean()
Y = y - y.mean()
N = 5
assert x.mean() == 171 and abs(y.mean() - 65.4) < 1e-9
assert np.allclose(X, [-5, 5, 0, 2, -2]) and np.allclose(Y, [-6.7, 10.3, -3.3, 5.0, -5.3])


def L(W, B):
    """MSE 손실. W, B 는 숫자나 배열."""
    W = np.asarray(W, float)[..., None]
    B = np.asarray(B, float)[..., None]
    return (((W * X + B) - Y) ** 2).mean(-1)


def grads(W, B):
    """(W.grad, B.grad). 2/n·Σ(Yp−Y)·X, 2/n·Σ(Yp−Y) 로 셈(노트북 backward 출력과 같은 값)."""
    e = W * X + B - Y
    g = 2 * e / N
    return float((g * X).sum()), float(g.sum())


def LW(w):
    """B 를 1 로 둔 손실."""
    return float(L(w, 1.0))


def dLW(w):
    return grads(w, 1.0)[0]


# 경사하강 500번(float64). k 번째 기록은 k 번 고친 뒤(= k 번째 반복의 갱신 전) 값으로, 노트북 history 와 같음
_hist = []
_w, _b = 1.0, 1.0
for _ep in range(500):
    _gw, _gb = grads(_w, _b)
    _hist.append((_ep, _w, _b, float(L(_w, _b)), _gw, _gb))
    _w, _b = _w - 0.001 * _gw, _b - 0.001 * _gb
W_END, B_END = _w, _b
HIST = np.array(_hist)
assert abs(HIST[0, 3] - 13.352) < 1e-9 and f"{HIST[490, 3]:.4f}" == "4.6796"
assert f"{W_END:.6f}" == "1.820683" and abs(B_END - 0.3675114) < 1e-6
assert grads(1.0, 1.0) == (-19.04, 2.0) or np.allclose(grads(1.0, 1.0), (-19.04, 2.0))


def num(v, nd=4):
    """그림에 찍는 숫자. 빼기표는 U+2212, 끝의 0 은 지움."""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"
    return ("0" if s in ("-0", "0") else s).replace("-", M)


def sgn(v, nd=1):
    """부호를 붙인 숫자(+2.7, −4.3)."""
    return f"{v:+.{nd}f}".replace("-", M)


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
        ax.grid(True, color=GRID, lw=1.0, zorder=0)
        ax.set_axisbelow(True)


def note(target, px, py, text, color=INK, size=18, bg=HL, ha="left", va="center", weight="normal", family=None,
         transform=None, ec=None):
    """설명 글자. bg 가 있으면 둥근 바탕을 깔아 선 위에서도 읽히게 함."""
    kw = dict(color=color, fontsize=size, ha=ha, va=va, weight=weight, zorder=12, linespacing=1.35)
    if family:
        kw["family"] = family
    if bg:
        kw["bbox"] = dict(boxstyle="round,pad=0.3", fc=bg, ec=ec or bg, lw=1.2)
    if transform is not None:
        kw["transform"] = transform
    return target.text(px, py, text, **kw)


def head(fig, text, size=21):
    """그림 맨 위 왼쪽 제목 줄."""
    fig.text(0.015, 0.955, text, fontsize=size, color=INK, va="center", ha="left", weight="bold")


# 4a 선형 모델과 손실

@figure("4a-1", 560, 280)
def names_4a():
    """4a 첫 단계(먼저 풀어 보기)의 이름표 그림. 사람 2 의 정답·예측·오차와 직선에 이름을 붙임."""
    plt, fig = new(560)
    ax = fig.add_axes([0.075, 0.12, 0.50, 0.78])
    tidy(ax)
    ax.set_xlim(-7, 7)
    ax.set_ylim(-9, 13)
    ax.set_yticks([-5, 0, 5, 10])
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.axhline(0, color=FAINT, lw=1.2)
    ax.axvline(0, color=FAINT, lw=1.2)
    ax.plot([-7, 7], [-6, 8], color=BLUE, lw=3, zorder=3)
    ax.scatter(X, Y, s=80, color=INK, zorder=5)
    yp2 = 1 * X[1] + 1
    assert yp2 == 6 and abs(Y[1] - 10.3) < 1e-9
    ax.plot([X[1], X[1]], [Y[1], yp2], color=RED, lw=3.5, zorder=4)
    ax.scatter([X[1]], [yp2], s=150, facecolor="white", edgecolor=BLUE, lw=2.8, zorder=6)
    arrow = dict(arrowstyle="-", color=MUTED, lw=1.4)
    ax.annotate("정답 Y", (X[1], Y[1]), xytext=(0.6, 11.4), fontsize=18, color=INK, ha="left", va="center",
                arrowprops=arrow, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"), zorder=9)
    ax.annotate("예측 Yp", (X[1], yp2), xytext=(2.0, 1.2), fontsize=18, color=BLUE, ha="left", va="center",
                arrowprops=arrow, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"), zorder=9)
    ax.text(X[1] - 0.35, (Y[1] + yp2) / 2, "오차 e", fontsize=18, color=RED, ha="right", va="center", weight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"), zorder=9)
    ax.annotate("직선 Yp = W × X + B", (-3.5, -2.5), xytext=(-6.6, 6.0), fontsize=18, color=BLUE, ha="left",
                va="center", arrowprops=arrow, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"), zorder=9)
    ax.text(X[1] + 0.25, Y[1] + 0.35, "2", fontsize=16, color=MUTED, weight="bold", va="bottom")
    rows = [(BLUE, "선형 모델", "직선 Yp = W × X + B 로 예측하는 식"),
            (INK, "파라미터", "학습하며 고쳐 가는 W 와 B"),
            (RED, "오차", "예측 " + M + " 정답, e = Yp " + M + " Y"),
            (INK, "손실", "틀린 정도를 나타내는 숫자 하나")]
    fig.text(0.62, 0.86, "이 단원의 이름표", fontsize=21, color=INK, weight="bold", va="center")
    for k, (color, name, desc) in enumerate(rows):
        yy = 0.70 - k * 0.165
        fig.text(0.62, yy, name, fontsize=20, color=color, weight="bold", va="center")
        fig.text(0.62, yy - 0.065, desc, fontsize=17, color=INK, va="center")
    return image(fig)


@figure("4a-2", 560, 300)
def center():
    """평균 빼기. 왼쪽 산점도, 오른쪽 표가 장마다 채워짐."""
    xm, ym = x.mean(), y.mean()
    cols = [0.635, 0.705, 0.785, 0.875, 0.955]
    rows = [0.70, 0.605, 0.51, 0.415, 0.32]

    def draw(stage, title):
        plt, fig = new(600)
        head(fig, title)
        ax = fig.add_axes([0.075, 0.13, 0.50, 0.72])
        tidy(ax)
        shifted = stage >= 6
        if shifted:
            ax.set_xlim(163.5 - xm, 178.5 - xm)
            ax.set_ylim(55 - ym, 79 - ym)
            ax.set_xlabel("X = 신장 " + M + " 171")
            ax.set_ylabel("Y = 체중 " + M + " 65.4")
            ax.axhline(0, color=INK, lw=1.4)
            ax.axvline(0, color=INK, lw=1.4)
            px, py = X, Y
        else:
            ax.set_xlim(163.5, 178.5)
            ax.set_ylim(55, 79)
            ax.set_xlabel("신장 x (cm)")
            ax.set_ylabel("체중 y (kg)")
            px, py = x, y
        ax.scatter(px, py, s=90, color=INK, zorder=5)
        for i in range(5):
            ax.text(px[i] + 0.25, py[i] + 0.5, str(i + 1), fontsize=17, color=MUTED, weight="bold", va="bottom")
        if 2 <= stage <= 5:
            ax.axvline(xm, color=MUTED, lw=2, ls="--")
            ax.text(xm + 0.2, 78, "x 평균 171", color=MUTED, fontsize=17, va="top",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
        if 3 <= stage <= 5:
            ax.axhline(ym, color=MUTED, lw=2, ls="--")
            ax.scatter([xm], [ym], s=150, facecolor="white", edgecolor=INK, lw=2.5, zorder=6)
            ax.text(163.8, ym + 0.6, "y 평균 65.4", color=MUTED, fontsize=17, va="bottom",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
        if stage in (4, 5):
            i = stage - 4
            ax.annotate("", xy=(x[i], ym), xytext=(xm, ym), arrowprops=dict(arrowstyle="->", color=GREEN, lw=2.6))
            ax.annotate("", xy=(x[i], y[i]), xytext=(x[i], ym), arrowprops=dict(arrowstyle="->", color=GREEN, lw=2.6))
            ax.scatter([x[i]], [y[i]], s=170, color=GREEN, zorder=7)
        if shifted:
            ax.scatter([0], [0], s=150, facecolor="white", edgecolor=INK, lw=2.5, zorder=6)
        # 오른쪽 표
        heads = ["사람", "x", "y", "X", "Y"]
        for c, h in enumerate(heads):
            fig.text(cols[c], 0.80, h, fontsize=19, color=(MUTED if c < 3 else GREEN), ha="center", va="center",
                     weight="bold")
        fig.lines.append(plt.Line2D([0.605, 0.99], [0.755, 0.755], transform=fig.transFigure, color=FAINT, lw=1.4))
        filled = {4: [0], 5: [0, 1], 6: [0, 1, 2, 3, 4]}.get(stage, [])
        for r in range(5):
            hot = (stage == 4 and r == 0) or (stage == 5 and r == 1)
            if hot:
                fig.patches.append(plt.Rectangle((0.605, rows[r] - 0.04), 0.385, 0.08, transform=fig.transFigure,
                                                 fc=HL, ec="none"))
            cells = [str(r + 1), num(x[r], 0), num(y[r], 1),
                     num(X[r], 0) if r in filled else "", f"{Y[r]:.1f}".replace("-", M) if r in filled else ""]
            for c, cell in enumerate(cells):
                fig.text(cols[c], rows[r], cell, fontsize=19, color=INK, ha="center", va="center")
        fig.lines.append(plt.Line2D([0.605, 0.99], [0.27, 0.27], transform=fig.transFigure, color=FAINT, lw=1.4))
        mean_cells = ["평균", "171" if stage >= 2 else "", "65.4" if stage >= 3 else "", "0" if stage >= 6 else "",
                      "0" if stage >= 6 else ""]
        for c, cell in enumerate(mean_cells):
            fig.text(cols[c], 0.215, cell, fontsize=19, color=INK, ha="center", va="center", weight="bold")
        return image(fig)

    assert num(X[0], 0) == M + "5" and num(Y[0], 1) == M + "6.7" and num(X[1], 0) == "5" and num(Y[1], 1) == "10.3"
    assert abs(X.mean()) < 1e-12 and abs(Y.mean()) < 1e-9
    frames = [draw(1, "다섯 사람의 신장과 체중"), draw(2, "신장 평균 171"), draw(3, "체중 평균 65.4"),
              draw(4, "사람 1: 166 " + M + " 171 = " + M + "5,  58.7 " + M + " 65.4 = " + M + "6.7"),
              draw(5, "사람 2: 176 " + M + " 171 = 5,  75.7 " + M + " 65.4 = 10.3"),
              draw(6, "평균을 뺀 값 X, Y: 점의 자리 관계는 같고 숫자만 0 근처")]
    return frames, [2000, 1800, 1800, 2400, 2400, 2500]


@figure("4a-3", 560, 300)
def line():
    """선형 모델 Yp = 1 × X + 1 로 예측하기."""
    Yp = 1 * X + 1
    assert np.allclose(Yp, [-4, 6, 1, 3, -1])

    def draw(stage, idx=(), strong=()):
        plt, fig = new(600)
        ax = fig.add_axes([0.075, 0.13, 0.52, 0.80])
        tidy(ax)
        ax.set_xlim(-7, 7)
        ax.set_ylim(-9, 13)
        ax.set_yticks([-5, 0, 5, 10])
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.axhline(0, color=FAINT, lw=1.2)
        ax.axvline(0, color=FAINT, lw=1.2)
        ax.scatter(X, Y, s=90, color=INK, zorder=5)
        for i in range(5):
            ax.text(X[i] + 0.25, Y[i] + 0.25, str(i + 1), fontsize=17, color=MUTED, weight="bold", va="bottom")
        right = []
        if stage >= 2:
            ax.plot([-7, 7], [-6, 8], color=BLUE, lw=3, zorder=3)
            right.append(("Yp = W × X + B", BLUE, 22))
            right.append(("W = 1, B = 1", BLUE, 20))
        if stage == 3:
            ax.plot([3, 4, 4], [4, 4, 5], color=BLUE, lw=3.2, zorder=6)
            ax.text(3.5, 3.6, "1", color=BLUE, fontsize=18, ha="center", va="top", weight="bold")
            ax.text(4.2, 4.5, "W = 1", color=BLUE, fontsize=18, ha="left", va="center", weight="bold")
            ax.scatter([0], [1], s=160, facecolor="white", edgecolor=PURPLE, lw=2.6, zorder=7)
            ax.text(-0.3, 1.6, "B = 1", color=PURPLE, fontsize=18, ha="right", va="bottom", weight="bold")
            right.append(("X가 1 커지면 Yp는\nW만큼 커짐", BLUE, 19))
            right.append(("X = 0에서 높이는 B", PURPLE, 19))
        for i in idx:
            c = BLUE if i in strong else SKY
            ax.plot([X[i], X[i]], [-9, Yp[i]], color=c, lw=1.4, ls=":", zorder=2)
            ax.scatter([X[i]], [Yp[i]], s=140, facecolor="white", edgecolor=c, lw=2.6, zorder=6)
        if stage == 4:
            right.append(("사람 1\n1 × (" + M + "5) + 1 = " + M + "4", INK, 20))
        if stage == 5:
            right.append(("사람 2\n1 × 5 + 1 = 6", INK, 20))
        if stage == 6:
            right.append(("사람 3: 1, 사람 4: 3\n사람 5: " + M + "1", INK, 19))
            right.append(("Yp = [" + ", ".join(num(v, 0) for v in Yp) + "]", INK, 20))
        yy = 0.86
        for text, color, size in right:
            lines = text.count("\n") + 1
            note(fig, 0.64, yy, text, color=color, size=size, bg=(HL if color == INK else None), va="top")
            yy -= 0.085 * lines + 0.05
        return image(fig)

    assert "[" + ", ".join(num(v, 0) for v in Yp) + "]" == "[" + M + "4, 6, 1, 3, " + M + "1]"
    frames = [draw(1), draw(2), draw(3), draw(4, [0], [0]), draw(5, [0, 1], [1]), draw(6, range(5), [2, 3, 4])]
    return frames, [1600, 1800, 2400, 2200, 2200, 2500]


@figure("4a-4", 560, 300)
def loss():
    """오차 → 제곱 → 합 → 평균(MSE 13.352). 왼쪽은 예측과 정답, 오른쪽은 막대."""
    Yp = X + 1
    e = Yp - Y
    sq = e ** 2
    assert np.allclose(e, [2.7, -4.3, 4.3, -2.0, 4.3]) and abs(e.sum() - 5.0) < 1e-9
    assert np.allclose(sq, [7.29, 18.49, 18.49, 4.0, 18.49])
    assert abs(sq.sum() - 66.76) < 1e-9 and abs(sq.mean() - 13.352) < 1e-9

    def draw(stage):
        plt, fig = new(600)
        ax = fig.add_axes([0.07, 0.13, 0.40, 0.74])
        bx = fig.add_axes([0.57, 0.13, 0.41, 0.74])
        tidy(ax)
        tidy(bx)
        ax.set_xlim(-7, 7)
        ax.set_ylim(-9, 13)
        ax.set_yticks([-5, 0, 5, 10])
        ax.set_xticks([-6, -4, -2, 0, 2, 4, 6])
        ax.axhline(0, color=FAINT, lw=1.2)
        ax.axvline(0, color=FAINT, lw=1.2)
        ax.plot([-7, 7], [-6, 8], color=BLUE, lw=3, zorder=3)
        ax.scatter(X, Y, s=80, color=INK, zorder=5)
        ax.scatter(X, Yp, s=110, facecolor="white", edgecolor=BLUE, lw=2.3, zorder=6)
        for i in range(5):
            ax.text(X[i] + 0.3, Y[i] - 0.4, str(i + 1), fontsize=16, color=MUTED, weight="bold", va="top")
        ax.set_title("예측(빈 원)과 정답(검은 점)", loc="left", pad=10)
        if stage >= 2:
            for i in range(5):
                ax.plot([X[i], X[i]], [Y[i], Yp[i]], color=RED, lw=3, zorder=4)
        bx.set_xticks(range(5))
        bx.set_xticklabels(["사람 %d" % (i + 1) for i in range(5)], fontsize=16)
        bx.set_xlim(-0.5, 4.5)
        if stage <= 3:
            bx.set_ylim(-7, 12)
            bx.set_yticks([-6, -3, 0, 3, 6])
            bx.axhline(0, color=INK, lw=1)
            bx.set_title("오차 e = Yp " + M + " Y", loc="left", pad=10)
            if stage >= 2:
                hl = (1, 2) if stage == 3 else ()
                cols = [RED] * 5
                bars = bx.bar(range(5), e, color=cols, width=0.55, zorder=3)
                for i, v in enumerate(e):
                    bx.text(i, v + (0.35 if v > 0 else -0.35), sgn(v), ha="center", va="bottom" if v > 0 else "top",
                            fontsize=17, weight="bold" if i in hl else "normal")
                    if hl and i not in hl:
                        bars[i].set_alpha(0.3)
            if stage == 3:
                note(bx, 0.5, 0.97, "그냥 더하면 5.0\n" + M + "4.3 과 +4.3 이 지워짐", size=17, ha="center", va="top",
                     transform=bx.transAxes)
        else:
            bx.set_ylim(0, 27)
            bx.set_title("제곱 $e^2$", loc="left", pad=10)
            bx.bar(range(5), sq, color=RED, width=0.55, zorder=3)
            for i, v in enumerate(sq):
                bx.text(i, v + 0.4, f"{v:.2f}", ha="center", va="bottom", fontsize=17)
            if stage == 5:
                note(bx, 0.5, 0.97, "합 66.76", size=18, ha="center", va="top", transform=bx.transAxes)
            if stage == 6:
                bx.axhline(sq.mean(), color=INK, lw=2.5, ls="--", zorder=4)
                note(bx, 0.5, 0.97, "평균 66.76 ÷ 5 = 13.352", size=18, ha="center", va="top", transform=bx.transAxes)
        return image(fig)

    frames = [draw(k) for k in range(1, 7)]
    return frames, [1600, 2200, 2500, 2200, 1800, 2500]


@figure("4a-5", 560, 250)
def summary_4a():
    """외울 것 그림. 평균 빼기 → 선형 모델 → 손실."""
    from matplotlib.patches import FancyBboxPatch
    plt, fig = new(500)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 5.0)
    ax.axis("off")
    Yp = X + 1
    assert abs(((Yp - Y) ** 2).mean() - 13.352) < 1e-9
    boxes = [(1.85, "평균 빼기", "X = x - x.mean()", "X = [" + M + "5, 5, 0, 2, " + M + "2]"),
             (5.6, "선형 모델", "Yp = W * X + B", "Yp = [" + M + "4, 6, 1, 3, " + M + "1]"),
             (9.35, "손실(MSE)", "((Yp - Y)**2).mean()", "13.352")]
    for cx, title, code, value in boxes:
        ax.add_patch(FancyBboxPatch((cx - 1.7, 1.75), 3.4, 2.5, boxstyle="round,pad=0.06", fc="#eff6ff", ec=BLUE, lw=2))
        ax.text(cx, 3.75, title, ha="center", va="center", fontsize=21, weight="bold", color=BLUE)
        ax.text(cx, 2.95, code, ha="center", va="center", fontsize=17, family=CODE, color=INK)
        ax.text(cx, 2.25, value, ha="center", va="center", fontsize=18, color=INK)
    kw = dict(arrowstyle="-|>", color=MUTED, lw=2.4, mutation_scale=22)
    ax.annotate("", xy=(3.85, 3.0), xytext=(3.6, 3.0), arrowprops=kw)
    ax.annotate("", xy=(7.6, 3.0), xytext=(7.35, 3.0), arrowprops=kw)
    ax.text(5.6, 0.95, "오차 e = Yp " + M + " Y 를 제곱해 평균 냄. 제곱하면 양수 오차와 음수 오차가 지워지지 않음",
            ha="center", va="center", fontsize=17, color=INK,
            bbox=dict(boxstyle="round,pad=0.35", fc=HL, ec="none"))
    return image(fig)


# 4b 경사와 경사하강법

@figure("4b-1", 560, 300)
def slope():
    """직선의 기울기 W 와 손실 곡선의 기울기(경사). 왼쪽 직선, 오른쪽 손실 곡선과 접선."""
    assert abs((LW(1.2) - LW(0.8)) / 0.4 + 19.04) < 1e-9
    assert abs(LW(0.8) - 17.624) < 1e-9 and abs(LW(1.2) - 10.008) < 1e-9
    ws = np.linspace(0.4, 2.6, 200)
    ls = [LW(w) for w in ws]

    def base(wtop, title_left, title_right, ghosts=()):
        plt, fig = new(600)
        ax = fig.add_axes([0.065, 0.13, 0.36, 0.74])
        bx = fig.add_axes([0.565, 0.13, 0.415, 0.74])
        tidy(ax)
        tidy(bx)
        ax.set_xlim(-7, 7)
        ax.set_ylim(-9, 13)
        ax.set_yticks([-5, 0, 5, 10])
        ax.axhline(0, color=FAINT, lw=1.2)
        ax.axvline(0, color=FAINT, lw=1.2)
        ax.scatter(X, Y, s=70, color=INK, zorder=5)
        for g in ghosts:
            ax.plot([-7, 7], [g * -7 + 1, g * 7 + 1], color=SKY, lw=2, zorder=2)
        ax.plot([-7, 7], [wtop * -7 + 1, wtop * 7 + 1], color=BLUE, lw=3, zorder=3)
        ax.set_title(title_left, loc="left", pad=10)
        bx.plot(ws, ls, color=RED, lw=3, zorder=3)
        bx.set_xlim(0.4, 2.6)
        bx.set_ylim(0, 32)
        bx.set_xlabel("W (B = 1 로 고정)")
        bx.set_ylabel("손실")
        bx.yaxis.set_label_coords(-0.13, 0.5)
        bx.set_title(title_right, loc="left", pad=10)
        return fig, ax, bx

    def tangent(bx, w):
        s = dLW(w)
        xs = np.array([w - 0.38, w + 0.38])
        bx.plot(xs, LW(w) + s * (xs - w), color=ORANGE, lw=3.2, zorder=5)
        bx.scatter([w], [LW(w)], s=120, color=ORANGE, zorder=6)

    frames, dur = [], []
    fig, ax, bx = base(1.0, "직선의 기울기 W = 1", "손실 곡선: W = 1 일 때 13.352")
    bx.scatter([1.0], [LW(1.0)], s=120, color=INK, zorder=6)
    frames.append(image(fig))
    dur.append(1800)

    fig, ax, bx = base(1.0, "W 를 0.8, 1.2 로 바꿔 보기", "손실 17.624 → 10.008", ghosts=(0.8, 1.2))
    for w in (0.8, 1.2):
        bx.scatter([w], [LW(w)], s=110, color=INK, zorder=6)
        bx.text(w + 0.06, LW(w) + 0.4, num(LW(w), 3), ha="left", va="bottom", fontsize=17,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    bx.plot([0.8, 1.2], [LW(0.8), LW(1.2)], color=MUTED, lw=2, ls="--")
    ax.text(-6.8, -2.3, "W = 0.8", fontsize=16, color="#3b82f6", ha="left", va="bottom")
    ax.text(-5.9, -7.7, "W = 1.2", fontsize=16, color="#3b82f6", ha="left", va="top")
    note(bx, 0.98, 0.96, "(10.008 " + M + " 17.624) ÷ (1.2 " + M + " 0.8)\n= " + M + "7.616 ÷ 0.4 = " + M + "19.04",
         size=18, ha="right", va="top", transform=bx.transAxes)
    frames.append(image(fig))
    dur.append(2500)

    expect = {1.0: (13.352, -19.04), 0.6: (22.824, -28.32), 1.4: (7.592, -9.76), 1.8207: (5.539, 0.0),
              2.2: (7.208, 8.8)}
    for w in (1.0, 0.6, 1.4, 1.8207, 2.2):
        s = dLW(w)
        lo_want, s_want = expect[w]
        assert abs(LW(w) - lo_want) < 1e-3 and abs(s - s_want) < 1e-2, (w, LW(w), s)
        stxt = "0" if abs(s) < 1e-2 else (("+" if s > 0 else "") + num(s, 2))
        if w == 1.0:
            sub = "접선의 기울기 " + stxt + ": 이것이 W.grad"
        elif abs(s) < 1e-2:
            sub = "접선이 평평함: 경사 0, 손실이 가장 작음"
        elif s > 0:
            sub = "경사 " + stxt + ": W 를 줄여야 손실이 줄어듦"
        else:
            sub = "경사 " + stxt + ": W 를 키우면 손실이 줄어듦"
        fig, ax, bx = base(w, "직선의 기울기 W = " + num(w, 4), "W = " + num(w, 4) + ": 손실 " + num(LW(w), 3))
        tangent(bx, w)
        note(bx, 0.98, 0.96, sub, size=18, ha="right", va="top", transform=bx.transAxes)
        frames.append(image(fig))
        dur.append(2200)

    fig, ax, bx = base(1.0, "지금 W = 1", "경사 " + M + "19.04: 오른쪽이 내리막")
    tangent(bx, 1.0)
    bx.annotate("", xy=(1.55, LW(1.55) + 1.0), xytext=(1.05, LW(1.05) + 1.5),
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=3.2, connectionstyle="arc3,rad=0.25"))
    note(bx, 0.98, 0.96, "W 를 키우는 쪽으로", size=18, color=GREEN, ha="right", va="top", transform=bx.transAxes)
    frames.append(image(fig))
    dur.append(2500)
    return frames, dur


@figure("4b-2", 560, 300)
def descent():
    """손실 등고선 위의 경사하강법. 경사 화살표, 반대쪽 이동, 실제 한 걸음, 되풀이한 길."""
    from matplotlib.patches import Rectangle
    Wg = np.linspace(0.5, 2.4, 240)
    Bg = np.linspace(-0.45, 1.45, 240)
    WW, BB = np.meshgrid(Wg, Bg)
    ZZ = L(WW, BB)
    wstar = float((X * Y).sum() / (X ** 2).sum())
    assert f"{wstar:.2f}" == "1.82" and f"{float(L(wstar, 0.0)):.3f}" == "4.539"
    gw, gb = grads(1.0, 1.0)
    u = np.array([gw, gb]) / np.hypot(gw, gb)
    w1, b1 = 1 - 0.001 * gw, 1 - 0.001 * gb
    assert abs(w1 - 1.01904) < 1e-12 and abs(b1 - 0.998) < 1e-12

    def base(title, sub=None):
        plt, fig = new(600)
        head(fig, title)
        ax = fig.add_axes([0.07, 0.11, 0.46, 0.78])
        tidy(ax, grid=False)
        cs = ax.contour(WW, BB, ZZ, levels=[4.7, 5.2, 6, 7.5, 10, 13.352, 17, 22], colors="#9ca3af", linewidths=1.3)
        spots = [(0.5946, 0.15), (0.7993, 0.6), (0.9683, 0.62), (1.1402, 0.3), (1.3232, 0.3), (1.5047, 0.55),
                 (1.5936, 0.25), (1.7066, 0.1)]
        ax.clabel(cs, fmt=lambda v: f"{v:g}", fontsize=15, inline=True, manual=spots)
        ax.set_aspect("equal")
        ax.set_xlim(0.5, 2.4)
        ax.set_ylim(-0.45, 1.45)
        ax.set_xlabel("W")
        ax.set_ylabel("B")
        ax.scatter([wstar], [0], marker="*", s=360, color=INK, zorder=6)
        ax.scatter([1.0], [1.0], s=130, color=INK, zorder=7)
        fig.text(0.58, 0.80, "● 시작 (1, 1), 손실 13.352", fontsize=18, color=INK, va="center")
        fig.text(0.58, 0.72, "★ 가장 낮은 곳 (1.82, 0), 손실 4.539", fontsize=18, color=INK, va="center")
        if sub:
            note(fig, 0.58, 0.14, sub, size=18, va="bottom")
        return plt, fig, ax

    def arrow(ax, d, color, label, ly):
        ax.annotate("", xy=(1 + 0.42 * d[0], 1 + 0.42 * d[1]), xytext=(1, 1),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=3.6, mutation_scale=24), zorder=8)
        ax.text(1 + 0.24 * d[0], ly, label, color=color, fontsize=18, ha="center", va="center", weight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"), zorder=9)

    frames, dur = [], []
    plt, fig, ax = base("손실 등고선: 같은 선 위는 손실이 같음", "가로 W, 세로 B\n선 위의 숫자가 그 선의 손실")
    frames.append(image(fig))
    dur.append(1800)
    plt, fig, ax = base("경사 (" + M + "19.04, 2.0) 가 가리키는 쪽", "주황: 손실이 가장 빨리 커지는 쪽")
    arrow(ax, u, ORANGE, "경사", 1.12)
    frames.append(image(fig))
    dur.append(2200)
    plt, fig, ax = base("경사하강법은 반대쪽으로 감", "초록: 실제로 움직이는 쪽\n(화살표 길이는 늘려 그림)")
    arrow(ax, u, ORANGE, "경사", 1.12)
    arrow(ax, -u, GREEN, "이동", 0.89)
    frames.append(image(fig))
    dur.append(2400)
    plt, fig, ax = base("한 걸음: 학습률 0.001", "W: 1 " + M + " 0.001 × (" + M + "19.04) = 1.01904\nB: 1 " + M +
                        " 0.001 × 2.0 = 0.998")
    ax.add_patch(Rectangle((0.975, 0.975), 0.07, 0.05, fill=False, ec=GREEN, lw=2, zorder=9))
    ix = fig.add_axes([0.60, 0.33, 0.34, 0.30])
    ix.set_facecolor("white")
    for sp in ix.spines.values():
        sp.set_edgecolor(GREEN)
        sp.set_linewidth(2)
    ix.set_xlim(0.994, 1.028)
    ix.set_ylim(0.9945, 1.0035)
    ix.set_xticks([])
    ix.set_yticks([])
    ix.annotate("", xy=(w1, b1), xytext=(1.0, 1.0), arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=2.6,
                                                                    mutation_scale=20))
    ix.scatter([1.0], [1.0], s=70, color=INK, zorder=5)
    ix.scatter([w1], [b1], s=70, color=GREEN, zorder=5)
    ix.text(1.0005, 1.0012, "시작 (1, 1)", fontsize=15, va="bottom")
    ix.text(1.017, 0.9968, "(1.019, 0.998)", fontsize=15, va="top", ha="center", color=GREEN)
    ix.set_title("초록 상자 안을 크게 봄", fontsize=16, loc="left", pad=4)
    frames.append(image(fig))
    dur.append(2500)

    marks = [(10,), (50,), (100, 200), (490,)]
    for g, grp in enumerate(marks):
        k = grp[-1]
        if k == 490:
            sub = "500번 고친 뒤 W " + num(W_END, 4) + ", B " + num(B_END, 4) + "\nW 는 빨리, B 는 천천히 움직임"
        elif k == 200:
            sub = "W 는 " + f"{HIST[200, 1]:.2f}" + " 까지 왔고\nB 는 아직 " + f"{HIST[200, 2]:.2f}"
        else:
            sub = "%d번째 자리, 손실 %s" % (k, num(HIST[k, 3], 4))
        plt, fig, ax = base("되풀이: %d번째 반복까지의 자리" % k, sub)
        ax.plot(HIST[:k + 1, 1], HIST[:k + 1, 2], color=GREEN, lw=3, zorder=8)
        for kk in [m for gg in marks[:g + 1] for m in gg]:
            ax.scatter([HIST[kk, 1]], [HIST[kk, 2]], s=70, color=GREEN, zorder=9)
            if kk == 10:
                ax.text(HIST[kk, 1], HIST[kk, 2] - 0.05, str(kk), fontsize=16, color=GREEN, weight="bold", va="top")
            else:
                ax.text(HIST[kk, 1] + 0.02, HIST[kk, 2] + 0.05, str(kk), fontsize=16, color=GREEN, weight="bold")
        if k == 490:
            ax.scatter([W_END], [B_END], s=110, facecolor="white", edgecolor=GREEN, lw=2.6, zorder=10)
        frames.append(image(fig))
        dur.append(2200 if k != 490 else 2500)
    assert num(HIST[10, 3], 4) == "10.3855" and num(HIST[50, 3], 4) == "6.1047"
    assert f"{HIST[200, 1]:.2f}" == "1.81" and f"{HIST[200, 2]:.2f}" == "0.67"
    assert num(W_END, 4) == "1.8207" and num(B_END, 4) == "0.3675"
    return frames, dur


@figure("4b-3", 560, 300)
def fit():
    """500번 되풀이하며 직선 맞추기. 왼쪽 직선, 오른쪽 손실 기록."""
    eps = [0, 10, 30, 60, 100, 200, 300, 490]
    want = {0: "13.352", 10: "10.3855", 30: "7.3364", 60: "5.7927", 100: "5.2805", 200: "4.9887", 300: "4.8399",
            490: "4.6796"}
    frames, dur = [], []
    for j, k in enumerate(eps):
        w, b, lo = HIST[k, 1], HIST[k, 2], HIST[k, 3]
        assert num(lo, 4) == want[k], (k, lo)
        plt, fig = new(600)
        ax = fig.add_axes([0.065, 0.13, 0.40, 0.72])
        bx = fig.add_axes([0.56, 0.13, 0.42, 0.72])
        tidy(ax)
        tidy(bx)
        ax.set_xlim(-7, 7)
        ax.set_ylim(-9, 13)
        ax.set_yticks([-5, 0, 5, 10])
        ax.set_xticks([-6, -4, -2, 0, 2, 4, 6])
        ax.axhline(0, color=FAINT, lw=1.2)
        ax.axvline(0, color=FAINT, lw=1.2)
        ax.scatter(X, Y, s=70, color=INK, zorder=5)
        for kk in eps[:j]:
            ww, bb = HIST[kk, 1], HIST[kk, 2]
            ax.plot([-7, 7], [-7 * ww + bb, 7 * ww + bb], color=PALE, lw=1.8, zorder=2)
        ax.plot([-7, 7], [-7 * w + b, 7 * w + b], color=BLUE, lw=3, zorder=3)
        ax.set_title("W = %s, B = %s" % (num(w, 4), num(b, 4)), loc="left", pad=10)
        bx.plot(HIST[:k + 1, 0], HIST[:k + 1, 3], color=RED, lw=3)
        bx.scatter([k], [lo], s=90, color=RED, zorder=5)
        bx.set_xlim(0, 500)
        bx.set_ylim(4, 14)
        bx.set_xlabel("반복 횟수(epoch)")
        bx.set_ylabel("손실")
        bx.yaxis.set_label_coords(-0.13, 0.5)
        bx.set_title("%d번째 반복: 손실 %s" % (k, num(lo, 4)), loc="left", pad=10)
        if k == 490:
            note(bx, 0.98, 0.96, "500번 고친 뒤\nW = %s, B = %s" % (num(W_END, 4), num(B_END, 4)), size=18, ha="right",
                 va="top", transform=bx.transAxes)
        frames.append(image(fig))
        dur.append(1600 if j < len(eps) - 1 else 2500)
    assert num(HIST[100, 1], 2) == "1.74" and num(HIST[300, 2], 4) == "0.5485"
    assert num(HIST[490, 1], 4) == "1.8207" and num(HIST[490, 2], 4) == "0.3749"
    return frames, dur


@figure("4b-4", 560, 280)
def summary_4b():
    """외울 것 그림. 경사의 반대쪽으로 한 걸음, 되풀이."""
    plt, fig = new(560)
    bx = fig.add_axes([0.075, 0.15, 0.40, 0.72])
    tidy(bx)
    ws = np.linspace(0.4, 2.6, 200)
    bx.plot(ws, [LW(w) for w in ws], color=RED, lw=3)
    s = dLW(1.0)
    assert abs(s + 19.04) < 1e-9
    xs = np.array([0.62, 1.38])
    bx.plot(xs, LW(1.0) + s * (xs - 1.0), color=ORANGE, lw=3.2)
    bx.scatter([1.0], [LW(1.0)], s=120, color=ORANGE, zorder=6)
    bx.annotate("", xy=(1.55, LW(1.55) + 1.0), xytext=(1.05, LW(1.05) + 1.5),
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=3.2, connectionstyle="arc3,rad=0.25"))
    bx.set_xlim(0.4, 2.6)
    bx.set_ylim(0, 32)
    bx.set_xlabel("W (B = 1 로 고정)")
    bx.set_ylabel("손실")
    bx.yaxis.set_label_coords(-0.13, 0.5)
    bx.set_title("경사 " + M + "19.04: W 를 키우는 쪽이 내리막", loc="left", pad=10, fontsize=19)
    lines = [("경사는 손실이 가장 빨리 커지는 쪽", ORANGE, 19, False),
             ("경사하강법은 그 반대쪽으로 한 걸음", GREEN, 19, False),
             ("새 W = W " + M + " 학습률 × W.grad", INK, 19, True),
             ("1 " + M + " 0.001 × (" + M + "19.04) = 1.01904", INK, 18, False),
             ("예측 → 손실 → 경사 계산 → 수정", BLUE, 19, True),
             ("500번 되풀이: W 1.8207, B 0.3675", BLUE, 18, False)]
    assert num(W_END, 4) == "1.8207" and num(B_END, 4) == "0.3675"
    yy = 0.86
    for text, color, size, gap in lines:
        if gap:
            yy -= 0.04
        fig.text(0.53, yy, text, fontsize=size, color=color, va="center",
                 weight="bold" if color != INK else "normal")
        yy -= 0.115
    return image(fig)


# 4c 연쇄법칙, 역전파, 학습 코드

@figure("4c-1", 560, 260)
def chain():
    """사람 2 의 연쇄법칙. 순전파로 값을 채우고 역전파로 미분을 곱해 감."""
    from matplotlib.patches import FancyBboxPatch
    i = 1
    yp = 1 * X[i] + 1
    e = yp - Y[i]
    s = e ** 2
    assert yp == 6 and abs(e + 4.3) < 1e-9 and abs(s - 18.49) < 1e-9 and abs(s / 5 - 3.698) < 1e-9
    assert abs(0.2 * 2 * e * 1 * X[i] + 8.6) < 1e-9 and abs(0.2 * 2 * e + 1.72) < 1e-9
    names = ["W", "Yp", "e", "s", "L"]
    vals = ["1", "6", M + "4.3", "18.49", "+3.698"]
    xs = [0.95, 3.25, 5.55, 7.85, 10.15]
    ops = ["× 5 + 1", M + " 10.3", "제곱", "÷ 5"]
    locd = ["미분 5", "미분 1", "미분 2e\n= " + M + "8.6", "미분 1/5\n= 0.2"]
    back = ["1 × 0.2\n= 0.2", "0.2 × (" + M + "8.6)\n= " + M + "1.72", M + "1.72 × 1\n= " + M + "1.72",
            M + "1.72 × 5\n= " + M + "8.6"]
    back_at = [3, 2, 1, 0]

    def draw(nvals, show_loc, nback, title, tags=False):
        plt, fig = new(520)
        head(fig, title, size=20)
        ax = fig.add_axes([0.0, 0.0, 1.0, 0.90])
        ax.set_xlim(0, 11.2)
        ax.set_ylim(0, 5.2)
        ax.axis("off")
        for k in range(5):
            fc = "#eff6ff" if k < nvals else "white"
            ax.add_patch(FancyBboxPatch((xs[k] - 0.72, 3.0), 1.44, 0.85, boxstyle="round,pad=0.05", fc=fc, ec=BLUE,
                                        lw=2))
            ax.text(xs[k], 4.08, names[k], ha="center", va="bottom", fontsize=21, weight="bold", color=BLUE)
            if k < nvals:
                ax.text(xs[k], 3.42, vals[k], ha="center", va="center", fontsize=19 if k < 4 else 17)
        for k in range(4):
            ax.annotate("", xy=(xs[k + 1] - 0.78, 3.42), xytext=(xs[k] + 0.78, 3.42),
                        arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2, mutation_scale=18))
            ax.text((xs[k] + xs[k + 1]) / 2, 4.62, ops[k], ha="center", va="center", fontsize=17, color=BLUE)
            if show_loc:
                ax.text((xs[k] + xs[k + 1]) / 2, 2.45, locd[k], ha="center", va="center", fontsize=16, color=MUTED,
                        linespacing=1.15)
        if tags:
            ax.text(5.6, 2.45, "순전파: 왼쪽에서 오른쪽으로 값 계산 →", ha="center", va="center", fontsize=18, color=BLUE)
            ax.text(5.6, 0.75, "← 역전파: 오른쪽에서 왼쪽으로 미분을 곱해 감", ha="center", va="center", fontsize=18,
                    color=ORANGE)
        if nback:
            ax.text(xs[4], 1.35, "1", ha="center", va="center", fontsize=19, color=ORANGE, weight="bold")
            ax.annotate("", xy=(0.25, 0.32), xytext=(10.95, 0.32),
                        arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=2, mutation_scale=18))
            ax.text(5.6, 0.55, "거꾸로 곱해 감", ha="center", va="bottom", fontsize=16, color=ORANGE)
        for j in range(max(0, nback - 1)):
            k = back_at[j]
            big = (j == 3)
            ax.text(xs[k], 1.35, back[j], ha="center", va="center", fontsize=18 if big else 16, color=ORANGE,
                    weight="bold" if big else "normal", linespacing=1.15,
                    bbox=dict(boxstyle="round,pad=0.25", fc=HL, ec="none") if big else None)
        return image(fig)

    frames = [draw(0, False, 0, "사람 2 (X = 5, Y = 10.3) 의 계산 단계", tags=True),
              draw(2, False, 0, "순전파: W = 1 에서 Yp = 1 × 5 + 1 = 6"),
              draw(5, False, 0, "순전파: 왼쪽에서 오른쪽으로 값 계산"),
              draw(5, True, 0, "단계마다 미분: 앞 칸을 조금 바꿀 때 뒤 칸이 바뀌는 배수"),
              draw(5, True, 1, "역전파: L 에서 1 로 시작"),
              draw(5, True, 2, "s 까지: 1 × 0.2"),
              draw(5, True, 3, "e 까지: 0.2 × (" + M + "8.6)"),
              draw(5, True, 4, "Yp 까지: " + M + "1.72 × 1"),
              draw(5, True, 5, "W 까지: 사람 2 가 W.grad 에 보태는 값 " + M + "8.6")]
    return frames, [2000, 1800, 2000, 2500, 1800, 1800, 1800, 1800, 2500]


@figure("4c-2", 560, 300)
def backprop():
    """다섯 사람의 역전파. 손실에서 Yp 까지 곱한 값 2e ÷ 5 를 W 쪽과 B 쪽이 나눠 씀."""
    from matplotlib.patches import FancyBboxPatch
    e = X + 1 - Y
    g = 2 * e / N
    wpart = g * X
    assert np.allclose(g, [1.08, -1.72, 1.72, -0.8, 1.72]) and np.allclose(wpart, [-5.4, -8.6, 0, -1.6, -3.44])
    assert abs(wpart.sum() + 19.04) < 1e-9 and abs(g.sum() - 2.0) < 1e-9
    cols = [0.75, 1.95, 3.35, 5.45, 7.75, 9.95]
    heads = ["사람", "X", "오차 e", "Yp 까지 곱한 값\n2e ÷ 5", "W 쪽 값\n× X", "B 쪽 값\n× 1"]
    rows = [4.65, 4.05, 3.45, 2.85, 2.25]

    def draw(stage, title):
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = fig.add_axes([0.0, 0.0, 1.0, 0.91])
        ax.set_xlim(0, 11.2)
        ax.set_ylim(0, 6.0)
        ax.axis("off")
        show = [True, True, True, stage >= 2, stage >= 3, stage >= 5]
        for c in range(6):
            if show[c]:
                col = INK if c < 3 else (ORANGE if c == 3 else (BLUE if c == 4 else PURPLE))
                ax.text(cols[c], 5.45, heads[c], ha="center", va="center", fontsize=17, color=col, weight="bold",
                        linespacing=1.15)
        if stage >= 2:
            ax.add_patch(FancyBboxPatch((cols[3] - 1.0, 1.95), 2.0, 2.98, boxstyle="round,pad=0.05", fc=HL, ec="none"))
        for r in range(5):
            cells = [str(r + 1), num(X[r], 0), sgn(e[r]), num(g[r], 2), num(wpart[r], 2), num(g[r], 2)]
            for c in range(6):
                if show[c]:
                    hot = (c == 4 and r == 2)
                    ax.text(cols[c], rows[r], cells[c], ha="center", va="center", fontsize=19,
                            color=(RED if hot else INK), weight="bold" if hot else "normal")
        ax.plot([0.2, 11.0], [1.85, 1.85], color=MUTED, lw=1.2)
        if stage >= 4:
            ax.text(cols[4], 1.3, "합 " + M + "19.04", ha="center", va="center", fontsize=20, color=BLUE, weight="bold")
            ax.text(cols[4], 0.6, "= W.grad", ha="center", va="center", fontsize=19, color=BLUE)
        if stage >= 6:
            ax.text(cols[5], 1.3, "합 2.0", ha="center", va="center", fontsize=20, color=PURPLE, weight="bold")
            ax.text(cols[5], 0.6, "= B.grad", ha="center", va="center", fontsize=19, color=PURPLE)
        if stage == 3:
            ax.text(cols[4] + 0.7, rows[2], "X = 0 이라 0", fontsize=16, color=RED, va="center")
        return image(fig)

    assert [num(v, 2) for v in wpart] == [M + "5.4", M + "8.6", "0", M + "1.6", M + "3.44"]
    frames = [draw(1, "다섯 사람의 X 와 오차 e"), draw(2, "손실에서 Yp 까지 곱한 값: 사람마다 한 번만 계산"),
              draw(3, "W 쪽: 2e ÷ 5 에 X 를 곱함"), draw(4, "W 쪽 값을 모두 더하면 W.grad"),
              draw(5, "B 쪽: 2e ÷ 5 에 1 을 곱함"), draw(6, "한 번 구한 값을 W 와 B 가 나눠 씀")]
    return frames, [1800, 2400, 2200, 2200, 2000, 2500]


@figure("4c-3", 560, 300)
def trace():
    """코드 한 줄마다 바뀌는 W, B, loss, W.grad, B.grad."""
    from matplotlib.patches import Rectangle
    code = ["W = torch.tensor(1.0, requires_grad=True).float()",
            "B = torch.tensor(1.0, requires_grad=True).float()",
            "lr = 0.001",
            "Yp = pred(X)",
            "loss = mse(Yp, Y)",
            "loss.backward()",
            "with torch.no_grad():",
            "    W -= lr * W.grad",
            "    B -= lr * B.grad",
            "W.grad.zero_()",
            "B.grad.zero_()"]
    gw1, gb1 = grads(1.01904, 0.998)
    assert f"{gw1:.6f}" == "-18.598272" and abs(gb1 - 1.996) < 1e-9
    acc_w = -19.04 + gw1
    assert f"{acc_w:.3f}" == "-37.638"
    heads = ["W", "B", "loss", "W.grad", "B.grad"]

    def draw(title, lines, state, changed, note_txt=None, bad=False, dim=()):
        plt, fig = new(600)
        head(fig, title, size=20)
        top, step = 0.85, 0.064
        fig.patches.append(Rectangle((0.012, top - 10.5 * step - 0.012), 0.64, 11 * step + 0.024,
                                     transform=fig.transFigure, fc=CODEBG, ec="#e5e7eb", lw=1))
        for k, ln in enumerate(code):
            yk = top - k * step
            if k in lines:
                fig.patches.append(Rectangle((0.016, yk - step / 2 + 0.004), 0.632, step - 0.008,
                                             transform=fig.transFigure, fc=("#fee2e2" if bad else HL), ec="none"))
            fig.text(0.025, yk, ln, family=CODE, fontsize=17, va="center", color=(FAINT if k in dim else INK))
            if k in dim:
                fig.lines.append(plt.Line2D([0.025, 0.025 + 0.0104 * len(ln)], [yk, yk], transform=fig.transFigure,
                                            color=RED, lw=1.6))
        if state is not None:
            for c in range(5):
                yy = 0.83 - c * 0.135
                fig.text(0.70, yy, heads[c], ha="left", va="center", fontsize=18, color=MUTED, family=CODE)
                hit = c in changed
                fig.text(0.975, yy, state[c], ha="right", va="center", fontsize=20,
                         color=(RED if bad and hit else INK), weight="bold" if hit else "normal",
                         bbox=dict(boxstyle="round,pad=0.3", fc=(HL if hit else "white"), ec="#e5e7eb"))
        if note_txt:
            fig.text(0.5, 0.055, note_txt, ha="center", va="center", fontsize=18, color=(RED if bad else INK),
                     linespacing=1.3)
        return image(fig)

    frames = [draw("W, B 만들기: .grad 는 아직 None", [0, 1, 2], ["1", "1", "", "None", "None"], [0, 1]),
              draw("예측과 손실을 계산해도 .grad 는 None", [3, 4], ["1", "1", "13.352", "None", "None"], [2]),
              draw("backward: .grad 만 채움", [5], ["1", "1", "13.352", M + "19.04", "2.0"], [3, 4],
                   "W 와 B 는 1 에서 바뀌지 않음"),
              draw("no_grad 안에서 W, B 수정", [6, 7, 8], ["1.0190", "0.9980", "13.352", M + "19.04", "2.0"], [0, 1],
                   "W: 1 " + M + " 0.001 × (" + M + "19.04) = 1.01904    B: 1 " + M + " 0.001 × 2.0 = 0.998"),
              draw("경사를 0 으로 지움", [9, 10], ["1.0190", "0.9980", "13.352", "0", "0"], [3, 4],
                   "다음 반복의 backward 가 새 경사만 담게 함"),
              draw("with torch.no_grad(): 없이 고치면", [7, 8], None, [],
                   "RuntimeError: a leaf Variable that requires grad\nis being used in an in-place operation.",
                   bad=True, dim=[6]),
              draw("zero_ 를 빼고 다음 반복에서 backward 하면", [5],
                   ["1.0190", "0.9980", num(HIST[1, 3], 4), num(acc_w, 3), num(2.0 + gb1, 3)], [3, 4],
                   "W.grad = " + M + "19.04 + (" + M + "18.598) = " + M + "37.638", bad=True, dim=[9, 10])]
    assert num(HIST[1, 3], 4) == "12.9897" and num(2.0 + gb1, 3) == "3.996"
    return frames, [2000, 2000, 2400, 2400, 2200, 2500, 2500]


@figure("4c-4", 560, 300)
def loop():
    """학습 루프 한 바퀴. 왼쪽 다섯 줄, 오른쪽 그 줄 뒤의 값."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    codes = ["optimizer.zero_grad()", "Yp = pred(X)", "loss = mse(Yp, Y)", "loss.backward()", "optimizer.step()"]
    labs = ["경사 비우기", "① 예측", "② 손실", "③ 경사 계산(역전파)", "④ 파라미터 수정"]
    e1, after1 = HIST[1], HIST[2]
    assert num(e1[3], 4) == "12.9897" and num(after1[1], 4) == "1.0376" and num(after1[2], 4) == "0.996"

    def draw(hl, center, title):
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = fig.add_axes([0, 0, 1, 0.92])
        ax.set_xlim(0, 11.2)
        ax.set_ylim(0, 5.5)
        ax.axis("off")
        ys = [4.8, 3.8, 2.8, 1.8, 0.8]
        for k, yk in enumerate(ys):
            on = (k == hl)
            ax.add_patch(FancyBboxPatch((1.3, yk - 0.38), 5.2, 0.76, boxstyle="round,pad=0.05",
                                        fc=(HL if on else "white"), ec=(INK if on else BLUE), lw=(3 if on else 1.8)))
            ax.text(1.5, yk, codes[k], family=CODE, fontsize=18, ha="left", va="center")
            ax.text(6.35, yk, labs[k], fontsize=16, ha="right", va="center", color=MUTED)
            if k < 4:
                ax.annotate("", xy=(3.9, ys[k + 1] + 0.42), xytext=(3.9, yk - 0.42),
                            arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.6, mutation_scale=14))
        ax.add_patch(FancyArrowPatch((1.22, 0.8), (1.22, 4.8), connectionstyle="arc3,rad=-0.35", arrowstyle="-|>",
                                     mutation_scale=18, color=MUTED, lw=1.8))
        ax.text(0.3, 2.8, "되풀이", fontsize=16, color=MUTED, rotation=90, ha="center", va="center")
        ax.text(8.9, 2.8, center, ha="center", va="center", fontsize=20, linespacing=1.5,
                bbox=dict(boxstyle="round,pad=0.5", fc="#f8fafc", ec="#e5e7eb"))
        return image(fig)

    st = [("epoch 0\nW.grad, B.grad 비우기", "한 바퀴: 경사 비우기"),
          ("Yp = [" + M + "4, 6, 1, 3, " + M + "1]", "한 바퀴: ① 예측"),
          ("loss = 13.352", "한 바퀴: ② 손실"),
          ("W.grad = " + M + "19.04\nB.grad = 2.0", "한 바퀴: ③ 경사 계산"),
          ("W = 1.0190\nB = 0.9980", "한 바퀴: ④ 수정")]
    frames = [draw(k, c, t) for k, (c, t) in enumerate(st)]
    frames.append(draw(-1, "epoch 1\nloss = %s\nstep 뒤 W = %s\nB = %s" % (num(e1[3], 4), num(after1[1], 4),
                                                                         "0.9960"), "둘째 바퀴: 같은 다섯 줄을 다시"))
    frames.append(draw(-1, "500바퀴 뒤\nW = %s\nB = %s" % (num(W_END, 4), num(B_END, 4)), "500바퀴를 돈 뒤"))
    return frames, [1800, 1800, 1800, 1800, 1800, 2400, 2500]


@figure("4c-5", 560, 280)
def zero_grad_place():
    """zero_grad 를 루프 맨 앞에 둘 때와 맨 끝에 둘 때, 줄마다 W.grad. 두 자리 모두 backward 직전에 비어 있음."""
    from matplotlib.patches import Rectangle
    gw1, _ = grads(1.01904, 0.998)
    second = num(gw1, 3)
    assert second == M + "18.598"
    first = M + "19.04"
    front = [("optimizer.zero_grad()", "None", False), ("Yp = pred(X)", "None", False),
             ("loss = mse(Yp, Y)", "None", True), ("loss.backward()", first, False), ("optimizer.step()", first, False),
             None, ("optimizer.zero_grad()", "None", False), ("Yp, loss 다시 계산", "None", True),
             ("loss.backward()", second, False)]
    end = [("Yp = pred(X)", "None", False), ("loss = mse(Yp, Y)", "None", True), ("loss.backward()", first, False),
           ("optimizer.step()", first, False), ("optimizer.zero_grad()", "None", False), None,
           ("Yp, loss 다시 계산", "None", True), ("loss.backward()", second, False)]
    plt, fig = new(560)
    for title, rows, x0 in (("5차시부터: 루프 맨 앞", front, 0.02), ("4차시 노트북: 루프 맨 끝", end, 0.515)):
        fig.text(x0, 0.93, title, fontsize=20, weight="bold", color=BLUE, va="center")
        fig.text(x0 + 0.455, 0.93, "W.grad", fontsize=17, color=MUTED, family=CODE, va="center", ha="right")
        yy = 0.84
        for row in rows:
            if row is None:
                fig.lines.append(plt.Line2D([x0, x0 + 0.46], [yy + 0.01, yy + 0.01], transform=fig.transFigure,
                                            color=FAINT, lw=1.4, ls="--"))
                fig.text(x0 + 0.23, yy + 0.01, "둘째 바퀴", fontsize=15, color=MUTED, ha="center", va="center",
                         bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
                yy -= 0.07
                continue
            code, value, before = row
            if before:
                fig.patches.append(Rectangle((x0 - 0.005, yy - 0.036), 0.47, 0.072, transform=fig.transFigure,
                                             fc=HL, ec="none"))
            fig.text(x0 + 0.005, yy, code, family=CODE, fontsize=17, va="center", color=INK)
            fig.text(x0 + 0.455, yy, value, fontsize=18, va="center", ha="right",
                     color=(ORANGE if value != "None" else MUTED), weight="bold" if value != "None" else "normal")
            yy -= 0.08
    fig.text(0.5, 0.06, "노란 줄은 backward 바로 앞. 두 자리 모두 이때 W.grad 가 비어 있어 결과가 같음",
             fontsize=17, color=INK, ha="center", va="center")
    return image(fig)


@figure("4c-6", 560, 280)
def summary_4c():
    """외울 것 그림. 반복 한 번의 네 단계와 그 숫자."""
    from matplotlib.patches import FancyBboxPatch
    plt, fig = new(560)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 5.6)
    ax.axis("off")
    boxes = [((2.85, 4.15), "① 예측", "Yp = W * X + B", "[" + M + "4, 6, 1, 3, " + M + "1]"),
             ((8.35, 4.15), "② 손실", "((Yp - Y)**2).mean()", "13.352"),
             ((8.35, 1.45), "③ 경사 계산", "loss.backward()", "W.grad " + M + "19.04, B.grad 2.0"),
             ((2.85, 1.45), "④ 수정", "optimizer.step()", "W 1.0190, B 0.9980")]
    for (cx, cy), title, code, value in boxes:
        ax.add_patch(FancyBboxPatch((cx - 2.45, cy - 1.0), 4.9, 2.0, boxstyle="round,pad=0.06", fc="#eff6ff", ec=BLUE,
                                    lw=2))
        ax.text(cx, cy + 0.58, title, ha="center", va="center", fontsize=21, weight="bold", color=BLUE)
        ax.text(cx, cy, code, ha="center", va="center", fontsize=18, family=CODE)
        ax.text(cx, cy - 0.58, value, ha="center", va="center", fontsize=18)
    kw = dict(arrowstyle="-|>", color=MUTED, lw=2.4, mutation_scale=22)
    ax.annotate("", xy=(5.82, 4.15), xytext=(5.38, 4.15), arrowprops=kw)
    ax.annotate("", xy=(8.35, 2.53), xytext=(8.35, 3.07), arrowprops=kw)
    ax.annotate("", xy=(5.38, 1.45), xytext=(5.82, 1.45), arrowprops=kw)
    ax.annotate("", xy=(2.85, 3.07), xytext=(2.85, 2.53), arrowprops=kw)
    ax.text(3.05, 2.8, "경사를 지우고 500번 되풀이", fontsize=16, color=MUTED, va="center")
    ax.text(8.55, 2.8, "연쇄법칙", fontsize=16, color=MUTED, va="center")
    return image(fig)


if __name__ == "__main__":
    from tools.ai_art import render
    rows = render("l04", sys.argv[1:] or None)
    for row in rows:
        print(row["name"], os.path.relpath(row["path"], ROOT), "; ".join(row["problems"]))
