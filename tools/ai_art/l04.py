#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4차시 학습 노트 l04 의 그림(4a 선형 모델과 손실, 4b 기울기와 경사하강법, 4c 연쇄법칙·역전파·학습 코드,
4d~4h 퍼셉트론과 XOR, 활성화 함수, 국소 최적해와 모멘텀, 모델 용량과 데이터 나누기, 평가 지표).

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
NOTE, BAND = "#f3f4f6", "#e5e7eb"
GREEN_L, ORANGE_L, BLUE_L = "#d1fae5", "#ffedd5", "#eff6ff"
CODE = "D2Coding"
# 한 단원 안에서 한 색은 한 뜻이고, 뜻은 그 그림의 캡션이나 장 설명에 적음. 그림 안 설명 글은 회색(NOTE) 바탕에 적고 뜻이 없음
# 4a 단원 색: 파랑은 직선과 그 예측 Yp, 옅은 파랑은 앞 장에서 구한 예측, 보라는 B, 빨강은 오차 e 와 그 제곱,
#   초록은 평균을 뺀 값 X, Y, 노랑은 지금 계산하는 사람, 회색 점선은 평균. 검은 점은 정답
# 4b 단원 색: 파랑은 직선, 옅은 파랑은 지금이 아닌 W 의 직선, 빨강은 손실, 주황은 접선과 기울기,
#   초록은 W, B 를 바꾸는 쪽과 바꾼 뒤의 점, 회색 곡선은 등고선. 4b-2 의 확대 상자는 초록과 겹치지 않게 검은 테두리
# 4c 단원 색: 파랑은 순전파, 주황은 역전파로 곱해 온 값, 초록은 W.grad 와 거기에 보태는 값, 보라는 B.grad 와 거기에
#   보태는 값, 노랑은 실행하는 줄과 그 줄이 바꾼 값, 빨강은 잘못 쓴 코드와 그 결과, 회색 띠(BAND)는 4c-5 의 backward 바로 앞 줄
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


# 경사하강 500번(float64). k 번째 기록은 k 번 갱신한 뒤(= k 번째 반복의 갱신 전) 값으로, 노트북 history 와 같음
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
            (INK, "파라미터", "학습하며 바꿔 가는 W 와 B"),
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
              draw(6, "평균을 뺀 X, Y: 점 사이 거리는 같고 좌표값만 0 근처로")]
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
            right.append(("사람 1\n1 × (" + M + "5) + 1 = " + M + "4", INK, 20, HL))
        if stage == 5:
            right.append(("사람 2\n1 × 5 + 1 = 6", INK, 20, HL))
        if stage == 6:
            right.append(("사람 3: 1, 사람 4: 3\n사람 5: " + M + "1", INK, 19, HL))
            right.append(("Yp = [" + ", ".join(num(v, 0) for v in Yp) + "]", INK, 20, NOTE))
        yy = 0.86
        for item in right:
            text, color, size = item[:3]
            bg = item[3] if len(item) > 3 else None
            lines = text.count("\n") + 1
            note(fig, 0.64, yy, text, color=color, size=size, bg=bg, va="top")
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
                bx.axhline(sq.mean(), color=MUTED, lw=2.5, ls="--", zorder=4)
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
    boxes = [(1.85, "평균 빼기", "X = x - x.mean()", "X = [" + M + "5, 5, 0, 2, " + M + "2]", GREEN, GREEN),
             (5.6, "선형 모델", "Yp = W * X + B", "Yp = [" + M + "4, 6, 1, 3, " + M + "1]", BLUE, BLUE),
             (9.35, "손실(MSE)", "((Yp - Y)**2).mean()", "13.352", "#9ca3af", INK)]
    for cx, title, code, value, edge, ink in boxes:
        ax.add_patch(FancyBboxPatch((cx - 1.7, 1.75), 3.4, 2.5, boxstyle="round,pad=0.06", fc="white", ec=edge, lw=2))
        ax.text(cx, 3.75, title, ha="center", va="center", fontsize=21, weight="bold", color=ink)
        ax.text(cx, 2.95, code, ha="center", va="center", fontsize=17, family=CODE, color=INK)
        ax.text(cx, 2.25, value, ha="center", va="center", fontsize=18, color=INK)
    kw = dict(arrowstyle="-|>", color=MUTED, lw=2.4, mutation_scale=22)
    ax.annotate("", xy=(3.85, 3.0), xytext=(3.6, 3.0), arrowprops=kw)
    ax.annotate("", xy=(7.6, 3.0), xytext=(7.35, 3.0), arrowprops=kw)
    ax.text(5.6, 0.95, "오차 e = Yp " + M + " Y 를 제곱해 평균 냄. 제곱하면 양수 오차와 음수 오차가 지워지지 않음",
            ha="center", va="center", fontsize=17, color=INK,
            bbox=dict(boxstyle="round,pad=0.35", fc=NOTE, ec="none"))
    return image(fig)


# 4b 기울기와 경사하강법

@figure("4b-1", 560, 300)
def slope():
    """직선의 기울기 W 와 손실 곡선의 기울기. 왼쪽 직선, 오른쪽 손실 곡선과 접선."""
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
            sub = "접선이 평평함: 기울기 0, 손실이 가장 작음"
        elif s > 0:
            sub = "기울기 " + stxt + ": W 를 줄여야 손실이 줄어듦"
        else:
            sub = "기울기 " + stxt + ": W 를 키우면 손실이 줄어듦"
        fig, ax, bx = base(w, "직선의 기울기 W = " + num(w, 4), "W = " + num(w, 4) + ": 손실 " + num(LW(w), 3))
        tangent(bx, w)
        note(bx, 0.98, 0.96, sub, size=17, ha="right", va="top", transform=bx.transAxes)
        frames.append(image(fig))
        dur.append(2200)

    fig, ax, bx = base(1.0, "지금 W = 1", "기울기 " + M + "19.04: 음수")
    tangent(bx, 1.0)
    bx.annotate("", xy=(1.55, LW(1.55) + 1.0), xytext=(1.05, LW(1.05) + 1.5),
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=3.2, connectionstyle="arc3,rad=0.25"))
    note(bx, 0.98, 0.96, "W 를 키우면 손실이 줄어듦", size=17, color=GREEN, ha="right", va="top", transform=bx.transAxes)
    frames.append(image(fig))
    dur.append(2500)
    return frames, dur


@figure("4b-2", 560, 300)
def descent():
    """손실 등고선 위의 경사하강법. 기울기 화살표, 반대쪽 갱신, 실제 한 번 갱신, 되풀이한 길."""
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
        fig.text(0.58, 0.72, "★ 손실이 가장 작은 곳 (1.82, 0): 4.539", fontsize=18, color=INK, va="center")
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
    plt, fig, ax = base("기울기 (" + M + "19.04, 2.0) 가 가리키는 쪽", "주황: 손실이 가장 빨리 커지는 쪽")
    arrow(ax, u, ORANGE, "기울기", 1.12)
    frames.append(image(fig))
    dur.append(2200)
    plt, fig, ax = base("경사하강법은 W, B 를 반대쪽으로 바꿈", "초록: W, B 를 실제로 바꾸는 쪽\n(화살표 길이는 늘려 그림)")
    arrow(ax, u, ORANGE, "기울기", 1.12)
    arrow(ax, -u, GREEN, "갱신", 0.89)
    frames.append(image(fig))
    dur.append(2400)
    plt, fig, ax = base("한 번 갱신: 학습률 0.001", "W: 1 " + M + " 0.001 × (" + M + "19.04) = 1.01904\nB: 1 " + M +
                        " 0.001 × 2.0 = 0.998")
    ax.add_patch(Rectangle((0.94, 0.94), 0.12, 0.12, fill=False, ec=INK, lw=2, zorder=9))
    ix = fig.add_axes([0.60, 0.33, 0.34, 0.30])
    ix.set_facecolor("white")
    for sp in ix.spines.values():
        sp.set_edgecolor(INK)
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
    ix.set_title("검은 상자 안을 크게 봄", fontsize=16, loc="left", pad=4)
    frames.append(image(fig))
    dur.append(2500)

    marks = [(10,), (50,), (100, 200), (490,)]
    for g, grp in enumerate(marks):
        k = grp[-1]
        if k == 490:
            sub = "500번 갱신한 뒤 W " + num(W_END, 4) + ", B " + num(B_END, 4) + "\nW 는 빨리, B 는 천천히 바뀜"
        elif k == 200:
            sub = "200번 갱신한 뒤 W 는 " + f"{HIST[200, 1]:.2f}" + ",\nB 는 아직 " + f"{HIST[200, 2]:.2f}"
        else:
            sub = "%d번 갱신한 뒤 손실 %s" % (k, num(HIST[k, 3], 4))
        plt, fig, ax = base("%d번 갱신하는 동안 지나온 점" % k, sub)
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
            note(bx, 0.98, 0.96, "500번 갱신한 뒤\nW = %s, B = %s" % (num(W_END, 4), num(B_END, 4)), size=18, ha="right",
                 va="top", transform=bx.transAxes)
        frames.append(image(fig))
        dur.append(1600 if j < len(eps) - 1 else 2500)
    assert num(HIST[100, 1], 2) == "1.74" and num(HIST[300, 2], 4) == "0.5485"
    assert num(HIST[490, 1], 4) == "1.8207" and num(HIST[490, 2], 4) == "0.3749"
    return frames, dur


@figure("4b-4", 560, 280)
def summary_4b():
    """외울 것 그림. 기울기의 반대쪽으로 갱신, 되풀이."""
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
    bx.set_title("기울기 " + M + "19.04: W 를 키우면 손실이 줄어듦", loc="left", pad=10, fontsize=19)
    lines = [("기울기는 손실이 가장 빨리 커지는 쪽", ORANGE, 19, False),
             ("경사하강법은 그 반대쪽으로 갱신", GREEN, 19, False),
             ("새 W = W " + M + " 학습률 × W.grad", INK, 19, True),
             ("1 " + M + " 0.001 × (" + M + "19.04) = 1.01904", INK, 18, False),
             ("예측 → 손실 → 기울기 계산 → 갱신", INK, 19, True),
             ("500번 되풀이: W 1.8207, B 0.3675", INK, 18, False)]
    assert num(W_END, 4) == "1.8207" and num(B_END, 4) == "0.3675"
    yy = 0.86
    for k, (text, color, size, gap) in enumerate(lines):
        if gap:
            yy -= 0.04
        fig.text(0.53, yy, text, fontsize=size, color=color, va="center",
                 weight="bold" if color != INK or k == 4 else "normal")
        yy -= 0.115
    return image(fig)


# 4c 연쇄법칙, 역전파, 학습 코드

@figure("4c-1", 560, 260)
def chain():
    """사람 2 의 연쇄법칙. 순전파로 값을 채우고 역전파로 미분값을 곱해 감."""
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
    locd = ["미분값 5", "미분값 1", "미분값 2e\n= " + M + "8.6", "미분값 1/5\n= 0.2"]
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
            ax.text(5.6, 0.75, "← 역전파: 오른쪽에서 왼쪽으로 미분값을 곱해 감", ha="center", va="center", fontsize=18,
                    color=ORANGE)
        if nback:
            ax.text(xs[4], 1.35, "1", ha="center", va="center", fontsize=19, color=ORANGE, weight="bold")
            ax.annotate("", xy=(0.25, 0.32), xytext=(10.95, 0.32),
                        arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=2, mutation_scale=18))
            ax.text(5.6, 0.55, "거꾸로 곱해 감", ha="center", va="bottom", fontsize=16, color=ORANGE)
        for j in range(max(0, nback - 1)):
            k = back_at[j]
            big = (j == 3)
            ax.text(xs[k], 1.35, back[j], ha="center", va="center", fontsize=18 if big else 16,
                    color=GREEN if big else ORANGE, weight="bold" if big else "normal", linespacing=1.15,
                    bbox=dict(boxstyle="round,pad=0.25", fc=GREEN_L, ec="none") if big else None)
        return image(fig)

    frames = [draw(0, False, 0, "사람 2 (X = 5, Y = 10.3) 의 계산 단계", tags=True),
              draw(2, False, 0, "순전파: W = 1 에서 Yp = 1 × 5 + 1 = 6"),
              draw(5, False, 0, "순전파: 왼쪽에서 오른쪽으로 값 계산"),
              draw(5, True, 0, "단계마다 미분값: 뒤 칸 변화량이 앞 칸 변화량의 몇 배인지"),
              draw(5, True, 1, "역전파: L 에서 1 로 시작"),
              draw(5, True, 2, "s 까지: 1 × 0.2"),
              draw(5, True, 3, "e 까지: 0.2 × (" + M + "8.6)"),
              draw(5, True, 4, "Yp 까지: " + M + "1.72 × 1"),
              draw(5, True, 5, "W 까지: 사람 2 가 W.grad 에 보태는 값 " + M + "8.6")]
    return frames, [2000, 1800, 2000, 2500, 1800, 1800, 1800, 1800, 2500]


@figure("4c-2", 560, 300)
def backprop():
    """다섯 사람의 역전파. 손실에서 Yp 까지 미분값을 곱한 값 2e ÷ 5 를 W.grad 와 B.grad 계산에 함께 씀."""
    from matplotlib.patches import FancyBboxPatch
    e = X + 1 - Y
    g = 2 * e / N
    wpart = g * X
    assert np.allclose(g, [1.08, -1.72, 1.72, -0.8, 1.72]) and np.allclose(wpart, [-5.4, -8.6, 0, -1.6, -3.44])
    assert abs(wpart.sum() + 19.04) < 1e-9 and abs(g.sum() - 2.0) < 1e-9
    cols = [0.75, 1.95, 3.35, 5.45, 7.75, 9.95]
    heads = ["사람", "X", "오차 e", "2e ÷ 5", "W.grad 에\n보탤 값\n(2e ÷ 5) × X", "B.grad 에\n보탤 값\n(2e ÷ 5) × 1"]
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
                col = INK if c < 3 else (ORANGE if c == 3 else (GREEN if c == 4 else PURPLE))
                ax.text(cols[c], 5.45, heads[c], ha="center", va="center", fontsize=17, color=col, weight="bold",
                        linespacing=1.15)
        if stage >= 2:
            ax.add_patch(FancyBboxPatch((cols[3] - 1.0, 1.95), 2.0, 2.98, boxstyle="round,pad=0.05", fc=ORANGE_L,
                                        ec="none"))
        for r in range(5):
            cells = [str(r + 1), num(X[r], 0), sgn(e[r]), num(g[r], 2), num(wpart[r], 2), num(g[r], 2)]
            for c in range(6):
                if show[c]:
                    hot = (c == 4 and r == 2 and stage == 3)
                    ax.text(cols[c], rows[r], cells[c], ha="center", va="center", fontsize=19, color=INK,
                            weight="bold" if hot else "normal")
        ax.plot([0.2, 11.0], [1.85, 1.85], color=MUTED, lw=1.2)
        if stage >= 4:
            ax.text(cols[4], 1.3, "합 " + M + "19.04", ha="center", va="center", fontsize=20, color=GREEN, weight="bold")
            ax.text(cols[4], 0.6, "= W.grad", ha="center", va="center", fontsize=19, color=GREEN)
        if stage >= 6:
            ax.text(cols[5], 1.3, "합 2.0", ha="center", va="center", fontsize=20, color=PURPLE, weight="bold")
            ax.text(cols[5], 0.6, "= B.grad", ha="center", va="center", fontsize=19, color=PURPLE)
        if stage == 3:
            ax.text(cols[4] + 0.7, rows[2], "X = 0 이라 0", fontsize=16, color=MUTED, va="center")
        return image(fig)

    assert [num(v, 2) for v in wpart] == [M + "5.4", M + "8.6", "0", M + "1.6", M + "3.44"]
    frames = [draw(1, "다섯 사람의 X 와 오차 e"), draw(2, "손실에서 Yp 까지 미분값을 곱한 값 2e ÷ 5: 사람마다 한 번만 계산"),
              draw(3, "W.grad: 2e ÷ 5 에 X 를 곱함"), draw(4, "다섯 값을 모두 더하면 W.grad"),
              draw(5, "B.grad: 2e ÷ 5 에 1 을 곱함"), draw(6, "한 번 구한 2e ÷ 5 를 W.grad 와 B.grad 계산에 함께 씀")]
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
              draw("no_grad 안에서 W, B 갱신", [6, 7, 8], ["1.0190", "0.9980", "13.352", M + "19.04", "2.0"], [0, 1],
                   "W: 1 " + M + " 0.001 × (" + M + "19.04) = 1.01904    B: 1 " + M + " 0.001 × 2.0 = 0.998"),
              draw("기울기를 0 으로 지움", [9, 10], ["1.0190", "0.9980", "13.352", "0", "0"], [3, 4],
                   "다음 반복의 backward 가 새 기울기만 담게 함"),
              draw("with torch.no_grad(): 없이 갱신하면", [7, 8], None, [],
                   "RuntimeError: a leaf Variable that requires grad\nis being used in an in-place operation.",
                   bad=True, dim=[6]),
              draw("zero_ 를 빼고 다음 반복에서 backward 하면", [5],
                   ["1.0190", "0.9980", num(HIST[1, 3], 4), num(acc_w, 3), num(2.0 + gb1, 3)], [3, 4],
                   "W.grad = " + M + "19.04 + (" + M + "18.598) = " + M + "37.638", bad=True, dim=[9, 10])]
    assert num(HIST[1, 3], 4) == "12.9897" and num(2.0 + gb1, 3) == "3.996"
    return frames, [2000, 2000, 2400, 2400, 2200, 2500, 2500]


@figure("4c-4", 560, 300)
def loop():
    """학습 루프 한 번 반복. 왼쪽 다섯 줄, 오른쪽 그 줄 뒤의 값."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    codes = ["optimizer.zero_grad()", "Yp = pred(X)", "loss = mse(Yp, Y)", "loss.backward()", "optimizer.step()"]
    labs = ["기울기 비우기", "① 예측", "② 손실", "③ 기울기 계산(역전파)", "④ 파라미터 갱신"]
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
                                        fc=(HL if on else "white"), ec=(INK if on else "#9ca3af"), lw=(3 if on else 1.8)))
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

    st = [("epoch 0\nW.grad, B.grad 비우기", "첫 반복: 기울기 비우기"),
          ("Yp = [" + M + "4, 6, 1, 3, " + M + "1]", "첫 반복: ① 예측"),
          ("loss = 13.352", "첫 반복: ② 손실"),
          ("W.grad = " + M + "19.04\nB.grad = 2.0", "첫 반복: ③ 기울기 계산"),
          ("W = 1.0190\nB = 0.9980", "첫 반복: ④ 갱신")]
    frames = [draw(k, c, t) for k, (c, t) in enumerate(st)]
    frames.append(draw(-1, "epoch 1\nloss = %s\nstep 뒤 W = %s\nB = %s" % (num(e1[3], 4), num(after1[1], 4),
                                                                         "0.9960"), "둘째 반복: 같은 다섯 줄을 다시"))
    frames.append(draw(-1, "500번 반복한 뒤\nW = %s\nB = %s" % (num(W_END, 4), num(B_END, 4)), "500번 반복한 뒤"))
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
        fig.text(x0, 0.93, title, fontsize=20, weight="bold", color=INK, va="center")
        fig.text(x0 + 0.455, 0.93, "W.grad", fontsize=17, color=MUTED, family=CODE, va="center", ha="right")
        yy = 0.84
        for row in rows:
            if row is None:
                fig.lines.append(plt.Line2D([x0, x0 + 0.46], [yy + 0.01, yy + 0.01], transform=fig.transFigure,
                                            color=FAINT, lw=1.4, ls="--"))
                fig.text(x0 + 0.23, yy + 0.01, "둘째 반복", fontsize=15, color=MUTED, ha="center", va="center",
                         bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
                yy -= 0.07
                continue
            code, value, before = row
            if before:
                fig.patches.append(Rectangle((x0 - 0.005, yy - 0.036), 0.47, 0.072, transform=fig.transFigure,
                                             fc=BAND, ec="none"))
            fig.text(x0 + 0.005, yy, code, family=CODE, fontsize=17, va="center", color=INK)
            fig.text(x0 + 0.455, yy, value, fontsize=18, va="center", ha="right",
                     color=(GREEN if value != "None" else MUTED), weight="bold" if value != "None" else "normal")
            yy -= 0.08
    fig.text(0.5, 0.06, "회색 줄은 backward 바로 앞. 두 자리 모두 이때 W.grad 가 비어 있어 결과가 같음",
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
    forward, backward, plain = (BLUE_L, BLUE, BLUE), (ORANGE_L, ORANGE, ORANGE), ("white", "#9ca3af", INK)
    boxes = [((2.85, 4.15), "① 예측", "Yp = W * X + B", "[" + M + "4, 6, 1, 3, " + M + "1]", forward),
             ((8.35, 4.15), "② 손실", "((Yp - Y)**2).mean()", "13.352", forward),
             ((8.35, 1.45), "③ 기울기 계산", "loss.backward()", "W.grad " + M + "19.04, B.grad 2.0", backward),
             ((2.85, 1.45), "④ 갱신", "optimizer.step()", "W 1.0190, B 0.9980", plain)]
    for (cx, cy), title, code, value, (fc, ec, ink) in boxes:
        ax.add_patch(FancyBboxPatch((cx - 2.45, cy - 1.0), 4.9, 2.0, boxstyle="round,pad=0.06", fc=fc, ec=ec, lw=2))
        ax.text(cx, cy + 0.58, title, ha="center", va="center", fontsize=21, weight="bold", color=ink)
        ax.text(cx, cy, code, ha="center", va="center", fontsize=18, family=CODE)
        ax.text(cx, cy - 0.58, value, ha="center", va="center", fontsize=18)
    kw = dict(arrowstyle="-|>", color=MUTED, lw=2.4, mutation_scale=22)
    ax.annotate("", xy=(5.82, 4.15), xytext=(5.38, 4.15), arrowprops=kw)
    ax.annotate("", xy=(8.35, 2.53), xytext=(8.35, 3.07), arrowprops=kw)
    ax.annotate("", xy=(5.38, 1.45), xytext=(5.82, 1.45), arrowprops=kw)
    ax.annotate("", xy=(2.85, 3.07), xytext=(2.85, 2.53), arrowprops=kw)
    ax.text(3.05, 2.8, "기울기를 지우고 500번 되풀이", fontsize=16, color=MUTED, va="center")
    ax.text(8.55, 2.8, "연쇄법칙", fontsize=16, color=MUTED, va="center")
    return image(fig)


# 4d~4h 단원 그림(PR2). 새 단원도 한 단원 안에서 한 색은 한 뜻이고, 뜻은 그 그림의 캡션에 적음
# 4d: 파랑은 출력 1(채운 점과 그쪽 영역), 회색 빈 점은 출력 0, 주황은 퍼셉트론이 긋는 직선, 빨강 테두리는 잘못 나뉜 점,
#   보라는 은닉층이 만든 값과 신경망의 층이 배우는 일, 초록은 사람이 하는 일. 4d-2 는 색에 뜻이 없음(검정·회색만)
# 4e: 파랑은 함수 값(층을 지난 출력), 주황은 미분값, 회색 띠는 미분값이 0 에 가까운 포화 구간, 회색 점선은 출력이 넘지 않는 값
# 4f: 빨강은 손실 곡선 f(x), 파랑은 모멘텀 없는 경사하강법, 보라는 모멘텀
# 4g: 파랑은 학습 데이터, 주황은 검증(새) 데이터, 보라는 테스트 데이터, 초록은 모델의 예측선, 빨강은 데이터 누수
# 4h: 파랑은 직선·예측, 빨강은 오차와 틀린 판정, 초록은 맞힌 판정, 회색 점선은 임계값, 보라는 ROC 곡선, 노랑 테두리는 지표가 쓰는 칸
PURPLE_L, RED_L, YELLOW_B = "#ede9fe", "#fee2e2", "#fde68a"
STEP4 = [(0, 0), (0, 1), (1, 0), (1, 1)]


def fmt2(v):
    """소수 둘째 자리까지 0 을 남겨 찍는 숫자(빼기표 U+2212)."""
    return f"{v:.2f}".replace("-", M)


def step_out(z):
    return 1 if z > 0 else 0


def perceptron_out(w1, w2, b):
    return [step_out(w1 * a + w2 * c + b) for a, c in STEP4]


def boxes_axes(fig, rect=(0, 0, 1, 1), xmax=11.2, ymax=6.0):
    ax = fig.add_axes(list(rect))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return ax


def card(ax, x0, y0, w, h, title, lines, edge="#9ca3af", fill="white", ink=INK, size=17, tsize=20, gap=0.52):
    """외울 것 그림의 상자 하나. lines 는 (글, 색) 이나 글."""
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0.05", fc=fill, ec=edge, lw=2))
    ax.text(x0 + 0.18, y0 + h - 0.38, title, ha="left", va="center", fontsize=tsize, weight="bold", color=ink)
    yy = y0 + h - 0.95
    for line in lines:
        text, color = (line, INK) if isinstance(line, str) else line
        ax.text(x0 + 0.22, yy, text, ha="left", va="center", fontsize=size, color=color)
        yy -= gap


# 4d 머신러닝, 딥러닝, 퍼셉트론과 XOR

@figure("4d-1", 560, 300)
def ai_ml_dl():
    """인공지능 ⊃ 머신러닝 ⊃ 딥러닝(왼쪽 원 셋)과 특징을 누가 만드는지(오른쪽 두 줄)."""
    from matplotlib.patches import Circle, FancyBboxPatch
    plt, fig = new(600)
    ax = fig.add_axes([0.0, 0.0, 0.47, 1.0])
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.08, 1.08)
    ax.set_aspect("equal")
    ax.axis("off")
    for (cx, cy, r, fc, name, ex, ty) in [(0, 0, 1.0, "#f8fafc", "인공지능", "체스, 번역기, 챗봇", 0.80),
                                          (0, -0.16, 0.76, "#f3f4f6", "머신러닝", "스팸 필터, 다섯 사람 직선", 0.40),
                                          (0, -0.33, 0.50, "#e5e7eb", "딥러닝", "얼굴 인식, 자율주행", -0.18)]:
        ax.add_patch(Circle((cx, cy), r, fc=fc, ec=MUTED, lw=2.2))
        ax.text(0, ty, name, ha="center", va="center", fontsize=21, weight="bold", color=INK)
        ax.text(0, ty - 0.15, ex, ha="center", va="center", fontsize=16, color=INK)
    bx = boxes_axes(fig, (0.47, 0.0, 0.53, 1.0), xmax=5.9, ymax=6.0)
    bx.text(0.05, 5.7, "특징은 누가 만드나", fontsize=21, weight="bold", color=INK, va="center")
    rows = [(3.75, "직선 모델 예", [("데이터", "신장, 체중", "white", "#9ca3af", INK),
                              ("사람이 특징을 고름", "신장", GREEN_L, GREEN, GREEN),
                              ("모델이 학습", "W, B", "white", "#9ca3af", INK)]),
            (1.55, "딥러닝", [("데이터", "사진의 픽셀값", "white", "#9ca3af", INK),
                            ("층이 특징까지 배움", "", PURPLE_L, PURPLE, PURPLE)])]
    for y0, name, steps in rows:
        bx.text(0.05, y0 + 0.9, name, fontsize=20, weight="bold", color=INK, va="center")
        xs = [0.05, 1.85, 4.2] if len(steps) == 3 else [0.05, 1.85]
        ws = [1.55, 2.1, 1.6] if len(steps) == 3 else [1.55, 3.95]
        for (title, sub, fc, ec, ink), x0, w in zip(steps, xs, ws):
            bx.add_patch(FancyBboxPatch((x0, y0 - 0.55), w, 1.1, boxstyle="round,pad=0.04", fc=fc, ec=ec, lw=2))
            bx.text(x0 + w / 2, y0 + (0.18 if sub else 0), title, ha="center", va="center", fontsize=16, color=ink,
                    weight="bold")
            if sub:
                bx.text(x0 + w / 2, y0 - 0.25, sub, ha="center", va="center", fontsize=15, color=INK)
        for x0, w in zip(xs[:-1], ws[:-1]):
            bx.annotate("", xy=(x0 + w + 0.25, y0), xytext=(x0 + w + 0.02, y0),
                        arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=2, mutation_scale=16))
    bx.text(0.05, 0.3, "두 방법 모두 데이터로 파라미터를 찾음", fontsize=16, color=INK, va="center")
    return image(fig)


@figure("4d-2", 560, 300)
def learning_types():
    """학습 방식 넷을 2×2 칸에. 색에는 뜻이 없음."""
    from matplotlib.patches import Ellipse, FancyBboxPatch
    plt, fig = new(600)
    panels = [(0.02, 0.51, "지도학습", "주는 것: 입력과 정답의 쌍"), (0.52, 0.51, "비지도학습", "주는 것: 정답 없는 데이터"),
              (0.02, 0.01, "자기지도학습", "정답을 데이터에서 만듦"), (0.52, 0.01, "강화학습", "주는 것: 행동마다 받는 보상")]
    for px, py, title, sub in panels:
        fig.patches.append(FancyBboxPatch((px, py), 0.46, 0.47, boxstyle="round,pad=0.005", transform=fig.transFigure,
                                          fc="none", ec=FAINT, lw=1.6, zorder=0))
        fig.text(px + 0.015, py + 0.425, title, fontsize=19, weight="bold", color=INK, va="center")
        fig.text(px + 0.015, py + 0.365, sub, fontsize=15, color=MUTED, va="center")
    a1 = fig.add_axes([0.08, 0.61, 0.37, 0.23])
    tidy(a1, grid=False)
    a1.scatter(x, y, s=55, color=INK, zorder=5)
    xs = np.array([164, 178])
    a1.plot(xs, y.mean() + 1.820683 * (xs - 171) + 0.3675, color=MUTED, lw=2)
    a1.set_xticks([166, 171, 176])
    a1.set_yticks([60, 70])
    a1.tick_params(labelsize=15)
    a1.set_xlabel("신장 (입력)", fontsize=15, labelpad=1)
    a1.set_ylabel("체중 (정답)", fontsize=15, labelpad=8)
    a2 = fig.add_axes([0.55, 0.53, 0.40, 0.33])
    a2.axis("off")
    pts = {(-2.2, 1.0): [(0, 0), (0.35, 0.3), (-0.3, 0.25), (0.1, -0.35)], (1.6, 1.4): [(0, 0), (0.3, -0.25), (-0.25, -0.3), (0.2, 0.3)],
           (0.0, -1.0): [(0, 0), (0.35, 0.1), (-0.3, 0.2), (0.0, -0.35)]}
    for (cx, cy), offs in pts.items():
        a2.scatter([cx + dx for dx, _ in offs], [cy + dy for _, dy in offs], s=55, color=INK, zorder=5)
        a2.add_patch(Ellipse((cx, cy), 1.4, 1.25, fc="none", ec=MUTED, lw=1.8, ls="--"))
    a2.set_xlim(-3.2, 2.6)
    a2.set_ylim(-1.9, 2.2)
    a2.text(2.9, -1.95, "비슷한 것끼리 묶음", fontsize=15, color=MUTED, ha="right")
    a3 = boxes_axes(fig, (0.03, 0.03, 0.44, 0.32), xmax=5.5, ymax=3.0)
    a3.text(0.1, 2.3, "다섯 사람의 신장과", fontsize=17, color=INK, va="center")
    a3.add_patch(FancyBboxPatch((3.1, 1.95), 1.4, 0.7, boxstyle="round,pad=0.04", fc=NOTE, ec=INK, lw=1.6))
    a3.text(3.8, 2.3, "(가림)", fontsize=17, color=INK, ha="center", va="center")
    a3.annotate("", xy=(3.8, 0.95), xytext=(3.8, 1.85), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=2, mutation_scale=16))
    a3.text(3.8, 0.6, "정답: 체중", fontsize=17, color=INK, ha="center", va="center", weight="bold")
    a3.text(0.1, 0.6, "원래 문장에서\n정답을 얻음", linespacing=1.5, fontsize=15, color=MUTED, va="center")
    a4 = boxes_axes(fig, (0.53, 0.03, 0.44, 0.32), xmax=5.5, ymax=3.0)
    a4.add_patch(FancyBboxPatch((0.1, 0.9), 1.6, 1.0, boxstyle="round,pad=0.04", fc=NOTE, ec=INK, lw=1.6))
    a4.text(0.9, 1.4, "로봇 청소기", fontsize=16, ha="center", va="center", color=INK)
    a4.add_patch(FancyBboxPatch((3.8, 0.9), 1.5, 1.0, boxstyle="round,pad=0.04", fc=NOTE, ec=INK, lw=1.6))
    a4.text(4.55, 1.4, "방", fontsize=16, ha="center", va="center", color=INK)
    a4.annotate("", xy=(3.75, 1.75), xytext=(1.75, 1.75), arrowprops=dict(arrowstyle="-|>", color=INK, lw=2, mutation_scale=16))
    a4.text(2.75, 2.1, "행동: 움직이기", fontsize=15, ha="center", va="center", color=INK)
    a4.annotate("", xy=(1.75, 1.05), xytext=(3.75, 1.05), arrowprops=dict(arrowstyle="-|>", color=INK, lw=2, mutation_scale=16))
    a4.text(2.75, 0.62, "상태, 보상 +1·" + M + "5", fontsize=15, ha="center", va="center", color=INK)
    return image(fig)


def gate_axes(fig, rect, xlabel="x1", ylabel="x2", color=INK):
    ax = fig.add_axes(rect)
    tidy(ax, grid=False)
    ax.set_xlim(-0.45, 1.6)
    ax.set_ylim(-0.45, 1.6)
    ax.set_aspect("equal")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xlabel(xlabel, color=color)
    ax.set_ylabel(ylabel, color=color, rotation=0, labelpad=14)
    return ax


def gate_points(ax, outs, pts=STEP4, wrong=(), labels=True, left=()):
    """left 에 든 점은 직선과 겹치지 않게 이름을 왼쪽 아래에 씀."""
    for (a, c), o in zip(pts, outs):
        if o:
            ax.scatter([a], [c], s=260, color=BLUE, zorder=6)
        else:
            ax.scatter([a], [c], s=260, facecolor="white", edgecolor="#9ca3af", lw=2.6, zorder=6)
    for k in wrong:
        a, c = pts[k]
        ax.scatter([a], [c], s=620, facecolor="none", edgecolor=RED, lw=3.2, zorder=7)
    if labels:
        for k, (a, c) in enumerate(pts):
            ax.text(a + (-0.09 if k in left else 0.09), c - 0.17, "(%d, %d)" % (a, c), fontsize=15, color=MUTED, zorder=8,
                    ha="right" if k in left else "left")


def gate_line(ax, w1, w2, b, shade=True, color=ORANGE, fill=None):
    """z = w1 x1 + w2 x2 + b = 0 인 직선과 z > 0 쪽 영역."""
    xs = np.linspace(-0.45, 1.6, 50)
    ys = -(w1 * xs + b) / w2
    ax.plot(xs, ys, color=color, lw=3.2, zorder=4)
    if shade:
        top = np.full_like(xs, 1.6)
        bottom = np.full_like(xs, -0.45)
        if w2 > 0:
            ax.fill_between(xs, ys, top, color=fill or "#dbeafe", zorder=1)
        else:
            ax.fill_between(xs, bottom, ys, color=fill or "#dbeafe", zorder=1)


@figure("4d-3", 560, 300)
def perceptron_and_or():
    """퍼셉트론 하나가 평면을 직선 하나로 나눔. AND(b = −1.5)와 OR(b = −0.5)."""
    AND, OR = perceptron_out(1, 1, -1.5), perceptron_out(1, 1, -0.5)
    zs = [1 * a + 1 * c - 1.5 for a, c in STEP4]
    assert AND == [0, 0, 0, 1] and OR == [0, 1, 1, 1] and zs == [-1.5, -0.5, -0.5, 0.5]

    def draw(stage, title):
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = gate_axes(fig, [0.06, 0.13, 0.44, 0.74])
        outs = [None] * 4
        if stage == 1:
            gate_points(ax, [0, 0, 0, 0])
        elif stage in (2, 3):
            if stage == 3:
                gate_line(ax, 1, 1, -1.5)
            gate_points(ax, AND)
            if stage == 2:
                for (a, c), z in zip(STEP4, zs):
                    ax.text(a - 0.08, c + 0.17, "z = " + num(z, 1), fontsize=16, color=INK, ha="left",
                            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
        else:
            gate_line(ax, 1, 1, -0.5)
            gate_points(ax, OR)
        right = [("z = w1 × x1 + w2 × x2 + b", INK, 20, True), ("z > 0 이면 1, 아니면 0", INK, 18, False)]
        if stage in (2, 3):
            right += [("w1 = 1, w2 = 1, b = " + M + "1.5", INK, 18, False), ("출력 0, 0, 0, 1: AND", BLUE, 19, True)]
        if stage == 3:
            right += [("직선 x1 + x2 = 1.5", ORANGE, 18, False)]
        if stage >= 4:
            right += [("w1 = 1, w2 = 1, b = " + M + "0.5", INK, 18, False), ("출력 0, 1, 1, 1: OR", BLUE, 19, True),
                      ("직선 x1 + x2 = 0.5", ORANGE, 18, False)]
        if stage == 5:
            right += [("b 를 바꾸면 직선이 옮겨 감", INK, 18, False), ("퍼셉트론 하나 = 직선 하나", INK, 19, True)]
        yy = 0.80
        for text, color, size, bold in right:
            fig.text(0.56, yy, text, fontsize=size, color=color, va="center", weight="bold" if bold else "normal")
            yy -= 0.105
        return image(fig)

    frames = [draw(1, "입력 두 개, 점 네 개"), draw(2, "z 를 계산해 0 보다 크면 1"), draw(3, "z = 0 인 직선으로 나눈 AND"),
              draw(4, "b 만 바꾼 OR"), draw(5, "퍼셉트론 하나는 직선 하나로 나눔")]
    return frames, [1800, 2400, 2400, 2400, 2500]


@figure("4d-4", 560, 300)
def xor_hidden():
    """XOR 은 직선 하나로 나뉘지 않고, 은닉층 (h1, h2) 에서는 나뉨. 마지막 장은 신경망 그림."""
    from matplotlib.patches import Circle
    XOR = [0, 1, 1, 0]
    h1s, h2s = perceptron_out(1, 1, -0.5), perceptron_out(-1, -1, 1.5)
    hpts = list(zip(h1s, h2s))
    ys = [step_out(a + c - 1.5) for a, c in hpts]
    assert ys == XOR and hpts == [(0, 1), (1, 1), (1, 1), (1, 0)]
    # 직선 하나로 XOR 를 만드는 w1, w2, b 는 없음(격자 −3~3, 0.1 간격)
    grid = np.round(np.arange(-3, 3.01, 0.1), 2)
    assert not any(perceptron_out(a, c, b) == XOR for a in grid for c in grid for b in grid[::5])
    wrong2 = [k for k, (o, t) in enumerate(zip(perceptron_out(1, 1, -0.5), XOR)) if o != t]
    wrong3 = [k for k, (o, t) in enumerate(zip(perceptron_out(-1, 1, -0.5), XOR)) if o != t]
    assert wrong2 == [3] and wrong3 == [2]

    def draw(stage, title):
        plt, fig = new(600)
        head(fig, title, size=20)
        if stage == 7:
            ax = boxes_axes(fig, (0, 0, 1, 0.92), xmax=11.2, ymax=5.6)
            nodes = {"x1": (1.4, 4.0), "x2": (1.4, 1.8), "h1": (5.2, 4.0), "h2": (5.2, 1.8), "y": (9.0, 2.9)}
            for a in ("x1", "x2"):
                for h in ("h1", "h2"):
                    ax.plot([nodes[a][0], nodes[h][0]], [nodes[a][1], nodes[h][1]], color="#9ca3af", lw=2, zorder=1)
            for h in ("h1", "h2"):
                ax.plot([nodes[h][0], nodes["y"][0]], [nodes[h][1], nodes["y"][1]], color="#9ca3af", lw=2, zorder=1)
            for name, (cx, cy) in nodes.items():
                ec = PURPLE if name[0] == "h" else INK
                ax.add_patch(Circle((cx, cy), 0.5, fc=PURPLE_L if name[0] == "h" else "white", ec=ec, lw=2.6, zorder=3))
                ax.text(cx, cy, name, ha="center", va="center", fontsize=21, weight="bold", color=ec, zorder=4)
            ax.text(5.9, 4.0, "OR", fontsize=17, color=PURPLE, va="center")
            ax.text(5.9, 1.8, "NAND", fontsize=17, color=PURPLE, va="center")
            ax.text(9.7, 2.9, "AND", fontsize=17, color=INK, va="center")
            for cx, label, sub, color in [(1.4, "입력층", "특징을 받아 넘김", INK), (5.2, "은닉층", "새 값 h1, h2", PURPLE),
                                          (9.0, "출력층", "마지막 답 y", INK)]:
                ax.text(cx, 0.75, label, ha="center", va="center", fontsize=19, weight="bold", color=color)
                ax.text(cx, 0.25, sub, ha="center", va="center", fontsize=16, color=INK)
            return image(fig)
        ax = gate_axes(fig, [0.05, 0.13, 0.42, 0.72])
        if stage == 1:
            gate_points(ax, XOR)
        elif stage == 2:
            gate_line(ax, 1, 1, -0.5)
            gate_points(ax, XOR, wrong=wrong2)
        elif stage == 3:
            gate_line(ax, -1, 1, -0.5)
            gate_points(ax, XOR, wrong=wrong3, left=(1,))
        else:
            xs = np.linspace(-0.45, 1.6, 50)
            ax.fill_between(xs, np.clip(0.5 - xs, -0.45, 1.6), np.clip(1.5 - xs, -0.45, 1.6), color=PURPLE_L, zorder=1)
            gate_line(ax, 1, 1, -0.5, shade=False)
            gate_line(ax, 1, 1, -1.5, shade=False)
            ax.text(-0.42, 0.7, "h1", color=PURPLE, fontsize=17, weight="bold")
            ax.text(0.22, 1.42, "h2", color=PURPLE, fontsize=17, weight="bold")
            gate_points(ax, XOR)
        if stage >= 5:
            bx = gate_axes(fig, [0.55, 0.13, 0.42, 0.72], "h1", "h2", PURPLE)
            if stage == 6:
                gate_line(bx, 1, 1, -1.5)
                bx.text(1.55, 1.52, "h1 + h2 = 1.5", color=ORANGE, fontsize=15, ha="right", va="center", weight="bold")
            for (a, c), o in zip(hpts, XOR):
                if o:
                    bx.scatter([a], [c], s=300, color=BLUE, zorder=6)
                else:
                    bx.scatter([a], [c], s=260, facecolor="white", edgecolor="#9ca3af", lw=2.6, zorder=6)
            bx.text(1.08, 1.12, "(0, 1), (1, 0)", fontsize=15, color=BLUE, zorder=8)
            bx.text(-0.09, 1.12, "(0, 0)", fontsize=15, color=MUTED, zorder=8, ha="right")
            bx.text(0.92, 0.12, "(1, 1)", fontsize=15, color=MUTED, zorder=8, ha="right")
        else:
            notes = {1: ["XOR: 두 입력이 다를 때만 1", "출력 1 은 대각선 양 끝"],
                     2: ["위쪽을 1 로 판정하면", "(1, 1) 이 잘못 나뉨"],
                     3: ["직선을 돌려도", "(1, 0) 이 잘못 나뉨"],
                     4: ["h1(OR): x1 + x2 = 0.5 위쪽", "h2(NAND): x1 + x2 = 1.5 아래쪽", "두 직선 사이만 h1 = h2 = 1"]}[stage]
            yy = 0.78
            for k, text in enumerate(notes):
                fig.text(0.55, yy, text, fontsize=19, color=(PURPLE if stage == 4 else INK), va="center")
                yy -= 0.11
        return image(fig)

    frames = [draw(1, "XOR 의 네 점"), draw(2, "직선 하나로 나누면"), draw(3, "직선을 바꿔 그어도"), draw(4, "은닉층의 두 직선"),
              draw(5, "(h1, h2) 로 옮긴 네 점"), draw(6, "출력층은 직선 하나로 나눔"), draw(7, "입력층 → 은닉층 → 출력층")]
    return frames, [2000, 2000, 2000, 2500, 2500, 2400, 2500]


@figure("4d-5", 560, 280)
def summary_4d():
    """외울 것 그림. 포함 관계, 학습 방식, 퍼셉트론, XOR 신경망."""
    plt, fig = new(560)
    ax = boxes_axes(fig, ymax=5.6)
    card(ax, 0.15, 2.95, 5.35, 2.5, "인공지능 ⊃ 머신러닝 ⊃ 딥러닝",
         [("직선 모델 예: 사람이 고른 특징", GREEN), ("딥러닝: 특징까지 신경망의 층이 배움", PURPLE)], size=17)
    card(ax, 0.15, 0.15, 5.35, 2.6, "학습 방식",
         ["지도: 입력과 정답의 쌍", "비지도: 정답 없는 데이터", "자기지도: 데이터에서 만든 정답", "강화: 행동마다 받는 보상"], size=16,
         gap=0.47)
    card(ax, 5.7, 2.95, 5.35, 2.5, "퍼셉트론",
         ["z = w1 × x1 + w2 × x2 + b, z > 0 이면 1", ("w1 = w2 = 1: b = " + M + "1.5 AND, " + M + "0.5 OR", BLUE)], size=16)
    card(ax, 5.7, 0.15, 5.35, 2.6, "XOR 와 은닉층",
         ["직선 하나로는 0, 1, 1, 0 을 못 나눔", ("은닉층 h1 = OR, h2 = NAND", PURPLE), "출력층 AND(h1, h2) = XOR"], size=16)
    assert perceptron_out(1, 1, -1.5) == [0, 0, 0, 1] and perceptron_out(1, 1, -0.5) == [0, 1, 1, 1]
    return image(fig)


# 4e 활성화 함수와 기울기 소실

def sig(v):
    return 1.0 / (1.0 + np.exp(-v))


def dsig(v):
    return sig(v) * (1 - sig(v))


def relu(v):
    return np.maximum(0.0, v)


@figure("4e-1", 560, 300)
def no_activation():
    """활성화 함수 없이 이은 두 층은 직선, ReLU 를 넣으면 꺾인 선."""
    xs = np.linspace(-2, 2.2, 400)
    y1 = 2 * xs + 1
    y2 = -y1 + 3
    bent = -relu(2 * xs + 1) + 3
    tri = relu(xs + 1) - 2 * relu(xs) + relu(xs - 1)
    assert np.allclose(y2, -2 * xs + 2)
    pts2 = [(0, 2), (1, 0), (2, -2)]
    assert all(abs((-2 * a + 2) - b) < 1e-12 for a, b in pts2)
    ptsb = [(-1, 3.0), (1, 0.0)]
    assert all(abs((-relu(2 * a + 1) + 3) - b) < 1e-12 for a, b in ptsb)
    ptst = [(-1, 0.0), (0, 1.0), (1, 0.0)]
    assert all(abs((relu(a + 1) - 2 * relu(a) + relu(a - 1)) - b) < 1e-12 for a, b in ptst)

    def panel(fig, rect, curve, ghost=None, pts=(), label=None, title=None):
        ax = fig.add_axes(rect)
        tidy(ax)
        ax.set_xlim(-2, 2.2)
        ax.set_ylim(-3.5, 5.5)
        ax.axhline(0, color=FAINT, lw=1.2)
        ax.axvline(0, color=FAINT, lw=1.2)
        ax.set_xlabel("x")
        if ghost is not None:
            ax.plot(xs, ghost, color=PALE, lw=3, zorder=2)
        ax.plot(xs, curve, color=BLUE, lw=3.4, zorder=3)
        for a, b in pts:
            ax.scatter([a], [b], s=90, color=INK, zorder=5)
            # x < 0 인 점은 오른쪽 위로 지나는 선을 피해 이름을 왼쪽 위에 씀
            ax.text(a + (0.08 if a >= 0 else -0.08), b + 0.35, "(%s, %s)" % (num(a, 0), num(b, 0)), fontsize=15, color=INK,
                    zorder=6, ha="left" if a >= 0 else "right", bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))
        if label:
            ax.text(-1.0, 4.9, label, fontsize=17, color=BLUE, va="center", weight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
        if title:
            ax.set_title(title, fontsize=18, loc="left")
        return ax

    def draw(stage, title):
        plt, fig = new(600)
        head(fig, title, size=20)
        if stage == 5:
            panel(fig, [0.07, 0.14, 0.40, 0.68], y2, label="y2 = " + M + "2x + 2", title="활성화 함수 없음")
            panel(fig, [0.57, 0.14, 0.40, 0.68], bent, label="y2 = " + M + "ReLU(2x + 1) + 3", title="ReLU 를 넣음")
            return image(fig)
        rect = [0.08, 0.14, 0.55, 0.74]
        if stage == 1:
            panel(fig, rect, y1, label="y1 = 2x + 1")
            notes = ["첫 층의 출력 y1"]
        elif stage == 2:
            panel(fig, rect, y2, ghost=y1, pts=pts2, label="y2 = " + M + "2x + 2")
            notes = ["y2 = " + M + "y1 + 3", "= " + M + "(2x + 1) + 3", "= " + M + "2x + 2", "직선"]
        elif stage == 3:
            panel(fig, rect, bent, ghost=y2, pts=ptsb, label="y2 = " + M + "ReLU(2x + 1) + 3")
            notes = ["ReLU(x) = max(0, x)", "x < " + M + "0.5: 2x + 1 이 음수", "→ ReLU 가 0, y2 = 3", "x = " + M + "0.5 에서 꺾임"]
        else:
            panel(fig, rect, tri, pts=ptst, label="ReLU 셋을 더한 모양")
            notes = ["ReLU(x + 1)", M + " 2 × ReLU(x)", "+ ReLU(x " + M + " 1)", "x = " + M + "1, 0, 1 에서 꺾임"]
        yy = 0.80
        for text in notes:
            fig.text(0.67, yy, text, fontsize=18, color=INK, va="center")
            yy -= 0.10
        return image(fig)

    frames = [draw(1, "첫 층 y1 = 2x + 1"), draw(2, "활성화 함수 없이 둘째 층을 이으면"), draw(3, "두 층 사이에 ReLU 를 두면"),
              draw(4, "꺾이는 자리를 여럿 두면"), draw(5, "직선과 꺾인 선")]
    return frames, [1800, 2400, 2400, 2400, 2500]


@figure("4e-2", 560, 300)
def four_activations():
    """시그모이드, tanh, ReLU, Leaky ReLU(a = 0.1)와 x = −3, 0, 2 의 값."""
    xs = np.linspace(-4, 4, 400)
    leaky = lambda v: np.where(v >= 0, v, 0.1 * v)
    funcs = [("시그모이드", sig, (0, 1), (-0.15, 1.15), ["0.0474", "0.5", "0.8808"]),
             ("tanh", np.tanh, (-1, 1), (-1.25, 1.25), [M + "0.9951", "0", "0.964"]),
             ("ReLU", relu, (0,), (-1.0, 4.2), ["0", "0", "2"]),
             ("Leaky ReLU (a = 0.1)", leaky, (), (-1.0, 4.2), [M + "0.3", "0", "2"])]
    for name, fn, _, _, labels in funcs:
        got = [num(float(fn(np.array(v))), 4) for v in (-3.0, 0.0, 2.0)]
        assert got == labels, (name, got)
    # 값 글자를 곡선에 닿지 않는 쪽에 둠. 적지 않은 점은 오른쪽 위
    spots = {("시그모이드", -3.0): "above", ("시그모이드", 0.0): "left", ("시그모이드", 2.0): "below", ("tanh", 0.0): "left",
             ("ReLU", 0.0): "left", ("ReLU", 2.0): "left", ("Leaky ReLU (a = 0.1)", 0.0): "left",
             ("Leaky ReLU (a = 0.1)", 2.0): "left"}
    plt, fig = new(600)
    rects = [[0.07, 0.58, 0.40, 0.33], [0.57, 0.58, 0.40, 0.33], [0.07, 0.09, 0.40, 0.33], [0.57, 0.09, 0.40, 0.33]]
    for rect, (name, fn, bounds, ylim, labels) in zip(rects, funcs):
        ax = fig.add_axes(rect)
        tidy(ax)
        ax.set_xlim(-4, 4)
        ax.set_ylim(*ylim)
        for bnd in bounds:
            ax.axhline(bnd, color=MUTED, lw=1.6, ls="--")
        ax.plot(xs, fn(xs), color=BLUE, lw=3.2, zorder=3)
        for v, lab in zip((-3.0, 0.0, 2.0), labels):
            yv = float(fn(np.array(v)))
            ax.scatter([v], [yv], s=70, color=INK, zorder=5)
            dy = (ylim[1] - ylim[0]) * 0.1
            spot = spots.get((name, v), "right")
            tx, ty, ha, va = {"right": (v + 0.15, yv + dy, "left", "baseline"), "left": (v - 0.15, yv + dy, "right", "baseline"),
                              "above": (v, yv + dy, "center", "baseline"), "below": (v + 0.15, yv - dy * 0.5, "left", "top")}[spot]
            ax.text(tx, ty, lab, fontsize=15, color=INK, zorder=6, ha=ha, va=va,
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
        ax.set_title(name, fontsize=18, loc="left", pad=4)
        # 눈금 글자를 키워도 눈금이 줄지 않게 정해 둠
        ax.set_xticks(range(-4, 5))
        ax.set_yticks({"시그모이드": [0, 0.5, 1], "tanh": [-1, -0.5, 0, 0.5, 1]}.get(name, [0, 2, 4]))
        ax.tick_params(labelsize=15)
    return image(fig)


@figure("4e-3", 560, 300)
def derivatives():
    """활성화 함수의 미분값과 층을 지나며 곱한 값."""
    xs = np.linspace(-6, 6, 600)
    assert num(dsig(0.0), 4) == "0.25" and num(dsig(5.0), 4) == "0.0066"
    dt = lambda v: 1 - np.tanh(v) ** 2
    assert num(dt(0.0), 4) == "1" and num(dt(2.0), 4) == "0.0707"
    prods = [0.25 ** n for n in (1, 2, 3)]
    assert prods == [0.25, 0.0625, 0.015625]

    def base(title):
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = fig.add_axes([0.08, 0.14, 0.56, 0.72])
        tidy(ax)
        ax.set_xlim(-6, 6)
        ax.set_xlabel("x")
        ax.axhline(0, color=FAINT, lw=1.2)
        return plt, fig, ax

    def notes(fig, lines):
        yy = 0.80
        for text, color in lines:
            fig.text(0.68, yy, text, fontsize=18, color=color, va="center")
            yy -= 0.10

    frames = []
    for stage in (1, 2):
        plt, fig, ax = base("시그모이드와 미분값" if stage == 1 else "양 끝은 미분값이 0 에 가까움")
        ax.set_ylim(-0.08, 1.08)
        if stage == 2:
            ax.axvspan(-6, -4, color=BAND, zorder=0)
            ax.axvspan(4, 6, color=BAND, zorder=0)
        ax.plot(xs, sig(xs), color=BLUE, lw=3.2)
        ax.plot(xs, dsig(xs), color=ORANGE, lw=3.2)
        ax.scatter([0], [0.25], s=90, color=ORANGE, zorder=5)
        ax.text(0.3, 0.31, "0.25", fontsize=17, color=ORANGE, weight="bold")
        lines = [("σ(x)", BLUE), ("σ'(x) = σ(x)(1 " + M + " σ(x))", ORANGE), ("x = 0 에서 가장 큰 0.25", ORANGE)]
        if stage == 2:
            ax.scatter([5], [float(dsig(5.0))], s=90, color=ORANGE, zorder=5)
            ax.text(4.1, 0.12, "0.0066", fontsize=17, color=ORANGE, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))
            lines = [("x = 5: σ'(5) = 0.0066", ORANGE), ("회색 띠: 출력이 0 이나 1 에", INK), ("가까운 포화 구간", INK)]
        notes(fig, lines)
        frames.append(image(fig))
    plt, fig, ax = base("tanh 와 미분값")
    ax.set_ylim(-1.15, 1.15)
    ax.plot(xs, np.tanh(xs), color=BLUE, lw=3.2)
    ax.plot(xs, dt(xs), color=ORANGE, lw=3.2)
    ax.scatter([0, 2], [1, float(dt(2.0))], s=90, color=ORANGE, zorder=5)
    ax.text(0.3, 1.02, "1", fontsize=17, color=ORANGE, weight="bold")
    ax.text(2.2, 0.15, "0.0707", fontsize=17, color=ORANGE, weight="bold")
    notes(fig, [("tanh(x)", BLUE), ("tanh'(x) = 1 " + M + " tanh(x)²", ORANGE), ("x = 0 에서 1", ORANGE)])
    frames.append(image(fig))
    plt, fig, ax = base("ReLU 와 미분값")
    ax.set_ylim(-0.4, 4.2)
    ax.plot(xs, relu(xs), color=BLUE, lw=3.2)
    ax.plot(xs[xs < 0], np.zeros((xs < 0).sum()), color=ORANGE, lw=3.6)
    ax.plot(xs[xs > 0], np.ones((xs > 0).sum()), color=ORANGE, lw=3.6)
    notes(fig, [("ReLU(x) = max(0, x)", BLUE), ("미분값: x < 0 이면 0", ORANGE), ("x > 0 이면 1", ORANGE)])
    frames.append(image(fig))
    plt, fig = new(600)
    head(fig, "활성화 함수의 미분값만 곱한 값", size=20)
    ax = fig.add_axes([0.08, 0.14, 0.56, 0.72])
    tidy(ax)
    pos = np.arange(3)
    ax.bar(pos - 0.2, prods, width=0.36, color=ORANGE)
    ax.bar(pos + 0.2, [1, 1, 1], width=0.36, color="white", edgecolor=ORANGE, lw=2.6, hatch="//")
    for p, v in zip(pos, prods):
        # 긴 숫자는 막대 오른쪽 끝에 맞춰 옆 빗금 막대에 닿지 않게 함
        long = len(num(v, 6)) > 6
        ax.text(p - 0.02 if long else p - 0.2, v + 0.03, num(v, 6), ha="right" if long else "center", fontsize=15, color=INK)
        ax.text(p + 0.2, 1.03, "1", ha="center", fontsize=15, color=INK)
    ax.set_xticks(pos)
    ax.set_xticklabels(["한 번", "두 번", "세 번"])
    ax.set_ylim(0, 1.18)
    notes(fig, [("채운 막대: 시그모이드", ORANGE), ("빗금 막대: ReLU(양수 입력)", ORANGE), ("0.25 × 0.25 × 0.25", INK),
                ("= 0.015625", INK)])
    frames.append(image(fig))
    return frames, [2200, 2400, 2200, 2200, 2500]


@figure("4e-4", 560, 280)
def summary_4e():
    """외울 것 그림. 활성화 함수가 하는 일, 네 함수의 범위와 값, 미분값과 기울기 소실."""
    plt, fig = new(560)
    ax = boxes_axes(fig, ymax=5.6)
    card(ax, 0.15, 3.95, 10.9, 1.5, "활성화 함수가 없으면 층을 쌓아도 직선",
         [(M + "(2x + 1) + 3 = " + M + "2x + 2,  ReLU 를 넣으면 x = " + M + "0.5 에서 꺾인 선", BLUE)], size=17)
    card(ax, 0.15, 0.15, 6.2, 3.6, "출력 범위와 값",
         [("시그모이드 0~1, σ(0) = 0.5", BLUE), ("tanh " + M + "1~1, tanh(0) = 0", BLUE), ("ReLU 0 이상, ReLU(2) = 2", BLUE),
          ("Leaky ReLU(a = 0.1)는 " + M + "3 에 " + M + "0.3", BLUE)], size=17, gap=0.62)
    card(ax, 6.55, 0.15, 4.5, 3.6, "미분값과 기울기 소실",
         [("σ'(0) = 0.25 가 최대", ORANGE), ("tanh'(0) = 1", ORANGE), ("ReLU: 음수 0, 양수 1", ORANGE),
          "시그모이드 세 번: 0.015625 이하"], size=17, gap=0.62)
    assert num(0.25 ** 3, 6) == "0.015625"
    return image(fig)


# 4f 국소 최적해와 모멘텀

def fq(v):
    return v * (v + 1) * (v + 2) * (v - 2)


def dfq(v):
    return 4 * v ** 3 + 3 * v ** 2 - 8 * v - 4


def quartic_path(start, mu=0.0, n=1000, lr=0.01):
    xv, vel, out = start, None, [start]
    for _ in range(n):
        g = dfq(xv)
        vel = g if vel is None else mu * vel + g
        xv -= lr * vel
        out.append(xv)
    return out


ROOTS = sorted(float(r) for r in np.roots([4, 3, -8, -4]).real)
assert [num(r, 2) for r in ROOTS] == [M + "1.61", M + "0.47", "1.33"]


def quartic_axes(fig, rect=(0.09, 0.14, 0.56, 0.74)):
    ax = fig.add_axes(list(rect))
    tidy(ax)
    xs = np.linspace(-2.8, 2.2, 400)
    ax.plot(xs, fq(xs), color=RED, lw=3)
    ax.set_xlim(-2.8, 2.2)
    ax.set_ylim(-8.5, 12)
    ax.set_xlabel("x")
    ax.set_ylabel("f(x)")
    return ax


def ball(ax, xv, color, label=None, dy=1.2, hollow=False, ha="center"):
    """ha 가 left 면 곡선을 피해 글자를 공 오른쪽에서 시작함."""
    if hollow:
        ax.scatter([xv], [fq(xv)], s=200, facecolor="white", edgecolor=color, lw=3, zorder=7)
    else:
        ax.scatter([xv], [fq(xv)], s=200, color=color, zorder=7)
    if label:
        ax.text(xv + (0.18 if ha == "left" else 0), fq(xv) + dy, label, ha=ha, fontsize=16, color=color, weight="bold",
                zorder=8, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))


@figure("4f-1", 560, 300)
def local_minimum():
    """f(x) = x(x+1)(x+2)(x−2) 에서 출발점에 따라 다른 곳에 멈추는 경사하강법(학습률 0.01)."""
    pa, pb = quartic_path(-2.5), quartic_path(0.5)
    assert [num(pa[k], 2) for k in (10, 20, 1000)] == [M + "1.7", M + "1.63", M + "1.61"]
    assert [num(pb[k], 2) for k in (10, 20, 1000)] == ["1.1", "1.3", "1.33"]
    assert num(fq(ROOTS[0]), 2) == M + "1.38" and num(fq(ROOTS[2]), 2) == M + "6.91" and num(fq(ROOTS[1]), 2) == "0.94"

    def draw(k, title, final=False):
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = quartic_axes(fig)
        if k is None:
            for r in (ROOTS[0], ROOTS[2]):
                ax.axvline(r, color=MUTED, lw=1.4, ls=":")
            ax.text(ROOTS[0] + 0.07, fq(ROOTS[0]) - 1.6, num(ROOTS[0], 2), ha="left", fontsize=16, color=INK)
            ax.text(ROOTS[2] + 0.07, fq(ROOTS[2]) - 1.2, num(ROOTS[2], 2), ha="left", fontsize=16, color=INK)
            lines = [("f(x) = x(x + 1)(x + 2)(x " + M + " 2)", RED), ("x ≈ " + M + "1.61 에서 " + M + "1.38", INK),
                     ("x ≈ 1.33 에서 " + M + "6.91", INK), ("x ≈ " + M + "0.47 에서 0.94", INK)]
        else:
            if final:
                ax.plot(pa[:k + 1], [fq(v) for v in pa[:k + 1]], color=SKY, lw=2.4, zorder=5)
                ax.plot(pb[:k + 1], [fq(v) for v in pb[:k + 1]], color=SKY, lw=2.4, zorder=5)
            ball(ax, pa[k], BLUE, fmt2(pa[k]), dy=1.4, ha="left" if k == 0 else "center")
            ball(ax, pb[k], BLUE, fmt2(pb[k]), dy=1.6)
            lines = [("학습률 0.01", INK), ("갱신 %s번 뒤" % format(k, ","), INK),
                     ("출발 " + M + "2.5 → " + fmt2(pa[k]), BLUE), ("출발 0.5 → " + fmt2(pb[k]), BLUE)]
            if k == 0:
                lines = [("학습률 0.01", INK), ("출발점 " + M + "2.5 와 0.5", BLUE)]
            if final:
                ax.text(ROOTS[0], fq(ROOTS[0]) - 2.6, "국소 최적해", ha="center", fontsize=17, color=INK, weight="bold")
                ax.text(ROOTS[2] - 0.35, fq(ROOTS[2]) - 0.3, "전역 최적해", ha="right", fontsize=17, color=INK, weight="bold",
                        va="center")
                lines = [("1.33: f 가 가장 낮은 곳", INK), ("전역 최적해", INK), (M + "1.61: 둘레에서만 낮은 곳", INK),
                         ("국소 최적해", INK)]
        yy = 0.80
        for text, color in lines:
            fig.text(0.69, yy, text, fontsize=18, color=color, va="center")
            yy -= 0.10
        return image(fig)

    frames = [draw(None, "둘레보다 낮은 곳이 두 군데"), draw(0, "두 곳에서 출발"), draw(10, "10번 갱신한 뒤"),
              draw(20, "20번 갱신한 뒤"), draw(1000, "1,000번 갱신한 뒤"), draw(1000, "멈춘 곳의 이름", final=True)]
    return frames, [2000, 1800, 2000, 2000, 2400, 2500]


@figure("4f-2", 560, 300)
def momentum_paths():
    """모멘텀(μ = 0.9)과 모멘텀 없는 경사하강법. −2.5 와 2.5 에서 출발."""
    s1, m1 = quartic_path(-2.5), quartic_path(-2.5, mu=0.9)
    s2, m2 = quartic_path(2.5), quartic_path(2.5, mu=0.9)
    assert [num(s1[k], 2) for k in (5, 10, 1000)] == [M + "1.84", M + "1.7", M + "1.61"]
    assert [num(m1[k], 2) for k in (5, 10, 15, 1000)] == [M + "0.81", "0.18", "1.64", "1.33"]
    assert num(s2[1000], 2) == "1.33" and num(m2[1000], 2) == M + "1.61"
    assert next(k for k, v in enumerate(m1) if v > ROOTS[1]) <= 10

    def draw(sp, mp, k, title, lines, mdy=-2.6, mha="center"):
        """mdy, mha 는 보라 글자가 곡선·축에 닿지 않게 놓는 자리. 파랑 글자는 곡선이 가파른 왼쪽에서 오른쪽으로 비킴."""
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = quartic_axes(fig)
        ball(ax, sp[k], BLUE, fmt2(sp[k]), dy=1.5, ha="left" if sp[k] < -1.75 else "center")
        ball(ax, mp[k], PURPLE, fmt2(mp[k]), dy=mdy, ha=mha)
        yy = 0.80
        for text, color in lines:
            fig.text(0.69, yy, text, fontsize=18, color=color, va="center")
            yy -= 0.10
        return image(fig, symbols=True)

    frames = [draw(s1, m1, 0, "x = " + M + "2.5 에서 함께 출발", [("파랑: 모멘텀 없음", BLUE), ("보라: μ = 0.9", PURPLE), ("학습률 0.01", INK)],
                   mdy=-0.4, mha="left"),
              draw(s1, m1, 5, "5번 갱신한 뒤", [("파랑 " + M + "1.84", BLUE), ("보라 " + M + "0.81", PURPLE), ("보라는 같은 쪽", INK),
                                            ("기울기가 쌓임", INK)]),
              draw(s1, m1, 10, "10번 갱신한 뒤", [("파랑 " + M + "1.70", BLUE), ("보라 0.18", PURPLE), ("보라가 x ≈ " + M + "0.47 의", INK),
                                              ("높은 곳을 넘음", INK)]),
              draw(s1, m1, 15, "15번 갱신한 뒤", [("보라 1.64", PURPLE), ("1.33 을 지나침", INK)], mdy=-1.9, mha="left"),
              draw(s1, m1, 1000, "1,000번 갱신한 뒤", [("파랑 " + M + "1.61 에서 멈춤", BLUE), ("보라 1.33 에서 멈춤", PURPLE)], mdy=1.5),
              draw(s2, m2, 1000, "x = 2.5 에서 출발하면", [("파랑 1.33 에서 멈춤", BLUE), ("보라는 1.33 을 지나쳐", PURPLE),
                                                       (M + "1.61 에서 멈춤", PURPLE)])]
    return frames, [1800, 2400, 2400, 2200, 2400, 2500]


def train_loss(mu, n=500, lr=0.001):
    w, b, vw, vb, hist = 1.0, 1.0, None, None, []
    for _ in range(n):
        hist.append(float(L(w, b)))
        gw, gb = grads(w, b)
        vw = gw if vw is None else mu * vw + gw
        vb = gb if vb is None else mu * vb + gb
        w, b = w - lr * vw, b - lr * vb
    return np.array(hist)


@figure("4f-3", 560, 280)
def momentum_curves():
    """다섯 사람 예의 학습 곡선. 모멘텀 없는 SGD 와 momentum=0.9. 10번마다 기록한 값(노트북 01 의 39·55번 셀과 같음)."""
    hs, hm = train_loss(0.0), train_loss(0.9)
    assert [num(hs[k], 4) for k in (10, 20, 490)] == ["10.3855", "8.5173", "4.6796"]
    assert [num(hm[k], 4) for k in (10, 20, 490)] == ["5.7585", "5.9541", "4.539"]
    ep = np.arange(0, 500, 10)
    plt, fig = new(560)
    ax = fig.add_axes([0.08, 0.15, 0.60, 0.76])
    tidy(ax)
    ax.plot(ep, hs[ep], color=BLUE, lw=3, marker="o", ms=4)
    ax.plot(ep, hm[ep], color=PURPLE, lw=3, marker="o", ms=4)
    ax.axhline(4.539, color=MUTED, lw=1.6, ls="--")
    ax.set_xlim(-5, 500)
    ax.set_ylim(4, 14)
    ax.set_xlabel("반복")
    ax.set_ylabel("손실")
    arrow = dict(arrowstyle="-", color=MUTED, lw=1.2, relpos=(0, 0.5))
    ax.annotate("10번째 10.3855", (10, 10.3855), xytext=(110, 11.2), fontsize=15, color=BLUE, arrowprops=arrow, va="center")
    ax.annotate("20번째 5.9541", (20, 5.9541), xytext=(110, 9.2), fontsize=15, color=PURPLE, arrowprops=arrow, va="center")
    ax.annotate("10번째 5.7585", (10, 5.7585), xytext=(110, 8.0), fontsize=15, color=PURPLE, arrowprops=arrow, va="center")
    lines = [("파랑: 모멘텀 없는 SGD", BLUE), ("보라: momentum=0.9", PURPLE), ("490번째", INK), ("4.6796 과 4.5390", INK),
             ("회색 점선: 가장 낮은 값 4.539", MUTED)]
    yy = 0.82
    for text, color in lines:
        fig.text(0.71, yy, text, fontsize=17, color=color, va="center")
        yy -= 0.11
    return image(fig)


@figure("4f-4", 560, 280)
def summary_4f():
    """외울 것 그림. 국소 최적해, 모멘텀 식과 다섯 사람 예, 코드."""
    w2s = 1.0 - 0.001 * (-19.04) - 0.001 * (0.9 * (-19.04) + grads(1.01904, 0.998)[0])
    assert num(w2s, 6) == "1.054774"
    plt, fig = new(560)
    ax = fig.add_axes([0.05, 0.13, 0.40, 0.74])
    tidy(ax)
    xs = np.linspace(-2.8, 2.2, 300)
    ax.plot(xs, fq(xs), color=RED, lw=3)
    ax.set_xlim(-2.8, 2.2)
    ax.set_ylim(-9.9, 12)
    ball(ax, ROOTS[0], BLUE, "국소 " + M + "1.61", dy=-2.6)
    ball(ax, ROOTS[2], BLUE, "전역 1.33", dy=-2.4)
    ax.set_title("출발 " + M + "2.5 → " + M + "1.61, 0.5 → 1.33", fontsize=16, loc="left")
    bx = boxes_axes(fig, (0.47, 0, 0.53, 1), xmax=5.9, ymax=5.6)
    card(bx, 0.1, 2.75, 5.7, 2.7, "모멘텀(PyTorch)",
         [("v = μ × v + 기울기", PURPLE), ("새 W = W " + M + " 학습률 × v", PURPLE), "첫 갱신은 v = 기울기",
          "W: 1 → 1.01904 → 1.054774"], size=16, gap=0.48)
    card(bx, 0.1, 0.15, 5.7, 2.4, "코드",
         [("optim.SGD([W, B], lr=0.001,", INK), ("          momentum=0.9)", INK), "같은 쪽 갱신은 커지고 흔들림은 줄어듦"], size=16)
    return image(fig, symbols=True)


# 4g 모델 용량과 데이터 나누기

VAL_X = np.array([170.0, 175.0, 177.0])
VAL_Y = np.array([61.0, 70.0, 79.5])
C4 = np.polyfit(X, Y, 4)


def model_preds(kind, xs):
    Xs = xs - x.mean()
    if kind == "평균":
        return np.full_like(xs, y.mean(), dtype=float)
    if kind == "직선":
        return W_END * Xs + B_END + y.mean()
    return np.polyval(C4, Xs) + y.mean()


def mse_of(kind, xs, ys):
    return float(((model_preds(kind, xs) - ys) ** 2).mean())


MODELS = [("평균", "늘 같은 값", 1), ("직선", "직선", 2), ("곡선", "네제곱 곡선", 5)]


def mse_text(v):
    """표에 찍는 MSE. 0 은 0, 나머지는 소수 둘째 자리까지."""
    return "0" if abs(v) < 1e-9 else fmt2(v)


@figure("4g-1", 560, 300)
def capacity():
    """파라미터 1, 2, 5개 모델을 다섯 사람(학습)과 지어낸 세 사람(새 데이터)에 맞춤."""
    tr = [mse_of(k, x, y) for k, _, _ in MODELS]
    va = [mse_of(k, VAL_X, VAL_Y) for k, _, _ in MODELS]
    assert [num(v, 2) for v in tr] == ["42.99", "4.67", "0"] and [num(v, 2) for v in va] == ["79.78", "8.62", "81.5"]
    assert num(float(model_preds("곡선", np.array([177.0]))[0]), 1) == "65.9"
    xs = np.linspace(163.5, 178.6, 400)

    def draw(stage, title):
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = fig.add_axes([0.08, 0.14, 0.52, 0.74])
        tidy(ax)
        ax.set_xlim(163.5, 178.6)
        ax.set_ylim(54, 84)
        ax.set_xlabel("신장 (cm)")
        ax.set_ylabel("체중 (kg)")
        if 2 <= stage <= 4:
            kind = MODELS[stage - 2][0]
            ax.plot(xs, model_preds(kind, xs), color=GREEN, lw=3.2, zorder=3)
            if kind == "곡선":
                ax.scatter([177], [float(model_preds("곡선", np.array([177.0]))[0])], s=150, facecolor="white", edgecolor=GREEN,
                           lw=3, zorder=6)
                ax.text(176.6, 63.0, "65.9", fontsize=16, color=GREEN, ha="right", weight="bold",
                        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"))
        ax.scatter(x, y, s=90, color=BLUE, zorder=5)
        ax.scatter(VAL_X, VAL_Y, s=110, color=ORANGE, zorder=5)
        fig.text(0.64, 0.83, "모델", fontsize=17, color=MUTED, weight="bold")
        fig.text(0.81, 0.83, "다섯 사람", fontsize=17, color=BLUE, weight="bold", ha="center")
        fig.text(0.94, 0.83, "새 세 사람", fontsize=17, color=ORANGE, weight="bold", ha="center")
        shown_rows = {1: 0, 2: 1, 3: 2, 4: 3, 5: 3}[stage]
        for r in range(3):
            yy = 0.72 - r * 0.12
            name = "%s (%d)" % (MODELS[r][1], MODELS[r][2])
            fig.text(0.64, yy, name, fontsize=16, color=INK, va="center")
            if r < shown_rows:
                fig.text(0.81, yy, mse_text(tr[r]), fontsize=17, color=INK, va="center", ha="center")
                if stage == 5:
                    fig.text(0.94, yy, mse_text(va[r]), fontsize=17, color=INK, va="center", ha="center")
        fig.text(0.64, 0.30, "괄호는 파라미터 수, 값은 MSE", fontsize=15, color=MUTED, va="center")
        if stage == 5:
            fig.text(0.64, 0.20, "곡선: 다섯 사람 0, 새 세 사람 81.50", fontsize=16, color=INK, va="center")
        return image(fig)

    frames = [draw(1, "다섯 사람과 학습에 쓰지 않은 세 사람"), draw(2, "늘 65.4 kg 을 내는 모델"), draw(3, "500번 학습한 직선"),
              draw(4, "다섯 점을 모두 지나는 네제곱 곡선"), draw(5, "두 MSE 를 함께 보기")]
    return frames, [2000, 2200, 2200, 2400, 2500]


@figure("4g-2", 560, 280)
def two_errors():
    """세 모델의 학습 데이터 MSE(파랑)와 새 데이터 MSE(주황)."""
    tr = [mse_of(k, x, y) for k, _, _ in MODELS]
    va = [mse_of(k, VAL_X, VAL_Y) for k, _, _ in MODELS]
    plt, fig = new(560)
    ax = fig.add_axes([0.08, 0.24, 0.88, 0.66])
    tidy(ax)
    pos = np.arange(3)
    ax.bar(pos - 0.19, tr, width=0.36, color=BLUE)
    ax.bar(pos + 0.19, va, width=0.36, color=ORANGE)
    for p, a, b in zip(pos, tr, va):
        ax.text(p - 0.19, a + 1.5, mse_text(a), ha="center", fontsize=16, color=INK)
        ax.text(p + 0.19, b + 1.5, mse_text(b), ha="center", fontsize=16, color=INK)
    ax.set_ylim(0, 95)
    ax.set_ylabel("MSE")
    ax.set_xticks(pos)
    ax.set_xticklabels(["늘 같은 값 (파라미터 1)", "직선 (파라미터 2)", "네제곱 곡선 (파라미터 5)"])
    for p, text in zip(pos, ["과소적합, 높은 편향", "알맞은 모델", "과적합, 높은 분산"]):
        fig.text(0.08 + 0.88 * (p + 0.5) / 3, 0.06, text, ha="center", fontsize=17, color=INK, weight="bold")
    fig.text(0.70, 0.92, "파랑: 다섯 사람(학습)   주황: 새 세 사람", fontsize=16, color=INK, ha="center")
    return image(fig)


@figure("4g-3", 560, 280)
def three_sets():
    """데이터 5,000개를 60/20/20 으로 나누기와 데이터 누수."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    parts = [(3000, "학습 데이터", BLUE, "W, B 같은 파라미터 학습"), (1000, "검증 데이터", ORANGE, "하이퍼파라미터\n고르기"),
             (1000, "테스트 데이터", PURPLE, "마지막에\n한 번 평가")]
    assert sum(p[0] for p in parts) == 5000 and [p[0] for p in parts] == [5000 * 6 // 10, 5000 * 2 // 10, 5000 * 2 // 10]
    plt, fig = new(560)
    ax = boxes_axes(fig, ymax=5.6)
    x0 = 0.4
    scale = 10.4 / 5000
    centers = []
    for n, name, color, use in parts:
        w = n * scale
        ax.add_patch(FancyBboxPatch((x0, 2.6), w - 0.06, 1.2, boxstyle="round,pad=0.02", fc=color, ec="white", lw=1))
        ax.text(x0 + w / 2, 3.42, name, ha="center", va="center", fontsize=18, color="white", weight="bold")
        ax.text(x0 + w / 2, 2.95, format(n, ",") + "개", ha="center", va="center", fontsize=17, color="white")
        ax.text(x0 + w / 2, 2.05, use, ha="center", va="center", fontsize=16, color=INK, linespacing=1.3)
        centers.append(x0 + w / 2)
        x0 += w
    ax.text(0.4, 4.95, "데이터 5,000개를 60/20/20 으로 나누기", fontsize=20, weight="bold", color=INK)
    ax.add_patch(FancyArrowPatch((centers[2], 3.85), (centers[0], 3.85), connectionstyle="arc3,rad=0.25", arrowstyle="-|>",
                                 mutation_scale=20, color=RED, lw=2.6))
    ax.text((centers[0] + centers[2]) / 2, 4.55, "테스트 데이터를 학습에 쓰면 데이터 누수", ha="center", fontsize=17,
            color=RED, weight="bold", bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    ax.text(0.4, 1.05, "평균 같은 전처리 값도 학습 데이터에서만 구해 세 묶음에 씀", fontsize=17, color=INK)
    ax.text(0.4, 0.45, "강의 권장: 10만 개 이상 80/10/10, 1만 개 이하 60/20/20", fontsize=16, color=MUTED)
    return image(fig)


@figure("4g-4", 560, 300)
def kfold():
    """학습 데이터 400개로 하는 5-Fold 교차 검증. 검증 정확도 다섯의 평균 0.80."""
    from matplotlib.patches import FancyBboxPatch
    scores = [0.82, 0.78, 0.85, 0.80, 0.75]
    assert abs(sum(scores) / 5 - 0.80) < 1e-12 and 400 // 5 == 80 and 400 - 80 == 320

    def draw(stage, title):
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = boxes_axes(fig, (0, 0, 1, 0.9), ymax=5.4)
        w = 1.6
        for k in range(5):
            val = (k == stage - 2)
            color = ORANGE if val else BLUE
            ax.add_patch(FancyBboxPatch((0.3 + k * (w + 0.08), 3.4), w, 1.0, boxstyle="round,pad=0.02", fc=color, ec="white"))
            ax.text(0.3 + k * (w + 0.08) + w / 2, 3.9, "80개", ha="center", va="center", fontsize=17, color="white",
                    weight="bold")
        ax.add_patch(FancyBboxPatch((9.0, 3.4), 1.9, 1.0, boxstyle="round,pad=0.02", fc=PURPLE, ec="white"))
        ax.text(9.95, 3.9, "테스트 100개", ha="center", va="center", fontsize=16, color="white", weight="bold")
        ax.text(0.3, 4.85, "학습 데이터 400개를 다섯 덩어리로", fontsize=17, color=INK)
        if 2 <= stage <= 6:
            k = stage - 2
            ax.text(0.3 + k * (w + 0.08) + w / 2, 3.05, "검증", ha="center", fontsize=16, color=ORANGE, weight="bold")
            ax.text(0.3, 2.35, "%d번째 학습: 나머지 320개로 학습, 80개로 검증" % (k + 1), fontsize=19, color=INK)
        done = scores[:max(0, min(stage - 1, 5))]
        line = "   ".join("%d번째 %.2f" % (j + 1, s) for j, s in enumerate(done))
        if done:
            ax.text(0.3, 1.45, "검증 정확도: " + line, fontsize=17, color=INK)
        if stage == 7:
            ax.text(0.3, 0.6, "평균 (0.82 + 0.78 + 0.85 + 0.80 + 0.75) ÷ 5 = 0.80", fontsize=20, color=INK, weight="bold")
            ax.text(0.3, 2.35, "덩어리 다섯이 모두 한 번씩 검증에 쓰임", fontsize=19, color=INK)
        return image(fig)

    frames = [draw(1, "테스트 100개를 떼고 400개를 나눔")] + [draw(s, "%d번째 학습" % (s - 1)) for s in range(2, 7)] + \
        [draw(7, "다섯 번의 평균이 모델의 성능")]
    return frames, [2000, 2000, 1800, 1800, 1800, 2000, 2500]


@figure("4g-5", 560, 280)
def summary_4g():
    """외울 것 그림. 과소적합·과적합, 세 묶음, K-Fold."""
    plt, fig = new(560)
    ax = boxes_axes(fig, ymax=5.6)
    card(ax, 0.15, 3.0, 5.35, 2.45, "과소적합: 높은 편향", ["학습·새 데이터 오차 모두 큼", "늘 같은 값: 42.99, 79.78"], size=16)
    card(ax, 5.7, 3.0, 5.35, 2.45, "과적합: 높은 분산", ["학습 오차 작고 새 데이터 오차 큼", "네제곱 곡선: 0, 81.50"], size=16)
    card(ax, 0.15, 0.15, 5.35, 2.65, "세 묶음(60/20/20, 5,000개)",
         [("학습 3,000: 파라미터", BLUE), ("검증 1,000: 하이퍼파라미터", ORANGE), ("테스트 1,000: 마지막에 한 번", PURPLE)], size=16,
         gap=0.5)
    card(ax, 5.7, 0.15, 5.35, 2.65, "5-Fold(학습 데이터 400개)", ["한 번에 학습 320, 검증 80", "다섯 번 학습해 성능을 평균"], size=16)
    return image(fig)


# 4h 평가 지표

YP = W_END * X + B_END
E = YP - Y
CONF0 = (int(((YP > 0) & (Y > 0)).sum()), int(((YP > 0) & (Y <= 0)).sum()), int(((YP <= 0) & (Y > 0)).sum()),
         int(((YP <= 0) & (Y <= 0)).sum()))
assert CONF0 == (2, 1, 0, 2)


@figure("4h-1", 560, 280)
def regression_metrics():
    """500번 학습한 직선의 오차와 MAE, RMSE, R²."""
    mae, mse = float(np.abs(E).mean()), float((E ** 2).mean())
    rmse, r2 = mse ** 0.5, 1 - mse / float((Y ** 2).mean())
    assert [num(v, 2) for v in E] == [M + "2.04", M + "0.83", "3.67", M + "0.99", "2.03"]
    assert num(mae, 2) == "1.91" and num(mse, 2) == "4.67" and num(rmse, 2) == "2.16" and num(r2, 2) == "0.89"
    plt, fig = new(560)
    ax = fig.add_axes([0.07, 0.14, 0.40, 0.76])
    tidy(ax)
    ax.set_xlim(-6.5, 6.5)
    ax.set_ylim(-11, 13)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.yaxis.set_label_coords(-0.10, 0.5)
    ax.plot([-6.5, 6.5], [W_END * -6.5 + B_END, W_END * 6.5 + B_END], color=BLUE, lw=3)
    for i in range(5):
        ax.plot([X[i], X[i]], [Y[i], YP[i]], color=RED, lw=3.2, zorder=4)
        # 정답이 직선 위에 있으면 오른쪽 위로 지나는 직선을 피해 번호를 왼쪽에 씀
        up = Y[i] > YP[i]
        ax.text(X[i] + (-0.3 if up else 0.3), (Y[i] + YP[i]) / 2, str(i + 1), fontsize=15, color=MUTED, weight="bold",
                ha="right" if up else "left")
    ax.scatter(X, Y, s=80, color=INK, zorder=5)
    ax.scatter(X, YP, s=90, facecolor="white", edgecolor=BLUE, lw=2.4, zorder=6)
    cols = [0.56, 0.66, 0.78, 0.90]
    for c, h in zip(cols, ["사람", "e", "$|\\,e\\,|$", "$e^2$"]):
        fig.text(c, 0.88, h, fontsize=17, color=(RED if h != "사람" else MUTED), ha="center", weight="bold")
    for i in range(5):
        yy = 0.78 - i * 0.075
        vals = [str(i + 1), num(E[i], 2), num(abs(E[i]), 2), num(E[i] ** 2, 2)]
        for c, v in zip(cols, vals):
            fig.text(c, yy, v, fontsize=16, color=INK, ha="center", va="center")
    lines = ["MAE = $|\\,e\\,|$ 의 평균 = 1.91", "MSE = $e^2$ 의 평균 = 4.67", "RMSE = $\\sqrt{4.67}$ = 2.16"]
    yy = 0.32
    for text in lines:
        fig.text(0.53, yy, text, fontsize=16, color=INK, va="center")
        yy -= 0.075
    fig.text(0.53, yy, "$R^2$", fontsize=16, color=INK, va="center")
    fig.text(0.565, yy, "= 1 " + M + " 4.6741 ÷ 42.992 = 0.89", fontsize=16, color=INK, va="center")
    return image(fig, symbols=True)


def conf_grid(ax, x0, y0, cell, values, show=(True, True, True, True), hl=()):
    """혼동 행렬 2×2(행 실제, 열 판정, TP 왼쪽 위). values = (TP, FN, FP, TN)."""
    from matplotlib.patches import Rectangle
    names = ["TP", "FN", "FP", "TN"]
    colors = [GREEN, RED, RED, GREEN]
    fills = [GREEN_L, RED_L, RED_L, GREEN_L]
    for k in range(4):
        r, c = divmod(k, 2)
        cx, cy = x0 + c * cell, y0 + (1 - r) * cell
        ax.add_patch(Rectangle((cx, cy), cell, cell, fc=fills[k] if show[k] else "white", ec="#9ca3af", lw=1.6, zorder=1))
        if show[k]:
            ax.text(cx + cell / 2, cy + cell * 0.62, names[k], ha="center", va="center", fontsize=18, color=colors[k],
                    weight="bold", zorder=3)
            ax.text(cx + cell / 2, cy + cell * 0.3, str(values[k]), ha="center", va="center", fontsize=22, color=INK, zorder=3)
    for k in hl:
        r, c = divmod(k, 2)
        ax.add_patch(Rectangle((x0 + c * cell + 0.05, y0 + (1 - r) * cell + 0.05), cell - 0.1, cell - 0.1, fc="none",
                               ec=YELLOW_B, lw=5, zorder=4))
    ax.text(x0 + cell / 2, y0 + 2 * cell + 0.25, "양성 판정", ha="center", fontsize=15, color=MUTED)
    ax.text(x0 + 1.5 * cell, y0 + 2 * cell + 0.25, "음성 판정", ha="center", fontsize=15, color=MUTED)
    ax.text(x0 - 0.15, y0 + 1.5 * cell, "실제 양성", ha="right", va="center", fontsize=15, color=MUTED)
    ax.text(x0 - 0.15, y0 + 0.5 * cell, "실제 음성", ha="right", va="center", fontsize=15, color=MUTED)


@figure("4h-2", 560, 300)
def confusion_fill():
    """임계값 0 으로 판정해 혼동 행렬 채우기."""
    pos = Y > 0
    assert list(np.flatnonzero(pos) + 1) == [2, 4] and [num(v, 2) for v in YP] == [M + "8.74", "9.47", "0.37", "4.01", M + "3.27"]
    tp, fp, fn, tn = CONF0
    order = {3: [1, 3], 4: [2], 5: [0, 4]}

    def draw(stage, title):
        plt, fig = new(600)
        head(fig, title, size=20)
        ax = fig.add_axes([0.08, 0.17, 0.47, 0.70])
        tidy(ax)
        ax.set_ylim(-11, 12)
        ax.set_xlim(0.4, 5.6)
        ax.set_xticks(range(1, 6))
        ax.set_xticklabels(["사람 %d" % k for k in range(1, 6)], fontsize=15)
        done = [k for s in (3, 4, 5) if stage >= s for k in order[s]]
        for i in range(5):
            edge = "none"
            if i in done:
                edge = GREEN if (YP[i] > 0) == pos[i] else RED
            ax.bar(i + 1, YP[i], width=0.6, color=BLUE, edgecolor=edge, lw=4 if edge != "none" else 0, zorder=3)
            ax.text(i + 1, YP[i] + (0.6 if YP[i] > 0 else -1.6), num(YP[i], 2), ha="center", fontsize=15, color=INK)
            if pos[i]:
                ax.text(i + 1, -10.4, "양성", ha="center", fontsize=15, color=INK, weight="bold")
        if stage >= 2:
            ax.axhline(0, color=MUTED, lw=2, ls="--", zorder=4)
        ax.set_ylabel("예측 Yp")
        bx = boxes_axes(fig, (0.58, 0.05, 0.42, 0.8), xmax=4.6, ymax=5.0)
        show = (stage >= 3, stage >= 5, stage >= 4, stage >= 5)
        conf_grid(bx, 1.4, 1.2, 1.5, (tp, fn, fp, tn), show=show)
        return image(fig)

    frames = [draw(1, "다섯 사람의 예측 Yp"), draw(2, "임계값 0 보다 크면 양성 판정"), draw(3, "사람 2, 4: TP"), draw(4, "사람 3: FP"),
              draw(5, "사람 1, 5: TN, FN 은 없음"), draw(6, "혼동 행렬 TP 2, FN 0, FP 1, TN 2")]
    return frames, [2000, 2200, 2200, 2200, 2200, 2500]


@figure("4h-3", 560, 300)
def metric_cells():
    """혼동 행렬의 어느 칸으로 지표를 계산하는지(노랑 테두리)."""
    from fractions import Fraction
    tp, fp, fn, tn = CONF0
    acc, prec, rec = Fraction(tp + tn, 5), Fraction(tp, tp + fp), Fraction(tp, tp + fn)
    f1 = 2 * prec * rec / (prec + rec)
    assert (acc, prec, rec, f1) == (Fraction(4, 5), Fraction(2, 3), Fraction(1), Fraction(4, 5))
    rows = [("정확도", (0, 3), ["(TP + TN) ÷ 전체", "(2 + 2) ÷ 5 = 0.8"]),
            ("정밀도", (0, 2), ["TP ÷ (TP + FP)", "양성으로 판정한 열", "2 ÷ (2 + 1) = 0.667"]),
            ("재현율", (0, 1), ["TP ÷ (TP + FN)", "실제 양성인 행", "2 ÷ (2 + 0) = 1"]),
            ("F1", (0, 1, 2), ["2 × 정밀도 × 재현율", "÷ (정밀도 + 재현율)", "2 × 0.667 × 1 ÷ 1.667 = 0.8"])]
    assert num(float(prec), 3) == "0.667"
    frames = []
    for name, hl, lines in rows:
        plt, fig = new(600)
        head(fig, name, size=21)
        ax = boxes_axes(fig, (0.02, 0.05, 0.52, 0.82), xmax=5.6, ymax=5.0)
        conf_grid(ax, 1.9, 0.9, 1.6, (tp, fn, fp, tn), hl=hl)
        yy = 0.72
        for text in lines:
            fig.text(0.58, yy, text, fontsize=20, color=INK, va="center")
            yy -= 0.13
        frames.append(image(fig))
    return frames, [2200, 2200, 2200, 2500]


@figure("4h-4", 560, 300)
def roc_curve():
    """임계값을 내리며 (FPR, TPR) 을 찍어 ROC 곡선 그리기. AUC = 1."""
    from fractions import Fraction
    pos = Y > 0
    order = np.argsort(-YP)
    pts = [(Fraction(0), Fraction(0))]
    for k in range(1, 6):
        chosen = order[:k]
        tp = int(pos[chosen].sum())
        fp = k - tp
        pts.append((Fraction(fp, 3), Fraction(tp, 2)))
    assert pts == [(0, 0), (0, Fraction(1, 2)), (0, 1), (Fraction(1, 3), 1), (Fraction(2, 3), 1), (1, 1)]
    cuts = [10.5, 6.7, 2.2, -1.5, -6.0, -9.6]
    frame_pts = [1, 2, 3, 4, 5, 6]
    ranked = sorted(YP, reverse=True)
    assert cuts[0] > ranked[0] and cuts[-1] < ranked[-1]
    assert all(ranked[k] > cuts[k + 1] > ranked[k + 1] for k in range(4))
    titles = ["임계값이 가장 클 때 (0, 0)", "사람 2 만 양성 (0, 0.5)", "사람 2, 4 가 양성 (0, 1)", "사람 3 도 양성 (1/3, 1)",
              "사람 5 도 양성 (2/3, 1)", "모두 양성 (1, 1)", "AUC = 1"]

    def draw(stage):
        plt, fig = new(600)
        head(fig, titles[stage - 1], size=20)
        ax = fig.add_axes([0.08, 0.14, 0.29, 0.72])
        tidy(ax, grid=False)
        ax.set_xlim(0, 1)
        ax.set_ylim(-11, 12)
        ax.set_xticks([])
        ax.set_ylabel("예측 Yp")
        for i in range(5):
            if pos[i]:
                ax.scatter([0.35], [YP[i]], s=150, color=INK, zorder=5)
            else:
                ax.scatter([0.35], [YP[i]], s=150, facecolor="white", edgecolor=INK, lw=2.2, zorder=5)
            ax.text(0.47, YP[i], "사람 %d%s" % (i + 1, " 양성" if pos[i] else ""), fontsize=15, va="center", color=INK)
        ax.axhline(cuts[min(stage, 6) - 1], color=MUTED, lw=2.2, ls="--")
        bx = fig.add_axes([0.52, 0.14, 0.40, 0.72])
        tidy(bx)
        bx.set_xlim(-0.03, 1.03)
        bx.set_ylim(-0.03, 1.03)
        bx.set_aspect("equal")
        bx.set_xlabel("FPR")
        bx.set_ylabel("TPR")
        bx.plot([0, 1], [0, 1], color="#9ca3af", lw=1.8, ls="--")
        n = frame_pts[min(stage, 6) - 1]
        px = [float(a) for a, _ in pts[:n]]
        py = [float(b) for _, b in pts[:n]]
        if stage == 7:
            bx.fill_between([0, 1], [1, 1], color=PURPLE_L, zorder=0)
            bx.text(0.3, 0.55, "AUC = 1", fontsize=20, color=PURPLE, weight="bold", ha="center")
            bx.text(0.78, 0.15, "무작위 0.5", fontsize=15, color=MUTED, ha="center")
        bx.plot(px, py, color=PURPLE, lw=3.2, marker="o", ms=10, zorder=4)
        return image(fig)

    frames = [draw(s) for s in range(1, 8)]
    return frames, [1800, 2000, 2000, 2000, 2000, 2200, 2500]


@figure("4h-5", 560, 280)
def summary_4h():
    """외울 것 그림. 회귀 지표, 혼동 행렬과 식, 지표 고르기와 ROC."""
    plt, fig = new(560)
    ax = boxes_axes(fig, ymax=5.6)
    card(ax, 0.15, 2.95, 3.6, 2.5, "회귀 지표", ["MAE: $|\\,e\\,|$ 의 평균", "RMSE: $\\sqrt{\\mathrm{MSE}}$, 큰 오차에 민감", "$R^2$: 1 이 최고, 음수도 됨"],
         size=15, gap=0.48)
    conf_grid(ax, 5.3, 3.0, 1.0, ("", "", "", ""), show=(True, True, True, True))
    card(ax, 7.6, 2.95, 3.45, 2.5, "식", ["정밀도 TP ÷ (TP + FP)", "재현율 TP ÷ (TP + FN)", "F1 = 2PR ÷ (P + R)"], size=15,
         gap=0.48)
    card(ax, 0.15, 0.15, 5.35, 2.55, "어느 지표를 보나",
         [("놓치면 안 됨(FN): 재현율", RED), ("잘못 양성이면 안 됨(FP): 정밀도", RED), "드문 양성: 정확도만 보지 않음"], size=15,
         gap=0.5)
    card(ax, 5.7, 0.15, 5.35, 2.55, "ROC 곡선과 AUC", ["가로 FPR, 세로 TPR", "AUC 0.5: 무작위 판정", "AUC 1: 양성 점수가 모두 음성보다 큼"], size=15,
         gap=0.48)
    return image(fig, symbols=True)


# 세 수준으로 다시 보기(ai-levels 블록) 그림. 블록마다 수준(7, 15, 20)을 받는 함수 하나와 이름마다 얇은 등록 함수 셋을 둠.
# 크기는 화면 520×280(파일 1040×560), 글자는 22pt 이상. 7살 그림에는 식 기호와 코드 글꼴을 쓰지 않음. 색 뜻은 그 단원 것을
# 따름(4b·4c·4d·4e·4h 단원 색 주석). 숫자는 위의 단계 상수(X, Y, L, grads, W_END, YP)에서 다시 계산하고 assert 함
LV_W, LV_H = 1040, 560
LV_FONT = 22
BLUE_P = "#dbeafe"


def lv_fig():
    """(pyplot, Figure). 파일 1040×560 의 빈 Figure."""
    plt = setup()
    plt.rcParams.update(SIZES)
    return plt, plt.figure(figsize=(LV_W / 100.0, LV_H / 100.0), dpi=100)


def lv_canvas():
    """(Figure, Axes). Axes 는 그림 전체를 덮고 좌표는 파일 픽셀(왼쪽 위 0, 0)."""
    plt = setup()
    plt.rcParams.update(SIZES)
    fig = plt.figure(figsize=(LV_W / 100.0, LV_H / 100.0), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, LV_W)
    ax.set_ylim(LV_H, 0)
    ax.axis("off")
    return fig, ax


def lv_text(ax, x, y, s, size=LV_FONT, color=INK, ha="center", va="center", bold=False, mono=False, math=False):
    """math 면 위 첨자(², ³)가 큰 DejaVu Sans 로 쓰고 한글만 나눔고딕으로 씀."""
    kw = dict(fontsize=size, color=color, ha=ha, va=va, weight="bold" if bold else "normal", zorder=6)
    if mono:
        kw["family"] = CODE
    elif math:
        kw["family"] = ["DejaVu Sans", "NanumGothic"]
    return ax.text(x, y, s, **kw)


def lv_box(ax, x, y, w, h, fc="white", ec=INK, lw=2.5, rounded=True):
    from matplotlib.patches import FancyBboxPatch, Rectangle
    if rounded:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=12", fc=fc, ec=ec, lw=lw, zorder=2))
    else:
        ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, zorder=2))


def lv_arrow(ax, x1, y1, x2, y2, color=INK, lw=3, ls="-"):
    from matplotlib.patches import FancyArrowPatch
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=24, color=color, lw=lw, zorder=4,
                                 shrinkA=0, shrinkB=0, linestyle=ls))


def lv_table(ax, x0, y0, rows, widths, ch=64, fills=None, colors=None, mono_cols=(), size=LV_FONT, head=True):
    """표. rows[0] 은 머리(회색 칸). fills(r, c)·colors(r, c) 는 칸 바탕색과 글자색(없으면 None)."""
    for r, row in enumerate(rows):
        x = x0
        for j, text in enumerate(row):
            hd = head and r == 0
            fc = NOTE if hd else ((fills(r, j) if fills else None) or "white")
            lv_box(ax, x, y0 + r * ch, widths[j], ch, fc=fc, ec=FAINT, lw=1.5, rounded=False)
            col = MUTED if hd else ((colors(r, j) if colors else None) or INK)
            lv_text(ax, x + widths[j] / 2, y0 + r * ch + ch / 2, text, size=size, color=col, mono=(j in mono_cols and not hd))
            x += widths[j]


def lv_axes(fig, rect):
    ax = fig.add_axes(rect)
    tidy(ax)
    ax.tick_params(labelsize=LV_FONT, colors=MUTED)
    return ax


def lv_ticks(ax, xs=None, ys=None, nd=4):
    """눈금 글을 빼기표 U+2212 로 적음."""
    if xs is not None:
        ax.set_xticks(xs)
        ax.set_xticklabels([num(v, nd) for v in xs])
    if ys is not None:
        ax.set_yticks(ys)
        ax.set_yticklabels([num(v, nd) for v in ys])


# 4b/3 경사하강법

def levels_4b3(level):
    gw = {w: grads(w, 1.0)[0] for w in (0.6, 1.0, 1.4, 2.2)}
    assert [round(gw[w], 2) for w in (0.6, 1.0, 1.4, 2.2)] == [-28.32, -19.04, -9.76, 8.8]
    w_best = float((X * Y).sum() / (X * X).sum())
    assert num(w_best) == "1.8207" and abs(grads(w_best, 1.0)[0]) < 1e-9
    if level == 7:
        assert num(2.2 - 0.001 * gw[2.2]) == "2.1912"
        plt, fig = lv_fig()
        ax = fig.add_axes([0.06, 0.16, 0.88, 0.78])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ws = np.linspace(0.4, 2.6, 120)
        ax.plot(ws, [LW(w) for w in ws], color=RED, lw=4)
        for w in (1.0, 2.2):
            ax.plot([w], [LW(w)], "o", color=INK, ms=14, zorder=5)
        ax.annotate("", xy=(1.42, LW(1.0) + 1.6), xytext=(1.02, LW(1.0) + 1.6),
                    arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=4, mutation_scale=28))
        ax.text(1.03, LW(1.0) + 2.6, "W를 키움", fontsize=24, color=GREEN, ha="left", va="bottom")
        ax.set_xlim(0.35, 2.65)
        ax.set_ylim(3, 22)
        ax.set_yticks([])
        ax.set_xticks([1.0, 2.2])
        ax.set_xticklabels(["1", "2.2"])
        ax.tick_params(labelsize=24, colors=INK)
        ax.set_xlabel("W", fontsize=24, color=INK)
        return image(fig)
    if level == 15:
        plt, fig = lv_fig()
        fig.text(0.5, 0.94, "W가 바뀌는 양 = " + M + " 학습률 × W.grad", fontsize=24, color=INK, ha="center", va="center")
        ax = lv_axes(fig, [0.16, 0.17, 0.78, 0.66])
        ws = np.linspace(0.4, 2.6, 50)
        mv = [-0.001 * grads(w, 1.0)[0] for w in ws]
        ax.axhline(0, color=MUTED, lw=1.5)
        ax.plot(ws, mv, color=GREEN, lw=3.5)
        pts = [(0.6, "0.02832", 0.07, 0.003, "left", "bottom"), (1.0, "0.01904", 0.07, 0.003, "left", "bottom"),
               (w_best, "W 1.8207 에서 0", 0.06, 0.004, "left", "bottom"),
               (2.2, M + "0.0088", -0.07, -0.0018, "right", "top")]
        for w, label, dx, dy, ha, va in pts:
            v = -0.001 * grads(w, 1.0)[0]
            assert label.endswith(num(v, 5)), (w, v)
            ax.plot([w], [v], "o", color=GREEN, ms=12, zorder=5)
            ax.text(w + dx, v + dy, label, fontsize=LV_FONT, color=INK, ha=ha, va=va)
        ax.set_xlim(0.35, 2.65)
        ax.set_ylim(-0.016, 0.036)
        lv_ticks(ax, xs=[0.6, 1.0, 1.4, 2.2], ys=[-0.01, 0, 0.01, 0.02, 0.03], nd=2)
        ax.set_xlabel("W", fontsize=LV_FONT, color=INK)
        ax.set_ylabel("W가 바뀌는 양", fontsize=LV_FONT, color=INK)
        return image(fig)
    # 20살: 학습률마다 어림한 변화와 실제 변화
    g0w, g0b = grads(1.0, 1.0)
    sq = g0w ** 2 + g0b ** 2
    rows = [["학습률", "어림한 변화", "실제 변화", "갱신 뒤 손실"]]
    want = {0.001: (M + "0.3665", M + "0.3623", "12.9897"), 0.01: (M + "3.6652", M + "3.2443", "10.1077"),
            0.1: (M + "36.6522", "+5.4403", "18.7923")}
    for lr in (0.001, 0.01, 0.1):
        w2, b2 = 1 - lr * g0w, 1 - lr * g0b
        est, act, after = -lr * sq, float(L(w2, b2)) - 13.352, float(L(w2, b2))
        got = (num(est), ("+" if act > 0 else "") + num(act), num(after))
        assert got == want[lr], (lr, got)
        rows.append([num(lr)] + list(got))
    fig, ax = lv_canvas()
    lv_text(ax, LV_W / 2, 48, "W, B = 1 - lr * (-19.04), 1 - lr * 2.0", mono=True)
    widths = [170, 250, 230, 250]
    lv_table(ax, (LV_W - sum(widths)) / 2, 100, rows, widths, ch=72,
             fills=lambda r, j: RED_L if (r, j) == (3, 2) else None,
             colors=lambda r, j: ORANGE if j == 1 and r > 0 else (RED if j in (2, 3) and r > 0 else None))
    lv_text(ax, LV_W / 2, 440, "어림한 변화 = " + M + "학습률 × (W.grad² + B.grad²)", color=ORANGE, math=True)
    lv_text(ax, LV_W / 2, 500, "학습률 0.1 이면 W가 2.904로 1.8207을 지나침", color=MUTED)
    return image(fig)


@figure("4b-31", 520, 280)
def levels_4b3_7():
    return levels_4b3(7)


@figure("4b-32", 520, 280)
def levels_4b3_15():
    return levels_4b3(15)


@figure("4b-33", 520, 280)
def levels_4b3_20():
    return levels_4b3(20)


# 4c/2 연쇄법칙

def person2(w, xp=5.0, yt=10.3):
    yp = w * xp + 1
    e = yp - yt
    s = e * e
    return yp, e, s, s / 5


def levels_4c2(level):
    base = person2(1.0)
    assert [num(v, 4) for v in base] == ["6", M + "4.3", "18.49", "3.698"]
    if level == 7:
        new_ = person2(1.01)
        d = [n - b for n, b in zip(new_, base)]
        assert [num(v, 4) for v in d] == ["0.05", "0.05", M + "0.4275", M + "0.0855"]
        fig, ax = lv_canvas()
        vals = ["W 1", "6", M + "4.3", "18.49", "3.698"]
        widths = [130, 150, 150, 150, 150]
        gap = 62
        x = (LV_W - sum(widths) - gap * 4) / 2
        xs = []
        for k, (v, w) in enumerate(zip(vals, widths)):
            lv_box(ax, x, 200, w, 96, fc=BLUE_L if k else "white", ec=BLUE if k else INK)
            lv_text(ax, x + w / 2, 248, v, size=28, bold=True)
            xs.append((x, w))
            x += w + gap
        mult = ["5배", "1배", M + "8.6배", "0.2배"]
        for k in range(4):
            x1 = xs[k][0] + xs[k][1] + 6
            x2 = xs[k + 1][0] - 6
            lv_arrow(ax, x1, 248, x2, 248)
            lv_text(ax, (x1 + x2) / 2, 160, mult[k], size=24, color=ORANGE, bold=True)
        under = ["0.01\n키움", "0.05\n커짐", "0.05\n커짐", "약 0.43\n작아짐", "약 0.086\n작아짐"]
        for (x0, w), t in zip(xs, under):
            lv_text(ax, x0 + w / 2, 370, t, size=24, color=BLUE, va="center")
        lv_text(ax, LV_W / 2, 486, "사람 2의 네 칸", size=24, color=MUTED)
        return image(fig)
    if level == 15:
        from fractions import Fraction as Fr

        def contrib(h):
            return ((5 * (1 + Fr(h)) + 1 - Fr("10.3")) ** 2) / 5

        ratio = {h: (contrib(h) - contrib(0)) / Fr(h) for h in ("0.1", "0.05", "0.01", "0.001")}
        assert ratio["0.1"] == Fr("-8.1") and ratio["0.05"] == Fr("-8.35") and ratio["0.01"] == Fr("-8.55")
        assert ratio["0.001"] == Fr("-8.595") and contrib("0.1") == Fr("2.888")
        plt, fig = lv_fig()
        fig.text(0.5, 0.94, "사람 2가 보태는 값 = (5 × W + 1 " + M + " 10.3)² ÷ 5", fontsize=24, color=INK, ha="center",
                 va="center", family=["DejaVu Sans", "NanumGothic"])
        ax = lv_axes(fig, [0.15, 0.17, 0.80, 0.66])
        hs = np.linspace(0, 0.11, 20)
        ax.plot(hs, -8.6 + 5 * hs, color=GREEN, lw=3.5)
        ax.axhline(-8.6, color=MUTED, lw=2.5, ls="--")
        ax.text(0.106, -8.585, "곱으로 구한 " + M + "8.6", fontsize=LV_FONT, color=MUTED, ha="right", va="bottom")
        for h, label in ((0.1, M + "8.1"), (0.05, M + "8.35"), (0.001, None)):
            v = -8.6 + 5 * h
            ax.plot([h], [v], "o", color=GREEN, ms=12, zorder=5)
            if label:
                ax.text(h - 0.004, v + 0.02, label, fontsize=LV_FONT, color=INK, ha="right", va="bottom")
        ax.set_xlim(-0.004, 0.112)
        ax.set_ylim(-8.68, -7.98)
        lv_ticks(ax, xs=[0, 0.05, 0.1], ys=[-8.6, -8.4, -8.2, -8.0], nd=2)
        ax.set_xlabel("W를 키운 양 h", fontsize=LV_FONT, color=INK)
        ax.set_ylabel("변화량 ÷ h", fontsize=LV_FONT, color=INK)
        return image(fig)
    # 20살: backward 뒤 .grad (float32 출력은 checks 스크립트에서 확인)
    g_yp = 2 * base[1] / 5
    assert num(g_yp, 4) == M + "1.72" and num(g_yp * 5, 4) == M + "8.6"
    fig, ax = lv_canvas()
    lv_text(ax, LV_W / 2, 48, "Yp = W * 5 + 1;  L2 = (Yp - 10.3)**2 / 5", mono=True)
    rows = [["텐서", "retain_grad() 없이", "retain_grad() 뒤"],
            ["W", "tensor(-8.6000)", "tensor(-8.6000)"],
            ["Yp", "None", "tensor(-1.7200)"]]
    widths = [140, 380, 380]
    lv_table(ax, (LV_W - sum(widths)) / 2, 110, rows, widths, ch=80, mono_cols=(1, 2),
             fills=lambda r, j: GREEN_L if r == 1 and j > 0 else (RED_L if (r, j) == (2, 1) else
                                                                   (ORANGE_L if (r, j) == (2, 2) else None)),
             colors=lambda r, j: GREEN if r == 1 and j > 0 else (RED if (r, j) == (2, 1) else
                                                                 (ORANGE if (r, j) == (2, 2) else None)))
    lv_text(ax, LV_W / 2, 420, "Yp.grad " + M + "1.72 = 1 × 0.2 × (" + M + "8.6) × 1", color=ORANGE)
    lv_text(ax, LV_W / 2, 480, "W.grad " + M + "8.6 = " + M + "1.72 × 5", color=GREEN)
    return image(fig)


@figure("4c-21", 520, 280)
def levels_4c2_7():
    return levels_4c2(7)


@figure("4c-22", 520, 280)
def levels_4c2_15():
    return levels_4c2(15)


@figure("4c-23", 520, 280)
def levels_4c2_20():
    return levels_4c2(20)


# 4d/5 XOR 와 은닉층

def levels_4d5(level):
    xor = [0, 1, 1, 0]
    assert [a ^ c for a, c in STEP4] == xor
    if level == 7:
        plt, fig = lv_fig()
        for k, rect in enumerate(([0.05, 0.08, 0.40, 0.74], [0.55, 0.08, 0.40, 0.74])):
            ax = fig.add_axes(rect)
            ax.set_xlim(-0.45, 1.45)
            ax.set_ylim(-0.45, 1.45)
            ax.set_aspect("equal")
            ax.axis("off")
            if k == 0:
                xs_ = np.array([-0.45, 1.45])
                ax.plot(xs_, 0.5 - xs_, color=ORANGE, lw=4)
                ax.plot([1], [1], "o", ms=46, mfc="none", mec=RED, mew=4, zorder=6)
                fig.text(0.25, 0.9, "직선 하나", fontsize=24, color=INK, ha="center")
            else:
                xs_ = np.array([-0.45, 1.45])
                ax.fill_between(xs_, 0.5 - xs_, 1.5 - xs_, color=BLUE_P, zorder=0)
                ax.plot(xs_, 0.5 - xs_, color=ORANGE, lw=4)
                ax.plot(xs_, 1.5 - xs_, color=ORANGE, lw=4)
                fig.text(0.75, 0.9, "직선 둘", fontsize=24, color=INK, ha="center")
            for (a, c), out in zip(STEP4, xor):
                if out:
                    ax.plot([a], [c], "o", ms=30, color=BLUE, zorder=5)
                else:
                    ax.plot([a], [c], "o", ms=30, mfc="white", mec=MUTED, mew=3.5, zorder=5)
                ax.text(a, c, str(out), fontsize=24, color="white" if out else INK, ha="center", va="center", zorder=7,
                        weight="bold")
        return image(fig)
    if level == 15:
        plt, fig = lv_fig()
        fig.text(0.5, 0.95, "s = x1 + x2", fontsize=24, color=INK, ha="center", va="center")
        ss = np.linspace(-0.3, 2.3, 400)
        rows = [("h1", (ss - 0.5 > 0).astype(float), PURPLE), ("h2", (-ss + 1.5 > 0).astype(float), PURPLE),
                ("y", (((ss - 0.5 > 0).astype(float) + (-ss + 1.5 > 0).astype(float)) - 1.5 > 0).astype(float), BLUE)]
        for k, (name, vals, col) in enumerate(rows):
            ax = fig.add_axes([0.14, 0.66 - k * 0.245, 0.80, 0.17])
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            ax.plot(ss, vals, color=col, lw=4)
            for s in (0, 1, 2):
                v = {"h1": int(s - 0.5 > 0), "h2": int(-s + 1.5 > 0), "y": int(s == 1)}[name]
                ax.plot([s], [v], "o", color=col, ms=12, zorder=5)
            for t in (0.5, 1.5):
                ax.axvline(t, color=ORANGE, lw=2.5, ls="--")
            ax.set_xlim(-0.3, 2.3)
            ax.set_ylim(-0.3, 1.4)
            ax.set_yticks([0, 1])
            ax.tick_params(labelsize=LV_FONT, colors=MUTED)
            ax.set_xticks([0, 0.5, 1, 1.5, 2] if k == 2 else [])
            if k == 2:
                ax.set_xticklabels(["0", "0.5", "1", "1.5", "2"])
                ax.set_xlabel("s", fontsize=LV_FONT, color=INK, labelpad=2)
            fig.text(0.06, 0.66 - k * 0.245 + 0.085, name, fontsize=24, color=col, ha="center", va="center", weight="bold")
        assert [int(s == 1) for s in (0, 1, 2)] == [0, 1, 0]
        return image(fig)
    # 20살: 입력 네 개를 한 번에
    P = np.array(STEP4, float)
    W1 = np.array([[1.0, 1.0], [-1.0, -1.0]])
    b1 = np.array([-0.5, 1.5])
    z1 = P @ W1.T + b1
    h = (z1 > 0).astype(int)
    yv = (h.sum(1) - 1.5 > 0).astype(int)
    assert yv.tolist() == xor and h.tolist() == [[0, 1], [1, 1], [1, 1], [1, 0]]
    rows = [["x", "z", "h", "y"]]
    for i in range(4):
        rows.append(["%d, %d" % STEP4[i], ", ".join(num(v) for v in z1[i]), "%d, %d" % tuple(h[i]), str(yv[i])])
    assert rows[1][1] == M + "0.5, 1.5" and rows[4][1] == "1.5, " + M + "0.5"
    fig, ax = lv_canvas()
    lv_text(ax, LV_W / 2, 44, "h = (x @ W1.t() + b1 > 0).float()", mono=True)
    widths = [170, 260, 170, 110]
    lv_table(ax, (LV_W - sum(widths)) / 2, 90, rows, widths, ch=72,
             fills=lambda r, j: PURPLE_L if j == 2 and r > 0 else (BLUE_P if j == 3 and r > 0 and rows[r][3] == "1" else None),
             colors=lambda r, j: PURPLE if j == 2 and r > 0 else (BLUE if j == 3 and r > 0 and rows[r][3] == "1" else None))
    lv_text(ax, LV_W / 2, 480, "x [4, 2]  @  W1.t() [2, 2]  →  z, h [4, 2]  →  y [4]", color=MUTED)
    return image(fig)


@figure("4d-51", 520, 280)
def levels_4d5_7():
    return levels_4d5(7)


@figure("4d-52", 520, 280)
def levels_4d5_15():
    return levels_4d5(15)


@figure("4d-53", 520, 280)
def levels_4d5_20():
    return levels_4d5(20)


# 4e/4 기울기 소실

def levels_4e4(level):
    assert dsig(0) == 0.25 and num(float(dsig(2)), 4) == "0.105"
    if level == 7:
        vals = [1, 0.25, 0.0625, 0.015625]
        assert all(abs(vals[k] - 0.25 ** k) < 1e-15 for k in range(4)) and 0.25 ** 4 < 0.01 < 0.25 ** 3
        plt, fig = lv_fig()
        ax = fig.add_axes([0.06, 0.14, 0.88, 0.80])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.bar(range(4), vals, width=0.6, color=ORANGE_L, edgecolor=ORANGE, lw=2.5)
        for k, v in enumerate(vals):
            ax.text(k, v + 0.03, num(v, 6), fontsize=24, color=INK, ha="center", va="bottom")
        ax.text(4, 0.16, "?", fontsize=34, color=INK, ha="center", va="bottom", weight="bold")
        ax.axhline(0.01, color=MUTED, lw=2.5, ls="--")
        ax.text(4.48, 0.03, "0.01", fontsize=24, color=MUTED, ha="right", va="bottom")
        ax.set_xlim(-0.5, 4.5)
        ax.set_ylim(0, 1.18)
        ax.set_yticks([])
        ax.set_xticks(range(5))
        ax.set_xticklabels(["처음", "한 번", "두 번", "세 번", "네 번"])
        ax.tick_params(labelsize=24, colors=INK)
        return image(fig)
    if level == 15:
        d2 = 0.1050
        rows = [["", "시그모이드 x = 0", "시그모이드 x = 2", "ReLU x = 2"]]
        for n, name in ((1, "한 번"), (2, "두 번"), (3, "세 번")):
            rows.append([name, num(0.25 ** n, 6), "%.4f" % (d2 ** n), "1"])
        assert [r[2] for r in rows[1:]] == ["0.1050", "0.0110", "0.0012"]
        assert [r[1] for r in rows[1:]] == ["0.25", "0.0625", "0.015625"]
        fig, ax = lv_canvas()
        fig.text(0.5, 0.92, "곱 = (첫째 미분값) × (둘째 미분값) × … × (n째 미분값)", fontsize=LV_FONT, color=INK, ha="center",
                 va="center")
        widths = [130, 280, 280, 200]
        lv_table(ax, (LV_W - sum(widths)) / 2, 110, rows, widths, ch=76,
                 colors=lambda r, j: ORANGE if r > 0 and j > 0 else None)
        lv_text(ax, LV_W / 2, 470, "모든 층의 입력이 같다고 두고 가중치는 뺌", color=MUTED)
        return image(fig)
    # 20살: x = 0 에서 시그모이드 세 번
    v = 0.0
    rows = [["층", "입력", "σ(입력)", "σ'(입력)", "곱"]]
    prod = 1.0
    for k in range(3):
        s_, d_ = float(sig(v)), float(dsig(v))
        prod *= d_
        rows.append([str(k + 1), num(v, 4), num(s_, 4), "%.4f" % d_ if k else num(d_, 4), num(prod, 4)])
        v = s_
    assert [r[4] for r in rows[1:]] == ["0.25", "0.0588", "0.0134"] and [r[3] for r in rows[1:]] == ["0.25", "0.2350", "0.2273"]
    assert prod < 0.25 ** 3
    fig, ax = lv_canvas()
    lv_text(ax, LV_W / 2, 44, "for _ in range(3): h = torch.sigmoid(h)", mono=True)
    widths = [100, 170, 200, 200, 170]
    lv_table(ax, (LV_W - sum(widths)) / 2, 90, rows, widths, ch=72,
             fills=lambda r, j: ORANGE_L if (r, j) == (3, 4) else None,
             colors=lambda r, j: BLUE if j == 2 and r > 0 else (ORANGE if j in (3, 4) and r > 0 else None))
    lv_text(ax, LV_W / 2, 430, "상한 0.25³ = 0.015625", color=MUTED, math=True)
    lv_text(ax, LV_W / 2, 490, "x.grad = tensor(0.0134)", color=ORANGE, mono=True)
    return image(fig)


@figure("4e-41", 520, 280)
def levels_4e4_7():
    return levels_4e4(7)


@figure("4e-42", 520, 280)
def levels_4e4_15():
    return levels_4e4(15)


@figure("4e-43", 520, 280)
def levels_4e4_20():
    return levels_4e4(20)


# 4h/4 정밀도와 재현율

def levels_4h4(level):
    y_true = (Y > 0).astype(int)
    y_pred = (YP > 0).astype(int)
    assert y_true.tolist() == [0, 1, 0, 1, 0] and y_pred.tolist() == [0, 1, 1, 1, 0]
    tp = int((y_true * y_pred).sum())
    assert tp == 2 and y_pred.sum() == 3 and y_true.sum() == 2
    if level == 7:
        fig, ax = lv_canvas()
        xs = [140 + k * 190 for k in range(5)]
        lv_box(ax, xs[1] - 85, 150, xs[3] - xs[1] + 170, 200, fc="white", ec=YELLOW_B, lw=5)
        lv_text(ax, (xs[1] + xs[3]) / 2, 112, "직선이 무겁다고 고른 사람", size=24, color=INK)
        from matplotlib.patches import Circle
        for k, x0 in enumerate(xs):
            heavy = bool(y_true[k])
            ax.add_patch(Circle((x0, 250), 58, fc=INK if heavy else "white", ec=INK, lw=3, zorder=3))
            lv_text(ax, x0, 250, "사람 %d" % (k + 1), size=22, color="white" if heavy else INK, bold=heavy)
            if heavy:
                lv_text(ax, x0, 400, "실제로\n무거움", size=24, color=INK)
        return image(fig)
    if level == 15:
        plt, fig = lv_fig()
        fig.text(0.5, 0.94, "정밀도 = TP ÷ (TP + FP),  재현율 = TP ÷ (TP + FN)", fontsize=LV_FONT, color=INK, ha="center",
                 va="center")
        ax = lv_axes(fig, [0.12, 0.14, 0.64, 0.68])
        prec, rec = tp / 3, tp / 2
        assert num(prec, 3) == "0.667" and rec == 1
        ax.bar([0 - 0.18, 1 - 0.18], [prec, rec], width=0.32, color=BLUE)
        ax.bar([1 + 0.18], [1.0], width=0.32, color="#9ca3af")
        ax.text(0 + 0.18, 0.06, "?", fontsize=34, color=INK, ha="center", va="bottom", weight="bold")
        ax.text(-0.18, prec + 0.03, "0.667", fontsize=LV_FONT, color=INK, ha="center", va="bottom")
        ax.text(1 - 0.18, rec + 0.03, "1", fontsize=LV_FONT, color=INK, ha="center", va="bottom")
        ax.text(1 + 0.18, 1.03, "1", fontsize=LV_FONT, color=INK, ha="center", va="bottom")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["정밀도", "재현율"])
        ax.set_ylim(0, 1.22)
        ax.set_xlim(-0.6, 1.6)
        lv_ticks(ax, ys=[0, 0.5, 1], nd=1)
        fig.text(0.79, 0.62, "직선", fontsize=LV_FONT, color=BLUE, ha="left", weight="bold")
        fig.text(0.79, 0.50, "모두 양성", fontsize=LV_FONT, color=MUTED, ha="left", weight="bold")
        return image(fig)
    # 20살: 사람마다 y_true, y_pred, 곱
    fig, ax = lv_canvas()
    lv_text(ax, LV_W / 2, 44, "tp = (y_pred * y_true).sum()", mono=True)
    prod = (y_pred * y_true).tolist()
    rows = [["", "1", "2", "3", "4", "5", "합"],
            ["y_true"] + [str(v) for v in y_true] + [str(int(y_true.sum()))],
            ["y_pred"] + [str(v) for v in y_pred] + [str(int(y_pred.sum()))],
            ["곱"] + [str(v) for v in prod] + [str(tp)]]
    widths = [170, 100, 100, 100, 100, 100, 110]

    def fill(r, j):
        if r == 3 and 1 <= j <= 5 and prod[j - 1]:
            return GREEN_L
        if r == 2 and j == 3:
            return RED_L
        return None

    lv_table(ax, (LV_W - sum(widths)) / 2, 90, rows, widths, ch=70, fills=fill, mono_cols=(0,),
             colors=lambda r, j: GREEN if fill(r, j) == GREEN_L else (RED if fill(r, j) == RED_L else None))
    lv_text(ax, LV_W / 2, 420, "정밀도 tp / y_pred.sum() = 2 ÷ 3 = 0.6667", color=INK)
    lv_text(ax, LV_W / 2, 480, "재현율 tp / y_true.sum() = 2 ÷ 2 = 1", color=INK)
    return image(fig)


@figure("4h-41", 520, 280)
def levels_4h4_7():
    return levels_4h4(7)


@figure("4h-42", 520, 280)
def levels_4h4_15():
    return levels_4h4(15)


@figure("4h-43", 520, 280)
def levels_4h4_20():
    return levels_4h4(20)


if __name__ == "__main__":
    from tools.ai_art import render
    rows = render("l04", sys.argv[1:] or None)
    for row in rows:
        print(row["name"], os.path.relpath(row["path"], ROOT), "; ".join(row["problems"]))
