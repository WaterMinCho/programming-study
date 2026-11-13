#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5차시 학습 노트 l05 의 그림(5a 레이어 함수와 모델, 5b 활성화 함수, 5c 기울기 소실·폭발과 초기화, 5d 경사하강법의 세 갈래와
미니배치, 5e 학습률과 스케줄러, 5f 배치 정규화, 5g 코드 읽기).

그림에 찍는 숫자는 모두 이 파일에서 numpy 로 다시 계산하고 assert 로 확인함. 검산 기록은 설계 폴더 pr2/checks/l05_values.py.

  python -m tools.ai_art l05                 ai/learn/l05/assets/ 에 그림을 모두 쓰고 manifest 를 고침
  python -m tools.ai_art l05 5a-2 5d-1       이름을 적은 그림만

numpy·matplotlib·Pillow 가 있는 출제자 파이썬에서만 돌림. matplotlib 는 Agg 로만 씀(창을 띄우지 않음).
파일은 1120×600 이하(화면 560×300), GIF 는 장 10개 이하·장마다 1600~2500ms·64색, 마지막 장은 정지 요약임.

단원마다 한 색은 한 뜻이고 뜻은 캡션에 적음.
  5a 회색 테두리는 텐서, 파랑은 레이어 함수, 보라는 파라미터, 노랑은 지금 만든 텐서, 빨강은 오류
  5b 파랑은 Linear 층만으로 만든 직선(점선 h1, 점 줄 h2), 초록은 ReLU 를 지난 선, 검정은 정답 자료, 회색 점선은 y = x²
  5c 파랑은 순전파 값, 주황은 역전파로 오는 기울기, 보라는 역전파에 쓰려고 저장한 값,
     5c-3 의 빨강은 표준편차 0.01, 회색은 Xavier, 초록은 He
  5d 파랑은 배치 경사하강법, 주황은 SGD, 초록은 미니배치, 회색 곡선은 등고선, 노랑은 마지막 배치
  5e 회색 곡선은 손실 L = w², 검정은 지금 w, 파랑은 StepLR, 보라는 MultiStepLR, 초록은 ExponentialLR,
     주황은 CosineAnnealingLR, 빨강은 OneCycleLR
  5f 파랑은 원래 값 x, 초록은 x̂, 보라는 y, 주황은 지금 배치의 평균·분산과 배치 정규화가 평균 내는 방향,
     회색은 이동 평균, 빨강은 Layer Normalization 이 평균 내는 방향
  5g 파랑은 학습 데이터, 주황은 테스트 데이터, 초록은 fit 으로 구한 평균·표준편차, 보라는 정답 y,
     노랑은 지금 꺼낸 배치와 행마다 가장 큰 칸, 빨강은 손실
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
BLUE_L, BLUE_M, ORANGE_L, GREEN_L, PURPLE_L, RED_L = "#dbeafe", "#93c5fd", "#ffedd5", "#d1fae5", "#ede9fe", "#fee2e2"
NOTE, BAND, LIGHT = "#f3f4f6", "#e5e7eb", "#9ca3af"
CODE = "D2Coding"
MATH = "DejaVu Sans"  # 나눔고딕의 γ·²·√ 글리프가 작거나 다르게 생겨 한글 없는 식은 이 글꼴로 씀
M = MINUS
SIZES = {"font.size": 20, "axes.titlesize": 20, "axes.labelsize": 19, "xtick.labelsize": 17, "ytick.labelsize": 17,
         "axes.linewidth": 1.2, "axes.edgecolor": "#9ca3af"}


def num(v, nd=4):
    """그림에 찍는 숫자. 빼기표는 U+2212, 끝의 0 은 지움."""
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"
    return ("0" if s in ("-0", "0") else s).replace("-", M)


def comma(v):
    return f"{int(v):,}"


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


def board(fig, h=600):
    """그림 전체를 덮는 좌표판. 가로 0~112, 세로 0~h/10(파일 10px 이 1)."""
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 112)
    ax.set_ylim(0, h / 10.0)
    ax.axis("off")
    return ax


def box(ax, x, y, w, h, text="", fc="white", ec=INK, color=INK, size=18, lw=2.0, family=None, weight="normal",
        ha="center", ls="-"):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.8", fc=fc, ec=ec, lw=lw, ls=ls,
                                zorder=3))
    if text:
        tx = x + w / 2 if ha == "center" else x + 1.0
        kw = dict(color=color, fontsize=size, ha=ha, va="center", zorder=4, weight=weight, linespacing=1.3)
        if family:
            kw["family"] = family
        ax.text(tx, y + h / 2, text, **kw)


def arrow(ax, x0, y0, x1, y1, color=INK, lw=2.2, style="-|>"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                                                                    mutation_scale=18), zorder=5)


def text(ax, x, y, s, color=INK, size=18, ha="left", va="center", weight="normal", family=None, bg=None):
    kw = dict(color=color, fontsize=size, ha=ha, va=va, weight=weight, zorder=6, linespacing=1.35)
    if family:
        kw["family"] = family
    if bg:
        kw["bbox"] = dict(boxstyle="round,pad=0.3", fc=bg, ec=bg)
    return ax.text(x, y, s, **kw)


def summary(title, cols, h=560, note_line=None, pad=1.6):
    """외울 것 요약 그림. cols 는 [(제목, [줄...], 테두리 색)] 이고 왼쪽에서 오른쪽으로 화살표로 이음. pad 는 상자 안 글줄의 왼쪽 여백임."""
    plt, fig = new(h)
    ax = board(fig, h)
    text(ax, 2, h / 10 - 3.5, title, size=22, weight="bold")
    n = len(cols)
    gap = 3.0
    w = (108 - gap * (n - 1)) / n
    top, bottom = h / 10 - 8, 9 if note_line else 3
    for k, (head, lines, ec) in enumerate(cols):
        x = 2 + k * (w + gap)
        box(ax, x, bottom, w, top - bottom, fc="white", ec=ec, lw=2.6)
        text(ax, x + w / 2, top - 3.2, head, size=19, weight="bold", ha="center", color=ec if ec != LIGHT else INK)
        yy = top - 8
        for line in lines:
            code, math = line.startswith("`"), line.startswith("§")
            body = line.strip("`").lstrip("§")
            text(ax, x + pad, yy, body, size=15 if code else 17, family=CODE if code else (MATH if math else None), va="top")
            yy -= 4.6 * (body.count("\n") + 1)
        if k < n - 1:
            arrow(ax, x + w + 0.2, (top + bottom) / 2, x + w + gap - 0.2, (top + bottom) / 2, color=LIGHT, lw=2.6)
    if note_line:
        text(ax, 2, 4.5, note_line, size=17, bg=NOTE)
    return image(fig)


# 5a 레이어 함수와 모델

@figure("5a-1", 560, 300)
def names_5a():
    """5a 이름표 그림. 왼쪽은 [100, 784] 가 세 레이어 함수를 지나는 흐름, 오른쪽은 네 이름의 뜻."""
    plt, fig = new(600)
    ax = board(fig)
    rows = [("[100, 784]", "t"), ("nn.Linear(784, 128)", "f"), ("[100, 128]", "t"), ("nn.ReLU()", "f"),
            ("[100, 128]", "t"), ("nn.Linear(128, 10)", "f"), ("[100, 10]", "t")]
    y = 53
    for label, kind in rows:
        if kind == "t":
            box(ax, 6, y - 3, 22, 5.6, label, fc="white", ec=LIGHT, family=CODE, size=18)
        else:
            box(ax, 3, y - 3, 28, 5.6, label, fc=BLUE_L, ec=BLUE, color=BLUE, family=CODE, size=17)
            if "Linear" in label:
                text(ax, 32.5, y - 0.2, "weight, bias", color=PURPLE, size=16, family=CODE)
        if label != rows[-1][0] or kind != "t":
            arrow(ax, 17, y - 3.2, 17, y - 4.7, color=LIGHT, lw=1.8)
        y -= 8
    ax.plot([45.5, 46.5, 46.5, 45.5], [46.5, 46.5, 7.5, 7.5], color=INK, lw=2, zorder=3)
    text(ax, 47.5, 27, "모델\n(net)", size=18, weight="bold")
    text(ax, 58, 55, "이 단원의 이름표", size=21, weight="bold")
    tags = [(LIGHT, "텐서", "[100, 784] 처럼 모양이 있는 숫자 묶음"),
            (BLUE, "레이어 함수", "텐서를 받아 텐서를 돌려주는 함수"),
            (PURPLE, "파라미터", "레이어 함수 안에서 학습하며 바뀌는 값"),
            (INK, "모델", "레이어 함수를 차례로 이은 함수 하나")]
    yy = 46
    for color, name, desc in tags:
        box(ax, 58, yy - 2.6, 3.2, 5.2, fc="white" if color == LIGHT else color, ec=color, lw=2.4)
        text(ax, 63.5, yy + 0.6, name, size=20, weight="bold", color=INK if color == LIGHT else color)
        text(ax, 63.5, yy - 4.0, desc, size=17)
        yy -= 11.5
    return image(fig)


@figure("5a-2", 560, 300)
def shapes_5a():
    """[100, 784] 가 l1, relu, l2 를 지나며 바뀌는 모양. 5장은 입력 수가 틀린 층, 6장은 nn.Sequential 요약."""
    m1 = np.array([0.7, -1.2, 0.3, -0.4])
    m2 = np.maximum(m1, 0)
    assert m2.tolist() == [0.7, 0.0, 0.3, 0.0]
    widths = {"[100, 784]": 22, "[100, 128]": 13, "[100, 10]": 7}

    def draw(stage, title):
        plt, fig = new(600)
        ax = board(fig)
        text(ax, 2, 56.5, title, size=21, weight="bold")
        x = 2.0
        seq = [("t", "[100, 784]"), ("f", "l1 = nn.Linear(784, 128)"), ("t", "[100, 128]"), ("f", "relu = nn.ReLU()"),
               ("t", "[100, 128]"), ("f", "l2 = nn.Linear(128, 10)"), ("t", "[100, 10]")]
        upto = {1: 1, 2: 3, 3: 5, 4: 7, 5: 3, 6: 7}[stage]
        slots = []
        for k, (kind, label) in enumerate(seq[:upto]):
            if kind == "t":
                w = widths[label]
                hot = (k == upto - 1) and stage in (1, 2, 3, 4)
                box(ax, x, 26, w, 16, "", fc=HL if hot else "white", ec=LIGHT, lw=2.2)
                text(ax, x + w / 2, 22.5, label, size=17, family=CODE, ha="center")
                text(ax, x + w / 2, 34, "100\n행", size=15, ha="center", color=MUTED)
                slots.append((x, w))
                x += w + 1.0
            else:
                body = label.split(" = ")[1].replace("(", "\n(") if "Linear" in label else label.split(" = ")[1]
                box(ax, x, 30, 13, 8, body, fc=BLUE_L, ec=BLUE, color=BLUE, family=CODE, size=15)
                arrow(ax, x - 1.0, 34, x + 0.1, 34, color=LIGHT, lw=1.6)
                arrow(ax, x + 13.1, 34, x + 14.3, 34, color=LIGHT, lw=1.6)
                x += 14.5
        if stage == 1:
            text(ax, 27, 37, "데이터 100개, 하나에 값 784개\n(28 × 28 그림을 한 줄로 편 것)", size=18)
        if stage == 2:
            text(ax, 2, 12, "nn.Linear(784, 128) 은 마지막 축 784개를 128개로 바꿉니다. 첫 축 100 은 바뀌지 않습니다.", size=17,
                 bg=NOTE)
        if stage == 3:
            text(ax, 2, 14.5, "m1 한 행의 앞 네 값: [" + ", ".join(num(v, 1) for v in m1) + "]", size=17, family=CODE)
            text(ax, 2, 9.0, "ReLU 를 지난 m2:   [" + ", ".join(num(v, 1) for v in m2) + "]   모양은 [100, 128]", size=17,
                 family=CODE)
        if stage == 4:
            text(ax, 2, 12, "앞 층의 출력 수 128 과 다음 층의 입력 수 128 이 같아서 이어집니다.", size=17, bg=NOTE)
        if stage == 5:
            box(ax, x, 30, 13, 8, "nn.Linear\n(100, 10)", fc=RED_L, ec=RED, color=RED, family=CODE, size=15)
            arrow(ax, x - 1.0, 34, x + 0.1, 34, color=RED, lw=1.6)
            text(ax, x + 14.5, 34, "오류", size=20, color=RED, weight="bold")
            text(ax, 2, 12, "들어온 텐서의 마지막 축은 128 인데 이 층은 100 을 받습니다.", size=17, color=RED, bg=RED_L)
        if stage == 6:
            x0 = slots[0][0] + slots[0][1] + 0.5
            x1 = slots[-1][0] - 0.5
            ax.plot([x0, x0, x1, x1], [44, 46, 46, 44], color=INK, lw=2, zorder=3)
            text(ax, (x0 + x1) / 2, 48.5, "net2 = nn.Sequential(l1, relu, l2)", size=17, family=CODE, ha="center")
            text(ax, 2, 12, "net2(inputs) 한 줄이 세 줄과 같은 계산을 해서 [100, 10] 을 냅니다.", size=17, bg=NOTE)
        return image(fig)

    frames = [draw(1, "입력 inputs = torch.randn(100, 784)"), draw(2, "m1 = l1(inputs)"), draw(3, "m2 = relu(m1)"),
              draw(4, "outputs = l2(m2)"), draw(5, "입력 수가 맞지 않는 층"), draw(6, "세 함수를 한 모델로 묶기")]
    return frames, [2000, 2200, 2400, 2200, 2400, 2500]


@figure("5a-3", 560, 300)
def params_5a():
    """파라미터 세기. 왼쪽은 Linear(3, 2) 의 weight 6개와 bias 2개, 오른쪽은 784-128-10 모델의 표."""
    assert 3 * 2 + 2 == 8
    rows = [("nn.Linear(784, 128)", 784 * 128, 128), ("nn.ReLU()", 0, 0), ("nn.Linear(128, 10)", 128 * 10, 10)]
    total = sum(a + b for _, a, b in rows)
    assert total == 101770 and rows[0][1] + rows[0][2] == 100480 and rows[2][1] + rows[2][2] == 1290
    plt, fig = new(600)
    ax = board(fig)
    text(ax, 2, 56.5, "nn.Linear(3, 2) 에서 세기", size=21, weight="bold")
    ins = [(8, 44), (8, 30), (8, 16)]
    outs = [(30, 37), (30, 23)]
    for (xi, yi) in ins:
        for (xo, yo) in outs:
            ax.plot([xi, xo], [yi, yo], color=PURPLE, lw=2.2, zorder=2)
    for (xi, yi) in ins:
        ax.add_patch(plt.Circle((xi, yi), 2.6, fc="white", ec=LIGHT, lw=2.2, zorder=4))
    for k, (xo, yo) in enumerate(outs):
        ax.add_patch(plt.Circle((xo, yo), 2.6, fc="white", ec=LIGHT, lw=2.2, zorder=4))
        box(ax, xo + 4, yo - 1.8, 5, 3.6, "+b", fc=PURPLE_L, ec=PURPLE, color=PURPLE, size=15)
    text(ax, 2, 50, "입력 3개", size=17, color=MUTED)
    text(ax, 25, 50, "출력 2개", size=17, color=MUTED)
    text(ax, 2, 7, "weight 3 × 2 = 6개, bias 2개\n합 8개", size=18, color=PURPLE)
    text(ax, 48, 56.5, "784 → 128 → 10 모델", size=21, weight="bold")
    xs = [48, 76, 89, 100]
    for x, h in zip(xs, ["층", "weight", "bias", "합"]):
        text(ax, x, 48, h, size=18, weight="bold", color=PURPLE if h in ("weight", "bias") else INK)
    ax.plot([47, 111], [45.5, 45.5], color=FAINT, lw=1.4)
    yy = 41
    for name, a, b in rows:
        text(ax, 48, yy, name, size=16, family=CODE)
        for x, v in zip(xs[1:], [a, b, a + b]):
            text(ax, x, yy, comma(v), size=17)
        yy -= 7
    ax.plot([47, 111], [yy + 3.4, yy + 3.4], color=FAINT, lw=1.4)
    text(ax, 48, yy - 0.5, "모델 전체", size=17, weight="bold")
    text(ax, 100, yy - 0.5, comma(total), size=17, weight="bold")
    text(ax, 48, 9, "Linear 층 하나: 입력 수 × 출력 수 + 출력 수", size=17, bg=NOTE)
    return image(fig)


@figure("5a-4", 560, 280)
def memo_5a():
    """5a 외울 것 요약."""
    return summary("레이어 함수와 모델", [
        ("부품", ["레이어 함수: 텐서 → 텐서", "파라미터: weight, bias", "모델: 레이어 함수를 이은 것"], BLUE),
        ("모양", ["`[100, 784]`", "`→ Linear(784, 128)`", "`→ [100, 128]`", "`→ Linear(128, 10)`", "`→ [100, 10]`"], LIGHT),
        ("모델 클래스", ["`super().__init__()`", "`self.l1 = nn.Linear(…)`", "`def forward(self, x):`", "`    return …`"], INK)],
        note_line="파라미터 수: 입력 × 출력 + 출력. 784 → 128 → 10 은 101,770개입니다.")


# 5b 활성화 함수

@figure("5b-1", 560, 300)
def fold_5b():
    """은닉층 노드 둘(h1 = 2x + 1, h2 = −x + 3)을 Linear 층만으로 이으면 y = h1 + h2 − 1 = x + 3 직선 하나."""
    xs = np.array([-3, 5.0])
    for xv in (1, 2):
        h1, h2 = 2 * xv + 1, -xv + 3
        assert h1 + h2 - 1 == xv + 3
    plt, fig = new(600)
    ax = fig.add_axes([0.08, 0.13, 0.46, 0.80])
    tidy(ax)
    ax.set_xlim(-3, 5)
    ax.set_ylim(-6, 12)
    ax.set_xlabel("x")
    ax.axhline(0, color=FAINT, lw=1.2)
    ax.axvline(0, color=FAINT, lw=1.2)
    ax.plot(xs, 2 * xs + 1, color=BLUE, lw=2.0, ls="--")
    ax.plot(xs, -xs + 3, color=BLUE, lw=2.0, ls=":")
    ax.plot(xs, xs + 3, color=BLUE, lw=3.4)
    for xv in (1, 2):
        ax.scatter([xv], [xv + 3], s=110, color=INK, zorder=5)
        ax.text(xv + 0.15, xv + 3 - 1.6, "(%d, %d)" % (xv, xv + 3), fontsize=17)
    ax.text(4.9, 11.0, "h1", fontsize=17, color=BLUE, ha="right")
    ax.text(4.9, -1.2, "h2", fontsize=17, color=BLUE, ha="right")
    ax.text(4.9, 6.5, "y", fontsize=19, color=BLUE, ha="right", weight="bold")
    bd = board(fig)
    lines = [("h1 = 2x + 1", INK), ("h2 = " + M + "x + 3", INK), ("y = h1 + h2 " + M + " 1", INK),
             ("  = (2x + 1) + (" + M + "x + 3) " + M + " 1", INK), ("  = x + 3", BLUE)]
    yy = 54
    for k, (t, c) in enumerate(lines):
        text(bd, 63, yy, t, size=20, color=c, weight="bold" if k == 4 else "normal")
        yy -= 6.5
    text(bd, 61, 15, "은닉층 노드가 둘이어도 Linear 층만 이으면\n직선 하나와 같은 함수입니다.", size=17, bg=NOTE)
    return image(fig)


@figure("5b-2", 560, 300)
def relu_5b():
    """은닉층 노드마다 ReLU 를 넣으면 꺾이는 자리가 생김. 1장 두 노드의 ReLU, 2장 더한 y, 3장 꺾인 토막으로 x² 따라가기."""
    xs = np.linspace(-3, 5, 801)
    r1, r2 = np.maximum(2 * xs + 1, 0), np.maximum(-xs + 3, 0)
    yv = r1 + r2 - 1
    f = lambda x: max(0, 2 * x + 1) + max(0, -x + 3) - 1
    assert f(-2) == 4 and f(1) == 4 and f(4) == 8 and f(-0.5) == 2.5 and f(3) == 6
    knots = np.arange(-3, 4)
    xq = np.linspace(-3, 3, 601)
    piece = np.interp(xq, knots, knots ** 2.0)

    def draw(stage):
        plt, fig = new(600)
        ax = fig.add_axes([0.08, 0.13, 0.52, 0.72])
        tidy(ax)
        ax.set_xlim(-3, 5)
        ax.set_ylim(-2, 12)
        ax.set_xlabel("x")
        ax.axhline(0, color=FAINT, lw=1.2)
        ax.axvline(0, color=FAINT, lw=1.2)
        bd = board(fig)
        if stage == 1:
            ax.plot(xs, r1, color=GREEN, lw=3.0, ls="--")
            ax.plot(xs, r2, color=GREEN, lw=3.0, ls=":")
            note = ["ReLU(h1): x = " + M + "0.5 에서 꺾임", "ReLU(h2): x = 3 에서 꺾임"]
            head = "노드마다 ReLU 를 지나면"
        elif stage == 2:
            ax.plot(xs, xs + 3, color=BLUE_M, lw=2.4, ls="--")
            ax.plot(xs, yv, color=GREEN, lw=3.4)
            ax.scatter([-2, 1, 4], [4, 4, 8], s=110, color=INK, zorder=5)
            for xv in (-0.5, 3):
                ax.axvline(xv, color=MUTED, lw=1.4, ls=":")
            note = ["y = ReLU(h1) + ReLU(h2) " + M + " 1", "x = " + M + "2 → y = 4", "x = 1 → y = 4", "x = 4 → y = 8"]
            head = "더하면 두 곳에서 꺾인 선"
        else:
            ax.set_xlim(-3, 3)
            ax.set_ylim(-1, 10)
            ax.plot(xq, xq ** 2, color=MUTED, lw=2.2, ls="--")
            ax.plot(xq, piece, color=GREEN, lw=3.2)
            ax.scatter(knots, knots ** 2.0, s=60, color=GREEN, zorder=5)
            note = ["꺾이는 자리 5곳", "토막 6개", "회색 점선:", "§y = x²"]
            head = "꺾이는 자리를 늘리면 곡선에 가까워짐"
        text(bd, 2, 57, head, size=21, weight="bold")
        yy = 47
        for s in note:
            text(bd, 70, yy, s.lstrip("§"), size=18, family=MATH if s.startswith("§") else None)
            yy -= 7
        return image(fig)

    return [draw(1), draw(2), draw(3)], [2400, 2400, 2500]


def _data_5b():
    np.random.seed(123)
    x = np.random.randn(100, 1) * 2.5
    y = x ** 2 + np.random.randn(100, 1) * 0.8
    return x[:50, 0], y[:50, 0], x[50:, 0], y[50:, 0], (x.min(), x.max())


def _relu_net(xtr, ytr, seed=2, epochs=1000, lr=0.01):
    """노트북 Net3(1-10-10-1, 층 사이 ReLU) 를 numpy 로 같은 설정(MSE, lr 0.01, 1000번, 전체 배치)으로 학습."""
    rng = np.random.default_rng(seed)

    def lin(i, o):
        k = 1 / math.sqrt(i)
        return rng.uniform(-k, k, (i, o)), rng.uniform(-k, k, o)
    W1, b1 = lin(1, 10)
    W2, b2 = lin(10, 10)
    W3, b3 = lin(10, 1)
    X, Y = xtr[:, None], ytr[:, None]
    n = len(X)
    for _ in range(epochs):
        z1 = X @ W1 + b1
        a1 = np.maximum(z1, 0)
        z2 = a1 @ W2 + b2
        a2 = np.maximum(z2, 0)
        g = 2 * (a2 @ W3 + b3 - Y) / n
        gW3, gb3 = a2.T @ g, g.sum(0)
        g2 = (g @ W3.T) * (z2 > 0)
        gW2, gb2 = a1.T @ g2, g2.sum(0)
        g1 = (g2 @ W2.T) * (z1 > 0)
        gW1, gb1 = X.T @ g1, g1.sum(0)
        for p, gp in ((W1, gW1), (b1, gb1), (W2, gW2), (b2, gb2), (W3, gW3), (b3, gb3)):
            p -= lr * gp

    def f(v):
        a1 = np.maximum(v[:, None] @ W1 + b1, 0)
        a2 = np.maximum(a1 @ W2 + b2, 0)
        return (a2 @ W3 + b3)[:, 0]
    return f


@figure("5b-3", 560, 300)
def experiment_5b():
    """노트북 01 4.7절 자료(시드 123)의 뒤 50개에서 예측과 정답. 왼쪽은 직선(Net·Net2), 오른쪽은 ReLU 모델(Net3)."""
    xtr, ytr, xte, yte, (lo, hi) = _data_5b()
    A = np.stack([xtr, np.ones_like(xtr)], 1)
    coef = np.linalg.lstsq(A, ytr, rcond=None)[0]
    mse = float(((A @ coef - ytr) ** 2).mean())
    assert f"{mse:.4f}" == "125.3143" and f"{coef[0]:.4f}" == "0.1285" and f"{coef[1]:.4f}" == "8.9372"
    assert f"{lo:.1f}" == "-7.0" and f"{hi:.1f}" == "6.0"
    net = _relu_net(xtr, ytr)
    net_mse = float(((net(xtr) - ytr) ** 2).mean())
    assert 4.0 < net_mse < 8.0
    plt, fig = new(600)
    for k, (title, pred, color) in enumerate([("활성화 함수 없음 (Net, Net2)", coef[0] * xte + coef[1], BLUE),
                                              ("층 사이에 ReLU (Net3)", net(xte), GREEN)]):
        ax = fig.add_axes([0.07 + k * 0.49, 0.13, 0.42, 0.68])
        tidy(ax)
        ax.set_xlim(-7.5, 6.5)
        ax.set_ylim(-5, 55)
        ax.set_xlabel("x")
        ax.set_title(title, fontsize=19, color=color, loc="left")
        ax.scatter(xte, yte, marker="x", s=60, color=INK, lw=2, zorder=4)
        ax.scatter(xte, pred, s=45, color=color, zorder=5)
    fig.text(0.07, 0.95, "검은 x 는 정답, 점은 예측 (뒤 50개 자료)", fontsize=18, color=INK, va="center")
    return image(fig)


@figure("5b-4", 560, 280)
def memo_5b():
    return summary("활성화 함수가 필요한 까닭", [
        ("Linear 만 이으면", ["h1 = 2x + 1", "h2 = " + M + "x + 3", "y = h1 + h2 " + M + " 1", "→ y = x + 3, 직선"], BLUE),
        ("ReLU 를 넣으면", ["ReLU(h1) + ReLU(h2) " + M + " 1", "x = " + M + "0.5, 3 에서 꺾임", "토막을 이어 곡선을 따라감"],
         GREEN),
        ("제곱 자료 실험", ["Net, Net2: 직선 예측", "Net3(ReLU): 곡선 예측", "활성화 함수의 목적:", "비선형성"], INK)],
        note_line="Linear 층 사이의 ReLU 가 비선형성을 더합니다.")


# 5c 기울기 소실·폭발과 가중치 초기화

@figure("5c-1", 560, 300)
def saved_5c():
    """Linear 입력과 설명용 ReLU 마스크의 역전파 사용을 나타냄."""
    z = np.array([1.5, -0.5, 2.0])
    g = np.array([0.4, 0.3, -0.2])
    mask = z > 0
    assert mask.tolist() == [True, False, True] and (g * mask).tolist() == [0.4, 0.0, -0.2]
    vec = lambda v: "[" + ", ".join(f"{t:.1f}".replace("-", M) for t in v) + "]"
    plt, fig = new(600)
    ax = board(fig)
    text(ax, 2, 56.5, "입력과 양수 위치를 역전파에 씁니다", size=21, weight="bold")
    xs = [2, 30, 58, 86]
    labels = [("입력 x", ""), ("Linear", "z = " + vec(z)), ("ReLU", "a = " + vec(np.maximum(z, 0))), ("손실", "")]
    for x, (name, val) in zip(xs, labels):
        box(ax, x, 38, 22, 9, name, fc="white", ec=LIGHT, size=19)
        if val:
            text(ax, x + 11, 51, val, size=16, ha="center", color=BLUE, family=CODE)
    for x in xs[:-1]:
        arrow(ax, x + 22.3, 44.5, x + 27.7, 44.5, color=BLUE, lw=2.6)
        arrow(ax, x + 27.7, 40.5, x + 22.3, 40.5, color=ORANGE, lw=2.6)
    box(ax, 30, 25, 22, 8, "저장: 입력 x", fc=PURPLE_L, ec=PURPLE, color=PURPLE, size=17)
    box(ax, 58, 25, 22, 8, "설명용 마스크\n[True, False, True]", fc=PURPLE_L, ec=PURPLE, color=PURPLE, size=15)
    text(ax, 2, 15, "뒤에서 온 기울기 " + vec(g) + " 가 ReLU 를 지나면 " + vec(g * mask), size=17, color=ORANGE,
         family=CODE)
    text(ax, 2, 8, "weight 의 기울기는 뒤에서 온 기울기와 저장한 입력 x 로 계산합니다.", size=17, bg=NOTE)
    return image(fig)


@figure("5c-2", 560, 300)
def vanish_5c():
    """층을 지날 때마다 같은 수를 곱한 기울기 크기. 2장 0.9, 3장 0.25(시그모이드 미분의 최댓값), 4장 1.1, 5장 요약."""
    ks = np.arange(11)
    r09, r25, r11 = 0.9 ** ks, 0.25 ** ks, 1.1 ** ks
    assert f"{r09[-1]:.4f}" == "0.3487" and f"{r11[-1]:.4f}" == "2.5937" and f"{1.1 ** 100:.1f}" == "13780.6"
    assert f"{0.25 ** 5:.6f}" == "0.000977"

    def draw(stage):
        plt, fig = new(600)
        if stage < 5:
            ax = fig.add_axes([0.08, 0.14, 0.55, 0.72])
            tidy(ax)
            ax.set_xlim(-0.7, 10.7)
            ax.set_ylim(0, 3)
            ax.set_xticks(range(11))
            ax.set_xlabel("출력 쪽에서 거꾸로 지난 층 수")
            ax.set_ylabel("기울기 크기(처음 = 1)")
            ax.axhline(1, color=FAINT, lw=1.4, ls="--")
            if stage == 1:
                ax.bar([0], [1], color=ORANGE, width=0.7)
                head, lines = "역전파는 층마다 미분값을 곱합니다", ["출력 쪽 기울기를", "1 로 둡니다."]
            elif stage == 2:
                ax.bar(ks, r09, color=ORANGE, width=0.7)
                ax.text(10, r09[-1] + 0.08, num(r09[-1], 4), ha="center", fontsize=16)
                head, lines = "층마다 0.9 를 곱하면", ["§0.9¹⁰ = 0.3487", "10층 앞에서", "35% 쯤 남음"]
            elif stage == 3:
                ax.bar(ks, r25, color=ORANGE, width=0.7)
                for k, x, y, ha in ((1, 1, r25[1] + 0.08, "center"), (2, 1.72, r25[2] + 0.08, "left"), (3, 2.72, r25[3] + 0.33, "left")):
                    ax.text(x, y, num(r25[k], 4), ha=ha, fontsize=15)
                head, lines = "층마다 0.25 를 곱하면", ["0.25 × 0.25 = 0.0625", "§0.25⁵ = 0.00098", "0.25 는 시그모이드", "미분값의 가장 큰 값"]
            else:
                ax.bar(ks, r11, color=ORANGE, width=0.7)
                ax.text(10, r11[-1] + 0.08, num(r11[-1], 4), ha="center", fontsize=16)
                head, lines = "층마다 1.1 을 곱하면", ["§1.1¹⁰ = 2.5937", "100층이면 13,780.6배"]
            fig.text(0.015, 0.94, head, fontsize=21, weight="bold", va="center")
            yy = 0.78
            for s in lines:
                fig.text(0.67, yy, s.lstrip("§"), fontsize=18, va="center", family=MATH if s.startswith("§") else None)
                yy -= 0.10
        else:
            fig.text(0.015, 0.94, "곱하는 수가 1 보다 작으면 소실, 크면 폭발", fontsize=21, weight="bold", va="center")
            assert num(r25[-1], 8) == "0.00000095"
            for k, (r, vals, name) in enumerate([(0.9, r09, "0.9배씩"), (0.25, r25, "0.25배씩"), (1.1, r11, "1.1배씩")]):
                ax = fig.add_axes([0.06 + k * 0.32, 0.16, 0.27, 0.62])
                tidy(ax)
                ax.set_ylim(0, 3)
                ax.set_xticks([0, 5, 10])
                ax.bar(ks, vals, color=ORANGE, width=0.7)
                ax.set_title(name, fontsize=17, loc="left", pad=12)
                ax.text(0.04, 0.96, "10층 뒤\n" + num(vals[-1], 4 if r != 0.25 else 8), transform=ax.transAxes, linespacing=1.5, fontsize=15,
                        ha="left", va="top")
        return image(fig)

    return [draw(1), draw(2), draw(3), draw(4), draw(5)], [2000, 2200, 2400, 2200, 2500]


def _init_runs():
    """Linear(256, 256)(편향 0)과 ReLU 를 10번. 입력은 표준편차 1 인 데이터 1000개. 층마다 출력의 표준편차."""
    rng = np.random.default_rng(0)
    x0 = rng.standard_normal((1000, 256))
    out = {}
    for name, std in (("0.01", 0.01), ("Xavier", math.sqrt(2 / 512)), ("He", math.sqrt(2 / 256))):
        r = np.random.default_rng(1)
        a, rows = x0, []
        for _ in range(10):
            a = np.maximum(a @ (r.standard_normal((256, 256)) * std), 0)
            rows.append(float(a.std()))
        out[name] = rows
    return out


@figure("5c-3", 560, 300)
def init_5c():
    """처음 가중치의 표준편차에 따라 층을 지날 때 출력이 얼마나 퍼지는지(세로축은 눈금마다 10배)."""
    runs = _init_runs()
    assert runs["0.01"][-1] < 1e-9 and 0.015 < runs["Xavier"][-1] < 0.03 and 0.6 < runs["He"][-1] < 1.1
    assert f"{math.sqrt(2 / 256):.4f}" == "0.0884" and f"{math.sqrt(2 / 512):.4f}" == "0.0625"
    plt, fig = new(600)
    ax = fig.add_axes([0.115, 0.14, 0.555, 0.74])
    tidy(ax)
    ax.set_yscale("log")
    ax.set_xlim(0.5, 10.5)
    ax.set_ylim(1e-11, 3)
    ax.set_yticks([10.0 ** p for p in (-10, -8, -6, -4, -2, 0)])
    ax.set_yticklabels(["10⁻¹⁰", "10⁻⁸", "10⁻⁶", "10⁻⁴", "10⁻²", "1"], family=MATH)
    ax.minorticks_off()
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("층 번호")
    ax.set_ylabel("출력의 표준편차", labelpad=10)
    layers = np.arange(1, 11)
    for name, color in (("0.01", RED), ("Xavier", MUTED), ("He", GREEN)):
        ax.plot(layers, runs[name], color=color, lw=3, marker="o", ms=7)
    fig.text(0.015, 0.95, "Linear(256, 256)과 ReLU 10층에서 처음 가중치에 따른 출력 크기", fontsize=20, weight="bold", va="center")
    rows = [(RED, "표준편차 0.01", "≈ 2.6 × 10⁻¹⁰"), (MUTED, "Xavier 0.0625", "≈ " + num(runs["Xavier"][-1], 3)),
            (GREEN, "He 0.0884", "≈ " + num(runs["He"][-1], 2))]
    assert f"{runs['0.01'][-1]:.1e}" == "2.6e-10" and num(runs["Xavier"][-1], 3) == "0.023" and num(runs["He"][-1], 2) == "0.75"
    fig.text(0.70, 0.84, "10층 뒤 표준편차", fontsize=17, color=MUTED, va="center")
    yy = 0.74
    for color, a, b in rows:
        fig.text(0.70, yy, a, fontsize=19, color=color, weight="bold", va="center")
        fig.text(0.70, yy - 0.07, b, fontsize=17, va="center", family=MATH)
        yy -= 0.19
    fig.text(0.70, 0.15, "세로축 값은 눈금 하나마다\n10배씩 커집니다.", linespacing=1.5, fontsize=16, color=MUTED, va="center")
    return image(fig)


@figure("5c-4", 560, 280)
def memo_5c():
    return summary("기울기 소실·폭발과 가중치 초기화", [
        ("층마다 곱해짐", ["§0.9¹⁰ = 0.3487", "§0.25⁵ = 0.00098", "§1.1¹⁰⁰ = 13,780.6", "작으면 소실, 크면 폭발"], ORANGE),
        ("줄이는 방법", ["ReLU", "He 초기화", "배치 정규화", "잔차 연결", "hook 은 보는 도구"], INK),
        ("초기화", ["Xavier 표준편차", "§  √(2 ÷ (n_in + n_out))", "He 표준편차", "§  √(2 ÷ n_in)", "`kaiming_normal_`", "`xavier_normal_`"], GREEN)],
        note_line="순전파는 Linear 의 입력과 ReLU 마스크를 저장하고, 역전파가 그 값으로 기울기를 구합니다.")


# 5d 경사하강법의 세 갈래와 미니배치

X5 = np.array([-5, 5, 0, 2, -2.0])
Y5 = np.array([-6.7, 10.3, -3.3, 5.0, -5.3])


def _loss5(W, B):
    W = np.asarray(W, float)[..., None]
    B = np.asarray(B, float)[..., None]
    return (((W * X5 + B) - Y5) ** 2).mean(-1)


def _paths(epochs=10, lr=0.02):
    """4차시 다섯 사람 자료. 배치 경사하강법, SGD(사람 1부터 차례로), 2명씩 미니배치의 갱신 경로와 에폭 끝 점."""
    out = {}
    for name, batches in (("batch", [[0, 1, 2, 3, 4]]), ("sgd", [[0], [1], [2], [3], [4]]), ("mini", [[0, 1], [2, 3], [4]])):
        W, B = 1.0, 1.0
        pts, ends = [(W, B)], [(W, B)]
        for _ in range(epochs):
            for idx in batches:
                e = W * X5[idx] + B - Y5[idx]
                W, B = W - lr * 2 * (e * X5[idx]).mean(), B - lr * 2 * e.mean()
                pts.append((W, B))
            ends.append((W, B))
        out[name] = (np.array(pts), np.array(ends), len(batches))
    return out


@figure("5d-1", 560, 300)
def paths_5d():
    """같은 학습률 0.02 로 10 에폭 동안의 경로. 파랑 배치, 주황 SGD, 초록 2명씩 미니배치."""
    paths = _paths()
    end = {k: v[1] for k, v in paths.items()}
    assert f"{end['batch'][1][0]:.3f}" == "1.381" and f"{end['sgd'][1][0]:.3f}" == "2.099"
    assert f"{end['mini'][1][0]:.3f}" == "1.948"
    L10 = {k: float(_loss5(*v[10])) for k, v in end.items()}
    assert f"{L10['batch']:.2f}" == "4.98" and f"{L10['sgd']:.2f}" == "5.93" and f"{L10['mini']:.2f}" == "4.64"
    allp = np.concatenate([v[0] for v in paths.values()])
    assert allp[:, 0].min() > 0.9 and allp[:, 0].max() < 2.6 and allp[:, 1].min() > -0.6 and allp[:, 1].max() < 1.3
    wg, bg = np.meshgrid(np.linspace(0.9, 2.6, 160), np.linspace(-0.6, 1.3, 160))
    Lg = _loss5(wg, bg)
    colors = {"batch": BLUE, "sgd": ORANGE, "mini": GREEN}
    names = {"batch": "배치(5명)", "sgd": "SGD(1명씩)", "mini": "미니배치(2명씩)"}

    def draw(ep, title):
        plt, fig = new(600)
        ax = fig.add_axes([0.10, 0.13, 0.52, 0.76])
        tidy(ax, grid=False)
        ax.set_xlim(0.9, 2.6)
        ax.set_ylim(-0.6, 1.3)
        ax.set_xlabel("W")
        ax.set_ylabel("B")
        cs = ax.contour(wg, bg, Lg, levels=[4.6, 5, 6, 7.5, 10, 13], colors=LIGHT, linewidths=1.3)
        # 오른쪽 위 구석의 13 등고선은 짧아서 숫자가 축 밖으로 잘리니 왼쪽 13 에만 숫자를 붙임
        ax.clabel(cs, fontsize=15, fmt="%g", manual=[(1.765, -0.158), (1.625, 0.129), (2.146, -0.481), (1.317, 0.153),
                                                    (2.32, -0.265), (1.135, 0.021), (2.472, 0.738), (0.971, 0.308)])
        ax.scatter([1], [1], s=120, color=INK, zorder=6)
        ax.scatter([105.6 / 58], [0], s=320, marker="*", color=INK, zorder=6)
        for key, z, lw in (("mini", 3, 2.2), ("sgd", 4, 2.2), ("batch", 5, 3.4)):
            pts, ends, per = paths[key]
            upto = 1 + ep * per
            ax.plot(pts[:upto, 0], pts[:upto, 1], color=colors[key], lw=lw, marker="o", ms=4 if key != "batch" else 6, zorder=z)
        fig.text(0.015, 0.95, title, fontsize=21, weight="bold", va="center")
        yy = 0.80
        for key in ("batch", "sgd", "mini"):
            pts, ends, per = paths[key]
            fig.text(0.65, yy, names[key], fontsize=18, color=colors[key], weight="bold", va="center")
            if ep:
                fig.text(0.65, yy - 0.065, "갱신 %d번, 손실 %s" % (ep * per, num(float(_loss5(*ends[ep])), 2)), fontsize=17,
                         va="center")
            else:
                fig.text(0.65, yy - 0.065, "한 에폭에 %d번 갱신" % per, fontsize=17, va="center")
            yy -= 0.19
        fig.text(0.65, 0.17, "검은 점: 시작 (1, 1)\n별: 손실이 가장 작은 곳", linespacing=1.5, fontsize=16, color=MUTED, va="center")
        return image(fig)

    frames = [draw(0, "같은 학습률 0.02 로 시작"), draw(1, "1 에폭 뒤"), draw(2, "2 에폭 뒤"), draw(5, "5 에폭 뒤"),
              draw(10, "10 에폭 뒤")]
    return frames, [2200, 2400, 2200, 2200, 2500]


@figure("5d-2", 560, 300)
def batches_5d():
    """훈련 데이터 800개를 배치 크기로 나눈 모습과 갱신 횟수 표. 상자마다 배치 하나를 그림. 초록은 꽉 찬 배치, 노랑은 마지막 배치."""
    rows = []
    for b in (8, 32, 128, 512):
        nb = -(-800 // b)
        rows.append((b, nb, 800 - (nb - 1) * b, 5 * nb))
    assert rows == [(8, 100, 8, 500), (32, 25, 32, 125), (128, 7, 32, 35), (512, 2, 288, 10)]
    plt, fig = new(600)
    ax = board(fig)
    text(ax, 2, 56.5, "데이터 800개를 묶음으로 나누기", size=21, weight="bold")
    for k, b in enumerate((128, 512)):
        y = 44 - k * 13
        text(ax, 2, y + 7.0, "배치 크기 %d" % b, size=18, weight="bold")
        x = 2.0
        scale = 60 / 800
        left = 800
        n = 0
        while left > 0:
            size = min(b, left)
            last = size < b or left == size
            fc = HL if (left == size) else GREEN_L
            narrow = size * scale < 4
            box(ax, x, y - 2.5, size * scale - 0.3, 5, "" if narrow else str(size), fc=fc, ec=GREEN, color=INK, size=15, lw=1.6)
            if narrow:
                text(ax, x + size * scale + 0.4, y, str(size), size=15)
            x += size * scale
            left -= size
            n += 1
    xs = [68, 82, 92, 102]
    for x, h in zip(xs, ["배치 크기", "에폭당", "마지막", "5 에폭"]):
        text(ax, x, 50, h, size=16, weight="bold")
    text(ax, 82, 46.5, "갱신", size=16, weight="bold")
    text(ax, 92, 46.5, "배치", size=16, weight="bold")
    text(ax, 102, 46.5, "갱신", size=16, weight="bold")
    ax.plot([67, 111], [44, 44], color=FAINT, lw=1.4)
    yy = 39.5
    for b, nb, last, total in rows:
        for x, v in zip(xs, (b, nb, last, total)):
            text(ax, x, yy, str(v), size=17)
        yy -= 6
    text(ax, 2, 9, "배치 수는 800 ÷ 배치 크기를 올림한 값입니다. 노랑은 남은 데이터만 든 마지막 배치입니다.", size=17, bg=NOTE)
    return image(fig)


@figure("5d-3", 560, 280)
def memo_5d():
    return summary("경사하강법의 세 갈래와 미니배치", [
        ("한 번 갱신에 쓰는 데이터", ["배치 경사하강법: 전체", "SGD: 하나", "미니배치: 작은 묶음"], INK),
        ("한 에폭의 갱신 횟수", ["N ÷ 배치 크기를 올림", "800 ÷ 32 = 25", "800 ÷ 128 → 7", "마지막 배치 32개"], GREEN),
        ("코드", ["`TensorDataset(x, y)`", "`DataLoader(dataset,`", "`  batch_size=32,`", "`  shuffle=True)`",
                 "`len(dataloader) == 25`"], INK)],
        note_line="같은 에폭 수면 배치 크기가 작을수록 갱신을 더 많이 합니다(배치 크기 8: 500번, 512: 10번).")


# 5e 학습률과 스케줄러

@figure("5e-1", 560, 300)
def lr_5e():
    """L = w², w = 4 에서 학습률 0.01, 0.45, 1.1 로 갱신. 1~6장은 갱신 0~5번, 7장은 요약."""
    seqs = {}
    for lr in (0.01, 0.45, 1.1):
        w, seq = 4.0, [4.0]
        for _ in range(5):
            w = w - lr * 2 * w
            seq.append(w)
        seqs[lr] = seq
    assert num(seqs[0.01][1], 4) == "3.92" and num(seqs[0.45][1], 4) == "0.4" and num(seqs[1.1][1], 4) == M + "4.8"
    assert num(seqs[1.1][2], 4) == "5.76" and num(seqs[1.1][5], 5) == M + "9.95328" and num(seqs[0.01][5], 4) == "3.6157"
    ws = np.linspace(-10.5, 10.5, 400)

    def draw(k, title):
        plt, fig = new(600)
        fig.text(0.015, 0.95, title, fontsize=21, weight="bold", va="center")
        fig.text(0.97, 0.95, "L = w²", fontsize=20, va="center", ha="right", family=MATH)
        for c, lr in enumerate((0.01, 0.45, 1.1)):
            ax = fig.add_axes([0.085 + c * 0.315, 0.14, 0.26, 0.66])
            tidy(ax)
            ax.set_xlim(-10.5, 10.5)
            ax.set_ylim(-3, 110)
            ax.set_xlabel("w")
            ax.plot(ws, ws ** 2, color=MUTED, lw=2)
            seq = np.array(seqs[lr][:k + 1])
            if k:
                ax.plot(seq, seq ** 2, color=LIGHT, lw=1.4, marker="o", ms=6, zorder=3)
            ax.scatter([seq[-1]], [seq[-1] ** 2], s=130, color=INK, zorder=5)
            ax.set_title("학습률 %s" % num(lr, 2), fontsize=19, loc="left")
            if c == 0:
                ax.set_ylabel("L")
            ax.text(0.5, 0.97, "w = " + num(seq[-1], 5), transform=ax.transAxes, fontsize=17, va="top", ha="center")
        return image(fig)

    frames = [draw(0, "w = 4 에서 시작")] + [draw(k, "%d번 갱신한 뒤" % k) for k in (1, 2, 3, 4, 5)]
    return frames, [2000, 2200, 2000, 2000, 2000, 2500]


def _step(e, lr0=0.1, step=10, gamma=0.1):
    return lr0 * gamma ** (e // step)


def _multistep(e, lr0=0.1, miles=(15, 30), gamma=0.1):
    return lr0 * gamma ** sum(1 for m in miles if e >= m)


@figure("5e-2", 560, 300)
def steps_5e():
    """에폭마다 step() 을 부를 때 StepLR, MultiStepLR, ExponentialLR 의 학습률(0~40 에폭, 처음 0.1)."""
    es = np.arange(41)
    assert [round(_step(e), 6) for e in (0, 9, 10, 20, 25, 30)] == [0.1, 0.1, 0.01, 0.001, 0.001, 0.0001]
    assert f"{0.1 * 0.9 ** 10:.4f}" == "0.0349"
    plt, fig = new(600)
    ax = fig.add_axes([0.105, 0.14, 0.555, 0.74])
    tidy(ax)
    ax.set_xlim(0, 40)
    ax.set_ylim(0, 0.105)
    ax.set_xlabel("step() 을 부른 횟수(에폭)")
    ax.set_ylabel("학습률", labelpad=10)
    ax.step(es, [_step(e) for e in es], where="post", color=BLUE, lw=3)
    ax.step(es, [_multistep(e) for e in es], where="post", color=PURPLE, lw=2.6, ls="--")
    ax.plot(es, 0.1 * 0.9 ** es, color=GREEN, lw=2.6)
    fig.text(0.015, 0.95, "처음 학습률 0.1 에서 줄이는 세 방법", fontsize=21, weight="bold", va="center")
    rows = [(BLUE, "StepLR", "10번마다 0.1배", "0.1 → 0.01 → 0.001"), (PURPLE, "MultiStepLR", "15번째, 30번째에 0.1배", ""),
            (GREEN, "ExponentialLR", "부를 때마다 0.9배", "10번 뒤 0.0349")]
    yy = 0.80
    for color, name, a, b in rows:
        fig.text(0.69, yy, name, fontsize=18, color=color, weight="bold", va="center")
        fig.text(0.69, yy - 0.065, a, fontsize=16, va="center")
        if b:
            fig.text(0.69, yy - 0.12, b, fontsize=16, va="center")
        yy -= 0.24
    return image(fig)


def _onecycle(total=1175, max_lr=3e-3, div=25.0, final_div=1e4, pct=0.3):
    """PyTorch OneCycleLR 기본값(cos, 두 구간)의 학습률. step 번호 0..total-1."""
    init = max_lr / div
    low = init / final_div
    end1 = float(pct * total) - 1
    end2 = total - 1
    out = []
    for s in range(total):
        if s <= end1:
            p, a, b = s / end1, init, max_lr
        else:
            p, a, b = (s - end1) / (end2 - end1), max_lr, low
        out.append(b + (a - b) / 2 * (1 + math.cos(math.pi * p)))
    return np.array(out)


@figure("5e-3", 560, 300)
def cosine_5e():
    """왼쪽 CosineAnnealingLR(T_max=40, 처음 0.1) 의 10 에폭 구간별 감소량, 오른쪽 노트북 02 의 OneCycleLR."""
    cos = lambda e: 0.1 * (1 + math.cos(math.pi * e / 40)) / 2
    drops = [cos(e) - cos(e + 10) for e in (0, 10, 20, 30)]
    assert [f"{d:.4f}" for d in drops] == ["0.0146", "0.0354", "0.0354", "0.0146"]
    assert [f"{cos(e):.4f}" for e in (0, 10, 20, 30, 40)] == ["0.1000", "0.0854", "0.0500", "0.0146", "0.0000"]
    oc = _onecycle()
    assert len(oc) == 5 * 235 and abs(oc[0] - 1.2e-4) < 1e-12 and abs(oc.max() - 3e-3) < 1e-7 and int(oc.argmax()) in (351, 352)
    assert oc[-1] < 1e-7
    plt, fig = new(600)
    ax = fig.add_axes([0.10, 0.14, 0.38, 0.70])
    tidy(ax)
    es = np.linspace(0, 40, 200)
    ax.plot(es, [cos(e) for e in es], color=ORANGE, lw=3)
    ax.set_xlim(0, 40)
    ax.set_ylim(0, 0.105)
    ax.set_xticks([0, 10, 20, 30, 40])
    ax.set_xlabel("에폭")
    ax.set_ylabel("학습률", labelpad=10)
    for k, e in enumerate((0, 10, 20, 30)):
        ax.plot([e + 10, e + 10], [cos(e + 10), cos(e)], color=INK, lw=1.4, ls=":")
        ax.text(e + 10.6, (cos(e) + cos(e + 10)) / 2, M + num(drops[k], 4), ha="left", va="center", fontsize=15)
    ax.set_title("CosineAnnealingLR(T_max=40)", fontsize=18, loc="left", color=ORANGE)
    bx = fig.add_axes([0.60, 0.14, 0.37, 0.70])
    tidy(bx)
    bx.plot(np.arange(len(oc)), oc * 1000, color=RED, lw=3)
    bx.set_xlim(0, 1175)
    bx.set_ylim(0, 3.2)
    bx.set_xlabel("sched.step() 횟수")
    bx.set_ylabel("학습률(× 0.001)", labelpad=10)
    bx.set_title("OneCycleLR(노트북 02)", fontsize=18, loc="left", color=RED)
    bx.text(352, 3.05, "약 352번째에 0.003", fontsize=15, ha="center")
    bx.scatter([0], [oc[0] * 1000], s=50, color=RED, zorder=5, clip_on=False)
    bx.text(60, 0.06, "시작 0.00012", fontsize=15, va="bottom")
    fig.text(0.015, 0.95, "처음과 끝은 천천히, 가운데는 빠르게 / 올렸다가 내리기", fontsize=20, weight="bold", va="center")
    return image(fig)


@figure("5e-4", 560, 280)
def memo_5e():
    return summary("학습률과 스케줄러", [
        ("학습률 크기", ["§L = w², w = 4", "0.01: 3.92 (느림)", "0.45: 0.4 (빠름)", "1.1: " + M + "4.8 (지나침)"], INK),
        ("스케줄러", ["StepLR: 계단", "MultiStepLR: 정한 에폭", "ExponentialLR: gamma 배씩", "CosineAnnealingLR:", "  코사인 곡선",
                  "OneCycleLR: 올렸다 내림"], BLUE),
        ("자리", ["`optimizer.step()`", "`scheduler.step()`", "StepLR·Cosine: 에폭마다", "OneCycleLR: 배치마다"], INK)],
        note_line="새 w = w " + M + " 학습률 × 기울기. 크면 지나치고, 작으면 갱신을 여러 번 해야 합니다.")


# 5f 배치 정규화

@figure("5f-1", 560, 300)
def bn_5f():
    """데이터 다섯 개가 한 특징에 낸 값 [1, 2, 3, 4, 5] 를 정규화하고 γ = 2, β = 1 을 쓰는 과정."""
    v = np.array([1, 2, 3, 4, 5.0])
    mu, var = v.mean(), ((v - v.mean()) ** 2).mean()
    xh = (v - mu) / math.sqrt(var)
    yv = 2 * xh + 1
    assert mu == 3 and var == 2 and [num(t, 3) for t in xh] == [M + "1.414", M + "0.707", "0", "0.707", "1.414"]
    assert [num(t, 3) for t in yv] == [M + "1.828", M + "0.414", "1", "2.414", "3.828"]
    assert abs(yv.mean() - 1) < 1e-12 and abs(yv.var() - 4) < 1e-12
    rows = [("x", v, BLUE, 3), ("x " + M + " μ", v - mu, LIGHT, 0), ("x̂", xh, GREEN, 0), ("y = 2x̂ + 1", yv, PURPLE, 1)]
    S2, GA = "σ²", "γ"

    def draw(stage, title, lines):
        plt, fig = new(600)
        ax = fig.add_axes([0.16, 0.10, 0.80, 0.76])
        ax.set_xlim(-2.5, 5.5)
        ax.set_ylim(-0.5, 3.6)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.set_yticks([])
        ax.set_xticks(range(-2, 6))
        ax.grid(True, axis="x", color=GRID)
        for k in range(min(stage, 4)):
            name, vals, color, mean = rows[k]
            y = 3 - k
            ax.scatter(vals, [y] * 5, s=140, color=color, zorder=5)
            ax.plot([mean, mean], [y - 0.35, y + 0.28], color=MUTED, lw=2, ls="--")
            fig.text(0.02, 0.10 + 0.76 * (y + 0.5) / 4.1, name, fontsize=19, color=color if color != LIGHT else INK,
                     weight="bold", va="center")
            for t in vals:
                ax.text(t, y + 0.40, num(t, 3), ha="center", fontsize=14)
        fig.text(0.015, 0.95, title, fontsize=21, weight="bold", va="center")
        if lines:
            math = lines.startswith("§")
            fig.text(0.55, 0.95, lines.lstrip("§"), fontsize=17, va="center", ha="left", family=MATH if math else None)
        return image(fig)

    frames = [draw(1, "데이터 다섯 개가 한 특징에 낸 값", "평균 μ = 3 (회색 점선)"),
              draw(2, "1. 평균 빼기", "§" + S2 + " = (4 + 1 + 0 + 1 + 4) ÷ 5 = 2"),
              draw(3, "2. 1.414 로 나누기", "x̂ 의 평균 0, 분산 1"),
              draw(4, "3. 2 를 곱하고 1 을 더하기", "y 의 평균 1, 분산 4"),
              draw(4, "특징 하나의 배치 정규화 계산", "§x̂ = (x " + M + " μ) ÷ √" + S2 + ",  y = " + GA + "x̂ + β")]
    return frames, [2000, 2400, 2400, 2400, 2500]


@figure("5f-2", 560, 300)
def modes_5f():
    """학습 모드와 평가 모드가 쓰는 통계, 학습 모드로 같은 배치를 넣을 때 처음 이동 평균이 남는 비율 0.9^k."""
    keep = [0.9 ** k for k in range(6)]
    assert f"{keep[5]:.2f}" == "0.59" and abs(0.9 * 3 + 0.1 * 5 - 3.2) < 1e-12
    plt, fig = new(600)
    ax = board(fig)
    text(ax, 2, 56.5, "model.train() 과 model.eval()", size=21, weight="bold")
    box(ax, 2, 30, 34, 20, "", fc="white", ec=ORANGE, lw=2.6)
    text(ax, 4, 46.5, "model.train()", size=18, family=CODE, weight="bold", color=ORANGE)
    text(ax, 4, 40.5, "지금 배치의 평균·분산으로\n정규화", size=16)
    text(ax, 4, 33.6, "이동 평균도 고침\n0.9 × 3 + 0.1 × 5 = 3.2", size=15, color=MUTED)
    box(ax, 40, 30, 30, 20, "", fc="white", ec=MUTED, lw=2.6)
    text(ax, 42, 46.5, "model.eval()", size=18, family=CODE, weight="bold", color=MUTED)
    text(ax, 42, 40, "모아 둔 이동 평균·분산으로\n정규화", size=16)
    text(ax, 42, 33, "배치와 상관없이 같은 출력", size=16)
    bx = fig.add_axes([0.66, 0.14, 0.32, 0.36])
    tidy(bx)
    bx.bar(range(6), keep, color=MUTED, width=0.6)
    bx.set_ylim(0, 1.15)
    bx.set_xticks(range(6))
    bx.set_xlabel("학습 모드로 넣은 횟수", fontsize=15)
    bx.text(5, keep[5] + 0.05, num(keep[5], 2), ha="center", fontsize=15)
    text(ax, 75, 46, "처음 이동 평균이\n남는 비율 0.9ᵏ", size=17, color=MUTED)
    text(ax, 2, 18, "no_grad 안이어도 학습 모드면 이동 평균이 바뀝니다.", size=17, bg=NOTE)
    text(ax, 2, 10, "평가 전에 model.eval() 을 부릅니다.", size=17, bg=NOTE)
    return image(fig)


@figure("5f-3", 560, 300)
def axes_5f():
    """[4, 3] 텐서(데이터 4개, 특징 3개). 배치 정규화는 특징마다 세로로, Layer Normalization 은 데이터마다 가로로 평균."""
    G = np.array([[1, 2, 3], [3, 4, 5], [5, 6, 7], [7, 8, 9.0]])
    assert G.mean(0).tolist() == [4, 5, 6] and G.mean(1).tolist() == [2, 4, 6, 8]
    plt, fig = new(600)
    ax = board(fig)
    for k, (title, color) in enumerate((("배치 정규화: 특징마다", ORANGE), ("Layer Normalization: 데이터마다", RED))):
        x0 = 4 + k * 56
        text(ax, x0 - 2, 56.5, title, size=19, weight="bold", color=color)
        for r in range(4):
            for c in range(3):
                box(ax, x0 + c * 9, 40 - r * 8, 8.4, 7.4, num(G[r, c], 0), fc="white", ec=LIGHT, size=18, lw=1.6)
            text(ax, x0 - 3.5, 43.7 - r * 8, "%d" % (r + 1), size=15, color=MUTED)
        if k == 0:
            for c in range(3):
                ax.add_patch(plt.Rectangle((x0 + c * 9 + 1.6, 15.8), 5.2, 32.4, fc="none", ec=color, lw=3, zorder=6))
                text(ax, x0 + c * 9 + 4.2, 12, num(G[:, c].mean(), 0), size=19, color=color, ha="center", weight="bold")
            text(ax, x0 - 2, 6, "평균 3개 = 특징 수", size=17)
        else:
            for r in range(4):
                ax.add_patch(plt.Rectangle((x0 - 0.6, 40.6 - r * 8), 27.6, 6.2, fc="none", ec=color, lw=3, zorder=6))
                text(ax, x0 + 29, 43.7 - r * 8, num(G[r].mean(), 0), size=19, color=color, weight="bold")
            text(ax, x0 - 2, 6, "평균 4개 = 데이터 수", size=17)
    return image(fig)


@figure("5f-4", 560, 280)
def memo_5f():
    return summary("배치 정규화", [
        ("계산", ["§μ = 3, σ² = 2", "§x̂ = (x " + M + " μ) ÷ √(σ²+ε)", "§y = γx̂ + β", "§γ, β", "학습하며 바뀌는 파라미터"], GREEN),
        ("자리와 코드", ["Linear → BN → ReLU", "`nn.Linear(20, 64)`", "`nn.BatchNorm1d(64)`", "`nn.ReLU()`"], INK),
        ("기본 모드", ["train: 배치 평균·분산", "eval: 이동 평균·분산", "평가 전 model.eval()", "RNN 도 통계 축을 확인"], ORANGE)],
        note_line="학습률과 일반화에 미치는 효과는 모델·데이터에 따라 달라집니다.")


# 5g 코드 읽기

@figure("5g-1", 560, 300)
def split_5g():
    """1,000개를 800·200 으로 나누고, 학습 데이터 값 [2, 6] 으로 fit 한 평균·표준편차로 테스트 값 8 을 바꾸기."""
    tr = np.array([2, 6.0])
    mu, sd = tr.mean(), tr.std()
    assert mu == 4 and sd == 2 and ((tr - mu) / sd).tolist() == [-1, 1] and (8 - mu) / sd == 2
    plt, fig = new(600)
    ax = board(fig)
    text(ax, 2, 56.5, "나누고, 학습 데이터로만 fit", size=21, weight="bold")
    box(ax, 2, 42, 80, 7, "학습 데이터 800개", fc=BLUE_L, ec=BLUE, color=BLUE, size=18)
    box(ax, 83, 42, 20, 7, "테스트 200개", fc=ORANGE_L, ec=ORANGE, color=ORANGE, size=18)
    text(ax, 2, 37, "train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)", size=16, family=CODE)
    box(ax, 2, 12, 34, 19, "", fc="white", ec=BLUE, lw=2.4)
    text(ax, 3, 27.5, "scaler.fit_transform(X_train)", size=15, family=CODE, color=BLUE)
    text(ax, 3, 21.5, "학습 데이터 [2, 6]", size=17)
    text(ax, 3, 16, "→ [" + M + "1, 1]", size=17)
    box(ax, 40, 18, 26, 9, "평균 4\n표준편차 2", fc=GREEN_L, ec=GREEN, color=GREEN, size=17)
    arrow(ax, 36.3, 22.5, 39.7, 22.5, color=GREEN)
    box(ax, 70, 12, 37, 19, "", fc="white", ec=ORANGE, lw=2.4)
    text(ax, 72, 27.5, "scaler.transform(X_test)", size=15, family=CODE, color=ORANGE)
    text(ax, 72, 21.5, "테스트 값 8", size=17)
    text(ax, 72, 16, "→ (8 " + M + " 4) ÷ 2 = 2", size=17)
    arrow(ax, 66.3, 22.5, 69.7, 22.5, color=GREEN)
    text(ax, 2, 5, "테스트 데이터에는 fit 하지 않고 학습 데이터에서 구한 평균 4, 표준편차 2 를 씁니다.", size=17, bg=NOTE)
    return image(fig)


@figure("5g-2", 560, 300)
def tensors_5g():
    """텐서로 바꾸고 묶어 배치로 꺼내기. 정답은 [800] 에서 [800, 1] 로, 배치 64 면 13개(마지막 32개)."""
    nb = -(-800 // 64)
    assert nb == 13 and 800 - 12 * 64 == 32

    def draw(stage, title, line):
        plt, fig = new(600)
        ax = board(fig)
        text(ax, 2, 56.5, title, size=21, weight="bold")
        box(ax, 2, 18, 30, 30, "", fc=BLUE_L, ec=BLUE, lw=2.4)
        text(ax, 17, 33, "x_train_t\n[800, 20]", size=18, ha="center", family=CODE, color=BLUE, bg="white" if stage >= 4 else None)
        if stage == 1:
            box(ax, 36, 18, 30, 3, "", fc=PURPLE_L, ec=PURPLE, lw=2)
            text(ax, 51, 24, "y_train [800]", size=17, ha="center", family=CODE, color=PURPLE)
        else:
            box(ax, 36, 18, 4, 30, "", fc=PURPLE_L, ec=PURPLE, lw=2)
            text(ax, 42, 33, "y_train_t\n[800, 1]", size=17, family=CODE, color=PURPLE)
        if stage >= 3:
            ax.plot([2, 40], [46.5, 46.5], color=INK, lw=1.4, ls=":")
            text(ax, 58, 46.5, "ds[0] = (x_train_t[0], y_train_t[0])", size=15, family=CODE)
        if stage >= 4:
            n = 13
            for k in range(n):
                y0 = 48 - (k + 1) * 30 / 800 * 64 if k < 12 else 18
                hot = (stage == 4 and k == 0) or (stage == 5 and k == 12)
                h = 30 / 800 * (64 if k < 12 else 32)
                top = 48 - k * 30 / 800 * 64
                ax.add_patch(plt.Rectangle((2, top - h), 38, h, fc=HL if hot else "none", ec=MUTED, lw=1, zorder=4))
            info = "batch_x [64, 20]\nbatch_y [64, 1]" if stage == 4 else "batch_x [32, 20]\nbatch_y [32, 1]"
            box(ax, 72, 22, 34, 14, info, fc=HL, ec=INK, family=CODE, size=17)
        text(ax, 2, 9, line, size=17, bg=NOTE)
        return image(fig)

    frames = [draw(1, "X_train, y_train 을 텐서로", "torch.FloatTensor(X_train) 은 32비트 실수 텐서를 만듭니다."),
              draw(2, "정답에 축 하나 더하기", "unsqueeze(1): [800] → [800, 1]"),
              draw(3, "TensorDataset 으로 묶기", "i 번째를 꺼내면 (x[i], y[i]) 를 줍니다. len(ds) = 800"),
              draw(4, "DataLoader(ds, batch_size=64)", "첫 배치: 64개. 배치는 모두 13개입니다."),
              draw(5, "마지막 배치", "12 × 64 + 32 = 800. 마지막 배치는 32개입니다.")]
    return frames, [2000, 2200, 2200, 2400, 2500]


@figure("5g-3", 560, 300)
def argmax_5g():
    """노트북 02 의 3×4 out 에서 argmax(), argmax(dim=1), max()."""
    out = np.array([[0.1, 2.3, 0.5, 1.1], [3.2, 0.4, 1.8, 0.9], [0.2, 1.1, 4.0, 0.3]])
    assert int(out.argmax()) == 10 and out.argmax(1).tolist() == [1, 0, 2] and out.max() == 4.0
    rows = out.argmax(1)
    plt, fig = new(600)
    ax = board(fig)
    text(ax, 2, 56.5, "out = 3 × 4 텐서", size=21, weight="bold")
    for r in range(3):
        text(ax, 2, 42.5 - r * 10, "%d행" % r, size=16, color=MUTED)
        for c in range(4):
            hot = rows[r] == c
            big = r == 2 and c == 2
            box(ax, 9 + c * 11, 38 - r * 10, 10, 9, f"{out[r, c]:.1f}", fc=HL if hot else "white", ec=INK if big else LIGHT,
                lw=4 if big else 1.6, size=19)
            text(ax, 9.8 + c * 11, 45.3 - r * 10, str(r * 4 + c), size=14, color=MUTED)
    for c in range(4):
        text(ax, 14 + c * 11, 50, "%d열" % c, size=16, color=MUTED, ha="center")
    lines = [("out.argmax()", "tensor(10)", "한 줄로 편 위치 2 × 4 + 2"), ("out.argmax(dim=1)", "tensor([1, 0, 2])",
                                                                       "행마다 가장 큰 칸의 열"),
             ("out.max()", "tensor(4.)", "위치가 아니라 값")]
    yy = 46
    for code, res, desc in lines:
        text(ax, 59, yy, code, size=17, family=CODE)
        text(ax, 59, yy - 4.5, "→ " + res, size=17, family=CODE, weight="bold")
        text(ax, 59, yy - 9, desc, size=15, color=MUTED)
        yy -= 15
    text(ax, 2, 5, "작은 회색 숫자는 한 줄로 폈을 때의 위치입니다.", size=16, bg=NOTE)
    return image(fig)


def _record_run():
    """4차시 다섯 사람 자료로 lr 0.001, 300번, 50번마다 갱신 전 손실 기록(float32). 기록과 300번 뒤 손실."""
    W, B = np.float32(1.0), np.float32(1.0)
    X, Y = X5.astype(np.float32), Y5.astype(np.float32)
    losses, rec = [], {}
    for ep in range(300):
        e = W * X + B - Y
        loss = float((e ** 2).mean())
        losses.append(loss)
        gw, gb = 2 * (e * X).mean(), 2 * e.mean()
        W, B = np.float32(W - np.float32(0.001) * gw), np.float32(B - np.float32(0.001) * gb)
        if ep % 50 == 0:
            rec[ep] = loss
    after = float(((W * X + B - Y) ** 2).mean())
    return np.array(losses), rec, after


@figure("5g-4", 560, 300)
def record_5g():
    """300번 되풀이하며 50번마다 갱신 전 손실을 기록할 때 마지막 기록과 300번 갱신 뒤 손실."""
    losses, rec, after = _record_run()
    assert sorted(rec) == [0, 50, 100, 150, 200, 250]
    assert f"{rec[0]:.4f}" == "13.3520" and f"{rec[250]:.4f}" == "4.9066" and f"{after:.4f}" == "4.8399"
    plt, fig = new(600)
    ax = fig.add_axes([0.09, 0.14, 0.86, 0.70])
    tidy(ax)
    ax.plot(np.arange(300), losses, color=RED, lw=2.6)
    ax.set_xlim(-18, 330)
    ax.set_ylim(4, 14.5)
    ax.set_xlabel("epoch")
    ax.set_ylabel("손실")
    for ep, val in rec.items():
        hot = ep == 250
        ax.scatter([ep], [val], s=170 if hot else 80, color=INK, zorder=5, edgecolor=INK)
        if hot:
            ax.scatter([ep], [val], s=520, color="#fde68a", zorder=4)
        ax.text(ep + (14 if ep == 50 else 0), val + 0.55, num(val, 4), ha="center", fontsize=15)
    ax.scatter([300], [after], s=150, facecolor="white", edgecolor=RED, lw=2.6, zorder=6)
    ax.text(300, after + 0.55, num(after, 4), ha="center", fontsize=15, color=RED)
    ax.annotate("", xy=(300, 6.2), xytext=(250, 6.2), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.6))
    ax.text(275, 6.5, "50번 더 갱신", ha="center", fontsize=15)
    fig.text(0.015, 0.95, "history[" + M + "1] 은 epoch가 250일 때 갱신하기 전에 잰 손실", fontsize=20, weight="bold", va="center")
    fig.text(0.55, 0.80, "검은 점: 기록한 손실\n빈 원: 300번 갱신한 뒤 다시 잰 손실", linespacing=1.5, fontsize=16, color=MUTED, va="center")
    return image(fig)


@figure("5g-5", 560, 280)
def memo_5g():
    return summary("코드 읽기: 표 데이터로 미니배치 학습", [
        ("나누고 표준화", ["`train_test_split(…, `", "`  test_size=0.2, stratify=y)`", "`scaler.fit_transform(X_train)`",
                     "`scaler.transform(X_test)`"], BLUE),
        ("텐서와 배치", ["`torch.FloatTensor(X_train)`", "`.unsqueeze(1)`", "[800] → [800, 1]", "`TensorDataset, DataLoader`",
                    "배치 크기 64: 13개", "마지막 배치 32개"], PURPLE),
        ("세기와 기록", ["`epoch_loss += loss.item()`", "`tot += y.size(0)`", "`out.argmax(1)`", "기록 = 갱신 전 손실"], RED)],
        note_line="range(300) 에서 50번마다 기록하면 마지막 기록은 epoch 250의 갱신 전 손실입니다.", pad=1.0)


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


# 5a 넷째 단계: Linear 층의 파라미터 수. 보라는 파라미터, 회색 테두리는 텐서의 값

def _levels_5a(level):
    assert 3 * 2 + 2 == 8 and (784 + 1) * 128 == 784 * 128 + 128 == 100480 and 2 * 3 + 3 == 9
    if level == 7:
        fig, ax = _lv_board()
        ins, outs = [200, 140, 80], [170, 110]
        for yi in ins:
            for yo in outs:
                ax.plot([110, 300], [yi, yo], color=PURPLE, lw=3, zorder=2)
        from matplotlib.patches import Circle
        for yi in ins:
            ax.add_patch(Circle((110, yi), 18, fc="white", ec=MUTED, lw=2.5, zorder=3))
        for yo in outs:
            ax.add_patch(Circle((300, yo), 18, fc="white", ec=MUTED, lw=2.5, zorder=3))
            ax.plot([318, 362], [yo, yo], color=MUTED, lw=2.5, zorder=2)
            _lv_box(ax, 405, yo, 86, 40, "더할 수", ec=PURPLE, fc=PURPLE_L, size=LV.FONT, color=PURPLE)
        _lv_text(ax, 110, 245, "입력 3개", color=MUTED)
        _lv_text(ax, 205, 245, "선 6개", color=PURPLE, bold=True)
        _lv_text(ax, 300, 245, "출력 2개", color=MUTED)
        _lv_text(ax, 260, 30, "보라 선 6개와 보라 칸 2개, 모두 8개")
        return fig
    if level == 15:
        xs = list(range(1, 9))
        ys = [(x + 1) * 2 for x in xs]
        assert ys[2] == 8 and all(b - a == 2 for a, b in zip(ys, ys[1:]))
        fig = LV.graph(xs, [(ys, "purple", "")], "입력 수", "파라미터 수", top="파라미터 수 = (입력 수 + 1) × 2",
                       marks=[(3, 8, "8", "purple")], xlim=(0.5, 8.6), ylim=(0, 21))
        return fig
    return LV.grid([["w", "w", "w", "b"], ["w", "w", "w", "b"]], col_names=["입력 1", "입력 2", "입력 3", "bias"],
                   row_names=["출력 1", "출력 2"], marks=[(r, c) for r in range(2) for c in range(4)], color="purple",
                   top="weight [2, 3], bias [2]", code=True)


@figure("5a-41", *LV.SIZE)
def levels_5a_7():
    return _levels_5a(7)


@figure("5a-42", *LV.SIZE)
def levels_5a_15():
    return _levels_5a(15)


@figure("5a-43", *LV.SIZE)
def levels_5a_20():
    return _levels_5a(20)


# 5b 셋째 단계: 비선형성. 초록은 ReLU 를 지난 값과 선

def _relu(z):
    return np.maximum(z, 0.0)


def _levels_5b(level):
    if level == 7:
        h1, h2 = 2 * -2 + 1, -(-2) + 3
        assert (h1, h2) == (-3, 5) and _relu(h1) + _relu(h2) - 1 == 4
        fig, ax = _lv_board()
        top, low, mid = 180, 100, 140
        _lv_box(ax, 60, mid, 70, 52, num(-2))
        _lv_box(ax, 185, top, 70, 52, num(h1))
        _lv_box(ax, 185, low, 70, 52, num(h2))
        _lv_box(ax, 315, top, 70, 52, "0", ec=GREEN, fc=GREEN_L, bold=True, lw=3)
        _lv_box(ax, 315, low, 70, 52, num(h2))
        _lv_box(ax, 445, mid, 70, 52, "4", bold=True)
        for y in (top, low):
            _lv_arrow(ax, 97, mid + (12 if y == top else -12), 148, y)
            _lv_arrow(ax, 222, y, 278, y)
            _lv_arrow(ax, 352, y, 408, mid + (12 if y == top else -12))
        for x, s in ((60, "입력"), (185, "두 상자"), (315, "바꾼 수"), (445, "나온 수")):
            _lv_text(ax, x, 240, s, color=MUTED)
        _lv_text(ax, 260, 32, "0보다 작으면 0, 둘을 더하고 1 빼기")
        return fig
    if level == 15:
        xs = np.linspace(-3, 5, 161)
        ys = _relu(2 * xs + 1) + _relu(-xs + 3) - 1
        assert abs(ys[0] - 5) < 1e-12 and abs(ys[-1] - 10) < 1e-12
        fig = LV.graph(list(xs), [(list(ys), "green", "")], "x", "y", top="y = ReLU(2x + 1) + ReLU(" + M + "x + 3) " + M + " 1",
                       marks=[(-0.5, 2.5, "", "green"), (3, 6, "", "green")], xlim=(-3.3, 5.6), ylim=(0, 11.5))
        ax = fig.axes[0]
        for x, y, s in ((-2.0, 6.6, M + "x + 2"), (1.2, 6.3, "x + 3"), (3.7, 9.4, "2x")):
            ax.text(x, y, s, ha="center", va="center", fontsize=LV.FONT, color=GREEN, family=LV.MATH_FONT)
        return fig
    x = np.array([-2.0, 1.0, 4.0])
    h1, h2 = 2 * x + 1, -x + 3
    line, bent = h1 + h2 - 1, _relu(h1) + _relu(h2) - 1
    assert line.tolist() == [1, 4, 7] and bent.tolist() == [4, 4, 8]
    rows = [["%g" % v for v in row] for row in zip(h1, h2, line, bent)]  # 코드 출력처럼 빼기표는 ASCII
    return LV.grid(rows, col_names=["h1", "h2", "ReLU 없이", "ReLU 넣음"],
                   row_names=["x = " + num(v) for v in x], marks=[(0, 3), (2, 3)], color="green",
                   top="relu(h1) + relu(h2) - 1", code=True)


@figure("5b-31", *LV.SIZE)
def levels_5b_7():
    return _levels_5b(7)


@figure("5b-32", *LV.SIZE)
def levels_5b_15():
    return _levels_5b(15)


@figure("5b-33", *LV.SIZE)
def levels_5b_20():
    return _levels_5b(20)


# 5d 둘째 단계: 배치·확률적·미니배치. 파랑 배치, 주황 SGD, 초록 미니배치, 노랑 마지막 배치

def fmt3(v):
    """소수 셋째 자리 고정, 빼기표는 코드 출력처럼 ASCII."""
    return f"{v:.3f}"


def _sgd_steps(lr=0.02):
    """사람 1부터 한 명씩 갱신할 때 (W, B, 다섯 사람 손실) 목록. 처음 값을 맨 앞에 둠."""
    W, B = 1.0, 1.0
    rows = [(W, B, float(_loss5(W, B)))]
    for i in range(5):
        e = W * X5[i] + B - Y5[i]
        W, B = W - lr * 2 * e * X5[i], B - lr * 2 * e
        rows.append((W, B, float(_loss5(W, B))))
    return rows


def _levels_5d(level):
    if level == 7:
        fig, ax = _lv_board()
        dots = [150, 200, 250, 300, 350]
        plans = [("한꺼번에", [[0, 1, 2, 3, 4]], BLUE, BLUE_L), ("한 사람씩", [[0], [1], [2], [3], [4]], ORANGE, ORANGE_L),
                 ("두 사람씩", [[0, 1], [2, 3], [4]], GREEN, GREEN_L)]
        assert [len(p[1]) for p in plans] == [1, 5, 3]
        for n, (name, groups, ec, fc) in enumerate(plans):
            y = 210 - 70 * n
            _lv_text(ax, 62, y, name)
            for k, group in enumerate(groups):
                last = n == 2 and k == len(groups) - 1
                x0, x1 = dots[group[0]] - 20, dots[group[-1]] + 20
                _lv_box(ax, (x0 + x1) / 2.0, y, x1 - x0, 44, "", ec=ec, fc=HL if last else fc, lw=2.5)
            for x in dots:
                ax.plot([x], [y], "o", ms=13, color=INK, zorder=5)
            _lv_text(ax, 440, y, "%d번" % len(groups), size=LV.BIG, bold=True, color=ec)
        _lv_text(ax, 250, 262, "다섯 사람", color=MUTED)
        _lv_text(ax, 440, 262, "갱신", color=MUTED)
        return fig
    e = 1.0 * X5 + 1.0 - Y5
    gW, gB = 2 * e * X5, 2 * e
    assert np.allclose(gW, [-27, -43, 0, -8, -17.2]) and np.allclose(gB, [5.4, -8.6, 8.6, -4, 8.6])
    assert abs(gW.mean() + 19.04) < 1e-9 and abs(gB.mean() - 2.0) < 1e-9
    if level == 15:
        rows = [[num(a, 1), num(b, 1), num(c, 1)] for a, b, c in zip(e, gW, gB)] + [["", num(gW.mean(), 2), num(gB.mean(), 1)]]
        return LV.grid(rows, col_names=["e", "W의 기울기", "B의 기울기"],
                       row_names=["사람 %d" % k for k in range(1, 6)] + ["평균"], marks=[(5, 1), (5, 2)], color="blue",
                       top="W의 기울기 = (다섯 사람 값의 합) ÷ 5")
    steps = _sgd_steps()
    assert f"{steps[0][2]:.3f}" == "13.352" and f"{steps[-1][2]:.2f}" == "5.95"
    assert steps[4][2] > steps[3][2] and all(steps[k][2] < steps[k - 1][2] for k in (1, 2, 3))
    rows = [[fmt3(w), fmt3(b), fmt3(l)] for w, b, l in steps]
    return LV.grid(rows, col_names=["W", "B", "다섯 사람 손실"], row_names=["처음"] + ["사람 %d" % k for k in range(1, 6)],
                   top="W -= 0.02 * W.grad", code=True)


@figure("5d-21", *LV.SIZE)
def levels_5d_7():
    return _levels_5d(7)


@figure("5d-22", *LV.SIZE)
def levels_5d_15():
    return _levels_5d(15)


@figure("5d-23", *LV.SIZE)
def levels_5d_20():
    return _levels_5d(20)


# 5f 넷째 단계: train 모드와 eval 모드. 파랑은 원래 값 x, 주황은 지금 배치의 평균, 회색은 이동 평균

def _levels_5f(level):
    assert abs(0.9 * 3 + 0.1 * 5 - 3.2) < 1e-12 and np.mean([1, 2, 3, 4, 5]) == 3 and np.mean([3, 4, 5, 6, 7]) == 5
    if level == 7:
        fig, ax = _lv_board()
        top, low = 185, 80
        _lv_text(ax, 58, top, "학습할 때")
        _lv_text(ax, 58, low, "평가할 때")
        for k, v in enumerate([1, 2, 3, 4, 5]):
            _lv_box(ax, 118 + 36 * k, top, 32, 46, str(v), ec=BLUE if v == 3 else MUTED, fc=BLUE_L if v == 3 else "white",
                    bold=v == 3)
        _lv_arrow(ax, 290, top, 322, top)
        _lv_box(ax, 372, top, 90, 46, "3", ec=ORANGE, fc=ORANGE_L, bold=True)
        _lv_text(ax, 372, top + 40, "평균", color=ORANGE)
        _lv_text(ax, 470, top, "차이 0", bold=True)
        _lv_box(ax, 190, low, 32, 46, "3", ec=BLUE, fc=BLUE_L, bold=True)
        _lv_arrow(ax, 214, low, 322, low)
        _lv_box(ax, 372, low, 90, 46, "3.2", ec=MUTED, fc=NOTE, bold=True)
        _lv_text(ax, 372, low + 40, "모아 둔 수", color=MUTED)
        _lv_text(ax, 470, low, "0.2 작음", bold=True)
        return fig
    if level == 15:
        rows = [["3", "0"], ["5", M + "2"], ["3.2", M + "0.2"], ["3.2", M + "0.2"]]
        assert 3 - 3 == 0 and 3 - 5 == -2 and abs((3 - 3.2) + 0.2) < 1e-12
        return LV.grid(rows, col_names=["빼는 값", "3의 결과"],
                       row_names=["학습 모드, 배치 1~5", "학습 모드, 배치 3~7", "평가 모드, 배치 1~5", "평가 모드, 배치 3~7"],
                       marks=[(0, 0), (1, 0)], color="orange", top="평가 모드는 이동 평균 3.2를 뺌")
    rm = 0.9 * 0.0 + 0.1 * 3.0
    assert abs(rm - 0.3) < 1e-12
    rows = [["True", "0"], ["True", "0.3"], ["False", "0.3"], ["False", "0.3"]]
    return LV.grid(rows, col_names=["training", "running_mean"], row_names=["만든 뒤", "bn(x)", "bn.eval()", "bn(x[2:3])"],
                   top="bn = nn.BatchNorm1d(1)", code=True)


@figure("5f-41", *LV.SIZE)
def levels_5f_7():
    return _levels_5f(7)


@figure("5f-42", *LV.SIZE)
def levels_5f_15():
    return _levels_5f(15)


@figure("5f-43", *LV.SIZE)
def levels_5f_20():
    return _levels_5f(20)
