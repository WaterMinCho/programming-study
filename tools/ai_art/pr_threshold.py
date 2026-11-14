# -*- coding: utf-8 -*-
"""같은 합성 거래에서 임계값 두 개의 PR점을 그림. 모델을 실행하지 않음."""
from fractions import Fraction
import json
from pathlib import Path

from tools.ai_art import FONTS, file_sha, read_manifest, save

ROOT = Path(__file__).resolve().parents[2]
FRAUD = (92, 61, 38)
NORMAL = (71, 45, 30, 22, 15, 8, 4)


def pr_point(threshold):
    """점수의 100배 정수로 비교해 재현율과 정밀도를 계산함."""
    tp = sum(score >= threshold for score in FRAUD)
    fp = sum(score >= threshold for score in NORMAL)
    return Fraction(tp, len(FRAUD)), Fraction(tp, tp + fp)


def draw():
    """두 점의 이동만 표시함. 전체 PR곡선이나 보간으로 그리지 않음."""
    from PIL import Image, ImageDraw, ImageFont

    before, after = pr_point(70), pr_point(60)
    assert before == (Fraction(1, 3), Fraction(1, 2))
    assert after == (Fraction(2, 3), Fraction(2, 3))
    image = Image.new("RGB", (960, 560), "white")
    pen = ImageDraw.Draw(image)
    ink, blue, purple = "#1f2937", "#2563eb", "#7c3aed"

    def text(x, y, value, size=32, color=ink, bold=False, anchor="lt"):
        path = Path(FONTS) / ("NanumGothic-Bold.ttf" if bold else "NanumGothic-Regular.ttf")
        font = ImageFont.truetype(str(path), size)
        bounds = pen.textbbox((x, y), value, font=font, anchor=anchor)
        assert 0 <= bounds[0] < bounds[2] <= 960 and 0 <= bounds[1] < bounds[3] <= 560
        pen.text((x, y), value, font=font, fill=color, anchor=anchor)

    text(36, 24, "PR점: 임계값 0.70 → 0.60", 38, bold=True)
    text(36, 92, "정밀도", bold=True)
    x0, y0, width, height = 155, 430, 705, 290

    def xy(point):
        return x0 + float(point[0]) * width, y0 - float(point[1]) * height

    for tick in (0, Fraction(1, 2), Fraction(2, 3), 1):
        y = y0 - float(tick) * height
        pen.line((x0, y, x0 + width, y), fill="#e5e7eb", width=2)
        text(x0 - 22, y, str(tick), 30, anchor="rm")
    for tick in (0, Fraction(1, 3), Fraction(2, 3), 1):
        x = x0 + float(tick) * width
        pen.line((x, y0, x, y0 - height), fill="#e5e7eb", width=2)
        text(x, y0 + 16, str(tick), 30, anchor="mt")
    pen.line((x0, y0 - height, x0, y0, x0 + width, y0), fill=ink, width=3)
    text(785, 477, "재현율", bold=True)
    a, b = xy(before), xy(after)
    pen.line((a, b), fill=ink, width=4)
    pen.polygon(((b[0] - 18, b[1] - 6), b, (b[0] - 13, b[1] + 12)), fill=ink)
    pen.ellipse((a[0] - 10, a[1] - 10, a[0] + 10, a[1] + 10), fill=blue)
    pen.rectangle((b[0] - 10, b[1] - 10, b[0] + 10, b[1] + 10), fill=purple)
    text(235, 322, "임계값 0.70", 34, blue, True)
    text(235, 369, "TP 1 · FP 1", 32, blue)
    text(615, 155, "임계값 0.60", 34, purple, True)
    text(615, 197, "TP 2 · FP 1", 32, purple)
    text(36, 523, "합성 예시 · 거래 10건 · 화살표는 두 점의 이동", 30)
    return image


def main():
    """새 그림 한 장과 그 manifest 항목만 저장함."""
    target = save("8f-6", draw(), str(ROOT / "ai/learn/l08/assets"))
    manifest = read_manifest()
    manifest["files"]["learn/l08/assets/8f-6.png"] = {
        "sha256": file_sha(target), "script": "tools/ai_art/pr_threshold.py", "fn": "draw"}
    (ROOT / "tools/ai_art/manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
