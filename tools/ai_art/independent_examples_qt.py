"""본문의 식·조건으로 그림을 다시 구성함. 원본 강의나 모델을 실행하지 않음."""
import hashlib
import json
import math
from pathlib import Path
import sys

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFontDatabase, QPainterPath, QPen, QImage
from PyQt6.QtWidgets import QApplication
from tools.ai_art import FIXED
from tools.ai_art import l01_training_qt as draw

ROOT = Path(__file__).resolve().parents[2]


def board(title, subtitle=""):
    image, painter = draw.canvas()
    draw.text(painter, 24, 12, 1072, 46, title, size=30, bold=True)
    if subtitle:
        draw.text(painter, 24, 65, 1072, 40, subtitle, size=24, color=draw.MUTED)
    return image, painter


def panels(title, columns, note=""):
    image, painter = board(title)
    width = 1056 / len(columns)
    for index, (heading, lines, color) in enumerate(columns):
        x = 24 + index * width
        painter.setPen(QPen(QColor(color), 3)); painter.setBrush(QColor("white"))
        painter.drawRoundedRect(QRectF(x, 92, width - 16, 388), 14, 14)
        draw.text(painter, x + 16, 106, width - 48, 44, heading, size=25, bold=True, color=color)
        for row, text in enumerate(lines):
            draw.text(painter, x + 16, 178 + row * 55, width - 48, 44, text, size=23)
    draw.text(painter, 24, 510, 1072, 66, note, size=25)
    painter.end()
    return image


def zero_grad():
    return panels("기울기를 지울 수 있는 두 위치", [
        ("역전파 전에 지우기", ["zero_grad()", "예측 → 손실", "backward() → step()", "다음 반복 전에 지움"], draw.BLUE),
        ("갱신 뒤에 지우기", ["예측 → 손실", "backward() → step()", "zero_grad()", "첫 역전파 전 상태 확인"], draw.GREEN)],
        "어느 쪽이든 이번 backward() 전에 이전 기울기가 없어야 합니다.")


def line_plot(painter, rect, xs, ys, max_x, max_y, color, dashed=False):
    x, y, width, height = rect
    point = lambda a, b: (x + width * a / max_x, y + height * (1 - b / max_y))
    for ratio in (0, 0.5, 1):
        draw.line(painter, (x, y + height * ratio), (x + width, y + height * ratio), draw.GRID)
    draw.line(painter, (x, y), (x, y + height), draw.MUTED)
    draw.line(painter, (x, y + height), (x + width, y + height), draw.MUTED)
    path = QPainterPath(QPointF(*point(xs[0], ys[0])))
    for a, b in zip(xs[1:], ys[1:]):
        path.lineTo(QPointF(*point(a, b)))
    pen = QPen(QColor(color), 4)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(pen); painter.drawPath(path)
    return point


def schedules():
    image, painter = board("학습률을 바꾸는 두 규칙", "왼쪽은 에폭마다 한 번, 오른쪽은 배치마다 한 번 step()을 부릅니다.")
    xs = list(range(41)); ys = [0.1 * (1 + math.cos(math.pi * e / 40)) / 2 for e in xs]
    assert abs(ys[20] - 0.05) < 1e-12
    point = line_plot(painter, (78, 175, 390, 270), xs, ys, 40, 0.1, draw.ORANGE)
    draw.text(painter, 68, 120, 440, 36, "CosineAnnealingLR", size=26, bold=True, color=draw.ORANGE)
    for x in (0, 10, 20, 30, 40):
        draw.text(painter, point(x, 0)[0] - 14, 450, 44, 30, str(x), size=20)
    draw.text(painter, 78, 485, 430, 42, "T_max=40 · 시작 0.1 → 0", size=23)
    draw.text(painter, 78, 532, 430, 36, "20에폭: 학습률 0.05", size=24, bold=True)
    warm = 1175 * 0.3 - 1
    def rate(step):
        if step <= warm:
            return 0.003 + (0.00012 - 0.003) * (1 + math.cos(math.pi * step / warm)) / 2
        return 1.2e-8 + (0.003 - 1.2e-8) * (1 + math.cos(math.pi * (step - warm) / (1174 - warm))) / 2
    steps = list(range(1175)); values = [rate(step) for step in steps]
    assert 0.0029999 < max(values) < 0.003 and math.isclose(values[0], 0.00012)
    point = line_plot(painter, (650, 175, 390, 270), steps, values, 1175, 0.003, draw.RED)
    draw.text(painter, 630, 120, 440, 36, "OneCycleLR", size=26, bold=True, color=draw.RED)
    for x in (0, 352, 1175):
        draw.text(painter, point(x, 0)[0] - 18, 450, 70, 30, str(x), size=20)
    draw.text(painter, 610, 485, 490, 42, "235배치 × 5에폭 = 1,175번", size=23)
    draw.text(painter, 610, 532, 490, 36, "시작 0.00012 · 최고 약 0.003", size=23)
    painter.end(); return image


def model_loss():
    return panels("모델을 정의하고 손실을 계산합니다", [
        ("__init__", ["입력·출력 수 받기", "층을 멤버로 등록", "처음 파라미터 설정"], draw.BLUE),
        ("forward", ["입력을 층에 전달", "예측값 반환", "쓴 층만 계산에 참여"], draw.GREEN),
        ("MSE", ["예측 − 정답", "원소마다 제곱", "제곱한 값의 평균"], draw.RED)],
        "MSE를 2로 나누면 손실과 기울기가 모두 절반이 됩니다.")


def first_step():
    image, painter = board("같은 처음 값에서 손실 배율만 바꿉니다", "처음 weight=bias=1 · SGD 학습률 0.01")
    rows = [("항목", "MSE", "MSE ÷ 2"), ("첫 손실", "308.45", "154.22"),
            ("weight 기울기", "−199.64", "−99.82"), ("bias 기울기", "−30.50", "−15.25"),
            ("갱신 뒤 weight", "2.9964", "1.9982"), ("갱신 뒤 bias", "1.3050", "1.1525")]
    for row, values in enumerate(rows):
        for col, text in enumerate(values):
            x, y = 36 + col * 354, 130 + row * 62
            painter.fillRect(QRectF(x, y, 340, 54), QColor(draw.PALE if row else draw.PURPLE_PALE))
            draw.text(painter, x + 12, y + 7, 316, 42, text, size=25, bold=row == 0)
    draw.text(painter, 36, 524, 1048, 48, "같은 학습률이어도 기울기가 절반이면 한 번의 갱신량도 절반입니다.", size=25)
    painter.end(); return image


def loss_checkpoints():
    image, painter = board("선택한 에폭의 손실 기록을 비교합니다", "같은 설정: 처음 w=b=1 · SGD lr=0.01 · 손실=MSE÷2")
    xs, ys = [0, 5000, 20000, 50000], [154.22, 24.21, 21.87, 21.80]
    point = line_plot(painter, (100, 150, 900, 300), xs, ys, 50000, 160, draw.RED, dashed=True)
    for x, y in zip(xs, ys):
        draw.dot(painter, point(x, y), draw.RED)
        draw.text(painter, point(x, y)[0] - (100 if x == 50000 else 0), point(x, y)[1] - 40, 140, 36, str(y), size=25, bold=True)
        draw.text(painter, point(x, 0)[0] - (90 if x == 50000 else 0), 465, 130, 32, str(x), size=23)
    draw.text(painter, 100, 514, 940, 50, "표시한 기록을 잇는 선입니다. 중간 에폭의 손실을 새로 계산한 그림은 아닙니다.", size=23)
    painter.end(); return image


def regression_summary():
    return panels("정답 모양과 갱신 조건을 함께 확인합니다", [
        ("정답 모양", ["출력: [506, 1]", "정답도 [506, 1]", "어긋나면 [506, 506]", "경고 뒤 계산은 진행"], draw.BLUE),
        ("첫 갱신", ["MSE: 308.45", "기울기: −199.64", "학습률: 0.01", "새 weight: 2.9964"], draw.GREEN),
        ("손실 배율", ["MSE÷2: 154.22", "기울기도 절반", "갱신량도 절반", "최솟값의 위치는 같음"], draw.PURPLE)],
        "원하는 정답 모양과 실제 계산한 손실을 먼저 확인합니다.")


def code_summary():
    return panels("학습 기록·직선 그리기·평가를 나눕니다", [
        ("기록", ["history에 두 열", "에폭·손실을 함께 저장", "1,000번마다 기록", "5,000에폭이면 5행"], draw.PURPLE),
        ("직선 그리기", ["입력의 최솟값·최댓값", "reshape(−1, 1)", "no_grad()로 예측", "cpu().numpy()로 표시"], draw.BLUE),
        ("학습과 평가", ["fit은 학습 자료만", "predict로 테스트 예측", "기울기는 역전파 전 초기화", "손실·정확도를 구분"], draw.MUTED)],
        "에폭을 0부터 세면 마지막 기록 번호는 4,000입니다.")


def boundary_summary():
    return panels("분류 경계와 관찰한 모델 값을 연결합니다", [
        ("결정 경계", ["z = w₁x₁+w₂x₂+b", "경계에서는 z=0", "w₂≠0이면", "x₂=−(b+w₁x₁)/w₂"], draw.BLUE),
        ("특징 수", ["특징 1개: 경계는 점", "특징 2개: 경계는 직선", "특징 3개: 경계는 평면", "직선 하나로 XOR 불가"], draw.GREEN),
        ("이 예제의 기록", ["b = −0.1045", "w = [2.951, −5.115]", "x₁=4.4 → x₂≈2.518", "x₁=6.8 → x₂≈3.903"], draw.PURPLE)],
        "기록한 파라미터로 구한 예이며 다른 자료의 학습 결과를 보장하지 않습니다.")


def validation_bars():
    image, painter = board("정확도가 같아도 손실은 다를 수 있습니다", "같은 검증 자료 · 마지막 기록은 에폭 번호 9,000")
    for index, (title, values, maximum) in enumerate((("검증 손실", [0.20501, 0.14243], 0.24), ("검증 정확도", [0.96, 0.96], 1.0))):
        x = 80 + index * 555
        draw.text(painter, x, 124, 420, 42, title, size=28, bold=True)
        for col, (value, color) in enumerate(zip(values, (draw.MUTED, draw.PURPLE))):
            bx, by, height = x + col * 210, 450, 240 * value / maximum
            painter.fillRect(QRectF(bx, by - height, 140, height), QColor(color))
            draw.text(painter, bx, by - height - 44, 170, 38, str(value), size=26, bold=True)
            draw.text(painter, bx, 466, 185, 38, "특징 %d개" % (2 + 2 * col), size=25)
    draw.text(painter, 36, 530, 1048, 44, "회색은 특징 2개, 보라는 특징 4개입니다. 두 지표가 세는 대상을 구분합니다.", size=24)
    painter.end(); return image


def checkpoint():
    return panels("마지막 모델과 가장 좋았던 모델을 구분합니다", [
        ("검증 손실의 예", ["1에폭: 0.6", "2에폭: 0.4 ← 가장 작음", "3에폭: 0.5", "4에폭: 0.7"], draw.MUTED),
        ("좋아졌을 때 보관", ["2에폭의 파라미터 사본", "copy.deepcopy(", "  model.state_dict()", ")"], draw.GREEN),
        ("끝난 뒤 복원", ["마지막은 4에폭의 모델", "보관한 2에폭을 선택", "load_state_dict(best)", "같은 검증 기준으로 선택"], draw.PURPLE)],
        "설명용 손실 값입니다. 평가용 시험 자료를 보고 최적 에폭을 고르지 않습니다.")


def main():
    app = QApplication.instance() or QApplication([])
    for name in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf", "D2Coding-Regular.ttf"):
        fid = QFontDatabase.addApplicationFont(str(ROOT / "gui/fonts" / name))
        assert fid >= 0
        draw.FONTS["code" if name.startswith("D2") else "body"] = QFontDatabase.applicationFontFamilies(fid)[0]
    manifest_path = ROOT / "tools/ai_art/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    functions = {"4c-5": zero_grad, "5e-3": schedules, "7d-4": model_loss, "7e-2": first_step, "7e-3": loss_checkpoints,
                 "7e-5": regression_summary, "7g-4": code_summary, "8c-5": boundary_summary, "9g-2": validation_bars, "15e-4": checkpoint}
    files = []
    for name in sys.argv[1:] or functions:
        fn = functions[name]
        lid = "l%02d" % int(name.split("-")[0][:-1])
        path = ROOT / "ai/learn" / lid / "assets" / (name + ".png")
        image = fn().convertToFormat(QImage.Format.Format_Indexed8, [QColor(color).rgb() for color in FIXED], Qt.ImageConversionFlag.AvoidDither)
        assert image.save(str(path)) and path.stat().st_size <= 150 * 1024
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["files"][f"learn/{lid}/assets/{name}.png"] = {"sha256": sha, "script": "tools/ai_art/independent_examples_qt.py", "fn": fn.__name__}
        files.append({"path": str(path), "sha256": sha})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    assert not any(name in sys.modules for name in ("numpy", "torch", "matplotlib"))
    print(json.dumps({"files": files, "labels": draw.TEXT}, ensure_ascii=False))
    return app


if __name__ == "__main__":
    main()
