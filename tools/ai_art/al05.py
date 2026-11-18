# -*- coding: utf-8 -*-
"""응용 5차시 노트 al05 의 그림.

  ~/.cache/rokey-dev/lib/bin/python -m tools.ai_art al05 a5a-1   이름을 적은 그림만 그림

Pillow 로 직접 그린 막대·띠·표·좌표 그래프임. 강의 슬라이드 그림, 노트북에 저장된 그림은 쓰지 않음.
그림에 찍는 크기·장수·파라미터 수는 이 파일에서 다시 계산하고 assert 로 본문 숫자와 견줌.
세 수준 그림은 화면 520×280(파일 1040×560)이고 levels.chain·grid 를 쓰거나 Pillow 로 글자 31px 이상으로 그림.

a5a 색: 주황 = 배치 축 길이(샘플 수), 파랑 = 이번 장에서 바뀐 층과 센 창, 옅은 파랑 = 앞 장에서 지난 층,
회색 = 층 종류 이름표와 채운 칸, 빨강 점선 = 세지 않는 창과 오류가 나는 줄.
a5b 색: 초록 = 기울기 기록 켬, 회색 = 기록 끔, 파랑 칠 = step 이 바꾸는 파라미터, 주황 = 넘겨받은 SGD 옵티마이저.
a5c 색: 파랑 = 검증 정확도와 > 기준, 주황 = >= 기준, 보라 = 검증 손실. 채운 점 = 복사함, 빈 점 = 건너뜀.
a5d 색: 파랑 = 꺼낸 307~312번과 ImageNet 번호, 파랑 칠과 굵은 테두리 = 최댓값, 초록 = ImageFolder 번호,
빨강 = 오류와 섞어 쓴 번호, 회색 테두리 = 두 변환에서 같은 단계, 주황 = 설명용 값 표시와 값이 다른 단계(정규화).
a5e 색: 파랑 = block1, 주황 = block2, 초록 = block3, 보라 = block4, 옅은 칸 = block2·block3 의 첫 층과 첫 층 출력.
"""
from math import ceil, floor, sqrt

from PIL import Image, ImageDraw

from tools.ai_art import COLORS, figure, iso
from tools.ai_art.al04 import arrow
from tools.ai_art.al18 import _dash, _dash_line, _face, _w
from tools.ai_art import levels

W = 1120
INK, MUTED, FAINT = COLORS["ink"], COLORS["muted"], COLORS["faint"]
BLUE, RED, ORANGE, GREEN, PURPLE = COLORS["blue"], COLORS["red"], COLORS["orange"], COLORS["green"], COLORS["purple"]
BLUE_L, GREEN_L, ORANGE_L, RED_L, PURPLE_L = "#dbeafe", "#d1fae5", "#ffedd5", "#fee2e2", "#ede9fe"
NOTE, LINE, LIGHT = "#f3f4f6", "#e5e7eb", "#9ca3af"
MIN_SIZE = 19
LEVEL_MIN = 31  # 세 수준 그림 글자 하한(파일 px). matplotlib 22pt 와 같은 크기
SAVED = "저장된 로그"


# 공통 도우미

def _new(h, w=W):
    image = Image.new("RGB", (w, h), "white")
    return image, ImageDraw.Draw(image)


def _t(d, xy, value, size=22, color=INK, bold=False, code=False, anchor="la", bg=None, low=MIN_SIZE):
    """글자 한 줄. 그림 밖으로 나가거나 하한보다 작으면 assert 로 멈춤. 나눔고딕에 없는 U+2212 는 코드 글꼴로만 씀."""
    value = str(value)
    assert size >= low, (value, size)
    assert code or "−" not in value, value
    face = _face(size, bold, code)
    box = d.textbbox(xy, value, font=face, anchor=anchor)
    width, height = d.im.size
    assert box[0] >= 8 and box[1] >= 6 and box[2] <= width - 8 and box[3] <= height - 6, (value, box)
    if bg:
        d.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill=bg)
    d.text(xy, value, font=face, fill=color, anchor=anchor)
    return box


def _box(d, rect, lines, fill="white", outline=LIGHT, size=22, color=INK, bold=False, code=False, width=2, gap=8,
         radius=12, low=MIN_SIZE):
    """둥근 상자 가운데에 여러 줄. lines 의 항목은 글이나 (글, 색, 굵게, 코드글꼴)."""
    x0, y0, x1, y1 = rect
    d.rounded_rectangle(rect, radius, fill=fill, outline=outline, width=width)
    rows = [item if isinstance(item, tuple) else (item, color, bold, code) for item in lines]
    total = len(rows) * size + (len(rows) - 1) * gap
    assert total <= y1 - y0 - 8, (lines, rect)
    y = (y0 + y1) / 2.0 - total / 2.0 + size / 2.0
    for value, ink, heavy, mono in rows:
        assert _w(value, size, heavy, mono) <= x1 - x0 - 16, (value, rect)
        _t(d, ((x0 + x1) / 2.0, y), value, size, ink, heavy, mono, anchor="mm", low=low)
        y += size + gap


def _shape(d, x, y, dims, size=22, accent=ORANGE, anchor="lm"):
    """[8, 64, 55, 55] 꼴 모양 글. 첫 값(배치 축)만 accent 색 굵게. 오른쪽 끝 x 를 돌려줌."""
    parts = [("[", INK, False), (str(dims[0]), accent, True)] + [(", " + str(v), INK, False) for v in dims[1:]] + [("]", INK, False)]
    total = sum(_w(p, size, b, True) for p, _, b in parts)
    if anchor == "mm":
        x -= total / 2.0
    for value, color, bold in parts:
        _t(d, (x, y), value, size, color, bold, code=True, anchor="lm")
        x += _w(value, size, bold, True)
    return x


def _cross(d, cx, cy, r=13, color=RED, width=5):
    d.line((cx - r, cy - r, cx + r, cy + r), fill=color, width=width)
    d.line((cx - r, cy + r, cx + r, cy - r), fill=color, width=width)


def _out(n, k, s=1, p=0):
    """Conv2d·MaxPool2d 출력 한 변(floor 식)."""
    return floor((n + 2 * p - k) / s) + 1


# a5a AlexNet 공간 크기

ALEX = [("입력", "", None), ("[0]", "합성곱", (11, 4, 2)), ("[2]", "최대 풀링", (3, 2, 0)), ("[3]", "합성곱", (5, 1, 2)),
        ("[5]", "최대 풀링", (3, 2, 0)), ("[6]·[8]·[10]", "합성곱 ×3", (3, 1, 1)), ("[12]", "최대 풀링", (3, 2, 0)),
        ("avgpool", "적응형|평균 풀링", None)]
ALEX_CH = [3, 64, 64, 192, 192, 256, 256, 256]


def _alex_chain(n):
    """features 를 지난 한 변 [입력, [0], [2], [3], [5], [6]~[10], [12]]."""
    sides = [n]
    for _, _, spec in ALEX[1:7]:
        k, s, p = spec
        sides.append(_out(sides[-1], k, s, p))
    return sides


def _a5a_numbers():
    assert _alex_chain(224) == [224, 55, 27, 27, 13, 13, 6]
    assert _alex_chain(256) == [256, 63, 31, 31, 15, 15, 7]
    assert (224 + 4 - 11) / 4 == 54.25 and _out(224, 11, 4, 2) == 55 and ceil(54.25) + 1 == 56


def _a5a_shape(sheet, x, y, dims, size=21):
    """Sheet 에 [8, 64, 55, 55] 꼴 모양 글을 씀. _shape 와 같이 첫 값(배치 축)만 주황 굵게. 오른쪽 끝 x 를 돌려줌."""
    parts = [("[", INK, False), (str(dims[0]), ORANGE, True)] + [(", " + str(v), INK, False) for v in dims[1:]] + [("]", INK, False)]
    for value, color, bold in parts:
        sheet.text((x, y), value, size, color, bold, code=True, anchor="lm")
        x += sheet.measure(value, size, bold, True)
    return x


def _a5a_px(side):
    """한 변 → 상자 앞면 한 변(파일 px). 224 를 185px 로 두고 제곱근 7할, 비례 3할로 섞어 줄임. 그대로 비례하면 6 이 5px 라
    보이지 않음. 제곱근만 쓰면 세로축 눈금 224 와 168 사이가 25px 로 붙음. 섞으면 6 은 23px, 두 눈금 사이는 31px 임.
    세로축 눈금도 같은 식으로 찍음."""
    r = side / 224.0
    return 185.0 * (0.7 * sqrt(r) + 0.3 * r)


def _a5a_depth(channels):
    """채널 수 → 상자 깊이(파일 px). 앞면과 같은 까닭으로 제곱근을 씀. 3채널은 5px, 256채널은 48px."""
    return 3.0 * sqrt(channels)


@figure("a5a-1", 560, 300)
def a5a_sides():
    """AlexNet features 를 지나는 한 변 상자 네 장. 층마다 입체 상자 하나이고 앞면 가로·세로는 한 변, 깊이는 채널 수를 나타냄.
    이번 장에서 새로 나온 층은 진한 파랑(strong), 앞 장에서 지난 층은 옅은 파랑(seen), 입력은 회색(normal)."""
    _a5a_numbers()
    sides = _alex_chain(224) + [6]
    x0, base = 96, 404
    groups = [(0, 1), (2, 3), (4, 5), (6, 7)]
    texts = [
        ([8, 3, 224, 224], [8, 64, 55, 55]),
        ([8, 64, 55, 55], [8, 64, 27, 27], [8, 192, 27, 27]),
        ([8, 192, 27, 27], [8, 192, 13, 13], [8, 256, 13, 13]),
        ([8, 256, 13, 13], [8, 256, 6, 6], [8, 256, 6, 6]),
    ]
    channel = ["채널 %d" % ch if n != 5 else "채널 384→256" for n, ch in enumerate(ALEX_CH)]
    probe = iso.Sheet(8, 8)
    sizes = [(_a5a_px(side), _a5a_depth(ch)) for side, ch in zip(sides, ALEX_CH)]
    spans = [w + d * iso.DEPTH[0] for w, d in sizes]
    labels = [max([probe.measure(name, 19, code=True), probe.measure(channel[n], 19), probe.measure(side, 24, True, True)]
                  + [probe.measure(part, 19) for part in kind.split("|")])
              for n, ((name, kind, _), side) in enumerate(zip(ALEX, sides))]
    # 칸 폭은 상자 사이가 28px 이상, 글 사이가 22px 이상 벌어지게 잡음
    widths = [max(span + 28, label + 22) for span, label in zip(spans, labels)]
    assert x0 + sum(widths) <= W - 20, widths
    centers = [x0 + sum(widths[:n]) + widths[n] / 2.0 for n in range(len(widths))]
    ticks = [base - _a5a_px(v) for v in (0, 56, 112, 168, 224)]
    assert min(a - b for a, b in zip(ticks, ticks[1:])) >= 28, ticks
    frames = []
    for k in range(4):
        s = iso.Sheet(W, 600)
        s.text((40, 18), "AlexNet features를 지나는 한 변", 24, INK, True)
        s.card((990, 36), ["배치 8"], "orange", "new", size=22, pad=(20, 9), width=180)
        s.path([(x0 - 10, base), (x0 + sum(widths), base)], LIGHT, 2)
        s.path([(x0 - 10, base - _a5a_px(224)), (x0 - 10, base)], LIGHT, 2)
        for v in (0, 56, 112, 168, 224):
            y = base - _a5a_px(v)
            s.path([(x0 - 16, y), (x0 - 10, y)], LIGHT, 2)
            s.text((x0 - 22, y), v, 19, MUTED, anchor="rm")
        s.text((x0 - 10, base - _a5a_px(224) - 22), "한 변", 19, MUTED, anchor="mb")
        shown = max(groups[k])
        for n, ((name, kind, _), side) in enumerate(zip(ALEX, sides)):
            cx = centers[n]
            s.text((cx, base + 22), name, 19, INK, code=True, anchor="mm")
            for j, part in enumerate(kind.split("|")):
                if part:
                    s.text((cx, base + 50 + j * 24), part, 19, MUTED, anchor="mm")
            if n > shown:
                continue
            active = n > 0 and n in groups[k]
            state = "normal" if n == 0 else ("strong" if active else "seen")
            w, depth = sizes[n]
            a = s.box(cx - spans[n] / 2.0, base - w, w, w, depth, state)
            s.text((cx, a["above"][1] - 12), side, 24, BLUE if active else INK, True, True, anchor="mb")
            s.text((cx, a["above"][1] - 46), channel[n], 19, MUTED, anchor="mb")
            if n:
                left, right = centers[n - 1] + spans[n - 1] / 2.0 + 5, cx - spans[n] / 2.0 - 5
                assert right - left >= 18, (n, left, right)
                s.arrow((left, base - 12), (right, base - 12), LIGHT, width=iso.ARROW_W, size=(10, 5))
        fx0, fx1 = x0 + widths[0] + 6, x0 + sum(widths[:7]) - 6
        s.path([(fx0, base + 96), (fx0, base + 104), (fx1, base + 104), (fx1, base + 96)], MUTED, 2)
        s.text(((fx0 + fx1) / 2.0, base + 112), "features", 19, MUTED, code=True, anchor="ma")
        x = 40
        for j, dims in enumerate(texts[k]):
            if j:
                s.text((x + 12, 562), "→", 22, MUTED, anchor="lm")
                x += 46
            x = _a5a_shape(s, x, 562, dims, 21)
        frames.append(s.image())
    for k, dims in enumerate(texts):
        assert dims[-1][2] == sides[max(groups[k])] and all(row[0] == 8 for row in dims)
    return frames, [2200, 2200, 2200, 2400]


@figure("a5a-2", 560, 245)
def a5a_starts():
    """padding 2 로 채운 228칸에서 11칸 창의 시작 위치."""
    _a5a_numbers()
    n, k, s, p = 224, 11, 4, 2
    length = n + 2 * p
    starts = list(range(0, length - k + 1, s))
    assert len(starts) == 55 and starts[-1] == 216 and starts[-1] + k - 1 == 226 and length - 1 == 227
    assert 220 + k - 1 == 230 > length - 1
    left, right = list(range(0, 20)), list(range(208, 228))
    hidden = right[0] - left[-1] - 1
    assert hidden == 188
    cell, x0, y = 22, 40, 300
    gap = 64
    image, d = _new(490)

    def cx(i):
        if i <= left[-1]:
            return x0 + i * cell
        return x0 + len(left) * cell + gap + (i - right[0]) * cell

    for i in left + right:
        pad = i < p or i >= length - p
        d.rectangle((cx(i), y, cx(i) + cell, y + 34), fill=NOTE if pad else "white", outline=LIGHT, width=2)
    _t(d, (x0 + len(left) * cell + gap / 2.0, y + 17), "…", 24, MUTED, anchor="mm")
    _t(d, (x0 + len(left) * cell + gap / 2.0, y + 52), "%d칸 생략" % hidden, 19, MUTED, anchor="mm")
    for i in (0, 2, 216):
        _t(d, (cx(i) + cell / 2.0, y + 52), i, 19, MUTED, anchor="mm")
    end = cx(227)
    d.rectangle((end, y, end + cell, y + 34), fill=NOTE, outline=RED, width=3)
    _t(d, (end + cell / 2.0, y + 52), 227, 19, RED, True, anchor="mm")
    _t(d, (end + cell + 4, y + 86), "남은 칸", 19, RED, True, anchor="ra")
    for i in range(228, 231):
        _dash(d, (cx(i), y, cx(i) + cell, y + 34), LIGHT, 2, 4)
    _t(d, (x0, y + 86), "회색 칸: padding으로 채운 칸(양 끝 두 칸씩)", 19, MUTED)
    rows = {0: 0, 4: 1, 8: 2, 212: 0, 216: 1, 220: 2}
    for start, row in rows.items():
        top = y - 30 - row * 62
        a, b = cx(start), cx(start + k - 1) + cell
        if start == 220:
            _dash(d, (a, top, b, top + 22), RED, 3, 7)
            _t(d, (a - 6, top + 11), "시작 220", 19, RED, True, anchor="rm")
            _t(d, (b + 4, top - 4), "끝 230", 19, RED, True, anchor="rb")
        else:
            d.rounded_rectangle((a, top, b, top + 22), 6, fill=BLUE_L, outline=BLUE, width=3)
            _t(d, (a - 6, top + 11), "시작 %d" % start, 19, BLUE, True, anchor="rm") if start >= 212 else \
                _t(d, (b + 8, top + 11), "시작 %d" % start, 19, BLUE, True, anchor="lm")
    _t(d, (40, 22), "11칸 창을 4칸씩 옮긴 시작 위치", 24, INK, True)
    _t(d, (40, 58), "시작 0, 4, 8, …, 216 → 216 ÷ 4 + 1 = %d개" % len(starts), 21, BLUE, True)
    formula = "floor((224 + 4 − 11) ÷ 4) + 1 = floor(%s) + 1 = %d" % ((n + 2 * p - k) / s, _out(n, k, s, p))
    _t(d, (40, 436), formula, 22, INK, code=True)
    return image


@figure("a5a-3", 560, 200)
def a5a_overlap():
    """13칸에 3칸 창을 2칸씩 옮긴 겹치는 최대 풀링."""
    n, k, s = 13, 3, 2
    starts = list(range(0, n - k + 1, s))
    covered = [sum(1 for a in starts if a <= i < a + k) for i in range(n)]
    shared = [i for i, c in enumerate(covered) if c == 2]
    assert starts == [0, 2, 4, 6, 8, 10] and len(starts) == _out(n, k, s) == 6
    assert shared == [2, 4, 6, 8, 10] and max(covered) == 2
    cell = 64
    x0 = (W - n * cell) // 2
    y = 250
    image, d = _new(400)
    _t(d, (40, 22), "MaxPool2d(kernel_size=3, stride=2)", 23, INK, True, code=True)
    for i in range(n):
        heavy = i in shared
        d.rectangle((x0 + i * cell, y, x0 + (i + 1) * cell, y + 56), fill="white", outline=INK if heavy else LIGHT,
                    width=5 if heavy else 2)
        _t(d, (x0 + i * cell + cell / 2.0, y + 28), i, 22, INK, heavy, anchor="mm")
    for j, a in enumerate(starts):
        top = y - 56 - (j % 2) * 58
        color = BLUE if j % 2 == 0 else PURPLE
        d.line((x0 + a * cell + 4, top + 40, x0 + a * cell + 4, y), fill=color, width=2)
        d.line((x0 + (a + k) * cell - 4, top + 40, x0 + (a + k) * cell - 4, y), fill=color, width=2)
    for j, a in enumerate(starts):
        top = y - 56 - (j % 2) * 58
        color, fill = (BLUE, BLUE_L) if j % 2 == 0 else (PURPLE, PURPLE_L)
        d.rounded_rectangle((x0 + a * cell + 4, top, x0 + (a + k) * cell - 4, top + 40), 8, fill=fill, outline=color, width=3)
        _t(d, (x0 + a * cell + k * cell / 2.0, top + 20), "시작 %d" % a, 20, color, True, anchor="mm")
    _t(d, (x0, y + 80), "굵은 테두리: 이웃한 두 창이 함께 덮는 칸", 20, INK)
    return image


def _level_strip(d, x0, y, cells, cell, labels=None, low=LEVEL_MIN):
    for n, i in enumerate(cells):
        d.rectangle((x0 + n * cell, y, x0 + (n + 1) * cell, y + cell), fill="white", outline=MUTED, width=3)
        if labels:
            _t(d, (x0 + n * cell + cell / 2.0, y + cell / 2.0), i, 31, INK, anchor="mm", low=low)


@figure("a5a-31", 520, 280)
def a5a_level7():
    """13칸 줄 위 세 칸 상자 여섯 개. 숫자와 글자 없이 그림."""
    starts = list(range(0, 13 - 3 + 1, 2))
    assert len(starts) == 6
    image, d = _new(560, 1040)
    cell = 70
    x0 = (1040 - 13 * cell) // 2
    y = 322
    _level_strip(d, x0, y, range(13), cell)
    for j, a in enumerate(starts):
        top = y - 70 - (j % 2) * 84
        color = BLUE if j % 2 == 0 else ORANGE
        d.line((x0 + a * cell + 5, top + 56, x0 + a * cell + 5, y), fill=color, width=3)
        d.line((x0 + (a + 3) * cell - 5, top + 56, x0 + (a + 3) * cell - 5, y), fill=color, width=3)
    for j, a in enumerate(starts):
        top = y - 70 - (j % 2) * 84
        color, fill = (BLUE, BLUE_L) if j % 2 == 0 else (ORANGE, ORANGE_L)
        d.rounded_rectangle((x0 + a * cell + 5, top, x0 + (a + 3) * cell - 5, top + 56), 10, fill=fill, outline=color, width=4)
    return image


@figure("a5a-32", 520, 280)
def a5a_level15():
    starts = list(range(0, 13 - 3 + 1, 2))
    rows = [[j + 1, a, a + 2] for j, a in enumerate(starts)]
    assert all(end == start + 2 for _, start, end in rows) and len(rows) == 6
    return levels.grid(rows, col_names=("상자", "시작 칸", "끝 칸"))


@figure("a5a-33", 520, 280)
def a5a_level20():
    """66칸 줄의 오른쪽 끝(56~65번)."""
    n, k, s = 66, 3, 2
    starts = list(range(0, n - k + 1, s))
    last_start = starts[-1]
    assert last_start == 62 and (n - k) // s + 1 == 32 == len(starts) and last_start + s + k - 1 > n - 1
    image, d = _new(560, 1040)
    lo = n - 10
    cells = list(range(lo, n))
    cell = 76
    x0 = 150
    y = 330
    _t(d, (x0 - 24, y + cell / 2.0), "…", 34, MUTED, anchor="rm", low=LEVEL_MIN)
    _level_strip(d, x0, y, cells, cell, labels=True)
    last = x0 + (n - 1 - lo) * cell
    d.rectangle((last, y, last + cell, y + cell), outline=RED, width=5)
    _t(d, (last + cell / 2.0, y + cell + 14), "남은 칸", 31, RED, True, anchor="ma", low=LEVEL_MIN)
    bad = last_start + s
    for j, a in enumerate((last_start - s, last_start, bad)):
        top = y - 66 - j * 96
        a0, a1 = x0 + (a - lo) * cell + 5, x0 + (a - lo + k) * cell - 5
        if a == bad:
            _dash(d, (a0, top, a1, top + 50), RED, 4, 9)
            _t(d, (a0 - 10, top + 25), "시작 %d · 놓을 수 없음" % bad, 31, RED, True, anchor="rm", low=LEVEL_MIN)
        else:
            first = a == last_start - s
            color = BLUE if first else PURPLE
            d.rounded_rectangle((a0, top, a1, top + 50), 10, fill=BLUE_L if first else PURPLE_L, outline=color, width=4)
            _t(d, (a0 - 10, top + 25), "시작 %d" % a, 31, color, True, anchor="rm", low=LEVEL_MIN)
    return image


@figure("a5a-4", 560, 240)
def a5a_two_inputs():
    """224 입력과 256 입력의 한 변을 두 줄 띠로."""
    _a5a_numbers()
    rows = [(224, _alex_chain(224) + [6]), (256, _alex_chain(256) + [6])]
    assert rows[0][1][-2] == 6 and rows[1][1][-2] == 7 and rows[0][1][-1] == rows[1][1][-1] == 6
    image, d = _new(480)
    names = ["입력", "[0]", "[2]", "[3]", "[5]", "[6]·[8]·[10]", "[12]", "avgpool"]
    bw, step, x0 = 86, 120, 150
    _t(d, (40, 22), "입력 크기에 따른 한 변", 24, INK, True)
    for n, name in enumerate(names):
        _t(d, (x0 + n * step + bw / 2.0, 100), name, 19, MUTED, code=True, anchor="mm")
    for r, (size, sides) in enumerate(rows):
        y = 140 + r * 130
        _t(d, (40, y + 32), "%d 입력" % size, 22, INK, True, anchor="lm")
        for n, side in enumerate(sides):
            x = x0 + n * step
            last = n == len(sides) - 1
            end = n == len(sides) - 2
            d.rounded_rectangle((x, y, x + bw, y + 64), 10, fill=GREEN_L if last else ("white" if not end else NOTE),
                                outline=GREEN if last else LIGHT, width=4 if last else 2)
            _t(d, (x + bw / 2.0, y + 32), side, 26, GREEN if last else INK, True, anchor="mm")
            if not last:
                arrow(d, (x + bw + 4, y + 32), (x + step - 4, y + 32), MUTED, 3)
    _t(d, (40, 418), "features 끝: 224 입력은 6×6, 256 입력은 7×7(회색 칸)", 21, INK)
    _t(d, (40, 450), "avgpool 뒤: 두 입력 모두 6×6(초록 테두리)", 21, GREEN, True)
    return image


@figure("a5a-5", 560, 280)
def a5a_flatten():
    """[25, 16, 6, 6] 을 576 과 400 으로 펼친 두 경로."""
    batch, c, h = 25, 16, 6
    per = c * h * h
    total = batch * per
    assert per == 576 and total == 14400 == 36 * 400 and total // 400 == 36
    assert (24 * per) % 400 != 0
    image, d = _new(560)
    _box(d, (40, 238, 270, 302), [""], NOTE, LIGHT, 22)
    _shape(d, 155, 270, [batch, c, h, h], 23, anchor="mm")
    _t(d, (155, 222), "펼치기 직전", 19, MUTED, anchor="mb")
    for y in (130, 410):
        d.line((270, 270, 300, 270), fill=MUTED, width=3)
        d.line((300, 270, 300, y), fill=MUTED, width=3)
        arrow(d, (300, y), (330, y), MUTED, 3)
    _t(d, (338, 70), "view(-1, flat_length(x)) · 실행 중에 센 576", 21, BLUE, True, code=False)
    _box(d, (338, 100, 488, 160), [""], "white", LIGHT)
    _shape(d, 413, 130, [batch, per], 22, anchor="mm")
    arrow(d, (494, 130), (534, 130), MUTED, 3)
    _box(d, (540, 100, 820, 160), [("fc1 Linear(400, 120)", INK, False, True)], "white", RED, 21, width=3)
    _cross(d, 846, 130)
    _t(d, (870, 130), "576 ≠ 400", 21, RED, True, anchor="lm")
    _t(d, (338, 190), "fc1 줄에서 모양 오류", 19, RED)
    _t(d, (338, 350), "view(-1, 400) · 고정한 400", 21, BLUE, True)
    _box(d, (338, 380, 478, 440), [""], "white", LIGHT)
    _shape(d, 408, 410, [36, 400], 22, anchor="mm")
    arrow(d, (484, 410), (514, 410), MUTED, 3)
    _box(d, (520, 380, 630, 440), ["fc1 통과"], "white", LIGHT, 21)
    arrow(d, (636, 410), (666, 410), MUTED, 3)
    _box(d, (672, 380, 800, 440), [""], "white", LIGHT)
    _shape(d, 736, 410, [36, 10], 22, anchor="mm")
    arrow(d, (806, 410), (836, 410), MUTED, 3)
    _box(d, (842, 380, 1060, 440), [("CrossEntropyLoss", INK, False, True)], "white", RED, 20, width=3)
    _cross(d, 1082, 410)
    _t(d, (842, 470), "출력 36행 · 정답 25개", 19, RED, True)
    _t(d, (338, 470), "손실 줄에서 처음 오류", 19, RED)
    _t(d, (40, 520), "주황 숫자는 첫 축 길이입니다.", 19, MUTED)
    return image


# a5b 학습 단계와 검증 단계

TRAIN, VAL, BATCH = 244, 153, 8


@figure("a5b-1", 560, 200)
def a5b_modes():
    """dset 값마다 모드와 기울기 기록."""
    rows = []
    for dset in ("train", "val"):
        on = dset == "train"
        rows.append(("'%s'" % dset, "train()" if on else "eval()", str(on), "켬" if on else "끔", on))
    assert rows[0][2] == "True" and rows[1][2] == "False"
    image, d = _new(400)
    cols = [(40, 230), (230, 470), (470, 840), (840, 1080)]
    heads = ["dset", "모드", "set_grad_enabled 값", "기울기 기록"]
    for (a, b), head in zip(cols, heads):
        d.rectangle((a, 30, b, 90), fill=NOTE, outline=LINE, width=2)
        _t(d, ((a + b) / 2.0, 60), head, 21, MUTED, anchor="mm")
    for r, (dset, mode, value, rec, on) in enumerate(rows):
        y = 90 + r * 90
        for n, ((a, b), cell) in enumerate(zip(cols, (dset, mode, value, rec))):
            fill = (GREEN_L if on else NOTE) if n == 3 else "white"
            d.rectangle((a, y, b, y + 90), fill=fill, outline=LINE, width=2)
            if n == 3:
                cx = (a + b) / 2.0 - 30
                if on:
                    d.ellipse((cx - 12, y + 33, cx + 12, y + 57), fill=GREEN)
                else:
                    d.ellipse((cx - 12, y + 33, cx + 12, y + 57), outline=MUTED, width=3)
                _t(d, (cx + 26, y + 45), cell, 24, GREEN if on else MUTED, True, anchor="lm")
            else:
                _t(d, ((a + b) / 2.0, y + 45), cell, 24, INK, n == 0, code=True, anchor="mm")
    _t(d, (40, 316), "AlexNet에서 모드에 따라 바뀌는 층: classifier 안 Dropout 두 개", 21, INK)
    _t(d, (40, 352), "BatchNorm 층은 없습니다.", 19, MUTED)
    return image


@figure("a5b-2", 560, 280)
def a5b_epoch():
    """한 에폭의 학습 31배치와 검증 20배치."""
    tb, vb = ceil(TRAIN / BATCH), ceil(VAL / BATCH)
    tl, vl = TRAIN - BATCH * (tb - 1), VAL - BATCH * (vb - 1)
    assert (tb, tl, vb, vl) == (31, 4, 20, 1)
    unit = 23
    x0 = 170
    rows = [("학습 %d장" % TRAIN, "기록 켬", tb, tl, 120, True), ("검증 %d장" % VAL, "기록 끔", vb, vl, 280, False)]
    states = [(0, 0), (0, tb - 1), (1, 0), (1, vb - 1)]
    steps = [1, tb, tb, tb]
    notes = [
        ["학습 배치 1 · 8장", "기록 켬 → 순전파 · 손실 · backward · step"],
        ["학습 배치 %d · 남은 %d장" % (tb, tl), "기록 켬 → 순전파 · 손실 · backward · step"],
        ["검증 배치 1 · 8장", "기록 끔 → 순전파 · 손실만 계산, step 없음"],
        ["검증 배치 %d · 남은 %d장" % (vb, vl), "기록 끔 → 순전파 · 손실만 계산, step 없음"],
    ]
    frames = []
    for k, (row_now, idx_now) in enumerate(states):
        image, d = _new(560)
        _t(d, (40, 22), "한 에폭 · 배치 8", 24, INK, True)
        for r, (name, rec, count, last, y, on) in enumerate(rows):
            _t(d, (40, y + 4), name, 21, INK, True)
            _t(d, (40, y + 34), rec, 19, GREEN if on else MUTED, True)
            x = x0
            for i in range(count):
                w = unit * (last / BATCH if i == count - 1 else 1)
                done = r < row_now or (r == row_now and i <= idx_now)
                now = r == row_now and i == idx_now
                if on:
                    fill = GREEN if done else GREEN_L
                else:
                    fill = MUTED if done else NOTE
                d.rectangle((x, y, x + w, y + 46), fill=fill, outline="white", width=1)
                if now:
                    d.rectangle((x - 3, y - 4, x + w + 3, y + 50), outline=INK, width=4)
                if on and done:
                    d.polygon([(x + w / 2.0, y + 52), (x + w / 2.0 - 6, y + 64), (x + w / 2.0 + 6, y + 64)], fill=BLUE)
                x += w
            _t(d, (x0, y + 70 + (8 if on else 0)), "8장", 19, MUTED)
            _t(d, (x, y + 70 + (8 if on else 0)), "%d장" % last, 19, MUTED, anchor="ra")
            _t(d, ((x0 + x) / 2.0, y + 70 + (8 if on else 0)), "%d배치" % count, 19, INK, True, anchor="ma")
        d.polygon([(x0 + 70, 206), (x0 + 64, 218), (x0 + 76, 218)], fill=BLUE)
        _t(d, (x0 + 84, 212), "step 호출", 19, BLUE, True, anchor="lm")
        _box(d, (40, 400, 900, 520), [(notes[k][0], INK, True, False), (notes[k][1], INK, False, False)], NOTE, LIGHT, 22,
             gap=14)
        d.rounded_rectangle((930, 120, 1080, 330), 12, fill="white", outline=BLUE, width=3)
        _t(d, (1005, 160), "step 누적", 21, MUTED, anchor="mm")
        _t(d, (1005, 232), steps[k], 56, BLUE, True, anchor="mm")
        _t(d, (1005, 296), "번", 21, MUTED, anchor="mm")
        frames.append(image)
    assert steps[-1] == 31
    return frames, [2000] * 4


@figure("a5b-3", 560, 260)
def a5b_shadow():
    """함수 인자 optim 이 모듈 이름을 가리는 모습."""
    image, d = _new(520)
    size = 19
    d.rounded_rectangle((30, 20, 810, 466), 16, fill="white", outline=LIGHT, width=3)
    _t(d, (50, 32), "코드 전체", 20, MUTED, True)
    d.rounded_rectangle((50, 116, 790, 376), 14, fill=ORANGE_L, outline=ORANGE, width=3)
    _t(d, (70, 128), "finetune_model 안", 20, ORANGE, True)
    rows = [(70, "import torch.optim as optim", "optim", True), (180, "def finetune_model(model, loss_func, optim, ...):",
            "optim,", False), (240, "    optim.zero_grad()", "optim.", False), (300, "    optim.step()", "optim.", False),
            (416, "optimizer = optim.SGD(...)", "optim.", True)]
    _box(d, (850, 20, 1090, 466), [("torch.optim", BLUE, True, True), ("모듈", BLUE, False, False)], BLUE_L, BLUE, 22, width=3)
    _box(d, (600, 166, 774, 336), [("SGD", ORANGE, True, False), ("옵티마이저", ORANGE, True, False),
                                   ("넘겨받은 객체", ORANGE, False, False)], "white", ORANGE, 21, width=3)
    for y, code, word, outer in rows:
        x = 70
        _t(d, (x, y), code, size, INK, code=True)
        pos = code.rfind(word) if word == "optim" else code.find(word)
        assert pos >= 0 and code[pos:pos + 5] == "optim"
        a = x + _w(code[:pos], size, code=True)
        b = a + _w("optim", size, code=True)
        end = x + _w(code, size, code=True)
        color = BLUE if outer else ORANGE
        d.line((a, y + 25, b, y + 25), fill=color, width=4)
        arrow(d, (end + 10, y + 11), (842 if outer else 592, y + 11), color, 3)
    _t(d, (30, 490), "파란 밑줄은 torch.optim 모듈, 주황 밑줄은 넘겨받은 SGD 옵티마이저입니다.", 19, MUTED, anchor="lm")
    return image


def _alex_params():
    feats = [(3, 64, 11), (64, 192, 5), (192, 384, 3), (384, 256, 3), (256, 256, 3)]
    features = sum(cin * cout * k * k + cout for cin, cout, k in feats)
    front = (9216 * 4096 + 4096) + (4096 * 4096 + 4096)
    old_head, new_head = 4096 * 1000 + 1000, 4096 * 2 + 2
    assert features == 2469696 and features + front + old_head == 61100840
    assert 61100840 - old_head + new_head == 57012034 and new_head == 8194
    return features, front, new_head


@figure("a5b-4", 560, 240)
def a5b_params():
    """옵티마이저에 넘긴 파라미터 범위 두 가지."""
    features, front, head = _alex_params()
    total = features + front + head
    rows = [("optim.SGD(model_finetuned.parameters(), ...)", (True, True, True), total),
            ("optim.SGD(model_finetuned.classifier[6].parameters(), ...)", (False, False, True), head)]
    image, d = _new(480)
    boxes = [("features", 40, 330), ("classifier 앞쪽 층", 340, 640), ("classifier[6]", 650, 820)]
    for r, (code, filled, count) in enumerate(rows):
        y = 40 + r * 180
        _t(d, (40, y), code, 19, INK, code=True)
        for (name, a, b), on in zip(boxes, filled):
            d.rounded_rectangle((a, y + 40, b, y + 110), 10, fill=BLUE if on else "white", outline=BLUE if on else LIGHT,
                                width=2)
            _t(d, ((a + b) / 2.0, y + 75), name, 21, "white" if on else MUTED, on, code=name != "classifier 앞쪽 층",
               anchor="mm")
        _t(d, (850, y + 75), "{:,}개".format(count), 28, BLUE, True, anchor="lm")
    assert "{:,}".format(total) == "57,012,034" and "{:,}".format(head) == "8,194"
    d.rectangle((40, 420, 64, 444), fill=BLUE)
    _t(d, (76, 432), "칠한 상자: step이 바꾸는 파라미터", 20, INK, anchor="lm")
    _t(d, (1080, 432), "상자 폭은 축척 없는 도식", 19, MUTED, anchor="rm")
    return image


# a5c 손실 기준과 정확도 기준

CORRECT = [109, 125, 132, 135, 137, 137, 137, 138, 138, 138]
ACC_TEXT = ["0.7124", "0.8170", "0.8627", "0.8824", "0.8954", "0.8954", "0.8954", "0.9020", "0.9020", "0.9020"]
LOSS = [0.5955, 0.4858, 0.4206, 0.3751, 0.3517, 0.3335, 0.3175, 0.3050, 0.2958, 0.2898]


def _copies(ge=False):
    """비교 기호로 복사한 에폭 목록과 남은 에폭."""
    best, copied = 0, []
    for e, c in enumerate(CORRECT):
        if c >= best if ge else c > best:
            best = c
            copied.append(e)
    return copied, copied[-1]


def _a5c_numbers():
    assert ["%.4f" % (c / float(VAL)) for c in CORRECT] == ACC_TEXT
    assert _copies() == ([0, 1, 2, 3, 4, 7], 7) and _copies(True) == (list(range(10)), 9)
    assert all(a > b for a, b in zip(LOSS, LOSS[1:])) and LOSS.index(min(LOSS)) == 9


@figure("a5c-1", 560, 240)
def a5c_first_five():
    """0~4번 에폭의 비교와 복사 표."""
    _a5c_numbers()
    image, d = _new(480)
    cols = [(40, 160), (160, 380), (380, 650), (650, 870), (870, 1080)]
    heads = ["에폭", "검증 정확도", "비교 직전 accuracy", "비교 결과", "복사 여부"]
    for (a, b), head in zip(cols, heads):
        d.rectangle((a, 24, b, 76), fill=NOTE, outline=LINE, width=2)
        _t(d, ((a + b) / 2.0, 50), head, 22, MUTED, anchor="mm")
    best = "0.0"
    for e in range(5):
        y = 76 + e * 66
        ok = CORRECT[e] > (CORRECT[e - 1] if e else 0)
        assert ok
        cells = [str(e), ACC_TEXT[e], best, "%s > %s 참" % (ACC_TEXT[e], best), "복사함"]
        for n, ((a, b), cell) in enumerate(zip(cols, cells)):
            d.rectangle((a, y, b, y + 66), fill="white", outline=LINE, width=2)
            if n == 4:
                cx = (a + b) / 2.0 - 30
                d.ellipse((cx - 11, y + 22, cx + 11, y + 44), fill=BLUE)
                _t(d, (cx + 22, y + 33), cell, 22, BLUE, True, anchor="lm")
            else:
                _t(d, ((a + b) / 2.0, y + 33), cell, 21 if n == 3 else 22, INK, n == 1, code=n == 3, anchor="mm")
        best = ACC_TEXT[e]
    _t(d, (40, 436), SAVED, 19, MUTED)
    _t(d, (1080, 436), "● 복사함", 19, BLUE, True, anchor="ra")
    return image


def _plot_axes(d, box, ylo, yhi, ticks, ylabel, fmt="%.2f"):
    x0, y0, x1, y1 = box

    def px(e):
        return x0 + 24 + e * (x1 - x0 - 48) / 9.0

    def py(v):
        return y1 - (v - ylo) * (y1 - y0) / float(yhi - ylo)

    d.line((x0, y1, x1, y1), fill=LIGHT, width=2)
    d.line((x0, y0, x0, y1), fill=LIGHT, width=2)
    for v in ticks:
        d.line((x0 - 6, py(v), x1, py(v)), fill=COLORS["grid"], width=1)
        _t(d, (x0 - 10, py(v)), fmt % v, 19, MUTED, anchor="rm")
    for e in range(10):
        _t(d, (px(e), y1 + 10), e, 19, MUTED, anchor="ma")
    _t(d, ((x0 + x1) / 2.0, y1 + 38), "에폭 번호(0부터)", 19, MUTED, anchor="ma")
    _t(d, (x0, y0 - 14), ylabel, 19, MUTED, anchor="lb")
    return px, py


def _acc_steps(d, px, py, upto, color=BLUE, width=4):
    vals = [c / float(VAL) for c in CORRECT]
    for e in range(upto):
        d.line((px(e), py(vals[e]), px(e + 1), py(vals[e])), fill=color, width=width)
        if vals[e + 1] != vals[e]:
            d.line((px(e + 1), py(vals[e]), px(e + 1), py(vals[e + 1])), fill=color, width=width)
    return vals


def _dot(d, x, y, color, filled, r=10):
    if filled:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color, outline=color, width=3)
    else:
        d.ellipse((x - r, y - r, x + r, y + r), fill="white", outline=color, width=4)


@figure("a5c-2", 560, 280)
def a5c_ties():
    """> 와 >= 가 복사하는 에폭."""
    _a5c_numbers()
    gt, keep_gt = _copies()
    ge, keep_ge = _copies(True)
    shown = [4, 6, 9, 9]
    keeps = ["4번 에폭", "4번 에폭", "7번 에폭", None]
    frames = []
    for k in range(4):
        image, d = _new(560)
        _t(d, (40, 18), "검증 정확도와 가중치 복사", 24, INK, True)
        _t(d, (1080, 22), SAVED, 19, MUTED, anchor="ra")
        px, py = _plot_axes(d, (120, 100, 770, 350), 0.70, 0.92, (0.70, 0.75, 0.80, 0.85, 0.90),
                            "검증 정확도(세로축 0.70부터)")
        last = shown[k]
        vals = _acc_steps(d, px, py, last, LIGHT if k == 3 else BLUE, 3 if k == 3 else 4)
        rule = ge if k == 3 else gt
        color = ORANGE if k == 3 else BLUE
        for e in range(last + 1):
            _dot(d, px(e), py(vals[e]), color, e in rule)
        for e in (0, 1, 2, 3, 4, 7):
            if e <= last:
                if e == 0:
                    _t(d, (px(e) - 8, py(vals[e]) - 16), ACC_TEXT[e], 19, INK, anchor="lb")
                else:
                    _t(d, (px(e) - 6, py(vals[e]) - 16), ACC_TEXT[e], 19, INK, anchor="mb")
        for r, (sign, copied, tone) in enumerate(((">", gt, BLUE), (">=", ge, ORANGE))):
            if r == 1 and k < 3:
                continue
            y = 446 + r * 44
            faint = k == 3 and r == 0
            ink = LIGHT if faint else tone
            _t(d, (40, y), sign, 21, ink, True, code=True, anchor="lm")
            _t(d, (40 + _w(sign, 21, True, True) + 8, y), "복사", 20, ink, True, anchor="lm")
            for e in range(last + 1 if r == 0 else 10):
                _dot(d, px(e), y, ink, e in copied, 9)
        if k < 3:
            _box(d, (820, 130, 1080, 280), [("남은 사본", MUTED, False, False), (keeps[k], BLUE, True, False)], "white", BLUE,
                 24, width=3, gap=16)
        else:
            _box(d, (820, 110, 1080, 330), [("남은 사본", MUTED, False, False), ("> 기준: %d번 에폭" % keep_gt, MUTED, True, False),
                                           (">= 기준: %d번 에폭" % keep_ge, ORANGE, True, False)], "white", ORANGE, 23,
                 width=3, gap=18)
        _dot(d, 830, 446, color, True, 9)
        _t(d, (850, 446), "복사함", 19, INK, anchor="lm")
        _dot(d, 830, 490, color, False, 9)
        _t(d, (850, 490), "건너뜀", 19, INK, anchor="lm")
        frames.append(image)
    assert keep_gt == 7 and keep_ge == 9
    return frames, [2000, 2200, 2200, 2200]


@figure("a5c-31", 520, 280)
def a5c_level7():
    return levels.chain(["137장", "138장", "138장"])


@figure("a5c-32", 520, 280)
def a5c_level15():
    epochs = [3, 4, 5, 6]
    counts = [CORRECT[e] for e in epochs]
    acc = [ACC_TEXT[e] for e in epochs]
    assert counts == [135, 137, 137, 137] and acc == ["0.8824", "0.8954", "0.8954", "0.8954"]
    return levels.grid([counts, acc], col_names=["에폭 %d" % e for e in epochs], row_names=("맞힌 장수", "정확도"))


@figure("a5c-33", 520, 280)
def a5c_level20():
    accs = [0.5, 0.7, 0.7]
    best, kept, rows = 0.0, None, []
    for e, acc in enumerate(accs):
        before, hit = best, acc > best
        if hit:
            best, kept = acc, e
        rows.append([str(acc), str(before), "참" if hit else "거짓", str(kept)])
    assert rows == [["0.5", "0.0", "참", "0"], ["0.7", "0.5", "참", "1"], ["0.7", "0.7", "거짓", "1"]]
    return levels.grid(rows, col_names=("acc", "직전 best", "acc > best", "kept"),
                       row_names=("위치 0", "위치 1", "위치 2"))


@figure("a5c-3", 560, 240)
def a5c_two_rules():
    """검증 손실 선과 검증 정확도 계단."""
    _a5c_numbers()
    image, d = _new(480)
    _t(d, (40, 18), "같은 로그의 두 기준", 24, INK, True)
    _t(d, (1080, 22), SAVED, 19, MUTED, anchor="ra")
    px, py = _plot_axes(d, (110, 110, 520, 400), 0.20, 0.65, (0.2, 0.3, 0.4, 0.5, 0.6), "검증 손실(세로축 0.2부터)", "%.1f")
    pts = [(px(e), py(v)) for e, v in enumerate(LOSS)]
    d.line(pts, fill=PURPLE, width=4)
    for x, y in pts:
        d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=PURPLE)
    x9, y9 = pts[9]
    d.ellipse((x9 - 12, y9 - 12, x9 + 12, y9 + 12), outline=PURPLE, width=4)
    _t(d, (x9, y9 - 22), "손실 최소 9번", 20, PURPLE, True, anchor="rb")
    _t(d, (pts[0][0] + 14, pts[0][1]), "%.4f" % LOSS[0], 19, INK, anchor="lm")
    _t(d, (x9, y9 + 18), "%.4f" % LOSS[9], 19, INK, anchor="ma")
    qx, qy = _plot_axes(d, (670, 110, 1080, 400), 0.70, 0.92, (0.70, 0.75, 0.80, 0.85, 0.90), "검증 정확도(세로축 0.70부터)")
    vals = _acc_steps(d, qx, qy, 9)
    gt, keep = _copies()
    for e in range(10):
        _dot(d, qx(e), qy(vals[e]), BLUE, e in gt, 7)
    x7, y7 = qx(keep), qy(vals[keep])
    d.ellipse((x7 - 14, y7 - 14, x7 + 14, y7 + 14), outline=BLUE, width=4)
    sign = _w(">", 20, True, True) + 6
    label = "기준 %d번" % keep
    left = x7 - (sign + _w(label, 20, True)) / 2.0
    _t(d, (left, y7 - 22), ">", 20, BLUE, True, code=True, anchor="lb")
    _t(d, (left + sign, y7 - 22), label, 20, BLUE, True, anchor="lb")
    return image


@figure("a5c-4", 560, 200)
def a5c_same_four():
    """검증 로더가 매번 같은 네 장을 고르는 경로."""
    classes = sorted(["bees", "ants"])
    assert classes == ["ants", "bees"] and classes.index("ants") == 0
    image, d = _new(400)
    bw, gap, y0, y1 = 190, 32, 60, 300
    items = [
        [("폴더 이름 정렬", INK, True, False), ("ants → 0", INK, False, True), ("bees → 1", INK, False, True)],
        [("파일 이름 정렬", INK, True, False), ("ants 폴더의", INK, False, False), ("파일이 앞", INK, False, False)],
        [("검증 로더", INK, True, False), ("shuffle=False", INK, False, True), ("같은 순서로 8장씩", INK, False, False)],
        [("검증 변환", INK, True, False), ("Resize(256)", INK, False, True), ("CenterCrop(224)", INK, False, True),
         ("무작위 단계 없음", MUTED, False, False)],
    ]
    for n, lines in enumerate(items):
        x = 40 + n * (bw + gap)
        _box(d, (x, y0, x + bw, y1), lines, "white", LIGHT, 20, gap=14)
        arrow(d, (x + bw + 4, (y0 + y1) / 2.0), (x + bw + gap - 4, (y0 + y1) / 2.0), MUTED, 3)
    x = 40 + 4 * (bw + gap)
    d.rounded_rectangle((x, y0, x + bw, y1), 12, fill="white", outline=BLUE, width=3)
    _t(d, (x + bw / 2.0, y0 + 26), "앞 네 장", 20, INK, True, anchor="mm")
    cell = 64
    gx, gy = x + (bw - 2 * cell) / 2.0, y0 + 56
    for r in range(2):
        for c in range(2):
            d.rectangle((gx + c * cell, gy + r * cell, gx + (c + 1) * cell, gy + (r + 1) * cell), fill=BLUE_L, outline=BLUE,
                        width=2)
            _t(d, (gx + c * cell + cell / 2.0, gy + r * cell + cell / 2.0), classes.index("ants"), 26, BLUE, True,
               anchor="mm")
    _t(d, (x + bw / 2.0, y1 - 26), "정답 번호", 19, MUTED, anchor="mm")
    _t(d, (40, 340), "칸 안 숫자는 사진 대신 적은 정답 클래스 번호입니다.", 19, MUTED)
    return image


# a5d 1000개 출력 번호와 라벨 사전
# 색: 파랑 = 꺼낸 307~312번과 예측 번호, 파랑 칠과 굵은 테두리 = 최댓값, 빨강 = 오류와 섞어 쓴 번호,
# 회색 테두리 = 두 변환에서 같은 단계, 주황 굵은 테두리 = 다른 단계(정규화).

SCORES = {307: 1.2, 308: 2.1, 309: 6.4, 310: 8.3, 311: 0.7, 312: 1.5}
LABEL_TEXT = "{309: 'bee', 310: 'ant, emmet, pismire'}"


def _a5d_numbers():
    best = max(SCORES, key=SCORES.get)
    assert best == 310 and SCORES[best] == 8.3 and len(SCORES) == 6
    return best


@figure("a5d-1", 560, 300)
def a5d_argmax():
    """점수 1000개 띠에서 307~312번을 꺼내 가장 큰 번호 고르기."""
    best = _a5d_numbers()
    groups = [list(range(0, 5)), list(range(307, 313)), list(range(995, 1000))]
    assert groups[0][0] == 0 and groups[-1][-1] == 999 and sum(len(g) for g in groups) == 16
    cell, gap, x0, by = 52, 84, 64, 100
    xs = {}
    x = x0
    for n, group in enumerate(groups):
        for i in group:
            xs[i] = x
            x += cell
        if n < len(groups) - 1:
            x += gap
    assert x <= W - 40
    bars = sorted(SCORES)
    bw, step, bx0, base, top = 80, 116, 170, 520, 290
    scale = (base - top) / 9.0
    frames = []
    for k in range(3):
        image, d = _new(600)
        _t(d, (40, 20), "사진 한 장의 출력 ops[0] · 점수 1000개", 24, INK, True)
        _box(d, (790, 14, 1090, 58), [("설명용 값 · 실행 결과 아님", ORANGE, True, False)], ORANGE_L, ORANGE, 20, width=2)
        for i, cx in xs.items():
            picked = k >= 1 and i in SCORES
            d.rectangle((cx, by, cx + cell, by + 44), fill=BLUE_L if picked else "white",
                        outline=BLUE if picked else LIGHT, width=3 if picked else 2)
            if i in (0, 4, 307, 312, 995, 999) or (k >= 1 and i in SCORES):
                _t(d, (cx + cell / 2.0, by + 56), i, 19, BLUE if picked else MUTED, picked, anchor="ma")
        for n in range(2):
            mid = xs[groups[n][-1]] + cell + gap / 2.0
            _t(d, (mid, by + 22), "…", 24, MUTED, anchor="mm")
        if k == 0:
            _t(d, (40, by + 96), "0번부터 999번까지 칸마다 점수 하나", 19, MUTED)
        if k >= 1:
            left, right = xs[307], xs[312] + cell
            _dash_line(d, (left, by + 82, bx0 - 20, top - 30), LIGHT, 2, 6)
            _dash_line(d, (right, by + 82, bx0 + 5 * step + bw + 20, top - 30), LIGHT, 2, 6)
            d.line((bx0 - 30, base, bx0 + 5 * step + bw + 30, base), fill=LIGHT, width=2)
            for n, i in enumerate(bars):
                x = bx0 + n * step
                h = SCORES[i] * scale
                top_bar = i == best and k == 2
                d.rectangle((x, base - h, x + bw, base), fill=BLUE if top_bar else BLUE_L,
                            outline=INK if top_bar else BLUE, width=5 if top_bar else 2)
                _t(d, (x + bw / 2.0, base - h - 10), SCORES[i], 24, INK, top_bar, anchor="mb")
                _t(d, (x + bw / 2.0, base + 12), "%d번" % i, 20, BLUE if top_bar else INK, top_bar, anchor="ma")
            if k == 2:
                x = bx0 + bars.index(best) * step
                _t(d, (x + bw / 2.0, base - SCORES[best] * scale - 44), "최댓값", 20, INK, True, anchor="mb")
                arrow(d, (x + bw + 8, base - SCORES[best] * scale + 30), (884, 380), BLUE, 4)
                _box(d, (890, 340, 1090, 420), [("preds[0] = %d" % best, BLUE, True, True)], BLUE_L, BLUE, 22, width=3)
        frames.append(image)
    return frames, [1800, 2000, 1800]


@figure("a5d-2", 560, 260)
def a5d_literal_eval():
    """같은 글을 ast.literal_eval 과 json.loads 로 읽은 결과."""
    import ast
    import json
    parsed = ast.literal_eval(LABEL_TEXT)
    assert parsed == {309: "bee", 310: "ant, emmet, pismire"} and all(type(key) is int for key in parsed)
    head = "{0: 'tench, Tinca tinca', " + LABEL_TEXT[1:]
    assert ast.literal_eval(head)[0] == "tench, Tinca tinca"
    try:
        json.loads(head)
        raise AssertionError("json.loads 가 읽었음")
    except json.JSONDecodeError as error:
        pos = error.pos
        assert pos == 1 and error.msg.startswith("Expecting property name enclosed in double quotes")
    # 0번 이름은 4단계 짐작 물음의 답이라 줄여 보임. 309·310 은 3단계 본문에 이미 있음.
    shown = "{0: '…', …, " + LABEL_TEXT[1:-1] + ", …}"
    image, d = _new(520)
    size = 26
    _t(d, (40, 18), "같은 글 text의 일부(…는 줄인 곳)", 21, MUTED, True)
    d.rounded_rectangle((40, 52, 1080, 112), 12, fill=NOTE, outline=LIGHT, width=2)
    tx = 64
    assert tx + _w(shown, size, code=True) <= 1060
    _t(d, (tx, 82), shown, size, INK, code=True, anchor="lm")
    key = shown[pos:shown.index(":")]
    assert key == "0" == head[pos:head.index(":")]
    a = tx + _w(shown[:pos], size, code=True)
    b = a + _w(key, size, code=True)
    d.line((a, 104, b, 104), fill=RED, width=4)
    lx, rx = 290, 830
    arrow(d, (lx, 116), (lx, 150), MUTED, 3)
    arrow(d, (rx, 116), (rx, 150), MUTED, 3)
    _box(d, (60, 154, 520, 206), [("ast.literal_eval(text)", INK, True, True)], "white", BLUE, 22, width=3)
    _box(d, (600, 154, 1060, 206), [("json.loads(text)", INK, True, True)], "white", RED, 22, width=3)
    arrow(d, (lx, 210), (lx, 236), MUTED, 3)
    cols = [(60, 200), (200, 520)]
    rows = [("키(int)", "값(str)")] + [(str(k), repr(v)) for k, v in sorted(parsed.items())]
    for r, cells in enumerate(rows):
        y = 240 + r * 52
        for n, ((c0, c1), cell) in enumerate(zip(cols, cells)):
            d.rectangle((c0, y, c1, y + 52), fill=NOTE if r == 0 else "white", outline=LINE, width=2)
            _t(d, ((c0 + c1) / 2.0, y + 26), cell, 20 if r == 0 else 22, MUTED if r == 0 else (BLUE if n == 0 else INK),
               r > 0 and n == 0, code=r > 0, anchor="mm")
    _t(d, (60, 420), "classes_dict[310]", 22, INK, code=True, anchor="lm")
    arrow(d, (60 + _w("classes_dict[310]", 22, code=True) + 10, 420), (60 + _w("classes_dict[310]", 22, code=True) + 46, 420),
          MUTED, 3)
    _t(d, (60 + _w("classes_dict[310]", 22, code=True) + 56, 420), repr(parsed[310]), 22, BLUE, True, code=True,
       anchor="lm")
    arrow(d, (rx, 210), (rx, 236), MUTED, 3)
    d.rounded_rectangle((600, 240, 1060, 344), 12, fill=RED_L, outline=RED, width=3)
    _t(d, (rx, 272), "JSONDecodeError", 24, RED, True, code=True, anchor="mm")
    _t(d, (rx, 314), "첫 키 0에서 멈춤", 20, RED, anchor="mm")
    _t(d, (600, 380), "0은 큰따옴표 문자열이 아닙니다", 20, INK)
    _t(d, (600, 414), "JSON은 키를 큰따옴표 문자열로만 받습니다", 19, MUTED)
    _t(d, (40, 486), "빨간 밑줄: json.loads가 멈춘 첫 키", 19, MUTED)
    return image


def _ant(d, cx, cy, color=INK):
    """사진 대신 쓰는 개미 기호. 머리·가슴·배 세 마디, 다리 여섯, 더듬이 둘."""
    for x, y in ((cx - 22, cy - 28), (cx - 8, cy - 32), (cx + 8, cy - 28)):
        d.line((cx - 8, cy, x, y), fill=color, width=4)
    for x, y in ((cx - 22, cy + 28), (cx - 8, cy + 32), (cx + 8, cy + 28)):
        d.line((cx - 8, cy, x, y), fill=color, width=4)
    d.line((cx - 44, cy - 8, cx - 60, cy - 30), fill=color, width=3)
    d.line((cx - 40, cy - 10, cx - 46, cy - 34), fill=color, width=3)
    for dx, rx, ry in ((-40, 13, 12), (-8, 15, 10), (30, 24, 16)):
        d.ellipse((cx + dx - rx, cy - ry, cx + dx + rx, cy + ry), fill=color)


@figure("a5d-3", 560, 260)
def a5d_two_lists():
    """ImageFolder classes 와 ImageNet classes_dict 의 번호."""
    folder = sorted(["bees", "ants"])
    net = {0: "tench, Tinca tinca", 309: "bee", 310: "ant, emmet, pismire"}
    label, pred = folder.index("ants"), 310
    assert folder == ["ants", "bees"] and label == 0 and net[label] != "ants" and net[pred].startswith("ant")
    image, d = _new(520)
    _t(d, (40, 18), "ImageFolder classes", 22, INK, True, code=True)
    _t(d, (700, 18), "ImageNet classes_dict", 22, INK, True, code=True)
    lrow = {0: 80, 1: 140}
    rrow = {0: 80, "a": 140, 309: 200, 310: 260, "b": 320}
    for i, y in lrow.items():
        hit = i == label
        d.rounded_rectangle((40, y, 330, y + 50), 10, fill=GREEN_L if hit else "white", outline=GREEN if hit else LIGHT,
                            width=3 if hit else 2)
        _t(d, (64, y + 25), i, 22, GREEN if hit else INK, True, anchor="lm")
        _t(d, (120, y + 25), repr(folder[i]), 22, INK, code=True, anchor="lm")
    for i, y in rrow.items():
        if isinstance(i, str):
            span = "1~308" if i == "a" else "311~999"
            _t(d, (740, y + 25), "⋮", 24, MUTED, anchor="mm")
            _t(d, (800, y + 25), span, 19, MUTED, anchor="lm")
            continue
        hit = i == pred
        wrong = i == label
        d.rounded_rectangle((700, y, 1080, y + 50), 10, fill=BLUE_L if hit else ("white" if not wrong else RED_L),
                            outline=BLUE if hit else (RED if wrong else LIGHT), width=3 if hit or wrong else 2)
        _t(d, (720, y + 25), i, 22, BLUE if hit else (RED if wrong else INK), True, anchor="lm")
        _t(d, (790, y + 25), repr(net[i]), 21, INK, code=True, anchor="lm")
    _dash_line(d, (334, 105, 694, 105), RED, 3, 9)
    _cross(d, 514, 105)
    _t(d, (514, 130), "0을 그대로 넣으면 tench", 19, RED, True, anchor="ma")
    px, py = 514, 330
    d.rounded_rectangle((px - 90, py - 50, px + 90, py + 50), 14, fill="white", outline=INK, width=3)
    _ant(d, px + 6, py - 4)
    _t(d, (px, py + 76), "같은 개미 사진", 20, INK, True, anchor="mm")
    arrow(d, (px - 94, py - 20), (334, lrow[label] + 40), GREEN, 4)
    _t(d, (300, 250), "라벨 0", 20, GREEN, True, anchor="mm")
    arrow(d, (px + 94, py - 20), (694, rrow[pred] + 25), BLUE, 4)
    _t(d, (660, 345), "예측 310", 20, BLUE, True, anchor="mm")
    _t(d, (40, 470), "초록: ImageFolder 번호 · 파랑: ImageNet 번호 · 빨강: 섞어 쓴 번호", 19, MUTED)
    return image


TRANSFORM_MEAN, TRANSFORM_STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
LECTURE_MEAN, LECTURE_STD = (0.490, 0.449, 0.411), (0.231, 0.221, 0.230)


@figure("a5d-4", 560, 240)
def a5d_transforms():
    """weights.transforms() 와 셋째 단원 검증 변환의 단계."""
    assert TRANSFORM_MEAN != LECTURE_MEAN and TRANSFORM_STD != LECTURE_STD

    def fmt(values):
        return "(%s)" % ", ".join("%.3f" % v for v in values)

    rows = [
        ("VGG13_Weights.IMAGENET1K_V1.transforms()", True,
         [["짧은 변을", "256에 맞추기"], ["가운데", "224×224 자르기"], ["0~1", "범위로"]], TRANSFORM_MEAN, TRANSFORM_STD),
        ("셋째 단원의 검증 변환", False,
         [["Resize(256)"], ["CenterCrop(224)"], ["ToTensor()"]], LECTURE_MEAN, LECTURE_STD),
    ]
    image, d = _new(480)
    widths, gap, x0 = [190, 220, 150], 36, 40
    for r, (title, code_title, steps, mean, std) in enumerate(rows):
        y = 30 + r * 210
        _t(d, (40, y), title, 21, INK, True, code=code_title)
        top, bottom = y + 40, y + 150
        x = x0
        for n, lines in enumerate(steps):
            mono = r == 1
            _box(d, (x, top, x + widths[n], bottom), [(v, INK, False, mono) for v in lines], "white", LIGHT, 20, width=2)
            arrow(d, (x + widths[n] + 4, (top + bottom) / 2.0), (x + widths[n] + gap - 4, (top + bottom) / 2.0), MUTED, 3)
            x += widths[n] + gap
        _box(d, (x, top, 1080, bottom), [("정규화" if r == 0 else "Normalize", ORANGE, True, r == 1),
                                         ("평균 " + fmt(mean), INK, False, False), ("표준편차 " + fmt(std), INK, False, False)],
             ORANGE_L, ORANGE, 20, width=5, gap=10)
        _t(d, (1076, top - 6), "다름", 19, ORANGE, True, anchor="rb")
    assert fmt(LECTURE_MEAN) == "(0.490, 0.449, 0.411)" and fmt(TRANSFORM_STD) == "(0.229, 0.224, 0.225)"
    _t(d, (40, 446), "회색 테두리: 두 변환에서 같은 단계 · 주황 굵은 테두리: 값이 다른 단계", 19, MUTED)
    return image


# a5e Inception 갈래와 계산량
# 색: 파랑 = block1, 주황 = block2, 초록 = block3, 보라 = block4. 옅은 칸 = block2·block3 의 첫 층과 첫 층 출력.

IM4 = (512, 160, 112, 224, 24, 64, 64)
IM5_IN = 512
BRANCHES = [("block1", BLUE, BLUE_L), ("block2", ORANGE, ORANGE_L), ("block3", GREEN, GREEN_L),
            ("block4", PURPLE, PURPLE_L)]


def _im4_out():
    cin, n1, r3, n3, r5, n5, pool = IM4
    outs = [n1, n3, n5, pool]
    assert outs == [160, 224, 64, 64] and sum(outs) == 512 == IM5_IN and (r3, r5) == (112, 24)
    return outs, {1: r3, 2: r5}


def _third_layers(cin=512, red=24, out=64):
    return [(1, cin, red), (3, red, out), (3, out, out)]


def _mults(layers):
    return [k * k * a * b for k, a, b in layers]


def _a5e_numbers():
    m = _mults(_third_layers())
    assert m == [12288, 13824, 36864] and sum(m) == 62976
    assert 25 * 24 * 64 == 38400 and 12288 + 38400 == 50688 and 25 * 512 * 64 == 819200
    assert round(819200 / 62976.0, 1) == 13.0 and round(819200 / 50688.0, 1) == 16.2
    return m


@figure("a5e-1", 560, 300)
def a5e_concat():
    """im4 네 갈래 출력 채널을 채널 축으로 이어 붙이기."""
    outs, reds = _im4_out()
    scale = 1.3
    lx, rx0, bx0 = 40, 200, 420
    ys = [110, 180, 250, 320]
    cy, iy, bh = 430, 506, 44
    assert bx0 + max(outs) * scale <= 1080 and rx0 + IM5_IN * scale <= 1080 and rx0 + max(reds.values()) * scale < bx0 - 30
    frames = []
    for k in range(5):
        image, d = _new(600)
        _t(d, (40, 18), "im4 = InceptionModule(512, 160, 112, 224, 24, 64, 64)", 21, INK, True, code=True)
        _t(d, (1080, 66), "높이·너비는 모두 H×W", 19, MUTED, anchor="ra")
        if k >= 1:
            _t(d, (40, 66), "옅은 막대: block2·block3의 첫 층 출력", 19, MUTED, anchor="la")
        for n, ((name, color, pale), ch, y) in enumerate(zip(BRANCHES, outs, ys)):
            _t(d, (lx, y + bh / 2.0), name, 21, color, True, anchor="lm")
            w = ch * scale
            moved = k >= 2
            if moved:
                _dash(d, (bx0, y, bx0 + w, y + bh), color, 2, 6)
            else:
                d.rectangle((bx0, y, bx0 + w, y + bh), fill=color, outline=color, width=2)
                _t(d, (bx0 + w / 2.0, y + bh / 2.0), ch, 22, "white", True, anchor="mm")
            if k >= 1 and n in reds:
                rw = reds[n] * scale
                d.rectangle((rx0, y, rx0 + rw, y + bh), fill=pale, outline=color, width=2)
                _t(d, (rx0 + rw + 8, y + bh / 2.0), "첫 층 %d" % reds[n], 19, color, True, anchor="lm") if rw < 80 else \
                    _t(d, (rx0 + rw / 2.0, y + bh / 2.0), "첫 층 %d" % reds[n], 19, color, True, anchor="mm")
                arrow(d, (bx0 - 34, y + bh / 2.0), (bx0 - 6, y + bh / 2.0), color, 3)
        if k >= 2:
            x = rx0
            for (name, color, pale), ch in zip(BRANCHES, outs):
                w = ch * scale
                d.rectangle((x, cy, x + w, cy + bh), fill=color, outline="white", width=2)
                _t(d, (x + w / 2.0, cy + bh / 2.0), ch, 22, "white", True, anchor="mm")
                x += w
            assert abs(x - (rx0 + sum(outs) * scale)) < 1e-6
            _t(d, (lx, cy + bh / 2.0), "torch.cat", 21, INK, True, code=True, anchor="lm")
            _t(d, (rx0, cy - 10), "채널 축(1번 축)으로 이어 붙임", 19, MUTED, anchor="lb")
        if k >= 3:
            end = rx0 + sum(outs) * scale
            _t(d, (end + 12, cy + bh / 2.0), "= %d" % sum(outs), 24, INK, True, anchor="lm")
            _t(d, (rx0, cy + bh + 8), "160 + 224 + 64 + 64 = %d 채널" % sum(outs), 20, INK, anchor="la")
        if k >= 4:
            w = IM5_IN * scale
            y = iy + 24
            d.rectangle((rx0, y, rx0 + w, y + bh), fill=NOTE, outline=INK, width=3)
            _t(d, (rx0 + w / 2.0, y + bh / 2.0), "im5 입력 %d" % IM5_IN, 22, INK, True, anchor="mm")
            _t(d, (lx, y + bh / 2.0), "im5", 21, INK, True, code=True, anchor="lm")
            _t(d, (rx0 + w + 12, y + bh / 2.0), "같은 길이", 20, GREEN, True, anchor="lm")
        frames.append(image)
    return frames, [2000, 2200, 2200, 2200, 2000]


@figure("a5e-2", 560, 260)
def a5e_third_table():
    """im4 block3 세 층의 위치 하나당 곱셈 수 표."""
    m = _a5e_numbers()
    layers = _third_layers()
    image, d = _new(520)
    cols = [(40, 360), (360, 760), (760, 1080)]
    heads = ["층", "식", "위치 하나당 곱셈 수"]
    for (a, b), head in zip(cols, heads):
        d.rectangle((a, 30, b, 90), fill=NOTE, outline=LINE, width=2)
        _t(d, ((a + b) / 2.0, 60), head, 21, MUTED, anchor="mm")
    for r, ((k, cin, cout), count) in enumerate(zip(layers, m)):
        y = 90 + r * 80
        name = "%d×%d 합성곱 %d→%d" % (k, k, cin, cout)
        expr = "%d × %d × %d × %d" % (k, k, cin, cout)
        fill = GREEN_L if r == 0 else "white"
        for (a, b) in cols:
            d.rectangle((a, y, b, y + 80), fill=fill, outline=LINE, width=2)
        d.rectangle((40, y, 52, y + 80), fill=GREEN)
        _t(d, (200, y + 40), name, 22, INK, True, anchor="mm")
        _t(d, (560, y + 40), expr, 22, INK, anchor="mm")
        _t(d, (1050, y + 40), "{:,}".format(count), 26, GREEN, True, anchor="rm")
    y = 90 + 3 * 80
    d.rectangle((40, y, 1080, y + 76), fill="white", outline=INK, width=3)
    _t(d, (200, y + 38), "합", 22, INK, True, anchor="mm")
    _t(d, (560, y + 38), " + ".join("{:,}".format(v) for v in m), 21, INK, anchor="mm")
    _t(d, (1050, y + 38), "{:,}".format(sum(m)), 28, INK, True, anchor="rm")
    _t(d, (40, 470), "옅은 칸: 채널을 24로 줄이는 첫 1×1 합성곱", 22, MUTED)
    return image


@figure("a5e-31", 520, 280)
def a5e_level7():
    """들어오는 값 3개와 나가는 값 2개를 모두 이은 선. 글자 없이 그림."""
    left = [(330, 130 + 150 * i) for i in range(3)]
    right = [(710, 205 + 150 * i) for i in range(2)]
    lines = [(a, b) for a in left for b in right]
    assert len(lines) == 3 * 2
    image, d = _new(560, 1040)
    for (x0, y0), (x1, y1) in lines:
        d.line((x0, y0, x1, y1), fill=MUTED, width=4)
    for x, y in left:
        d.ellipse((x - 46, y - 46, x + 46, y + 46), fill=BLUE_L, outline=BLUE, width=5)
    for x, y in right:
        d.ellipse((x - 46, y - 46, x + 46, y + 46), fill=ORANGE_L, outline=ORANGE, width=5)
    return image


@figure("a5e-32", 520, 280)
def a5e_level15():
    k, cin, cout = 3, 24, 64
    count = k * k * cin * cout
    assert count == 13824
    return levels.grid([[str(k * k), str(cin), str(cout), "{:,}".format(count)]],
                       col_names=("칸", "입력 채널", "출력 채널", "곱셈 수"), marks=[(0, 3)], color="green",
                       top="9 × 24 × 64 = 13,824")


@figure("a5e-33", 520, 280)
def a5e_level20():
    """layers 세 항목을 weight 모양으로."""
    layers = [(1, 512, 24), (3, 24, 96), (3, 96, 96)]
    shapes = [[cout, cin, k, k] for k, cin, cout in layers]
    assert shapes == [[24, 512, 1, 1], [96, 24, 3, 3], [96, 96, 3, 3]]
    assert sum(a * b * c * e for a, b, c, e in shapes) == 115968
    image, d = _new(560, 1040)
    size = 34
    _t(d, (60, 50), "(k, cin, cout)", 31, MUTED, code=True, low=LEVEL_MIN)
    _t(d, (560, 50), "weight 모양", 31, MUTED, low=LEVEL_MIN)
    _t(d, (560, 96), "[cout, cin, k, k]", 31, MUTED, code=True, low=LEVEL_MIN)
    for r, ((k, cin, cout), shape) in enumerate(zip(layers, shapes)):
        y = 210 + r * 115
        _t(d, (60, y), "(%d, %d, %d)" % (k, cin, cout), size, INK, code=True, anchor="lm", low=LEVEL_MIN)
        arrow(d, (380, y), (520, y), MUTED, 4)
        _t(d, (560, y), "[%s]" % ", ".join(str(v) for v in shape), size, GREEN, True, code=True, anchor="lm", low=LEVEL_MIN)
    return image


def _axis(d, x0, x1, base, top, vmax, ticks, label):
    d.line((x0, base, x1, base), fill=LIGHT, width=2)
    d.line((x0, top, x0, base), fill=LIGHT, width=2)
    for v in ticks:
        y = base - v * (base - top) / float(vmax)
        d.line((x0 - 6, y, x1, y), fill=COLORS["grid"], width=1)
        _t(d, (x0 - 10, y), "{:,}".format(v), 19, MUTED, anchor="rm")
    _t(d, (x0 - 4, top - 18), label, 19, MUTED, anchor="lb")
    return lambda v: v * (base - top) / float(vmax)


@figure("a5e-3", 560, 290)
def a5e_compare():
    """block3 자리의 두 구성의 층별 곱셈 수와 출력 64 채널 세 계산."""
    m = _a5e_numbers()
    configs = [("1×1·3×3·3×3", m), ("1×1·5×5", [12288, 38400])]
    totals = [sum(v) for _, v in configs] + [25 * 512 * 64]
    assert totals == [62976, 50688, 819200]
    image, d = _new(580)
    base, top = 470, 120
    h = _axis(d, 130, 500, base, top, 70000, (0, 20000, 40000, 60000), "위치 하나당 곱셈 수(bias 제외)")
    for n, (name, parts) in enumerate(configs):
        x = 190 + n * 160
        y = base
        for j, v in enumerate(parts):
            hh = h(v)
            d.rectangle((x, y - hh, x + 100, y), fill=GREEN_L if j == 0 else GREEN, outline="white", width=2)
            if hh >= 34:
                _t(d, (x + 50, y - hh / 2.0), "{:,}".format(v), 19, INK if j == 0 else "white", True, anchor="mm")
            y -= hh
        _t(d, (x + 50, y - 8), "{:,}".format(sum(parts)), 22, INK, True, anchor="mb")
        _t(d, (x + 50, base + 12), name, 19, INK, True, anchor="ma")
    _t(d, (130, base + 46), "아래 옅은 칸: 1×1 512→24", 19, MUTED)
    names = ["1×1·3×3·3×3", "1×1·5×5", "5×5 한 층"]
    g = _axis(d, 690, 1080, base, top, 900000, (0, 300000, 600000, 900000), "위치 하나당 곱셈 수(bias 제외)")
    for n, (name, v) in enumerate(zip(names, totals)):
        x = 720 + n * 120
        hh = g(v)
        last = n == 2
        d.rectangle((x, base - hh, x + 84, base), fill="white" if last else GREEN, outline=INK if last else GREEN,
                    width=3 if last else 2)
        _t(d, (x + 42, base - hh - 8), "{:,}".format(v), 20, INK, True, anchor="mb")
        _t(d, (x + 42, base + 12), name, 19, INK, True, anchor="ma")
    _t(d, (885, base + 46), "세 계산 모두 출력 64 채널", 19, MUTED, anchor="ma")
    _t(d, (40, 30), "block3 자리의 두 구성", 22, INK, True)
    _t(d, (600, 30), "출력 64 채널을 내는 세 계산", 22, INK, True)
    return image


def _pool(s):
    return (s + 2 - 3) // 2 + 1


def _avg(s):
    return s - 6


@figure("a5e-4", 560, 240)
def a5e_sizes():
    """한 변 32 와 224 가 GoogLeNet 을 지나는 길이."""
    stages = ["입력", "stem·im1~2", "max_pool", "im3~7", "max_pool", "im8~9", "average_pool"]

    def chain(s):
        out = [s, s]
        out += [_pool(out[-1])]
        out += [out[-1]]
        out += [_pool(out[-1])]
        out += [out[-1]]
        out += [_avg(out[-1])]
        return out

    rows = [chain(32), chain(224)]
    assert rows[0] == [32, 32, 16, 16, 8, 8, 2] and rows[1] == [224, 224, 112, 112, 56, 56, 50]
    flat = [1024 * r[-1] * r[-1] for r in rows]
    assert flat == [4096, 2560000]
    image, d = _new(480)
    cell, step, x0 = 100, 124, 40
    for n, name in enumerate(stages):
        _t(d, (x0 + n * step + cell / 2.0, 34), name, 19, MUTED, code=n > 0, anchor="mm")
    for r, sides in enumerate(rows):
        y = 64 + r * 200
        ok = flat[r] == 4096
        for n, side in enumerate(sides):
            x = x0 + n * step
            changed = n in (2, 4, 6)
            d.rounded_rectangle((x, y, x + cell, y + 60), 10, fill=NOTE if changed else "white",
                                outline=INK if changed else LIGHT, width=3 if changed else 2)
            _t(d, (x + cell / 2.0, y + 30), side, 26, INK, True, anchor="mm")
            if n < len(sides) - 1:
                arrow(d, (x + cell + 3, y + 30), (x + step - 3, y + 30), MUTED, 3)
        color = GREEN if ok else RED
        text = "1024 × %d × %d = %s" % (sides[-1], sides[-1], "{:,}".format(flat[r]) if flat[r] >= 10000 else flat[r])
        _t(d, (x0, y + 104), text, 22, color, True, anchor="lm")
        tail = "fc 입력 4096과 같음" if ok else "fc 입력 4096과 다름"
        tx = x0 + _w(text, 22, True) + 30
        if ok:
            d.line((tx, y + 104, tx + 10, y + 114), fill=GREEN, width=5)
            d.line((tx + 10, y + 114, tx + 26, y + 92), fill=GREEN, width=5)
        else:
            _cross(d, tx + 13, y + 104, 11)
        _t(d, (tx + 40, y + 104), tail, 21, color, True, anchor="lm")
    _t(d, (40, 446), "굵은 테두리: 한 변이 바뀌는 풀링 층", 19, MUTED)
    return image
