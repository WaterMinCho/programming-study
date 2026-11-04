#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""상황별 코드 학습 노트 l18 의 그림(18a 미니배치 학습 한 에폭).

그림에 찍는 숫자는 이 파일에서 다시 계산하고 assert 로 확인함. 검산 기록은 설계 폴더 factcheck/scripts/pc_check.py.
코드 줄은 ai/patterns/S1.json 의 표준형을 읽어 그려서 노트·카드와 같은 줄이 나옴.

  python -m tools.ai_art l18                 ai/learn/l18/assets/ 에 그림을 모두 쓰고 manifest 를 고침
  python -m tools.ai_art l18 18a-2           이름을 적은 그림만

numpy·matplotlib·Pillow 가 있는 출제자 파이썬에서만 돌림. matplotlib 는 Agg 로만 씀(창을 띄우지 않음).
파일은 1120×600 이하(화면 560×300), GIF 는 장 10개 이하·장마다 1600~2500ms·64색, 마지막 장은 정지 요약임.

18a 의 색은 한 색이 한 뜻임. 뜻은 캡션에 적음.
  회색 꼬리표는 앞 차시에서 배운 줄, 주황은 손실의 합과 이 단원 4단계에서 배우는 손실 세기 줄, 파랑은 데이터 수,
  초록은 맞힌 수, 보라는 optimizer.zero_grad() 와 그 줄을 둘 수 있는 자리, 빨강은 둘 수 없는 자리, 노랑은 지금 꺼낸 배치
"""
import json
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
BLUE_L, ORANGE_L, GREEN_L, PURPLE_L, RED_L = "#dbeafe", "#ffedd5", "#d1fae5", "#ede9fe", "#fee2e2"
NOTE, BAND, LIGHT = "#f3f4f6", "#e5e7eb", "#9ca3af"
CODE = "D2Coding"
SIZES = {"font.size": 20, "axes.titlesize": 20, "axes.labelsize": 19, "xtick.labelsize": 17, "ytick.labelsize": 17,
         "axes.linewidth": 1.2, "axes.edgecolor": "#9ca3af"}

# 18a 의 예: 데이터 10개, 배치 크기 4 → 배치 4·4·2, 배치 평균 손실 0.5·1.0·2.0, 맞힌 수 3·2·1
SIZES_18A = [4, 4, 2]
MEANS_18A = [0.5, 1.0, 2.0]
HITS_18A = [3, 2, 1]


def standard_lines():
    with open(os.path.join(ROOT, "ai", "patterns", "S1.json"), encoding="utf-8") as f:
        return json.load(f)["variants"]["표준형"]["lines"]


def num(v, nd=2):
    """그림에 찍는 숫자. 빼기표는 U+2212."""
    s = f"{v:.{nd}f}"
    return s.replace("-", MINUS)


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


def rect(ax, x, y, w, h, fc, ec="none", lw=0.0, zorder=1):
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, zorder=zorder))


def dot(ax, x, y, color, r=0.9):
    from matplotlib.patches import Circle
    ax.add_patch(Circle((x, y), r, fc=color, ec=color, zorder=7))


def summary(title, cols, h=560, note_line=None, pad=1.6):
    """외울 것 요약 그림. cols 는 [(제목, [줄...], 테두리 색)] 이고 왼쪽에서 오른쪽으로 화살표로 이음."""
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
        text(ax, x + w / 2, top - 3.2, head, size=19, weight="bold", ha="center", color=ec)
        yy = top - 8
        for line in lines:
            code = line.startswith("`")
            body = line.strip("`")
            text(ax, x + pad, yy, body, size=14 if code else 16, family=CODE if code else None, va="top")
            yy -= 4.4 * (body.count("\n") + 1)
        if k < n - 1:
            arrow(ax, x + w + 0.2, (top + bottom) / 2, x + w + gap - 0.2, (top + bottom) / 2, color=LIGHT, lw=2.6)
    if note_line:
        text(ax, 2, 4.5, note_line, size=16, bg=NOTE)
    return image(fig)


def _epoch():
    """18a 예의 값. 배치 합, 누적 loss_sum·total·correct, 에폭 손실·정확도, 배치 수로 나눈 값, fit 식."""
    sums = [m * n for m, n in zip(MEANS_18A, SIZES_18A)]
    acc_loss = list(np.cumsum(sums))
    acc_total = list(np.cumsum(SIZES_18A))
    acc_hits = list(np.cumsum(HITS_18A))
    total = sum(SIZES_18A)
    epoch_loss = sum(sums) / total
    by_batches = sum(MEANS_18A) / len(SIZES_18A)
    fit = sum(MEANS_18A) / total
    assert sums == [2.0, 4.0, 4.0] and acc_loss == [2.0, 6.0, 10.0] and acc_total == [4, 8, 10] and acc_hits == [3, 5, 6]
    assert epoch_loss == 1.0 and abs(by_batches - 7 / 6) < 1e-12 and abs(fit - 0.35) < 1e-12
    assert sum(HITS_18A) / total == 0.6
    return sums, acc_loss, acc_total, acc_hits, epoch_loss, by_batches, fit


# 18a-1 열다섯 줄과 배운 곳

@figure("18a-1", 560, 300)
def lines_18a():
    """표준형 열다섯 줄 옆에 그 줄을 배운 곳 꼬리표. 회색은 앞 차시, 주황은 이 단원 4단계."""
    lines = standard_lines()
    assert len(lines) == 15 and lines[10].strip() == "loss_sum += loss.item() * x.size(0)"
    tags = [((0, 0), "5차시 여섯째 단원 · 배치 정규화", False), ((1, 1), "이 단원 4단계 · 손실 세기", True),
            ((2, 2), "5차시 넷째 단원 · DataLoader", False), ((3, 4), "3차시 여덟째 단원 · 장치", False),
            ((5, 9), "1차시 둘째 단원 · 학습 다섯 줄", False), ((10, 10), "이 단원 4단계 · 손실 세기", True),
            ((11, 12), "5차시 일곱째 단원 · 데이터 수, 맞힌 수", False), ((13, 13), "이 단원 4단계 · 손실 세기", True),
            ((14, 14), "1차시 둘째 단원 · 정확도", False)]
    covered = sorted(k for (a, b), _, _ in tags for k in range(a, b + 1))
    assert covered == list(range(15))
    plt, fig = new(600)
    ax = board(fig)
    text(ax, 2, 57, "미니배치 학습 한 에폭: 줄마다 배운 곳", size=21, weight="bold")
    top, step = 51.6, 3.35
    ys = [top - k * step for k in range(15)]
    for (a, b), label, new_here in tags:
        y0, y1 = ys[b] - step / 2 + 0.25, ys[a] + step / 2 - 0.25
        if new_here:
            rect(ax, 1.2, y0, 52.6, y1 - y0, ORANGE_L)
        ax.plot([55.2, 56.2, 56.2, 55.2], [y1 - 0.2, y1 - 0.2, y0 + 0.2, y0 + 0.2], color=ORANGE if new_here else LIGHT,
                lw=2.0, zorder=4)
        box(ax, 58, (y0 + y1) / 2 - 1.4, 51, 2.8, label, fc=ORANGE_L if new_here else NOTE,
            ec=ORANGE if new_here else LIGHT, color=ORANGE if new_here else INK, size=15, lw=1.6, ha="left")
    for k, line in enumerate(lines):
        text(ax, 2, ys[k], line, size=14, family=CODE)
    return image(fig)


# 18a-2 zero_grad 를 둘 수 있는 자리

FIVE = ["optimizer.zero_grad()", "out = model(x)", "loss = criterion(out, y)", "loss.backward()", "optimizer.step()"]


def _loop(order):
    """FIVE 의 번호 순서로 만든 루프 줄. order 에 0 이 없으면 zero_grad 가 없는 루프."""
    return ["for x, y in loader:"] + ["    " + FIVE[k] for k in order]


@figure("18a-2", 560, 300)
def places_18a():
    """zero_grad 를 둘 수 있는 네 자리와 둘 수 없는 자리, 빠진 경우. 오른쪽 칸은 step() 이 갱신에 쓰는 기울기."""
    standard = [l.strip() for l in standard_lines()[5:10]]
    assert standard == FIVE
    cases = [
        ("맨 앞에 둘 때", [0, 1, 2, 3, 4], "이번 배치의 기울기", True),
        ("순전파 다음에 둘 때", [1, 0, 2, 3, 4], "이번 배치의 기울기", True),
        ("backward() 바로 앞에 둘 때", [1, 2, 0, 3, 4], "이번 배치의 기울기", True),
        ("step() 뒤에 둘 때", [1, 2, 3, 4, 0], "이번 배치의 기울기", True),
        ("backward()와 step() 사이에 둘 때", [1, 2, 3, 0, 4], "이번 배치의 기울기가\n지워짐", False),
        ("zero_grad()가 없을 때", [1, 2, 3, 4], "지난 배치의 기울기\n+ 이번 배치의 기울기", False),
    ]
    # 둘 수 있는 자리는 zero_grad 가 backward(3) 앞에 있거나 step(4) 뒤에 있는 순서임
    for _, order, _, ok in cases:
        if 0 in order:
            at = order.index(0)
            assert ok == (at < order.index(3) or at > order.index(4))

    def frame(title, order, used, ok):
        plt, fig = new(600)
        ax = board(fig)
        text(ax, 2, 56.5, title, size=21, weight="bold")
        lines = _loop(order)
        top, step = 46, 5.6
        for k, line in enumerate(lines):
            y = top - k * step
            if "zero_grad" in line:
                rect(ax, 1.4, y - step / 2 + 0.5, 50, step - 1.0, PURPLE_L if ok else RED_L)
                text(ax, 2.5, y, line, size=17, family=CODE, color=PURPLE if ok else RED, weight="bold")
            else:
                text(ax, 2.5, y, line, size=17, family=CODE)
        box(ax, 60, 22, 48, 24, "", fc="white", ec=PURPLE if ok else RED, lw=2.4)
        text(ax, 84, 42, "step()이 갱신에 쓰는 기울기", size=16, ha="center", color=MUTED)
        text(ax, 84, 32.5, used, size=19, ha="center", weight="bold", color=INK if ok else RED)
        box(ax, 66, 10, 36, 6, "둘 수 있는 자리" if ok else "둘 수 없는 자리", fc=PURPLE_L if ok else RED_L,
            ec=PURPLE if ok else RED, color=PURPLE if ok else RED, size=18, weight="bold")
        return image(fig)

    def places():
        plt, fig = new(600)
        ax = board(fig)
        text(ax, 2, 56.5, "zero_grad()를 둘 수 있는 자리", size=21, weight="bold")
        rows = ["for x, y in loader:", "    out = model(x)", "    loss = criterion(out, y)", "    loss.backward()",
                "    optimizer.step()"]
        top, step = 46, 7.2
        for k, line in enumerate(rows):
            text(ax, 8, top - k * step, line, size=17, family=CODE)
        # 줄 사이 자리: 순전파 앞, 순전파와 손실 사이, 손실과 backward 사이, backward 와 step 사이, step 뒤
        gaps = [(top - (k + 0.5) * step, k != 3) for k in range(5)]
        assert [ok for _, ok in gaps].count(True) == 4
        for y, ok in gaps:
            dot(ax, 5.5, y, PURPLE if ok else RED, r=1.0)
            ax.plot([7.5, 50], [y, y], color=PURPLE if ok else RED, lw=1.4, ls=(0, (4, 3)), zorder=2)
        box(ax, 60, 26, 48, 18, "보라 점 네 곳: 둘 수 있음\n빨간 점: 둘 수 없음", fc="white", ec=LIGHT, size=18, lw=2.0)
        text(ax, 60, 18, "이번 backward() 앞에서\n지난 기울기가 지워져 있으면 됩니다.", size=16, va="top")
        return image(fig)

    frames = [frame(*c) for c in cases] + [places()]
    return frames, [2400, 2200, 2000, 2400, 2500, 2400, 2000]


# 18a-3 배치 셋을 지나며 모이는 값

@figure("18a-3", 560, 300)
def batches_18a():
    """데이터 10개를 배치 4·4·2 로 꺼내며 loss_sum(주황), total(파랑), correct(초록)이 모이는 과정."""
    sums, acc_loss, acc_total, acc_hits, epoch_loss, by_batches, fit = _epoch()
    starts = [0, 4, 8]

    def frame(stage):
        plt, fig = new(600)
        ax = board(fig)
        titles = ["데이터 10개, 배치 크기 4", "첫 배치", "둘째 배치", "셋째 배치: 데이터 2개", "루프가 끝난 뒤",
                  "배치 수로 나누면"]
        text(ax, 2, 56.5, titles[stage], size=21, weight="bold")
        # 데이터 칸 10개. 배치 사이를 띄움
        cell, gap = 9.6, 4.0
        xs = []
        for b, (s, n) in enumerate(zip(starts, SIZES_18A)):
            for k in range(n):
                xs.append(4 + (s + k) * cell + b * gap)
        for b, (s, n) in enumerate(zip(starts, SIZES_18A)):
            x0 = xs[s] - 0.6
            w = n * cell + 0.6
            now = stage == b + 1
            done = stage >= b + 1
            box(ax, x0, 39, w - 0.4, 9.4, "", fc=HL if now else "white", ec=INK if now else LIGHT, lw=2.2 if now else 1.4)
            for k in range(n):
                hit = done and k < HITS_18A[b]
                rect(ax, xs[s + k] + 0.2, 40.3, cell - 1.4, 6.6, GREEN_L if hit else "white", GREEN if hit else MUTED, 1.4, 4)
            label = "loss.item() = %s" % num(MEANS_18A[b], 1)
            text(ax, x0 + w / 2, 35.6, label, size=15, ha="center", family=CODE, color=INK if done else MUTED)
            if done:
                text(ax, x0 + w / 2, 31.8, "%s × %d = %s" % (num(MEANS_18A[b], 1), n, num(sums[b], 1)), size=16,
                     ha="center", color=ORANGE, weight="bold")
        k = min(stage, 3)
        vals = [("loss_sum", num(acc_loss[k - 1], 1) if k else "0.0", ORANGE, ORANGE_L),
                ("total", str(acc_total[k - 1]) if k else "0", BLUE, BLUE_L),
                ("correct", str(acc_hits[k - 1]) if k else "0", GREEN, GREEN_L)]
        if stage <= 3:
            for j, (name, value, ec, fc) in enumerate(vals):
                x = 4 + j * 36
                box(ax, x, 9, 32, 15, "", fc=fc, ec=ec, lw=2.4)
                text(ax, x + 16, 20, name, size=17, ha="center", family=CODE, color=ec)
                text(ax, x + 16, 13.5, value, size=26, ha="center", weight="bold")
        elif stage == 4:
            box(ax, 4, 9, 50, 15, "", fc=ORANGE_L, ec=ORANGE, lw=2.4)
            text(ax, 29, 20, "epoch_loss = loss_sum / total", size=15, ha="center", family=CODE, color=ORANGE)
            text(ax, 29, 13.5, "10.0 ÷ 10 = %s" % num(epoch_loss, 1), size=22, ha="center", weight="bold")
            box(ax, 58, 9, 50, 15, "", fc=GREEN_L, ec=GREEN, lw=2.4)
            text(ax, 83, 20, "epoch_acc = correct / total", size=15, ha="center", family=CODE, color=GREEN)
            text(ax, 83, 13.5, "6 ÷ 10 = 0.6", size=22, ha="center", weight="bold")
        else:
            box(ax, 4, 9, 50, 15, "", fc=ORANGE_L, ec=ORANGE, lw=2.4)
            text(ax, 29, 20, "데이터 하나당 평균", size=16, ha="center", color=ORANGE)
            text(ax, 29, 13.5, "10.0 ÷ 10 = %s" % num(epoch_loss, 1), size=22, ha="center", weight="bold")
            box(ax, 58, 9, 50, 15, "", fc=NOTE, ec=LIGHT, lw=2.4)
            text(ax, 83, 20, "배치 평균의 평균", size=16, ha="center", color=INK)
            text(ax, 83, 13.5, "3.5 ÷ 3 ≈ %s" % num(by_batches, 2), size=22, ha="center", weight="bold")
        return image(fig)

    frames = [frame(s) for s in range(6)]
    return frames, [2200, 2500, 2500, 2500, 2200, 2500]


# 18a-4 외울 것 요약

@figure("18a-4", 560, 280)
def memo_18a():
    sums, acc_loss, acc_total, acc_hits, epoch_loss, by_batches, fit = _epoch()
    assert num(fit, 2) == "0.35"
    return summary("미니배치 학습 한 에폭", [
        ("학습 다섯 줄", ["`optimizer.zero_grad()`", "`out = model(x)`", "`loss = criterion(out, y)`", "`loss.backward()`",
                    "`optimizer.step()`", "zero_grad는 backward 앞\n또는 step 뒤"], PURPLE),
        ("평균 손실", ["`loss_sum += loss.item()`", "`           * x.size(0)`", "`loss_sum / total`",
                   "2.0 + 4.0 + 4.0 = 10.0", "10.0 ÷ 10 = 1.0"], ORANGE),
        ("맞힌 수와 정확도", ["`(out.argmax(1) == y)`", "`    .sum().item()`", "3 + 2 + 1 = 6", "6 ÷ 10 = 0.6",
                       ".item()이 없으면 텐서"], GREEN)],
        h=560, note_line="1차시 fit은 배치 평균의 합 3.5를 데이터 수 10으로 나눠 0.35를 찍습니다.", pad=1.0)


if __name__ == "__main__":
    from tools.ai_art.__main__ import main
    sys.exit(main(["l18"] + sys.argv[1:]))
