# -*- coding: utf-8 -*-
"""응용 12차시의 예측 결과, 라벨 좌표, 분할 과정을 그림."""
from tools.ai_art import figure
from tools.ai_art.al10 import BLUE_D, BLUE_L, INK, PURPLE_D, PURPLE_L, SIZE, arrow, box, center, sheet
from tools.ai_art.al11 import outline


@figure("a12b-1", *SIZE)
def per_image_results(focus=0):
    drawing = sheet("사진마다 결과 하나")
    for n, count in enumerate((2, 0, 2)):
        x = 65 + (n * 315)
        box(drawing, (x, 128, x + 285, 262), BLUE_L, BLUE_D)
        center(drawing, x + 142, 195, f"사진 {n + 1}", 44, BLUE_D, True)
        arrow(drawing, (x + 142, 268), (x + 142, 310))
        box(drawing, (x, 314, x + 285, 449), PURPLE_L, PURPLE_D)
        center(drawing, x + 142, 353, f"결과 {n + 1}", 34, PURPLE_D, True)
        center(drawing, x + 142, 407, f"박스 {count}개", 36, INK)
    footer = {
        0: "결과 3개     검출 박스 4개",
        1: "가운데 사진의 결과 보기",
        2: "세 결과의 박스 수를 더하기",
        3: "박스가 들어 있는 사진만 세기",
    }
    center(drawing, 520, 512, footer[focus], 41, INK, True)
    return drawing.image()


@figure("a12c-1", *SIZE)
def normalize_box(focus=0):
    drawing = sheet("같은 상자를 픽셀과 비율로 보기")
    box(drawing, (56, 116, 568, 404))
    outline(drawing, (107, 145, 286, 260), BLUE_D)
    center(drawing, 198, 202, "+", 38, PURPLE_D, True)
    center(drawing, 312, 310, "(128, 72) → (576, 360)", 29, BLUE_D, True, True)
    center(drawing, 312, 357, "1280 × 720 픽셀", 33, INK)
    for y, label, size, result, line, fill in (
            (132, "중심 x · 너비", "가로 1280으로 나누기", "0.275 · 0.35", BLUE_D, BLUE_L),
            (277, "중심 y · 높이", "세로 720으로 나누기", "0.3 · 0.4", PURPLE_D, PURPLE_L)):
        if focus == 1:
            continue
        box(drawing, (600, y, 983, y + 124), fill, line)
        center(drawing, 791, y + 26, label, 29, line, True)
        center(drawing, 791, y + 62, size, 28, INK)
        center(drawing, 791, y + 99, "?" if focus == 2 else result, 31, line, True)
    box(drawing, (56, 443, 983, 529), BLUE_L, BLUE_D)
    labels = {
        0: "1   0.275   0.3   0.35   0.4",
        1: "사진 가로와 세로의 크기 읽기",
        2: "두 모서리의 차로 박스 높이 구하기",
        3: "픽셀 너비 = 비율 × 사진 가로",
    }
    center(drawing, 520, 485, labels[focus], 43 if focus == 0 else 37, BLUE_D, True, not focus)
    return drawing.image()


@figure("a12d-1", *SIZE)
def paired_split(focus=0):
    drawing = sheet("이미지와 라벨을 한 쌍으로 나누기")
    box(drawing, (119, 142, 921, 255), BLUE_L, BLUE_D)
    center(drawing, 520, 198, "이름으로 짝지은 파일 23쌍", 42, BLUE_D, True)
    groups = ((68, "학습", 16), (388, "검증", 4), (708, "테스트", 3))
    for n, (x, label, count) in enumerate(groups, 1):
        arrow(drawing, (520, 256), (x + 130, 344))
        box(drawing, (x, 346, x + 260, 464), PURPLE_L, PURPLE_D)
        center(drawing, x + 130, 383, label, 36, PURPLE_D, True)
        answer_hidden = (focus == 2 and n == 2) or (focus == 3 and n == 3)
        value = "쌍 수 확인" if focus == 1 else "?" if answer_hidden else f"{count}쌍"
        center(drawing, x + 130, 432, value, 39)
    footer = {
        0: "16 + 4 + 3 = 23쌍",
        1: "파일을 짝지은 뒤에 묶음으로 나누기",
        2: "학습과 테스트에 넣은 쌍을 먼저 빼기",
        3: "남은 쌍은 모두 테스트에 배정",
    }
    center(drawing, 520, 518, footer[focus], 38, INK, True)
    return drawing.image()


@figure("a12b-21", *SIZE)
def empty():
    return per_image_results(1)


@figure("a12b-22", *SIZE)
def box_total():
    return per_image_results(2)


@figure("a12b-23", *SIZE)
def images_with_boxes():
    return per_image_results(3)


@figure("a12c-21", *SIZE)
def image_size():
    return normalize_box(1)


@figure("a12c-22", *SIZE)
def height_ratio():
    return normalize_box(2)


@figure("a12c-23", *SIZE)
def pixel_width():
    return normalize_box(3)


@figure("a12d-31", *SIZE)
def total_pairs():
    return paired_split(1)


@figure("a12d-32", *SIZE)
def validation_remainder():
    return paired_split(2)


@figure("a12d-33", *SIZE)
def test_remainder():
    return paired_split(3)
