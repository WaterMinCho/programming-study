# -*- coding: utf-8 -*-
"""응용 11차시의 박스, 비교 순서, 검출 평가 그림을 그림."""
from tools.ai_art import figure
from tools.ai_art.al10 import (
    BLUE, BLUE_D, BLUE_L, INK, PURPLE, PURPLE_D, PURPLE_L, RED, RED_D, RED_L,
    RULE, SIZE, WHITE, arrow, box, center, left, sheet,
)


def outline(s, bounds, color, dash=None, width=5):
    x1, y1, x2, y2 = bounds
    s.path([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], color, width, dash=dash, closed=True)


def grid(s, x, y, cell, cols, rows):
    for col in range(cols + 1):
        g = x + cell * col
        s.path([(g, y), (g, y + cell * rows)], RULE, 2)
    for row in range(rows + 1):
        g = y + cell * row
        s.path([(x, g), (x + cell * cols, g)], RULE, 2)


def scaled(x, y, cell, coords):
    x1, y1, x2, y2 = coords
    return x + cell * x1, y + cell * y1, x + cell * x2, y + cell * y2


def overlap_grid(s, x, y, cell, first, second, stage, cols=6, rows=4):
    intersection = (max(first[0], second[0]), max(first[1], second[1]),
                    min(first[2], second[2]), min(first[3], second[3]))
    if stage == "union":
        for bounds in (first, second):
            s.plate(scaled(x, y, cell, bounds), BLUE_L, BLUE_L, 0, 0)
    if stage == "intersection":
        s.plate(scaled(x, y, cell, intersection), PURPLE_L, PURPLE_L, 0, 0)
    grid(s, x, y, cell, cols, rows)
    outline(s, scaled(x, y, cell, first), BLUE_D)
    outline(s, scaled(x, y, cell, second), RED_D, (13, 9))


def badge(s, x, y, w, label, tone=BLUE_D, fill=BLUE_L, size=37):
    box(s, (x, y, x + w, y + 70), fill, tone)
    center(s, x + w / 2, y + 35, label, size, tone, True)


@figure("a11a-1", *SIZE)
def detection_fields():
    s = sheet("같은 번호의 값이 검출 한 건")
    box(s, (50, 135, 415, 467))
    grid(s, 82, 170, 46, 6, 5)
    outline(s, (128, 216, 266, 400), BLUE_D)
    outline(s, (220, 170, 358, 308), RED_D, (14, 9))
    center(s, 177, 363, "0번", 32, BLUE_D, True)
    center(s, 309, 203, "1번", 32, RED_D, True)
    for y, idx, coords, name, score, tone, fill in (
        (135, "0번", "(1, 1, 4, 5)", "사람", "0.82", BLUE_D, BLUE_L),
        (306, "1번", "(3, 0, 6, 3)", "자전거", "0.50", RED_D, RED_L),
    ):
        box(s, (452, y, 990, y + 151), fill, tone)
        left(s, 475, y + 46, idx, 37, tone, True)
        left(s, 568, y + 46, coords, 37, INK, True, True)
        left(s, 568, y + 105, name + "  ·  " + score, 38, INK)
    center(s, 520, 515, "박스 좌표  ·  클래스  ·  점수", 36)
    return s.image()


@figure("a11b-1", *SIZE)
def iou_sequence():
    s = sheet("박스는 고정하고 칠한 범위만 바꾸기", PURPLE)
    for x, name, stage, note in (
        (54, "두 박스", "outlines", "각각 12칸"),
        (379, "교집합", "intersection", "함께 덮은 4칸"),
        (704, "합집합", "union", "하나라도 덮은 20칸"),
    ):
        center(s, x + 132, 161, name, 41, INK, True)
        overlap_grid(s, x, 222, 44, (0, 0, 4, 3), (2, 1, 6, 4), stage)
        center(s, x + 132, 438, note, 29)
    center(s, 185, 516, "A 실선 · B 점선", 31)
    center(s, 739, 516, "IoU = 4 ÷ 20 = 0.2", 39, PURPLE_D, True)
    return s.image()


@figure("a11c-1", *SIZE)
def nms_sequence():
    s = sheet("남긴 후보만 다음 억제의 기준", PURPLE)
    status = [
        ("점수순으로 놓기", ("대기", "대기", "대기")),
        ("A와 비교하기", ("선택", "제거", "대기")),
        ("C 선택하기", ("선택", "제거", "선택")),
    ]
    for i, (name, states) in enumerate(status):
        x = 45 + i * 330
        center(s, x + 145, 143, name, 36, INK, True)
        for row, (name, score, start, state) in enumerate(zip("ABC", ("0.90", "0.70", "0.55"), (0, 2, 5), states)):
            y = 211 + 88 * row
            tone = {"대기": PURPLE_D, "제거": RED_D, "선택": BLUE_D}[state]
            left(s, x, y, f"{name} {score}", 32, tone, True, True)
            left(s, x + 204, y, state, 32, tone, True)
            unit = 16
            line_x = x + start * unit
            s.path([(line_x, y + 28), (line_x + 10 * unit, y + 28)],
                   tone, 8, dash=(15, 10) if state == "제거" else None)
        s.path([(x, 474), (x + 240, 474)], INK, 2)
        for tick in (0, 5, 10, 15):
            g = x + 16 * tick
            s.path([(g, 467), (g, 481)], INK, 2)
            center(s, g, 502, str(tick), 25, INK, code=True)
    return s.image()


@figure("a11d-1", *SIZE)
def detector_stages():
    s = sheet("공유 특징에서 제안과 최종 검출로")
    badge(s, 56, 232, 245, "이미지 특징")
    badge(s, 407, 154, 225, "RPN", PURPLE_D, PURPLE_L)
    badge(s, 718, 232, 245, "RoI 헤드")
    arrow(s, (301, 243), (398, 190), PURPLE_D)
    arrow(s, (632, 190), (706, 235), PURPLE_D)
    arrow(s, (305, 284), (706, 284), BLUE_D)
    center(s, 527, 327, "같은 특징맵 사용", 34, BLUE_D, True)
    center(s, 520, 111, "물체가 있을 만한 영역을 제안", 33, PURPLE_D)
    arrow(s, (840, 312), (840, 389), BLUE_D)
    box(s, (584, 406, 966, 483), BLUE_L, BLUE)
    center(s, 775, 444, "후보별 클래스와 보정 박스", 32, BLUE_D, True)
    return s.image()


@figure("a11e-1", *SIZE)
def detection_batch():
    s = sheet("사진마다 정답 박스 수가 달라도 한 쌍으로")
    center(s, 250, 151, "이미지 목록", 41, INK, True)
    center(s, 739, 151, "정답 사전 목록", 41, INK, True)
    for row, (n, positions, theme, fill) in enumerate((
        (1, [(0, 0, 2, 2)], BLUE_D, BLUE_L),
        (3, [(0, 0, 1, 2), (2, 0, 3, 2), (4, 0, 5, 2)], PURPLE_D, PURPLE_L),
    )):
        y = 193 + row * 143
        box(s, (80, y, 414, y + 118), fill, theme)
        left(s, 109, y + 59, f"{row+1}번 사진", 36, theme, True)
        for coords in positions:
            outline(s, scaled(267, y + 34, 24, coords), theme)
        arrow(s, (430, y + 58), (515, y + 58), theme)
        box(s, (533, y, 964, y + 118), fill, theme)
        center(s, 748, y + 39, f"박스 {n}개 · 레이블 {n}개", 35, theme, True)
        center(s, 748, y + 83, f"boxes: ({n}, 4)", 36, INK, True, True)
    center(s, 520, 511, "같은 자리의 이미지와 정답이 대응합니다.", 37)
    return s.image()


def eval_pair(s, x, y, prediction, cell=25):
    grid(s, x, y, cell, 12, 4)
    outline(s, scaled(x, y, cell, (1, 1, 4, 4)), BLUE_D, width=6)
    outline(s, scaled(x, y, cell, prediction), RED_D, (14, 8), width=6)


@figure("a11f-1", *SIZE)
def counts_and_overlap():
    s = sheet("같은 개수, 다른 위치", PURPLE)
    for x, label, pred, result, theme in (
        (90, "정답과 위치 일치", (1, 1, 4, 4), "IoU 1 · 맞은 검출 1건", BLUE_D),
        (565, "정답과 떨어짐", (8, 1, 11, 4), "IoU 0 · 맞은 검출 0건", RED_D),
    ):
        center(s, x + 180, 165, label, 41, INK, True)
        eval_pair(s, x, 233, pred, 30)
        center(s, x + 180, 416, result, 37, theme, True)
    center(s, 520, 508, "두 장면 모두 정답 하나와 예측 하나 · 기준 0.50", 34)
    return s.image()


@figure("a11b-2", *SIZE)
def shared_cells():
    s = sheet("같은 칸을 덮는 두 상자", PURPLE)
    overlap_grid(s, 284, 130, 94, (0, 0, 3, 2), (2, 0, 6, 2), "outlines", rows=3)
    center(s, 520, 491, "파란 실선 상자  ·  붉은 점선 상자", 36)
    return s.image()


@figure("a11b-3", *SIZE)
def two_areas():
    s = sheet("두 박스의 면적에서 중복 덜기", PURPLE)
    overlap_grid(s, 70, 143, 99, (0, 0, 3, 2), (2, 0, 6, 2), "intersection", rows=3)
    for y, label, tone in ((167, "A의 면적 6", BLUE_D), (269, "B의 면적 8", RED_D),
                           (371, "공통 구역", PURPLE_D)):
        left(s, 733, y, label, 40, tone, True)
    center(s, 520, 510, "같은 크기로 그린 모눈을 셉니다.", 34)
    return s.image()


@figure("a11b-4", *SIZE)
def separate_intervals():
    s = sheet("가로축에서 겹칠 구간 찾기", PURPLE)
    x, cell = 113, 100
    for row, (start, end, tone) in enumerate(((0, 3, BLUE_D), (4, 8, RED_D))):
        y = 198 + 120 * row
        s.path([(x + cell * start, y), (x + cell * end, y)], tone, 14,
               dash=(22, 13) if row else None)
        center(s, x + cell * (start + end) / 2, y - 54, "구간 " + "AB"[row], 40, tone, True)
    s.path([(x, 407), (x + cell * 8, 407)], INK, 4)
    for tick in range(9):
        g = x + cell * tick
        s.path([(g, 394), (g, 421)], INK, 4)
        center(s, g, 451, str(tick), 34, INK, code=True)
    return s.image()


@figure("a11c-2", *SIZE)
def score_choices():
    s = sheet("같은 물체 둘레에 있던 후보 3개", PURPLE)
    box(s, (102, 129, 625, 455))
    for coords, tone, dash in (((205, 191, 520, 397), BLUE_D, None),
                               ((174, 218, 490, 431), RED_D, (17, 11)),
                               ((245, 162, 562, 368), PURPLE_D, (5, 10))):
        outline(s, coords, tone, dash, 7)
    for row, (value, tone, fill) in enumerate((
        ("70점", PURPLE_D, PURPLE_L), ("40점", RED_D, RED_L), ("90점", BLUE_D, BLUE_L),
    )):
        badge(s, 698, 141 + row * 102, 217, value, tone, fill, 43)
    return s.image()


@figure("a11c-3", *SIZE)
def threshold_boundary():
    s = sheet("두 겹침 값을 같은 기준에 놓기", PURPLE)
    x, width, y = 99, 834, 291
    s.path([(x, y), (x + width, y)], INK, 5)
    for value, label, yy, tone in ((0, "0", 363, INK), (.60, "기준 0.60", 181, PURPLE_D),
                                    (.80, "0.80", 363, RED_D), (1, "1", 363, INK)):
        g = x + width * value
        s.path([(g, y-18), (g, y+18)], tone, 5)
        center(s, g, yy, label, 38, tone, True)
    center(s, 515, 460, "임계값보다 큰 후보만 지웁니다.", 39)
    return s.image()


@figure("a11c-4", *SIZE)
def index_candidates():
    s = sheet("선택한 번호와 비교할 후보", PURPLE)
    badge(s, 359, 131, 322, "선택한 박스 · 4번", PURPLE_D, PURPLE_L)
    for index, overlap, x in ((6, "0.72", 115), (8, "0.31", 638)):
        arrow(s, (520, 214), (x + 140, 338), PURPLE_D)
        badge(s, x, 357, 281, f"{index}번 · {overlap}", BLUE_D, BLUE_L)
    center(s, 520, 498, "기준 0.50 · 두 비교는 선택한 박스를 기준으로 합니다.", 32)
    return s.image()


@figure("a11f-2", *SIZE)
def disjoint():
    s = sheet("실선과 점선의 위치를 비교하기", PURPLE)
    eval_pair(s, 153, 146, (8, 1, 11, 4), 61)
    center(s, 320, 448, "정답", 42, BLUE_D, True)
    center(s, 724, 448, "예측", 42, RED_D, True)
    return s.image()


@figure("a11f-3", *SIZE)
def precision_counts():
    s = sheet("예측 수와 정답 수를 구분하기", PURPLE)
    for row, (label, count, fill, tone) in enumerate((
        ("낸 예측", 3, RED_L, RED_D), ("실제 정답", 5, BLUE_L, BLUE_D),
    )):
        y = 157 + 174 * row
        left(s, 100, y + 35, label, 38, tone, True)
        for col in range(count):
            x = 344 + col * 111
            box(s, (x, y, x + 81, y + 70), fill if col < 2 else WHITE, tone)
            center(s, x + 40, y + 34, "✓" if col < 2 else "·", 36, tone, True)
    center(s, 520, 508, "채운 칸은 서로 연결한 박스입니다.", 38)
    return s.image()


@figure("a11f-4", *SIZE)
def one_reference():
    s = sheet("두 예측이 같은 정답을 가리킬 때", PURPLE)
    for y, label in ((155, "높은 점수의 예측"), (321, "낮은 점수의 예측")):
        badge(s, 82, y, 350, label, RED_D, RED_L)
        arrow(s, (452, y + 35), (695, 273), PURPLE_D)
    badge(s, 715, 237, 235, "정답 4번")
    center(s, 520, 508, "한 정답을 한 번만 연결합니다.", 38)
    return s.image()
