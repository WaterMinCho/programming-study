#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""8차시 학습 노트 l08 의 그림(8a 이진 분류와 로지스틱 회귀, 8b 데이터 나누기와 정확도, 8c 결정 경계, 8d 두 손실 방식,
8e 사기 거래 데이터와 pos_weight, 8f 혼동 행렬과 지표, 8g 코드 읽기).

그림에 찍는 숫자는 모두 이 파일에서 numpy 로 다시 계산하고 assert 로 확인함. iris 앞 100송이의 꽃받침 길이·폭은 8차시
노트북 01 [15] 에 저장된 출력을 옮긴 것이고(Fisher 의 iris 자료), 학습·검증 분할은 scikit-learn ShuffleSplit 과 같은 방법
(RandomState(42).permutation 앞 30개가 검증, 다음 70개가 학습)으로 따라 함. 학습은 노트북 01 [43]~[45] 와 같은 설정
(처음 값 1, SGD 학습률 0.01, 10,000번)을 numpy 로 다시 계산했고 노트북 출력 0.52857, 0.43333, 0.08318, b −0.1045,
w [2.951, −5.115] 와 맞춤. 사기 거래 숫자는 노트북 02 [7]·[41]~[44] 출력 9,461, 539, [[1849, 43], [19, 89]] 에서 계산함.

  python -m tools.ai_art l08                 ai/learn/l08/assets/ 에 그림을 모두 쓰고 manifest 를 고침
  python -m tools.ai_art l08 8c-1            이름을 적은 그림만

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
SLATE, SLATE_L, YELLOW = "#3d6187", "#e0e8f0", "#fde68a"
CODE = "D2Coding"
# 단원마다 한 색은 한 뜻이고, 뜻은 그 그림의 캡션에 적음. 그림 안 설명 글은 회색(NOTE) 바탕이고 뜻이 없음
# 차시 전체: 파랑은 클래스 0(품종 0, 정상 거래), 주황은 클래스 1(품종 1, 사기 거래)
# 8a: 회색 곡선은 시그모이드, 노랑은 따라가는 꽃 (4.8, 3.4)
# 8b: 슬레이트는 학습 데이터, 보라는 검증 데이터, 초록은 맞힌 예측, 빨강은 틀린 예측, 회색 점선은 임계값 0.5
# 8c: 검은 선은 결정 경계, 슬레이트는 학습 데이터 곡선, 보라는 검증 데이터 곡선, 노랑은 따라가는 꽃
# 8d: 회색 상자는 시그모이드, 초록 테두리는 BCEWithLogitsLoss 방식, 빨강은 logit 에 0.5 기준을 쓴 잘못된 판정
# 8e: 슬레이트는 학습 데이터, 보라는 테스트 데이터, 회색은 stratify 없이 나눈 예
# 8f: 초록은 맞힌 칸, 빨강은 틀린 칸, 노란 테두리는 그 지표가 쓰는 칸, 보라는 점수로 그린 ROC 곡선, 빨강 점선은 0/1 로 그린 곡선
# 8g: 초록은 True, 빨강은 False, 슬레이트는 학습 손실, 보라는 검증 손실
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


def comma(v):
    return f"{v:,}"


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


def box(ax, x0, y0, w, h, edge=INK, fill="white", lw=2.2, z=2):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0.04", fc=fill, ec=edge, lw=lw, zorder=z))


def arrow(ax, x0, y0, x1, y1, color=MUTED, lw=2.2, z=3):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                                                  mutation_scale=22), zorder=z)


def card(ax, x0, y0, w, h, title, lines, edge, ink=INK, fill="white", size=17, title_size=20, code_lines=()):
    """둥근 상자 하나. lines 는 위에서부터 한 줄씩. code_lines 에 든 번호의 줄은 D2Coding 으로 씀."""
    box(ax, x0, y0, w, h, edge=edge, fill=fill)
    ax.text(x0 + 0.18, y0 + h - 0.32, title, ha="left", va="center", fontsize=title_size, weight="bold", color=ink,
            zorder=3)
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


# 공용 계산

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.asarray(z, float)))


def bce_logit(z, t):
    z = np.asarray(z, float)
    return float(np.mean(np.maximum(z, 0) - z * t + np.log1p(np.exp(-np.abs(z)))))


# iris 앞 100송이의 꽃받침 길이·폭(×10). 앞 50송이가 품종 0(setosa), 뒤 50송이가 품종 1(versicolor)
_L0 = ("51,35 49,30 47,32 46,31 50,36 54,39 46,34 50,34 44,29 49,31 54,37 48,34 48,30 43,30 58,40 57,44 54,39 51,35 "
       "57,38 51,38 54,34 51,37 46,36 51,33 48,34 50,30 50,34 52,35 52,34 47,32 48,31 54,34 52,41 55,42 49,31 50,32 "
       "55,35 49,36 44,30 51,34 50,35 45,23 44,32 50,35 51,38 48,30 51,38 46,32 53,37 50,33")
_L1 = ("70,32 64,32 69,31 55,23 65,28 57,28 63,33 49,24 66,29 52,27 50,20 59,30 60,22 61,29 56,29 67,31 56,30 58,27 "
       "62,22 56,25 59,32 61,28 63,25 61,28 64,29 66,30 68,28 67,30 60,29 57,26 55,24 55,24 58,27 60,27 54,30 60,34 "
       "67,31 63,23 56,30 55,25 55,26 61,30 58,26 50,23 56,27 57,30 57,29 62,29 51,25 57,28")
IRIS = np.array([[int(a) / 10.0, int(b) / 10.0] for a, b in (p.split(",") for p in (_L0 + " " + _L1).split())])
IRIS_Y = np.array([0.0] * 50 + [1.0] * 50)
assert IRIS.shape == (100, 2)
_PERM = np.random.RandomState(42).permutation(100)
TEST, TRAIN = _PERM[:30], _PERM[30:]
XTR, YTR, XTE, YTE = IRIS[TRAIN], IRIS_Y[TRAIN], IRIS[TEST], IRIS_Y[TEST]
assert XTR.shape == (70, 2) and XTE.shape == (30, 2)
assert tuple(XTR[0]) == (4.8, 3.4) and YTR[0] == 0
assert int(YTR.sum()) == 37 and int(YTE.sum()) == 13
FLOWER = np.array([4.8, 3.4])


def train(epochs=10000, lr=0.01, keep=()):
    """노트북 01 [43]~[45] 의 학습(처음 값 1, 전체 데이터로 SGD)을 numpy 로. 반복마다 (학습 손실·정확도는 갱신 전,
    검증 손실·정확도는 갱신 뒤, 갱신 전 검증 손실) 을 남김. keep 에 든 반복 수만큼 갱신한 뒤의 (w, b) 도 돌려줌."""
    w, b = np.array([1.0, 1.0]), 1.0
    rows, snaps = [], {}
    for ep in range(epochs):
        if ep in keep:
            snaps[ep] = (w.copy(), b)
        z = XTR @ w + b
        p = sigmoid(z)
        before = bce_logit(XTE @ w + b, YTE)
        g = p - YTR
        tr_loss, tr_acc = bce_logit(z, YTR), float(np.mean((p >= 0.5) == YTR))
        w = w - lr * (XTR.T @ g) / len(YTR)
        b = b - lr * g.mean()
        zt = XTE @ w + b
        rows.append((tr_loss, tr_acc, bce_logit(zt, YTE), float(np.mean((zt >= 0) == YTE)), before))
    if epochs in keep:
        snaps[epochs] = (w.copy(), b)
    return np.array(rows), snaps, w, b


HIST, SNAPS, W_END, B_END = train(keep=(0, 200, 300, 400, 500, 1000, 10000))
assert fx(HIST[0, 0], 5) == "4.41009" and fx(HIST[0, 1], 5) == "0.52857" and fx(HIST[0, 3], 5) == "0.43333"
assert fx(HIST[0, 4], 5) == "5.43341" and fx(HIST[-1, 2], 5) == "0.08318" and fx(HIST[9000, 2], 5) == "0.08904"
assert fx(B_END, 4) == M + "0.1045" and fx(W_END[0], 3) == "2.951" and fx(W_END[1], 3) == M + "5.115"
W_NB, B_NB = np.array([2.951, -5.115]), -0.1045


def boundary_x2(x1, w, b):
    return -(b + w[0] * x1) / w[1]


assert fx(boundary_x2(4.4, W_NB, B_NB), 3) == "2.518" and fx(boundary_x2(6.8, W_NB, B_NB), 3) == "3.903"
assert fx(boundary_x2(4.8, W_NB, B_NB), 3) == "2.749"
Z_INIT = float(FLOWER @ np.ones(2) + 1)
Z_LEARN = float(FLOWER @ W_NB + B_NB)
assert abs(Z_INIT - 9.2) < 1e-9 and fx(sigmoid(Z_INIT), 4) == "0.9999"
assert fx(Z_LEARN, 2) == M + "3.33" and fx(sigmoid(Z_LEARN), 4) == "0.0345"

# 8b 정확도 예: 다섯 송이의 p 와 정답
P5 = np.array([0.8, 0.3, 0.6, 0.2, 0.9])
Y5 = np.array([1, 0, 0, 0, 1])
PRED5 = np.where(P5 < 0.5, 0, 1)
assert PRED5.tolist() == [1, 0, 1, 0, 1] and (PRED5 == Y5).sum() == 4 and (PRED5 == Y5).mean() == 0.8
# 8b 부트스트래핑 예: 데이터 0~9 에서 10번 복원 추출한 결과(이 노트가 정한 예)
DRAWS = [3, 7, 3, 0, 9, 5, 7, 2, 3, 1]
NEVER = sorted(set(range(10)) - set(DRAWS))
assert NEVER == [4, 6, 8] and DRAWS.count(3) == 3 and DRAWS.count(7) == 2
# 8e 사기 거래
N0, N1 = 9461, 539
PW = N0 / N1
assert fx(PW, 2) == "17.55" and abs(N1 * PW - N0) < 1e-9
L_POS = math.log1p(math.exp(1.0))
assert fx(L_POS, 4) == "1.3133" and fx(L_POS * PW, 2) == "23.05"
SPLITS = [int(v) for v in (lambda r: [r.hypergeometric(N1, N0, 2000) for _ in range(5)])(np.random.RandomState(7))]
assert SPLITS == [116, 108, 94, 108, 115]
# 8f 혼동 행렬(scikit-learn 배치)
TN, FP, FN, TP = 1849, 43, 19, 89
ACC, PREC, REC = (TP + TN) / 2000, TP / (TP + FP), TP / (TP + FN)
F1 = 2 * TP / (2 * TP + FP + FN)
assert (fx(ACC, 3), fx(PREC, 4), fx(REC, 4), fx(F1, 4)) == ("0.969", "0.6742", "0.8241", "0.7417")
assert TN + FP == 1892 and FN + TP == 108 and fx((TN + FP) / 2000, 3) == "0.946"
# 8f ROC 예: 거래 10건(사기 3, 정상 7)의 점수
SC_POS = [0.92, 0.61, 0.38]
SC_NEG = [0.71, 0.45, 0.30, 0.22, 0.15, 0.08, 0.04]


def roc_points(pos, neg):
    """임계값을 점수마다 내리며 (FPR, TPR) 목록. score >= 임계값이면 양성."""
    th = sorted(set(pos + neg), reverse=True)
    pts = [(0.0, 0.0)]
    for t in th:
        pts.append((sum(s >= t for s in neg) / len(neg), sum(s >= t for s in pos) / len(pos)))
    return pts


def area(pts):
    return sum((x1 - x0) * (y0 + y1) / 2 for (x0, y0), (x1, y1) in zip(pts, pts[1:]))


ROC = roc_points(SC_POS, SC_NEG)
AUC_P = area(ROC)
PAIRS = sum(p > n for p in SC_POS for n in SC_NEG)
assert PAIRS == 18 and abs(AUC_P - 18 / 21) < 1e-12 and fx(AUC_P, 3) == "0.857"
CUT = [(0.0, 0.0), (1 / 7, 2 / 3), (1.0, 1.0)]
AUC_01 = area(CUT)
assert abs(AUC_01 - 16 / 21) < 1e-12 and fx(AUC_01, 3) == "0.762"


# 8a

@figure("8a-1", 560, 270)
def three_kinds():
    """세 문제의 답 꼴: 회귀, 이진 분류, 다중 분류와 이 단원 낱말."""
    plt, fig, ax = board(540)
    head(fig, "답이 어떤 꼴인가로 문제를 나눕니다", y=0.94)
    specs = [
        (0.25, "회귀", ["택배 상자 무게 맞히기", "답: 1,240 g 처럼", "크기가 이어지는 숫자"], MUTED),
        (3.95, "이진 분류", ["결제가 사기인지 가리기", "답: 0 정상 또는 1 사기", "클래스 2개"], INK),
        (7.65, "다중 분류", ["과일 사진이 무엇인지", "답: 사과, 배, 귤 중 하나", "클래스 3개"], MUTED),
    ]
    for x0, title, lines, edge in specs:
        card(ax, x0, 1.55, 3.3, 2.75, title, lines, edge, size=17)
    for k, (txt, col) in enumerate((("0", BLUE), ("1", ORANGE))):
        ax.text(5.75 + k * 0.62, 1.85, txt, ha="center", va="center", fontsize=19, color="white", weight="bold",
                zorder=5, bbox=dict(boxstyle="circle,pad=0.25", fc=col, ec=col))
    note(ax, 5.6, 0.7, "이 단원의 낱말: 이진 분류 · 클래스 0 과 1 · 시그모이드 · 로지스틱 회귀 · 임계값", size=17, ha="center")
    return image(fig)


@figure("8a-2", 560, 300)
def iris_scatter():
    """iris 앞 100송이를 꽃받침 길이·폭으로 찍은 산점도와 따라갈 꽃 (4.8, 3.4)."""
    assert int((IRIS_Y == 0).sum()) == 50 and int((IRIS_Y == 1).sum()) == 50
    assert any((IRIS[k] == FLOWER).all() and IRIS_Y[k] == 0 for k in range(100))
    plt, fig = new(600)
    ax = fig.add_axes([0.08, 0.14, 0.56, 0.8])
    tidy(ax)
    a, b = IRIS[IRIS_Y == 0], IRIS[IRIS_Y == 1]
    ax.scatter(a[:, 0], a[:, 1], marker="x", s=70, color=BLUE, lw=2.2, zorder=4)
    ax.scatter(b[:, 0], b[:, 1], marker="o", s=60, facecolors="none", edgecolors=ORANGE, lw=2.2, zorder=4)
    ax.scatter([FLOWER[0]], [FLOWER[1]], s=520, color=YELLOW, zorder=3)
    ax.set_xlim(4.1, 7.3)
    ax.set_ylim(1.8, 4.7)
    ax.set_xlabel("꽃받침 길이 x1")
    ax.set_ylabel("꽃받침 폭 x2")
    note(ax, 4.2, 4.55, "품종 0 50송이", color=BLUE, size=17, weight="bold")
    note(ax, 6.0, 1.94, "품종 1 50송이", color=ORANGE, size=17, weight="bold")
    note(fig, 0.67, 0.72, "iris.data  (150, 4)", size=18, family=CODE, transform=fig.transFigure)
    note(fig, 0.67, 0.56, "iris.data[:100, :2]", size=18, family=CODE, transform=fig.transFigure)
    note(fig, 0.67, 0.42, "→ (100, 2)", size=18, family=CODE, transform=fig.transFigure)
    note(fig, 0.67, 0.28, "앞 100송이, 앞 두 특징", size=17, transform=fig.transFigure)
    note(fig, 0.67, 0.14, "노란 원: (4.8, 3.4), 정답 0", size=17, bg=HL, transform=fig.transFigure)
    return image(fig)


@figure("8a-3", 560, 290)
def model_flow():
    """꽃 (4.8, 3.4) 가 Linear 층과 시그모이드를 지나는 흐름. 처음 값과 학습한 값 두 줄."""
    rows = [("처음 값  w = [1, 1], b = 1", fx(Z_INIT, 1), fx(sigmoid(Z_INIT), 4)),
            ("학습한 값  w = [2.951, " + M + "5.115], b = " + M + "0.1045", fx(Z_LEARN, 2), fx(sigmoid(Z_LEARN), 4))]
    assert rows[0][1:] == ("9.2", "0.9999") and rows[1][1:] == (M + "3.33", "0.0345")

    def draw(stage):
        plt, fig, ax = board(580)
        head(fig, "입력 x 가 nn.Linear(2, 1) 과 nn.Sigmoid() 를 지납니다", y=0.95)
        xs = [(0.3, 2.0, "입력 x"), (2.75, 2.3, "nn.Linear(2, 1)"), (5.55, 1.3, "z"), (7.25, 2.1, "nn.Sigmoid()"),
              (9.75, 1.2, "p")]
        for x0, w, label in xs:
            ax.text(x0 + w / 2, 4.75, label, ha="center", va="center", fontsize=18, color=INK, weight="bold",
                    family=(CODE if label.startswith("nn.") else None))
        for x0, x1 in ((2.3, 2.75), (5.05, 5.55), (6.85, 7.25), (9.35, 9.75)):
            arrow(ax, x0, 4.75, x1, 4.75)
        for r, (label, z, p) in enumerate(rows):
            y0 = 3.1 - r * 1.75
            ax.text(0.3, y0 + 0.95, label, ha="left", va="center", fontsize=16, color=MUTED)
            box(ax, 0.3, y0 - 0.45, 2.0, 0.9, edge=INK, fill=HL)
            ax.text(1.3, y0, "(4.8, 3.4)", ha="center", va="center", fontsize=18, zorder=4)
            show_z = stage >= (2 if r == 0 else 4)
            show_p = stage >= (3 if r == 0 else 5)
            box(ax, 2.75, y0 - 0.45, 2.3, 0.9, edge=INK if show_z else FAINT)
            if show_z:
                form = "4.8 + 3.4 + 1" if r == 0 else "w1·x1 + w2·x2 + b"
                ax.text(3.9, y0, form, ha="center", va="center", fontsize=17 if r == 0 else 15, zorder=4)
            box(ax, 5.55, y0 - 0.45, 1.3, 0.9, edge=INK if show_z else FAINT)
            if show_z:
                ax.text(6.2, y0, z, ha="center", va="center", fontsize=19, weight="bold", zorder=4)
            box(ax, 7.25, y0 - 0.45, 2.1, 0.9, edge=GRAY if show_p else FAINT, fill=NOTE if show_p else "white")
            if show_p:
                ax.text(8.3, y0, "σ(" + z + ")", ha="center", va="center", fontsize=17, zorder=4)
            box(ax, 9.75, y0 - 0.45, 1.2, 0.9, edge=INK if show_p else FAINT)
            if show_p:
                ax.text(10.35, y0, p, ha="center", va="center", fontsize=19, weight="bold", zorder=4)
        if stage == 6:
            note(ax, 5.6, 0.35, "같은 꽃의 p 가 처음 값으로는 0.9999, 학습한 값으로는 0.0345", size=16, ha="center")
        return image(fig)

    frames = [draw(k) for k in range(1, 7)]
    return frames, [2000, 2200, 2200, 2200, 2200, 2500]


@figure("8a-4", 560, 300)
def sigmoid_walk():
    """시그모이드 곡선 위를 z = −3~3 으로 움직이는 점과 0.5 기준."""
    zs = [-3, -2, -1, 0, 1, 2, 3]
    ps = [float(sigmoid(z)) for z in zs]
    assert [fx(p, 4) for p in ps] == ["0.0474", "0.1192", "0.2689", "0.5000", "0.7311", "0.8808", "0.9526"]
    grid = np.linspace(-4.5, 4.5, 300)

    def draw(upto, summary=False):
        plt, fig = new(600)
        ax = fig.add_axes([0.09, 0.14, 0.58, 0.8])
        tidy(ax)
        if summary:
            ax.axvspan(-4.5, 0, color=BLUE_L, zorder=0)
            ax.axvspan(0, 4.5, color=ORANGE_L, zorder=0)
        ax.plot(grid, sigmoid(grid), color=GRAY, lw=3)
        ax.axhline(0.5, color=MUTED, lw=1.6, ls="--")
        ax.axvline(0, color=MUTED, lw=1.2, ls=":")
        ax.set_xlim(-4.5, 4.5)
        ax.set_ylim(-0.03, 1.05)
        ax.set_xlabel("z")
        ax.set_ylabel("p = σ(z)")
        ax.set_xticks(range(-4, 5))
        ax.set_xticklabels([str(v).replace("-", M) for v in range(-4, 5)])
        shown = range(len(zs)) if summary else [upto]
        for k in shown:
            color = INK if zs[k] == 0 else (ORANGE if zs[k] > 0 else BLUE)
            ax.scatter([zs[k]], [ps[k]], s=180 if not summary else 110, color=color, zorder=6)
        if not summary:
            z, p = zs[upto], ps[upto]
            verdict = "0 과 1 의 경계" if z == 0 else ("예측 1" if z > 0 else "예측 0")
            color = INK if z == 0 else (ORANGE if z > 0 else BLUE)
            note(fig, 0.7, 0.66, "z = " + num(z, 0), size=22, transform=fig.transFigure)
            note(fig, 0.7, 0.5, "p = " + fx(p, 4), size=22, transform=fig.transFigure)
            note(fig, 0.7, 0.34, verdict, size=22, color=color, weight="bold", transform=fig.transFigure)
        else:
            note(fig, 0.7, 0.66, "z < 0  →  p < 0.5  →  0", size=19, color=BLUE, weight="bold", transform=fig.transFigure)
            note(fig, 0.7, 0.5, "z > 0  →  p > 0.5  →  1", size=19, color=ORANGE, weight="bold", transform=fig.transFigure)
            note(fig, 0.7, 0.34, "σ(0) = 0.5", size=19, transform=fig.transFigure)
        return image(fig)

    frames = [draw(k) for k in range(7)] + [draw(0, summary=True)]
    return frames, [1800, 1800, 1800, 2200, 1800, 1800, 1800, 2500]


@figure("8a-5", 560, 250)
def memo_8a():
    return memo([[(0.2, 5.35, "이진 분류와 iris", ["답이 클래스 2개 가운데 하나", "앞 100송이, 앞 두 특징", "iris.data[:100, :2] → (100, 2)"],
                   INK, INK, (2,)),
                  (5.65, 5.35, "이진 로지스틱 회귀", ["nn.Linear(2, 1) → nn.Sigmoid()", "z = w1·x1 + w2·x2 + b", "p = σ(z), 0 과 1 사이"],
                   GRAY, INK, (0,))]],
                "p 는 정답이 1일 확률 · p > 0.5 이면 1 · σ(0) = 0.5 라 p > 0.5 와 z > 0 은 같은 조건")


# 8b

@figure("8b-1", 560, 300)
def holdout_bootstrap():
    """홀드아웃: 100송이를 학습 70, 검증 30 으로. 부트스트래핑: 데이터 0~9 에서 10번 복원 추출."""
    plt, fig, ax = board(600)
    ax.text(0.3, 5.55, "홀드아웃: 한 번 나눠 한쪽으로 학습, 다른 쪽으로 평가", fontsize=19, weight="bold", color=INK)
    box(ax, 0.3, 4.2, 7.0, 0.8, edge=SLATE, fill=SLATE_L)
    box(ax, 7.4, 4.2, 3.0, 0.8, edge=PURPLE, fill=PURPLE_L)
    ax.text(3.8, 4.6, "학습 데이터 70송이", ha="center", va="center", fontsize=18, color=SLATE, weight="bold", zorder=4)
    ax.text(8.9, 4.6, "검증 데이터 30송이", ha="center", va="center", fontsize=18, color=PURPLE, weight="bold", zorder=4)
    ax.text(3.8, 3.75, "품종 1 은 37송이", ha="center", va="center", fontsize=16, color=INK)
    ax.text(8.9, 3.75, "품종 1 은 13송이", ha="center", va="center", fontsize=16, color=INK)
    ax.text(0.3, 2.95, "부트스트래핑: 뽑은 데이터를 다시 넣고 데이터 수만큼 뽑기", fontsize=19, weight="bold", color=INK)
    ax.text(0.3, 2.25, "원래 데이터", fontsize=16, color=MUTED, va="center")
    ax.text(0.3, 1.25, "뽑은 10개", fontsize=16, color=MUTED, va="center")
    for k in range(10):
        never = k in NEVER
        ax.text(2.2 + k * 0.85, 2.25, str(k), ha="center", va="center", fontsize=17, zorder=4,
                color=INK, weight="bold" if never else "normal",
                bbox=dict(boxstyle="circle,pad=0.3", fc=YELLOW if never else "white", ec=INK if never else GRAY,
                          lw=1.8))
    for k, d in enumerate(DRAWS):
        ax.text(2.2 + k * 0.85, 1.25, str(d), ha="center", va="center", fontsize=17, zorder=4, color=SLATE,
                bbox=dict(boxstyle="round,pad=0.3", fc=SLATE_L, ec=SLATE, lw=1.6))
    note(ax, 2.0, 0.45, "3 은 세 번, 7 은 두 번 뽑혔고 4, 6, 8 은 한 번도 뽑히지 않았습니다", size=16)
    return image(fig)


@figure("8b-2", 560, 250)
def label_shape():
    """정답 [70] 을 view((-1, 1)) 로 [70, 1] 로 바꿔 출력 [70, 1] 과 칸을 맞춤."""
    first = [0, 0, 1, 0, 1]
    plt, fig, ax = board(500)
    ax.text(0.3, 4.55, "정답 y_tr  [70]", fontsize=18, weight="bold", color=INK)
    for k, v in enumerate(first):
        box(ax, 0.3 + k * 0.62, 3.55, 0.56, 0.6, edge=GRAY)
        ax.text(0.58 + k * 0.62, 3.85, f"{v}.", ha="center", va="center", fontsize=16, zorder=4)
    ax.text(3.55, 3.85, "…", ha="center", va="center", fontsize=18)
    arrow(ax, 4.0, 3.85, 5.0, 3.85, color=INK)
    ax.text(4.5, 4.25, "view((" + M + "1, 1))", ha="center", va="bottom", fontsize=16, family=CODE)
    ax.text(5.3, 4.55, "y_tr1  [70, 1]", fontsize=18, weight="bold", color=INK)
    for k, v in enumerate(first[:4]):
        box(ax, 5.5, 3.55 - k * 0.66, 0.7, 0.6, edge=GRAY)
        ax.text(5.85, 3.85 - k * 0.66, f"{v}.", ha="center", va="center", fontsize=16, zorder=4)
    ax.text(5.85, 0.95, "⋮", ha="center", va="center", fontsize=18)
    ax.text(8.0, 4.55, "모델 출력  [70, 1]", fontsize=18, weight="bold", color=INK)
    for k in range(4):
        box(ax, 8.2, 3.55 - k * 0.66, 0.9, 0.6, edge=GRAY, fill=NOTE)
        ax.text(8.65, 3.85 - k * 0.66, f"p{k + 1}", ha="center", va="center", fontsize=16, zorder=4)
        ax.plot([6.35, 8.05], [3.85 - k * 0.66] * 2, color=FAINT, lw=1.4, ls=":")
    ax.text(8.65, 0.95, "⋮", ha="center", va="center", fontsize=18)
    note(ax, 9.4, 2.3, "같은 줄끼리\nnn.BCELoss() 가\n짝지어 계산", size=15)
    return image(fig)


@figure("8b-3", 560, 300)
def count_accuracy():
    """다섯 송이의 p 를 0.5 로 잘라 정답과 견주고 맞힌 수를 세어 정확도 0.8."""
    def draw(stage):
        plt, fig = new(600)
        ax = fig.add_axes([0.09, 0.42, 0.55, 0.5])
        tidy(ax)
        xs = np.arange(5)
        ax.bar(xs, P5, color=GRAY, width=0.55, zorder=3)
        ax.axhline(0.5, color=MUTED, lw=1.8, ls="--", zorder=4)
        ax.set_ylim(0, 1.05)
        ax.set_xlim(-0.6, 4.6)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"꽃 {k + 1}" for k in xs])
        ax.set_ylabel("p")
        for k in xs:
            ax.text(k, P5[k] + 0.03, num(P5[k], 1), ha="center", va="bottom", fontsize=16)
        rows = [("예측", 2), ("정답", 3), ("같은가", 4)]
        for label, need in rows:
            yy = {"예측": 0.29, "정답": 0.2, "같은가": 0.11}[label]
            if stage >= need:
                fig.text(0.015, yy, label, fontsize=17, color=MUTED, va="center")
        for k in xs:
            xx = 0.09 + 0.55 * (k + 0.6) / 5.2
            if stage >= 2:
                fig.text(xx, 0.29, str(PRED5[k]), ha="center", va="center", fontsize=19, weight="bold",
                         color=ORANGE if PRED5[k] else BLUE)
            if stage >= 3:
                fig.text(xx, 0.2, str(Y5[k]), ha="center", va="center", fontsize=19, color=INK)
            if stage >= 4:
                ok = PRED5[k] == Y5[k]
                fig.text(xx, 0.11, "True" if ok else "False", ha="center", va="center", fontsize=16, weight="bold",
                         color=GREEN if ok else RED)
        if stage >= 2:
            note(fig, 0.67, 0.8, "torch.where(p < 0.5, 0, 1)", size=15, family=CODE, transform=fig.transFigure)
        if stage >= 4:
            note(fig, 0.67, 0.62, "(pred == y).sum()  →  4", size=15, family=CODE, transform=fig.transFigure)
        if stage >= 5:
            note(fig, 0.67, 0.44, "4 ÷ 5 = 0.8", size=20, weight="bold", transform=fig.transFigure)
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2000, 2200, 2000, 2200, 2500]


@figure("8b-4", 560, 300)
def all_ones():
    """처음 값이 모두 1 이면 z = x1 + x2 + 1 > 0 이라 모든 꽃을 1 로 예측. 정확도는 클래스 1 비율."""
    z_tr = XTR @ np.ones(2) + 1
    z_te = XTE @ np.ones(2) + 1
    assert fx(z_tr.min(), 1) == "7.8" and z_te.min() > 0
    plt, fig = new(600)
    ax = fig.add_axes([0.08, 0.14, 0.5, 0.78])
    tidy(ax)
    ax.axvspan(4.1, 7.3, color=ORANGE_L, zorder=0)
    a, b = XTR[YTR == 0], XTR[YTR == 1]
    ax.scatter(a[:, 0], a[:, 1], marker="x", s=70, color=BLUE, lw=2.2, zorder=4)
    ax.scatter(b[:, 0], b[:, 1], marker="o", s=60, facecolors="none", edgecolors=ORANGE, lw=2.2, zorder=4)
    ax.set_xlim(4.1, 7.3)
    ax.set_ylim(1.8, 4.7)
    ax.set_xlabel("꽃받침 길이 x1")
    ax.set_ylabel("꽃받침 폭 x2")
    note(ax, 5.55, 4.45, "학습 데이터 70송이 모두 z > 0", size=16, ha="center")
    note(fig, 0.62, 0.84, "z = x1 + x2 + 1", size=19, family=CODE, transform=fig.transFigure)
    note(fig, 0.62, 0.7, "가장 작은 z = 7.8", size=18, transform=fig.transFigure)
    note(fig, 0.62, 0.56, "→ 70송이 모두 1 로 예측", size=18, color=ORANGE, weight="bold", transform=fig.transFigure)
    note(fig, 0.62, 0.38, "학습 데이터  37 ÷ 70 ≈ 0.5286", size=18, color=SLATE, transform=fig.transFigure)
    note(fig, 0.62, 0.24, "검증 데이터  13 ÷ 30 ≈ 0.4333", size=18, color=PURPLE, transform=fig.transFigure)
    assert fx(37 / 70, 4) == "0.5286" and fx(13 / 30, 4) == "0.4333"
    return image(fig)


@figure("8b-5", 560, 250)
def memo_8b():
    return memo([[(0.2, 5.35, "나누기와 정답 모양", ["학습 70송이, 검증 30송이(홀드아웃)", "부트스트래핑은 다시 넣고 뽑기",
                                                 "y.view((" + M + "1, 1))  [70] → [70, 1]"], SLATE, INK, (2,)),
                  (5.65, 5.35, "정확도", ["맞힌 건수 ÷ 전체 건수", "torch.where(p < 0.5, 0, 1)", "모두 1 로 예측하면 클래스 1 비율"],
                   INK, INK, (1,))]],
                "처음 값이 모두 1 인 모델의 첫 정확도는 37 ÷ 70 ≈ 0.5286, 13 ÷ 30 ≈ 0.4333")


# 8c

@figure("8c-1", 560, 300)
def boundary_moves():
    """학습 데이터 70송이 위에서 결정 경계가 반복 0·200·300·400·500·1,000·10,000번에 움직이는 모습과 학습 정확도."""
    steps = [0, 200, 300, 400, 500, 1000, 10000]
    accs = {}
    for ep in steps:
        w, b = SNAPS[ep]
        accs[ep] = float(np.mean(((XTR @ w + b) >= 0) == YTR))
    assert [fx(accs[e], 4) for e in steps] == ["0.5286", "0.5286", "0.6857", "0.8857", "0.9571", "0.9857", "0.9857"]
    xx = np.linspace(4.1, 7.3, 50)

    def draw(k, summary=False):
        plt, fig = new(600)
        ax = fig.add_axes([0.08, 0.14, 0.56, 0.8])
        tidy(ax)
        ep = steps[k]
        w, b = SNAPS[ep]
        yy = boundary_x2(xx, w, b)
        if w[1] < 0:
            ax.fill_between(xx, np.clip(yy, 1.8, 4.7), 4.7, color=BLUE_L, zorder=0)
            ax.fill_between(xx, 1.8, np.clip(yy, 1.8, 4.7), color=ORANGE_L, zorder=0)
        else:
            ax.axvspan(4.1, 7.3, color=ORANGE_L, zorder=0)
        a, b0 = XTR[YTR == 0], XTR[YTR == 1]
        ax.scatter(a[:, 0], a[:, 1], marker="x", s=70, color=BLUE, lw=2.2, zorder=4)
        ax.scatter(b0[:, 0], b0[:, 1], marker="o", s=60, facecolors="none", edgecolors=ORANGE, lw=2.2, zorder=4)
        ax.set_xlim(4.1, 7.3)
        ax.set_ylim(1.8, 4.7)
        ax.set_xlabel("꽃받침 길이 x1")
        ax.set_ylabel("꽃받침 폭 x2")
        if summary:
            for j in range(1, len(steps) - 1):
                wj, bj = SNAPS[steps[j]]
                ax.plot(xx, boundary_x2(xx, wj, bj), color=GRAY, lw=1.6, zorder=5)
        ax.plot(xx, yy, color=INK, lw=3, zorder=5)
        if summary:
            note(fig, 0.67, 0.78, "반복이 늘수록 경계가\n두 품종 사이를 지납니다", size=18, transform=fig.transFigure)
            note(fig, 0.67, 0.53, "10,000번 뒤\nb = " + M + "0.1045\nw = [2.951, " + M + "5.115]", size=17,
                 transform=fig.transFigure)
        else:
            note(fig, 0.67, 0.84, "반복 " + comma(ep) + "번", size=20, weight="bold", transform=fig.transFigure)
            note(fig, 0.67, 0.68, "w = [" + fx(w[0], 3) + ", " + fx(w[1], 3) + "]\nb = " + fx(b, 4), size=17,
                 transform=fig.transFigure)
            note(fig, 0.67, 0.5, "학습 정확도 " + fx(accs[ep], 4), size=18, color=SLATE, transform=fig.transFigure)
            if ep == 0:
                note(fig, 0.67, 0.32, "경계가 그림 아래 밖이라\n70송이 모두 1 로 예측", size=16, transform=fig.transFigure)
        return image(fig)

    frames = [draw(k) for k in range(len(steps))] + [draw(len(steps) - 1, summary=True)]
    return frames, [2200, 2000, 2000, 2000, 2000, 2000, 2200, 2500]


@figure("8c-2", 560, 300)
def boundary_points():
    """경계 위 두 점 (4.4, 2.518), (6.8, 3.903) 과 경계 양쪽, 따라가는 꽃 (4.8, 3.4)."""
    x_ends = np.array([4.4, 6.8])
    y_ends = boundary_x2(x_ends, W_NB, B_NB)
    y48 = boundary_x2(4.8, W_NB, B_NB)
    assert abs(FLOWER[1] - y48 - 0.6512) < 1e-3 and fx(W_NB[1] * (FLOWER[1] - y48), 2) == M + "3.33"
    plt, fig = new(600)
    ax = fig.add_axes([0.08, 0.14, 0.56, 0.8])
    tidy(ax)
    xx = np.linspace(4.1, 7.3, 50)
    yy = boundary_x2(xx, W_NB, B_NB)
    ax.fill_between(xx, yy, 4.7, color=BLUE_L, zorder=0)
    ax.fill_between(xx, 1.8, yy, color=ORANGE_L, zorder=0)
    a, b = XTE[YTE == 0], XTE[YTE == 1]
    ax.scatter(a[:, 0], a[:, 1], marker="x", s=70, color=BLUE, lw=2.2, zorder=4)
    ax.scatter(b[:, 0], b[:, 1], marker="o", s=60, facecolors="none", edgecolors=ORANGE, lw=2.2, zorder=4)
    ax.plot(xx, yy, color=INK, lw=3, zorder=5)
    ax.scatter(x_ends, y_ends, s=110, color=INK, zorder=6)
    ax.scatter([FLOWER[0]], [FLOWER[1]], s=520, color=YELLOW, zorder=3)
    ax.scatter([FLOWER[0]], [FLOWER[1]], s=70, color=INK, marker="x", lw=2.2, zorder=6)
    ax.plot([4.8, 4.8], [y48, FLOWER[1]], color=INK, lw=1.4, ls=":", zorder=5)
    ax.scatter([4.8], [y48], s=60, color=INK, zorder=6)
    ax.set_xlim(4.1, 7.3)
    ax.set_ylim(1.8, 4.7)
    ax.set_xlabel("꽃받침 길이 x1")
    ax.set_ylabel("꽃받침 폭 x2")
    note(ax, 4.45, 2.2, "(4.4, 2.518)", size=15)
    note(ax, 6.6, 3.62, "(6.8, 3.903)", size=15)
    note(ax, 4.2, 4.45, "z < 0 쪽: 예측 0", size=16, color=BLUE, weight="bold")
    note(ax, 6.0, 2.05, "z > 0 쪽: 예측 1", size=16, color=ORANGE, weight="bold")
    note(fig, 0.67, 0.8, "x2 = " + M + "(b + w1·x1) ÷ w2", size=18, family=CODE, transform=fig.transFigure)
    note(fig, 0.67, 0.62, "b = " + M + "0.1045\nw1 = 2.951, w2 = " + M + "5.115", size=17, transform=fig.transFigure)
    note(fig, 0.67, 0.4, "x1 = 4.8 의 경계 x2 = 2.749\n꽃 (4.8, 3.4) 는 0.651 위\nz ≈ " + M + "3.33", size=17,
         transform=fig.transFigure)
    note(fig, 0.67, 0.17, "점은 검증 데이터 30송이", size=16, color=MUTED, transform=fig.transFigure)
    return image(fig)


@figure("8c-3", 560, 280)
def hyperplanes():
    """특징 1개면 점, 2개면 직선, 3개면 평면인 경계."""
    plt, fig = new(560)
    head(fig, "경계는 w·x + b = 0 인 점을 모은 것입니다", y=0.95)
    ax1 = fig.add_axes([0.04, 0.42, 0.27, 0.32])
    ax1.set_xlim(-1, 5)
    ax1.set_ylim(-1, 1)
    ax1.axis("off")
    ax1.plot([-0.8, 4.8], [0, 0], color=GRAY, lw=2)
    ax1.axvspan(-1, 2, color=BLUE_L)
    ax1.axvspan(2, 5, color=ORANGE_L)
    ax1.scatter([2], [0], s=200, color=INK, zorder=5)
    ax1.text(2, -0.55, "x1 = 2", ha="center", fontsize=16)
    ax1.text(0.4, 0.5, "z < 0", ha="center", fontsize=16, color=BLUE)
    ax1.text(3.6, 0.5, "z > 0", ha="center", fontsize=16, color=ORANGE)
    fig.text(0.175, 0.82, "특징 1개: 점", ha="center", fontsize=19, weight="bold")
    fig.text(0.175, 0.28, "z = 2·x1 " + M + " 4", ha="center", fontsize=16, family=CODE)
    ax2 = fig.add_axes([0.37, 0.2, 0.26, 0.55])
    ax2.set_xlim(0, 4)
    ax2.set_ylim(0, 4)
    ax2.set_xticks([])
    ax2.set_yticks([])
    xx = np.linspace(0, 4, 20)
    ax2.fill_between(xx, xx * 0.5 + 1, 4, color=BLUE_L)
    ax2.fill_between(xx, 0, xx * 0.5 + 1, color=ORANGE_L)
    ax2.plot(xx, xx * 0.5 + 1, color=INK, lw=3)
    ax2.text(0.4, 3.4, "z < 0", fontsize=16, color=BLUE)
    ax2.text(2.6, 0.5, "z > 0", fontsize=16, color=ORANGE)
    ax2.set_xlabel("x1", fontsize=16)
    ax2.set_ylabel("x2", fontsize=16)
    fig.text(0.5, 0.82, "특징 2개: 직선", ha="center", fontsize=19, weight="bold")
    ax3 = fig.add_axes([0.64, 0.1, 0.3, 0.66], projection="3d")
    g = np.linspace(0, 1, 6)
    gx, gy = np.meshgrid(g, g)
    ax3.plot_surface(gx, gy, 0.6 - 0.3 * gx + 0.2 * gy, color=GRAY, alpha=0.6, edgecolor=MUTED, lw=0.6)
    ax3.set_xticks([])
    ax3.set_yticks([])
    ax3.set_zticks([])
    ax3.set_xlabel("x1", fontsize=15, labelpad=-10)
    ax3.set_ylabel("x2", fontsize=15, labelpad=-10)
    ax3.set_zlabel("x3", fontsize=15, labelpad=-10)
    ax3.view_init(elev=22, azim=-55)
    fig.text(0.825, 0.82, "특징 3개: 평면", ha="center", fontsize=19, weight="bold")
    note(fig, 0.5, 0.06, "특징이 n개면 초평면 · 직선과 평면도 초평면입니다", size=16, ha="center",
         transform=fig.transFigure)
    return image(fig)


@figure("8c-4", 560, 300)
def learning_curves():
    """학습 데이터와 검증 데이터의 손실·정확도 곡선(10,000번)."""
    ep = np.arange(len(HIST))
    assert fx(HIST[-1, 0], 3) == "0.112" and fx(HIST[-1, 2], 3) == "0.083"
    assert fx(HIST[-1, 1], 3) == "0.986" and HIST[-1, 3] == 1.0
    plt, fig = new(600)
    ax1 = fig.add_axes([0.08, 0.15, 0.38, 0.72])
    ax2 = fig.add_axes([0.58, 0.15, 0.38, 0.72])
    for ax in (ax1, ax2):
        tidy(ax)
        ax.set_xlim(0, 10000)
        ax.set_xticks([0, 5000, 10000])
        ax.set_xticklabels(["0", "5,000", "10,000"])
        ax.set_xlabel("반복 횟수")
    ax1.plot(ep, HIST[:, 0], color=SLATE, lw=2.6)
    ax1.plot(ep, HIST[:, 2], color=PURPLE, lw=2.6, ls="--")
    ax1.set_ylim(0, 5.6)
    ax1.set_ylabel("손실", labelpad=12)
    ax2.plot(ep, HIST[:, 1], color=SLATE, lw=2.6)
    ax2.plot(ep, HIST[:, 3], color=PURPLE, lw=2.6, ls="--")
    ax2.set_ylim(0.4, 1.05)
    ax2.set_ylabel("정확도", labelpad=12)
    note(ax1, 2600, 4.6, "학습 4.41 → 0.112", size=16, color=SLATE)
    note(ax1, 2600, 3.7, "검증 5.33 → 0.083", size=16, color=PURPLE)
    note(ax2, 2600, 0.66, "학습 0.529 → 0.986", size=16, color=SLATE)
    note(ax2, 2600, 0.54, "검증 0.433 → 1.0", size=16, color=PURPLE)
    fig.text(0.27, 0.93, "손실", ha="center", fontsize=19, weight="bold")
    fig.text(0.77, 0.93, "정확도", ha="center", fontsize=19, weight="bold")
    return image(fig)


@figure("8c-5", 560, 250)
def memo_8c():
    return memo([[(0.2, 5.35, "결정 경계", ["z = w1·x1 + w2·x2 + b = 0 인 직선", "x2 = " + M + "(b + w1·x1) ÷ w2",
                                         "z > 0 쪽 예측 1, z < 0 쪽 예측 0"], INK, INK, ()),
                  (5.65, 5.35, "초평면과 학습 곡선", ["특징 1개 점, 2개 직선, 3개 평면", "직선 하나라 XOR 는 못 나눔",
                                              "두 손실이 함께 줄면 과적합 신호 없음"], INK, INK, ())]],
                "노트북 01 학습값 b = " + M + "0.1045, w = [2.951, " + M + "5.115] · x1 = 4.4 → 2.518, 6.8 → 3.903")


# 8d

@figure("8d-1", 560, 280)
def two_versions():
    """BCELoss 방식(Linear → Sigmoid → BCELoss, 기준 0.5)과 BCEWithLogitsLoss 방식(Linear → BCEWithLogitsLoss, 기준 0.0)."""
    plt, fig, ax = board(560)
    rows = [(4.0, "BCELoss 방식", False), (1.55, "BCEWithLogitsLoss 방식", True)]
    for y0, title, logit in rows:
        ax.text(0.3, y0 + 1.15, title, fontsize=19, weight="bold", color=GREEN if logit else INK)
        box(ax, 0.3, y0 - 0.4, 1.1, 0.8, edge=INK)
        ax.text(0.85, y0, "x", ha="center", va="center", fontsize=19, zorder=4)
        arrow(ax, 1.45, y0, 1.85, y0)
        box(ax, 1.9, y0 - 0.4, 2.3, 0.8, edge=INK)
        ax.text(3.05, y0, "nn.Linear(2, 1)", ha="center", va="center", fontsize=16, family=CODE, zorder=4)
        arrow(ax, 4.25, y0, 4.65, y0)
        ax.text(4.9, y0, "z", ha="center", va="center", fontsize=20, weight="bold")
        arrow(ax, 5.15, y0, 5.55, y0)
        if not logit:
            box(ax, 5.6, y0 - 0.4, 2.0, 0.8, edge=GRAY, fill=NOTE)
            ax.text(6.6, y0, "nn.Sigmoid()", ha="center", va="center", fontsize=16, family=CODE, zorder=4)
            arrow(ax, 7.65, y0, 8.05, y0)
            ax.text(8.3, y0, "p", ha="center", va="center", fontsize=20, weight="bold")
            box(ax, 8.65, y0 - 0.4, 2.3, 0.8, edge=INK)
            ax.text(9.8, y0, "nn.BCELoss()", ha="center", va="center", fontsize=16, family=CODE, zorder=4)
            note(ax, 5.6, y0 - 0.95, "판정: p 와 0.5 를 견줌", size=16)
        else:
            box(ax, 5.6, y0 - 0.4, 5.35, 0.8, edge=GREEN, fill="white", lw=2.8)
            ax.text(8.27, y0, "nn.BCEWithLogitsLoss()  (시그모이드 + BCE)", ha="center", va="center", fontsize=16,
                    family=CODE, zorder=4)
            note(ax, 5.6, y0 - 0.95, "판정: z 와 0.0 을 견줌", size=16)
    return image(fig)


@figure("8d-2", 560, 300)
def two_thresholds():
    """logit z 를 0.0 과, 확률 p 를 0.5 와 견주면 같은 예측. z 에 0.5 를 쓰면 0.3 이 0 으로 바뀜."""
    zs = np.array([-1.2, 0.3, 2.0])
    ps = sigmoid(zs)
    assert [fx(p, 4) for p in ps] == ["0.2315", "0.5744", "0.8808"]
    pred = (zs >= 0).astype(int)
    assert pred.tolist() == [0, 1, 1] and (ps >= 0.5).astype(int).tolist() == [0, 1, 1]
    assert (zs >= 0.5).astype(int).tolist() == [0, 0, 1]
    zx = lambda z: 0.1 + (z + 3) / 6 * 0.8
    px = lambda p: 0.1 + p * 0.8

    def draw(stage):
        plt, fig, ax = board(600)
        ax.set_xlim(0, 1)
        ax.text(0.03, 5.55, "logit z" + ("   기준 0.0" if stage >= 3 else ""), fontsize=18, weight="bold")
        ax.text(0.03, 3.0, "확률 p = σ(z)" + ("   기준 0.5" if stage >= 3 else ""), fontsize=18, weight="bold")
        ax.plot([0.1, 0.9], [4.4, 4.4], color=GRAY, lw=2.2)
        ax.plot([0.1, 0.9], [1.75, 1.75], color=GRAY, lw=2.2)
        ax.text(0.085, 4.4, M + "3", ha="right", va="center", fontsize=15, color=MUTED)
        ax.text(0.915, 4.4, "3", ha="left", va="center", fontsize=15, color=MUTED)
        ax.text(0.085, 1.75, "0", ha="right", va="center", fontsize=15, color=MUTED)
        ax.text(0.915, 1.75, "1", ha="left", va="center", fontsize=15, color=MUTED)
        if stage >= 3:
            ax.plot([zx(0)] * 2, [4.15, 4.65], color=INK, lw=2, ls="--")
            ax.plot([px(0.5)] * 2, [1.5, 2.0], color=INK, lw=2, ls="--")
        if stage == 4:
            ax.plot([zx(0.5)] * 2, [4.15, 4.65], color=RED, lw=2.4, ls="--")
        for k, (z, p) in enumerate(zip(zs, ps)):
            color = MUTED
            if stage >= 3:
                color = ORANGE if pred[k] else BLUE
            if stage == 4 and k == 1:
                color = RED
            ax.scatter([zx(z)], [4.4], s=170, color=color, zorder=5)
            ax.text(zx(z), 4.85, num(z, 1), ha="center", fontsize=17, color=INK)
            if stage >= 2:
                ax.plot([zx(z), px(p)], [4.25, 1.9], color=FAINT, lw=1.4, zorder=1)
                ax.scatter([px(p)], [1.75], s=170, color=color, zorder=5)
                ax.text(px(p), 1.15, fx(p, 4), ha="center", fontsize=17, color=INK)
        if stage == 3:
            note(ax, 0.5, 0.4, "z 를 0.0 과, p 를 0.5 와 견주면 두 줄 모두 예측 [0, 1, 1]", size=17, ha="center")
        if stage == 4:
            note(ax, 0.5, 0.4, "빨간 점선: z 에 0.5 를 쓰면 z = 0.3 (p = 0.5744) 이 0 으로 판정", size=17, ha="center",
                 color=RED)
        if stage == 5:
            note(ax, 0.5, 0.4, "σ(0) = 0.5 라 z > 0 과 p > 0.5 는 같은 조건", size=17, ha="center")
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2000, 2200, 2200, 2400, 2500]


@figure("8d-3", 560, 250)
def same_training():
    """노트북 01 의 두 판: 같은 설정, 같은 학습 결과, 첫 검증 손실의 작은 차이."""
    exact = HIST[0, 2]
    assert fx(exact, 5) == "5.33163" and abs(exact - 5.331626) < 5e-7
    plt, fig, ax = board(500)
    cols = [0.3, 4.6, 8.0]
    ax.text(cols[1], 4.55, "BCELoss 방식", fontsize=18, weight="bold", ha="left")
    ax.text(cols[2], 4.55, "BCEWithLogitsLoss 방식", fontsize=18, weight="bold", ha="left", color=GREEN)
    rows = [("처음 값, 학습률, 반복", "1, 0.01, 10,000번", "1, 0.01, 10,000번"),
            ("반복 0번의 학습 손실", "4.41008", "4.41009"),
            ("반복 1,000번부터 찍은 학습 손실", "같은 값", "같은 값"),
            ("학습한 b", M + "0.10450024", M + "0.10450011"),
            ("첫 갱신 뒤 검증 손실", "5.33157", "5.33163")]
    for r, (label, a, b) in enumerate(rows):
        yy = 3.85 - r * 0.7
        ax.plot([0.3, 10.9], [yy + 0.35, yy + 0.35], color=FAINT, lw=1.2)
        ax.text(cols[0], yy, label, fontsize=17, va="center", color=MUTED)
        ax.text(cols[1], yy, a, fontsize=17, va="center")
        ax.text(cols[2], yy, b, fontsize=17, va="center")
    assert fx(HIST[0, 0], 5) == "4.41009"
    note(ax, 0.3, 0.35, "float64 로 계산하면 반복 0번 학습 손실 4.41009, 첫 갱신 뒤 검증 손실 5.331626", size=16)
    return image(fig)


@figure("8d-4", 560, 260)
def half_rules():
    """p = [0.2, 0.5, 0.9, 0.6], 정답 [0, 1, 1, 0] 을 판정 줄 셋으로 자른 결과와 정확도."""
    p = np.array([0.2, 0.5, 0.9, 0.6])
    y = np.array([0, 1, 1, 0])
    rules = [("torch.where(p < 0.5, 0, 1)", np.where(p < 0.5, 0, 1)), ("(p > 0.5).float()", (p > 0.5).astype(int)),
             ("(p >= 0.5).float()", (p >= 0.5).astype(int))]
    assert [r[1].tolist() for r in rules] == [[0, 1, 1, 1], [0, 0, 1, 1], [0, 1, 1, 1]]
    accs = [float((r[1] == y).mean()) for r in rules]
    assert accs == [0.75, 0.5, 0.75]
    plt, fig, ax = board(520)
    xs = [5.6, 6.8, 8.0, 9.2]
    ax.text(0.3, 4.55, "p", fontsize=18, weight="bold")
    ax.text(0.3, 3.85, "정답", fontsize=18, weight="bold")
    ax.text(10.3, 4.55, "정확도", fontsize=17, weight="bold", ha="center")
    for k, x in enumerate(xs):
        ax.text(x, 4.55, num(p[k], 1), ha="center", fontsize=18, weight="bold" if p[k] == 0.5 else "normal",
                bbox=dict(boxstyle="round,pad=0.25", fc=HL, ec=HL) if p[k] == 0.5 else None)
        ax.text(x, 3.85, str(y[k]), ha="center", fontsize=18)
    for r, (code, out) in enumerate(rules):
        yy = 2.85 - r * 0.85
        ax.text(0.3, yy, code, fontsize=16, family=CODE, va="center")
        for k, x in enumerate(xs):
            ok = out[k] == y[k]
            ax.text(x, yy, str(out[k]), ha="center", va="center", fontsize=18, weight="bold",
                    color=ORANGE if out[k] else BLUE)
            if k == 1:
                ax.plot([x - 0.35, x + 0.35, x + 0.35, x - 0.35, x - 0.35], [yy - 0.3, yy - 0.3, yy + 0.3, yy + 0.3, yy - 0.3],
                        color=GREEN if ok else RED, lw=1.8)
        ax.text(10.3, yy, num(accs[r], 2), ha="center", va="center", fontsize=18)
    return image(fig)


@figure("8d-5", 560, 250)
def memo_8d():
    return memo([[(0.2, 5.35, "BCELoss 방식", ["모델 끝 nn.Sigmoid(), 출력은 확률 p", "nn.BCELoss()", "기준 0.5"], GRAY, INK, (1,)),
                  (5.65, 5.35, "BCEWithLogitsLoss 방식", ["모델 끝 Linear, 출력은 logit z", "nn.BCEWithLogitsLoss()",
                                                   "기준 0.0, 확률은 torch.sigmoid(z)"], GREEN, INK, (1,))]],
                "p = 0.5 이면 torch.where(p < 0.5, 0, 1) 과 >= 는 1, > 는 0 · logit 에 0.5 를 쓰면 0 과 0.5 사이의 z 를 놓침")


# 8e

@figure("8e-1", 560, 260)
def fraud_counts():
    """make_classification 으로 만든 10,000건의 클래스 수와 np.unique 출력."""
    assert N0 + N1 == 10000 and fx(N1 / 100, 2) == "5.39"
    plt, fig = new(520)
    ax = fig.add_axes([0.13, 0.16, 0.38, 0.74])
    tidy(ax)
    ax.bar([0, 1], [N0, N1], color=[BLUE, ORANGE], width=0.55, zorder=3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["0 정상 거래", "1 사기 거래"])
    ax.set_ylim(0, 11500)
    ax.set_yticks([0, 5000, 10000])
    ax.set_yticklabels(["0", "5,000", "10,000"])
    ax.text(0, N0 - 900, "9,461\n(94.61%)", ha="center", va="top", fontsize=17, color="white", weight="bold")
    ax.text(1, N1 + 250, "539 (5.39%)", ha="center", fontsize=17)
    note(fig, 0.57, 0.74, "np.unique(y, return_counts=True)", size=16, family=CODE, transform=fig.transFigure)
    note(fig, 0.57, 0.56, "→ (array([0, 1]),\n    array([9461, 539]))", size=16, family=CODE, transform=fig.transFigure)
    note(fig, 0.57, 0.3, "weights=[0.95, 0.05], flip_y=0.01", size=16, family=CODE, transform=fig.transFigure)
    return image(fig)


@figure("8e-2", 560, 300)
def stratify_splits():
    """테스트 데이터 2,000건의 사기 비율: stratify 없이 다섯 번 나눈 예와 stratify=y."""
    pct = [s / 2000 * 100 for s in SPLITS]
    assert [fx(v, 2) for v in pct] == ["5.80", "5.40", "4.70", "5.40", "5.75"]

    def draw(k, summary=False):
        plt, fig = new(600)
        ax = fig.add_axes([0.1, 0.15, 0.55, 0.75])
        tidy(ax)
        ax.set_xlim(0.4, 6.6)
        ax.set_ylim(4.3, 6.2)
        ax.set_xticks(range(1, 7))
        ax.set_xticklabels(["1", "2", "3", "4", "5", "stratify"])
        ax.set_xlabel("나눈 차례")
        ax.set_ylabel("테스트 사기 비율 (%)")
        ax.axhline(5.39, color=MUTED, lw=1.6, ls="--")
        ax.text(0.5, 5.25, "전체 5.39%", fontsize=15, color=MUTED)
        upto = 5 if summary else min(k, 5)
        for j in range(upto):
            ax.scatter([j + 1], [pct[j]], s=150, color=GRAY, zorder=5)
            ax.text(j + 1, pct[j] + 0.08, str(SPLITS[j]) + "건", ha="center", fontsize=15)
        if summary or k == 6:
            ax.scatter([6], [5.40], s=170, color=PURPLE, zorder=5)
            ax.text(6, 5.48, "108건", ha="center", fontsize=15, color=PURPLE)
        if summary:
            note(fig, 0.68, 0.7, "stratify 없이: 94~116건", size=16, transform=fig.transFigure)
            note(fig, 0.68, 0.52, "stratify=y: 108건", size=16, color=PURPLE, transform=fig.transFigure)
        elif k == 0:
            note(fig, 0.68, 0.7, "10,000건 가운데 사기 539건", size=17, transform=fig.transFigure)
            note(fig, 0.68, 0.52, "테스트 2,000건을 떼어 냅니다", size=17, transform=fig.transFigure)
        elif k <= 5:
            note(fig, 0.68, 0.7, f"무작위로 {k}번째 나눔", size=17, transform=fig.transFigure)
            note(fig, 0.68, 0.52, f"사기 {SPLITS[k - 1]}건 = {fx(pct[k - 1], 2)}%", size=18, weight="bold",
                 transform=fig.transFigure)
        else:
            note(fig, 0.68, 0.7, "stratify=y 로 나눔", size=17, color=PURPLE, transform=fig.transFigure)
            note(fig, 0.68, 0.52, "539 × 0.2 ≈ 108건", size=18, weight="bold", color=PURPLE, transform=fig.transFigure)
        return image(fig)

    frames = [draw(k) for k in range(0, 7)] + [draw(6, summary=True)]
    return frames, [2000, 1800, 1800, 1800, 1800, 1800, 2200, 2500]


@figure("8e-3", 560, 300)
def pos_weight_effect():
    """사기 거래(z = −1)와 정상 거래(z = 1)의 손실, pos_weight 17.55 를 곱한 뒤, 클래스별 합의 무게."""
    plt, fig = new(600)
    ax1 = fig.add_axes([0.08, 0.16, 0.4, 0.68])
    ax2 = fig.add_axes([0.6, 0.16, 0.36, 0.68])
    for ax in (ax1, ax2):
        tidy(ax)
    ax1.bar([0, 1, 2.4], [L_POS, L_POS * PW, L_POS], color=[ORANGE_L, ORANGE, BLUE], edgecolor=[ORANGE, ORANGE, BLUE],
            lw=2, width=0.8, zorder=3)
    ax1.set_xticks([0, 1, 2.4])
    ax1.set_xticklabels(["사기\n그대로", "사기\n× 17.55", "정상"])
    ax1.set_ylim(0, 27)
    ax1.set_ylabel("손실", labelpad=12)
    ax1.text(0, L_POS + 0.6, fx(L_POS, 4), ha="center", fontsize=16)
    ax1.text(1, L_POS * PW + 0.6, fx(L_POS * PW, 2), ha="center", fontsize=16)
    ax1.text(2.4, L_POS + 0.6, fx(L_POS, 4), ha="center", fontsize=16)
    fig.text(0.28, 0.9, "데이터 하나의 손실", ha="center", fontsize=18, weight="bold")
    ax2.bar([0, 1], [N1 * PW, N0], color=[ORANGE, BLUE], width=0.6, zorder=3)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["사기 539건\n× pos_weight", "정상\n9,461건"])
    ax2.set_ylim(0, 11000)
    ax2.set_yticks([0, 5000, 10000])
    ax2.set_yticklabels(["0", "5,000", "10,000"])
    assert abs(N1 * PW - N0) < 1e-9
    ax2.text(0, N1 * PW + 250, "= 9,461", ha="center", fontsize=16)
    ax2.text(1, N0 + 250, "9,461", ha="center", fontsize=16)
    fig.text(0.78, 0.9, "클래스별 무게", ha="center", fontsize=18, weight="bold")
    return image(fig)


@figure("8e-4", 560, 260)
def train_eval_loop():
    """반복 한 번: 학습 모드에서 갱신하고 평가 모드에서 테스트 데이터를 잼."""
    plt, fig, ax = board(520)
    rows = [(3.9, "학습", SLATE, SLATE_L, ["model.train()", "zero_grad()", "손실", "backward()", "step()"]),
            (1.6, "평가", PURPLE, PURPLE_L, ["model.eval()", "no_grad() 안", "z_test", "z_test >= 0.0", "정확도"])]
    for y0, title, edge, fill, steps in rows:
        ax.text(0.3, y0, title, fontsize=19, weight="bold", color=edge, va="center")
        x = 1.3
        for k, s in enumerate(steps):
            w = 1.9
            box(ax, x, y0 - 0.38, w - 0.25, 0.76, edge=edge, fill=fill)
            ax.text(x + (w - 0.25) / 2, y0, s, ha="center", va="center", fontsize=15,
                    family=CODE if ("(" in s or ">" in s or "_" in s) else None, zorder=4)
            if k < len(steps) - 1:
                arrow(ax, x + w - 0.24, y0, x + w - 0.02, y0, color=edge, lw=1.8)
            x += w
    ax.plot([10.5, 10.5, 2.125], [3.45, 2.65, 2.65], color=MUTED, lw=2)
    arrow(ax, 2.125, 2.65, 2.125, 2.05, color=MUTED)
    note(ax, 5.6, 0.45, "1,000번 되풀이 · BCEWithLogitsLoss 방식이라 기준 0.0", size=16, ha="center")
    return image(fig)


@figure("8e-5", 560, 250)
def memo_8e():
    return memo([[(0.2, 5.35, "전체 분포의 산술 예", ["정상 9,461건, 사기 539건", "np.unique(y, return_counts=True)",
                                          "stratify=y: 비율 5.39% · 5.40%"], SLATE, INK, (1,)),
                  (5.65, 5.35, "훈련 라벨로 가중치 계산", ["pos_weight = 훈련 음성 수 ÷ 훈련 양성 수",
                                           "정답 1 인 항에만 곱함", "평가는 model.eval() + no_grad()"], INK, INK, ())]],
                "테스트 데이터는 학습 데이터로 fit 한 scaler 로 transform 만 · 마지막 Linear(8, 1) 출력은 logit")


# 8f

def cm_table(ax, x0, y0, cells, names, colors, frames=(), cell=1.6, labels=True, title=None, order="sk"):
    """2×2 혼동 행렬. cells[r][c] 는 숫자, names[r][c] 는 칸 이름. order 는 머리글 순서(sk 는 0 먼저)."""
    heads = ("0 정상", "1 사기") if order == "sk" else ("1 사기", "0 정상")
    if title:
        ax.text(x0 + cell, y0 + 2 * cell + 1.05, title, ha="center", fontsize=17, weight="bold")
    if labels:
        ax.text(x0 + cell, y0 + 2 * cell + 0.55, "예측", ha="center", fontsize=16, color=MUTED)
        ax.text(x0 - 1.05, y0 + cell, "실제", ha="center", va="center", fontsize=16, color=MUTED, rotation=90)
    for c in range(2):
        ax.text(x0 + c * cell + cell / 2, y0 + 2 * cell + 0.15, heads[c], ha="center", fontsize=15)
    for r in range(2):
        ax.text(x0 - 0.12, y0 + (1 - r) * cell + cell / 2, heads[r], ha="right", va="center", fontsize=15)
        for c in range(2):
            xx, yy = x0 + c * cell, y0 + (1 - r) * cell
            box(ax, xx + 0.05, yy + 0.05, cell - 0.1, cell - 0.1, edge=YELLOW if (r, c) in frames else GRAY,
                fill=colors[r][c], lw=5 if (r, c) in frames else 1.6)
            ax.text(xx + cell / 2, yy + cell * 0.6, comma(cells[r][c]), ha="center", va="center", fontsize=20,
                    weight="bold", zorder=4)
            if names[r][c]:
                ax.text(xx + cell / 2, yy + cell * 0.27, names[r][c], ha="center", va="center", fontsize=15, zorder=4)


SK = [[TN, FP], [FN, TP]]
SK_NAMES = [["TN", "FP"], ["FN", "TP"]]
SK_COLORS = [[GREEN_L, RED_L], [RED_L, GREEN_L]]


@figure("8f-1", 560, 300)
def cm_layout():
    """scikit-learn 혼동 행렬 [[1849, 43], [19, 89]] 의 칸 이름, ravel 순서, 양성 먼저 배치와 견주기."""
    def draw(stage):
        plt, fig, ax = board(600)
        names = [["", ""], ["", ""]]
        colors = [["white", "white"], ["white", "white"]]
        if stage >= 2:
            names[0][0], colors[0][0] = "TN", GREEN_L
        if stage >= 3:
            names[0][1], colors[0][1] = "FP", RED_L
            names[1][0], colors[1][0] = "FN", RED_L
        if stage >= 4:
            names[1][1], colors[1][1] = "TP", GREEN_L
        cm_table(ax, 1.5, 1.2, SK, names, colors, title="scikit-learn  confusion_matrix")
        if stage == 1:
            note(ax, 5.3, 3.6, "행은 실제, 열은 예측\n클래스 번호가 작은 0 이 먼저", size=17)
        if stage == 2:
            note(ax, 5.3, 3.6, "TN: 정상을 정상으로 1,849건", size=17)
        if stage == 3:
            note(ax, 5.3, 3.6, "FP: 정상을 사기로 43건\nFN: 사기를 정상으로 19건", size=17)
        if stage == 4:
            note(ax, 5.3, 3.6, "TP: 사기를 사기로 89건", size=17)
        if stage == 5:
            note(ax, 5.3, 3.9, "cm.ravel()", size=17, family=CODE)
            note(ax, 5.3, 3.1, "→ [1849, 43, 19, 89]\n    TN, FP, FN, TP", size=17, family=CODE)
        if stage == 6:
            cm_table(ax, 7.3, 1.2, [[TP, FN], [FP, TN]], [["TP", "FN"], ["FP", "TN"]],
                     [[GREEN_L, RED_L], [RED_L, GREEN_L]], title="요약본·4차시 배치", order="pos")
        return image(fig)

    frames = [draw(k) for k in range(1, 7)]
    return frames, [2000, 2000, 2200, 2000, 2200, 2500]


@figure("8f-2", 560, 300)
def cm_metrics():
    """같은 혼동 행렬로 정확도, 정밀도, 재현율, F1 과 모두 정상이라고 답한 모델."""
    def draw(stage):
        plt, fig, ax = board(600)
        if stage == 5:
            cm_table(ax, 1.5, 1.2, [[1892, 0], [108, 0]], SK_NAMES, SK_COLORS, frames=((0, 0), (1, 1)),
                     title="모두 정상이라고 답한 모델")
            note(ax, 5.3, 3.9, "정확도  1,892 ÷ 2,000 = 0.946", size=18)
            note(ax, 5.3, 3.0, "재현율  0 ÷ 108 = 0", size=18, color=RED, weight="bold")
            return image(fig)
        frames = {1: ((0, 0), (1, 1)), 2: ((0, 1), (1, 1)), 3: ((1, 0), (1, 1)), 4: ((0, 1), (1, 0), (1, 1))}[stage]
        cm_table(ax, 1.5, 1.2, SK, SK_NAMES, SK_COLORS, frames=frames, title="사기 거래 모델의 테스트 2,000건")
        text = {1: ("정확도", "(89 + 1,849) ÷ 2,000", "= 0.969"),
                2: ("정밀도", "89 ÷ (89 + 43) = 89 ÷ 132", "≈ 0.6742"),
                3: ("재현율", "89 ÷ (89 + 19) = 89 ÷ 108", "≈ 0.8241"),
                4: ("F1 점수", "2 × 89 ÷ (2 × 89 + 43 + 19)", "= 178 ÷ 240 ≈ 0.7417")}[stage]
        note(ax, 5.3, 4.3, text[0], size=20, weight="bold")
        note(ax, 5.3, 3.4, text[1], size=17)
        note(ax, 5.3, 2.6, text[2], size=18, weight="bold")
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2200, 2200, 2200, 2200, 2500]


@figure("8f-3", 560, 260)
def metric_choice():
    """어떤 실수가 더 큰 손해인지로 지표를 고르는 표(강사 요약본 2주차 7쪽)."""
    plt, fig, ax = board(520)
    heads = ["지표", "줄이려는 것", "예"]
    xs = [0.3, 2.7, 6.0]
    for x, h in zip(xs, heads):
        ax.text(x, 4.65, h, fontsize=18, weight="bold", color=MUTED)
    rows = [("정밀도", "FP 거짓 양성", "스팸 필터, 광고 클릭 예측", RED_L),
            ("재현율", "FN 거짓 음성", "암 진단, 사기 탐지", RED_L),
            ("F1 점수", "FP 와 FN 둘 다", "보통의 이진 분류", None),
            ("ROC-AUC", "임계값 하나에 묶이지 않음", "확률을 내는 모델 전체", None)]
    for r, (a, b, c, fill) in enumerate(rows):
        yy = 3.85 - r * 0.92
        ax.plot([0.3, 10.9], [yy + 0.46, yy + 0.46], color=FAINT, lw=1.2)
        ax.text(xs[0], yy, a, fontsize=18, weight="bold", va="center")
        ax.text(xs[1], yy, b, fontsize=17, va="center", bbox=dict(boxstyle="round,pad=0.25", fc=fill, ec=fill) if fill else None)
        ax.text(xs[2], yy, c, fontsize=17, va="center")
    return image(fig)


@figure("8f-4", 560, 300)
def roc_scores():
    """거래 10건의 점수로 그린 ROC 곡선(AUC 0.857)과 0.5 로 자른 0/1 로 그린 곡선(AUC 0.762)."""
    pts = ROC
    def at(t):
        tp = sum(s >= t for s in SC_POS)
        fp = sum(s >= t for s in SC_NEG)
        return fp / 7, tp / 3, tp, fp
    f5, t5, tp5, fp5 = at(0.5)
    f35, t35, tp35, fp35 = at(0.35)
    assert (tp5, fp5) == (2, 1) and (tp35, fp35) == (3, 2) and fx(tp35 / (tp35 + fp35), 1) == "0.6"
    scores = sorted([(s, 1) for s in SC_POS] + [(s, 0) for s in SC_NEG], reverse=True)

    def draw(stage):
        plt, fig = new(600)
        ax0 = fig.add_axes([0.04, 0.12, 0.3, 0.8])
        ax0.set_xlim(0, 1)
        ax0.set_ylim(0, 1)
        ax0.axis("off")
        for k, (s, lab) in enumerate(scores):
            yy = 0.93 - k * 0.09
            col = ORANGE if lab else BLUE
            ax0.text(0.08, yy, fx(s, 2), fontsize=16, va="center", color=INK)
            ax0.text(0.42, yy, "사기" if lab else "정상", fontsize=16, va="center", color=col, weight="bold")
        th = {1: 0.5, 2: 0.35}.get(stage)
        if th is not None:
            cut = sum(s >= th for s, _ in scores)
            yy = 0.93 - (cut - 0.5) * 0.09
            ax0.plot([0.02, 0.62], [yy, yy], color=INK, lw=2, ls="--")
            ax0.text(0.65, yy, f"임계값 {num(th, 2)}", fontsize=14, va="center")
        ax = fig.add_axes([0.48, 0.13, 0.33, 0.75])
        tidy(ax)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.05)
        ax.set_xlabel("FPR")
        ax.set_ylabel("TPR")
        ax.plot([0, 1], [0, 1], color=GRAY, lw=1.4, ls=":")
        if stage >= 3:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color=PURPLE, lw=3, zorder=4)
            if stage == 3:
                ax.fill_between(xs, ys, color=PURPLE_L, zorder=1, step=None)
        if stage >= 4:
            xs, ys = zip(*CUT)
            ax.plot(xs, ys, color=RED, lw=2.6, ls="--", zorder=5)
        if stage == 1:
            ax.scatter([f5], [t5], s=150, color=INK, zorder=6)
            note(fig, 0.82, 0.62, "TP 2, FP 1\n(1/7, 2/3)", size=16, transform=fig.transFigure)
        if stage == 2:
            ax.scatter([f5, f35], [t5, t35], s=150, color=INK, zorder=6)
            note(fig, 0.82, 0.62, "TP 3, FP 2\n(2/7, 1)\n재현율 1\n정밀도 0.6", size=16, transform=fig.transFigure)
        if stage == 3:
            note(fig, 0.82, 0.62, "점수로 그림\nAUC = 18/21\n≈ 0.857", size=16, color=PURPLE, transform=fig.transFigure)
        if stage == 4:
            note(fig, 0.82, 0.62, "0/1 로 그림\nAUC = 16/21\n≈ 0.762", size=16, color=RED, transform=fig.transFigure)
        if stage == 5:
            note(fig, 0.82, 0.7, "점수 0.857", size=16, color=PURPLE, transform=fig.transFigure)
            note(fig, 0.82, 0.55, "0/1 0.762", size=16, color=RED, transform=fig.transFigure)
        return image(fig)

    frames = [draw(k) for k in range(1, 6)]
    return frames, [2200, 2200, 2200, 2200, 2500]


@figure("8f-5", 560, 250)
def memo_8f():
    return memo([[(0.2, 5.35, "혼동 행렬과 지표", ["scikit-learn [[TN, FP], [FN, TP]]", "정밀도 TP ÷ (TP + FP)",
                                              "재현율 TP ÷ (TP + FN)"], INK, INK, (0,)),
                  (5.65, 5.35, "지표 고르기와 ROC", ["FP 를 줄이면 정밀도, FN 이면 재현율", "사기 탐지는 재현율 먼저",
                                              "roc_auc_score 에는 확률"], PURPLE, INK, ())]],
                "[[1849, 43], [19, 89]] → 정확도 0.969, 정밀도 0.6742, 재현율 0.8241, F1 0.7417 · 모두 정상이면 0.946")


# 8g

@figure("8g-1", 560, 300)
def broadcast_grid():
    """예측 [4, 1] 과 정답 [4] 를 견주면 [4, 4], 정답을 [4, 1] 로 바꾸면 [4, 1]."""
    pred = np.array([[1], [0], [1], [1]])
    y = np.array([1, 0, 0, 1])
    wide = pred == y
    right = pred == y.reshape(-1, 1)
    assert wide.shape == (4, 4) and int(wide.sum()) == 8 and wide.sum() / 4 == 2.0
    assert right.shape == (4, 1) and int(right.sum()) == 3 and right.sum() / 4 == 0.75
    plt, fig, ax = board(600)
    ax.text(0.3, 5.5, "y.view(" + M + "1, 1) 과 견줌  [4, 1]", fontsize=17, weight="bold", family=CODE)
    ax.text(5.9, 5.5, "y 그대로 견줌  [4, 4]", fontsize=17, weight="bold", family=CODE)
    s = 0.72
    for r in range(4):
        yy = 4.1 - r * s
        ax.text(0.6, yy + s / 2, str(pred[r, 0]), ha="center", va="center", fontsize=17)
        ax.text(1.5, yy + s / 2, str(y[r]), ha="center", va="center", fontsize=17)
        ok = bool(right[r, 0])
        box(ax, 2.2, yy + 0.05, 1.2, s - 0.1, edge=GREEN if ok else RED, fill=GREEN_L if ok else RED_L, lw=1.6)
        ax.text(2.8, yy + s / 2, "True" if ok else "False", ha="center", va="center", fontsize=15, zorder=4)
    ax.text(0.6, 4.95, "pred", ha="center", fontsize=15, color=MUTED, family=CODE)
    ax.text(1.5, 4.95, "y", ha="center", fontsize=15, color=MUTED, family=CODE)
    note(ax, 0.4, 1.0, "True 3개 ÷ 4 = 0.75", size=17)
    for c in range(4):
        ax.text(7.55 + c * s + s / 2, 4.95, str(y[c]), ha="center", fontsize=15, color=MUTED)
    for r in range(4):
        yy = 4.1 - r * s
        ax.text(7.2, yy + s / 2, str(pred[r, 0]), ha="center", va="center", fontsize=15, color=MUTED)
        for c in range(4):
            ok = bool(wide[r, c])
            box(ax, 7.55 + c * s + 0.03, yy + 0.03, s - 0.06, s - 0.06, edge=GREEN if ok else RED,
                fill=GREEN_L if ok else RED_L, lw=1.4)
            ax.text(7.55 + c * s + s / 2, yy + s / 2, "T" if ok else "F", ha="center", va="center", fontsize=15, zorder=4)
    note(ax, 6.0, 1.0, "True 8개 ÷ 4 = 2.0", size=17, color=RED, weight="bold")
    return image(fig)


@figure("8g-2", 560, 250)
def sigmoid_forms():
    """nn.Sigmoid() 층과 torch.sigmoid() 함수가 같은 값을 냄. fill_(1.0) 결과."""
    z = np.array([-1.0, 0.0, 2.0])
    p = sigmoid(z)
    assert [fx(v, 4) for v in p] == ["0.2689", "0.5000", "0.8808"]
    plt, fig, ax = board(500)
    card(ax, 0.25, 1.55, 5.2, 3.2, "층 객체", ["act = nn.Sigmoid()", "p = act(z)", "__init__ 에서 만들고", "forward 에서 부름"],
         GRAY, code_lines=(0, 1))
    card(ax, 5.75, 1.55, 5.2, 3.2, "함수", ["p = torch.sigmoid(z)", "텐서를 바로 넣음", "모델 밖에서 값을 구할 때"], INK,
         code_lines=(0,))
    note(ax, 5.6, 0.95, "z = [" + M + "1, 0, 2] → 둘 다 [0.2689, 0.5, 0.8808]", size=16, ha="center")
    note(ax, 5.6, 0.35, "weight.data.fill_(1.0) → tensor([[1., 1.]])", size=16, ha="center", family=CODE)
    return image(fig)


@figure("8g-3", 560, 260)
def tensor_to_sklearn():
    """logit [2000, 1] 텐서를 0 과 1 을 담은 (2000,) numpy 배열로 바꾸는 줄과 모양."""
    z = [6.1504, -7.2898, -1.9947]
    bools = [v >= 0 for v in z]
    assert bools == [True, False, False]
    plt, fig, ax = board(520)
    steps = [("z_test", "[2000, 1]", ["[6.15]", "[" + M + "7.29]", "[" + M + "1.99]"]),
             (">= 0.0", "[2000, 1]", ["[True]", "[False]", "[False]"]),
             (".cpu().numpy()\n.astype(int)", "(2000, 1)", ["[1]", "[0]", "[0]"]),
             (".flatten()", "(2000,)", ["1", "0", "0"])]
    for k, (code, shape, vals) in enumerate(steps):
        x0 = 0.3 + k * 2.75
        ax.text(x0 + 1.1, 4.6, code, ha="center", va="center", fontsize=15, family=CODE)
        box(ax, x0, 1.3, 2.2, 2.6, edge=GRAY)
        for r, v in enumerate(vals):
            ax.text(x0 + 1.1, 3.4 - r * 0.6, v, ha="center", va="center", fontsize=16, zorder=4,
                    color=GREEN if v in ("[True]",) else (RED if v == "[False]" else INK))
        ax.text(x0 + 1.1, 1.6, "⋮", ha="center", va="center", fontsize=16)
        ax.text(x0 + 1.1, 0.8, shape, ha="center", va="center", fontsize=16, weight="bold")
        if k < 3:
            arrow(ax, x0 + 2.25, 2.6, x0 + 2.7, 2.6)
    return image(fig)


@figure("8g-4", 560, 280)
def record_timing():
    """한 반복 안에서 학습 손실은 갱신 전, 검증 손실은 갱신 뒤에 잼."""
    assert fx(HIST[0, 0], 5) == "4.41009" and fx(HIST[0, 4], 5) == "5.43341"
    plt, fig, ax = board(560)
    ax.text(0.3, 5.1, "첫 반복", fontsize=19, weight="bold")
    ax.plot([0.5, 10.7], [3.4, 3.4], color=GRAY, lw=2.4)
    marks = [(1.4, "w = [1, 1], b = 1", INK), (5.6, "step(): w, b 가 바뀜", INK), (9.4, "한 번 갱신한 w, b", INK)]
    for x, text, col in marks:
        ax.scatter([x], [3.4], s=120, color=col, zorder=4)
        ax.text(x, 3.85, text, ha="center", fontsize=16)
    box(ax, 1.9, 1.75, 2.9, 0.9, edge=SLATE, fill=SLATE_L)
    ax.text(3.35, 2.2, "학습 손실 4.41008", ha="center", va="center", fontsize=16, color=SLATE, zorder=4)
    box(ax, 7.0, 1.75, 2.9, 0.9, edge=PURPLE, fill=PURPLE_L)
    ax.text(8.45, 2.2, "검증 손실 5.33157", ha="center", va="center", fontsize=16, color=PURPLE, zorder=4)
    arrow(ax, 3.35, 3.25, 3.35, 2.7, color=SLATE)
    arrow(ax, 8.45, 3.25, 8.45, 2.7, color=PURPLE)
    note(ax, 5.6, 0.7, "처음 값 w = [1, 1], b = 1 로 잰 검증 손실은 5.43341", size=16, ha="center")
    return image(fig)


@figure("8g-5", 560, 250)
def memo_8g():
    return memo([[(0.2, 5.25, "모양과 판정 줄", ["[N, 1] == [N] → [N, N]", "정답은 view(" + M + "1, 1) 로 [N, 1]",
                                             "nn.Sigmoid() 층, torch.sigmoid() 함수"], INK, INK, (0,)),
                  (5.75, 5.25, "scikit-learn 과 기록", [".cpu().numpy().astype(int).flatten()",
                                                   "confusion_matrix(정답, 예측)", "step() 뒤 검증 손실은 갱신 뒤 값"],
                   PURPLE, INK, (0,))]],
                "정확도가 1 보다 크면 모양부터 확인합니다 · 두 인자를 바꾸면 FP 칸과 FN 칸이 바뀝니다")


# 세 수준으로 다시 보기 블록 그림. 화면 520×280(파일 1040×560), 글자 22 이상은 tools/ai_art/levels.py 를 따름.
# 그림 이름은 <단원>-<단계 번호><수준 번호>(7살 1, 15살 2, 20살 3)이고 색 뜻은 그 단원의 뜻을 그대로 씀.
# 칸마다 바탕색이 다른 표가 필요해서 levels.grid 와 같은 크기 규칙으로 _lv_table 을 둠.

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


def _lv_text(ax, x, y, s, color=INK, size=None, ha="center", va="center", bold=False, rotation=0):
    ax.text(x, y, s, ha=ha, va=va, fontsize=size or LV.FONT, color=color, zorder=6, weight="bold" if bold else "normal",
            rotation=rotation, linespacing=1.3)


def _lv_box(ax, cx, cy, w, h, s, ec=MUTED, fc="white", size=None, bold=False, lw=2.0, color=INK):
    from matplotlib.patches import FancyBboxPatch
    ax.add_patch(FancyBboxPatch((cx - w / 2.0, cy - h / 2.0), w, h, boxstyle="round,pad=0,rounding_size=10", fc=fc, ec=ec,
                                lw=lw, zorder=3))
    if s != "":
        _lv_text(ax, cx, cy, s, color=color, size=size or LV.BIG, bold=bold)


def _lv_arrow(ax, x0, y0, x1, y1, color=INK, lw=2.4):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=4,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=20, shrinkA=0, shrinkB=0))


def _lv_table(rows, col_names=(), row_names=(), fills=None, top="", code=False, pad=28, min_w=72.0, row_tone="muted",
              col_tone="muted"):
    """levels.grid 와 같은 버전·글자 크기의 표. fills 는 {(행, 열): levels.PALE 색 이름이나 FIXED 색}(머리 빼고 0부터)이고
    칠한 칸 글은 굵게 씀. pad 는 칸 글 좌우 여백 합, min_w 는 칸 폭 하한(논리 px). 표나 위 글이 그림 폭을 넘으면 ValueError."""
    from matplotlib.patches import Rectangle
    fills = fills or {}
    fig, ax = LV._canvas()
    room = LV.SIZE[0] - 2 * LV.PAD
    if top and LV._width(fig, top, code=True if code else LV.MATH_FONT) > room:
        raise ValueError("표 위 글 %r 가 그림 폭을 넘습니다." % top)
    LV._top(ax, top, code)
    head_rows = 1 if col_names else 0
    total = len(rows) + head_rows
    if total > 7:
        raise ValueError("표는 머리를 넣어 7행 이하여야 합니다: %d행" % total)
    room_h = LV.SIZE[1] - 2 * LV.PAD - (56 if top else 0)
    cell_h = min(56.0, room_h / total)
    head_w = max([LV._width(fig, n) + pad for n in row_names] + [min_w]) if row_names else 0
    widths = []
    for c in range(len(rows[0])):
        need = [LV._width(fig, row[c], code=code, bold=(r, c) in fills) + pad for r, row in enumerate(rows)]
        if c < len(col_names):
            need.append(LV._width(fig, col_names[c]) + pad)
        widths.append(max(need + [min_w]))
    table_w = head_w + sum(widths)
    if table_w > room:
        raise ValueError("표 폭 %.0f 가 그림 폭 %d 를 넘습니다." % (table_w, room))
    left = (LV.SIZE[0] - table_w) / 2.0
    upper = LV.PAD + (room_h + cell_h * total) / 2.0

    def cell(r, c, text, fill, bold=False, tone="ink", mono=False):
        x = left + (head_w + sum(widths[:c]) if c >= 0 else 0)
        y = upper - (r + 1) * cell_h
        w = head_w if c < 0 else widths[c]
        ax.add_patch(Rectangle((x, y), w, cell_h, fc=fill, ec=COLORS["faint"], lw=1.5))
        ax.text(x + w / 2, y + cell_h / 2, str(text), ha="center", va="center", fontsize=LV.FONT, color=COLORS[tone],
                weight="bold" if bold else "normal", family=LV.CODE_FONT if mono else None)

    for c, name in enumerate(col_names):
        cell(0, c, name, LV.PALE["gray"], tone=col_tone)
    for r, row in enumerate(rows):
        if row_names:
            cell(r + head_rows, -1, row_names[r] if r < len(row_names) else "", LV.PALE["gray"], tone=row_tone)
        for c, text in enumerate(row):
            hit = (r, c) in fills
            cell(r + head_rows, c, text, LV.PALE.get(fills[(r, c)], fills[(r, c)]) if hit else "white", bold=hit, mono=code)
    return fig


# 8c 셋째 단계: 결정 경계. 파랑 바탕은 0, 주황 바탕은 1로 예측하는 쪽, 노랑은 따라가는 꽃, 회색은 경계 위의 점

def _z8c(x1, x2):
    return W_NB[0] * x1 + W_NB[1] * x2 + B_NB


def _levels_8c(level):
    y48 = boundary_x2(4.8, W_NB, B_NB)
    assert fx(y48, 3) == "2.749" and FLOWER[1] > y48
    assert sum(w > y48 for w in (3.2, 3.0, 2.9, 2.6)) == 3  # 7살 물음의 답
    if level == 7:
        fig, ax = _lv_board()
        lo, hi, y0, y1 = 2.3, 3.7, 24.0, 228.0
        ypx = lambda w: y0 + (w - lo) / (hi - lo) * (y1 - y0)  # noqa: E731
        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((150, ypx(y48)), 346, y1 - ypx(y48), fc=LV.PALE["blue"], ec="none", zorder=1))
        ax.add_patch(Rectangle((150, y0), 346, ypx(y48) - y0, fc=LV.PALE["orange"], ec="none", zorder=1))
        ax.plot([150, 150], [y0, y1], color=MUTED, lw=2, zorder=2)
        for w in (2.5, 3.0, 3.5):
            ax.plot([144, 150], [ypx(w)] * 2, color=MUTED, lw=2, zorder=2)
            _lv_text(ax, 138, ypx(w), fx(w, 1), color=MUTED, ha="right")
        _lv_text(ax, 48, (y0 + y1) / 2, "꽃받침 폭", color=MUTED, rotation=90)
        ax.plot([150, 496], [ypx(y48)] * 2, color=INK, lw=3.5, zorder=4)
        _lv_text(ax, 486, ypx(y48) + 6, "검은 선이 지나는 폭 2.749", ha="right", va="bottom")
        ax.scatter([190], [ypx(FLOWER[1])], s=420, color=YELLOW, edgecolors=INK, linewidths=1.5, zorder=5)
        _lv_text(ax, 214, ypx(FLOWER[1]), "첫 단원의 꽃, 폭 3.4", ha="left")
        _lv_text(ax, 486, ypx(3.05), "품종 0으로 예측", color=BLUE, ha="right", bold=True)
        _lv_text(ax, 486, ypx(2.5), "품종 1로 예측", color=ORANGE, ha="right", bold=True)
        _lv_text(ax, 260, 258, "꽃받침 길이가 4.8인 자리")
        return fig
    if level == 15:
        xs2 = [3.4, 3.0, y48, 2.5]
        zs = [_z8c(4.8, w) for w in xs2]
        assert [fx(z, 2) for z in zs] == [M + "3.33", M + "1.28", M + "0.00", "1.27"]
        rows = [["3.4", num(zs[0], 2), "0"], ["3.0", num(zs[1], 2), "0"], ["2.749", "0", "경계"], ["2.5", num(zs[3], 2), "1"]]
        fills = {(0, c): "blue" for c in range(3)}
        fills.update({(1, c): "blue" for c in range(3)})
        fills.update({(2, c): BAND for c in range(3)})
        fills.update({(3, c): "orange" for c in range(3)})
        return _lv_table(rows, col_names=["x2", "z", "예측"], fills=fills, min_w=110,
                         top="z = 2.951 × 4.8 " + M + " 5.115 × x2 " + M + " 0.1045")
    rows = [["w.shape", "(1, 2)"], ["w[0, 0]", "2.9509459"], ["w[0, 1]", "-5.114985"], ["w[1]", "IndexError"]]
    return _lv_table(rows, col_names=["코드", "결과"], fills={(3, 0): "red", (3, 1): "red"},
                     top="w = net.fc.weight.data.numpy()", code=True)


@figure("8c-31", *LV.SIZE)
def levels_8c_7():
    return _levels_8c(7)


@figure("8c-32", *LV.SIZE)
def levels_8c_15():
    return _levels_8c(15)


@figure("8c-33", *LV.SIZE)
def levels_8c_20():
    return _levels_8c(20)


# 8d 셋째 단계: BCEWithLogitsLoss 방식의 기준. 주황은 1 예측, 빨강은 logit 에 0.5 기준을 잘못 쓴 판정, 회색 곡선은 시그모이드,
# 보라는 시그모이드를 두 번 거친 값(이 그림에서만 씀)

def _levels_8d(level):
    zs = np.array([-1.2, 0.3, 2.0])
    ps = sigmoid(zs)
    assert [fx(p, 4) for p in ps] == ["0.2315", "0.5744", "0.8808"]
    if level == 7:
        assert sum(v > 0 for v in (0.1, -0.4, 0.45, 1.5)) == 3  # 7살 물음의 답
        fig, ax = _lv_board()
        for y, word, out, color, fill in ((178, "0과 견줌", "1", ORANGE, LV.PALE["orange"]),
                                          (68, "0.5와 견줌", "0", RED, LV.PALE["red"])):
            _lv_box(ax, 92, y, 110, 62, "0.3")
            _lv_arrow(ax, 152, y, 330, y, color=color if color == RED else INK)
            _lv_text(ax, 241, y + 8, word, color=color if color == RED else INK, va="bottom")
            _lv_box(ax, 400, y, 110, 62, out, ec=color, fc=fill, bold=True, lw=3)
        _lv_text(ax, 92, 238, "모델이 낸 수", color=MUTED)
        _lv_text(ax, 400, 238, "예측", color=MUTED)
        return fig
    if level == 15:
        assert fx(sigmoid(0.5), 4) == "0.6225" and sigmoid(0.0) == 0.5
        p15 = np.array([0.52, 0.6, 0.7])
        assert int((np.log(p15 / (1 - p15)) < 0.5).sum()) == 2  # 15살 물음의 답
        xs = np.linspace(-2.2, 2.6, 121)
        fig = LV.graph(list(xs), [(list(sigmoid(xs)), GRAY, "")], "logit z", "p", top="p = 1 ÷ (1 + e^(" + M + "z))",
                       marks=[(0.0, 0.5, "", "ink"), (0.3, float(ps[1]), "", "orange"), (0.5, float(sigmoid(0.5)), "", "red")],
                       xlim=(-2.3, 2.7), ylim=(0, 1.0))
        ax = fig.axes[0]
        ax.axvspan(0.0, 0.5, color=LV.PALE["red"], zorder=0)
        for p, color in ((0.5, INK), (float(sigmoid(0.5)), RED)):
            ax.plot([-2.3, 0.5 if color == RED else 0.0], [p, p], color=color, lw=1.6, ls=":", zorder=1)
        ax.text(-2.15, 0.5, "0.5", ha="left", va="top", fontsize=LV.FONT, color=INK)
        ax.text(-2.15, float(sigmoid(0.5)) + 0.02, "0.6225", ha="left", va="bottom", fontsize=LV.FONT, color=RED)
        LV._inside(fig)
        return fig
    p2 = sigmoid(ps)
    assert [fx(p, 4) for p in p2] == ["0.5576", "0.6398", "0.7070"] and all(0.5 < p < sigmoid(1.0) for p in p2)
    y = np.array([0.0, 1.0, 1.0])
    once, twice = bce_logit(zs, y), bce_logit(ps, y)
    assert fx(once, 4) == "0.3149" and fx(twice, 4) == "0.5363"
    rows = [[f"{z:.1f}", fx(p, 4), fx(q, 4)] for z, p, q in zip(zs, ps, p2)] + [["", fx(once, 4), fx(twice, 4)]]
    return _lv_table(rows, col_names=["z_out", "한 번", "두 번"], row_names=["데이터 1", "데이터 2", "데이터 3", "손실"],
                     fills={(r, 2): "purple" for r in range(4)}, top="torch.sigmoid(torch.sigmoid(z_out))", code=True)


@figure("8d-31", *LV.SIZE)
def levels_8d_7():
    return _levels_8d(7)


@figure("8d-32", *LV.SIZE)
def levels_8d_15():
    return _levels_8d(15)


@figure("8d-33", *LV.SIZE)
def levels_8d_20():
    return _levels_8d(20)


# 8f 둘째 단계: 혼동 행렬. 초록은 맞힌 칸, 빨강은 틀린 칸

def _levels_8f2(level):
    if level == 7:
        fig, ax = _lv_board()
        for y, name, count, cells in ((150, "실제 정상", TN + FP, ((TN, "green"), (FP, "red"))),
                                      (62, "실제 사기", FN + TP, ((FN, "red"), (TP, "green")))):
            _lv_box(ax, 96, y, 144, 70, "")
            _lv_text(ax, 96, y + 13, name)
            _lv_text(ax, 96, y - 15, comma(count) + "건", bold=True)
            _lv_arrow(ax, 172, y, 206, y)
            for x, (value, tone) in zip((278, 420), cells):
                _lv_box(ax, x, y, 136, 70, comma(value), ec=COLORS[tone], fc=LV.PALE[tone], bold=True, lw=2.5)
        _lv_text(ax, 278, 222, "정상이라고 답함", color=MUTED)
        _lv_text(ax, 420, 222, "사기라고 답함", color=MUTED)
        return fig
    if level == 15:
        assert FN + TP == 108 and TN + FP == 1892 and FP + TP == 132  # 132 는 15살 물음의 답
        rows = [["TN " + comma(TN), "FP " + str(FP), comma(TN + FP)], ["FN " + str(FN), "TP " + str(TP), str(FN + TP)]]
        return _lv_table(rows, col_names=["예측 0", "예측 1", "행의 합"], row_names=["실제 0", "실제 1"],
                         fills={(0, 0): "green", (0, 1): "red", (1, 0): "red", (1, 1): "green", (1, 2): "highlight"},
                         top="실제 사기 수 = FN + TP = 19 + 89 = 108")
    cm, cm_p = [TN, FP, FN, TP], [TP, FN, FP, TN]  # labels=[1, 0] 이면 ravel 순서가 TP, FN, FP, TN
    wrong = dict(zip(("tn", "fp", "fn", "tp"), cm_p))
    assert fx(wrong["tp"] / (wrong["tp"] + wrong["fp"]), 4) == "0.9898"  # 20살 물음: 1849 ÷ 1868
    rows = [[name, str(a), str(b)] for name, a, b in zip(("tn", "fp", "fn", "tp"), cm, cm_p)]
    return _lv_table(rows, col_names=["이름", "cm", "cm_p"], fills={(r, 2): "red" for r in range(4)},
                     top="tn, fp, fn, tp = M.ravel()", code=True, min_w=110)


@figure("8f-21", *LV.SIZE)
def levels_8f2_7():
    return _levels_8f2(7)


@figure("8f-22", *LV.SIZE)
def levels_8f2_15():
    return _levels_8f2(15)


@figure("8f-23", *LV.SIZE)
def levels_8f2_20():
    return _levels_8f2(20)


# 8f 다섯째 단계: AUC. 초록은 사기 쪽 점수가 큰 짝, 빨강은 정상 쪽 점수가 큰 짝, 회색은 같은 짝

def _levels_8f5(level):
    if level == 7:
        assert sum(p > n for p in (0.8, 0.4) for n in (0.6, 0.3, 0.1)) == 5  # 7살 물음의 답
        fills = {(r, c): "green" if p > n else "red" for r, p in enumerate(SC_POS) for c, n in enumerate(SC_NEG)}
        assert sum(v == "green" for v in fills.values()) == PAIRS == 18
        rows = [[""] * len(SC_NEG) for _ in SC_POS]
        return _lv_table(rows, col_names=[f"{n:.2f}" for n in SC_NEG], row_names=[f"{p:.2f}" for p in SC_POS], fills=fills,
                         top="왼쪽은 사기 거래, 위는 정상 거래의 점수", pad=14, min_w=40, row_tone="orange", col_tone="blue")
    if level == 15:
        cut = lambda xs: [1 if s >= 0.5 else 0 for s in xs]  # noqa: E731
        pc, nc = cut(SC_POS), cut(SC_NEG)
        big = sum(p > n for p in pc for n in nc)
        same = sum(p == n for p in pc for n in nc)
        small = sum(p < n for p in pc for n in nc)
        assert (big, same, small) == (12, 8, 1) and abs((big + 0.5 * same) / 21 - AUC_01) < 1e-12
        rows = [["같음 2짝", "큼 12짝"], ["작음 1짝", "같음 6짝"]]
        return _lv_table(rows, col_names=["정상 1, 1건", "정상 0, 6건"], row_names=["사기 1, 2건", "사기 0, 1건"],
                         fills={(0, 0): BAND, (0, 1): "green", (1, 0): "red", (1, 1): BAND}, min_w=130,
                         top="AUC = (12 + 8 × 0.5) ÷ 21 ≈ 0.762")
    lg = lambda xs: [math.log(s / (1 - s)) for s in xs]  # noqa: E731
    assert abs(area(roc_points(lg(SC_POS), lg(SC_NEG))) - AUC_P) < 1e-12
    flip = area(roc_points([1 - s for s in SC_POS], [1 - s for s in SC_NEG]))
    neg = area(roc_points([-s for s in SC_POS], [-s for s in SC_NEG]))
    assert abs(flip - 3 / 21) < 1e-12 and abs(neg - flip) < 1e-12 and fx(flip, 3) == "0.143"
    rows = [["p", fx(AUC_P, 3)], ["np.log(p / (1 - p))", fx(AUC_P, 3)], ["1 - p", fx(flip, 3)]]
    return _lv_table(rows, col_names=["둘째 인자", "AUC"], fills={(2, 0): "red", (2, 1): "red"},
                     top="roc_auc_score(y_true, 둘째 인자)", code=True)


@figure("8f-51", *LV.SIZE)
def levels_8f5_7():
    return _levels_8f5(7)


@figure("8f-52", *LV.SIZE)
def levels_8f5_15():
    return _levels_8f5(15)


@figure("8f-53", *LV.SIZE)
def levels_8f5_20():
    return _levels_8f5(20)
