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
        text(ax, 60, 18, "이번 backward() 앞에서\n지난 배치의 기울기가 지워져 있으면 됩니다.", size=16, va="top")
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


# 18b~18e는 같은 숫자로 출력·정답·손실과 상태 변화를 비교함.

def _phase_table(title, heads, rows, foot="", widths=None, marked=()):
    """같은 항목의 행을 비교하는 표를 그림. marked는 강조할 (행, 열) 위치임."""
    plt, fig = new(560)
    ax = board(fig, 560)
    text(ax, 3, 51.5, title, size=22, weight="bold")
    widths = widths or [106 / len(heads)] * len(heads)
    assert len(widths) == len(heads) and abs(sum(widths) - 106) < 0.01
    assert all(len(row) == len(heads) for row in rows)
    x = 3
    for head, width in zip(heads, widths):
        box(ax, x, 39, width, 7, head, fc=NOTE, ec=GRID, size=18)
        x += width
    for r, row in enumerate(rows):
        x = 3
        for c, (value, width) in enumerate(zip(row, widths)):
            label = str(value).replace("-", MINUS) if isinstance(value, (int, float)) else str(value)
            box(ax, x, 32 - 7 * r, width, 7, label, fc=BLUE_L if (r, c) in marked else "white", ec=GRID, size=19)
            x += width
    if foot:
        text(ax, 3, 5, foot, size=17, va="center", bg=NOTE)
    return image(fig)


def _phase_flow(title, blocks, foot="", arrows=True):
    """コード와 숫자를 큰 글자 칸으로 연결함. blocks는 (제목, 줄 목록)임."""
    plt, fig = new(560)
    ax = board(fig, 560)
    text(ax, 3, 51.5, title, size=22, weight="bold")
    gap = 4
    width = (106 - gap * (len(blocks) - 1)) / len(blocks)
    for n, (head, lines) in enumerate(blocks):
        assert len(lines) <= 5
        x = 3 + n * (width + gap)
        box(ax, x, 11, width, 35, fc="white", ec=BLUE, lw=2)
        text(ax, x + width / 2, 41.5, head, size=20, ha="center", color=BLUE, weight="bold")
        for k, line in enumerate(lines):
            code = line.startswith("`")
            text(ax, x + width / 2, 35 - k * 4.7, line.strip("`"), size=18, ha="center", family=CODE if code else None)
        if arrows and n + 1 < len(blocks):
            arrow(ax, x + width + 0.3, 28, x + width + gap - 0.3, 28, color=LIGHT)
    if foot:
        text(ax, 3, 5, foot, size=17, bg=NOTE)
    return image(fig)


@figure("18b-1", 560, 280)
def eval_modes_18b():
    return _phase_table("층의 동작과 계산 기록을 따로 정합니다", ["호출", "층의 동작", "기울기 기록"],
                        [["model.train()", "학습용", "바꾸지 않음"], ["model.eval()", "평가용", "바꾸지 않음"],
                         ["no_grad()", "바꾸지 않음", "끄기"], ["eval + no_grad", "평가용", "끄기"]],
                        "평가에서는 backward와 step을 호출하지 않습니다.", marked=[(3, 1), (3, 2)])


@figure("18b-2", 560, 280)
def eval_mean_18b():
    sizes, means = [4, 2], [0.3, 0.9]
    sums = [n * mean for n, mean in zip(sizes, means)]
    total, mean = sum(sizes), sum(sums) / sum(sizes)
    assert total == 6 and math.isclose(sum(sums), 3) and math.isclose(mean, 0.5)
    return _phase_table("배치 평균을 데이터별 평균으로 모읍니다", ["배치 데이터 수", "배치 평균", "손실 합"],
                        [[4, "0.3", "1.2"], [2, "0.9", "1.8"], [6, "전체 평균 0.5", "합 3.0"]],
                        "(0.3 × 4 + 0.9 × 2) ÷ 6 = 0.5", marked=[(2, 1)])


@figure("18b-3", 560, 280)
def copy_state_18b():
    from copy import deepcopy
    state = {"w": [2]}
    shallow, separate = state.copy(), deepcopy(state)
    state["w"][0] = 3
    assert shallow["w"][0] == 3 and separate["w"][0] == 2
    return _phase_table("사전만 복사할 때와 값도 복사할 때를 비교합니다", ["모델 변화", "사전만 복사", "값도 복사"],
                        [["보관 시점: 2", 2, 2], ["다음 갱신: 3", 3, 2]],
                        "dict.copy()는 같은 저장소를 가리키고 deepcopy는 값을 따로 보관합니다.", marked=[(1, 2)])


def _best_trace_18b():
    losses = [0.8, 0.5, 0.6, 0.7]
    best, best_epoch, waiting = math.inf, None, 0
    trace = []
    for epoch, loss in enumerate(losses):
        if loss < best:
            best, best_epoch, waiting = loss, epoch, 0
        else:
            waiting += 1
        trace.append((epoch, loss, waiting, best_epoch))
        if waiting >= 2:
            break
    assert [row[2] for row in trace] == [0, 0, 1, 2]
    assert trace[-1][0] == 3 and best_epoch == 1 and best == 0.5
    return trace


@figure("18b-4", 560, 280)
def best_restore_18b():
    trace = _best_trace_18b()
    weights = [1, 2, 3, 4]
    assert weights[trace[-1][3]] == 2
    frames = []
    for stage in range(6):
        shown = min(stage, 3)
        rows = [[epoch, num(loss, 1) if epoch <= shown else "·", waiting if epoch <= shown else "·",
                 best_epoch if epoch <= shown else "·"] for epoch, loss, waiting, best_epoch in trace]
        if stage < 4:
            title = "개선하면 보관하고 개선이 없으면 횟수를 셉니다"
            current = trace[stage]
            foot = "epoch %d | waiting %d | 보관한 가중치 %d" % (current[0], current[2], weights[current[3]])
            marked = [(stage, c) for c in range(4)]
        elif stage == 4:
            title = "보관한 최고 모델 값을 다시 읽어 넣습니다"
            foot, marked = "load_state_dict(best_state): epoch 1의 가중치 2", [(1, c) for c in range(4)]
        else:
            title = "중단한 시점과 보관한 시점을 구별합니다"
            foot, marked = "중단: epoch 3 | 보관: epoch 1 | 되돌린 가중치: 2", [(1, c) for c in range(4)]
        frames.append(_phase_table(title, ["epoch", "검증 손실", "waiting", "최고 epoch"], rows, foot, marked=marked))
    return frames, [1800] * 5 + [2200]


@figure("18b-5", 560, 280)
def memo_18b():
    _best_trace_18b()
    assert math.isclose((4 * 0.3 + 2 * 0.9) / 6, 0.5)
    return _phase_flow("평가하고 개선한 상태를 보관합니다", [
        ("평가", ["`model.eval()`", "`no_grad()`", "역전파·갱신 없음"]),
        ("손실 합과 개수", ["1.2 + 1.8 = 3.0", "4 + 2 = 6", "3.0 ÷ 6 = 0.5"]),
        ("최고 상태", ["`deepcopy`", "patience 2", "epoch 1 값으로 복원"])])


@figure("18c-1", 560, 280)
def regression_pairs_18c():
    errors = [(out - target) ** 2 for out, target in zip([2, 4], [1, 5])]
    assert errors == [1, 1] and sum(errors) / 2 == 1
    return _phase_table("같은 데이터의 출력과 정답을 비교합니다", ["데이터", "예측", "정답", "제곱 차이"],
                        [[0, 2, 1, 1], [1, 4, 5, 1]], "(1 + 1) ÷ 2 = 1", marked=[(0, 3), (1, 3)])


@figure("18c-2", 560, 280)
def broadcast_pairs_18c():
    outputs, targets = [2, 4], [1, 5]
    correct = [(a - b) ** 2 for a, b in zip(outputs, targets)]
    all_pairs = [(a - b) ** 2 for a in outputs for b in targets]
    assert correct == [1, 1] and all_pairs == [1, 9, 9, 1]
    assert sum(correct) / 2 == 1 and sum(all_pairs) / 4 == 5
    frames = [
        _phase_table("예측값을 두 행에 놓습니다", ["데이터", "예측", "정답"], [[0, 2, "·"], [1, 4, "·"]], "out: [2, 1]"),
        _phase_table("정답도 같은 두 행에 놓습니다", ["데이터", "예측", "정답"], [[0, 2, 1], [1, 4, 5]], "target: [2, 1]"),
        _phase_table("같은 행의 차이를 제곱합니다", ["예측 − 정답", "제곱 차이", "비교한 수"], [["2 − 1", 1, 1], ["4 − 5", 1, 1]], "평균: (1 + 1) ÷ 2 = 1"),
        _phase_table("정답 [2]를 두면 모든 짝으로 늘어납니다", ["예측", "정답", "비교한 짝"], [[2, 1, "2와 1"], [2, 5, "2와 5"], [4, 1, "4와 1"], [4, 5, "4와 5"]], "뺄셈 결과: [2, 2]"),
        _phase_table("다른 데이터의 정답까지 비교합니다", ["예측", "정답", "제곱 차이"], [[2, 1, 1], [2, 5, 9], [4, 1, 9], [4, 5, 1]], "평균: (1 + 9 + 9 + 1) ÷ 4 = 5"),
        _phase_table("모양이 바뀌면 비교한 짝도 바뀝니다", ["정답 모양", "비교", "평균 손실"], [["[2, 1]", "같은 데이터끼리", 1], ["[2]", "모든 짝", 5]], "출력과 정답을 [2, 1]로 맞춥니다.", marked=[(0, 2)])]
    return frames, [1800] * 5 + [2200]


@figure("18c-3", 560, 280)
def full_batch_18c():
    epochs = list(range(3))
    assert epochs == [0, 1, 2] and len(epochs) == 3
    return _phase_flow("같은 두 행으로 반복하고 최종 출력을 구합니다", [
        ("epoch 0", ["x [2, 2]", "target [2, 1]", "갱신 1회"]),
        ("epoch 1", ["x [2, 2]", "target [2, 1]", "갱신 1회"]),
        ("epoch 2", ["x [2, 2]", "target [2, 1]", "갱신 1회"])], "갱신 3회 뒤 model(x)를 다시 계산해 prediction에 넣습니다.")


@figure("18c-4", 560, 280)
def memo_18c():
    assert sum([(2 - 1) ** 2, (4 - 5) ** 2]) / 2 == 1
    return _phase_flow("출력과 정답을 맞춘 뒤 전체 배치를 갱신합니다", [
        ("연속값", ["`Linear(2, 1)`", "`MSELoss()`", "확률 변환 없음"]),
        ("같은 데이터끼리", ["out [2, 1]", "target [2, 1]", "한 열로 비교"]),
        ("전체 배치", ["두 행 함께 사용", "출력 → 손실", "역전파 → 갱신"])])


def _binary_values_18d():
    logits = [-0.2, 0.0, 0.2]
    probs = [1 / (1 + math.exp(-z)) for z in logits]
    assert [int(z >= 0) for z in logits] == [0, 1, 1]
    assert [int(p >= 0.5) for p in probs] == [0, 1, 1]
    assert math.isclose(probs[1], 0.5)
    assert math.isclose(math.log1p(math.exp(-0.2)), 0.5981388693815918)
    return logits, probs


@figure("18d-1", 560, 280)
def binary_probs_18d():
    logits, probs = _binary_values_18d()
    rows = [[num(logits[n], 1), num(probs[n], 4), int(probs[n] >= 0.5)] for n in [0, 2]]
    return _phase_table("Sigmoid 확률을 BCELoss에 전달합니다", ["로짓", "확률", "예측"], rows,
                        "출력과 정답: float32[2, 1] | 정답: 0·1", marked=[(0, 1), (1, 1)])


@figure("18d-2", 560, 280)
def binary_pair_18d():
    _binary_values_18d()
    return _phase_flow("모델의 마지막과 손실을 함께 바꿉니다", [
        ("확률판", ["`Linear(2, 1)`", "`Sigmoid()`", "`BCELoss()`"]),
        ("로짓판", ["`Linear(2, 1)`", "Sigmoid를 뺌", "`BCEWithLogitsLoss()`"])], "두 판의 target은 float32[2, 1]입니다.", arrows=False)


@figure("18d-3", 560, 280)
def binary_threshold_18d():
    logits, probs = _binary_values_18d()
    return _phase_table("경계값 0도 클래스 1에 넣습니다", ["로짓", "Sigmoid 확률", "예측 클래스"],
                        [[num(z, 1), num(p, 4), int(z >= 0)] for z, p in zip(logits, probs)],
                        "로짓 ≥ 0  ↔  확률 ≥ 0.5", marked=[(1, 0), (1, 1), (1, 2)])


@figure("18d-4", 560, 280)
def memo_18d():
    _binary_values_18d()
    return _phase_table("출력·손실·예측 경계를 함께 기억합니다", ["모델 마지막", "손실", "예측 경계"],
                        [["Sigmoid 확률", "BCELoss", "0.5 이상 → 1"], ["Linear 로짓", "BCEWithLogitsLoss", "0 이상 → 1"]],
                        "정답은 두 판 모두 float32[배치, 1]입니다.", widths=[30, 46, 30])


def _multi_values_18e():
    scores, labels = [[1, 0, -1], [-1, 0, 2]], [0, 2]
    probabilities, logs, losses = [], [], []
    for row, label in zip(scores, labels):
        maximum = max(row)
        logsum = maximum + math.log(sum(math.exp(x - maximum) for x in row))
        logrow = [x - logsum for x in row]
        logs.append(logrow)
        probabilities.append([math.exp(value) for value in logrow])
        losses.append(-logrow[label])
    mean = sum(losses) / 2
    assert [row.index(max(row)) for row in scores] == labels
    assert math.isclose(mean, 0.2887259920013329)
    assert math.isclose(sum(probabilities[0]), 1) and math.isclose(sum(probabilities[1]), 1)
    return scores, labels, probabilities, logs, losses, mean


@figure("18e-1", 560, 280)
def multiclass_rows_18e():
    scores, labels, _, _, _, _ = _multi_values_18e()
    rows = [[n] + row + [labels[n]] for n, row in enumerate(scores)]
    return _phase_table("각 행에서 정답 클래스 열을 지정합니다", ["데이터", "클래스 0", "클래스 1", "클래스 2", "정답"], rows,
                        "출력 [2, 3] | 정답 long[2]의 [0, 2]", widths=[16, 24, 24, 24, 18], marked=[(0, 1), (1, 3)])


@figure("18e-2", 560, 280)
def multiclass_loss_18e():
    scores, labels, probs, logs, losses, mean = _multi_values_18e()
    heads, widths, marked = ["데이터", "클래스 0", "클래스 1", "클래스 2", "정답"], [16, 24, 24, 24, 18], [(0, 1), (1, 3)]
    frames = []
    for title, values, foot in [
            ("같은 로짓과 정답 번호를 준비합니다", scores, "첫 행은 0번 열, 둘째 행은 2번 열을 고릅니다."),
            ("정답 열의 확률을 확인합니다", probs, "정답 확률: 약 0.6652·0.8438"),
            ("로그확률에서 정답 열을 고릅니다", logs, "정답 로그확률: 약 −0.4076·−0.1698")]:
        rows = [[n] + [num(v, 4) for v in row] + [labels[n]] for n, row in enumerate(values)]
        frames.append(_phase_table(title, heads, rows, foot, widths=widths, marked=marked))
    frames.append(_phase_table("정답 로그확률의 부호를 바꿉니다", ["데이터", "정답 로그확률", "손실"],
                               [[n, num(logs[n][labels[n]], 4), num(losses[n], 4)] for n in range(2)], "마이너스를 붙여 데이터별 손실을 구합니다."))
    frames.append(_phase_table("데이터 두 개의 손실을 평균합니다", ["데이터 0 손실", "데이터 1 손실", "평균"],
                               [[num(losses[0], 4), num(losses[1], 4), num(mean, 4)]], "반올림 전 값으로 평균합니다.", marked=[(0, 2)]))
    frames.append(_phase_flow("같은 로짓을 손실 두 판에서 사용합니다", [
        ("로짓", ["`CrossEntropyLoss`", "평균 손실 0.2887"]),
        ("로그확률", ["`LogSoftmax(dim=1)`", "`NLLLoss`", "평균 손실 0.2887"])], "target은 두 판 모두 long[2]의 [0, 2]입니다.", arrows=False))
    assert len(frames) == 6
    return frames, [1800] * 5 + [2200]


@figure("18e-3", 560, 280)
def multiclass_shapes_18e():
    scores, labels, _, _, _, _ = _multi_values_18e()
    assert len(scores) == 2 and len(scores[0]) == 3 and len(labels) == 2
    return _phase_flow("클래스 열을 고르면 데이터별 번호가 남습니다", [
        ("입력", ["x [2, 2]", "데이터 2개"]),
        ("출력", ["out [2, 3]", "클래스 열 3개"]),
        ("예측", ["`argmax(1)`", "번호 [0, 2]", "모양 [2]"])], "이번 배치에 1번 정답이 없어도 모델의 출력 열은 3개입니다.")


@figure("18e-4", 560, 280)
def memo_18e():
    _multi_values_18e()
    return _phase_table("모델의 마지막과 손실을 짝지어 기억합니다", ["모델 마지막", "손실", "정답"],
                        [["Linear 로짓", "CrossEntropyLoss", "long[배치]"], ["LogSoftmax(1)", "NLLLoss", "long[배치]"]],
                        "두 판 모두 argmax(1)로 예측 클래스 번호를 고릅니다.", widths=[32, 42, 32])


# 18f~18h는 배치 축·항목 묶기·학습 대상을 같은 예로 확인함.

def _shapes_18f():
    def conv(n):
        return (n + 2 * 1 - 1 * (3 - 1) - 1) // 1 + 1
    def pool(n):
        return (n - 2) // 2 + 1
    shapes = [(2, 1, 8, 8), (2, 4, conv(8), conv(8)), (2, 4, pool(8), pool(8)),
              (2, 8, conv(4), conv(4)), (2, 8, pool(4), pool(4))]
    assert shapes == [(2, 1, 8, 8), (2, 4, 8, 8), (2, 4, 4, 4), (2, 8, 4, 4), (2, 8, 2, 2)]
    assert math.prod(shapes[-1][1:]) == 32
    assert math.prod(shapes[-1]) == 64
    return [str(list(s)).replace(' ', '') for s in shapes]


@figure('18f-1', 560, 280)
def module_18f():
    assert 1 * 8 * 8 == 64 and len([0, 1, 2]) == 3
    return _phase_flow('층을 등록한 뒤 입력이 지나는 순서를 적습니다', [
        ('__init__', ['`super().__init__()`', '`self.fc = nn.Linear(64,3)`', '기반 초기화 → 층 등록']),
        ('forward', ['입력 [2,1,8,8]', '펼친 값 [2,64]', '로짓 [2,3]'])], '실제 사용은 model(x)로 호출합니다.', arrows=False)


@figure('18f-2', 560, 280)
def conv_pool_18f():
    shapes = _shapes_18f()
    return _phase_table('앞 층의 채널과 다음 층의 입력을 맞춥니다', ['층', '채널', '공간 크기', '출력 모양'],
                        [['첫 합성곱', '1 → 4', '8 → 8', shapes[1]], ['첫 풀링', '4 유지', '8 → 4', shapes[2]],
                         ['둘째 합성곱', '4 → 8', '4 → 4', shapes[3]], ['둘째 풀링', '8 유지', '4 → 2', shapes[4]]],
                        '합성곱: kernel 3·padding 1·stride 1 | 풀링: kernel 2·stride 2', widths=[25, 20, 24, 37])


@figure('18f-3', 560, 280)
def shape_flow_18f():
    shapes = _shapes_18f()
    rows = list(zip(['첫 합성곱', '첫 풀링', '둘째 합성곱', '둘째 풀링'], shapes[:-1], shapes[1:]))
    frames = []
    for n in range(4):
        visible = [list(row) if i <= n else [row[0], '·', '·'] for i, row in enumerate(rows)]
        frames.append(_phase_table('이미지 두 개의 모양을 차례로 계산합니다', ['층', '입력', '출력'], visible,
                                   '0번 축의 이미지 수 2를 유지합니다.', widths=[28, 39, 39], marked=[(n, 2)]))
    frames.append(_phase_table('한 이미지의 특징만 한 행으로 펼칩니다', ['대상', '모양', '한 이미지의 특징 수'],
                               [['특징 추출 뒤', shapes[-1], '8 × 2 × 2 = 32'], ['flatten 시작 축 1', '[2,32]', 32]],
                               '기본 flatten 시작 축 0은 이미지까지 합쳐 [64]로 만듭니다.', widths=[34, 31, 41]))
    frames.append(_phase_flow('이미지 구분을 유지한 채 클래스별 점수를 냅니다', [
        ('입력 이미지', [shapes[0], '이미지 2개', '8×8 흑백']),
        ('특징', [shapes[-1], '[2,32]로 펼침', '한 이미지당 32개']),
        ('분류기', ['`Linear(32,3)`', '로짓 [2,3]', '클래스 0·1·2'])]))
    return frames, [1800] * 5 + [2200]


@figure('18f-4', 560, 280)
def classifier_18f():
    assert 1 * 8 * 8 == 64 and 8 * 2 * 2 == 32
    return _phase_table('특징 수에 맞춰 분류기 입력을 정합니다', ['모델', '한 이미지의 특징', '분류기', '로짓'],
                        [['한 층', 64, 'Linear(64,3)', '[2,3]'], ['CNN', 32, 'Linear(32,3)', '[2,3]']],
                        '두 모델 모두 정답은 long[2] | CrossEntropyLoss에는 로짓을 전달합니다.', widths=[20, 30, 34, 22])


@figure('18f-5', 560, 280)
def memo_18f():
    _shapes_18f()
    return _phase_flow('등록한 층을 지나 클래스별 로짓을 돌려줍니다', [
        ('층 등록', ['`nn.Module`', '`super().__init__()`', 'self에 층을 붙임']),
        ('계산 순서', ['`forward`', '특징 추출', '배치 축을 남겨 펼침']),
        ('출력', ['`self.fc(x)`', '로짓 [2,3]', '클래스별 점수'])])


def _batches_18g():
    labels = [0, 2, 1]
    indices = [list(range(i, min(i + 2, len(labels)))) for i in range(0, len(labels), 2)]
    values = [[labels[i] for i in batch] for batch in indices]
    assert indices == [[0, 1], [2]] and values == [[0, 2], [1]]
    assert sum(map(len, indices)) == 3 and len(indices) == 2
    return indices, values


@figure('18g-1', 560, 280)
def pairs_18g():
    _, values = _batches_18g()
    assert values[0][1] == 2
    return _phase_table('같은 인덱스의 이미지와 정답을 읽습니다', ['인덱스', '이미지 경로 위치', '정답'],
                        [[0, '첫 번째', 0], [1, '두 번째', 2], [2, '세 번째', 1]],
                        'len(data)는 항목 수 3 | data[1]은 두 번째 이미지와 정답 2', marked=[(1, 1), (1, 2)])


@figure('18g-2', 560, 280)
def image_item_18g():
    assert 3 * 8 * 8 == 192
    return _phase_flow('한 이미지와 같은 인덱스의 라벨을 반환합니다', [
        ('이미지 읽기', ['인덱스 1', '8×8 PNG', 'RGB 채널로 맞춤']),
        ('텐서 변환', ['`ToTensor()`', '[3,8,8]', 'float32·0~1']),
        ('항목 반환', ['이미지 텐서 x', '정수 라벨 2', '`return x, 2`'])], 'RGB 이미지의 0~255 값을 0~1로 바꿉니다.')


@figure('18g-3', 560, 280)
def batch_flow_18g():
    indices, values = _batches_18g()
    frames = [
        _phase_table('항목 세 개를 원래 순서대로 놓습니다', ['항목 인덱스', '정답', '배치 배정'],
                     [[0, 0, '·'], [1, 2, '·'], [2, 1, '·']], 'batch_size=2 | shuffle=False | drop_last=False'),
        _phase_table('항목 두 개를 첫 배치에 넣습니다', ['항목 인덱스', '정답', '배치 배정'],
                     [[0, 0, '첫 배치'], [1, 2, '첫 배치'], [2, 1, '아직 남음']], '첫 배치 인덱스: [0,1]', marked=[(0, 2), (1, 2)]),
        _phase_table('앞에 배치 축을 더해 두 항목을 모읍니다', ['항목', '모양', '자료형·값'],
                     [['이미지 x', '[2,3,8,8]', 'float32'], ['정답 y', '[2]', 'long·[0,2]']], '이미지 두 개와 정답 두 개를 함께 사용합니다.'),
        _phase_table('남은 항목도 마지막 배치에 넣습니다', ['항목 인덱스', '정답', '배치 배정'],
                     [[0, 0, '첫 배치'], [1, 2, '첫 배치'], [2, 1, '마지막 배치']], 'drop_last=False가 남은 한 항목을 사용합니다.', marked=[(2, 2)]),
        _phase_table('마지막 배치의 축 길이는 1입니다', ['항목', '모양', '자료형·값'],
                     [['이미지 x', '[1,3,8,8]', 'float32'], ['정답 y', '[1]', 'long·[1]']], '배치 크기를 채우지 못해도 항목을 제외하지 않습니다.'),
        _phase_table('전체 항목 수와 배치 수를 구별합니다', ['배치', '항목 인덱스', '정답', '항목 수'],
                     [['첫 배치', str(indices[0]), str(values[0]), 2], ['마지막 배치', str(indices[1]), str(values[1]), 1]],
                     '전체 항목: 2 + 1 = 3 | 전체 배치: 2개')]
    return frames, [1800] * 5 + [2200]


@figure('18g-4', 560, 280)
def dataset_forms_18g():
    assert len(['TensorDataset', 'PictureData', 'ImageFolder']) == 3
    return _phase_table('저장한 형태에 맞춰 한 항목을 읽습니다', ['준비한 데이터', '읽는 클래스', '한 항목 반환'],
                        [['이미지·라벨 텐서', 'TensorDataset', '같은 첫 축의 쌍'], ['경로·라벨 목록', 'PictureData', '같은 인덱스의 쌍'],
                         ['클래스 이름 폴더', 'ImageFolder', '이미지·폴더 라벨']],
                        'ImageFolder의 실제 클래스 번호는 data.class_to_idx에서 확인합니다.', widths=[34, 35, 37])


@figure('18g-5', 560, 280)
def memo_18g():
    _batches_18g()
    return _phase_flow('항목을 읽은 뒤 배치 규칙으로 묶습니다', [
        ('Dataset', ['`__len__`', '항목 수 3', '`__getitem__`', '이미지·라벨 한 쌍']),
        ('DataLoader', ['최대 2개씩', '순서를 유지함', '마지막 1개도 사용함', '배치 수 2']),
        ('클래스 폴더', ['`ImageFolder`', '폴더 이름 → 번호', '`class_to_idx`'])], arrows=False)


def _running_mean_18h():
    old, batch, momentum = 0.0, 2.0, 0.1
    updated = (1 - momentum) * old + momentum * batch
    assert math.isclose(updated, 0.2)
    return old, batch, momentum, updated


@figure('18h-1', 560, 280)
def replace_head_18h():
    assert len([0, 1, 2]) == 3
    return _phase_flow('본체를 동결한 다음 새 분류기를 만듭니다', [
        ('새 모델 동결', ['`parameters()`', '원래 파라미터 순회', '`requires_grad=False`']),
        ('fc 교체', ['`fc.in_features`', '입력 특징 수를 읽음', '새 출력 수 3']),
        ('새 fc', ['기울기 계산 켜짐', '`fc.parameters()`', '이 파라미터로 opt 생성'])])


@figure('18h-2', 560, 280)
def strategy_18h():
    chosen = [set(['fc']), set(['layer4', 'fc']), set(['stem', 'layer1', 'layer2', 'layer3', 'layer4', 'fc'])]
    assert chosen[0] < chosen[1] < chosen[2]
    return _phase_table('기울기 계산과 최적화 대상을 함께 맞춥니다', ['판', '기울기를 계산할 부분', 'opt가 받을 부분'],
                        [['마지막 층', 'fc', 'fc'], ['일부 해제', 'layer4 + fc', 'layer4 + fc'], ['전체 학습', '모든 파라미터', '모든 파라미터']],
                        '기울기를 구해도 opt가 받지 않은 파라미터는 그 opt가 갱신하지 않습니다.', widths=[26, 40, 40])


@figure('18h-3', 560, 280)
def batchnorm_mode_18h():
    old, batch, momentum, updated = _running_mean_18h()
    frames = [
        _phase_table('동결한 층의 이동 평균을 따로 확인합니다', ['대상', '시작 값', '설정'],
                     [['저장한 이동 평균', num(old, 1), 'track_running_stats=True'], ['이번 배치 평균', num(batch, 1), 'momentum=0.1']],
                     '예의 파라미터 requires_grad=False | 모델의 실제 측정값이 아닙니다.', widths=[36, 20, 50]),
        _phase_table('학습 모드에서는 이동 통계도 갱신합니다', ['파라미터 기울기', '층 모드', '이동 평균 갱신'],
                     [['False', 'train', '갱신함']], '파라미터 동결은 버퍼의 갱신을 멈추지 않습니다.'),
        _phase_flow('이번 배치 평균을 0.1만큼 반영합니다', [
            ('기존 평균 몫', ['0.9 × 0', '= 0']), ('이번 평균 몫', ['0.1 × 2', '= 0.2']),
            ('새 이동 평균', [num(updated, 1), '두 몫을 더함'])], '새 이동 평균: 0.9 × 0 + 0.1 × 2 = 0.2', arrows=False),
        _phase_table('같은 시작 값에서 평가 모드로 비교합니다', ['시작 이동 평균', '층 모드', '순전파 뒤 이동 평균'],
                     [[num(old, 1), 'eval', num(old, 1)]], '저장한 통계를 사용하고 이동 통계를 갱신하지 않습니다.'),
        _phase_flow('매 에폭 동결한 층의 모드를 다시 정합니다', [
            ('전체 모델', ['`model.train()`', '안쪽 층도 학습 모드']),
            ('동결한 BatchNorm2d', ['`layer.eval()`', '저장한 통계 사용'])], '기울기를 계산할 BatchNorm2d는 학습 모드를 유지합니다.'),
        _phase_table('같은 초기 상태에서 층 모드만 비교합니다', ['requires_grad', '층 모드', '시작 평균', '순전파 뒤 평균'],
                     [['False', 'train', 0, num(updated, 1)], ['False', 'eval', 0, num(old, 1)]],
                     'track_running_stats=True | 배치 평균 2·momentum 0.1', widths=[29, 20, 24, 33])]
    return frames, [1800] * 5 + [2200]


@figure('18h-4', 560, 280)
def epoch_mode_18h():
    assert list(range(2)) == [0, 1]
    return _phase_flow('준비 뒤 매 에폭에서 모드와 배치를 처리합니다', [
        ('처음 준비', ['본체 동결', 'fc 교체', '학습할 params 선택', 'opt 생성']),
        ('매 에폭 시작', ['`model.train()`', '동결한 BatchNorm2d', '`layer.eval()`']),
        ('배치 반복', ['기울기 비우기', '순전파 → 손실', '역전파 → 갱신'])], 'model.train을 다시 부르면 동결한 층의 eval도 그 뒤에 적용합니다.')


@figure('18h-5', 560, 280)
def memo_18h():
    _running_mean_18h()
    return _phase_table('분류기 입력과 학습할 부분을 확인합니다', ['확인할 부분', '이 예의 코드·선택'],
                        [['새 fc의 입력 수', 'model.fc.in_features'], ['일부 해제의 최적화 대상', 'layer4 + fc'],
                         ['전체 학습의 최적화 대상', 'model.parameters()'], ['동결한 BatchNorm2d', '매 train 뒤 layer.eval()']], widths=[45, 61])



if __name__ == "__main__":
    from tools.ai_art.__main__ import main
    sys.exit(main(["l18"] + sys.argv[1:]))
