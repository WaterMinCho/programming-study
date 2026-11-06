# 글은 사람이 쓴 문장으로 읽히는지 먼저 확인함.
# 구조·문단 끝·어휘·번역투·서식을 대조하며 설명은 ~니다 체로 씀.
# 기록은 ~함 체로 쓰고 새 수치·정답·원자료를 임의로 보태지 않음.
"""학습 기본 패턴의 수치 예를 Qt로 그림. 모델 코드는 실행하지 않음."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ai/learn/l01/assets"
WIDTH, HEIGHT = 1120, 600
INK, MUTED, GRID = "#1f2937", "#6b7280", "#eef0f3"
BLUE, RED, ORANGE, GREEN = "#2563eb", "#dc2626", "#ea580c", "#059669"
GRAY, PALE, HIGHLIGHT = "#d1d5db", "#f3f4f6", "#fef3c7"
PURPLE, PURPLE_PALE = "#7c3aed", "#ede9fe"
CODE = ["optimizer.zero_grad()", "output = model(input)", "loss = fn(output, target)",
        "loss.backward()", "optimizer.step()"]
FONTS = {}
TEXT = []


def loss(w, b):
    """지정한 두 점의 평균 제곱 손실을 반환함."""
    return ((b - 1) ** 2 + (w + b - 3) ** 2) / 2


def gradient(w, b):
    """본문의 수치를 독립 계산함."""
    return w + b - 3, (b - 1) + (w + b - 3)


def verify_math():
    """제안 값과 중앙 차분 결과를 대조함."""
    expected = [(0, 0, 5, -3, -4), (0.6, 0.8, 1.3, -1.6, -1.8)]
    for w, b, value, gw, gb in expected:
        assert math.isclose(loss(w, b), value, abs_tol=1e-12)
        assert all(math.isclose(x, y, abs_tol=1e-12) for x, y in zip(gradient(w, b), (gw, gb)))
        delta = 1e-5
        dw = (loss(w + delta, b) - loss(w - delta, b)) / (2 * delta)
        db = (loss(w, b + delta) - loss(w, b - delta)) / (2 * delta)
        assert math.isclose(dw, gw, abs_tol=1e-8)
        assert math.isclose(db, gb, abs_tol=1e-8)
    assert math.isclose(0 - 0.2 * -3, 0.6, abs_tol=1e-12)
    assert math.isclose(0 - 0.2 * -4, 0.8, abs_tol=1e-12)
    assert math.isclose(-3 - 1.6, -4.6, abs_tol=1e-12)
    assert math.isclose(-4 - 1.8, -5.8, abs_tol=1e-12)


def text(painter, x, y, width, height, value, color=INK, size=22, bold=False, mono=False):
    font = QFont(FONTS["code" if mono else "body"])
    font.setPixelSize(size)
    font.setBold(bold)
    metrics = QFontMetricsF(font)
    for line in value.splitlines():
        assert metrics.horizontalAdvance(line) <= width, (value, width)
    assert 0 <= x and x + width <= WIDTH and 0 <= y and y + height <= HEIGHT, value
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(QRectF(x, y, width, height), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, value)
    TEXT.append(value)


def line(painter, a, b, color=GRAY, width=2, dashed=False):
    pen = QPen(QColor(color), width)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.drawLine(QPointF(*a), QPointF(*b))


def arrow(painter, a, b, color, width=3):
    line(painter, a, b, color, width)
    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    ends = [(b[0] - 11 * math.cos(angle + offset), b[1] - 11 * math.sin(angle + offset)) for offset in (-0.48, 0.48)]
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawPolygon(QPolygonF([QPointF(*b), *(QPointF(*point) for point in ends)]))


def dot(painter, point, color, radius=6, hollow=False):
    painter.setPen(QPen(QColor(color), 3))
    painter.setBrush(QColor("white" if hollow else color))
    painter.drawEllipse(QPointF(*point), radius, radius)


def canvas():
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return image, painter


def project(w, b, value):
    return 720 + w * 80 + b * 65, 438 + w * 18 - b * 24 - value * 22


def data_plot(painter, w, b):
    def point(x, y):
        return 80 + x * 345, 440 - y * 77
    text(painter, 32, 111, 455, 36, "같은 데이터와 예측선", size=26, bold=True)
    for y in (0, 1, 2, 3):
        line(painter, point(0, y), point(1.14, y), GRID)
        text(painter, 46, point(0, y)[1] - 15, 28, 30, str(y), MUTED, 20)
    arrow(painter, point(0, -0.15), point(0, 3.55), MUTED, 2)
    arrow(painter, point(-0.02, 0), point(1.18, 0), MUTED, 2)
    text(painter, 464, 440, 32, 30, "x", MUTED, 22)
    text(painter, 48, 157, 32, 30, "y", MUTED, 22)
    for x in (0, 1):
        text(painter, point(x, 0)[0] - 8, 449, 30, 28, str(x), MUTED, 20)
    line(painter, point(0, 0), point(1.1, 0), BLUE, 3, True)
    if w or b:
        line(painter, point(0, b), point(1.1, 1.1 * w + b), BLUE, 4)
    else:
        line(painter, point(0, 0), point(1.1, 0), BLUE, 4)
    for x, y in ((0, 1), (1, 3)):
        dot(painter, point(x, y), INK)
        label_x = 96 if x == 0 else 303
        label_y = point(x, y)[1] - 40 if x == 0 else point(x, y)[1] + 10
        text(painter, label_x, label_y, 165, 32, f"정답 ({x}, {y})", size=22)
        dot(painter, point(x, w * x + b), BLUE, 6)
    text(painter, 97, 151, 400, 30, "검정은 정답, 파랑은 예측입니다.", size=22)
    text(painter, 97, 483, 400, 30, "점선은 갱신 전 예측선입니다.", BLUE, 21)


def surface(painter, w, b, show_gradient, show_update):
    text(painter, 566, 111, 520, 36, "파라미터 위치와 손실 곡면", size=26, bold=True)
    text(painter, 566, 150, 520, 30, "가로 w · 세로 b · 높이 L", MUTED, 22)
    cells = []
    for wi in range(12):
        for bi in range(8):
            wa, ba = -0.5 + wi * 0.25, -0.5 + bi * 0.25
            corners = [(wa, ba), (wa + 0.25, ba), (wa + 0.25, ba + 0.25), (wa, ba + 0.25)]
            cells.append((wa - ba, corners))
    for _, corners in sorted(cells):
        painter.setPen(QPen(QColor("#9fb2c4"), 0.8))
        shade = QColor("#fee2e2")
        shade.setAlpha(175)
        painter.setBrush(shade)
        painter.drawPolygon(QPolygonF([QPointF(*project(a, b0, loss(a, b0))) for a, b0 in corners]))
    origin = project(-0.5, -0.5, 0)
    for endpoint, color in ((project(2.65, -0.5, 0), GREEN), (project(-0.5, 1.65, 0), GREEN), (project(-0.5, -0.5, 10), RED)):
        arrow(painter, origin, endpoint, color, 2)
    text(painter, 910, 482, 90, 30, "w", GREEN, 24, True)
    text(painter, 790, 377, 70, 30, "b", GREEN, 24, True)
    text(painter, 617, 192, 60, 30, "L", RED, 24, True)
    if show_update:
        path = QPainterPath()
        for index in range(25):
            t = index / 24
            point = project(0.6 * t, 0.8 * t, loss(0.6 * t, 0.8 * t))
            if index == 0:
                path.moveTo(QPointF(*point))
            else:
                path.lineTo(QPointF(*point))
        painter.setPen(QPen(QColor(GREEN), 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        before_end = project(0.6 * 0.94, 0.8 * 0.94, loss(0.6 * 0.94, 0.8 * 0.94))
        arrow(painter, before_end, project(0.6, 0.8, 1.3), GREEN)
        dot(painter, project(0, 0, 5), GREEN, 6, True)
        arrow(painter, project(0, 0, 0), project(0.6, 0.8, 0), GREEN, 3)
    current = project(w, b, loss(w, b))
    base = project(w, b, 0)
    line(painter, base, current, MUTED, 1, True)
    dot(painter, current, GREEN, 7)
    if show_gradient:
        gw, gb = gradient(w, b)
        endpoint = project(w + gw * 0.12, b + gb * 0.12, 0)
        arrow(painter, base, endpoint, ORANGE, 4)
        text(painter, 567, 518, 525, 30, "주황은 w,b 평면의 기울기 방향입니다.", ORANGE, 22)
    else:
        text(painter, 567, 518, 500, 30, "초록 점은 현재 파라미터의 손실입니다.", GREEN, 22)
    label = "w=0, b=0" if not w else "w=0.6, b=0.8"
    text(painter, 714, 200, 380, 32, label, GREEN, 23, True)
    text(painter, 714, 235, 380, 32, "L=5" if not w else "다시 계산한 L=1.3", RED, 23, True)


def training_overview():
    titles = ["시작할 때는 예측이 정답보다 작습니다.", "backward는 현재 위치의 기울기를 구합니다.",
              "step 뒤 예측과 손실을 다시 계산합니다.", "다음 backward는 새 위치의 기울기를 구합니다."]
    details = ["모델 y=wx+b · 시작 w=0, b=0 · 예측 [0, 0] · 손실 L=5",
               "w,b는 0,0으로 유지합니다.  dL/dw=−3, dL/db=−4",
               "step 직후의 output과 loss는 이전 값입니다. 여기서는 model과 fn을 다시 계산합니다.",
               "새 기울기는 dL/dw=−1.6, dL/db=−1.8입니다. w,b는 아직 0.6,0.8입니다."]
    images = []
    for index in range(4):
        w, b = (0, 0) if index < 2 else (0.6, 0.8)
        image, painter = canvas()
        text(painter, 24, 18, 1072, 42, f"{index + 1}/4  {titles[index]}", size=29, bold=True)
        text(painter, 24, 66, 1072, 32, details[index], size=22)
        data_plot(painter, w, b)
        surface(painter, w, b, index in (1, 3), index >= 2)
        if index == 2:
            text(painter, 25, 521, 520, 30, "초록 이동은 기울기의 반대 방향입니다.", GREEN, 22)
        else:
            text(painter, 25, 521, 185, 30, "w,b=0,0" if index < 2 else "w,b=0.6,0.8", GREEN, 21)
            text(painter, 210, 521, 240, 30, "output=[0,0]" if index < 2 else "output=[0.8,1.4]", BLUE, 21)
            text(painter, 450, 521, 110, 30, "L=5" if index < 2 else "L=1.3", RED, 21)
        text(painter, 24, 564, 1072, 29, "구조·차원 고정: 자료·예측은 2행×1열, w·b·손실에는 값을 하나씩 담습니다.", MUTED, 21)
        painter.end()
        images.append(image)
    return images


def training_steps():
    frames = [
        ("시작", -1, "0, 0", "아직 계산하지 않음", "아직 계산하지 않음", "빈 칸", "입력 x=[0,1], 정답=[1,3], 모델 예측=wx+b", "학습률은 0.2로 정합니다."),
        ("zero_grad", 0, "0, 0", "아직 계산하지 않음", "아직 계산하지 않음", "None 또는 0", "기울기 버퍼만 비웁니다.", "w,b를 0으로 되돌리는 줄이 아닙니다."),
        ("순전파", 1, "0, 0", "[0, 0]", "아직 계산하지 않음", "None 또는 0", "예측=[0×0+0, 0×1+0]=[0,0]", "계산한 예측을 output에 담습니다."),
        ("손실 계산", 2, "0, 0", "[0, 0]", "5", "None 또는 0", "L=((0−1)²+(0−3)²)/2=5", "두 예측의 제곱 오차를 평균 냅니다."),
        ("backward", 3, "0, 0", "[0, 0]", "5", "[−3, −4]", "dL/dw=−3, dL/db=−4를 기울기 버퍼에 담습니다.", "w,b와 저장된 예측·손실은 바뀌지 않습니다."),
        ("step", 4, "0.6, 0.8", "[0, 0]", "5", "[−3, −4]", "w=0−0.2×(−3)=0.6, b=0−0.2×(−4)=0.8", "step은 w,b만 바꿉니다. 저장된 output=[0,0], loss=5를 유지합니다."),
        ("다음 회차의 zero_grad", 0, "0.6, 0.8", "[0, 0]", "5", "None 또는 0", "지난 기울기 [−3,−4]를 비웁니다.", "갱신한 w=0.6, b=0.8은 유지합니다."),
        ("다음 순전파", 1, "0.6, 0.8", "[0.8, 1.4]", "5", "None 또는 0", "예측=[0.6×0+0.8, 0.6×1+0.8]=[0.8,1.4]", "output을 새로 구했습니다. 아직 loss는 이전 값 5입니다."),
        ("다음 손실 계산", 2, "0.6, 0.8", "[0.8, 1.4]", "1.3", "None 또는 0", "L=((0.8−1)²+(1.4−3)²)/2=1.3", "손실도 다시 계산한 뒤에야 loss=1.3이 됩니다."),
        ("다음 backward와 누적 비교", 3, "0.6, 0.8", "[0.8, 1.4]", "1.3", "[−1.6, −1.8]", "비웠으면 [−1.6,−1.8], 비우지 않았으면 [−4.6,−5.8]입니다.", "지금 위치의 기울기로 갱신하려고 지난 기울기를 먼저 비웁니다."),
    ]
    images = []
    for index, (title, active, params, output, value, grad, calculation, note) in enumerate(frames):
        image, painter = canvas()
        text(painter, 24, 16, 1072, 44, f"{index + 1}/10  {title}", size=29, bold=True)
        text(painter, 24, 64, 1072, 32, "같은 자료·모델을 반복합니다. 값의 목록은 [w, b] 순서입니다.", size=22)
        text(painter, 28, 106, 495, 36, "기존 코드의 순서대로 읽습니다.", size=24, bold=True)
        for row, code in enumerate(CODE):
            y = 153 + row * 55
            painter.fillRect(QRectF(24, y, 500, 47), QColor(HIGHLIGHT if row == active else PALE))
            text(painter, 39, y + 5, 470, 36, f"{row + 1}  {code}", size=24, mono=True)
        text(painter, 555, 106, 535, 36, "지금 저장된 값", size=24, bold=True)
        states = [("w, b", params, GREEN), ("output", output, BLUE), ("loss", value, RED), ("w.grad, b.grad", grad, ORANGE)]
        for row, (label, data, color) in enumerate(states):
            y = 156 + row * 57
            line(painter, (551, y + 45), (1094, y + 45), GRID)
            text(painter, 558, y, 196, 40, label, color, 23, True)
            text(painter, 768, y, 326, 40, data, color, 23)
        painter.fillRect(QRectF(24, 445, 1072, 98), QColor(PALE))
        text(painter, 39, 452, 1040, 38, calculation, size=23)
        text(painter, 39, 493, 1040, 38, note, size=22)
        text(painter, 24, 564, 1072, 29, "구조·차원 고정: 자료·예측은 2행×1열, w·b·손실에는 값을 하나씩 담습니다.", MUTED, 21)
        painter.end()
        images.append(image)
    return images


def development_flow():
    """전체 개발 흐름에서 한 과정의 입력·작업·결과를 크게 표시함."""
    rows = [
        ("문제 정의", "풀고 싶은 분류 문제", "분류 대상과 기준 정하기", "맞힐 클래스·평가 기준", "지금은 전체 순서를 봅니다."),
        ("데이터 수집", "구분할 클래스와 대상", "이미지와 정답 준비하기", "이미지·정답 묶음", "10·15차시 · 자료와 정답"),
        ("전처리", "이미지·정답 묶음", "크기·값을 맞추고 묶기", "같은 모양의 이미지 배치", "10·15차시 · 변환과 배치"),
        ("모델 설계", "배치 모양·클래스 수", "입력과 마지막 층 정하기", "클래스별 점수를 내는 모델", "13차시 · 새 분류기"),
        ("학습", "모델·학습용 배치", "학습 기본 패턴 반복하기", "갱신한 모델 파라미터", "14차시 · 갱신 범위와 학습률"),
        ("평가", "학습한 모델·검증 배치", "갱신 없이 손실·정확도 재기", "검증 손실·정확도", "10·12차시 · 지표와 검증 곡선"),
        ("개선", "검증 손실·예측 오류", "학습률 등 조건 다시 선택하기", "다시 학습할 조건", "조건을 바꿔 학습·평가합니다."),
        ("배포", "선택한 모델·입력 조건", "예측을 쓸 환경에 연결하기", "새 입력에 대한 예측", "모델을 실제로 쓰는 과정입니다."),
        ("모니터링", "새 입력·예측 결과", "성능 변화와 오류 살피기", "추가 자료·재학습 판단", "필요하면 자료 준비로 돌아갑니다."),
    ]
    images = []
    for index, (name, source, action, result, course) in enumerate(rows):
        image, painter = canvas()
        text(painter, 24, 14, 1072, 40, "학습 기본 패턴은 개발 과정의 학습 안에서 반복합니다.", size=28, bold=True)
        text(painter, 24, 65, 330, 34, "전체 개발 흐름", size=24, bold=True)
        text(painter, 414, 65, 682, 34, "한 과정의 입력·할 일·결과를 잇습니다.", size=24, bold=True)
        for number, row in enumerate(rows):
            y = 112 + number * 45
            is_purple = 1 <= number <= 5
            color = PURPLE if is_purple else INK
            painter.setBrush(QColor(PURPLE_PALE if is_purple else PALE))
            painter.setPen(QPen(QColor(color if number == index else GRAY), 3 if number == index else 1))
            painter.drawRoundedRect(QRectF(24, y, 320, 37), 7, 7)
            text(painter, 42, y + 2, 284, 32, f"{number + 1}  {row[0]}", color, 23, number == index)
        start_y = 112 + index * 45 + 18
        line(painter, (349, start_y), (383, start_y), PURPLE, 3)
        line(painter, (383, start_y), (383, 305), PURPLE, 3)
        arrow(painter, (383, 305), (407, 305), PURPLE, 3)
        painter.setPen(QPen(QColor(PURPLE if 1 <= index <= 5 else GRAY), 2))
        painter.setBrush(QColor("white"))
        painter.drawRoundedRect(QRectF(414, 112, 682, 394), 12, 12)
        text(painter, 438, 126, 634, 46, f"{index + 1}/9  {name}", PURPLE if 1 <= index <= 5 else INK, 32, True)
        for row_index, (label, value) in enumerate((("입력", source), ("할 일", action), ("결과", result), ("연결", course))):
            y = 194 + row_index * 75
            text(painter, 438, y, 95, 38, label, MUTED, 22)
            text(painter, 548, y - 2, 524, 42, value, PURPLE if row_index == 3 and 1 <= index <= 5 else INK,
                 25 if row_index == 3 else 27, row_index == 2)
        if index == 0:
            connection = "문제 정의 → 데이터 수집 → 전처리"
        elif index == len(rows) - 1:
            connection = "모니터링 → 필요하면 자료 준비·개선"
        else:
            connection = f"{rows[index - 1][0]} → {name} → {rows[index + 1][0]}"
        text(painter, 414, 520, 682, 34, connection, PURPLE, 24)
        text(painter, 24, 565, 1072, 29, "보라색 과정은 10~15차시에서 하나씩 배웁니다. 학습 한 바퀴는 전체 개발 흐름의 일부입니다.", MUTED, 21)
        painter.end()
        images.append(image)
    return images


def save_gif(images, path, pillow):
    """Qt 그림을 기존 Pillow로 64색 GIF에 저장함."""
    frames = []
    for image in images:
        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
        frame = pillow.frombytes("RGBA", (WIDTH, HEIGHT), rgba.constBits().asstring(rgba.sizeInBytes())).convert("RGB")
        frames.append(frame)
    sheet = pillow.new("RGB", (WIDTH, HEIGHT * len(frames)), "white")
    for index, frame in enumerate(frames):
        sheet.paste(frame, (0, HEIGHT * index))
    palette = sheet.quantize(colors=64)
    fixed = ["#ffffff", INK, MUTED, GRAY, GRID, BLUE, RED, ORANGE, GREEN, PALE, HIGHLIGHT, "#fee2e2", "#9fb2c4"]
    if path.stem == "1b-8":
        fixed.extend((PURPLE, PURPLE_PALE))
    fixed_rgb = [channel for color in fixed for channel in (QColor(color).red(), QColor(color).green(), QColor(color).blue())]
    learned = palette.getpalette()
    colors = fixed_rgb + learned[:(64 - len(fixed)) * 3]
    palette.putpalette(colors + [0] * (768 - len(colors)))
    frames = [frame.quantize(palette=palette, dither=pillow.Dither.NONE) for frame in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=[2400] * len(frames),
                   loop=0, disposal=1, optimize=True)
    with pillow.open(path) as saved:
        assert saved.size == (WIDTH, HEIGHT) and saved.n_frames == len(frames)
        for index in range(saved.n_frames):
            saved.seek(index)
            assert saved.info["duration"] == 2400
            assert saved.convert("RGB").tobytes() == frames[index].convert("RGB").tobytes()
    assert path.stat().st_size <= 250 * 1024, (path.name, path.stat().st_size)


def main():
    parser = argparse.ArgumentParser(description="기존 Qt와 Pillow로 학습 패턴 그림을 만듭니다.")
    parser.add_argument("--pillow-site", help="이미 설치된 Pillow의 site-packages 경로입니다.")
    parser.add_argument("--only", nargs="+", choices=("1b-6", "1b-7", "1b-8"), help="지정한 새 그림만 만듭니다.")
    args = parser.parse_args()
    if args.pillow_site:
        sys.path.append(args.pillow_site)
    from PIL import Image
    app = QApplication.instance() or QApplication([])
    for name in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf", "D2Coding-Regular.ttf", "D2Coding-Bold.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(ROOT / "gui/fonts" / name))
        assert font_id >= 0, name
        FONTS["code" if name.startswith("D2") else "body"] = QFontDatabase.applicationFontFamilies(font_id)[0]
    verify_math()
    manifest_path = ROOT / "tools/ai_art/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    result = []
    for name, fn in (("1b-6", training_overview), ("1b-7", training_steps), ("1b-8", development_flow)):
        if args.only and name not in args.only:
            continue
        path = OUT / f"{name}.gif"
        save_gif(fn(), path, Image)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["files"][f"learn/l01/assets/{name}.gif"] = {
            "sha256": sha, "script": "tools/ai_art/l01_training_qt.py", "fn": fn.__name__}
        result.append({"file": str(path), "sha256": sha, "bytes": path.stat().st_size})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    assert not any(name in sys.modules for name in ("torch", "numpy", "matplotlib"))
    print(json.dumps({"files": result, "math": "제안 값과 중앙 차분 검산을 통과했음", "font": FONTS}, ensure_ascii=False))
    return app


if __name__ == "__main__":
    main()
