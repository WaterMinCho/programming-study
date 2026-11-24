# -*- coding: utf-8 -*-
"""응용 8차시 노트 al08 의 그림.

  ~/.cache/rokey-dev/lib/bin/python -m tools.ai_art al08 a8a-1   이름을 적은 그림만 그림

Pillow 로 직접 그린 칸·막대·상자·나무·꺾은선임. 강의 슬라이드 그림, 노트북에 저장된 그림, 사진(COCO, Flickr8k)은 쓰지 않음.
사진 자리는 회색 사각형으로 둠.
그림에 찍는 번호 줄, 파라미터 수, pack 차례, 스텝 수, 누적 확률, BLEU·METEOR·IDF 값은 이 파일에서 노트의 식과 코드대로
다시 계산하고 assert 로 본문 숫자와 견줌. ResNet·LSTM·pack 처럼 PyTorch 가 정하는 값은 식으로 셈.
세 수준 그림은 화면 520×280(파일 1040×560)이고 levels.grid·graph 를 쓰거나 Pillow 로 글자 31px 이상으로 그림.

a8a 색: 파랑 = 어휘에 든 낱말과 그 번호, 회색 = 특수 토큰 1·2 와 0 칸, 주황 = 기준선과 <unk> 로 바뀐 칸, 빨강 = 버린 캡션.
a8b 색: 회색 = 고정한 ResNet·떼어 낸 fc·사진 자리, 파랑 = 새로 붙여 학습하는 Linear·BatchNorm1d 와 모양, 주황 = 바뀌는 running_mean.
a8c 색: 회색 = 이미지 특징 칸과 빠진 칸, 파랑 = 캡션 번호·임베딩과 짝, 초록 = 정답 줄, 주황 = 추론이 넣는 예측, 빨강 = 틀린 출력.
a8d 색: 파랑 = 손실에 들어가는 자리와 정답 점수, 회색 점선 = 정답 0 인 자리와 저장 없는 구간.
a8e 색: 파랑 = 고른 번호·빔이 남긴 문장·soft 가중치, 빨강 = <end> 에서 멈추는 선, 주황 점선 = greedy 길, 회색 = 버린 가지와 지운 토큰.
a8f 색: 초록 = 정답에 있는 n그램, 빨강 = 없는 n그램, 파랑·주황 = 덩어리 1·2, 회색 = 짝이 없는 old, 파랑 선 = 검증 점수.
"""
import re
from math import ceil, exp, floor, log

from PIL import Image, ImageDraw

from tools.ai_art import COLORS, figure, fmt
from tools.ai_art import levels
from tools.ai_art.al04 import arrow
from tools.ai_art.al05 import _cross, _t
from tools.ai_art.al18 import _dash, _dash_line, _w

W = 1120
INK, MUTED, FAINT = COLORS["ink"], COLORS["muted"], COLORS["faint"]
BLUE, RED, ORANGE, GREEN, PURPLE = COLORS["blue"], COLORS["red"], COLORS["orange"], COLORS["green"], COLORS["purple"]
BLUE_L, GREEN_L, ORANGE_L, RED_L, PURPLE_L = "#dbeafe", "#d1fae5", "#ffedd5", "#fee2e2", "#ede9fe"
NOTE, LINE, LIGHT, PANEL = "#f3f4f6", "#e5e7eb", "#9ca3af", "#f8fafc"
BLUE_M = "#bfdbfe"
LW, LH = 1040, 560  # 세 수준 그림 파일 크기
LEVEL_MIN = 31  # 세 수준 그림 글자 하한(파일 px)


# 공통 도우미

def _new(h, w=W):
    image = Image.new("RGB", (w, h), "white")
    return image, ImageDraw.Draw(image)


def _title(d, text):
    _t(d, (36, 24), text, 25, INK, bold=True)


def _cell(d, rect, text="", fill="white", outline=LIGHT, size=22, color=INK, bold=False, code=True, width=2, radius=8,
          low=19):
    d.rounded_rectangle(rect, radius, fill=fill, outline=outline, width=width)
    if text != "":
        assert _w(text, size, bold, code) <= rect[2] - rect[0] - 6, (text, rect)
        _t(d, ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0), text, size, color, bold, code, anchor="mm", low=low)


def _dcell(d, rect, text="", color=LIGHT, size=22, ink=MUTED, code=True, fill=None, low=19):
    """점선 테두리 칸."""
    if fill:
        d.rectangle(rect, fill=fill)
    _dash(d, rect, color, 2, 7)
    if text != "":
        assert _w(text, size, False, code) <= rect[2] - rect[0] - 6, (text, rect)
        _t(d, ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0), text, size, ink, False, code, anchor="mm", low=low)


def _chip(d, xy, text, color, fill, size=19, anchor="mm", code=False, bold=True, low=19):
    """둥근 꼬리표. 차지한 상자를 돌려줌."""
    width = _w(text, size, bold, code) + 20
    x, y = xy
    x0 = {"mm": x - width / 2.0, "lm": x, "rm": x - width}[anchor]
    rect = (x0, y - size / 2.0 - 8, x0 + width, y + size / 2.0 + 8)
    d.rounded_rectangle(rect, 10, fill=fill, outline=color, width=2)
    _t(d, ((rect[0] + rect[2]) / 2.0, y), text, size, color, bold, code, anchor="mm", low=low)
    return rect


def _panel(d, rect, fill=PANEL):
    d.rounded_rectangle(rect, 12, fill=fill, outline=LINE, width=2)


def _bracket(d, x0, x1, y, color, down=True, tick=10, width=3):
    """가로 괄호. down 이면 끝이 아래로 꺾임."""
    s = tick if down else -tick
    d.line((x0, y + s, x0, y, x1, y, x1, y + s), fill=color, width=width)


def _foot(d, y, text, code=False):
    _t(d, (36, y), text, 21, INK, code=code)


def _d4(value):
    return "%.4f" % value


def _comma(n):
    return "{:,}".format(n)


def _curve(d, start, end, lift, color, width=4):
    """두 점을 잇는 위로 굽은 화살표(2차 베지어). 끝에 화살촉."""
    (x0, y0), (x1, y1) = start, end
    cx, cy = (x0 + x1) / 2.0, min(y0, y1) - lift
    points = []
    for k in range(41):
        t = k / 40.0
        points.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1))
    d.line(points, fill=color, width=width, joint="curve")
    arrow(d, points[-4], points[-1], color, width)


# a8a 캡션을 번호 줄로 바꾸고 짧은 캡션 채우기

FREQ = [("a", 9), ("dog", 5), ("runs", 4), ("cat", 4), ("bird", 3)]
SPECIAL = ["<pad>", "<start>", "<end>", "<unk>"]


def _vocab(threshold=4):
    words = SPECIAL + [w for w, n in FREQ if n >= threshold]
    return {w: i for i, w in enumerate(words)}


def _encode(caption, w2i):
    return [w2i["<start>"]] + [w2i.get(w, w2i["<unk>"]) for w in caption.split()] + [w2i["<end>"]]


def _to_ids(words, max_len, w2i):
    """두 번째 코드의 to_ids: 시작 토큰, 낱말, 길이 max_len − 1 에서 멈춤, 끝 토큰, 0 채움."""
    ids = [1]
    for w in words:
        ids.append(w2i.get(w, 3))
        if len(ids) >= max_len - 1:
            break
    ids.append(2)
    return ids + [0] * (max_len - len(ids))


def _collate(caps):
    """첫 번째 코드의 collate_fn: 길이순으로 정렬하고 가장 긴 길이의 0 행렬에 복사."""
    caps = sorted(caps, key=len, reverse=True)
    lens = [len(c) for c in caps]
    tgts = [[0] * max(lens) for _ in caps]
    for i, c in enumerate(caps):
        tgts[i][:lens[i]] = c
    return tgts, lens


def _clean(sentence):
    sentence = sentence.lower()
    sentence = re.sub(r"[^a-z ]", "", sentence)
    return re.sub(r"\s+", " ", sentence).strip()


def _a8a1_frame(k):
    w2i = _vocab()
    assert w2i == {"<pad>": 0, "<start>": 1, "<end>": 2, "<unk>": 3, "a": 4, "dog": 5, "runs": 6, "cat": 7}
    rows = [("a dog runs", _encode("a dog runs", w2i)), ("a bird runs", _encode("a bird runs", w2i))]
    assert rows[0][1] == [1, 4, 5, 6, 2] and rows[1][1] == [1, 4, 3, 6, 2]
    image, d = _new(600)
    _title(d, "빈도로 어휘를 고르고 캡션을 번호 줄로 바꿉니다")
    _panel(d, (36, 76, 540, 384))
    _t(d, (56, 92), "학습 캡션에서 나온 횟수", 20, MUTED)
    base, unit = 340, 24
    line_y = base - 4 * unit
    for n, (word, count) in enumerate(FREQ):
        cx = 95 + n * 80
        kept = count >= 4
        top = base - count * unit
        d.rounded_rectangle((cx - 28, top, cx + 28, base), 4, fill=BLUE if kept else LIGHT)
        _t(d, (cx, base - 20), str(count), 20, "white", True, anchor="mm")  # 기준선과 겹치지 않게 막대 아래쪽에 적음
        _t(d, (cx, base + 10), word, 20, INK if kept else MUTED, False, True, anchor="ma")
    d.line((56, base, 455, base), fill=LIGHT, width=2)
    _dash_line(d, (56, line_y, 455, line_y), ORANGE, 3, 9)
    _chip(d, (497, line_y), "기준 4", ORANGE, ORANGE_L, 19)
    _panel(d, (570, 76, 1084, 384))
    if k >= 1:
        _t(d, (590, 92), "특수 토큰", 20, MUTED)
        _t(d, (840, 92), "4번 이상 나온 낱말", 20, BLUE)
        for word, number in w2i.items():
            col, row = (0, number) if number < 4 else (1, number - 4)
            x0, y0 = 590 + col * 250, 130 + row * 60
            special = number < 4
            d.rounded_rectangle((x0, y0, x0 + 230, y0 + 48), 8, fill="white", outline=LIGHT if special else BLUE, width=2)
            _t(d, (x0 + 30, y0 + 24), str(number), 22, MUTED if special else BLUE, True, True, anchor="mm")
            _t(d, (x0 + 62, y0 + 24), word, 22, INK, False, True, anchor="lm")
    else:
        _t(d, (827, 230), "어휘 표", 22, LIGHT, anchor="mm")
    _panel(d, (36, 404, 1084, 584))
    for r, (caption, ids) in enumerate(rows):
        if k < 2 + r:
            continue
        y = 424 + r * 82
        _t(d, (56, y + 25), caption, 22, INK, True, True, anchor="lm")
        arrow(d, (250, y + 25), (310, y + 25), MUTED, 4)
        for c, number in enumerate(ids):
            x0 = 330 + c * 70
            unk = number == 3
            special = number in (1, 2)
            fill = ORANGE_L if unk else (NOTE if special else "white")
            _cell(d, (x0, y, x0 + 60, y + 50), str(number), fill, ORANGE if unk else (LIGHT if special else BLUE), 24,
                  ORANGE if unk else (MUTED if special else BLUE), True, width=3 if unk else 2)
        if r == 1:
            _chip(d, (720, y + 25), "bird → <unk> 번호 3", ORANGE, ORANGE_L, 20, anchor="lm", code=True)
    return image


@figure("a8a-1", 560, 300)
def a8a_vocab():
    """빈도 막대와 기준선 → 어휘 표 → 캡션 두 개의 번호 줄(4장)."""
    return [_a8a1_frame(k) for k in range(4)], [2200, 2200, 2400, 2400]


@figure("a8a-2", 560, 200)
def a8a_pad_cut():
    """max_len 10 에서 0 채우기와 낱말 자르기."""
    w2i = _vocab()
    short = _to_ids("a dog runs".split(), 10, w2i)
    long_words = ["a"] * 18
    long_ids = _to_ids(long_words, 10, w2i)
    kept = sum(1 for i in long_ids if i not in (0, 1, 2))
    assert short == [1, 4, 5, 6, 2, 0, 0, 0, 0, 0] and len(long_ids) == 10 and kept == 8 and 18 - kept == 10
    image, d = _new(400)
    _title(d, "max_len 10에 맞춰 0으로 채우고 낱말을 자릅니다")
    _chip(d, (36, 90), "max_len = 10", BLUE, BLUE_L, 20, anchor="lm", code=True)
    y = 132
    _t(d, (36, y + 26), "낱말 3개", 21, INK, True, anchor="lm")
    for c, number in enumerate(short):
        x0 = 190 + c * 60
        zero = number == 0
        _cell(d, (x0, y, x0 + 52, y + 52), str(number), NOTE if zero else "white", LIGHT if zero else BLUE, 22,
              MUTED if zero else BLUE, not zero)
    _bracket(d, 190 + 5 * 60, 190 + 10 * 60 - 8, y + 62, MUTED, down=False)
    _t(d, (190 + 7.5 * 60 - 4, y + 70), "0 다섯 칸", 19, MUTED, anchor="ma")
    y = 248
    _t(d, (36, y + 26), "낱말 18개", 21, INK, True, anchor="lm")
    for c in range(10):
        x0 = 190 + c * 60
        if c in (0, 9):
            _cell(d, (x0, y, x0 + 52, y + 52), "1" if c == 0 else "2", "white", BLUE, 22, BLUE, True)
        else:
            d.rounded_rectangle((x0, y, x0 + 52, y + 52), 8, fill=BLUE_L, outline=BLUE_M, width=2)
            d.ellipse((x0 + 20, y + 20, x0 + 32, y + 32), fill=BLUE)
    _bracket(d, 250, 190 + 9 * 60 - 8, y + 62, BLUE, down=False)
    _t(d, (216 + 4.5 * 60, y + 70), "남은 낱말 8개", 19, BLUE, True, anchor="ma")
    _dash_line(d, (800, y - 10, 800, y + 62), LIGHT, 3, 7)
    for c in range(10):
        x0 = 816 + c * 27
        _dash(d, (x0, y + 12, x0 + 22, y + 44), LIGHT, 2, 5)
    _t(d, (816 + 5 * 27 - 3, y + 70), "버린 낱말 10개", 19, MUTED, anchor="ma")
    return image


@figure("a8a-3", 560, 190)
def a8a_collate():
    """들어온 차례 → 길이순 정렬 → 2행 5열 0 행렬에 복사."""
    batch = [[1, 4, 7, 2], [1, 4, 5, 6, 2]]
    tgts, lens = _collate(batch)
    assert tgts == [[1, 4, 5, 6, 2], [1, 4, 7, 2, 0]] and lens == [5, 4]
    image, d = _new(380)
    _title(d, "배치에서 가장 긴 길이 5로 0을 채웁니다")
    panels = [((36, 90, 306, 330), "들어온 차례", batch), ((420, 90, 690, 330), "길이순으로 정렬", sorted(batch, key=len, reverse=True)),
              ((804, 90, 1084, 330), "2행 5열 텐서", tgts)]
    for n, (rect, head, rows) in enumerate(panels):
        _panel(d, rect)
        _t(d, (rect[0] + 18, rect[1] + 16), head, 20, INK, True)
        for r, row in enumerate(rows):
            for c, number in enumerate(row):
                x0, y0 = rect[0] + 16 + c * 50, rect[1] + 64 + r * 64
                pad = n == 2 and r == 1 and c == 4
                _cell(d, (x0, y0, x0 + 42, y0 + 50), str(number), NOTE if pad else "white", LIGHT if pad else BLUE, 22,
                      MUTED if pad else BLUE, False)
    for x0, lines in ((306, ("길이순", "정렬")), (690, ("0 행렬에", "복사"))):
        for k, text in enumerate(lines):
            _t(d, (x0 + 57, 160 + k * 24), text, 19, MUTED, anchor="mb")
        arrow(d, (x0 + 14, 202), (x0 + 100, 202), BLUE, 4)
    _chip(d, (944, 296), "길이 목록 [5, 4]", INK, "white", 20, code=True, bold=False)
    return image


@figure("a8a-4", 560, 180)
def a8a_clean():
    """캡션 세 줄의 정리 결과 표."""
    rows = []
    for raw in ("A dog runs on the grass.", "A black-and-white dog.", "Two dogs."):
        cleaned = _clean(raw)
        rows.append((raw, cleaned, len(cleaned.split())))
    assert [r[1:] for r in rows] == [("a dog runs on the grass", 6), ("a blackandwhite dog", 3), ("two dogs", 2)]
    image, d = _new(360)
    _title(d, "정리 규칙을 지난 캡션 세 줄")
    cols = [36, 366, 696, 846, 1084]
    d.rounded_rectangle((36, 80, 1084, 320), 10, fill="white", outline=LINE, width=2)
    d.rectangle((38, 82, 1082, 130), fill=PANEL)
    for c, head in enumerate(("원래 캡션", "정리한 캡션", "낱말 수", "결과")):
        _t(d, (cols[c] + 20 if c < 2 else (cols[c] + cols[c + 1]) / 2.0, 106), head, 20, MUTED, True,
           anchor="lm" if c < 2 else "mm")
    for r, (raw, cleaned, count) in enumerate(rows):
        y = 130 + r * 63
        d.line((38, y, 1082, y), fill=LINE, width=2)
        drop = count < 3
        cy = y + 32
        _t(d, (cols[0] + 20, cy), raw, 21, MUTED if drop else INK, False, True, anchor="lm")
        _t(d, (cols[1] + 20, cy), cleaned, 21, MUTED if drop else BLUE, not drop, True, anchor="lm")
        _t(d, ((cols[2] + cols[3]) / 2.0, cy), str(count), 22, RED if drop else INK, True, True, anchor="mm")
        _chip(d, ((cols[3] + cols[4]) / 2.0, cy), "버림" if drop else "남김", RED if drop else GREEN,
              RED_L if drop else GREEN_L, 20)
    return image


@figure("a8a-31", 520, 280)
def a8a_level7():
    """칸 열 개 줄: 시작, 낱말 셋, 끝, 나누지 않은 점선 띠. 0 개수는 적지 않음."""
    image, d = _new(LH, LW)
    left, cell, gap = 40, 96, 0
    _bracket(d, left, left + 10 * cell, 190, MUTED, down=True, tick=16, width=4)
    _t(d, (left + 5 * cell, 170), "칸 10", 34, INK, True, anchor="mb", low=LEVEL_MIN)
    y0, y1 = 240, 350
    for c, text in enumerate(("시작", "낱말", "낱말", "낱말", "끝")):
        x0 = left + c * cell + 4
        word = text == "낱말"
        _cell(d, (x0, y0, x0 + cell - 8, y1), text, BLUE if word else NOTE, BLUE if word else LIGHT, 34,
              "white" if word else INK, True, False, low=LEVEL_MIN)
    _dash(d, (left + 5 * cell + 4, y0, left + 10 * cell - 4, y1), LIGHT, 3, 10)
    return image


@figure("a8a-32", 520, 280)
def a8a_level15():
    zeros = {n: 10 - (n + 2) for n in (1, 6, 4)}
    assert zeros == {1: 7, 6: 2, 4: 4}
    return levels.grid([["1", str(zeros[1])], ["6", str(zeros[6])], ["4", ""]], col_names=("낱말 수", "0의 개수"),
                       marks=[(2, 1)], color="orange")


@figure("a8a-33", 520, 280)
def a8a_level20():
    """max_len 12 길이 눈금 띠: 1 시작 토큰, 11 위 멈춤, 12 끝 토큰, 나머지는 칠하지 않은 점선 칸."""
    w2i = _vocab()
    ids = _to_ids(["a"] * 15, 12, w2i)
    assert ids.index(2) == 11 and ids[0] == 1  # 11 칸에서 멈추고 12 칸에 끝 토큰
    image, d = _new(LH, LW)
    left, cell = 24, (LW - 48) / 12.0
    y0, y1 = 260, 400
    for n in range(1, 13):
        x0 = left + (n - 1) * cell + 3
        x1 = x0 + cell - 6
        _t(d, ((x0 + x1) / 2.0, y0 - 14), str(n), LEVEL_MIN, MUTED, False, True, anchor="mb", low=LEVEL_MIN)
        if n in (1, 12):
            d.rounded_rectangle((x0, y0, x1, y1), 8, fill=NOTE, outline=LIGHT, width=2)
            for k, part in enumerate(("시작" if n == 1 else "끝", "토큰")):
                _t(d, ((x0 + x1) / 2.0, (y0 + y1) / 2.0 + (k - 0.5) * 42), part, LEVEL_MIN, INK, True, anchor="mm",
                   low=LEVEL_MIN)
        else:
            _dash(d, (x0, y0, x1, y1), LIGHT, 2, 8)
        if n == 11:
            d.line(((x0 + x1) / 2.0, y0 - 56, (x0 + x1) / 2.0, y0 - 76), fill=RED, width=4)
            _t(d, ((x0 + x1) / 2.0, y0 - 82), "멈춤", LEVEL_MIN, RED, True, anchor="mb", low=LEVEL_MIN)
    return image


# a8b 사전학습 ResNet 이 사진 한 장을 256개 숫자로 바꾸기

def _conv_out(n, k, s, p):
    return floor((n + 2 * p - k) / s) + 1


def _resnet_side(n=224):
    """ResNet 의 공간 한 변: conv1(7, 2, 3) → maxpool(3, 2, 1) → layer2·3·4 에서 반씩 → 평균 풀링 1."""
    n = _conv_out(_conv_out(n, 7, 2, 3), 3, 2, 1)
    for _ in range(3):
        n = _conv_out(n, 3, 2, 1)
    return n


def _a8b_numbers():
    side = _resnet_side()
    channels = 512 * 4  # Bottleneck 의 expansion 4
    linear = 2048 * 256 + 256
    bn = 256 * 2
    assert side == 7 and channels == 2048 and linear == 524544 and bn == 512
    return channels, linear, bn


def _photo(d, rect, text=""):
    d.rounded_rectangle(rect, 8, fill=NOTE, outline=LIGHT, width=2)
    if text:
        _t(d, ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0), text, 19, MUTED, anchor="mm")


def _a8b1_frame(k):
    channels, _, _ = _a8b_numbers()
    shapes = ["(2, 3, 224, 224)", "(2, %d, 1, 1)" % channels, "(2, %d)" % channels, "(2, 256)"]
    image, d = _new(600)
    _title(d, "fc를 뗀 ResNet-152가 사진 한 장을 숫자 2048개로 바꿉니다")
    _photo(d, (66, 100, 186, 220))
    _photo(d, (46, 120, 166, 240), "사진")
    _t(d, (116, 262), "사진 2장", 20, INK, True, anchor="ma")
    _t(d, (116, 292), shapes[0], 19, BLUE, False, True, anchor="ma")
    arrow(d, (196, 180), (252, 180), MUTED, 4)
    d.rounded_rectangle((260, 90, 790, 290), 12, fill=NOTE, outline=LIGHT, width=2)
    _t(d, (280, 106), "ResNet-152 (가중치 고정)", 21, INK, True)
    for n, name in enumerate(("conv1", "layer1", "layer2", "layer3", "layer4")):
        x0 = 280 + n * 76
        _cell(d, (x0, 156, x0 + 70, 206), name, "white", LIGHT, 19, MUTED, False)
    arrow(d, (656, 181), (674, 181), MUTED, 3)
    _cell(d, (680, 150, 776, 212), "평균 풀링", "white", BLUE if k == 1 else LIGHT, 19, INK, True, False,
          width=3 if k == 1 else 2)
    _t(d, (280, 240), "합성곱 층을 지나 평균 풀링까지 씁니다", 19, MUTED)
    _dcell(d, (820, 140, 930, 240), "", LIGHT)
    _t(d, (875, 172), "fc", 22, MUTED, True, True, anchor="mm")
    _t(d, (875, 210), "떼어 냄", 19, MUTED, anchor="mm")
    if k >= 1:
        d.line((728, 292, 728, 326, 145, 326), fill=BLUE, width=4)
        arrow(d, (145, 326), (145, 392), BLUE, 4)
        _chip(d, (145, 420), shapes[1], BLUE, BLUE_L if k == 1 else "white", 20, code=True)
    if k >= 2:
        arrow(d, (236, 420), (276, 420), MUTED, 4)
        _cell(d, (282, 395, 382, 445), "펴기", "white", BLUE if k == 2 else LIGHT, 20, INK, True, False,
              width=3 if k == 2 else 2)
        arrow(d, (388, 420), (428, 420), MUTED, 4)
        _chip(d, (434, 420), shapes[2], BLUE, BLUE_L if k == 2 else "white", 20, anchor="lm", code=True)
    if k >= 3:
        _chip(d, (747, 370), "다음 단계에서 붙일 층", MUTED, "white", 19, bold=False)
        arrow(d, (556, 420), (590, 420), MUTED, 4)
        _cell(d, (596, 395, 706, 445), "Linear", BLUE_L, BLUE, 20, BLUE, True, False)
        arrow(d, (712, 420), (742, 420), MUTED, 4)
        _cell(d, (748, 395, 898, 445), "BatchNorm1d", BLUE_L, BLUE, 20, BLUE, True, False)
        arrow(d, (904, 420), (934, 420), MUTED, 4)
        _chip(d, (940, 420), shapes[3], BLUE, BLUE_L, 20, anchor="lm", code=True)
    lines = ["입력 (2, 3, 224, 224) 사진 두 장이 fc를 뗀 ResNet-152로 들어갑니다.",
             "평균 풀링을 지난 출력은 (2, 2048, 1, 1)입니다.", "reshape로 펴면 (2, 2048)입니다.",
             "다음 단계에서 붙일 Linear와 BatchNorm1d를 지나면 (2, 256)입니다."]
    _foot(d, 530, lines[k])
    return image


@figure("a8b-1", 560, 300)
def a8b_encoder():
    """사진 두 장 → fc 를 뗀 ResNet-152 → 평균 풀링 → 펴기 → Linear → BatchNorm1d(4장)."""
    return [_a8b1_frame(k) for k in range(4)], [2200, 2200, 2200, 2400]


@figure("a8b-2", 560, 200)
def a8b_params():
    """2048 띠 → Linear → 256 띠 → BatchNorm1d → 256 띠와 파라미터 수."""
    _, linear, bn = _a8b_numbers()
    image, d = _new(400)
    _title(d, "숫자 2048개를 256개로 맞추는 두 층")
    long_w = 400
    short_w = long_w * 256 // 2048
    assert short_w * 2048 == long_w * 256
    y0, y1, cy = 196, 252, 224
    _cell(d, (36, y0, 36 + long_w, y1), "2048개", BLUE_L, BLUE_M, 22, BLUE, True, False)
    arrow(d, (446, cy), (736, cy), BLUE, 4)
    _t(d, (591, cy - 14), "Linear(2048, 256)", 20, INK, True, True, anchor="mb")
    _t(d, (591, cy + 14), "2048 × 256 + 256 = %s" % _comma(linear), 20, BLUE, False, True, anchor="mt")
    d.rounded_rectangle((746, y0, 746 + short_w, y1), 8, fill=BLUE_L, outline=BLUE_M, width=2)
    _t(d, (746 + short_w / 2.0, y1 + 12), "256개", 20, BLUE, True, anchor="ma")
    arrow(d, (806, cy), (1024, cy), BLUE, 4)
    _t(d, (915, cy - 14), "BatchNorm1d(256)", 20, INK, True, True, anchor="mb")
    _t(d, (915, cy + 14), "256 × 2 = %d" % bn, 20, BLUE, False, True, anchor="mt")
    d.rounded_rectangle((1034, y0, 1034 + short_w, y1), 8, fill=BLUE, outline=BLUE, width=2)
    _t(d, (1034 + short_w / 2.0, y1 + 12), "256개", 20, BLUE, True, anchor="ma")
    _t(d, (36, 330), "BatchNorm1d(256)은 특징 256개마다 곱하는 값과 더하는 값을 하나씩 학습합니다.", 19, MUTED)
    return image


@figure("a8b-3", 560, 210)
def a8b_frozen():
    """갱신하는 층과 고정한 층, 두 모드에서 running_mean 이 바뀌는지."""
    image, d = _new(420)
    _title(d, "ResNet 가중치는 그대로여도 running_mean은 바뀝니다")
    boxes = [((120, 114, 320, 174), "ResNet", "고정", False), ((460, 114, 640, 174), "Linear", "학습", True),
             ((700, 114, 900, 174), "BatchNorm1d", "학습", True)]
    for rect, name, tag, train in boxes:
        _cell(d, rect, name, BLUE_L if train else NOTE, BLUE if train else LIGHT, 22, BLUE if train else MUTED, True, False)
        _chip(d, ((rect[0] + rect[2]) / 2.0, 90), tag, BLUE if train else MUTED, "white", 19)
    arrow(d, (330, 144), (450, 144), MUTED, 4)
    arrow(d, (646, 144), (694, 144), MUTED, 4)
    cols = [36, 400, 742, 1084]
    d.rounded_rectangle((36, 214, 1084, 394), 10, fill="white", outline=LINE, width=2)
    d.rectangle((38, 216, 1082, 266), fill=PANEL)
    for c, head in enumerate(("실행 모드", "ResNet 가중치", "ResNet 안 running_mean")):
        _t(d, (cols[c] + 20, 241), head, 20, MUTED, True, anchor="lm")
    rows = [("학습 모드 + no_grad", "안 바뀜", "바뀜"), ("평가 모드", "안 바뀜", "안 바뀜")]
    for r, row in enumerate(rows):
        y = 266 + r * 64
        d.line((38, y, 1082, y), fill=LINE, width=2)
        for c, text in enumerate(row):
            if text == "바뀜":
                _chip(d, (cols[c] + 20, y + 32), text, ORANGE, ORANGE_L, 21, anchor="lm")
            else:
                _t(d, (cols[c] + 20, y + 32), text, 21, INK, c == 0, anchor="lm")
    for x in cols[1:3]:
        d.line((x, 216, x, 392), fill=LINE, width=2)
    return image


@figure("a8b-4", 560, 260)
def a8b_transform():
    """학습 변환(256 → 무작위 224 자르기 → 좌우 뒤집기 → 정규화)과 추론 변환(224 로 줄이기 → 정규화)."""
    mean, std = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
    big = 180
    small = big * 224 / 256.0
    assert abs(small - 157.5) < 1e-9
    image, d = _new(520)
    _title(d, "학습 사진은 무작위로 자르고 뒤집습니다")
    for row, (name, y) in enumerate((("학습", 80), ("추론", 310))):
        _chip(d, (70, y + big / 2.0), name, BLUE if row == 0 else INK, BLUE_L if row == 0 else NOTE, 21)
        d.rectangle((150, y, 150 + big, y + big), fill=NOTE, outline=LIGHT, width=2)
        if row == 0:
            ox, oy = 150 + 9, y + 15
            d.rectangle((ox, oy, ox + small, oy + small), fill=BLUE_L)
            _dash(d, (ox, oy, ox + small, oy + small), BLUE, 3, 8)
            _t(d, (ox + small / 2.0, oy + small / 2.0), "224×224", 21, BLUE, True, anchor="mm")
            _t(d, (150 + big / 2.0, y + big + 8), "256×256", 19, MUTED, anchor="ma")
            _t(d, (430, y + big / 2.0 - 12), "좌우 뒤집기", 20, INK, anchor="mb")
            _t(d, (430, y + big / 2.0 + 12), "절반의 확률", 19, MUTED, anchor="mt")
        else:
            _t(d, (150 + big / 2.0, y + big / 2.0), "사진", 21, MUTED, anchor="mm")
            _t(d, (430, y + big / 2.0 - 12), "224×224로 줄이기", 20, INK, anchor="mb")
        arrow(d, (340, y + big / 2.0), (520, y + big / 2.0), MUTED, 4)
        _cell(d, (530, y + big / 2.0 - 30, 670, y + big / 2.0 + 30), "정규화", BLUE_L, BLUE, 22, BLUE, True, False)
    d.rounded_rectangle((720, 240, 1084, 340), 10, fill=PANEL, outline=BLUE, width=2)
    _t(d, (740, 272), "평균 (%s)" % ", ".join("%.3f" % v for v in mean), 19, INK, True, True, anchor="lm")
    _t(d, (740, 310), "표준편차 (%s)" % ", ".join("%.3f" % v for v in std), 19, BLUE, True, True, anchor="lm")
    d.line((670, 170, 720, 270), fill=LIGHT, width=2)
    d.line((670, 400, 720, 310), fill=LIGHT, width=2)
    return image


# a8c 이미지 특징을 첫 입력으로 넣고 한 칸 밀린 정답 맞추기

W_ROWS = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]


def _onehot_times(index, rows):
    hot = [1 if r == index else 0 for r in range(len(rows))]
    return hot, [sum(hot[r] * rows[r][c] for r in range(len(rows))) for c in range(len(rows[0]))]


def _pairs(ids):
    """자리마다 (입력, 정답). 입력은 이미지 특징과 번호 줄 앞쪽, 정답은 번호 줄 전체."""
    inputs = ["이미지"] + ids[:-1]
    return list(zip(inputs, ids))


def _pack(rows, lens):
    """batch_first 로 길이순 정렬된 줄을 자리 차례로 이음. (이은 값, batch_sizes)."""
    data, sizes = [], []
    for t in range(max(lens)):
        alive = [b for b in range(len(rows)) if lens[b] > t]
        data += [rows[b][t] for b in alive]
        sizes.append(len(alive))
    return data, sizes


@figure("a8c-1", 560, 280)
def a8c_embedding():
    """원-핫 × W 가 W 의 2번 행과 같음, (2, 1, 256) 과 (2, 5, 256) 을 이어 (2, 6, 256)."""
    hot, out = _onehot_times(2, W_ROWS)
    assert hot == [0, 0, 1, 0] and out == W_ROWS[2] == [6, 7, 8]
    feat, emb = (2, 1, 256), (2, 5, 256)
    cat = (feat[0], feat[1] + emb[1], feat[2])
    assert cat == (2, 6, 256)
    image, d = _new(560)
    _title(d, "번호로 행을 꺼내고 이미지 특징을 앞에 붙입니다")
    cy = 237
    _t(d, (36, cy - 36), "번호 2의 원-핫 벡터", 19, MUTED, anchor="lb")
    for c, v in enumerate(hot):
        x0 = 36 + c * 60
        _cell(d, (x0, cy - 26, x0 + 52, cy + 26), str(v), BLUE_L if v else "white", BLUE if v else LIGHT, 22,
              BLUE if v else MUTED, bool(v), width=3 if v else 2)
    _t(d, (306, cy), "×", 30, MUTED, anchor="mm")
    _t(d, (472, 84), "W (4행 3열)", 20, INK, True, anchor="mm")
    for r, row in enumerate(W_ROWS):
        y0 = 110 + r * 52
        mark = r == 2
        _t(d, (370, y0 + 23), "%d번" % r, 19, BLUE if mark else MUTED, mark, anchor="rm")
        for c, v in enumerate(row):
            x0 = 380 + c * 64
            _cell(d, (x0, y0, x0 + 56, y0 + 46), str(v), BLUE_L if mark else "white", BLUE if mark else LIGHT, 22,
                  BLUE if mark else INK, mark, width=3 if mark else 2)
    _t(d, (600, cy), "=", 30, MUTED, anchor="mm")
    _t(d, (630, cy - 36), "W의 2번 행과 같음", 19, BLUE, anchor="lb")
    for c, v in enumerate(out):
        x0 = 630 + c * 64
        _cell(d, (x0, cy - 26, x0 + 56, cy + 26), str(v), BLUE_L, BLUE, 22, BLUE, True, width=3)
    d.line((36, 330, 1084, 330), fill=LINE, width=2)
    _t(d, (116, 360), "(2, 1, 256)", 19, MUTED, False, True, anchor="ma")
    _t(d, (204 + 5 * 70 / 2.0, 360), "(2, 5, 256)", 19, BLUE, False, True, anchor="ma")
    for r in range(2):
        y0 = 394 + r * 60
        _cell(d, (36, y0, 196, y0 + 50), "이미지 특징", NOTE, LIGHT, 19, MUTED, False, False)
        for c in range(5):
            x0 = 204 + c * 70
            d.rounded_rectangle((x0, y0, x0 + 64, y0 + 50), 8, fill=BLUE_L, outline=BLUE_M, width=2)
    _t(d, (370, 536), "캡션 임베딩 다섯 자리", 19, BLUE, anchor="ms")
    arrow(d, (580, 449), (660, 449), BLUE, 5)
    _t(d, (680, 449), "(2, 6, 256)", 28, BLUE, True, True, anchor="lm")
    return image


def _a8c2_frame(k):
    ids = [1, 4, 5, 6, 2]
    pairs = _pairs(ids)
    assert pairs == [("이미지", 1), (1, 4), (4, 5), (5, 6), (6, 2)]
    image, d = _new(560)
    _title(d, "정답 줄은 입력 줄보다 한 칸 앞섭니다")
    _t(d, (36, 220), "입력", 22, INK, True, anchor="lm")
    _t(d, (36, 380), "정답", 22, GREEN, True, anchor="lm")
    _t(d, (36, 120), "자리", 20, MUTED, anchor="lm")
    linked = {0: 0, 1: 1, 2: 2, 3: 5}[k]
    for p, (x, y) in enumerate(pairs):
        cx = 250 + p * 150
        _t(d, (cx, 120), str(p), 22, MUTED, True, True, anchor="mm")
        if p < linked:
            d.rounded_rectangle((cx - 70, 172, cx + 70, 428), 14, fill=PANEL, outline=BLUE, width=3)
            d.line((cx, 252, cx, 348), fill=BLUE, width=4)
        image_cell = x == "이미지"
        _cell(d, (cx - 60, 190, cx + 60, 250), "이미지 특징" if image_cell else str(x), NOTE if image_cell else "white",
              LIGHT if image_cell else BLUE, 19 if image_cell else 26, MUTED if image_cell else BLUE, not image_cell,
              not image_cell)
        _cell(d, (cx - 60, 350, cx + 60, 410), str(y), GREEN_L, GREEN, 26, GREEN, True)
    if k == 2:
        arrow(d, (310, 350), (342, 250), ORANGE, 5)
    if k == 3:
        _dcell(d, (940, 190, 1060, 250), "2", LIGHT, 26, LIGHT)
        _t(d, (1000, 262), "입력에 없음", 19, MUTED, anchor="ma")
    lines = ["입력 줄은 이미지 특징과 1, 4, 5, 6이고 정답 줄은 1, 4, 5, 6, 2입니다.", "0번 자리는 이미지 특징을 받아 정답 1을 맞힙니다.",
             "1번 자리의 입력 1은 0번 자리의 정답 1입니다.", "다섯 짝이 모두 이어지고, 번호 줄 끝의 2는 입력 줄에 들어가지 않습니다."]
    _foot(d, 500, lines[k])
    return image


@figure("a8c-2", 560, 280)
def a8c_shift():
    """자리 0~4 의 입력과 정답 짝짓기(4장)."""
    return [_a8c2_frame(k) for k in range(4)], [2200, 2200, 2400, 2400]


@figure("a8c-3", 560, 260)
def a8c_pack():
    """lens [5, 4] 로 pack 한 입력·정답과 batch_sizes."""
    caps = [[1, 4, 5, 6, 2], [1, 4, 7, 2, 0]]
    lens = [5, 4]
    x_rows = [["이미지"] + c for c in caps]
    inputs, sizes = _pack(x_rows, lens)
    answers, sizes2 = _pack(caps, lens)
    assert inputs == ["이미지", "이미지", 1, 1, 4, 4, 5, 7, 6] and sizes == sizes2 == [2, 2, 2, 2, 1]
    assert answers == [1, 1, 4, 4, 5, 7, 6, 2, 2]
    image, d = _new(520)
    _title(d, "pack은 자리 차례로 9개를 이어 붙입니다")
    _t(d, (36, 154), "lens [5, 4]", 22, BLUE, True, True, anchor="lm")
    for c in range(6):
        cx = 230 + c * 140 + 64
        _t(d, (cx, 98), str(c), 20, MUTED, False, True, anchor="mm")
    for r, row in enumerate(x_rows):
        for c, v in enumerate(row):
            x0, y0 = 230 + c * 140, 114 + r * 58
            rect = (x0, y0, x0 + 128, y0 + 50)
            if c >= lens[r]:
                _dcell(d, rect, str(v), LIGHT, 22, LIGHT, fill=NOTE)
            else:
                pic = v == "이미지"
                _cell(d, rect, str(v), BLUE_L if pic else "white", BLUE_M if pic else LIGHT, 19 if pic else 22,
                      BLUE if pic else INK, pic, not pic)
    arrow(d, (560, 236), (560, 276), BLUE, 4)
    _t(d, (576, 256), "pack_padded_sequence", 19, MUTED, False, True, anchor="lm")
    _t(d, (36, 318), "batch_sizes", 20, INK, True, True, anchor="lm")
    _t(d, (36, 370), "입력 9칸", 20, INK, True, anchor="lm")
    _t(d, (36, 430), "정답 9칸", 20, GREEN, True, anchor="lm")
    x, n = 230, 0
    for t, size in enumerate(sizes):
        width = size * 80 + (size - 1) * 8
        _chip(d, (x + width / 2.0, 318), str(size), BLUE, BLUE_L, 20, code=True)
        for j in range(size):
            x0 = x + j * 88
            v, a = inputs[n], answers[n]
            pic = v == "이미지"
            _cell(d, (x0, 346, x0 + 80, 394), str(v), BLUE_L if pic else "white", BLUE if pic else LIGHT, 19 if pic else 22,
                  BLUE if pic else INK, pic, not pic)
            _cell(d, (x0, 406, x0 + 80, 454), str(a), GREEN_L, GREEN, 22, GREEN, True)
            n += 1
        _t(d, (x + width / 2.0, 466), "t = %d" % t, 19, MUTED, False, True, anchor="ma")
        x += width + 30
    return image


@figure("a8c-4", 560, 220)
def a8c_teacher():
    """2번 자리에서 cat 을 냈을 때 3번 자리 입력(Teacher Forcing 은 dog, 추론은 cat)."""
    ids = [1, 4, 5, 6, 2]
    w = {1: "<start>", 4: "a", 5: "dog", 6: "runs", 2: "<end>"}
    pairs = _pairs(ids)
    assert w[pairs[2][0]] == "a" and w[pairs[2][1]] == "dog" and pairs[3][0] == 5
    image, d = _new(440)
    _title(d, "2번 자리에서 틀렸을 때 3번 자리에 들어가는 입력")
    _t(d, (36, 64), "정답 번호 줄 [1, 4, 5, 6, 2]", 19, MUTED, False, True)
    _t(d, (380, 104), "자리 2", 20, MUTED, True, anchor="mm")
    _t(d, (640, 104), "자리 3", 20, MUTED, True, anchor="mm")
    rows = [("Teacher Forcing", BLUE, BLUE_L, w[pairs[3][0]], "정답 줄의 dog를 넣음"),
            ("추론", ORANGE, ORANGE_L, "cat", "앞 자리 예측 cat을 넣음")]
    for r, (name, color, pale, nxt, note) in enumerate(rows):
        top = 124 + r * 160
        _t(d, (36, top + 54), name, 22, color, True, anchor="lm")

        def slot(x0, y0, label, value, outline, fill, ink, dashed=False):
            rect = (x0, y0, x0 + 160, y0 + 48)
            if dashed:
                _dash(d, rect, LIGHT, 2, 7)
            else:
                d.rounded_rectangle(rect, 8, fill=fill, outline=outline, width=3 if outline != LIGHT else 2)
            _t(d, (x0 + 14, y0 + 24), label, 19, MUTED, anchor="lm")
            if value:
                _t(d, (x0 + 146, y0 + 24), value, 22, ink, True, True, anchor="rm")

        slot(300, top, "출력", "cat", RED, RED_L, RED)
        slot(300, top + 58, "입력", w[pairs[2][0]], LIGHT, "white", INK)
        slot(560, top, "출력", "", LIGHT, "white", INK, dashed=True)
        slot(560, top + 58, "입력", nxt, color, pale, color)
        arrow(d, (468, top + 50), (552, top + 80), color, 4)
        _t(d, (760, top + 82), note, 20, color, True, anchor="lm")
    d.line((36, 274, 1084, 274), fill=LINE, width=2)
    return image


@figure("a8c-31", 520, 280)
def a8c_level7():
    """사진 칸과 시작·낱말 셋·끝 칸, 보기로 그린 화살표 둘."""
    image, d = _new(LH, LW)
    texts = ["사진", "시작", "낱말", "낱말", "낱말", "끝"]
    cell, gap, left = 150, 16, 32
    y0, y1 = 270, 370
    centers = []
    for c, text in enumerate(texts):
        x0 = left + c * (cell + gap)
        word = c in (1, 2, 3, 4)
        _cell(d, (x0, y0, x0 + cell, y1), text, BLUE if word else PURPLE_L, BLUE if word else LIGHT, 36,
              "white" if word else INK, True, False, low=LEVEL_MIN)
        centers.append(x0 + cell / 2.0)
    for a, b in ((0, 1), (1, 2)):
        _curve(d, (centers[a] + 14, y0 - 8), (centers[b] - 14, y0 - 8), 70, BLUE, 5)
    return image


@figure("a8c-32", 520, 280)
def a8c_level15():
    pairs = {n: len(_pairs(list(range(n)))) for n in (3, 4, 7, 6)}
    assert pairs == {3: 3, 4: 4, 7: 7, 6: 6} and pairs[7] + pairs[6] == 13
    return levels.grid([["3", "3"], ["4", "4"], ["7", ""], ["6", ""]], col_names=("번호 줄 길이", "짝 수"),
                       marks=[(2, 1), (3, 1)], color="orange")


@figure("a8c-33", 520, 280)
def a8c_level20():
    """21자리 줄에서 lens 20 만큼 남기고 마지막 자리에 ×."""
    x_len = 20 + 1
    kept, _ = _pack([list(range(x_len))], [20])
    assert len(kept) == 20 and 16 * len(kept) == 320
    image, d = _new(LH, LW)
    left = 24
    cell = (LW - 48) / float(x_len)
    y0, y1 = 220, 300
    for c in range(x_len):
        x0 = left + c * cell + 2
        x1 = x0 + cell - 4
        if c == 0:
            d.rounded_rectangle((x0, y0, x1, y1), 5, fill=NOTE, outline=LIGHT, width=2)
        else:
            d.rounded_rectangle((x0, y0, x1, y1), 5, fill=BLUE, outline=BLUE, width=2)
        if c == x_len - 1:
            _cross(d, (x0 + x1) / 2.0, (y0 + y1) / 2.0, 13, RED, 6)
            d.rounded_rectangle((x0, y0, x1, y1), 5, outline=RED, width=4)
    keep_end = left + (x_len - 1) * cell - 2
    _bracket(d, left + 2, keep_end, 320, MUTED, down=False, tick=14, width=4)
    _t(d, ((left + keep_end) / 2.0, 340), "남는 자리 20", 34, INK, True, anchor="ma", low=LEVEL_MIN)
    return image


# a8d LSTM 출력을 9,948개 점수로 바꾸고 손실 읽기

V, E, H = 9948, 256, 512


def _a8d_params():
    emb = V * E
    lstm = 4 * (H * E + H * H + 2 * H)
    lin = H * V + V
    inner = H * E + H * H + 2 * H
    assert (emb, lstm, lin, emb + lstm + lin, inner) == (2546688, 1576960, 5103324, 9226972, 394240)
    return emb, lstm, lin, inner


@figure("a8d-1", 560, 200)
def a8d_params():
    """디코더 층 셋의 파라미터 수 막대와 합."""
    emb, lstm, lin, inner = _a8d_params()
    image, d = _new(400)
    _title(d, "디코더 파라미터는 Linear가 가장 많습니다")
    rows = [("Embedding(9948, 256)", emb, BLUE_M), ("LSTM(256, 512)", lstm, BLUE_M), ("Linear(512, 9948)", lin, BLUE)]
    full = 560
    for r, (name, count, color) in enumerate(rows):
        cy = 110 + r * 76
        _t(d, (36, cy), name, 20, INK, r == 2, True, anchor="lm")
        x1 = 300 + full * count / float(lin)
        d.rounded_rectangle((300, cy - 20, x1, cy + 20), 5, fill=color)
        end = _t(d, (x1 + 12, cy), _comma(count), 20, INK, True, True, anchor="lm")
        if r == 1:
            _t(d, (end[2] + 24, cy - 13), "4 × (512 × 256 + 512 × 512 + 2 × 512)", 19, INK, False, True, anchor="lm")
            _t(d, (end[2] + 24, cy + 15), "괄호 안 %s" % _comma(inner), 19, MUTED, False, True, anchor="lm")
    d.line((36, 312, 1084, 312), fill=LINE, width=2)
    _t(d, (1084, 348), "합 %s" % _comma(emb + lstm + lin), 24, INK, True, True, anchor="rm")
    return image


def _a8d2_frame(k):
    caps = [[1, 4, 5, 6, 2], [1, 4, 7, 2, 0]]
    real = [a for row in caps for a in row if a != 0]
    p = 0.5
    loss = -log(p)
    assert len(real) == 9 and _d4(loss) == "0.6931" and _d4(sum([loss] * len(real)) / len(real)) == "0.6931"
    image, d = _new(580)
    _title(d, "정답이 0인 자리는 손실 평균에서 빠집니다")
    for r, row in enumerate(caps):
        cy = 84 + r * 84
        _t(d, (36, cy + 35), "캡션 %d" % (r + 1), 20, INK, True, anchor="lm")
        for c, a in enumerate(row):
            x0 = 150 + c * 110
            rect = (x0, cy, x0 + 102, cy + 74)
            pad = a == 0
            here = (r, c) == (0, 0) and k <= 1
            if pad and k >= 2:
                _dash(d, rect, LIGHT, 2, 7)
            else:
                d.rounded_rectangle(rect, 8, fill=BLUE_L if (k >= 2 and not pad) else "white",
                                    outline=BLUE if (here or (k >= 2 and not pad)) else LIGHT, width=3 if here else 2)
            _t(d, (x0 + 51, cy + (23 if k >= 2 else 37)), "정답 %d" % a, 19, RED if pad else MUTED, pad, anchor="mm")
            if k >= 2:
                _t(d, (x0 + 51, cy + 53), "제외" if pad else _d4(loss), 19 if pad else 20, LIGHT if pad else BLUE, not pad,
                   not pad, anchor="mm")
    if k >= 3:
        d.rounded_rectangle((760, 100, 1084, 220), 12, fill=BLUE, outline=BLUE)
        _t(d, (922, 136), "10자리 중 9자리의 평균", 20, "white", anchor="mm")
        _t(d, (922, 182), _d4(loss), 30, "white", True, True, anchor="mm")
    if k <= 1:
        _t(d, (36, 326), "캡션 1의 0번 자리", 19, BLUE, True, anchor="lb")
    _cell(d, (36, 340, 196, 440), "", BLUE_L, BLUE, width=3)
    _t(d, (116, 372), "LSTM 출력", 20, INK, True, anchor="mm")
    _t(d, (116, 408), "512개", 20, BLUE, True, anchor="mm")
    arrow(d, (204, 390), (248, 390), MUTED, 4)
    _cell(d, (256, 360, 396, 420), "Linear", "white", LIGHT, 22, INK, True, False)
    arrow(d, (404, 390), (448, 390), MUTED, 4)
    _panel(d, (456, 290, 740, 500))
    _t(d, (470, 302), "점수 8개를 확률로 바꾼 값", 19, MUTED)
    base, top_h = 458, 88
    probs = [p if i == 1 else (1 - p) / 7.0 for i in range(8)]
    assert abs(sum(probs) - 1) < 1e-12
    for i, q in enumerate(probs):
        x0 = 476 + i * 32
        hit = i == 1 and k >= 1
        d.rectangle((x0, base - top_h * q / p, x0 + 22, base), fill=BLUE if hit else LIGHT)
        _t(d, (x0 + 11, base + 6), str(i), 19, BLUE if hit else MUTED, hit, True, anchor="ma")
    if k >= 1:
        _t(d, (476 + 32 + 11, base - top_h - 6), "0.5", 19, BLUE, True, True, anchor="mb")
        _t(d, (760, 400), "−ln 0.5 = %s" % _d4(loss), 24, INK, True, True, anchor="lm")
        _t(d, (760, 436), "정답 1의 확률로 계산한 손실", 19, MUTED, anchor="lm")
    lines = ["한 자리의 LSTM 출력 512개가 Linear를 지나 점수 8개가 됩니다.", "정답 낱말의 확률 0.5로 그 자리의 손실을 구합니다.",
             "진짜 9자리에 손실이 적히고, 정답이 0인 칸은 빠집니다.", "9자리의 손실을 더해 9로 나눈 평균이 오른쪽에 적힙니다."]
    _foot(d, 534, lines[k])
    return image


@figure("a8d-2", 560, 290)
def a8d_ignore():
    """자리 10칸 → 한 자리의 LSTM → Linear → 점수 8개 → 정답 점수 → 정답 0 제외 → 9자리 평균(4장)."""
    return [_a8d2_frame(k) for k in range(4)], [2200, 2200, 2200, 2400]


@figure("a8d-3", 560, 220)
def a8d_uniform():
    """확률 0.125 막대 8개와 촘촘한 띠, 손실 ln V 와 perplexity."""
    small, big = log(8), log(V)
    assert _d4(small) == "2.0794" and _d4(big) == "9.2051" and round(exp(small)) == 8 and round(exp(big)) == V
    assert 1 / 8.0 == 0.125
    image, d = _new(440)
    _title(d, "같은 점수로 시작하면 손실은 ln V, perplexity는 V입니다")
    base, h = 320, 170
    for n, (x0, x1, name) in enumerate(((36, 540, "어휘 8개"), (580, 1084, "어휘 9,948개"))):
        _t(d, (x0, 80), name, 21, INK, True)
        d.line((x0, base, x1, base), fill=LIGHT, width=2)
    _t(d, (80, base - h - 12), "막대마다 0.125", 19, MUTED, False, True, anchor="lb")
    for i in range(8):
        x0 = 80 + i * 56
        d.rectangle((x0, base - h, x0 + 30, base), fill=BLUE)
    _t(d, (600, base - 30), "막대마다 1/9,948", 19, MUTED, False, True, anchor="lb")
    for i in range(160):
        x0 = 600 + i * 3
        d.rectangle((x0, base - 5, x0 + 1, base), fill=BLUE)
    for x0, loss, ppl in ((36, "손실 ln 8 = %s" % _d4(small), "perplexity 8"),
                          (580, "손실 ln 9948 = %s" % _d4(big), "perplexity 9,948")):
        _t(d, (x0, 352), loss, 21, INK, True, True)
        _t(d, (x0, 388), ppl, 21, BLUE, True, True)
    return image


@figure("a8d-4", 560, 230)
def a8d_ckpt():
    """0~3236 눈금, 1000·2000·3000 저장 표시와 파일 이름, 3000~3236 회색 저장 없음."""
    steps = ceil(414113 / 128.0)
    saves = [i + 1 for i in range(steps) if (i + 1) % 1000 == 0]
    assert steps == 3236 and saves == [1000, 2000, 3000] and steps - saves[-1] == 236
    image, d = _new(460)
    _title(d, "한 에폭 3,236스텝에 체크포인트를 세 번 저장합니다")
    x0, x1, y = 80, 1040, 320

    def at(s):
        return x0 + (x1 - x0) * s / float(steps)

    d.rectangle((at(3000), y - 16, x1, y + 16), fill=NOTE, outline=LIGHT, width=2)
    d.line((x0, y, at(3000), y), fill=BLUE, width=5)
    for s in (0, 1000, 2000, 3000, steps):
        d.line((at(s), y + 8, at(s), y + 20), fill=MUTED, width=3)
        _t(d, (at(s), y + 26), str(s), 20, BLUE if s in saves else INK, s in saves, True, anchor="ma")
    for s in saves:
        cx = at(s)
        d.ellipse((cx - 12, y - 12, cx + 12, y + 12), fill=BLUE, outline="white", width=3)
        d.rounded_rectangle((cx - 104, 104, cx + 104, 196), 10, fill="white", outline=BLUE_M, width=2)
        for k, part in enumerate(("decoder", "encoder")):
            _t(d, (cx, 132 + k * 36), "%s-1-%d.ckpt" % (part, s), 19, INK, False, True, anchor="mm")
        d.line((cx, 196, cx, y - 14), fill=BLUE, width=3)
    _t(d, ((at(3000) + x1) / 2.0, y + 64), "저장 없음", 19, MUTED, True, anchor="ma")
    _t(d, ((at(3000) + x1) / 2.0, y + 92), "236스텝", 19, MUTED, anchor="ma")
    _t(d, (36, 412), "i + 1이 1000의 배수일 때만 저장합니다.", 19, MUTED)
    return image


# a8e greedy 탐색으로 한 낱말씩 고르고 <end> 에서 멈추기

WORDS = {0: "<pad>", 1: "<start>", 2: "<end>", 3: "<unk>", 4: "a", 5: "dog", 6: "runs", 7: "cat"}
SAMPLED = [1, 4, 5, 6, 2, 5, 6, 2]


def _decode_first(ids):
    """첫 번째 코드: 낱말을 넣은 다음 <end> 이면 멈춤."""
    out = []
    for i in ids:
        out.append(WORDS[i])
        if WORDS[i] == "<end>":
            break
    return " ".join(out)


def _decode_second(ids):
    """두 번째 코드: <end> 이면 넣기 전에 멈추고 <start>, <pad>, <unk> 는 건너뜀."""
    words = []
    for i in ids:
        w = WORDS[i]
        if w == "<end>":
            break
        if w not in ["<start>", "<pad>", "<unk>"]:
            words.append(w)
    return " ".join(words)


def _a8e1_frame(k):
    picked = SAMPLED[:5]
    assert [WORDS[i] for i in picked] == ["<start>", "a", "dog", "runs", "<end>"]
    image, d = _new(600)
    _title(d, "sample은 고른 번호를 다음 자리 입력으로 넣습니다")
    xs = [40 + n * 145 for n in range(6)] + [950]
    shown = {0: 1, 1: 1, 2: 2, 3: 5, 4: 7}[k]
    labels = {0: 1, 1: 2, 2: 2, 3: 5, 4: 7}[k]  # 위 꼬리표를 적은 상자 수
    if k == 0:
        labels = 0
    if k == 4:
        _chip(d, (1084, 84), "결과 (1, 20)", BLUE, BLUE_L, 21, anchor="rm", code=True)
    for n, x0 in enumerate(xs):
        if n >= shown:
            continue
        last = n == 6
        box = (x0, 230, x0 + 90, 300)
        _cell(d, box, "LSTM", BLUE_L if n == shown - 1 and k < 4 else "white", BLUE if n < 6 else LIGHT, 22,
              BLUE if n < 6 else MUTED, True, True, width=3 if n == shown - 1 and k < 4 else 2)
        if last:
            _t(d, (x0 + 45, 308), "20번째", 19, MUTED, anchor="ma")
        if n < labels:
            if n < 5:
                number = SAMPLED[n]
                text, color = "%d %s" % (number, WORDS[number]), BLUE
            elif n == 5:
                text, color = "5 dog", MUTED
            else:
                text, color = "20번째 번호", MUTED
            arrow(d, (x0 + 45, 226), (x0 + 45, 166), MUTED, 3)
            _chip(d, (x0 + 45, 142), text, color, "white" if color == MUTED else BLUE_L, 19, code=n < 6)
        if n == 0:
            arrow(d, (x0 + 45, 352), (x0 + 45, 304), BLUE, 4)
            _t(d, (x0 + 45, 362), "(1, 1, 256)", 19, BLUE, True, True, anchor="ma")
            _t(d, (x0 + 45, 396), "unsqueeze(1)", 19, MUTED, False, True, anchor="ma")
            _t(d, (x0 + 45, 430), "이미지 특징", 19, INK, True, anchor="ma")
            _t(d, (x0 + 45, 458), "(1, 256)", 19, MUTED, False, True, anchor="ma")
        elif not last:
            prev = WORDS[SAMPLED[n - 1]]
            arrow(d, (x0 + 45, 352), (x0 + 45, 304), BLUE, 3)
            _t(d, (x0 + 45, 362), prev, 19, BLUE, True, True, anchor="ma")
            _t(d, (x0 + 45, 392), "임베딩", 19, MUTED, anchor="ma")
        if 0 < n:
            px = xs[n - 1] + 90
            if last:
                _dash_line(d, (xs[5] + 90 + 4, 265, 880, 265), LIGHT, 3, 6)
                _t(d, (900, 265), "…", 24, MUTED, anchor="mm")
                _dash_line(d, (920, 265, x0 - 6, 265), LIGHT, 3, 6)
                arrow(d, (x0 - 14, 265), (x0 - 2, 265), LIGHT, 3)
            else:
                arrow(d, (px + 4, 265), (x0 - 4, 265), MUTED, 3)
                _t(d, ((px + x0) / 2.0, 258), "h, c", 19, MUTED, False, True, anchor="mb")
    lines = ["이미지 특징 (1, 256)을 unsqueeze(1)로 (1, 1, 256)으로 만들어 첫 LSTM에 넣습니다.",
             "첫 자리에서 점수가 가장 큰 1 <start>를 고릅니다.", "<start>의 임베딩이 둘째 자리 입력이 되고, h와 c가 다음 자리로 넘어갑니다.",
             "셋째부터 다섯째 자리에서 5 dog, 6 runs, 2 <end>를 고릅니다.", "<end> 뒤에도 20번째 자리까지 번호를 골라 결과는 (1, 20)입니다."]
    _foot(d, 530, lines[k])
    return image


@figure("a8e-1", 560, 300)
def a8e_sample():
    """sample 이 고른 번호를 다음 자리 입력으로 넣고 h, c 를 넘김(5장)."""
    return [_a8e1_frame(k) for k in range(5)], [2200, 2000, 2200, 2200, 2400]


@figure("a8e-2", 560, 220)
def a8e_stop():
    """번호 칸 8개와 … 칸, <end> 뒤 굵은 선, 두 코드의 결과."""
    first, second = _decode_first(SAMPLED), _decode_second(SAMPLED)
    assert first == "<start> a dog runs <end>" and second == "a dog runs"
    image, d = _new(440)
    _title(d, "두 코드 모두 <end>에서 멈춥니다")
    _t(d, (36, 76), "sample이 고른 번호", 19, MUTED)
    for k in range(9):
        x0 = 36 + k * 92
        after = k >= 5
        if k == 8:
            _dcell(d, (x0, 104, x0 + 80, 160), "…", LIGHT, 24, LIGHT, code=False)
            continue
        number = SAMPLED[k]
        _cell(d, (x0, 104, x0 + 80, 160), str(number), NOTE if after else ("white" if number != 2 else RED_L),
              LIGHT if after else (RED if number == 2 else BLUE), 24, LIGHT if after else (RED if number == 2 else BLUE), True)
        _t(d, (x0 + 40, 168), WORDS[number], 19, LIGHT if after else MUTED, False, True, anchor="ma")
    d.line((36 + 5 * 92 - 7, 92, 36 + 5 * 92 - 7, 200), fill=RED, width=6)
    rows = [("첫 번째 코드", first.split(), set()), ("두 번째 코드", ["<start>", "a", "dog", "runs", "<end>"], {"<start>", "<end>"})]
    for r, (name, words, gone) in enumerate(rows):
        y0 = 250 + r * 84
        _t(d, (36, y0 + 28), name, 21, INK, True, anchor="lm")
        for c, word in enumerate(words):
            x0 = 230 + c * 130
            rect = (x0, y0, x0 + 120, y0 + 56)
            if word in gone:
                _dcell(d, rect, word, LIGHT, 20, LIGHT, fill=NOTE)
                tw = _w(word, 20, False, True)
                d.line((x0 + 60 - tw / 2.0, y0 + 28, x0 + 60 + tw / 2.0, y0 + 28), fill=LIGHT, width=2)
            else:
                blue = r == 1
                _cell(d, rect, word, BLUE_L if blue else "white", BLUE if blue else LIGHT, 22, BLUE if blue else INK, blue)
    return image


def _beam():
    first = {"a": 0.5, "the": 0.4, "one": 0.1}
    nxt = {"a": {"dog": 0.3, "cat": 0.25, "man": 0.25, "car": 0.2}, "the": {"dog": 0.9, "cat": 0.1}}
    kept = sorted(first, key=first.get, reverse=True)[:2]
    cands = sorted(((w1, w2, round(first[w1] * p, 4)) for w1 in kept for w2, p in nxt[w1].items()), key=lambda c: -c[2])
    g1 = max(first, key=first.get)
    g2 = max(nxt[g1], key=nxt[g1].get)
    greedy = (g1, g2, round(first[g1] * nxt[g1][g2], 4))
    assert kept == ["a", "the"] and greedy == ("a", "dog", 0.15)
    assert [c[2] for c in cands] == [0.36, 0.15, 0.125, 0.125, 0.1, 0.04] and cands[0][:2] == ("the", "dog")
    return first, nxt, cands, greedy


@figure("a8e-3", 560, 300)
def a8e_beam():
    """빔 나무: 첫 가지 셋, one 회색, 둘째 가지 여섯과 누적 확률, 남긴 둘 굵은 테두리, greedy 길 점선."""
    first, nxt, cands, greedy = _beam()
    kept = {(c[0], c[1]) for c in cands[:2]}
    image, d = _new(600)
    _title(d, "빔 크기 2는 누적 확률 0.36인 the dog를 고릅니다")
    _t(d, (300, 74), "첫 자리", 20, MUTED, True)
    _t(d, (640, 74), "둘째 자리(누적 확률)", 20, MUTED, True)
    root = (40, 300, 140, 352)
    _cell(d, root, "시작", "white", LIGHT, 22, INK, True, False)
    ys1 = {"a": 216, "the": 440, "one": 544}
    ys2 = {("a", "dog"): 134, ("a", "cat"): 194, ("a", "man"): 254, ("a", "car"): 314, ("the", "dog"): 414, ("the", "cat"): 474}
    for w1, y in ys1.items():
        gray = w1 == "one"
        d.line((140, 326, 300, y), fill=LIGHT if gray else INK, width=3)
        rect = (300, y - 26, 450, y + 26)
        _cell(d, rect, "", NOTE if gray else "white", LIGHT if gray else BLUE, width=3 if not gray else 2)
        _t(d, (316, y), w1, 22, MUTED if gray else INK, not gray, True, anchor="lm")
        _t(d, (436, y), fmt(first[w1], 2), 22, MUTED if gray else BLUE, not gray, True, anchor="rm")
        if gray:
            _t(d, (466, y), "버림", 19, MUTED, anchor="lm")
    for (w1, w2), y in ys2.items():
        cum = round(first[w1] * nxt[w1][w2], 4)
        keep = (w1, w2) in kept
        is_greedy = (w1, w2) == greedy[:2]
        d.line((450, ys1[w1], 640, y), fill=BLUE if (w1, w2) == cands[0][:2] else LIGHT, width=3)
        rect = (640, y - 24, 830, y + 24)
        _cell(d, rect, "", "white", BLUE if keep else LIGHT, width=4 if keep else 2)
        _t(d, (656, y), w2, 21, INK, keep, True, anchor="lm")
        _t(d, (816, y), fmt(cum, 3), 21, BLUE if keep else MUTED, keep, True, anchor="rm")
        if keep:
            _chip(d, (850, y), "빔이 남긴 둘 (%d위)" % (1 if cum == cands[0][2] else 2), BLUE, BLUE_L, 19, anchor="lm")
    # greedy 길은 시작 → a → dog 를 따라 주황 점선
    _dash_line(d, (140, 318, 300, ys1["a"] - 8), ORANGE, 4, 9)
    _dash_line(d, (450, ys1["a"] - 8, 640, ys2[("a", "dog")] - 8), ORANGE, 4, 9)
    _chip(d, (850, ys2[("a", "dog")] + 40), "greedy 탐색이 고름", ORANGE, ORANGE_L, 19, anchor="lm")
    return image


@figure("a8e-4", 560, 230)
def a8e_attention():
    """칸 값 3×3, 가중치 3×3(가운데 가장 진함), soft 결과와 hard 설명."""
    values = [[2, 0, 4], [0, 6, 2], [0, 0, 0]]
    weights = [[0.05, 0.05, 0.1], [0.05, 0.5, 0.1], [0.05, 0.05, 0.05]]
    total = sum(sum(r) for r in weights)
    soft = sum(values[r][c] * weights[r][c] for r in range(3) for c in range(3))
    assert abs(total - 1) < 1e-12 and round(soft, 4) == 3.7
    image, d = _new(460)
    _title(d, "soft attention은 아홉 칸의 값을 가중합합니다")
    _t(d, (174, 96), "칸 값", 20, INK, True, anchor="mm")
    _t(d, (494, 96), "가중치", 20, INK, True, anchor="mm")
    for r in range(3):
        for c in range(3):
            x0, y0 = 60 + c * 76, 120 + r * 76
            _cell(d, (x0, y0, x0 + 72, y0 + 72), str(values[r][c]), "white", LIGHT, 24, INK, True, radius=4)
            wv = weights[r][c]
            fill = BLUE if wv == 0.5 else (BLUE_M if wv == 0.1 else BLUE_L)
            x1 = 380 + c * 76
            _cell(d, (x1, y0, x1 + 72, y0 + 72), fmt(wv, 2), fill, BLUE_M, 22, "white" if wv == 0.5 else INK, True, radius=4)
    _t(d, (334, 234), "×", 30, MUTED, anchor="mm")
    _t(d, (494, 360), "합 1", 20, MUTED, False, True, anchor="ma")
    arrow(d, (640, 234), (700, 234), MUTED, 4)
    d.rounded_rectangle((720, 150, 1084, 222), 12, fill=BLUE_L, outline=BLUE, width=3)
    _t(d, (902, 186), "soft = %s" % fmt(soft, 1), 30, BLUE, True, True, anchor="mm")
    d.rounded_rectangle((720, 250, 1084, 318), 12, fill="white", outline=LIGHT, width=2)
    _t(d, (902, 284), "hard: 칸 하나를 뽑음", 22, INK, anchor="mm")
    _t(d, (36, 410), "0.05 × 2 + 0.1 × 4 + 0.5 × 6 + 0.1 × 2 = %s" % fmt(soft, 1), 20, MUTED, False, True)
    return image


# a8f BLEU·METEOR·CIDEr 를 짧은 문장으로 계산하기

REF = "a big car parked near the old house".split()
CAND = "a big car parked near the house".split()


def _grams(words, n):
    return [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]


def _bleu():
    """n그램마다 (맞음 여부 목록, 맞은 수, 전체 수), 기하평균, 벌점, BLEU-4."""
    rows = []
    for n in range(1, 5):
        ref = _grams(REF, n)
        left = list(ref)
        hits = []
        for g in _grams(CAND, n):
            ok = g in left
            if ok:
                left.remove(g)
            hits.append(ok)
        rows.append((hits, sum(hits), len(hits)))
    prod = 1.0
    for _, m, t in rows:
        prod *= m / float(t)
    geo = prod ** 0.25
    bp = exp(1 - len(REF) / float(len(CAND)))
    score = geo * bp
    assert [(m, t) for _, m, t in rows] == [(7, 7), (5, 6), (4, 5), (3, 4)]
    assert _d4(geo) == "0.8409" and _d4(bp) == "0.8669" and round(score, 4) == 0.729
    return rows, geo, bp, score


def _meteor(ref, cand):
    """낱말이 한 번씩만 나오는 문장의 정확 일치 METEOR. (m, 덩어리, P, R, Fmean, 벌점, 점수, 자리 번호)."""
    pos = [ref.index(w) + 1 for w in cand if w in ref]
    m = len(pos)
    chunks = 1 + sum(1 for a, b in zip(pos, pos[1:]) if b != a + 1)
    p, r = m / float(len(cand)), m / float(len(ref))
    f = 10 * p * r / (r + 9 * p)
    pen = 0.5 * (chunks / float(m)) ** 3
    return m, chunks, p, r, f, pen, f * (1 - pen), pos


def _a8f1_frame(k):
    rows, geo, bp, score = _bleu()
    image, d = _new(600)
    _title(d, "n그램 정밀도 넷과 짧은 길이 벌점으로 구한 BLEU-4")
    for r, (name, words) in enumerate((("정답", REF), ("후보", CAND))):
        y = 96 + r * 52
        _t(d, (36, y), name, 20, MUTED, True, anchor="lm")
        x = 110
        for word in words:
            miss = name == "정답" and word == "old"
            rect = _chip(d, (x, y), word, LIGHT if miss else INK, NOTE if miss else "white", 20, anchor="lm", code=True,
                         bold=False)
            x = rect[2] + 10
    d.line((36, 182, 1084, 182), fill=LINE, width=2)
    upto = {0: 1, 1: 2, 2: 4, 3: 4}[k]
    for n in range(upto):
        hits, m, t = rows[n]
        y = 216 + n * 58
        _t(d, (36, y), "%d그램" % (n + 1), 20, INK, True, anchor="lm")
        x = 110
        for g, ok in zip(_grams(CAND, n + 1), hits):
            rect = _chip(d, (x, y), " ".join(g), GREEN if ok else RED, GREEN_L if ok else RED_L, 19, anchor="lm", code=True,
                         bold=False)
            x = rect[2] + 8
        _t(d, (1084, y), "%d/%d" % (m, t), 24, GREEN if m == t else INK, True, True, anchor="rm")
    if k == 3:
        boxes = [((110, 466, 330, 556), "기하평균", _d4(geo), "white", LIGHT, INK),
                 ((380, 466, 760, 556), "짧은 길이 벌점", "exp(1 − 8/7) = %s" % _d4(bp), "white", LIGHT, INK),
                 ((810, 466, 1084, 556), "BLEU-4", "%.3f" % round(score, 3), BLUE, BLUE, "white")]
        for rect, head, value, fill, line, ink in boxes:
            d.rounded_rectangle(rect, 12, fill=fill, outline=line, width=2)
            _t(d, ((rect[0] + rect[2]) / 2.0, rect[1] + 24), head, 19, ink if fill == BLUE else MUTED, anchor="mm")
            _t(d, ((rect[0] + rect[2]) / 2.0, rect[1] + 62), value, 24, ink, True, True, anchor="mm")
        _t(d, (355, 511), "×", 28, MUTED, anchor="mm")
        _t(d, (785, 511), "=", 28, MUTED, anchor="mm")
    return image


@figure("a8f-1", 560, 300)
def a8f_bleu():
    """정답 8낱말·후보 7낱말, 1~4그램 맞음·없음, 기하평균·벌점·BLEU-4(4장)."""
    return [_a8f1_frame(k) for k in range(4)], [2000, 2000, 2200, 2400]


@figure("a8f-2", 560, 240)
def a8f_meteor():
    """짝 선 7개, 후보 앞 6낱말 파랑 덩어리, house 주황 덩어리, 정답 old 회색, 오른쪽 값."""
    m, chunks, p, r, f, pen, score, _ = _meteor(REF, CAND)
    assert (m, chunks, p, r) == (7, 2, 1.0, 0.875)
    assert _d4(f) == "0.8861" and _d4(pen) == "0.0117" and _d4(score) == "0.8757"
    image, d = _new(480)
    _title(d, "METEOR는 짝 7개를 덩어리 둘로 묶습니다")
    ref_rects = {}
    _t(d, (36, 124), "정답", 20, MUTED, True, anchor="lm")
    _t(d, (36, 324), "후보", 20, MUTED, True, anchor="lm")
    x = 110
    for word in REF:
        miss = word not in CAND
        rect = _chip(d, (x, 124), word, LIGHT if miss else INK, NOTE if miss else "white", 21, anchor="lm", code=True,
                     bold=False)
        ref_rects[word] = rect
        x = rect[2] + 12
    x = 110
    cand_rects = []
    for word in CAND:
        rect = _chip(d, (x, 324), word, INK, "white", 21, anchor="lm", code=True, bold=False)
        cand_rects.append(rect)
        x = rect[2] + 12
    for word, rect in zip(CAND, cand_rects):
        top = ref_rects[word]
        color = ORANGE if word == "house" else BLUE
        d.line(((top[0] + top[2]) / 2.0, top[3] + 4, (rect[0] + rect[2]) / 2.0, rect[1] - 10), fill=color, width=3)
    first = cand_rects[:6]
    d.rounded_rectangle((first[0][0] - 8, first[0][1] - 8, first[-1][2] + 8, first[0][3] + 8), 12, outline=BLUE, width=3)
    last = cand_rects[6]
    d.rounded_rectangle((last[0] - 8, last[1] - 8, last[2] + 8, last[3] + 8), 12, outline=ORANGE, width=3)
    _t(d, ((first[0][0] + first[-1][2]) / 2.0, first[0][3] + 18), "덩어리 1", 19, BLUE, True, anchor="ma")
    _t(d, ((last[0] + last[2]) / 2.0, last[3] + 18), "덩어리 2", 19, ORANGE, True, anchor="ma")
    _panel(d, (740, 80, 1100, 444))
    values = [("m = %d" % m, INK), ("덩어리 %d" % chunks, INK), ("P = %s" % fmt(p, 3), INK), ("R = %s" % fmt(r, 3), INK),
              ("Fmean %s" % _d4(f), INK), ("벌점 0.5 × (2/7)³ = %s" % _d4(pen), INK), ("METEOR %s" % _d4(score), BLUE)]
    for n, (text, color) in enumerate(values):
        _t(d, (760, 110 + n * 50), text, 21 if n < 6 else 24, color, n in (0, 1, 6), True, anchor="lm")
    return image


@figure("a8f-3", 560, 220)
def a8f_idf():
    """사진 칸 셋과 정답 캡션 셋, IDF 표, 사진 1장이면 0."""
    caps = ["a dog runs on the grass", "a cat sleeps on the sofa", "a red car near the house"]
    words = ["a", "the", "on", "dog"]
    df = {w: sum(1 for c in caps if w in c.split()) for w in words}
    idf = {w: log(len(caps) / float(df[w])) for w in words}
    assert [df[w] for w in words] == [3, 3, 2, 1] and [_d4(idf[w]) for w in ("on", "dog")] == ["0.4055", "1.0986"]
    assert idf["a"] == idf["the"] == 0 and log(1 / 1.0) == 0
    image, d = _new(440)
    _title(d, "많은 사진에 나오는 낱말일수록 IDF가 작습니다")
    tone = {"a": BLUE, "the": BLUE, "on": PURPLE, "dog": ORANGE}
    for n, cap in enumerate(caps):
        y = 92 + n * 92
        _photo(d, (36, y, 136, y + 70), "사진 %d" % (n + 1))
        x = 156
        for word in cap.split():
            color = tone.get(word, INK)
            box = _t(d, (x, y + 35), word, 21, color, word in tone, True, anchor="lm")
            x = box[2] + 12
    cols = [640, 780, 940, 1084]
    d.rounded_rectangle((640, 88, 1084, 344), 10, fill="white", outline=LINE, width=2)
    d.rectangle((642, 90, 1082, 136), fill=PANEL)
    for c, head in enumerate(("낱말", "나온 사진 수", "IDF")):
        _t(d, ((cols[c] + cols[c + 1]) / 2.0, 113), head, 19, MUTED, True, anchor="mm")
    for r, word in enumerate(words):
        y = 136 + r * 52
        if r:
            d.line((642, y, 1082, y), fill=LINE, width=1)
        texts = [word, str(df[word]), "0" if idf[word] == 0 else _d4(idf[word])]
        for c, text in enumerate(texts):
            _t(d, ((cols[c] + cols[c + 1]) / 2.0, y + 26), text, 21, tone[word] if c != 1 else INK, True, True,
               anchor="mm")
    _chip(d, (862, 380), "사진 1장이면 log(1/1) = 0", INK, NOTE, 20, code=True, bold=False)
    return image


SCORE_LABEL = {1: (18, 0, "lm"), 2: (-14, -12, "rb"), 3: (14, -12, "lb"), 4: (14, -12, "lb"), 5: (-14, 12, "ra")}


@figure("a8f-4", 560, 260)
def a8f_early():
    """에폭 1~5 학습 손실과 검증 점수(예로 정한 값), 에폭 3 세로 점선."""
    loss = [3.1, 2.7, 2.5, 2.4, 2.3]
    score = [0.61, 0.68, 0.70, 0.69, 0.67]
    best = score.index(max(score)) + 1
    assert best == 3 and all(a > b for a, b in zip(loss, loss[1:]))
    image, d = _new(520)
    _title(d, "검증 점수가 가장 높은 에폭 3의 체크포인트를 남깁니다")
    x0, x1, top, bottom = 150, 950, 120, 410

    def ex(e):
        return 190 + (e - 1) * 180

    def ly(v):
        return bottom - (v - 2.2) / 1.0 * (bottom - top - 10)

    def sy(v):
        return bottom - (v - 0.60) / 0.12 * (bottom - top - 10)

    d.line((x0, top, x0, bottom, x1, bottom, x1, top), fill=LIGHT, width=2)
    for v in (2.2, 2.6, 3.0):
        _t(d, (x0 - 10, ly(v)), "%.1f" % v, 19, MUTED, False, True, anchor="rm")
        d.line((x0, ly(v), x1, ly(v)), fill=COLORS["grid"], width=1)
    for v in (0.60, 0.66, 0.72):
        _t(d, (x1 + 10, sy(v)), "%.2f" % v, 19, BLUE, False, True, anchor="lm")
    _t(d, (x0, 92), "학습 손실", 19, MUTED, True, anchor="mm")
    _t(d, (x1, 92), "검증 점수", 19, BLUE, True, anchor="mm")
    for e in range(1, 6):
        _t(d, (ex(e), bottom + 12), str(e), 20, BLUE if e == best else INK, e == best, True, anchor="ma")
    _t(d, ((x0 + x1) / 2.0, bottom + 44), "에폭", 19, MUTED, anchor="ma")
    _dash_line(d, (ex(best), top - 6, ex(best), bottom), ORANGE, 3, 8)
    _chip(d, (ex(best), 92), "남길 체크포인트", ORANGE, ORANGE_L, 19)
    d.line([(ex(e), ly(v)) for e, v in enumerate(loss, 1)], fill=MUTED, width=4)
    d.line([(ex(e), sy(v)) for e, v in enumerate(score, 1)], fill=BLUE, width=4)
    for e, v in enumerate(loss, 1):
        d.ellipse((ex(e) - 8, ly(v) - 8, ex(e) + 8, ly(v) + 8), fill="white", outline=MUTED, width=3)
        if e == 1:  # 왼쪽 눈금 글과 선을 피해 점 오른쪽 위에 적음
            _t(d, (ex(e) + 14, ly(v) - 12), fmt(v, 1), 19, MUTED, False, True, anchor="lb")
        elif e == 5:  # 가로축 선을 피해 점 위에 적음
            _t(d, (ex(e), ly(v) - 14), fmt(v, 1), 19, MUTED, False, True, anchor="mb")
        else:
            _t(d, (ex(e) - 14, ly(v) + 12), fmt(v, 1), 19, MUTED, False, True, anchor="ra")
    for e, v in enumerate(score, 1):
        d.ellipse((ex(e) - 8, sy(v) - 8, ex(e) + 8, sy(v) + 8), fill=BLUE if e == best else "white", outline=BLUE, width=3)
        dx, dy, anchor = SCORE_LABEL[e]  # 선과 축을 피한 자리
        _t(d, (ex(e) + dx, sy(v) + dy), "%.2f" % v, 19, BLUE, e == best, True, anchor=anchor)
    _t(d, (36, 486), "예로 정한 값입니다.", 19, MUTED)
    return image


@figure("a8f-31", 520, 280)
def a8f_level7():
    """번호 칸 1, 2, 3, 5, 6, 8 과 세 테두리, 아래 줄 6, 7, 8, 1, 2, 3 은 테두리 없음."""
    pos = [1, 2, 3, 5, 6, 8]
    groups, cur = [], [pos[0]]
    for a, b in zip(pos, pos[1:]):
        if b == a + 1:
            cur.append(b)
        else:
            groups.append(cur)
            cur = [b]
    groups.append(cur)
    assert groups == [[1, 2, 3], [5, 6], [8]]
    image, d = _new(LH, LW)
    cell, gap, ggap = 96, 12, 44
    total = 6 * cell + 3 * gap + 2 * ggap
    x = (LW - total) / 2.0
    colors = [BLUE, GREEN, ORANGE]
    for g, members in enumerate(groups):
        start = x
        for n, v in enumerate(members):
            _cell(d, (x, 160, x + cell, 256), str(v), "white", LINE, 44, colors[g], True, low=LEVEL_MIN)
            x += cell + (gap if n < len(members) - 1 else 0)
        d.rounded_rectangle((start - 8, 152, x + 8, 264), 14, outline=colors[g], width=4)
        x += ggap
    x = (LW - (6 * cell + 5 * gap)) / 2.0
    for v in (6, 7, 8, 1, 2, 3):
        _cell(d, (x, 320, x + cell, 416), str(v), NOTE, LINE, 44, INK, True, low=LEVEL_MIN)
        x += cell + gap
    return image


@figure("a8f-32", 520, 280)
def a8f_level15():
    xs = [k / 50.0 for k in range(51)]
    ys = [0.5 * x ** 3 for x in xs]
    assert 0.5 * 0.5 ** 3 == 0.0625 and 0.5 * 1 ** 3 == 0.5
    fig = levels.graph(xs, [(ys, "blue", "")], "덩어리 수 ÷ 맞은 낱말 수", "벌점",
                       marks=[(0.5, 0.0625, "0.0625", "orange"), (1.0, 0.5, "0.5", "blue")], xlim=(0, 1.08), ylim=(0, 0.62))
    fig.axes[0].tick_params(axis="x", pad=12)  # 원점에서 가로축 0.0 과 세로축 0.0 이 붙지 않게 가로축 눈금 글을 내림
    levels._inside(fig)
    return fig


@figure("a8f-33", 520, 280)
def a8f_level20():
    """상자 넷(m·덩어리, P·R, Fmean, METEOR)을 화살표가 잇는 띠. 뒤 두 상자의 값은 비움."""
    m, chunks, p, r, _, _, _, _ = _meteor(REF, "a big car near the house".split())
    assert (m, chunks, p, r) == (6, 3, 1.0, 0.75)
    image, d = _new(LH, LW)
    width, gap = 200, 52
    left = (LW - 4 * width - 3 * gap) / 2.0
    assert left >= 24
    boxes = [["m = %d" % m, "덩어리 %d" % chunks], ["P = %s" % fmt(p, 2), "R = %s" % fmt(r, 2)], ["Fmean", None], ["METEOR", None]]
    for n, lines in enumerate(boxes):
        x0 = left + n * (width + gap)
        d.rounded_rectangle((x0, 160, x0 + width, 400), 16, fill="white", outline=BLUE if n == 3 else LIGHT, width=3)
        for k, text in enumerate(lines):
            if text is None:
                _dash(d, (x0 + 30, 300, x0 + width - 30, 360), LIGHT, 3, 8)
            else:
                _t(d, (x0 + width / 2.0, 240 + k * 70), text, 34, BLUE if n == 3 else INK, True, k == 0 or n == 1,
                   anchor="mm", low=LEVEL_MIN)
        if n < 3:
            arrow(d, (x0 + width + 10, 280), (x0 + width + gap - 10, 280), MUTED, 5)
    return image
