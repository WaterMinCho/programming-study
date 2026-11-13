"""같은 눈금으로 원본과 축소한 직사각형을 그림. manifest는 쓰지 않음."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "ai/learn/l15/assets/15b-6.png"
CELL = 24
PANELS = ((90, 430, 12, 8, "#2563eb"), (650, 430, 6, 4, "#ea580c"))


def draw():
    """두 패널의 한 칸 길이와 가로·세로 축척을 같게 적용함."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPen
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont(str(ROOT / "gui/fonts/NanumGothic-Regular.ttf"))
    family = QFontDatabase.applicationFontFamilies(font_id)[0]
    image = QImage(1120, 600, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    def text(x, y, width, value, size=24, color="#1f2937"):
        font = QFont(family)
        font.setPixelSize(size)
        assert QFontMetricsF(font).horizontalAdvance(value) <= width, value
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(QRectF(x, y, width, 38), Qt.AlignmentFlag.AlignLeft, value)

    text(28, 22, 1060, "두 변을 같은 배율로 줄이면 모양을 유지합니다", 32)
    text(28, 78, 1060, "가로와 세로 모두 한 칸은 길이 1이며 두 그림의 눈금도 같습니다.", 24)
    assert PANELS[0][2] / PANELS[0][3] == PANELS[1][2] / PANELS[1][3] == 1.5
    assert PANELS[1][2] / PANELS[0][2] == PANELS[1][3] / PANELS[0][3] == 0.5
    for x, bottom, width, height, color in PANELS:
        painter.setPen(QPen(QColor("#eef0f3"), 1))
        for col in range(13):
            painter.drawLine(x + col * CELL, bottom - 8 * CELL, x + col * CELL, bottom)
        for row in range(9):
            painter.drawLine(x, bottom - row * CELL, x + 12 * CELL, bottom - row * CELL)
        painter.setPen(QPen(QColor(color), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(x, bottom - height * CELL, width * CELL, height * CELL))
        text(x, 154, 390, "원본 12 × 8" if width == 12 else "두 변을 절반으로 6 × 4", 26, color)
        for col in range(0, 13, 2):
            text(x + col * CELL - 8, bottom + 8, 42, str(col), 18)
        for row in range(2, 9, 2):
            text(x - 32, bottom - row * CELL - 14, 30, str(row), 18)
        text(x + 306, bottom - 8, 70, "가로", 20)
        text(x - 38, bottom - 8 * CELL - 43, 100, "세로", 20)
        text(x, 498, 410, f"가로 ÷ 세로 = {width} ÷ {height} = 1.5", 25, color)
    text(28, 554, 1060, "가로와 세로가 각각 절반이 되며 가로와 세로의 비율은 같습니다.", 24)
    painter.end()
    assert app is QApplication.instance()
    return image


if __name__ == "__main__":
    assert draw().save(str(OUTPUT))
    print(OUTPUT)
